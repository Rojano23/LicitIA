from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import RequirementComplianceDecision
from tests.test_compliance_evaluation import (
    _analyze_compliance,
    _approve_evidence,
    _confirm_match,
    _create_company,
    _create_tender,
    _explicit_certification_fixture,
    _find_match,
    _find_requirement_row,
    _import_company_document,
    _manual_company_evidence,
    _seed_requirement,
)
from tests.test_evidence_matching import _analyze_matches
from tests.test_requirement_versioning import (
    _analyze_changes,
    _analyze_requirement_versions,
    _confirm_change,
    _import_pdf,
    _normalize_requirements,
    _seed_page_and_normalized,
    _seed_requirement_candidate,
    _seed_requirement_from_candidate,
    _seed_change,
    _seed_event,
)

client = TestClient(app)


def _get_matrix(tender_id: str, company_id: str, query: str = "") -> dict:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/compliance-matrix{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _get_audit(tender_id: str, company_id: str, query: str = "") -> dict:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/missing-evidence-audit{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _find_row(payload: dict, requirement_id: str) -> dict:
    for row in payload["rows"]:
        if row["requirement"]["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Matrix row not found")


def test_matrix_excludes_rejected_rows_by_default() -> None:
    tender_id = _create_tender("CMP matrix rejected")
    company_id = _create_company("CMP Matrix Rejected")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    response = client.patch(
        f"/tenders/{tender_id}/requirements/{requirement_id}/review",
        json={"action": "REJECT", "review_note": "No corresponde a bases"},
    )
    assert response.status_code == 200, response.text

    payload = _get_matrix(tender_id, company_id)
    assert payload["summary"]["excluded_rejected_count"] == 1
    assert payload["rows"] == []


def test_matrix_excludes_superseded_rows_by_default() -> None:
    tender_id = _create_tender("CMP matrix superseded")
    company_id = _create_company("CMP Matrix Superseded")

    doc_a = _import_pdf(tender_id, "anexo-d-v1.pdf")
    doc_b = _import_pdf(tender_id, "anexo-d-v2.pdf")
    doc_c = _import_pdf(tender_id, "anexo-d-v3.pdf")

    p_a, n_a = _seed_page_and_normalized(doc_a, 1, "Numeral 4.2: plazo de 30 dias naturales.")
    c_a = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=doc_a,
        page_id=p_a,
        normalized_content_id=n_a,
        source_page=1,
        text="REQ_A 30 dias naturales numeral 4.2",
    )
    p_b, n_b = _seed_page_and_normalized(doc_b, 1, "Numeral 4.2: plazo de 40 dias naturales.")
    c_b = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=doc_b,
        page_id=p_b,
        normalized_content_id=n_b,
        source_page=1,
        text="REQ_B 40 dias naturales numeral 4.2",
    )
    p_c, n_c = _seed_page_and_normalized(doc_c, 1, "Numeral 4.2: plazo de 45 dias naturales.")
    c_c = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=doc_c,
        page_id=p_c,
        normalized_content_id=n_c,
        source_page=1,
        text="REQ_C 45 dias naturales numeral 4.2",
    )

    _seed_requirement_from_candidate(tender_id, c_a, "REQ_A_30", "chain-a")
    _seed_requirement_from_candidate(tender_id, c_b, "REQ_B_40", "chain-b")
    _seed_requirement_from_candidate(tender_id, c_c, "REQ_C_45", "chain-c")

    _seed_change(
        tender_id=tender_id,
        source_document_id=doc_b,
        target_document_id=doc_a,
        locator="numeral 4.2",
        before_text="REQ_A 30 dias naturales numeral 4.2",
        after_text="REQ_B 40 dias naturales numeral 4.2",
        review_status="CONFIRMED",
    )
    _seed_change(
        tender_id=tender_id,
        source_document_id=doc_c,
        target_document_id=doc_b,
        locator="numeral 4.2",
        before_text="REQ_B 40 dias naturales numeral 4.2",
        after_text="REQ_C 45 dias naturales numeral 4.2",
        review_status="CONFIRMED",
    )
    _seed_event(
        tender_id=tender_id,
        source_document_id=doc_b,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 1),
    )
    _seed_event(
        tender_id=tender_id,
        source_document_id=doc_c,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 9),
    )

    version_payload = _analyze_requirement_versions(tender_id)
    status_by_text = {row["canonical_text"]: row["effective_status"] for row in version_payload["requirements"]}
    assert status_by_text["REQ_A_30"] == "SUPERSEDED"
    assert status_by_text["REQ_B_40"] == "SUPERSEDED"
    assert status_by_text["REQ_C_45"] == "EFFECTIVE"

    payload = _get_matrix(tender_id, company_id)
    assert payload["summary"]["excluded_superseded_count"] == 2
    assert payload["summary"]["active_requirements"] == 1
    assert any("REQ_C_45" in row["requirement"]["canonical_text"] for row in payload["rows"])
    assert all("REQ_A_30" not in row["requirement"]["canonical_text"] for row in payload["rows"])
    assert all("REQ_B_40" not in row["requirement"]["canonical_text"] for row in payload["rows"])

    historical_payload = _get_matrix(tender_id, company_id, "?include_historical=true")
    historical_status = {row["requirement"]["canonical_text"]: row["requirement"]["effective_status"] for row in historical_payload["rows"]}
    assert historical_status["REQ_A_30"] == "SUPERSEDED"
    assert historical_status["REQ_B_40"] == "SUPERSEDED"
    assert historical_status["REQ_C_45"] == "EFFECTIVE"


