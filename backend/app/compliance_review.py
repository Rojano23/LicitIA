from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compliance_evaluation import (
    SYSTEM_NOT_EVALUATED,
    SYSTEM_NOT_SUPPORTED,
    SYSTEM_PARTIALLY_SUPPORTED,
    SYSTEM_REVIEW_REQUIRED,
    SYSTEM_SUPPORTED,
    _company_or_404,
    _tender_or_404,
    list_tender_company_compliance_assessments,
)
from app.models import (
    RequirementComplianceApplicabilityContext,
    RequirementComplianceAssessment,
    RequirementComplianceDecision,
    RequirementComplianceDecisionStatus,
)
from app.requirement_matrix import get_tender_requirement_matrix

DECISION_PENDING = RequirementComplianceDecisionStatus.PENDING.value
DECISION_COMPLIES = RequirementComplianceDecisionStatus.COMPLIES.value
DECISION_DOES_NOT_COMPLY = RequirementComplianceDecisionStatus.DOES_NOT_COMPLY.value
DECISION_NEEDS_REVIEW = RequirementComplianceDecisionStatus.NEEDS_REVIEW.value
DECISION_NOT_APPLICABLE = RequirementComplianceDecisionStatus.NOT_APPLICABLE.value

FRESHNESS_NOT_REVIEWED = "NOT_REVIEWED"
FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"

RELATION_PENDING = "PENDING"
RELATION_ALIGNED = "ALIGNED"
RELATION_HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
RELATION_SYSTEM_UNDECIDED = "SYSTEM_UNDECIDED"

_ALLOWED_DECISION_STATUS = {
    DECISION_PENDING,
    DECISION_COMPLIES,
    DECISION_DOES_NOT_COMPLY,
    DECISION_NEEDS_REVIEW,
    DECISION_NOT_APPLICABLE,
}

_NON_REVIEWABLE_EFFECTIVE_STATUS = {"REJECTED", "SUPERSEDED"}

SCOPE_NOTE = (
    "La revisión humana de cumplimiento conserva la evaluación automática como referencia, "
    "pero la decisión final de cumplimiento es humana y puede confirmar, rechazar, marcar "
    "no aplicable o mantener en revisión cada requisito."
)


def _normalize_status(value: str) -> str:
    return (value or "").strip().upper()


def _normalize_note(value: str | None) -> str | None:
    note = (value or "").strip()
    return note or None


def _decision_freshness(decision: RequirementComplianceDecision | None, assessment_fingerprint: str) -> str:
    if decision is None:
        return FRESHNESS_NOT_REVIEWED
    if decision.decision_status == DECISION_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not decision.reviewed_assessment_fingerprint:
        return FRESHNESS_STALE
    if decision.reviewed_assessment_fingerprint != assessment_fingerprint:
        return FRESHNESS_STALE
    return FRESHNESS_CURRENT


def _decision_relation(system_status: str, decision_status: str) -> str:
    if decision_status == DECISION_PENDING:
        return RELATION_PENDING
    if decision_status == DECISION_NEEDS_REVIEW:
        return RELATION_SYSTEM_UNDECIDED
    if decision_status == DECISION_NOT_APPLICABLE:
        return RELATION_SYSTEM_UNDECIDED

    if decision_status == DECISION_COMPLIES:
        if system_status == SYSTEM_SUPPORTED:
            return RELATION_ALIGNED
        if system_status == SYSTEM_NOT_SUPPORTED:
            return RELATION_HUMAN_OVERRIDE
        return RELATION_SYSTEM_UNDECIDED

    if decision_status == DECISION_DOES_NOT_COMPLY:
        if system_status == SYSTEM_NOT_SUPPORTED:
            return RELATION_ALIGNED
        if system_status == SYSTEM_SUPPORTED:
            return RELATION_HUMAN_OVERRIDE
        return RELATION_SYSTEM_UNDECIDED

    return RELATION_SYSTEM_UNDECIDED


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "requirements_reviewable": len(rows),
        "pending_count": sum(1 for row in rows if row["human_decision"]["decision_status"] == DECISION_PENDING),
        "complies_count": sum(1 for row in rows if row["human_decision"]["decision_status"] == DECISION_COMPLIES),
        "does_not_comply_count": sum(1 for row in rows if row["human_decision"]["decision_status"] == DECISION_DOES_NOT_COMPLY),
        "needs_review_count": sum(1 for row in rows if row["human_decision"]["decision_status"] == DECISION_NEEDS_REVIEW),
        "not_applicable_count": sum(1 for row in rows if row["human_decision"]["decision_status"] == DECISION_NOT_APPLICABLE),
        "aligned_count": sum(1 for row in rows if row["decision_relation"] == RELATION_ALIGNED),
        "human_override_count": sum(1 for row in rows if row["decision_relation"] == RELATION_HUMAN_OVERRIDE),
        "system_undecided_count": sum(1 for row in rows if row["decision_relation"] == RELATION_SYSTEM_UNDECIDED),
        "stale_count": sum(1 for row in rows if row["human_decision"]["freshness"] == FRESHNESS_STALE),
        "current_count": sum(1 for row in rows if row["human_decision"]["freshness"] == FRESHNESS_CURRENT),
        "not_reviewed_count": sum(1 for row in rows if row["human_decision"]["freshness"] == FRESHNESS_NOT_REVIEWED),
    }


