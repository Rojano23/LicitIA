from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.models import DocumentPage, TenderScopeDetail, TenderScopeQuantity
from app.scope_quantities import ScopeQuantityCandidate, compute_scope_quantity_fingerprint, list_scope_quantities_for_scope_detail
from app.scope_quantity_adapters import ScopeQuantityAdapter
from app.scope_quantity_materializer import (
    SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
    ScopeQuantityMaterializationResult,
    materialize_scope_quantities_for_scope_detail,
)
from app.scope_quantity_semantic_discovery import (
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    ScopeQuantitySemanticDiscoveryProvider,
    ScopeQuantitySemanticDiscoveryResult,
    ScopeQuantitySemanticFragment,
    discover_scope_quantities,
)

SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED = "INTEGRATED"
SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_ONLY = "SEMANTIC_ONLY"
SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_UNAVAILABLE = "SEMANTIC_UNAVAILABLE"
SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_INVALID = "SEMANTIC_INVALID"

SCOPE_QUANTITY_INTEGRATION_SEMANTIC_STATUS_SKIPPED = "SKIPPED"
SCOPE_QUANTITY_INTEGRATION_REASON_DUPLICATE_DETERMINISTIC = "DUPLICATE_DETERMINISTIC"
SCOPE_QUANTITY_INTEGRATION_REASON_NORMALIZATION_CONFLICT = "QUANTITY_NORMALIZATION_CONFLICT"


@dataclass(frozen=True, slots=True)
class ScopeQuantityIntegrationProviderMetadata:
    provider_name: str | None
    provider_version: str | None
    contract_version: str | None


@dataclass(frozen=True, slots=True)
class ScopeQuantityDuplicateSemanticCandidate:
    deterministic_quantity_id: str
    reason: str
    semantic_candidate: ScopeQuantityCandidate


@dataclass(frozen=True, slots=True)
class ScopeQuantityConflictSemanticCandidate:
    deterministic_quantity_id: str
    reason: str
    deterministic_quantity_value: Decimal | None
    deterministic_quantity_min: Decimal | None
    deterministic_quantity_max: Decimal | None
    semantic_candidate: ScopeQuantityCandidate


@dataclass(frozen=True, slots=True)
class ScopeQuantityIntegrationResult:
    scope_detail_id: str
    status: str
    deterministic_status: str
    semantic_discovery_status: str
    deterministic_quantities: tuple[TenderScopeQuantity, ...]
    semantic_supplements: tuple[ScopeQuantityCandidate, ...]
    duplicate_semantic_candidates: tuple[ScopeQuantityDuplicateSemanticCandidate, ...]
    conflict_semantic_candidates: tuple[ScopeQuantityConflictSemanticCandidate, ...]
    semantic_provider_metadata: ScopeQuantityIntegrationProviderMetadata | None
    diagnostics: tuple[str, ...]
    errors: tuple[str, ...]
    deterministic_count: int
    semantic_supplement_count: int
    duplicate_semantic_count: int
    conflict_semantic_count: int


SemanticDiscoverer = Callable[
    [ScopeQuantitySemanticFragment, ScopeQuantitySemanticDiscoveryProvider],
    ScopeQuantitySemanticDiscoveryResult,
]


