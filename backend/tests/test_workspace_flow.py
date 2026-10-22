"""Normal API contracts over generic PDFs; no blind fixtures."""
import fcntl
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.main import app
from app.models import TenderScopeDetail, TenderScopeQuantity
from app.workspace_flow import _paths, quantity_read
from tests.test_native_table_bridge import pdf_table

@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr('app.main.get_licitia_data_root', lambda: tmp_path)
    def denied(*args, **kwargs):
        raise AssertionError('Workspace cannot acquire perception')
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize', denied)
    monkeypatch.setattr('app.ocr.PaddleOCRProvider.recognize', denied)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient', denied)
    with engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr('app.document_structure_orchestrator.SessionLocal', lambda: Session(bind=connection, autoflush=False, join_transaction_mode='create_savepoint'))
        with Session(bind=connection, autoflush=False, join_transaction_mode='create_savepoint') as db:
            app.dependency_overrides[get_db] = lambda: db
            try:
                with TestClient(app) as client:
                    response = client.post('/tenders', json={'title': 'Workspace synthetic contract'})
                    assert response.status_code == 201
                    yield client, response.json()['id'], db
            finally:
                app.dependency_overrides.pop(get_db, None)
        transaction.rollback()

def upload(client, tender, data=None, filename='generic.pdf', mime='application/pdf'):
    response = client.post(f'/tenders/{tender}/documents/import', files=[('files', (filename, pdf_table() if data is None else data, mime))])
    assert response.status_code == 200, response.text
    return response.json()[0]['document_id']

def process(client, tender):
    response = client.post(f'/tenders/{tender}/workspace/process')
    assert response.status_code == 200, response.text
    return response.json()

def test_normal_pdf_workflow_parent_ownership_and_provenance(scene):
    client, tender, db = scene
    document = upload(client, tender)
    result = process(client, tender)
    assert result['processing']['status'] == 'COMPLETED_REVIEW_REQUIRED'
    assert len(result['scopes']) == 2
    for scope in result['scopes']:
        assert len(scope['quantities']) == 1
        q = scope['quantities'][0]
        assert q['scope_detail_id'] == scope['scope_detail_id'] and q['tender_id'] == tender
        assert q['quantity_raw'] == {'31': '3', '32': '7'}[scope['candidate_item_key']]
        assert q['status'] == 'REVIEW_REQUIRED'
        assert scope['review']['current']['effective_status'] == 'PENDING'
        for source in [scope['source'], q['source']]:
            assert source['document_id'] == document and source['filename'] == 'generic.pdf'
            assert source['page'] == 1 and source['revision'] == 1
            assert source['available'] and source['excerpt'] and source['locator']
    assert client.get(f'/tenders/{tender}/workspace').json()['scopes'] == result['scopes']
    repeat = process(client, tender)
    assert [s['scope_detail_id'] for s in repeat['scopes']] == [s['scope_detail_id'] for s in result['scopes']]
    assert [[(q['scope_detail_id'], q['quantity_raw'], q['unit_raw'], q['source']) for q in s['quantities']] for s in repeat['scopes']] == [[(q['scope_detail_id'], q['quantity_raw'], q['unit_raw'], q['source']) for q in s['quantities']] for s in result['scopes']]
    assert repeat['processing']['run_id'] != result['processing']['run_id']

def test_two_parents_cannot_exchange_quantity_children(scene):
    client, tender, db = scene
    upload(client, tender); process(client, tender)
    parents = db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender).order_by(TenderScopeDetail.candidate_item_key)).all()
    q = db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == parents[0].id)).one()
    assert quantity_read(db, q, parents[1]).status == 'UNRESOLVED'
    q.scope_detail_id = parents[1].id; db.flush()
    assert quantity_read(db, q, parents[1]).status == 'UNRESOLVED'
    result = client.get(f'/tenders/{tender}/workspace').json()
    assert result['scopes'][0]['quantities'] == []
    assert any(q['status'] == 'UNRESOLVED' for q in result['scopes'][1]['quantities'])

def test_empty_unknown_stale_and_unsupported(scene):
    client, tender, db = scene
    result = client.get(f'/tenders/{tender}/workspace')
    assert result.status_code == 200
    assert result.json()['processing']['status'] == 'NOT_PROCESSED'
    assert not result.json()['scopes'] and not result.json()['requirements']['requirements']
    assert client.post(f'/tenders/{tender}/workspace/process').status_code == 409
    assert client.get(f'/tenders/{uuid4()}/workspace').status_code == 404
    assert client.post(f'/tenders/{uuid4()}/workspace/process').status_code == 404
    upload(client, tender); process(client, tender)
    upload(client, tender, b'not supported', 'readme.txt', 'text/plain')
    assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status'] == 'STALE'
    assert process(client, tender)['processing']['status'] == 'PARTIAL'

