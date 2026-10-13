from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import TechnicalAlternative, TechnicalAlternativeRevision, Tender
from app.technical_alternatives import (
    TechnicalAlternativeContent as Content, TechnicalAlternativeAppend as Append,
    TechnicalAlternativeConflict, TechnicalAlternativeNotFound,
    create_technical_alternative as create, append_technical_alternative_revision as append,
    get_technical_alternative as read, list_technical_alternatives as listing,
    archive_technical_alternative as archive, technical_content_fingerprint as fingerprint,
)


@pytest.fixture
def db():
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def tender(db):
    row = Tender(title="Synthetic technical strategy")
    db.add(row)
    db.flush()
    return row


def content(**changes):
    return Content(name="Plan A", technical_description="Inspección manual documentada", **changes)


def created(db, tender):
    return create(db, tender_id=tender.id, content=content())


def revised(db, row, expected=1, **changes):
    values = content().model_dump()
    values.update(changes)
    return append(db, tender_id=row.tender_id, alternative_id=row.id,
                  content=Append(**values, expected_current_revision=expected))


def test_ta01_create(db, tender):
    row = created(db, tender)
    assert db.get(TechnicalAlternative, row.id).tender_id == tender.id
    assert row.current_revision.revision == 1 and len(row.revisions) == 1


def test_ta02_validation():
    for changes in ({"name": " "}, {"name": "x" * 256}, {"technical_description": " "},
                    {"name": 3}, {"lifecycle_state": "BEST"}, {"assumptions": 7}):
        with pytest.raises(ValidationError):
            Content.model_validate({**content().model_dump(), **changes})
    for field in ("name", "technical_description"):
        values = content().model_dump()
        del values[field]
        with pytest.raises(ValidationError):
            Content.model_validate(values)


def test_ta03_current_uses_revision_not_timestamp(db, tender):
    row = created(db, tender)
    db.add(TechnicalAlternativeRevision(alternative_id=row.id, tender_id=tender.id, revision=2,
        **content().model_dump(), fingerprint=fingerprint(content()),
        created_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
    db.flush()
    result = read(db, tender_id=tender.id, alternative_id=row.id)
    assert result.current_revision.revision == 2
    assert result.current_revision.created_at < result.revisions[0].created_at


def test_ta04_append_preserves(db, tender):
    row = created(db, tender)
    result = revised(db, row, technical_description="Plan humano distinto")
    assert [r.revision for r in result.revisions] == [1, 2]
    assert result.revisions[0] == row.revisions[0]


def test_ta05_fingerprint_deterministic():
    assert fingerprint(content()) == fingerprint(Content(name=" Plan A ", technical_description=" Inspección manual documentada "))
    assert fingerprint(content(assumptions="")) == fingerprint(content())


def test_ta06_technical_change():
    for field in ("name", "technical_description", "assumptions"):
        values = content().model_dump()
        values[field] = "Cambio humano"
        assert fingerprint(Content(**values)) != fingerprint(content())


def test_ta07_incidental_fields(db, tender):
    a, b = created(db, tender), created(db, tender)
    c = revised(db, a, notes="Nueva nota", lifecycle_state="ACTIVE")
    assert a.id != b.id
    assert a.current_revision.id != b.current_revision.id
    assert a.current_revision.fingerprint == b.current_revision.fingerprint == c.current_revision.fingerprint
    incidental = a.current_revision.model_copy(update={
        "id": str(uuid4()), "alternative_id": str(uuid4()), "tender_id": str(uuid4()),
        "revision": 99, "created_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
    })
    assert fingerprint(incidental) == a.current_revision.fingerprint


def test_ta08_coexist(db, tender):
    a, b = created(db, tender), created(db, tender)
    revised(db, a, lifecycle_state="ACTIVE")
    revised(db, b, lifecycle_state="ACTIVE")
    assert len(listing(db, tender_id=tender.id)) == 2
    assert all(row.current_revision.lifecycle_state == "ACTIVE" for row in listing(db, tender_id=tender.id))


def test_ta09_unique(db, tender):
    row = created(db, tender)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TechnicalAlternativeRevision(alternative_id=row.id, tender_id=tender.id, revision=1,
            **content().model_dump(), fingerprint=fingerprint(content())))
        db.flush()
    assert len(read(db, tender_id=tender.id, alternative_id=row.id).revisions) == 1


def test_ta10_expectation_success(db, tender):
    row = revised(db, created(db, tender))
    assert revised(db, row, expected=2).current_revision.revision == 3


def test_ta11_stale(db, tender):
    row = revised(db, created(db, tender))
    with pytest.raises(TechnicalAlternativeConflict):
        revised(db, row)
    assert len(read(db, tender_id=tender.id, alternative_id=row.id).revisions) == 2


def test_ta12_cross_tender(db, tender):
    row = created(db, tender)
    other = Tender(title="Other synthetic tender")
    db.add(other)
    db.flush()
    with pytest.raises(TechnicalAlternativeNotFound):
        append(db, tender_id=other.id, alternative_id=row.id,
               content=Append(**content().model_dump(), expected_current_revision=1))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TechnicalAlternativeRevision(alternative_id=row.id, tender_id=other.id, revision=2,
            **content().model_dump(), fingerprint=fingerprint(content())))
        db.flush()
    assert listing(db, tender_id=other.id) == ()


