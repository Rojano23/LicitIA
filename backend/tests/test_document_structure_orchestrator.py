from __future__ import annotations

import hashlib
import sys
import types

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

import app.document_structure_orchestrator as orchestrator_module
import app.ollama_vision as ollama_vision_module
from app.document_structure_orchestrator import (
    EXECUTION_POLICY_ALLOW_OCR,
    EXECUTION_POLICY_AUTO,
    EXECUTION_POLICY_AVAILABLE_ONLY,
    orchestrate_document_structure_available_only,
)
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
from app.schemas import VisionProviderStatusRead
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
        db.commit()

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
        db.commit()

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
        db.commit()

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
        db.commit()

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
        db.commit()

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
        db.commit()

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
        db.commit()

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
        db.commit()
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


def test_available_only_regression_does_not_execute_providers() -> None:
    tender_id = _create_tender("orchestrator available only", "MVP-625B2-001")
    document_id = _import_pdf(tender_id, "orchestrator-available-only.pdf")
    calls: list[str] = []

    def fake_ocr(_request) -> None:
        calls.append("ocr")

    def fake_vision(_request) -> None:
        calls.append("vision")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AVAILABLE_ONLY,
            ocr_executor=fake_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "NEEDS_VISION"
        assert calls == []
    finally:
        db.close()


def test_allow_ocr_image_only_calls_ocr_once_and_never_vision() -> None:
    tender_id = _create_tender("orchestrator allow ocr image-only", "MVP-625B2-002")
    document_id = _import_pdf(tender_id, "orchestrator-allow-ocr-image-only.pdf")
    calls: list[str] = []

    db = SessionLocal()

    def fake_ocr(request) -> None:
        calls.append(f"ocr:{request.page_number}")
        fake_db = SessionLocal()
        try:
            result = PageOcrResult(
                document_page_id=request.document_page_id,
                engine="TESSERACT",
                engine_version="fake",
                language="es+en",
                text="PARTIDA 4\nServicio",
                status="OCR_TEXT_EXTRACTED",
                confidence=0.95,
                processing_time_ms=1,
                warnings=None,
                scope="FULL_PAGE",
                region_id=None,
            )
            fake_db.add(result)
            fake_db.flush()
            fake_db.add(
                NormalizedContent(
                    document_page_id=request.document_page_id,
                    page_ocr_result_id=result.id,
                    region_id=None,
                    source_type="OCR",
                    source_scope="FULL_PAGE",
                    engine="TESSERACT",
                    normalized_text="PARTIDA 4\nServicio",
                    char_count=len("PARTIDA 4\nServicio"),
                    content_sha256=hashlib.sha256(f"ocr|{request.document_page_id}|4".encode("utf-8")).hexdigest(),
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    def fake_vision(_request) -> None:
        calls.append("vision")

    try:
        page = _create_page(db, document_id, 1, "", status="NO_TEXT")
        region = DocumentPageRegion(
            document_page_id=page.id,
            region_index=0,
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
        _add_native_normalized(db, page, "")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="4")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_ALLOW_OCR,
            ocr_executor=fake_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "OCR"
        assert calls == ["ocr:1"]
    finally:
        db.close()


def test_text_only_unknown_auto_skips_ocr_and_requests_vision() -> None:
    tender_id = _create_tender("orchestrator auto text-only", "MVP-625B2-003")
    document_id = _import_pdf(tender_id, "orchestrator-auto-text-only.pdf")
    calls: list[str] = []

    db = SessionLocal()

    def fake_ocr(_request) -> None:
        calls.append("ocr")

    def fake_vision(request) -> None:
        calls.append(f"vision:{request.page_number}")
        fake_db = SessionLocal()
        try:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="qwen-test",
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=hashlib.sha256(f"vision|{request.document_page_id}".encode("utf-8")).hexdigest(),
            )
            fake_db.add(analysis)
            fake_db.flush()
            fake_db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=request.document_page_id,
                    page_number=request.page_number,
                    image_sha256=hashlib.sha256(f"img|{request.document_page_id}".encode("utf-8")).hexdigest(),
                    status="COMPLETED",
                    raw_response_text=None,
                    structured_json=_vision_structured(1, "8"),
                    extracted_markdown=None,
                    extracted_plain_text=None,
                    warnings=[],
                    processing_time_ms=5,
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="8")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            ocr_executor=fake_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "VISION"
        assert calls == ["vision:1"]
    finally:
        db.close()


