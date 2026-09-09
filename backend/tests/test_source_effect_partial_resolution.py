from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument, TenderSourceEffect
from app.source_effect_partial_resolution import (
    DIAGNOSTIC_AFFECTED_DOCUMENT_TERMINAL_AT_DOCUMENT_LEVEL,
    DIAGNOSTIC_CONFLICTING_PARTIAL_TERMINAL_EFFECTS,
    DIAGNOSTIC_MULTIPLE_PARTIAL_SUPERSEDING_SOURCES,
    DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED,
    DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW,
    PARTIAL_LOCATOR_STATUS_CLARIFIED,
    PARTIAL_LOCATOR_STATUS_CORRECTED,
    PARTIAL_LOCATOR_STATUS_MODIFIED,
    PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED,
    PARTIAL_LOCATOR_STATUS_REVOKED,
    PARTIAL_LOCATOR_STATUS_SUPERSEDED,
    PARTIAL_LOCATOR_STATUS_SUPPLEMENTED,
    PARTIAL_TENDER_STATUS_RESOLVED,
    PARTIAL_TENDER_STATUS_REVIEW_REQUIRED,
    normalize_partial_locator_identity,
    resolve_partial_source_effects_for_tender,
)
from app.source_effect_resolution import (
    DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS,
    DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
    DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED,
    resolve_effective_sources_for_tender,
)
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
    SourceEffectCandidate,
    replace_source_effects_for_artifact,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-PARTIAL-{uuid4()}",
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


def _prepare_docs(db, tender_id: str, names: Iterable[str]) -> tuple[dict[str, str], dict[str, DocumentPage]]:
    doc_ids: dict[str, str] = {}
    pages: dict[str, DocumentPage] = {}
    for name in names:
        doc_id = _import_pdf(tender_id, f"{name}.pdf")
        doc_ids[name] = doc_id
        pages[name] = _seed_page(db, doc_id, 1, f"Texto de {name}")
    db.commit()
    return doc_ids, pages


def _persist_effect(
    db,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    effect_type: str,
    effect_scope: str,
    affected_document_id: str | None,
    affected_document_ref_raw: str | None,
    effect_index: int,
    review_required: bool = False,
    affected_locator_raw: str | None = None,
    affected_document_page_id: str | None = None,
) -> str:
    artifact_key = f"native-page:{document_page_id}:effect:{effect_index}"
    candidate = SourceEffectCandidate(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        affected_document_id=affected_document_id,
        document_page_id=document_page_id,
        affected_document_page_id=affected_document_page_id,
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=affected_document_ref_raw,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=None,
        source_method="NATIVE",
        source_artifact_key=artifact_key,
        source_locator=f"page:1|effect:{effect_index}",
        source_excerpt=f"Efecto {effect_index}: {effect_type} {effect_scope}",
        review_required=review_required,
        confidence=0.9,
        source_contract_version="partial-resolution-test-001",
        source_analysis_id=None,
        source_page_result_id=None,
    )

    rows = replace_source_effects_for_artifact(
        db,
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        document_page_id=document_page_id,
        source_artifact_key=artifact_key,
        candidates=[candidate],
    )
    assert len(rows) == 1
    return rows[0].id


def _locator_for(result, *, affected_document_id: str, locator_identity: str):
    for item in result.locators:
        if item.affected_document_id == affected_document_id and item.locator_identity == locator_identity:
            return item
    raise AssertionError("Missing locator resolution")


def test_single_amends_maps_to_modified() -> None:
    tender_id = _create_tender("partial single amends")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_RESOLVED
        assert locator.status == PARTIAL_LOCATOR_STATUS_MODIFIED
    finally:
        db.close()


def test_single_corrects_maps_to_corrected() -> None:
    tender_id = _create_tender("partial single corrects")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_CORRECTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")
        assert locator.status == PARTIAL_LOCATOR_STATUS_CORRECTED
    finally:
        db.close()


def test_single_clarifies_maps_to_clarified() -> None:
    tender_id = _create_tender("partial single clarifies")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_CLARIFIES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")
        assert locator.status == PARTIAL_LOCATOR_STATUS_CLARIFIED
    finally:
        db.close()


def test_single_supplements_maps_to_supplemented() -> None:
    tender_id = _create_tender("partial single supplements")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPPLEMENTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")
        assert locator.status == PARTIAL_LOCATOR_STATUS_SUPPLEMENTED
    finally:
        db.close()


def test_single_partial_supersedes_sets_effective_source_document() -> None:
    tender_id = _create_tender("partial single supersedes")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")
        doc_resolution = resolve_effective_sources_for_tender(db, tender_id=tender_id)

        assert locator.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED
        assert locator.effective_source_document_id == doc_ids["A"]
        assert all(item.status != DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED for item in doc_resolution.documents)
    finally:
        db.close()


def test_single_partial_revokes_sets_locator_revoked() -> None:
    tender_id = _create_tender("partial single revokes")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert locator.status == PARTIAL_LOCATOR_STATUS_REVOKED
        assert locator.effective_source_document_id is None
    finally:
        db.close()


