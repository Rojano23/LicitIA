import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Company, CompanyDocument, TenderDocument

client = TestClient(app)


def _create_company(name: str = "Empresa Uno") -> str:
    response = client.post(
        "/companies",
        json={
            "name": name,
            "legal_name": f"{name} SA de CV",
            "tax_id": "AAA010101AAA",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_company_file(company_id: str, filename: str, payload: bytes, mime_type: str = "text/plain") -> dict:
    response = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", (filename, payload, mime_type))],
        data={"source_relative_paths": f"empresa/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]


def _stored_file_bytes(stored_relative_path: str) -> bytes:
    root = Path(__file__).resolve().parents[1] / ".licitia-data-test"
    file_path = root / stored_relative_path
    assert file_path.exists()
    return file_path.read_bytes()


def test_create_list_and_patch_company() -> None:
    company_id = _create_company("Industrial Base")

    listed = client.get("/companies")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert any(item["id"] == company_id for item in payload)

    updated = client.patch(
        f"/companies/{company_id}",
        json={
            "name": "Industrial Base MX",
            "status": "ARCHIVED",
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["name"] == "Industrial Base MX"
    assert updated_payload["status"] == "ARCHIVED"


def test_company_document_import_duplicate_and_new_document_conflict_resolution() -> None:
    company_id = _create_company("Documentos Empresa")
    first_payload = b"constancia fiscal v1\n"

    first = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("constancia.txt", first_payload, "text/plain"))],
        data={"source_relative_paths": "empresa/constancia.txt"},
    )
    assert first.status_code == 200, first.text
    first_result = first.json()[0]
    assert first_result["status"] == "IMPORTED"
    assert first_result["sha256"] == hashlib.sha256(first_payload).hexdigest()

    duplicate = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("constancia.txt", first_payload, "text/plain"))],
        data={"source_relative_paths": "empresa/constancia.txt"},
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()[0]["status"] == "DUPLICATE"

    conflict = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("constancia.txt", b"constancia fiscal v2\n", "text/plain"))],
        data={"source_relative_paths": "empresa/constancia.txt"},
    )
    assert conflict.status_code == 200, conflict.text
    assert conflict.json()[0]["status"] == "NAME_CONFLICT"

    resolved = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("constancia.txt", b"constancia fiscal v2\n", "text/plain"))],
        data={
            "source_relative_paths": "empresa/constancia.txt",
            "conflict_action": "NEW_DOCUMENT",
        },
    )
    assert resolved.status_code == 200, resolved.text
    resolved_result = resolved.json()[0]
    assert resolved_result["status"] == "IMPORTED"
    assert resolved_result["conflict_resolution_action"] == "NEW_DOCUMENT"

    documents = client.get(f"/companies/{company_id}/documents")
    assert documents.status_code == 200, documents.text
    assert len(documents.json()) == 2


