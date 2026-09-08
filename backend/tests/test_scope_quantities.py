from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

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
from app.scope_attributes import ScopeAttributeCandidate, replace_scope_attributes_for_artifact
from app.scope_quantities import (
    SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    SCOPE_QUANTITY_RELATION_APPROXIMATE,
    SCOPE_QUANTITY_RELATION_EXACT,
    SCOPE_QUANTITY_RELATION_MAXIMUM,
    SCOPE_QUANTITY_RELATION_MINIMUM,
    SCOPE_QUANTITY_RELATION_RANGE,
    SCOPE_QUANTITY_RELATION_UNSPECIFIED,
    ScopeQuantityCandidate,
    compute_scope_quantity_fingerprint,
    list_scope_quantities_for_scope_detail,
    replace_scope_quantities_for_artifact,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-QTY-{uuid4()}"
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
    page: DocumentPage,
    source_excerpt: str,
    source_method: str = "NATIVE",
    source_artifact_key: str | None = None,
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
        source_artifact_key=source_artifact_key or f"{source_method.lower()}-page:{page.id}:scope",
        source_contract_version="scope-quantities-contract-001",
        source_locator="page:1|block:1",
        source_excerpt=source_excerpt,
        confidence=None,
        review_required=False,
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
    source_artifact_key: str,
    source_excerpt: str,
    quantity_raw: str,
    source_method: str = "NATIVE",
    relation: str | None = SCOPE_QUANTITY_RELATION_UNSPECIFIED,
    measure_kind: str | None = None,
    unit_raw: str | None = None,
    quantity_value: Decimal | None = None,
    quantity_min: Decimal | None = None,
    quantity_max: Decimal | None = None,
    confidence: float | None = None,
    review_required: bool = True,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
) -> ScopeQuantityCandidate:
    return ScopeQuantityCandidate(
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=document_id,
        document_page_id=page_id,
        quantity_raw=quantity_raw,
        quantity_value=quantity_value,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        unit_raw=unit_raw,
        measure_kind=measure_kind,
        relation=relation,
        source_method=source_method,
        source_artifact_key=source_artifact_key,
        source_locator="page:1|block:2",
        source_excerpt=source_excerpt,
        confidence=confidence,
        review_required=review_required,
        source_contract_version="scope-quantities-contract-001",
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )


def _count_scope_quantities(db, *, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeQuantity.id)).where(TenderScopeQuantity.scope_detail_id == scope_detail_id))
    return int(value or 0)


def _count_scope_attributes(db, *, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.scope_detail_id == scope_detail_id))
    return int(value or 0)


def test_valid_quantity_relations_and_raw_only_unspecified() -> None:
    tender_id = _create_tender("scope qty relations")
    document_id = _import_pdf(tender_id, "scope-qty-relations.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "2 TECNICOS DURANTE 5 DIAS; MINIMO 3; MAXIMO 10; APROX 2"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)
        artifact = f"native-page:{page.id}:qty"

        rows = replace_scope_quantities_for_artifact(
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
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value=Decimal("2"),
                    measure_kind=SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
                    unit_raw="TECNICOS",
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="3",
                    relation=SCOPE_QUANTITY_RELATION_MINIMUM,
                    quantity_min=Decimal("3"),
                    measure_kind=SCOPE_QUANTITY_MEASURE_KIND_COUNT,
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="10",
                    relation=SCOPE_QUANTITY_RELATION_MAXIMUM,
                    quantity_max=Decimal("10"),
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="5",
                    relation=SCOPE_QUANTITY_RELATION_RANGE,
                    quantity_min=Decimal("2"),
                    quantity_max=Decimal("5"),
                    measure_kind=SCOPE_QUANTITY_MEASURE_KIND_DURATION,
                    unit_raw="DIAS",
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                    relation=SCOPE_QUANTITY_RELATION_APPROXIMATE,
                    quantity_value=Decimal("2"),
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="5",
                    relation=SCOPE_QUANTITY_RELATION_UNSPECIFIED,
                ),
            ],
        )
        db.commit()

        assert len(rows) == 6
    finally:
        db.close()


