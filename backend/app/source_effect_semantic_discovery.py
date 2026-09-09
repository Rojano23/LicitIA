from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TenderDocument
from app.source_effect_adapters import build_source_effect_document_aliases
from app.source_effect_deterministic import (
    SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT,
    SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET,
    SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW,
    SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT,
)
from app.source_effects import (
    SOURCE_EFFECT_ALLOWED_SCOPES,
    SOURCE_EFFECT_ALLOWED_SOURCE_METHODS,
    SOURCE_EFFECT_ALLOWED_TYPES,
    SourceEffectCandidate,
    compute_source_effect_fingerprint,
    validate_source_effect_candidate,
)

SOURCE_EFFECT_SEMANTIC_DISCOVERY_CONTRACT_VERSION = "source-effect-semantic-discovery-2026-09-08-001"

SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED = "DISCOVERED"
SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS = "NO_EFFECTS"
SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED = "UNSUPPORTED"
SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"

_ALLOWED_STATUSES = {
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
}

_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAnexo\s+(?:T[eé]cnico(?:\s+Rev\.?\s*\d+)?|[A-Z0-9]+(?:[-\.][A-Z0-9]+)*)\b", re.IGNORECASE),
    re.compile(r"\bBases(?:\s+de\s+Licitaci[oó]n)?\b", re.IGNORECASE),
    re.compile(r"\bConvocatoria\b", re.IGNORECASE),
    re.compile(r"\bDocumento\s+[A-Z0-9]+(?:[-\.][A-Z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\bFormato\s+[A-Z0-9]+(?:[-\.][A-Z0-9]+)*\b", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class SourceEffectSemanticFragment:
    tender_id: str
    acting_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_text: str
    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredSourceEffect:
    effect_type: str
    effect_scope: str
    affected_document_ref_raw: str | None
    affected_locator_raw: str | None
    effective_date_raw: str | None
    evidence_excerpt: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class SourceEffectProviderDiscoveryPayload:
    status: str
    effects: tuple[DiscoveredSourceEffect, ...] = ()
    diagnostics: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceEffectSemanticDiscoveryResult:
    provider_name: str | None
    provider_version: str | None
    contract_version: str | None
    status: str
    candidate_count: int
    review_required_count: int
    candidates: tuple[SourceEffectCandidate, ...]
    discovered_effects: tuple[DiscoveredSourceEffect, ...]
    diagnostics: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class SourceEffectSemanticDiscoveryProvider(Protocol):
    provider_name: str
    provider_version: str
    contract_version: str

    def supports(self, fragment: SourceEffectSemanticFragment) -> bool:
        ...

    def discover(self, fragment: SourceEffectSemanticFragment) -> SourceEffectProviderDiscoveryPayload:
        ...


def discover_source_effect_semantics(
    db: Session,
    fragment: SourceEffectSemanticFragment,
    *,
    providers: Sequence[SourceEffectSemanticDiscoveryProvider],
) -> SourceEffectSemanticDiscoveryResult:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SOURCE_EFFECT_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            errors=fragment_errors,
        )

    selected_provider: Optional[SourceEffectSemanticDiscoveryProvider] = None
    for provider in providers:
        if provider.supports(fragment):
            selected_provider = provider
            break

    if selected_provider is None:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=None,
            provider_version=None,
            contract_version=SOURCE_EFFECT_SEMANTIC_DISCOVERY_CONTRACT_VERSION,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
        )

    try:
        provider_payload = selected_provider.discover(fragment)
    except Exception as exc:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            errors=(str(exc),),
        )

    try:
        payload = _normalize_provider_payload(provider_payload)
        _validate_provider_payload_contract(payload)
    except ValueError as exc:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            errors=(str(exc),),
        )

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=payload.diagnostics,
            errors=payload.errors,
        )

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=payload.diagnostics,
            errors=payload.errors,
        )

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=payload.diagnostics,
            errors=payload.errors or ("Provider reported INVALID_OUTPUT",),
        )

    mapped_candidates: list[SourceEffectCandidate] = []
    mapped_effects: list[DiscoveredSourceEffect] = []
    diagnostics = list(payload.diagnostics)
    seen_fingerprints: set[str] = set()

    for index, discovered in enumerate(payload.effects):
        try:
            normalized = _normalize_discovered_effect(discovered)
            _validate_discovered_effect(fragment, normalized)
            candidate, candidate_diagnostics = map_discovered_source_effect_to_candidate(
                db,
                fragment,
                normalized,
                ordinal=index,
            )
            validate_source_effect_candidate(db, candidate)
        except ValueError as exc:
            return SourceEffectSemanticDiscoveryResult(
                provider_name=selected_provider.provider_name,
                provider_version=selected_provider.provider_version,
                contract_version=selected_provider.contract_version,
                status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                candidate_count=0,
                review_required_count=0,
                candidates=(),
                discovered_effects=(),
                diagnostics=tuple(diagnostics),
                errors=(str(exc),),
            )

        fingerprint = compute_source_effect_fingerprint(candidate)
        if fingerprint in seen_fingerprints:
            continue

        seen_fingerprints.add(fingerprint)
        diagnostics.extend(candidate_diagnostics)
        mapped_candidates.append(candidate)
        mapped_effects.append(normalized)

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED and not mapped_candidates:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=tuple(diagnostics),
            errors=("DISCOVERED status requires at least one valid discovered effect",),
        )

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED and not mapped_candidates:
        return SourceEffectSemanticDiscoveryResult(
            provider_name=selected_provider.provider_name,
            provider_version=selected_provider.provider_version,
            contract_version=selected_provider.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=tuple(diagnostics),
            errors=payload.errors,
        )

    final_status = payload.status
    if diagnostics and final_status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED:
        final_status = SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED

    return SourceEffectSemanticDiscoveryResult(
        provider_name=selected_provider.provider_name,
        provider_version=selected_provider.provider_version,
        contract_version=selected_provider.contract_version,
        status=final_status,
        candidate_count=len(mapped_candidates),
        review_required_count=len(mapped_candidates),
        candidates=tuple(mapped_candidates),
        discovered_effects=tuple(mapped_effects),
        diagnostics=tuple(diagnostics),
        errors=payload.errors,
    )


