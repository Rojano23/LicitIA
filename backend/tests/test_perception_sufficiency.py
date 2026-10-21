"""SI21–SI23 / PS01–PS16: generic synthetic planner boundary contracts.

Doubles exercise eligibility/guards only; no real OCR, Vision or blind corpus.
"""
from dataclasses import replace
import pytest
from sqlalchemy import select
from app.models import TenderScopeDetail,NormalizedContent
from app.document_perception_planner import (PerceptionTask as T,TaskRequest,VisionTaskRequest,
    plan_ocr,plan_document_ocr_tasks,plan_document_vision_tasks,perception_metrics)
from app.selective_ocr_executor import execute_planned_ocr
from app.selective_vision_executor import execute_planned_vision,VisionBudget,vision_metrics
from test_selective_ocr_recovery import scene,execute,plans,TEXT
from test_selective_vision_recovery import setup,plan as vision_plan,execute as vision_execute
from test_document_intelligence_integration import corpus,norm
from test_blind_selective_harness import harness,profile,run,spatial

PROSE = 'Se documentarán las verificaciones realizadas durante la puesta en marcha.'
TABLE = 'Partida | Descripción | Cantidad | Unidad\n91 | Componentes de prueba | 7 | PZA'


def native(scene,text=PROSE):
    return norm(scene[0][0],scene[0][3],text=text)


def textual_vision(scene,request=None):
    db,tender,doc,page = scene[0]
    return plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,
        requests={page.id:(VisionTaskRequest(request or TaskRequest(T.SCOPE),'DETAIL_TRANSCRIPTION'),)},
        execution_policy='AUTO')[0]


def test_SI21_PS02_interpretation_not_perception(scene):
    native(scene)
    p=plans(scene)[0]
    assert p.assessment.state=='SUFFICIENT' and p.interpretation.state=='UNRESOLVED'
    assert p.native_sufficient and not p.ocr_eligible and p.status=='REVIEW_REQUIRED'
    assert execute(scene,p).status=='SKIPPED' and not scene[3]


def test_SI22_native_no_candidate_no_acquisition(harness,profile):
    from app.scope_detail_materializer import materialize_document_scope_details
    scene=harness[0];db,tender,doc,page=scene[0]
    native(scene)
    result=materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    assert result.candidate_count==0
    assert not db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==doc.id)).all()
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert not scene[3] and not harness[1]
    assert result.perception_metrics['ocr']['ocr_avoided']>0
    assert result.perception_metrics['ocr']['interpretation_states']['UNRESOLVED']>0
    decisions=[p for p in result.providers if p.configuration.get('decision_only')]
    assert any(e.configuration['perception_assessment']['state']=='SUFFICIENT' and
               e.configuration['interpretation_assessment']['state']=='UNRESOLVED' for e in decisions)


def test_SI23_PS04_ocr_text_sufficient_no_vision(setup):
    scene=setup[0];db,_,_,page=scene[0]
    norm(db,page,'OCR',text=PROSE)
    p=textual_vision(scene)
    assert p.assessment.state=='SUFFICIENT' and p.assessment.source_method=='OCR'
    assert p.interpretation.state=='UNRESOLVED' and not p.eligible
    assert vision_execute(setup,p).status=='SKIPPED' and not setup[1]
    # A separate explicit spatial question remains a legitimate visual deficit.
    assert vision_plan(setup).eligible


def test_PS01_native_interpreted_no_ocr_or_vision(setup):
    native(setup[0],TEXT)
    p=plans(setup[0])[0];v=textual_vision(setup[0])
    assert p.interpretation.state=='SUCCESS' and p.native_sufficient
    assert execute(setup[0],p).status=='SKIPPED'
    assert vision_execute(setup,v).status=='SKIPPED'
    assert not setup[0][3] and not setup[1]


def test_PS03_real_missing_text_eligible(scene):
    p=plans(scene)[0]
    assert p.assessment.state=='INSUFFICIENT' and p.assessment.reason=='TEXT_NOT_AVAILABLE'
    assert p.ocr_eligible


def test_PS05_bad_ocr_not_implicit_visual_need(setup):
    db,_,_,page=setup[0][0]
    n=norm(db,page,'OCR',text='unreadable')
    p=textual_vision(setup[0])
    assert not p.eligible and p.assessment.state=='INSUFFICIENT'
    assert vision_execute(setup,p).status=='SKIPPED' and not setup[1]


def test_PS06_explicit_spatial_need(setup):
    native(setup[0],PROSE)
    p=vision_plan(setup)
    assert p.eligible and p.assessment.state=='VISUAL_REQUIRED'
    assert p.reason=='PROVEN_TASK_VISUAL_DEFICIT'