def test_invalid_relation_measure_kind_confidence_and_shape_rejected() -> None:
    tender_id = _create_tender("scope qty invalids")
    document_id = _import_pdf(tender_id, "scope-qty-invalids.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "ENTRE 2 Y 4 UNIDADES"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)
        artifact = f"native-page:{page.id}:qty-invalid"

        base = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail.id,
            document_id=document_id,
            page_id=page.id,
            source_artifact_key=artifact,
            source_excerpt=source_excerpt,
            quantity_raw="2",
            relation=SCOPE_QUANTITY_RELATION_EXACT,
            quantity_value=Decimal("2"),
        )

        with pytest.raises(ValueError, match="quantity_raw is required"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, quantity_raw="  ")],
            )

        with pytest.raises(ValueError, match="Unsupported relation"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, relation="TOLERANCE")],
            )

        with pytest.raises(ValueError, match="Unsupported measure_kind"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, measure_kind="VOLTAGE")],
            )

        with pytest.raises(ValueError, match="confidence must be between"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, confidence=1.2)],
            )

        with pytest.raises(ValueError, match="confidence must be between"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, confidence=-0.1)],
            )

        with pytest.raises(ValueError, match="quantity_min and quantity_max are required"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, relation=SCOPE_QUANTITY_RELATION_RANGE, quantity_value=None, quantity_max=Decimal("4"))],
            )

        with pytest.raises(ValueError, match="quantity_min and quantity_max are required"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[replace(base, relation=SCOPE_QUANTITY_RELATION_RANGE, quantity_value=None, quantity_min=Decimal("2"), quantity_max=None)],
            )

        with pytest.raises(ValueError, match="quantity_min cannot be greater than quantity_max"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=artifact,
                candidates=[
                    replace(
                        base,
                        relation=SCOPE_QUANTITY_RELATION_RANGE,
                        quantity_value=None,
                        quantity_min=Decimal("5"),
                        quantity_max=Decimal("2"),
                    )
                ],
            )
    finally:
        db.close()


def test_grounding_enforced_for_quantity_and_unit() -> None:
    tender_id = _create_tender("scope qty grounding")
    document_id = _import_pdf(tender_id, "scope-qty-grounding.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "SE REQUIEREN 2 TECNICOS"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)
        artifact = f"native-page:{page.id}:qty-grounding"

        with pytest.raises(ValueError, match="quantity_raw is not grounded"):
            replace_scope_quantities_for_artifact(
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
                        source_artifact_key=artifact,
                        source_excerpt=source_excerpt,
                        quantity_raw="3",
                    )
                ],
            )

        with pytest.raises(ValueError, match="unit_raw is not grounded"):
            replace_scope_quantities_for_artifact(
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
                        source_artifact_key=artifact,
                        source_excerpt=source_excerpt,
                        quantity_raw="2",
                        relation=SCOPE_QUANTITY_RELATION_EXACT,
                        quantity_value=Decimal("2"),
                        unit_raw="DIAS",
                    )
                ],
            )
    finally:
        db.close()


def test_source_method_allowlist_accepts_native_ocr_vision_and_rejects_unknown() -> None:
    tender_id = _create_tender("scope qty source methods")
    document_id = _import_pdf(tender_id, "scope-qty-source-methods.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "2 EQUIPOS"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)

        for method in ["NATIVE", "OCR", "VISION"]:
            artifact = f"{method.lower()}:{page.id}:qty"
            rows = replace_scope_quantities_for_artifact(
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
                        source_artifact_key=artifact,
                        source_excerpt=source_excerpt,
                        quantity_raw="2",
                        relation=SCOPE_QUANTITY_RELATION_EXACT,
                        quantity_value=Decimal("2"),
                        source_method=method,
                    )
                ],
            )
            assert len(rows) == 1

        with pytest.raises(ValueError, match="Unsupported source_method"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_id,
                scope_detail_id=detail.id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key="custom:qty",
                candidates=[
                    _candidate(
                        tender_id=tender_id,
                        scope_detail_id=detail.id,
                        document_id=document_id,
                        page_id=page.id,
                        source_artifact_key="custom:qty",
                        source_excerpt=source_excerpt,
                        quantity_raw="2",
                        source_method="MANUAL",
                    )
                ],
            )
    finally:
        db.close()


