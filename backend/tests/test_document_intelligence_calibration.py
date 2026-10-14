from pathlib import Path
import json
import pytest
from pydantic import ValidationError
from app.document_intelligence_calibration import (Observation, Reference, ErrorCategory, Capability, analyze, evaluate, aggregate, freeze_references, serialize, observations_from_inventory)
from scripts.run_document_intelligence_calibration import parser, main


def observation(**kwargs):
    return Observation(provider='NATIVE',capability='TRANSCRIPTION',document_id='doc',page_number=1,
        artifact_id='a',routing_status='REVIEW_REQUIRED',**kwargs)


def reference(**kwargs):
    return Reference(identity='human',file_sha256='a'*64,human_label_status='APPROVED',**kwargs)


def test_cal01_golden_read_only(tmp_path):
    path=tmp_path/'golden.json'; path.write_text('{"truth":1}')
    before=path.read_bytes(); freeze_references([path]); evaluate(observation(),reference())
    assert path.read_bytes()==before


def test_cal02_default_no_model():
    args=parser().parse_args(['--output-json','reports/result.json'])
    assert not args.execute_provider
    with pytest.raises(ValueError,match='safety flags'):
        main(['--execute-provider','--no-real-model','--output-json','reports/result.json'])


def test_cal03_native_captured():
    assert evaluate(observation(text='real native'))['observed']['text']=='real native'


def test_cal04_ocr_captured():
    o=observation().model_copy(update={'provider':'TESSERACT','text':'ocr'})
    assert evaluate(o)['observed']['provider']=='TESSERACT'


def test_cal05_external_vision_ingestion(tmp_path):
    out=Path(__file__).resolve().parents[1]/'reports'/'test_r4a_ingested.json'
    artifact=tmp_path/'external.json'
    o=observation().model_copy(update={'provider':'VISION','model':'configured','text':'visible'})
    artifact.write_text(serialize({'observations':[o.model_dump(mode='json')]}))
    try:
        main(['--provider','VISION','--ingest-json',str(artifact),'--output-json',str(out)])
        assert json.loads(out.read_text())['observations'][0]['text']=='visible'
    finally:
        out.unlink(missing_ok=True)


def test_cal06_taxonomy_deterministic():
    assert len(ErrorCategory)==15
    assert evaluate(observation(conflicts=('IDENTIFIER',)),reference(numeric_tokens=('1',)))['error_category']==[
        'CORRECT_REVIEW_ESCALATION','NUMERIC_ERROR','PROVIDER_CONFLICT']


def test_cal07_unsafe_trust():
    o=observation(text='2',domain_input_trusted=True).model_copy(update={'routing_status':'RESOLVED'})
    assert evaluate(o,reference(numeric_tokens=('1',)))['unsafe_trusted_contractual_errors']==1


def test_cal08_review_separate():
    r=evaluate(observation(text='2'),reference(numeric_tokens=('1',)))
    assert r['review_surfaced'] and r['unsafe_trusted_contractual_errors']==0


def test_cal09_safe_miss():
    assert evaluate(observation(),reference(material_fragments=('obligation',)))['safe_misses']==1


def test_cal10_identifier_metrics():
    r=evaluate(observation(identifiers={'ITEM_NUMBER':('01',)}),reference(identifiers={'ITEM_NUMBER':('1',)},exhaustive_identifiers=True))
    assert r['measurements']['identifier:ITEM_NUMBER']=={'correct':0,'missing':1,'false':1}


def test_cal11_boundary():
    r=evaluate(observation(structure={'starts':False}).model_copy(update={'capability':Capability.STRUCTURE}),reference(structure={'starts':True}))
    assert 'STRUCTURE_BOUNDARY_ERROR' in r['error_category']


def test_cal12_continuity():
    r=evaluate(observation(continuity_status='UNKNOWN',outgoing_item_key='1'))
    assert r['stale_carry_violations']==1