def test_PS07_no_spatial_contract_no_vision(setup):
    p=textual_vision(setup[0])
    assert not p.eligible and p.reason=='NO_PROVEN_VISUAL_SEMANTIC_DEFICIT'
    assert vision_execute(setup,p).status=='SKIPPED'


def test_PS08_tasks_keep_independent_coverage(scene):
    native(scene)
    db,tender,doc,page=scene[0]
    requests=(TaskRequest(T.SCOPE),TaskRequest(T.QUANTITIES,region_id=scene[1].id))
    a,b=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,requests={page.id:requests},execution_policy='AUTO')
    assert a.native_sufficient and not a.ocr_eligible
    assert b.ocr_eligible and not b.native_sufficient
    assert b.assessment.reason=='REQUESTED_REGION_TEXT_NOT_COVERED'


def test_PS09_ambiguous_IR_review_not_perception_gap(scene):
    native(scene,'ITEM 91\nSuministro de componentes\n  con soporte\nCantidad: 7\nCantidad: 9\nUnidad: PZA')
    p=plans(scene)[0]
    assert p.assessment.reason=='GROUNDED_STRUCTURED_FRAGMENTS_AVAILABLE'
    assert p.assessment.state=='SUFFICIENT' and p.interpretation.state=='AMBIGUOUS'
    assert p.status=='REVIEW_REQUIRED' and not p.ocr_eligible
    assert execute(scene,p).status=='SKIPPED' and not scene[3]


def test_PS10_observability_independent_states(scene):
    missing=plans(scene)[0];native(scene)
    present=plans(scene)[0]
    m=perception_metrics((missing,present))
    assert m['perception_states']=={'INSUFFICIENT':1,'SUFFICIENT':1}
    assert m['interpretation_states']=={'NOT_ATTEMPTED':1,'UNRESOLVED':1}
    assert m['ocr_eligible']==1 and m['ocr_avoided']==1


def test_PS11_available_only_no_calls(scene):
    p=plans(scene,policy='AVAILABLE_ONLY')[0]
    assert p.ocr_eligible and execute(scene,p).status=='DEFERRED'
    assert not scene[3]


