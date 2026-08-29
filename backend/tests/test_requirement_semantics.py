from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import (
    EvaluationCriterion,
    Requirement,
    RequirementCandidate,
    RequirementCandidateEvidence,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementSemantics,
    TenderEvaluationModel,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "REQ-SEM-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page_and_normalized(document_id: str, page_number: int, text: str) -> tuple[str, str]:
    from app.models import DocumentPage, NormalizedContent, TenderDocument

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

        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = max(doc.page_count, page_number)
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"

        normalized = NormalizedContent(
            document_page_id=page.id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page.id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(normalized)
        db.flush()
        db.commit()
        return page.id, normalized.id
    finally:
        db.close()


def _seed_candidate(
    tender_id: str,
    document_id: str,
    page_id: str,
    normalized_content_id: str,
    text: str,
    *,
    actor_text: str | None = "El participante",
    modality_text: str | None = "deberá",
    source_page: int = 1,
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

        evidence = RequirementCandidateEvidence(
            candidate_id=candidate.id,
            source_document_id=document_id,
            source_page=source_page,
            source_excerpt=text,
            excerpt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            document_page_id=page_id,
            normalized_content_id=normalized_content_id,
        )
        db.add(evidence)
        db.commit()
        return candidate.id
    finally:
        db.close()


def _normalize(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_semantics(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert response.status_code == 200, response.text
    return response.json()


def _prepare_single_requirement(text: str, *, actor: str | None = "El participante") -> tuple[str, dict]:
    tender_id = _create_tender(f"REQ-SEM {text[:20]}")
    doc_id = _import_pdf(tender_id, "req-sem.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text=actor)
    _normalize(tender_id)
    payload = _analyze_semantics(tender_id)
    return tender_id, payload


def _first_requirement(payload: dict) -> dict:
    assert payload["requirements"]
    return payload["requirements"][0]


def test_mandatory_detection_for_debera_presentar() -> None:
    _, payload = _prepare_single_requirement("El participante deberá presentar su acta constitutiva.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"


def test_mandatory_detection_for_rejection_language() -> None:
    _, payload = _prepare_single_requirement("La falta de firma será causa de desechamiento.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"


def test_mandatory_detection_for_imperative_checklist() -> None:
    _, payload = _prepare_single_requirement("Presentar Anexo D firmado.", actor="Participante")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"


def test_conditional_detection_consorcio_case() -> None:
    _, payload = _prepare_single_requirement("En caso de participación en consorcio, cada integrante deberá presentar su constancia fiscal.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert "En caso de participación en consorcio" in row["condition_text"]


def test_conditional_detection_tratandose_case() -> None:
    _, payload = _prepare_single_requirement("Tratándose de propuesta conjunta, deberá presentarse convenio privado.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"


def test_temporal_cuando_is_not_always_conditional() -> None:
    _, payload = _prepare_single_requirement("El documento deberá presentarse cuando se abra la plataforma.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"


def test_unknown_applicability_for_ocr_garbage() -> None:
    _, payload = _prepare_single_requirement("we participen documento al tenor de lo anterior")
    row = _first_requirement(payload)

    assert row["applicability"] == "UNKNOWN"
    assert row["interpretation_status"] == "REVIEW_REQUIRED"


def test_explicit_artifact_certificate() -> None:
    _, payload = _prepare_single_requirement("El participante deberá presentar certificado ISO 9001 vigente.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert any(item["evidence_type"] == "CERTIFICATE" for item in row["expected_evidence"])


def test_explicit_artifact_letter() -> None:
    _, payload = _prepare_single_requirement("El participante deberá presentar carta de respaldo del fabricante.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert any(item["evidence_type"] == "LETTER" for item in row["expected_evidence"])


def test_explicit_artifact_form() -> None:
    _, payload = _prepare_single_requirement("El participante deberá presentar el formato DA-2 firmado.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert any(item["evidence_type"] == "FORM" for item in row["expected_evidence"])


def test_explicit_artifact_screenshot() -> None:
    _, payload = _prepare_single_requirement("El participante deberá anexar captura de pantalla del certificado vigente.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert any(item["evidence_type"] == "SCREENSHOT_OR_DIGITAL_PROOF" for item in row["expected_evidence"])


def test_direct_verification_for_spanish_language() -> None:
    _, payload = _prepare_single_requirement("La propuesta deberá presentarse en idioma español.", actor="La propuesta")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "DIRECT_VERIFICATION"


def test_direct_verification_for_signature() -> None:
    _, payload = _prepare_single_requirement("La propuesta deberá ser firmada por el representante común.", actor="La propuesta")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "DIRECT_VERIFICATION"


def test_direct_verification_for_prices_rule() -> None:
    _, payload = _prepare_single_requirement("Los precios unitarios no podrán ser mayores a los originalmente presentados.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "DIRECT_VERIFICATION"


def test_unspecified_evidence_for_contar_con() -> None:
    _, payload = _prepare_single_requirement("El personal deberá contar con certificación del fabricante.", actor="El personal")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "UNSPECIFIED"


def test_unspecified_evidence_for_acreditar_without_method() -> None:
    _, payload = _prepare_single_requirement("El licitante deberá acreditar experiencia.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "UNSPECIFIED"


def test_preserve_alternative_evidence_phrase() -> None:
    _, payload = _prepare_single_requirement(
        "El participante deberá acreditar experiencia mediante constancias de experiencia, cartas laborales u otros documentos equivalentes."
    )
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert len(row["expected_evidence"]) == 1
    assert "constancias de experiencia" in row["expected_evidence"][0]["evidence_description"]
    assert "cartas laborales" in row["expected_evidence"][0]["evidence_description"]


def test_conditional_with_explicit_artifact() -> None:
    _, payload = _prepare_single_requirement("En caso de consorcio, cada integrante deberá presentar constancia fiscal.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"


def test_conditional_with_direct_verification() -> None:
    _, payload = _prepare_single_requirement("Si participa conjuntamente, la propuesta deberá estar firmada por el representante común.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["evidence_mode"] == "DIRECT_VERIFICATION"


def test_future_tense_consortium_member_obligation_is_conditional_and_artifact() -> None:
    _, payload = _prepare_single_requirement("Cada integrante de la propuesta conjunta presentará su constancia fiscal.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert "propuesta conjunta" in row["condition_text"]
    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"


def test_future_tense_participant_artifact_obligation_is_mandatory() -> None:
    _, payload = _prepare_single_requirement("El participante presentará el formato firmado.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"
    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"


def test_future_tense_percentage_in_proposal_is_direct_verification() -> None:
    _, payload = _prepare_single_requirement("El participante incluirá el porcentaje ofertado en su propuesta.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"
    assert row["evidence_mode"] == "DIRECT_VERIFICATION"
    assert len(row["expected_evidence"]) == 0


def test_future_tense_without_bidder_context_does_not_create_artifact() -> None:
    _, payload = _prepare_single_requirement("El Área Contratante publicará el fallo.", actor="Área Contratante")
    row = _first_requirement(payload)

    assert row["evidence_mode"] != "EXPLICIT_ARTIFACT"


def test_conditional_detection_for_en_el_caso_de_que() -> None:
    _, payload = _prepare_single_requirement(
        "En el caso de que el personal haya participado en un contrato con varios trabajos, el participante deberá relacionar cada trabajo."
    )
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert row["condition_text"].startswith("En el caso de que")


def test_scope_conditionality_for_people_who_integrate_consortium() -> None:
    _, payload = _prepare_single_requirement("Las personas que integran el consorcio deberán celebrar un convenio privado.")
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert "personas que integran el consorcio" in row["condition_text"]
    assert row["evidence_mode"] == "UNSPECIFIED"


def test_common_representative_scope_is_not_global_mandatory() -> None:
    _, payload = _prepare_single_requirement(
        "La propuesta deberá ser firmada por el representante común designado por los integrantes del grupo en el convenio.",
        actor="La propuesta",
    )
    row = _first_requirement(payload)

    assert row["applicability"] == "CONDITIONAL"
    assert row["condition_text"] is not None
    assert "representante común" in row["condition_text"].lower()
    assert row["evidence_mode"] == "DIRECT_VERIFICATION"


def test_consortium_word_alone_does_not_force_conditional() -> None:
    _, payload = _prepare_single_requirement("Todos los participantes deberán indicar si participan en consorcio.")
    row = _first_requirement(payload)

    assert row["applicability"] == "MANDATORY"


def test_future_tense_constancia_creates_explicit_artifact() -> None:
    _, payload = _prepare_single_requirement("Cada integrante presentará su constancia de situación fiscal.")
    row = _first_requirement(payload)

    assert row["evidence_mode"] == "EXPLICIT_ARTIFACT"
    assert any("constancia de situación fiscal" in item["evidence_description"].lower() for item in row["expected_evidence"])


def test_review_required_propagates_from_normalization_review_status() -> None:
    _, payload = _prepare_single_requirement("we El participante deberá presentar en su propuesta técnica copia de sls Certificado de calidad ISO 9001:2015 el cual")
    row = _first_requirement(payload)

    assert row["interpretation_status"] == "REVIEW_REQUIRED"
    assert row["applicability"] == "MANDATORY"


def test_idempotent_analysis_no_duplicate_rows() -> None:
    tender_id, _ = _prepare_single_requirement("El participante deberá presentar certificado ISO 9001 vigente.")

    first = _analyze_semantics(tender_id)
    second = _analyze_semantics(tender_id)

    assert first["summary"]["evidence_expectation_count"] == second["summary"]["evidence_expectation_count"]

    db = SessionLocal()
    try:
        requirements = db.execute(select(Requirement).where(Requirement.tender_id == tender_id)).scalars().all()
        semantics = db.execute(
            select(RequirementSemantics)
            .join(Requirement, Requirement.id == RequirementSemantics.requirement_id)
            .where(Requirement.tender_id == tender_id)
        ).scalars().all()
        expectations = db.execute(
            select(RequirementEvidenceExpectation)
            .join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id)
            .where(Requirement.tender_id == tender_id)
        ).scalars().all()
        assert len(requirements) == 1
        assert len(semantics) == 1
        assert len(expectations) == 1
    finally:
        db.close()


def test_requirement_and_candidate_immutability_after_semantics_analysis() -> None:
    tender_id = _create_tender("REQ-SEM immutability")
    doc_id = _import_pdf(tender_id, "immutable.pdf")
    text = "El participante deberá presentar carta de respaldo del fabricante."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    candidate_id = _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    normalized = _normalize(tender_id)
    requirement_id = normalized["requirements"][0]["id"]

    db = SessionLocal()
    try:
        requirement_before = db.get(Requirement, requirement_id)
        candidate_before = db.get(RequirementCandidate, candidate_id)
        assert requirement_before is not None
        assert candidate_before is not None
        snapshot = (
            requirement_before.canonical_text,
            requirement_before.category,
            requirement_before.normalization_status,
            candidate_before.requirement_text,
            candidate_before.semantic_key,
        )
    finally:
        db.close()

    _analyze_semantics(tender_id)

    db = SessionLocal()
    try:
        requirement_after = db.get(Requirement, requirement_id)
        candidate_after = db.get(RequirementCandidate, candidate_id)
        assert requirement_after is not None
        assert candidate_after is not None
        assert snapshot == (
            requirement_after.canonical_text,
            requirement_after.category,
            requirement_after.normalization_status,
            candidate_after.requirement_text,
            candidate_after.semantic_key,
        )
    finally:
        db.close()


def test_multi_source_conflict_marks_review_required() -> None:
    tender_id = _create_tender("REQ-SEM multi-source conflict")
    doc_id = _import_pdf(tender_id, "multi.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar constancia fiscal.")
    page_b, norm_b = _seed_page_and_normalized(doc_id, 2, "En caso de consorcio, cada integrante deberá presentar constancia fiscal.")
    candidate_a = _seed_candidate(tender_id, doc_id, page_a, norm_a, "El participante deberá presentar constancia fiscal.", source_page=1)
    candidate_b = _seed_candidate(tender_id, doc_id, page_b, norm_b, "En caso de consorcio, cada integrante deberá presentar constancia fiscal.", source_page=2)

    _normalize(tender_id)

    db = SessionLocal()
    try:
        requirement = db.execute(select(Requirement).where(Requirement.tender_id == tender_id)).scalars().first()
        assert requirement is not None
        links = db.execute(select(RequirementCandidateLink).where(RequirementCandidateLink.requirement_id == requirement.id)).scalars().all()
        for link in links:
            db.delete(link)
        db.flush()
        db.add(RequirementCandidateLink(requirement_id=requirement.id, requirement_candidate_id=candidate_a, is_primary_source=True, link_origin="DETERMINISTIC"))
        db.add(RequirementCandidateLink(requirement_id=requirement.id, requirement_candidate_id=candidate_b, is_primary_source=False, link_origin="DETERMINISTIC"))
        db.commit()
    finally:
        db.close()

    payload = _analyze_semantics(tender_id)
    row = _first_requirement(payload)

    assert row["applicability"] == "UNKNOWN"
    assert row["interpretation_status"] == "REVIEW_REQUIRED"


def test_closed_domain_entities_unchanged() -> None:
    tender_id = _create_tender("REQ-SEM closed domain")
    doc_id = _import_pdf(tender_id, "closed.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar documento legal.")
    _seed_candidate(tender_id, doc_id, page_id, norm_id, "El participante deberá presentar documento legal.")
    _normalize(tender_id)

    db = SessionLocal()
    try:
        evaluation_model = TenderEvaluationModel(
            tender_id=tender_id,
            suggested_method="UNKNOWN",
            summary="test",
            review_status="SUGGESTED",
            detector_version="mvp-04.1",
        )
        db.add(evaluation_model)
        db.flush()

        criterion = EvaluationCriterion(
            tender_id=tender_id,
            evaluation_model_id=evaluation_model.id,
            semantic_key=hashlib.sha256(f"criterion-{tender_id}".encode("utf-8")).hexdigest(),
            criterion_type="UNKNOWN",
            title="test",
            criterion_text="test",
            review_status="SUGGESTED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-04.1",
            source_document_id=doc_id,
            source_page=1,
            source_excerpt="test",
        )
        db.add(criterion)
        db.commit()

        before = (
            db.execute(select(TenderEvaluationModel.id).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            db.execute(select(EvaluationCriterion.id).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
        )
    finally:
        db.close()

    _analyze_semantics(tender_id)

    db = SessionLocal()
    try:
        after = (
            db.execute(select(TenderEvaluationModel.id).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            db.execute(select(EvaluationCriterion.id).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
        )
    finally:
        db.close()

    assert before == after
