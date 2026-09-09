from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TenderDocument, TenderSourceEffect
from app.source_effect_resolution import (
    DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED,
    DOCUMENT_EFFECTIVE_STATUS_REVOKED,
    DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED,
    TenderEffectiveSourceResolution,
    resolve_effective_sources_for_tender,
)
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
)

PARTIAL_TENDER_STATUS_RESOLVED = "RESOLVED"
PARTIAL_TENDER_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

PARTIAL_LOCATOR_STATUS_UNCHANGED = "UNCHANGED"
PARTIAL_LOCATOR_STATUS_MODIFIED = "MODIFIED"
PARTIAL_LOCATOR_STATUS_SUPERSEDED = "SUPERSEDED"
PARTIAL_LOCATOR_STATUS_REVOKED = "REVOKED"
PARTIAL_LOCATOR_STATUS_SUPPLEMENTED = "SUPPLEMENTED"
PARTIAL_LOCATOR_STATUS_CLARIFIED = "CLARIFIED"
PARTIAL_LOCATOR_STATUS_CORRECTED = "CORRECTED"
PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

DIAGNOSTIC_UNRESOLVED_PARTIAL_TARGET = "UNRESOLVED_PARTIAL_TARGET"
DIAGNOSTIC_UNRESOLVED_PARTIAL_LOCATOR = "UNRESOLVED_PARTIAL_LOCATOR"
DIAGNOSTIC_PARTIAL_REVIEW_REQUIRED_EFFECT = "PARTIAL_REVIEW_REQUIRED_EFFECT"
DIAGNOSTIC_MULTIPLE_PARTIAL_SUPERSEDING_SOURCES = "MULTIPLE_PARTIAL_SUPERSEDING_SOURCES"
DIAGNOSTIC_CONFLICTING_PARTIAL_TERMINAL_EFFECTS = "CONFLICTING_PARTIAL_TERMINAL_EFFECTS"
DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED = "PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED"
DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW = "PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW"
DIAGNOSTIC_MULTIPLE_COMPATIBLE_PARTIAL_OVERLAYS = "MULTIPLE_COMPATIBLE_PARTIAL_OVERLAYS"
DIAGNOSTIC_AFFECTED_DOCUMENT_TERMINAL_AT_DOCUMENT_LEVEL = "AFFECTED_DOCUMENT_TERMINAL_AT_DOCUMENT_LEVEL"

_NON_TERMINAL_TYPES = {
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
}


@dataclass(frozen=True, slots=True)
class PartialResolutionDiagnostic:
    code: str
    message: str
    effect_ids: tuple[str, ...] = ()
    affected_document_id: str | None = None
    locator_identity: str | None = None