def integrate_scope_quantities_for_scope_detail(
    db: Session,
    *,
    scope_detail_id: str,
    adapters: Sequence[ScopeQuantityAdapter] | None = None,
    semantic_provider: ScopeQuantitySemanticDiscoveryProvider | None = None,
    semantic_discoverer: SemanticDiscoverer | None = None,
) -> ScopeQuantityIntegrationResult:
    deterministic = materialize_scope_quantities_for_scope_detail(
        db,
        scope_detail_id=scope_detail_id,
        adapters=adapters,
    )
    deterministic_quantities = tuple(list_scope_quantities_for_scope_detail(db, scope_detail_id=scope_detail_id))

    diagnostics = list(deterministic.errors)
    errors = list(deterministic.errors)

    if deterministic.status == SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE:
        return _build_result(
            scope_detail_id=scope_detail_id,
            status=SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED,
            deterministic=deterministic,
            semantic_discovery_status=SCOPE_QUANTITY_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
            deterministic_quantities=deterministic_quantities,
            semantic_supplements=(),
            duplicate_semantic_candidates=(),
            conflict_semantic_candidates=(),
            semantic_provider_metadata=None,
            diagnostics=tuple(diagnostics),
            errors=tuple(errors),
        )

    if semantic_provider is None:
        return _build_result(
            scope_detail_id=scope_detail_id,
            status=SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY,
            deterministic=deterministic,
            semantic_discovery_status=SCOPE_QUANTITY_INTEGRATION_SEMANTIC_STATUS_SKIPPED,
            deterministic_quantities=deterministic_quantities,
            semantic_supplements=(),
            duplicate_semantic_candidates=(),
            conflict_semantic_candidates=(),
            semantic_provider_metadata=None,
            diagnostics=tuple(diagnostics),
            errors=tuple(errors),
        )

    provider_metadata = ScopeQuantityIntegrationProviderMetadata(
        provider_name=getattr(semantic_provider, "provider_name", None),
        provider_version=getattr(semantic_provider, "provider_version", None),
        contract_version=getattr(semantic_provider, "contract_version", None),
    )

    try:
        fragment = _build_semantic_fragment(db, scope_detail_id=scope_detail_id)
    except ValueError as exc:
        errors.append(str(exc))
        diagnostics.append(str(exc))
        return _build_result(
            scope_detail_id=scope_detail_id,
            status=SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_INVALID,
            deterministic=deterministic,
            semantic_discovery_status=SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            deterministic_quantities=deterministic_quantities,
            semantic_supplements=(),
            duplicate_semantic_candidates=(),
            conflict_semantic_candidates=(),
            semantic_provider_metadata=provider_metadata,
            diagnostics=tuple(diagnostics),
            errors=tuple(errors),
        )

    discover = semantic_discoverer or _default_semantic_discoverer
    semantic = discover(fragment, semantic_provider)
    diagnostics.extend(semantic.errors)
    errors.extend(semantic.errors)

    provider_metadata = ScopeQuantityIntegrationProviderMetadata(
        provider_name=semantic.provider_name or provider_metadata.provider_name,
        provider_version=semantic.provider_version or provider_metadata.provider_version,
        contract_version=semantic.contract_version or provider_metadata.contract_version,
    )

    if semantic.status != SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED:
        status = _integration_status_for_non_discovered(
            semantic_status=semantic.status,
            deterministic_count=len(deterministic_quantities),
        )
        return _build_result(
            scope_detail_id=scope_detail_id,
            status=status,
            deterministic=deterministic,
            semantic_discovery_status=semantic.status,
            deterministic_quantities=deterministic_quantities,
            semantic_supplements=(),
            duplicate_semantic_candidates=(),
            conflict_semantic_candidates=(),
            semantic_provider_metadata=provider_metadata,
            diagnostics=tuple(diagnostics),
            errors=tuple(errors),
        )

    supplements, duplicates, conflicts = _merge_semantic_candidates(
        deterministic_quantities=deterministic_quantities,
        semantic_candidates=semantic.candidates,
    )

    if supplements or conflicts:
        integrated_status = (
            SCOPE_QUANTITY_INTEGRATION_STATUS_INTEGRATED
            if deterministic_quantities
            else SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_ONLY
        )
    else:
        integrated_status = SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY

    return _build_result(
        scope_detail_id=scope_detail_id,
        status=integrated_status,
        deterministic=deterministic,
        semantic_discovery_status=semantic.status,
        deterministic_quantities=deterministic_quantities,
        semantic_supplements=supplements,
        duplicate_semantic_candidates=duplicates,
        conflict_semantic_candidates=conflicts,
        semantic_provider_metadata=provider_metadata,
        diagnostics=tuple(diagnostics),
        errors=tuple(errors),
    )


def _default_semantic_discoverer(
    fragment: ScopeQuantitySemanticFragment,
    provider: ScopeQuantitySemanticDiscoveryProvider,
) -> ScopeQuantitySemanticDiscoveryResult:
    return discover_scope_quantities(fragment, providers=(provider,))


def _integration_status_for_non_discovered(*, semantic_status: str, deterministic_count: int) -> str:
    if semantic_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES:
        return SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
    if semantic_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED:
        return (
            SCOPE_QUANTITY_INTEGRATION_STATUS_DETERMINISTIC_ONLY
            if deterministic_count > 0
            else SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_UNAVAILABLE
        )
    if semantic_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED:
        return SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED
    if semantic_status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT:
        return SCOPE_QUANTITY_INTEGRATION_STATUS_SEMANTIC_INVALID
    return SCOPE_QUANTITY_INTEGRATION_STATUS_REVIEW_REQUIRED


