from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.database import SessionLocal
from app.models import DocumentPage, Requirement, TenderDocument, TenderScopeAttribute, TenderScopeDetail
from app.scope_attribute_integration import (
    SCOPE_ATTRIBUTE_INTEGRATION_REASON_ATTRIBUTE_VALUE_CONFLICT,
    SCOPE_ATTRIBUTE_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
    integrate_scope_attributes_for_scope_detail,
)
from app.scope_attribute_semantic_discovery import (
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    DiscoveredScopeAttribute,
    ScopeAttributeSemanticFragment,
)
from app.scope_attributes import (
    SCOPE_ATTRIBUTE_RELATION_EXACT,
    SCOPE_ATTRIBUTE_RELATION_RANGE,
    SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
    ScopeAttributeCandidate,
    replace_scope_attributes_for_artifact,
)

client = TestClient(app)


class FakeSemanticProvider:
    provider_name = "Fake Semantic Provider"
    provider_version = "fake-semantic-provider-001"
    contract_version = "scope-attribute-semantic-discovery-2026-09-08-001"

    def __init__(
        self,
        *,
        supported: bool = True,
        discovered: list[DiscoveredScopeAttribute] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.supported = supported
        self.discovered = discovered or []
        self.raise_error = raise_error
        self.supports_calls = 0
        self.discover_calls = 0

    def supports(self, fragment: ScopeAttributeSemanticFragment) -> bool:
        del fragment
        self.supports_calls += 1
        return self.supported

    def discover(self, fragment: ScopeAttributeSemanticFragment):
        del fragment
        self.discover_calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        return tuple(self.discovered)


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-ATTRIBUTE-INTEGRATION-{uuid4()}"
    response = client.post(
        "/tenders",
        json={"title": title, "institution_profile": "General", "external_reference": external_reference},
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


def _seed_scope_detail(
    db,
    *,
    tender_id: str,
    document_id: str,
    page: DocumentPage,
    source_method: str,
    source_artifact_key: str,
    source_locator: str,
    source_excerpt: str,
) -> TenderScopeDetail:
    row = TenderScopeDetail(
        tender_id=tender_id,
        tender_item_id=None,
        scope_segment_id=None,
        candidate_item_key=None,
        source_document_id=document_id,
        document_page_id=page.id,
        source_analysis_id=None,
        source_page_result_id=None,
        domain="SUPPLY",
        detail_type="DETAIL",
        description=source_excerpt,
        normalized_label=None,
        applicability="UNRESOLVED",
        source_method=source_method,
        source_artifact_key=source_artifact_key,
        source_contract_version=None,
        source_locator=source_locator,
        source_excerpt=source_excerpt,
        confidence=None,
        review_required=False,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=hashlib.sha256(
            f"scope-detail|{tender_id}|{document_id}|{page.id}|{source_artifact_key}|{source_locator}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _persist_deterministic_attribute(
    db,
    *,
    scope_detail: TenderScopeDetail,
    attribute_name: str,
    value_raw: str,
    relation: str = SCOPE_ATTRIBUTE_RELATION_EXACT,
    unit_raw: str | None = None,
) -> None:
    existing_rows = list(
        db.execute(
            select(TenderScopeAttribute).where(
                TenderScopeAttribute.scope_detail_id == scope_detail.id,
                TenderScopeAttribute.source_artifact_key == scope_detail.source_artifact_key,
            )
        ).scalars()
    )

    candidates = [
        ScopeAttributeCandidate(
            tender_id=row.tender_id,
            scope_detail_id=row.scope_detail_id,
            source_document_id=row.source_document_id,
            document_page_id=row.document_page_id,
            source_method=row.source_method,
            source_artifact_key=row.source_artifact_key,
            source_locator=row.source_locator,
            source_excerpt=row.source_excerpt,
            attribute_name=row.attribute_name,
            value_raw=row.value_raw,
            review_required=row.review_required,
            unit_raw=row.unit_raw,
            relation=row.relation,
            attribute_label_raw=row.attribute_label_raw,
            normalized_name=row.normalized_name,
            confidence=row.confidence,
            source_contract_version=row.source_contract_version,
            source_analysis_id=row.source_analysis_id,
            source_page_result_id=row.source_page_result_id,
        )
        for row in existing_rows
    ]

    candidates.append(
        ScopeAttributeCandidate(
            tender_id=scope_detail.tender_id,
            scope_detail_id=scope_detail.id,
            source_document_id=scope_detail.source_document_id,
            document_page_id=scope_detail.document_page_id,
            source_method=scope_detail.source_method,
            source_artifact_key=scope_detail.source_artifact_key,
            source_locator=f"{scope_detail.source_locator}|attr:{attribute_name}",
            source_excerpt=scope_detail.source_excerpt,
            attribute_name=attribute_name,
            value_raw=value_raw,
            review_required=False,
            unit_raw=unit_raw,
            relation=relation,
        )
    )

    replace_scope_attributes_for_artifact(
        db,
        tender_id=scope_detail.tender_id,
        scope_detail_id=scope_detail.id,
        source_document_id=scope_detail.source_document_id,
        document_page_id=scope_detail.document_page_id,
        source_artifact_key=scope_detail.source_artifact_key,
        candidates=candidates,
    )


def _count_scope_attributes(db, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeAttribute.id)).where(TenderScopeAttribute.scope_detail_id == scope_detail_id))
    return int(value or 0)


def _semantic(
    *,
    name: str,
    value: str,
    evidence: str,
    relation: str | None = None,
    unit_raw: str | None = None,
) -> DiscoveredScopeAttribute:
    return DiscoveredScopeAttribute(
        attribute_name=name,
        value_raw=value,
        evidence_excerpt=evidence,
        relation=relation,
        unit_raw=unit_raw,
        confidence=None,
    )


def test_invalid_evidence_fails_closed_before_semantic_provider_call() -> None:
    db = SessionLocal()
    provider = FakeSemanticProvider(
        discovered=[_semantic(name="brand", value="YOKOGAWA", evidence="MARCA: YOKOGAWA")]
    )
    try:
        result = integrate_scope_attributes_for_scope_detail(
            db,
            scope_detail_id="missing-scope-detail",
            semantic_provider=provider,
        )

        assert result.deterministic_status == "INVALID_EVIDENCE"
        assert result.semantic_status == SCOPE_ATTRIBUTE_INTEGRATION_SEMANTIC_STATUS_SKIPPED
        assert provider.supports_calls == 0
        assert provider.discover_calls == 0
        assert result.semantic_review_count == 0
    finally:
        db.close()


def test_unsupported_deterministic_allows_semantic_without_inserting_rows() -> None:
    tender_id = _create_tender("integration unsupported deterministic")
    document_id = _import_pdf(tender_id, "integration-unsupported.pdf")

    db = SessionLocal()
    try:
        source_text = (
            "FUENTE DE ALIMENTACION DE 100-120VCA, MARCA: YOKOGAWA, MODELO: PW481-50, PROTOCOLO: ESB BUS"
        )
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-120",
            source_excerpt=source_text,
        )
        db.commit()

        provider = FakeSemanticProvider(
            discovered=[
                _semantic(name="brand", value="YOKOGAWA", evidence="MARCA: YOKOGAWA"),
                _semantic(name="model", value="PW481-50", evidence="MODELO: PW481-50"),
                _semantic(name="power_supply", value="100-120VCA", evidence="FUENTE DE ALIMENTACION DE 100-120VCA"),
            ]
        )

        before_count = _count_scope_attributes(db, scope_detail.id)
        result = integrate_scope_attributes_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            semantic_provider=provider,
        )
        db.commit()

        after_count = _count_scope_attributes(db, scope_detail.id)
        assert before_count == 0
        assert after_count == 0
        assert result.deterministic_status == "UNSUPPORTED"
        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert result.semantic_discovered_count == 3
        assert result.semantic_review_count == 3
        assert result.duplicate_suppressed_count == 0
        assert result.conflict_count == 0
        assert all(candidate.review_required for candidate in result.semantic_review_candidates)
        assert all(candidate.source_method == "NATIVE" for candidate in result.semantic_review_candidates)
        assert result.semantic_provider_name == provider.provider_name
        assert result.semantic_provider_version == provider.provider_version
        assert result.semantic_contract_version == provider.contract_version
    finally:
        db.close()