def test_cross_tender_document_page_and_vision_lineage_validation() -> None:
    tender_a = _create_tender("scope qty tender a")
    tender_b = _create_tender("scope qty tender b")
    doc_a = _import_pdf(tender_a, "scope-qty-a.pdf")
    doc_b = _import_pdf(tender_b, "scope-qty-b.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, doc_a, 1, "2 EQUIPOS")
        page_b = _seed_page(db, doc_b, 1, "2 EQUIPOS")

        detail_a = _seed_scope_detail(db, tender_id=tender_a, document_id=doc_a, page=page_a, source_excerpt="2 EQUIPOS")
        detail_b = _seed_scope_detail(db, tender_id=tender_b, document_id=doc_b, page=page_b, source_excerpt="2 EQUIPOS")

        analysis_a, page_result_a = _seed_vision_lineage(db, tender_id=tender_a, document_id=doc_a, page=page_a)
        analysis_a_alt, page_result_a_alt = _seed_vision_lineage(db, tender_id=tender_a, document_id=doc_a, page=page_a)
        analysis_b, page_result_b = _seed_vision_lineage(db, tender_id=tender_b, document_id=doc_b, page=page_b)
        db.commit()

        with pytest.raises(ValueError, match="scope_detail_id belongs to a different tender"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_a,
                scope_detail_id=detail_b.id,
                source_document_id=doc_a,
                document_page_id=page_a.id,
                source_artifact_key="native-a",
                candidates=[
                    _candidate(
                        tender_id=tender_a,
                        scope_detail_id=detail_b.id,
                        document_id=doc_a,
                        page_id=page_a.id,
                        source_artifact_key="native-a",
                        source_excerpt="2 EQUIPOS",
                        quantity_raw="2",
                    )
                ],
            )

        with pytest.raises(ValueError, match="source_document_id belongs to a different tender"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_a,
                scope_detail_id=detail_a.id,
                source_document_id=doc_b,
                document_page_id=page_a.id,
                source_artifact_key="native-bad-doc",
                candidates=[
                    _candidate(
                        tender_id=tender_a,
                        scope_detail_id=detail_a.id,
                        document_id=doc_b,
                        page_id=page_a.id,
                        source_artifact_key="native-bad-doc",
                        source_excerpt="2 EQUIPOS",
                        quantity_raw="2",
                    )
                ],
            )

        with pytest.raises(ValueError, match="document_page_id does not belong to source_document_id"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_a,
                scope_detail_id=detail_a.id,
                source_document_id=doc_a,
                document_page_id=page_b.id,
                source_artifact_key="native-bad-page",
                candidates=[
                    _candidate(
                        tender_id=tender_a,
                        scope_detail_id=detail_a.id,
                        document_id=doc_a,
                        page_id=page_b.id,
                        source_artifact_key="native-bad-page",
                        source_excerpt="2 EQUIPOS",
                        quantity_raw="2",
                    )
                ],
            )

        with pytest.raises(ValueError, match="source_analysis_id belongs to a different tender"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_a,
                scope_detail_id=detail_a.id,
                source_document_id=doc_a,
                document_page_id=page_a.id,
                source_artifact_key="vision-bad-lineage",
                candidates=[
                    _candidate(
                        tender_id=tender_a,
                        scope_detail_id=detail_a.id,
                        document_id=doc_a,
                        page_id=page_a.id,
                        source_artifact_key="vision-bad-lineage",
                        source_excerpt="2 EQUIPOS",
                        quantity_raw="2",
                        source_method="VISION",
                            source_analysis_id=analysis_b.id,
                            source_page_result_id=page_result_a.id,
                    )
                ],
            )

        with pytest.raises(ValueError, match="source_page_result_id does not belong to source_analysis_id"):
            replace_scope_quantities_for_artifact(
                db,
                tender_id=tender_a,
                scope_detail_id=detail_a.id,
                source_document_id=doc_a,
                document_page_id=page_a.id,
                source_artifact_key="vision-page-result-mismatch",
                candidates=[
                    _candidate(
                        tender_id=tender_a,
                        scope_detail_id=detail_a.id,
                        document_id=doc_a,
                        page_id=page_a.id,
                        source_artifact_key="vision-page-result-mismatch",
                        source_excerpt="2 EQUIPOS",
                        quantity_raw="2",
                        source_method="VISION",
                        source_analysis_id=analysis_a.id,
                        source_page_result_id=page_result_a_alt.id,
                    )
                ],
            )

        rows = replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_a,
            scope_detail_id=detail_a.id,
            source_document_id=doc_a,
            document_page_id=page_a.id,
            source_artifact_key="vision-ok",
            candidates=[
                _candidate(
                    tender_id=tender_a,
                    scope_detail_id=detail_a.id,
                    document_id=doc_a,
                    page_id=page_a.id,
                    source_artifact_key="vision-ok",
                    source_excerpt="2 EQUIPOS",
                    quantity_raw="2",
                    source_method="VISION",
                    source_analysis_id=analysis_a.id,
                    source_page_result_id=page_result_a.id,
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value=Decimal("2"),
                )
            ],
        )
        assert len(rows) == 1
    finally:
        db.close()


