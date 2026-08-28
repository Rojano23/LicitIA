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
    DocumentRelationship,
    NormalizedContent,
    TenderChange,
    TenderChangeEvidence,
    TenderDocument,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": "CHG-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str, *, payload_suffix: str = "") -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}{payload_suffix}) >>\nendobj\n%%EOF\n".encode("utf-8")
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


def _seed_classification(document_id: str, *, status: str = "SUGGESTED", human_type: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(
            DocumentClassification(
                document_id=document_id,
                suggested_type="NOTICE",
                suggested_score=80,
                classification_status=status,
                classifier_method="RULE_BASED_GENERIC",
                classifier_version="mvp-02.4.2",
                input_fingerprint_sha256="fingerprint",
                is_composite=False,
                human_type=human_type,
                human_note="manual" if human_type else None,
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


def _seed_human_resolved_reference(source_document_id: str, page_id: str, target_document_id: str) -> str:
    db = SessionLocal()
    try:
        analysis_id = db.execute(
            select(DocumentReferenceAnalysis.id).where(DocumentReferenceAnalysis.document_id == source_document_id)
        ).scalar_one()
        row = DocumentReference(
            analysis_id=analysis_id,
            source_document_id=source_document_id,
            document_page_id=page_id,
            reference_identity_key=hashlib.sha256(f"ref-{source_document_id}-{target_document_id}".encode("utf-8")).hexdigest(),
            raw_reference_text="ANEXO D",
            normalized_reference_key="ANEXO:D",
            reference_kind="ANNEX",
            relationship_hint="REFERENCES",
            resolution_status="HUMAN_RESOLVED",
            resolved_target_document_id=target_document_id,
            human_target_document_id=target_document_id,
            human_decision="RESOLVE_TO_DOCUMENT",
            source_scope="NATIVE_PAGE",
            source_type="NATIVE_PDF",
            excerpt="Referencia humana",
            extractor_version="mvp-02.5.1",
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


def _list_changes(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/changes")
    assert response.status_code == 200, response.text
    return response.json()


def _patch_change(tender_id: str, change_id: str, payload: dict) -> dict:
    response = client.patch(f"/tenders/{tender_id}/changes/{change_id}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_references_for_document(tender_id: str, document_id: str) -> None:
    response = client.post(f"/tenders/{tender_id}/documents/{document_id}/analyze-references")
    assert response.status_code == 200, response.text


def _event_timeline(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/events")
    assert response.status_code == 200, response.text
    return response.json()


def _change_by_id(payload: dict, change_id: str) -> dict:
    return next(item for item in payload["changes"] if item["id"] == change_id)


def test_detect_modifies_statement() -> None:
    tender_id = _create_tender("CHG A modifies")
    source = _import_pdf(tender_id, "junta-1.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el plazo de ejecucion senalado en el Anexo D, de 30 a 45 dias naturales.")

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 1
    change = payload["changes"][0]
    assert change["change_type"] == "MODIFIES"
    assert change["target_document_id"] == target
    assert change["before_text"] == "30"
    assert change["after_text"].startswith("45")


def test_detect_clarifies_statement() -> None:
    tender_id = _create_tender("CHG B clarifies")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se aclara que la experiencia podra acreditarse mediante contratos concluidos.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["change_type"] == "CLARIFIES"


def test_detect_replaces_statement() -> None:
    tender_id = _create_tender("CHG C replaces")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo c.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se sustituye el Anexo C por el documento adjunto.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["change_type"] == "REPLACES"
    assert payload["changes"][0]["target_document_id"] == target


def test_detect_adds_statement() -> None:
    tender_id = _create_tender("CHG D adds")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se adiciona la partida 12 al alcance tecnico.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["change_type"] == "ADDS"


def test_detect_removes_statement() -> None:
    tender_id = _create_tender("CHG E removes")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se elimina el numeral 3.2 de las bases.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["change_type"] == "REMOVES"


def test_donde_dice_debe_decir_extracts_before_after() -> None:
    tender_id = _create_tender("CHG F before after")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Donde dice: 30 dias naturales, debe decir: 45 dias naturales")

    payload = _analyze_changes(tender_id)
    change = payload["changes"][0]
    assert change["before_text"] == "30 dias naturales"
    assert change["after_text"] == "45 dias naturales"


def test_modify_with_only_after_keeps_before_null() -> None:
    tender_id = _create_tender("CHG G after only")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se modifica el plazo de ejecucion a 45 dias naturales.")

    payload = _analyze_changes(tender_id)
    change = payload["changes"][0]
    assert change["before_text"] is None
    assert change["after_text"] == "45 dias naturales"


def test_generic_modificado_without_tender_context_is_rejected() -> None:
    tender_id = _create_tender("CHG H generic modificado")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "El documento fue modificado el 5 de mayo de 2026.")

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 0


def test_fecha_modificacion_metadata_is_rejected() -> None:
    tender_id = _create_tender("CHG I metadata")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Fecha de modificacion: 2026-05-05")

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 0


def test_contractor_operational_modify_is_rejected() -> None:
    tender_id = _create_tender("CHG J contractor")
    source = _import_pdf(tender_id, "bases.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "El contratista debera modificar el programa de trabajo cuando sea necesario.")

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 0


def test_unique_target_resolves_automatically() -> None:
    tender_id = _create_tender("CHG K unique target")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["target_document_id"] == target


def test_zero_target_candidates_keeps_unresolved() -> None:
    tender_id = _create_tender("CHG L no target")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se modifica el Anexo Z en el numeral 4.2.")

    payload = _analyze_changes(tender_id)
    change = payload["changes"][0]
    assert change["target_document_id"] is None
    assert change["target_reference_key"] == "ANEXO:Z"


def test_multiple_target_candidates_stays_ambiguous() -> None:
    tender_id = _create_tender("CHG M ambiguous")
    source = _import_pdf(tender_id, "junta.pdf")
    _import_pdf(tender_id, "anexo d version 1.pdf", payload_suffix="v1")
    _import_pdf(tender_id, "anexo d version 2.pdf", payload_suffix="v2")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se modifica el Anexo D.")

    payload = _analyze_changes(tender_id)
    change = payload["changes"][0]
    assert change["target_document_id"] is None
    assert len(change["target_candidate_documents"]) == 2


def test_non_current_candidate_is_excluded() -> None:
    tender_id = _create_tender("CHG N non current")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page_source = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target", is_current=False)
    _seed_normalized(page_source, "Se modifica el Anexo D.")

    payload = _analyze_changes(tender_id)
    assert payload["changes"][0]["target_document_id"] is None


def test_internal_locator_is_stored_without_fake_document() -> None:
    tender_id = _create_tender("CHG O locator")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se corrige el numeral 4.2 de la seccion II.")

    payload = _analyze_changes(tender_id)
    change = payload["changes"][0]
    assert change["target_document_id"] is None
    assert change["target_locator_text"] == "numeral 4.2"


def test_self_target_does_not_create_invalid_modifies_edge() -> None:
    tender_id = _create_tender("CHG P self edge")
    source = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_normalized(page, "Se modifica el Anexo D.")

    payload = _analyze_changes(tender_id)
    change_id = payload["changes"][0]["id"]
    _patch_change(tender_id, change_id, {"action": "CONFIRM"})

    baseline = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
    assert baseline["counts"]["self_edge_count"] == 0


def test_repeated_same_change_is_deduped() -> None:
    tender_id = _create_tender("CHG Q dedup")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page1 = _seed_page(source, 1, "texto")
    page2 = _seed_page(source, 2, "texto")
    _seed_page(target, 1, "target")
    statement = "Se modifica el Anexo D en el numeral 4.2."
    _seed_normalized(page1, statement)
    _seed_normalized(page2, statement)

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 1


def test_multiple_mentions_add_multiple_evidence_items() -> None:
    tender_id = _create_tender("CHG R evidence")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    p1 = _seed_page(source, 1, "texto")
    p2 = _seed_page(source, 2, "texto")
    _seed_page(target, 1, "target")
    statement = "Se modifica el Anexo D en el numeral 4.2."
    _seed_normalized(p1, statement)
    _seed_normalized(p2, statement)

    payload = _analyze_changes(tender_id)
    assert len(payload["changes"][0]["evidence"]) == 2


def test_two_distinct_changes_in_same_document_remain_separate() -> None:
    tender_id = _create_tender("CHG S separate")
    source = _import_pdf(tender_id, "junta.pdf")
    target_d = _import_pdf(tender_id, "anexo d.pdf")
    target_c = _import_pdf(tender_id, "anexo c.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target_d, 1, "target")
    _seed_page(target_c, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D. Se sustituye el Anexo C por nueva version.")

    payload = _analyze_changes(tender_id)
    assert payload["counts"]["total_changes"] == 2


def test_confirmed_modifies_creates_document_relationship() -> None:
    tender_id = _create_tender("CHG T edge")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2.")

    payload = _analyze_changes(tender_id)
    change_id = payload["changes"][0]["id"]
    _patch_change(tender_id, change_id, {"action": "CONFIRM"})

    relationships = client.get(f"/tenders/{tender_id}/relationships").json()
    modifies = [item for item in relationships if item["relationship_type"] == "MODIFIES"]
    assert len(modifies) == 1
    assert modifies[0]["source_document_id"] == source
    assert modifies[0]["target_document_id"] == target


def test_repeated_confirmed_changes_same_pair_do_not_duplicate_edge() -> None:
    tender_id = _create_tender("CHG U no duplicate edge")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2. Se corrige el Anexo D en el numeral 5.")

    payload = _analyze_changes(tender_id)
    for change in payload["changes"]:
      _patch_change(tender_id, change["id"], {"action": "CONFIRM"})

    relationships = client.get(f"/tenders/{tender_id}/relationships").json()
    modifies = [item for item in relationships if item["relationship_type"] == "MODIFIES"]
    assert len(modifies) == 1


def test_references_and_modifies_coexist_for_same_pair() -> None:
    tender_id = _create_tender("CHG V coexist")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Consulte el Anexo D.\nSe modifica el Anexo D en el numeral 4.2.")

    _analyze_references_for_document(tender_id, source)
    payload = _analyze_changes(tender_id)
    _patch_change(tender_id, payload["changes"][0]["id"], {"action": "CONFIRM"})

    relationships = client.get(f"/tenders/{tender_id}/relationships").json()
    types = {(item["source_document_id"], item["target_document_id"], item["relationship_type"]) for item in relationships}
    assert (source, target, "REFERENCES") in types
    assert (source, target, "MODIFIES") in types


def test_relationship_baseline_has_zero_duplicate_and_self_edges() -> None:
    tender_id = _create_tender("CHG W X baseline")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2.")

    payload = _analyze_changes(tender_id)
    _patch_change(tender_id, payload["changes"][0]["id"], {"action": "CONFIRM"})
    baseline = client.get(f"/tenders/{tender_id}/relationship-baseline").json()

    assert baseline["counts"]["duplicate_edge_count"] == 0
    assert baseline["counts"]["self_edge_count"] == 0


def test_confirm_reject_override_and_reset_survive_reanalysis() -> None:
    tender_id = _create_tender("CHG Y-Z-AA-AB-AC-AD-AE-AF-AG")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    content_id = _seed_normalized(page, "Donde dice: 30 dias, debe decir: 45 dias. Se aclara que aplica para mantenimiento.")

    initial = _analyze_changes(tender_id)
    assert initial["counts"]["total_changes"] == 2

    modify_row = next(item for item in initial["changes"] if item["change_type"] == "MODIFIES")
    clarify_row = next(item for item in initial["changes"] if item["change_type"] == "CLARIFIES")

    confirm_payload = _patch_change(tender_id, modify_row["id"], {"action": "CONFIRM"})
    assert _change_by_id(confirm_payload, modify_row["id"])["review_status"] == "CONFIRMED"

    reject_payload = _patch_change(tender_id, clarify_row["id"], {"action": "REJECT"})
    assert _change_by_id(reject_payload, clarify_row["id"])["review_status"] == "REJECTED"

    overridden = _patch_change(
        tender_id,
        modify_row["id"],
        {
            "action": "OVERRIDE",
            "change_type": "REPLACES",
            "target_document_id": target,
            "target_locator_text": "numeral 4.2",
            "before_text": "30 dias",
            "after_text": "50 dias",
            "human_note": "ajuste humano",
        },
    )
    modified = _change_by_id(overridden, modify_row["id"])
    evidence_before = sorted((item["source_document_id"], item["source_page"], item["source_excerpt"]) for item in modified["evidence"])

    _update_normalized(content_id, "Texto sin anchors de cambios")

    rerun = _analyze_changes(tender_id)
    persisted_modify = _change_by_id(rerun, modify_row["id"])
    persisted_reject = _change_by_id(rerun, clarify_row["id"])

    assert persisted_modify["review_status"] == "CONFIRMED"
    assert persisted_modify["change_type"] == "REPLACES"
    assert persisted_modify["target_document_id"] == target
    assert persisted_modify["before_text"] == "30 dias"
    assert persisted_modify["after_text"] == "50 dias"
    assert persisted_modify["human_note"] == "ajuste humano"

    evidence_after = sorted((item["source_document_id"], item["source_page"], item["source_excerpt"]) for item in persisted_modify["evidence"])
    assert evidence_before == evidence_after

    assert persisted_reject["review_status"] == "REJECTED"


def test_reset_to_suggested_clears_human_fields() -> None:
    tender_id = _create_tender("CHG reset")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")
    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2.")

    payload = _analyze_changes(tender_id)
    change_id = payload["changes"][0]["id"]
    _patch_change(
        tender_id,
        change_id,
        {
            "action": "OVERRIDE",
            "change_type": "CORRECTS",
            "target_document_id": target,
            "target_locator_text": "numeral 8",
            "before_text": "x",
            "after_text": "y",
            "human_note": "manual",
        },
    )

    reset_payload = _patch_change(tender_id, change_id, {"action": "RESET_TO_SUGGESTED"})
    reset_change = _change_by_id(reset_payload, change_id)
    assert reset_change["review_status"] == "SUGGESTED"
    assert reset_change["human_note"] is None


def test_stale_suggested_is_removed_but_human_reviewed_survives() -> None:
    tender_id = _create_tender("CHG AF AG")
    source = _import_pdf(tender_id, "junta.pdf")
    page = _seed_page(source, 1, "texto")
    content_id = _seed_normalized(page, "Se aclara que la experiencia sera valida.")

    first = _analyze_changes(tender_id)
    change_id = first["changes"][0]["id"]
    _patch_change(tender_id, change_id, {"action": "CONFIRM"})

    _update_normalized(content_id, "Sin statement")
    second = _analyze_changes(tender_id)
    assert any(item["id"] == change_id for item in second["changes"])

    third = _patch_change(tender_id, change_id, {"action": "RESET_TO_SUGGESTED"})
    assert _change_by_id(third, change_id)["review_status"] == "SUGGESTED"

    fourth = _analyze_changes(tender_id)
    assert not any(item["id"] == change_id for item in fourth["changes"])


def test_analyze_changes_does_not_mutate_classification_reference_or_timeline_human_states() -> None:
    tender_id = _create_tender("CHG AH-AI-AJ-AK-AL")
    source = _import_pdf(tender_id, "junta.pdf")
    target = _import_pdf(tender_id, "anexo d.pdf")
    page = _seed_page(source, 1, "texto")
    _seed_page(target, 1, "target")

    _seed_classification(source, status="CONFIRMED", human_type="BIDDING_RULES")
    _seed_reference_analysis(source)
    ref_id = _seed_human_resolved_reference(source, page, target)

    _seed_normalized(page, "Se modifica el Anexo D en el numeral 4.2. La junta de aclaraciones se realizara el 03/10/2026")

    before_timeline = client.post(f"/tenders/{tender_id}/analyze-events").json()
    event_id = before_timeline["events"][0]["id"]
    confirmed_timeline = client.patch(f"/tenders/{tender_id}/events/{event_id}", json={"action": "CONFIRM"}).json()

    db = SessionLocal()
    try:
        classification_before = db.execute(
            select(DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source)
        ).one()
        reference_before = db.execute(
            select(DocumentReference.resolution_status, DocumentReference.human_decision, DocumentReference.human_target_document_id)
            .where(DocumentReference.id == ref_id)
        ).one()
    finally:
        db.close()

    _analyze_changes(tender_id)

    db = SessionLocal()
    try:
        classification_after = db.execute(
            select(DocumentClassification.classification_status, DocumentClassification.human_type)
            .where(DocumentClassification.document_id == source)
        ).one()
        reference_after = db.execute(
            select(DocumentReference.resolution_status, DocumentReference.human_decision, DocumentReference.human_target_document_id)
            .where(DocumentReference.id == ref_id)
        ).one()
        counts = {
            "changes": db.execute(select(func.count()).select_from(TenderChange).where(TenderChange.tender_id == tender_id)).scalar_one(),
            "change_evidence": db.execute(
                select(func.count())
                .select_from(TenderChangeEvidence)
                .join(TenderChange, TenderChange.id == TenderChangeEvidence.change_id)
                .where(TenderChange.tender_id == tender_id)
            ).scalar_one(),
        }
    finally:
        db.close()

    after_timeline = _event_timeline(tender_id)
    event_after = next(item for item in after_timeline["events"] if item["id"] == event_id)

    baseline_before = client.get(f"/tenders/{tender_id}/relationship-baseline").json()
    _analyze_changes(tender_id)
    baseline_after = client.get(f"/tenders/{tender_id}/relationship-baseline").json()

    assert classification_before == classification_after
    assert reference_before == reference_after
    assert event_after["review_status"] == "CONFIRMED"
    assert counts["changes"] >= 1
    assert counts["change_evidence"] >= 1

    assert baseline_after["counts"]["duplicate_edge_count"] == 0
    assert baseline_after["counts"]["self_edge_count"] == 0
    assert baseline_after["relationship_type_counts"]["REFERENCES"] == baseline_before["relationship_type_counts"]["REFERENCES"]
    assert any(item["id"] == event_id and item["review_status"] == "CONFIRMED" for item in confirmed_timeline["events"])
