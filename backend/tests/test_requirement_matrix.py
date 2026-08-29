from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    DocumentRelationship,
    EvaluationCriterion,
    DocumentPage,
    NormalizedContent,
    Requirement,
    RequirementCandidate,
    RequirementCandidateEvidence,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementReview,
    RequirementSemantics,
    RequirementVersionLink,
    TenderChange,
    TenderChangeEvidence,
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
            "external_reference": "REQ-MATRIX-001",
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

        document = db.get(TenderDocument, document_id)
        assert document is not None
        document.page_count = max(document.page_count, page_number)
        document.processing_status = "TEXT_EXTRACTION_COMPLETE"

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


def _prepare_requirement_pipeline(tender_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert response.status_code == 200, response.text
    return response.json()


def _get_matrix(tender_id: str) -> dict:
    response = client.get(f"/tenders/{tender_id}/requirement-matrix")
    assert response.status_code == 200, response.text
    return response.json()


def _patch_review(tender_id: str, requirement_id: str, action: str, review_note: str | None = None) -> dict:
    payload: dict[str, str] = {"action": action}
    if review_note is not None:
        payload["review_note"] = review_note
    response = client.patch(f"/tenders/{tender_id}/requirements/{requirement_id}/review", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _first_requirement_id(tender_id: str) -> str:
    matrix = _get_matrix(tender_id)
    assert matrix["requirements"]
    return matrix["requirements"][0]["requirement_id"]


def _seed_basic_requirement(tender_id: str, filename: str, requirement_text: str) -> str:
    doc_id = _import_pdf(tender_id, filename)
    page_id, normalized_id = _seed_page_and_normalized(doc_id, 1, requirement_text)
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=doc_id,
        page_id=page_id,
        normalized_content_id=normalized_id,
        source_page=1,
        text=requirement_text,
    )
    _prepare_requirement_pipeline(tender_id)
    return _first_requirement_id(tender_id)


def _find_matrix_row(matrix: dict, requirement_id: str) -> dict:
    for row in matrix["requirements"]:
        if row["requirement_id"] == requirement_id:
            return row
    raise AssertionError("Requirement row not found in matrix")


def test_requirement_matrix_initial_state_is_pending_not_reviewed() -> None:
    tender_id = _create_tender("REQ MATRIX initial")
    _seed_basic_requirement(
        tender_id,
        "anexo_d.pdf",
        "El participante debera presentar constancia fiscal vigente.",
    )

    payload = _get_matrix(tender_id)

    assert payload["summary"]["total_requirements"] == 1
    assert payload["summary"]["pending_review_count"] == 1
    row = payload["requirements"][0]
    assert row["review_status"] == "PENDING"
    assert row["review_freshness"] == "NOT_REVIEWED"


def test_approve_review_marks_current_freshness() -> None:
    tender_id = _create_tender("REQ MATRIX approve")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_i.pdf",
        "El participante debera entregar curriculum del personal propuesto.",
    )

    payload = _patch_review(tender_id, requirement_id, "APPROVE", "Representacion validada")
    row = payload["requirements"][0]

    assert row["review_status"] == "APPROVED"
    assert row["review_freshness"] == "CURRENT"
    assert row["reviewed_at"] is not None


def test_reject_requires_note() -> None:
    tender_id = _create_tender("REQ MATRIX reject")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_h.pdf",
        "El participante debera anexar carta de confidencialidad firmada.",
    )

    response = client.patch(
        f"/tenders/{tender_id}/requirements/{requirement_id}/review",
        json={"action": "REJECT"},
    )
    assert response.status_code == 400
    assert "review_note is required" in response.text

    ok = _patch_review(tender_id, requirement_id, "REJECT", "No es requisito verificable")
    row = ok["requirements"][0]
    assert row["review_status"] == "REJECTED"
    assert row["review_note"] == "No es requisito verificable"


