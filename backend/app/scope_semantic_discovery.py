from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.scope_details import (
    SCOPE_DETAIL_ALLOWED_APPLICABILITY,
    SCOPE_DETAIL_ALLOWED_DOMAINS,
    SCOPE_DETAIL_APPLICABILITY_ITEM,
    SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
    SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
    ScopeDetailCandidate,
)

SCOPE_SEMANTIC_DISCOVERY_CONTRACT_VERSION = "scope-semantic-discovery-001"

SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED = "DISCOVERED"
SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS = "NO_OBLIGATIONS"
SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"


@dataclass(frozen=True, slots=True)
class ScopeSemanticSourceFragment:
    tender_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_text: str
    source_contract_version: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredScopeObligation:
    domain: str
    description: str
    evidence_excerpt: str
    review_required: bool
    detail_type: str | None = None
    normalized_label: str | None = None
    confidence: float | None = None
    quantity_raw: str | None = None
    unit_raw: str | None = None
    candidate_item_key: str | None = None
    applicability_hint: str | None = None


@dataclass(frozen=True, slots=True)
class ScopeSemanticDiscoveryResult:
    provider_name: str | None
    provider_version: str | None
    contract_version: str | None
    candidate_count: int
    review_required_count: int
    status: str
    candidates: tuple[DiscoveredScopeObligation, ...]
    errors: tuple[str, ...] = ()


class ScopeSemanticDiscoveryProvider(Protocol):
    provider_name: str
    provider_version: str
    contract_version: str

    def supports(self, fragment: ScopeSemanticSourceFragment) -> bool:
        ...

    def discover(self, fragment: ScopeSemanticSourceFragment) -> Sequence[DiscoveredScopeObligation]:
        ...


def discover_scope_semantics(
    fragment: ScopeSemanticSourceFragment,
    *,
    providers: Sequence[ScopeSemanticDiscoveryProvider],
) -> ScopeSemanticDiscoveryResult:
    _validate_source_fragment(fragment)

    selected_provider: ScopeSemanticDiscoveryProvider | None = None
    for provider in providers:
        if provider.supports(fragment):
            selected_provider = provider
            break

    if selected_provider is None:
        return ScopeSemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SCOPE_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
            candidates=(),
        )

    raw_candidates = tuple(selected_provider.discover(fragment))
    deduped_candidates: list[DiscoveredScopeObligation] = []
    dedupe_keys: set[tuple[str, ...]] = set()
    errors: list[str] = []

    for candidate in raw_candidates:
        try:
            normalized_candidate = _normalize_obligation(candidate)
            _validate_discovered_obligation(fragment, normalized_candidate)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        dedupe_key = _dedupe_key(normalized_candidate)
        if dedupe_key in dedupe_keys:
            continue
        dedupe_keys.add(dedupe_key)
        deduped_candidates.append(normalized_candidate)

    if errors:
        return ScopeSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidates=(),
            errors=tuple(errors),
        )

    review_required_count = sum(1 for candidate in deduped_candidates if candidate.review_required)
    if not deduped_candidates:
        return ScopeSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
            candidates=(),
        )

    status = (
        SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
        if review_required_count > 0
        else SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    )
    return ScopeSemanticDiscoveryResult(
        provider_name=selected_provider.provider_name,
        provider_version=selected_provider.provider_version,
        contract_version=selected_provider.contract_version,
        candidate_count=len(deduped_candidates),
        review_required_count=review_required_count,
        status=status,
        candidates=tuple(deduped_candidates),
    )


def map_discovered_obligation_to_scope_detail_candidate(
    fragment: ScopeSemanticSourceFragment,
    obligation: DiscoveredScopeObligation,
) -> ScopeDetailCandidate:
    _validate_source_fragment(fragment)
    normalized_obligation = _normalize_obligation(obligation)
    _validate_discovered_obligation(fragment, normalized_obligation)

    applicability = _resolve_applicability(normalized_obligation)
    if applicability == SCOPE_DETAIL_APPLICABILITY_UNRESOLVED and not normalized_obligation.review_required:
        raise ValueError(
            "Cannot map ownership-neutral obligation to ScopeDetailCandidate without explicit applicability or review_required=true"
        )

    if applicability == SCOPE_DETAIL_APPLICABILITY_ITEM and normalized_obligation.candidate_item_key is None:
        raise ValueError("ITEM applicability requires candidate_item_key")

    return ScopeDetailCandidate(
        tender_id=fragment.tender_id,
        source_document_id=fragment.source_document_id,
        document_page_id=fragment.document_page_id,
        domain=normalized_obligation.domain,
        detail_type=normalized_obligation.detail_type,
        description=normalized_obligation.description,
        normalized_label=normalized_obligation.normalized_label,
        applicability=applicability,
        source_method=fragment.source_method,
        source_artifact_key=fragment.source_artifact_key,
        source_contract_version=fragment.source_contract_version,
        source_locator=fragment.source_locator,
        source_excerpt=normalized_obligation.evidence_excerpt,
        confidence=normalized_obligation.confidence,
        review_required=normalized_obligation.review_required,
        scope_segment_id=None,
        tender_item_id=None,
        candidate_item_key=normalized_obligation.candidate_item_key,
        source_analysis_id=None,
        source_page_result_id=None,
        quantity_raw=normalized_obligation.quantity_raw,
        unit_raw=normalized_obligation.unit_raw,
    )


