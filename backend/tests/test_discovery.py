"""M10A offline contracts over current public SharePoint shapes; no real network."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
import json,socket
import httpx,pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func,event
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine,get_db
from app.discovery_models import DiscoveryOpportunity,DiscoverySourceDocument,DiscoveryScanRun,DiscoverySource
from app.discovery_contract import SourceQuery,ScanRequest,Profile,Opportunity,Batch,identity,match_profile
from app.discovery_pemex import PEMEXConcursosAdapter,public_url,AREAS,AcquisitionError
from app.discovery import run_scan,bootstrap,list_opportunities

@pytest.fixture
def offline(monkeypatch):
    def denied(*a,**k):raise AssertionError('No network/analysis in offline Discovery tests')
    monkeypatch.setattr(socket,'create_connection',denied)
    with engine.connect() as connection:
        tx=connection.begin()
        with Session(bind=connection,autoflush=False,join_transaction_mode='create_savepoint') as db:
            app.dependency_overrides[get_db]=lambda:db
            try:
                bootstrap(db)
                with TestClient(app) as client:yield client,db
            finally:app.dependency_overrides.pop(get_db,None)
        tx.rollback()

def query(**changes):return SourceQuery(areas=['support'],page_size=100,**changes)
def request(**changes):return ScanRequest(request_id=uuid4(),query=query(**changes))
BASE_ROW=json.loads((Path(__file__).parent/'fixtures/discovery/pemex-row.json').read_text())

def raw(i,**changes):
    return {**deepcopy(BASE_ROW),'Id':i,'Title':f'EVENT-{i}','descripcion':f'Suministro válvula {i}','inicio':'2026-10-01T00:00:00Z',
        'tipoevento':'Nacional','tiposuministro':'Bienes','AttachmentFiles':{'results':[{'FileName':'Bases.pdf',
        'ServerRelativeUrl':f'/procura/procedimientos-de-contratacion/concursosabiertos/Lists/Concursoseinvitaciones/Attachments/{i}/Bases.pdf'}]},**changes}

def adapter(pages,*,fail=None):
    calls=[];holder={}
    def handler(req):
        assert req.url.host=='www.pemex.com'
        area=next(k for k,v in AREAS.items() if v['list'] in str(req.url))
        page=int(req.url.params.get('$skip','0'));calls.append((area,page))
        if fail and fail(area,page):return httpx.Response(404,json={'error':'synthetic unavailable'})
        sequence=pages[area];data=deepcopy(sequence[page]);next_url=None
        if page+1<len(sequence):
            params=dict(req.url.params);params['$skip']=str(page+1)
            next_url=str(req.url.copy_with(params=params))
        if isinstance(data,list):data={'results':data}
        if next_url:data['__next']=next_url
        return httpx.Response(200,json={'d':data})
    value=PEMEXConcursosAdapter(httpx.MockTransport(handler),pacing=0);holder['adapter']=value
    return value,calls


def test_m10a01_02_05_23_24_28_29_normalization_and_source(offline):
    c,db=offline;s=c.get('/discovery/sources').json();assert len(s)==3 and len(next(x for x in s if x['id']=='PEMEX')['areas'])==4
    a,calls=adapter({'support':[[raw(1,tipoevento=None)]]});out=run_scan(db,'PEMEX',request(),a)
    assert out['status']=='SUCCESS';item=list_opportunities(db)['items'][0]
    assert item['external_id']=='EVENT-1' and item['event_type'] is None and item['source_status'] is None
    assert item['contracting_area'] is None and item['document_count']==1
    assert item['documents_state']=='REFERENCES_DISCOVERED_NOT_DOWNLOADED'
    assert db.scalar(select(func.count()).select_from(DiscoverySourceDocument))==1
    assert item['business_area']==AREAS['support']['label']
    a.close()


def test_m10a03_06_07_08_09_10_20_30_37_38_39_identity_history(offline):
    c,db=offline;a,_=adapter({'support':[[raw(1)]]});req=request()
    first=run_scan(db,'PEMEX',req,a);before=list_opportunities(db)['items'][0]
    assert before['internal_state']=='NEW' and before['first_seen']!=before['published_date']
    changed=c.patch('/discovery/opportunities/'+before['id']+'/state',json={'expected_revision':1,'internal_state':'FOLLOWING'})
    assert changed.status_code==200
    same=run_scan(db,'PEMEX',req,a);assert same['id']==first['id']
    second=run_scan(db,'PEMEX',request(),a);after=list_opportunities(db)['items'][0]
    assert second['metrics']['unchanged']==1 and after['first_seen']==before['first_seen'] and after['last_seen']>=before['last_seen']
    a.close();a,_=adapter({'support':[[raw(1,descripcion='Descripción cambiada')]]})
    updated=run_scan(db,'PEMEX',request(),a);last=list_opportunities(db)['items'][0]
    assert updated['metrics']['updated']==1 and last['previous_fingerprint']==before['source_fingerprint']
    assert last['internal_state']=='FOLLOWING' and last['source_status'] is None
    assert db.scalar(select(func.count()).select_from(DiscoveryOpportunity))==1
    assert db.scalar(select(func.count()).select_from(DiscoverySourceDocument))==1
    assert c.patch('/discovery/opportunities/'+last['id']+'/state',json={'expected_revision':1,'internal_state':'REVIEW'}).status_code==409
    a.close()


def test_m10a11_12_13_14_15_16_17_22_55_56_complete_large_pagination_and_matching(offline):
    c,db=offline
    pages=[[raw(i) for i in range(1,101)],[raw(i) for i in range(100,200)],[raw(i) for i in range(200,218)]]
    pages[2][-1]['descripcion']='Controlador lógico programable exclusivo final'
    a,calls=adapter({'support':pages});statements=[]
    def collect(conn,cursor,statement,params,context,executemany):statements.append(statement)
    event.listen(engine,'before_cursor_execute',collect)
    try:out=run_scan(db,'PEMEX',request(published_from=datetime(2026,1,1).date()),a)
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert out['status']=='SUCCESS' and calls==[('support',0),('support',1),('support',2)]
    assert out['metrics']['unique_opportunities']==217 and out['metrics']['duplicates']==1
    p=c.post('/discovery/profiles',json={'name':'PLC','include_keywords':['PLC'],'synonyms':{'PLC':['controlador lógico programable']}}).json()
    result=c.get('/discovery/opportunities',params={'profile_id':p['id'],'matched_only':True,'limit':1}).json()
    assert result['total']==1 and result['items'][0]['external_id']=='EVENT-217'
    assert result['items'][0]['match']['include_hits'][0]['kind']=='SYNONYM'
    assert len(statements)<100,{'sql':len(statements)}
    repeated=run_scan(db,'PEMEX',request(),a);assert repeated['metrics']['new']==0
    assert db.scalar(select(func.count()).select_from(DiscoveryOpportunity))==217
    Path('reports/m10_c/pemex_large_fixture.json').write_text(json.dumps({'unique':217,'raw':218,'pages':3,'sql_statements':len(statements),
        'match_last_page':'EVENT-217','duplicate':1,'result':'PASS'},indent=2)+'\n');a.close()


@pytest.mark.parametrize('total',[1,3])
def test_m10a20_21_source_total_agreement(offline,total):
    c,db=offline;a,_=adapter({'support':[{'results':[raw(1)],'__count':str(total)}]})
    out=run_scan(db,'PEMEX',request(),a)
    assert out['status']==('SUCCESS' if total==1 else 'PARTIAL')
    assert out['metrics']['areas']['support']['source_reported_total']==total;a.close()


def test_m10a18_19_26_27_40_41_42_43_partial_retry_and_malformed(offline):
    c,db=offline;pages={'support':[[raw(1)],[raw(2)],[raw(3)]],'logistics':[[raw(4)]]}
    a,calls=adapter(pages,fail=lambda area,page:area=='support' and page==1)
    req=ScanRequest(request_id=uuid4(),query=SourceQuery(areas=['support','logistics']))
    out=run_scan(db,'PEMEX',req,a)
    assert out['status']=='PARTIAL' and out['metrics']['areas']['logistics']['status']=='SUCCESS'
    assert out['metrics']['pages_attempted']==3 and out['metrics']['pages_completed']==2
    assert list_opportunities(db)['total']==2;a.close()
    a,_=adapter(pages);out=run_scan(db,'PEMEX',ScanRequest(request_id=uuid4(),query=req.query),a)
    assert out['status']=='SUCCESS' and list_opportunities(db)['total']==4;a.close()
    a,_=adapter({'support':[[raw(5),raw(6,Title=None),raw(7,tipoevento=None)]]})
    out=run_scan(db,'PEMEX',request(),a);assert out['status']=='PARTIAL' and out['metrics']['malformed_rows']==1
    assert list_opportunities(db)['total']==6;a.close()


def test_m10a04_cross_source_namespace(offline):
    c,db=offline
    assert identity('PEMEX','123')!=identity('SYNTHETIC','123')
    from app.discovery import persist_batch
    db.add(DiscoverySource(id='SYNTHETIC',name='Contract namespace',base_url='https://example.invalid',adapter_version='fixture',enabled=True,configuration={}));db.flush()
    value=Opportunity(external_id='123',business_area='A',title='Same',public_url='https://example.invalid')
    persist_batch(db,'PEMEX',[value],{});persist_batch(db,'SYNTHETIC',[value],{});db.flush()
    assert list_opportunities(db)['total']==2


@pytest.mark.parametrize('text,profile,matched',[
 ('INSTRUMENTACIÓN',{'include_keywords':['instrumentacion']},True),
 ('instrumentación servicio médico',{'include_keywords':['instrumentación'],'exclude_keywords':['servicio medico']},False),
 ('Controlador lógico programable',{'include_keywords':['PLC'],'synonyms':{'PLC':['controlador lógico programable']}},True),
 ('XPLC',{'include_keywords':['PLC']},False),
 ('válvula',{'include_keywords':['válvula'],'source_ids':['OTHER']},False),
 ('válvula',{'include_keywords':['válvula'],'business_areas':['OTHER']},False),
 ('válvula',{'include_keywords':['válvula'],'active':False},False),
])
def test_m10a31_32_33_34_35_36_keywords(text,profile,matched):
    value=Opportunity(external_id='1',business_area='A',title=text,public_url='https://example.invalid')
    result=match_profile(Profile(name='Test',**profile),'PEMEX',value)
    assert result['matched'] is matched and result['policy']=='ANY_INCLUDE_EXCLUDE_WINS'


@pytest.mark.parametrize('url',[
 'http://www.pemex.com/procura/x','https://evil.invalid/procura/x','https://localhost/procura/x',
 'https://www.pemex.com@evil.invalid/procura/x','https://www.pemex.com:444/procura/x',
 'https://www.pemex.com'+ '/procura/procedimientos-de-contratacion/concursosabiertos/%252e%252e/private',
 '/procura/procedimientos-de-contratacion/concursosabiertos/../private','file:///etc/passwd',
])
def test_m10a44_45_46_url_policy(url):
    with pytest.raises(ValueError):public_url(url)


def test_m10a47_48_49_50_51_52_53_remote_content_and_boundaries(offline,monkeypatch):
    c,db=offline
    def denied(*a,**k):raise AssertionError('No analysis allowed')
    monkeypatch.setattr('app.proposal_exports.create_export',denied)
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize',denied)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient',denied)
    from app.models import Tender
    before=db.scalar(select(func.count()).select_from(Tender))
    row=raw(1,descripcion='<script>window.evil=1</script><b>Válvula</b>')
    row['AttachmentFiles']['results'].append({'FileName':'unsafe','ServerRelativeUrl':'https://evil.invalid/a.pdf'})
    a,_=adapter({'support':[[row]]});out=run_scan(db,'PEMEX',request(),a)
    assert out['status']=='PARTIAL' and list_opportunities(db)['items'][0]['title']=='Válvula'
    assert list_opportunities(db)['items'][0]['document_count']==1
    assert db.scalar(select(func.count()).select_from(Tender))==before
    assert c.patch('/discovery/opportunities/'+list_opportunities(db)['items'][0]['id']+'/state',json={'expected_revision':1,'internal_state':'IMPORTED'}).status_code==422;a.close()


def test_disappeared_rows_retained_profile_revision_and_api_filters(offline):
    c,db=offline;a,_=adapter({'support':[[raw(1),raw(2)]]});run_scan(db,'PEMEX',request(),a);a.close()
    a,_=adapter({'support':[[]]});run_scan(db,'PEMEX',request(),a);a.close()
    assert list_opportunities(db)['total']==2
    profile=c.post('/discovery/profiles',json={'name':'v','include_keywords':['válvula']}).json()
    assert c.patch('/discovery/profiles/'+profile['id'],json={'name':'updated','expected_revision':1}).status_code==200
    assert c.patch('/discovery/profiles/'+profile['id'],json={'name':'stale','expected_revision':1}).status_code==409
    assert c.get('/discovery/opportunities',params={'search':'EVENT-2'}).json()['total']==1
    assert c.get('/discovery/opportunities',params={'source':'OTHER'}).json()['total']==0
    assert c.get('/discovery/opportunities',params={'limit':201}).status_code==422


def test_continuation_cycle_and_filter_escape(offline,monkeypatch):
    c,db=offline;a,_=adapter({'support':[[raw(1)]]})
    q=query(event_type="x' or true or 'x")
    assert "x'' or true or ''x" in str(httpx.URL(a.first_url(q,'support')).params['$filter'])
    value=a.normalize(raw(1),'support')[0]
    monkeypatch.setattr(a,'fetch',lambda *args:Batch(rows=[value],raw_count=1,next_cursor='same',terminal=False))
    out=run_scan(db,'PEMEX',request(),a)
    assert out['status']=='PARTIAL' and out['metrics']['pages_completed']==2
    assert any(d['code']=='CONTINUATION_CYCLE' for d in out['metrics']['diagnostics']);a.close()


def test_interruption_missing_terminal_order_mutation_and_conflicting_duplicates(offline,monkeypatch):
    c,db=offline;a,_=adapter({'support':[[raw(1),raw(2)]]})
    first=run_scan(db,'PEMEX',request(),a);a.close()
    run=db.get(DiscoveryScanRun,first['id']);run.status='RUNNING';run.finished_at=None;db.commit()
    a,_=adapter({'support':[[raw(2)],[raw(1)]]});second=run_scan(db,'PEMEX',request(),a)
    assert second['status']=='SUCCESS' and second['metrics']['new']==0
    old=db.get(DiscoveryScanRun,first['id']);db.refresh(old)
    assert old.status=='PARTIAL' and 'interruption' in old.metrics;a.close()
    a,_=adapter({'support':[[raw(1)],[raw(1,descripcion='conflict')]]})
    result=run_scan(db,'PEMEX',request(),a)
    assert result['status']=='PARTIAL' and any(i['code']=='CONFLICTING_DUPLICATE_REPRESENTATION' for i in result['metrics']['diagnostics']);a.close()
    a,_=adapter({'support':[[]]});monkeypatch.setattr(a,'fetch',lambda *args:Batch(rows=[],raw_count=0,terminal=False))
    assert run_scan(db,'PEMEX',request(),a)['status']=='FAILED';a.close()


def test_contracting_area_null_and_literal_status_separate(offline):
    c,db=offline;a,_=adapter({'support':[[raw(1,areacontratante='Área pública publicada')]]})
    run_scan(db,'PEMEX',request(),a)
    item=list_opportunities(db)['items'][0];assert item['contracting_area']=='Área pública publicada'
    # Generic adapter can provide a literal status; PEMEX currently doesn't expose it.
    from app.discovery import persist_batch
    value=Opportunity.model_validate(db.get(DiscoveryOpportunity,item['id']).representation)
    value.source_status='Public source literal status';persist_batch(db,'PEMEX',[value],{});db.commit()
    changed=c.patch('/discovery/opportunities/'+item['id']+'/state',json={'expected_revision':2,'internal_state':'DISCARDED'}).json()
    assert changed['source_status']=='Public source literal status' and changed['internal_state']=='DISCARDED';a.close()


def test_source_retry_mime_limit_redirect_and_continuation_security(monkeypatch):
    monkeypatch.setattr('app.discovery_pemex.time.sleep',lambda *args:None)
    attempts=[]
    def retry(req):
        attempts.append(1)
        return httpx.Response(503 if len(attempts)<3 else 200,json={'d':{'results':[]}})
    a=PEMEXConcursosAdapter(httpx.MockTransport(retry),pacing=0)
    assert a.fetch(query(),'support',None).terminal and len(attempts)==3;a.close()
    for response in [httpx.Response(302,headers={'location':'https://evil.invalid'}),httpx.Response(200,text='<script/>'),httpx.Response(200,json={'layout':'changed'})]:
        a=PEMEXConcursosAdapter(httpx.MockTransport(lambda req:response),pacing=0)
        with pytest.raises(ValueError):a.fetch(query(),'support',None)
        a.close()
    a=PEMEXConcursosAdapter(pacing=0)
    with pytest.raises(ValueError):a.continuation('https://evil.invalid/x',query(),'support')
    with pytest.raises(ValueError):a.continuation(a.endpoint('logistics')+'?$skip=1',query(),'support')
    with pytest.raises(ValueError):a.continuation(a.first_url(query(),'support')+'&$filter=x&$skip=1',query(),'support')
    a.close()


def test_adapter_cap_and_empty_matching_policy(offline,monkeypatch):
    c,db=offline;a,_=adapter({'support':[[raw(1)]]})
    value=a.normalize(raw(1),'support')[0]
    monkeypatch.setattr(a,'fetch',lambda *args:Batch(rows=[value],raw_count=1,next_cursor='next',terminal=False))
    monkeypatch.setattr('app.discovery.MAX_BATCHES',1)
    out=run_scan(db,'PEMEX',request(),a)
    assert out['status']=='PARTIAL' and any(d['code']=='BATCH_LIMIT_WITH_REMAINING_RESULTS' for d in out['metrics']['diagnostics'])
    assert match_profile(Profile(name='All'), 'PEMEX',value)['matched']
    a.close()


def test_generic_opaque_cursor_adapter_and_no_canonical_writes(offline):
    c,db=offline
    db.add(DiscoverySource(id='SYNTHETIC',name='Generic cursor contract',base_url='https://example.invalid',adapter_version='opaque-v1',enabled=True,configuration={'areas':['a']}));db.flush()
    class OpaqueAdapter:
        source_id='SYNTHETIC';version='opaque-v1';areas={'a':{}}
        def __init__(self):self.calls=[]
        def fetch(self,query,area,cursor):
            self.calls.append(cursor);number={None:1,'opaque-next-a':2,'opaque-next-b':3}[cursor]
            value=Opportunity(external_id=str(number),business_area='Generic',title='Generic source',source_status='OPEN',public_url='https://example.invalid')
            return Batch(rows=[value],raw_count=1,next_cursor={1:'opaque-next-a',2:'opaque-next-b',3:None}[number],terminal=number==3,source_total=3)
        def close(self):pass
        def capabilities(self):return {'pagination':'OPAQUE_CURSOR'}
    a=OpaqueAdapter();writes=[]
    def collect(conn,cursor,statement,params,context,executemany):
        if statement.lstrip().upper().startswith(('INSERT ','UPDATE ','DELETE ')):writes.append(statement)
    event.listen(engine,'before_cursor_execute',collect)
    try:out=run_scan(db,'SYNTHETIC',ScanRequest(request_id=uuid4(),query=SourceQuery(areas=['a'])),a)
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert out['status']=='SUCCESS' and a.calls==[None,'opaque-next-a','opaque-next-b']
    assert out['metrics']['unique_opportunities']==3
    for statement in writes:assert 'discovery_' in statement.split('VALUES')[0].split('SET')[0],statement


def test_failed_page_commit_does_not_publish_uncommitted_counts(offline,monkeypatch):
    c,db=offline;a,_=adapter({'support':[[raw(1)]]});original_commit=db.commit;calls=[]
    def fail_second_commit():
        calls.append(1)
        if len(calls)==2:raise RuntimeError('Synthetic page commit failed before durability')
        return original_commit()
    monkeypatch.setattr(db,'commit',fail_second_commit)
    out=run_scan(db,'PEMEX',request(),a)
    assert db.scalar(select(func.count()).select_from(DiscoveryOpportunity))==0
    assert out['status']=='FAILED' and out['metrics']['new']==0 and out['metrics']['unique_opportunities']==0
    assert out['metrics']['areas']['support']['status']=='FAILED'
    a.close()


def test_profile_listing_is_bounded_and_paginated(offline):
    c,db=offline
    for name in ['A','B','C']:assert c.post('/discovery/profiles',json={'name':name}).status_code==200
    first=c.get('/discovery/profiles',params={'limit':2,'offset':0}).json()
    second=c.get('/discovery/profiles',params={'limit':2,'offset':2}).json()
    assert [p['name'] for p in first]==['A','B'] and [p['name'] for p in second]==['C']
    assert c.get('/discovery/profiles',params={'limit':201}).status_code==422
