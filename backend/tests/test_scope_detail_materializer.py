from __future__ import annotations

import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import ollama_vision as ollama_vision_module
from app import document_structure_orchestrator as orchestrator_module
from app import local_vision as local_vision_module
from app import ocr as ocr_module
from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentPageStructureResolution,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    PageOcrResult,
    TenderDocument,
    TenderItem,
    TenderScopeDetail,
    TenderScopeSegment,
)
from app.scope_detail_materializer import (
    EXECUTION_POLICY_AVAILABLE_ONLY,
    SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED,
    SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED,
    SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_DETAILS,
    SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE,
    SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL,
    SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
    materialize_document_scope_details,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-MATERIALIZE-{uuid4()}"
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


def _seed_page(db, document_id: str, page_number: int, text: str = "") -> DocumentPage:
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
    return page


def _seed_classification(db, document_id: str, human_type: str) -> None:
    db.add(
        DocumentClassification(
            document_id=document_id,
            suggested_type=human_type,
            suggested_score=90,
            classification_status="CONFIRMED",
            human_type=human_type,
        )
    )


def _seed_tender_item(db, *, tender_id: str, document_id: str, page: DocumentPage, item_number: str) -> TenderItem:
    row = TenderItem(
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
        detector_version="mvp-06.1",
        semantic_fingerprint=hashlib.sha256(f"item|{document_id}|{page.id}|{item_number}|{uuid4()}".encode("utf-8")).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _seed_scope_segment(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    candidate_item_key: str | None,
    tender_item_id: str | None,
    source_excerpt: str,
    source_page_result_id: str | None = None,
    review_required: bool = False,
    sequence_index: int = 0,
) -> TenderScopeSegment:
    row = TenderScopeSegment(
        tender_id=tender_id,
        source_document_id=document_id,
        document_page_id=page.id,
        page_number=page.page_number,
        tender_item_id=tender_item_id,
        candidate_item_key=candidate_item_key,
        candidate_item_raw_label=candidate_item_key,
        sequence_index=sequence_index,
        scope_domain=None,
        source_method="VISION",
        link_reason="EXPLICIT_ITEM_START",
        source_locator=f"page:{page.page_number}|segment:0",
        source_excerpt=source_excerpt,
        source_analysis_id=None,
        source_page_result_id=source_page_result_id,
        confidence=None,
        review_required=review_required,
        semantic_fingerprint=hashlib.sha256(
            f"segment|{document_id}|{page.id}|{candidate_item_key}|{tender_item_id}|{source_excerpt}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _seed_vision_result(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    structured_json: dict | None,
    prompt_version: str = "vision-detail-transcription-2026-08-31-001",
    analysis_status: str = "COMPLETED",
    image_sha256: str | None = None,
) -> DocumentVisionPageResult:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status=analysis_status,
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b-instruct",
        prompt_version=prompt_version,
        input_fingerprint_sha256=hashlib.sha256(
            f"analysis|{document_id}|{page.id}|{page.page_number}|{prompt_version}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(analysis)
    db.flush()

    page_result = DocumentVisionPageResult(
        analysis_id=analysis.id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=image_sha256 or hashlib.sha256(f"image|{page.id}|{uuid4()}".encode("utf-8")).hexdigest(),
        status="COMPLETED",
        raw_response_text=None,
        structured_json=structured_json,
        extracted_markdown=None,
        extracted_plain_text=None,
        warnings=[],
        processing_time_ms=5,
    )
    db.add(page_result)
    db.flush()
    return page_result


def _seed_ocr_result(db, *, page: DocumentPage, engine: str, text: str) -> PageOcrResult:
    row = PageOcrResult(
        document_page_id=page.id,
        engine=engine,
        engine_version="ocr-1",
        language="es+en",
        text=text,
        status="OCR_TEXT_EXTRACTED",
        confidence=0.95,
        processing_time_ms=8,
        warnings=None,
        scope="FULL_PAGE",
        region_id=None,
    )
    db.add(row)
    db.flush()
    return row


def _seed_native_content(db, *, page: DocumentPage, text: str) -> None:
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


def _seed_page_structure_resolution(
    db,
    *,
    document_id: str,
    page: DocumentPage,
    status: str = "RESOLVED",
    review_required: bool = False,
) -> DocumentPageStructureResolution:
    resolution = DocumentPageStructureResolution(
        source_document_id=document_id,
        document_page_id=page.id,
        page_number=page.page_number,
        status=status,
        selected_source_method="VISION",
        review_required=review_required,
        reason="seeded-test-resolution",
        resolver_version="page-structure-resolver-005",
        input_fingerprint_sha256=hashlib.sha256(
            f"resolution|{document_id}|{page.id}|{status}|{review_required}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(resolution)
    db.flush()
    return resolution


def _materialize(db, tender_id: str, document_id: str):
    return materialize_document_scope_details(
        db,
        tender_id=tender_id,
        document_id=document_id,
        execution_policy=EXECUTION_POLICY_AVAILABLE_ONLY,
    )


def test_persisted_vision_supply_materializes() -> None:
    tender_id = _create_tender("materializer vision supply")
    document_id = _import_pdf(tender_id, "materializer-supply.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "prompt_version": "vision-detail-transcription-2026-08-31-001",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                        "description": "MODULO DE ENTRADAS ANALOGICAS",
                        "quantity": "1",
                        "unit": "PIEZA",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_result(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        tender_item = _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page=page, item_number="2")
        _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            candidate_item_key="2",
            tender_item_id=tender_item.id,
            source_excerpt="PARTIDA 2",
            source_page_result_id=page_result.id,
        )

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.artifacts_materialized == 1
        assert result.persisted_count == 1
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.domain == "SUPPLY"
        assert row.quantity_raw == "1"
        assert row.unit_raw == "PIEZA"
    finally:
        db.close()


def test_persisted_vision_deliverable_materializes() -> None:
    tender_id = _create_tender("materializer vision deliverable")
    document_id = _import_pdf(tender_id, "materializer-deliverable.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "scope_type": "DELIVERABLE",
                        "item_number": "2",
                        "raw_visible_text": "ENTREGAR REPORTE FINAL FIRMADO",
                        "description": "ENTREGAR REPORTE FINAL FIRMADO",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_result(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id)

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.domain == "DELIVERABLE"
    finally:
        db.close()


def test_same_artifact_replay_is_idempotent() -> None:
    tender_id = _create_tender("materializer replay idempotent")
    document_id = _import_pdf(tender_id, "materializer-replay.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                        "description": "MODULO DE ENTRADAS ANALOGICAS",
                        "quantity": "1",
                        "unit": "PIEZA",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_result(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id)

        first = _materialize(db, tender_id, document_id)
        second = _materialize(db, tender_id, document_id)
        db.commit()

        assert first.persisted_count == second.persisted_count == 1
        count = db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert count == 1
    finally:
        db.close()


def test_rematerialize_no_details_clears_only_own_rows() -> None:
    tender_id = _create_tender("materializer no details replay")
    document_id = _import_pdf(tender_id, "materializer-no-details.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, document_id, 1, "PARTIDA 2")
        page_b = _seed_page(db, document_id, 2, "PARTIDA 3")
        artifact_a = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_a,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                            "description": "MODULO DE ENTRADAS ANALOGICAS",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        artifact_b = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_b,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 2,
                    "parsed_supply_rows": [
                        {
                            "scope_type": "DELIVERABLE",
                            "item_number": "3",
                            "raw_visible_text": "ENTREGAR REPORTE FINAL FIRMADO",
                            "description": "ENTREGAR REPORTE FINAL FIRMADO",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page_a, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=artifact_a.id)
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page_b, candidate_item_key="3", tender_item_id=None, source_excerpt="PARTIDA 3", source_page_result_id=artifact_b.id)

        _materialize(db, tender_id, document_id)
        page_result = db.get(DocumentVisionPageResult, artifact_a.id)
        assert page_result is not None
        page_result.structured_json = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [],
            }
        }
        first_replay = _materialize(db, tender_id, document_id)
        db.flush()
        db.commit()

        assert first_replay.artifacts_no_details >= 1
        with SessionLocal() as verify_db:
            a_count = verify_db.scalar(
                select(func.count(TenderScopeDetail.id)).where(
                    TenderScopeDetail.source_artifact_key == f"vision-page-result:{artifact_a.id}"
                )
            )
            b_count = verify_db.scalar(
                select(func.count(TenderScopeDetail.id)).where(
                    TenderScopeDetail.source_artifact_key == f"vision-page-result:{artifact_b.id}"
                )
            )
            assert a_count == 0
            assert b_count == 1
    finally:
        db.close()


def test_unresolved_ownership_persists_review_required() -> None:
    tender_id = _create_tender("materializer unresolved")
    document_id = _import_pdf(tender_id, "materializer-unresolved.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "SUMINISTRAR MODULO DE RESPALDO",
                            "description": "SUMINISTRAR MODULO DE RESPALDO",
                            "quantity": "2",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.applicability == "UNRESOLVED"
        assert row.review_required is True
        assert row.candidate_item_key is None
    finally:
        db.close()


def test_structure_only_artifact_does_not_create_scope_detail() -> None:
    tender_id = _create_tender("materializer structure only")
    document_id = _import_pdf(tender_id, "materializer-structure-only.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 1")
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "item_segments": [],
                "new_items": [],
                "_vision_runtime": {"task_type": "STRUCTURE_SCOPE"},
            },
            prompt_version="vision-structure-scope-2026-09-03-006",
        )

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.artifacts_unsupported >= 1
        assert result.persisted_count == 0
    finally:
        db.close()


def test_unsupported_historical_artifact_is_safe_noop() -> None:
    tender_id = _create_tender("materializer unsupported historical")
    document_id = _import_pdf(tender_id, "materializer-unsupported-historical.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 1")
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "LEGACY_DETAIL",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "1",
                            "raw_visible_text": "LEGACY ROW",
                            "description": "LEGACY ROW",
                            "quantity": "1",
                            "unit": "PIEZA",
                        }
                    ],
                }
            },
        )

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.artifacts_unsupported >= 1
        assert result.persisted_count == 0
    finally:
        db.close()


def test_zero_evidence_document_returns_no_evidence() -> None:
    tender_id = _create_tender("materializer zero evidence")
    document_id = _import_pdf(tender_id, "materializer-zero-evidence.pdf")

    db = SessionLocal()
    try:
        _seed_page(db, document_id, 1, "")
        _seed_page(db, document_id, 2, "")

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
        assert result.artifacts_seen == 0
        assert result.persisted_count == 0
    finally:
        db.close()


def test_unsupported_only_document_is_no_evidence_with_unsupported_counts() -> None:
    tender_id = _create_tender("materializer unsupported only")
    document_id = _import_pdf(tender_id, "materializer-unsupported-only.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 1")
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={"item_segments": [{"item_number": "1"}]},
            prompt_version="vision-structure-scope-2026-09-03-006",
        )
        _seed_ocr_result(db, page=page, engine="tesseract", text="TEXTO OCR")
        _seed_native_content(db, page=page, text="TEXTO NATIVE")

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
        assert result.artifacts_unsupported >= 2
        assert result.persisted_count == 0
    finally:
        db.close()


