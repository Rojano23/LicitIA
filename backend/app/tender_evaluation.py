from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentPage,
    EvaluationCriterion,
    EvaluationCriterionEvidence,
    NormalizedContent,
    Tender,
    TenderDocument,
    TenderEvaluationModel,
    TenderEvaluationModelEvidence,
)

EVALUATION_DETECTOR_VERSION = "mvp-04.1"

REVIEW_SUGGESTED = "SUGGESTED"
REVIEW_CONFIRMED = "CONFIRMED"
REVIEW_REJECTED = "REJECTED"

ACTION_CONFIRM = "CONFIRM"
ACTION_REJECT = "REJECT"
ACTION_OVERRIDE = "OVERRIDE"
ACTION_RESET = "RESET_TO_SUGGESTED"

ORIGIN_DETERMINISTIC = "DETERMINISTIC"

METHOD_BINARY = "BINARY_COMPLIANCE"
METHOD_POINTS = "POINTS_PERCENTAGES"
METHOD_COST_BENEFIT = "COST_BENEFIT"
METHOD_LOWEST_PRICE = "LOWEST_EVALUATED_PRICE"
METHOD_TECH_ECON = "TECHNICAL_ECONOMIC_COMBINED"
METHOD_MULTI_STAGE = "MULTI_STAGE"
METHOD_MIXED = "MIXED"
METHOD_OTHER = "OTHER"
METHOD_UNKNOWN = "UNKNOWN"

CRITERION_PASS_FAIL = "PASS_FAIL_RULE"
CRITERION_SCORING_COMPONENT = "SCORING_COMPONENT"
CRITERION_MINIMUM_SCORE = "MINIMUM_SCORE"
CRITERION_WEIGHTING = "WEIGHTING_RULE"
CRITERION_QUALIFICATION_GATE = "QUALIFICATION_GATE"
CRITERION_REJECTION_CAUSE = "REJECTION_CAUSE"
CRITERION_AWARD_RULE = "AWARD_RULE"
CRITERION_PRICE_RULE = "PRICE_EVALUATION_RULE"
CRITERION_TECH_RULE = "TECHNICAL_EVALUATION_RULE"
CRITERION_ADMIN_RULE = "ADMINISTRATIVE_EVALUATION_RULE"
CRITERION_LEGAL_RULE = "LEGAL_EVALUATION_RULE"
CRITERION_EXPERIENCE_RULE = "EXPERIENCE_EVALUATION_RULE"
CRITERION_OTHER = "OTHER"
CRITERION_UNKNOWN = "UNKNOWN"

ROLE_METHOD_DECLARATION = "METHOD_DECLARATION"
ROLE_SCORING_RULE = "SCORING_RULE"
ROLE_PASS_FAIL_RULE = "PASS_FAIL_RULE"
ROLE_THRESHOLD = "THRESHOLD"
ROLE_REJECTION_RULE = "REJECTION_RULE"
ROLE_AWARD_RULE = "AWARD_RULE"
ROLE_EVALUATION_STAGE = "EVALUATION_STAGE"
ROLE_OTHER = "OTHER"

