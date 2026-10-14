"""Human-approved structural calibration; offline measurement, never production policy."""
from __future__ import annotations
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from app.document_intelligence_structural_golden import Contract,Groups,PageCandidate,CandidatePack,TENDER_ID,DOCUMENT_ID,SHA

class ApprovedPage(PageCandidate):
    approval_status: Literal['APPROVED']='APPROVED'
    approved_by_human: Literal[True]=True
    approval_revision: str=Field(min_length=1)
    @model_validator(mode='after')
    def human_sources(self):
        if any(r.authority=='MODEL_DERIVED' for r in self.supporting_references):
            raise ValueError('Model-derived evidence cannot establish Golden truth')
        return self

class ApprovedGolden(Contract):
    schema_version: Literal['1']='1'
    artifact_kind: Literal['HUMAN_APPROVED_STRUCTURAL_GOLDEN']='HUMAN_APPROVED_STRUCTURAL_GOLDEN'
    canonical_golden: Literal[True]=True
    golden_id: str=Field(min_length=1)
    approval_status: Literal['APPROVED']='APPROVED'
    approved_by_human: Literal[True]=True
    approval_revision: str=Field(min_length=1)
    approval_statement: str=Field(min_length=1)
    content_sha256: str=Field(pattern=SHA)
    content_hash_contract: Literal['SHA256 canonical JSON excluding content_sha256']='SHA256 canonical JSON excluding content_sha256'
    pages: tuple[ApprovedPage,...]
    @model_validator(mode='after')
    def coherent(self):
        if [p.page_number for p in self.pages]!=[1,2,3,4]:
            raise ValueError('Approved B-4 source must cover exactly pages 1–4 in order')
        if len({(p.document_version,p.source_document_sha256,p.source_path) for p in self.pages})!=1:
            raise ValueError('Golden must preserve one original/version')
        if any(p.approval_revision!=self.approval_revision for p in self.pages):
            raise ValueError('Approval revision must match page approvals')
        return self

class PageApproval(Contract):
    page_number: int=Field(ge=1,le=4)
    source_page_hash: str=Field(pattern=SHA)
    incoming_group: Groups
    outgoing_group: Groups
    starts_item: Groups
    continues_item: Groups
    closes_item: Groups
    structural_review_expected: bool
    events: tuple[tuple[str,str],...]

class HumanApproval(Contract):
    tender_id: Literal['decd32ae-2c1f-4520-89bc-d845c986a7ba']
    document_id: Literal['acf31750-1d8d-4a0c-910c-fc3743930c57']
    source_document_sha256: str=Field(pattern=SHA)
    approval_revision: str=Field(min_length=1)
    approved_by_human: Literal[True]
    statement: str=Field(min_length=1)
    pages: tuple[PageApproval,...]


def canonical_bytes(value: dict)->bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def digest(value: dict)->str:
    return hashlib.sha256(canonical_bytes({k:v for k,v in value.items() if k!='content_sha256'})).hexdigest()


def freeze_golden(candidate: CandidatePack,approval: HumanApproval,path: Path)->ApprovedGolden:
    """Requires explicit structured human input. Never ingests a model result."""
    if path.name!='document_intelligence_b4_structure_golden_v1.json' or path.parent.name!='evals':
        raise ValueError('Frozen Golden has a dedicated evals path')
    if {p.page_number for p in approval.pages}!={1,2,3,4} or len(approval.pages)!=4:
        raise ValueError('Explicit approval of all four pages required')
    approvals={p.page_number:p for p in approval.pages};pages=[]
    for page in sorted(candidate.pages,key=lambda p:p.page_number):
        decision=approvals[page.page_number]
        if page.source_document_sha256!=approval.source_document_sha256 or page.source_page_hash!=decision.source_page_hash:
            raise ValueError('Approval source hashes differ from candidate')
        for field in ('incoming_group','outgoing_group','starts_item','continues_item','closes_item','structural_review_expected'):
            if getattr(page,field)!=getattr(decision,field):
                raise ValueError('This approval authorizes unchanged candidate labels only')
        if tuple((e.event_type,e.group) for e in page.boundary_events)!=decision.events:
            raise ValueError('Approved ordered events differ from candidate')
        value=page.model_dump(mode='json');value.update(approval_status='APPROVED',approved_by_human=True,approval_revision=approval.approval_revision)
        pages.append(ApprovedPage.model_validate(value))
    value=dict(golden_id='b4-human-structure-v1',approval_revision=approval.approval_revision,
        approval_statement=approval.statement,pages=[p.model_dump(mode='json') for p in pages],content_sha256='0'*64)
    provisional=ApprovedGolden.model_validate(value).model_dump(mode='json')
    provisional['content_sha256']=digest(provisional)
    approved=ApprovedGolden.model_validate(provisional)
    raw=canonical_bytes(approved.model_dump(mode='json'))
    if path.exists():
        if path.read_bytes()!=raw:
            raise ValueError('Frozen Golden exists; overwrite forbidden')
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as file:file.write(raw)
    return approved