def test_matrix_reports_missing_company_evidence_as_action_required() -> None:
    tender_id = _create_tender("CMP matrix no evidence")
    company_id = _create_company("CMP Matrix No Evidence")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    payload = _get_matrix(tender_id, company_id)
    row = _find_row(payload, requirement_id)

    assert row["operational_state"] == "ACTION_REQUIRED"
    assert any(finding["code"] == "NO_COMPANY_EVIDENCE" for finding in row["findings"])


def test_matrix_marks_direct_verification_without_false_missing_evidence() -> None:
    tender_id = _create_tender("CMP matrix direct verify")
    company_id = _create_company("CMP Matrix Direct Verify")
    requirement_id = _seed_requirement(tender_id, "spanish.pdf", "La propuesta debera presentarse en idioma espanol.")

    payload = _get_matrix(tender_id, company_id)
    row = _find_row(payload, requirement_id)

    assert row["operational_state"] == "DIRECT_VERIFICATION_PENDING"
    assert any(finding["code"] == "DIRECT_VERIFICATION_PENDING" for finding in row["findings"])
    assert all(finding["code"] != "NO_COMPANY_EVIDENCE" for finding in row["findings"])


def test_matrix_reports_pending_match_review() -> None:
    tender_id = _create_tender("CMP matrix pending match")
    company_id = _create_company("CMP Matrix Pending Match")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", _explicit_certification_fixture())
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Matrix Pending Match SA de CV",
        canonical_statement="La empresa acredita certificacion ISO 9001 vigente.",
        source_excerpt="Certificacion ISO 9001 vigente.",
    )
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match_row = _find_requirement_row(matches, requirement_id)
    match = _find_match(match_row, "CERTIFICATION")
    assert match["review"] is None or match["review"]["review_status"] == "PENDING"

    payload = _get_matrix(tender_id, company_id)
    row = _find_row(payload, requirement_id)

    assert row["operational_state"] == "ACTION_REQUIRED"
    assert any(finding["code"] == "MATCH_REVIEW_PENDING" for finding in row["findings"])


def test_matrix_reports_human_override_and_stale_decision() -> None:
    tender_id = _create_tender("CMP matrix override")
    company_id = _create_company("CMP Matrix Override")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001:2015 vigente.")
    document_id = _import_company_document(company_id, "iso.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Matrix Override SA de CV",
        canonical_statement="La empresa acredita certificacion ISO 9001:2015 vigente.",
        source_excerpt="Certificacion ISO 9001:2015 vigente.",
        issuer="Organismo certificador",
        reference_number="ISO-9001-2015-A1",
    )
    _approve_evidence(company_id, evidence["id"])

    matches = _analyze_matches(tender_id, company_id)
    match_row = _find_requirement_row(matches, requirement_id)
    match = _find_match(match_row, "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    compliance = _analyze_compliance(tender_id, company_id)
    assert compliance["assessments"], "Expected an assessment before human override"

    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/requirements/{requirement_id}/compliance-decision",
        json={"decision_status": "DOES_NOT_COMPLY", "decision_note": "Override humano para prueba"},
    )
    assert response.status_code == 200, response.text

    payload = _get_matrix(tender_id, company_id)
    row = _find_row(payload, requirement_id)
    assert row["operational_state"] == "FINALIZED"
    assert any(finding["code"] == "HUMAN_OVERRIDE_PRESENT" for finding in row["findings"])

    with SessionLocal() as db:
        decision = db.execute(
            select(RequirementComplianceDecision).where(
                RequirementComplianceDecision.tender_id == tender_id,
                RequirementComplianceDecision.company_id == company_id,
                RequirementComplianceDecision.requirement_id == requirement_id,
            )
        ).scalar_one()
        decision.reviewed_assessment_fingerprint = "0" * 64
        db.commit()

    stale_payload = _get_matrix(tender_id, company_id)
    stale_row = _find_row(stale_payload, requirement_id)
    assert stale_row["operational_state"] == "REVIEW_REQUIRED"
    assert any(finding["code"] == "HUMAN_DECISION_STALE" for finding in stale_row["findings"])


def test_matrix_marks_conditional_requirements_unresolved() -> None:
    tender_id = _create_tender("CMP matrix conditional")
    company_id = _create_company("CMP Matrix Conditional")
    requirement_id = _seed_requirement(
        tender_id,
        "conditional.pdf",
        "En caso de propuesta conjunta, cada integrante debera presentar constancia fiscal vigente.",
    )

    _analyze_compliance(tender_id, company_id)
    payload = _get_matrix(tender_id, company_id)
    row = _find_row(payload, requirement_id)

    assert row["operational_state"] == "CONDITION_UNRESOLVED"
    assert any(finding["code"] == "CONDITIONAL_APPLICABILITY_UNRESOLVED" for finding in row["findings"])


def test_missing_evidence_audit_alias_matches_matrix_payload() -> None:
    tender_id = _create_tender("CMP matrix alias")
    company_a = _create_company("CMP Matrix Alias A")
    company_b = _create_company("CMP Matrix Alias B")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    document_id = _import_company_document(company_a, "iso.txt", _explicit_certification_fixture())
    evidence = _manual_company_evidence(
        company_a,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Matrix Alias A SA de CV",
        canonical_statement="La empresa acredita certificacion ISO 9001 vigente.",
        source_excerpt="Certificacion ISO 9001 vigente.",
    )
    _approve_evidence(company_a, evidence["id"])

    matrix = _get_matrix(tender_id, company_b)
    audit = _get_audit(tender_id, company_b)

    assert matrix["summary"]["company_evidence_count"] == 0
    assert audit["summary"]["company_evidence_count"] == 0
    assert any(finding["code"] == "NO_COMPANY_EVIDENCE" for finding in _find_row(matrix, requirement_id)["findings"])