"""CP synthetic contracts + real test-DB JSONB; no perception accuracy claims."""
from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.critical_identifier_comparison import (
    IdentifierKind as K, compare_identifiers,
    identifier_observation, normalize_identifier,
)
from app.document_intelligence import Capability as C, PageIdentity, PerceptionEvidence, Quality as Q, RoutingResult, SourceMethod as S, route_capability
from app.item_identity import normalize_item_identity
from app.page_structure import PageStructuralProvenance, PageStructuralSegment, build_page_structural_state
from app.models import RequirementCandidateEvidence
from app.requirement_di_adapter import candidate_perception
from app.requirement_extraction import analyze_tender_requirements
from app.requirement_perception_provenance import (
    RequirementPerceptionProvenanceV2, provenance_from_routing, provenance_from_routings,
    read_provenance, serialize_provenance, write_provenance,
)
from app.schemas import RequirementCandidateEvidenceRead
from test_requirement_perception_provenance import logical  # shared rollback-only DB fixture


def page():
    return PageIdentity(tender_id="synthetic", document_id="doc", document_page_id="page", page_number=1, document_version="rev-A")


def source(value="2", capability=C.TRANSCRIPTION, method=S.NATIVE, lineage="ACTIVE", quality=Q.RELIABLE, identity=None):
    identity = identity or page()
    text = "Item " + value
    fields = {}
    if capability == C.STRUCTURE:
        fields['structural_state'] = build_page_structural_state(page_number=identity.page_number,
            state_quality="VALID", review_required=False,
            provenance=PageStructuralProvenance(source_method=method.value, source_analysis_id="analysis",
                source_page_result_id="result", source_contract_version="synthetic-v1"),
            segments=(PageStructuralSegment(item_identity=normalize_item_identity("3"), sequence=0,
                starts_on_this_page=True, anchor_raw_text=text, review_required=False),),
            incoming_item_key=None, outgoing_item_key="3")
    return PerceptionEvidence(page=identity, capability=capability, source_method=method,
        source_artifact_key=f"{method.value}:{capability.value}", generation_id="generation",
        source_analysis_id="analysis", source_page_result_id="result", source_contract_version="synthetic-v1",
        normalized_content_id="normalized", source_locator="page:1|row:1", coordinates=(1., 2., 3., 4.),
        confidence=90., confidence_scale="percent", lineage=lineage, quality=quality, text=text,
        provider_metadata=(("model", "synthetic"),), **fields)


def route(sources):
    return route_capability(page=sources[0].page, capability=sources[0].capability, evidence=sources)


def observation(s, value=None, kind=K.ITEM_NUMBER, binding="row:1:owner"):
    return identifier_observation(kind=kind, binding_key=binding,
        raw_value=value if value is not None else s.text.removeprefix("Item "), excerpt=s.text, source=s)


def pair(identity=None, **second):
    a = source(identity=identity)
    b = source("3", C.STRUCTURE, S.VISION, identity=identity, **second)
    comparison = compare_identifiers(kind=K.ITEM_NUMBER, binding_key="row:1:owner",
        observations=(observation(a), observation(b)))
    return provenance_from_routings((route((a,)), route((b,))), comparisons=(comparison,))


def roundtrip(v):
    payload = serialize_provenance(v)
    actual = read_provenance(payload)
    assert serialize_provenance(actual) == payload
    return actual


def test_CP01_v1_readable():
    payload = serialize_provenance(provenance_from_routing(route((source(),))))
    assert read_provenance(payload).schema_version == "1"
    assert read_provenance(None) is None


def test_CP02_transcription_roundtrip():
    v = roundtrip(provenance_from_routings((route((source(),)),)))
    assert v.routing_contexts[0].capability == C.TRANSCRIPTION
    assert v.routing_contexts[0].selected.source_method == S.NATIVE


def test_CP03_structure_roundtrip():
    v = roundtrip(provenance_from_routings((route((source(capability=C.STRUCTURE),)),)))
    assert v.routing_contexts[0].capability == C.STRUCTURE
    assert v.routing_contexts[0].routing_status == "RESOLVED"