def load_golden(path: Path, *, verify_source: bool=True)->ApprovedGolden:
    value=json.loads(path.read_text());golden=ApprovedGolden.model_validate(value)
    if digest(value)!=golden.content_sha256:
        raise ValueError('Golden content hash mismatch')
    if verify_source:
        for page in golden.pages:
            if hashlib.sha256(Path(page.source_path).read_bytes()).hexdigest()!=page.source_document_sha256:
                raise ValueError('Original source hash mismatch')
            if hashlib.sha256(Path(page.source_representation).read_bytes()).hexdigest()!=page.source_page_hash:
                raise ValueError('Approved page hash mismatch')
    return golden


def group(value)->str|None:
    if value is None:return None
    raw=str(value).strip().rstrip('.')
    return 'ITEM_'+raw if raw else None


def surface(payload: dict)->dict:
    segments=payload.get('item_segments',[])
    incoming=group(payload.get('previous_item_number')) if payload.get('continues_previous_item') else None
    outgoing=group(payload.get('open_item_at_page_end'))
    starts=[group(s['item_number']) for s in segments if s.get('starts_on_this_page') and s.get('item_number')]
    continues=[group(s['item_number']) for s in segments if not s.get('starts_on_this_page') and s.get('item_number')]
    events=[]
    closes=[]
    previous=None
    if incoming:events.append(('CONTINUES_IN',incoming))
    for s in segments:
        identity=group(s.get('item_number'))
        if previous and identity!=previous and s.get('starts_on_this_page'):
            closes.append(previous)
            events.append(('CLOSES',previous))
        if identity:events.append(('STARTS' if s.get('starts_on_this_page') else 'CONTINUES',identity))
        previous=identity
    if outgoing:events.append(('CONTINUES_OUT',outgoing))
    return {'incoming':incoming,'outgoing':outgoing,'starts':starts,'continues':continues,
        # Local owner transition proves a structural close; a null outgoing key does not.
        'closes':closes,'groups':sorted({group(s.get('item_number')) for s in segments if s.get('item_number')}),'events':events}


def score_page(label: ApprovedPage,observed: dict,*,routing='REVIEW_REQUIRED',domain_review=True,conflicts=0,stale=False)->dict:
    expected={'incoming':label.incoming_group.groups,'outgoing':label.outgoing_group.groups,
              'starts':label.starts_item.groups,'continues':label.continues_item.groups,'closes':label.closes_item.groups}
    dimensions={}
    for field,values in expected.items():
        source=getattr(label,{'incoming':'incoming_group','outgoing':'outgoing_group','starts':'starts_item','continues':'continues_item','closes':'closes_item'}[field])
        actual=[observed[field]] if field in {'incoming','outgoing'} and observed[field] else observed[field] if field not in {'incoming','outgoing'} else []
        dimensions[field]=None if source.state=='UNKNOWN' else set(actual)==set(values)
    expected_groups=set().union(*(set(v) for v in expected.values()))
    dimensions['group_identity']=set(observed['groups'])==expected_groups
    dimensions['ordered_events']=observed['events']==[(e.event_type,e.group) for e in label.boundary_events]
    dimensions['boundary']=all(dimensions[f] is True for f in ('incoming','outgoing','starts','continues','closes','ordered_events'))
    false_starts=set(observed['starts'])-set(expected['starts'])
    missed_continuations=set(expected['continues'])-set(observed['continues'])
    missed_closures=set(expected['closes'])-set(observed['closes'])
    errors=[]
    if false_starts:errors.append('FALSE_ITEM_START')
    if missed_continuations:errors.append('MISSED_CONTINUATION')
    if missed_closures:errors.append('MISSED_CLOSURE')
    if dimensions['group_identity'] is False:errors.append('GROUP_IDENTITY_ERROR')
    if not dimensions['boundary']:errors.append('STRUCTURE_BOUNDARY_ERROR')
    if dimensions['incoming'] is False or dimensions['outgoing'] is False:errors.append('CONTINUITY_ERROR')
    if conflicts:errors.append('PROVIDER_CONFLICT')
    if stale:errors.append('STALE_CARRY')
    unassessable=any(value is None for value in dimensions.values())
    wrong=bool(errors)
    unsafe=wrong and routing=='RESOLVED' and domain_review is False
    reviewed=wrong and (routing=='REVIEW_REQUIRED' or domain_review is True)
    overlap=set(observed['groups']) & expected_groups
    status='UNASSESSABLE' if unassessable else 'REVIEW_REQUIRED_CORRECT' if reviewed else 'CORRECT' if not wrong else 'PARTIAL' if overlap else 'INCORRECT'
    return {'page_number':label.page_number,'status':status,'dimensions':dimensions,'observed':observed,
        'expected':{k:list(v) for k,v in expected.items()},'errors':sorted(errors),
        'false_starts':sorted(false_starts),'missed_continuations':sorted(missed_continuations),'missed_closures':sorted(missed_closures),
        'provider_conflicts':conflicts,'correct_review_escalation':int(reviewed),
        'unsafe_trusted_structural_errors':int(unsafe),'stale_carry_violations':int(stale),
        'trust_basis':{'routing':routing,'persisted_segment_review_required':domain_review}}