BINARY_ANCHOR_RE = re.compile(
    r"\b(evaluaci(?:on|o)n[^\.\n]{0,80}binari[ao]|cumple\s*/\s*no\s+cumple|cumple\s+no\s+cumple)\b",
    re.IGNORECASE,
)
EVALUATION_CONTEXT_RE = re.compile(r"\b(evaluaci(?:on|o)n|criterio|metodo|dictamen|solvente|adjudic)\b", re.IGNORECASE)
POINTS_WORD_RE = re.compile(r"\b(puntos|puntaje|puntuacion|ponderacion|porcentaje|porcentajes|calificacion\s+minima)\b", re.IGNORECASE)
POINTS_METHOD_RE = re.compile(r"\b(puntos\s+y\s+porcentajes|metodo\s+de\s+puntos|puntuacion\s+porcentual)\b", re.IGNORECASE)
PERCENT_VALUE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[\.,]\d+)?)\s*%")
POINTS_VALUE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[\.,]\d+)?)\s*puntos?\b", re.IGNORECASE)
MINIMUM_POINTS_RE = re.compile(r"\b(minim[oa]|calificacion\s+minima|minimo\s+de\s+puntos)\b[^\.\n]{0,40}?(\d{1,3}(?:[\.,]\d+)?)\s*puntos?\b", re.IGNORECASE)
REJECTION_RE = re.compile(r"\b(causa\s+de\s+desechamiento|sera\s+desechad[oa]|motivo\s+de\s+rechazo|incumplimiento[^\.\n]{0,80}(desechamiento|rechazo))\b", re.IGNORECASE)
COST_BENEFIT_RE = re.compile(r"\b(costo\s*[- ]\s*beneficio|costo\s+beneficio)\b", re.IGNORECASE)
LOWEST_PRICE_RE = re.compile(
    r"\b(adjudic\w*[^\.\n]{0,120}(precio\s+m[aá]s\s+bajo|menor\s+precio|precio\s+m[aá]s\s+bajo\s+solvente|solvente))\b",
    re.IGNORECASE,
)
GATE_RE = re.compile(r"\b(solo\s+se\s+evaluara|solo\s+se\s+abrira|siempre\s+que\s+hayan\s+cumplido|una\s+vez\s+aprobada\s+la\s+evaluacion\s+tecnica)\b", re.IGNORECASE)
TECH_ECON_COMBINED_RE = re.compile(r"\b(evaluacion\s+tecnica[^\.\n]{0,120}evaluacion\s+economica|tecnica\s*\+\s*economica|tecnica\s+y\s+economica[^\.\n]{0,80}(ponderacion|combinad|conjunta))\b", re.IGNORECASE)
AWARD_SCORE_RE = re.compile(r"\b(adjudic\w*[^\.\n]{0,120}mayor\s+puntuacion)\b", re.IGNORECASE)
WEIGHTING_POSITIVE_CONTEXT_RE = re.compile(
    r"\b(ponderaci(?:on|o)n|peso\s+de\s+evaluaci(?:on|o)n|puntuaci(?:on|o)n|puntaje|puntos|calificaci(?:on|o)n|evaluaci(?:on|o)n\s+tecnica|evaluaci(?:on|o)n\s+economica|se\s+otorgaran\s+\d+\s+puntos?|representar(?:a|á)\s+(?:el\s+)?\d+(?:[\.,]\d+)?\s*%\s+de\s+la\s+evaluaci(?:on|o)n|valor\s+ponderado|factor\s+de\s+evaluaci(?:on|o)n)\b",
    re.IGNORECASE,
)
WEIGHTING_NEGATIVE_CONTEXT_RE = re.compile(
    r"\b(pena\s+convencional|penalizaci(?:on|o)n|deductiva|garant(?:ia|i)a|fianza|anticipo|iva|impuesto|retenci(?:on|o)n|descuento|intere(?:s|ses)|da(?:n|ñ)os|mora|sanci(?:on|o)n)\b",
    re.IGNORECASE,
)
PRICE_CONTEXT_RE = re.compile(r"\b(precio|precios|importe|oferta|ofertar|propuesta\s+economica)\b", re.IGNORECASE)
PRICE_EVAL_EXPLICIT_RE = re.compile(
    r"\b(criterio\s+de\s+adjudicaci(?:on|[oó]n)|se\s+adjudicar(?:a|á)|adjudicaci(?:on|[oó]n)[^\.\n]{0,80}(precio\s+m[aá]s\s+bajo|menor\s+precio)|precio\s+m[aá]s\s+bajo|menor\s+precio|evaluaci(?:on|[oó]n)\s+econ[oó]mica[^\.\n]{0,120}(precio|precios|compar)|comparar[aá]n\s+los\s+precios|propuesta\s+econ[oó]mica[^\.\n]{0,120}(evaluad|compar))\b",
    re.IGNORECASE,
)
VISIBLE_PRICE_SEMANTICS_RE = re.compile(
    r"\b(precio\s+m[aá]s\s+bajo|menor\s+precio|precio\s+unitario\s+m[aá]s\s+bajo|importe\s+total\s+m[aá]s\s+bajo|precio\s+sea\s+el\s+m[aá]s\s+bajo|propuesta\s+econ[oó]mica|comparar[aá]n\s+los\s+precios|comparaci(?:on|[oó]n)\s+de\s+precios|precio\s+evaluado|precios\s+unitarios\s+ofertados|importe\s+total\s+m[aá]s\s+bajo)\b",
    re.IGNORECASE,
)
VISIBLE_AWARD_SEMANTICS_RE = re.compile(r"\b(adjudicaci(?:on|[oó]n)|se\s+adjudicar(?:a|á)|solvente)\b", re.IGNORECASE)


@dataclass
class TextFragment:
    source_document_id: str
    source_filename: str
    source_page: int | None
    text: str


@dataclass
class DetectedEvidence:
    source_document_id: str
    source_page: int | None
    source_excerpt: str
    evidence_role: str


@dataclass
class DetectedCriterion:
    semantic_key: str
    criterion_type: str
    category: str | None
    title: str
    criterion_text: str
    weight_value: float | None = None
    weight_unit: str | None = None
    threshold_operator: str | None = None
    threshold_value: float | None = None
    threshold_unit: str | None = None
    is_exclusionary: bool | None = None
    source_document_id: str = ""
    source_page: int | None = None
    source_excerpt: str = ""
    evidence_role: str = ROLE_OTHER
    evidence: list[DetectedEvidence] = field(default_factory=list)


def _normalize_space(text: str) -> str:
    return " ".join((text or "").split())


