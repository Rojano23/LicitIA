from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument, TenderSourceEffect
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_UNSPECIFIED,
    SourceEffectCandidate,
    compute_source_effect_fingerprint,
    list_source_effects_for_boundary,
    list_source_effects_for_tender,
    replace_source_effects_for_artifact,
    validate_source_effect_candidate,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-{uuid4()}",
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


def _seed_page(db, document_id: str, page_number: int, text: str) -> DocumentPage:
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
    document = db.get(TenderDocument, document_id)
    assert document is not None
    document.page_count = max(document.page_count, page_number)
    document.processing_status = "TEXT_EXTRACTION_COMPLETE"
    return page


def _candidate(
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    effect_type: str,
    effect_scope: str,
    affected_document_id: str | None,
    affected_document_ref_raw: str | None,
    affected_locator_raw: str | None = None,
    affected_document_page_id: str | None = None,
    review_required: bool = False,
    confidence: float | None = 0.9,
    source_artifact_key: str = "DocumentPage:acting-1",
    source_locator: str = "page:1|chars:10-90",
    source_excerpt: str = "Se modifica el Anexo B, numeral 4.2.",
    source_method: str = "NATIVE",
    effective_date_raw: str | None = None,
) -> SourceEffectCandidate:
    return SourceEffectCandidate(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        affected_document_id=affected_document_id,
        document_page_id=document_page_id,
        affected_document_page_id=affected_document_page_id,
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=affected_document_ref_raw,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=effective_date_raw,
        source_method=source_method,
        source_artifact_key=source_artifact_key,
        source_locator=source_locator,
        source_excerpt=source_excerpt,
        review_required=review_required,
        confidence=confidence,
        source_contract_version="contract-001",
        source_analysis_id=None,
        source_page_result_id=None,
    )


def _count_source_effects(db, *, tender_id: str) -> int:
    value = db.scalar(select(func.count(TenderSourceEffect.id)).where(TenderSourceEffect.tender_id == tender_id))
    return int(value or 0)


def test_resolved_target_valid_persistence() -> None:
    tender_id = _create_tender("source effect resolved target")
    acting_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica el Anexo B.")
        _seed_page(db, affected_doc_id, 1, "Contenido base")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw=None,
        )

        persisted = replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate],
        )
        db.commit()

        assert len(persisted) == 1
        assert persisted[0].affected_document_id == affected_doc_id
        assert persisted[0].effect_type == SOURCE_EFFECT_TYPE_AMENDS
    finally:
        db.close()


def test_unresolved_raw_target_valid_with_review_required() -> None:
    tender_id = _create_tender("source effect unresolved target")
    acting_doc_id = _import_pdf(tender_id, "junta-aclaraciones.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica el anexo tecnico")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_UNRESOLVED,
            affected_document_id=None,
            affected_document_ref_raw="Anexo Técnico",
            review_required=True,
        )

        validate_source_effect_candidate(db, candidate)
        persisted = replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate],
        )
        assert len(persisted) == 1
        assert persisted[0].affected_document_id is None
        assert persisted[0].affected_document_ref_raw == "Anexo Técnico"
    finally:
        db.close()


def test_partial_effect_valid_with_partial_locator_only() -> None:
    tender_id = _create_tender("source effect partial")
    acting_doc_id = _import_pdf(tender_id, "fe-de-erratas.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-c.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige numeral 4.2")
        _seed_page(db, affected_doc_id, 7, "numeral 4.2")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_CORRECTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo C",
            affected_locator_raw="numeral 4.2",
        )

        validate_source_effect_candidate(db, candidate)
        persisted = replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate],
        )
        assert len(persisted) == 1
        assert persisted[0].affected_locator_raw == "numeral 4.2"
    finally:
        db.close()


