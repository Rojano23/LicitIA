from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.item_identity import ITEM_IDENTITY_DETERMINED, ITEM_IDENTITY_UNKNOWN, NormalizedItemIdentity, normalize_item_identity

PAGE_STRUCTURE_VALID = "VALID"
PAGE_STRUCTURE_UNKNOWN = "UNKNOWN"
PAGE_STRUCTURE_SOURCE_METHOD_VISION = "VISION"
PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT = "NATIVE_TEXT"
PAGE_STRUCTURE_SOURCE_METHOD_OCR = "OCR"
PAGE_STRUCTURE_CONTRACT_VISION_005 = "VISION_STRUCTURE_SCOPE_005"


@dataclass(frozen=True, slots=True)
class PageStructuralProvenance:
    source_method: str
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    source_contract_version: str | None = None


@dataclass(frozen=True, slots=True)
class PageStructuralSegment:
    item_identity: NormalizedItemIdentity
    starts_on_this_page: bool
    sequence: int
    anchor_raw_text: str | None = None
    has_service: bool | None = None
    has_supply: bool | None = None
    has_deliverable: bool | None = None
    review_required: bool = True


@dataclass(frozen=True, slots=True)
class PageStructuralState:
    page_number: int
    incoming_item_key: str | None
    outgoing_item_key: str | None
    segments: tuple[PageStructuralSegment, ...]
    state_quality: str
    review_required: bool
    provenance: PageStructuralProvenance
    warnings: tuple[str, ...] = ()


def _normalize_page_number(value: Any) -> int | None:
    try:
        page_number = int(value)
    except (TypeError, ValueError):
        return None
    return page_number if page_number > 0 else None


def _normalize_anchor_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _normalized_key_or_none(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    identity = normalize_item_identity(str(raw_value))
    return identity.normalized_key


def build_page_structural_state(
    *,
    page_number: int,
    segments: list[PageStructuralSegment] | tuple[PageStructuralSegment, ...],
    state_quality: str,
    review_required: bool,
    provenance: PageStructuralProvenance,
    incoming_item_key: str | None = None,
    outgoing_item_key: str | None = None,
    warnings: list[str] | tuple[str, ...] = (),
) -> PageStructuralState:
    return PageStructuralState(
        page_number=page_number,
        incoming_item_key=incoming_item_key,
        outgoing_item_key=outgoing_item_key,
        segments=tuple(segments),
        state_quality=state_quality,
        review_required=review_required,
        provenance=provenance,
        warnings=tuple(warnings),
    )


def adapt_structure_scope_005_page(
    structured_json: Mapping[str, Any] | None,
    *,
    page_number: int | None = None,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
    source_contract_version: str | None = PAGE_STRUCTURE_CONTRACT_VISION_005,
) -> PageStructuralState:
    resolved_page_number = _normalize_page_number(page_number if page_number is not None else (structured_json or {}).get("page_number"))
    provenance = PageStructuralProvenance(
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_VISION,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        source_contract_version=source_contract_version,
    )

    if resolved_page_number is None or not isinstance(structured_json, Mapping):
        return build_page_structural_state(
            page_number=resolved_page_number or 0,
            segments=[],
            state_quality=PAGE_STRUCTURE_UNKNOWN,
            review_required=True,
            provenance=provenance,
            warnings=("UNSUPPORTED_STRUCTURAL_SHAPE",),
        )

    item_segments = structured_json.get("item_segments")
    if not isinstance(item_segments, list):
        return build_page_structural_state(
            page_number=resolved_page_number,
            segments=[],
            state_quality=PAGE_STRUCTURE_UNKNOWN,
            review_required=True,
            provenance=provenance,
            warnings=("MISSING_ITEM_SEGMENTS",),
        )

    continuity_quality = str(structured_json.get("_continuity_state_quality") or PAGE_STRUCTURE_UNKNOWN).upper()
    previous_item_key = _normalized_key_or_none(structured_json.get("previous_item_number"))
    outgoing_item_key = _normalized_key_or_none(structured_json.get("open_item_at_page_end"))
    continues_previous_item = bool(structured_json.get("continues_previous_item"))

    segments: list[PageStructuralSegment] = []
    warnings: list[str] = []
    unknown_identity_count = 0

    for sequence, raw_segment in enumerate(item_segments):
        if not isinstance(raw_segment, Mapping):
            warnings.append("UNSUPPORTED_SEGMENT_SHAPE")
            unknown_identity_count += 1
            continue

        item_identity = normalize_item_identity(str(raw_segment.get("item_number") or ""))
        if item_identity.state != ITEM_IDENTITY_DETERMINED:
            unknown_identity_count += 1

        anchor_raw_text = _normalize_anchor_text(raw_segment.get("anchor_raw_text"))
        segment = PageStructuralSegment(
            item_identity=item_identity,
            starts_on_this_page=bool(raw_segment.get("starts_on_this_page")),
            sequence=sequence,
            anchor_raw_text=anchor_raw_text,
            has_service=_optional_bool(raw_segment.get("has_service")),
            has_supply=_optional_bool(raw_segment.get("has_supply")),
            has_deliverable=_optional_bool(raw_segment.get("has_deliverable")),
            review_required=bool(raw_segment.get("review_required", True)) or item_identity.state != ITEM_IDENTITY_DETERMINED,
        )
        segments.append(segment)

    state_quality = PAGE_STRUCTURE_VALID
    incoming_item_key: str | None = None

    if continuity_quality != PAGE_STRUCTURE_VALID or not segments or unknown_identity_count > 0:
        state_quality = PAGE_STRUCTURE_UNKNOWN
        warnings.append("STRUCTURAL_STATE_UNRESOLVED")
        outgoing_item_key = None
    else:
        if continues_previous_item and previous_item_key is not None:
            incoming_item_key = previous_item_key
        if outgoing_item_key is None and segments:
            last_segment_key = segments[-1].item_identity.normalized_key
            outgoing_item_key = last_segment_key

    if state_quality != PAGE_STRUCTURE_VALID:
        review_required = True
    else:
        review_required = any(segment.review_required for segment in segments)

    return build_page_structural_state(
        page_number=resolved_page_number,
        segments=segments,
        state_quality=state_quality,
        review_required=review_required,
        provenance=provenance,
        incoming_item_key=incoming_item_key,
        outgoing_item_key=outgoing_item_key,
        warnings=warnings,
    )