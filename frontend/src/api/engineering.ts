import axios from 'axios';
import type {TenderRequirementMatrix,ComplianceMatrix,TenderRequirementEvidenceMatches,CompanyOption,MatchCompanyEvidence} from './engineeringTypes';
const path=(base:string,tender:string)=>`${base}/tenders/${encodeURIComponent(tender)}`;
const companyPath=(base:string,tender:string,company:string)=>`${path(base,tender)}/companies/${encodeURIComponent(company)}`;
function own<T extends {tender_id:string}>(data:T,tender:string):T{if(data.tender_id!==tender)throw new Error('WRONG_TENDER');return data;}
function ownedCompany<T extends {tender_id:string;company_id:string}>(data:T,tender:string,company:string):T{own(data,tender);if(data.company_id!==company)throw new Error('WRONG_COMPANY');return data;}
export const engineeringApi={
 requirements:async(base:string,t:string)=>own((await axios.get<TenderRequirementMatrix>(`${path(base,t)}/requirement-matrix`)).data,t),
 reviewRequirement:async(base:string,t:string,id:string,action:string,note:string)=>own((await axios.patch<TenderRequirementMatrix>(`${path(base,t)}/requirements/${encodeURIComponent(id)}/review`,{action,review_note:note||null})).data,t),
 companies:async(base:string)=>(await axios.get<CompanyOption[]>(`${base}/companies`)).data,
 compliance:async(base:string,t:string,c:string)=>ownedCompany((await axios.get<ComplianceMatrix>(`${companyPath(base,t,c)}/compliance-matrix`)).data,t,c),
 matches:async(base:string,t:string,c:string,r:string)=>ownedCompany((await axios.get<TenderRequirementEvidenceMatches>(`${companyPath(base,t,c)}/requirements/${encodeURIComponent(r)}/evidence-match-candidates`)).data,t,c),
 reviewMatch:async(base:string,t:string,c:string,id:string,status:string,note:string)=>ownedCompany((await axios.patch<TenderRequirementEvidenceMatches>(`${companyPath(base,t,c)}/evidence-match-candidates/${encodeURIComponent(id)}/review`,{review_status:status,review_note:note||null})).data,t,c),
 evidence:async(base:string,c:string)=>{const data=(await axios.get<{evidence:MatchCompanyEvidence[]}>(`${base}/companies/${encodeURIComponent(c)}/evidence`)).data;if(data.evidence.some(e=>e.company_id!==c))throw new Error('WRONG_COMPANY');return data.evidence;},
 manual:async(base:string,t:string,c:string,r:string,id:string,note:string)=>ownedCompany((await axios.post<TenderRequirementEvidenceMatches>(`${companyPath(base,t,c)}/requirements/${encodeURIComponent(r)}/evidence-match-candidates/manual`,{company_evidence_id:id,rationale:note||null})).data,t,c),
 decide:async(base:string,t:string,c:string,r:string,status:string,note:string)=>{await axios.patch(`${companyPath(base,t,c)}/requirements/${encodeURIComponent(r)}/compliance-decision`,{decision_status:status,decision_note:note||null});},
};
