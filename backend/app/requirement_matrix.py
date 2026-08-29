from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementReview,
    RequirementSemantics,
    Tender,
)
from app.requirement_versioning import get_tender_requirement_effective_state

REQUIREMENT_MATRIX_VERSION = "mvp-04.6"

REVIEW_PENDING = "PENDING"
REVIEW_APPROVED = "APPROVED"
REVIEW_NEEDS_REVIEW = "NEEDS_REVIEW"
REVIEW_REJECTED = "REJECTED"

ACTION_APPROVE = "APPROVE"
ACTION_MARK_NEEDS_REVIEW = "MARK_NEEDS_REVIEW"
ACTION_REJECT = "REJECT"
ACTION_RESET = "RESET"

FRESHNESS_CURRENT = "CURRENT"
FRESHNESS_STALE = "STALE"
FRESHNESS_NOT_REVIEWED = "NOT_REVIEWED"

SCOPE_NOTE = (
    "La revisión humana valida la representación del requisito y su evidencia fuente; "
    "no evalúa cumplimiento de una empresa ni decide estrategia comercial."
)


def _normalize_space(value: str | None) -> str:
    return " ".join((value or "").split())


def _primary_source(requirement: Requirement) -> dict[str, Any] | None:
    ordered_links = sorted(requirement.candidate_links, key=lambda row: (0 if row.is_primary_source else 1, row.id))
    for link in ordered_links:
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


