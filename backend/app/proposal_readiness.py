"""M8-D typed proposal handoff and immutable product snapshots, no generation."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session
from app.database import engine
from app.models import Tender, TenderDocument, ProposalReadinessSnapshot
from app.bid_readiness import Dimension, Severity, Status
from app.readiness_work import Contract, Workflow, _items
from app.read_batch import canonical_read_batch
from app.commercial_matrix import read_matrix
from app.commercial_projections import proposal_projection
from app.workspace_flow import read_workspace

Eligibility = Literal['ELIGIBLE','ELIGIBLE_WITH_WARNINGS','NOT_ELIGIBLE','REVIEW_REQUIRED']
SCHEMA = '20261022_proposal_snapshot_075'


def get_proposal_db():
    # New connection/transaction per request; no global isolation change or edit locks.
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with Session(bind=connection,autoflush=False) as db:
            yield db


def canonical_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical_bytes(value)).hexdigest()


class SourceRef(Contract):
    document_id: str | None
    revision: int | None
    page: int | None
    locator: str | None
    excerpt_sha256: str | None


class StateItem(Contract):
    id: str
    dimension: Dimension
    entity_type: str
    entity_id: str
    status: Status
    severity: Severity | None
    code: str
    reference: SourceRef | None
    parent_scope_id: str | None=None
    parent_requirement_id: str | None=None


class WorkflowRef(Contract):
    issue_id: str
    revision: int
    workflow_status: Workflow
    recorded_workflow_status: Workflow | None
    annotation_stale: bool
    note: str | None
    owner: str | None
    actor_label: str | None


class HandoffRow(Contract):
    tender_id: str
    scope_id: str
    item_reference: str | None
    description: str
    quantity_id: str
    quantity_scope_id: str
    quantity_tender_id: str
    quantity: str
    unit: str | None
    commercial_line_id: str
    commercial_revision: int
    price_value_origin: Literal['CONFIRMED_QUOTE','HISTORICAL_COST','SYSTEM_ESTIMATE','MANUAL_INPUT']
    price_method: Literal['MANUAL','CALCULATED']
    offered_unit_price: str
    offered_total: str
    currency: str
    source: SourceRef
    quantity_source: SourceRef
    warnings: list[str]

    @model_validator(mode='after')
    def ownership(self):
        if self.scope_id!=self.quantity_scope_id or self.tender_id!=self.quantity_tender_id:
            raise ValueError('PROPOSAL_QUANTITY_PARENT_MISMATCH')
        return self


class ProposalReadinessProjection(Contract):
    contract_version: Literal['proposal-readiness-v1']='proposal-readiness-v1'
    tender_id: str
    tender_title: str
    readiness_status: Status
    eligibility: Eligibility
    blockers: list[StateItem]
    reviews: list[StateItem]
    warnings: list[StateItem]
    accepted_risks: list[WorkflowRef]
    workflow: list[WorkflowRef]
    rows: list[HandoffRow]
    excluded_scope_ids: list[str]
    tracked_context: list[StateItem]
    requirement_representations: list[dict[str,str]]
    documents: list[dict[str,str|int|bool]]
    notice: str='Preparación de información rastreada para Proposal Builder; no certifica cumplimiento contractual. Revisión humana autoritativa. Quantity sólo lectura.'

    @model_validator(mode='after')
    def ownership(self):
        if any(r.tender_id!=self.tender_id for r in self.rows):raise ValueError('PROPOSAL_TENDER_MISMATCH')
        if len({r.scope_id for r in self.rows})!=len(self.rows):raise ValueError('PROPOSAL_DUPLICATE_SCOPE')
        return self


class Evaluation(Contract):
    input_sha256: str
    projection: ProposalReadinessProjection


def source_ref(source):
    if not source:return None
    doc=source.get('document_id') or source.get('source_document_id')
    excerpt=source.get('excerpt') or source.get('source_excerpt')
    return SourceRef(document_id=doc,revision=source.get('revision'),page=source.get('page',source.get('source_page')),
        locator=source.get('locator'),excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest() if excerpt else None)


def state_fingerprint(projection):
    value=projection.model_dump(mode='json')
    # Commercial revision may change for cost/contact-only edits, while proposal values stay equal.
    for row in value['rows']:row.pop('commercial_revision')
    return digest(value)


def eligibility(blockers,reviews,warnings,rows,excluded):
    if blockers or not rows and not reviews:return 'NOT_ELIGIBLE'
    if reviews or excluded:return 'REVIEW_REQUIRED'
    return 'ELIGIBLE_WITH_WARNINGS' if warnings else 'ELIGIBLE'


def evaluate(db,tender_id):
    with canonical_read_batch(db,tender_id):
        canonical,work=_items(db,tender_id,batched=False)
        matrix=read_matrix(db,tender_id)
        commercial=proposal_projection(db,tender_id)
        workspace=read_workspace(db,tender_id)
        tender=db.get(Tender,tender_id)
        by_scope={r['scope_id']:r for r in matrix['rows']}
        states=[StateItem(id=i.id,dimension=i.dimension,entity_type=i.entity_type,entity_id=i.entity_id,
            status=i.status,severity=i.severity,code=i.code,reference=source_ref(i.reference.model_dump(mode='json')) if i.reference else None,
            parent_scope_id=i.underlying.get('scope_id'),parent_requirement_id=i.underlying.get('requirement_id')) for i in canonical.items]
        rows=[]
        for row in commercial.rows:
            detail=by_scope[row.scope_id];context=detail['source']
            quantity=next(q for q in context['quantities'] if q['id']==context['selected_quantity_id'])
            rows.append(HandoffRow(tender_id=tender_id,scope_id=row.scope_id,item_reference=row.item_reference,
                description=row.description,quantity_id=quantity['id'],quantity_scope_id=quantity['scope_detail_id'],
                quantity_tender_id=quantity['tender_id'],quantity=row.quantity,unit=row.unit,
                commercial_line_id=detail['commercial_line_id'],commercial_revision=detail['revision'],
                price_value_origin=detail['price_value_origin'],price_method=detail['price_method'],
                offered_unit_price=row.offered_unit_price,offered_total=row.offered_total,currency=row.currency,
                source=source_ref(context['scope']['source']),quantity_source=source_ref(quantity['source']),warnings=row.warnings))
        rows.sort(key=lambda r:r.scope_id)
        workflows=[WorkflowRef(issue_id=i.id,revision=i.revision,workflow_status=i.workflow_status,
            recorded_workflow_status=i.recorded_workflow_status,annotation_stale=i.annotation_stale,
            note=i.note,owner=i.owner,actor_label=i.actor_label) for i in work if i.lifecycle=='ACTIVE' and i.revision]
        blockers=[s for s in states if s.severity=='BLOCKER'];reviews=[s for s in states if s.severity=='REVIEW'];warnings=[s for s in states if s.severity=='WARNING']
        excluded=sorted(r.scope_id for r in commercial.excluded)
        documents=[{'id':d.id,'revision':d.revision_number,'sha256':d.sha256,'is_current':d.is_current} for d in db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tender_id).order_by(TenderDocument.id))]
        projection=ProposalReadinessProjection(tender_id=tender_id,tender_title=tender.title,readiness_status=canonical.status,
            eligibility=eligibility(blockers,reviews,warnings,rows,excluded),blockers=blockers,reviews=reviews,warnings=warnings,
            accepted_risks=[w for w in workflows if w.workflow_status=='ACCEPTED_RISK'],workflow=workflows,
            rows=rows,excluded_scope_ids=excluded,tracked_context=states,documents=documents,
            requirement_representations=sorted([{'requirement_id':r.requirement_id,'representation_fingerprint':r.representation_fingerprint} for r in workspace.requirements.requirements],key=lambda r:r['requirement_id']))
        return Evaluation(input_sha256=state_fingerprint(projection),projection=projection)


class CreateSnapshot(Contract):
    request_id: UUID
    expected_input_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    acknowledge_warnings: bool=False
    actor_label: str | None=Field(default=None,max_length=200)


class SnapshotPayload(Contract):
    contract_version: Literal['proposal-readiness-snapshot-v1']='proposal-readiness-snapshot-v1'
    snapshot_id: str
    tender_id: str
    request_id: str
    request_sha256: str
    created_at: datetime
    actor_label: str | None
    warnings_acknowledged: bool
    input_sha256: str
    schema_revision: str
    application_contract: Literal['licitia-mvp08-v1']='licitia-mvp08-v1'
    projection: ProposalReadinessProjection

    @model_validator(mode='after')
    def consistency(self):
        if self.tender_id!=self.projection.tender_id or self.input_sha256!=state_fingerprint(self.projection):raise ValueError('SNAPSHOT_STATE_INCONSISTENT')
        if self.projection.eligibility not in {'ELIGIBLE','ELIGIBLE_WITH_WARNINGS'}:raise ValueError('SNAPSHOT_NOT_ELIGIBLE')
        if self.projection.warnings and not self.warnings_acknowledged:raise ValueError('SNAPSHOT_WARNINGS_UNACKNOWLEDGED')
        return self


class SnapshotRead(Contract):
    payload: SnapshotPayload
    payload_sha256: str


def verify_payload(payload,sha256):
    if digest(payload)!=sha256:raise ValueError('SNAPSHOT_HASH_MISMATCH')
    return SnapshotPayload.model_validate(payload)


def _verified(row):
    try:
        payload=verify_payload(row.payload,row.payload_sha256)
        metadata=(row.id,row.tender_id,row.request_id,row.request_sha256,row.created_at.astimezone(timezone.utc),row.actor_label,row.input_sha256)
        expected=(payload.snapshot_id,payload.tender_id,payload.request_id,payload.request_sha256,payload.created_at,payload.actor_label,payload.input_sha256)
        if metadata!=expected:raise ValueError('SNAPSHOT_METADATA_MISMATCH')
    except (ValueError,TypeError,KeyError) as exc:raise HTTPException(409,'SNAPSHOT_INTEGRITY_FAILURE') from exc
    return SnapshotRead(payload=payload,payload_sha256=row.payload_sha256)


def _snapshot(db,tender_id,snapshot_id):
    row=db.scalar(select(ProposalReadinessSnapshot).where(ProposalReadinessSnapshot.tender_id==tender_id,ProposalReadinessSnapshot.id==snapshot_id))
    if row is None:raise HTTPException(404,'PROPOSAL_SNAPSHOT_NOT_FOUND')
    return row


def get_snapshot(db,tender_id,snapshot_id):return _verified(_snapshot(db,tender_id,snapshot_id))


def create_snapshot(db,tender_id,request):
    request_sha=digest(request.model_dump(mode='json'))
    existing=db.scalar(select(ProposalReadinessSnapshot).where(ProposalReadinessSnapshot.tender_id==tender_id,ProposalReadinessSnapshot.request_id==str(request.request_id)))
    if existing:
        if existing.request_sha256!=request_sha:raise HTTPException(409,'SNAPSHOT_REQUEST_REUSED_WITH_DIFFERENT_INPUT')
        return _verified(existing)
    current=evaluate(db,tender_id)
    if current.input_sha256!=request.expected_input_sha256:raise HTTPException(409,'PROPOSAL_INPUT_STALE')
    if current.projection.eligibility not in {'ELIGIBLE','ELIGIBLE_WITH_WARNINGS'}:raise HTTPException(409,'PROPOSAL_NOT_PREPARED')
    if current.projection.warnings and not request.acknowledge_warnings:raise HTTPException(409,'PROPOSAL_WARNINGS_CONFIRMATION_REQUIRED')
    payload=SnapshotPayload(snapshot_id=str(uuid4()),tender_id=tender_id,request_id=str(request.request_id),request_sha256=request_sha,
        created_at=datetime.now(timezone.utc),actor_label=request.actor_label,warnings_acknowledged=request.acknowledge_warnings,
        input_sha256=current.input_sha256,schema_revision=SCHEMA,projection=current.projection)
    value=payload.model_dump(mode='json');sha=digest(value)
    row=ProposalReadinessSnapshot(id=payload.snapshot_id,tender_id=tender_id,request_id=payload.request_id,
        request_sha256=request_sha,created_at=payload.created_at,actor_label=payload.actor_label,input_sha256=payload.input_sha256,
        payload_sha256=sha,payload=value)
    db.add(row);db.flush()
    return _verified(row)


def freshness(db,tender_id,snapshot_id):
    snapshot=get_snapshot(db,tender_id,snapshot_id)
    current=evaluate(db,tender_id)
    return {'snapshot_id':snapshot_id,'state':'CURRENT' if snapshot.payload.input_sha256==current.input_sha256 else 'STALE','current_input_sha256':current.input_sha256}


def list_snapshots(db,tender_id,*,limit=20,before_id=None):
    if not 1<=limit<=50:raise HTTPException(422,'INVALID_SNAPSHOT_PAGE')
    current=evaluate(db,tender_id)
    query=select(ProposalReadinessSnapshot).where(ProposalReadinessSnapshot.tender_id==tender_id)
    if before_id:
        before=_snapshot(db,tender_id,before_id)
        query=query.where(or_(ProposalReadinessSnapshot.created_at<before.created_at,and_(ProposalReadinessSnapshot.created_at==before.created_at,ProposalReadinessSnapshot.id<before.id)))
    rows=list(db.scalars(query.order_by(ProposalReadinessSnapshot.created_at.desc(),ProposalReadinessSnapshot.id.desc()).limit(limit+1)))
    result=[]
    for row in rows[:limit]:
        snapshot=_verified(row)
        result.append({'snapshot_id':row.id,'created_at':snapshot.payload.created_at,'readiness_status':snapshot.payload.projection.readiness_status,
            'eligibility':snapshot.payload.projection.eligibility,'state':'CURRENT' if row.input_sha256==current.input_sha256 else 'STALE','payload_sha256':row.payload_sha256})
    return {'items':result,'next_before_id':rows[limit-1].id if len(rows)>limit else None}
