from __future__ import annotations

from app.item_identity import ITEM_IDENTITY_DETERMINED, ITEM_IDENTITY_UNKNOWN
from app.page_structure import (
    PAGE_STRUCTURE_CONTRACT_VISION_005,
    PAGE_STRUCTURE_SOURCE_METHOD_VISION,
    PAGE_STRUCTURE_UNKNOWN,
    PAGE_STRUCTURE_VALID,
    PageStructuralProvenance,
    PageStructuralSegment,
    PageStructuralState,
    adapt_structure_scope_005_page,
    build_page_structural_state,
)


def _vision_005_page(page_number: int, previous_item_number: str | None, item_segments: list[dict[str, object]], open_item_at_page_end: str | None, continuity_quality: str = "VALID", continues_previous_item: bool = False) -> dict[str, object]:
    return {
        "page_number": page_number,
        "continues_previous_item": continues_previous_item,
        "previous_item_number": previous_item_number,
        "item_segments": item_segments,
        "new_items": [],
        "open_item_at_page_end": open_item_at_page_end,
        "uncertainties": [],
        "_continuity_state_quality": continuity_quality,
    }


def test_page_structural_state_can_be_constructed_without_provider_data() -> None:
    provenance = PageStructuralProvenance(source_method="NATIVE_TEXT", source_analysis_id="analysis-1", source_page_result_id="page-result-1", source_contract_version=None)
    segment = PageStructuralSegment(
        item_identity=adapt_structure_scope_005_page(_vision_005_page(1, None, [{"item_number": "1", "starts_on_this_page": True, "anchor_raw_text": "PARTIDA 1", "review_required": False}], "1")).segments[0].item_identity,
        starts_on_this_page=True,
        sequence=0,
        anchor_raw_text="PARTIDA 1",
        has_service=True,
        has_supply=False,
        has_deliverable=False,
        review_required=False,
    )

    state = build_page_structural_state(
        page_number=1,
        segments=[segment],
        state_quality=PAGE_STRUCTURE_VALID,
        review_required=False,
        provenance=provenance,
        incoming_item_key=None,
        outgoing_item_key="1",
    )

    assert state.page_number == 1
    assert state.incoming_item_key is None
    assert state.outgoing_item_key == "1"
    assert state.segments[0].item_identity.normalized_key == "1"
    assert state.provenance.source_method == "NATIVE_TEXT"
    assert state.state_quality == PAGE_STRUCTURE_VALID
    assert state.review_required is False


def test_vision_005_simple_page_maps_into_neutral_state() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            1,
            None,
            [
                {
                    "item_number": "1",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 1 SERVICIO CENTUM MTBE 1",
                    "review_required": False,
                }
            ],
            "1",
            continues_previous_item=False,
        ),
        source_analysis_id="analysis-1",
        source_page_result_id="page-result-1",
    )

    assert state.page_number == 1
    assert state.incoming_item_key is None
    assert state.outgoing_item_key == "1"
    assert state.state_quality == PAGE_STRUCTURE_VALID
    assert state.review_required is False
    assert state.provenance.source_method == PAGE_STRUCTURE_SOURCE_METHOD_VISION
    assert state.provenance.source_contract_version == PAGE_STRUCTURE_CONTRACT_VISION_005
    assert state.segments[0].item_identity.normalized_key == "1"
    assert state.segments[0].starts_on_this_page is True


def test_vision_005_continuation_page_maps_incoming_and_outgoing_keys() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            2,
            "1",
            [
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
            "1",
            continues_previous_item=True,
        ),
    )

    assert state.incoming_item_key == "1"
    assert state.outgoing_item_key == "1"
    assert state.state_quality == PAGE_STRUCTURE_VALID
    assert state.segments[0].starts_on_this_page is False


def test_vision_005_shared_page_preserves_two_item_ownerships() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            2,
            "1",
            [
                {
                    "item_number": "1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1 EN SITIO",
                    "review_required": False,
                },
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO CENTUM ASFALTOS",
                    "review_required": False,
                },
            ],
            "2",
            continues_previous_item=True,
        ),
    )

    assert state.incoming_item_key == "1"
    assert state.outgoing_item_key == "2"
    assert [segment.item_identity.normalized_key for segment in state.segments] == ["1", "2"]
    assert [segment.starts_on_this_page for segment in state.segments] == [False, True]
    assert state.state_quality == PAGE_STRUCTURE_VALID


