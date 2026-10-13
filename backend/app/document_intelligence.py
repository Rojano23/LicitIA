"""Read-only perception contracts. No provider execution or domain decisions.

Quality is an explicit adapter assessment, never inferred from text presence or
an invented confidence threshold. Existing structural value objects are reused.
"""
from __future__ import annotations

from enum import Enum
from itertools import combinations
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.page_structure import PageStructuralState


class Capability(str, Enum):
    TRANSCRIPTION = "TRANSCRIPTION"  # provider-neutral VISION_TRANSCRIPTION
    STRUCTURE = "STRUCTURE"  # provider-neutral VISION_STRUCTURE
    SEMANTIC_ASSIST = "SEMANTIC_ASSIST"  # provider-neutral VISION_SEMANTIC_ASSIST


class SourceMethod(str, Enum):
    NATIVE = "NATIVE"
    OCR = "OCR"
    VISION = "VISION"


class Quality(str, Enum):
    RELIABLE = "RELIABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class PageIdentity(Contract):
    tender_id: str | None = Field(default=None, min_length=1)
    document_id: str = Field(min_length=1)
    document_page_id: str = Field(min_length=1)
    page_number: int = Field(gt=0)
    document_version: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> PageIdentity:
        if any(value is not None and not value.strip() for value in
               (self.tender_id, self.document_id, self.document_page_id, self.document_version)):
            raise ValueError("Page identity cannot be blank")
        return self


class CriticalIdentifier(Contract):
    """An adapter-declared binding, with an exact grounded alternative.

    binding_key includes the location/role so unrelated item numbers do not
    conflict. DI neither discovers nor normalizes contractual identifiers.
    """
    binding_key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class PerceptionEvidence(Contract):
    page: PageIdentity
    source_method: SourceMethod
    source_artifact_key: str = Field(min_length=1)
    capability: Capability
    quality: Quality = Quality.REVIEW_REQUIRED
    text: str = ""
    source_locator: str | None = None
    coordinates: tuple[float, float, float, float] | None = None
    confidence: float | None = None  # provider's original scale; no thresholds
    confidence_scale: str | None = None
    diagnostics: tuple[str, ...] = ()
    provider_metadata: tuple[tuple[str, str], ...] = ()
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    generation_id: str = Field(min_length=1)
    source_contract_version: str | None = None
    normalized_content_id: str | None = None
    lineage: Literal["ACTIVE", "DESELECTED"] = "ACTIVE"
    structural_state: PageStructuralState | None = None
    critical_identifiers: tuple[CriticalIdentifier, ...] = ()
    bounded_grounded: bool = False
    contractual_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_grounding(self) -> PerceptionEvidence:
        for value in (self.source_artifact_key, self.generation_id):
            if not value.strip():
                raise ValueError("Artifact and generation identities cannot be blank")
        if self.confidence is not None and not self.confidence_scale:
            raise ValueError("Confidence requires its provider scale")
        if self.coordinates is not None:
            x0, y0, x1, y1 = self.coordinates
            if x1 < x0 or y1 < y0:
                raise ValueError("Invalid coordinate rectangle")
        for identifier in self.critical_identifiers:
            if identifier.excerpt not in self.text or identifier.value not in identifier.excerpt:
                raise ValueError("Critical identifier must be grounded in exact source text")
        if len({i.binding_key for i in self.critical_identifiers}) != len(self.critical_identifiers):
            raise ValueError("A single evidence artifact cannot silently repeat a critical binding")
        state = self.structural_state
        if state is not None:
            if self.capability != Capability.STRUCTURE or state.page_number != self.page.page_number:
                raise ValueError("Structural evidence must match capability and current page")
            canonical_method = normalize_source_method(state.provenance.source_method)
            if canonical_method != self.source_method:
                raise ValueError("Structural provenance channel mismatch")
            for field in ("source_analysis_id", "source_page_result_id", "source_contract_version"):
                if getattr(state.provenance, field) != getattr(self, field):
                    raise ValueError(f"Structural provenance mismatch: {field}")
        return self


def normalize_source_method(value: str) -> SourceMethod:
    """Normalize historical channel names, never model/provider names."""
    aliases = {"NATIVE_TEXT": "NATIVE", "NATIVE_PDF": "NATIVE"}
    return SourceMethod(aliases.get(value, value))


