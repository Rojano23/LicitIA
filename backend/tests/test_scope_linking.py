from __future__ import annotations

import inspect

from app.item_identity import normalize_item_identity
from app.page_structure import PAGE_STRUCTURE_UNKNOWN, PAGE_STRUCTURE_VALID, PageStructuralProvenance, PageStructuralSegment, build_page_structural_state
from app.scope_linking import (
    CanonicalTenderItemReference,
    CONTINUITY_NOTE_CANONICAL_AMBIGUOUS,
    CONTINUITY_NOTE_MISMATCH_RESET,
    LINK_REASON_CONTINUATION,
    LINK_REASON_EXPLICIT_ITEM_START,
    ScopeLinkingPageInput,
    link_scope_ownership_decisions,
)


def _segment(raw_item: str, *, starts: bool, sequence: int, review_required: bool = False, anchor: str | None = None) -> PageStructuralSegment:
    return PageStructuralSegment(
        item_identity=normalize_item_identity(raw_item),
        starts_on_this_page=starts,
        sequence=sequence,
        anchor_raw_text=anchor or f"PARTIDA {raw_item}",
        has_service=True,
        has_supply=False,
        has_deliverable=False,
        review_required=review_required,
    )


def _state(
    page_number: int,
    *,
    segments: list[PageStructuralSegment],
    incoming: str | None,
    outgoing: str | None,
    quality: str = PAGE_STRUCTURE_VALID,
    review_required: bool = False,
    source_method: str = "VISION",
):
    return build_page_structural_state(
        page_number=page_number,
        segments=segments,
        state_quality=quality,
        review_required=review_required,
        provenance=PageStructuralProvenance(
            source_method=source_method,
            source_analysis_id="analysis-test",
            source_page_result_id="page-result-test",
            source_contract_version="VISION_STRUCTURE_SCOPE_005",
        ),
        incoming_item_key=incoming,
        outgoing_item_key=outgoing,
    )


def _page_input(document_id: str, page_id: str, state) -> ScopeLinkingPageInput:
    return ScopeLinkingPageInput(source_document_id=document_id, document_page_id=page_id, page_state=state)


def test_simple_explicit_item_start_yields_single_decision() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-1",
        page_inputs=[
            _page_input(
                "doc-a",
                "page-a1",
                _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1"),
            )
        ],
    )

    assert len(decisions) == 1
    assert decisions[0].candidate_item_key == "1"
    assert decisions[0].link_reason == LINK_REASON_EXPLICIT_ITEM_START


def test_normal_continuation_keeps_both_page_decisions() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-1",
        page_inputs=[
            _page_input("doc-a", "page-a1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input("doc-a", "page-a2", _state(2, segments=[_segment("1", starts=False, sequence=0)], incoming="1", outgoing="1")),
        ],
    )

    assert [(item.page_number, item.sequence_index, item.link_reason) for item in decisions] == [
        (1, 0, LINK_REASON_EXPLICIT_ITEM_START),
        (2, 0, LINK_REASON_CONTINUATION),
    ]


def test_shared_page_preserves_continuation_and_start_order() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-1",
        page_inputs=[
            _page_input(
                "doc-a",
                "page-a2",
                _state(
                    2,
                    segments=[
                        _segment("1", starts=False, sequence=0),
                        _segment("2", starts=True, sequence=1),
                    ],
                    incoming="1",
                    outgoing="2",
                ),
            )
        ],
    )

    assert [(item.sequence_index, item.candidate_item_key, item.link_reason) for item in decisions] == [
        (0, "1", LINK_REASON_CONTINUATION),
        (1, "2", LINK_REASON_EXPLICIT_ITEM_START),
    ]


def test_synthetic_b4_progression_maps_expected_ownership() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-b4",
        page_inputs=[
            _page_input("doc-b4", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input(
                "doc-b4",
                "p2",
                _state(
                    2,
                    segments=[
                        _segment("1", starts=False, sequence=0),
                        _segment("2", starts=True, sequence=1),
                    ],
                    incoming="1",
                    outgoing="2",
                ),
            ),
            _page_input("doc-b4", "p3", _state(3, segments=[_segment("2", starts=False, sequence=0)], incoming="2", outgoing="2")),
            _page_input("doc-b4", "p4", _state(4, segments=[_segment("2", starts=False, sequence=0)], incoming="2", outgoing="2")),
        ],
    )

    by_item = {
        "1": [(item.page_number, item.sequence_index) for item in decisions if item.candidate_item_key == "1"],
        "2": [(item.page_number, item.sequence_index) for item in decisions if item.candidate_item_key == "2"],
    }
    assert by_item["1"] == [(1, 0), (2, 0)]
    assert by_item["2"] == [(2, 1), (3, 0), (4, 0)]