def test_processing_lock_and_interruption(scene):
    import json
    client, tender, db = scene
    upload(client, tender); process(client, tender)
    path, lock_path = _paths(tender)
    with lock_path.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status'] == 'PROCESSING'
        assert client.post(f'/tenders/{tender}/workspace/process').status_code == 409
    data = json.loads(path.read_text()); data['status'] = 'PROCESSING'; path.write_text(json.dumps(data))
    assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status'] == 'INTERRUPTED'

def test_failed_preparation_is_explicit(scene):
    client, tender, db = scene
    upload(client, tender, b'broken pdf')
    response = client.post(f'/tenders/{tender}/workspace/process')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'PROCESSING_FAILED'
    assert client.get(f'/tenders/{tender}/workspace').json()['processing']['status'] == 'FAILED'

def test_requirements_and_requested_evidence_canonical_composition(scene):
    import pymupdf
    from app.requirement_matrix import get_tender_requirement_matrix
    from app.requirement_semantics import get_tender_requirement_semantics
    client, tender, db = scene
    pdf = pymupdf.open(); page = pdf.new_page()
    page.insert_text((40, 60), 'El licitante debera presentar una carta de garantia firmada.', fontsize=11)
    upload(client, tender, pdf.tobytes()); pdf.close()
    result = process(client, tender)
    canonical = get_tender_requirement_matrix(db, tender)
    semantics = get_tender_requirement_semantics(db, tender)
    assert result['requirements']['requirements']
    assert [r['requirement_id'] for r in result['requirements']['requirements']] == [r['requirement_id'] for r in canonical['requirements']]
    assert result['semantics']['summary']['evidence_expectation_count'] > 0
    assert result['semantics']['summary'] == semantics['summary']
    r = result['requirements']['requirements'][0]
    assert r['primary_source']['source_excerpt'] and r['review_status']
    evidence = result['semantics']['requirements'][0]['expected_evidence'][0]
    assert evidence['source_page'] == 1 and evidence['source_document_id'] and evidence['source_excerpt']


def test_scope_review_correction_does_not_accept_quantities_and_survives_reprocessing(scene):
    client, tender, db = scene
    upload(client, tender)
    result = process(client, tender)
    scope = result['scopes'][0]
    review = scope['review']
    response = client.post(f"/tenders/{tender}/scope-review/{scope['scope_detail_id']}/decisions", json={
        'decision': 'CORRECTED', 'correction': {'description': 'Descripción corregida por una persona'},
        'expected_projection_fingerprint': review['projection_fingerprint'],
        'expected_current_review_revision': review['current_review_revision'], 'note': 'Prueba sintética'})
    assert response.status_code == 200, response.text
    result = client.get(f'/tenders/{tender}/workspace').json()
    assert result['scopes'][0]['description'] == 'Descripción corregida por una persona'
    assert result['scopes'][0]['review']['current']['effective_status'] == 'CORRECTED'
    assert result['scopes'][0]['quantities'][0]['status'] == 'REVIEW_REQUIRED'
    result = process(client, tender)
    assert result['scopes'][0]['description'] == 'Descripción corregida por una persona'
    assert result['scopes'][0]['review']['history']
    assert result['scopes'][0]['quantities'][0]['status'] == 'REVIEW_REQUIRED'


def test_missing_original_is_visible_without_losing_other_scope_results(scene):
    from app.main import _resolve_document_file_path
    from app.models import TenderDocument
    client, tender, db = scene
    document_id = upload(client, tender); process(client, tender)
    document = db.get(TenderDocument, document_id)
    _resolve_document_file_path(document.stored_relative_path).unlink()
    result = client.get(f'/tenders/{tender}/workspace')
    assert result.status_code == 200
    assert len(result.json()['scopes']) == 2
    for scope in result.json()['scopes']:
        assert not scope['source']['available']
        assert scope['quantities'][0]['status'] == 'UNRESOLVED'
    assert client.post(f'/tenders/{tender}/workspace/process').status_code == 422


def test_missing_manifest_is_fail_closed(scene):
    from app.structured_evidence_storage import digest_from_locator, manifest_path
    client, tender, db = scene
    upload(client, tender); result = process(client, tender)
    manifest_path(digest_from_locator(result['scopes'][0]['source']['locator'])).unlink()
    result = client.get(f'/tenders/{tender}/workspace')
    assert result.status_code == 200
    assert result.json()['scopes'][0]['review'] is None
    assert result.json()['scopes'][0]['quantities'][0]['status'] == 'UNRESOLVED'


def test_status_symlink_cannot_escape_root(scene, tmp_path):
    client, tender, db = scene
    upload(client, tender)
    path, lock = _paths(tender)
    path.parent.mkdir(parents=True)
    target = tmp_path / 'unrelated.json'; target.write_text('preserve')
    path.symlink_to(target)
    assert client.post(f'/tenders/{tender}/workspace/process').status_code == 409
    assert target.read_text() == 'preserve'