def test_cal13_quantity_binding():
    r=evaluate(observation(quantity_bindings=('01:10',)),reference(quantity_bindings=('1:10',)))
    assert 'QUANTITY_BINDING_ERROR' in r['error_category']


def test_cal14_domain_impact():
    r=evaluate(observation(domain_impact=('Scope','Quantity')),reference(material_fragments=('missing',)))
    assert aggregate([r])['domain_impact']=={'Quantity':1,'Scope':1}


def test_cal15_aggregate_order():
    a=evaluate(observation(),reference(numeric_tokens=('1',)))
    b=evaluate(observation(text='1'),reference(numeric_tokens=('1',)))
    assert serialize(aggregate([a,b]))==serialize(aggregate([b,a]))


def test_cal16_idempotent():
    o=observation(); refs={('doc',1):reference()}
    assert serialize(analyze([o],refs))==serialize(analyze([o],refs))


def test_cal17_tender002_rejected():
    with pytest.raises(ValidationError):
        observation(tender_id='other')
    with pytest.raises(ValueError,match='Tender #001'):
        main(['--tender-id','other','--output-json','reports/no.json'])


def test_cal18_metadata():
    o=observation().model_copy(update={'provider':'VISION','model':'qwen3-vl:4b-instruct'})
    r=evaluate(o)['observed']
    assert (r['provider'],r['model'],r['capability'])==('VISION','qwen3-vl:4b-instruct','TRANSCRIPTION')


def test_cal19_hash(tmp_path):
    path=tmp_path/'g'; path.write_bytes(b'approved')
    import hashlib
    assert freeze_references([path])[0]['sha256']==hashlib.sha256(b'approved').hexdigest()


def test_cal20_serialization():
    assert serialize({'z':1,'a':2})==serialize({'a':2,'z':1})


def test_unlabeled_never_scores():
    r=evaluate(observation(),Reference(identity='pending',file_sha256='x',material_fragments=('missing',)))
    assert r['status']=='DIAGNOSTIC_ONLY' and not r['measurements']


def test_deselected_never_counts_unsafe():
    o=observation(lineage='DESELECTED').model_copy(update={'routing_status':'RESOLVED'})
    assert aggregate([evaluate(o,reference(material_fragments=('missing',)))])['unsafe_trusted_contractual_errors']==0


def test_partial_reference_does_not_claim_precision():
    result=analyze([observation(critical_tokens=('1','2'))],{('doc',1):reference(critical_tokens=('1',))})
    assert result['aggregate']['transcription']['critical_tokens']['precision'] is None


@pytest.mark.parametrize('method,provider', [('NATIVE','NATIVE'),('OCR','TESSERACT')])
def test_capture_real_routing_contract(method, provider):
    from app.document_intelligence import PageIdentity, normalize_perception_evidence, route_capability
    page=PageIdentity(document_id='doc',document_page_id='page',page_number=1,tender_id=observation().tender_id)
    source=normalize_perception_evidence(source_method=method,page=page,capability=Capability.TRANSCRIPTION,
        source_artifact_key='artifact',generation_id='generation',text='PARTIDA 01',
        provider_metadata=(('engine',provider),) if method=='OCR' else ())
    transcription=route_capability(page=page,capability=Capability.TRANSCRIPTION,evidence=(source,))
    structure=route_capability(page=page,capability=Capability.STRUCTURE,evidence=())
    rows={'pages':[{'document_id':'doc','page_number':1,'transcription':transcription.model_dump(mode='json'),
        'structure':structure.model_dump(mode='json'),'domain_inputs':{'Requirements':1}}]}
    result=observations_from_inventory(rows,method,Capability.TRANSCRIPTION)
    assert result[0].provider==provider and result[0].text=='PARTIDA 01'
    assert result[0].identifiers['ITEM_NUMBER']==('01',)
    assert result[0].routing_status=='REVIEW_REQUIRED'
    assert result[0].provenance['generation_id']=='generation'


