from __future__ import annotations

from dataclasses import fields
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import DocumentPage, Tender, TenderDocument, TenderScopeDetail, TenderScopeReview
from app.scope_details import ScopeDetailCandidate, replace_scope_details_for_artifact
from app.scope_review import (
    ScopeReviewDecisionInput,
    ScopeReviewNotFound,
    ScopeReviewSourceBlocked,
    append_scope_review,
    get_effective_scope_review,
    list_scope_review_history,
    _source_fingerprint,
)
from app.source_effects import SourceEffectCandidate, replace_source_effects_for_artifact


@pytest.fixture
def db():
    # Commit/savepoint tests exercise PostgreSQL without leaving synthetic history.
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


def _document(db: Session, tender_id: str) -> tuple[TenderDocument, DocumentPage]:
    document = TenderDocument(
        tender_id=tender_id, original_filename="synthetic-scope.pdf",
        stored_relative_path=f"synthetic/{uuid4()}.pdf", sha256=uuid4().hex * 2,
        file_size_bytes=0, page_count=1, revision_number=3,
    )
    db.add(document)
    db.flush()
    page = DocumentPage(
        document_id=document.id, page_number=1, text="Evidencia sintética",
        char_count=19, extraction_method="NATIVE_PDF", status="TEXT_EXTRACTED",
    )
    db.add(page)
    db.flush()
    return document, page


def _scope(db: Session, *, review_required: bool = True) -> TenderScopeDetail:
    tender = Tender(title="Scope review synthetic contract", external_reference=str(uuid4()))
    db.add(tender)
    db.flush()
    document, page = _document(db, tender.id)
    candidate = ScopeDetailCandidate(
        tender_id=tender.id, source_document_id=document.id, document_page_id=page.id,
        domain="SERVICE", description="Inspeccionar equipo", applicability="TENDER_WIDE",
        source_method="NATIVE", source_artifact_key=f"native:{page.id}",
        source_locator="numeral 1", source_excerpt="Se deberá inspeccionar el equipo",
        review_required=review_required, source_contract_version="scope-review-test",
        confidence=0.8,
    )
    return replace_scope_details_for_artifact(
        db, tender_id=tender.id, source_document_id=document.id,
        document_page_id=page.id, source_artifact_key=candidate.source_artifact_key,
        candidates=[candidate],
    )[0]


def _read(db: Session, scope: TenderScopeDetail):
    return get_effective_scope_review(db, tender_id=scope.tender_id, scope_detail_id=scope.id)


def _review(db: Session, scope: TenderScopeDetail, decision: str = "CONFIRMED"):
    payload = {"decision": decision, "note": "Decisión humana sintética"}
    if decision == "CORRECTED":
        payload["correction"] = {"description": "Inspeccionar y documentar el equipo"}
    return append_scope_review(
        db, tender_id=scope.tender_id, scope_detail_id=scope.id,
        decision=ScopeReviewDecisionInput.model_validate(payload),
    )


def _effect(db: Session, scope: TenderScopeDetail, effect_type: str, effect_scope: str = "DOCUMENT_WIDE"):
    document, page = _document(db, scope.tender_id)
    artifact_key = f"effect:{uuid4()}"
    candidate = SourceEffectCandidate(
        tender_id=scope.tender_id, acting_document_id=document.id,
        affected_document_id=scope.source_document_id, document_page_id=page.id,
        affected_document_page_id=None, effect_type=effect_type, effect_scope=effect_scope,
        affected_document_ref_raw=None,
        affected_locator_raw=scope.source_locator if effect_scope == "PARTIAL" else None,
        effective_date_raw=None, source_method="NATIVE", source_artifact_key=artifact_key,
        source_locator="page:1", source_excerpt="Efecto sintético explícito",
        review_required=False, confidence=1.0, source_contract_version="scope-review-test",
        source_analysis_id=None, source_page_result_id=None,
    )
    return replace_source_effects_for_artifact(
        db, tender_id=scope.tender_id, acting_document_id=document.id,
        document_page_id=page.id, source_artifact_key=artifact_key, candidates=[candidate],
    )[0]


@pytest.mark.parametrize("required,status,accepted", [(True, "PENDING", False), (False, "NOT_REQUIRED", True)])
def test_r01_no_review(db, required, status, accepted):
    scope = _scope(db, review_required=required)
    view = _read(db, scope)
    assert view.effective_status == status
    assert view.accepted_execution_scope is accepted
    assert view.machine.description == view.effective_description == scope.description
    assert view.human_review_status == "NO_REVIEW"
    assert view.latest_review is None


