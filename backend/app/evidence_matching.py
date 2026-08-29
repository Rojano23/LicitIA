from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.company_evidence import _serialize_evidence_row
from app.models import (
    Company,
    CompanyEvidence,
    CompanyEvidenceAnalysisStatus,
    CompanyEvidenceReviewStatus,
    Requirement,
    RequirementEvidenceCandidateMatch,
    RequirementEvidenceCandidateMatchOrigin,
    RequirementEvidenceCandidateMatchStrength,
    RequirementEvidenceCandidateReview,
    RequirementEvidenceCandidateReviewStatus,
    Tender,
)
from app.requirement_matrix import get_tender_requirement_matrix

EVIDENCE_MATCHER_VERSION = "mvp-05.3"
HUMAN_MATCHER_VERSION = "human-manual-entry"

MATCH_STRONG = RequirementEvidenceCandidateMatchStrength.STRONG.value
MATCH_POSSIBLE = RequirementEvidenceCandidateMatchStrength.POSSIBLE.value
MATCH_REVIEW_REQUIRED = RequirementEvidenceCandidateMatchStrength.REVIEW_REQUIRED.value

ORIGIN_DETERMINISTIC = RequirementEvidenceCandidateMatchOrigin.DETERMINISTIC.value
ORIGIN_HUMAN = RequirementEvidenceCandidateMatchOrigin.HUMAN.value

REVIEW_PENDING = RequirementEvidenceCandidateReviewStatus.PENDING.value
REVIEW_CONFIRMED = RequirementEvidenceCandidateReviewStatus.CONFIRMED.value
REVIEW_NEEDS_REVIEW = RequirementEvidenceCandidateReviewStatus.NEEDS_REVIEW.value
REVIEW_REJECTED = RequirementEvidenceCandidateReviewStatus.REJECTED.value

FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_NOT_REVIEWED = "NOT_REVIEWED"

BASIS_EVIDENCE_TYPE = "EVIDENCE_TYPE"
BASIS_EXPECTED_EVIDENCE_TEXT = "EXPECTED_EVIDENCE_TEXT"
BASIS_REQUIREMENT_FACT = "REQUIREMENT_FACT"
BASIS_SUBJECT_CONTEXT = "SUBJECT_CONTEXT"
BASIS_MANUAL = "MANUAL"

SCOPE_NOTE = (
    "LicitIA propone evidencias que podrían ser relevantes para cada requisito. "
    "Una asociación confirmada indica que la evidencia es pertinente para evaluar el requisito; "
    "no significa que el requisito esté cumplido."
)

_SPACE_RE = re.compile(r"\s+")
_ISO_RE = re.compile(r"\biso[\s\-]*([0-9]{4,5})(?::[\s\-]*([0-9]{4}))?\b", re.IGNORECASE)


@dataclass(slots=True)
class MatchDraft:
    requirement_id: str
    company_evidence_id: str
    match_strength: str
    match_basis: list[str]
    match_rationale: str
    system_warnings: list[str]
    requirement_fingerprint: str
    evidence_fingerprint: str
    match_fingerprint: str


def _normalize_space(value: str | None) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip())