def test_invalid_cross_tender_rejected() -> None:
    tender_a = _create_tender("source effect tender a")
    tender_b = _create_tender("source effect tender b")
    acting_doc_id = _import_pdf(tender_a, "junta.pdf")
    affected_doc_other_tender = _import_pdf(tender_b, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica anexo")
        _seed_page(db, affected_doc_other_tender, 1, "contenido")
        db.commit()

        candidate = _candidate(
            tender_id=tender_a,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_other_tender,
            affected_document_ref_raw=None,
        )

        with pytest.raises(ValueError, match="different tender"):
            validate_source_effect_candidate(db, candidate)
    finally:
        db.close()


def test_invalid_page_ownership_rejected_for_acting_and_affected_pages() -> None:
    tender_id = _create_tender("source effect page ownership")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")
    other_doc_id = _import_pdf(tender_id, "otro.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica")
        affected_page = _seed_page(db, affected_doc_id, 3, "tabla")
        other_page = _seed_page(db, other_doc_id, 2, "otro")
        db.commit()

        candidate_acting_page_mismatch = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=other_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo B",
        )
        with pytest.raises(ValueError, match="document_page_id does not belong"):
            validate_source_effect_candidate(db, candidate_acting_page_mismatch)

        candidate_affected_page_mismatch = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_CORRECTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo B",
            affected_locator_raw=None,
            affected_document_page_id=other_page.id,
        )
        with pytest.raises(ValueError, match="affected_document_page_id does not belong"):
            validate_source_effect_candidate(db, candidate_affected_page_mismatch)

        candidate_ok = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_CORRECTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo B",
            affected_locator_raw=None,
            affected_document_page_id=affected_page.id,
        )
        validate_source_effect_candidate(db, candidate_ok)
    finally:
        db.close()


def test_invalid_unspecified_without_review_rejected() -> None:
    tender_id = _create_tender("source effect unspecified review")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica")
        _seed_page(db, affected_doc_id, 1, "contenido")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_UNSPECIFIED,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo",
            review_required=False,
        )
        with pytest.raises(ValueError, match="requires review_required=True"):
            validate_source_effect_candidate(db, candidate)
    finally:
        db.close()


def test_invalid_unresolved_without_review_rejected() -> None:
    tender_id = _create_tender("source effect unresolved review")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_UNRESOLVED,
            affected_document_id=None,
            affected_document_ref_raw="Anexo Técnico",
            review_required=False,
        )
        with pytest.raises(ValueError, match="requires review_required=True"):
            validate_source_effect_candidate(db, candidate)
    finally:
        db.close()


def test_invalid_partial_without_target_detail_rejected() -> None:
    tender_id = _create_tender("source effect partial invalid")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige")
        _seed_page(db, affected_doc_id, 1, "contenido")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_CORRECTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=affected_doc_id,
            affected_document_ref_raw="Anexo",
            affected_locator_raw=None,
            affected_document_page_id=None,
        )

        with pytest.raises(ValueError, match="PARTIAL effect_scope requires"):
            validate_source_effect_candidate(db, candidate)
    finally:
        db.close()


def test_replacement_isolation_boundary() -> None:
    tender_id = _create_tender("source effect replacement boundary")
    acting_doc_a = _import_pdf(tender_id, "junta-a.pdf")
    acting_doc_b = _import_pdf(tender_id, "junta-b.pdf")
    affected_doc = _import_pdf(tender_id, "anexo.pdf")

    db = SessionLocal()
    try:
        page_a1 = _seed_page(db, acting_doc_a, 1, "Texto A1")
        page_a2 = _seed_page(db, acting_doc_a, 2, "Texto A2")
        page_b1 = _seed_page(db, acting_doc_b, 1, "Texto B1")
        _seed_page(db, affected_doc, 1, "Destino")
        db.commit()

        c1 = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc_a,
            document_page_id=page_a1.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc,
            affected_document_ref_raw="Anexo",
            source_locator="page:1|chars:1-20",
        )
        c2 = replace(c1, source_locator="page:1|chars:21-40", affected_locator_raw="tabla 2", effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL)
        c3 = replace(c1, document_page_id=page_a2.id, source_artifact_key="DocumentPage:acting-2", source_locator="page:2|chars:1-20")
        c4 = replace(c1, acting_document_id=acting_doc_b, document_page_id=page_b1.id, source_artifact_key="DocumentPage:acting-b", source_locator="page:1|chars:1-20")

        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_a,
            document_page_id=page_a1.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[c1, c2],
        )
        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_a,
            document_page_id=page_a2.id,
            source_artifact_key="DocumentPage:acting-2",
            candidates=[c3],
        )
        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_b,
            document_page_id=page_b1.id,
            source_artifact_key="DocumentPage:acting-b",
            candidates=[c4],
        )
        db.commit()

        replacement = replace(c1, source_locator="page:1|chars:80-120", affected_document_ref_raw="Anexo actualizado")
        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_a,
            document_page_id=page_a1.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[replacement],
        )
        db.commit()

        boundary_rows = list_source_effects_for_boundary(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_a,
            document_page_id=page_a1.id,
            source_artifact_key="DocumentPage:acting-1",
        )
        all_rows = list_source_effects_for_tender(db, tender_id=tender_id)

        assert len(boundary_rows) == 1
        assert boundary_rows[0].source_locator == "page:1|chars:80-120"
        assert len(all_rows) == 3
    finally:
        db.close()


