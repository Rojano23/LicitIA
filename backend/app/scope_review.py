"""Human ScopeDetail decisions, separate from machine and source-version evidence.

Writes participate in the caller's transaction. Reads never flush or mutate.
No API adapter or attribute/quantity editing is introduced here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from app.effective_source_projection import (
    DIAGNOSTIC_FACT_REVIEW_REQUIRED,
    EffectiveEntityProjection,
    project_effective_sources_for_tender,
)
from app.models import DocumentPage, TenderDocument, TenderScopeDetail, TenderScopeReview

ReviewDecision = Literal["CONFIRMED", "CORRECTED", "REJECTED"]
Description = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


class ScopeReviewNotFound(LookupError):
    """No scope detail belongs to the requested tender."""


class ScopeReviewSourceBlocked(ValueError):
    """Human scope review cannot resolve source-version uncertainty."""


class ScopeDescriptionCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    description: Description


class ScopeReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision: ReviewDecision
    correction: ScopeDescriptionCorrection | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_correction(self) -> ScopeReviewDecisionInput:
        if (self.decision == "CORRECTED") != (self.correction is not None):
            raise ValueError("Only CORRECTED requires a description correction")
        return self


class ScopeMachineEvidence(BaseModel):
    """Typed snapshot of all ScopeDetail fields, plus document revision/page.

    The snapshot is needed because machine rows are derived, regenerable data.
    It is audit evidence, never a replacement canonical machine record.
    """
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)
    id: str
    tender_id: str
    tender_item_id: str | None
    scope_segment_id: str | None
    candidate_item_key: str | None
    source_document_id: str
    document_page_id: str
    source_analysis_id: str | None
    source_page_result_id: str | None
    domain: str
    detail_type: str | None
    description: str
    normalized_label: str | None
    applicability: str
    source_method: str
    source_artifact_key: str
    source_contract_version: str | None
    source_locator: str
    source_excerpt: str
    confidence: float | None
    review_required: bool
    quantity_raw: str | None
    unit_raw: str | None
    semantic_fingerprint: str
    created_at: datetime
    updated_at: datetime
    document_revision: int
    source_page: int


class ScopeReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    tender_id: str
    scope_detail_id: str
    revision: int
    decision: ReviewDecision
    correction: ScopeDescriptionCorrection | None
    note: str | None
    machine_snapshot: ScopeMachineEvidence
    reviewed_source_fingerprint: str
    reviewed_at: datetime

    @model_validator(mode="after")
    def validate_identity_and_correction(self) -> ScopeReviewRead:
        if self.machine_snapshot.id != self.scope_detail_id or self.machine_snapshot.tender_id != self.tender_id:
            raise ValueError("Review snapshot identity mismatch")
        if (self.decision == "CORRECTED") != (self.correction is not None):
            raise ValueError("Invalid persisted correction")
        return self


class EffectiveScopeReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    machine: ScopeMachineEvidence
    latest_review: ScopeReviewRead | None
    human_review_status: Literal["NO_REVIEW", "CURRENT", "STALE"]
    effective_status: Literal[
        "NOT_REQUIRED", "PENDING", "CONFIRMED", "CORRECTED", "REJECTED",
        "STALE_REVIEW", "SOURCE_BLOCKED",
    ]
    effective_description: str
    accepted_execution_scope: bool
    machine_review_required: bool
    human_resolved_machine_review: bool
    source_blocked: bool
    source_projection: EffectiveEntityProjection


def _detail(db: Session, tender_id: str, scope_detail_id: str, *, lock: bool = False) -> TenderScopeDetail:
    query = select(TenderScopeDetail).where(
        TenderScopeDetail.id == scope_detail_id, TenderScopeDetail.tender_id == tender_id,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise ScopeReviewNotFound("ScopeDetail not found in requested tender")
    return row


def _evidence(db: Session, detail: TenderScopeDetail) -> ScopeMachineEvidence:
    document = db.get(TenderDocument, detail.source_document_id)
    page = db.get(DocumentPage, detail.document_page_id)
    if document is None or page is None or document.tender_id != detail.tender_id or page.document_id != document.id:
        raise ScopeReviewSourceBlocked("Missing or inconsistent source provenance")
    values = {name: getattr(detail, name) for name in ScopeMachineEvidence.model_fields
              if name not in {"document_revision", "source_page"}}
    return ScopeMachineEvidence(**values, document_revision=document.revision_number, source_page=page.page_number)


def _projection(db: Session, detail: TenderScopeDetail) -> EffectiveEntityProjection:
    projection = project_effective_sources_for_tender(db, tender_id=detail.tender_id)
    for item in projection.scope_details:
        if item.entity_id == detail.id:
            return item
    raise ScopeReviewSourceBlocked("ScopeDetail has no effective-source projection")


def _source_blocked(projection: EffectiveEntityProjection) -> bool:
    # FACT_REVIEW_REQUIRED concerns this fact, not contractual source precedence.
    # The production projection retains its original status and diagnostics.
    if projection.document_effective_status not in {"ACTIVE", "ACTIVE_WITH_EFFECTS"}:
        return True
    if projection.partial_locator_status not in {
        None, "UNCHANGED", "MODIFIED", "CORRECTED", "CLARIFIED", "SUPPLEMENTED",
    }:
        return True
    if projection.blocking_effect_ids:
        return True
    if any(item.code != DIAGNOSTIC_FACT_REVIEW_REQUIRED for item in projection.diagnostics):
        return True
    return projection.status not in {"EFFECTIVE", "EFFECTIVE_WITH_OVERLAY", "REVIEW_REQUIRED"}


def _source_fingerprint(projection: EffectiveEntityProjection) -> str:
    payload = asdict(projection)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _review_read(row: TenderScopeReview) -> ScopeReviewRead:
    return ScopeReviewRead.model_validate({name: getattr(row, name) for name in ScopeReviewRead.model_fields})


def _history(db: Session, tender_id: str, scope_detail_id: str) -> list[TenderScopeReview]:
    return list(db.scalars(select(TenderScopeReview).where(
        TenderScopeReview.tender_id == tender_id,
        TenderScopeReview.scope_detail_id == scope_detail_id,
    ).order_by(TenderScopeReview.revision.asc())))


def list_scope_review_history(db: Session, *, tender_id: str, scope_detail_id: str) -> tuple[ScopeReviewRead, ...]:
    with db.no_autoflush:
        history = _history(db, tender_id, scope_detail_id)
        if not history:
            _detail(db, tender_id, scope_detail_id)
        return tuple(_review_read(row) for row in history)


def append_scope_review(
    db: Session, *, tender_id: str, scope_detail_id: str, decision: ScopeReviewDecisionInput,
) -> ScopeReviewRead:
    # Revalidate even Pydantic model_construct inputs before any persistence.
    validated = ScopeReviewDecisionInput.model_validate(decision.model_dump())
    with db.no_autoflush:
        detail = _detail(db, tender_id, scope_detail_id, lock=True)
        evidence = _evidence(db, detail)
        projection = _projection(db, detail)
        if _source_blocked(projection):
            raise ScopeReviewSourceBlocked("Resolve source-version review before reviewing ScopeDetail")
        history = _history(db, tender_id, scope_detail_id)
        row = TenderScopeReview(
            tender_id=tender_id, scope_detail_id=scope_detail_id,
            revision=(history[-1].revision + 1 if history else 1),
            decision=validated.decision, note=validated.note,
            correction=(validated.correction.model_dump() if validated.correction else None),
            machine_snapshot=evidence.model_dump(mode="json"),
            reviewed_source_fingerprint=_source_fingerprint(projection),
        )
        db.add(row)
    db.flush([row])
    return _review_read(row)


def get_effective_scope_review(db: Session, *, tender_id: str, scope_detail_id: str) -> EffectiveScopeReview:
    with db.no_autoflush:
        detail = _detail(db, tender_id, scope_detail_id)
        machine = _evidence(db, detail)
        projection = _projection(db, detail)
        history = _history(db, tender_id, scope_detail_id)
        review = _review_read(history[-1]) if history else None

    blocked = _source_blocked(projection)
    current = bool(review and review.machine_snapshot == machine
                   and review.reviewed_source_fingerprint == _source_fingerprint(projection))
    human_status = "NO_REVIEW" if review is None else ("CURRENT" if current else "STALE")
    effective_description = machine.description
    if blocked:
        status = "SOURCE_BLOCKED"
    elif review and not current:
        status = "STALE_REVIEW"
    elif review:
        status = review.decision
        if review.correction:
            effective_description = review.correction.description
    else:
        status = "PENDING" if machine.review_required else "NOT_REQUIRED"

    return EffectiveScopeReview(
        machine=machine, latest_review=review, human_review_status=human_status,
        effective_status=status, effective_description=effective_description,
        accepted_execution_scope=status in {"NOT_REQUIRED", "CONFIRMED", "CORRECTED"},
        machine_review_required=machine.review_required,
        human_resolved_machine_review=bool(current and not blocked and review
                                          and review.decision in {"CONFIRMED", "CORRECTED"}),
        source_blocked=blocked, source_projection=projection,
    )
