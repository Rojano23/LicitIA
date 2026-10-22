"""M9-A proposal identity, draft configuration and frozen snapshot binding only."""
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,func,and_,or_
from app.models import Proposal,ProposalVersion,ProposalVersionEvent,Tender
from app.proposal_readiness import Contract,ProposalReadinessProjection,get_snapshot,freshness,digest

SectionType=Literal['IDENTIFICATION','TECHNICAL_SCOPE','REQUIREMENTS','REQUESTED_EVIDENCE','ECONOMIC','NOTES','ANNEX_REFERENCES']
SECTION_TYPES=('IDENTIFICATION','TECHNICAL_SCOPE','REQUIREMENTS','REQUESTED_EVIDENCE','ECONOMIC','NOTES','ANNEX_REFERENCES')


class SectionConfig(Contract):
    id: str=Field(max_length=64)
    type: SectionType
    order: int=Field(ge=0,le=999,strict=True)
    included: bool=True
    note: str | None=Field(default=None,max_length=4000)

    @model_validator(mode='after')
    def identity(self):
        if self.id!=self.type.lower():raise ValueError('SECTION_ID_TYPE_MISMATCH')
        return self


class ProposalConfig(Contract):
    title: str | None=Field(default=None,max_length=300)
    bidder_name: str | None=Field(default=None,max_length=300)
    bidder_reference: str | None=Field(default=None,max_length=200)
    currency_presentation: Literal['BY_CURRENCY','ORIGINAL']='BY_CURRENCY'
    notes: str | None=Field(default=None,max_length=4000)
    sections: list[SectionConfig]=Field(default_factory=list,max_length=7)

    @model_validator(mode='after')
    def unique_sections(self):
        if len({s.id for s in self.sections})!=len(self.sections) or len({s.order for s in self.sections})!=len(self.sections):
            raise ValueError('DUPLICATE_SECTION_ID_OR_ORDER')
        return self


def section_projection(config):
    overrides={s.type:s for s in config.sections}
    return sorted([overrides.get(t,SectionConfig(id=t.lower(),type=t,order=n*10)) for n,t in enumerate(SECTION_TYPES)],key=lambda s:(s.order,s.id))


class CreateProposal(Contract):
    request_id: UUID
    snapshot_id: UUID
    proposal_id: UUID | None=None
    previous_version_id: UUID | None=None
    configuration: ProposalConfig | None=None
    acknowledge_warnings: bool=False
    acknowledge_stale: bool=False
    actor_label: str | None=Field(default=None,max_length=200)
    origin: Literal['API','WORKSPACE']='API'

    @model_validator(mode='after')
    def chain(self):
        if (self.proposal_id is None)!=(self.previous_version_id is None):raise ValueError('EXPLICIT_PREVIOUS_VERSION_REQUIRED')
        return self


class UpdateProposal(Contract):
    expected_edit_revision: int=Field(ge=1,strict=True)
    configuration: ProposalConfig
    actor_label: str | None=Field(default=None,max_length=200)


class FreezeProposal(Contract):
    expected_edit_revision: int=Field(ge=1,strict=True)
    acknowledge_warnings: bool=False
    acknowledge_stale: bool=False
    actor_label: str | None=Field(default=None,max_length=200)


class ProposalRead(Contract):
    id: str
    proposal_id: str
    tender_id: str
    version: int
    previous_version_id: str | None
    snapshot_id: str
    snapshot_sha256: str
    snapshot_eligibility: str
    state: Literal['DRAFT','FROZEN']
    edit_revision: int
    is_latest: bool
    content_contract: Literal['proposal-builder-v1']='proposal-builder-v1'
    configuration: ProposalConfig
    sections: list[SectionConfig]
    created_at: datetime
    updated_at: datetime
    created_origin: str
    actor_label: str | None
    frozen_at: datetime | None
    frozen_actor_label: str | None
    frozen_sha256: str | None


