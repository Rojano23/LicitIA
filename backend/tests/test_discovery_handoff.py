"""M10-C canonical ingestion E2E with synthetic allowlisted HTTP; no analysis."""
from hashlib import sha256
from uuid import uuid4
import httpx,pytest
from sqlalchemy import select,func,delete
from tests.test_discovery import offline,raw,adapter,request
from tests.test_discovery_cfe import adapter as cfe_adapter,row as cfe_row,request as cfe_request
from app.discovery import run_scan,list_opportunities
from app.discovery_contract import PublicDocument
from app.discovery_models import DiscoveryOpportunity as Opp,DiscoveryChange as Change,DiscoveryImportReceipt as Receipt,DiscoveryTenderLink as Link
from app.discovery_pemex import PEMEXConcursosAdapter
from app.discovery_cfe import CFEProcurementAdapter
from app.discovery_downloads import download
from app.models import Tender,TenderDocument,DocumentPage
PDF=b'%PDF-1.4\nSynthetic public document\n%%EOF'

@pytest.fixture
def imports(offline,monkeypatch,tmp_path):
    c,db=offline
    db.info['baseline']={m:db.scalar(select(func.count()).select_from(m)) for m in [Tender,TenderDocument,DocumentPage]}
    monkeypatch.setattr('app.main.get_licitia_data_root',lambda:tmp_path/'data')
    calls=[];state={'content':PDF,'fail':set()}
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(503 if any(t in str(req.url) for t in state['fail']) else 200,content=state['content'],headers={'content-type':'application/pdf'})
    def factory(source):return (PEMEXConcursosAdapter if source=='PEMEX' else CFEProcurementAdapter)(httpx.MockTransport(handler),pacing=0)
    monkeypatch.setattr('app.discovery_handoff.adapter_for',factory)
    def forbidden(*a,**k):raise AssertionError('NO_AUTO_ANALYSIS')
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize',forbidden)
    monkeypatch.setattr('app.ocr.PaddleOCRProvider.recognize',forbidden)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient',forbidden)
    monkeypatch.setattr('app.document_structure_orchestrator.orchestrate_document_structure_available_only',forbidden)
    monkeypatch.setattr('app.workspace_flow.process_workspace',forbidden)
    yield c,db,tmp_path/'data',calls,state

def count(db,model):return db.scalar(select(func.count()).select_from(model))-db.info['baseline'].get(model,0)
def first_document(db):return db.scalar(select(TenderDocument).where(TenderDocument.tender_id.in_(select(Link.tender_id))))

def seed(db,source='PEMEX',rows=None):
    a,_=adapter({'support':[rows or [raw(1)]]}) if source=='PEMEX' else cfe_adapter(rows or [cfe_row()])
    try:out=run_scan(db,source,request() if source=='PEMEX' else cfe_request(),a);assert out['status']=='SUCCESS',out
    finally:a.close()
    return list_opportunities(db,source=source)['items'][0]
def preview(c,oid):
    r=c.get('/discovery/opportunities/'+oid+'/tender-preview');assert r.status_code==200,r.text
    return r.json()
def payload(p,docs=None,**kw):return {'confirm':True,'expected_binding':p['binding'],'documents':docs or [],**kw}
def choice(p,**kw):return {'document_id':p['documents'][0]['id'],**kw}
def create(c,p,docs=None,**kw):return c.post('/discovery/opportunities/'+p['opportunity_id']+'/create-tender',json=payload(p,docs,**kw))
def sync(c,p,docs,tid=None):return c.post('/discovery/opportunities/'+p['opportunity_id']+'/tenders/'+(tid or p['linked_tender']['id'])+'/documents',json=payload(p,docs))

@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_explicit_handoff_hash_provenance_idempotency_no_analysis(imports,source):
    c,db,root,calls,state=imports;row=seed(db,source);p=preview(c,row['id'])
    assert count(db,Tender)==0 and not calls
    assert p['selection_default']=='NONE' and not p['analysis_automatic']
    assert p['context']['public_url']==row['public_url'] and p['source_id']==source
    assert create(c,p,confirm=False).status_code==422
    r=create(c,p,[choice(p)]);assert r.status_code==200,r.text
    body=r.json();assert body['documents_status']=='COMPLETE_SELECTION' and body['documents'][0]['status']=='IMPORTED',body
    tid=body['tender_id'];t=db.get(Tender,tid);assert t.status=='DRAFT' and t.title==row['title']
    doc=db.scalar(select(TenderDocument).where(TenderDocument.tender_id==tid));assert doc.sha256==sha256(PDF).hexdigest()
    assert (root/doc.stored_relative_path).read_bytes()==PDF and doc.processing_status=='PENDING' and doc.page_count==0
    assert not body['analysis_started'] and len(calls)==1 and not count(db,DocumentPage)
    receipt=db.scalar(select(Receipt));assert receipt.sha256==doc.sha256 and receipt.source_url==p['documents'][0]['public_url']
    assert receipt.source_document_id==p['documents'][0]['id'] and receipt.opportunity_id==row['id'] and receipt.downloaded_at
    imported=c.get('/discovery/opportunities/'+row['id']).json();assert imported['internal_state']=='IMPORTED' and imported['linked_tender']['id']==tid
    again=create(c,p,[choice(p)]).json();assert again['already_created'] and again['tender_id']==tid and len(calls)==1
    now=preview(c,row['id']);assert sync(c,now,[choice(now)]).json()['documents'][0]['status']=='REUSED' and len(calls)==1
    assert sync(c,now,[choice(now,refresh=True)]).json()['documents'][0]['status']=='DUPLICATE' and len(calls)==2
    assert count(db,TenderDocument)==1 and db.scalar(select(func.count()).select_from(Receipt))==1