def test_structure_cannot_use_transcription_golden():
    o=observation().model_copy(update={'capability':Capability.STRUCTURE})
    r=evaluate(o,reference(material_fragments=('visible text',)))
    assert r['status']=='DIAGNOSTIC_ONLY' and not r['measurements']


def test_unassessed_domain_trust_is_not_certified():
    o=observation(text='2').model_copy(update={'routing_status':'RESOLVED'})
    r=analyze([o],{('doc',1):reference(numeric_tokens=('1',))})['aggregate']
    assert r['unsafe_auto_selections']==1 and r['unsafe_trusted_contractual_errors']==0
    assert r['domain_trust_assessed']==0 and r['domain_trust_unassessed']==1


def test_domain_engine_error_not_perception_error():
    r=evaluate(observation(domain_errors=(ErrorCategory.QUANTITY_BINDING_ERROR,)))
    assert r['error_origin']=='DOMAIN_ENGINE'
    assert aggregate([r])['domain_engine_error_count']==1


def test_external_structure_capture_defers_context_to_production_replay(monkeypatch):
    """Mock proves client integration/continuity control, never model quality."""
    from types import SimpleNamespace
    from scripts.run_document_intelligence_calibration import execute
    from app.ollama_vision import OllamaVisionAssistClient, RenderedVisionPage
    from app.document_intelligence import PageIdentity, route_capability
    doc=SimpleNamespace(id='doc',tender_id=observation().tender_id,revision_number=1)
    pages={i:SimpleNamespace(id=f'p{i}',document_id='doc',page_number=i) for i in (1,2)}
    pending=iter(pages.values())
    db=SimpleNamespace(get=lambda *args:doc,scalar=lambda *args:next(pending))
    rendered=[RenderedVisionPage(i,'',b'image',str(i)*64,100,100,5,1,2.0,[]) for i in (1,2)]
    monkeypatch.setattr(OllamaVisionAssistClient,'ensure_available',lambda self:None)
    monkeypatch.setattr(OllamaVisionAssistClient,'render_document_pages',lambda *args:rendered)
    payload={'page_number':1,'continues_previous_item':False,'previous_item_number':None,
        'new_items':[{'item_number':'1','concept_raw_text':'PARTIDA 1','review_required':False}],
        'item_segments':[{'item_number':'1','starts_on_this_page':True,'anchor_raw_text':'PARTIDA 1',
                          'has_service':True,'has_supply':False,'has_deliverable':False,'review_required':False}],
        'open_item_at_page_end':'1','uncertainties':[]}
    monkeypatch.setattr(OllamaVisionAssistClient,'analyze_structure_scope_page',lambda self,**kwargs:
        ('COMPLETED',payload,5,200,[],None,None,'{}') if kwargs['page_number']==1 else ('FAILED',None,5,500,[],None,None,''))
    trans={p.id:route_capability(page=PageIdentity(document_id='doc',document_page_id=p.id,page_number=p.page_number,
            tender_id=doc.tender_id,document_version='1'),capability=Capability.TRANSCRIPTION,evidence=()) for p in pages.values()}
    monkeypatch.setattr('app.document_intelligence_sources.load_document_transcriptions',lambda *args:trans)
    args=SimpleNamespace(document_id='doc',pages=[1,2],provider='VISION',capability='STRUCTURE',model='qwen3-vl:4b-instruct',timeout=180)
    result=execute(db,args)
    assert all(o.continuity_status is None and o.outgoing_item_key is None for o in result)
    assert all(o.structure=={} for o in result)
    assert 'PRODUCTION_CONTEXT_REPLAY_REQUIRED' in result[0].notes
    assert '_continuity_state_quality' not in result[0].provenance['structured_json']
    assert all(o.routing_status=='REVIEW_REQUIRED' for o in result)
