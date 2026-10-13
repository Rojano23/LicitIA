"""Requirement-specific DI bridge; no reinterpretation of domain decisions."""
from __future__ import annotations
import re
from app.document_intelligence import Capability, PerceptionEvidence, Quality, RoutingResult, route_capability
from app.models import RequirementCandidate, RequirementCandidateEvidence
from app.requirement_perception_provenance import PerceptionSource, RequirementPerceptionProvenance, read_provenance, write_provenance


def _observation(source: PerceptionSource) -> PerceptionEvidence:
    fields = source.model_dump(exclude={"excerpt", "excerpt_sha256"})
    return PerceptionEvidence(**fields, text=source.excerpt)


def complete_snapshot(row: RequirementCandidateEvidence, result: RoutingResult) -> RoutingResult:
    """Retain history on explicit full-page refresh; missing generations are inactive.

    This adapter owns refresh eligibility. The R.2a writer remains unchanged and
    continues to reject incomplete snapshots. No temporal winner is inferred.
    """
    previous = read_provenance(row.perception_provenance)
    if previous is None:
        return result
    observations = list(result.candidates)
    identities = {(e.source_artifact_key, e.generation_id, e.text) for e in observations}
    for source in previous.candidates:
        if (source.source_artifact_key, source.generation_id, source.excerpt) not in identities:
            old = _observation(source)
            observations.append(old.model_copy(update={"lineage": "DESELECTED",
                "diagnostics": tuple(sorted(set(old.diagnostics + ("NOT_IN_CURRENT_PAGE_SNAPSHOT",))))}))
    return route_capability(page=result.page, capability=Capability.TRANSCRIPTION, evidence=observations)


def persist_snapshot(row: RequirementCandidateEvidence, result: RoutingResult) -> None:
    write_provenance(row, complete_snapshot(row, result))


def candidate_perception(candidate: RequirementCandidate) -> tuple[bool, bool]:
    """Active support and review need; legacy NULL keeps the accepted behavior."""
    states = [read_provenance(row.perception_provenance) for row in candidate.evidence]
    legacy = not states or any(state is None for state in states)
    states = [state for state in states if state is not None]
    if not states:
        return True, False
    excerpt = re.sub(r"\s+", " ", candidate.source_excerpt).strip()
    supporting = [state for state in states if any(source.lineage == "ACTIVE"
        and source.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED}
        and excerpt in re.sub(r"\s+", " ", source.excerpt).strip() for source in state.candidates)]
    active = legacy or bool(supporting)
    review = not active or any(state.routing_status != "RESOLVED" for state in (states if legacy else supporting))
    return active, review


def candidate_provenance(candidate: RequirementCandidate) -> list[RequirementPerceptionProvenance]:
    return [state for row in candidate.evidence
            if (state := read_provenance(row.perception_provenance)) is not None]
