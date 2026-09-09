from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementReview,
    TenderScopeAttribute,
    TenderScopeDetail,
    TenderScopeQuantity,
)
from app.source_effect_partial_resolution import (
    PARTIAL_LOCATOR_STATUS_CLARIFIED,
    PARTIAL_LOCATOR_STATUS_CORRECTED,
    PARTIAL_LOCATOR_STATUS_MODIFIED,
    PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED,
    PARTIAL_LOCATOR_STATUS_REVOKED,
    PARTIAL_LOCATOR_STATUS_SUPERSEDED,
    PARTIAL_LOCATOR_STATUS_SUPPLEMENTED,
    PARTIAL_LOCATOR_STATUS_UNCHANGED,
    PARTIAL_TENDER_STATUS_REVIEW_REQUIRED,
    TenderPartialSourceResolution,
    normalize_partial_locator_identity,
    resolve_partial_source_effects_for_tender,
)
from app.source_effect_resolution import (
    DOCUMENT_EFFECTIVE_STATUS_ACTIVE,
    DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS,
    DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
    DOCUMENT_EFFECTIVE_STATUS_REVOKED,
    DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED,
    TenderEffectiveSourceResolution,
    resolve_effective_sources_for_tender,
)

PROJECTION_STATUS_EFFECTIVE = "EFFECTIVE"
PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY = "EFFECTIVE_WITH_OVERLAY"
PROJECTION_STATUS_SUPERSEDED = "SUPERSEDED"
PROJECTION_STATUS_REVOKED = "REVOKED"
PROJECTION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
PROJECTION_STATUS_UNRESOLVED_SOURCE = "UNRESOLVED_SOURCE"

TENDER_PROJECTION_STATUS_RESOLVED = "RESOLVED"
TENDER_PROJECTION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

ENTITY_TYPE_REQUIREMENT = "REQUIREMENT"
ENTITY_TYPE_SCOPE_DETAIL = "SCOPE_DETAIL"
ENTITY_TYPE_SCOPE_ATTRIBUTE = "SCOPE_ATTRIBUTE"
ENTITY_TYPE_SCOPE_QUANTITY = "SCOPE_QUANTITY"

DIAGNOSTIC_FACT_REVIEW_REQUIRED = "FACT_REVIEW_REQUIRED"
DIAGNOSTIC_SOURCE_DOCUMENT_MISSING = "SOURCE_DOCUMENT_MISSING"
DIAGNOSTIC_SOURCE_DOCUMENT_REVIEW_REQUIRED = "SOURCE_DOCUMENT_REVIEW_REQUIRED"
DIAGNOSTIC_SOURCE_LOCATOR_REVIEW_REQUIRED = "SOURCE_LOCATOR_REVIEW_REQUIRED"
DIAGNOSTIC_SOURCE_LOCATOR_UNRESOLVED = "SOURCE_LOCATOR_UNRESOLVED"
DIAGNOSTIC_SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED = "SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED"
DIAGNOSTIC_PARENT_SCOPE_SUPERSEDED = "PARENT_SCOPE_SUPERSEDED"
DIAGNOSTIC_PARENT_SCOPE_REVOKED = "PARENT_SCOPE_REVOKED"
DIAGNOSTIC_PARENT_SCOPE_REVIEW_REQUIRED = "PARENT_SCOPE_REVIEW_REQUIRED"
DIAGNOSTIC_PARENT_SCOPE_UNRESOLVED_SOURCE = "PARENT_SCOPE_UNRESOLVED_SOURCE"
DIAGNOSTIC_PARENT_SCOPE_OVERLAY_APPLIED = "PARENT_SCOPE_OVERLAY_APPLIED"
DIAGNOSTIC_PARENT_CHILD_TERMINAL_STATUS_CONFLICT = "PARENT_CHILD_TERMINAL_STATUS_CONFLICT"


