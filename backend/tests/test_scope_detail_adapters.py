from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    TenderDocument,
    TenderItem,
    TenderScopeDetail,
    TenderScopeSegment,
)
from app.scope_detail_adapters import (
    SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED,
    SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS,
    SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED,
    SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
    ScopeDetailEvidenceArtifact,
    adapt_and_persist_scope_detail_artifact,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-DETAIL-ADAPTER-{uuid4()}"
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


def _seed_vision_page_result(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    structured_json: dict,
) -> DocumentVisionPageResult:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status="COMPLETED",
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b-instruct",
        prompt_version="vision-structure-scope-2026-09-03-006",
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
        processing_time_ms=5,
    )
    db.add(page_result)
    db.flush()
    return page_result


def _seed_tender_item(db, *, tender_id: str, document_id: str, page_id: str, item_number: str) -> str:
    row = TenderItem(
        tender_id=tender_id,
        source_document_id=document_id,
        source_page=1,
        document_page_id=page_id,
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
        semantic_fingerprint=hashlib.sha256(f"item|{document_id}|{page_id}|{item_number}|{uuid4()}".encode("utf-8")).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row.id


def _seed_scope_segment(
    db,
    *,
    tender_id: str,
    document_id: str,
    page_id: str,
    candidate_item_key: str,
    source_page_result_id: str,
    tender_item_id: str | None,
    source_excerpt: str,
) -> TenderScopeSegment:
    row = TenderScopeSegment(
        tender_id=tender_id,
        source_document_id=document_id,
        document_page_id=page_id,
        page_number=1,
        tender_item_id=tender_item_id,
        candidate_item_key=candidate_item_key,
        candidate_item_raw_label=candidate_item_key,
        sequence_index=0,
        scope_domain=None,
        source_method="VISION",
        link_reason="EXPLICIT_ITEM_START",
        source_locator="page:1|segment:0",
        source_excerpt=source_excerpt,
        source_analysis_id=None,
        source_page_result_id=source_page_result_id,
        confidence=None,
        review_required=False,
        semantic_fingerprint=hashlib.sha256(
            f"segment|{document_id}|{page_id}|{candidate_item_key}|{source_page_result_id}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _build_vision_artifact(*, tender_id: str, document_id: str, page_id: str, page_result: DocumentVisionPageResult) -> ScopeDetailEvidenceArtifact:
    return ScopeDetailEvidenceArtifact(
        tender_id=tender_id,
        source_document_id=document_id,
        document_page_id=page_id,
        source_method="VISION",
        source_artifact_key=f"vision-page-result:{page_result.id}",
        source_contract_version=None,
        source_locator=f"page:{page_result.page_number}",
        source_analysis_id=page_result.analysis_id,
        source_page_result_id=page_result.id,
        payload=page_result.structured_json,
    )


def test_vision_supply_row_maps_to_supply_and_persists_raw_quantity_unit() -> None:
    tender_id = _create_tender("adapter supply row")
    document_id = _import_pdf(tender_id, "adapter-supply.pdf")

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
        page_result = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured,
        )
        tender_item_id = _seed_tender_item(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            item_number="2",
        )
        segment = _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            candidate_item_key="2",
            source_page_result_id=page_result.id,
            tender_item_id=tender_item_id,
            source_excerpt="PARTIDA 2",
        )

        artifact = _build_vision_artifact(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            page_result=page_result,
        )
        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED
        assert result.persisted_count == 1

        row = db.scalar(
            select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key)
        )
        assert row is not None
        assert row.domain == "SUPPLY"
        assert row.source_method == "VISION"
        assert row.quantity_raw == "1"
        assert row.unit_raw == "PIEZA"
        assert row.scope_segment_id == segment.id
        assert row.tender_item_id == tender_item_id
        assert row.candidate_item_key == "2"
        assert row.source_contract_version == "vision-detail-transcription-2026-08-31-001"
    finally:
        db.close()


def test_vision_deliverable_maps_to_deliverable_not_supply() -> None:
    tender_id = _create_tender("adapter deliverable row")
    document_id = _import_pdf(tender_id, "adapter-deliverable.pdf")

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
                        "scope_type": "DELIVERABLE",
                        "raw_visible_text": "ENTREGAR REPORTE FINAL FIRMADO",
                        "description": "ENTREGAR REPORTE FINAL FIRMADO",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured,
        )
        _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            candidate_item_key="2",
            source_page_result_id=page_result.id,
            tender_item_id=None,
            source_excerpt="PARTIDA 2",
        )

        artifact = _build_vision_artifact(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            page_result=page_result,
        )
        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key))
        assert row is not None
        assert row.domain == "DELIVERABLE"
    finally:
        db.close()


