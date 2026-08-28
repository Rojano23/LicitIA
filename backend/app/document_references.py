from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    DocumentClassification,
    DocumentPage,
    NormalizedContent,
    TenderDocument,
)

REFERENCE_EXTRACTOR_VERSION = "mvp-02.5.1"

RELATIONSHIP_REFERENCES = "REFERENCES"
RELATIONSHIP_MODIFIES = "MODIFIES"

STATUS_NOT_READY = "NOT_READY"
STATUS_COMPLETED = "COMPLETED"

RESOLUTION_AUTO = "AUTO_RESOLVED"
RESOLUTION_AMBIGUOUS = "AMBIGUOUS"
RESOLUTION_UNRESOLVED = "UNRESOLVED"
RESOLUTION_HUMAN = "HUMAN_RESOLVED"
RESOLUTION_IGNORED = "IGNORED"

HUMAN_ACTION_RESOLVE = "RESOLVE_TO_DOCUMENT"
HUMAN_ACTION_MARK_UNRESOLVED = "MARK_UNRESOLVED"
HUMAN_ACTION_IGNORE = "IGNORE_REFERENCE"
HUMAN_ACTION_CLEAR = "CLEAR_HUMAN_DECISION"

REFERENCE_KIND_ANNEX = "ANNEX"
REFERENCE_KIND_BASES = "BASES"
REFERENCE_KIND_NOTICE = "NOTICE"
REFERENCE_KIND_CONTRACT_MODEL = "CONTRACT_MODEL"

REFERENCE_DETECTORS: list[tuple[str, re.Pattern[str], str]] = [
    (
        REFERENCE_KIND_ANNEX,
        re.compile(r"\banexo\s+[\"'“”]?([a-z0-9]+(?:[-.][a-z0-9]+)*)[\"'“”]?", re.IGNORECASE),
        "ANEXO",
    ),
    (
        REFERENCE_KIND_BASES,
        re.compile(r"\bbases\s+de\s+contrataci[oó]n\b", re.IGNORECASE),
        "BASES DE CONTRATACION",
    ),
    (
        REFERENCE_KIND_NOTICE,
        re.compile(r"\bconvocatoria\b", re.IGNORECASE),
        "CONVOCATORIA",
    ),
    (
        REFERENCE_KIND_CONTRACT_MODEL,
        re.compile(r"\bmodelo\s+de\s+contrato\b", re.IGNORECASE),
        "MODELO DE CONTRATO",
    ),
]

MODIFICATION_CUES = [
    "se modifica",
    "se sustituye",
    "se reemplaza",
    "modificar",
    "modifica",
    "sustituye",
]


