"""Source-neutral discovery contracts and deterministic local matching."""
from dataclasses import dataclass,field
from datetime import date
from typing import Protocol,Literal
from uuid import UUID,uuid5,NAMESPACE_URL
import hashlib,json,re,unicodedata
from pydantic import BaseModel,ConfigDict,Field,model_validator

class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def identity(source,external):return str(uuid5(NAMESPACE_URL,'licitia:discovery:'+source+'\0'+external))
def normalized(text):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)).split())

class PublicDocument(Contract):
    external_id:str=Field(min_length=1,max_length=500)
    name:str=Field(min_length=1,max_length=500)
    public_url:str=Field(max_length=2000)

class Opportunity(Contract):
    procedure_number:str|None=Field(default=None,min_length=1,max_length=200)
    external_id:str=Field(min_length=1,max_length=200)
    business_area:str=Field(min_length=1,max_length=120)
    contracting_area:str|None=Field(default=None,max_length=300)
    title:str=Field(min_length=1,max_length=20000)
    description:str|None=Field(default=None,max_length=20000)
    published_date:date|None=None
    event_type:str|None=Field(default=None,max_length=300)
    supply_type:str|None=Field(default=None,max_length=300)
    public_url:str=Field(max_length=2000)
    source_status:str|None=Field(default=None,max_length=300)
    documents:list[PublicDocument]=Field(default_factory=list,max_length=1000)
    raw_metadata:dict=Field(default_factory=dict)
    @model_validator(mode='after')
    def bounded(self):
        if len(json.dumps(self.raw_metadata))>8192:raise ValueError('RAW_METADATA_LIMIT')
        self.documents=sorted(self.documents,key=lambda d:d.external_id)
        if len({d.external_id for d in self.documents})!=len(self.documents):raise ValueError('DOCUMENT_IDENTITY_COLLISION')
        return self
    @property
    def source_fingerprint(self):
        # Raw parser diagnostics are not source meaning.
        return fingerprint(self.model_dump(mode='json',exclude={'raw_metadata'} | ({'procedure_number'} if self.procedure_number is None else set())))

class SourceQuery(Contract):
    areas:list[str]=Field(min_length=1,max_length=20)
    published_from:date|None=None
    published_to:date|None=None
    event_type:str|None=Field(default=None,min_length=1,max_length=120)
    supply_type:str|None=Field(default=None,min_length=1,max_length=120)
    page_size:int=Field(default=100,ge=1,le=200,strict=True)
    @model_validator(mode='after')
    def valid(self):
        if any(not a or len(a)>120 for a in self.areas):raise ValueError('INVALID_AREA_KEY')
        if len(set(self.areas))!=len(self.areas):raise ValueError('DUPLICATE_AREA')
        if self.published_from and self.published_to and self.published_from>self.published_to:raise ValueError('INVALID_DATE_RANGE')
        return self

class ScanRequest(Contract):
    request_id:UUID
    query:SourceQuery

class SourceSettings(Contract):
    enabled:bool=True
    areas:list[str]=Field(min_length=1,max_length=20)

class Profile(Contract):
    name:str=Field(min_length=1,max_length=160)
    include_keywords:list[str]=Field(default_factory=list,max_length=50)
    exclude_keywords:list[str]=Field(default_factory=list,max_length=50)
    synonyms:dict[str,list[str]]=Field(default_factory=dict,max_length=30)
    source_ids:list[str]=Field(default_factory=list,max_length=20)
    business_areas:list[str]=Field(default_factory=list,max_length=20)
    active:bool=True
    @model_validator(mode='after')
    def bounded(self):
        terms=self.include_keywords+self.exclude_keywords+list(self.synonyms)+[t for values in self.synonyms.values() for t in values]
        if any(not v or len(v)>200 for v in self.source_ids+self.business_areas):raise ValueError('INVALID_PROFILE_RESTRICTION')
        if any(not t.strip() or len(t)>120 for t in terms) or any(len(v)>10 for v in self.synonyms.values()):raise ValueError('INVALID_KEYWORD')
        return self

