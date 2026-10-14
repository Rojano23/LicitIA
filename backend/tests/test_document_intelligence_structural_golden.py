from copy import deepcopy
import hashlib,json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.document_intelligence_structural_golden import CandidatePack,Groups,serialize,write_candidate,review_page_images
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def data():
    # Synthetic contract fixture; never source-derived or approved truth.
    def groups(*keys):return {'state':'KNOWN' if keys else 'NONE','groups':list(keys)}
    specs=[([],['A'],['A'],[],[],[('STARTS','A'),('CONTINUES_OUT','A')]),
           (['A'],['B'],['B'],['A'],['A'],[('CONTINUES_IN','A'),('CONTINUES','A'),('CLOSES','A'),('STARTS','B'),('CONTINUES_OUT','B')]),
           (['B'],['B'],[],['B'],[],[('CONTINUES_IN','B'),('CONTINUES','B'),('CONTINUES_OUT','B')]),
           (['B'],[],[],['B'],['B'],[('CONTINUES_IN','B'),('CONTINUES','B'),('CLOSES','B')])]
    pages=[]
    for n,(incoming,outgoing,starts,continues,closes,events) in enumerate(specs,1):
        pages.append({'golden_id':'synthetic-pending','tender_id':'decd32ae-2c1f-4520-89bc-d845c986a7ba',
            'document_id':'acf31750-1d8d-4a0c-910c-fc3743930c57','document_version':'1','page_number':n,
            'source_document_sha256':'a'*64,'source_path':'synthetic-not-read.pdf','source_representation':'synthetic.png',
            'source_page_hash':'b'*64,'representation_contract':'synthetic fixture',
            'incoming_group':groups(*incoming),'outgoing_group':groups(*outgoing),'starts_item':groups(*starts),
            'continues_item':groups(*continues),'closes_item':groups(*closes),
            'boundary_events':[{'order':i,'event_type':kind,'group':key,'locator':'synthetic'} for i,(kind,key) in enumerate(events,1)],
            'structural_review_expected':False,'human_note':'Synthetic, no truth approval','uncertainty':'fixture only',
            'supporting_references':[{'identity':'synthetic','authority':'DIAGNOSTIC_ONLY','scope':'fixture','sha256':'c'*64}],
            'approved_by_human':False})
    return {'golden_id':'synthetic-pending','pages':pages,'approved_by_human':False}
def test_HG01_contract(data):assert len(CandidatePack.model_validate(data).pages)==4
def test_HG02_unknown_none():assert Groups(state='UNKNOWN')!=Groups(state='NONE')
def test_HG03_multiple_events(data):assert [e.event_type for e in CandidatePack.model_validate(data).pages[1].boundary_events]==['CONTINUES_IN','CONTINUES','CLOSES','STARTS','CONTINUES_OUT']
def test_HG04_order(data):
    data['pages'][1]['boundary_events'].reverse()
    with pytest.raises(ValidationError,match='contiguous'):CandidatePack.model_validate(data)
def test_HG05_hash_required(data):
    del data['pages'][0]['source_page_hash']
    with pytest.raises(ValidationError):CandidatePack.model_validate(data)
def test_HG06_provenance(data):
    for field in ['document_id','document_version','page_number']:
        altered=deepcopy(data);del altered['pages'][0][field]
        with pytest.raises(ValidationError):CandidatePack.model_validate(altered)
def test_HG07_cannot_approve(data):
    data['approval_status']='APPROVED'
    with pytest.raises(ValidationError):CandidatePack.model_validate(data)
def test_HG08_false_default(data):
    del data['approved_by_human'];del data['pages'][0]['approved_by_human']
    pack=CandidatePack.model_validate(data)
    assert pack.approved_by_human is False and pack.pages[0].approved_by_human is False
def test_HG09_model_cannot_approve(data):
    data['pages'][0]['supporting_references'][0]['authority']='MODEL_DERIVED';data['pages'][0]['approved_by_human']=True
    with pytest.raises(ValidationError):CandidatePack.model_validate(data)
def test_HG10_no_providers(data):
    from app.document_intelligence_calibration_replay import provider_guard
    with provider_guard() as calls:serialize(CandidatePack.model_validate(data))
    assert calls['real_provider_calls']==calls['blocked_provider_attempts']==0
def pdf(tmp_path):
    import pymupdf
    path=tmp_path/'source.pdf';doc=pymupdf.open()
    for _ in range(4):doc.new_page()
    doc.save(path);doc.close();return path
def test_HG11_immutable(tmp_path):
    source=pdf(tmp_path);before=source.read_bytes()
    rows=review_page_images(source,tmp_path/'review',expected_sha256=hashlib.sha256(before).hexdigest())
    assert source.read_bytes()==before
    assert all(hashlib.sha256(Path(r['source_representation']).read_bytes()).hexdigest()==r['source_page_hash'] for r in rows)
def test_HG12_no_vision_dependency(tmp_path):
    source=pdf(tmp_path)
    from app.document_intelligence_calibration_replay import provider_guard
    with provider_guard() as calls:rows=review_page_images(source,tmp_path/'review',expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    assert len(rows)==4 and calls['real_provider_calls']==0
def test_HG13_deterministic(data):
    a=CandidatePack.model_validate(data);data['pages'].reverse();b=CandidatePack.model_validate(data)
    assert serialize(a)==serialize(b)
def test_HG14_tender002_rejected(data):
    data['pages'][0]['tender_id']='other'
    with pytest.raises(ValidationError):CandidatePack.model_validate(data)
def test_HG15_no_canonical_write(data):
    target=ROOT/'evals'/'document_intelligence_b4_structure_golden_v1.json'
    before=target.read_bytes() if target.exists() else None
    with pytest.raises(ValueError,match='no canonical'):write_candidate(CandidatePack.model_validate(data),target)
    assert (target.read_bytes() if target.exists() else None)==before
