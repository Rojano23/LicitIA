from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    CompanyDocument,
    CompanyEvidence,
    DocumentPage,
    NormalizedContent,
    Requirement,
    RequirementCandidate,
    RequirementCandidateEvidence,
    RequirementCandidateLink,
    RequirementEvidenceCandidateMatch,
    RequirementEvidenceCandidateReview,
    RequirementEvidenceExpectation,
    RequirementReview,
    RequirementSemantics,
    RequirementVersionLink,
    TenderChange,
    TenderDocument,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "MATCH-053",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


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


def _import_tender_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page_and_normalized(document_id: str, page_number: int, text: str) -> tuple[str, str]:
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
        db.flush()

        normalized = NormalizedContent(
            document_page_id=page.id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page.id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(normalized)

        document = db.get(TenderDocument, document_id)
        assert document is not None
        document.page_count = max(document.page_count, page_number)
        document.processing_status = "TEXT_EXTRACTION_COMPLETE"

        db.commit()
        return page.id, normalized.id
    finally:
        db.close()


def _seed_requirement_candidate(
    *,
    tender_id: str,
    document_id: str,
    page_id: str,
    normalized_content_id: str,
    source_page: int,
    text: str,
    actor_text: str | None = "El participante",
    modality_text: str | None = "debera",
) -> str:
    db = SessionLocal()
    try:
        candidate = RequirementCandidate(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"{tender_id}|{document_id}|{page_id}|{text}".encode("utf-8")).hexdigest(),
            requirement_text=text,
            actor_text=actor_text,
            modality_text=modality_text,
            source_document_id=document_id,
            source_page=source_page,
            source_excerpt=text,
            document_page_id=page_id,
            normalized_content_id=normalized_content_id,
            detection_origin="DETERMINISTIC",
            review_status="SUGGESTED",
            detector_version="mvp-04.2",
        )
        db.add(candidate)
        db.flush()
        db.add(
            RequirementCandidateEvidence(
                candidate_id=candidate.id,
                source_document_id=document_id,
                source_page=source_page,
                source_excerpt=text,
                excerpt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                document_page_id=page_id,
                normalized_content_id=normalized_content_id,
            )
        )
        db.commit()
        return candidate.id
    finally:
        db.close()


def _prepare_requirement_pipeline(tender_id: str) -> None:
    response = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert response.status_code == 200, response.text


def _seed_requirement(
    tender_id: str,
    filename: str,
    requirement_text: str,
    *,
    actor_text: str | None = "El participante",
) -> str:
    document_id = _import_tender_pdf(tender_id, filename)
    page_id, normalized_id = _seed_page_and_normalized(document_id, 1, requirement_text)
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=document_id,
        page_id=page_id,
        normalized_content_id=normalized_id,
        source_page=1,
        text=requirement_text,
        actor_text=actor_text,
    )
    _prepare_requirement_pipeline(tender_id)
    response = client.get(f"/tenders/{tender_id}/requirement-matrix")
    assert response.status_code == 200, response.text
    rows = response.json()["requirements"]
    return next(row["requirement_id"] for row in rows if requirement_text.split(".")[0] in row["canonical_text"])