def test_duplicate_suppression_with_deterministic_precedence_and_semantic_only_candidate() -> None:
    tender_id = _create_tender("integration duplicate suppression")
    document_id = _import_pdf(tender_id, "integration-duplicates.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA MODELO: PW481-50 FUENTE DE ALIMENTACION DE 100-120VCA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-90",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="model", value_raw="PW481-50")
        db.commit()

        provider = FakeSemanticProvider(
            discovered=[
                _semantic(name="brand", value="YOKOGAWA", evidence="MARCA: YOKOGAWA"),
                _semantic(name="model", value="PW481-50", evidence="MODELO: PW481-50", relation=SCOPE_ATTRIBUTE_RELATION_RANGE),
                _semantic(
                    name="power_supply",
                    value="100-120VCA",
                    evidence="FUENTE DE ALIMENTACION DE 100-120VCA",
                    relation=SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
                    unit_raw="VCA",
                ),
            ]
        )

        result = integrate_scope_attributes_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            semantic_provider=provider,
        )
        db.commit()

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert result.duplicate_suppressed_count == 2
        assert result.semantic_review_count == 1
        assert result.conflict_count == 0
        assert result.semantic_review_candidates[0].attribute_name == "power_supply"
        reasons = {item.reason for item in result.suppressed_duplicates}
        assert any("semantic duplicate suppressed" in reason for reason in reasons)

        persisted_rows = list(
            db.execute(
                select(TenderScopeAttribute)
                .where(TenderScopeAttribute.scope_detail_id == scope_detail.id)
                .order_by(TenderScopeAttribute.attribute_name.asc())
            ).scalars()
        )
        assert [row.attribute_name for row in persisted_rows] == ["brand", "model"]
        assert all(row.relation == SCOPE_ATTRIBUTE_RELATION_EXACT for row in persisted_rows)
    finally:
        db.close()


