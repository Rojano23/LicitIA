from __future__ import annotations

import hashlib

import pytest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.item_identity import normalize_item_identity
from app.main import app
from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    TenderDocument,
    TenderItem,
    TenderScopeSegment,
)
from app.page_structure import (
    PAGE_STRUCTURE_SOURCE_METHOD_VISION,
    PAGE_STRUCTURE_VALID,
    PageStructuralProvenance,
    PageStructuralSegment,
    build_page_structural_state,
)
from app.scope_segments import persist_tender_scope_segments

from fastapi.testclient import TestClient


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


def _seed_page_and_normalized(document_id: str, page_number: int, text: str) -> tuple[str, str]:
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

        normalized = NormalizedContent(
            document_page_id=page.id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"{document_id}|{page_number}|NATIVE_PDF|{text}".encode("utf-8")).hexdigest(),
        )
        db.add(normalized)
        db.commit()
        return page.id, normalized.id
    finally:
        db.close()


def _seed_scope_vision_provenance(document_id: str, document_page_id: str, page_number: int) -> tuple[str, str]:
    db = SessionLocal()
    try:
        analysis_fingerprint = hashlib.sha256(f"{document_id}|{page_number}|scope-analysis".encode("utf-8")).hexdigest()
        analysis = db.scalar(
            select(DocumentVisionAnalysis).where(
                DocumentVisionAnalysis.document_id == document_id,
                DocumentVisionAnalysis.model_name == "scope-segment-test-model",
                DocumentVisionAnalysis.prompt_version == "scope-segment-test-prompt",
                DocumentVisionAnalysis.input_fingerprint_sha256 == analysis_fingerprint,
            )
        )
        if analysis is None:
            analysis = DocumentVisionAnalysis(
                tender_id=db.scalar(select(TenderDocument.tender_id).where(TenderDocument.id == document_id)),
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="scope-segment-test-model",
                prompt_version="scope-segment-test-prompt",
                input_fingerprint_sha256=analysis_fingerprint,
            )
            db.add(analysis)
            db.flush()

        image_sha256 = hashlib.sha256(f"{document_id}|{page_number}|scope-page-result".encode("utf-8")).hexdigest()
        page_result = db.scalar(
            select(DocumentVisionPageResult).where(
                DocumentVisionPageResult.analysis_id == analysis.id,
                DocumentVisionPageResult.document_page_id == document_page_id,
                DocumentVisionPageResult.image_sha256 == image_sha256,
            )
        )
        if page_result is None:
            page_result = DocumentVisionPageResult(
                analysis_id=analysis.id,
                document_page_id=document_page_id,
                page_number=page_number,
                image_sha256=image_sha256,
                status="COMPLETED",
            )
            db.add(page_result)
            db.flush()

        db.commit()
        return analysis.id, page_result.id
    finally:
        db.close()


def _page_state(page_number: int, segments: list[PageStructuralSegment], incoming_item_key: str | None, outgoing_item_key: str | None, review_required: bool = False) -> object:
    return build_page_structural_state(
        page_number=page_number,
        segments=segments,
        state_quality=PAGE_STRUCTURE_VALID,
        review_required=review_required,
        provenance=PageStructuralProvenance(source_method=PAGE_STRUCTURE_SOURCE_METHOD_VISION, source_analysis_id="analysis-1", source_page_result_id="page-result-1", source_contract_version="VISION_STRUCTURE_SCOPE_005"),
        incoming_item_key=incoming_item_key,
        outgoing_item_key=outgoing_item_key,
    )


