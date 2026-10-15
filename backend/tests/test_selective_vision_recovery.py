"""V.4c2 synthetic contracts. No provider or blind corpus access."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from app.models import DocumentVisionPageResult, DocumentPageRegion
from app.document_perception_planner import (TaskRequest,PerceptionTask as T,VisionTaskRequest,plan_document_vision_tasks)
from app.selective_vision_executor import (VisionConfiguration,VisionBudget,execute_planned_vision,vision_metrics)
from test_selective_ocr_recovery import scene
from test_document_intelligence_integration import corpus,norm,add_page,requirements,requested

CONFIG=VisionConfiguration('synthetic-model','sha256:synthetic-local-model')
TEXT='ITEM 73: Suministro de instrumentos | Marca: Delta | Modelo: Z-8 | Cantidad: 4 | Unidad: PZA'

@pytest.fixture
def setup(scene,monkeypatch):
    import app.selective_vision_executor as executor
    monkeypatch.setattr(executor,'receipt_root',lambda:scene[4]/'vision-receipts')
    calls=[]
    def invoke(config,task,number,image):
        calls.append(task)
        payload=({'page_number':number,'item_segments':[{'item_number':'73','starts_on_this_page':True,
            'anchor_raw_text':'ITEM 73','has_supply':True,'review_required':True}]}
            if task=='STRUCTURE_SCOPE' else {'source_page':number,'raw_lines':[{'raw_visible_text':TEXT}]})
        return 'COMPLETED',payload,1,200,[],None,None,None
    return scene,calls,invoke


def plan(setup,*,task='DETAIL_TRANSCRIPTION',policy='AUTO',visual=True):
    scene=setup[0];db,tender,doc,page=scene[0]
    request=TaskRequest(T.STRUCTURE if task=='STRUCTURE_SCOPE' else T.SCOPE,
        visual_relationships_required=visual)
    item=VisionTaskRequest(request,task,scene[1].id,'TABLE_RELATIONSHIP' if visual else None)
    return plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,
        requests={page.id:(item,)},execution_policy=policy)[0]


def execute(setup,p=None,**kwargs):
    return execute_planned_vision(setup[0][0][0],p or plan(setup),config=kwargs.pop('config',CONFIG),
        budget=kwargs.pop('budget',VisionBudget()),invoke=kwargs.pop('invoke',setup[2]),**kwargs)


@pytest.mark.parametrize('method',['NATIVE','OCR'])
def test_VI01_VI02_sufficient_avoids_vision(setup,method):
    db,_,_,page=setup[0][0]
    norm(db,page,method,text=TEXT)
    p=plan(setup,visual=False)
    assert p.status=='SUFFICIENT_FOR_TASK'
    assert not p.eligible and execute(setup,p).status=='SKIPPED' and setup[1]==[]


def test_VI03_ocr_failure_is_not_visual_need(setup):
    p=plan(setup,visual=False)
    assert not p.eligible and p.reason=='NO_PROVEN_VISUAL_SEMANTIC_DEFICIT'
    assert execute(setup,p).status=='SKIPPED'


@pytest.mark.parametrize('policy',['AVAILABLE_ONLY','ALLOW_OCR'])
def test_VI05_VI06_eligible_not_executed(setup,policy):
    p=plan(setup,policy=policy)
    assert p.eligible and execute(setup,p).status=='DEFERRED' and not setup[1]
    assert not (setup[0][4]/'vision-receipts').exists()


def test_VP16_region_proves_eligibility(setup):
    assert plan(setup).eligible
    p=replace(plan(setup).task,visual_region_id='missing')
    db,tender,doc,page=setup[0][0]
    result=plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,requests={page.id:(p,)})[0]
    assert not result.eligible


@pytest.mark.parametrize('task',['STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'])
def test_VT_tasks_independent_reused_without_render(setup,task):
    p=plan(setup,task=task)
    first=execute(setup,p)
    assert first.status=='COMPLETED'
    second=execute(setup,p,render=lambda *args:pytest.fail('cache must not render'))
    assert second.reused and second.page_result_id==first.page_result_id and setup[1]==[task]
    row=setup[0][0][0].get(DocumentVisionPageResult,first.page_result_id)
    assert ('detail_transcription' in row.structured_json)==(task=='DETAIL_TRANSCRIPTION')
    assert row.structured_json['_selective_vision']['task_fingerprint']==first.fingerprint


def test_VT05_structure_then_detail_independent(setup):
    a=execute(setup,plan(setup,task='STRUCTURE_SCOPE'))
    b=execute(setup)
    assert a.fingerprint!=b.fingerprint and setup[1]==['STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION']


@pytest.mark.parametrize('change',[{'model':'another'},{'model_revision':'sha256:other'},
    {'detail_tokens':1500},{'timeout_seconds':30}])
def test_VP22_config_change_new_generation(setup,change):
    first=execute(setup)
    second=execute(setup,config=replace(CONFIG,**change))
    assert first.fingerprint!=second.fingerprint and len(setup[1])==2
    assert setup[0][0][0].get(DocumentVisionPageResult,first.page_result_id).status=='COMPLETED'


def test_detail_config_does_not_invalidate_structure(setup):
    p=plan(setup,task='STRUCTURE_SCOPE')
    a=execute(setup,p)
    b=execute(setup,p,config=replace(CONFIG,detail_tokens=1500))
    assert b.reused and a.fingerprint==b.fingerprint


@pytest.mark.parametrize('kind',['timeout','malformed','schema','empty','partial','unavailable'])
def test_VR_finite_persistent_failure(setup,kind):
    def fail(*args):
        if kind=='timeout':raise TimeoutError('synthetic timeout')
        if kind=='schema':return 'COMPLETED',{'source_page':1,'raw_lines':[{'raw_visible_text':123}]},1,200,[],None,None,None
        if kind=='empty':return 'COMPLETED',{'source_page':1,'raw_lines':[]},1,200,[],None,None,None
        return kind.upper(),None,1,None,[],None,None,None
    first=execute(setup,invoke=fail)
    second=execute(setup,invoke=fail)
    third=execute(setup,invoke=lambda *args:pytest.fail('exhausted'))
    assert first.status==second.status==('UNAVAILABLE' if kind=='unavailable' else 'FAILED')
    assert third.status=='RETRY_EXHAUSTED'
    assert third.attempts==2
    assert setup[0][0][0].scalars(select(DocumentVisionPageResult).where(DocumentVisionPageResult.document_page_id==setup[0][0][3].id)).all()==[]


@pytest.mark.parametrize('kwargs',[{'max_calls':0},{'max_tasks':0},{'max_pages':0}])
def test_VB_budgets_no_calls(setup,kwargs):
    assert execute(setup,budget=VisionBudget(**kwargs)).status=='BUDGET_EXHAUSTED'
    assert setup[1]==[]


def test_VB_shared_run_cap(setup):
    budget=VisionBudget(max_calls=1)
    assert execute(setup,budget=budget).status=='COMPLETED'
    assert execute(setup,plan(setup,task='STRUCTURE_SCOPE'),budget=budget).status=='BUDGET_EXHAUSTED'
    assert len(setup[1])==1


def test_render_failure_no_call(setup):
    def fail(*args):raise ValueError('synthetic render')
    assert execute(setup,render=fail).status=='RENDER_FAILED' and not setup[1]


def test_VP30_unsupported_no_vision(setup):
    setup[0][0][2].mime_type='application/octet-stream'
    setup[0][0][2].original_filename='metadata.bin'
    assert execute(setup).status=='SKIPPED' and not setup[1]


def test_native_and_ocr_survive_failure(setup):
    db,_,_,page=setup[0][0]
    n=norm(db,page,text='Native heading')
    o=norm(db,page,'OCR',text='OCR heading')
    before=(n.id,n.content_sha256,o.id,o.content_sha256,page.text)
    execute(setup,invoke=lambda *args:('FAILED',None,1,None,[],None,None,None))
    assert before==(n.id,n.content_sha256,o.id,o.content_sha256,page.text)


def test_VP25_detail_reaches_requirements(setup):
    text='El licitante debera presentar certificado de calidad para el suministro de equipos.'
    result=execute(setup,invoke=lambda *args:('COMPLETED',{'source_page':1,'raw_lines':[{'raw_visible_text':text}]},1,200,[],None,None,None))
    candidates=requirements(setup[0][0])
    assert candidates and any(result.page_result_id in json.dumps(e.perception_provenance) for c in candidates for e in c.evidence)
    assert requested(setup[0][0])['requirements']


def test_metrics(setup):
    p=plan(setup);r=execute(setup,p)
    m=vision_metrics((p,),(r,))
    assert m['executed']==1 and m['tasks']=={'DETAIL_TRANSCRIPTION':1}


@pytest.mark.parametrize('url',['https://remote.example','http://remote.example','http://localhost@remote.example'])
def test_VP38_no_remote_provider(url):
    with pytest.raises(ValueError,match='LOCAL_VISION'):
        replace(CONFIG,base_url=url)


@pytest.mark.parametrize('method',['NATIVE','OCR'])
def test_VC_comparable_scope_dedup(setup,method):
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.models import TenderScopeDetail
    execute(setup)
    db,tender,doc,page=setup[0][0]
    normalized=norm(db,page,method,text=TEXT)
    if method=='OCR':
        normalized.engine='synthetic';db.flush()
    report=materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==doc.id)).all()
    assert len(rows)==1
    assert any(len(e.source_artifact_keys)==2 for e in report.logical_evidence)


def test_VP24_conflict_not_vision_authority(setup):
    from app.document_intelligence_sources import load_document_transcriptions
    execute(setup)
    db,_,doc,page=setup[0][0]
    norm(db,page,text=TEXT.replace('Cantidad: 4','Cantidad: 9'))
    route=load_document_transcriptions(db,doc)[page.id]
    assert route.status=='REVIEW_REQUIRED' and route.conflicts


def test_VP36_structure_cannot_fill_detail(setup):
    from app.document_intelligence_sources import load_document_transcriptions
    execute(setup,plan(setup,task='STRUCTURE_SCOPE'))
    db,_,doc,page=setup[0][0]
    assert not load_document_transcriptions(db,doc)[page.id].selected
    assert plan(setup).eligible


def test_VP35_completed_page_independent_of_failed_page(setup):
    scene=setup[0];db,tender,doc,page=scene[0]
    first=execute(setup)
    second_page=add_page(db,doc,2)
    region=DocumentPageRegion(document_page_id=second_page.id,region_index=1,region_type='IMAGE',
        x0=0,y0=0,x1=200,y1=200,width=200,height=200,area_ratio=.4)
    db.add(region);db.flush();db.expire(second_page,['regions'])
    req=VisionTaskRequest(TaskRequest(T.SCOPE,visual_relationships_required=True),'DETAIL_TRANSCRIPTION',region.id,'TABLE_RELATIONSHIP')
    p=plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,requests={second_page.id:(req,)},execution_policy='AUTO')[0]
    failed=execute(setup,p,invoke=lambda *args:('FAILED',None,1,None,[],None,None,None),render=lambda *args:b'synthetic')
    assert failed.status=='FAILED'
    assert execute(setup).reused and len(setup[1])==1


def test_interrupted_attempt_is_not_reissued(setup):
    execute(setup,invoke=lambda *args:('FAILED',None,1,None,[],None,None,None))
    path=next((setup[0][4]/'vision-receipts').glob('*.json'))
    data=json.loads(path.read_text());data['state']='RUNNING';path.write_text(json.dumps(data))
    assert execute(setup,invoke=lambda *args:pytest.fail('uncertain execution')).status=='RETRY_EXHAUSTED'


def test_changed_fingerprint_can_run_after_exhaustion(setup):
    budget=VisionBudget(max_attempts_per_task=1)
    execute(setup,budget=budget,invoke=lambda *args:('FAILED',None,1,None,[],None,None,None))
    assert execute(setup).status=='RETRY_EXHAUSTED'
    assert execute(setup,config=replace(CONFIG,model_revision='sha256:new')).status=='COMPLETED'


def test_canonical_client_single_task_no_probe_no_internal_retry(monkeypatch):
    from app.selective_vision_executor import invoke_canonical_task
    from app.ollama_vision import OllamaVisionAssistClient
    calls=[]
    monkeypatch.setattr(OllamaVisionAssistClient,'probe',lambda *args:pytest.fail('no probes'))
    def detail(self,**kwargs):
        assert self.settings.licitia_vision_retry_malformed_json==0
        assert self.settings.licitia_ollama_timeout_seconds==CONFIG.timeout_seconds
        calls.append(kwargs)
        return 'FAILED',None,1,None,[],None,None,None
    monkeypatch.setattr(OllamaVisionAssistClient,'analyze_detail_transcription_page',detail)
    invoke_canonical_task(CONFIG,'DETAIL_TRANSCRIPTION',1,b'synthetic')
    assert len(calls)==1


def test_existing_metrics_contract(setup):
    from app.selective_vision_executor import vision_provider_metrics
    r=execute(setup)
    metric=vision_provider_metrics((r,),CONFIG)[0]
    assert metric.execution_event and metric.calls==1 and metric.source_method=='VISION'


def test_VI04_independent_satisfied_and_visual_tasks(setup):
    db,tender,doc,page=setup[0][0]
    norm(db,page,text=TEXT)
    satisfied=VisionTaskRequest(TaskRequest(T.TEXT,(TEXT,)),'DETAIL_TRANSCRIPTION')
    visual=plan(setup,task='STRUCTURE_SCOPE').task
    plans=plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,
        requests={page.id:(satisfied,visual)},execution_policy='AUTO')
    assert not plans[0].eligible and plans[1].eligible


def test_VP23_three_capabilities_one_logical_scope(setup):
    from app.scope_detail_materializer import materialize_document_scope_details
    execute(setup)
    db,tender,doc,page=setup[0][0]
    norm(db,page,text=TEXT)
    n=norm(db,page,'OCR',text=TEXT);n.engine='synthetic';db.flush()
    report=materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    assert any(len(e.source_artifact_keys)==3 for e in report.logical_evidence)


def test_VP25_vision_children_keep_source_ids(setup):
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
    from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
    from app.models import TenderScopeDetail
    text='ITEM 73: Suministro de instrumentos, Marca: Delta, Modelo: Z-8 (4 PZA)'
    r=execute(setup,invoke=lambda *args:('COMPLETED',{'source_page':1,'raw_lines':[{'raw_visible_text':text}]},1,200,[],None,None,None))
    db,tender,doc,page=setup[0][0]
    materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    detail=db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==doc.id))
    assert detail.source_method=='VISION' and detail.source_page_result_id==r.page_result_id
    assert detail.review_required
    a=materialize_scope_attributes_for_scope_detail(db,scope_detail_id=detail.id)
    q=materialize_scope_quantities_for_scope_detail(db,scope_detail_id=detail.id)
    assert a.persisted_count==2 and q.persisted_count==1


def test_VC_distinct_items_and_paraphrase_not_collapsed(setup):
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.models import TenderScopeDetail
    text=TEXT+'\n'+TEXT.replace('ITEM 73:','ITEM 74:')
    execute(setup,invoke=lambda *args:('COMPLETED',{'source_page':1,'raw_lines':[{'raw_visible_text':line} for line in text.splitlines()]},1,200,[],None,None,None))
    db,tender,doc,page=setup[0][0]
    norm(db,page,text=TEXT.replace('Suministro de instrumentos','Suministro de aparatos de medición'))
    materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==doc.id)).all()
    assert len(rows)==3 and all(r.review_required for r in rows)


def test_corrupt_completed_result_not_reused(setup):
    r=execute(setup)
    row=setup[0][0][0].get(DocumentVisionPageResult,r.page_result_id)
    row.structured_json={}
    assert execute(setup,invoke=lambda *args:pytest.fail('corrupt reuse')).status=='DEFERRED'
