from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.company_evidence import _serialize_evidence_row
from app.evidence_matching import _serialize_match_row
from app.models import (
    Company,
    CompanyEvidence,
    CompanyEvidenceReviewStatus,
    Requirement,
    RequirementComplianceApplicabilityContext,
    RequirementComplianceAssessment,
    RequirementComplianceCheck,
    RequirementComplianceCheckStatus,
    RequirementComplianceSystemStatus,
    RequirementEvidenceCandidateMatch,
    RequirementEvidenceCandidateReviewStatus,
    Tender,
    TenderEvent,
)
from app.requirement_matrix import get_tender_requirement_matrix

COMPLIANCE_EVALUATOR_VERSION = "mvp-05.4"

SYSTEM_SUPPORTED = RequirementComplianceSystemStatus.SUPPORTED.value
SYSTEM_PARTIALLY_SUPPORTED = RequirementComplianceSystemStatus.PARTIALLY_SUPPORTED.value
SYSTEM_NOT_SUPPORTED = RequirementComplianceSystemStatus.NOT_SUPPORTED.value
SYSTEM_REVIEW_REQUIRED = RequirementComplianceSystemStatus.REVIEW_REQUIRED.value
SYSTEM_NOT_EVALUATED = RequirementComplianceSystemStatus.NOT_EVALUATED.value

APPLIES = RequirementComplianceApplicabilityContext.APPLIES.value
CONDITION_UNRESOLVED = RequirementComplianceApplicabilityContext.CONDITION_UNRESOLVED.value
APPLICABILITY_UNKNOWN = RequirementComplianceApplicabilityContext.UNKNOWN.value

CHECK_PASS = RequirementComplianceCheckStatus.PASS.value
CHECK_FAIL = RequirementComplianceCheckStatus.FAIL.value
CHECK_UNKNOWN = RequirementComplianceCheckStatus.UNKNOWN.value
CHECK_NOT_APPLICABLE = RequirementComplianceCheckStatus.NOT_APPLICABLE.value

MATCH_CONFIRMED = RequirementEvidenceCandidateReviewStatus.CONFIRMED.value
MATCH_PENDING = RequirementEvidenceCandidateReviewStatus.PENDING.value
MATCH_NEEDS_REVIEW = RequirementEvidenceCandidateReviewStatus.NEEDS_REVIEW.value
MATCH_REJECTED = RequirementEvidenceCandidateReviewStatus.REJECTED.value

EVIDENCE_APPROVED = CompanyEvidenceReviewStatus.APPROVED.value
EVIDENCE_PENDING = CompanyEvidenceReviewStatus.PENDING.value
EVIDENCE_NEEDS_REVIEW = CompanyEvidenceReviewStatus.NEEDS_REVIEW.value
EVIDENCE_REJECTED = CompanyEvidenceReviewStatus.REJECTED.value

FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_NOT_REVIEWED = "NOT_REVIEWED"

CHECK_EVIDENCE_PRESENT = "EVIDENCE_PRESENT"
CHECK_MATCH_CONFIRMED = "MATCH_CONFIRMED"
CHECK_EVIDENCE_INTERPRETATION_REVIEWED = "EVIDENCE_INTERPRETATION_REVIEWED"
CHECK_ARTIFACT_TYPE = "ARTIFACT_TYPE"
CHECK_SPECIFIC_STANDARD = "SPECIFIC_STANDARD"
CHECK_STANDARD_EDITION = "STANDARD_EDITION"
CHECK_ISSUER = "ISSUER"
CHECK_VALIDITY_DATE = "VALIDITY_DATE"
CHECK_MINIMUM_COUNT = "MINIMUM_COUNT"
CHECK_DATE_WINDOW = "DATE_WINDOW"
CHECK_SUBJECT_IDENTITY = "SUBJECT_IDENTITY"
CHECK_ALTERNATIVE_GROUP = "ALTERNATIVE_GROUP"
CHECK_SOURCE_CURRENT = "SOURCE_CURRENT"
CHECK_OTHER = "OTHER"

SCOPE_NOTE = (
    "La evaluación automática indica qué tan bien la evidencia disponible soporta cada requisito "
    "según reglas determinísticas de LicitIA. No constituye la decisión final de cumplimiento. "
    "La decisión final corresponde al operador."
)

_SPACE_RE = re.compile(r"\s+")
_ISO_RE = re.compile(r"\biso[\s\-]*([0-9]{4,5})(?::[\s\-]*([0-9]{4}))?\b", re.IGNORECASE)
_MIN_COUNT_RE = re.compile(r"\b(?:al\s+menos|m[ií]nimo(?:s)?\s+de?)\s+(\d+)\b", re.IGNORECASE)
_YEAR_WINDOW_RE = re.compile(r"\b(?:[uú]ltimos?|últimos?)\s+(\d+)\s+a[nñ]os\b", re.IGNORECASE)


@dataclass(slots=True)
class CheckDraft:
    check_type: str
    check_status: str
    expected_value: str | None
    observed_value: str | None
    rationale: str
    company_evidence_id: str | None = None
    match_id: str | None = None


@dataclass(slots=True)
class AssessmentDraft:
    requirement_id: str
    system_status: str
    applicability_context: str
    assessment_summary: str
    warning_codes: list[str]
    checks: list[CheckDraft]
    fingerprint: str


def _normalize_space(value: str | None) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip())


