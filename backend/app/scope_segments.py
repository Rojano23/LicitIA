from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.item_identity import NormalizedItemIdentity
from app.models import TenderScopeSegment
from app.page_structure import PageStructuralSegment, PageStructuralState


@dataclass(frozen=True, slots=True)
class TenderScopeSegmentInput:
    page_state: PageStructuralState
    source_document_id: str
    document_page_id: str
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


def _segment_owner_key(segment: PageStructuralSegment) -> str | None:
    identity: NormalizedItemIdentity = segment.item_identity
    return identity.normalized_key


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


def _segment_link_reason(segment: PageStructuralSegment) -> str:
    if segment.starts_on_this_page:
        return "EXPLICIT_ITEM_START"
    if not segment.starts_on_this_page:
        return "CONTINUATION"
    return "UNKNOWN"


def _segment_source_method(page_state: PageStructuralState) -> str:
    return page_state.provenance.source_method


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
    if page_state.state_quality != "VALID":
        return []

    persisted: list[TenderScopeSegment] = []
    for segment in page_state.segments:
        owner_key = _segment_owner_key(segment)
        if owner_key is None and segment.item_identity.normalized_key is None:
            continue

        tender_item_id = None
        if owner_key is not None and tender_item_id_by_candidate_key is not None:
            tender_item_id = tender_item_id_by_candidate_key.get(owner_key)

        source_method = _segment_source_method(page_state)
        link_reason = _segment_link_reason(segment)
        source_locator = f"page:{page_state.page_number}|segment:{segment.sequence}"
        source_excerpt = segment.anchor_raw_text or ""
        semantic_fingerprint = _build_semantic_fingerprint(
            tender_id=tender_id,
            source_document_id=source_document_id,
            page_number=page_state.page_number,
            sequence_index=segment.sequence,
            owner_key=owner_key,
            source_method=source_method,
            link_reason=link_reason,
            source_locator=source_locator,
            source_excerpt=source_excerpt,
        )

        existing = db.scalar(
            select(TenderScopeSegment).where(
                TenderScopeSegment.tender_id == tender_id,
                TenderScopeSegment.source_document_id == source_document_id,
                TenderScopeSegment.semantic_fingerprint == semantic_fingerprint,
            )
        )
        if existing is not None:
            existing.document_page_id = document_page_id
            existing.page_number = page_state.page_number
            existing.tender_item_id = tender_item_id
            existing.candidate_item_key = owner_key
            existing.candidate_item_raw_label = segment.item_identity.raw_label if owner_key is not None else None
            existing.sequence_index = segment.sequence
            existing.scope_domain = None
            existing.source_method = source_method
            existing.link_reason = link_reason
            existing.source_locator = source_locator
            existing.source_excerpt = source_excerpt
            existing.source_analysis_id = source_analysis_id
            existing.source_page_result_id = source_page_result_id
            existing.confidence = None
            existing.review_required = bool(segment.review_required or page_state.review_required or page_state.state_quality != "VALID")
            persisted.append(existing)
            continue

        row = TenderScopeSegment(
            tender_id=tender_id,
            source_document_id=source_document_id,
            document_page_id=document_page_id,
            page_number=page_state.page_number,
            tender_item_id=tender_item_id,
            candidate_item_key=owner_key,
            candidate_item_raw_label=segment.item_identity.raw_label if owner_key is not None else None,
            sequence_index=segment.sequence,
            scope_domain=None,
            source_method=source_method,
            link_reason=link_reason,
            source_locator=source_locator,
            source_excerpt=source_excerpt,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            confidence=None,
            review_required=bool(segment.review_required or page_state.review_required or page_state.state_quality != "VALID"),
            semantic_fingerprint=semantic_fingerprint,
        )
        db.add(row)
        persisted.append(row)

    return persisted