class PerceptionConflict(Contract):
    kind: Literal["TEXTUAL", "STRUCTURAL", "IDENTIFIER"]
    binding_key: str | None = None
    alternatives: tuple[PerceptionEvidence, ...]
    status: Literal["REVIEW_REQUIRED"] = "REVIEW_REQUIRED"


class CapabilityAvailability(Contract):
    capability: Capability
    source_method: SourceMethod
    available: bool
    diagnostics: tuple[str, ...] = ()


class RoutingResult(Contract):
    page: PageIdentity
    capability: Capability
    status: Literal["RESOLVED", "REVIEW_REQUIRED", "UNAVAILABLE"]
    selected: PerceptionEvidence | None = None
    candidates: tuple[PerceptionEvidence, ...] = ()
    conflicts: tuple[PerceptionConflict, ...] = ()
    diagnostics: tuple[str, ...] = ()
    fallback_requires_real_vision: bool = False
    contractual_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> RoutingResult:
        if any(e.page != self.page or e.capability != self.capability for e in self.candidates):
            raise ValueError("Routing candidates must match the requested page and capability")
        if self.selected is not None and (self.selected not in self.candidates or not _usable(self.selected)):
            raise ValueError("Selected evidence must be a usable current candidate")
        if self.status == "RESOLVED" and (self.selected is None or self.capability == Capability.SEMANTIC_ASSIST):
            raise ValueError("Resolved perception requires evidence; semantic assistance always requires review")
        if self.conflicts and (self.status != "REVIEW_REQUIRED" or self.selected is not None):
            raise ValueError("Conflicting evidence cannot be silently selected")
        if self.status == "UNAVAILABLE" and self.selected is not None:
            raise ValueError("Unavailable evidence cannot be selected")
        return self


def _order(evidence: PerceptionEvidence) -> tuple:
    # Stable identity order, never temporal precedence. Payload breaks duplicate
    # identity ties deterministically without deleting contradictory evidence.
    rank = {SourceMethod.NATIVE: 0, SourceMethod.OCR: 1, SourceMethod.VISION: 2}
    return (rank[evidence.source_method], evidence.source_artifact_key,
            evidence.generation_id, evidence.model_dump_json())


def _structural_signature(state: PageStructuralState) -> tuple:
    return (state.incoming_item_key, state.outgoing_item_key,
            tuple((s.sequence, s.item_identity.normalized_key, s.starts_on_this_page,
                   s.has_service, s.has_supply, s.has_deliverable)
                  for s in sorted(state.segments, key=lambda s: s.sequence)))


def _usable(evidence: PerceptionEvidence) -> bool:
    if evidence.lineage != "ACTIVE" or evidence.quality != Quality.RELIABLE:
        return False
    if evidence.capability == Capability.STRUCTURE:
        state = evidence.structural_state
        return bool(state and state.state_quality == "VALID" and not state.review_required
                    and state.segments and all(s.item_identity.normalized_key is not None
                    and not s.review_required and s.anchor_raw_text
                    and s.anchor_raw_text in evidence.text for s in state.segments))
    return bool(evidence.text.strip()) and (
        evidence.capability != Capability.SEMANTIC_ASSIST or evidence.bounded_grounded)


def _conflicts(evidence: tuple[PerceptionEvidence, ...]) -> tuple[PerceptionConflict, ...]:
    conflicts: list[PerceptionConflict] = []
    for left, right in combinations(evidence, 2):
        right_ids = {identifier.binding_key: identifier for identifier in right.critical_identifiers}
        for identifier in sorted(left.critical_identifiers, key=lambda i: (i.binding_key, i.value)):
            other = right_ids.get(identifier.binding_key)
            if other is not None and identifier.value != other.value:
                conflicts.append(PerceptionConflict(kind="IDENTIFIER", binding_key=identifier.binding_key,
                                                    alternatives=(left, right)))
        if left.capability == Capability.STRUCTURE:
            if _structural_signature(left.structural_state) != _structural_signature(right.structural_state):
                conflicts.append(PerceptionConflict(kind="STRUCTURAL", alternatives=(left, right)))
        elif left.capability == Capability.TRANSCRIPTION and left.text != right.text:
            conflicts.append(PerceptionConflict(kind="TEXTUAL", alternatives=(left, right)))
    return tuple(conflicts)