def test_persisted_ocr_valid_prevents_new_ocr_execution() -> None:
    tender_id = _create_tender("orchestrator reuse ocr", "MVP-625B2-004")
    document_id = _import_pdf(tender_id, "orchestrator-reuse-ocr.pdf")
    calls: list[str] = []

    def fake_ocr(_request) -> None:
        calls.append("ocr")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "texto sin item")
        _add_native_normalized(db, page, "texto sin item")
        _add_ocr_source(db, page, engine="tesseract", text="PARTIDA 6\nServicio", scope="FULL_PAGE")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="6")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_ALLOW_OCR,
            ocr_executor=fake_ocr,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "OCR"
        assert calls == []
    finally:
        db.close()


def test_multipage_targets_only_unresolved_page_for_vision() -> None:
    tender_id = _create_tender("orchestrator multipage targeting", "MVP-625B2-005")
    document_id = _import_pdf(tender_id, "orchestrator-multipage-targeting.pdf")
    calls: list[str] = []

    def fake_vision(request) -> None:
        calls.append(f"vision:{request.page_number}")
        fake_db = SessionLocal()
        try:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="qwen-test",
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=hashlib.sha256(f"vision|{request.document_page_id}|{request.page_number}".encode("utf-8")).hexdigest(),
            )
            fake_db.add(analysis)
            fake_db.flush()
            item_number = "2" if request.page_number == 2 else "1"
            fake_db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=request.document_page_id,
                    page_number=request.page_number,
                    image_sha256=hashlib.sha256(f"img|{request.document_page_id}|{request.page_number}".encode("utf-8")).hexdigest(),
                    status="COMPLETED",
                    raw_response_text=None,
                    structured_json=_vision_structured(request.page_number, item_number),
                    extracted_markdown=None,
                    extracted_plain_text=None,
                    warnings=[],
                    processing_time_ms=5,
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    db = SessionLocal()
    try:
        page1 = _create_page(db, document_id, 1, "PARTIDA 1\nServicio")
        _add_native_normalized(db, page1, "PARTIDA 1\nServicio")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page1, item_number="1")

        page2 = _create_page(db, document_id, 2, "contenido sin partida")
        _add_native_normalized(db, page2, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page2, item_number="2")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            vision_executor=fake_vision,
        )
        db.commit()

        assert len(result.page_results) == 2
        assert calls == ["vision:2"]
    finally:
        db.close()


def test_auto_marks_review_required_when_vision_executor_fails() -> None:
    tender_id = _create_tender("orchestrator vision fail", "MVP-625B2-006")
    document_id = _import_pdf(tender_id, "orchestrator-vision-fail.pdf")

    def failing_vision(_request) -> None:
        raise RuntimeError("VISION_TIMEOUT")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        db.commit()

        first = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AVAILABLE_ONLY,
        )
        db.commit()
        assert first.page_results[0].status == "NEEDS_VISION"

        second = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            vision_executor=failing_vision,
        )
        db.commit()

        assert second.page_results[0].status == "REVIEW_REQUIRED"
        assert second.page_results[0].reason is not None
        scope_count = db.execute(
            select(func.count(TenderScopeSegment.id)).where(TenderScopeSegment.source_document_id == document_id)
        ).scalar_one()
        assert scope_count == 0
    finally:
        db.close()


