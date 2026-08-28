from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentClassification,
    DocumentClassificationCandidate,
    DocumentClassificationEvidence,
    DocumentClassificationTag,
    DocumentPage,
    DocumentChunk,
    NormalizedContent,
    TenderDocument,
)

DOCUMENT_TYPE_RULES: dict[str, list[str]] = {
    "NOTICE": ["convocatoria", "aviso de convocatoria", "aviso de licitacion", "publicacion"],
    "BIDDING_RULES": ["bases de contratacion", "bases de contratación", "pliego de condiciones", "pliego de bases", "bases del proceso"],
    "CLARIFICATION": ["junta de aclaraciones", "aclaraciones", "preguntas y respuestas", "respuestas de aclaracion", "respuestas de aclaraciones"],
    "ADDENDUM_MODIFICATION": ["modificacion", "modificación", "adenda", "adicion", "reforma", "amendment"],
    "TECHNICAL_SPECIFICATION": ["especificaciones técnicas", "especificaciones tecnicas", "especificacion tecnica", "especificaciones particulares", "alcance tecnico"],
    "SCOPE_OF_WORK": ["alcance de los servicios", "alcance del trabajo", "alcance de la obra", "alcance de servicios", "alcance del servicio"],
    "EXECUTION_SCHEDULE": ["programa de ejecucion", "programa de ejecución", "cronograma", "programa general de ejecucion", "programa general de ejecución"],
    "PRICING_SCHEDULE_CATALOG": ["catalogo de conceptos", "catálogo de conceptos", "lista de partidas", "partidas economicas", "partidas económicas", "propuesta economica", "propuesta económica"],
    "QUALIFICATION_REQUIREMENTS": ["requisitos de calificacion", "requisitos de calificación", "experiencia", "perfil profesional", "personal profesional", "perfil tecnico"],
    "ADMINISTRATIVE_LEGAL_REQUIREMENTS": ["requisitos administrativos", "requisitos legales", "cumplimiento legal", "requisitos legales y administrativos"],
    "CONTRACT_DRAFT": ["modelo de contrato", "contrato modelo", "documento contractual", "formato de contrato"],
    "GENERAL_TERMS_CONDITIONS": ["condiciones generales", "terminos y condiciones", "términos y condiciones", "condiciones contractuales"],
    "GUARANTEE_BOND": ["fianza", "garantia", "garantía", "amparo financiero"],
    "FORM_TEMPLATE": ["formato", "modelo de formato", "anexo de formato", "formato de entrega"],
    "INSTRUCTION_GUIDE": ["instructivo", "guia de participacion", "guía de participación", "guia de presentacion", "guía de presentación"],
    "DOCUMENT_PACKAGE": ["paquete documental", "anexos de bases", "anexos de contratación", "documentos del paquete"],
}

CONTROLLED_TYPES = sorted(DOCUMENT_TYPE_RULES.keys())
VALID_HUMAN_TYPES = CONTROLLED_TYPES + ["UNKNOWN"]
CLASSIFIER_VERSION = "mvp-02.4.2"
ANCHOR_SIGNAL_SCORE = 35
ANCHOR_HEADING_BONUS = 10
ANCHOR_EARLY_PAGE_BONUS = 10
REFERENCE_SIGNAL_SCORE = 8
REFERENCE_LIST_SIGNAL_SCORE = 4
FILENAME_SIGNAL_SCORE = 12
MIN_DOC_SCORE = 35
COMPOSITE_MIN_ANCHORED_TYPES = 3
EARLY_PAGE_WINDOW = 3
MAX_HEADING_WORDS = 14

COMPOSITE_AUTONOMOUS_TYPES = {
    "TECHNICAL_SPECIFICATION",
    "SCOPE_OF_WORK",
    "EXECUTION_SCHEDULE",
    "PRICING_SCHEDULE_CATALOG",
    "QUALIFICATION_REQUIREMENTS",
    "ADMINISTRATIVE_LEGAL_REQUIREMENTS",
    "CONTRACT_DRAFT",
    "FORM_TEMPLATE",
}

REFERENCE_CUE_PATTERNS = [
    "de acuerdo con",
    "conforme a",
    "consulte",
    "se anexa",
    "se anexara",
    "se anexará",
    "se presentara",
    "se presentará",
    "debera presentar",
    "deberá presentar",
    "ver anexo",
    "incluye",
    "incluyen",
]

