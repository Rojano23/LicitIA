from __future__ import annotations

import inspect

from app.page_structure import (
    PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
    PAGE_STRUCTURE_SOURCE_METHOD_OCR,
    PAGE_STRUCTURE_SOURCE_METHOD_VISION,
    PAGE_STRUCTURE_UNKNOWN,
    PAGE_STRUCTURE_VALID,
)
from app.page_structure_resolver import (
    OcrStructuralEvidence,
    ProviderAcquisitionState,
    RESOLUTION_NEEDS_OCR,
    RESOLUTION_NEEDS_VISION,
    RESOLUTION_RESOLVED,
    RESOLUTION_REVIEW_REQUIRED,
    resolve_page_structure,
    structural_candidate_from_native_text,
    structural_candidate_from_ocr_evidence,
    structural_candidate_from_vision_005,
)


def _vision_payload(
    *,
    page_number: int,
    continues_previous_item: bool,
    previous_item_number: str | None,
    segments: list[dict[str, object]],
    open_item_at_page_end: str | None,
    continuity_quality: str = "VALID",
) -> dict[str, object]:
    return {
        "page_number": page_number,
        "continues_previous_item": continues_previous_item,
        "previous_item_number": previous_item_number,
        "item_segments": segments,
        "new_items": [],
        "open_item_at_page_end": open_item_at_page_end,
        "uncertainties": [],
        "_continuity_state_quality": continuity_quality,
    }


def test_native_simple_explicit_single_item_is_valid() -> None:
    candidate = structural_candidate_from_native_text(
        page_number=1,
        native_text="PARTIDA 01: Servicio de mantenimiento",
    )

    assert candidate.structural_quality == PAGE_STRUCTURE_VALID
    assert candidate.page_state is not None
    assert candidate.page_state.segments[0].item_identity.normalized_key == "1"
    assert candidate.page_state.incoming_item_key is None
    assert candidate.page_state.outgoing_item_key == "1"


def test_native_ambiguous_shared_page_flat_text_is_unknown() -> None:
    candidate = structural_candidate_from_native_text(
        page_number=2,
        native_text="CONTINUA PARTIDA 1\nPARTIDA 2: Equipos y materiales",
    )

    assert candidate.structural_quality == PAGE_STRUCTURE_UNKNOWN
    assert candidate.page_state is not None
    assert candidate.page_state.state_quality == PAGE_STRUCTURE_UNKNOWN


def test_ocr_simple_explicit_single_item_is_valid() -> None:
    candidate = structural_candidate_from_ocr_evidence(
        page_number=1,
        ocr_evidence=[
            OcrStructuralEvidence(
                text="PARTIDA 1: SUMINISTRO DE EQUIPO",
                scope="FULL_PAGE",
                confidence=0.99,
                page_ocr_result_id="ocr-1",
            )
        ],
    )

    assert candidate.structural_quality == PAGE_STRUCTURE_VALID
    assert candidate.page_state is not None
    assert candidate.page_state.segments[0].item_identity.normalized_key == "1"


def test_ocr_high_confidence_but_ambiguous_shared_page_is_unknown() -> None:
    candidate = structural_candidate_from_ocr_evidence(
        page_number=2,
        ocr_evidence=[
            OcrStructuralEvidence(
                text="CONTINUA PARTIDA 1\nPARTIDA 2: HERRAMIENTAS",
                scope="FULL_PAGE",
                confidence=0.995,
                page_ocr_result_id="ocr-2",
            )
        ],
    )

    assert candidate.structural_quality == PAGE_STRUCTURE_UNKNOWN


def test_vision_005_shared_page_candidate_is_valid() -> None:
    candidate = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=2,
            continues_previous_item=True,
            previous_item_number="1",
            segments=[
                {
                    "item_number": "1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1",
                    "review_required": False,
                },
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2",
                    "review_required": False,
                },
            ],
            open_item_at_page_end="2",
        ),
        page_number=2,
        source_analysis_id="vision-analysis-1",
        source_page_result_id="vision-page-2",
    )

    assert candidate.structural_quality == PAGE_STRUCTURE_VALID
    assert candidate.page_state is not None
    assert [segment.item_identity.normalized_key for segment in candidate.page_state.segments] == ["1", "2"]