def test_idempotency_for_same_semantic_candidates() -> None:
    tender_id = _create_tender("source effect idempotency")
    acting_doc = _import_pdf(tender_id, "junta.pdf")
    affected_doc = _import_pdf(tender_id, "anexo.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc, 1, "Texto")
        _seed_page(db, affected_doc, 1, "Destino")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc,
            affected_document_ref_raw="Anexo",
        )

        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate],
        )
        db.commit()
        first = list_source_effects_for_boundary(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            source_artifact_key="DocumentPage:acting-1",
        )

        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate],
        )
        db.commit()
        second = list_source_effects_for_boundary(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            source_artifact_key="DocumentPage:acting-1",
        )

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].semantic_fingerprint == second[0].semantic_fingerprint
    finally:
        db.close()


def test_fingerprint_semantics_excludes_provenance_and_review_confidence() -> None:
    base = SourceEffectCandidate(
        tender_id="t-1",
        acting_document_id="d-1",
        affected_document_id="d-2",
        document_page_id="p-1",
        affected_document_page_id=None,
        effect_type=SOURCE_EFFECT_TYPE_AMENDS,
        effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
        affected_document_ref_raw="Anexo B",
        affected_locator_raw="numeral 4.2",
        effective_date_raw="08/09/2026",
        source_method="NATIVE",
        source_artifact_key="artifact-a",
        source_locator="loc-a",
        source_excerpt="Se modifica el anexo B",
        review_required=False,
        confidence=0.5,
    )

    changed_non_semantic = replace(
        base,
        tender_id="t-999",
        acting_document_id="d-999",
        document_page_id="p-999",
        source_artifact_key="artifact-b",
        source_locator="loc-b",
        source_excerpt="  Se   modifica   el   anexo B  ",
        review_required=True,
        confidence=0.1,
        source_analysis_id="a-1",
        source_page_result_id="r-1",
    )
    assert compute_source_effect_fingerprint(base) == compute_source_effect_fingerprint(changed_non_semantic)

    changed_semantic = replace(base, effect_type=SOURCE_EFFECT_TYPE_CORRECTS)
    assert compute_source_effect_fingerprint(base) != compute_source_effect_fingerprint(changed_semantic)


def test_fingerprint_distinguishes_two_resolved_targets_without_raw_reference() -> None:
    tender_id = _create_tender("source effect distinct resolved targets")
    acting_doc = _import_pdf(tender_id, "junta.pdf")
    affected_doc_b = _import_pdf(tender_id, "anexo-b.pdf", payload_suffix="b")
    affected_doc_c = _import_pdf(tender_id, "anexo-c.pdf", payload_suffix="c")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc, 1, "Se modifica documento")
        _seed_page(db, affected_doc_b, 1, "B")
        _seed_page(db, affected_doc_c, 1, "C")
        db.commit()

        candidate_b = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_b,
            affected_document_ref_raw=None,
            source_locator="page:1|chars:1-50",
        )
        candidate_c = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=acting_page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=affected_doc_c,
            affected_document_ref_raw=None,
            source_locator="page:1|chars:51-100",
        )

        fingerprint_b = compute_source_effect_fingerprint(candidate_b)
        fingerprint_c = compute_source_effect_fingerprint(candidate_c)
        assert fingerprint_b != fingerprint_c

        persisted = replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=acting_page.id,
            source_artifact_key="DocumentPage:acting-1",
            candidates=[candidate_b, candidate_c],
        )
        db.commit()

        assert len(persisted) == 2
        assert _count_source_effects(db, tender_id=tender_id) == 2
    finally:
        db.close()


