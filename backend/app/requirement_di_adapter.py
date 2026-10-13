"""Requirement-specific DI bridge; no reinterpretation of domain decisions."""
from __future__ import annotations
import re
from app.document_intelligence import Capability, PerceptionEvidence, Quality, RoutingResult, route_capability
from app.critical_identifier_comparison import compare_identifiers
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
    previous = read_provenance(row.perception_provenance)
    refreshed = complete_snapshot(row, result)
    if not isinstance(previous, RequirementPerceptionProvenanceV2):
        write_provenance(row, refreshed)
        return
    # Compatibility refresh: preserve other contexts and identifier history.
    replacement = provenance_from_routings((refreshed,)).routing_contexts[0]
    contexts = tuple(context for context in previous.routing_contexts
                     if context.capability != refreshed.capability) + (replacement,)
    current = {(source.source_artifact_key, source.generation_id, source.excerpt): source
               for source in replacement.candidates}
    comparisons = []
    for comparison in previous.identifier_comparisons:
        observations = []
        for observation in comparison.observations:
            source = observation.source
            if source.capability == refreshed.capability:
                updated = current[(source.source_artifact_key, source.generation_id, source.text)]
                source = source.model_copy(update={"lineage": updated.lineage,
                    "diagnostics": updated.diagnostics})
            observations.append(observation.model_copy(update={"source": source}))
        comparisons.append(compare_identifiers(kind=comparison.kind, binding_key=comparison.binding_key,
            observations=tuple(observations)).model_copy(update={"diagnostics": comparison.diagnostics}))
    write_provenance(row, RequirementPerceptionProvenanceV2(page=previous.page,
        routing_contexts=contexts, identifier_comparisons=tuple(comparisons)))


def candidate_perception(candidate: RequirementCandidate) -> tuple[bool, bool]:
    """Active support and review need; legacy NULL keeps the accepted behavior."""
    states = [read_provenance(row.perception_provenance) for row in candidate.evidence]
    legacy = not states or any(state is None for state in states)
    states = [context for state in states if state is not None for context in routing_contexts(state)
              if context.capability == Capability.TRANSCRIPTION]
    if not states:
        return (True, False) if legacy else (False, True)
    excerpt = re.sub(r"\s+", " ", candidate.source_excerpt).strip()
    supporting = [state for state in states if any(source.lineage == "ACTIVE"
        and source.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED}
        and excerpt in re.sub(r"\s+", " ", source.excerpt).strip() for source in state.candidates)]
    active = legacy or bool(supporting)
    review = not active or any(state.routing_status != "RESOLVED" for state in (states if legacy else supporting))
    return active, review


def candidate_provenance(candidate: RequirementCandidate) -> list[PersistedProvenance]:
    return [state for row in candidate.evidence
            if (state := read_provenance(row.perception_provenance)) is not None]