def test_mixed_supported_unsupported_and_no_detail_artifacts() -> None:
    tender_id = _create_tender("materializer mixed")
    document_id = _import_pdf(tender_id, "materializer-mixed.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, document_id, 1, "PARTIDA 2")
        page_b = _seed_page(db, document_id, 2, "PARTIDA 3")
        page_c = _seed_page(db, document_id, 3, "PARTIDA 4")
        page_d = _seed_page(db, document_id, 4, "PARTIDA 5")
        page_e = _seed_page(db, document_id, 5, "PARTIDA 6")

        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_a,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                            "description": "MODULO DE ENTRADAS ANALOGICAS",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_b,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 2,
                    "parsed_supply_rows": [
                        {
                            "scope_type": "DELIVERABLE",
                            "item_number": "3",
                            "raw_visible_text": "ENTREGAR REPORTE FINAL FIRMADO",
                            "description": "ENTREGAR REPORTE FINAL FIRMADO",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_c,
            structured_json={"_vision_runtime": {"task_type": "STRUCTURE_SCOPE"}, "item_segments": []},
            prompt_version="vision-structure-scope-2026-09-03-006",
        )
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_d,
            structured_json={
                "detail_transcription": {
                    "task_type": "LEGACY_DETAIL",
                    "source_page": 4,
                    "parsed_supply_rows": [
                        {"item_number": "5", "raw_visible_text": "LEGACY", "description": "LEGACY"}
                    ],
                }
            },
        )
        _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_e,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 5,
                    "parsed_supply_rows": [],
                }
            },
        )

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.artifacts_materialized == 2
        assert result.artifacts_no_details == 1
        assert result.artifacts_unsupported >= 2
        assert result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL or result.status == SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    finally:
        db.close()