def _validate_source_fragment(fragment: ScopeSemanticSourceFragment) -> None:
    _required_text("tender_id", fragment.tender_id)
    _required_text("source_document_id", fragment.source_document_id)
    _required_text("document_page_id", fragment.document_page_id)
    _required_text("source_method", fragment.source_method)
    _required_text("source_artifact_key", fragment.source_artifact_key)
    _required_text("source_locator", fragment.source_locator)
    _required_text("source_text", fragment.source_text)

    if fragment.page_number <= 0:
        raise ValueError("page_number must be greater than zero")

    if fragment.confidence is not None and not 0 <= fragment.confidence <= 1:
        raise ValueError("fragment confidence must be between 0 and 1")


def _validate_discovered_obligation(
    fragment: ScopeSemanticSourceFragment,
    obligation: DiscoveredScopeObligation,
) -> None:
    if obligation.domain not in SCOPE_DETAIL_ALLOWED_DOMAINS:
        raise ValueError(f"Unsupported semantic domain: {obligation.domain}")

    _required_text("description", obligation.description)
    _required_text("evidence_excerpt", obligation.evidence_excerpt)

    if obligation.confidence is not None and not 0 <= obligation.confidence <= 1:
        raise ValueError("candidate confidence must be between 0 and 1")

    applicability_hint = obligation.applicability_hint
    if applicability_hint is not None and applicability_hint not in SCOPE_DETAIL_ALLOWED_APPLICABILITY:
        raise ValueError(f"Unsupported applicability hint: {applicability_hint}")

    if applicability_hint == SCOPE_DETAIL_APPLICABILITY_ITEM and obligation.candidate_item_key is None:
        raise ValueError("ITEM applicability hint requires candidate_item_key")

    normalized_source = _normalize_text(fragment.source_text)
    normalized_excerpt = _normalize_text(obligation.evidence_excerpt)
    if normalized_excerpt not in normalized_source:
        raise ValueError("evidence_excerpt is not supported by source_text")


def _resolve_applicability(obligation: DiscoveredScopeObligation) -> str:
    if obligation.applicability_hint == SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE:
        return SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE
    if obligation.applicability_hint == SCOPE_DETAIL_APPLICABILITY_ITEM:
        return SCOPE_DETAIL_APPLICABILITY_ITEM
    if obligation.candidate_item_key is not None:
        return SCOPE_DETAIL_APPLICABILITY_ITEM
    return SCOPE_DETAIL_APPLICABILITY_UNRESOLVED


def _dedupe_key(obligation: DiscoveredScopeObligation) -> tuple[str, ...]:
    return (
        obligation.domain,
        obligation.detail_type or "",
        obligation.description,
        obligation.normalized_label or "",
        obligation.evidence_excerpt,
        "1" if obligation.review_required else "0",
        "" if obligation.confidence is None else repr(obligation.confidence),
        obligation.quantity_raw or "",
        obligation.unit_raw or "",
        obligation.candidate_item_key or "",
        obligation.applicability_hint or "",
    )


def _normalize_obligation(obligation: DiscoveredScopeObligation) -> DiscoveredScopeObligation:
    domain = _required_text("domain", obligation.domain).upper().replace("-", "_").replace(" ", "_")
    description = _required_text("description", obligation.description)
    evidence_excerpt = _required_text("evidence_excerpt", obligation.evidence_excerpt)
    detail_type = _optional_text(obligation.detail_type)
    normalized_label = _optional_text(obligation.normalized_label)
    candidate_item_key = _optional_text(obligation.candidate_item_key)
    applicability_hint = _optional_text(obligation.applicability_hint)
    if applicability_hint is not None:
        applicability_hint = applicability_hint.upper().replace("-", "_").replace(" ", "_")

    return DiscoveredScopeObligation(
        domain=domain,
        description=description,
        evidence_excerpt=evidence_excerpt,
        review_required=bool(obligation.review_required),
        detail_type=detail_type,
        normalized_label=normalized_label,
        confidence=obligation.confidence,
        quantity_raw=_optional_text(obligation.quantity_raw),
        unit_raw=_optional_text(obligation.unit_raw),
        candidate_item_key=candidate_item_key,
        applicability_hint=applicability_hint,
    )


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()


def _required_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None