def test_ta13_archive_revision(db, tender):
    row = created(db, tender)
    result = archive(db, tender_id=tender.id, alternative_id=row.id, expected_current_revision=1)
    assert len(result.revisions) == 2 and result.current_revision.lifecycle_state == "ARCHIVED"
    assert result.revisions[0] == row.current_revision
    assert result.current_revision.fingerprint == row.current_revision.fingerprint


def test_ta14_archived_queryable(db, tender):
    row = created(db, tender)
    archive(db, tender_id=tender.id, alternative_id=row.id, expected_current_revision=1)
    assert listing(db, tender_id=tender.id)[0].current_revision.lifecycle_state == "ARCHIVED"
    assert read(db, tender_id=tender.id, alternative_id=row.id).current_revision.revision == 2


def test_ta15_deterministic_list(db, tender):
    for _ in range(3):
        created(db, tender)
    ids = [row.id for row in listing(db, tender_id=tender.id)]
    assert ids == sorted(ids)


def test_ta16_read_no_write(db, tender):
    row = created(db, tender)
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        assert read(db, tender_id=tender.id, alternative_id=row.id) == read(db, tender_id=tender.id, alternative_id=row.id)
        assert listing(db, tender_id=tender.id) == listing(db, tender_id=tender.id)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)


def test_ta17_atomic_failed_initial_revision(db, tender, monkeypatch):
    import app.technical_alternatives as service
    original = service._insert_revision
    def invalid(db, identity, values, revision):
        original(db, identity, values.model_copy(update={"name": " "}), revision)
    monkeypatch.setattr(service, "_insert_revision", invalid)
    with pytest.raises(IntegrityError):
        created(db, tender)
    assert listing(db, tender_id=tender.id) == ()


def test_ta18_append_only(db, tender):
    row = created(db, tender)
    for statement in (
        update(TechnicalAlternativeRevision).where(TechnicalAlternativeRevision.alternative_id == row.id).values(notes="mutated"),
        delete(TechnicalAlternativeRevision).where(TechnicalAlternativeRevision.alternative_id == row.id),
        update(TechnicalAlternative).where(TechnicalAlternative.id == row.id).values(tender_id=str(uuid4())),
        delete(TechnicalAlternative).where(TechnicalAlternative.id == row.id),
    ):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(statement)
    assert read(db, tender_id=tender.id, alternative_id=row.id) == row


def untouched_state(db, tender, tables):
    from tests.test_scope_review import _scope, _review, _effect
    scope = _scope(db)
    _review(db, scope)
    _effect(db, scope, "CLARIFIES", "PARTIAL")
    def snapshot():
        return {table: db.execute(select(table).where(table.c.tender_id == scope.tender_id)).all() for table in tables}
    before = snapshot()
    row = create(db, tender_id=scope.tender_id, content=content())
    revised(db, row)
    archive(db, tender_id=scope.tender_id, alternative_id=row.id, expected_current_revision=2)
    assert snapshot() == before


def test_ta19_scope_untouched(db, tender):
    from app.models import TenderScopeDetail, TenderScopeAttribute, TenderScopeQuantity
    untouched_state(db, tender, [cls.__table__ for cls in (TenderScopeDetail, TenderScopeAttribute, TenderScopeQuantity)])


def test_ta20_effects_review_untouched(db, tender):
    from app.models import TenderScopeReview, TenderSourceEffect
    untouched_state(db, tender, [cls.__table__ for cls in (TenderScopeReview, TenderSourceEffect)])


def test_ta11_concurrent_writers_only_one_appends():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import text
    from app.database import SessionLocal
    with SessionLocal.begin() as seed:
        tender = Tender(title="Synthetic concurrent technical alternative")
        seed.add(tender)
        seed.flush()
        row = created(seed, tender)
    barrier = Barrier(2)
    def write():
        with SessionLocal.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            try:
                revised(session, row)
                return "appended"
            except TechnicalAlternativeConflict:
                return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write) for _ in range(2)]
        assert sorted(future.result(timeout=10) for future in futures) == ["appended", "conflict"]
    with SessionLocal() as session:
        assert [r.revision for r in read(session, tender_id=row.tender_id, alternative_id=row.id).revisions] == [1, 2]


def test_ta17_invalid_append_no_partial_persistence(db, tender):
    row = created(db, tender)
    invalid = Append(**content().model_dump(), expected_current_revision=1).model_copy(update={"technical_description": " "})
    with pytest.raises(ValidationError):
        append(db, tender_id=tender.id, alternative_id=row.id, content=invalid)
    assert read(db, tender_id=tender.id, alternative_id=row.id) == row


def test_missing_tender_or_alternative(db, tender):
    with pytest.raises(TechnicalAlternativeNotFound):
        create(db, tender_id=str(uuid4()), content=content())
    with pytest.raises(TechnicalAlternativeNotFound):
        read(db, tender_id=tender.id, alternative_id=str(uuid4()))
    with pytest.raises(TechnicalAlternativeNotFound):
        listing(db, tender_id=str(uuid4()))
