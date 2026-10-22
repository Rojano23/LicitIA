from pathlib import Path
import json,hashlib,sys,collections
R=Path('/Users/ceciliavalencia/LiticIA');sys.path.insert(0,str(R/'backend'));P=R/'backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349';A=P/'semantic_adjudication'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
from app.structured_evidence import StructuredEvidenceManifest
from app.camelot_table_contract import check_digest,digest
from app.camelot_table_adapter import match_cells,_prove_row,dependency_identity
from app.native_table_relationships import _words_with_offsets
from app.content_normalization import _normalize_text
import pymupdf
f=read(P/'first_pass.json')['payload'];s=f['snapshot'];records=s['records'];locs=read(P/'original_locators.json');out=[]
for rec in read(P/'manifest_verification.json'):
 path=Path(rec['path']);assert sha(path)==path.stem
 manifest=StructuredEvidenceManifest.model_validate_json(path.read_bytes());block=manifest.blocks[0];proof=block.native_table_proof;check_digest(proof,'proof_sha256');check_digest(proof.proposal,'proposal_sha256');assert proof.proposal.source_identity_sha256==digest(block.source.model_dump(mode='json'))
 src=block.source;original=Path(next(x['path'] for x in locs if x['document_id']==src.document_id));assert sha(original)==src.original_sha256
 with pymupdf.open(original) as pdf:
  page=pdf[src.page_number-1];text=_normalize_text(page.get_text('text'));words=_words_with_offsets(page,text)
 assert hashlib.sha256(text.encode()).hexdigest()==src.text_sha256
 canonical=[e for p in s['perception'] for e in p['sources'] if e.get('source_artifact_key')==src.artifact_key and e.get('source_method')=='NATIVE']
 assert canonical and any(e.get('normalized_content_id')==src.generation_id and e.get('text')==text for e in canonical)
 assert all(text[g.start:g.end]==g.text for g in block.fragments)
 matches=match_cells(proof.proposal,words,text);assert matches is not None
 roles=[c.role for c in sorted((c for c in proof.cells if c.header),key=lambda c:c.column)]
 replay=_prove_row(src,text,proof.proposal,matches,roles,proof.row_index,block.occurrence,dependency_identity());assert replay==block
 scope=next(r for r in records if r['domain']=='SCOPE' and path.stem in r['provenance']['source_locator']);q=next(r for r in records if r['domain']=='QUANTITIES' and r['parent_id']==scope['id']);pr=scope['provenance']['persisted_record'];qr=q['provenance']['persisted_record'];item=block.item_raw
 assert item==pr['candidate_item_key'] and pr['description']==block.field('description').value
 assert str(int(float(qr['quantity_value'])))==item==block.field('quantity').value and qr['unit_raw']==block.field('unit').value=='PZA'
 assert pr['confidence'] is None and pr['review_required'] and qr['review_required']
 assert ('F60-' if item=='1' else 'L90-') in pr['description'] and ('L90-' if item=='1' else 'F60-') not in pr['description']
 out.append(dict(item=item,scope_id=scope['id'],quantity_id=q['id'],parent_id=q['parent_id'],source=src.model_dump(mode='json'),description=pr['description'],description_refs=list(block.field('description').refs),quantity=qr['quantity_value'],unit=qr['unit_raw'],manifest_sha256=path.stem,proof_sha256=proof.proof_sha256,proposal_sha256=proof.proposal.proposal_sha256,row_index=proof.row_index,canonical_fragments=[x.model_dump(mode='json') for x in block.fragments],proof_cells=[x.model_dump(mode='json') for x in proof.cells],checks=dict(literal_fidelity=True,unique_cell_membership=True,source_generation=True,pure_proof_replay=True,no_cross_row_contamination=True,appropriate_review_trust=True),semantic_verdict='PASS_AGAINST_ACCEPTED_B1_REFERENCE'))
(A/'individual_scope_quantity_adjudication.json').write_text(json.dumps(sorted(out,key=lambda x:x['item']),ensure_ascii=False,indent=2)+'\n');print('BOTH NATIVE PROOFS + SCOPE + QUANTITY PASS; pure replay only, no parser/provider')
# Safety cases and raw Vision structural payloads, no inference.
vision=[];safety=[]
for r in records:
 if r['domain']!='STRUCTURE':continue
 pr=r['provenance'];page=pr['persisted_record']['page_number'];doc=next(d['provenance']['persisted_record'] for d in records if d['domain']=='DOCUMENTS' and d['id']==r['document_id'])
 if (page==13 and 'Bases' in doc['original_filename']) or (page==12 and 'Cuestionario' in doc['original_filename']):
  safety.append(dict(filename=doc['original_filename'],page=page,state=r['state'],continuity=pr['continuity']))
 for source in pr['routing']['candidates']:
  if source.get('source_method')=='VISION':vision.append(dict(filename=doc['original_filename'],page=page,state=r['state'],structural_state=source.get('structural_state')))
(A/'structural_safety_review.json').write_text(json.dumps(dict(trusted_structures=sum(r['state']=='TRUSTED' for r in records if r['domain']=='STRUCTURE'),historical_cases=safety,vision_raw=vision),ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(safety=safety,vision=vision),ensure_ascii=False)[:4500])
