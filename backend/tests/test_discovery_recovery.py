"""M10C-46 real offline PostgreSQL+originals backup/restore, including provenance."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
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


def test_discovery_workflow_history_link_receipt_and_original_roundtrip(runtime,tmp_path,monkeypatch):
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
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration)
        # DDL reversibility in this disposable cluster only; no development DB touched.
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','downgrade','20261022_discovery_078'],migration)
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration)
        with application(runtime,env) as (c,engine):
            assert c.post('/discovery/sources/PEMEX/scans',json=request().model_dump(mode='json')).json()['status']=='SUCCESS'
            row=c.get('/discovery/opportunities').json()['items'][0];oid=row['id'];url='/discovery/opportunities/'+oid
            c.patch(url+'/state',json={'internal_state':'FOLLOWING','expected_revision':row['revision']})
            p=c.get(url+'/tender-preview').json();body=c.post(url+'/create-tender',json={'confirm':True,'expected_binding':p['binding'],'documents':[{'document_id':p['documents'][0]['id']}]}).json()
            assert body['documents_status']=='COMPLETE_SELECTION',body
            history=c.get(url+'/changes').json();unread=[e['id'] for e in history['items'] if not e['acknowledged_at']]
            c.post(url+'/changes/acknowledge',json={'change_ids':unread})
            before={'row':c.get(url).json(),'history':c.get(url+'/changes').json(),'preview':c.get(url+'/tender-preview').json(),'documents':c.get('/tenders/'+body['tender_id']+'/documents').json()}
            with Session(engine) as db:
                receipt=db.scalar(select(DiscoveryImportReceipt));receipt_before={k:getattr(receipt,k) for k in ['id','opportunity_id','source_document_id','tender_identity','tender_document_id','sha256','source_url','metadata_fingerprint']}
                coverage=db.scalar(select(DiscoveryCoverage));coverage_before=(coverage.scope_sha,coverage.opportunity_id,coverage.present)
    destination=tmp_path/'backup';assert backup(runtime,destination)['status']=='VERIFIED';manifest=verify_backup(destination)
    assert manifest.alembic_revisions==('20261023_discovery_079',)
    clean=tmp_path/'clean';clean.mkdir(mode=0o700);(clean/'data').mkdir(mode=0o700);target=replace(runtime,root=str(clean),password='c'*64)
    assert restore(target,destination)['status']=='RESTORED'
    with private_postgres(target,target.directory/'postgres') as env:
        with application(target,env) as (c,engine):
            after={'row':c.get(url).json(),'history':c.get(url+'/changes').json(),'preview':c.get(url+'/tender-preview').json(),'documents':c.get('/tenders/'+body['tender_id']+'/documents').json()}
            assert after==before and after['row']['internal_state']=='IMPORTED' and after['row']['watching']
            with Session(engine) as db:
                receipt=db.scalar(select(DiscoveryImportReceipt));assert receipt_before=={k:getattr(receipt,k) for k in receipt_before}
                coverage=db.scalar(select(DiscoveryCoverage));assert coverage_before==(coverage.scope_sha,coverage.opportunity_id,coverage.present)
                assert db.get(DiscoveryTenderLink,oid).tender_id==body['tender_id']
            original=next((target.directory/'data').rglob('Bases.pdf'));assert original.read_bytes()==PDF
    Path('reports/m10_c/backup_restore.json').write_text(json.dumps({'status':'PASS','real_private_postgres':True,'workflow':True,'watching':True,'history_ack':True,'coverage':True,'link':True,'receipt_provenance':True,'original_sha_verified':True,'offline':True},indent=2))