def test_fingerprint_unresolved_to_resolved_is_stable_when_raw_target_exists() -> None:
    unresolved = SourceEffectCandidate(
        tender_id="t-1",
        acting_document_id="d-acting",
        affected_document_id=None,
        document_page_id="p-1",
        affected_document_page_id=None,
        effect_type=SOURCE_EFFECT_TYPE_AMENDS,
        effect_scope=SOURCE_EFFECT_SCOPE_UNRESOLVED,
        affected_document_ref_raw="Anexo Técnico",
        affected_locator_raw="numeral 4.2",
        effective_date_raw="08/09/2026",
        source_method="NATIVE",
        source_artifact_key="artifact-a",
        source_locator="loc-a",
        source_excerpt="Se modifica el Anexo Técnico",
        review_required=True,
        confidence=0.4,
    )
    resolved = replace(unresolved, affected_document_id="resolved-doc-uuid")

    assert compute_source_effect_fingerprint(unresolved) == compute_source_effect_fingerprint(resolved)


def test_fingerprint_differs_for_different_raw_target_references() -> None:
    base = SourceEffectCandidate(
        tender_id="t-1",
        acting_document_id="d-acting",
        affected_document_id=None,
        document_page_id="p-1",
        affected_document_page_id=None,
        effect_type=SOURCE_EFFECT_TYPE_AMENDS,
        effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
        affected_document_ref_raw="Anexo B",
        affected_locator_raw=None,
        effective_date_raw=None,
        source_method="NATIVE",
        source_artifact_key="artifact-a",
        source_locator="loc-a",
        source_excerpt="Se modifica el Anexo B",
        review_required=False,
        confidence=0.5,
    )
    other = replace(base, affected_document_ref_raw="Anexo C", source_excerpt="Se modifica el Anexo C")

    assert compute_source_effect_fingerprint(base) != compute_source_effect_fingerprint(other)


def test_acting_document_equal_to_affected_document_is_rejected() -> None:
    tender_id = _create_tender("source effect same document reject")
    same_doc_id = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, same_doc_id, 1, "Se modifica el mismo documento")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=same_doc_id,
            document_page_id=page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=same_doc_id,
            affected_document_ref_raw="Documento base",
        )

        with pytest.raises(ValueError, match="cannot equal"):
            validate_source_effect_candidate(db, candidate)
    finally:
        db.close()


def test_provenance_fields_preserved_exactly() -> None:
    tender_id = _create_tender("source effect provenance")
    acting_doc = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc, 1, "Texto")
        db.commit()

        candidate = _candidate(
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_UNRESOLVED,
            affected_document_id=None,
            affected_document_ref_raw="Anexo Técnico Rev. 0",
            review_required=True,
            source_method="OCR",
            source_artifact_key="PageOcrResult:abc123",
            source_locator="page:1|ocr:full",
            source_excerpt="Se aclara que aplica anexo técnico rev. 0",
        )

        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc,
            document_page_id=page.id,
            source_artifact_key="PageOcrResult:abc123",
            candidates=[candidate],
        )
        db.commit()

        row = list_source_effects_for_tender(db, tender_id=tender_id)[0]
        assert row.source_method == "OCR"
        assert row.source_artifact_key == "PageOcrResult:abc123"
        assert row.source_locator == "page:1|ocr:full"
        assert row.source_excerpt == "Se aclara que aplica anexo técnico rev. 0"
    finally:
        db.close()


def test_module_stores_claims_only_without_precedence_fields() -> None:
    forbidden_fields = {
        "priority",
        "precedence_score",
        "rank",
        "winner",
        "is_effective",
        "is_current",
        "superseded",
        "effective_source_id",
    }
    table_fields = set(TenderSourceEffect.__table__.columns.keys())
    assert forbidden_fields.isdisjoint(table_fields)
