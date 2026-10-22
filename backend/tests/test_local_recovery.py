"""RC-H3 offline backup, validation, rollback and real PostgreSQL roundtrip."""
from contextlib import contextmanager
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest
from app.local_deployment import RuntimeConfig, REPOSITORY
from app.local_recovery import (BackupManifest, FileEntry, atomic_json, backup, canonical, category,
    digest, private_postgres, recover_restore, recovery_status, require_stopped, restore, schema_heads,
    swap_candidate, tree_files, verify_backup, _run)


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path/'runtime'; root.mkdir(mode=0o700); (root/'data').mkdir(mode=0o700)
    return RuntimeConfig(root=str(root.resolve()), password='b'*64)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path/'bundle'; (root/'storage/tenders/a/originals/b').mkdir(parents=True)
    (root/'database.dump').write_bytes(b'synthetic dump verification only')
    (root/'storage/tenders/a/originals/b/.DS_Store').write_bytes(b'generic hidden original')
    entries = tuple(FileEntry(path=p.relative_to(root).as_posix(),size=p.stat().st_size,sha256=digest(p),category=category(p.relative_to(root).as_posix())) for p in tree_files(root))
    from datetime import datetime, timezone
    manifest = BackupManifest(created_at=datetime.now(timezone.utc),application_head='synthetic',application_code_sha256='synthetic-code',alembic_revisions=schema_heads(),storage_identity='opaque',database_identity='synthetic-db',files=entries,file_count=len(entries),orphan_original_count=0)
    payload = manifest.model_dump(mode='json')
    atomic_json(root/'manifest.json',{'payload':payload,'sha256':hashlib.sha256(canonical(payload)).hexdigest()})
    return root


def rewrite_manifest(bundle, change):
    data = json.loads((bundle/'manifest.json').read_bytes()); change(data['payload'])
    data['sha256'] = hashlib.sha256(canonical(data['payload'])).hexdigest()
    atomic_json(bundle/'manifest.json',data)


def test_RH302_manifest_and_hidden_original_verify(bundle):
    result = verify_backup(bundle)
    assert result.file_count == 2
    assert any(f.path.endswith('/.DS_Store') for f in result.files)


def test_RH303_tamper_fails_verification(bundle):
    (bundle/'database.dump').write_bytes(b'changed')
    with pytest.raises(ValueError,match='CHECKSUM'): verify_backup(bundle)


def test_RH311_schema_and_extra_missing_files_refused(bundle):
    rewrite_manifest(bundle,lambda p:p.update(alembic_revisions=['incompatible']))
    with pytest.raises(ValueError,match='SCHEMA'): verify_backup(bundle)


@pytest.mark.parametrize('mutation',['extra','missing','symlink','path_escape','manifest_checksum'])
def test_backup_rejects_incomplete_or_unsafe_bundle(bundle,mutation,tmp_path):
    if mutation=='extra': (bundle/'extra').write_text('extra')
    elif mutation=='missing': (bundle/'database.dump').unlink()
    elif mutation=='symlink':
        (bundle/'database.dump').unlink(); (bundle/'database.dump').symlink_to(tmp_path/'unrelated')
    elif mutation=='path_escape': rewrite_manifest(bundle,lambda p:p['files'][0].update(path='../escape'))
    else:
        data=json.loads((bundle/'manifest.json').read_bytes()); data['sha256']='0'*64
        (bundle/'manifest.json').write_text(json.dumps(data))
    with pytest.raises(ValueError): verify_backup(bundle)


