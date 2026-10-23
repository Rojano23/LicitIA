import axios from 'axios';
export type Source={capabilities?:{automation_status?:string;message?:string;pagination?:string;requires_date_pair?:boolean};id:string;name:string;enabled:boolean;last_scan_state:string|null;last_error:string|null;areas:{key:string;label:string}[];configuration:{areas:string[]}};
export type Match={matched:boolean;include_hits:{term:string;matched_text:string;field:string;kind:string}[];exclude_hits:{term:string;matched_text:string;field:string;kind:string}[];restrictions:string[]};
export type Opportunity={watching?:boolean;unread_changes?:number;unread_document_changes?:number;linked_tender?:{id:string;available:boolean}|null;source_changes_available?:boolean;procedure_number?:string|null;contracting_area?:string|null;id:string;source_id:string;external_id:string;title:string;description:string|null;business_area:string;published_date:string|null;event_type:string|null;supply_type:string|null;source_status:string|null;internal_state:string;revision:number;document_count:number;public_url:string;first_seen:string;last_seen:string;match:Match|null};
export type Profile={id:string;name:string;revision:number;include_keywords:string[];exclude_keywords:string[];synonyms:Record<string,string[]>;source_ids:string[];business_areas:string[];active:boolean};
export type Scan={id:string;status:string;started_at:string;metrics:{pages_attempted?:number;pages_completed?:number;unique_opportunities?:number;rows_retrieved?:number;diagnostics?:{area:string;code:string;page?:number}[]}};
export type Page={items:Opportunity[];total:number;limit:number;offset:number};
export type SourceQuery={areas:string[];published_from:string|null;published_to:string|null;event_type:string|null;supply_type:string|null;page_size:number};
export const discoveryApi={
 sources:async(base:string)=>(await axios.get<Source[]>(`${base}/discovery/sources`)).data,
 configure:async(base:string,id:string,payload:{enabled:boolean;areas:string[]})=>(await axios.patch<Source>(`${base}/discovery/sources/${id}`,payload)).data,
 scans:async(base:string,source:string)=>(await axios.get<Scan[]>(`${base}/discovery/scans`,{params:{source_id:source}})).data,
 scan:async(base:string,source:string,request_id:string,query:SourceQuery)=>(await axios.post<Scan>(`${base}/discovery/sources/${source}/scans`,{request_id,query})).data,
 profiles:async(base:string)=>{
  const values:Profile[]=[];
  for(let offset=0;offset<2000;offset+=100){
   const page=(await axios.get<Profile[]>(`${base}/discovery/profiles`,{params:{limit:100,offset}})).data;
   values.push(...page);if(page.length<100)return values;
  }
  throw new Error('DISCOVERY_PROFILE_LIST_LIMIT');
 },
 saveProfile:async(base:string,payload:Omit<Profile,'id'|'revision'>,id?:string,expected_revision?:number)=>id?
  (await axios.patch<Profile>(`${base}/discovery/profiles/${id}`,{...payload,expected_revision})).data:
  (await axios.post<Profile>(`${base}/discovery/profiles`,payload)).data,
 list:async(base:string,params:Record<string,string|number|boolean|undefined>)=>(await axios.get<Page>(`${base}/discovery/opportunities`,{params})).data,
 state:async(base:string,row:Opportunity,internal_state:string)=>(await axios.patch<Opportunity>(`${base}/discovery/opportunities/${row.id}/state`,{expected_revision:row.revision,internal_state})).data,
};

export type Change={id:string;category:string;origin:string;detected_at:string;summary:string;changed_fields:Record<string,unknown>;acknowledged_at:string|null};
export type History={items:Change[];total:number;offset:number;limit:number};
export type Receipt={tender_document_id:string;sha256:string;source_url:string;downloaded_at:string};
export type Preview={opportunity_id:string;source_id:string;source_fingerprint:string;binding:string;internal_state:string;suggested_title:string|null;context:Record<string,string|null>;documents:{id:string;name:string;public_url:string;metadata_fingerprint:string;last_import:Receipt|null}[];linked_tender:{id:string;available:boolean}|null;selection_default:string;analysis_automatic:boolean};
export type Choice={document_id:string;conflict_action:'NONE'|'NEW_REVISION'|'IMPORT_INDEPENDENT';revision_of_document_id:string|null;refresh:boolean};
export type Handoff={tender_id:string;tender_available:boolean;already_created:boolean;documents_status:string;analysis_started:boolean;documents:{source_document_id:string;status:string;document_id?:string;error_code?:string;error_type?:string}[]};
export type Counters={new_opportunities:number;changed_opportunities:number;followed_with_changes:number;unread_changes:number;new_documents:number};
export const monitoringApi={
 summary:async(base:string)=>(await axios.get<Counters>(`${base}/discovery/monitoring/summary`)).data,
 get:async(base:string,id:string,profileId?:string)=>(await axios.get<Opportunity>(`${base}/discovery/opportunities/${id}`,{params:{profile_id:profileId}})).data,
 history:async(base:string,id:string,offset=0)=>(await axios.get<History>(`${base}/discovery/opportunities/${id}/changes`,{params:{offset,limit:100}})).data,
 preview:async(base:string,id:string)=>(await axios.get<Preview>(`${base}/discovery/opportunities/${id}/tender-preview`)).data,
 follow:async(base:string,row:Opportunity)=>(await axios.patch<Opportunity>(`${base}/discovery/opportunities/${row.id}/following`,{following:!row.watching,expected_revision:row.revision})).data,
 acknowledge:async(base:string,id:string,ids:string[])=>axios.post(`${base}/discovery/opportunities/${id}/changes/acknowledge`,{change_ids:ids}),
 handoff:async(base:string,preview:Preview,title:string,documents:Choice[])=>(await axios.post<Handoff>(preview.linked_tender?`${base}/discovery/opportunities/${preview.opportunity_id}/tenders/${preview.linked_tender.id}/documents`:`${base}/discovery/opportunities/${preview.opportunity_id}/create-tender`,{confirm:true,expected_binding:preview.binding,title:title||null,documents})).data,
};
