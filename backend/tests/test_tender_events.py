from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    NormalizedContent,
    TenderDocument,
    TenderEvent,
    TenderEventEvidence,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "EVT-001",
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


def _seed_page(document_id: str, page_number: int, text: str, *, is_current: bool = True) -> str:
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
        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = max(doc.page_count, page_number)
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"
        doc.is_current = is_current
        db.commit()
        return page.id
    finally:
        db.close()


def _seed_normalized(page_id: str, text: str) -> str:
    db = SessionLocal()
    try:
        row = NormalizedContent(
            document_page_id=page_id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page_id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _update_normalized(content_id: str, text: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(NormalizedContent, content_id)
        assert row is not None
        row.normalized_text = text
        row.char_count = len(text)
        row.content_sha256 = hashlib.sha256(f"updated-{content_id}-{text}".encode("utf-8")).hexdigest()
        db.commit()
    finally:
        db.close()


def _seed_classification(document_id: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=document_id,
                suggested_type="NOTICE",
                suggested_score=80,
                classification_status="SUGGESTED",
                classifier_method="RULE_BASED_GENERIC",
                classifier_version="mvp-02.4.2",
                input_fingerprint_sha256="fingerprint",
                is_composite=False,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_reference_analysis(document_id: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentReferenceAnalysis(
                document_id=document_id,
                status="COMPLETED",
                extractor_version="mvp-02.5.1",
                input_fingerprint_sha256="fp",
            )
        )
        db.commit()
    finally:
        db.close()


def _get_timeline(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/events")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_timeline(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-events")
    assert response.status_code == 200, response.text
    return response.json()


def _event_by_id(timeline: dict, event_id: str) -> dict:
    return next(item for item in timeline["events"] if item["id"] == event_id)


def test_same_segment_anchor_and_date_creates_event() -> None:
    tender_id = _create_tender("Events same segment")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "cronograma")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 2 de octubre de 2026.")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "CLARIFICATION_MEETING"
    assert event["event_date"] == "2026-10-02"


def test_structurally_related_fragments_create_one_event_with_time() -> None:
    tender_id = _create_tender("Events structural fragments time")
    document_id = _import_pdf(tender_id, "tabla.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(
        page_id,
        "Presentacion de proposiciones\n2-octubre-2026\n10:00 horas",
    )

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "PROPOSAL_SUBMISSION_DEADLINE"
    assert event["event_date"] == "2026-10-02"
    assert event["event_time"] == "10:00:00"
    evidence_texts = {item["source_excerpt"] for item in event["evidence"]}
    assert "Presentacion de proposiciones" in evidence_texts
    assert "2-octubre-2026" in evidence_texts
    assert "10:00 horas" in evidence_texts


def test_structurally_related_fragments_without_time_create_event_with_null_time() -> None:
    tender_id = _create_tender("Events structural fragments no time")
    document_id = _import_pdf(tender_id, "tabla.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(page_id, "Junta de aclaraciones\n02-10-2026")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "CLARIFICATION_MEETING"
    assert event["event_date"] == "2026-10-02"
    assert event["event_time"] is None


def test_anchor_and_date_in_unrelated_contexts_on_same_page_do_not_join() -> None:
    tender_id = _create_tender("Events unrelated same page")
    document_id = _import_pdf(tender_id, "tabla.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(page_id, "La junta de aclaraciones queda sujeta a confirmacion.")
    _seed_normalized(page_id, "02-10-2026")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_bare_date_fragment_does_not_create_event() -> None:
    tender_id = _create_tender("Events bare date")
    document_id = _import_pdf(tender_id, "tabla.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(page_id, "02-10-2026")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_bare_time_fragment_does_not_create_event() -> None:
    tender_id = _create_tender("Events bare time")
    document_id = _import_pdf(tender_id, "tabla.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(page_id, "10:00 horas")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_apartado_labels_do_not_create_events() -> None:
    tender_id = _create_tender("Events apartados")
    document_id = _import_pdf(tender_id, "anexos.pdf")
    page_id = _seed_page(document_id, 1, "tabla")
    _seed_normalized(page_id, "APARTADO D-3\nAPARTADO D-4\nAPARTADO D-5")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_schedule_row_and_narrative_duplicate_merge_into_one_event() -> None:
    tender_id = _create_tender("Events duplicate merge")
    document_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "Presentacion de proposiciones\n02/10/2026\n10:00 horas")
    _seed_normalized(page_id, "El acto de presentacion de proposiciones se realizara el 2 de octubre de 2026 a las 10:00 horas")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 1
    event = payload["events"][0]
    assert event["event_type"] == "PROPOSAL_SUBMISSION_DEADLINE"
    assert len(event["evidence"]) >= 3


def test_two_schedule_rows_with_different_dates_create_two_events() -> None:
    tender_id = _create_tender("Events two rows")
    document_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "Junta de aclaraciones\n02/10/2026\n10:00 horas\nJunta de aclaraciones\n05/10/2026\n11:00 horas")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 2
    dates = sorted(item["event_date"] for item in payload["events"])
    assert dates == ["2026-10-02", "2026-10-05"]


def test_hyphen_spanish_date_parses_day_correctly() -> None:
    tender_id = _create_tender("Events parser")
    document_id = _import_pdf(tender_id, "convocatoria.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "El acto de presentacion de proposiciones se realizara el 2-octubre-2026")

    payload = _analyze_timeline(tender_id)
    event = payload["events"][0]
    assert event["event_date"] == "2026-10-02"
    assert event["date_precision"] == "DAY"


def test_structural_fragment_missing_year_uses_nearby_explicit_year() -> None:
    tender_id = _create_tender("Events inferred year")
    document_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(
        page_id,
        "Aclaraciones de dudas\n28 de agosto de 2026\n10:00 horas\nPresentacion de proposiciones\n9 de septiembre de\n10:00 horas",
    )

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] >= 1
    proposal_events = [item for item in payload["events"] if item["event_type"] == "PROPOSAL_SUBMISSION_DEADLINE"]
    assert proposal_events
    assert proposal_events[0]["event_date"] == "2026-09-09"


def test_structural_fragment_missing_year_without_neighbor_year_is_rejected() -> None:
    tender_id = _create_tender("Events no inferred year")
    document_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "Presentacion de proposiciones\n9 de septiembre de\n10:00 horas")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_bare_year_does_not_create_auto_event() -> None:
    tender_id = _create_tender("Events year only")
    document_id = _import_pdf(tender_id, "fallo.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "Fallo durante 2026")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_tender_identifier_with_year_does_not_create_auto_event() -> None:
    tender_id = _create_tender("Events tender id")
    document_id = _import_pdf(tender_id, "fallo.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "SNR-CAD-265-CA-S-2026")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_execution_duration_is_not_contract_signature_event() -> None:
    tender_id = _create_tender("Events duration")
    document_id = _import_pdf(tender_id, "anexo-d.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(
        page_id,
        "La firma del contrato se realizara en su oportunidad. El plazo de ejecucion de los servicios es de 35 dias naturales a partir de la fecha.",
    )

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_confirm_sets_status_confirmed() -> None:
    tender_id = _create_tender("Events confirm")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/10/2026")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    response = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "CONFIRM"})
    assert response.status_code == 200, response.text
    assert _event_by_id(response.json(), event_id)["review_status"] == "CONFIRMED"


def test_reject_sets_status_rejected() -> None:
    tender_id = _create_tender("Events reject")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/10/2026")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    response = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "REJECT"})
    assert response.status_code == 200, response.text
    assert _event_by_id(response.json(), event_id)["review_status"] == "REJECTED"


def test_override_can_modify_date_time_event_type_title_and_note() -> None:
    tender_id = _create_tender("Events override fields")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 02/10/2026 a las 10:00 horas")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    response = client.patch(
        f"/tenders/{tender_id}/events/{event_id}",
        json={
            "action": "OVERRIDE",
            "event_type": "PROPOSAL_SUBMISSION_DEADLINE",
            "title": "Entrega final",
            "event_date": "2026-10-03",
            "event_time": "11:00:00",
            "date_precision": "DAY",
            "human_note": "ajuste humano",
        },
    )
    assert response.status_code == 200, response.text
    event = _event_by_id(response.json(), event_id)
    assert event["event_type"] == "PROPOSAL_SUBMISSION_DEADLINE"
    assert event["title"] == "Entrega final"
    assert event["event_date"] == "2026-10-03"
    assert event["event_time"] == "11:00:00"
    assert event["human_note"] == "ajuste humano"


def test_human_override_survives_reanalysis() -> None:
    tender_id = _create_tender("Events override survives")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    content_id = _seed_normalized(page_id, "La junta de aclaraciones se realizara el 02/10/2026 a las 10:00 horas")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    patched = client.patch(
        f"/tenders/{tender_id}/events/{event_id}",
        json={
            "action": "OVERRIDE",
            "event_type": "PROPOSAL_SUBMISSION_DEADLINE",
            "title": "Entrega ajustada",
            "event_date": "2026-10-03",
            "event_time": "11:00:00",
            "date_precision": "DAY",
            "human_note": "modificada",
        },
    )
    assert patched.status_code == 200, patched.text

    _update_normalized(content_id, "Texto sin evento ni fecha procesable")

    second = _analyze_timeline(tender_id)
    event = _event_by_id(second, event_id)
    assert event["review_status"] == "CONFIRMED"
    assert event["event_date"] == "2026-10-03"
    assert event["event_time"] == "11:00:00"


def test_source_evidence_remains_unchanged_after_human_override() -> None:
    tender_id = _create_tender("Events evidence immutable")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "Presentacion de proposiciones\n02/10/2026\n10:00 horas")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]
    before_evidence = sorted((item["source_document_id"], item["source_page"], item["source_excerpt"]) for item in first["events"][0]["evidence"])

    patched = client.patch(
        f"/tenders/{tender_id}/events/{event_id}",
        json={
            "action": "OVERRIDE",
            "event_date": "2026-10-03",
            "event_time": "11:00:00",
            "date_precision": "DAY",
            "human_note": "ajuste",
        },
    )
    assert patched.status_code == 200, patched.text
    after_event = _event_by_id(patched.json(), event_id)
    after_evidence = sorted((item["source_document_id"], item["source_page"], item["source_excerpt"]) for item in after_event["evidence"])

    assert before_evidence == after_evidence


def test_reset_to_suggested_clears_human_override_fields() -> None:
    tender_id = _create_tender("Events reset")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 02/10/2026 a las 10:00 horas")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    patched = client.patch(
        f"/tenders/{tender_id}/events/{event_id}",
        json={
            "action": "OVERRIDE",
            "title": "Junta ajustada",
            "event_date": "2026-10-04",
            "event_time": "11:30:00",
            "date_precision": "DAY",
            "human_note": "manual",
        },
    )
    assert patched.status_code == 200, patched.text

    reset = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "RESET_TO_SUGGESTED"})
    assert reset.status_code == 200, reset.text
    event = _event_by_id(reset.json(), event_id)

    assert event["review_status"] == "SUGGESTED"
    assert event["event_date"] == "2026-10-02"
    assert event["event_time"] == "10:00:00"
    assert event["human_note"] is None


