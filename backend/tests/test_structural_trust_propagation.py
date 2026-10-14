"""Synthetic structural safety contracts; no provider or Golden needed."""
from pathlib import Path

from app.document_intelligence import (Capability, PageIdentity, PerceptionEvidence, Quality, RoutingResult,
    SourceMethod, advance_continuity, route_capability)
from app.item_identity import normalize_item_identity
from app.page_structure import PageStructuralProvenance, PageStructuralSegment, build_page_structural_state
from app.scope_detail_adapters import ScopeDetailEvidenceArtifact, adapt_and_persist_scope_detail_artifact
from app.scope_details import ScopeDetailCandidate
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from app.models import TenderScopeDetail, TenderScopeQuantity, TenderScopeAttribute
from sqlalchemy import select
from test_requirement_perception_provenance import logical
from test_critical_identifier_propagation import Adapter, STABLE
from test_cross_capability_provenance import source, route
from test_document_intelligence_integration import vision


def observation(number=1, key='17', incoming=None, outgoing='17', method=SourceMethod.NATIVE, transition=False, anchor=None):
    identity=PageIdentity(tender_id='synthetic',document_id='doc',document_page_id=f'p{number}',document_version='1',page_number=number)
    segments=[]
    if transition:
        segments.append(PageStructuralSegment(normalize_item_identity(incoming),False,0,f'Item {incoming}',review_required=False))
    segments.append(PageStructuralSegment(normalize_item_identity(key),incoming is None or transition,len(segments),anchor or f'Item {key}',review_required=False))
    state=build_page_structural_state(page_number=number,segments=segments,state_quality='VALID',review_required=False,
        provenance=PageStructuralProvenance(method.value),incoming_item_key=incoming,outgoing_item_key=outgoing)
    evidence=PerceptionEvidence(page=identity,source_method=method,capability=Capability.STRUCTURE,quality=Quality.RELIABLE,
        text='\n'.join(s.anchor_raw_text for s in segments),generation_id='synthetic',source_artifact_key=f'artifact:{number}',structural_state=state)
    return route_capability(page=identity,capability=Capability.STRUCTURE,evidence=(evidence,))


def first():return advance_continuity(observation())
def conflict():return advance_continuity(observation(2,key='23',outgoing='23',anchor='service only'),first())


def test_ST01_continuation():assert advance_continuity(observation(2,incoming='17'),first()).status=='VALID'
def test_ST02_transition():
    assert advance_continuity(observation(2,key='23',incoming='17',outgoing='23',transition=True),first()).status=='VALID'
    closed=advance_continuity(observation(outgoing=None))
    assert advance_continuity(observation(2,key='23',outgoing='23'),closed).status=='VALID'
def test_ST03_unexplained_start():assert conflict().diagnostics==('STRUCTURAL_BOUNDARY_CONFLICT',)
def test_ST04_incompatible_incoming():assert advance_continuity(observation(2,key='23',incoming='23'),first()).status=='UNKNOWN'
def test_ST05_missing():
    result=observation(2)
    missing=route_capability(page=result.page,capability=Capability.STRUCTURE,evidence=())
    state=advance_continuity(missing,first())
    assert state.status=='UNKNOWN' and 'STRUCTURAL_BOUNDARY_CONFLICT' not in state.diagnostics

def test_ST06_no_stale():assert conflict().outgoing_item_key is None and conflict().structural_state is None
def test_ST07_no_replacement():
    current=advance_continuity(observation(3,key='41',outgoing='41',anchor='service only'),conflict())
    assert current.status=='UNKNOWN' and current.outgoing_item_key is None
def test_ST08_recovery():assert advance_continuity(observation(3,key='41',outgoing='41'),conflict()).status=='VALID'
def test_ST09_locality():
    old=first();bad=advance_continuity(observation(2,key='23',outgoing='23'),old)
    assert old.status=='VALID' and bad.status=='UNKNOWN'
    assert advance_continuity(observation(3,key='41',outgoing='41'),bad).status=='VALID'