def _normalize_for_key(text: str) -> str:
    value = _normalize_space(text).lower()
    return re.sub(r"[^a-z0-9%]+", "_", value).strip("_")


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _excerpt(text: str, limit: int = 500) -> str:
    value = _normalize_space(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


_EVIDENCE_ROLE_PRIORITY: dict[str, int] = {
    ROLE_METHOD_DECLARATION: 100,
    ROLE_AWARD_RULE: 90,
    ROLE_SCORING_RULE: 80,
    ROLE_PASS_FAIL_RULE: 70,
    ROLE_THRESHOLD: 60,
    ROLE_REJECTION_RULE: 50,
    ROLE_EVALUATION_STAGE: 40,
    ROLE_OTHER: 10,
}


def _preferred_evidence_role(left: str, right: str) -> str:
    if _EVIDENCE_ROLE_PRIORITY.get(right, 0) > _EVIDENCE_ROLE_PRIORITY.get(left, 0):
        return right
    return left


def _evidence_key(source_document_id: str, source_page: int | None, excerpt: str) -> tuple[str, int | None, str]:
    excerpt_sha = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    return (source_document_id, source_page, excerpt_sha)


def _category_from_text(text: str) -> str | None:
    low = text.lower()
    if "tecnic" in low or "dictamen tecnico" in low:
        return "TECHNICAL"
    if "econom" in low or "precio" in low:
        return "ECONOMIC"
    if "admin" in low:
        return "ADMINISTRATIVE"
    if "legal" in low or "jurid" in low:
        return "LEGAL"
    if "experien" in low:
        return "EXPERIENCE"
    return None


def _category_from_value_context(text: str, index: int) -> str | None:
    start = max(0, index - 80)
    window = text[start:index]
    by_window = _category_from_text(window)
    if by_window is not None:
        return by_window
    return _category_from_text(text)


def _split_fragments(text: str) -> list[str]:
    normalized = text.replace("\r", "\n")
    paragraph_blocks: list[str] = []
    block_lines: list[str] = []

    for raw_line in normalized.split("\n"):
        clean_line = _normalize_space(raw_line)
        if not clean_line:
            if block_lines:
                paragraph_blocks.append(" ".join(block_lines))
                block_lines = []
            continue
        block_lines.append(clean_line)

    if block_lines:
        paragraph_blocks.append(" ".join(block_lines))

    parts: list[str] = []
    for block in paragraph_blocks:
        clean_block = _normalize_space(block)
        if len(clean_block) < 20:
            continue
        sentence_candidates = re.split(r"(?<=[\.;])\s+", clean_block)
        for sentence in sentence_candidates:
            clean_sentence = _normalize_space(sentence)
            if 20 <= len(clean_sentence) <= 600:
                parts.append(clean_sentence)
    return parts


def _coherent_context(text: str, index: int, radius: int = 120) -> str:
    start = max(0, index - radius)
    end = min(len(text), index + radius)
    return text[start:end]


def _has_weighting_semantics(text: str, index: int) -> bool:
    context = _coherent_context(text, index)
    has_positive = bool(WEIGHTING_POSITIVE_CONTEXT_RE.search(context))
    has_negative = bool(WEIGHTING_NEGATIVE_CONTEXT_RE.search(context))
    if has_negative and not has_positive:
        return False
    return has_positive


def _is_price_evaluation_context(text: str) -> bool:
    return bool(PRICE_CONTEXT_RE.search(text) and PRICE_EVAL_EXPLICIT_RE.search(text))


def _has_visible_price_semantics(text: str) -> bool:
    return bool(VISIBLE_PRICE_SEMANTICS_RE.search(text))


def _has_visible_award_semantics(text: str) -> bool:
    return bool(VISIBLE_AWARD_SEMANTICS_RE.search(text))


def _build_semantic_key(
    criterion_type: str,
    category: str | None,
    criterion_text: str,
    weight_value: float | None,
    weight_unit: str | None,
    threshold_operator: str | None,
    threshold_value: float | None,
    threshold_unit: str | None,
    is_exclusionary: bool | None,
) -> str:
    payload = "|".join(
        [
            criterion_type,
            category or "",
            _normalize_for_key(criterion_text)[:220],
            str(weight_value) if weight_value is not None else "",
            weight_unit or "",
            threshold_operator or "",
            str(threshold_value) if threshold_value is not None else "",
            threshold_unit or "",
            "1" if is_exclusionary else "0" if is_exclusionary is not None else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_current_normalized_fragments(db: Session, tender_id: str) -> list[TextFragment]:
    rows = (
        db.execute(
            select(
                TenderDocument.id,
                TenderDocument.original_filename,
                DocumentPage.page_number,
                NormalizedContent.normalized_text,
            )
            .join(DocumentPage, DocumentPage.document_id == TenderDocument.id)
            .join(NormalizedContent, NormalizedContent.document_page_id == DocumentPage.id)
            .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            .order_by(TenderDocument.original_filename.asc(), DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
        )
        .all()
    )

    fragments: list[TextFragment] = []
    for doc_id, filename, page_number, normalized_text in rows:
        text_value = (normalized_text or "").strip()
        if not text_value:
            continue
        for fragment in _split_fragments(text_value):
            fragments.append(
                TextFragment(
                    source_document_id=doc_id,
                    source_filename=filename,
                    source_page=page_number,
                    text=fragment,
                )
            )
    return fragments


def _detect_criteria_from_fragment(fragment: TextFragment) -> list[DetectedCriterion]:
    text = fragment.text
    low = text.lower()
    out: list[DetectedCriterion] = []

    if BINARY_ANCHOR_RE.search(text) and EVALUATION_CONTEXT_RE.search(text):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_PASS_FAIL, _category_from_text(text), criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_PASS_FAIL,
                category=_category_from_text(text),
                title="Evaluacion en esquema binario",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_PASS_FAIL_RULE,
            )
        )

    for match in MINIMUM_POINTS_RE.finditer(text):
        threshold = _to_float(match.group(2))
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(
                    CRITERION_MINIMUM_SCORE,
                    _category_from_text(text),
                    criterion_text,
                    None,
                    None,
                    "GREATER_THAN_OR_EQUAL",
                    threshold,
                    "POINTS",
                    None,
                ),
                criterion_type=CRITERION_MINIMUM_SCORE,
                category=_category_from_text(text),
                title="Puntaje minimo para mantener solvencia",
                criterion_text=criterion_text,
                threshold_operator="GREATER_THAN_OR_EQUAL",
                threshold_value=threshold,
                threshold_unit="POINTS",
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_THRESHOLD,
            )
        )

    if REJECTION_RE.search(text):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(
                    CRITERION_REJECTION_CAUSE,
                    _category_from_text(text),
                    criterion_text,
                    None,
                    None,
                    None,
                    None,
                    None,
                    True,
                ),
                criterion_type=CRITERION_REJECTION_CAUSE,
                category=_category_from_text(text),
                title="Causal explicita de desechamiento o rechazo",
                criterion_text=criterion_text,
                is_exclusionary=True,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_REJECTION_RULE,
            )
        )

    if GATE_RE.search(text) and "evalu" in low:
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_QUALIFICATION_GATE, _category_from_text(text), criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_QUALIFICATION_GATE,
                category=_category_from_text(text),
                title="Condicion de paso entre etapas de evaluacion",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_EVALUATION_STAGE,
            )
        )

    if LOWEST_PRICE_RE.search(text):
        criterion_text = _excerpt(text)
        if _has_visible_award_semantics(criterion_text):
            out.append(
                DetectedCriterion(
                    semantic_key=_build_semantic_key(CRITERION_AWARD_RULE, "ECONOMIC", criterion_text, None, None, None, None, None, None),
                    criterion_type=CRITERION_AWARD_RULE,
                    category="ECONOMIC",
                    title="Regla de adjudicacion por precio",
                    criterion_text=criterion_text,
                    source_document_id=fragment.source_document_id,
                    source_page=fragment.source_page,
                    source_excerpt=criterion_text,
                    evidence_role=ROLE_AWARD_RULE,
                )
            )
        if _has_visible_price_semantics(criterion_text):
            out.append(
                DetectedCriterion(
                    semantic_key=_build_semantic_key(CRITERION_PRICE_RULE, "ECONOMIC", criterion_text, None, None, None, None, None, None),
                    criterion_type=CRITERION_PRICE_RULE,
                    category="ECONOMIC",
                    title="Regla explicita de evaluacion economica",
                    criterion_text=criterion_text,
                    source_document_id=fragment.source_document_id,
                    source_page=fragment.source_page,
                    source_excerpt=criterion_text,
                    evidence_role=ROLE_AWARD_RULE,
                )
            )

    if AWARD_SCORE_RE.search(text):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_AWARD_RULE, _category_from_text(text), criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_AWARD_RULE,
                category=_category_from_text(text),
                title="Regla de adjudicacion por puntuacion",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_AWARD_RULE,
            )
        )

    for match in POINTS_VALUE_RE.finditer(text):
        if not EVALUATION_CONTEXT_RE.search(text):
            continue
        value = _to_float(match.group(1))
        category = _category_from_value_context(text, match.start())
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_SCORING_COMPONENT, category, criterion_text, value, "POINTS", None, None, None, None),
                criterion_type=CRITERION_SCORING_COMPONENT,
                category=category,
                title="Componente de puntuacion explicito",
                criterion_text=criterion_text,
                weight_value=value,
                weight_unit="POINTS",
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_SCORING_RULE,
            )
        )

    for match in PERCENT_VALUE_RE.finditer(text):
        if not _has_weighting_semantics(text, match.start()):
            continue
        value = _to_float(match.group(1))
        category = _category_from_value_context(text, match.start())
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_WEIGHTING, category, criterion_text, value, "PERCENT", None, None, None, None),
                criterion_type=CRITERION_WEIGHTING,
                category=category,
                title="Ponderacion explicita",
                criterion_text=criterion_text,
                weight_value=value,
                weight_unit="PERCENT",
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_SCORING_RULE,
            )
        )

    if re.search(r"\bevaluacion\s+tecnica\b", text, re.IGNORECASE):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_TECH_RULE, "TECHNICAL", criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_TECH_RULE,
                category="TECHNICAL",
                title="Regla de evaluacion tecnica",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_METHOD_DECLARATION,
            )
        )

    if _is_price_evaluation_context(text):
        criterion_text = _excerpt(text)
        if _has_visible_price_semantics(criterion_text):
            out.append(
                DetectedCriterion(
                    semantic_key=_build_semantic_key(CRITERION_PRICE_RULE, "ECONOMIC", criterion_text, None, None, None, None, None, None),
                    criterion_type=CRITERION_PRICE_RULE,
                    category="ECONOMIC",
                    title="Regla de evaluacion economica",
                    criterion_text=criterion_text,
                    source_document_id=fragment.source_document_id,
                    source_page=fragment.source_page,
                    source_excerpt=criterion_text,
                    evidence_role=ROLE_METHOD_DECLARATION,
                )
            )

    if re.search(r"\bevaluacion\s+administrativa\b", text, re.IGNORECASE):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_ADMIN_RULE, "ADMINISTRATIVE", criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_ADMIN_RULE,
                category="ADMINISTRATIVE",
                title="Regla de evaluacion administrativa",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_METHOD_DECLARATION,
            )
        )

    if re.search(r"\bevaluacion\s+legal\b", text, re.IGNORECASE):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_LEGAL_RULE, "LEGAL", criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_LEGAL_RULE,
                category="LEGAL",
                title="Regla de evaluacion legal",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_METHOD_DECLARATION,
            )
        )

    if re.search(r"\bexperien\w+[^\.\n]{0,60}(puntos?|evalua)\b", text, re.IGNORECASE):
        criterion_text = _excerpt(text)
        out.append(
            DetectedCriterion(
                semantic_key=_build_semantic_key(CRITERION_EXPERIENCE_RULE, "EXPERIENCE", criterion_text, None, None, None, None, None, None),
                criterion_type=CRITERION_EXPERIENCE_RULE,
                category="EXPERIENCE",
                title="Regla de evaluacion de experiencia",
                criterion_text=criterion_text,
                source_document_id=fragment.source_document_id,
                source_page=fragment.source_page,
                source_excerpt=criterion_text,
                evidence_role=ROLE_SCORING_RULE,
            )
        )

    return out


