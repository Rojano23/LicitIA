from __future__ import annotations

import hashlib

import app.main as main_module
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, DocumentPageStructureResolution, TenderDocument, TenderItem, TenderScopeSegment


client = TestClient(app)


def _create_tender(title: str, external_reference: str) -> str:
    response = client.post(
        "/tenders",
        json={"title": title, "institution_profile": "General", "external_reference": external_reference},
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


def _seed_page(document_id: str, page_number: int, text: str = "PARTIDA") -> str:
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
        db.flush()

        document = db.get(TenderDocument, document_id)
        assert document is not None
        document.page_count = max(document.page_count, page_number)
        document.processing_status = "TEXT_EXTRACTION_COMPLETE"
        db.commit()
        return page.id
    finally:
        db.close()


def _insert_resolution(
    document_id: str,
    document_page_id: str,
    page_number: int,
    *,
    status: str,
    selected_source_method: str | None,
    review_required: bool,
    reason: str | None,
) -> None:
    db = SessionLocal()
    try:
        resolution = DocumentPageStructureResolution(
            source_document_id=document_id,
            document_page_id=document_page_id,
            page_number=page_number,
            status=status,
            selected_source_method=selected_source_method,
            review_required=review_required,
            reason=reason,
            resolver_version="page-structure-resolver-005",
            input_fingerprint_sha256=hashlib.sha256(f"{document_id}|{page_number}|{status}".encode("utf-8")).hexdigest(),
        )
        db.add(resolution)
        db.commit()
    finally:
        db.close()


def _insert_tender_item(tender_id: str, document_id: str, document_page_id: str, item_number: str, fingerprint: str) -> str:
    db = SessionLocal()
    try:
        row = TenderItem(
            tender_id=tender_id,
            source_document_id=document_id,
            source_page=1,
            document_page_id=document_page_id,
            normalized_content_id=None,
            item_number=item_number,
            parent_item_number=None,
            raw_description=f"Partida {item_number}",
            quantity=None,
            unit=None,
            source_excerpt=f"PARTIDA {item_number}",
            source_locator="page:1|segment:0",
            extraction_confidence=1.0,
            extraction_status="DETERMINED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-06.1",
            semantic_fingerprint=fingerprint,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _insert_scope_segment(
    *,
    tender_id: str,
    document_id: str,
    document_page_id: str,
    page_number: int,
    sequence_index: int,
    tender_item_id: str | None,
    candidate_item_key: str | None,
    candidate_item_raw_label: str | None,
    source_method: str = "VISION",
    link_reason: str = "EXPLICIT_ITEM_START",
    source_locator: str = "page:1|segment:0",
    source_excerpt: str = "PARTIDA",
    review_required: bool = False,
) -> None:
    db = SessionLocal()
    try:
        row = TenderScopeSegment(
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=document_page_id,
            page_number=page_number,
            tender_item_id=tender_item_id,
            candidate_item_key=candidate_item_key,
            candidate_item_raw_label=candidate_item_raw_label,
            sequence_index=sequence_index,
            scope_domain=None,
            source_method=source_method,
            link_reason=link_reason,
            source_locator=source_locator,
            source_excerpt=source_excerpt,
            source_analysis_id=None,
            source_page_result_id=None,
            confidence=None,
            review_required=review_required,
            semantic_fingerprint=hashlib.sha256(
                f"{tender_id}|{document_id}|{page_number}|{sequence_index}|{candidate_item_key}|{tender_item_id}|{source_locator}|{source_excerpt}".encode("utf-8")
            ).hexdigest(),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def test_scope_summary_missing_orchestration_state() -> None:
    tender_id = _create_tender("scope summary empty", "SCOPE-SUM-001")
    document_id = _import_pdf(tender_id, "scope-summary-empty.pdf")

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary_state"] == "NO_ORCHESTRATION"
    assert payload["summary"]["document_page_count"] == 0
    assert payload["summary"]["structurally_analyzed_count"] == 0
    assert payload["page_resolutions"] == []
    assert payload["ownership_groups"] == []


def test_scope_summary_candidate_only_group_and_provenance_fields() -> None:
    tender_id = _create_tender("scope summary candidate", "SCOPE-SUM-002")
    document_id = _import_pdf(tender_id, "scope-summary-candidate.pdf")
    page_id = _seed_page(document_id, 1, "PARTIDA 01")
    _insert_resolution(
        document_id,
        page_id,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_id,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="01.",
        source_method="VISION",
        link_reason="EXPLICIT_ITEM_START",
        source_locator="page:1|segment:0",
        source_excerpt="PARTIDA 01",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["segments_count"] == 1
    assert len(payload["ownership_groups"]) == 1
    group = payload["ownership_groups"][0]
    assert group["group_key"] == "candidate:1"
    assert group["candidate_item_key"] == "1"
    assert group["candidate_item_raw_label"] == "01."
    assert group["canonical_items"] == []

    segment = group["segments"][0]
    assert segment["page_number"] == 1
    assert segment["sequence_index"] == 0
    assert segment["link_reason"] == "EXPLICIT_ITEM_START"
    assert segment["source_method"] == "VISION"
    assert segment["source_locator"] == "page:1|segment:0"
    assert segment["source_excerpt"] == "PARTIDA 01"


def test_scope_summary_canonical_fallback_when_candidate_key_is_missing() -> None:
    tender_id = _create_tender("scope summary canonical fallback", "SCOPE-SUM-003")
    document_id = _import_pdf(tender_id, "scope-summary-canonical-fallback.pdf")
    page_id = _seed_page(document_id, 1, "PARTIDA X")
    _insert_resolution(
        document_id,
        page_id,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason=None,
    )
    tender_item_id = _insert_tender_item(tender_id, document_id, page_id, "1", "scope-summary-canonical-fallback-item")
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_id,
        page_number=1,
        sequence_index=0,
        tender_item_id=tender_item_id,
        candidate_item_key=None,
        candidate_item_raw_label="01.",
        source_method="NATIVE_TEXT",
        link_reason="EXPLICIT_ITEM_START",
        source_locator="page:1|segment:0",
        source_excerpt="PARTIDA X",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["ownership_groups"]) == 1
    group = payload["ownership_groups"][0]
    assert group["group_key"] == f"canonical:{tender_item_id}"
    assert group["candidate_item_key"] is None
    assert group["candidate_item_raw_label"] == "01."
    assert len(group["canonical_items"]) == 1
    assert group["canonical_items"][0]["tender_item_id"] == tender_item_id


def test_scope_summary_raw_label_is_not_identity_for_canonical_groups() -> None:
    tender_id = _create_tender("scope summary raw label non identity", "SCOPE-SUM-004")
    document_id = _import_pdf(tender_id, "scope-summary-raw-label-non-identity.pdf")
    page_id = _seed_page(document_id, 1, "PARTIDA")
    _insert_resolution(
        document_id,
        page_id,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )
    item_a = _insert_tender_item(tender_id, document_id, page_id, "1", "scope-summary-item-a")
    item_b = _insert_tender_item(tender_id, document_id, page_id, "2", "scope-summary-item-b")

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_id,
        page_number=1,
        sequence_index=0,
        tender_item_id=item_a,
        candidate_item_key=None,
        candidate_item_raw_label="MISMATCHED-LABEL",
        source_excerpt="A",
        source_locator="page:1|segment:0",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_id,
        page_number=1,
        sequence_index=1,
        tender_item_id=item_b,
        candidate_item_key=None,
        candidate_item_raw_label="MISMATCHED-LABEL",
        source_excerpt="B",
        source_locator="page:1|segment:1",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    keys = sorted(group["group_key"] for group in payload["ownership_groups"])
    assert set(keys) == {f"canonical:{item_a}", f"canonical:{item_b}"}


def test_scope_summary_all_physical_pages_are_returned_with_has_resolution() -> None:
    tender_id = _create_tender("scope summary all pages", "SCOPE-SUM-005")
    document_id = _import_pdf(tender_id, "scope-summary-all-pages.pdf")
    page_one = _seed_page(document_id, 1, "PARTIDA 1")
    _seed_page(document_id, 2, "PARTIDA 2")
    _seed_page(document_id, 3, "PARTIDA 3")
    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason=None,
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    rows = payload["page_resolutions"]
    assert [row["page_number"] for row in rows] == [1, 2, 3]
    assert rows[0]["has_resolution"] is True
    assert rows[1]["has_resolution"] is False
    assert rows[1]["status"] is None
    assert rows[1]["selected_source_method"] is None
    assert rows[1]["review_required"] is False
    assert rows[1]["reason"] is None


def test_scope_summary_counter_semantics_and_ready_derivation() -> None:
    tender_id = _create_tender("scope summary counters", "SCOPE-SUM-006")
    document_id = _import_pdf(tender_id, "scope-summary-counters.pdf")
    page_one = _seed_page(document_id, 1, "PAGE 1")
    page_two = _seed_page(document_id, 2, "PAGE 2")
    page_three = _seed_page(document_id, 3, "PAGE 3")
    page_four = _seed_page(document_id, 4, "PAGE 4")

    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason=None,
    )
    _insert_resolution(
        document_id,
        page_two,
        2,
        status="NEEDS_OCR",
        selected_source_method=None,
        review_required=False,
        reason="NATIVE_NO_EXPLICIT_ITEM_START",
    )
    _insert_resolution(
        document_id,
        page_three,
        3,
        status="NEEDS_VISION",
        selected_source_method=None,
        review_required=False,
        reason="NO_VALID_STRUCTURE",
    )
    _insert_resolution(
        document_id,
        page_four,
        4,
        status="REVIEW_REQUIRED",
        selected_source_method="VISION",
        review_required=True,
        reason="CONFLICTING_VALID_STRUCTURES",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    summary = payload["summary"]
    assert summary["document_page_count"] == 4
    assert summary["structurally_analyzed_count"] == 4
    assert summary["resolved_count"] == 1
    assert summary["needs_ocr_count"] == 1
    assert summary["needs_vision_count"] == 1
    assert summary["review_required_count"] == 1
    assert summary["not_analyzed_count"] == 0
    assert payload["summary_state"] == "REVIEW_REQUIRED"


def test_scope_summary_ready_is_impossible_with_missing_resolution_pages() -> None:
    tender_id = _create_tender("scope summary not ready", "SCOPE-SUM-007")
    document_id = _import_pdf(tender_id, "scope-summary-not-ready.pdf")
    page_one = _seed_page(document_id, 1, "PAGE 1")
    _seed_page(document_id, 2, "PAGE 2")

    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason=None,
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["document_page_count"] == 2
    assert payload["summary"]["structurally_analyzed_count"] == 1
    assert payload["summary"]["not_analyzed_count"] == 1
    assert payload["summary_state"] == "REVIEW_REQUIRED"


def test_scope_summary_unresolved_zero_scope_pages_remain_visible() -> None:
    tender_id = _create_tender("scope summary unresolved visible", "SCOPE-SUM-008")
    document_id = _import_pdf(tender_id, "scope-summary-unresolved-visible.pdf")
    page_review = _seed_page(document_id, 1, "R")
    page_vision = _seed_page(document_id, 2, "V")

    _insert_resolution(
        document_id,
        page_review,
        1,
        status="REVIEW_REQUIRED",
        selected_source_method=None,
        review_required=True,
        reason="CONFLICTING_VALID_STRUCTURES",
    )
    _insert_resolution(
        document_id,
        page_vision,
        2,
        status="NEEDS_VISION",
        selected_source_method=None,
        review_required=False,
        reason="NO_VALID_STRUCTURE",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    page_map = {row["page_number"]: row for row in payload["page_resolutions"]}
    assert page_map[1]["scope_segment_count"] == 0
    assert page_map[1]["status"] == "REVIEW_REQUIRED"
    assert page_map[2]["scope_segment_count"] == 0
    assert page_map[2]["status"] == "NEEDS_VISION"


def test_scope_summary_group_and_segment_ordering_with_shared_page_segments() -> None:
    tender_id = _create_tender("scope summary ordering", "SCOPE-SUM-009")
    document_id = _import_pdf(tender_id, "scope-summary-ordering.pdf")
    page_one = _seed_page(document_id, 1, "P1")
    page_two = _seed_page(document_id, 2, "P2")

    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )
    _insert_resolution(
        document_id,
        page_two,
        2,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_one,
        page_number=1,
        sequence_index=1,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        source_excerpt="P1 S1 item2",
        source_locator="page:1|segment:1",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_one,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        source_excerpt="P1 S0 item1",
        source_locator="page:1|segment:0",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_two,
        page_number=2,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        source_excerpt="P2 S0 item2",
        source_locator="page:2|segment:0",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [group["candidate_item_key"] for group in payload["ownership_groups"]] == ["1", "2"]

    group_two = next(group for group in payload["ownership_groups"] if group["candidate_item_key"] == "2")
    assert [segment["page_number"] for segment in group_two["segments"]] == [1, 2]
    assert [segment["sequence_index"] for segment in group_two["segments"]] == [1, 0]


def test_scope_summary_multi_document_isolation() -> None:
    tender_id = _create_tender("scope summary multi doc", "SCOPE-SUM-010")
    doc_a = _import_pdf(tender_id, "scope-summary-a.pdf")
    doc_b = _import_pdf(tender_id, "scope-summary-b.pdf")
    page_a = _seed_page(doc_a, 1, "PARTIDA 1")
    page_b = _seed_page(doc_b, 1, "PARTIDA 2")

    _insert_resolution(
        doc_a,
        page_a,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )
    _insert_resolution(
        doc_b,
        page_b,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=doc_a,
        document_page_id=page_a,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        source_excerpt="DOC A",
        source_locator="page:1|segment:0",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=doc_b,
        document_page_id=page_b,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        source_excerpt="DOC B",
        source_locator="page:1|segment:0",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{doc_a}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["document_id"] == doc_a
    assert payload["summary"]["segments_count"] == 1
    assert len(payload["ownership_groups"]) == 1
    assert payload["ownership_groups"][0]["candidate_item_key"] == "1"
    assert payload["ownership_groups"][0]["segments"][0]["source_excerpt"] == "DOC A"


def test_scope_summary_404_when_document_does_not_belong_to_tender() -> None:
    tender_a = _create_tender("scope summary tender a", "SCOPE-SUM-011A")
    tender_b = _create_tender("scope summary tender b", "SCOPE-SUM-011B")
    document_b = _import_pdf(tender_b, "scope-summary-foreign.pdf")

    response = client.get(f"/tenders/{tender_a}/documents/{document_b}/scope-summary")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tender document not found"


def test_scope_summary_get_has_no_provider_or_orchestrator_side_effects(monkeypatch) -> None:
    tender_id = _create_tender("scope summary read only", "SCOPE-SUM-012")
    document_id = _import_pdf(tender_id, "scope-summary-readonly.pdf")
    page_id = _seed_page(document_id, 1, "PARTIDA")
    _insert_resolution(
        document_id,
        page_id,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason=None,
    )

    def _fail(*_args, **_kwargs):
        raise AssertionError("provider/orchestrator entrypoint should not be called by GET scope-summary")

    monkeypatch.setattr(main_module, "analyze_vision_document", _fail)
    monkeypatch.setattr(main_module, "analyze_tender_document_items", _fail)
    monkeypatch.setattr(main_module, "process_document_normalization", _fail)

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["document_page_count"] == 1
    assert payload["summary"]["structurally_analyzed_count"] == 1


def test_scope_summary_scoped_segment_count_matches_read_model() -> None:
    tender_id = _create_tender("scope summary segment count", "SCOPE-SUM-013")
    document_id = _import_pdf(tender_id, "scope-summary-segment-count.pdf")
    page_one = _seed_page(document_id, 1, "PARTIDA 1")
    page_two = _seed_page(document_id, 2, "PARTIDA 2")

    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )
    _insert_resolution(
        document_id,
        page_two,
        2,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason=None,
    )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_one,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        source_excerpt="X",
        source_locator="page:1|segment:0",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_two,
        page_number=2,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        source_excerpt="Y",
        source_locator="page:2|segment:0",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["groups_count"] == 2
    assert payload["summary"]["segments_count"] == 2
    rows = payload["page_resolutions"]
    by_page = {row["page_number"]: row for row in rows}
    assert by_page[1]["scope_segment_count"] == 1
    assert by_page[2]["scope_segment_count"] == 1


def test_scope_summary_segment_review_blocks_ready_and_marks_page_review() -> None:
    tender_id = _create_tender("scope summary segment review safety", "SCOPE-SUM-014")
    document_id = _import_pdf(tender_id, "scope-summary-segment-review-safety.pdf")

    page_ids = [
        _seed_page(document_id, 1, "P1"),
        _seed_page(document_id, 2, "P2"),
        _seed_page(document_id, 3, "P3"),
        _seed_page(document_id, 4, "P4"),
    ]

    for page_number, page_id in enumerate(page_ids, start=1):
        _insert_resolution(
            document_id,
            page_id,
            page_number,
            status="RESOLVED",
            selected_source_method="VISION",
            review_required=False,
            reason="CONSISTENT_VALID_CANDIDATE",
        )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_ids[0],
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        link_reason="EXPLICIT_ITEM_START",
        review_required=False,
        source_locator="page:1|segment:0",
        source_excerpt="P1 item1",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_ids[1],
        page_number=2,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        link_reason="CONTINUATION",
        review_required=False,
        source_locator="page:2|segment:0",
        source_excerpt="P2 item1",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_ids[2],
        page_number=3,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        link_reason="CONTINUATION",
        review_required=True,
        source_locator="page:3|segment:0",
        source_excerpt="P3 item2",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_ids[3],
        page_number=4,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        link_reason="CONTINUATION",
        review_required=False,
        source_locator="page:4|segment:0",
        source_excerpt="P4 item2",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary_state"] == "REVIEW_REQUIRED"
    assert payload["summary"]["review_required_count"] == 1
    page_map = {row["page_number"]: row for row in payload["page_resolutions"]}
    assert page_map[3]["review_required"] is True
    assert page_map[1]["review_required"] is False
    assert page_map[2]["review_required"] is False
    assert page_map[4]["review_required"] is False


def test_scope_summary_review_required_count_is_unique_per_page() -> None:
    tender_id = _create_tender("scope summary review unique page", "SCOPE-SUM-015")
    document_id = _import_pdf(tender_id, "scope-summary-review-unique-page.pdf")

    page_ids = [
        _seed_page(document_id, 1, "P1"),
        _seed_page(document_id, 2, "P2"),
        _seed_page(document_id, 3, "P3"),
    ]

    _insert_resolution(
        document_id,
        page_ids[0],
        1,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason="CONSISTENT_VALID_CANDIDATE",
    )
    _insert_resolution(
        document_id,
        page_ids[1],
        2,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=True,
        reason="DOCUMENT_CONTINUITY_CONFLICT",
    )
    _insert_resolution(
        document_id,
        page_ids[2],
        3,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason="CONSISTENT_VALID_CANDIDATE",
    )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_ids[1],
        page_number=2,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="2",
        candidate_item_raw_label="2",
        link_reason="CONTINUATION",
        review_required=True,
        source_locator="page:2|segment:0",
        source_excerpt="P2 item2",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary_state"] == "REVIEW_REQUIRED"
    assert payload["summary"]["review_required_count"] == 1


def test_scope_summary_ready_requires_no_page_or_segment_review() -> None:
    tender_id = _create_tender("scope summary ready guard", "SCOPE-SUM-016")
    document_id = _import_pdf(tender_id, "scope-summary-ready-guard.pdf")

    page_one = _seed_page(document_id, 1, "P1")
    page_two = _seed_page(document_id, 2, "P2")

    _insert_resolution(
        document_id,
        page_one,
        1,
        status="RESOLVED",
        selected_source_method="NATIVE_TEXT",
        review_required=False,
        reason="CONSISTENT_VALID_CANDIDATE",
    )
    _insert_resolution(
        document_id,
        page_two,
        2,
        status="RESOLVED",
        selected_source_method="VISION",
        review_required=False,
        reason="CONSISTENT_VALID_CANDIDATE",
    )

    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_one,
        page_number=1,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        link_reason="EXPLICIT_ITEM_START",
        review_required=False,
        source_locator="page:1|segment:0",
        source_excerpt="P1",
    )
    _insert_scope_segment(
        tender_id=tender_id,
        document_id=document_id,
        document_page_id=page_two,
        page_number=2,
        sequence_index=0,
        tender_item_id=None,
        candidate_item_key="1",
        candidate_item_raw_label="1",
        link_reason="CONTINUATION",
        review_required=False,
        source_locator="page:2|segment:0",
        source_excerpt="P2",
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/scope-summary")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary_state"] == "READY"
    assert payload["summary"]["review_required_count"] == 0
