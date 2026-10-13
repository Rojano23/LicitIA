"""Synthetic contracts with production Scope Review/projection and PostgreSQL."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update, delete, event
from sqlalchemy.exc import IntegrityError

from tests.test_scope_review import db, _scope, _review, _effect, _regenerate
from tests.test_technical_alternatives import content, revised
from app.technical_alternatives import create_technical_alternative, archive_technical_alternative
from app.alternative_compliance import (
    get_effective_scope_snapshot as snapshot, scope_snapshot_fingerprint,
    EvaluationCreate, ItemDecisionWrite, create_compliance_evaluation as create,
    get_compliance_evaluation as read, list_compliance_evaluations as listing,
    append_compliance_decision as decide, aggregate_status,
    AlternativeComplianceConflict, AlternativeComplianceNotFound,
)
from app.models import (
    AlternativeScopeComplianceEvaluation as Evaluation, AlternativeScopeComplianceItem as Item,
    AlternativeScopeComplianceDecision as Decision, TenderScopeDetail, TenderScopeReview,
    TenderSourceEffect, TechnicalAlternative, TechnicalAlternativeRevision, RequirementComplianceAssessment,
)


@pytest.fixture
def context(db):
    scope = _scope(db, review_required=False)
    alt = create_technical_alternative(db, tender_id=scope.tender_id, content=content())
    return scope, alt


def expected(db, scope, alt):
    return EvaluationCreate(expected_alternative_revision=alt.current_revision.revision,
        expected_alternative_fingerprint=alt.current_revision.fingerprint,
        expected_scope_snapshot_fingerprint=snapshot(db, tender_id=scope.tender_id).fingerprint)


def evaluation(db, context):
    scope, alt = context
    return create(db, tender_id=scope.tender_id, alternative_id=alt.id, payload=expected(db, scope, alt))


def reread(db, row):
    return read(db, tender_id=row.tender_id, alternative_id=row.alternative_id, evaluation_id=row.id)


def decision(db, row, status='COMPLIANT', revision=None):
    return decide(db, tender_id=row.tender_id, alternative_id=row.alternative_id, evaluation_id=row.id,
        item_key=row.items[0].item_key,
        payload=ItemDecisionWrite(status=status, rationale='Juicio humano documentado', evidence_note='Referencia humana',
                                 expected_current_decision_revision=revision))


def test_ac01_snapshot_deterministic(db, context):
    scope, _ = context
    assert snapshot(db, tender_id=scope.tender_id) == snapshot(db, tender_id=scope.tender_id)


def test_ac02_rejected_excluded(db, context):
    scope, _ = context
    _review(db, scope, 'REJECTED')
    row = evaluation(db, context)
    assert row.items == () and not row.scope_snapshot.items[0].accepted_execution_scope
    assert row.overall_status == 'NOT_EVALUATED'


def test_ac03_corrected_effective_description(db, context):
    scope, _ = context
    _review(db, scope, 'CORRECTED')
    row = evaluation(db, context)
    assert row.items[0].snapshot.effective_description == 'Inspeccionar y documentar el equipo'
    assert row.items[0].snapshot.machine['description'] == scope.description
    assert row.items[0].snapshot.machine['document_revision'] == 3


def test_ac04_source_blocked(db, context):
    scope, _ = context
    _effect(db, scope, 'SUPERSEDES', 'PARTIAL')
    _effect(db, scope, 'SUPERSEDES', 'PARTIAL')
    row = evaluation(db, context)
    assert row.scope_snapshot.unresolved and row.overall_status == 'REVIEW_REQUIRED'


def test_ac05_fingerprint_order_independent(db, context):
    scope, _ = context
    original = db.get(TenderScopeDetail, scope.id)
    values = {column.name: getattr(original, column.name) for column in original.__table__.columns}
    values.update(id=str(uuid4()), semantic_fingerprint=uuid4().hex * 2)
    db.add(TenderScopeDetail(**values))
    db.flush()
    result = snapshot(db, tender_id=scope.tender_id)
    assert result.fingerprint == scope_snapshot_fingerprint(scope.tender_id, tuple(reversed(result.items)))


def test_ac06_scope_change_fingerprint(db, context):
    scope, _ = context
    old = snapshot(db, tender_id=scope.tender_id).fingerprint
    scope.description = 'Otra obligación explícita'
    db.flush()
    assert snapshot(db, tender_id=scope.tender_id).fingerprint != old


def test_ac07_regeneration_stale_identical(db, context):
    row = evaluation(db, context)
    new = _regenerate(db, context[0])
    assert new.id != context[0].id
    assert reread(db, row).applicability == 'STALE_SCOPE'


def test_ac08_exact_binding(db, context):
    row = evaluation(db, context)
    assert row.alternative_revision == context[1].current_revision


def test_ac09_frozen_snapshot(db, context):
    row = evaluation(db, context)
    context[0].description = 'Cambió la fuente'
    db.flush()
    assert reread(db, row).scope_snapshot == row.scope_snapshot


def test_ac10_idempotent_create(db, context):
    assert evaluation(db, context) == evaluation(db, context)
    assert len(listing(db, tender_id=context[0].tender_id, alternative_id=context[1].id)) == 1


def test_ac11_stale_alternative(db, context):
    row = evaluation(db, context)
    revised(db, context[1], notes='Nota administrativa')
    result = reread(db, row)
    assert result.applicability == 'STALE_ALTERNATIVE' and result.overall_status == 'STALE'


def test_ac12_stale_scope(db, context):
    row = evaluation(db, context)
    _review(db, context[0], 'CORRECTED')
    assert reread(db, row).applicability == 'STALE_SCOPE'


def test_ac13_stale_both(db, context):
    row = evaluation(db, context)
    revised(db, context[1])
    _review(db, context[0], 'REJECTED')
    assert reread(db, row).applicability == 'STALE_BOTH'


def test_ac14_historical_aggregate(db, context):
    row = decision(db, evaluation(db, context))
    revised(db, context[1])
    result = reread(db, row)
    assert result.overall_status == 'STALE' and result.historical_aggregate == 'COMPLIANT'
    assert result.items == row.items


def test_ac15_defaults(db, context):
    row = evaluation(db, context)
    assert row.overall_status == 'NOT_EVALUATED' and row.items[0].decisions == ()
    assert row.counts['NOT_EVALUATED'] == 1


@pytest.mark.parametrize('status', ['COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED'])
def test_ac16_ac19_human_statuses(db, context, status):
    row = decision(db, evaluation(db, context), status)
    assert row.overall_status == status and row.items[0].latest_decision.status == status
    assert row.items[0].latest_decision.evidence_note == 'Referencia humana'


def test_ac20_history(db, context):
    row = decision(db, evaluation(db, context), 'PARTIAL')
    row = decision(db, row, 'COMPLIANT', 1)
    assert [item.status for item in row.items[0].decisions] == ['PARTIAL', 'COMPLIANT']


def test_ac21_latest_revision_not_time(db, context):
    row = decision(db, evaluation(db, context), 'PARTIAL')
    item = db.scalar(select(Item).where(Item.evaluation_id == row.id))
    db.add(Decision(item_id=item.id, evaluation_id=row.id, tender_id=row.tender_id, alternative_id=row.alternative_id,
        revision=2, status='NON_COMPLIANT', rationale='Juicio histórico', created_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
    db.flush()
    assert reread(db, row).items[0].latest_decision.revision == 2


def test_ac22_stale_revision_no_append(db, context):
    row = decision(db, evaluation(db, context))
    with pytest.raises(AlternativeComplianceConflict, match='COMPLIANCE_DECISION_REVISION_CONFLICT'):
        decision(db, row)
    assert len(reread(db, row).items[0].decisions) == 1


def test_ac23_stale_evaluation_no_append(db, context):
    row = evaluation(db, context)
    revised(db, context[1])
    with pytest.raises(AlternativeComplianceConflict, match='COMPLIANCE_EVALUATION_STALE'):
        decision(db, row)
    assert reread(db, row).items[0].decisions == ()


def test_ac24_archived_reject_create(db, context):
    scope, alt = context
    alt = archive_technical_alternative(db, tender_id=scope.tender_id, alternative_id=alt.id, expected_current_revision=1)
    with pytest.raises(AlternativeComplianceConflict, match='ALTERNATIVE_ARCHIVED'):
        create(db, tender_id=scope.tender_id, alternative_id=alt.id, payload=expected(db, scope, alt))
    assert listing(db, tender_id=scope.tender_id, alternative_id=alt.id) == ()


def test_ac25_archived_history(db, context):
    row = evaluation(db, context)
    archive_technical_alternative(db, tender_id=row.tender_id, alternative_id=row.alternative_id, expected_current_revision=1)
    assert reread(db, row).applicability == 'STALE_ALTERNATIVE'


def test_ac26_cross_tender(db, context):
    row = evaluation(db, context)
    other = _scope(db)
    with pytest.raises(AlternativeComplianceNotFound):
        read(db, tender_id=other.tender_id, alternative_id=row.alternative_id, evaluation_id=row.id)
    alt = create_technical_alternative(db, tender_id=other.tender_id, content=content())
    with pytest.raises(AlternativeComplianceNotFound):
        read(db, tender_id=other.tender_id, alternative_id=alt.id, evaluation_id=row.id)
    item = db.scalar(select(Item).where(Item.evaluation_id == row.id))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Decision(item_id=item.id, evaluation_id=row.id, tender_id=other.tender_id,
            alternative_id=alt.id, revision=1, status='COMPLIANT', rationale='Wrong tender'))
        db.flush()


def test_ac27_snapshot_survives_removal(db, context):
    row = evaluation(db, context)
    historical_id = context[0].id
    _regenerate(db, context[0], description='Nueva versión')
    assert db.get(TenderScopeDetail, historical_id) is None
    result = reread(db, row)
    assert result.items[0].snapshot.scope_detail_id == historical_id
    assert result.items[0].snapshot.machine['source_excerpt'] == row.items[0].snapshot.machine['source_excerpt']


@pytest.mark.parametrize(('states', 'expected_status'), [
    (('COMPLIANT', 'COMPLIANT'), 'COMPLIANT'),
    (('PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED'), 'NON_COMPLIANT'),
    (('PARTIAL', 'REVIEW_REQUIRED', 'NOT_EVALUATED'), 'PARTIAL'),
    (('COMPLIANT', 'REVIEW_REQUIRED', 'NOT_EVALUATED'), 'REVIEW_REQUIRED'),
    (('COMPLIANT', 'NOT_EVALUATED'), 'NOT_EVALUATED'),
])
def test_ac28_ac32_aggregate_precedence(states, expected_status):
    assert aggregate_status(states, unresolved=False) == expected_status


def test_ac33_unresolved_dominates_compliant(db):
    scope = _scope(db, review_required=True)
    alt = create_technical_alternative(db, tender_id=scope.tender_id, content=content())
    row = decision(db, evaluation(db, (scope, alt)))
    assert row.items[0].status == 'COMPLIANT' and row.overall_status == 'REVIEW_REQUIRED'


def record_snapshot(db, models):
    return {model.__tablename__: db.execute(select(model.__table__)).all() for model in models}


def test_ac34_reads_idempotent_no_writes(db, context):
    row = evaluation(db, context)
    statements = []
    def capture(conn, cursor, statement, parameters, ctx, many):
        statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', capture)
    try:
        assert reread(db, row) == reread(db, row)
        assert listing(db, tender_id=row.tender_id, alternative_id=row.alternative_id)[0] == row
    finally:
        event.remove(db.bind, 'before_cursor_execute', capture)
    assert not any(sql.lstrip().split()[0] in {'INSERT', 'UPDATE', 'DELETE'} for sql in statements)


def test_ac35_scope_not_mutated(db, context):
    models = (TenderScopeDetail, TenderScopeReview, TenderSourceEffect)
    before = record_snapshot(db, models)
    decision(db, evaluation(db, context))
    assert record_snapshot(db, models) == before


def test_ac36_alternative_not_mutated(db, context):
    models = (TechnicalAlternative, TechnicalAlternativeRevision)
    before = record_snapshot(db, models)
    row = evaluation(db, context)
    reread(db, row)
    decision(db, row)
    assert record_snapshot(db, models) == before


def test_ac37_existing_compliance_unchanged(db, context):
    from tests.test_compliance_evaluation import (
        _create_tender, _create_company, _seed_requirement, _analyze_compliance,
    )
    from app.database import SessionLocal
    # Seed real existing Requirement/Evidence service records, independent of this transaction.
    tender_id = _create_tender('Synthetic existing compliance isolation')
    company_id = _create_company('Synthetic existing compliance isolation')
    _seed_requirement(tender_id, 'synthetic.pdf', 'La propuesta deberá presentarse en idioma español.')
    _analyze_compliance(tender_id, company_id)
    with SessionLocal() as session:
        before = record_snapshot(session, (RequirementComplianceAssessment,))
    decision(db, evaluation(db, context))
    with SessionLocal() as session:
        assert record_snapshot(session, (RequirementComplianceAssessment,)) == before


def test_append_only_all_audit_tables(db, context):
    row = decision(db, evaluation(db, context))
    for model in (Evaluation, Item, Decision):
        for mutation in (update(model).values(id=str(uuid4())), delete(model)):
            with pytest.raises(IntegrityError), db.begin_nested():
                db.execute(mutation)
    assert reread(db, row) == row


@pytest.mark.parametrize(('field', 'value', 'code'), [
    ('expected_alternative_revision', 2, 'ALTERNATIVE_REVISION_CONFLICT'),
    ('expected_alternative_fingerprint', '0' * 64, 'ALTERNATIVE_FINGERPRINT_STALE'),
    ('expected_scope_snapshot_fingerprint', '0' * 64, 'SCOPE_SNAPSHOT_STALE'),
])
def test_creation_conflicts_atomic(db, context, field, value, code):
    scope, alt = context
    payload = expected(db, scope, alt).model_copy(update={field: value})
    with pytest.raises(AlternativeComplianceConflict, match=code):
        create(db, tender_id=scope.tender_id, alternative_id=alt.id, payload=payload)
    assert listing(db, tender_id=scope.tender_id, alternative_id=alt.id) == ()


def test_empty_scope_not_certified(db):
    from app.models import Tender
    tender = Tender(title='Synthetic empty scope')
    db.add(tender)
    db.flush()
    alt = create_technical_alternative(db, tender_id=tender.id, content=content())
    row = create(db, tender_id=tender.id, alternative_id=alt.id, payload=EvaluationCreate(
        expected_alternative_revision=1, expected_alternative_fingerprint=alt.current_revision.fingerprint,
        expected_scope_snapshot_fingerprint=snapshot(db, tender_id=tender.id).fingerprint))
    assert row.items == () and row.overall_status == 'NOT_EVALUATED'


def test_snapshot_excludes_incidental_times(db, context):
    scope, _ = context
    before = snapshot(db, tender_id=scope.tender_id).fingerprint
    scope.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db.flush()
    assert snapshot(db, tender_id=scope.tender_id).fingerprint == before


def test_missing_provenance_is_unresolved(db, context):
    from tests.test_scope_review import _document
    scope, _ = context
    _, other_page = _document(db, scope.tender_id)
    scope.document_page_id = other_page.id  # page exists, but belongs to another document
    db.flush()
    row = evaluation(db, context)
    assert row.scope_snapshot.unresolved
    assert row.items[0].snapshot.effective_status == 'UNRESOLVED_SOURCE'
    assert row.overall_status == 'REVIEW_REQUIRED'


def test_pending_human_fact_can_become_accepted(db):
    scope = _scope(db, review_required=True)
    alt = create_technical_alternative(db, tender_id=scope.tender_id, content=content())
    old = evaluation(db, (scope, alt))
    _review(db, scope, 'CONFIRMED')
    new = evaluation(db, (scope, alt))
    assert old.scope_snapshot.unresolved and not new.scope_snapshot.unresolved
    assert new.items[0].snapshot.accepted_execution_scope
    assert reread(db, old).applicability == 'STALE_SCOPE'


def test_database_rejects_wrong_revision_binding(db, context):
    row = evaluation(db, context)
    other = create_technical_alternative(db, tender_id=row.tender_id, content=content())
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Evaluation(tender_id=row.tender_id, alternative_id=other.id,
            alternative_revision_id=row.alternative_revision.id, alternative_revision=1,
            alternative_fingerprint=row.alternative_revision.fingerprint,
            scope_snapshot_fingerprint=row.scope_snapshot.fingerprint,
            scope_snapshot=row.scope_snapshot.model_dump(mode='json')))
        db.flush()


def test_concurrent_creation_idempotent_and_decisions_fail_closed():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import text
    from app.database import SessionLocal
    with SessionLocal.begin() as seed:
        scope = _scope(seed, review_required=False)
        tender_id = scope.tender_id
        alt = create_technical_alternative(seed, tender_id=scope.tender_id, content=content())
        payload = expected(seed, scope, alt)
    barrier = Barrier(2)
    def freeze():
        with SessionLocal.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            return create(session, tender_id=tender_id, alternative_id=alt.id, payload=payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(freeze) for _ in range(2)]
        rows = [future.result(timeout=10) for future in futures]
    assert rows[0].id == rows[1].id
    barrier = Barrier(2)
    def assess():
        with SessionLocal.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            try:
                decision(session, rows[0])
                return 'appended'
            except AlternativeComplianceConflict as exc:
                return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(assess) for _ in range(2)]
        assert sorted(future.result(timeout=10) for future in futures) == ['COMPLIANCE_DECISION_REVISION_CONFLICT', 'appended']
    with SessionLocal() as session:
        assert len(reread(session, rows[0]).items[0].decisions) == 1


def test_item_must_match_frozen_scope(db, context):
    row = evaluation(db, context)
    bad = row.items[0].snapshot.model_dump(mode='json')
    bad['effective_description'] = 'Invented replacement obligation'
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Item(evaluation_id=row.id, tender_id=row.tender_id, alternative_id=row.alternative_id,
            item_key=row.items[0].item_key, scope_detail_id=row.items[0].item_key,
            item_index=1, snapshot=bad))
        db.flush()
    assert len(reread(db, row).items) == 1


def test_unflushed_scope_not_overwritten_by_read(db, context):
    scope, _ = context
    scope.description = 'Pending human-controlled edit'
    with pytest.raises(AlternativeComplianceConflict, match='SCOPE_CONTEXT_UNFLUSHED'):
        snapshot(db, tender_id=scope.tender_id)
    assert scope.description == 'Pending human-controlled edit' and scope in db.dirty
