import axios from "axios";
import type { ScopeReviewItem } from "./scopeReview";

export type ProcessingStatus = "NOT_PROCESSED" | "PROCESSING" | "COMPLETED" | "COMPLETED_REVIEW_REQUIRED" | "PARTIAL" | "FAILED" | "INTERRUPTED" | "STALE";
export type WorkspaceSource = {
  document_id: string; filename: string | null; revision: number | null;
  page: number | null; excerpt: string; locator: string; method: string; available: boolean;
};
export type WorkspaceQuantity = {
  id: string; tender_id: string; scope_detail_id: string; quantity_raw: string;
  quantity_value: string | null; quantity_min: string | null; quantity_max: string | null;
  unit_raw: string | null; relation: string | null; review_required: boolean;
  status: "REVIEW_REQUIRED" | "NOT_REQUIRED" | "UNRESOLVED"; source: WorkspaceSource;
};
export type WorkspaceScope = {
  scope_detail_id: string; candidate_item_key: string | null; description: string;
  source: WorkspaceSource; review: ScopeReviewItem | null; quantities: WorkspaceQuantity[];
};
type RequirementSource = {
  source_document_id: string; source_filename: string | null; source_page: number | null; source_excerpt: string;
};
export type RequestedEvidence = {
  id: string; requirement_id: string; evidence_type: string; evidence_description: string;
  source_document_id: string | null; source_filename: string | null; source_page: number | null; source_excerpt: string;
};
export type WorkspaceRequirement = {
  requirement_id: string; canonical_text: string; normalization_status: string;
  interpretation_status: string; interpretation_reason: string | null; applicability: string;
  evidence_mode: string; primary_source: RequirementSource | null; expected_evidence: RequestedEvidence[];
};
export type WorkspaceRead = {
  tender_id: string;
  processing: { status: ProcessingStatus; run_id: string | null; error_code: string | null; context_sha256: string | null };
  scopes: WorkspaceScope[];
  requirements: { scope_note: string; requirements: (WorkspaceRequirement & {
    effective_status: string; review_status: string; review_freshness: string; system_warnings: string[];
  })[] };
  semantics: { scope_note: string; requirements: WorkspaceRequirement[] };
  warnings: string[];
};
export const workspaceApi = {
  read: async (apiUrl: string, tenderId: string): Promise<WorkspaceRead> =>
    (await axios.get<WorkspaceRead>(`${apiUrl}/tenders/${tenderId}/workspace`)).data,
  process: async (apiUrl: string, tenderId: string): Promise<WorkspaceRead> =>
    (await axios.post<WorkspaceRead>(`${apiUrl}/tenders/${tenderId}/workspace/process`)).data,
};
