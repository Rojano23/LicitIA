from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    EvaluationCriterion,
    EvaluationCriterionEvidence,
    NormalizedContent,
    Requirement,
    RequirementCandidate,
    RequirementCandidateEvidence,
    RequirementCandidateLink,
    TenderDocument,
    TenderEvaluationModel,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "REQ-NORM-001",
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


def _get_requirements(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/requirements")
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot_candidate(candidate_id: str) -> tuple[str, str | None, str | None, str, str, str]:
    db = SessionLocal()
    try:
        row = db.get(RequirementCandidate, candidate_id)
        assert row is not None
        return (
            row.requirement_text,
            row.actor_text,
            row.modality_text,
            row.semantic_key,
            row.review_status,
            row.detector_version,
        )
    finally:
        db.close()


def test_one_candidate_becomes_one_requirement() -> None:
    tender_id = _create_tender("REQ-NORM one to one")
    doc_id = _import_pdf(tender_id, "one.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar Anexo D firmado.")
    _seed_candidate(tender_id, doc_id, page_id, norm_id, "El participante deberá presentar Anexo D firmado.")

    payload = _normalize(tender_id)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["requirement_count"] == 1
    assert payload["summary"]["single_source_requirement_count"] == 1


def test_identical_candidates_cross_document_merge_into_single_requirement() -> None:
    tender_id = _create_tender("REQ-NORM merge identical")
    doc_a = _import_pdf(tender_id, "bases.pdf")
    doc_b = _import_pdf(tender_id, "anexos.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, "El participante deberá presentar el Anexo D debidamente firmado.")
    page_b, norm_b = _seed_page_and_normalized(doc_b, 2, "El participante deberá presentar el Anexo D debidamente firmado.")
    _seed_candidate(tender_id, doc_a, page_a, norm_a, "El participante deberá presentar el Anexo D debidamente firmado.", source_page=1)
    _seed_candidate(tender_id, doc_b, page_b, norm_b, "El participante deberá presentar el Anexo D debidamente firmado.", source_page=2)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 1
    assert payload["summary"]["merged_requirement_count"] == 1
    assert payload["requirements"][0]["source_occurrence_count"] == 2


def test_repeated_normalization_is_idempotent() -> None:
    tender_id = _create_tender("REQ-NORM idempotent")
    doc_id = _import_pdf(tender_id, "idem.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "La propuesta deberá presentarse en idioma español.")
    _seed_candidate(tender_id, doc_id, page_id, norm_id, "La propuesta deberá presentarse en idioma español.", actor_text="La propuesta")

    first = _normalize(tender_id)
    second = _normalize(tender_id)

    assert first["summary"]["requirement_count"] == second["summary"]["requirement_count"] == 1
    assert first["requirements"][0]["canonical_key"] == second["requirements"][0]["canonical_key"]

    db = SessionLocal()
    try:
        count = db.execute(select(Requirement).where(Requirement.tender_id == tender_id)).scalars().all()
        links = db.execute(
            select(RequirementCandidateLink)
            .join(Requirement, Requirement.id == RequirementCandidateLink.requirement_id)
            .where(Requirement.tender_id == tender_id)
        ).scalars().all()
        assert len(count) == 1
        assert len(links) == 1
    finally:
        db.close()


def test_candidate_rows_are_immutable_after_normalization() -> None:
    tender_id = _create_tender("REQ-NORM immutable candidates")
    doc_id = _import_pdf(tender_id, "immutable.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar carta de respaldo del fabricante.")
    candidate_id = _seed_candidate(
        tender_id,
        doc_id,
        page_id,
        norm_id,
        "El participante deberá presentar carta de respaldo del fabricante.",
    )
    before = _snapshot_candidate(candidate_id)

    _normalize(tender_id)
    after = _snapshot_candidate(candidate_id)

    assert before == after


def test_merge_anexo_d_variants() -> None:
    tender_id = _create_tender("REQ-NORM merge anexo")
    doc_a = _import_pdf(tender_id, "a.pdf")
    doc_b = _import_pdf(tender_id, "b.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, "El participante deberá presentar el Anexo D debidamente firmado.")
    page_b, norm_b = _seed_page_and_normalized(doc_b, 1, "Presentar Anexo D firmado.")
    _seed_candidate(tender_id, doc_a, page_a, norm_a, "El participante deberá presentar el Anexo D debidamente firmado.")
    _seed_candidate(tender_id, doc_b, page_b, norm_b, "Presentar Anexo D firmado.", actor_text=None, modality_text="Presentar")

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 1
    assert payload["summary"]["merged_requirement_count"] == 1


def test_does_not_merge_iso_with_manufacturer_support_letter() -> None:
    tender_id = _create_tender("REQ-NORM no merge iso respaldo")
    doc_id = _import_pdf(tender_id, "tech.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar certificado ISO 9001 vigente.")
    page_b, norm_b = _seed_page_and_normalized(doc_id, 2, "El participante deberá presentar carta de respaldo del fabricante.")
    _seed_candidate(tender_id, doc_id, page_a, norm_a, "El participante deberá presentar certificado ISO 9001 vigente.", source_page=1)
    _seed_candidate(tender_id, doc_id, page_b, norm_b, "El participante deberá presentar carta de respaldo del fabricante.", source_page=2)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 2


def test_does_not_merge_numeric_mismatch() -> None:
    tender_id = _create_tender("REQ-NORM no merge numeric")
    doc_id = _import_pdf(tender_id, "exp.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_id, 1, "El participante deberá acreditar 2 servicios similares.")
    page_b, norm_b = _seed_page_and_normalized(doc_id, 2, "El participante deberá acreditar 5 servicios similares.")
    _seed_candidate(tender_id, doc_id, page_a, norm_a, "El participante deberá acreditar 2 servicios similares.", source_page=1)
    _seed_candidate(tender_id, doc_id, page_b, norm_b, "El participante deberá acreditar 5 servicios similares.", source_page=2)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 2


def test_does_not_merge_qualification_mismatch() -> None:
    tender_id = _create_tender("REQ-NORM no merge qualifier")
    doc_id = _import_pdf(tender_id, "qualifier.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar certificado vigente.")
    page_b, norm_b = _seed_page_and_normalized(doc_id, 2, "El participante deberá presentar certificado emitido en los últimos 30 días.")
    _seed_candidate(tender_id, doc_id, page_a, norm_a, "El participante deberá presentar certificado vigente.", source_page=1)
    _seed_candidate(tender_id, doc_id, page_b, norm_b, "El participante deberá presentar certificado emitido en los últimos 30 días.", source_page=2)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 2


def test_does_not_merge_consortium_condition_with_unconditional() -> None:
    tender_id = _create_tender("REQ-NORM no merge condition")
    doc_id = _import_pdf(tender_id, "consorcio.pdf")
    page_a, norm_a = _seed_page_and_normalized(doc_id, 1, "En caso de consorcio, cada integrante deberá presentar constancia fiscal.")
    page_b, norm_b = _seed_page_and_normalized(doc_id, 2, "El participante deberá presentar constancia fiscal.")
    _seed_candidate(tender_id, doc_id, page_a, norm_a, "En caso de consorcio, cada integrante deberá presentar constancia fiscal.", actor_text="consorcio", source_page=1)
    _seed_candidate(tender_id, doc_id, page_b, norm_b, "El participante deberá presentar constancia fiscal.", actor_text="participante", source_page=2)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 2


def test_category_detection_core_cases() -> None:
    tender_id = _create_tender("REQ-NORM categories")
    doc_id = _import_pdf(tender_id, "categories.pdf")

    fixtures = [
        ("El participante deberá incluir curriculum vitae y cédula profesional.", "PERSONNEL"),
        ("El participante deberá acreditar al menos 2 servicios similares ejecutados.", "EXPERIENCE"),
        ("La propuesta económica incluirá los precios unitarios ofertados.", "ECONOMIC"),
        ("La propuesta deberá presentarse en idioma español y en formato PDF.", "INSTRUCTIONS"),
        ("El interesado deberá contar con certificado de registro en la plataforma.", "REGISTRATION"),
        ("El representante legal deberá presentar poder notarial para suscribir contratos.", "LEGAL"),
        ("El participante deberá presentar certificado de calidad ISO 9001 vigente.", "TECHNICAL"),
        ("El participante deberá cumplir lo indicado.", "UNKNOWN"),
    ]

    for idx, (text, _) in enumerate(fixtures, start=1):
        page_id, norm_id = _seed_page_and_normalized(doc_id, idx, text)
        _seed_candidate(tender_id, doc_id, page_id, norm_id, text, source_page=idx)

    payload = _normalize(tender_id)
    categories = {item["canonical_text"]: item["category"] for item in payload["requirements"]}

    for text, expected_category in fixtures:
        assert categories[text] == expected_category


def test_primary_source_prefers_clean_candidate_over_ocr_noise() -> None:
    tender_id = _create_tender("REQ-NORM primary source")
    doc_a = _import_pdf(tender_id, "clean.pdf")
    doc_b = _import_pdf(tender_id, "ocr.pdf")
    clean_text = "El participante deberá presentar carta de respaldo del fabricante."
    noisy_text = "we El participante deberá presentar carta de respaldo del fabricante"
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, clean_text)
    page_b, norm_b = _seed_page_and_normalized(doc_b, 1, noisy_text)
    clean_id = _seed_candidate(tender_id, doc_a, page_a, norm_a, clean_text)
    _seed_candidate(tender_id, doc_b, page_b, norm_b, noisy_text)

    payload = _normalize(tender_id)

    assert payload["summary"]["requirement_count"] == 1
    assert payload["requirements"][0]["primary_source"]["candidate_id"] == clean_id


def test_primary_source_is_deterministic() -> None:
    tender_id = _create_tender("REQ-NORM deterministic primary")
    doc_a = _import_pdf(tender_id, "a1.pdf")
    doc_b = _import_pdf(tender_id, "a2.pdf")
    text = "El participante deberá presentar el Anexo D debidamente firmado."
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, text)
    page_b, norm_b = _seed_page_and_normalized(doc_b, 1, text)
    _seed_candidate(tender_id, doc_a, page_a, norm_a, text)
    _seed_candidate(tender_id, doc_b, page_b, norm_b, text)

    first = _normalize(tender_id)
    second = _normalize(tender_id)

    assert first["requirements"][0]["primary_source"]["candidate_id"] == second["requirements"][0]["primary_source"]["candidate_id"]


def test_requirement_provenance_links_all_occurrences() -> None:
    tender_id = _create_tender("REQ-NORM provenance")
    doc_a = _import_pdf(tender_id, "src-a.pdf")
    doc_b = _import_pdf(tender_id, "src-b.pdf")
    text = "El participante deberá presentar constancia de situación fiscal."
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, text)
    page_b, norm_b = _seed_page_and_normalized(doc_b, 2, text)
    _seed_candidate(tender_id, doc_a, page_a, norm_a, text, source_page=1)
    _seed_candidate(tender_id, doc_b, page_b, norm_b, text, source_page=2)

    payload = _normalize(tender_id)

    requirement = payload["requirements"][0]
    assert requirement["source_occurrence_count"] == 2
    assert len(requirement["candidates"]) == 2
    assert all(item["source_excerpt"] for item in requirement["candidates"])


def test_stale_reconciliation_updates_links_and_removes_orphans() -> None:
    tender_id = _create_tender("REQ-NORM stale")
    doc_a = _import_pdf(tender_id, "s-a.pdf")
    doc_b = _import_pdf(tender_id, "s-b.pdf")
    text = "El participante deberá presentar Anexo D firmado."
    page_a, norm_a = _seed_page_and_normalized(doc_a, 1, text)
    page_b, norm_b = _seed_page_and_normalized(doc_b, 1, text)
    candidate_a = _seed_candidate(tender_id, doc_a, page_a, norm_a, text)
    candidate_b = _seed_candidate(tender_id, doc_b, page_b, norm_b, text)

    first = _normalize(tender_id)
    assert first["summary"]["requirement_count"] == 1
    assert first["requirements"][0]["source_occurrence_count"] == 2

    db = SessionLocal()
    try:
        row = db.get(RequirementCandidate, candidate_b)
        assert row is not None
        db.delete(row)
        db.commit()
    finally:
        db.close()

    second = _normalize(tender_id)
    assert second["summary"]["requirement_count"] == 1
    assert second["requirements"][0]["source_occurrence_count"] == 1
    assert second["requirements"][0]["candidates"][0]["candidate_id"] == candidate_a


def test_closed_domain_rows_are_unchanged_by_normalization() -> None:
    tender_id = _create_tender("REQ-NORM closed domains")
    doc_id = _import_pdf(tender_id, "domains.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar documento legal.")
    _seed_candidate(tender_id, doc_id, page_id, norm_id, "El participante deberá presentar documento legal.")

    db = SessionLocal()
    try:
        classification = DocumentClassification(
            document_id=doc_id,
            suggested_type="GOVERNING",
            suggested_score=80,
            classification_status="CONFIRMED",
            classifier_method="RULE_BASED_GENERIC",
            classifier_version="mvp-02.4.2",
            input_fingerprint_sha256="hash",
            is_composite=False,
        )
        db.add(classification)
        db.flush()

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
        db.flush()

        evidence = EvaluationCriterionEvidence(
            criterion_id=criterion.id,
            source_document_id=doc_id,
            source_page=1,
            source_excerpt="test",
            excerpt_sha256=hashlib.sha256(b"test").hexdigest(),
            evidence_role="OTHER",
        )
        db.add(evidence)
        db.commit()

        before = (
            db.execute(select(TenderEvaluationModel.id).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            db.execute(select(EvaluationCriterion.id).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
            db.execute(select(DocumentClassification.id).where(DocumentClassification.document_id == doc_id)).scalar_one(),
        )
    finally:
        db.close()

    _normalize(tender_id)

    db = SessionLocal()
    try:
        after = (
            db.execute(select(TenderEvaluationModel.id).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            db.execute(select(EvaluationCriterion.id).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
            db.execute(select(DocumentClassification.id).where(DocumentClassification.document_id == doc_id)).scalar_one(),
        )
    finally:
        db.close()

    assert before == after


def test_get_requirements_endpoint_returns_empty_when_not_normalized() -> None:
    tender_id = _create_tender("REQ-NORM empty get")

    payload = _get_requirements(tender_id)

    assert payload["summary"]["candidate_count"] == 0
    assert payload["summary"]["requirement_count"] == 0
    assert payload["requirements"] == []


def test_clear_iso_requirement_is_normalized() -> None:
    tender_id = _create_tender("REQ-NORM sufficiency clear iso")
    doc_id = _import_pdf(tender_id, "iso-clear.pdf")
    text = "El participante deberá presentar su certificado ISO 9001 vigente."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "TECHNICAL"
    assert item["normalization_status"] == "NORMALIZED"


def test_clipped_iso_requirement_is_review_required() -> None:
    tender_id = _create_tender("REQ-NORM sufficiency clipped iso")
    doc_id = _import_pdf(tender_id, "iso-clipped.pdf")
    text = "we El participante deberá presentar su certificado ISO 9001:2015 el cual"
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "TECHNICAL"
    assert item["normalization_status"] == "REVIEW_REQUIRED"


def test_referent_without_antecedent_is_review_required() -> None:
    tender_id = _create_tender("REQ-NORM referent missing")
    doc_id = _import_pdf(tender_id, "referent-missing.pdf")
    text = "dicha documentación deberá integrarse como parte de la propuesta."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text="La propuesta")

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["normalization_status"] == "REVIEW_REQUIRED"


def test_referent_with_local_antecedent_can_normalize() -> None:
    tender_id = _create_tender("REQ-NORM referent with antecedent")
    doc_id = _import_pdf(tender_id, "referent-ok.pdf")
    text = "Formato DA-2. El participante deberá presentar el presente documento debidamente firmado en PDF."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "INSTRUCTIONS"
    assert item["normalization_status"] == "NORMALIZED"


def test_sat_truncated_sentence_is_review_required() -> None:
    tender_id = _create_tender("REQ-NORM sat truncation")
    doc_id = _import_pdf(tender_id, "sat-truncated.pdf")
    text = "DEL SERVICIO DE ADMINISTRACIÓN TRIBUTARIA PARTICIPEN, DEBERÁN PRESENTAR EL PRESENTE DOCUMENTO COMO PARTE DE LA PROPUESTA."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text=None)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "INSTRUCTIONS"
    assert item["normalization_status"] == "REVIEW_REQUIRED"


def test_procedural_event_words_do_not_force_technical_category() -> None:
    tender_id = _create_tender("REQ-NORM procedural event guard")
    doc_id = _import_pdf(tender_id, "event-guard.pdf")
    text = (
        "dicha documentación deberá integrarse como parte de la propuesta, "
        "antes de la Presentación y Apertura de Propuestas Comercial, Técnica y Económica."
    )
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text="La propuesta")

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] in {"INSTRUCTIONS", "UNKNOWN"}
    assert item["category"] != "TECHNICAL"


def test_technical_category_when_substantive_technical_object_exists() -> None:
    tender_id = _create_tender("REQ-NORM technical substantive")
    doc_id = _import_pdf(tender_id, "technical-object.pdf")
    text = "El participante deberá integrar su propuesta técnica con el certificado de calidad requerido."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "TECHNICAL"


def test_economic_category_for_unit_prices() -> None:
    tender_id = _create_tender("REQ-NORM economic prices")
    doc_id = _import_pdf(tender_id, "economic.pdf")
    text = "Propuesta económica deberá incluir precios unitarios."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text="La propuesta")

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "ECONOMIC"


def test_instructions_category_for_pdf_format() -> None:
    tender_id = _create_tender("REQ-NORM instructions pdf")
    doc_id = _import_pdf(tender_id, "pdf-format.pdf")
    text = "La documentación deberá presentarse en PDF."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text="La documentación")

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "INSTRUCTIONS"


