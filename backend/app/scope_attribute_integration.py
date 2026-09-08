from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.models import DocumentPage, TenderScopeAttribute, TenderScopeDetail
from app.scope_attribute_materializer import (
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_UNSUPPORTED,
    ScopeAttributeAdapter,
    materialize_scope_attributes_for_scope_detail,
)
from app.scope_attribute_semantic_discovery import (
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    DiscoveredScopeAttribute,
    ScopeAttributeSemanticDiscoveryProvider,
    ScopeAttributeSemanticFragment,
    discover_scope_attributes,
    map_discovered_scope_attribute_to_candidate,
)
from app.scope_attributes import (
    SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS,
    ScopeAttributeCandidate,
    list_scope_attributes_for_scope_detail,
)

SCOPE_ATTRIBUTE_INTEGRATION_SEMANTIC_STATUS_SKIPPED = "SKIPPED"
SCOPE_ATTRIBUTE_INTEGRATION_REASON_ATTRIBUTE_VALUE_CONFLICT = "ATTRIBUTE_VALUE_CONFLICT"

_ALLOWED_SEMANTIC_DETERMINISTIC_STATUSES = {
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_MATERIALIZED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_UNSUPPORTED,
    SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
}


@dataclass(frozen=True, slots=True)
class ScopeAttributeSuppressedDuplicate:
    attribute_name: str
    value_raw: str
    deterministic_attribute_id: str
    semantic_candidate: ScopeAttributeCandidate
    reason: str


@dataclass(frozen=True, slots=True)
class ScopeAttributeConflict:
    attribute_name: str
    deterministic_value_raw: str
    semantic_value_raw: str
    deterministic_attribute_id: str
    semantic_candidate: ScopeAttributeCandidate
    reason: str


@dataclass(frozen=True, slots=True)
class ScopeAttributeIntegrationResult:
    scope_detail_id: str
    deterministic_status: str
    semantic_status: str
    deterministic_attributes: tuple[TenderScopeAttribute, ...]
    semantic_review_candidates: tuple[ScopeAttributeCandidate, ...]
    suppressed_duplicates: tuple[ScopeAttributeSuppressedDuplicate, ...]
    conflicts: tuple[ScopeAttributeConflict, ...]
    semantic_provider_name: str | None
    semantic_provider_version: str | None
    semantic_contract_version: str | None
    diagnostics: tuple[str, ...]
    deterministic_count: int
    semantic_discovered_count: int
    semantic_review_count: int
    duplicate_suppressed_count: int
    conflict_count: int