def _normalize_for_match(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return _normalize_space(without_marks).lower()


def _load_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _dump_json_list(values: list[str]) -> str:
    return json.dumps(sorted(dict.fromkeys(values)), ensure_ascii=True)


def _evidence_review_freshness(evidence: CompanyEvidence) -> str:
    review = evidence.review
    if review is None:
        return FRESHNESS_NOT_REVIEWED
    if review.review_status == EVIDENCE_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not review.reviewed_fingerprint:
        return FRESHNESS_STALE
    if review.reviewed_fingerprint != evidence.semantic_fingerprint:
        return FRESHNESS_STALE
    return FRESHNESS_CURRENT


def _match_review_freshness(match: RequirementEvidenceCandidateMatch) -> str:
    review = match.review
    if review is None:
        return FRESHNESS_NOT_REVIEWED
    if review.review_status == MATCH_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not review.reviewed_fingerprint:
        return FRESHNESS_STALE
    if review.reviewed_fingerprint != match.match_fingerprint:
        return FRESHNESS_STALE
    return FRESHNESS_CURRENT


def _tender_or_404(db: Session, tender_id: str) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


def _company_or_404(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _applicability_context(requirement_row: dict[str, Any]) -> str:
    applicability = str(requirement_row.get("applicability") or "UNKNOWN")
    if applicability == "MANDATORY":
        return APPLIES
    if applicability == "CONDITIONAL":
        return CONDITION_UNRESOLVED
    return APPLICABILITY_UNKNOWN


def _is_requirement_rejected(requirement_row: dict[str, Any]) -> bool:
    return str(requirement_row.get("review_status") or "") == "REJECTED"


def _matches_for_requirement(db: Session, tender_id: str, company_id: str) -> list[RequirementEvidenceCandidateMatch]:
    return db.execute(
        select(RequirementEvidenceCandidateMatch)
        .where(
            RequirementEvidenceCandidateMatch.tender_id == tender_id,
            RequirementEvidenceCandidateMatch.company_id == company_id,
            RequirementEvidenceCandidateMatch.is_active.is_(True),
        )
        .options(
            selectinload(RequirementEvidenceCandidateMatch.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence).selectinload(CompanyEvidence.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence).selectinload(CompanyEvidence.source_document),
            selectinload(RequirementEvidenceCandidateMatch.requirement),
        )
        .order_by(RequirementEvidenceCandidateMatch.created_at.asc(), RequirementEvidenceCandidateMatch.id.asc())
    ).scalars().all()


def _evidence_is_current(evidence: CompanyEvidence) -> bool:
    return evidence.source_document.archived_at is None and bool(evidence.source_document.is_current)


def _joined_evidence_text(evidence: CompanyEvidence) -> str:
    pieces = [
        evidence.canonical_statement,
        evidence.source_excerpt,
        evidence.reference_number,
        evidence.issuer,
        evidence.subject_name,
    ]
    return " ".join(_normalize_space(piece) for piece in pieces if _normalize_space(piece))


def _joined_requirement_text(requirement_row: dict[str, Any]) -> str:
    pieces = [str(requirement_row.get("canonical_text") or "")]
    primary_source = requirement_row.get("primary_source") or {}
    if primary_source.get("requirement_text"):
        pieces.append(str(primary_source.get("requirement_text") or ""))
    for item in requirement_row.get("expected_evidence") or []:
        desc = _normalize_space(item.get("evidence_description"))
        if desc:
            pieces.append(desc)
    return " ".join(pieces)


def _extract_iso(text: str) -> tuple[str | None, str | None]:
    match = _ISO_RE.search(text)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _needs_validity_check(requirement_text: str) -> bool:
    text = _normalize_for_match(requirement_text)
    if "vigente" not in text and "vigencia" not in text and "valido" not in text:
        return False
    return "presentacion" in text or "propuesta" in text


def _submission_reference_date(db: Session, tender_id: str) -> date | None:
    events = db.execute(
        select(TenderEvent)
        .where(TenderEvent.tender_id == tender_id)
        .order_by(TenderEvent.created_at.asc(), TenderEvent.id.asc())
    ).scalars().all()
    for event in events:
        effective_type = event.human_event_type or event.event_type
        if effective_type != "PROPOSAL_SUBMISSION_DEADLINE":
            continue
        if event.review_status not in {"CONFIRMED", "SUGGESTED"}:
            continue
        return event.human_event_date or event.event_date
    return None


def _map_expected_evidence_types(requirement_row: dict[str, Any]) -> set[str]:
    mapped: set[str] = set()
    for item in requirement_row.get("expected_evidence") or []:
        ev_type = str(item.get("evidence_type") or "").upper()
        if ev_type == "CERTIFICATE":
            mapped.add("CERTIFICATION")
        elif ev_type == "EXPERIENCE_RECORD":
            mapped.add("EXPERIENCE")
        elif ev_type == "PERSONNEL_CREDENTIAL":
            mapped.add("PERSONNEL_QUALIFICATION")
        elif ev_type == "REGISTRATION_PROOF":
            mapped.add("REGISTRATION")
            mapped.add("TAX_REGISTRATION")
        elif ev_type in {"FORM", "DOCUMENT", "DECLARATION", "LETTER", "COMMERCIAL_DOCUMENT", "TECHNICAL_DOCUMENT", "ECONOMIC_DOCUMENT"}:
            mapped.add("COMMERCIAL_DOCUMENT")
        elif ev_type == "GUARANTEE":
            mapped.add("GUARANTEE")
    return mapped


def _inference_tokens(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _clear_subject_mismatch(company: Company, evidence: CompanyEvidence) -> bool:
    if evidence.subject_kind != "COMPANY" or not evidence.subject_name:
        return False
    subject = _normalize_for_match(evidence.subject_name)
    if not subject:
        return False
    legal_name = _normalize_for_match(company.legal_name)
    company_name = _normalize_for_match(company.name)
    if legal_name and legal_name in subject:
        return False
    if company_name and company_name in subject:
        return False
    return True


def _assessment_fingerprint(
    *,
    requirement_row: dict[str, Any],
    system_status: str,
    applicability_context: str,
    warning_codes: list[str],
    checks: list[CheckDraft],
    used_matches: list[RequirementEvidenceCandidateMatch],
    reference_date: date | None,
) -> str:
    payload = {
        "requirement_id": requirement_row["requirement_id"],
        "representation_fingerprint": requirement_row["representation_fingerprint"],
        "requirement_review_status": requirement_row["review_status"],
        "requirement_review_freshness": requirement_row["review_freshness"],
        "effective_status": requirement_row["effective_status"],
        "applicability": requirement_row["applicability"],
        "evidence_mode": requirement_row["evidence_mode"],
        "system_status": system_status,
        "applicability_context": applicability_context,
        "warning_codes": sorted(dict.fromkeys(warning_codes)),
        "checks": [
            {
                "check_type": check.check_type,
                "check_status": check.check_status,
                "expected_value": _normalize_space(check.expected_value),
                "observed_value": _normalize_space(check.observed_value),
                "rationale": _normalize_space(check.rationale),
                "company_evidence_id": check.company_evidence_id,
                "match_id": check.match_id,
            }
            for check in sorted(
                checks,
                key=lambda item: (
                    item.check_type,
                    item.check_status,
                    item.expected_value or "",
                    item.observed_value or "",
                    item.company_evidence_id or "",
                    item.match_id or "",
                ),
            )
        ],
        "used_matches": [
            {
                "match_id": row.id,
                "match_fingerprint": row.match_fingerprint,
                "match_review_status": row.review.review_status if row.review is not None else MATCH_PENDING,
                "match_review_freshness": _match_review_freshness(row),
                "company_evidence_id": row.company_evidence_id,
                "evidence_fingerprint": row.company_evidence.semantic_fingerprint,
                "evidence_review_status": row.company_evidence.review.review_status if row.company_evidence.review is not None else EVIDENCE_PENDING,
                "evidence_review_freshness": _evidence_review_freshness(row.company_evidence),
            }
            for row in sorted(used_matches, key=lambda item: item.id)
        ],
        "reference_date": reference_date.isoformat() if reference_date is not None else None,
        "evaluator_version": COMPLIANCE_EVALUATOR_VERSION,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _make_summary(system_status: str, checks: list[CheckDraft]) -> str:
    pass_count = sum(1 for row in checks if row.check_status == CHECK_PASS)
    fail_count = sum(1 for row in checks if row.check_status == CHECK_FAIL)
    unknown_count = sum(1 for row in checks if row.check_status == CHECK_UNKNOWN)
    if system_status == SYSTEM_NOT_EVALUATED:
        return "No evaluado por alcance documental de empresa."
    if system_status == SYSTEM_NOT_SUPPORTED:
        return "No se encontró evidencia empresarial que soporte el requisito de forma determinística."
    if system_status == SYSTEM_SUPPORTED:
        return f"Evidencia suficiente: {pass_count} verificación(es) PASS, sin fallas ni incertidumbre material."
    if system_status == SYSTEM_PARTIALLY_SUPPORTED:
        return f"Evidencia parcial: PASS {pass_count}, FAIL {fail_count}, UNKNOWN {unknown_count}."
    return f"Requiere revisión: PASS {pass_count}, FAIL {fail_count}, UNKNOWN {unknown_count}."


def _evaluate_requirement(
    db: Session,
    *,
    tender_id: str,
    company: Company,
    requirement_row: dict[str, Any],
    matches: list[RequirementEvidenceCandidateMatch],
) -> AssessmentDraft:
    warning_codes: list[str] = []
    checks: list[CheckDraft] = []
    applicability_context = _applicability_context(requirement_row)
    requirement_text = _normalize_for_match(_joined_requirement_text(requirement_row))

    if applicability_context == CONDITION_UNRESOLVED:
        warning_codes.append("CONDITION_UNRESOLVED")

    effective_status = str(requirement_row.get("effective_status") or "UNRESOLVED")
    if effective_status == "SUPERSEDED":
        checks.append(
            CheckDraft(
                check_type=CHECK_OTHER,
                check_status=CHECK_NOT_APPLICABLE,
                expected_value="Requirement effective state",
                observed_value="SUPERSEDED",
                rationale="El requisito se encuentra sustituido y no se evalúa como obligación vigente.",
            )
        )
        system_status = SYSTEM_NOT_EVALUATED
        fingerprint = _assessment_fingerprint(
            requirement_row=requirement_row,
            system_status=system_status,
            applicability_context=applicability_context,
            warning_codes=warning_codes,
            checks=checks,
            used_matches=[],
            reference_date=None,
        )
        return AssessmentDraft(
            requirement_id=str(requirement_row["requirement_id"]),
            system_status=system_status,
            applicability_context=applicability_context,
            assessment_summary=_make_summary(system_status, checks),
            warning_codes=warning_codes,
            checks=checks,
            fingerprint=fingerprint,
        )

    if effective_status in {"AMBIGUOUS", "UNRESOLVED"}:
        warning_codes.append("REQUIREMENT_EFFECTIVE_STATE_UNRESOLVED")

    evidence_mode = str(requirement_row.get("evidence_mode") or "REVIEW_REQUIRED")
    if evidence_mode == "DIRECT_VERIFICATION":
        checks.append(
            CheckDraft(
                check_type=CHECK_OTHER,
                check_status=CHECK_NOT_APPLICABLE,
                expected_value="Verificación directa sobre la propuesta",
                observed_value="Fuera del alcance de CompanyEvidence",
                rationale="Este requisito debe verificarse directamente sobre la propuesta y no mediante la biblioteca documental de la empresa.",
            )
        )
        warning_codes.append("DIRECT_VERIFICATION_OUTSIDE_COMPANY_EVIDENCE")
        system_status = SYSTEM_NOT_EVALUATED
        fingerprint = _assessment_fingerprint(
            requirement_row=requirement_row,
            system_status=system_status,
            applicability_context=applicability_context,
            warning_codes=warning_codes,
            checks=checks,
            used_matches=[],
            reference_date=None,
        )
        return AssessmentDraft(
            requirement_id=str(requirement_row["requirement_id"]),
            system_status=system_status,
            applicability_context=applicability_context,
            assessment_summary=_make_summary(system_status, checks),
            warning_codes=warning_codes,
            checks=checks,
            fingerprint=fingerprint,
        )

    if evidence_mode == "UNSPECIFIED":
        warning_codes.append("EXPECTED_ARTIFACT_UNSPECIFIED")

    if str(requirement_row.get("interpretation_status") or "") == "REVIEW_REQUIRED":
        warning_codes.append("REQUIREMENT_INTERPRETATION_REVIEW_REQUIRED")

    usable_matches: list[RequirementEvidenceCandidateMatch] = []
    rejected_match_used = False
    for match in matches:
        evidence = match.company_evidence
        review_status = match.review.review_status if match.review is not None else MATCH_PENDING
        if review_status == MATCH_REJECTED:
            rejected_match_used = True
            continue
        if evidence.review is not None and evidence.review.review_status == EVIDENCE_REJECTED:
            warning_codes.append("REJECTED_EVIDENCE_IGNORED")
            continue
        if evidence.company_id != company.id:
            continue
        if not _evidence_is_current(evidence):
            warning_codes.append("HISTORICAL_SOURCE_EVIDENCE")
        usable_matches.append(match)

    if rejected_match_used:
        warning_codes.append("REJECTED_MATCH_IGNORED")

    confirmed_current = [
        match
        for match in usable_matches
        if (match.review is not None and match.review.review_status == MATCH_CONFIRMED and _match_review_freshness(match) == FRESHNESS_CURRENT)
    ]

    if usable_matches and not confirmed_current:
        warning_codes.append("EVIDENCE_ASSOCIATION_NOT_CONFIRMED")

    checks.append(
        CheckDraft(
            check_type=CHECK_EVIDENCE_PRESENT,
            check_status=CHECK_PASS if usable_matches else CHECK_FAIL,
            expected_value="Al menos una evidencia elegible",
            observed_value=str(len(usable_matches)),
            rationale="Se consideran asociaciones activas con evidencia no rechazada para la empresa seleccionada.",
            company_evidence_id=usable_matches[0].company_evidence_id if usable_matches else None,
            match_id=usable_matches[0].id if usable_matches else None,
        )
    )

    if confirmed_current:
        checks.append(
            CheckDraft(
                check_type=CHECK_MATCH_CONFIRMED,
                check_status=CHECK_PASS,
                expected_value="Asociación confirmada y vigente",
                observed_value=str(len(confirmed_current)),
                rationale="Existe al menos una asociación requisito-evidencia confirmada por revisión humana y vigente.",
                company_evidence_id=confirmed_current[0].company_evidence_id,
                match_id=confirmed_current[0].id,
            )
        )
    elif usable_matches:
        checks.append(
            CheckDraft(
                check_type=CHECK_MATCH_CONFIRMED,
                check_status=CHECK_UNKNOWN,
                expected_value="Asociación confirmada y vigente",
                observed_value="No confirmada",
                rationale="Existen candidatos relevantes, pero no una asociación humana confirmada vigente.",
                company_evidence_id=usable_matches[0].company_evidence_id,
                match_id=usable_matches[0].id,
            )
        )
    else:
        checks.append(
            CheckDraft(
                check_type=CHECK_MATCH_CONFIRMED,
                check_status=CHECK_FAIL,
                expected_value="Asociación confirmada y vigente",
                observed_value="Sin asociaciones elegibles",
                rationale="Sin asociaciones elegibles no existe base para confirmar soporte documental.",
            )
        )

    supports_review = [
        match
        for match in usable_matches
        if (match.company_evidence.review is not None and match.company_evidence.review.review_status == EVIDENCE_APPROVED)
    ]
    supports_current = [match for match in supports_review if _evidence_review_freshness(match.company_evidence) == FRESHNESS_CURRENT]

    if supports_current:
        checks.append(
            CheckDraft(
                check_type=CHECK_EVIDENCE_INTERPRETATION_REVIEWED,
                check_status=CHECK_PASS,
                expected_value="Evidencia revisada y vigente",
                observed_value=str(len(supports_current)),
                rationale="La evidencia usada cuenta con revisión humana APPROVED y fingerprint vigente.",
                company_evidence_id=supports_current[0].company_evidence_id,
                match_id=supports_current[0].id,
            )
        )
    elif usable_matches:
        checks.append(
            CheckDraft(
                check_type=CHECK_EVIDENCE_INTERPRETATION_REVIEWED,
                check_status=CHECK_UNKNOWN,
                expected_value="Evidencia revisada y vigente",
                observed_value="Pendiente/Desactualizada",
                rationale="La evidencia material no está aprobada o su revisión no está vigente.",
                company_evidence_id=usable_matches[0].company_evidence_id,
                match_id=usable_matches[0].id,
            )
        )

    expected_types = _map_expected_evidence_types(requirement_row)
    if expected_types:
        observed_types = {match.company_evidence.evidence_type for match in usable_matches}
        overlap = sorted(expected_types & observed_types)
        checks.append(
            CheckDraft(
                check_type=CHECK_ARTIFACT_TYPE,
                check_status=CHECK_PASS if overlap else (CHECK_FAIL if usable_matches else CHECK_UNKNOWN),
                expected_value=", ".join(sorted(expected_types)),
                observed_value=", ".join(sorted(observed_types)) if observed_types else None,
                rationale="Se compara el tipo de evidencia esperado por semántica contra los tipos de evidencia asociados.",
                company_evidence_id=usable_matches[0].company_evidence_id if usable_matches else None,
                match_id=usable_matches[0].id if usable_matches else None,
            )
        )
    elif evidence_mode == "UNSPECIFIED":
        checks.append(
            CheckDraft(
                check_type=CHECK_ARTIFACT_TYPE,
                check_status=CHECK_NOT_APPLICABLE,
                expected_value="No especificado",
                observed_value=None,
                rationale="La fuente exige una obligación sustantiva pero no define artefacto documental específico.",
            )
        )

    req_iso_code, req_iso_edition = _extract_iso(requirement_text)
    if req_iso_code is not None:
        same_standard: list[RequirementEvidenceCandidateMatch] = []
        wrong_standard: list[str] = []
        edition_match = False
        for match in usable_matches:
            ev_code, ev_edition = _extract_iso(_normalize_for_match(_joined_evidence_text(match.company_evidence)))
            if ev_code is None:
                continue
            if ev_code == req_iso_code:
                same_standard.append(match)
                if req_iso_edition and ev_edition == req_iso_edition:
                    edition_match = True
            else:
                wrong_standard.append(ev_code)

        checks.append(
            CheckDraft(
                check_type=CHECK_SPECIFIC_STANDARD,
                check_status=CHECK_PASS if same_standard else (CHECK_FAIL if wrong_standard else CHECK_UNKNOWN),
                expected_value=f"ISO {req_iso_code}",
                observed_value=(
                    f"ISO {req_iso_code}" if same_standard else (", ".join(sorted(dict.fromkeys(wrong_standard))) if wrong_standard else "No identificado")
                ),
                rationale="Se valida el estándar específico mencionado por el requisito contra el estándar detectado en la evidencia asociada.",
                company_evidence_id=same_standard[0].company_evidence_id if same_standard else (usable_matches[0].company_evidence_id if usable_matches else None),
                match_id=same_standard[0].id if same_standard else (usable_matches[0].id if usable_matches else None),
            )
        )

        if req_iso_edition:
            if edition_match:
                edition_status = CHECK_PASS
                observed_edition = req_iso_edition
                rationale = "La evidencia identifica explícitamente la misma edición requerida del estándar."
                support_match = next(
                    (
                        match
                        for match in same_standard
                        if _extract_iso(_normalize_for_match(_joined_evidence_text(match.company_evidence)))[1] == req_iso_edition
                    ),
                    same_standard[0] if same_standard else (usable_matches[0] if usable_matches else None),
                )
            elif same_standard:
                edition_status = CHECK_UNKNOWN
                observed_edition = "No identificada"
                rationale = "La evidencia confirma el estándar, pero no demuestra explícitamente la edición requerida."
                support_match = same_standard[0]
            elif usable_matches:
                edition_status = CHECK_FAIL
                observed_edition = "Edición incompatible o no evidenciada"
                rationale = "No existe evidencia asociada que demuestre la edición requerida del estándar."
                support_match = usable_matches[0]
            else:
                edition_status = CHECK_UNKNOWN
                observed_edition = "Sin evidencia asociada"
                rationale = "Sin evidencia elegible no se puede determinar la edición requerida."
                support_match = None

            checks.append(
                CheckDraft(
                    check_type=CHECK_STANDARD_EDITION,
                    check_status=edition_status,
                    expected_value=req_iso_edition,
                    observed_value=observed_edition,
                    rationale=rationale,
                    company_evidence_id=support_match.company_evidence_id if support_match is not None else None,
                    match_id=support_match.id if support_match is not None else None,
                )
            )

    issuer_required = _inference_tokens(requirement_text, ("fabricante", "distribuidor autorizado"))
    if issuer_required:
        issuer_support = [
            match
            for match in usable_matches
            if _inference_tokens(
                _normalize_for_match(_joined_evidence_text(match.company_evidence)),
                ("fabricante", "distribuidor autorizado"),
            )
        ]
        checks.append(
            CheckDraft(
                check_type=CHECK_ISSUER,
                check_status=CHECK_PASS if issuer_support else (CHECK_UNKNOWN if usable_matches else CHECK_FAIL),
                expected_value="Fabricante o distribuidor autorizado",
                observed_value="Evidencia de emisor específica" if issuer_support else "No identificada",
                rationale="Sólo se valida emisor cuando el requisito lo exige expresamente.",
                company_evidence_id=issuer_support[0].company_evidence_id if issuer_support else (usable_matches[0].company_evidence_id if usable_matches else None),
                match_id=issuer_support[0].id if issuer_support else (usable_matches[0].id if usable_matches else None),
            )
        )

    validity_required = _needs_validity_check(requirement_text)
    reference_date = _submission_reference_date(db, tender_id) if validity_required else None
    if validity_required:
        if reference_date is None:
            warning_codes.append("MISSING_REFERENCE_DATE")
            checks.append(
                CheckDraft(
                    check_type=CHECK_VALIDITY_DATE,
                    check_status=CHECK_UNKNOWN,
                    expected_value="Vigente a fecha de presentación",
                    observed_value="Fecha de referencia no disponible",
                    rationale="No existe fecha de presentación confirmada para evaluar vigencia de manera determinística.",
                )
            )
        else:
            valid_matches: list[RequirementEvidenceCandidateMatch] = []
            expired_matches: list[RequirementEvidenceCandidateMatch] = []
            for match in usable_matches:
                valid_until = match.company_evidence.valid_until
                if valid_until is None:
                    continue
                if valid_until >= reference_date:
                    valid_matches.append(match)
                else:
                    expired_matches.append(match)
            if valid_matches:
                checks.append(
                    CheckDraft(
                        check_type=CHECK_VALIDITY_DATE,
                        check_status=CHECK_PASS,
                        expected_value=f"Validez >= {reference_date.isoformat()}",
                        observed_value=valid_matches[0].company_evidence.valid_until.isoformat() if valid_matches[0].company_evidence.valid_until else None,
                        rationale="La evidencia registra vigencia posterior o igual a la fecha de referencia del requisito.",
                        company_evidence_id=valid_matches[0].company_evidence_id,
                        match_id=valid_matches[0].id,
                    )
                )
            elif expired_matches:
                checks.append(
                    CheckDraft(
                        check_type=CHECK_VALIDITY_DATE,
                        check_status=CHECK_FAIL,
                        expected_value=f"Validez >= {reference_date.isoformat()}",
                        observed_value=expired_matches[0].company_evidence.valid_until.isoformat() if expired_matches[0].company_evidence.valid_until else None,
                        rationale="La vigencia registrada expira antes de la fecha de referencia exigida.",
                        company_evidence_id=expired_matches[0].company_evidence_id,
                        match_id=expired_matches[0].id,
                    )
                )
            else:
                checks.append(
                    CheckDraft(
                        check_type=CHECK_VALIDITY_DATE,
                        check_status=CHECK_UNKNOWN,
                        expected_value=f"Validez >= {reference_date.isoformat()}",
                        observed_value="Vigencia no identificada",
                        rationale="La evidencia no incluye fecha de vigencia suficiente para validar el requisito.",
                        company_evidence_id=usable_matches[0].company_evidence_id if usable_matches else None,
                        match_id=usable_matches[0].id if usable_matches else None,
                    )
                )

    if _inference_tokens(requirement_text, ("experiencia", "servicios")):
        min_count_match = _MIN_COUNT_RE.search(requirement_text)
        if min_count_match:
            required_count = int(min_count_match.group(1))
            confirmed_experience = {
                match.company_evidence_id
                for match in confirmed_current
                if match.company_evidence.evidence_type == "EXPERIENCE"
            }
            checks.append(
                CheckDraft(
                    check_type=CHECK_MINIMUM_COUNT,
                    check_status=CHECK_PASS if len(confirmed_experience) >= required_count else CHECK_FAIL,
                    expected_value=str(required_count),
                    observed_value=str(len(confirmed_experience)),
                    rationale="Se evalúa conteo determinístico sobre evidencias de experiencia con asociación confirmada vigente.",
                    company_evidence_id=confirmed_current[0].company_evidence_id if confirmed_current else None,
                    match_id=confirmed_current[0].id if confirmed_current else None,
                )
            )

        window_match = _YEAR_WINDOW_RE.search(requirement_text)
        if window_match:
            years = int(window_match.group(1))
            if reference_date is None:
                checks.append(
                    CheckDraft(
                        check_type=CHECK_DATE_WINDOW,
                        check_status=CHECK_UNKNOWN,
                        expected_value=f"Dentro de {years} años previos",
                        observed_value="Sin fecha de referencia",
                        rationale="Sin fecha de referencia confirmada no puede evaluarse ventana temporal.",
                    )
                )
            else:
                min_year = reference_date.replace(year=reference_date.year - years)
                in_window = [
                    match
                    for match in confirmed_current
                    if match.company_evidence.period_end is not None and min_year <= match.company_evidence.period_end <= reference_date
                ]
                checks.append(
                    CheckDraft(
                        check_type=CHECK_DATE_WINDOW,
                        check_status=CHECK_PASS if in_window else CHECK_UNKNOWN,
                        expected_value=f"Periodo fin entre {min_year.isoformat()} y {reference_date.isoformat()}",
                        observed_value=in_window[0].company_evidence.period_end.isoformat() if in_window and in_window[0].company_evidence.period_end else "No identificada",
                        rationale="Se valida ventana temporal sólo cuando existen fechas explícitas en la evidencia.",
                        company_evidence_id=in_window[0].company_evidence_id if in_window else None,
                        match_id=in_window[0].id if in_window else None,
                    )
                )

    identity_required = _inference_tokens(
        requirement_text,
        (
            "rfc",
            "registro federal de contribuyentes",
            "razon social",
            "a nombre del participante",
            "del participante",
        ),
    )

    if usable_matches and identity_required:
        mismatch_rows = [match for match in usable_matches if _clear_subject_mismatch(company, match.company_evidence)]
        if mismatch_rows:
            checks.append(
                CheckDraft(
                    check_type=CHECK_SUBJECT_IDENTITY,
                    check_status=CHECK_FAIL,
                    expected_value=company.legal_name or company.name,
                    observed_value=mismatch_rows[0].company_evidence.subject_name,
                    rationale="El sujeto explícito de la evidencia no coincide con la empresa seleccionada.",
                    company_evidence_id=mismatch_rows[0].company_evidence_id,
                    match_id=mismatch_rows[0].id,
                )
            )

    if _inference_tokens(requirement_text, (" o ", " u ")):
        has_any = any(check.check_status == CHECK_PASS for check in checks if check.check_type in {CHECK_ARTIFACT_TYPE, CHECK_SPECIFIC_STANDARD})
        checks.append(
            CheckDraft(
                check_type=CHECK_ALTERNATIVE_GROUP,
                check_status=CHECK_PASS if has_any else CHECK_UNKNOWN,
                expected_value="Al menos una alternativa documental válida",
                observed_value="Alternativa evidenciada" if has_any else "No determinada",
                rationale="Las alternativas OR se evalúan como grupo; una alternativa válida puede satisfacer el grupo.",
                company_evidence_id=usable_matches[0].company_evidence_id if usable_matches else None,
                match_id=usable_matches[0].id if usable_matches else None,
            )
        )

    if any(not _evidence_is_current(match.company_evidence) for match in usable_matches):
        checks.append(
            CheckDraft(
                check_type=CHECK_SOURCE_CURRENT,
                check_status=CHECK_UNKNOWN,
                expected_value="Fuentes documentales vigentes",
                observed_value="Incluye fuentes históricas",
                rationale="Evidencia histórica se mantiene visible pero reduce confianza de soporte automático.",
                company_evidence_id=usable_matches[0].company_evidence_id if usable_matches else None,
                match_id=usable_matches[0].id if usable_matches else None,
            )
        )

    if any(_match_review_freshness(match) == FRESHNESS_STALE for match in usable_matches):
        warning_codes.append("STALE_MATCH_REVIEW")
    if any(_evidence_review_freshness(match.company_evidence) == FRESHNESS_STALE for match in usable_matches):
        warning_codes.append("STALE_EVIDENCE_REVIEW")

    material_checks = [check for check in checks if check.check_status in {CHECK_PASS, CHECK_FAIL, CHECK_UNKNOWN}]
    fail_types = {check.check_type for check in material_checks if check.check_status == CHECK_FAIL}
    has_unknown = any(check.check_status == CHECK_UNKNOWN for check in material_checks)
    has_fail = bool(fail_types)

    if not usable_matches:
        warning_codes.append("NO_SUPPORTING_EVIDENCE")

    if not usable_matches:
        system_status = SYSTEM_NOT_SUPPORTED
    elif any(item in fail_types for item in {CHECK_SPECIFIC_STANDARD, CHECK_VALIDITY_DATE, CHECK_MINIMUM_COUNT, CHECK_SUBJECT_IDENTITY}):
        system_status = SYSTEM_NOT_SUPPORTED
    elif has_fail:
        system_status = SYSTEM_PARTIALLY_SUPPORTED
    elif has_unknown:
        if confirmed_current and not ({"STALE_MATCH_REVIEW", "STALE_EVIDENCE_REVIEW"} & set(warning_codes)):
            system_status = SYSTEM_PARTIALLY_SUPPORTED
        else:
            system_status = SYSTEM_REVIEW_REQUIRED
    elif confirmed_current and not ({"STALE_MATCH_REVIEW", "STALE_EVIDENCE_REVIEW"} & set(warning_codes)):
        system_status = SYSTEM_SUPPORTED
    else:
        system_status = SYSTEM_REVIEW_REQUIRED

    fingerprint = _assessment_fingerprint(
        requirement_row=requirement_row,
        system_status=system_status,
        applicability_context=applicability_context,
        warning_codes=warning_codes,
        checks=checks,
        used_matches=usable_matches,
        reference_date=reference_date,
    )

    return AssessmentDraft(
        requirement_id=str(requirement_row["requirement_id"]),
        system_status=system_status,
        applicability_context=applicability_context,
        assessment_summary=_make_summary(system_status, checks),
        warning_codes=sorted(dict.fromkeys(warning_codes)),
        checks=checks,
        fingerprint=fingerprint,
    )


def _assessment_query(tender_id: str, company_id: str):
    return (
        select(RequirementComplianceAssessment)
        .where(
            RequirementComplianceAssessment.tender_id == tender_id,
            RequirementComplianceAssessment.company_id == company_id,
        )
        .options(
            selectinload(RequirementComplianceAssessment.requirement),
            selectinload(RequirementComplianceAssessment.company),
            selectinload(RequirementComplianceAssessment.checks).selectinload(RequirementComplianceCheck.company_evidence).selectinload(CompanyEvidence.source_document),
            selectinload(RequirementComplianceAssessment.checks).selectinload(RequirementComplianceCheck.company_evidence).selectinload(CompanyEvidence.review),
            selectinload(RequirementComplianceAssessment.checks).selectinload(RequirementComplianceCheck.match).selectinload(RequirementEvidenceCandidateMatch.review),
            selectinload(RequirementComplianceAssessment.checks).selectinload(RequirementComplianceCheck.match).selectinload(RequirementEvidenceCandidateMatch.company_evidence).selectinload(CompanyEvidence.source_document),
            selectinload(RequirementComplianceAssessment.checks).selectinload(RequirementComplianceCheck.match).selectinload(RequirementEvidenceCandidateMatch.company_evidence).selectinload(CompanyEvidence.review),
        )
        .order_by(RequirementComplianceAssessment.created_at.asc(), RequirementComplianceAssessment.id.asc())
    )


def _serialize_check_row(row: RequirementComplianceCheck) -> dict[str, Any]:
    return {
        "id": row.id,
        "assessment_id": row.assessment_id,
        "check_type": row.check_type,
        "check_status": row.check_status,
        "expected_value": row.expected_value,
        "observed_value": row.observed_value,
        "rationale": row.rationale,
        "company_evidence_id": row.company_evidence_id,
        "match_id": row.match_id,
        "created_at": row.created_at,
        "company_evidence": _serialize_evidence_row(row.company_evidence) if row.company_evidence is not None else None,
        "match": _serialize_match_row(row.match) if row.match is not None else None,
    }


def _serialize_assessment_row(row: RequirementComplianceAssessment, requirement_row: dict[str, Any]) -> dict[str, Any]:
    checks = [_serialize_check_row(check) for check in sorted(row.checks, key=lambda item: (item.check_type, item.id))]
    return {
        "id": row.id,
        "tender_id": row.tender_id,
        "company_id": row.company_id,
        "requirement_id": row.requirement_id,
        "system_status": row.system_status,
        "applicability_context": row.applicability_context,
        "assessment_summary": row.assessment_summary,
        "warning_codes": _load_json_list(row.warning_codes_json),
        "evaluator_version": row.evaluator_version,
        "assessment_fingerprint": row.assessment_fingerprint,
        "evaluated_at": row.evaluated_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "requirement": {
            "requirement_id": requirement_row["requirement_id"],
            "canonical_text": requirement_row["canonical_text"],
            "category": requirement_row["category"],
            "applicability": requirement_row["applicability"],
            "condition_text": requirement_row["condition_text"],
            "effective_status": requirement_row["effective_status"],
            "interpretation_status": requirement_row["interpretation_status"],
            "evidence_mode": requirement_row["evidence_mode"],
            "expected_evidence": requirement_row["expected_evidence"],
            "review_status": requirement_row["review_status"],
            "review_freshness": requirement_row["review_freshness"],
            "primary_source": requirement_row["primary_source"],
            "representation_fingerprint": requirement_row["representation_fingerprint"],
        },
        "company": {
            "id": row.company.id,
            "name": row.company.name,
        },
        "checks": checks,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "requirements_considered": len(rows),
        "supported_count": sum(1 for row in rows if row["system_status"] == SYSTEM_SUPPORTED),
        "partially_supported_count": sum(1 for row in rows if row["system_status"] == SYSTEM_PARTIALLY_SUPPORTED),
        "not_supported_count": sum(1 for row in rows if row["system_status"] == SYSTEM_NOT_SUPPORTED),
        "review_required_count": sum(1 for row in rows if row["system_status"] == SYSTEM_REVIEW_REQUIRED),
        "not_evaluated_count": sum(1 for row in rows if row["system_status"] == SYSTEM_NOT_EVALUATED),
        "condition_unresolved_count": sum(1 for row in rows if row["applicability_context"] == CONDITION_UNRESOLVED),
    }


def analyze_tender_company_compliance(db: Session, tender_id: str, company_id: str) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    company = _company_or_404(db, company_id)

    matrix = get_tender_requirement_matrix(db, tender_id)
    requirement_rows = matrix["requirements"]
    requirement_lookup = {row["requirement_id"]: row for row in requirement_rows}

    all_matches = _matches_for_requirement(db, tender_id, company_id)
    by_requirement: dict[str, list[RequirementEvidenceCandidateMatch]] = {}
    for row in all_matches:
        if row.requirement_id not in requirement_lookup:
            continue
        if row.company_id != company_id or row.company_evidence.company_id != company_id:
            continue
        by_requirement.setdefault(row.requirement_id, []).append(row)

    existing_rows = db.execute(_assessment_query(tender_id, company_id)).scalars().all()
    existing_by_requirement = {row.requirement_id: row for row in existing_rows}

    active_requirement_ids: set[str] = set()
    for requirement_row in requirement_rows:
        requirement_id = str(requirement_row["requirement_id"])
        if _is_requirement_rejected(requirement_row):
            continue
        active_requirement_ids.add(requirement_id)
        draft = _evaluate_requirement(
            db,
            tender_id=tender_id,
            company=company,
            requirement_row=requirement_row,
            matches=by_requirement.get(requirement_id, []),
        )

        row = existing_by_requirement.get(requirement_id)
        if row is None:
            row = RequirementComplianceAssessment(
                tender_id=tender_id,
                company_id=company_id,
                requirement_id=requirement_id,
            )
            db.add(row)

        row.system_status = draft.system_status
        row.applicability_context = draft.applicability_context
        row.assessment_summary = draft.assessment_summary
        row.warning_codes_json = _dump_json_list(draft.warning_codes)
        row.evaluator_version = COMPLIANCE_EVALUATOR_VERSION
        row.assessment_fingerprint = draft.fingerprint
        row.evaluated_at = datetime.now(timezone.utc)

        db.flush()

        db.execute(
            delete(RequirementComplianceCheck).where(
                RequirementComplianceCheck.tender_id == tender_id,
                RequirementComplianceCheck.company_id == company_id,
                RequirementComplianceCheck.requirement_id == requirement_id,
            )
        )
        db.flush()

        for check in draft.checks:
            db.add(
                RequirementComplianceCheck(
                    assessment=row,
                    tender_id=tender_id,
                    company_id=company_id,
                    requirement_id=requirement_id,
                    check_type=check.check_type,
                    check_status=check.check_status,
                    expected_value=check.expected_value,
                    observed_value=check.observed_value,
                    rationale=check.rationale,
                    company_evidence_id=check.company_evidence_id,
                    match_id=check.match_id,
                )
            )

    for row in existing_rows:
        if row.requirement_id in active_requirement_ids:
            continue
        db.delete(row)

    db.flush()
    # Clear in-session relationship state so serialization reflects persisted rows only.
    db.expire_all()
    return list_tender_company_compliance_assessments(db, tender_id, company_id)


def list_tender_company_compliance_assessments(
    db: Session,
    tender_id: str,
    company_id: str,
    *,
    system_status: str | None = None,
    requirement_id: str | None = None,
    category: str | None = None,
    applicability_context: str | None = None,
) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)

    matrix = get_tender_requirement_matrix(db, tender_id)
    requirement_lookup = {row["requirement_id"]: row for row in matrix["requirements"]}

    rows = db.execute(_assessment_query(tender_id, company_id)).scalars().all()
    normalized_status = (system_status or "").strip().upper() or None
    normalized_requirement_id = (requirement_id or "").strip() or None
    normalized_category = (category or "").strip().upper() or None
    normalized_applicability = (applicability_context or "").strip().upper() or None

    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        requirement_row = requirement_lookup.get(row.requirement_id)
        if requirement_row is None:
            continue
        if normalized_status and row.system_status != normalized_status:
            continue
        if normalized_requirement_id and row.requirement_id != normalized_requirement_id:
            continue
        if normalized_category and str(requirement_row.get("category") or "").upper() != normalized_category:
            continue
        if normalized_applicability and row.applicability_context != normalized_applicability:
            continue
        payload_rows.append(_serialize_assessment_row(row, requirement_row))

    payload_rows.sort(
        key=lambda item: (
            0 if item["system_status"] in {SYSTEM_NOT_SUPPORTED, SYSTEM_REVIEW_REQUIRED, SYSTEM_PARTIALLY_SUPPORTED} else 1,
            str(item["requirement"]["canonical_text"]).lower(),
            item["requirement_id"],
        )
    )

    return {
        "tender_id": tender_id,
        "company_id": company_id,
        "evaluator_version": COMPLIANCE_EVALUATOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _summary(payload_rows),
        "assessments": payload_rows,
    }


def get_requirement_compliance_assessment(
    db: Session,
    tender_id: str,
    company_id: str,
    requirement_id: str,
) -> dict[str, Any]:
    payload = list_tender_company_compliance_assessments(
        db,
        tender_id,
        company_id,
        requirement_id=requirement_id,
    )
    if not payload["assessments"]:
        raise HTTPException(status_code=404, detail="Compliance assessment not found for the selected requirement")
    return payload
