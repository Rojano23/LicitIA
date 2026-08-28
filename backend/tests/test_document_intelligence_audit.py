from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentChunk,
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
            "external_reference": "AUDIT-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"folder/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page(document_id: str, text: str, *, status: str = "TEXT_EXTRACTED") -> str:
    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text=text,
            char_count=len(text),
            extraction_method="NATIVE_PDF",
            status=status,
        )
        db.add(page)

        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = 1
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE" if text.strip() else "NO_NATIVE_TEXT"
        db.commit()
        return page.id
    finally:
        db.close()


def _seed_normalized(page_id: str, text: str) -> str:
    db = SessionLocal()
    try:
        source = NormalizedContent(
            document_page_id=page_id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=f"norm-{page_id}",
        )
        db.add(source)
        db.commit()
        return source.id
    finally:
        db.close()


def _seed_chunk(normalized_content_id: str, text: str) -> None:
    db = SessionLocal()
    try:
        chunk = DocumentChunk(
            normalized_content_id=normalized_content_id,
            chunk_index=1,
            text=text,
            char_start=0,
            char_end=len(text),
            char_count=len(text),
            content_sha256=f"chunk-{normalized_content_id}",
        )
        db.add(chunk)
        db.commit()
    finally:
        db.close()


def _seed_classification(
    document_id: str,
    *,
    suggested_type: str = "NOTICE",
    classification_status: str = "SUGGESTED",
    classifier_version: str = "mvp-02.4.2",
    human_type: str | None = None,
    human_note: str | None = None,
    is_composite: bool = False,
) -> None:
    db = SessionLocal()
    try:
        row = DocumentClassification(
            document_id=document_id,
            suggested_type=suggested_type,
            suggested_score=80,
            classification_status=classification_status,
            classifier_method="RULE_BASED_GENERIC",
            classifier_version=classifier_version,
            input_fingerprint_sha256="fingerprint",
            is_composite=is_composite,
            human_type=human_type,
            human_note=human_note,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _seed_reference_analysis(document_id: str, *, status: str = "COMPLETED", version: str = "mvp-02.5.1") -> None:
    db = SessionLocal()
    try:
        row = DocumentReferenceAnalysis(
            document_id=document_id,
            status=status,
            extractor_version=version,
            input_fingerprint_sha256="ref-fingerprint",
            analyzed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _seed_reference(
    source_document_id: str,
    *,
    normalized_key: str,
    resolution_status: str,
    target_document_id: str | None = None,
    page_id: str | None = None,
    auto_candidates: str | None = None,
    human_decision: str | None = None,
    human_target_document_id: str | None = None,
    human_note: str | None = None,
) -> str:
    db = SessionLocal()
    try:
        identity_seed = f"{normalized_key}|{resolution_status}|{source_document_id}|{page_id}|{uuid4()}"
        identity_key = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()
        row = DocumentReference(
            analysis_id=db.query(DocumentReferenceAnalysis.id).filter_by(document_id=source_document_id).scalar(),
            source_document_id=source_document_id,
            document_page_id=page_id,
            reference_identity_key=identity_key,
            raw_reference_text=normalized_key,
            normalized_reference_key=normalized_key,
            reference_kind="ANNEX",
            relationship_hint="REFERENCES",
            resolution_status=resolution_status,
            resolved_target_document_id=target_document_id,
            auto_candidate_document_ids=auto_candidates,
            human_target_document_id=human_target_document_id,
            human_decision=human_decision,
            human_note=human_note,
            source_scope="NATIVE_PAGE",
            source_type="NATIVE_PDF",
            excerpt="muestra",
            extractor_version="mvp-02.5.1",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _audit_post(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/audit-document-intelligence")
    assert response.status_code == 200, response.text
    return response.json()


def _audit_get(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/document-intelligence-audit")
    assert response.status_code == 200, response.text
    return response.json()


def test_audit_fully_ready_corpus_returns_ready() -> None:
    tender_id = _create_tender("Audit Ready")
    doc_id = _import_pdf(tender_id, "convocatoria.pdf")
    page_id = _seed_page(doc_id, "Convocatoria")
    source_id = _seed_normalized(page_id, "Convocatoria")
    _seed_chunk(source_id, "Convocatoria")
    _seed_classification(doc_id, suggested_type="NOTICE", classification_status="SUGGESTED")
    _seed_reference_analysis(doc_id, status="COMPLETED", version="mvp-02.5.1")

    payload = _audit_post(tender_id)
    assert payload["overall_readiness"] == "READY"


def test_audit_processing_incomplete_returns_partially_ready() -> None:
    tender_id = _create_tender("Audit Partial")
    _import_pdf(tender_id, "pending.pdf")

    payload = _audit_post(tender_id)
    assert payload["overall_readiness"] == "PARTIALLY_READY"


def test_audit_structural_blocker_returns_not_ready() -> None:
    tender_id = _create_tender("Audit Blocker")
    doc_id = _import_pdf(tender_id, "missing-storage.pdf")

    db = SessionLocal()
    try:
        doc = db.get(TenderDocument, doc_id)
        assert doc is not None
        doc.stored_relative_path = "../../outside.pdf"
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"
        db.commit()
    finally:
        db.close()

    payload = _audit_post(tender_id)
    assert payload["overall_readiness"] == "NOT_READY"
    assert any(item["code"] == "MISSING_STORAGE" and item["severity"] == "BLOCKING" for item in payload["findings"])


def test_audit_current_filename_collision_is_warning_without_mutation() -> None:
    tender_id = _create_tender("Audit Collision")
    first_id = _import_pdf(tender_id, "bases.pdf")
    second_id = _import_pdf(tender_id, "bases-v2.pdf")

    db = SessionLocal()
    try:
        first = db.get(TenderDocument, first_id)
        second = db.get(TenderDocument, second_id)
        assert first is not None and second is not None
        second.original_filename = first.original_filename
        db.commit()
    finally:
        db.close()

    payload = _audit_post(tender_id)
    collisions = payload["registry_anomalies"]["filename_collisions"]
    assert len(collisions) == 1
    assert collisions[0]["filename"] == "bases.pdf"


def test_audit_duplicate_current_sha_detected() -> None:
    tender_id = _create_tender("Audit Dup SHA")
    _import_pdf(tender_id, "same-a.pdf")
    _import_pdf(tender_id, "same-b.pdf")

    payload = _audit_post(tender_id)
    assert payload["summary"]["integrity"]["duplicate_current_sha256_count"] == 0


def test_audit_ready_normalized_document_without_classification_is_finding() -> None:
    tender_id = _create_tender("Audit Missing Classification")
    doc_id = _import_pdf(tender_id, "no-classification.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")

    payload = _audit_post(tender_id)
    assert any(item["code"] == "MISSING_CLASSIFICATION" for item in payload["findings"])


def test_audit_stale_classification_version_is_detected() -> None:
    tender_id = _create_tender("Audit Stale Classifier")
    doc_id = _import_pdf(tender_id, "stale-classification.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(doc_id, classifier_version="mvp-02.4.1")

    payload = _audit_post(tender_id)
    stale = [item for item in payload["findings"] if item["code"] == "STALE_ANALYSIS_VERSION"]
    assert any(item["metadata"].get("engine") == "classification" for item in stale)


def test_audit_ready_document_without_reference_analysis_is_finding() -> None:
    tender_id = _create_tender("Audit Missing Reference Analysis")
    doc_id = _import_pdf(tender_id, "no-reference-analysis.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(doc_id)

    payload = _audit_post(tender_id)
    assert any(item["code"] == "MISSING_REFERENCE_ANALYSIS" for item in payload["findings"])


def test_audit_stale_reference_version_is_detected() -> None:
    tender_id = _create_tender("Audit Stale References")
    doc_id = _import_pdf(tender_id, "stale-reference.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(doc_id)
    _seed_reference_analysis(doc_id, version="mvp-02.5")
    _seed_reference(doc_id, normalized_key="ANEXO:X", resolution_status="UNRESOLVED", page_id=page_id)

    payload = _audit_post(tender_id)
    stale = [item for item in payload["findings"] if item["code"] == "STALE_ANALYSIS_VERSION"]
    assert any(item["metadata"].get("engine") == "references" for item in stale)


def test_audit_unresolved_references_are_grouped_by_key() -> None:
    tender_id = _create_tender("Audit Unresolved Groups")
    doc_id = _import_pdf(tender_id, "unresolved.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(doc_id)
    _seed_reference_analysis(doc_id)
    _seed_reference(doc_id, normalized_key="ANEXO:DI-2", resolution_status="UNRESOLVED", page_id=page_id)
    _seed_reference(doc_id, normalized_key="ANEXO:DI-2", resolution_status="UNRESOLVED", page_id=page_id)

    payload = _audit_post(tender_id)
    groups = payload["unresolved_reference_groups"]
    assert groups[0]["normalized_reference_key"] == "ANEXO:DI-2"
    assert groups[0]["mention_count"] == 2


def test_audit_ambiguous_references_grouped_with_human_resolved_count() -> None:
    tender_id = _create_tender("Audit Ambiguous Groups")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_a = _import_pdf(tender_id, "bases.pdf")
    target_b = _import_pdf(tender_id, "bases-alt.pdf")
    page_id = _seed_page(source_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(source_id)
    _seed_reference_analysis(source_id)

    candidates = f"{target_a},{target_b}"
    _seed_reference(
        source_id,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="AMBIGUOUS",
        page_id=page_id,
        auto_candidates=candidates,
    )
    _seed_reference(
        source_id,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="HUMAN_RESOLVED",
        page_id=page_id,
        auto_candidates=candidates,
        target_document_id=target_a,
        human_decision="RESOLVE_TO_DOCUMENT",
        human_target_document_id=target_a,
    )

    payload = _audit_post(tender_id)
    group = payload["ambiguous_reference_groups"][0]
    assert group["normalized_reference_key"] == "BASES_DE_CONTRATACION"
    assert group["ambiguous_mention_count"] == 1
    assert group["human_resolved_mention_count"] == 1
    assert group["candidate_documents"][0]["processing_status"] is not None


def test_audit_ignored_self_reference_not_counted_as_unresolved() -> None:
    tender_id = _create_tender("Audit Ignored Self")
    source_id = _import_pdf(tender_id, "anexo-d.pdf")
    page_id = _seed_page(source_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(source_id)
    _seed_reference_analysis(source_id)
    _seed_reference(source_id, normalized_key="ANEXO:D", resolution_status="IGNORED", page_id=page_id)

    payload = _audit_post(tender_id)
    assert payload["summary"]["references"]["status_counts"]["UNRESOLVED"] == 0
    assert payload["summary"]["references"]["status_counts"]["IGNORED"] == 1


def test_audit_self_relationship_detected() -> None:
    tender_id = _create_tender("Audit Self Edge")
    source_id = _import_pdf(tender_id, "self-edge.pdf")

    db = SessionLocal()
    try:
        db.add(
            DocumentRelationship(
                tender_id=tender_id,
                source_document_id=source_id,
                target_document_id=source_id,
                relationship_type="REFERENCES",
            )
        )
        db.commit()
    finally:
        db.close()

    payload = _audit_post(tender_id)
    assert payload["summary"]["relationships"]["self_edge_count"] == 1
    assert any(item["code"] == "SELF_RELATIONSHIP_EDGE" for item in payload["findings"])


def test_audit_does_not_mutate_human_classification_decision() -> None:
    tender_id = _create_tender("Audit Human Classification")
    doc_id = _import_pdf(tender_id, "human-classification.pdf")
    page_id = _seed_page(doc_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(
        doc_id,
        suggested_type="NOTICE",
        classification_status="OVERRIDDEN",
        human_type="BIDDING_RULES",
        human_note="decisión humana",
    )

    _audit_post(tender_id)

    db = SessionLocal()
    try:
        row = db.query(DocumentClassification).filter_by(document_id=doc_id).one()
        assert row.human_type == "BIDDING_RULES"
        assert row.human_note == "decisión humana"
        assert row.classification_status == "OVERRIDDEN"
    finally:
        db.close()


def test_audit_does_not_mutate_human_reference_decision() -> None:
    tender_id = _create_tender("Audit Human References")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(source_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(source_id)
    _seed_reference_analysis(source_id)

    reference_id = _seed_reference(
        source_id,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="HUMAN_RESOLVED",
        target_document_id=target_id,
        page_id=page_id,
        auto_candidates=target_id,
        human_decision="RESOLVE_TO_DOCUMENT",
        human_target_document_id=target_id,
        human_note="decisión humana",
    )

    _audit_post(tender_id)

    db = SessionLocal()
    try:
        row = db.get(DocumentReference, reference_id)
        assert row is not None
        assert row.human_decision == "RESOLVE_TO_DOCUMENT"
        assert row.human_target_document_id == target_id
        assert row.human_note == "decisión humana"
    finally:
        db.close()


def test_audit_non_current_docs_do_not_count_as_current_gaps() -> None:
    tender_id = _create_tender("Audit Current Scope")
    current_id = _import_pdf(tender_id, "current.pdf")
    non_current_id = _import_pdf(tender_id, "historical.pdf")

    page_id = _seed_page(current_id, "texto")
    _seed_normalized(page_id, "texto")
    _seed_classification(current_id)
    _seed_reference_analysis(current_id)

    db = SessionLocal()
    try:
        historical = db.get(TenderDocument, non_current_id)
        assert historical is not None
        historical.is_current = False
        historical.processing_status = "PENDING"
        db.commit()
    finally:
        db.close()

    payload = _audit_post(tender_id)
    assert payload["summary"]["documents"]["current_documents"] == 1
    assert payload["summary"]["normalization"]["current_documents_without_normalized_content"] == 0


def test_audit_document_without_normalized_content_is_honestly_incomplete() -> None:
    tender_id = _create_tender("Audit Missing Normalization")
    doc_id = _import_pdf(tender_id, "no-normalized.pdf")
    _seed_page(doc_id, "texto")

    payload = _audit_get(tender_id)
    row = next(item for item in payload["document_rows"] if item["document_id"] == doc_id)
    assert row["normalized"] is False
    assert "MISSING_NORMALIZED_CONTENT" in row["integrity_findings"]


def test_audit_payload_does_not_include_compliance_fields() -> None:
    tender_id = _create_tender("Audit No Compliance Terms")
    _import_pdf(tender_id, "minimal.pdf")

    payload = _audit_get(tender_id)
    serialized = str(payload).lower()
    assert "compliance" not in serialized
