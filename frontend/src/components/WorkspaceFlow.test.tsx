import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { workspaceApi, type WorkspaceRead, type WorkspaceSource } from "../api/workspace";
import { scopeItem } from "../test/scopeReviewFixtures";
import { WorkspaceFlow } from "./WorkspaceFlow";

const props = { apiUrl: "http://localhost:8000", tenderId: "tender-1", documents: [{ id: "doc-1", original_filename: "generic.pdf" }] };
const source: WorkspaceSource = { document_id: "doc-1", filename: "generic.pdf", revision: 1, page: 2, excerpt: "Texto fuente", locator: "page:2", method: "NATIVE", available: true };
function fixture(): WorkspaceRead {
  return {
    tender_id: props.tenderId, processing: { status: "COMPLETED_REVIEW_REQUIRED", run_id: "run", error_code: null, context_sha256: "hash" },
    scopes: ["31", "32"].map((id, index) => ({ scope_detail_id: id, candidate_item_key: id, description: `Equipo ${id}`, source,
      review: scopeItem(id), quantities: [{ id: `quantity-${id}`, tender_id: props.tenderId, scope_detail_id: id,
        quantity_raw: index ? "7" : "3", quantity_value: index ? "7.0000" : "3.0000", quantity_min: null, quantity_max: null,
        unit_raw: "PZA", relation: "EXACT", review_required: true, status: "REVIEW_REQUIRED", source }] })),
    requirements: { scope_note: "Alcance provisional", requirements: [] }, semantics: { scope_note: "Requiere validación", requirements: [] }, warnings: [],
  };
}
let data: WorkspaceRead;
beforeEach(() => {
  vi.restoreAllMocks(); data = fixture();
  vi.spyOn(workspaceApi, "read").mockImplementation(async () => structuredClone(data));
  vi.spyOn(workspaceApi, "process").mockImplementation(async () => structuredClone(data));
});
it("preserves two Scope parents and their distinct quantity/source associations", async () => {
  render(<WorkspaceFlow {...props} />);
  const first = await screen.findByRole("article", { name: "Alcance 31" });
  const second = screen.getByRole("article", { name: "Alcance 32" });
  expect(within(first).getByText(/Cantidad: 3 PZA/)).toBeInTheDocument();
  expect(within(first).queryByText(/Cantidad: 7 PZA/)).not.toBeInTheDocument();
  expect(within(second).getByText(/Cantidad: 7 PZA/)).toBeInTheDocument();
  expect(within(first).getAllByRole("link", { hidden: true })[0]).toHaveAttribute("href", expect.stringContaining("/doc-1/content#page=2"));
  expect(screen.getByText(/Confirmar el alcance no confirma sus cantidades/)).toBeInTheDocument();
  expect(workspaceApi.process).not.toHaveBeenCalled();
});
it("processes only through an explicit user action", async () => {
  render(<WorkspaceFlow {...props} />);
  await screen.findByText("Completado con revisión requerida");
  fireEvent.click(screen.getByRole("button", { name: "Procesar documentos disponibles" }));
  await waitFor(() => expect(workspaceApi.process).toHaveBeenCalledWith(props.apiUrl, props.tenderId));
});
it("shows empty outputs and disables processing without documents", async () => {
  data.scopes = []; data.processing.status = "NOT_PROCESSED";
  render(<WorkspaceFlow {...props} documents={[]} />);
  expect(await screen.findByText(/Sin resultados de alcance/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Procesar documentos disponibles" })).toBeDisabled();
  expect(screen.getByText(/no es una lista contractual certificada/)).toBeInTheDocument();
});
it("handles backend unavailability without hiding the review entry point", async () => {
  vi.mocked(workspaceApi.read).mockRejectedValue(new Error("offline"));
  render(<WorkspaceFlow {...props} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("backend esté disponible");
  expect(screen.getByRole("button", { name: "Abrir revisión de alcance" })).toBeInTheDocument();
});
it("rejects mismatched parent ownership in frontend mapping", async () => {
  data.scopes[0].quantities[0].scope_detail_id = "32";
  render(<WorkspaceFlow {...props} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("asociación no válida");
  expect(screen.queryByText(/Cantidad: 3 PZA/)).not.toBeInTheDocument();
});
it("shows source unavailable, unresolved quantities and degraded processing", async () => {
  data.processing.status = "PARTIAL";
  data.scopes[0].source = { ...source, available: false };
  data.scopes[0].quantities[0].status = "UNRESOLVED";
  render(<WorkspaceFlow {...props} />);
  expect(await screen.findByText(/Resultado parcial/)).toBeInTheDocument();
  expect(screen.getByText("Fuente no disponible")).toBeInTheDocument();
  expect(screen.getByText(/Cantidad: 3 PZA.*Sin resolver/)).toBeInTheDocument();
});
it("renders canonical Requirements and Requested Evidence with uncertainty and provenance", async () => {
  const requirement = { requirement_id: "r-1", canonical_text: "Presentar carta", normalization_status: "REVIEW_REQUIRED", interpretation_status: "REVIEW_REQUIRED",
    interpretation_reason: "Condición por verificar", applicability: "UNKNOWN", evidence_mode: "EXPLICIT_ARTIFACT",
    primary_source: { source_document_id: "doc-1", source_filename: "generic.pdf", source_page: 2, source_excerpt: "Carta firmada" },
    expected_evidence: [{ id: "e-1", requirement_id: "r-1", evidence_type: "DOCUMENT", evidence_description: "Carta de garantía", source_document_id: "doc-1", source_filename: "generic.pdf", source_page: 2, source_excerpt: "Carta firmada" }] };
  data.requirements.requirements = [{ ...requirement, effective_status: "UNRESOLVED", review_status: "PENDING", review_freshness: "NOT_REVIEWED", system_warnings: ["Revisar fuente"] }];
  data.semantics.requirements = [requirement];
  render(<WorkspaceFlow {...props} />);
  await screen.findByText("Presentar carta");
  expect(screen.getByText(/Carta de garantía/)).toBeInTheDocument();
  expect(screen.getByText(/Revisión: PENDING/)).toBeInTheDocument();
  expect(screen.getByText("Revisar fuente")).toBeInTheDocument();
  expect(screen.getByText("Evidencia solicitada — requiere validación humana")).toBeInTheDocument();
});
it("keeps failed processing visible after a process request fails", async () => {
  data.processing.status = "FAILED";
  vi.mocked(workspaceApi.process).mockRejectedValue(new Error("failed"));
  render(<WorkspaceFlow {...props} />);
  await screen.findByText(/Falló el procesamiento/);
  fireEvent.click(screen.getByRole("button", { name: "Procesar documentos disponibles" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo completar");
  expect(screen.getByText(/Falló el procesamiento/)).toBeInTheDocument();
});

it("offers explicit safe retry after recovery verification and submits the server fingerprint", async () => {
  const { recoveryApi } = await import("../api/workspace");
  vi.spyOn(recoveryApi, "read").mockResolvedValue({ eligible: true, fingerprint: "identity", reasons: [], effect: "REUSE_AVAILABLE_EVIDENCE", previous_results_preserved: true, provider_acquisition: false, provider_degraded: true });
  vi.spyOn(recoveryApi, "retry").mockResolvedValue(data);
  render(<WorkspaceFlow {...props} />);
  await screen.findByText("Completado con revisión requerida");
  fireEvent.click(screen.getByRole("button", { name: "Verificar recuperación" }));
  const retry = await screen.findByRole("button", { name: "Reintentar de forma segura" });
  expect(screen.getByText(/Se conserva la evidencia determinista válida/)).toBeInTheDocument();
  expect(recoveryApi.retry).not.toHaveBeenCalled();
  fireEvent.click(retry);
  await waitFor(() => expect(recoveryApi.retry).toHaveBeenCalledWith(props.apiUrl, props.tenderId, "identity"));
});
it("keeps unsafe recovery blocked and preserves the diagnostic", async () => {
  const { recoveryApi } = await import("../api/workspace");
  vi.spyOn(recoveryApi, "read").mockResolvedValue({ eligible: false, fingerprint: "identity", reasons: ["ORIGINAL_CHANGED"], effect: "REUSE_AVAILABLE_EVIDENCE", previous_results_preserved: true, provider_acquisition: false, provider_degraded: false });
  const retry = vi.spyOn(recoveryApi, "retry");
  render(<WorkspaceFlow {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Verificar recuperación" }));
  expect(await screen.findByRole("button", { name: "Reintentar de forma segura" })).toBeDisabled();
  expect(screen.getByText(/ORIGINAL_CHANGED/)).toBeInTheDocument();
  expect(retry).not.toHaveBeenCalled();
});
it("shows recovery backend failure without offering an unverified retry", async () => {
  const { recoveryApi } = await import("../api/workspace");
  vi.spyOn(recoveryApi, "read").mockRejectedValue(new Error("offline"));
  render(<WorkspaceFlow {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Verificar recuperación" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo verificar la recuperación");
  expect(screen.queryByRole("button", { name: "Reintentar de forma segura" })).not.toBeInTheDocument();
});

it("UIR3 processing-only composition does not mount downstream domains and pauses reads when inactive", async () => {
 const view=render(<WorkspaceFlow {...props} processingOnly active={false}/>);
 expect(workspaceApi.read).not.toHaveBeenCalled();
 expect(screen.queryByText('Alcance y cantidades')).not.toBeInTheDocument();
 expect(screen.queryByText('Abrir revisión de alcance')).not.toBeInTheDocument();
 view.rerender(<WorkspaceFlow {...props} processingOnly active/>);
 await screen.findByText('Completado con revisión requerida');
 expect(workspaceApi.read).toHaveBeenCalledTimes(1);
 expect(screen.queryByText('Alcance y cantidades')).not.toBeInTheDocument();
});