def test_r02_confirm_preserves_machine_evidence(db):
    scope = _scope(db)
    before = _read(db, scope).machine
    review = _review(db, scope)
    db.commit()
    db.expire_all()
    view = _read(db, scope)
    assert view.effective_status == "CONFIRMED"
    assert view.accepted_execution_scope
    assert view.human_resolved_machine_review
    assert view.machine == review.machine_snapshot == before
    assert view.machine.document_revision == 3
    assert view.machine.source_page == 1
    assert view.effective_description == before.description
    assert view.latest_review.reviewed_at.tzinfo is not None


def test_r03_correct_is_separate_and_durable(db):
    scope = _scope(db)
    before = _read(db, scope).machine
    review = _review(db, scope, "CORRECTED")
    db.commit()
    with Session(bind=db.get_bind()) as reader:
        view = _read(reader, scope)
        assert view.effective_description == review.correction.description
        assert view.effective_status == "CORRECTED"
        assert view.accepted_execution_scope
        assert view.machine == before
        assert reader.get(TenderScopeDetail, scope.id).description == before.description


def test_r04_reject_preserves_row(db):
    scope = _scope(db)
    _review(db, scope, "REJECTED")
    db.commit()
    view = _read(db, scope)
    assert view.effective_status == "REJECTED"
    assert not view.accepted_execution_scope
    assert db.get(TenderScopeDetail, scope.id) is not None
    assert view.effective_description == view.machine.description


def test_r05_history_latest_uses_revision_not_timestamp(db):
    scope = _scope(db)
    first = _review(db, scope, "REJECTED")
    second = _review(db, scope, "CORRECTED")
    third = _review(db, scope, "CONFIRMED")
    db.commit()
    history = list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id)
    assert [row.id for row in history] == [first.id, second.id, third.id]
    assert [row.revision for row in history] == [1, 2, 3]
    assert _read(db, scope).latest_review.id == third.id
    assert _read(db, scope).effective_description == scope.description


def test_r05_equal_timestamp_latest_remains_deterministic(db):
    scope = _scope(db)
    first = _review(db, scope)
    original = db.get(TenderScopeReview, first.id)
    second = TenderScopeReview(
        tender_id=scope.tender_id, scope_detail_id=scope.id, revision=2, decision="REJECTED",
        reviewed_at=first.reviewed_at, correction=None, machine_snapshot=original.machine_snapshot,
        reviewed_source_fingerprint=original.reviewed_source_fingerprint,
    )
    db.add(second)
    db.flush()
    assert _read(db, scope).latest_review.id == second.id
    assert _read(db, scope).effective_status == "REJECTED"


def test_r06_idempotent_read_performs_only_selects(db):
    scope = _scope(db)
    _review(db, scope)
    before = _read(db, scope)
    statements = []
    connection = db.connection()

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture)
    try:
        assert _read(db, scope) == before
        assert _read(db, scope) == before
        list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert statements and all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert not db.dirty and not db.new and not db.deleted


@pytest.mark.parametrize("payload", [
    {"decision": "CORRECTED"},
    {"decision": "CORRECTED", "correction": {}},
    {"decision": "CORRECTED", "correction": {"description": "  "}},
    {"decision": "CORRECTED", "correction": {"description": 1}},
    {"decision": "CORRECTED", "correction": {"description": "valid", "quantity_raw": "9"}},
    {"decision": "CONFIRMED", "correction": {"description": "valid"}},
    {"decision": "REJECTED", "correction": {"description": "valid"}},
    {"decision": "UNSUPPORTED"},
])
def test_r07_invalid_input_has_no_partial_persistence(db, payload):
    scope = _scope(db)
    with pytest.raises(ValidationError):
        decision = ScopeReviewDecisionInput.model_validate(payload)
        append_scope_review(db, tender_id=scope.tender_id, scope_detail_id=scope.id, decision=decision)
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == ()


def test_r07_model_construct_cannot_bypass_validation(db):
    scope = _scope(db)
    with pytest.raises(ValidationError):
        append_scope_review(
            db, tender_id=scope.tender_id, scope_detail_id=scope.id,
            decision=ScopeReviewDecisionInput.model_construct(decision="CORRECTED", correction=None),
        )
    assert not db.new


