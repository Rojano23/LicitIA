from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementSemantics,
    Tender,
)

REQUIREMENT_SEMANTICS_VERSION = "mvp-04.4"

APPLICABILITY_MANDATORY = "MANDATORY"
APPLICABILITY_CONDITIONAL = "CONDITIONAL"
APPLICABILITY_UNKNOWN = "UNKNOWN"

INTERPRETATION_DETERMINED = "DETERMINED"
INTERPRETATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"

EVIDENCE_MODE_EXPLICIT_ARTIFACT = "EXPLICIT_ARTIFACT"
EVIDENCE_MODE_DIRECT_VERIFICATION = "DIRECT_VERIFICATION"
EVIDENCE_MODE_UNSPECIFIED = "UNSPECIFIED"
EVIDENCE_MODE_REVIEW_REQUIRED = "REVIEW_REQUIRED"

EVIDENCE_TYPE_DOCUMENT = "DOCUMENT"
EVIDENCE_TYPE_FORM = "FORM"
EVIDENCE_TYPE_CERTIFICATE = "CERTIFICATE"
EVIDENCE_TYPE_DECLARATION = "DECLARATION"
EVIDENCE_TYPE_LETTER = "LETTER"
EVIDENCE_TYPE_REGISTRATION_PROOF = "REGISTRATION_PROOF"
EVIDENCE_TYPE_PERSONNEL_CREDENTIAL = "PERSONNEL_CREDENTIAL"
EVIDENCE_TYPE_EXPERIENCE_RECORD = "EXPERIENCE_RECORD"
EVIDENCE_TYPE_TECHNICAL_DOCUMENT = "TECHNICAL_DOCUMENT"
EVIDENCE_TYPE_COMMERCIAL_DOCUMENT = "COMMERCIAL_DOCUMENT"
EVIDENCE_TYPE_ECONOMIC_DOCUMENT = "ECONOMIC_DOCUMENT"
EVIDENCE_TYPE_GUARANTEE = "GUARANTEE"
EVIDENCE_TYPE_SCREENSHOT_OR_DIGITAL_PROOF = "SCREENSHOT_OR_DIGITAL_PROOF"
EVIDENCE_TYPE_OTHER = "OTHER"
EVIDENCE_TYPE_UNKNOWN = "UNKNOWN"

REVIEW_REJECTED = "REJECTED"
SCOPE_NOTE = "Interpretación realizada sobre los requisitos detectados en los documentos actualmente procesados."

OBLIGATION_RE = re.compile(
    r"\b(deber[aá]n?|debe[n]?|se\s+requiere|ser[aá]\s+requisito|tendr[aá]n?\s+que|se\s+presentar[aá]|se\s+entregar[aá]|se\s+deber[aá]|ser[aá]\s+de\s+observancia\s+obligatoria|no\s+deber[aá]n?|no\s+podr[aá]n|no\s+se\s+aceptar[aá])\b",
    re.IGNORECASE,
)
IMPERATIVE_START_RE = re.compile(r"^\s*(presentar|adjuntar|anexar|incluir|firmar|acreditar|entregar|integrar|requisitar)\b", re.IGNORECASE)
REJECTION_RE = re.compile(r"\b(causa\s+de\s+desechamiento|motivo\s+de\s+rechazo|se\s+desechar[aá])\b", re.IGNORECASE)

CONDITIONAL_ANCHOR_RE = re.compile(
    r"\b(en\s+caso\s+de(?:\s+que)?|en\s+el\s+caso\s+de\s+que|trat[aá]ndose\s+de|para\s+el\s+caso\s+de|siempre\s+que|si|cuando\s+aplique|cuando\s+corresponda|[uú]nicamente\s+cuando|solo\s+cuando|de\s+resultar\s+aplicable)\b",
    re.IGNORECASE,
)
TEMPORAL_WHEN_RE = re.compile(
    r"\bcuando\s+(se\s+abra|abra|se\s+publique|se\s+realice|inicie|termine|concluya|se\s+habilite)\b",
    re.IGNORECASE,
)