@dataclass
class _DetectedReference:
    identity_key: str
    source_document_id: str
    document_page_id: str
    normalized_content_id: str
    source_scope: str
    source_type: str
    source_engine: str | None
    source_region_id: str | None
    raw_reference_text: str
    normalized_reference_key: str
    reference_kind: str
    relationship_hint: str
    excerpt: str


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.lower()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_accents(value: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    return "".join(replacements.get(char, char) for char in value)


def _canonical_annex_identifier(raw_annex_id: str) -> str:
    normalized = _strip_accents(_normalize_text(raw_annex_id))
    normalized = normalized.replace('"', "").replace("'", "")
    normalized = normalized.replace(".", "-")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
    return normalized.upper()


def _reference_key_for_match(reference_kind: str, raw_text: str, annex_id: str | None) -> str:
    if reference_kind == REFERENCE_KIND_ANNEX and annex_id is not None:
        return f"ANEXO:{_canonical_annex_identifier(annex_id)}"
    if reference_kind == REFERENCE_KIND_BASES:
        return "BASES_DE_CONTRATACION"
    if reference_kind == REFERENCE_KIND_NOTICE:
        return "CONVOCATORIA"
    if reference_kind == REFERENCE_KIND_CONTRACT_MODEL:
        return "MODELO_DE_CONTRATO"
    clean = _strip_accents(_normalize_text(raw_text)).upper()
    clean = re.sub(r"\s+", "_", clean)
    return clean


def _relationship_hint_for_context(line_text: str) -> str:
    normalized_line = _strip_accents(_normalize_text(line_text))
    if any(cue in normalized_line for cue in MODIFICATION_CUES):
        return RELATIONSHIP_MODIFIES
    return RELATIONSHIP_REFERENCES


def _excerpt_for_match(line_text: str, raw_reference_text: str) -> str:
    normalized_line = _normalize_text(line_text)
    normalized_ref = _normalize_text(raw_reference_text)
    index = normalized_line.find(normalized_ref)
    if index < 0:
        return line_text.strip()[:220]
    start = max(0, index - 60)
    end = min(len(line_text), index + len(raw_reference_text) + 60)
    return line_text[start:end].strip()


def _source_priority(source: NormalizedContent) -> int:
    if source.source_type == "NATIVE_PDF":
        return 3
    if source.source_type == "OCR" and source.engine == "TESSERACT":
        return 2
    if source.source_type == "OCR" and source.engine == "PADDLEOCR":
        return 1
    return 0


def _build_identity_key(
    source_document_id: str,
    document_page_id: str,
    source_region_id: str | None,
    normalized_reference_key: str,
    relationship_hint: str,
    excerpt: str,
) -> str:
    physical_anchor = source_region_id or f"PAGE:{document_page_id}"
    payload = "|".join(
        [
            source_document_id,
            physical_anchor,
            normalized_reference_key,
            relationship_hint,
            _strip_accents(_normalize_text(excerpt)),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_references_for_source(source_document_id: str, source: NormalizedContent) -> list[_DetectedReference]:
    text = source.normalized_text or ""
    if not text.strip():
        return []

    detected: list[_DetectedReference] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for reference_kind, pattern, _ in REFERENCE_DETECTORS:
            for match in pattern.finditer(line):
                annex_id = match.group(1) if reference_kind == REFERENCE_KIND_ANNEX else None
                raw_reference_text = match.group(0)
                reference_key = _reference_key_for_match(reference_kind, raw_reference_text, annex_id)
                relationship_hint = _relationship_hint_for_context(line)
                excerpt = _excerpt_for_match(line, raw_reference_text)
                identity_key = _build_identity_key(
                    source_document_id=source_document_id,
                    document_page_id=source.document_page_id,
                    source_region_id=source.region_id,
                    normalized_reference_key=reference_key,
                    relationship_hint=relationship_hint,
                    excerpt=excerpt,
                )
                detected.append(
                    _DetectedReference(
                        identity_key=identity_key,
                        source_document_id=source_document_id,
                        document_page_id=source.document_page_id,
                        normalized_content_id=source.id,
                        source_scope=source.source_scope,
                        source_type=source.source_type,
                        source_engine=source.engine,
                        source_region_id=source.region_id,
                        raw_reference_text=raw_reference_text,
                        normalized_reference_key=reference_key,
                        reference_kind=reference_kind,
                        relationship_hint=relationship_hint,
                        excerpt=excerpt,
                    )
                )
    return detected


def _extract_document_references(source_document_id: str, normalized_sources: list[NormalizedContent]) -> list[_DetectedReference]:
    winners: dict[str, tuple[int, _DetectedReference]] = {}
    for source in normalized_sources:
        priority = _source_priority(source)
        for candidate in _extract_references_for_source(source_document_id, source):
            current = winners.get(candidate.identity_key)
            if current is None or priority > current[0]:
                winners[candidate.identity_key] = (priority, candidate)
    return [item for _, item in winners.values()]


def _slugify_filename(value: str) -> str:
    stem = os.path.splitext(value)[0]
    clean = _strip_accents(_normalize_text(stem))
    clean = re.sub(r"[^a-z0-9\s-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _strip_leading_ordinal(slug: str) -> str:
    return re.sub(r"^\s*\d+[\s.)_-]*", "", slug).strip()


def _strip_identifier_suffix(slug: str) -> str:
    parts = slug.split(" ")
    if len(parts) < 2:
        return slug

    tail = parts[-1]
    if tail.count("-") < 2:
        return slug
    if not re.search(r"\d", tail):
        return slug
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", tail):
        return slug

    trimmed = " ".join(parts[:-1]).strip()
    return trimmed or slug


def _filename_alias_variants(filename: str) -> set[str]:
    base = _slugify_filename(filename)
    variants: set[str] = set()
    if not base:
        return variants

    variants.add(base)
    without_ordinal = _strip_leading_ordinal(base)
    if without_ordinal:
        variants.add(without_ordinal)
    without_suffix = _strip_identifier_suffix(without_ordinal)
    if without_suffix:
        variants.add(without_suffix)
    return variants


def _annex_aliases_from_filename(filename: str) -> set[str]:
    aliases: set[str] = set()
    normalized = _slugify_filename(filename)
    matches = re.findall(r"\banexo\s+([a-z0-9]+(?:[-.][a-z0-9]+)*)", normalized, flags=re.IGNORECASE)
    for match in matches:
        aliases.add(f"ANEXO:{_canonical_annex_identifier(match)}")
    return aliases


def _is_accepted_classification(classification: DocumentClassification | None) -> bool:
    return classification is not None and classification.classification_status in {"CONFIRMED", "OVERRIDDEN"}


def _effective_classification_type(classification: DocumentClassification | None) -> str | None:
    if classification is None:
        return None
    if classification.human_type:
        return classification.human_type
    return classification.suggested_type


def _document_alias_keys(document: TenderDocument, classification: DocumentClassification | None) -> set[str]:
    aliases: set[str] = set()
    filename_variants = _filename_alias_variants(document.original_filename)
    for variant in filename_variants:
        aliases.add(f"FILE:{variant}")

    filename_slug = _slugify_filename(document.original_filename)
    aliases.update(_annex_aliases_from_filename(document.original_filename))

    has_bases_phrase = any("bases de contratacion" in variant for variant in filename_variants)
    has_bases_token = any(re.search(r"\bbases\b", variant) is not None for variant in filename_variants)
    if has_bases_phrase:
        aliases.add("BASES_DE_CONTRATACION")
        aliases.add("BASES")
    elif has_bases_token:
        aliases.add("BASES")

    classification_type = _effective_classification_type(classification)
    if has_bases_token and _is_accepted_classification(classification) and classification_type == "BIDDING_RULES":
        aliases.add("BASES_DE_CONTRATACION")

    if "convocatoria" in filename_slug:
        aliases.add("CONVOCATORIA")
    if "modelo de contrato" in filename_slug or "contrato modelo" in filename_slug:
        aliases.add("MODELO_DE_CONTRATO")
    return aliases


def _equivalent_reference_keys(reference_key: str) -> set[str]:
    if reference_key == "BASES_DE_CONTRATACION":
        return {"BASES_DE_CONTRATACION", "BASES"}
    if reference_key == "BASES":
        return {"BASES", "BASES_DE_CONTRATACION"}
    return {reference_key}


def _candidate_targets_for_reference(
    source_document_id: str,
    normalized_reference_key: str,
    alias_index: dict[str, set[str]],
) -> tuple[list[str], bool]:
    candidates: set[str] = set()
    for equivalent_key in _equivalent_reference_keys(normalized_reference_key):
        candidates.update(alias_index.get(equivalent_key, set()))
    if normalized_reference_key.startswith("ANEXO:"):
        for key, value in alias_index.items():
            if key.startswith("ANEXO:") and key == normalized_reference_key:
                candidates.update(value)

    had_self = source_document_id in candidates
    if source_document_id in candidates:
        candidates.remove(source_document_id)

    return sorted(candidates), had_self


def _effective_resolution(reference: DocumentReference) -> tuple[str, str | None]:
    if reference.human_decision == HUMAN_ACTION_IGNORE:
        return RESOLUTION_IGNORED, None
    if reference.human_decision == HUMAN_ACTION_MARK_UNRESOLVED:
        return RESOLUTION_UNRESOLVED, None
    if reference.human_decision == HUMAN_ACTION_RESOLVE and reference.human_target_document_id:
        return RESOLUTION_HUMAN, reference.human_target_document_id
    if reference.resolution_status in {RESOLUTION_AUTO, RESOLUTION_AMBIGUOUS, RESOLUTION_UNRESOLVED, RESOLUTION_IGNORED}:
        return reference.resolution_status, reference.resolved_target_document_id
    return RESOLUTION_UNRESOLVED, None


def _serialize_reference(reference: DocumentReference, current_docs_by_id: dict[str, TenderDocument]) -> dict[str, Any]:
    resolution_status, effective_target_id = _effective_resolution(reference)
    candidates = []
    for candidate_id in (reference.auto_candidate_document_ids or "").split(","):
        candidate_id = candidate_id.strip()
        if not candidate_id:
            continue
        target_doc = current_docs_by_id.get(candidate_id)
        if target_doc is None:
            continue
        candidates.append({"document_id": target_doc.id, "original_filename": target_doc.original_filename})

    target_doc = current_docs_by_id.get(effective_target_id) if effective_target_id else None
    return {
        "id": reference.id,
        "source_document_id": reference.source_document_id,
        "document_page_id": reference.document_page_id,
        "normalized_content_id": reference.normalized_content_id,
        "document_chunk_id": reference.document_chunk_id,
        "source_scope": reference.source_scope,
        "source_type": reference.source_type,
        "source_engine": reference.source_engine,
        "source_region_id": reference.source_region_id,
        "raw_reference_text": reference.raw_reference_text,
        "normalized_reference_key": reference.normalized_reference_key,
        "reference_kind": reference.reference_kind,
        "relationship_hint": reference.relationship_hint,
        "resolution_status": resolution_status,
        "resolved_target_document_id": effective_target_id,
        "resolved_target_filename": target_doc.original_filename if target_doc is not None else None,
        "ambiguous_candidates": candidates,
        "human_target_document_id": reference.human_target_document_id,
        "human_note": reference.human_note,
        "human_decision": reference.human_decision,
        "excerpt": reference.excerpt,
        "extractor_version": reference.extractor_version,
        "created_at": reference.created_at,
        "updated_at": reference.updated_at,
        "page_number": reference.document_page.page_number if reference.document_page is not None else None,
    }


def _serialize_relationship(
    relationship: DocumentRelationship,
    references: list[DocumentReference],
    docs_by_id: dict[str, TenderDocument],
) -> dict[str, Any]:
    supporting_references = []
    for reference in references:
        resolution_status, effective_target_id = _effective_resolution(reference)
        if effective_target_id != relationship.target_document_id:
            continue
        if reference.relationship_hint != relationship.relationship_type:
            continue
        supporting_references.append(
            {
                "reference_id": reference.id,
                "raw_reference_text": reference.raw_reference_text,
                "normalized_reference_key": reference.normalized_reference_key,
                "page_number": reference.document_page.page_number if reference.document_page is not None else None,
                "excerpt": reference.excerpt,
            }
        )

    source_doc = docs_by_id.get(relationship.source_document_id)
    target_doc = docs_by_id.get(relationship.target_document_id)
    return {
        "id": relationship.id,
        "tender_id": relationship.tender_id,
        "source_document_id": relationship.source_document_id,
        "source_document_filename": source_doc.original_filename if source_doc else None,
        "target_document_id": relationship.target_document_id,
        "target_document_filename": target_doc.original_filename if target_doc else None,
        "relationship_type": relationship.relationship_type,
        "supporting_references": supporting_references,
        "created_at": relationship.created_at,
        "updated_at": relationship.updated_at,
    }


def _load_current_documents(db: Session, tender_id: str) -> list[TenderDocument]:
    return (
        db.execute(
            select(TenderDocument)
            .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            .order_by(TenderDocument.imported_at.asc())
        )
        .scalars()
        .all()
    )


def _build_alias_index(db: Session, current_documents: list[TenderDocument]) -> dict[str, set[str]]:
    alias_index: dict[str, set[str]] = {}
    document_ids = [document.id for document in current_documents]
    classifications_by_document_id: dict[str, DocumentClassification] = {}
    if document_ids:
        stmt = (
            select(DocumentClassification)
            .where(DocumentClassification.document_id.in_(document_ids))
            .order_by(DocumentClassification.created_at.desc())
        )
        # current_documents are current-only, so this is used only as optional corroboration.
        for classification in db.execute(stmt).scalars().all():
            classifications_by_document_id.setdefault(classification.document_id, classification)

    for document in current_documents:
        for alias in _document_alias_keys(document, classifications_by_document_id.get(document.id)):
            alias_index.setdefault(alias, set()).add(document.id)
    return alias_index


def _normalized_sources_for_document(db: Session, document_id: str) -> list[NormalizedContent]:
    return (
        db.execute(
            select(NormalizedContent)
            .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
            .options(selectinload(NormalizedContent.document_page))
        )
        .scalars()
        .all()
    )


def _reference_fingerprint(normalized_sources: list[NormalizedContent]) -> str:
    payload = "\n".join(
        [
            "|".join(
                [
                    source.document_page_id,
                    source.source_scope,
                    source.source_type,
                    source.engine or "none",
                    source.region_id or "none",
                    source.normalized_text or "",
                ]
            )
            for source in normalized_sources
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _analysis_row(db: Session, document_id: str) -> DocumentReferenceAnalysis | None:
    return (
        db.execute(
            select(DocumentReferenceAnalysis)
            .where(DocumentReferenceAnalysis.document_id == document_id)
            .options(selectinload(DocumentReferenceAnalysis.references))
        )
        .scalar_one_or_none()
    )


def _upsert_analysis(db: Session, analysis: DocumentReferenceAnalysis | None, document_id: str) -> DocumentReferenceAnalysis:
    if analysis is None:
        analysis = DocumentReferenceAnalysis(document_id=document_id)
        db.add(analysis)
        db.flush()
    return analysis


def _materialize_relationships(
    db: Session,
    tender_id: str,
    source_document_id: str,
    references: list[DocumentReference],
) -> list[DocumentRelationship]:
    existing = (
        db.execute(
            select(DocumentRelationship).where(
                DocumentRelationship.tender_id == tender_id,
                DocumentRelationship.source_document_id == source_document_id,
            )
        )
        .scalars()
        .all()
    )
    by_key = {(row.source_document_id, row.target_document_id, row.relationship_type): row for row in existing}

    desired_keys: set[tuple[str, str, str]] = set()
    for reference in references:
        status, effective_target_id = _effective_resolution(reference)
        if status not in {RESOLUTION_AUTO, RESOLUTION_HUMAN}:
            continue
        if not effective_target_id:
            continue
        if effective_target_id == source_document_id:
            continue
        desired_keys.add((source_document_id, effective_target_id, reference.relationship_hint))

    for stale_key, stale_row in by_key.items():
        if stale_key not in desired_keys:
            db.delete(stale_row)

    realized: list[DocumentRelationship] = []
    for key in sorted(desired_keys):
        row = by_key.get(key)
        if row is None:
            row = DocumentRelationship(
                tender_id=tender_id,
                source_document_id=key[0],
                target_document_id=key[1],
                relationship_type=key[2],
            )
            db.add(row)
            db.flush()
        realized.append(row)
    return realized


def _document_reference_rows(db: Session, source_document_id: str) -> list[DocumentReference]:
    return (
        db.execute(
            select(DocumentReference)
            .where(DocumentReference.source_document_id == source_document_id)
            .order_by(DocumentReference.created_at.asc())
            .options(selectinload(DocumentReference.document_page))
        )
        .scalars()
        .all()
    )


def analyze_document_references(db: Session, tender_id: str, source_document: TenderDocument) -> dict[str, Any]:
    normalized_sources = _normalized_sources_for_document(db, source_document.id)
    analysis = _analysis_row(db, source_document.id)
    analysis = _upsert_analysis(db, analysis, source_document.id)

    if not normalized_sources:
        analysis.extractor_version = REFERENCE_EXTRACTOR_VERSION
        analysis.input_fingerprint_sha256 = ""
        analysis.status = STATUS_NOT_READY
        analysis.analyzed_at = datetime.now(timezone.utc)
        for row in _document_reference_rows(db, source_document.id):
            if row.human_decision is None:
                db.delete(row)
        _materialize_relationships(db, tender_id, source_document.id, _document_reference_rows(db, source_document.id))
        db.flush()
        return {
            "document_id": source_document.id,
            "status": STATUS_NOT_READY,
            "extractor_version": REFERENCE_EXTRACTOR_VERSION,
            "input_fingerprint_sha256": "",
            "references": [],
            "relationships": [],
            "counts": {
                "total_reference_mentions": 0,
                "resolved_references": 0,
                "ambiguous_references": 0,
                "unresolved_references": 0,
                "human_resolved_references": 0,
                "ignored_references": 0,
                "resolved_relationships": 0,
            },
        }

    fingerprint = _reference_fingerprint(normalized_sources)
    current_docs = _load_current_documents(db, tender_id)
    docs_by_id = {doc.id: doc for doc in current_docs}

    current_refs = _document_reference_rows(db, source_document.id)
    if (
        analysis.extractor_version == REFERENCE_EXTRACTOR_VERSION
        and analysis.input_fingerprint_sha256 == fingerprint
        and analysis.status == STATUS_COMPLETED
    ):
        relationships = _materialize_relationships(db, tender_id, source_document.id, current_refs)
        serialized_refs = [_serialize_reference(row, docs_by_id) for row in current_refs]
        serialized_relationships = [_serialize_relationship(row, current_refs, docs_by_id) for row in relationships]
        return _analysis_payload(source_document.id, analysis, serialized_refs, serialized_relationships)

    alias_index = _build_alias_index(db, current_docs)
    detected = _extract_document_references(source_document.id, normalized_sources)

    existing_by_identity = {row.reference_identity_key: row for row in current_refs}
    seen_identity_keys = {item.identity_key for item in detected}

    active_rows: list[DocumentReference] = []
    now = datetime.now(timezone.utc)
    for detected_ref in detected:
        row = existing_by_identity.get(detected_ref.identity_key)
        if row is None:
            row = DocumentReference(
                source_document_id=source_document.id,
                reference_identity_key=detected_ref.identity_key,
            )
            db.add(row)
            db.flush()

        candidates, had_self = _candidate_targets_for_reference(
            source_document_id=source_document.id,
            normalized_reference_key=detected_ref.normalized_reference_key,
            alias_index=alias_index,
        )

        row.document_page_id = detected_ref.document_page_id
        row.analysis_id = analysis.id
        row.normalized_content_id = detected_ref.normalized_content_id
        row.document_chunk_id = None
        row.source_scope = detected_ref.source_scope
        row.source_type = detected_ref.source_type
        row.source_engine = detected_ref.source_engine
        row.source_region_id = detected_ref.source_region_id
        row.raw_reference_text = detected_ref.raw_reference_text
        row.normalized_reference_key = detected_ref.normalized_reference_key
        row.reference_kind = detected_ref.reference_kind
        row.relationship_hint = detected_ref.relationship_hint
        row.auto_candidate_document_ids = ",".join(candidates)
        row.excerpt = detected_ref.excerpt
        row.extractor_version = REFERENCE_EXTRACTOR_VERSION
        row.updated_at = now

        if row.human_decision == HUMAN_ACTION_RESOLVE and row.human_target_document_id:
            row.resolution_status = RESOLUTION_HUMAN
            row.resolved_target_document_id = row.human_target_document_id
        elif row.human_decision == HUMAN_ACTION_IGNORE:
            row.resolution_status = RESOLUTION_IGNORED
            row.resolved_target_document_id = None
        elif row.human_decision == HUMAN_ACTION_MARK_UNRESOLVED:
            row.resolution_status = RESOLUTION_UNRESOLVED
            row.resolved_target_document_id = None
        else:
            if len(candidates) == 0:
                if had_self:
                    row.resolution_status = RESOLUTION_IGNORED
                else:
                    row.resolution_status = RESOLUTION_UNRESOLVED
                row.resolved_target_document_id = None
            elif len(candidates) == 1:
                row.resolution_status = RESOLUTION_AUTO
                row.resolved_target_document_id = candidates[0]
            else:
                row.resolution_status = RESOLUTION_AMBIGUOUS
                row.resolved_target_document_id = None

        active_rows.append(row)

    for stale_row in current_refs:
        if stale_row.reference_identity_key in seen_identity_keys:
            continue
        if stale_row.human_decision is not None:
            continue
        db.delete(stale_row)

    db.flush()

    refreshed_refs = _document_reference_rows(db, source_document.id)
    relationships = _materialize_relationships(db, tender_id, source_document.id, refreshed_refs)

    analysis.extractor_version = REFERENCE_EXTRACTOR_VERSION
    analysis.input_fingerprint_sha256 = fingerprint
    analysis.status = STATUS_COMPLETED
    analysis.analyzed_at = now
    analysis.updated_at = now

    serialized_refs = [_serialize_reference(row, docs_by_id) for row in refreshed_refs]
    serialized_relationships = [_serialize_relationship(row, refreshed_refs, docs_by_id) for row in relationships]
    return _analysis_payload(source_document.id, analysis, serialized_refs, serialized_relationships)


def _analysis_payload(
    document_id: str,
    analysis: DocumentReferenceAnalysis,
    serialized_references: list[dict[str, Any]],
    serialized_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    resolved_references = [item for item in serialized_references if item["resolution_status"] == RESOLUTION_AUTO]
    ambiguous_references = [item for item in serialized_references if item["resolution_status"] == RESOLUTION_AMBIGUOUS]
    unresolved_references = [item for item in serialized_references if item["resolution_status"] == RESOLUTION_UNRESOLVED]
    human_resolved = [item for item in serialized_references if item["resolution_status"] == RESOLUTION_HUMAN]
    ignored = [item for item in serialized_references if item["resolution_status"] == RESOLUTION_IGNORED]

    return {
        "document_id": document_id,
        "status": analysis.status,
        "extractor_version": analysis.extractor_version,
        "input_fingerprint_sha256": analysis.input_fingerprint_sha256,
        "references": serialized_references,
        "relationships": serialized_relationships,
        "counts": {
            "total_reference_mentions": len(serialized_references),
            "resolved_references": len(resolved_references),
            "ambiguous_references": len(ambiguous_references),
            "unresolved_references": len(unresolved_references),
            "human_resolved_references": len(human_resolved),
            "ignored_references": len(ignored),
            "resolved_relationships": len(serialized_relationships),
        },
    }


def list_document_references(db: Session, tender_id: str, document_id: str) -> dict[str, Any]:
    source_document = db.get(TenderDocument, document_id)
    if source_document is None or source_document.tender_id != tender_id:
        raise ValueError("Document not found for tender")

    current_docs = _load_current_documents(db, tender_id)
    docs_by_id = {doc.id: doc for doc in current_docs}
    analysis = _analysis_row(db, document_id)
    refs = _document_reference_rows(db, document_id)
    relationships = (
        db.execute(
            select(DocumentRelationship).where(
                DocumentRelationship.tender_id == tender_id,
                DocumentRelationship.source_document_id == document_id,
            )
        )
        .scalars()
        .all()
    )

    if analysis is None:
        return {
            "document_id": document_id,
            "status": STATUS_NOT_READY,
            "extractor_version": REFERENCE_EXTRACTOR_VERSION,
            "input_fingerprint_sha256": "",
            "references": [],
            "relationships": [],
            "counts": {
                "total_reference_mentions": 0,
                "resolved_references": 0,
                "ambiguous_references": 0,
                "unresolved_references": 0,
                "human_resolved_references": 0,
                "ignored_references": 0,
                "resolved_relationships": 0,
            },
        }

    serialized_refs = [_serialize_reference(row, docs_by_id) for row in refs]
    serialized_relationships = [_serialize_relationship(row, refs, docs_by_id) for row in relationships]
    return _analysis_payload(document_id, analysis, serialized_refs, serialized_relationships)


def analyze_tender_references(db: Session, tender_id: str) -> list[dict[str, Any]]:
    documents = (
        db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.imported_at.asc()))
        .scalars()
        .all()
    )
    results: list[dict[str, Any]] = []
    for document in documents:
        try:
            results.append(analyze_document_references(db, tender_id, document))
        except Exception:
            results.append(
                {
                    "document_id": document.id,
                    "status": STATUS_NOT_READY,
                    "extractor_version": REFERENCE_EXTRACTOR_VERSION,
                    "input_fingerprint_sha256": "",
                    "references": [],
                    "relationships": [],
                    "counts": {
                        "total_reference_mentions": 0,
                        "resolved_references": 0,
                        "ambiguous_references": 0,
                        "unresolved_references": 0,
                        "human_resolved_references": 0,
                        "ignored_references": 0,
                        "resolved_relationships": 0,
                    },
                }
            )
    return results


def list_tender_relationships(
    db: Session,
    tender_id: str,
    source_document_id: str | None = None,
    target_document_id: str | None = None,
    relationship_type: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(DocumentRelationship).where(DocumentRelationship.tender_id == tender_id)
    if source_document_id:
        stmt = stmt.where(DocumentRelationship.source_document_id == source_document_id)
    if target_document_id:
        stmt = stmt.where(DocumentRelationship.target_document_id == target_document_id)
    if relationship_type:
        stmt = stmt.where(DocumentRelationship.relationship_type == relationship_type)

    relationships = db.execute(stmt.order_by(DocumentRelationship.created_at.asc())).scalars().all()

    docs = _load_current_documents(db, tender_id)
    docs_by_id = {doc.id: doc for doc in docs}
    references = (
        db.execute(
            select(DocumentReference)
            .where(DocumentReference.source_document_id.in_([row.source_document_id for row in relationships] or [""]))
            .options(selectinload(DocumentReference.document_page))
        )
        .scalars()
        .all()
    )

    refs_by_source: dict[str, list[DocumentReference]] = {}
    for row in references:
        refs_by_source.setdefault(row.source_document_id, []).append(row)

    return [_serialize_relationship(row, refs_by_source.get(row.source_document_id, []), docs_by_id) for row in relationships]


def apply_human_reference_decision(
    db: Session,
    tender_id: str,
    reference_id: str,
    action: str,
    human_target_document_id: str | None,
    human_note: str | None,
) -> dict[str, Any]:
    reference = db.get(DocumentReference, reference_id)
    if reference is None:
        raise ValueError("Reference not found")

    source_document = db.get(TenderDocument, reference.source_document_id)
    if source_document is None or source_document.tender_id != tender_id:
        raise ValueError("Reference not found for tender")

    normalized_action = action.strip().upper()
    if normalized_action == HUMAN_ACTION_RESOLVE:
        if not human_target_document_id:
            raise ValueError("human_target_document_id is required")
        target_doc = db.get(TenderDocument, human_target_document_id)
        if target_doc is None or target_doc.tender_id != tender_id or not target_doc.is_current:
            raise ValueError("human_target_document_id must point to a current document in the same tender")
        reference.human_decision = HUMAN_ACTION_RESOLVE
        reference.human_target_document_id = human_target_document_id
        reference.human_note = human_note
    elif normalized_action == HUMAN_ACTION_MARK_UNRESOLVED:
        reference.human_decision = HUMAN_ACTION_MARK_UNRESOLVED
        reference.human_target_document_id = None
        reference.human_note = human_note
    elif normalized_action == HUMAN_ACTION_IGNORE:
        reference.human_decision = HUMAN_ACTION_IGNORE
        reference.human_target_document_id = None
        reference.human_note = human_note
    elif normalized_action == HUMAN_ACTION_CLEAR:
        reference.human_decision = None
        reference.human_target_document_id = None
        reference.human_note = human_note
    else:
        raise ValueError(f"Unsupported action: {action}")

    reference.updated_at = datetime.now(timezone.utc)
    db.flush()

    analyze_document_references(db, tender_id, source_document)
    payload = list_document_references(db, tender_id, source_document.id)
    return payload