def test_document_type_independence_for_materialization() -> None:
    tender_id = _create_tender("materializer document type independence")
    documents = [
        ("bases.pdf", "BIDDING_RULES"),
        ("anexo-tecnico.pdf", "TECHNICAL_SPECIFICATION"),
        ("anexo-comercial.pdf", "PRICING_SCHEDULE_CATALOG"),
    ]

    db = SessionLocal()
    try:
        seen_domains: list[str] = []
        for filename, classification in documents:
            document_id = _import_pdf(tender_id, filename)
            page = _seed_page(db, document_id, 1, "PARTIDA 2")
            _seed_classification(db, document_id, classification)
            page_result = _seed_vision_result(
                db,
                tender_id=tender_id,
                document_id=document_id,
                page=page,
                structured_json={
                    "detail_transcription": {
                        "task_type": "DETAIL_TRANSCRIPTION",
                        "source_page": 1,
                        "parsed_supply_rows": [
                            {
                                "item_number": "2",
                                "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                                "description": "MODULO DE ENTRADAS ANALOGICAS",
                                "quantity": "1",
                                "unit": "PIEZA",
                                "review_required": False,
                            }
                        ],
                    }
                },
            )
            _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id)
            result = _materialize(db, tender_id, document_id)
            assert result.persisted_count == 1
            row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
            assert row is not None
            seen_domains.append(row.domain)

        db.commit()
        assert seen_domains == ["SUPPLY", "SUPPLY", "SUPPLY"]
    finally:
        db.close()


