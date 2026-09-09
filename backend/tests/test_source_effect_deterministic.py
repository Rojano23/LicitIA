from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument
from app.source_effect_adapters import SourceEffectEvidenceArtifact
from app.source_effect_deterministic import (
    SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT,
    SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT,
    SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET,
    SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT,
    discover_source_effects_from_evidence,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-DET-{uuid4()}",
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


def test_extracts_partial_effect_with_unique_target_resolution() -> None:
    tender_id = _create_tender("source effect deterministic unique target")
    acting_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige Anexo B, numeral 4.2.")
        _seed_page(db, affected_doc_id, 4, "contenido objetivo")
        db.commit()

        artifact = SourceEffectEvidenceArtifact(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            page_number=1,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{acting_page.id}",
            source_locator="page:1",
            source_text="Se corrige Anexo B, numeral 4.2.",
            source_contract_version="NATIVE_TEXT_V1",
        )

        result = discover_source_effects_from_evidence(db, artifact)

        assert result.status == "MATERIALIZED"
        assert len(result.candidates) == 1
        candidate = result.candidates[0]
        assert candidate.effect_type == "CORRECTS"
        assert candidate.effect_scope == "PARTIAL"
        assert candidate.affected_document_id == affected_doc_id
        assert candidate.affected_locator_raw == "numeral 4.2"
        assert candidate.review_required is False
    finally:
        db.close()


def test_anchor_without_target_context_is_review_required_without_candidates() -> None:
    tender_id = _create_tender("source effect deterministic missing context")
    acting_doc_id = _import_pdf(tender_id, "nota-tecnica.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige el voltaje del transmisor.")
        db.commit()

        artifact = SourceEffectEvidenceArtifact(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            page_number=1,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{acting_page.id}",
            source_locator="page:1",
            source_text="Se corrige el voltaje del transmisor.",
        )

        result = discover_source_effects_from_evidence(db, artifact)

        assert result.status == "REVIEW_REQUIRED"
        assert not result.candidates
        assert SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT in result.diagnostics
    finally:
        db.close()


def test_unresolved_and_ambiguous_target_reference_stay_review_required() -> None:
    tender_id = _create_tender("source effect deterministic unresolved")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    _ = _import_pdf(tender_id, "anexo-b-v1.pdf")
    _ = _import_pdf(tender_id, "anexo-b-v2.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(
            db,
            acting_doc_id,
            1,
            "Se modifica Anexo B en su totalidad.\nSe modifica Convocatoria en su totalidad.",
        )
        db.commit()

        artifact = SourceEffectEvidenceArtifact(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            page_number=1,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{acting_page.id}",
            source_locator="page:1",
            source_text="Se modifica Anexo B en su totalidad. Se modifica Convocatoria en su totalidad.",
        )

        result = discover_source_effects_from_evidence(db, artifact)

        assert result.status == "REVIEW_REQUIRED"
        assert len(result.candidates) == 2
        assert all(candidate.review_required for candidate in result.candidates)
        assert SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT in result.diagnostics
        assert SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT in result.diagnostics
    finally:
        db.close()


def test_same_document_target_forces_review_and_drops_resolved_id() -> None:
    tender_id = _create_tender("source effect deterministic same doc")
    acting_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B en su totalidad.")
        db.commit()

        artifact = SourceEffectEvidenceArtifact(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            page_number=1,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{acting_page.id}",
            source_locator="page:1",
            source_text="Se modifica Anexo B en su totalidad.",
        )

        result = discover_source_effects_from_evidence(db, artifact)

        assert result.status == "REVIEW_REQUIRED"
        assert len(result.candidates) == 1
        assert result.candidates[0].affected_document_id is None
        assert result.candidates[0].review_required is True
        assert SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET in result.diagnostics
    finally:
        db.close()
