"""Human Alternative-vs-Scope assessments; deterministic audit and applicability."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    AlternativeScopeComplianceEvaluation as Evaluation,
    AlternativeScopeComplianceItem as Item,
    AlternativeScopeComplianceDecision as Decision,
    TechnicalAlternative, TechnicalAlternativeRevision, Tender, TenderScopeDetail,
    TenderDocument, DocumentPage, TenderSourceEffect, TenderScopeReview,
)
from app.scope_review import get_scope_review_item, ScopeReviewSourceBlocked
from app.technical_alternatives import (
    get_technical_alternative, TechnicalAlternativeNotFound,
    TechnicalAlternativeRevisionRead, RevisionNumber, TextContent,
)

ItemStatus = Literal['COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED', 'NOT_EVALUATED']
Applicability = Literal['CURRENT', 'STALE_ALTERNATIVE', 'STALE_SCOPE', 'STALE_BOTH']
Fingerprint = Annotated[str, StringConstraints(strict=True, pattern=r'^[0-9a-f]{64}$')]
STATUSES = ('COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED', 'NOT_EVALUATED')


class AlternativeComplianceNotFound(LookupError):
    pass


class AlternativeComplianceConflict(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class EffectiveScopeItem(Contract):
    scope_detail_id: str
    effective_description: str
    accepted_execution_scope: bool
    unresolved: bool
    effective_status: str
    human_review_status: str
    current_review_revision: int | None
    # Full machine/projection content without incidental timestamps; JSON schema validated.
    machine: dict[str, JsonValue]
    source_projection: dict[str, JsonValue] | None
    applicable_review: dict[str, JsonValue] | None
    projection_fingerprint: Fingerprint


class EffectiveScopeSnapshot(Contract):
    tender_id: str
    items: tuple[EffectiveScopeItem, ...]
    fingerprint: Fingerprint
    unresolved: bool


class EvaluationCreate(Contract):
    expected_alternative_revision: RevisionNumber
    expected_alternative_fingerprint: Fingerprint
    expected_scope_snapshot_fingerprint: Fingerprint


class ItemDecisionWrite(Contract):
    status: ItemStatus
    rationale: TextContent
    evidence_note: Annotated[str, StringConstraints(strict=True, strip_whitespace=True)] | None = None
    expected_current_decision_revision: RevisionNumber | None


class ItemDecisionRead(Contract):
    model_config = ConfigDict(extra='forbid', frozen=True, from_attributes=True)
    id: str
    revision: int
    status: ItemStatus
    rationale: str
    evidence_note: str | None
    created_at: datetime


class ComplianceItemRead(Contract):
    item_key: str
    item_index: int
    snapshot: EffectiveScopeItem
    status: ItemStatus
    latest_decision: ItemDecisionRead | None
    decisions: tuple[ItemDecisionRead, ...]


class EvaluationRead(Contract):
    id: str
    tender_id: str
    alternative_id: str
    alternative_revision: TechnicalAlternativeRevisionRead
    scope_snapshot: EffectiveScopeSnapshot
    created_at: datetime
    applicability: Applicability
    overall_status: Literal['STALE', 'COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED', 'NOT_EVALUATED']
    historical_aggregate: ItemStatus
    counts: dict[ItemStatus, int]
    items: tuple[ComplianceItemRead, ...]


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def _without_times(value):
    if isinstance(value, dict):
        return {key: _without_times(item) for key, item in value.items()
                if key not in {'created_at', 'updated_at', 'reviewed_at'}}
    if isinstance(value, (list, tuple)):
        return [_without_times(item) for item in value]
    return value


def scope_snapshot_fingerprint(tender_id: str, items: tuple[EffectiveScopeItem, ...]) -> str:
    return _hash({'contract': 'alternative-effective-scope-v1', 'tender_id': tender_id,
                  'items': [item.model_dump(mode='json') for item in sorted(items, key=lambda item: item.scope_detail_id)]})


def get_effective_scope_snapshot(db: Session, *, tender_id: str) -> EffectiveScopeSnapshot:
    with db.no_autoflush:
        context_models = (TenderScopeDetail, TenderDocument, TenderSourceEffect, TenderScopeReview, DocumentPage)
        if any(isinstance(row, context_models) for row in db.new | db.dirty | db.deleted):
            raise AlternativeComplianceConflict('SCOPE_CONTEXT_UNFLUSHED')
        if db.get(Tender, tender_id) is None:
            raise AlternativeComplianceNotFound('Tender not found')
        _lock_scope(db)
        # Reload relevant persisted context, avoiding stale identity-map values.
        for model in (TenderScopeDetail, TenderDocument, TenderSourceEffect, TenderScopeReview):
            db.scalars(select(model).where(model.tender_id == tender_id)
                       .execution_options(populate_existing=True)).all()
        db.scalars(select(DocumentPage).join(TenderDocument, DocumentPage.document_id == TenderDocument.id)
                   .where(TenderDocument.tender_id == tender_id)
                   .execution_options(populate_existing=True)).all()
        rows = db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender_id)
                          .order_by(TenderScopeDetail.id)).all()
        items = []
        for row in rows:
            try:
                view = get_scope_review_item(db, tender_id=tender_id, scope_detail_id=row.id)
                current = view.current
                assert current is not None
                machine = _without_times(current.machine.model_dump(mode='json'))
                projection = _without_times(asdict(current.source_projection))
                review = view.latest_applicable_review
                # Notes are audit commentary, not contractual Scope content.
                applicable = _without_times(review.model_dump(mode='json', exclude={'note'})) if review else None
                values = dict(scope_detail_id=row.id, effective_description=current.effective_description,
                    accepted_execution_scope=current.accepted_execution_scope,
                    unresolved=not current.accepted_execution_scope and current.effective_status != 'REJECTED',
                    effective_status=current.effective_status, human_review_status=current.human_review_status,
                    current_review_revision=view.current_review_revision, machine=machine,
                    source_projection=projection, applicable_review=applicable)
            except ScopeReviewSourceBlocked:
                # Missing provenance cannot establish an accepted fact. Preserve actual row only.
                machine = {column.name: getattr(row, column.name) for column in row.__table__.columns
                           if column.name not in {'created_at', 'updated_at'}}
                values = dict(scope_detail_id=row.id, effective_description=row.description,
                    accepted_execution_scope=False, unresolved=True, effective_status='UNRESOLVED_SOURCE',
                    human_review_status='UNKNOWN', current_review_revision=None, machine=machine,
                    source_projection=None, applicable_review=None)
            items.append(EffectiveScopeItem(**values, projection_fingerprint=_hash(values)))
        result = tuple(items)
        return EffectiveScopeSnapshot(tender_id=tender_id, items=result,
            fingerprint=scope_snapshot_fingerprint(tender_id, result), unresolved=any(item.unresolved for item in result))


def _lock_scope(db: Session) -> None:
    # SHARE blocks concurrent INSERT/UPDATE/DELETE, including new Scope identities.
    # Short local transactions; no changes to protected writers/resolvers are needed.
    db.execute(text('LOCK TABLE tender_documents, document_pages, tender_scope_details, '
                    'tender_scope_reviews, tender_source_effects IN SHARE MODE'))


def _lock_context(db: Session, tender_id: str, alternative_id: str, *, write: bool = True) -> None:
    _lock_scope(db)
    row = db.scalar(select(TechnicalAlternative).where(TechnicalAlternative.id == alternative_id,
                    TechnicalAlternative.tender_id == tender_id).with_for_update(read=not write))
    if row is None:
        raise AlternativeComplianceNotFound('Alternative not found in requested tender')


def _alternative(db, tender_id, alternative_id):
    try:
        return get_technical_alternative(db, tender_id=tender_id, alternative_id=alternative_id)
    except TechnicalAlternativeNotFound as exc:
        raise AlternativeComplianceNotFound('Alternative not found in requested tender') from exc


def _evaluation(db, tender_id, alternative_id, evaluation_id):
    _alternative(db, tender_id, alternative_id)
    row = db.scalar(select(Evaluation).where(Evaluation.id == evaluation_id,
        Evaluation.tender_id == tender_id, Evaluation.alternative_id == alternative_id))
    if row is None:
        raise AlternativeComplianceNotFound('Evaluation not found in requested alternative')
    return row


def aggregate_status(statuses: tuple[ItemStatus, ...], *, unresolved: bool) -> ItemStatus:
    if unresolved:
        return 'REVIEW_REQUIRED'
    for state in ('NON_COMPLIANT', 'PARTIAL', 'REVIEW_REQUIRED', 'NOT_EVALUATED'):
        if state in statuses:
            return state
    return 'COMPLIANT' if statuses else 'NOT_EVALUATED'


def get_compliance_evaluation(db: Session, *, tender_id: str, alternative_id: str, evaluation_id: str) -> EvaluationRead:
    with db.no_autoflush:
        _lock_context(db, tender_id, alternative_id, write=False)
        row = _evaluation(db, tender_id, alternative_id, evaluation_id)
        current_alt = _alternative(db, tender_id, alternative_id).current_revision
        current_scope = get_effective_scope_snapshot(db, tender_id=tender_id)
        alt_stale = current_alt.revision != row.alternative_revision or current_alt.fingerprint != row.alternative_fingerprint
        scope_stale = current_scope.fingerprint != row.scope_snapshot_fingerprint
        applicability = ('STALE_BOTH' if alt_stale and scope_stale else 'STALE_ALTERNATIVE' if alt_stale
                         else 'STALE_SCOPE' if scope_stale else 'CURRENT')
        snapshot = EffectiveScopeSnapshot.model_validate(row.scope_snapshot)
        items = []
        for item in db.scalars(select(Item).where(Item.evaluation_id == row.id).order_by(Item.item_index)):
            history = tuple(ItemDecisionRead.model_validate(decision) for decision in db.scalars(
                select(Decision).where(Decision.item_id == item.id).order_by(Decision.revision)))
            latest = history[-1] if history else None
            items.append(ComplianceItemRead(item_key=item.item_key, item_index=item.item_index,
                snapshot=EffectiveScopeItem.model_validate(item.snapshot), status=latest.status if latest else 'NOT_EVALUATED',
                latest_decision=latest, decisions=history))
        states = tuple(item.status for item in items)
        counts = Counter(states)
        historical = aggregate_status(states, unresolved=snapshot.unresolved)
        revision = db.get(TechnicalAlternativeRevision, row.alternative_revision_id)
        return EvaluationRead(id=row.id, tender_id=tender_id, alternative_id=alternative_id,
            alternative_revision=TechnicalAlternativeRevisionRead.model_validate(revision), scope_snapshot=snapshot,
            created_at=row.created_at, applicability=applicability,
            overall_status=historical if applicability == 'CURRENT' else 'STALE', historical_aggregate=historical,
            counts={state: counts[state] for state in STATUSES}, items=tuple(items))


def list_compliance_evaluations(db: Session, *, tender_id: str, alternative_id: str) -> tuple[EvaluationRead, ...]:
    with db.no_autoflush:
        _alternative(db, tender_id, alternative_id)
        ids = db.scalars(select(Evaluation.id).where(Evaluation.tender_id == tender_id,
            Evaluation.alternative_id == alternative_id).order_by(Evaluation.id)).all()
        return tuple(get_compliance_evaluation(db, tender_id=tender_id, alternative_id=alternative_id, evaluation_id=value) for value in ids)


def create_compliance_evaluation(db: Session, *, tender_id: str, alternative_id: str, payload: EvaluationCreate) -> EvaluationRead:
    payload = EvaluationCreate.model_validate(payload.model_dump())
    with db.no_autoflush:
        _lock_context(db, tender_id, alternative_id)
        alternative = _alternative(db, tender_id, alternative_id).current_revision
        scope = get_effective_scope_snapshot(db, tender_id=tender_id)
        for mismatch, code in (
            (alternative.revision != payload.expected_alternative_revision, 'ALTERNATIVE_REVISION_CONFLICT'),
            (alternative.fingerprint != payload.expected_alternative_fingerprint, 'ALTERNATIVE_FINGERPRINT_STALE'),
            (scope.fingerprint != payload.expected_scope_snapshot_fingerprint, 'SCOPE_SNAPSHOT_STALE'),
            (alternative.lifecycle_state == 'ARCHIVED', 'ALTERNATIVE_ARCHIVED'),
        ):
            if mismatch:
                raise AlternativeComplianceConflict(code)
        existing = db.scalar(select(Evaluation).where(Evaluation.alternative_id == alternative_id,
            Evaluation.alternative_revision == alternative.revision, Evaluation.alternative_fingerprint == alternative.fingerprint,
            Evaluation.scope_snapshot_fingerprint == scope.fingerprint))
        if existing is None:
            with db.begin_nested():
                existing = Evaluation(tender_id=tender_id, alternative_id=alternative_id,
                    alternative_revision_id=alternative.id, alternative_revision=alternative.revision,
                    alternative_fingerprint=alternative.fingerprint, scope_snapshot_fingerprint=scope.fingerprint,
                    scope_snapshot=scope.model_dump(mode='json'))
                db.add(existing)
                db.flush()
                # Rejected facts are frozen in context, but are not evaluable obligations.
                for index, item in enumerate(value for value in scope.items if value.accepted_execution_scope or value.unresolved):
                    db.add(Item(evaluation_id=existing.id, tender_id=tender_id, alternative_id=alternative_id,
                        item_key=item.scope_detail_id, scope_detail_id=item.scope_detail_id, item_index=index,
                        snapshot=item.model_dump(mode='json')))
                db.flush()
        return get_compliance_evaluation(db, tender_id=tender_id, alternative_id=alternative_id, evaluation_id=existing.id)


def append_compliance_decision(db: Session, *, tender_id: str, alternative_id: str,
                               evaluation_id: str, item_key: str, payload: ItemDecisionWrite) -> EvaluationRead:
    payload = ItemDecisionWrite.model_validate(payload.model_dump())
    with db.no_autoflush:
        _lock_context(db, tender_id, alternative_id)
        view = get_compliance_evaluation(db, tender_id=tender_id, alternative_id=alternative_id, evaluation_id=evaluation_id)
        item = db.scalar(select(Item).where(Item.evaluation_id == evaluation_id, Item.item_key == item_key,
            Item.tender_id == tender_id, Item.alternative_id == alternative_id).with_for_update())
        if item is None:
            raise AlternativeComplianceNotFound('Frozen Scope item not found')
        if view.applicability != 'CURRENT':
            raise AlternativeComplianceConflict('COMPLIANCE_EVALUATION_STALE')
        revisions = db.scalars(select(Decision.revision).where(Decision.item_id == item.id)).all()
        current = max(revisions) if revisions else None
        if current != payload.expected_current_decision_revision:
            raise AlternativeComplianceConflict('COMPLIANCE_DECISION_REVISION_CONFLICT')
        with db.begin_nested():
            db.add(Decision(item_id=item.id, evaluation_id=evaluation_id, tender_id=tender_id,
                alternative_id=alternative_id, revision=(current or 0) + 1,
                **payload.model_dump(exclude={'expected_current_decision_revision'})))
            db.flush()
        return get_compliance_evaluation(db, tender_id=tender_id, alternative_id=alternative_id, evaluation_id=evaluation_id)