def test_terminal_branching_partial_supersedes_is_review_required() -> None:
    tender_id = _create_tender("partial terminal branch")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        first = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        second = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert first in result.conflicts
        assert second in result.conflicts
        assert any(item.code == DIAGNOSTIC_MULTIPLE_PARTIAL_SUPERSEDING_SOURCES for item in locator.diagnostics)
    finally:
        db.close()


def test_partial_supersedes_vs_revokes_conflict_is_review_required() -> None:
    tender_id = _create_tender("partial supersedes vs revokes")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_CONFLICTING_PARTIAL_TERMINAL_EFFECTS for item in locator.diagnostics)
    finally:
        db.close()


def test_duplicate_claim_same_logical_edge_not_treated_as_branching() -> None:
    tender_id = _create_tender("partial duplicate claim")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        one = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        two = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_RESOLVED
        assert locator.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED
        assert one in locator.effect_ids
        assert two in locator.effect_ids
    finally:
        db.close()


def test_review_required_partial_effect_blocks_locator() -> None:
    tender_id = _create_tender("partial review effect")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert effect_id in locator.blocking_effect_ids
    finally:
        db.close()


def test_unresolved_partial_target_sets_tender_review_required() -> None:
    tender_id = _create_tender("partial unresolved target")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A",))
        effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=None,
            affected_document_ref_raw="Anexo Z",
            affected_locator_raw="numeral 4.2",
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert effect_id in result.unresolved_effects
    finally:
        db.close()


def test_locator_normalization_groups_whitespace_and_case_variants() -> None:
    tender_id = _create_tender("partial locator normalization")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw=" Numeral   4.2 ",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPPLEMENTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert "Numeral 4.2" in locator.locator_raw_variants
        assert "numeral 4.2" in locator.locator_raw_variants
        assert len(result.locators) == 1
    finally:
        db.close()


def test_locator_non_equivalence_does_not_infer_hierarchy() -> None:
    tender_id = _create_tender("partial locator non equivalence")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="sección 4.2",
            effect_index=3,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)

        identities = sorted(item.locator_identity for item in result.locators)
        assert identities == ["numeral 4", "numeral 4.2", "sección 4.2"]
    finally:
        db.close()


def test_acting_document_review_required_blocks_partial_supersedes() -> None:
    tender_id = _create_tender("partial acting review blocked")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "X"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["X"],
            document_page_id=pages["X"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=1,
            review_required=True,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        assert any(item.document_id == doc_ids["A"] and item.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED for item in doc_result.documents)

        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert locator.effective_source_document_id is None
        assert any(item.code == DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED for item in locator.diagnostics)
    finally:
        db.close()


def test_acting_document_revoked_blocks_partial_effect() -> None:
    tender_id = _create_tender("partial acting revoked blocked")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "X"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["X"],
            document_page_id=pages["X"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert locator.effective_source_document_id is None
        assert any(item.code == DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED for item in locator.diagnostics)
    finally:
        db.close()


def test_no_mixed_inheritance_from_superseded_acting_source() -> None:
    tender_id = _create_tender("partial no mixed inheritance")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW for item in locator.diagnostics)
    finally:
        db.close()


def test_superseded_acting_document_blocks_partial_supersedes() -> None:
    tender_id = _create_tender("partial superseded actor terminal supersedes")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert any(item.document_id == doc_ids["A"] and item.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED for item in doc_result.documents)
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert locator.effective_source_document_id is None
        assert locator.effective_source_document_id != doc_ids["C"]
        assert any(item.code == DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW for item in locator.diagnostics)
    finally:
        db.close()


def test_superseded_acting_document_blocks_partial_revokes() -> None:
    tender_id = _create_tender("partial superseded actor terminal revokes")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert any(item.document_id == doc_ids["A"] and item.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED for item in doc_result.documents)
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
        assert locator.status != PARTIAL_LOCATOR_STATUS_REVOKED
        assert locator.effective_source_document_id is None
        assert any(item.code == DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW for item in locator.diagnostics)
    finally:
        db.close()


def test_active_with_effects_actor_keeps_partial_supersedes_applicable() -> None:
    tender_id = _create_tender("partial active with effects remains applicable")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["C"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["C"], locator_identity="numeral 4.2")

        assert any(item.document_id == doc_ids["A"] and item.status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS for item in doc_result.documents)
        assert locator.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED
        assert locator.effective_source_document_id == doc_ids["A"]
    finally:
        db.close()


def test_affected_document_terminal_state_is_traceable_without_revival() -> None:
    tender_id = _create_tender("partial affected terminal trace")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        doc_result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_doc = next(item for item in doc_result.documents if item.document_id == doc_ids["B"])
        assert b_doc.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED

        partial_result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id, document_resolution=doc_result)
        locator = _locator_for(partial_result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert locator.affected_document_effective_status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
        assert any(item.code == DIAGNOSTIC_AFFECTED_DOCUMENT_TERMINAL_AT_DOCUMENT_LEVEL for item in locator.diagnostics)
    finally:
        db.close()


def test_date_and_revision_do_not_resolve_partial_terminal_conflict() -> None:
    tender_id = _create_tender("partial date non precedence")
    db = SessionLocal()
    try:
        doc_b = _import_pdf(tender_id, "anexo-base.pdf")
        doc_a = _import_pdf(tender_id, "anexo-rev-2025.pdf")
        doc_c = _import_pdf(tender_id, "anexo-rev-2027.pdf")

        page_b = _seed_page(db, doc_b, 1, "Base")
        page_a = _seed_page(db, doc_a, 1, "A")
        page_c = _seed_page(db, doc_c, 1, "C")

        record_a = db.get(TenderDocument, doc_a)
        record_c = db.get(TenderDocument, doc_c)
        assert record_a is not None
        assert record_c is not None
        record_a.created_at = datetime.now(timezone.utc) - timedelta(days=90)
        record_c.created_at = datetime.now(timezone.utc)

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_a,
            document_page_id=page_a.id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_b,
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_c,
            document_page_id=page_c.id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_b,
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_b, locator_identity="numeral 4.2")

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert locator.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
    finally:
        db.close()


