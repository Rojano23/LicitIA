"""R.3 synthetic trust/production boundaries; no real model accuracy claim."""
from copy import deepcopy
import pytest
from sqlalchemy import select
from app.critical_identifier_comparison import IdentifierKind as K,compare_identifiers
from app.document_identifier_bindings import page_identifier_comparisons,guard_structure
from app.document_intelligence import Capability as C,Quality as Q,SourceMethod as S,advance_continuity
from app.models import CompanyEvidence,TenderScopeDetail,TenderScopeQuantity,TenderScopeAttribute
from app.requirement_di_adapter import candidate_perception
from app.requirement_perception_provenance import read_provenance,provenance_from_routings,write_provenance
from app.requirement_normalization import normalize_tender_requirements
from app.requirement_semantics import analyze_tender_requirement_semantics
from app.scope_detail_adapters import ScopeDetailEvidenceArtifact,adapt_and_persist_scope_detail_artifact
from app.scope_details import ScopeDetailCandidate
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from test_cross_capability_provenance import source,route,observation,pair
from test_requirement_perception_provenance import logical
from test_document_intelligence_integration import vision,corpus,norm,orchestrated,add_page,structure

STABLE='Servicio independiente Modelo Y200 (5 piezas)'

@pytest.mark.parametrize('left,right,a,b,status',[
    pytest.param(S.NATIVE,S.OCR,'2','2','AGREEMENT',id='CI01'),
    pytest.param(S.OCR,S.VISION,'2','2','AGREEMENT',id='CI02'),
    pytest.param(S.NATIVE,S.OCR,'2','2','AGREEMENT',id='CI03'),
    pytest.param(S.NATIVE,S.OCR,'2','3','CONFLICT',id='CI04'),
    pytest.param(S.OCR,S.VISION,'2','3','CONFLICT',id='CI05'),
    pytest.param(S.VISION,S.VISION,'2','3','CONFLICT',id='CI06'),
    pytest.param(S.NATIVE,S.OCR,'1','01','CONFLICT',id='CI11'),
    pytest.param(S.NATIVE,S.OCR,'TAG-101','TAG-10I','CONFLICT',id='CI12'),
    pytest.param(S.NATIVE,S.OCR,'X100','X100A','CONFLICT',id='CI13')])
def test_identifier_baseline(left,right,a,b,status):
    x=source(a,method=left);y=source(b,method=right).model_copy(update={'generation_id':'other'})
    c=compare_identifiers(kind=K.ITEM_NUMBER,binding_key='row:1:owner',observations=(observation(x),observation(y)))
    assert c.status==status and len(c.observations)==2

def test_CI07_deselected():
    assert pair(lineage='DESELECTED').identifier_comparisons[0].status=='INSUFFICIENT_EVIDENCE'

def test_CI08_unavailable():
    assert not page_identifier_comparisons(route((source(quality=Q.UNAVAILABLE),)))

def test_CI09_order():
    a=source('2').model_copy(update={'provider_metadata':(('uploaded_at','2099-01-01'),)})
    b=source('3',method=S.OCR).model_copy(update={'provider_metadata':(('uploaded_at','2000-01-01'),)})
    assert page_identifier_comparisons(route((a,b)))[0].status==page_identifier_comparisons(route((b,a)))[0].status=='CONFLICT'

def test_CI10_normalization():
    from app.critical_identifier_comparison import normalize_identifier
    for a,b in [('A-1','A1'),('Rev A','Rev B'),('10 piezas','10 SET')]:
        assert normalize_identifier(a)!=normalize_identifier(b)

def test_CI14_metadata():
    s=source().model_copy(update={'text':'ordinary prose','provider_metadata':(('item','3'),)})
    assert not page_identifier_comparisons(route((s,)))

def test_CI15_deterministic():
    a,b=source('2'),source('3',method=S.OCR)
    assert page_identifier_comparisons(route((a,b)))==page_identifier_comparisons(route((b,a)))

