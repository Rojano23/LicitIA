from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol, Sequence

from app.scope_quantities import (
    SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS,
    SCOPE_QUANTITY_ALLOWED_RELATIONS,
    SCOPE_QUANTITY_ALLOWED_SOURCE_METHODS,
    SCOPE_QUANTITY_RELATION_APPROXIMATE,
    SCOPE_QUANTITY_RELATION_EXACT,
    SCOPE_QUANTITY_RELATION_MAXIMUM,
    SCOPE_QUANTITY_RELATION_MINIMUM,
    SCOPE_QUANTITY_RELATION_RANGE,
    SCOPE_QUANTITY_RELATION_UNSPECIFIED,
    ScopeQuantityCandidate,
    compute_scope_quantity_fingerprint,
)

SCOPE_QUANTITY_SEMANTIC_DISCOVERY_CONTRACT_VERSION = "scope-quantity-semantic-discovery-2026-09-08-003"

SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED = "DISCOVERED"
SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES = "NO_QUANTITIES"
SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"

_ALLOWED_DISCOVERY_STATUSES = {
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
}

_DECIMAL_GRAMMAR = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class ScopeQuantitySemanticFragment:
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    scope_detail_domain: str
    scope_detail_description: str
    source_text: str
    source_contract_version: Optional[str] = None
    source_analysis_id: Optional[str] = None
    source_page_result_id: Optional[str] = None
    scope_detail_review_required: Optional[bool] = None


@dataclass(frozen=True)
class DiscoveredScopeQuantity:
    quantity_raw: str
    evidence_excerpt: str
    unit_raw: Optional[str] = None
    measure_kind: Optional[str] = None
    relation: Optional[str] = None
    quantity_value_raw: Optional[str] = None
    quantity_min_raw: Optional[str] = None
    quantity_max_raw: Optional[str] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class ScopeQuantityProviderDiscoveryPayload:
    status: str
    quantities: tuple[DiscoveredScopeQuantity, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopeQuantitySemanticDiscoveryResult:
    provider_name: Optional[str]
    provider_version: Optional[str]
    contract_version: Optional[str]
    status: str
    candidate_count: int
    review_required_count: int
    candidates: tuple[ScopeQuantityCandidate, ...]
    discovered_quantities: tuple[DiscoveredScopeQuantity, ...]
    errors: tuple[str, ...] = ()


class ScopeQuantitySemanticDiscoveryProvider(Protocol):
    provider_name: str
    provider_version: str
    contract_version: str

    def supports(self, fragment: ScopeQuantitySemanticFragment) -> bool:
        ...

    def discover(self, fragment: ScopeQuantitySemanticFragment) -> ScopeQuantityProviderDiscoveryPayload:
        ...


def discover_scope_quantities(
    fragment: ScopeQuantitySemanticFragment,
    *,
    providers: Sequence[ScopeQuantitySemanticDiscoveryProvider],
) -> ScopeQuantitySemanticDiscoveryResult:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
            errors=fragment_errors,
        )

    selected_provider: Optional[ScopeQuantitySemanticDiscoveryProvider] = None
    for provider in providers:
        if provider.supports(fragment):
            selected_provider = provider
            break

    if selected_provider is None:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
        )

    try:
        provider_payload = selected_provider.discover(fragment)
    except Exception as exc:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
            errors=(str(exc),),
        )

    try:
        normalized_payload = _normalize_provider_payload(provider_payload)
        _validate_provider_payload_contract(normalized_payload)
    except ValueError as exc:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
            errors=(str(exc),),
        )

    status = normalized_payload.status
    if status in {
        SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
        SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
        SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    }:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=status,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
            errors=normalized_payload.errors,
        )

    if status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
            errors=normalized_payload.errors or ("Provider reported INVALID_OUTPUT",),
        )

    mapped_candidates: list[ScopeQuantityCandidate] = []
    discovered_quantities: list[DiscoveredScopeQuantity] = []
    semantic_fingerprints: set[str] = set()

    for discovered in normalized_payload.quantities:
        try:
            normalized_discovered = _normalize_discovered_quantity(discovered)
            _validate_discovered_quantity(fragment, normalized_discovered)
            mapped = map_discovered_scope_quantity_to_candidate(fragment, normalized_discovered)
        except ValueError as exc:
            return ScopeQuantitySemanticDiscoveryResult(
                provider_name=selected_provider.provider_name,
                provider_version=selected_provider.provider_version,
                contract_version=selected_provider.contract_version,
                status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                candidate_count=0,
                review_required_count=0,
                candidates=(),
                discovered_quantities=(),
                errors=(str(exc),),
            )

        fingerprint = compute_scope_quantity_fingerprint(mapped)
        if fingerprint in semantic_fingerprints:
            continue

        semantic_fingerprints.add(fingerprint)
        mapped_candidates.append(mapped)
        discovered_quantities.append(normalized_discovered)

    if not mapped_candidates:
        return ScopeQuantitySemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_quantities=(),
        )

    review_required_count = sum(1 for row in mapped_candidates if row.review_required)
    return ScopeQuantitySemanticDiscoveryResult(
        provider_name=selected_provider.provider_name,
        provider_version=selected_provider.provider_version,
        contract_version=selected_provider.contract_version,
        status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidate_count=len(mapped_candidates),
        review_required_count=review_required_count,
        candidates=tuple(mapped_candidates),
        discovered_quantities=tuple(discovered_quantities),
        errors=normalized_payload.errors,
    )


