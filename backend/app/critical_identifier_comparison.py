"""Grounded identifier comparison; never routing or contractual authority."""
from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from app.document_intelligence import Contract, PerceptionEvidence, Quality


class IdentifierKind(str, Enum):
    ITEM_NUMBER = "ITEM_NUMBER"
    PARTIDA = "PARTIDA"
    EQUIPMENT_TAG = "EQUIPMENT_TAG"
    MODEL_IDENTIFIER = "MODEL_IDENTIFIER"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    QUANTITY_BINDING_IDENTIFIER = "QUANTITY_BINDING_IDENTIFIER"
    STRUCTURAL_GROUP_IDENTIFIER = "STRUCTURAL_GROUP_IDENTIFIER"
    OTHER_CRITICAL_IDENTIFIER = "OTHER_CRITICAL_IDENTIFIER"


def normalize_identifier(value: str) -> str:
    """Comparison only: NFC and whitespace; preserve case, punctuation and zeros."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


class IdentifierObservation(Contract):
    model_config = {"strict": True}
    # The upstream adapter supplies kind and binding; never infer them from text.
    kind: IdentifierKind
    binding_key: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    source: PerceptionEvidence

    @model_validator(mode="after")
    def validate_observation(self) -> IdentifierObservation:
        if not self.binding_key.strip():
            raise ValueError("Identifier binding cannot be blank")
        if self.normalized_value != normalize_identifier(self.raw_value):
            raise ValueError("Identifier comparison normalization mismatch")
        if self.source.quality in {Quality.FAILED, Quality.UNAVAILABLE}:
            raise ValueError("Unavailable/failed evidence cannot supply identifier values")
        if self.raw_value not in self.excerpt or self.excerpt not in self.source.text:
            raise ValueError("Identifier observation must be exactly grounded")
        return self


def identifier_observation(*, kind: IdentifierKind, binding_key: str,
                           raw_value: str, excerpt: str,
                           source: PerceptionEvidence) -> IdentifierObservation:
    return IdentifierObservation(kind=kind, binding_key=binding_key, raw_value=raw_value,
        normalized_value=normalize_identifier(raw_value), excerpt=excerpt, source=source)


def _identity(observation: IdentifierObservation) -> tuple:
    source = observation.source
    return (source.page, source.capability, source.source_method, source.source_artifact_key,
            source.generation_id, source.source_analysis_id, source.source_page_result_id)


def _status(observations: tuple[IdentifierObservation, ...]) -> str:
    if not observations:
        return "NOT_APPLICABLE"
    active = tuple(o for o in observations if o.source.lineage == "ACTIVE"
                   and o.source.quality == Quality.RELIABLE)
    if len({_identity(o) for o in active}) < 2:
        return "INSUFFICIENT_EVIDENCE"
    return "CONFLICT" if len({o.normalized_value for o in active}) > 1 else "AGREEMENT"


class IdentifierComparison(Contract):
    model_config = {"strict": True}
    kind: IdentifierKind
    binding_key: str = Field(min_length=1)
    status: Literal["AGREEMENT", "CONFLICT", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"]
    contractually_critical: Literal[True] = True
    observations: tuple[IdentifierObservation, ...]
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_comparison(self) -> IdentifierComparison:
        if not self.binding_key.strip():
            raise ValueError("Identifier binding cannot be blank")
        if any(o.kind != self.kind or o.binding_key != self.binding_key for o in self.observations):
            raise ValueError("Identifier comparison kind/binding mismatch")
        if len({o.source.page for o in self.observations}) > 1:
            raise ValueError("Identifier comparison must belong to one page")
        if len({_identity(o) for o in self.observations}) != len(self.observations):
            raise ValueError("Duplicate observation identity in identifier comparison")
        if self.status != _status(self.observations):
            raise ValueError("Identifier comparison status contradicts grounded observations")
        return self


def compare_identifiers(*, kind: IdentifierKind, binding_key: str,
                        observations: tuple[IdentifierObservation, ...]) -> IdentifierComparison:
    ordered = tuple(sorted(observations, key=lambda o: o.model_dump_json()))
    status = _status(ordered)
    return IdentifierComparison(kind=kind, binding_key=binding_key, observations=ordered,
        status=status, diagnostics=("CRITICAL_IDENTIFIER_CONFLICT" if status == "CONFLICT" else status,))