def req(logical):
    _,row,identity=logical
    a=source(identity=identity).model_copy(update={'text':row.source_excerpt+' Item 2'})
    b=source('3',C.STRUCTURE,S.VISION,identity=identity)
    c=compare_identifiers(kind=K.ITEM_NUMBER,binding_key='row:1:owner',observations=(observation(a,value='2'),observation(b)))
    write_provenance(row,provenance_from_routings((route((a,)),route((b,))),comparisons=(c,)))
    return row

def test_CR01_requirement(logical):
    assert candidate_perception(req(logical).candidate)==(True,True)

def test_CR02_provenance(logical):
    row=req(logical)
    assert {o.raw_value for o in read_provenance(row.perception_provenance).identifier_comparisons[0].observations}=={'2','3'}

def test_CR03_unrelated(logical):
    _,row,identity=logical
    a=source(identity=identity).model_copy(update={'text':'Item 2\n'+row.source_excerpt})
    b=source('3',method=S.OCR,identity=identity).model_copy(update={'text':'Item 3\n'+row.source_excerpt})
    result=route((a,b))
    write_provenance(row,provenance_from_routings((result,),comparisons=page_identifier_comparisons(result)))
    assert candidate_perception(row.candidate)==(True,False)

def requested(logical):
    db,_,identity=logical;req(logical)
    normalize_tender_requirements(db,identity.tender_id)
    return analyze_tender_requirement_semantics(db,identity.tender_id)

def test_CE01_requested_review(logical):
    result=requested(logical)
    assert any(r['interpretation_status']=='REVIEW_REQUIRED' for r in result['requirements'])

def test_CE02_requested_provenance(logical):
    result=str(requested(logical))
    assert 'identifier_comparisons' in result and 'CONFLICT' in result

def test_CE03_company():
    assert 'perception_provenance' not in CompanyEvidence.__table__.columns

class Adapter:
    adapter_name='synthetic';adapter_version='1'
    def __init__(self,candidates):self.candidates=candidates
    def supports(self,artifact):return True
    def extract_candidates(self,db,artifact):return self.candidates

def scopes(logical,line='Item 2 Modelo X100 equipo (10 piezas)',other='Item 3 Modelo X100 equipo (10 piezas)'):
    db,row,identity=logical
    from app.models import TenderDocument,DocumentPage
    doc=db.get(TenderDocument,identity.document_id);page=db.get(DocumentPage,identity.document_page_id)
    v=vision(db,doc,page,text=line+'\n'+STABLE)
    payload=deepcopy(v.structured_json)
    payload['detail_transcription']['parsed_supply_rows']=[
        {'description':line,'raw_visible_text':line,'model':'X100','quantity':'10','unit':'EA','review_required':False},
        {'description':STABLE,'raw_visible_text':STABLE,'model':'Y200','quantity':'5','unit':'EA','review_required':False}]
    v.structured_json=payload;db.flush()
    # Perception reliability is declared by this synthetic fixture, not certified.
    a=source(identity=identity,method=S.VISION).model_copy(update={'text':line+'\n'+STABLE,'source_artifact_key':f'vision-page-result:{v.id}'})
    b=source(identity=identity,method=S.OCR).model_copy(update={'text':other+'\n'+STABLE})
    def detail(text,index):
        return ScopeDetailCandidate(tender_id=identity.tender_id,source_document_id=identity.document_id,
            document_page_id=identity.document_page_id,domain='SUPPLY',description=text,applicability='TENDER_WIDE' if index==1 else 'ITEM',
            source_method='VISION',source_artifact_key=a.source_artifact_key,source_locator=f'page:1|detail_row:{index}',
            source_excerpt=text,review_required=False,candidate_item_key=None if index==1 else '2')
    artifact=ScopeDetailEvidenceArtifact(tender_id=identity.tender_id,source_document_id=identity.document_id,
        document_page_id=identity.document_page_id,source_method='VISION',source_artifact_key=a.source_artifact_key,
        payload=payload,transcription=route((a,b)))
    adapt_and_persist_scope_detail_artifact(db,artifact,adapters=(Adapter((detail(line,0),detail(STABLE,1))),))
    db.flush()
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key==a.source_artifact_key)).all()
    return rows,artifact

