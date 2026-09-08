from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import document_structure_orchestrator as orchestrator_module
from app import local_vision as local_vision_module
from app import ocr as ocr_module
from app import ollama_scope_semantic_provider as semantic_provider_module
from app import ollama_vision as ollama_vision_module
from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    PageOcrResult,
    Requirement,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
)
from app.scope_attribute_materializer import (
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_UNSUPPORTED,
    materialize_scope_attributes_for_scope_detail,
)
from app.scope_attributes import ScopeAttributeCandidate, replace_scope_attributes_for_artifact

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-ATTRIBUTE-MATERIALIZER-{uuid4()}"
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


def _seed_page(db, document_id: str, page_number: int, text: str) -> DocumentPage:
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


def _seed_vision_lineage(db, *, tender_id: str, document_id: str, page: DocumentPage, structured_json: dict) -> DocumentVisionPageResult:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status="COMPLETED",
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b-instruct",
        prompt_version="vision-detail-transcription-2026-08-31-001",
        input_fingerprint_sha256=hashlib.sha256(f"analysis|{document_id}|{page.id}|{uuid4()}".encode("utf-8")).hexdigest(),
    )
    db.add(analysis)
    db.flush()

    page_result = DocumentVisionPageResult(
        analysis_id=analysis.id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=hashlib.sha256(f"image|{page.id}|{uuid4()}".encode("utf-8")).hexdigest(),
        status="COMPLETED",
        raw_response_text=None,
        structured_json=structured_json,
        extracted_markdown=None,
        extracted_plain_text=None,
        warnings=[],
        processing_time_ms=7,
    )
    db.add(page_result)
    db.flush()
    return page_result


def _seed_scope_detail(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    source_method: str,
    source_artifact_key: str,
    source_locator: str,
    source_excerpt: str,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
    review_required: bool = False,
) -> TenderScopeDetail:
    row = TenderScopeDetail(
        tender_id=tender_id,
        tender_item_id=None,
        scope_segment_id=None,
        candidate_item_key=None,
        source_document_id=document_id,
        document_page_id=page.id,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        domain="SUPPLY",
        detail_type="DETAIL",
        description=source_excerpt,
        normalized_label=None,
        applicability="UNRESOLVED",
        source_method=source_method,
        source_artifact_key=source_artifact_key,
        source_contract_version="vision-detail-transcription-2026-08-31-001" if source_method == "VISION" else None,
        source_locator=source_locator,
        source_excerpt=source_excerpt,
        confidence=None,
        review_required=review_required,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=hashlib.sha256(
            f"scope-detail|{tender_id}|{document_id}|{page.id}|{source_artifact_key}|{source_locator}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _seed_stale_attribute(
    db,
    *,
    tender_id: str,
    scope_detail_id: str,
    document_id: str,
    page_id: str,
    source_method: str,
    source_artifact_key: str,
) -> None:
    replace_scope_attributes_for_artifact(
        db,
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=document_id,
        document_page_id=page_id,
        source_artifact_key=source_artifact_key,
        candidates=[
            ScopeAttributeCandidate(
                tender_id=tender_id,
                scope_detail_id=scope_detail_id,
                source_document_id=document_id,
                document_page_id=page_id,
                source_method=source_method,
                source_artifact_key=source_artifact_key,
                source_locator="page:1|detail_row:0|attr:model",
                source_excerpt="TRANSMISOR MARCA YOKOGAWA MODELO YTA1100",
                attribute_name="model",
                value_raw="YTA1100",
                review_required=False,
            )
        ],
    )


def _count_attrs(db, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.scope_detail_id == scope_detail_id))
    return int(value or 0)


def test_missing_scope_detail_fails_closed_without_persistence() -> None:
    db = SessionLocal()
    try:
        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id="missing-scope-detail")
        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert result.persisted_count == 0
    finally:
        db.close()


def test_unsupported_native_artifact_is_non_destructive() -> None:
    tender_id = _create_tender("attr materializer native unsupported")
    document_id = _import_pdf(tender_id, "attr-materializer-native-unsupported.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TRANSMISOR MARCA YOKOGAWA")
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-40",
            source_excerpt="TRANSMISOR MARCA YOKOGAWA",
            review_required=False,
        )
        _seed_stale_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
        )
        db.commit()

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_UNSUPPORTED
        assert _count_attrs(db, scope_detail.id) == 1
    finally:
        db.close()