def test_conflict_and_non_synonym_rule() -> None:
    tender_id = _create_tender("integration conflicts")
    document_id = _import_pdf(tender_id, "integration-conflicts.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA; MARCA PROPUESTA: ABB; FABRICANTE: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-80",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        db.commit()

        provider = FakeSemanticProvider(
            discovered=[
                _semantic(name="brand", value="ABB", evidence="MARCA PROPUESTA: ABB"),
                _semantic(name="manufacturer", value="YOKOGAWA", evidence="FABRICANTE: YOKOGAWA"),
            ]
        )

        result = integrate_scope_attributes_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            semantic_provider=provider,
        )

        assert result.conflict_count == 1
        assert result.conflicts[0].reason == SCOPE_ATTRIBUTE_INTEGRATION_REASON_ATTRIBUTE_VALUE_CONFLICT
        assert result.conflicts[0].attribute_name == "brand"
        assert result.conflicts[0].deterministic_value_raw == "YOKOGAWA"
        assert result.semantic_review_count == 2
        assert {c.attribute_name for c in result.semantic_review_candidates} == {"brand", "manufacturer"}
    finally:
        db.close()


def test_semantic_no_attributes_keeps_deterministic_rows() -> None:
    tender_id = _create_tender("integration semantic no attributes")
    document_id = _import_pdf(tender_id, "integration-semantic-no-attrs.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        db.commit()

        provider = FakeSemanticProvider(discovered=[])
        result = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES
        assert _count_scope_attributes(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_invalid_output_is_non_destructive() -> None:
    tender_id = _create_tender("integration semantic invalid output")
    document_id = _import_pdf(tender_id, "integration-semantic-invalid.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        db.commit()

        provider = FakeSemanticProvider(
            discovered=[_semantic(name="brand", value="YOKOGAWA", evidence="EVIDENCIA AJENA")]
        )
        result = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert _count_scope_attributes(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_unsupported_is_non_destructive() -> None:
    tender_id = _create_tender("integration semantic unsupported")
    document_id = _import_pdf(tender_id, "integration-semantic-unsupported.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        db.commit()

        provider = FakeSemanticProvider(supported=False)
        result = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED
        assert _count_scope_attributes(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_provider_exception_is_non_destructive() -> None:
    tender_id = _create_tender("integration semantic exception")
    document_id = _import_pdf(tender_id, "integration-semantic-exception.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt=source_text,
        )
        _persist_deterministic_attribute(db, scope_detail=scope_detail, attribute_name="brand", value_raw="YOKOGAWA")
        db.commit()

        provider = FakeSemanticProvider(raise_error=RuntimeError("synthetic provider failure"))
        result = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert _count_scope_attributes(db, scope_detail.id) == 1
    finally:
        db.close()


def test_idempotent_results_and_no_row_accumulation() -> None:
    tender_id = _create_tender("integration idempotency")
    document_id = _import_pdf(tender_id, "integration-idempotency.pdf")

    db = SessionLocal()
    try:
        source_text = "PROTOCOLO: ESB BUS"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-18",
            source_excerpt=source_text,
        )
        db.commit()

        provider = FakeSemanticProvider(
            discovered=[_semantic(name="protocol", value="ESB BUS", evidence="PROTOCOLO: ESB BUS")]
        )

        before_count = _count_scope_attributes(db, scope_detail.id)
        first = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)
        second = integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail.id, semantic_provider=provider)
        after_count = _count_scope_attributes(db, scope_detail.id)

        assert before_count == 0
        assert after_count == 0
        assert first.semantic_status == second.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert first.semantic_review_count == second.semantic_review_count == 1
        assert first.duplicate_suppressed_count == second.duplicate_suppressed_count == 0
        assert first.conflict_count == second.conflict_count == 0
    finally:
        db.close()


def test_boundary_isolation_no_cross_scope_deletion_or_requirement_changes() -> None:
    tender_id = _create_tender("integration boundary isolation")
    document_id = _import_pdf(tender_id, "integration-boundary-isolation.pdf")

    db = SessionLocal()
    try:
        page_a = _seed_page(db, document_id, 1, "MARCA: YOKOGAWA")
        page_b = _seed_page(db, document_id, 2, "MODELO: PW481-50")

        scope_a = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_a,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page_a.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt="MARCA: YOKOGAWA",
        )
        scope_b = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page_b,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page_b.id}",
            source_locator="page:2|chars:0-18",
            source_excerpt="MODELO: PW481-50",
        )

        _persist_deterministic_attribute(db, scope_detail=scope_b, attribute_name="model", value_raw="PW481-50")

        requirement = Requirement(
            tender_id=tender_id,
            canonical_key=f"req-{uuid4()}",
            canonical_text="No debe cambiar en integración de atributos",
            category="TECHNICAL",
            normalization_status="REVIEW_REQUIRED",
            normalizer_version="mvp-04.3",
        )
        db.add(requirement)
        db.commit()

        attrs_scope_b_before = _count_scope_attributes(db, scope_b.id)
        details_before = int(db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)) or 0)
        req_before = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        provider = FakeSemanticProvider(
            discovered=[_semantic(name="brand", value="YOKOGAWA", evidence="MARCA: YOKOGAWA")]
        )
        integrate_scope_attributes_for_scope_detail(db, scope_detail_id=scope_a.id, semantic_provider=provider)

        attrs_scope_b_after = _count_scope_attributes(db, scope_b.id)
        details_after = int(db.scalar(select(func.count(TenderScopeDetail.id)).where(TenderScopeDetail.tender_id == tender_id)) or 0)
        req_after = int(db.scalar(select(func.count(Requirement.id)).where(Requirement.tender_id == tender_id)) or 0)

        assert attrs_scope_b_before == attrs_scope_b_after == 1
        assert details_before == details_after == 2
        assert req_before == req_after == 1
    finally:
        db.close()