def test_CP04_contexts_coexist():
    assert {r.capability for r in roundtrip(pair()).routing_contexts} == {C.TRANSCRIPTION, C.STRUCTURE}


def test_CP05_values_exact():
    observations = roundtrip(pair()).identifier_comparisons[0].observations
    assert {(o.source.capability, o.raw_value, o.normalized_value) for o in observations} == {(C.TRANSCRIPTION, "2", "2"), (C.STRUCTURE, "3", "3")}


def test_CP06_conflict_jsonb_roundtrip(logical):
    db, row, identity = logical
    expected = write_provenance(row, pair(identity))
    db.flush(); db.expire(row)
    assert read_provenance(row.perception_provenance) == expected
    assert expected.identifier_comparisons[0].status == "CONFLICT"


def test_CP07_original_capabilities():
    assert {o.source.capability for o in roundtrip(pair()).identifier_comparisons[0].observations} == {C.TRANSCRIPTION, C.STRUCTURE}


def test_CP08_full_provenance():
    for o in roundtrip(pair()).identifier_comparisons[0].observations:
        s = o.source
        assert s.page == page() and s.source_locator == "page:1|row:1"
        assert s.coordinates == (1., 2., 3., 4.)
        assert (s.generation_id, s.source_analysis_id, s.source_page_result_id, s.normalized_content_id) == ("generation", "analysis", "result", "normalized")
        assert s.confidence == 90. and s.confidence_scale == "percent"
        assert o.raw_value in o.excerpt and o.excerpt in s.text


def test_CP09_active_conflict():
    c = pair().identifier_comparisons[0]
    assert c.status == "CONFLICT" and c.contractually_critical


def test_CP10_deselected_history():
    c = roundtrip(pair(lineage="DESELECTED")).identifier_comparisons[0]
    assert c.status == "INSUFFICIENT_EVIDENCE"
    assert {o.source.lineage for o in c.observations} == {"ACTIVE", "DESELECTED"}


def test_CP11_unavailable_no_value():
    bad = source("3", C.STRUCTURE, S.VISION, quality=Q.UNAVAILABLE)
    with pytest.raises(ValidationError, match="cannot supply"):
        observation(bad)
    v = provenance_from_routings((route((source(),)), route((bad,))))
    assert not roundtrip(v).identifier_comparisons
    assert next(c for c in v.routing_contexts if c.capability == C.STRUCTURE).selected is None


def test_CP12_deterministic_serialization():
    v = pair(); payload = serialize_provenance(v)
    reversed_payload = deepcopy(payload)
    reversed_payload['routing_contexts'].reverse()
    reversed_payload['identifier_comparisons'][0]['observations'].reverse()
    for context in reversed_payload['routing_contexts']:
        context['candidates'].reverse()
    assert serialize_provenance(read_provenance(reversed_payload)) == payload


def test_CP13_unknown_version():
    for version in ("3", "99", 2):
        with pytest.raises(ValidationError):
            read_provenance({**serialize_provenance(pair()), "schema_version": version})


def test_CP14_malformed_v2():
    payload = serialize_provenance(pair())
    patches = ({'unknown': True}, {'routing_contexts': []}, {'identifier_comparisons': [{'kind': 'ITEM_NUMBER'}]})
    for patch in patches:
        with pytest.raises(ValidationError):
            read_provenance({**payload, **patch})
    bad = deepcopy(payload)
    bad['identifier_comparisons'][0]['observations'][0]['raw_value'] = 'fabricated'
    with pytest.raises(ValidationError):
        read_provenance(bad)


def test_CP15_v1_no_comparisons():
    v = read_provenance(serialize_provenance(provenance_from_routing(route((source(),)))))
    assert v.schema_version == "1" and not hasattr(v, 'identifier_comparisons')


@pytest.mark.parametrize('a,b,kind', [pytest.param('1','01', K.ITEM_NUMBER, id='CP16'),
    pytest.param('TAG-101','TAG-10I', K.EQUIPMENT_TAG, id='CP17'),
    pytest.param('A-1','A1', K.DOCUMENT_REFERENCE, id='CP18'),
    pytest.param('X100','X100A', K.MODEL_IDENTIFIER, id='CP19')])
