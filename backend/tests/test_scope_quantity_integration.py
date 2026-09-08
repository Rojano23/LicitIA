from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument, TenderScopeDetail, TenderScopeQuantity
from app.scope_quantities import (
    SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    SCOPE_QUANTITY_RELATION_EXACT,
    ScopeQuantityCandidate,
)
from app.scope_quantity_adapters import ScopeQuantityEvidenceArtifact
from app.scope_quantity_integration import (
    SCOPE_QUANTITY_INTEGRATION_REASON_DUPLICATE_DETERMINISTIC,
    SCOPE_QUANTITY_INTEGRATION_REASON_NORMALIZATION_CONFLICT,
    SCOPE_QUANTITY_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
    SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY,
    SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED,
    SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_INVALID,
    SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_ONLY,
    integrate_scope_quantities_for_scope_detail,
)
from app.scope_quantity_semantic_discovery import (
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    DiscoveredScopeQuantity,
    ScopeQuantityProviderDiscoveryPayload,
    ScopeQuantitySemanticFragment,
)

client = TestClient(app)


class FakeDeterministicAdapter:
    adapter_name = "FakeDeterministicAdapter"
    adapter_version = "fake-deterministic-adapter-001"

    def __init__(self, candidates: list[ScopeQuantityCandidate] | None = None) -> None:
        self._candidates = tuple(candidates or ())

    def supports(self, artifact: ScopeQuantityEvidenceArtifact) -> bool:
        del artifact
        return True

    def extract_candidates(self, db, artifact: ScopeQuantityEvidenceArtifact):
        del db
        return tuple(self._candidates)


class FakeSemanticProvider:
    provider_name = "Fake Semantic Quantity Provider"
    provider_version = "fake-semantic-quantity-provider-001"
    contract_version = "scope-quantity-semantic-discovery-2026-09-08-003"

    def __init__(
        self,
        *,
        supported: bool = True,
        status: str = SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        quantities: list[DiscoveredScopeQuantity] | None = None,
        errors: tuple[str, ...] = (),
        raise_error: Exception | None = None,
    ) -> None:
        self._supported = supported
        self._status = status
        self._quantities = tuple(quantities or ())
        self._errors = tuple(errors)
        self._raise_error = raise_error
        self.supports_calls = 0
        self.discover_calls = 0

    def supports(self, fragment: ScopeQuantitySemanticFragment) -> bool:
        del fragment
        self.supports_calls += 1
        return self._supported

    def discover(self, fragment: ScopeQuantitySemanticFragment) -> ScopeQuantityProviderDiscoveryPayload:
        del fragment
        self.discover_calls += 1
        if self._raise_error is not None:
            raise self._raise_error
        return ScopeQuantityProviderDiscoveryPayload(
            status=self._status,
            quantities=self._quantities,
            errors=self._errors,
        )


