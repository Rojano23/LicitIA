from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    NormalizedContent,
    TenderDocument,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "RB-001",
        },
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


def _seed_page(document_id: str, page_number: int, text: str) -> str:
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
        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = max(doc.page_count, page_number)
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"
        db.commit()
        return page.id
    finally:
        db.close()


def _seed_normalized(page_id: str, text: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            NormalizedContent(
                document_page_id=page_id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text=text,
                char_count=len(text),
                content_sha256=hashlib.sha256(f"norm-{page_id}-{text}".encode("utf-8")).hexdigest(),
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_classification(document_id: str, *, human: bool = False) -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=document_id,
                suggested_type="NOTICE",
                suggested_score=80,
                classification_status="OVERRIDDEN" if human else "SUGGESTED",
                classifier_method="RULE_BASED_GENERIC",
                classifier_version="mvp-02.4.2",
                input_fingerprint_sha256="fingerprint",
                is_composite=False,
                human_type="BIDDING_RULES" if human else None,
                human_note="manual" if human else None,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_reference_analysis(document_id: str, *, status: str = "COMPLETED") -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentReferenceAnalysis(
                document_id=document_id,
                status=status,
                extractor_version="mvp-02.5.1",
                input_fingerprint_sha256="fp",
                analyzed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_reference(
    source_document_id: str,
    *,
    page_id: str,
    normalized_key: str,
    resolution_status: str,
    relationship_hint: str = "REFERENCES",
    target_document_id: str | None = None,
    auto_candidates: str | None = None,
    human_decision: str | None = None,
    human_target_document_id: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        analysis_id = db.execute(
            select(DocumentReferenceAnalysis.id).where(DocumentReferenceAnalysis.document_id == source_document_id)
        ).scalar_one()
        identity_key = hashlib.sha256(
            f"{source_document_id}|{page_id}|{normalized_key}|{resolution_status}|{uuid4()}".encode("utf-8")
        ).hexdigest()
        db.add(
            DocumentReference(
                analysis_id=analysis_id,
                source_document_id=source_document_id,
                document_page_id=page_id,
                reference_identity_key=identity_key,
                raw_reference_text=normalized_key,
                normalized_reference_key=normalized_key,
                reference_kind="ANNEX",
                relationship_hint=relationship_hint,
                resolution_status=resolution_status,
                resolved_target_document_id=target_document_id,
                auto_candidate_document_ids=auto_candidates,
                human_decision=human_decision,
                human_target_document_id=human_target_document_id,
                source_scope="NATIVE_PAGE",
                source_type="NATIVE_PDF",
                excerpt="evidencia",
                extractor_version="mvp-02.5.1",
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_relationship(tender_id: str, source_document_id: str, target_document_id: str, *, relationship_type: str = "REFERENCES") -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentRelationship(
                tender_id=tender_id,
                source_document_id=source_document_id,
                target_document_id=target_document_id,
                relationship_type=relationship_type,
            )
        )
        db.commit()
    finally:
        db.close()


def _get_baseline(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/relationship-baseline")
    assert response.status_code == 200, response.text
    return response.json()


def _get_audit(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/document-intelligence-audit")
    assert response.status_code == 200, response.text
    return response.json()


def test_relationship_baseline_reuses_audit_totals() -> None:
    tender_id = _create_tender("RB totals")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_id = _import_pdf(tender_id, "bases.pdf")

    source_page = _seed_page(source_id, 1, "texto fuente")
    _seed_normalized(source_page, "texto fuente")
    _seed_classification(source_id)
    _seed_classification(target_id)
    _seed_reference_analysis(source_id)

    _seed_reference(
        source_id,
        page_id=source_page,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="AUTO_RESOLVED",
        target_document_id=target_id,
        auto_candidates=target_id,
    )
    _seed_relationship(tender_id, source_id, target_id)

    baseline = _get_baseline(tender_id)
    audit = _get_audit(tender_id)

    assert baseline["counts"]["relationship_edge_count"] == audit["summary"]["relationships"]["total_edges"]
    assert baseline["counts"]["duplicate_edge_count"] == audit["summary"]["relationships"]["duplicate_edge_count"]
    assert baseline["counts"]["self_edge_count"] == audit["summary"]["relationships"]["self_edge_count"]
    assert baseline["reference_status_counts"] == audit["summary"]["references"]["status_counts"]


def test_relationship_baseline_document_map_supports_pages_and_origin() -> None:
    tender_id = _create_tender("RB map")
    source_id = _import_pdf(tender_id, "anexos.pdf")
    target_id = _import_pdf(tender_id, "anexo-c.pdf")

    page1 = _seed_page(source_id, 1, "texto 1")
    page2 = _seed_page(source_id, 2, "texto 2")
    _seed_normalized(page1, "texto 1")
    _seed_normalized(page2, "texto 2")
    _seed_classification(source_id)
    _seed_classification(target_id)
    _seed_reference_analysis(source_id)

    _seed_reference(
        source_id,
        page_id=page1,
        normalized_key="ANEXO:C",
        resolution_status="AUTO_RESOLVED",
        target_document_id=target_id,
        auto_candidates=target_id,
    )
    _seed_reference(
        source_id,
        page_id=page2,
        normalized_key="ANEXO:C",
        resolution_status="HUMAN_RESOLVED",
        target_document_id=target_id,
        auto_candidates=target_id,
        human_decision="RESOLVE_TO_DOCUMENT",
        human_target_document_id=target_id,
    )
    _seed_relationship(tender_id, source_id, target_id)

    baseline = _get_baseline(tender_id)
    assert len(baseline["document_map"]) == 1
    entry = baseline["document_map"][0]
    assert entry["source_document_id"] == source_id
    assert entry["target_document_id"] == target_id
    assert entry["supporting_reference_count"] == 2
    assert entry["supporting_pages"] == [1, 2]
    assert entry["resolution_origin"] == "AUTO_HUMAN"


def test_relationship_baseline_exposes_unresolved_and_ambiguous_groups() -> None:
    tender_id = _create_tender("RB groups")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_a = _import_pdf(tender_id, "bases-a.pdf")
    target_b = _import_pdf(tender_id, "bases-b.pdf")

    page = _seed_page(source_id, 1, "texto")
    _seed_normalized(page, "texto")
    _seed_classification(source_id)
    _seed_reference_analysis(source_id)

    _seed_reference(
        source_id,
        page_id=page,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="AMBIGUOUS",
        auto_candidates=f"{target_a},{target_b}",
    )
    _seed_reference(
        source_id,
        page_id=page,
        normalized_key="ANEXO:DI-2",
        resolution_status="UNRESOLVED",
    )

    baseline = _get_baseline(tender_id)
    assert baseline["counts"]["ambiguous_reference_groups_count"] == 1
    assert baseline["counts"]["unresolved_reference_groups_count"] == 1
    assert baseline["ambiguous_reference_groups"][0]["normalized_reference_key"] == "BASES_DE_CONTRATACION"
    assert baseline["unresolved_reference_groups"][0]["normalized_reference_key"] == "ANEXO:DI-2"


def test_relationship_baseline_does_not_mutate_human_states() -> None:
    tender_id = _create_tender("RB human invariants")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_id = _import_pdf(tender_id, "bases.pdf")

    page = _seed_page(source_id, 1, "texto")
    _seed_normalized(page, "texto")
    _seed_classification(source_id, human=True)
    _seed_reference_analysis(source_id)
    _seed_reference(
        source_id,
        page_id=page,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="HUMAN_RESOLVED",
        target_document_id=target_id,
        auto_candidates=target_id,
        human_decision="RESOLVE_TO_DOCUMENT",
        human_target_document_id=target_id,
    )
    _seed_relationship(tender_id, source_id, target_id)

    db = SessionLocal()
    try:
        cls_before = db.execute(
            select(
                DocumentClassification.document_id,
                DocumentClassification.classification_status,
                DocumentClassification.human_type,
                DocumentClassification.human_note,
            ).where(DocumentClassification.document_id == source_id)
        ).all()
        refs_before = db.execute(
            select(
                DocumentReference.id,
                DocumentReference.resolution_status,
                DocumentReference.human_decision,
                DocumentReference.human_target_document_id,
                DocumentReference.human_note,
            ).where(DocumentReference.source_document_id == source_id)
        ).all()
    finally:
        db.close()

    _get_baseline(tender_id)

    db = SessionLocal()
    try:
        cls_after = db.execute(
            select(
                DocumentClassification.document_id,
                DocumentClassification.classification_status,
                DocumentClassification.human_type,
                DocumentClassification.human_note,
            ).where(DocumentClassification.document_id == source_id)
        ).all()
        refs_after = db.execute(
            select(
                DocumentReference.id,
                DocumentReference.resolution_status,
                DocumentReference.human_decision,
                DocumentReference.human_target_document_id,
                DocumentReference.human_note,
            ).where(DocumentReference.source_document_id == source_id)
        ).all()
    finally:
        db.close()

    assert cls_before == cls_after
    assert refs_before == refs_after


def test_relationship_baseline_not_found_tender() -> None:
    response = client.get("/tenders/does-not-exist/relationship-baseline")
    assert response.status_code == 404
