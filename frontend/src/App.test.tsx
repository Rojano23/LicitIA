import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { scopeItem } from "./test/scopeReviewFixtures";
import { alternative, evaluation } from "./test/alternativeFixtures";

const tender = {
  id: "tender-1", title: "Licitación sintética de interfaz", institution_profile: "General",
  external_reference: "UI-SYNTHETIC", status: "DRAFT", created_at: "2026-10-12T12:00:00Z", updated_at: "2026-10-12T12:00:00Z",
};

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(axios, "get").mockImplementation(async (url: string) => {
    if (url.endsWith("/tenders")) return { data: [tender] };
    if (url.endsWith("/companies") || url.endsWith("/documents")) return { data: [] };
    if (url.endsWith("/scope-review")) return { data: [scopeItem()] };
    if (url.endsWith("/scope-review/scope-1")) return { data: scopeItem() };
    // Existing unrelated panels keep their normal recoverable-error paths.
    throw new Error("Synthetic unavailable endpoint");
  });
  vi.spyOn(axios, "post").mockRejectedValue(new Error("No automatic writes allowed"));
});

it("workspace selection exposes Scope Review beside canonical items without automatic writes", async () => {
  const user = userEvent.setup();
  render(<App />);
  expect(screen.getByRole("heading", { name: "RX23 TuScope — Licitaciones" })).toBeVisible();
  expect(screen.getByRole("heading", { name: /Biblioteca empresarial/ })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Revisión de alcance" })).not.toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: /Licitación sintética de interfaz/ }));
  expect(screen.getByRole("heading", { name: "Partidas canónicas" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Revisión de alcance" })).toBeVisible();
  expect(window.localStorage.getItem("licitia_selected_tender_id")).toBe(tender.id);
  expect(axios.get).not.toHaveBeenCalledWith("http://localhost:8000/tenders/tender-1/scope-review");
  await user.click(screen.getByRole("button", { name: "Abrir revisión de alcance" }));
  await screen.findByRole("heading", { name: "Lo que RX23 TuScope encontró" });
  expect(within(screen.getByLabelText("Detalle de alcance")).getByText("numeral 4.2")).toBeVisible();
  expect(axios.post).not.toHaveBeenCalled();
});

it("workspace restores the selected tender and preserves the existing create form", async () => {
  window.localStorage.setItem("licitia_selected_tender_id", tender.id);
  render(<App />);
  await waitFor(() => expect(screen.getByRole("heading", { name: "Revisión de alcance" })).toBeVisible());
  expect(screen.getByRole("button", { name: "Create Tender" })).toBeEnabled();
  expect(screen.getByLabelText("Title")).toHaveValue("");
  expect(axios.post).not.toHaveBeenCalled();
});

it("workspace opens alternatives beside Scope Review with independent backend states", async () => {
  const original = vi.mocked(axios.get).getMockImplementation()!;
  vi.mocked(axios.get).mockImplementation(async (url: string) => {
    if (url.endsWith("/technical-alternatives")) return { data: [alternative()] };
    if (url.endsWith("/technical-alternatives/alt-a")) return { data: alternative() };
    if (url.endsWith("/alternative-scope-snapshot")) return { data: evaluation().scope_snapshot };
    if (url.endsWith("/compliance")) return { data: [evaluation()] };
    if (url.endsWith("/compliance/eval-1")) return { data: evaluation() };
    return original(url);
  });
  const user = userEvent.setup(); render(<App />);
  await user.click(await screen.findByRole("button", { name: /Licitación sintética de interfaz/ }));
  expect(screen.getByRole("heading", { name: "Revisión de alcance" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Alternativas técnicas" })).toBeVisible();
  expect(axios.get).not.toHaveBeenCalledWith("http://localhost:8000/tenders/tender-1/technical-alternatives");
  await user.click(screen.getByRole("button", { name: "Abrir alternativas técnicas" }));
  expect(await screen.findByLabelText("Detalle de evaluación")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Lo que exige la licitación" })).toBeVisible();
  expect(axios.post).not.toHaveBeenCalled();
});
