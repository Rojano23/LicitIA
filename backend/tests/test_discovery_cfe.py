"""CFE verified public shapes, synthetic offline records. No public network/AI."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import os
from urllib.parse import parse_qs
from uuid import uuid4
import json
import httpx,pytest
from sqlalchemy import select,func,event
from tests.test_discovery import offline,raw as pemex_row,adapter as pemex_adapter,request as pemex_request
from app.discovery_cfe import CFEProcurementAdapter,AcquisitionError,ROOT,public_url,publication,MAX_RESPONSE
from app.discovery_contract import SourceQuery,ScanRequest,Profile,Opportunity,identity,match_profile,fingerprint
from app.discovery import run_scan,list_opportunities
from app.discovery_models import DiscoveryOpportunity,DiscoverySourceDocument,DiscoveryScanRun,DiscoverySource
from app.discovery_registry import adapter_for
from app.models import Tender

FIX=Path(__file__).parent/'fixtures/discovery'
BASE=json.loads((FIX/'cfe-row.json').read_text())
FORM=(FIX/'cfe-form.html').read_text();DETAIL=(FIX/'cfe-detail.html').read_text()
def row(i=123,**changes):return {**deepcopy(BASE),'Id':i,'Numero':f'CFE-SYNTHETIC-{i}-2026',**changes}
def query(size=100,**changes):return SourceQuery(areas=['public'],page_size=size,published_from=date(2026,10,22),published_to=date(2026,10,22),**changes)
def request(size=100):return ScanRequest(request_id=uuid4(),query=query(size))
def adapter(rows,fail_ids=(),detail_edit=None,listing=None):
    calls=[]
    def handler(req):
        assert req.url.host=='msc.cfe.mx'
        form=parse_qs(req.content.decode());calls.append((req.method,req.url.path,form))
        if req.method=='GET' and str(req.url)==ROOT:return httpx.Response(200,text=FORM,headers={'content-type':'text/html'})
        if req.url.path.endswith('/getProcBusqueda'):
            assert form['__RequestVerificationToken']==['synthetic-search-token']
            assert form['FechaPublicacionIni']==['2026-10-22']
            return listing or httpx.Response(200,json=rows)
        assert req.url.path.endswith('/Details') and req.method=='POST'
        assert form['__RequestVerificationToken']==['synthetic-detail-token']
        key=int(form['id'][0])
        if key in fail_ids:return httpx.Response(404,text='unavailable')
        source=next(r for r in rows if isinstance(r,dict) and r.get('Id')==key)
        page=DETAIL.format(id=key,number=source['Numero'])
        if detail_edit:page=detail_edit(page,key)
        return httpx.Response(200,text=page,headers={'content-type':'text/html; charset=utf-8'})
    return CFEProcurementAdapter(httpx.MockTransport(handler),pacing=0),calls


def test_cfe_normalization_identity_documents_and_sparse_fields(offline):
    c,db=offline;a,calls=adapter([row(EstadoProcedimiento=None,TipoContratacionClave=None,FechaPublicacion=None)])
    out=run_scan(db,'CFE',request(),a);assert out['status']=='SUCCESS'
    v=list_opportunities(db,source='CFE')['items'][0]
    assert v['id']==identity('CFE','123') and v['procedure_number']=='CFE-SYNTHETIC-123-2026'
    assert v['source_status'] is None and v['published_date'] is None and v['supply_type'] is None
    assert v['contracting_area']=='Área industrial de pruebas' and v['business_area']=='CFE Empresa Sintética'
    assert v['public_url']==ROOT and v['documents'][0]['name']=='Bases-123.pdf'
    assert v['documents'][0]['public_url'].startswith(ROOT+'Procedure/GetAnexo?id=')
    assert db.scalar(select(func.count()).select_from(DiscoverySourceDocument))==1
    assert '__RequestVerificationToken' not in json.dumps(v,default=str)
    assert all('GetAnexo' not in path for _,path,_ in calls);a.close()


def test_cfe_three_batch_large_late_profile_dedup_and_bounded_sql(offline):
    c,db=offline;rows=[row(i,Descripcion='Controlador lógico programable' if i==217 else 'Válvula') for i in range(1,218)]
    rows.insert(101,deepcopy(rows[0]));a,calls=adapter(rows);statements=[]
    def capture(*args):statements.append(args[2])
    bind=db.get_bind()
    def capture_other_connection(*args):
        if args[0] is not bind:capture(*args)
    event.listen(bind,'before_cursor_execute',capture);event.listen(bind.engine,'before_cursor_execute',capture_other_connection)
    try:out=run_scan(db,'CFE',request(),a)
    finally:
        event.remove(bind,'before_cursor_execute',capture);event.remove(bind.engine,'before_cursor_execute',capture_other_connection)
    assert out['status']=='SUCCESS';m=out['metrics']
    assert m['pages_completed']==3 and m['rows_retrieved']==218 and m['unique_opportunities']==217 and m['duplicates']==1
    assert len(statements)<60,(len(statements),statements)
    p=c.post('/discovery/profiles',json={'name':'Industrial','include_keywords':['PLC'],'synonyms':{'PLC':['controlador lógico programable']}}).json()
    matches=list_opportunities(db,profile_id=p['id'],matched_only=True)
    assert matches['total']==1 and matches['items'][0]['external_id']=='217'
    assert a.observation['listing_requests']==1 and a.observation['detail_requests']==218
    assert a.observation['batch_count']==3 and m['areas']['public']['source_reported_total'] is None
    (Path(os.environ.get('LICITIA_DISCOVERY_REPORT_ROOT','reports/m10_c'))/'cfe_large_fixture.json').write_text(json.dumps({'raw_rows':218,'unique':217,'batches':3,'duplicates':1,'sql_statements':len(statements),'last_batch_profile_match':'217','result':'PASS'},indent=2)+'\n')
    a.close()


def test_cfe_idempotency_change_fingerprint_workflow_and_search(offline):
    c,db=offline;a,_=adapter([row()]);first=run_scan(db,'CFE',request(),a);before=list_opportunities(db,source='CFE')['items'][0]
    c.patch('/discovery/opportunities/'+before['id']+'/state',json={'expected_revision':1,'internal_state':'FOLLOWING'})
    again=run_scan(db,'CFE',request(),a);assert again['metrics']['new']==0 and again['metrics']['unchanged']==1
    a.close();a,_=adapter([row(Numero='CFE-CHANGED-HUMAN-NUMBER')]);out=run_scan(db,'CFE',request(),a)
    after=list_opportunities(db,source='CFE')['items'][0]
    assert out['metrics']['updated']==1 and after['id']==before['id']
    assert after['previous_fingerprint']==before['source_fingerprint'] and after['internal_state']=='FOLLOWING'
    assert after['first_seen']==before['first_seen'] and after['last_seen']>=before['last_seen']
    for term in ['CHANGED-HUMAN','industrial de pruebas','Empresa Sintética']:
        assert list_opportunities(db,search=term)['total']==1
    assert list_opportunities(db,area='Área industrial de pruebas')['total']==1
    assert list_opportunities(db,source_status='Vigente')['total']==1
    assert list_opportunities(db,source_status='Cancelado')['total']==0
    assert list_opportunities(db,source='PEMEX')['total']==0;a.close()


def test_cfe_late_detail_failure_partial_retry_converges_no_tender(offline):
    c,db=offline;pe,_=pemex_adapter({'support':[[pemex_row(1)]]});run_scan(db,'PEMEX',pemex_request(),pe);pe.close()
    pe_before=list_opportunities(db,source='PEMEX')['items'][0]
    before=db.scalar(select(func.count()).select_from(Tender));rows=[row(i) for i in range(1,6)]
    a,_=adapter(rows,fail_ids={3});out=run_scan(db,'CFE',request(2),a)
    assert out['status']=='PARTIAL' and out['metrics']['pages_completed']==3 and out['metrics']['new']==4
    assert any(x['code']=='CFE_DETAIL_ACQUISITION_FAILED' for x in out['metrics']['diagnostics']);a.close()
    a,_=adapter(rows);retry=run_scan(db,'CFE',request(2),a)
    assert retry['status']=='SUCCESS' and retry['metrics']['new']==1 and retry['metrics']['unchanged']==4
    assert list_opportunities(db,source='CFE')['total']==5 and db.scalar(select(func.count()).select_from(Tender))==before
    assert list_opportunities(db,source='PEMEX')['items'][0]==pe_before;a.close()


@pytest.mark.parametrize('bad',[None,{},row(Id=None),row(Descripcion=''),row(FechaPublicacion='not-a-date')])
def test_cfe_malformed_record_is_not_success(offline,bad):
    c,db=offline;a,_=adapter([row(1),bad]);out=run_scan(db,'CFE',request(),a)
    assert out['status']=='PARTIAL' and out['metrics']['malformed_rows']==1;a.close()


def test_cfe_empty_array_and_missing_optional_detail(offline):
    c,db=offline;a,_=adapter([]);out=run_scan(db,'CFE',request(),a)
    assert out['status']=='SUCCESS' and out['metrics']['unique_opportunities']==0;a.close()
    a,_=adapter([row()],detail_edit=lambda s,i:s.replace('<td>Empresa</td>','<td>Other</td>').replace('<td>Área Contratante</td>','<td>Other2</td>'))
    v=a.fetch(query(),'public',None).rows[0]
    assert v.contracting_area is None and v.business_area=='CFE procedimientos públicos';a.close()


@pytest.mark.parametrize('bad',[
 'https://evil.example/Procedure/GetAnexo?id=1','http://msc.cfe.mx/Aplicaciones/NCFE/Concursos/Procedure/GetAnexo?id=1',
 'https://msc.cfe.mx.evil.test/Aplicaciones/NCFE/Concursos/Procedure/GetAnexo',
 'https://user@msc.cfe.mx/Aplicaciones/NCFE/Concursos/Procedure/GetAnexo',
 'https://msc.cfe.mx:444/Aplicaciones/NCFE/Concursos/Procedure/GetAnexo',
 ROOT+'%252e%252e/secret',ROOT+'Procedure/GetAnexo#fragment',ROOT+'Procedure/GetAnexo\n',
 ROOT+'Procedure/%255csecret',ROOT+'User/Login'])
def test_cfe_host_path_and_document_policy(bad):
    with pytest.raises(ValueError):public_url(bad,document=True)


@pytest.mark.parametrize('response',[
 httpx.Response(302,headers={'location':'https://evil.test'}),httpx.Response(401,json={'error':'restricted'}),
 httpx.Response(200,text='<html>error</html>',headers={'content-type':'text/html'}),httpx.Response(200,json={'rows':[]}),
])
def test_cfe_unsafe_transport_or_layout_fails_without_persistence(offline,response):
    c,db=offline;a,_=adapter([],listing=response);out=run_scan(db,'CFE',request(),a)
    assert out['status']=='FAILED' and out['metrics']['new']==0;a.close()


def test_cfe_size_limit_and_bounded_retry(monkeypatch):
    import app.discovery_cfe as module
    monkeypatch.setattr(module.time,'sleep',lambda n:None)
    calls=[]
    def handler(r):
        calls.append(r)
        return httpx.Response(503) if len(calls)<3 else httpx.Response(200,text=FORM,headers={'content-type':'text/html'})
    a=CFEProcurementAdapter(httpx.MockTransport(handler),pacing=0);a.prepare();assert len(calls)==3;a.close()
    monkeypatch.setattr(module,'MAX_RESPONSE',8)
    a=CFEProcurementAdapter(httpx.MockTransport(lambda r:httpx.Response(200,text='long response',headers={'content-type':'text/html'})),pacing=0)
    with pytest.raises(AcquisitionError,match='RESPONSE_LIMIT'):a.prepare()
    a.close()


def test_cfe_cursor_cannot_change_query_or_escape_host():
    a,_=adapter([row(1),row(2)]);batch=a.fetch(query(1),'public',None)
    assert not batch.terminal and batch.next_cursor
    with pytest.raises(AcquisitionError):a.fetch(query(2),'public',batch.next_cursor)
    with pytest.raises(AcquisitionError):a.fetch(query(1),'public','https://evil.test')
    assert a.fetch(query(1),'public',batch.next_cursor).terminal;a.close()


def test_cfe_wrong_detail_identity_and_unsafe_doc_are_partial(offline):
    c,db=offline;a,_=adapter([row()],detail_edit=lambda s,i:s.replace('CFE-SYNTHETIC-123-2026','OTHER'))
    out=run_scan(db,'CFE',request(),a);assert out['status']=='FAILED';a.close()
    a,_=adapter([row()],detail_edit=lambda s,i:s.replace("onclick=\"descargarAnexoConToken('synthetic-123!!')\"",'href="https://evil.test/GetAnexo?id=123"').replace('href="javascript:void(0)"',''))
    out=run_scan(db,'CFE',request(),a);assert out['status']=='PARTIAL' and out['metrics']['document_references']==0;a.close()


def test_registry_api_deferred_guard_and_generic_cfe_scan(offline,monkeypatch):
    c,db=offline;sources=c.get('/discovery/sources').json();assert {s['id'] for s in sources}=={'PEMEX','CFE','COMPRAS_MX'}
    deferred=next(s for s in sources if s['id']=='COMPRAS_MX')
    assert not deferred['enabled'] and deferred['capabilities']['automation_status']=='DEFERRED_SOURCE_AUTOMATION_RESTRICTED'
    payload=request().model_dump(mode='json')
    assert c.post('/discovery/sources/COMPRAS_MX/scans',json=payload).status_code==409
    assert c.patch('/discovery/sources/COMPRAS_MX',json={'enabled':True,'areas':['public']}).status_code==409
    with pytest.raises(Exception) as error:adapter_for('COMPRAS_MX')
    assert error.value.status_code==409
    assert db.scalar(select(func.count()).select_from(DiscoveryScanRun))==0
    a,_=adapter([row()]);monkeypatch.setattr('app.discovery.adapter_for',lambda source:a)
    result=c.post('/discovery/sources/CFE/scans',json=payload)
    assert result.status_code==200 and result.json()['status']=='SUCCESS'
    assert result.json()['source_id']=='CFE' and result.json()['metrics']['pages_completed']==1
    a.close()


def test_same_profile_namespace_and_pemex_fingerprint_compatibility(offline):
    c,db=offline;a,_=pemex_adapter({'support':[[pemex_row(1,descripcion='Controlador lógico programable')]]})
    assert run_scan(db,'PEMEX',pemex_request(),a)['status']=='SUCCESS';a.close()
    a,_=adapter([row(1,Descripcion='Controlador lógico programable')]);assert run_scan(db,'CFE',request(),a)['status']=='SUCCESS';a.close()
    p=Profile(name='Industrial',include_keywords=['PLC'],synonyms={'PLC':['controlador lógico programable']})
    values=list_opportunities(db)['items'];assert len(values)==2
    explanations=[]
    for value in values:
        obj=Opportunity.model_validate({k:v for k,v in value.items() if k in Opportunity.model_fields})
        match=match_profile(p,value['source_id'],obj);assert match['matched'];explanations.append(match['include_hits'])
        assert not match_profile(Profile(name='Exclude',include_keywords=['PLC'],exclude_keywords=['controlador'],synonyms=p.synonyms),value['source_id'],obj)['matched']
    assert explanations[0]==explanations[1]
    assert len({identity(s,'123') for s in ['PEMEX','CFE','COMPRAS_MX']})==3
    obj=Opportunity(external_id='old',title='Legacy',business_area='Area',public_url='https://www.pemex.com')
    assert obj.source_fingerprint==fingerprint(obj.model_dump(mode='json',exclude={'raw_metadata','procedure_number'}))


def test_cfe_generic_core_rejects_synthetic_reported_total_mismatch(offline,monkeypatch):
    # Contract robustness only: the live CFE source does NOT publish this count.
    c,db=offline;a,_=adapter([row()]);original=a.fetch
    def fetch(*args):
        batch=original(*args);batch.source_total=2;return batch
    monkeypatch.setattr(a,'fetch',fetch)
    out=run_scan(db,'CFE',request(),a)
    assert out['status']=='PARTIAL'
    assert any(d['code']=='SOURCE_TOTAL_MISMATCH' for d in out['metrics']['diagnostics']);a.close()