def integrate_scope_attributes_for_scope_detail(
    db: Session,
    *,
    scope_detail_id: str,
    semantic_provider: ScopeAttributeSemanticDiscoveryProvider,
    adapters: Sequence[ScopeAttributeAdapter] | None = None,
) -> ScopeAttributeIntegrationResult:
    deterministic = materialize_scope_attributes_for_scope_detail(
        db,
        scope_detail_id=scope_detail_id,
        adapters=adapters,
    )
    deterministic_attributes = tuple(
        list_scope_attributes_for_scope_detail(db, scope_detail_id=scope_detail_id)
    )

    diagnostics: list[str] = list(deterministic.errors)

    if deterministic.status == SCOPE_ATTRIBUTE_MATERIALIZATION_STATUS_INVALID_EVIDENCE:
        return _build_result(
            scope_detail_id=scope_detail_id,
            deterministic_status=deterministic.status,
            semantic_status=SCOPE_ATTRIBUTE_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
            deterministic_attributes=deterministic_attributes,
            semantic_review_candidates=(),
            suppressed_duplicates=(),
            conflicts=(),
            semantic_provider_name=None,
            semantic_provider_version=None,
            semantic_contract_version=None,
            diagnostics=tuple(diagnostics),
            semantic_discovered_count=0,
        )

    if deterministic.status not in _ALLOWED_SEMANTIC_DETERMINISTIC_STATUSES:
        diagnostics.append(
            f"semantic supplementation skipped for deterministic status: {deterministic.status}"
        )
        return _build_result(
            scope_detail_id=scope_detail_id,
            deterministic_status=deterministic.status,
            semantic_status=SCOPE_ATTRIBUTE_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
            deterministic_attributes=deterministic_attributes,
            semantic_review_candidates=(),
            suppressed_duplicates=(),
            conflicts=(),
            semantic_provider_name=None,
            semantic_provider_version=None,
            semantic_contract_version=None,
            diagnostics=tuple(diagnostics),
            semantic_discovered_count=0,
        )

    try:
        fragment = _build_semantic_fragment(db, scope_detail_id=scope_detail_id)
    except ValueError as exc:
        diagnostics.append(str(exc))
        return _build_result(
            scope_detail_id=scope_detail_id,
            deterministic_status=deterministic.status,
            semantic_status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            deterministic_attributes=deterministic_attributes,
            semantic_review_candidates=(),
            suppressed_duplicates=(),
            conflicts=(),
            semantic_provider_name=getattr(semantic_provider, "provider_name", None),
            semantic_provider_version=getattr(semantic_provider, "provider_version", None),
            semantic_contract_version=getattr(semantic_provider, "contract_version", None),
            diagnostics=tuple(diagnostics),
            semantic_discovered_count=0,
        )

    semantic = discover_scope_attributes(fragment, providers=(semantic_provider,))
    diagnostics.extend(semantic.errors)

    if semantic.status != SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED:
        return _build_result(
            scope_detail_id=scope_detail_id,
            deterministic_status=deterministic.status,
            semantic_status=semantic.status,
            deterministic_attributes=deterministic_attributes,
            semantic_review_candidates=(),
            suppressed_duplicates=(),
            conflicts=(),
            semantic_provider_name=semantic.provider_name,
            semantic_provider_version=semantic.provider_version,
            semantic_contract_version=semantic.contract_version,
            diagnostics=tuple(diagnostics),
            semantic_discovered_count=semantic.candidate_count,
        )

    mapped_candidates: list[ScopeAttributeCandidate] = []
    for discovered in semantic.candidates:
        try:
            candidate = map_discovered_scope_attribute_to_candidate(fragment, discovered)
        except Exception as exc:
            diagnostics.append(str(exc))
            return _build_result(
                scope_detail_id=scope_detail_id,
                deterministic_status=deterministic.status,
                semantic_status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                deterministic_attributes=deterministic_attributes,
                semantic_review_candidates=(),
                suppressed_duplicates=(),
                conflicts=(),
                semantic_provider_name=semantic.provider_name,
                semantic_provider_version=semantic.provider_version,
                semantic_contract_version=semantic.contract_version,
                diagnostics=tuple(diagnostics),
                semantic_discovered_count=semantic.candidate_count,
            )

        if not candidate.review_required:
            diagnostics.append(
                "semantic candidate review_required invariant failed"
            )
            return _build_result(
                scope_detail_id=scope_detail_id,
                deterministic_status=deterministic.status,
                semantic_status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                deterministic_attributes=deterministic_attributes,
                semantic_review_candidates=(),
                suppressed_duplicates=(),
                conflicts=(),
                semantic_provider_name=semantic.provider_name,
                semantic_provider_version=semantic.provider_version,
                semantic_contract_version=semantic.contract_version,
                diagnostics=tuple(diagnostics),
                semantic_discovered_count=semantic.candidate_count,
            )

        if candidate.source_method not in SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS:
            diagnostics.append(
                f"semantic candidate source_method invariant failed: {candidate.source_method}"
            )
            return _build_result(
                scope_detail_id=scope_detail_id,
                deterministic_status=deterministic.status,
                semantic_status=SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                deterministic_attributes=deterministic_attributes,
                semantic_review_candidates=(),
                suppressed_duplicates=(),
                conflicts=(),
                semantic_provider_name=semantic.provider_name,
                semantic_provider_version=semantic.provider_version,
                semantic_contract_version=semantic.contract_version,
                diagnostics=tuple(diagnostics),
                semantic_discovered_count=semantic.candidate_count,
            )

        mapped_candidates.append(candidate)

    semantic_review_candidates, suppressed_duplicates, conflicts = _merge_semantic_candidates(
        deterministic_attributes=deterministic_attributes,
        semantic_candidates=tuple(mapped_candidates),
    )

    return _build_result(
        scope_detail_id=scope_detail_id,
        deterministic_status=deterministic.status,
        semantic_status=semantic.status,
        deterministic_attributes=deterministic_attributes,
        semantic_review_candidates=semantic_review_candidates,
        suppressed_duplicates=suppressed_duplicates,
        conflicts=conflicts,
        semantic_provider_name=semantic.provider_name,
        semantic_provider_version=semantic.provider_version,
        semantic_contract_version=semantic.contract_version,
        diagnostics=tuple(diagnostics),
        semantic_discovered_count=semantic.candidate_count,
    )


