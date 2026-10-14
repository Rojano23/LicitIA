"""Synthetic, Tender-neutral preflight tests. No blind corpus or provider execution."""
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess

import pytest
from sqlalchemy import select, text

from app.document_intelligence_validation_metrics import (
    DOMAINS, MetricRecord, ProviderMetric, ValidationSnapshot, HumanTruth, HumanJudgment,
    collect_metrics, adjudicate, snapshot_tender, database_identity)
from app.document_intelligence_blind_run import (
    BlindConfig, FirstPass, capture_code_identity, canonical_bytes, sha256,
    freeze_first_pass, verify_frozen, freeze_analysis, assert_tuning_allowed, load_config, ExecutionLog)
from test_document_intelligence_integration import corpus, norm
from test_requirement_perception_provenance import logical
ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'backend/evals/document_intelligence_06v_config_v1.json'

@pytest.fixture
def synthetic_identity(tmp_path, monkeypatch):
    # Identity mechanics use a synthetic repository, not Attempt #1's frozen code.
    root=tmp_path/'repository'; file=root/'backend/app/synthetic.py'
    file.parent.mkdir(parents=True); file.write_text('synthetic = True\n')
    config=root/'backend/evals/config.json'; config.parent.mkdir(parents=True)
    data=json.loads(CONFIG.read_bytes())
    data['code_file_sha256']={'backend/app/synthetic.py':sha256(file.read_bytes())}
    config.write_bytes(canonical_bytes(data))
    original=subprocess.check_output
    def git(args, **kwargs):
        if args[0] != 'git': return original(args, **kwargs)
        if args[1]=='rev-parse': return 'a'*40+'\n'
        if args[1]=='status': return ''
        if args[1]=='ls-files': return 'backend/app/synthetic.py\nbackend/evals/config.json\n'
        raise AssertionError(args)
    monkeypatch.setattr(subprocess,'check_output',git)
    return root,config

@pytest.fixture
def snapshot():
    records=[]
    for domain in DOMAINS:
        records.extend((MetricRecord(id=domain+'-a',domain=domain,state='TRUSTED',automatic=True,
            document_id='synthetic-doc',page_id='synthetic-page',version_state='ACTIVE' if domain=='VERSIONS' else None),
            MetricRecord(id=domain+'-b',domain=domain,state='REVIEW_REQUIRED',reason='AMBIGUOUS',
                unresolved_binding=domain in {'SCOPE','QUANTITIES'},document_id='synthetic-doc',page_id='synthetic-page',
                version_state='REVIEW_REQUIRED' if domain=='VERSIONS' else None)))
    return ValidationSnapshot(tender_id='independent-synthetic-tender',page_ids=('synthetic-page',),records=tuple(records),
        providers=(ProviderMetric(id='synthetic-call',provider='synthetic',source_method='VISION',model='fixture',
            capability='STRUCTURE',status='FAILED',calls=1,latency_ms=25,truncated=True),),
        stale_carry_violations=0)

@pytest.fixture
def report(snapshot):
    timestamp=datetime(2026,1,1,tzinfo=timezone.utc)
    return FirstPass(run_id='synthetic-run',started_at=timestamp,ended_at=timestamp,
        code_identity={'commit':'a'*40,'protected_dirty':False,'config_sha256':'b'*64},
        database_identity={'database':'licitia_validation_06v','revision':'20261013_req_perception_prov_072'},
        snapshot=snapshot,metrics=collect_metrics(snapshot))

def test_VF01_generic(snapshot):assert collect_metrics(snapshot)['first_pass']['documents_total']==2
def test_VF02_separation(snapshot):
    result=collect_metrics(snapshot)
    assert result['first_pass']['domains']['REQUIREMENTS']['trusted']==1
    assert all(value is None for value in result['post_adjudication'].values())

