import axios from "axios";

export type ReviewDecision = "CONFIRMED" | "CORRECTED" | "REJECTED";
export type EffectiveReviewStatus = "NOT_REQUIRED" | "PENDING" | "CONFIRMED" | "CORRECTED" | "REJECTED" | "STALE_REVIEW" | "SOURCE_BLOCKED";

export type ScopeMachineEvidence = {
  id: string;
  tender_id: string;
  tender_item_id: string | null;
  scope_segment_id: string | null;
  candidate_item_key: string | null;
  source_document_id: string;
  document_page_id: string;
  source_analysis_id: string | null;
  source_page_result_id: string | null;
  domain: string;
  detail_type: string | null;
  description: string;
  normalized_label: string | null;
  applicability: string;
  source_method: string;
  source_artifact_key: string;
  source_contract_version: string | null;
  source_locator: string;
  source_excerpt: string;
  confidence: number | null;
  review_required: boolean;
  quantity_raw: string | null;
  unit_raw: string | null;
  semantic_fingerprint: string;
  created_at: string;
  updated_at: string;
  document_revision: number;
  source_page: number;
};

export type ScopeHumanReview = {
  id: string;
  tender_id: string;
  scope_detail_id: string;
  revision: number;
  decision: ReviewDecision;
  correction: { description: string } | null;
  note: string | null;
  machine_snapshot: ScopeMachineEvidence;
  reviewed_source_fingerprint: string;
  reviewed_at: string;
};

export type ScopeProjectionDiagnostic = {
  code: string;
  message: string;
  effect_ids: string[];
  entity_type: string | null;
  entity_id: string | null;
  source_document_id: string | null;
  source_locator: string | null;
  parent_entity_id: string | null;
};

export type ScopeSourceProjection = {
  entity_type: string;
  entity_id: string;
  source_document_id: string | null;
  document_page_id: string | null;
  source_locator: string | null;
  status: string;
  document_effective_status: string | null;
  partial_locator_status: string | null;
  supporting_effect_ids: string[];
  blocking_effect_ids: string[];
  diagnostics: ScopeProjectionDiagnostic[];
};

export type EffectiveScopeReview = {
  machine: ScopeMachineEvidence;
  latest_review: ScopeHumanReview | null;
  human_review_status: "NO_REVIEW" | "CURRENT" | "STALE";
  effective_status: EffectiveReviewStatus;
  effective_description: string;
  accepted_execution_scope: boolean;
  machine_review_required: boolean;
  human_resolved_machine_review: boolean;
  source_blocked: boolean;
  source_projection: ScopeSourceProjection;
};

export type ScopeReviewHistoryEntry = {
  review: ScopeHumanReview;
  applicable: boolean;
  reason: "CURRENT" | "HISTORICAL_REVISION" | "TARGET_CHANGED" | "TARGET_REMOVED";
};

export type ScopeReviewItem = {
  scope_detail_id: string;
  current: EffectiveScopeReview | null;
  projection_fingerprint: string | null;
  current_review_revision: number | null;
  latest_applicable_review: ScopeHumanReview | null;
  reviewable: boolean;
  not_reviewable_reason: string | null;
  history: ScopeReviewHistoryEntry[];
};

// Only description may be corrected. The discriminated union excludes corrections
// from confirmation/rejection and keeps concurrency fields mandatory.
type DecisionExpectations = {
  expected_projection_fingerprint: string;
  expected_current_review_revision: number | null;
  note?: string | null;
};
export type ScopeReviewDecisionRequest = DecisionExpectations & (
  | { decision: "CORRECTED"; correction: { description: string } }
  | { decision: "CONFIRMED" | "REJECTED"; correction?: never }
);

export function scopeReviewApi(apiUrl: string, tenderId: string) {
  const base = `${apiUrl}/tenders/${encodeURIComponent(tenderId)}/scope-review`;
  return {
    async list(): Promise<ScopeReviewItem[]> {
      return (await axios.get<ScopeReviewItem[]>(base)).data;
    },
    async detail(id: string): Promise<ScopeReviewItem> {
      return (await axios.get<ScopeReviewItem>(`${base}/${encodeURIComponent(id)}`)).data;
    },
    async decide(id: string, payload: ScopeReviewDecisionRequest): Promise<ScopeReviewItem> {
      return (await axios.post<ScopeReviewItem>(`${base}/${encodeURIComponent(id)}/decisions`, payload)).data;
    },
  };
}

export function scopeReviewError(error: unknown): { status?: number; code?: string } {
  if (!axios.isAxiosError<{ detail?: { code?: string } }>(error)) return {};
  return { status: error.response?.status, code: error.response?.data?.detail?.code };
}