def _expected_evidence_payload(semantics: RequirementSemantics | None) -> list[dict[str, Any]]:
    if semantics is None:
        return []

    rows = sorted(
        semantics.expected_evidence,
        key=lambda item: (
            item.evidence_type,
            item.evidence_description,
            item.source_document_id or "",
            item.source_page or 0,
            item.id,
        ),
    )

    out: list[dict[str, Any]] = []
    for row in rows:
        source_document = row.source_document
        out.append(
            {
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
        )
    return out


def _build_representation_fingerprint(
    requirement: Requirement,
    *,
    effective_status: str,
    effective_source_document_id: str | None,
    evidence_reasons: list[str],
) -> str:
    semantics = requirement.semantics
    primary_source = _primary_source(requirement)
    expected_evidence = _expected_evidence_payload(semantics)

    payload = {
        "canonical_text": _normalize_space(requirement.canonical_text),
        "category": requirement.category,
        "normalization_status": requirement.normalization_status,
        "normalization_reason": _normalize_space(requirement.normalization_reason),
        "source_occurrence_count": len(requirement.candidate_links),
        "primary_source": {
            "source_document_id": primary_source["source_document_id"] if primary_source else None,
            "source_page": primary_source["source_page"] if primary_source else None,
            "requirement_text": _normalize_space(primary_source["requirement_text"]) if primary_source else None,
            "source_excerpt": _normalize_space(primary_source["source_excerpt"]) if primary_source else None,
            "actor_text": _normalize_space(primary_source["actor_text"]) if primary_source else None,
            "modality_text": _normalize_space(primary_source["modality_text"]) if primary_source else None,
        },
        "semantics": {
            "applicability": semantics.applicability if semantics else "UNKNOWN",
            "condition_text": _normalize_space(semantics.condition_text) if semantics else None,
            "interpretation_status": semantics.interpretation_status if semantics else "REVIEW_REQUIRED",
            "interpretation_reason": _normalize_space(semantics.interpretation_reason) if semantics else "not_analyzed",
            "evidence_mode": semantics.evidence_mode if semantics else "REVIEW_REQUIRED",
            "expected_evidence": [
                {
                    "evidence_type": item["evidence_type"],
                    "evidence_description": _normalize_space(item["evidence_description"]),
                    "source_document_id": item["source_document_id"],
                    "source_page": item["source_page"],
                    "source_excerpt": _normalize_space(item["source_excerpt"]),
                }
                for item in expected_evidence
            ],
        },
        "effective": {
            "effective_status": effective_status,
            "effective_source_document_id": effective_source_document_id,
            "evidence_reasons": sorted(evidence_reasons),
        },
    }

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _review_freshness(review: RequirementReview | None, current_fingerprint: str) -> str:
    if review is None:
        return FRESHNESS_NOT_REVIEWED
    if review.review_status == REVIEW_PENDING:
        return FRESHNESS_NOT_REVIEWED
    if not review.reviewed_fingerprint:
        return FRESHNESS_STALE
    if review.reviewed_fingerprint != current_fingerprint:
        return FRESHNESS_STALE
    return FRESHNESS_CURRENT


def _system_warnings(
    requirement: Requirement,
    *,
    effective_status: str,
) -> list[str]:
    warnings: list[str] = []
    semantics = requirement.semantics

    if requirement.normalization_status == "REVIEW_REQUIRED":
        warnings.append("NORMALIZATION_REVIEW_REQUIRED")

    if semantics is None:
        warnings.append("SEMANTICS_NOT_ANALYZED")
    else:
        if semantics.interpretation_status == "REVIEW_REQUIRED":
            warnings.append("INTERPRETATION_REVIEW_REQUIRED")
        if semantics.evidence_mode == "REVIEW_REQUIRED":
            warnings.append("EVIDENCE_DEFINITION_REVIEW_REQUIRED")

    if effective_status == "AMBIGUOUS":
        warnings.append("EFFECTIVE_STATUS_AMBIGUOUS")
    if effective_status == "UNRESOLVED":
        warnings.append("EFFECTIVE_STATUS_UNRESOLVED")

    return warnings


def _serialize_matrix_row(
    requirement: Requirement,
    *,
    effective_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    effective_row = effective_lookup.get(requirement.id, {})
    effective_status = str(effective_row.get("effective_status") or "UNRESOLVED")
    effective_source_document_id = effective_row.get("effective_source_document_id")
    effective_source_filename = effective_row.get("effective_source_filename")
    evidence_reasons = [str(item) for item in (effective_row.get("evidence_reasons") or [])]

    semantics = requirement.semantics
    primary_source = _primary_source(requirement)
    expected_evidence = _expected_evidence_payload(semantics)

    fingerprint = _build_representation_fingerprint(
        requirement,
        effective_status=effective_status,
        effective_source_document_id=effective_source_document_id,
        evidence_reasons=evidence_reasons,
    )

    review = requirement.review
    freshness = _review_freshness(review, fingerprint)

    review_status = REVIEW_PENDING
    review_note = None
    reviewed_fingerprint = None
    reviewed_at = None
    created_at = None
    updated_at = None

    if review is not None:
        review_status = review.review_status
        review_note = review.review_note
        reviewed_fingerprint = review.reviewed_fingerprint
        reviewed_at = review.reviewed_at
        created_at = review.created_at
        updated_at = review.updated_at

    return {
        "requirement_id": requirement.id,
        "canonical_text": requirement.canonical_text,
        "category": requirement.category,
        "normalization_status": requirement.normalization_status,
        "source_occurrence_count": len(requirement.candidate_links),
        "primary_source": primary_source,
        "applicability": semantics.applicability if semantics is not None else "UNKNOWN",
        "condition_text": semantics.condition_text if semantics is not None else None,
        "interpretation_status": semantics.interpretation_status if semantics is not None else "REVIEW_REQUIRED",
        "interpretation_reason": semantics.interpretation_reason if semantics is not None else "not_analyzed",
        "evidence_mode": semantics.evidence_mode if semantics is not None else "REVIEW_REQUIRED",
        "expected_evidence": expected_evidence,
        "effective_status": effective_status,
        "effective_source_document_id": effective_source_document_id,
        "effective_source_filename": effective_source_filename,
        "effective_reasons": evidence_reasons,
        "system_warnings": _system_warnings(requirement, effective_status=effective_status),
        "representation_fingerprint": fingerprint,
        "review_status": review_status,
        "review_note": review_note,
        "reviewed_fingerprint": reviewed_fingerprint,
        "review_freshness": freshness,
        "reviewed_at": reviewed_at,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_requirements": len(rows),
        "effective_requirements": sum(1 for row in rows if row["effective_status"] == "EFFECTIVE"),
        "pending_review_count": sum(1 for row in rows if row["review_status"] == REVIEW_PENDING),
        "approved_count": sum(1 for row in rows if row["review_status"] == REVIEW_APPROVED),
        "needs_review_count": sum(1 for row in rows if row["review_status"] == REVIEW_NEEDS_REVIEW),
        "rejected_count": sum(1 for row in rows if row["review_status"] == REVIEW_REJECTED),
        "current_review_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_CURRENT),
        "stale_review_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_STALE),
        "not_reviewed_count": sum(1 for row in rows if row["review_freshness"] == FRESHNESS_NOT_REVIEWED),
    }


def get_tender_requirement_matrix(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    effective_state = get_tender_requirement_effective_state(db, tender_id)
    effective_lookup = {item["requirement_id"]: item for item in effective_state["requirements"]}

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics)
            .selectinload(RequirementSemantics.expected_evidence)
            .selectinload(RequirementEvidenceExpectation.source_document),
            selectinload(Requirement.review),
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    rows = [_serialize_matrix_row(item, effective_lookup=effective_lookup) for item in requirements]
    rows = sorted(rows, key=lambda row: (0 if row["effective_status"] == "EFFECTIVE" else 1, row["canonical_text"].lower(), row["requirement_id"]))

    return {
        "tender_id": tender_id,
        "matrix_version": REQUIREMENT_MATRIX_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": SCOPE_NOTE,
        "summary": _build_summary(rows),
        "requirements": rows,
    }


def update_requirement_review(
    db: Session,
    *,
    tender_id: str,
    requirement_id: str,
    action: str,
    review_note: str | None,
) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirement = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics)
            .selectinload(RequirementSemantics.expected_evidence)
            .selectinload(RequirementEvidenceExpectation.source_document),
            selectinload(Requirement.review),
        )
        .where(Requirement.id == requirement_id)
    ).scalars().first()

    if requirement is None or requirement.tender_id != tender_id:
        raise LookupError("Requirement not found for the selected Tender")

    normalized_action = (action or "").strip().upper()
    note = (review_note or "").strip() or None

    effective_state = get_tender_requirement_effective_state(db, tender_id)
    effective_lookup = {item["requirement_id"]: item for item in effective_state["requirements"]}
    effective_row = effective_lookup.get(requirement.id, {})
    fingerprint = _build_representation_fingerprint(
        requirement,
        effective_status=str(effective_row.get("effective_status") or "UNRESOLVED"),
        effective_source_document_id=effective_row.get("effective_source_document_id"),
        evidence_reasons=[str(item) for item in (effective_row.get("evidence_reasons") or [])],
    )

    review = requirement.review
    if review is None:
        review = RequirementReview(
            tender_id=tender_id,
            requirement_id=requirement.id,
            review_status=REVIEW_PENDING,
        )
        db.add(review)
        db.flush()

    if normalized_action == ACTION_APPROVE:
        review.review_status = REVIEW_APPROVED
        review.review_note = note
        review.reviewed_fingerprint = fingerprint
        review.reviewed_at = datetime.now(timezone.utc)
    elif normalized_action == ACTION_MARK_NEEDS_REVIEW:
        review.review_status = REVIEW_NEEDS_REVIEW
        review.review_note = note
        review.reviewed_fingerprint = fingerprint
        review.reviewed_at = datetime.now(timezone.utc)
    elif normalized_action == ACTION_REJECT:
        if not note:
            raise ValueError("review_note is required when action is REJECT")
        review.review_status = REVIEW_REJECTED
        review.review_note = note
        review.reviewed_fingerprint = fingerprint
        review.reviewed_at = datetime.now(timezone.utc)
    elif normalized_action == ACTION_RESET:
        review.review_status = REVIEW_PENDING
        review.review_note = None
        review.reviewed_fingerprint = None
        review.reviewed_at = None
    else:
        raise ValueError("Unsupported review action")

    db.flush()
    db.expire_all()
    return get_tender_requirement_matrix(db, tender_id)
