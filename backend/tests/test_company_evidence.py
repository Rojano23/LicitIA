import hashlib

import fitz
from fastapi.testclient import TestClient

from app.company_evidence import analyze_company_document_evidence
from app.database import SessionLocal
from app.main import app
from app.models import CompanyEvidence, CompanyEvidenceReview

client = TestClient(app)


def _create_company(name: str) -> str:
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


def _make_pdf(*pages: str) -> bytes:
    document = fitz.open()
    for page_text in pages:
        page = document.new_page()
        page.insert_text((72, 72), page_text)
    try:
        return document.tobytes()
    finally:
        document.close()


def _import_document(company_id: str, filename: str, payload: bytes, mime_type: str = "text/plain") -> dict:
    response = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", (filename, payload, mime_type))],
        data={"source_relative_paths": f"evidence/{filename}"},
    )
    assert response.status_code == 200, response.text
    result = response.json()[0]
    assert result["status"] == "IMPORTED"
    return result


def _analyze(company_id: str, document_id: str) -> dict:
    response = client.post(f"/companies/{company_id}/documents/{document_id}/analyze-evidence")
    assert response.status_code == 200, response.text
    return response.json()


def _find_evidence(rows: list[dict], evidence_type: str, statement_fragment: str | None = None) -> dict:
    for row in rows:
        if row["evidence_type"] != evidence_type:
            continue
        if statement_fragment and statement_fragment not in row["canonical_statement"]:
            continue
        return row
    raise AssertionError(f"Evidence {evidence_type} not found")


def _explicit_txt_fixture() -> bytes:
    return (
        "ROGIN CONSTRUCTORA, S.A. DE C.V.\n\n"
        "La empresa ROGIN CONSTRUCTORA, S.A. DE C.V. se encuentra registrada\n"
        "con RFC ROG801230D54.\n\n"
        "ROGIN CONSTRUCTORA, S.A. DE C.V. cuenta con certificación ISO 9001.\n\n"
        "La certificación ISO 9001 fue emitida por Instituto de Calidad Industrial.\n\n"
        "Número de certificado: QMS-2026-001.\n\n"
        "Fecha de emisión: 29/08/2026.\n\n"
        "Válido hasta: 31/12/2027.\n"
    ).encode("utf-8")


def _evidence_signature(row: dict) -> tuple[str, str, str | None, str | None, str | None, str | None]:
    return (
        row["evidence_type"],
        row["canonical_statement"],
        row.get("reference_number"),
        row.get("issuer"),
        str(row.get("issued_on")) if row.get("issued_on") is not None else None,
        str(row.get("valid_until")) if row.get("valid_until") is not None else None,
    )


def test_corporate_existence_pdf_extracts_source_backed_evidence() -> None:
    company_id = _create_company("Existencia Legal")
    payload = _make_pdf(
        "ACTA CONSTITUTIVA\nRazón social: NEXORA INDUSTRIAL, S.A. DE C.V.\n"
        "Se constituyó el 2021-03-15 mediante escritura pública.",
    )
    imported = _import_document(company_id, "acta.pdf", payload, "application/pdf")

    analyzed = _analyze(company_id, imported["document_id"])
    assert analyzed["summary"]["text_extraction_status"] == "TEXT_EXTRACTED"
    corporate = _find_evidence(analyzed["evidence"], "CORPORATE_EXISTENCE")
    assert corporate["subject_name"] == "NEXORA INDUSTRIAL, S.A. DE C.V"
    assert corporate["issued_on"] == "2021-03-15"
    assert corporate["source_page"] == 1
    assert "constituyó" in corporate["source_excerpt"]


def test_tax_registration_preserves_source_subject_and_excerpt() -> None:
    company_id = _create_company("Registro Fiscal")
    imported = _import_document(
        company_id,
        "constancia.txt",
        b"Raz\xc3\xb3n social: ROGIN CONSTRUCTORA, S.A. DE C.V.\nRFC: ROC010203AB1\n",
    )

    analyzed = _analyze(company_id, imported["document_id"])
    tax_evidence = _find_evidence(analyzed["evidence"], "TAX_REGISTRATION")
    assert tax_evidence["subject_name"] == "ROGIN CONSTRUCTORA, S.A. DE C.V"
    assert tax_evidence["reference_number"] == "ROC010203AB1"
    assert tax_evidence["source_locator"].startswith("lines:")
    assert "RFC: ROC010203AB1" in tax_evidence["source_excerpt"]


