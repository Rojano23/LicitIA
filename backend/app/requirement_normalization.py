from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Requirement, RequirementCandidate, RequirementCandidateLink, Tender

REQUIREMENT_NORMALIZER_VERSION = "mvp-04.3"

STATUS_NORMALIZED = "NORMALIZED"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

CATEGORY_ADMINISTRATIVE = "ADMINISTRATIVE"
CATEGORY_LEGAL = "LEGAL"
CATEGORY_TECHNICAL = "TECHNICAL"
CATEGORY_COMMERCIAL = "COMMERCIAL"
CATEGORY_ECONOMIC = "ECONOMIC"
CATEGORY_EXPERIENCE = "EXPERIENCE"
CATEGORY_PERSONNEL = "PERSONNEL"
CATEGORY_SAFETY = "SAFETY"
CATEGORY_GUARANTEE = "GUARANTEE"
CATEGORY_REGISTRATION = "REGISTRATION"
CATEGORY_INSTRUCTIONS = "INSTRUCTIONS"
CATEGORY_OTHER = "OTHER"
CATEGORY_UNKNOWN = "UNKNOWN"

REVIEW_REJECTED = "REJECTED"
ORIGIN_DETERMINISTIC = "DETERMINISTIC"

SCOPE_NOTE = "Requisitos normalizados a partir de los documentos actualmente procesados."

ANNEX_RE = re.compile(r"\banexo\s+([a-z0-9][a-z0-9\.-]*)\b", re.IGNORECASE)
CONSORTIUM_RE = re.compile(r"\b(consorcio|integrantes?\s+del\s+consorcio|propuesta\s+conjunta|cada\s+integrante)\b", re.IGNORECASE)
PARTICIPANT_RE = re.compile(r"\b(participante|licitante|oferente|interesado|propuesta|proposicion|oferta)\b", re.IGNORECASE)
OCR_NOISE_RE = re.compile(r"\b[a-zA-Z]\b")
TRUNCATED_END_RE = re.compile(r"[\|:;,-]\s*$")
REFERENT_RE = re.compile(
    r"\b(dicha\s+documentacion|dicha\s+documentación|el\s+presente\s+documento|los\s+documentos\s+antes\s+mencionados|lo\s+anterior|los\s+mismos|antes\s+mencionad[oa]s?)\b",
    re.IGNORECASE,
)
PROCEDURAL_EVENT_RE = re.compile(
    r"presentacion\s+y\s+apertura\s+de\s+propuestas\s+comercial,?\s+tecnica\s+y\s+economica",
    re.IGNORECASE,
)
TERMINAL_CONNECTOR_RE = re.compile(r"\b(el\s+cual|la\s+cual|que|y|o|para)\.?\s*$", re.IGNORECASE)
MALFORMED_CHAR_RE = re.compile(r"[\|¢�]")

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    CATEGORY_PERSONNEL: (
        "curriculum",
        "cedula",
        "cédula",
        "personal",
        "profesional",
        "profesionista",
        "tecnico",
        "técnico",
        "titulo",
        "certificacion",
        "certificación",
    ),
    CATEGORY_EXPERIENCE: (
        "experiencia",
        "servicios",
        "contratos",
        "trabajos",
        "ejecutados",
        "similares",
        "años",
        "anos",
    ),
    CATEGORY_ECONOMIC: (
        "propuesta economica",
        "propuesta económica",
        "precio",
        "precios",
        "porcentaje ofertado",
        "unitarios",
        "importe",
    ),
    CATEGORY_COMMERCIAL: (
        "propuesta comercial",
        "condiciones comerciales",
        "terminos y condiciones",
        "términos y condiciones",
    ),
    CATEGORY_REGISTRATION: (
        "registro",
        "hiip",
        "constancia fiscal",
        "seguridad social",
        "sat",
        "certificado de registro",
        "plataforma",
        "siscep",
    ),
    CATEGORY_GUARANTEE: (
        "garantia",
        "garantía",
        "fianza",
        "bond",
        "garantias",
        "garantías",
    ),
    CATEGORY_SAFETY: (
        "sspa",
        "seguridad industrial",
        "hse",
        "safety",
        "salud ocupacional",
    ),
    CATEGORY_LEGAL: (
        "poder notarial",
        "representante legal",
        "persona moral",
        "declaro bajo protesta",
        "manifestacion",
        "manifestación",
        "inhabilitado",
    ),
    CATEGORY_TECHNICAL: (
        "iso",
        "9001",
        "fabricante",
        "refaccionamiento",
        "especificacion",
        "especificación",
        "documentacion tecnica",
        "documentación técnica",
        "capacidad tecnica",
        "capacidad técnica",
        "sistema de control",
        "certificado de calidad",
    ),
    CATEGORY_INSTRUCTIONS: (
        "idioma",
        "firmada",
        "firmado",
        "formato",
        "pdf",
        "zip",
        "integrar",
        "presentar",
        "editable",
        "seccion",
        "sección",
    ),
    CATEGORY_ADMINISTRATIVE: (
        "area contratante",
        "área contratante",
        "solicitudes de aclaracion",
        "solicitudes de aclaración",
        "bases de contratacion",
        "bases de contratación",
        "procedimiento de contratacion",
        "procedimiento de contratación",
    ),
}