def test_reset_returns_pending_not_reviewed() -> None:
    tender_id = _create_tender("REQ MATRIX reset")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_f.pdf",
        "El participante debera integrar manifestacion bajo protesta.",
    )

    _patch_review(tender_id, requirement_id, "MARK_NEEDS_REVIEW", "Ambiguo")
    payload = _patch_review(tender_id, requirement_id, "RESET")
    row = payload["requirements"][0]

    assert row["review_status"] == "PENDING"
    assert row["review_note"] is None
    assert row["review_freshness"] == "NOT_REVIEWED"
    assert row["reviewed_at"] is None


def test_review_becomes_stale_when_requirement_representation_changes() -> None:
    tender_id = _create_tender("REQ MATRIX stale")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_k.pdf",
        "El participante debera presentar evidencia de experiencia minima.",
    )

    _patch_review(tender_id, requirement_id, "APPROVE", "OK")

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        requirement.canonical_text = "El participante debera presentar evidencia de experiencia minima comprobable."
        db.commit()
    finally:
        db.close()

    payload = _get_matrix(tender_id)
    row = payload["requirements"][0]
    assert row["review_status"] == "APPROVED"
    assert row["review_freshness"] == "STALE"


def test_cross_tender_review_update_is_rejected() -> None:
    tender_a = _create_tender("REQ MATRIX cross A")
    tender_b = _create_tender("REQ MATRIX cross B")

    _seed_basic_requirement(tender_a, "a.pdf", "El participante debera incluir constancia SAT.")
    requirement_b = _seed_basic_requirement(tender_b, "b.pdf", "El participante debera incluir carta de no inhabilitacion.")

    response = client.patch(
        f"/tenders/{tender_a}/requirements/{requirement_b}/review",
        json={"action": "APPROVE"},
    )

    assert response.status_code == 404


def test_review_overlay_does_not_mutate_derived_layers() -> None:
    tender_id = _create_tender("REQ MATRIX overlay")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_q.pdf",
        "El participante debera presentar declaracion de integridad.",
    )

    db = SessionLocal()
    try:
        requirement_before = db.get(Requirement, requirement_id)
        assert requirement_before is not None
        before_tuple = (
            requirement_before.canonical_text,
            requirement_before.category,
            requirement_before.normalization_status,
            requirement_before.normalization_reason,
        )

        semantics_before = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one_or_none()
        semantics_tuple = None
        if semantics_before is not None:
            semantics_tuple = (
                semantics_before.applicability,
                semantics_before.interpretation_status,
                semantics_before.evidence_mode,
            )

        links_before = db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    _patch_review(tender_id, requirement_id, "MARK_NEEDS_REVIEW", "Revisar redaccion")

    db = SessionLocal()
    try:
        requirement_after = db.get(Requirement, requirement_id)
        assert requirement_after is not None
        after_tuple = (
            requirement_after.canonical_text,
            requirement_after.category,
            requirement_after.normalization_status,
            requirement_after.normalization_reason,
        )
        assert after_tuple == before_tuple

        semantics_after = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one_or_none()
        semantics_after_tuple = None
        if semantics_after is not None:
            semantics_after_tuple = (
                semantics_after.applicability,
                semantics_after.interpretation_status,
                semantics_after.evidence_mode,
            )
        assert semantics_after_tuple == semantics_tuple

        links_after = db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one()
        assert links_after == links_before

        review_row = db.execute(select(RequirementReview).where(RequirementReview.requirement_id == requirement_id)).scalar_one_or_none()
        assert review_row is not None
        assert review_row.review_status == "NEEDS_REVIEW"
    finally:
        db.close()


def test_matrix_payload_has_no_compliance_fields() -> None:
    tender_id = _create_tender("REQ MATRIX no compliance")
    _seed_basic_requirement(
        tender_id,
        "anexo_m.pdf",
        "El participante debera adjuntar registro patronal vigente.",
    )

    payload = _get_matrix(tender_id)
    row = payload["requirements"][0]

    forbidden = {"compliance_status", "company_match_status", "matched_company_evidence_id", "compliance_score"}
    assert forbidden.isdisjoint(set(row.keys()))


