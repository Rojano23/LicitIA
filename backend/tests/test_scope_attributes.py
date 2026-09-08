from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    Requirement,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
)
from app.scope_attributes import (
    SCOPE_ATTRIBUTE_RELATION_EXACT,
    SCOPE_ATTRIBUTE_RELATION_RANGE,
    ScopeAttributeCandidate,
    replace_scope_attributes_for_artifact,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-ATTR-{uuid4()}"
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


def _seed_scope_detail(
    db,
    *,
    tender_id: str,
    document_id: str,
    page_id: str,
    source_method: str = "NATIVE",
    source_artifact_key: str | None = None,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
) -> TenderScopeDetail:
    row = TenderScopeDetail(
        tender_id=tender_id,
        source_document_id=document_id,
        document_page_id=page_id,
        scope_segment_id=None,
        tender_item_id=None,
        candidate_item_key=None,
        domain="SUPPLY",
        detail_type="EQUIPMENT",
        description="Supply pressure transmitter",
        normalized_label="pressure_transmitter_supply",
        applicability="TENDER_WIDE",
        source_method=source_method,
        source_artifact_key=source_artifact_key or f"native-page:{page_id}:scope",
        source_contract_version="scope-semantic-discovery-2026-09-08-004",
        source_locator="page:1|block:1",
        source_excerpt="Supply pressure transmitter",
        confidence=0.9,
        review_required=False,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=f"scope-{uuid4().hex}",
    )
    db.add(row)
    db.flush()
    return row


def _seed_vision_lineage(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
) -> tuple[DocumentVisionAnalysis, DocumentVisionPageResult]:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status="COMPLETED",
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b",
        prompt_version="vision-detail-transcription-2026-08-31-001",
        input_fingerprint_sha256=f"analysis-{uuid4().hex}",
    )
    db.add(analysis)
    db.flush()

    page_result = DocumentVisionPageResult(
        analysis_id=analysis.id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=f"image-{uuid4().hex}",
        status="COMPLETED",
        raw_response_text=None,
        structured_json={"ok": True},
        extracted_markdown=None,
        extracted_plain_text=None,
        warnings=[],
        processing_time_ms=1,
    )
    db.add(page_result)
    db.flush()
    return analysis, page_result


def _candidate(
    *,
    tender_id: str,
    scope_detail_id: str,
    document_id: str,
    page_id: str,
    artifact_key: str,
    attribute_name: str,
    value_raw: str,
    source_method: str = "NATIVE",
    unit_raw: str | None = None,
    relation: str | None = None,
    confidence: float | None = None,
    review_required: bool = True,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
) -> ScopeAttributeCandidate:
    return ScopeAttributeCandidate(
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=document_id,
        document_page_id=page_id,
        source_method=source_method,
        source_artifact_key=artifact_key,
        source_locator="page:1|block:2",
        source_excerpt="output 4-20 mA HART, SS316 body and accuracy +/-0.075%",
        attribute_name=attribute_name,
        attribute_label_raw=None,
        normalized_name=None,
        value_raw=value_raw,
        unit_raw=unit_raw,
        relation=relation,
        confidence=confidence,
        review_required=review_required,
        source_contract_version="scope-attribute-contract-001",
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )


def _count_scope_attributes(db, tender_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.tender_id == tender_id)
        )
        or 0
    )


def test_valid_single_attribute_persists() -> None:
    tender_id = _create_tender("attr single")
    document_id = _import_pdf(tender_id, "attr-single.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                    review_required=True,
                )
            ],
        )
        db.commit()

        assert len(rows) == 1
        persisted = db.get(TenderScopeAttribute, rows[0].id)
        assert persisted is not None
        assert persisted.attribute_name == "signal"
        assert persisted.value_raw == "4-20 mA HART"
    finally:
        db.close()


