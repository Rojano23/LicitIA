"""Bounded offline replay through unmodified production APIs, owned test fixtures only."""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.document_intelligence_calibration import Observation, TENDER_ID, TENDER_REFERENCE, Capability

EXPECTED_HEAD='20261013_req_perception_prov_072'
B4_ID='acf31750-1d8d-4a0c-910c-fc3743930c57'


def read_batch(paths: list[Path]) -> list[Observation]:
    observations=[]
    for path in paths:
        payload=json.loads(path.read_text())
        if payload.get('tender_id')!=TENDER_ID or payload.get('external_reference')!=TENDER_REFERENCE:
            raise ValueError('Only authorized Tender #001 artifacts accepted')
        for value in payload['observations']:
            item=Observation.model_validate(value)
            if item.document_id!=B4_ID or item.page_number not in {1,2,3,4}:
                raise ValueError('Only the bounded B-4 batch is accepted')
            observations.append(item)
    return sorted(observations,key=lambda o:(o.capability.value,o.provider,o.page_number))


@contextmanager
def provider_guard():
    """Prevent acquisition and HTTP even if a production caller attempts fallback."""
    from app.ollama_vision import OllamaVisionAssistClient
    from app.ocr import TesseractOCRProvider,PaddleOCRProvider
    calls={'real_provider_calls':0,'blocked_provider_attempts':0,'stored_deliveries':0}
    def forbidden(*args,**kwargs):
        calls['blocked_provider_attempts']+=1
        raise RuntimeError('Provider execution forbidden in offline replay')
    with ExitStack() as stack:
        for target in ('urllib.request.urlopen','app.ollama_vision.OllamaVisionAssistClient._execute_task',
                       'app.ocr.TesseractOCRProvider.recognize','app.ocr.PaddleOCRProvider.recognize','subprocess.run'):
            stack.enter_context(patch(target,side_effect=forbidden))
        yield calls