def test_needs_review_is_independent_from_automatic_review_required() -> None:
    tender_id = _create_tender("REQ MATRIX needs review independence")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_u.pdf",
        "El participante debera presentar evidencia de cumplimiento aplicable.",
    )

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        requirement.normalization_status = "REVIEW_REQUIRED"
        semantics = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one()
        semantics.interpretation_status = "REVIEW_REQUIRED"
        db.commit()
    finally:
        db.close()

    payload = _patch_review(tender_id, requirement_id, "MARK_NEEDS_REVIEW", "Necesita aclaracion")
    row = _find_matrix_row(payload, requirement_id)
    assert row["review_status"] == "NEEDS_REVIEW"
    assert row["interpretation_status"] == "REVIEW_REQUIRED"
    assert "INTERPRETATION_REVIEW_REQUIRED" in row["system_warnings"]


def test_human_approval_does_not_erase_system_warnings() -> None:
    tender_id = _create_tender("REQ MATRIX warning coexistence")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_warn.pdf",
        "El participante debera presentar evidencia que requiere aclaracion.",
    )

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        requirement.normalization_status = "REVIEW_REQUIRED"
        semantics = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one()
        semantics.interpretation_status = "REVIEW_REQUIRED"
        semantics.evidence_mode = "REVIEW_REQUIRED"
        db.commit()
    finally:
        db.close()

    payload = _patch_review(tender_id, requirement_id, "APPROVE", "Aprobado por revisión humana")
    row = _find_matrix_row(payload, requirement_id)

    assert row["review_status"] == "APPROVED"
    assert "NORMALIZATION_REVIEW_REQUIRED" in row["system_warnings"]
    assert "INTERPRETATION_REVIEW_REQUIRED" in row["system_warnings"]
    assert "EVIDENCE_DEFINITION_REVIEW_REQUIRED" in row["system_warnings"]


def test_reject_keeps_requirement_physically_present() -> None:
    tender_id = _create_tender("REQ MATRIX reject keep requirement")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_v.pdf",
        "El participante debera presentar carta bajo protesta.",
    )

    _patch_review(tender_id, requirement_id, "REJECT", "No representa un requisito operativo")

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        review = db.execute(select(RequirementReview).where(RequirementReview.requirement_id == requirement_id)).scalar_one_or_none()
        assert review is not None
        assert review.review_status == "REJECTED"
    finally:
        db.close()


def test_patch_idempotency_reuses_single_review_row() -> None:
    tender_id = _create_tender("REQ MATRIX idempotent")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_w.pdf",
        "El participante debera incluir registro patronal.",
    )

    _patch_review(tender_id, requirement_id, "APPROVE", "Primera")
    _patch_review(tender_id, requirement_id, "APPROVE", "Primera")

    db = SessionLocal()
    try:
        count = db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.requirement_id == requirement_id)).scalar_one()
        assert count == 1
    finally:
        db.close()


