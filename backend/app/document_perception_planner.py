"""Pure task-aware OCR planning. No filesystem, ORM, probes or acquisition."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re
import hashlib
from app.native_scope_evidence import procurement_rows, explicit_fields
from app.page_structure_resolver import structural_candidate_from_native_text


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


def plan_ocr(*, page_id: str, page_number: int, native_text: str,
             image_region_ids: tuple[str, ...], request: TaskRequest,
             execution_policy: str = 'AVAILABLE_ONLY', supported: bool = True) -> PerceptionPlan:
    if execution_policy not in {'AVAILABLE_ONLY', 'ALLOW_OCR', 'AUTO'}:
        raise ValueError('UNSUPPORTED_EXECUTION_POLICY')
    if not isinstance(request.task, PerceptionTask):
        raise ValueError('UNSUPPORTED_PERCEPTION_TASK')
    if request.region_id is not None and request.region_id not in image_region_ids:
        raise ValueError('REGION_OUTSIDE_PAGE')
    def result(sufficient, eligible, status, reason):
        return PerceptionPlan(page_id, request, execution_policy, sufficient, eligible, status, reason,
            hashlib.sha256(repr((native_text, image_region_ids, page_number)).encode()).hexdigest())
    if not supported:
        return result(False, False, 'UNAVAILABLE', 'UNSUPPORTED_NATIVE_CAPABILITY')
    if request.task == PerceptionTask.TEXT and not request.required_excerpts and native_text.strip() and request.region_id is None:
        return result(False, False, 'UNKNOWN', 'TEXT_TASK_CONTRACT_REQUIRED')
    if request.visual_relationships_required:
        return result(False, False, 'VISUAL_CAPABILITY_PENDING', 'VISUAL_RELATIONSHIP_REQUIRES_V4C2')
    anchors = bool(request.required_excerpts) and all(
        anchor.strip() and anchor in native_text for anchor in request.required_excerpts)
    structure = structural_candidate_from_native_text(page_number=page_number, native_text=native_text)
    identity_valid = structure.structural_quality == 'VALID' and not structure.page_state.review_required
    rows = procurement_rows(native_text)
    sufficient = False
    identity_review = False
    if request.task == PerceptionTask.TEXT:
        # A task must declare what text it needs; non-empty alone proves nothing.
        sufficient = anchors
    elif request.task == PerceptionTask.STRUCTURE:
        sufficient = identity_valid and (anchors or not request.required_excerpts)
    else:
        for row in rows:
            if request.required_excerpts and not all(a.strip() and a in row.text for a in request.required_excerpts):
                continue
            try:
                fields = explicit_fields(row.text)
            except ValueError:
                continue
            if request.task == PerceptionTask.SCOPE:
                identity_review = not identity_valid
                sufficient = identity_valid
            elif request.task == PerceptionTask.ATTRIBUTES:
                sufficient = identity_valid and bool(fields.get('brand') or fields.get('model'))
            elif request.task == PerceptionTask.QUANTITIES:
                from app.scope_quantity_adapters import _unit_to_measure_kind
                sufficient = identity_valid and bool(re.fullmatch(r'\d+(?:\.\d+)?', fields.get('quantity', ''))) and bool(_unit_to_measure_kind(fields.get('unit', '')))
            if sufficient:
                break
    if request.region_id is not None:
        sufficient = False  # No Native region binding proves coverage of this image.
    if sufficient:
        return result(True, False, 'NATIVE_SUFFICIENT', 'TASK_CONTRACT_SATISFIED')
    if identity_review and request.region_id is None:
        return result(False, False, 'REVIEW_REQUIRED', 'DOMAIN_IDENTITY_REVIEW_NOT_OCR_GAP')
    # Images only establish eligibility, never that OCR can recover semantics.
    if image_region_ids:
        return result(False, True, 'OCR_NEEDED', 'TASK_CONTRACT_NOT_SATISFIED_BY_NATIVE')
    return result(False, False, 'UNKNOWN', 'NO_PROVEN_OCR_SOURCE')


def perception_metrics(plans, results=()):
    return dict(tasks=len(plans), pages=len({p.page_id for p in plans}),
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
        images = tuple(r.id for r in page.regions if r.region_type == 'IMAGE')
        for task in tasks:
            plan = plan_ocr(page_id=page_id, page_number=page.page_number, native_text=native,
                image_region_ids=images, request=task, execution_policy=execution_policy,
                supported=_is_pdf_document(document))
            if page.text.strip() and not observations and _is_pdf_document(document):
                plan = replace(plan, ocr_eligible=False, status='UNKNOWN', reason='NATIVE_NORMALIZATION_REQUIRED')
            plans.append(replace(plan, source_identity=(document.tender_id, document.id,
                f'{document.revision_number}:{document.sha256}')))
    return tuple(plans)
