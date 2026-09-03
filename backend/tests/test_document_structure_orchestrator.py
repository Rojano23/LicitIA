from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.document_structure_orchestrator import orchestrate_document_structure_available_only
from app.main import app
from app.models import (
    DocumentPage,
    DocumentPageRegion,
    DocumentPageStructureResolution,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    PageOcrResult,
    TenderDocument,
    TenderItem,
    TenderScopeSegment,
)
from app.ollama_vision import VISION_STRUCTURE_SCOPE_PROMPT_VERSION
from app.database import SessionLocal

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


def _create_page(db, document_id: str, page_number: int, text: str, *, status: str = "TEXT_EXTRACTED") -> DocumentPage:
    page = DocumentPage(
        document_id=document_id,
        page_number=page_number,
        text=text,
        char_count=len(text),
        extraction_method="NATIVE_PDF",
        status=status,
    )
    db.add(page)
    db.flush()
    document = db.get(TenderDocument, document_id)
    assert document is not None
    document.page_count = max(document.page_count, page_number)
    document.processing_status = "TEXT_EXTRACTION_COMPLETE"
    return page


def _add_native_normalized(db, page: DocumentPage, text: str) -> None:
    db.add(
        NormalizedContent(
            document_page_id=page.id,
            page_ocr_result_id=None,
            region_id=None,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            engine=None,
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"native|{page.id}|{text}".encode("utf-8")).hexdigest(),
        )
    )


def _add_ocr_source(
    db,
    page: DocumentPage,
    *,
    engine: str,
    text: str,
    scope: str = "FULL_PAGE",
    region_index: int | None = None,
    result_status: str = "OCR_TEXT_EXTRACTED",
) -> None:
    region_id = None
    if scope == "IMAGE_REGION":
        assert region_index is not None
        region = DocumentPageRegion(
            document_page_id=page.id,
            region_index=region_index,
            region_type="IMAGE",
            x0=0,
            y0=0,
            x1=100,
            y1=100,
            width=100,
            height=100,
            area_ratio=0.4,
        )
        db.add(region)
        db.flush()
        region_id = region.id

    result = PageOcrResult(
        document_page_id=page.id,
        engine=engine,
        engine_version="test",
        language="es+en",
        text=text,
        status=result_status,
        confidence=0.95,
        processing_time_ms=10,
        warnings=None,
        scope=scope,
        region_id=region_id,
    )
    db.add(result)
    db.flush()

    db.add(
        NormalizedContent(
            document_page_id=page.id,
            page_ocr_result_id=result.id,
            region_id=region_id,
            source_type="OCR",
            source_scope="IMAGE_REGION" if region_id else "FULL_PAGE",
            engine=engine,
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"ocr|{page.id}|{engine}|{scope}|{text}".encode("utf-8")).hexdigest(),
        )
    )


def _add_vision_result(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    structured_json: dict,
    analysis_status: str = "COMPLETED",
    page_status: str = "COMPLETED",
    prompt_version: str = VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
) -> None:
    fingerprint = hashlib.sha256(
        f"vision|{document_id}|{page.page_number}|{prompt_version}|{analysis_status}".encode("utf-8")
    ).hexdigest()
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status=analysis_status,
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b",
        prompt_version=prompt_version,
        input_fingerprint_sha256=fingerprint,
    )
    db.add(analysis)
    db.flush()

    image_sha256 = hashlib.sha256(f"image|{page.id}|{page.page_number}|{prompt_version}".encode("utf-8")).hexdigest()
    page_result = DocumentVisionPageResult(
        analysis_id=analysis.id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=image_sha256,
        status=page_status,
        raw_response_text=None,
        structured_json=structured_json,
        extracted_markdown=None,
        extracted_plain_text=None,
        warnings=[],
        processing_time_ms=5,
    )
    db.add(page_result)


