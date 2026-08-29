from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DocumentClassification, DocumentPage, NormalizedContent, RequirementCandidate, RequirementCandidateEvidence, Tender, TenderDocument

REQUIREMENT_DETECTOR_VERSION = "mvp-04.2"

REVIEW_SUGGESTED = "SUGGESTED"
REVIEW_CONFIRMED = "CONFIRMED"
REVIEW_REJECTED = "REJECTED"

ORIGIN_DETERMINISTIC = "DETERMINISTIC"

BIDDER_ACTOR_RE = re.compile(
    r"\b(?:el|la|los|las)?\s*(participante|licitante|oferente|interesado|persona participante|consorcio|propuesta|proposici(?:on|[oó]n)|oferta|personal propuesto|bienes ofertados|servicios ofertados)\b",
    re.IGNORECASE,
)
AUTHORITY_ACTOR_RE = re.compile(
    r"\b(?:el|la|los|las)?\s*(convocante|contratante|[aá]rea contratante|[aá]rea requirente|[aá]rea usuaria|entidad contratante|dependencia|entidad|autoridad contratante|comprador|supervisor|residente|administrador del contrato|sociedad|comit[eé])\b",
    re.IGNORECASE,
)
POST_AWARD_ACTOR_RE = re.compile(
    r"\b(?:el|la)?\s*(participante\s+adjudicado|proveedor(?:\s+adjudicado)?|contratista|prestador(?:\s+del\s+servicio|\s+de\s+servicios)?|adjudicatario|adjudicado)\b",
    re.IGNORECASE,
)
POST_AWARD_CONTEXT_RE = re.compile(
    r"\b(durante\s+la\s+ejecuci(?:on|[oó]n)|ejecuci(?:on|[oó]n)\s+del\s+contrato|una\s+vez\s+adjudicado|posterior(?:es)?\s+a\s+la\s+firma|firma\s+del\s+contrato|inicio\s+de\s+los\s+servicios|entregar\s+reportes?\s+mensuales|vigencia\s+del\s+contrato|administraci(?:on|[oó]n)\s+del\s+contrato|durante\s+la\s+prestaci(?:on|[oó]n)\s+de\s+los\s+servicios|a\s+partir\s+de\s+la\s+firma\s+del\s+contrato|despu[eé]s\s+de\s+la\s+firma|previo\s+a\s+la\s+firma\s+del\s+contrato|posteriores?\s+a\s+la\s+fecha\s+de\s+notificaci(?:on|[oó]n)\s+del\s+fallo)\b",
    re.IGNORECASE,
)
POST_AWARD_RESULT_RE = re.compile(
    r"\b(resulte\s+adjudicad[oa]|resulte\s+ganadora|que\s+resulte\s+adjudicado|previo\s+a\s+la\s+fecha\s+de\s+formalizaci(?:on|[oó]n)\s+del\s+contrato|formalizaci(?:on|[oó]n)\s+del\s+contrato|contrato\s+deber[aá]\s+ser\s+firmado|ser\s+firmado\s+por\s+el\s+representante|previo\s+a\s+la\s+firma\s+del\s+contrato|participante\s+adjudicado|[uú]nicamente\s+lo\s+presentar[aá]\s+el\s+adjudicado|documentaci(?:on|[oó]n)\s+requerida\s+para\s+la\s+formalizaci(?:on|[oó]n)\s+del\s+contrato)\b",
    re.IGNORECASE,
)
BIDDER_CONTEXT_RE = re.compile(
    r"\b(participante|licitante|oferente|interesado|propuesta|proposici(?:on|[oó]n)|oferta|documentaci(?:on|[oó]n)\s+(?:legal|administrativa|t[eé]cnica|econ[oó]mica)|personal\s+propuesto|bienes\s+ofertados|servicios\s+ofertados|acto\s+de\s+presentaci(?:on|[oó]n))\b",
    re.IGNORECASE,
)
PROPOSAL_STAGE_RE = re.compile(
    r"\b(con\s+su\s+propuesta|como\s+parte\s+de\s+la\s+propuesta|como\s+parte\s+de\s+su\s+propuesta|en\s+su\s+propuesta\s+(?:t[eé]cnica|econ[oó]mica|comercial|administrativa)|en\s+la\s+propuesta\s+(?:t[eé]cnica|econ[oó]mica|comercial|administrativa)|integrarse\s+como\s+parte\s+de\s+la\s+propuesta|integrar\s+su\s+propuesta|para\s+la\s+elaboraci(?:on|[oó]n)\s+de\s+su\s+propuesta|presentaci(?:on|[oó]n)\s+y\s+apertura\s+de\s+propuestas|durante\s+el\s+procedimiento\s+de\s+contrataci(?:on|[oó]n)|manifestar\s+su\s+inter[eé]s\s+en\s+participar)\b",
    re.IGNORECASE,
)
STRONG_MODALITY_PATTERNS = [
    re.compile(r"\bno\s+se\s+aceptar[aá]n?\b", re.IGNORECASE),
    re.compile(r"\bno\s+se\s+admitir[aá]n?\b", re.IGNORECASE),
    re.compile(r"\bno\s+deber[aá]n?\b", re.IGNORECASE),
    re.compile(r"\bno\s+podr[aá]n\b", re.IGNORECASE),
    re.compile(r"\bdeber[aá]n?\b", re.IGNORECASE),
    re.compile(r"\btendr[aá]n?\s+que\b", re.IGNORECASE),
    re.compile(r"\bse\s+requiere\b", re.IGNORECASE),
    re.compile(r"\bse\s+requerir[aá]\b", re.IGNORECASE),
    re.compile(r"\bser[aá]\s+requisito\b", re.IGNORECASE),
    re.compile(r"\bes\s+requisito\b", re.IGNORECASE),
    re.compile(r"\bquedar[aá]\s+obligad[oa]s?\b", re.IGNORECASE),
]
DIRECT_BIDDER_VERB_RE = re.compile(
    r"\b(?:el|la|los|las)?\s*(participante|licitante|oferente|interesado|propuesta|proposici(?:on|[oó]n)|oferta|personal propuesto)\b[^\.;:]{0,80}\b(presentar[aá]n?|adjuntar[aá]n?|anexar[aá]n?|incluir[aá]n?|acreditar[aá]n?|entregar[aá]n?|contar[aá]n?|cumplir[aá]n?)\b",
    re.IGNORECASE,
)
DIRECT_IMPERATIVE_START_RE = re.compile(
    r"^(presentar|adjuntar|anexar|incluir|firmar|acreditar|entregar|integrar|requisitar)\b",
    re.IGNORECASE,
)
IMPERATIVE_AFTER_SEPARATOR_RE = re.compile(
    r"(?::|;|•)\s*(presentar|adjuntar|anexar|incluir|firmar|acreditar|entregar|integrar|requisitar)\b",
    re.IGNORECASE,
)
REJECTION_CAUSE_RE = re.compile(
    r"\b(causa\s+de\s+desechamiento|motivo\s+de\s+rechazo|ser[aá]\s+causa\s+de\s+desechamiento|ser[aá]\s+motivo\s+de\s+rechazo|se\s+desechar[aá]|ser[aá]\s+desechad[ao])\b",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"(\[[^\]]{1,80}\]|escriba\s+aqu[ií]|seleccione\s+una\s+opci[oó]n|campo\s+en\s+blanco)", re.IGNORECASE)