_NON_TERMINAL_PARTIAL_STATUSES = {
    PARTIAL_LOCATOR_STATUS_MODIFIED,
    PARTIAL_LOCATOR_STATUS_CORRECTED,
    PARTIAL_LOCATOR_STATUS_CLARIFIED,
    PARTIAL_LOCATOR_STATUS_SUPPLEMENTED,
}


@dataclass(frozen=True, slots=True)
class ProjectionDiagnostic:
    code: str
    message: str
    effect_ids: tuple[str, ...] = ()
    entity_type: str | None = None
    entity_id: str | None = None
    source_document_id: str | None = None
    source_locator: str | None = None
    parent_entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class EffectiveEntityProjection:
    entity_type: str
    entity_id: str
    source_document_id: str | None
    document_page_id: str | None
    source_locator: str | None
    status: str
    document_effective_status: str | None
    partial_locator_status: str | None
    supporting_effect_ids: tuple[str, ...]
    blocking_effect_ids: tuple[str, ...]
    diagnostics: tuple[ProjectionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class TenderEffectiveProjection:
    tender_id: str
    status: str
    requirements: tuple[EffectiveEntityProjection, ...]
    scope_details: tuple[EffectiveEntityProjection, ...]
    scope_attributes: tuple[EffectiveEntityProjection, ...]
    scope_quantities: tuple[EffectiveEntityProjection, ...]
    unresolved_effects: tuple[str, ...]
    conflicts: tuple[str, ...]
    diagnostics: tuple[ProjectionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _SourceDecision:
    status: str
    document_effective_status: str | None
    partial_locator_status: str | None
    supporting_effect_ids: tuple[str, ...]
    blocking_effect_ids: tuple[str, ...]
    diagnostics: tuple[ProjectionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _ParentChildCombination:
    status: str
    diagnostics: tuple[ProjectionDiagnostic, ...] = ()
    include_parent_traceability: bool = False


def project_effective_sources_for_tender(
    db: Session,
    *,
    tender_id: str,
    document_resolution: TenderEffectiveSourceResolution | None = None,
    partial_resolution: TenderPartialSourceResolution | None = None,
) -> TenderEffectiveProjection:
    resolved_tender_id = str(tender_id or "").strip()
    if not resolved_tender_id:
        raise ValueError("tender_id is required")

    effective_document_resolution = document_resolution or resolve_effective_sources_for_tender(
        db,
        tender_id=resolved_tender_id,
    )
    effective_partial_resolution = partial_resolution or resolve_partial_source_effects_for_tender(
        db,
        tender_id=resolved_tender_id,
        document_resolution=effective_document_resolution,
    )

    document_status_by_id = {
        item.document_id: item.status
        for item in effective_document_resolution.documents
    }
    partial_by_key = {
        (item.affected_document_id, item.locator_identity): item
        for item in effective_partial_resolution.locators
    }
    partial_docs = {item.affected_document_id for item in effective_partial_resolution.locators}

    requirements = _project_requirements(
        db,
        tender_id=resolved_tender_id,
        document_status_by_id=document_status_by_id,
        partial_by_key=partial_by_key,
        partial_docs=partial_docs,
    )

    scope_details = _project_scope_details(
        db,
        tender_id=resolved_tender_id,
        document_status_by_id=document_status_by_id,
        partial_by_key=partial_by_key,
        partial_docs=partial_docs,
    )
    scope_detail_by_id = {item.entity_id: item for item in scope_details}

    scope_attributes = _project_scope_attributes(
        db,
        tender_id=resolved_tender_id,
        scope_detail_by_id=scope_detail_by_id,
        document_status_by_id=document_status_by_id,
        partial_by_key=partial_by_key,
        partial_docs=partial_docs,
    )

    scope_quantities = _project_scope_quantities(
        db,
        tender_id=resolved_tender_id,
        scope_detail_by_id=scope_detail_by_id,
        document_status_by_id=document_status_by_id,
        partial_by_key=partial_by_key,
        partial_docs=partial_docs,
    )

    top_level_diagnostics: list[ProjectionDiagnostic] = []
    for row in effective_document_resolution.diagnostics:
        top_level_diagnostics.append(
            ProjectionDiagnostic(
                code=row.code,
                message=row.message,
                effect_ids=row.effect_ids,
                source_document_id=row.document_id,
            )
        )
    for row in effective_partial_resolution.diagnostics:
        top_level_diagnostics.append(
            ProjectionDiagnostic(
                code=row.code,
                message=row.message,
                effect_ids=row.effect_ids,
                source_document_id=row.affected_document_id,
                source_locator=row.locator_identity,
            )
        )

    has_entity_review = any(
        item.status in {PROJECTION_STATUS_REVIEW_REQUIRED, PROJECTION_STATUS_UNRESOLVED_SOURCE}
        for item in requirements + scope_details + scope_attributes + scope_quantities
    )

    tender_status = (
        TENDER_PROJECTION_STATUS_REVIEW_REQUIRED
        if (
            effective_document_resolution.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
            or effective_partial_resolution.status == PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
            or effective_document_resolution.unresolved_effects
            or effective_document_resolution.conflicts
            or effective_partial_resolution.unresolved_effects
            or effective_partial_resolution.conflicts
            or has_entity_review
        )
        else TENDER_PROJECTION_STATUS_RESOLVED
    )

    return TenderEffectiveProjection(
        tender_id=resolved_tender_id,
        status=tender_status,
        requirements=tuple(requirements),
        scope_details=tuple(scope_details),
        scope_attributes=tuple(scope_attributes),
        scope_quantities=tuple(scope_quantities),
        unresolved_effects=tuple(sorted(set(effective_document_resolution.unresolved_effects) | set(effective_partial_resolution.unresolved_effects))),
        conflicts=tuple(sorted(set(effective_document_resolution.conflicts) | set(effective_partial_resolution.conflicts))),
        diagnostics=tuple(top_level_diagnostics),
    )


def _project_requirements(
    db: Session,
    *,
    tender_id: str,
    document_status_by_id: dict[str, str],
    partial_by_key: dict[tuple[str, str], object],
    partial_docs: set[str],
) -> list[EffectiveEntityProjection]:
    rows = list(
        db.execute(
            select(Requirement)
            .where(Requirement.tender_id == tender_id)
            .options(
                selectinload(Requirement.primary_candidate),
                selectinload(Requirement.review),
                selectinload(Requirement.candidate_links).selectinload(RequirementCandidateLink.candidate),
            )
            .order_by(Requirement.id.asc())
        ).scalars()
    )

    projections: list[EffectiveEntityProjection] = []
    for row in rows:
        source_candidate = _pick_requirement_source_candidate(row)
        source_document_id = source_candidate.source_document_id if source_candidate is not None else None
        document_page_id = source_candidate.document_page_id if source_candidate is not None else None
        source_locator = _extract_requirement_source_locator(source_candidate)

        fact_review_required = bool(row.normalization_status == "REVIEW_REQUIRED")
        if row.review is not None and row.review.review_status in {"PENDING", "NEEDS_REVIEW", "REJECTED"}:
            fact_review_required = True

        source_decision = _resolve_source_decision(
            source_document_id=source_document_id,
            source_locator=source_locator,
            fact_review_required=fact_review_required,
            document_status_by_id=document_status_by_id,
            partial_by_key=partial_by_key,
            partial_docs=partial_docs,
            entity_type=ENTITY_TYPE_REQUIREMENT,
            entity_id=row.id,
        )

        projections.append(
            EffectiveEntityProjection(
                entity_type=ENTITY_TYPE_REQUIREMENT,
                entity_id=row.id,
                source_document_id=source_document_id,
                document_page_id=document_page_id,
                source_locator=source_locator,
                status=source_decision.status,
                document_effective_status=source_decision.document_effective_status,
                partial_locator_status=source_decision.partial_locator_status,
                supporting_effect_ids=source_decision.supporting_effect_ids,
                blocking_effect_ids=source_decision.blocking_effect_ids,
                diagnostics=source_decision.diagnostics,
            )
        )

    return projections


def _project_scope_details(
    db: Session,
    *,
    tender_id: str,
    document_status_by_id: dict[str, str],
    partial_by_key: dict[tuple[str, str], object],
    partial_docs: set[str],
) -> list[EffectiveEntityProjection]:
    rows = list(
        db.execute(
            select(TenderScopeDetail)
            .where(TenderScopeDetail.tender_id == tender_id)
            .order_by(TenderScopeDetail.id.asc())
        ).scalars()
    )

    projections: list[EffectiveEntityProjection] = []
    for row in rows:
        source_decision = _resolve_source_decision(
            source_document_id=row.source_document_id,
            source_locator=row.source_locator,
            fact_review_required=bool(row.review_required),
            document_status_by_id=document_status_by_id,
            partial_by_key=partial_by_key,
            partial_docs=partial_docs,
            entity_type=ENTITY_TYPE_SCOPE_DETAIL,
            entity_id=row.id,
        )

        projections.append(
            EffectiveEntityProjection(
                entity_type=ENTITY_TYPE_SCOPE_DETAIL,
                entity_id=row.id,
                source_document_id=row.source_document_id,
                document_page_id=row.document_page_id,
                source_locator=row.source_locator,
                status=source_decision.status,
                document_effective_status=source_decision.document_effective_status,
                partial_locator_status=source_decision.partial_locator_status,
                supporting_effect_ids=source_decision.supporting_effect_ids,
                blocking_effect_ids=source_decision.blocking_effect_ids,
                diagnostics=source_decision.diagnostics,
            )
        )

    return projections


def _project_scope_attributes(
    db: Session,
    *,
    tender_id: str,
    scope_detail_by_id: dict[str, EffectiveEntityProjection],
    document_status_by_id: dict[str, str],
    partial_by_key: dict[tuple[str, str], object],
    partial_docs: set[str],
) -> list[EffectiveEntityProjection]:
    rows = list(
        db.execute(
            select(TenderScopeAttribute)
            .where(TenderScopeAttribute.tender_id == tender_id)
            .order_by(TenderScopeAttribute.id.asc())
        ).scalars()
    )

    projections: list[EffectiveEntityProjection] = []
    for row in rows:
        source_decision = _resolve_source_decision(
            source_document_id=row.source_document_id,
            source_locator=row.source_locator,
            fact_review_required=bool(row.review_required),
            document_status_by_id=document_status_by_id,
            partial_by_key=partial_by_key,
            partial_docs=partial_docs,
            entity_type=ENTITY_TYPE_SCOPE_ATTRIBUTE,
            entity_id=row.id,
        )

        parent = scope_detail_by_id.get(row.scope_detail_id)
        if parent is None:
            final_status = PROJECTION_STATUS_UNRESOLVED_SOURCE
            parent_diagnostics = (
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_SCOPE_UNRESOLVED_SOURCE,
                    message="El atributo no tiene un ScopeDetail proyectable.",
                    entity_type=ENTITY_TYPE_SCOPE_ATTRIBUTE,
                    entity_id=row.id,
                    parent_entity_id=row.scope_detail_id,
                ),
            )
            include_parent_traceability = False
        else:
            combination = _combine_parent_child_status(
                parent=parent,
                child_status=source_decision.status,
                child_entity_type=ENTITY_TYPE_SCOPE_ATTRIBUTE,
                child_entity_id=row.id,
            )
            final_status = combination.status
            parent_diagnostics = combination.diagnostics
            include_parent_traceability = combination.include_parent_traceability

        supporting_effect_ids = set(source_decision.supporting_effect_ids)
        blocking_effect_ids = set(source_decision.blocking_effect_ids)
        combined_diagnostics = list(source_decision.diagnostics)
        combined_diagnostics.extend(parent_diagnostics)
        if parent is not None and include_parent_traceability:
            supporting_effect_ids.update(parent.supporting_effect_ids)
            blocking_effect_ids.update(parent.blocking_effect_ids)
            combined_diagnostics.extend(parent.diagnostics)

        projections.append(
            EffectiveEntityProjection(
                entity_type=ENTITY_TYPE_SCOPE_ATTRIBUTE,
                entity_id=row.id,
                source_document_id=row.source_document_id,
                document_page_id=row.document_page_id,
                source_locator=row.source_locator,
                status=final_status,
                document_effective_status=source_decision.document_effective_status,
                partial_locator_status=source_decision.partial_locator_status,
                supporting_effect_ids=tuple(sorted(supporting_effect_ids)),
                blocking_effect_ids=tuple(sorted(blocking_effect_ids)),
                diagnostics=tuple(combined_diagnostics),
            )
        )

    return projections


def _project_scope_quantities(
    db: Session,
    *,
    tender_id: str,
    scope_detail_by_id: dict[str, EffectiveEntityProjection],
    document_status_by_id: dict[str, str],
    partial_by_key: dict[tuple[str, str], object],
    partial_docs: set[str],
) -> list[EffectiveEntityProjection]:
    rows = list(
        db.execute(
            select(TenderScopeQuantity)
            .where(TenderScopeQuantity.tender_id == tender_id)
            .order_by(TenderScopeQuantity.id.asc())
        ).scalars()
    )

    projections: list[EffectiveEntityProjection] = []
    for row in rows:
        source_decision = _resolve_source_decision(
            source_document_id=row.source_document_id,
            source_locator=row.source_locator,
            fact_review_required=bool(row.review_required),
            document_status_by_id=document_status_by_id,
            partial_by_key=partial_by_key,
            partial_docs=partial_docs,
            entity_type=ENTITY_TYPE_SCOPE_QUANTITY,
            entity_id=row.id,
        )

        parent = scope_detail_by_id.get(row.scope_detail_id)
        if parent is None:
            final_status = PROJECTION_STATUS_UNRESOLVED_SOURCE
            parent_diagnostics = (
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_SCOPE_UNRESOLVED_SOURCE,
                    message="La cantidad no tiene un ScopeDetail proyectable.",
                    entity_type=ENTITY_TYPE_SCOPE_QUANTITY,
                    entity_id=row.id,
                    parent_entity_id=row.scope_detail_id,
                ),
            )
            include_parent_traceability = False
        else:
            combination = _combine_parent_child_status(
                parent=parent,
                child_status=source_decision.status,
                child_entity_type=ENTITY_TYPE_SCOPE_QUANTITY,
                child_entity_id=row.id,
            )
            final_status = combination.status
            parent_diagnostics = combination.diagnostics
            include_parent_traceability = combination.include_parent_traceability

        supporting_effect_ids = set(source_decision.supporting_effect_ids)
        blocking_effect_ids = set(source_decision.blocking_effect_ids)
        combined_diagnostics = list(source_decision.diagnostics)
        combined_diagnostics.extend(parent_diagnostics)
        if parent is not None and include_parent_traceability:
            supporting_effect_ids.update(parent.supporting_effect_ids)
            blocking_effect_ids.update(parent.blocking_effect_ids)
            combined_diagnostics.extend(parent.diagnostics)

        projections.append(
            EffectiveEntityProjection(
                entity_type=ENTITY_TYPE_SCOPE_QUANTITY,
                entity_id=row.id,
                source_document_id=row.source_document_id,
                document_page_id=row.document_page_id,
                source_locator=row.source_locator,
                status=final_status,
                document_effective_status=source_decision.document_effective_status,
                partial_locator_status=source_decision.partial_locator_status,
                supporting_effect_ids=tuple(sorted(supporting_effect_ids)),
                blocking_effect_ids=tuple(sorted(blocking_effect_ids)),
                diagnostics=tuple(combined_diagnostics),
            )
        )

    return projections


def _pick_requirement_source_candidate(requirement: Requirement) -> RequirementCandidate | None:
    links = sorted(
        requirement.candidate_links,
        key=lambda row: (
            0 if row.is_primary_source else 1,
            row.id,
        ),
    )
    for link in links:
        if link.candidate is not None:
            return link.candidate

    if requirement.primary_candidate is not None:
        return requirement.primary_candidate

    return None


def _extract_requirement_source_locator(candidate: RequirementCandidate | None) -> str | None:
    if candidate is None:
        return None

    direct = getattr(candidate, "source_locator", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    if candidate.source_excerpt and str(candidate.source_excerpt).strip():
        return str(candidate.source_excerpt).strip()

    return None


def _resolve_source_decision(
    *,
    source_document_id: str | None,
    source_locator: str | None,
    fact_review_required: bool,
    document_status_by_id: dict[str, str],
    partial_by_key: dict[tuple[str, str], object],
    partial_docs: set[str],
    entity_type: str,
    entity_id: str,
) -> _SourceDecision:
    diagnostics: list[ProjectionDiagnostic] = []

    if not source_document_id:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_DOCUMENT_MISSING,
                message="La entidad no tiene source_document_id resoluble.",
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
            document_effective_status=None,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    document_effective_status = document_status_by_id.get(source_document_id)
    if document_effective_status is None:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_DOCUMENT_MISSING,
                message="No existe resolución documental para el source_document_id de la entidad.",
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
            document_effective_status=None,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if document_effective_status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_SUPERSEDED,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if document_effective_status == DOCUMENT_EFFECTIVE_STATUS_REVOKED:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_REVOKED,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if document_effective_status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_DOCUMENT_REVIEW_REQUIRED,
                message="El documento fuente requiere revisión humana antes de aplicar esta entidad.",
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_REVIEW_REQUIRED,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if document_effective_status not in {DOCUMENT_EFFECTIVE_STATUS_ACTIVE, DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS}:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_DOCUMENT_MISSING,
                message="La resolución documental devolvió un estado no soportado para proyección.",
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if source_locator is None or not str(source_locator).strip():
        if source_document_id in partial_docs:
            diagnostics.append(
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED,
                    message="Existen overlays parciales en el documento fuente pero la entidad no tiene source_locator para evaluar coincidencia exacta.",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    source_document_id=source_document_id,
                )
            )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_EFFECTIVE,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    locator_identity = normalize_partial_locator_identity(str(source_locator))
    if locator_identity is None:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_LOCATOR_UNRESOLVED,
                message="El source_locator de la entidad no es representable con normalización conservadora.",
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
                source_locator=source_locator,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
            document_effective_status=document_effective_status,
            partial_locator_status=None,
            supporting_effect_ids=(),
            blocking_effect_ids=(),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    partial = partial_by_key.get((source_document_id, locator_identity))
    if partial is None or partial.status == PARTIAL_LOCATOR_STATUS_UNCHANGED:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_EFFECTIVE,
            document_effective_status=document_effective_status,
            partial_locator_status=PARTIAL_LOCATOR_STATUS_UNCHANGED if partial is not None else None,
            supporting_effect_ids=tuple(partial.effect_ids) if partial is not None else (),
            blocking_effect_ids=tuple(partial.blocking_effect_ids) if partial is not None else (),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if partial.status == PARTIAL_LOCATOR_STATUS_SUPERSEDED:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_SUPERSEDED,
            document_effective_status=document_effective_status,
            partial_locator_status=partial.status,
            supporting_effect_ids=tuple(partial.effect_ids),
            blocking_effect_ids=tuple(partial.blocking_effect_ids),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if partial.status == PARTIAL_LOCATOR_STATUS_REVOKED:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_REVOKED,
            document_effective_status=document_effective_status,
            partial_locator_status=partial.status,
            supporting_effect_ids=tuple(partial.effect_ids),
            blocking_effect_ids=tuple(partial.blocking_effect_ids),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if partial.status in _NON_TERMINAL_PARTIAL_STATUSES:
        return _finalize_source_decision(
            status=PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY,
            document_effective_status=document_effective_status,
            partial_locator_status=partial.status,
            supporting_effect_ids=tuple(partial.effect_ids),
            blocking_effect_ids=tuple(partial.blocking_effect_ids),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    if partial.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED:
        diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_SOURCE_LOCATOR_REVIEW_REQUIRED,
                message="El locator fuente tiene conflicto o bloqueo parcial y requiere revisión humana.",
                effect_ids=tuple(partial.blocking_effect_ids),
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
                source_locator=source_locator,
            )
        )
        return _finalize_source_decision(
            status=PROJECTION_STATUS_REVIEW_REQUIRED,
            document_effective_status=document_effective_status,
            partial_locator_status=partial.status,
            supporting_effect_ids=tuple(partial.effect_ids),
            blocking_effect_ids=tuple(partial.blocking_effect_ids),
            diagnostics=diagnostics,
            fact_review_required=fact_review_required,
            entity_type=entity_type,
            entity_id=entity_id,
            source_document_id=source_document_id,
            source_locator=source_locator,
        )

    return _finalize_source_decision(
        status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
        document_effective_status=document_effective_status,
        partial_locator_status=partial.status,
        supporting_effect_ids=tuple(partial.effect_ids),
        blocking_effect_ids=tuple(partial.blocking_effect_ids),
        diagnostics=diagnostics,
        fact_review_required=fact_review_required,
        entity_type=entity_type,
        entity_id=entity_id,
        source_document_id=source_document_id,
        source_locator=source_locator,
    )


