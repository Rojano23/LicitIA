import axios from "axios";
export type Workflow="OPEN"|"IN_REVIEW"|"RESOLVED"|"ACCEPTED_RISK"|"NOT_APPLICABLE";
export type WorkItem={id:string;dimension:string;entity_type:string;entity_id:string;code:string;
 issue:{status:string;severity:"BLOCKER"|"REVIEW"|"WARNING";summary:string}|null;lifecycle:string;
 workflow_status:Workflow;recorded_workflow_status:Workflow|null;annotation_stale:boolean;revision:number;context_sha256:string;
 note:string|null;owner:string|null;actor_label:string|null;accepted_risk_allowed:boolean;canonical_blocker_remains:boolean;action_target:string};
export type WorkRead={tender_id:string;canonical_summary:{status:string;blocker_count:number;review_required_count:number;warning_count:number;total_issues:number};
 work_summary:Record<string,number>;total_filtered:number;items:WorkItem[];notice:string};
export type WorkEvent={revision:number;workflow_status:Workflow;note:string|null;owner:string|null;actor_label:string|null;timestamp:string};
export const workApi={
 read:async(base:string,tender:string,params:{offset:number;workflow_status?:Workflow;include_inactive:boolean})=>(await axios.get<WorkRead>(`${base}/tenders/${tender}/readiness-work`,{params:{...params,limit:50}})).data,
 update:async(base:string,tender:string,item:WorkItem,fields:{workflow_status:Workflow;note:string|null;owner:string|null;actor_label:string|null})=>(await axios.patch<WorkItem>(`${base}/tenders/${tender}/readiness-work/${item.id}`,{...fields,expected_revision:item.revision,expected_context_sha256:item.context_sha256})).data,
 history:async(base:string,tender:string,id:string)=>(await axios.get<WorkEvent[]>(`${base}/tenders/${tender}/readiness-work/${id}/history`,{params:{limit:25}})).data,
};