def owner_details(logical):
    db,_,identity=logical
    text='Item 17 Modelo X100 equipo (10 piezas)'
    from app.models import TenderDocument,DocumentPage
    from copy import deepcopy
    row=vision(db,db.get(TenderDocument,identity.document_id),db.get(DocumentPage,identity.document_page_id),text=text)
    payload=deepcopy(row.structured_json)
    payload['detail_transcription']['parsed_supply_rows']=[{'description':text,'raw_visible_text':text,
        'model':'X100','quantity':'10','unit':'EA','review_required':False}]
    row.structured_json=payload;db.flush()
    transcription=route((source(identity=identity,method=SourceMethod.VISION).model_copy(update={
        'text':text+'\n'+STABLE,'source_artifact_key':f'vision-page-result:{row.id}'}),))
    structure=RoutingResult(page=identity,capability=Capability.STRUCTURE,status='REVIEW_REQUIRED',
        diagnostics=('STRUCTURAL_BOUNDARY_CONFLICT',))
    artifact=ScopeDetailEvidenceArtifact(tender_id=identity.tender_id,source_document_id=identity.document_id,
        document_page_id=identity.document_page_id,source_method='VISION',source_artifact_key=transcription.selected.source_artifact_key,
        transcription=transcription,structure=structure,payload=payload)
    def candidate(excerpt,key):
        return ScopeDetailCandidate(tender_id=identity.tender_id,source_document_id=identity.document_id,
            document_page_id=identity.document_page_id,domain='SUPPLY',description=excerpt,source_excerpt=excerpt,
            applicability='ITEM' if key else 'TENDER_WIDE',candidate_item_key=key,review_required=False,
            source_method='VISION',source_artifact_key=artifact.source_artifact_key,source_locator='page:1|detail_row:0')
    candidates=(candidate(text,'17'),candidate(STABLE,None))
    for _ in range(2):adapt_and_persist_scope_detail_artifact(db,artifact,adapters=(Adapter(candidates),))
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key==artifact.source_artifact_key)).all()
    return db,rows

def test_ST10_scope(logical):
    _,rows=owner_details(logical);bad=next(r for r in rows if r.source_excerpt!=STABLE)
    assert bad.review_required and bad.applicability=='UNRESOLVED'
    assert bad.candidate_item_key is bad.scope_segment_id is bad.tender_item_id is None

def test_ST11_quantity(logical):
    db,rows=owner_details(logical)
    bad=next(r for r in rows if r.source_excerpt!=STABLE)
    materialize_scope_quantities_for_scope_detail(db,scope_detail_id=bad.id)
    row=db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id==bad.id))
    assert row is not None and row.review_required

def test_ST12_attribute(logical):
    db,rows=owner_details(logical);bad=next(r for r in rows if r.source_excerpt!=STABLE)
    materialize_scope_attributes_for_scope_detail(db,scope_detail_id=bad.id)
    row=db.scalar(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id==bad.id))
    assert row is not None and row.review_required

def test_ST13_unrelated(logical):assert not next(r for r in owner_details(logical)[1] if r.source_excerpt==STABLE).review_required

def provider_check(method):
    previous=advance_continuity(observation(method=method))
    assert advance_continuity(observation(2,key='23',outgoing='23',method=method),previous).status=='UNKNOWN'
    assert advance_continuity(observation(2,incoming='17',method=method),previous).status=='VALID'
def test_ST14_native():provider_check(SourceMethod.NATIVE)
def test_ST15_ocr():provider_check(SourceMethod.OCR)
def test_ST16_vision():provider_check(SourceMethod.VISION)
def test_ST17_provider_alone():
    for method in SourceMethod:assert advance_continuity(observation(method=method)).status=='VALID'
def test_ST18_idempotence():assert conflict()==conflict()
def test_ST19_no_duplicate_diagnostics():assert len(conflict().diagnostics)==len(set(conflict().diagnostics))==1

def test_ST20_no_golden_dependency(monkeypatch):
    original=Path.read_bytes
    def protected(path,*args,**kwargs):
        assert 'golden' not in str(path).lower() and '/evals/' not in str(path)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_bytes',protected)
    original_text=Path.read_text
    def protected_text(path,*args,**kwargs):
        assert 'golden' not in str(path).lower() and '/evals/' not in str(path)
        return original_text(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',protected_text)
    provider_check(SourceMethod.NATIVE);provider_check(SourceMethod.OCR);provider_check(SourceMethod.VISION)
    from app import document_intelligence,document_structure_orchestrator,scope_detail_adapters
    for module in (document_intelligence,document_structure_orchestrator,scope_detail_adapters):
        content=Path(module.__file__).read_text()
        assert 'document_intelligence_b4_structure_golden' not in content
