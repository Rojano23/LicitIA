from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.database import SessionLocal
from app.effective_source_projection import (
    DIAGNOSTIC_FACT_REVIEW_REQUIRED,
    DIAGNOSTIC_PARENT_CHILD_TERMINAL_STATUS_CONFLICT,
    DIAGNOSTIC_PARENT_SCOPE_REVIEW_REQUIRED,
    DIAGNOSTIC_PARENT_SCOPE_REVOKED,
    DIAGNOSTIC_PARENT_SCOPE_SUPERSEDED,
    DIAGNOSTIC_SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED,
    ENTITY_TYPE_REQUIREMENT,
    ENTITY_TYPE_SCOPE_ATTRIBUTE,
    ENTITY_TYPE_SCOPE_DETAIL,
    ENTITY_TYPE_SCOPE_QUANTITY,
    PROJECTION_STATUS_EFFECTIVE,
    PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY,
    PROJECTION_STATUS_REVIEW_REQUIRED,
    PROJECTION_STATUS_REVOKED,
    PROJECTION_STATUS_SUPERSEDED,
    PROJECTION_STATUS_UNRESOLVED_SOURCE,
    TENDER_PROJECTION_STATUS_REVIEW_REQUIRED,
    project_effective_sources_for_tender,
)
from app.main import app
from app.models import (
    DocumentPage,
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementReview,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
    TenderScopeQuantity,
)
from app.source_effect_resolution import TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED, resolve_effective_sources_for_tender
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
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
            "external_reference": f"EFF-PROJ-{uuid4()}",
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


def _prepare_docs(db, tender_id: str, names: tuple[str, ...]) -> tuple[dict[str, str], dict[str, DocumentPage]]:
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
    effect_index: int,
    review_required: bool = False,
    affected_document_ref_raw: str | None = None,
    affected_locator_raw: str | None = None,
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
        effective_date_raw=None,
        source_method="NATIVE",
        source_artifact_key=artifact_key,
        source_locator=f"page:1|effect:{effect_index}",
        source_excerpt=f"Efecto {effect_index}: {effect_type} {effect_scope}",
        review_required=review_required,
        confidence=0.9,
        source_contract_version="effective-projection-test-001",
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


def _create_requirement(
    db,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str | None,
    source_locator: str | None,
    normalization_status: str = "NORMALIZED",
    review_status: str | None = None,
) -> Requirement:
    candidate = RequirementCandidate(
        id=str(uuid4()),
        tender_id=tender_id,
        semantic_key=f"cand-{uuid4()}",
        requirement_text=source_locator or "req",
        source_document_id=source_document_id,
        source_page=1,
        source_excerpt=source_locator or "",
        document_page_id=document_page_id,
        review_status="CONFIRMED",
        detector_version="test",
    )
    requirement = Requirement(
        id=str(uuid4()),
        tender_id=tender_id,
        canonical_key=f"req-{uuid4()}",
        canonical_text="texto",
        category="TECHNICAL",
        normalization_status=normalization_status,
        normalizer_version="test",
        primary_candidate_id=candidate.id,
    )
    link = RequirementCandidateLink(
        requirement_id=requirement.id,
        requirement_candidate_id=candidate.id,
        is_primary_source=True,
        link_origin="DETERMINISTIC",
    )

    db.add(candidate)
    db.add(requirement)
    db.flush()
    db.add(link)

    if review_status is not None:
        db.add(
            RequirementReview(
                tender_id=tender_id,
                requirement_id=requirement.id,
                review_status=review_status,
            )
        )

    db.flush()
    return requirement


def _create_scope_detail(
    db,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool = False,
) -> TenderScopeDetail:
    row = TenderScopeDetail(
        id=str(uuid4()),
        tender_id=tender_id,
        tender_item_id=None,
        scope_segment_id=None,
        candidate_item_key=None,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        domain="TECHNICAL",
        detail_type="ACTIVITY",
        description="detalle",
        normalized_label=None,
        applicability="APPLIES",
        source_method="NATIVE",
        source_artifact_key=f"detail:{uuid4()}",
        source_contract_version="test",
        source_locator=source_locator,
        source_excerpt=source_locator,
        confidence=0.9,
        review_required=review_required,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=f"fp-{uuid4()}",
    )
    db.add(row)
    db.flush()
    return row