class ProfileUpdate(Profile):
    expected_revision:int=Field(ge=1,strict=True)

class WorkflowUpdate(Contract):
    expected_revision:int=Field(ge=1,strict=True)
    internal_state:Literal['NEW','REVIEW','FOLLOWING','DISCARDED']

@dataclass
class Batch:
    rows:list[Opportunity]
    raw_count:int
    next_cursor:str|None=None
    terminal:bool=False
    source_total:int|None=None
    issues:list[dict]=field(default_factory=list)

class DiscoveryAdapter(Protocol):
    source_id:str
    version:str
    areas:dict[str,dict]
    def fetch(self,query:SourceQuery,area:str,cursor:str|None)->Batch:...
    def close(self)->None:...
    def download(self,document:PublicDocument):...
    def capabilities(self)->dict:...


def match_profile(profile:Profile,source_id:str,opportunity:Opportunity):
    fields={k:normalized(v or '') for k,v in opportunity.model_dump().items() if k in {'title','description','business_area','event_type','supply_type'}}
    def hits(terms,expand):
        result=[]
        for term in terms:
            candidates=[term]
            if expand:
                for canonical,related in profile.synonyms.items():
                    group=[canonical,*related]
                    if normalized(term) in {normalized(t) for t in group}:candidates+=group
            for candidate in dict.fromkeys(candidates):
                needle=normalized(candidate)
                for name,text in fields.items():
                    # Phrase/word boundary avoids PLC matching an unrelated substring.
                    if re.search(r'(?<!\w)'+re.escape(needle)+r'(?!\w)',text):
                        result.append({'term':term,'matched_text':candidate,'field':name,'kind':'EXACT' if normalized(term)==needle else 'SYNONYM'})
        return result
    included=hits(profile.include_keywords,True);excluded=hits(profile.exclude_keywords,True)
    restrictions=[]
    if profile.source_ids and source_id not in profile.source_ids:restrictions.append('SOURCE_RESTRICTION')
    if profile.business_areas and opportunity.business_area not in profile.business_areas:restrictions.append('AREA_RESTRICTION')
    if not profile.active:restrictions.append('PROFILE_INACTIVE')
    return {'matched':not restrictions and not excluded and (bool(included) or not profile.include_keywords),
        'policy':'ANY_INCLUDE_EXCLUDE_WINS','include_hits':included,'exclude_hits':excluded,'restrictions':restrictions,'score':None}


class AcknowledgeRequest(Contract):
    change_ids:list[UUID]=Field(min_length=1,max_length=200)
    actor:str=Field(default='LOCAL_USER',min_length=1,max_length=160)

class FollowRequest(Contract):
    following:bool
    expected_revision:int=Field(ge=1,strict=True)

class DocumentChoice(Contract):
    document_id:UUID
    conflict_action:Literal['NONE','NEW_REVISION','IMPORT_INDEPENDENT']='NONE'
    revision_of_document_id:UUID|None=None
    refresh:bool=False

class HandoffRequest(Contract):
    confirm:Literal[True]
    expected_binding:str=Field(pattern=r'^[a-f0-9]{64}$')
    title:str|None=Field(default=None,min_length=1,max_length=255)
    documents:list[DocumentChoice]=Field(default_factory=list,max_length=1000)
    actor:str=Field(default='LOCAL_USER',min_length=1,max_length=160)
    @model_validator(mode='after')
    def unique_documents(self):
        if len({d.document_id for d in self.documents})!=len(self.documents):raise ValueError('DUPLICATE_SOURCE_DOCUMENT')
        for d in self.documents:
            if (d.conflict_action=='NEW_REVISION')!=(d.revision_of_document_id is not None):raise ValueError('REVISION_TARGET_REQUIRED_ONLY_FOR_REVISION')
        return self