def test_distinctions(a,b,kind):
    c = compare_identifiers(kind=kind, binding_key='row:1:owner',
        observations=(observation(source(a), kind=kind), observation(source(b, method=S.OCR), kind=kind)))
    assert c.status == 'CONFLICT'
    assert {o.normalized_value for o in c.observations} == {a,b}


def test_CP20_safe_whitespace():
    a, b = source('  TAG-101  '), source('TAG-101', method=S.OCR)
    c = compare_identifiers(kind=K.EQUIPMENT_TAG, binding_key='row:1:owner', observations=(observation(a, kind=K.EQUIPMENT_TAG), observation(b, kind=K.EQUIPMENT_TAG)))
    assert c.status == 'AGREEMENT' and len(c.observations) == 2
    assert normalize_identifier('Rev A') != normalize_identifier('Rev B')
    assert normalize_identifier('10 EA') != normalize_identifier('10 SET')
    assert normalize_identifier('A') != normalize_identifier('a')


def test_CP21_raw_preserved():
    o = observation(source('  01  '))
    assert o.raw_value == '  01  ' and o.normalized_value == '01'


def test_CP22_preference_not_conflict_resolution():
    v = pair()
    assert all(context.selected is not None for context in v.routing_contexts)
    assert v.identifier_comparisons[0].status == 'CONFLICT'
    a,b = source('2'), source('2', method=S.OCR)
    assert route((b,a)).selected.source_method == S.NATIVE
    comparison = v.identifier_comparisons[0]
    assert compare_identifiers(kind=comparison.kind, binding_key=comparison.binding_key,
        observations=tuple(reversed(comparison.observations))).status == 'CONFLICT'


def test_CP23_multiple_comparisons():
    v = pair(); first = v.identifier_comparisons[0]
    second = compare_identifiers(kind=K.QUANTITY_BINDING_IDENTIFIER, binding_key='row:1:quantity-owner',
        observations=tuple(observation(o.source, kind=K.QUANTITY_BINDING_IDENTIFIER, binding='row:1:quantity-owner') for o in first.observations))
    assert len(roundtrip(RequirementPerceptionProvenanceV2(page=v.page, routing_contexts=v.routing_contexts,
        identifier_comparisons=(second, first))).identifier_comparisons) == 2


def test_CP24_repeated_jsonb_persistence(logical):
    db,row,identity = logical
    first = write_provenance(row, pair(identity)); db.flush(); db.expire(row)
    snapshot = deepcopy(row.perception_provenance)
    second = write_provenance(row, pair(identity)); db.flush(); db.expire(row)
    assert first == second == read_provenance(row.perception_provenance)
    assert row.perception_provenance == snapshot


def test_CP25_logical_dedup_unchanged(logical):
    db,row,identity = logical
    key = (row.id,row.source_document_id,row.source_page,row.excerpt_sha256)
    write_provenance(row, pair(identity)); db.flush()
    before_review = candidate_perception(row.candidate)
    analyze_tender_requirements(db, identity.tender_id)
    rows = db.scalars(select(RequirementCandidateEvidence).where(RequirementCandidateEvidence.candidate_id == row.candidate_id)).all()
    assert len(rows) == 1 and (rows[0].id,rows[0].source_document_id,rows[0].source_page,rows[0].excerpt_sha256) == key
    v = read_provenance(rows[0].perception_provenance)
    assert v.schema_version == '2' and len(v.routing_contexts) == 2
    assert len(v.identifier_comparisons[0].observations) == 2
    assert before_review == (False, True)  # existing absence-of-support semantics; fixture requirement is not Item 2
    snapshot = deepcopy(rows[0].perception_provenance)
    analyze_tender_requirements(db, identity.tender_id)
    assert rows[0].perception_provenance == snapshot


def test_routing_stays_single_capability():
    with pytest.raises(ValidationError, match='requested page and capability'):
        RoutingResult(page=page(), capability=C.TRANSCRIPTION, status='REVIEW_REQUIRED',
            candidates=(source(), source('3', C.STRUCTURE, S.VISION)))