def test_unsupported_ocr_artifact_is_non_destructive() -> None:
    tender_id = _create_tender("attr materializer ocr unsupported")
    document_id = _import_pdf(tender_id, "attr-materializer-ocr-unsupported.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        ocr_row = PageOcrResult(
            document_page_id=page.id,
            engine="tesseract",
            engine_version="ocr-1",
            language="es+en",
            text="EQUIPO MODELO YTA1100",
            status="OCR_TEXT_EXTRACTED",
            confidence=0.95,
            processing_time_ms=10,
            warnings=None,
            scope="FULL_PAGE",
            region_id=None,
        )
        db.add(ocr_row)
        db.flush()

        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="OCR",
            source_artifact_key=f"PageOcrResult:{ocr_row.id}",
            source_locator="page:1|ocr_scope:FULL_PAGE",
            source_excerpt="EQUIPO MODELO YTA1100",
            review_required=False,
        )
        _seed_stale_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="OCR",
            source_artifact_key=f"PageOcrResult:{ocr_row.id}",
        )
        db.commit()

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_UNSUPPORTED
        assert _count_attrs(db, scope_detail.id) == 1
    finally:
        db.close()


def test_supported_zero_attributes_clears_only_same_boundary() -> None:
    tender_id = _create_tender("attr materializer no attributes")
    document_id = _import_pdf(tender_id, "attr-materializer-no-attributes.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 1")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR INDUSTRIAL",
                            "description": "TRANSMISOR INDUSTRIAL",
                            "review_required": False,
                        }
                    ],
                }
            },
        )

        scope_detail_a = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR INDUSTRIAL",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )
        scope_detail_b = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR INDUSTRIAL",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        _seed_stale_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail_a.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
        )
        _seed_stale_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail_b.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
        )
        db.commit()

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail_a.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_NO_ATTRIBUTES
        assert _count_attrs(db, scope_detail_a.id) == 0
        assert _count_attrs(db, scope_detail_b.id) == 1
    finally:
        db.close()