def _is_reviewable_requirement(requirement_row: dict[str, Any]) -> bool:
    effective_status = str(requirement_row.get("effective_status") or "").upper()
    review_status = str(requirement_row.get("review_status") or "").upper()
    if effective_status in _NON_REVIEWABLE_EFFECTIVE_STATUS:
        return False
    if review_status == "REJECTED":
        return False
    return True


def _note_is_required(
    *,
    decision_status: str,
    system_status: str,
    requirement_effective_status: str,
    applicability_context: str,
) -> bool:
    if decision_status in {DECISION_DOES_NOT_COMPLY, DECISION_NOT_APPLICABLE}:
        return True

    if decision_status not in {DECISION_COMPLIES, DECISION_DOES_NOT_COMPLY}:
        return False

    if system_status in {SYSTEM_PARTIALLY_SUPPORTED, SYSTEM_REVIEW_REQUIRED, SYSTEM_NOT_EVALUATED}:
        return True

    if requirement_effective_status in {"AMBIGUOUS", "UNRESOLVED"}:
        return True

    if applicability_context == RequirementComplianceApplicabilityContext.CONDITION_UNRESOLVED.value:
        return True

    if decision_status == DECISION_COMPLIES and system_status == SYSTEM_NOT_SUPPORTED:
        return True

    if decision_status == DECISION_DOES_NOT_COMPLY and system_status == SYSTEM_SUPPORTED:
        return True

    return False


def _compose_human_decision_row(
    assessment: dict[str, Any],
    decision: RequirementComplianceDecision | None,
) -> dict[str, Any]:
    decision_status = decision.decision_status if decision is not None else DECISION_PENDING
    freshness = _decision_freshness(decision, str(assessment["assessment_fingerprint"]))
    relation = _decision_relation(str(assessment["system_status"]), decision_status)

    return {
        "requirement_id": assessment["requirement_id"],
        "requirement": assessment["requirement"],
        "system_assessment": assessment,
        "human_decision": {
            "id": decision.id if decision is not None else None,
            "tender_id": assessment["tender_id"],
            "company_id": assessment["company_id"],
            "requirement_id": assessment["requirement_id"],
            "decision_status": decision_status,
            "decision_note": decision.decision_note if decision is not None else None,
            "reviewed_assessment_fingerprint": decision.reviewed_assessment_fingerprint if decision is not None else None,
            "decided_at": decision.decided_at if decision is not None else None,
            "created_at": decision.created_at if decision is not None else None,
            "updated_at": decision.updated_at if decision is not None else None,
            "freshness": freshness,
        },
        "decision_relation": relation,
    }


