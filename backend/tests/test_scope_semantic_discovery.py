from __future__ import annotations

from dataclasses import fields

import pytest

from app.scope_details import (
    SCOPE_DETAIL_APPLICABILITY_ITEM,
    SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
    SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
)
from app.scope_semantic_discovery import (
    SCOPE_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    DiscoveredScopeObligation,
    ScopeSemanticDiscoveryProvider,
    ScopeSemanticSourceFragment,
    discover_scope_semantics,
    map_discovered_obligation_to_scope_detail_candidate,
)


class _StubProvider:
    provider_name = "Stub Semantic Provider"
    provider_version = "stub-001"
    contract_version = SCOPE_SEMANTIC_DISCOVERY_CONTRACT_VERSION

    def __init__(self, *, supported_methods: tuple[str, ...] = ("NATIVE", "OCR", "VISION"), candidates=None):
        self.supported_methods = supported_methods
        self.candidates = tuple(candidates or ())

    def supports(self, fragment: ScopeSemanticSourceFragment) -> bool:
        return fragment.source_method in self.supported_methods

    def discover(self, fragment: ScopeSemanticSourceFragment):
        return self.candidates


def _fragment(*, source_method: str = "NATIVE", source_text: str = "EL PROVEEDOR ENTREGARA REPORTE FINAL.") -> ScopeSemanticSourceFragment:
    return ScopeSemanticSourceFragment(
        tender_id="tender-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=1,
        source_method=source_method,
        source_artifact_key="artifact-1",
        source_locator="page:1|block:1",
        source_text=source_text,
        source_contract_version="contract-1",
    )


