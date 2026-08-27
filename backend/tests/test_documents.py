import hashlib

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, PageOcrResult, TenderDocument

client = TestClient(app)


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
