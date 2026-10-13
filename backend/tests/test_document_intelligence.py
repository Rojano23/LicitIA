"""Synthetic perception contracts only: no OCR/Vision quality certification."""
from itertools import permutations

import pytest
from pydantic import ValidationError

from app.document_intelligence import (
    Capability as C, CapabilityAvailability, CriticalIdentifier, PageIdentity,
    PerceptionEvidence, Quality as Q, SourceMethod as S, advance_continuity,
    normalize_perception_evidence, route_capability,
)
from app.page_structure import PageStructuralProvenance, PageStructuralSegment, build_page_structural_state
from app.item_identity import normalize_item_identity


def page(number=1, document="doc"):
    return PageIdentity(tender_id="synthetic-tender", document_id=document,
                        document_page_id=f"{document}-page-{number}", page_number=number, document_version="v1")


def evidence(method=S.NATIVE, capability=C.TRANSCRIPTION, quality=Q.RELIABLE, number=1,
             text="PARTIDA 1 servicio", incoming=None, outgoing="1", artifact=None, **fields):
    if capability == C.STRUCTURE:
        state = build_page_structural_state(
            page_number=number, state_quality="VALID", review_required=False,
            provenance=PageStructuralProvenance(source_method=method.value),
            segments=(PageStructuralSegment(item_identity=normalize_item_identity(outgoing),
                        starts_on_this_page=incoming is None, sequence=0,
                        anchor_raw_text=text, review_required=False),),
            incoming_item_key=incoming, outgoing_item_key=outgoing)
        fields["structural_state"] = state
    return PerceptionEvidence(page=page(number), source_method=method, capability=capability,
        quality=quality, text=text, generation_id="generation-1",
        source_artifact_key=artifact or f"{method.value}-{capability.value}-{number}", **fields)


def route(*items, capability=C.TRANSCRIPTION, number=1, **kwargs):
    return route_capability(page=page(number), capability=capability, evidence=items, **kwargs)


def vision_available(capability=C.TRANSCRIPTION):
    return (CapabilityAvailability(capability=capability, source_method=S.VISION, available=True),)


def test_DI01_good_native_selected():
    native = evidence()
    assert route(evidence(S.VISION), evidence(S.OCR), native).selected == native


def test_DI02_missing_native_uses_ocr():
    ocr = evidence(S.OCR)
    assert route(ocr).selected == ocr


def test_DI03_unreliable_native_uses_reliable_ocr():
    ocr = evidence(S.OCR)
    assert route(evidence(quality=Q.REVIEW_REQUIRED), ocr).selected == ocr


def test_DI04_vision_eligible_not_executed():
    result = route(availability=vision_available())
    assert result.status == "REVIEW_REQUIRED" and result.selected is None
    assert result.fallback_requires_real_vision
    assert result.diagnostics == ("VISION_ELIGIBLE_EXECUTION_DEFERRED",)


def test_DI05_all_unavailable_fail_closed():
    result = route(evidence(quality=Q.UNAVAILABLE), evidence(S.OCR, quality=Q.UNAVAILABLE))
    assert result.status == "UNAVAILABLE" and result.selected is None


def test_DI06_native_text_vision_structure_same_page():
    native, vision = evidence(), evidence(S.VISION, C.STRUCTURE)
    assert route(native, vision).selected == native
    assert route(native, vision, capability=C.STRUCTURE).selected == vision


def test_DI07_structure_survives_failed_detail():
    structure, detail = evidence(S.VISION, C.STRUCTURE), evidence(S.VISION, quality=Q.FAILED)
    assert route(structure, detail, capability=C.STRUCTURE).status == "RESOLVED"
    assert route(structure, detail).status == "REVIEW_REQUIRED"


def test_DI08_transcription_does_not_imply_structure():
    native = evidence()
    assert route(native).status == "RESOLVED"
    assert route(native, capability=C.STRUCTURE).status == "UNAVAILABLE"


def test_DI09_failed_current_structure_clears_old_boundary():
    previous = advance_continuity(route(evidence(capability=C.STRUCTURE), capability=C.STRUCTURE))
    failed = route(evidence(capability=C.STRUCTURE, number=2, quality=Q.FAILED), capability=C.STRUCTURE, number=2)
    current = advance_continuity(failed, previous)
    assert current.status == "UNKNOWN" and current.outgoing_item_key is None and current.structural_state is None
    following = route(evidence(S.OCR, C.STRUCTURE, number=3, incoming="1"), capability=C.STRUCTURE, number=3)
    assert advance_continuity(following, current).status == "UNKNOWN"