TOC_CUE_PATTERNS = [
    "indice",
    "índice",
    "contenido",
    "anexos",
    "tabla de contenido",
    "relacion de anexos",
    "relación de anexos",
]

CONTROLLED_FUNCTIONAL_TAGS = {
    "TECHNICAL",
    "COMMERCIAL",
    "ECONOMIC",
    "ADMINISTRATIVE",
    "LEGAL",
    "CONTRACTUAL",
    "SCHEDULE",
    "EXPERIENCE",
    "PERSONNEL",
    "SAFETY",
    "GUARANTEE",
    "REGISTRATION",
    "INSTRUCTIONS",
}

FUNCTIONAL_TAG_SIGNAL_RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("programa de ejecucion", "programa de ejecución", "programa general de ejecucion", "programa general de ejecución", "cronograma"), ("SCHEDULE",)),
    (("experiencia",), ("EXPERIENCE",)),
    (("personal profesional", "perfil profesional", "perfil tecnico", "perfil técnico"), ("PERSONNEL",)),
    (("fianza", "garantia", "garantía", "amparo financiero"), ("GUARANTEE",)),
    (("especificaciones tecnicas", "especificaciones técnicas", "especificacion tecnica", "especificación técnica", "alcance tecnico", "alcance técnico", "alcance del trabajo", "alcance de los servicios", "alcance de servicios", "alcance del servicio", "alcance de la obra"), ("TECHNICAL",)),
    (("propuesta economica", "propuesta económica"), ("ECONOMIC",)),
    (("catalogo de conceptos", "catálogo de conceptos", "lista de partidas", "partidas economicas", "partidas económicas"), ("ECONOMIC", "COMMERCIAL")),
    (("modelo de contrato", "contrato modelo", "documento contractual", "formato de contrato", "condiciones generales", "terminos y condiciones", "términos y condiciones", "condiciones contractuales"), ("CONTRACTUAL",)),
    (("requisitos administrativos",), ("ADMINISTRATIVE",)),
    (("requisitos legales", "cumplimiento legal"), ("LEGAL",)),
    (("requisitos legales y administrativos",), ("LEGAL", "ADMINISTRATIVE")),
    (("instructivo", "guia de participacion", "guía de participación", "guia de presentacion", "guía de presentación", "formato", "modelo de formato", "anexo de formato", "formato de entrega"), ("INSTRUCTIONS",)),
    (("sspa", "seguridad", "hse", "seguridad industrial"), ("SAFETY",)),
]

REGISTRATION_SIGNAL_CUES = (
    "registro",
    "inscripcion",
    "inscripción",
    "usuario",
    "acceso",
)


@dataclass
class _SignalOccurrence:
    document_type: str
    signal: str
    page_number: int
    document_page_id: str | None
    normalized_content_id: str | None
    excerpt: str
    source_kind: str
    weight: int


def _serialize_classification(document: TenderDocument, classification: DocumentClassification) -> dict[str, Any]:
    every_evidence = [
        {
            "document_page_id": item.document_page_id,
            "normalized_content_id": item.normalized_content_id,
            "document_chunk_id": item.document_chunk_id,
            "source_kind": item.source_kind,
            "signal": item.signal,
            "excerpt": item.excerpt,
            "weight_or_score": item.weight_or_score,
        }
        for item in classification.evidence
    ]
    candidate_scores = [
        {"type": item.candidate_type, "score": item.score}
        for item in sorted(classification.candidates, key=lambda row: row.score, reverse=True)
        if item.score > 0
    ]
    tags = [
        {"tag": item.tag, "score": item.score}
        for item in sorted(classification.tags, key=lambda row: row.score, reverse=True)
        if item.tag in CONTROLLED_FUNCTIONAL_TAGS and item.score > 0
    ]
    effective_type = classification.human_type or classification.suggested_type
    return {
        "document_id": document.id,
        "suggested_type": classification.suggested_type,
        "suggested_score": classification.suggested_score,
        "effective_type": effective_type,
        "classification_status": classification.classification_status,
        "is_composite": classification.is_composite,
        "human_type": classification.human_type,
        "human_note": classification.human_note,
        "candidate_scores": candidate_scores,
        "functional_tags": tags,
        "evidence": every_evidence,
        "input_fingerprint_sha256": classification.input_fingerprint_sha256,
        "not_ready": False,
    }


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.lower()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _match_type_text(text: str) -> dict[str, tuple[str, int]]:
    normalized = _normalize_text(text)
    matches: dict[str, tuple[str, int]] = {}
    for document_type, patterns in DOCUMENT_TYPE_RULES.items():
        for pattern in patterns:
            if pattern in normalized:
                matches[document_type] = (pattern, ANCHOR_SIGNAL_SCORE)
                break
    return matches


