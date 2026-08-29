from __future__ import annotations

import hashlib
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentPage,
    NormalizedContent,
    Requirement,
    RequirementCandidate,
    RequirementCandidateEvidence,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementSemantics,
    RequirementVersionLink,
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
            "external_reference": "REQ-VER-001",
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

        normalized = NormalizedContent(
            document_page_id=page.id,
            source_type="NATIVE_PDF",
            source_scope="NATIVE_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"norm-{page.id}-{text}".encode("utf-8")).hexdigest(),
        )
        db.add(normalized)

        doc = db.get(TenderDocument, document_id)
        assert doc is not None
        doc.page_count = max(doc.page_count, page_number)
        doc.processing_status = "TEXT_EXTRACTION_COMPLETE"

        db.commit()
        return page.id, normalized.id
    finally:
        db.close()


def _seed_requirement_candidate(
    *,
    tender_id: str,
    document_id: str,
    page_id: str,
    normalized_content_id: str,
    source_page: int,
    text: str,
) -> str:
    db = SessionLocal()
    try:
        candidate = RequirementCandidate(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(f"{tender_id}|{document_id}|{page_id}|{text}".encode("utf-8")).hexdigest(),
            requirement_text=text,
            actor_text="El participante",
            modality_text="debera",
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

        db.add(
            RequirementCandidateEvidence(
                candidate_id=candidate.id,
                source_document_id=document_id,
                source_page=source_page,
                source_excerpt=text,
                excerpt_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                document_page_id=page_id,
                normalized_content_id=normalized_content_id,
            )
        )

        db.commit()
        return candidate.id
    finally:
        db.close()


def _normalize_requirements(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_changes(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-changes")
    assert response.status_code == 200, response.text
    return response.json()


def _confirm_change(tender_id: str, change_id: str) -> None:
    response = client.patch(f"/tenders/{tender_id}/changes/{change_id}", json={"action": "CONFIRM"})
    assert response.status_code == 200, response.text


def _analyze_requirement_versions(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert response.status_code == 200, response.text
    return response.json()


def _get_requirement_effective_state(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/requirement-effective-state")
    assert response.status_code == 200, response.text
    return response.json()


def _analyze_requirement_semantics(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert response.status_code == 200, response.text
    return response.json()


def _seed_change(
    *,
    tender_id: str,
    source_document_id: str,
    target_document_id: str,
    locator: str,
    before_text: str | None,
    after_text: str | None,
    review_status: str,
    change_type: str = "MODIFIES",
) -> str:
    db = SessionLocal()
    try:
        semantic = "|".join(
            [tender_id, source_document_id, target_document_id, locator, before_text or "", after_text or "", change_type]
        )
        row = TenderChange(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
            change_type=change_type,
            target_reference_key="ANEXO:D",
            target_document_id=target_document_id,
            target_candidate_document_ids=target_document_id,
            target_locator_text=locator,
            before_text=before_text,
            after_text=after_text,
            source_document_id=source_document_id,
            source_page=1,
            source_excerpt=f"{change_type} {locator}",
            review_status=review_status,
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.3",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _seed_event(
    *,
    tender_id: str,
    source_document_id: str,
    event_type: str,
    review_status: str,
    event_date: date,
) -> str:
    db = SessionLocal()
    try:
        semantic = "|".join([tender_id, source_document_id, event_type, str(event_date), review_status])
        row = TenderEvent(
            tender_id=tender_id,
            semantic_key=hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
            event_type=event_type,
            title=event_type,
            event_date=event_date,
            date_precision="DAY",
            review_status=review_status,
            detection_origin="DETERMINISTIC",
            detector_version="mvp-03.2",
            source_document_id=source_document_id,
            source_page=1,
            source_excerpt=event_type,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _get_version_links(tender_id: str) -> list[RequirementVersionLink]:
    db = SessionLocal()
    try:
        return db.execute(
            select(RequirementVersionLink)
            .where(RequirementVersionLink.tender_id == tender_id)
            .order_by(RequirementVersionLink.id.asc())
        ).scalars().all()
    finally:
        db.close()


def _snapshot_semantics_state(tender_id: str) -> tuple[list[tuple], list[tuple]]:
    db = SessionLocal()
    try:
        semantics_rows = db.execute(
            select(RequirementSemantics).join(Requirement, Requirement.id == RequirementSemantics.requirement_id).where(Requirement.tender_id == tender_id)
        ).scalars().all()
        semantics = sorted(
            [
                (
                    row.requirement_id,
                    row.applicability,
                    row.condition_text,
                    row.interpretation_status,
                    row.evidence_mode,
                )
                for row in semantics_rows
            ]
        )

        expectations_rows = db.execute(
            select(RequirementEvidenceExpectation)
            .join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id)
            .where(Requirement.tender_id == tender_id)
        ).scalars().all()
        expectations = sorted(
            [
                (
                    row.requirement_id,
                    row.evidence_type,
                    row.evidence_description,
                    row.source_candidate_id,
                    row.source_document_id,
                    row.source_page,
                    row.source_excerpt,
                )
                for row in expectations_rows
            ]
        )
        return semantics, expectations
    finally:
        db.close()


def _requirement_count(tender_id: str) -> int:
    db = SessionLocal()
    try:
        return db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one()
    finally:
        db.close()


def _seed_requirement_from_candidate(tender_id: str, candidate_id: str, canonical_text: str, canonical_key: str) -> str:
    db = SessionLocal()
    try:
        row = Requirement(
            tender_id=tender_id,
            canonical_key=canonical_key,
            canonical_text=canonical_text,
            category="TECHNICAL",
            normalization_status="NORMALIZED",
            normalizer_version="mvp-04.3",
            normalization_confidence=1.0,
            normalization_reason="seeded_for_test",
            primary_candidate_id=candidate_id,
        )
        db.add(row)
        db.flush()
        db.add(
            RequirementCandidateLink(
                requirement_id=row.id,
                requirement_candidate_id=candidate_id,
                is_primary_source=True,
                link_origin="DETERMINISTIC",
            )
        )
        db.commit()
        return row.id
    finally:
        db.close()


def _find_requirement(payload: dict, text_fragment: str) -> dict:
    for row in payload["requirements"]:
        if text_fragment.lower() in row["canonical_text"].lower():
            return row
    raise AssertionError(f"Requirement not found for fragment: {text_fragment}")


def test_no_confirmed_change_keeps_requirements_effective() -> None:
    tender_id = _create_tender("REQ VER no confirmed")
    bases_id = _import_pdf(tender_id, "anexo d.pdf")

    p1, n1 = _seed_page_and_normalized(bases_id, 1, "El participante debera presentar constancia fiscal vigente.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=bases_id,
        page_id=p1,
        normalized_content_id=n1,
        source_page=1,
        text="El participante debera presentar constancia fiscal vigente.",
    )

    _normalize_requirements(tender_id)
    payload = _analyze_requirement_versions(tender_id)

    assert payload["summary"]["version_link_count"] == 0
    assert payload["summary"]["effective_count"] == 1
    assert payload["requirements"][0]["effective_status"] == "EFFECTIVE"


def test_confirmed_explicit_modification_creates_version_link() -> None:
    tender_id = _create_tender("REQ VER explicit modify")
    target_doc_id = _import_pdf(tender_id, "anexo d.pdf")
    source_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p_old, n_old = _seed_page_and_normalized(target_doc_id, 1, "Numeral 4.2: el plazo sera de 30 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir un plazo de 30 dias naturales.",
    )

    p_new, n_new = _seed_page_and_normalized(source_doc_id, 1, "Numeral 4.2: el plazo sera de 45 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=source_doc_id,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir un plazo de 45 dias naturales.",
    )

    _seed_page_and_normalized(source_doc_id, 2, "Se modifica el Anexo D en el numeral 4.2, de 30 dias naturales a 45 dias naturales.")

    _normalize_requirements(tender_id)
    changes = _analyze_changes(tender_id)
    assert len(changes["changes"]) == 1
    _confirm_change(tender_id, changes["changes"][0]["id"])

    payload = _analyze_requirement_versions(tender_id)

    assert payload["summary"]["version_link_count"] == 1
    assert payload["version_links"][0]["link_kind"] == "SUPERSEDES"

    old_req = _find_requirement(payload, "30 dias naturales")
    new_req = _find_requirement(payload, "45 dias naturales")

    assert old_req["effective_status"] == "SUPERSEDED"
    assert new_req["effective_status"] == "EFFECTIVE"
    assert new_req["effective_source_document_id"] == source_doc_id


def test_similarity_alone_does_not_create_version_link() -> None:
    tender_id = _create_tender("REQ VER no similarity")
    target_doc_id = _import_pdf(tender_id, "anexo d.pdf")
    source_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p_old, n_old = _seed_page_and_normalized(target_doc_id, 1, "Se requiere experiencia minima de tres anos en mantenimiento industrial.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="El participante debera acreditar experiencia minima de tres anos en mantenimiento industrial.",
    )

    p_new, n_new = _seed_page_and_normalized(source_doc_id, 1, "Se requiere experiencia minima de cuatro anos en mantenimiento industrial.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=source_doc_id,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="El participante debera acreditar experiencia minima de cuatro anos en mantenimiento industrial.",
    )

    _seed_page_and_normalized(source_doc_id, 2, "Se modifica el Anexo D.")

    _normalize_requirements(tender_id)
    changes = _analyze_changes(tender_id)
    _confirm_change(tender_id, changes["changes"][0]["id"])

    payload = _analyze_requirement_versions(tender_id)

    assert payload["summary"]["version_link_count"] == 0
    assert payload["summary"]["superseded_count"] == 0


def test_ambiguous_predecessor_mapping_marks_requirements_ambiguous() -> None:
    tender_id = _create_tender("REQ VER ambiguous predecessor")
    target_doc_id = _import_pdf(tender_id, "anexo d.pdf")
    source_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p_a, n_a = _seed_page_and_normalized(target_doc_id, 1, "Numeral 4.2: plazo de 30 dias naturales para etapa A.")
    candidate_a = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p_a,
        normalized_content_id=n_a,
        source_page=1,
        text="Numeral 4.2: el participante debera entregar etapa A en 30 dias naturales.",
    )

    p_b, n_b = _seed_page_and_normalized(target_doc_id, 2, "Numeral 4.2: plazo de 30 dias naturales para etapa B.")
    candidate_b = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p_b,
        normalized_content_id=n_b,
        source_page=2,
        text="Numeral 4.2: el participante debera entregar etapa B en 30 dias naturales.",
    )

    p_new, n_new = _seed_page_and_normalized(source_doc_id, 1, "Numeral 4.2: plazo de 45 dias naturales.")
    candidate_new = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=source_doc_id,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="Numeral 4.2: el participante debera entregar en 45 dias naturales.",
    )

    _seed_page_and_normalized(source_doc_id, 2, "Se modifica el Anexo D en el numeral 4.2, de 30 dias naturales a 45 dias naturales.")

    _seed_requirement_from_candidate(tender_id, candidate_a, "REQ_A_N4_2_30", "req-a-n42")
    _seed_requirement_from_candidate(tender_id, candidate_b, "REQ_B_N4_2_30", "req-b-n42")
    _seed_requirement_from_candidate(tender_id, candidate_new, "REQ_N4_2_45", "req-new-n42")

    changes = _analyze_changes(tender_id)
    _confirm_change(tender_id, changes["changes"][0]["id"])

    payload = _analyze_requirement_versions(tender_id)

    assert payload["summary"]["version_link_count"] == 0
    assert payload["summary"]["ambiguous_count"] >= 1


def test_analyze_versions_does_not_create_new_requirements() -> None:
    tender_id = _create_tender("REQ VER no requirement creation")
    target_doc_id = _import_pdf(tender_id, "anexo d.pdf")

    p1, n1 = _seed_page_and_normalized(target_doc_id, 1, "El participante debera presentar acta constitutiva.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p1,
        normalized_content_id=n1,
        source_page=1,
        text="El participante debera presentar acta constitutiva.",
    )

    _normalize_requirements(tender_id)
    before_count = _requirement_count(tender_id)

    _analyze_requirement_versions(tender_id)
    after_count = _requirement_count(tender_id)

    assert before_count == after_count


def test_suggested_change_does_not_create_effective_link() -> None:
    tender_id = _create_tender("REQ VER suggested no authority")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta-a.pdf")

    p_old, n_old = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: plazo de 30 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=base_doc,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir plazo de 30 dias naturales.",
    )
    p_new, n_new = _seed_page_and_normalized(junta_doc, 1, "Numeral 4.2: plazo de 45 dias naturales.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=junta_doc,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="Numeral 4.2: el participante debera cumplir plazo de 45 dias naturales.",
    )

    _normalize_requirements(tender_id)
    _seed_change(
        tender_id=tender_id,
        source_document_id=junta_doc,
        target_document_id=base_doc,
        locator="numeral 4.2",
        before_text="30 dias naturales",
        after_text="45 dias naturales",
        review_status="SUGGESTED",
    )

    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 0
    assert all(item["effective_status"] == "EFFECTIVE" for item in payload["requirements"])


def test_version_chain_a_to_b_to_c() -> None:
    tender_id = _create_tender("REQ VER chain")
    doc_a = _import_pdf(tender_id, "anexo d v1.pdf")
    doc_b = _import_pdf(tender_id, "anexo d v2.pdf")
    doc_c = _import_pdf(tender_id, "anexo d v3.pdf")

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

    payload = _analyze_requirement_versions(tender_id)
    status_by_text = {row["canonical_text"]: row["effective_status"] for row in payload["requirements"]}
    assert status_by_text["REQ_A_30"] == "SUPERSEDED"
    assert status_by_text["REQ_B_40"] == "SUPERSEDED"
    assert status_by_text["REQ_C_45"] == "EFFECTIVE"


def test_precedence_uses_effective_state_not_created_at() -> None:
    tender_id = _create_tender("REQ VER precedence")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    src_old = _import_pdf(tender_id, "junta-old.pdf")
    src_new = _import_pdf(tender_id, "junta-new.pdf")

    p_base, n_base = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: plazo de 30 dias naturales.")
    c_base = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=base_doc,
        page_id=p_base,
        normalized_content_id=n_base,
        source_page=1,
        text="REQ_BASE 30 dias naturales numeral 4.2",
    )
    p_old, n_old = _seed_page_and_normalized(src_old, 1, "Numeral 4.2: plazo de 40 dias naturales.")
    c_old = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=src_old,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="REQ_OLD 40 dias naturales numeral 4.2",
    )
    p_new, n_new = _seed_page_and_normalized(src_new, 1, "Numeral 4.2: plazo de 45 dias naturales.")
    c_new = _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=src_new,
        page_id=p_new,
        normalized_content_id=n_new,
        source_page=1,
        text="REQ_NEW 45 dias naturales numeral 4.2",
    )

    _seed_requirement_from_candidate(tender_id, c_base, "REQ_BASE_30", "pre-base")
    _seed_requirement_from_candidate(tender_id, c_old, "REQ_OLD_40", "pre-old")
    _seed_requirement_from_candidate(tender_id, c_new, "REQ_NEW_45", "pre-new")

    _seed_change(
        tender_id=tender_id,
        source_document_id=src_old,
        target_document_id=base_doc,
        locator="numeral 4.2",
        before_text="REQ_BASE 30 dias naturales numeral 4.2",
        after_text="REQ_OLD 40 dias naturales numeral 4.2",
        review_status="CONFIRMED",
    )
    _seed_change(
        tender_id=tender_id,
        source_document_id=src_new,
        target_document_id=base_doc,
        locator="numeral 4.2",
        before_text="REQ_BASE 30 dias naturales numeral 4.2",
        after_text="REQ_NEW 45 dias naturales numeral 4.2",
        review_status="CONFIRMED",
    )

    _seed_event(
        tender_id=tender_id,
        source_document_id=src_old,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 1),
    )
    _seed_event(
        tender_id=tender_id,
        source_document_id=src_new,
        event_type="ADDENDUM_PUBLICATION",
        review_status="CONFIRMED",
        event_date=date(2026, 8, 9),
    )

    payload = _analyze_requirement_versions(tender_id)
    target = _find_requirement(payload, "REQ_NEW_45")
    assert target["effective_status"] == "EFFECTIVE"