def map_discovered_source_effect_to_candidate(
    db: Session,
    fragment: SourceEffectSemanticFragment,
    discovered: DiscoveredSourceEffect,
    *,
    ordinal: int = 0,
) -> tuple[SourceEffectCandidate, tuple[str, ...]]:
    fragment_errors = _validate_fragment(fragment)
    if fragment_errors:
        raise ValueError("; ".join(fragment_errors))

    normalized = _normalize_discovered_effect(discovered)
    _validate_discovered_effect(fragment, normalized)

    diagnostics: list[str] = []
    affected_document_id: str | None = None

    affected_ref_raw = normalized.affected_document_ref_raw
    if affected_ref_raw is not None:
        affected_document_id, resolution_diagnostic = _resolve_affected_document_id(
            db,
            tender_id=fragment.tender_id,
            acting_document_id=fragment.acting_document_id,
            affected_document_ref_raw=affected_ref_raw,
        )
        if resolution_diagnostic is not None:
            diagnostics.append(resolution_diagnostic)

    third_source_diagnostic = _third_source_diagnostic(normalized.evidence_excerpt, affected_ref_raw)
    if third_source_diagnostic is not None:
        diagnostics.append(third_source_diagnostic)

    candidate = SourceEffectCandidate(
        tender_id=fragment.tender_id,
        acting_document_id=fragment.acting_document_id,
        affected_document_id=affected_document_id,
        document_page_id=fragment.document_page_id,
        affected_document_page_id=None,
        effect_type=normalized.effect_type,
        effect_scope=normalized.effect_scope,
        affected_document_ref_raw=affected_ref_raw,
        affected_locator_raw=normalized.affected_locator_raw,
        effective_date_raw=normalized.effective_date_raw,
        source_method=fragment.source_method,
        source_artifact_key=fragment.source_artifact_key,
        source_locator=f"{fragment.source_locator}|semantic_effect:{ordinal}",
        source_excerpt=normalized.evidence_excerpt,
        review_required=True,
        confidence=normalized.confidence,
        source_contract_version=fragment.source_contract_version,
        source_analysis_id=fragment.source_analysis_id,
        source_page_result_id=fragment.source_page_result_id,
    )

    return candidate, tuple(diagnostics)


def _validate_fragment(fragment: SourceEffectSemanticFragment) -> tuple[str, ...]:
    errors: list[str] = []

    for field_name, value in (
        ("tender_id", fragment.tender_id),
        ("acting_document_id", fragment.acting_document_id),
        ("document_page_id", fragment.document_page_id),
        ("source_method", fragment.source_method),
        ("source_artifact_key", fragment.source_artifact_key),
        ("source_locator", fragment.source_locator),
        ("source_text", fragment.source_text),
    ):
        if not _optional_text(value):
            errors.append(f"{field_name} is required")

    try:
        if int(fragment.page_number) <= 0:
            errors.append("page_number must be greater than zero")
    except (TypeError, ValueError):
        errors.append("page_number must be greater than zero")

    if fragment.source_method not in SOURCE_EFFECT_ALLOWED_SOURCE_METHODS:
        errors.append(f"Unsupported source_method: {fragment.source_method}")

    if fragment.source_analysis_id is not None and not _optional_text(fragment.source_analysis_id):
        errors.append("source_analysis_id is required when provided")
    if fragment.source_page_result_id is not None and not _optional_text(fragment.source_page_result_id):
        errors.append("source_page_result_id is required when provided")

    return tuple(errors)