DIRECT_VERIFICATION_RE = re.compile(
    r"\b(idioma\s+espa[nñ]ol|deber[aá]\s+ser\s+firmad[oa]|firmad[oa]\s+por\s+el\s+representante|formato\s+pdf|\.pdf|\.zip|editable|precios\s+unitarios(?:\s+ofertados)?\s+.*no\s+podr[aá]n\s+ser\s+mayores|porcentaje\s+ofertado|se\s+presentar[aá]\s+en\s+idioma\s+espa[nñ]ol)\b",
    re.IGNORECASE,
)

REFERENT_RE = re.compile(
    r"\b(dicha\s+documentacion|dicha\s+documentación|el\s+presente\s+documento|los\s+documentos\s+antes\s+mencionados|lo\s+anterior|los\s+mismos|antes\s+mencionad[oa]s?)\b",
    re.IGNORECASE,
)
ANTECEDENT_RE = re.compile(
    r"\b(anexo\s+[a-z0-9\.-]+|formato\s+[a-z0-9\.-]+|documento\s+[a-z0-9\.-]+|certificado|constancia|carta|convenio|garantia|garantía|curriculum|c[eé]dula|t[ií]tulo)\b",
    re.IGNORECASE,
)

VERB_OBJECT_RE = re.compile(
    r"\b(presentar|adjuntar|anexar|incluir|entregar|integrar)\b\s+(?P<object>[^\.;]{3,320})",
    re.IGNORECASE,
)
ACCREDIT_WITH_RE = re.compile(
    r"\bacreditar\b[^\.;]{0,120}?\bmediante\b\s+(?P<object>[^\.;]{3,320})",
    re.IGNORECASE,
)
FUTURE_OBLIGATION_RE = re.compile(
    r"\b(presentar[aá]n?|entregar[aá]n?|anexar[aá]n?|adjuntar[aá]n?|incluir[aá]n?|integrar[aá]n?|acreditar[aá]n?)\b",
    re.IGNORECASE,
)
SCOPE_CONDITION_RE_LIST = (
    re.compile(r"\b(cada\s+integrante\s+de\s+la\s+propuesta\s+conjunta)\b", re.IGNORECASE),
    re.compile(r"\b(cada\s+integrante\s+del\s+consorcio)\b", re.IGNORECASE),
    re.compile(r"\b(cada\s+uno\s+de\s+los\s+integrantes\s+del\s+consorcio)\b", re.IGNORECASE),
    re.compile(r"\b(las\s+personas\s+que\s+integran\s+el\s+consorcio)\b", re.IGNORECASE),
    re.compile(r"\b(representante\s+com[uú]n[^\.;]{0,220}?integrantes\s+del\s+grupo[^\.;]{0,120}?convenio)\b", re.IGNORECASE),
)
BIDDER_CONTEXT_RE = re.compile(
    r"\b(participante(?:s)?|interesad[oa]s?|licitante(?:s)?|propuesta|integrante(?:s)?|consorcio|grupo|representante\s+com[uú]n|personal\s+propuesto)\b",
    re.IGNORECASE,
)
ARTIFACT_OBJECT_HINT_RE = re.compile(
    r"\b(document(?:o|os|acion|ación)?|constancia(?:s)?|certific(?:ado|ados|acion|ación|aciones)?|carta(?:s)?|formato(?:s)?|anexo(?:s)?|archivo(?:s)?|copia(?:s)?|curriculum|c[eé]dula|titulo|captura|garant(?:ia|ías|ía)?|convenio)\b",
    re.IGNORECASE,
)
FUTURE_ACTION_OBJECT_RE = re.compile(
    r"\b(presentar[aá]n?|entregar[aá]n?|anexar[aá]n?|adjuntar[aá]n?|incluir[aá]n?|integrar[aá]n?|acreditar[aá]n?)\b\s+(?P<object>[^\.;]{3,320})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CandidateView:
    candidate_id: str
    requirement_text: str
    actor_text: str | None
    modality_text: str | None
    source_document_id: str
    source_filename: str | None
    source_page: int | None
    source_excerpt: str


@dataclass(frozen=True)
class EvidenceExpectationDraft:
    evidence_type: str
    evidence_description: str
    source_candidate_id: str
    source_document_id: str
    source_filename: str | None
    source_page: int | None
    source_excerpt: str


@dataclass(frozen=True)
class CandidateSemantics:
    applicability: str
    condition_text: str | None
    evidence_mode: str
    expectations: tuple[EvidenceExpectationDraft, ...]
    reasons: tuple[str, ...]


@dataclass
class RequirementSemanticsDraft:
    requirement_id: str
    applicability: str
    condition_text: str | None
    interpretation_status: str
    interpretation_reason: str
    evidence_mode: str
    expected_evidence: list[EvidenceExpectationDraft] = field(default_factory=list)


def _normalize_space(value: str) -> str:
    return " ".join((value or "").replace("\r", "\n").split())


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_for_match(value: str) -> str:
    return _strip_accents(_normalize_space(value).lower())


def _first_modality_index(text: str) -> int | None:
    match = OBLIGATION_RE.search(text)
    if match:
        return match.start()
    match = IMPERATIVE_START_RE.search(text)
    if match:
        return match.start()
    return None


def _extract_condition_text(raw_text: str) -> str | None:
    compact = _normalize_space(raw_text)
    if not compact:
        return None

    condition_match = CONDITIONAL_ANCHOR_RE.search(compact)
    if not condition_match:
        return None

    modality_index = _first_modality_index(compact)
    if modality_index is not None and condition_match.start() > modality_index:
        return None

    anchor = _normalize_for_match(condition_match.group(0))
    if anchor == "si":
        # Avoid promoting incidental "si" when no obligation is visible.
        if modality_index is None:
            return None

    condition_end = len(compact)
    comma_after = compact.find(",", condition_match.start())
    if comma_after != -1:
        condition_end = min(condition_end, comma_after)
    if modality_index is not None:
        condition_end = min(condition_end, modality_index)

    condition = _normalize_space(compact[condition_match.start():condition_end]).strip(" ,;:")
    if len(condition) < 4:
        return None
    return condition


def _has_bidder_context(candidate: CandidateView, text: str) -> bool:
    actor = _normalize_space(candidate.actor_text or "")
    if actor and BIDDER_CONTEXT_RE.search(actor):
        return True
    return bool(BIDDER_CONTEXT_RE.search(text))


def _has_future_obligation_signal(candidate: CandidateView, text: str) -> bool:
    if not FUTURE_OBLIGATION_RE.search(text):
        return False
    if not _has_bidder_context(candidate, text):
        return False

    normalized = _normalize_for_match(text)
    if ARTIFACT_OBJECT_HINT_RE.search(normalized):
        return True
    if DIRECT_VERIFICATION_RE.search(text):
        return True
    if "propuesta" in normalized:
        return True
    if _extract_scope_condition_text(text):
        return True
    return False


def _has_obligation_signal(candidate: CandidateView, text: str) -> bool:
    compact = _normalize_space(text)
    if not compact:
        return False
    if OBLIGATION_RE.search(compact):
        return True
    if IMPERATIVE_START_RE.search(compact):
        return True
    if REJECTION_RE.search(compact):
        return True
    if _has_future_obligation_signal(candidate, compact):
        return True
    return False


def _extract_scope_condition_text(text: str) -> str | None:
    compact = _normalize_space(text)
    if not compact:
        return None

    for pattern in SCOPE_CONDITION_RE_LIST:
        match = pattern.search(compact)
        if match:
            return _normalize_space(match.group(1)).strip(" ,;:")
    return None


def _looks_artifact_object(object_text: str) -> bool:
    return bool(ARTIFACT_OBJECT_HINT_RE.search(_normalize_for_match(object_text)))


def _has_missing_referent(text: str) -> bool:
    normalized = _normalize_for_match(text)
    referent = REFERENT_RE.search(normalized)
    if not referent:
        return False
    prefix = normalized[: referent.start()]
    return not bool(ANTECEDENT_RE.search(prefix))


def _looks_direct_verification(text: str) -> bool:
    return bool(DIRECT_VERIFICATION_RE.search(_normalize_space(text)))


def _classify_evidence_type(description: str) -> str:
    normalized = _normalize_for_match(description)

    if "captura de pantalla" in normalized:
        return EVIDENCE_TYPE_SCREENSHOT_OR_DIGITAL_PROOF
    if "formato" in normalized:
        return EVIDENCE_TYPE_FORM
    if "curriculum" in normalized or "cedula" in normalized or "titulo" in normalized:
        return EVIDENCE_TYPE_PERSONNEL_CREDENTIAL
    if "constancia" in normalized and ("fiscal" in normalized or "seguridad social" in normalized):
        return EVIDENCE_TYPE_REGISTRATION_PROOF
    if "registro" in normalized and ("hiip" in normalized or "certificado" in normalized):
        return EVIDENCE_TYPE_REGISTRATION_PROOF
    if "garantia" in normalized or "fianza" in normalized:
        return EVIDENCE_TYPE_GUARANTEE
    if "certificado" in normalized or "iso" in normalized:
        return EVIDENCE_TYPE_CERTIFICATE
    if "carta" in normalized:
        return EVIDENCE_TYPE_LETTER
    if "experiencia" in normalized or "cartas laborales" in normalized or "documentos equivalentes" in normalized:
        return EVIDENCE_TYPE_EXPERIENCE_RECORD
    if "propuesta economica" in normalized or "economica" in normalized and "documentos" in normalized:
        return EVIDENCE_TYPE_ECONOMIC_DOCUMENT
    if "propuesta comercial" in normalized and "documentos" in normalized:
        return EVIDENCE_TYPE_COMMERCIAL_DOCUMENT
    if "documentacion tecnica" in normalized or "documentación técnica" in description.lower():
        return EVIDENCE_TYPE_TECHNICAL_DOCUMENT
    if "declaracion" in normalized or "manifestacion" in normalized:
        return EVIDENCE_TYPE_DECLARATION
    if "documento" in normalized or "documentacion" in normalized:
        return EVIDENCE_TYPE_DOCUMENT
    return EVIDENCE_TYPE_OTHER


def _extract_expectations(candidate: CandidateView) -> list[EvidenceExpectationDraft]:
    text = _normalize_space(candidate.requirement_text)
    normalized = _normalize_for_match(text)

    expectations: list[EvidenceExpectationDraft] = []

    with_match = ACCREDIT_WITH_RE.search(text)
    if with_match:
        object_text = _normalize_space(with_match.group("object")).strip(" ,;:")
        if object_text:
            expectations.append(
                EvidenceExpectationDraft(
                    evidence_type=_classify_evidence_type(object_text),
                    evidence_description=object_text,
                    source_candidate_id=candidate.candidate_id,
                    source_document_id=candidate.source_document_id,
                    source_filename=candidate.source_filename,
                    source_page=candidate.source_page,
                    source_excerpt=candidate.source_excerpt,
                )
            )

    for match in VERB_OBJECT_RE.finditer(text):
        object_text = _normalize_space(match.group("object")).strip(" ,;:")
        if not object_text:
            continue

        object_norm = _normalize_for_match(object_text)
        if "su propuesta" in object_norm and not any(
            token in object_norm
            for token in (
                "document",
                "certific",
                "constancia",
                "carta",
                "formato",
                "curriculum",
                "cedula",
                "titulo",
                "captura",
                "garantia",
            )
        ):
            continue

        if not _looks_artifact_object(object_text):
            continue

        expectations.append(
            EvidenceExpectationDraft(
                evidence_type=_classify_evidence_type(object_text),
                evidence_description=object_text,
                source_candidate_id=candidate.candidate_id,
                source_document_id=candidate.source_document_id,
                source_filename=candidate.source_filename,
                source_page=candidate.source_page,
                source_excerpt=candidate.source_excerpt,
            )
        )

    for match in FUTURE_ACTION_OBJECT_RE.finditer(text):
        if not _has_bidder_context(candidate, text):
            break

        object_text = _normalize_space(match.group("object")).strip(" ,;:")
        if not object_text:
            continue

        if not _looks_artifact_object(object_text):
            continue

        expectations.append(
            EvidenceExpectationDraft(
                evidence_type=_classify_evidence_type(object_text),
                evidence_description=object_text,
                source_candidate_id=candidate.candidate_id,
                source_document_id=candidate.source_document_id,
                source_filename=candidate.source_filename,
                source_page=candidate.source_page,
                source_excerpt=candidate.source_excerpt,
            )
        )

    dedup: dict[tuple[str, str], EvidenceExpectationDraft] = {}
    for item in expectations:
        key = (item.evidence_type, _normalize_for_match(item.evidence_description))
        dedup.setdefault(key, item)
    return list(dedup.values())


def _analyze_candidate(candidate: CandidateView) -> CandidateSemantics:
    text = _normalize_space(candidate.requirement_text)
    normalized = _normalize_for_match(text)

    reasons: list[str] = []
    has_obligation = _has_obligation_signal(candidate, text)

    condition_text = _extract_condition_text(text)
    if condition_text is None and has_obligation:
        condition_text = _extract_scope_condition_text(text)
    is_temporal_only = bool(TEMPORAL_WHEN_RE.search(normalized)) and condition_text is None

    if condition_text:
        applicability = APPLICABILITY_CONDITIONAL
    elif has_obligation:
        applicability = APPLICABILITY_MANDATORY
    else:
        applicability = APPLICABILITY_UNKNOWN
        reasons.append("unknown_applicability")

    if is_temporal_only and applicability == APPLICABILITY_UNKNOWN and has_obligation:
        applicability = APPLICABILITY_MANDATORY

    missing_referent = _has_missing_referent(text)
    expectations = _extract_expectations(candidate)

    if missing_referent:
        evidence_mode = EVIDENCE_MODE_REVIEW_REQUIRED
        reasons.append("missing_referent_context")
    elif expectations:
        evidence_mode = EVIDENCE_MODE_EXPLICIT_ARTIFACT
    elif _looks_direct_verification(text):
        evidence_mode = EVIDENCE_MODE_DIRECT_VERIFICATION
    elif has_obligation:
        evidence_mode = EVIDENCE_MODE_UNSPECIFIED
    else:
        evidence_mode = EVIDENCE_MODE_REVIEW_REQUIRED
        reasons.append("undetermined_evidence_mode")

    return CandidateSemantics(
        applicability=applicability,
        condition_text=condition_text,
        evidence_mode=evidence_mode,
        expectations=tuple(expectations),
        reasons=tuple(reasons),
    )


def _primary_candidate_from_requirement(requirement: Requirement) -> CandidateView | None:
    if not requirement.candidate_links:
        return None

    links = sorted(
        requirement.candidate_links,
        key=lambda row: (
            0 if row.is_primary_source else 1,
            (row.candidate.source_document.original_filename if row.candidate and row.candidate.source_document else ""),
            (row.candidate.source_page if row.candidate else 0),
            row.id,
        ),
    )
    for link in links:
        candidate = link.candidate
        if candidate is None:
            continue
        source_document = candidate.source_document
        return CandidateView(
            candidate_id=candidate.id,
            requirement_text=candidate.requirement_text,
            actor_text=candidate.actor_text,
            modality_text=candidate.modality_text,
            source_document_id=candidate.source_document_id,
            source_filename=source_document.original_filename if source_document else None,
            source_page=candidate.source_page,
            source_excerpt=candidate.source_excerpt,
        )
    return None


def _candidate_views(requirement: Requirement) -> list[CandidateView]:
    items: list[CandidateView] = []
    for link in sorted(
        requirement.candidate_links,
        key=lambda row: (
            0 if row.is_primary_source else 1,
            (row.candidate.source_document.original_filename if row.candidate and row.candidate.source_document else ""),
            (row.candidate.source_page if row.candidate else 0),
            row.id,
        ),
    ):
        candidate = link.candidate
        if candidate is None:
            continue
        source_document = candidate.source_document
        items.append(
            CandidateView(
                candidate_id=candidate.id,
                requirement_text=candidate.requirement_text,
                actor_text=candidate.actor_text,
                modality_text=candidate.modality_text,
                source_document_id=candidate.source_document_id,
                source_filename=source_document.original_filename if source_document else None,
                source_page=candidate.source_page,
                source_excerpt=candidate.source_excerpt,
            )
        )
    return items


def _draft_for_requirement(requirement: Requirement) -> RequirementSemanticsDraft:
    candidates = _candidate_views(requirement)
    candidate_semantics = [_analyze_candidate(item) for item in candidates]
    reasons: list[str] = []

    applicability_set = {item.applicability for item in candidate_semantics if item.applicability != APPLICABILITY_UNKNOWN}
    if APPLICABILITY_CONDITIONAL in applicability_set and APPLICABILITY_MANDATORY in applicability_set:
        applicability = APPLICABILITY_UNKNOWN
        reasons.append("applicability_conflict")
    elif APPLICABILITY_CONDITIONAL in applicability_set:
        applicability = APPLICABILITY_CONDITIONAL
    elif APPLICABILITY_MANDATORY in applicability_set:
        applicability = APPLICABILITY_MANDATORY
    else:
        applicability = APPLICABILITY_UNKNOWN
        reasons.append("unknown_applicability")

    condition_text = None
    if applicability == APPLICABILITY_CONDITIONAL:
        for item in candidate_semantics:
            if item.condition_text:
                condition_text = item.condition_text
                break
        if not condition_text:
            reasons.append("missing_condition_text")

    mode_set = {item.evidence_mode for item in candidate_semantics if item.evidence_mode != EVIDENCE_MODE_REVIEW_REQUIRED}
    if EVIDENCE_MODE_EXPLICIT_ARTIFACT in mode_set and EVIDENCE_MODE_DIRECT_VERIFICATION in mode_set:
        evidence_mode = EVIDENCE_MODE_REVIEW_REQUIRED
        reasons.append("evidence_mode_conflict")
    elif EVIDENCE_MODE_EXPLICIT_ARTIFACT in mode_set:
        evidence_mode = EVIDENCE_MODE_EXPLICIT_ARTIFACT
    elif EVIDENCE_MODE_DIRECT_VERIFICATION in mode_set:
        evidence_mode = EVIDENCE_MODE_DIRECT_VERIFICATION
    elif EVIDENCE_MODE_UNSPECIFIED in mode_set:
        evidence_mode = EVIDENCE_MODE_UNSPECIFIED
    elif any(item.evidence_mode == EVIDENCE_MODE_REVIEW_REQUIRED for item in candidate_semantics):
        evidence_mode = EVIDENCE_MODE_REVIEW_REQUIRED
    else:
        evidence_mode = EVIDENCE_MODE_UNSPECIFIED if applicability != APPLICABILITY_UNKNOWN else EVIDENCE_MODE_REVIEW_REQUIRED

    expectations: list[EvidenceExpectationDraft] = []
    if evidence_mode == EVIDENCE_MODE_EXPLICIT_ARTIFACT:
        dedup: dict[tuple[str, str], EvidenceExpectationDraft] = {}
        for item in candidate_semantics:
            for expectation in item.expectations:
                key = (expectation.evidence_type, _normalize_for_match(expectation.evidence_description))
                dedup.setdefault(key, expectation)
        expectations = sorted(dedup.values(), key=lambda row: (row.evidence_type, _normalize_for_match(row.evidence_description)))
        if not expectations:
            reasons.append("missing_explicit_evidence")

    for item in candidate_semantics:
        for reason in item.reasons:
            reasons.append(reason)

    if requirement.normalization_status == "REVIEW_REQUIRED":
        reasons.append("normalization_review_required")

    interpretation_status = INTERPRETATION_DETERMINED
    if requirement.normalization_status == "REVIEW_REQUIRED":
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED
    if applicability == APPLICABILITY_UNKNOWN:
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED
    if applicability == APPLICABILITY_CONDITIONAL and not condition_text:
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED
    if evidence_mode == EVIDENCE_MODE_REVIEW_REQUIRED:
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED
    if evidence_mode == EVIDENCE_MODE_EXPLICIT_ARTIFACT and not expectations:
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED
    if "applicability_conflict" in reasons or "evidence_mode_conflict" in reasons:
        interpretation_status = INTERPRETATION_REVIEW_REQUIRED

    reason_text = ";".join(sorted(set(reasons))) if reasons else "determined"

    return RequirementSemanticsDraft(
        requirement_id=requirement.id,
        applicability=applicability,
        condition_text=condition_text,
        interpretation_status=interpretation_status,
        interpretation_reason=reason_text,
        evidence_mode=evidence_mode,
        expected_evidence=expectations,
    )


def _expectation_key(item: EvidenceExpectationDraft) -> tuple[str, str, str]:
    return (
        item.source_candidate_id,
        item.evidence_type,
        hashlib.sha256(item.source_excerpt.encode("utf-8")).hexdigest(),
    )


def analyze_tender_requirement_semantics(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.primary_candidate),
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics).selectinload(RequirementSemantics.expected_evidence),
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    seen_requirement_ids: set[str] = set()
    for requirement in requirements:
        seen_requirement_ids.add(requirement.id)
        draft = _draft_for_requirement(requirement)

        row = requirement.semantics
        if row is None:
            row = RequirementSemantics(
                requirement_id=requirement.id,
                applicability=draft.applicability,
                condition_text=draft.condition_text,
                interpretation_status=draft.interpretation_status,
                evidence_mode=draft.evidence_mode,
                analyzer_version=REQUIREMENT_SEMANTICS_VERSION,
                interpretation_reason=draft.interpretation_reason,
            )
            db.add(row)
            db.flush()
            requirement.semantics = row
        else:
            row.applicability = draft.applicability
            row.condition_text = draft.condition_text
            row.interpretation_status = draft.interpretation_status
            row.evidence_mode = draft.evidence_mode
            row.analyzer_version = REQUIREMENT_SEMANTICS_VERSION
            row.interpretation_reason = draft.interpretation_reason

        existing_by_key: dict[tuple[str | None, str, str], RequirementEvidenceExpectation] = {}
        for item in row.expected_evidence:
            key = (item.source_candidate_id, item.evidence_type, item.excerpt_sha256)
            existing_by_key[key] = item

        desired_keys: set[tuple[str | None, str, str]] = set()
        for expectation in draft.expected_evidence:
            excerpt_sha = hashlib.sha256(expectation.source_excerpt.encode("utf-8")).hexdigest()
            key = (expectation.source_candidate_id, expectation.evidence_type, excerpt_sha)
            desired_keys.add(key)
            existing = existing_by_key.get(key)
            if existing is None:
                row.expected_evidence.append(
                    RequirementEvidenceExpectation(
                        requirement_semantics_id=row.id,
                        requirement_id=requirement.id,
                        evidence_type=expectation.evidence_type,
                        evidence_description=expectation.evidence_description,
                        source_candidate_id=expectation.source_candidate_id,
                        source_document_id=expectation.source_document_id,
                        source_page=expectation.source_page,
                        source_excerpt=expectation.source_excerpt,
                        excerpt_sha256=excerpt_sha,
                        analyzer_version=REQUIREMENT_SEMANTICS_VERSION,
                    )
                )
            else:
                existing.evidence_description = expectation.evidence_description
                existing.source_document_id = expectation.source_document_id
                existing.source_page = expectation.source_page
                existing.source_excerpt = expectation.source_excerpt
                existing.analyzer_version = REQUIREMENT_SEMANTICS_VERSION

        for item in list(row.expected_evidence):
            key = (item.source_candidate_id, item.evidence_type, item.excerpt_sha256)
            if key not in desired_keys:
                row.expected_evidence.remove(item)

    stale_rows = db.execute(
        select(RequirementSemantics)
        .join(Requirement, Requirement.id == RequirementSemantics.requirement_id)
        .where(Requirement.tender_id == tender_id)
    ).scalars().all()
    for row in stale_rows:
        if row.requirement_id not in seen_requirement_ids:
            db.delete(row)

    db.flush()
    db.expire_all()
    return get_tender_requirement_semantics(db, tender_id)


