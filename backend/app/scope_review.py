"""Human ScopeDetail decisions, separate from machine and source-version evidence.

Writes participate in the caller's transaction. Reads never flush or mutate.
HTTP adapters remain separate; attribute/quantity editing is not supported.
"""
from __future__ import annotations

import hashlib
import json
from app.read_batch import memo_read

from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
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


class ScopeReviewConflict(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


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


class ScopeReviewDecisionWrite(ScopeReviewDecisionInput):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    expected_projection_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    expected_current_review_revision: Annotated[int, Field(strict=True, ge=1)] | None


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
    from app.read_batch import current_batch
    batch = current_batch(db)
    if not lock and batch is not None and batch['tender_id']==tender_id:
        detail = batch['scopes'].get(scope_detail_id)
        if detail is None:raise ScopeReviewNotFound('ScopeDetail not found in requested tender')
        return detail
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
    from app.structured_evidence_grounding import is_structured, resolve_payload
    if is_structured(detail.source_locator):
        try:
            resolve_payload(db, detail)
        except ValueError as exc:
            raise ScopeReviewSourceBlocked(str(exc)) from exc
    values = {name: getattr(detail, name) for name in ScopeMachineEvidence.model_fields
              if name not in {"document_revision", "source_page"}}
    # PostgreSQL may return the same instant in the session timezone after reload.
    # Canonical UTC serialization keeps fingerprints stable across sessions.
    for name in ("created_at", "updated_at"):
        values[name] = values[name].astimezone(timezone.utc)
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
    from app.read_batch import current_batch
    batch = current_batch(db)
    if batch is not None and batch['tender_id']==tender_id:
        return list(batch['history'].get(scope_detail_id, []))
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
    expectations: ScopeReviewDecisionWrite | None = None,
) -> ScopeReviewRead:
    # Revalidate even Pydantic model_construct inputs before any persistence.
    validated = ScopeReviewDecisionInput.model_validate(decision.model_dump())
    with db.no_autoflush:
        detail = _detail(db, tender_id, scope_detail_id, lock=True)
        evidence = _evidence(db, detail)
        projection = _projection(db, detail)
        history = _history(db, tender_id, scope_detail_id)
        if expectations is not None:
            if expectations.expected_projection_fingerprint != _target_fingerprint(evidence, projection):
                raise ScopeReviewConflict("SCOPE_REVIEW_TARGET_STALE")
            if expectations.expected_current_review_revision != (history[-1].revision if history else None):
                raise ScopeReviewConflict("SCOPE_REVIEW_REVISION_CONFLICT")
        if _source_blocked(projection):
            raise ScopeReviewSourceBlocked("Resolve source-version review before reviewing ScopeDetail")
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


def _corroborated_review_current(db, review, machine, projection):
    from app.structured_evidence_grounding import corroboration_only
    old = review.machine_snapshot
    if not corroboration_only(db, old.source_locator, machine.source_locator):
        return False
    comparable = machine.model_copy(update={'source_locator':old.source_locator,'updated_at':old.updated_at})
    if comparable != old:
        return False
    # Preserve the exact prior source-effect projection contract. Only the
    # verified proof reference may differ; any effect/status change goes stale.
    comparable_projection = replace(projection,source_locator=old.source_locator,
        diagnostics=tuple(replace(d,source_locator=old.source_locator)
            if d.source_locator == machine.source_locator else d for d in projection.diagnostics))
    return review.reviewed_source_fingerprint == _source_fingerprint(comparable_projection)


@memo_read
def _read_scope_review(
    db: Session, *, tender_id: str, scope_detail_id: str,
) -> tuple[EffectiveScopeReview, tuple[ScopeReviewRead, ...]]:
    with db.no_autoflush:
        detail = _detail(db, tender_id, scope_detail_id)
        machine = _evidence(db, detail)
        projection = _projection(db, detail)
        history = tuple(_review_read(row) for row in _history(db, tender_id, scope_detail_id))
        review = history[-1] if history else None

    blocked = _source_blocked(projection)
    current = bool(review and (
        (review.machine_snapshot == machine and review.reviewed_source_fingerprint == _source_fingerprint(projection))
        or _corroborated_review_current(db, review, machine, projection)))
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

    view = EffectiveScopeReview(
        machine=machine, latest_review=review, human_review_status=human_status,
        effective_status=status, effective_description=effective_description,
        accepted_execution_scope=status in {"NOT_REQUIRED", "CONFIRMED", "CORRECTED"},
        machine_review_required=machine.review_required,
        human_resolved_machine_review=bool(current and not blocked and review
                                          and review.decision in {"CONFIRMED", "CORRECTED"}),
        source_blocked=blocked, source_projection=projection,
    )
    return view, history