def test_multi_domain_same_evidence_survives_validation() -> None:
    fragment = _fragment(
        source_text="EL PROVEEDOR DEBE CONTAR CON EL EQUIPO DE COMPUTO Y SOFTWARE NECESARIO PARA LA EJECUCION DE LOS SERVICIOS, INCLUYENDO LOS MEDIOS DE TRANSPORTE Y COMUNICACION CON RADIOS A PRUEBA DE EXPLOSION."
    )
    evidence = "INCLUYENDO LOS MEDIOS DE TRANSPORTE Y COMUNICACION CON RADIOS A PRUEBA DE EXPLOSION"
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="TOOLS_EQUIPMENT",
                description="Proveer equipo de computo y software para ejecutar los servicios",
                evidence_excerpt=evidence,
                review_required=False,
            ),
            DiscoveredScopeObligation(
                domain="TOOLS_EQUIPMENT",
                description="Proveer radios a prueba de explosion para comunicacion",
                evidence_excerpt=evidence,
                review_required=False,
            ),
            DiscoveredScopeObligation(
                domain="LOGISTICS_SITE",
                description="Proveer medios de transporte para ejecutar los servicios",
                evidence_excerpt=evidence,
                review_required=False,
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 3
    assert [candidate.domain for candidate in result.candidates] == [
        "TOOLS_EQUIPMENT",
        "TOOLS_EQUIPMENT",
        "LOGISTICS_SITE",
    ]


def test_exact_duplicate_semantic_candidate_is_collapsed() -> None:
    fragment = _fragment(source_text="SUMINISTRAR 4 PIEZAS DE BATERIA")
    duplicate = DiscoveredScopeObligation(
        domain="SUPPLY",
        description="Suministrar baterias",
        evidence_excerpt="SUMINISTRAR 4 PIEZAS DE BATERIA",
        review_required=False,
        quantity_raw="4",
        unit_raw="PIEZAS",
    )
    provider = _StubProvider(candidates=(duplicate, duplicate))

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1


def test_evidence_hallucination_fails_validation() -> None:
    fragment = _fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL.")
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="SUPPLY",
                description="Suministrar dos bombas",
                evidence_excerpt="DEBERA SUMINISTRAR DOS BOMBAS",
                review_required=False,
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.candidate_count == 0
    assert result.candidates == ()
    assert any("evidence_excerpt is not supported by source_text" in error for error in result.errors)


def test_zero_obligation_returns_no_obligations() -> None:
    fragment = _fragment(source_text="INDICE GENERAL")
    provider = _StubProvider(candidates=())

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS
    assert result.candidate_count == 0
    assert result.candidates == ()


def test_invalid_domain_fails_validation() -> None:
    fragment = _fragment(source_text="PRESENTAR DOCUMENTACION ADMINISTRATIVA")
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="ADMINISTRATIVE",
                description="Presentar documentacion administrativa",
                evidence_excerpt="PRESENTAR DOCUMENTACION ADMINISTRATIVA",
                review_required=True,
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("Unsupported semantic domain: ADMINISTRATIVE" in error for error in result.errors)


def test_quantity_and_unit_raw_are_preserved_exactly() -> None:
    fragment = _fragment(source_text="SUMINISTRAR 4 PIEZAS DE BATERIA")
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="SUPPLY",
                description="Suministrar baterias",
                evidence_excerpt="SUMINISTRAR 4 PIEZAS DE BATERIA",
                review_required=False,
                quantity_raw="4",
                unit_raw="PIEZAS",
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.candidate_count == 1
    candidate = result.candidates[0]
    assert candidate.quantity_raw == "4"
    assert candidate.unit_raw == "PIEZAS"


def test_mapping_preserves_ownership_boundary_without_invented_ids() -> None:
    fragment = _fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL.")
    obligation = DiscoveredScopeObligation(
        domain="DELIVERABLE",
        description="Entregar reporte final",
        evidence_excerpt="EL PROVEEDOR ENTREGARA REPORTE FINAL.",
        review_required=True,
    )

    candidate = map_discovered_obligation_to_scope_detail_candidate(fragment, obligation)

    assert candidate.applicability == SCOPE_DETAIL_APPLICABILITY_UNRESOLVED
    assert candidate.scope_segment_id is None
    assert candidate.tender_item_id is None
    assert candidate.candidate_item_key is None
    assert candidate.review_required is True


def test_mapping_rejects_unresolved_non_review_candidate() -> None:
    fragment = _fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL.")
    obligation = DiscoveredScopeObligation(
        domain="DELIVERABLE",
        description="Entregar reporte final",
        evidence_excerpt="EL PROVEEDOR ENTREGARA REPORTE FINAL.",
        review_required=False,
    )

    with pytest.raises(ValueError, match="Cannot map ownership-neutral obligation"):
        map_discovered_obligation_to_scope_detail_candidate(fragment, obligation)


def test_mapping_with_explicit_candidate_item_key_maps_to_item() -> None:
    fragment = _fragment(source_text="PARTIDA 4 SUMINISTRAR BATERIA")
    obligation = DiscoveredScopeObligation(
        domain="SUPPLY",
        description="Suministrar bateria",
        evidence_excerpt="PARTIDA 4 SUMINISTRAR BATERIA",
        review_required=False,
        candidate_item_key="4",
    )

    candidate = map_discovered_obligation_to_scope_detail_candidate(fragment, obligation)

    assert candidate.applicability == SCOPE_DETAIL_APPLICABILITY_ITEM
    assert candidate.candidate_item_key == "4"
    assert candidate.scope_segment_id is None
    assert candidate.tender_item_id is None


def test_mapping_allows_explicit_tender_wide_applicability() -> None:
    fragment = _fragment(source_text="EL CONTRATISTA DEBE PRESENTAR BITACORA DIARIA DURANTE TODA LA EJECUCION")
    obligation = DiscoveredScopeObligation(
        domain="DELIVERABLE",
        description="Mantener bitacora diaria durante la ejecucion",
        evidence_excerpt="EL CONTRATISTA DEBE PRESENTAR BITACORA DIARIA DURANTE TODA LA EJECUCION",
        review_required=False,
        applicability_hint="TENDER_WIDE",
    )

    candidate = map_discovered_obligation_to_scope_detail_candidate(fragment, obligation)

    assert candidate.applicability == SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE


def test_document_classification_is_not_part_of_semantic_contract() -> None:
    field_names = {field.name for field in fields(ScopeSemanticSourceFragment)}

    assert "document_type" not in field_names
    assert "human_type" not in field_names
    assert "classification" not in field_names


def test_semantic_review_candidate_remains_valid() -> None:
    fragment = _fragment(source_text="EL PROVEEDOR DEBE PROPORCIONAR RADIOS DE COMUNICACION")
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="TOOLS_EQUIPMENT",
                description="Proporcionar radios de comunicacion",
                evidence_excerpt="EL PROVEEDOR DEBE PROPORCIONAR RADIOS DE COMUNICACION",
                review_required=True,
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
    assert result.candidate_count == 1
    assert result.review_required_count == 1
    assert result.candidates[0].review_required is True


def test_unsupported_when_no_provider_accepts_fragment() -> None:
    fragment = _fragment(source_method="FUTURE_SOURCE")
    provider = _StubProvider(supported_methods=("VISION",), candidates=())

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED
    assert result.provider_name is None
    assert result.candidate_count == 0


def test_item_applicability_hint_requires_candidate_item_key() -> None:
    fragment = _fragment(source_text="PARTIDA SIN CLAVE EXPLICITA")
    provider = _StubProvider(
        candidates=(
            DiscoveredScopeObligation(
                domain="SUPPLY",
                description="Suministrar material",
                evidence_excerpt="PARTIDA SIN CLAVE EXPLICITA",
                review_required=True,
                applicability_hint="ITEM",
            ),
        )
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("ITEM applicability hint requires candidate_item_key" in error for error in result.errors)