def test_get_requirement_matrix_is_read_only() -> None:
    tender_id = _create_tender("REQ MATRIX readonly")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_x.pdf",
        "El participante debera incluir documentacion legal requerida.",
    )

    db = SessionLocal()
    try:
        requirement_count_before = db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one()
        review_count_before = db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one()
        semantics_count_before = db.execute(
            select(func.count(RequirementSemantics.id)).join(Requirement, Requirement.id == RequirementSemantics.requirement_id).where(Requirement.tender_id == tender_id)
        ).scalar_one()
        version_links_before = db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one()
        change_count_before = db.execute(select(func.count(TenderChange.id)).where(TenderChange.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    _get_matrix(tender_id)
    _get_matrix(tender_id)
    _get_matrix(tender_id)

    db = SessionLocal()
    try:
        requirement_count_after = db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one()
        review_count_after = db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one()
        semantics_count_after = db.execute(
            select(func.count(RequirementSemantics.id)).join(Requirement, Requirement.id == RequirementSemantics.requirement_id).where(Requirement.tender_id == tender_id)
        ).scalar_one()
        version_links_after = db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one()
        change_count_after = db.execute(select(func.count(TenderChange.id)).where(TenderChange.tender_id == tender_id)).scalar_one()
    finally:
        db.close()

    assert requirement_count_after == requirement_count_before
    assert review_count_after == review_count_before
    assert semantics_count_after == semantics_count_before
    assert version_links_after == version_links_before
    assert change_count_after == change_count_before

    payload = _get_matrix(tender_id)
    row = _find_matrix_row(payload, requirement_id)
    assert row["review_status"] == "PENDING"


def test_no_auto_approval_for_normalized_determined_effective_requirement() -> None:
    tender_id = _create_tender("REQ MATRIX no auto approve")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_y.pdf",
        "El participante debera presentar propuesta en idioma espanol.",
    )

    payload = _get_matrix(tender_id)
    row = _find_matrix_row(payload, requirement_id)

    assert row["normalization_status"] == "NORMALIZED"
    assert row["interpretation_status"] == "DETERMINED"
    assert row["effective_status"] == "EFFECTIVE"
    assert row["review_status"] == "PENDING"


def test_reanalysis_preserves_human_review() -> None:
    tender_id = _create_tender("REQ MATRIX reanalysis preserve")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_z.pdf",
        "El participante debera presentar certificado vigente del fabricante.",
    )

    _patch_review(tender_id, requirement_id, "APPROVE", "Revision valida")

    response = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert response.status_code == 200, response.text
    response = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert response.status_code == 200, response.text

    matrix = _get_matrix(tender_id)
    row = _find_matrix_row(matrix, requirement_id)
    assert row["review_status"] == "APPROVED"
    assert row["review_note"] == "Revision valida"
    assert row["review_freshness"] == "CURRENT"


def test_timestamp_only_changes_do_not_mark_review_stale() -> None:
    tender_id = _create_tender("REQ MATRIX timestamp no stale")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_ts.pdf",
        "El participante debera integrar curriculum y cedula.",
    )

    baseline = _patch_review(tender_id, requirement_id, "APPROVE", "OK")
    baseline_row = _find_matrix_row(baseline, requirement_id)
    baseline_fingerprint = baseline_row["representation_fingerprint"]

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        requirement.updated_at = requirement.updated_at
        semantics = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one_or_none()
        if semantics is not None:
            semantics.updated_at = semantics.updated_at
        db.commit()
    finally:
        db.close()

    payload = _get_matrix(tender_id)
    row = _find_matrix_row(payload, requirement_id)
    assert row["review_status"] == "APPROVED"
    assert row["review_freshness"] == "CURRENT"
    assert row["representation_fingerprint"] == baseline_fingerprint


def test_fingerprint_is_deterministic_across_expected_evidence_row_order() -> None:
    tender_id = _create_tender("REQ MATRIX fingerprint deterministic")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_ord.pdf",
        "El participante debera anexar evidencia documental de experiencia.",
    )

    db = SessionLocal()
    try:
        semantics = db.execute(select(RequirementSemantics).where(RequirementSemantics.requirement_id == requirement_id)).scalar_one_or_none()
        assert semantics is not None
        db.add(
            RequirementEvidenceExpectation(
                requirement_semantics_id=semantics.id,
                requirement_id=requirement_id,
                evidence_type="CERTIFICATE",
                evidence_description="Constancia adicional",
                source_candidate_id=None,
                source_document_id=None,
                source_page=None,
                source_excerpt="Constancia adicional",
                excerpt_sha256=hashlib.sha256(b"Constancia adicional").hexdigest(),
                analyzer_version="mvp-04.4",
            )
        )
        db.add(
            RequirementEvidenceExpectation(
                requirement_semantics_id=semantics.id,
                requirement_id=requirement_id,
                evidence_type="LETTER",
                evidence_description="Carta adicional",
                source_candidate_id=None,
                source_document_id=None,
                source_page=None,
                source_excerpt="Carta adicional",
                excerpt_sha256=hashlib.sha256(b"Carta adicional").hexdigest(),
                analyzer_version="mvp-04.4",
            )
        )
        db.commit()
    finally:
        db.close()

    first = _get_matrix(tender_id)
    first_row = _find_matrix_row(first, requirement_id)
    first_fp = first_row["representation_fingerprint"]

    db = SessionLocal()
    try:
        expectations = db.execute(
            select(RequirementEvidenceExpectation)
            .where(RequirementEvidenceExpectation.requirement_id == requirement_id)
            .order_by(RequirementEvidenceExpectation.id.desc())
        ).scalars().all()
        for item in expectations:
            item.source_excerpt = f"{item.source_excerpt}"
        db.commit()
    finally:
        db.close()

    second = _get_matrix(tender_id)
    second_row = _find_matrix_row(second, requirement_id)
    assert second_row["representation_fingerprint"] == first_fp