def test_running_instance_and_launcher_lock_refused(runtime,tmp_path):
    (runtime.directory/'running.json').write_text('{}')
    with pytest.raises(ValueError,match='STOP_INSTANCE'): backup(runtime,tmp_path/'backup')
    (runtime.directory/'running.json').unlink()
    with (runtime.directory/'operation.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='OPERATION_ACTIVE'): backup(runtime,tmp_path/'backup')


def stage_pair(runtime):
    (runtime.directory/'postgres').mkdir(); (runtime.directory/'postgres/identity').write_text('old db')
    (runtime.directory/'data/identity').write_text('old storage')
    stage=runtime.directory/('.restore-'+uuid4().hex)
    for name in ('postgres','data'):
        (stage/'candidate'/name).mkdir(parents=True)
        (stage/'candidate'/name/'identity').write_text('new '+name)
    return stage


def test_RH312_failed_swap_rolls_back_both_resources(runtime,monkeypatch):
    stage=stage_pair(runtime); original=os.replace
    def fail(source,destination):
        if Path(source)==stage/'candidate/data': raise OSError('simulated disk failure')
        return original(source,destination)
    monkeypatch.setattr('app.local_recovery.os.replace',fail)
    with pytest.raises(OSError): swap_candidate(runtime,stage)
    assert (runtime.directory/'postgres/identity').read_text()=='old db'
    assert (runtime.directory/'data/identity').read_text()=='old storage'
    assert recovery_status(runtime)['status']=='NO_PENDING_RESTORE'


def test_RH310_hard_process_exit_during_swap_is_recoverable(runtime):
    stage=stage_pair(runtime)
    script='''
import os,sys
from pathlib import Path
from app.local_deployment import RuntimeConfig
from app.local_recovery import swap_candidate
config=RuntimeConfig(root=sys.argv[1],password='b'*64)
stage=Path(sys.argv[2]); original=os.replace
def interrupted(source,destination):
    result=original(source,destination)
    if Path(source)==stage/'candidate/postgres': os._exit(73)
    return result
os.replace=interrupted
swap_candidate(config,stage)
'''
    result=subprocess.run([sys.executable,'-c',script,str(runtime.directory),str(stage)],env={**os.environ,'PYTHONPATH':str(REPOSITORY/'backend')})
    assert result.returncode==73
    assert recovery_status(runtime)['status']=='PENDING_RESTORE'
    assert recover_restore(runtime)['status']=='ROLLED_BACK'
    assert (runtime.directory/'postgres/identity').read_text()=='old db'
    assert (runtime.directory/'data/identity').read_text()=='old storage'


def test_RH311_corrupt_restore_never_touches_current_state(runtime,bundle):
    (runtime.directory/'data/keep').write_text('preserve')
    (bundle/'database.dump').write_bytes(b'tampered')
    with pytest.raises(ValueError): restore(runtime,bundle)
    assert (runtime.directory/'data/keep').read_text()=='preserve'
    assert not list(runtime.directory.glob('.restore-*'))


def test_RH301_RH304_RH305_RH306_RH307_real_backup_restore_roundtrip(runtime,tmp_path,monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app
    from tests.test_native_table_bridge import pdf_table

    cluster=runtime.directory/'postgres'
    with (runtime.directory/'password.tmp').open('w') as stream: stream.write(runtime.password)
    try:
        _run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile',runtime.directory/'password.tmp','--encoding=UTF8','--locale=C'])
    finally: (runtime.directory/'password.tmp').unlink()

    @contextmanager
    def application(config, env):
        url=URL.create('postgresql+psycopg',username='licitia',password=config.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']})
        engine=create_engine(url)
        def session():
            with Session(engine,autoflush=False) as db: yield db
        app.dependency_overrides[get_db]=session
        monkeypatch.setattr('app.main.get_licitia_data_root',lambda:config.directory/'data')
        monkeypatch.setattr('app.document_structure_orchestrator.SessionLocal',lambda:Session(engine,autoflush=False))
        try:
            with TestClient(app) as client: yield client
        finally:
            app.dependency_overrides.pop(get_db,None); engine.dispose()

    def denied(*a,**kw): raise AssertionError('Recovery must not acquire perception')
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize',denied)
    monkeypatch.setattr('app.ocr.PaddleOCRProvider.recognize',denied)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient',denied)
    with private_postgres(runtime,cluster) as env:
        _run(['createdb','licitia_uat'],env)
        url=URL.create('postgresql+psycopg',username='licitia',password=runtime.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']})
        migration_env={**env,'DATABASE_URL':f"postgresql+psycopg://licitia:{runtime.password}@/licitia_uat?host={env['PGHOST']}&port={env['PGPORT']}"}
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration_env)
        with application(runtime,env) as client:
            response=client.post('/tenders',json={'title':'Generic recovery tender'}); assert response.status_code==201
            tender=response.json()['id']
            response=client.post(f'/tenders/{tender}/documents/import',files=[('files',('table.pdf',pdf_table(),'application/pdf')),('files',('.DS_Store',b'generic hidden input','application/octet-stream'))])
            assert response.status_code==200
            response=client.post(f'/tenders/{tender}/workspace/process'); assert response.status_code==200,response.text
            before=response.json(); scope=before['scopes'][0]; review=scope['review']
            response=client.post(f"/tenders/{tender}/scope-review/{scope['scope_detail_id']}/decisions",json={'decision':'CORRECTED','correction':{'description':'Corrección humana sintética'},'note':'Conservar auditoría','expected_projection_fingerprint':review['projection_fingerprint'],'expected_current_review_revision':review['current_review_revision']})
            assert response.status_code==200,response.text
            before=client.get(f'/tenders/{tender}/workspace').json()
    receipt_bytes=b'{"attempts":2,"status":"RETRY_EXHAUSTED","fingerprint":"synthetic-control"}'
    for name in ('ocr-task-receipts-v1','vision-task-receipts-v1'):
        directory=runtime.directory/'data'/name; directory.mkdir()
        (directory/'synthetic.json').write_bytes(receipt_bytes)
    destination=tmp_path/'real-backup'
    result=backup(runtime,destination)
    assert result['status']=='VERIFIED'
    verified=verify_backup(destination)
    assert any(f.category=='DATABASE' for f in verified.files)
    assert any(f.category=='MANIFEST' for f in verified.files)
    assert sum(f.category=='RECEIPT' for f in verified.files)==2
    assert any(f.path.endswith('/.DS_Store') for f in verified.files)
    assert not any('password' in f.path or 'runtime.json' in f.path for f in verified.files)
    assert runtime.password not in (destination/'manifest.json').read_text()
    assert all(p.stat().st_mode & 0o077 == 0 for p in tree_files(destination))
    # Alter only generated test working state, then restore into a clean independent root.
    shutil.rmtree(runtime.directory/'data'); (runtime.directory/'data').mkdir()
    clean=tmp_path/'clean'; clean.mkdir(mode=0o700); (clean/'data').mkdir()
    target=replace(runtime,root=str(clean),password='c'*64)
    assert restore(target,destination)['status']=='RESTORED'
    for name in ('ocr-task-receipts-v1','vision-task-receipts-v1'):
        assert (target.directory/'data'/name/'synthetic.json').read_bytes()==receipt_bytes
    with private_postgres(target,target.directory/'postgres') as env:
        with application(target,env) as client:
            assert client.get('/tenders').json()[0]['title']=='Generic recovery tender'
            after=client.get(f'/tenders/{tender}/workspace').json()
            assert after['scopes']==before['scopes']
            assert len(after['scopes'])==2
            for scope in after['scopes']:
                assert len(scope['quantities'])==1
                assert scope['quantities'][0]['scope_detail_id']==scope['scope_detail_id']
                assert scope['source']['available'] and scope['quantities'][0]['source']['available']
            assert after['scopes'][0]['description']=='Corrección humana sintética'
            assert after['scopes'][0]['review']['history'][0]['review']['note']=='Conservar auditoría'
            assert after['processing']['status']==before['processing']['status']
    # A syntactically checksummed but unusable dump fails in staging, preserving restored work.
    broken=tmp_path/'broken'; shutil.copytree(destination,broken)
    (broken/'database.dump').write_bytes(b'invalid pg archive')
    def resign(payload):
        for f in payload['files']:
            if f['path']=='database.dump': f.update(size=(broken/'database.dump').stat().st_size,sha256=digest(broken/'database.dump'))
    rewrite_manifest(broken,resign)
    prior={p.relative_to(target.directory/'data').as_posix():digest(p) for p in tree_files(target.directory/'data')}
    with pytest.raises(ValueError,match='pg_restore'): restore(target,broken)
    assert prior=={p.relative_to(target.directory/'data').as_posix():digest(p) for p in tree_files(target.directory/'data')}
    with private_postgres(target,target.directory/'postgres') as env:
        with application(target,env) as client:
            assert client.get(f'/tenders/{tender}/workspace').json()['scopes']==before['scopes']

    evidence={'status':'PASS','kind':'REAL_PRIVATE_POSTGRES_GENERIC_API_ROUNDTRIP','scope_count':2,'quantity_count':2,
        'distinct_scope_parents':2,'human_scope_correction_preserved':True,'source_and_manifests_preserved':True,
        'ocr_vision_receipts_preserved':True,'source_destination_passwords_different':True,'db_reconnect_and_app_restart_verified':True,
        'invalid_dump_restore_preserved_valid_current_state':True,'provider_calls':0,'blind_corpus_used':False}
    (REPOSITORY/'backend/reports/rc_h3/e2e_restore_result.json').write_text(json.dumps(evidence,indent=2))


def test_restore_uses_private_verified_backup_snapshot_despite_external_source_changes(bundle,tmp_path,monkeypatch):
    from app.local_recovery import copy_verified_backup
    expected=verify_backup(bundle); real=shutil.copytree
    def source_changes_after_copy(source,destination,*args,**kwargs):
        result=real(source,destination,*args,**kwargs)
        if Path(source)==bundle:
            (bundle/'database.dump').write_bytes(b'another valid checksummed backup generation')
            def resign(payload):
                for entry in payload['files']:
                    if entry['path']=='database.dump': entry.update(size=(bundle/'database.dump').stat().st_size,sha256=digest(bundle/'database.dump'))
            rewrite_manifest(bundle,resign)
        return result
    monkeypatch.setattr('app.local_recovery.shutil.copytree',source_changes_after_copy)
    snapshot=copy_verified_backup(bundle,tmp_path/'private-snapshot',expected)
    assert verify_backup(snapshot)==expected
    assert verify_backup(bundle)!=expected
    with pytest.raises(ValueError,match='BACKUP_CHANGED_DURING_COPY'):
        copy_verified_backup(bundle,tmp_path/'changed-before-copy',expected)
