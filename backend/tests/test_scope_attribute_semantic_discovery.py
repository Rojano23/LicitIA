from __future__ import annotations

from app.scope_attribute_semantic_discovery import (
    DiscoveredScopeAttribute,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    ScopeAttributeSemanticFragment,
    discover_scope_attributes,
    map_discovered_scope_attribute_to_candidate,
)


class _StubProvider:
    provider_name = "Stub Attribute Provider"
    provider_version = "stub-001"
    contract_version = "stub-contract-001"

    def __init__(self, *, supports: bool, attributes: tuple[DiscoveredScopeAttribute, ...] = ()) -> None:
        self._supports = supports
        self._attributes = attributes

    def supports(self, fragment: ScopeAttributeSemanticFragment) -> bool:
        return self._supports

    def discover(self, fragment: ScopeAttributeSemanticFragment):
        return self._attributes


def _fragment(*, source_text: str, page_number: int = 1, source_method: str = "VISION") -> ScopeAttributeSemanticFragment:
    return ScopeAttributeSemanticFragment(
        tender_id="tender-1",
        scope_detail_id="scope-detail-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=page_number,
        source_method=source_method,
        source_artifact_key="scope-detail-1:vision",
        source_locator="page:1|block:2",
        scope_detail_domain="TECHNICAL",
        scope_detail_description="The supplier shall provide a pump set.",
        source_text=source_text,
        source_contract_version="scope-detail-v1",
    )


def test_valid_fragment_is_accepted_and_review_required_is_forced() -> None:
    discovered = DiscoveredScopeAttribute(
        attribute_name="brand",
        value_raw="Acme",
        evidence_excerpt="MARCA ACME",
        attribute_label_raw="MARCA",
        unit_raw=None,
        relation="UNSPECIFIED",
        confidence=0.93,
    )
    provider = _StubProvider(supports=True, attributes=(discovered,))

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1
    assert result.review_required_count == 1
    candidate = result.candidates[0]
    assert candidate.attribute_name == "brand"
    assert candidate.value_raw == "Acme"
    assert candidate.relation == "UNSPECIFIED"

    mapped = map_discovered_scope_attribute_to_candidate(_fragment(source_text="MARCA ACME"), candidate)
    assert mapped.review_required is True
    assert mapped.normalized_name is None
    assert mapped.source_method == "VISION"


def test_empty_source_text_is_rejected() -> None:
    provider = _StubProvider(
        supports=True,
        attributes=(
            DiscoveredScopeAttribute(
                attribute_name="brand",
                value_raw="Acme",
                evidence_excerpt="MARCA ACME",
                relation="UNSPECIFIED",
            ),
        ),
    )

    result = discover_scope_attributes(_fragment(source_text="   "), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.candidate_count == 0
    assert any("source_text is required" in error for error in result.errors)


def test_zero_page_number_is_rejected() -> None:
    provider = _StubProvider(supports=True, attributes=())

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME", page_number=0), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("page_number must be greater than zero" in error for error in result.errors)


def test_exact_duplicate_candidates_collapse() -> None:
    discovered = DiscoveredScopeAttribute(
        attribute_name="model",
        value_raw="ZX-10",
        evidence_excerpt="MODELO ZX-10",
        attribute_label_raw="MODELO",
        unit_raw=None,
        relation="UNSPECIFIED",
        confidence=0.88,
    )
    provider = _StubProvider(supports=True, attributes=(discovered, discovered))

    result = discover_scope_attributes(_fragment(source_text="MODELO ZX-10"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1
    assert result.candidates[0].attribute_name == "model"


def test_unsupported_provider_returns_unsupported() -> None:
    provider = _StubProvider(supports=False)

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED
    assert result.candidate_count == 0
    assert result.review_required_count == 0


def test_no_attributes_returns_no_attributes() -> None:
    provider = _StubProvider(supports=True, attributes=())

    result = discover_scope_attributes(_fragment(source_text="SIN ATRIBUTOS TECNICOS"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES
    assert result.candidate_count == 0


def test_mapper_rejects_unbounded_attributes() -> None:
    discovered = DiscoveredScopeAttribute(
        attribute_name="brand",
        value_raw="Acme",
        evidence_excerpt="MARCA INVENTADA",
        relation="UNSPECIFIED",
    )

    try:
        map_discovered_scope_attribute_to_candidate(_fragment(source_text="MARCA ACME"), discovered)
    except ValueError as exc:
        assert "evidence_excerpt is not supported by source_text" in str(exc)
    else:
        raise AssertionError("expected ValueError")