def test_multi_document_additivity_and_replay_is_isolated_per_artifact() -> None:
    tender_id = _create_tender("materializer multi document additive")
    doc_a = _import_pdf(tender_id, "materializer-add-a.pdf")
    doc_b = _import_pdf(tender_id, "materializer-add-b.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, doc_a, 1, "PARTIDA 2")
        page_b = _seed_page(db, doc_b, 1, "PARTIDA 2")

        result_a = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=doc_a,
            page=page_a,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                            "description": "MODULO DE ENTRADAS ANALOGICAS",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        result_b = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=doc_b,
            page=page_b,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "scope_type": "DELIVERABLE",
                            "item_number": "2",
                            "raw_visible_text": "ENTREGAR REPORTE FINAL FIRMADO",
                            "description": "ENTREGAR REPORTE FINAL FIRMADO",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=doc_a, page=page_a, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=result_a.id)
        _seed_scope_segment(db, tender_id=tender_id, document_id=doc_b, page=page_b, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=result_b.id)

        materialize_document_scope_details(db, tender_id=tender_id, document_id=doc_a)
        materialize_document_scope_details(db, tender_id=tender_id, document_id=doc_b)
        db.commit()

        counts = db.execute(
            select(TenderScopeDetail.source_document_id, func.count(TenderScopeDetail.id))
            .where(TenderScopeDetail.tender_id == tender_id)
            .group_by(TenderScopeDetail.source_document_id)
        ).all()
        assert sorted(counts) == sorted([(doc_a, 1), (doc_b, 1)])

        materialize_document_scope_details(db, tender_id=tender_id, document_id=doc_a)
        db.commit()

        counts_after = db.execute(
            select(TenderScopeDetail.source_document_id, func.count(TenderScopeDetail.id))
            .where(TenderScopeDetail.tender_id == tender_id)
            .group_by(TenderScopeDetail.source_document_id)
        ).all()
        assert sorted(counts_after) == sorted([(doc_a, 1), (doc_b, 1)])
    finally:
        db.close()


