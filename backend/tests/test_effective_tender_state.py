from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    NormalizedContent,
    TenderChange,
    TenderDocument,
    TenderEvent,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "EFF-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page(document_id: str, page_number: int, text: str, *, is_current: bool = True) -> str:
    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=page_number,
            text=text,
            char_count=len(text),
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = max(doc.page_count, page_number)
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"
        doc.is_current = is_current
        db.commit()
        return page.id
    finally:
        db.close()


def _seed_normalized(page_id: str, text: str) -> str:
    db = SessionLocal()
    try:
        row = NormalizedContent(
            document_page_id=page_id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"eff-{page_id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _seed_event(
    tender_id: str,
    source_document_id: str,
    *,
    event_type: str,
    review_status: str,
    event_date: date | None,
    event_time: str | None = None,
    human_event_date: date | None = None,
    human_event_time: str | None = None,
    created_at: datetime | None = None,
) -> str:
    db = SessionLocal()
    try:
        if event_time is not None:
            hour, minute = [int(item) for item in event_time.split(":")]
            parsed_time = time(hour=hour, minute=minute)
        else:
            parsed_time = None

        if human_event_time is not None:
            hour, minute = [int(item) for item in human_event_time.split(":")]
            parsed_human_time = time(hour=hour, minute=minute)
        else:
            parsed_human_time = None

        row = TenderEvent(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"{tender_id}|{source_document_id}|{event_type}|{event_date}|{event_time}|{created_at}".encode("utf-8")).hexdigest(),
            event_type=event_type,
            title=event_type,
            event_date=event_date,
            event_time=parsed_time,
            date_precision="DAY" if event_date else "UNKNOWN",
            timezone="America/Mexico_City",
            review_status=review_status,
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.2",
            source_document_id=source_document_id,
            source_page=1,
            source_excerpt=event_type,
            human_event_date=human_event_date,
            human_event_time=parsed_human_time,
            human_date_precision="DAY" if human_event_date else None,
        )
        if created_at is not None:
            row.created_at = created_at
            row.updated_at = created_at
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _analyze_changes(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-changes")
    assert response.status_code == 200, response.text
    return response.json()


def _patch_change(tender_id: str, change_id: str, payload: dict) -> dict:
    response = client.patch(f"/tenders/{tender_id}/changes/{change_id}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _get_effective_state(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/effective-state")
    assert response.status_code == 200, response.text
    return response.json()


def _scope_for_target(payload: dict, target_document_id: str, locator: str | None = None) -> dict:
    normalized = (locator or "").lower()
    for scope in payload["scopes"]:
        if scope["target_document_id"] != target_document_id:
            continue
        if (scope["normalized_locator"] or "") == normalized:
            return scope
    raise AssertionError("scope not found")


def _scope_unresolved(payload: dict, reference_key: str) -> dict:
    for scope in payload["scopes"]:
        if scope["resolution_status"] == "UNRESOLVED_TARGET" and scope["target_reference_key"] == reference_key:
            return scope
    raise AssertionError("unresolved scope not found")


def _setup_single_confirmed_modifies(title: str) -> tuple[str, str, str]:
    tender_id = _create_tender(title)
    source = _import_pdf(tender_id, "junta-1.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")

    changes = _analyze_changes(tender_id)
    change_id = changes["changes"][0]["id"]
    _patch_change(tender_id, change_id, {"action": "CONFIRM"})
    return tender_id, source, target


def test_case_1_single_confirmed_mutation_is_determined() -> None:
    tender_id, _, target = _setup_single_confirmed_modifies("EFF CASE1")
    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["resolution_status"] == "DETERMINED"
    assert scope["effective_mutation"]["change_type"] == "MODIFIES"
    assert scope["effective_mutation"]["before_text"] == "30 dias naturales"
    assert scope["effective_mutation"]["after_text"] == "45 dias naturales"


def test_case_2_later_confirmed_publication_wins() -> None:
    tender_id = _create_tender("EFF CASE2")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")

    _seed_page(target, 1, "target")
    page_a = _seed_page(source_a, 1, "a")
    page_b = _seed_page(source_b, 1, "b")

    _seed_normalized(page_a, "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")
    _seed_normalized(page_b, "Se modifica el Anexo D en el numeral 12, de 45 dias naturales a 40 dias naturales.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(
        tender_id,
        source_a,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 27),
    )
    _seed_event(
        tender_id,
        source_b,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 9, 2),
    )

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "DETERMINED"
    assert scope["effective_mutation"]["source_document_id"] == source_b
    assert scope["effective_mutation"]["after_text"] == "40 dias naturales"