def _create_scope_attribute(
    db,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool = False,
) -> TenderScopeAttribute:
    row = TenderScopeAttribute(
        id=str(uuid4()),
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        attribute_name="presion",
        attribute_label_raw="Presion",
        normalized_name="presion",
        value_raw="10",
        unit_raw="bar",
        relation="EXACT",
        source_method="NATIVE",
        source_artifact_key=f"attr:{uuid4()}",
        source_locator=source_locator,
        source_excerpt=source_locator,
        review_required=review_required,
        semantic_fingerprint=f"fp-{uuid4()}",
        confidence=0.9,
        source_contract_version="test",
        source_analysis_id=None,
        source_page_result_id=None,
    )
    db.add(row)
    db.flush()
    return row


def _create_scope_quantity(
    db,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool = False,
) -> TenderScopeQuantity:
    row = TenderScopeQuantity(
        id=str(uuid4()),
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        quantity_raw="5",
        quantity_value=Decimal("5.0000"),
        quantity_min=None,
        quantity_max=None,
        unit_raw="pieza",
        measure_kind="COUNT",
        relation="EXACT",
        source_method="NATIVE",
        source_artifact_key=f"qty:{uuid4()}",
        source_locator=source_locator,
        source_excerpt=source_locator,
        review_required=review_required,
        semantic_fingerprint=f"fp-{uuid4()}",
        confidence=0.9,
        source_contract_version="test",
        source_analysis_id=None,
        source_page_result_id=None,
    )
    db.add(row)
    db.flush()
    return row


def _entity(result, entity_type: str, entity_id: str):
    group = {
        ENTITY_TYPE_REQUIREMENT: result.requirements,
        ENTITY_TYPE_SCOPE_DETAIL: result.scope_details,
        ENTITY_TYPE_SCOPE_ATTRIBUTE: result.scope_attributes,
        ENTITY_TYPE_SCOPE_QUANTITY: result.scope_quantities,
    }[entity_type]
    for row in group:
        if row.entity_id == entity_id:
            return row
    raise AssertionError(f"Projection not found for {entity_type} {entity_id}")


def test_requirement_active_is_effective() -> None:
    tender_id = _create_tender("proj requirement active")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 1",
        )
        db.commit()

        result = project_effective_sources_for_tender(db, tender_id=tender_id)
        projection = _entity(result, ENTITY_TYPE_REQUIREMENT, req.id)

        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_requirement_document_superseded() -> None:
    tender_id = _create_tender("proj requirement superseded")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 1",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        before = db.get(Requirement, req.id)
        assert before is not None
        before_updated_at = before.updated_at

        result = project_effective_sources_for_tender(db, tender_id=tender_id)
        projection = _entity(result, ENTITY_TYPE_REQUIREMENT, req.id)

        after = db.get(Requirement, req.id)
        assert after is not None
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
        assert after.updated_at == before_updated_at
    finally:
        db.close()


def test_requirement_document_revoked() -> None:
    tender_id = _create_tender("proj requirement revoked")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 1",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        result = project_effective_sources_for_tender(db, tender_id=tender_id)
        projection = _entity(result, ENTITY_TYPE_REQUIREMENT, req.id)

        assert projection.status == PROJECTION_STATUS_REVOKED
    finally:
        db.close()


def test_requirement_document_review_required() -> None:
    tender_id = _create_tender("proj requirement doc review")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 1",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
            review_required=True,
        )
        db.commit()

        result = project_effective_sources_for_tender(db, tender_id=tender_id)
        projection = _entity(result, ENTITY_TYPE_REQUIREMENT, req.id)

        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
    finally:
        db.close()


