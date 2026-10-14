"""DF01–DF20: synthetic capability handling, never blind corpus fixtures."""
from pathlib import Path
import hashlib
import itertools

import pymupdf
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, func
from app.database import SessionLocal
from app import models as m
from app import main
from app.document_intelligence_blind_run import prepare_tender_documents, sha256, freeze_first_pass
from test_document_intelligence_06v_preflight import report, snapshot
from app.document_intelligence_validation_metrics import snapshot_tender, collect_metrics

@pytest.fixture
def batch(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'get_licitia_data_root', lambda: tmp_path)
    calls=[]
    def forbidden(*a, **kw):
        calls.append(True)
        raise AssertionError('Provider execution forbidden')
    from app.ocr import TesseractOCRProvider, PaddleOCRProvider
    from app.ollama_vision import OllamaVisionAssistClient
    for cls, name in [(TesseractOCRProvider,'recognize'), (PaddleOCRProvider,'recognize'), (OllamaVisionAssistClient,'_execute_task')]:
        monkeypatch.setattr(cls,name,forbidden)
    db=SessionLocal(); tender=m.Tender(title='Synthetic capability batch')
    db.add(tender); db.flush(); docs=[]
    for name, mime in [('a.pdf','application/pdf'), ('b.txt','text/plain'), ('c.pdf','application/pdf')]:
        if mime=='application/pdf':
            pdf=pymupdf.open(); page=pdf.new_page(); page.insert_text((72,72),'Synthetic document '+name)
            content=pdf.tobytes(); pdf.close()
        else: content=b'Synthetic unsupported document'
        (tmp_path/name).write_bytes(content)
        doc=m.TenderDocument(tender_id=tender.id, original_filename=name, mime_type=mime,
            stored_relative_path=name, sha256=hashlib.sha256(content).hexdigest(), file_size_bytes=len(content))
        db.add(doc); docs.append(doc)
    db.commit(); tid=tender.id
    yield db, tender, docs, tmp_path, calls
    db.rollback(); db.execute(delete(m.Tender).where(m.Tender.id==tid)); db.commit(); db.close()

def run(batch, order=(0,1,2)):
    db,tender,docs,_,_=batch
    return prepare_tender_documents(db,tender_id=tender.id,document_ids=tuple(docs[i].id for i in order))

def rows(db, cls): return db.scalar(select(func.count()).select_from(cls))
def no_artifacts(batch):
    db,_,docs,_,_=batch; doc=docs[1]
    assert not db.scalars(select(m.DocumentPage).where(m.DocumentPage.document_id==doc.id)).all()
    assert not db.scalars(select(m.NormalizedContent).join(m.DocumentPage).where(m.DocumentPage.document_id==doc.id)).all()
    assert not db.scalars(select(m.DocumentVisionAnalysis).where(m.DocumentVisionAnalysis.document_id==doc.id)).all()
    assert doc.text_extracted_at is None and doc.processing_status=='PENDING'

def test_DF01_supported(batch):
    assert run(batch,(0,))[0].status=='PREPARED'
    # Canonical MIME eligibility is retained even without a PDF extension.
    batch[2][2].original_filename='neutral.bin'; batch[0].commit()
    assert run(batch,(2,))[0].status=='PREPARED'

def test_DF02_unsupported(batch):
    r=run(batch,(1,))[0]; assert (r.status,r.reason)==('UNAVAILABLE','UNSUPPORTED_NATIVE_CAPABILITY')
def test_DF03_no_pages(batch): run(batch,(1,)); no_artifacts(batch)
def test_DF04_no_perception(batch): run(batch,(1,)); no_artifacts(batch)
def test_DF05_mixed(batch): assert [r.status for r in run(batch)]==['PREPARED','UNAVAILABLE','PREPARED']
def test_DF06_unsupported_first(batch): assert [r.status for r in run(batch,(1,0,2))]==['UNAVAILABLE','PREPARED','PREPARED']
def test_DF07_unsupported_middle(batch): assert run(batch)[2].status=='PREPARED'
def test_DF08_order(batch):
    expected=None
    for order in itertools.permutations(range(3)):
        result={r.document_id:(r.status,r.page_count) for r in run(batch,order)}
        if expected is None: expected=result
        assert result==expected