def test_default_no_download_stale_binding_title_and_imported_authority(imports):
    c,db,root,calls,state=imports;row=seed(db);p=preview(c,row['id'])
    assert create(c,{**p,'binding':'0'*64}).status_code==409 and not count(db,Tender)
    r=create(c,p,title='  Decisión humana  ');assert r.status_code==200
    assert db.get(Tender,r.json()['tender_id']).title=='Decisión humana' and not calls
    assert not count(db,TenderDocument)
    assert c.patch('/discovery/opportunities/'+row['id']+'/state',json={'internal_state':'NEW','expected_revision':2}).status_code==409


def test_source_changes_explicit_revision_preserves_original(imports):
    c,db,root,calls,state=imports;row=seed(db);p=preview(c,row['id']);tid=create(c,p,[choice(p)]).json()['tender_id']
    original=first_document(db);path=original.stored_relative_path
    updated=raw(1,descripcion='Nueva descripción');updated['AttachmentFiles']['results'].append({'FileName':'Adenda.pdf','ServerRelativeUrl':updated['AttachmentFiles']['results'][0]['ServerRelativeUrl'].replace('Bases.pdf','Adenda.pdf')})
    seed(db,rows=[updated]);after=c.get('/discovery/opportunities/'+row['id']).json()
    assert after['source_changes_available'] and after['internal_state']=='IMPORTED'
    assert count(db,TenderDocument)==1 and len(calls)==1
    assert db.get(Tender,tid).title==row['title'] and (root/path).read_bytes()==PDF
    p=preview(c,row['id']);base=next(d for d in p['documents'] if d['name']=='Bases.pdf');added=next(d for d in p['documents'] if d['name']=='Adenda.pdf')
    state['content']=PDF+b'\nupdated';out=sync(c,p,[{'document_id':base['id'],'refresh':True}]).json()
    assert out['documents'][0]['status']=='NAME_CONFLICT' and out['documents_status']=='PARTIAL'
    out=sync(c,p,[{'document_id':base['id'],'refresh':True,'conflict_action':'NEW_REVISION','revision_of_document_id':original.id}]).json()
    assert out['documents'][0]['status']=='IMPORTED',out
    db.refresh(original);assert not original.is_current and (root/path).read_bytes()==PDF
    revised=db.get(TenderDocument,out['documents'][0]['document_id']);assert revised.revision_of_document_id==original.id and revised.revision_number==2
    assert (root/revised.stored_relative_path).read_bytes()==state['content'] and revised.processing_status=='PENDING'
    state['content']=PDF+b'\nadenda';assert sync(c,p,[{'document_id':added['id']}]).json()['documents'][0]['status']=='IMPORTED'
    updated['AttachmentFiles']['results'][0]['FileName']='Bases 2027.pdf';seed(db,rows=[updated])
    assert count(db,TenderDocument)==3
    assert db.scalar(select(Change.id).where(Change.category=='DOCUMENT_CHANGED'))


def test_partial_download_tender_and_retry_successful_subset(imports):
    c,db,root,calls,state=imports;r=raw(1);r['AttachmentFiles']['results'].append({'FileName':'Fallida.pdf','ServerRelativeUrl':r['AttachmentFiles']['results'][0]['ServerRelativeUrl'].replace('Bases.pdf','Fallida.pdf')})
    row=seed(db,rows=[r]);p=preview(c,row['id']);state['fail']={'Fallida.pdf'}
    response=create(c,p,[{'document_id':d['id']} for d in p['documents']]);assert response.status_code==200,response.text
    body=response.json();assert body['documents_status']=='PARTIAL' and {d['status'] for d in body['documents']}=={'IMPORTED','FAILED'},body
    assert c.get('/discovery/opportunities/'+row['id']).json()['internal_state']=='IMPORTED'
    assert count(db,TenderDocument)==1
    state['fail']=set();p=preview(c,row['id']);body=sync(c,p,[{'document_id':d['id']} for d in p['documents']]).json()
    assert {d['status'] for d in body['documents']}=={'REUSED','DUPLICATE'}