def test_successor_review_non_inheritance_and_historical_traceability() -> None:
    tender_id = _create_tender("REQ MATRIX successor")
    target_doc_id = _import_pdf(tender_id, "anexo_d_target.pdf")
    source_doc_id = _import_pdf(tender_id, "junta_source.pdf")

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

    normalized = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert normalized.status_code == 200, normalized.text
    requirements = normalized.json()["requirements"]
    old_req = next(item for item in requirements if "30 dias naturales" in item["canonical_text"])
    new_req = next(item for item in requirements if "45 dias naturales" in item["canonical_text"])

    _patch_review(tender_id, old_req["id"], "APPROVE", "Version inicial validada")

    db = SessionLocal()
    try:
        semantic = "|".join([tender_id, source_doc_id, target_doc_id, "numeral 4.2", "30 dias naturales", "45 dias naturales", "MODIFIES"])
        db.add(
            TenderChange(
                tender_id=tender_id,
                semantic_key=hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
                change_type="MODIFIES",
                target_reference_key="ANEXO:D",
                target_document_id=target_doc_id,
                target_candidate_document_ids=target_doc_id,
                target_locator_text="numeral 4.2",
                before_text="30 dias naturales",
                after_text="45 dias naturales",
                source_document_id=source_doc_id,
                source_page=1,
                source_excerpt="Se modifica numeral 4.2",
                review_status="CONFIRMED",
                detection_origin="DETERMINISTIC",
                detector_version="mvp-03.3",
            )
        )
        db.commit()
    finally:
        db.close()

    versions = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert versions.status_code == 200, versions.text

    matrix = _get_matrix(tender_id)
    old_row = _find_matrix_row(matrix, old_req["id"])
    new_row = _find_matrix_row(matrix, new_req["id"])

    assert old_row["effective_status"] == "SUPERSEDED"
    assert old_row["review_status"] == "APPROVED"
    assert new_row["effective_status"] == "EFFECTIVE"
    assert new_row["review_status"] == "PENDING"
    assert new_row["review_freshness"] == "NOT_REVIEWED"

    db = SessionLocal()
    try:
        old_review = db.execute(select(RequirementReview).where(RequirementReview.requirement_id == old_req["id"])).scalar_one_or_none()
        new_review = db.execute(select(RequirementReview).where(RequirementReview.requirement_id == new_req["id"])).scalar_one_or_none()
        assert old_review is not None
        assert old_review.review_status == "APPROVED"
        assert new_review is None
    finally:
        db.close()


