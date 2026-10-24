import axios from 'axios';
export type Company = {
  id: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CompanyDocument = {
  id: string;
  company_id: string;
  original_filename: string;
  source_relative_path: string | null;
  stored_relative_path: string;
  mime_type: string | null;
  file_size_bytes: number;
  sha256: string;
  status: string;
  document_type: string | null;
  label: string | null;
  issuer: string | null;
  issue_date: string | null;
  expiration_date: string | null;
  metadata_note: string | null;
  archived_at: string | null;
  revision_of_document_id: string | null;
  conflict_resolution_action: string | null;
  revision_number: number;
  is_current: boolean;
  imported_at: string;
  updated_at: string;
};

export type CompanyImportResult = {
  filename: string;
  source_relative_path: string | null;
  status: string;
  message: string | null;
  document_id: string | null;
  stored_relative_path: string | null;
  sha256: string | null;
  revision_of_document_id: string | null;
  conflict_resolution_action: string | null;
  revision_number: number | null;
  is_current: boolean | null;
};

export type CompanyEvidenceSourceDocument = {
  id: string;
  company_id: string;
  original_filename: string;
  document_type: string | null;
  label: string | null;
  status: string;
  archived_at: string | null;
  revision_number: number;
  is_current: boolean;
};

export type CompanyEvidenceReview = {
  id: string;
  company_id: string;
  company_evidence_id: string;
  review_status: string;
  review_note: string | null;
  reviewed_fingerprint: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CompanyEvidence = {
  id: string;
  company_id: string;
  company_document_id: string;
  evidence_type: string;
  subject_kind: string;
  subject_name: string | null;
  canonical_statement: string;
  issuer: string | null;
  reference_number: string | null;
  issued_on: string | null;
  valid_from: string | null;
  valid_until: string | null;
  period_start: string | null;
  period_end: string | null;
  analysis_status: string;
  origin: string;
  extractor_version: string;
  source_page: number | null;
  source_locator: string | null;
  source_excerpt: string;
  semantic_fingerprint: string;
  system_warnings: string[];
  review_freshness: string;
  created_at: string;
  updated_at: string;
  source_document: CompanyEvidenceSourceDocument;
  review: CompanyEvidenceReview | null;
};

export type CompanyEvidenceSummary = {
  evidence_count: number;
  determined_count: number;
  review_required_count: number;
  validated_count: number;
  pending_review_count: number;
  rejected_count: number;
  historical_source_count: number;
  current_review_count: number;
  stale_review_count: number;
  not_reviewed_count: number;
};

export type CompanyEvidenceCollection = {
  summary: CompanyEvidenceSummary;
  evidence: CompanyEvidence[];
};

export type CompanyDocumentEvidenceAnalysis = {
  summary: CompanyEvidenceSummary & {
    document_id: string;
    company_id: string;
    text_extraction_status: string;
    extractor_version: string;
    warnings: string[];
  };
  evidence: CompanyEvidence[];
};

export type ManualEvidenceForm = {
  evidenceType: string;
  subjectKind: string;
  subjectName: string;
  canonicalStatement: string;
  issuer: string;
  referenceNumber: string;
  issuedOn: string;
  validFrom: string;
  validUntil: string;
  periodStart: string;
  periodEnd: string;
  sourceLocator: string;
  sourceExcerpt: string;
  reviewNote: string;
};


const path=(base:string,company:string)=>`${base}/companies/${encodeURIComponent(company)}`;
const documentPath=(base:string,company:string,document:string)=>`${path(base,company)}/documents/${encodeURIComponent(document)}`;
const own=(d:CompanyDocument,c:string)=>{if(d.company_id!==c)throw new Error('COMPANY_CONTEXT_MISMATCH');return d;};
export const companyApi={
 list:async(base:string)=>(await axios.get<Company[]>(`${base}/companies`)).data,
 create:async(base:string,input:{name:string;legal_name:string|null;tax_id:string|null})=>(await axios.post<Company>(`${base}/companies`,input)).data,
 documents:async(base:string,c:string,archived:boolean)=>{const values=(await axios.get<CompanyDocument[]>(`${path(base,c)}/documents`,{params:{include_archived:archived}})).data;if(!Array.isArray(values))throw new Error('INVALID_COMPANY_DOCUMENTS');return values.map(d=>own(d,c));},
 evidence:async(base:string,c:string,d:string)=>{const values=(await axios.get<CompanyEvidenceCollection>(`${documentPath(base,c,d)}/evidence`)).data;if(values.evidence.some(e=>e.company_id!==c||e.company_document_id!==d))throw new Error('EVIDENCE_CONTEXT_MISMATCH');return values;},
 metadata:async(base:string,c:string,d:string,input:Pick<CompanyDocument,'document_type'|'label'|'issuer'|'issue_date'|'expiration_date'|'metadata_note'>)=>own((await axios.patch<CompanyDocument>(documentPath(base,c,d),input)).data,c),
 archive:async(base:string,c:string,d:string,archived:boolean)=>own((await axios.patch<CompanyDocument>(`${documentPath(base,c,d)}/archive`,{archived})).data,c),
 import:async(base:string,c:string,file:File,action='NONE',target?:string)=>{const data=new FormData();data.append('files',file);data.append('source_relative_paths',file.webkitRelativePath||'');data.append('conflict_action',action);if(target)data.append('revision_of_document_id',target);const values=(await axios.post<CompanyImportResult[]>(`${path(base,c)}/documents/import`,data)).data;if(!Array.isArray(values)||values.length!==1||values[0].filename!==file.name)throw new Error('IMPORT_IDENTITY_MISMATCH');return values[0];},
 analyze:async(base:string,c:string,d:string)=>(await axios.post<CompanyDocumentEvidenceAnalysis>(`${documentPath(base,c,d)}/analyze-evidence`)).data,
 review:async(base:string,c:string,id:string,status:string,note:string|null)=>axios.patch(`${path(base,c)}/evidence/${encodeURIComponent(id)}/review`,{review_status:status,review_note:note}),
 manual:async(base:string,c:string,d:string,form:Record<string,string|null>)=>axios.post(`${documentPath(base,c,d)}/evidence/manual`,form),
 content:documentPath,
};
