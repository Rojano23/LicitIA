"""Synthetic OCR/task contracts. No OCR engine, Vision, model or blind corpus."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from app.models import DocumentPageRegion, PageOcrResult, NormalizedContent, TenderScopeDetail
from app.document_perception_planner import PerceptionTask as T, TaskRequest, plan_ocr, plan_document_ocr_tasks, perception_metrics
from app.selective_ocr_executor import execute_planned_ocr, OcrInvocation
from app.scope_detail_materializer import materialize_document_scope_details
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from test_document_intelligence_integration import corpus, norm

TEXT = 'ITEM 73: Suministro de instrumentos | Marca: Delta | Modelo: Z-8 | Cantidad: 4 | Unidad: PZA'


@pytest.fixture
def scene(corpus, monkeypatch, tmp_path):
    import fitz
    import app.main as main
    import app.selective_ocr_executor as executor
    db,tender,doc,page = corpus
    pdf = fitz.open(); p = pdf.new_page(); p.insert_text((40,50),'synthetic scan')
    path = tmp_path/'synthetic.pdf'; pdf.save(path); pdf.close()
    doc.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(main, '_resolve_document_file_path', lambda relative: path)
    monkeypatch.setattr(executor, 'receipt_root', lambda: tmp_path/'receipts')
    region = DocumentPageRegion(document_page_id=page.id, region_index=1, region_type='IMAGE',
        x0=0,y0=0,x1=300,y1=300,width=300,height=300,area_ratio=.6)
    db.add(region); db.flush(); db.expire(page,['regions'])
    calls=[]
    def invoke(engine,image,language,timeout):
        calls.append((engine,language))
        return OcrInvocation('COMPLETED',True,dict(text=TEXT,status='OCR_TEXT_EXTRACTED',
            engine=engine,engine_version='fixture-1',language=language,confidence=None,
            processing_time_ms=None,warnings=[]))
    return corpus,region,invoke,calls,tmp_path


def plans(scene, task=T.SCOPE, *, policy='ALLOW_OCR', request=None):
    corpus,region,_,_,_=scene
    db,tender,doc,page=corpus
    return plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,
        requests={page.id:(request or TaskRequest(task),)},execution_policy=policy)


def execute(scene, plan=None, **kwargs):
    corpus,_,invoke,_,_=scene
    return execute_planned_ocr(corpus[0],plan or plans(scene)[0],engine='TESSERACT',
        engine_version=kwargs.pop('engine_version','fixture-1'),invoke=kwargs.pop('invoke',invoke),**kwargs)


def materialize(scene):
    db,tender,doc,page=scene[0]
    report=materialize_document_scope_details(db,tender_id=tender.id,document_id=doc.id)
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==doc.id)).all()
    return report,rows


def test_OC01_VP10_VP15_native_sufficient_no_calls(scene):
    corpus,_,_,calls,_=scene
    norm(corpus[0],corpus[3],text=TEXT)
    plan=plans(scene)[0]
    assert plan.native_sufficient and not plan.ocr_eligible
    assert execute(scene,plan).status=='SKIPPED' and not calls


def test_OC02_VP11_eligible_without_execution(scene):
    plan=plans(scene)[0]
    assert plan.ocr_eligible and not plan.native_sufficient and scene[3]==[]


def test_OC03_OC04_VP17_available_only(scene):
    plan=plans(scene,policy='AVAILABLE_ONLY')[0]
    assert plan.ocr_eligible
    result=execute(scene,plan)
    assert result.status=='DEFERRED' and not result.executed and not scene[3]
    assert not (scene[4]/'receipts').exists()


def test_OC05_OC06_task_specific(scene):
    corpus,_,_,calls,_=scene
    norm(corpus[0],corpus[3],text='ITEM 73: Suministro de instrumentos')
    scope=plans(scene,T.SCOPE)[0]
    quantity=plans(scene,request=TaskRequest(T.QUANTITIES,region_id=scene[1].id))[0]
    assert scope.native_sufficient and quantity.ocr_eligible
    execute(scene,scope); execute(scene,quantity)
    assert len(calls)==1


@pytest.mark.parametrize('task',list(T))
def test_task_contracts_not_text_length(scene,task):
    corpus=scene[0]
    norm(corpus[0],corpus[3],text='Administrative content. '*100)
    plan=plans(scene,task)[0]
    assert not plan.native_sufficient
    assert plan.status=='UNKNOWN' if task==T.TEXT else plan.ocr_eligible


def test_text_contract_explicit_grounding(scene):
    corpus=scene[0]
    norm(corpus[0],corpus[3],text='Required execution schedule is attached.')
    plan=plans(scene,request=TaskRequest(T.TEXT,('Required execution schedule',)))[0]
    assert plan.native_sufficient


def test_region_requires_coverage_proof(scene):
    corpus,region,_,_,_=scene
    norm(corpus[0],corpus[3],text=TEXT)
    assert plans(scene,request=TaskRequest(T.SCOPE,region_id=region.id))[0].ocr_eligible


def test_VP12_VP13_VP14_VP25_OCR_consumption(scene):
    result=execute(scene)
    assert result.status=='COMPLETED' and result.executed
    db=scene[0][0]
    row=db.get(PageOcrResult,result.result_id)
    assert row.engine=='TESSERACT' and row.status=='OCR_TEXT_EXTRACTED'
    receipt=json.loads(Path(result.receipt_path).read_text())
    assert receipt['identity']['original_sha256']==scene[0][2].sha256
    assert receipt['fingerprint']==result.fingerprint and receipt['image_sha256']
    assert db.scalar(select(NormalizedContent).where(NormalizedContent.page_ocr_result_id==row.id)).source_type=='OCR'
    report,details=materialize(scene)
    assert not any(r.errors for r in report.artifact_results)
    assert len(details)==1 and details[0].source_method=='OCR' and details[0].source_page_result_id is None
    detail=details[0]
    assert 'ocr_sha256:' in detail.source_locator and 'normalized:' in detail.source_locator
    assert result.fingerprint in detail.source_locator
    a=materialize_scope_attributes_for_scope_detail(db,scope_detail_id=detail.id)
    q=materialize_scope_quantities_for_scope_detail(db,scope_detail_id=detail.id)
    assert a.persisted_count==2 and q.persisted_count==1
    assert a.review_required_count==2 and q.review_required_count==1


def test_OP01_VP21_equivalent_work_reuses(scene):
    first=execute(scene);second=execute(scene)
    assert first.result_id==second.result_id and first.fingerprint==second.fingerprint
    assert not second.executed and len(scene[3])==1


def test_OP02_VP22_incompatible_config_deferred(scene):
    first=execute(scene)
    second=execute(scene,engine_version='fixture-2')
    assert second.status=='DEFERRED' and not second.executed and len(scene[3])==1
    assert scene[0][0].get(PageOcrResult,first.result_id).engine_version=='fixture-1'


def test_OP03_VP19_native_survives_failure(scene):
    corpus=scene[0]
    n=norm(corpus[0],corpus[3],text='Native heading')
    native=(n.id,n.normalized_text,n.content_sha256,corpus[3].text)
    failed=lambda *args:OcrInvocation('FAILED',True,error='synthetic timeout')
    result=execute(scene,plans(scene,request=TaskRequest(T.SCOPE,region_id=scene[1].id))[0],invoke=failed)
    assert result.status=='FAILED'
    assert (n.id,n.normalized_text,n.content_sha256,corpus[3].text)==native


def test_VP18_engine_unavailable(scene):
    result=execute(scene,invoke=lambda *args:OcrInvocation('UNAVAILABLE',False,error='missing engine'))
    assert result.status=='UNAVAILABLE' and not result.executed
    assert scene[0][0].scalars(select(PageOcrResult).where(PageOcrResult.document_page_id==scene[0][3].id)).all()==[]


@pytest.mark.parametrize('kind',['empty','malformed','exception','timeout'])
def test_VP26_VP27_failure_exhaustion(scene,kind):
    def fail(*args):
        if kind=='exception':raise RuntimeError('synthetic exception')
        if kind=='timeout':return OcrInvocation('FAILED',None,error='OCR_TIMEOUT')
        if kind=='malformed':return OcrInvocation('COMPLETED',True,{'text':123})
        return OcrInvocation('COMPLETED',True,dict(text='',status='NO_TEXT',engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    first=execute(scene,invoke=fail)
    assert first.status in {'FAILED','INVALID_OUTPUT'}
    second=execute(scene,invoke=lambda *args:pytest.fail('retry must not invoke'))
    assert second.reason=='RETRY_EXHAUSTED'
    assert scene[0][0].get(PageOcrResult,first.result_id).text==''
    assert materialize(scene)[1]==[]


def test_render_failure_no_provider(scene):
    def fail(*args):raise ValueError('synthetic render failure')
    result=execute(scene,render=fail)
    assert result.status=='RENDER_FAILED' and not scene[3]


def test_VP20_no_vision_fallback(scene):
    plan=plans(scene,request=TaskRequest(T.STRUCTURE,visual_relationships_required=True))[0]
    assert plan.status=='VISUAL_CAPABILITY_PENDING' and not plan.ocr_eligible
    assert execute(scene,plan).status=='SKIPPED'
    assert not scene[3]


def test_OI01_VP23_native_OCR_dedup(scene):
    execute(scene)
    corpus=scene[0]
    norm(corpus[0],corpus[3],text=TEXT)
    report,rows=materialize(scene)
    assert len(rows)==1 and len(report.logical_evidence[0].source_artifact_keys)==2


def test_OI03_distinct_items(scene):
    text=TEXT+'\n'+TEXT.replace('73','74').replace('4 |','8 |')
    invoke=lambda *args:OcrInvocation('COMPLETED',True,dict(text=text,status='OCR_TEXT_EXTRACTED',engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    execute(scene,invoke=invoke)
    assert len(materialize(scene)[1])==2


def test_VP24_OCR_ambiguity_remains_review(scene):
    text='CONCEPTO 73: Suministro de instrumentos\nMarca: Delta'
    invoke=lambda *args:OcrInvocation('COMPLETED',True,dict(text=text,status='OCR_TEXT_EXTRACTED',engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    execute(scene,invoke=invoke)
    details=materialize(scene)[1]
    assert details[0].review_required and details[0].applicability=='UNRESOLVED'
    assert materialize_scope_attributes_for_scope_detail(scene[0][0],scope_detail_id=details[0].id).persisted_count==0


def test_VP30_unsupported_no_provider(scene):
    scene[0][2].mime_type='application/octet-stream';scene[0][2].original_filename='metadata.bin'
    plan=plans(scene)[0]
    assert plan.status=='UNAVAILABLE' and execute(scene,plan).status=='SKIPPED' and not scene[3]


def test_VP31_explicit_engine_no_auto(scene):
    with pytest.raises(ValueError,match='INVALID_EXPLICIT'):
        execute_planned_ocr(scene[0][0],plans(scene)[0],engine='AUTO',engine_version='fixture-1')
    assert not scene[3]


def test_VP32_no_raster_unknown(corpus):
    db,tender,doc,page=corpus
    plan=plan_document_ocr_tasks(db,tender_id=tender.id,document_id=doc.id,requests={page.id:(TaskRequest(T.SCOPE),)})[0]
    assert plan.status=='UNKNOWN' and not plan.ocr_eligible


def test_VP34_completed_never_overwritten_by_failure(scene):
    first=execute(scene)
    second=execute(scene,invoke=lambda *args:pytest.fail('completed work must be reused'))
    assert second.status=='COMPLETED' and scene[0][0].get(PageOcrResult,first.result_id).text==TEXT


def test_VP37_original_changed_rejects_cache(scene):
    first=execute(scene)
    scene[0][2].sha256='b'*64
    second=execute(scene)
    assert second.status=='DEFERRED' and len(scene[3])==1


def test_receipt_corruption_never_reused(scene):
    first=execute(scene)
    scene[0][0].get(PageOcrResult,first.result_id).text='altered'
    second=execute(scene)
    assert second.status=='DEFERRED' and len(scene[3])==1


def test_generation_change_children_fail_closed(scene):
    result=execute(scene)
    details=materialize(scene)[1]
    row=scene[0][0].get(PageOcrResult,result.result_id)
    row.text='altered'
    assert materialize_scope_attributes_for_scope_detail(scene[0][0],scope_detail_id=details[0].id).status=='INVALID_EVIDENCE'
    assert materialize_scope_quantities_for_scope_detail(scene[0][0],scope_detail_id=details[0].id).status=='INVALID_EVIDENCE'


def test_metrics_distinguish_eligibility_execution_completion(scene):
    plan=plans(scene)[0]
    before=perception_metrics((plan,))
    assert before['ocr_eligible']==1 and before['ocr_executed']==0
    after=perception_metrics((plan,),(execute(scene,plan),))
    assert after['ocr_executed']==1 and after['ocr_completed']==1


def test_stale_or_unbound_plan_deferred(scene):
    plan=plans(scene)[0]
    plan=replace(plan,source_identity=None)
    assert execute(scene,plan).reason=='STALE_OR_UNBOUND_PERCEPTION_PLAN' and not scene[3]


def test_VP35_partial_page_region_only(scene):
    corpus,region,invoke,calls,_=scene
    norm(corpus[0],corpus[3],text='Native heading')
    p=plans(scene,request=TaskRequest(T.SCOPE,region_id=region.id))[0]
    result=execute(scene,p)
    assert result.status=='COMPLETED'
    row=corpus[0].get(PageOcrResult,result.result_id)
    assert row.region_id==region.id and row.scope=='IMAGE_REGION'
    assert corpus[3].text=='Native heading'


def test_mixed_page_needs_explicit_region(scene):
    corpus=scene[0]
    norm(corpus[0],corpus[3],text='Native heading')
    assert execute(scene).reason=='REGION_SELECTION_REQUIRED_FOR_MIXED_PAGE'
    assert not scene[3]


def test_OI05_VP24_unproven_conflict_not_merged(scene):
    execute(scene)
    corpus=scene[0]
    norm(corpus[0],corpus[3],text=TEXT.replace('Cantidad: 4','Cantidad: 9'))
    from app.document_intelligence_sources import load_document_transcriptions
    route=load_document_transcriptions(corpus[0],corpus[2])[corpus[3].id]
    assert route.status=='REVIEW_REQUIRED' and route.conflicts
    _,rows=materialize(scene)
    assert len(rows)==2 and all(row.review_required for row in rows)


def test_native_identity_review_is_not_ocr_gap(scene):
    corpus=scene[0]
    norm(corpus[0],corpus[3],text='CONCEPTO 73: Suministro de instrumentos')
    p=plans(scene)[0]
    assert p.status=='REVIEW_REQUIRED' and not p.ocr_eligible
    assert execute(scene,p).status=='SKIPPED' and not scene[3]


def test_legacy_completed_no_overwrite(scene):
    db=scene[0][0]
    row=PageOcrResult(document_page_id=scene[0][3].id,engine='TESSERACT',engine_version='legacy',
        language='spa+eng',scope='FULL_PAGE',text='legacy completed evidence',status='OCR_TEXT_EXTRACTED')
    db.add(row);db.flush()
    result=execute(scene)
    assert result.status=='DEFERRED' and not scene[3]
    assert row.text=='legacy completed evidence'


def test_unknown_version_does_not_execute(scene):
    with pytest.raises(ValueError,match='INVALID_EXPLICIT'):
        execute(scene,engine_version='unknown')
    assert not scene[3]


def test_bounded_worker_timeout_kills_only_owned_group(monkeypatch):
    import subprocess
    import app.selective_ocr_executor as executor
    killed=[]
    class Process:
        pid=123456
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def communicate(self, payload=None, timeout=None):
            if timeout is not None:raise subprocess.TimeoutExpired('synthetic worker',timeout)
            return b'',b''
    monkeypatch.setattr(executor.subprocess,'Popen',lambda *args,**kwargs:Process())
    monkeypatch.setattr(executor.os,'killpg',lambda pid,sig:killed.append((pid,sig)))
    result=executor.bounded_local_ocr('TESSERACT',b'fixture','spa+eng',.01)
    assert result.status=='FAILED' and result.invoked is None
    assert killed==[(123456,executor.signal.SIGKILL)]


def test_normalization_preserves_native_chunk_identity(scene):
    from app.content_normalization import process_document_normalization
    from app.models import DocumentChunk
    corpus=scene[0]
    native=norm(corpus[0],corpus[3],text='Native heading')
    process_document_normalization(corpus[0],corpus[2])
    corpus[0].flush()
    before=corpus[0].scalars(select(DocumentChunk.id).where(DocumentChunk.normalized_content_id==native.id)).all()
    plan=plans(scene,request=TaskRequest(T.SCOPE,region_id=scene[1].id))[0]
    execute(scene,plan)
    after=corpus[0].scalars(select(DocumentChunk.id).where(DocumentChunk.normalized_content_id==native.id)).all()
    assert before and before==after


def test_OCR_provenance_reaches_requirements_and_requested_evidence(scene):
    from test_document_intelligence_integration import requirements, requested
    text='El licitante debera presentar certificado de calidad para el suministro de equipos.'
    invoke=lambda *args:OcrInvocation('COMPLETED',True,dict(text=text,status='OCR_TEXT_EXTRACTED',engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    result=execute(scene,invoke=invoke)
    candidates=requirements(scene[0])
    assert candidates and any(result.result_id in json.dumps(e.perception_provenance) for c in candidates for e in c.evidence)
    response=requested(scene[0])
    assert response['requirements'] and 'OCR' in json.dumps(response,default=str)


def test_provider_null_text_invalid_and_not_persisted_as_transcript(scene):
    invoke=lambda *args:OcrInvocation('COMPLETED',True,dict(text='invalid\x00text',status='OCR_TEXT_EXTRACTED',engine='TESSERACT',engine_version='fixture-1',language='spa+eng'))
    result=execute(scene,invoke=invoke)
    assert result.status=='INVALID_OUTPUT'
    assert scene[0][0].get(PageOcrResult,result.result_id).text==''