MERGE_CONFLICT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("iso", "9001"),
    ("respaldo", "fabricante"),
    ("curriculum", "cedula", "cédula"),
    ("experiencia", "servicios", "contratos", "trabajos"),
    ("constancia", "fiscal", "seguridad", "social"),
)

STOPWORDS = {
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "y",
    "o",
    "a",
    "en",
    "por",
    "para",
    "con",
    "que",
    "se",
    "su",
    "sus",
    "al",
    "un",
    "una",
    "como",
    "debera",
    "deberá",
    "deberan",
    "deberán",
    "presentar",
    "integrar",
    "anexar",
    "incluir",
}


@dataclass(frozen=True)
class CandidateView:
    id: str
    requirement_text: str
    actor_text: str | None
    modality_text: str | None
    source_document_id: str
    source_filename: str | None
    source_page: int | None
    source_excerpt: str
    document_page_id: str | None
    normalized_content_id: str | None


@dataclass(frozen=True)
class CandidateSignals:
    normalized_text: str
    token_set: frozenset[str]
    content_token_set: frozenset[str]
    numeric_tokens: tuple[str, ...]
    qualifier_tokens: tuple[str, ...]
    annex_key: str | None
    actor_scope: str
    has_ocr_noise: bool
    is_truncated: bool
    is_context_dependent: bool
    malformed_char_count: int
    starts_like_clipped_continuation: bool
    ends_with_open_connector: bool


@dataclass
class RequirementDraft:
    candidates: list[CandidateView]
    category: str
    normalization_status: str
    normalization_confidence: float
    normalization_reason: str
    primary_candidate_id: str
    canonical_text: str
    canonical_key: str


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_space(value: str) -> str:
    return " ".join((value or "").replace("\r", "\n").split())


def _normalize_for_key(value: str) -> str:
    return _strip_accents(_normalize_space(value).lower())


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9áéíóúñ]+", value.lower())