def _seed_tender_item(db, *, tender_id: str, document_id: str, page: DocumentPage, item_number: str) -> None:
    db.add(
        TenderItem(
            tender_id=tender_id,
            source_document_id=document_id,
            source_page=page.page_number,
            document_page_id=page.id,
            normalized_content_id=None,
            item_number=item_number,
            parent_item_number=None,
            raw_description=f"Partida {item_number}",
            quantity=None,
            unit=None,
            source_excerpt=f"PARTIDA {item_number}",
            source_locator=f"page:{page.page_number}|segment:0",
            extraction_confidence=1.0,
            extraction_status="DETERMINED",
            detection_origin="DETERMINISTIC",
            detector_version="test",
            semantic_fingerprint=hashlib.sha256(f"item|{document_id}|{page.page_number}|{item_number}".encode("utf-8")).hexdigest(),
        )
    )


def _vision_structured(page_number: int, item_number: str) -> dict:
    return {
        "page_number": page_number,
        "continues_previous_item": False,
        "previous_item_number": None,
        "open_item_at_page_end": item_number,
        "item_segments": [
            {
                "item_number": item_number,
                "starts_on_this_page": True,
                "anchor_raw_text": f"PARTIDA {item_number}",
                "review_required": False,
            }
        ],
        "_continuity_state_quality": "VALID",
    }


def test_native_resolved_persists_status_and_scope() -> None:
    tender_id = _create_tender("orchestrator native", "MVP-625B1-001")
    document_id = _import_pdf(tender_id, "orchestrator-native.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "PARTIDA 1\nServicio")
        _add_native_normalized(db, page, "PARTIDA 1\nServicio")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="1")

        result = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert result.scope_segments_persisted == 1
        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "NATIVE_TEXT"

        row = db.scalar(select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id == page.id))
        assert row is not None
        assert row.status == "RESOLVED"
        assert row.selected_source_method == "NATIVE_TEXT"

        segments = db.execute(select(TenderScopeSegment).where(TenderScopeSegment.source_document_id == document_id)).scalars().all()
        assert len(segments) == 1
        assert segments[0].candidate_item_key == "1"
        assert segments[0].source_method == "NATIVE_TEXT"
    finally:
        db.close()


def test_single_ocr_source_is_used_when_native_unknown() -> None:
    tender_id = _create_tender("orchestrator ocr", "MVP-625B1-002")
    document_id = _import_pdf(tender_id, "orchestrator-ocr.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "tabla sin partida")
        _add_native_normalized(db, page, "tabla sin partida")
        _add_ocr_source(db, page, engine="tesseract", text="PARTIDA 4\nServicio", scope="FULL_PAGE")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="4")

        result = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "OCR"

        segment = db.scalar(select(TenderScopeSegment).where(TenderScopeSegment.source_document_id == document_id))
        assert segment is not None
        assert segment.candidate_item_key == "4"
        assert segment.source_method == "OCR"
    finally:
        db.close()


def test_multi_engine_ocr_conflict_sets_review_required_and_clears_scope() -> None:
    tender_id = _create_tender("orchestrator ocr conflict", "MVP-625B1-003")
    document_id = _import_pdf(tender_id, "orchestrator-ocr-conflict.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "PARTIDA 1\nServicio base")
        _add_native_normalized(db, page, "PARTIDA 1\nServicio base")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="1")

        first = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()
        assert first.page_results[0].status == "RESOLVED"
        assert db.execute(select(func.count(TenderScopeSegment.id)).where(TenderScopeSegment.source_document_id == document_id)).scalar_one() == 1

        # Make native inconclusive and add conflicting OCR providers.
        page.text = "contenido sin etiqueta"
        page.char_count = len(page.text)
        native = db.scalar(
            select(NormalizedContent).where(
                NormalizedContent.document_page_id == page.id,
                NormalizedContent.source_type == "NATIVE_PDF",
            )
        )
        assert native is not None
        native.normalized_text = "contenido sin etiqueta"
        native.char_count = len(native.normalized_text)
        native.content_sha256 = hashlib.sha256("native-reset".encode("utf-8")).hexdigest()

        _add_ocr_source(db, page, engine="tesseract", text="PARTIDA 2\nServicio")
        _add_ocr_source(db, page, engine="paddleocr", text="PARTIDA 3\nServicio")

        second = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert second.page_results[0].status == "REVIEW_REQUIRED"
        assert second.page_results[0].reason == "CONFLICTING_VALID_STRUCTURES"
        assert db.execute(select(func.count(TenderScopeSegment.id)).where(TenderScopeSegment.source_document_id == document_id)).scalar_one() == 0

        resolution = db.scalar(select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id == page.id))
        assert resolution is not None
        assert resolution.status == "REVIEW_REQUIRED"
        assert resolution.review_required is True
    finally:
        db.close()


