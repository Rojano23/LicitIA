import hashlib

from fastapi.testclient import TestClient

from app.main import app

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