@pytest.mark.parametrize('line,other',[
    pytest.param('Item 2 equipo','Item 3 equipo',id='CS01'),
    pytest.param('Partida 2 equipo','Partida 3 equipo',id='CS02'),
    pytest.param('TAG TAG-101 equipo','TAG TAG-10I equipo',id='CS03'),
    pytest.param('Modelo X100 equipo','Modelo X100A equipo',id='CS04')])
def test_scope_conflicts(logical,line,other):
    rows,_=scopes(logical,line,other);affected=next(r for r in rows if r.source_excerpt==line)
    assert affected.review_required and affected.applicability=='UNRESOLVED'
    assert affected.candidate_item_key is None and affected.tender_item_id is None and affected.scope_segment_id is None

def test_CS05_cross_capability(logical):
    db,row,identity=logical
    a=source(identity=identity);b=source('3',C.STRUCTURE,S.VISION,identity=identity)
    artifact=ScopeDetailEvidenceArtifact(tender_id=identity.tender_id,source_document_id=identity.document_id,
        document_page_id=identity.document_page_id,source_method='NATIVE',source_artifact_key=a.source_artifact_key,
        transcription=route((a,)),structure=route((b,)))
    candidate=ScopeDetailCandidate(tender_id=identity.tender_id,source_document_id=identity.document_id,
        document_page_id=identity.document_page_id,domain='SUPPLY',description='Item 2',applicability='ITEM',
        source_method='NATIVE',source_artifact_key=a.source_artifact_key,source_locator='page:1',source_excerpt='Item 2',
        review_required=False,candidate_item_key='2')
    assert adapt_and_persist_scope_detail_artifact(db,artifact,adapters=(Adapter((candidate,)),)).review_required_count==1

def test_CS06_unrelated(logical):
    rows,_=scopes(logical)
    assert not next(r for r in rows if r.source_excerpt==STABLE).review_required

def boundary():
    a,b=source('2'),source('3',C.STRUCTURE,S.VISION)
    return guard_structure(route((b,)),page_identifier_comparisons(route((a,)),route((b,))))

def test_CC01_stops():
    assert advance_continuity(boundary()).status=='UNKNOWN'

def test_CC02_no_stale():
    previous=advance_continuity(route((source('2',C.STRUCTURE,S.VISION),)))
    current=advance_continuity(boundary(),previous)
    assert current.outgoing_item_key is None and current.structural_state is None and previous.status=='VALID'

def test_CC03_recovers():
    assert advance_continuity(route((source('4',C.STRUCTURE,S.VISION),)),advance_continuity(boundary())).status=='VALID'

def children(logical,line=None,other=None):
    db,_,_=logical
    rows,_=scopes(logical,*((line,other) if line else ()))
    for row in rows:
        materialize_scope_quantities_for_scope_detail(db,scope_detail_id=row.id)
        materialize_scope_attributes_for_scope_detail(db,scope_detail_id=row.id)
    db.flush()
    return rows,db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==rows[0].tender_id)).all(),db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.tender_id==rows[0].tender_id)).all()

def test_CQ01_owner(logical):
    rows,quantities,_=children(logical)
    bad=next(r for r in rows if r.source_excerpt!=STABLE)
    assert bad.candidate_item_key is None
    assert next(q for q in quantities if q.scope_detail_id==bad.id).review_required

def test_CQ02_value(logical):
    rows,quantities,_=children(logical,'Item 2 Modelo X100 equipo (10 piezas)','Item 2 Modelo X100 equipo (100 piezas)')
    bad=next(r for r in rows if r.source_excerpt!=STABLE)
    assert next(q for q in quantities if q.scope_detail_id==bad.id).review_required

def test_CQ03_unrelated(logical):
    rows,quantities,_=children(logical);good=next(r for r in rows if r.source_excerpt==STABLE)
    assert not next(q for q in quantities if q.scope_detail_id==good.id).review_required

def test_CA01_owner(logical):
    rows,_,attributes=children(logical);bad=next(r for r in rows if r.source_excerpt!=STABLE)
    assert bad.candidate_item_key is None and next(a for a in attributes if a.scope_detail_id==bad.id).review_required

def test_CA02_unrelated(logical):
    rows,_,attributes=children(logical);good=next(r for r in rows if r.source_excerpt==STABLE)
    assert not next(a for a in attributes if a.scope_detail_id==good.id).review_required