@dataclass(frozen=True, slots=True)
class PartialLocatorResolution:
    affected_document_id: str
    affected_document_effective_status: str
    locator_identity: str
    locator_raw_variants: tuple[str, ...]
    status: str
    effective_source_document_id: str | None
    effect_ids: tuple[str, ...]
    blocking_effect_ids: tuple[str, ...]
    diagnostics: tuple[PartialResolutionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class TenderPartialSourceResolution:
    tender_id: str
    status: str
    locators: tuple[PartialLocatorResolution, ...]
    unresolved_effects: tuple[str, ...]
    conflicts: tuple[str, ...]
    diagnostics: tuple[PartialResolutionDiagnostic, ...]


@dataclass(slots=True)
class _MutableLocatorGroup:
    affected_document_id: str
    locator_identity: str
    affected_document_effective_status: str
    raw_variants: set[str] = field(default_factory=set)
    effect_ids: set[str] = field(default_factory=set)
    blocking_effect_ids: set[str] = field(default_factory=set)
    trusted_edges: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    diagnostics: list[PartialResolutionDiagnostic] = field(default_factory=list)

    def add_diagnostic(self, *, code: str, message: str, effect_ids: tuple[str, ...]) -> None:
        self.diagnostics.append(
            PartialResolutionDiagnostic(
                code=code,
                message=message,
                effect_ids=tuple(sorted(set(effect_ids))),
                affected_document_id=self.affected_document_id,
                locator_identity=self.locator_identity,
            )
        )


def resolve_partial_source_effects_for_tender(
    db: Session,
    *,
    tender_id: str,
    document_resolution: TenderEffectiveSourceResolution | None = None,
) -> TenderPartialSourceResolution:
    resolved_tender_id = str(tender_id or "").strip()
    if not resolved_tender_id:
        raise ValueError("tender_id is required")

    documents = list(
        db.execute(
            select(TenderDocument)
            .where(TenderDocument.tender_id == resolved_tender_id)
            .order_by(TenderDocument.id.asc())
        ).scalars()
    )
    document_ids = {doc.id for doc in documents}

    effective_document_resolution = document_resolution or resolve_effective_sources_for_tender(
        db,
        tender_id=resolved_tender_id,
    )
    document_status_by_id = {
        item.document_id: item.status
        for item in effective_document_resolution.documents
    }

    effects = list(
        db.execute(
            select(TenderSourceEffect)
            .where(TenderSourceEffect.tender_id == resolved_tender_id)
            .order_by(TenderSourceEffect.id.asc())
        ).scalars()
    )

    groups: dict[tuple[str, str], _MutableLocatorGroup] = {}
    unresolved_effects: set[str] = set()
    conflicts: set[str] = set()
    tender_diagnostics: list[PartialResolutionDiagnostic] = []

    for effect in effects:
        if effect.effect_scope != SOURCE_EFFECT_SCOPE_PARTIAL:
            continue

        if effect.affected_document_id is None or effect.affected_document_id not in document_ids:
            unresolved_effects.add(effect.id)
            tender_diagnostics.append(
                PartialResolutionDiagnostic(
                    code=DIAGNOSTIC_UNRESOLVED_PARTIAL_TARGET,
                    message="El efecto parcial no tiene documento afectado resoluble.",
                    effect_ids=(effect.id,),
                )
            )
            continue

        locator_identity = normalize_partial_locator_identity(effect.affected_locator_raw)
        if locator_identity is None:
            unresolved_effects.add(effect.id)
            tender_diagnostics.append(
                PartialResolutionDiagnostic(
                    code=DIAGNOSTIC_UNRESOLVED_PARTIAL_LOCATOR,
                    message="El efecto parcial no tiene locator textual representable de forma segura.",
                    effect_ids=(effect.id,),
                    affected_document_id=effect.affected_document_id,
                )
            )
            continue

        key = (effect.affected_document_id, locator_identity)
        group = groups.get(key)
        if group is None:
            group = _MutableLocatorGroup(
                affected_document_id=effect.affected_document_id,
                locator_identity=locator_identity,
                affected_document_effective_status=document_status_by_id.get(effect.affected_document_id, "UNKNOWN"),
            )
            groups[key] = group

        group.effect_ids.add(effect.id)
        raw_variant = normalize_partial_locator_variant(effect.affected_locator_raw)
        if raw_variant is not None:
            group.raw_variants.add(raw_variant)

        if effect.review_required:
            group.blocking_effect_ids.add(effect.id)
            group.add_diagnostic(
                code=DIAGNOSTIC_PARTIAL_REVIEW_REQUIRED_EFFECT,
                message="Existe un efecto parcial con revisión pendiente para este locator.",
                effect_ids=(effect.id,),
            )
            continue

        acting_status = document_status_by_id.get(effect.acting_document_id)
        if acting_status in {DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED, DOCUMENT_EFFECTIVE_STATUS_REVOKED}:
            group.blocking_effect_ids.add(effect.id)
            group.add_diagnostic(
                code=DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_NOT_RESOLVED,
                message="La fuente actuante no tiene estado documental resoluble para usarse como superposición efectiva.",
                effect_ids=(effect.id,),
            )
            continue

        if acting_status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED:
            group.blocking_effect_ids.add(effect.id)
            group.add_diagnostic(
                code=DIAGNOSTIC_PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW,
                message="La fuente actuante está sustituida a nivel documental y sus efectos parciales requieren revisión humana.",
                effect_ids=(effect.id,),
            )
            continue

        edge_key = (str(effect.effect_type), str(effect.acting_document_id))
        group.trusted_edges.setdefault(edge_key, set()).add(effect.id)

    locator_results: list[PartialLocatorResolution] = []
    for key in sorted(groups.keys()):
        group = groups[key]
        effect_ids = tuple(sorted(group.effect_ids))
        blocking_effect_ids = tuple(sorted(group.blocking_effect_ids))

        status = PARTIAL_LOCATOR_STATUS_UNCHANGED
        effective_source_document_id: str | None = None

        superseders: dict[str, tuple[str, ...]] = {}
        revokers: dict[str, tuple[str, ...]] = {}
        non_terminal_by_type: dict[str, set[str]] = {}

        for edge_key, supporting_ids in sorted(group.trusted_edges.items()):
            effect_type, acting_document_id = edge_key
            normalized_support = tuple(sorted(supporting_ids))
            if effect_type == SOURCE_EFFECT_TYPE_SUPERSEDES:
                superseders[acting_document_id] = normalized_support
                continue
            if effect_type == SOURCE_EFFECT_TYPE_REVOKES:
                revokers[acting_document_id] = normalized_support
                continue
            if effect_type in _NON_TERMINAL_TYPES:
                non_terminal_by_type.setdefault(effect_type, set()).update(normalized_support)

        if group.affected_document_effective_status in {DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED, DOCUMENT_EFFECTIVE_STATUS_REVOKED}:
            group.add_diagnostic(
                code=DIAGNOSTIC_AFFECTED_DOCUMENT_TERMINAL_AT_DOCUMENT_LEVEL,
                message="El documento afectado tiene estado documental terminal; este overlay parcial se conserva solo como trazabilidad.",
                effect_ids=effect_ids,
            )

        if len(superseders) > 1:
            status = PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
            conflict_ids = _flatten_effect_ids(superseders)
            group.add_diagnostic(
                code=DIAGNOSTIC_MULTIPLE_PARTIAL_SUPERSEDING_SOURCES,
                message="Existen múltiples fuentes que declaran sustituir el mismo locator parcial.",
                effect_ids=conflict_ids,
            )
            conflicts.update(conflict_ids)
        elif superseders and revokers:
            status = PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
            conflict_ids = tuple(sorted(set(_flatten_effect_ids(superseders) + _flatten_effect_ids(revokers))))
            group.add_diagnostic(
                code=DIAGNOSTIC_CONFLICTING_PARTIAL_TERMINAL_EFFECTS,
                message="Existen efectos terminales parciales conflictivos sobre el mismo locator.",
                effect_ids=conflict_ids,
            )
            conflicts.update(conflict_ids)
        elif superseders:
            acting_document_id = sorted(superseders.keys())[0]
            status = PARTIAL_LOCATOR_STATUS_SUPERSEDED
            effective_source_document_id = acting_document_id
        elif revokers:
            status = PARTIAL_LOCATOR_STATUS_REVOKED
            effective_source_document_id = None
        else:
            non_terminal_types = sorted(non_terminal_by_type.keys())
            if len(non_terminal_types) == 1:
                only = non_terminal_types[0]
                status = _non_terminal_status_mapping(only)
            elif len(non_terminal_types) > 1:
                status = PARTIAL_LOCATOR_STATUS_MODIFIED
                compatible_ids = tuple(sorted(set().union(*non_terminal_by_type.values())))
                group.add_diagnostic(
                    code=DIAGNOSTIC_MULTIPLE_COMPATIBLE_PARTIAL_OVERLAYS,
                    message="Existen múltiples overlays parciales no terminales compatibles en el mismo locator.",
                    effect_ids=compatible_ids,
                )
            else:
                status = PARTIAL_LOCATOR_STATUS_UNCHANGED

        if blocking_effect_ids:
            status = PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED
            effective_source_document_id = None

        locator_results.append(
            PartialLocatorResolution(
                affected_document_id=group.affected_document_id,
                affected_document_effective_status=group.affected_document_effective_status,
                locator_identity=group.locator_identity,
                locator_raw_variants=tuple(sorted(group.raw_variants)),
                status=status,
                effective_source_document_id=effective_source_document_id,
                effect_ids=effect_ids,
                blocking_effect_ids=blocking_effect_ids,
                diagnostics=tuple(group.diagnostics),
            )
        )

    has_review_locator = any(item.status == PARTIAL_LOCATOR_STATUS_REVIEW_REQUIRED for item in locator_results)
    tender_status = (
        PARTIAL_TENDER_STATUS_REVIEW_REQUIRED
        if (has_review_locator or unresolved_effects or conflicts)
        else PARTIAL_TENDER_STATUS_RESOLVED
    )

    return TenderPartialSourceResolution(
        tender_id=resolved_tender_id,
        status=tender_status,
        locators=tuple(locator_results),
        unresolved_effects=tuple(sorted(unresolved_effects)),
        conflicts=tuple(sorted(conflicts)),
        diagnostics=tuple(tender_diagnostics),
    )


def normalize_partial_locator_identity(raw_locator: str | None) -> str | None:
    if raw_locator is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(raw_locator))
    normalized = " ".join(normalized.strip().split())
    if not normalized:
        return None
    return normalized.casefold()


def normalize_partial_locator_variant(raw_locator: str | None) -> str | None:
    if raw_locator is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(raw_locator))
    normalized = " ".join(normalized.strip().split())
    return normalized or None


def _flatten_effect_ids(edges: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    all_ids: set[str] = set()
    for effect_ids in edges.values():
        all_ids.update(effect_ids)
    return tuple(sorted(all_ids))


def _non_terminal_status_mapping(effect_type: str) -> str:
    if effect_type == SOURCE_EFFECT_TYPE_AMENDS:
        return PARTIAL_LOCATOR_STATUS_MODIFIED
    if effect_type == SOURCE_EFFECT_TYPE_CORRECTS:
        return PARTIAL_LOCATOR_STATUS_CORRECTED
    if effect_type == SOURCE_EFFECT_TYPE_CLARIFIES:
        return PARTIAL_LOCATOR_STATUS_CLARIFIED
    if effect_type == SOURCE_EFFECT_TYPE_SUPPLEMENTS:
        return PARTIAL_LOCATOR_STATUS_SUPPLEMENTED
    return PARTIAL_LOCATOR_STATUS_MODIFIED