def test_source_method_allowlist_accepts_native_ocr_vision() -> None:
    tender_id = _create_tender("attr source method allowlist")
    document_id = _import_pdf(tender_id, "attr-source-method-allowlist.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)

        for method in ["NATIVE", "OCR", "VISION"]:
            artifact = f"{method.lower()}:{page.id}:allowlist"
            rows = replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[
                    _candidate(
                        tender_id=tender_id,
                        scope_detail_id=detail.id,
                        document_id=document_id,
                        page_id=page.id,
                        artifact_key=artifact,
                        source_method=method,
                        attribute_name="signal",
                        value_raw="4-20 mA HART",
                    )
                ],
            )
            assert len(rows) == 1
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("invalid_source_method", ["QWEN", "UNKNOWN_PROVIDER"])
def test_source_method_rejects_non_evidence_provider_values(invalid_source_method: str) -> None:
    tender_id = _create_tender(f"attr source method reject {invalid_source_method}")
    document_id = _import_pdf(tender_id, f"attr-source-method-reject-{invalid_source_method}.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"invalid:{page.id}:source-method"
        candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            artifact_key=artifact,
            source_method=invalid_source_method,
            attribute_name="signal",
            value_raw="4-20 mA HART",
        )

        with pytest.raises(ValueError, match="Unsupported source_method"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[candidate],
            )
    finally:
        db.close()


def test_review_required_defaults_true_and_explicit_false_is_preserved() -> None:
    tender_id = _create_tender("attr review required defaults")
    document_id = _import_pdf(tender_id, "attr-review-required-defaults.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)

        artifact_default = f"native:{page.id}:review-default"
        rows_default = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_default,
            candidates=[
                ScopeAttributeCandidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    source_document_id=document_id,
                    document_page_id=page.id,
                    source_method="NATIVE",
                    source_artifact_key=artifact_default,
                    source_locator="page:1|block:2",
                    source_excerpt="source excerpt",
                    attribute_name="material",
                    value_raw="SS316",
                )
            ],
        )

        artifact_false = f"native:{page.id}:review-false"
        rows_false = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_false,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact_false,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                    review_required=False,
                )
            ],
        )
        db.commit()

        persisted_default = db.get(TenderScopeAttribute, rows_default[0].id)
        persisted_false = db.get(TenderScopeAttribute, rows_false[0].id)
        assert persisted_default is not None and persisted_default.review_required is True
        assert persisted_false is not None and persisted_false.review_required is False
    finally:
        db.close()


def test_scope_detail_can_have_multiple_attributes() -> None:
    tender_id = _create_tender("attr multiple")
    document_id = _import_pdf(tender_id, "attr-multiple.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="material",
                    value_raw="SS316",
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="accuracy",
                    value_raw="+/-0.075%",
                ),
            ],
        )
        db.commit()

        assert len(rows) == 3
        assert _count_scope_attributes(db, tender_id) == 3
    finally:
        db.close()


def test_same_excerpt_supports_multiple_attributes() -> None:
    tender_id = _create_tender("attr same excerpt")
    document_id = _import_pdf(tender_id, "attr-excerpt.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        candidates = [
            _candidate(
                tender_id=tender_id,
                scope_detail_id=detail.id,
                document_id=document_id,
                page_id=page.id,
                artifact_key=artifact,
                attribute_name="signal",
                value_raw="4-20 mA HART",
            ),
            _candidate(
                tender_id=tender_id,
                scope_detail_id=detail.id,
                document_id=document_id,
                page_id=page.id,
                artifact_key=artifact,
                attribute_name="protocol",
                value_raw="HART",
            ),
        ]
        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=candidates,
        )
        db.commit()

        rows = db.execute(
            select(TenderScopeAttribute)
            .where(TenderScopeAttribute.scope_detail_id == detail.id)
            .order_by(TenderScopeAttribute.attribute_name.asc())
        ).scalars().all()
        assert [row.attribute_name for row in rows] == ["protocol", "signal"]
        assert all(row.source_excerpt == candidates[0].source_excerpt for row in rows)
    finally:
        db.close()


def test_exact_replay_is_semantically_idempotent() -> None:
    tender_id = _create_tender("attr idempotent")
    document_id = _import_pdf(tender_id, "attr-idempotent.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        candidates = [
            _candidate(
                tender_id=tender_id,
                scope_detail_id=detail.id,
                document_id=document_id,
                page_id=page.id,
                artifact_key=artifact,
                attribute_name="accuracy",
                value_raw="+/-0.075%",
                relation=SCOPE_ATTRIBUTE_RELATION_EXACT,
            )
        ]

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=candidates,
        )
        db.commit()

        first = db.execute(
            select(TenderScopeAttribute.attribute_name, TenderScopeAttribute.value_raw, TenderScopeAttribute.semantic_fingerprint).where(
                TenderScopeAttribute.scope_detail_id == detail.id
            )
        ).all()

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=candidates,
        )
        db.commit()

        second = db.execute(
            select(TenderScopeAttribute.attribute_name, TenderScopeAttribute.value_raw, TenderScopeAttribute.semantic_fingerprint).where(
                TenderScopeAttribute.scope_detail_id == detail.id
            )
        ).all()

        assert first == second
        assert len(second) == 1
    finally:
        db.close()


