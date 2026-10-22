import axios from "axios";
import type { WorkspaceQuantity, WorkspaceSource } from "./workspace";

export const costSources = ["SUPPLIER_QUOTE", "INTERNAL_COST", "MANUFACTURER_COST", "HISTORICAL_REFERENCE", "ESTIMATE", "MANUAL", "NOT_APPLICABLE"] as const;
export const valueOrigins = ["CONFIRMED_QUOTE", "HISTORICAL_COST", "SYSTEM_ESTIMATE", "MANUAL_INPUT"] as const;
export type CommercialInputs = {
  cost_source_type: typeof costSources[number]; cost_value_origin: typeof valueOrigins[number];
  reference_party_name: string | null; reference_party_reference: string | null; reference_party_note: string | null;
  quote_document_id: string | null; quote_reference: string | null; currency: "MXN" | "USD" | "EUR" | null;
  unit_cost: string | null; offered_unit_price: string | null; calculation_mode: "COST_FIRST" | "PRICE_FIRST";
  calculation_basis: "MARKUP" | "MARGIN" | null; markup_percent: string | null; target_margin_percent: string | null;
  quantity_id: string | null; notes: string | null; input_origin: "UI" | "API"; actor_label: string | null;
};
export type CommercialSummary = {
  recommended_unit_price: string | null; total_cost: string | null; offered_total: string | null; profit: string | null;
  actual_markup_percent: string | null; actual_margin_percent: string | null; currency: string | null;
  status: "READY" | "INCOMPLETE" | "REVIEW_REQUIRED"; warnings: string[];
};
export type CommercialRead = {
  id: string; tender_id: string; scope_detail_id: string | null; scope_id_at_creation: string; revision: number;
  created_at: string; updated_at: string; inputs: CommercialInputs; price_method: "MANUAL" | "CALCULATED" | null;
  price_value_origin: string | null; source_fingerprint: string;
  source: { scope: { description: string; source: WorkspaceSource; review_status: string } | null; quantities: WorkspaceQuantity[]; selected_quantity_id: string | null };
  summary: CommercialSummary;
  history: { revision: number; action: string; created_at: string; inputs: CommercialInputs; price_method: string | null; price_value_origin: string | null }[];
};
const path = (base: string, tender: string, scope: string) => `${base}/tenders/${tender}/scopes/${scope}/commercial-line`;
const expectation = (line: CommercialRead) => ({ expected_revision: line.revision, expected_source_fingerprint: line.source_fingerprint });
export const commercialApi = {
  read: async (base: string, tender: string, scope: string) => {
    try { return (await axios.get<CommercialRead>(path(base, tender, scope))).data; }
    catch (error) { if (axios.isAxiosError(error) && error.response?.status === 404) return null; throw error; }
  },
  save: async (base: string, tender: string, scope: string, fields: Partial<CommercialInputs>, line: CommercialRead | null) =>
    line ? (await axios.patch<CommercialRead>(path(base, tender, scope), { ...fields, ...expectation(line) })).data
      : (await axios.post<CommercialRead>(path(base, tender, scope), fields)).data,
  apply: async (base: string, tender: string, scope: string, line: CommercialRead, replace: boolean) =>
    (await axios.post<CommercialRead>(`${path(base, tender, scope)}/calculate`, {
      ...expectation(line), apply_calculated_price: true, replace_manual_price: replace,
    })).data,
};
