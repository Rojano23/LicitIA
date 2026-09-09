from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TenderDocument, TenderSourceEffect
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
)

TENDER_RESOLUTION_STATUS_RESOLVED = "RESOLVED"
TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

DOCUMENT_EFFECTIVE_STATUS_ACTIVE = "ACTIVE"
DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS = "ACTIVE_WITH_EFFECTS"
DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED = "SUPERSEDED"
DOCUMENT_EFFECTIVE_STATUS_REVOKED = "REVOKED"
DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

TERMINAL_EFFECT_TYPES = {
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_REVOKES,
}

NON_TERMINAL_EFFECT_TYPES = {
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
}

DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES = "MULTIPLE_SUPERSEDING_SOURCES"
DIAGNOSTIC_CONFLICTING_TERMINAL_EFFECTS = "CONFLICTING_TERMINAL_EFFECTS"
DIAGNOSTIC_SUPERSESSION_CYCLE = "SUPERSESSION_CYCLE"
DIAGNOSTIC_SELF_SOURCE_EFFECT = "SELF_SOURCE_EFFECT"
DIAGNOSTIC_REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION = "REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION"
DIAGNOSTIC_UNRESOLVED_REVIEW_EFFECT_TARGET = "UNRESOLVED_REVIEW_EFFECT_TARGET"
DIAGNOSTIC_UNRESOLVED_TARGET_FOR_TRUSTED_EFFECT = "UNRESOLVED_TARGET_FOR_TRUSTED_EFFECT"
DIAGNOSTIC_UNRESOLVED_SCOPE_TARGET_BLOCKS_AUTOMATION = "UNRESOLVED_SCOPE_TARGET_BLOCKS_AUTOMATION"
DIAGNOSTIC_UNRESOLVED_SCOPE_UNRESOLVED_TARGET = "UNRESOLVED_SCOPE_UNRESOLVED_TARGET"
DIAGNOSTIC_ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW = "ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW"
DIAGNOSTIC_REVOKED_ACTING_SOURCE_EFFECT_APPLICABILITY_UNRESOLVED = "REVOKED_ACTING_SOURCE_EFFECT_APPLICABILITY_UNRESOLVED"
DIAGNOSTIC_NO_REVIVAL_REQUIRES_REVIEW = "NO_REVIVAL_REQUIRES_REVIEW"
DIAGNOSTIC_MISSING_DOCUMENT_REFERENCE = "MISSING_DOCUMENT_REFERENCE"
DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED = "SUPERSEDING_SOURCE_REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class SourceEffectResolutionDiagnostic:
    code: str
    message: str
    effect_ids: tuple[str, ...] = ()
    document_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentEffectiveSourceResolution:
    document_id: str
    status: str
    effective_replacement_document_id: str | None
    supersession_chain: tuple[str, ...]
    document_wide_effect_ids: tuple[str, ...]
    partial_effect_ids: tuple[str, ...]
    blocking_effect_ids: tuple[str, ...]
    diagnostics: tuple[SourceEffectResolutionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class TenderEffectiveSourceResolution:
    tender_id: str
    status: str
    documents: tuple[DocumentEffectiveSourceResolution, ...]
    unresolved_effects: tuple[str, ...]
    conflicts: tuple[str, ...]
    diagnostics: tuple[SourceEffectResolutionDiagnostic, ...]


@dataclass(slots=True)
class _MutableDocumentResolution:
    document_id: str
    status: str = DOCUMENT_EFFECTIVE_STATUS_ACTIVE
    effective_replacement_document_id: str | None = None
    supersession_chain: tuple[str, ...] = field(default_factory=tuple)
    document_wide_effect_ids: set[str] = field(default_factory=set)
    partial_effect_ids: set[str] = field(default_factory=set)
    blocking_effect_ids: set[str] = field(default_factory=set)
    diagnostics: list[SourceEffectResolutionDiagnostic] = field(default_factory=list)

    def force_review(
        self,
        *,
        code: str,
        message: str,
        effect_ids: tuple[str, ...],
    ) -> None:
        self.status = DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED
        self.blocking_effect_ids.update(effect_ids)
        self.diagnostics.append(
            SourceEffectResolutionDiagnostic(
                code=code,
                message=message,
                effect_ids=tuple(sorted(set(effect_ids))),
                document_id=self.document_id,
            )
        )


@dataclass(frozen=True, slots=True)
class _EffectEdge:
    affected_document_id: str
    acting_document_id: str
    effect_ids: tuple[str, ...]


def resolve_effective_sources_for_tender(db: Session, *, tender_id: str) -> TenderEffectiveSourceResolution:
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
    document_state = {doc.id: _MutableDocumentResolution(document_id=doc.id) for doc in documents}

    effects = list(
        db.execute(
            select(TenderSourceEffect)
            .where(TenderSourceEffect.tender_id == resolved_tender_id)
            .order_by(TenderSourceEffect.id.asc())
        ).scalars()
    )

    supersedes_edges: dict[tuple[str, str], set[str]] = {}
    revokes_edges: dict[tuple[str, str], set[str]] = {}
    trusted_non_terminal_effect_ids: list[str] = []
    trusted_effect_by_id: dict[str, TenderSourceEffect] = {}

    unresolved_effects: set[str] = set()
    conflicts: set[str] = set()
    tender_diagnostics: list[SourceEffectResolutionDiagnostic] = []

    for effect in effects:
        trusted_effect_by_id[effect.id] = effect

        if effect.affected_document_id == effect.acting_document_id and effect.affected_document_id is not None:
            if effect.acting_document_id in document_state:
                document_state[effect.acting_document_id].force_review(
                    code=DIAGNOSTIC_SELF_SOURCE_EFFECT,
                    message="Se detectó un efecto inválido de auto-referencia del documento origen.",
                    effect_ids=(effect.id,),
                )
            conflicts.add(effect.id)
            continue

        if effect.acting_document_id not in document_ids:
            unresolved_effects.add(effect.id)
            tender_diagnostics.append(
                SourceEffectResolutionDiagnostic(
                    code=DIAGNOSTIC_MISSING_DOCUMENT_REFERENCE,
                    message="El efecto referencia un documento origen que no pertenece al expediente.",
                    effect_ids=(effect.id,),
                )
            )
            continue

        if effect.review_required:
            if effect.affected_document_id in document_state:
                document_state[effect.affected_document_id].force_review(
                    code=DIAGNOSTIC_REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION,
                    message="Existe un efecto persistido con revisión pendiente que bloquea la resolución automática.",
                    effect_ids=(effect.id,),
                )
            else:
                unresolved_effects.add(effect.id)
                tender_diagnostics.append(
                    SourceEffectResolutionDiagnostic(
                        code=DIAGNOSTIC_UNRESOLVED_REVIEW_EFFECT_TARGET,
                        message="Existe un efecto con revisión pendiente cuyo documento afectado no puede resolverse.",
                        effect_ids=(effect.id,),
                    )
                )
            continue

        if effect.effect_scope == SOURCE_EFFECT_SCOPE_UNRESOLVED:
            if effect.affected_document_id in document_state:
                document_state[effect.affected_document_id].force_review(
                    code=DIAGNOSTIC_UNRESOLVED_SCOPE_TARGET_BLOCKS_AUTOMATION,
                    message="Existe un efecto confiable con alcance no resuelto que requiere revisión humana.",
                    effect_ids=(effect.id,),
                )
            else:
                unresolved_effects.add(effect.id)
                tender_diagnostics.append(
                    SourceEffectResolutionDiagnostic(
                        code=DIAGNOSTIC_UNRESOLVED_SCOPE_UNRESOLVED_TARGET,
                        message="Existe un efecto confiable con alcance no resuelto y sin documento afectado resoluble.",
                        effect_ids=(effect.id,),
                    )
                )
            continue

        if effect.affected_document_id not in document_state:
            unresolved_effects.add(effect.id)
            tender_diagnostics.append(
                SourceEffectResolutionDiagnostic(
                    code=DIAGNOSTIC_UNRESOLVED_TARGET_FOR_TRUSTED_EFFECT,
                    message="Existe un efecto confiable sin documento afectado resoluble para este expediente.",
                    effect_ids=(effect.id,),
                )
            )
            continue

        target = document_state[effect.affected_document_id]

        if effect.effect_scope == SOURCE_EFFECT_SCOPE_PARTIAL:
            target.partial_effect_ids.add(effect.id)
            if effect.effect_type in NON_TERMINAL_EFFECT_TYPES:
                trusted_non_terminal_effect_ids.append(effect.id)
            continue

        target.document_wide_effect_ids.add(effect.id)

        if effect.effect_scope != SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE:
            unresolved_effects.add(effect.id)
            continue

        if effect.effect_type == SOURCE_EFFECT_TYPE_SUPERSEDES:
            key = _dedupe_key(effect)
            supersedes_edges.setdefault(key, set()).add(effect.id)
            continue

        if effect.effect_type == SOURCE_EFFECT_TYPE_REVOKES:
            key = _dedupe_key(effect)
            revokes_edges.setdefault(key, set()).add(effect.id)
            continue

        if effect.effect_type in NON_TERMINAL_EFFECT_TYPES:
            trusted_non_terminal_effect_ids.append(effect.id)

    supersedes_by_target = _group_edges_by_target(supersedes_edges)
    revokes_by_target = _group_edges_by_target(revokes_edges)
    supersession_cycle_nodes = _detect_supersession_cycle_nodes(supersedes_by_target)

    for document_id in sorted(document_ids):
        state = document_state[document_id]
        if state.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED:
            continue

        superseders = supersedes_by_target.get(document_id, {})
        revokers = revokes_by_target.get(document_id, {})

        if document_id in supersession_cycle_nodes:
            effect_ids = _effect_ids_touching_document(document_id, superseders, revokers)
            state.force_review(
                code=DIAGNOSTIC_SUPERSESSION_CYCLE,
                message="Se detectó un ciclo de sustitución entre documentos y no se puede resolver automáticamente.",
                effect_ids=effect_ids,
            )
            conflicts.update(effect_ids)
            continue

        if superseders and revokers:
            effect_ids = _effect_ids_touching_document(document_id, superseders, revokers)
            state.force_review(
                code=DIAGNOSTIC_CONFLICTING_TERMINAL_EFFECTS,
                message="Existen efectos terminales conflictivos (sustitución y revocación) sobre el mismo documento.",
                effect_ids=effect_ids,
            )
            conflicts.update(effect_ids)
            continue

        if len(superseders) > 1:
            effect_ids = _effect_ids_touching_document(document_id, superseders, revokers)
            state.force_review(
                code=DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES,
                message="Existen múltiples documentos que declaran sustituir la misma fuente.",
                effect_ids=effect_ids,
            )
            conflicts.update(effect_ids)
            continue

        if revokers:
            state.status = DOCUMENT_EFFECTIVE_STATUS_REVOKED
            state.blocking_effect_ids.update(_effect_ids_touching_document(document_id, superseders, revokers))
            continue

        if len(superseders) == 1:
            chain_resolution = _resolve_supersession_chain(
                document_id=document_id,
                supersedes_by_target=supersedes_by_target,
                revokes_by_target=revokes_by_target,
                cycle_nodes=supersession_cycle_nodes,
            )
            if chain_resolution.review_required:
                state.force_review(
                    code=chain_resolution.code,
                    message=chain_resolution.message,
                    effect_ids=chain_resolution.effect_ids,
                )
                conflicts.update(chain_resolution.effect_ids)
                continue

            state.status = DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
            state.supersession_chain = chain_resolution.chain
            state.effective_replacement_document_id = chain_resolution.effective_replacement_document_id
            state.blocking_effect_ids.update(chain_resolution.effect_ids)

    superseded_documents = {
        doc_id
        for doc_id, state in document_state.items()
        if state.status == DOCUMENT_EFFECTIVE_STATUS_SUPERSEDED
    }
    revoked_documents = {
        doc_id
        for doc_id, state in document_state.items()
        if state.status == DOCUMENT_EFFECTIVE_STATUS_REVOKED
    }

    for effect_id in trusted_non_terminal_effect_ids:
        effect = trusted_effect_by_id[effect_id]
        if effect.affected_document_id not in document_state:
            continue

        if effect.acting_document_id in superseded_documents:
            document_state[effect.affected_document_id].force_review(
                code=DIAGNOSTIC_ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW,
                message="La aplicabilidad del efecto depende de herencia desde una fuente actuante sustituida.",
                effect_ids=(effect.id,),
            )
            conflicts.add(effect.id)

        if effect.acting_document_id in revoked_documents:
            document_state[effect.affected_document_id].force_review(
                code=DIAGNOSTIC_REVOKED_ACTING_SOURCE_EFFECT_APPLICABILITY_UNRESOLVED,
                message="La aplicabilidad del efecto emitido por una fuente revocada no puede resolverse automáticamente.",
                effect_ids=(effect.id,),
            )
            conflicts.add(effect.id)

    _propagate_review_dependency_from_superseding_sources(
        document_state=document_state,
        supersedes_by_target=supersedes_by_target,
        conflicts=conflicts,
    )

    for document_id, state in document_state.items():
        if state.status == DOCUMENT_EFFECTIVE_STATUS_ACTIVE:
            if state.document_wide_effect_ids or state.partial_effect_ids:
                state.status = DOCUMENT_EFFECTIVE_STATUS_ACTIVE_WITH_EFFECTS

    resolved_documents = tuple(
        DocumentEffectiveSourceResolution(
            document_id=document_id,
            status=state.status,
            effective_replacement_document_id=state.effective_replacement_document_id,
            supersession_chain=state.supersession_chain,
            document_wide_effect_ids=tuple(sorted(state.document_wide_effect_ids)),
            partial_effect_ids=tuple(sorted(state.partial_effect_ids)),
            blocking_effect_ids=tuple(sorted(state.blocking_effect_ids)),
            diagnostics=tuple(state.diagnostics),
        )
        for document_id, state in sorted(document_state.items())
    )

    if unresolved_effects:
        for effect_id in sorted(unresolved_effects):
            if effect_id in conflicts:
                continue
            tender_diagnostics.append(
                SourceEffectResolutionDiagnostic(
                    code=DIAGNOSTIC_UNRESOLVED_TARGET_FOR_TRUSTED_EFFECT,
                    message="Existe al menos un efecto sin objetivo resoluble que impide declarar resolución completa.",
                    effect_ids=(effect_id,),
                )
            )

    has_review_documents = any(item.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED for item in resolved_documents)
    status = TENDER_RESOLUTION_STATUS_REVIEW_REQUIRED if (has_review_documents or unresolved_effects or conflicts) else TENDER_RESOLUTION_STATUS_RESOLVED

    return TenderEffectiveSourceResolution(
        tender_id=resolved_tender_id,
        status=status,
        documents=resolved_documents,
        unresolved_effects=tuple(sorted(unresolved_effects)),
        conflicts=tuple(sorted(conflicts)),
        diagnostics=tuple(tender_diagnostics),
    )


@dataclass(frozen=True, slots=True)
class _ChainResolution:
    review_required: bool
    chain: tuple[str, ...]
    effective_replacement_document_id: str | None
    effect_ids: tuple[str, ...]
    code: str = ""
    message: str = ""


def _resolve_supersession_chain(
    *,
    document_id: str,
    supersedes_by_target: dict[str, dict[str, tuple[str, ...]]],
    revokes_by_target: dict[str, dict[str, tuple[str, ...]]],
    cycle_nodes: set[str],
) -> _ChainResolution:
    chain: list[str] = [document_id]
    seen: set[str] = {document_id}
    effect_ids: set[str] = set()
    current = document_id

    while True:
        superseders = supersedes_by_target.get(current, {})
        revokers = revokes_by_target.get(current, {})

        effect_ids.update(_effect_ids_touching_document(current, superseders, revokers))

        if current in cycle_nodes:
            return _ChainResolution(
                review_required=True,
                chain=tuple(chain),
                effective_replacement_document_id=None,
                effect_ids=tuple(sorted(effect_ids)),
                code=DIAGNOSTIC_SUPERSESSION_CYCLE,
                message="Se detectó un ciclo de sustitución en la cadena de reemplazo.",
            )

        if superseders and revokers:
            return _ChainResolution(
                review_required=True,
                chain=tuple(chain),
                effective_replacement_document_id=None,
                effect_ids=tuple(sorted(effect_ids)),
                code=DIAGNOSTIC_CONFLICTING_TERMINAL_EFFECTS,
                message="Existen efectos terminales conflictivos dentro de la cadena de sustitución.",
            )

        if len(superseders) > 1:
            return _ChainResolution(
                review_required=True,
                chain=tuple(chain),
                effective_replacement_document_id=None,
                effect_ids=tuple(sorted(effect_ids)),
                code=DIAGNOSTIC_MULTIPLE_SUPERSEDING_SOURCES,
                message="La cadena de sustitución tiene bifurcación no resoluble de forma automática.",
            )

        if revokers:
            return _ChainResolution(
                review_required=True,
                chain=tuple(chain),
                effective_replacement_document_id=None,
                effect_ids=tuple(sorted(effect_ids)),
                code=DIAGNOSTIC_NO_REVIVAL_REQUIRES_REVIEW,
                message="No se permite inferir reactivación automática cuando el reemplazo también fue revocado.",
            )

        if len(superseders) == 0:
            return _ChainResolution(
                review_required=False,
                chain=tuple(chain),
                effective_replacement_document_id=current,
                effect_ids=tuple(sorted(effect_ids)),
            )

        next_document_id = sorted(superseders.keys())[0]
        if next_document_id in seen:
            return _ChainResolution(
                review_required=True,
                chain=tuple(chain),
                effective_replacement_document_id=None,
                effect_ids=tuple(sorted(effect_ids)),
                code=DIAGNOSTIC_SUPERSESSION_CYCLE,
                message="Se detectó un ciclo de sustitución durante el recorrido de cadena.",
            )

        seen.add(next_document_id)
        chain.append(next_document_id)
        current = next_document_id


def _group_edges_by_target(edges: dict[tuple[str, str, str, str], set[str]]) -> dict[str, dict[str, tuple[str, ...]]]:
    grouped: dict[str, dict[str, tuple[str, ...]]] = {}
    for key, effect_ids in sorted(edges.items()):
        affected_document_id, acting_document_id, _effect_type, _effect_scope = key
        grouped.setdefault(affected_document_id, {})[acting_document_id] = tuple(sorted(effect_ids))
    return grouped


def _dedupe_key(effect: TenderSourceEffect) -> tuple[str, str, str, str]:
    return (
        str(effect.affected_document_id),
        str(effect.acting_document_id),
        str(effect.effect_type),
        str(effect.effect_scope),
    )


def _detect_supersession_cycle_nodes(
    supersedes_by_target: dict[str, dict[str, tuple[str, ...]]]
) -> set[str]:
    adjacency: dict[str, list[str]] = {
        target: sorted(actors.keys())
        for target, actors in supersedes_by_target.items()
    }

    cycle_nodes: set[str] = set()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        visiting.add(node)
        stack.append(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
                continue
            if neighbor in visiting:
                try:
                    idx = stack.index(neighbor)
                    cycle_nodes.update(stack[idx:])
                except ValueError:
                    cycle_nodes.add(neighbor)

        stack.pop()
        visiting.remove(node)

    for root in sorted(adjacency.keys()):
        if root in visited:
            continue
        dfs(root)

    return cycle_nodes


def _effect_ids_touching_document(
    document_id: str,
    superseders: dict[str, tuple[str, ...]],
    revokers: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    values: set[str] = set()
    for ids in superseders.values():
        values.update(ids)
    for ids in revokers.values():
        values.update(ids)
    return tuple(sorted(values))


def _propagate_review_dependency_from_superseding_sources(
    *,
    document_state: dict[str, _MutableDocumentResolution],
    supersedes_by_target: dict[str, dict[str, tuple[str, ...]]],
    conflicts: set[str],
) -> None:
    changed = True
    while changed:
        changed = False
        for target_document_id in sorted(supersedes_by_target.keys()):
            target_state = document_state.get(target_document_id)
            if target_state is None:
                continue
            if target_state.status == DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED:
                continue

            superseders = supersedes_by_target[target_document_id]
            if len(superseders) != 1:
                continue

            superseding_document_id = sorted(superseders.keys())[0]
            superseding_state = document_state.get(superseding_document_id)
            if superseding_state is None:
                continue
            if superseding_state.status != DOCUMENT_EFFECTIVE_STATUS_REVIEW_REQUIRED:
                continue

            edge_effect_ids = tuple(sorted(superseders[superseding_document_id]))
            target_state.force_review(
                code=DIAGNOSTIC_SUPERSEDING_SOURCE_REVIEW_REQUIRED,
                message="No se puede resolver la sustitución porque la fuente que sustituye requiere revisión.",
                effect_ids=edge_effect_ids,
            )
            target_state.effective_replacement_document_id = None
            target_state.supersession_chain = ()
            conflicts.update(edge_effect_ids)
            changed = True