def test_r08_cross_tender_service_and_database_fail_closed(db):
    scope = _scope(db)
    other = _scope(db)
    with pytest.raises(ScopeReviewNotFound):
        append_scope_review(
            db, tender_id=other.tender_id, scope_detail_id=scope.id,
            decision=ScopeReviewDecisionInput(decision="CONFIRMED"),
        )
    with pytest.raises(ScopeReviewNotFound):
        get_effective_scope_review(db, tender_id=other.tender_id, scope_detail_id=scope.id)
    with db.begin_nested():
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(TenderScopeReview(
                tender_id=other.tender_id, scope_detail_id=scope.id, revision=1,
                decision="CONFIRMED", machine_snapshot={}, reviewed_source_fingerprint="0" * 64,
            ))
            db.flush()
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == ()


def test_r09_missing_scope_detail(db):
    scope = _scope(db)
    with pytest.raises(ScopeReviewNotFound):
        get_effective_scope_review(db, tender_id=scope.tender_id, scope_detail_id=str(uuid4()))
    with pytest.raises(ScopeReviewNotFound):
        append_scope_review(
            db, tender_id=scope.tender_id, scope_detail_id=str(uuid4()),
            decision=ScopeReviewDecisionInput(decision="CONFIRMED"),
        )


def test_r10_machine_review_state_and_reason_remain_visible(db):
    scope = _scope(db)
    _review(db, scope)
    view = _read(db, scope)
    assert view.machine_review_required and view.machine.review_required
    assert view.human_resolved_machine_review
    assert view.source_projection.status == "REVIEW_REQUIRED"
    assert [item.code for item in view.source_projection.diagnostics] == ["FACT_REVIEW_REQUIRED"]
    assert db.get(TenderScopeDetail, scope.id).review_required


@pytest.mark.parametrize("effect_type,effect_scope", [
    ("SUPERSEDES", "DOCUMENT_WIDE"), ("REVOKES", "DOCUMENT_WIDE"),
    ("SUPERSEDES", "PARTIAL"), ("REVOKES", "PARTIAL"),
])
@pytest.mark.parametrize("decision", ["CONFIRMED", "CORRECTED"])
def test_r11_review_cannot_revive_terminal_source(db, effect_type, effect_scope, decision):
    scope = _scope(db)
    review = _review(db, scope, decision)
    _effect(db, scope, effect_type, effect_scope)
    view = _read(db, scope)
    assert view.effective_status == "SOURCE_BLOCKED"
    assert view.source_blocked and not view.accepted_execution_scope
    assert not view.human_resolved_machine_review
    assert view.effective_description == scope.description
    assert view.latest_review.id == review.id
    with pytest.raises(ScopeReviewSourceBlocked):
        _review(db, scope)
    assert len(list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id)) == 1


@pytest.mark.parametrize("effect_scope", ["DOCUMENT_WIDE", "PARTIAL"])
def test_r11_source_conflict_cannot_be_resolved_by_fact_confirmation(db, effect_scope):
    scope = _scope(db)
    _review(db, scope)
    _effect(db, scope, "SUPERSEDES", effect_scope)
    _effect(db, scope, "SUPERSEDES", effect_scope)
    view = _read(db, scope)
    assert view.source_blocked and not view.accepted_execution_scope
    assert view.source_projection.status == "REVIEW_REQUIRED"
    with pytest.raises(ScopeReviewSourceBlocked):
        _review(db, scope)


def test_source_overlay_change_makes_old_correction_stale(db):
    scope = _scope(db)
    _review(db, scope, "CORRECTED")
    _effect(db, scope, "AMENDS", "PARTIAL")
    view = _read(db, scope)
    assert not view.source_blocked
    assert view.human_review_status == "STALE"
    assert view.effective_status == "STALE_REVIEW"
    assert not view.accepted_execution_scope
    assert view.effective_description == scope.description
    _review(db, scope, "CONFIRMED")
    assert _read(db, scope).accepted_execution_scope


def test_changed_machine_evidence_does_not_reuse_old_review(db):
    scope = _scope(db)
    review = _review(db, scope, "CORRECTED")
    scope.description = "Nueva evidencia máquina"
    db.flush()
    view = _read(db, scope)
    assert view.effective_status == "STALE_REVIEW"
    assert view.latest_review.machine_snapshot.description == review.machine_snapshot.description
    assert view.effective_description == "Nueva evidencia máquina"


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_history_is_append_only_in_postgresql(db, operation):
    scope = _scope(db)
    review = _review(db, scope)
    with pytest.raises(IntegrityError), db.begin_nested():
        statement = (update(TenderScopeReview).values(note="erase") if operation == "update"
                     else delete(TenderScopeReview))
        db.execute(statement.where(TenderScopeReview.id == review.id))
    assert _read(db, scope).latest_review == review


