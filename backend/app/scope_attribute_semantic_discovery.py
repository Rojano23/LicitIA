from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from app.scope_attributes import (
    SCOPE_ATTRIBUTE_RELATION_EXACT,
    SCOPE_ATTRIBUTE_RELATION_MAXIMUM,
    SCOPE_ATTRIBUTE_RELATION_MINIMUM,
    SCOPE_ATTRIBUTE_RELATION_RANGE,
    SCOPE_ATTRIBUTE_RELATION_REFERENCE,
    SCOPE_ATTRIBUTE_RELATION_TOLERANCE,
    SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
    ScopeAttributeCandidate,
)

SCOPE_ATTRIBUTE_RELATION_EXACT = "EXACT"
SCOPE_ATTRIBUTE_RELATION_MINIMUM = "MINIMUM"
SCOPE_ATTRIBUTE_RELATION_MAXIMUM = "MAXIMUM"
SCOPE_ATTRIBUTE_RELATION_RANGE = "RANGE"
SCOPE_ATTRIBUTE_RELATION_TOLERANCE = "TOLERANCE"
SCOPE_ATTRIBUTE_RELATION_REFERENCE = "REFERENCE"
SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED = "UNSPECIFIED"

SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS = {"NATIVE", "OCR", "VISION"}

SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_CONTRACT_VERSION = "scope-attribute-semantic-discovery-2026-09-08-001"

SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED = "DISCOVERED"
SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES = "NO_ATTRIBUTES"
SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"

_ALLOWED_RELATIONS = {
    SCOPE_ATTRIBUTE_RELATION_EXACT,
    SCOPE_ATTRIBUTE_RELATION_MINIMUM,
    SCOPE_ATTRIBUTE_RELATION_MAXIMUM,
    SCOPE_ATTRIBUTE_RELATION_RANGE,
    SCOPE_ATTRIBUTE_RELATION_TOLERANCE,
    SCOPE_ATTRIBUTE_RELATION_REFERENCE,
    SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
}


@dataclass(frozen=True)
class ScopeAttributeSemanticFragment:
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


@dataclass(frozen=True)
class DiscoveredScopeAttribute:
    attribute_name: str
    value_raw: str
    evidence_excerpt: str
    attribute_label_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    relation: Optional[str] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class ScopeAttributeSemanticDiscoveryResult:
    provider_name: Optional[str]
    provider_version: Optional[str]
    contract_version: Optional[str]
    candidate_count: int
    review_required_count: int
    status: str
    candidates: tuple[DiscoveredScopeAttribute, ...]
    errors: tuple[str, ...] = ()


class ScopeAttributeSemanticDiscoveryProvider(Protocol):
    provider_name: str
    provider_version: str
    contract_version: str

    def supports(self, fragment: ScopeAttributeSemanticFragment) -> bool:
        ...

    def discover(self, fragment: ScopeAttributeSemanticFragment) -> Sequence[DiscoveredScopeAttribute]:
        ...


def discover_scope_attributes(
    fragment: ScopeAttributeSemanticFragment,
    *,
    providers: Sequence[ScopeAttributeSemanticDiscoveryProvider],
) -> ScopeAttributeSemanticDiscoveryResult:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        return ScopeAttributeSemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidates=(),
            errors=fragment_errors,
        )

    selected_provider: Optional[ScopeAttributeSemanticDiscoveryProvider] = None
    for provider in providers:
        if provider.supports(fragment):
            selected_provider = provider
            break

    if selected_provider is None:
        return ScopeAttributeSemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
            candidates=(),
        )

    try:
        raw_candidates = tuple(selected_provider.discover(fragment))
    except Exception as exc:
        return ScopeAttributeSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidates=(),
            errors=(str(exc),),
        )

    normalized_candidates: list[DiscoveredScopeAttribute] = []
    seen: set[tuple[str, ...]] = set()
    errors: list[str] = []

    for raw_candidate in raw_candidates:
        try:
            candidate = _normalize_candidate(raw_candidate)
            _validate_candidate(fragment, candidate)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        dedupe_key = _dedupe_key(candidate)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_candidates.append(candidate)

    if errors:
        return ScopeAttributeSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidates=(),
            errors=tuple(errors),
        )

    review_required_count = len(normalized_candidates)
    if not normalized_candidates:
        return ScopeAttributeSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_NO_ATTRIBUTES,
            candidates=(),
        )

    return ScopeAttributeSemanticDiscoveryResult(
        provider_name=selected_provider.provider_name,
        provider_version=selected_provider.provider_version,
        contract_version=selected_provider.contract_version,
        candidate_count=len(normalized_candidates),
        review_required_count=review_required_count,
        status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=tuple(normalized_candidates),
    )


