from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, PageOcrResult, TenderDocument
from app.source_effect_adapters import (
    SourceEffectEvidenceArtifact,
    enumerate_source_effect_evidence_for_document,
    resolve_source_effect_evidence_artifact,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-ADAPTER-{uuid4()}",
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


def _seed_vision_analysis(
    db,
    *,
    tender_id: str,
    document_id: str,
    input_fingerprint: str,
) -> DocumentVisionAnalysis:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status="COMPLETED",
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b-instruct",
        prompt_version="vision-source-effects-001",
        input_fingerprint_sha256=input_fingerprint,
    )
    db.add(analysis)
    db.flush()
    return analysis


def _seed_vision_page_result(
    db,
    *,
    analysis_id: str,
    page: DocumentPage,
    plain_text: str,
) -> DocumentVisionPageResult:
    page_result = DocumentVisionPageResult(
        analysis_id=analysis_id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=hashlib.sha256(f"image|{page.id}|{uuid4()}".encode("utf-8")).hexdigest(),
        status="COMPLETED",
        raw_response_text=None,
        structured_json=None,
        extracted_markdown=None,
        extracted_plain_text=plain_text,
        warnings=[],
        processing_time_ms=5,
    )
    db.add(page_result)
    db.flush()
    return page_result


def test_resolve_native_artifact_reconstructs_evidence() -> None:
    tender_id = _create_tender("source effect adapter native")
    document_id = _import_pdf(tender_id, "adapter-native.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "Se modifica el Anexo B en su totalidad.")
        db.commit()

        artifact = resolve_source_effect_evidence_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=document_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{page.id}",
        )

        assert isinstance(artifact, SourceEffectEvidenceArtifact)
        assert artifact.source_method == "NATIVE"
        assert artifact.source_locator == "page:1"
        assert "Anexo B" in artifact.source_text
    finally:
        db.close()


def test_resolve_ocr_artifact_reconstructs_locator() -> None:
    tender_id = _create_tender("source effect adapter ocr")
    document_id = _import_pdf(tender_id, "adapter-ocr.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 2, "")
        ocr = PageOcrResult(
            document_page_id=page.id,
            engine="tesseract",
            engine_version="5.5.0",
            language="es",
            text="Se corrige Anexo B, numeral 4.2.",
            scope="FULL_PAGE",
            region_id=None,
            status="OCR_TEXT_EXTRACTED",
        )
        db.add(ocr)
        db.commit()

        artifact = resolve_source_effect_evidence_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=document_id,
            document_page_id=page.id,
            source_method="OCR",
            source_artifact_key=f"ocr-result:{ocr.id}",
        )

        assert artifact.source_method == "OCR"
        assert artifact.source_contract_version == "5.5.0"
        assert artifact.source_locator == "page:2|ocr_scope:FULL_PAGE"
    finally:
        db.close()


def test_enumerate_vision_lineage_marks_old_result_as_deselected() -> None:
    tender_id = _create_tender("source effect adapter vision lineage")
    document_id = _import_pdf(tender_id, "adapter-vision-lineage.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "texto nativo")
        fingerprint = hashlib.sha256(f"lineage|{document_id}|{page.id}".encode("utf-8")).hexdigest()
        analysis = _seed_vision_analysis(
            db,
            tender_id=tender_id,
            document_id=document_id,
            input_fingerprint=fingerprint,
        )

        older = _seed_vision_page_result(
            db,
            analysis_id=analysis.id,
            page=page,
            plain_text="Se modifica el Anexo B en su totalidad.",
        )
        newer = _seed_vision_page_result(
            db,
            analysis_id=analysis.id,
            page=page,
            plain_text="Sin efecto documental.",
        )
        db.commit()

        rows = enumerate_source_effect_evidence_for_document(
            db,
            tender_id=tender_id,
            document_id=document_id,
            pages=[page],
        )

        active_keys = {item.artifact.source_artifact_key for item in rows.active}
        deselected_keys = {item.artifact.source_artifact_key for item in rows.deselected}

        assert f"vision-page-result:{newer.id}" in active_keys
        assert f"vision-page-result:{older.id}" in deselected_keys
    finally:
        db.close()


def test_resolve_invalid_vision_key_fails_closed() -> None:
    tender_id = _create_tender("source effect adapter invalid")
    document_id = _import_pdf(tender_id, "adapter-invalid.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, document_id, 1, "texto")
        db.commit()

        try:
            resolve_source_effect_evidence_artifact(
                db,
                tender_id=tender_id,
                acting_document_id=document_id,
                document_page_id=page.id,
                source_method="VISION",
                source_artifact_key="vision-page-result:missing",
            )
            assert False, "Expected ValueError"
        except ValueError as exc:
            assert "does not exist" in str(exc)
    finally:
        db.close()
