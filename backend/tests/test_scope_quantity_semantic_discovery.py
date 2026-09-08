from __future__ import annotations

import inspect

import pytest

from app.scope_quantity_semantic_discovery import (
    DiscoveredScopeQuantity,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    ScopeQuantityProviderDiscoveryPayload,
    ScopeQuantitySemanticFragment,
    discover_scope_quantities,
    map_discovered_scope_quantity_to_candidate,
)


class _StubProvider:
    provider_name = "Stub Quantity Provider"
    provider_version = "stub-001"
    contract_version = "stub-contract-001"

    def __init__(self, *, supports: bool, payload: ScopeQuantityProviderDiscoveryPayload) -> None:
        self._supports = supports
        self._payload = payload

    def supports(self, fragment: ScopeQuantitySemanticFragment) -> bool:
        return self._supports

    def discover(self, fragment: ScopeQuantitySemanticFragment) -> ScopeQuantityProviderDiscoveryPayload:
        return self._payload


def _fragment(*, source_text: str, source_method: str = "VISION") -> ScopeQuantitySemanticFragment:
    return ScopeQuantitySemanticFragment(
        tender_id="tender-1",
        scope_detail_id="scope-detail-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=1,
        source_method=source_method,
        source_artifact_key="vision-page-result:pr-1",
        source_locator="page:1|detail_row:0",
        scope_detail_domain="SUPPLY",
        scope_detail_description="Suministro de material.",
        source_text=source_text,
        source_contract_version="vision-detail-transcription-2026-08-31-001",
        source_analysis_id="analysis-1",
        source_page_result_id="pr-1",
        scope_detail_review_required=False,
    )


def _discovered(
    *,
    quantity_raw: str,
    evidence_excerpt: str,
    unit_raw: str,
    measure_kind: str,
    relation: str,
    quantity_value_raw: str | None = None,
    quantity_min_raw: str | None = None,
    quantity_max_raw: str | None = None,
    confidence: float | None = 0.9,
) -> DiscoveredScopeQuantity:
    return DiscoveredScopeQuantity(
        quantity_raw=quantity_raw,
        evidence_excerpt=evidence_excerpt,
        unit_raw=unit_raw,
        measure_kind=measure_kind,
        relation=relation,
        quantity_value_raw=quantity_value_raw,
        quantity_min_raw=quantity_min_raw,
        quantity_max_raw=quantity_max_raw,
        confidence=confidence,
    )


def test_positive_A_personnel_exact_numeric() -> None:
    text = "se requieren 3 técnicos"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="se requieren 3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))

    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1
    assert result.candidates[0].measure_kind == "PERSONNEL"
    assert result.candidates[0].review_required is True


def test_positive_B_personnel_exact_word_number() -> None:
    text = "se requieren tres técnicos"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="tres",
                evidence_excerpt="se requieren tres técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )

    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))

    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    candidate = result.candidates[0]
    assert candidate.quantity_raw == "tres"
    assert str(candidate.quantity_value) == "3"
    assert candidate.review_required is True


def test_positive_C_duration_exact() -> None:
    text = "los trabajos tendrán una duración de 5 días"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="5",
                evidence_excerpt="duración de 5 días",
                unit_raw="días",
                measure_kind="DURATION",
                relation="EXACT",
                quantity_value_raw="5",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidates[0].measure_kind == "DURATION"


def test_positive_D_length_exact() -> None:
    text = "se suministrarán 500 metros de cable"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="500",
                evidence_excerpt="500 metros de cable",
                unit_raw="metros",
                measure_kind="LENGTH",
                relation="EXACT",
                quantity_value_raw="500",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].measure_kind == "LENGTH"


def test_positive_E_service_exact() -> None:
    text = "se realizarán 2 servicios"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="2",
                evidence_excerpt="2 servicios",
                unit_raw="servicios",
                measure_kind="SERVICE",
                relation="EXACT",
                quantity_value_raw="2",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].measure_kind == "SERVICE"


def test_positive_F_count_exact() -> None:
    text = "se suministrarán 4 equipos"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="4",
                evidence_excerpt="4 equipos",
                unit_raw="equipos",
                measure_kind="COUNT",
                relation="EXACT",
                quantity_value_raw="4",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].measure_kind == "COUNT"