def test_orchestrator_transaction_closed_during_ocr_executor() -> None:
    tender_id = _create_tender("orchestrator txn seam ocr", "MVP-625B2-007")
    document_id = _import_pdf(tender_id, "orchestrator-txn-seam-ocr.pdf")
    transaction_flags: list[bool] = []

    db = SessionLocal()

    def fake_ocr(request) -> None:
        transaction_flags.append(bool(db.in_transaction()))
        fake_db = SessionLocal()
        try:
            result = PageOcrResult(
                document_page_id=request.document_page_id,
                engine="TESSERACT",
                engine_version="fake",
                language="es+en",
                text="PARTIDA 5\nServicio",
                status="OCR_TEXT_EXTRACTED",
                confidence=0.95,
                processing_time_ms=1,
                warnings=None,
                scope="FULL_PAGE",
                region_id=None,
            )
            fake_db.add(result)
            fake_db.flush()
            fake_db.add(
                NormalizedContent(
                    document_page_id=request.document_page_id,
                    page_ocr_result_id=result.id,
                    region_id=None,
                    source_type="OCR",
                    source_scope="FULL_PAGE",
                    engine="TESSERACT",
                    normalized_text="PARTIDA 5\nServicio",
                    char_count=len("PARTIDA 5\nServicio"),
                    content_sha256=hashlib.sha256(f"ocr|{request.document_page_id}|5".encode("utf-8")).hexdigest(),
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    try:
        page = _create_page(db, document_id, 1, "", status="NO_TEXT")
        db.add(
            DocumentPageRegion(
                document_page_id=page.id,
                region_index=0,
                region_type="IMAGE",
                x0=0,
                y0=0,
                x1=100,
                y1=100,
                width=100,
                height=100,
                area_ratio=0.4,
            )
        )
        _add_native_normalized(db, page, "")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="5")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_ALLOW_OCR,
            ocr_executor=fake_ocr,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert transaction_flags == [False]
    finally:
        db.close()


def test_orchestrator_transaction_closed_during_vision_executor() -> None:
    tender_id = _create_tender("orchestrator txn seam vision", "MVP-625B2-008")
    document_id = _import_pdf(tender_id, "orchestrator-txn-seam-vision.pdf")
    transaction_flags: list[bool] = []

    db = SessionLocal()

    def fake_vision(request) -> None:
        transaction_flags.append(bool(db.in_transaction()))
        fake_db = SessionLocal()
        try:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="qwen-test",
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=hashlib.sha256(f"vision|{request.document_page_id}|txn".encode("utf-8")).hexdigest(),
            )
            fake_db.add(analysis)
            fake_db.flush()
            fake_db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=request.document_page_id,
                    page_number=request.page_number,
                    image_sha256=hashlib.sha256(f"img|{request.document_page_id}|txn".encode("utf-8")).hexdigest(),
                    status="COMPLETED",
                    raw_response_text=None,
                    structured_json=_vision_structured(request.page_number, "8"),
                    extracted_markdown=None,
                    extracted_plain_text=None,
                    warnings=[],
                    processing_time_ms=5,
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="8")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert transaction_flags == [False]
    finally:
        db.close()


