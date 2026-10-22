"""Generic planned perception harness. No corpus selection or expected answers."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from sqlalchemy import select
from app.blind_selective_profile import SelectiveProfile
from app.document_perception_planner import (PerceptionTask,TaskRequest,VisionTaskRequest,
    plan_document_ocr_tasks,plan_document_vision_tasks,perception_metrics)
from app.selective_ocr_executor import execute_planned_ocr,bounded_local_ocr,OcrInvocation,_bytes,_hash
from app.selective_vision_executor import execute_planned_vision,invoke_canonical_task,VisionBudget,vision_metrics
from app.document_intelligence_validation_metrics import ProviderMetric,snapshot_tender,collect_metrics
from app.models import TenderDocument,DocumentPage,TenderScopeDetail


class ProtocolViolation(RuntimeError):
    pass


def plan_identity(plan):
    return _hash(_bytes(asdict(plan)))


class ProviderCallGuard:
    """Only registered fresh plans can reach the injected canonical clients."""
    def __init__(self,profile: SelectiveProfile,*,ocr=bounded_local_ocr,vision=invoke_canonical_task,event_sink=None):
        self.profile=profile;self._ocr=ocr;self._vision=vision
        self.planned={}
        class Events(list):
            def append(self,event):
                if event_sink:event_sink(event)
                super().append(event)
        self.events=Events();self.violations=[];self.ocr_calls=0;self.vision_calls=0

    def register(self,method,plan):
        self.planned[(method,plan_identity(plan))]=plan

    def reject(self,method,plan,reason):
        page_id=plan.perception.page_id if method=='VISION' else plan.page_id
        self.events.append(ProviderMetric(id=f'guard-{len(self.events)}',provider='GUARD',source_method=method,
            capability='TRANSCRIPTION',status='REJECTED',calls=0,page_id=page_id,execution_event=True,
            configuration={'reason':reason,'plan':plan_identity(plan),
                'perception_assessment':asdict(plan.assessment) if plan.assessment else None,
                'interpretation_assessment':asdict(plan.interpretation) if plan.interpretation else None}))
        self.violations.append(reason)
        raise ProtocolViolation(reason)

    def allowed(self,method,plan):
        p=plan.perception if method=='VISION' else plan
        if (method,plan_identity(plan)) not in self.planned:
            self.reject(method,plan,'UNPLANNED_PROVIDER_CALL')
        if (self.profile.profile!='SELECTIVE_PERCEPTION' or self.profile.execution_policy=='AVAILABLE_ONLY'
                or method=='VISION' and self.profile.execution_policy!='AUTO'
                or p.execution_policy!=self.profile.execution_policy
                or not (plan.eligible if method=='VISION' else plan.ocr_eligible)):
            self.reject(method,plan,'POLICY_OR_PLAN_REJECTED')

    def decision(self,method,plan,result):
        page_id=plan.perception.page_id if method=='VISION' else plan.page_id
        self.events.append(ProviderMetric(id=f'guard-{len(self.events)}',provider='PLANNER',source_method=method,
            capability='STRUCTURE' if method=='VISION' and plan.task.vision_task=='STRUCTURE_SCOPE' else 'TRANSCRIPTION',
            status='REUSED' if getattr(result,'reused',False) or result.reason=='REUSED_EQUIVALENT_COMPLETED' else result.status,
            calls=0,page_id=page_id,execution_event=True,
            configuration={'decision_only':True,'reason':result.reason,'fingerprint':result.fingerprint,
                'plan':plan_identity(plan),
                'perception_assessment':asdict(plan.assessment) if plan.assessment else None,
                'interpretation_assessment':asdict(plan.interpretation) if plan.interpretation else None}))

    def ocr(self,plan,engine,image,language,timeout):
        self.allowed('OCR',plan)
        policy=self.profile.ocr
        expected={'TESSERACT':{'es+en':'spa+eng','es':'spa','en':'eng'},
                  'PADDLEOCR':{'es+en':'es','es':'es','en':'en'}}[policy.engine][policy.language]
        if engine!=policy.engine or language!=expected or timeout!=policy.timeout_seconds:
            self.reject('OCR',plan,'OCR_CONFIGURATION_MISMATCH')
        if self.ocr_calls>=policy.max_calls:
            # Normal budget deferral: never enter the actual client.
            self.events.append(ProviderMetric(id=f'guard-{len(self.events)}',provider=engine,source_method='OCR',
                capability='TRANSCRIPTION',status='BUDGET_EXHAUSTED',calls=0,page_id=plan.page_id,
                execution_event=True,configuration={'plan':plan_identity(plan)}))
            return OcrInvocation('UNAVAILABLE',False,error='OCR_AGGREGATE_BUDGET_EXHAUSTED')
        self.ocr_calls+=1
        start=datetime.now(timezone.utc)
        output=None
        try:
            output=self._ocr(engine,image,language,timeout)
            return output
        finally:
            # Unknown execution ACK stays unknown; do not claim zero calls on timeout.
            calls=None if output is None or output.invoked is None else int(output.invoked)
            self.events.append(ProviderMetric(id=f'guard-{len(self.events)}',provider=engine,source_method='OCR',
                capability='TRANSCRIPTION',status=output.status if output else 'FAILED',calls=calls,
                page_id=plan.page_id,execution_event=True,
                latency_ms=int((datetime.now(timezone.utc)-start).total_seconds()*1000),
                configuration={'plan':plan_identity(plan),'engine_version':policy.engine_version,
                    'attempt_reserved':self.ocr_calls,'language':language}))

    def vision(self,plan,config,task,number,image):
        self.allowed('VISION',plan)
        if config!=self.profile.vision.configuration() or task!=plan.task.vision_task:
            self.reject('VISION',plan,'VISION_CONFIGURATION_MISMATCH')
        if self.vision_calls>=self.profile.vision.max_calls:
            self.reject('VISION',plan,'VISION_CALL_BUDGET_BYPASS')
        self.vision_calls+=1
        start=datetime.now(timezone.utc);status='FAILED'
        try:
            output=self._vision(config,task,number,image);status=output[0]
            return output
        finally:
            self.events.append(ProviderMetric(id=f'guard-{len(self.events)}',provider='OLLAMA',source_method='VISION',
                model=config.model,capability='STRUCTURE' if task=='STRUCTURE_SCOPE' else 'TRANSCRIPTION',
                status=status,calls=1,page_id=plan.perception.page_id,execution_event=True,
                latency_ms=int((datetime.now(timezone.utc)-start).total_seconds()*1000),
                configuration={'plan':plan_identity(plan),'task':task,'model_revision':config.model_revision}))


def construct_tasks(db,document,profile):
    """Frozen task contracts + canonical pages/regions only; no names or expected answers.

    Spatial contracts are explicit questions about image layout, not inferred
    from low confidence or OCR failure. A plain IMAGE does not create a contract.
    """
    pages=db.scalars(select(DocumentPage).where(DocumentPage.document_id==document.id)
        .order_by(DocumentPage.page_number)).all()
    ocr={};vision={}
    for page in pages:
        base=tuple(TaskRequest(t) for t in PerceptionTask)
        images=tuple(r for r in sorted(page.regions,key=lambda r:r.region_index) if r.region_type=='IMAGE'
            and all(math.isfinite(v) for v in (r.x0,r.y0,r.x1,r.y1)) and r.x1>r.x0 and r.y1>r.y0)
        # Evaluate sufficiency before any region-specific work to avoid decorative images.
        evaluated=plan_document_ocr_tasks(db,tender_id=document.tender_id,document_id=document.id,
            requests={page.id:base},execution_policy=profile.execution_policy)
        work=[];visual=[]
        for p in evaluated:
            if not p.ocr_eligible or not images:
                work.append(p.request)
            else:
                work.extend(TaskRequest(p.request.task,region_id=r.id) for r in images)
        for contract in profile.spatial_contracts:
            task=PerceptionTask.STRUCTURE if contract.task=='STRUCTURE_SCOPE' else PerceptionTask.SCOPE
            # Already sufficient task needs no separate spatial recovery.
            if any(p.request.task==task and p.native_sufficient for p in evaluated):
                continue
            for region in images:
                request=TaskRequest(task,visual_relationships_required=True)
                visual.append(VisionTaskRequest(request,contract.task,region.id,'SPATIAL_RELATIONSHIP'))
        ocr[page.id]=tuple(work);vision[page.id]=tuple(visual)
    return ocr,vision


from app.canonical_materialization import materialize_canonical  # compatibility export


@dataclass(frozen=True)
class HarnessResult:
    plans: tuple
    ocr_results: tuple
    vision_plans: tuple
    vision_results: tuple
    providers: tuple
    perception_metrics: dict
    snapshot: object
    metrics: dict


def execute_selective_pipeline(db,*,tender_id,profile,ocr=bounded_local_ocr,vision=invoke_canonical_task,
                               prepare=None,materialize=materialize_canonical,event_sink=None):
    """Authorized caller controls run freeze/DB. Tests inject only client doubles."""
    from app.document_intelligence_blind_run import prepare_tender_documents
    (prepare or prepare_tender_documents)(db,tender_id=tender_id)
    # Plan persisted scalar types (not pre-flush int coordinates in a Float column).
    db.flush();db.expire_all()
    documents=db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tender_id)
        .order_by(TenderDocument.id)).all()
    guard=ProviderCallGuard(profile,ocr=ocr,vision=vision,event_sink=event_sink)
    budget=VisionBudget(max_calls=profile.vision.max_calls,max_tasks=profile.vision.max_tasks,
        max_pages=profile.vision.max_pages,max_attempts_per_task=profile.vision.max_attempts)
    plans=[];outputs=[];vplans=[];voutputs=[]
    for document in documents:
        requests,visual=construct_tasks(db,document,profile)
        # Spatial-only contracts never force a preceding OCR task for that capability.
        for page_id,tasks in requests.items():
            spatial_types={v.request.task for v in visual[page_id]}
            for request in tasks:
                if request.task in spatial_types:
                    continue
                plan=plan_document_ocr_tasks(db,tender_id=tender_id,document_id=document.id,
                    requests={page_id:(request,)},execution_policy=profile.execution_policy)[0]
                plans.append(plan);guard.register('OCR',plan)
                result=execute_planned_ocr(db,plan,engine=profile.ocr.engine,engine_version=profile.ocr.engine_version,
                    language=profile.ocr.language,timeout_seconds=profile.ocr.timeout_seconds,
                    invoke=lambda *args,p=plan:guard.ocr(p,*args))
                outputs.append(result);guard.decision('OCR',plan,result)
                if guard.violations:raise ProtocolViolation(guard.violations[-1])
                if result.reason=='OCR_AGGREGATE_BUDGET_EXHAUSTED':
                    # No transcript was acquired; keep explicit pending state.
                    continue
        # Re-evaluate only after OCR; task construction is independent of its failures.
        for page_id,tasks in visual.items():
            for request in tasks:
                # Keep the original spatial question and source-region binding.
                # The planner may discharge it only with proven equivalent
                # relationships; generic readable OCR is not spatial evidence.
                plan=plan_document_vision_tasks(db,tender_id=tender_id,document_id=document.id,
                    requests={page_id:(request,)},execution_policy=profile.execution_policy)[0]
                vplans.append(plan);guard.register('VISION',plan)
                # The final executor check reports persistent exhaustion without another provider call.
                for _ in range(profile.vision.max_attempts+1):
                    result=execute_planned_vision(db,plan,config=profile.vision.configuration(),budget=budget,
                        invoke=lambda *args,p=plan:guard.vision(p,*args))
                    voutputs.append(result);guard.decision('VISION',plan,result)
                    if guard.violations:raise ProtocolViolation(guard.violations[-1])
                    if result.status not in {'FAILED','UNAVAILABLE'}:break
        db.commit()
    materialize(db,tender_id,documents)
    db.commit()
    snapshot=snapshot_tender(db,tender_id,authorized_import=True)
    from collections import Counter
    native_sources=[e for p in snapshot.perception if p['channel']=='NATIVE' for e in p['sources'] if e.get('text','').strip()]
    native=dict(pages_available=len({e['page']['document_page_id'] for e in native_sources}),
        documents_available=len({e['page']['document_id'] for e in native_sources}))
    metrics=dict(native=native,ocr=perception_metrics(plans,outputs),vision=vision_metrics(vplans,voutputs),
        ocr_states=dict(Counter(r.status for r in outputs)),vision_states=dict(Counter(r.status for r in voutputs)),
        ocr_reused=sum(r.reason=='REUSED_EQUIVALENT_COMPLETED' for r in outputs),
        ocr_exhausted=sum(r.reason=='RETRY_EXHAUSTED' for r in outputs),
        ocr_budget_exhausted=sum(r.reason=='OCR_AGGREGATE_BUDGET_EXHAUSTED' for r in outputs),
        vision_completed=sum(r.status=='COMPLETED' for r in voutputs),
        provenance_capabilities=dict(Counter(str((p.get('channel'),p.get('capability'))) for p in snapshot.perception)))
    snapshot=snapshot.model_copy(update={'providers':(*snapshot.providers,*guard.events)})
    return HarnessResult(tuple(plans),tuple(outputs),tuple(vplans),tuple(voutputs),tuple(guard.events),
        metrics,snapshot,collect_metrics(snapshot))