def _normalize_provider_payload(payload: SourceEffectProviderDiscoveryPayload) -> SourceEffectProviderDiscoveryPayload:
    status = _required_text(payload.status, field_name="status").upper().replace("-", "_").replace(" ", "_")
    return SourceEffectProviderDiscoveryPayload(
        status=status,
        effects=tuple(payload.effects),
        diagnostics=tuple(_required_text(item, field_name="diagnostic") for item in payload.diagnostics if _optional_text(item)),
        errors=tuple(_required_text(item, field_name="error") for item in payload.errors if _optional_text(item)),
    )


def _validate_provider_payload_contract(payload: SourceEffectProviderDiscoveryPayload) -> None:
    if payload.status not in _ALLOWED_STATUSES:
        raise ValueError(f"Unsupported discovery status: {payload.status}")

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED and not payload.effects:
        raise ValueError("DISCOVERED status requires at least one effect")

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS and payload.effects:
        raise ValueError("NO_EFFECTS status cannot include effects")

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED and payload.effects:
        raise ValueError("UNSUPPORTED status cannot include effects")

    if payload.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT and payload.effects:
        raise ValueError("INVALID_OUTPUT status cannot include effects")


def _validate_discovered_effect(fragment: SourceEffectSemanticFragment, effect: DiscoveredSourceEffect) -> None:
    if effect.effect_type not in SOURCE_EFFECT_ALLOWED_TYPES:
        raise ValueError(f"Unsupported effect_type: {effect.effect_type}")

    if effect.effect_scope not in SOURCE_EFFECT_ALLOWED_SCOPES:
        raise ValueError(f"Unsupported effect_scope: {effect.effect_scope}")

    if effect.confidence is not None and not 0.0 <= effect.confidence <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")

    if not _is_grounded(fragment.source_text, effect.evidence_excerpt):
        raise ValueError("evidence_excerpt is not grounded in source_text")

    if effect.affected_document_ref_raw is not None and not _is_grounded(effect.evidence_excerpt, effect.affected_document_ref_raw):
        raise ValueError("affected_document_ref_raw is not grounded in evidence_excerpt")

    if effect.affected_locator_raw is not None and not _is_grounded(effect.evidence_excerpt, effect.affected_locator_raw):
        raise ValueError("affected_locator_raw is not grounded in evidence_excerpt")

    if effect.effective_date_raw is not None and not _is_grounded(effect.evidence_excerpt, effect.effective_date_raw):
        raise ValueError("effective_date_raw is not grounded in evidence_excerpt")


def _normalize_discovered_effect(effect: DiscoveredSourceEffect) -> DiscoveredSourceEffect:
    effect_type = _required_text(effect.effect_type, field_name="effect_type").upper().replace("-", "_").replace(" ", "_")
    effect_scope = _required_text(effect.effect_scope, field_name="effect_scope").upper().replace("-", "_").replace(" ", "_")

    return DiscoveredSourceEffect(
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=_optional_text(effect.affected_document_ref_raw),
        affected_locator_raw=_optional_text(effect.affected_locator_raw),
        effective_date_raw=_optional_text(effect.effective_date_raw),
        evidence_excerpt=_required_text(effect.evidence_excerpt, field_name="evidence_excerpt"),
        confidence=effect.confidence,
    )


def _resolve_affected_document_id(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    affected_document_ref_raw: str,
) -> tuple[str | None, str | None]:
    reference_key = _normalize_text(affected_document_ref_raw)
    if not reference_key:
        return None, None

    matches: list[str] = []
    for doc in db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id)).scalars().all():
        aliases = build_source_effect_document_aliases(
            original_filename=doc.original_filename,
            source_relative_path=doc.source_relative_path,
        )
        if reference_key not in aliases:
            continue
        matches.append(doc.id)

    unique_matches = sorted(set(matches))
    if len(unique_matches) == 0:
        return None, SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT

    if len(unique_matches) > 1:
        return None, SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT

    if unique_matches[0] == acting_document_id:
        return None, SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET

    return unique_matches[0], None


def _third_source_diagnostic(evidence_excerpt: str, affected_document_ref_raw: str | None) -> str | None:
    if affected_document_ref_raw is None:
        return None
    lowered = evidence_excerpt.lower()
    marker = " por "
    index = lowered.find(marker)
    if index < 0:
        return None

    tail = evidence_excerpt[index + len(marker) :]
    third_ref = _extract_reference(tail)
    if third_ref is None:
        return None

    if _normalize_text(third_ref) == _normalize_text(affected_document_ref_raw):
        return None

    return SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW


def _extract_reference(text: str) -> str | None:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        value = _optional_text(match.group(0))
        if value is not None:
            return value
    return None


def _is_grounded(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).upper()


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