def _persist_for_document(tender_id: str, document_id: str, page_number: int, state) -> list[TenderScopeSegment]:
    db = SessionLocal()
    try:
        document_page_id = db.scalar(select(DocumentPage.id).where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number))
        assert document_page_id is not None
        source_analysis_id, source_page_result_id = _seed_scope_vision_provenance(document_id, document_page_id, page_number)
        tender_item_id_by_candidate_key = {
            row[0]: row[1]
            for row in db.execute(
                select(TenderItem.item_number, TenderItem.id).where(TenderItem.tender_id == tender_id)
            ).all()
            if row[0] is not None
        }
        rows = persist_tender_scope_segments(
            db,
            tender_id=tender_id,
            page_state=state,
            source_document_id=document_id,
            document_page_id=document_page_id,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            tender_item_id_by_candidate_key=tender_item_id_by_candidate_key,
        )
        db.commit()
        for row in rows:
            db.refresh(row)
            db.expunge(row)
        return rows
    finally:
        db.close()


def test_candidate_only_scope_segment_can_persist_without_canonical_item() -> None:
    tender_id = _create_tender("scope candidate only", "SCOPE-001")
    document_id = _import_pdf(tender_id, "scope-candidate-only.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 01\nCONTENIDO")

    state = _page_state(
        1,
        [
            PageStructuralSegment(
                item_identity=normalize_item_identity("01."),
                starts_on_this_page=True,
                sequence=0,
                anchor_raw_text="PARTIDA 01",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=False,
            )
        ],
        incoming_item_key=None,
        outgoing_item_key="1",
    )

    rows = _persist_for_document(tender_id, document_id, 1, state)

    assert len(rows) == 1
    assert rows[0].tender_item_id is None
    assert rows[0].candidate_item_key == "1"
    assert rows[0].candidate_item_raw_label == "01."


def test_ownerless_scope_segment_is_rejected_by_database_constraint() -> None:
    tender_id = _create_tender("scope ownerless invalid", "SCOPE-001B")
    document_id = _import_pdf(tender_id, "scope-ownerless-invalid.pdf")
    page_id, _ = _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nCONTENIDO")

    db = SessionLocal()
    try:
        row = TenderScopeSegment(
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page_id,
            page_number=1,
            tender_item_id=None,
            candidate_item_key=None,
            candidate_item_raw_label=None,
            sequence_index=0,
            scope_domain=None,
            source_method="VISION",
            link_reason="EXPLICIT_ITEM_START",
            source_locator="page:1|segment:0",
            source_excerpt="PARTIDA 1",
            source_analysis_id=None,
            source_page_result_id=None,
            confidence=None,
            review_required=False,
            semantic_fingerprint="ownerless-invalid-fingerprint",
        )
        db.add(row)

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()
        persisted = db.scalar(
            select(TenderScopeSegment).where(
                TenderScopeSegment.tender_id == tender_id,
                TenderScopeSegment.source_document_id == document_id,
                TenderScopeSegment.semantic_fingerprint == "ownerless-invalid-fingerprint",
            )
        )
        assert persisted is None
    finally:
        db.close()


def test_canonical_tender_item_linked_segment_can_persist() -> None:
    tender_id = _create_tender("scope canonical", "SCOPE-002")
    document_id = _import_pdf(tender_id, "scope-canonical.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nServicio\nCantidad: 1\nUnidad: SERVICIO")

    db = SessionLocal()
    try:
        document_page_id = db.scalar(select(DocumentPage.id).where(DocumentPage.document_id == document_id, DocumentPage.page_number == 1))
        assert document_page_id is not None
        tender_item = TenderItem(
            tender_id=tender_id,
            source_document_id=document_id,
            source_page=1,
            document_page_id=document_page_id,
            normalized_content_id=None,
            item_number="1",
            parent_item_number=None,
            raw_description="Servicio",
            quantity=None,
            unit=None,
            source_excerpt="PARTIDA 1",
            source_locator="page:1|segment:0",
            extraction_confidence=1.0,
            extraction_status="DETERMINED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-06.1",
            semantic_fingerprint="fingerprint-1",
        )
        db.add(tender_item)
        db.flush()

        state = _page_state(
            1,
            [
                PageStructuralSegment(
                    item_identity=normalize_item_identity("1"),
                    starts_on_this_page=True,
                    sequence=0,
                    anchor_raw_text="PARTIDA 1",
                    has_service=True,
                    has_supply=False,
                    has_deliverable=False,
                    review_required=False,
                )
            ],
            incoming_item_key=None,
            outgoing_item_key="1",
        )
        source_analysis_id, source_page_result_id = _seed_scope_vision_provenance(document_id, document_page_id, 1)
        rows = persist_tender_scope_segments(
            db,
            tender_id=tender_id,
            page_state=state,
            source_document_id=document_id,
            document_page_id=document_page_id,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            tender_item_id_by_candidate_key={"1": tender_item.id},
        )
        db.commit()
        for row in rows:
            db.refresh(row)
            db.expunge(row)
    finally:
        db.close()

    assert len(rows) == 1
    assert rows[0].tender_item_id is not None
    assert rows[0].candidate_item_key == "1"
    assert rows[0].candidate_item_raw_label == "1"