def test_unresolved_ownership_retains_candidate_as_review_required_without_guessing_item() -> None:
    tender_id = _create_tender("adapter unresolved ownership")
    document_id = _import_pdf(tender_id, "adapter-unresolved.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto")
        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "99",
                        "raw_visible_text": "SUMINISTRAR MODULO DE RESPALDO",
                        "description": "SUMINISTRAR MODULO DE RESPALDO",
                        "quantity": "2",
                        "unit": "PIEZA",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured,
        )
        artifact = _build_vision_artifact(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            page_result=page_result,
        )

        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED
        row = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key))
        assert row is not None
        assert row.applicability == "UNRESOLVED"
        assert row.review_required is True
        assert row.scope_segment_id is None
        assert row.tender_item_id is None
        assert row.candidate_item_key is None
    finally:
        db.close()


def test_no_execution_detail_results_in_no_details_and_no_persistence() -> None:
    tender_id = _create_tender("adapter no details")
    document_id = _import_pdf(tender_id, "adapter-no-details.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto")
        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "raw_visible_text": "",
                        "description": "",
                        "review_required": False,
                    }
                ],
            }
        }
        page_result = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json=structured,
        )
        artifact = _build_vision_artifact(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            page_result=page_result,
        )

        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS
        count = db.scalar(
            select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key)
        )
        assert count == 0
    finally:
        db.close()


def test_unsupported_payload_is_safe_noop_without_fake_rows() -> None:
    tender_id = _create_tender("adapter unsupported")
    document_id = _import_pdf(tender_id, "adapter-unsupported.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto")
        artifact = ScopeDetailEvidenceArtifact(
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:unsupported:{page.id}",
            payload={"unexpected": True},
        )
        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED
        assert result.persisted_count == 0
        count = db.scalar(
            select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key)
        )
        assert count == 0
    finally:
        db.close()


def test_document_type_independence_for_same_vision_evidence() -> None:
    tender_id = _create_tender("adapter document type independence")

    db = SessionLocal()
    try:
        docs = [
            ("bases-doc.pdf", "BIDDING_RULES"),
            ("anexo-tecnico-doc.pdf", "TECHNICAL_SPECIFICATION"),
            ("anexo-comercial-doc.pdf", "PRICING_SCHEDULE_CATALOG"),
        ]
        artifact_keys: list[str] = []

        for filename, classification in docs:
            document_id = _import_pdf(tender_id, filename)
            page = _seed_page(db, document_id, 1, "PARTIDA 2")
            _seed_classification(db, document_id, classification)
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
            page_result = _seed_vision_page_result(
                db,
                tender_id=tender_id,
                document_id=document_id,
                page=page,
                structured_json=structured,
            )
            _seed_scope_segment(
                db,
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                candidate_item_key="2",
                source_page_result_id=page_result.id,
                tender_item_id=None,
                source_excerpt="PARTIDA 2",
            )
            artifact = _build_vision_artifact(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                page_result=page_result,
            )
            artifact_keys.append(artifact.source_artifact_key)
            result = adapt_and_persist_scope_detail_artifact(db, artifact)
            assert result.persisted_count == 1
            assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED

        db.commit()

        domains = db.execute(
            select(TenderScopeDetail.domain)
            .where(TenderScopeDetail.source_artifact_key.in_(artifact_keys))
            .order_by(TenderScopeDetail.domain.asc())
        ).scalars().all()
        assert domains == ["SUPPLY", "SUPPLY", "SUPPLY"]
    finally:
        db.close()