def _direct_method_evidence(fragments: list[TextFragment]) -> tuple[set[str], list[DetectedEvidence]]:
    methods: set[str] = set()
    evidence: list[DetectedEvidence] = []
    for fragment in fragments:
        text = fragment.text
        if not EVALUATION_CONTEXT_RE.search(text):
            continue

        if BINARY_ANCHOR_RE.search(text):
            methods.add(METHOD_BINARY)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_METHOD_DECLARATION))
        if COST_BENEFIT_RE.search(text):
            methods.add(METHOD_COST_BENEFIT)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_METHOD_DECLARATION))
        if LOWEST_PRICE_RE.search(text) and _has_visible_price_semantics(text):
            methods.add(METHOD_LOWEST_PRICE)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_AWARD_RULE))
        if TECH_ECON_COMBINED_RE.search(text):
            methods.add(METHOD_TECH_ECON)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_METHOD_DECLARATION))
        if GATE_RE.search(text) and "evalu" in text.lower():
            methods.add(METHOD_MULTI_STAGE)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_EVALUATION_STAGE))
        if POINTS_METHOD_RE.search(text):
            methods.add(METHOD_POINTS)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_METHOD_DECLARATION))
        elif POINTS_WORD_RE.search(text) and (PERCENT_VALUE_RE.search(text) or POINTS_VALUE_RE.search(text) or MINIMUM_POINTS_RE.search(text)):
            methods.add(METHOD_POINTS)
            evidence.append(DetectedEvidence(fragment.source_document_id, fragment.source_page, _excerpt(text), ROLE_SCORING_RULE))

    return methods, evidence