def test_unknown_gap_breaks_continuity_without_stale_propagation() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-gap",
        page_inputs=[
            _page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input("doc-a", "p2", _state(2, segments=[], incoming="1", outgoing=None, quality=PAGE_STRUCTURE_UNKNOWN, review_required=True)),
            _page_input(
                "doc-a",
                "p3",
                _state(3, segments=[_segment("A-1", starts=False, sequence=0)], incoming="1", outgoing=None, quality=PAGE_STRUCTURE_VALID),
            ),
        ],
    )

    assert [(item.page_number, item.candidate_item_key) for item in decisions] == [(1, "1")]


def test_explicit_recovery_after_unknown_gap_is_allowed() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-gap",
        page_inputs=[
            _page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input("doc-a", "p2", _state(2, segments=[], incoming="1", outgoing=None, quality=PAGE_STRUCTURE_UNKNOWN, review_required=True)),
            _page_input("doc-a", "p3", _state(3, segments=[_segment("3", starts=True, sequence=0)], incoming=None, outgoing="3")),
        ],
    )

    assert [(item.page_number, item.candidate_item_key) for item in decisions] == [(1, "1"), (3, "3")]


def test_continuity_mismatch_keeps_local_owner_but_marks_review() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-mismatch",
        page_inputs=[
            _page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input("doc-a", "p2", _state(2, segments=[_segment("2", starts=False, sequence=0)], incoming="2", outgoing="2")),
        ],
    )

    second = [item for item in decisions if item.page_number == 2][0]
    assert second.candidate_item_key == "2"
    assert second.review_required is True
    assert second.continuity_note == CONTINUITY_NOTE_MISMATCH_RESET


def test_unique_canonical_match_populates_tender_item_id() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-can",
        page_inputs=[_page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1"))],
        canonical_items=[CanonicalTenderItemReference(tender_item_id="item-1", item_number="01.")],
    )

    assert decisions[0].tender_item_id == "item-1"


def test_no_canonical_match_keeps_candidate_only() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-can",
        page_inputs=[_page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1"))],
        canonical_items=[CanonicalTenderItemReference(tender_item_id="item-3", item_number="3")],
    )

    assert decisions[0].tender_item_id is None


def test_duplicate_canonical_normalized_match_requires_review() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-can",
        page_inputs=[_page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1"))],
        canonical_items=[
            CanonicalTenderItemReference(tender_item_id="item-a", item_number="1"),
            CanonicalTenderItemReference(tender_item_id="item-b", item_number="01"),
        ],
    )

    assert decisions[0].tender_item_id is None
    assert decisions[0].review_required is True
    assert decisions[0].continuity_note == CONTINUITY_NOTE_CANONICAL_AMBIGUOUS


def test_candidate_raw_label_is_preserved_after_canonical_match() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-can",
        page_inputs=[_page_input("doc-a", "p1", _state(1, segments=[_segment("01.", starts=True, sequence=0)], incoming=None, outgoing="1"))],
        canonical_items=[CanonicalTenderItemReference(tender_item_id="item-1", item_number="1")],
    )

    assert decisions[0].candidate_item_key == "1"
    assert decisions[0].candidate_item_raw_label == "01."
    assert decisions[0].tender_item_id == "item-1"


def test_document_boundary_resets_continuity() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-doc-boundary",
        page_inputs=[
            _page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0)], incoming=None, outgoing="1")),
            _page_input("doc-b", "p1", _state(1, segments=[_segment("1", starts=False, sequence=0)], incoming="1", outgoing="1")),
        ],
    )

    second = [item for item in decisions if item.source_document_id == "doc-b"][0]
    assert second.review_required is False


def test_review_flags_propagate_from_page_and_segment() -> None:
    decisions = link_scope_ownership_decisions(
        tender_id="tender-review",
        page_inputs=[
            _page_input("doc-a", "p1", _state(1, segments=[_segment("1", starts=True, sequence=0, review_required=False)], incoming=None, outgoing="1", review_required=True)),
            _page_input("doc-a", "p2", _state(2, segments=[_segment("1", starts=False, sequence=0, review_required=True)], incoming="1", outgoing="1", review_required=False)),
        ],
    )

    assert [item.review_required for item in decisions] == [True, True]


def test_scope_linking_module_has_no_provider_specific_dependencies() -> None:
    import app.scope_linking as scope_linking_module

    source = inspect.getsource(scope_linking_module)
    forbidden_tokens = ["ollama", "ocr", "VisionAssist", "DocumentVisionAnalysis", "DocumentVisionPageResult"]
    assert all(token not in source for token in forbidden_tokens)