def test_created_order_independence_for_same_logical_precedence() -> None:
    tender_a = _create_tender("REQ VER order A")
    base_a = _import_pdf(tender_a, "anexo d.pdf")
    old_a = _import_pdf(tender_a, "junta-old.pdf")
    new_a = _import_pdf(tender_a, "junta-new.pdf")

    pa1, na1 = _seed_page_and_normalized(base_a, 1, "Numeral 4.2: plazo 30.")
    ca1 = _seed_requirement_candidate(tender_id=tender_a, document_id=base_a, page_id=pa1, normalized_content_id=na1, source_page=1, text="A_BASE 30 numeral 4.2")
    pa2, na2 = _seed_page_and_normalized(old_a, 1, "Numeral 4.2: plazo 40.")
    ca2 = _seed_requirement_candidate(tender_id=tender_a, document_id=old_a, page_id=pa2, normalized_content_id=na2, source_page=1, text="A_OLD 40 numeral 4.2")
    pa3, na3 = _seed_page_and_normalized(new_a, 1, "Numeral 4.2: plazo 45.")
    ca3 = _seed_requirement_candidate(tender_id=tender_a, document_id=new_a, page_id=pa3, normalized_content_id=na3, source_page=1, text="A_NEW 45 numeral 4.2")
    _seed_requirement_from_candidate(tender_a, ca1, "A_BASE_30", "ord-a-base")
    _seed_requirement_from_candidate(tender_a, ca2, "A_OLD_40", "ord-a-old")
    _seed_requirement_from_candidate(tender_a, ca3, "A_NEW_45", "ord-a-new")
    _seed_change(tender_id=tender_a, source_document_id=old_a, target_document_id=base_a, locator="numeral 4.2", before_text="A_BASE 30 numeral 4.2", after_text="A_OLD 40 numeral 4.2", review_status="CONFIRMED")
    _seed_change(tender_id=tender_a, source_document_id=new_a, target_document_id=base_a, locator="numeral 4.2", before_text="A_BASE 30 numeral 4.2", after_text="A_NEW 45 numeral 4.2", review_status="CONFIRMED")
    _seed_event(tender_id=tender_a, source_document_id=old_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 1))
    _seed_event(tender_id=tender_a, source_document_id=new_a, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 9))
    out_a = _analyze_requirement_versions(tender_a)

    tender_b = _create_tender("REQ VER order B")
    base_b = _import_pdf(tender_b, "anexo d.pdf")
    new_b = _import_pdf(tender_b, "junta-new.pdf")
    old_b = _import_pdf(tender_b, "junta-old.pdf")

    pb1, nb1 = _seed_page_and_normalized(base_b, 1, "Numeral 4.2: plazo 30.")
    cb1 = _seed_requirement_candidate(tender_id=tender_b, document_id=base_b, page_id=pb1, normalized_content_id=nb1, source_page=1, text="B_BASE 30 numeral 4.2")
    pb2, nb2 = _seed_page_and_normalized(new_b, 1, "Numeral 4.2: plazo 45.")
    cb2 = _seed_requirement_candidate(tender_id=tender_b, document_id=new_b, page_id=pb2, normalized_content_id=nb2, source_page=1, text="B_NEW 45 numeral 4.2")
    pb3, nb3 = _seed_page_and_normalized(old_b, 1, "Numeral 4.2: plazo 40.")
    cb3 = _seed_requirement_candidate(tender_id=tender_b, document_id=old_b, page_id=pb3, normalized_content_id=nb3, source_page=1, text="B_OLD 40 numeral 4.2")
    _seed_requirement_from_candidate(tender_b, cb1, "B_BASE_30", "ord-b-base")
    _seed_requirement_from_candidate(tender_b, cb2, "B_NEW_45", "ord-b-new")
    _seed_requirement_from_candidate(tender_b, cb3, "B_OLD_40", "ord-b-old")
    _seed_change(tender_id=tender_b, source_document_id=new_b, target_document_id=base_b, locator="numeral 4.2", before_text="B_BASE 30 numeral 4.2", after_text="B_NEW 45 numeral 4.2", review_status="CONFIRMED")
    _seed_change(tender_id=tender_b, source_document_id=old_b, target_document_id=base_b, locator="numeral 4.2", before_text="B_BASE 30 numeral 4.2", after_text="B_OLD 40 numeral 4.2", review_status="CONFIRMED")
    _seed_event(tender_id=tender_b, source_document_id=old_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 1))
    _seed_event(tender_id=tender_b, source_document_id=new_b, event_type="ADDENDUM_PUBLICATION", review_status="CONFIRMED", event_date=date(2026, 8, 9))
    out_b = _analyze_requirement_versions(tender_b)

    assert _find_requirement(out_a, "A_NEW_45")["effective_status"] == "EFFECTIVE"
    assert _find_requirement(out_b, "B_NEW_45")["effective_status"] == "EFFECTIVE"


