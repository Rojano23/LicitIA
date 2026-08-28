from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.document_references import RELATIONSHIP_MODIFIES
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentRelationship,
    NormalizedContent,
    Tender,
    TenderChange,
    TenderChangeEvidence,
    TenderDocument,
    TenderEvent,
)

CHANGE_DETECTOR_VERSION = "mvp-03.3"

REVIEW_SUGGESTED = "SUGGESTED"
REVIEW_CONFIRMED = "CONFIRMED"
REVIEW_REJECTED = "REJECTED"

ORIGIN_DETERMINISTIC = "DETERMINISTIC"

ACTION_CONFIRM = "CONFIRM"
ACTION_REJECT = "REJECT"
ACTION_RESET = "RESET_TO_SUGGESTED"
ACTION_OVERRIDE = "OVERRIDE"

RELATIONSHIP_ORIGIN_CHANGE_ENGINE = "CHANGE_ENGINE"

CHANGE_CLARIFIES = "CLARIFIES"
CHANGE_MODIFIES = "MODIFIES"
CHANGE_REPLACES = "REPLACES"
CHANGE_ADDS = "ADDS"
CHANGE_REMOVES = "REMOVES"
CHANGE_CORRECTS = "CORRECTS"
CHANGE_CONFIRMS = "CONFIRMS"
CHANGE_OTHER = "OTHER"
CHANGE_UNKNOWN = "UNKNOWN"

AUTHORITATIVE_MODIFICATION_TYPES = {
    CHANGE_MODIFIES,
    CHANGE_REPLACES,
    CHANGE_ADDS,
    CHANGE_REMOVES,
    CHANGE_CORRECTS,
}


@dataclass
class DetectedChange:
    semantic_key: str
    change_type: str
    target_reference_key: str | None
    target_document_id: str | None
    target_candidate_document_ids: list[str]
    target_locator_text: str | None
    before_text: str | None
    after_text: str | None
    source_document_id: str
    source_page: int | None
    source_excerpt: str
    evidence_fragments: list[str]


@dataclass
class _DetectedStatement:
    change_type: str
    target_reference_key: str | None
    target_locator_text: str | None
    before_text: str | None
    after_text: str | None
    source_excerpt: str


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    compact = value.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.replace("“", '"').replace("”", '"').replace("’", "'")
    compact = compact.lower().strip()
    compact = _strip_accents(compact)
    compact = re.sub(r"\s+", " ", compact)
    return compact


def _excerpt(value: str, max_len: int = 500) -> str:
    return " ".join(value.split())[:max_len]


def _context_segments(text: str) -> list[str]:
    segments: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for fragment in re.split(r"(?<=[\.;!?])\s+", line):
            candidate = fragment.strip()
            if candidate:
                segments.append(candidate)
    if not segments and text.strip():
        segments.append(text.strip())
    return segments


def _detect_change_type(context: str) -> str:
    normalized = _normalize_text(context)

    if "donde dice" in normalized and "debe decir" in normalized:
        return CHANGE_MODIFIES
    if re.search(r"\b(se\s+sustituye|se\s+reemplaza|queda\s+sustituido|queda\s+reemplazado)\b", normalized):
        return CHANGE_REPLACES
    if re.search(r"\b(se\s+adiciona|se\s+agrega|se\s+anade|queda\s+adicionado)\b", normalized):
        return CHANGE_ADDS
    if re.search(r"\b(se\s+elimina|se\s+cancela|se\s+suprime|queda\s+eliminado)\b", normalized):
        return CHANGE_REMOVES
    if re.search(r"\b(se\s+corrige|se\s+rectifica|fe\s+de\s+erratas|errata)\b", normalized):
        return CHANGE_CORRECTS
    if re.search(r"\b(se\s+modifica|se\s+modifican|queda\s+modificado|debe\s+decir)\b", normalized):
        return CHANGE_MODIFIES
    if re.search(r"\b(se\s+aclara|se\s+precisa|se\s+hace\s+la\s+aclaracion)\b", normalized):
        return CHANGE_CLARIFIES
    if re.search(r"\b(se\s+confirma|permanece\s+sin\s+cambio|no\s+se\s+modifica)\b", normalized):
        return CHANGE_CONFIRMS
    return CHANGE_UNKNOWN


