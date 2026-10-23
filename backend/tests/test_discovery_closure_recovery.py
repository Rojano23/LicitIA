"""M10-D upgrade/restore/retry, real offline PostgreSQL+originals backup/restore, including provenance."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import os
import json,sys
import httpx
from sqlalchemy import create_engine,select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from tests.test_local_recovery import runtime
from tests.test_discovery import adapter,raw,request
from tests.test_discovery_handoff import PDF
from app.database import get_db
from app.main import app
from app.discovery_pemex import PEMEXConcursosAdapter
from app.discovery_models import DiscoveryImportReceipt,DiscoveryCoverage,DiscoveryTenderLink
from app.local_deployment import REPOSITORY
from app.local_recovery import _run,private_postgres,backup,restore,verify_backup


def test_closure_upgrade_077_078_079_restore_and_safe_retry(runtime,tmp_path,monkeypatch):
    cluster=runtime.directory/'postgres';secret=runtime.directory/'password.tmp';secret.write_text(runtime.password)
    try:_run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile',secret,'--encoding=UTF8','--locale=C'])
    finally:secret.unlink()
    monkeypatch.setattr('app.discovery.adapter_for',lambda source:adapter({'support':[[raw(1)]]})[0])
    monkeypatch.setattr('app.discovery_handoff.adapter_for',lambda source:PEMEXConcursosAdapter(httpx.MockTransport(lambda r:httpx.Response(200,content=PDF,headers={'content-type':'application/pdf'})),pacing=0))
    @contextmanager
    def application(config,env):
        url=URL.create('postgresql+psycopg',username='licitia',password=config.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']});engine=create_engine(url)
        def sessions():
            with Session(engine,autoflush=False) as db:yield db
        app.dependency_overrides[get_db]=sessions;monkeypatch.setattr('app.main.get_licitia_data_root',lambda:config.directory/'data')
        try:
            with TestClient(app) as client:yield client,engine
        finally:app.dependency_overrides.pop(get_db,None);engine.dispose()
    with private_postgres(runtime,cluster) as env:
        _run(['createdb','licitia_uat'],env)
        migration={**env,'DATABASE_URL':f"postgresql+psycopg://licitia:{runtime.password}@/licitia_uat?host={env['PGHOST']}&port={env['PGPORT']}"}
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','20261022_composition_077'],migration)
        # A real pre-Discovery Tender/file must survive the two Discovery migrations.
        with application(runtime,env) as (c,engine):
            legacy=c.post('/tenders',json={'title':'Legacy pre MVP10'}).json()
            imported=c.post('/tenders/'+legacy['id']+'/documents/import',files=[('files',('legacy.pdf',PDF,'application/pdf'))]);assert imported.status_code==200
            legacy_documents=c.get('/tenders/'+legacy['id']+'/documents').json()
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','20261022_discovery_078'],migration)
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration)
        # DDL reversibility in this disposable cluster only; no development DB touched.
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','downgrade','20261022_discovery_078'],migration)
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration)
        with application(runtime,env) as (c,engine):
            assert c.get('/tenders/'+legacy['id']).json()==legacy
            assert c.get('/tenders/'+legacy['id']+'/documents').json()==legacy_documents
            shared_profile=c.post('/discovery/profiles',json={'name':'Closure restore profile','include_keywords':['PLC'],'exclude_keywords':['cancelado'],'synonyms':{'PLC':['válvula']}}).json()
            scan_request=request().model_dump(mode='json')
            assert c.post('/discovery/sources/PEMEX/scans',json=scan_request).json()['status']=='SUCCESS'
            row=c.get('/discovery/opportunities').json()['items'][0];oid=row['id'];url='/discovery/opportunities/'+oid
            c.patch(url+'/state',json={'internal_state':'FOLLOWING','expected_revision':row['revision']})
            p=c.get(url+'/tender-preview',params={'profile_id':shared_profile['id']}).json();body=c.post(url+'/create-tender',json={'confirm':True,'expected_binding':p['binding'],'profile_id':shared_profile['id'],'documents':[{'document_id':p['documents'][0]['id']}]}).json()
            assert body['documents_status']=='COMPLETE_SELECTION',body
            history=c.get(url+'/changes').json();unread=[e['id'] for e in history['items'] if not e['acknowledged_at']]
            c.post(url+'/changes/acknowledge',json={'change_ids':unread})
            before={'row':c.get(url).json(),'history':c.get(url+'/changes').json(),'preview':c.get(url+'/tender-preview').json(),'documents':c.get('/tenders/'+body['tender_id']+'/documents').json(),'profiles':c.get('/discovery/profiles').json(),'scans':c.get('/discovery/scans').json(),'sources':c.get('/discovery/sources').json()}
            with Session(engine) as db:
                receipt=db.scalar(select(DiscoveryImportReceipt));receipt_before={k:getattr(receipt,k) for k in ['id','opportunity_id','source_document_id','tender_identity','tender_document_id','sha256','source_url','metadata_fingerprint']}
                coverage=db.scalar(select(DiscoveryCoverage));coverage_before=(coverage.scope_sha,coverage.opportunity_id,coverage.present)
    destination=tmp_path/'backup';assert backup(runtime,destination)['status']=='VERIFIED';manifest=verify_backup(destination)
    assert manifest.alembic_revisions==('20261023_discovery_079',)
    clean=tmp_path/'clean';clean.mkdir(mode=0o700);(clean/'data').mkdir(mode=0o700);target=replace(runtime,root=str(clean),password='c'*64)
    assert restore(target,destination)['status']=='RESTORED'
    with private_postgres(target,target.directory/'postgres') as env:
        with application(target,env) as (c,engine):
            after={'row':c.get(url).json(),'history':c.get(url+'/changes').json(),'preview':c.get(url+'/tender-preview').json(),'documents':c.get('/tenders/'+body['tender_id']+'/documents').json(),'profiles':c.get('/discovery/profiles').json(),'scans':c.get('/discovery/scans').json(),'sources':c.get('/discovery/sources').json()}
            assert after==before and after['row']['internal_state']=='IMPORTED' and after['row']['watching']
            with Session(engine) as db:
                receipt=db.scalar(select(DiscoveryImportReceipt));assert receipt_before=={k:getattr(receipt,k) for k in receipt_before}
                coverage=db.scalar(select(DiscoveryCoverage));assert coverage_before==(coverage.scope_sha,coverage.opportunity_id,coverage.present)
                assert db.get(DiscoveryTenderLink,oid).tender_id==body['tender_id']
                assert db.get(DiscoveryTenderLink,oid).context['profile_context']['id']==shared_profile['id']
            original=next((target.directory/'data').rglob('Bases.pdf'));assert original.read_bytes()==PDF
            assert c.post('/discovery/sources/PEMEX/scans',json=scan_request).json()['id']==before['scans'][0]['id']
            next_request={**scan_request,'request_id':str(__import__('uuid').uuid4())}
            rerun=c.post('/discovery/sources/PEMEX/scans',json=next_request).json();assert rerun['status']=='SUCCESS' and rerun['metrics']['new']==0 and rerun['metrics']['change_events']==0
            assert c.get(url+'/changes').json()==before['history']
            repeated=c.post(url+'/create-tender',json={'confirm':True,'expected_binding':p['binding'],'profile_id':shared_profile['id'],'documents':[{'document_id':p['documents'][0]['id']}]}).json()
            assert repeated['tender_id']==body['tender_id'] and repeated['already_created']
            assert c.get('/discovery/opportunities').json()['total']==1
            assert len(c.get('/tenders/'+body['tender_id']+'/documents').json())==1
            assert c.get('/tenders/'+legacy['id']+'/documents').json()==legacy_documents
    (Path(os.environ.get('LICITIA_DISCOVERY_REPORT_ROOT','reports/m10_c'))/'closure_restore_retry.json').write_text(json.dumps({'status':'PASS','real_private_postgres':True,'workflow':True,'watching':True,'history_ack':True,'coverage':True,'link':True,'receipt_provenance':True,'original_sha_verified':True,'offline':True,'upgrade_077_078_079':True,'legacy_tender_and_file':True,'profile_and_scan_history':True,'safe_scan_retry_after_restore':True,'safe_handoff_retry_after_restore':True},indent=2))
