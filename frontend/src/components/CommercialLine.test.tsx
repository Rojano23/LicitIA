import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { CommercialLine } from "./CommercialLine";
import { commercialApi, type CommercialRead } from "../api/commercial";
vi.mock("../api/commercial", async importOriginal => ({ ...await importOriginal<typeof import("../api/commercial")>(), commercialApi: { read: vi.fn(), save: vi.fn(), apply: vi.fn() } }));
const row: CommercialRead = { id: "line", tender_id: "t", scope_detail_id: "s", scope_id_at_creation: "s", revision: 1, created_at: "2026-10-21T00:00:00Z", updated_at: "2026-10-21T00:00:00Z", price_method: "MANUAL", price_value_origin: "MANUAL_INPUT", source_fingerprint: "f".repeat(64),
  inputs: { cost_source_type: "MANUAL", cost_value_origin: "MANUAL_INPUT", currency: "MXN", unit_cost: "100", offered_unit_price: "125", calculation_mode: "COST_FIRST", calculation_basis: "MARKUP", markup_percent: "25", target_margin_percent: null, reference_party_name: null, reference_party_reference: null, reference_party_note: null, quote_document_id: null, quote_reference: null, quantity_id: null, notes: null, input_origin: "UI", actor_label: null },
  source: { scope: null, quantities: [], selected_quantity_id: null }, history: [], summary: { recommended_unit_price: "125", total_cost: "200.00", offered_total: "250.00", profit: "50.00", actual_margin_percent: "20", actual_markup_percent: "25", currency: "MXN", status: "REVIEW_REQUIRED", warnings: ["SCOPE_REVIEW_REQUIRED"] } };
const props = { apiUrl: "http://local", tenderId: "t", scopeDetailId: "s", documents: [] };
beforeEach(() => { vi.clearAllMocks(); vi.mocked(commercialApi.read).mockResolvedValue(row); vi.mocked(commercialApi.save).mockResolvedValue(row); vi.mocked(commercialApi.apply).mockResolvedValue(row); });
it("does not automatically read or write commercial decisions", async () => {
  render(<CommercialLine {...props} />); expect(commercialApi.read).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Comercial")); expect(await screen.findByText("250.00 MXN")).toBeInTheDocument();
  expect(screen.getByText(/SCOPE_REVIEW_REQUIRED/)).toBeInTheDocument(); expect(commercialApi.save).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Cantidad")).not.toBeInTheDocument();
});
it("sends decimal strings and preserves untouched manual offered price", async () => {
  render(<CommercialLine {...props} />); fireEvent.click(screen.getByText("Comercial")); await screen.findByLabelText("Costo unitario");
  fireEvent.change(screen.getByLabelText("Costo unitario"), {target:{value:"0.10"}});
  fireEvent.change(screen.getByLabelText("Markup objetivo (%)"), {target:{value:"40"}});
  fireEvent.click(screen.getByText("Guardar decisión comercial"));
  await waitFor(() => expect(commercialApi.save).toHaveBeenCalled());
  expect(vi.mocked(commercialApi.save).mock.calls[0][3]).toEqual({unit_cost:"0.10", markup_percent:"40", input_origin:"UI"});
});
it("requires confirmation before replacing manual price", async () => {
  const confirm = vi.spyOn(window,"confirm").mockReturnValue(false);
  render(<CommercialLine {...props} />); fireEvent.click(screen.getByText("Comercial")); fireEvent.click(await screen.findByText("Aplicar recomendación al precio"));
  expect(confirm).toHaveBeenCalled(); expect(commercialApi.apply).not.toHaveBeenCalled();
  confirm.mockReturnValue(true); fireEvent.click(screen.getByText("Aplicar recomendación al precio"));
  await waitFor(() => expect(commercialApi.apply).toHaveBeenCalledWith(props.apiUrl,"t","s",row,true)); confirm.mockRestore();
});
it("blocks writes after read error", async () => {
  vi.mocked(commercialApi.read).mockRejectedValue(new Error("offline"));
  render(<CommercialLine {...props} />); fireEvent.click(screen.getByText("Comercial"));
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo consultar");
  expect(screen.queryByText("Guardar decisión comercial")).not.toBeInTheDocument();
});
it("creates a draft without asking for canonical fields", async () => {
  vi.mocked(commercialApi.read).mockResolvedValue(null); render(<CommercialLine {...props} />); fireEvent.click(screen.getByText("Comercial"));
  fireEvent.click(await screen.findByText("Guardar decisión comercial")); await waitFor(() => expect(commercialApi.save).toHaveBeenCalled());
  expect(vi.mocked(commercialApi.save).mock.calls[0][3]).not.toHaveProperty("description"); expect(vi.mocked(commercialApi.save).mock.calls[0][4]).toBeNull();
});