def test_empty_replacement_clears_only_same_artifact_boundary() -> None:
    tender_id = _create_tender("attr clear boundary")
    document_id = _import_pdf(tender_id, "attr-clear-boundary.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact1 = f"native-page:{page.id}:attrs-1"
        artifact2 = f"native-page:{page.id}:attrs-2"

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact1,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact1,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                )
            ],
        )
        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact2,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact2,
                    attribute_name="material",
                    value_raw="SS316",
                )
            ],
        )
        db.commit()

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact1,
            candidates=[],
        )
        db.commit()

        remaining = db.execute(
            select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == detail.id)
        ).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].source_artifact_key == artifact2
    finally:
        db.close()


def test_different_source_artifact_key_remains_additive() -> None:
    tender_id = _create_tender("attr artifact additive")
    document_id = _import_pdf(tender_id, "attr-artifact-add.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)

        for idx in range(2):
            artifact = f"native-page:{page.id}:attrs-{idx}"
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[
                    _candidate(
                        tender_id=tender_id,
                        scope_detail_id=detail.id,
                        document_id=document_id,
                        page_id=page.id,
                        artifact_key=artifact,
                        attribute_name=f"model_{idx}",
                        value_raw="3051TG",
                    )
                ],
            )
        db.commit()

        assert _count_scope_attributes(db, tender_id) == 2
    finally:
        db.close()


def test_different_page_document_remains_additive() -> None:
    tender_id = _create_tender("attr page doc additive")
    doc1 = _import_pdf(tender_id, "attr-doc1.pdf")
    doc2 = _import_pdf(tender_id, "attr-doc2.pdf")

    db = SessionLocal()
    try:
        page1 = _seed_page(db, doc1, 1, "TX")
        page2 = _seed_page(db, doc2, 1, "TX")
        detail1 = _seed_scope_detail(db, tender_id=tender_id, document_id=doc1, page_id=page1.id)
        detail2 = _seed_scope_detail(db, tender_id=tender_id, document_id=doc2, page_id=page2.id)

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail1.id,
            source_document_id=doc1,
            document_page_id=page1.id,
            source_artifact_key=f"native-page:{page1.id}:attrs",
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail1.id,
                    document_id=doc1,
                    page_id=page1.id,
                    artifact_key=f"native-page:{page1.id}:attrs",
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                )
            ],
        )
        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail2.id,
            source_document_id=doc2,
            document_page_id=page2.id,
            source_artifact_key=f"native-page:{page2.id}:attrs",
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail2.id,
                    document_id=doc2,
                    page_id=page2.id,
                    artifact_key=f"native-page:{page2.id}:attrs",
                    attribute_name="material",
                    value_raw="SS316",
                )
            ],
        )
        db.commit()

        assert _count_scope_attributes(db, tender_id) == 2
    finally:
        db.close()


def test_different_scope_detail_is_isolated() -> None:
    tender_id = _create_tender("attr scope isolation")
    document_id = _import_pdf(tender_id, "attr-scope-iso.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail1 = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        detail2 = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)

        artifact = f"native-page:{page.id}:attrs"
        artifact_d2 = f"native-page:{page.id}:attrs-d2"
        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail1.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail1.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                )
            ],
        )
        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail2.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_d2,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail2.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact_d2,
                    attribute_name="material",
                    value_raw="SS316",
                )
            ],
        )
        db.commit()

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail1.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[],
        )
        db.commit()

        count_d2 = db.scalar(select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.scope_detail_id == detail2.id))
        assert int(count_d2 or 0) == 1
    finally:
        db.close()