def test_case_3_competing_confirmed_without_reliable_chronology_is_ambiguous() -> None:
    tender_id = _create_tender("EFF CASE3")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")

    _seed_page(target, 1, "target")
    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 dias naturales a 40 dias naturales.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"
    assert scope["effective_mutation"] is None


def test_case_4_confirmed_plus_suggested_keeps_confirmed_and_marks_pending_review() -> None:
    tender_id = _create_tender("EFF CASE4")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")

    _seed_page(target, 1, "target")
    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 dias naturales a 40 dias naturales.")

    changes = _analyze_changes(tender_id)
    confirmed_row = next(item for item in changes["changes"] if item["source_document_id"] == source_a)
    _patch_change(tender_id, confirmed_row["id"], {"action": "CONFIRM"})

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["resolution_status"] == "PENDING_REVIEW"
    assert scope["effective_mutation"]["source_document_id"] == source_a
    assert len(scope["pending_changes"]) == 1


def test_suggested_only_scope_is_pending_review_with_no_authoritative_mutation() -> None:
    tender_id = _create_tender("EFF suggested only")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta.pdf")
    _seed_page(target, 1, "target")
    _seed_normalized(_seed_page(source, 1, "texto"), "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")

    _analyze_changes(tender_id)
    payload = _get_effective_state(tender_id)

    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "PENDING_REVIEW"
    assert scope["effective_mutation"] is None


def test_rejected_change_is_excluded_from_authoritative_effective_state() -> None:
    tender_id = _create_tender("EFF rejected")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta.pdf")
    _seed_page(target, 1, "target")
    _seed_normalized(_seed_page(source, 1, "texto"), "Se modifica el Anexo D en el numeral 12, de 30 dias naturales a 45 dias naturales.")

    changes = _analyze_changes(tender_id)
    _patch_change(tender_id, changes["changes"][0]["id"], {"action": "REJECT"})

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "NO_CONFIRMED_CHANGE"
    assert scope["effective_mutation"] is None


def test_unresolved_target_scope_is_explicit() -> None:
    tender_id = _create_tender("EFF unresolved target")
    source = _import_pdf(tender_id, "junta.pdf")
    _seed_normalized(_seed_page(source, 1, "texto"), "Se modifica el Anexo Z en el numeral 8, de 10 a 12.")

    changes = _analyze_changes(tender_id)
    _patch_change(tender_id, changes["changes"][0]["id"], {"action": "CONFIRM"})

    payload = _get_effective_state(tender_id)
    scope = _scope_unresolved(payload, "ANEXO:Z")
    assert scope["resolution_status"] == "UNRESOLVED_TARGET"


def test_two_locators_in_same_target_form_independent_scopes() -> None:
    tender_id = _create_tender("EFF two locators")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta.pdf")
    _seed_page(target, 1, "target")
    _seed_normalized(
        _seed_page(source, 1, "texto"),
        "Se modifica el Anexo D en el numeral 3.2, de 30 a 45. Se modifica el Anexo D en el numeral 5, de 11 a 12.",
    )

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    payload = _get_effective_state(tender_id)
    locators = sorted(scope["normalized_locator"] for scope in payload["scopes"])
    assert "numeral 3.2" in locators
    assert "numeral 5" in locators


def test_document_level_and_locator_level_changes_remain_separate() -> None:
    tender_id = _create_tender("EFF doc plus locator")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta.pdf")
    _seed_page(target, 1, "target")
    _seed_normalized(_seed_page(source, 1, "texto"), "Se modifica el Anexo D. Se corrige el Anexo D en el numeral 4.2.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    payload = _get_effective_state(tender_id)
    normalized_locators = sorted(scope["normalized_locator"] for scope in payload["scopes"])
    assert "" in normalized_locators
    assert "numeral 4.2" in normalized_locators


def test_same_day_without_distinct_time_is_ambiguous_precedence() -> None:
    tender_id = _create_tender("EFF same day tie")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, source_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 28))
    _seed_event(tender_id, source_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 28))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"