def _candidate_signals(candidate: CandidateView) -> CandidateSignals:
    raw_text = candidate.requirement_text or ""
    normalized_text = _normalize_for_key(raw_text)
    token_set = frozenset(_tokenize(normalized_text))
    content_token_set = frozenset(token for token in token_set if token not in STOPWORDS and len(token) > 2)
    numeric_tokens = tuple(sorted(re.findall(r"\d+(?:[\.,]\d+)?%?", normalized_text)))
    qualifier_tokens = tuple(sorted(set(re.findall(r"\b(vigente|original|certificada|simple|editable|firmada|firmado)\b", normalized_text))))
    annex_match = ANNEX_RE.search(raw_text)
    annex_key = _normalize_for_key(annex_match.group(1)) if annex_match else None
    has_consorcio = bool(CONSORTIUM_RE.search(raw_text) or CONSORTIUM_RE.search(candidate.actor_text or ""))
    has_participant = bool(PARTICIPANT_RE.search(raw_text) or PARTICIPANT_RE.search(candidate.actor_text or ""))
    actor_scope = "CONSORTIUM" if has_consorcio else "PARTICIPANT" if has_participant else "UNKNOWN"
    prefix = raw_text[:42]
    has_ocr_noise = bool(prefix.startswith(("|", "✓", "we ", "n ", "y ", "v ")) or len(OCR_NOISE_RE.findall(prefix)) >= 6)
    is_truncated = bool(TRUNCATED_END_RE.search(raw_text) or len(raw_text) < 60 and raw_text[-1:] not in {".", ":"})
    malformed_char_count = len(MALFORMED_CHAR_RE.findall(raw_text))

    referent = REFERENT_RE.search(normalized_text)
    is_context_dependent = False
    if referent:
        referent_start = referent.start()
        prefix_text = normalized_text[:referent_start]
        has_local_antecedent = bool(
            re.search(
                r"\b(anexo\s+[a-z0-9\.-]+|formato\s+[a-z0-9\.-]+|documento\s+[a-z0-9\.-]+|certificado|constancia|carta|convenio|seccion\s+[a-z0-9\.-]+|seccion\s+[ivxlcdm0-9\.-]+)\b",
                prefix_text,
                re.IGNORECASE,
            )
        )
        is_context_dependent = not has_local_antecedent

    first_token_match = re.match(r"^([a-záéíóúñ]+)", normalized_text)
    first_token = first_token_match.group(1) if first_token_match else ""
    starts_like_clipped_continuation = bool(
        re.match(r"^[a-záéíóúñ]", raw_text)
        and (
            first_token in {"we", "n", "y", "o", "e", "u", "de", "del", "al"}
            or len(first_token) <= 2
        )
    )
    ends_with_open_connector = bool(TERMINAL_CONNECTOR_RE.search(normalized_text))

    return CandidateSignals(
        normalized_text=normalized_text,
        token_set=token_set,
        content_token_set=content_token_set,
        numeric_tokens=numeric_tokens,
        qualifier_tokens=qualifier_tokens,
        annex_key=annex_key,
        actor_scope=actor_scope,
        has_ocr_noise=has_ocr_noise,
        is_truncated=is_truncated,
        is_context_dependent=is_context_dependent,
        malformed_char_count=malformed_char_count,
        starts_like_clipped_continuation=starts_like_clipped_continuation,
        ends_with_open_connector=ends_with_open_connector,
    )