def _merge_semantic_candidates(
    *,
    deterministic_attributes: tuple[TenderScopeAttribute, ...],
    semantic_candidates: tuple[ScopeAttributeCandidate, ...],
) -> tuple[
    tuple[ScopeAttributeCandidate, ...],
    tuple[ScopeAttributeSuppressedDuplicate, ...],
    tuple[ScopeAttributeConflict, ...],
]:
    deterministic_by_key: dict[tuple[str, str], TenderScopeAttribute] = {}
    deterministic_by_name: dict[str, TenderScopeAttribute] = {}

    for deterministic in deterministic_attributes:
        key = (_normalize_identity(deterministic.attribute_name), _normalize_identity(deterministic.value_raw))
        deterministic_by_key.setdefault(key, deterministic)
        deterministic_by_name.setdefault(_normalize_identity(deterministic.attribute_name), deterministic)

    review_candidates: list[ScopeAttributeCandidate] = []
    suppressed_duplicates: list[ScopeAttributeSuppressedDuplicate] = []
    conflicts: list[ScopeAttributeConflict] = []

    seen_review: set[tuple[str, str]] = set()
    seen_suppressed: set[tuple[str, str, str]] = set()
    seen_conflicts: set[tuple[str, str, str]] = set()

    for semantic_candidate in semantic_candidates:
        name_key = _normalize_identity(semantic_candidate.attribute_name)
        value_key = _normalize_identity(semantic_candidate.value_raw)
        full_key = (name_key, value_key)

        deterministic_match = deterministic_by_key.get(full_key)
        if deterministic_match is not None:
            suppress_key = (deterministic_match.id, name_key, value_key)
            if suppress_key not in seen_suppressed:
                seen_suppressed.add(suppress_key)
                reason = "semantic duplicate suppressed"
                if _semantic_metadata_differs(deterministic_match, semantic_candidate):
                    reason = "semantic duplicate suppressed (unit/relation metadata differs)"
                suppressed_duplicates.append(
                    ScopeAttributeSuppressedDuplicate(
                        attribute_name=semantic_candidate.attribute_name,
                        value_raw=semantic_candidate.value_raw,
                        deterministic_attribute_id=deterministic_match.id,
                        semantic_candidate=semantic_candidate,
                        reason=reason,
                    )
                )
            continue

        deterministic_same_name = deterministic_by_name.get(name_key)
        if deterministic_same_name is not None:
            conflict_key = (
                deterministic_same_name.id,
                name_key,
                _normalize_identity(semantic_candidate.value_raw),
            )
            if conflict_key not in seen_conflicts:
                seen_conflicts.add(conflict_key)
                conflicts.append(
                    ScopeAttributeConflict(
                        attribute_name=semantic_candidate.attribute_name,
                        deterministic_value_raw=deterministic_same_name.value_raw,
                        semantic_value_raw=semantic_candidate.value_raw,
                        deterministic_attribute_id=deterministic_same_name.id,
                        semantic_candidate=semantic_candidate,
                        reason=SCOPE_ATTRIBUTE_INTEGRATION_REASON_ATTRIBUTE_VALUE_CONFLICT,
                    )
                )

        review_key = (name_key, value_key)
        if review_key not in seen_review:
            seen_review.add(review_key)
            review_candidates.append(semantic_candidate)

    return (
        tuple(review_candidates),
        tuple(suppressed_duplicates),
        tuple(conflicts),
    )