def test_shared_page_can_persist_two_ordered_segments() -> None:
    tender_id = _create_tender("scope shared", "SCOPE-003")
    document_id = _import_pdf(tender_id, "scope-shared.pdf")
    _seed_page_and_normalized(document_id, 2, "CONTINUA 1\nPARTIDA 2")

    state = _page_state(
        2,
        [
            PageStructuralSegment(
                item_identity=normalize_item_identity("1"),
                starts_on_this_page=False,
                sequence=0,
                anchor_raw_text="CONTINUA PARTIDA 1",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=False,
            ),
            PageStructuralSegment(
                item_identity=normalize_item_identity("2"),
                starts_on_this_page=True,
                sequence=1,
                anchor_raw_text="PARTIDA 2",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=False,
            ),
        ],
        incoming_item_key="1",
        outgoing_item_key="2",
    )

    rows = _persist_for_document(tender_id, document_id, 2, state)

    assert [row.sequence_index for row in rows] == [0, 1]
    assert [row.candidate_item_key for row in rows] == ["1", "2"]


def test_scope_segment_rerun_does_not_create_duplicates() -> None:
    tender_id = _create_tender("scope idempotent", "SCOPE-004")
    document_id = _import_pdf(tender_id, "scope-idempotent.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nContenido")

    state = _page_state(
        1,
        [
            PageStructuralSegment(
                item_identity=normalize_item_identity("1"),
                starts_on_this_page=True,
                sequence=0,
                anchor_raw_text="PARTIDA 1",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=False,
            )
        ],
        incoming_item_key=None,
        outgoing_item_key="1",
    )

    first = _persist_for_document(tender_id, document_id, 1, state)
    second = _persist_for_document(tender_id, document_id, 1, state)

    assert len(first) == 1
    assert len(second) == 1


def test_same_candidate_identity_can_be_persisted_across_multiple_documents() -> None:
    tender_id = _create_tender("scope multi-doc", "SCOPE-005")
    doc_a = _import_pdf(tender_id, "scope-a.pdf")
    doc_b = _import_pdf(tender_id, "scope-b.pdf")
    _seed_page_and_normalized(doc_a, 1, "PARTIDA 1\nDocumento A")
    _seed_page_and_normalized(doc_b, 1, "PARTIDA 1\nDocumento B")

    state = _page_state(
        1,
        [
            PageStructuralSegment(
                item_identity=normalize_item_identity("1"),
                starts_on_this_page=True,
                sequence=0,
                anchor_raw_text="PARTIDA 1",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=False,
            )
        ],
        incoming_item_key=None,
        outgoing_item_key="1",
    )

    rows_a = _persist_for_document(tender_id, doc_a, 1, state)
    rows_b = _persist_for_document(tender_id, doc_b, 1, state)

    assert rows_a[0].candidate_item_key == "1"
    assert rows_b[0].candidate_item_key == "1"
    assert rows_a[0].source_document_id != rows_b[0].source_document_id


