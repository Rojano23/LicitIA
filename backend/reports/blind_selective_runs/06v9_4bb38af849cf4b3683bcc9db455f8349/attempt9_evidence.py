exec(open('/private/tmp/attempt9_ops.py').read().split("if sys.argv[1]=='init':")[0])
c=json.loads(C.read_text());p=Path(c['directory']);boot=Path(c['bootstrap_directory']);data=Path(c['data_dir'])
from app.blind_environment import establish_environment
establish_environment(database_url=c['database_url'],data_dir=data)
from app.database import SessionLocal
from app.blind_selective_freeze import read_evidence,verify_execution_identity
from app.blind_selective_profile import SelectiveProfile
from app.structured_evidence_grounding import validate_manifest
from app.blind_schema_drift import observe_schema_drift,verify_accepted_drift
profile=SelectiveProfile.model_validate_json((boot/'execution_profile.json').read_bytes());f=read_evidence(p/'first_pass.json');frozen=json.loads((p/'FROZEN.json').read_bytes());assert frozen['first_pass_sha256']==sha(p/'first_pass.json')
assert not (p/'BLOCKED.json').exists()
# Seal all original derived artifacts before replay or reporting. No semantic excerpts emitted.
write(p/'first_pass_artifact_manifest.json',{str(x.relative_to(data)):sha(x) for x in data.rglob('*') if x.is_file()})
manifest_files=list((data/'provenance'/'structured-evidence-v1').rglob('*.json'));print('manifests found',len(manifest_files))
blocks=[];verified=[]
with SessionLocal() as db:
 from sqlalchemy import text,select
 db.execute(text('SET TRANSACTION READ ONLY'))
 verify_execution_identity(p,R,profile,db=db)
 for path in manifest_files:
  m=validate_manifest(db,path.stem);blocks.extend(m.blocks);verified.append(dict(path=str(path),sha256=sha(path),blocks=len(m.blocks)))
 from app.models import TenderDocument,TenderScopeDetail,TenderScopeQuantity,TenderScopeAttribute
 docs=db.scalars(select(TenderDocument)).all()
 statuses={}
 for d in docs:
  key=str(getattr(d,'preparation_status',getattr(d,'status','NOT_DIRECTLY_MEASURABLE')));statuses[key]=statuses.get(key,0)+1
 write(p/'post_run_schema.json',verify_accepted_drift(observe_schema_drift(db)))
proofs=[b.native_table_proof for b in blocks if b.native_table_proof is not None and b.native_table_proof.version=='CAMELOT_NATIVE_TABLE_001']
unique_proposals={x.proposal.proposal_sha256:x.proposal for x in proofs}
unique_words={(b.source.page_id,w.start,w.end) for b in blocks if b.native_table_proof in proofs for cell in b.native_table_proof.cells for w in cell.words}
from collections import Counter
relations=Counter(r.kind for b in blocks for r in b.relations)
metrics=dict(blocks=len(blocks),table_derived_blocks=len(proofs),positive_item_identities=len(blocks),manifest_count=len(manifest_files),manifests_verified=len(verified),manifest_missing=0,hash_failures=0,proof_verification_failures=0,proof_artifacts=len(proofs),tables_accepted_with_native_proof=len(unique_proposals),accepted_table_cells=sum(len(x.cells) for x in unique_proposals.values()),unique_native_words_proved=len(unique_words),literal_fragments=sum(len(b.fragments) for b in blocks),relations=dict(relations),multiline_blocks=sum(any(r.kind=='CONTINUES' for r in b.relations) for b in blocks),document_statuses=statuses)
for k in ['eligible_pdf_pages','camelot_pages_evaluated','tables_proposed','tables_rejected','ambiguous_tables','cells_proposed','ambiguous_fragment_ownership','rejected_fragment_relationships','ambiguous_rejected_blocks','scope_candidates_created','grounded_candidates','grounding_rejected','reconciled_scope','provisional_quantities','parent_resolved_quantities','rejected_ambiguous_quantity_ownership','provisional_attributes','rejected_unresolved_attributes']:
 metrics[k]='NOT_DIRECTLY_MEASURABLE'
write(p/'structural_metrics.json',metrics);write(p/'manifest_verification.json',verified)
# Sleep/Wake events are filtered by execution timestamps; assertions containing Sleep are not suspension events.
start=json.loads((p/'EXECUTION_STARTED.json').read_text())['started_at'];end=f['ended_at']
from datetime import datetime,timezone
lo=datetime.fromisoformat(start);hi=datetime.fromisoformat(end)
log=(p/'sleep_log_end.txt').read_text();events=[]
import re
for line in log.splitlines():
 match=re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4})\s+(Sleep|Wake|DarkWake)\s',line)
 if match:
  t=datetime.strptime(match[1],'%Y-%m-%d %H:%M:%S %z')
  if lo<=t<=hi:events.append(line)
assert not events,'HOST SUSPENSION'
write(p/'host_awake_verification.json',dict(mechanism='caffeinate -ims',pid=52678,execution_start=start,execution_end=end,suspension_events_during_entire_execution=events,provider_intervals_covered_by_whole_run=True,actual_per_call_start_end='NOT_DIRECTLY_MEASURABLE; provider wall durations recorded, entire execution interval has no sleep events'))
old=json.loads((boot/'historical_integrity_baseline.json').read_text());bad=[k for k,v in old.items() if not Path(k).exists() or sha(k)!=v];assert not bad
write(p/'historical_integrity.json',dict(files_verified=len(old),mismatches=bad))
print(json.dumps(metrics));print('first-pass',sha(p/'first_pass.json'));print('no suspension events; history intact')