def test_positive_G_minimum() -> None:
    text = "se requieren al menos 3 especialistas"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="al menos 3",
                evidence_excerpt="al menos 3 especialistas",
                unit_raw="especialistas",
                measure_kind="PERSONNEL",
                relation="MINIMUM",
                quantity_min_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].relation == "MINIMUM"
    assert str(result.candidates[0].quantity_min) == "3"


def test_positive_H_maximum() -> None:
    text = "máximo 5 personas"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="máximo 5",
                evidence_excerpt="máximo 5 personas",
                unit_raw="personas",
                measure_kind="PERSONNEL",
                relation="MAXIMUM",
                quantity_max_raw="5",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].relation == "MAXIMUM"
    assert str(result.candidates[0].quantity_max) == "5"


def test_positive_I_range() -> None:
    text = "entre 2 y 4 técnicos"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="entre 2 y 4",
                evidence_excerpt="entre 2 y 4 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="RANGE",
                quantity_min_raw="2",
                quantity_max_raw="4",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].relation == "RANGE"


def test_positive_J_approximate() -> None:
    text = "aproximadamente 100 metros"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="aproximadamente 100",
                evidence_excerpt="aproximadamente 100 metros",
                unit_raw="metros",
                measure_kind="LENGTH",
                relation="APPROXIMATE",
                quantity_value_raw="100",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].relation == "APPROXIMATE"


def test_positive_K_multiple_quantities() -> None:
    text = "3 técnicos durante 5 días"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
            _discovered(
                quantity_raw="5",
                evidence_excerpt="5 días",
                unit_raw="días",
                measure_kind="DURATION",
                relation="EXACT",
                quantity_value_raw="5",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidate_count == 2


def test_positive_L_deliverable_count() -> None:
    text = "entregar 2 copias impresas del reporte"
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="2",
                evidence_excerpt="2 copias impresas",
                unit_raw="copias",
                measure_kind="COUNT",
                relation="EXACT",
                quantity_value_raw="2",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidates[0].measure_kind == "COUNT"


@pytest.mark.parametrize(
    "token",
    [
        "24 VDC",
        "100-120 VCA",
        "4-20 mA",
        "±0.075 %",
        "Class 300",
        "ANSI 150",
        "IP66",
        "model 3051",
        "AA143-H50/K4400",
        "EC401-50",
        "2026",
        "3/4 inch",
        "2 pulgadas nominales",
        "50 Hz",
        "10 bar",
        "150 °C",
        "5 años de experiencia",
        "Nivel III",
        "API 6D",
        "IEC 61508",
        "$25,000",
        "IVA 16%",
        "anticipo 30%",
    ],
)
def test_negative_tokens_are_no_quantities(token: str) -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(status="NO_QUANTITIES", quantities=())
    result = discover_scope_quantities(
        _fragment(source_text=token),
        providers=(_StubProvider(supports=True, payload=payload),),
    )
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES


def test_mixed_context_valves_extracts_only_execution_count() -> None:
    text = "Se suministrarán 2 válvulas de 4 pulgadas, clase 300."
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="2",
                evidence_excerpt="2 válvulas",
                unit_raw="válvulas",
                measure_kind="COUNT",
                relation="EXACT",
                quantity_value_raw="2",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidate_count == 1
    assert result.candidates[0].quantity_raw == "2"


def test_mixed_context_cable_extracts_only_length() -> None:
    text = "Instalar 500 m de cable de 5 mm."
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="500",
                evidence_excerpt="500 m de cable",
                unit_raw="m",
                measure_kind="LENGTH",
                relation="EXACT",
                quantity_value_raw="500",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=text), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.candidate_count == 1
    assert result.candidates[0].measure_kind == "LENGTH"


def test_source_method_invariant_preserves_native_ocr_vision() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    for method in ("NATIVE", "OCR", "VISION"):
        result = discover_scope_quantities(_fragment(source_text="3 técnicos", source_method=method), providers=(_StubProvider(supports=True, payload=payload),))
        assert result.candidates[0].source_method == method


def test_mapping_preserves_trusted_provenance_and_forces_review_required() -> None:
    fragment = _fragment(source_text="se requieren 3 técnicos", source_method="OCR")
    discovered = _discovered(
        quantity_raw="3",
        evidence_excerpt="3 técnicos",
        unit_raw="técnicos",
        measure_kind="PERSONNEL",
        relation="EXACT",
        quantity_value_raw="3",
        confidence=1.0,
    )

    candidate = map_discovered_scope_quantity_to_candidate(fragment, discovered)

    assert candidate.tender_id == fragment.tender_id
    assert candidate.scope_detail_id == fragment.scope_detail_id
    assert candidate.source_document_id == fragment.source_document_id
    assert candidate.document_page_id == fragment.document_page_id
    assert candidate.source_artifact_key == fragment.source_artifact_key
    assert candidate.source_locator == fragment.source_locator
    assert candidate.source_method == "OCR"
    assert candidate.source_analysis_id == fragment.source_analysis_id
    assert candidate.source_page_result_id == fragment.source_page_result_id
    assert candidate.review_required is True


