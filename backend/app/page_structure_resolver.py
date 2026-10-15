from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from app.item_identity import ITEM_IDENTITY_DETERMINED, NormalizedItemIdentity, normalize_item_identity
from app.page_structure import (
    PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
    PAGE_STRUCTURE_SOURCE_METHOD_OCR,
    PAGE_STRUCTURE_SOURCE_METHOD_VISION,
    PAGE_STRUCTURE_UNKNOWN,
    PAGE_STRUCTURE_VALID,
    PageStructuralProvenance,
    PageStructuralSegment,
    PageStructuralState,
    adapt_structure_scope_005_page,
    build_page_structural_state,
)

RESOLUTION_RESOLVED = "RESOLVED"
RESOLUTION_NEEDS_NATIVE = "NEEDS_NATIVE"
RESOLUTION_NEEDS_OCR = "NEEDS_OCR"
RESOLUTION_NEEDS_VISION = "NEEDS_VISION"
RESOLUTION_REVIEW_REQUIRED = "REVIEW_REQUIRED"

_RESOLUTION_PROVIDER_PREFERENCE = {
    PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT: 0,
    PAGE_STRUCTURE_SOURCE_METHOD_OCR: 1,
    PAGE_STRUCTURE_SOURCE_METHOD_VISION: 2,
    "HYBRID": 3,
}

_EXPLICIT_ITEM_START_RE = re.compile(
    r"(?im)^\s*(?:PARTIDA|CONCEPTO|I[TÍ]EM|ITEM|NO\.?)\s*:?\s*([A-Z]?[- ]?\d+(?:\.\d+)*)\b"
)
_CONTINUATION_MARKER_RE = re.compile(r"(?i)\b(?:CONTINUA|CONTINUACI[OÓ]N)\b")


@dataclass(frozen=True, slots=True)
class StructuralCandidate:
    source_method: str
    structural_quality: str
    page_state: PageStructuralState | None
    evaluated: bool = True
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    acquisition_status: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderAcquisitionState:
    native_evaluated: bool = False
    ocr_evaluated: bool = False
    ocr_applicable: bool = True
    vision_evaluated: bool = False


@dataclass(frozen=True, slots=True)
class OcrStructuralEvidence:
    text: str
    scope: str = "FULL_PAGE"
    region_index: int | None = None
    confidence: float | None = None
    page_ocr_result_id: str | None = None


@dataclass(frozen=True, slots=True)
class PageStructureResolution:
    status: str
    resolved_state: PageStructuralState | None
    resolved_source_method: str | None
    needs_provider: str | None
    reason: str | None
    review_required: bool
    considered_methods: tuple[str, ...] = ()


def _unknown_candidate(
    *,
    page_number: int,
    source_method: str,
    source_analysis_id: str | None,
    source_page_result_id: str | None,
    source_contract_version: str | None,
    reason: str,
) -> StructuralCandidate:
    state = build_page_structural_state(
        page_number=page_number,
        segments=(),
        state_quality=PAGE_STRUCTURE_UNKNOWN,
        review_required=True,
        provenance=PageStructuralProvenance(
            source_method=source_method,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            source_contract_version=source_contract_version,
        ),
        warnings=(reason,),
    )
    return StructuralCandidate(
        source_method=source_method,
        structural_quality=PAGE_STRUCTURE_UNKNOWN,
        page_state=state,
        evaluated=True,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        warnings=(reason,),
    )


def _identity_for_match(raw_item_label: str) -> NormalizedItemIdentity:
    return normalize_item_identity(raw_item_label)


def _extract_explicit_item_starts(text: str) -> list[NormalizedItemIdentity]:
    matches = _EXPLICIT_ITEM_START_RE.findall(text or "")
    identities: list[NormalizedItemIdentity] = []
    for raw_value in matches:
        identity = _identity_for_match(str(raw_value))
        if identity.state == ITEM_IDENTITY_DETERMINED:
            identities.append(identity)
    return identities