def route_capability(*, page: PageIdentity, capability: Capability,
                     evidence: Iterable[PerceptionEvidence],
                     availability: Iterable[CapabilityAvailability] = ()) -> RoutingResult:
    """Pure available-evidence policy; availability never executes a provider.

    Exact disagreements between reliable sources conservatively require review.
    Native/OCR preference applies only after checking conflicts.
    """
    candidates = tuple(sorted((e for e in evidence if e.page == page and e.capability == capability), key=_order))
    usable = tuple(e for e in candidates if _usable(e))
    conflicts = _conflicts(usable)
    base = dict(page=page, capability=capability, candidates=candidates, conflicts=conflicts)
    if conflicts:
        return RoutingResult(**base, status="REVIEW_REQUIRED", diagnostics=("PERCEPTION_CONFLICT",))
    if usable:
        selected = usable[0]
        if capability == Capability.SEMANTIC_ASSIST:
            return RoutingResult(**base, selected=selected, status="REVIEW_REQUIRED",
                                 diagnostics=("BOUNDED_ASSISTANCE_REQUIRES_DOMAIN_AND_HUMAN_VALIDATION",))
        return RoutingResult(**base, selected=selected, status="RESOLVED",
                             diagnostics=("RELIABLE_CURRENT_CAPABILITY_EVIDENCE",))
    vision_eligible = any(a.capability == capability and a.source_method == SourceMethod.VISION
                          and a.available for a in availability)
    uncertain = any(e.lineage == "ACTIVE" and e.quality != Quality.UNAVAILABLE for e in candidates)
    return RoutingResult(**base, status="REVIEW_REQUIRED" if uncertain or vision_eligible else "UNAVAILABLE",
                         diagnostics=("VISION_ELIGIBLE_EXECUTION_DEFERRED" if vision_eligible else "NO_RELIABLE_CURRENT_EVIDENCE",),
                         fallback_requires_real_vision=vision_eligible)


class StructuralContinuity(Contract):
    """Neutral page boundary, not a provider session or domain ownership decision."""
    page: PageIdentity
    status: Literal["VALID", "UNKNOWN"]
    outgoing_item_key: str | None = None
    structural_state: PageStructuralState | None = None
    evidence: PerceptionEvidence | None = None
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_boundary(self) -> StructuralContinuity:
        if self.status == "UNKNOWN":
            if self.outgoing_item_key is not None or self.structural_state is not None:
                raise ValueError("Unknown continuity cannot carry stale structural output")
        elif (self.evidence is None or self.evidence.page != self.page
              or self.evidence.capability != Capability.STRUCTURE or not _usable(self.evidence)
              or self.structural_state != self.evidence.structural_state
              or self.outgoing_item_key != self.structural_state.outgoing_item_key):
            raise ValueError("Valid continuity must preserve trustworthy current structural evidence")
        return self


def advance_continuity(result: RoutingResult, previous: StructuralContinuity | None = None) -> StructuralContinuity:
    if result.capability != Capability.STRUCTURE:
        raise ValueError("Continuity requires STRUCTURE_SCOPE, not DETAIL_TRANSCRIPTION")
    selected = result.selected
    if result.status != "RESOLVED" or selected is None or not _usable(selected):
        return StructuralContinuity(page=result.page, status="UNKNOWN", diagnostics=("CURRENT_STRUCTURE_UNTRUSTWORTHY",))
    state = selected.structural_state
    if state.incoming_item_key is not None:
        adjacent = bool(previous and previous.status == "VALID"
                        and previous.page.tender_id == result.page.tender_id
                        and previous.page.document_id == result.page.document_id
                        and previous.page.document_version == result.page.document_version
                        and previous.page.page_number + 1 == result.page.page_number
                        and previous.outgoing_item_key == state.incoming_item_key)
        if not adjacent:
            return StructuralContinuity(page=result.page, status="UNKNOWN", evidence=selected,
                                        diagnostics=("UNPROVEN_CONTINUITY_BOUNDARY",))
    return StructuralContinuity(page=result.page, status="VALID", outgoing_item_key=state.outgoing_item_key,
                                structural_state=state, evidence=selected)


def normalize_perception_evidence(*, source_method: str, **fields: object) -> PerceptionEvidence:
    """Validate adapter-owned evidence and normalize only historical channel names.

    Callers supply quality, lineage and generation from their existing artifacts.
    Missing quality stays REVIEW_REQUIRED; text presence is never certification.
    No domain classification, identifier discovery or persistence occurs here.
    """
    return PerceptionEvidence.model_validate({**fields, "source_method": normalize_source_method(source_method)})
