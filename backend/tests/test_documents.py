import hashlib

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import TenderDocument

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
    assert "invalid" in response.text.lower() or "escapes" in response.text.lower()


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
