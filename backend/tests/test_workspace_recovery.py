"""RH308-RH310 retry uses generic source identity and existing materializers."""
import json
import pytest
from sqlalchemy import select
from app.models import TenderDocument, TenderScopeQuantity, DocumentPage
from app.workspace_flow import _paths
from tests.test_workspace_flow import scene, upload, process


def status(client,tender):
    result=client.get(f'/tenders/{tender}/workspace/recovery')
    assert result.status_code==200,result.text
    return result.json()


def retry(client,tender,identity=None):
    identity=identity or status(client,tender)['fingerprint']
    return client.post(f'/tenders/{tender}/workspace/retry',json={'expected_fingerprint':identity})


def quantities(result):
    return [(s['scope_detail_id'],[(q['quantity_raw'],q['unit_raw'],q['scope_detail_id'],q['source']) for q in s['quantities']]) for s in result['scopes']]


def test_RH308_completed_same_document_retry_idempotent(scene,tmp_path):
    import pymupdf
    from tests.test_native_table_bridge import pdf_table
    client,tender,db=scene
    pdf=pymupdf.open(stream=pdf_table(),filetype='pdf'); page=pdf.new_page()
    page.insert_text((40,60),'El licitante debera presentar una carta de garantia firmada.',fontsize=11)
    upload(client,tender,pdf.tobytes()); pdf.close()
    before=process(client,tender)
    assert before['requirements']['summary']['total_requirements']>0
    assert before['semantics']['summary']['evidence_expectation_count']>0
    scope=before['scopes'][0]; view=scope['review']
    response=client.post(f"/tenders/{tender}/scope-review/{scope['scope_detail_id']}/decisions",json={
        'decision':'CORRECTED','correction':{'description':'Descripción humana preservada'},
        'expected_projection_fingerprint':view['projection_fingerprint'],
        'expected_current_review_revision':view['current_review_revision']})
    assert response.status_code==200,response.text
    before=client.get(f'/tenders/{tender}/workspace').json()
    manifests=set((tmp_path/'provenance/structured-evidence-v1').glob('*.json'))
    initial=status(client,tender)
    assert initial['eligible'] and initial['provider_acquisition'] is False
    for _ in range(2):
        response=retry(client,tender); assert response.status_code==200,response.text
        result=response.json()
        assert quantities(result)==quantities(before)
        assert len(db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==tender)).all())==2
        assert result['requirements']['summary']==before['requirements']['summary']
        assert result['semantics']['summary']==before['semantics']['summary']
        assert len(result['scopes'][0]['review']['history'])==1
        assert result['scopes'][0]['description']=='Descripción humana preservada'
        assert set((tmp_path/'provenance/structured-evidence-v1').glob('*.json'))==manifests


def test_RH310_interruption_then_retry_preserves_generation(scene):
    client,tender,db=scene
    upload(client,tender); before=process(client,tender)
    path,_=_paths(tender); data=json.loads(path.read_bytes()); data['status']='PROCESSING'; path.write_text(json.dumps(data))
    assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status']=='INTERRUPTED'
    assert status(client,tender)['eligible']
    response=retry(client,tender); assert response.status_code==200,response.text
    assert quantities(response.json())==quantities(before)
    assert response.json()['processing']['status']=='COMPLETED_REVIEW_REQUIRED'


def test_RH309_provider_failure_preserves_native_and_retry_does_not_duplicate(scene,monkeypatch):
    client,tender,db=scene
    upload(client,tender); before=process(client,tender)
    from app.canonical_materialization import materialize_canonical
    def fail(*args):
        materialize_canonical(*args)
        raise ConnectionError('simulated optional provider interruption')
    monkeypatch.setattr('app.canonical_materialization.materialize_canonical',fail)
    assert retry(client,tender).status_code==422
    failed=client.get(f'/tenders/{tender}/workspace').json()
    assert failed['processing']['status']=='FAILED'
    assert quantities(failed)==quantities(before)
    monkeypatch.setattr('app.canonical_materialization.materialize_canonical',materialize_canonical)
    for _ in range(2):
        response=retry(client,tender); assert response.status_code==200,response.text
        assert quantities(response.json())==quantities(before)


def test_failed_native_with_no_pages_can_retry_without_original_mutation(scene,monkeypatch):
    client,tender,db=scene
    document=upload(client,tender)
    from app import main
    real=main._extract_pdf_pages
    def unavailable(*a): raise RuntimeError('transient parser failure')
    monkeypatch.setattr(main,'_extract_pdf_pages',unavailable)
    assert client.post(f'/tenders/{tender}/workspace/process').status_code==422
    db.expire_all()
    assert db.get(TenderDocument,document).processing_status=='TEXT_EXTRACTION_FAILED'
    assert not db.scalars(select(DocumentPage).where(DocumentPage.document_id==document)).all()
    assert status(client,tender)['eligible']
    monkeypatch.setattr(main,'_extract_pdf_pages',real)
    response=retry(client,tender); assert response.status_code==200,response.text
    assert len(response.json()['scopes'])==2