def test_vision_005_b4_progression_remains_consistent_across_pages() -> None:
    page_one = adapt_structure_scope_005_page(
        _vision_005_page(
            1,
            None,
            [
                {
                    "item_number": "1",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 1 SERVICIO CENTUM MTBE 1",
                    "review_required": False,
                }
            ],
            "1",
            continues_previous_item=False,
        ),
    )
    page_two = adapt_structure_scope_005_page(
        _vision_005_page(
            2,
            "1",
            [
                {
                    "item_number": "1",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 1 ACTIVIDADES EN SITIO",
                    "review_required": False,
                },
                {
                    "item_number": "2",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 2 MANTENIMIENTO CENTUM ASFALTOS",
                    "review_required": False,
                },
            ],
            "2",
            continues_previous_item=True,
        ),
    )
    page_three = adapt_structure_scope_005_page(
        _vision_005_page(
            3,
            "2",
            [
                {
                    "item_number": "2",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "CONTINUA PARTIDA 2",
                    "review_required": False,
                }
            ],
            "2",
            continues_previous_item=True,
        ),
    )
    page_four = adapt_structure_scope_005_page(
        _vision_005_page(
            4,
            "2",
            [
                {
                    "item_number": "2",
                    "starts_on_this_page": False,
                    "has_service": True,
                    "has_supply": True,
                    "has_deliverable": False,
                    "anchor_raw_text": "LISTADO CONTINUA 2",
                    "review_required": False,
                }
            ],
            "2",
            continues_previous_item=True,
        ),
    )

    assert (page_one.incoming_item_key, page_one.outgoing_item_key) == (None, "1")
    assert (page_two.incoming_item_key, page_two.outgoing_item_key) == ("1", "2")
    assert (page_three.incoming_item_key, page_three.outgoing_item_key) == ("2", "2")
    assert (page_four.incoming_item_key, page_four.outgoing_item_key) == ("2", "2")
    assert page_two.segments[1].item_identity.normalized_key == "2"


def test_vision_005_normalizes_item_identity_from_raw_label() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            1,
            None,
            [
                {
                    "item_number": "01.",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA 01",
                    "review_required": False,
                }
            ],
            "1",
            continues_previous_item=False,
        ),
    )

    segment = state.segments[0]
    assert segment.item_identity.raw_label == "01."
    assert segment.item_identity.normalized_key == "1"
    assert segment.item_identity.state == ITEM_IDENTITY_DETERMINED


def test_vision_005_unknown_item_identity_fails_closed() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            1,
            None,
            [
                {
                    "item_number": "A-1",
                    "starts_on_this_page": True,
                    "has_service": True,
                    "has_supply": False,
                    "has_deliverable": False,
                    "anchor_raw_text": "PARTIDA A-1",
                    "review_required": False,
                }
            ],
            "A-1",
            continues_previous_item=False,
        ),
    )

    segment = state.segments[0]
    assert segment.item_identity.raw_label == "A-1"
    assert segment.item_identity.normalized_key is None
    assert segment.item_identity.state == ITEM_IDENTITY_UNKNOWN
    assert state.state_quality == PAGE_STRUCTURE_UNKNOWN
    assert state.review_required is True
    assert state.incoming_item_key is None
    assert state.outgoing_item_key is None


def test_vision_005_unknown_structural_quality_produces_unknown_state() -> None:
    state = adapt_structure_scope_005_page(
        _vision_005_page(
            2,
            "1",
            [
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
            "1",
            continuity_quality="UNKNOWN",
            continues_previous_item=True,
        ),
    )

    assert state.state_quality == PAGE_STRUCTURE_UNKNOWN
    assert state.review_required is True
    assert state.incoming_item_key is None
    assert state.outgoing_item_key is None


def test_vision_005_missing_item_segments_fails_closed() -> None:
    state = adapt_structure_scope_005_page(
        {
            "page_number": 1,
            "continues_previous_item": False,
            "previous_item_number": None,
            "new_items": [],
            "open_item_at_page_end": None,
            "uncertainties": [],
            "_continuity_state_quality": "VALID",
        },
    )

    assert state.state_quality == PAGE_STRUCTURE_UNKNOWN
    assert state.review_required is True
    assert state.segments == ()
    assert state.incoming_item_key is None
    assert state.outgoing_item_key is None


def test_page_structure_module_is_provider_neutral() -> None:
    import app.page_structure as page_structure_module

    assert page_structure_module.PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT == "NATIVE_TEXT"
    assert page_structure_module.PAGE_STRUCTURE_SOURCE_METHOD_OCR == "OCR"
    assert page_structure_module.PAGE_STRUCTURE_SOURCE_METHOD_VISION == "VISION"
    assert not any(name.startswith(("Vision", "Ollama", "OCR")) for name in vars(page_structure_module))
    assert not hasattr(page_structure_module, "OllamaVisionProvider")
    assert not hasattr(page_structure_module, "VisionAnalysisRead")
    assert not hasattr(page_structure_module, "VisionPageImage")
