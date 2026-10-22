import axios from "axios";
import type { CommercialInputs, CommercialRead, CommercialSummary } from "./commercial";
export type MatrixRow = {
  scope_id: string; item_reference: string | null; description: string; commercial_line_id: string | null;
  revision: number | null; source_fingerprint: string; initialized: boolean; inputs: CommercialInputs;
  source: CommercialRead["source"]; summary: CommercialSummary; manual_price_protected: boolean;
  price_method: string | null; price_value_origin: string | null; commercial_complete: boolean;
  warning_count: number; offered_price_status: string | null; unresolved_cost: boolean;
};
export type CurrencySummary = { currency: string | null; line_count: number; status_counts: Record<string, number>;
  total_cost: string | null; offered_total: string | null; profit: string | null;
  total_cost_calculable_count: number; offered_total_calculable_count: number; profit_calculable_count: number;
  total_cost_missing_count: number; offered_total_missing_count: number; profit_missing_count: number;
  paired_count: number; paired_markup_percent: string | null; paired_margin_percent: string | null };
export type MatrixRead = { tender_id: string; rows: MatrixRow[]; summary_by_currency: CurrencySummary[]; archived_lines: {id: string; scope_id: string; warning: string}[] };
export const target = (row: MatrixRow) => ({scope_id: row.scope_id, expected_revision: row.revision, expected_source_fingerprint: row.source_fingerprint});
export type BulkAction = "PATCH" | "MARKUP" | "MARGIN" | "RECALCULATE" | "COPY_SETTINGS" | "INITIALIZE";
export type BulkWrite = { operation_id?: string; targets: ReturnType<typeof target>[]; action: BulkAction;
  changes: Partial<CommercialInputs>; row_changes?: Record<string, Partial<CommercialInputs>>; defaults: Partial<CommercialInputs>; copy_from?: ReturnType<typeof target>;
  recalculate: boolean; replace_manual_price: boolean; confirm_currency_change: boolean; input_origin: "UI"; apply: boolean };
export type BulkRead = { operation_id: string; applied: boolean; counts: Record<string, number>; outcomes: {
  scope_id: string; outcome: string; reasons: string[]; warnings?: string[]; price_outcome: string;
  proposed_inputs?: CommercialInputs; revision?: number; validation_fields?: string[] }[] };
const path = (base: string, tender: string) => `${base}/tenders/${tender}/commercial-matrix`;
export const matrixApi = {
  read: async (base: string, tender: string) => (await axios.get<MatrixRead>(path(base,tender))).data,
  bulk: async (base: string, tender: string, payload: BulkWrite) => (await axios.post<BulkRead>(`${path(base,tender)}/bulk`,payload)).data,
};