def test_retry_refuses_changed_missing_source_and_stale_request(scene):
    from app.main import _resolve_document_file_path
    client,tender,db=scene
    document=upload(client,tender); process(client,tender)
    identity=status(client,tender)['fingerprint']
    assert retry(client,tender,'0'*64).status_code==409
    path=_resolve_document_file_path(db.get(TenderDocument,document).stored_relative_path)
    original=path.read_bytes(); path.write_bytes(b'changed')
    assert not status(client,tender)['eligible']
    assert retry(client,tender,identity).status_code==409
    assert path.read_bytes()==b'changed'  # Retry never rewrites/reverts originals.
    path.write_bytes(original); path.unlink()
    assert 'SOURCE_UNAVAILABLE' in status(client,tender)['reasons']
    assert retry(client,tender,identity).status_code==409


def test_retry_does_not_clear_receipt_exhaustion(scene,tmp_path):
    client,tender,db=scene
    upload(client,tender); process(client,tender)
    directory=tmp_path/'vision-task-receipts-v1'; directory.mkdir()
    receipt=directory/'synthetic.json'; receipt.write_text('{"attempts":2,"status":"RETRY_EXHAUSTED"}')
    before=receipt.read_bytes(); identity=status(client,tender)['fingerprint']
    receipt.write_text('{"attempts":2,"status":"FAILED"}')
    assert retry(client,tender,identity).status_code==409
    after=receipt.read_bytes()
    assert retry(client,tender).status_code==200
    assert receipt.read_bytes()==after


def test_empty_and_invalid_provenance_do_not_offer_retry(scene):
    from app.structured_evidence_storage import digest_from_locator,manifest_path
    client,tender,db=scene
    assert not status(client,tender)['eligible']
    upload(client,tender); result=process(client,tender)
    manifest_path(digest_from_locator(result['scopes'][0]['source']['locator'])).unlink()
    assert 'PROVENANCE_REVIEW_REQUIRED' in status(client,tender)['reasons']
    assert retry(client,tender).status_code==409


def test_provider_unavailable_record_does_not_invalidate_native(scene):
    from app.models import DocumentVisionAnalysis,DocumentVisionPageResult
    client,tender,db=scene
    document=upload(client,tender); before=process(client,tender)
    page=db.scalars(select(DocumentPage).where(DocumentPage.document_id==document)).one()
    analysis=DocumentVisionAnalysis(tender_id=tender,document_id=document,prompt_version='synthetic-control',input_fingerprint_sha256='a'*64,status='FAILED')
    db.add(analysis); db.flush()
    db.add(DocumentVisionPageResult(analysis_id=analysis.id,document_page_id=page.id,page_number=page.page_number,image_sha256='b'*64,status='UNAVAILABLE'))
    db.commit()
    view=client.get(f'/tenders/{tender}/workspace').json()
    assert view['processing']['provider_degraded']
    assert quantities(view)==quantities(before)
    assert status(client,tender)['provider_degraded'] and status(client,tender)['eligible']
    response=retry(client,tender); assert response.status_code==200,response.text
    assert quantities(response.json())==quantities(before)
    assert response.json()['processing']['status']=='COMPLETED_REVIEW_REQUIRED'


def test_processing_identity_change_marks_stale_without_silent_child_reassociation(scene,monkeypatch):
    client,tender,db=scene
    upload(client,tender); before=process(client,tender)
    old=status(client,tender)['fingerprint']
    monkeypatch.setattr('app.workspace_recovery.processing_identity',lambda:'changed-processing-identity')
    assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status']=='STALE'
    assert retry(client,tender,old).status_code==409
    response=retry(client,tender); assert response.status_code==200,response.text
    assert quantities(response.json())==quantities(before)
    assert response.json()['processing']['processing_identity']=='changed-processing-identity'


def test_retry_waits_for_active_provider_task_lock(scene,tmp_path):
    import fcntl
    client,tender,db=scene
    upload(client,tender); process(client,tender)
    directory=tmp_path/'ocr-task-receipts-v1'; directory.mkdir()
    with (directory/'synthetic.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        view=status(client,tender)
        assert not view['eligible'] and 'RECEIPT_TASK_ACTIVE' in view['reasons']
        assert retry(client,tender).status_code==409
    assert status(client,tender)['eligible']


def test_native_failure_with_existing_pages_requires_review_not_reset(scene):
    client,tender,db=scene
    document=upload(client,tender); before=process(client,tender)
    record=db.get(TenderDocument,document); record.processing_status='TEXT_EXTRACTION_FAILED'; db.commit()
    view=status(client,tender)
    assert not view['eligible'] and 'INCONSISTENT_NATIVE_STATE' in view['reasons']
    assert retry(client,tender).status_code==409
    assert db.get(TenderDocument,document).processing_status=='TEXT_EXTRACTION_FAILED'
    assert quantities(client.get(f'/tenders/{tender}/workspace').json())==quantities(before)