def test_default_ocr_executor_has_no_internal_session_during_slow_call(monkeypatch: pytest.MonkeyPatch) -> None:
    tender_id = _create_tender("orchestrator default ocr isolation", "MVP-625B2-009")
    document_id = _import_pdf(tender_id, "orchestrator-default-ocr-isolation.pdf")

    open_session_count = 0
    observed_open_counts: list[int] = []
    real_session_factory = SessionLocal

    class _TrackedSessionContext:
        def __init__(self, session) -> None:
            self._session = session

        def __enter__(self):
            nonlocal open_session_count
            open_session_count += 1
            self._session.__enter__()
            return self._session

        def __exit__(self, exc_type, exc_value, traceback):
            nonlocal open_session_count
            try:
                return self._session.__exit__(exc_type, exc_value, traceback)
            finally:
                open_session_count -= 1

    def _tracked_session_factory():
        return _TrackedSessionContext(real_session_factory())

    class _FakeOcrProvider:
        provider_id = "TESSERACT"
        status = "AVAILABLE"
        version = "fake"

        def recognize(self, _page_image, language: str = "es+en") -> dict[str, object]:
            observed_open_counts.append(open_session_count)
            return {
                "text": "PARTIDA 3\nServicio",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "TESSERACT",
                "engine_version": "fake",
                "language": language,
                "confidence": 0.9,
                "processing_time_ms": 1,
                "warnings": [],
            }

    class _FakePixmap:
        def tobytes(self, _format: str) -> bytes:
            return b"fake-png"

    class _FakePage:
        def get_pixmap(self, matrix=None, clip=None):
            _ = matrix, clip
            return _FakePixmap()

    class _FakePdf:
        page_count = 1

        def __getitem__(self, index: int):
            if index != 0:
                raise IndexError(index)
            return _FakePage()

        def close(self) -> None:
            return None

    fake_fitz_module = types.SimpleNamespace(
        Matrix=lambda _x, _y: None,
        Rect=lambda *args: args,
        open=lambda _path: _FakePdf(),
    )

    monkeypatch.setattr(orchestrator_module, "SessionLocal", _tracked_session_factory)
    monkeypatch.setattr(orchestrator_module, "get_ocr_providers", lambda: [_FakeOcrProvider()])
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz_module)

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "", status="NO_TEXT")
        db.add(
            DocumentPageRegion(
                document_page_id=page.id,
                region_index=0,
                region_type="IMAGE",
                x0=0,
                y0=0,
                x1=100,
                y1=100,
                width=100,
                height=100,
                area_ratio=0.4,
            )
        )
        _add_native_normalized(db, page, "")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="3")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_ALLOW_OCR,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert observed_open_counts == [0]
    finally:
        db.close()


def test_structure_only_default_vision_never_calls_detail_and_has_no_internal_session_during_slow_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tender_id = _create_tender("orchestrator detail isolation", "MVP-625B2-010")
    document_id = _import_pdf(tender_id, "orchestrator-detail-isolation.pdf")

    open_session_count = 0
    observed_open_counts: list[int] = []
    real_session_factory = SessionLocal

    class _TrackedSessionContext:
        def __init__(self, session) -> None:
            self._session = session

        def __enter__(self):
            nonlocal open_session_count
            open_session_count += 1
            self._session.__enter__()
            return self._session

        def __exit__(self, exc_type, exc_value, traceback):
            nonlocal open_session_count
            try:
                return self._session.__exit__(exc_type, exc_value, traceback)
            finally:
                open_session_count -= 1

    def _tracked_session_factory():
        return _TrackedSessionContext(real_session_factory())

    available_provider = VisionProviderStatusRead(
        provider_id="OLLAMA_VISION",
        provider_name="Ollama Vision Assist",
        provider_status="AVAILABLE",
        provider_status_reason="runtime mocked",
        runtime_available=True,
        configured_model=ollama_vision_module.VISION_ASSIST_MODEL_NAME,
        selected_model=ollama_vision_module.VISION_ASSIST_MODEL_NAME,
        model_available=True,
        models_available=[ollama_vision_module.VISION_ASSIST_MODEL_NAME],
        base_url="http://127.0.0.1:11434",
    )

    def fake_analyze_structure_scope_page(self, *, page_number: int, image_bytes: bytes, mode: str, previous_page_context):
        _ = image_bytes, mode, previous_page_context
        observed_open_counts.append(open_session_count)
        return "COMPLETED", _vision_structured(page_number, "8"), 5, 200, [], None, None, "{}"

    def fake_render_document_pages(self, document, page_numbers, *, zoom=2.0):
        _ = document, zoom
        rendered = []
        for page_number in page_numbers:
            rendered.append(
                ollama_vision_module.RenderedVisionPage(
                    page_number=page_number,
                    document_page_id="",
                    image_bytes=b"fake-image",
                    image_sha256=hashlib.sha256(f"vision-img-{page_number}".encode("utf-8")).hexdigest(),
                    width_px=1000,
                    height_px=1400,
                    image_bytes_size=1024,
                    render_time_ms=1,
                    render_zoom=2.0,
                    warnings=[],
                )
            )
        return rendered

    def fail_detail_call(self, **_kwargs):
        raise AssertionError("DETAIL_TRANSCRIPTION must not execute in structure-only acquisition")

    monkeypatch.setattr(ollama_vision_module, "SessionLocal", _tracked_session_factory)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "probe", lambda self: available_provider)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "ensure_available", lambda self: available_provider)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "render_document_pages", fake_render_document_pages)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "analyze_structure_scope_page", fake_analyze_structure_scope_page)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "analyze_detail_transcription_page", fail_detail_call)

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="8")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "VISION"
        assert observed_open_counts == [0]
    finally:
        db.close()


