import axios from "axios";
import type { AlternativeRevision } from "./technicalAlternatives";
import type { ScopeMachineEvidence, ScopeSourceProjection } from "./scopeReview";

export type ComplianceStatus = "COMPLIANT" | "PARTIAL" | "NON_COMPLIANT" | "REVIEW_REQUIRED" | "NOT_EVALUATED";
export type EvaluationApplicability = "CURRENT" | "STALE_ALTERNATIVE" | "STALE_SCOPE" | "STALE_BOTH";
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type FrozenScopeItem = {
  scope_detail_id: string; effective_description: string; accepted_execution_scope: boolean;
  unresolved: boolean; effective_status: string; human_review_status: string;
  current_review_revision: number | null;
  // HTTP uses a JSON map and missing provenance may omit document_revision/source_page.
  machine: Partial<Omit<ScopeMachineEvidence, "created_at" | "updated_at">>;
  source_projection: ScopeSourceProjection | null;
  applicable_review: { [key: string]: JsonValue } | null;
  projection_fingerprint: string;
};
export type ScopeSnapshot = { tender_id: string; items: FrozenScopeItem[]; fingerprint: string; unresolved: boolean };
export type ComplianceDecision = {
  id: string; revision: number; status: ComplianceStatus; rationale: string;
  evidence_note: string | null; created_at: string;
};
export type ComplianceItem = {
  item_key: string; item_index: number; snapshot: FrozenScopeItem;
  status: ComplianceStatus; latest_decision: ComplianceDecision | null; decisions: ComplianceDecision[];
};
export type ComplianceEvaluation = {
  id: string; tender_id: string; alternative_id: string; alternative_revision: AlternativeRevision;
  scope_snapshot: ScopeSnapshot; created_at: string; applicability: EvaluationApplicability;
  overall_status: ComplianceStatus | "STALE"; historical_aggregate: ComplianceStatus;
  counts: Record<ComplianceStatus, number>; items: ComplianceItem[];
};
export type EvaluationCreate = {
  expected_alternative_revision: number; expected_alternative_fingerprint: string;
  expected_scope_snapshot_fingerprint: string;
};
export type ComplianceDecisionWrite = {
  status: Exclude<ComplianceStatus, "NOT_EVALUATED">; rationale: string; evidence_note: string | null;
  expected_current_decision_revision: number | null;
};
export function alternativeComplianceApi(apiUrl: string, tenderId: string, alternativeId: string) {
  const tender = `${apiUrl}/tenders/${encodeURIComponent(tenderId)}`;
  const base = `${tender}/technical-alternatives/${encodeURIComponent(alternativeId)}/compliance`;
  return {
    async scope(): Promise<ScopeSnapshot> { return (await axios.get<ScopeSnapshot>(`${tender}/alternative-scope-snapshot`)).data; },
    async list(): Promise<ComplianceEvaluation[]> { return (await axios.get<ComplianceEvaluation[]>(base)).data; },
    async detail(id: string): Promise<ComplianceEvaluation> {
      return (await axios.get<ComplianceEvaluation>(`${base}/${encodeURIComponent(id)}`)).data;
    },
    async create(payload: EvaluationCreate): Promise<ComplianceEvaluation> {
      return (await axios.post<ComplianceEvaluation>(base, payload)).data;
    },
    async decide(id: string, itemKey: string, payload: ComplianceDecisionWrite): Promise<ComplianceEvaluation> {
      return (await axios.post<ComplianceEvaluation>(`${base}/${encodeURIComponent(id)}/items/${encodeURIComponent(itemKey)}/decisions`, payload)).data;
    },
  };
}