def test_cross_tender_scope_detail_attachment_rejected() -> None:
    tender1 = _create_tender("attr cross tender 1")
    tender2 = _create_tender("attr cross tender 2")
    doc1 = _import_pdf(tender1, "attr-ct1.pdf")
    doc2 = _import_pdf(tender2, "attr-ct2.pdf")

    db = SessionLocal()
    try:
        page1 = _seed_page(db, doc1, 1, "TX")
        page2 = _seed_page(db, doc2, 1, "TX")
        detail2 = _seed_scope_detail(db, tender_id=tender2, document_id=doc2, page_id=page2.id)

        with pytest.raises(ValueError, match="different tender"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender1,
                scope_detail_id=detail2.id,
                source_document_id=doc1,
                document_page_id=page1.id,
                source_artifact_key=f"native-page:{page1.id}:attrs",
                candidates=[],
            )
    finally:
        db.close()


def test_cross_tender_document_page_provenance_rejected() -> None:
    tender1 = _create_tender("attr cross tender provenance 1")
    tender2 = _create_tender("attr cross tender provenance 2")
    doc1 = _import_pdf(tender1, "attr-ctp1.pdf")
    doc2 = _import_pdf(tender2, "attr-ctp2.pdf")

    db = SessionLocal()
    try:
        page1 = _seed_page(db, doc1, 1, "TX")
        page2 = _seed_page(db, doc2, 1, "TX")
        detail1 = _seed_scope_detail(db, tender_id=tender1, document_id=doc1, page_id=page1.id)

        with pytest.raises(ValueError, match="different tender"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender1,
                scope_detail_id=detail1.id,
                source_document_id=doc2,
                document_page_id=page2.id,
                source_artifact_key=f"native-page:{page2.id}:attrs",
                candidates=[],
            )
    finally:
        db.close()


def test_missing_provenance_is_rejected() -> None:
    tender_id = _create_tender("attr missing provenance")
    document_id = _import_pdf(tender_id, "attr-missing-provenance.pdf")
    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"
        candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            artifact_key=artifact,
            attribute_name="signal",
            value_raw="4-20 mA",
        )
        candidate = replace(candidate, source_artifact_key="")

        with pytest.raises(ValueError, match="source_artifact_key is required"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[candidate],
            )
    finally:
        db.close()


@pytest.mark.parametrize(
    ("attribute_name", "value_raw", "expected"),
    [
        ("", "4-20 mA", "attribute_name is required"),
        ("signal", "", "value_raw is required"),
    ],
)
def test_required_fields_rejected(attribute_name: str, value_raw: str, expected: str) -> None:
    tender_id = _create_tender(f"attr required {attribute_name or 'empty'}")
    document_id = _import_pdf(tender_id, f"attr-required-{uuid4().hex}.pdf")
    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"
        candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            artifact_key=artifact,
            attribute_name=attribute_name,
            value_raw=value_raw,
        )

        with pytest.raises(ValueError, match=expected):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[candidate],
            )
    finally:
        db.close()


def test_confidence_outside_range_rejected() -> None:
    tender_id = _create_tender("attr confidence range")
    document_id = _import_pdf(tender_id, "attr-confidence.pdf")
    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"
        candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            artifact_key=artifact,
            attribute_name="accuracy",
            value_raw="+/-0.075%",
            confidence=1.2,
        )

        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[candidate],
            )
    finally:
        db.close()


def test_invalid_relation_rejected() -> None:
    tender_id = _create_tender("attr relation")
    document_id = _import_pdf(tender_id, "attr-relation.pdf")
    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"
        candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            artifact_key=artifact,
            attribute_name="pressure_rating",
            value_raw="Class 150",
            relation="APPROX",
        )

        with pytest.raises(ValueError, match="Unsupported relation"):
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[candidate],
            )
    finally:
        db.close()


def test_native_and_ocr_persist_without_vision_lineage() -> None:
    tender_id = _create_tender("attr native ocr")
    document_id = _import_pdf(tender_id, "attr-native-ocr.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)

        for method in ["NATIVE", "OCR"]:
            artifact = f"{method.lower()}:{page.id}:attrs"
            replace_scope_attributes_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[
                    _candidate(
                        tender_id=tender_id,
                        scope_detail_id=detail.id,
                        document_id=document_id,
                        page_id=page.id,
                        artifact_key=artifact,
                        attribute_name="power_supply",
                        value_raw="24 VDC",
                        source_method=method,
                    )
                ],
            )

        db.commit()

        rows = db.execute(
            select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == detail.id)
        ).scalars().all()
        assert len(rows) == 2
        assert all(row.source_analysis_id is None for row in rows)
        assert all(row.source_page_result_id is None for row in rows)
    finally:
        db.close()


