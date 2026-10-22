from pathlib import Path
import os,sys,json,hashlib,subprocess,uuid,datetime,urllib.request,mimetypes
R=Path('/Users/ceciliavalencia/LiticIA');B=R/'backend';sys.path.insert(0,str(B));os.chdir(B)
C=Path('/private/tmp/licitia_attempt9_context.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def providers():
 with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=10) as f:version=json.load(f)['version']
 with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as f:models=json.load(f)['models']
 m=next(m for m in models if m['name']=='qwen3-vl:4b-instruct');assert version=='0.23.3' and m['digest']=='ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b'
 return dict(version=version,model=m['name'],digest=m['digest'],inference_calls=0)
if sys.argv[1]=='init':
 import importlib.metadata
 assert importlib.metadata.version('camelot-py')=='2.0.0'
 from app.camelot_table_contract import CONFIG,POLICY_VERSION
 assert CONFIG['flavor']=='lattice' and CONFIG['engine']=='combined' and POLICY_VERSION=='camelot-native-table-proof-v1'
 p=providers();assert subprocess.check_output(['/opt/homebrew/bin/tesseract','--version'],text=True).splitlines()[0]=='tesseract 5.5.3'
 langs=subprocess.check_output(['/opt/homebrew/bin/tesseract','--list-langs'],text=True);assert 'spa\n' in langs and 'eng\n' in langs and '/opt/homebrew/share/tessdata/' in langs
 awake=subprocess.check_output(['pmset','-g','assertions'],text=True);assert 'caffeinate command-line tool' in awake and 'PreventUserIdleSystemSleep' in awake
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='14097f428e2185152aae1b671485244f1656fb07'
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).strip()
 run='06v9_'+uuid.uuid4().hex;out=B/'reports/blind_selective_runs';boot=out/(run+'_bootstrap');boot.mkdir();data=B/('.licitia-data-validation-'+run);data.mkdir()
 context=dict(run_id=run,data_dir=str(data),directory=str(out/run),bootstrap_directory=str(boot),head='14097f428e2185152aae1b671485244f1656fb07',database_url='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v',source_root='/Users/ceciliavalencia/Documents/LicitIA/Reelevadores Elecricos')
 write(C,context);write(boot/'operational_context.json',context);write(boot/'provider_readiness.json',p);(boot/'sleep_assertions_start.txt').write_text(awake)
 (boot/'sleep_log_start.txt').write_text(subprocess.check_output(['pmset','-g','log'],text=True))
 old=json.loads((B/'reports/camelot_native_table_spike/historical_baseline.json').read_text());assert all(Path(k).is_file() and sha(k)==v for k,v in old.items());write(boot/'historical_integrity_baseline.json',old)
 profile=json.loads((B/'reports/blind_selective_runs/06v8_eaca60f950044a40a7e28cdd3e01fa86_bootstrap/execution_profile.json').read_text());write(boot/'execution_profile.json',profile)
 print(json.dumps(context));sys.exit()
c=json.loads(C.read_text());boot=Path(c['bootstrap_directory']);directory=Path(c['directory']);data=Path(c['data_dir'])
from app.blind_environment import establish_environment
establish_environment(database_url=c['database_url'],data_dir=data)
from app.blind_selective_profile import SelectiveProfile
from app.blind_selective_freeze import runtime_preflight,create_pre_execution_freeze,bind_import,verify_execution_identity,input_identity,execute_frozen_run,read_evidence
from app.blind_schema_drift import observe_schema_drift,verify_accepted_drift
from app.database import SessionLocal,engine
from app.document_intelligence_validation_metrics import database_identity
profile=SelectiveProfile.model_validate_json((boot/'execution_profile.json').read_bytes())
def identity():
 with SessionLocal() as db:return dict(database=database_identity(db),drift=verify_accepted_drift(observe_schema_drift(db)))
if sys.argv[1]=='preflight':
 write(boot/'preflight_operational.json',dict(identity=identity(),runtime=runtime_preflight(profile),providers=providers()));print('PREFLIGHT PASS')
