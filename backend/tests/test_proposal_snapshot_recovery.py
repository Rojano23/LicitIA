"""M8D-20 real private PostgreSQL backup/restore of a product snapshot island."""
from dataclasses import replace
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.models import Tender,ProposalReadinessSnapshot
from app.proposal_readiness import get_snapshot
from app.local_deployment import REPOSITORY
from app.local_recovery import private_postgres,_run,backup,restore,verify_backup
from tests.test_local_recovery import runtime
from tests.test_proposal_readiness import proposal_connection,create
from tests.test_bid_readiness import complete
from tests.test_workspace_flow import scene


def test_m8d20_snapshot_survives_real_backup_restore(complete,runtime,tmp_path):
    c,t,db,m=complete;result,_=create(c,t);payload=result['payload'];identity=payload['snapshot_id']
    row=db.get(ProposalReadinessSnapshot,identity)
    saved={col.name:getattr(row,col.name) for col in ProposalReadinessSnapshot.__table__.columns}
    cluster=runtime.directory/'postgres';password=runtime.directory/'password.tmp'
    password.write_text(runtime.password)
    try:_run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile',password,'--encoding=UTF8','--locale=C'])
    finally:password.unlink()
    def url(config,env):return URL.create('postgresql+psycopg',username='licitia',password=config.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']})
    with private_postgres(runtime,cluster) as env:
        _run(['createdb','licitia_uat'],env)
        migration_env={**env,'DATABASE_URL':f"postgresql+psycopg://licitia:{runtime.password}@/licitia_uat?host={env['PGHOST']}&port={env['PGPORT']}"}
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration_env)
        engine=create_engine(url(runtime,env))
        with Session(engine) as isolated:
            isolated.add(Tender(id=t,title=payload['projection']['tender_title']));isolated.flush()
            isolated.add(ProposalReadinessSnapshot(**saved));isolated.commit()
        engine.dispose()
    destination=tmp_path/'snapshot-backup'
    assert backup(runtime,destination)['status']=='VERIFIED'
    assert verify_backup(destination)
    clean=tmp_path/'restored';clean.mkdir(mode=0o700);(clean/'data').mkdir(mode=0o700)
    target=replace(runtime,root=str(clean),password='c'*64)
    assert restore(target,destination)['status']=='RESTORED'
    with private_postgres(target,target.directory/'postgres') as env:
        engine=create_engine(url(target,env))
        with Session(engine) as restored:
            assert get_snapshot(restored,t,identity).model_dump(mode='json')==result
        engine.dispose()
    # Source domains intentionally absent in this island: handoff reads stored verified payload.
    # Full originals/provenance recovery is separately covered by canonical RC-H3 regression.
    Path('reports/m8_d/backup_restore.json').write_text(json.dumps({'result':'PASS','kind':'REAL_PRIVATE_POSTGRES_SNAPSHOT_ISLAND','payload_hash':result['payload_sha256'],'scope_rows':len(payload['projection']['rows']),'source_recomputation':False,'backup_engine_changed':False},indent=2)+'\n')