class ProposalInput(Contract):
    contract_version: Literal['proposal-builder-v1']='proposal-builder-v1'
    proposal_id: str
    version_id: str
    version: int
    snapshot_id: str
    snapshot_sha256: str
    configuration: ProposalConfig
    sections: list[SectionConfig]
    handoff: ProposalReadinessProjection
    notice: str='Composición futura sobre snapshot fijo; sin recalcular precios/Quantity ni reinterpretar requisitos. No certifica cumplimiento.'


def _utc(value):return value.astimezone(timezone.utc) if value else None


def frozen_envelope(row):
    return {'contract_version':'proposal-builder-v1','id':row.id,'proposal_id':row.proposal_id,'tender_id':row.tender_id,
        'version':row.version,'previous_version_id':row.previous_version_id,'snapshot_id':row.snapshot_id,
        'snapshot_sha256':row.snapshot_sha256,'configuration':ProposalConfig.model_validate(row.configuration).model_dump(mode='json'),
        'created_at':_utc(row.created_at).isoformat(),'created_origin':row.created_origin,'actor_label':row.actor_label,
        'frozen_at':_utc(row.frozen_at).isoformat() if row.frozen_at else None,'frozen_actor_label':row.frozen_actor_label,
        'acknowledgements':row.freeze_acknowledgements,'content_contract':row.content_contract}


def _row(db,tender_id,version_id,*,lock=False):
    query=select(ProposalVersion).where(ProposalVersion.tender_id==tender_id,ProposalVersion.id==version_id)
    row=db.scalar(query)
    if row is None:raise HTTPException(404,'PROPOSAL_VERSION_NOT_FOUND')
    if lock:
        db.scalar(select(Proposal).where(Proposal.id==row.proposal_id,Proposal.tender_id==tender_id).with_for_update())
        row=db.scalar(query.with_for_update().execution_options(populate_existing=True))
    return row


def _latest(db,proposal_id):
    return db.scalar(select(ProposalVersion).where(ProposalVersion.proposal_id==proposal_id).order_by(ProposalVersion.version.desc()).limit(1))


def _verified(db,row):
    snapshot=get_snapshot(db,row.tender_id,row.snapshot_id)
    try:
        ProposalConfig.model_validate(row.configuration)
        if snapshot.payload_sha256!=row.snapshot_sha256:raise ValueError('SNAPSHOT_BINDING_HASH_MISMATCH')
        if row.content_contract!='proposal-builder-v1':raise ValueError('PROPOSAL_CONTRACT_UNSUPPORTED')
        if row.state=='FROZEN' and digest(frozen_envelope(row))!=row.frozen_sha256:raise ValueError('FROZEN_PROPOSAL_HASH_MISMATCH')
    except (ValueError,TypeError,KeyError) as exc:raise HTTPException(409,'PROPOSAL_INTEGRITY_FAILURE') from exc
    return snapshot


def _view(db,row,snapshot=None):
    snapshot=snapshot or _verified(db,row)
    config=ProposalConfig.model_validate(row.configuration)
    return ProposalRead(id=row.id,proposal_id=row.proposal_id,tender_id=row.tender_id,version=row.version,
        previous_version_id=row.previous_version_id,snapshot_id=row.snapshot_id,snapshot_sha256=row.snapshot_sha256,
        snapshot_eligibility=snapshot.payload.projection.eligibility,state=row.state,edit_revision=row.edit_revision,
        is_latest=_latest(db,row.proposal_id).id==row.id,configuration=config,sections=section_projection(config),
        created_at=_utc(row.created_at),updated_at=_utc(row.updated_at),created_origin=row.created_origin,actor_label=row.actor_label,
        frozen_at=_utc(row.frozen_at),frozen_actor_label=row.frozen_actor_label,frozen_sha256=row.frozen_sha256)


def read_version(db,tender_id,version_id):return _view(db,_row(db,tender_id,version_id))


def input_projection(db,tender_id,version_id):
    row=_row(db,tender_id,version_id);snapshot=_verified(db,row);config=ProposalConfig.model_validate(row.configuration)
    return ProposalInput(proposal_id=row.proposal_id,version_id=row.id,version=row.version,snapshot_id=row.snapshot_id,
        snapshot_sha256=row.snapshot_sha256,configuration=config,sections=section_projection(config),handoff=snapshot.payload.projection)