def _create_tender(title: str) -> str:
    external_reference = f"SCOPE-QUANTITY-INTEGRATION-{uuid4()}"
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
        source_method="NATIVE",
        source_artifact_key=f"DocumentPage:{page.id}",
        source_contract_version="vision-detail-transcription-2026-08-31-001",
        source_locator="page:1|detail_row:0",
        source_excerpt=source_excerpt,
        confidence=None,
        review_required=False,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=hashlib.sha256(
            f"scope-detail|{tender_id}|{document_id}|{page.id}|{uuid4()}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(row)
    db.flush()
    return row


def _deterministic_candidate(scope_detail: TenderScopeDetail, *, quantity_raw: str, unit_raw: str, value: str) -> ScopeQuantityCandidate:
    excerpt = scope_detail.source_excerpt
    return ScopeQuantityCandidate(
        tender_id=scope_detail.tender_id,
        scope_detail_id=scope_detail.id,
        source_document_id=scope_detail.source_document_id,
        document_page_id=scope_detail.document_page_id,
        quantity_raw=quantity_raw,
        quantity_value=Decimal(value),
        quantity_min=None,
        quantity_max=None,
        unit_raw=unit_raw,
        measure_kind=SCOPE_QUANTITY_MEASURE_KIND_COUNT,
        relation=SCOPE_QUANTITY_RELATION_EXACT,
        source_method=scope_detail.source_method,
        source_artifact_key=scope_detail.source_artifact_key,
        source_locator=scope_detail.source_locator,
        source_excerpt=excerpt,
        review_required=False,
        confidence=None,
        source_contract_version=scope_detail.source_contract_version,
        source_analysis_id=scope_detail.source_analysis_id,
        source_page_result_id=scope_detail.source_page_result_id,
    )


def _semantic_quantity(*, quantity_raw: str, unit_raw: str | None, value_raw: str | None, min_raw: str | None, max_raw: str | None, evidence: str) -> DiscoveredScopeQuantity:
    return DiscoveredScopeQuantity(
        quantity_raw=quantity_raw,
        unit_raw=unit_raw,
        measure_kind=SCOPE_QUANTITY_MEASURE_KIND_COUNT,
        relation=SCOPE_QUANTITY_RELATION_EXACT,
        quantity_value_raw=value_raw,
        quantity_min_raw=min_raw,
        quantity_max_raw=max_raw,
        evidence_excerpt=evidence,
        confidence=1.0,
    )


def _count_scope_quantities(db, scope_detail_id: str) -> int:
    value = db.scalar(select(func.count(TenderScopeQuantity.id)).where(TenderScopeQuantity.scope_detail_id == scope_detail_id))
    return int(value or 0)


def test_deterministic_only_without_semantic_provider_and_without_semantic_discoverer_call() -> None:
    tender_id = _create_tender("quantity integration deterministic only")
    document_id = _import_pdf(tender_id, "quantity-integration-deterministic-only.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        candidate = _deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")
        adapter = FakeDeterministicAdapter([candidate])

        def _should_not_run(fragment, provider):
            del fragment, provider
            raise AssertionError("semantic_discoverer should not run when semantic_provider is None")

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=None,
            semantic_discoverer=_should_not_run,
        )
        db.commit()

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
        assert result.semantic_discovery_status == SCOPE_QUANTITY_INTEGRATION_SEMANTIC_STATUS_SKIPPED
        assert result.deterministic_count == 1
        assert result.semantic_supplement_count == 0
        assert result.duplicate_semantic_count == 0
        assert result.conflict_semantic_count == 0
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_exact_duplicate_semantic_candidate_is_suppressed() -> None:
    tender_id = _create_tender("quantity integration duplicate")
    document_id = _import_pdf(tender_id, "quantity-integration-duplicate.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="2",
                    unit_raw="equipos",
                    value_raw="2",
                    min_raw=None,
                    max_raw=None,
                    evidence="2 equipos",
                )
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
        assert result.semantic_discovery_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert result.deterministic_count == 1
        assert result.semantic_supplement_count == 0
        assert result.duplicate_semantic_count == 1
        assert result.conflict_semantic_count == 0
        assert result.duplicate_semantic_candidates[0].reason == SCOPE_QUANTITY_INTEGRATION_REASON_DUPLICATE_DETERMINISTIC
        assert result.duplicate_semantic_candidates[0].semantic_candidate.review_required is True
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_only_supplement_when_no_deterministic_quantity_exists() -> None:
    tender_id = _create_tender("quantity integration semantic only")
    document_id = _import_pdf(tender_id, "quantity-integration-semantic-only.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere tres equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="tres",
                    unit_raw="equipos",
                    value_raw="3",
                    min_raw=None,
                    max_raw=None,
                    evidence="tres equipos",
                )
            ]
        )

        before_count = _count_scope_quantities(db, scope_detail.id)
        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )
        after_count = _count_scope_quantities(db, scope_detail.id)

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_ONLY
        assert result.deterministic_count == 0
        assert result.semantic_supplement_count == 1
        assert result.semantic_supplements[0].review_required is True
        assert before_count == 0
        assert after_count == 0
    finally:
        db.close()


def test_deterministic_plus_distinct_semantic_is_integrated_without_merging() -> None:
    tender_id = _create_tender("quantity integration deterministic plus semantic")
    document_id = _import_pdf(tender_id, "quantity-integration-both.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 1 equipo y tres equipos adicionales"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="1", unit_raw="equipo", value="1")])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="tres",
                    unit_raw="equipos",
                    value_raw="3",
                    min_raw=None,
                    max_raw=None,
                    evidence="tres equipos",
                )
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED
        assert result.deterministic_count == 1
        assert result.semantic_supplement_count == 1
        assert result.duplicate_semantic_count == 0
        assert result.conflict_semantic_count == 0
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_normalization_conflict_detected_with_deterministic_precedence() -> None:
    tender_id = _create_tender("quantity integration normalization conflict")
    document_id = _import_pdf(tender_id, "quantity-integration-conflict.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="2",
                    unit_raw="equipos",
                    value_raw="3",
                    min_raw=None,
                    max_raw=None,
                    evidence="2 equipos",
                )
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED
        assert result.deterministic_count == 1
        assert result.semantic_supplement_count == 0
        assert result.conflict_semantic_count == 1
        assert result.conflict_semantic_candidates[0].reason == SCOPE_QUANTITY_INTEGRATION_REASON_NORMALIZATION_CONFLICT
        assert result.conflict_semantic_candidates[0].semantic_candidate.review_required is True
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_multiple_same_kind_semantic_quantities_are_not_collapsed() -> None:
    tender_id = _create_tender("quantity integration multiple same kind")
    document_id = _import_pdf(tender_id, "quantity-integration-multi.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 1 pieza y 2 piezas y 3 piezas"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="1", unit_raw="pieza", value="1")])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="2",
                    unit_raw="piezas",
                    value_raw="2",
                    min_raw=None,
                    max_raw=None,
                    evidence="2 piezas",
                ),
                _semantic_quantity(
                    quantity_raw="3",
                    unit_raw="piezas",
                    value_raw="3",
                    min_raw=None,
                    max_raw=None,
                    evidence="3 piezas",
                ),
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED
        assert result.semantic_supplement_count == 2
        assert result.conflict_semantic_count == 0
        assert result.duplicate_semantic_count == 0
    finally:
        db.close()