def test_DI10_mixed_provider_continuity():
    previous = None
    for number, method in enumerate((S.NATIVE, S.VISION, S.OCR), 1):
        result = route(evidence(method, C.STRUCTURE, number=number, incoming="1" if number > 1 else None),
                       capability=C.STRUCTURE, number=number)
        previous = advance_continuity(result, previous)
        assert previous.status == "VALID" and previous.evidence.source_method == method


def test_DI11_provider_change_does_not_reset_valid_boundary():
    first = advance_continuity(route(evidence(capability=C.STRUCTURE), capability=C.STRUCTURE))
    second = advance_continuity(route(evidence(S.VISION, C.STRUCTURE, number=2, incoming="1"),
                                      capability=C.STRUCTURE, number=2), first)
    assert second.status == "VALID" and second.outgoing_item_key == "1"


def test_DI12_noncritical_text_conflict_explicit():
    a, b = evidence(text="Servicio A"), evidence(S.OCR, text="Servicio B")
    result = route(b, a)
    assert result.status == "REVIEW_REQUIRED" and result.selected is None
    assert result.conflicts[0].kind == "TEXTUAL"
    assert result.conflicts[0].alternatives == (a, b)


def test_DI13_critical_identifier_conflict_preserves_grounded_alternatives():
    a = evidence(text="TAG X1", critical_identifiers=(CriticalIdentifier(binding_key="tag:row1", value="X1", excerpt="TAG X1"),))
    b = evidence(S.OCR, text="TAG X7", critical_identifiers=(CriticalIdentifier(binding_key="tag:row1", value="X7", excerpt="TAG X7"),))
    result = route(a, b)
    conflict = next(c for c in result.conflicts if c.kind == "IDENTIFIER")
    assert result.status == "REVIEW_REQUIRED" and conflict.binding_key == "tag:row1"
    assert {i.value for e in conflict.alternatives for i in e.critical_identifiers} == {"X1", "X7"}


def test_DI14_provenance_preserved_exactly():
    original = evidence(source_locator="page:1|block:2", coordinates=(1, 2, 3, 4),
        source_analysis_id="analysis", source_page_result_id="result", normalized_content_id="normalized",
        source_contract_version="contract-v1", confidence=87, confidence_scale="percent",
        diagnostics=("provider-warning",))
    assert route(original).selected == original
    assert PerceptionEvidence.model_validate_json(original.model_dump_json()) == original


def test_DI15_active_vision_lineage_selected():
    active = evidence(S.VISION, lineage="ACTIVE")
    assert route(active).selected == active


def test_DI16_deselected_vision_never_selected():
    old = evidence(S.VISION, lineage="DESELECTED")
    result = route(old)
    assert result.status == "UNAVAILABLE" and result.selected is None and result.candidates == (old,)


def test_DI17_semantic_assistance_is_not_contractual_truth():
    assist = evidence(S.VISION, C.SEMANTIC_ASSIST, bounded_grounded=True)
    result = route(assist, capability=C.SEMANTIC_ASSIST)
    assert result.selected == assist and result.status == "REVIEW_REQUIRED"
    assert not result.contractual_authority and not assist.contractual_authority
    unbounded = evidence(S.VISION, C.SEMANTIC_ASSIST)
    assert route(unbounded, capability=C.SEMANTIC_ASSIST).selected is None


def test_DI18_metadata_does_not_change_channel():
    original = evidence(S.VISION, provider_metadata=(("provider", "OLLAMA"), ("model", "QWEN")))
    assert route(original).selected.source_method == S.VISION
    with pytest.raises(ValidationError):
        PerceptionEvidence.model_validate({**original.model_dump(), "source_method": "QWEN"})


def test_DI19_pure_idempotent_routing():
    original = evidence()
    before = original.model_dump_json()
    assert route(original) == route(original)
    assert original.model_dump_json() == before


def test_DI20_candidate_order_deterministic():
    items = (evidence(S.VISION), evidence(S.OCR, artifact="z"), evidence(S.OCR, artifact="a"))
    expected = route(*items)
    for order in permutations(items):
        assert route(*order) == expected


def test_DI21_timestamp_upload_order_not_precedence():
    old = evidence(text="valor 1", provider_metadata=(("created_at", "2000-01-01"),))
    new = evidence(S.VISION, text="valor 2", provider_metadata=(("created_at", "2099-01-01"),))
    assert route(old, new) == route(new, old)
    assert route(old, new).selected is None