def domain_count(snapshot,domain):
    a=collect_metrics(snapshot)['first_pass']['domains'][domain]
    assert a['total']==a['discovered']==2 and a['trusted']==a['review_required']==1
    assert collect_metrics(snapshot)==collect_metrics(snapshot.model_copy(update={'records':tuple(reversed(snapshot.records))}))
def test_VF03_requirements(snapshot):domain_count(snapshot,'REQUIREMENTS')
def test_VF04_evidence(snapshot):domain_count(snapshot,'REQUESTED_EVIDENCE')
def test_VF05_scope(snapshot):domain_count(snapshot,'SCOPE')
def test_VF06_attributes(snapshot):domain_count(snapshot,'ATTRIBUTES')
def test_VF07_quantities(snapshot):domain_count(snapshot,'QUANTITIES')
def test_VF08_versions(snapshot):assert collect_metrics(snapshot)['first_pass']['versions']=={'ACTIVE':1,'REVIEW_REQUIRED':1}
def test_VF09_reviews(snapshot):
    review=collect_metrics(snapshot)['first_pass']['review_queue']
    assert review['total']==len(DOMAINS) and review['by_reason']=={'AMBIGUOUS':len(DOMAINS)}
    assert review['pages_affected']==review['documents_affected']==1

def test_VF10_provider(snapshot):
    p=collect_metrics(snapshot)['first_pass']['providers'][0]
    assert (p['calls'],p['failure'],p['truncations'],p['latencies_ms'])==(1,1,1,[25])
    missing=snapshot.model_copy(update={'providers':(snapshot.providers[0].model_copy(update={'calls':None}),)})
    assert collect_metrics(missing)['first_pass']['providers'][0]['calls'] is None
    event=snapshot.providers[0].model_copy(update={'id':'event-1','calls':2,'execution_event':True})
    both=missing.model_copy(update={'providers':(*missing.providers,event)})
    result=collect_metrics(both)['first_pass']['providers'][0]
    assert result['calls']==2 and result['artifacts']==result['execution_events']==1

def test_VF11_automation(snapshot):
    domain=collect_metrics(snapshot)['first_pass']['domains']['SCOPE']
    assert domain['trusted_automatic_rate_unadjudicated']==domain['review_required_rate']==0.5

def test_VF12_unsafe_unknown(snapshot):assert collect_metrics(snapshot)['post_adjudication']['unsafe_trusted_contractual_errors'] is None
def test_VF13_manifest():assert load_config(CONFIG).metrics_schema=='DI_BLIND_METRICS_001'
def test_VF14_transcription_excluded():
    data=json.loads(CONFIG.read_text());data['provider_policy']['vision_full_page_transcription_automatic']=True
    with pytest.raises(ValueError,match='transcription'):BlindConfig.model_validate(data)
def test_VF15_structure_bounded():
    policy=load_config(CONFIG).provider_policy
    assert policy['vision_structure_eligible'] is True
    assert policy['vision_structure_requires_grounding_review_and_explicit_authorization'] is True
    assert policy['provider_calls_authorized']==0

def test_VF16_code_sha(synthetic_identity):assert len(capture_code_identity(*synthetic_identity,require_clean=False)['commit'])==40
def test_VF17_config_sha(synthetic_identity):assert capture_code_identity(*synthetic_identity,require_clean=False)['config_sha256']==sha256(synthetic_identity[1].read_bytes())
def test_VF18_dirty_capture(monkeypatch, synthetic_identity):
    original=subprocess.check_output
    def output(args,**kwargs):
        if args[:2]==['git','status']:return ' M backend/app/document_intelligence.py\n?? backend/reports/runtime.json\n'
        return original(args,**kwargs)
    monkeypatch.setattr(subprocess,'check_output',output)
    identity=capture_code_identity(*synthetic_identity,require_clean=False)
    assert identity['protected_dirty'] and len(identity['protected_status'])==1
    with pytest.raises(ValueError,match='Dirty'):capture_code_identity(*synthetic_identity)