def test_semantic_invalid_output_keeps_deterministic_quantities() -> None:
    tender_id = _create_tender("quantity integration semantic invalid")
    document_id = _import_pdf(tender_id, "quantity-integration-invalid.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(
            quantities=[
                DiscoveredScopeQuantity(
                    quantity_raw="2",
                    unit_raw="equipos",
                    measure_kind=None,
                    relation=SCOPE_QUANTITY_RELATION_EXACT,
                    quantity_value_raw="2",
                    quantity_min_raw=None,
                    quantity_max_raw=None,
                    evidence_excerpt="2 equipos",
                    confidence=0.8,
                )
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_INVALID
        assert result.semantic_discovery_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert result.deterministic_count == 1
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_review_required_keeps_deterministic_quantities() -> None:
    tender_id = _create_tender("quantity integration semantic review required")
    document_id = _import_pdf(tender_id, "quantity-integration-review-required.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED)

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED
        assert result.semantic_discovery_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.deterministic_count == 1
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_semantic_no_quantities_cannot_erase_deterministic() -> None:
    tender_id = _create_tender("quantity integration semantic no quantities")
    document_id = _import_pdf(tender_id, "quantity-integration-no-quantities.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES)

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
        assert result.semantic_discovery_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES
        assert result.deterministic_count == 1
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()


def test_provider_metadata_does_not_change_source_method_or_persistence_identity() -> None:
    tender_id = _create_tender("quantity integration provider metadata")
    document_id = _import_pdf(tender_id, "quantity-integration-provider-metadata.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere tres equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([])
        provider = FakeSemanticProvider(
            quantities=[
                _semantic_quantity(
                    quantity_raw="tres",
                    unit_raw="equipos",
                    value_raw="3",
                    min_raw=None,
                    max_raw=None,
                    evidence="tres equipos",
                )
            ]
        )

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.semantic_provider_metadata is not None
        assert result.semantic_provider_metadata.provider_name == provider.provider_name
        assert result.semantic_provider_metadata.provider_version == provider.provider_version
        assert result.semantic_provider_metadata.contract_version == provider.contract_version
        assert result.semantic_supplements[0].source_method == "NATIVE"
        assert result.semantic_supplements[0].source_artifact_key == scope_detail.source_artifact_key
        assert _count_scope_quantities(db, scope_detail.id) == 0

        persisted = list(
            db.execute(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == scope_detail.id)).scalars()
        )
        assert persisted == []
    finally:
        db.close()


def test_semantic_provider_unsupported_isolated_from_deterministic() -> None:
    tender_id = _create_tender("quantity integration semantic unsupported")
    document_id = _import_pdf(tender_id, "quantity-integration-semantic-unsupported.pdf")

    db = SessionLocal()
    try:
        source_text = "Se requiere 2 equipos para el servicio"
        page = _seed_page(db, document_id, 1, source_text)
        scope_detail = _seed_scope_detail(db, tender_id=tender_id, document_id=document_id, page=page, source_excerpt=source_text)
        db.commit()

        adapter = FakeDeterministicAdapter([_deterministic_candidate(scope_detail, quantity_raw="2", unit_raw="equipos", value="2")])
        provider = FakeSemanticProvider(supported=False, status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED)

        result = integrate_scope_quantities_for_scope_detail(
            db,
            scope_detail_id=scope_detail.id,
            adapters=(adapter,),
            semantic_provider=provider,
        )

        assert result.status == SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
        assert result.semantic_discovery_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED
        assert result.deterministic_count == 1
        assert _count_scope_quantities(db, scope_detail.id) == 1
    finally:
        db.close()