def test_multiple_quantities_same_excerpt_and_list_ordering() -> None:
    tender_id = _create_tender("scope qty multiple")
    document_id = _import_pdf(tender_id, "scope-qty-multiple.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "2 TECNICOS DURANTE 5 DIAS"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)
        artifact = f"native-page:{page.id}:qty-multi"

        replace_scope_quantities_for_artifact(
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
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value=Decimal("2"),
                    measure_kind=SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
                    unit_raw="TECNICOS",
                ),
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact,
                    source_excerpt=source_excerpt,
                    quantity_raw="5",
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value=Decimal("5"),
                    measure_kind=SCOPE_QUANTITY_MEASURE_KIND_DURATION,
                    unit_raw="DIAS",
                ),
            ],
        )
        db.commit()

        listed = list_scope_quantities_for_scope_detail(db, scope_detail_id=detail.id)
        assert len(listed) == 2
        assert [row.quantity_raw for row in listed] == ["2", "5"]
    finally:
        db.close()


def test_fingerprint_stable_and_independent_of_confidence_review_and_provenance() -> None:
    base = ScopeQuantityCandidate(
        tender_id="t1",
        scope_detail_id="sd1",
        source_document_id="d1",
        document_page_id="p1",
        quantity_raw="2",
        quantity_value=Decimal("2"),
        unit_raw="EQUIPOS",
        measure_kind=SCOPE_QUANTITY_MEASURE_KIND_COUNT,
        relation=SCOPE_QUANTITY_RELATION_EXACT,
        source_method="NATIVE",
        source_artifact_key="artifact",
        source_locator="loc",
        source_excerpt="2 EQUIPOS",
        confidence=0.2,
        review_required=True,
    )

    fp_a = compute_scope_quantity_fingerprint(base)
    fp_b = compute_scope_quantity_fingerprint(replace(base, confidence=0.9, review_required=False))
    fp_c = compute_scope_quantity_fingerprint(
        replace(
            base,
            source_locator="page:99|block:8",
            source_excerpt="SE REQUIEREN 2 EQUIPOS PARA EJECUCION",
            source_artifact_key="artifact-other",
        )
    )
    fp_d = compute_scope_quantity_fingerprint(base)

    assert fp_a == fp_b
    assert fp_a == fp_c
    assert fp_a == fp_d


@pytest.mark.parametrize(
    "field_patch",
    [
        {"quantity_raw": "3"},
        {"unit_raw": "PIEZAS"},
        {"measure_kind": SCOPE_QUANTITY_MEASURE_KIND_DURATION},
        {"relation": SCOPE_QUANTITY_RELATION_MINIMUM, "quantity_value": None, "quantity_min": Decimal("2")},
        {"quantity_value": Decimal("3")},
        {"quantity_min": Decimal("1")},
        {"quantity_max": Decimal("4")},
    ],
)
def test_fingerprint_changes_when_semantic_quantity_identity_changes(field_patch: dict[str, object]) -> None:
    base = ScopeQuantityCandidate(
        tender_id="t1",
        scope_detail_id="sd1",
        source_document_id="d1",
        document_page_id="p1",
        quantity_raw="2",
        quantity_value=Decimal("2"),
        quantity_min=None,
        quantity_max=None,
        unit_raw="EQUIPOS",
        measure_kind=SCOPE_QUANTITY_MEASURE_KIND_COUNT,
        relation=SCOPE_QUANTITY_RELATION_EXACT,
        source_method="NATIVE",
        source_artifact_key="artifact",
        source_locator="loc",
        source_excerpt="2 EQUIPOS",
        confidence=0.2,
        review_required=True,
    )

    changed = replace(base, **field_patch)

    assert compute_scope_quantity_fingerprint(base) != compute_scope_quantity_fingerprint(changed)