def test_junta_document_without_confirmed_mutation_does_not_supersede() -> None:
    tender_id = _create_tender("REQ VER junta no authority")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "El participante debera presentar garantia de seriedad.")
    _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="REQ_GARANTIA_BASE")
    p2, n2 = _seed_page_and_normalized(junta_doc, 1, "El participante debera presentar garantia y carta adicional.")
    _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p2, normalized_content_id=n2, source_page=1, text="REQ_GARANTIA_JUNTA")

    _normalize_requirements(tender_id)
    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 0


def test_confirmed_change_from_junta_has_authority_via_change_status() -> None:
    tender_id = _create_tender("REQ VER junta confirmed")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    p_old, n_old = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: 30 dias naturales.")
    c_old = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p_old, normalized_content_id=n_old, source_page=1, text="J_BASE_30 numeral 4.2")
    p_new, n_new = _seed_page_and_normalized(junta_doc, 1, "Numeral 4.2: 45 dias naturales.")
    c_new = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p_new, normalized_content_id=n_new, source_page=1, text="J_NEW_45 numeral 4.2")
    _seed_requirement_from_candidate(tender_id, c_old, "J_BASE", "j-base")
    _seed_requirement_from_candidate(tender_id, c_new, "J_NEW", "j-new")

    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="J_BASE_30 numeral 4.2", after_text="J_NEW_45 numeral 4.2", review_status="CONFIRMED")

    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 1