def _semantic_metadata_differs(
    deterministic: TenderScopeAttribute,
    semantic_candidate: ScopeAttributeCandidate,
) -> bool:
    deterministic_unit = _normalize_optional(deterministic.unit_raw)
    semantic_unit = _normalize_optional(semantic_candidate.unit_raw)
    deterministic_relation = _normalize_optional(deterministic.relation)
    semantic_relation = _normalize_optional(semantic_candidate.relation)
    return deterministic_unit != semantic_unit or deterministic_relation != semantic_relation


def _build_semantic_fragment(
    db: Session,
    *,
    scope_detail_id: str,
) -> ScopeAttributeSemanticFragment:
    scope_detail = db.get(TenderScopeDetail, scope_detail_id)
    if scope_detail is None:
        raise ValueError("scope_detail_id does not exist")

    page = db.get(DocumentPage, scope_detail.document_page_id)
    if page is None:
        raise ValueError("scope_detail document page does not exist")

    source_text = str(scope_detail.source_excerpt or "").strip()
    if not source_text:
        raise ValueError("scope_detail.source_excerpt is required")

    return ScopeAttributeSemanticFragment(
        tender_id=scope_detail.tender_id,
        scope_detail_id=scope_detail.id,
        source_document_id=scope_detail.source_document_id,
        document_page_id=scope_detail.document_page_id,
        page_number=page.page_number,
        source_method=scope_detail.source_method,
        source_artifact_key=scope_detail.source_artifact_key,
        source_locator=scope_detail.source_locator,
        scope_detail_domain=scope_detail.domain,
        scope_detail_description=scope_detail.description,
        source_text=source_text,
        source_contract_version=scope_detail.source_contract_version,
        source_analysis_id=scope_detail.source_analysis_id,
        source_page_result_id=scope_detail.source_page_result_id,
    )


def _build_result(
    *,
    scope_detail_id: str,
    deterministic_status: str,
    semantic_status: str,
    deterministic_attributes: tuple[TenderScopeAttribute, ...],
    semantic_review_candidates: tuple[ScopeAttributeCandidate, ...],
    suppressed_duplicates: tuple[ScopeAttributeSuppressedDuplicate, ...],
    conflicts: tuple[ScopeAttributeConflict, ...],
    semantic_provider_name: str | None,
    semantic_provider_version: str | None,
    semantic_contract_version: str | None,
    diagnostics: tuple[str, ...],
    semantic_discovered_count: int,
) -> ScopeAttributeIntegrationResult:
    return ScopeAttributeIntegrationResult(
        scope_detail_id=scope_detail_id,
        deterministic_status=deterministic_status,
        semantic_status=semantic_status,
        deterministic_attributes=deterministic_attributes,
        semantic_review_candidates=semantic_review_candidates,
        suppressed_duplicates=suppressed_duplicates,
        conflicts=conflicts,
        semantic_provider_name=semantic_provider_name,
        semantic_provider_version=semantic_provider_version,
        semantic_contract_version=semantic_contract_version,
        diagnostics=diagnostics,
        deterministic_count=len(deterministic_attributes),
        semantic_discovered_count=semantic_discovered_count,
        semantic_review_count=len(semantic_review_candidates),
        duplicate_suppressed_count=len(suppressed_duplicates),
        conflict_count=len(conflicts),
    )


def _normalize_identity(value: str) -> str:
    return " ".join(str(value or "").split()).upper()


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).upper()
    return normalized or None
