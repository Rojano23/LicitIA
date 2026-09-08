from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import local_vision as local_vision_module
from app import ollama_scope_semantic_provider as semantic_provider_module
from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    Requirement,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
    TenderScopeQuantity,
)
from app.scope_quantities import ScopeQuantityCandidate, replace_scope_quantities_for_artifact
from app.scope_quantity_materializer import (
    SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
    SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED,
    SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_MATERIALIZATION_STATUS_UNSUPPORTED,
    materialize_scope_quantities_for_scope_detail,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-QUANTITY-MATERIALIZER-{uuid4()}"
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
        processing_time_ms=11,
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
        review_required=False,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=hashlib.sha256(
            f"scope-detail|{tender_id}|{document_id}|{page.id}|{source_artifact_key}|{source_locator}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _seed_stale_quantity(
    db,
    *,
    tender_id: str,
    scope_detail_id: str,
    document_id: str,
    page_id: str,
    source_method: str,
    source_artifact_key: str,
) -> None:
    replace_scope_quantities_for_artifact(
        db,
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=document_id,
        document_page_id=page_id,
        source_artifact_key=source_artifact_key,
        candidates=[
            ScopeQuantityCandidate(
                tender_id=tender_id,
                scope_detail_id=scope_detail_id,
                source_document_id=document_id,
                document_page_id=page_id,
                quantity_raw="1",
                quantity_value=1,
                relation="EXACT",
                unit_raw="PIEZA",
                measure_kind="COUNT",
                source_method=source_method,
                source_artifact_key=source_artifact_key,
                source_locator="page:1|detail_row:0",
                source_excerpt="EQUIPO DE RESPALDO (1 PIEZA)",
                review_required=False,
            )
        ],
    )


def _count_quantities(db, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeQuantity.id)).where(TenderScopeQuantity.scope_detail_id == scope_detail_id))
    return int(value or 0)


def test_missing_scope_detail_fails_closed_without_persistence() -> None:
    db = SessionLocal()
    try:
        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id="missing-scope-detail")
        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert result.persisted_count == 0
    finally:
        db.close()


def test_supported_vision_quantity_materializes_and_persists() -> None:
    tender_id = _create_tender("quantity materializer vision")
    document_id = _import_pdf(tender_id, "quantity-materializer-vision.pdf")

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
                        "raw_visible_text": "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS (2 PIEZAS)",
                        "description": "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS (2 PIEZAS)",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 1
        row = db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == scope_detail.id))
        assert row is not None
        assert row.quantity_value is not None
        assert row.quantity_value == 2
        assert row.quantity_raw == "2"
        assert row.unit_raw == "PIEZAS"
        assert row.measure_kind == "COUNT"
        assert row.source_locator == "page:1|detail_row:0"
        assert row.source_method == "VISION"
        assert row.source_artifact_key == f"vision-page-result:{page_result.id}"
        assert row.source_analysis_id == page_result.analysis_id
        assert row.source_page_result_id == page_result.id
        assert row.source_contract_version == "vision-detail-transcription-2026-08-31-001"
    finally:
        db.close()


def test_supported_zero_quantities_clears_exact_artifact_boundary() -> None:
    tender_id = _create_tender("quantity materializer clears boundary")
    document_id = _import_pdf(tender_id, "quantity-materializer-clears-boundary.pdf")

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
                        "raw_visible_text": "SUMINISTRAR MODULO SIN CANTIDAD EXPLICITA",
                        "description": "SUMINISTRAR MODULO",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="SUMINISTRAR MODULO SIN CANTIDAD EXPLICITA",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
        )
        _seed_stale_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
        )
        db.commit()

        assert _count_quantities(db, scope_detail.id) == 1
        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES
        assert _count_quantities(db, scope_detail.id) == 0
    finally:
        db.close()


def test_unsupported_source_method_is_non_destructive() -> None:
    tender_id = _create_tender("quantity materializer unsupported")
    document_id = _import_pdf(tender_id, "quantity-materializer-unsupported.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "SUMINISTRAR EQUIPO")
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt="SUMINISTRAR EQUIPO (1 PIEZA)",
        )
        _seed_stale_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_UNSUPPORTED
        assert _count_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_invalid_vision_lineage_is_non_destructive() -> None:
    tender_id = _create_tender("quantity materializer invalid lineage")
    document_id = _import_pdf(tender_id, "quantity-materializer-invalid-lineage.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key="vision-page-result:missing-page-result-id",
            source_locator="page:1|detail_row:0",
            source_excerpt="SUMINISTRAR EQUIPO (1 PIEZA)",
        )
        _seed_stale_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key="vision-page-result:missing-page-result-id",
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert _count_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_replay_is_idempotent_and_preserves_semantic_fingerprint() -> None:
    tender_id = _create_tender("quantity materializer replay")
    document_id = _import_pdf(tender_id, "quantity-materializer-replay.pdf")

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
                        "raw_visible_text": "SUMINISTRAR CABLE (12 METROS)",
                        "description": "SUMINISTRAR CABLE",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="SUMINISTRAR CABLE (12 METROS)",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
        )
        db.commit()

        first = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        fingerprints_first = {
            row.semantic_fingerprint
            for row in db.execute(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == scope_detail.id)).scalars()
        }

        second = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        fingerprints_second = {
            row.semantic_fingerprint
            for row in db.execute(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == scope_detail.id)).scalars()
        }
        db.commit()

        assert first.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED
        assert second.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED
        assert fingerprints_first == fingerprints_second
        assert len(fingerprints_second) == 1
    finally:
        db.close()