def test_analyze_versions_is_idempotent_without_duplicate_links() -> None:
    tender_id = _create_tender("REQ VER idempotent")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: valor 30.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="IDEM_30 numeral 4.2")
    p2, n2 = _seed_page_and_normalized(junta_doc, 1, "Numeral 4.2: valor 45.")
    c2 = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p2, normalized_content_id=n2, source_page=1, text="IDEM_45 numeral 4.2")
    _seed_requirement_from_candidate(tender_id, c1, "IDEM_BASE", "idem-base")
    _seed_requirement_from_candidate(tender_id, c2, "IDEM_NEW", "idem-new")
    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="IDEM_30 numeral 4.2", after_text="IDEM_45 numeral 4.2", review_status="CONFIRMED")

    out1 = _analyze_requirement_versions(tender_id)
    out2 = _analyze_requirement_versions(tender_id)
    links = _get_version_links(tender_id)

    assert out1["summary"] == out2["summary"]
    assert len(links) == out1["summary"]["version_link_count"]


def test_requirement_semantics_immutability_during_version_analysis() -> None:
    tender_id = _create_tender("REQ VER semantics immutable")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "El participante debera presentar certificado ISO 9001.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="IMM_BASE certificado ISO 9001")
    p2, n2 = _seed_page_and_normalized(junta_doc, 1, "El participante debera presentar certificado ISO 14001.")
    c2 = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p2, normalized_content_id=n2, source_page=1, text="IMM_NEW certificado ISO 14001")

    _seed_requirement_from_candidate(tender_id, c1, "IMM_BASE", "imm-base")
    _seed_requirement_from_candidate(tender_id, c2, "IMM_NEW", "imm-new")
    _analyze_requirement_semantics(tender_id)

    before_sem, before_exp = _snapshot_semantics_state(tender_id)
    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="IMM_BASE certificado ISO 9001", after_text="IMM_NEW certificado ISO 14001", review_status="CONFIRMED")

    _analyze_requirement_versions(tender_id)
    after_sem, after_exp = _snapshot_semantics_state(tender_id)

    assert before_sem == after_sem
    assert before_exp == after_exp