def test_raw_quantity_unit_remain_unchanged() -> None:
    tender_id = _create_tender("materializer raw quantity")
    document_id = _import_pdf(tender_id, "materializer-raw-quantity.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (01 PZA.)",
                            "description": "MODULO DE ENTRADAS ANALOGICAS",
                            "quantity": "01",
                            "unit": "PZA.",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id)
        materialize_document_scope_details(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.quantity_raw == "01"
        assert row.unit_raw == "PZA."
    finally:
        db.close()


def test_same_lineage_selects_single_active_artifact() -> None:
    tender_id = _create_tender("materializer same lineage select active")
    document_id = _import_pdf(tender_id, "materializer-lineage-active.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        shared_image_sha = hashlib.sha256(f"shared-image|{document_id}|{page.id}".encode("utf-8")).hexdigest()
        detail_v1 = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "task_fingerprint": "fp-lineage-001",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "ROW-OLD",
                        "description": "ROW-OLD",
                        "quantity": "1",
                        "unit": "PIEZA",
                        "review_required": False,
                    }
                ],
            }
        }
        detail_v2 = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "task_fingerprint": "fp-lineage-001",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "ROW-NEW",
                        "description": "ROW-NEW",
                        "quantity": "1",
                        "unit": "PIEZA",
                        "review_required": False,
                    }
                ],
            }
        }
        older = _seed_vision_result(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=detail_v1, image_sha256=shared_image_sha)
        newer = _seed_vision_result(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=detail_v2, image_sha256=shared_image_sha)
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=newer.id)

        result = _materialize(db, tender_id, document_id)
        db.commit()

        by_status = {entry.source_artifact_key: entry.status for entry in result.artifact_results}
        assert by_status[f"vision-page-result:{newer.id}"] != SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED
        assert by_status[f"vision-page-result:{older.id}"] == SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED

        with SessionLocal() as verify_db:
            old_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{older.id}"))
            new_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{newer.id}"))
            assert old_count == 0
            assert new_count == 1
    finally:
        db.close()


def test_same_lineage_selection_shift_cleans_stale_rows() -> None:
    tender_id = _create_tender("materializer lineage shift stale cleanup")
    document_id = _import_pdf(tender_id, "materializer-lineage-shift.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        shared_image_sha = hashlib.sha256(f"shared-image|{document_id}|{page.id}".encode("utf-8")).hexdigest()
        older = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            image_sha256=shared_image_sha,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-lineage-002",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "ONLY-OLD",
                            "description": "ONLY-OLD",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=older.id)

        first = _materialize(db, tender_id, document_id)
        assert first.persisted_count == 1

        newer = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            image_sha256=shared_image_sha,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-lineage-002",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "ONLY-NEW",
                            "description": "ONLY-NEW",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=newer.id)

        second = _materialize(db, tender_id, document_id)
        db.commit()

        stale_status = {
            entry.source_artifact_key: entry.status
            for entry in second.artifact_results
        }
        assert stale_status[f"vision-page-result:{older.id}"] == SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED

        with SessionLocal() as verify_db:
            old_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{older.id}"))
            new_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{newer.id}"))
            assert old_count == 0
            assert new_count == 1
    finally:
        db.close()


