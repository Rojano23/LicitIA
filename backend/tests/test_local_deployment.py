"""Deployment boundaries, without Tender content or model inference."""
from contextlib import contextmanager
from dataclasses import asdict,replace
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from app.local_deployment import (RuntimeConfig,REPOSITORY,load_config,validate_storage,
    local_url,aggregate,readiness,OllamaReadiness)

@pytest.fixture
def runtime(tmp_path):
    (tmp_path/'data').mkdir()
    return RuntimeConfig(root=str(tmp_path.resolve()),password='a'*64)

@pytest.mark.parametrize('url',['https://example.com','http://example.com','http://localhost/a',
                                 'http://user@localhost','http://127.0.0.1/?secret=x'])
def test_external_provider_rejected(url):
    with pytest.raises(ValueError):local_url(url)

def test_local_provider_allowed():assert local_url('http://127.0.0.1:11434/')=='http://127.0.0.1:11434'

def test_ambient_blind_cloud_and_database_overridden(runtime,monkeypatch):
    monkeypatch.setenv('LICITIA_BLIND_DATA_ROOT','/wrong')
    monkeypatch.setenv('LICITIA_OLLAMA_BASE_URL','https://example.com')
    monkeypatch.setenv('DATABASE_URL','postgresql://wrong')
    env=runtime.environment()
    assert 'LICITIA_BLIND_DATA_ROOT' not in env
    assert env['DATABASE_URL']==runtime.database_url
    assert env['LICITIA_DATA_DIR']==str(runtime.directory/'data')
    assert env['LICITIA_OLLAMA_BASE_URL'].startswith('http://127.0.0.1:')
    assert env['LICITIA_LOCAL_AI_ENABLED']=='false' and env['LICITIA_RUNTIME_LOCAL_ONLY']=='1'

@pytest.mark.parametrize('values',[dict(root='relative'),dict(root=str(REPOSITORY)),
    dict(password='change_me'),dict(api_port=55432),dict(pg_port=5432,web_port=5432),dict(provider_enabled='false')])
def test_invalid_config_fails_closed(runtime,values):
    with pytest.raises(ValueError):replace(runtime,**values)

def test_private_config_required(runtime):
    path=runtime.directory/'runtime.json';path.write_text(json.dumps(asdict(runtime)));path.chmod(0o644)
    with pytest.raises(ValueError,match='0600'):load_config(path)
    path.chmod(0o600);assert load_config(path)==runtime

def test_symlink_storage_rejected(runtime):
    link=runtime.directory/'link';link.symlink_to(runtime.directory/'data',target_is_directory=True)
    with pytest.raises(ValueError):validate_storage(link)

def test_readonly_storage_rejected(runtime):
    path=runtime.directory/'data';path.chmod(0o500)
    try:
        with pytest.raises(ValueError):validate_storage(path)
    finally:path.chmod(0o700)

@pytest.mark.parametrize(('parts','expected'),[
    ({'db':dict(state='FAILED',required=True)},'FAILED'),
    ({'db':dict(state='READY',required=True),'llm':dict(state='DEGRADED',required=False)},'DEGRADED'),
    ({'db':dict(state='READY',required=True)},'READY')])
def test_health_classification(parts,expected):assert aggregate(parts)==expected

def test_disabled_provider_never_connects(runtime,monkeypatch):
    monkeypatch.setattr('urllib.request.build_opener',lambda *a:pytest.fail('Unexpected probe'))
    assert OllamaReadiness().probe(runtime)==('DEGRADED','LOCAL_PROVIDER_DISABLED')

def test_missing_provider_degraded(runtime,monkeypatch):
    class Broken:
        def open(self,*a,**kw):raise OSError('private details')
    monkeypatch.setattr('urllib.request.build_opener',lambda *a:Broken())
    assert OllamaReadiness().probe(replace(runtime,provider_enabled=True))==('DEGRADED','LOCAL_PROVIDER_UNAVAILABLE')

def test_wrong_model_digest(runtime,monkeypatch):
    import io
    payloads=[{'version':'0.23.3'},{'models':[{'name':runtime.model,'digest':'wrong'}]}]
    class Probe:
        def open(self,*a,**kw):return io.BytesIO(json.dumps(payloads.pop(0)).encode())
    monkeypatch.setattr('urllib.request.build_opener',lambda *a:Probe())
    assert OllamaReadiness().probe(replace(runtime,provider_enabled=True))==('DEGRADED','MODEL_MISSING_OR_DIGEST_MISMATCH')