def test_replay_idempotency_empty_clear_and_boundary_isolation() -> None:
    tender_id = _create_tender("scope qty replay")
    document_id = _import_pdf(tender_id, "scope-qty-replay.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "2 EQUIPOS")
        detail_a = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt="2 EQUIPOS")
        detail_b = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_excerpt="2 EQUIPOS",
            source_artifact_key=f"native-page:{page.id}:scope-b",
        )

        artifact_a = "artifact-a"
        artifact_b = "artifact-b"

        first_candidate = _candidate(
            tender_id=tender_id,
            scope_detail_id=detail_a.id,
            document_id=document_id,
            page_id=page.id,
            source_artifact_key=artifact_a,
            source_excerpt="2 EQUIPOS",
            quantity_raw="2",
            relation=SCOPE_QUANTITY_RELATION_EXACT,
            quantity_value=Decimal("2"),
            review_required=False,
        )

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail_a.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_a,
            candidates=[first_candidate],
        )

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail_a.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_b,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail_a.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact_b,
                    source_excerpt="2 EQUIPOS",
                    quantity_raw="2",
                    relation=SCOPE_QUANTITY_RELATION_UNSPECIFIED,
                )
            ],
        )

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail_b.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key="artifact-detail-b",
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail_b.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key="artifact-detail-b",
                    source_excerpt="2 EQUIPOS",
                    quantity_raw="2",
                )
            ],
        )
        db.commit()

        before = list_scope_quantities_for_scope_detail(db, scope_detail_id=detail_a.id)

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail_a.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_a,
            candidates=[first_candidate],
        )

        after_replay = list_scope_quantities_for_scope_detail(db, scope_detail_id=detail_a.id)
        assert len(before) == len(after_replay) == 2

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail_a.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_a,
            candidates=[],
        )
        db.commit()

        remaining_detail_a = list_scope_quantities_for_scope_detail(db, scope_detail_id=detail_a.id)
        remaining_detail_b = list_scope_quantities_for_scope_detail(db, scope_detail_id=detail_b.id)

        assert len(remaining_detail_a) == 1
        assert remaining_detail_a[0].source_artifact_key == artifact_b
        assert len(remaining_detail_b) == 1
    finally:
        db.close()


def test_quantity_persistence_does_not_change_technical_attributes_or_requirements() -> None:
    tender_id = _create_tender("scope qty separation")
    document_id = _import_pdf(tender_id, "scope-qty-separation.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "2 EQUIPOS"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)

        replace_scope_attributes_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key="attr-artifact",
            candidates=[
                ScopeAttributeCandidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    source_document_id=document_id,
                    document_page_id=page.id,
                    source_method="NATIVE",
                    source_artifact_key="attr-artifact",
                    source_locator="page:1|block:2|attr:model",
                    source_excerpt="MODELO: PW481-50",
                    attribute_name="model",
                    value_raw="PW481-50",
                    review_required=False,
                )
            ],
        )

        requirement = Requirement(
            tender_id=tender_id,
            canonical_key=f"req-{uuid4()}",
            canonical_text="No cambia en persistencia de cantidades",
            category="TECHNICAL",
            normalization_status="REVIEW_REQUIRED",
            normalizer_version="mvp-04.3",
        )
        db.add(requirement)
        db.commit()

        attr_before = _count_scope_attributes(db, scope_detail_id=detail.id)
        req_before = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key="qty-artifact",
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key="qty-artifact",
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value=Decimal("2"),
                )
            ],
        )
        db.commit()

        attr_after = _count_scope_attributes(db, scope_detail_id=detail.id)
        req_after = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        assert attr_before == attr_after == 1
        assert req_before == req_after == 1
    finally:
        db.close()


def test_review_required_default_true_and_explicit_false_preserved() -> None:
    tender_id = _create_tender("scope qty review required")
    document_id = _import_pdf(tender_id, "scope-qty-review-required.pdf")

    db = SessionLocal()
    try:
        source_excerpt = "2 EQUIPOS"
        page = _seed_page(db, document_id, 1, source_excerpt)
        detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_excerpt)

        artifact_true = "artifact-review-default"
        rows_default = replace_scope_quantities_for_artifact(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_true,
            candidates=[
                _candidate(
                    tender_id=tender_id,
                    scope_detail_id=detail.id,
                    document_id=document_id,
                    page_id=page.id,
                    source_artifact_key=artifact_true,
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                )
            ],
        )

        artifact_false = "artifact-review-false"
        rows_false = replace_scope_quantities_for_artifact(
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
                    source_artifact_key=artifact_false,
                    source_excerpt=source_excerpt,
                    quantity_raw="2",
                    review_required=False,
                )
            ],
        )
        db.commit()

        persisted_default = db.get(TenderScopeQuantity, rows_default[0].id)
        persisted_false = db.get(TenderScopeQuantity, rows_false[0].id)
        assert persisted_default is not None and persisted_default.review_required is True
        assert persisted_false is not None and persisted_false.review_required is False
    finally:
        db.close()