def list_tender_company_compliance_review(
    db: Session,
    tender_id: str,
    company_id: str,
    *,
    system_status: str | None = None,
    decision_status: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)

    compliance_payload = list_tender_company_compliance_assessments(
        db,
        tender_id,
        company_id,
        system_status=system_status,
        category=category,
    )
    assessments = compliance_payload["assessments"]
    requirement_ids = [row["requirement_id"] for row in assessments]

    decisions = db.execute(
        select(RequirementComplianceDecision).where(
            RequirementComplianceDecision.tender_id == tender_id,
            RequirementComplianceDecision.company_id == company_id,
            RequirementComplianceDecision.requirement_id.in_(requirement_ids),
        )
    ).scalars().all() if requirement_ids else []
    decision_by_requirement = {row.requirement_id: row for row in decisions}

    normalized_decision_status = _normalize_status(decision_status or "") or None

    rows: list[dict[str, Any]] = []
    for assessment in assessments:
        row = _compose_human_decision_row(assessment, decision_by_requirement.get(assessment["requirement_id"]))
        if normalized_decision_status and row["human_decision"]["decision_status"] != normalized_decision_status:
            continue
        rows.append(row)

    rows.sort(
        key=lambda item: (
            0 if item["decision_relation"] in {RELATION_HUMAN_OVERRIDE, RELATION_SYSTEM_UNDECIDED} else 1,
            str(item["requirement"]["canonical_text"]).lower(),
            item["requirement_id"],
        )
    )

    return {
        "tender_id": tender_id,
        "company_id": company_id,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _build_summary(rows),
        "rows": rows,
    }


def _assessment_or_409(db: Session, tender_id: str, company_id: str, requirement_id: str) -> RequirementComplianceAssessment:
    row = db.execute(
        select(RequirementComplianceAssessment).where(
            RequirementComplianceAssessment.tender_id == tender_id,
            RequirementComplianceAssessment.company_id == company_id,
            RequirementComplianceAssessment.requirement_id == requirement_id,
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Compliance assessment not found for requirement. Run analyze-compliance first.",
        )
    return row


def _requirement_row_or_400(matrix_rows: list[dict[str, Any]], requirement_id: str) -> dict[str, Any]:
    lookup = {str(row["requirement_id"]): row for row in matrix_rows}
    requirement_row = lookup.get(requirement_id)
    if requirement_row is None:
        raise HTTPException(status_code=400, detail="Requirement is not reviewable in the current tender state")
    if not _is_reviewable_requirement(requirement_row):
        raise HTTPException(status_code=400, detail="Human compliance decision is not allowed for superseded or rejected requirements")
    return requirement_row


def upsert_requirement_compliance_decision(
    db: Session,
    tender_id: str,
    company_id: str,
    requirement_id: str,
    *,
    decision_status: str,
    decision_note: str | None,
) -> dict[str, Any]:
    _tender_or_404(db, tender_id)
    _company_or_404(db, company_id)

    normalized_status = _normalize_status(decision_status)
    if normalized_status not in _ALLOWED_DECISION_STATUS:
        raise HTTPException(status_code=400, detail="Unsupported decision_status")

    assessment = _assessment_or_409(db, tender_id, company_id, requirement_id)

    matrix = get_tender_requirement_matrix(db, tender_id)
    requirement_row = _requirement_row_or_400(matrix["requirements"], requirement_id)

    note = _normalize_note(decision_note)
    if _note_is_required(
        decision_status=normalized_status,
        system_status=assessment.system_status,
        requirement_effective_status=str(requirement_row.get("effective_status") or "").upper(),
        applicability_context=assessment.applicability_context,
    ) and not note:
        raise HTTPException(status_code=400, detail="decision_note is required for the selected decision and current system context")

    decision = db.execute(
        select(RequirementComplianceDecision).where(
            RequirementComplianceDecision.tender_id == tender_id,
            RequirementComplianceDecision.company_id == company_id,
            RequirementComplianceDecision.requirement_id == requirement_id,
        )
    ).scalars().first()

    if decision is None:
        decision = RequirementComplianceDecision(
            tender_id=tender_id,
            company_id=company_id,
            requirement_id=requirement_id,
        )
        db.add(decision)

    decision.decision_status = normalized_status
    if normalized_status == DECISION_PENDING:
        decision.decision_note = None
        decision.reviewed_assessment_fingerprint = None
        decision.decided_at = None
    else:
        decision.decision_note = note
        decision.reviewed_assessment_fingerprint = assessment.assessment_fingerprint
        decision.decided_at = datetime.now(timezone.utc)

    db.flush()
    db.expire_all()

    payload = list_tender_company_compliance_review(db, tender_id, company_id)
    for row in payload["rows"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise HTTPException(status_code=404, detail="Compliance review row not found")