def _filename_signal(filename: str) -> dict[str, int]:
    clean_name = _normalize_text(filename)
    results: dict[str, int] = {}
    for document_type, patterns in DOCUMENT_TYPE_RULES.items():
        for pattern in patterns:
            if pattern in clean_name:
                results[document_type] = FILENAME_SIGNAL_SCORE
                break
    return results


def _snippet_from_text(text: str, phrase: str, limit: int = 140) -> str:
    lowered = _normalize_text(text)
    phrase_normalized = _normalize_text(phrase)
    index = lowered.find(phrase_normalized)
    if index < 0:
        return text[:limit].strip()
    start = max(0, index - 40)
    end = min(len(text), index + len(phrase_normalized) + 40)
    snippet = text[start:end].replace("\n", " ").strip()
    if len(snippet) > limit:
        snippet = snippet[:limit].rstrip()
    return snippet


def _split_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines and text.strip():
        lines = [text.strip()]
    return lines


def _line_word_count(text: str) -> int:
    return len([word for word in re.split(r"\s+", text.strip()) if word])


def _is_uppercase_title_like(raw_line: str) -> bool:
    letters = [char for char in raw_line if char.isalpha()]
    if not letters:
        return False
    uppercase = sum(1 for char in letters if char.isupper())
    return (uppercase / len(letters)) >= 0.6


def _is_reference_list_source(text: str, lines: list[str]) -> bool:
    normalized_text = _normalize_text(text)
    has_toc_cue = any(cue in normalized_text for cue in TOC_CUE_PATTERNS)
    list_like_lines = 0
    for line in lines:
        normalized_line = _normalize_text(line)
        if re.match(r"^(anexo|anexos|apendice|apéndice|seccion|sección|[0-9]+[\.)]|[ivxlcdm]+\.)", normalized_line):
            list_like_lines += 1
            continue
        if " - " in line or " : " in line or "..." in line:
            list_like_lines += 1
    return has_toc_cue and list_like_lines >= 3


def _is_reference_context(line_text: str, signal: str) -> bool:
    normalized = _normalize_text(line_text)
    if any(cue in normalized for cue in REFERENCE_CUE_PATTERNS):
        return True
    signal_index = normalized.find(signal)
    if signal_index > 0:
        prefix = normalized[:signal_index].strip()
        if prefix and _line_word_count(prefix) >= 2:
            return True
    return False


def _is_heading_like_occurrence(
    raw_line: str,
    normalized_line: str,
    signal: str,
    page_number: int,
    line_index: int,
) -> bool:
    words = _line_word_count(raw_line)
    if words == 0 or words > MAX_HEADING_WORDS:
        return False
    early_line = line_index <= 2
    early_page = page_number <= EARLY_PAGE_WINDOW
    starts_with_signal = normalized_line.startswith(signal)
    standalone_signal = normalized_line == signal
    uppercase_title = _is_uppercase_title_like(raw_line)
    tight_line = len(normalized_line) <= len(signal) + 35
    return (starts_with_signal or standalone_signal or uppercase_title or tight_line) and (early_line or early_page or uppercase_title)


def _best_occurrence(current: _SignalOccurrence | None, candidate: _SignalOccurrence) -> _SignalOccurrence:
    if current is None:
        return candidate
    rank = {"ANCHOR": 3, "REFERENCE": 2, "REFERENCE_LIST": 1}
    current_rank = rank.get(current.source_kind, 0)
    candidate_rank = rank.get(candidate.source_kind, 0)
    if candidate_rank > current_rank:
        return candidate
    if candidate_rank < current_rank:
        return current
    if candidate.weight > current.weight:
        return candidate
    if candidate.weight < current.weight:
        return current
    if candidate.page_number < current.page_number:
        return candidate
    return current