def test_human_approval_does_not_resolve_unresolved_effective_status() -> None:
    tender_id = _create_tender("REQ MATRIX unresolved isolation")
    target_doc_id = _import_pdf(tender_id, "anexo_d_target_u.pdf")
    source_doc_id = _import_pdf(tender_id, "junta_source_u.pdf")

    p_old, n_old = _seed_page_and_normalized(target_doc_id, 1, "Numeral 9.1: plazo de 10 dias.")
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=target_doc_id,
        page_id=p_old,
        normalized_content_id=n_old,
        source_page=1,
        text="Numeral 9.1: el participante debera cumplir un plazo de 10 dias.",
    )

    _seed_page_and_normalized(source_doc_id, 1, "Se modifica el numeral 9.1")
    normalized = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert normalized.status_code == 200, normalized.text
    requirement_id = normalized.json()["requirements"][0]["id"]

    db = SessionLocal()
    try:
        semantic = "|".join([tender_id, source_doc_id, target_doc_id, "numeral 9.1", "10 dias", "20 dias", "MODIFIES"])
        db.add(
            TenderChange(
                tender_id=tender_id,
                semantic_key=hashlib.sha256(semantic.encode("utf-8")).hexdigest(),
                change_type="MODIFIES",
                target_reference_key="ANEXO:D",
                target_document_id=target_doc_id,
                target_candidate_document_ids=target_doc_id,
                target_locator_text="numeral 9.1",
                before_text="10 dias",
                after_text="20 dias",  # no successor candidate should match
                source_document_id=source_doc_id,
                source_page=1,
                source_excerpt="Se modifica numeral 9.1",
                review_status="CONFIRMED",
                detection_origin="DETERMINISTIC",
                detector_version="mvp-03.3",
            )
        )
        db.commit()
    finally:
        db.close()

    versions = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert versions.status_code == 200, versions.text
    row_before = _find_matrix_row(_get_matrix(tender_id), requirement_id)
    assert row_before["effective_status"] == "UNRESOLVED"

    row_after = _find_matrix_row(_patch_review(tender_id, requirement_id, "APPROVE", "Aprobado con reserva"), requirement_id)
    assert row_after["review_status"] == "APPROVED"
    assert row_after["effective_status"] == "UNRESOLVED"


def test_unknown_category_is_visible_and_reviewable() -> None:
    tender_id = _create_tender("REQ MATRIX unknown category")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_unknown.pdf",
        "El participante debera presentar un documento no categorizado.",
    )

    db = SessionLocal()
    try:
        requirement = db.get(Requirement, requirement_id)
        assert requirement is not None
        requirement.category = "UNKNOWN"
        db.commit()
    finally:
        db.close()

    row = _find_matrix_row(_get_matrix(tender_id), requirement_id)
    assert row["category"] == "UNKNOWN"

    row = _find_matrix_row(_patch_review(tender_id, requirement_id, "APPROVE", "OK"), requirement_id)
    assert row["review_status"] == "APPROVED"
    row = _find_matrix_row(_patch_review(tender_id, requirement_id, "MARK_NEEDS_REVIEW", "Revisar"), requirement_id)
    assert row["review_status"] == "NEEDS_REVIEW"
    row = _find_matrix_row(_patch_review(tender_id, requirement_id, "REJECT", "No aplica"), requirement_id)
    assert row["review_status"] == "REJECTED"


