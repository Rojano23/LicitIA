"""Pure task-aware OCR planning. No filesystem, ORM, probes or acquisition."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib
from app.perception_sufficiency import (POLICY_VERSION, PerceptionAssessment, InterpretationAssessment,
    assess_perception, assess_interpretation, reconstruct_for_assessment)


class PerceptionTask(str, Enum):
    TEXT = 'TEXT'
    STRUCTURE = 'STRUCTURE'
    SCOPE = 'SCOPE'
    ATTRIBUTES = 'ATTRIBUTES'
    QUANTITIES = 'QUANTITIES'


@dataclass(frozen=True)
class TaskRequest:
    task: PerceptionTask
    # Explicit source-grounded anchors demanded by the caller's task contract.
    required_excerpts: tuple[str, ...] = ()
    region_id: str | None = None
    visual_relationships_required: bool = False


@dataclass(frozen=True)
class PerceptionPlan:
    page_id: str
    request: TaskRequest
    execution_policy: str
    native_sufficient: bool
    ocr_eligible: bool
    status: str
    reason: str
    input_signature: str
    source_identity: tuple[str, str, str] | None = None
    assessment: PerceptionAssessment | None = None
    interpretation: InterpretationAssessment | None = None


def plan_ocr(*, page_id: str, page_number: int, native_text: str,
             image_region_ids: tuple[str, ...], request: TaskRequest,
             execution_policy: str = 'AVAILABLE_ONLY', supported: bool = True, structured_blocks=()) -> PerceptionPlan:
    if execution_policy not in {'AVAILABLE_ONLY', 'ALLOW_OCR', 'AUTO'}:
        raise ValueError('UNSUPPORTED_EXECUTION_POLICY')
    if not isinstance(request.task, PerceptionTask):
        raise ValueError('UNSUPPORTED_PERCEPTION_TASK')
    if request.region_id is not None and request.region_id not in image_region_ids:
        raise ValueError('REGION_OUTSIDE_PAGE')
    assessment = assess_perception(native_text,request,supported=supported,blocks=structured_blocks)
    interpretation = (InterpretationAssessment('NOT_ATTEMPTED','CAPABILITY_UNAVAILABLE')
        if not supported else assess_interpretation(native_text,request,page_number=page_number,blocks=structured_blocks))
    def result(sufficient, eligible, status, reason):
        return PerceptionPlan(page_id, request, execution_policy, sufficient, eligible, status, reason,
            hashlib.sha256(repr((POLICY_VERSION,native_text,image_region_ids,page_number)).encode()).hexdigest(),
            assessment=assessment,interpretation=interpretation)
    if assessment.state == 'UNAVAILABLE':
        return result(False,False,'UNAVAILABLE',assessment.reason)
    if assessment.state == 'VISUAL_REQUIRED':
        return result(False,False,'VISUAL_CAPABILITY_PENDING',assessment.reason)
    if assessment.state == 'SUFFICIENT':
        review = interpretation.state in {'UNRESOLVED','AMBIGUOUS','REJECTED'}
        return result(True,False,'REVIEW_REQUIRED' if review else 'NATIVE_SUFFICIENT',
            interpretation.reason if review else 'TASK_CONTRACT_SATISFIED')
    if assessment.state == 'UNKNOWN':
        return result(False,False,'UNKNOWN',assessment.reason)
    # Eligibility follows a textual evidence gap bound to a real IMAGE, never
    # interpretation outcome. No image means an observable unresolved gap.
    if image_region_ids:
        return result(False,True,'OCR_NEEDED',assessment.reason)
    return result(False,False,'UNKNOWN','NO_PROVEN_OCR_SOURCE')


def perception_metrics(plans, results=()):
    from collections import Counter
    return dict(perception_states=dict(Counter(p.assessment.state for p in plans if p.assessment)),
        interpretation_states=dict(Counter(p.interpretation.state for p in plans if p.interpretation)),
        sufficiency_reasons=dict(Counter(p.assessment.reason for p in plans if p.assessment)),tasks=len(plans), pages=len({p.page_id for p in plans}),
        native_sufficient=sum(p.native_sufficient for p in plans),
        ocr_eligible=sum(p.ocr_eligible for p in plans),
        ocr_avoided=sum(p.native_sufficient for p in plans),
        ocr_executed=sum(r.executed is True for r in results),
        ocr_execution_unknown=sum(r.executed is None for r in results),
        ocr_completed=sum(r.status == 'COMPLETED' for r in results),
        ocr_failed=sum(r.status in {'FAILED', 'INVALID_OUTPUT', 'RENDER_FAILED'} for r in results),
        ocr_unavailable=sum(r.status in {'UNAVAILABLE', 'DEFERRED'} for r in results),
        visual_pending=sum(p.status == 'VISUAL_CAPABILITY_PENDING' for p in plans))


def plan_document_ocr_tasks(db, *, tender_id: str, document_id: str, requests,
                            execution_policy: str = 'AVAILABLE_ONLY'):
    """Canonical ORM boundary; every requested task retains its own decision."""
    from dataclasses import replace
    from sqlalchemy import select
    from app.models import TenderDocument, DocumentPage
    from app.main import _is_pdf_document
    from app.document_intelligence_sources import load_document_transcriptions
    document = db.get(TenderDocument, document_id)
    if document is None or document.tender_id != tender_id:
        raise ValueError('DOCUMENT_TENDER_MISMATCH')
    pages = {p.id: p for p in db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id))}
    if not set(requests).issubset(pages):
        raise ValueError('PAGE_OUTSIDE_DOCUMENT')
    transcriptions = load_document_transcriptions(db, document)
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    from app.structured_evidence_grounding import source_text
    artifacts = _enumerate_persisted_artifacts_for_document(db,tender_id=tender_id,document_id=document_id,pages=list(pages.values()))
    plans = []
    for page_id, tasks in requests.items():
        page = pages[page_id]
        observations = [e for e in transcriptions[page_id].candidates if e.source_method.value == 'NATIVE'
                        and e.lineage == 'ACTIVE' and e.quality.value in {'RELIABLE', 'REVIEW_REQUIRED'}]
        # Multiple differing Native generations cannot establish sufficiency.
        from app.models import NormalizedContent
        for observation in observations:
            source = db.get(NormalizedContent, observation.normalized_content_id)
            if source is None or hashlib.sha256(source.normalized_text.encode()).hexdigest() != source.content_sha256:
                raise ValueError('NATIVE_GENERATION_HASH_MISMATCH')
        texts = {e.text for e in observations}
        native = next(iter(texts)) if len(texts) == 1 else ''
        blocks = ()
        interpretation_limit = None
        source_artifact = next((a.artifact for a in artifacts.active if a.artifact.source_method == 'NATIVE'
                               and a.artifact.document_page_id == page_id),None)
        if source_artifact and native:
            source,text = source_text(db,source_artifact)
            blocks,interpretation_limit = reconstruct_for_assessment(source,text)
        images = tuple(r.id for r in page.regions if r.region_type == 'IMAGE')
        for task in tasks:
            plan = plan_ocr(page_id=page_id, page_number=page.page_number, native_text=native,
                image_region_ids=images, request=task, execution_policy=execution_policy,
                supported=_is_pdf_document(document),structured_blocks=blocks)
            if interpretation_limit is not None:
                plan = replace(plan,interpretation=interpretation_limit,
                    status='REVIEW_REQUIRED' if plan.native_sufficient else plan.status,
                    reason=interpretation_limit.reason if plan.native_sufficient else plan.reason)
            if len(texts) > 1:
                plan = replace(plan,native_sufficient=False,ocr_eligible=False,status='REVIEW_REQUIRED',
                    reason='NATIVE_GENERATIONS_AMBIGUOUS',
                    assessment=PerceptionAssessment('UNKNOWN','NATIVE_GENERATIONS_AMBIGUOUS'),
                    interpretation=InterpretationAssessment('AMBIGUOUS','NATIVE_GENERATIONS_AMBIGUOUS'))
            if page.text.strip() and not observations and _is_pdf_document(document):
                plan = replace(plan, native_sufficient=False, ocr_eligible=False, status='UNKNOWN', reason='NATIVE_NORMALIZATION_REQUIRED',
                    assessment=PerceptionAssessment('UNKNOWN','NATIVE_NORMALIZATION_REQUIRED'))
            plans.append(replace(plan, source_identity=(document.tender_id, document.id,
                f'{document.revision_number}:{document.sha256}')))
    return tuple(plans)


@dataclass(frozen=True)
class VisionTaskRequest:
    request: TaskRequest
    vision_task: str
    # Explicit evidence binding; a failure or low score is never this proof.
    visual_region_id: str | None = None
    visual_reason: str | None = None


@dataclass(frozen=True)
class VisionPlan:
    perception: PerceptionPlan
    task: VisionTaskRequest
    eligible: bool
    status: str
    reason: str
    evidence_signature: str
    assessment: PerceptionAssessment | None = None
    interpretation: InterpretationAssessment | None = None


def plan_document_vision_tasks(db, *, tender_id: str, document_id: str, requests,
                               execution_policy: str = 'AVAILABLE_ONLY'):
    """Pure persisted-evidence planning: no render, probes or providers."""
    from dataclasses import replace
    from app.models import TenderDocument, DocumentPage, NormalizedContent, PageOcrResult
    from app.document_intelligence_sources import load_document_transcriptions
    from sqlalchemy import select
    document = db.get(TenderDocument, document_id)
    base = plan_document_ocr_tasks(db, tender_id=tender_id, document_id=document_id,
        requests={p: tuple(t.request for t in tasks) for p,tasks in requests.items()},
        execution_policy=execution_policy)
    routes = load_document_transcriptions(db, document)
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    from app.structured_evidence_grounding import source_text
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id)).all()
    artifacts = _enumerate_persisted_artifacts_for_document(db,tender_id=tender_id,document_id=document_id,pages=pages)
    plans = []
    index = 0
    for page_id,tasks in requests.items():
        page = db.get(DocumentPage, page_id)
        for task in tasks:
            if task.vision_task not in {'STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION'}:
                raise ValueError('UNSUPPORTED_VISION_TASK')
            if (task.request.region_id and task.visual_region_id and task.request.visual_relationships_required
                    and task.request.region_id != task.visual_region_id):
                raise ValueError('VISION_REGION_BINDING_MISMATCH')
            if (task.request.task == PerceptionTask.STRUCTURE) != (task.vision_task == 'STRUCTURE_SCOPE'):
                raise ValueError('VISION_TASK_CAPABILITY_MISMATCH')
            p = base[index]; index += 1
            evidence = []
            bound_visual_region = task.visual_region_id if task.request.visual_relationships_required else None
            sufficient = p.native_sufficient and not bound_visual_region
            assessment = (PerceptionAssessment('VISUAL_REQUIRED' if task.request.visual_relationships_required else 'INSUFFICIENT',
                'BOUND_REGION_EVIDENCE_REQUIRED') if bound_visual_region else p.assessment)
            interpretation = p.interpretation
            for n in db.scalars(select(NormalizedContent).where(NormalizedContent.document_page_id == page_id)):
                if n.source_type not in {'OCR','NATIVE_TEXT','NATIVE_PDF'}:
                    continue
                if hashlib.sha256(n.normalized_text.encode()).hexdigest() != n.content_sha256:
                    raise ValueError('PERCEPTION_GENERATION_HASH_MISMATCH')
                evidence.append((n.id,n.content_sha256))
                if n.source_type != 'OCR' or not n.page_ocr_result_id:
                    continue
                row = db.get(PageOcrResult, n.page_ocr_result_id)
                from app.content_normalization import _normalize_text
                if (row is None or row.status != 'OCR_TEXT_EXTRACTED'
                        or _normalize_text(row.text) != n.normalized_text):
                    continue
                if row.document_page_id != page_id or n.region_id != row.region_id:
                    raise ValueError('OCR_SOURCE_SCOPE_MISMATCH')
                if n.engine is not None and n.engine != row.engine:
                    raise ValueError('OCR_SOURCE_ENGINE_MISMATCH')
                target_region = task.request.region_id or bound_visual_region
                if target_region and row.region_id != target_region:
                    continue
                # Textual sufficiency is independent of parser success. Explicit
                # spatial questions retain their separate capability demand.
                blocks = ()
                interpretation_limit = None
                artifact = next((a.artifact for a in artifacts.active if a.artifact.source_artifact_key == 'ocr-result:' + row.id),None)
                if artifact and n.engine == row.engine and n.region_id == row.region_id:
                    source,text = source_text(db,artifact)
                    blocks,interpretation_limit = reconstruct_for_assessment(source,text)
                probe = assess_perception(n.normalized_text,task.request,source_method='OCR',region_covered=True,blocks=blocks)
                observed = interpretation_limit or assess_interpretation(n.normalized_text,task.request,page_number=page.page_number,blocks=blocks)
                # Only proven same-region header or labelled row edges can
                # answer an item-layout question textually. Readable prose alone cannot discharge it.
                table_relation = (task.visual_reason in {'TABLE_RELATIONSHIP','SPATIAL_RELATIONSHIP'} and target_region
                    and blocks and all(b.source.region_id == target_region for b in blocks)
                    and any(any(e.kind == 'HEADER_OF' for e in b.relations) or
                            {'VALUE_FOR','UNIT_FOR'} <= {e.kind for e in b.relations} for b in blocks))
                if table_relation and task.request.visual_relationships_required:
                    probe = PerceptionAssessment('SUFFICIENT','GROUNDED_REGION_RELATIONSHIPS_AVAILABLE','OCR')
                if probe.state == 'SUFFICIENT':
                    sufficient = True
                    assessment,interpretation = probe,observed
            signature = hashlib.sha256(repr((POLICY_VERSION,sorted(evidence))).encode()).hexdigest()
            proven = (task.request.visual_relationships_required and task.visual_reason in {
                'SPATIAL_RELATIONSHIP','TABLE_RELATIONSHIP','GRAPHICAL_STRUCTURE'} and
                any(r.id == task.visual_region_id and r.region_type == 'IMAGE' for r in page.regions))
            if p.status == 'UNAVAILABLE':
                eligible,status,reason = False,'UNAVAILABLE',p.reason
                assessment,interpretation = p.assessment,p.interpretation
            elif sufficient:
                eligible,status,reason = False,'SUFFICIENT_FOR_TASK','NATIVE_OCR_SUFFICIENT'
            elif proven:
                eligible,status,reason = True,'VISUAL_CAPABILITY_PENDING','PROVEN_TASK_VISUAL_DEFICIT'
            else:
                eligible,status,reason = False,'REVIEW_REQUIRED','NO_PROVEN_VISUAL_SEMANTIC_DEFICIT'
            if p.status != 'UNAVAILABLE' and routes[page_id].conflicts:
                interpretation = InterpretationAssessment('AMBIGUOUS','PERCEPTION_VALUES_CONFLICT_REQUIRE_REVIEW')
            plans.append(VisionPlan(p,task,eligible,status,reason,signature,assessment,interpretation))
    return tuple(plans)
