import axios from "axios";
export type Section={id:string;type:string;order:number;included:boolean;note:string|null};
export type ProposalConfig={title:string|null;bidder_name:string|null;bidder_reference:string|null;currency_presentation:"BY_CURRENCY"|"ORIGINAL";notes:string|null;sections:Section[]};
export type ProposalVersion={id:string;proposal_id:string;tender_id:string;version:number;previous_version_id:string|null;snapshot_id:string;snapshot_sha256:string;snapshot_eligibility:string;state:"DRAFT"|"FROZEN";edit_revision:number;is_latest:boolean;configuration:ProposalConfig;sections:Section[];frozen_sha256:string|null};
export type VersionPage={items:Pick<ProposalVersion,"id"|"proposal_id"|"version"|"snapshot_id"|"state"|"is_latest">[];next_before_id:string|null};
export type CreateVersion={request_id:string;snapshot_id:string;proposal_id?:string;previous_version_id?:string;configuration?:ProposalConfig;acknowledge_warnings:boolean;acknowledge_stale:boolean;actor_label:string|null;origin:"WORKSPACE"};
export type ProposalEvent={sequence:number;action:string;actor_label:string|null;created_at:string};
const route=(base:string,tender:string)=>`${base}/tenders/${tender}/proposal-versions`;
export const versionsApi={
 list:async(base:string,tender:string,before?:string)=>(await axios.get<VersionPage>(route(base,tender),{params:{limit:20,before_id:before}})).data,
 get:async(base:string,tender:string,id:string)=>(await axios.get<ProposalVersion>(`${route(base,tender)}/${id}`)).data,
 create:async(base:string,tender:string,payload:CreateVersion)=>(await axios.post<ProposalVersion>(route(base,tender),payload)).data,
 update:async(base:string,tender:string,value:ProposalVersion,configuration:ProposalConfig,actor:string|null)=>(await axios.patch<ProposalVersion>(`${route(base,tender)}/${value.id}`,{expected_edit_revision:value.edit_revision,configuration,actor_label:actor})).data,
 freeze:async(base:string,tender:string,value:ProposalVersion,warnings:boolean,stale:boolean,actor:string|null,compositionRevision?:number,compositionAck=false)=>(await axios.post<ProposalVersion>(`${route(base,tender)}/${value.id}/freeze`,{expected_edit_revision:value.edit_revision,acknowledge_warnings:warnings,acknowledge_stale:stale,actor_label:actor,expected_composition_revision:compositionRevision,acknowledge_composition_review:compositionAck})).data,
 source:async(base:string,tender:string,id:string)=>(await axios.get<{state:"CURRENT"|"SOURCE_SNAPSHOT_STALE"}>(`${route(base,tender)}/${id}/source-state`)).data,
 history:async(base:string,tender:string,id:string)=>(await axios.get<ProposalEvent[]>(`${route(base,tender)}/${id}/history`,{params:{limit:25}})).data,
};