def test_supported_single_attribute_materializes() -> None:
    tender_id = _create_tender("attr materializer single")
    document_id = _import_pdf(tender_id, "attr-materializer-single.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR MARCA YOKOGAWA",
                            "description": "TRANSMISOR MARCA YOKOGAWA",
                            "brand": "YOKOGAWA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR MARCA YOKOGAWA",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 1
        persisted = db.execute(
            select(TenderScopeAttribute)
            .where(TenderScopeAttribute.scope_detail_id == scope_detail.id)
            .order_by(TenderScopeAttribute.attribute_name.asc())
        ).scalars().all()
        assert [row.attribute_name for row in persisted] == ["brand"]
        assert persisted[0].value_raw == "YOKOGAWA"
    finally:
        db.close()


def test_supported_multiple_attributes_materialize_from_same_excerpt() -> None:
    tender_id = _create_tender("attr materializer multiple")
    document_id = _import_pdf(tender_id, "attr-materializer-multiple.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "description": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "brand": "YOKOGAWA",
                            "model": "YTA1100",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR YOKOGAWA MODELO YTA1100",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 2
        rows = db.execute(
            select(TenderScopeAttribute.attribute_name, TenderScopeAttribute.source_excerpt)
            .where(TenderScopeAttribute.scope_detail_id == scope_detail.id)
            .order_by(TenderScopeAttribute.attribute_name.asc())
        ).all()
        assert [name for name, _ in rows] == ["brand", "model"]
        assert all(excerpt == "TRANSMISOR YOKOGAWA MODELO YTA1100" for _, excerpt in rows)
    finally:
        db.close()


def test_invalid_evidence_is_non_destructive() -> None:
    tender_id = _create_tender("attr materializer invalid evidence")
    document_id = _import_pdf(tender_id, "attr-materializer-invalid-evidence.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR MARCA YOKOGAWA",
                            "description": "TRANSMISOR MARCA YOKOGAWA",
                            "model": "YTA1100",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR MARCA YOKOGAWA",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )
        _seed_stale_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
        )
        db.commit()

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert _count_attrs(db, scope_detail.id) == 1
    finally:
        db.close()


def test_replay_is_semantically_idempotent() -> None:
    tender_id = _create_tender("attr materializer idempotent")
    document_id = _import_pdf(tender_id, "attr-materializer-idempotent.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "description": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "brand": "YOKOGAWA",
                            "model": "YTA1100",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR YOKOGAWA MODELO YTA1100",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        first = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.flush()
        first_state = db.execute(
            select(
                TenderScopeAttribute.attribute_name,
                TenderScopeAttribute.value_raw,
                TenderScopeAttribute.semantic_fingerprint,
            ).where(TenderScopeAttribute.scope_detail_id == scope_detail.id)
        ).all()

        second = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.flush()
        second_state = db.execute(
            select(
                TenderScopeAttribute.attribute_name,
                TenderScopeAttribute.value_raw,
                TenderScopeAttribute.semantic_fingerprint,
            ).where(TenderScopeAttribute.scope_detail_id == scope_detail.id)
        ).all()
        db.commit()

        assert first.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED
        assert second.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED
        assert first_state == second_state
    finally:
        db.close()


def test_cross_tender_lineage_mismatch_fails_closed_non_destructive() -> None:
    tender_a = _create_tender("attr materializer cross tender A")
    tender_b = _create_tender("attr materializer cross tender B")
    doc_a = _import_pdf(tender_a, "attr-materializer-cross-a.pdf")
    doc_b = _import_pdf(tender_b, "attr-materializer-cross-b.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, doc_a, 1, "")
        page_b = _seed_page(db, doc_b, 1, "")
        page_result_b = _seed_vision_lineage(
            db,
            tender_id=tender_b,
            document_id=doc_b,
            page=page_b,
            structured_json={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "raw_visible_text": "TRANSMISOR YOKOGAWA",
                            "description": "TRANSMISOR YOKOGAWA",
                            "brand": "YOKOGAWA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )

        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_a,
            document_id=doc_a,
            page=page_a,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_b.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR YOKOGAWA",
            source_analysis_id=None,
            source_page_result_id=None,
            review_required=False,
        )
        _seed_stale_attribute(
            db,
            tender_id=tender_a,
            scope_detail_id=scope_detail.id,
            document_id=doc_a,
            page_id=page_a.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_b.id}",
        )
        db.commit()

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert _count_attrs(db, scope_detail.id) == 1
    finally:
        db.close()


def test_no_scope_detail_or_requirement_mutation() -> None:
    tender_id = _create_tender("attr materializer no mutations")
    document_id = _import_pdf(tender_id, "attr-materializer-no-mutation.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR YOKOGAWA",
                            "description": "TRANSMISOR YOKOGAWA",
                            "brand": "YOKOGAWA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR YOKOGAWA",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        before = (
            scope_detail.description,
            scope_detail.domain,
            scope_detail.applicability,
            scope_detail.review_required,
            scope_detail.source_method,
            scope_detail.source_artifact_key,
            scope_detail.source_locator,
            scope_detail.source_excerpt,
            scope_detail.source_analysis_id,
            scope_detail.source_page_result_id,
        )
        requirements_before = int(db.scalar(select(func.count(Requirement.id))) or 0)

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        refreshed = db.get(TenderScopeDetail, scope_detail.id)
        assert refreshed is not None
        after = (
            refreshed.description,
            refreshed.domain,
            refreshed.applicability,
            refreshed.review_required,
            refreshed.source_method,
            refreshed.source_artifact_key,
            refreshed.source_locator,
            refreshed.source_excerpt,
            refreshed.source_analysis_id,
            refreshed.source_page_result_id,
        )
        requirements_after = int(db.scalar(select(func.count(Requirement.id))) or 0)

        assert result.status in {
            SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED,
            SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
        }
        assert before == after
        assert requirements_before == requirements_after
    finally:
        db.close()


def test_zero_provider_acquisition_path_called(monkeypatch) -> None:
    tender_id = _create_tender("attr materializer provider guard")
    document_id = _import_pdf(tender_id, "attr-materializer-provider-guard.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "")
        page_result = _seed_vision_lineage(
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
                            "raw_visible_text": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "description": "TRANSMISOR YOKOGAWA MODELO YTA1100",
                            "brand": "YOKOGAWA",
                            "model": "YTA1100",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TRANSMISOR YOKOGAWA MODELO YTA1100",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
            review_required=False,
        )

        def forbid_provider_acquisition(*args, **kwargs):
            raise AssertionError("provider acquisition must not run during persisted-evidence attribute materialization")

        monkeypatch.setattr(semantic_provider_module, "discover_scope_semantics", forbid_provider_acquisition)
        monkeypatch.setattr(ollama_vision_module, "analyze_vision_document", forbid_provider_acquisition)
        monkeypatch.setattr(ollama_vision_module, "analyze_vision_document_structure_only", forbid_provider_acquisition)
        monkeypatch.setattr(ollama_vision_module, "analyze_vision_document_structure_only_isolated", forbid_provider_acquisition)
        monkeypatch.setattr(local_vision_module.OllamaVisionProvider, "analyze_scope_pages", forbid_provider_acquisition)
        monkeypatch.setattr(orchestrator_module, "_default_vision_executor", forbid_provider_acquisition)
        monkeypatch.setattr(orchestrator_module, "_default_ocr_executor", forbid_provider_acquisition)
        monkeypatch.setattr(ocr_module.TesseractOCRProvider, "recognize", forbid_provider_acquisition)
        monkeypatch.setattr(ocr_module.PaddleOCRProvider, "recognize", forbid_provider_acquisition)

        result = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 2
    finally:
        db.close()
