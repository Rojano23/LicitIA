import os
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
import app.ollama_vision as ollama_vision_module
from app.models import (
    DocumentClassification,
    DocumentClassificationCandidate,
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    DocumentClassificationTag,
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    PageOcrResult,
    TenderDocument,
)

client = TestClient(app)

ALLOWED_FUNCTIONAL_TAGS = {
    "TECHNICAL",
    "COMMERCIAL",
    "ECONOMIC",
    "ADMINISTRATIVE",
    "LEGAL",
    "CONTRACTUAL",
    "SCHEDULE",
    "EXPERIENCE",
    "PERSONNEL",
    "SAFETY",
    "GUARANTEE",
    "REGISTRATION",
    "INSTRUCTIONS",
}

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260827_document_classification_candidates.py"


def _create_tender(title: str = "Document Tender") -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "DOC-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_classification_pdf(tender_id: str, filename: str = "classification.pdf") -> str:
    unique_payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, unique_payload, "application/pdf"))],
        data={"source_relative_paths": f"folder/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _import_vision_pdf(tender_id: str, filename: str, pages: list[str]) -> str:
    import fitz

    pdf_document = fitz.open()
    for text in pages:
        page = pdf_document.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = pdf_document.write()
    pdf_document.close()

    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, pdf_bytes, "application/pdf"))],
        data={"source_relative_paths": f"folder/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_normalized_lines(document_id: str, lines: list[str]) -> None:
    db = SessionLocal()
    try:
        for page_number, text in enumerate(lines, start=1):
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
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    engine=None,
                    normalized_text=text,
                    char_count=len(text),
                    content_sha256=f"seed-{document_id}-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()


def _classify(tender_id: str, document_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_references(tender_id: str, document_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/documents/{document_id}/analyze-references")
    assert response.status_code == 200, response.text
    return response.json()


def _get_references(tender_id: str, document_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/references")
    assert response.status_code == 200, response.text
    return response.json()


def _load_candidate_migration_module():
    spec = importlib.util.spec_from_file_location("candidate_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_duplicate_and_name_conflict() -> None:
    tender_id = _create_tender("Document Integrity")
    payload = b"alpha content\nline 2\n"
    sha256 = hashlib.sha256(payload).hexdigest()

    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("alpha.txt", payload, "text/plain"))],
        data={"source_relative_paths": "folder/alpha.txt"},
    )
    assert response.status_code == 200, response.text
    result = response.json()[0]
    assert result["status"] == "IMPORTED"
    assert result["sha256"] == sha256

    duplicate_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("alpha.txt", payload, "text/plain"))],
        data={"source_relative_paths": "folder/alpha.txt"},
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate_result = duplicate_response.json()[0]
    assert duplicate_result["status"] == "DUPLICATE"

    conflict_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("alpha.txt", b"different content\n", "text/plain"))],
        data={"source_relative_paths": "folder/alpha.txt"},
    )
    assert conflict_response.status_code == 200, conflict_response.text
    conflict_result = conflict_response.json()[0]
    assert conflict_result["status"] == "NAME_CONFLICT"

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    payload_documents = documents.json()
    assert len(payload_documents) == 1
    assert payload_documents[0]["sha256"] == sha256
    assert payload_documents[0]["original_filename"] == "alpha.txt"


def test_file_stays_unchanged_and_metadata_persists() -> None:
    tender_id = _create_tender("Document Storage")
    original_path = "folder/report.pdf"
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"

    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("report.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": original_path},
    )
    assert response.status_code == 200, response.text
    import_result = response.json()[0]
    assert import_result["status"] == "IMPORTED"
    assert import_result["stored_relative_path"].startswith("tenders/")

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    document = documents.json()[0]
    assert document["file_size_bytes"] == len(payload)
    assert document["mime_type"] == "application/pdf"
    assert document["source_relative_path"] == original_path


def test_name_conflict_can_be_imported_as_independent_document() -> None:
    tender_id = _create_tender("Conflict Independent")

    first_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("conflict.txt", b"first version\n", "text/plain"))],
        data={"source_relative_paths": "folder/conflict.txt"},
    )
    assert first_response.status_code == 200, first_response.text
    first_result = first_response.json()[0]
    assert first_result["status"] == "IMPORTED"

    second_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("conflict.txt", b"second version\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/conflict.txt",
            "conflict_action": "IMPORT_INDEPENDENT",
        },
    )
    assert second_response.status_code == 200, second_response.text
    second_result = second_response.json()[0]
    assert second_result["status"] == "IMPORTED"

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    payload_documents = documents.json()
    assert len(payload_documents) == 2
    assert {item["sha256"] for item in payload_documents} == {
        hashlib.sha256(b"first version\n").hexdigest(),
        hashlib.sha256(b"second version\n").hexdigest(),
    }
    assert all(item["revision_number"] == 1 for item in payload_documents)
    assert all(item["revision_of_document_id"] is None for item in payload_documents)
    assert all(item["is_current"] is True for item in payload_documents)


def test_name_conflict_can_create_revision_chain() -> None:
    tender_id = _create_tender("Conflict Revision")

    first_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("revision.txt", b"base revision\n", "text/plain"))],
        data={"source_relative_paths": "folder/revision.txt"},
    )
    assert first_response.status_code == 200, first_response.text
    first_document = first_response.json()[0]
    first_document_id = first_document["document_id"]
    assert first_document["status"] == "IMPORTED"
    assert first_document.get("conflict_resolution_action") is None

    second_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("revision.txt", b"revised content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/revision.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_document_id,
        },
    )
    assert second_response.status_code == 200, second_response.text
    second_result = second_response.json()[0]
    assert second_result["status"] == "IMPORTED"
    assert second_result["conflict_resolution_action"] == "NEW_REVISION"

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    payload_documents = documents.json()
    assert len(payload_documents) == 2

    by_id = {item["id"]: item for item in payload_documents}
    old_document = by_id[first_document_id]
    new_document = next(item for item in payload_documents if item["id"] != first_document_id)

    assert old_document["revision_number"] == 1
    assert old_document["is_current"] is False
    assert old_document["revision_of_document_id"] is None
    assert old_document["conflict_resolution_action"] is None

    assert new_document["revision_number"] == 2
    assert new_document["is_current"] is True
    assert new_document["revision_of_document_id"] == first_document_id
    assert new_document["conflict_resolution_action"] == "NEW_REVISION"
    assert new_document["sha256"] == hashlib.sha256(b"revised content\n").hexdigest()

    third_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("revision.txt", b"third revision\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/revision.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": new_document["id"],
        },
    )
    assert third_response.status_code == 200, third_response.text
    third_result = third_response.json()[0]
    assert third_result["status"] == "IMPORTED"
    assert third_result["conflict_resolution_action"] == "NEW_REVISION"

    final_documents = client.get(f"/tenders/{tender_id}/documents")
    assert final_documents.status_code == 200, final_documents.text
    final_payload = final_documents.json()
    assert len(final_payload) == 3

    current_docs = [item for item in final_payload if item["is_current"] is True]
    assert len(current_docs) == 1
    assert current_docs[0]["revision_number"] == 3
    assert current_docs[0]["revision_of_document_id"] == new_document["id"]
    assert all(item["is_current"] is False for item in final_payload if item["id"] != current_docs[0]["id"])


def test_superseded_revision_target_is_rejected_and_cross_tender_target_is_rejected() -> None:
    tender_a = _create_tender("Superseded Target")
    tender_b = _create_tender("Other Tender")

    base_response = client.post(
        f"/tenders/{tender_a}/documents/import",
        files=[("files", ("target.txt", b"base content\n", "text/plain"))],
        data={"source_relative_paths": "folder/target.txt"},
    )
    assert base_response.status_code == 200, base_response.text
    base_document_id = base_response.json()[0]["document_id"]

    first_revision = client.post(
        f"/tenders/{tender_a}/documents/import",
        files=[("files", ("target.txt", b"next content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/target.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": base_document_id,
        },
    )
    assert first_revision.status_code == 200, first_revision.text
    revision_id = first_revision.json()[0]["document_id"]

    rejected_response = client.post(
        f"/tenders/{tender_a}/documents/import",
        files=[("files", ("target.txt", b"forbidden content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/target.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": base_document_id,
        },
    )
    assert rejected_response.status_code == 400, rejected_response.text
    assert "Only the current revision can receive a new revision" in rejected_response.text

    other_tender_doc = client.post(
        f"/tenders/{tender_b}/documents/import",
        files=[("files", ("target.txt", b"other tender content\n", "text/plain"))],
        data={"source_relative_paths": "folder/target.txt"},
    )
    assert other_tender_doc.status_code == 200, other_tender_doc.text
    other_tender_document_id = other_tender_doc.json()[0]["document_id"]

    cross_tender_response = client.post(
        f"/tenders/{tender_a}/documents/import",
        files=[("files", ("target.txt", b"cross content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/target.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": other_tender_document_id,
        },
    )
    assert cross_tender_response.status_code == 400, cross_tender_response.text

    final_documents = client.get(f"/tenders/{tender_a}/documents")
    assert final_documents.status_code == 200, final_documents.text
    final_payload = final_documents.json()
    assert len(final_payload) == 2
    current_docs = [item for item in final_payload if item["is_current"] is True]
    assert len(current_docs) == 1
    assert current_docs[0]["id"] == revision_id


def test_conflict_actions_never_bypass_duplicate_hash_protection() -> None:
    tender_id = _create_tender("Duplicate Guard")
    payload = b"shared content\n"

    first_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("shared.txt", payload, "text/plain"))],
        data={"source_relative_paths": "folder/shared.txt"},
    )
    assert first_response.status_code == 200, first_response.text
    first_document_id = first_response.json()[0]["document_id"]

    duplicate_independent = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("shared.txt", payload, "text/plain"))],
        data={
            "source_relative_paths": "folder/shared.txt",
            "conflict_action": "IMPORT_INDEPENDENT",
        },
    )
    assert duplicate_independent.status_code == 200, duplicate_independent.text
    assert duplicate_independent.json()[0]["status"] == "DUPLICATE"

    second_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("shared.txt", b"changed content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/shared.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_document_id,
        },
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()[0]["status"] == "IMPORTED"

    duplicate_revision = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("shared.txt", b"changed content\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/shared.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_document_id,
        },
    )
    assert duplicate_revision.status_code == 200, duplicate_revision.text
    assert duplicate_revision.json()[0]["status"] == "DUPLICATE"


def test_failed_new_revision_does_not_leave_orphan_state(monkeypatch) -> None:
    tender_id = _create_tender("Failure Consistency")

    first_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("pending.txt", b"old version\n", "text/plain"))],
        data={"source_relative_paths": "folder/pending.txt"},
    )
    assert first_response.status_code == 200, first_response.text
    first_document_id = first_response.json()[0]["document_id"]

    original_store = __import__("app.main", fromlist=["_store_uploaded_file"])._store_uploaded_file

    def broken_store(*args, **kwargs):
        stored_relative_path, source_relative_path = original_store(*args, **kwargs)
        storage_path = __import__("app.main", fromlist=["get_licitia_data_root"]).get_licitia_data_root() / stored_relative_path
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(b"partial content")
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr("app.main._store_uploaded_file", broken_store)

    failing_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("pending.txt", b"new version\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/pending.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_document_id,
        },
    )
    assert failing_response.status_code == 200, failing_response.text
    assert failing_response.json()[0]["status"] == "FAILED"

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    payload_documents = documents.json()
    assert len(payload_documents) == 1
    assert payload_documents[0]["id"] == first_document_id
    assert payload_documents[0]["is_current"] is True
    assert payload_documents[0]["revision_number"] == 1

    stored_paths = [item["stored_relative_path"] for item in payload_documents]
    assert stored_paths[0].startswith("tenders/")


def test_import_independent_persists_explicit_human_decision() -> None:
    tender_id = _create_tender("Independent Traceability")

    first_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("trace.txt", b"first trace\n", "text/plain"))],
        data={"source_relative_paths": "folder/trace.txt"},
    )
    assert first_response.status_code == 200, first_response.text
    first_document_id = first_response.json()[0]["document_id"]

    second_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("trace.txt", b"second trace\n", "text/plain"))],
        data={
            "source_relative_paths": "folder/trace.txt",
            "conflict_action": "IMPORT_INDEPENDENT",
        },
    )
    assert second_response.status_code == 200, second_response.text
    second_result = second_response.json()[0]
    assert second_result["status"] == "IMPORTED"
    assert second_result["conflict_resolution_action"] == "IMPORT_INDEPENDENT"

    documents = client.get(f"/tenders/{tender_id}/documents")
    assert documents.status_code == 200, documents.text
    payload_documents = documents.json()
    assert len(payload_documents) == 2
    assert {item["id"] for item in payload_documents} == {first_document_id, second_result["document_id"]}
    assert all(item["revision_of_document_id"] is None for item in payload_documents)
    assert all(item["is_current"] is True for item in payload_documents)
    assert all(item["conflict_resolution_action"] in {None, "IMPORT_INDEPENDENT"} for item in payload_documents)
    assert any(item["conflict_resolution_action"] == "IMPORT_INDEPENDENT" for item in payload_documents)