def test_completed_unusable_vision_result_is_retried_on_explicit_later_run(monkeypatch: pytest.MonkeyPatch) -> None:
    tender_id = _create_tender("orchestrator completed unusable retry", "MVP-625B2-011")
    document_id = _import_pdf(tender_id, "orchestrator-completed-unusable-retry.pdf")
    structure_call_count = {"count": 0}

    available_provider = VisionProviderStatusRead(
        provider_id="OLLAMA_VISION",
        provider_name="Ollama Vision Assist",
        provider_status="AVAILABLE",
        provider_status_reason="runtime mocked",
        runtime_available=True,
        configured_model=ollama_vision_module.VISION_ASSIST_MODEL_NAME,
        selected_model=ollama_vision_module.VISION_ASSIST_MODEL_NAME,
        model_available=True,
        models_available=[ollama_vision_module.VISION_ASSIST_MODEL_NAME],
        base_url="http://127.0.0.1:11434",
    )

    def fake_analyze_structure_scope_page(self, *, page_number: int, image_bytes: bytes, mode: str, previous_page_context):
        _ = image_bytes, mode, previous_page_context
        structure_call_count["count"] += 1
        if structure_call_count["count"] == 1:
            unusable = {
                "page_number": page_number,
                "continues_previous_item": False,
                "previous_item_number": None,
                "item_segments": [],
                "new_items": [],
                "open_item_at_page_end": None,
                "uncertainties": [],
                "_continuity_state_quality": "UNKNOWN",
            }
            return "COMPLETED", unusable, 5, 200, [], None, None, "{}"
        return "COMPLETED", _vision_structured(page_number, "9"), 5, 200, [], None, None, "{}"

    def fake_render_document_pages(self, document, page_numbers, *, zoom=2.0):
        _ = document, zoom
        rendered = []
        for page_number in page_numbers:
            rendered.append(
                ollama_vision_module.RenderedVisionPage(
                    page_number=page_number,
                    document_page_id="",
                    image_bytes=b"fake-image",
                    image_sha256=hashlib.sha256(f"retry-img-{page_number}".encode("utf-8")).hexdigest(),
                    width_px=1000,
                    height_px=1400,
                    image_bytes_size=1024,
                    render_time_ms=1,
                    render_zoom=2.0,
                    warnings=[],
                )
            )
        return rendered

    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "probe", lambda self: available_provider)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "ensure_available", lambda self: available_provider)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "render_document_pages", fake_render_document_pages)
    monkeypatch.setattr(ollama_vision_module.OllamaVisionAssistClient, "analyze_structure_scope_page", fake_analyze_structure_scope_page)

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "contenido sin partida")
        _add_native_normalized(db, page, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="9")
        db.commit()

        first = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
        )
        db.commit()
        assert first.page_results[0].status in {"REVIEW_REQUIRED", "NEEDS_VISION"}

        second = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
        )
        db.commit()

        assert second.page_results[0].status == "RESOLVED"
        assert second.page_results[0].selected_source_method == "VISION"
        assert structure_call_count["count"] == 2
    finally:
        db.close()