def _extract_signal_occurrences(normalized_sources: list[NormalizedContent]) -> dict[tuple[str, str], _SignalOccurrence]:
    best_occurrences: dict[tuple[str, str], _SignalOccurrence] = {}
    for source in normalized_sources:
        text = source.normalized_text or ""
        lines = _split_lines(text)
        reference_list_source = _is_reference_list_source(text, lines)
        page_number = source.document_page.page_number if source.document_page is not None else 999999

        for line_index, raw_line in enumerate(lines):
            normalized_line = _normalize_text(raw_line)
            if not normalized_line:
                continue
            line_matches = _match_type_text(raw_line)
            for document_type, match in line_matches.items():
                signal, _ = match
                source_kind = "REFERENCE"
                weight = REFERENCE_SIGNAL_SCORE

                if reference_list_source:
                    source_kind = "REFERENCE_LIST"
                    weight = REFERENCE_LIST_SIGNAL_SCORE
                elif _is_heading_like_occurrence(raw_line, normalized_line, signal, page_number, line_index) and not _is_reference_context(raw_line, signal):
                    source_kind = "ANCHOR"
                    weight = ANCHOR_SIGNAL_SCORE
                    if _line_word_count(raw_line) <= 8:
                        weight += ANCHOR_HEADING_BONUS
                    if page_number <= EARLY_PAGE_WINDOW:
                        weight += ANCHOR_EARLY_PAGE_BONUS

                occurrence = _SignalOccurrence(
                    document_type=document_type,
                    signal=signal,
                    page_number=page_number,
                    document_page_id=source.document_page_id,
                    normalized_content_id=source.id,
                    excerpt=_snippet_from_text(raw_line, signal),
                    source_kind=source_kind,
                    weight=weight,
                )
                dedupe_key = (document_type, signal)
                best_occurrences[dedupe_key] = _best_occurrence(best_occurrences.get(dedupe_key), occurrence)
    return best_occurrences


def _effective_type(classification: DocumentClassification | None) -> str:
    if classification is None:
        return "UNKNOWN"
    return classification.human_type or classification.suggested_type


def _candidate_score_rows(scores: dict[str, int]) -> list[dict[str, int | str]]:
    return [
        {"type": document_type, "score": score}
        for document_type, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if document_type != "UNKNOWN" and score > 0
    ]


def _functional_signal_tags(signal: str, excerpt: str) -> set[str]:
    combined_text = f"{signal} {excerpt}".strip()
    tags: set[str] = set()
    for patterns, mapped_tags in FUNCTIONAL_TAG_SIGNAL_RULES:
        if any(pattern in combined_text for pattern in patterns):
            tags.update(mapped_tags)
    if any(cue in combined_text for cue in REGISTRATION_SIGNAL_CUES):
        tags.add("REGISTRATION")
    return {tag for tag in tags if tag in CONTROLLED_FUNCTIONAL_TAGS}


def _functional_tag_scale(source_kind: str) -> float:
    if source_kind == "ANCHOR":
        return 1.0
    if source_kind == "REFERENCE":
        return 0.5
    if source_kind == "REFERENCE_LIST":
        return 0.25
    if source_kind == "CONTENT":
        return 0.5
    return 0.0


def _functional_tag_scores_from_evidence(evidence_entries: list[dict[str, Any]]) -> dict[str, int]:
    unique_signal_weights: dict[tuple[str, str], int] = {}
    for evidence in evidence_entries:
        source_kind = str(evidence.get("source_kind") or "")
        if source_kind == "FILENAME":
            continue
        normalized_signal = _normalize_text(str(evidence.get("signal") or ""))
        normalized_excerpt = _normalize_text(str(evidence.get("excerpt") or ""))
        mapped_tags = _functional_signal_tags(normalized_signal, normalized_excerpt)
        if not mapped_tags:
            continue
        raw_weight = int(evidence.get("weight_or_score") or 0)
        scaled_weight = int(round(raw_weight * _functional_tag_scale(source_kind)))
        if scaled_weight <= 0:
            continue
        for tag in mapped_tags:
            key = (tag, normalized_signal)
            previous = unique_signal_weights.get(key, 0)
            if scaled_weight > previous:
                unique_signal_weights[key] = scaled_weight

    totals: dict[str, int] = {}
    for (tag, _), score in unique_signal_weights.items():
        totals[tag] = totals.get(tag, 0) + score
    return totals


