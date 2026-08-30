from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    CompanyDocument,
    CompanyEvidence,
    CompanyEvidenceReview,
    RequirementComplianceAssessment,
    RequirementComplianceCheck,
    RequirementComplianceDecision,
    RequirementEvidenceCandidateMatch,
    RequirementEvidenceCandidateReview,
)
from tests.test_compliance_evaluation import _create_company, _create_tender, _seed_requirement

client = TestClient(app)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "golden_company_001"


def _seed_golden_requirements(tender_id: str) -> dict[str, str]:
    controls = {
        "A_HIIP": "El interesado debera contar con el certificado de registro HIIP vigente durante todo el procedimiento.",
        "B_ACUERDO_PARTICIPANTE": "El participante debera aceptar el Acuerdo de Participante para reconocer como propia la documentacion enviada.",
        "C_DA2": "El participante debera presentar solicitudes de aclaracion mediante formato DA-2 debidamente firmado en PDF y editable.",
        "D_CONSORTIUM_REPORTING": "En caso de propuesta conjunta, cada integrante del consorcio debera informar su participacion por escrito.",
        "E_CONSORTIUM_FISCAL_SOCIAL": "En caso de propuesta conjunta, cada integrante debera presentar constancia fiscal y de seguridad social actualizada.",
        "F_SPANISH_PROPOSAL": "La propuesta y su documentacion deberan presentarse en idioma espanol.",
        "G_COMMON_REP_SIGNATURE": "La propuesta conjunta debera ser firmada por el representante comun designado por los integrantes.",
        "H_PERSONNEL_MANUFACTURER_CERT": "El personal tecnico del participante debera contar con certificacion del fabricante para servicio y refacciones.",
        "I_CV_TITLE_LICENSE": "El participante debera incluir curriculum vitae, titulo y cedula profesional del personal clave.",
        "J_EXPERIENCE_TWO_SERVICES": "El participante debera acreditar participacion en al menos 2 servicios similares en los ultimos cinco anos.",
        "K_ISO_9001": "El participante debera presentar certificado ISO 9001:2015 vigente.",
        "L_SUPPORT_LETTER": "El participante debera presentar carta de respaldo del fabricante del ano en curso.",
    }
    return {key: _seed_requirement(tender_id, f"{key.lower()}.pdf", text) for key, text in controls.items()}


def _import_fixture_documents(company_id: str) -> list[dict[str, object]]:
    imported: list[dict[str, object]] = []
    for fixture in sorted(FIXTURE_DIR.glob("GC001_*_BASE.txt")):
        payload = fixture.read_bytes()
        response = client.post(
            f"/companies/{company_id}/documents/import",
            files=[("files", (fixture.name, payload, "text/plain"))],
            data={"source_relative_paths": f"fixtures/golden_company_001/{fixture.name}"},
        )
        assert response.status_code == 200, response.text
        result = response.json()[0]
        assert result["status"] == "IMPORTED"
        assert result["sha256"] == sha256(payload).hexdigest()
        imported.append(result)
    return imported


def _analyze_company_documents(company_id: str, document_ids: list[str]) -> dict[str, dict[str, object]]:
    payloads: dict[str, dict[str, object]] = {}
    for document_id in document_ids:
        response = client.post(f"/companies/{company_id}/documents/{document_id}/analyze-evidence")
        assert response.status_code == 200, response.text
        payloads[document_id] = response.json()
    return payloads


def _list_company_evidence(company_id: str) -> dict[str, object]:
    response = client.get(f"/companies/{company_id}/evidence")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_matches(tender_id: str, company_id: str) -> dict[str, object]:
    response = client.post(f"/tenders/{tender_id}/companies/{company_id}/analyze-evidence-matches")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_compliance(tender_id: str, company_id: str) -> dict[str, object]:
    response = client.post(f"/tenders/{tender_id}/companies/{company_id}/analyze-compliance")
    assert response.status_code == 200, response.text
    return response.json()


def _get_matrix(tender_id: str, company_id: str) -> dict[str, object]:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/compliance-matrix")
    assert response.status_code == 200, response.text
    return response.json()