def _regenerate(db, scope, *, description=None, review_required=None):
    values = {field.name: getattr(scope, field.name) for field in fields(ScopeDetailCandidate)}
    if description is not None:
        values["description"] = description
        values["source_excerpt"] = description
    if review_required is not None:
        values["review_required"] = review_required
    candidate = ScopeDetailCandidate(**values)
    return replace_scope_details_for_artifact(
        db, tender_id=scope.tender_id, source_document_id=scope.source_document_id,
        document_page_id=scope.document_page_id, source_artifact_key=scope.source_artifact_key,
        candidates=[candidate],
    )[0]


def test_r12_reviewed_detail_reprocessing_succeeds(db):
    scope = _scope(db)
    _review(db, scope)
    regenerated = _regenerate(db, scope, description="Alcance reprocesado")
    db.commit()
    assert regenerated.id != scope.id
    assert db.get(TenderScopeDetail, scope.id) is None
    assert db.get(TenderScopeDetail, regenerated.id).description == "Alcance reprocesado"


def test_r13_history_survives_reprocessing_and_removal(db):
    scope = _scope(db)
    reviews = [_review(db, scope, "CONFIRMED"), _review(db, scope, "CORRECTED")]
    regenerated = _regenerate(db, scope, description="Alcance nuevo")
    replace_scope_details_for_artifact(
        db, tender_id=regenerated.tender_id, source_document_id=regenerated.source_document_id,
        document_page_id=regenerated.document_page_id, source_artifact_key=regenerated.source_artifact_key,
        candidates=[],
    )
    db.commit()
    with Session(bind=db.get_bind()) as reader:
        history = list_scope_review_history(reader, tender_id=scope.tender_id, scope_detail_id=scope.id)
        assert list(history) == reviews
        assert reader.get(TenderScopeDetail, scope.id) is None
        assert reader.get(TenderScopeDetail, regenerated.id) is None


def test_r14_changed_projection_invalidates_applicability(db):
    scope = _scope(db)
    review = _review(db, scope)
    regenerated = _regenerate(db, scope, description="Evidencia diferente")
    view = _read(db, regenerated)
    assert view.machine.semantic_fingerprint != review.machine_snapshot.semantic_fingerprint
    assert _source_fingerprint(view.source_projection) != review.reviewed_source_fingerprint
    assert view.human_review_status == "NO_REVIEW"  # Historical identity is not reattached.
    assert view.latest_review is None
    assert view.effective_status == "PENDING"
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


@pytest.mark.parametrize("decision", ["CONFIRMED", "CORRECTED"])
def test_r15_no_automatic_human_decision_carry_forward(db, decision):
    scope = _scope(db)
    review = _review(db, scope, decision)
    regenerated = _regenerate(db, scope, description="Nuevo alcance requiere revisión")
    view = _read(db, regenerated)
    assert not view.accepted_execution_scope and not view.human_resolved_machine_review
    assert view.effective_description == regenerated.description
    assert view.latest_review is None and view.human_review_status == "NO_REVIEW"
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


def test_r16_rejected_v1_does_not_reject_changed_v2(db):
    scope = _scope(db)
    review = _review(db, scope, "REJECTED")
    regenerated = _regenerate(db, scope, description="Nuevo alcance", review_required=False)
    view = _read(db, regenerated)
    assert view.effective_status == "NOT_REQUIRED" and view.accepted_execution_scope
    assert not view.human_resolved_machine_review and view.latest_review is None
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


def test_r17_historical_provenance_survives_replacement(db):
    scope = _scope(db)
    evidence = _read(db, scope).machine
    review = _review(db, scope, "CORRECTED")
    _regenerate(db, scope, description="Nueva evidencia")
    db.commit()
    db.expire_all()
    history = list_scope_review_history(db, tender_id=review.tender_id, scope_detail_id=review.scope_detail_id)
    assert history == (review,)
    snapshot = history[0].machine_snapshot
    assert snapshot == evidence
    assert snapshot.source_document_id == evidence.source_document_id
    assert snapshot.document_page_id == evidence.document_page_id
    assert snapshot.document_revision == 3 and snapshot.source_page == 1
    assert snapshot.source_excerpt == evidence.source_excerpt
    assert snapshot.source_locator == evidence.source_locator
    assert history[0].reviewed_source_fingerprint == review.reviewed_source_fingerprint