def source_state(db,tender_id,version_id):
    row=_row(db,tender_id,version_id);_verified(db,row)
    state=freshness(db,tender_id,row.snapshot_id)['state']
    return {'version_id':row.id,'snapshot_id':row.snapshot_id,'state':'SOURCE_SNAPSHOT_STALE' if state=='STALE' else 'CURRENT'}


def _confirm(db,tender_id,snapshot,request):
    if snapshot.payload.projection.eligibility not in {'ELIGIBLE','ELIGIBLE_WITH_WARNINGS'}:raise HTTPException(409,'PROPOSAL_SNAPSHOT_NOT_ELIGIBLE')
    if snapshot.payload.projection.warnings and not request.acknowledge_warnings:raise HTTPException(409,'PROPOSAL_WARNINGS_ACK_REQUIRED')
    state=freshness(db,tender_id,snapshot.payload.snapshot_id)['state']
    if state=='STALE' and not request.acknowledge_stale:raise HTTPException(409,'SOURCE_SNAPSHOT_STALE_ACK_REQUIRED')
    return state


def _event(db,row,action,actor,details):
    sequence=(db.scalar(select(func.max(ProposalVersionEvent.sequence)).where(ProposalVersionEvent.version_id==row.id)) or 0)+1
    db.add(ProposalVersionEvent(id=str(uuid4()),version_id=row.id,sequence=sequence,action=action,actor_label=actor,
        created_at=datetime.now(timezone.utc),details=details));db.flush()


def create_version(db,tender_id,request):
    request_hash=digest(request.model_dump(mode='json'))
    existing=db.scalar(select(ProposalVersion).where(ProposalVersion.tender_id==tender_id,ProposalVersion.request_id==str(request.request_id)))
    if existing:
        if existing.request_sha256!=request_hash:raise HTTPException(409,'PROPOSAL_REQUEST_REUSED')
        return _view(db,existing)
    snapshot=get_snapshot(db,tender_id,str(request.snapshot_id))
    state=_confirm(db,tender_id,snapshot,request)
    now=datetime.now(timezone.utc);previous=None
    if request.proposal_id:
        header=db.scalar(select(Proposal).where(Proposal.id==str(request.proposal_id),Proposal.tender_id==tender_id).with_for_update())
        if header is None:raise HTTPException(404,'PROPOSAL_NOT_FOUND')
        previous=_latest(db,header.id)
        if previous.id!=str(request.previous_version_id):raise HTTPException(409,'PROPOSAL_PREVIOUS_VERSION_STALE')
        _verified(db,previous)
    else:
        header=Proposal(id=str(uuid4()),tender_id=tender_id,created_at=now);db.add(header);db.flush()
    config=request.configuration or (ProposalConfig.model_validate(previous.configuration) if previous else ProposalConfig())
    row=ProposalVersion(id=str(uuid4()),proposal_id=header.id,tender_id=tender_id,snapshot_id=snapshot.payload.snapshot_id,
        snapshot_sha256=snapshot.payload_sha256,previous_version_id=previous.id if previous else None,
        version=previous.version+1 if previous else 1,edit_revision=1,state='DRAFT',content_contract='proposal-builder-v1',
        configuration=config.model_dump(mode='json'),created_at=now,updated_at=now,created_origin=request.origin,
        actor_label=request.actor_label,request_id=str(request.request_id),request_sha256=request_hash)
    db.add(row);db.flush()
    _event(db,row,'CREATED',request.actor_label,{'request_id':str(request.request_id),'snapshot_id':row.snapshot_id,'source_state':state,
        'warnings_acknowledged':request.acknowledge_warnings,'stale_acknowledged':request.acknowledge_stale,'configuration':row.configuration})
    if previous:_event(db,previous,'SUPERSEDED',request.actor_label,{'new_version_id':row.id})
    return _view(db,row,snapshot)


def _editable(db,row,revision):
    if row.state!='DRAFT':raise HTTPException(409,'FROZEN_PROPOSAL_IMMUTABLE')
    if _latest(db,row.proposal_id).id!=row.id:raise HTTPException(409,'HISTORICAL_PROPOSAL_DRAFT_IMMUTABLE')
    if row.edit_revision!=revision:raise HTTPException(409,'PROPOSAL_EDIT_REVISION_STALE')