def test_discovery_without_provider_returns_unsupported() -> None:
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=())
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED


def test_unknown_status_is_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(status="MAYBE", quantities=())
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_discovered_with_zero_quantities_is_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(status="DISCOVERED", quantities=())
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_no_quantities_with_payload_is_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="NO_QUANTITIES",
        quantities=(
            _discovered(
                quantity_raw="1",
                evidence_excerpt="1 pieza",
                unit_raw="pieza",
                measure_kind="COUNT",
                relation="EXACT",
                quantity_value_raw="1",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="1 pieza"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unknown_measure_kind_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="1",
                evidence_excerpt="1 cosa",
                unit_raw="cosa",
                measure_kind="UNIVERSE",
                relation="EXACT",
                quantity_value_raw="1",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="1 cosa"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unknown_relation_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="1",
                evidence_excerpt="1 pieza",
                unit_raw="pieza",
                measure_kind="COUNT",
                relation="ABOUT",
                quantity_value_raw="1",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="1 pieza"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_range_missing_bounds_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="entre 2 y 4",
                evidence_excerpt="entre 2 y 4 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="RANGE",
                quantity_min_raw="2",
                quantity_max_raw=None,
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="entre 2 y 4 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_range_min_greater_than_max_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="entre 4 y 2",
                evidence_excerpt="entre 4 y 2 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="RANGE",
                quantity_min_raw="4",
                quantity_max_raw="2",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="entre 4 y 2 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_exact_missing_scalar_invalid_output() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw=None,
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


@pytest.mark.parametrize("raw", ["1,250", "2,5", "1.2.3", "~10", "2-4"])
def test_invalid_numeric_normalization_rejected(raw: str) -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="texto",
                evidence_excerpt=f"texto {raw} técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw=raw,
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text=f"texto {raw} técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_confidence_out_of_range_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="1",
                evidence_excerpt="1 pieza",
                unit_raw="pieza",
                measure_kind="COUNT",
                relation="EXACT",
                quantity_value_raw="1",
                confidence=1.1,
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="1 pieza"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_empty_quantity_raw_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw=" ",
                evidence_excerpt="3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_empty_evidence_excerpt_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt=" ",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_ungrounded_evidence_excerpt_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="5 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_ungrounded_quantity_raw_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="4",
                evidence_excerpt="3 técnicos",
                unit_raw="técnicos",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="4",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_ungrounded_unit_raw_rejected() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(
        status="DISCOVERED",
        quantities=(
            _discovered(
                quantity_raw="3",
                evidence_excerpt="3 técnicos",
                unit_raw="personas",
                measure_kind="PERSONNEL",
                relation="EXACT",
                quantity_value_raw="3",
            ),
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_semantic_duplicate_quantities_are_deduplicated() -> None:
    q = _discovered(
        quantity_raw="3",
        evidence_excerpt="3 técnicos",
        unit_raw="técnicos",
        measure_kind="PERSONNEL",
        relation="EXACT",
        quantity_value_raw="3",
    )
    payload = ScopeQuantityProviderDiscoveryPayload(status="DISCOVERED", quantities=(q, q))
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1


def test_review_required_status_with_empty_quantities_passes() -> None:
    payload = ScopeQuantityProviderDiscoveryPayload(status="REVIEW_REQUIRED", quantities=())
    result = discover_scope_quantities(_fragment(source_text="a más tardar en 5 días"), providers=(_StubProvider(supports=True, payload=payload),))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
    assert result.candidate_count == 0


def test_module_has_no_db_or_persistence_dependencies() -> None:
    import app.scope_quantity_semantic_discovery as module

    source = inspect.getsource(module)
    assert "replace_scope_quantities_for_artifact" not in source
    assert "materialize_scope_quantities_for_scope_detail" not in source
    assert "Session" not in source

    signature = inspect.signature(discover_scope_quantities)
    assert "db" not in signature.parameters
