from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import CompanyEvidence, RequirementEvidenceCandidateReview, RequirementComplianceAssessment, RequirementComplianceCheck, TenderEvent
from tests.test_evidence_matching import (
    _analyze_company_document,
    _analyze_matches,
    _create_company,
    _create_tender,
    _explicit_certification_fixture,
    _find_match,
    _find_requirement_row,
    _import_company_document,
    _manual_company_evidence,
    _seed_requirement,
)

client = TestClient(app)


def _approve_evidence(company_id: str, evidence_id: str) -> None:
    response = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": "APPROVED", "review_note": "Validada"},
    )
    assert response.status_code == 200, response.text


def _confirm_match(tender_id: str, company_id: str, match_id: str) -> None:
    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match_id}/review",
        json={"review_status": "CONFIRMED", "review_note": "Asociación confirmada"},
    )
    assert response.status_code == 200, response.text


def _analyze_compliance(tender_id: str, company_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/companies/{company_id}/analyze-compliance")
    assert response.status_code == 200, response.text
    return response.json()


def _get_compliance(tender_id: str, company_id: str, query: str = "") -> dict:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/compliance-assessments{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _find_assessment(payload: dict, requirement_id: str) -> dict:
    for row in payload["assessments"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Assessment not found")


def _find_check(row: dict, check_type: str) -> dict:
    for check in row["checks"]:
        if check["check_type"] == check_type:
            return check
    raise AssertionError(f"Check {check_type} not found")


def test_direct_verification_is_not_evaluated() -> None:
    tender_id = _create_tender("CMP direct verification")
    company_id = _create_company("CMP Direct")
    requirement_id = _seed_requirement(tender_id, "spanish.pdf", "La propuesta deberá presentarse en idioma español.")

    payload = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(payload, requirement_id)
    assert row["system_status"] == "NOT_EVALUATED"
    assert "DIRECT_VERIFICATION_OUTSIDE_COMPANY_EVIDENCE" in row["warning_codes"]


def test_no_evidence_mandatory_is_not_supported_without_human_verdict_wording() -> None:
    tender_id = _create_tender("CMP no evidence")
    company_id = _create_company("CMP No Evidence")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")

    payload = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(payload, requirement_id)
    assert row["system_status"] == "NOT_SUPPORTED"
    assert "NO_SUPPORTING_EVIDENCE" in row["warning_codes"]
    assert "cumple" not in row["assessment_summary"].lower()


def test_unconfirmed_strong_match_is_review_required() -> None:
    tender_id = _create_tender("CMP unconfirmed match")
    company_id = _create_company("CMP Unconfirmed")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _analyze_company_document(company_id, document_id)["evidence"][0]
    _approve_evidence(company_id, evidence["id"])

    match_payload = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(match_payload, requirement_id), "CERTIFICATION")
    assert match["match_strength"] == "STRONG"

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["system_status"] == "REVIEW_REQUIRED"
    assert "EVIDENCE_ASSOCIATION_NOT_CONFIRMED" in row["warning_codes"]
    assert _find_check(row, "MATCH_CONFIRMED")["check_status"] == "UNKNOWN"


def test_rejected_match_is_not_used_for_support() -> None:
    tender_id = _create_tender("CMP rejected match")
    company_id = _create_company("CMP Rejected Match")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _analyze_company_document(company_id, document_id)["evidence"][0]
    _approve_evidence(company_id, evidence["id"])

    match_payload = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(match_payload, requirement_id), "CERTIFICATION")
    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match['id']}/review",
        json={"review_status": "REJECTED", "review_note": "No corresponde"},
    )
    assert response.status_code == 200, response.text

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["system_status"] == "NOT_SUPPORTED"


def test_iso_exact_can_be_supported_when_all_material_checks_pass() -> None:
    tender_id = _create_tender("CMP iso exact")
    company_id = _create_company("CMP ISO Exact")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001:2015 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP ISO Exact SA de CV",
        canonical_statement="La empresa acredita certificación ISO 9001:2015 vigente.",
        source_excerpt="Certificación ISO 9001:2015 vigente.",
        issuer="Organismo certificador",
        reference_number="ISO-9001-2015-A1",
    )
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["system_status"] == "SUPPORTED"
    assert _find_check(row, "SPECIFIC_STANDARD")["check_status"] == "PASS"
    assert _find_check(row, "STANDARD_EDITION")["check_status"] == "PASS"


def test_iso_edition_unknown_stays_partially_supported_or_review_required() -> None:
    tender_id = _create_tender("CMP iso edition unknown")
    company_id = _create_company("CMP ISO Edition Unknown")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001:2015 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _analyze_company_document(company_id, document_id)["evidence"][0]
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["system_status"] in {"PARTIALLY_SUPPORTED", "REVIEW_REQUIRED"}
    assert _find_check(row, "SPECIFIC_STANDARD")["check_status"] == "PASS"
    assert _find_check(row, "STANDARD_EDITION")["check_status"] == "UNKNOWN"


def test_wrong_iso_is_not_supported() -> None:
    tender_id = _create_tender("CMP wrong iso")
    company_id = _create_company("CMP Wrong ISO")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Wrong ISO SA de CV",
        canonical_statement="La empresa acredita certificación ISO 45001 vigente.",
        source_excerpt="Certificación ISO 45001 vigente.",
    )
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    row = _find_requirement_row(matches, requirement_id)
    assert row["candidate_count"] == 0

    manual = client.post(
        f"/tenders/{tender_id}/companies/{company_id}/requirements/{requirement_id}/evidence-match-candidates/manual",
        json={"company_evidence_id": evidence["id"], "rationale": "Prueba control wrong ISO"},
    )
    assert manual.status_code == 200, manual.text

    compliance = _analyze_compliance(tender_id, company_id)
    assessment = _find_assessment(compliance, requirement_id)
    assert assessment["system_status"] == "NOT_SUPPORTED"
    assert _find_check(assessment, "SPECIFIC_STANDARD")["check_status"] == "FAIL"


