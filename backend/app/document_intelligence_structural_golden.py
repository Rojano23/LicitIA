"""Calibration-only candidate contract. No self-approval, scoring or providers."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

TENDER_ID='decd32ae-2c1f-4520-89bc-d845c986a7ba'
DOCUMENT_ID='acf31750-1d8d-4a0c-910c-fc3743930c57'
SHA= r'^[0-9a-f]{64}$'

class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)

class Groups(Contract):
    state: Literal['KNOWN','NONE','UNKNOWN']
    groups: tuple[str,...]=()
    @model_validator(mode='after')
    def consistent(self):
        if (self.state=='KNOWN') != bool(self.groups):
            raise ValueError('KNOWN requires groups; NONE/UNKNOWN must not invent identities')
        if len(set(self.groups))!=len(self.groups) or any(not g.strip() for g in self.groups):
            raise ValueError('Distinct nonblank comparison identities required')
        return self

class Event(Contract):
    order: int=Field(gt=0)
    event_type: Literal['CONTINUES_IN','STARTS','CONTINUES','CLOSES','CONTINUES_OUT']
    group: str=Field(min_length=1)
    locator: str=Field(min_length=1)
    human_note: str=''

class VisibleIdentifier(Contract):
    raw: str=Field(min_length=1)
    group: str=Field(min_length=1)
    locator: str=Field(min_length=1)

class SupportingReference(Contract):
    identity: str=Field(min_length=1)
    authority: Literal['HUMAN_APPROVED','HUMAN_REFERENCE_NONCANONICAL','DIAGNOSTIC_ONLY','MODEL_DERIVED']
    scope: str=Field(min_length=1)
    sha256: str=Field(pattern=SHA)

class PageCandidate(Contract):
    schema_version: Literal['1']='1'
    golden_id: str=Field(min_length=1)
    tender_id: Literal['decd32ae-2c1f-4520-89bc-d845c986a7ba']
    document_id: Literal['acf31750-1d8d-4a0c-910c-fc3743930c57']
    document_version: str=Field(min_length=1)
    page_number: int=Field(ge=1,le=4)
    source_document_sha256: str=Field(pattern=SHA)
    source_path: str=Field(min_length=1)
    source_representation: str=Field(min_length=1)
    source_page_hash: str=Field(pattern=SHA)
    representation_contract: str=Field(min_length=1)
    incoming_group: Groups
    outgoing_group: Groups
    starts_item: Groups
    continues_item: Groups
    closes_item: Groups
    visible_item_identifiers: tuple[VisibleIdentifier,...]=()
    boundary_events: tuple[Event,...]
    structural_review_expected: bool
    human_note: str=Field(min_length=1)
    uncertainty: str=Field(min_length=1)
    supporting_references: tuple[SupportingReference,...]=()
    approval_status: Literal['PENDING']='PENDING'
    approved_by_human: Literal[False]=False
    approval_revision: None=None
    @model_validator(mode='after')
    def consistency(self):
        if [e.order for e in self.boundary_events]!=list(range(1,len(self.boundary_events)+1)):
            raise ValueError('Events must be in contiguous page order')
        for field,event_type in [('starts_item','STARTS'),('closes_item','CLOSES'),('continues_item','CONTINUES_IN')]:
            selection=getattr(self,field)
            if selection.state!='UNKNOWN' and set(selection.groups)!={e.group for e in self.boundary_events if e.event_type==event_type}:
                raise ValueError('Summary and ordered events disagree')
        for selection,event_type in [(self.incoming_group,'CONTINUES_IN'),(self.outgoing_group,'CONTINUES_OUT')]:
            if len(selection.groups)>1:
                raise ValueError('A page boundary admits one group, not multiple owners')
            if selection.state!='UNKNOWN' and set(selection.groups)!={e.group for e in self.boundary_events if e.event_type==event_type}:
                raise ValueError('Boundary state and events disagree')
        return self

class CandidatePack(Contract):
    schema_version: Literal['1']='1'
    artifact_kind: Literal['HUMAN_REVIEW_CANDIDATE']='HUMAN_REVIEW_CANDIDATE'
    canonical_golden: Literal[False]=False
    golden_id: str=Field(min_length=1)
    approval_status: Literal['PENDING']='PENDING'
    approved_by_human: Literal[False]=False
    pages: tuple[PageCandidate,...]
    @model_validator(mode='after')
    def same_source(self):
        if not self.pages or len({p.page_number for p in self.pages})!=len(self.pages):
            raise ValueError('Distinct pages required')
        if len({(p.document_version,p.source_path,p.source_document_sha256) for p in self.pages})!=1:
            raise ValueError('One immutable document version required')
        return self


def serialize(pack: CandidatePack)->str:
    value=pack.model_dump(mode='json')
    value['pages'].sort(key=lambda p:p['page_number'])
    return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n'


def review_page_images(source: Path, output_dir: Path, *, expected_sha256: str,
                       tender_id: str=TENDER_ID,document_id: str=DOCUMENT_ID)->tuple[dict,...]:
    """Hash exact PNG bytes used in review. No OCR, Vision, or extraction provider."""
    import pymupdf
    if tender_id!=TENDER_ID or document_id!=DOCUMENT_ID:
        raise ValueError('Only authorized Tender #001 B-4 selectable')
    before=source.read_bytes()
    if hashlib.sha256(before).hexdigest()!=expected_sha256:
        raise ValueError('Immutable source hash mismatch')
    if output_dir.resolve()==source.resolve().parent:
        raise ValueError('Review artifacts must be separate from immutable originals')
    output_dir.mkdir(parents=True,exist_ok=True)
    pages=[]
    with pymupdf.open(source) as pdf:
        if pdf.page_count!=4:
            raise ValueError('Authorized B-4 must have exactly four pages')
        for number in range(1,5):
            raw=pdf[number-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).tobytes('png')
            target=output_dir/f'page_{number}.png'
            target.write_bytes(raw)
            pages.append({'page_number':number,'source_representation':str(target.resolve()),
                'source_page_hash':hashlib.sha256(raw).hexdigest(),
                'representation_contract':f'PNG full page, PyMuPDF {pymupdf.VersionBind}, zoom 1.5, alpha false'})
    if source.read_bytes()!=before:
        raise RuntimeError('Original changed during review rendering')
    return tuple(pages)


def write_candidate(pack: CandidatePack,path:Path)->None:
    # This path never has approval authority, even if a caller supplies an approved-looking dict.
    validated=CandidatePack.model_validate(pack.model_dump(mode='json'))
    reports=(Path(__file__).resolve().parents[1]/'reports').resolve()
    if path.name!='b4_structural_golden_candidate_v1.json' or not path.resolve().is_relative_to(reports):
        raise ValueError('Candidate writer only accepts the untracked review candidate path; no canonical Golden')
    for page in validated.pages:
        if hashlib.sha256(Path(page.source_representation).read_bytes()).hexdigest()!=page.source_page_hash:
            raise ValueError('Review image hash mismatch')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(serialize(validated))