def test_XCI01_independent(logical):
    row=req(logical);rows,_=scopes(logical)
    assert candidate_perception(row.candidate)[1] and any(r.review_required for r in rows)

def test_XCI02_requirement_does_not_mutate_scope(logical):
    rows,_=scopes(logical);before=[(r.source_excerpt,r.review_required) for r in rows];req(logical)
    assert before==[(r.source_excerpt,r.review_required) for r in rows]

def test_XCI03_scope_does_not_mutate_requirement(logical):
    row=req(logical);before=deepcopy(row.perception_provenance);scopes(logical)
    assert before==row.perception_provenance

def test_XCI04_locality(logical):
    rows,_=scopes(logical)
    assert sum(r.review_required for r in rows)==1

def test_XCI05_idempotence(logical):
    db,row,_=logical
    rows,artifact=scopes(logical)
    candidates=tuple(ScopeDetailCandidate(tender_id=r.tender_id,source_document_id=r.source_document_id,
        document_page_id=r.document_page_id,domain=r.domain,description=r.description,applicability='TENDER_WIDE' if r.source_excerpt==STABLE else 'ITEM',
        source_method=r.source_method,source_artifact_key=r.source_artifact_key,source_locator=r.source_locator,
        source_excerpt=r.source_excerpt,review_required=False,candidate_item_key=None if r.source_excerpt==STABLE else '2') for r in rows)
    for _ in range(2):
        adapt_and_persist_scope_detail_artifact(db,artifact,adapters=(Adapter(candidates),))
    assert len(db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_artifact_key==artifact.source_artifact_key)).all())==2
    assert len(row.candidate.evidence)==1

def test_XCI06_no_fallback():
    assert boundary().selected is None and boundary().status=='REVIEW_REQUIRED'

def test_production_raw_01_reaches_comparison_and_persistence(corpus):
    from app.requirement_extraction import analyze_tender_requirements
    from app.models import RequirementCandidate
    db,tender,doc,page=corpus
    text='PARTIDA 1\nEl licitante debera presentar identificacion oficial vigente.'
    norm(db,page,text=text);norm(db,page,'OCR',text.replace('PARTIDA 1','PARTIDA 01'))
    analyze_tender_requirements(db,tender.id)
    rows=db.scalars(select(RequirementCandidate).where(RequirementCandidate.tender_id==tender.id)).all()
    assert len(rows)==2
    for row in rows:
        v=read_provenance(row.evidence[0].perception_provenance)
        assert v.schema_version=='2'
        conflict=next(c for c in v.identifier_comparisons if c.kind==K.ITEM_NUMBER)
        assert conflict.status=='CONFLICT' and {o.raw_value for o in conflict.observations}=={'1','01'}
        assert candidate_perception(row)[1]
    snapshots=[deepcopy(row.evidence[0].perception_provenance) for row in rows]
    analyze_tender_requirements(db,tender.id)
    assert snapshots==[row.evidence[0].perception_provenance for row in rows]


def test_production_continuity_blocks_01_and_recovers(corpus):
    db,tender,doc,page=corpus
    norm(db,page,text='PARTIDA 1\nServicio base')
    norm(db,page,'OCR','PARTIDA 01\nServicio base')
    following=add_page(db,doc,2)
    vision(db,doc,following,text=None,structure=structure(2,key='4'))
    result=orchestrated(corpus)
    assert result.page_results[0].status=='REVIEW_REQUIRED'
    assert result.page_results[0].reason=='CRITICAL_IDENTIFIER_CONFLICT'
    assert result.page_results[0].selected_source_method is None
    assert result.page_results[1].status=='RESOLVED'


def test_children_repeated_materialization_preserves_local_review(logical):
    db,_,_=logical
    rows,quantities,attributes=children(logical)
    for row in rows:
        materialize_scope_quantities_for_scope_detail(db,scope_detail_id=row.id)
        materialize_scope_attributes_for_scope_detail(db,scope_detail_id=row.id)
    db.flush()
    q=db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==rows[0].tender_id)).all()
    a=db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.tender_id==rows[0].tender_id)).all()
    assert len(q)==len(quantities)==2 and len(a)==len(attributes)==2
    assert sum(x.review_required for x in q)==sum(x.review_required for x in a)==1

