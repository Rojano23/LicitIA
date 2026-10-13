"""Typed JSONB bridge; no discovery, routing, commits or domain decisions."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.document_intelligence import Capability, CriticalIdentifier, PageIdentity, PerceptionEvidence, Quality, RoutingResult, SourceMethod
from app.models import RequirementCandidateEvidence


class PersistenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class PerceptionSource(PersistenceContract):
    page: PageIdentity
    source_method: SourceMethod
    capability: Capability
    source_artifact_key: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    source_analysis_id: str | None
    source_page_result_id: str | None
    normalized_content_id: str | None
    source_contract_version: str | None
    source_locator: str | None
    coordinates: tuple[float, float, float, float] | None
    excerpt: str
    excerpt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage: Literal["ACTIVE", "DESELECTED"]
    quality: Quality
    confidence: float | None
    confidence_scale: str | None
    diagnostics: tuple[str, ...]
    provider_metadata: tuple[tuple[str, str], ...]
    critical_identifiers: tuple[CriticalIdentifier, ...]
    contractual_authority: Literal[False]

    @model_validator(mode="after")
    def validate_source(self) -> PerceptionSource:
        if hashlib.sha256(self.excerpt.encode("utf-8")).hexdigest() != self.excerpt_sha256:
            raise ValueError("Perception excerpt hash mismatch")
        if not self.source_artifact_key.strip() or not self.generation_id.strip():
            raise ValueError("Perception identities cannot be blank")
        if self.confidence is not None and not self.confidence_scale:
            raise ValueError("Confidence requires its original scale")
        for identifier in self.critical_identifiers:
            if identifier.excerpt not in self.excerpt or identifier.value not in identifier.excerpt:
                raise ValueError("Identifier provenance must remain grounded")
        return self


class PersistedConflict(PersistenceContract):
    kind: Literal["TEXTUAL", "STRUCTURAL", "IDENTIFIER"]
    binding_key: str | None
    alternatives: tuple[PerceptionSource, ...] = Field(min_length=2)
    status: Literal["REVIEW_REQUIRED"]


class RequirementPerceptionProvenance(PersistenceContract):
    schema_version: Literal["1"]
    page: PageIdentity
    capability: Capability
    routing_status: Literal["RESOLVED", "REVIEW_REQUIRED", "UNAVAILABLE"]
    selected: PerceptionSource | None
    candidates: tuple[PerceptionSource, ...]
    conflicts: tuple[PersistedConflict, ...]
    diagnostics: tuple[str, ...]
    fallback_requires_real_vision: bool
    contractual_authority: Literal[False]

    @model_validator(mode="after")
    def validate_consistency(self) -> RequirementPerceptionProvenance:
        if any(c.page != self.page or c.capability != self.capability for c in self.candidates):
            raise ValueError("Perception candidate page/capability mismatch")
        if self.selected is not None and (self.selected not in self.candidates
                or self.selected.lineage != "ACTIVE" or self.selected.quality != Quality.RELIABLE):
            raise ValueError("Selected perception must be reliable ACTIVE candidate")
        if self.routing_status == "RESOLVED" and (self.selected is None or self.capability == Capability.SEMANTIC_ASSIST):
            raise ValueError("Resolved perception requires selected evidence")
        if self.routing_status == "UNAVAILABLE" and self.selected is not None:
            raise ValueError("Unavailable perception cannot select evidence")
        if self.conflicts and (self.routing_status != "REVIEW_REQUIRED" or self.selected is not None):
            raise ValueError("Conflicting perception must remain unresolved")
        if any(a not in self.candidates for conflict in self.conflicts for a in conflict.alternatives):
            raise ValueError("Conflict alternatives must remain in considered candidates")
        return self


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _source(evidence: PerceptionEvidence) -> dict:
    fields = evidence.model_dump(mode="json", exclude={"text", "structural_state", "bounded_grounded"})
    fields["excerpt"] = evidence.text
    fields["excerpt_sha256"] = hashlib.sha256(evidence.text.encode("utf-8")).hexdigest()
    fields["diagnostics"] = sorted(fields["diagnostics"])
    fields["provider_metadata"] = sorted(fields["provider_metadata"])
    fields["critical_identifiers"] = sorted(fields["critical_identifiers"], key=_canonical_json)
    return fields


def provenance_from_routing(result: RoutingResult) -> RequirementPerceptionProvenance:
    """Project an already validated R.1 result; never recalculate its decision."""
    payload = {
        "schema_version": "1", "page": result.page.model_dump(mode="json"),
        "capability": result.capability.value, "routing_status": result.status,
        "selected": _source(result.selected) if result.selected is not None else None,
        "candidates": sorted((_source(c) for c in result.candidates), key=_canonical_json),
        "conflicts": sorted(({"kind": c.kind, "binding_key": c.binding_key,
            "alternatives": sorted((_source(a) for a in c.alternatives), key=_canonical_json),
            "status": c.status} for c in result.conflicts), key=_canonical_json),
        "diagnostics": sorted(result.diagnostics),
        "fallback_requires_real_vision": result.fallback_requires_real_vision,
        "contractual_authority": result.contractual_authority,
    }
    return RequirementPerceptionProvenance.model_validate_json(_canonical_json(payload))


def serialize_provenance(value: RequirementPerceptionProvenance) -> dict:
    """JSON-safe, canonical collection order for both writes and reserialization."""
    payload = value.model_dump(mode="json")
    def ordered_source(source: dict) -> dict:
        source["diagnostics"] = sorted(source["diagnostics"])
        source["provider_metadata"] = sorted(source["provider_metadata"])
        source["critical_identifiers"] = sorted(source["critical_identifiers"], key=_canonical_json)
        return source

    payload["selected"] = ordered_source(payload["selected"]) if payload["selected"] is not None else None
    payload["candidates"] = sorted((ordered_source(c) for c in payload["candidates"]), key=_canonical_json)
    for conflict in payload["conflicts"]:
        conflict["alternatives"] = sorted((ordered_source(a) for a in conflict["alternatives"]), key=_canonical_json)
    payload["conflicts"] = sorted(payload["conflicts"], key=_canonical_json)
    payload["diagnostics"] = sorted(payload["diagnostics"])
    return json.loads(_canonical_json(payload))


def read_provenance(value: object) -> RequirementPerceptionProvenance | None:
    """SQL NULL is legacy unavailable provenance; malformed JSON raises explicitly."""
    if value is None:
        return None
    return RequirementPerceptionProvenance.model_validate_json(_canonical_json(value))


def write_provenance(row: RequirementCandidateEvidence, result: RoutingResult) -> RequirementPerceptionProvenance:
    """Assign a complete routing snapshot to an existing logical evidence row.

    Caller owns flush/transaction and supplies all current/audit candidates.
    Prior observations must remain represented with explicitly supplied lineage;
    the helper never guesses deselection or silently erases a generation.
    """
    value = provenance_from_routing(result)
    if (row.source_document_id != result.page.document_id
            or row.document_page_id != result.page.document_page_id
            or row.source_page != result.page.page_number):
        raise ValueError("Requirement evidence is outside perception page")
    if row.candidate is None:
        raise ValueError("Requirement evidence must belong to a candidate")
    if result.page.tender_id is not None and row.candidate.tender_id != result.page.tender_id:
        raise ValueError("Requirement evidence is outside perception tender")
    previous = read_provenance(row.perception_provenance)
    def identity(source: PerceptionSource) -> tuple:
        return (source.source_method, source.source_artifact_key, source.generation_id,
                source.source_analysis_id, source.source_page_result_id, source.excerpt_sha256,
                source.page, source.capability)

    if previous is not None and not {identity(c) for c in previous.candidates}.issubset(
            {identity(c) for c in value.candidates}):
        raise ValueError("A complete provenance snapshot must retain prior perception observations")
    row.perception_provenance = serialize_provenance(value)
    return value