def test_stale_deterministic_suggested_event_disappears_after_reanalysis() -> None:
    tender_id = _create_tender("Events stale suggested")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    content_id = _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/10/2026")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]

    _update_normalized(content_id, "Texto sin evento ni fecha procesable")

    second = _analyze_timeline(tender_id)
    event_ids = {item["id"] for item in second["events"]}
    assert event_id not in event_ids


def test_confirmed_event_survives_reanalysis_without_source_match() -> None:
    tender_id = _create_tender("Events confirmed survives")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    content_id = _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/10/2026")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]
    patched = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "CONFIRM"})
    assert patched.status_code == 200, patched.text

    _update_normalized(content_id, "Texto sin evento ni fecha procesable")

    second = _analyze_timeline(tender_id)
    assert _event_by_id(second, event_id)["review_status"] == "CONFIRMED"


def test_rejected_event_survives_reanalysis_without_source_match() -> None:
    tender_id = _create_tender("Events rejected survives")
    document_id = _import_pdf(tender_id, "cronograma.pdf")
    page_id = _seed_page(document_id, 1, "texto")
    content_id = _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/10/2026")

    first = _analyze_timeline(tender_id)
    event_id = first["events"][0]["id"]
    patched = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "REJECT"})
    assert patched.status_code == 200, patched.text

    _update_normalized(content_id, "Texto sin evento ni fecha procesable")

    second = _analyze_timeline(tender_id)
    assert _event_by_id(second, event_id)["review_status"] == "REJECTED"