REFERENCE_ONLY_RE = re.compile(r"^(v[eé]ase|ver|conforme\s+a|seg[uú]n\s+lo\s+previsto\s+en)\b", re.IGNORECASE)
DEFINITION_RE = re.compile(r"\b(se\s+entender[aá]\s+por|para\s+efectos\s+de\s+la\s+presente\s+convocatoria)\b", re.IGNORECASE)
TABLE_OF_CONTENTS_RE = re.compile(r"\b(indice|contenido|tabla\s+de\s+contenido)\b", re.IGNORECASE)
CONTRACT_CLASSIFICATION_RE = re.compile(r"\b(CONTRACT|AGREEMENT|TERMS|CONDITIONS|GENERAL_TERMS|CONTRACT_DRAFT)\b")
FORM_FILLING_RE = re.compile(
    r"\b(dejando\s+solo\s+la\s+opci[oó]n\s+seleccionada|eliminar\s+los\s+textos\s+marcados|seleccionar\s+una\s+de\s+las\s+\d+\s+opciones|al\s+tenor\s+de\s+las\s+siguientes\s+consideraciones|en\s+lo\s+sucesivo\s+se\s+le\s+denominar[aá])\b",
    re.IGNORECASE,
)
FORM_TEMPLATE_PAGE_RE = re.compile(
    r"\(en\s+papel\s+membretado|protesto\s+lo\s+necesario|fecha:\s*xx|\[nombre\s+y\s+firma|manifiesto\s+bajo\s+protesta|declaro\s+bajo\s+protesta",
    re.IGNORECASE,
)
INTERNAL_FORM_INSTRUCTION_RE = re.compile(
    r"\b(siguiente\s+manifestaci(?:on|[oó]n)|presente\s+documento\s+deber[aá]\s+entregarse\s+debidamente\s+requisitado|se\s+deber[aá]\s+adjuntar,?\s+para\s+cada\s+uno\s+de\s+los\s+integrantes\s+del\s+consorcio)\b",
    re.IGNORECASE,
)
CHECKLIST_CONTEXT_RE = re.compile(
    r"\b(documentos?\s+que\s+deber[aá]n?\s+presentar|documentaci(?:on|[oó]n)\s+requerida|se\s+verificar[aá]\s+que|requisitos?\s+y\s+criterios|como\s+parte\s+de\s+la\s+propuesta|integrar\s+su\s+propuesta)\b",
    re.IGNORECASE,
)
STRONG_POST_AWARD_PAGE_RE = re.compile(
    r"\b([uú]nicamente\s+lo\s+presentar[aá]\s+el\s+adjudicado|documentaci(?:on|[oó]n)\s+requerida\s+para\s+la\s+formalizaci(?:on|[oó]n)\s+del\s+contrato|participante\s+adjudicado|previo\s+a\s+la\s+fecha\s+de\s+formalizaci(?:on|[oó]n)\s+del\s+contrato|previo\s+a\s+la\s+firma\s+del\s+contrato)\b",
    re.IGNORECASE,
)


