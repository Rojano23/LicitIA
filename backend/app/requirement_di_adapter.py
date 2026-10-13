"""Requirement-specific DI bridge; no reinterpretation of domain decisions."""
from __future__ import annotations
import re
from app.document_intelligence import Capability, PerceptionEvidence, Quality, RoutingResult, route_capability
from app.critical_identifier_comparison import compare_identifiers
from app.document_identifier_bindings import affected_comparisons, page_identifier_comparisons, transcription_requires_review
from app.models import RequirementCandidate, RequirementCandidateEvidence
from app.requirement_perception_provenance import PerceptionSource, PersistedProvenance, RequirementPerceptionProvenanceV2, provenance_from_routings, read_provenance, routing_contexts, write_provenance


def _observation(source: PerceptionSource) -> PerceptionEvidence:
    fields = source.model_dump(exclude={"excerpt", "excerpt_sha256"})
    return PerceptionEvidence(**fields, text=source.excerpt)


def complete_snapshot(row: RequirementCandidateEvidence, result: RoutingResult) -> RoutingResult:
    """Retain history on explicit full-page refresh; missing generations are inactive.

    This adapter owns refresh eligibility. The versioned writer continues to
    reject incomplete snapshots. No temporal winner is inferred.
    """
    previous = read_provenance(row.perception_provenance)
    if previous is None:
        return result
    observations = list(result.candidates)
    identities = {(e.source_artifact_key, e.generation_id, e.text) for e in observations}
    for context in routing_contexts(previous):
        if context.capability != result.capability:
            continue
        for source in context.candidates:
            if (source.source_artifact_key, source.generation_id, source.excerpt) not in identities:
                old = _observation(source)
                observations.append(old.model_copy(update={"lineage": "DESELECTED",
                    "diagnostics": tuple(sorted(set(old.diagnostics + ("NOT_IN_CURRENT_PAGE_SNAPSHOT",))))}))
    return route_capability(page=result.page, capability=Capability.TRANSCRIPTION, evidence=observations)


def persist_snapshot(row: RequirementCandidateEvidence, result: RoutingResult) -> None:
    """Refresh known capabilities and preserve all earlier observations explicitly."""
    from sqlalchemy.orm import object_session
    from app.document_intelligence_sources import load_page_structure
    from app.models import TenderDocument, DocumentPage
    db = object_session(row)
    previous = read_provenance(row.perception_provenance)
    refreshed = complete_snapshot(row,result)
    results = [refreshed]
    if db is not None:
        document = db.get(TenderDocument,row.source_document_id)
        page = db.get(DocumentPage,row.document_page_id)
        if document is not None and page is not None:
            structure = load_page_structure(db,document,page)
            if previous is not None:
                observations = list(structure.candidates)
                identities = {(o.source_artifact_key,o.generation_id,o.text) for o in observations}
                for context in routing_contexts(previous):
                    if context.capability != Capability.STRUCTURE:
                        continue
                    for source in context.candidates:
                        if (source.source_artifact_key,source.generation_id,source.excerpt) not in identities:
                            observations.append(_observation(source).model_copy(update={"lineage":"DESELECTED"}))
                structure = route_capability(page=structure.page,capability=structure.capability,evidence=observations)
            results.append(structure)
    comparisons = list(page_identifier_comparisons(*results))
    if not comparisons and not isinstance(previous,RequirementPerceptionProvenanceV2):
        write_provenance(row,refreshed)
        return
    contexts = provenance_from_routings(tuple(results)).routing_contexts
    if isinstance(previous,RequirementPerceptionProvenanceV2):
        known = {context.capability for context in contexts}
        contexts += tuple(context for context in previous.routing_contexts if context.capability not in known)
        current = {(source.capability,source.source_artifact_key,source.generation_id,source.excerpt):source
            for context in contexts for source in context.candidates}
        by_key = {(c.kind,c.binding_key):c for c in comparisons}
        for old in previous.identifier_comparisons:
            fresh = by_key.get((old.kind,old.binding_key))
            observations = list(fresh.observations if fresh is not None else ())
            identities = {(o.source.capability,o.source.source_artifact_key,o.source.generation_id,o.source.text) for o in observations}
            for observation in old.observations:
                source = observation.source
                key = (source.capability,source.source_artifact_key,source.generation_id,source.text)
                updated = current[key]
                preserved = observation.model_copy(update={"source":source.model_copy(
                    update={"lineage":updated.lineage,"diagnostics":updated.diagnostics})})
                if key not in identities:
                    observations.append(preserved)
                else:
                    observations = [preserved if (o.source.capability,o.source.source_artifact_key,
                        o.source.generation_id,o.source.text) == key else o for o in observations]
            by_key[(old.kind,old.binding_key)] = compare_identifiers(kind=old.kind,binding_key=old.binding_key,
                observations=tuple(observations))
        comparisons = list(by_key.values())
    write_provenance(row,RequirementPerceptionProvenanceV2(page=refreshed.page,routing_contexts=contexts,
        identifier_comparisons=tuple(comparisons)))


def candidate_perception(candidate: RequirementCandidate) -> tuple[bool, bool]:
    """Active support and review need; legacy NULL keeps the accepted behavior."""
    states = [read_provenance(row.perception_provenance) for row in candidate.evidence]
    legacy = not states or any(state is None for state in states)
    critical_review = any(isinstance(state, RequirementPerceptionProvenanceV2)
        and affected_comparisons(state.identifier_comparisons,candidate.source_excerpt) for state in states)
    states = [context for state in states if state is not None for context in routing_contexts(state)
              if context.capability == Capability.TRANSCRIPTION]
    if not states:
        return (True, False) if legacy else (False, True)
    excerpt = re.sub(r"\s+", " ", candidate.source_excerpt).strip()
    supporting = [state for state in states if any(source.lineage == "ACTIVE"
        and source.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED}
        and excerpt in re.sub(r"\s+", " ", source.excerpt).strip() for source in state.candidates)]
    active = legacy or bool(supporting)
    def requires_review(state):
        # Pure domain-local trust check; no mutation of persisted routing.
        from app.document_intelligence import PerceptionConflict
        result = RoutingResult(page=state.page,capability=state.capability,status=state.routing_status,
            selected=_observation(state.selected) if state.selected is not None else None,
            candidates=tuple(_observation(c) for c in state.candidates),
            conflicts=tuple(PerceptionConflict(kind=c.kind,binding_key=c.binding_key,
                alternatives=tuple(_observation(a) for a in c.alternatives)) for c in state.conflicts),
            diagnostics=state.diagnostics)
        return transcription_requires_review(result,candidate.source_excerpt)
    review = not active or bool(critical_review) or any(requires_review(state) for state in (states if legacy else supporting))
    return active, review


def candidate_provenance(candidate: RequirementCandidate) -> list[PersistedProvenance]:
    return [state for row in candidate.evidence
            if (state := read_provenance(row.perception_provenance)) is not None]