def test_r18_cross_tender_safety_after_regeneration(db):
    scope = _scope(db)
    review = _review(db, scope)
    regenerated = _regenerate(db, scope, description="Nueva evidencia")
    other = _scope(db)
    forged_snapshot = _read(db, regenerated).machine.model_dump(mode="json")
    forged_snapshot["tender_id"] = other.tender_id
    with pytest.raises(ScopeReviewNotFound):
        list_scope_review_history(db, tender_id=other.tender_id, scope_detail_id=scope.id)
    with pytest.raises(ScopeReviewNotFound):
        append_scope_review(
            db, tender_id=other.tender_id, scope_detail_id=regenerated.id,
            decision=ScopeReviewDecisionInput(decision="CONFIRMED"),
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TenderScopeReview(
            tender_id=other.tender_id, scope_detail_id=regenerated.id, revision=1,
            decision="CONFIRMED", machine_snapshot=forged_snapshot,
            reviewed_source_fingerprint=review.reviewed_source_fingerprint,
        ))
        db.flush()
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_r19_historical_review_remains_append_only(db, operation):
    scope = _scope(db)
    review = _review(db, scope)
    _regenerate(db, scope, description="Nueva evidencia")
    with pytest.raises(IntegrityError), db.begin_nested():
        statement = (update(TenderScopeReview).values(note="erase") if operation == "update"
                     else delete(TenderScopeReview))
        db.execute(statement.where(TenderScopeReview.id == review.id))
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


def test_identical_content_regeneration_never_reattaches_old_review(db):
    scope = _scope(db)
    review = _review(db, scope)
    regenerated = _regenerate(db, scope)
    assert regenerated.semantic_fingerprint == review.machine_snapshot.semantic_fingerprint
    assert regenerated.id != review.scope_detail_id
    view = _read(db, regenerated)
    assert _source_fingerprint(view.source_projection) != review.reviewed_source_fingerprint
    assert view.human_review_status == "NO_REVIEW" and not view.accepted_execution_scope
    new_review = _review(db, regenerated)
    assert new_review.revision == 1 and new_review.scope_detail_id == regenerated.id
    assert _read(db, regenerated).human_review_status == "CURRENT"
    assert list_scope_review_history(db, tender_id=scope.tender_id, scope_detail_id=scope.id) == (review,)


@pytest.mark.parametrize("effect_type,effect_scope", [
    ("SUPERSEDES", "DOCUMENT_WIDE"), ("REVOKES", "DOCUMENT_WIDE"),
    ("SUPERSEDES", "PARTIAL"), ("REVOKES", "PARTIAL"),
])
def test_regeneration_does_not_revive_terminal_source(db, effect_type, effect_scope):
    scope = _scope(db)
    _review(db, scope, "CORRECTED")
    _effect(db, scope, effect_type, effect_scope)
    regenerated = _regenerate(db, scope, description="Nuevo alcance", review_required=False)
    view = _read(db, regenerated)
    assert view.source_blocked and view.effective_status == "SOURCE_BLOCKED"
    assert not view.accepted_execution_scope and view.latest_review is None


@pytest.mark.parametrize("correction", [{}, {"description": ""}, {"description": "valid", "extra": "x"}, {"description": 1}])
def test_database_rejects_invalid_correction(db, correction):
    scope = _scope(db)
    evidence = _read(db, scope).machine
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TenderScopeReview(
            tender_id=scope.tender_id, scope_detail_id=scope.id, revision=1,
            decision="CORRECTED", correction=correction,
            machine_snapshot=evidence.model_dump(mode="json"), reviewed_source_fingerprint="0" * 64,
        ))
        db.flush()
    assert db.scalar(select(func.count()).select_from(TenderScopeReview).where(
        TenderScopeReview.scope_detail_id == scope.id,
    )) == 0


def test_missing_or_cross_tender_source_provenance_blocks_review(db):
    scope = _scope(db)
    other = _scope(db)
    scope.source_document_id = other.source_document_id
    db.flush()
    with pytest.raises(ScopeReviewSourceBlocked):
        _review(db, scope)
    assert not db.new


def test_read_does_not_flush_unrelated_pending_writes(db):
    scope = _scope(db)
    pending = Tender(title="Unflushed unrelated tender")
    db.add(pending)
    _read(db, scope)
    assert pending in db.new and pending.id is None
