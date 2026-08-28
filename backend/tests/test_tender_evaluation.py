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
    TenderChange,
    TenderDocument,
    TenderEvent,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "EVAL-001",
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


def _seed_page_and_normalized(document_id: str, page_number: int, text: str, *, is_current: bool = True) -> str:
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
        doc.is_current = is_current

        norm = NormalizedContent(
            document_page_id=page.id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page.id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(norm)
        db.commit()
        return page.id
    finally:
        db.close()


def _update_normalized(document_id: str, new_text: str) -> None:
    db = SessionLocal()
    try:
        pages = db.execute(select(DocumentPage).where(DocumentPage.document_id == document_id)).scalars().all()
        assert pages
        page_ids = [page.id for page in pages]
        norms = db.execute(
            select(NormalizedContent).where(NormalizedContent.document_page_id.in_(page_ids))
        ).scalars().all()
        assert norms
        for norm in norms:
            norm.normalized_text = new_text
            norm.char_count = len(new_text)
            norm.content_sha256 = hashlib.sha256(f"updated-{norm.id}-{new_text}".encode("utf-8")).hexdigest()
        db.commit()
    finally:
        db.close()


def _analyze(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-evaluation")
    assert response.status_code == 200, response.text
    return response.json()


def _get_eval(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/evaluation")
    assert response.status_code == 200, response.text
    return response.json()


def _seed_closed_domain_rows(tender_id: str, source_doc_id: str, page_id: str, target_doc_id: str) -> dict:
    db = SessionLocal()
    try:
        classification = DocumentClassification(
            document_id=source_doc_id,
            suggested_type="NOTICE",
            suggested_score=70,
            classification_status="CONFIRMED",
            classifier_method="RULE_BASED_GENERIC",
            classifier_version="mvp-02.4.2",
            input_fingerprint_sha256="fp-eval",
            is_composite=False,
            human_type="NOTICE",
        )
        db.add(classification)
        db.flush()

        analysis = DocumentReferenceAnalysis(
            document_id=source_doc_id,
            status="COMPLETED",
            extractor_version="mvp-02.5.1",
            input_fingerprint_sha256="ref-eval",
        )
        db.add(analysis)
        db.flush()

        reference = DocumentReference(
            analysis_id=analysis.id,
            source_document_id=source_doc_id,
            document_page_id=page_id,
            reference_identity_key=hashlib.sha256(f"ref-{tender_id}".encode("utf-8")).hexdigest(),
            raw_reference_text="ANEXO X",
            normalized_reference_key="ANEXO:X",
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
            event_date=None,
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
            "classification": (classification.classification_status, classification.human_type),
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
        classification = db.execute(
            select(DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source_doc_id)
        ).first()
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
        doc = db.get(TenderDocument, source_doc_id)
        assert doc is not None
        return {
            "classification": classification,
            "reference": reference,
            "relationship": relationship,
            "event": event,
            "change": change,
            "doc_current": doc.is_current,
        }
    finally:
        db.close()


def test_detects_binary_compliance_from_explicit_phrase() -> None:
    tender_id = _create_tender("Eval binary")
    doc_id = _import_pdf(tender_id, "rules.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion tecnica sera binaria, cumple/no cumple.")

    payload = _analyze(tender_id)

    assert payload["model"]["effective_method"] == "BINARY_COMPLIANCE"
    assert any(item["criterion_type"] == "PASS_FAIL_RULE" for item in payload["criteria"])


def test_detects_points_percentages_from_explicit_phrase() -> None:
    tender_id = _create_tender("Eval points")
    doc_id = _import_pdf(tender_id, "points.pdf")
    _seed_page_and_normalized(doc_id, 1, "El metodo de evaluacion sera por puntos y porcentajes.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "POINTS_PERCENTAGES"


def test_detects_cost_benefit() -> None:
    tender_id = _create_tender("Eval cost benefit")
    doc_id = _import_pdf(tender_id, "cb.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion economica aplicara metodologia de costo beneficio.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "COST_BENEFIT"


def test_detects_lowest_evaluated_price_award_rule() -> None:
    tender_id = _create_tender("Eval lowest price")
    doc_id = _import_pdf(tender_id, "award.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se adjudicara al licitante solvente que oferte el precio mas bajo.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "LOWEST_EVALUATED_PRICE"
    assert any(item["criterion_type"] == "AWARD_RULE" for item in payload["criteria"])


def test_detects_multistage_or_mixed_when_gate_and_economic_rule_present() -> None:
    tender_id = _create_tender("Eval multistage")
    doc_id = _import_pdf(tender_id, "gate.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Solo se evaluara la propuesta economica de quienes hayan cumplido la evaluacion tecnica. "
        "La adjudicacion sera por menor precio solvente.",
    )

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] in {"MULTI_STAGE", "MIXED"}
    assert any(item["criterion_type"] == "QUALIFICATION_GATE" for item in payload["criteria"])


def test_word_cumplimiento_alone_does_not_infer_binary_model() -> None:
    tender_id = _create_tender("Eval compliance word only")
    doc_id = _import_pdf(tender_id, "word.pdf")
    _seed_page_and_normalized(doc_id, 1, "El cumplimiento contractual sera revisado en terminos generales.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "UNKNOWN"


def test_isolated_percent_value_does_not_infer_points_model() -> None:
    tender_id = _create_tender("Eval isolated percent")
    doc_id = _import_pdf(tender_id, "percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "El incremento anual es de 5% para efectos de ajuste.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "UNKNOWN"


def test_pricing_table_alone_does_not_infer_lowest_price_model() -> None:
    tender_id = _create_tender("Eval pricing table only")
    doc_id = _import_pdf(tender_id, "prices.pdf")
    _seed_page_and_normalized(doc_id, 1, "Concepto A 1000.00, Concepto B 500.00, Total 1500.00")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "UNKNOWN"
    assert payload["criteria_summary"]["total"] == 0


def test_extracts_scoring_component_points() -> None:
    tender_id = _create_tender("Eval scoring component")
    doc_id = _import_pdf(tender_id, "score.pdf")
    _seed_page_and_normalized(doc_id, 1, "Criterio de evaluacion: Experiencia tecnica: 20 puntos.")

    payload = _analyze(tender_id)
    scoring = [item for item in payload["criteria"] if item["criterion_type"] == "SCORING_COMPONENT"]
    assert scoring
    assert scoring[0]["weight_value"] == 20
    assert scoring[0]["weight_unit"] == "POINTS"


def test_extracts_weighting_rules_for_technical_and_economic() -> None:
    tender_id = _create_tender("Eval weighting")
    doc_id = _import_pdf(tender_id, "weight.pdf")
    _seed_page_and_normalized(doc_id, 1, "Evaluacion por puntos y porcentajes: propuesta tecnica 70%, propuesta economica 30%.")

    payload = _analyze(tender_id)
    weighting = [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert len(weighting) == 2
    assert sorted(item["weight_value"] for item in weighting) == [30, 70]


def test_penalty_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative penalty")
    doc_id = _import_pdf(tender_id, "penalty-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se aplicara pena convencional del 5% por atraso.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_penalization_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative penalization")
    doc_id = _import_pdf(tender_id, "penalizacion-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se aplicara una penalizacion equivalente al 10% del monto.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_guarantee_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative guarantee")
    doc_id = _import_pdf(tender_id, "guarantee-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "Garantia equivalente al 10% del monto total.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_advance_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative advance")
    doc_id = _import_pdf(tender_id, "advance-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se otorgara anticipo del 20% conforme al contrato.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_vat_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative vat")
    doc_id = _import_pdf(tender_id, "vat-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "El precio incluye IVA 16%.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_retention_percentage_is_not_weighting_rule() -> None:
    tender_id = _create_tender("Eval weighting negative retention")
    doc_id = _import_pdf(tender_id, "retention-percent.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se aplicara una retencion del 5% al pago mensual.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]


def test_explicit_technical_weighting_is_detected() -> None:
    tender_id = _create_tender("Eval weighting positive technical")
    doc_id = _import_pdf(tender_id, "positive-tech-weight.pdf")
    _seed_page_and_normalized(doc_id, 1, "La propuesta tecnica tendra una ponderacion del 70%.")

    payload = _analyze(tender_id)
    weighting = [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert weighting
    assert weighting[0]["weight_value"] == 70
    assert weighting[0]["weight_unit"] == "PERCENT"


def test_explicit_economic_weighting_of_evaluation_is_detected() -> None:
    tender_id = _create_tender("Eval weighting positive economic")
    doc_id = _import_pdf(tender_id, "positive-econ-weight.pdf")
    _seed_page_and_normalized(doc_id, 1, "La propuesta economica representara el 30% de la evaluacion.")

    payload = _analyze(tender_id)
    weighting = [item for item in payload["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert weighting
    assert weighting[0]["weight_value"] == 30
    assert weighting[0]["weight_unit"] == "PERCENT"


def test_price_clause_without_evaluation_semantics_is_not_price_evaluation_rule() -> None:
    tender_id = _create_tender("Eval price context negative")
    doc_id = _import_pdf(tender_id, "price-contractual.pdf")
    _seed_page_and_normalized(doc_id, 1, "El precio del contrato incluye IVA y los precios seran fijos.")

    payload = _analyze(tender_id)
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "PRICE_EVALUATION_RULE"]


def test_lowest_solvent_price_clause_produces_award_and_price_rules() -> None:
    tender_id = _create_tender("Eval price context positive")
    doc_id = _import_pdf(tender_id, "price-award.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se adjudicara a la propuesta solvente que oferte el precio mas bajo.")

    payload = _analyze(tender_id)
    by_type = {item["criterion_type"] for item in payload["criteria"]}
    assert "AWARD_RULE" in by_type
    assert "PRICE_EVALUATION_RULE" in by_type


def test_accented_lowest_price_clause_produces_price_evidence() -> None:
    tender_id = _create_tender("Eval accented price context positive")
    doc_id = _import_pdf(tender_id, "price-award-accented.pdf")
    _seed_page_and_normalized(doc_id, 1, "El criterio de adjudicación que se utilizará será el precio más bajo.")

    payload = _analyze(tender_id)
    by_type = {item["criterion_type"] for item in payload["criteria"]}
    assert "AWARD_RULE" in by_type
    assert "PRICE_EVALUATION_RULE" in by_type


def test_price_evaluation_rule_evidence_contains_visible_price_semantics() -> None:
    tender_id = _create_tender("Eval price evidence completeness")
    doc_id = _import_pdf(tender_id, "price-evidence.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "El criterio de adjudicacion que se utilizara sera el precio mas bajo. Una vez hecha la evaluacion, la adjudicacion se realizara al participante cuya propuesta resulte solvente y cuyo precio sea el mas bajo.",
    )

    payload = _analyze(tender_id)
    price_rule = next(item for item in payload["criteria"] if item["criterion_type"] == "PRICE_EVALUATION_RULE")
    excerpts = [evidence["source_excerpt"].lower() for evidence in price_rule["evidence"]]
    assert any("precio" in excerpt and ("bajo" in excerpt or "economica" in excerpt or "compar" in excerpt) for excerpt in excerpts)


def test_line_wrapped_clause_retains_decisive_price_evidence() -> None:
    tender_id = _create_tender("Eval wrapped price evidence")
    doc_id = _import_pdf(tender_id, "wrapped-price.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Una vez hecha la evaluacion de las propuestas y realizada la adjudicacion se realizara al participante cuya propuesta resulte solvente porque cumple con los\ncriterios de evaluacion establecidos y cuyo precio sea el mas bajo.",
    )

    payload = _analyze(tender_id)
    price_rule = next(item for item in payload["criteria"] if item["criterion_type"] == "PRICE_EVALUATION_RULE")
    assert "precio sea el mas bajo" in price_rule["source_excerpt"].lower()
    assert "precio sea el mas bajo" in price_rule["criterion_text"].lower()


def test_truncated_award_only_excerpt_is_not_sufficient_for_price_rule() -> None:
    tender_id = _create_tender("Eval truncated price insufficiency")
    doc_id = _import_pdf(tender_id, "truncated-price.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "La adjudicacion se realizara al participante cuya propuesta resulte solvente porque cumple con los criterios de evaluacion establecidos.",
    )

    payload = _analyze(tender_id)
    assert any(item["criterion_type"] == "AWARD_RULE" for item in payload["criteria"])
    assert not [item for item in payload["criteria"] if item["criterion_type"] == "PRICE_EVALUATION_RULE"]


def test_lowest_price_model_evidence_includes_explicit_price_semantics() -> None:
    tender_id = _create_tender("Eval model price evidence completeness")
    doc_id = _import_pdf(tender_id, "model-price-evidence.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "El criterio de adjudicacion que se utilizara sera el precio mas bajo. Una vez hecha la evaluacion, la adjudicacion se realizara al participante cuya propuesta resulte solvente y cuyo precio sea el mas bajo.",
    )

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "LOWEST_EVALUATED_PRICE"
    model_excerpts = [item["source_excerpt"].lower() for item in payload["model"]["evidence"]]
    assert any("precio mas bajo" in excerpt for excerpt in model_excerpts)


def test_award_only_evidence_does_not_produce_lowest_price_model() -> None:
    tender_id = _create_tender("Eval award only no lowest price")
    doc_id = _import_pdf(tender_id, "award-only.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "La adjudicacion se realizara al participante cuya propuesta resulte solvente porque cumple con los criterios de evaluacion establecidos.",
    )

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] != "LOWEST_EVALUATED_PRICE"


def test_multiple_coherent_evidence_records_can_jointly_support_lowest_price_model() -> None:
    tender_id = _create_tender("Eval model multi evidence")
    doc_id = _import_pdf(tender_id, "multi-evidence-price.pdf")
    _seed_page_and_normalized(doc_id, 1, "La adjudicacion se realizara al participante cuya propuesta resulte solvente.")
    _seed_page_and_normalized(doc_id, 2, "El criterio de adjudicacion que se utilizara sera el precio mas bajo.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "LOWEST_EVALUATED_PRICE"
    model_excerpts = [item["source_excerpt"].lower() for item in payload["model"]["evidence"]]
    assert any("adjudicacion" in excerpt or "solvente" in excerpt for excerpt in model_excerpts)
    assert any("precio mas bajo" in excerpt for excerpt in model_excerpts)


def test_does_not_join_unrelated_paragraphs_on_same_page() -> None:
    tender_id = _create_tender("Eval no arbitrary same page joining")
    doc_id = _import_pdf(tender_id, "same-page-paragraphs.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "La adjudicacion se realizara al participante cuya propuesta resulte solvente.\n\nCuyo precio sea el mas bajo.",
    )

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] != "LOWEST_EVALUATED_PRICE"


def test_extracts_minimum_score_threshold() -> None:
    tender_id = _create_tender("Eval threshold")
    doc_id = _import_pdf(tender_id, "threshold.pdf")
    _seed_page_and_normalized(doc_id, 1, "Se requiere un minimo de 75 puntos para ser considerado solvente.")

    payload = _analyze(tender_id)
    minimum = [item for item in payload["criteria"] if item["criterion_type"] == "MINIMUM_SCORE"]
    assert minimum
    assert minimum[0]["threshold_operator"] == "GREATER_THAN_OR_EQUAL"
    assert minimum[0]["threshold_value"] == 75
    assert minimum[0]["threshold_unit"] == "POINTS"


def test_extracts_rejection_cause_and_exclusionary_true() -> None:
    tender_id = _create_tender("Eval rejection")
    doc_id = _import_pdf(tender_id, "reject.pdf")
    _seed_page_and_normalized(doc_id, 1, "El incumplimiento de requisitos indispensables sera causa de desechamiento.")

    payload = _analyze(tender_id)
    rejection = [item for item in payload["criteria"] if item["criterion_type"] == "REJECTION_CAUSE"]
    assert rejection
    assert rejection[0]["is_exclusionary"] is True


def test_obligation_without_evaluation_semantics_is_not_criterion() -> None:
    tender_id = _create_tender("Eval obligation no criterion")
    doc_id = _import_pdf(tender_id, "obligation.pdf")
    _seed_page_and_normalized(doc_id, 1, "El licitante debera presentar su acta constitutiva.")

    payload = _analyze(tender_id)
    assert payload["criteria_summary"]["total"] == 0


def test_every_auto_model_and_criteria_have_evidence_and_source() -> None:
    tender_id = _create_tender("Eval evidence checks")
    doc_id = _import_pdf(tender_id, "ev.pdf")
    _seed_page_and_normalized(doc_id, 2, "La evaluacion tecnica sera binaria y el incumplimiento sera causa de desechamiento.")

    payload = _analyze(tender_id)
    assert payload["model"]["evidence"]
    for item in payload["model"]["evidence"]:
        assert item["source_document_id"] == doc_id
        assert item["source_page"] == 2
        assert item["source_excerpt"]

    for criterion in payload["criteria"]:
        assert criterion["source_document_id"] == doc_id
        assert criterion["source_excerpt"]
        assert criterion["evidence"]


def test_repeated_model_statement_keeps_one_model_with_multiple_evidence() -> None:
    tender_id = _create_tender("Eval repeated model evidence")
    doc_id = _import_pdf(tender_id, "repeat.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion tecnica sera binaria.")
    _seed_page_and_normalized(doc_id, 2, "El criterio de evaluacion sera cumple/no cumple.")

    payload = _analyze(tender_id)
    assert payload["model"]["effective_method"] == "BINARY_COMPLIANCE"
    assert len(payload["model"]["evidence"]) >= 2


def test_repeated_exact_criterion_is_deduplicated() -> None:
    tender_id = _create_tender("Eval criterion dedup")
    doc_id = _import_pdf(tender_id, "dedup.pdf")
    text = "La evaluacion tecnica sera binaria, cumple/no cumple."
    _seed_page_and_normalized(doc_id, 1, text)
    _seed_page_and_normalized(doc_id, 2, text)

    payload = _analyze(tender_id)
    pass_fail = [item for item in payload["criteria"] if item["criterion_type"] == "PASS_FAIL_RULE"]
    assert len(pass_fail) == 1
    assert len(pass_fail[0]["evidence"]) >= 2


def test_two_distinct_rejection_causes_remain_separate() -> None:
    tender_id = _create_tender("Eval rejection separation")
    doc_id = _import_pdf(tender_id, "rejsep.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Sera causa de desechamiento no entregar garantia. Tambien sera causa de desechamiento no acreditar experiencia.",
    )

    payload = _analyze(tender_id)
    rejection = [item for item in payload["criteria"] if item["criterion_type"] == "REJECTION_CAUSE"]
    assert len(rejection) == 2


def test_model_confirm_reject_override_survive_rerun() -> None:
    tender_id = _create_tender("Eval model human persistence")
    doc_id = _import_pdf(tender_id, "human-model.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion tecnica sera binaria.")

    first = _analyze(tender_id)
    assert first["model"]["effective_method"] == "BINARY_COMPLIANCE"

    confirm = client.patch(f"/tenders/{tender_id}/evaluation", json={"action": "CONFIRM"})
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["model"]["review_status"] == "CONFIRMED"

    override = client.patch(
        f"/tenders/{tender_id}/evaluation",
        json={"action": "OVERRIDE", "method": "POINTS_PERCENTAGES", "summary": "Decision humana"},
    )
    assert override.status_code == 200, override.text
    assert override.json()["model"]["effective_method"] == "POINTS_PERCENTAGES"

    rerun = _analyze(tender_id)
    assert rerun["model"]["effective_method"] == "POINTS_PERCENTAGES"
    assert rerun["model"]["review_status"] == "CONFIRMED"

    reject = client.patch(f"/tenders/{tender_id}/evaluation", json={"action": "REJECT"})
    assert reject.status_code == 200, reject.text
    rerun_rejected = _analyze(tender_id)
    assert rerun_rejected["model"]["review_status"] == "REJECTED"


def test_criterion_confirm_reject_override_survive_rerun_and_evidence_immutable() -> None:
    tender_id = _create_tender("Eval criterion human persistence")
    doc_id = _import_pdf(tender_id, "human-criterion.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion tecnica sera binaria, cumple/no cumple.")

    first = _analyze(tender_id)
    criterion = next(item for item in first["criteria"] if item["criterion_type"] == "PASS_FAIL_RULE")
    criterion_id = criterion["id"]
    evidence_before = criterion["evidence"]

    confirm = client.patch(f"/tenders/{tender_id}/evaluation-criteria/{criterion_id}", json={"action": "CONFIRM"})
    assert confirm.status_code == 200, confirm.text

    override = client.patch(
        f"/tenders/{tender_id}/evaluation-criteria/{criterion_id}",
        json={
            "action": "OVERRIDE",
            "criterion_type": "TECHNICAL_EVALUATION_RULE",
            "category": "TECHNICAL",
            "title": "Regla tecnica humana",
            "criterion_text": "La evaluacion tecnica se confirma por decision humana.",
            "is_exclusionary": False,
            "human_note": "override",
        },
    )
    assert override.status_code == 200, override.text

    rerun = _analyze(tender_id)
    criterion_after = next(item for item in rerun["criteria"] if item["id"] == criterion_id)
    assert criterion_after["criterion_type"] == "TECHNICAL_EVALUATION_RULE"
    assert criterion_after["review_status"] == "CONFIRMED"
    assert criterion_after["evidence"] == evidence_before

    reject = client.patch(f"/tenders/{tender_id}/evaluation-criteria/{criterion_id}", json={"action": "REJECT"})
    assert reject.status_code == 200, reject.text
    rerun_rejected = _analyze(tender_id)
    criterion_rejected = next(item for item in rerun_rejected["criteria"] if item["id"] == criterion_id)
    assert criterion_rejected["review_status"] == "REJECTED"


def test_stale_suggested_criteria_reconciles_without_deleting_human_reviewed() -> None:
    tender_id = _create_tender("Eval stale reconcile")
    doc_id = _import_pdf(tender_id, "stale.pdf")
    _seed_page_and_normalized(doc_id, 1, "La evaluacion tecnica sera binaria, cumple/no cumple.")

    first = _analyze(tender_id)
    criterion_id = next(item["id"] for item in first["criteria"] if item["criterion_type"] == "PASS_FAIL_RULE")

    mark = client.patch(f"/tenders/{tender_id}/evaluation-criteria/{criterion_id}", json={"action": "CONFIRM"})
    assert mark.status_code == 200, mark.text

    _update_normalized(doc_id, "Texto actualizado sin semantica de evaluacion.")

    rerun = _analyze(tender_id)
    still_exists = [item for item in rerun["criteria"] if item["id"] == criterion_id]
    assert still_exists
    assert still_exists[0]["review_status"] == "CONFIRMED"


def test_stale_suggested_false_weighting_criteria_are_reconciled_away() -> None:
    tender_id = _create_tender("Eval stale weighting reconcile")
    doc_id = _import_pdf(tender_id, "stale-weight.pdf")
    _seed_page_and_normalized(doc_id, 1, "Evaluacion por puntos y porcentajes: propuesta tecnica 70%, propuesta economica 30%.")

    first = _analyze(tender_id)
    weight_ids = [item["id"] for item in first["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert len(weight_ids) == 2

    _update_normalized(doc_id, "Se aplicara pena convencional del 5% por atraso en la entrega.")

    rerun = _analyze(tender_id)
    remaining_weight_ids = [item["id"] for item in rerun["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert not remaining_weight_ids
    assert not [item for item in rerun["criteria"] if item["id"] in weight_ids]


def test_model_aggregation_changes_after_false_weighting_disappears() -> None:
    tender_id = _create_tender("Eval model aggregation after weighting cleanup")
    doc_id = _import_pdf(tender_id, "agg-weighting.pdf")
    _seed_page_and_normalized(
        doc_id,
        1,
        "Se adjudicara a la propuesta solvente que oferte el precio mas bajo. Evaluacion por puntos y porcentajes: propuesta tecnica 70%.",
    )

    before = _analyze(tender_id)
    assert before["model"]["effective_method"] == "MIXED"
    assert [item for item in before["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]

    _update_normalized(doc_id, "Se adjudicara a la propuesta solvente que oferte el precio mas bajo. Se aplicara pena convencional del 5%.")

    after = _analyze(tender_id)
    assert not [item for item in after["criteria"] if item["criterion_type"] == "WEIGHTING_RULE"]
    assert after["model"]["effective_method"] == "LOWEST_EVALUATED_PRICE"


def test_analyze_evaluation_does_not_mutate_closed_domains() -> None:
    tender_id = _create_tender("Eval non regression closed domains")
    source_doc = _import_pdf(tender_id, "source.pdf")
    target_doc = _import_pdf(tender_id, "target.pdf", suffix="target")
    page_id = _seed_page_and_normalized(source_doc, 1, "La evaluacion tecnica sera binaria, cumple/no cumple.")
    _seed_page_and_normalized(target_doc, 1, "Documento destino")

    _seed_closed_domain_rows(tender_id, source_doc, page_id, target_doc)
    before = _snapshot_closed_domain_rows(tender_id, source_doc)

    payload = _analyze(tender_id)
    assert payload["criteria_summary"]["total"] >= 1

    after = _snapshot_closed_domain_rows(tender_id, source_doc)

    assert before["classification"] == after["classification"]
    assert before["reference"] == after["reference"]
    assert before["relationship"] == after["relationship"]
    assert before["event"] == after["event"]
    assert before["change"] == after["change"]
    assert before["doc_current"] == after["doc_current"]


def test_get_evaluation_without_analysis_returns_unknown_contract() -> None:
    tender_id = _create_tender("Eval empty get")
    payload = _get_eval(tender_id)

    assert payload["model"]["effective_method"] == "UNKNOWN"
    assert payload["criteria_summary"]["total"] == 0


def test_snapshot_endpoint_remains_operational_after_evaluation_analysis() -> None:
    tender_id = _create_tender("Eval snapshot interaction")
    doc_id = _import_pdf(tender_id, "snapshot.pdf")
    _seed_page_and_normalized(doc_id, 1, "El metodo de evaluacion sera por puntos y porcentajes.")

    _ = _analyze(tender_id)

    snapshot = client.get(f"/tenders/{tender_id}/state-snapshot")
    assert snapshot.status_code == 200, snapshot.text
    payload = snapshot.json()
    assert payload["tender_id"] == tender_id
    assert "readiness" in payload
