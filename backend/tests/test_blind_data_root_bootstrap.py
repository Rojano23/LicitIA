"""BR synthetic settings/process/storage regression; no blind corpus or providers."""
import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.blind_environment import verify_storage_root, storage_identity
from test_selective_ocr_recovery import scene
from test_document_intelligence_integration import corpus

BACKEND=Path(__file__).resolve().parents[1]
URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v'


def isolated(code, root):
    env={**os.environ,'PYTHONPATH':str(BACKEND),'BR_ROOT':str(root)}
    env.pop('LICITIA_BLIND_DATA_ROOT',None)
    return subprocess.run([sys.executable,'-c',code],cwd=BACKEND,env=env,capture_output=True,text=True)


BOOT='''
import os
from app.blind_environment import establish_environment
root=establish_environment(database_url="'''+URL+'''",data_dir=os.environ['BR_ROOT'])
'''


def test_BR01_BR02_environment_precedes_settings_and_application(tmp_path):
    result=isolated(BOOT+'''
from app.config import get_settings
assert get_settings().licitia_data_dir==str(root)
from app import main
assert main.get_licitia_data_root()==root
assert main.settings.licitia_data_dir==str(root)
from app.database import engine
assert engine.url.database=='licitia_validation_06v'
''',tmp_path)
    assert result.returncode==0,result.stderr


def test_BR10_cached_previous_settings_require_fresh_process(tmp_path):
    result=isolated('''
from app.config import get_settings
get_settings()
'''+BOOT,tmp_path)
    assert result.returncode!=0 and 'FRESH_BLIND_BOOTSTRAP_PROCESS_REQUIRED' in result.stderr


def test_BR10_two_fresh_processes_honor_independent_roots(tmp_path):
    for name in ('a','b'):
        root=tmp_path/name;root.mkdir()
        result=isolated(BOOT+'''
from app.config import get_settings
assert get_settings().licitia_data_dir==str(root)
''',root)
        assert result.returncode==0,result.stderr


@pytest.fixture
def blind_root(tmp_path,monkeypatch):
    from app.config import get_settings
    root=tmp_path/'isolated';root.mkdir()
    monkeypatch.setenv('LICITIA_BLIND_DATA_ROOT',str(root))
    monkeypatch.setenv('LICITIA_DATA_DIR',str(root))
    monkeypatch.setattr(get_settings(),'licitia_data_dir',str(root))
    return root


def test_BR03_BR04_BR05_failure_point_import_binding_preparation(blind_root,tmp_path,monkeypatch):
    import fitz
    import app.main as main
    from app.database import SessionLocal
    from app.models import Tender
    from app.blind_selective_freeze import input_identity
    from app.document_intelligence_blind_run import prepare_tender_documents
    # Default project data root already exists, as in the failed lifecycle.
    import app.blind_environment as environment
    project=tmp_path/'project';project.mkdir()
    monkeypatch.setattr(environment,'BACKEND',project)
    default=project/'.licitia-data';default.mkdir()
    before=set(default.rglob('*'))
    pdf=fitz.open();page=pdf.new_page();page.insert_text((40,50),'Synthetic independent source.');raw=pdf.tobytes();pdf.close()
    client=TestClient(main.app)
    response=client.post('/tenders',json={'title':'Synthetic bootstrap contract'})
    assert response.status_code==201
    tender=response.json()['id']
    try:
        response=client.post(f'/tenders/{tender}/documents/import',files=[('files',('neutral.pdf',raw,'application/pdf'))])
        assert response.status_code==200,response.text
        outcome=response.json()[0];assert outcome['status']=='IMPORTED'
        with SessionLocal() as db:
            identity=input_identity(db,tender_id=tender)
            assert identity['documents'][0]['original_filename']=='neutral.pdf'
            files=list(blind_root.rglob('neutral.pdf'));assert len(files)==1 and files[0].read_bytes()==raw
            prepared=prepare_tender_documents(db,tender_id=tender)
            assert prepared[0].page_count==1
            assert input_identity(db,tender_id=tender)['documents']==identity['documents']
        assert set(default.rglob('*'))==before
    finally:
        with SessionLocal() as db:
            db.execute(delete(Tender).where(Tender.id==tender));db.commit()


def test_BR06_mismatch_before_marker(blind_root,tmp_path,monkeypatch):
    from app.blind_selective_freeze import execute_frozen_run,write_evidence,FREEZE_VERSION
    from app.config import get_settings
    # Storage validation precedes code/DB/input/provider work.
    write_evidence(tmp_path/'pre_execution.json',dict(schema_version=FREEZE_VERSION,schema_drift={},
        storage={'schema_version':'BLIND_STORAGE_ROOT_001','canonical_data_root':str(blind_root)}))
    monkeypatch.setattr(get_settings(),'licitia_data_dir',str(tmp_path))
    with pytest.raises(ValueError,match='BLIND_RUNTIME_DATA_ROOT_MISMATCH'):
        execute_frozen_run(None,directory=tmp_path,root=tmp_path,profile=None,authorized=True)
    assert not (tmp_path/'EXECUTION_STARTED.json').exists()


def test_BR07_unset_root_cannot_fallback(monkeypatch):
    monkeypatch.delenv('LICITIA_BLIND_DATA_ROOT',raising=False)
    with pytest.raises(ValueError,match='BLIND_BOOTSTRAP_REQUIRED'):
        storage_identity()


def test_BR08_ordinary_default_root_remains_valid(monkeypatch):
    monkeypatch.delenv('LICITIA_BLIND_DATA_ROOT',raising=False)
    assert verify_storage_root('.licitia-data')==(BACKEND/'.licitia-data').resolve()