def _dedupe_criteria(items: list[DetectedCriterion]) -> list[DetectedCriterion]:
    index: dict[str, DetectedCriterion] = {}
    for item in items:
        evidence_item = DetectedEvidence(item.source_document_id, item.source_page, item.source_excerpt, item.evidence_role)
        existing = index.get(item.semantic_key)
        if existing is None:
            item.evidence = [evidence_item]
            index[item.semantic_key] = item
            continue
        existing_keys = {(ev.source_document_id, ev.source_page, ev.source_excerpt) for ev in existing.evidence}
        key = (evidence_item.source_document_id, evidence_item.source_page, evidence_item.source_excerpt)
        if key not in existing_keys:
            existing.evidence.append(evidence_item)
    return list(index.values())


def _derive_method(criteria: list[DetectedCriterion], direct_methods: set[str]) -> str:
    methods = set(direct_methods)
    criterion_types = {item.criterion_type for item in criteria}

    if CRITERION_PASS_FAIL in criterion_types or CRITERION_REJECTION_CAUSE in criterion_types:
        methods.add(METHOD_BINARY)
    if CRITERION_SCORING_COMPONENT in criterion_types or CRITERION_WEIGHTING in criterion_types or CRITERION_MINIMUM_SCORE in criterion_types:
        methods.add(METHOD_POINTS)
    if CRITERION_AWARD_RULE in criterion_types and any("precio" in (item.criterion_text or "").lower() for item in criteria):
        methods.add(METHOD_LOWEST_PRICE)
    if CRITERION_QUALIFICATION_GATE in criterion_types:
        methods.add(METHOD_MULTI_STAGE)
    if CRITERION_TECH_RULE in criterion_types and CRITERION_PRICE_RULE in criterion_types:
        methods.add(METHOD_TECH_ECON)

    methods.discard(METHOD_UNKNOWN)
    if not methods:
        return METHOD_UNKNOWN
    if len(methods) == 1:
        return sorted(methods)[0]
    return METHOD_MIXED


def _build_model_summary(method: str, criteria: list[DetectedCriterion]) -> str:
    if method == METHOD_UNKNOWN:
        return "No hay evidencia explicita suficiente para clasificar el metodo de evaluacion."

    by_type: dict[str, int] = {}
    for item in criteria:
        by_type[item.criterion_type] = by_type.get(item.criterion_type, 0) + 1
    top = ", ".join(f"{key}:{value}" for key, value in sorted(by_type.items(), key=lambda p: (p[0])))
    return f"Metodo sugerido {method} soportado por criterios explicitos ({top})."


def _criterion_has_human_override(row: EvaluationCriterion) -> bool:
    return any(
        [
            row.human_criterion_type,
            row.human_category,
            row.human_title,
            row.human_criterion_text,
            row.human_weight_value is not None,
            row.human_weight_unit,
            row.human_threshold_operator,
            row.human_threshold_value is not None,
            row.human_threshold_unit,
            row.human_is_exclusionary is not None,
            row.human_note,
        ]
    )


def _model_has_human_override(row: TenderEvaluationModel) -> bool:
    return bool(row.human_method or row.human_summary)


def _reconcile_model_evidence(
    db: Session,
    model: TenderEvaluationModel,
    evidence_rows: list[DetectedEvidence],
    *,
    mutable: bool,
) -> None:
    if not mutable:
        return

    existing = {(row.source_document_id, row.source_page, row.excerpt_sha256): row for row in model.evidence}
    collapsed: dict[tuple[str, int | None, str], DetectedEvidence] = {}

    for item in evidence_rows:
        excerpt = _excerpt(item.source_excerpt)
        key = _evidence_key(item.source_document_id, item.source_page, excerpt)
        previous = collapsed.get(key)
        if previous is None:
            collapsed[key] = DetectedEvidence(
                source_document_id=item.source_document_id,
                source_page=item.source_page,
                source_excerpt=excerpt,
                evidence_role=item.evidence_role,
            )
            continue
        previous.evidence_role = _preferred_evidence_role(previous.evidence_role, item.evidence_role)

    expected_keys = set(collapsed.keys())
    for key, item in collapsed.items():
        if key in existing:
            existing[key].evidence_role = _preferred_evidence_role(existing[key].evidence_role, item.evidence_role)
            continue
        db.add(
            TenderEvaluationModelEvidence(
                evaluation_model=model,
                source_document_id=item.source_document_id,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                excerpt_sha256=key[2],
                evidence_role=item.evidence_role,
            )
        )

    for key, row in existing.items():
        if key not in expected_keys:
            db.delete(row)