def test_resolver_uses_native_when_valid_and_no_conflict() -> None:
    native = structural_candidate_from_native_text(
        page_number=1,
        native_text="PARTIDA 1: SERVICIO",
    )
    ocr_unknown = structural_candidate_from_ocr_evidence(
        page_number=1,
        ocr_evidence=[OcrStructuralEvidence(text="Texto sin item")],
    )

    resolution = resolve_page_structure(
        candidates=[native, ocr_unknown],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=False),
    )

    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT
    assert resolution.resolved_state is not None


def test_resolver_uses_ocr_when_native_unknown_and_ocr_valid() -> None:
    native = structural_candidate_from_native_text(
        page_number=1,
        native_text="Texto plano sin estructura",
    )
    ocr = structural_candidate_from_ocr_evidence(
        page_number=1,
        ocr_evidence=[OcrStructuralEvidence(text="PARTIDA 1: SUMINISTRO")],
    )

    resolution = resolve_page_structure(
        candidates=[native, ocr],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=False),
    )

    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_OCR


def test_resolver_requests_vision_when_native_ocr_unknown_and_vision_not_evaluated() -> None:
    native = structural_candidate_from_native_text(page_number=2, native_text="Texto sin item")
    ocr = structural_candidate_from_ocr_evidence(
        page_number=2,
        ocr_evidence=[OcrStructuralEvidence(text="CONTINUA PARTIDA 1")],
    )

    resolution = resolve_page_structure(
        candidates=[native, ocr],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=False),
    )

    assert resolution.status == RESOLUTION_NEEDS_VISION
    assert resolution.needs_provider == PAGE_STRUCTURE_SOURCE_METHOD_VISION


def test_resolver_uses_vision_valid_after_earlier_unknowns() -> None:
    native = structural_candidate_from_native_text(page_number=2, native_text="Texto plano")
    ocr = structural_candidate_from_ocr_evidence(page_number=2, ocr_evidence=[OcrStructuralEvidence(text="Sin partida")])
    vision = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=2,
            continues_previous_item=True,
            previous_item_number="1",
            segments=[
                {
                    "item_number": "1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1",
                    "review_required": False,
                }
            ],
            open_item_at_page_end="1",
        ),
        page_number=2,
        source_analysis_id="vision-analysis",
        source_page_result_id="vision-page",
    )

    resolution = resolve_page_structure(
        candidates=[native, ocr, vision],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=True),
    )

    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_VISION


def test_resolver_consistent_valid_structures_choose_deterministically() -> None:
    native = structural_candidate_from_native_text(page_number=1, native_text="PARTIDA 01: SERVICIO")
    vision = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=1,
            continues_previous_item=False,
            previous_item_number=None,
            segments=[
                {
                    "item_number": "1",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 1",
                    "review_required": False,
                }
            ],
            open_item_at_page_end="1",
        ),
        page_number=1,
        source_analysis_id="vision-analysis",
        source_page_result_id="vision-page",
    )

    resolution = resolve_page_structure(
        candidates=[vision, native],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=False, vision_evaluated=True),
    )

    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT


def test_resolver_conflicting_valid_structures_require_review() -> None:
    ocr = structural_candidate_from_ocr_evidence(
        page_number=3,
        ocr_evidence=[OcrStructuralEvidence(text="PARTIDA 1: SUMINISTRO")],
    )
    vision = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=3,
            continues_previous_item=False,
            previous_item_number=None,
            segments=[
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2",
                    "review_required": False,
                }
            ],
            open_item_at_page_end="2",
        ),
        page_number=3,
        source_analysis_id="vision-analysis",
        source_page_result_id="vision-page",
    )

    resolution = resolve_page_structure(
        candidates=[ocr, vision],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=True),
    )

    assert resolution.status == RESOLUTION_REVIEW_REQUIRED
    assert resolution.resolved_state is None
    assert resolution.reason == "CONFLICTING_VALID_STRUCTURES"