@dataclass
class SourceBlock:
    source_document_id: str
    source_filename: str
    source_page: int | None
    document_page_id: str
    normalized_content_id: str
    classification_type: str | None
    source_type: str
    text: str
    page_text: str


@dataclass
class DetectedRequirementEvidence:
    source_document_id: str
    source_page: int | None
    document_page_id: str | None
    normalized_content_id: str | None
    source_excerpt: str


@dataclass
class DetectedRequirementCandidate:
    semantic_key: str
    requirement_text: str
    actor_text: str | None
    modality_text: str | None
    source_document_id: str
    source_page: int | None
    source_excerpt: str
    document_page_id: str | None
    normalized_content_id: str | None
    evidence: list[DetectedRequirementEvidence] = field(default_factory=list)


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_space(text: str) -> str:
    return " ".join((text or "").replace("\r", "\n").split())


def _normalize_for_key(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents((text or "").lower())).strip()


def _excerpt(text: str, limit: int = 1200) -> str:
    value = _normalize_space(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _split_blocks(text: str) -> list[str]:
    lines = text.replace("\r", "\n").split("\n")
    blocks: list[str] = []
    current: list[str] = []
    context_prefix = ""

    def has_requirement_anchor(value: str) -> bool:
        compact = _normalize_space(value)
        if not compact:
            return False
        if _extract_modality_match(compact):
            return True
        return bool(DIRECT_IMPERATIVE_START_RE.match(compact))

    def is_garbled_line(value: str) -> bool:
        compact = _normalize_space(value)
        if not compact:
            return True
        if len(compact) <= 3:
            return True
        isolated_tokens = len(re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚ]\b", compact))
        alphabetic = len(re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", compact))
        if isolated_tokens >= 4 and alphabetic <= 18:
            return True
        if alphabetic == 0 and len(compact) < 12:
            return True
        return False

    for raw_line in lines:
        clean_line = _normalize_space(raw_line)
        if not clean_line:
            if current:
                blocks.append(" ".join(current))
                current = []
            context_prefix = ""
            continue

        if is_garbled_line(clean_line):
            continue

        if CHECKLIST_CONTEXT_RE.search(clean_line) and clean_line.endswith(":"):
            if current:
                blocks.append(" ".join(current))
                current = []
            context_prefix = clean_line
            continue

        if DIRECT_IMPERATIVE_START_RE.match(clean_line) and context_prefix:
            if current:
                blocks.append(" ".join(current))
            current = [context_prefix, clean_line]
            context_prefix = ""
            continue

        if re.match(r"^(?:[-•*✓]|\d+[\.)]|[A-Za-z][\.)]|[IVXLCDM]+\.)\s*", clean_line) and current:
            blocks.append(" ".join(current))
            current = []

        if current and has_requirement_anchor(clean_line) and any(has_requirement_anchor(line) for line in current):
            blocks.append(" ".join(current))
            current = []

        if context_prefix and not current:
            current.append(context_prefix)
            context_prefix = ""

        current.append(clean_line)

    if current:
        blocks.append(" ".join(current))

    spans: list[str] = []
    for block in blocks:
        clean_block = _normalize_space(block)
        if len(clean_block) < 20:
            continue

        sentence_candidates = re.split(r"(?<=[\.;])\s+", clean_block)
        useful_sentences = [candidate for candidate in sentence_candidates if len(_normalize_space(candidate)) >= 20]
        if len(useful_sentences) <= 1:
            spans.append(clean_block)
            continue

        for sentence in useful_sentences:
            spans.append(_normalize_space(sentence))

    return spans


def _extract_actor_text(text: str) -> str | None:
    for pattern in (BIDDER_ACTOR_RE, AUTHORITY_ACTOR_RE, POST_AWARD_ACTOR_RE):
        match = pattern.search(text)
        if match:
            return _normalize_space(match.group(0))
    return None


def _extract_modality_match(text: str) -> re.Match[str] | None:
    separated_imperative = IMPERATIVE_AFTER_SEPARATOR_RE.search(text)
    if separated_imperative:
        return separated_imperative

    matches: list[re.Match[str]] = []
    for pattern in STRONG_MODALITY_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append(match)

    direct = DIRECT_BIDDER_VERB_RE.search(text)
    if direct:
        matches.append(direct)

    rejection = REJECTION_CAUSE_RE.search(text)
    if rejection:
        matches.append(rejection)

    imperative = DIRECT_IMPERATIVE_START_RE.search(text)
    if imperative:
        matches.append(imperative)

    if not matches:
        return None
    return sorted(matches, key=lambda item: item.start())[0]


def _modality_text(match: re.Match[str]) -> str:
    compact = _normalize_space(match.group(0))
    direct_verb = re.search(r"\b(presentar(?:[aá]n?)?|adjuntar(?:[aá]n?)?|anexar(?:[aá]n?)?|incluir(?:[aá]n?)?|acreditar(?:[aá]n?)?|entregar(?:[aá]n?)?|integrar|requisitar|firmar|contar(?:[aá]n?)?|cumplir(?:[aá]n?)?)\b", compact, re.IGNORECASE)
    if direct_verb:
        return _normalize_space(direct_verb.group(0))
    return compact


def _starts_with_authority_subject(text: str) -> bool:
    compact = _normalize_space(text)
    return bool(AUTHORITY_ACTOR_RE.match(compact) or POST_AWARD_ACTOR_RE.match(compact))


def _is_contract_like(classification_type: str | None) -> bool:
    if not classification_type:
        return False
    return bool(CONTRACT_CLASSIFICATION_RE.search(classification_type))


def _is_noise_span(text: str) -> bool:
    normalized = _normalize_space(text)
    if len(normalized) < 20:
        return True
    if normalized.endswith(":") and CHECKLIST_CONTEXT_RE.search(normalized):
        return True
    if PLACEHOLDER_RE.search(normalized):
        return True
    if FORM_FILLING_RE.search(normalized):
        return True
    if DEFINITION_RE.search(normalized):
        return True
    if TABLE_OF_CONTENTS_RE.search(normalized) and not _extract_modality_match(normalized):
        return True
    if REFERENCE_ONLY_RE.search(normalized) and not _extract_modality_match(normalized):
        return True
    return False


def _is_bidder_relevant(text: str, block_text: str) -> bool:
    return bool(BIDDER_ACTOR_RE.search(text) or BIDDER_CONTEXT_RE.search(text) or BIDDER_CONTEXT_RE.search(block_text))


def _is_post_award_only(text: str) -> bool:
    has_post_award_actor = bool(POST_AWARD_ACTOR_RE.search(text))
    has_post_award_context = bool(POST_AWARD_CONTEXT_RE.search(text))
    has_bidder_actor = bool(BIDDER_ACTOR_RE.search(text))
    return (has_post_award_actor or has_post_award_context) and not has_bidder_actor


def _has_authority_or_post_award_subject_near_modality(text: str, modality_match: re.Match[str]) -> bool:
    start = max(0, modality_match.start() - 100)
    prefix = text[start:modality_match.start()]
    return bool(AUTHORITY_ACTOR_RE.search(prefix) or POST_AWARD_ACTOR_RE.search(prefix))


def _is_post_award_requirement_form(text: str, modality_match: re.Match[str]) -> bool:
    if not POST_AWARD_RESULT_RE.search(text):
        return False
    award_match = POST_AWARD_RESULT_RE.search(text)
    if award_match is None:
        return False
    return award_match.start() <= modality_match.start()


def _has_proposal_stage_context(text: str, page_text: str) -> bool:
    return bool(PROPOSAL_STAGE_RE.search(text) or PROPOSAL_STAGE_RE.search(page_text))


def _has_inline_proposal_stage_context(text: str) -> bool:
    return bool(PROPOSAL_STAGE_RE.search(text))


def _is_internal_form_instruction(text: str, page_text: str) -> bool:
    if not INTERNAL_FORM_INSTRUCTION_RE.search(text):
        return False
    return bool(FORM_TEMPLATE_PAGE_RE.search(page_text))


def _page_is_post_award_only(page_text: str) -> bool:
    return bool(POST_AWARD_RESULT_RE.search(page_text) or POST_AWARD_CONTEXT_RE.search(page_text)) and not PROPOSAL_STAGE_RE.search(page_text)


def _page_is_strong_post_award_only(page_text: str) -> bool:
    return bool(STRONG_POST_AWARD_PAGE_RE.search(page_text))


def _is_checklist_supported_imperative(text: str, page_text: str) -> bool:
    return bool(DIRECT_IMPERATIVE_START_RE.match(text) and CHECKLIST_CONTEXT_RE.search(page_text))


def _is_pre_award_exception(text: str, modality_match: re.Match[str]) -> bool:
    award_match = POST_AWARD_RESULT_RE.search(text)
    if award_match is None:
        return False
    if award_match.start() <= modality_match.start():
        return False
    if not BIDDER_ACTOR_RE.search(text):
        return False
    return bool(re.search(r"\b(acreditar|presentar|manifestar|comprometer|contar)\b", text[: award_match.start() + 1], re.IGNORECASE))


def _contains_multiple_requirement_anchors(text: str) -> bool:
    hits = 0
    for pattern in STRONG_MODALITY_PATTERNS:
        hits += len(pattern.findall(text))
    hits += len(DIRECT_BIDDER_VERB_RE.findall(text))
    hits += len(DIRECT_IMPERATIVE_START_RE.findall(text))
    return hits >= 2


def _text_quality_score(text: str) -> tuple[int, int, int, int]:
    compact = _normalize_space(text)
    weird_char_penalty = len(re.findall(r"[|¢�]", compact))
    isolated_tokens = len(re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚ]\b", compact[:80]))
    placeholder_penalty = 1 if PLACEHOLDER_RE.search(compact) else 0
    alphabetic = len(re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", compact))
    return (placeholder_penalty, weird_char_penalty, isolated_tokens, -alphabetic)


def _starts_with_ocr_noise(text: str) -> bool:
    compact = _normalize_space(text)
    prefix = compact[:40]
    if prefix.startswith(("|", "✓", "we ", "n ", "y ")):
        return True
    return len(re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚ]\b", prefix)) >= 4


def _similarity_score(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, _normalize_for_key(left), _normalize_for_key(right)).ratio()


def _has_substantive_tail(text: str, modality_match: re.Match[str]) -> bool:
    tail = _normalize_space(text[modality_match.end() :]).strip(" :-,.;")
    return len(tail) >= 8


def _build_semantic_key(tender_id: str, block: SourceBlock, requirement_text: str) -> str:
    payload = "|".join(
        [
            tender_id,
            block.source_document_id,
            str(block.source_page or ""),
            block.document_page_id,
            _normalize_for_key(requirement_text),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _detect_requirement_from_span(tender_id: str, block: SourceBlock, span: str, block_text: str) -> DetectedRequirementCandidate | None:
    text = _normalize_space(span)
    if _is_noise_span(text):
        return None

    modality_match = _extract_modality_match(text)
    if modality_match is None:
        return None

    bidder_relevant = _is_bidder_relevant(text, block_text)
    rejection_cause = bool(REJECTION_CAUSE_RE.search(text))
    proposal_stage = _has_proposal_stage_context(text, block.page_text)
    inline_proposal_stage = _has_inline_proposal_stage_context(text)
    checklist_supported = _is_checklist_supported_imperative(text, block.page_text)
    pre_award_exception = _is_pre_award_exception(text, modality_match)
    imperative_without_subject = bool(DIRECT_IMPERATIVE_START_RE.match(text) and text[:1].islower())

    if _starts_with_authority_subject(text):
        return None
    if imperative_without_subject:
        return None
    if _has_authority_or_post_award_subject_near_modality(text, modality_match):
        return None
    if _is_post_award_only(text):
        return None
    if _is_post_award_requirement_form(text, modality_match) and not inline_proposal_stage and not pre_award_exception:
        return None
    if _page_is_strong_post_award_only(block.page_text) and not inline_proposal_stage and not pre_award_exception:
        return None
    if _page_is_post_award_only(block.page_text) and not inline_proposal_stage and not pre_award_exception:
        return None
    if _is_internal_form_instruction(text, block.page_text):
        return None
    if _is_contract_like(block.classification_type) and not bidder_relevant and not rejection_cause:
        return None
    if not rejection_cause and not bidder_relevant and not checklist_supported:
        return None
    if not rejection_cause and not _has_substantive_tail(text, modality_match):
        return None

    requirement_text = _excerpt(text)
    modality_text = _modality_text(modality_match)
    actor_text = _extract_actor_text(text)
    semantic_key = _build_semantic_key(tender_id, block, requirement_text)
    evidence = DetectedRequirementEvidence(
        source_document_id=block.source_document_id,
        source_page=block.source_page,
        document_page_id=block.document_page_id,
        normalized_content_id=block.normalized_content_id,
        source_excerpt=requirement_text,
    )
    return DetectedRequirementCandidate(
        semantic_key=semantic_key,
        requirement_text=requirement_text,
        actor_text=actor_text,
        modality_text=modality_text,
        source_document_id=block.source_document_id,
        source_page=block.source_page,
        source_excerpt=requirement_text,
        document_page_id=block.document_page_id,
        normalized_content_id=block.normalized_content_id,
        evidence=[evidence],
    )


def _extract_current_requirement_blocks(db: Session, tender_id: str) -> list[SourceBlock]:
    rows = db.execute(
        select(
            TenderDocument.id,
            TenderDocument.original_filename,
            DocumentPage.id,
            DocumentPage.page_number,
            NormalizedContent.id,
            NormalizedContent.normalized_text,
            NormalizedContent.source_type,
            DocumentClassification.human_type,
            DocumentClassification.suggested_type,
        )
        .join(DocumentPage, DocumentPage.document_id == TenderDocument.id)
        .join(NormalizedContent, NormalizedContent.document_page_id == DocumentPage.id)
        .outerjoin(DocumentClassification, DocumentClassification.document_id == TenderDocument.id)
        .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
        .order_by(TenderDocument.original_filename.asc(), DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
    ).all()

    dedup: dict[tuple[str, str], SourceBlock] = {}
    for doc_id, filename, page_id, page_number, normalized_content_id, normalized_text, source_type, human_type, suggested_type in rows:
        text_value = (normalized_text or "").strip()
        if not text_value:
            continue

        classification_type = human_type or suggested_type
        source_rank = 0 if source_type == "NATIVE_PDF" else 1
        for span in _split_blocks(text_value):
            key = (page_id, hashlib.sha256(_normalize_for_key(span).encode("utf-8")).hexdigest())
            candidate = SourceBlock(
                source_document_id=doc_id,
                source_filename=filename,
                source_page=page_number,
                document_page_id=page_id,
                normalized_content_id=normalized_content_id,
                classification_type=classification_type,
                source_type=source_type,
                text=span,
                page_text=text_value,
            )
            existing = dedup.get(key)
            if existing is None:
                dedup[key] = candidate
                continue
            existing_rank = 0 if existing.source_type == "NATIVE_PDF" else 1
            if source_rank < existing_rank:
                dedup[key] = candidate

    return sorted(dedup.values(), key=lambda item: (item.source_filename.lower(), item.source_page or 0, item.text))


def _merge_detected_candidates(detected: list[DetectedRequirementCandidate]) -> list[DetectedRequirementCandidate]:
    by_key: dict[str, DetectedRequirementCandidate] = {}
    for item in detected:
        existing = by_key.get(item.semantic_key)
        if existing is None:
            by_key[item.semantic_key] = item
            continue

        evidence_seen = {
            (e.source_document_id, e.source_page, hashlib.sha256(e.source_excerpt.encode("utf-8")).hexdigest())
            for e in existing.evidence
        }
        for evidence in item.evidence:
            evidence_key = (
                evidence.source_document_id,
                evidence.source_page,
                hashlib.sha256(evidence.source_excerpt.encode("utf-8")).hexdigest(),
            )
            if evidence_key not in evidence_seen:
                existing.evidence.append(evidence)
                evidence_seen.add(evidence_key)
    return sorted(by_key.values(), key=lambda item: (item.source_document_id, item.source_page or 0, item.requirement_text))


def _prune_page_level_noise(detected: list[DetectedRequirementCandidate]) -> list[DetectedRequirementCandidate]:
    by_page: dict[tuple[str, int | None], list[DetectedRequirementCandidate]] = {}
    for item in detected:
        by_page.setdefault((item.source_document_id, item.source_page), []).append(item)

    pruned: list[DetectedRequirementCandidate] = []
    for page_items in by_page.values():
        suppressed: set[str] = set()
        normalized_texts = {item.semantic_key: _normalize_for_key(item.requirement_text) for item in page_items}

        for candidate in page_items:
            if candidate.semantic_key in suppressed:
                continue
            current_norm = normalized_texts[candidate.semantic_key]
            for other in page_items:
                if candidate.semantic_key == other.semantic_key or other.semantic_key in suppressed:
                    continue
                other_norm = normalized_texts[other.semantic_key]
                if _normalize_for_key(candidate.modality_text) != _normalize_for_key(other.modality_text):
                    continue
                if current_norm == other_norm:
                    if _text_quality_score(candidate.requirement_text) > _text_quality_score(other.requirement_text):
                        suppressed.add(candidate.semantic_key)
                    else:
                        suppressed.add(other.semantic_key)
                    continue
                if current_norm in other_norm and len(current_norm) >= 80 and _contains_multiple_requirement_anchors(other.requirement_text):
                    suppressed.add(other.semantic_key)
                elif other_norm in current_norm and len(other_norm) >= 80 and _contains_multiple_requirement_anchors(candidate.requirement_text):
                    suppressed.add(candidate.semantic_key)
                elif _similarity_score(candidate.requirement_text, other.requirement_text) >= 0.82:
                    if _text_quality_score(candidate.requirement_text) > _text_quality_score(other.requirement_text):
                        suppressed.add(candidate.semantic_key)
                    else:
                        suppressed.add(other.semantic_key)
                elif _starts_with_ocr_noise(candidate.requirement_text) or _starts_with_ocr_noise(other.requirement_text):
                    if _similarity_score(candidate.requirement_text, other.requirement_text) >= 0.65:
                        if _text_quality_score(candidate.requirement_text) > _text_quality_score(other.requirement_text):
                            suppressed.add(candidate.semantic_key)
                        else:
                            suppressed.add(other.semantic_key)

        pruned.extend(item for item in page_items if item.semantic_key not in suppressed)

    return sorted(pruned, key=lambda item: (item.source_document_id, item.source_page or 0, item.requirement_text))


def _detect_requirement_candidates(db: Session, tender_id: str) -> list[DetectedRequirementCandidate]:
    detected: list[DetectedRequirementCandidate] = []
    for block in _extract_current_requirement_blocks(db, tender_id):
        candidate = _detect_requirement_from_span(tender_id, block, block.text, block.text)
        if candidate is not None:
            detected.append(candidate)
    return _merge_detected_candidates(_prune_page_level_noise(detected))


def _sync_evidence(candidate: RequirementCandidate, detected: DetectedRequirementCandidate) -> None:
    existing_by_key = {
        (row.source_document_id, row.source_page, row.excerpt_sha256): row for row in candidate.evidence
    }
    detected_keys: set[tuple[str, int | None, str]] = set()

    for evidence in detected.evidence:
        excerpt_sha = hashlib.sha256(evidence.source_excerpt.encode("utf-8")).hexdigest()
        key = (evidence.source_document_id, evidence.source_page, excerpt_sha)
        detected_keys.add(key)
        current = existing_by_key.get(key)
        if current is None:
            candidate.evidence.append(
                RequirementCandidateEvidence(
                    source_document_id=evidence.source_document_id,
                    source_page=evidence.source_page,
                    source_excerpt=evidence.source_excerpt,
                    excerpt_sha256=excerpt_sha,
                    document_page_id=evidence.document_page_id,
                    normalized_content_id=evidence.normalized_content_id,
                )
            )
            continue

        current.source_excerpt = evidence.source_excerpt
        current.document_page_id = evidence.document_page_id
        current.normalized_content_id = evidence.normalized_content_id

    for row in list(candidate.evidence):
        key = (row.source_document_id, row.source_page, row.excerpt_sha256)
        if key not in detected_keys:
            candidate.evidence.remove(row)


def _serialize_evidence(item: RequirementCandidateEvidence) -> dict[str, Any]:
    source_document = item.source_document
    return {
        "id": item.id,
        "source_document_id": item.source_document_id,
        "source_filename": source_document.original_filename if source_document else None,
        "source_page": item.source_page,
        "source_excerpt": item.source_excerpt,
        "document_page_id": item.document_page_id,
        "normalized_content_id": item.normalized_content_id,
    }


def _serialize_candidate(item: RequirementCandidate) -> dict[str, Any]:
    source_document = item.source_document
    return {
        "id": item.id,
        "tender_id": item.tender_id,
        "semantic_key": item.semantic_key,
        "requirement_text": item.requirement_text,
        "actor_text": item.actor_text,
        "modality_text": item.modality_text,
        "review_status": item.review_status,
        "detection_origin": item.detection_origin,
        "detector_version": item.detector_version,
        "source_document_id": item.source_document_id,
        "source_filename": source_document.original_filename if source_document else None,
        "source_page": item.source_page,
        "source_excerpt": item.source_excerpt,
        "document_page_id": item.document_page_id,
        "normalized_content_id": item.normalized_content_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "evidence": [_serialize_evidence(evidence) for evidence in sorted(item.evidence, key=lambda row: (row.source_page or 0, row.id))],
    }


def _build_summary(items: list[RequirementCandidate]) -> dict[str, Any]:
    by_modality: dict[str, int] = {}
    documents_with_candidates = {item.source_document_id for item in items}
    pages_with_candidates = {(item.source_document_id, item.source_page) for item in items}
    explicit_actor_count = 0
    suggested = 0
    confirmed = 0
    rejected = 0

    for item in items:
        if item.actor_text:
            explicit_actor_count += 1
        if item.modality_text:
            by_modality[item.modality_text] = by_modality.get(item.modality_text, 0) + 1
        if item.review_status == REVIEW_CONFIRMED:
            confirmed += 1
        elif item.review_status == REVIEW_REJECTED:
            rejected += 1
        else:
            suggested += 1

    return {
        "total": len(items),
        "suggested": suggested,
        "confirmed": confirmed,
        "rejected": rejected,
        "documents_with_candidates": len(documents_with_candidates),
        "pages_with_candidates": len(pages_with_candidates),
        "explicit_actor_count": explicit_actor_count,
        "by_modality": dict(sorted(by_modality.items())),
    }


def get_tender_requirement_candidates(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    rows = db.execute(
        select(RequirementCandidate)
        .options(
            selectinload(RequirementCandidate.source_document),
            selectinload(RequirementCandidate.evidence).selectinload(RequirementCandidateEvidence.source_document),
        )
        .where(RequirementCandidate.tender_id == tender_id)
        .order_by(RequirementCandidate.source_document_id.asc(), RequirementCandidate.source_page.asc(), RequirementCandidate.created_at.asc())
    ).scalars().all()

    return {
        "tender_id": tender_id,
        "requirements_version": REQUIREMENT_DETECTOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "summary": _build_summary(rows),
        "candidates": [_serialize_candidate(row) for row in rows],
    }


def analyze_tender_requirements(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    detected = _detect_requirement_candidates(db, tender_id)

    existing_rows = db.execute(
        select(RequirementCandidate)
        .options(selectinload(RequirementCandidate.evidence))
        .where(RequirementCandidate.tender_id == tender_id)
    ).scalars().all()
    existing_by_key = {row.semantic_key: row for row in existing_rows}
    detected_keys = {row.semantic_key for row in detected}

    for row in existing_rows:
        if row.semantic_key in detected_keys:
            continue
        if row.detection_origin == ORIGIN_DETERMINISTIC and row.review_status == REVIEW_SUGGESTED:
            db.delete(row)

    for item in detected:
        existing = existing_by_key.get(item.semantic_key)
        if existing is None:
            existing = RequirementCandidate(
                tender_id=tender_id,
                semantic_key=item.semantic_key,
                requirement_text=item.requirement_text,
                actor_text=item.actor_text,
                modality_text=item.modality_text,
                source_document_id=item.source_document_id,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                document_page_id=item.document_page_id,
                normalized_content_id=item.normalized_content_id,
                detection_origin=ORIGIN_DETERMINISTIC,
                review_status=REVIEW_SUGGESTED,
                detector_version=REQUIREMENT_DETECTOR_VERSION,
            )
            db.add(existing)
            db.flush()
        elif existing.detection_origin == ORIGIN_DETERMINISTIC and existing.review_status == REVIEW_SUGGESTED:
            existing.requirement_text = item.requirement_text
            existing.actor_text = item.actor_text
            existing.modality_text = item.modality_text
            existing.source_document_id = item.source_document_id
            existing.source_page = item.source_page
            existing.source_excerpt = item.source_excerpt
            existing.document_page_id = item.document_page_id
            existing.normalized_content_id = item.normalized_content_id
            existing.detector_version = REQUIREMENT_DETECTOR_VERSION

        _sync_evidence(existing, item)

    db.flush()
    db.expire_all()
    return get_tender_requirement_candidates(db, tender_id)