elif sys.argv[1]=='reset':
 before=identity();write(boot/'pre_reset_identity.json',before);engine.dispose()
 dump=boot/'pre_reset_database.dump';subprocess.run(['pg_dump','-h','localhost','-U','ceciliavalencia','-Fc','-f',str(dump),'licitia_validation_06v'],check=True)
 write(boot/'pre_reset_export_identity.json',dict(path=str(dump),sha256=sha(dump)))
 subprocess.run(['dropdb','-h','localhost','-U','ceciliavalencia','licitia_validation_06v'],check=True)
 subprocess.run(['createdb','-h','localhost','-U','ceciliavalencia','licitia_validation_06v'],check=True)
 with (boot/'reset_alembic.log').open('x') as f:subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True,stdout=f,stderr=subprocess.STDOUT)
 after=identity();assert after['database']['tender_count']==after['database']['document_count']==0;write(boot/'post_reset_identity.json',after)
 with SessionLocal() as db:create_pre_execution_freeze(db,root=R,output_root=directory.parent,run_id=c['run_id'],profile=profile,availability=runtime_preflight(profile))
 read_evidence(directory/'pre_execution.json');write(boot/'pre_freeze_identity.json',dict(path=str(directory/'pre_execution.json'),sha256=sha(directory/'pre_execution.json'),profile_sha256=sha(boot/'execution_profile.json')));print('RESET AND FREEZE PASS')
elif sys.argv[1]=='import':
 from fastapi.testclient import TestClient
 from app.main import app,_resolve_document_file_path
 from app.models import TenderDocument
 from sqlalchemy import select
 baseline=read_evidence(B/'reports/blind_selective_runs/06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba/input_binding.json')['input']['documents']
 expected=sorted((d['original_filename'],d['sha256'],d['size'],d['mime']) for d in baseline)
 paths=sorted(p for p in Path(c['source_root']).rglob('*') if p.is_file());assert len(paths)==11
 with TestClient(app) as client:
  resp=client.post('/tenders',json={'title':'Blind Tender 002 Attempt 9'});assert resp.status_code==201;tid=resp.json()['id'];responses=[]
  for p in paths:
   mime=next(d['mime'] for d in baseline if d['original_filename']==p.name)
   with p.open('rb') as f:r=client.post(f'/tenders/{tid}/documents/import',files=[('files',(p.name,f,mime))])
   assert r.status_code in (200,201),r.status_code;responses.append(r.json())
 write(directory/'import_receipts.json',responses)
 with SessionLocal() as db:
  docs=db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tid)).all();actual=sorted((d.original_filename,d.sha256,d.file_size_bytes,d.mime_type) for d in docs)
  inside=all(_resolve_document_file_path(d.stored_relative_path).resolve().is_relative_to(data) for d in docs)
  exact=actual==expected and len(docs)==11 and inside and any(d.original_filename=='.DS_Store' for d in docs)
  write(directory/'corpus_completeness_gate.json',dict(status='PASS' if exact else 'FAIL',expected=11,imported_count=len(docs),exact_identity_match=actual==expected,all_originals_inside_root=inside,hidden_original_present=any(d.original_filename=='.DS_Store' for d in docs),baseline='Attempt4 immutable input binding',binding_created_at_gate=False))
  assert exact,'CORPUS MISMATCH STOP'
  write(directory/'original_locators.json',[dict(document_id=d.id,filename=d.original_filename,path=str(_resolve_document_file_path(d.stored_relative_path))) for d in docs])
  bind_import(db,directory=directory,root=R,profile=profile,tender_id=tid)
 print('CORPUS AND BINDING PASS')
elif sys.argv[1]=='execute':
 providers();assert 'caffeinate command-line tool' in subprocess.check_output(['pmset','-g','assertions'],text=True)
 with SessionLocal() as db:
  frozen=verify_execution_identity(directory,R,profile,db=db);binding=read_evidence(directory/'input_binding.json');assert input_identity(db,tender_id=binding['input']['tender_id'])==binding['input']
  assert runtime_preflight(profile)==frozen['availability']
  write(directory/'final_integrity_gate.json',dict(status='PASS',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),pre_freeze_sha256=sha(directory/'pre_execution.json'),binding_sha256=sha(directory/'input_binding.json'),provider=providers(),sleep_prevention=True))
  print('FINAL GATE PASS',flush=True);print(execute_frozen_run(db,directory=directory,root=R,profile=profile,authorized=True),flush=True)
