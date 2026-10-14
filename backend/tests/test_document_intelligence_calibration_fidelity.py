"""HF contracts plus actual stored-batch offline replay; no inference or new truth."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine,select
from app.document_intelligence_calibration import Reference,EquipmentReference,SourceReferenceConflict,Observation,Capability,evaluate
from app.document_intelligence_calibration_fidelity import comparison,compare_equipment,transcription_fidelity
from app.document_intelligence_calibration_replay import read_batch,replay_batch,provider_guard
from scripts.run_document_intelligence_calibration import references,GOLDENS,main
from test_requirement_perception_provenance import logical

ROOT=Path(__file__).resolve().parents[1]
PATHS=[ROOT/'reports'/f for f in ['di_r4a_tesseract_b4_p4_transcription.json','di_r4a_vision_b4_p4_transcription.json','di_r4a_vision_b4_p1_p3_structure.json']]
TEST_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test'

@pytest.fixture(scope='module')
def batch():return read_batch(PATHS)
@pytest.fixture(scope='module')
def refs():return references([ROOT/'evals'/n for n in GOLDENS])
@pytest.fixture(scope='module')
def replay(batch,refs):return replay_batch(batch,TEST_URL,refs)


def ref(**kwargs):return Reference(identity='approved synthetic',file_sha256='x',human_label_status='APPROVED',**kwargs)

def obs(text='',**kwargs):return Observation(provider='NATIVE',document_id='synthetic',page_number=1,
    artifact_id='synthetic',capability=Capability.TRANSCRIPTION,routing_status='REVIEW_REQUIRED',text=text,**kwargs)


def test_HF01_line_wrap():assert comparison('UNA COPIA','UNA\nCOPIA')['kind']=='EXACT_FORMAT_DIFFERENCE'
def test_HF02_whitespace():assert not comparison('UNA COPIA','UNA   COPIA')['material']
def test_HF03_noise():assert comparison('MODELO: X100','MODELO: |\nX100',kind='IDENTIFIER_MISMATCH')['kind']=='OCR_NOISE'
def test_HF04_identifier():assert comparison('MODELO: X100','MODELO: X100A',kind='IDENTIFIER_MISMATCH')['material']

def rowref():return ref(equipment_rows=(EquipmentReference(identity='synthetic',source_excerpt='MÓDULO DE ENTRADAS, MARCA: A, MODELO: X100 (1 PIEZA)',model='X100',quantity='1',unit='PIEZA'),))
def test_HF05_numeric():assert any(f['kind']=='NUMERIC_MISMATCH' for f in compare_equipment('MÓDULO DE ENTRADAS, MARCA: A, MODELO: X100 (2 PIEZA)',rowref())['rows'][0]['findings'])
def test_HF06_unit():assert any(f['kind']=='UNIT_MISMATCH' for f in compare_equipment('MÓDULO DE ENTRADAS, MARCA: A, MODELO: X100 (1 SET)',rowref())['rows'][0]['findings'])
def test_HF07_prose():assert comparison('ENTREGAR REPORTE PROFESIONAL','equipos disponibles')['kind']=='MATERIAL_TEXT_OMISSION'

def conflict():return SourceReferenceConflict(golden_value='X100',source_reading='X10O',authority='Authorized unresolved human reading')
def test_HF08_conflict():
    result=comparison('X100','X10O',conflict=conflict());assert result['kind']=='REFERENCE_SOURCE_CONFLICT' and result['review_required']
def test_HF09_excluded():assert not comparison('X100','X10O',conflict=conflict())['scored']
def test_HF10_raw_diagnostic(batch,refs):
    o=next(o for o in batch if o.provider=='VISION' and o.page_number==4)
    result=transcription_fidelity(o,refs[(o.document_id,4)])
    assert result['raw_diagnostic']['equipment']['preserved_rows']==7 and not result['raw_diagnostic']['canonical']
def test_HF11_failed_not_canonical(batch):
    o=next(o for o in batch if o.provider=='VISION' and o.page_number==4).model_dump(mode='json');o['text']='rescued raw'
    with pytest.raises(ValidationError,match='FAILED Vision'):Observation.model_validate(o)
def test_HF12_zero_calls(replay):assert replay['provider_calls']==replay['blocked_provider_attempts']==0

def test_HF13_production_metadata(replay):
    vision=[s for p in replay['structure'] for s in p['candidates'] if s['source_method']=='VISION']
    assert len(vision)==3 and all(s['structural_state']['state_quality']=='VALID' for s in vision)
def test_HF14_not_invented(batch,replay):
    assert all('_continuity_state_quality' not in o.provenance['structured_json'] for o in batch if o.capability==Capability.STRUCTURE)
    assert replay['production_contexts'][1]['production_context'] is not None
    assert replay['production_contexts'][1]['original_inference_context'] is None

def test_HF15_unlabeled(batch):
    assert all(evaluate(o)['status']=='DIAGNOSTIC_ONLY' for o in batch if o.capability==Capability.STRUCTURE)
def test_HF16_diagnostic_not_label(batch,refs):
    assert all(evaluate(o,refs.get((o.document_id,o.page_number)))['status']=='DIAGNOSTIC_ONLY' for o in batch if o.capability==Capability.STRUCTURE)
def test_HF17_seven_rows(batch,refs):
    o=next(o for o in batch if o.provider=='TESSERACT');result=transcription_fidelity(o,refs[(o.document_id,4)])
    assert result['equipment']['preserved_rows']==result['equipment']['expected_rows']==7
    assert result['equipment']['quantity_matches']==result['equipment']['unit_matches']==7
    assert result['equipment']['reference_conflicts']==1

def test_HF18_isolated(batch,replay):
    assert replay['isolated_database']=='licitia_test' and replay['fixture_tender_id']!=batch[0].tender_id
    with pytest.raises(ValueError,match='licitia_test'):replay_batch(batch,TEST_URL.replace('licitia_test','licitia_dev'))
    from app.models import Tender
    from sqlalchemy.orm import Session
    engine=create_engine(TEST_URL)
    with Session(engine) as db:
        assert db.get(Tender,replay['fixture_tender_id']) is None
    engine.dispose()
def test_HF19_provenance(replay):
    p4=next(p for p in replay['perception'] if p['page']==4)
    source=next(s for s in p4['sources'] if s['source_method']=='OCR')
    assert source['page']['document_version']=='1' and source['source_artifact_key'].startswith('ocr-result:')
    assert source['generation_id'] and source['source_locator'] and source['normalized_content_id']
def test_HF20_review(replay):
    assert next(p for p in replay['perception'] if p['page']==4)['routing']=='REVIEW_REQUIRED'
    assert all(s['quality']!='RELIABLE' for p in replay['perception'] if p['page']==4 for s in p['sources'])
def test_HF21_stale(replay):assert replay['stale_carry_violations']==0

def test_HF22_quantity_no_cross(replay,logical):
    assert replay['scope']['persisted_count']==0 and replay['quantity_count']==0
    assert any(r['status']=='UNSUPPORTED' for r in replay['scope']['artifact_results'])
    from test_critical_identifier_propagation import children,STABLE
    details,quantities,_=children(logical)
    bad=next(d for d in details if d.source_excerpt!=STABLE)
    assert bad.candidate_item_key is None and next(q for q in quantities if q.scope_detail_id==bad.id).review_required
def test_HF23_attribute_no_cross(replay,logical):
    assert replay['attribute_count']==0
    from test_critical_identifier_propagation import children,STABLE
    details,_,attributes=children(logical)
    bad=next(d for d in details if d.source_excerpt!=STABLE)
    assert bad.candidate_item_key is None and next(a for a in attributes if a.scope_detail_id==bad.id).review_required

def test_HF24_idempotent(replay):assert replay['idempotent']
def test_HF25_unsafe_metric():
    assert evaluate(obs('MODELO: X100A',domain_input_trusted=True),ref(material_fragments=('MODELO: X100',)))['unsafe_trusted_contractual_errors']==1

def test_HF26_safe_miss_format():assert evaluate(obs('UNA\nCOPIA'),ref(material_fragments=('UNA COPIA',)))['safe_misses']==0

def test_HF27_safe_miss_conflict():
    r=evaluate(obs('MODELO: X10O'),ref(material_fragments=('MODELO: X100',),source_conflicts=(conflict(),)))
    assert r['safe_misses']==0 and r['fidelity_findings'][0]['kind']=='REFERENCE_SOURCE_CONFLICT'
def test_HF28_assessment(replay,batch):
    assert replay['domain_trust']['assessed']==2 and replay['domain_trust']['unassessed_structural_truth']==3
    assert replay_batch(batch,TEST_URL)['domain_trust']['assessed']==0

def test_HF29_tender002():
    with pytest.raises(ValidationError):obs(tender_id='other')
def test_HF30_offline_no_execution():
    with pytest.raises(ValueError,match='acquisition forbidden'):
        main(['--offline-replay','--execute-provider','--output-json','reports/rejected.json'])
    with provider_guard() as calls:
        import urllib.request
        with pytest.raises(RuntimeError,match='forbidden'):urllib.request.urlopen('http://127.0.0.1:11434')
        assert calls['real_provider_calls']==0 and calls['blocked_provider_attempts']==1