def test_review_patch_only_mutates_requirement_review_overlay() -> None:
    tender_id = _create_tender("REQ MATRIX immutability breadth")
    requirement_id = _seed_basic_requirement(
        tender_id,
        "anexo_immut.pdf",
        "El participante debera entregar documentacion requerida.",
    )

    db = SessionLocal()
    try:
        snapshot_before = {
            "candidate_count": db.execute(select(func.count(RequirementCandidate.id)).where(RequirementCandidate.tender_id == tender_id)).scalar_one(),
            "candidate_evidence_count": db.execute(
                select(func.count(RequirementCandidateEvidence.id))
                .join(RequirementCandidate, RequirementCandidate.id == RequirementCandidateEvidence.candidate_id)
                .where(RequirementCandidate.tender_id == tender_id)
            ).scalar_one(),
            "requirement_count": db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one(),
            "candidate_link_count": db.execute(
                select(func.count(RequirementCandidateLink.id))
                .join(Requirement, Requirement.id == RequirementCandidateLink.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "semantics_count": db.execute(
                select(func.count(RequirementSemantics.id))
                .join(Requirement, Requirement.id == RequirementSemantics.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "expectations_count": db.execute(
                select(func.count(RequirementEvidenceExpectation.id))
                .join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "version_link_count": db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one(),
            "evaluation_model_count": db.execute(select(func.count(TenderEvaluationModel.id)).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            "evaluation_criterion_count": db.execute(select(func.count(EvaluationCriterion.id)).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
            "change_count": db.execute(select(func.count(TenderChange.id)).where(TenderChange.tender_id == tender_id)).scalar_one(),
            "change_evidence_count": db.execute(
                select(func.count(TenderChangeEvidence.id))
                .join(TenderChange, TenderChange.id == TenderChangeEvidence.change_id)
                .where(TenderChange.tender_id == tender_id)
            ).scalar_one(),
            "relationship_count": db.execute(
                select(func.count(DocumentRelationship.id))
                .join(TenderDocument, TenderDocument.id == DocumentRelationship.source_document_id)
                .where(TenderDocument.tender_id == tender_id)
            ).scalar_one(),
            "current_docs": db.execute(
                select(func.count(TenderDocument.id)).where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            ).scalar_one(),
            "review_count": db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one(),
        }
    finally:
        db.close()

    _patch_review(tender_id, requirement_id, "APPROVE", "Overlay only")

    db = SessionLocal()
    try:
        snapshot_after = {
            "candidate_count": db.execute(select(func.count(RequirementCandidate.id)).where(RequirementCandidate.tender_id == tender_id)).scalar_one(),
            "candidate_evidence_count": db.execute(
                select(func.count(RequirementCandidateEvidence.id))
                .join(RequirementCandidate, RequirementCandidate.id == RequirementCandidateEvidence.candidate_id)
                .where(RequirementCandidate.tender_id == tender_id)
            ).scalar_one(),
            "requirement_count": db.execute(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)).scalar_one(),
            "candidate_link_count": db.execute(
                select(func.count(RequirementCandidateLink.id))
                .join(Requirement, Requirement.id == RequirementCandidateLink.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "semantics_count": db.execute(
                select(func.count(RequirementSemantics.id))
                .join(Requirement, Requirement.id == RequirementSemantics.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "expectations_count": db.execute(
                select(func.count(RequirementEvidenceExpectation.id))
                .join(Requirement, Requirement.id == RequirementEvidenceExpectation.requirement_id)
                .where(Requirement.tender_id == tender_id)
            ).scalar_one(),
            "version_link_count": db.execute(select(func.count(RequirementVersionLink.id)).where(RequirementVersionLink.tender_id == tender_id)).scalar_one(),
            "evaluation_model_count": db.execute(select(func.count(TenderEvaluationModel.id)).where(TenderEvaluationModel.tender_id == tender_id)).scalar_one(),
            "evaluation_criterion_count": db.execute(select(func.count(EvaluationCriterion.id)).where(EvaluationCriterion.tender_id == tender_id)).scalar_one(),
            "change_count": db.execute(select(func.count(TenderChange.id)).where(TenderChange.tender_id == tender_id)).scalar_one(),
            "change_evidence_count": db.execute(
                select(func.count(TenderChangeEvidence.id))
                .join(TenderChange, TenderChange.id == TenderChangeEvidence.change_id)
                .where(TenderChange.tender_id == tender_id)
            ).scalar_one(),
            "relationship_count": db.execute(
                select(func.count(DocumentRelationship.id))
                .join(TenderDocument, TenderDocument.id == DocumentRelationship.source_document_id)
                .where(TenderDocument.tender_id == tender_id)
            ).scalar_one(),
            "current_docs": db.execute(
                select(func.count(TenderDocument.id)).where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            ).scalar_one(),
            "review_count": db.execute(select(func.count(RequirementReview.id)).where(RequirementReview.tender_id == tender_id)).scalar_one(),
        }
    finally:
        db.close()

    assert snapshot_after["review_count"] == snapshot_before["review_count"] + 1
    snapshot_before.pop("review_count")
    snapshot_after.pop("review_count")
    assert snapshot_after == snapshot_before