def _finalize_source_decision(
    *,
    status: str,
    document_effective_status: str | None,
    partial_locator_status: str | None,
    supporting_effect_ids: tuple[str, ...],
    blocking_effect_ids: tuple[str, ...],
    diagnostics: list[ProjectionDiagnostic],
    fact_review_required: bool,
    entity_type: str,
    entity_id: str,
    source_document_id: str | None,
    source_locator: str | None,
) -> _SourceDecision:
    final_status = status
    final_diagnostics = list(diagnostics)

    if fact_review_required:
        final_status = PROJECTION_STATUS_REVIEW_REQUIRED
        final_diagnostics.append(
            ProjectionDiagnostic(
                code=DIAGNOSTIC_FACT_REVIEW_REQUIRED,
                message="La entidad ya está marcada para revisión humana en su propio contrato persistido.",
                entity_type=entity_type,
                entity_id=entity_id,
                source_document_id=source_document_id,
                source_locator=source_locator,
            )
        )

    return _SourceDecision(
        status=final_status,
        document_effective_status=document_effective_status,
        partial_locator_status=partial_locator_status,
        supporting_effect_ids=tuple(sorted(set(supporting_effect_ids))),
        blocking_effect_ids=tuple(sorted(set(blocking_effect_ids))),
        diagnostics=tuple(final_diagnostics),
    )


