import axios from "axios";
export type Readiness = {status: "READY" | "INCOMPLETE" | "REVIEW_REQUIRED"; reasons: {code: string; severity: "BLOCKER" | "REVIEW" | "WARNING"}[]; warnings: string[]; proposal_eligible: boolean};
export type ReadinessCounts = {status: Readiness["status"]; total_scope_items: number; ready_count: number; incomplete_count: number; review_required_count: number; warning_count: number; missing_commercial_treatment_count: number};
export type CommercialAudit = {current_revision: number; current_manual_price: boolean; scope_available: boolean; next_before_revision: number | null;
  events: {revision: number; timestamp: string; origin: "UI" | "API" | "BULK" | "XLSX" | "CSV"; action: string; actor_label: string | null; manual_price: boolean; note: string | null;
    offered_unit_price: string | null; recommended_unit_price: string | null; differs_from_recommendation: boolean | null;
    changes: {field: string; previous: string | null; current: string | null}[]; import_evidence: {sha256?: string} | null}[]};
export const auditApi = {read: async (base: string,tender: string,scope: string,before?: number) =>
  (await axios.get<CommercialAudit>(`${base}/tenders/${tender}/scopes/${scope}/commercial-audit`,{params:{limit:25,before_revision:before}})).data};
