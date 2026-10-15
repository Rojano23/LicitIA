"""BH synthetic contracts. No real blind identity, freeze, or provider services."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from app.blind_selective_profile import SelectiveProfile
from app.blind_selective_harness import (ProviderCallGuard,ProtocolViolation,construct_tasks,
    execute_selective_pipeline)
from app.document_perception_planner import plan_document_ocr_tasks,TaskRequest,PerceptionTask as T,plan_document_vision_tasks
from app.selective_ocr_executor import OcrInvocation
from test_selective_ocr_recovery import scene
from test_document_intelligence_integration import corpus,norm

@pytest.fixture
def profile():
    return SelectiveProfile.model_validate(dict(profile='SELECTIVE_PERCEPTION',execution_policy='AUTO',
        ocr=dict(engine='TESSERACT',engine_version='fixture-1',max_calls=1),
        vision=dict(model='synthetic',model_revision='a'*64,model_manifest='/synthetic/not-present'),
        spatial_contracts=[]))


@pytest.fixture
def harness(scene,monkeypatch):
    import app.selective_vision_executor as v
    monkeypatch.setattr(v,'receipt_root',lambda:scene[4]/'vision')
    calls=[]
    def vision(config,task,number,image):
        calls.append(task)
        return 'COMPLETED',({'page_number':number,'item_segments':[{'item_number':'73',
            'anchor_raw_text':'ITEM 73','has_supply':True}]} if task=='STRUCTURE_SCOPE' else
            {'source_page':number,'raw_lines':[{'raw_visible_text':'ITEM 73: Suministro de instrumentos'}]}),1,200,[],None,None,None
    return scene,calls,vision


def run(harness,profile,**kwargs):
    scene,_,vision=harness
    def spatial_ocr(engine,image,language,timeout):
        scene[3].append((engine,language))
        return OcrInvocation('COMPLETED',True,dict(text='Unresolved visual columns',status='OCR_TEXT_EXTRACTED',
            engine=engine,engine_version='fixture-1',language=language))
    return execute_selective_pipeline(scene[0][0],tender_id=scene[0][1].id,profile=profile,
        ocr=kwargs.pop('ocr',spatial_ocr if profile.spatial_contracts else scene[2]),vision=kwargs.pop('vision',vision),
        prepare=lambda *args,**kwargs:None,materialize=kwargs.pop('materialize',lambda *args:None),**kwargs)


def spatial(profile,*tasks):
    return profile.model_copy(update={'spatial_contracts':tuple(__import__('app.blind_selective_profile',fromlist=['SpatialContract']).SpatialContract(
        task=t,requirement='IMAGE_LAYOUT_RELATIONSHIP') for t in tasks)})


def test_BH01_BH20_historical_zero_calls(harness,profile):
    safe=profile.model_copy(update={'profile':'HISTORICAL_SAFE','execution_policy':'AVAILABLE_ONLY'})
    result=run(harness,spatial(safe,'STRUCTURE_SCOPE'))
    assert harness[0][3]==[] and harness[1]==[] and all(e.calls==0 for e in result.providers)


def test_BH02_native_sufficient(harness,profile):
    from test_selective_ocr_recovery import TEXT
    scene=harness[0];norm(scene[0][0],scene[0][3],text=TEXT)
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert not harness[0][3] and not harness[1]
    assert result.perception_metrics['ocr']['native_sufficient']>=1


def test_BH03_planned_ocr(harness,profile):
    result=run(harness,profile)
    assert len(harness[0][3])==1 and any(r.status=='COMPLETED' for r in result.ocr_results)


@pytest.mark.parametrize('method',['OCR','VISION'])
def test_BH04_BH06_unplanned_rejected(harness,profile,method):
    db,tender,doc,page=harness[0][0]
    requests,visual=construct_tasks(db,doc,spatial(profile,'STRUCTURE_SCOPE'))
    if method=='OCR':
        p=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,requests=requests,execution_policy='AUTO')[0]
    else:
        p=plan_document_vision_tasks(db,tender_id=tender.id,document_id=doc.id,requests=visual,execution_policy='AUTO')[0]
    guard=ProviderCallGuard(profile,ocr=lambda *args:pytest.fail('unplanned'),vision=lambda *args:pytest.fail('unplanned'))
    with pytest.raises(ProtocolViolation,match='UNPLANNED'):
        guard.allowed(method,p)
    assert guard.events[0].calls==0 and guard.events[0].status=='REJECTED'


def test_BH05_BH19_vision_independent(harness,profile):
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert set(harness[1])=={'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'}
    assert {e.configuration.get('task') for e in result.providers if e.source_method=='VISION' and not e.configuration.get('decision_only')}=={'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'}


def test_BH07_available_only_in_selective(harness,profile):
    result=run(harness,spatial(profile.model_copy(update={'execution_policy':'AVAILABLE_ONLY'}),'STRUCTURE_SCOPE'))
    assert not harness[1] and not harness[0][3]
    assert any(r.status=='DEFERRED' for r in result.vision_results)


def test_BH08_BH13_shared_vision_budget(harness,profile):
    profile=profile.model_copy(update={'vision':profile.vision.model_copy(update={'max_calls':1})})
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'))
    assert len(harness[1])==1 and any(r.status=='BUDGET_EXHAUSTED' for r in result.vision_results)


def test_BH09_finite_ocr_budget(harness,profile):
    profile=profile.model_copy(update={'ocr':profile.ocr.model_copy(update={'max_calls':0})})
    result=run(harness,profile)
    assert not harness[0][3] and result.perception_metrics['ocr_budget_exhausted']>=1
    assert all(e.calls==0 for e in result.providers)


def test_BH10_completed_reuse(harness,profile):
    first=run(harness,spatial(profile,'STRUCTURE_SCOPE'))
    before=(len(harness[0][3]),len(harness[1]))
    second=run(harness,spatial(profile,'STRUCTURE_SCOPE'))
    assert before==(len(harness[0][3]),len(harness[1]))
    assert any(r.reused for r in second.vision_results)


def test_BH11_exhausted_no_more_calls(harness,profile):
    calls=[]
    def fail(*args):
        calls.append(1);return 'FAILED',None,1,None,[],None,None,None
    run(harness,spatial(profile,'STRUCTURE_SCOPE'),vision=fail)
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE'),vision=lambda *args:pytest.fail('exhausted'))
    assert len(calls)==2 and result.vision_results[0].status=='RETRY_EXHAUSTED'


def test_BH12_guard_config_mismatch(harness,profile):
    db,tender,doc,page=harness[0][0]
    requests,_=construct_tasks(db,doc,profile)
    p=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,requests=requests,execution_policy='AUTO')[0]
    guard=ProviderCallGuard(profile);guard.register('OCR',p)
    with pytest.raises(ProtocolViolation,match='CONFIGURATION'):
        guard.ocr(p,'PADDLEOCR',b'synthetic','es',30)


def test_BH14_native_preserved_failure(harness,profile):
    scene=harness[0];n=norm(scene[0][0],scene[0][3],text='Native heading')
    before=n.id,n.content_sha256,scene[0][3].text
    run(harness,profile,ocr=lambda *args:OcrInvocation('FAILED',True,error='synthetic'))
    assert before==(n.id,n.content_sha256,scene[0][3].text)


def test_BH17_generic_task_construction(harness,profile):
    db,_,doc,page=harness[0][0]
    first=construct_tasks(db,doc,profile)
    doc.original_filename='unrelated.pdf'
    assert construct_tasks(db,doc,profile)==first
    assert not any(first[1].values())  # No spatial contract means no automatic visual need.


def test_BH18_eligibility_vs_execution(harness,profile):
    result=run(harness,profile.model_copy(update={'execution_policy':'AVAILABLE_ONLY'}))
    assert result.perception_metrics['ocr']['ocr_eligible']>0
    assert result.perception_metrics['ocr']['ocr_executed']==0


def test_required_ocr_bound(profile):
    data=profile.model_dump(mode='json');del data['ocr']['max_calls']
    with pytest.raises(ValueError):SelectiveProfile.model_validate(data)


def test_no_legacy_policy_weakening(profile):
    data=profile.model_dump(mode='json');data['profile']='HISTORICAL_SAFE'
    with pytest.raises(ValueError,match='AVAILABLE_ONLY'):SelectiveProfile.model_validate(data)


def test_no_budget_increase(profile):
    data=profile.model_dump(mode='json');data['vision']['max_calls']=5
    with pytest.raises(ValueError):SelectiveProfile.model_validate(data)


@pytest.fixture
def frozen_context(tmp_path,monkeypatch,profile):
    import app.blind_selective_freeze as f
    identity=dict(head='a'*40,tracked_clean=True,code_sha256={'synthetic':'b'*64},code_manifest_sha256='c'*64)
    empty=dict(database='licitia_validation_06v',revision=profile.alembic_revision,tender_count=0,document_count=0)
    availability={'inference_calls':0,'synthetic':True}
    monkeypatch.setattr(f,'code_identity',lambda root:identity.copy())
    monkeypatch.setattr(f,'runtime_preflight',lambda p:availability.copy())
    monkeypatch.setattr(f,'database_identity',lambda db:empty.copy())
    from app.blind_schema_drift import ACCEPTED_DRIFT
    monkeypatch.setattr(f,'observe_schema_drift',lambda db:ACCEPTED_DRIFT)
    # Unit tests write only synthetic evidence beneath pytest tmp_path, never real blind roots.
    directory=f.create_pre_execution_freeze(None,root=tmp_path,output_root=tmp_path/'synthetic',
        run_id='synthetic-BH',profile=profile,availability=availability)
    return f,directory,tmp_path,empty,availability


def test_BH15_complete_freeze(frozen_context,profile):
    f,directory,root,_,_=frozen_context
    payload=f.read_evidence(directory/'pre_execution.json')
    assert payload['profile']==profile.model_dump(mode='json')
    assert payload['versions']['vision_fingerprint']=='selective-vision-v1'
    assert payload['versions']['structure_schema_sha256']
    with pytest.raises(FileExistsError):
        f.create_pre_execution_freeze(None,root=root,output_root=root/'synthetic',run_id='synthetic-BH',
            profile=profile,availability=payload['availability'])


def test_BH16_binding_separate_immutable(frozen_context,profile,monkeypatch):
    f,directory,root,database,_=frozen_context
    before=(directory/'pre_execution.json').read_bytes()
    database['tender_count']=1
    monkeypatch.setattr(f,'input_identity',lambda *args,**kwargs:dict(tender_id='synthetic',documents=[],generations={'pages':[]}))
    f.bind_import(None,directory=directory,root=root,profile=profile,tender_id='synthetic')
    assert (directory/'pre_execution.json').read_bytes()==before
    with pytest.raises(FileExistsError):
        f.bind_import(None,directory=directory,root=root,profile=profile,tender_id='synthetic')


def test_tampered_freeze_rejected(frozen_context):
    f,directory,*_=frozen_context
    p=directory/'pre_execution.json';data=json.loads(p.read_bytes());data['payload']['run_id']='tampered';p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='HASH_MISMATCH'):f.read_evidence(p)


def test_no_execution_without_authorization(frozen_context,profile):
    f,directory,root,*_=frozen_context
    with pytest.raises(PermissionError):f.execute_frozen_run(None,directory=directory,root=root,profile=profile)


def test_ocr_sufficient_avoids_visual_recovery(harness,profile):
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE'),ocr=harness[0][2])
    assert not harness[1] and any(p.status=='SUFFICIENT_FOR_TASK' for p in result.vision_plans)


def test_failed_attempt_cannot_run_twice(frozen_context,profile,monkeypatch):
    f,directory,root,database,_=frozen_context
    database['tender_count']=1
    binding=dict(tender_id='synthetic',documents=[],generations={'pages':[]})
    monkeypatch.setattr(f,'input_identity',lambda *args,**kwargs:binding)
    f.bind_import(None,directory=directory,root=root,profile=profile,tender_id='synthetic')
    import app.blind_selective_harness as h
    def fail(*args,**kwargs):raise ValueError('synthetic operational defect')
    monkeypatch.setattr(h,'execute_selective_pipeline',fail)
    with pytest.raises(ValueError,match='operational defect'):
        f.execute_frozen_run(None,directory=directory,root=root,profile=profile,authorized=True)
    assert (directory/'BLOCKED.json').is_file()
    with pytest.raises(FileExistsError):
        f.execute_frozen_run(None,directory=directory,root=root,profile=profile,authorized=True)


def test_provider_events_preserved_on_pipeline_error(harness,profile,tmp_path):
    events=[]
    def fail(*args):raise RuntimeError('synthetic domain defect')
    with pytest.raises(RuntimeError,match='domain defect'):
        run(harness,profile,materialize=fail,event_sink=events.append)
    assert any(e.calls==1 for e in events)
    assert any(e.configuration.get('decision_only') for e in events)


def test_guard_policy_rejected_even_if_registered(harness,profile):
    db,tender,doc,page=harness[0][0]
    requests,_=construct_tasks(db,doc,profile)
    p=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,requests=requests,execution_policy='AUTO')[0]
    safe=profile.model_copy(update={'profile':'HISTORICAL_SAFE','execution_policy':'AVAILABLE_ONLY'})
    guard=ProviderCallGuard(safe);guard.register('OCR',p)
    with pytest.raises(ProtocolViolation,match='POLICY'):guard.allowed('OCR',p)


def test_unknown_ocr_execution_ack_preserved(harness,profile):
    result=run(harness,profile,ocr=lambda *args:OcrInvocation('FAILED',None,error='timeout unknown'))
    assert any(e.calls is None for e in result.providers)


def test_canonical_materialization_consumes_new_perception(harness,profile):
    from app.blind_selective_harness import materialize_canonical
    from app.models import TenderScopeDetail
    from sqlalchemy import select
    result=run(harness,profile,materialize=materialize_canonical)
    db,tender,doc,page=harness[0][0]
    assert db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==tender.id)).all()
    assert result.metrics['first_pass']['domains']['SCOPE']['total']>=1


def test_offline_preflight_does_not_import_or_invoke_motors(tmp_path,profile,monkeypatch):
    import app.blind_selective_freeze as f
    import builtins
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in {'paddle','paddleocr','pytesseract'}:pytest.fail('motor import')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    monkeypatch.setattr(f.shutil,'which',lambda name:None)
    report=f.runtime_preflight(profile)
    assert report['inference_calls']==0 and report['service_availability']=='NOT_PROBED'
    assert report['model_manifest_sha256'] is None


@pytest.mark.parametrize('dimension',['max_calls','max_tasks','max_pages'])
def test_shared_vision_dimensions(harness,profile,dimension):
    profile=profile.model_copy(update={'vision':profile.vision.model_copy(update={dimension:0})})
    result=run(harness,spatial(profile,'STRUCTURE_SCOPE'))
    assert not harness[1] and any(r.status=='BUDGET_EXHAUSTED' for r in result.vision_results)


def test_freeze_detects_profile_changes(frozen_context,profile):
    f,directory,root,*_=frozen_context
    changed=profile.model_copy(update={'execution_policy':'AVAILABLE_ONLY'})
    with pytest.raises(ValueError,match='PROFILE_CHANGED'):
        f.verify_execution_identity(directory,root,changed)


def test_binding_requires_no_prior_perception(frozen_context,profile,monkeypatch):
    f,directory,root,database,_=frozen_context;database['tender_count']=1
    monkeypatch.setattr(f,'input_identity',lambda *args,**kwargs:dict(tender_id='synthetic',documents=[],generations={'pages':['synthetic-page']}))
    with pytest.raises(ValueError,match='BEFORE_CORPUS_EXECUTION'):
        f.bind_import(None,directory=directory,root=root,profile=profile,tender_id='synthetic')


def test_successful_synthetic_freeze_is_not_reexecutable(frozen_context,profile,monkeypatch):
    from types import SimpleNamespace
    from app.document_intelligence_validation_metrics import ValidationSnapshot,collect_metrics
    import app.blind_selective_harness as h
    f,directory,root,database,_=frozen_context;database['tender_count']=1
    binding=dict(tender_id='synthetic',documents=[],generations={'pages':[]})
    monkeypatch.setattr(f,'input_identity',lambda *args,**kwargs:binding)
    f.bind_import(None,directory=directory,root=root,profile=profile,tender_id='synthetic')
    snapshot=ValidationSnapshot(tender_id='synthetic')
    monkeypatch.setattr(h,'execute_selective_pipeline',lambda *args,**kwargs:SimpleNamespace(
        snapshot=snapshot,metrics=collect_metrics(snapshot),perception_metrics={},providers=()))
    digest=f.execute_frozen_run(None,directory=directory,root=root,profile=profile,authorized=True)
    assert json.loads((directory/'FROZEN.json').read_bytes())['first_pass_sha256']==digest
    with pytest.raises(FileExistsError):
        f.execute_frozen_run(None,directory=directory,root=root,profile=profile,authorized=True)


def test_harness_never_uses_legacy_acquisition(harness,profile,monkeypatch):
    import app.document_structure_orchestrator as o
    monkeypatch.setattr(o,'_default_ocr_executor',lambda *args:pytest.fail('legacy OCR'))
    monkeypatch.setattr(o,'_default_vision_executor',lambda *args:pytest.fail('legacy Vision'))
    from app.blind_selective_harness import materialize_canonical
    run(harness,profile,materialize=materialize_canonical)


def test_non_inference_ocr_probe_reports_effective_tessdata(tmp_path,profile,monkeypatch):
    import app.blind_selective_freeze as f
    from types import SimpleNamespace
    binary=tmp_path/'bin'/'tesseract';binary.parent.mkdir();binary.write_text('synthetic executable')
    packs=tmp_path/'tessdata';packs.mkdir()
    (packs/'spa.traineddata').write_bytes(b'synthetic');(packs/'eng.traineddata').write_bytes(b'synthetic')
    monkeypatch.setattr(f.shutil,'which',lambda name:str(binary))
    commands=[]
    def probe(command,**kwargs):
        commands.append(command)
        return SimpleNamespace(stdout=('tesseract 5.5.3\n' if command[-1]=='--version' else
            f'List of available languages in "{packs}" (2):\neng\nspa\n'),stderr='')
    monkeypatch.setattr(f.subprocess,'run',probe)
    result=f.runtime_preflight(profile)
    assert result['ocr_binary_version']=='5.5.3' and result['effective_tessdata']==str(packs)
    assert result['ocr_runtime_languages']==['eng','spa'] and result['inference_calls']==0
    assert all(c[-1] in {'--version','--list-langs'} for c in commands)