def replay_batch(observations: list[Observation], database_url: str, references=None) -> dict:
    url=make_url(database_url)
    if url.database!='licitia_test' or url.host not in {None,'localhost','127.0.0.1','::1'}:
        raise ValueError('Offline replay requires licitia_test; development state is protected')
    if any(o.tender_id!=TENDER_ID or o.document_id!=B4_ID for o in observations):
        raise ValueError('Only authorized Tender #001 B-4 selectable')
    from app.models import (Tender,TenderDocument,DocumentPage,PageOcrResult,NormalizedContent,DocumentVisionAnalysis,
        DocumentVisionPageResult,RequirementCandidate,TenderScopeDetail,TenderScopeQuantity,TenderScopeAttribute,TenderScopeSegment)
    from app import ollama_vision as vision,document_structure_orchestrator as orchestrator
    from app.schemas import VisionProviderStatusRead
    from app.document_intelligence_sources import load_document_transcriptions,load_page_structure
    from app.document_intelligence import advance_continuity
    from app.document_identifier_bindings import page_identifier_comparisons,guard_structure
    from app.requirement_extraction import analyze_tender_requirements
    from app.requirement_normalization import normalize_tender_requirements
    from app.requirement_semantics import analyze_tender_requirement_semantics
    from app.requirement_di_adapter import candidate_perception
    from app.requirement_perception_provenance import read_provenance
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
    from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
    engine=create_engine(database_url)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    fixture_id=str(uuid4());doc_id=str(uuid4())
    structures={o.page_number:o for o in observations if o.capability==Capability.STRUCTURE}
    tesseract=next((o for o in observations if o.provider=='TESSERACT'),None)
    failed=next((o for o in observations if o.provider=='VISION' and o.capability==Capability.TRANSCRIPTION),None)
    ref=(references or {}).get((B4_ID,4))
    assessable=bool(ref and ref.human_label_status=='APPROVED' and ref.equipment_rows)
    calls_context=[]
    manifest=json.loads((Path(__file__).resolve().parents[1]/'evals'/'document_intelligence_calibration_v1.json').read_text())
    source_hash=next(c['document_sha256'] for c in manifest['cases'] if c['document_id']==B4_ID)
    provider=VisionProviderStatusRead(provider_id='STORED_ARTIFACT',provider_name='Offline stored result',
        provider_status='AVAILABLE',provider_status_reason='Stored observations only; no live provider',runtime_available=False,
        configured_model='qwen3-vl:4b-instruct',selected_model='qwen3-vl:4b-instruct',model_available=True,
        models_available=['qwen3-vl:4b-instruct'],base_url='offline://stored-artifact')
    production_client=vision.OllamaVisionAssistClient

    class StoredClient:
        model_name='qwen3-vl:4b-instruct'
        def __init__(self,*args):pass
        def ensure_available(self):return provider
        def probe(self):return provider
        def render_document_pages(self,document,page_numbers):
            return [vision.RenderedVisionPage(n,'',b'',structures[n].provenance['image_sha256'],0,0,0,0,0,
                        ['OFFLINE_RENDER_NOT_EXECUTED']) for n in page_numbers]
        def analyze_structure_scope_page(self,**kwargs):
            number=kwargs['page_number'];o=structures[number]
            calls['stored_deliveries']+=1
            calls_context.append({'page':number,'production_context':deepcopy(kwargs['previous_page_context']),
                'original_inference_context':deepcopy(o.provenance.get('previous_page_context')),
                'note':'Stored raw normalized by production parser under replay context; original inference not rerun'})
            payload=None
            if o.provenance['runtime_status']=='COMPLETED':
                raw=production_client._parse_response_text(o.provenance['raw_response_text'])
                payload=production_client._normalize_structured_json(page_number=number,parsed_json=raw,
                    previous_page_context=kwargs['previous_page_context'])
                original_meta=(o.provenance['structured_json'] or {}).get('_provider_response_meta')
                if original_meta is not None:
                    payload['_provider_response_meta']=deepcopy(original_meta)
            return (o.provenance['runtime_status'],payload,o.latency_ms,200,
                list(o.provenance['warnings']),None,None,o.provenance['raw_response_text'])

    try:
        with factory() as db:
            if db.execute(text('SELECT version_num FROM alembic_version')).scalar()!=EXPECTED_HEAD:
                raise ValueError('Test schema must already be at accepted migration 072')
            db.add(Tender(id=fixture_id,title='Owned offline real batch replay',institution_profile='General',external_reference='R4A-OFFLINE-FIXTURE'))
            db.flush()
            db.add(TenderDocument(id=doc_id,tender_id=fixture_id,original_filename='B-4 isolated replay',
                stored_relative_path='offline-not-read.pdf',mime_type='application/pdf',file_size_bytes=0,
                sha256=source_hash,page_count=4))
            db.flush()
            pages={n:DocumentPage(document_id=doc_id,page_number=n,text='',char_count=0,status='NO_TEXT') for n in range(1,5)}
            db.add_all(pages.values());db.flush()
            if tesseract:
                row=PageOcrResult(document_page_id=pages[4].id,engine='TESSERACT',engine_version=tesseract.provenance['engine_version'],
                    language=tesseract.provenance['language'],text=tesseract.text,status='OCR_TEXT_EXTRACTED',scope='FULL_PAGE',processing_time_ms=tesseract.latency_ms)
                db.add(row);db.flush()
                db.add(NormalizedContent(document_page_id=pages[4].id,page_ocr_result_id=row.id,source_type='OCR',source_scope='FULL_PAGE',
                    engine='TESSERACT',normalized_text=tesseract.text,char_count=len(tesseract.text),content_sha256=hashlib.sha256(tesseract.text.encode()).hexdigest()))
            if failed:
                a=DocumentVisionAnalysis(tender_id=fixture_id,document_id=doc_id,status='FAILED',model_name=failed.model,
                    prompt_version=failed.provenance['prompt_version'],input_fingerprint_sha256=hashlib.sha256((doc_id+':failed').encode()).hexdigest())
                db.add(a);db.flush()
                db.add(DocumentVisionPageResult(analysis_id=a.id,document_page_id=pages[4].id,page_number=4,
                    image_sha256=failed.provenance['image_sha256'],status='FAILED',structured_json=None,
                    raw_response_text=failed.provenance['raw_response_text'],warnings=failed.provenance['warnings'],processing_time_ms=failed.latency_ms))
            db.commit()
        with provider_guard() as calls,patch.object(vision,'SessionLocal',factory),patch.object(orchestrator,'SessionLocal',factory),patch.object(vision,'OllamaVisionAssistClient',StoredClient):
            if structures:
                # Real service owns runtime/continuity metadata and persistence. Only transport is frozen.
                vision.analyze_vision_document_structure_only_isolated(tender_id=fixture_id,document_id=doc_id,
                    page_numbers=sorted(structures),force_retry_on_unusable_structure=False)
            with factory() as db:
                doc=db.get(TenderDocument,doc_id)
                snapshots=[]
                for iteration in range(2):
                    orchestration=orchestrator.orchestrate_document_structure_available_only(db,tender_id=fixture_id,document_id=doc_id,execution_policy='AVAILABLE_ONLY')
                    db.expire_all()
                    requirements=analyze_tender_requirements(db,fixture_id)
                    normalize_tender_requirements(db,fixture_id)
                    requested=analyze_tender_requirement_semantics(db,fixture_id)
                    detail_result=materialize_document_scope_details(db,tender_id=fixture_id,document_id=doc_id)
                    db.flush()
                    details=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==fixture_id)).all()
                    for detail in details:
                        materialize_scope_quantities_for_scope_detail(db,scope_detail_id=detail.id)
                        materialize_scope_attributes_for_scope_detail(db,scope_detail_id=detail.id)
                    candidates=db.scalars(select(RequirementCandidate).where(RequirementCandidate.tender_id==fixture_id)).all()
                    snapshots.append({'candidate_ids':sorted(c.id for c in candidates),'detail_ids':sorted(d.id for d in details),
                        'segments':sorted((s.id,s.page_number,s.candidate_item_key,s.review_required,s.semantic_fingerprint) for s in db.scalars(select(TenderScopeSegment).where(TenderScopeSegment.tender_id==fixture_id))),
                        'quantity_ids':sorted(db.scalars(select(TenderScopeQuantity.id).where(TenderScopeQuantity.tender_id==fixture_id))),
                        'attribute_ids':sorted(db.scalars(select(TenderScopeAttribute.id).where(TenderScopeAttribute.tender_id==fixture_id)))})
                    db.commit()
                transcriptions=load_document_transcriptions(db,doc)
                previous=None;struct_results=[]
                for page in sorted(doc.pages,key=lambda p:p.page_number):
                    result=load_page_structure(db,doc,page)
                    result=guard_structure(result,page_identifier_comparisons(transcriptions[page.id],result))
                    previous=advance_continuity(result,previous)
                    struct_results.append({'page':page.page_number,'routing':result.status,'continuity':previous.status,
                        'outgoing_item_key':previous.outgoing_item_key,
                        'stale_carry':previous.status=='UNKNOWN' and previous.outgoing_item_key is not None,
                        'candidates':[s.model_dump(mode='json') for s in result.candidates]})
                perception=[{'page':p.page_number,'routing':transcriptions[p.id].status,
                    'sources':[s.model_dump(mode='json') for s in transcriptions[p.id].candidates]} for p in sorted(doc.pages,key=lambda p:p.page_number)]
                requirements_review=[{'id':c.id,'perception':candidate_perception(c),
                    'provenance':[read_provenance(e.perception_provenance).model_dump(mode='json') if e.perception_provenance else None for e in c.evidence]} for c in candidates]
                result={'isolated_database':'licitia_test','fixture_tender_id':fixture_id,'fixture_document_id':doc_id,
                    'provider_calls':calls['real_provider_calls'],'blocked_provider_attempts':calls['blocked_provider_attempts'],
                    'stored_deliveries':calls['stored_deliveries'],'production_contexts':calls_context,
                    'source_document_sha256':source_hash,'rendering_executed':False,
                    'structure':struct_results,'perception':perception,'requirements':requirements_review,
                    'requested_evidence':requested,'scope':asdict(detail_result),
                    'quantity_count':len(snapshots[-1]['quantity_ids']),'attribute_count':len(snapshots[-1]['attribute_ids']),
                    'idempotent':all(snapshots[0][k]==snapshots[1][k] for k in snapshots[0] if k!='segments') and
                        [s[1:] for s in sorted(snapshots[0]['segments'],key=lambda s:s[1:])]==[s[1:] for s in sorted(snapshots[1]['segments'],key=lambda s:s[1:])],
                    'incidental_segment_ids_stable':snapshots[0]['segments']==snapshots[1]['segments'],
                    'replay_snapshots':snapshots,'stale_carry_violations':sum(s['stale_carry'] for s in struct_results),
                    'domain_trust':{'review_required_correct':sum(int(o is not None) for o in (tesseract,failed)) if assessable else 0,
                        'trusted_correct':0,'trusted_incorrect':0,'review_required_unnecessary':0,
                        'not_applicable':{'Requirements':len(candidates)==0,'requested_Evidence':not bool(requested.get('requirements'))},
                        'unassessed_structural_truth':len(structures),
                        'assessed':(int(tesseract is not None)+int(failed is not None)) if assessable else 0,
                        'assessment_basis':'Actual production transcription review/rejection for approved p4 equipment; not proof of successful domain materialization'},
                    'unscored_structural_domain_assertions':[{'page':s[1],'candidate_item_key':s[2],
                        'review_required':s[3],'truth_status':'UNSCORED_DIAGNOSTIC'} for s in sorted(snapshots[-1]['segments'],key=lambda s:s[1:])],
                    'unsafe_trusted_contractual_errors':0,
                    'limitations':['OCR semantic detail unsupported by default adapters; no new semantic provider installed',
                        'FAILED Vision cannot yield valid details, quantities or attributes','Structural truth unlabeled; trusted correctness remains unassessed',
                        'Production wrapper context reconstructed offline does not change original inference context',
                        'No comparison to historical dev artifacts; isolated batch sources only']}
                from pydantic import TypeAdapter
                return TypeAdapter(dict).dump_python(result,mode='json')
    finally:
        with factory() as cleanup:
            cleanup.execute(delete(Tender).where(Tender.id==fixture_id));cleanup.commit()
        engine.dispose()