def test_auto_ocr_exception_escalates_to_vision_once() -> None:
    tender_id = _create_tender("orchestrator auto ocr failure", "MVP-625B2-012")
    document_id = _import_pdf(tender_id, "orchestrator-auto-ocr-failure.pdf")
    calls: list[str] = []

    def failing_ocr(request) -> None:
        calls.append(f"ocr:{request.page_number}")
        raise RuntimeError("OCR_FAILURE")

    def fake_vision(request) -> None:
        calls.append(f"vision:{request.page_number}")
        fake_db = SessionLocal()
        try:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="qwen-test",
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=hashlib.sha256(f"vision|{request.document_page_id}|auto-fail".encode("utf-8")).hexdigest(),
            )
            fake_db.add(analysis)
            fake_db.flush()
            fake_db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=request.document_page_id,
                    page_number=request.page_number,
                    image_sha256=hashlib.sha256(f"img|{request.document_page_id}|auto-fail".encode("utf-8")).hexdigest(),
                    status="COMPLETED",
                    raw_response_text=None,
                    structured_json=_vision_structured(request.page_number, "12"),
                    extracted_markdown=None,
                    extracted_plain_text=None,
                    warnings=[],
                    processing_time_ms=5,
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "", status="NO_TEXT")
        db.add(
            DocumentPageRegion(
                document_page_id=page.id,
                region_index=0,
                region_type="IMAGE",
                x0=0,
                y0=0,
                x1=100,
                y1=100,
                width=100,
                height=100,
                area_ratio=0.4,
            )
        )
        _add_native_normalized(db, page, "")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="12")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            ocr_executor=failing_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "RESOLVED"
        assert result.page_results[0].selected_source_method == "VISION"
        assert calls == ["ocr:1", "vision:1"]
    finally:
        db.close()


def test_allow_ocr_exception_never_calls_vision_and_persists_unresolved_state() -> None:
    tender_id = _create_tender("orchestrator allow ocr failure", "MVP-625B2-013")
    document_id = _import_pdf(tender_id, "orchestrator-allow-ocr-failure.pdf")
    calls: list[str] = []

    def failing_ocr(request) -> None:
        calls.append(f"ocr:{request.page_number}")
        raise RuntimeError("OCR_FAILURE")

    def fake_vision(_request) -> None:
        calls.append("vision")

    db = SessionLocal()
    try:
        page = _create_page(db, document_id, 1, "", status="NO_TEXT")
        db.add(
            DocumentPageRegion(
                document_page_id=page.id,
                region_index=0,
                region_type="IMAGE",
                x0=0,
                y0=0,
                x1=100,
                y1=100,
                width=100,
                height=100,
                area_ratio=0.4,
            )
        )
        _add_native_normalized(db, page, "")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_ALLOW_OCR,
            ocr_executor=failing_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert result.page_results[0].status == "NEEDS_VISION"
        assert calls == ["ocr:1"]
        resolution = db.scalar(select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id == page.id))
        assert resolution is not None
        assert resolution.status == "NEEDS_VISION"
        scope_count = db.execute(
            select(func.count(TenderScopeSegment.id)).where(TenderScopeSegment.source_document_id == document_id)
        ).scalar_one()
        assert scope_count == 0
    finally:
        db.close()