def _jaccard_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _are_equivalent(left: CandidateView, right: CandidateView) -> tuple[bool, str, float]:
    left_signals = _candidate_signals(left)
    right_signals = _candidate_signals(right)

    if left_signals.actor_scope != right_signals.actor_scope:
        if "UNKNOWN" not in {left_signals.actor_scope, right_signals.actor_scope}:
            return False, "actor_scope_mismatch", 0.0

    if left_signals.numeric_tokens != right_signals.numeric_tokens:
        return False, "numeric_mismatch", 0.0

    if left_signals.qualifier_tokens != right_signals.qualifier_tokens:
        return False, "qualifier_mismatch", 0.0

    if left_signals.annex_key and right_signals.annex_key and left_signals.annex_key != right_signals.annex_key:
        return False, "annex_mismatch", 0.0

    for group in MERGE_CONFLICT_GROUPS:
        left_hit = any(token in left_signals.token_set for token in group)
        right_hit = any(token in right_signals.token_set for token in group)
        if left_hit != right_hit:
            return False, "material_token_family_mismatch", 0.0

    lexical_similarity = SequenceMatcher(None, left_signals.normalized_text, right_signals.normalized_text).ratio()
    token_similarity = _jaccard_similarity(left_signals.content_token_set, right_signals.content_token_set)

    if left_signals.annex_key and right_signals.annex_key and left_signals.annex_key == right_signals.annex_key:
        shared_tokens = left_signals.content_token_set & right_signals.content_token_set
        has_action_overlap = bool({"presentar", "anexar", "adjuntar", "incluir"} & left_signals.token_set & right_signals.token_set)
        if has_action_overlap and len(shared_tokens) >= 2:
            return True, "same_annex_action_signature", max(lexical_similarity, token_similarity)

    if lexical_similarity >= 0.95:
        return True, "near_exact_lexical_match", lexical_similarity
    if lexical_similarity >= 0.88 and token_similarity >= 0.70:
        return True, "high_lexical_and_token_similarity", lexical_similarity
    if left_signals.annex_key and left_signals.annex_key == right_signals.annex_key and lexical_similarity >= 0.75 and token_similarity >= 0.50:
        return True, "same_annex_with_high_similarity", lexical_similarity

    return False, "insufficient_similarity", lexical_similarity


def _clean_canonical_text(value: str) -> str:
    clean = _normalize_space(value)
    clean = re.sub(r"^(?:[-•*✓]\s*)+", "", clean)
    clean = re.sub(r"^(?:[A-Za-z]\)|\d+\)|\d+\.|[IVXLCDM]+\.)\s*", "", clean)
    return clean.strip()


def _category_from_text(value: str) -> str:
    normalized = _normalize_for_key(value)
    normalized = PROCEDURAL_EVENT_RE.sub(" ", normalized)
    scores: dict[str, int] = {category: 0 for category in CATEGORY_KEYWORDS}

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _normalize_for_key(keyword) in normalized:
                scores[category] += 1

    if scores[CATEGORY_PERSONNEL] > 0 and scores[CATEGORY_EXPERIENCE] > 0:
        if scores[CATEGORY_PERSONNEL] >= scores[CATEGORY_EXPERIENCE]:
            scores[CATEGORY_EXPERIENCE] -= 1
        else:
            scores[CATEGORY_PERSONNEL] -= 1

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ordered or ordered[0][1] <= 0:
        return CATEGORY_UNKNOWN

    best_category, best_score = ordered[0]
    tied = [item for item in ordered if item[1] == best_score]
    if len(tied) > 1:
        has_strong_technical_evidence = bool(
            re.search(
                r"\b(iso\s*9001|certificado\s+de\s+calidad|carta\s+de\s+respaldo\s+del\s+fabricante|certificacion\s+del\s+fabricante|certificación\s+del\s+fabricante|sistema\s+de\s+control|documentacion\s+tecnica|documentación\s+técnica)\b",
                normalized,
                re.IGNORECASE,
            )
        )
        tied_categories = {category for category, _ in tied}
        if has_strong_technical_evidence and CATEGORY_TECHNICAL in tied_categories:
            return CATEGORY_TECHNICAL

        has_strong_instruction_evidence = bool(
            re.search(r"\b(idioma|formato|pdf|zip|firmad[oa]|editable|presentarse|integrarse)\b", normalized, re.IGNORECASE)
        )
        if has_strong_instruction_evidence and CATEGORY_INSTRUCTIONS in tied_categories:
            return CATEGORY_INSTRUCTIONS

        has_strong_economic_evidence = bool(
            re.search(r"\b(precios?\s+unitarios?|importe|porcentaje\s+ofertado)\b", normalized, re.IGNORECASE)
        )
        if has_strong_economic_evidence and CATEGORY_ECONOMIC in tied_categories:
            return CATEGORY_ECONOMIC

        has_strong_commercial_evidence = bool(
            re.search(r"\b(parte\s+comercial|terminos\s+y\s+condiciones|términos\s+y\s+condiciones|condiciones\s+comerciales)\b", normalized, re.IGNORECASE)
        )
        if has_strong_commercial_evidence and CATEGORY_COMMERCIAL in tied_categories:
            return CATEGORY_COMMERCIAL
        return CATEGORY_UNKNOWN
    return best_category


