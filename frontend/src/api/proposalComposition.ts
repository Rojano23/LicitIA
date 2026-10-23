import axios from "axios";
export type ResponseStatus="PENDING"|"COMPLY"|"PARTIAL"|"NOT_APPLICABLE"|"EXCEPTION"|"REVIEW_REQUIRED"|"PROVIDED";
export type HumanResponse={status:ResponseStatus;text:string;offered_description:string;comment:string;clarification:string;note:string;document_id:string|null;external_reference:string;included:boolean;reason:string};
export type CompositionRow={key:string;section:string;canonical:Record<string,unknown>;response:HumanResponse;source_match:string;review_required:boolean;declaration_authority:string};
export type CompositionSection={id:string;type:string;order:number;included:boolean;note:string|null};
export type ManualItem={id:string;kind:"CLARIFICATION"|"EXCLUSION"|"ASSUMPTION"|"DEVIATION"|"NOTE"|"ANNEX_REFERENCE";text:string;document_id:string|null;external_reference:string};
export type CompositionSummary={status:string;hard_incomplete:{key:string;code:string}[];blocking_review:{key:string;code:string}[];acknowledgeable_review:{key:string;code:string}[];sections:{section:string;status:string;pending_count:number;review_count:number;row_count:number}[]};
export type Composition={initialized:boolean;contract_version:string;version_id:string;revision?:number;sha256?:string;identification?:Record<string,unknown>;sections?:CompositionSection[];summary?:CompositionSummary;rows?:CompositionRow[];items?:ManualItem[];total?:number;next_offset?:number|null;currency_groups?:{currency:string;line_count:number}[];removed_keys?:string[]};
const route=(base:string,tender:string,id:string)=>`${base}/tenders/${tender}/proposal-versions/${id}/composition`;
export const compositionApi={
 get:async(base:string,tender:string,id:string,section?:string,offset=0)=>(await axios.get<Composition>(route(base,tender,id),{params:{section,offset,limit:25}})).data,
 initialize:async(base:string,tender:string,id:string)=>(await axios.post<Composition>(`${route(base,tender,id)}/initialize`,{origin:"WORKSPACE"})).data,
 responses:async(base:string,tender:string,id:string,revision:number,changes:{key:string;response:HumanResponse;acknowledge_source_change?:boolean}[])=>(await axios.patch<Composition>(`${route(base,tender,id)}/responses`,{expected_revision:revision,origin:"WORKSPACE",changes})).data,
 settings:async(base:string,tender:string,id:string,revision:number,fields:{sections?:CompositionSection[];items?:ManualItem[]})=>(await axios.patch<Composition>(`${route(base,tender,id)}/settings`,{expected_revision:revision,origin:"WORKSPACE",...fields,...(fields.sections?{sections:fields.sections.map(s=>({id:s.id,order:s.order,included:s.included,note:s.note??""}))}:{})})).data,
};
