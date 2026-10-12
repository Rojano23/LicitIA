"""Synthetic HTTP contracts using real PostgreSQL and projection services."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from app.database import get_db
from app.main import app
from app.models import TenderScopeReview
from test_scope_review import db, _scope, _effect, _regenerate

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db)

def path(scope):
    return f"/tenders/{scope.tender_id}/scope-review/{scope.id}"

def read(client, scope):
    response = client.get(path(scope))
    assert response.status_code == 200, response.text
    return response.json()

def payload(view, decision="CONFIRMED"):
    result = dict(decision=decision, expected_projection_fingerprint=view["projection_fingerprint"],
                  expected_current_review_revision=view["current_review_revision"])
    if decision == "CORRECTED":
        result["correction"] = {"description": "Corrección humana"}
    return result

def post(client, scope, data):
    return client.post(path(scope) + "/decisions", json=data)

def count(db):
    return db.scalar(select(func.count()).select_from(TenderScopeReview))

def test_a01_a02_queue_and_detail(client, db):
    scope = _scope(db)
    view = read(client, scope)
    assert client.get(f"/tenders/{scope.tender_id}/scope-review").json() == [view]
    assert view["current"]["machine"]["source_locator"] == scope.source_locator
    assert view["current"]["source_projection"]["diagnostics"][0]["code"] == "FACT_REVIEW_REQUIRED"
    assert view["current"]["effective_status"] == "PENDING"
    assert view["history"] == [] and view["reviewable"]
    assert view["latest_applicable_review"] is None

@pytest.mark.parametrize("decision", ["CONFIRMED", "CORRECTED", "REJECTED"])
def test_a03_a04_a05_decisions(client, db, decision):
    scope = _scope(db)
    view = read(client, scope)
    result = post(client, scope, payload(view, decision))
    assert result.status_code == 200, result.text
    current = result.json()["current"]
    assert current["machine"] == view["current"]["machine"]
    assert current["effective_status"] == decision
    assert current["accepted_execution_scope"] is (decision != "REJECTED")
    assert current["effective_description"] == ("Corrección humana" if decision == "CORRECTED" else scope.description)
    assert result.json()["history"][0]["applicable"]
    assert result.json()["latest_applicable_review"]["revision"] == 1

@pytest.mark.parametrize("change", ["client", "machine", "projection"])
def test_a06_stale_target(client, db, change):
    scope = _scope(db)
    data = payload(read(client, scope))
    if change == "client":
        data["expected_projection_fingerprint"] = "0" * 64
    elif change == "machine":
        scope.description = "Nueva evidencia"
        db.flush()
    else:
        _effect(db, scope, "AMENDS", "PARTIAL")
    before = count(db)
    response = post(client, scope, data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCOPE_REVIEW_TARGET_STALE"
    assert count(db) == before

def test_a07_revision_conflict(client, db):
    scope = _scope(db)
    data = payload(read(client, scope))
    data["expected_current_review_revision"] = 8
    before = count(db)
    response = post(client, scope, data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCOPE_REVIEW_REVISION_CONFLICT"
    assert count(db) == before

def test_a08_regenerated_history(client, db):
    scope = _scope(db)
    assert post(client, scope, payload(read(client, scope))).status_code == 200
    regenerated = _regenerate(db, scope)
    view = read(client, regenerated)
    assert view["current"]["human_review_status"] == "NO_REVIEW"
    assert view["latest_applicable_review"] is None
    archived = read(client, scope)
    assert archived["current"] is None and not archived["reviewable"]
    assert archived["history"][0]["reason"] == "TARGET_REMOVED"
    assert not archived["history"][0]["applicable"]
    assert post(client, scope, payload(view)).status_code == 404

@pytest.mark.parametrize("effect_type,effect_scope", [
    ("SUPERSEDES", "DOCUMENT_WIDE"), ("REVOKES", "DOCUMENT_WIDE"),
    ("SUPERSEDES", "PARTIAL"), ("REVOKES", "PARTIAL"),
])
def test_a09_blocked(client, db, effect_type, effect_scope):
    scope = _scope(db)
    _effect(db, scope, effect_type, effect_scope)
    view = read(client, scope)
    assert not view["reviewable"] and view["not_reviewable_reason"]
    assert view["current"]["effective_status"] == "SOURCE_BLOCKED"
    before = count(db)
    response = post(client, scope, payload(view))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCOPE_SOURCE_NOT_REVIEWABLE"
    assert count(db) == before

def test_a10_cross_tender_missing(client, db):
    scope, other = _scope(db), _scope(db)
    target = f"/tenders/{other.tender_id}/scope-review/{scope.id}"
    before = count(db)
    assert client.get(target).status_code == 404
    assert client.post(target + "/decisions", json=payload(read(client, scope))).status_code == 404
    assert client.get(f"/tenders/{uuid4()}/scope-review").status_code == 404
    assert client.get(f"/tenders/{scope.tender_id}/scope-review/{uuid4()}").status_code == 404
    assert count(db) == before

@pytest.mark.parametrize("invalid", [
    {"correction": {"description": " "}}, {"correction": {"description": 1}},
    {"correction": {"description": "valid", "quantity_raw": "9"}}, {"correction": None},
    {"decision": "CONFIRMED", "correction": {"description": "valid"}},
    {"expected_current_review_revision": "1"}, {"expected_current_review_revision": True},
    {"extra": 1}, {"note": 42},
])
def test_a11_invalid(client, db, invalid):
    scope = _scope(db)
    data = payload(read(client, scope), "CORRECTED")
    data.update(invalid)
    before = count(db)
    assert post(client, scope, data).status_code == 422
    assert count(db) == before

def test_a12_ordering(client, db):
    scope = _scope(db)
    for decision in ["REJECTED", "CORRECTED", "CONFIRMED"]:
        assert post(client, scope, payload(read(client, scope), decision)).status_code == 200
    view = read(client, scope)
    assert [entry["review"]["revision"] for entry in view["history"]] == [1, 2, 3]
    assert [entry["reason"] for entry in view["history"]] == ["HISTORICAL_REVISION", "HISTORICAL_REVISION", "CURRENT"]
    regenerated = _regenerate(db, scope)
    queue = client.get(f"/tenders/{scope.tender_id}/scope-review").json()
    assert [item["scope_detail_id"] for item in queue] == sorted([scope.id, regenerated.id])

def test_a13_post_same_read_path(client, db, monkeypatch):
    import app.scope_review as service
    original, calls = service.get_scope_review_item, []
    def tracked(*args, **kwargs):
        calls.append(kwargs["scope_detail_id"])
        return original(*args, **kwargs)
    scope = _scope(db)
    data = payload(read(client, scope))
    monkeypatch.setattr(service, "get_scope_review_item", tracked)
    response = post(client, scope, data)
    assert calls == [scope.id]
    assert response.json() == read(client, scope)

def test_a14_read_idempotence(client, db):
    scope = _scope(db)
    assert post(client, scope, payload(read(client, scope))).status_code == 200
    statements = []
    connection = db.connection()
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(connection, "before_cursor_execute", capture)
    try:
        view = read(client, scope)
        assert read(client, scope) == view
        client.get(f"/tenders/{scope.tender_id}/scope-review")
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert statements and all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert not db.new and not db.dirty and not db.deleted

def test_a15_duplicate_tab(client, db):
    scope = _scope(db)
    data = payload(read(client, scope))
    assert post(client, scope, data).status_code == 200
    before = count(db)
    response = post(client, scope, data)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCOPE_REVIEW_REVISION_CONFLICT"
    assert count(db) == before

def test_a16_not_required(client, db):
    scope = _scope(db, review_required=False)
    current = read(client, scope)["current"]
    assert current["effective_status"] == "NOT_REQUIRED" and not current["human_resolved_machine_review"]
    required = _scope(db)
    current = post(client, required, payload(read(client, required))).json()["current"]
    assert current["machine_review_required"] and current["human_resolved_machine_review"]

@pytest.mark.parametrize("effect_scope", ["DOCUMENT_WIDE", "PARTIAL"])
def test_a17_ambiguity(client, db, effect_scope):
    scope = _scope(db)
    _effect(db, scope, "SUPERSEDES", effect_scope)
    _effect(db, scope, "SUPERSEDES", effect_scope)
    view = read(client, scope)
    assert view["current"]["source_projection"]["status"] == "REVIEW_REQUIRED"
    assert not view["reviewable"]
    before = count(db)
    assert post(client, scope, payload(view)).status_code == 409
    assert count(db) == before


def test_history_stale_after_source_overlay(client, db):
    scope = _scope(db)
    assert post(client, scope, payload(read(client, scope), "CORRECTED")).status_code == 200
    _effect(db, scope, "AMENDS", "PARTIAL")
    view = read(client, scope)
    assert view["current"]["human_review_status"] == "STALE"
    assert view["current"]["effective_status"] == "STALE_REVIEW"
    assert view["current"]["effective_description"] == scope.description
    assert view["latest_applicable_review"] is None
    assert view["history"][0]["reason"] == "TARGET_CHANGED"
    assert not view["history"][0]["applicable"]
    assert post(client, scope, payload(view)).status_code == 200
    assert [entry["review"]["revision"] for entry in read(client, scope)["history"]] == [1, 2]


def test_archived_history_cross_tender_access(client, db):
    scope, other = _scope(db), _scope(db)
    assert post(client, scope, payload(read(client, scope))).status_code == 200
    _regenerate(db, scope)
    assert client.get(f"/tenders/{other.tender_id}/scope-review/{scope.id}").status_code == 404