def get_effective_scope_review(db: Session, *, tender_id: str, scope_detail_id: str) -> EffectiveScopeReview:
    return _read_scope_review(db, tender_id=tender_id, scope_detail_id=scope_detail_id)[0]


class ScopeReviewHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    review: ScopeReviewRead
    applicable: bool
    reason: Literal["CURRENT", "HISTORICAL_REVISION", "TARGET_CHANGED", "TARGET_REMOVED"]


class ScopeReviewItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope_detail_id: str
    current: EffectiveScopeReview | None
    projection_fingerprint: str | None
    current_review_revision: int | None
    latest_applicable_review: ScopeReviewRead | None
    reviewable: bool
    not_reviewable_reason: str | None
    history: tuple[ScopeReviewHistoryEntry, ...]


def _target_fingerprint(machine: ScopeMachineEvidence, projection: EffectiveEntityProjection) -> str:
    payload = {"machine": machine.model_dump(mode="json"), "projection": asdict(projection)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def get_scope_review_item(db: Session, *, tender_id: str, scope_detail_id: str) -> ScopeReviewItemRead:
    """Read current facts or an archived identity, without carrying decisions forward."""
    with db.no_autoflush:
        try:
            current, history = _read_scope_review(db, tender_id=tender_id, scope_detail_id=scope_detail_id)
        except ScopeReviewNotFound:
            history = list_scope_review_history(db, tender_id=tender_id, scope_detail_id=scope_detail_id)
            if not history:
                raise
            current = None
        applicable = current.latest_review if current and current.human_review_status == "CURRENT" else None
        entries = tuple(ScopeReviewHistoryEntry(
            review=review,
            applicable=bool(applicable and applicable.id == review.id),
            reason=("TARGET_REMOVED" if current is None else
                    "TARGET_CHANGED" if review.machine_snapshot != current.machine or
                    review.reviewed_source_fingerprint != _source_fingerprint(current.source_projection) else
                    "CURRENT" if applicable and applicable.id == review.id else "HISTORICAL_REVISION"),
        ) for review in history)
        blocked = current is None or current.source_blocked
        return ScopeReviewItemRead(
            scope_detail_id=scope_detail_id, current=current,
            projection_fingerprint=(_target_fingerprint(current.machine, current.source_projection) if current else None),
            current_review_revision=history[-1].revision if history else None,
            latest_applicable_review=applicable, reviewable=not blocked,
            not_reviewable_reason=("TARGET_REMOVED" if current is None else
                                   f"SOURCE_{current.source_projection.status}" if blocked else None),
            history=entries,
        )


def list_scope_review_items(db: Session, *, tender_id: str) -> tuple[ScopeReviewItemRead, ...]:
    # Include archived identities so regeneration cannot hide the audit trail.
    with db.no_autoflush:
        current_ids = set(db.scalars(select(TenderScopeDetail.id).where(TenderScopeDetail.tender_id == tender_id)))
        historical_ids = set(db.scalars(select(TenderScopeReview.scope_detail_id).where(TenderScopeReview.tender_id == tender_id)))
        return tuple(get_scope_review_item(db, tender_id=tender_id, scope_detail_id=identity)
                     for identity in sorted(current_ids | historical_ids))


def decide_scope_review(db: Session, *, tender_id: str, scope_detail_id: str,
                        payload: ScopeReviewDecisionWrite) -> ScopeReviewItemRead:
    validated = ScopeReviewDecisionWrite.model_validate(payload.model_dump())
    decision = ScopeReviewDecisionInput.model_validate(validated.model_dump(exclude={
        "expected_projection_fingerprint", "expected_current_review_revision",
    }))
    append_scope_review(db, tender_id=tender_id, scope_detail_id=scope_detail_id,
                        decision=decision, expectations=validated)
    return get_scope_review_item(db, tender_id=tender_id, scope_detail_id=scope_detail_id)