def test_requirement_partial_supersedes() -> None:
    tender_id = _create_tender("proj requirement partial supersedes")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
    finally:
        db.close()


def test_requirement_partial_revokes() -> None:
    tender_id = _create_tender("proj requirement partial revokes")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_REVOKED
    finally:
        db.close()


def test_requirement_non_terminal_overlay() -> None:
    tender_id = _create_tender("proj requirement overlay")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY
    finally:
        db.close()


def test_locator_isolation_in_same_document() -> None:
    tender_id = _create_tender("proj locator isolation")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 5",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_same_locator_different_document_isolation() -> None:
    tender_id = _create_tender("proj same locator different doc")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_no_hierarchy_inference_for_locator() -> None:
    tender_id = _create_tender("proj no hierarchy")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_scope_detail_active() -> None:
    tender_id = _create_tender("proj scope detail active")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 3",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_DETAIL, detail.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_scope_detail_partial_review_required() -> None:
    tender_id = _create_tender("proj scope detail partial review")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_DETAIL, detail.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
    finally:
        db.close()


def test_attribute_parent_superseded_blocks_effective_child() -> None:
    tender_id = _create_tender("proj attribute parent superseded")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
        assert any(item.code == DIAGNOSTIC_PARENT_SCOPE_SUPERSEDED for item in projection.diagnostics)
    finally:
        db.close()


def test_quantity_parent_revoked_blocks_effective_child() -> None:
    tender_id = _create_tender("proj quantity parent revoked")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_REVOKED
        assert any(item.code == DIAGNOSTIC_PARENT_SCOPE_REVOKED for item in projection.diagnostics)
    finally:
        db.close()


def test_attribute_parent_and_child_same_superseded() -> None:
    tender_id = _create_tender("proj attribute same superseded")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 2",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["C"],
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
    finally:
        db.close()


def test_quantity_parent_and_child_same_revoked() -> None:
    tender_id = _create_tender("proj quantity same revoked")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 2",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["C"],
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_REVOKED
    finally:
        db.close()


def test_attribute_parent_superseded_child_revoked_conflict_is_review_required() -> None:
    tender_id = _create_tender("proj attribute terminal conflict")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 2",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["C"],
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_PARENT_CHILD_TERMINAL_STATUS_CONFLICT for item in projection.diagnostics)
    finally:
        db.close()


def test_quantity_parent_revoked_child_superseded_conflict_is_review_required() -> None:
    tender_id = _create_tender("proj quantity terminal conflict")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 2",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_REVOKES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["C"],
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_PARENT_CHILD_TERMINAL_STATUS_CONFLICT for item in projection.diagnostics)
    finally:
        db.close()


def test_parent_review_blocks_clean_effective_child() -> None:
    tender_id = _create_tender("proj parent review child")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        attr = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 9",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
            review_required=True,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attr.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_PARENT_SCOPE_REVIEW_REQUIRED for item in projection.diagnostics)
    finally:
        db.close()


def test_parent_review_keeps_child_terminal_in_review_required() -> None:
    tender_id = _create_tender("proj parent review child terminal")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 7",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
            review_required=True,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["C"],
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_PARENT_SCOPE_REVIEW_REQUIRED for item in projection.diagnostics)
    finally:
        db.close()


def test_parent_unresolved_source_blocks_effective_child() -> None:
    tender_id = _create_tender("proj parent unresolved source")
    external_tender_id = _create_tender("proj parent unresolved source external")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        external_docs, _ = _prepare_docs(db, external_tender_id, ("EXT",))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=external_docs["EXT"],
            document_page_id=pages["A"].id,
            source_locator="numeral ext",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 1",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_UNRESOLVED_SOURCE
    finally:
        db.close()


def test_child_unresolved_source_is_preserved_with_effective_parent() -> None:
    tender_id = _create_tender("proj child unresolved source")
    external_tender_id = _create_tender("proj child unresolved source external")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        external_docs, _ = _prepare_docs(db, external_tender_id, ("EXT",))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 1",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=external_docs["EXT"],
            document_page_id=pages["B"].id,
            source_locator="numeral ext",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_UNRESOLVED_SOURCE
    finally:
        db.close()