def test_complementary_similar_requirements_remain_effective_without_change_evidence() -> None:
    tender_id = _create_tender("REQ VER complementary")
    base_doc = _import_pdf(tender_id, "bases.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "El participante debera presentar curriculum del personal tecnico.")
    _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="REQ_CV_PERSONAL")
    p2, n2 = _seed_page_and_normalized(base_doc, 2, "El participante debera presentar certificaciones del personal tecnico.")
    _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p2, normalized_content_id=n2, source_page=2, text="REQ_CERT_PERSONAL")

    _normalize_requirements(tender_id)
    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 0
    assert all(item["effective_status"] == "EFFECTIVE" for item in payload["requirements"])


def test_multiple_sources_same_canonical_requirement_does_not_create_version_edge() -> None:
    tender_id = _create_tender("REQ VER multi source same canonical")
    doc_a = _import_pdf(tender_id, "bases.pdf")
    doc_b = _import_pdf(tender_id, "anexo d.pdf")

    p1, n1 = _seed_page_and_normalized(doc_a, 1, "El participante debera presentar garantia de seriedad.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=doc_a, page_id=p1, normalized_content_id=n1, source_page=1, text="SAME_CANONICAL")
    p2, n2 = _seed_page_and_normalized(doc_b, 1, "El participante debera presentar garantia de seriedad.")
    c2 = _seed_requirement_candidate(tender_id=tender_id, document_id=doc_b, page_id=p2, normalized_content_id=n2, source_page=1, text="SAME_CANONICAL")

    req_id = _seed_requirement_from_candidate(tender_id, c1, "SAME_CANONICAL", "same-canonical")
    db = SessionLocal()
    try:
        db.add(
            RequirementCandidateLink(
                requirement_id=req_id,
                requirement_candidate_id=c2,
                is_primary_source=False,
                link_origin="DETERMINISTIC",
            )
        )
        db.commit()
    finally:
        db.close()

    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 0


def test_confirmed_change_without_successor_requirement_marks_unresolved_without_creation() -> None:
    tender_id = _create_tender("REQ VER unresolved no successor")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: monto base 30.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="UNRES_BASE 30 numeral 4.2")
    _seed_requirement_from_candidate(tender_id, c1, "UNRES_BASE", "unres-base")

    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="UNRES_BASE 30 numeral 4.2", after_text="UNMATCHED_SUCCESSOR_TEXT", review_status="CONFIRMED")

    before_count = _requirement_count(tender_id)
    payload = _analyze_requirement_versions(tender_id)
    after_count = _requirement_count(tender_id)

    assert payload["summary"]["version_link_count"] == 0
    assert payload["summary"]["unresolved_count"] >= 1
    assert before_count == after_count