def test_all_unknown_after_vision_attempt_is_review_required() -> None:
    native = structural_candidate_from_native_text(page_number=4, native_text="sin estructura")
    ocr = structural_candidate_from_ocr_evidence(page_number=4, ocr_evidence=[OcrStructuralEvidence(text="sin item")])
    vision = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=4,
            continues_previous_item=True,
            previous_item_number="A-1",
            segments=[
                {
                    "item_number": "A-1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA A-1",
                    "review_required": False,
                }
            ],
            open_item_at_page_end="A-1",
            continuity_quality="VALID",
        ),
        page_number=4,
        source_analysis_id="vision-analysis",
        source_page_result_id="vision-page",
    )

    assert vision.structural_quality == PAGE_STRUCTURE_UNKNOWN

    resolution = resolve_page_structure(
        candidates=[native, ocr, vision],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=True),
    )

    assert resolution.status == RESOLUTION_REVIEW_REQUIRED
    assert resolution.reason == "ALL_CANDIDATES_UNKNOWN_AFTER_VISION"


def test_item_identity_normalization_matches_across_native_and_ocr_adapters() -> None:
    native = structural_candidate_from_native_text(page_number=1, native_text="PARTIDA 01.: Servicio")
    ocr = structural_candidate_from_ocr_evidence(
        page_number=1,
        ocr_evidence=[OcrStructuralEvidence(text="PARTIDA 1: Servicio")],
    )

    assert native.page_state is not None
    assert ocr.page_state is not None
    assert native.page_state.segments[0].item_identity.normalized_key == ocr.page_state.segments[0].item_identity.normalized_key


def test_resolver_requests_ocr_after_native_unknown_when_ocr_not_evaluated() -> None:
    native = structural_candidate_from_native_text(page_number=5, native_text="sin item")
    resolution = resolve_page_structure(
        candidates=[native],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=False, vision_evaluated=False),
    )

    assert resolution.status == RESOLUTION_NEEDS_OCR
    assert resolution.needs_provider == PAGE_STRUCTURE_SOURCE_METHOD_OCR


def test_hybrid_sequence_keeps_per_page_provenance_and_allows_unknown_ocr_page() -> None:
    p1_ocr = structural_candidate_from_ocr_evidence(
        page_number=1,
        ocr_evidence=[OcrStructuralEvidence(text="PARTIDA 1: SERVICIO", page_ocr_result_id="ocr-p1")],
    )
    p2_vision = structural_candidate_from_vision_005(
        structured_json=_vision_payload(
            page_number=2,
            continues_previous_item=True,
            previous_item_number="1",
            segments=[
                {
                    "item_number": "1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1",
                    "review_required": False,
                },
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2",
                    "review_required": False,
                },
            ],
            open_item_at_page_end="2",
        ),
        page_number=2,
        source_analysis_id="vision-a",
        source_page_result_id="vision-p2",
    )
    p3_ocr_unknown = structural_candidate_from_ocr_evidence(
        page_number=3,
        ocr_evidence=[OcrStructuralEvidence(text="CONTINUA PARTIDA 2")],
    )

    r1 = resolve_page_structure(
        candidates=[p1_ocr],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=False),
    )
    r2 = resolve_page_structure(
        candidates=[p2_vision],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=True),
    )
    r3 = resolve_page_structure(
        candidates=[p3_ocr_unknown],
        acquisition_state=ProviderAcquisitionState(native_evaluated=True, ocr_evaluated=True, vision_evaluated=False),
    )

    assert r1.status == RESOLUTION_RESOLVED
    assert r1.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_OCR
    assert r2.status == RESOLUTION_RESOLVED
    assert r2.resolved_source_method == PAGE_STRUCTURE_SOURCE_METHOD_VISION
    assert r3.status == RESOLUTION_NEEDS_VISION


def test_resolver_module_is_provider_neutral_and_does_not_call_live_engines() -> None:
    import app.page_structure_resolver as resolver_module

    source = inspect.getsource(resolver_module)
    forbidden_tokens = [
        "OllamaVisionAssistClient",
        "urllib.request",
        "PaddleOCR",
        "pytesseract",
        "build_default_ocr_provider_registry",
        "recognize(",
    ]
    assert all(token not in source for token in forbidden_tokens)
