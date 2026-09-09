from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument
from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW,
    SourceEffectProviderDiscoveryPayload,
    SourceEffectSemanticFragment,
    discover_source_effect_semantics,
)
from app.source_effect_deterministic import (
    SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT,
    SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET,
    SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT,
)

client = TestClient(app)


class _StubProvider:
    provider_name = "Stub Source Effect Provider"
    provider_version = "stub-001"
    contract_version = "stub-contract-001"

    def __init__(self, *, supports: bool, payload: SourceEffectProviderDiscoveryPayload) -> None:
        self._supports = supports
        self._payload = payload

    def supports(self, fragment: SourceEffectSemanticFragment) -> bool:
        return self._supports

    def discover(self, fragment: SourceEffectSemanticFragment) -> SourceEffectProviderDiscoveryPayload:
        return self._payload


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-SEM-{uuid4()}",
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


def _fragment(
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_text: str,
    source_method: str = "NATIVE",
) -> SourceEffectSemanticFragment:
    return SourceEffectSemanticFragment(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        document_page_id=document_page_id,
        page_number=1,
        source_method=source_method,
        source_artifact_key=f"native-page:{document_page_id}",
        source_locator="page:1",
        source_text=source_text,
        source_contract_version="source-effect-semantic-discovery-2026-09-08-001",
    )


def _effect(
    *,
    effect_type: str,
    effect_scope: str,
    affected_document_ref_raw: str | None,
    affected_locator_raw: str | None,
    effective_date_raw: str | None,
    evidence_excerpt: str,
    confidence: float | None = 0.9,
) -> DiscoveredSourceEffect:
    return DiscoveredSourceEffect(
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=affected_document_ref_raw,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=effective_date_raw,
        evidence_excerpt=evidence_excerpt,
        confidence=confidence,
    )


def test_unique_target_resolves_and_candidate_stays_review_required() -> None:
    tender_id = _create_tender("source effect semantic unique target")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B, numeral 4.2.")
        _seed_page(db, affected_doc_id, 2, "contenido")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="AMENDS",
                    effect_scope="PARTIAL",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw="numeral 4.2",
                    effective_date_raw=None,
                    evidence_excerpt="Se modifica Anexo B, numeral 4.2.",
                ),
            ),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo B, numeral 4.2.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert result.candidate_count == 1
        candidate = result.candidates[0]
        assert candidate.affected_document_id == affected_doc_id
        assert candidate.affected_document_ref_raw == "Anexo B"
        assert candidate.review_required is True
        assert candidate.source_method == "NATIVE"
    finally:
        db.close()


def test_zero_match_target_keeps_raw_and_marks_review_with_diagnostic() -> None:
    tender_id = _create_tender("source effect semantic zero match")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo Z en su totalidad.")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="AMENDS",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo Z",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    evidence_excerpt="Se modifica Anexo Z en su totalidad.",
                ),
            ),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo Z en su totalidad.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidates[0].affected_document_id is None
        assert result.candidates[0].affected_document_ref_raw == "Anexo Z"
        assert SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT in result.diagnostics
    finally:
        db.close()


def test_ambiguous_match_keeps_raw_and_marks_review() -> None:
    tender_id = _create_tender("source effect semantic ambiguous")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    _ = _import_pdf(tender_id, "anexo-b-v1.pdf")
    _ = _import_pdf(tender_id, "anexo-b-v2.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B en su totalidad.")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="AMENDS",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    evidence_excerpt="Se modifica Anexo B en su totalidad.",
                ),
            ),
        )
        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo B en su totalidad.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidates[0].affected_document_id is None
        assert SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT in result.diagnostics
    finally:
        db.close()


def test_self_target_keeps_review_candidate_and_diagnostic() -> None:
    tender_id = _create_tender("source effect semantic self target")
    acting_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B en su totalidad.")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="AMENDS",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    evidence_excerpt="Se modifica Anexo B en su totalidad.",
                ),
            ),
        )
        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo B en su totalidad.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidates[0].affected_document_id is None
        assert SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET in result.diagnostics
    finally:
        db.close()


def test_cross_tender_document_never_resolves() -> None:
    tender_a = _create_tender("source effect semantic cross tender A")
    tender_b = _create_tender("source effect semantic cross tender B")
    acting_doc_id = _import_pdf(tender_a, "junta.pdf")
    _ = _import_pdf(tender_b, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B en su totalidad.")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="AMENDS",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    evidence_excerpt="Se modifica Anexo B en su totalidad.",
                ),
            ),
        )
        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_a,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo B en su totalidad.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidates[0].affected_document_id is None
        assert SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT in result.diagnostics
    finally:
        db.close()


def test_triadic_replacement_preserves_review_diagnostic() -> None:
    tender_id = _create_tender("source effect semantic triadic")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")
    _ = _import_pdf(tender_id, "anexo-c.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se sustituye Anexo B por Anexo C.")
        _seed_page(db, affected_doc_id, 1, "contenido")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="SUPERSEDES",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    evidence_excerpt="Se sustituye Anexo B por Anexo C.",
                ),
            ),
        )
        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se sustituye Anexo B por Anexo C.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidate_count == 1
        assert result.candidates[0].affected_document_id == affected_doc_id
        assert SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW in result.diagnostics
    finally:
        db.close()


