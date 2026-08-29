from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    NormalizedContent,
    RequirementCandidate,
    TenderChange,
    TenderDocument,
    TenderEvaluationModel,
    TenderEvent,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "REQ-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str, *, suffix: str = "") -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}{suffix}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page_and_normalized(document_id: str, page_number: int, text: str, *, source_type: str = "NATIVE_PDF") -> tuple[str, str]:
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

        norm = NormalizedContent(
            document_page_id=page.id,
            source_type=source_type,
            source_scope="NATIVE_PAGE" if source_type == "NATIVE_PDF" else "OCR_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page.id}-{source_type}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(norm)
        db.commit()
        return page.id, norm.id
    finally:
        db.close()


def _add_normalized_source(page_id: str, text: str, *, source_type: str) -> str:
    db = SessionLocal()
    try:
        norm = NormalizedContent(
            document_page_id=page_id,
            source_type=source_type,
            source_scope="NATIVE_PAGE" if source_type == "NATIVE_PDF" else "OCR_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"extra-{page_id}-{source_type}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(norm)
        db.commit()
        return norm.id
    finally:
        db.close()


def _set_document_classification(document_id: str, suggested_type: str, *, human_type: str | None = None) -> None:
    db = SessionLocal()
    try:
        classification = DocumentClassification(
            document_id=document_id,
            suggested_type=suggested_type,
            suggested_score=80,
            classification_status="CONFIRMED",
            classifier_method="RULE_BASED_GENERIC",
            classifier_version="mvp-02.4.2",
            input_fingerprint_sha256=hashlib.sha256(f"class-{document_id}-{suggested_type}".encode("utf-8")).hexdigest(),
            is_composite=False,
            human_type=human_type,
        )
        db.add(classification)
        db.commit()
    finally:
        db.close()


def _update_normalized(document_id: str, new_text: str) -> None:
    db = SessionLocal()
    try:
        pages = db.execute(select(DocumentPage).where(DocumentPage.document_id == document_id)).scalars().all()
        assert pages
        page_ids = [page.id for page in pages]
        norms = db.execute(select(NormalizedContent).where(NormalizedContent.document_page_id.in_(page_ids))).scalars().all()
        assert norms
        for norm in norms:
            norm.normalized_text = new_text
            norm.char_count = len(new_text)
            norm.content_sha256 = hashlib.sha256(f"updated-{norm.id}-{new_text}".encode("utf-8")).hexdigest()
        db.commit()
    finally:
        db.close()


def _analyze(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-requirements")
    assert response.status_code == 200, response.text
    return response.json()


def _get_candidates(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/requirement-candidates")
    assert response.status_code == 200, response.text
    return response.json()


def _seed_closed_domain_rows(tender_id: str, source_doc_id: str, page_id: str, target_doc_id: str) -> dict:
    db = SessionLocal()
    try:
        analysis = DocumentReferenceAnalysis(
            document_id=source_doc_id,
            status="COMPLETED",
            extractor_version="mvp-02.5.1",
            input_fingerprint_sha256="ref-req",
        )
        db.add(analysis)
        db.flush()

        reference = DocumentReference(
            analysis_id=analysis.id,
            source_document_id=source_doc_id,
            document_page_id=page_id,
            reference_identity_key=hashlib.sha256(f"ref-{tender_id}".encode("utf-8")).hexdigest(),
            raw_reference_text="ANEXO D",
            normalized_reference_key="ANEXO:D",
            reference_kind="ANNEX",
            relationship_hint="REFERENCES",
            resolution_status="UNRESOLVED",
            excerpt="Referencia de prueba",
            extractor_version="mvp-02.5.1",
        )
        db.add(reference)

        relationship = DocumentRelationship(
            tender_id=tender_id,
            source_document_id=source_doc_id,
            target_document_id=target_doc_id,
            relationship_type="REFERENCES",
            relationship_origin="REFERENCE_ENGINE",
        )
        db.add(relationship)

        event = TenderEvent(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"evt-{tender_id}".encode("utf-8")).hexdigest(),
            event_type="CLARIFICATION_MEETING",
            title="Junta",
            review_status="SUGGESTED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.2",
            source_document_id=source_doc_id,
            source_page=1,
            source_excerpt="Evento prueba",
        )
        db.add(event)

        change = TenderChange(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"chg-{tender_id}".encode("utf-8")).hexdigest(),
            change_type="UNKNOWN",
            source_document_id=source_doc_id,
            source_page=1,
            source_excerpt="Cambio prueba",
            review_status="SUGGESTED",
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.3",
        )
        db.add(change)
        db.commit()

        return {
            "reference": (reference.resolution_status, reference.resolved_target_document_id, reference.human_decision),
            "relationship": (relationship.relationship_type, relationship.source_document_id, relationship.target_document_id),
            "event": (event.review_status, event.event_type, event.source_document_id),
            "change": (change.review_status, change.change_type, change.source_document_id),
        }
    finally:
        db.close()


def _snapshot_closed_domain_rows(tender_id: str, source_doc_id: str) -> dict:
    db = SessionLocal()
    try:
        reference = db.execute(
            select(DocumentReference.resolution_status, DocumentReference.resolved_target_document_id, DocumentReference.human_decision)
            .where(DocumentReference.source_document_id == source_doc_id)
        ).first()
        relationship = db.execute(
            select(DocumentRelationship.relationship_type, DocumentRelationship.source_document_id, DocumentRelationship.target_document_id)
            .where(DocumentRelationship.tender_id == tender_id)
        ).first()
        event = db.execute(
            select(TenderEvent.review_status, TenderEvent.event_type, TenderEvent.source_document_id)
            .where(TenderEvent.tender_id == tender_id)
        ).first()
        change = db.execute(
            select(TenderChange.review_status, TenderChange.change_type, TenderChange.source_document_id)
            .where(TenderChange.tender_id == tender_id)
        ).first()
        evaluation_model = db.execute(select(TenderEvaluationModel.id).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one_or_none()
        return {
            "reference": reference,
            "relationship": relationship,
            "event": event,
            "change": change,
            "evaluation_model": evaluation_model,
        }
    finally:
        db.close()


def test_get_requirement_candidates_returns_empty_before_analysis() -> None:
    tender_id = _create_tender("Req empty")

    payload = _get_candidates(tender_id)

    assert payload["requirements_version"] == "mvp-04.2"
    assert payload["summary"]["total"] == 0
    assert payload["candidates"] == []


def test_detects_explicit_bidder_obligation() -> None:
    tender_id = _create_tender("Req explicit bidder")
    doc_id = _import_pdf(tender_id, "bases.pdf")
    _seed_page_and_normalized(doc_id, 1, "El LICITANTE debera presentar opinion de cumplimiento fiscal vigente.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    candidate = payload["candidates"][0]
    assert candidate["actor_text"].lower().endswith("licitante")
    assert candidate["modality_text"].lower() == "debera"
    assert "opinion de cumplimiento fiscal vigente" in candidate["requirement_text"].lower()


def test_detects_proposal_obligation_and_preserves_excerpt() -> None:
    tender_id = _create_tender("Req proposal")
    doc_id = _import_pdf(tender_id, "tecnica.pdf")
    text = "La PROPOSICION TECNICA debera incluir carta firmada por el representante legal."
    page_id, norm_id = _seed_page_and_normalized(doc_id, 2, text)

    payload = _analyze(tender_id)

    candidate = payload["candidates"][0]
    assert candidate["source_page"] == 2
    assert candidate["document_page_id"] == page_id
    assert candidate["normalized_content_id"] == norm_id
    assert candidate["source_excerpt"] == text
    assert candidate["evidence"][0]["source_excerpt"] == text


def test_detects_impersonal_requirement_when_bidder_context_is_present() -> None:
    tender_id = _create_tender("Req impersonal")
    doc_id = _import_pdf(tender_id, "administrativa.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Para integrar la propuesta administrativa, se requiere presentar la constancia de situacion fiscal vigente.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert payload["candidates"][0]["modality_text"].lower() == "se requiere"


def test_detects_rejection_cause_as_requirement_candidate() -> None:
    tender_id = _create_tender("Req rejection")
    doc_id = _import_pdf(tender_id, "motivos.pdf")
    _seed_page_and_normalized(doc_id, 1, "La falta de firma autografa sera causa de desechamiento.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "causa de desechamiento" in payload["candidates"][0]["modality_text"].lower()


def test_rejects_authority_obligations() -> None:
    tender_id = _create_tender("Req authority")
    doc_id = _import_pdf(tender_id, "contrato.pdf")
    _seed_page_and_normalized(doc_id, 1, "El area contratante debera conservar los originales del expediente.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_rejects_post_award_execution_obligations() -> None:
    tender_id = _create_tender("Req post award")
    doc_id = _import_pdf(tender_id, "modelo-contrato.pdf")
    _set_document_classification(doc_id, "CONTRACT_DRAFT")
    _seed_page_and_normalized(doc_id, 1, "El proveedor adjudicado debera entregar reportes mensuales durante la ejecucion del contrato.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_keeps_pre_award_bidder_conditions_even_if_they_reference_future_award() -> None:
    tender_id = _create_tender("Req future award")
    doc_id = _import_pdf(tender_id, "experiencia.pdf")
    _seed_page_and_normalized(doc_id, 1, "El participante debera acreditar que, en caso de resultar adjudicado, contara con personal tecnico certificado.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "personal tecnico certificado" in payload["candidates"][0]["requirement_text"].lower()


def test_ignores_reference_only_headings_and_template_placeholders() -> None:
    tender_id = _create_tender("Req noise")
    doc_id = _import_pdf(tender_id, "anexos.pdf")
    _seed_page_and_normalized(doc_id, 1, "Documentacion requerida\n\nVease Anexo D para requisitos tecnicos.\n\n[Especificar documento aqui]")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_same_text_in_different_documents_produces_distinct_candidates() -> None:
    tender_id = _create_tender("Req separate docs")
    doc_a = _import_pdf(tender_id, "bases-a.pdf")
    doc_b = _import_pdf(tender_id, "bases-b.pdf")
    text = "El licitante debera presentar escrito libre bajo protesta de decir verdad."
    _seed_page_and_normalized(doc_a, 1, text)
    _seed_page_and_normalized(doc_b, 1, text)

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 2
    assert len({item["source_document_id"] for item in payload["candidates"]}) == 2


def test_deduplicates_duplicate_normalized_sources_from_same_page() -> None:
    tender_id = _create_tender("Req dedup normalized")
    doc_id = _import_pdf(tender_id, "dual-source.pdf")
    text = "El licitante debera anexar identificacion oficial vigente."
    page_id, _ = _seed_page_and_normalized(doc_id, 1, text, source_type="NATIVE_PDF")
    _add_normalized_source(page_id, text, source_type="OCR")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert len(payload["candidates"][0]["evidence"]) == 1


def test_reconciles_stale_suggested_candidates() -> None:
    tender_id = _create_tender("Req stale")
    doc_id = _import_pdf(tender_id, "stale.pdf")
    _seed_page_and_normalized(doc_id, 1, "El licitante debera presentar registro patronal vigente.")

    first = _analyze(tender_id)
    assert first["summary"]["total"] == 1

    _update_normalized(doc_id, "Texto narrativo sin obligaciones para el participante.")
    second = _analyze(tender_id)

    assert second["summary"]["total"] == 0


def test_preserves_confirmed_candidates_that_disappear_from_detector() -> None:
    tender_id = _create_tender("Req preserve confirmed")
    doc_id = _import_pdf(tender_id, "confirmed.pdf")
    page_id, norm_id = _seed_page_and_normalized(doc_id, 1, "El licitante debera presentar catalogo de conceptos firmado.")
    payload = _analyze(tender_id)
    candidate_id = payload["candidates"][0]["id"]

    db = SessionLocal()
    try:
        candidate = db.get(RequirementCandidate, candidate_id)
        assert candidate is not None
        candidate.review_status = "CONFIRMED"
        db.commit()
    finally:
        db.close()

    _update_normalized(doc_id, "Contenido sustituido sin requerimiento verificable.")
    refreshed = _analyze(tender_id)

    assert refreshed["summary"]["total"] == 1
    assert refreshed["candidates"][0]["review_status"] == "CONFIRMED"
    assert refreshed["candidates"][0]["document_page_id"] == page_id
    assert refreshed["candidates"][0]["normalized_content_id"] == norm_id


def test_keeps_compound_list_as_single_stable_candidate() -> None:
    tender_id = _create_tender("Req compound")
    doc_id = _import_pdf(tender_id, "lista.pdf")
    _seed_page_and_normalized(doc_id, 1, "El licitante debera presentar RFC, CURP y comprobante de domicilio vigente.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "rfc, curp y comprobante de domicilio vigente" in payload["candidates"][0]["requirement_text"].lower()


def test_analyze_requirements_does_not_mutate_closed_domains_or_evaluation() -> None:
    tender_id = _create_tender("Req isolation")
    source_doc_id = _import_pdf(tender_id, "source.pdf")
    target_doc_id = _import_pdf(tender_id, "target.pdf")
    page_id, _ = _seed_page_and_normalized(source_doc_id, 1, "El licitante debera presentar garantia de seriedad.")
    _seed_page_and_normalized(target_doc_id, 1, "Texto sin uso.")
    before = _seed_closed_domain_rows(tender_id, source_doc_id, page_id, target_doc_id)

    payload = _analyze(tender_id)
    after = _snapshot_closed_domain_rows(tender_id, source_doc_id)

    assert payload["summary"]["total"] == 1
    assert before["reference"] == after["reference"]
    assert before["relationship"] == after["relationship"]
    assert before["event"] == after["event"]
    assert before["change"] == after["change"]
    assert after["evaluation_model"] is None


def test_summary_reports_modality_and_actor_counts() -> None:
    tender_id = _create_tender("Req summary")
    doc_id = _import_pdf(tender_id, "summary.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "El licitante debera presentar curriculum del personal clave. La proposicion tecnica debera incluir metodologia de trabajo.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 2
    assert payload["summary"]["explicit_actor_count"] == 2
    assert payload["summary"]["by_modality"]["debera"] == 2


def test_placeholder_form_field_alone_is_not_candidate() -> None:
    tender_id = _create_tender("Req placeholder only")
    doc_id = _import_pdf(tender_id, "placeholder.pdf")
    _seed_page_and_normalized(doc_id, 1, "Nombre del participante: [Escriba aqui]\nDomicilio: [Campo en blanco]")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_first_person_template_declaration_alone_is_not_candidate() -> None:
    tender_id = _create_tender("Req first person declaration")
    doc_id = _import_pdf(tender_id, "declaration.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "(En papel membretado del participante)\nDeclaro bajo protesta de decir verdad que mi representada no se encuentra inhabilitada.\nProtesto lo necesario.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_form_submission_instruction_is_candidate() -> None:
    tender_id = _create_tender("Req form submission")
    doc_id = _import_pdf(tender_id, "formato.pdf")
    _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar el formato DC-2 debidamente firmado.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "formato dc-2" in payload["candidates"][0]["requirement_text"].lower()


def test_template_content_plus_submission_instruction_keeps_only_submission_instruction() -> None:
    tender_id = _create_tender("Req external instruction only")
    doc_id = _import_pdf(tender_id, "template-plus-instruction.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "El participante deberá presentar el formato DC-2 debidamente firmado.\n\nSi el PARTICIPANTE es persona moral, deberá incluir la siguiente manifestación:\nManifiesto bajo protesta de decir verdad que no me encuentro inhabilitado.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "presentar el formato dc-2 debidamente firmado" in payload["candidates"][0]["requirement_text"].lower()


def test_repeated_template_text_from_same_page_is_not_duplicated() -> None:
    tender_id = _create_tender("Req repeated template")
    doc_id = _import_pdf(tender_id, "template-dup.pdf")
    page_id, _ = _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar el formato DC-2 debidamente firmado.", source_type="NATIVE_PDF")
    _add_normalized_source(page_id, "El participante deberá presentar el formato DC-2 debidamente firmado.", source_type="OCR")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1


def test_rejects_contractor_execution_obligation() -> None:
    tender_id = _create_tender("Req contractor execution")
    doc_id = _import_pdf(tender_id, "contractor.pdf")
    _seed_page_and_normalized(doc_id, 1, "El contratista deberá iniciar los trabajos dentro de cinco días posteriores a la firma del contrato.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_rejects_award_guarantee_after_fallo() -> None:
    tender_id = _create_tender("Req award guarantee")
    doc_id = _import_pdf(tender_id, "garantia.pdf")
    _seed_page_and_normalized(doc_id, 1, "El adjudicatario deberá presentar la garantía después del fallo.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_keeps_proposal_stage_commitment_for_future_guarantee() -> None:
    tender_id = _create_tender("Req future guarantee commitment")
    doc_id = _import_pdf(tender_id, "future-guarantee.pdf")
    _seed_page_and_normalized(doc_id, 1, "El participante deberá presentar con su propuesta compromiso de constituir la garantía en caso de adjudicación.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "compromiso de constituir la garantía" in payload["candidates"][0]["requirement_text"].lower()


def test_rejects_authority_fallo_obligation() -> None:
    tender_id = _create_tender("Req authority fallo")
    doc_id = _import_pdf(tender_id, "fallo.pdf")
    _seed_page_and_normalized(doc_id, 1, "El Área Contratante deberá emitir el fallo.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_rejects_authority_optional_clarification() -> None:
    tender_id = _create_tender("Req authority clarification")
    doc_id = _import_pdf(tender_id, "clarification.pdf")
    _seed_page_and_normalized(doc_id, 1, "La convocante podrá solicitar aclaraciones.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_rejects_committee_evaluation_statement() -> None:
    tender_id = _create_tender("Req committee evaluation")
    doc_id = _import_pdf(tender_id, "committee.pdf")
    _seed_page_and_normalized(doc_id, 1, "El comité evaluará las propuestas.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_narrative_acreditar_phrase_without_instruction_context_is_not_candidate() -> None:
    tender_id = _create_tender("Req narrative acreditar")
    doc_id = _import_pdf(tender_id, "narrative.pdf")
    _seed_page_and_normalized(doc_id, 1, "Para acreditar lo anterior, la convocante revisará la documentación existente.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_checklist_row_under_explicit_bidder_heading_is_candidate() -> None:
    tender_id = _create_tender("Req checklist row")
    doc_id = _import_pdf(tender_id, "checklist.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Documentos que deberá presentar el participante:\nPresentar Anexo D firmado.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert payload["candidates"][0]["modality_text"].lower() == "presentar"


def test_reference_only_annex_text_is_not_candidate() -> None:
    tender_id = _create_tender("Req annex reference only")
    doc_id = _import_pdf(tender_id, "annex-reference.pdf")
    _seed_page_and_normalized(doc_id, 1, "Conforme al Anexo D, se describen las características técnicas.")

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 0


def test_present_annex_signed_in_checklist_is_candidate() -> None:
    tender_id = _create_tender("Req annex submit")
    doc_id = _import_pdf(tender_id, "annex-submit.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Como parte de la propuesta técnica:\nPresentar Anexo D firmado.",
    )

    payload = _analyze(tender_id)

    assert payload["summary"]["total"] == 1
    assert "anexo d firmado" in payload["candidates"][0]["requirement_text"].lower()