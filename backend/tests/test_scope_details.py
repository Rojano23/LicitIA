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
    TenderDocument,
    TenderItem,
    TenderScopeDetail,
    TenderScopeSegment,
)
from app.scope_details import (
    SCOPE_DETAIL_APPLICABILITY_ITEM,
    SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
    SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
    SCOPE_DETAIL_DOMAIN_DELIVERABLE,
    SCOPE_DETAIL_DOMAIN_PERSONNEL,
    SCOPE_DETAIL_DOMAIN_SERVICE,
    SCOPE_DETAIL_DOMAIN_SSPA,
    SCOPE_DETAIL_DOMAIN_SUPPLY,
    ScopeDetailCandidate,
    replace_scope_details_for_artifact,
)


client = TestClient(app)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-DETAIL-{uuid4()}"
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


def _seed_classification(db, document_id: str, suggested_type: str) -> None:
    row = DocumentClassification(
        document_id=document_id,
        suggested_type=suggested_type,
        suggested_score=90,
        classification_status="CONFIRMED",
        human_type=suggested_type,
    )
    db.add(row)


def _base_candidate(
    *,
    tender_id: str,
    document_id: str,
    page_id: str,
    domain: str,
    artifact_key: str,
    description: str,
    applicability: str,
) -> ScopeDetailCandidate:
    return ScopeDetailCandidate(
        tender_id=tender_id,
        source_document_id=document_id,
        document_page_id=page_id,
        domain=domain,
        detail_type="TASK",
        description=description,
        normalized_label=description.upper(),
        applicability=applicability,
        source_method="NATIVE",
        source_artifact_key=artifact_key,
        source_locator="page:1|block:1",
        source_excerpt=description,
        review_required=False,
    )


def test_document_type_independence_for_scope_detail_persistence() -> None:
    tender_id = _create_tender("scope detail doc type independence")
    docs = [
        ("anexo-tecnico.pdf", "TECHNICAL_SPECIFICATION", SCOPE_DETAIL_DOMAIN_SERVICE),
        ("bases.pdf", "BIDDING_RULES", SCOPE_DETAIL_DOMAIN_SUPPLY),
        ("anexo-comercial.pdf", "PRICING_SCHEDULE_CATALOG", SCOPE_DETAIL_DOMAIN_DELIVERABLE),
        ("sspa.pdf", "ADMINISTRATIVE_LEGAL_REQUIREMENTS", SCOPE_DETAIL_DOMAIN_PERSONNEL),
    ]

    db = SessionLocal()
    try:
        for idx, (filename, classification_type, domain) in enumerate(docs, start=1):
            document_id = _import_pdf(tender_id, filename)
            page = _seed_page(db, document_id, 1, f"Documento {idx}")
            _seed_classification(db, document_id, classification_type)
            candidate = _base_candidate(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                domain=domain,
                artifact_key=f"native-page:{page.id}:v1",
                description=f"Obligacion {domain}",
                applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
            )
            rows = replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=f"native-page:{page.id}:v1",
                candidates=[candidate],
            )
            assert len(rows) == 1
        db.commit()

        count = db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id))
        assert count == 4
    finally:
        db.close()


def test_heterogeneous_domains_on_same_artifact_coexist() -> None:
    tender_id = _create_tender("scope detail heterogeneous domains")
    document_id = _import_pdf(tender_id, "heterogeneous-domains.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Servicio y personal y entrega")
        artifact_key = f"native-page:{page.id}:v1"
        candidates = [
            _base_candidate(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                domain=SCOPE_DETAIL_DOMAIN_SERVICE,
                artifact_key=artifact_key,
                description="Ejecutar mantenimiento del sistema",
                applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
            ),
            _base_candidate(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                domain=SCOPE_DETAIL_DOMAIN_PERSONNEL,
                artifact_key=artifact_key,
                description="Asignar tres tecnicos certificados",
                applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
            ),
            _base_candidate(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                domain=SCOPE_DETAIL_DOMAIN_DELIVERABLE,
                artifact_key=artifact_key,
                description="Entregar reporte final firmado",
                applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
            ),
        ]

        rows = replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
            candidates=candidates,
        )
        db.commit()

        assert len(rows) == 3
        domains = db.execute(
            select(TenderScopeDetail.domain)
            .where(TenderScopeDetail.tender_id == tender_id)
            .order_by(TenderScopeDetail.domain.asc())
        ).scalars().all()
        assert domains == ["DELIVERABLE", "PERSONNEL", "SERVICE"]
    finally:
        db.close()