def _reconcile_criteria(db: Session, tender_id: str, model: TenderEvaluationModel, detected: list[DetectedCriterion]) -> None:
    existing_rows = (
        db.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.tender_id == tender_id)
            .options(selectinload(EvaluationCriterion.evidence))
        )
        .scalars()
        .all()
    )
    existing_by_key = {row.semantic_key: row for row in existing_rows}
    detected_keys = {item.semantic_key for item in detected}

    for row in existing_rows:
        if row.detection_origin != ORIGIN_DETERMINISTIC:
            continue
        if row.review_status != REVIEW_SUGGESTED:
            continue
        if _criterion_has_human_override(row):
            continue
        if row.semantic_key not in detected_keys:
            db.delete(row)

    for item in detected:
        row = existing_by_key.get(item.semantic_key)
        if row is None:
            row = EvaluationCriterion(
                tender_id=tender_id,
                evaluation_model_id=model.id,
                semantic_key=item.semantic_key,
                criterion_type=item.criterion_type,
                category=item.category,
                title=item.title,
                criterion_text=item.criterion_text,
                weight_value=item.weight_value,
                weight_unit=item.weight_unit,
                threshold_operator=item.threshold_operator,
                threshold_value=item.threshold_value,
                threshold_unit=item.threshold_unit,
                is_exclusionary=item.is_exclusionary,
                source_document_id=item.source_document_id,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                detection_origin=ORIGIN_DETERMINISTIC,
                review_status=REVIEW_SUGGESTED,
                detector_version=EVALUATION_DETECTOR_VERSION,
            )
            db.add(row)
            db.flush()
            existing_by_key[item.semantic_key] = row
        elif row.review_status == REVIEW_SUGGESTED and not _criterion_has_human_override(row):
            row.evaluation_model_id = model.id
            row.criterion_type = item.criterion_type
            row.category = item.category
            row.title = item.title
            row.criterion_text = item.criterion_text
            row.weight_value = item.weight_value
            row.weight_unit = item.weight_unit
            row.threshold_operator = item.threshold_operator
            row.threshold_value = item.threshold_value
            row.threshold_unit = item.threshold_unit
            row.is_exclusionary = item.is_exclusionary
            row.source_document_id = item.source_document_id
            row.source_page = item.source_page
            row.source_excerpt = item.source_excerpt
            row.detector_version = EVALUATION_DETECTOR_VERSION
            row.detection_origin = ORIGIN_DETERMINISTIC

        mutable = row.review_status == REVIEW_SUGGESTED and not _criterion_has_human_override(row)
        if mutable:
            existing_evidence = {(ev.source_document_id, ev.source_page, ev.excerpt_sha256): ev for ev in row.evidence}
            collapsed: dict[tuple[str, int | None, str], DetectedEvidence] = {}

            evidence_pool = item.evidence or [
                DetectedEvidence(
                    source_document_id=item.source_document_id,
                    source_page=item.source_page,
                    source_excerpt=item.source_excerpt,
                    evidence_role=item.evidence_role,
                )
            ]

            for evidence in evidence_pool:
                excerpt = _excerpt(evidence.source_excerpt)
                key = _evidence_key(evidence.source_document_id, evidence.source_page, excerpt)
                previous = collapsed.get(key)
                if previous is None:
                    collapsed[key] = DetectedEvidence(
                        source_document_id=evidence.source_document_id,
                        source_page=evidence.source_page,
                        source_excerpt=excerpt,
                        evidence_role=evidence.evidence_role,
                    )
                    continue
                previous.evidence_role = _preferred_evidence_role(previous.evidence_role, evidence.evidence_role)

            expected_keys = set(collapsed.keys())
            for key, evidence in collapsed.items():
                if key in existing_evidence:
                    existing_evidence[key].evidence_role = _preferred_evidence_role(
                        existing_evidence[key].evidence_role,
                        evidence.evidence_role,
                    )
                    continue
                db.add(
                    EvaluationCriterionEvidence(
                        criterion=row,
                        source_document_id=evidence.source_document_id,
                        source_page=evidence.source_page,
                        source_excerpt=evidence.source_excerpt,
                        excerpt_sha256=key[2],
                        evidence_role=evidence.evidence_role,
                    )
                )

            for key, evidence_row in existing_evidence.items():
                if key not in expected_keys:
                    db.delete(evidence_row)


def _effective_model_payload(model: TenderEvaluationModel) -> dict[str, Any]:
    effective_method = model.human_method or model.suggested_method
    effective_summary = model.human_summary or model.summary
    return {
        "suggested_method": model.suggested_method,
        "effective_method": effective_method,
        "review_status": model.review_status,
        "summary": effective_summary,
        "human_method": model.human_method,
        "human_summary": model.human_summary,
        "detector_version": model.detector_version,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _serialize_model_evidence(row: TenderEvaluationModelEvidence) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_document_id": row.source_document_id,
        "source_filename": row.source_document.original_filename if row.source_document else None,
        "source_page": row.source_page,
        "source_excerpt": row.source_excerpt,
        "evidence_role": row.evidence_role,
    }


def _effective_criterion_payload(row: EvaluationCriterion) -> dict[str, Any]:
    return {
        "criterion_type": row.human_criterion_type or row.criterion_type,
        "category": row.human_category if row.human_category is not None else row.category,
        "title": row.human_title or row.title,
        "criterion_text": row.human_criterion_text or row.criterion_text,
        "weight_value": row.human_weight_value if row.human_weight_value is not None else row.weight_value,
        "weight_unit": row.human_weight_unit if row.human_weight_unit is not None else row.weight_unit,
        "threshold_operator": row.human_threshold_operator if row.human_threshold_operator is not None else row.threshold_operator,
        "threshold_value": row.human_threshold_value if row.human_threshold_value is not None else row.threshold_value,
        "threshold_unit": row.human_threshold_unit if row.human_threshold_unit is not None else row.threshold_unit,
        "is_exclusionary": row.human_is_exclusionary if row.human_is_exclusionary is not None else row.is_exclusionary,
    }


