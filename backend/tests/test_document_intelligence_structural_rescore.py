from pathlib import Path
import hashlib,json
import pytest
from pydantic import ValidationError
from app.document_intelligence_structural_rescore import *
from app.document_intelligence_calibration_replay import read_batch,replay_batch
ROOT=Path(__file__).resolve().parents[1]
GOLD=ROOT/'evals'/'document_intelligence_b4_structure_golden_v1.json'
OBS=ROOT/'reports'/'di_r4a_vision_b4_p1_p3_structure.json'
URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test'
@pytest.fixture(scope='module', autouse=True)
def current_schema_replay_contract():
    # Regression at M7-A schema only; do not alter the frozen production replay guard.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('app.document_intelligence_calibration_replay.EXPECTED_HEAD', '20261021_commercial_073')
        yield

@pytest.fixture(scope='module')
def golden():return load_golden(GOLD)
@pytest.fixture(scope='module')
def observations():return read_batch([OBS])
@pytest.fixture(scope='module')
def replay(observations):return replay_batch(observations,URL)
@pytest.fixture(scope='module')
def result(golden,observations,replay):return rescore(golden,observations,replay)
def test_GS01_load(golden):assert golden.approved_by_human and len(golden.pages)==4
def test_GS02_hashes(golden):assert all(hashlib.sha256(Path(p.source_representation).read_bytes()).hexdigest()==p.source_page_hash for p in golden.pages)
def test_GS03_changed_source(tmp_path):
    data=json.loads(GOLD.read_text());p=tmp_path/'changed.pdf';p.write_bytes(b'wrong')
    for page in data['pages']:page['source_path']=str(p)
    data['content_sha256']=digest(data);file=tmp_path/'gold.json';file.write_bytes(canonical_bytes(data))
    with pytest.raises(ValueError,match='source hash'):load_golden(file)
def test_GS04_readonly(result):
    before=GOLD.read_bytes();load_golden(GOLD);assert GOLD.read_bytes()==before

def test_GS05_candidate():
    with pytest.raises(ValidationError):load_golden(ROOT/'reports'/'b4_structural_golden_candidate_v1.json')
def test_GS06_ingestion(observations):assert [o.page_number for o in observations]==[1,2,3]
def test_GS07_zero_calls(replay):assert replay['provider_calls']==replay['blocked_provider_attempts']==0

def test_GS08_boundary(result):assert result['pages'][1]['dimensions']['boundary'] is False
def test_GS09_continuation(result):assert result['pages'][1]['missed_continuations']==['ITEM_1']
def test_GS10_identity(result):assert result['pages'][2]['dimensions']['group_identity'] is False
def test_GS11_false_start(result):assert result['pages'][2]['false_starts']==['ITEM_3']
def test_GS12_missed_continue(result):assert result['aggregate']['missed_continuations']==2
def test_GS13_missed_close(result,golden):
    assert result['aggregate']['missed_closures']==1
    complete=surface({'continues_previous_item':True,'previous_item_number':'1','open_item_at_page_end':'2',
        'item_segments':[{'item_number':'1','starts_on_this_page':False},{'item_number':'2','starts_on_this_page':True}]})
    assert complete['closes']==['ITEM_1']
    assert score_page(golden.pages[1],complete,routing='RESOLVED',domain_review=False)['status']=='CORRECT'
def test_GS14_review(golden,observations):
    r=score_page(golden.pages[2],surface(observations[2].provenance['structured_json']),routing='REVIEW_REQUIRED',domain_review=True)
    assert r['status']=='REVIEW_REQUIRED_CORRECT' and r['correct_review_escalation']==1

def test_GS15_unsafe(result):
    assert result['aggregate']['unsafe_trusted_structural_errors']==0
    assert result['aggregate']['correct_review_escalation']==2
    assert result['aggregate']['safe_misses']==2
def test_GS16_stale(golden,observations):
    r=score_page(golden.pages[0],surface(observations[0].provenance['structured_json']),stale=True)
    assert r['stale_carry_violations']==1

def test_GS17_boundary12(result):assert result['boundaries'][0]['status']=='INCORRECT'
def test_GS18_boundary23(result):assert result['boundaries'][1]['status']=='INCORRECT'
def test_GS19_no_p4(result):
    assert result['provider_pages']==[1,2,3] and len(result['pages'])==3
    assert result['boundaries'][2]['right_observed'] is False

def test_GS20_determinism(golden,observations,replay):assert canonical_bytes(rescore(golden,observations,replay))==canonical_bytes(rescore(golden,list(reversed(observations)),replay))
def test_GS21_isolation(observations,replay):
    assert replay['isolated_database']=='licitia_test'
    with pytest.raises(ValueError,match='licitia_test'):replay_batch(observations,URL.replace('licitia_test','licitia_dev'))
def test_GS22_idempotence(replay):assert replay['idempotent']
def test_GS23_provenance(result):assert all(p['perception_provenance']['source_analysis_id'] and p['perception_provenance']['source_page_result_id'] for p in result['pages'])
def test_GS24_tender002(golden,observations,replay):
    bad=observations[0].model_copy(update={'tender_id':'other'})
    with pytest.raises(ValueError,match='Tender #001'):rescore(golden,[bad],replay)
def test_GS25_no_model_truth(golden):
    data=golden.model_dump(mode='json');data['pages'][0]['supporting_references'][0]['authority']='MODEL_DERIVED'
    with pytest.raises(ValidationError,match='Model-derived'):ApprovedGolden.model_validate(data)