def test_partial_vision_is_reused_when_valid() -> None:
    tender_id = _create_tender("orchestrator partial vision", "MVP-625B1-004")
    document_id = _import_pdf(tender_id, "orchestrator-partial-vision.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido no estructurado")
        _add_native_normalized(db, page, "contenido no estructurado")
        _add_ocr_source(db, page, engine="tesseract", text="sin partida", scope="FULL_PAGE")
        _add_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=_vision_structured(1, "7"),
            analysis_status="PARTIAL",
            page_status="PARTIAL",
        )
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="7")

        result = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "VISION"

        segment = db.scalar(select(TenderScopeSegment).where(TenderScopeSegment.source_document_id == document_id))
        assert segment is not None
        assert segment.source_method == "VISION"
        assert segment.candidate_item_key == "7"
    finally:
        db.close()


def test_incompatible_vision_prompt_is_not_reused_and_needs_vision() -> None:
    tender_id = _create_tender("orchestrator incompatible vision", "MVP-625B1-005")
    document_id = _import_pdf(tender_id, "orchestrator-incompatible-vision.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido no estructurado")
        _add_native_normalized(db, page, "contenido no estructurado")
        _add_ocr_source(db, page, engine="tesseract", text="texto sin item", scope="FULL_PAGE")
        _add_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=_vision_structured(1, "9"),
            prompt_version="vision-structure-scope-older-contract",
        )

        result = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert result.page_results[0].status == "NEEDS_VISION"
        assert result.page_results[0].needs_provider == "VISION"
        assert result.scope_segments_persisted == 0
    finally:
        db.close()


def test_idempotent_rerun_updates_single_resolution_row() -> None:
    tender_id = _create_tender("orchestrator idempotent", "MVP-625B1-006")
    document_id = _import_pdf(tender_id, "orchestrator-idempotent.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "PARTIDA 2\nServicio")
        _add_native_normalized(db, page, "PARTIDA 2\nServicio")

        first = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()
        second = orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert first.page_results[0].status == "RESOLVED"
        assert second.page_results[0].status == "RESOLVED"

        resolution_count = db.execute(
            select(func.count(DocumentPageStructureResolution.id)).where(DocumentPageStructureResolution.document_page_id == page.id)
        ).scalar_one()
        assert resolution_count == 1

        scope_count = db.execute(
            select(func.count(TenderScopeSegment.id)).where(TenderScopeSegment.source_document_id == document_id)
        ).scalar_one()
        assert scope_count == 1
    finally:
        db.close()


def test_discoverability_after_session_reload() -> None:
    tender_id = _create_tender("orchestrator discoverability", "MVP-625B1-007")
    document_id = _import_pdf(tender_id, "orchestrator-discoverability.pdf")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "PARTIDA 1\nServicio")
        _add_native_normalized(db, page, "PARTIDA 1\nServicio")
        orchestrate_document_structure_available_only(db, tender_id=tender_id, document_id=document_id)
        db.commit()
        page_id = page.id
    finally:
        db.close()

    reloaded_db = SessionLocal()
    try:
        persisted = reloaded_db.scalar(
            select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id == page_id)
        )
        assert persisted is not None
        assert persisted.status == "RESOLVED"
        assert persisted.selected_source_method == "NATIVE_TEXT"
    finally:
        reloaded_db.close()
