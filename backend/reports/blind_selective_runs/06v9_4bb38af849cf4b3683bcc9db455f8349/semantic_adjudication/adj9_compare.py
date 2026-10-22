from pathlib import Path
import json,collections
base=Path('/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs');p=base/'06v9_4bb38af849cf4b3683bcc9db455f8349';a=p/'semantic_adjudication';old=base/'06v7_eee8df9b4a1f44428531dbae0c236a1d'
def read(p):return json.loads(p.read_bytes())
s9=read(p/'first_pass.json')['payload']['snapshot'];s7=read(old/'first_pass.json')['payload']['snapshot'];jud=read(old/'semantic_adjudication/semantic_adjudication.json')
def indexed(s,domain):
 docs={r['id']:r['provenance']['persisted_record']['sha256'] for r in s['records'] if r['domain']=='DOCUMENTS'};cands={x['candidate']['id']:x['candidate'] for x in s['discovery_records']};out={}
 for r in s['records']:
  if r['domain']!=domain:continue
  v=r['provenance']['persisted_record']
  if domain=='REQUIREMENTS':
   c=cands[v['primary_candidate_id']];key=(docs[c['source_document_id']],c['source_page'],v['canonical_text'],v['category'],c['requirement_text'],c['source_excerpt'])
  else:key=(docs[v['source_document_id']],v['source_page'],v['evidence_type'],v['evidence_description'],v['source_excerpt'])
  assert key not in out;out[key]=r
 return out
ledger={}
for domain,labels in [('REQUIREMENTS',jud['requirements']),('REQUESTED_EVIDENCE',jud['requested_evidence'])]:
 x=indexed(s9,domain);y=indexed(s7,domain);mapping={v['current_id']:v for v in labels};entries=[]
 for key,r in x.items():
  match=y.get(key)
  entries.append(dict(current_id=r['id'],attempt7_id=match['id'] if match else None,exact_semantic_source_match=match is not None,canonical_comparison_fields=key,prior_judgment=mapping.get(match['id']) if match else None,current_state=r['state']))
 ledger[domain]=entries
 print(domain,'exact',sum(e['exact_semantic_source_match'] for e in entries),'of',len(entries))
 if any(not e['exact_semantic_source_match'] for e in entries):
  for k,r in x.items():
   if k not in y:
    print('CHANGED',json.dumps(k,ensure_ascii=False));print('near',[json.dumps(j,ensure_ascii=False) for j in y if j[2].casefold()==k[2].casefold()][:1])
(a/'comparison_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
