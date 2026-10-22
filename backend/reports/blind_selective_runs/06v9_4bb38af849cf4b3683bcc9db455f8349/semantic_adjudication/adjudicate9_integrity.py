from pathlib import Path
import json,hashlib,subprocess
R=Path('/Users/ceciliavalencia/LiticIA');B=R/'backend';P=B/'reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349';A=P/'semantic_adjudication';D=B/'.licitia-data-validation-06v9_4bb38af849cf4b3683bcc9db455f8349'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
assert sha(P/'first_pass.json')=='8972172fd0c9c14ff2e20ba4e13e9c438bfee13d3fc8c5182af723c11972c1b6'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='14097f428e2185152aae1b671485244f1656fb07'
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).strip()
for k in ['pre_execution.json','input_binding.json','first_pass.json']:
 from sys import path
 path.insert(0,str(B))
 from app.document_intelligence_blind_run import canonical_bytes,sha256
 x=read(P/k);assert x['sha256']==sha256(canonical_bytes(x['payload']))
assert read(P/'FROZEN.json')['first_pass_sha256']==sha(P/'first_pass.json')
for rel,h in read(P/'operational_artifact_manifest.json').items():assert sha(P/rel)==h,rel
for rel,h in read(P/'first_pass_artifact_manifest.json').items():assert sha(D/rel)==h,rel
hist=read(B/'reports/camelot_native_table_spike/historical_baseline.json');assert all(sha(k)==v for k,v in hist.items())
A.mkdir(exist_ok=False)
manifest={str(p):sha(p) for root in [P,D] for p in root.rglob('*') if p.is_file() and not p.is_relative_to(A)}
(A/'preservation_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(A/'integrity_verification.json').write_text(json.dumps({'status':'PASS','operational_artifacts_verified':len(read(P/'operational_artifact_manifest.json')),'historical_files_verified':len(hist),'first_pass_sha256':sha(P/'first_pass.json'),'pre_freeze_sha256':sha(P/'pre_execution.json'),'binding_sha256':sha(P/'input_binding.json'),'head':'14097f428e2185152aae1b671485244f1656fb07'},indent=2)+'\n')
print('INTEGRITY PASS',len(manifest))