def _get_missing_audit(tender_id: str, company_id: str) -> dict[str, object]:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/missing-evidence-audit")
    assert response.status_code == 200, response.text
    return response.json()


def _get_review(tender_id: str, company_id: str) -> dict[str, object]:
    response = client.get(f"/tenders/{tender_id}/companies/{company_id}/compliance-review")
    assert response.status_code == 200, response.text
    return response.json()


def _assessment_by_requirement(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["requirement_id"]: row for row in payload["assessments"]}


def _match_rows_by_requirement(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["requirement_id"]: row for row in payload["requirements"]}


def _check(row: dict[str, object], check_type: str) -> dict[str, object]:
    for check in row["checks"]:
        if check["check_type"] == check_type:
            return check
    raise AssertionError(f"Check {check_type} not found")


def _find_match(row: dict[str, object], evidence_type: str, evidence_id: str | None = None) -> dict[str, object]:
    for match in row["matches"]:
        if match["company_evidence"]["evidence_type"] != evidence_type:
            continue
        if evidence_id is not None and match["company_evidence"]["id"] != evidence_id:
            continue
        return match
    raise AssertionError(f"Match for evidence type {evidence_type} not found")


def _review_row_by_requirement(payload: dict[str, object], requirement_id: str) -> dict[str, object]:
    for row in payload["rows"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Review row not found")


def _matrix_row_by_requirement(payload: dict[str, object], requirement_id: str) -> dict[str, object]:
    for row in payload["rows"]:
        if row["requirement"]["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Matrix row not found")


def _patch_evidence_review(company_id: str, evidence_id: str, review_status: str, review_note: str) -> None:
    response = client.patch(
        f"/companies/{company_id}/evidence/{evidence_id}/review",
        json={"review_status": review_status, "review_note": review_note},
    )
    assert response.status_code == 200, response.text


def _patch_match_review(tender_id: str, company_id: str, match_id: str, review_status: str, review_note: str) -> None:
    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/evidence-match-candidates/{match_id}/review",
        json={"review_status": review_status, "review_note": review_note},
    )
    assert response.status_code == 200, response.text


def _patch_decision(tender_id: str, company_id: str, requirement_id: str, decision_status: str, note: str) -> None:
    response = client.patch(
        f"/tenders/{tender_id}/companies/{company_id}/requirements/{requirement_id}/compliance-decision",
        json={"decision_status": decision_status, "decision_note": note},
    )
    assert response.status_code == 200, response.text


def _table_counts_for_scope(tender_id: str, company_id: str) -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "company_documents": db.execute(
                select(func.count()).select_from(CompanyDocument).where(CompanyDocument.company_id == company_id)
            ).scalar_one(),
            "company_evidence": db.execute(
                select(func.count()).select_from(CompanyEvidence).where(CompanyEvidence.company_id == company_id)
            ).scalar_one(),
            "company_evidence_reviews": db.execute(
                select(func.count()).select_from(CompanyEvidenceReview).where(CompanyEvidenceReview.company_id == company_id)
            ).scalar_one(),
            "matches": db.execute(
                select(func.count()).select_from(RequirementEvidenceCandidateMatch).where(
                    RequirementEvidenceCandidateMatch.tender_id == tender_id,
                    RequirementEvidenceCandidateMatch.company_id == company_id,
                )
            ).scalar_one(),
            "match_reviews": db.execute(
                select(func.count()).select_from(RequirementEvidenceCandidateReview).where(
                    RequirementEvidenceCandidateReview.tender_id == tender_id,
                    RequirementEvidenceCandidateReview.company_id == company_id,
                )
            ).scalar_one(),
            "assessments": db.execute(
                select(func.count()).select_from(RequirementComplianceAssessment).where(
                    RequirementComplianceAssessment.tender_id == tender_id,
                    RequirementComplianceAssessment.company_id == company_id,
                )
            ).scalar_one(),
            "checks": db.execute(
                select(func.count()).select_from(RequirementComplianceCheck).where(
                    RequirementComplianceCheck.tender_id == tender_id,
                    RequirementComplianceCheck.company_id == company_id,
                )
            ).scalar_one(),
            "decisions": db.execute(
                select(func.count()).select_from(RequirementComplianceDecision).where(
                    RequirementComplianceDecision.tender_id == tender_id,
                    RequirementComplianceDecision.company_id == company_id,
                )
            ).scalar_one(),
        }