def _candidate_quality_score(candidate: CandidateView) -> tuple[int, int, int, int, str]:
    signals = _candidate_signals(candidate)
    weird_penalty = signals.malformed_char_count
    return (
        0 if signals.has_ocr_noise else 1,
        0 if signals.is_context_dependent else 1,
        0 if signals.ends_with_open_connector else 1,
        1 if candidate.actor_text else 0,
        1 if candidate.modality_text else 0,
        max(len(candidate.requirement_text) - weird_penalty * 8, 0),
        candidate.id,
    )


def _is_sufficiently_complete(candidate: CandidateView, category: str) -> tuple[bool, list[str]]:
    signals = _candidate_signals(candidate)
    reasons: list[str] = []

    if signals.has_ocr_noise:
        reasons.append("ocr_noise")
    if signals.is_truncated:
        reasons.append("truncated_span")
    if signals.starts_like_clipped_continuation:
        reasons.append("clipped_continuation")
    if signals.ends_with_open_connector:
        reasons.append("open_terminal_connector")
    if signals.is_context_dependent:
        reasons.append("missing_context_antecedent")

    if signals.malformed_char_count >= 3:
        reasons.append("malformed_chars")

    if category == CATEGORY_UNKNOWN:
        reasons.append("unknown_category")

    return (len(reasons) == 0, reasons)


