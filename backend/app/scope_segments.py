from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import TenderScopeSegment
from app.page_structure import PageStructuralProvenance, PageStructuralState, build_page_structural_state
from app.scope_linking import CanonicalTenderItemReference, ScopeLinkingPageInput, ScopeOwnershipDecision, link_scope_ownership_decisions


@dataclass(frozen=True, slots=True)
class TenderScopeSegmentInput:
    page_state: PageStructuralState
    source_document_id: str
    document_page_id: str
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


def _build_semantic_fingerprint(
    *,
    tender_id: str,
    source_document_id: str,
    page_number: int,
    sequence_index: int,
    owner_key: str | None,
    source_method: str,
    link_reason: str,
    source_locator: str,
    source_excerpt: str,
) -> str:
    payload = "|".join(
        [
            tender_id,
            source_document_id,
            str(page_number),
            str(sequence_index),
            owner_key or "",
            source_method,
            link_reason,
            source_locator,
            source_excerpt,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _delete_active_scope_segments_for_page(
    db: Session,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str,
) -> None:
    db.execute(
        delete(TenderScopeSegment).where(
            TenderScopeSegment.tender_id == tender_id,
            TenderScopeSegment.source_document_id == source_document_id,
            TenderScopeSegment.document_page_id == document_page_id,
        )
    )


def _persist_decisions(
    db: Session,
    *,
    decisions: list[ScopeOwnershipDecision],
) -> list[TenderScopeSegment]:
    persisted: list[TenderScopeSegment] = []
    for decision in decisions:
        row = TenderScopeSegment(
            tender_id=decision.tender_id,
            source_document_id=decision.source_document_id,
            document_page_id=decision.document_page_id,
            page_number=decision.page_number,
            tender_item_id=decision.tender_item_id,
            candidate_item_key=decision.candidate_item_key,
            candidate_item_raw_label=decision.candidate_item_raw_label,
            sequence_index=decision.sequence_index,
            scope_domain=None,
            source_method=decision.source_method,
            link_reason=decision.link_reason,
            source_locator=decision.source_locator,
            source_excerpt=decision.source_excerpt,
            source_analysis_id=decision.source_analysis_id,
            source_page_result_id=decision.source_page_result_id,
            confidence=None,
            review_required=decision.review_required,
            semantic_fingerprint=_build_semantic_fingerprint(
                tender_id=decision.tender_id,
                source_document_id=decision.source_document_id,
                page_number=decision.page_number,
                sequence_index=decision.sequence_index,
                owner_key=decision.candidate_item_key,
                source_method=decision.source_method,
                link_reason=decision.link_reason,
                source_locator=decision.source_locator,
                source_excerpt=decision.source_excerpt,
            ),
        )
        db.add(row)
        persisted.append(row)
    return persisted


def _canonical_references_from_candidate_map(
    tender_item_id_by_candidate_key: dict[str, str] | None,
) -> list[CanonicalTenderItemReference]:
    if not tender_item_id_by_candidate_key:
        return []
    return [
        CanonicalTenderItemReference(tender_item_id=tender_item_id, item_number=candidate_key)
        for candidate_key, tender_item_id in tender_item_id_by_candidate_key.items()
    ]


def resolve_scope_ownership_decisions_for_page_inputs(
    *,
    tender_id: str,
    page_inputs: list[TenderScopeSegmentInput],
    canonical_items: list[CanonicalTenderItemReference] | None = None,
) -> list[ScopeOwnershipDecision]:
    if not page_inputs:
        return []

    linking_inputs: list[ScopeLinkingPageInput] = []
    for page_input in page_inputs:
        effective_provenance = PageStructuralProvenance(
            source_method=page_input.page_state.provenance.source_method,
            source_analysis_id=page_input.source_analysis_id
            if page_input.source_analysis_id is not None
            else page_input.page_state.provenance.source_analysis_id,
            source_page_result_id=page_input.source_page_result_id
            if page_input.source_page_result_id is not None
            else page_input.page_state.provenance.source_page_result_id,
            source_contract_version=page_input.page_state.provenance.source_contract_version,
        )
        effective_page_state = build_page_structural_state(
            page_number=page_input.page_state.page_number,
            segments=page_input.page_state.segments,
            state_quality=page_input.page_state.state_quality,
            review_required=page_input.page_state.review_required,
            provenance=effective_provenance,
            incoming_item_key=page_input.page_state.incoming_item_key,
            outgoing_item_key=page_input.page_state.outgoing_item_key,
            warnings=page_input.page_state.warnings,
        )

        linking_inputs.append(
            ScopeLinkingPageInput(
                source_document_id=page_input.source_document_id,
                document_page_id=page_input.document_page_id,
                page_state=effective_page_state,
            )
        )

    decisions = link_scope_ownership_decisions(
        tender_id=tender_id,
        page_inputs=linking_inputs,
        canonical_items=canonical_items or (),
    )

    expected_page_keys = {
        (page_input.source_document_id, page_input.document_page_id)
        for page_input in page_inputs
    }
    decisions_by_page_key: dict[tuple[str, str], list[ScopeOwnershipDecision]] = defaultdict(list)
    for decision in decisions:
        page_key = (decision.source_document_id, decision.document_page_id)
        if page_key in expected_page_keys:
            decisions_by_page_key[page_key].append(decision)

    ordered_keys = [
        (page_input.source_document_id, page_input.document_page_id)
        for page_input in page_inputs
    ]
    ordered_decisions: list[ScopeOwnershipDecision] = []
    for page_key in ordered_keys:
        ordered_decisions.extend(
            sorted(decisions_by_page_key.get(page_key, []), key=lambda decision: decision.sequence_index)
        )

    return ordered_decisions


def replace_tender_scope_segments_for_page_inputs(
    db: Session,
    *,
    tender_id: str,
    page_inputs: list[TenderScopeSegmentInput],
    canonical_items: list[CanonicalTenderItemReference] | None = None,
) -> list[TenderScopeSegment]:
    if not page_inputs:
        return []

    for page_input in page_inputs:
        _delete_active_scope_segments_for_page(
            db,
            tender_id=tender_id,
            source_document_id=page_input.source_document_id,
            document_page_id=page_input.document_page_id,
        )

    ordered_decisions = resolve_scope_ownership_decisions_for_page_inputs(
        tender_id=tender_id,
        page_inputs=page_inputs,
        canonical_items=canonical_items,
    )

    return _persist_decisions(db, decisions=ordered_decisions)


def persist_tender_scope_segments(
    db: Session,
    *,
    tender_id: str,
    page_state: PageStructuralState,
    source_document_id: str,
    document_page_id: str,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
    tender_item_id_by_candidate_key: dict[str, str] | None = None,
) -> list[TenderScopeSegment]:
    input_row = TenderScopeSegmentInput(
        page_state=page_state,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )
    canonical_items = _canonical_references_from_candidate_map(tender_item_id_by_candidate_key)
    return replace_tender_scope_segments_for_page_inputs(
        db,
        tender_id=tender_id,
        page_inputs=[input_row],
        canonical_items=canonical_items,
    )