def test_same_day_with_distinct_times_picks_later_time() -> None:
    tender_id = _create_tender("EFF same day times")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, source_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 28), event_time="10:00")
    _seed_event(tender_id, source_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 28), event_time="15:00")

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "DETERMINED"
    assert scope["effective_mutation"]["source_document_id"] == source_b


def test_suggested_and_rejected_events_are_not_authoritative_for_precedence() -> None:
    tender_id = _create_tender("EFF non authoritative events")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, source_a, event_type="ADDENDUM_PUBLICATION", review_status="SUGGESTED", event_date=date(2026, 8, 27))
    _seed_event(tender_id, source_b, event_type="ADDENDUM_PUBLICATION", review_status="REJECTED", event_date=date(2026, 9, 2))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"


def test_human_overridden_confirmed_event_date_is_used_for_precedence() -> None:
    tender_id = _create_tender("EFF human event override")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(
        tender_id,
        source_a,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 20),
        human_event_date=date(2026, 9, 5),
    )
    _seed_event(tender_id, source_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 9, 2))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "DETERMINED"
    assert scope["effective_mutation"]["source_document_id"] == source_a


def test_unrelated_confirmed_event_type_is_not_used_for_precedence() -> None:
    tender_id = _create_tender("EFF unrelated event type")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, source_a, event_type="PROPOSAL_SUBMISSION_DEADLINE", review_status="CONFIRMED", event_date=date(2026, 8, 20))
    _seed_event(tender_id, source_b, event_type="PROPOSAL_SUBMISSION_DEADLINE", review_status="CONFIRMED", event_date=date(2026, 9, 2))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"


def test_conflicting_confirmed_eligible_events_same_source_mark_ambiguity() -> None:
    tender_id = _create_tender("EFF conflicting source events")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 1, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, source_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 20))
    _seed_event(tender_id, source_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 21))
    _seed_event(tender_id, source_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 22))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"


def test_replacement_chain_includes_modifies_replaces_corrects_removes_and_latest_can_be_removes() -> None:
    tender_id = _create_tender("EFF replacement chain")
    target = _import_pdf(tender_id, "anexo d.pdf")
    src1 = _import_pdf(tender_id, "junta-1.pdf")
    src2 = _import_pdf(tender_id, "junta-2.pdf")
    src3 = _import_pdf(tender_id, "junta-3.pdf")
    src4 = _import_pdf(tender_id, "junta-4.pdf")
    _seed_page(target, 1, "target")

    _seed_normalized(_seed_page(src1, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(src2, 1, "b"), "Se sustituye el Anexo D en el numeral 12.")
    _seed_normalized(_seed_page(src3, 1, "c"), "Se corrige el Anexo D en el numeral 12, de 45 a 44.")
    _seed_normalized(_seed_page(src4, 1, "d"), "Se elimina el numeral 12 del Anexo D.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, src1, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 20))
    _seed_event(tender_id, src2, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 22))
    _seed_event(tender_id, src3, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 25))
    _seed_event(tender_id, src4, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 28))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["resolution_status"] == "DETERMINED"
    assert scope["effective_mutation"]["change_type"] == "REMOVES"
    assert len(scope["confirmed_mutations"]) == 4


def test_non_replacing_assertions_do_not_supersede_confirmed_mutation_and_remain_visible() -> None:
    tender_id, src_mod, target = _setup_single_confirmed_modifies("EFF non replacing")
    src_clarify = _import_pdf(tender_id, "junta-aclara.pdf")
    src_add = _import_pdf(tender_id, "junta-agrega.pdf")
    src_confirm = _import_pdf(tender_id, "junta-confirma.pdf")

    _seed_normalized(_seed_page(src_clarify, 1, "a"), "Se aclara el Anexo D en el numeral 12.")
    _seed_normalized(_seed_page(src_add, 1, "b"), "Se adiciona una condicion al Anexo D en el numeral 12.")
    _seed_normalized(_seed_page(src_confirm, 1, "c"), "Se confirma el Anexo D en el numeral 12.")

    analyzed = _analyze_changes(tender_id)
    for row in analyzed["changes"]:
        if row["source_document_id"] in {src_clarify, src_add, src_confirm}:
            _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(tender_id, src_mod, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 20))

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["effective_mutation"]["change_type"] == "MODIFIES"
    non_replacing_types = {item["change_type"] for item in scope["confirmed_non_replacing_assertions"]}
    assert {"CLARIFIES", "ADDS", "CONFIRMS"}.issubset(non_replacing_types)