def test_other_artifacts_and_models_remain_unchanged() -> None:
    tender_id = _create_tender("quantity materializer isolation")
    document_id = _import_pdf(tender_id, "quantity-materializer-isolation.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 2")

        structured_target = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "TARGET ROW WITHOUT QUANTITY",
                        "description": "TARGET ROW",
                        "review_required": False,
                    }
                ],
            }
        }
        target_page_result = _seed_vision_lineage(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured_target,
        )

        structured_other = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "raw_visible_text": "OTHER ROW (3 PIEZAS)",
                        "description": "OTHER ROW",
                        "review_required": False,
                    }
                ],
            }
        }
        other_page_result = _seed_vision_lineage(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured_other,
        )

        target_scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{target_page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TARGET ROW WITHOUT QUANTITY",
            source_analysis_id=target_page_result.analysis_id,
            source_page_result_id=target_page_result.id,
        )
        other_scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{other_page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="OTHER ROW (3 PIEZAS)",
            source_analysis_id=other_page_result.analysis_id,
            source_page_result_id=other_page_result.id,
        )

        _seed_stale_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=target_scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{target_page_result.id}",
        )
        _seed_stale_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=other_scope_detail.id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{other_page_result.id}",
        )

        requirement = Requirement(
            tender_id=tender_id,
            canonical_key=f"REQ-{uuid4()}",
            canonical_text="REQUISITO DE PRUEBA",
        )
        db.add(requirement)
        db.flush()

        scope_detail_count_before = db.scalar(
            select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)
        )
        requirement_count_before = db.scalar(
            select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)
        )
        attribute_count_before = db.scalar(
            select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.tender_id == tender_id)
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=target_scope_detail.id)
        db.commit()

        scope_detail_count_after = db.scalar(
            select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)
        )
        requirement_count_after = db.scalar(
            select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)
        )
        attribute_count_after = db.scalar(
            select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.tender_id == tender_id)
        )

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES
        assert _count_quantities(db, target_scope_detail.id) == 0
        assert _count_quantities(db, other_scope_detail.id) == 1
        assert int(scope_detail_count_before or 0) == int(scope_detail_count_after or 0)
        assert int(requirement_count_before or 0) == int(requirement_count_after or 0)
        assert int(attribute_count_before or 0) == int(attribute_count_after or 0)
    finally:
        db.close()


def test_other_tender_isolated_from_target_materialization() -> None:
    tender_a = _create_tender("quantity materializer tender A")
    doc_a = _import_pdf(tender_a, "quantity-materializer-tender-a.pdf")
    tender_b = _create_tender("quantity materializer tender B")
    doc_b = _import_pdf(tender_b, "quantity-materializer-tender-b.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, doc_a, 1, "PARTIDA A")
        page_b = _seed_page(db, doc_b, 1, "PARTIDA B")

        structured_a = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "1",
                        "raw_visible_text": "TENDER A WITHOUT QUANTITY",
                        "description": "TENDER A",
                        "review_required": False,
                    }
                ],
            }
        }
        structured_b = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "1",
                        "raw_visible_text": "TENDER B (3 PIEZAS)",
                        "description": "TENDER B",
                        "review_required": False,
                    }
                ],
            }
        }

        page_result_a = _seed_vision_lineage(db, tender_id=tender_a, document_id=doc_a, page=page_a, structured_json=structured_a)
        page_result_b = _seed_vision_lineage(db, tender_id=tender_b, document_id=doc_b, page=page_b, structured_json=structured_b)

        scope_a = _seed_scope_detail(
            db,
            tender_id=tender_a,
            document_id=doc_a,
            page=page_a,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_a.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TENDER A WITHOUT QUANTITY",
            source_analysis_id=page_result_a.analysis_id,
            source_page_result_id=page_result_a.id,
        )
        scope_b = _seed_scope_detail(
            db,
            tender_id=tender_b,
            document_id=doc_b,
            page=page_b,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_b.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="TENDER B (3 PIEZAS)",
            source_analysis_id=page_result_b.analysis_id,
            source_page_result_id=page_result_b.id,
        )

        _seed_stale_quantity(
            db,
            tender_id=tender_a,
            scope_detail_id=scope_a.id,
            document_id=doc_a,
            page_id=page_a.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_a.id}",
        )
        _seed_stale_quantity(
            db,
            tender_id=tender_b,
            scope_detail_id=scope_b.id,
            document_id=doc_b,
            page_id=page_b.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result_b.id}",
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_a.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES
        assert _count_quantities(db, scope_a.id) == 0
        assert _count_quantities(db, scope_b.id) == 1
    finally:
        db.close()


def test_no_provider_or_semantic_execution_is_triggered(monkeypatch) -> None:
    tender_id = _create_tender("quantity materializer no providers")
    document_id = _import_pdf(tender_id, "quantity-materializer-no-providers.pdf")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("Provider execution should not be triggered during deterministic quantity materialization")

    monkeypatch.setattr(local_vision_module, "build_local_vision_provider", _raise_if_called)
    monkeypatch.setattr(semantic_provider_module, "run_ollama_scope_semantic_discovery", _raise_if_called)

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
                        "raw_visible_text": "SUMINISTRAR EQUIPO (1 PIEZA)",
                        "description": "SUMINISTRAR EQUIPO",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page, structured_json=structured)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator="page:1|detail_row:0",
            source_excerpt="SUMINISTRAR EQUIPO (1 PIEZA)",
            source_analysis_id=page_result.analysis_id,
            source_page_result_id=page_result.id,
        )
        db.commit()

        result = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail.id)
        db.commit()

        assert result.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 1
    finally:
        db.close()