def _serialize_criterion_evidence(row: EvaluationCriterionEvidence) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_document_id": row.source_document_id,
        "source_filename": row.source_document.original_filename if row.source_document else None,
        "source_page": row.source_page,
        "source_excerpt": row.source_excerpt,
        "evidence_role": row.evidence_role,
    }


def _serialize_criterion(row: EvaluationCriterion) -> dict[str, Any]:
    effective = _effective_criterion_payload(row)
    evidence = [_serialize_criterion_evidence(item) for item in row.evidence]
    return {
        "id": row.id,
        "tender_id": row.tender_id,
        "evaluation_model_id": row.evaluation_model_id,
        "semantic_key": row.semantic_key,
        "criterion_type": effective["criterion_type"],
        "category": effective["category"],
        "title": effective["title"],
        "criterion_text": effective["criterion_text"],
        "weight_value": effective["weight_value"],
        "weight_unit": effective["weight_unit"],
        "threshold_operator": effective["threshold_operator"],
        "threshold_value": effective["threshold_value"],
        "threshold_unit": effective["threshold_unit"],
        "is_exclusionary": effective["is_exclusionary"],
        "review_status": row.review_status,
        "detection_origin": row.detection_origin,
        "detector_version": row.detector_version,
        "source_document_id": row.source_document_id,
        "source_filename": row.source_document.original_filename if row.source_document else None,
        "source_page": row.source_page,
        "source_excerpt": row.source_excerpt,
        "human_criterion_type": row.human_criterion_type,
        "human_category": row.human_category,
        "human_title": row.human_title,
        "human_criterion_text": row.human_criterion_text,
        "human_weight_value": row.human_weight_value,
        "human_weight_unit": row.human_weight_unit,
        "human_threshold_operator": row.human_threshold_operator,
        "human_threshold_value": row.human_threshold_value,
        "human_threshold_unit": row.human_threshold_unit,
        "human_is_exclusionary": row.human_is_exclusionary,
        "human_note": row.human_note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "evidence": evidence,
    }