def test_vision_lineage_ids_can_be_preserved() -> None:
    tender_id = _create_tender("attr vision lineage")
    document_id = _import_pdf(tender_id, "attr-vision-lineage.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        analysis, page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page)
        detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_analysis_id=analysis.id,
            source_page_result_id=page_result.id,
        )

        artifact = f"vision-page-result:{page_result.id}:attrs"
        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="protocol",
                    value_raw="HART",
                    source_method="VISION",
                    source_analysis_id=analysis.id,
                    source_page_result_id=page_result.id,
                    confidence=0.76,
                )
            ],
        )
        db.commit()

        persisted = db.get(TenderScopeAttribute, rows[0].id)
        assert persisted is not None
        assert persisted.source_analysis_id == analysis.id
        assert persisted.source_page_result_id == page_result.id
    finally:
        db.close()


def test_cascade_and_set_null_fk_behavior() -> None:
    tender_id = _create_tender("attr fk behavior")
    document_id = _import_pdf(tender_id, "attr-fk-behavior.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        analysis, page_result = _seed_vision_lineage(db, tender_id=tender_id, document_id=document_id, page=page)
        detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_analysis_id=analysis.id,
            source_page_result_id=page_result.id,
        )
        artifact = f"vision-page-result:{page_result.id}:attrs"

        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="manufacturer",
                    value_raw="Emerson",
                    source_method="VISION",
                    source_analysis_id=analysis.id,
                    source_page_result_id=page_result.id,
                )
            ],
        )
        db.commit()

        attribute_id = rows[0].id
        db.delete(analysis)
        db.commit()
        db.expire_all()

        refreshed = db.get(TenderScopeAttribute, attribute_id)
        assert refreshed is not None
        assert refreshed.source_analysis_id is None
        assert refreshed.source_page_result_id is None

        db.delete(detail)
        db.flush()
        assert db.get(TenderScopeAttribute, attribute_id) is None
    finally:
        db.close()


def test_quantity_and_unit_strings_remain_unchanged() -> None:
    tender_id = _create_tender("attr unit raw unchanged")
    document_id = _import_pdf(tender_id, "attr-unit-raw.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="pressure_rating",
                    value_raw="10-15",
                    unit_raw="bar",
                    relation=SCOPE_ATTRIBUTE_RELATION_RANGE,
                )
            ],
        )
        db.commit()

        persisted = db.get(TenderScopeAttribute, rows[0].id)
        assert persisted is not None
        assert persisted.value_raw == "10-15"
        assert persisted.unit_raw == "bar"
    finally:
        db.close()


def test_attributes_do_not_modify_scope_details_or_requirements() -> None:
    tender_id = _create_tender("attr no side effects")
    document_id = _import_pdf(tender_id, "attr-no-side-effects.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        scope_count_before = int(db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)) or 0)
        req_count_before = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="material",
                    value_raw="SS316",
                )
            ],
        )
        db.commit()

        scope_count_after = int(db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)) or 0)
        req_count_after = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        assert scope_count_after == scope_count_before
        assert req_count_after == req_count_before
    finally:
        db.close()


def test_no_document_type_filtering_for_attributes() -> None:
    tender_id = _create_tender("attr no doc type filter")
    document_id = _import_pdf(tender_id, "attr-doc-type-filter.pdf")

    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=document_id,
                suggested_type="ADMINISTRATIVE_LEGAL_REQUIREMENTS",
                suggested_score=100,
                classification_status="CONFIRMED",
                human_type="ADMINISTRATIVE_LEGAL_REQUIREMENTS",
            )
        )
        page = _seed_page(db, document_id, 1, "TX")
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page_id=page.id)
        artifact = f"native-page:{page.id}:attrs"

        rows = replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    artifact_key=artifact,
                    attribute_name="signal",
                    value_raw="4-20 mA HART",
                )
            ],
        )
        db.commit()

        assert len(rows) == 1
        assert _count_scope_attributes(db, tender_id) == 1
    finally:
        db.close()