def test_PS12_historical_profile_zero_acquisitions(harness,profile):
    safe=profile.model_copy(update={'profile':'HISTORICAL_SAFE','execution_policy':'AVAILABLE_ONLY'})
    result=run(harness,spatial(safe,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert not harness[0][3] and not harness[1]
    assert all(e.calls==0 for e in result.providers)


def test_PS13_selective_legitimate_text_gap(harness,profile):
    result=run(harness,profile)
    assert len(harness[0][3])==1
    assert any(e.calls==1 for e in result.providers if e.source_method=='OCR')


def test_PS14_legitimate_vision_execution(setup):
    p=vision_plan(setup)
    result=vision_execute(setup,p)
    assert result.status=='COMPLETED' and setup[1]==['DETAIL_TRANSCRIPTION']
    assert vision_metrics((p,),(result,))['executed']==1


def test_PS15_budget_caps_unchanged(harness,profile):
    limited=profile.model_copy(update={'ocr':profile.ocr.model_copy(update={'max_calls':0}),
                                     'vision':profile.vision.model_copy(update={'max_calls':0})})
    result=run(harness,spatial(limited,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert not harness[0][3] and not harness[1]
    assert result.perception_metrics['ocr_budget_exhausted']>0
    assert result.perception_metrics['vision']['budget_exhausted']>0


def test_PS16_deterministic_planning(scene):
    native(scene,PROSE)
    assert plans(scene)==plans(scene)
    assert textual_vision(scene)==textual_vision(scene)


def test_PS17_not_character_length(scene):
    native(scene,'Administrative content. '*200)
    p=plans(scene)[0]
    assert p.ocr_eligible and not p.native_sufficient


def test_PS18_explicit_missing_anchor_is_text_gap(scene):
    native(scene)
    p=plans(scene,request=TaskRequest(T.SCOPE,('Synthetic required source anchor',)))[0]
    assert p.ocr_eligible and p.assessment.reason=='REQUIRED_TEXT_NOT_AVAILABLE'


def test_PS19_corrupt_generation_fails_closed(scene):
    n=native(scene);n.content_sha256='0'*64;scene[0][0].flush()
    with pytest.raises(ValueError,match='HASH_MISMATCH'):plans(scene)
    assert not scene[3]


def test_PS20_persisted_failure_not_sufficient(setup):
    from app.models import PageOcrResult
    db,_,_,page=setup[0][0]
    n=norm(db,page,'OCR',text=PROSE)
    row=db.get(PageOcrResult,n.page_ocr_result_id);row.status='OCR_FAILED';db.flush()
    assert not textual_vision(setup[0]).eligible
    assert textual_vision(setup[0]).assessment.state!='SUFFICIENT'


def test_PS21_region_mismatch_cannot_borrow_ocr(setup):
    db,_,_,page=setup[0][0];norm(db,page,'OCR',text=PROSE)
    p=textual_vision(setup[0],TaskRequest(T.SCOPE,region_id=setup[0][1].id))
    assert p.assessment.state=='INSUFFICIENT' and not p.eligible


def test_PS22_IR_table_support_is_perception_not_authority(scene):
    native(scene,TABLE)
    p=plans(scene)[0]
    assert p.native_sufficient and p.assessment.reason=='GROUNDED_STRUCTURED_FRAGMENTS_AVAILABLE'
    assert not p.ocr_eligible


def test_PS23_policy_version_in_freeze():
    from app.blind_selective_freeze import implementation_versions
    from app.perception_sufficiency import POLICY_VERSION
    assert implementation_versions()['perception_sufficiency']==POLICY_VERSION


def test_PS24_readable_ocr_not_arbitrary_spatial_proof(harness,profile):
    from app.selective_ocr_executor import OcrInvocation
    def prose(*args):
        return OcrInvocation('COMPLETED',True,dict(text=PROSE,status='OCR_TEXT_EXTRACTED',
            engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE'),ocr=prose)
    assert any(p.eligible for p in result.vision_plans)
    assert harness[1]==['STRUCTURE_SCOPE']


def test_PS25_grounded_ocr_region_relationship_avoids_vision(harness,profile):
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE'),ocr=harness[0][2])
    assert not harness[1]
    assert any(p.assessment.reason=='GROUNDED_REGION_RELATIONSHIPS_AVAILABLE' for p in result.vision_plans)


def test_PS26_region_binding_mismatch_rejected(setup):
    from app.models import DocumentPageRegion
    scene=setup[0];db,tender,doc,page=scene[0]
    region=DocumentPageRegion(document_page_id=page.id,region_index=2,region_type='IMAGE',
        x0=10,y0=10,x1=30,y1=30,width=20,height=20,area_ratio=.1)
    db.add(region);db.flush();db.expire(page,['regions'])
    request=replace(vision_plan(setup).task,request=TaskRequest(T.SCOPE,region_id=region.id,visual_relationships_required=True))
    with pytest.raises(ValueError,match='REGION_BINDING_MISMATCH'):
        plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,requests={page.id:(request,)})


def test_PS27_unavailable_not_interpreted():
    p=plan_ocr(page_id='synthetic',page_number=1,native_text=TEXT,image_region_ids=(),request=TaskRequest(T.SCOPE),supported=False)
    assert p.assessment.state=='UNAVAILABLE' and p.interpretation.state=='NOT_ATTEMPTED'
    assert not p.ocr_eligible


def test_PS28_interpreter_limit_not_perception_gap(scene,monkeypatch):
    native(scene,TABLE)
    monkeypatch.setattr('app.structured_evidence.MAX_BLOCKS',0)
    p=plans(scene)[0]
    assert p.assessment.state=='SUFFICIENT' and p.interpretation.state=='REJECTED'
    assert not p.ocr_eligible and execute(scene,p).status=='SKIPPED'
    assert not scene[3]



@pytest.mark.parametrize('defect',['page','region','engine'])
def test_PS29_invalid_ocr_binding_not_coverage(setup,defect):
    from app.models import PageOcrResult
    from test_document_intelligence_integration import add_page
    scene=setup[0];db,_,doc,page=scene[0]
    n=norm(db,page,'OCR',text=PROSE)
    row=db.get(PageOcrResult,n.page_ocr_result_id)
    if defect=='page':
        row.document_page_id=add_page(db,doc,2).id
    elif defect=='region':
        n.region_id=scene[1].id
    else:
        n.engine='another-engine'
    db.flush()
    with pytest.raises(ValueError,match='OCR_SOURCE_(SCOPE|ENGINE)_MISMATCH'):
        textual_vision(scene)
    assert not setup[1] and not scene[3]



@pytest.mark.parametrize('fields,state',[
    ('Cantidad: 7\nUnidad: PZA','SUCCESS'),
    ('Cantidad: 7','UNRESOLVED'),
    ('Unidad: PZA','UNRESOLVED'),
    ('Cantidad: aproximadamente siete\nUnidad: PZA','UNRESOLVED'),
])
def test_PS30_partial_quantity_interpretation_not_perception_gap(scene,fields,state):
    native(scene,'ITEM 91\nSuministro de componentes\n'+fields)
    p=plans(scene,T.QUANTITIES)[0]
    assert p.assessment.state=='SUFFICIENT' and p.interpretation.state==state
    assert not p.ocr_eligible and execute(scene,p).status=='SKIPPED'
    assert not scene[3]