def test_parent_overlay_applies_to_effective_child() -> None:
    tender_id = _create_tender("proj parent overlay applies")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        parent_effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        attribute = _create_scope_attribute(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 8",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_ATTRIBUTE, attribute.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY
        assert parent_effect_id in projection.supporting_effect_ids
    finally:
        db.close()


def test_child_overlay_with_effective_parent() -> None:
    tender_id = _create_tender("proj child overlay")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 1",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 7",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["C"],
            affected_locator_raw="numeral 7",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY
    finally:
        db.close()


def test_both_overlay_preserves_parent_and_child_traceability() -> None:
    tender_id = _create_tender("proj both overlay traceability")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C", "D"))
        parent_effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        child_effect_id = _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["D"],
            document_page_id=pages["D"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["C"],
            affected_locator_raw="numeral 7",
            effect_index=2,
        )
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        quantity = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["C"],
            document_page_id=pages["C"].id,
            source_locator="numeral 7",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, quantity.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY
        assert parent_effect_id in projection.supporting_effect_ids
        assert child_effect_id in projection.supporting_effect_ids
    finally:
        db.close()


def test_child_direct_blocker_from_own_source() -> None:
    tender_id = _create_tender("proj child direct blocker")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B", "C"))
        detail = _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 1",
        )
        qty = _create_scope_quantity(
            db,
            tender_id=tender_id,
            scope_detail_id=detail.id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["C"],
            document_page_id=pages["C"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_SCOPE_QUANTITY, qty.id)
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
    finally:
        db.close()


def test_persisted_fact_review_required_blocks_automation() -> None:
    tender_id = _create_tender("proj fact review")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 1",
            normalization_status="REVIEW_REQUIRED",
            review_status="NEEDS_REVIEW",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_FACT_REVIEW_REQUIRED for item in projection.diagnostics)
    finally:
        db.close()


def test_global_unresolved_effect_does_not_blanket_block_entities() -> None:
    tender_id = _create_tender("proj global unresolved")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 1",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=None,
            affected_document_ref_raw="Anexo Z",
            effect_index=1,
            review_required=True,
        )
        db.commit()

        doc_resolution = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        assert doc_resolution.status == TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED

        result = project_effective_sources_for_tender(db, tender_id=tender_id, document_resolution=doc_resolution)
        projection = _entity(result, ENTITY_TYPE_REQUIREMENT, req.id)
        assert result.status == TENDER_PROJECTION_STATUS_REVIEW_REQUIRED
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
    finally:
        db.close()


def test_document_terminal_overrides_partial_overlay() -> None:
    tender_id = _create_tender("proj doc terminal over partial")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=2,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_SUPERSEDED
        assert projection.status != PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY
    finally:
        db.close()


def test_historical_records_remain_unchanged_after_projection() -> None:
    tender_id = _create_tender("proj historical preservation")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="numeral 7",
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
            affected_document_id=docs["B"],
            effect_index=1,
        )
        db.commit()

        before = db.get(Requirement, req.id)
        assert before is not None
        before_snapshot = (before.id, before.updated_at, before.normalization_status)

        _ = project_effective_sources_for_tender(db, tender_id=tender_id)

        after = db.get(Requirement, req.id)
        assert after is not None
        after_snapshot = (after.id, after.updated_at, after.normalization_status)
        assert after_snapshot == before_snapshot
    finally:
        db.close()


def test_no_cross_source_dedupe_keeps_all_entities() -> None:
    tender_id = _create_tender("proj no cross source dedupe")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="texto igual",
        )
        _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator="texto igual",
        )
        db.commit()

        result = project_effective_sources_for_tender(db, tender_id=tender_id)
        assert len(result.requirements) == 2
    finally:
        db.close()