def test_pending_review_rule_with_confirmed_mutation_and_suggested_clarification() -> None:
    tender_id, _, target = _setup_single_confirmed_modifies("EFF pending rule")
    src = _import_pdf(tender_id, "junta-clari.pdf")
    _seed_normalized(_seed_page(src, 1, "a"), "Se aclara el Anexo D en el numeral 12.")

    _analyze_changes(tender_id)
    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["resolution_status"] == "PENDING_REVIEW"
    assert scope["effective_mutation"]["change_type"] == "MODIFIES"
    assert any(item["change_type"] == "CLARIFIES" for item in scope["pending_changes"])


def test_human_change_overrides_define_scope_and_display_values() -> None:
    tender_id = _create_tender("EFF human overrides")
    target_a = _import_pdf(tender_id, "anexo a.pdf")
    target_d = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta.pdf")

    _seed_page(target_a, 1, "target-a")
    _seed_page(target_d, 1, "target-d")
    _seed_normalized(_seed_page(source, 1, "texto"), "Se modifica el Anexo D en el numeral 3.2, de 30 a 45.")

    analyzed = _analyze_changes(tender_id)
    change_id = analyzed["changes"][0]["id"]

    _patch_change(
        tender_id,
        change_id,
        {
            "action": "OVERRIDE",
            "change_type": "CLARIFIES",
            "target_document_id": target_a,
            "target_locator_text": "Numeral 99.1",
            "before_text": "antes humano",
            "after_text": "despues humano",
            "human_note": "override",
        },
    )

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target_a, "numeral 99.1")

    assert scope["effective_mutation"] is None
    assert scope["resolution_status"] == "NO_CONFIRMED_CHANGE"
    assertion = scope["confirmed_non_replacing_assertions"][0]
    assert assertion["change_type"] == "CLARIFIES"
    assert assertion["before_text"] == "antes humano"
    assert assertion["after_text"] == "despues humano"