def test_scope_provenance_and_review_required_survive_readback() -> None:
    tender_id = _create_tender("scope provenance", "SCOPE-006")
    document_id = _import_pdf(tender_id, "scope-provenance.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nContenido")

    state = build_page_structural_state(
        page_number=1,
        segments=[
            PageStructuralSegment(
                item_identity=normalize_item_identity("1"),
                starts_on_this_page=True,
                sequence=0,
                anchor_raw_text="PARTIDA 1",
                has_service=True,
                has_supply=False,
                has_deliverable=False,
                review_required=True,
            )
        ],
        state_quality=PAGE_STRUCTURE_VALID,
        review_required=True,
        provenance=PageStructuralProvenance(
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_VISION,
            source_analysis_id="analysis-xyz",
            source_page_result_id="page-result-xyz",
            source_contract_version="VISION_STRUCTURE_SCOPE_005",
        ),
        incoming_item_key=None,
        outgoing_item_key="1",
    )

    rows = _persist_for_document(tender_id, document_id, 1, state)
    db = SessionLocal()
    try:
        persisted = db.get(TenderScopeSegment, rows[0].id)
        assert persisted is not None
        assert persisted.review_required is True
        assert persisted.source_method == PAGE_STRUCTURE_SOURCE_METHOD_VISION
        assert persisted.source_analysis_id is not None
        assert persisted.source_page_result_id is not None
        assert persisted.source_analysis is not None
        assert persisted.source_analysis.model_name == "scope-segment-test-model"
        assert persisted.source_page_result is not None
        assert persisted.source_page_result.page_number == 1
        assert persisted.source_locator == "page:1|segment:0"
        assert persisted.source_excerpt == "PARTIDA 1"
    finally:
        db.close()


def test_deleting_canonical_tender_item_does_not_erase_underlying_scope_segment() -> None:
    tender_id = _create_tender("scope delete safe", "SCOPE-007")
    document_id = _import_pdf(tender_id, "scope-delete-safe.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nServicio")

    db = SessionLocal()
    try:
        document_page_id = db.scalar(select(DocumentPage.id).where(DocumentPage.document_id == document_id, DocumentPage.page_number == 1))
        assert document_page_id is not None
        tender_item = TenderItem(
            tender_id=tender_id,
            source_document_id=document_id,
            source_page=1,
            document_page_id=document_page_id,
            normalized_content_id=None,
            item_number="1",
            parent_item_number=None,
            raw_description="Servicio",
            quantity=None,
            unit=None,
            source_excerpt="PARTIDA 1",
            source_locator="page:1|segment:0",
            extraction_confidence=1.0,
            extraction_status="DETERMINED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-06.1",
            semantic_fingerprint="fingerprint-delete-safe",
        )
        db.add(tender_item)
        db.flush()

        state = _page_state(
            1,
            [
                PageStructuralSegment(
                    item_identity=normalize_item_identity("1"),
                    starts_on_this_page=True,
                    sequence=0,
                    anchor_raw_text="PARTIDA 1",
                    has_service=True,
                    has_supply=False,
                    has_deliverable=False,
                    review_required=False,
                )
            ],
            incoming_item_key=None,
            outgoing_item_key="1",
        )
        source_analysis_id, source_page_result_id = _seed_scope_vision_provenance(document_id, document_page_id, 1)
        rows = persist_tender_scope_segments(
            db,
            tender_id=tender_id,
            page_state=state,
            source_document_id=document_id,
            document_page_id=document_page_id,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            tender_item_id_by_candidate_key={"1": tender_item.id},
        )
        db.commit()
        for row in rows:
            db.refresh(row)
            db.expunge(row)
        scope_segment_id = rows[0].id
        db.delete(tender_item)
        db.commit()

        persisted = db.get(TenderScopeSegment, scope_segment_id)
        assert persisted is not None
        assert persisted.tender_item_id is None
        assert persisted.candidate_item_key == "1"
    finally:
        db.close()