def map_discovered_scope_attribute_to_candidate(
    fragment: ScopeAttributeSemanticFragment,
    discovered: DiscoveredScopeAttribute,
) -> ScopeAttributeCandidate:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        raise ValueError("; ".join(fragment_errors))

    candidate = _normalize_candidate(discovered)
    _validate_candidate(fragment, candidate)

    return ScopeAttributeCandidate(
        tender_id=fragment.tender_id,
        scope_detail_id=fragment.scope_detail_id,
        source_document_id=fragment.source_document_id,
        document_page_id=fragment.document_page_id,
        source_method=fragment.source_method,
        source_artifact_key=fragment.source_artifact_key,
        source_locator=fragment.source_locator,
        source_excerpt=candidate.evidence_excerpt,
        attribute_name=candidate.attribute_name,
        value_raw=candidate.value_raw,
        review_required=True,
        attribute_label_raw=candidate.attribute_label_raw,
        normalized_name=None,
        unit_raw=candidate.unit_raw,
        relation=candidate.relation,
        confidence=candidate.confidence,
        source_contract_version=fragment.source_contract_version,
        source_analysis_id=fragment.source_analysis_id,
        source_page_result_id=fragment.source_page_result_id,
    )


def _validate_fragment(fragment: ScopeAttributeSemanticFragment) -> tuple[str, ...]:
    errors: list[str] = []

    for field_name, value in (
        ("tender_id", fragment.tender_id),
        ("scope_detail_id", fragment.scope_detail_id),
        ("source_document_id", fragment.source_document_id),
        ("document_page_id", fragment.document_page_id),
        ("page_number", fragment.page_number),
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

    if fragment.source_method not in SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS:
        errors.append(f"Unsupported source_method: {fragment.source_method}")

    if fragment.source_analysis_id is not None and not _optional_text(fragment.source_analysis_id):
        errors.append("source_analysis_id is required when provided")
    if fragment.source_page_result_id is not None and not _optional_text(fragment.source_page_result_id):
        errors.append("source_page_result_id is required when provided")

    return tuple(errors)


def _validate_candidate(
    fragment: ScopeAttributeSemanticFragment,
    candidate: DiscoveredScopeAttribute,
) -> None:
    _required_text(candidate.attribute_name, field_name="attribute_name")
    _required_text(candidate.value_raw, field_name="value_raw")
    _required_text(candidate.evidence_excerpt, field_name="evidence_excerpt")

    if candidate.relation is not None and candidate.relation not in _ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {candidate.relation}")
    relation = candidate.relation or SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED

    if candidate.confidence is not None and not (0.0 <= candidate.confidence <= 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")

    if not _is_grounded(fragment.source_text, candidate.evidence_excerpt):
        raise ValueError("evidence_excerpt is not supported by source_text")
    if not _is_grounded(candidate.evidence_excerpt, candidate.value_raw):
        raise ValueError("value_raw is not grounded in evidence_excerpt")

    if candidate.attribute_label_raw is not None and not _is_grounded(candidate.evidence_excerpt, candidate.attribute_label_raw):
        raise ValueError("attribute_label_raw is not grounded in evidence_excerpt")

    if candidate.unit_raw is not None and not (
        _is_grounded(candidate.evidence_excerpt, candidate.unit_raw)
        or _is_grounded(candidate.value_raw, candidate.unit_raw)
    ):
        raise ValueError("unit_raw is not grounded in evidence_excerpt or value_raw")

    if relation != SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED and relation not in _ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {relation}")


def _normalize_candidate(discovered: DiscoveredScopeAttribute) -> DiscoveredScopeAttribute:
    attribute_name = _required_text(discovered.attribute_name, field_name="attribute_name")
    value_raw = _required_text(discovered.value_raw, field_name="value_raw")
    evidence_excerpt = _required_text(discovered.evidence_excerpt, field_name="evidence_excerpt")
    attribute_label_raw = _optional_text(discovered.attribute_label_raw)
    unit_raw = _optional_text(discovered.unit_raw)
    relation = _optional_text(discovered.relation)
    if relation is None:
        relation = SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED
    if relation not in _ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {relation}")

    return DiscoveredScopeAttribute(
        attribute_name=attribute_name,
        value_raw=value_raw,
        evidence_excerpt=evidence_excerpt,
        attribute_label_raw=attribute_label_raw,
        unit_raw=unit_raw,
        relation=relation,
        confidence=discovered.confidence,
    )


def _dedupe_key(candidate: DiscoveredScopeAttribute) -> tuple[str, ...]:
    return (
        candidate.attribute_name,
        candidate.value_raw,
        candidate.attribute_label_raw or "",
        candidate.unit_raw or "",
        candidate.relation or SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
        candidate.evidence_excerpt,
        "" if candidate.confidence is None else repr(candidate.confidence),
    )


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
