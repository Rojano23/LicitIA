from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.item_identity import normalize_item_identity
from app.page_structure import PageStructuralState

LINK_REASON_EXPLICIT_ITEM_START = "EXPLICIT_ITEM_START"
LINK_REASON_CONTINUATION = "CONTINUATION"
LINK_REASON_UNKNOWN = "UNKNOWN"
CONTINUITY_NOTE_MISMATCH_RESET = "CONTINUITY_MISMATCH_RESET"
CONTINUITY_NOTE_CANONICAL_AMBIGUOUS = "CANONICAL_AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class ScopeLinkingPageInput:
    source_document_id: str
    document_page_id: str
    page_state: PageStructuralState


@dataclass(frozen=True, slots=True)
class CanonicalTenderItemReference:
    tender_item_id: str
    item_number: str


@dataclass(frozen=True, slots=True)
class ScopeOwnershipDecision:
    tender_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    sequence_index: int
    candidate_item_key: str
    candidate_item_raw_label: str
    tender_item_id: str | None
    link_reason: str
    source_method: str
    source_analysis_id: str | None
    source_page_result_id: str | None
    source_locator: str
    source_excerpt: str
    review_required: bool
    continuity_note: str | None = None


def _link_reason(starts_on_this_page: bool) -> str:
    if starts_on_this_page:
        return LINK_REASON_EXPLICIT_ITEM_START
    if not starts_on_this_page:
        return LINK_REASON_CONTINUATION
    return LINK_REASON_UNKNOWN


def build_canonical_item_index(canonical_items: Iterable[CanonicalTenderItemReference]) -> dict[str, tuple[str, ...]]:
    indexed: dict[str, list[str]] = defaultdict(list)
    for item in canonical_items:
        normalized = normalize_item_identity(item.item_number)
        if normalized.normalized_key is None:
            continue
        bucket = indexed[normalized.normalized_key]
        if item.tender_item_id not in bucket:
            bucket.append(item.tender_item_id)

    return {key: tuple(value) for key, value in indexed.items()}


def _link_single_document(
    *,
    tender_id: str,
    page_inputs: Sequence[ScopeLinkingPageInput],
    canonical_index: Mapping[str, tuple[str, ...]],
) -> list[ScopeOwnershipDecision]:
    ordered_pages = sorted(page_inputs, key=lambda item: item.page_state.page_number)
    decisions: list[ScopeOwnershipDecision] = []
    previous_valid_outgoing: str | None = None

    for page_input in ordered_pages:
        page_state = page_input.page_state
        if page_state.state_quality != "VALID":
            previous_valid_outgoing = None
            continue

        ordered_segments = sorted(page_state.segments, key=lambda segment: segment.sequence)
        has_explicit_start = any(
            segment.starts_on_this_page and segment.item_identity.normalized_key is not None
            for segment in ordered_segments
        )

        continuity_mismatch = (
            previous_valid_outgoing is not None
            and page_state.incoming_item_key is not None
            and page_state.incoming_item_key != previous_valid_outgoing
        )

        for segment in ordered_segments:
            owner_key = segment.item_identity.normalized_key
            if owner_key is None:
                continue

            review_required = bool(page_state.review_required or segment.review_required)
            continuity_note: str | None = None
            if continuity_mismatch:
                review_required = True
                continuity_note = CONTINUITY_NOTE_MISMATCH_RESET

            tender_item_id: str | None = None
            canonical_matches = canonical_index.get(owner_key, ())
            if len(canonical_matches) == 1:
                tender_item_id = canonical_matches[0]
            elif len(canonical_matches) > 1:
                review_required = True
                tender_item_id = None
                continuity_note = CONTINUITY_NOTE_CANONICAL_AMBIGUOUS

            decisions.append(
                ScopeOwnershipDecision(
                    tender_id=tender_id,
                    source_document_id=page_input.source_document_id,
                    document_page_id=page_input.document_page_id,
                    page_number=page_state.page_number,
                    sequence_index=segment.sequence,
                    candidate_item_key=owner_key,
                    candidate_item_raw_label=segment.item_identity.raw_label,
                    tender_item_id=tender_item_id,
                    link_reason=_link_reason(segment.starts_on_this_page),
                    source_method=page_state.provenance.source_method,
                    source_analysis_id=page_state.provenance.source_analysis_id,
                    source_page_result_id=page_state.provenance.source_page_result_id,
                    source_locator=f"page:{page_state.page_number}|segment:{segment.sequence}",
                    source_excerpt=segment.anchor_raw_text or "",
                    review_required=review_required,
                    continuity_note=continuity_note,
                )
            )

        if continuity_mismatch and not has_explicit_start:
            previous_valid_outgoing = None
        else:
            previous_valid_outgoing = page_state.outgoing_item_key

    return decisions


def link_scope_ownership_decisions(
    *,
    tender_id: str,
    page_inputs: Sequence[ScopeLinkingPageInput],
    canonical_items: Iterable[CanonicalTenderItemReference] = (),
) -> list[ScopeOwnershipDecision]:
    canonical_index = build_canonical_item_index(canonical_items)

    per_document: dict[str, list[ScopeLinkingPageInput]] = defaultdict(list)
    for page_input in page_inputs:
        per_document[page_input.source_document_id].append(page_input)

    decisions: list[ScopeOwnershipDecision] = []
    for source_document_id in sorted(per_document):
        decisions.extend(
            _link_single_document(
                tender_id=tender_id,
                page_inputs=per_document[source_document_id],
                canonical_index=canonical_index,
            )
        )

    return decisions