def test_order_independence_same_logical_projection() -> None:
    db = SessionLocal()
    try:
        tender_one = _create_tender("proj order one")
        docs_one, pages_one = _prepare_docs(db, tender_one, ("A", "B", "C"))
        req_one = _create_requirement(
            db,
            tender_id=tender_one,
            source_document_id=docs_one["B"],
            document_page_id=pages_one["B"].id,
            source_locator="numeral 4.2",
        )
        _persist_effect(
            db,
            tender_id=tender_one,
            acting_document_id=docs_one["A"],
            document_page_id=pages_one["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_one["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        tender_two = _create_tender("proj order two")
        docs_two, pages_two = _prepare_docs(db, tender_two, ("A", "B", "C"))
        _persist_effect(
            db,
            tender_id=tender_two,
            acting_document_id=docs_two["A"],
            document_page_id=pages_two["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_AMENDS,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs_two["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        req_two = _create_requirement(
            db,
            tender_id=tender_two,
            source_document_id=docs_two["B"],
            document_page_id=pages_two["B"].id,
            source_locator="numeral 4.2",
        )
        db.commit()

        one = _entity(project_effective_sources_for_tender(db, tender_id=tender_one), ENTITY_TYPE_REQUIREMENT, req_one.id)
        two = _entity(project_effective_sources_for_tender(db, tender_id=tender_two), ENTITY_TYPE_REQUIREMENT, req_two.id)

        assert one.status == two.status
        assert one.partial_locator_status == two.partial_locator_status
    finally:
        db.close()


def test_projection_is_read_only_no_writes() -> None:
    tender_id = _create_tender("proj no mutation")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        _create_scope_detail(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 2",
        )
        db.commit()

        writes: list[str] = []
        connection = db.connection()

        def _capture_writes(_conn, _cursor, statement, _params, _context, _executemany):
            normalized = str(statement).lstrip().upper()
            if normalized.startswith("INSERT") or normalized.startswith("UPDATE") or normalized.startswith("DELETE"):
                writes.append(str(statement))

        event.listen(connection, "before_cursor_execute", _capture_writes)
        try:
            _ = project_effective_sources_for_tender(db, tender_id=tender_id)
        finally:
            event.remove(connection, "before_cursor_execute", _capture_writes)

        assert writes == []
    finally:
        db.close()


def test_absent_locator_remains_effective_without_blanket_block() -> None:
    tender_id = _create_tender("proj absent locator behavior")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A", "B"))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["B"],
            document_page_id=pages["B"].id,
            source_locator=None,
        )
        _persist_effect(
            db,
            tender_id=tender_id,
            acting_document_id=docs["A"],
            document_page_id=pages["A"].id,
            effect_type=SOURCE_EFFECT_TYPE_SUPERSEDES,
            effect_scope=SOURCE_EFFECT_SCOPE_PARTIAL,
            affected_document_id=docs["B"],
            affected_locator_raw="numeral 4.2",
            effect_index=1,
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_EFFECTIVE
        assert any(item.code == DIAGNOSTIC_SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED for item in projection.diagnostics)
    finally:
        db.close()


def test_review_record_pending_blocks_requirement_even_if_source_active() -> None:
    tender_id = _create_tender("proj requirement review row")
    db = SessionLocal()
    try:
        docs, pages = _prepare_docs(db, tender_id, ("A",))
        req = _create_requirement(
            db,
            tender_id=tender_id,
            source_document_id=docs["A"],
            document_page_id=pages["A"].id,
            source_locator="numeral 11",
            normalization_status="NORMALIZED",
            review_status="PENDING",
        )
        db.commit()

        projection = _entity(project_effective_sources_for_tender(db, tender_id=tender_id), ENTITY_TYPE_REQUIREMENT, req.id)
        assert projection.status == PROJECTION_STATUS_REVIEW_REQUIRED
        assert any(item.code == DIAGNOSTIC_FACT_REVIEW_REQUIRED for item in projection.diagnostics)
    finally:
        db.close()