def test_multi_document_additivity_and_artifact_scoped_replacement_with_adapter() -> None:
    tender_id = _create_tender("adapter multi document")
    technical_doc = _import_pdf(tender_id, "adapter-tech.pdf")
    commercial_doc = _import_pdf(tender_id, "adapter-commercial.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, technical_doc, 1, "PARTIDA 2")
        page_b = _seed_page(db, commercial_doc, 1, "PARTIDA 2")

        structured_supply = {
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
        structured_deliverable = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "item_number": "2",
                        "scope_type": "DELIVERABLE",
                        "raw_visible_text": "ENTREGAR REPORTE DE PRUEBAS",
                        "description": "ENTREGAR REPORTE DE PRUEBAS",
                        "review_required": False,
                    }
                ],
            }
        }

        page_result_a = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=technical_doc,
            page=page_a,
            structured_json=structured_supply,
        )
        page_result_b = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=commercial_doc,
            page=page_b,
            structured_json=structured_deliverable,
        )

        _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=technical_doc,
            page_id=page_a.id,
            candidate_item_key="2",
            source_page_result_id=page_result_a.id,
            tender_item_id=None,
            source_excerpt="PARTIDA 2",
        )
        _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=commercial_doc,
            page_id=page_b.id,
            candidate_item_key="2",
            source_page_result_id=page_result_b.id,
            tender_item_id=None,
            source_excerpt="PARTIDA 2",
        )

        artifact_a = _build_vision_artifact(
            tender_id=tender_id,
            document_id=technical_doc,
            page_id=page_a.id,
            page_result=page_result_a,
        )
        artifact_b = _build_vision_artifact(
            tender_id=tender_id,
            document_id=commercial_doc,
            page_id=page_b.id,
            page_result=page_result_b,
        )

        result_a = adapt_and_persist_scope_detail_artifact(db, artifact_a)
        result_b = adapt_and_persist_scope_detail_artifact(db, artifact_b)
        assert result_a.persisted_count == 1
        assert result_b.persisted_count == 1

        # Reprocess technical artifact only; this must not remove commercial details.
        artifact_a_updated = replace(
            artifact_a,
            payload={
                "detail_transcription": {
                    "task_type": "DETAIL_TRANSCRIPTION",
                    "source_page": 1,
                    "parsed_supply_rows": [
                        {
                            "item_number": "2",
                            "raw_visible_text": "MODULO ACTUALIZADO (2 PIEZA)",
                            "description": "MODULO ACTUALIZADO",
                            "quantity": "2",
                            "unit": "PIEZA",
                            "review_required": False,
                        }
                    ],
                }
            },
        )
        adapt_and_persist_scope_detail_artifact(db, artifact_a_updated)
        db.commit()

        counts = db.execute(
            select(TenderScopeDetail.source_document_id, func.count(TenderScopeDetail.id))
            .where(TenderScopeDetail.tender_id == tender_id)
            .group_by(TenderScopeDetail.source_document_id)
        ).all()
        assert sorted(counts) == sorted([(technical_doc, 1), (commercial_doc, 1)])

        domains = db.execute(
            select(TenderScopeDetail.source_document_id, TenderScopeDetail.domain)
            .where(TenderScopeDetail.tender_id == tender_id)
        ).all()
        assert sorted(domains) == sorted([(technical_doc, "SUPPLY"), (commercial_doc, "DELIVERABLE")])

        tech_row = db.scalar(
            select(TenderScopeDetail).where(
                TenderScopeDetail.tender_id == tender_id,
                TenderScopeDetail.source_document_id == technical_doc,
            )
        )
        assert tech_row is not None
        assert tech_row.quantity_raw == "2"
    finally:
        db.close()


def test_ownership_resolution_priority_segment_then_tender_item_then_candidate_key() -> None:
    tender_id = _create_tender("adapter ownership priority")
    document_id = _import_pdf(tender_id, "adapter-ownership-priority.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "PARTIDA 7")
        item_id = _seed_tender_item(db, tender_id=tender_id, document_id=document_id, page_id=page.id, item_number="7")
        page_result_seed = _seed_vision_page_result(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            structured_json={"detail_transcription": {"task_type": "DETAIL_TRANSCRIPTION", "source_page": 1, "parsed_supply_rows": []}},
        )
        segment = _seed_scope_segment(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            candidate_item_key="7",
            source_page_result_id=page_result_seed.id,
            tender_item_id=item_id,
            source_excerpt="PARTIDA 7",
        )

        structured = {
            "detail_transcription": {
                "task_type": "DETAIL_TRANSCRIPTION",
                "source_page": 1,
                "parsed_supply_rows": [
                    {
                        "scope_segment_id": segment.id,
                        "raw_visible_text": "ROW SEGMENT",
                        "description": "ROW SEGMENT",
                        "quantity": "1",
                        "unit": "PIEZA",
                    },
                    {
                        "tender_item_id": item_id,
                        "raw_visible_text": "ROW ITEM",
                        "description": "ROW ITEM",
                        "quantity": "1",
                        "unit": "PIEZA",
                    },
                    {
                        "item_number": "7",
                        "raw_visible_text": "ROW CANDIDATE",
                        "description": "ROW CANDIDATE",
                        "quantity": "1",
                        "unit": "PIEZA",
                    },
                ],
            }
        }
        page_result_seed.structured_json = structured
        db.flush()

        artifact = _build_vision_artifact(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            page_result=page_result_seed,
        )
        result = adapt_and_persist_scope_detail_artifact(db, artifact)
        db.commit()

        assert result.status == SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED
        rows = db.execute(
            select(TenderScopeDetail)
            .where(TenderScopeDetail.source_artifact_key == artifact.source_artifact_key)
            .order_by(TenderScopeDetail.description.asc())
        ).scalars().all()
        assert len(rows) == 3
        for row in rows:
            assert row.scope_segment_id == segment.id
            assert row.tender_item_id == item_id
            assert row.candidate_item_key == "7"
    finally:
        db.close()


def test_neutral_domain_has_no_provider_specific_parsing_terms() -> None:
    scope_details_file = Path(__file__).resolve().parents[1] / "app" / "scope_details.py"
    content = scope_details_file.read_text(encoding="utf-8")
    forbidden = ("Ollama", "Qwen", "detail_transcription", "parsed_supply_rows", "structured_json")
    for term in forbidden:
        assert term not in content


def test_vision_adapter_depends_on_neutral_scope_detail_contract() -> None:
    adapter_file = Path(__file__).resolve().parents[1] / "app" / "vision_scope_detail_adapter.py"
    content = adapter_file.read_text(encoding="utf-8")
    assert "from app.scope_details import" in content
    assert "ScopeDetailCandidate" in content