def test_cross_tender_document_selection_revision_and_deleted_link(imports):
    c,db,root,calls,state=imports;first=seed(db);p=preview(c,first['id']);tid=create(c,p,[choice(p)]).json()['tender_id'];original=first_document(db)
    other=c.post('/tenders',json={'title':'Manual Compras MX'}).json()['id'];p=preview(c,first['id'])
    assert sync(c,p,[choice(p)],tid=other).status_code==409 and len(calls)==1
    second=seed(db,rows=[raw(2)]);p2=preview(c,second['id'])
    assert create(c,p2,[choice(p)]).status_code==404
    assert create(c,p2,[choice(p2,conflict_action='NEW_REVISION',revision_of_document_id=original.id)]).status_code==409
    db.execute(delete(TenderDocument).where(TenderDocument.tender_id==tid));db.execute(delete(Tender).where(Tender.id==tid));db.commit();db.expire_all()
    gone=preview(c,first['id']);assert gone['linked_tender']=={'id':tid,'available':False}
    assert create(c,gone).status_code==409 and db.get(Opp,first['id']).internal_state=='IMPORTED'
    assert db.scalar(select(func.count()).select_from(Receipt))==1


def test_discarded_and_restricted_guard_no_network_manual_tender_works(imports):
    c,db,root,calls,state=imports;row=seed(db);url='/discovery/opportunities/'+row['id']
    c.patch(url+'/state',json={'internal_state':'DISCARDED','expected_revision':1});p=preview(c,row['id']);assert create(c,p).status_code==409
    db.get(Opp,row['id']).source_id='COMPRAS_MX';db.commit()
    assert c.get(url+'/tender-preview').status_code==409 and create(c,p).status_code==409 and not calls
    assert c.post('/discovery/sources/COMPRAS_MX/scans',json={'request_id':str(uuid4()),'query':{'areas':['public']}}).status_code==409
    assert c.post('/tenders',json={'title':'Compras MX manual permitido'}).status_code==201

@pytest.mark.parametrize('name',['../x.pdf','a\\x.pdf','a/b.pdf','.','a:stream.pdf','x\x00.pdf',' x.pdf','CON.pdf','nul.txt','name.pdf.'])
def test_unsafe_source_filename_before_network(name):
    calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        with pytest.raises(ValueError):download(client,PublicDocument(external_id='doc',name=name,public_url='https://www.pemex.com/procura/x'),lambda u:u)
    assert not calls

@pytest.mark.parametrize('case',['host','redirect','mime','html','signature','oversize','empty','timeout'])
def test_download_failure_closed(case,monkeypatch):
    import app.discovery_downloads as module
    calls=[]
    def response(req):
        calls.append(str(req.url))
        if case=='timeout':raise httpx.ReadTimeout('synthetic')
        return httpx.Response(302 if case=='redirect' else 200,content=b'' if case=='empty' else b'<html>bad' if case in {'html','signature'} else PDF,
          headers={'content-type':'text/html' if case=='mime' else 'application/octet-stream' if case=='html' else 'application/pdf','location':'http://127.0.0.1/'})
    if case=='oversize':monkeypatch.setattr(module,'MAX_BYTES',4)
    url='http://127.0.0.1/private' if case=='host' else 'https://www.pemex.com/procura/procedimientos-de-contratacion/concursosabiertos/Lists/Concursoseinvitaciones/Attachments/1/Bases.pdf'
    a=PEMEXConcursosAdapter(httpx.MockTransport(response),pacing=0)
    try:
        with pytest.raises((ValueError,httpx.HTTPError)):a.download(PublicDocument(external_id='doc',name='Bases.pdf',public_url=url))
    finally:a.close()
    assert len(calls)==(0 if case=='host' else 1)


def test_only_selected_documents_downloaded_and_handoff_lock(imports):
    from sqlalchemy import text
    c,db,root,calls,state=imports;r=raw(1);r['AttachmentFiles']['results'].append({'FileName':'NoSeleccionado.pdf','ServerRelativeUrl':r['AttachmentFiles']['results'][0]['ServerRelativeUrl'].replace('Bases.pdf','NoSeleccionado.pdf')})
    row=seed(db,rows=[r]);p=preview(c,row['id']);selected=next(d for d in p['documents'] if d['name']=='Bases.pdf')
    with db.get_bind().engine.connect() as connection:
        key='discovery-handoff:'+row['id'];connection.execute(text('SELECT pg_advisory_lock(hashtext(:k))'),{'k':key})
        try:assert create(c,p,[{'document_id':selected['id']}]).status_code==409 and not calls
        finally:connection.execute(text('SELECT pg_advisory_unlock(hashtext(:k))'),{'k':key})
    out=create(c,p,[{'document_id':selected['id']}]);assert out.status_code==200 and len(calls)==1
    assert 'NoSeleccionado' not in calls[0] and count(db,TenderDocument)==1


def test_long_source_title_requires_human_override_then_sync_remains_available(imports):
    c,db,root,calls,state=imports;row=seed(db,rows=[raw(1,descripcion='Título público '+('largo '*60))]);p=preview(c,row['id'])
    assert p['suggested_title'] is None and create(c,p).status_code==422 and not calls
    r=create(c,p,title='Título humano acotado');assert r.status_code==200
    after=preview(c,row['id']);assert after['suggested_title']=='Título humano acotado'
    assert sync(c,after,[choice(after)]).json()['documents'][0]['status']=='IMPORTED'
