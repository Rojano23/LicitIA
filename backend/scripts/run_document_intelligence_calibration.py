"""Bounded calibration CLI. No provider acquisition unless explicitly requested."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import sys
from dataclasses import asdict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.document_intelligence_calibration import (TENDER_ID, TENDER_REFERENCE, Capability, Observation,
    Reference, EquipmentReference, SourceReferenceConflict, analyze, freeze_references, inventory, observations_from_inventory, serialize)

GOLDENS = ('semantic_scope_golden_v1.json','technical_attribute_golden_v1.json','scope_quantity_golden_v1.json')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provider',choices=['NATIVE','OCR','VISION','ALL','TESSERACT','PADDLEOCR'],default='NATIVE')
    p.add_argument('--capability',choices=[c.value for c in Capability if c.value!='SEMANTIC_ASSIST'],default='TRANSCRIPTION')
    p.add_argument('--tender-id',default=TENDER_ID)
    p.add_argument('--document-id')
    p.add_argument('--pages',type=int,nargs='+',default=[])
    p.add_argument('--database-url',default=os.environ.get('DATABASE_URL'))
    p.add_argument('--output-json',type=Path,required=True)
    p.add_argument('--inventory-json',type=Path)
    p.add_argument('--ingest-json',type=Path)
    p.add_argument('--offline-replay',action='store_true')
    p.add_argument('--batch-artifacts',type=Path,nargs='+')
    p.add_argument('--no-real-model',action='store_true')
    p.add_argument('--execute-provider',action='store_true')
    p.add_argument('--model',default='qwen3-vl:4b-instruct')
    p.add_argument('--timeout',type=float,default=180)
    return p


def references(paths):
    # Approved domain fragments are partial text references, not whole-page truth.
    grouped = {}
    quantities = {}
    models = {}
    dimensions = {}
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get('tender_id',TENDER_ID)!=TENDER_ID or payload.get('external_reference',TENDER_REFERENCE)!=TENDER_REFERENCE:
            raise ValueError('Golden identity mismatch')
        for case in payload.get('cases',[]):
            doc = case.get('source_document_id') or case.get('document_id')
            page = case.get('page_number')
            source = case.get('source_text') or case.get('source_excerpt')
            if not doc or not page or not source or case.get('human_label_status')!='APPROVED':
                continue
            # source_text has only domain-fragment approval; do not assume its entirety is a reviewed transcription.
            excerpts = [q.get('evidence_excerpt') for q in case.get('expected_quantities',[])]
            excerpts += [a.get('evidence_excerpt') for a in case.get('expected_attributes',[])]
            excerpts += [a.get('evidence_excerpt') for a in case.get('expected_obligations',[])]
            excerpts = [e for e in excerpts if e and e in source]
            if excerpts:
                grouped.setdefault((doc,page),[]).append((path,case['case_id'],excerpts))
            for q in case.get('expected_quantities',[]):
                dimensions[(doc,page,q.get('evidence_excerpt'))]='NUMERIC_MISMATCH'
            for a in case.get('expected_attributes',[]):
                dimensions[(doc,page,a.get('evidence_excerpt'))]={'model':'IDENTIFIER_MISMATCH','power_supply':'NUMERIC_MISMATCH'}.get(a['attribute_name'],'CRITICAL_TOKEN_MISMATCH')
            for quantity in case.get('expected_quantities',[]):
                if quantity.get('quantity_raw','').isdigit() and quantity.get('unit_raw') in {'PIEZA','PIEZAS'}:
                    quantities[(doc,page,case['scope_detail_id'])]=(case,quantity)
            for attribute in case.get('expected_attributes',[]):
                if attribute.get('attribute_name')=='model':
                    models[(doc,page,case['scope_detail_id'])]=attribute['value_raw']
    result = {key:Reference(identity='|'.join(sorted(c for _,c,_ in rows)),
        file_sha256=hashlib.sha256(serialize(freeze_references(list({p for p,_,_ in rows}))).encode()).hexdigest(),
        human_label_status='APPROVED',material_fragments=tuple(sorted(set(e for _,_,ex in rows for e in ex)))) for key,rows in grouped.items()}
    for key, ref in list(result.items()):
        equipment=[]
        for identity,(case,qty) in sorted(quantities.items()):
            if identity[:2]==key and identity in models:
                equipment.append(EquipmentReference(identity=case['case_id'],source_excerpt=case['source_text'],
                    model=models[identity],quantity=qty['quantity_raw'],unit=qty['unit_raw']))
        conflicts=()
        # User-authorized Phase 2 discrepancy, also documented in the immutable first-batch analysis.
        # This is unresolved reference metadata, never a replacement Golden label.
        if key==('acf31750-1d8d-4a0c-910c-fc3743930c57',4) and any(e.model=='AA143-H50/K4400' for e in equipment):
            conflicts=(SourceReferenceConflict(golden_value='AA143-H50/K4400',source_reading='AAI143-H50/K4A00',
                authority='Phase 2 user instruction / document_intelligence_r4a_first_batch_analysis.md; unresolved'),)
        result[key]=ref.model_copy(update={'equipment_rows':tuple(equipment),'source_conflicts':conflicts,
            'fragment_dimensions':{fragment:dimensions[(key[0],key[1],fragment)] for fragment in ref.material_fragments
                if (key[0],key[1],fragment) in dimensions}})
    return result


def execute(db, args):
    # Imports and provider construction live entirely behind the explicit execution gate.
    from app.models import TenderDocument, DocumentPage
    from app.ollama_vision import OllamaVisionAssistClient
    from app.config import get_settings
    doc = db.get(TenderDocument,args.document_id)
    if doc is None or doc.tender_id!=TENDER_ID:
        raise ValueError('Document outside authorized Tender #001')
    settings = get_settings().model_copy(update={'licitia_ollama_vision_model':args.model,'licitia_ollama_timeout_seconds':args.timeout})
    client = OllamaVisionAssistClient(settings)
    if args.provider=='VISION':
        client.ensure_available()
    outputs = []
    context = None
    continuity = None
    for rendered in client.render_document_pages(doc,sorted(set(args.pages))):
        if (rendered.image_bytes_size > settings.licitia_vision_render_max_image_bytes or
                max(rendered.width_px,rendered.height_px)>settings.licitia_vision_render_max_dimension_px):
            raise ValueError('Rendered page exceeds existing runtime image bounds')
        page = db.scalar(select(DocumentPage).where(DocumentPage.document_id==doc.id,DocumentPage.page_number==rendered.page_number))
        if page is None:
            raise ValueError('Selected page not in authorized inventory')
        if args.provider=='VISION':
            previous_context = context
            if args.capability=='STRUCTURE':
                result = client.analyze_structure_scope_page(page_number=rendered.page_number,image_bytes=rendered.image_bytes,
                    mode='ASSISTIVE_EXTRACTION',previous_page_context=context)
            else:
                result = client.analyze_detail_transcription_page(page_number=rendered.page_number,image_bytes=rendered.image_bytes,
                    mode='ASSISTIVE_EXTRACTION',region_hint=None)
            status,payload,latency,_,warnings,_,_,raw = result
            context = None
            if args.capability=='STRUCTURE' and payload is None:
                continuity = None
            content = '\n'.join(line['raw_visible_text'] for line in (payload or {}).get('raw_lines',[]))
            structure = {}
            if payload and args.capability=='STRUCTURE':
                # Acquisition captures provider output only. Structural quality/context
                # is constructed by the production service in isolated offline replay.
                content='\n'.join(segment.get('anchor_raw_text') or '' for segment in payload.get('item_segments',[]))
            provenance = {'image_sha256':rendered.image_sha256,'structured_json':payload,'raw_response_text':raw,'warnings':warnings,'runtime_status':status,
                'timeout_seconds':args.timeout,'task':'STRUCTURE_SCOPE' if args.capability=='STRUCTURE' else 'DETAIL_TRANSCRIPTION',
                'prompt_version':'vision-structure-scope-2026-09-03-006' if args.capability=='STRUCTURE' else 'vision-detail-transcription-2026-08-31-001'}
            provenance['previous_page_context']=previous_context
            provenance['continuity']=continuity.model_dump(mode='json') if continuity else None
            model = args.model
        else:
            if args.provider!='TESSERACT' or args.capability!='TRANSCRIPTION':
                raise ValueError('Acquisition supports local Tesseract transcription or Vision tasks only')
            from app.ocr import TesseractOCRProvider
            from PIL import Image
            import io
            started=time.perf_counter()
            result = TesseractOCRProvider().recognize(Image.open(io.BytesIO(rendered.image_bytes)))
            content,latency,structure,model = result['text'],int((time.perf_counter()-started)*1000),{},None
            provenance = result
        outputs.append(Observation(provider=args.provider,model=model,capability=args.capability,document_id=doc.id,
            page_number=page.page_number,artifact_id='external:'+rendered.image_sha256,
            text=content,structure=structure,routing_status='REVIEW_REQUIRED',latency_ms=latency,provenance=provenance,
            continuity_status=None,outgoing_item_key=None,
            notes=('EXTERNAL_ACQUISITION_NOT_PERSISTED','FIDELITY_NOT_CERTIFIED',
                *(['STRUCTURE_CAPTURE_ONLY','PRODUCTION_CONTEXT_REPLAY_REQUIRED'] if args.capability=='STRUCTURE' else []))))
    return outputs


def main(argv=None):
    args = parser().parse_args(argv)
    if args.tender_id!=TENDER_ID:
        raise ValueError('Only Tender #001 is selectable')
    if args.offline_replay and (args.execute_provider or not args.batch_artifacts or not args.database_url):
        raise ValueError('Offline replay requires stored batch and licitia_test; acquisition forbidden')
    if any(page<1 for page in args.pages) or args.timeout<=0:
        raise ValueError('Pages and timeout must be positive')
    if args.execute_provider and (args.no_real_model or not args.document_id or not args.pages or len(set(args.pages))>4):
        raise ValueError('Explicit bounded document/pages (maximum 4) required; safety flags conflict')
    if args.execute_provider and args.provider not in {'VISION','TESSERACT'}:
        raise ValueError('Unsupported provider acquisition')
    if args.execute_provider and args.provider=='TESSERACT' and args.capability!='TRANSCRIPTION':
        raise ValueError('Tesseract acquisition supports TRANSCRIPTION only')
    paths = [BACKEND_ROOT/'evals'/name for name in GOLDENS]
    frozen = freeze_references(paths)
    manifest=json.loads((BACKEND_ROOT/'evals'/'document_intelligence_calibration_v1.json').read_text())
    if manifest['tender_id']!=TENDER_ID or manifest['external_reference']!=TENDER_REFERENCE:
        raise ValueError('Calibration manifest identity mismatch')
    approved_hashes={Path(r['path']).name:r['sha256'] for r in manifest['golden_references']}
    if any(approved_hashes.get(Path(r['path']).name)!=r['sha256'] for r in frozen):
        raise ValueError('Frozen Golden hash changed; explicit review required')
    protected = [p.resolve() for p in paths]
    for out in (args.output_json,args.inventory_json):
        if out and (out.resolve() in protected or not out.resolve().is_relative_to((BACKEND_ROOT/'reports').resolve())):
            raise ValueError('Outputs must be separate artifacts under backend/reports')
    replay=None
    if args.offline_replay:
        from app.document_intelligence_calibration_replay import read_batch,replay_batch
        observations=read_batch(args.batch_artifacts)
        replay=replay_batch(observations,args.database_url,references(paths))
        data=None
    elif args.ingest_json:
        if args.execute_provider:
            raise ValueError('Ingestion and acquisition are separate operations')
        observations = [Observation.model_validate(o) for o in json.loads(args.ingest_json.read_text())['observations']]
        observations = [o for o in observations if o.capability.value==args.capability and
            (args.provider=='ALL' or o.provider==args.provider)]
        data = None
        if args.document_id:
            observations = [o for o in observations if o.document_id==args.document_id and (not args.pages or o.page_number in args.pages)]
    else:
        if not args.database_url:
            raise ValueError('--database-url or DATABASE_URL required')
        engine = create_engine(args.database_url)
        with Session(engine) as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            data = inventory(db)
            if args.document_id and args.document_id not in {d['id'] for d in data['documents']}:
                raise ValueError('Document outside Tender #001')
            observations = execute(db,args) if args.execute_provider else observations_from_inventory(data,args.provider,Capability(args.capability),args.document_id,tuple(args.pages))
            db.rollback()
        engine.dispose()
    if replay is not None and replay['domain_trust']['assessed']:
        # Attach measured boundary trust only to applicable, referenced transcriptions.
        page4=next(p for p in replay['perception'] if p['page']==4)
        derived=[]
        for o in observations:
            method='OCR' if o.provider=='TESSERACT' else o.provider
            sources=[s for s in page4['sources'] if s['source_method']==method]
            if o.capability==Capability.TRANSCRIPTION and o.page_number==4 and sources:
                o=o.model_copy(update={'domain_input_trusted':any(s['quality']=='RELIABLE' for s in sources)})
            derived.append(o)
        observations=derived
    report = analyze(observations,references(paths))
    from app.document_intelligence_calibration_fidelity import transcription_fidelity
    refs=references(paths)
    report['transcription_fidelity']=[{'provider':o.provider,**transcription_fidelity(o,refs[(o.document_id,o.page_number)])}
        for o in observations if o.capability==Capability.TRANSCRIPTION and (o.document_id,o.page_number) in refs]
    if replay is not None:
        report['offline_replay']=replay
        report['aggregate']['domain_trust_assessment_basis']=replay['domain_trust']['assessment_basis']
    report.update({'golden_references':frozen,'real_models_executed':args.execute_provider and args.provider=='VISION',
                   'observations':[o.model_dump(mode='json') for o in observations],
                   'baseline_provider':args.provider,'capability':args.capability})
    if freeze_references(paths)!=frozen:
        raise RuntimeError('Golden changed during calibration')
    args.output_json.parent.mkdir(parents=True,exist_ok=True)
    args.output_json.write_text(serialize(report))
    if args.inventory_json and data:
        args.inventory_json.write_text(serialize(data))
    print(serialize(report['aggregate']))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