def _has_semantic_functional_tags(classification: DocumentClassification, expected_scores: dict[str, int]) -> bool:
    if any(tag.tag not in CONTROLLED_FUNCTIONAL_TAGS for tag in classification.tags):
        return False
    current = {tag.tag: int(tag.score) for tag in classification.tags}
    return current == expected_scores


def _has_semantic_candidate_scores(classification: DocumentClassification, expected_scores: list[dict[str, int | str]]) -> bool:
    current = {candidate.candidate_type: int(candidate.score) for candidate in classification.candidates}
    expected = {str(item["type"]): int(item["score"]) for item in expected_scores}
    return current == expected


def _classification_row_query(db: Session, document_id: str) -> DocumentClassification | None:
    return db.execute(
        select(DocumentClassification)
        .options(
            selectinload(DocumentClassification.evidence),
            selectinload(DocumentClassification.candidates),
            selectinload(DocumentClassification.tags),
        )
        .where(DocumentClassification.document_id == document_id)
    ).scalar_one_or_none()


def _page_source_variants_for_document(db: Session, document_id: str) -> list[NormalizedContent]:
    return db.execute(
        select(NormalizedContent)
        .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
        .options(selectinload(NormalizedContent.document_page), selectinload(NormalizedContent.page_ocr_result), selectinload(NormalizedContent.region))
    ).scalars().all()


def _build_input_fingerprint(normalized_sources: list[NormalizedContent]) -> str:
    assembled = "\n".join(
        f"{source.document_page_id}|{source.source_scope}|{source.region_id or 'none'}|{source.engine or 'none'}|{source.normalized_text}"
        for source in normalized_sources
    )
    return _sha256(assembled)


def _score_document(document: TenderDocument, normalized_sources: list[NormalizedContent]) -> tuple[str, int, bool, dict[str, int], list[dict[str, Any]], dict[str, Any]]:
    scores: dict[str, int] = {doc_type: 0 for doc_type in CONTROLLED_TYPES}
    scores["UNKNOWN"] = 0
    evidence: list[dict[str, Any]] = []

    filename_scores = _filename_signal(document.original_filename)
    for document_type, weight in filename_scores.items():
        scores[document_type] += weight
        evidence.append(
            {
                "source_kind": "FILENAME",
                "signal": document_type,
                "excerpt": document.original_filename,
                "weight_or_score": weight,
                "document_page_id": None,
                "normalized_content_id": None,
                "document_chunk_id": None,
            }
        )

    occurrences = _extract_signal_occurrences(normalized_sources)
    anchored_type_to_pages: dict[str, set[int]] = {}
    anchored_type_scores: dict[str, int] = {}

    for occurrence in occurrences.values():
        scores[occurrence.document_type] += occurrence.weight
        evidence.append(
            {
                "source_kind": occurrence.source_kind,
                "signal": occurrence.signal,
                "excerpt": occurrence.excerpt,
                "weight_or_score": occurrence.weight,
                "document_page_id": occurrence.document_page_id,
                "normalized_content_id": occurrence.normalized_content_id,
                "document_chunk_id": None,
            }
        )
        if occurrence.source_kind == "ANCHOR":
            anchored_type_to_pages.setdefault(occurrence.document_type, set()).add(occurrence.page_number)
            anchored_type_scores[occurrence.document_type] = anchored_type_scores.get(occurrence.document_type, 0) + occurrence.weight

    if not any(score > 0 for score in scores.values()):
        return "UNKNOWN", 0, False, scores, evidence, {"UNKNOWN": 0}

    strong_types = {doc_type: score for doc_type, score in scores.items() if score >= MIN_DOC_SCORE and doc_type != "DOCUMENT_PACKAGE"}
    strongest_document_type = max(strong_types.items(), key=lambda item: item[1])[0] if strong_types else "UNKNOWN"
    strongest_score = scores.get(strongest_document_type, 0)

    composite = False
    anchored_types = [doc_type for doc_type, pages in anchored_type_to_pages.items() if pages and anchored_type_scores.get(doc_type, 0) >= MIN_DOC_SCORE]
    anchored_types_sorted = sorted(anchored_types, key=lambda doc_type: anchored_type_scores.get(doc_type, 0), reverse=True)
    autonomous_types_sorted = [doc_type for doc_type in anchored_types_sorted if doc_type in COMPOSITE_AUTONOMOUS_TYPES]
    if len(autonomous_types_sorted) >= COMPOSITE_MIN_ANCHORED_TYPES:
        composite = True

    if strongest_score < MIN_DOC_SCORE:
        strongest_document_type = "UNKNOWN"
        strongest_score = 0

    if composite:
        strongest_document_type = "DOCUMENT_PACKAGE"
        strongest_score = sum(anchored_type_scores[doc_type] for doc_type in autonomous_types_sorted)

    return strongest_document_type, strongest_score, composite, scores, evidence, {
        "strong_types": len(strong_types),
        "anchored_types": len(anchored_types_sorted),
        "autonomous_anchored_types": len(autonomous_types_sorted),
    }