def update_version(db,tender_id,version_id,request):
    row=_row(db,tender_id,version_id,lock=True);_verified(db,row);_editable(db,row,request.expected_edit_revision)
    config=request.configuration.model_dump(mode='json')
    if config!=row.configuration:
        previous=row.configuration;row.configuration=config;row.edit_revision+=1;row.updated_at=datetime.now(timezone.utc);db.flush()
        _event(db,row,'CONFIGURED',request.actor_label,{'previous_configuration':previous,'configuration':config})
    return _view(db,row)


def freeze_version(db,tender_id,version_id,request):
    row=_row(db,tender_id,version_id,lock=True);snapshot=_verified(db,row)
    request_hash=digest(request.model_dump(mode='json'))
    if row.state=='FROZEN':
        if row.freeze_acknowledgements['request_sha256']==request_hash:return _view(db,row,snapshot)
        raise HTTPException(409,'FROZEN_PROPOSAL_IMMUTABLE')
    _editable(db,row,request.expected_edit_revision)
    state=_confirm(db,tender_id,snapshot,request)
    row.state='FROZEN';row.frozen_at=datetime.now(timezone.utc);row.updated_at=row.frozen_at;row.frozen_actor_label=request.actor_label
    row.freeze_acknowledgements={'request_sha256':request_hash,'warnings':request.acknowledge_warnings,'stale':request.acknowledge_stale,'source_state':state}
    row.edit_revision+=1;row.frozen_sha256=digest(frozen_envelope(row));db.flush()
    _event(db,row,'FROZEN',request.actor_label,{'frozen_sha256':row.frozen_sha256,'source_state':state})
    return _view(db,row,snapshot)


def list_versions(db,tender_id,*,proposal_id=None,limit=20,before_id=None):
    if not 1<=limit<=50:raise HTTPException(422,'INVALID_PROPOSAL_PAGE')
    if db.get(Tender,tender_id) is None:raise HTTPException(404,'Tender not found')
    query=select(ProposalVersion).where(ProposalVersion.tender_id==tender_id)
    if proposal_id:query=query.where(ProposalVersion.proposal_id==proposal_id)
    if before_id:
        before=_row(db,tender_id,before_id)
        if proposal_id and before.proposal_id!=proposal_id:raise HTTPException(422,'PROPOSAL_CURSOR_MISMATCH')
        query=query.where(or_(ProposalVersion.created_at<before.created_at,and_(ProposalVersion.created_at==before.created_at,ProposalVersion.id<before.id)))
    rows=list(db.scalars(query.order_by(ProposalVersion.created_at.desc(),ProposalVersion.id.desc()).limit(limit+1)))
    latest=dict(db.execute(select(ProposalVersion.proposal_id,func.max(ProposalVersion.version)).where(ProposalVersion.proposal_id.in_([r.proposal_id for r in rows])).group_by(ProposalVersion.proposal_id)).all())
    return {'items':[{'id':r.id,'proposal_id':r.proposal_id,'version':r.version,'snapshot_id':r.snapshot_id,'state':r.state,
        'created_at':_utc(r.created_at),'is_latest':r.version==latest[r.proposal_id]} for r in rows[:limit]],'next_before_id':rows[limit-1].id if len(rows)>limit else None}


def version_history(db,tender_id,version_id,*,limit=25,before_sequence=None):
    if not 1<=limit<=100 or before_sequence is not None and before_sequence<1:raise HTTPException(422,'INVALID_PROPOSAL_AUDIT_PAGE')
    _row(db,tender_id,version_id)
    query=select(ProposalVersionEvent).where(ProposalVersionEvent.version_id==version_id)
    if before_sequence is not None:query=query.where(ProposalVersionEvent.sequence<before_sequence)
    rows=list(db.scalars(query.order_by(ProposalVersionEvent.sequence.desc()).limit(limit)))
    return [{'sequence':r.sequence,'action':r.action,'actor_label':r.actor_label,'created_at':_utc(r.created_at),'details':r.details} for r in rows]