def test_BR09_cross_root_rejected(blind_root,tmp_path):
    other=tmp_path/'other';other.mkdir()
    with pytest.raises(ValueError,match='FROZEN_DATA_ROOT_MISMATCH'):
        storage_identity(expected=str(other))


def test_BR11_root_does_not_change_semantic_plan(blind_root,tmp_path,monkeypatch,scene):
    from app.document_perception_planner import plan_document_ocr_tasks,TaskRequest,PerceptionTask
    db,tender,document,page=scene[0]
    args=dict(tender_id=tender.id,document_id=document.id,requests={page.id:(TaskRequest(PerceptionTask.SCOPE),)})
    first=plan_document_ocr_tasks(db,**args)
    other=tmp_path/'second';other.mkdir()
    from app.config import get_settings
    monkeypatch.setenv('LICITIA_BLIND_DATA_ROOT',str(other));monkeypatch.setenv('LICITIA_DATA_DIR',str(other))
    monkeypatch.setattr(get_settings(),'licitia_data_dir',str(other))
    second=plan_document_ocr_tasks(db,**args)
    assert first==second and asdict(first[0])==asdict(second[0])


def test_BR12_historical_freeze_not_upgraded(tmp_path,blind_root):
    from app.blind_selective_freeze import write_evidence,verify_execution_identity
    path=tmp_path/'pre_execution.json'
    write_evidence(path,{'schema_version':'DI_SELECTIVE_FREEZE_002','schema_drift':{}})
    before=path.read_bytes()
    with pytest.raises(ValueError,match='CURRENT_DRIFT_FREEZE_CONTRACT_REQUIRED'):
        verify_execution_identity(tmp_path,tmp_path,None)
    assert path.read_bytes()==before


@pytest.mark.parametrize('case',['missing','default','unwritable'])
def test_invalid_bootstrap_root(tmp_path,case):
    root=tmp_path/'missing' if case=='missing' else BACKEND/'.licitia-data' if case=='default' else tmp_path/'readonly'
    if case=='unwritable':root.mkdir();root.chmod(0o555)
    try:
        result=isolated(BOOT,root)
        assert result.returncode!=0
        assert any(reason in result.stderr for reason in ('BLIND_DATA_ROOT_MUST_EXIST','ISOLATED_BLIND_DATA_ROOT_REQUIRED','BLIND_DATA_ROOT_NOT_WRITABLE'))
    finally:
        if case=='unwritable':root.chmod(0o755)


def test_import_symlink_escape_fails_before_writing(blind_root,tmp_path):
    import io
    from starlette.datastructures import UploadFile
    from app.main import _store_uploaded_file
    outside=tmp_path/'outside';outside.mkdir()
    (blind_root/'tenders').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='BLIND_ORIGINAL_OUTSIDE_DATA_ROOT'):
        _store_uploaded_file('synthetic',UploadFile(io.BytesIO(b'synthetic'),filename='neutral.pdf'),None)
    assert list(outside.iterdir())==[]


def test_bootstrap_rebinding_without_settings_is_rejected(tmp_path):
    other=tmp_path/'other';other.mkdir()
    result=isolated(BOOT+"\nestablish_environment(database_url='"+URL+"',data_dir=root/'other')",tmp_path)
    assert result.returncode!=0 and 'BLIND_PROCESS_ROOT_ALREADY_BOUND' in result.stderr


def test_failure_point_fresh_bootstrap_then_canonical_api_import(tmp_path):
    synthetic_boot=BOOT.replace("root=establish_environment", "import app.blind_environment as environment\nfrom pathlib import Path\nenvironment.BACKEND=Path(os.environ['BR_ROOT'])/'project'\n(environment.BACKEND/'.licitia-data').mkdir(parents=True)\nroot=establish_environment")
    result=isolated(synthetic_boot+'''
from app.config import get_settings
assert get_settings().licitia_data_dir==str(root)
from app.main import app,get_licitia_data_root
from app.database import get_db
from app.models import Tender
from app.blind_selective_freeze import input_identity
from app.document_intelligence_blind_run import prepare_tender_documents
from sqlalchemy import create_engine,delete
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import fitz
# Override only the API database dependency: all synthetic writes stay in licitia_test.
engine=create_engine('postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test')
def test_database():
    with Session(engine) as db:yield db
app.dependency_overrides[get_db]=test_database
assert get_licitia_data_root()==root
from app.blind_environment import BACKEND
default=BACKEND/'.licitia-data'
assert default.is_dir()
before=set(default.rglob('*'))
pdf=fitz.open();page=pdf.new_page();page.insert_text((40,50),'Synthetic process source.');raw=pdf.tobytes();pdf.close()
with TestClient(app) as client:
    r=client.post('/tenders',json={'title':'Synthetic fresh bootstrap'});assert r.status_code==201
    tender=r.json()['id']
    try:
        r=client.post(f'/tenders/{tender}/documents/import',files=[('files',('source.pdf',raw,'application/pdf'))])
        assert r.status_code==200 and r.json()[0]['status']=='IMPORTED'
        assert len(list(root.rglob('source.pdf')))==1
        with Session(engine) as db:
            identity=input_identity(db,tender_id=tender)
            assert len(identity['documents'])==1
            assert prepare_tender_documents(db,tender_id=tender)[0].page_count==1
        assert set(default.rglob('*'))==before
    finally:
        with Session(engine) as db:
            db.execute(delete(Tender).where(Tender.id==tender));db.commit()
engine.dispose()
''',tmp_path)
    assert result.returncode==0,result.stderr