def test_certification_extracts_dates_without_compliance_conclusion() -> None:
    company_id = _create_company("Certificaciones")
    imported = _import_document(
        company_id,
        "iso-9001.txt",
        (
            "Titular: COMPAÑIA UNO SA DE CV\n"
            "Certificado No: ISO-9001-7788\n"
            "Emitido por: Casa Certificadora MX\n"
            "Fecha de emisión: 2023-06-01\n"
            "Vigente hasta: 2020-01-01\n"
            "Certificación ISO 9001\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    certification = _find_evidence(analyzed["evidence"], "CERTIFICATION")
    assert certification["subject_name"] == "COMPAÑIA UNO SA DE CV"
    assert certification["issuer"] == "Casa Certificadora MX"
    assert certification["reference_number"] == "ISO-9001-7788"
    assert certification["issued_on"] == "2023-06-01"
    assert certification["valid_until"] == "2020-01-01"
    assert certification["analysis_status"] == "DETERMINED"
    assert "EXPIRED" not in certification["canonical_statement"]


def test_personnel_document_can_yield_multiple_independent_claims() -> None:
    company_id = _create_company("Personal Tecnico")
    imported = _import_document(
        company_id,
        "cv-juan.txt",
        (
            "Nombre: Juan Perez\n"
            "Grado: Ingeniero Mecánico\n"
            "Cédula profesional: CED-998877\n"
            "Certificación: Trabajo en alturas\n"
            "Emitido por: Centro de Capacitación Industrial\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    personnel_rows = [row for row in analyzed["evidence"] if row["evidence_type"] == "PERSONNEL_QUALIFICATION"]
    assert len(personnel_rows) >= 2
    assert all(row["subject_kind"] == "PERSON" for row in personnel_rows)
    assert all(row["subject_name"] == "Juan Perez" for row in personnel_rows)
    assert any(row["reference_number"] == "CED-998877" for row in personnel_rows)


def test_experience_extracts_client_service_and_period() -> None:
    company_id = _create_company("Experiencia Industrial")
    imported = _import_document(
        company_id,
        "contrato.txt",
        (
            "Empresa: MONTAJES DEL NORTE SA DE CV\n"
            "Cliente: Refineria Costera\n"
            "Servicio: Automatización industrial y cableado\n"
            "Del 2022-01-10 al 2022-12-31\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    experience = _find_evidence(analyzed["evidence"], "EXPERIENCE")
    assert experience["subject_name"] == "MONTAJES DEL NORTE SA DE CV"
    assert experience["issuer"] == "Refineria Costera"
    assert experience["period_start"] == "2022-01-10"
    assert experience["period_end"] == "2022-12-31"


def test_negative_document_and_wrong_company_name_remain_source_faithful() -> None:
    company_id = _create_company("Company A Owner")
    imported = _import_document(
        company_id,
        "opinion.txt",
        (
            "Contribuyente: COMPANY B OWNER SA DE CV\n"
            "Opinión negativa de cumplimiento fiscal\n"
            "Emitido por: Autoridad Fiscal Local\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    adverse = _find_evidence(analyzed["evidence"], "TAX_COMPLIANCE")
    assert adverse["subject_name"] == "COMPANY B OWNER SA DE CV"
    assert "negativa" in adverse["canonical_statement"].lower()
    assert adverse["analysis_status"] == "DETERMINED"


def test_no_evidence_and_filename_trap_do_not_invent_claims() -> None:
    company_id = _create_company("Sin Evidencia")
    imported = _import_document(company_id, "ISO9001_CERTIFICATE.txt", b"hello world\ntexto generico\n")

    analyzed = _analyze(company_id, imported["document_id"])
    assert analyzed["summary"]["evidence_count"] == 0
    assert analyzed["evidence"] == []


def test_non_tax_registry_extraction_creates_generic_registration_and_preserves_tax_registration() -> None:
    company_id = _create_company("Registro No Fiscal")
    imported = _import_document(
        company_id,
        "hiip-registro.txt",
        (
            "Razon social: GOLDEN INDUSTRIAL SERVICES, S.A. DE C.V.\n"
            "RFC: GIS260101AB1\n"
            "Consta su registro vigente en la plataforma HIIP para participar en procedimientos electronicos.\n"
            "Numero de registro: HIIP-GC001-2026\n"
            "Vigente hasta: 2027-12-31\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    evidence_types = [row["evidence_type"] for row in analyzed["evidence"]]
    assert "TAX_REGISTRATION" in evidence_types
    assert "REGISTRATION" in evidence_types

    registry = next(row for row in analyzed["evidence"] if row["evidence_type"] == "REGISTRATION")
    assert "hiip" in registry["canonical_statement"].lower()
    assert registry["reference_number"] == "HIIP-GC001-2026"
    assert registry["valid_until"] == "2027-12-31"
    assert registry["source_locator"].startswith("lines:")
    assert registry["source_excerpt"]
    assert registry["review"] is None
    assert registry["review_freshness"] == "NOT_REVIEWED"


def test_registry_name_preservation_supports_non_hiip_registry() -> None:
    company_id = _create_company("Registro Proveedores Industriales")
    imported = _import_document(
        company_id,
        "padron-proveedores.txt",
        (
            "Empresa: SUMINISTROS INDUSTRIALES DEL CENTRO, S.A. DE C.V.\n"
            "Se encuentra inscrita en el Registro de Proveedores Industriales.\n"
            "Numero de registro: RPI-77881\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    registry = _find_evidence(analyzed["evidence"], "REGISTRATION")
    assert "registro de proveedores industriales" in registry["canonical_statement"].lower()
    assert registry["reference_number"] == "RPI-77881"


def test_registration_not_inferred_from_filename_or_metadata_only() -> None:
    company_id = _create_company("Trap Registro Nombre")
    imported = _import_document(
        company_id,
        "HIIP_CERTIFICATE.txt",
        b"hello world\ntexto sin hechos de registro\n",
    )
    analyzed = _analyze(company_id, imported["document_id"])
    assert all(row["evidence_type"] != "REGISTRATION" for row in analyzed["evidence"])

    patched = client.patch(
        f"/companies/{company_id}/documents/{imported['document_id']}",
        json={
            "document_type": "REGISTRATION",
            "label": "HIIP",
            "metadata_note": "Registro HIIP",
        },
    )
    assert patched.status_code == 200, patched.text

    analyzed_again = _analyze(company_id, imported["document_id"])
    assert all(row["evidence_type"] != "REGISTRATION" for row in analyzed_again["evidence"])


def test_analysis_is_idempotent_and_get_routes_are_read_only() -> None:
    company_id = _create_company("Idempotencia")
    imported = _import_document(
        company_id,
        "constancia-fiscal.txt",
        b"Raz\xc3\xb3n social: TALLERES DEL GOLFO SA DE CV\nRFC: TGO0101012A1\n",
    )

    first = _analyze(company_id, imported["document_id"])
    second = _analyze(company_id, imported["document_id"])

    first_ids = [row["id"] for row in first["evidence"]]
    second_ids = [row["id"] for row in second["evidence"]]
    assert first_ids == second_ids
    assert [row["semantic_fingerprint"] for row in first["evidence"]] == [row["semantic_fingerprint"] for row in second["evidence"]]

    before = client.get(f"/companies/{company_id}/documents/{imported['document_id']}/evidence")
    assert before.status_code == 200, before.text
    evidence_id = before.json()["evidence"][0]["id"]

    db = SessionLocal()
    try:
        row = db.get(CompanyEvidence, evidence_id)
        assert row is not None
        before_updated_at = row.updated_at
    finally:
        db.close()

    list_response = client.get(f"/companies/{company_id}/evidence")
    detail_response = client.get(f"/companies/{company_id}/documents/{imported['document_id']}/evidence")
    assert list_response.status_code == 200, list_response.text
    assert detail_response.status_code == 200, detail_response.text

    db = SessionLocal()
    try:
        row = db.get(CompanyEvidence, evidence_id)
        assert row is not None
        assert row.updated_at == before_updated_at
    finally:
        db.close()


def test_human_review_persists_on_unchanged_reanalysis_and_stale_is_detected() -> None:
    company_id = _create_company("Revision Humana")
    imported = _import_document(
        company_id,
        "cert-review.txt",
        (
            "Titular: ELECTROMECANICA DEL SUR SA DE CV\n"
            "Certificado No: EM-555\n"
            "Emitido por: Organismo Certificador\n"
            "Certificación ISO 9001\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    evidence_id = analyzed["evidence"][0]["id"]

    approved = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": "APPROVED", "review_note": "Interpretación correcta"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review"]["review_status"] == "APPROVED"
    assert approved.json()["review_freshness"] == "CURRENT"

    unchanged = _analyze(company_id, imported["document_id"])
    unchanged_row = next(row for row in unchanged["evidence"] if row["id"] == evidence_id)
    assert unchanged_row["review"]["review_status"] == "APPROVED"
    assert unchanged_row["review_freshness"] == "CURRENT"

    db = SessionLocal()
    try:
        review = db.query(CompanyEvidenceReview).filter(CompanyEvidenceReview.company_evidence_id == evidence_id).one()
        review.reviewed_fingerprint = hashlib.sha256(b"older-representation").hexdigest()
        db.commit()
    finally:
        db.close()

    stale = _analyze(company_id, imported["document_id"])
    stale_row = next(row for row in stale["evidence"] if row["id"] == evidence_id)
    assert stale_row["review"]["review_status"] == "APPROVED"
    assert stale_row["review_freshness"] == "STALE"


def test_rejection_requires_note_and_rejected_evidence_remains_persisted() -> None:
    company_id = _create_company("Rechazo")
    imported = _import_document(company_id, "rechazo.txt", b"Razon social: A\nRFC: ABC010101AB1\n")
    analyzed = _analyze(company_id, imported["document_id"])
    evidence_id = analyzed["evidence"][0]["id"]

    rejected_without_note = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": "REJECTED"},
    )
    assert rejected_without_note.status_code == 400, rejected_without_note.text

    rejected = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": "REJECTED", "review_note": "El hallazgo no corresponde al documento"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["review"]["review_status"] == "REJECTED"
    assert rejected.json()["review"]["review_note"] is not None

    listing = client.get(f"/companies/{company_id}/evidence")
    assert listing.status_code == 200, listing.text
    assert any(row["id"] == evidence_id for row in listing.json()["evidence"])


def test_new_document_revision_does_not_inherit_review_and_keeps_historical_evidence() -> None:
    company_id = _create_company("Revisiones Evidencia")
    first = _import_document(
        company_id,
        "constancia.txt",
        b"Razon social: REVISIONES DEL PACIFICO SA DE CV\nRFC: RDP010101AA1\n",
    )
    first_analysis = _analyze(company_id, first["document_id"])
    first_evidence_id = first_analysis["evidence"][0]["id"]

    approved = client.patch(
        f"/companies/{company_id}/evidence/{first_evidence_id}/review",
        json={"review_status": "APPROVED", "review_note": "Correcta"},
    )
    assert approved.status_code == 200, approved.text

    revision = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("constancia.txt", b"Razon social: REVISIONES DEL PACIFICO SA DE CV\nRFC: RDP010101AA2\n", "text/plain"))],
        data={
            "source_relative_paths": "evidence/constancia.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": first["document_id"],
        },
    )
    assert revision.status_code == 200, revision.text
    revision_document_id = revision.json()[0]["document_id"]

    second_analysis = _analyze(company_id, revision_document_id)
    second_evidence = second_analysis["evidence"][0]
    assert second_evidence["review_freshness"] == "NOT_REVIEWED"
    assert second_evidence["review"] is None

    company_evidence = client.get(f"/companies/{company_id}/evidence?include_archived_sources=true")
    assert company_evidence.status_code == 200, company_evidence.text
    payload = company_evidence.json()
    assert payload["summary"]["historical_source_count"] >= 1
    first_row = next(row for row in payload["evidence"] if row["id"] == first_evidence_id)
    assert first_row["source_document"]["is_current"] is False
    assert first_row["review"]["review_status"] == "APPROVED"


def test_cross_company_routes_are_blocked_and_same_claim_stays_independent() -> None:
    company_a = _create_company("Compania A")
    company_b = _create_company("Compania B")
    payload = (
        "Titular: MISMA CERTIFICACION SA DE CV\n"
        "Certificado No: CC-101\n"
        "Emitido por: Organismo Certificador\n"
        "Certificación ISO 9001\n"
    ).encode("utf-8")

    first = _import_document(company_a, "same-claim.txt", payload)
    second = _import_document(company_b, "same-claim.txt", payload)
    first_analysis = _analyze(company_a, first["document_id"])
    second_analysis = _analyze(company_b, second["document_id"])

    first_evidence_id = first_analysis["evidence"][0]["id"]
    second_evidence_id = second_analysis["evidence"][0]["id"]
    assert first_evidence_id != second_evidence_id

    blocked_review = client.patch(
        f"/companies/{company_b}/evidence/{first_evidence_id}/review",
        json={"review_status": "APPROVED", "review_note": "forbidden"},
    )
    assert blocked_review.status_code == 404, blocked_review.text

    blocked_analyze = client.post(f"/companies/{company_b}/documents/{first['document_id']}/analyze-evidence")
    assert blocked_analyze.status_code == 404, blocked_analyze.text

    blocked_manual = client.post(
        f"/companies/{company_b}/documents/{first['document_id']}/evidence/manual",
        json={
            "evidence_type": "OTHER",
            "subject_kind": "OTHER",
            "canonical_statement": "manual",
            "source_excerpt": "manual",
        },
    )
    assert blocked_manual.status_code == 404, blocked_manual.text


def test_manual_evidence_is_source_backed_and_owned_by_document_company() -> None:
    company_id = _create_company("Manual Evidence")
    imported = _import_document(company_id, "manual.txt", b"Documento manual\nlinea fuente\n")

    response = client.post(
        f"/companies/{company_id}/documents/{imported['document_id']}/evidence/manual",
        json={
            "evidence_type": "OTHER",
            "subject_kind": "COMPANY",
            "subject_name": "Manual Evidence SA de CV",
            "canonical_statement": "La empresa presenta una constancia manual revisada por el usuario.",
            "source_locator": "lines:1-2|manual-entry",
            "source_excerpt": "Documento manual\nlinea fuente",
            "review_note": "Agregada manualmente por validación documental.",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["origin"] == "HUMAN"
    assert payload["company_id"] == company_id
    assert payload["company_document_id"] == imported["document_id"]
    assert payload["review"]["review_status"] == "APPROVED"
    assert payload["source_excerpt"] == "Documento manual\nlinea fuente"


def test_exact_human_txt_fixture_extracts_tax_registration_and_certification() -> None:
    company_id = _create_company("Fixture Humano")
    imported = _import_document(company_id, "fixture-humano.txt", _explicit_txt_fixture())

    analyzed = _analyze(company_id, imported["document_id"])
    assert analyzed["summary"]["text_extraction_status"] == "TEXT_EXTRACTED"
    assert analyzed["summary"]["evidence_count"] == 2
    assert analyzed["summary"]["determined_count"] == 2

    tax_evidence = _find_evidence(analyzed["evidence"], "TAX_REGISTRATION")
    assert tax_evidence["subject_name"] == "ROGIN CONSTRUCTORA, S.A. DE C.V"
    assert tax_evidence["reference_number"] == "ROG801230D54"

    certification_rows = [row for row in analyzed["evidence"] if row["evidence_type"] == "CERTIFICATION"]
    assert len(certification_rows) == 1
    certification = _find_evidence(analyzed["evidence"], "CERTIFICATION")
    assert certification["subject_name"] == "ROGIN CONSTRUCTORA, S.A. DE C.V"
    assert certification["issuer"] == "Instituto de Calidad Industrial"
    assert certification["reference_number"] == "QMS-2026-001"
    assert certification["issued_on"] == "2026-08-29"
    assert certification["valid_until"] == "2027-12-31"
    assert "cumple" not in certification["canonical_statement"].lower()
    assert "QMS-2026-001" in certification["source_excerpt"]


def test_certification_enrichment_supports_accentless_multiline_text() -> None:
    company_id = _create_company("Acentos Planos")
    imported = _import_document(
        company_id,
        "cert-accentless.txt",
        (
            "rogin constructora, s.a. de c.v. cuenta con certificacion iso 9001.\n\n"
            "La certificacion ISO 9001 fue emitida por instituto de calidad industrial.\n\n"
            "numero de certificado: QMS-2026-001.\n\n"
            "fecha de emision: 29/08/2026.\n\n"
            "valido hasta: 31/12/2027.\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    certification = _find_evidence(analyzed["evidence"], "CERTIFICATION")
    assert certification["subject_name"] == "rogin constructora, s.a. de c.v"
    assert certification["issuer"] == "instituto de calidad industrial"
    assert certification["reference_number"] == "QMS-2026-001"
    assert certification["issued_on"] == "2026-08-29"
    assert certification["valid_until"] == "2027-12-31"


def test_document_metadata_does_not_create_company_evidence() -> None:
    company_id = _create_company("Metadata Trap")
    imported = _import_document(company_id, "neutral.txt", b"hello world\ntexto generico\n")

    updated = client.patch(
        f"/companies/{company_id}/documents/{imported['document_id']}",
        json={
            "document_type": "CERTIFICATION",
            "label": "ISO 9001 QMS-2026-001",
            "issuer": "Instituto de Calidad Industrial",
            "issue_date": "2026-08-29",
            "expiration_date": "2027-12-31",
            "metadata_note": "RFC ROG801230D54",
        },
    )
    assert updated.status_code == 200, updated.text

    analyzed = _analyze(company_id, imported["document_id"])
    assert analyzed["summary"]["evidence_count"] == 0
    assert analyzed["evidence"] == []


def test_negative_certification_phrase_does_not_create_certification_evidence() -> None:
    company_id = _create_company("Negacion Certificacion")
    imported = _import_document(
        company_id,
        "negative-cert.txt",
        (
            "ROGIN CONSTRUCTORA, S.A. DE C.V.\n\n"
            "Este documento no constituye una certificación ISO 9001.\n\n"
            "Número de certificado: QMS-2026-001.\n"
        ).encode("utf-8"),
    )

    analyzed = _analyze(company_id, imported["document_id"])
    assert all(row["evidence_type"] != "CERTIFICATION" for row in analyzed["evidence"])


def test_archived_document_analysis_stays_available_and_company_list_can_include_historical_sources() -> None:
    company_id = _create_company("Archivado Explicito")
    imported = _import_document(company_id, "archived-explicit.txt", _explicit_txt_fixture())

    archived = client.patch(
        f"/companies/{company_id}/documents/{imported['document_id']}/archive",
        json={"archived": True},
    )
    assert archived.status_code == 200, archived.text

    analyzed = _analyze(company_id, imported["document_id"])
    assert _find_evidence(analyzed["evidence"], "TAX_REGISTRATION")["reference_number"] == "ROG801230D54"
    assert _find_evidence(analyzed["evidence"], "CERTIFICATION")["reference_number"] == "QMS-2026-001"

    listing = client.get(f"/companies/{company_id}/evidence")
    assert listing.status_code == 200, listing.text
    assert listing.json()["summary"]["evidence_count"] == 0

    historical = client.get(f"/companies/{company_id}/evidence?include_archived_sources=true")
    assert historical.status_code == 200, historical.text
    assert historical.json()["summary"]["evidence_count"] >= 2
    assert any(row["source_document"]["archived_at"] is not None for row in historical.json()["evidence"])


def test_service_post_and_get_are_semantically_consistent_for_exact_fixture() -> None:
    company_id = _create_company("Consistencia Exacta")
    imported = _import_document(company_id, "consistency.txt", _explicit_txt_fixture())

    db = SessionLocal()
    try:
        service_payload = analyze_company_document_evidence(db, company_id, imported["document_id"])
    finally:
        db.close()

    post_payload = _analyze(company_id, imported["document_id"])
    get_response = client.get(f"/companies/{company_id}/documents/{imported['document_id']}/evidence")
    assert get_response.status_code == 200, get_response.text
    get_payload = get_response.json()

    assert service_payload["summary"]["evidence_count"] == post_payload["summary"]["evidence_count"] == get_payload["summary"]["evidence_count"]
    assert sorted(_evidence_signature(row) for row in service_payload["evidence"]) == sorted(
        _evidence_signature(row) for row in post_payload["evidence"]
    )
    assert sorted(_evidence_signature(row) for row in post_payload["evidence"]) == sorted(
        _evidence_signature(row) for row in get_payload["evidence"]
    )