def _normalize_for_match(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return _normalize_space(without_marks).lower()


def _dump_json_list(values: list[str]) -> str:
    return json.dumps(sorted(dict.fromkeys(values)), ensure_ascii=True)


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


def _match_fingerprint(
    *,
    requirement_fingerprint: str,
    evidence_fingerprint: str,
    match_strength: str,
    match_basis: list[str],
    match_rationale: str,
    system_warnings: list[str],
    origin: str,
) -> str:
    payload = {
        "requirement_fingerprint": requirement_fingerprint,
        "evidence_fingerprint": evidence_fingerprint,
        "match_strength": match_strength,
        "match_basis": sorted(dict.fromkeys(match_basis)),
        "match_rationale": _normalize_space(match_rationale),
        "system_warnings": sorted(dict.fromkeys(system_warnings)),
        "origin": origin,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _review_freshness(review: RequirementEvidenceCandidateReview | None, current_fingerprint: str) -> str:
    if review is None:
        return FRESHNESS_NOT_REVIEWED
    if review.review_status == REVIEW_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not review.reviewed_fingerprint:
        return FRESHNESS_STALE
    if review.reviewed_fingerprint != current_fingerprint:
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


def _requirement_or_404(db: Session, tender_id: str, requirement_id: str) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None or requirement.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Requirement not found for the selected Tender")
    return requirement


def _match_or_404(db: Session, tender_id: str, company_id: str, match_id: str) -> RequirementEvidenceCandidateMatch:
    match = db.execute(
        select(RequirementEvidenceCandidateMatch)
        .where(RequirementEvidenceCandidateMatch.id == match_id)
        .options(
            selectinload(RequirementEvidenceCandidateMatch.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence)
            .selectinload(CompanyEvidence.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence)
            .selectinload(CompanyEvidence.source_document),
        )
    ).scalar_one_or_none()
    if match is None or match.tender_id != tender_id or match.company_id != company_id:
        raise HTTPException(status_code=404, detail="Evidence match candidate not found")
    if match.company_evidence.company_id != company_id:
        raise HTTPException(status_code=400, detail="Evidence match company mismatch")
    return match


def _requirement_rows_for_matching(
    db: Session,
    tender_id: str,
    *,
    include_historical: bool,
    requirement_id: str | None,
) -> list[dict[str, Any]]:
    matrix = get_tender_requirement_matrix(db, tender_id)
    rows = matrix["requirements"]
    lookup = {row["requirement_id"]: row for row in rows}

    if requirement_id is not None:
        row = lookup.get(requirement_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Requirement not found for the selected Tender")
        return [row]

    if include_historical:
        return rows

    out: list[dict[str, Any]] = []
    for row in rows:
        if row["review_status"] == "REJECTED":
            continue
        if row["effective_status"] == "SUPERSEDED":
            continue
        out.append(row)
    return out


def _row_warning_codes(requirement_row: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if requirement_row["applicability"] == "CONDITIONAL":
        warnings.append("CONDITIONAL_APPLICABILITY_NOT_EVALUATED")
    if requirement_row["effective_status"] == "AMBIGUOUS":
        warnings.append("REQUIREMENT_EFFECTIVE_STATE_UNRESOLVED")
    if requirement_row["effective_status"] == "UNRESOLVED":
        warnings.append("REQUIREMENT_EFFECTIVE_STATE_UNRESOLVED")
    if requirement_row["evidence_mode"] == "DIRECT_VERIFICATION":
        warnings.append("DIRECT_VERIFICATION_NOT_COMPANY_EVIDENCE")
    if requirement_row["evidence_mode"] == "UNSPECIFIED":
        warnings.append("EXPECTED_ARTIFACT_UNSPECIFIED")
    if requirement_row["evidence_mode"] == "REVIEW_REQUIRED":
        warnings.append("REQUIREMENT_EVIDENCE_DEFINITION_REVIEW_REQUIRED")
    if requirement_row["review_status"] == "REJECTED":
        warnings.append("REQUIREMENT_REJECTED_BY_HUMAN")
    return warnings


def _requirement_allows_automatic_matching(requirement_row: dict[str, Any]) -> bool:
    if requirement_row["review_status"] == "REJECTED":
        return False
    if requirement_row["effective_status"] != "EFFECTIVE":
        return False
    if requirement_row["evidence_mode"] == "DIRECT_VERIFICATION":
        return False
    return True


def _evidence_is_usable_for_automatic_matching(evidence: CompanyEvidence) -> bool:
    review_status = evidence.review.review_status if evidence.review is not None else CompanyEvidenceReviewStatus.PENDING.value
    if review_status == CompanyEvidenceReviewStatus.REJECTED.value:
        return False
    if evidence.source_document.archived_at is not None:
        return False
    if not evidence.source_document.is_current:
        return False
    return True


def _evidence_review_warning_codes(evidence: CompanyEvidence) -> list[str]:
    warnings: list[str] = []
    review_status = evidence.review.review_status if evidence.review is not None else CompanyEvidenceReviewStatus.PENDING.value
    if review_status == CompanyEvidenceReviewStatus.PENDING.value:
        warnings.append("EVIDENCE_HUMAN_REVIEW_PENDING")
    elif review_status == CompanyEvidenceReviewStatus.NEEDS_REVIEW.value:
        warnings.append("EVIDENCE_HUMAN_REVIEW_REQUIRED")
    if evidence.review is not None and evidence.review.reviewed_fingerprint and evidence.review.reviewed_fingerprint != evidence.semantic_fingerprint:
        warnings.append("EVIDENCE_HUMAN_REVIEW_STALE")
    if evidence.analysis_status == CompanyEvidenceAnalysisStatus.REVIEW_REQUIRED.value:
        warnings.append("EVIDENCE_INTERPRETATION_REVIEW_REQUIRED")
    return warnings


def _joined_requirement_text(requirement_row: dict[str, Any]) -> str:
    fragments = [str(requirement_row["canonical_text"])]
    for item in requirement_row.get("expected_evidence", []):
        description = _normalize_space(item.get("evidence_description"))
        if description:
            fragments.append(description)
    primary_source = requirement_row.get("primary_source")
    if primary_source and primary_source.get("requirement_text"):
        fragments.append(str(primary_source["requirement_text"]))
    return " ".join(fragments)


def _joined_evidence_text(evidence: CompanyEvidence) -> str:
    pieces = [
        evidence.canonical_statement,
        evidence.source_excerpt,
        evidence.reference_number,
        evidence.issuer,
        evidence.subject_name,
    ]
    return " ".join(_normalize_space(piece) for piece in pieces if _normalize_space(piece))


def _extract_iso_standard_code(text: str) -> str | None:
    match = _ISO_RE.search(text)
    if not match:
        return None
    return match.group(1)


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _requirement_family(requirement_row: dict[str, Any]) -> str | None:
    text = _normalize_for_match(_joined_requirement_text(requirement_row))
    expectation_types = {str(item.get("evidence_type") or "") for item in requirement_row.get("expected_evidence", [])}

    if _contains_any(text, ("seguridad social", "imss", "infonavit")):
        return "SOCIAL_SECURITY_COMPLIANCE"
    if _contains_any(text, ("opinion positiva", "opinion de cumplimiento", "cumplimiento fiscal")):
        return "TAX_COMPLIANCE"
    if "rfc" in text or "registro federal de contribuyentes" in text or "constancia fiscal" in text:
        return "TAX_REGISTRATION"
    if "acta constitutiva" in text or "existencia legal" in text or "constitucion" in text or "constitutiva" in text:
        return "CORPORATE_EXISTENCE"
    if _contains_any(text, ("representante legal", "apoderado", "facultades", "poder")):
        return "LEGAL_AUTHORITY"
    if "experiencia" in text or "servicios similares" in text or "contratos" in text:
        return "EXPERIENCE"
    if _contains_any(text, ("curriculum", "curriculum vitae", "cedula", "titulo", "licencia profesional", "personal propuesto")):
        return "PERSONNEL_QUALIFICATION"
    if "certificacion" in text or _extract_iso_standard_code(text) is not None or "CERTIFICATE" in expectation_types:
        return "CERTIFICATION"
    if "hiip" in text or "padron" in text or "registro" in text or "inscripcion" in text:
        return "REGISTRATION"
    if "garantia" in text or "fianza" in text:
        return "GUARANTEE"
    if "carta de respaldo" in text or "carta" in text or "propuesta comercial" in text:
        return "COMMERCIAL_DOCUMENT"
    return None


def _match_strength_for_mode(match_strength: str, requirement_row: dict[str, Any], warnings: list[str]) -> str:
    evidence_mode = requirement_row["evidence_mode"]
    if evidence_mode == "UNSPECIFIED" and match_strength == MATCH_STRONG:
        return MATCH_POSSIBLE
    if evidence_mode == "REVIEW_REQUIRED":
        warnings.append("REQUIREMENT_EVIDENCE_DEFINITION_REVIEW_REQUIRED")
        return MATCH_REVIEW_REQUIRED
    return match_strength


def _build_draft(
    *,
    requirement_row: dict[str, Any],
    evidence: CompanyEvidence,
    match_strength: str,
    match_basis: list[str],
    match_rationale: str,
    system_warnings: list[str],
    origin: str,
) -> MatchDraft:
    warnings = sorted(dict.fromkeys(system_warnings))
    basis = sorted(dict.fromkeys(match_basis))
    effective_strength = _match_strength_for_mode(match_strength, requirement_row, warnings)
    requirement_fingerprint = str(requirement_row["representation_fingerprint"])
    evidence_fingerprint = evidence.semantic_fingerprint
    fingerprint = _match_fingerprint(
        requirement_fingerprint=requirement_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        match_strength=effective_strength,
        match_basis=basis,
        match_rationale=match_rationale,
        system_warnings=warnings,
        origin=origin,
    )
    return MatchDraft(
        requirement_id=str(requirement_row["requirement_id"]),
        company_evidence_id=evidence.id,
        match_strength=effective_strength,
        match_basis=basis,
        match_rationale=match_rationale,
        system_warnings=warnings,
        requirement_fingerprint=requirement_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        match_fingerprint=fingerprint,
    )


def _draft_for_pair(requirement_row: dict[str, Any], evidence: CompanyEvidence) -> MatchDraft | None:
    family = _requirement_family(requirement_row)
    if family is None:
        return None

    requirement_text = _normalize_for_match(_joined_requirement_text(requirement_row))
    evidence_text = _normalize_for_match(_joined_evidence_text(evidence))
    warnings = _row_warning_codes(requirement_row) + _evidence_review_warning_codes(evidence)

    if family == "CERTIFICATION":
        if evidence.evidence_type != "CERTIFICATION":
            return None
        required_iso_code = _extract_iso_standard_code(requirement_text)
        evidence_iso_code = _extract_iso_standard_code(evidence_text)
        if required_iso_code is not None:
            if evidence_iso_code != required_iso_code:
                return None
            rationale = (
                f"La evidencia de certificación menciona ISO {required_iso_code} y coincide con el estándar esperado del requisito. "
                "La alineación se evalúa por estándar para pertinencia, sin resolver edición o vigencia en este paso."
            )
            basis = [BASIS_EVIDENCE_TYPE, BASIS_EXPECTED_EVIDENCE_TEXT]
        else:
            rationale = "La evidencia pertenece a la familia de certificación solicitada por el requisito."
            basis = [BASIS_EVIDENCE_TYPE]
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=basis,
            match_rationale=rationale,
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "TAX_REGISTRATION":
        if evidence.evidence_type != "TAX_REGISTRATION":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=[BASIS_EVIDENCE_TYPE, BASIS_REQUIREMENT_FACT],
            match_rationale="La evidencia fiscal describe registro con RFC y es relevante para un requisito de registro fiscal.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "TAX_COMPLIANCE":
        if evidence.evidence_type != "TAX_COMPLIANCE":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=[BASIS_EVIDENCE_TYPE, BASIS_REQUIREMENT_FACT],
            match_rationale="La evidencia describe cumplimiento fiscal y puede ser pertinente para evaluar una opinión o constancia fiscal positiva.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "SOCIAL_SECURITY_COMPLIANCE":
        if evidence.evidence_type != "SOCIAL_SECURITY_COMPLIANCE":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=[BASIS_EVIDENCE_TYPE, BASIS_REQUIREMENT_FACT],
            match_rationale="La evidencia corresponde a cumplimiento de seguridad social y no se sustituyó por evidencia fiscal distinta.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "LEGAL_AUTHORITY":
        if evidence.evidence_type != "LEGAL_AUTHORITY":
            return None
        basis = [BASIS_EVIDENCE_TYPE]
        if evidence.subject_kind == "PERSON":
            basis.append(BASIS_SUBJECT_CONTEXT)
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=basis,
            match_rationale="La evidencia trata facultades o representación legal, por lo que puede ser pertinente para evaluar este requisito.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "CORPORATE_EXISTENCE":
        if evidence.evidence_type != "CORPORATE_EXISTENCE":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=[BASIS_EVIDENCE_TYPE],
            match_rationale="La evidencia documenta existencia corporativa o constitución de la empresa.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "PERSONNEL_QUALIFICATION":
        if evidence.evidence_type != "PERSONNEL_QUALIFICATION":
            return None
        basis = [BASIS_EVIDENCE_TYPE]
        if evidence.subject_kind == "PERSON":
            basis.append(BASIS_SUBJECT_CONTEXT)
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=basis,
            match_rationale="La evidencia corresponde a credenciales o calificaciones de personal y puede apoyar la evaluación del requisito de personal.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "EXPERIENCE":
        if evidence.evidence_type != "EXPERIENCE":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_POSSIBLE,
            match_basis=[BASIS_EVIDENCE_TYPE, BASIS_REQUIREMENT_FACT],
            match_rationale="La evidencia documenta experiencia o servicios previos y puede ser relevante para evaluar requisitos de experiencia, sin concluir suficiencia.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "REGISTRATION":
        if evidence.evidence_type != "REGISTRATION":
            return None
        basis = [BASIS_EVIDENCE_TYPE, BASIS_REQUIREMENT_FACT]
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=basis,
            match_rationale="La evidencia documenta un registro o padrón que es semánticamente relevante para el requisito.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "GUARANTEE":
        if evidence.evidence_type != "GUARANTEE":
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_STRONG,
            match_basis=[BASIS_EVIDENCE_TYPE],
            match_rationale="La evidencia pertenece a la familia de garantías solicitada por el requisito.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    if family == "COMMERCIAL_DOCUMENT":
        if evidence.evidence_type not in {"COMMERCIAL_DOCUMENT", "OTHER"}:
            return None
        if "fabricante" in requirement_text and "fabricante" not in evidence_text:
            return None
        return _build_draft(
            requirement_row=requirement_row,
            evidence=evidence,
            match_strength=MATCH_REVIEW_REQUIRED if evidence.evidence_type == "OTHER" else MATCH_POSSIBLE,
            match_basis=[BASIS_EVIDENCE_TYPE, BASIS_EXPECTED_EVIDENCE_TEXT],
            match_rationale="La evidencia comparte la familia documental comercial del requisito y requiere revisión humana para confirmar pertinencia exacta.",
            system_warnings=warnings,
            origin=ORIGIN_DETERMINISTIC,
        )

    return None


def _serialize_review(review: RequirementEvidenceCandidateReview | None) -> dict[str, Any] | None:
    if review is None:
        return None
    return {
        "id": review.id,
        "match_id": review.match_id,
        "tender_id": review.tender_id,
        "company_id": review.company_id,
        "review_status": review.review_status,
        "review_note": review.review_note,
        "reviewed_fingerprint": review.reviewed_fingerprint,
        "reviewed_at": review.reviewed_at,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def _serialize_match_row(match: RequirementEvidenceCandidateMatch) -> dict[str, Any]:
    return {
        "id": match.id,
        "tender_id": match.tender_id,
        "requirement_id": match.requirement_id,
        "company_id": match.company_id,
        "company_evidence_id": match.company_evidence_id,
        "match_strength": match.match_strength,
        "match_basis": _load_json_list(match.match_basis_json),
        "match_rationale": match.match_rationale,
        "system_warnings": _load_json_list(match.system_warnings_json),
        "origin": match.origin,
        "matcher_version": match.matcher_version,
        "requirement_fingerprint": match.requirement_fingerprint,
        "evidence_fingerprint": match.evidence_fingerprint,
        "match_fingerprint": match.match_fingerprint,
        "is_active": match.is_active,
        "review_freshness": _review_freshness(match.review, match.match_fingerprint),
        "created_at": match.created_at,
        "updated_at": match.updated_at,
        "company_evidence": _serialize_evidence_row(match.company_evidence),
        "review": _serialize_review(match.review),
    }


def _summary_payload(requirement_rows: list[dict[str, Any]]) -> dict[str, int]:
    all_matches = [match for row in requirement_rows for match in row["matches"]]
    return {
        "requirements_evaluated": len(requirement_rows),
        "requirements_with_candidate_evidence": sum(1 for row in requirement_rows if row["candidate_count"] > 0),
        "candidate_associations": len(all_matches),
        "strong_candidates": sum(1 for match in all_matches if match["match_strength"] == MATCH_STRONG),
        "possible_candidates": sum(1 for match in all_matches if match["match_strength"] == MATCH_POSSIBLE),
        "review_required_candidates": sum(1 for match in all_matches if match["match_strength"] == MATCH_REVIEW_REQUIRED),
        "human_confirmed_associations": sum(
            1 for match in all_matches if match["review"] is not None and match["review"]["review_status"] == REVIEW_CONFIRMED
        ),
        "rejected_associations": sum(
            1 for match in all_matches if match["review"] is not None and match["review"]["review_status"] == REVIEW_REJECTED
        ),
    }


def _build_requirement_row_payload(requirement_row: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "requirement_id": requirement_row["requirement_id"],
        "canonical_text": requirement_row["canonical_text"],
        "category": requirement_row["category"],
        "normalization_status": requirement_row["normalization_status"],
        "source_occurrence_count": requirement_row["source_occurrence_count"],
        "primary_source": requirement_row["primary_source"],
        "applicability": requirement_row["applicability"],
        "condition_text": requirement_row["condition_text"],
        "interpretation_status": requirement_row["interpretation_status"],
        "interpretation_reason": requirement_row["interpretation_reason"],
        "evidence_mode": requirement_row["evidence_mode"],
        "expected_evidence": requirement_row["expected_evidence"],
        "effective_status": requirement_row["effective_status"],
        "effective_source_document_id": requirement_row["effective_source_document_id"],
        "effective_source_filename": requirement_row["effective_source_filename"],
        "effective_reasons": requirement_row["effective_reasons"],
        "requirement_system_warnings": requirement_row["system_warnings"],
        "requirement_review_status": requirement_row["review_status"],
        "requirement_review_note": requirement_row["review_note"],
        "requirement_review_freshness": requirement_row["review_freshness"],
        "representation_fingerprint": requirement_row["representation_fingerprint"],
        "matching_warnings": _row_warning_codes(requirement_row),
        "candidate_count": len(matches),
        "matches": matches,
    }


def _all_match_rows_query(tender_id: str, company_id: str):
    return (
        select(RequirementEvidenceCandidateMatch)
        .where(
            RequirementEvidenceCandidateMatch.tender_id == tender_id,
            RequirementEvidenceCandidateMatch.company_id == company_id,
        )
        .options(
            selectinload(RequirementEvidenceCandidateMatch.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence)
            .selectinload(CompanyEvidence.review),
            selectinload(RequirementEvidenceCandidateMatch.company_evidence)
            .selectinload(CompanyEvidence.source_document),
        )
        .order_by(RequirementEvidenceCandidateMatch.created_at.asc(), RequirementEvidenceCandidateMatch.id.asc())
    )


def _refresh_manual_matches(
    requirement_lookup: dict[str, dict[str, Any]],
    matches: list[RequirementEvidenceCandidateMatch],
) -> None:
    for match in matches:
        if match.origin != ORIGIN_HUMAN:
            continue
        requirement_row = requirement_lookup.get(match.requirement_id)
        if requirement_row is None:
            match.is_active = False
            continue
        match.requirement_fingerprint = str(requirement_row["representation_fingerprint"])
        match.evidence_fingerprint = match.company_evidence.semantic_fingerprint
        match.match_fingerprint = _match_fingerprint(
            requirement_fingerprint=match.requirement_fingerprint,
            evidence_fingerprint=match.evidence_fingerprint,
            match_strength=match.match_strength,
            match_basis=_load_json_list(match.match_basis_json),
            match_rationale=match.match_rationale,
            system_warnings=_load_json_list(match.system_warnings_json),
            origin=match.origin,
        )
        match.is_active = _requirement_allows_automatic_matching(requirement_row) and _evidence_is_usable_for_automatic_matching(match.company_evidence)


def analyze_tender_company_evidence_matches(db: Session, tender_id: str, company_id: str) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)

    requirement_rows = _requirement_rows_for_matching(
        db,
        tender_id,
        include_historical=True,
        requirement_id=None,
    )
    requirement_lookup = {row["requirement_id"]: row for row in requirement_rows}

    evidence_rows = db.execute(
        select(CompanyEvidence)
        .where(CompanyEvidence.company_id == company_id)
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
        .order_by(CompanyEvidence.created_at.asc(), CompanyEvidence.id.asc())
    ).scalars().all()

    existing_matches = db.execute(_all_match_rows_query(tender_id, company_id)).scalars().all()
    existing_by_key = {
        (match.requirement_id, match.company_evidence_id, match.origin): match
        for match in existing_matches
    }

    _refresh_manual_matches(requirement_lookup, existing_matches)

    derived_keys: set[tuple[str, str, str]] = set()
    for requirement_row in requirement_rows:
        if not _requirement_allows_automatic_matching(requirement_row):
            continue
        for evidence in evidence_rows:
            if not _evidence_is_usable_for_automatic_matching(evidence):
                continue
            draft = _draft_for_pair(requirement_row, evidence)
            if draft is None:
                continue
            key = (draft.requirement_id, draft.company_evidence_id, ORIGIN_DETERMINISTIC)
            derived_keys.add(key)
            row = existing_by_key.get(key)
            if row is None:
                row = RequirementEvidenceCandidateMatch(
                    tender_id=tender_id,
                    requirement_id=draft.requirement_id,
                    company_id=company_id,
                    company_evidence_id=draft.company_evidence_id,
                    origin=ORIGIN_DETERMINISTIC,
                )
                db.add(row)
                existing_by_key[key] = row
            row.match_strength = draft.match_strength
            row.match_basis_json = _dump_json_list(draft.match_basis)
            row.match_rationale = draft.match_rationale
            row.system_warnings_json = _dump_json_list(draft.system_warnings)
            row.matcher_version = EVIDENCE_MATCHER_VERSION
            row.requirement_fingerprint = draft.requirement_fingerprint
            row.evidence_fingerprint = draft.evidence_fingerprint
            row.match_fingerprint = draft.match_fingerprint
            row.is_active = True

    for match in existing_matches:
        if match.origin != ORIGIN_DETERMINISTIC:
            continue
        key = (match.requirement_id, match.company_evidence_id, match.origin)
        match.is_active = key in derived_keys

    db.flush()
    return list_tender_company_evidence_match_candidates(db, tender_id, company_id)


def list_tender_company_evidence_match_candidates(
    db: Session,
    tender_id: str,
    company_id: str,
    *,
    requirement_id: str | None = None,
    match_strength: str | None = None,
    review_status: str | None = None,
    evidence_type: str | None = None,
    include_historical: bool = False,
) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)

    requirement_rows = _requirement_rows_for_matching(
        db,
        tender_id,
        include_historical=include_historical,
        requirement_id=requirement_id,
    )
    requirement_lookup = {row["requirement_id"]: row for row in requirement_rows}
    grouped_matches: dict[str, list[dict[str, Any]]] = {row["requirement_id"]: [] for row in requirement_rows}

    rows = db.execute(_all_match_rows_query(tender_id, company_id)).scalars().all()
    normalized_review_status = (review_status or "").strip().upper() or None
    normalized_match_strength = (match_strength or "").strip().upper() or None
    normalized_evidence_type = (evidence_type or "").strip().upper() or None

    for row in rows:
        requirement_row = requirement_lookup.get(row.requirement_id)
        if requirement_row is None:
            continue
        if not include_historical:
            if not row.is_active:
                continue
            if not _evidence_is_usable_for_automatic_matching(row.company_evidence):
                continue
        serialized = _serialize_match_row(row)
        actual_review_status = serialized["review"]["review_status"] if serialized["review"] is not None else REVIEW_PENDING
        if normalized_review_status and actual_review_status != normalized_review_status:
            continue
        if normalized_match_strength and serialized["match_strength"] != normalized_match_strength:
            continue
        if normalized_evidence_type and serialized["company_evidence"]["evidence_type"] != normalized_evidence_type:
            continue
        grouped_matches[row.requirement_id].append(serialized)

    payload_rows = [
        _build_requirement_row_payload(requirement_row, grouped_matches.get(requirement_row["requirement_id"], []))
        for requirement_row in requirement_rows
    ]
    payload_rows.sort(
        key=lambda row: (
            0 if row["candidate_count"] > 0 else 1,
            0 if row["effective_status"] == "EFFECTIVE" else 1,
            row["canonical_text"].lower(),
            row["requirement_id"],
        )
    )

    return {
        "tender_id": tender_id,
        "company_id": company_id,
        "matcher_version": EVIDENCE_MATCHER_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _summary_payload(payload_rows),
        "requirements": payload_rows,
    }


def get_requirement_evidence_match_candidates(
    db: Session,
    tender_id: str,
    company_id: str,
    requirement_id: str,
    *,
    include_historical: bool = False,
) -> dict[str, Any]:
    return list_tender_company_evidence_match_candidates(
        db,
        tender_id,
        company_id,
        requirement_id=requirement_id,
        include_historical=include_historical,
    )


def review_requirement_evidence_candidate_match(
    db: Session,
    tender_id: str,
    company_id: str,
    match_id: str,
    *,
    review_status: str,
    review_note: str | None,
) -> dict[str, Any]:
    normalized_review_status = (review_status or "").strip().upper()
    normalized_note = _normalize_space(review_note) or None
    if normalized_review_status not in {REVIEW_PENDING, REVIEW_CONFIRMED, REVIEW_NEEDS_REVIEW, REVIEW_REJECTED}:
        raise HTTPException(status_code=400, detail="Unsupported evidence match review status")
    if normalized_review_status == REVIEW_REJECTED and not normalized_note:
        raise HTTPException(status_code=400, detail="Rejected evidence match requires a review note")

    match = _match_or_404(db, tender_id, company_id, match_id)
    review = match.review
    if review is None:
        review = RequirementEvidenceCandidateReview(match_id=match.id, tender_id=tender_id, company_id=company_id)
        db.add(review)

    review.review_status = normalized_review_status
    review.review_note = normalized_note
    if normalized_review_status == REVIEW_PENDING:
        review.reviewed_fingerprint = None
        review.reviewed_at = None
    else:
        review.reviewed_fingerprint = match.match_fingerprint
        review.reviewed_at = datetime.now(timezone.utc)

    db.flush()
    return list_tender_company_evidence_match_candidates(db, tender_id, company_id)


def create_manual_requirement_evidence_candidate_match(
    db: Session,
    tender_id: str,
    company_id: str,
    requirement_id: str,
    *,
    company_evidence_id: str,
    rationale: str | None,
) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)
    _requirement_or_404(db, tender_id, requirement_id)

    requirement_rows = _requirement_rows_for_matching(db, tender_id, include_historical=True, requirement_id=requirement_id)
    requirement_row = requirement_rows[0]

    evidence = db.execute(
        select(CompanyEvidence)
        .where(CompanyEvidence.id == company_evidence_id)
        .options(selectinload(CompanyEvidence.review), selectinload(CompanyEvidence.source_document))
    ).scalar_one_or_none()
    if evidence is None or evidence.company_id != company_id:
        raise HTTPException(status_code=404, detail="Company evidence not found for the selected Company")

    existing = db.execute(
        select(RequirementEvidenceCandidateMatch)
        .where(
            RequirementEvidenceCandidateMatch.tender_id == tender_id,
            RequirementEvidenceCandidateMatch.requirement_id == requirement_id,
            RequirementEvidenceCandidateMatch.company_id == company_id,
            RequirementEvidenceCandidateMatch.company_evidence_id == company_evidence_id,
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Evidence association already exists for the selected requirement and company evidence")

    match_rationale = _normalize_space(rationale) or "Asociación manual registrada por el usuario para evaluación posterior."
    warnings = _row_warning_codes(requirement_row) + _evidence_review_warning_codes(evidence)
    match = RequirementEvidenceCandidateMatch(
        tender_id=tender_id,
        requirement_id=requirement_id,
        company_id=company_id,
        company_evidence_id=company_evidence_id,
        match_strength=MATCH_POSSIBLE,
        match_basis_json=_dump_json_list([BASIS_MANUAL]),
        match_rationale=match_rationale,
        system_warnings_json=_dump_json_list(warnings),
        origin=ORIGIN_HUMAN,
        matcher_version=HUMAN_MATCHER_VERSION,
        requirement_fingerprint=str(requirement_row["representation_fingerprint"]),
        evidence_fingerprint=evidence.semantic_fingerprint,
        match_fingerprint=_match_fingerprint(
            requirement_fingerprint=str(requirement_row["representation_fingerprint"]),
            evidence_fingerprint=evidence.semantic_fingerprint,
            match_strength=MATCH_POSSIBLE,
            match_basis=[BASIS_MANUAL],
            match_rationale=match_rationale,
            system_warnings=warnings,
            origin=ORIGIN_HUMAN,
        ),
        is_active=_requirement_allows_automatic_matching(requirement_row) and _evidence_is_usable_for_automatic_matching(evidence),
    )
    db.add(match)
    db.flush()

    db.add(
        RequirementEvidenceCandidateReview(
            match_id=match.id,
            tender_id=tender_id,
            company_id=company_id,
            review_status=REVIEW_CONFIRMED,
            review_note=match_rationale,
            reviewed_fingerprint=match.match_fingerprint,
            reviewed_at=datetime.now(timezone.utc),
        )
    )

    db.flush()
    return list_tender_company_evidence_match_candidates(db, tender_id, company_id)