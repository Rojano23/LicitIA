from __future__ import annotations

import hashlib
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    NormalizedContent,
    TenderChange,
    TenderDocument,
    TenderEvent,
)
from app.tender_state_snapshot import generate_tender_state_snapshot

client = TestClient(app)


def _create_tender(title: str, external_reference: str = "SS-001") -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": external_reference,
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


def _seed_page(document_id: str, text: str, *, page_number: int = 1, processing_status: str = "TEXT_EXTRACTION_COMPLETE") -> str:
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
        doc.processing_status = processing_status
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
            content_sha256=hashlib.sha256(f"snapshot-{page_id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _seed_classification(document_id: str, *, status: str = "CONFIRMED") -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=document_id,
                suggested_type="NOTICE",
                suggested_score=85,
                classification_status=status,
                classifier_method="RULE_BASED_GENERIC",
                classifier_version="mvp-02.4.2",
                input_fingerprint_sha256="snapshot-fp",
                is_composite=False,
                human_type="BIDDING_RULES" if status == "CONFIRMED" else None,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_reference_analysis(document_id: str) -> str:
    db = SessionLocal()
    try:
        row = DocumentReferenceAnalysis(
            document_id=document_id,
            status="COMPLETED",
            extractor_version="mvp-02.5.1",
            input_fingerprint_sha256="snapshot-ref-fp",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _seed_reference(
    analysis_id: str,
    source_document_id: str,
    page_id: str,
    *,
    normalized_key: str,
    resolution_status: str,
    target_document_id: str | None = None,
    auto_candidates: str | None = None,
) -> str:
    db = SessionLocal()
    try:
        row = DocumentReference(
            analysis_id=analysis_id,
            source_document_id=source_document_id,
            document_page_id=page_id,
            reference_identity_key=hashlib.sha256(
                f"{analysis_id}|{source_document_id}|{normalized_key}|{resolution_status}".encode("utf-8")
            ).hexdigest(),
            raw_reference_text=normalized_key,
            normalized_reference_key=normalized_key,
            reference_kind="ANNEX",
            relationship_hint="REFERENCES",
            resolution_status=resolution_status,
            resolved_target_document_id=target_document_id,
            auto_candidate_document_ids=auto_candidates,
            source_scope="NATIVE_PAGE",
            source_type="NATIVE_PDF",
            excerpt="snapshot-ref",
            extractor_version="mvp-02.5.1",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _seed_event(
    tender_id: str,
    source_document_id: str,
    *,
    review_status: str = "SUGGESTED",
    event_type: str = "CLARIFICATION_MEETING",
    event_date: date | None = None,
) -> str:
    db = SessionLocal()
    try:
        row = TenderEvent(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"{tender_id}|{source_document_id}|{event_type}|{event_date}".encode("utf-8")).hexdigest(),
            event_type=event_type,
            title=event_type,
            event_date=event_date,
            date_precision="DAY" if event_date else "UNKNOWN",
            timezone="America/Mexico_City",
            review_status=review_status,
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.2",
            source_document_id=source_document_id,
            source_page=1,
            source_excerpt="snapshot-event",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _analyze_changes(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-changes")
    assert response.status_code == 200, response.text
    return response.json()


def _patch_change(tender_id: str, change_id: str, payload: dict) -> None:
    response = client.patch(f"/tenders/{tender_id}/changes/{change_id}", json=payload)
    assert response.status_code == 200, response.text


def _get_snapshot(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/state-snapshot")
    assert response.status_code == 200, response.text
    return response.json()


def test_snapshot_minimal_tender_has_valid_contract() -> None:
    tender_id = _create_tender("Snapshot minimal")
    payload = _get_snapshot(tender_id)

    assert payload["tender_id"] == tender_id
    assert payload["snapshot_version"] == "mvp-03.5"
    assert payload["readiness"]["code"] == "UNDERSTOOD"
    assert "documents" in payload["summary"]
    assert "relationships" in payload["summary"]
    assert "timeline" in payload["summary"]
    assert "changes" in payload["summary"]
    assert "effective_state" in payload["summary"]
    assert "pending_actions" in payload["summary"]


def test_snapshot_reuses_existing_read_model_counts() -> None:
    tender_id = _create_tender("Snapshot counts")
    source = _import_pdf(tender_id, "convocatoria.pdf")
    target = _import_pdf(tender_id, "bases.pdf")

    page = _seed_page(source, "Referencia a bases")
    _seed_page(target, "bases")
    _seed_normalized(page, "Se hace referencia a BASES_DE_CONTRATACION")
    _seed_classification(source)
    _seed_classification(target)
    analysis_id = _seed_reference_analysis(source)
    _seed_reference(
        analysis_id,
        source,
        page,
        normalized_key="BASES_DE_CONTRATACION",
        resolution_status="AUTO_RESOLVED",
        target_document_id=target,
        auto_candidates=target,
    )

    snapshot = _get_snapshot(tender_id)
    baseline = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
    timeline = client.get(f"/tenders/{tender_id}/events").json()
    changes = client.get(f"/tenders/{tender_id}/changes").json()
    effective = client.get(f"/tenders/{tender_id}/effective-state").json()

    assert snapshot["summary"]["relationships"]["relationship_edge_count"] == baseline["counts"]["relationship_edge_count"]
    assert snapshot["summary"]["timeline"]["total_events"] == timeline["counts"]["total_events"]
    assert snapshot["summary"]["changes"]["total_changes"] == changes["counts"]["total_changes"]
    assert snapshot["summary"]["effective_state"]["total_scopes"] == effective["summary"]["total_scopes"]


def test_snapshot_repeated_get_is_read_only_semantic_equal_except_generated_at() -> None:
    tender_id = _create_tender("Snapshot idempotency")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, "texto")
    _seed_page(target, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 12, de 30 a 45.")

    before_changes = client.get(f"/tenders/{tender_id}/changes").json()
    before_events = client.get(f"/tenders/{tender_id}/events").json()

    first = _get_snapshot(tender_id)
    second = _get_snapshot(tender_id)

    first_copy = dict(first)
    second_copy = dict(second)
    first_copy.pop("generated_at", None)
    second_copy.pop("generated_at", None)
    assert first_copy == second_copy

    after_changes = client.get(f"/tenders/{tender_id}/changes").json()
    after_events = client.get(f"/tenders/{tender_id}/events").json()

    assert before_changes["changes"] == after_changes["changes"]
    assert before_events["events"] == after_events["events"]


def test_snapshot_not_ready_when_blocking_integrity_exists() -> None:
    tender_id = _create_tender("Snapshot blocker")
    doc_id = _import_pdf(tender_id, "missing-storage.pdf")

    db = SessionLocal()
    try:
        doc = db.get(TenderDocument, doc_id)
        assert doc is not None
        doc.stored_relative_path = "../../outside.pdf"
        db.commit()
    finally:
        db.close()

    snapshot = _get_snapshot(tender_id)
    assert snapshot["readiness"]["code"] == "NOT_READY"
    assert snapshot["summary"]["pending_actions"]["blocking"] >= 1


def test_snapshot_partial_for_ambiguous_reference_and_pending_event_change() -> None:
    tender_id = _create_tender("Snapshot partial signals")
    source = _import_pdf(tender_id, "junta-a.pdf")
    target_a = _import_pdf(tender_id, "anexo-a.pdf")
    target_b = _import_pdf(tender_id, "anexo-b.pdf")

    page = _seed_page(source, "texto")
    _seed_page(target_a, "A")
    _seed_page(target_b, "B")
    _seed_normalized(page, "Se modifica el Anexo Z en el numeral 8, de 10 a 12.")
    _seed_classification(source)
    analysis_id = _seed_reference_analysis(source)
    _seed_reference(
        analysis_id,
        source,
        page,
        normalized_key="ANEXO:Z",
        resolution_status="AMBIGUOUS",
        auto_candidates=f"{target_a},{target_b}",
    )

    _seed_event(tender_id, source, review_status="SUGGESTED", event_date=date(2026, 10, 2))
    changes = _analyze_changes(tender_id)
    assert changes["counts"]["suggested_changes"] >= 1

    snapshot = _get_snapshot(tender_id)
    assert snapshot["readiness"]["code"] == "PARTIALLY_UNDERSTOOD"
    categories = {item["category"] for item in snapshot["pending_actions"]}
    assert "RESOLVE_REFERENCE" in categories
    assert "REVIEW_EVENT" in categories
    assert "REVIEW_CHANGE" in categories


def test_snapshot_partial_for_ambiguous_precedence_and_resolve_precedence_action() -> None:
    tender_id = _create_tender("Snapshot ambiguous precedence")
    target = _import_pdf(tender_id, "anexo d.pdf")
    source_a = _import_pdf(tender_id, "junta-a.pdf")
    source_b = _import_pdf(tender_id, "junta-b.pdf")

    _seed_page(target, "target")
    _seed_normalized(_seed_page(source_a, "a"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    _seed_normalized(_seed_page(source_b, "b"), "Se modifica el Anexo D en el numeral 12, de 45 a 40.")

    changes = _analyze_changes(tender_id)
    for row in changes["changes"]:
        _patch_change(tender_id, row["id"], {"action": "CONFIRM"})

    snapshot = _get_snapshot(tender_id)
    assert snapshot["summary"]["effective_state"]["ambiguous_precedence"] >= 1
    assert snapshot["readiness"]["code"] == "PARTIALLY_UNDERSTOOD"
    assert any(item["category"] == "RESOLVE_PRECEDENCE" for item in snapshot["pending_actions"])


def test_snapshot_understood_for_fully_coherent_synthetic_tender() -> None:
    tender_id = _create_tender("Snapshot understood")
    source = _import_pdf(tender_id, "convocatoria.pdf")

    page = _seed_page(source, "texto procesado")
    _seed_normalized(page, "Contenido listo")
    _seed_classification(source)
    _seed_reference_analysis(source)

    snapshot = _get_snapshot(tender_id)
    assert snapshot["readiness"]["code"] == "UNDERSTOOD"
    assert snapshot["summary"]["pending_actions"]["blocking"] == 0
    assert snapshot["summary"]["pending_actions"]["warning"] == 0


def test_snapshot_pending_actions_are_deduplicated() -> None:
    tender_id = _create_tender("Snapshot dedup")
    source = _import_pdf(tender_id, "source.pdf")

    page = _seed_page(source, "texto")
    _seed_normalized(page, "Junta de aclaraciones")
    _seed_event(tender_id, source, review_status="SUGGESTED", event_type="CLARIFICATION_MEETING", event_date=date(2026, 10, 2))
    _seed_event(tender_id, source, review_status="SUGGESTED", event_type="SITE_VISIT", event_date=date(2026, 10, 3))

    snapshot = _get_snapshot(tender_id)
    keys = {
        (
            item["category"],
            item["severity"],
            item["document_id"],
            item["source_page"],
            item["related_entity_id"],
            item["title"],
        )
        for item in snapshot["pending_actions"]
    }
    assert len(keys) == len(snapshot["pending_actions"])


def test_snapshot_cross_layer_modifies_without_confirmed_change_is_warning(monkeypatch) -> None:
    tender_id = _create_tender("Snapshot cross-layer modifies")

    original = generate_tender_state_snapshot

    def fake_baseline(db: SessionLocal, _tender_id: str) -> dict:
        payload = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
        payload["document_map"] = [
            {
                "source_document_id": "a",
                "source_filename": "a.pdf",
                "relationship_type": "MODIFIES",
                "target_document_id": "b",
                "target_filename": "b.pdf",
                "supporting_reference_count": 1,
                "supporting_pages": [1],
                "resolution_origin": "AUTO",
            }
        ]
        return payload

    monkeypatch.setattr("app.tender_state_snapshot.generate_tender_relationship_baseline", fake_baseline)
    db = SessionLocal()
    try:
        snapshot = original(db, tender_id)
    finally:
        db.close()
    codes = {item["code"] for item in snapshot["integrity"]["cross_layer_issues"]}
    assert "MODIFIES_WITHOUT_CONFIRMED_CHANGE" in codes


def test_snapshot_cross_layer_confirmed_mutation_missing_modifies_edge_is_warning(monkeypatch) -> None:
    tender_id = _create_tender("Snapshot cross-layer missing edge")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")

    _seed_page(target, "target")
    _seed_normalized(_seed_page(source, "texto"), "Se modifica el Anexo D en el numeral 12, de 30 a 45.")
    changes = _analyze_changes(tender_id)
    _patch_change(tender_id, changes["changes"][0]["id"], {"action": "CONFIRM"})

    def fake_baseline(db: SessionLocal, _tender_id: str) -> dict:
        payload = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
        payload["document_map"] = []
        return payload

    monkeypatch.setattr("app.tender_state_snapshot.generate_tender_relationship_baseline", fake_baseline)
    db = SessionLocal()
    try:
        snapshot = generate_tender_state_snapshot(db, tender_id)
    finally:
        db.close()

    codes = {item["code"] for item in snapshot["integrity"]["cross_layer_issues"]}
    assert "CONFIRMED_MUTATION_MISSING_MODIFIES_EDGE" in codes


def test_snapshot_endpoint_does_not_mutate_human_controls() -> None:
    tender_id = _create_tender("Snapshot human controls", external_reference="SS-HUMAN")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")

    page_id = _seed_page(source, "texto")
    _seed_page(target, "target")
    _seed_normalized(page_id, "Se modifica el Anexo D en el numeral 12, de 30 a 45.")

    _seed_classification(source, status="CONFIRMED")
    analysis_id = _seed_reference_analysis(source)
    reference_id = _seed_reference(
        analysis_id,
        source,
        page_id,
        normalized_key="ANEXO:D",
        resolution_status="HUMAN_RESOLVED",
        target_document_id=target,
        auto_candidates=target,
    )

    db = SessionLocal()
    try:
        ref = db.get(DocumentReference, reference_id)
        assert ref is not None
        ref.human_decision = "RESOLVE_TO_DOCUMENT"
        ref.human_target_document_id = target
        db.commit()
    finally:
        db.close()

    event_id = _seed_event(tender_id, source, review_status="CONFIRMED", event_date=date(2026, 10, 2))
    changes = _analyze_changes(tender_id)
    change_id = changes["changes"][0]["id"]
    _patch_change(
        tender_id,
        change_id,
        {
            "action": "OVERRIDE",
            "change_type": "MODIFIES",
            "target_document_id": target,
            "target_locator_text": "Numeral 12",
            "before_text": "30",
            "after_text": "45",
            "human_note": "manual",
        },
    )

    response = client.patch(
        f"/tenders/{tender_id}/events/{event_id}",
        json={
            "action": "OVERRIDE",
            "event_type": "CLARIFICATION_MEETING",
            "title": "Junta aclaraciones",
            "event_date": "2026-10-03",
            "date_precision": "DAY",
            "human_note": "manual event",
        },
    )
    assert response.status_code == 200, response.text

    before_events = client.get(f"/tenders/{tender_id}/events").json()["events"]
    before_changes = client.get(f"/tenders/{tender_id}/changes").json()["changes"]

    db = SessionLocal()
    try:
        before_classifications = db.execute(
            select(DocumentClassification.document_id, DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source)
        ).all()
        before_refs = db.execute(
            select(
                DocumentReference.id,
                DocumentReference.resolution_status,
                DocumentReference.human_decision,
                DocumentReference.human_target_document_id,
            ).where(DocumentReference.id == reference_id)
        ).all()
    finally:
        db.close()

    _get_snapshot(tender_id)

    after_events = client.get(f"/tenders/{tender_id}/events").json()["events"]
    after_changes = client.get(f"/tenders/{tender_id}/changes").json()["changes"]

    db = SessionLocal()
    try:
        after_classifications = db.execute(
            select(DocumentClassification.document_id, DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source)
        ).all()
        after_refs = db.execute(
            select(
                DocumentReference.id,
                DocumentReference.resolution_status,
                DocumentReference.human_decision,
                DocumentReference.human_target_document_id,
            ).where(DocumentReference.id == reference_id)
        ).all()
    finally:
        db.close()

    assert before_events == after_events
    assert before_changes == after_changes
    assert before_classifications == after_classifications
    assert before_refs == after_refs