def get_tender_evaluation(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    model = (
        db.execute(
            select(TenderEvaluationModel)
            .where(TenderEvaluationModel.tender_id == tender_id)
            .options(
                selectinload(TenderEvaluationModel.evidence).selectinload(TenderEvaluationModelEvidence.source_document),
                selectinload(TenderEvaluationModel.criteria)
                .selectinload(EvaluationCriterion.evidence)
                .selectinload(EvaluationCriterionEvidence.source_document),
                selectinload(TenderEvaluationModel.criteria).selectinload(EvaluationCriterion.source_document),
            )
        )
        .scalars()
        .first()
    )

    if model is None:
        return {
            "tender_id": tender_id,
            "evaluation_version": EVALUATION_DETECTOR_VERSION,
            "generated_at": datetime.now(timezone.utc),
            "model": {
                "suggested_method": METHOD_UNKNOWN,
                "effective_method": METHOD_UNKNOWN,
                "review_status": REVIEW_SUGGESTED,
                "summary": "Sin analisis de evaluacion ejecutado.",
                "human_method": None,
                "human_summary": None,
                "detector_version": EVALUATION_DETECTOR_VERSION,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "evidence": [],
            },
            "criteria_summary": {
                "total": 0,
                "suggested": 0,
                "confirmed": 0,
                "rejected": 0,
                "exclusionary": 0,
                "scoring": 0,
                "gates": 0,
                "by_type": {},
                "by_category": {},
            },
            "criteria": [],
        }

    criteria_rows = sorted(
        model.criteria,
        key=lambda row: (
            (row.human_criterion_type or row.criterion_type),
            (row.human_category or row.category or ""),
            row.id,
        ),
    )

    by_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    counts = {REVIEW_SUGGESTED: 0, REVIEW_CONFIRMED: 0, REVIEW_REJECTED: 0}
    exclusionary = 0
    scoring = 0
    gates = 0

    serialized_criteria: list[dict[str, Any]] = []
    for row in criteria_rows:
        payload = _serialize_criterion(row)
        serialized_criteria.append(payload)

        ctype = payload["criterion_type"]
        category = payload["category"] or "UNCATEGORIZED"
        by_type[ctype] = by_type.get(ctype, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        counts[row.review_status] = counts.get(row.review_status, 0) + 1

        if payload["is_exclusionary"]:
            exclusionary += 1
        if ctype in {CRITERION_SCORING_COMPONENT, CRITERION_WEIGHTING, CRITERION_MINIMUM_SCORE}:
            scoring += 1
        if ctype == CRITERION_QUALIFICATION_GATE:
            gates += 1

    model_payload = _effective_model_payload(model)
    model_payload["evidence"] = [_serialize_model_evidence(item) for item in model.evidence]

    return {
        "tender_id": tender_id,
        "evaluation_version": EVALUATION_DETECTOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "model": model_payload,
        "criteria_summary": {
            "total": len(serialized_criteria),
            "suggested": counts.get(REVIEW_SUGGESTED, 0),
            "confirmed": counts.get(REVIEW_CONFIRMED, 0),
            "rejected": counts.get(REVIEW_REJECTED, 0),
            "exclusionary": exclusionary,
            "scoring": scoring,
            "gates": gates,
            "by_type": by_type,
            "by_category": by_category,
        },
        "criteria": serialized_criteria,
    }


def analyze_tender_evaluation(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    fragments = _extract_current_normalized_fragments(db, tender_id)

    detected_criteria_raw: list[DetectedCriterion] = []
    for fragment in fragments:
        detected_criteria_raw.extend(_detect_criteria_from_fragment(fragment))

    detected_criteria = _dedupe_criteria(detected_criteria_raw)
    direct_methods, direct_evidence = _direct_method_evidence(fragments)
    suggested_method = _derive_method(detected_criteria, direct_methods)

    model = (
        db.execute(
            select(TenderEvaluationModel)
            .where(TenderEvaluationModel.tender_id == tender_id)
            .options(
                selectinload(TenderEvaluationModel.evidence),
                selectinload(TenderEvaluationModel.criteria).selectinload(EvaluationCriterion.evidence),
            )
        )
        .scalars()
        .first()
    )

    if model is None:
        model = TenderEvaluationModel(
            tender_id=tender_id,
            suggested_method=suggested_method,
            review_status=REVIEW_SUGGESTED,
            summary=_build_model_summary(suggested_method, detected_criteria),
            detector_version=EVALUATION_DETECTOR_VERSION,
        )
        db.add(model)
        db.flush()
    else:
        mutable_model = model.review_status == REVIEW_SUGGESTED and not _model_has_human_override(model)
        if mutable_model:
            model.suggested_method = suggested_method
            model.summary = _build_model_summary(suggested_method, detected_criteria)
            model.detector_version = EVALUATION_DETECTOR_VERSION

    model_mutable = model.review_status == REVIEW_SUGGESTED and not _model_has_human_override(model)

    evidence_pool = list(direct_evidence)
    for item in detected_criteria:
        evidence_pool.extend(item.evidence or [DetectedEvidence(item.source_document_id, item.source_page, item.source_excerpt, item.evidence_role)])

    _reconcile_model_evidence(db, model, evidence_pool, mutable=model_mutable)
    _reconcile_criteria(db, tender_id, model, detected_criteria)

    db.flush()
    db.expire_all()
    return get_tender_evaluation(db, tender_id)


def update_tender_evaluation_model_human_decision(
    db: Session,
    tender_id: str,
    action: str,
    *,
    method: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    model = (
        db.execute(select(TenderEvaluationModel).where(TenderEvaluationModel.tender_id == tender_id))
        .scalars()
        .first()
    )
    if model is None:
        raise ValueError("Evaluation model not found. Run analyze-evaluation first.")

    normalized_action = action.strip().upper()
    if normalized_action == ACTION_CONFIRM:
        model.review_status = REVIEW_CONFIRMED
    elif normalized_action == ACTION_REJECT:
        model.review_status = REVIEW_REJECTED
    elif normalized_action == ACTION_RESET:
        model.review_status = REVIEW_SUGGESTED
        model.human_method = None
        model.human_summary = None
    elif normalized_action == ACTION_OVERRIDE:
        model.review_status = REVIEW_CONFIRMED
        if method is not None:
            candidate = method.strip().upper()
            model.human_method = candidate or None
        if summary is not None:
            model.human_summary = summary.strip() or None
    else:
        raise ValueError(f"Unsupported action: {action}")

    db.flush()
    return get_tender_evaluation(db, tender_id)


def update_evaluation_criterion_human_decision(
    db: Session,
    tender_id: str,
    criterion_id: str,
    action: str,
    *,
    criterion_type: str | None = None,
    category: str | None = None,
    title: str | None = None,
    criterion_text: str | None = None,
    weight_value: float | None = None,
    weight_unit: str | None = None,
    threshold_operator: str | None = None,
    threshold_value: float | None = None,
    threshold_unit: str | None = None,
    is_exclusionary: bool | None = None,
    human_note: str | None = None,
) -> dict[str, Any]:
    row = db.get(EvaluationCriterion, criterion_id)
    if row is None or row.tender_id != tender_id:
        raise ValueError("Evaluation criterion not found")

    normalized_action = action.strip().upper()
    if normalized_action == ACTION_CONFIRM:
        row.review_status = REVIEW_CONFIRMED
    elif normalized_action == ACTION_REJECT:
        row.review_status = REVIEW_REJECTED
    elif normalized_action == ACTION_RESET:
        row.review_status = REVIEW_SUGGESTED
        row.human_criterion_type = None
        row.human_category = None
        row.human_title = None
        row.human_criterion_text = None
        row.human_weight_value = None
        row.human_weight_unit = None
        row.human_threshold_operator = None
        row.human_threshold_value = None
        row.human_threshold_unit = None
        row.human_is_exclusionary = None
        row.human_note = None
    elif normalized_action == ACTION_OVERRIDE:
        row.review_status = REVIEW_CONFIRMED
        if criterion_type is not None:
            row.human_criterion_type = criterion_type.strip().upper() or None
        if category is not None:
            row.human_category = category.strip().upper() or None
        if title is not None:
            row.human_title = title.strip() or None
        if criterion_text is not None:
            row.human_criterion_text = criterion_text.strip() or None
        if weight_value is not None:
            row.human_weight_value = weight_value
        if weight_unit is not None:
            row.human_weight_unit = weight_unit.strip().upper() or None
        if threshold_operator is not None:
            row.human_threshold_operator = threshold_operator.strip().upper() or None
        if threshold_value is not None:
            row.human_threshold_value = threshold_value
        if threshold_unit is not None:
            row.human_threshold_unit = threshold_unit.strip().upper() or None
        if is_exclusionary is not None:
            row.human_is_exclusionary = is_exclusionary
        if human_note is not None:
            row.human_note = human_note
    else:
        raise ValueError(f"Unsupported action: {action}")

    db.flush()
    return get_tender_evaluation(db, tender_id)