def test_provider_neutral_source_methods_and_artifact_keys() -> None:
    tender_id = _create_tender("scope detail provider neutral")
    document_id = _import_pdf(tender_id, "provider-neutral.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto de prueba")

        native = _base_candidate(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            domain=SCOPE_DETAIL_DOMAIN_SERVICE,
            artifact_key=f"native-page:{page.id}:v1",
            description="Servicio desde nativo",
            applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
        )
        ocr = replace(
            native,
            source_method="OCR",
            source_artifact_key="ocr-result:ocr-1",
            description="Servicio desde OCR",
        )
        vision = replace(
            native,
            source_method="VISION",
            source_artifact_key="vision-page-result:vision-1",
            description="Servicio desde vision",
        )

        replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=native.source_artifact_key,
            candidates=[native],
        )
        replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=ocr.source_artifact_key,
            candidates=[ocr],
        )
        replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=vision.source_artifact_key,
            candidates=[vision],
        )
        db.commit()

        methods = db.execute(
            select(TenderScopeDetail.source_method)
            .where(TenderScopeDetail.tender_id == tender_id)
            .order_by(TenderScopeDetail.source_method.asc())
        ).scalars().all()
        assert methods == ["NATIVE", "OCR", "VISION"]

        native_row = db.scalar(
            select(TenderScopeDetail).where(TenderScopeDetail.source_method == "NATIVE", TenderScopeDetail.tender_id == tender_id)
        )
        ocr_row = db.scalar(
            select(TenderScopeDetail).where(TenderScopeDetail.source_method == "OCR", TenderScopeDetail.tender_id == tender_id)
        )
        assert native_row is not None and native_row.source_page_result_id is None
        assert ocr_row is not None and ocr_row.source_page_result_id is None
    finally:
        db.close()


def test_tender_wide_without_item_ownership_is_accepted() -> None:
    tender_id = _create_tender("scope detail tender wide")
    document_id = _import_pdf(tender_id, "tender-wide.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Entrega global")
        candidate = _base_candidate(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            domain=SCOPE_DETAIL_DOMAIN_DELIVERABLE,
            artifact_key=f"native-page:{page.id}:v1",
            description="Entregar reporte final",
            applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
        )

        rows = replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=candidate.source_artifact_key,
            candidates=[candidate],
        )
        db.commit()

        assert len(rows) == 1
        persisted = db.get(TenderScopeDetail, rows[0].id)
        assert persisted is not None
        assert persisted.tender_item_id is None
        assert persisted.candidate_item_key is None
        assert persisted.scope_segment_id is None
    finally:
        db.close()


def test_unresolved_ownership_requires_review_required_true() -> None:
    tender_id = _create_tender("scope detail unresolved")
    document_id = _import_pdf(tender_id, "unresolved.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Obligacion sin dueno")
        bad = _base_candidate(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            domain=SCOPE_DETAIL_DOMAIN_SERVICE,
            artifact_key=f"native-page:{page.id}:v1",
            description="Obligacion ambigua",
            applicability=SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
        )

        with pytest.raises(ValueError):
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=bad.source_artifact_key,
                candidates=[replace(bad, review_required=False)],
            )

        rows = replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=bad.source_artifact_key,
            candidates=[replace(bad, review_required=True)],
        )
        db.commit()
        assert len(rows) == 1
    finally:
        db.close()


def test_item_applicability_supports_candidate_key_tender_item_and_scope_segment() -> None:
    tender_id = _create_tender("scope detail item ownership")
    document_id = _import_pdf(tender_id, "item-ownership.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Partida 1")
        item = TenderItem(
            tender_id=tender_id,
            source_document_id=document_id,
            source_page=1,
            document_page_id=page.id,
            normalized_content_id=None,
            item_number="1",
            parent_item_number=None,
            raw_description="Partida uno",
            quantity=None,
            unit=None,
            source_excerpt="Partida 1",
            source_locator="page:1|segment:0",
            extraction_confidence=1.0,
            extraction_status="DETERMINED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-06.1",
            semantic_fingerprint=f"item-{uuid4()}",
        )
        db.add(item)
        db.flush()

        segment = TenderScopeSegment(
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            page_number=1,
            tender_item_id=item.id,
            candidate_item_key="1",
            candidate_item_raw_label="1",
            sequence_index=0,
            scope_domain=None,
            source_method="NATIVE_TEXT",
            link_reason="EXPLICIT_ITEM_START",
            source_locator="page:1|segment:0",
            source_excerpt="Partida 1",
            source_analysis_id=None,
            source_page_result_id=None,
            confidence=None,
            review_required=False,
            semantic_fingerprint=f"segment-{uuid4()}",
        )
        db.add(segment)
        db.flush()

        artifact = f"native-page:{page.id}:ownership"
        rows = replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=artifact,
            candidates=[
                replace(
                    _base_candidate(
                        tender_id=tender_id,
                        document_id=document_id,
                        page_id=page.id,
                        domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                        artifact_key=artifact,
                        description="Con candidate key",
                        applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                    ),
                    candidate_item_key="candidate-1",
                ),
                replace(
                    _base_candidate(
                        tender_id=tender_id,
                        document_id=document_id,
                        page_id=page.id,
                        domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                        artifact_key=artifact,
                        description="Con tender item",
                        applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                    ),
                    tender_item_id=item.id,
                ),
                replace(
                    _base_candidate(
                        tender_id=tender_id,
                        document_id=document_id,
                        page_id=page.id,
                        domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                        artifact_key=artifact,
                        description="Con scope segment",
                        applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                    ),
                    scope_segment_id=segment.id,
                ),
            ],
        )
        db.commit()
        assert len(rows) == 3

        with pytest.raises(ValueError):
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key="native-page:missing-owner",
                candidates=[
                    _base_candidate(
                        tender_id=tender_id,
                        document_id=document_id,
                        page_id=page.id,
                        domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                        artifact_key="native-page:missing-owner",
                        description="Sin ownership",
                        applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                    )
                ],
            )
    finally:
        db.close()