def _build_canonical_key(tender_id: str, canonical_text: str, category: str, actor_scope: str, numeric_tokens: tuple[str, ...]) -> str:
    payload = "|".join(
        [
            tender_id,
            _normalize_for_key(canonical_text),
            category,
            actor_scope,
            ",".join(numeric_tokens),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_requirement_drafts(tender_id: str, candidates: list[CandidateView]) -> list[RequirementDraft]:
    groups: list[list[CandidateView]] = []
    merge_reasons: dict[tuple[str, str], tuple[str, float]] = {}

    for candidate in sorted(candidates, key=lambda item: (item.source_filename or "", item.source_page or 0, item.id)):
        placed = False
        for group in groups:
            decisions = [_are_equivalent(existing, candidate) for existing in group]
            if all(decision[0] for decision in decisions):
                group.append(candidate)
                for existing, (_, reason, confidence) in zip(group[:-1], decisions, strict=False):
                    merge_reasons[(existing.id, candidate.id)] = (reason, confidence)
                placed = True
                break
        if not placed:
            groups.append([candidate])

    drafts: list[RequirementDraft] = []
    for group in groups:
        primary = max(group, key=_candidate_quality_score)
        canonical_text = _clean_canonical_text(primary.requirement_text)
        category = _category_from_text(canonical_text)

        has_review_risk = False
        confidences: list[float] = []
        reasons: list[str] = []
        for left_idx in range(len(group)):
            for right_idx in range(left_idx + 1, len(group)):
                left = group[left_idx]
                right = group[right_idx]
                decision = _are_equivalent(left, right)
                confidences.append(decision[2])
                reasons.append(decision[1])
                if decision[2] < 0.88:
                    has_review_risk = True

        quality_ok, quality_reasons = _is_sufficiently_complete(primary, category)
        if not quality_ok:
            has_review_risk = True
            reasons.extend(quality_reasons)

        normalization_status = STATUS_REVIEW_REQUIRED if has_review_risk else STATUS_NORMALIZED
        normalization_confidence = min(confidences) if confidences else (0.65 if has_review_risk else 0.98)

        reason_parts: list[str] = []
        if len(group) == 1:
            reason_parts.append("single_source_occurrence")
        else:
            reason_parts.append("merged_equivalent_occurrences")
            if reasons:
                reason_parts.append(
                    ",".join(sorted(set(reasons)))
                )
        if has_review_risk:
            reason_parts.append("requires_human_review")

        primary_signals = _candidate_signals(primary)
        canonical_key = _build_canonical_key(
            tender_id=tender_id,
            canonical_text=canonical_text,
            category=category,
            actor_scope=primary_signals.actor_scope,
            numeric_tokens=primary_signals.numeric_tokens,
        )

        drafts.append(
            RequirementDraft(
                candidates=sorted(group, key=lambda item: (item.source_filename or "", item.source_page or 0, item.id)),
                category=category,
                normalization_status=normalization_status,
                normalization_confidence=round(normalization_confidence, 4),
                normalization_reason=";".join(reason_parts),
                primary_candidate_id=primary.id,
                canonical_text=canonical_text,
                canonical_key=canonical_key,
            )
        )

    return sorted(drafts, key=lambda item: (item.canonical_text.lower(), item.primary_candidate_id))


def _candidate_view_from_row(row: RequirementCandidate) -> CandidateView:
    source_document = row.source_document
    return CandidateView(
        id=row.id,
        requirement_text=row.requirement_text,
        actor_text=row.actor_text,
        modality_text=row.modality_text,
        source_document_id=row.source_document_id,
        source_filename=source_document.original_filename if source_document else None,
        source_page=row.source_page,
        source_excerpt=row.source_excerpt,
        document_page_id=row.document_page_id,
        normalized_content_id=row.normalized_content_id,
    )


def _serialize_requirement(requirement: Requirement) -> dict[str, Any]:
    links = sorted(requirement.candidate_links, key=lambda row: (row.candidate.source_document_id if row.candidate else "", row.candidate.source_page if row.candidate else 0, row.id))
    candidates_payload: list[dict[str, Any]] = []
    primary_payload: dict[str, Any] | None = None

    for link in links:
        candidate = link.candidate
        if candidate is None:
            continue
        source_document = candidate.source_document
        item = {
            "candidate_id": candidate.id,
            "source_document_id": candidate.source_document_id,
            "source_filename": source_document.original_filename if source_document else None,
            "source_page": candidate.source_page,
            "requirement_text": candidate.requirement_text,
            "source_excerpt": candidate.source_excerpt,
            "actor_text": candidate.actor_text,
            "modality_text": candidate.modality_text,
            "document_page_id": candidate.document_page_id,
            "normalized_content_id": candidate.normalized_content_id,
            "is_primary_source": link.is_primary_source,
            "link_origin": link.link_origin,
        }
        candidates_payload.append(item)
        if link.is_primary_source:
            primary_payload = item

    return {
        "id": requirement.id,
        "tender_id": requirement.tender_id,
        "canonical_key": requirement.canonical_key,
        "canonical_text": requirement.canonical_text,
        "category": requirement.category,
        "normalization_status": requirement.normalization_status,
        "normalizer_version": requirement.normalizer_version,
        "normalization_confidence": requirement.normalization_confidence,
        "normalization_reason": requirement.normalization_reason,
        "source_occurrence_count": len(candidates_payload),
        "primary_source": primary_payload,
        "candidates": candidates_payload,
        "created_at": requirement.created_at,
        "updated_at": requirement.updated_at,
    }


def _build_summary(requirements: list[Requirement], candidate_count: int) -> dict[str, Any]:
    normalized_count = 0
    review_required_count = 0
    merged_count = 0
    single_source_count = 0
    category_counts: dict[str, int] = {}

    for row in requirements:
        source_count = len(row.candidate_links)
        if source_count >= 2:
            merged_count += 1
        elif source_count == 1:
            single_source_count += 1

        if row.normalization_status == STATUS_NORMALIZED:
            normalized_count += 1
        else:
            review_required_count += 1

        category_counts[row.category] = category_counts.get(row.category, 0) + 1

    return {
        "candidate_count": candidate_count,
        "requirement_count": len(requirements),
        "normalized_count": normalized_count,
        "review_required_count": review_required_count,
        "merged_requirement_count": merged_count,
        "single_source_requirement_count": single_source_count,
        "category_counts": dict(sorted(category_counts.items())),
        "unknown_count": category_counts.get(CATEGORY_UNKNOWN, 0),
    }


def get_tender_requirements(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document)
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    candidate_count = db.execute(
        select(RequirementCandidate)
        .where(RequirementCandidate.tender_id == tender_id, RequirementCandidate.review_status != REVIEW_REJECTED)
    ).scalars().all()

    return {
        "tender_id": tender_id,
        "normalizer_version": REQUIREMENT_NORMALIZER_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _build_summary(requirements, len(candidate_count)),
        "requirements": [_serialize_requirement(row) for row in requirements],
    }


def normalize_tender_requirements(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    candidate_rows = db.execute(
        select(RequirementCandidate)
        .options(selectinload(RequirementCandidate.source_document))
        .where(RequirementCandidate.tender_id == tender_id, RequirementCandidate.review_status != REVIEW_REJECTED)
        .order_by(RequirementCandidate.source_document_id.asc(), RequirementCandidate.source_page.asc(), RequirementCandidate.created_at.asc())
    ).scalars().all()

    candidate_views = [_candidate_view_from_row(row) for row in candidate_rows]
    drafts = _build_requirement_drafts(tender_id, candidate_views)

    existing_requirements = db.execute(
        select(Requirement)
        .options(selectinload(Requirement.candidate_links))
        .where(Requirement.tender_id == tender_id)
    ).scalars().all()
    by_key = {row.canonical_key: row for row in existing_requirements}

    seen_keys: set[str] = set()
    for draft in drafts:
        seen_keys.add(draft.canonical_key)
        row = by_key.get(draft.canonical_key)
        if row is None:
            row = Requirement(
                tender_id=tender_id,
                canonical_key=draft.canonical_key,
                canonical_text=draft.canonical_text,
                category=draft.category,
                normalization_status=draft.normalization_status,
                normalizer_version=REQUIREMENT_NORMALIZER_VERSION,
                normalization_confidence=draft.normalization_confidence,
                normalization_reason=draft.normalization_reason,
                primary_candidate_id=draft.primary_candidate_id,
            )
            db.add(row)
            db.flush()
        else:
            row.canonical_text = draft.canonical_text
            row.category = draft.category
            row.normalization_status = draft.normalization_status
            row.normalizer_version = REQUIREMENT_NORMALIZER_VERSION
            row.normalization_confidence = draft.normalization_confidence
            row.normalization_reason = draft.normalization_reason
            row.primary_candidate_id = draft.primary_candidate_id

        candidate_ids = {candidate.id for candidate in draft.candidates}
        existing_by_candidate = {link.requirement_candidate_id: link for link in row.candidate_links}

        for link in list(row.candidate_links):
            if link.requirement_candidate_id not in candidate_ids:
                row.candidate_links.remove(link)

        for candidate in draft.candidates:
            link = existing_by_candidate.get(candidate.id)
            is_primary = candidate.id == draft.primary_candidate_id
            if link is None:
                row.candidate_links.append(
                    RequirementCandidateLink(
                        requirement_id=row.id,
                        requirement_candidate_id=candidate.id,
                        is_primary_source=is_primary,
                        link_origin=ORIGIN_DETERMINISTIC,
                    )
                )
            else:
                link.is_primary_source = is_primary
                link.link_origin = ORIGIN_DETERMINISTIC

    for row in existing_requirements:
        if row.canonical_key not in seen_keys:
            db.delete(row)

    db.flush()
    return get_tender_requirements(db, tender_id)
