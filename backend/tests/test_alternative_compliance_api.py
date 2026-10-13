"""Typed HTTP contracts over real synthetic persisted domain data."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.database import get_db
from app.main import app
from tests.test_alternative_compliance import db, context, evaluation, expected, record_snapshot
from tests.test_scope_review import _scope, _regenerate
from tests.test_technical_alternatives import content, revised
from app.models import AlternativeScopeComplianceEvaluation, AlternativeScopeComplianceItem, AlternativeScopeComplianceDecision


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.pop(get_db)


def path(context):
    scope, alt = context
    return f'/tenders/{scope.tender_id}/technical-alternatives/{alt.id}'


def evalpath(context, row):
    return path(context) + '/compliance/' + row.id


def create_eval(client, db, context, **changes):
    data = expected(db, *context).model_dump()
    data.update(changes)
    return client.post(path(context) + '/compliance', json=data)


def assessment(client, context, row, status='COMPLIANT', revision=None):
    return client.post(evalpath(context, row) + '/items/' + row.items[0].item_key + '/decisions',
        json={'status': status, 'rationale': 'Juicio técnico humano', 'evidence_note': 'Referencia sintética',
              'expected_current_decision_revision': revision})


def revision(client, context, state='ACTIVE', expected_revision=1):
    return client.post(path(context) + '/revisions', json={**content().model_dump(),
                      'lifecycle_state': state, 'expected_current_revision': expected_revision})


def test_api01_create(client, context):
    response = client.post(path(context).rsplit('/', 1)[0], json=content().model_dump())
    assert response.status_code == 201, response.text
    assert response.json()['current_revision']['revision'] == 1


def test_api02_list_deterministic(client, context):
    url = path(context).rsplit('/', 1)[0]
    client.post(url, json=content().model_dump())
    result = client.get(url)
    assert result.status_code == 200
    assert [row['id'] for row in result.json()] == sorted(row['id'] for row in result.json())


def test_api03_detail_history(client, context):
    result = client.get(path(context))
    assert result.status_code == 200
    assert len(result.json()['revisions']) == 1
    assert result.json()['current_revision']['fingerprint'] == context[1].current_revision.fingerprint


def test_api04_append(client, context):
    result = revision(client, context)
    assert result.status_code == 200, result.text
    assert len(result.json()['revisions']) == 2 and result.json()['current_revision']['revision'] == 2


def test_api05_revision_conflict(client, context):
    result = revision(client, context, expected_revision=7)
    assert result.status_code == 409 and result.json()['detail']['code'] == 'ALTERNATIVE_REVISION_CONFLICT'


def test_api06_archive_revision(client, context):
    result = revision(client, context, state='ARCHIVED')
    assert result.status_code == 200
    assert result.json()['current_revision']['lifecycle_state'] == 'ARCHIVED'
    assert len(result.json()['revisions']) == 2


def test_api07_create_evaluation(client, db, context):
    result = create_eval(client, db, context)
    assert result.status_code == 200, result.text
    assert result.json()['applicability'] == 'CURRENT'
    snapshot = client.get(f'/tenders/{context[0].tender_id}/alternative-scope-snapshot')
    assert snapshot.status_code == 200 and snapshot.json()['fingerprint'] == result.json()['scope_snapshot']['fingerprint']
    assert create_eval(client, db, context).json()['id'] == result.json()['id']


@pytest.mark.parametrize(('change', 'code'), [
    ({'expected_alternative_revision': 2}, 'ALTERNATIVE_REVISION_CONFLICT'),
    ({'expected_alternative_fingerprint': '0' * 64}, 'ALTERNATIVE_FINGERPRINT_STALE'),
])
def test_api08_alternative_stale(client, db, context, change, code):
    result = create_eval(client, db, context, **change)
    assert result.status_code == 409 and result.json()['detail']['code'] == code


def test_api09_scope_stale(client, db, context):
    result = create_eval(client, db, context, expected_scope_snapshot_fingerprint='0' * 64)
    assert result.status_code == 409 and result.json()['detail']['code'] == 'SCOPE_SNAPSHOT_STALE'


def test_api10_detail_frozen_items(client, db, context):
    row = evaluation(db, context)
    response = client.get(evalpath(context, row))
    assert response.status_code == 200, response.text
    item = response.json()['items'][0]
    assert item['snapshot']['machine']['source_locator'] == context[0].source_locator
    assert item['latest_decision'] is None and item['decisions'] == []


def test_api11_compliant(client, db, context):
    row = evaluation(db, context)
    result = assessment(client, context, row)
    assert result.status_code == 200, result.text
    assert result.json()['overall_status'] == 'COMPLIANT'


@pytest.mark.parametrize('status', ['PARTIAL', 'NON_COMPLIANT'])
def test_api12_partial_non_compliant(client, db, context, status):
    row = evaluation(db, context)
    response = assessment(client, context, row, status)
    assert response.status_code == 200 and response.json()['overall_status'] == status


def test_api13_stale_decision_revision(client, db, context):
    row = evaluation(db, context)
    assert assessment(client, context, row).status_code == 200
    result = assessment(client, context, row)
    assert result.status_code == 409 and result.json()['detail']['code'] == 'COMPLIANCE_DECISION_REVISION_CONFLICT'
    assert len(client.get(evalpath(context, row)).json()['items'][0]['decisions']) == 1


def test_api14_stale_evaluation(client, db, context):
    row = evaluation(db, context)
    revision(client, context)
    result = assessment(client, context, row)
    assert result.status_code == 409 and result.json()['detail']['code'] == 'COMPLIANCE_EVALUATION_STALE'


def test_api15_archived_new_evaluation(client, db, context):
    revision(client, context, state='ARCHIVED')
    from app.technical_alternatives import get_technical_alternative
    alt = get_technical_alternative(db, tender_id=context[0].tender_id, alternative_id=context[1].id)
    result = create_eval(client, db, (context[0], alt))
    assert result.status_code == 409 and result.json()['detail']['code'] == 'ALTERNATIVE_ARCHIVED'


def test_api16_stale_history_readable(client, db, context):
    row = evaluation(db, context)
    _regenerate(db, context[0])
    db.commit()
    result = client.get(evalpath(context, row))
    assert result.status_code == 200 and result.json()['applicability'] == 'STALE_SCOPE'
    assert client.get(path(context) + '/compliance').json()[0]['id'] == row.id


def test_api17_aggregate_counts(client, db, context):
    row = evaluation(db, context)
    result = assessment(client, context, row).json()
    assert result['counts'] == {'COMPLIANT': 1, 'PARTIAL': 0, 'NON_COMPLIANT': 0, 'REVIEW_REQUIRED': 0, 'NOT_EVALUATED': 0}


def test_api18_wrong_identity_404(client, db, context):
    row = evaluation(db, context)
    other = _scope(db)
    urls = [path(context).replace(context[0].tender_id, other.tender_id),
            path(context).replace(context[1].id, str(uuid4())),
            evalpath(context, row).replace(row.id, str(uuid4())),
            path(context).replace(context[0].tender_id, str(uuid4()))]
    for url in urls:
        assert client.get(url).status_code == 404
    wrong_item = evalpath(context, row) + '/items/' + str(uuid4()) + '/decisions'
    assert client.post(wrong_item, json={'status': 'COMPLIANT', 'rationale': 'Humano',
        'expected_current_decision_revision': None}).status_code == 404


@pytest.mark.parametrize('data', [
    {'status': 'BEST', 'rationale': 'Humano', 'expected_current_decision_revision': None},
    {'status': 'COMPLIANT', 'rationale': ' ', 'expected_current_decision_revision': None},
    {'status': 'COMPLIANT', 'rationale': 'Humano'},
    {'status': 'COMPLIANT', 'rationale': 'Humano', 'expected_current_decision_revision': True},
    {'status': 'COMPLIANT', 'rationale': 'Humano', 'expected_current_decision_revision': None, 'score': 100},
])
def test_api19_typed_validation(client, db, context, data):
    row = evaluation(db, context)
    result = client.post(evalpath(context, row) + '/items/' + row.items[0].item_key + '/decisions', json=data)
    assert result.status_code == 422
    assert client.get(evalpath(context, row)).json()['items'][0]['decisions'] == []


def test_api20_reads_no_mutation(client, db, context):
    row = evaluation(db, context)
    tables = (AlternativeScopeComplianceEvaluation, AlternativeScopeComplianceItem, AlternativeScopeComplianceDecision)
    before = record_snapshot(db, tables)
    statements = []
    def capture(conn, cursor, statement, params, ctx, many):
        statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', capture)
    try:
        for url in (path(context), path(context).rsplit('/', 1)[0], path(context) + '/compliance', evalpath(context, row)):
            assert client.get(url).status_code == 200
    finally:
        event.remove(db.bind, 'before_cursor_execute', capture)
    assert record_snapshot(db, tables) == before
    assert not any(sql.lstrip().split()[0] in {'INSERT', 'UPDATE', 'DELETE'} for sql in statements)


def test_api_validation_alternative_and_evaluation(client, db, context):
    base = path(context).rsplit('/', 1)[0]
    for payload in ({'name': ' ', 'technical_description': 'Human'},
                    {'name': 'Human', 'technical_description': ' ', 'lifecycle_state': 'ACTIVE'},
                    {**content().model_dump(), 'preferred': True}):
        assert client.post(base, json=payload).status_code == 422
    assert client.post(path(context) + '/revisions', json=content().model_dump()).status_code == 422
    values = expected(db, *context).model_dump()
    for changes in ({'expected_alternative_revision': True},
                    {'expected_alternative_fingerprint': 'invalid'}, {'expected_scope_snapshot_fingerprint': None}):
        assert client.post(path(context) + '/compliance', json={**values, **changes}).status_code == 422


def test_api_database_error_does_not_leak_sql(client, context, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    import app.main as main
    def fail(*args, **kwargs):
        raise IntegrityError('SECRET SQL', {}, Exception('SECRET DB DETAILS'))
    monkeypatch.setattr(main, 'create_technical_alternative', fail)
    response = client.post(path(context).rsplit('/', 1)[0], json=content().model_dump())
    assert response.status_code == 500
    assert response.json()['detail']['code'] == 'ALTERNATIVE_PERSISTENCE_ERROR'
    assert 'SECRET' not in response.text