def test_multi_owner_01_cannot_escape_through_unproven_row_alignment():
    from app.page_structure import build_page_structural_state,PageStructuralSegment
    from app.item_identity import normalize_item_identity
    def perception(method,labels):
        base=source('1',C.STRUCTURE,method)
        state=build_page_structural_state(page_number=1,state_quality='VALID',review_required=False,
            provenance=base.structural_state.provenance,incoming_item_key=None,outgoing_item_key='2',
            segments=tuple(PageStructuralSegment(item_identity=normalize_item_identity(label),sequence=index,
                starts_on_this_page=True,anchor_raw_text='PARTIDA '+label,review_required=False)
                for index,label in enumerate(labels)))
        return base.model_copy(update={'text':'\n'.join('PARTIDA '+label for label in labels),'structural_state':state})
    a=perception(S.NATIVE,('1','2'));b=perception(S.OCR,('01','2'))
    initial=route((a,b))
    assert initial.status=='RESOLVED'  # identical legacy-normalized signatures
    comparisons=page_identifier_comparisons(initial)
    guarded=guard_structure(initial,comparisons)
    assert guarded.status=='REVIEW_REQUIRED' and guarded.selected is None
    assert {o.raw_value for c in comparisons for o in c.observations}=={'1','01','2'}

def test_production_scope_retains_both_durable_vision_alternatives(corpus):
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.document_intelligence_sources import load_document_transcriptions,load_page_structure
    from app.models import DocumentVisionPageResult
    db,tender,doc,page=corpus
    first=vision(db,doc,page,text='PARTIDA 1\nModelo X100 equipo (10 piezas)',structure=structure(key='1'))
    second=vision(db,doc,page,text='PARTIDA 01\nModelo X100 equipo (100 piezas)',structure=structure(key='01'))
    for _ in range(2):
        result=materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
        assert result.review_required_count==2
        details=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==tender.id)).all()
        assert len(details)==2 and all(row.review_required for row in details)
        assert {row.source_page_result_id for row in details}=={first.id,second.id}
        for row in details:
            materialize_scope_quantities_for_scope_detail(db,scope_detail_id=row.id)
    db.flush();db.expire_all()
    assert db.get(DocumentVisionPageResult,first.id).structured_json['detail_transcription']['raw_text'].startswith('PARTIDA 1\n')
    assert db.get(DocumentVisionPageResult,second.id).structured_json['detail_transcription']['raw_text'].startswith('PARTIDA 01\n')
    quantities=db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==tender.id)).all()
    assert len(quantities)==2 and {str(q.quantity_value.normalize()) for q in quantities}=={'1E+1','1E+2'}
    assert all(q.review_required for q in quantities)
    comparisons=page_identifier_comparisons(load_document_transcriptions(db,doc)[page.id],load_page_structure(db,doc,page))
    conflict=next(c for c in comparisons if c.kind==K.ITEM_NUMBER)
    assert conflict.status=='CONFLICT'
    assert {o.source.source_page_result_id for o in conflict.observations}=={first.id,second.id}

def test_declared_identifier_conflict_does_not_blanket_review_agreed_fragment(logical):
    from app.document_intelligence import CriticalIdentifier
    db,row,identity=logical
    a=source(identity=identity).model_copy(update={'text':'Item 2\n'+row.source_excerpt,
        'critical_identifiers':(CriticalIdentifier(binding_key='ITEM_NUMBER:owner',value='2',excerpt='Item 2'),)})
    b=source('3',method=S.OCR,identity=identity).model_copy(update={'text':'Item 3\n'+row.source_excerpt,
        'critical_identifiers':(CriticalIdentifier(binding_key='ITEM_NUMBER:owner',value='3',excerpt='Item 3'),)})
    result=route((a,b))
    assert any(c.kind=='IDENTIFIER' for c in result.conflicts)
    write_provenance(row,provenance_from_routings((result,),comparisons=page_identifier_comparisons(result)))
    assert candidate_perception(row.candidate)==(True,False)