def test_DF09_parser_failure(batch):
    db,_,docs,root,_=batch; payload=b'not a valid PDF'; (root/'a.pdf').write_bytes(payload)
    docs[0].sha256=hashlib.sha256(payload).hexdigest(); docs[0].file_size_bytes=len(payload); db.commit()
    with pytest.raises(HTTPException) as caught: run(batch,(0,1,2))
    assert caught.value.status_code==500 and docs[0].processing_status=='TEXT_EXTRACTION_FAILED'
    assert docs[2].processing_status=='PENDING'

def test_DF10_missing_original(batch):
    (batch[3]/'a.pdf').unlink()
    with pytest.raises(FileNotFoundError): run(batch)
    # Unsupported capability never masks a missing original either.
    (batch[3]/'b.txt').unlink()
    with pytest.raises(FileNotFoundError): run(batch,(1,))

def test_DF11_identity_integrity(batch):
    db,tender,docs,root,_=batch
    with pytest.raises(LookupError): prepare_tender_documents(db,tender_id='absent')
    with pytest.raises(LookupError): prepare_tender_documents(db,tender_id=tender.id,document_ids=('absent',))
    (root/'b.txt').write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'): run(batch,(1,))
    docs[0].stored_relative_path='../escape'; db.commit()
    with pytest.raises(HTTPException): run(batch,(0,))
    docs[2].page_count=3; db.commit()
    with pytest.raises(ValueError,match='consistent'): run(batch,(2,))

def metrics(batch):
    return collect_metrics(snapshot_tender(batch[0],batch[1].id,authorized_import=True))['first_pass']['domains']['DOCUMENTS']
def test_DF12_metrics_visible(batch): run(batch); assert metrics(batch)['unavailable']==1
def test_DF13_no_trust(batch):
    run(batch,(1,)); snap=snapshot_tender(batch[0],batch[1].id,authorized_import=True)
    record=next(r for r in snap.records if r.domain=='DOCUMENTS' and r.id==batch[2][1].id)
    assert record.state=='UNAVAILABLE' and not record.automatic

def test_DF14_no_fake_provenance(batch): run(batch); no_artifacts(batch)
def test_DF15_idempotence(batch):
    run(batch); db,_,docs,_,_=batch
    before=[(p.id,p.document_id,p.page_number) for p in db.scalars(select(m.DocumentPage).where(m.DocumentPage.document_id.in_([d.id for d in docs])))]
    norms=[n.id for n in db.scalars(select(m.NormalizedContent).join(m.DocumentPage).where(m.DocumentPage.document_id.in_([d.id for d in docs])))]
    r=run(batch)
    assert r[0].reused and r[2].reused and not r[1].reused
    assert before==[(p.id,p.document_id,p.page_number) for p in db.scalars(select(m.DocumentPage).where(m.DocumentPage.document_id.in_([d.id for d in docs])))]
    assert norms==[n.id for n in db.scalars(select(m.NormalizedContent).join(m.DocumentPage).where(m.DocumentPage.document_id.in_([d.id for d in docs])))]

def test_DF16_no_provider(batch): run(batch); assert batch[4]==[]
def test_DF17_no_tender_special_case():
    import inspect
    source=inspect.getsource(prepare_tender_documents)
    assert '421da160' not in source and '06v_6f6c60' not in source

def test_DF18_no_source_path():
    import inspect
    assert 'Reelevadores' not in inspect.getsource(prepare_tender_documents)

def test_DF19_no_count_dependency(batch):
    assert len(run(batch,(1,)))==1 and len(run(batch,(0,2)))==2
    assert len(prepare_tender_documents(batch[0],tender_id=batch[1].id))==3

def test_DF20_historical_artifact_not_overwritten(batch, report, tmp_path):
    # Synthetic historical first-pass identity; never requires the real blind run.
    marker=freeze_first_pass(report,tmp_path)
    path=tmp_path/report.run_id/'first_pass.json'
    before=path.read_bytes()
    run(batch)
    assert path.read_bytes()==before and sha256(before)==marker['first_pass_sha256']
    with pytest.raises(FileExistsError): freeze_first_pass(report,tmp_path)
    assert path.read_bytes()==before