def _combine_parent_child_status(
    *,
    parent: EffectiveEntityProjection,
    child_status: str,
    child_entity_type: str,
    child_entity_id: str,
) -> _ParentChildCombination:
    parent_status = parent.status

    # Parent review blocks any automatic child terminal/effective interpretation.
    if parent_status == PROJECTION_STATUS_REVIEW_REQUIRED:
        if child_status != PROJECTION_STATUS_REVIEW_REQUIRED:
            return _ParentChildCombination(
                status=PROJECTION_STATUS_REVIEW_REQUIRED,
                diagnostics=(
                    ProjectionDiagnostic(
                        code=DIAGNOSTIC_PARENT_SCOPE_REVIEW_REQUIRED,
                        message="El ScopeDetail padre requiere revisión y bloquea la efectividad automática del hijo.",
                        entity_type=child_entity_type,
                        entity_id=child_entity_id,
                        parent_entity_id=parent.entity_id,
                    ),
                ),
                include_parent_traceability=True,
            )
        return _ParentChildCombination(status=PROJECTION_STATUS_REVIEW_REQUIRED)

    # Child direct unresolved provenance cannot be fixed by parent.
    if child_status == PROJECTION_STATUS_UNRESOLVED_SOURCE:
        return _ParentChildCombination(status=PROJECTION_STATUS_UNRESOLVED_SOURCE)

    # Parent unresolved source blocks a clean child only when child is otherwise effective.
    if parent_status == PROJECTION_STATUS_UNRESOLVED_SOURCE:
        if child_status in {PROJECTION_STATUS_EFFECTIVE, PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY}:
            return _ParentChildCombination(
                status=PROJECTION_STATUS_UNRESOLVED_SOURCE,
                diagnostics=(
                    ProjectionDiagnostic(
                        code=DIAGNOSTIC_PARENT_SCOPE_UNRESOLVED_SOURCE,
                        message="El ScopeDetail padre no tiene fuente resoluble y el hijo no puede quedar efectivo.",
                        entity_type=child_entity_type,
                        entity_id=child_entity_id,
                        parent_entity_id=parent.entity_id,
                    ),
                ),
                include_parent_traceability=True,
            )
        return _ParentChildCombination(status=child_status)

    terminal_statuses = {PROJECTION_STATUS_SUPERSEDED, PROJECTION_STATUS_REVOKED}
    effective_statuses = {PROJECTION_STATUS_EFFECTIVE, PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY}

    if parent_status in terminal_statuses and child_status in terminal_statuses:
        if parent_status == child_status:
            return _ParentChildCombination(status=child_status, include_parent_traceability=True)
        return _ParentChildCombination(
            status=PROJECTION_STATUS_REVIEW_REQUIRED,
            diagnostics=(
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_CHILD_TERMINAL_STATUS_CONFLICT,
                    message=(
                        "El ScopeDetail padre y la fuente directa del hijo tienen estados terminales "
                        f"conflictivos ({parent_status} vs {child_status}) y requieren revisión humana."
                    ),
                    entity_type=child_entity_type,
                    entity_id=child_entity_id,
                    parent_entity_id=parent.entity_id,
                ),
            ),
            include_parent_traceability=True,
        )

    if parent_status == PROJECTION_STATUS_SUPERSEDED and child_status in effective_statuses:
        return _ParentChildCombination(
            status=PROJECTION_STATUS_SUPERSEDED,
            diagnostics=(
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_SCOPE_SUPERSEDED,
                    message="El ScopeDetail padre está sustituido y el hijo no puede quedar efectivo.",
                    entity_type=child_entity_type,
                    entity_id=child_entity_id,
                    parent_entity_id=parent.entity_id,
                ),
            ),
            include_parent_traceability=True,
        )

    if parent_status == PROJECTION_STATUS_REVOKED and child_status in effective_statuses:
        return _ParentChildCombination(
            status=PROJECTION_STATUS_REVOKED,
            diagnostics=(
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_SCOPE_REVOKED,
                    message="El ScopeDetail padre está revocado y el hijo no puede quedar efectivo.",
                    entity_type=child_entity_type,
                    entity_id=child_entity_id,
                    parent_entity_id=parent.entity_id,
                ),
            ),
            include_parent_traceability=True,
        )

    if parent_status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY and child_status == PROJECTION_STATUS_EFFECTIVE:
        return _ParentChildCombination(
            status=PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY,
            diagnostics=(
                ProjectionDiagnostic(
                    code=DIAGNOSTIC_PARENT_SCOPE_OVERLAY_APPLIED,
                    message="El ScopeDetail padre tiene overlay aplicable que también condiciona al hijo.",
                    entity_type=child_entity_type,
                    entity_id=child_entity_id,
                    parent_entity_id=parent.entity_id,
                ),
            ),
            include_parent_traceability=True,
        )

    if parent_status == PROJECTION_STATUS_EFFECTIVE and child_status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY:
        return _ParentChildCombination(status=PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY)

    if parent_status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY and child_status == PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY:
        return _ParentChildCombination(status=PROJECTION_STATUS_EFFECTIVE_WITH_OVERLAY, include_parent_traceability=True)

    return _ParentChildCombination(status=child_status)
