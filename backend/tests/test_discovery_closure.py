"""M10-D source-neutral closure; synthetic offline API/adapter contracts only."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json,os
import httpx,pytest
from sqlalchemy import select,func,event
from sqlalchemy.orm import Session
from tests.test_discovery import offline,raw,adapter,request
from tests.test_discovery_cfe import adapter as cfe_adapter,row as cfe_row,request as cfe_request
from tests.test_discovery_handoff import seed,preview,choice,create
from tests.test_native_table_bridge import pdf_table
from app.discovery import run_scan,list_opportunities
from app.discovery_contract import identity,SourceQuery,ScanRequest,Profile,match_profile
from app.discovery_models import DiscoveryOpportunity as Opp,DiscoverySourceDocument as Doc,DiscoveryChange as Change,DiscoveryTenderLink as Link,DiscoveryImportReceipt as Receipt
from app.discovery_pemex import PEMEXConcursosAdapter
from app.discovery_cfe import CFEProcurementAdapter
from app.models import Tender,TenderDocument,Base
from app.main import app
from app.proposal_readiness import get_proposal_db

def record(name,value):
    directory=Path(os.environ.get('LICITIA_DISCOVERY_REPORT_ROOT','reports/m10_d'));directory.mkdir(exist_ok=True,parents=True)
    (directory/name).write_text(json.dumps(value,indent=2,default=str)+'\n')

def test_cross_source_profile_identity_three_batches_and_late_matches(offline):
    c,db=offline;profile={'name':'M10-D compartido','include_keywords':['PLC'],'exclude_keywords':['cancelado'],'synonyms':{'PLC':['controlador lógico programable']}}
    saved=c.post('/discovery/profiles',json=profile).json();reports={}
    for source in ['PEMEX','CFE']:
        def description(i):return 'PLC cancelado' if i==216 else 'controlador lógico programable' if i==217 else 'Válvula'
        rows=[raw(i,Title=str(i),descripcion=description(i)) if source=='PEMEX' else cfe_row(i,Descripcion=description(i)) for i in range(1,218)]
        rows.insert(101,deepcopy(rows[0]));a,_=adapter({'support':[rows[i:i+100] for i in range(0,len(rows),100)]}) if source=='PEMEX' else cfe_adapter(rows)
        req=request() if source=='PEMEX' else cfe_request()
        try:
            out=run_scan(db,source,req,a);assert out['status']=='SUCCESS',out
            assert out['metrics']['pages_completed']==3 and out['metrics']['unique_opportunities']==217 and out['metrics']['duplicates']==1
            assert run_scan(db,source,req,a)['id']==out['id']
        finally:a.close()
        result=c.get('/discovery/opportunities',params={'source':source,'profile_id':saved['id'],'matched_only':True}).json()
        assert result['total']==1 and result['items'][0]['external_id']=='217'
        detail=c.get('/discovery/opportunities/'+identity(source,'217'),params={'profile_id':saved['id']}).json();assert detail['match']==result['items'][0]['match']
        excluded=c.get('/discovery/opportunities/'+identity(source,'216'),params={'profile_id':saved['id']}).json()['match'];assert not excluded['matched'] and excluded['exclude_hits']
        repeat_a,_=adapter({'support':[rows[i:i+100] for i in range(0,len(rows),100)]}) if source=='PEMEX' else cfe_adapter(rows)
        try:again=run_scan(db,source,request() if source=='PEMEX' else cfe_request(),repeat_a)
        finally:repeat_a.close()
        assert again['metrics']['new']==0 and again['metrics']['change_events']==0
        reports[source]={'unique':217,'raw':218,'batches':3,'late_match':detail['match'],'excluded':excluded,'unchanged_events':0,'document_references':out['metrics']['document_references']}
        assert detail['first_seen']!=detail['published_date'] and detail['last_seen']>=detail['first_seen']
    assert reports['PEMEX']['late_match']==reports['CFE']['late_match'] and reports['PEMEX']['excluded']==reports['CFE']['excluded']
    assert len({identity(source,'217') for source in ['PEMEX','CFE','COMPRAS_MX']})==3
    assert db.scalar(select(func.count()).select_from(Opp))==434
    record('cross_source.json',reports)

@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_cosmetic_whitespace_html_and_auxiliary_metadata_do_not_change_meaning(offline,source):
    c,db=offline
    if source=='PEMEX':
        before=raw(1,descripcion='Válvula industrial');after=raw(1,Id=999,descripcion='<style>.x{color:red}</style><p class="x">  Válvula\n industrial </p><script>malicious()</script>')
        factory=lambda row:adapter({'support':[[row]]})[0]
    else:
        before=cfe_row(Descripcion='Válvula industrial');after=cfe_row(Descripcion='  Válvula\n industrial  ',EntidadFederativa='auxiliar distinta')
        factory=lambda row:cfe_adapter([row],detail_edit=lambda page,key:page.replace('Área industrial de pruebas','<span class="changed-css"> Área industrial\n de pruebas </span>'))[0]
    for row in [before,after]:
        a=factory(row)
        try:out=run_scan(db,source,request() if source=='PEMEX' else cfe_request(),a)
        finally:a.close()
        assert out['status']=='SUCCESS'
    assert out['metrics']['change_events']==0 and out['metrics']['updated']==0

@pytest.mark.parametrize('source',['PEMEX','CFE'])
@pytest.mark.parametrize('state',['FOLLOWING','DISCARDED'])
def test_human_workflow_preserved_during_meaningful_changes(offline,source,state):
    c,db=offline;row=seed(db,source);url='/discovery/opportunities/'+row['id']
    assert c.patch(url+'/state',json={'internal_state':state,'expected_revision':row['revision']}).status_code==200
    a,_=adapter({'support':[[raw(1,descripcion='Descripción actualizada')]]}) if source=='PEMEX' else cfe_adapter([cfe_row(EstadoProcedimiento='Cancelado')])
    try:out=run_scan(db,source,request() if source=='PEMEX' else cfe_request(),a)
    finally:a.close()
    after=c.get(url).json();assert out['status']=='SUCCESS' and after['internal_state']==state and after['watching']==(state=='FOLLOWING')
    assert not after['linked_tender'] and after['unread_changes']>0


def test_cfe_partial_detail_never_removes_documents_or_opportunities(offline):
    c,db=offline
    for rows,fail,edit in [([cfe_row(1),cfe_row(2)],(),None),([cfe_row(1),cfe_row(2)],(2,),lambda page,key:page.replace("descargarAnexoConToken",'unsupportedLink'))]:
        a,_=cfe_adapter(rows,fail_ids=fail,detail_edit=edit)
        try:out=run_scan(db,'CFE',cfe_request(),a)
        finally:a.close()
    assert out['status']=='PARTIAL'
    assert not list(db.scalars(select(Change).where(Change.scan_run_id==out['id'],Change.category.in_(['DOCUMENT_REMOVED','NO_LONGER_OBSERVED']))))
    assert db.scalar(select(func.count()).select_from(Doc).where(Doc.active.is_(True)))==2

@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_remote_malicious_metadata_stays_text_and_preview_is_readonly(offline,source):
    c,db=offline;title='Referencia '+('muy larga '*40)+'<script>alert(1)</script>'
    row=seed(db,source,[raw(1,descripcion=title)] if source=='PEMEX' else [cfe_row(Descripcion=title)])
    before=db.scalar(select(func.count()).select_from(Tender));p=preview(c,row['id']);assert p['suggested_title'] is None
    assert db.scalar(select(func.count()).select_from(Tender))==before
    assert create(c,p).status_code==422
    if source=='PEMEX':assert '<script>' not in p['context']['description']
    else:assert '<script>' in p['context']['description'] # JSON literal; React must escape it, never execute it.

@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_canonical_downstream_and_no_automatic_domain_execution(offline,monkeypatch,tmp_path,source):
    c,db=offline;data=pdf_table();monkeypatch.setattr('app.main.get_licitia_data_root',lambda:tmp_path)
    monkeypatch.setattr('app.document_structure_orchestrator.SessionLocal',lambda:Session(bind=db.get_bind(),autoflush=False,join_transaction_mode='create_savepoint'))
    cls=PEMEXConcursosAdapter if source=='PEMEX' else CFEProcurementAdapter
    monkeypatch.setattr('app.discovery_handoff.adapter_for',lambda source:cls(httpx.MockTransport(lambda r:httpx.Response(200,content=data,headers={'content-type':'application/pdf'})),pacing=0))
    row=seed(db,source);p=preview(c,row['id'])
    with monkeypatch.context() as guard:
        def forbidden(*a,**k):raise AssertionError('AUTOMATIC_ANALYSIS_FORBIDDEN')
        for path in ['app.workspace_flow.process_workspace','app.document_structure_orchestrator.orchestrate_document_structure_available_only','app.ocr.TesseractOCRProvider.recognize','app.ocr.PaddleOCRProvider.recognize','app.ollama_vision.OllamaVisionAssistClient','app.proposal_readiness.evaluate','app.proposal_versions.create_version']:
            guard.setattr(path,forbidden)
        result=create(c,p,[choice(p)]);assert result.status_code==200,result.text
        tid=result.json()['tender_id'];assert not result.json()['analysis_started']
        for table in Base.metadata.tables.values():
            if 'tender_id' in table.c and table.name not in {'tender_documents','discovery_tender_links'}:
                assert db.scalar(select(func.count()).select_from(table).where(table.c.tender_id==tid))==0,table.name
    doc=db.scalar(select(TenderDocument).where(TenderDocument.tender_id==tid));assert doc.processing_status=='PENDING' and doc.sha256==sha256(data).hexdigest()
    assert c.get('/tenders/'+tid).status_code==200
    # Only this deliberate user processing command starts deterministic native analysis.
    result=c.post('/tenders/'+tid+'/workspace/process');assert result.status_code==200,result.text
    scopes=result.json()['scopes'];assert len(scopes)==2 and all(len(s['quantities'])==1 for s in scopes)
    assert c.get('/tenders/'+tid+'/commercial-matrix').status_code==200
    assert c.get('/tenders/'+tid+'/bid-readiness').status_code==200
    app.dependency_overrides[get_proposal_db]=lambda:db
    try:
        readiness=c.get('/tenders/'+tid+'/proposal-readiness');assert readiness.status_code==200,readiness.text
        assert readiness.json()['projection']['eligibility']=='NOT_ELIGIBLE' # Human pricing/review intentionally incomplete.
        assert c.get('/tenders/'+tid+'/proposal-versions').json()['items']==[]
    finally:app.dependency_overrides.pop(get_proposal_db,None)
    assert db.get(Opp,row['id']).internal_state=='IMPORTED'
    record('downstream_'+source.lower()+'.json',{'source':source,'canonical':True,'no_auto_domains':True,'explicit_native_process':True,'scopes':2,'quantities':2,'commercial':200,'bid_readiness':200,'proposal_readiness':200,'proposal_eligibility':'NOT_ELIGIBLE','hash':doc.sha256})


def test_scale_small_vs_large_select_growth_followed_and_imported(offline):
    c,db=offline
    def scan(rows,small=False):
        a,_=adapter({'support':[rows[i:i+100] for i in range(0,len(rows),100)]})
        try:return run_scan(db,'PEMEX',request(event_type='small') if small else request(),a)
        finally:a.close()
    scan([raw(i) for i in range(1,201)])
    oid=identity('PEMEX','EVENT-1');assert create(c,preview(c,oid)).status_code==200
    assert c.patch('/discovery/opportunities/'+identity('PEMEX','EVENT-2')+'/state',json={'internal_state':'FOLLOWING','expected_revision':1}).status_code==200
    def measure(rows,small=False):
        counts=Counter();bind=db.get_bind()
        def capture(*args):
            if args[2].lstrip().upper().startswith('SELECT'):counts['SELECT']+=1
            counts['ALL']+=1
        def other(*args):
            if args[0] is not bind:capture(*args)
        event.listen(bind,'before_cursor_execute',capture);event.listen(bind.engine,'before_cursor_execute',other)
        try:out=scan(rows,small)
        finally:event.remove(bind,'before_cursor_execute',capture);event.remove(bind.engine,'before_cursor_execute',other)
        return out,dict(counts)
    _,small=measure([raw(i) for i in range(1,21)],True)
    rows=[raw(i,descripcion='Actualizada' if i<=15 else f'Suministro válvula {i}') for i in range(1,196)]
    for row in rows[:25]:row['AttachmentFiles']['results'].append({'FileName':'Nuevo.pdf','ServerRelativeUrl':row['AttachmentFiles']['results'][0]['ServerRelativeUrl'].replace('Bases.pdf','Nuevo.pdf')})
    for row in rows[190:195]:row['AttachmentFiles']={'results':[]}
    rows.extend(raw(i) for i in range(201,221));out,large=measure(rows)
    counts=Counter(db.scalars(select(Change.category).where(Change.scan_run_id==out['id'])))
    assert counts=={'NEW_OPPORTUNITY':20,'METADATA_CHANGED':15,'DOCUMENT_ADDED':45,'DOCUMENT_REMOVED':5,'NO_LONGER_OBSERVED':5},counts
    assert large['SELECT']<=small['SELECT']+24 and large['SELECT']<50,(small,large)
    assert db.get(Opp,oid).internal_state=='IMPORTED' and db.get(Opp,identity('PEMEX','EVENT-2')).watching
    assert db.get(Tender,db.get(Link,oid).tender_id).title!='Actualizada'
    record('query_growth.json',{'small_opportunities':20,'large_opportunities':215,'small_queries':small,'large_queries':large,'changes':counts,'followed':True,'imported':True,'result':'PASS'})


def test_compras_mx_manual_ingestion_and_explicit_native_analysis_remain_optional(offline,monkeypatch,tmp_path):
    c,db=offline;monkeypatch.setattr('app.main.get_licitia_data_root',lambda:tmp_path)
    monkeypatch.setattr('app.document_structure_orchestrator.SessionLocal',lambda:Session(bind=db.get_bind(),autoflush=False,join_transaction_mode='create_savepoint'))
    assert c.post('/discovery/sources/COMPRAS_MX/scans',json={'request_id':str(uuid4()),'query':{'areas':['public']}}).status_code==409
    manual=c.post('/tenders',json={'title':'Manual Compras MX obtenido por usuario'});assert manual.status_code==201
    tid=manual.json()['id'];r=c.post('/tenders/'+tid+'/documents/import',files=[('files',('manual.pdf',pdf_table(),'application/pdf'))]);assert r.status_code==200
    assert not db.scalar(select(Link).where(Link.tender_id==tid))
    r=c.post('/tenders/'+tid+'/workspace/process');assert r.status_code==200 and len(r.json()['scopes'])==2


def test_duplicate_remote_names_do_not_silently_replace_originals(offline,monkeypatch,tmp_path):
    c,db=offline;monkeypatch.setattr('app.main.get_licitia_data_root',lambda:tmp_path);row=raw(1)
    duplicate={**row['AttachmentFiles']['results'][0]};duplicate['ServerRelativeUrl']+='.different';row['AttachmentFiles']['results'].append(duplicate)
    item=seed(db,rows=[row]);p=preview(c,item['id']);assert len(p['documents'])==2 and len({d['name'] for d in p['documents']})==1
    monkeypatch.setattr('app.discovery_handoff.adapter_for',lambda source:PEMEXConcursosAdapter(httpx.MockTransport(lambda r:httpx.Response(200,content=b'%PDF-1.4\n'+str(r.url).encode(),headers={'content-type':'application/pdf'})),pacing=0))
    r=create(c,p,[{'document_id':d['id']} for d in p['documents']]);assert r.status_code==200,r.text
    body=r.json();assert body['documents_status']=='PARTIAL' and {d['status'] for d in body['documents']}=={'IMPORTED','NAME_CONFLICT'}
    docs=list(db.scalars(select(TenderDocument).where(TenderDocument.tender_id==body['tender_id'])));assert len(docs)==1
    assert sha256((tmp_path/docs[0].stored_relative_path).read_bytes()).hexdigest()==docs[0].sha256


@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_handoff_profile_match_remains_reconstructable_after_profile_changes(offline,source):
    from app.discovery_contract import Opportunity,fingerprint
    c,db=offline;row=seed(db,source,[raw(1,descripcion='controlador lógico programable')] if source=='PEMEX' else [cfe_row(Descripcion='controlador lógico programable')])
    profile={'name':'Perfil histórico local','include_keywords':['PLC'],'exclude_keywords':['cancelado'],'synonyms':{'PLC':['controlador lógico programable']}}
    saved=c.post('/discovery/profiles',json=profile).json();url='/discovery/opportunities/'+row['id']+'/tender-preview'
    p=c.get(url,params={'profile_id':saved['id']}).json();assert p['profile_context']['match']['matched']
    changed={**profile,'include_keywords':['inexistente']}
    assert c.patch('/discovery/profiles/'+saved['id'],json={**changed,'expected_revision':1}).status_code==200
    before=db.scalar(select(func.count()).select_from(Tender))
    assert create(c,p,profile_id=saved['id']).status_code==409
    assert db.scalar(select(func.count()).select_from(Tender))==before
    fresh=c.get(url,params={'profile_id':saved['id']}).json();assert not fresh['profile_context']['match']['matched']
    # A mismatch is an explanation, never an automatic commercial block.
    result=create(c,fresh,profile_id=saved['id']);assert result.status_code==200,result.text
    link=db.get(Link,row['id']);captured=deepcopy(link.context['profile_context']);assert captured['revision']==2
    assert c.patch('/discovery/profiles/'+saved['id'],json={**profile,'expected_revision':2}).status_code==200
    after=c.get(url,params={'profile_id':saved['id']}).json()
    assert after['profile_context']['revision']==3 and after['profile_context']['match']['matched']
    assert after['creation_profile_context']==captured and after['creation_profile_status']=='CAPTURED'
    source_snapshot=Opportunity.model_validate({k:v for k,v in link.context.items() if k in Opportunity.model_fields})
    assert match_profile(Profile.model_validate(captured['configuration']),source,source_snapshot)==captured['match']
    assert fingerprint({k:v for k,v in captured.items() if k!='sha256'})==captured['sha256']
    audit=db.scalar(select(Change).where(Change.opportunity_id==row['id'],Change.category=='TENDER_CREATED'))
    assert audit.changed_fields['profile_id']==saved['id'] and audit.changed_fields['profile_revision']==2 and audit.changed_fields['profile_snapshot_sha256']==captured['sha256']
    assert create(c,p,profile_id=saved['id']).json()['tender_id']==result.json()['tender_id']
    record('profile_audit_'+source.lower()+'.json',{'result':'PASS','source':source,'captured_revision':2,'current_revision':3,'snapshot_sha_verified':True,'historical_match_reconstructed':True,'mismatch_does_not_block_human':True,'stale_preview_rejected':True})


def test_handoff_profile_absent_and_legacy_links_do_not_fabricate_match_history(offline):
    c,db=offline;row=seed(db);p=preview(c,row['id'])
    assert create(c,p,profile_id=str(uuid4())).status_code==404
    result=create(c,p);assert result.status_code==200
    assert preview(c,row['id'])['creation_profile_status']=='NO_PROFILE_SELECTED'
    link=db.get(Link,row['id']);link.context={k:v for k,v in link.context.items() if k!='profile_context'};db.commit()
    legacy=preview(c,row['id']);assert legacy['creation_profile_status']=='LEGACY_NOT_CAPTURED' and legacy['creation_profile_context'] is None