def test_DI22_failed_vision_preserves_native():
    native = evidence()
    assert route(native, evidence(S.VISION, quality=Q.FAILED)).selected == native


def test_DI23_failed_ocr_preserves_structure():
    structure = evidence(S.VISION, C.STRUCTURE)
    assert route(structure, evidence(S.OCR, C.STRUCTURE, quality=Q.FAILED), capability=C.STRUCTURE).selected == structure


def test_DI24_capability_availability_independent():
    assert route(availability=vision_available(C.STRUCTURE)).status == "UNAVAILABLE"
    assert route(capability=C.STRUCTURE, availability=vision_available(C.STRUCTURE)).fallback_requires_real_vision


def test_DI25_no_hidden_fallback_or_other_page_reuse():
    previous = evidence(number=1)
    result = route(previous, number=2)
    assert result.status == "UNAVAILABLE" and not result.candidates and result.selected is None
    with pytest.raises(ValueError):
        advance_continuity(route(previous))


def test_structural_disagreement_requires_review():
    a = evidence(capability=C.STRUCTURE)
    b = evidence(S.VISION, C.STRUCTURE, text="PARTIDA 2", outgoing="2")
    result = route(a, b, capability=C.STRUCTURE)
    assert result.status == "REVIEW_REQUIRED"
    assert result.conflicts[0].kind == "STRUCTURAL"
    assert advance_continuity(result).status == "UNKNOWN"


def test_untrusted_structure_and_empty_text_are_not_success():
    original = evidence(capability=C.STRUCTURE)
    state = build_page_structural_state(page_number=1, segments=(), state_quality="UNKNOWN", review_required=True,
                                       provenance=PageStructuralProvenance(source_method="NATIVE"))
    invalid = PerceptionEvidence.model_validate({**original.model_dump(), "structural_state": state})
    assert route(invalid, capability=C.STRUCTURE).selected is None
    assert route(evidence(text="")).selected is None


def test_normalization_defaults_fail_closed_and_rejects_missing_source():
    original = evidence()
    fields = original.model_dump(exclude={"source_method", "quality"})
    neutral = normalize_perception_evidence(source_method="NATIVE_PDF", **fields)
    assert neutral.source_method == S.NATIVE and neutral.quality == Q.REVIEW_REQUIRED
    with pytest.raises(ValidationError):
        normalize_perception_evidence(source_method="OCR", **{**fields, "source_artifact_key": ""})
    with pytest.raises(ValidationError):
        evidence(critical_identifiers=(CriticalIdentifier(binding_key="tag", value="invented", excerpt="invented"),))


def test_continuity_cannot_cross_document_or_page_gap():
    previous = advance_continuity(route(evidence(capability=C.STRUCTURE), capability=C.STRUCTURE))
    gap = route(evidence(capability=C.STRUCTURE, number=3, incoming="1"), capability=C.STRUCTURE, number=3)
    assert advance_continuity(gap, previous).status == "UNKNOWN"
    other_page = page(2, document="other")
    other = evidence(capability=C.STRUCTURE, number=2, incoming="1")
    other = PerceptionEvidence.model_validate({**other.model_dump(), "page": other_page})
    result = route_capability(page=other_page, capability=C.STRUCTURE, evidence=(other,))
    assert advance_continuity(result, previous).status == "UNKNOWN"


def test_invalid_result_and_boundary_contracts_are_rejected():
    from app.document_intelligence import RoutingResult, StructuralContinuity
    with pytest.raises(ValidationError):
        RoutingResult(page=page(), capability=C.TRANSCRIPTION, status="RESOLVED")
    with pytest.raises(ValidationError):
        StructuralContinuity(page=page(), status="UNKNOWN", outgoing_item_key="old")
    with pytest.raises(ValidationError):
        StructuralContinuity(page=page(), status="VALID")
    with pytest.raises(ValidationError):
        evidence(confidence=99)
    with pytest.raises(ValidationError):
        evidence(coordinates=(2, 2, 1, 1))
    with pytest.raises(ValidationError):
        PageIdentity(document_id=" ", document_page_id="page", page_number=1)


def test_structural_provenance_mismatch_is_rejected():
    original = evidence(capability=C.STRUCTURE)
    with pytest.raises(ValidationError):
        PerceptionEvidence.model_validate({**original.model_dump(), "source_method": "VISION"})
    with pytest.raises(ValidationError):
        PerceptionEvidence.model_validate({**original.model_dump(), "source_analysis_id": "different"})