def process_document_classification(db: Session, document: TenderDocument) -> dict[str, Any]:
    normalized_sources = _page_source_variants_for_document(db, document.id)
    if not normalized_sources:
        return {
            "document_id": document.id,
            "suggested_type": "UNKNOWN",
            "suggested_score": 0,
            "effective_type": "UNKNOWN",
            "classification_status": "NEEDS_REVIEW",
            "is_composite": False,
            "human_type": None,
            "human_note": None,
            "candidate_scores": [],
            "functional_tags": [],
            "evidence": [],
            "input_fingerprint_sha256": "",
            "not_ready": True,
        }

    suggested_type, suggested_score, is_composite, scores, evidence_entries, _ = _score_document(document, normalized_sources)
    candidate_scores = _candidate_score_rows(scores)
    functional_tag_scores = _functional_tag_scores_from_evidence(evidence_entries)
    input_fingerprint = _build_input_fingerprint(normalized_sources)

    existing = _classification_row_query(db, document.id)
    has_materialized_evidence = bool(existing and existing.evidence)
    has_materialized_candidates = bool(existing and _has_semantic_candidate_scores(existing, candidate_scores))
    has_materialized_tags = bool(existing and _has_semantic_functional_tags(existing, functional_tag_scores))
    if (
        existing is not None
        and existing.classifier_version == CLASSIFIER_VERSION
        and existing.input_fingerprint_sha256 == input_fingerprint
        and has_materialized_evidence
        and has_materialized_candidates
        and has_materialized_tags
    ):
        return _serialize_classification(document, existing)

    preserve_human = existing is not None and (existing.human_type is not None or existing.human_note is not None or existing.classification_status in {"NEEDS_REVIEW", "CONFIRMED", "OVERRIDDEN"})
    if existing is not None and existing.human_type is not None:
        effective_type = existing.human_type
        classification_status = "OVERRIDDEN" if existing.human_type and existing.human_type != existing.suggested_type else "CONFIRMED"
    elif preserve_human and existing is not None and existing.human_note is not None:
        effective_type = existing.human_type or suggested_type
        classification_status = "NEEDS_REVIEW"
    else:
        effective_type = suggested_type
        classification_status = "SUGGESTED" if suggested_type != "UNKNOWN" and suggested_score >= MIN_DOC_SCORE else "NEEDS_REVIEW"

    if existing is None:
        existing = DocumentClassification(
            document_id=document.id,
            suggested_type=suggested_type,
            suggested_score=suggested_score,
            classification_status=classification_status,
            classifier_method="RULE_BASED_GENERIC",
            classifier_version=CLASSIFIER_VERSION,
            input_fingerprint_sha256=input_fingerprint,
            is_composite=is_composite,
        )
        db.add(existing)
        db.flush()
    else:
        existing.suggested_type = suggested_type
        existing.suggested_score = suggested_score
        existing.classification_status = classification_status
        existing.classifier_method = "RULE_BASED_GENERIC"
        existing.classifier_version = CLASSIFIER_VERSION
        existing.input_fingerprint_sha256 = input_fingerprint
        existing.is_composite = is_composite
        if existing.human_type is None:
            existing.human_type = None
        existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    if existing.evidence:
        for entry in list(existing.evidence):
            db.delete(entry)
    if existing.tags:
        for tag in list(existing.tags):
            db.delete(tag)
    if existing.candidates:
        for candidate in list(existing.candidates):
            db.delete(candidate)
    db.flush()

    seen_evidence_signals: set[tuple[str, str | None, str | None, str | None, str]] = set()
    for evidence in evidence_entries:
        evidence_key = (
            existing.id,
            evidence["document_page_id"],
            evidence["normalized_content_id"],
            evidence["document_chunk_id"],
            evidence["signal"],
        )
        if evidence_key in seen_evidence_signals:
            continue
        seen_evidence_signals.add(evidence_key)
        db.add(
            DocumentClassificationEvidence(
                classification_id=existing.id,
                document_page_id=evidence["document_page_id"],
                normalized_content_id=evidence["normalized_content_id"],
                document_chunk_id=evidence["document_chunk_id"],
                source_kind=evidence["source_kind"],
                signal=evidence["signal"],
                excerpt=evidence["excerpt"],
                weight_or_score=evidence["weight_or_score"],
            )
        )

    for candidate in candidate_scores:
        db.add(
            DocumentClassificationCandidate(
                classification_id=existing.id,
                candidate_type=str(candidate["type"]),
                score=int(candidate["score"]),
            )
        )

    for tag_name, tag_score in sorted(functional_tag_scores.items(), key=lambda item: item[1], reverse=True):
        db.add(
            DocumentClassificationTag(
                classification_id=existing.id,
                tag=tag_name,
                score=tag_score,
            )
        )

    db.flush()
    if existing.human_type is not None:
        effective_type = existing.human_type
        classification_status = "OVERRIDDEN" if existing.human_type != existing.suggested_type else "CONFIRMED"
    elif existing.human_note is not None:
        effective_type = existing.human_type or suggested_type
        classification_status = "NEEDS_REVIEW"
    else:
        effective_type = suggested_type
        classification_status = "SUGGESTED" if suggested_type != "UNKNOWN" and suggested_score >= MIN_DOC_SCORE else "NEEDS_REVIEW"

    return {
        "document_id": document.id,
        "suggested_type": suggested_type,
        "suggested_score": suggested_score,
        "effective_type": effective_type,
        "classification_status": classification_status,
        "is_composite": is_composite,
        "human_type": existing.human_type,
        "human_note": existing.human_note,
        "candidate_scores": candidate_scores,
        "functional_tags": [{"tag": tag_name, "score": tag_score} for tag_name, tag_score in sorted(functional_tag_scores.items(), key=lambda item: item[1], reverse=True)],
        "evidence": [
            {
                "document_page_id": evidence["document_page_id"],
                "normalized_content_id": evidence["normalized_content_id"],
                "source_kind": evidence["source_kind"],
                "signal": evidence["signal"],
                "excerpt": evidence["excerpt"],
                "weight_or_score": evidence["weight_or_score"],
            }
            for evidence in evidence_entries
        ],
        "input_fingerprint_sha256": input_fingerprint,
        "not_ready": False,
    }