def test_multiple_effects_and_dedupe_by_semantic_fingerprint() -> None:
    tender_id = _create_tender("source effect semantic multiple")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    _ = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B, numeral 4.2. Se modifica Anexo B, numeral 4.3.")
        db.commit()

        effect_a = _effect(
            effect_type="AMENDS",
            effect_scope="PARTIAL",
            affected_document_ref_raw="Anexo B",
            affected_locator_raw="numeral 4.2",
            effective_date_raw=None,
            evidence_excerpt="Se modifica Anexo B, numeral 4.2.",
        )
        payload = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(effect_a, effect_a),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se modifica Anexo B, numeral 4.2. Se modifica Anexo B, numeral 4.3.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status in {
            SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
            SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
        }
        assert result.candidate_count == 1
    finally:
        db.close()


def test_provider_review_required_zero_effects_is_preserved() -> None:
    tender_id = _create_tender("source effect semantic review required zero")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Texto ambiguo sobre documentos.")
        db.commit()

        payload = SourceEffectProviderDiscoveryPayload(
            status="REVIEW_REQUIRED",
            effects=(),
            diagnostics=("AMBIGUOUS_EFFECT_SCOPE",),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Texto ambiguo sobre documentos.",
            ),
            providers=(_StubProvider(supports=True, payload=payload),),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        assert result.candidate_count == 0
        assert "AMBIGUOUS_EFFECT_SCOPE" in result.diagnostics
    finally:
        db.close()


def test_invalid_contract_and_grounding_fail_closed() -> None:
    tender_id = _create_tender("source effect semantic invalid")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.")
        db.commit()

        payload_unknown_type = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="MODIFIES",
                    effect_scope="PARTIAL",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw="numeral 4.2",
                    effective_date_raw="2026-09-08",
                    evidence_excerpt="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
                ),
            ),
        )
        result_unknown_type = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
            ),
            providers=(_StubProvider(supports=True, payload=payload_unknown_type),),
        )
        assert result_unknown_type.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT

        payload_bad_grounding = SourceEffectProviderDiscoveryPayload(
            status="DISCOVERED",
            effects=(
                _effect(
                    effect_type="CORRECTS",
                    effect_scope="PARTIAL",
                    affected_document_ref_raw="Anexo C",
                    affected_locator_raw="numeral 4.2",
                    effective_date_raw="2026-09-08",
                    evidence_excerpt="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
                ),
            ),
        )
        result_bad_grounding = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
            ),
            providers=(_StubProvider(supports=True, payload=payload_bad_grounding),),
        )
        assert result_bad_grounding.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT

        payload_discovered_empty = SourceEffectProviderDiscoveryPayload(status="DISCOVERED", effects=())
        result_discovered_empty = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
            ),
            providers=(_StubProvider(supports=True, payload=payload_discovered_empty),),
        )
        assert result_discovered_empty.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT

        payload_no_effects_with_items = SourceEffectProviderDiscoveryPayload(
            status="NO_EFFECTS",
            effects=(
                _effect(
                    effect_type="CORRECTS",
                    effect_scope="PARTIAL",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw="numeral 4.2",
                    effective_date_raw="2026-09-08",
                    evidence_excerpt="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
                ),
            ),
        )
        result_no_effects_with_items = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se corrige Anexo B, numeral 4.2 con fecha 2026-09-08.",
            ),
            providers=(_StubProvider(supports=True, payload=payload_no_effects_with_items),),
        )
        assert result_no_effects_with_items.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    finally:
        db.close()


def test_unsupported_provider_returns_unsupported() -> None:
    payload = SourceEffectProviderDiscoveryPayload(status="UNSUPPORTED", effects=())
    fragment = SourceEffectSemanticFragment(
        tender_id="t-1",
        acting_document_id="d-1",
        document_page_id="p-1",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="native-page:p-1",
        source_locator="page:1",
        source_text="texto",
    )

    db = SessionLocal()
    try:
        result = discover_source_effect_semantics(db, fragment, providers=(_StubProvider(supports=False, payload=payload),))
        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED
    finally:
        db.close()


def test_no_effects_status_passthrough() -> None:
    payload = SourceEffectProviderDiscoveryPayload(status="NO_EFFECTS", effects=())
    fragment = SourceEffectSemanticFragment(
        tender_id="t-1",
        acting_document_id="d-1",
        document_page_id="p-1",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="native-page:p-1",
        source_locator="page:1",
        source_text="sin efectos",
    )

    db = SessionLocal()
    try:
        result = discover_source_effect_semantics(db, fragment, providers=(_StubProvider(supports=True, payload=payload),))
        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS
        assert result.candidate_count == 0
    finally:
        db.close()