def test_multi_document_additivity_and_artifact_scoped_replacement() -> None:
    tender_id = _create_tender("scope detail multi document")
    doc_a = _import_pdf(tender_id, "bases-multi.pdf")
    doc_b = _import_pdf(tender_id, "anexo-multi.pdf")
    doc_c = _import_pdf(tender_id, "sspa-multi.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, doc_a, 1, "Detalle bases")
        page_b = _seed_page(db, doc_b, 1, "Detalle anexo")
        page_c = _seed_page(db, doc_c, 1, "Detalle sspa")

        key_a = f"native-page:{page_a.id}:a"
        key_b = f"native-page:{page_b.id}:b"
        key_c = f"native-page:{page_c.id}:c"

        for document_id, page_id, domain, artifact_key in (
            (doc_a, page_a.id, SCOPE_DETAIL_DOMAIN_SUPPLY, key_a),
            (doc_b, page_b.id, SCOPE_DETAIL_DOMAIN_SERVICE, key_b),
            (doc_c, page_c.id, SCOPE_DETAIL_DOMAIN_SSPA, key_c),
        ):
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page_id,
                source_artifact_key=artifact_key,
                candidates=[
                        replace(
                            _base_candidate(
                                tender_id=tender_id,
                                document_id=document_id,
                                page_id=page_id,
                                domain=domain,
                                artifact_key=artifact_key,
                                description=f"Detalle {domain}",
                                applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                            ),
                            candidate_item_key="1",
                        )
                ],
            )

        replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=doc_a,
            document_page_id=page_a.id,
            source_artifact_key=key_a,
            candidates=[
                replace(
                    _base_candidate(
                        tender_id=tender_id,
                        document_id=doc_a,
                        page_id=page_a.id,
                        domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                        artifact_key=key_a,
                        description="Detalle bases actualizado",
                        applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
                    ),
                    candidate_item_key="1",
                )
            ],
        )
        db.commit()

        by_doc = db.execute(
            select(TenderScopeDetail.source_document_id, func.count(TenderScopeDetail.id))
            .where(TenderScopeDetail.tender_id == tender_id)
            .group_by(TenderScopeDetail.source_document_id)
        ).all()
        assert sorted(by_doc) == sorted([(doc_a, 1), (doc_b, 1), (doc_c, 1)])
    finally:
        db.close()


@pytest.mark.parametrize(
    "field_name,field_value",
    [
        ("source_locator", ""),
        ("source_excerpt", ""),
        ("source_method", ""),
        ("source_artifact_key", ""),
    ],
)
def test_provenance_required_fields_cannot_be_missing(field_name: str, field_value: str) -> None:
    tender_id = _create_tender("scope detail provenance required")
    document_id = _import_pdf(tender_id, "provenance-required.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Texto")
        base = _base_candidate(
            tender_id=tender_id,
            document_id=document_id,
            page_id=page.id,
            domain=SCOPE_DETAIL_DOMAIN_SERVICE,
            artifact_key=f"native-page:{page.id}:v1",
            description="Servicio",
            applicability=SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
        )
        payload = {field_name: field_value}
        with pytest.raises(ValueError):
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page.id,
                source_artifact_key=(
                    field_value if field_name == "source_artifact_key" else base.source_artifact_key
                )
                or f"native-page:{page.id}:missing",
                candidates=[replace(base, **payload)],
            )
    finally:
        db.close()


def test_quantity_and_unit_raw_are_persisted_without_normalization() -> None:
    tender_id = _create_tender("scope detail raw quantity")
    document_id = _import_pdf(tender_id, "raw-quantity.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "02 PZAS.")
        candidate = replace(
            _base_candidate(
                tender_id=tender_id,
                document_id=document_id,
                page_id=page.id,
                domain=SCOPE_DETAIL_DOMAIN_SUPPLY,
                artifact_key=f"native-page:{page.id}:qty",
                description="Proveer modulos",
                applicability=SCOPE_DETAIL_APPLICABILITY_ITEM,
            ),
            candidate_item_key="1",
            quantity_raw="02",
            unit_raw="PZAS.",
        )

        rows = replace_scope_details_for_artifact(
            db,
            tender_id=tender_id,
            source_document_id=document_id,
            document_page_id=page.id,
            source_artifact_key=candidate.source_artifact_key,
            candidates=[candidate],
        )
        db.commit()

        assert len(rows) == 1
        persisted = db.get(TenderScopeDetail, rows[0].id)
        assert persisted is not None
        assert persisted.quantity_raw == "02"
        assert persisted.unit_raw == "PZAS."
    finally:
        db.close()