def test_company_document_revision_update_archive_and_view_content() -> None:
    company_id = _create_company("Certificados MX")
    base_payload = b"%PDF-1.4\n1 0 obj\n<< /Title (CERT) >>\nendobj\n%%EOF\n"

    first = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("certificado.pdf", base_payload, "application/pdf"))],
        data={"source_relative_paths": "certs/certificado.pdf"},
    )
    assert first.status_code == 200, first.text
    first_result = first.json()[0]
    first_document_id = first_result["document_id"]

    revision = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("certificado.pdf", b"%PDF-1.4\nnew\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "certs/certificado.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_document_id,
        },
    )
    assert revision.status_code == 200, revision.text
    revision_result = revision.json()[0]
    assert revision_result["conflict_resolution_action"] == "NEW_REVISION"

    patched = client.patch(
        f"/companies/{company_id}/documents/{revision_result['document_id']}",
        json={
            "document_type": "CERTIFICATE",
            "label": "ISO 9001",
            "issuer": "Organismo Acreditado",
            "metadata_note": "Vigente para expediente de prueba",
        },
    )
    assert patched.status_code == 200, patched.text
    patched_payload = patched.json()
    assert patched_payload["document_type"] == "CERTIFICATE"
    assert patched_payload["label"] == "ISO 9001"

    content = client.get(f"/companies/{company_id}/documents/{revision_result['document_id']}/content")
    assert content.status_code == 200, content.text
    assert content.headers["content-type"].startswith("application/pdf")

    archived = client.patch(
        f"/companies/{company_id}/documents/{revision_result['document_id']}/archive",
        json={"archived": True},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "ARCHIVED"

    visible = client.get(f"/companies/{company_id}/documents")
    assert visible.status_code == 200, visible.text
    visible_ids = {item["id"] for item in visible.json()}
    assert revision_result["document_id"] not in visible_ids

    with_archived = client.get(f"/companies/{company_id}/documents?include_archived=true")
    assert with_archived.status_code == 200, with_archived.text
    archived_ids = {item["id"] for item in with_archived.json()}
    assert revision_result["document_id"] in archived_ids


def test_company_creation_persists_across_sessions_without_tender() -> None:
    company_id = _create_company("Persistencia SA")

    db = SessionLocal()
    try:
        company = db.get(Company, company_id)
        assert company is not None
        assert company.name == "Persistencia SA"
    finally:
        db.close()

    db = SessionLocal()
    try:
        company_again = db.get(Company, company_id)
        assert company_again is not None
        assert company_again.legal_name == "Persistencia SA SA de CV"
        assert company_again.tax_id == "AAA010101AAA"
    finally:
        db.close()


def test_import_storage_integrity_and_metadata_patch_keeps_bytes_hash() -> None:
    company_id = _create_company("Integridad Bytes")
    payload = b"archivo original de evidencia\nlinea 2\n"
    payload_sha = hashlib.sha256(payload).hexdigest()

    imported = _import_company_file(company_id, "evidencia.txt", payload)
    assert imported["status"] == "IMPORTED"
    assert imported["sha256"] == payload_sha
    assert imported["is_current"] is True

    detail = client.get(f"/companies/{company_id}/documents/{imported['document_id']}")
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["company_id"] == company_id
    assert detail_payload["original_filename"] == "evidencia.txt"
    assert detail_payload["file_size_bytes"] == len(payload)
    assert detail_payload["archived_at"] is None
    assert detail_payload["status"] == "IMPORTED"
    assert detail_payload["stored_relative_path"].startswith(f"companies/{company_id}/originals/")
    assert ".." not in detail_payload["stored_relative_path"]

    original_bytes = _stored_file_bytes(detail_payload["stored_relative_path"])
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    assert original_bytes == payload
    assert original_sha == payload_sha

    patched = client.patch(
        f"/companies/{company_id}/documents/{imported['document_id']}",
        json={
            "document_type": "CERTIFICATION",
            "label": "ISO 9001",
            "issuer": "Casa Certificadora",
            "issue_date": "2026-01-01",
            "expiration_date": "2027-01-01",
            "metadata_note": "Nota manual",
        },
    )
    assert patched.status_code == 200, patched.text
    patched_payload = patched.json()
    assert patched_payload["document_type"] == "CERTIFICATION"
    assert patched_payload["issuer"] == "Casa Certificadora"
    assert patched_payload["issue_date"] == "2026-01-01"
    assert patched_payload["expiration_date"] == "2027-01-01"

    current_bytes = _stored_file_bytes(detail_payload["stored_relative_path"])
    current_sha = hashlib.sha256(current_bytes).hexdigest()
    assert current_bytes == original_bytes
    assert current_sha == original_sha


def test_duplicate_does_not_create_extra_row_in_same_company() -> None:
    company_id = _create_company("Duplicados SA")
    payload = b"mismo archivo\n"

    first = _import_company_file(company_id, "duplicado.txt", payload)
    assert first["status"] == "IMPORTED"

    duplicate = _import_company_file(company_id, "duplicado.txt", payload)
    assert duplicate["status"] == "DUPLICATE"

    db = SessionLocal()
    try:
        rows = db.query(CompanyDocument).filter(CompanyDocument.company_id == company_id).all()
        assert len(rows) == 1
    finally:
        db.close()


def test_name_conflict_without_action_does_not_create_revision() -> None:
    company_id = _create_company("Conflicto Sin Accion")

    first = _import_company_file(company_id, "certificate.pdf", b"%PDF-1.4\nA\n%%EOF\n", "application/pdf")
    assert first["status"] == "IMPORTED"

    conflict = _import_company_file(company_id, "certificate.pdf", b"%PDF-1.4\nB\n%%EOF\n", "application/pdf")
    assert conflict["status"] == "NAME_CONFLICT"

    db = SessionLocal()
    try:
        rows = db.query(CompanyDocument).filter(CompanyDocument.company_id == company_id).all()
        assert len(rows) == 1
        assert rows[0].revision_of_document_id is None
        assert rows[0].revision_number == 1
        assert rows[0].is_current is True
    finally:
        db.close()


def test_new_revision_keeps_old_row_bytes_and_lineage_and_rejects_invalid_parents() -> None:
    company_a = _create_company("Revisiones A")
    company_b = _create_company("Revisiones B")

    base_payload = b"%PDF-1.4\nbase\n%%EOF\n"
    second_payload = b"%PDF-1.4\nsecond\n%%EOF\n"

    base = _import_company_file(company_a, "revision.pdf", base_payload, "application/pdf")
    base_id = base["document_id"]

    base_detail = client.get(f"/companies/{company_a}/documents/{base_id}")
    assert base_detail.status_code == 200, base_detail.text
    base_path = base_detail.json()["stored_relative_path"]
    base_bytes_before = _stored_file_bytes(base_path)

    revision_response = client.post(
        f"/companies/{company_a}/documents/import",
        files=[("files", ("revision.pdf", second_payload, "application/pdf"))],
        data={
            "source_relative_paths": "empresa/revision.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": base_id,
        },
    )
    assert revision_response.status_code == 200, revision_response.text
    revision = revision_response.json()[0]
    assert revision["status"] == "IMPORTED"
    assert revision["revision_of_document_id"] == base_id
    assert revision["is_current"] is True

    documents = client.get(f"/companies/{company_a}/documents?include_archived=true")
    assert documents.status_code == 200, documents.text
    by_id = {item["id"]: item for item in documents.json()}
    assert by_id[base_id]["is_current"] is False
    assert by_id[revision["document_id"]]["is_current"] is True
    assert by_id[revision["document_id"]]["company_id"] == company_a
    assert by_id[revision["document_id"]]["sha256"] != by_id[base_id]["sha256"]

    base_bytes_after = _stored_file_bytes(base_path)
    assert base_bytes_after == base_bytes_before

    other_company_doc = _import_company_file(company_b, "revision.pdf", b"%PDF-1.4\nother\n%%EOF\n", "application/pdf")
    cross_parent = client.post(
        f"/companies/{company_a}/documents/import",
        files=[("files", ("revision.pdf", b"%PDF-1.4\nthird\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "empresa/revision.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": other_company_doc["document_id"],
        },
    )
    assert cross_parent.status_code == 400, cross_parent.text

    missing_parent = client.post(
        f"/companies/{company_a}/documents/import",
        files=[("files", ("revision.pdf", b"%PDF-1.4\nthird\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "empresa/revision.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert missing_parent.status_code == 404, missing_parent.text


def test_cross_company_access_is_blocked_for_detail_patch_archive_content_and_revision() -> None:
    company_a = _create_company("Control A")
    company_b = _create_company("Control B")

    document_a = _import_company_file(company_a, "a.pdf", b"%PDF-1.4\nA\n%%EOF\n", "application/pdf")
    document_a_id = document_a["document_id"]
    _import_company_file(company_b, "a.pdf", b"%PDF-1.4\nB-base\n%%EOF\n", "application/pdf")

    detail_via_other = client.get(f"/companies/{company_b}/documents/{document_a_id}")
    assert detail_via_other.status_code == 404, detail_via_other.text

    patch_via_other = client.patch(
        f"/companies/{company_b}/documents/{document_a_id}",
        json={"label": "forbidden"},
    )
    assert patch_via_other.status_code == 404, patch_via_other.text

    archive_via_other = client.patch(
        f"/companies/{company_b}/documents/{document_a_id}/archive",
        json={"archived": True},
    )
    assert archive_via_other.status_code == 404, archive_via_other.text

    content_via_other = client.get(f"/companies/{company_b}/documents/{document_a_id}/content")
    assert content_via_other.status_code == 404, content_via_other.text

    cross_revision = client.post(
        f"/companies/{company_b}/documents/import",
        files=[("files", ("a.pdf", b"%PDF-1.4\nB-new\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "empresa/a.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": document_a_id,
        },
    )
    assert cross_revision.status_code == 400, cross_revision.text


def test_archive_and_restore_preserve_file_and_hash() -> None:
    company_id = _create_company("Archivo y Restauracion")
    payload = b"%PDF-1.4\narchive\n%%EOF\n"
    imported = _import_company_file(company_id, "archive.pdf", payload, "application/pdf")
    document_id = imported["document_id"]

    detail = client.get(f"/companies/{company_id}/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    stored_relative_path = detail.json()["stored_relative_path"]
    initial_sha = detail.json()["sha256"]
    initial_bytes = _stored_file_bytes(stored_relative_path)

    archived = client.patch(f"/companies/{company_id}/documents/{document_id}/archive", json={"archived": True})
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "ARCHIVED"

    active_list = client.get(f"/companies/{company_id}/documents")
    assert active_list.status_code == 200, active_list.text
    assert document_id not in {item["id"] for item in active_list.json()}

    with_archived = client.get(f"/companies/{company_id}/documents?include_archived=true")
    assert with_archived.status_code == 200, with_archived.text
    archived_record = next(item for item in with_archived.json() if item["id"] == document_id)
    assert archived_record["archived_at"] is not None

    restored = client.patch(f"/companies/{company_id}/documents/{document_id}/archive", json={"archived": False})
    assert restored.status_code == 200, restored.text
    restored_payload = restored.json()
    assert restored_payload["status"] == "IMPORTED"
    assert restored_payload["archived_at"] is None

    final_bytes = _stored_file_bytes(stored_relative_path)
    final_sha = hashlib.sha256(final_bytes).hexdigest()
    assert final_bytes == initial_bytes
    assert final_sha == initial_sha


def test_same_hash_can_exist_in_different_companies() -> None:
    payload = b"shared hash across companies\n"
    sha = hashlib.sha256(payload).hexdigest()
    company_a = _create_company("Hash A")
    company_b = _create_company("Hash B")

    first = _import_company_file(company_a, "shared.txt", payload)
    second = _import_company_file(company_b, "shared.txt", payload)

    assert first["status"] == "IMPORTED"
    assert second["status"] == "IMPORTED"
    assert first["sha256"] == sha
    assert second["sha256"] == sha


def test_get_endpoints_are_read_only_for_company_state() -> None:
    company_id = _create_company("Read Only Co")
    imported = _import_company_file(company_id, "readonly.pdf", b"%PDF-1.4\nreadonly\n%%EOF\n", "application/pdf")
    document_id = imported["document_id"]

    before_company = client.get(f"/companies/{company_id}")
    before_document = client.get(f"/companies/{company_id}/documents/{document_id}")
    assert before_company.status_code == 200
    assert before_document.status_code == 200

    for _ in range(3):
        assert client.get("/companies").status_code == 200
        assert client.get(f"/companies/{company_id}").status_code == 200
        assert client.get(f"/companies/{company_id}/documents").status_code == 200
        assert client.get(f"/companies/{company_id}/documents/{document_id}").status_code == 200
        assert client.get(f"/companies/{company_id}/documents/{document_id}/content").status_code == 200

    after_company = client.get(f"/companies/{company_id}")
    after_document = client.get(f"/companies/{company_id}/documents/{document_id}")
    assert after_company.status_code == 200
    assert after_document.status_code == 200

    assert before_company.json()["updated_at"] == after_company.json()["updated_at"]
    assert before_document.json()["sha256"] == after_document.json()["sha256"]
    assert before_document.json()["status"] == after_document.json()["status"]
    assert before_document.json()["is_current"] == after_document.json()["is_current"]


def test_company_import_does_not_create_tender_side_processing() -> None:
    company_id = _create_company("No Tender Pipeline")
    imported = _import_company_file(company_id, "iso-like.txt", b"ISO 9001 constancia SAT experiencia personal\n")
    assert imported["status"] == "IMPORTED"

    db = SessionLocal()
    try:
        company_doc = db.get(CompanyDocument, imported["document_id"])
        assert company_doc is not None
        assert company_doc.document_type is None
        assert company_doc.issuer is None
        assert company_doc.issue_date is None
        assert company_doc.expiration_date is None

        tender_docs = db.query(TenderDocument).all()
        assert all(doc.id != imported["document_id"] for doc in tender_docs)
    finally:
        db.close()


def test_company_import_sanitizes_filename_path_traversal() -> None:
    company_id = _create_company("Path Safety")
    payload = b"%PDF-1.4\npath\n%%EOF\n"

    response = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("../../../../outside.pdf", payload, "application/pdf"))],
        data={"source_relative_paths": "../../../../outside.pdf"},
    )
    assert response.status_code == 200, response.text
    imported = response.json()[0]
    assert imported["status"] == "IMPORTED"

    detail = client.get(f"/companies/{company_id}/documents/{imported['document_id']}")
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["stored_relative_path"].startswith(f"companies/{company_id}/originals/")
    assert ".." not in detail_payload["stored_relative_path"]


def test_superseded_revision_parent_is_rejected() -> None:
    company_id = _create_company("Superseded Parent")

    first = _import_company_file(company_id, "supersede.pdf", b"%PDF-1.4\nfirst\n%%EOF\n", "application/pdf")
    first_id = first["document_id"]

    second = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("supersede.pdf", b"%PDF-1.4\nsecond\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "empresa/supersede.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_id,
        },
    )
    assert second.status_code == 200, second.text

    rejected = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("supersede.pdf", b"%PDF-1.4\nthird\n%%EOF\n", "application/pdf"))],
        data={
            "source_relative_paths": "empresa/supersede.pdf",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first_id,
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert "Only the current revision can receive a new revision" in rejected.text