def _import_company_document(company_id: str, filename: str, payload: bytes, mime_type: str = "text/plain") -> str:
    response = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", (filename, payload, mime_type))],
        data={"source_relative_paths": f"evidence/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _analyze_company_document(company_id: str, document_id: str) -> dict:
    response = client.post(f"/companies/{company_id}/documents/{document_id}/analyze-evidence")
    assert response.status_code == 200, response.text
    return response.json()


def _manual_company_evidence(
    company_id: str,
    document_id: str,
    *,
    evidence_type: str,
    subject_kind: str,
    canonical_statement: str,
    source_excerpt: str,
    subject_name: str | None = None,
    issuer: str | None = None,
    reference_number: str | None = None,
) -> dict:
    payload = {
        "evidence_type": evidence_type,
        "subject_kind": subject_kind,
        "canonical_statement": canonical_statement,
        "source_excerpt": source_excerpt,
        "source_locator": "lines:1-1|manual-entry",
    }
    if subject_name is not None:
        payload["subject_name"] = subject_name
    if issuer is not None:
        payload["issuer"] = issuer
    if reference_number is not None:
        payload["reference_number"] = reference_number
    response = client.post(f"/companies/{company_id}/documents/{document_id}/evidence/manual", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _explicit_certification_fixture() -> bytes:
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


def _analyze_matches(tender_id: str, company_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/companies/{company_id}/analyze-evidence-matches")
    assert response.status_code == 200, response.text
    return response.json()


def _get_matches(tender_id: str, company_id: str, query: str = "") -> dict:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _find_requirement_row(payload: dict, requirement_id: str) -> dict:
    for row in payload["requirements"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Requirement row not found")


def _find_match(row: dict, evidence_type: str) -> dict:
    for match in row["matches"]:
        if match["company_evidence"]["evidence_type"] == evidence_type:
            return match
    raise AssertionError("Match not found")


def test_strong_iso_certification_candidate_without_compliance_conclusion() -> None:
    tender_id = _create_tender("MATCH iso strong")
    company_id = _create_company("Match ISO Strong")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "CERTIFICATION")

    assert row["candidate_count"] == 1
    assert match["match_strength"] == "STRONG"
    assert "cumple" not in match["match_rationale"].lower()
    assert match["company_evidence"]["reference_number"] == "QMS-2026-001"


def test_wrong_certification_does_not_become_strong_for_iso_requirement() -> None:
    tender_id = _create_tender("MATCH iso wrong")
    company_id = _create_company("Match ISO Wrong")
    requirement_id = _seed_requirement(tender_id, "iso-wrong.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "safety.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="Match ISO Wrong SA de CV",
        canonical_statement="La empresa acredita una certificación de seguridad industrial.",
        source_excerpt="Certificación de seguridad industrial.",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0


def test_iso_9001_2015_requirement_matches_iso_9001_evidence_as_strong_candidate() -> None:
    tender_id = _create_tender("MATCH iso edition req")
    company_id = _create_company("Match ISO Edition Requirement")
    requirement_id = _seed_requirement(tender_id, "iso-edition.pdf", "El participante deberá presentar certificado ISO 9001:2015 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "CERTIFICATION")
    assert row["candidate_count"] == 1
    assert match["match_strength"] == "STRONG"
    assert "cumpl" not in match["match_rationale"].lower()


def test_iso_9001_requirement_matches_iso_9001_2015_evidence_as_strong_candidate() -> None:
    tender_id = _create_tender("MATCH iso edition evidence")
    company_id = _create_company("Match ISO Edition Evidence")
    requirement_id = _seed_requirement(tender_id, "iso-plain.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso2015.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="Match ISO Edition Evidence SA de CV",
        canonical_statement="La empresa acredita certificación ISO-9001:2015 emitida por organismo certificador.",
        source_excerpt="Certificación ISO-9001:2015 emitida por organismo certificador.",
        issuer="Organismo certificador",
        reference_number="ISO-2015-ACME",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "CERTIFICATION")
    assert row["candidate_count"] == 1
    assert match["match_strength"] == "STRONG"


def test_iso_45001_evidence_does_not_become_strong_for_iso_9001_requirement() -> None:
    tender_id = _create_tender("MATCH iso wrong standard")
    company_id = _create_company("Match ISO Wrong Standard")
    requirement_id = _seed_requirement(tender_id, "iso9001.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso45001.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="Match ISO Wrong Standard SA de CV",
        canonical_statement="La empresa acredita certificación ISO 45001 de seguridad y salud.",
        source_excerpt="Certificación ISO 45001 de seguridad y salud.",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0


def test_company_iso_does_not_become_strong_for_personnel_manufacturer_certification_requirement() -> None:
    tender_id = _create_tender("MATCH manufacturer personnel cert")
    company_id = _create_company("Match Manufacturer Personnel Cert")
    requirement_id = _seed_requirement(
        tender_id,
        "manufacturer-personnel.pdf",
        "El personal del participante deberá contar con certificación del fabricante para servicio y refacciones.",
    )
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "CERTIFICATION")
    assert match["match_strength"] != "STRONG"


def test_hiip_requirement_strongly_matches_generic_registration_with_same_registry_identity() -> None:
    tender_id = _create_tender("MATCH registration hiip strong")
    company_id = _create_company("Match HIIP Strong")
    requirement_id = _seed_requirement(
        tender_id,
        "hiip.pdf",
        "El interesado debera contar con certificado de registro en la HIIP vigente durante todo el procedimiento.",
    )
    document_id = _import_company_document(company_id, "hiip.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="REGISTRATION",
        subject_kind="COMPANY",
        subject_name="Match HIIP Strong SA de CV",
        canonical_statement="La empresa cuenta con registro vigente en la plataforma HIIP, numero HIIP-7788.",
        source_excerpt="Registro vigente en la plataforma HIIP, numero HIIP-7788.",
        reference_number="HIIP-7788",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "REGISTRATION")
    assert match["company_evidence"]["id"] == evidence["id"]
    assert match["match_strength"] in {"STRONG", "POSSIBLE"}
    assert "REGISTRY_IDENTITY_MISMATCH" not in match["system_warnings"]


def test_wrong_registry_identity_is_not_strong_for_hiip_requirement() -> None:
    tender_id = _create_tender("MATCH registration wrong registry")
    company_id = _create_company("Match HIIP Wrong Registry")
    requirement_id = _seed_requirement(
        tender_id,
        "hiip.pdf",
        "El interesado debera contar con certificado de registro en la HIIP vigente durante todo el procedimiento.",
    )
    document_id = _import_company_document(company_id, "registro-otro.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="REGISTRATION",
        subject_kind="COMPANY",
        subject_name="Match HIIP Wrong Registry SA de CV",
        canonical_statement="La empresa se encuentra inscrita en el Registro de Proveedores XYZ.",
        source_excerpt="Inscrita en el Registro de Proveedores XYZ.",
        reference_number="RXYZ-1122",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "REGISTRATION")
    assert match["match_strength"] != "STRONG"


def test_tax_registration_does_not_become_strong_for_hiip_requirement() -> None:
    tender_id = _create_tender("MATCH registration tax false positive")
    company_id = _create_company("Match HIIP Tax False")
    requirement_id = _seed_requirement(
        tender_id,
        "hiip.pdf",
        "El interesado debera contar con certificado de registro en la HIIP vigente durante todo el procedimiento.",
    )
    document_id = _import_company_document(company_id, "rfc.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="TAX_REGISTRATION",
        subject_kind="COMPANY",
        subject_name="Match HIIP Tax False SA de CV",
        canonical_statement="La empresa esta registrada con RFC MHF260101AB1.",
        source_excerpt="RFC MHF260101AB1.",
        reference_number="MHF260101AB1",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0


def test_tax_registration_does_not_substitute_tax_compliance() -> None:
    tender_id = _create_tender("MATCH tax separation")
    company_id = _create_company("Match Tax Separation")
    req_registration = _seed_requirement(tender_id, "rfc.pdf", "El participante deberá estar registrado con RFC vigente.")
    req_compliance = _seed_requirement(tender_id, "opinion.pdf", "El participante deberá presentar opinión positiva de cumplimiento fiscal.")
    document_id = _import_company_document(company_id, "fiscal.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    registration_row = _find_requirement_row(payload, req_registration)
    compliance_row = _find_requirement_row(payload, req_compliance)

    assert _find_match(registration_row, "TAX_REGISTRATION")["match_strength"] == "POSSIBLE"
    assert "EXPECTED_ARTIFACT_UNSPECIFIED" in registration_row["matching_warnings"]
    assert compliance_row["candidate_count"] == 0


def test_direct_verification_requirement_returns_zero_company_evidence_candidates() -> None:
    tender_id = _create_tender("MATCH direct verification")
    company_id = _create_company("Match Direct Verification")
    requirement_id = _seed_requirement(
        tender_id,
        "spanish.pdf",
        "La propuesta deberá presentarse en idioma español.",
        actor_text="La propuesta",
    )
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0
    assert "DIRECT_VERIFICATION_NOT_COMPANY_EVIDENCE" in row["matching_warnings"]


def test_conditional_requirement_preserves_condition_without_participation_inference() -> None:
    tender_id = _create_tender("MATCH conditional")
    company_id = _create_company("Match Conditional")
    requirement_id = _seed_requirement(
        tender_id,
        "conditional.pdf",
        "En caso de propuesta conjunta, cada integrante deberá presentar constancia fiscal vigente.",
    )
    document_id = _import_company_document(company_id, "fiscal.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 1
    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert "CONDITIONAL_APPLICABILITY_NOT_EVALUATED" in row["matching_warnings"]


def test_rejected_requirement_is_excluded_from_active_matching_but_kept_historical() -> None:
    tender_id = _create_tender("MATCH rejected requirement")
    company_id = _create_company("Match Rejected Requirement")
    requirement_id = _seed_requirement(tender_id, "reject.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)
    initial = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(initial, requirement_id)
    match_id = _find_match(row, "CERTIFICATION")["id"]

    response = client.patch(
        f"/tenders/{tender_id}/requirements/{requirement_id}/review",
        json={"action": "REJECT", "review_note": "Descartar representación"},
    )
    assert response.status_code == 200, response.text

    payload = _analyze_matches(tender_id, company_id)
    assert all(row["requirement_id"] != requirement_id for row in payload["requirements"])

    historical = _get_matches(tender_id, company_id, "?include_historical=true")
    historical_row = _find_requirement_row(historical, requirement_id)
    assert historical_row["requirement_review_status"] == "REJECTED"
    assert historical_row["matches"][0]["id"] == match_id
    assert historical_row["matches"][0]["is_active"] is False


def test_rejected_evidence_is_excluded_from_active_matching() -> None:
    tender_id = _create_tender("MATCH rejected evidence")
    company_id = _create_company("Match Rejected Evidence")
    requirement_id = _seed_requirement(tender_id, "reject-ev.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence_payload = _analyze_company_document(company_id, document_id)
    evidence_id = next(row["id"] for row in evidence_payload["evidence"] if row["evidence_type"] == "CERTIFICATION")

    reject_response = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": "REJECTED", "review_note": "Interpretación inválida"},
    )
    assert reject_response.status_code == 200, reject_response.text

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0


def test_pending_evidence_can_match_but_carries_review_context() -> None:
    tender_id = _create_tender("MATCH pending evidence")
    company_id = _create_company("Match Pending Evidence")
    requirement_id = _seed_requirement(tender_id, "pending.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "CERTIFICATION")
    assert "EVIDENCE_HUMAN_REVIEW_PENDING" in match["system_warnings"]


def test_personnel_and_experience_candidates_stay_distinct() -> None:
    tender_id = _create_tender("MATCH personnel experience")
    company_id = _create_company("Match Personnel Experience")
    personnel_requirement_id = _seed_requirement(tender_id, "personal.pdf", "El participante deberá presentar curriculum y cédula profesional del personal propuesto.")
    experience_requirement_id = _seed_requirement(tender_id, "experience.pdf", "El participante deberá acreditar experiencia en servicios similares completados.")

    personnel_doc_id = _import_company_document(
        company_id,
        "cv.txt",
        (
            "Nombre: Juan Perez\n"
            "Grado: Ingeniero Mecánico\n"
            "Cédula profesional: CED-998877\n"
        ).encode("utf-8"),
    )
    _analyze_company_document(company_id, personnel_doc_id)

    experience_doc_id = _import_company_document(company_id, "exp.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        experience_doc_id,
        evidence_type="EXPERIENCE",
        subject_kind="COMPANY",
        subject_name="Match Personnel Experience SA de CV",
        canonical_statement="La empresa acredita experiencia documental en servicios similares.",
        source_excerpt="Experiencia documental en servicios similares.",
    )

    payload = _analyze_matches(tender_id, company_id)
    personnel_row = _find_requirement_row(payload, personnel_requirement_id)
    experience_row = _find_requirement_row(payload, experience_requirement_id)
    assert _find_match(personnel_row, "PERSONNEL_QUALIFICATION")["match_strength"] == "STRONG"
    assert _find_match(experience_row, "EXPERIENCE")["match_strength"] == "POSSIBLE"


def test_unspecified_registration_can_match_without_inventing_artifact() -> None:
    tender_id = _create_tender("MATCH unspecified registration")
    company_id = _create_company("Match HIIP")
    requirement_id = _seed_requirement(tender_id, "hiip.pdf", "El licitante deberá estar registrado en el padrón HIIP.")
    document_id = _import_company_document(company_id, "hiip.txt", b"Documento base\n")
    _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="REGISTRATION",
        subject_kind="COMPANY",
        subject_name="Match HIIP SA de CV",
        canonical_statement="La empresa acredita registro vigente en el padrón HIIP.",
        source_excerpt="Registro vigente en el padrón HIIP.",
        reference_number="HIIP-7788",
    )

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    match = _find_match(row, "REGISTRATION")
    assert match["match_strength"] == "POSSIBLE"
    assert "EXPECTED_ARTIFACT_UNSPECIFIED" in row["matching_warnings"]


def test_cross_company_and_cross_tender_manual_association_are_blocked() -> None:
    tender_a = _create_tender("MATCH cross tender A")
    tender_b = _create_tender("MATCH cross tender B")
    company_a = _create_company("Match Cross A")
    company_b = _create_company("Match Cross B")
    requirement_a = _seed_requirement(tender_a, "cross-a.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    requirement_b = _seed_requirement(tender_b, "cross-b.pdf", "El participante deberá presentar constancia fiscal vigente.")
    document_a = _import_company_document(company_a, "a.txt", _explicit_certification_fixture())
    document_b = _import_company_document(company_b, "b.txt", _explicit_certification_fixture())
    evidence_a = next(row for row in _analyze_company_document(company_a, document_a)["evidence"] if row["evidence_type"] == "CERTIFICATION")
    evidence_b = next(row for row in _analyze_company_document(company_b, document_b)["evidence"] if row["evidence_type"] == "CERTIFICATION")

    wrong_company = client.post(
        f"/tenders/{tender_a}/companies/{company_a}/requirements/{requirement_a}/evidence-match-candidates/manual",
        json={"company_evidence_id": evidence_b["id"], "rationale": "forbidden"},
    )
    assert wrong_company.status_code == 404, wrong_company.text

    wrong_tender = client.post(
        f"/tenders/{tender_a}/companies/{company_a}/requirements/{requirement_b}/evidence-match-candidates/manual",
        json={"company_evidence_id": evidence_a["id"], "rationale": "forbidden"},
    )
    assert wrong_tender.status_code == 404, wrong_tender.text


def test_manual_match_and_review_rejection_are_traceable() -> None:
    tender_id = _create_tender("MATCH manual trace")
    company_id = _create_company("Match Manual Trace")
    requirement_id = _seed_requirement(tender_id, "da2.pdf", "El participante deberá presentar el formato DA-2 firmado.")
    document_id = _import_company_document(company_id, "manual.txt", b"Documento manual\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="OTHER",
        subject_kind="COMPANY",
        subject_name="Match Manual Trace SA de CV",
        canonical_statement="La empresa cuenta con un formato interno relacionado con DA-2.",
        source_excerpt="Formato interno relacionado con DA-2.",
    )

    initial = _analyze_matches(tender_id, company_id)
    assert _find_requirement_row(initial, requirement_id)["candidate_count"] == 0

    manual = client.post(
        f"/tenders/{tender_id}/companies/{company_id}/requirements/{requirement_id}/evidence-match-candidates/manual",
        json={"company_evidence_id": evidence["id"], "rationale": "Asociación manual por revisión documental."},
    )
    assert manual.status_code == 200, manual.text
    row = _find_requirement_row(manual.json(), requirement_id)
    match = row["matches"][0]
    assert match["origin"] == "HUMAN"
    assert match["review"]["review_status"] == "CONFIRMED"

    reject_without_note = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match['id']}/review",
        json={"review_status": "REJECTED"},
    )
    assert reject_without_note.status_code == 400, reject_without_note.text

    rejected = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match['id']}/review",
        json={"review_status": "REJECTED", "review_note": "Asociación descartada por el usuario."},
    )
    assert rejected.status_code == 200, rejected.text
    rejected_match = _find_requirement_row(rejected.json(), requirement_id)["matches"][0]
    assert rejected_match["review"]["review_status"] == "REJECTED"


def test_match_analysis_is_idempotent_and_get_is_read_only() -> None:
    tender_id = _create_tender("MATCH idempotent")
    company_id = _create_company("Match Idempotent")
    requirement_id = _seed_requirement(tender_id, "idempotent.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)

    first = _analyze_matches(tender_id, company_id)
    second = _analyze_matches(tender_id, company_id)
    first_match = _find_requirement_row(first, requirement_id)["matches"][0]
    second_match = _find_requirement_row(second, requirement_id)["matches"][0]
    assert first_match["id"] == second_match["id"]
    assert first_match["match_fingerprint"] == second_match["match_fingerprint"]

    db = SessionLocal()
    try:
        before = db.execute(select(func.count(RequirementEvidenceCandidateMatch.id)).where(RequirementEvidenceCandidateMatch.tender_id == tender_id)).scalar_one()
        review_before = db.execute(select(func.count(RequirementEvidenceCandidateReview.id)).join(RequirementEvidenceCandidateMatch, RequirementEvidenceCandidateMatch.id == RequirementEvidenceCandidateReview.match_id).where(RequirementEvidenceCandidateMatch.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    _get_matches(tender_id, company_id)
    _get_matches(tender_id, company_id)

    db = SessionLocal()
    try:
        after = db.execute(select(func.count(RequirementEvidenceCandidateMatch.id)).where(RequirementEvidenceCandidateMatch.tender_id == tender_id)).scalar_one()
        review_after = db.execute(select(func.count(RequirementEvidenceCandidateReview.id)).join(RequirementEvidenceCandidateMatch, RequirementEvidenceCandidateMatch.id == RequirementEvidenceCandidateReview.match_id).where(RequirementEvidenceCandidateMatch.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    assert before == after
    assert review_before == review_after


def test_requirement_and_evidence_changes_mark_confirmed_match_stale() -> None:
    tender_id = _create_tender("MATCH stale")
    company_id = _create_company("Match Stale")
    requirement_id = _seed_requirement(tender_id, "stale.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence_payload = _analyze_company_document(company_id, document_id)
    evidence_id = next(row["id"] for row in evidence_payload["evidence"] if row["evidence_type"] == "CERTIFICATION")

    analyzed = _analyze_matches(tender_id, company_id)
    match_id = _find_requirement_row(analyzed, requirement_id)["matches"][0]["id"]
    confirm = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match_id}/review",
        json={"review_status": "CONFIRMED", "review_note": "Pertinente"},
    )
    assert confirm.status_code == 200, confirm.text

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        evidence = db.get(CompanyEvidence, evidence_id)
        assert requirement is not None
        assert evidence is not None
        requirement.canonical_text = "El participante deberá presentar certificación ISO 9001:2015 vigente."
        evidence.canonical_statement = "La empresa acredita una certificación ISO 9001:2015 documental."
        evidence.semantic_fingerprint = hashlib.sha256(b"changed-evidence-fingerprint").hexdigest()
        db.commit()
    finally:
        db.close()

    payload = _analyze_matches(tender_id, company_id)
    stale_match = _find_requirement_row(payload, requirement_id)["matches"][0]
    assert stale_match["review"]["review_status"] == "CONFIRMED"
    assert stale_match["review_freshness"] == "STALE"


def test_requirement_successor_and_document_revision_do_not_inherit_confirmation() -> None:
    tender_id = _create_tender("MATCH successors")
    company_id = _create_company("Match Successors")
    target_doc_id = _import_tender_pdf(tender_id, "target.pdf")
    source_doc_id = _import_tender_pdf(tender_id, "source.pdf")

    page_old, norm_old = _seed_page_and_normalized(target_doc_id, 1, "Numeral 4.2: el participante deberá estar registrado con RFC vigente.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=page_old,
        normalized_content_id=norm_old,
        source_page=1,
        text="Numeral 4.2: el participante deberá estar registrado con RFC vigente.",
    )

    page_new, norm_new = _seed_page_and_normalized(source_doc_id, 1, "Numeral 4.2: el participante deberá presentar constancia fiscal vigente.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=source_doc_id,
        page_id=page_new,
        normalized_content_id=norm_new,
        source_page=1,
        text="Numeral 4.2: el participante deberá presentar constancia fiscal vigente.",
    )
    _prepare_requirement_pipeline(tender_id)

    matrix = client.get(f"/tenders/{tender_id}/requirement-matrix")
    assert matrix.status_code == 200, matrix.text
    old_requirement_id = next(item["requirement_id"] for item in matrix.json()["requirements"] if "registrado con RFC" in item["canonical_text"])
    new_requirement_id = next(item["requirement_id"] for item in matrix.json()["requirements"] if "constancia fiscal" in item["canonical_text"])

    company_doc_v1 = _import_company_document(company_id, "fiscal.txt", _explicit_certification_fixture())
    evidence_v1 = _analyze_company_document(company_id, company_doc_v1)
    tax_v1 = next(row for row in evidence_v1["evidence"] if row["evidence_type"] == "TAX_REGISTRATION")

    initial = _analyze_matches(tender_id, company_id)
    initial_match_id = _find_requirement_row(initial, old_requirement_id)["matches"][0]["id"]
    confirm_initial = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{initial_match_id}/review",
        json={"review_status": "CONFIRMED", "review_note": "Pertinente para la versión inicial."},
    )
    assert confirm_initial.status_code == 200, confirm_initial.text

    db = SessionLocal()
    try:
        semantic = "|".join([tender_id, source_doc_id, target_doc_id, "numeral 4.2", "registrado con RFC", "constancia fiscal", "MODIFIES"])
        db.add(
            TenderChange(
                tender_id=tender_id,
                semantic_key=hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
                change_type="MODIFIES",
                target_reference_key="ANEXO:D",
                target_document_id=target_doc_id,
                target_candidate_document_ids=target_doc_id,
                target_locator_text="numeral 4.2",
                before_text="registrado con RFC",
                after_text="constancia fiscal vigente",
                source_document_id=source_doc_id,
                source_page=1,
                source_excerpt="Se modifica numeral 4.2",
                review_status="CONFIRMED",
                detection_origin="DETERMINISTIC",
                detector_version="mvp-03.3",
            )
        )
        db.commit()
    finally:
        db.close()

    versions = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert versions.status_code == 200, versions.text

    revision_response = client.post(
        f"/companies/{company_id}/documents/import",
        files=[("files", ("fiscal.txt", b"Raz\xc3\xb3n social: Match Successors SA DE CV\nRFC: MSS010101AA2\n", "text/plain"))],
        data={
            "source_relative_paths": "evidence/fiscal.txt",
            "conflict_action": "NEW_REVISION",
            "revision_of_document_id": company_doc_v1,
        },
    )
    assert revision_response.status_code == 200, revision_response.text
    company_doc_v2 = revision_response.json()[0]["document_id"]
    evidence_v2 = _analyze_company_document(company_id, company_doc_v2)
    tax_v2 = next(row for row in evidence_v2["evidence"] if row["evidence_type"] == "TAX_REGISTRATION")

    payload = _analyze_matches(tender_id, company_id)
    current_row = _find_requirement_row(payload, new_requirement_id)
    current_match = _find_match(current_row, "TAX_REGISTRATION")
    assert current_match["company_evidence_id"] == tax_v2["id"]
    assert current_match["review"] is None
    assert current_match["review_freshness"] == "NOT_REVIEWED"

    historical = _get_matches(tender_id, company_id, "?include_historical=true")
    old_row = _find_requirement_row(historical, old_requirement_id)
    old_match = next(match for match in old_row["matches"] if match["company_evidence_id"] == tax_v1["id"])
    assert old_match["review"]["review_status"] == "CONFIRMED"
    assert old_match["is_active"] is False


def test_filename_and_metadata_do_not_create_certification_matches() -> None:
    tender_id = _create_tender("MATCH traps")
    company_id = _create_company("Match Traps")
    requirement_id = _seed_requirement(tender_id, "trap.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")

    filename_doc_id = _import_company_document(company_id, "ISO9001_CERTIFICATE.txt", b"hello world\n", "text/plain")
    metadata_doc_id = _import_company_document(company_id, "neutral.txt", b"hola\n")
    update = client.patch(
        f"/companies/{company_id}/documents/{metadata_doc_id}",
        json={
            "document_type": "ISO",
            "label": "ISO9001",
            "issuer": "Instituto de Calidad Industrial",
            "metadata_note": "Documento marcado como ISO9001",
        },
    )
    assert update.status_code == 200, update.text

    _manual_company_evidence(
        company_id,
        metadata_doc_id,
        evidence_type="OTHER",
        subject_kind="COMPANY",
        subject_name="Match Traps SA de CV",
        canonical_statement="La empresa adjunta un documento genérico sin afirmación de certificación.",
        source_excerpt="Documento genérico sin certificación.",
    )
    _analyze_company_document(company_id, filename_doc_id)

    payload = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(payload, requirement_id)
    assert row["candidate_count"] == 0


def test_match_review_overlay_does_not_mutate_requirement_or_company_evidence_sources() -> None:
    tender_id = _create_tender("MATCH immutability")
    company_id = _create_company("Match Immutability")
    requirement_id = _seed_requirement(tender_id, "immutability.pdf", "El participante deberá presentar certificación ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)
    analyzed = _analyze_matches(tender_id, company_id)
    match_id = _find_requirement_row(analyzed, requirement_id)["matches"][0]["id"]

    db = SessionLocal()
    try:
        snapshot_before = {
            "requirement_count": db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one(),
            "requirement_review_count": db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one(),
            "semantics_count": db.execute(select(func.count(RequirementSemantics.id)).join(Requirement, Requirement.id == RequirementSemantics.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "expectation_count": db.execute(select(func.count(RequirementEvidenceExpectation.id)).join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "version_link_count": db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one(),
            "candidate_count": db.execute(select(func.count(RequirementCandidate.id)).where(RequirementCandidate.tender_id == tender_id)).scalar_one(),
            "candidate_link_count": db.execute(select(func.count(RequirementCandidateLink.id)).join(Requirement, Requirement.id == RequirementCandidateLink.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "company_document_count": db.execute(select(func.count(CompanyDocument.id)).where(CompanyDocument.company_id == company_id)).scalar_one(),
            "company_evidence_count": db.execute(select(func.count(CompanyEvidence.id)).where(CompanyEvidence.company_id == company_id)).scalar_one(),
        }
    finally:
        db.close()

    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match_id}/review",
        json={"review_status": "NEEDS_REVIEW", "review_note": "Verificar asociación."},
    )
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        snapshot_after = {
            "requirement_count": db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one(),
            "requirement_review_count": db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one(),
            "semantics_count": db.execute(select(func.count(RequirementSemantics.id)).join(Requirement, Requirement.id == RequirementSemantics.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "expectation_count": db.execute(select(func.count(RequirementEvidenceExpectation.id)).join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "version_link_count": db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one(),
            "candidate_count": db.execute(select(func.count(RequirementCandidate.id)).where(RequirementCandidate.tender_id == tender_id)).scalar_one(),
            "candidate_link_count": db.execute(select(func.count(RequirementCandidateLink.id)).join(Requirement, Requirement.id == RequirementCandidateLink.requirement_id).where(Requirement.tender_id == tender_id)).scalar_one(),
            "company_document_count": db.execute(select(func.count(CompanyDocument.id)).where(CompanyDocument.company_id == company_id)).scalar_one(),
            "company_evidence_count": db.execute(select(func.count(CompanyEvidence.id)).where(CompanyEvidence.company_id == company_id)).scalar_one(),
        }
    finally:
        db.close()

    assert snapshot_after == snapshot_before