import axios from "axios";
export type Eligibility="ELIGIBLE"|"ELIGIBLE_WITH_WARNINGS"|"NOT_ELIGIBLE"|"REVIEW_REQUIRED";
export type ProposalIssue={id:string;dimension:string;code:string;entity_type:string;entity_id:string;status:string;severity:string|null};
export type Evaluation={input_sha256:string;projection:{tender_id:string;readiness_status:string;eligibility:Eligibility;blockers:ProposalIssue[];reviews:ProposalIssue[];warnings:ProposalIssue[];accepted_risks:{issue_id:string;note:string|null}[];rows:{scope_id:string}[];notice:string}};
export type Snapshot={payload:{snapshot_id:string;created_at:string;input_sha256:string;projection:Evaluation["projection"]};payload_sha256:string};
export type SnapshotHistory={items:{snapshot_id:string;created_at:string;readiness_status:string;eligibility:Eligibility;state:"CURRENT"|"STALE";payload_sha256:string}[];next_before_id:string|null};
export type SnapshotRequest={request_id:string;expected_input_sha256:string;acknowledge_warnings:boolean;actor_label:string|null};
const route=(base:string,tender:string)=>`${base}/tenders/${tender}/proposal-readiness`;
export const proposalApi={
 evaluate:async(base:string,tender:string)=>(await axios.get<Evaluation>(route(base,tender))).data,
 create:async(base:string,tender:string,payload:SnapshotRequest)=>(await axios.post<Snapshot>(`${route(base,tender)}/snapshots`,payload)).data,
 history:async(base:string,tender:string,before?:string)=>(await axios.get<SnapshotHistory>(`${route(base,tender)}/snapshots`,{params:{limit:20,before_id:before}})).data,
};