def map_discovered_scope_quantity_to_candidate(
    fragment: ScopeQuantitySemanticFragment,
    discovered: DiscoveredScopeQuantity,
) -> ScopeQuantityCandidate:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        raise ValueError("; ".join(fragment_errors))

    normalized = _normalize_discovered_quantity(discovered)
    _validate_discovered_quantity(fragment, normalized)

    relation = normalized.relation or SCOPE_QUANTITY_RELATION_UNSPECIFIED

    return ScopeQuantityCandidate(
        tender_id=fragment.tender_id,
        scope_detail_id=fragment.scope_detail_id,
        source_document_id=fragment.source_document_id,
        document_page_id=fragment.document_page_id,
        quantity_raw=normalized.quantity_raw,
        quantity_value=_decimal_or_none(normalized.quantity_value_raw),
        quantity_min=_decimal_or_none(normalized.quantity_min_raw),
        quantity_max=_decimal_or_none(normalized.quantity_max_raw),
        unit_raw=normalized.unit_raw,
        measure_kind=normalized.measure_kind,
        relation=relation,
        source_method=fragment.source_method,
        source_artifact_key=fragment.source_artifact_key,
        source_locator=fragment.source_locator,
        source_excerpt=normalized.evidence_excerpt,
        review_required=True,
        confidence=normalized.confidence,
        source_contract_version=fragment.source_contract_version,
        source_analysis_id=fragment.source_analysis_id,
        source_page_result_id=fragment.source_page_result_id,
    )


def _validate_fragment(fragment: ScopeQuantitySemanticFragment) -> tuple[str, ...]:
    errors: list[str] = []

    for field_name, value in (
        ("tender_id", fragment.tender_id),
        ("scope_detail_id", fragment.scope_detail_id),
        ("source_document_id", fragment.source_document_id),
        ("document_page_id", fragment.document_page_id),
        ("source_method", fragment.source_method),
        ("source_artifact_key", fragment.source_artifact_key),
        ("source_locator", fragment.source_locator),
        ("scope_detail_domain", fragment.scope_detail_domain),
        ("scope_detail_description", fragment.scope_detail_description),
        ("source_text", fragment.source_text),
    ):
        if not _optional_text(value):
            errors.append(f"{field_name} is required")

    try:
        if int(fragment.page_number) <= 0:
            errors.append("page_number must be greater than zero")
    except (TypeError, ValueError):
        errors.append("page_number must be greater than zero")

    if fragment.source_method not in SCOPE_QUANTITY_ALLOWED_SOURCE_METHODS:
        errors.append(f"Unsupported source_method: {fragment.source_method}")

    if fragment.source_analysis_id is not None and not _optional_text(fragment.source_analysis_id):
        errors.append("source_analysis_id is required when provided")
    if fragment.source_page_result_id is not None and not _optional_text(fragment.source_page_result_id):
        errors.append("source_page_result_id is required when provided")

    return tuple(errors)


def _normalize_provider_payload(payload: ScopeQuantityProviderDiscoveryPayload) -> ScopeQuantityProviderDiscoveryPayload:
    status = _required_text(payload.status, field_name="status").upper().replace("-", "_").replace(" ", "_")
    return ScopeQuantityProviderDiscoveryPayload(
        status=status,
        quantities=tuple(payload.quantities),
        errors=tuple(_optional_text(error) or "" for error in payload.errors if _optional_text(error) is not None),
    )


def _validate_provider_payload_contract(payload: ScopeQuantityProviderDiscoveryPayload) -> None:
    if payload.status not in _ALLOWED_DISCOVERY_STATUSES:
        raise ValueError(f"Unsupported discovery status: {payload.status}")

    if payload.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED and not payload.quantities:
        raise ValueError("DISCOVERED status requires at least one quantity")

    if payload.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES and payload.quantities:
        raise ValueError("NO_QUANTITIES status cannot include quantities")

    if payload.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED and payload.quantities:
        raise ValueError("REVIEW_REQUIRED status cannot include quantities")

    if payload.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED and payload.quantities:
        raise ValueError("UNSUPPORTED status cannot include quantities")

    if payload.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT and payload.quantities:
        raise ValueError("INVALID_OUTPUT status cannot include quantities")