def test_VF19_serialization(report):assert canonical_bytes(report)==canonical_bytes(FirstPass.model_validate_json(canonical_bytes(report)))
def test_VF20_no_overwrite(report,tmp_path):
    freeze_first_pass(report,tmp_path)
    before=(tmp_path/report.run_id/'first_pass.json').read_bytes()
    with pytest.raises(FileExistsError):freeze_first_pass(report,tmp_path)
    assert (tmp_path/report.run_id/'first_pass.json').read_bytes()==before

def test_VF21_hash(report,tmp_path):
    marker=freeze_first_pass(report,tmp_path)
    assert marker['first_pass_sha256']==sha256((tmp_path/report.run_id/'first_pass.json').read_bytes())

def truth(report,digest):
    return HumanTruth(approved_by_human=True,authority='INDEPENDENT_HUMAN_TRUTH',reviewer='synthetic human',revision='synthetic-v1',
        frozen_first_pass_sha256=digest,judgments=(HumanJudgment(domain='SCOPE',record_id='SCOPE-a',truth_id='independent-fact',disposition='TRUSTED_INCORRECT'),))

def test_VF22_analysis_separate(report,tmp_path):
    marker=freeze_first_pass(report,tmp_path);directory=tmp_path/report.run_id
    result=freeze_analysis(directory,truth(report,marker['first_pass_sha256']),'review1')
    assert result.name=='analysis_review1.json' and verify_frozen(directory)==report
    with pytest.raises(FileExistsError):freeze_analysis(directory,truth(report,marker['first_pass_sha256']),'review1')

def test_VF23_db_revision(report):assert report.database_identity['revision']=='20261013_req_perception_prov_072'
def test_VF24_empty_db(corpus):
    db,_,_,_=corpus
    identity=database_identity(db)
    assert identity['database']=='licitia_test' and identity['tender_count']>0
    # Empty detection is independent from names/contents and never queries other corpus tables.
    assert identity['revision']=='20261013_req_perception_prov_072'
    # V.0's historical empty validation DB is no longer a test fixture.
    # Empty-state identity is exercised with a synthetic read-only query interface.
    class EmptyDatabase:
        def execute(self, statement):
            sql=str(statement)
            value='licitia_validation_06v' if 'current_database' in sql else identity['revision'] if 'alembic_version' in sql else 0
            class Result:
                def scalar_one(self): return value
            return Result()
    empty=database_identity(EmptyDatabase())
    assert empty['tender_count']==empty['document_count']==0
    assert empty['revision']==identity['revision']

def test_VF25_no_blind_corpus(snapshot,monkeypatch):
    assert snapshot.tender_id=='independent-synthetic-tender'
    with pytest.raises(PermissionError):snapshot_tender(None,'any-tender')
    from scripts import run_document_intelligence_06v as runner
    def forbidden(*args,**kwargs):raise AssertionError('Unauthorized database access')
    monkeypatch.setattr(runner,'create_engine',forbidden)
    with pytest.raises(PermissionError):runner.main(['--database-url','postgresql+psycopg://localhost/unused'])

def test_VF26_no_provider(corpus,monkeypatch):
    from app.ollama_vision import OllamaVisionAssistClient
    from app.ocr import TesseractOCRProvider,PaddleOCRProvider
    calls=[]
    def forbidden(*args,**kwargs):calls.append(True);raise AssertionError('Acquisition forbidden')
    for obj,name in [(OllamaVisionAssistClient,'_execute_task'),(TesseractOCRProvider,'recognize'),(PaddleOCRProvider,'recognize')]:
        monkeypatch.setattr(obj,name,forbidden)
    db,tender,doc,page=corpus;norm(db,page,text='PARTIDA 17 servicio')
    result=snapshot_tender(db,tender.id,authorized_import=True)
    assert result.tender_id==tender.id and not calls

def test_VF27_neutral_ids(snapshot):
    changed=snapshot.model_copy(update={'tender_id':'another-arbitrary-id'})
    assert collect_metrics(changed)==collect_metrics(snapshot)

