"""Bounded operational composition; source readiness and human activity stay separate."""
from typing import Literal
from pydantic import JsonValue
from fastapi import HTTPException
from app.bid_readiness import DIMENSIONS, Dimension, Status
from app.readiness_work import Contract, WorkItem, _items, work_summary

Bucket = Literal['BLOCKERS','REVIEW_REQUIRED','IN_PROGRESS','ATTENTION','ACCEPTED_RISKS','RESOLVED']
BUCKETS = ('BLOCKERS','REVIEW_REQUIRED','IN_PROGRESS','ATTENTION','ACCEPTED_RISKS','RESOLVED')


class BoardItem(Contract):
    work: WorkItem
    bucket: Bucket
    priority: int
    action_target: str
    source_target: str | None


class BoardDimension(Contract):
    dimension: Dimension
    status: Status
    blocker_count: int
    review_count: int
    warning_count: int
    open_work_count: int


class BoardRead(Contract):
    contract_version: Literal['readiness-board-v1']='readiness-board-v1'
    tender_id: str
    canonical_summary: dict[str,JsonValue]
    work_summary: dict[str,int]
    bucket_counts: dict[str,int]
    dimensions: list[BoardDimension]
    total_filtered: int
    offset: int
    limit: int
    items: list[BoardItem]
    notice: str='Vista operacional de registros rastreados; no certifica cumplimiento. Los conteos fuente y actividad tienen autoridades separadas.'


def project_item(item):
    issue=item.issue
    if item.lifecycle!='ACTIVE':bucket,priority='RESOLVED',4
    elif issue.severity=='BLOCKER':bucket,priority='BLOCKERS',0 if issue.status=='BLOCKED' else 2
    elif issue.severity=='REVIEW':bucket,priority='REVIEW_REQUIRED',1
    elif item.workflow_status in {'ACCEPTED_RISK','NOT_APPLICABLE'}:bucket,priority='ACCEPTED_RISKS',4
    elif item.workflow_status=='RESOLVED':bucket,priority='RESOLVED',4
    else:bucket,priority='ATTENTION',3
    # Activity can be in progress without demoting a blocker/review's canonical priority.
    if item.lifecycle=='ACTIVE' and item.workflow_status=='IN_REVIEW' and issue.severity=='WARNING':bucket='IN_PROGRESS'
    target=item.action_target
    root=f'/tenders/{item.tender_id}'
    if item.lifecycle=='ACTIVE':
        if item.dimension=='COMMERCIAL' and item.entity_type=='SCOPE':target=f'{root}/scopes/{item.entity_id}/commercial-line'
        elif item.entity_type=='QUANTITY' and issue.underlying.get('scope_id'):
            target=f"{root}/scope-review/{issue.underlying['scope_id']}"
        elif item.entity_type in {'REQUIREMENT','REQUESTED_EVIDENCE'}:
            target=f'{root}/requirement-matrix#{item.entity_id}'
    ref=issue.reference if issue else None
    source=f'{root}/documents/{ref.document_id}/content' if ref and ref.document_id else None
    if source and ref.page:source+=f'#page={ref.page}'
    return BoardItem(work=item,bucket=bucket,priority=priority,action_target=target,source_target=source)


def read_board(db,tender_id,*,dimension=None,severity=None,workflow_status=None,bucket=None,
               include_inactive=False,search='',offset=0,limit=50):
    if offset<0 or not 1<=limit<=200 or len(search)>200:raise HTTPException(422,'INVALID_BOARD_QUERY')
    canonical,work=_items(db,tender_id)
    rows=[project_item(i) for i in work]
    rows.sort(key=lambda r:(r.priority,DIMENSIONS.index(r.work.dimension),r.work.entity_type,r.work.entity_id,r.work.code,r.work.id))
    active=[i for i in work if i.lifecycle=='ACTIVE']
    dimensions=[]
    for d in canonical.dimensions:
        members=[i for i in active if i.dimension==d.dimension]
        counts=work_summary(members)
        dimensions.append(BoardDimension(dimension=d.dimension,status=d.status,
            blocker_count=sum(i.issue.severity=='BLOCKER' for i in members),
            review_count=sum(i.issue.severity=='REVIEW' for i in members),
            warning_count=sum(i.issue.severity=='WARNING' for i in members),open_work_count=counts['total_open']))
    query=search.strip().casefold()
    selected=[r for r in rows if (include_inactive or r.work.lifecycle=='ACTIVE')
        and (dimension is None or r.work.dimension==dimension)
        and (severity is None or r.work.issue is not None and r.work.issue.severity==severity)
        and (workflow_status is None or r.work.workflow_status==workflow_status)
        and (bucket is None or r.bucket==bucket)
        and (not query or query in ' '.join([r.work.dimension,r.work.code,r.work.entity_id,
             r.work.issue.summary if r.work.issue else '',str(r.work.issue.underlying.get('item_reference','')) if r.work.issue else '']).casefold())]
    return BoardRead(tender_id=tender_id,
        canonical_summary=canonical.model_dump(mode='json',include={'status','blocker_count','review_required_count','warning_count','total_issues'}),
        work_summary={**work_summary(work),'in_review':sum(i.workflow_status=='IN_REVIEW' for i in active)},bucket_counts={b:sum(r.bucket==b for r in rows) for b in BUCKETS},
        dimensions=dimensions,total_filtered=len(selected),offset=offset,limit=limit,items=selected[offset:offset+limit])