def _has_procurement_identity(text: str, match: re.Match[str]) -> bool:
    """Positive row evidence, distinct from recognizing a number/column label.

    Text flattened across columns cannot establish a label-to-number binding.
    Explicit item declarations need a description; generic labels additionally
    need quantity/unit fields bound to that row, not keywords elsewhere on a page.
    """
    anchor = match.group(0).strip()
    if "\n" in anchor or "\r" in anchor:
        return False
    explicit_item_label = bool(re.match(r"(?i)^(?:PARTIDA|I[TÍ]EM|ITEM)\b", anchor))
    remaining_lines = text[match.end():].splitlines()
    tail = (remaining_lines[0] if remaining_lines else "").strip(" .:\t|;-–")
    if not tail and explicit_item_label and len(remaining_lines) > 1:
        # The label and identifier are bound on one line; a following description
        # is legitimate. This never binds a generic column heading to another row.
        tail = remaining_lines[1].strip(" .:\t|;-–")
    if not re.search(r"[^\W\d_]", tail, re.UNICODE):
        return False
    if "?" in tail or "¿" in tail or re.search(r"\.{2,}\s*\d+\s*$", tail):
        return False
    if explicit_item_label:
        return True
    # Require explicit field/value bindings, not a page-level catalog score.
    if (re.search(r"(?i)\b(?:cantidad|quantity|qty)\s*:\s*\d+(?:[.,]\d+)?\b", tail)
            and re.search(r"(?i)\b(?:unidad|unit)\s*:\s*[a-záéíóú]+\b", tail)):
        return True
    # A delimited row may bind values through its immediately preceding header.
    prior = text[:match.start()].rstrip().splitlines()
    if not prior:
        return False
    row = anchor + (remaining_lines[0] if remaining_lines else "")
    for delimiter in ("|", "\t"):
        headers = [cell.strip().casefold() for cell in prior[-1].split(delimiter)]
        values = [cell.strip() for cell in row.split(delimiter)]
        if len(headers) != len(values):
            continue
        quantity = next((i for i, h in enumerate(headers) if h in {"cantidad", "quantity", "qty"}), None)
        unit = next((i for i, h in enumerate(headers) if h in {"unidad", "unit"}), None)
        if quantity is not None and unit is not None:
            if re.fullmatch(r"\d+(?:[.,]\d+)?", values[quantity]) and re.fullmatch(r"[^\W\d_]+\.?", values[unit]):
                return True
    return False


def _identity_review_candidate(*, text: str, page_number: int, source_method: str,
                              source_analysis_id: str | None, source_page_result_id: str | None,
                              source_contract_version: str) -> StructuralCandidate:
    candidate = _unknown_candidate(page_number=page_number, source_method=source_method,
        source_analysis_id=source_analysis_id, source_page_result_id=source_page_result_id,
        source_contract_version=source_contract_version, reason="INSUFFICIENT_PROCUREMENT_ITEM_IDENTITY")
    segments = tuple(PageStructuralSegment(item_identity=_identity_for_match(m.group(1)),
        starts_on_this_page=True, sequence=i, anchor_raw_text=m.group(0).strip(), review_required=True)
        for i, m in enumerate(_EXPLICIT_ITEM_START_RE.finditer(text))
        if _identity_for_match(m.group(1)).state == ITEM_IDENTITY_DETERMINED)
    return replace(candidate, page_state=replace(candidate.page_state, segments=segments))


def _has_continuation_marker(text: str) -> bool:
    return bool(_CONTINUATION_MARKER_RE.search(text or ""))


def _valid_single_segment_state(
    *,
    page_number: int,
    source_method: str,
    item_identity: NormalizedItemIdentity,
    source_analysis_id: str | None,
    source_page_result_id: str | None,
    source_contract_version: str | None,
    source_excerpt: str,
) -> PageStructuralState:
    return build_page_structural_state(
        page_number=page_number,
        segments=(
            PageStructuralSegment(
                item_identity=item_identity,
                starts_on_this_page=True,
                sequence=0,
                anchor_raw_text=source_excerpt,
                has_service=None,
                has_supply=None,
                has_deliverable=None,
                review_required=False,
            ),
        ),
        state_quality=PAGE_STRUCTURE_VALID,
        review_required=False,
        provenance=PageStructuralProvenance(
            source_method=source_method,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            source_contract_version=source_contract_version,
        ),
        incoming_item_key=None,
        outgoing_item_key=item_identity.normalized_key,
    )