def _has_non_substantive_metadata_context(context: str) -> bool:
    normalized = _normalize_text(context)
    return any(
        token in normalized
        for token in (
            "fecha de modificacion",
            "ultima modificacion",
            "ultima revision",
            "revision 2",
            "revision:",
            "file modified",
        )
    )


def _is_operational_instruction_context(context: str) -> bool:
    normalized = _normalize_text(context)
    if not re.search(r"\bcontratista\b", normalized):
        return False
    if not re.search(r"\b(modificar|modifique|modificado|modificacion)\b", normalized):
        return False
    # Keep only solicitation/tender-content assertions, not contractor execution actions.
    return not any(
        token in normalized
        for token in (
            "bases",
            "convocatoria",
            "anexo",
            "numeral",
            "apartado",
            "seccion",
            "punto",
            "tabla",
            "partida",
            "debe decir",
            "donde dice",
        )
    )


def _extract_locator_text(context: str) -> str | None:
    normalized = _normalize_text(context)
    patterns = [
        r"\bnumeral\s+[0-9]+(?:\.[0-9]+)*[a-z]?\b",
        r"\bapartado\s+[a-z0-9][a-z0-9\.-]*\b",
        r"\bseccion\s+[ivxlcdm0-9]+(?:\.[0-9]+)*\b",
        r"\bpunto\s+[0-9]+(?:\.[0-9]+)*\b",
        r"\btabla\s+[a-z0-9]+\b",
        r"\bpartida\s+[0-9]+\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(0)
    return None


def _canonical_annex_identifier(raw_annex_id: str) -> str:
    normalized = _normalize_text(raw_annex_id)
    normalized = normalized.replace(".", "-")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
    return normalized.upper()


def _extract_target_reference_key(context: str) -> str | None:
    normalized = _normalize_text(context)

    annex_match = re.search(r"\banexo\s+([a-z0-9]+(?:[-.][a-z0-9]+)*)\b", normalized)
    if annex_match:
        return f"ANEXO:{_canonical_annex_identifier(annex_match.group(1))}"

    if re.search(r"\bbases\s+de\s+contratacion\b", normalized):
        return "BASES_DE_CONTRATACION"
    if re.search(r"\bconvocatoria\b", normalized):
        return "CONVOCATORIA"
    if re.search(r"\bmodelo\s+de\s+contrato\b", normalized):
        return "MODELO_DE_CONTRATO"
    return None


def _clean_capture(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip(".,;: ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or None


def _extract_before_after(context: str, change_type: str) -> tuple[str | None, str | None]:
    normalized = _normalize_text(context)

    explicit = re.search(r"donde\s+dice\s*:?\s*(.+?)\s*debe\s+decir\s*:?\s*(.+)$", normalized)
    if explicit:
        return _clean_capture(explicit.group(1)), _clean_capture(explicit.group(2))

    if change_type in {CHANGE_MODIFIES, CHANGE_REPLACES, CHANGE_CORRECTS}:
        range_match = re.search(
            r"\bde\s+(\d[\w\s\-/,\.]{0,80}?)\s+a\s+([\w\d\s\-/,\.]{1,120}?)(?:[\.;]|$)",
            normalized,
        )
        if range_match:
            left = _clean_capture(range_match.group(1))
            right = _clean_capture(range_match.group(2))
            if left and right and re.search(r"\d", left):
                return left, right

    if change_type in {CHANGE_MODIFIES, CHANGE_REPLACES, CHANGE_ADDS, CHANGE_CORRECTS}:
        after_match = re.search(r"\b(?:a|por)\s+(.{2,160}?)(?:[\.;]|$)", normalized)
        if after_match:
            return None, _clean_capture(after_match.group(1))

    return None, None


def _relationship_target_from_reference_key(
    *,
    source_document_id: str,
    target_reference_key: str | None,
    alias_index: dict[str, set[str]],
) -> tuple[str | None, list[str]]:
    if target_reference_key is None:
        return None, []

    candidates = sorted(alias_index.get(target_reference_key, set()))
    candidates = [item for item in candidates if item != source_document_id]
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _source_priority(source: NormalizedContent) -> int:
    if source.source_type == "NATIVE_PDF":
        return 3
    if source.source_type == "OCR" and source.engine == "TESSERACT":
        return 2
    if source.source_type == "OCR" and source.engine == "PADDLEOCR":
        return 1
    return 0


def _document_alias_keys(document: TenderDocument, classification: DocumentClassification | None) -> set[str]:
    aliases: set[str] = set()
    filename_stem = os.path.splitext(document.original_filename)[0]
    slug = _normalize_text(filename_stem)

    if "bases de contratacion" in slug or ("bases" in slug and (classification is not None)):
        aliases.add("BASES_DE_CONTRATACION")

    if "convocatoria" in slug:
        aliases.add("CONVOCATORIA")

    if "modelo de contrato" in slug:
        aliases.add("MODELO_DE_CONTRATO")

    for match in re.findall(r"\banexo\s+([a-z0-9]+(?:[-.][a-z0-9]+)*)", slug):
        aliases.add(f"ANEXO:{_canonical_annex_identifier(match)}")

    return aliases


def _build_alias_index(db: Session, current_documents: list[TenderDocument]) -> dict[str, set[str]]:
    alias_index: dict[str, set[str]] = {}
    doc_ids = [item.id for item in current_documents]
    classifications_by_document_id: dict[str, DocumentClassification] = {}

    if doc_ids:
        stmt = select(DocumentClassification).where(DocumentClassification.document_id.in_(doc_ids)).order_by(DocumentClassification.created_at.desc())
        for row in db.execute(stmt).scalars().all():
            classifications_by_document_id.setdefault(row.document_id, row)

    for document in current_documents:
        aliases = _document_alias_keys(document, classifications_by_document_id.get(document.id))
        for alias in aliases:
            alias_index.setdefault(alias, set()).add(document.id)

    return alias_index


def _semantic_key(
    *,
    source_document_id: str,
    change_type: str,
    target_reference_key: str | None,
    target_document_id: str | None,
    target_locator_text: str | None,
    before_text: str | None,
    after_text: str | None,
    source_excerpt: str,
) -> str:
    payload = "|".join(
        [
            source_document_id,
            change_type,
            target_reference_key or "none",
            target_document_id or "none",
            _normalize_text(target_locator_text),
            _normalize_text(before_text),
            _normalize_text(after_text),
            _normalize_text(source_excerpt),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _detect_change_statement(context: str) -> _DetectedStatement | None:
    if _has_non_substantive_metadata_context(context):
        return None
    if _is_operational_instruction_context(context):
        return None

    change_type = _detect_change_type(context)
    if change_type == CHANGE_UNKNOWN:
        return None

    target_reference_key = _extract_target_reference_key(context)
    target_locator_text = _extract_locator_text(context)
    before_text, after_text = _extract_before_after(context, change_type)

    return _DetectedStatement(
        change_type=change_type,
        target_reference_key=target_reference_key,
        target_locator_text=target_locator_text,
        before_text=before_text,
        after_text=after_text,
        source_excerpt=_excerpt(context),
    )


def _gather_detected_changes(db: Session, tender_id: str) -> list[DetectedChange]:
    statement = (
        select(NormalizedContent, DocumentPage, TenderDocument)
        .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
        .join(TenderDocument, TenderDocument.id == DocumentPage.document_id)
        .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
        .order_by(TenderDocument.original_filename.asc(), DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
    )

    current_documents = (
        db.execute(
            select(TenderDocument)
            .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            .order_by(TenderDocument.original_filename.asc())
        )
        .scalars()
        .all()
    )
    alias_index = _build_alias_index(db, current_documents)

    detected_changes: list[DetectedChange] = []

    for normalized_content, page, document in db.execute(statement).all():
        text = (normalized_content.normalized_text or "").strip()
        if not text:
            continue

        for segment in _context_segments(text):
            detected_statement = _detect_change_statement(segment)
            if detected_statement is None:
                continue

            target_document_id, candidates = _relationship_target_from_reference_key(
                source_document_id=document.id,
                target_reference_key=detected_statement.target_reference_key,
                alias_index=alias_index,
            )

            semantic_key = _semantic_key(
                source_document_id=document.id,
                change_type=detected_statement.change_type,
                target_reference_key=detected_statement.target_reference_key,
                target_document_id=target_document_id,
                target_locator_text=detected_statement.target_locator_text,
                before_text=detected_statement.before_text,
                after_text=detected_statement.after_text,
                source_excerpt=detected_statement.source_excerpt,
            )

            candidate = DetectedChange(
                semantic_key=semantic_key,
                change_type=detected_statement.change_type,
                target_reference_key=detected_statement.target_reference_key,
                target_document_id=target_document_id,
                target_candidate_document_ids=candidates,
                target_locator_text=detected_statement.target_locator_text,
                before_text=detected_statement.before_text,
                after_text=detected_statement.after_text,
                source_document_id=document.id,
                source_page=page.page_number,
                source_excerpt=detected_statement.source_excerpt,
                evidence_fragments=[detected_statement.source_excerpt],
            )

            detected_changes.append(candidate)

    return detected_changes


def _effective_change_payload(change: TenderChange) -> dict[str, Any]:
    return {
        "change_type": change.human_change_type or change.change_type,
        "target_document_id": change.human_target_document_id or change.target_document_id,
        "target_locator_text": change.human_target_locator_text or change.target_locator_text,
        "before_text": change.human_before_text if change.human_before_text is not None else change.before_text,
        "after_text": change.human_after_text if change.human_after_text is not None else change.after_text,
    }


def _has_human_override(change: TenderChange) -> bool:
    return any(
        [
            change.human_change_type,
            change.human_target_document_id,
            change.human_target_locator_text,
            change.human_before_text is not None,
            change.human_after_text is not None,
            change.human_note,
        ]
    )


def _serialize_tender_change(change: TenderChange, docs_by_id: dict[str, TenderDocument], source_event_dates: dict[str, date]) -> dict[str, Any]:
    effective = _effective_change_payload(change)

    candidates = []
    for candidate_id in (change.target_candidate_document_ids or "").split(","):
        normalized_id = candidate_id.strip()
        if not normalized_id:
            continue
        candidate = docs_by_id.get(normalized_id)
        if not candidate:
            continue
        candidates.append(
            {
                "document_id": candidate.id,
                "original_filename": candidate.original_filename,
                "processing_status": candidate.processing_status,
            }
        )

    evidence = [
        {
            "id": item.id,
            "source_document_id": item.source_document_id,
            "source_filename": item.source_document.original_filename if item.source_document else None,
            "source_page": item.source_page,
            "source_excerpt": item.source_excerpt,
        }
        for item in sorted(change.evidence, key=lambda row: (row.source_document_id, row.source_page or 0, row.id))
    ]

    source_document = docs_by_id.get(change.source_document_id)
    target_document = docs_by_id.get(effective["target_document_id"]) if effective["target_document_id"] else None

    return {
        "id": change.id,
        "tender_id": change.tender_id,
        "semantic_key": change.semantic_key,
        "change_type": effective["change_type"],
        "target_reference_key": change.target_reference_key,
        "target_document_id": effective["target_document_id"],
        "target_filename": target_document.original_filename if target_document else None,
        "target_candidate_documents": candidates,
        "target_locator_text": effective["target_locator_text"],
        "before_text": effective["before_text"],
        "after_text": effective["after_text"],
        "source_document_id": change.source_document_id,
        "source_filename": source_document.original_filename if source_document else None,
        "source_page": change.source_page,
        "source_excerpt": change.source_excerpt,
        "source_event_date": source_event_dates.get(change.source_document_id),
        "review_status": change.review_status,
        "detection_origin": change.detection_origin,
        "detector_version": change.detector_version,
        "human_change_type": change.human_change_type,
        "human_target_document_id": change.human_target_document_id,
        "human_target_locator_text": change.human_target_locator_text,
        "human_before_text": change.human_before_text,
        "human_after_text": change.human_after_text,
        "human_note": change.human_note,
        "created_at": change.created_at,
        "updated_at": change.updated_at,
        "evidence": evidence,
    }


def list_tender_changes(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    rows = (
        db.execute(
            select(TenderChange)
            .where(TenderChange.tender_id == tender_id)
            .options(selectinload(TenderChange.source_document), selectinload(TenderChange.target_document), selectinload(TenderChange.evidence).selectinload(TenderChangeEvidence.source_document))
        )
        .scalars()
        .all()
    )

    docs = (
        db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True)))
        .scalars()
        .all()
    )
    docs_by_id = {doc.id: doc for doc in docs}

    source_event_dates: dict[str, date] = {}
    events = (
        db.execute(select(TenderEvent).where(TenderEvent.tender_id == tender_id, TenderEvent.event_date.is_not(None)).order_by(TenderEvent.event_date.asc()))
        .scalars()
        .all()
    )
    for event in events:
        if event.source_document_id and event.source_document_id not in source_event_dates:
            source_event_dates[event.source_document_id] = event.event_date

    rows.sort(
        key=lambda item: (
            source_event_dates.get(item.source_document_id) is None,
            source_event_dates.get(item.source_document_id) or date.max,
            docs_by_id[item.source_document_id].original_filename if item.source_document_id in docs_by_id else "",
            item.source_page or 0,
            item.id,
        )
    )

    status_counts = {
        REVIEW_SUGGESTED: 0,
        REVIEW_CONFIRMED: 0,
        REVIEW_REJECTED: 0,
    }
    semantic_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.review_status] = status_counts.get(row.review_status, 0) + 1
        semantic_counts[row.semantic_key] = semantic_counts.get(row.semantic_key, 0) + 1

    duplicate_semantic_count = sum(max(0, count - 1) for count in semantic_counts.values())

    return {
        "tender_id": tender_id,
        "changes_version": CHANGE_DETECTOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "counts": {
            "total_changes": len(rows),
            "suggested_changes": status_counts.get(REVIEW_SUGGESTED, 0),
            "confirmed_changes": status_counts.get(REVIEW_CONFIRMED, 0),
            "rejected_changes": status_counts.get(REVIEW_REJECTED, 0),
            "duplicate_semantic_count": duplicate_semantic_count,
        },
        "changes": [_serialize_tender_change(row, docs_by_id, source_event_dates) for row in rows],
    }


def _reconcile_modifies_relationships_from_changes(db: Session, tender_id: str) -> None:
    all_modifies = (
        db.execute(
            select(DocumentRelationship).where(
                DocumentRelationship.tender_id == tender_id,
                DocumentRelationship.relationship_type == RELATIONSHIP_MODIFIES,
            )
        )
        .scalars()
        .all()
    )

    change_modifies = [row for row in all_modifies if row.relationship_origin == RELATIONSHIP_ORIGIN_CHANGE_ENGINE]
    by_key_any_origin = {(row.source_document_id, row.target_document_id, row.relationship_type): row for row in all_modifies}

    changes = db.execute(select(TenderChange).where(TenderChange.tender_id == tender_id)).scalars().all()

    desired: set[tuple[str, str, str]] = set()
    for change in changes:
        effective = _effective_change_payload(change)
        effective_type = effective["change_type"]
        effective_target_document_id = effective["target_document_id"]

        if change.review_status != REVIEW_CONFIRMED:
            continue
        if effective_type not in AUTHORITATIVE_MODIFICATION_TYPES:
            continue
        if not effective_target_document_id:
            continue
        if effective_target_document_id == change.source_document_id:
            continue

        desired.add((change.source_document_id, effective_target_document_id, RELATIONSHIP_MODIFIES))

    for row in change_modifies:
        key = (row.source_document_id, row.target_document_id, row.relationship_type)
        if key not in desired:
            db.delete(row)

    for key in sorted(desired):
        if key in by_key_any_origin:
            continue
        row = DocumentRelationship(
            tender_id=tender_id,
            source_document_id=key[0],
            target_document_id=key[1],
            relationship_type=key[2],
            relationship_origin=RELATIONSHIP_ORIGIN_CHANGE_ENGINE,
        )
        db.add(row)


def analyze_tender_changes(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    detected = _gather_detected_changes(db, tender_id)
    grouped: dict[str, list[DetectedChange]] = {}
    for item in detected:
        grouped.setdefault(item.semantic_key, []).append(item)

    existing_rows = db.execute(select(TenderChange).where(TenderChange.tender_id == tender_id)).scalars().all()
    existing_by_key = {item.semantic_key: item for item in existing_rows}

    detected_keys = set(grouped.keys())
    for row in existing_rows:
        if row.detection_origin != ORIGIN_DETERMINISTIC:
            continue
        if row.review_status != REVIEW_SUGGESTED:
            continue
        if _has_human_override(row):
            continue
        if row.semantic_key not in detected_keys:
            db.delete(row)

    for semantic_key in sorted(grouped.keys()):
        samples = sorted(grouped[semantic_key], key=lambda item: (item.source_document_id, item.source_page or 0, item.source_excerpt))
        primary = samples[0]

        row = existing_by_key.get(semantic_key)
        if row is None:
            row = TenderChange(
                tender_id=tender_id,
                semantic_key=semantic_key,
                change_type=primary.change_type,
                target_reference_key=primary.target_reference_key,
                target_document_id=primary.target_document_id,
                target_candidate_document_ids=",".join(primary.target_candidate_document_ids),
                target_locator_text=primary.target_locator_text,
                before_text=primary.before_text,
                after_text=primary.after_text,
                source_document_id=primary.source_document_id,
                source_page=primary.source_page,
                source_excerpt=primary.source_excerpt,
                review_status=REVIEW_SUGGESTED,
                detection_origin=ORIGIN_DETERMINISTIC,
                detector_version=CHANGE_DETECTOR_VERSION,
            )
            db.add(row)
            db.flush()
            existing_by_key[semantic_key] = row
        elif row.review_status == REVIEW_SUGGESTED and not _has_human_override(row):
            row.change_type = primary.change_type
            row.target_reference_key = primary.target_reference_key
            row.target_document_id = primary.target_document_id
            row.target_candidate_document_ids = ",".join(primary.target_candidate_document_ids)
            row.target_locator_text = primary.target_locator_text
            row.before_text = primary.before_text
            row.after_text = primary.after_text
            row.source_document_id = primary.source_document_id
            row.source_page = primary.source_page
            row.source_excerpt = primary.source_excerpt
            row.detector_version = CHANGE_DETECTOR_VERSION
            row.detection_origin = ORIGIN_DETERMINISTIC

        existing_evidence = {(item.source_document_id, item.source_page, item.excerpt_sha256): item for item in row.evidence}
        expected_evidence_keys: set[tuple[str, int | None, str]] = set()

        for sample in samples:
            for fragment_text in sample.evidence_fragments or [sample.source_excerpt]:
                fragment = _excerpt(fragment_text)
                excerpt_sha = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
                evidence_key = (sample.source_document_id, sample.source_page, excerpt_sha)
                expected_evidence_keys.add(evidence_key)
                if evidence_key in existing_evidence:
                    continue
                db.add(
                    TenderChangeEvidence(
                        change=row,
                        source_document_id=sample.source_document_id,
                        source_page=sample.source_page,
                        source_excerpt=fragment,
                        excerpt_sha256=excerpt_sha,
                    )
                )

        if row.review_status == REVIEW_SUGGESTED and not _has_human_override(row):
            for key, evidence_row in existing_evidence.items():
                if key not in expected_evidence_keys:
                    db.delete(evidence_row)

    _reconcile_modifies_relationships_from_changes(db, tender_id)
    db.flush()
    return list_tender_changes(db, tender_id)


def update_tender_change_human_decision(
    db: Session,
    tender_id: str,
    change_id: str,
    action: str,
    *,
    change_type: str | None = None,
    target_document_id: str | None = None,
    target_locator_text: str | None = None,
    before_text: str | None = None,
    after_text: str | None = None,
    human_note: str | None = None,
) -> dict[str, Any]:
    row = db.get(TenderChange, change_id)
    if row is None or row.tender_id != tender_id:
        raise ValueError("Change not found")

    normalized_action = action.strip().upper()
    if normalized_action == ACTION_CONFIRM:
        row.review_status = REVIEW_CONFIRMED
    elif normalized_action == ACTION_REJECT:
        row.review_status = REVIEW_REJECTED
    elif normalized_action == ACTION_RESET:
        row.review_status = REVIEW_SUGGESTED
        row.human_change_type = None
        row.human_target_document_id = None
        row.human_target_locator_text = None
        row.human_before_text = None
        row.human_after_text = None
        row.human_note = None
    elif normalized_action == ACTION_OVERRIDE:
        row.review_status = REVIEW_CONFIRMED
        if change_type is not None:
            row.human_change_type = change_type.strip() or None
        if target_document_id is not None:
            if target_document_id.strip() == "":
                row.human_target_document_id = None
            else:
                target_doc = db.get(TenderDocument, target_document_id)
                if target_doc is None or target_doc.tender_id != tender_id or not target_doc.is_current:
                    raise ValueError("target_document_id must point to a current document in the same tender")
                if target_doc.id == row.source_document_id:
                    raise ValueError("target_document_id cannot be the same as source_document_id")
                row.human_target_document_id = target_doc.id
        if target_locator_text is not None:
            row.human_target_locator_text = target_locator_text.strip() or None
        if before_text is not None:
            row.human_before_text = before_text.strip() or None
        if after_text is not None:
            row.human_after_text = after_text.strip() or None
        if human_note is not None:
            row.human_note = human_note
    else:
        raise ValueError(f"Unsupported action: {action}")

    _reconcile_modifies_relationships_from_changes(db, tender_id)
    db.flush()
    return list_tender_changes(db, tender_id)