def test_instructions_category_for_spanish_language() -> None:
    tender_id = _create_tender("REQ-NORM instructions language")
    doc_id = _import_pdf(tender_id, "spanish-language.pdf")
    text = "La propuesta deberá estar en idioma español."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text, actor_text="La propuesta")

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "INSTRUCTIONS"


def test_documents_before_mentioned_without_antecedent_is_review_required() -> None:
    tender_id = _create_tender("REQ-NORM referent before mentioned")
    doc_id = _import_pdf(tender_id, "before-mentioned.pdf")
    text = "Los documentos antes mencionados deberán presentarse en original."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["normalization_status"] == "REVIEW_REQUIRED"


def test_known_category_does_not_imply_normalized() -> None:
    tender_id = _create_tender("REQ-NORM known category review")
    doc_id = _import_pdf(tender_id, "known-category-review.pdf")
    text = "we El personal del participante deberá presentar certificado ISO 9001 el cual"
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "TECHNICAL"
    assert item["normalization_status"] == "REVIEW_REQUIRED"


def test_unknown_category_is_review_required() -> None:
    tender_id = _create_tender("REQ-NORM unknown review")
    doc_id = _import_pdf(tender_id, "unknown-review.pdf")
    text = "Se atenderá lo aplicable conforme a lo señalado anteriormente."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, text)
    _seed_candidate(tender_id, doc_id, page_id, norm_id, text)

    payload = _normalize(tender_id)
    item = payload["requirements"][0]

    assert item["category"] == "UNKNOWN"
    assert item["normalization_status"] == "REVIEW_REQUIRED"
