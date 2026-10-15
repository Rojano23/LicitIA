"""FB evidence-only closure; synthetic files/rows and drift observations."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
import pytest
from app.document_intelligence_blind_run import canonical_bytes,sha256
from app.blind_selective_freeze import input_identity,bind_import,read_evidence,verify_execution_identity,write_evidence
from app.blind_schema_drift import ACCEPTED_DRIFT,verify_accepted_drift,normalize_differences
from app.document_perception_planner import plan_document_ocr_tasks,TaskRequest,PerceptionTask as T
from test_blind_selective_harness import profile,frozen_context
from test_selective_ocr_recovery import scene
from test_document_intelligence_integration import corpus


def identity(scene):
    db,tender,document,_=scene[0]
    document.file_size_bytes=(scene[4]/'synthetic.pdf').stat().st_size
    db.flush()
    return input_identity(db,tender_id=tender.id)


def test_FB01_filename_exact_in_canonical_identity(scene):
    document=scene[0][2];document.original_filename='Álfa  _R01.PDF'
    assert identity(scene)['documents'][0]['original_filename']=='Álfa  _R01.PDF'


def test_FB02_filename_changes_digest_only_metadata(scene):
    before=identity(scene)
    scene[0][2].original_filename='renamed.pdf'
    after=identity(scene)
    assert sha256(canonical_bytes(before))!=sha256(canonical_bytes(after))
    assert {k:v for k,v in before['documents'][0].items() if k!='original_filename'}=={
        k:v for k,v in after['documents'][0].items() if k!='original_filename'}


def test_FB03_filename_not_in_task_or_perception_identity(scene):
    db,tender,document,page=scene[0]
    requests={page.id:(TaskRequest(T.SCOPE),)}
    before=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=document.id,requests=requests)
    scene[0][2].original_filename='Different neutral source.pdf'
    after=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=document.id,requests=requests)
    assert before==after and asdict(before[0])==asdict(after[0])


def test_FB04_pre_freeze_records_drift_and_revision(frozen_context):
    f,directory,*_=frozen_context
    data=read_evidence(directory/'pre_execution.json')
    assert data['schema_version']=='DI_SELECTIVE_FREEZE_002'
    assert data['schema_drift']==ACCEPTED_DRIFT.model_dump(mode='json')
    assert data['database']['revision']==ACCEPTED_DRIFT.current_revision[0]


def test_FB05_correct_drift_verifies(frozen_context,profile):
    _,directory,root,*_=frozen_context
    assert verify_execution_identity(directory,root,profile)['schema_drift']['difference_count']==59


@pytest.mark.parametrize('field,value',[
    ('signature_sha256','0'*64),('difference_count',60),
    ('current_revision',('wrong-revision',)),('head_revision',('wrong-head',)),
    ('operations',{'add_index':54,'remove_index':5})])
def test_FB06_FB07_FB08_changed_observed_drift_blocks(frozen_context,profile,monkeypatch,field,value):
    f,directory,root,*_=frozen_context
    data=ACCEPTED_DRIFT.model_dump();data[field]=value
    monkeypatch.setattr(f,'observe_schema_drift',lambda db:data)
    with pytest.raises(ValueError,match='OBSERVED_SCHEMA_DRIFT_MISMATCH'):
        verify_execution_identity(directory,root,profile)


@pytest.mark.parametrize('field,value',[('signature_sha256','0'*64),('difference_count',60)])
def test_changed_frozen_baseline_blocks_even_with_rehashed_file(frozen_context,profile,field,value):
    _,directory,root,*_=frozen_context
    path=directory/'pre_execution.json';data=read_evidence(path)
    data['schema_drift'][field]=value
    # Simulate an externally replaced artifact; never rewrite production evidence.
    path.write_bytes(canonical_bytes({'payload':data,'sha256':sha256(canonical_bytes(data))}))
    with pytest.raises(ValueError,match='FROZEN_SCHEMA_DRIFT_MISMATCH'):
        verify_execution_identity(directory,root,profile)


def test_FB08_database_revision_independent(frozen_context,profile):
    f,directory,root,database,availability=frozen_context
    database['revision']='wrong-revision'
    with pytest.raises(ValueError,match='EMPTY_VALIDATION_DATABASE_REQUIRED'):
        f.create_pre_execution_freeze(None,root=root,output_root=root/'another-synthetic',
            run_id='synthetic-fb',profile=profile,availability=availability)


def test_FB09_binding_filename_without_mutating_freeze(frozen_context,profile,scene):
    f,directory,root,database,_=frozen_context
    before=(directory/'pre_execution.json').read_bytes()
    db,tender,document,page=scene[0]
    document.file_size_bytes=(scene[4]/'synthetic.pdf').stat().st_size
    from app.models import DocumentPage
    # Match canonical post-import/pre-extraction state in this synthetic fixture.
    db.delete(page);db.flush()
    database['tender_count']=1;database['document_count']=1
    bind_import(db,directory=directory,root=root,profile=profile,tender_id=tender.id)
    binding=read_evidence(directory/'input_binding.json')
    assert binding['input']['documents'][0]['original_filename']==document.original_filename
    assert (directory/'pre_execution.json').read_bytes()==before
    with pytest.raises(FileExistsError):
        bind_import(db,directory=directory,root=root,profile=profile,tender_id=tender.id)


def test_FB10_legacy_blind_configuration_unaffected():
    from app.document_intelligence_blind_run import load_config
    config=load_config(Path(__file__).resolve().parents[1]/'evals/document_intelligence_06v_config_v1.json')
    assert config.provider_policy['execution_policy']=='AVAILABLE_ONLY'
    assert config.provider_policy['provider_calls_authorized']==0


def test_FB11_profile_configuration_unchanged(profile):
    from app.blind_selective_profile import SelectiveProfile
    candidate=SelectiveProfile.model_validate(dict(profile='SELECTIVE_PERCEPTION',execution_policy='AUTO',
        ocr=dict(engine='TESSERACT',engine_version='5.5.3',language='es+en',max_calls=8,timeout_seconds=30),
        vision=dict(model='qwen3-vl:4b-instruct',model_revision='ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b',
            model_manifest='/Users/ceciliavalencia/.ollama/models/manifests/registry.ollama.ai/library/qwen3-vl/4b-instruct'),
        spatial_contracts=[dict(task=t,requirement='IMAGE_LAYOUT_RELATIONSHIP') for t in ('STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION')]))
    assert sha256(canonical_bytes(candidate.model_dump(mode='json')))=='a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6'


def test_FB12_no_tender_specific_drift_input():
    assert verify_accepted_drift(ACCEPTED_DRIFT)['operations']=={'add_index':55,'remove_index':4}


def test_FI05_canonical_distinct_sources_auditable(scene):
    from app.models import Tender,TenderDocument
    db,tender,document,_=scene[0]
    first=identity(scene)
    other=Tender(title='Independent synthetic source',institution_profile='General');db.add(other);db.flush()
    clone=TenderDocument(tender_id=other.id,original_filename='another-name.pdf',stored_relative_path='synthetic-copy.pdf',
        mime_type=document.mime_type,file_size_bytes=document.file_size_bytes,sha256=document.sha256)
    db.add(clone);db.flush()
    second=input_identity(db,tender_id=other.id)
    assert first['documents'][0]['sha256']==second['documents'][0]['sha256']
    assert first['documents'][0]['id']!=second['documents'][0]['id']
    assert first['documents'][0]['original_filename']!=second['documents'][0]['original_filename']
    # Within a single Tender the canonical unique(tender_id, sha256) remains authoritative.


def test_non_index_drift_fails_closed():
    with pytest.raises(ValueError,match='UNACCEPTED_SCHEMA_DRIFT_OPERATION'):
        normalize_differences([('add_table',object())])


def test_missing_drift_contract_is_not_silently_accepted(frozen_context,profile):
    _,directory,root,*_=frozen_context
    path=directory/'pre_execution.json';data=read_evidence(path);del data['schema_drift']
    path.write_bytes(canonical_bytes({'payload':data,'sha256':sha256(canonical_bytes(data))}))
    with pytest.raises(ValueError,match='CURRENT_DRIFT_FREEZE_CONTRACT_REQUIRED'):
        verify_execution_identity(directory,root,profile)


def test_DFZ06_canonical_comparison_is_read_only(corpus):
    from sqlalchemy import event
    from app.blind_schema_drift import observe_schema_drift
    db=corpus[0];engine=db.get_bind().engine
    statements=[]
    def inspect_sql(conn,cursor,statement,parameters,context,executemany):
        statements.append(statement.lstrip().split(None,1)[0].upper())
    event.listen(engine,'before_cursor_execute',inspect_sql)
    try:
        observed=observe_schema_drift(db)
    finally:
        event.remove(engine,'before_cursor_execute',inspect_sql)
    assert observed==ACCEPTED_DRIFT
    assert statements and set(statements)<={'SELECT','SET','SHOW'}


def test_renamed_bound_input_blocks_before_execution(frozen_context,profile,scene):
    f,directory,root,database,_=frozen_context
    db,tender,document,page=scene[0]
    document.file_size_bytes=(scene[4]/'synthetic.pdf').stat().st_size
    db.delete(page);db.flush();database['tender_count']=1;database['document_count']=1
    bind_import(db,directory=directory,root=root,profile=profile,tender_id=tender.id)
    document.original_filename='renamed-after-binding.pdf';db.flush()
    with pytest.raises(ValueError,match='IMPORTED_INPUT_CHANGED'):
        f.execute_frozen_run(db,directory=directory,root=root,profile=profile,authorized=True)
    assert not (directory/'EXECUTION_STARTED.json').exists()


def test_new_freeze_rejects_unaccepted_observation(frozen_context,profile,monkeypatch):
    f,_,root,_,availability=frozen_context
    changed=ACCEPTED_DRIFT.model_dump();changed['difference_count']=58
    monkeypatch.setattr(f,'observe_schema_drift',lambda db:changed)
    output_root=root/'synthetic-rejected'
    with pytest.raises(ValueError,match='OBSERVED_SCHEMA_DRIFT_MISMATCH'):
        f.create_pre_execution_freeze(None,root=root,output_root=output_root,run_id='synthetic-rejected',
            profile=profile,availability=availability)
    assert not output_root.exists()