def test_review_required_invariant_defensive_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    tender_id = _create_tender("integration review required invariant")
    document_id = _import_pdf(tender_id, "integration-invariant.pdf")

    db = SessionLocal()
    try:
        source_text = "MARCA: YOKOGAWA"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(
            db,
            tender_id=tender_id,
            document_id=document_id,
            page=page,
            source_method="NATIVE",
            source_artifact_key=f"DocumentPage:{page.id}",
            source_locator="page:1|chars:0-20",
            source_excerpt=source_text,
        )
        db.commit()

        import app.scope_attribute_integration as integration_module

        def _broken_mapper(fragment, discovered):
            del fragment, discovered
            return ScopeAttributeCandidate(
                tender_id=scope_detail.tender_id,
                scope_detail_id=scope_detail.id,
                source_document_id=scope_detail.source_document_id,
                document_page_id=scope_detail.document_page_id,
                source_method="NATIVE",
                source_artifact_key=scope_detail.source_artifact_key,
                source_locator=scope_detail.source_locator,
                source_excerpt=scope_detail.source_excerpt,
                attribute_name="brand",
                value_raw="YOKOGAWA",
                review_required=False,
            )

        monkeypatch.setattr(integration_module, "map_discovered_scope_attribute_to_candidate", _broken_mapper)

        provider = FakeSemanticProvider(
            discovered=[_semantic(name="brand", value="YOKOGAWA", evidence="MARCA: YOKOGAWA")]
        )
        result = integration_module.integrate_scope_attributes_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            semantic_provider=provider,
        )

        assert result.semantic_status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert any("review_required invariant failed" in msg for msg in result.diagnostics)
    finally:
        db.close()