def test_ambiguous_successor_mapping_does_not_pick_one() -> None:
    tender_id = _create_tender("REQ VER ambiguous successor")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: monto base 30.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="AMB_BASE 30 numeral 4.2")
    p2, n2 = _seed_page_and_normalized(junta_doc, 1, "Numeral 4.2: alternativa A 45.")
    c2 = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p2, normalized_content_id=n2, source_page=1, text="AMB_SUC_A numeral 4.2")
    p3, n3 = _seed_page_and_normalized(junta_doc, 2, "Numeral 4.2: alternativa B 45.")
    c3 = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p3, normalized_content_id=n3, source_page=2, text="AMB_SUC_B numeral 4.2")

    _seed_requirement_from_candidate(tender_id, c1, "AMB_BASE", "amb-base")
    _seed_requirement_from_candidate(tender_id, c2, "AMB_SUC_A", "amb-suc-a")
    _seed_requirement_from_candidate(tender_id, c3, "AMB_SUC_B", "amb-suc-b")

    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="AMB_BASE 30 numeral 4.2", after_text="numeral 4.2", review_status="CONFIRMED")

    payload = _analyze_requirement_versions(tender_id)
    assert payload["summary"]["version_link_count"] == 0
    assert payload["summary"]["ambiguous_count"] >= 1 or payload["summary"]["unresolved_count"] >= 1


