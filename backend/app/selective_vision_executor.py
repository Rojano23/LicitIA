"""Task-local Vision governance over canonical clients and persisted artifacts.

No implicit provider probes, no structure/detail chaining, no legacy API changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import fcntl
import json
from urllib.parse import urlparse
from app.models import DocumentPage, TenderDocument, DocumentVisionAnalysis, DocumentVisionPageResult
from app.document_perception_planner import VisionPlan, plan_document_vision_tasks
from app.selective_ocr_executor import _bytes, _hash, _verified_path, render_ocr_input
from app.ollama_vision import (OllamaVisionAssistClient, VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
    VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION, VisionAssistModelPageResponse,
    VisionAssistModelDetailTranscriptionResponse, _merge_detail_transcription)

POLICY_VERSION = 'selective-vision-v1'


@dataclass(frozen=True)
class VisionConfiguration:
    model: str
    model_revision: str  # Caller-supplied local digest; never probe while planning/reusing.
    base_url: str = 'http://localhost:11434'
    timeout_seconds: int = 60
    structure_tokens: int = 600
    detail_tokens: int = 1000

    def __post_init__(self):
        url = urlparse(self.base_url)
        if (url.scheme != 'http' or url.hostname not in {'localhost','127.0.0.1','::1'}
                or url.username or url.password or url.query or url.fragment or url.path not in {'','/'}):
            raise ValueError('LOCAL_VISION_ENDPOINT_REQUIRED')
        if (not self.model.strip() or len(self.model)>64 or not self.model_revision.strip()
                or self.model_revision.lower() in {'unknown','unavailable'}
                or not 1 <= self.timeout_seconds <= 180
                or not 128 <= self.structure_tokens <= 4096 or not 256 <= self.detail_tokens <= 4096):
            raise ValueError('INVALID_VISION_CONFIGURATION')


@dataclass
class VisionBudget:
    max_calls: int = 4
    max_tasks: int = 4
    max_pages: int = 4
    max_attempts_per_task: int = 2
    calls: int = field(default=0,init=False)
    tasks: set = field(default_factory=set,init=False)
    pages: set = field(default_factory=set,init=False)

    def __post_init__(self):
        if (any(type(v) is not int or not 0 <= v <= 64 for v in (self.max_calls,self.max_tasks,self.max_pages))
                or type(self.max_attempts_per_task) is not int or not 1 <= self.max_attempts_per_task <= 3):
            raise ValueError('INVALID_VISION_BUDGET')

    def acquire(self, page_id, fingerprint):
        if (self.calls >= self.max_calls or fingerprint not in self.tasks and len(self.tasks)>=self.max_tasks
                or page_id not in self.pages and len(self.pages)>=self.max_pages):
            return False
        self.calls += 1; self.tasks.add(fingerprint); self.pages.add(page_id)
        return True


@dataclass(frozen=True)
class VisionExecutionResult:
    page_id: str
    task: str
    status: str
    reason: str
    fingerprint: str | None = None
    analysis_id: str | None = None
    page_result_id: str | None = None
    calls: int = 0
    attempts: int = 0
    reused: bool = False


def receipt_root():
    from app.main import get_licitia_data_root
    return get_licitia_data_root() / 'vision-task-receipts-v1'


def invoke_canonical_task(config, task, page_number, image):
    """One canonical HTTP execution maximum. No probe, pull, or chained task."""
    from app.config import get_settings
    settings = get_settings().model_copy(update={
        'licitia_ollama_base_url': config.base_url,
        'licitia_ollama_vision_model': config.model,
        'licitia_ollama_timeout_seconds': config.timeout_seconds,
        'licitia_vision_retry_malformed_json': 0,
        'licitia_vision_structure_scope_max_output_tokens': config.structure_tokens,
        'licitia_vision_detail_transcription_max_output_tokens': config.detail_tokens})
    client = OllamaVisionAssistClient(settings)
    if task == 'STRUCTURE_SCOPE':
        return client.analyze_structure_scope_page(page_number=page_number,image_bytes=image,
            mode='ASSISTIVE_EXTRACTION',previous_page_context=None)
    return client.analyze_detail_transcription_page(page_number=page_number,image_bytes=image,
        mode='ASSISTIVE_EXTRACTION',region_hint=None)


def _write(path, receipt):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as output:
        json.dump(receipt,output,sort_keys=True)
        output.flush()
        import os
        os.fsync(output.fileno())
    temporary.replace(path)


def _validated_payload(task, payload, page_number, fingerprint):
    if not isinstance(payload,dict):
        raise ValueError('VISION_SCHEMA_INVALID')
    if (payload.get('_provider_response_meta') or {}).get('done_reason') == 'length':
        raise ValueError('VISION_TRUNCATED_RESPONSE')
    if task == 'STRUCTURE_SCOPE':
        parsed = VisionAssistModelPageResponse.model_validate(payload, strict=True)
        if parsed.page_number != page_number or not parsed.item_segments:
            raise ValueError('VISION_STRUCTURE_EMPTY_OR_WRONG_PAGE')
        # Model success cannot certify identity/continuity; downstream V.4a owns it.
        output = parsed.model_dump()
        for segment in output['item_segments']:
            segment['review_required'] = True
        output['_vision_runtime'] = dict(task_type=task,structure_schema_valid=True)
        return output,None
    parsed = VisionAssistModelDetailTranscriptionResponse.model_validate(payload, strict=True)
    if parsed.source_page != page_number or not parsed.raw_lines or any(not r.raw_visible_text.strip() for r in parsed.raw_lines):
        raise ValueError('VISION_DETAIL_EMPTY_OR_WRONG_PAGE')
    output = {}
    _merge_detail_transcription(structured_json=output,detail_structured_json=parsed.model_dump(),
        detail_task_fingerprint=fingerprint,detail_region_hint='')
    # Reuse canonical explicit textual grounding where available, without relabeling Vision.
    from app.native_scope_evidence import procurement_rows, explicit_fields
    for row in output['detail_transcription']['parsed_supply_rows']:
        grounded = procurement_rows(row['raw_visible_text'])
        if len(grounded) == 1:
            source = grounded[0]
            fields = explicit_fields(source.text)
            row.update(description=source.text,domain=source.domain,item_number=source.item_raw)
            row.update(fields)
        row['review_required'] = True
    output['_detail_runtime'] = dict(status='COMPLETED',schema_valid=True)
    text = '\n'.join(r.raw_visible_text for r in parsed.raw_lines)
    if '\x00' in text:
        raise ValueError('INVALID_VISION_TEXT')
    return output,text


def execute_planned_vision(db, plan: VisionPlan, *, config: VisionConfiguration,
                          budget: VisionBudget, invoke=invoke_canonical_task, render=render_ocr_input):
    task = plan.task.vision_task
    def result(status,reason,**kwargs):
        return VisionExecutionResult(plan.perception.page_id,task,status,reason,**kwargs)
    if not plan.eligible:
        return result('SKIPPED',plan.reason)
    if plan.perception.execution_policy != 'AUTO':
        return result('DEFERRED','POLICY_NO_VISION_ACQUISITION')
    page = db.get(DocumentPage,plan.perception.page_id)
    if page is None:
        raise ValueError('PAGE_MISSING')
    document = db.get(TenderDocument,page.document_id)
    fresh = plan_document_vision_tasks(db,tender_id=document.tender_id,document_id=document.id,
        requests={page.id:(plan.task,)},execution_policy=plan.perception.execution_policy)[0]
    if plan != fresh:
        return result('DEFERRED','STALE_OR_UNBOUND_VISION_PLAN')
    region = next((r for r in page.regions if r.id==plan.task.visual_region_id),None)
    if region is None:
        return result('DEFERRED','VISUAL_SOURCE_REGION_MISSING')
    _verified_path(document)
    import fitz
    prompt = VISION_STRUCTURE_SCOPE_PROMPT_VERSION if task=='STRUCTURE_SCOPE' else VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION
    schema = VisionAssistModelPageResponse if task=='STRUCTURE_SCOPE' else VisionAssistModelDetailTranscriptionResponse
    identity = dict(policy=POLICY_VERSION,task=task,task_version=1,prompt_version=prompt,
        schema_sha256=_hash(_bytes(schema.model_json_schema())),provider='OLLAMA',model=config.model,
        model_revision=config.model_revision,endpoint=config.base_url.rstrip('/'),temperature=0,think=False,
        output_tokens=config.structure_tokens if task=='STRUCTURE_SCOPE' else config.detail_tokens,
        timeout_seconds=config.timeout_seconds,document_id=document.id,tender_id=document.tender_id,
        revision=document.revision_number,original_sha256=document.sha256,page_id=page.id,page_number=page.page_number,
        source_generation=plan.evidence_signature,region_id=region.id,
        coordinates=[region.x0,region.y0,region.x1,region.y1],zoom=2,renderer_version=fitz.VersionBind)
    slot = _hash(_bytes(identity))
    directory = receipt_root(); directory.mkdir(parents=True,exist_ok=True)
    path = directory/(slot+'.json')
    with (directory/(slot+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        receipt = None
        if path.exists():
            try:
                receipt = json.loads(path.read_text())
                if (type(receipt['attempts']) is not int or type(receipt['max_attempts']) is not int
                        or not 0 <= receipt['attempts'] <= receipt['max_attempts'] <= 3
                        or receipt['state'] not in {'PENDING','RUNNING','FAILED','COMPLETED'}):
                    raise ValueError('INVALID_ATTEMPT_LEDGER')
                if receipt['identity'] != identity or receipt['fingerprint'] != _hash(_bytes({**identity,'image_sha256':receipt['image_sha256']})):
                    raise ValueError('INCOMPATIBLE_RECEIPT')
            except (ValueError,KeyError,TypeError):
                return result('DEFERRED','INVALID_VISION_RECEIPT')
            fingerprint = receipt['fingerprint']
            if receipt['state']=='COMPLETED':
                row = db.get(DocumentVisionPageResult,receipt['page_result_id'])
                analysis = db.get(DocumentVisionAnalysis,receipt['analysis_id'])
                if (row is None or analysis is None or row.analysis_id != analysis.id or row.status!='COMPLETED'
                        or analysis.input_fingerprint_sha256!=fingerprint or row.image_sha256!=receipt['image_sha256']
                        or analysis.document_id!=document.id or analysis.tender_id!=document.tender_id
                        or row.document_page_id!=page.id or row.page_number!=page.page_number
                        or analysis.model_name!=config.model or analysis.prompt_version!=prompt
                        or _hash(_bytes(row.structured_json))!=receipt['payload_sha256']):
                    return result('DEFERRED','VISION_RECEIPT_RESULT_MISMATCH',fingerprint=fingerprint)
                return result('COMPLETED','REUSED_EQUIVALENT_TASK',fingerprint=fingerprint,
                    analysis_id=analysis.id,page_result_id=row.id,attempts=receipt['attempts'],reused=True)
            # Interrupted work is uncertain: fail closed instead of issuing another call.
            if receipt['state']=='RUNNING' or receipt['attempts']>=receipt['max_attempts']:
                return result('RETRY_EXHAUSTED','PERSISTENT_TASK_EXHAUSTION',fingerprint=fingerprint,attempts=receipt['attempts'])
        else:
            try:
                image = render(document,page,region)
                if not isinstance(image,bytes) or not image or len(image)>8_388_608:
                    raise ValueError('INVALID_VISION_RENDER')
            except Exception as exc:
                return result('RENDER_FAILED',str(exc))
            fingerprint = _hash(_bytes({**identity,'image_sha256':_hash(image)}))
            receipt = dict(identity=identity,fingerprint=fingerprint,image_sha256=_hash(image),
                attempts=0,max_attempts=budget.max_attempts_per_task,state='PENDING')
        # Re-render retry input and verify exact image; no altered generation reuse.
        if receipt['attempts']:
            try:
                image=render(document,page,region)
                if _hash(image)!=receipt['image_sha256']:
                    return result('DEFERRED','RETRY_RENDER_CHANGED',fingerprint=fingerprint)
            except Exception as exc:
                return result('RENDER_FAILED',str(exc),fingerprint=fingerprint)
        if not budget.acquire(page.id,fingerprint):
            return result('BUDGET_EXHAUSTED','RUN_VISION_BUDGET_EXHAUSTED',fingerprint=fingerprint,attempts=receipt['attempts'])
        receipt.update(state='RUNNING',attempts=receipt['attempts']+1)
        _write(path,receipt)  # Durable reservation precedes every actual provider call.
        status = None
        try:
            status,payload,timing,http,warnings,markdown,plain,raw = invoke(config,task,page.page_number,image)
            if status!='COMPLETED':
                raise ValueError('VISION_PROVIDER_'+str(status)+':'+str(warnings))
            structured,text = _validated_payload(task,payload,page.page_number,fingerprint)
            _verified_path(document)
        except Exception as exc:
            receipt.update(state='FAILED',error=str(exc))
            _write(path,receipt)
            return result('UNAVAILABLE' if status=='UNAVAILABLE' else 'FAILED',str(exc),fingerprint=fingerprint,calls=1,attempts=receipt['attempts'])
        provenance = dict(**identity,image_sha256=receipt['image_sha256'],task_fingerprint=fingerprint,
            attempts=receipt['attempts'],region_coordinates=identity['coordinates'])
        structured['_selective_vision'] = provenance
        if task=='DETAIL_TRANSCRIPTION':
            structured['detail_transcription']['task_region_id']=region.id
        analysis=DocumentVisionAnalysis(tender_id=document.tender_id,document_id=document.id,status='COMPLETED',
            model_name=config.model,prompt_version=prompt,input_fingerprint_sha256=fingerprint)
        db.add(analysis); db.flush()
        row=DocumentVisionPageResult(analysis_id=analysis.id,document_page_id=page.id,page_number=page.page_number,
            image_sha256=receipt['image_sha256'],status='COMPLETED',structured_json=structured,
            extracted_plain_text=text,processing_time_ms=timing,warnings=warnings)
        db.add(row); db.flush()
        receipt.update(state='COMPLETED',analysis_id=analysis.id,page_result_id=row.id,
            payload_sha256=_hash(_bytes(structured)))
        _write(path,receipt)
        return result('COMPLETED','VISION_ACQUIRED_REVIEW_REQUIRED',fingerprint=fingerprint,
            analysis_id=analysis.id,page_result_id=row.id,calls=1,attempts=receipt['attempts'])


def vision_metrics(plans,results):
    from collections import Counter
    return dict(needed=sum(p.eligible for p in plans),eligible=sum(p.eligible for p in plans),
        executed=sum(r.calls for r in results),reused=sum(r.reused for r in results),
        avoided=sum(p.status=='SUFFICIENT_FOR_TASK' for p in plans),
        failures=sum(r.status in {'FAILED','UNAVAILABLE','RENDER_FAILED'} for r in results),
        retries=sum(r.calls>0 and r.attempts>1 for r in results),
        retry_exhausted=sum(r.status=='RETRY_EXHAUSTED' for r in results),
        budget_exhausted=sum(r.status=='BUDGET_EXHAUSTED' for r in results),
        pending=sum(r.status not in {'COMPLETED','SKIPPED'} for r in results),
        tasks=dict(Counter(r.task for r in results)))


def vision_provider_metrics(results, config):
    """Adapt execution events to the existing validation collector contract."""
    from app.document_intelligence_validation_metrics import ProviderMetric
    return tuple(ProviderMetric(id=f'{r.fingerprint or r.page_id}:{i}',provider='OLLAMA',
        model=config.model,source_method='VISION',capability='STRUCTURE' if r.task=='STRUCTURE_SCOPE' else 'TRANSCRIPTION',
        status=r.status,calls=r.calls,page_id=r.page_id,execution_event=bool(r.calls),
        configuration=dict(policy=POLICY_VERSION,task=r.task,fingerprint=r.fingerprint,
            attempts=r.attempts,reason=r.reason,reused=r.reused,model_revision=config.model_revision))
        for i,r in enumerate(results))