def _validate_discovered_quantity(fragment: ScopeQuantitySemanticFragment, discovered: DiscoveredScopeQuantity) -> None:
    _required_text(discovered.quantity_raw, field_name="quantity_raw")
    _required_text(discovered.evidence_excerpt, field_name="evidence_excerpt")

    if discovered.measure_kind is None:
        raise ValueError("measure_kind is required")
    if discovered.measure_kind not in SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS:
        raise ValueError(f"Unsupported measure_kind: {discovered.measure_kind}")

    relation = discovered.relation or SCOPE_QUANTITY_RELATION_UNSPECIFIED
    if relation not in SCOPE_QUANTITY_ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {relation}")

    if discovered.confidence is not None and not (0.0 <= discovered.confidence <= 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")

    if not _is_grounded(fragment.source_text, discovered.evidence_excerpt):
        raise ValueError("evidence_excerpt is not supported by source_text")

    if not _is_grounded(discovered.evidence_excerpt, discovered.quantity_raw):
        raise ValueError("quantity_raw is not grounded in evidence_excerpt")

    if discovered.unit_raw is not None and not _is_grounded(discovered.evidence_excerpt, discovered.unit_raw):
        raise ValueError("unit_raw is not grounded in evidence_excerpt")

    value = _decimal_or_none(discovered.quantity_value_raw, field_name="quantity_value_raw")
    min_value = _decimal_or_none(discovered.quantity_min_raw, field_name="quantity_min_raw")
    max_value = _decimal_or_none(discovered.quantity_max_raw, field_name="quantity_max_raw")

    if relation == SCOPE_QUANTITY_RELATION_EXACT:
        if value is None:
            raise ValueError("EXACT relation requires quantity_value_raw")
        if min_value is not None or max_value is not None:
            raise ValueError("EXACT relation does not allow quantity_min_raw/quantity_max_raw")
    elif relation == SCOPE_QUANTITY_RELATION_MINIMUM:
        if min_value is None:
            raise ValueError("MINIMUM relation requires quantity_min_raw")
    elif relation == SCOPE_QUANTITY_RELATION_MAXIMUM:
        if max_value is None:
            raise ValueError("MAXIMUM relation requires quantity_max_raw")
    elif relation == SCOPE_QUANTITY_RELATION_RANGE:
        if min_value is None or max_value is None:
            raise ValueError("RANGE relation requires quantity_min_raw and quantity_max_raw")
        if min_value > max_value:
            raise ValueError("quantity_min_raw cannot be greater than quantity_max_raw")
        if value is not None:
            raise ValueError("RANGE relation does not allow quantity_value_raw")
    elif relation == SCOPE_QUANTITY_RELATION_APPROXIMATE:
        if value is None:
            raise ValueError("APPROXIMATE relation requires quantity_value_raw")
    elif relation == SCOPE_QUANTITY_RELATION_UNSPECIFIED:
        if value is None and min_value is None and max_value is None:
            raise ValueError("UNSPECIFIED relation requires at least one numeric field")


def _normalize_discovered_quantity(discovered: DiscoveredScopeQuantity) -> DiscoveredScopeQuantity:
    quantity_raw = _required_text(discovered.quantity_raw, field_name="quantity_raw")
    evidence_excerpt = _required_text(discovered.evidence_excerpt, field_name="evidence_excerpt")
    measure_kind = _optional_text(discovered.measure_kind)
    if measure_kind is not None:
        measure_kind = measure_kind.upper().replace("-", "_").replace(" ", "_")

    relation = _optional_text(discovered.relation)
    if relation is None:
        relation = SCOPE_QUANTITY_RELATION_UNSPECIFIED
    relation = relation.upper().replace("-", "_").replace(" ", "_")

    return DiscoveredScopeQuantity(
        quantity_raw=quantity_raw,
        evidence_excerpt=evidence_excerpt,
        unit_raw=_optional_text(discovered.unit_raw),
        measure_kind=measure_kind,
        relation=relation,
        quantity_value_raw=_optional_text(discovered.quantity_value_raw),
        quantity_min_raw=_optional_text(discovered.quantity_min_raw),
        quantity_max_raw=_optional_text(discovered.quantity_max_raw),
        confidence=discovered.confidence,
    )


def _decimal_or_none(value: Optional[str], *, field_name: str = "numeric") -> Optional[Decimal]:
    text = _optional_text(value)
    if text is None:
        return None
    if _DECIMAL_GRAMMAR.fullmatch(text) is None:
        raise ValueError(f"{field_name} has invalid decimal normalization")
    return Decimal(text)


def _is_grounded(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()


def _required_text(value: Optional[str], *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