def test_same_page_complementary_fingerprints_are_additive() -> None:
    tender_id = _create_tender("materializer complementary fingerprints")
    document_id = _import_pdf(tender_id, "materializer-complementary-fp.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        shared_image_sha = hashlib.sha256(f"shared-image|{document_id}|{page.id}".encode("utf-8")).hexdigest()
        first = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            image_sha256=shared_image_sha,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-a",
                    "source_page": 1,
                    "parsed_supply_rows": [{"item_number": "2", "raw_visible_text": "A", "description": "A", "quantity": "1", "unit": "PIEZA", "review_required": False}],
                }
            },
        )
        second = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            image_sha256=shared_image_sha,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-b",
                    "source_page": 1,
                    "parsed_supply_rows": [{"item_number": "2", "raw_visible_text": "B", "description": "B", "quantity": "1", "unit": "PIEZA", "review_required": False}],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=first.id)

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.persisted_count == 2
        with SessionLocal() as verify_db:
            first_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{first.id}"))
            second_count = verify_db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{second.id}"))
            assert first_count == 1
            assert second_count == 1
    finally:
        db.close()


def test_unique_structural_segment_inheritance_resolves_ownership() -> None:
    tender_id = _create_tender("materializer structural inheritance unique")
    document_id = _import_pdf(tender_id, "materializer-structural-inheritance.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 4, "PARTIDA 2")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-own-001",
                    "source_page": 4,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "SUMINISTRAR MODULO",
                            "description": "SUMINISTRAR MODULO",
                            "quantity": "2",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        segment = _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            candidate_item_key="2",
            tender_item_id=None,
            source_excerpt="PARTIDA 2",
            source_page_result_id=page_result.id,
            review_required=False,
        )
        _seed_page_structure_resolution(db, document_id=document_id, page=page, status="RESOLVED", review_required=False)

        result = _materialize(db, tender_id, document_id)
        db.commit()

        assert result.persisted_count == 1
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.applicability == "ITEM"
        assert row.scope_segment_id == segment.id
        assert row.review_required is False
    finally:
        db.close()


def test_structural_inheritance_fail_closed_on_multiple_or_review_segments() -> None:
    tender_id = _create_tender("materializer structural inheritance fail closed")
    document_id = _import_pdf(tender_id, "materializer-structural-fail-closed.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 5, "PARTIDA")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-own-002",
                    "source_page": 5,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "SUMINISTRAR EQUIPO",
                            "description": "SUMINISTRAR EQUIPO",
                            "quantity": "1",
                            "unit": "PZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="1", tender_item_id=None, source_excerpt="PARTIDA 1", source_page_result_id=page_result.id, review_required=False, sequence_index=0)
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id, review_required=False, sequence_index=1)
        _seed_page_structure_resolution(db, document_id=document_id, page=page, status="RESOLVED", review_required=False)

        _materialize(db, tender_id, document_id)

        # Re-seed a second page where unique segment exists but is review-required.
        page_review = _seed_page(db, document_id, 6, "PARTIDA")
        review_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_review,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-own-003",
                    "source_page": 6,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "SUMINISTRAR RESPALDO",
                            "description": "SUMINISTRAR RESPALDO",
                            "quantity": "1",
                            "unit": "PZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page_review, candidate_item_key="1", tender_item_id=None, source_excerpt="PARTIDA 1", source_page_result_id=review_result.id, review_required=True)
        _seed_page_structure_resolution(db, document_id=document_id, page=page_review, status="RESOLVED", review_required=False)

        _materialize(db, tender_id, document_id)
        db.commit()

        unresolved_rows = db.execute(
            select(TenderScopeDetail).where(
                TenderScopeDetail.source_artifact_key.in_(
                    [f"vision-page-result:{page_result.id}", f"vision-page-result:{review_result.id}"]
                )
            )
        ).scalars().all()
        assert unresolved_rows
        for row in unresolved_rows:
            assert row.applicability == "UNRESOLVED"
            assert row.review_required is True
    finally:
        db.close()