class FakeDatabase:
    def exec_driver_sql(self,*a):pass
    def execute(self,*a):return self
    def scalars(self):return self
    def all(self):return ['20261021_commercial_073']
    @contextmanager
    def connect(self):yield self
    def dispose(self):pass

def test_dependencies_and_missing_components(runtime,monkeypatch):
    monkeypatch.setattr('sqlalchemy.create_engine',lambda *a,**kw:FakeDatabase())
    monkeypatch.setattr('app.local_deployment.subprocess.run',lambda *a,**kw:SimpleNamespace(stdout='List:\neng\nspa\n'))
    result=readiness(runtime)
    assert result['state']=='DEGRADED' and result['components']['database_migrations']['state']=='READY'
    def absent(*a,**kw):raise FileNotFoundError('Missing binary')
    monkeypatch.setattr('app.local_deployment.subprocess.run',absent)
    result=readiness(runtime)
    assert result['state']=='FAILED' and result['components']['tesseract']['detail']=='FileNotFoundError'

def test_missing_package_fails_without_secret_leak(runtime,monkeypatch):
    def missing(*a):raise ValueError('secret connection string')
    monkeypatch.setattr('app.local_deployment.importlib.metadata.version',missing)
    monkeypatch.setattr('sqlalchemy.create_engine',lambda *a,**kw:FakeDatabase())
    monkeypatch.setattr('app.local_deployment.subprocess.run',lambda *a,**kw:SimpleNamespace(stdout='List:\neng\nspa\n'))
    result=readiness(runtime)
    assert result['state']=='FAILED' and result['components']['camelot']['detail']=='ValueError'
    assert 'secret' not in json.dumps(result)

def test_external_network_denied_before_connect(runtime):
    result=subprocess.run([sys.executable,'-c',"import socket; socket.create_connection(('198.51.100.1',443),timeout=.1)"],env=runtime.environment(),capture_output=True,text=True)
    assert result.returncode!=0 and 'LICITIA_EXTERNAL_NETWORK_DISABLED' in result.stderr
    events=[json.loads(x) for x in (runtime.directory/'network.jsonl').read_text().splitlines()]
    assert events and all(not x['allowed'] for x in events)

def test_configure_does_not_overwrite_secret(tmp_path):
    path=tmp_path/'new/runtime.json';script=REPOSITORY/'backend/scripts/licitia_local.py'
    cmd=[sys.executable,str(script),'--config',str(path),'configure']
    first=subprocess.run(cmd,capture_output=True,text=True);assert first.returncode==0,first.stderr
    original=path.read_bytes();second=subprocess.run(cmd,capture_output=True,text=True)
    assert second.returncode!=0 and path.read_bytes()==original and 'password' not in first.stdout


def test_configure_refuses_foreign_runtime_directory(tmp_path):
    foreign=tmp_path/'postgres';foreign.mkdir();(foreign/'PG_VERSION').write_text('17')
    script=REPOSITORY/'backend/scripts/licitia_local.py'
    result=subprocess.run([sys.executable,str(script),'--config',str(tmp_path/'runtime.json'),'configure'],capture_output=True,text=True)
    assert result.returncode!=0 and 'EMPTY_NEW_RUNTIME_DIRECTORY_REQUIRED' in result.stderr
    assert not (tmp_path/'runtime.json').exists() and (foreign/'PG_VERSION').read_text()=='17'


def test_outdated_database_requires_migration(runtime,monkeypatch):
    class OutdatedDatabase(FakeDatabase):
        def all(self):return ['20261013_req_perception_prov_072']
    monkeypatch.setattr('sqlalchemy.create_engine',lambda *a,**kw:OutdatedDatabase())
    monkeypatch.setattr('app.local_deployment.subprocess.run',lambda *a,**kw:SimpleNamespace(stdout='List:\neng\nspa\n'))
    result=readiness(runtime)
    assert result['state']=='FAILED'
    assert result['components']['database_migrations']['state']=='FAILED'