def test_analyze_events_is_idempotent_and_does_not_duplicate() -> None:
    tender_id = _create_tender("Events idempotent")
    doc_a = _import_pdf(tender_id, "convocatoria-a.pdf")
    doc_b = _import_pdf(tender_id, "convocatoria-b.pdf")
    page_a = _seed_page(doc_a, 1, "texto")
    page_b = _seed_page(doc_b, 1, "texto")
    event_line = "La junta de aclaraciones se realizara el 15 de septiembre de 2026"
    _seed_normalized(page_a, event_line)
    _seed_normalized(page_b, event_line)

    first = _analyze_timeline(tender_id)
    second = _analyze_timeline(tender_id)

    assert first["counts"]["total_events"] == 1
    assert second["counts"]["total_events"] == 1
    assert first["events"][0]["id"] == second["events"][0]["id"]


def test_analyze_events_ignores_non_current_documents() -> None:
    tender_id = _create_tender("Events current only")
    old_doc = _import_pdf(tender_id, "bases-v1.pdf")
    current_doc = _import_pdf(tender_id, "bases-v2.pdf")

    old_page = _seed_page(old_doc, 1, "old", is_current=False)
    _seed_normalized(old_page, "La junta de aclaraciones se realizara el 10/09/2026")

    current_page = _seed_page(current_doc, 1, "current", is_current=True)
    _seed_normalized(current_page, "Documento vigente sin eventos")

    payload = _analyze_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0