def test_non_current_confirmed_change_is_not_authoritative_automatic_input() -> None:
    tender_id = _create_tender("EFF non current source")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source = _import_pdf(tender_id, "junta-v1.pdf")

    _seed_page(target, 1, "target", is_current=True)
    _seed_normalized(_seed_page(source, 1, "texto", is_current=True), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")

    analyzed = _analyze_changes(tender_id)
    _patch_change(tender_id, analyzed["changes"][0]["id"], {"action": "CONFIRM"})

    db = SessionLocal()
    try:
        row = db.get(TenderDocument, source)
        assert row is not None
        row.is_current = False
        db.commit()
    finally:
        db.close()

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")

    assert scope["effective_mutation"] is None
    assert scope["resolution_status"] == "NO_CONFIRMED_CHANGE"
    assert len(scope["non_current_confirmed_changes"]) == 1


def test_no_system_metadata_based_precedence_is_inferred() -> None:
    tender_id = _create_tender("EFF no system precedence")
    target = _import_pdf(tender_id, "z-anexo d.pdf")
    source_a = _import_pdf(tender_id, "a-junta.pdf")
    source_b = _import_pdf(tender_id, "z-junta.pdf")
    _seed_page(target, 1, "target")

    old = datetime.now(timezone.utc) - timedelta(days=10)
    new = datetime.now(timezone.utc)

    _seed_normalized(_seed_page(source_a, 1, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, 2, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    _seed_event(
        tender_id,
        source_a,
        event_type="ADDENDUM_PUBLICATION",
        review_status="REJECTED",
        event_date=date(2026, 8, 20),
        created_at=old,
    )
    _seed_event(
        tender_id,
        source_b,
        event_type="ADDENDUM_PUBLICATION",
        review_status="SUGGESTED",
        event_date=date(2026, 9, 2),
        created_at=new,
    )

    payload = _get_effective_state(tender_id)
    scope = _scope_for_target(payload, target, "numeral 12")
    assert scope["resolution_status"] == "AMBIGUOUS_PRECEDENCE"
    assert scope["effective_mutation"] is None


def test_get_effective_state_does_not_mutate_closed_engines_or_relationship_baseline() -> None:
    tender_id = _create_tender("EFF regression")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 12, de 30 a 45. Junta de aclaraciones el 03/10/2026")

    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=source,
                suggested_type="NOTICE",
                suggested_score=80,
                classification_status="CONFIRMED",
                classifier_method="RULE_BASED_GENERIC",
                classifier_version="mvp-02.4.2",
                input_fingerprint_sha256="fp",
                is_composite=False,
                human_type="BIDDING_RULES",
            )
        )
        db.add(
            DocumentReferenceAnalysis(
                document_id=source,
                status="COMPLETED",
                extractor_version="mvp-02.5.1",
                input_fingerprint_sha256="fp-ref",
            )
        )
        db.commit()
    finally:
        db.close()

    baseline_before = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
    changes_before = _analyze_changes(tender_id)

    event_resp = client.post(f"/tenders/{tender_id}/analyze-events")
    assert event_resp.status_code == 200, event_resp.text

    db = SessionLocal()
    try:
        ref_analysis_id = db.execute(select(DocumentReferenceAnalysis.id).where(DocumentReferenceAnalysis.document_id == source)).scalar_one()
        db.add(
            DocumentReference(
                analysis_id=ref_analysis_id,
                source_document_id=source,
                document_page_id=page,
                reference_identity_key=hashlib.sha256(f"{tender_id}-ref".encode("utf-8")).hexdigest(),
                raw_reference_text="ANEXO D",
                normalized_reference_key="ANEXO:D",
                reference_kind="ANNEX",
                relationship_hint="REFERENCES",
                resolution_status="HUMAN_RESOLVED",
                resolved_target_document_id=target,
                human_target_document_id=target,
                human_decision="RESOLVE_TO_DOCUMENT",
                source_scope="NATIVE_PAGE",
                source_type="NATIVE_PDF",
                excerpt="ref",
                extractor_version="mvp-02.5.1",
            )
        )
        db.commit()
    finally:
        db.close()

    before_counts = {
        "changes": client.get(f"/tenders/{tender_id}/changes").json(),
        "events": client.get(f"/tenders/{tender_id}/events").json(),
    }

    _get_effective_state(tender_id)

    after_counts = {
        "changes": client.get(f"/tenders/{tender_id}/changes").json(),
        "events": client.get(f"/tenders/{tender_id}/events").json(),
    }
    baseline_after = client.get(f"/tenders/{tender_id}/relationship-baseline").json()

    assert before_counts["changes"]["counts"] == after_counts["changes"]["counts"]
    assert before_counts["changes"]["changes"] == after_counts["changes"]["changes"]
    assert before_counts["events"]["counts"] == after_counts["events"]["counts"]
    assert before_counts["events"]["events"] == after_counts["events"]["events"]
    assert baseline_before["relationship_type_counts"] == baseline_after["relationship_type_counts"]
    assert baseline_after["counts"]["duplicate_edge_count"] == 0
    assert baseline_after["counts"]["self_edge_count"] == 0

    db = SessionLocal()
    try:
        classification_status = db.execute(
            select(DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source)
        ).one()
        references_count = db.execute(select(func.count()).select_from(DocumentReference).where(DocumentReference.source_document_id == source)).scalar_one()
        relationship_count = db.execute(select(func.count()).select_from(DocumentRelationship).where(DocumentRelationship.tender_id == tender_id)).scalar_one()
        change_count = db.execute(select(func.count()).select_from(TenderChange).where(TenderChange.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    assert classification_status[0] == "CONFIRMED"
    assert classification_status[1] == "BIDDING_RULES"
    assert references_count >= 1
    assert relationship_count >= 0
    assert change_count == changes_before["counts"]["total_changes"]