def test_mixed_provider_full_document_routes_all_pages_through_neutral_scope_linker() -> None:
    tender_id = _create_tender("orchestrator mixed provider doc", "MVP-625B2-014")
    document_id = _import_pdf(tender_id, "orchestrator-mixed-provider-doc.pdf")
    calls: list[str] = []

    def fake_ocr(request) -> None:
        calls.append(f"ocr:{request.page_number}")
        fake_db = SessionLocal()
        try:
            result = PageOcrResult(
                document_page_id=request.document_page_id,
                engine="TESSERACT",
                engine_version="fake",
                language="es+en",
                text="PARTIDA 3\nServicio",
                status="OCR_TEXT_EXTRACTED",
                confidence=0.95,
                processing_time_ms=1,
                warnings=None,
                scope="FULL_PAGE",
                region_id=None,
            )
            fake_db.add(result)
            fake_db.flush()
            fake_db.add(
                NormalizedContent(
                    document_page_id=request.document_page_id,
                    page_ocr_result_id=result.id,
                    region_id=None,
                    source_type="OCR",
                    source_scope="FULL_PAGE",
                    engine="TESSERACT",
                    normalized_text="PARTIDA 3\nServicio",
                    char_count=len("PARTIDA 3\nServicio"),
                    content_sha256=hashlib.sha256(f"ocr|{request.document_page_id}|3".encode("utf-8")).hexdigest(),
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    def fake_vision(request) -> None:
        calls.append(f"vision:{request.page_number}")
        fake_db = SessionLocal()
        try:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status="COMPLETED",
                mode="ASSISTIVE_EXTRACTION",
                model_name="qwen-test",
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=hashlib.sha256(f"vision|{request.document_page_id}|mixed".encode("utf-8")).hexdigest(),
            )
            fake_db.add(analysis)
            fake_db.flush()
            fake_db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=request.document_page_id,
                    page_number=request.page_number,
                    image_sha256=hashlib.sha256(f"img|{request.document_page_id}|mixed".encode("utf-8")).hexdigest(),
                    status="COMPLETED",
                    raw_response_text=None,
                    structured_json=_vision_structured(request.page_number, "2"),
                    extracted_markdown=None,
                    extracted_plain_text=None,
                    warnings=[],
                    processing_time_ms=5,
                )
            )
            fake_db.commit()
        finally:
            fake_db.close()

    db = SessionLocal()
    try:
        page1 = _create_page(db, document_id, 1, "PARTIDA 1\nServicio")
        _add_native_normalized(db, page1, "PARTIDA 1\nServicio")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page1, item_number="1")

        page2 = _create_page(db, document_id, 2, "contenido sin partida")
        _add_native_normalized(db, page2, "contenido sin partida")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page2, item_number="2")

        page3 = _create_page(db, document_id, 3, "", status="NO_TEXT")
        db.add(
            DocumentPageRegion(
                document_page_id=page3.id,
                region_index=0,
                region_type="IMAGE",
                x0=0,
                y0=0,
                x1=100,
                y1=100,
                width=100,
                height=100,
                area_ratio=0.4,
            )
        )
        _add_native_normalized(db, page3, "")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page3, item_number="3")

        page4 = _create_page(db, document_id, 4, "PARTIDA 4\nServicio")
        _add_native_normalized(db, page4, "PARTIDA 4\nServicio")
        _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page4, item_number="4")
        db.commit()

        result = orchestrate_document_structure_available_only(
            db,
            tender_id=tender_id,
            document_id=document_id,
            execution_policy=EXECUTION_POLICY_AUTO,
            ocr_executor=fake_ocr,
            vision_executor=fake_vision,
        )
        db.commit()

        assert len(result.page_results) == 4
        assert "vision:2" in calls
        assert "ocr:3" in calls

        segments = db.execute(
            select(TenderScopeSegment).where(TenderScopeSegment.source_document_id == document_id)
        ).scalars().all()
        methods_by_page = {segment.page_number: segment.source_method for segment in segments}
        assert methods_by_page[1] == "NATIVE_TEXT"
        assert methods_by_page[2] == "VISION"
        assert methods_by_page[3] == "OCR"
        assert methods_by_page[4] == "NATIVE_TEXT"
    finally:
        db.close()
