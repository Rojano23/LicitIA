from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument, TenderSourceEffect
from app.source_effect_resolution import (
    DIAGNOSTIC_ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW,
    DIAGNOSTIC_CONFLICTING_TERMINAL_EFFECTS,
    DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES,
    DIAGNOSTIC_NO_REVIVAL_REQUIRES_REVIEW,
    DIAGNOSTIC_REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION,
    DIAGNOSTIC_REVOKED_ACTING_SOURCE_EFFECT_APPLICABILITY_UNRESOLVED,
    DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED,
    DIAGNOSTIC_SUPERSESSION_CYCLE,
    TENDER_RESOLUTION_STATUS_RESOLVED,
    TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED,
    DOCUMENT_EFFECTIVE_STATUS_ACTIVE,
    DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS,
    DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
    DOCUMENT_EFFECTIVE_STATUS_REVOKED,
    DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED,
    resolve_effective_sources_for_tender,
)
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
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
            "external_reference": f"SRC-EFF-RES-{uuid4()}",
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
    effective_date_raw: str | None = None,
) -> str:
    artifact_key = f"native-page:{document_page_id}:effect:{effect_index}"
    candidate = SourceEffectCandidate(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        affected_document_id=affected_document_id,
        document_page_id=document_page_id,
        affected_document_page_id=None,
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=affected_document_ref_raw,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=effective_date_raw,
        source_method="NATIVE",
        source_artifact_key=artifact_key,
        source_locator=f"page:1|effect:{effect_index}",
        source_excerpt=f"Efecto {effect_index}: {effect_type} {effect_scope}",
        review_required=review_required,
        confidence=0.9,
        source_contract_version="resolution-test-001",
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


def _get_doc_result(result, document_id: str):
    for item in result.documents:
        if item.document_id == document_id:
            return item
    raise AssertionError(f"Missing document result for {document_id}")


def _doc_status_map(result, doc_ids_by_name: dict[str, str]) -> dict[str, str]:
    return {
        name: _get_doc_result(result, doc_id).status
        for name, doc_id in doc_ids_by_name.items()
    }


def _replacement_name_map(result, doc_ids_by_name: dict[str, str]) -> dict[str, str | None]:
    id_to_name = {value: key for key, value in doc_ids_by_name.items()}
    replacements: dict[str, str | None] = {}
    for name, doc_id in doc_ids_by_name.items():
        replacement_id = _get_doc_result(result, doc_id).effective_replacement_document_id
        replacements[name] = id_to_name.get(replacement_id) if replacement_id is not None else None
    return replacements


def _prepare_docs(db, tender_id: str, names: Iterable[str]) -> tuple[dict[str, str], dict[str, DocumentPage]]:
    doc_ids: dict[str, str] = {}
    pages: dict[str, DocumentPage] = {}
    for name in names:
        doc_id = _import_pdf(tender_id, f"{name}.pdf")
        doc_ids[name] = doc_id
        pages[name] = _seed_page(db, doc_id, 1, f"Texto de {name}")
    db.commit()
    return doc_ids, pages


def test_no_effects_returns_resolved_all_active() -> None:
    tender_id = _create_tender("resolution no effects")

    db = SessionLocal()
    try:
        doc_ids, _pages = _prepare_docs(db, tender_id, ("A", "B", "C"))

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _doc_status_map(result, doc_ids) == {
            "A": DOCUMENT_EFFECTIVE_STATUS_ACTIVE,
            "B": DOCUMENT_EFFECTIVE_STATUS_ACTIVE,
            "C": DOCUMENT_EFFECTIVE_STATUS_ACTIVE,
        }
        assert result.unresolved_effects == ()
        assert result.conflicts == ()
    finally:
        db.close()


def test_single_supersedes_marks_target_superseded_with_replacement() -> None:
    tender_id = _create_tender("resolution single supersedes")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
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
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
        assert b_result.effective_replacement_document_id == doc_ids["A"]
        assert b_result.supersession_chain == (doc_ids["B"], doc_ids["A"])
    finally:
        db.close()


def test_pure_supersedes_chain_resolves_ultimate_replacement() -> None:
    tender_id = _create_tender("resolution pure chain")

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
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _get_doc_result(result, doc_ids["C"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
        assert b_result.supersession_chain == (doc_ids["B"], doc_ids["A"], doc_ids["C"])
        assert b_result.effective_replacement_document_id == doc_ids["C"]
    finally:
        db.close()


def test_single_revokes_marks_target_revoked_without_replacement() -> None:
    tender_id = _create_tender("resolution single revokes")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVOKED
        assert b_result.effective_replacement_document_id is None
    finally:
        db.close()


def test_document_wide_amends_keeps_active_with_effects() -> None:
    tender_id = _create_tender("resolution doc wide amends")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _get_doc_result(result, doc_ids["B"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS
    finally:
        db.close()


def test_partial_supersedes_keeps_document_active_with_effects() -> None:
    tender_id = _create_tender("resolution partial supersedes")

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

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])
        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS
        assert len(b_result.partial_effect_ids) == 1
    finally:
        db.close()


def test_partial_revokes_keeps_document_active_with_effects() -> None:
    tender_id = _create_tender("resolution partial revokes")

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
            affected_locator_raw="tabla 3",
            effect_index=1,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert _get_doc_result(result, doc_ids["B"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS
    finally:
        db.close()


def test_review_required_effect_with_resolved_target_blocks_document() -> None:
    tender_id = _create_tender("resolution review resolved target")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert effect_id in b_result.blocking_effect_ids
        assert any(item.code == DIAGNOSTIC_REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION for item in b_result.diagnostics)
    finally:
        db.close()


def test_review_required_effect_with_unresolved_target_blocks_tender_only() -> None:
    tender_id = _create_tender("resolution review unresolved target")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_UNRESOLVED,
            affected_document_id=None,
            affected_document_ref_raw="Anexo X",
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert effect_id in result.unresolved_effects
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
        assert _get_doc_result(result, doc_ids["B"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
    finally:
        db.close()


def test_direct_superseding_source_review_required_blocks_target_resolution() -> None:
    tender_id = _create_tender("resolution direct superseding source review dependency")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "X"))

        review_effect_id = _persist_effect(
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
        supersedes_effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        a_result = _get_doc_result(result, doc_ids["A"])
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert a_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert b_result.effective_replacement_document_id is None
        assert review_effect_id in a_result.blocking_effect_ids
        assert supersedes_effect_id in b_result.blocking_effect_ids
        assert any(item.code == DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED for item in b_result.diagnostics)
    finally:
        db.close()


def test_transitive_superseding_source_review_required_propagates_downstream() -> None:
    tender_id = _create_tender("resolution transitive superseding source review dependency")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D", "X"))

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["X"],
            document_page_id=pages["X"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["D"],
            affected_document_ref_raw=None,
            effect_index=1,
            review_required=True,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["C"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=3,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["B"],
            document_page_id=pages["B"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=4,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["D"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["C"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["B"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert any(
            item.code == DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED
            for item in _get_doc_result(result, doc_ids["C"]).diagnostics
        )
        assert any(
            item.code == DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED
            for item in _get_doc_result(result, doc_ids["B"]).diagnostics
        )
        assert any(
            item.code == DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED
            for item in _get_doc_result(result, doc_ids["A"]).diagnostics
        )
        assert _get_doc_result(result, doc_ids["C"]).effective_replacement_document_id is None
        assert _get_doc_result(result, doc_ids["B"]).effective_replacement_document_id is None
        assert _get_doc_result(result, doc_ids["A"]).effective_replacement_document_id is None
    finally:
        db.close()


def test_intermediate_review_required_blocks_only_downstream_dependencies() -> None:
    tender_id = _create_tender("resolution intermediate review dependency")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "X"))

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["B"],
            document_page_id=pages["B"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["X"],
            document_page_id=pages["X"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=3,
            review_required=True,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["B"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["A"]).status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert _get_doc_result(result, doc_ids["A"]).effective_replacement_document_id is None
        assert _get_doc_result(result, doc_ids["C"]).status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE
        assert any(
            item.code == DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED
            for item in _get_doc_result(result, doc_ids["A"]).diagnostics
        )
    finally:
        db.close()


def test_branching_supersedes_conflict_sets_review_required() -> None:
    tender_id = _create_tender("resolution branching supersedes")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        first_id = _persist_effect(
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
        second_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert first_id in result.conflicts
        assert second_id in result.conflicts
        assert any(item.code == DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES for item in b_result.diagnostics)
    finally:
        db.close()


def test_terminal_type_conflict_supersedes_vs_revokes() -> None:
    tender_id = _create_tender("resolution terminal conflict")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        supersedes_id = _persist_effect(
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
        revokes_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert supersedes_id in result.conflicts
        assert revokes_id in result.conflicts
        assert any(item.code == DIAGNOSTIC_CONFLICTING_TERMINAL_EFFECTS for item in b_result.diagnostics)
    finally:
        db.close()


def test_supersession_cycle_marks_involved_documents_review_required() -> None:
    tender_id = _create_tender("resolution cycle")

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
            acting_document_id=doc_ids["B"],
            document_page_id=pages["B"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["C"],
            affected_document_ref_raw=None,
            effect_index=2,
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
            effect_index=3,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        statuses = _doc_status_map(result, doc_ids)

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert statuses == {
            "A": DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
            "B": DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
            "C": DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
        }
        assert any(
            item.code == DIAGNOSTIC_SUPERSESSION_CYCLE
            for doc in result.documents
            for item in doc.diagnostics
        )
    finally:
        db.close()


def test_duplicate_supporting_claim_not_treated_as_branching() -> None:
    tender_id = _create_tender("resolution duplicate supporting claim")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))

        first_id = _persist_effect(
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
        second_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
        assert first_id in b_result.blocking_effect_ids
        assert second_id in b_result.blocking_effect_ids
    finally:
        db.close()


def test_mixed_actor_inheritance_requires_review() -> None:
    tender_id = _create_tender("resolution mixed actor inheritance")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
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
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW for item in b_result.diagnostics)
    finally:
        db.close()


def test_no_revival_when_replacement_is_revoked() -> None:
    tender_id = _create_tender("resolution no revival")

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
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_NO_REVIVAL_REQUIRES_REVIEW for item in b_result.diagnostics)
    finally:
        db.close()


def test_revoked_acting_source_effect_applicability_requires_review() -> None:
    tender_id = _create_tender("resolution revoked acting source applicability")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
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
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["A"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_ids["B"])

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert any(
            item.code == DIAGNOSTIC_REVOKED_ACTING_SOURCE_EFFECT_APPLICABILITY_UNRESOLVED
            for item in b_result.diagnostics
        )
    finally:
        db.close()


def test_order_independence_same_logical_graph_same_result() -> None:
    db = SessionLocal()
    try:
        tender_one = _create_tender("resolution order independence one")
        docs_one, pages_one = _prepare_docs(db, tender_one, ("A", "B", "C", "D"))

        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["A"],
            document_page_id=pages_one["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs_one["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["C"],
            document_page_id=pages_one["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs_one["D"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["D"],
            document_page_id=pages_one["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_one["C"],
            affected_document_ref_raw=None,
            affected_locator_raw="inciso b",
            effect_index=3,
        )
        db.commit()

        tender_two = _create_tender("resolution order independence two")
        docs_two, pages_two = _prepare_docs(db, tender_two, ("A", "B", "C", "D"))

        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["D"],
            document_page_id=pages_two["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_two["C"],
            affected_document_ref_raw=None,
            affected_locator_raw="inciso b",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["C"],
            document_page_id=pages_two["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs_two["D"],
            affected_document_ref_raw=None,
            effect_index=2,
        )
        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["A"],
            document_page_id=pages_two["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs_two["B"],
            affected_document_ref_raw=None,
            effect_index=3,
        )
        db.commit()

        result_one = resolve_effective_sources_for_tender(db, tender_id=tender_one)
        result_two = resolve_effective_sources_for_tender(db, tender_id=tender_two)

        assert result_one.status == result_two.status
        assert _doc_status_map(result_one, docs_one) == _doc_status_map(result_two, docs_two)
        assert _replacement_name_map(result_one, docs_one) == _replacement_name_map(result_two, docs_two)
    finally:
        db.close()


def test_dates_and_revision_like_names_do_not_resolve_branch_conflict() -> None:
    tender_id = _create_tender("resolution no date precedence")

    db = SessionLocal()
    try:
        doc_b = _import_pdf(tender_id, "anexo-base.pdf")
        doc_a = _import_pdf(tender_id, "anexo-rev-2025.pdf")
        doc_c = _import_pdf(tender_id, "anexo-rev-2027.pdf")

        page_b = _seed_page(db, doc_b, 1, "Base")
        page_a = _seed_page(db, doc_a, 1, "A")
        page_c = _seed_page(db, doc_c, 1, "C")

        document_a = db.get(TenderDocument, doc_a)
        document_c = db.get(TenderDocument, doc_c)
        assert document_a is not None
        assert document_c is not None
        document_a.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        document_c.created_at = datetime.now(timezone.utc)

        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_a,
            document_page_id=page_a.id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_b,
            affected_document_ref_raw=None,
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_c,
            document_page_id=page_c.id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_b,
            affected_document_ref_raw=None,
            effect_index=2,
        )
        db.commit()

        result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        b_result = _get_doc_result(result, doc_b)

        assert result.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED
        assert b_result.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES for item in b_result.diagnostics)
        assert page_b.id is not None
    finally:
        db.close()


def test_resolver_does_not_mutate_database() -> None:
    tender_id = _create_tender("resolution no mutation")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=doc_ids["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=doc_ids["B"],
            affected_document_ref_raw=None,
            effect_index=1,
        )
        db.commit()

        before_effect_rows = [
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
            result = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        finally:
            event.remove(connection, "before_cursor_execute", _capture_writes)

        after_effect_rows = [
            (item.id, item.updated_at)
            for item in db.execute(
                select(TenderSourceEffect)
                .where(TenderSourceEffect.tender_id == tender_id)
                .order_by(TenderSourceEffect.id.asc())
            ).scalars()
        ]

        assert result.status == TENDER_RESOLUTION_STATUS_RESOLVED
        assert writes == []
        assert before_effect_rows == after_effect_rows
    finally:
        db.close()