def test_pdf_pages_are_extracted_and_persisted() -> None:
    import fitz

    tender_id = _create_tender("PDF Extraction")
    pdf_document = fitz.open()
    page_one = pdf_document.new_page()
    page_one.insert_text((72, 72), "Tender title: Extraction test")
    page_two = pdf_document.new_page()
    page_two.insert_text((72, 72), "Second page with obligation details")
    pdf_bytes = pdf_document.write()
    pdf_document.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("report.pdf", pdf_bytes, "application/pdf"))],
        data={"source_relative_paths": "folder/report.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text
    extraction = extract_response.json()
    assert extraction["processing_status"] == "TEXT_EXTRACTION_COMPLETE"
    assert extraction["page_count"] == 2

    pages_response = client.get(f"/documents/{document_id}/pages")
    assert pages_response.status_code == 200, pages_response.text
    pages = pages_response.json()
    assert len(pages) == 2
    assert [page["page_number"] for page in pages] == [1, 2]
    assert any("Extraction test" in page["text"] for page in pages)
    assert any("obligation details" in page["text"] for page in pages)


def test_pdf_extraction_tracks_native_text_metadata_and_tender_scope() -> None:
    import fitz

    tender_id = _create_tender("PDF Metadata")
    pdf_document = fitz.open()
    page_one = pdf_document.new_page()
    page_one.insert_text((72, 72), "Mandatory obligation section")
    pdf_document.new_page()
    pdf_bytes = pdf_document.write()
    pdf_document.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("metadata.pdf", pdf_bytes, "application/pdf"))],
        data={"source_relative_paths": "folder/metadata.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text
    extraction = extract_response.json()
    assert extraction["processing_status"] == "TEXT_EXTRACTION_PARTIAL"
    assert extraction["page_count"] == 2

    pages_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/pages")
    assert pages_response.status_code == 200, pages_response.text
    pages = pages_response.json()
    assert len(pages) == 2
    assert pages[0]["status"] == "TEXT_EXTRACTED"
    assert pages[0]["char_count"] > 0
    assert pages[0]["extraction_method"] == "NATIVE_PDF"
    assert pages[1]["status"] == "NO_TEXT"
    assert pages[1]["char_count"] == 0


def test_blank_pdf_is_marked_as_no_native_text() -> None:
    import fitz

    tender_id = _create_tender("Blank PDF")
    blank_pdf = fitz.open()
    blank_pdf.new_page()
    payload = blank_pdf.write()
    blank_pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("blank.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/blank.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text
    assert extract_response.json()["processing_status"] == "NO_NATIVE_TEXT"

    pages_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/pages")
    assert pages_response.status_code == 200, pages_response.text
    pages = pages_response.json()
    assert pages[0]["status"] == "NO_TEXT"
    assert pages[0]["char_count"] == 0
    assert pages[0]["ocr_results"] == []


def test_tender_pages_include_persisted_ocr_alternatives() -> None:
    import fitz

    tender_id = _create_tender("OCR Page Read")
    pdf = fitz.open()
    pdf.new_page()
    payload = pdf.write()
    pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("ocr-read.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/ocr-read.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text

    db = SessionLocal()
    try:
        page = db.query(DocumentPage).filter_by(document_id=document_id).one()
        db.add_all(
            [
                PageOcrResult(
                    document_page_id=page.id,
                    engine="TESSERACT",
                    engine_version="5.5.3",
                    language="spa+eng",
                    text="OCR text from Tesseract",
                    status="OCR_TEXT_EXTRACTED",
                    confidence=0.98,
                    processing_time_ms=250,
                    warnings=None,
                ),
                PageOcrResult(
                    document_page_id=page.id,
                    engine="PADDLEOCR",
                    engine_version="2.0",
                    language="es",
                    text="OCR text from PaddleOCR",
                    status="OCR_TEXT_EXTRACTED",
                    confidence=0.95,
                    processing_time_ms=320,
                    warnings=None,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    pages_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/pages")
    assert pages_response.status_code == 200, pages_response.text
    page_payload = pages_response.json()[0]
    assert page_payload["status"] == "NO_TEXT"
    assert page_payload["ocr_results"]
    assert {result["engine"] for result in page_payload["ocr_results"]} == {"TESSERACT", "PADDLEOCR"}
    assert any(result["status"] == "OCR_TEXT_EXTRACTED" for result in page_payload["ocr_results"])


def test_pdf_extraction_rejects_non_pdf_documents() -> None:
    tender_id = _create_tender("Invalid Extraction")
    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("notes.txt", b"hello world", "text/plain"))],
        data={"source_relative_paths": "folder/notes.txt"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 400, extract_response.text
    assert "PDF" in extract_response.json()["detail"]


def test_pdf_content_route_returns_file_from_immutable_storage() -> None:
    tender_id = _create_tender("PDF Viewer")
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("spec.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/spec.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    content_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/content")
    assert content_response.status_code == 200, content_response.text
    assert content_response.headers["content-type"].startswith("application/pdf")
    assert content_response.headers["content-disposition"].lower().startswith("inline")
    assert not content_response.headers["content-disposition"].lower().startswith("attachment")
    assert content_response.content.startswith(b"%PDF")


def test_pdf_content_route_rejects_foreign_document() -> None:
    tender_a = _create_tender("Foreign Access A")
    tender_b = _create_tender("Foreign Access B")

    import_response = client.post(
        f"/tenders/{tender_a}/documents/import",
        files=[("files", ("a.pdf", b"%PDF-1.4\nA\n", "application/pdf"))],
        data={"source_relative_paths": "folder/a.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    foreign_document_id = import_response.json()[0]["document_id"]

    response = client.get(f"/tenders/{tender_b}/documents/{foreign_document_id}/content")
    assert response.status_code == 404, response.text


def test_pdf_content_route_rejects_missing_storage_file() -> None:
    tender_id = _create_tender("Missing File")
    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("missing.pdf", b"%PDF-1.4\nMISSING\n", "application/pdf"))],
        data={"source_relative_paths": "folder/missing.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]
    stored_relative_path = import_response.json()[0]["stored_relative_path"]

    from app.main import get_licitia_data_root

    file_path = get_licitia_data_root() / stored_relative_path
    assert file_path.exists()
    file_path.unlink()

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/content")
    assert response.status_code == 404, response.text


def test_pdf_content_route_rejects_path_traversal() -> None:
    tender_id = _create_tender("Traversal Guard")
    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("safe.pdf", b"%PDF-1.4\nSAFE\n", "application/pdf"))],
        data={"source_relative_paths": "folder/safe.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        document = db.get(TenderDocument, document_id)
        assert document is not None
        document.stored_relative_path = "../outside/traversal.pdf"
        db.commit()
    finally:
        db.close()

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/content")
    assert response.status_code == 400, response.text


def test_tesseract_translates_neutral_language_profile_to_runtime_codes(monkeypatch) -> None:
    from app.ocr import TesseractOCRProvider

    captured: dict[str, str] = {}

    def fake_image_to_string(image, lang):
        captured["lang"] = lang
        return "OCR output"

    monkeypatch.setattr("pytesseract.image_to_string", fake_image_to_string)

    provider = TesseractOCRProvider()
    provider.status = "AVAILABLE"
    monkeypatch.setattr(provider, "_coerce_image", lambda page_image: "fake-image")
    result = provider.recognize(b"image-bytes", language="es+en")

    assert captured["lang"] == "spa+eng"
    assert result["language"] == "spa+eng"
    assert result["status"] == "OCR_TEXT_EXTRACTED"


def test_paddleocr_translates_neutral_profile_to_paddle_lang(monkeypatch) -> None:
    import io

    from PIL import Image

    from app.ocr import PaddleOCRProvider

    captured: dict[str, object] = {}

    class FakePaddleOCR:
        def __init__(self, lang):
            captured["lang"] = lang

        def predict(self, image):
            captured["image_type"] = type(image).__name__
            captured["predict_called"] = True
            return [{"rec_texts": ["OCR output line 1", "OCR output line 2"], "rec_scores": [0.91, 0.89]}]

    monkeypatch.setattr("paddleocr.PaddleOCR", FakePaddleOCR)

    image = Image.new("RGB", (20, 20), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    payload = buffer.getvalue()

    provider = PaddleOCRProvider()
    provider.status = "AVAILABLE"
    result = provider.recognize(payload, language="es+en")

    assert captured["lang"] == "es"
    assert captured["predict_called"] is True
    assert "image_type" in captured
    assert result["language"] == "es"
    assert result["status"] == "OCR_TEXT_EXTRACTED"
    assert "esen" not in str(captured["lang"])
    assert "es+en" not in str(captured["lang"])
    assert "spa+eng" not in str(captured["lang"])
    assert "OCR output line 1" in result["text"]


def test_mixed_content_image_region_is_ocr_candidate_without_overwriting_native_text(monkeypatch) -> None:
    import io

    import fitz
    from PIL import Image

    class FakeProvider:
        provider_id = "PADDLEOCR"
        provider_name = "PaddleOCR"
        version = "test-3.7.0"
        status = "AVAILABLE"
        status_reason = "fake provider for tests"

        def recognize(self, page_image, language: str):
            return {
                "text": "mixed content OCR output",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "PADDLEOCR",
                "engine_version": "test-3.7.0",
                "language": "es",
                "confidence": 0.97,
                "processing_time_ms": 111,
                "warnings": [],
            }

    monkeypatch.setattr("app.main.get_ocr_providers", lambda: [FakeProvider()])

    tender_id = _create_tender("Mixed Content Page")
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=800)
    page.insert_text((72, 72), "SNR Infraestructura...\nAnexos de Bases de Contratación\nPágina 24 de 100")

    image = Image.new("RGB", (300, 200), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page.insert_image((80, 250, 520, 650), stream=buffer.getvalue())
    payload = pdf.write()
    pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("mixed.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/mixed.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text

    page_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/pages")
    assert page_response.status_code == 200, page_response.text
    first_page = page_response.json()[0]
    assert first_page["content_profile"] == "MIXED_CONTENT"
    assert first_page["text"]

    ocr_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/ocr",
        json={"provider": "PADDLEOCR", "page_numbers": [1], "force": False},
    )
    assert ocr_response.status_code == 200, ocr_response.text
    result = ocr_response.json()
    assert result["results"]
    assert any(item["scope"] == "IMAGE_REGION" for item in result["results"])
    assert all(item["engine"] == "PADDLEOCR" for item in result["results"])
    assert len(first_page["text"]) > 0


def test_ocr_provider_catalog_reports_runtime_state() -> None:
    response = client.get("/ocr/providers")
    assert response.status_code == 200, response.text
    providers = response.json()
    keys = {item["provider_id"] for item in providers}
    assert {"TESSERACT", "PADDLEOCR"}.issubset(keys)
    assert all(item["status"] in {"AVAILABLE", "UNAVAILABLE", "ERROR"} for item in providers)


def test_ocr_auto_skips_native_text_and_runs_on_no_text_pages(monkeypatch) -> None:
    import fitz

    class FakeProvider:
        provider_id = "TESSERACT"
        provider_name = "Tesseract"
        version = "test-1.0"
        status = "AVAILABLE"
        status_reason = "fake provider for tests"

        def recognize(self, page_image, language: str):
            return {
                "text": "OCR recovered text",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "TESSERACT",
                "engine_version": "test-1.0",
                "language": "es+en",
                "confidence": 0.91,
                "processing_time_ms": 234,
                "warnings": [],
            }

    monkeypatch.setattr("app.main.get_ocr_providers", lambda: [FakeProvider()])

    tender_id = _create_tender("OCR Auto")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "")
    payload = pdf.write()
    pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("ocr.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/ocr.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text
    assert extract_response.json()["processing_status"] == "NO_NATIVE_TEXT"

    ocr_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/ocr",
        json={"provider": "AUTO", "page_numbers": [1], "force": False},
    )
    assert ocr_response.status_code == 200, ocr_response.text
    payload_result = ocr_response.json()
    assert payload_result["document_id"] == document_id
    assert len(payload_result["results"]) == 1
    assert payload_result["results"][0]["engine"] == "TESSERACT"
    assert payload_result["results"][0]["status"] == "OCR_TEXT_EXTRACTED"


def test_ocr_auto_runs_both_providers_for_image_only_and_mixed_content(monkeypatch) -> None:
    import io

    import fitz
    from PIL import Image

    class FakeTesseract:
        provider_id = "TESSERACT"
        provider_name = "Tesseract"
        version = "test-1.0"
        status = "AVAILABLE"
        status_reason = "fake"

        def recognize(self, page_image, language: str):
            return {
                "text": "tesseract output",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "TESSERACT",
                "engine_version": "test-1.0",
                "language": "spa+eng",
                "confidence": 0.88,
                "processing_time_ms": 120,
                "warnings": [],
            }

    class FakePaddle:
        provider_id = "PADDLEOCR"
        provider_name = "PaddleOCR"
        version = "test-2.0"
        status = "AVAILABLE"
        status_reason = "fake"

        def recognize(self, page_image, language: str):
            return {
                "text": "paddle output",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "PADDLEOCR",
                "engine_version": "test-2.0",
                "language": "es",
                "confidence": 0.90,
                "processing_time_ms": 180,
                "warnings": [],
            }

    monkeypatch.setattr("app.main.get_ocr_providers", lambda: [FakeTesseract(), FakePaddle()])

    tender_id = _create_tender("OCR Auto Dual Providers")
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=800)
    page.insert_text((72, 72), "Native heading on page")
    image = Image.new("RGB", (300, 200), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page.insert_image((80, 250, 520, 650), stream=buffer.getvalue())
    payload = pdf.write()
    pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("auto-dual.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/auto-dual.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    extract_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/extract-pages")
    assert extract_response.status_code == 200, extract_response.text

    ocr_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/ocr",
        json={"provider": "AUTO", "page_numbers": [1], "force": False},
    )
    assert ocr_response.status_code == 200, ocr_response.text
    result = ocr_response.json()
    engines = {item["engine"] for item in result["results"]}
    assert engines == {"TESSERACT", "PADDLEOCR"}
    assert all(item["scope"] == "IMAGE_REGION" for item in result["results"])


def test_normalize_document_content_preserves_separate_native_and_ocr_sources() -> None:
    tender_id = _create_tender("Normalized Sources")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("reference.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/reference.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="Native page text\nwith meaningful lines\n",
            char_count=32,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.commit()
        db.refresh(page)

        tesseract = PageOcrResult(
            document_page_id=page.id,
            engine="TESSERACT",
            engine_version="1.0",
            language="es+en",
            text="Tesseract OCR line 1\nTesseract OCR line 2\n",
            status="OCR_TEXT_EXTRACTED",
            confidence=0.90,
            processing_time_ms=200,
            warnings=None,
            scope="FULL_PAGE",
            region_id=None,
        )
        paddle = PageOcrResult(
            document_page_id=page.id,
            engine="PADDLEOCR",
            engine_version="2.0",
            language="es",
            text="Paddle OCR line 1\nPaddle OCR line 2\n",
            status="OCR_TEXT_EXTRACTED",
            confidence=0.88,
            processing_time_ms=220,
            warnings=None,
            scope="FULL_PAGE",
            region_id=None,
        )
        db.add_all([tesseract, paddle])
        db.commit()
    finally:
        db.close()

    normalize_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/normalize")
    assert normalize_response.status_code == 200, normalize_response.text
    summary = normalize_response.json()
    assert summary["normalized_sources"] == 3
    assert summary["chunks_created"] >= 3

    normalized_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/normalized")
    assert normalized_response.status_code == 200, normalized_response.text
    normalized = normalized_response.json()
    assert {item["source_type"] for item in normalized} == {"NATIVE_PDF", "OCR"}
    assert {item["engine"] for item in normalized if item["engine"] is not None} == {"TESSERACT", "PADDLEOCR"}

    rerun = client.post(f"/tenders/{tender_id}/documents/{document_id}/normalize")
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["normalized_sources"] == 3


def test_compare_mode_persists_independent_provider_results(monkeypatch) -> None:
    import fitz

    class FakeTesseract:
        provider_id = "TESSERACT"
        provider_name = "Tesseract"
        version = "test-1.0"
        status = "AVAILABLE"
        status_reason = "fake"

        def recognize(self, page_image, language: str):
            return {
                "text": "text from Tesseract",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "TESSERACT",
                "engine_version": "test-1.0",
                "language": "es+en",
                "confidence": 0.88,
                "processing_time_ms": 120,
                "warnings": [],
            }

    class FakePaddle:
        provider_id = "PADDLEOCR"
        provider_name = "PaddleOCR"
        version = "test-2.0"
        status = "AVAILABLE"
        status_reason = "fake"

        def recognize(self, page_image, language: str):
            return {
                "text": "text from PaddleOCR",
                "status": "OCR_TEXT_EXTRACTED",
                "engine": "PADDLEOCR",
                "engine_version": "test-2.0",
                "language": "es+en",
                "confidence": 0.90,
                "processing_time_ms": 180,
                "warnings": [],
            }

    monkeypatch.setattr("app.main.get_ocr_providers", lambda: [FakeTesseract(), FakePaddle()])

    tender_id = _create_tender("OCR Compare")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "")
    payload = pdf.write()
    pdf.close()

    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("compare.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "folder/compare.pdf"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    ocr_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/ocr",
        json={"provider": "COMPARE", "page_numbers": [1], "force": True},
    )
    assert ocr_response.status_code == 200, ocr_response.text
    result = ocr_response.json()
    assert result["document_id"] == document_id
    assert {item["engine"] for item in result["results"]} == {"TESSERACT", "PADDLEOCR"}
    assert len({item["id"] for item in result["results"]}) == 2

    rerun = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/ocr",
        json={"provider": "COMPARE", "page_numbers": [1], "force": True},
    )
    assert rerun.status_code == 200, rerun.text
    assert len(rerun.json()["results"]) == 2


def test_document_classification_detects_execution_schedule_from_content() -> None:
    tender_id = _create_tender("Execution Schedule Classification")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("schedule.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/schedule.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="Programa de ejecución de los servicios",
            char_count=40,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.commit()
        db.refresh(page)

        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                engine=None,
                normalized_text="Programa de ejecución de los servicios",
                char_count=40,
                content_sha256="schedule-1",
            )
        )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["suggested_type"] == "EXECUTION_SCHEDULE"
    assert payload["is_composite"] is False
    assert payload["classification_status"] in {"SUGGESTED", "NEEDS_REVIEW"}
    assert payload["not_ready"] is False


def test_document_classification_get_exposes_candidates_and_functional_tags() -> None:
    tender_id = _create_tender("GET Classification Contract")
    document_id = _import_classification_pdf(tender_id, "get-contract.pdf")
    _seed_normalized_lines(document_id, ["Modelo de contrato para prestación de servicios"])

    post_payload = _classify(tender_id, document_id)
    get_response = client.get(f"/tenders/{tender_id}/documents/{document_id}/classification")
    assert get_response.status_code == 200, get_response.text
    get_payload = get_response.json()

    assert get_payload["candidate_scores"] == post_payload["candidate_scores"]
    assert get_payload["functional_tags"] == post_payload["functional_tags"]
    assert any(item["type"] == "CONTRACT_DRAFT" for item in get_payload["candidate_scores"])
    assert any(item["tag"] == "CONTRACTUAL" for item in get_payload["functional_tags"])


def test_document_classification_exposes_candidates_separately_from_functional_tags() -> None:
    tender_id = _create_tender("Semantic Split")
    document_id = _import_classification_pdf(tender_id, "semantic-split.pdf")
    _seed_normalized_lines(
        document_id,
        [
            "BASES DE CONTRATACIÓN",
            "modelo de contrato y propuesta económica con fianza",
        ],
    )

    payload = _classify(tender_id, document_id)

    candidate_types = {item["type"] for item in payload["candidate_scores"]}
    functional_tags = {item["tag"] for item in payload["functional_tags"]}

    assert payload["candidate_scores"]
    assert "BIDDING_RULES" in candidate_types
    assert functional_tags <= ALLOWED_FUNCTIONAL_TAGS
    assert functional_tags.isdisjoint(candidate_types)

    db = SessionLocal()
    try:
        classification = db.query(DocumentClassification).filter_by(document_id=document_id).one()
        candidates = db.query(DocumentClassificationCandidate).filter_by(classification_id=classification.id).all()
        tags = db.query(DocumentClassificationTag).filter_by(classification_id=classification.id).all()
        assert len(candidates) > 0
        assert all(item.candidate_type in candidate_types for item in candidates)
        assert all(item.tag in ALLOWED_FUNCTIONAL_TAGS for item in tags)
    finally:
        db.close()


def test_document_classification_functional_tag_schedule_from_evidence() -> None:
    tender_id = _create_tender("Functional Schedule")
    document_id = _import_classification_pdf(tender_id, "schedule-tag.pdf")
    _seed_normalized_lines(document_id, ["Programa de ejecución de los servicios"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "SCHEDULE" in tag_scores
    assert tag_scores["SCHEDULE"] > 0


def test_document_classification_functional_tag_experience_from_evidence() -> None:
    tender_id = _create_tender("Functional Experience")
    document_id = _import_classification_pdf(tender_id, "experience-tag.pdf")
    _seed_normalized_lines(document_id, ["Requisitos de calificación por experiencia comprobable"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "EXPERIENCE" in tag_scores


def test_document_classification_functional_tag_personnel_from_evidence() -> None:
    tender_id = _create_tender("Functional Personnel")
    document_id = _import_classification_pdf(tender_id, "personnel-tag.pdf")
    _seed_normalized_lines(document_id, ["Se requiere personal profesional certificado"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "PERSONNEL" in tag_scores


def test_document_classification_functional_tag_guarantee_from_evidence() -> None:
    tender_id = _create_tender("Functional Guarantee")
    document_id = _import_classification_pdf(tender_id, "guarantee-tag.pdf")
    _seed_normalized_lines(document_id, ["Garantía de cumplimiento y fianza de seriedad"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "GUARANTEE" in tag_scores


def test_document_classification_functional_tag_technical_from_evidence() -> None:
    tender_id = _create_tender("Functional Technical")
    document_id = _import_classification_pdf(tender_id, "technical-tag.pdf")
    _seed_normalized_lines(document_id, ["Especificaciones técnicas para alcance del servicio"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "TECHNICAL" in tag_scores


def test_document_classification_functional_tag_economic_from_evidence() -> None:
    tender_id = _create_tender("Functional Economic")
    document_id = _import_classification_pdf(tender_id, "economic-tag.pdf")
    _seed_normalized_lines(document_id, ["Propuesta económica y catálogo de conceptos"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "ECONOMIC" in tag_scores


def test_document_classification_functional_tag_contractual_from_evidence() -> None:
    tender_id = _create_tender("Functional Contractual")
    document_id = _import_classification_pdf(tender_id, "contract-tag.pdf")
    _seed_normalized_lines(document_id, ["Modelo de contrato para prestación de servicios"])

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "CONTRACTUAL" in tag_scores


def test_document_classification_unrelated_text_does_not_create_uncontrolled_functional_tag() -> None:
    tender_id = _create_tender("No Uncontrolled Tag")
    document_id = _import_classification_pdf(tender_id, "unrelated.pdf")
    _seed_normalized_lines(document_id, ["Documento informativo de antecedentes generales del proceso"])

    payload = _classify(tender_id, document_id)
    functional_tags = {item["tag"] for item in payload["functional_tags"]}
    assert functional_tags <= ALLOWED_FUNCTIONAL_TAGS
    assert functional_tags == set()


def test_document_classification_repeated_signal_does_not_inflate_functional_tag_score_by_page_count() -> None:
    tender_id = _create_tender("No Tag Inflation")
    document_id = _import_classification_pdf(tender_id, "inflation.pdf")
    _seed_normalized_lines(document_id, ["Experiencia comprobable"] * 60)

    payload = _classify(tender_id, document_id)
    tag_scores = {item["tag"]: item["score"] for item in payload["functional_tags"]}
    assert "EXPERIENCE" in tag_scores
    assert tag_scores["EXPERIENCE"] <= 55


def test_document_classification_candidate_and_functional_scores_are_stable_after_rerun_and_confirmed_survives() -> None:
    tender_id = _create_tender("Candidate And Tags Stable")
    document_id = _import_classification_pdf(tender_id, "stable-rerun.pdf")
    _seed_normalized_lines(document_id, ["Programa de ejecución", "Modelo de contrato", "fianza"])

    first = _classify(tender_id, document_id)
    first_candidates = first["candidate_scores"]
    first_tags = first["functional_tags"]

    confirm = client.patch(
        f"/tenders/{tender_id}/documents/{document_id}/classification",
        json={"action": "CONFIRM", "human_note": "Confirmado"},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["classification_status"] == "CONFIRMED"

    rerun = _classify(tender_id, document_id)
    assert rerun["classification_status"] == "CONFIRMED"
    assert rerun["candidate_scores"] == first_candidates
    assert rerun["functional_tags"] == first_tags


def test_legacy_candidate_tags_are_cleaned_up_into_candidates() -> None:
    module = _load_candidate_migration_module()

    tender_id = _create_tender("Legacy Cleanup")
    document_id = _import_classification_pdf(tender_id, "legacy-cleanup.pdf")
    _seed_normalized_lines(document_id, ["Modelo de contrato para prestación de servicios"])

    db = SessionLocal()
    try:
        classification = DocumentClassification(document_id=document_id)
        db.add(classification)
        db.flush()
        db.add(
            DocumentClassificationTag(
                classification_id=classification.id,
                tag="BIDDING_RULES",
                score=55,
            )
        )
        db.add(
            DocumentClassificationTag(
                classification_id=classification.id,
                tag="CONTRACTUAL",
                score=49,
            )
        )
        db.commit()

        module._cleanup_legacy_candidate_tags(db.connection())
        db.commit()

        refreshed = db.query(DocumentClassification).filter_by(id=classification.id).one()
        assert {candidate.candidate_type for candidate in refreshed.candidates} == {"BIDDING_RULES"}
        assert {tag.tag for tag in refreshed.tags} == {"CONTRACTUAL"}
    finally:
        db.close()


def test_document_classification_validated_type_outcomes_do_not_regress() -> None:
    tender_id = _create_tender("Validated Outcomes")

    convocatoria_id = _import_classification_pdf(tender_id, "convocatoria.pdf")
    bases_id = _import_classification_pdf(tender_id, "bases.pdf")
    anexos_id = _import_classification_pdf(tender_id, "anexos.pdf")
    anexo_d_id = _import_classification_pdf(tender_id, "anexo-d.pdf")

    _seed_normalized_lines(
        convocatoria_id,
        [
            "CONVOCATORIA",
            "De acuerdo con el modelo de contrato y las bases de contratación.",
        ],
    )
    _seed_normalized_lines(
        bases_id,
        [
            "BASES DE CONTRATACIÓN",
            "Conforme al modelo de contrato, especificaciones técnicas y propuesta económica.",
        ],
    )
    _seed_normalized_lines(
        anexos_id,
        [
            "Especificaciones técnicas",
            "Programa de ejecución",
            "Modelo de contrato",
            "Formato de entrega",
        ],
    )
    _seed_normalized_lines(
        anexo_d_id,
        [
            "PROGRAMA GENERAL DE EJECUCIÓN",
            "Conforme al modelo de contrato y especificaciones técnicas.",
        ],
    )

    convocatoria = _classify(tender_id, convocatoria_id)
    bases = _classify(tender_id, bases_id)
    anexos = _classify(tender_id, anexos_id)
    anexo_d = _classify(tender_id, anexo_d_id)

    assert convocatoria["suggested_type"] == "NOTICE"
    assert convocatoria["is_composite"] is False

    assert bases["suggested_type"] == "BIDDING_RULES"
    assert bases["is_composite"] is False

    assert anexos["suggested_type"] == "DOCUMENT_PACKAGE"
    assert anexos["is_composite"] is True

    assert anexo_d["suggested_type"] == "EXECUTION_SCHEDULE"
    assert anexo_d["is_composite"] is False


def test_document_classification_human_override_survives_rerun() -> None:
    tender_id = _create_tender("Human Override")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("contract.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/contract.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="modelo de contrato para el suministro",
            char_count=40,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.commit()
        db.refresh(page)

        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                engine=None,
                normalized_text="modelo de contrato para el suministro",
                char_count=40,
                content_sha256="abc123",
            )
        )
        db.commit()
    finally:
        db.close()

    first = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert first.status_code == 200, first.text

    override_response = client.patch(
        f"/tenders/{tender_id}/documents/{document_id}/classification",
        json={"action": "OVERRIDE", "human_type": "CONTRACT_DRAFT", "human_note": "Manual override"},
    )
    assert override_response.status_code == 200, override_response.text
    assert override_response.json()["effective_type"] == "CONTRACT_DRAFT"

    rerun = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["effective_type"] == "CONTRACT_DRAFT"


def test_document_classification_repeated_boilerplate_is_unique_signal_only() -> None:
    tender_id = _create_tender("Repeated Boilerplate")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("bases.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/bases.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        for page_number in range(1, 101):
            page = DocumentPage(
                document_id=document_id,
                page_number=page_number,
                text="Bases de contratación\n",
                char_count=24,
                extraction_method="NATIVE_PDF",
                status="TEXT_EXTRACTED",
            )
            db.add(page)
            db.flush()
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    normalized_text="Bases de contratación\n",
                    char_count=24,
                    content_sha256=f"repeat-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["suggested_type"] == "BIDDING_RULES"
    assert payload["suggested_score"] >= 35
    bases_evidence = [item for item in payload["evidence"] if "bases de contrat" in item["signal"]]
    assert len(bases_evidence) == 1


def test_document_classification_composite_package_requires_diverse_signals() -> None:
    tender_id = _create_tender("Composite Package")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("package.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/package.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        sources = [
            (1, "requisitos de calificación para experiencia"),
            (2, "programa de ejecución de los servicios"),
            (3, "modelo de contrato para suministro"),
            (4, "garantia y fianza"),
        ]
        for page_number, text in sources:
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
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    normalized_text=text,
                    char_count=len(text),
                    content_sha256=f"package-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["is_composite"] is True
    assert payload["suggested_type"] == "DOCUMENT_PACKAGE"


def test_document_classification_notice_with_references_is_not_composite() -> None:
    tender_id = _create_tender("Notice With References")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("convocatoria.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/convocatoria.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page_texts = [
            "CONVOCATORIA\nLicitación pública nacional",
            "De acuerdo con el modelo de contrato y las bases de contratación, se presentará propuesta económica y garantía.",
        ]
        for page_number, text in enumerate(page_texts, start=1):
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
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    normalized_text=text,
                    char_count=len(text),
                    content_sha256=f"notice-ref-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["suggested_type"] == "NOTICE"
    assert payload["is_composite"] is False


def test_document_classification_bidding_rules_with_references_is_not_composite() -> None:
    tender_id = _create_tender("Rules With References")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("bases.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/bases.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page_texts = [
            "BASES DE CONTRATACIÓN\nCondiciones de participación",
            "Conforme al modelo de contrato, especificaciones técnicas y propuesta económica se deberán presentar garantías.",
        ]
        for page_number, text in enumerate(page_texts, start=1):
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
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    normalized_text=text,
                    char_count=len(text),
                    content_sha256=f"rules-ref-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["suggested_type"] == "BIDDING_RULES"
    assert payload["is_composite"] is False


def test_document_classification_toc_list_alone_does_not_trigger_composite() -> None:
    tender_id = _create_tender("TOC Only")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("toc.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/toc.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    toc_text = """
    INDICE DE CONTENIDO
    Anexo B - Especificaciones Particulares
    Anexo C - Relación de Conceptos
    Anexo D - Programa General de Ejecución
    Anexo E - Modelo de Contrato
    """

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text=toc_text,
            char_count=len(toc_text),
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.flush()
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text=toc_text,
                char_count=len(toc_text),
                content_sha256="toc-only-1",
            )
        )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["is_composite"] is False
    assert payload["suggested_type"] != "DOCUMENT_PACKAGE"


def test_document_classification_execution_schedule_with_references_is_not_composite() -> None:
    tender_id = _create_tender("Schedule With References")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("anexo-d.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/anexo-d.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page_texts = [
            "PROGRAMA GENERAL DE EJECUCIÓN DE LOS SERVICIOS",
            "Conforme al modelo de contrato y especificaciones técnicas, este cronograma regirá actividades.",
        ]
        for page_number, text in enumerate(page_texts, start=1):
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
            db.add(
                NormalizedContent(
                    document_page_id=page.id,
                    source_type="NATIVE_PDF",
                    source_scope="NATIVE_PAGE",
                    normalized_text=text,
                    char_count=len(text),
                    content_sha256=f"schedule-ref-{page_number}",
                )
            )
        db.commit()
    finally:
        db.close()

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["suggested_type"] == "EXECUTION_SCHEDULE"
    assert payload["is_composite"] is False


def test_document_classification_human_confirmed_survives_recompute() -> None:
    tender_id = _create_tender("Human Confirmed")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("confirmed.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/confirmed.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="Programa de ejecución de los servicios",
            char_count=40,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text="Programa de ejecución de los servicios",
                char_count=40,
                content_sha256="confirmed-1",
            )
        )
        db.commit()
    finally:
        db.close()

    first = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert first.status_code == 200, first.text

    confirm = client.patch(
        f"/tenders/{tender_id}/documents/{document_id}/classification",
        json={"action": "CONFIRM", "human_note": "Confirmado por analista"},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["classification_status"] == "CONFIRMED"

    rerun = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["classification_status"] == "CONFIRMED"


def test_document_classification_version_change_forces_recompute() -> None:
    tender_id = _create_tender("Version Invalidation")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("versioned.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/versioned.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="BASES DE CONTRATACIÓN",
            char_count=22,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.flush()
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text="BASES DE CONTRATACIÓN",
                char_count=22,
                content_sha256="version-old",
            )
        )
        db.commit()
    finally:
        db.close()

    first = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert first.status_code == 200, first.text

    db = SessionLocal()
    try:
        classification = db.query(DocumentClassification).filter_by(document_id=document_id).one()
        classification.classifier_version = "mvp-02.4.1"
        db.commit()
    finally:
        db.close()

    rerun = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert rerun.status_code == 200, rerun.text

    db = SessionLocal()
    try:
        classification = db.query(DocumentClassification).filter_by(document_id=document_id).one()
        assert classification.classifier_version == "mvp-02.4.2"
    finally:
        db.close()


def test_document_classification_second_identical_rerun_is_idempotent() -> None:
    tender_id = _create_tender("Idempotent Rerun")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("idem.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/idem.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="CONVOCATORIA",
            char_count=12,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.flush()
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text="CONVOCATORIA",
                char_count=12,
                content_sha256="idem-1",
            )
        )
        db.commit()
    finally:
        db.close()

    first = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert first.status_code == 200, first.text

    db = SessionLocal()
    try:
        before = db.query(DocumentClassification).filter_by(document_id=document_id).one()
        before_updated_at = before.updated_at
    finally:
        db.close()

    second = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert second.status_code == 200, second.text

    db = SessionLocal()
    try:
        after = db.query(DocumentClassification).filter_by(document_id=document_id).one()
        assert after.updated_at == before_updated_at
    finally:
        db.close()


def test_document_classification_human_review_survives_rerun() -> None:
    tender_id = _create_tender("Human Review")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("review.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n", "application/pdf"))],
        data={"source_relative_paths": "folder/review.pdf"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=1,
            text="Bases de contratación",
            char_count=24,
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="NATIVE_PDF",
                source_scope="NATIVE_PAGE",
                normalized_text="Bases de contratación",
                char_count=24,
                content_sha256="review-1",
            )
        )
        db.commit()
    finally:
        db.close()

    first = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert first.status_code == 200, first.text

    review_response = client.patch(
        f"/tenders/{tender_id}/documents/{document_id}/classification",
        json={"action": "MARK_FOR_REVIEW", "human_note": "Revisión humana requerida"},
    )
    assert review_response.status_code == 200, review_response.text
    assert review_response.json()["classification_status"] == "NEEDS_REVIEW"
    assert review_response.json()["human_note"] == "Revisión humana requerida"

    rerun = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["classification_status"] == "NEEDS_REVIEW"
    assert rerun.json()["human_note"] == "Revisión humana requerida"


def test_document_classification_not_ready_without_normalized_content() -> None:
    tender_id = _create_tender("Not Ready")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("notes.txt", b"plain text\n", "text/plain"))],
        data={"source_relative_paths": "folder/notes.txt"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    classify_response = client.post(f"/tenders/{tender_id}/documents/{document_id}/classify")
    assert classify_response.status_code == 200, classify_response.text
    payload = classify_response.json()
    assert payload["not_ready"] is True
    assert payload["suggested_type"] == "UNKNOWN"


def test_pdf_content_route_rejects_non_pdf_viewer_requests() -> None:
    tender_id = _create_tender("Non PDF Guard")
    import_response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("notes.txt", b"plain text\n", "text/plain"))],
        data={"source_relative_paths": "folder/notes.txt"},
    )
    assert import_response.status_code == 200, import_response.text
    document_id = import_response.json()[0]["document_id"]

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/content")
    assert response.status_code == 400, response.text
    assert "Only PDF files can be displayed" in response.text


def test_reference_exact_annex_resolution_creates_relationship() -> None:
    tender_id = _create_tender("References Exact Annex")
    source_id = _import_classification_pdf(tender_id, "bases-source.pdf")
    target_id = _import_classification_pdf(tender_id, "ANEXO D.pdf")

    _seed_normalized_lines(source_id, ["Conforme al Anexo D se ejecutará el servicio"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["resolved_references"] == 1
    assert payload["relationships"][0]["relationship_type"] == "REFERENCES"
    assert payload["relationships"][0]["target_document_id"] == target_id


def test_reference_canonical_annex_normalization_uses_same_key() -> None:
    tender_id = _create_tender("References Canonical Annex")
    source_id = _import_classification_pdf(tender_id, "source.pdf")
    _import_classification_pdf(tender_id, "Anexo D.pdf")

    _seed_normalized_lines(source_id, ["Anexo \"D\"", "ANEXO D", "anexo d"])
    payload = _analyze_references(tender_id, source_id)

    keys = {item["normalized_reference_key"] for item in payload["references"]}
    assert keys == {"ANEXO:D"}


def test_reference_missing_document_stays_unresolved() -> None:
    tender_id = _create_tender("References Missing")
    source_id = _import_classification_pdf(tender_id, "source-missing.pdf")
    _seed_normalized_lines(source_id, ["Ver Anexo Z para requisitos adicionales"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["unresolved_references"] == 1
    assert payload["counts"]["resolved_relationships"] == 0


def test_reference_ambiguous_target_does_not_auto_resolve() -> None:
    tender_id = _create_tender("References Ambiguous")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    _import_classification_pdf(tender_id, "bases de contratacion v1.pdf")
    _import_classification_pdf(tender_id, "bases de contratacion v2.pdf")
    _seed_normalized_lines(source_id, ["De acuerdo con las Bases de Contratación"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["ambiguous_references"] == 1
    assert payload["counts"]["resolved_relationships"] == 0
    candidates = payload["references"][0]["ambiguous_candidates"]
    assert len(candidates) == 2
    assert [item["document_id"] for item in candidates] == sorted(item["document_id"] for item in candidates)
    assert {item["original_filename"] for item in candidates} == {
        "bases de contratacion v1.pdf",
        "bases de contratacion v2.pdf",
    }


def test_reference_bases_alias_with_ordinal_and_suffix_auto_resolves() -> None:
    tender_id = _create_tender("References Bases Alias")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    target_id = _import_classification_pdf(tender_id, "2. Bases - ABC-123.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["resolved_references"] == 1
    reference = payload["references"][0]
    assert reference["normalized_reference_key"] == "BASES_DE_CONTRATACION"
    assert reference["resolution_status"] == "AUTO_RESOLVED"
    assert reference["resolved_target_document_id"] == target_id


def test_reference_bases_alias_two_current_candidates_is_ambiguous() -> None:
    tender_id = _create_tender("References Bases Ambiguous")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    first_target_id = _import_classification_pdf(tender_id, "2. Bases - ABC-123.pdf")
    second_target_id = _import_classification_pdf(tender_id, "4. Bases - XYZ-999.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    payload = _analyze_references(tender_id, source_id)
    reference = payload["references"][0]
    assert reference["resolution_status"] == "AMBIGUOUS"
    assert reference["resolved_target_document_id"] is None
    candidate_ids = [item["document_id"] for item in reference["ambiguous_candidates"]]
    assert candidate_ids == sorted(candidate_ids)
    assert set(candidate_ids) == {first_target_id, second_target_id}


def test_reference_bases_alias_current_only_ignores_obsolete_revision() -> None:
    tender_id = _create_tender("References Bases Current Only")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    obsolete_target_id = _import_classification_pdf(tender_id, "2. Bases - ABC-123.pdf")
    current_target_id = _import_classification_pdf(tender_id, "2. Bases - XYZ-999.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    db = SessionLocal()
    try:
        obsolete_doc = db.get(TenderDocument, obsolete_target_id)
        assert obsolete_doc is not None
        obsolete_doc.is_current = False
        db.commit()
    finally:
        db.close()

    payload = _analyze_references(tender_id, source_id)
    reference = payload["references"][0]
    assert reference["resolution_status"] == "AUTO_RESOLVED"
    assert reference["resolved_target_document_id"] == current_target_id
    assert [item["document_id"] for item in reference["ambiguous_candidates"]] == [current_target_id]


def test_reference_bases_alias_without_physical_target_stays_unresolved() -> None:
    tender_id = _create_tender("References Bases Missing")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    payload = _analyze_references(tender_id, source_id)
    reference = payload["references"][0]
    assert reference["resolution_status"] == "UNRESOLVED"
    assert reference["resolved_target_document_id"] is None
    assert reference["ambiguous_candidates"] == []


def test_reference_bases_alias_normalizes_leading_ordinal_and_tender_suffix() -> None:
    tender_id = _create_tender("References Bases Filename Normalization")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    target_id = _import_classification_pdf(tender_id, "010) BASES - PROC-AB-2026-77.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    payload = _analyze_references(tender_id, source_id)
    reference = payload["references"][0]
    assert reference["resolution_status"] == "AUTO_RESOLVED"
    assert reference["resolved_target_document_id"] == target_id


def test_reference_contract_model_does_not_resolve_to_document_package_section() -> None:
    tender_id = _create_tender("References Contract Model Package Guard")
    source_id = _import_classification_pdf(tender_id, "convocatoria-source.pdf")
    package_id = _import_classification_pdf(tender_id, "2.1. ANEXOS - CAD-265-2026.pdf")
    _seed_normalized_lines(source_id, ["Modelo de Contrato"])
    _seed_normalized_lines(package_id, ["Modelo de Contrato", "Contenido interno"])

    payload = _analyze_references(tender_id, source_id)
    reference = payload["references"][0]
    assert reference["normalized_reference_key"] == "MODELO_DE_CONTRATO"
    assert reference["resolution_status"] == "UNRESOLVED"
    assert reference["resolved_target_document_id"] is None


def test_reference_human_resolution_survives_resolver_version_bump() -> None:
    tender_id = _create_tender("References Human Resolve Version")
    source_id = _import_classification_pdf(tender_id, "source-human-version.pdf")
    target_a = _import_classification_pdf(tender_id, "2. Bases - AAA-100.pdf")
    target_b = _import_classification_pdf(tender_id, "3. Bases - BBB-200.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    first = _analyze_references(tender_id, source_id)
    reference_id = first["references"][0]["id"]
    assert first["references"][0]["resolution_status"] == "AMBIGUOUS"

    patch = client.patch(
        f"/tenders/{tender_id}/references/{reference_id}",
        json={"action": "RESOLVE_TO_DOCUMENT", "human_target_document_id": target_a, "human_note": "Resolución humana"},
    )
    assert patch.status_code == 200, patch.text

    db = SessionLocal()
    try:
        analysis = db.query(DocumentReferenceAnalysis).filter_by(document_id=source_id).one()
        analysis.extractor_version = "mvp-02.5"
        db.commit()
    finally:
        db.close()

    rerun = _analyze_references(tender_id, source_id)
    assert rerun["references"][0]["resolution_status"] == "HUMAN_RESOLVED"
    assert rerun["references"][0]["resolved_target_document_id"] == target_a
    assert target_b in [item["document_id"] for item in rerun["references"][0]["ambiguous_candidates"]]


def test_reference_second_identical_rerun_is_idempotent_with_mvp_02_5_1() -> None:
    tender_id = _create_tender("References Idempotent 02.5.1")
    source_id = _import_classification_pdf(tender_id, "source-idempotent-v251.pdf")
    _import_classification_pdf(tender_id, "2. Bases - ABC-123.pdf")
    _seed_normalized_lines(source_id, ["Bases de Contratación"])

    first = _analyze_references(tender_id, source_id)
    second = _analyze_references(tender_id, source_id)

    assert first["extractor_version"] == "mvp-02.5.1"
    assert second["extractor_version"] == "mvp-02.5.1"
    assert [item["id"] for item in first["references"]] == [item["id"] for item in second["references"]]


def test_reference_self_reference_does_not_create_self_edge() -> None:
    tender_id = _create_tender("References Self")
    source_id = _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["Conforme al Anexo D se ejecutará"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["resolved_relationships"] == 0
    assert payload["references"][0]["resolution_status"] == "IGNORED"


def test_reference_repeated_mentions_create_single_relationship_edge() -> None:
    tender_id = _create_tender("References Repeated")
    source_id = _import_classification_pdf(tender_id, "bases.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["Conforme al Anexo D"] * 5)

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["resolved_relationships"] == 1
    relationships = client.get(f"/tenders/{tender_id}/relationships").json()
    assert len(relationships) == 1


def test_reference_ocr_duplicate_sources_do_not_duplicate_semantic_reference() -> None:
    tender_id = _create_tender("References OCR Dedup")
    source_id = _import_classification_pdf(tender_id, "source-ocr.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")

    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=source_id,
            page_number=1,
            text="",
            char_count=0,
            extraction_method="NATIVE_PDF",
            status="NO_TEXT",
        )
        db.add(page)
        db.flush()
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="OCR",
                source_scope="IMAGE_REGION",
                engine="TESSERACT",
                normalized_text="conforme al anexo d",
                char_count=19,
                content_sha256="ocr-tess",
            )
        )
        db.add(
            NormalizedContent(
                document_page_id=page.id,
                source_type="OCR",
                source_scope="IMAGE_REGION",
                engine="PADDLEOCR",
                normalized_text="conforme al anexo d",
                char_count=19,
                content_sha256="ocr-paddle",
            )
        )
        db.commit()
    finally:
        db.close()

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["total_reference_mentions"] == 1


def test_reference_multiple_supporting_mentions_appear_under_single_edge() -> None:
    tender_id = _create_tender("References Support")
    source_id = _import_classification_pdf(tender_id, "bases-support.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["Conforme al Anexo D", "Ver Anexo D para mayor detalle"])

    _analyze_references(tender_id, source_id)
    relationships = client.get(f"/tenders/{tender_id}/relationships").json()
    assert len(relationships) == 1
    assert len(relationships[0]["supporting_references"]) >= 2


def test_reference_modifies_requires_explicit_reference_target() -> None:
    tender_id = _create_tender("References Modifies")
    source_id = _import_classification_pdf(tender_id, "bases-modifica.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["Se modifica el Anexo D conforme al acta"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["relationships"][0]["relationship_type"] == "MODIFIES"


def test_reference_generic_modification_word_without_target_creates_no_relationship() -> None:
    tender_id = _create_tender("References No Modifies")
    source_id = _import_classification_pdf(tender_id, "bases-plazo.pdf")
    _seed_normalized_lines(source_id, ["Modificación del plazo contractual"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["total_reference_mentions"] == 0
    assert payload["counts"]["resolved_relationships"] == 0


def test_reference_generic_prose_does_not_create_false_document_references() -> None:
    tender_id = _create_tender("References Prose Guard")
    source_id = _import_classification_pdf(tender_id, "prose.pdf")
    _seed_normalized_lines(source_id, ["el contrato tendrá vigencia", "en formato electrónico", "experiencia del participante"])

    payload = _analyze_references(tender_id, source_id)
    assert payload["counts"]["total_reference_mentions"] == 0


def test_reference_current_only_resolution_ignores_obsolete_candidate() -> None:
    tender_id = _create_tender("References Current Only")
    source_id = _import_classification_pdf(tender_id, "source-current.pdf")
    old_target_id = _import_classification_pdf(tender_id, "ANEXO D old.pdf")
    current_target_id = _import_classification_pdf(tender_id, "ANEXO D current.pdf")
    _seed_normalized_lines(source_id, ["ver Anexo D"])

    db = SessionLocal()
    try:
        old_doc = db.get(TenderDocument, old_target_id)
        assert old_doc is not None
        old_doc.is_current = False
        db.commit()
    finally:
        db.close()

    payload = _analyze_references(tender_id, source_id)
    assert payload["references"][0]["resolved_target_document_id"] == current_target_id


def test_reference_human_resolution_persists_across_rerun() -> None:
    tender_id = _create_tender("References Human Resolve")
    source_id = _import_classification_pdf(tender_id, "source-human.pdf")
    target_a = _import_classification_pdf(tender_id, "bases de contratacion a.pdf")
    _import_classification_pdf(tender_id, "bases de contratacion b.pdf")
    _seed_normalized_lines(source_id, ["de acuerdo con las bases de contratación"])

    first = _analyze_references(tender_id, source_id)
    reference_id = first["references"][0]["id"]
    patch = client.patch(
        f"/tenders/{tender_id}/references/{reference_id}",
        json={"action": "RESOLVE_TO_DOCUMENT", "human_target_document_id": target_a, "human_note": "Resolución humana"},
    )
    assert patch.status_code == 200, patch.text

    rerun = _analyze_references(tender_id, source_id)
    assert rerun["references"][0]["resolution_status"] == "HUMAN_RESOLVED"
    assert rerun["references"][0]["resolved_target_document_id"] == target_a


def test_reference_human_ignored_persists_across_rerun() -> None:
    tender_id = _create_tender("References Human Ignore")
    source_id = _import_classification_pdf(tender_id, "source-ignore.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["ver anexo d"])

    first = _analyze_references(tender_id, source_id)
    reference_id = first["references"][0]["id"]
    patch = client.patch(
        f"/tenders/{tender_id}/references/{reference_id}",
        json={"action": "IGNORE_REFERENCE", "human_note": "No aplica"},
    )
    assert patch.status_code == 200, patch.text

    rerun = _analyze_references(tender_id, source_id)
    assert rerun["references"][0]["resolution_status"] == "IGNORED"


def test_reference_same_input_is_idempotent_and_stale_edges_are_removed_on_input_change() -> None:
    tender_id = _create_tender("References Idempotent")
    source_id = _import_classification_pdf(tender_id, "source-idempotent.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["conforme al anexo d"])

    first = _analyze_references(tender_id, source_id)
    second = _analyze_references(tender_id, source_id)
    assert [item["id"] for item in first["references"]] == [item["id"] for item in second["references"]]
    assert first["counts"]["resolved_relationships"] == 1
    assert second["counts"]["resolved_relationships"] == 1

    db = SessionLocal()
    try:
        content = db.query(NormalizedContent).join(DocumentPage).filter(DocumentPage.document_id == source_id).first()
        assert content is not None
        content.normalized_text = "sin referencias explícitas"
        content.char_count = len(content.normalized_text)
        db.commit()
    finally:
        db.close()

    third = _analyze_references(tender_id, source_id)
    assert third["counts"]["resolved_relationships"] == 0


def test_reference_analysis_does_not_modify_classification_rows() -> None:
    tender_id = _create_tender("References Classifier Isolation")
    source_id = _import_classification_pdf(tender_id, "source-isolation.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["CONVOCATORIA", "conforme al anexo d"])

    classify_payload = _classify(tender_id, source_id)
    confirm = client.patch(
        f"/tenders/{tender_id}/documents/{source_id}/classification",
        json={"action": "CONFIRM", "human_note": "Confirmado"},
    )
    assert confirm.status_code == 200, confirm.text

    before = client.get(f"/tenders/{tender_id}/documents/{source_id}/classification").json()
    _analyze_references(tender_id, source_id)
    after = client.get(f"/tenders/{tender_id}/documents/{source_id}/classification").json()

    assert after["suggested_type"] == classify_payload["suggested_type"]
    assert after["candidate_scores"] == before["candidate_scores"]
    assert after["functional_tags"] == before["functional_tags"]
    assert after["classification_status"] == "CONFIRMED"


def test_reference_not_ready_without_normalized_content() -> None:
    tender_id = _create_tender("References Not Ready")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("empty.txt", b"plain\n", "text/plain"))],
        data={"source_relative_paths": "folder/empty.txt"},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()[0]["document_id"]

    payload = _analyze_references(tender_id, document_id)
    assert payload["status"] == "NOT_READY"
    assert payload["counts"]["total_reference_mentions"] == 0


def test_reference_batch_resilience_for_ready_and_not_ready_documents() -> None:
    tender_id = _create_tender("References Batch")
    ready_id = _import_classification_pdf(tender_id, "ready.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", ("not-ready.txt", b"plain\n", "text/plain"))],
        data={"source_relative_paths": "folder/not-ready.txt"},
    )
    assert response.status_code == 200, response.text
    not_ready_id = response.json()[0]["document_id"]
    _seed_normalized_lines(ready_id, ["conforme al anexo d"])

    batch = client.post(f"/tenders/{tender_id}/analyze-references")
    assert batch.status_code == 200, batch.text
    payload = batch.json()
    by_id = {item["document_id"]: item for item in payload}
    assert by_id[ready_id]["status"] == "COMPLETED"
    assert by_id[not_ready_id]["status"] == "NOT_READY"


def test_reference_get_endpoint_returns_detected_references() -> None:
    tender_id = _create_tender("References GET")
    source_id = _import_classification_pdf(tender_id, "source-get.pdf")
    _import_classification_pdf(tender_id, "ANEXO D.pdf")
    _seed_normalized_lines(source_id, ["conforme al anexo d"])

    _analyze_references(tender_id, source_id)
    payload = _get_references(tender_id, source_id)
    assert payload["counts"]["total_reference_mentions"] == 1
    assert payload["references"][0]["raw_reference_text"].lower().startswith("anexo")


class _FakeOllamaResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeOllamaResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _import_vision_pdf(tender_id: str, filename: str, pages: list[str]) -> str:
    import fitz

    pdf_document = fitz.open()
    for text in pages:
        page = pdf_document.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = pdf_document.write()
    pdf_document.close()

    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, pdf_bytes, "application/pdf"))],
        data={"source_relative_paths": f"folder/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _patch_ollama_available(monkeypatch: pytest.MonkeyPatch, *, invalid_json: bool = False) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}, {"name": "qwen3-vl:4b"}, {"name": "llava:latest"}]})
        if request.full_url.endswith("/api/chat"):
            if invalid_json:
                return _FakeOllamaResponse({"message": {"content": "not valid json"}})
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][0]["content"]
            if "Task type: DETAIL_TRANSCRIPTION" in prompt:
                return _FakeOllamaResponse(
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "source_page": 1,
                                    "raw_lines": [
                                        {
                                            "raw_visible_text": "MODULO DE PRUEBA, MARCA: YOKOGAWA, MODELO: MTBE-1 (1 PIEZA)",
                                            "uncertain": False,
                                            "uncertain_characters": [],
                                        }
                                    ],
                                    "uncertainties": [],
                                }
                            )
                        },
                        "done_reason": "stop",
                        "prompt_eval_count": 123,
                        "eval_count": 89,
                    }
                )
            match = re.search(r"Page number: (\d+)", prompt)
            page_number = int(match.group(1)) if match else 1
            return _FakeOllamaResponse(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "page_number": page_number,
                                "continues_previous_item": False,
                                "previous_item_number": None,
                                "item_segments": [
                                    {
                                        "item_number": str(page_number),
                                        "starts_on_this_page": True,
                                        "has_service": True,
                                        "has_supply": False,
                                        "has_deliverable": False,
                                        "anchor_raw_text": f"Servicio de mantenimiento pagina {page_number}",
                                        "review_required": False,
                                    }
                                ],
                                "new_items": [
                                    {
                                        "item_number": str(page_number),
                                        "concept_raw_text": f"Servicio de mantenimiento pagina {page_number}",
                                        "review_required": False,
                                    }
                                ],
                                "open_item_at_page_end": str(page_number),
                                "uncertainties": [],
                            }
                        )
                    },
                    "done_reason": "stop",
                    "prompt_eval_count": 201,
                    "eval_count": 180,
                }
            )
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)


def test_vision_provider_availability_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ollama_available(monkeypatch)

    response = client.get("/vision/providers")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider_id"] == "OLLAMA_VISION"
    assert payload["provider_status"] == "AVAILABLE"
    assert payload["runtime_available"] is True
    assert payload["configured_model"] == "qwen3-vl:4b-instruct"
    assert payload["model_available"] is True
    assert payload["selected_model"] == "qwen3-vl:4b-instruct"


def test_vision_assist_reports_offline_provider_as_controlled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_down(request, timeout):
        raise OSError("ollama unavailable")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_down)

    tender_id = _create_tender("Vision offline")
    document_id = _import_vision_pdf(tender_id, "offline.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 503, response.text

    db = SessionLocal()
    try:
        assert (
            db.execute(
                select(func.count(DocumentVisionAnalysis.id)).where(DocumentVisionAnalysis.document_id == document_id)
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                select(func.count(DocumentVisionPageResult.id))
                .join(DocumentVisionAnalysis, DocumentVisionAnalysis.id == DocumentVisionPageResult.analysis_id)
                .where(DocumentVisionAnalysis.document_id == document_id)
            ).scalar_one()
            == 0
        )
    finally:
        db.close()


def test_vision_assist_persists_successful_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ollama_available(monkeypatch)

    tender_id = _create_tender("Vision success")
    document_id = _import_vision_pdf(tender_id, "vision-success.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["page_results"][0]["status"] == "COMPLETED"
    assert payload["page_results"][0]["structured_json"]["page_number"] == 1
    structured = payload["page_results"][0]["structured_json"]
    assert structured["item_segments"][0]["has_service"] is True
    assert structured["new_items"][0]["item_number"] == "1"
    assert structured["open_item_at_page_end"] == "1"
    assert "scope_blocks" not in structured

    db = SessionLocal()
    try:
        analyses = db.execute(select(DocumentVisionAnalysis).where(DocumentVisionAnalysis.document_id == document_id)).scalars().all()
        assert len(analyses) == 1
        page_results = db.execute(select(DocumentVisionPageResult).where(DocumentVisionPageResult.analysis_id == analyses[0].id)).scalars().all()
        assert len(page_results) == 1
        assert page_results[0].status == "COMPLETED"
        assert page_results[0].structured_json is not None
        assert page_results[0].raw_response_text is not None
    finally:
        db.close()


def test_vision_assist_is_idempotent_for_same_exact_input(monkeypatch: pytest.MonkeyPatch) -> None:
    call_counts = {"chat": 0}

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            call_counts["chat"] += 1
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][0]["content"]
            match = re.search(r"Page number: (\d+)", prompt)
            page_number = int(match.group(1)) if match else 1
            return _FakeOllamaResponse(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "page_number": page_number,
                                "continues_previous_item": False,
                                "previous_item_number": None,
                                "item_segments": [],
                                "new_items": [{"item_number": str(page_number), "concept_raw_text": None, "review_required": True}],
                                "open_item_at_page_end": str(page_number),
                                "uncertainties": [],
                            }
                        )
                    }
                }
            )
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision idempotent")
    document_id = _import_vision_pdf(tender_id, "vision-idempotent.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    first_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert first_response.status_code == 200, first_response.text
    first_payload = first_response.json()

    second_response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert second_response.status_code == 200, second_response.text
    second_payload = second_response.json()

    assert first_payload["id"] == second_payload["id"]
    assert first_payload["input_fingerprint_sha256"] == second_payload["input_fingerprint_sha256"]
    assert first_payload["prompt_version"] == ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION
    assert second_payload["prompt_version"] == ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION
    assert call_counts["chat"] == 1

    db = SessionLocal()
    try:
        assert db.execute(select(func.count(DocumentVisionAnalysis.id)).where(DocumentVisionAnalysis.document_id == document_id)).scalar_one() == 1
        assert (
            db.execute(
                select(func.count(DocumentVisionPageResult.id))
                .join(DocumentVisionAnalysis, DocumentVisionAnalysis.id == DocumentVisionPageResult.analysis_id)
                .where(DocumentVisionAnalysis.document_id == document_id)
            ).scalar_one()
            == 1
        )
    finally:
        db.close()


def test_vision_assist_scopes_analysis_to_requested_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ollama_available(monkeypatch)

    tender_id = _create_tender("Vision scoped pages")
    document_id = _import_vision_pdf(tender_id, "anexo-b-4.pdf", ["ANEXO B-4 PAGE 1", "ANEXO B-4 PAGE 2"])
    _seed_normalized_lines(document_id, ["ANEXO B-4 PAGE 1", "ANEXO B-4 PAGE 2"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [2], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["page_number"] for item in payload["page_results"]] == [2]
    assert payload["page_results"][0]["structured_json"]["page_number"] == 2


def test_vision_assist_safely_handles_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ollama_available(monkeypatch, invalid_json=True)

    tender_id = _create_tender("Vision invalid json")
    document_id = _import_vision_pdf(tender_id, "vision-invalid-json.pdf", ["ANEXO B-4"])
    _seed_normalized_lines(document_id, ["ANEXO B-4"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "FAILED"
    assert payload["page_results"][0]["status"] == "INVALID_JSON"
    assert payload["page_results"][0]["structured_json"] is None
    assert payload["page_results"][0]["raw_response_text"] == "not valid json"


def test_vision_assist_rejects_cross_tender_document_ownership() -> None:
    tender_a = _create_tender("Vision owner A")
    tender_b = _create_tender("Vision owner B")
    document_id = _import_vision_pdf(tender_a, "ownership.pdf", ["ANEXO B-4"])
    _seed_normalized_lines(document_id, ["ANEXO B-4"])

    response = client.post(
        f"/tenders/{tender_b}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 404, response.text


def test_vision_assist_calls_ollama_once_per_page_in_sequence_and_passes_continuity_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_calls: list[dict[str, object]] = []

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][0]["content"]
            match = re.search(r"Page number: (\d+)", prompt)
            page_number = int(match.group(1)) if match else 1
            chat_calls.append(
                {
                    "page_number": page_number,
                    "images": len(payload["messages"][0].get("images", [])),
                    "prompt": prompt,
                }
            )

            if page_number == 1:
                content = {
                    "page_number": 1,
                    "continues_previous_item": False,
                    "new_items": [
                        {
                            "item_number": "1",
                            "concept_raw_text": "Servicio CENTUM MTBE 1",
                            "review_required": False,
                        }
                    ],
                    "item_segments": [
                        {
                            "item_number": "1",
                            "starts_on_this_page": True,
                            "has_service": True,
                            "has_supply": False,
                            "has_deliverable": False,
                            "anchor_raw_text": "PARTIDA 1 SERVICIO CENTUM MTBE 1",
                            "review_required": False,
                        }
                    ],
                    "open_item_at_page_end": "1",
                    "uncertainties": [],
                }
            elif page_number == 2:
                content = {
                    "page_number": 2,
                    "continues_previous_item": True,
                    "previous_item_number": "1",
                    "new_items": [
                        {
                            "item_number": "2",
                            "concept_raw_text": "Mantenimiento CENTUM Asfaltos",
                            "review_required": False,
                        }
                    ],
                    "item_segments": [
                        {
                            "item_number": "1",
                            "starts_on_this_page": False,
                            "has_service": True,
                            "has_supply": False,
                            "has_deliverable": False,
                            "anchor_raw_text": "CONTINUA PARTIDA 1 ACTIVIDADES EN SITIO",
                            "review_required": False,
                        },
                        {
                            "item_number": "2",
                            "starts_on_this_page": True,
                            "has_service": True,
                            "has_supply": False,
                            "has_deliverable": False,
                            "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO CENTUM ASFALTOS",
                            "review_required": False,
                        },
                    ],
                    "open_item_at_page_end": "2",
                    "uncertainties": [],
                }
            else:
                content = {
                    "page_number": 3,
                    "continues_previous_item": True,
                    "previous_item_number": "2",
                    "new_items": [],
                    "item_segments": [
                        {
                            "item_number": "2",
                            "starts_on_this_page": False,
                            "has_service": True,
                            "has_supply": False,
                            "has_deliverable": False,
                            "anchor_raw_text": "CONTINUA PARTIDA 2",
                            "review_required": False,
                        }
                    ],
                    "open_item_at_page_end": "2",
                    "uncertainties": [],
                }

            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision continuity")
    document_id = _import_vision_pdf(tender_id, "vision-continuity.pdf", ["P1", "P2", "P3"])
    _seed_normalized_lines(document_id, ["P1", "P2", "P3"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1, 2, 3], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert len(chat_calls) == 3
    assert [call["page_number"] for call in chat_calls] == [1, 2, 3]
    assert all(call["images"] == 1 for call in chat_calls)
    assert '"open_item_number":"1"' in str(chat_calls[1]["prompt"])

    page_two = payload["page_results"][1]["structured_json"]
    assert page_two["continues_previous_item"] is True
    assert page_two["previous_item_number"] == "1"
    assert page_two["new_items"][0]["item_number"] == "2"
    assert page_two["_continuity_context_used"]["open_item_number"] == "1"
    assert any(
        item_segment["item_number"] == "1" for item_segment in page_two["item_segments"]
    )
    assert any(
        item_segment["item_number"] == "2" for item_segment in page_two["item_segments"]
    )


def test_vision_assist_derives_open_item_from_single_first_page_segment() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=1,
        parsed_json={
            "page_number": 1,
            "continues_previous_item": False,
            "previous_item_number": None,
            "item_segments": [
                {
                    "item_number": " 1. ",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 1 SERVICIO CENTUM MTBE 1",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context=None,
    )

    assert structured["item_segments"][0]["item_number"] == "1"
    assert structured["open_item_at_page_end"] == "1"
    assert "NEW_ITEM_DERIVED_FROM_ITEM_START" in structured["_normalization_warnings"]
    assert "OPEN_ITEM_DERIVED_FROM_LAST_NEW_ITEM" in structured["_normalization_warnings"]


def test_vision_assist_fills_previous_item_from_context_and_derives_new_item_from_started_segment() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": None,
            "item_segments": [
                {
                    "item_number": None,
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": True,
                    "has_deliverable": True,
                    "anchor_raw_text": "CONTINUA SERVICIO EN SITIO",
                    "review_required": False,
                },
                {
                    "item_number": "2.",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO CENTUM ASFALTOS",
                    "review_required": False,
                },
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1.",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert structured["previous_item_number"] == "1"
    assert structured["item_segments"][0]["item_number"] == "1"
    assert structured["item_segments"][1]["item_number"] == "2"
    assert structured["new_items"][0]["item_number"] == "2"
    assert structured["open_item_at_page_end"] == "2"
    assert structured["_continuity_context_used"]["open_item_number"] == "1"
    assert "PREVIOUS_ITEM_FILLED_FROM_CONTEXT" in structured["_normalization_warnings"]
    assert "NEW_ITEM_DERIVED_FROM_ITEM_START" in structured["_normalization_warnings"]
    assert "OPEN_ITEM_DERIVED_FROM_LAST_NEW_ITEM" in structured["_normalization_warnings"]


def test_vision_assist_suppresses_started_segment_for_continuation_item() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": "1",
            "item_segments": [
                {
                    "item_number": "1",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert structured["item_segments"][0]["starts_on_this_page"] is False
    assert structured["new_items"] == []
    assert ollama_vision_module.WARNING_SEGMENT_START_SUPPRESSED_BY_CONTINUITY in structured["_normalization_warnings"]


def test_vision_assist_derives_new_item_when_started_segment_changes_from_previous() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": "1",
            "item_segments": [
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert [item["item_number"] for item in structured["new_items"]] == ["2"]


def test_vision_assist_treats_same_item_started_segment_as_continuation() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=3,
        parsed_json={
            "page_number": 3,
            "continues_previous_item": True,
            "previous_item_number": "2",
            "item_segments": [
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 2",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "2",
            "open_item_concept": "Mantenimiento CENTUM Asfaltos",
            "open_section": "ALCANCES",
        },
    )

    assert structured["item_segments"][0]["starts_on_this_page"] is False
    assert structured["new_items"] == []


def test_vision_assist_deduplicates_explicit_and_derived_new_items_for_same_item() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": "1",
            "item_segments": [
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO",
                    "review_required": False,
                }
            ],
            "new_items": [
                {
                    "item_number": "2",
                    "concept_raw_text": "PARTIDA 2 MANTENIMIENTO",
                    "review_required": False,
                }
            ],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert [item["item_number"] for item in structured["new_items"]] == ["2"]


def test_vision_assist_deduplicates_new_items_by_normalized_item_number() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": "1",
            "item_segments": [],
            "new_items": [
                {
                    "item_number": "2.",
                    "concept_raw_text": "PARTIDA 2 MANTENIMIENTO",
                    "review_required": False,
                },
                {
                    "item_number": "2",
                    "concept_raw_text": "PARTIDA 2 MANTENIMIENTO",
                    "review_required": True,
                },
            ],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert [item["item_number"] for item in structured["new_items"]] == ["2"]


def test_vision_assist_marks_structure_inconsistent_when_segment_changes_without_boundary() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=2,
        parsed_json={
            "page_number": 2,
            "continues_previous_item": True,
            "previous_item_number": None,
            "item_segments": [
                {
                    "item_number": "2.",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "ACTIVIDADES EN SITIO",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "1",
            "open_item_concept": "Servicio CENTUM MTBE 1",
            "open_section": "ALCANCES",
        },
    )

    assert structured["previous_item_number"] == "1"
    assert structured["item_segments"][0]["item_number"] == "2"
    assert structured["open_item_at_page_end"] is None
    assert structured["item_segments"][0]["review_required"] is True
    assert "STRUCTURE_INCONSISTENT" in structured["_normalization_warnings"]
    assert "STRUCTURE_CONTINUATION_UNRESOLVED" in structured["_normalization_warnings"]


def test_vision_assist_service_uses_structure_scope_method(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"structure": 0, "legacy": 0}

    def fake_structure_scope(self, *, page_number, image_bytes, mode, previous_page_context):
        calls["structure"] += 1
        return (
            "COMPLETED",
            {
                "page_number": page_number,
                "continues_previous_item": False,
                "previous_item_number": None,
                "item_segments": [],
                "new_items": [],
                "open_item_at_page_end": None,
                "uncertainties": [],
            },
            1,
            200,
            [],
            None,
            None,
            "{}",
        )

    def fail_legacy_alias(self, *, page_number, image_bytes, mode, previous_page_context):
        calls["legacy"] += 1
        pytest.fail("legacy analyze_page alias should not be called on live service path")

    monkeypatch.setattr(
        ollama_vision_module.OllamaVisionAssistClient,
        "analyze_structure_scope_page",
        fake_structure_scope,
    )
    monkeypatch.setattr(
        ollama_vision_module.OllamaVisionAssistClient,
        "analyze_page",
        fail_legacy_alias,
    )

    tender_id = _create_tender("Vision wiring")
    document_id = _import_vision_pdf(tender_id, "vision-wiring.pdf", ["P1"])
    _seed_normalized_lines(document_id, ["P1"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )

    assert response.status_code == 200, response.text
    assert calls["structure"] == 1
    assert calls["legacy"] == 0


def test_vision_assist_sends_think_false_stream_false_and_uses_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {"timeout": None, "payload": None, "calls": 0}

    def fake_urlopen(request, timeout):
        observed["calls"] = int(observed["calls"]) + 1
        observed["timeout"] = timeout
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        content = {
            "page_number": 1,
            "continues_previous_item": False,
            "previous_item_number": None,
            "item_segments": [],
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
        }
        return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    settings = ollama_vision_module.Settings(
        licitia_ollama_base_url="http://127.0.0.1:11434",
        licitia_ollama_vision_model="qwen3-vl:4b-instruct",
        licitia_ollama_timeout_seconds=123.0,
        licitia_vision_retry_malformed_json=0,
    )
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(settings)
    status, structured_json, processing_time_ms, http_status, warnings, *_ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )

    assert status == "COMPLETED"
    assert structured_json is not None
    assert processing_time_ms >= 0
    assert http_status == 200
    assert any(str(item).startswith("HTTP_STATUS:") for item in warnings)
    assert observed["calls"] == 1
    assert observed["timeout"] == 123.0
    request_payload = observed["payload"]
    assert isinstance(request_payload, dict)
    assert request_payload["think"] is False
    assert request_payload["stream"] is False
    assert isinstance(request_payload["format"], dict)
    format_schema = request_payload["format"]
    assert isinstance(format_schema.get("properties"), dict)
    format_properties = set(format_schema["properties"].keys())
    assert {"page_number", "continues_previous_item", "previous_item_number", "item_segments", "new_items", "open_item_at_page_end", "uncertainties"}.issubset(
        format_properties
    )
    assert "regions" not in format_properties
    assert "candidate_requirements" not in format_properties
    assert "plain_text" not in format_properties
    assert "markdown_reconstruction" not in format_properties
    item_segments_schema = format_schema["properties"]["item_segments"]
    assert item_segments_schema.get("maxItems") == 4
    prompt = request_payload["messages"][0]["content"]
    assert "candidate_requirements" not in prompt
    assert "markdown_reconstruction" not in prompt
    assert '"plain_text"' not in prompt
    assert "scope_blocks" not in prompt
    assert "supply_rows" not in prompt
    assert "regions" not in prompt
    assert "anchor_raw_text" in prompt
    assert "8 to 15 visible words" in prompt
    assert "Return item ownership segments" in prompt
    assert "An item segment is not an equipment row" in prompt
    assert "both item segments must be represented in the same response" in prompt
    assert "return one item segment for that contiguous area" in prompt
    assert "has_supply=true" in prompt
    assert "do not infer values from neighboring columns" in prompt.lower()
    assert request_payload["options"]["num_predict"] == 600


def test_vision_assist_does_not_retry_on_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        raise ollama_vision_module.urllib.error.HTTPError(
            url=request.full_url,
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    settings = ollama_vision_module.Settings(licitia_vision_retry_malformed_json=1)
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(settings)
    status, structured_json, _, http_status, _, _, _, _ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )

    assert status == "FAILED"
    assert structured_json is None
    assert http_status == 500
    assert calls["count"] == 1


def test_vision_assist_does_not_cascade_retry_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        raise TimeoutError("vision timeout")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    settings = ollama_vision_module.Settings(licitia_vision_retry_malformed_json=1)
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(settings)
    status, structured_json, _, http_status, warnings, _, _, _ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )

    assert status == "FAILED"
    assert structured_json is None
    assert http_status is None
    assert any("timeout" in str(warning).lower() for warning in warnings)
    assert calls["count"] == 1


def test_vision_assist_regions_over_schema_bound_returns_controlled_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/chat"):
            content = {
                "page_number": 1,
                "continues_previous_item": False,
                "previous_item_number": None,
                "item_segments": [
                    {
                        "item_number": "1",
                        "starts_on_this_page": idx == 1,
                        "has_service": True,
                        "has_supply": False,
                        "has_deliverable": False,
                        "anchor_raw_text": f"REGION {idx}",
                        "review_required": False,
                    }
                    for idx in range(1, 10)
                ],
                "new_items": [],
                "open_item_at_page_end": "1",
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    client_under_test = ollama_vision_module.OllamaVisionAssistClient(
        ollama_vision_module.Settings(licitia_vision_retry_malformed_json=0)
    )
    status, structured_json, _, http_status, warnings, _, _, _ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )

    assert status == "INVALID_JSON"
    assert structured_json is None
    assert http_status == 200
    assert "INVALID_JSON" in warnings


def test_vision_assist_preserves_raw_visible_text_and_null_uncertainty_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            content = {
                "page_number": 1,
                "continues_previous_item": False,
                "previous_item_number": None,
                "new_items": [{"item_number": "1", "concept_raw_text": "MODULO DE SALIDAS ANALOGICAS", "review_required": False}],
                "item_segments": [
                    {
                        "item_number": "1",
                        "starts_on_this_page": True,
                        "has_service": False,
                        "has_supply": True,
                        "has_deliverable": False,
                        "anchor_raw_text": "MODULO SALIDAS ANALOGICAS YOKOGAWA AAI543",
                        "review_required": False,
                    }
                ],
                "open_item_at_page_end": "1",
                "uncertainties": ["Modelo no legible con certeza; se mantiene null."],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision model mismatch")
    document_id = _import_vision_pdf(tender_id, "vision-model-mismatch.pdf", ["P1"])
    _seed_normalized_lines(document_id, ["P1"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    structured = payload["page_results"][0]["structured_json"]
    assert structured["item_segments"][0]["has_supply"] is True
    assert structured["item_segments"][0]["anchor_raw_text"]
    assert "scope_blocks" not in structured
    assert structured["uncertainties"]


def test_vision_assist_failed_same_fingerprint_is_retryable_without_duplicate_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"chat_calls": 0}

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            state["chat_calls"] += 1
            if state["chat_calls"] == 1:
                raise ollama_vision_module.urllib.error.HTTPError(
                    url=request.full_url,
                    code=500,
                    msg="Internal Server Error",
                    hdrs=None,
                    fp=None,
                )
            content = {
                "page_number": 1,
                "continues_previous_item": False,
                "previous_item_number": None,
                "new_items": [{"item_number": "1", "concept_raw_text": "Servicio MTBE 1", "review_required": False}],
                "item_segments": [
                    {
                        "item_number": "1",
                        "starts_on_this_page": True,
                        "has_service": True,
                        "has_supply": False,
                        "has_deliverable": False,
                        "anchor_raw_text": "PARTIDA 1 SERVICIO MTBE 1",
                        "review_required": False,
                    }
                ],
                "open_item_at_page_end": "1",
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision failed retryable")
    document_id = _import_vision_pdf(tender_id, "vision-failed-retryable.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    first = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "FAILED"

    second = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert second.status_code == 200, second.text
    second_payload = second.json()
    assert second_payload["status"] == "COMPLETED"
    assert state["chat_calls"] == 2

    db = SessionLocal()
    try:
        analysis_rows = db.execute(
            select(DocumentVisionAnalysis)
            .where(DocumentVisionAnalysis.document_id == document_id)
            .order_by(DocumentVisionAnalysis.created_at.asc())
        ).scalars().all()
        assert len(analysis_rows) == 1
        assert analysis_rows[0].status == "COMPLETED"

        page_rows = db.execute(
            select(DocumentVisionPageResult).where(DocumentVisionPageResult.analysis_id == analysis_rows[0].id)
        ).scalars().all()
        assert len(page_rows) == 1
        assert page_rows[0].status == "COMPLETED"
    finally:
        db.close()


def test_vision_assist_failed_page_does_not_fabricate_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            payload = json.loads(request.data.decode("utf-8"))
            prompt = payload["messages"][0]["content"]
            match = re.search(r"Page number: (\d+)", prompt)
            page_number = int(match.group(1)) if match else 1
            if page_number == 2:
                raise ollama_vision_module.urllib.error.HTTPError(
                    url=request.full_url,
                    code=500,
                    msg="Internal Server Error",
                    hdrs=None,
                    fp=None,
                )
            content = {
                "page_number": page_number,
                "continues_previous_item": page_number > 1,
                "previous_item_number": "1" if page_number > 1 else None,
                "new_items": [],
                "item_segments": [
                    {
                        "item_number": "1",
                        "starts_on_this_page": False,
                        "has_service": True,
                        "has_supply": False,
                        "has_deliverable": False,
                        "anchor_raw_text": "SERVICIO",
                        "review_required": False,
                    }
                ],
                "open_item_at_page_end": "1",
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision controlled failure")
    document_id = _import_vision_pdf(tender_id, "vision-controlled-failure.pdf", ["P1", "P2", "P3"])
    _seed_normalized_lines(document_id, ["P1", "P2", "P3"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1, 2, 3], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["status"] == "PARTIAL"
    statuses = [page["status"] for page in payload["page_results"]]
    assert statuses == ["COMPLETED", "FAILED", "COMPLETED"]
    assert payload["page_results"][1]["structured_json"] is None
    page_three = payload["page_results"][2]
    assert page_three["structured_json"]["_continuity_context_used"] is None
    assert page_three["structured_json"]["_continuity_state_quality"] == "UNKNOWN"
    assert all(segment["review_required"] is True for segment in page_three["structured_json"]["item_segments"])
    assert ollama_vision_module.WARNING_CONTINUITY_CONTEXT_LOST_AFTER_PAGE_FAILURE in page_three["warnings"]


def test_vision_default_model_is_instruct_and_model_is_configurable() -> None:
    default_settings = ollama_vision_module.Settings()
    assert default_settings.licitia_ollama_vision_model == "qwen3-vl:4b-instruct"

    custom_settings = ollama_vision_module.Settings(licitia_ollama_vision_model="llava:latest")
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(custom_settings)
    assert client_under_test.model_name == "llava:latest"


def test_vision_model_unavailable_does_not_silently_fallback_to_thinking_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b"}]})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    response = client.get("/vision/providers")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configured_model"] == "qwen3-vl:4b-instruct"
    assert payload["model_available"] is False
    assert payload["selected_model"] is None

    tender_id = _create_tender("Vision model unavailable")
    document_id = _import_vision_pdf(tender_id, "vision-model-unavailable.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    analyze = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert analyze.status_code == 503, analyze.text
    assert "MODEL_UNAVAILABLE" in analyze.text


def test_structure_scope_request_uses_bounded_output_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {"request": None}

    def fake_urlopen(request, timeout):
        observed["request"] = json.loads(request.data.decode("utf-8"))
        content = {
            "page_number": 1,
            "continues_previous_partida": False,
            "previous_partida_number": None,
            "new_partidas": [],
            "scope_blocks": [],
            "supply_rows": [],
            "open_partida_at_page_end": {"item_number": None, "concept_raw_text": None},
            "uncertainties": [],
        }
        return _FakeOllamaResponse(
            {
                "message": {"content": json.dumps(content)},
                "done_reason": "stop",
                "prompt_eval_count": 111,
                "eval_count": 120,
            }
        )

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    settings = ollama_vision_module.Settings(
        licitia_vision_structure_scope_max_output_tokens=550,
        licitia_vision_retry_malformed_json=0,
    )
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(settings)
    status, structured_json, *_ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )
    assert status == "COMPLETED"
    assert structured_json is not None

    payload = observed["request"]
    assert isinstance(payload, dict)
    assert payload["options"]["num_predict"] == 550
    assert "Task type: STRUCTURE_SCOPE" in payload["messages"][0]["content"]


def test_detail_transcription_is_conditional_and_task_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})

        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        calls.append(prompt)

        if "Task type: DETAIL_TRANSCRIPTION" in prompt:
            content = {
                "source_page": 1,
                "raw_lines": [
                    {
                        "raw_visible_text": "MODULO DE SALIDAS ANALOGICAS, MARCA: YOKOGAWA, MODELO: AAI543-H50/K4A00 (1 PIEZA)",
                        "uncertain": False,
                        "uncertain_characters": [],
                    }
                ],
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})

        content = {
            "page_number": 1,
            "continues_previous_partida": False,
            "previous_partida_number": None,
            "new_partidas": [{"item_number": "1", "concept_raw_text": "Servicio", "starts_on_this_page": True}],
            "item_segments": [
                {
                    "item_number": "1",
                    "starts_on_this_page": True,
                    "has_service": False,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "LISTA DE SUMINISTRO",
                    "review_required": True,
                }
            ],
            "open_partida_at_page_end": {"item_number": "1", "concept_raw_text": "Servicio"},
            "uncertainties": [],
        }
        return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision detail conditional")
    document_id = _import_vision_pdf(tender_id, "vision-detail-conditional.pdf", ["P1"])
    _seed_normalized_lines(document_id, ["P1"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["page_results"][0]["status"] == "COMPLETED"
    assert any("Task type: STRUCTURE_SCOPE" in call for call in calls)
    assert any("Task type: DETAIL_TRANSCRIPTION" in call for call in calls)

    calls.clear()

    def fake_urlopen_no_detail(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        calls.append(prompt)
        content = {
            "page_number": 1,
            "continues_previous_partida": False,
            "previous_partida_number": None,
            "new_partidas": [],
            "item_segments": [{"item_number": "1", "starts_on_this_page": True, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "SERVICIO", "review_required": False}],
            "open_partida_at_page_end": {"item_number": "1", "concept_raw_text": "SERVICIO"},
            "uncertainties": [],
        }
        return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen_no_detail)

    document_id_no_detail = _import_vision_pdf(tender_id, "vision-detail-conditional-no-detail.pdf", ["P1 no detail"])
    _seed_normalized_lines(document_id_no_detail, ["P1 no detail"])

    response_no_detail = client.post(
        f"/tenders/{tender_id}/documents/{document_id_no_detail}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response_no_detail.status_code == 200, response_no_detail.text
    assert any("Task type: STRUCTURE_SCOPE" in call for call in calls)
    assert all("Task type: DETAIL_TRANSCRIPTION" not in call for call in calls)


def test_detail_failure_after_successful_structure_keeps_next_page_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})

        payload = json.loads(request.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        if "Task type: DETAIL_TRANSCRIPTION" in prompt:
            return _FakeOllamaResponse({"message": {"content": ""}, "done_reason": "length"})

        match = re.search(r"Page number: (\d+)", prompt)
        page_number = int(match.group(1)) if match else 1
        calls.append({"page_number": str(page_number), "prompt": prompt})
        content = {
            "page_number": page_number,
            "continues_previous_item": page_number > 1,
            "previous_item_number": "2" if page_number > 1 else None,
            "item_segments": [
                {
                    "item_number": "2",
                    "starts_on_this_page": page_number == 1,
                    "has_service": page_number > 1,
                    "has_supply": True if page_number == 1 else False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 SUMINISTRO" if page_number == 1 else "CONTINUA PARTIDA 2",
                    "review_required": False,
                }
            ],
            "new_items": [
                {"item_number": "2", "concept_raw_text": "Partida 2", "review_required": False}
            ] if page_number == 1 else [],
            "open_item_at_page_end": "2",
            "uncertainties": [],
        }
        return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision detail failure keeps context")
    document_id = _import_vision_pdf(tender_id, "vision-detail-failure-context.pdf", ["P1", "P2"])
    _seed_normalized_lines(document_id, ["P1", "P2"])

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1, 2], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["page_results"][0]["status"] == "PARTIAL"
    assert '"open_item_number":"2"' in calls[1]["prompt"]
    assert payload["page_results"][1]["structured_json"]["_continuity_context_used"]["open_item_number"] == "2"


def test_done_reason_length_with_incomplete_json_returns_output_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        return _FakeOllamaResponse({
            "message": {"content": "{\"page_number\":1,\"new_partidas\":["},
            "done_reason": "length",
            "eval_count": 600,
        })

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    client_under_test = ollama_vision_module.OllamaVisionAssistClient(ollama_vision_module.Settings())
    status, structured_json, _, _, warnings, _, _, _ = client_under_test.analyze_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )
    assert status == "FAILED"
    assert structured_json is None
    assert any("OUTPUT_TRUNCATED" in str(warning) for warning in warnings)


def test_empty_content_and_thinking_only_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        return _FakeOllamaResponse(
            {
                "message": {"content": "", "thinking": "hidden chain"},
                "done_reason": "length",
            }
        )

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    client_under_test = ollama_vision_module.OllamaVisionAssistClient(ollama_vision_module.Settings())
    status, structured_json, _, _, warnings, _, _, _ = client_under_test.analyze_page(
        page_number=1,
        image_bytes=b"fake-page",
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )
    assert status == "FAILED"
    assert structured_json is None
    assert "EMPTY_CONTENT" in warnings
    assert "THINKING_CONTENT_IGNORED" in warnings


def test_detail_parser_extracts_fields_and_preserves_raw_text() -> None:
    parsed = ollama_vision_module._parse_supply_line(
        "MODULO DE SALIDAS ANALOGICAS, MARCA: YOKOGAWA, MODELO: AAI543-H50/K4A00 (1 PIEZA)"
    )
    assert parsed["raw_visible_text"].startswith("MODULO DE SALIDAS ANALOGICAS")
    assert parsed["brand"] == "YOKOGAWA"
    assert parsed["model"] == "AAI543-H50/K4A00"
    assert parsed["quantity"] == "1"
    assert parsed["unit"] == "PIEZA"


def test_detail_parser_failure_preserves_raw_text_and_marks_review() -> None:
    parsed = ollama_vision_module._parse_supply_line("CODIGO TECNICO I/1 O/0 Z/2 S/5")
    assert parsed["raw_visible_text"] == "CODIGO TECNICO I/1 O/0 Z/2 S/5"
    assert parsed["brand"] is None
    assert parsed["model"] is None
    assert parsed["review_required"] is True


def test_task_fingerprint_differs_by_task_type_and_region() -> None:
    base = {
        "model_name": "qwen3-vl:4b-instruct",
        "prompt_version": "v1",
        "page_number": 2,
        "image_sha256": "abc123",
    }
    structure = ollama_vision_module._build_task_fingerprint(
        task_type="STRUCTURE_SCOPE",
        task_region_id=None,
        **base,
    )
    detail_a = ollama_vision_module._build_task_fingerprint(
        task_type="DETAIL_TRANSCRIPTION",
        task_region_id="SUPPLY:TOP",
        **base,
    )
    detail_b = ollama_vision_module._build_task_fingerprint(
        task_type="DETAIL_TRANSCRIPTION",
        task_region_id="SUPPLY:BOTTOM",
        **base,
    )
    assert structure != detail_a
    assert detail_a != detail_b


def test_structure_scope_prompt_version_bumped_for_normalization_semantics() -> None:
    assert ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION == "vision-structure-scope-2026-09-01-005"


def test_structure_scope_input_fingerprint_differs_by_prompt_version() -> None:
    rendered_pages = [
        ollama_vision_module.RenderedVisionPage(
            page_number=1,
            document_page_id="page-1",
            image_bytes=b"",
            image_sha256="sha-page-1",
            width_px=100,
            height_px=100,
            image_bytes_size=0,
            render_time_ms=1,
            render_zoom=2.0,
            warnings=[],
        )
    ]

    fingerprint_004 = ollama_vision_module._build_input_fingerprint(
        tender_id="tender-1",
        document_id="document-1",
        model_name="qwen3-vl:4b-instruct",
        prompt_version="vision-structure-scope-2026-09-01-004",
        mode="ASSISTIVE_EXTRACTION",
        rendered_pages=rendered_pages,
        task_type="STRUCTURE_SCOPE",
        task_region_id=None,
    )
    fingerprint_005 = ollama_vision_module._build_input_fingerprint(
        tender_id="tender-1",
        document_id="document-1",
        model_name="qwen3-vl:4b-instruct",
        prompt_version=ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
        mode="ASSISTIVE_EXTRACTION",
        rendered_pages=rendered_pages,
        task_type="STRUCTURE_SCOPE",
        task_region_id=None,
    )

    assert fingerprint_004 != fingerprint_005


def test_completed_old_structure_scope_analysis_is_not_reused_after_version_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_counts = {"chat": 0}

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            call_counts["chat"] += 1
            content = {
                "page_number": 1,
                "continues_previous_item": False,
                "previous_item_number": None,
                "item_segments": [
                    {
                        "item_number": "1",
                        "starts_on_this_page": True,
                        "has_service": True,
                        "has_supply": False,
                        "has_deliverable": False,
                        "anchor_raw_text": "PARTIDA 1 SERVICIO",
                        "review_required": False,
                    }
                ],
                "new_items": [
                    {
                        "item_number": "1",
                        "concept_raw_text": "PARTIDA 1 SERVICIO",
                        "review_required": False,
                    }
                ],
                "open_item_at_page_end": "1",
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision version bump")
    document_id = _import_vision_pdf(tender_id, "vision-version-bump.pdf", ["ANEXO B-4", "PARTIDA 1"])
    _seed_normalized_lines(document_id, ["ANEXO B-4", "PARTIDA 1"])

    db = SessionLocal()
    try:
        document = db.get(TenderDocument, document_id)
        assert document is not None
        service = ollama_vision_module.VisionAssistService(db)
        rendered_pages = service._render_requested_pages(document, [1])
        old_fingerprint = ollama_vision_module._build_input_fingerprint(
            tender_id=tender_id,
            document_id=document_id,
            model_name="qwen3-vl:4b-instruct",
            prompt_version="vision-structure-scope-2026-09-01-004",
            mode="ASSISTIVE_EXTRACTION",
            rendered_pages=rendered_pages,
            task_type="STRUCTURE_SCOPE",
            task_region_id=None,
        )
        historical = DocumentVisionAnalysis(
            tender_id=tender_id,
            document_id=document_id,
            status="COMPLETED",
            mode="ASSISTIVE_EXTRACTION",
            model_name="qwen3-vl:4b-instruct",
            prompt_version="vision-structure-scope-2026-09-01-004",
            input_fingerprint_sha256=old_fingerprint,
            analyzed_at=datetime.now(timezone.utc),
        )
        db.add(historical)
        db.flush()
        db.add(
            DocumentVisionPageResult(
                analysis_id=historical.id,
                document_page_id=rendered_pages[0].document_page_id,
                page_number=1,
                image_sha256=rendered_pages[0].image_sha256,
                status="COMPLETED",
                raw_response_text='{"page_number":1}',
                structured_json={"page_number": 1},
                warnings=[],
                processing_time_ms=1,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["prompt_version"] == ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION
    assert payload["prompt_version"] != "vision-structure-scope-2026-09-01-004"
    assert call_counts["chat"] == 1

    db = SessionLocal()
    try:
        analyses = db.execute(
            select(DocumentVisionAnalysis)
            .where(DocumentVisionAnalysis.document_id == document_id)
            .order_by(DocumentVisionAnalysis.created_at.asc())
        ).scalars().all()
        assert len(analyses) == 2
        assert {analysis.prompt_version for analysis in analyses} == {
            "vision-structure-scope-2026-09-01-004",
            "vision-structure-scope-2026-09-01-005",
        }
        assert any(analysis.status == "COMPLETED" and analysis.prompt_version == "vision-structure-scope-2026-09-01-004" for analysis in analyses)
        assert any(analysis.id == payload["id"] and analysis.prompt_version == ollama_vision_module.VISION_STRUCTURE_SCOPE_PROMPT_VERSION for analysis in analyses)
    finally:
        db.close()


def test_structure_scope_aggregated_supply_block_fixture_is_accepted_and_triggers_detail() -> None:
    structured = ollama_vision_module.OllamaVisionAssistClient._normalize_structured_json(
        page_number=4,
        parsed_json={
            "page_number": 4,
            "continues_previous_item": True,
            "previous_item_number": "2",
            "item_segments": [
                {
                    "item_number": "2",
                    "starts_on_this_page": False,
                    "has_service": False,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "YOKOGAWA MODULE LIST MARCA MODELO PIEZAS",
                    "review_required": False,
                }
            ],
            "new_items": [],
            "open_item_at_page_end": "2",
            "uncertainties": [],
        },
        previous_page_context={
            "open_item_number": "2",
            "open_item_concept": "Mantenimiento CENTUM Asfaltos",
            "open_section": "ALCANCES",
        },
    )

    assert len(structured["item_segments"]) == 1
    assert structured["item_segments"][0]["has_supply"] is True
    assert structured["item_segments"][0]["item_number"] == "2"
    assert structured["open_item_at_page_end"] == "2"
    assert ollama_vision_module._should_run_detail_transcription(structured) is True


def test_detail_transcription_version_remains_unchanged() -> None:
    assert ollama_vision_module.VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION == "vision-detail-transcription-2026-08-31-001"


def test_output_truncated_same_fingerprint_is_retryable_without_duplicate_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"chat_calls": 0}

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeOllamaResponse({"models": [{"name": "qwen3-vl:4b-instruct"}]})
        if request.full_url.endswith("/api/chat"):
            state["chat_calls"] += 1
            if state["chat_calls"] == 1:
                return _FakeOllamaResponse(
                    {
                        "message": {"content": "{\"page_number\":1,\"new_partidas\":["},
                        "done_reason": "length",
                    }
                )
            content = {
                "page_number": 1,
                "continues_previous_partida": False,
                "previous_partida_number": None,
                "new_partidas": [{"item_number": "1", "concept_raw_text": "Servicio", "starts_on_this_page": True}],
                "scope_blocks": [],
                "supply_rows": [],
                "open_partida_at_page_end": {"item_number": "1", "concept_raw_text": "Servicio"},
                "uncertainties": [],
            }
            return _FakeOllamaResponse({"message": {"content": json.dumps(content)}, "done_reason": "stop"})
        raise AssertionError(f"Unexpected Ollama URL: {request.full_url}")

    monkeypatch.setattr(ollama_vision_module.urllib.request, "urlopen", fake_urlopen)

    tender_id = _create_tender("Vision truncated retryable")
    document_id = _import_vision_pdf(tender_id, "vision-truncated-retryable.pdf", ["ANEXO B-4"])
    _seed_normalized_lines(document_id, ["ANEXO B-4"])

    first = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "FAILED"

    second = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/vision-analyze",
        json={"page_numbers": [1], "mode": "ASSISTIVE_EXTRACTION"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "COMPLETED"

    db = SessionLocal()
    try:
        analyses = db.execute(
            select(DocumentVisionAnalysis).where(DocumentVisionAnalysis.document_id == document_id)
        ).scalars().all()
        assert len(analyses) == 1
    finally:
        db.close()


def _seed_vision_analysis_with_pages(
    *,
    tender_id: str,
    document_id: str,
    prompt_version: str,
    status: str,
    model_name: str = "qwen3-vl:4b-instruct",
    page_rows: list[dict[str, object]],
) -> str:
    db = SessionLocal()
    try:
        analysis = DocumentVisionAnalysis(
            tender_id=tender_id,
            document_id=document_id,
            status=status,
            mode="ASSISTIVE_EXTRACTION",
            model_name=model_name,
            prompt_version=prompt_version,
            input_fingerprint_sha256=hashlib.sha256(f"{prompt_version}-{status}-{len(page_rows)}".encode("utf-8")).hexdigest(),
            analyzed_at=datetime.now(timezone.utc),
        )
        db.add(analysis)
        db.flush()

        pages = {
            page.page_number: page
            for page in db.execute(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            ).scalars().all()
        }

        for row in page_rows:
            page_number = int(row["page_number"])
            page = pages[page_number]
            db.add(
                DocumentVisionPageResult(
                    analysis_id=analysis.id,
                    document_page_id=page.id,
                    page_number=page_number,
                    image_sha256=f"sha-{analysis.id}-{page_number}",
                    status=str(row.get("status") or "COMPLETED"),
                    raw_response_text=str(row.get("raw_response_text") or "{\"raw\":true}"),
                    structured_json=row.get("structured_json"),
                    warnings=list(row.get("warnings") or []),
                    processing_time_ms=1,
                )
            )
        db.commit()
        return analysis.id
    finally:
        db.close()


def test_vision_latest_summary_prefers_current_005_over_legacy() -> None:
    tender_id = _create_tender("Vision latest summary preferred version")
    document_id = _import_vision_pdf(tender_id, "vision-latest-summary-preferred.pdf", ["P1", "P2"])
    _seed_normalized_lines(document_id, ["P1", "P2"])

    analysis_005_id = _seed_vision_analysis_with_pages(
        tender_id=tender_id,
        document_id=document_id,
        prompt_version="vision-structure-scope-2026-09-01-005",
        status="PARTIAL",
        page_rows=[
            {
                "page_number": 1,
                "status": "COMPLETED",
                "structured_json": {
                    "page_number": 1,
                    "continues_previous_item": False,
                    "previous_item_number": None,
                    "item_segments": [{"item_number": "1", "starts_on_this_page": True, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "PARTIDA 1", "review_required": False}],
                    "new_items": [{"item_number": "1", "concept_raw_text": "PARTIDA 1 SERVICIO", "review_required": True}],
                    "open_item_at_page_end": "1",
                    "uncertainties": [],
                    "_continuity_state_quality": "VALID",
                },
            }
        ],
    )

    _seed_vision_analysis_with_pages(
        tender_id=tender_id,
        document_id=document_id,
        prompt_version="vision-structure-scope-2026-09-01-004",
        status="COMPLETED",
        page_rows=[
            {
                "page_number": 1,
                "status": "COMPLETED",
                "structured_json": {
                    "page_number": 1,
                    "continues_previous_item": False,
                    "previous_item_number": None,
                    "item_segments": [],
                    "new_items": [{"item_number": "9", "concept_raw_text": "LEGACY", "review_required": True}],
                    "open_item_at_page_end": "9",
                    "uncertainties": [],
                    "_continuity_state_quality": "VALID",
                },
            }
        ],
    )

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/vision-results/latest-summary")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latest_analysis"] is not None
    assert payload["latest_analysis"]["analysis_id"] == analysis_005_id
    assert payload["latest_analysis"]["prompt_version"] == "vision-structure-scope-2026-09-01-005"


def test_vision_latest_summary_derives_candidates_and_status_without_heavy_payload() -> None:
    tender_id = _create_tender("Vision latest summary candidates")
    document_id = _import_vision_pdf(tender_id, "vision-latest-summary-candidates.pdf", ["P1", "P2", "P3", "P4"])
    _seed_normalized_lines(document_id, ["P1", "P2", "P3", "P4"])

    _seed_vision_analysis_with_pages(
        tender_id=tender_id,
        document_id=document_id,
        prompt_version="vision-structure-scope-2026-09-01-005",
        status="PARTIAL",
        page_rows=[
            {
                "page_number": 1,
                "status": "COMPLETED",
                "structured_json": {
                    "page_number": 1,
                    "continues_previous_item": False,
                    "previous_item_number": None,
                    "item_segments": [{"item_number": "1", "starts_on_this_page": True, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "PARTIDA 1", "review_required": False}],
                    "new_items": [{"item_number": "1", "concept_raw_text": "PARTIDA 1 SERVICIO", "review_required": False}],
                    "open_item_at_page_end": "1",
                    "uncertainties": [],
                    "_continuity_state_quality": "VALID",
                },
            },
            {
                "page_number": 2,
                "status": "PARTIAL",
                "structured_json": {
                    "page_number": 2,
                    "continues_previous_item": True,
                    "previous_item_number": "1",
                    "item_segments": [
                        {"item_number": "1", "starts_on_this_page": False, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "CONTINUA 1", "review_required": False},
                        {"item_number": "2", "starts_on_this_page": True, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "PARTIDA 2", "review_required": True},
                    ],
                    "new_items": [
                        {"item_number": "2.", "concept_raw_text": "PARTIDA 2 MANTENIMIENTO", "review_required": True},
                        {"item_number": "2", "concept_raw_text": None, "review_required": True},
                    ],
                    "open_item_at_page_end": "2",
                    "uncertainties": [],
                    "detail_transcription": {"raw_lines": [{"raw_visible_text": "NO DEBE EXPONERSE"}]},
                    "_detail_runtime": {"status": "FAILED", "task_type": "DETAIL_TRANSCRIPTION"},
                    "_continuity_state_quality": "VALID",
                },
            },
            {
                "page_number": 3,
                "status": "COMPLETED",
                "structured_json": {
                    "page_number": 3,
                    "continues_previous_item": True,
                    "previous_item_number": "2",
                    "item_segments": [{"item_number": "2", "starts_on_this_page": False, "has_service": True, "has_supply": False, "has_deliverable": False, "anchor_raw_text": "CONTINUA 2", "review_required": True}],
                    "new_items": [],
                    "open_item_at_page_end": "2",
                    "uncertainties": [],
                    "_continuity_state_quality": "VALID",
                },
            },
            {
                "page_number": 4,
                "status": "COMPLETED",
                "structured_json": {
                    "page_number": 4,
                    "continues_previous_item": True,
                    "previous_item_number": "2",
                    "item_segments": [{"item_number": "2", "starts_on_this_page": False, "has_service": False, "has_supply": True, "has_deliverable": False, "anchor_raw_text": "LISTADO", "review_required": True}],
                    "new_items": [],
                    "open_item_at_page_end": "2",
                    "uncertainties": [],
                    "_detail_runtime": {"status": "COMPLETED", "task_type": "DETAIL_TRANSCRIPTION"},
                    "_continuity_state_quality": "VALID",
                },
            },
        ],
    )

    before_items_response = client.get(f"/tenders/{tender_id}/items", params={"document_id": document_id})
    assert before_items_response.status_code == 200, before_items_response.text
    before_items_total = before_items_response.json()["summary"]["total_items"]

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/vision-results/latest-summary")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latest_analysis"]["status"] == "PARTIAL"
    structure_summary = payload["latest_analysis"]["structure_summary"]
    assert structure_summary["page_count"] == 4
    assert structure_summary["valid_structure_pages"] == 4
    assert structure_summary["structure_continuity_valid"] is True
    assert structure_summary["detail_partial_pages"] == [2]

    candidates = payload["item_candidates"]
    assert [candidate["item_number"] for candidate in candidates] == ["1", "2"]
    candidate_one = next(candidate for candidate in candidates if candidate["item_number"] == "1")
    candidate_two = next(candidate for candidate in candidates if candidate["item_number"] == "2")
    assert candidate_one["observed_pages"] == [1, 2]
    assert candidate_two["observed_pages"] == [2, 3, 4]

    page_summaries = payload["page_summaries"]
    assert len(page_summaries) == 4
    assert all(page_summary["structure_status"] == "VALID" for page_summary in page_summaries)
    assert page_summaries[1]["detail_status"] == "FAILED"
    assert page_summaries[3]["detail_status"] == "COMPLETED"

    assert "analyses" not in payload
    assert "raw_response_text" not in json.dumps(payload)
    assert "detail_transcription" not in json.dumps(payload)

    after_items_response = client.get(f"/tenders/{tender_id}/items", params={"document_id": document_id})
    assert after_items_response.status_code == 200, after_items_response.text
    after_items_total = after_items_response.json()["summary"]["total_items"]
    assert before_items_total == 0
    assert after_items_total == before_items_total


def test_vision_latest_summary_returns_clean_empty_response_when_no_analysis() -> None:
    tender_id = _create_tender("Vision latest summary empty")
    document_id = _import_vision_pdf(tender_id, "vision-latest-summary-empty.pdf", ["P1"])
    _seed_normalized_lines(document_id, ["P1"])

    response = client.get(f"/tenders/{tender_id}/documents/{document_id}/vision-results/latest-summary")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["document_id"] == document_id
    assert payload["latest_analysis"] is None
    assert payload["item_candidates"] == []
    assert payload["page_summaries"] == []


@pytest.mark.local_ollama
def test_local_ollama_live_structure_scope_opt_in() -> None:
    if os.getenv("RUN_LOCAL_OLLAMA_TESTS") != "1":
        pytest.skip("opt-in only: set RUN_LOCAL_OLLAMA_TESTS=1")
    image_path = os.getenv("LOCAL_OLLAMA_TEST_IMAGE")
    if not image_path:
        pytest.skip("set LOCAL_OLLAMA_TEST_IMAGE to a real page PNG path")

    image_bytes = Path(image_path).read_bytes()
    settings = ollama_vision_module.Settings(
        licitia_ollama_vision_model="qwen3-vl:4b-instruct",
        licitia_vision_structure_scope_max_output_tokens=600,
    )
    client_under_test = ollama_vision_module.OllamaVisionAssistClient(settings)
    status, structured_json, _, _, warnings, _, _, _ = client_under_test.analyze_structure_scope_page(
        page_number=1,
        image_bytes=image_bytes,
        mode="ASSISTIVE_EXTRACTION",
        previous_page_context=None,
    )
    assert status in {"COMPLETED", "FAILED", "INVALID_JSON"}
    assert isinstance(warnings, list)
    if status == "COMPLETED":
        assert structured_json is not None