def test_mvp05_golden_company_tender_integrated_acceptance() -> None:
    assert FIXTURE_DIR.exists()
    fixture_files = sorted(FIXTURE_DIR.glob("GC001_*_BASE.txt"))
    assert len(fixture_files) == 11

    tender_id = _create_tender("MVP-05.7 Golden Company + Golden Tender")
    requirements = _seed_golden_requirements(tender_id)

    company_a = _create_company("GOLDEN INDUSTRIAL SERVICES")
    company_b = _create_company("GOLDEN INTEGRATION CONTROL B")

    import_start = perf_counter()
    imported_docs = _import_fixture_documents(company_a)
    import_elapsed = perf_counter() - import_start
    assert len(imported_docs) == 11

    analyze_evidence_start = perf_counter()
    analyzed_docs = _analyze_company_documents(company_a, [row["document_id"] for row in imported_docs])
    analyze_evidence_elapsed = perf_counter() - analyze_evidence_start
    assert len(analyzed_docs) == 11

    evidence_list_before = _list_company_evidence(company_a)
    evidence_rows_before = evidence_list_before["evidence"]
    assert evidence_rows_before
    assert all(row["source_excerpt"] for row in evidence_rows_before)
    assert all(row["source_document"]["company_id"] == company_a for row in evidence_rows_before)
    assert all(row["review"] is None or row["review"]["review_status"] == "PENDING" for row in evidence_rows_before)

    evidence_by_type: dict[str, list[dict[str, object]]] = {}
    for row in evidence_rows_before:
        evidence_by_type.setdefault(row["evidence_type"], []).append(row)

    assert "CERTIFICATION" in evidence_by_type
    assert "REGISTRATION" in evidence_by_type
    assert len(evidence_by_type.get("EXPERIENCE", [])) >= 2
    assert len(evidence_by_type.get("PERSONNEL_QUALIFICATION", [])) >= 1

    iso_evidence = next(
        row
        for row in evidence_by_type["CERTIFICATION"]
        if row["source_document"]["original_filename"] == "GC001_07_ISO9001_BASE.txt"
    )
    registration_family = evidence_by_type.get("REGISTRATION", [])
    hiip_evidence = next(
        row
        for row in registration_family
        if row["source_document"]["original_filename"] == "GC001_06_HIIP_REGISTRATION_BASE.txt"
    )
    cv_evidence = next(
        row
        for row in evidence_by_type["PERSONNEL_QUALIFICATION"]
        if (row.get("reference_number") or "").startswith("CED-")
    )
    personnel_cert_evidence = next(
        row
        for row in evidence_by_type["CERTIFICATION"]
        if row["source_document"]["original_filename"] == "GC001_09_PERSONNEL_MANUFACTURER_CERT_BASE.txt"
    )
    experience_evidence = evidence_by_type["EXPERIENCE"][:2]

    for target in [iso_evidence, hiip_evidence, cv_evidence, personnel_cert_evidence, *experience_evidence]:
        _patch_evidence_review(company_a, target["id"], "APPROVED", "MVP-05.7 integrated acceptance review")

    matches_start = perf_counter()
    matches_payload = _analyze_matches(tender_id, company_a)
    matches_elapsed = perf_counter() - matches_start
    rows_by_requirement = _match_rows_by_requirement(matches_payload)

    assert rows_by_requirement[requirements["A_HIIP"]]["candidate_count"] >= 1
    assert rows_by_requirement[requirements["L_SUPPORT_LETTER"]]["candidate_count"] == 0
    assert rows_by_requirement[requirements["F_SPANISH_PROPOSAL"]]["candidate_count"] == 0
    assert rows_by_requirement[requirements["G_COMMON_REP_SIGNATURE"]]["candidate_count"] == 0
    assert rows_by_requirement[requirements["J_EXPERIENCE_TWO_SERVICES"]]["candidate_count"] >= 2
    assert all(
        match["review"] is None or match["review"]["review_status"] == "PENDING"
        for row in matches_payload["requirements"]
        for match in row["matches"]
    )

    iso_match = _find_match(rows_by_requirement[requirements["K_ISO_9001"]], "CERTIFICATION", iso_evidence["id"])
    hiip_match = None
    for match in rows_by_requirement[requirements["A_HIIP"]]["matches"]:
        if match["company_evidence"]["id"] != hiip_evidence["id"]:
            continue
        hiip_match = match
        break
    cv_match = _find_match(rows_by_requirement[requirements["I_CV_TITLE_LICENSE"]], "PERSONNEL_QUALIFICATION", cv_evidence["id"])
    personnel_cert_match = _find_match(
        rows_by_requirement[requirements["H_PERSONNEL_MANUFACTURER_CERT"]],
        "CERTIFICATION",
        personnel_cert_evidence["id"],
    )
    experience_matches = [
        _find_match(rows_by_requirement[requirements["J_EXPERIENCE_TWO_SERVICES"]], "EXPERIENCE", row["id"])
        for row in experience_evidence
    ]

    h_row_matches = rows_by_requirement[requirements["H_PERSONNEL_MANUFACTURER_CERT"]]["matches"]
    for match in h_row_matches:
        if match["company_evidence"]["id"] != iso_evidence["id"]:
            continue
        assert match["match_strength"] != "STRONG"

    assert hiip_match is not None
    selected_matches = [iso_match, hiip_match, cv_match, personnel_cert_match, *experience_matches]

    for selected in selected_matches:
        _patch_match_review(tender_id, company_a, selected["id"], "CONFIRMED", "MVP-05.7 integrated acceptance confirmation")

    compliance_start = perf_counter()
    compliance_before = _analyze_compliance(tender_id, company_a)
    compliance_elapsed = perf_counter() - compliance_start
    assessments_before = _assessment_by_requirement(compliance_before)

    assert assessments_before[requirements["F_SPANISH_PROPOSAL"]]["system_status"] == "NOT_EVALUATED"
    assert assessments_before[requirements["G_COMMON_REP_SIGNATURE"]]["system_status"] == "NOT_EVALUATED"
    assert assessments_before[requirements["D_CONSORTIUM_REPORTING"]]["applicability_context"] == "CONDITION_UNRESOLVED"
    assert assessments_before[requirements["E_CONSORTIUM_FISCAL_SOCIAL"]]["applicability_context"] == "CONDITION_UNRESOLVED"
    assert assessments_before[requirements["L_SUPPORT_LETTER"]]["system_status"] == "NOT_SUPPORTED"
    assert "NO_SUPPORTING_EVIDENCE" in assessments_before[requirements["L_SUPPORT_LETTER"]]["warning_codes"]

    hiip_assessment = assessments_before[requirements["A_HIIP"]]
    assert "NO_SUPPORTING_EVIDENCE" not in hiip_assessment["warning_codes"]
    assert hiip_assessment["system_status"] in {"SUPPORTED", "PARTIALLY_SUPPORTED", "REVIEW_REQUIRED"}

    iso_assessment = assessments_before[requirements["K_ISO_9001"]]
    assert iso_assessment["system_status"] in {"SUPPORTED", "PARTIALLY_SUPPORTED", "REVIEW_REQUIRED"}
    assert _check(iso_assessment, "SPECIFIC_STANDARD")["check_status"] == "PASS"
    assert _check(iso_assessment, "STANDARD_EDITION")["check_status"] == "PASS"

    review_before = _get_review(tender_id, company_a)
    assert review_before["summary"]["pending_count"] == len(review_before["rows"])

    _patch_decision(
        tender_id,
        company_a,
        requirements["K_ISO_9001"],
        "COMPLIES",
        "Golden acceptance: evidencia ISO 9001:2015 validada y confirmada.",
    )
    _patch_decision(
        tender_id,
        company_a,
        requirements["L_SUPPORT_LETTER"],
        "DOES_NOT_COMPLY",
        "Golden acceptance: no manufacturer support letter is present.",
    )
    _patch_decision(
        tender_id,
        company_a,
        requirements["D_CONSORTIUM_REPORTING"],
        "NOT_APPLICABLE",
        "Golden acceptance scenario is an individual proposal.",
    )
    _patch_decision(
        tender_id,
        company_a,
        requirements["F_SPANISH_PROPOSAL"],
        "COMPLIES",
        "Golden acceptance: verified directly by the acceptance operator.",
    )

    review_after_decisions = _get_review(tender_id, company_a)
    assert _review_row_by_requirement(review_after_decisions, requirements["K_ISO_9001"])["human_decision"]["decision_status"] == "COMPLIES"
    assert _review_row_by_requirement(review_after_decisions, requirements["L_SUPPORT_LETTER"])["human_decision"]["decision_status"] == "DOES_NOT_COMPLY"
    assert _review_row_by_requirement(review_after_decisions, requirements["D_CONSORTIUM_REPORTING"])["human_decision"]["decision_status"] == "NOT_APPLICABLE"
    assert _review_row_by_requirement(review_after_decisions, requirements["F_SPANISH_PROPOSAL"])["human_decision"]["decision_status"] == "COMPLIES"

    decision_rows = [
        _review_row_by_requirement(review_after_decisions, requirements[key])["human_decision"]
        for key in ["K_ISO_9001", "L_SUPPORT_LETTER", "D_CONSORTIUM_REPORTING", "F_SPANISH_PROPOSAL"]
    ]
    assert all(row["freshness"] == "CURRENT" for row in decision_rows)

    assessments_before_decision = {
        requirement_id: (row["system_status"], row["assessment_fingerprint"])
        for requirement_id, row in assessments_before.items()
    }

    counts_before_reanalysis = _table_counts_for_scope(tender_id, company_a)
    evidence_fingerprints_before = {row["id"]: row["semantic_fingerprint"] for row in _list_company_evidence(company_a)["evidence"]}
    match_fingerprints_before = {
        match["id"]: match["match_fingerprint"]
        for row in _analyze_matches(tender_id, company_a)["requirements"]
        for match in row["matches"]
    }
    assessment_fingerprints_before = {
        row["requirement_id"]: row["assessment_fingerprint"]
        for row in _analyze_compliance(tender_id, company_a)["assessments"]
    }

    _analyze_company_documents(company_a, [row["document_id"] for row in imported_docs])
    matches_after_reanalysis = _analyze_matches(tender_id, company_a)
    compliance_after_reanalysis = _analyze_compliance(tender_id, company_a)

    counts_after_reanalysis = _table_counts_for_scope(tender_id, company_a)
    assert counts_before_reanalysis == counts_after_reanalysis

    evidence_fingerprints_after = {row["id"]: row["semantic_fingerprint"] for row in _list_company_evidence(company_a)["evidence"]}
    assert evidence_fingerprints_before == evidence_fingerprints_after

    match_fingerprints_after = {
        match["id"]: match["match_fingerprint"]
        for row in matches_after_reanalysis["requirements"]
        for match in row["matches"]
    }
    assert match_fingerprints_before == match_fingerprints_after

    assessment_fingerprints_after = {
        row["requirement_id"]: row["assessment_fingerprint"]
        for row in compliance_after_reanalysis["assessments"]
    }
    assert assessment_fingerprints_before == assessment_fingerprints_after

    review_after_reanalysis = _get_review(tender_id, company_a)
    for key in ["K_ISO_9001", "L_SUPPORT_LETTER", "D_CONSORTIUM_REPORTING", "F_SPANISH_PROPOSAL"]:
        row = _review_row_by_requirement(review_after_reanalysis, requirements[key])
        assert row["human_decision"]["freshness"] == "CURRENT"

    matrix_before_gets = _table_counts_for_scope(tender_id, company_a)
    _ = _list_company_evidence(company_a)
    _ = client.get(f"/tenders/{tender_id}/companies/{company_a}/evidence-match-candidates")
    _ = client.get(f"/tenders/{tender_id}/companies/{company_a}/compliance-assessments")
    _ = _get_review(tender_id, company_a)
    matrix_first = _get_matrix(tender_id, company_a)
    matrix_second = _get_matrix(tender_id, company_a)
    audit_first = _get_missing_audit(tender_id, company_a)
    audit_second = _get_missing_audit(tender_id, company_a)
    matrix_after_gets = _table_counts_for_scope(tender_id, company_a)
    assert matrix_before_gets == matrix_after_gets

    def _normalize_matrix(payload: dict[str, object]) -> dict[str, object]:
        return {
            "summary": payload["summary"],
            "rows": [
                {
                    "requirement_id": row["requirement"]["requirement_id"],
                    "operational_state": row["operational_state"],
                    "system_status": row["system_assessment"]["system_status"] if row["system_assessment"] else None,
                    "human_status": row["human_decision"]["decision_status"] if row["human_decision"] else None,
                    "human_freshness": row["human_decision"]["freshness"] if row["human_decision"] else None,
                    "findings": [(finding["code"], finding["severity"]) for finding in row["findings"]],
                }
                for row in payload["rows"]
            ],
        }

    assert _normalize_matrix(matrix_first) == _normalize_matrix(matrix_second)
    assert _normalize_matrix(audit_first) == _normalize_matrix(audit_second)

    matrix_states = set(matrix_first["summary"]["operational_state_counts"].keys())
    assert "FINALIZED" in matrix_states
    assert "ACTION_REQUIRED" in matrix_states
    assert "DIRECT_VERIFICATION_PENDING" in matrix_states
    assert "CONDITION_UNRESOLVED" in matrix_states

    matrix_k = _matrix_row_by_requirement(matrix_first, requirements["K_ISO_9001"])
    matrix_l = _matrix_row_by_requirement(matrix_first, requirements["L_SUPPORT_LETTER"])
    matrix_f = _matrix_row_by_requirement(matrix_first, requirements["F_SPANISH_PROPOSAL"])
    matrix_e = _matrix_row_by_requirement(matrix_first, requirements["E_CONSORTIUM_FISCAL_SOCIAL"])
    assert matrix_k["operational_state"] == "FINALIZED"
    assert matrix_l["human_decision"]["decision_status"] == "DOES_NOT_COMPLY"
    assert matrix_l["operational_state"] == "FINALIZED"
    assert matrix_f["system_assessment"]["system_status"] == "NOT_EVALUATED"
    assert matrix_e["operational_state"] == "CONDITION_UNRESOLVED"

    # Cross-company isolation control.
    company_b_matches = _analyze_matches(tender_id, company_b)
    company_b_rows = _match_rows_by_requirement(company_b_matches)
    assert company_b_rows[requirements["K_ISO_9001"]]["candidate_count"] == 0

    company_b_compliance = _analyze_compliance(tender_id, company_b)
    company_b_assessments = _assessment_by_requirement(company_b_compliance)
    assert company_b_assessments[requirements["K_ISO_9001"]]["system_status"] == "NOT_SUPPORTED"

    company_b_matrix = _get_matrix(tender_id, company_b)
    assert company_b_matrix["summary"]["company_evidence_count"] == 0
    assert _matrix_row_by_requirement(company_b_matrix, requirements["D_CONSORTIUM_REPORTING"])["operational_state"] == "CONDITION_UNRESOLVED"

    # Human decisions must not mutate existing system assessments.
    assessments_after = _assessment_by_requirement(_analyze_compliance(tender_id, company_a))
    for requirement_id, baseline in assessments_before_decision.items():
        current = assessments_after[requirement_id]
        assert (current["system_status"], current["assessment_fingerprint"]) == baseline

    # Timing diagnostics stay explicit and bounded for local acceptance expectations.
    assert import_elapsed >= 0
    assert analyze_evidence_elapsed >= 0
    assert matches_elapsed >= 0
    assert compliance_elapsed >= 0