def test_malformed_status_context_and_grounding_fail_closed():
    v = pair(); payload = serialize_provenance(v)
    bad = deepcopy(payload); bad['identifier_comparisons'][0]['status'] = 'AGREEMENT'
    with pytest.raises(ValidationError, match='status contradicts'):
        read_provenance(bad)
    bad = deepcopy(payload); bad['routing_contexts'][0]['capability'] = 'SEMANTIC_ASSIST'
    with pytest.raises(ValidationError):
        read_provenance(bad)
    bad = deepcopy(payload); bad['identifier_comparisons'][0]['observations'][0]['source']['generation_id'] = 'unconsidered'
    with pytest.raises(ValidationError, match='routing context source'):
        read_provenance(bad)
    bad = deepcopy(payload); bad['identifier_comparisons'][0]['observations'][0]['unknown'] = True
    with pytest.raises(ValidationError):
        read_provenance(bad)


def test_history_cannot_be_erased_or_downgraded(logical):
    _, row, identity = logical
    v = pair(identity); write_provenance(row,v)
    saved = deepcopy(row.perception_provenance)
    dropped = RequirementPerceptionProvenanceV2(page=v.page, routing_contexts=v.routing_contexts)
    with pytest.raises(ValueError, match='retain prior identifier'):
        write_provenance(row,dropped)
    with pytest.raises(ValueError):
        write_provenance(row,route((source(identity=identity),)))
    assert row.perception_provenance == saved


def test_explicit_v1_upgrade_retains_history(logical):
    _,row,identity = logical
    legacy = route((source(identity=identity),))
    write_provenance(row,legacy)
    assert row.perception_provenance['schema_version'] == '1'
    assert write_provenance(row,pair(identity)).schema_version == '2'


def test_api_union_and_critical_comparison_propagates_domain_review(logical):
    _,row,identity = logical
    a = source(identity=identity).model_copy(update={'text': row.source_excerpt + '\nItem 2'})
    b = source('3', C.STRUCTURE, S.VISION, identity=identity)
    routes = (route((a,)), route((b,)))
    write_provenance(row,routes[0])
    baseline = candidate_perception(row.candidate)
    c = compare_identifiers(kind=K.ITEM_NUMBER, binding_key='row:1:owner',
        observations=(observation(a,value='2'), observation(b)))
    v = provenance_from_routings(routes, comparisons=(c,))
    write_provenance(row,v)
    assert baseline == (True,False)
    assert candidate_perception(row.candidate) == (True,True)
    response = RequirementCandidateEvidenceRead(id=row.id,source_document_id=row.source_document_id,
        source_excerpt=row.source_excerpt, perception_provenance=read_provenance(row.perception_provenance))
    assert response.model_dump(mode='json')['perception_provenance']['schema_version'] == '2'
    assert response.perception_provenance.identifier_comparisons[0].status == 'CONFLICT'


def test_comparison_empty_uncertain_failed_and_duplicates():
    assert compare_identifiers(kind=K.ITEM_NUMBER,binding_key='owner', observations=()).status == 'NOT_APPLICABLE'
    uncertain = observation(source(quality=Q.REVIEW_REQUIRED))
    assert compare_identifiers(kind=K.ITEM_NUMBER,binding_key=uncertain.binding_key, observations=(uncertain,)).status == 'INSUFFICIENT_EVIDENCE'
    with pytest.raises(ValidationError):
        observation(source(quality=Q.FAILED))
    with pytest.raises(ValidationError,match='Duplicate observation'):
        compare_identifiers(kind=K.ITEM_NUMBER,binding_key=uncertain.binding_key, observations=(uncertain,uncertain))


def test_semantic_assist_context_retains_review():
    s = source(capability=C.SEMANTIC_ASSIST).model_copy(update={'bounded_grounded':True})
    v = roundtrip(provenance_from_routings((route((s,)),)))
    assert v.routing_contexts[0].capability == C.SEMANTIC_ASSIST
    assert v.routing_contexts[0].routing_status == 'REVIEW_REQUIRED'


def test_structure_only_v2_does_not_fabricate_requirement_support(logical):
    _,row,identity = logical
    write_provenance(row,provenance_from_routings((route((source('3', C.STRUCTURE, S.VISION, identity=identity),)),)))
    assert candidate_perception(row.candidate) == (False,True)
