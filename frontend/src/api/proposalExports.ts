import axios from "axios";
export type ArtifactType="DOCX"|"XLSX"|"PDF"|"ZIP";
export type ExportRequest={request_id:string;formats:Exclude<ArtifactType,"ZIP">[];include_package:boolean;allow_draft:boolean;expected_composition_revision:number;expected_edit_revision:number;actor_label:null};
export type GeneratedArtifact={type:ArtifactType;name:string;sha256:string;size:number;created_at:string};
export type ExportReceipt={contract_version:string;request_id:string;tender_id:string;proposal_id:string;version_id:string;snapshot_id:string;snapshot_sha256:string;composition_sha256:string;proposal_state:"DRAFT"|"FROZEN";semantic_sha256:string;created_at:string;manifest_sha256:string;artifacts:GeneratedArtifact[];verification_status:string};
export type ExportPage={items:ExportReceipt[];next_before_id:string|null};
const route=(base:string,tender:string,version:string)=>`${base}/tenders/${encodeURIComponent(tender)}/proposal-versions/${encodeURIComponent(version)}/exports`;
export const exportsApi={
 create:async(base:string,tender:string,version:string,payload:ExportRequest)=>(await axios.post<ExportReceipt>(route(base,tender,version),payload)).data,
 list:async(base:string,tender:string,version:string,before?:string)=>(await axios.get<ExportPage>(route(base,tender,version),{params:{limit:20,before_id:before}})).data,
 verify:async(base:string,tender:string,version:string,request:string)=>(await axios.post<{verification_status:string}>(`${route(base,tender,version)}/${encodeURIComponent(request)}/verify`)).data,
 file:(base:string,tender:string,version:string,request:string,kind:ArtifactType)=>`${route(base,tender,version)}/${encodeURIComponent(request)}/files/${kind}`,
};