def get_document_classification(db: Session, document_id: str) -> dict[str, Any]:
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise ValueError("Document not found")
    classification = _classification_row_query(db, document_id)
    if classification is None:
        processed = process_document_classification(db, document)
        db.flush()
        return processed
    return _serialize_classification(document, classification)


def apply_human_classification_decision(db: Session, document: TenderDocument, action: str, human_type: str | None, human_note: str | None) -> dict[str, Any]:
    existing = _classification_row_query(db, document.id)
    if existing is None:
        processed = process_document_classification(db, document)
        existing = _classification_row_query(db, document.id)
        if existing is None:
            raise ValueError("Document classification was not generated")

    if action == "CONFIRM":
        if human_type is not None:
            existing.human_type = human_type if human_type in VALID_HUMAN_TYPES else None
        else:
            existing.human_type = existing.suggested_type
        existing.human_note = human_note
        existing.classification_status = "CONFIRMED"
    elif action == "OVERRIDE":
        if human_type is None or human_type not in VALID_HUMAN_TYPES:
            raise ValueError("A valid controlled human_type is required for override")
        existing.human_type = human_type
        existing.human_note = human_note
        existing.classification_status = "OVERRIDDEN"
    elif action == "MARK_FOR_REVIEW":
        existing.human_type = None
        existing.human_note = human_note
        existing.classification_status = "NEEDS_REVIEW"
    else:
        raise ValueError(f"Unsupported human decision: {action}")

    db.flush()
    return get_document_classification(db, document.id)
