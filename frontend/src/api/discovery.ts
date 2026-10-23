import axios from 'axios';
export type Source={id:string;name:string;enabled:boolean;last_scan_state:string|null;last_error:string|null;areas:{key:string;label:string}[];configuration:{areas:string[]}};
export type Match={matched:boolean;include_hits:{term:string;matched_text:string;field:string;kind:string}[];exclude_hits:{term:string;matched_text:string;field:string;kind:string}[];restrictions:string[]};
export type Opportunity={id:string;source_id:string;external_id:string;title:string;description:string|null;business_area:string;published_date:string|null;event_type:string|null;supply_type:string|null;source_status:string|null;internal_state:string;revision:number;document_count:number;public_url:string;first_seen:string;last_seen:string;match:Match|null};
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
