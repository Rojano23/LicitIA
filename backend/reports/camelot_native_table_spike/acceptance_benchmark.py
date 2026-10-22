"""Authorized known-page acceptance; no blind run or historical mutation."""
import json,os,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent;BACKEND=BASE.parents[1]
DATA=BASE/'acceptance_data';DATA.mkdir(exist_ok=False)
os.environ.update(DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test',LICITIA_DATA_DIR=str(DATA),LICITIA_LOCAL_AI_ENABLED='false')
from app.database import SessionLocal
from app.main import app
from app.models import Tender,DocumentPage,TenderScopeDetail,TenderScopeQuantity,TenderScopeAttribute
from app.scope_detail_materializer import materialize_document_scope_details
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from app.structured_evidence_grounding import resolve_payload,validate_manifest,source_text,_reconstruct_for_materialization
from app.structured_evidence_storage import digest_from_locator,manifest_path
from app.camelot_table_adapter import dependency_identity
from app.camelot_table_contract import CONFIG,CONFIG_SHA256,POLICY_VERSION
from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
from fastapi.testclient import TestClient
from sqlalchemy import select,delete
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=['app/camelot_table_contract.py','app/camelot_table_adapter.py','app/camelot_table_worker.py','app/native_table_relationships.py','app/structured_evidence.py','app/structured_evidence_grounding.py','app/blind_selective_freeze.py','requirements.txt','pyproject.toml']
seal={'source_hashes':{f:sha(BACKEND/f) for f in files},'configuration':CONFIG,'config_sha256':CONFIG_SHA256,'proof_policy':POLICY_VERSION,'dependencies':dependency_identity(),'generic_validation':'ct_rt_verified.xml:54passed','no_tuning_after_acceptance':True}
with (BASE/'pre_acceptance_implementation_seal.json').open('x') as f:json.dump(seal,f,indent=2)
benchmark=BACKEND/'reports/table_tooling_benchmark';pages=json.loads((benchmark/'page_manifest.json').read_text())
client=TestClient(app);db=SessionLocal();created=[]
def prepare(path,title):
 r=client.post('/tenders',json={'title':title});assert r.status_code==201
 tid=r.json()['id'];created.append(tid)
 with path.open('rb') as f:r=client.post(f'/tenders/{tid}/documents/import',files=[('files',(path.name,f,'application/pdf'))])
 assert r.status_code==200,r.text
 did=r.json()[0]['document_id']
 for action in ['extract-pages','normalize']:
  r=client.post(f'/tenders/{tid}/documents/{did}/{action}');assert r.status_code==200,r.text
 return tid,did
try:
 b1=next(x for x in pages if x['key']=='B1_P1');path=Path(b1['original_path']);assert sha(path)==b1['document_sha256']
 tid,did=prepare(path,'Known B1 acceptance, not blind')
 result=materialize_document_scope_details(db,tender_id=tid,document_id=did)
 assert not any(x.errors for x in result.artifact_results),result
 details=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==did).order_by(TenderScopeDetail.candidate_item_key)).all()
 records=[];words=set()
 for detail in details:
  a=materialize_scope_attributes_for_scope_detail(db,scope_detail_id=detail.id);q=materialize_scope_quantities_for_scope_detail(db,scope_detail_id=detail.id);assert not a.errors and not q.errors
  block=resolve_payload(db,detail)['structured_block'];proof=block.native_table_proof
  for cell in proof.cells:
   for w in cell.words:words.add((w.start,w.end,w.bbox))
  qs=db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id==detail.id)).all();attrs=db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id==detail.id)).all()
  dg=digest_from_locator(detail.source_locator);validate_manifest(db,dg)
  records.append({'item':block.item_raw,'scope_id':detail.id,'description':block.field('description').value,'quantities':[{'quantity':str(x.quantity_value),'unit':x.unit_raw,'scope_detail_id':x.scope_detail_id} for x in qs],'attributes':[{'name':x.attribute_name,'value':x.value_raw} for x in attrs],'manifest_sha256':dg,'manifest_file_sha256':sha(manifest_path(dg)),'review_required':detail.review_required,'confidence':detail.confidence,'proof':proof.model_dump(mode='json'),'fragments':[f.model_dump(mode='json') for f in block.fragments]})
 out={'basis':'AUTHORIZED_KNOWN_ACCEPTANCE_NOT_BLIND','production_configuration':CONFIG,'source_sha256':b1['document_sha256'],'candidate_count':result.candidate_count,'persisted_scope':len(details),'unique_native_words_proved':len(words),'records':records,'attributes_note':'No inference from part numbers or manufacturer labels inside description.'}
 (BASE/'b1_acceptance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 assert len(details)==2 and [x['item'] for x in records]==['1','2']
 assert [float(x['quantities'][0]['quantity']) for x in records]==[1,2] and all(x['quantities'][0]['unit']=='PZA' for x in records)
 assert 'F60' in records[0]['description'] and 'L90' in records[1]['description'] and len(words)==37
 secondary=[]
 for key in ['B1_P2','BASES_P41','QUESTION_P12','ANEXOC_P1']:
  meta=next(x for x in pages if x['key']==key);stid,sdid=prepare(benchmark/'pages'/f'{key}.pdf','Known secondary page, no semantic persistence');db.rollback()
  ps=db.scalars(select(DocumentPage).where(DocumentPage.document_id==sdid)).all();enum=_enumerate_persisted_artifacts_for_document(db,tender_id=stid,document_id=sdid,pages=ps);blocks=[]
  for entry in enum.active:
   if entry.artifact.source_method!='NATIVE':continue
   source,text=source_text(db,entry.artifact);blocks.extend(_reconstruct_for_materialization(db,entry.artifact,source,text))
  secondary.append({'page':key,'blocks':len(blocks),'semantic_objects_materialized':False,'inherits_b1_truth':False,'original_document_sha256':meta['document_sha256'],'benchmark_page_copy_sha256':sha(benchmark/'pages'/f'{key}.pdf')});assert not blocks,key
 (BASE/'secondary_acceptance.json').write_text(json.dumps(secondary,indent=2))
 assert all(sha(BACKEND/f)==h for f,h in seal['source_hashes'].items())
 print('B1 PASS: scopes2, quantities2, attributes',sum(len(x['attributes']) for x in records),'Native words37/37; secondary4 safe.',flush=True)
finally:
 db.rollback()
 for tid in created:db.execute(delete(Tender).where(Tender.id==tid))
 db.commit();db.close()