def structural_candidate_from_native_text(
    *,
    page_number: int,
    native_text: str,
    source_analysis_id: str | None = None,
    source_page_result_id: str | None = None,
) -> StructuralCandidate:
    explicit_starts = _extract_explicit_item_starts(native_text)
    if not explicit_starts:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            source_contract_version="NATIVE_TEXT_V1",
            reason="NATIVE_NO_EXPLICIT_ITEM_START",
        )

    eligible = [m for m in _EXPLICIT_ITEM_START_RE.finditer(native_text)
                if _has_procurement_identity(native_text, m)]
    if not eligible:
        return _identity_review_candidate(text=native_text, page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT, source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id, source_contract_version="NATIVE_TEXT_V1")
    explicit_starts = [_identity_for_match(m.group(1)) for m in eligible]
    unique_keys = {identity.normalized_key for identity in explicit_starts if identity.normalized_key is not None}
    if _has_continuation_marker(native_text):
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            source_contract_version="NATIVE_TEXT_V1",
            reason="NATIVE_CONTINUATION_REQUIRES_BOUNDARY_PROOF",
        )

    if len(explicit_starts) != 1 or len(unique_keys) != 1:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
            source_analysis_id=source_analysis_id,
            source_page_result_id=source_page_result_id,
            source_contract_version="NATIVE_TEXT_V1",
            reason="NATIVE_AMBIGUOUS_ITEM_OWNERSHIP",
        )

    identity = explicit_starts[0]
    state = _valid_single_segment_state(
        page_number=page_number,
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
        item_identity=identity,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        source_contract_version="NATIVE_TEXT_V1",
        source_excerpt=eligible[0].group(0).strip(),
    )
    return StructuralCandidate(
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
        structural_quality=PAGE_STRUCTURE_VALID,
        page_state=state,
        evaluated=True,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )


def structural_candidate_from_ocr_evidence(
    *,
    page_number: int,
    ocr_evidence: Iterable[OcrStructuralEvidence],
    source_analysis_id: str | None = None,
) -> StructuralCandidate:
    evidence_list = list(ocr_evidence)
    if not evidence_list:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
            source_analysis_id=source_analysis_id,
            source_page_result_id=None,
            source_contract_version="OCR_TEXT_V1",
            reason="OCR_NO_EVIDENCE",
        )

    explicit_starts: list[NormalizedItemIdentity] = []
    has_continuation_marker = False
    for item in evidence_list:
        has_continuation_marker = has_continuation_marker or _has_continuation_marker(item.text)
        explicit_starts.extend(_extract_explicit_item_starts(item.text))

    if not explicit_starts:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
            source_analysis_id=source_analysis_id,
            source_page_result_id=None,
            source_contract_version="OCR_TEXT_V1",
            reason="OCR_NO_EXPLICIT_ITEM_START",
        )

    eligible = [(item, m) for item in evidence_list for m in _EXPLICIT_ITEM_START_RE.finditer(item.text)
                if _has_procurement_identity(item.text, m)]
    if not eligible:
        source = next(item for item in evidence_list if _EXPLICIT_ITEM_START_RE.search(item.text))
        return _identity_review_candidate(text="\n".join(item.text for item in evidence_list), page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR, source_analysis_id=source_analysis_id,
            source_page_result_id=source.page_ocr_result_id, source_contract_version="OCR_TEXT_V1")
    explicit_starts = [_identity_for_match(m.group(1)) for _, m in eligible]
    unique_keys = {identity.normalized_key for identity in explicit_starts if identity.normalized_key is not None}
    if has_continuation_marker:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
            source_analysis_id=source_analysis_id,
            source_page_result_id=None,
            source_contract_version="OCR_TEXT_V1",
            reason="OCR_CONTINUATION_REQUIRES_BOUNDARY_PROOF",
        )

    if len(explicit_starts) != 1 or len(unique_keys) != 1:
        return _unknown_candidate(
            page_number=page_number,
            source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
            source_analysis_id=source_analysis_id,
            source_page_result_id=None,
            source_contract_version="OCR_TEXT_V1",
            reason="OCR_AMBIGUOUS_ITEM_OWNERSHIP",
        )

    evidence, anchor = eligible[0]
    identity = explicit_starts[0]
    state = _valid_single_segment_state(
        page_number=page_number,
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
        item_identity=identity,
        source_analysis_id=source_analysis_id,
        source_page_result_id=evidence.page_ocr_result_id,
        source_contract_version="OCR_TEXT_V1",
        source_excerpt=anchor.group(0).strip(),
    )
    return StructuralCandidate(
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
        structural_quality=PAGE_STRUCTURE_VALID,
        page_state=state,
        evaluated=True,
        source_analysis_id=source_analysis_id,
        source_page_result_id=evidence.page_ocr_result_id,
    )


def structural_candidate_from_vision_005(
    *,
    structured_json: dict | None,
    page_number: int,
    source_analysis_id: str | None,
    source_page_result_id: str | None,
) -> StructuralCandidate:
    page_state = adapt_structure_scope_005_page(
        structured_json,
        page_number=page_number,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )
    return StructuralCandidate(
        source_method=PAGE_STRUCTURE_SOURCE_METHOD_VISION,
        structural_quality=page_state.state_quality,
        page_state=page_state,
        evaluated=True,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )


def _state_signature(page_state: PageStructuralState) -> tuple | None:
    if page_state.state_quality != PAGE_STRUCTURE_VALID:
        return None
    ordered_segments = sorted(page_state.segments, key=lambda segment: segment.sequence)
    signature_segments: list[tuple[int, str | None, bool]] = []
    for segment in ordered_segments:
        signature_segments.append(
            (
                segment.sequence,
                segment.item_identity.normalized_key,
                bool(segment.starts_on_this_page),
            )
        )
    return (
        page_state.incoming_item_key,
        page_state.outgoing_item_key,
        tuple(signature_segments),
    )


def _candidate_selection_key(candidate: StructuralCandidate) -> tuple[int, str, str, str]:
    provider_rank = _RESOLUTION_PROVIDER_PREFERENCE.get(candidate.source_method, 999)
    return (
        provider_rank,
        candidate.source_method,
        candidate.source_analysis_id or "",
        candidate.source_page_result_id or "",
    )


def _resolve_next_acquisition_step(
    *,
    candidates: Sequence[StructuralCandidate],
    acquisition_state: ProviderAcquisitionState,
) -> PageStructureResolution:
    evaluated_methods = {candidate.source_method for candidate in candidates if candidate.evaluated}
    native_evaluated = acquisition_state.native_evaluated or PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT in evaluated_methods
    ocr_evaluated = acquisition_state.ocr_evaluated or PAGE_STRUCTURE_SOURCE_METHOD_OCR in evaluated_methods
    vision_evaluated = acquisition_state.vision_evaluated or PAGE_STRUCTURE_SOURCE_METHOD_VISION in evaluated_methods

    considered_methods = tuple(sorted(evaluated_methods))
    if not native_evaluated:
        return PageStructureResolution(
            status=RESOLUTION_NEEDS_NATIVE,
            resolved_state=None,
            resolved_source_method=None,
            needs_provider=PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
            reason="NATIVE_NOT_EVALUATED",
            review_required=False,
            considered_methods=considered_methods,
        )

    if not ocr_evaluated and acquisition_state.ocr_applicable:
        return PageStructureResolution(
            status=RESOLUTION_NEEDS_OCR,
            resolved_state=None,
            resolved_source_method=None,
            needs_provider=PAGE_STRUCTURE_SOURCE_METHOD_OCR,
            reason="OCR_NOT_EVALUATED",
            review_required=False,
            considered_methods=considered_methods,
        )

    if not vision_evaluated:
        return PageStructureResolution(
            status=RESOLUTION_NEEDS_VISION,
            resolved_state=None,
            resolved_source_method=None,
            needs_provider=PAGE_STRUCTURE_SOURCE_METHOD_VISION,
            reason="VISION_NOT_EVALUATED",
            review_required=False,
            considered_methods=considered_methods,
        )

    return PageStructureResolution(
        status=RESOLUTION_REVIEW_REQUIRED,
        resolved_state=None,
        resolved_source_method=None,
        needs_provider=None,
        reason="ALL_CANDIDATES_UNKNOWN_AFTER_VISION",
        review_required=True,
        considered_methods=considered_methods,
    )


def resolve_page_structure(
    *,
    candidates: Sequence[StructuralCandidate],
    acquisition_state: ProviderAcquisitionState,
) -> PageStructureResolution:
    evaluated_candidates = [candidate for candidate in candidates if candidate.evaluated]
    considered_methods = tuple(sorted({candidate.source_method for candidate in evaluated_candidates}))

    valid_candidates: list[tuple[StructuralCandidate, tuple]] = []
    for candidate in evaluated_candidates:
        if candidate.page_state is None:
            continue
        if candidate.structural_quality != PAGE_STRUCTURE_VALID:
            continue
        signature = _state_signature(candidate.page_state)
        if signature is None:
            continue
        valid_candidates.append((candidate, signature))

    if not valid_candidates:
        return _resolve_next_acquisition_step(candidates=evaluated_candidates, acquisition_state=acquisition_state)

    signatures = {signature for _, signature in valid_candidates}
    if len(signatures) > 1:
        return PageStructureResolution(
            status=RESOLUTION_REVIEW_REQUIRED,
            resolved_state=None,
            resolved_source_method=None,
            needs_provider=None,
            reason="CONFLICTING_VALID_STRUCTURES",
            review_required=True,
            considered_methods=considered_methods,
        )

    chosen_candidate = sorted((candidate for candidate, _ in valid_candidates), key=_candidate_selection_key)[0]
    return PageStructureResolution(
        status=RESOLUTION_RESOLVED,
        resolved_state=chosen_candidate.page_state,
        resolved_source_method=chosen_candidate.source_method,
        needs_provider=None,
        reason="CONSISTENT_VALID_CANDIDATE",
        review_required=bool(chosen_candidate.page_state.review_required if chosen_candidate.page_state else False),
        considered_methods=considered_methods,
    )