def test_conditional_requirement_keeps_condition_unresolved_context() -> None:
    tender_id = _create_tender("CMP conditional")
    company_id = _create_company("CMP Conditional")
    requirement_id = _seed_requirement(
        tender_id,
        "conditional.pdf",
        "En caso de propuesta conjunta, cada integrante deberá presentar constancia fiscal vigente.",
    )
    document_id = _import_company_document(company_id, "fiscal.txt", _explicit_certification_fixture())
    _analyze_company_document(company_id, document_id)
    _analyze_matches(tender_id, company_id)

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["applicability_context"] == "CONDITION_UNRESOLVED"


def test_stale_match_review_forces_review_required() -> None:
    tender_id = _create_tender("CMP stale match")
    company_id = _create_company("CMP Stale Match")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _analyze_company_document(company_id, document_id)["evidence"][0]
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    with SessionLocal() as db:
        review = db.execute(
            select(RequirementEvidenceCandidateReview).where(RequirementEvidenceCandidateReview.match_id == match["id"])
        ).scalar_one()
        review.reviewed_fingerprint = "0" * 64
        db.commit()

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    assert row["system_status"] == "REVIEW_REQUIRED"
    assert "STALE_MATCH_REVIEW" in row["warning_codes"]


def test_validity_check_uses_submission_reference_date_when_explicit() -> None:
    tender_id = _create_tender("CMP validity")
    company_id = _create_company("CMP Validity")
    requirement_id = _seed_requirement(
        tender_id,
        "validity.pdf",
        "El participante deberá presentar certificado ISO 9001 vigente a la fecha de presentación de la propuesta.",
    )
    document_id = _import_company_document(company_id, "iso.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Validity SA de CV",
        canonical_statement="La empresa acredita certificación ISO 9001:2015 vigente.",
        source_excerpt="Certificación ISO 9001:2015 vigente.",
    )

    with SessionLocal() as db:
        row = db.get(CompanyEvidence, evidence["id"])
        assert row is not None
        row.valid_until = date(2027, 12, 31)
        db.commit()

    _approve_evidence(company_id, evidence["id"])

    with SessionLocal() as db:
        db.add(
            TenderEvent(
                tender_id=tender_id,
                semantic_key=f"submission-{tender_id}",
                event_type="PROPOSAL_SUBMISSION_DEADLINE",
                title="Fecha límite",
                event_date=date(2027, 6, 1),
                review_status="CONFIRMED",
            )
        )
        db.commit()

    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    compliance = _analyze_compliance(tender_id, company_id)
    row = _find_assessment(compliance, requirement_id)
    validity = _find_check(row, "VALIDITY_DATE")
    assert validity["check_status"] == "PASS"


def test_get_is_read_only_and_reanalysis_is_idempotent() -> None:
    tender_id = _create_tender("CMP idempotent")
    company_id = _create_company("CMP Idempotent")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _analyze_company_document(company_id, document_id)["evidence"][0]
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    first = _analyze_compliance(tender_id, company_id)
    second = _analyze_compliance(tender_id, company_id)

    first_row = _find_assessment(first, requirement_id)
    second_row = _find_assessment(second, requirement_id)
    assert first_row["assessment_fingerprint"] == second_row["assessment_fingerprint"]

    with SessionLocal() as db:
        before_count = db.query(RequirementComplianceAssessment).filter(RequirementComplianceAssessment.tender_id == tender_id, RequirementComplianceAssessment.company_id == company_id).count()
        before_check_count = db.query(RequirementComplianceCheck).join(RequirementComplianceAssessment, RequirementComplianceCheck.assessment_id == RequirementComplianceAssessment.id).filter(RequirementComplianceAssessment.tender_id == tender_id, RequirementComplianceAssessment.company_id == company_id).count()

    _ = _get_compliance(tender_id, company_id)

    with SessionLocal() as db:
        after_count = db.query(RequirementComplianceAssessment).filter(RequirementComplianceAssessment.tender_id == tender_id, RequirementComplianceAssessment.company_id == company_id).count()
        after_check_count = db.query(RequirementComplianceCheck).join(RequirementComplianceAssessment, RequirementComplianceCheck.assessment_id == RequirementComplianceAssessment.id).filter(RequirementComplianceAssessment.tender_id == tender_id, RequirementComplianceAssessment.company_id == company_id).count()

    assert before_count == after_count
    assert before_check_count == after_check_count


def test_cross_company_isolation() -> None:
    tender_id = _create_tender("CMP isolation")
    company_a = _create_company("CMP Isolation A")
    company_b = _create_company("CMP Isolation B")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante deberá presentar certificado ISO 9001 vigente.")

    doc_a = _import_company_document(company_a, "iso-a.txt", _explicit_certification_fixture())
    evidence_a = _analyze_company_document(company_a, doc_a)["evidence"][0]
    _approve_evidence(company_a, evidence_a["id"])

    matches_a = _analyze_matches(tender_id, company_a)
    match_a = _find_match(_find_requirement_row(matches_a, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_a, match_a["id"])

    assessment_a = _analyze_compliance(tender_id, company_a)
    assessment_b = _analyze_compliance(tender_id, company_b)

    row_a = _find_assessment(assessment_a, requirement_id)
    row_b = _find_assessment(assessment_b, requirement_id)
    assert row_a["system_status"] in {"SUPPORTED", "PARTIALLY_SUPPORTED", "REVIEW_REQUIRED"}
    assert row_b["system_status"] == "NOT_SUPPORTED"