def test_analyze_events_does_not_mutate_reference_or_classification_rows() -> None:
    tender_id = _create_tender("Events no mutation")
    doc_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(doc_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/03/2027")
    _seed_classification(doc_id)
    _seed_reference_analysis(doc_id)

    db = SessionLocal()
    try:
        counts_before = {
            "classifications": db.execute(select(func.count()).select_from(DocumentClassification)).scalar_one(),
            "references": db.execute(select(func.count()).select_from(DocumentReference)).scalar_one(),
            "reference_analyses": db.execute(select(func.count()).select_from(DocumentReferenceAnalysis)).scalar_one(),
        }
    finally:
        db.close()

    _analyze_timeline(tender_id)

    db = SessionLocal()
    try:
        counts_after = {
            "classifications": db.execute(select(func.count()).select_from(DocumentClassification)).scalar_one(),
            "references": db.execute(select(func.count()).select_from(DocumentReference)).scalar_one(),
            "reference_analyses": db.execute(select(func.count()).select_from(DocumentReferenceAnalysis)).scalar_one(),
        }
    finally:
        db.close()

    assert counts_before == counts_after


def test_relationship_baseline_is_unchanged_after_event_analysis() -> None:
    tender_id = _create_tender("Events baseline regression")
    source_id = _import_pdf(tender_id, "convocatoria.pdf")
    target_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(source_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 10 de septiembre de 2026")

    _seed_classification(source_id)
    _seed_classification(target_id)
    _seed_reference_analysis(source_id)

    baseline_before_response = client.get(f"/tenders/{tender_id}/relationship-baseline")
    assert baseline_before_response.status_code == 200, baseline_before_response.text
    baseline_before = baseline_before_response.json()

    _analyze_timeline(tender_id)

    baseline_after_response = client.get(f"/tenders/{tender_id}/relationship-baseline")
    assert baseline_after_response.status_code == 200, baseline_after_response.text
    baseline_after = baseline_after_response.json()

    assert baseline_before["counts"] == baseline_after["counts"]
    assert baseline_before["reference_status_counts"] == baseline_after["reference_status_counts"]


def test_invalid_event_action_returns_400() -> None:
    tender_id = _create_tender("Events invalid action")
    doc_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(doc_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/03/2027")

    timeline = _analyze_timeline(tender_id)
    event_id = timeline["events"][0]["id"]

    response = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "INVALID"})
    assert response.status_code == 400


def test_get_events_without_analysis_returns_empty_timeline() -> None:
    tender_id = _create_tender("Events empty")
    payload = _get_timeline(tender_id)
    assert payload["counts"]["total_events"] == 0
    assert payload["events"] == []


def test_event_tables_are_persisted() -> None:
    tender_id = _create_tender("Events persisted")
    doc_id = _import_pdf(tender_id, "bases.pdf")
    page_id = _seed_page(doc_id, 1, "texto")
    _seed_normalized(page_id, "La junta de aclaraciones se realizara el 03/03/2027")

    _analyze_timeline(tender_id)

    db = SessionLocal()
    try:
        event_count = db.execute(select(func.count()).select_from(TenderEvent).where(TenderEvent.tender_id == tender_id)).scalar_one()
        evidence_count = db.execute(
            select(func.count())
            .select_from(TenderEventEvidence)
            .join(TenderEvent, TenderEvent.id == TenderEventEvidence.event_id)
            .where(TenderEvent.tender_id == tender_id)
        ).scalar_one()
    finally:
        db.close()

    assert event_count == 1
    assert evidence_count >= 1