def rescore(golden: ApprovedGolden,observations:list,replay:dict)->dict:
    labels={p.page_number:p for p in golden.pages};pages=[];surfaces={}
    domain={p['page']:p for p in replay['unscored_structural_domain_assertions']}
    import pymupdf
    for o in observations:
        if o.tender_id!=TENDER_ID or o.document_id!=DOCUMENT_ID or o.capability.value!='STRUCTURE':
            raise ValueError('Only approved Tender #001 B-4 structure observations selectable')
    # The model used zoom 2.0; approved review images use 1.5. Verify both representations
    # against the same approved original, without provider execution or new timing.
    with pymupdf.open(golden.pages[0].source_path) as pdf:
        for o in observations:
            rendered=pdf[o.page_number-1].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png')
            if hashlib.sha256(rendered).hexdigest()!=o.provenance.get('image_sha256'):
                raise ValueError('Provider image does not match approved source page')
    for o in sorted(observations,key=lambda o:o.page_number):
        if o.tender_id!=TENDER_ID or o.document_id!=DOCUMENT_ID or o.capability.value!='STRUCTURE':
            raise ValueError('Only approved Tender #001 B-4 structure observations selectable')
        payload=o.provenance.get('structured_json')
        if not payload:
            pages.append({'page_number':o.page_number,'status':'UNASSESSABLE','errors':['CANONICAL_RESULT_UNAVAILABLE']})
            continue
        observed=surface(payload);surfaces[o.page_number]=observed
        replay_page=next(p for p in replay['structure'] if p['page']==o.page_number)
        # Use actual normalized production state for effective boundary; raw is retained separately.
        source=next((c for c in replay_page['candidates'] if c['source_method']=='VISION'),None)
        if source and source['structural_state']:
            state=source['structural_state'];observed['incoming']=group(state['incoming_item_key']);observed['outgoing']=group(state['outgoing_item_key'])
        result=score_page(labels[o.page_number],observed,routing=replay_page['routing'],
            domain_review=domain.get(o.page_number,{}).get('review_required'),stale=replay_page['stale_carry'])
        result['raw_provider_surface']=surface(json.loads(o.provenance['raw_response_text']))
        result['latency_ms']=o.latency_ms
        result['source_page_hash']=labels[o.page_number].source_page_hash
        result['perception_provenance']=source
        pages.append(result)
    boundaries=[]
    for left,right in [(1,2),(2,3),(3,4)]:
        expected_left=labels[left].outgoing_group;expected_right=labels[right].incoming_group
        a=surfaces.get(left);b=surfaces.get(right)
        left_correct=a is not None and tuple([a['outgoing']] if a['outgoing'] else [])==expected_left.groups
        right_correct=b is not None and tuple([b['incoming']] if b['incoming'] else [])==expected_right.groups
        boundaries.append({'boundary':f'P{left}→P{right}','left_observed':a is not None,'right_observed':b is not None,
            'left_outgoing_correct':left_correct if a else None,'right_incoming_correct':right_correct if b else None,
            'status':'CORRECT' if a and b and left_correct and right_correct else 'INCORRECT' if a and b else 'UNASSESSABLE',
            'partial_left_check':left_correct if a and not b else None,'observation_fabricated':False})
    aggregates={field:sum(p.get(field,0) for p in pages) for field in ['unsafe_trusted_structural_errors','correct_review_escalation','stale_carry_violations','provider_conflicts']}
    for field in ('false_starts','missed_continuations','missed_closures'):
        aggregates[field]=sum(len(p.get(field,())) for p in pages)
    aggregates['group_identity_errors']=sum('GROUP_IDENTITY_ERROR' in p['errors'] for p in pages)
    aggregates['pages_scored']=sum(p['status']!='UNASSESSABLE' for p in pages)
    adjudicated=deepcopy(replay)
    adjudicated['pre_golden_domain_trust']=adjudicated['domain_trust']
    adjudicated['limitations']=[note for note in adjudicated['limitations']
        if note!='Structural truth unlabeled; trusted correctness remains unassessed']
    adjudicated['domain_trust']={'assessed':aggregates['pages_scored'],
        'trusted_correct':sum(p['status']=='CORRECT' and p['trust_basis']['routing']=='RESOLVED' and
            p['trust_basis']['persisted_segment_review_required'] is False for p in pages),
        'trusted_incorrect':aggregates['unsafe_trusted_structural_errors'],
        'review_required_correct':aggregates['correct_review_escalation'],
        'unassessed':sum(p['status']=='UNASSESSABLE' for p in pages),
        'assessment_basis':'Human-approved B-4 structure Golden + actual isolated production replay'}
    adjudicated['unsafe_trusted_contractual_errors']=aggregates['unsafe_trusted_structural_errors']
    return {'schema_version':'1','golden_id':golden.golden_id,'golden_content_sha256':golden.content_sha256,
        'pages':pages,'boundaries':boundaries,'aggregate':aggregates,'provider_calls':replay['provider_calls'],
        'golden_pages':[1,2,3,4],'provider_pages':sorted(surfaces),'replay':adjudicated,'readiness_certified':False}
