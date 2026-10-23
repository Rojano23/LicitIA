"""M9A-18 private PostgreSQL proposal/version/audit restore, synthetic snapshot island."""
from dataclasses import replace
import json,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.models import Tender,ProposalReadinessSnapshot
from app.proposal_versions import create_version,freeze_version,read_version,version_history,CreateProposal,FreezeProposal
from app.local_deployment import REPOSITORY
from app.local_recovery import private_postgres,_run,backup,restore
from tests.test_local_recovery import runtime
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection
from tests.test_proposal_versions import ready


def test_m9a18_real_proposal_backup_restore(ready,runtime,tmp_path):
    c,t,db,m,snapshot=ready
    from tests.test_proposal_versions import create
    from tests.test_proposal_composition import init
    from app.models import ProposalComposition
    source_version,_=create(c,t,snapshot);init(c,t,source_version)
    from copy import deepcopy
    captured=deepcopy(db.get(ProposalComposition,source_version['id']).content)
    stored=db.get(ProposalReadinessSnapshot,snapshot['payload']['snapshot_id'])
    values={col.name:getattr(stored,col.name) for col in ProposalReadinessSnapshot.__table__.columns}
    cluster=runtime.directory/'postgres';password=runtime.directory/'password.tmp';password.write_text(runtime.password)
    try:_run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile',password,'--encoding=UTF8','--locale=C'])
    finally:password.unlink()
    def url(config,env):return URL.create('postgresql+psycopg',username='licitia',password=config.password,database='licitia_uat',query={'host':env['PGHOST'],'port':env['PGPORT']})
    with private_postgres(runtime,cluster) as env:
        _run(['createdb','licitia_uat'],env)
        migration_env={**env,'DATABASE_URL':f"postgresql+psycopg://licitia:{runtime.password}@/licitia_uat?host={env['PGHOST']}&port={env['PGPORT']}"}
        _run([sys.executable,'-m','alembic','-c',REPOSITORY/'backend/alembic.ini','upgrade','head'],migration_env)
        engine=create_engine(url(runtime,env),isolation_level='REPEATABLE READ')
        with Session(engine,autoflush=False) as isolated:
            isolated.add(Tender(id=t,title='Synthetic proposal restore'));isolated.flush()
            isolated.add(ProposalReadinessSnapshot(**values));isolated.flush()
            value=create_version(isolated,t,CreateProposal(request_id=uuid4(),snapshot_id=stored.id,acknowledge_warnings=True,acknowledge_stale=True,configuration={'title':'Configuración preservada'}))
            from app.proposal_composition import initialize,change_responses,projection,Initialize,ChangeResponses
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc)
            isolated.add(ProposalComposition(version_id=value.id,contract_version='proposal-composition-v1',revision=1,
                content=captured,created_at=now,updated_at=now));isolated.flush()
            composition=initialize(isolated,t,value.id,Initialize())
            for row in composition['rows']:
                if row['section']=='REQUIREMENTS':response={'status':'COMPLY','text':'Synthetic human response'}
                elif row['section']=='REQUESTED_EVIDENCE':response={'status':'PROVIDED','external_reference':'Local evidence'}
                elif row['section']=='TECHNICAL_SCOPE':response={'offered_description':'Human technical wording'}
                else:response={'note':'Human economic note; canonical prices unchanged'}
                composition=change_responses(isolated,t,value.id,ChangeResponses(expected_revision=composition['revision'],changes=[{'key':row['key'],'response':response}]))
            from app.proposal_composition import change_settings,ChangeSettings
            composition=change_settings(isolated,t,value.id,ChangeSettings(expected_revision=composition['revision'],items=[
                {'id':str(uuid4()),'kind':'CLARIFICATION','text':'Human clarification preserved'},
                {'id':str(uuid4()),'kind':'ANNEX_REFERENCE','text':'Frozen document reference','document_id':snapshot['payload']['projection']['documents'][0]['id']}]))
            composition_before=projection(isolated,t,value.id)
            frozen=freeze_version(isolated,t,value.id,FreezeProposal(expected_edit_revision=1,expected_composition_revision=composition['revision'],acknowledge_warnings=True,acknowledge_stale=True))
            before=frozen.model_dump(mode='json');audit=version_history(isolated,t,value.id);isolated.commit()
        engine.dispose()
    destination=tmp_path/'proposal-backup';assert backup(runtime,destination)['status']=='VERIFIED'
    clean=tmp_path/'restored';clean.mkdir(mode=0o700);(clean/'data').mkdir(mode=0o700)
    target=replace(runtime,root=str(clean),password='c'*64);assert restore(target,destination)['status']=='RESTORED'
    with private_postgres(target,target.directory/'postgres') as env:
        engine=create_engine(url(target,env))
        with Session(engine) as restored:
            assert read_version(restored,t,value.id).model_dump(mode='json')==before
            assert version_history(restored,t,value.id)==audit
            assert projection(restored,t,value.id)==composition_before
        engine.dispose()
    Path('reports/m9_b').mkdir(parents=True,exist_ok=True)
    Path('reports/m9_b/backup_restore.json').write_text(json.dumps({'result':'PASS','kind':'REAL_PRIVATE_POSTGRES_PROPOSAL_ISLAND','snapshot_id':stored.id,'frozen_hash':before['frozen_sha256'],'configuration_preserved':True,'audit_preserved':True,'composition_responses_preserved':True,'source_state_at_creation':'STALE_ACKNOWLEDGED','backup_engine_changed':False},indent=2)+'\n')