def test_self_supersession_protection_has_no_self_link() -> None:
    tender_id = _create_tender("REQ VER no self link")
    base_doc = _import_pdf(tender_id, "anexo d.pdf")
    junta_doc = _import_pdf(tender_id, "junta.pdf")

    p1, n1 = _seed_page_and_normalized(base_doc, 1, "Numeral 4.2: entrega en 30 dias.")
    c1 = _seed_requirement_candidate(tender_id=tender_id, document_id=base_doc, page_id=p1, normalized_content_id=n1, source_page=1, text="SELF_CANONICAL")
    p2, n2 = _seed_page_and_normalized(junta_doc, 1, "Numeral 4.2: entrega en 45 dias.")
    c2 = _seed_requirement_candidate(tender_id=tender_id, document_id=junta_doc, page_id=p2, normalized_content_id=n2, source_page=1, text="SELF_CANONICAL")

    req_id = _seed_requirement_from_candidate(tender_id, c1, "SELF_CANONICAL", "self-canonical")
    db = SessionLocal()
    try:
        db.add(
            RequirementCandidateLink(
                requirement_id=req_id,
                requirement_candidate_id=c2,
                is_primary_source=False,
                link_origin="DETERMINISTIC",
            )
        )
        db.commit()
    finally:
        db.close()

    _seed_change(tender_id=tender_id, source_document_id=junta_doc, target_document_id=base_doc, locator="numeral 4.2", before_text="SELF_CANONICAL", after_text="SELF_CANONICAL", review_status="CONFIRMED")
    _analyze_requirement_versions(tender_id)
    links = _get_version_links(tender_id)

    assert all(link.predecessor_requirement_id != link.successor_requirement_id for link in links)