def test_explicit_conflict_remains_fail_closed_and_semantic_review_is_preserved() -> None:
    tender_id = _create_tender("materializer explicit conflict fail closed")
    document_id = _import_pdf(tender_id, "materializer-explicit-conflict.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 7, "PARTIDA")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-own-004",
                    "source_page": 7,
                    "parsed_supply_rows": [
                        {
                            "item_number": "99",
                            "raw_visible_text": "CONFLICT ROW",
                            "description": "CONFLICT ROW",
                            "quantity": "1",
                            "unit": "PZA",
                            "review_required": False,
                        },
                        {
                            "raw_visible_text": "SEMANTIC REVIEW ROW",
                            "description": "SEMANTIC REVIEW ROW",
                            "quantity": "1",
                            "unit": "PZA",
                            "review_required": True,
                        },
                    ],
                }
            },
        )
        segment = _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id, review_required=False)
        _seed_page_structure_resolution(db, document_id=document_id, page=page, status="RESOLVED", review_required=False)

        _materialize(db, tender_id, document_id)
        db.commit()

        rows = db.execute(
            select(TenderScopeDetail)
            .where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}")
            .order_by(TenderScopeDetail.source_locator.asc())
        ).scalars().all()
        assert len(rows) == 2

        explicit_conflict_row = rows[0]
        semantic_review_row = rows[1]

        assert explicit_conflict_row.applicability == "UNRESOLVED"
        assert explicit_conflict_row.scope_segment_id is None
        assert explicit_conflict_row.review_required is True

        assert semantic_review_row.scope_segment_id == segment.id
        assert semantic_review_row.applicability == "ITEM"
        assert semantic_review_row.review_required is True
    finally:
        db.close()


def test_structural_inheritance_fail_closed_on_resolution_review_or_unknown_page() -> None:
    tender_id = _create_tender("materializer inheritance resolution/unknown fail closed")
    document_id = _import_pdf(tender_id, "materializer-inheritance-resolution-unknown.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 8, "PARTIDA")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "task_fingerprint": "fp-own-005",
                    "source_page": 999,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "UNKNOWN PAGE ROW",
                            "description": "UNKNOWN PAGE ROW",
                            "quantity": "1",
                            "unit": "PZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="1", tender_item_id=None, source_excerpt="PARTIDA 1", source_page_result_id=page_result.id, review_required=False)
        _seed_page_structure_resolution(db, document_id=document_id, page=page, status="RESOLVED", review_required=True)

        _materialize(db, tender_id, document_id)
        db.commit()

        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == f"vision-page-result:{page_result.id}"))
        assert row is not None
        assert row.applicability == "UNRESOLVED"
        assert row.scope_segment_id is None
        assert row.review_required is True
    finally:
        db.close()


def test_no_provider_acquisition_path_called(monkeypatch) -> None:
    tender_id = _create_tender("materializer provider guard")
    document_id = _import_pdf(tender_id, "materializer-provider-guard.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        page_result = _seed_vision_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO DE ENTRADAS ANALOGICAS (1 PIEZA)",
                            "description": "MODULO DE ENTRADAS ANALOGICAS",
                            "quantity": "1",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        _seed_scope_segment(db, tender_id=tender_id, document_id=document_id, page=page, candidate_item_key="2", tender_item_id=None, source_excerpt="PARTIDA 2", source_page_result_id=page_result.id)

        def forbid_provider_acquisition(*args, **kwargs):
            raise AssertionError("provider acquisition must not run during persisted-evidence materialization")

        monkeypatch.setattr(ollama_vision_module, "analyze_vision_document", forbid_provider_acquisition)
        monkeypatch.setattr(ollama_vision_module, "analyze_vision_document_structure_only", forbid_provider_acquisition)
        monkeypatch.setattr(
            ollama_vision_module,
            "analyze_vision_document_structure_only_isolated",
            forbid_provider_acquisition,
        )
        monkeypatch.setattr(local_vision_module.OllamaVisionProvider, "analyze_scope_pages", forbid_provider_acquisition)
        monkeypatch.setattr(orchestrator_module, "_default_vision_executor", forbid_provider_acquisition)
        monkeypatch.setattr(orchestrator_module, "_default_ocr_executor", forbid_provider_acquisition)
        monkeypatch.setattr(ocr_module.TesseractOCRProvider, "recognize", forbid_provider_acquisition)
        monkeypatch.setattr(ocr_module.PaddleOCRProvider, "recognize", forbid_provider_acquisition)

        result = materialize_document_scope_details(db, tender_id=tender_id, document_id=document_id)
        db.commit()

        assert result.persisted_count == 1
    finally:
        db.close()
