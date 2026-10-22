"""Readiness-specific human activity, separate from canonical source truth."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sqlalchemy import select
from app.models import Tender, ReadinessWorkDecision
from app.bid_readiness import ReadinessItem, Dimension, Severity
from app.bid_readiness_service import read_bid_readiness
from app.commercial_projections import tender_readiness
from app.workspace_flow import read_workspace
from app.read_batch import canonical_read_batch

Workflow = Literal['OPEN','IN_REVIEW','RESOLVED','ACCEPTED_RISK','NOT_APPLICABLE']
Lifecycle = Literal['ACTIVE','RESOLVED_BY_SOURCE_CHANGE','OBSOLETE']


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')


class WorkUpdate(Contract):
    expected_revision: int=Field(ge=0,strict=True)
    expected_context_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    workflow_status: Workflow | None=None
    note: str | None=Field(default=None,max_length=4000)
    owner: str | None=Field(default=None,max_length=200)
    actor_label: str | None=Field(default=None,max_length=200)


class WorkEvent(Contract):
    revision: int
    workflow_status: Workflow
    note: str | None
    owner: str | None
    actor_label: str | None
    timestamp: datetime
    context_sha256: str


class WorkItem(Contract):
    id: str
    tender_id: str
    dimension: Dimension
    entity_type: str
    entity_id: str
    code: str
    issue: ReadinessItem | None
    lifecycle: Lifecycle
    workflow_status: Workflow
    recorded_workflow_status: Workflow | None
    annotation_stale: bool
    revision: int
    context_sha256: str
    note: str | None
    owner: str | None
    actor_label: str | None
    updated_at: datetime | None
    accepted_risk_allowed: bool
    canonical_blocker_remains: bool
    action_target: str


class WorkRead(Contract):
    contract_version: Literal['readiness-work-v1']='readiness-work-v1'
    tender_id: str
    canonical_summary: dict[str,JsonValue]
    work_summary: dict[str,int]
    total_filtered: int
    items: list[WorkItem]
    notice: str='Seguimiento humano; no modifica readiness canónico ni certifica cumplimiento. Owner/actor son declaraciones sin autenticación.'


def _context(db,tender_id):
    with canonical_read_batch(db,tender_id):
        canonical=read_bid_readiness(db,tender_id,batched=False)
        commercial=tender_readiness(db,tender_id)
        workspace=read_workspace(db,tender_id)
        payload={'readiness':canonical.model_dump(mode='json'),'commercial':commercial.state_reference,
                 'requirements':[(r.requirement_id,r.representation_fingerprint) for r in workspace.requirements.requirements]}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return canonical,digest


def _latest(db,tender_id):
    return list(db.scalars(select(ReadinessWorkDecision).where(ReadinessWorkDecision.tender_id==tender_id)
        .distinct(ReadinessWorkDecision.issue_id).order_by(ReadinessWorkDecision.issue_id,ReadinessWorkDecision.revision.desc())))


def _items(db,tender_id):
    canonical,digest=_context(db,tender_id)
    active={i.id:i for i in canonical.issues}
    by_id={r.issue_id:r for r in _latest(db,tender_id)}
    entities={(i.entity_type,i.entity_id) for i in canonical.items}
    result=[]
    for identity in sorted(set(active)|set(by_id)):
        issue=active.get(identity);row=by_id.get(identity)
        entity_type=issue.entity_type if issue else row.entity_type
        entity_id=issue.entity_id if issue else row.entity_id
        lifecycle='ACTIVE' if issue else 'RESOLVED_BY_SOURCE_CHANGE' if (entity_type,entity_id) in entities else 'OBSOLETE'
        stale=bool(issue and row and row.context_sha256!=digest)
        workflow='RESOLVED' if issue is None else 'OPEN' if stale or row is None else row.workflow_status
        result.append(WorkItem(id=identity,tender_id=tender_id,dimension=issue.dimension if issue else row.dimension,
            entity_type=entity_type,entity_id=entity_id,code=issue.code if issue else row.issue_code,
            issue=issue,lifecycle=lifecycle,workflow_status=workflow,
            recorded_workflow_status=row.workflow_status if row else None,annotation_stale=stale,
            revision=row.revision if row else 0,context_sha256=digest,note=row.note if row else None,
            owner=row.owner if row else None,actor_label=row.actor_label if row else None,updated_at=row.created_at.astimezone(timezone.utc) if row else None,
            accepted_risk_allowed=bool(issue and issue.severity=='WARNING'),
            canonical_blocker_remains=bool(issue and issue.severity=='BLOCKER'),
            action_target=issue.review_context if issue else f'/tenders/{tender_id}/workspace'))
    result.sort(key=lambda i:({'BLOCKER':0,'REVIEW':1,'WARNING':2}.get(i.issue.severity if i.issue else None,3),i.dimension,i.id))
    return canonical,result


def list_work(db,tender_id,*,dimension=None,severity=None,workflow_status=None,include_inactive=False,offset=0,limit=50):
    if offset<0 or not 1<=limit<=200:raise HTTPException(422,'INVALID_WORK_PAGE')
    canonical,items=_items(db,tender_id)
    active=[i for i in items if i.lifecycle=='ACTIVE']
    closed={'RESOLVED','ACCEPTED_RISK','NOT_APPLICABLE'}
    summary={'total_active':len(active),
        'total_open':sum(i.canonical_blocker_remains or i.workflow_status not in closed for i in active),
        'blockers_open':sum(i.canonical_blocker_remains for i in active),
        'review_items_open':sum(i.issue.severity=='REVIEW' and i.workflow_status!='RESOLVED' for i in active),
        'accepted_risks':sum(i.workflow_status=='ACCEPTED_RISK' for i in active),
        'resolved':sum(i.lifecycle=='RESOLVED_BY_SOURCE_CHANGE' for i in items),
        'obsolete':sum(i.lifecycle=='OBSOLETE' for i in items),
        'manually_closed_activity':sum(i.workflow_status=='RESOLVED' for i in active),
        'stale_annotations':sum(i.annotation_stale for i in active)}
    selected=[i for i in items if (include_inactive or i.lifecycle=='ACTIVE') and (dimension is None or i.dimension==dimension)
        and (severity is None or i.issue is not None and i.issue.severity==severity)
        and (workflow_status is None or i.workflow_status==workflow_status)]
    return WorkRead(tender_id=tender_id,canonical_summary=canonical.model_dump(mode='json',include={'status','blocker_count','review_required_count','warning_count','total_issues'}),
        work_summary=summary,total_filtered=len(selected),items=selected[offset:offset+limit])


def get_work(db,tender_id,issue_id):
    _,items=_items(db,tender_id)
    item=next((i for i in items if i.id==issue_id),None)
    if item is None:raise HTTPException(404,'READINESS_WORK_NOT_FOUND')
    return item


def update_work(db,tender_id,issue_id,payload):
    try:UUID(issue_id)
    except ValueError as exc:raise HTTPException(422,'INVALID_READINESS_WORK_ID') from exc
    if db.scalar(select(Tender).where(Tender.id==tender_id).with_for_update()) is None:
        raise HTTPException(404,'Tender not found')
    item=get_work(db,tender_id,issue_id)
    if item.lifecycle!='ACTIVE':raise HTTPException(409,'READINESS_ISSUE_NO_LONGER_ACTIVE')
    if item.revision!=payload.expected_revision or item.context_sha256!=payload.expected_context_sha256:
        raise HTTPException(409,'READINESS_WORK_CONTEXT_STALE')
    values=payload.model_dump(exclude_unset=True,exclude={'expected_revision','expected_context_sha256'})
    state=values.get('workflow_status') or item.workflow_status
    if state in {'ACCEPTED_RISK','NOT_APPLICABLE'} and not item.accepted_risk_allowed:
        raise HTTPException(422,'CANONICAL_BLOCKER_OR_REVIEW_NOT_ACCEPTABLE_AS_RISK')
    note=values.get('note',item.note);owner=values.get('owner',item.owner)
    actor=values.get('actor_label')
    if item.revision and not item.annotation_stale and (state,note,owner,actor)==(item.workflow_status,item.note,item.owner,item.actor_label):
        return item
    row=ReadinessWorkDecision(tender_id=tender_id,issue_id=issue_id,revision=item.revision+1,
        dimension=item.dimension,entity_type=item.entity_type,entity_id=item.entity_id,issue_code=item.code,
        context_sha256=item.context_sha256,workflow_status=state,note=note,owner=owner,actor_label=actor)
    db.add(row);db.flush()
    return item.model_copy(update={'revision':row.revision,'workflow_status':state,'recorded_workflow_status':state,
        'annotation_stale':False,'note':note,'owner':owner,'actor_label':actor,'updated_at':row.created_at.astimezone(timezone.utc)})


def work_history(db,tender_id,issue_id,*,limit=25,before_revision=None):
    if db.get(Tender,tender_id) is None:raise HTTPException(404,'Tender not found')
    if not 1<=limit<=100 or before_revision is not None and before_revision<1:raise HTTPException(422,'INVALID_WORK_HISTORY_PAGE')
    query=select(ReadinessWorkDecision).where(ReadinessWorkDecision.tender_id==tender_id,ReadinessWorkDecision.issue_id==issue_id)
    if before_revision is not None:query=query.where(ReadinessWorkDecision.revision<before_revision)
    rows=list(db.scalars(query.order_by(ReadinessWorkDecision.revision.desc()).limit(limit)))
    return [WorkEvent(revision=r.revision,workflow_status=r.workflow_status,note=r.note,owner=r.owner,actor_label=r.actor_label,
        timestamp=r.created_at.astimezone(timezone.utc),context_sha256=r.context_sha256) for r in rows]