def _merge_semantic_candidates(
    *,
    deterministic_quantities: tuple[TenderScopeQuantity, ...],
    semantic_candidates: tuple[ScopeQuantityCandidate, ...],
) -> tuple[
    tuple[ScopeQuantityCandidate, ...],
    tuple[ScopeQuantityDuplicateSemanticCandidate, ...],
    tuple[ScopeQuantityConflictSemanticCandidate, ...],
]:
    deterministic_by_fingerprint: dict[str, TenderScopeQuantity] = {}
    deterministic_by_identity: dict[tuple[str, str, str, str], list[TenderScopeQuantity]] = {}

    for row in deterministic_quantities:
        deterministic_by_fingerprint[row.semantic_fingerprint] = row
        identity = _quantity_identity_key(
            quantity_raw=row.quantity_raw,
            unit_raw=row.unit_raw,
            measure_kind=row.measure_kind,
            relation=row.relation,
        )
        deterministic_by_identity.setdefault(identity, []).append(row)

    supplements: list[ScopeQuantityCandidate] = []
    duplicates: list[ScopeQuantityDuplicateSemanticCandidate] = []
    conflicts: list[ScopeQuantityConflictSemanticCandidate] = []

    for candidate in semantic_candidates:
        fingerprint = compute_scope_quantity_fingerprint(candidate)
        duplicate = deterministic_by_fingerprint.get(fingerprint)
        if duplicate is not None:
            duplicates.append(
                ScopeQuantityDuplicateSemanticCandidate(
                    deterministic_quantity_id=duplicate.id,
                    reason=SCOPE_QUANTITY_INTEGRATION_REASON_DUPLICATE_DETERMINISTIC,
                    semantic_candidate=candidate,
                )
            )
            continue

        identity = _quantity_identity_key(
            quantity_raw=candidate.quantity_raw,
            unit_raw=candidate.unit_raw,
            measure_kind=candidate.measure_kind,
            relation=candidate.relation,
        )
        identity_matches = deterministic_by_identity.get(identity, ())

        conflict_row = _select_numeric_conflict(identity_matches, candidate)
        if conflict_row is not None:
            conflicts.append(
                ScopeQuantityConflictSemanticCandidate(
                    deterministic_quantity_id=conflict_row.id,
                    reason=SCOPE_QUANTITY_INTEGRATION_REASON_NORMALIZATION_CONFLICT,
                    deterministic_quantity_value=conflict_row.quantity_value,
                    deterministic_quantity_min=conflict_row.quantity_min,
                    deterministic_quantity_max=conflict_row.quantity_max,
                    semantic_candidate=candidate,
                )
            )
            continue

        supplements.append(candidate)

    return tuple(supplements), tuple(duplicates), tuple(conflicts)


def _select_numeric_conflict(
    deterministic_rows: Sequence[TenderScopeQuantity],
    semantic_candidate: ScopeQuantityCandidate,
) -> TenderScopeQuantity | None:
    semantic_numeric = (
        semantic_candidate.quantity_value,
        semantic_candidate.quantity_min,
        semantic_candidate.quantity_max,
    )
    for row in deterministic_rows:
        deterministic_numeric = (row.quantity_value, row.quantity_min, row.quantity_max)
        if deterministic_numeric != semantic_numeric:
            return row
    return None


def _quantity_identity_key(
    *,
    quantity_raw: str,
    unit_raw: str | None,
    measure_kind: str | None,
    relation: str | None,
) -> tuple[str, str, str, str]:
    return (
        _normalize_text(quantity_raw),
        _normalize_text(unit_raw or ""),
        _normalize_text(measure_kind or ""),
        _normalize_text(relation or "UNSPECIFIED"),
    )


def _build_semantic_fragment(
    db: Session,
    *,
    scope_detail_id: str,
) -> ScopeQuantitySemanticFragment:
    scope_detail = db.get(TenderScopeDetail, scope_detail_id)
    if scope_detail is None:
        raise ValueError("scope_detail_id does not exist")

    page = db.get(DocumentPage, scope_detail.document_page_id)
    if page is None:
        raise ValueError("scope_detail document page does not exist")

    source_text = str(scope_detail.source_excerpt or "").strip()
    if not source_text:
        raise ValueError("scope_detail.source_excerpt is required")

    return ScopeQuantitySemanticFragment(
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
        scope_detail_review_required=scope_detail.review_required,
    )


def _build_result(
    *,
    scope_detail_id: str,
    status: str,
    deterministic: ScopeQuantityMaterializationResult,
    semantic_discovery_status: str,
    deterministic_quantities: tuple[TenderScopeQuantity, ...],
    semantic_supplements: tuple[ScopeQuantityCandidate, ...],
    duplicate_semantic_candidates: tuple[ScopeQuantityDuplicateSemanticCandidate, ...],
    conflict_semantic_candidates: tuple[ScopeQuantityConflictSemanticCandidate, ...],
    semantic_provider_metadata: ScopeQuantityIntegrationProviderMetadata | None,
    diagnostics: tuple[str, ...],
    errors: tuple[str, ...],
) -> ScopeQuantityIntegrationResult:
    return ScopeQuantityIntegrationResult(
        scope_detail_id=scope_detail_id,
        status=status,
        deterministic_status=deterministic.status,
        semantic_discovery_status=semantic_discovery_status,
        deterministic_quantities=deterministic_quantities,
        semantic_supplements=semantic_supplements,
        duplicate_semantic_candidates=duplicate_semantic_candidates,
        conflict_semantic_candidates=conflict_semantic_candidates,
        semantic_provider_metadata=semantic_provider_metadata,
        diagnostics=diagnostics,
        errors=errors,
        deterministic_count=len(deterministic_quantities),
        semantic_supplement_count=len(semantic_supplements),
        duplicate_semantic_count=len(duplicate_semantic_candidates),
        conflict_semantic_count=len(conflict_semantic_candidates),
    )


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()
