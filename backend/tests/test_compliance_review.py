from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import RequirementComplianceAssessment, RequirementComplianceCheck, RequirementComplianceDecision
from tests.test_compliance_evaluation import (
    _analyze_compliance,
    _approve_evidence,
    _confirm_match,
    _create_company,
    _create_tender,
    _explicit_certification_fixture,
    _find_assessment,
    _find_match,
    _find_requirement_row,
    _import_company_document,
    _manual_company_evidence,
    _seed_requirement,
)
from tests.test_evidence_matching import _analyze_company_document, _analyze_matches
from tests.test_requirement_versioning import _analyze_changes, _analyze_requirement_versions, _confirm_change, _import_pdf, _normalize_requirements, _seed_page_and_normalized, _seed_requirement_candidate

client = TestClient(app)


def _get_compliance_review(tender_id: str, company_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/compliance-review")
    assert response.status_code == 200, response.text
    return response.json()


def _patch_compliance_decision(
    tender_id: str,
    company_id: str,
    requirement_id: str,
    decision_status: str,
    decision_note: str | None = None,
):
    payload = {"decision_status": decision_status, "decision_note": decision_note}
    return client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/requirements/{requirement_id}/compliance-decision",
        json=payload,
    )


def _find_review_row(payload: dict, requirement_id: str) -> dict:
    for row in payload["rows"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Review row not found")


def test_not_applicable_requires_justification_note() -> None:
    tender_id = _create_tender("CMP review note required")
    company_id = _create_company("CMP Review Note")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    _analyze_compliance(tender_id, company_id)

    missing_note = _patch_compliance_decision(tender_id, company_id, requirement_id, "NOT_APPLICABLE")
    assert missing_note.status_code == 400
    assert "decision_note is required" in missing_note.text

    ok = _patch_compliance_decision(tender_id, company_id, requirement_id, "NOT_APPLICABLE", "No aplica por alcance contratado")
    assert ok.status_code == 200, ok.text
    payload = ok.json()
    assert payload["human_decision"]["decision_status"] == "NOT_APPLICABLE"
    assert payload["human_decision"]["decision_note"] == "No aplica por alcance contratado"


def test_human_override_requires_note_and_sets_relation() -> None:
    tender_id = _create_tender("CMP human override")
    company_id = _create_company("CMP Override")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001:2015 vigente.")

    document_id = _import_company_document(company_id, "iso.txt", b"Documento base\n")
    evidence = _manual_company_evidence(
        company_id,
        document_id,
        evidence_type="CERTIFICATION",
        subject_kind="COMPANY",
        subject_name="CMP Override SA de CV",
        canonical_statement="La empresa acredita certificacion ISO 9001:2015 vigente.",
        source_excerpt="Certificacion ISO 9001:2015 vigente.",
        issuer="Organismo certificador",
        reference_number="ISO-9001-2015-A1",
    )
    _approve_evidence(company_id, evidence["id"])
    matches = _analyze_matches(tender_id, company_id)
    match = _find_match(_find_requirement_row(matches, requirement_id), "CERTIFICATION")
    _confirm_match(tender_id, company_id, match["id"])

    compliance = _analyze_compliance(tender_id, company_id)
    assert _find_assessment(compliance, requirement_id)["system_status"] == "SUPPORTED"

    missing_note = _patch_compliance_decision(tender_id, company_id, requirement_id, "DOES_NOT_COMPLY")
    assert missing_note.status_code == 400

    response = _patch_compliance_decision(
        tender_id,
        company_id,
        requirement_id,
        "DOES_NOT_COMPLY",
        "Se detecto exclusion contractual adicional fuera de evidencia automatica",
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["decision_relation"] == "HUMAN_OVERRIDE"
    assert payload["human_decision"]["freshness"] == "CURRENT"


def test_direct_verification_requires_note_for_complies_decision() -> None:
    tender_id = _create_tender("CMP direct verify human")
    company_id = _create_company("CMP Direct Verify Human")
    requirement_id = _seed_requirement(tender_id, "spanish.pdf", "La propuesta debera presentarse en idioma espanol.")

    compliance = _analyze_compliance(tender_id, company_id)
    assert _find_assessment(compliance, requirement_id)["system_status"] == "NOT_EVALUATED"

    missing_note = _patch_compliance_decision(tender_id, company_id, requirement_id, "COMPLIES")
    assert missing_note.status_code == 400

    response = _patch_compliance_decision(tender_id, company_id, requirement_id, "COMPLIES", "Validado manualmente en acto de presentacion")
    assert response.status_code == 200, response.text


def test_reanalysis_preserves_human_decision_and_can_become_stale() -> None:
    tender_id = _create_tender("CMP decision stale")
    company_id = _create_company("CMP Decision Stale")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    _analyze_compliance(tender_id, company_id)
    response = _patch_compliance_decision(tender_id, company_id, requirement_id, "NOT_APPLICABLE", "Excepcion validada por comprador")
    assert response.status_code == 200, response.text

    _analyze_compliance(tender_id, company_id)
    review = _get_compliance_review(tender_id, company_id)
    row = _find_review_row(review, requirement_id)
    assert row["human_decision"]["decision_status"] == "NOT_APPLICABLE"

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

    stale = _get_compliance_review(tender_id, company_id)
    stale_row = _find_review_row(stale, requirement_id)
    assert stale_row["human_decision"]["freshness"] == "STALE"


def test_patch_is_isolated_by_company_and_requires_existing_assessment() -> None:
    tender_id = _create_tender("CMP cross company guard")
    company_a = _create_company("CMP A")
    company_b = _create_company("CMP B")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    _analyze_compliance(tender_id, company_a)

    response = _patch_compliance_decision(
        tender_id,
        company_b,
        requirement_id,
        "NEEDS_REVIEW",
        "Sin evaluacion de empresa B",
    )
    assert response.status_code == 409


def test_patch_does_not_mutate_assessments_or_checks_and_is_idempotent() -> None:
    tender_id = _create_tender("CMP immutability")
    company_id = _create_company("CMP Immutable")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    _analyze_compliance(tender_id, company_id)

    with SessionLocal() as db:
        assessment_count_before = db.execute(
            select(func.count()).select_from(RequirementComplianceAssessment).where(
                RequirementComplianceAssessment.tender_id == tender_id,
                RequirementComplianceAssessment.company_id == company_id,
            )
        ).scalar_one()
        check_count_before = db.execute(
            select(func.count()).select_from(RequirementComplianceCheck).where(
                RequirementComplianceCheck.tender_id == tender_id,
                RequirementComplianceCheck.company_id == company_id,
            )
        ).scalar_one()

    first = _patch_compliance_decision(tender_id, company_id, requirement_id, "NOT_APPLICABLE", "No aplica en esta modalidad")
    second = _patch_compliance_decision(tender_id, company_id, requirement_id, "NOT_APPLICABLE", "No aplica en esta modalidad")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    with SessionLocal() as db:
        assessment_count_after = db.execute(
            select(func.count()).select_from(RequirementComplianceAssessment).where(
                RequirementComplianceAssessment.tender_id == tender_id,
                RequirementComplianceAssessment.company_id == company_id,
            )
        ).scalar_one()
        check_count_after = db.execute(
            select(func.count()).select_from(RequirementComplianceCheck).where(
                RequirementComplianceCheck.tender_id == tender_id,
                RequirementComplianceCheck.company_id == company_id,
            )
        ).scalar_one()
        decision_count = db.execute(
            select(func.count()).select_from(RequirementComplianceDecision).where(
                RequirementComplianceDecision.tender_id == tender_id,
                RequirementComplianceDecision.company_id == company_id,
                RequirementComplianceDecision.requirement_id == requirement_id,
            )
        ).scalar_one()

    assert assessment_count_before == assessment_count_after
    assert check_count_before == check_count_after
    assert decision_count == 1


def test_rejected_requirement_cannot_receive_human_decision() -> None:
    tender_id = _create_tender("CMP rejected requirement review")
    company_id = _create_company("CMP Rejected Requirement")
    requirement_id = _seed_requirement(tender_id, "iso.pdf", "El participante debera presentar certificado ISO 9001 vigente.")

    response = client.patch(
        f"/tenders/{tender_id}/requirements/{requirement_id}/review",
        json={"action": "REJECT", "review_note": "No corresponde a bases"},
    )
    assert response.status_code == 200, response.text

    _analyze_compliance(tender_id, company_id)

    blocked = _patch_compliance_decision(tender_id, company_id, requirement_id, "NEEDS_REVIEW", "Intento invalido")
    assert blocked.status_code == 409 or blocked.status_code == 400


def test_successor_requirement_does_not_inherit_predecessor_decision() -> None:
    tender_id = _create_tender("CMP successor no inheritance")
    company_id = _create_company("CMP Successor")
    base_doc_id = _import_pdf(tender_id, "anexo-d.pdf")
    addendum_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p_old, n_old = _seed_page_and_normalized(base_doc_id, 1, "Numeral 4.2: el plazo sera de 30 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=base_doc_id,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir un plazo de 30 dias naturales.",
    )

    p_new, n_new = _seed_page_and_normalized(addendum_doc_id, 1, "Numeral 4.2: el plazo sera de 45 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=addendum_doc_id,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir un plazo de 45 dias naturales.",
    )

    _seed_page_and_normalized(addendum_doc_id, 2, "Se modifica el Anexo D en el numeral 4.2, de 30 dias naturales a 45 dias naturales.")

    _normalize_requirements(tender_id)
    _analyze_compliance(tender_id, company_id)

    matrix_before = client.get(f"/tenders/{tender_id}/requirement-matrix")
    assert matrix_before.status_code == 200, matrix_before.text
    req_30 = next(
        row["requirement_id"] for row in matrix_before.json()["requirements"] if "30 dias naturales" in row["canonical_text"]
    )

    decision_response = _patch_compliance_decision(
        tender_id,
        company_id,
        req_30,
        "NOT_APPLICABLE",
        "Aplicable solo en version previa",
    )
    assert decision_response.status_code == 200, decision_response.text

    changes = _analyze_changes(tender_id)
    assert len(changes["changes"]) == 1
    _confirm_change(tender_id, changes["changes"][0]["id"])
    _analyze_requirement_versions(tender_id)
    _analyze_compliance(tender_id, company_id)

    review = _get_compliance_review(tender_id, company_id)
    req_45 = next(row for row in review["rows"] if "45 dias naturales" in row["requirement"]["canonical_text"])
    assert req_45["human_decision"]["decision_status"] == "PENDING"
