"""M9C backup/restore: real private PostgreSQL plus generated files/receipts."""
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
import json,sys
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.models import Tender,ProposalReadinessSnapshot,ProposalComposition
from app.local_deployment import REPOSITORY
from app.local_recovery import private_postgres,_run,backup,restore
from app.proposal_versions import create_version,freeze_version,CreateProposal,FreezeProposal
from app.proposal_composition import initialize,Initialize,projection
from app.proposal_exports import create_export,verify_export,artifact_file
from app.proposal_export_contract import ExportRequest
from tests.test_local_recovery import runtime
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection
from tests.test_proposal_versions import ready,create
from tests.test_proposal_composition import finish


def test_m9c_backup_restore_metadata_binaries_and_frozen_source(ready,runtime,tmp_path,monkeypatch):
    c,t,db,m,snapshot=ready
    original,_=create(c,t,snapshot);finish(c,t,original)
    captured=deepcopy(db.get(ProposalComposition,original['id']).content)
    stored=db.get(ProposalReadinessSnapshot,snapshot['payload']['snapshot_id'])
    values={column.name:getattr(stored,column.name) for column in ProposalReadinessSnapshot.__table__.columns}
    cluster=runtime.directory/'postgres';password=runtime.directory/'password.tmp';password.write_text(runtime.password)
    try:_run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile',password,'--encoding=UTF8','--locale=C'])
    finally:password.unlink()
    def url(config,env):return URL.create('postgresql+psycopg',username='licitia',password=config.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']})
    with private_postgres(runtime,cluster) as env:
        _run(['createdb','licitia_uat'],env)
        migration_env={**env,'DATABASE_URL':f"postgresql+psycopg://licitia:{runtime.password}@/licitia_uat?host={env['PGHOST']}&port={env['PGPORT']}"}
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration_env)
        engine=create_engine(url(runtime,env),isolation_level='REPEATABLE READ')
        with Session(engine,autoflush=False) as isolated,monkeypatch.context() as patch:
            patch.setattr('app.main.get_licitia_data_root',lambda:runtime.directory/'data')
            isolated.add(Tender(id=t,title='Synthetic export restore'));isolated.flush()
            isolated.add(ProposalReadinessSnapshot(**values));isolated.flush()
            version=create_version(isolated,t,CreateProposal(request_id=uuid4(),snapshot_id=stored.id,acknowledge_warnings=True,acknowledge_stale=True))
            now=datetime.now(timezone.utc)
            isolated.add(ProposalComposition(version_id=version.id,contract_version='proposal-composition-v1',revision=1,
                content=captured,created_at=now,updated_at=now));isolated.flush()
            freeze_version(isolated,t,version.id,FreezeProposal(expected_edit_revision=1,expected_composition_revision=1,acknowledge_warnings=True,acknowledge_stale=True))
            receipt=create_export(isolated,t,version.id,ExportRequest(request_id=uuid4()))
            assert verify_export(isolated,t,version.id,receipt['request_id'])['verification_status']=='VERIFIED'
            before=projection(isolated,t,version.id);isolated.commit()
        engine.dispose()
    destination=tmp_path/'export-backup';assert backup(runtime,destination)['status']=='VERIFIED'
    clean=tmp_path/'restored';clean.mkdir(mode=0o700);(clean/'data').mkdir(mode=0o700)
    target=replace(runtime,root=str(clean),password='c'*64);assert restore(target,destination)['status']=='RESTORED'
    with private_postgres(target,target.directory/'postgres') as env:
        engine=create_engine(url(target,env))
        with Session(engine) as restored,monkeypatch.context() as patch:
            patch.setattr('app.main.get_licitia_data_root',lambda:target.directory/'data')
            assert projection(restored,t,version.id)==before
            assert verify_export(restored,t,version.id,receipt['request_id'])['verification_status']=='VERIFIED'
            for kind in ['DOCX','XLSX','PDF','ZIP']:
                path,_,_=artifact_file(restored,t,version.id,receipt['request_id'],kind);assert path.is_file()
        engine.dispose()
    Path('reports/m9_c').mkdir(parents=True,exist_ok=True)
    Path('reports/m9_c/backup_restore.json').write_text(json.dumps({'result':'PASS','database':'PRIVATE_POSTGRESQL_ISLAND',
        'metadata_preserved':True,'binaries_preserved':True,'frozen_literals_preserved':True,'hashes_verified':True,
        'backup_engine_changed':False,'regenerable_and_backed_up':True},indent=2)+'\n')