def test_VF28_no_tuning_before_freeze(report,tmp_path):
    with pytest.raises(FileNotFoundError):assert_tuning_allowed(tmp_path/report.run_id)
    freeze_first_pass(report,tmp_path);assert_tuning_allowed(tmp_path/report.run_id)

def test_VF29_no_truth_required(snapshot):assert collect_metrics(snapshot)['first_pass']['pages_total']==1
def test_VF30_independent_truth_later(report,tmp_path):
    marker=freeze_first_pass(report,tmp_path)
    result=adjudicate(report.snapshot,truth(report,marker['first_pass_sha256']),marker['first_pass_sha256'])
    assert result['post_adjudication']['unsafe_trusted_contractual_errors']==1
    assert result['coverage']['observed_unjudged']==len(report.snapshot.records)-1
    with pytest.raises(ValueError):HumanTruth.model_validate({**truth(report,marker['first_pass_sha256']).model_dump(),'authority':'MODEL_DERIVED'})


def test_tamper_and_path_controls(report,tmp_path):
    freeze_first_pass(report,tmp_path);directory=tmp_path/report.run_id
    (directory/'first_pass.json').write_text('{}')
    with pytest.raises(ValueError,match='tampered'):verify_frozen(directory)
    with pytest.raises(ValueError):FirstPass.model_validate({**report.model_dump(),'run_id':'../escape'})

def test_db_collector_actual_domains(corpus):
    from app.models import Requirement,RequirementSemantics,RequirementEvidenceExpectation,TenderScopeDetail,TenderScopeQuantity,TenderScopeAttribute
    from decimal import Decimal
    db,tender,doc,page=corpus;norm(db,page,text='PARTIDA 17 servicio')
    requirement=Requirement(tender_id=tender.id,canonical_key='synthetic',canonical_text='synthetic obligation',normalization_status='REVIEW_REQUIRED')
    db.add(requirement);db.flush()
    semantics=RequirementSemantics(requirement_id=requirement.id,interpretation_status='REVIEW_REQUIRED')
    db.add(semantics);db.flush()
    db.add(RequirementEvidenceExpectation(requirement_semantics_id=semantics.id,requirement_id=requirement.id,evidence_type='OTHER',excerpt_sha256='a'*64))
    detail=TenderScopeDetail(tender_id=tender.id,source_document_id=doc.id,document_page_id=page.id,domain='SUPPLY',description='synthetic',applicability='UNRESOLVED',
        source_method='NATIVE',source_artifact_key='fixture',source_locator='page:1',source_excerpt='synthetic',semantic_fingerprint='d'*64,review_required=True)
    db.add(detail);db.flush()
    result=snapshot_tender(db,tender.id,authorized_import=True)
    metrics=collect_metrics(result)['first_pass']['domains']
    assert metrics['REQUIREMENTS']['total']==metrics['REQUESTED_EVIDENCE']['total']==metrics['SCOPE']['total']==1
    assert metrics['SCOPE']['unresolved_binding']==1
    assert metrics['VERSIONS']['total']==1
    assert collect_metrics(snapshot_tender(db,tender.id,authorized_import=True))==collect_metrics(result)


def test_db_collector_quantity_attribute_traceability(logical):
    from test_critical_identifier_propagation import children
    rows,quantities,attributes=children(logical)
    db,_,_=logical
    result=snapshot_tender(db,rows[0].tender_id,authorized_import=True)
    metrics=collect_metrics(result)['first_pass']
    assert metrics['domains']['QUANTITIES']['total']==len(quantities)==2
    assert metrics['domains']['ATTRIBUTES']['total']==len(attributes)==2
    assert metrics['domain_impact']['traceable_links']['SCOPE->QUANTITIES']==2
    assert metrics['domain_impact']['traceable_links']['SCOPE->ATTRIBUTES']==2