def _serialize_primary_source(requirement: Requirement) -> dict[str, Any] | None:
    for link in sorted(requirement.candidate_links, key=lambda row: (0 if row.is_primary_source else 1, row.id)):
        candidate = link.candidate
        if candidate is None:
            continue
        source_document = candidate.source_document
        return {
            "candidate_id": candidate.id,
            "source_document_id": candidate.source_document_id,
            "source_filename": source_document.original_filename if source_document else None,
            "source_page": candidate.source_page,
            "requirement_text": candidate.requirement_text,
            "source_excerpt": candidate.source_excerpt,
            "actor_text": candidate.actor_text,
            "modality_text": candidate.modality_text,
            "is_primary_source": link.is_primary_source,
            "link_origin": link.link_origin,
        }
    return None


def _serialize_expectation(row: RequirementEvidenceExpectation) -> dict[str, Any]:
    source_document = row.source_document
    return {
        "id": row.id,
        "requirement_semantics_id": row.requirement_semantics_id,
        "requirement_id": row.requirement_id,
        "evidence_type": row.evidence_type,
        "evidence_description": row.evidence_description,
        "source_candidate_id": row.source_candidate_id,
        "source_document_id": row.source_document_id,
        "source_filename": source_document.original_filename if source_document else None,
        "source_page": row.source_page,
        "source_excerpt": row.source_excerpt,
        "analyzer_version": row.analyzer_version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_requirement(requirement: Requirement) -> dict[str, Any]:
    semantics = requirement.semantics
    expected_evidence = []
    if semantics is not None:
        expected_evidence = [_serialize_expectation(item) for item in sorted(semantics.expected_evidence, key=lambda row: (row.evidence_type, row.id))]

    return {
        "requirement_id": requirement.id,
        "canonical_text": requirement.canonical_text,
        "category": requirement.category,
        "normalization_status": requirement.normalization_status,
        "applicability": semantics.applicability if semantics is not None else APPLICABILITY_UNKNOWN,
        "condition_text": semantics.condition_text if semantics is not None else None,
        "interpretation_status": semantics.interpretation_status if semantics is not None else INTERPRETATION_REVIEW_REQUIRED,
        "interpretation_reason": semantics.interpretation_reason if semantics is not None else "not_analyzed",
        "evidence_mode": semantics.evidence_mode if semantics is not None else EVIDENCE_MODE_REVIEW_REQUIRED,
        "expected_evidence": expected_evidence,
        "primary_source": _serialize_primary_source(requirement),
    }


def _build_summary(requirements: list[Requirement]) -> dict[str, Any]:
    applicability_counts = {
        APPLICABILITY_MANDATORY: 0,
        APPLICABILITY_CONDITIONAL: 0,
        APPLICABILITY_UNKNOWN: 0,
    }
    interpretation_counts = {
        INTERPRETATION_DETERMINED: 0,
        INTERPRETATION_REVIEW_REQUIRED: 0,
    }
    mode_counts = {
        EVIDENCE_MODE_EXPLICIT_ARTIFACT: 0,
        EVIDENCE_MODE_DIRECT_VERIFICATION: 0,
        EVIDENCE_MODE_UNSPECIFIED: 0,
        EVIDENCE_MODE_REVIEW_REQUIRED: 0,
    }

    evidence_type_counts: dict[str, int] = {}
    evidence_expectation_count = 0

    for row in requirements:
        semantics = row.semantics
        applicability = semantics.applicability if semantics is not None else APPLICABILITY_UNKNOWN
        status = semantics.interpretation_status if semantics is not None else INTERPRETATION_REVIEW_REQUIRED
        mode = semantics.evidence_mode if semantics is not None else EVIDENCE_MODE_REVIEW_REQUIRED

        applicability_counts[applicability] = applicability_counts.get(applicability, 0) + 1
        interpretation_counts[status] = interpretation_counts.get(status, 0) + 1
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

        if semantics is None:
            continue
        for item in semantics.expected_evidence:
            evidence_expectation_count += 1
            evidence_type_counts[item.evidence_type] = evidence_type_counts.get(item.evidence_type, 0) + 1

    return {
        "requirement_count": len(requirements),
        "mandatory_count": applicability_counts.get(APPLICABILITY_MANDATORY, 0),
        "conditional_count": applicability_counts.get(APPLICABILITY_CONDITIONAL, 0),
        "unknown_applicability_count": applicability_counts.get(APPLICABILITY_UNKNOWN, 0),
        "determined_count": interpretation_counts.get(INTERPRETATION_DETERMINED, 0),
        "review_required_count": interpretation_counts.get(INTERPRETATION_REVIEW_REQUIRED, 0),
        "explicit_artifact_count": mode_counts.get(EVIDENCE_MODE_EXPLICIT_ARTIFACT, 0),
        "direct_verification_count": mode_counts.get(EVIDENCE_MODE_DIRECT_VERIFICATION, 0),
        "unspecified_evidence_count": mode_counts.get(EVIDENCE_MODE_UNSPECIFIED, 0),
        "evidence_review_required_count": mode_counts.get(EVIDENCE_MODE_REVIEW_REQUIRED, 0),
        "evidence_expectation_count": evidence_expectation_count,
        "evidence_type_counts": dict(sorted(evidence_type_counts.items())),
    }


def get_tender_requirement_semantics(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.primary_candidate),
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics)
            .selectinload(RequirementSemantics.expected_evidence)
            .selectinload(RequirementEvidenceExpectation.source_document),
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    return {
        "tender_id": tender_id,
        "analyzer_version": REQUIREMENT_SEMANTICS_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _build_summary(requirements),
        "requirements": [_serialize_requirement(item) for item in requirements],
    }