def test_order_independence_with_same_logical_partial_graph() -> None:
    db = SessionLocal()
    try:
        tender_one = _create_tender("partial order one")
        docs_one, pages_one = _prepare_docs(db, tender_one, ("A", "B", "C", "D"))
        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["A"],
            document_page_id=pages_one["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_one["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["C"],
            document_page_id=pages_one["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPPLEMENTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_one["D"],
            affected_document_ref_raw=None,
            affected_locator_raw="tabla 3",
            effect_index=2,
        )
        db.commit()

        tender_two = _create_tender("partial order two")
        docs_two, pages_two = _prepare_docs(db, tender_two, ("A", "B", "C", "D"))
        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["C"],
            document_page_id=pages_two["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPPLEMENTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_two["D"],
            affected_document_ref_raw=None,
            affected_locator_raw="tabla 3",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["A"],
            document_page_id=pages_two["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_two["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result_one = resolve_partial_source_effects_for_tender(db, tender_id=tender_one)
        result_two = resolve_partial_source_effects_for_tender(db, tender_id=tender_two)

        map_one = sorted((item.locator_identity, item.status) for item in result_one.locators)
        map_two = sorted((item.locator_identity, item.status) for item in result_two.locators)
        assert result_one.status == result_two.status
        assert map_one == map_two
    finally:
        db.close()


def test_partial_resolver_no_mutation() -> None:
    tender_id = _create_tender("partial no mutation")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        before_rows = [
            (item.id, item.updated_at)
            for item in db.execute(
                select(TenderSourceEffect)
                .where(TenderSourceEffect.tender_id == tender_id)
                .order_by(TenderSourceEffect.id.asc())
            ).scalars()
        ]

        writes: list[str] = []
        connection = db.connection()

        def _capture_writes(_conn, _cursor, statement, _params, _context, _executemany):
            normalized = str(statement).lstrip().upper()
            if normalized.startswith("INSERT") or normalized.startswith("UPDATE") or normalized.startswith("DELETE"):
                writes.append(str(statement))

        event.listen(connection, "before_cursor_execute", _capture_writes)
        try:
            result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        finally:
            event.remove(connection, "before_cursor_execute", _capture_writes)

        after_rows = [
            (item.id, item.updated_at)
            for item in db.execute(
                select(TenderSourceEffect)
                .where(TenderSourceEffect.tender_id == tender_id)
                .order_by(TenderSourceEffect.id.asc())
            ).scalars()
        ]

        assert result.status == PARTIAL_TENDER_STATUS_RESOLVED
        assert writes == []
        assert before_rows == after_rows
    finally:
        db.close()


def test_unresolved_locator_without_raw_goes_to_unresolved_effects() -> None:
    tender_id = _create_tender("partial unresolved locator")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        target_page = _seed_page(db, doc_ids["B"], 2, "target page")
        effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw=None,
            affected_document_page_id=target_page.id,
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)

        assert result.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        assert effect_id in result.unresolved_effects
    finally:
        db.close()


def test_multiple_compatible_non_terminal_overlays_do_not_conflict() -> None:
    tender_id = _create_tender("partial compatible overlays")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_CLARIFIES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPPLEMENTS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")

        assert result.conflicts == ()
        assert locator.status == PARTIAL_LOCATOR_STATUS_MODIFIED
    finally:
        db.close()


def test_conservative_normalization_function() -> None:
    assert normalize_partial_locator_identity(" Numeral   4.2 ") == "numeral 4.2"
    assert normalize_partial_locator_identity("SECCIÓN 4.2") == "sección 4.2"
    assert normalize_partial_locator_identity(" ") is None


def test_no_cross_document_partial_chain_inference() -> None:
    tender_id = _create_tender("partial no cross document chain")
    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        result = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
        locator_b = _locator_for(result, affected_document_id=doc_ids["B"], locator_identity="numeral 4.2")
        locator_a = _locator_for(result, affected_document_id=doc_ids["A"], locator_identity="numeral 4.2")

        assert locator_b.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED
        assert locator_b.effective_source_document_id == doc_ids["A"]
        assert locator_a.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED
        assert locator_a.effective_source_document_id == doc_ids["C"]
    finally:
        db.close()
