import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScopeReview } from "./ScopeReview";
import type { ScopeReviewItem } from "../api/scopeReview";
import { humanReview, scopeItem } from "../test/scopeReviewFixtures";

const props = { apiUrl: "http://localhost:8000", tenderId: "tender-1", documents: [{ id: "document-1", original_filename: "Alcance sintético.pdf" }] };
let queue: ScopeReviewItem[];
let details: Map<string, ScopeReviewItem>;
let get = vi.spyOn(axios, "get");
let post = vi.spyOn(axios, "post");

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
function apiFailure(status: number, code?: string) {
  return { isAxiosError: true, response: { status, data: { detail: { code } } } };
}
function detailRegion() {
  return screen.getByLabelText("Detalle de alcance");
}
async function open() {
  const user = userEvent.setup();
  render(<ScopeReview {...props} />);
  await user.click(screen.getByRole("button", { name: "Abrir revisión de alcance" }));
  return user;
}
async function loaded() {
  await screen.findByRole("heading", { name: "Lo que LicitIA encontró" });
}
function seed(item: ScopeReviewItem) {
  queue = [item];
  details.set(item.scope_detail_id, item);
}
function confirmed(item: ScopeReviewItem): ScopeReviewItem {
  const review = humanReview(item);
  return { ...item, current_review_revision: 1, latest_applicable_review: review,
    history: [{ review, applicable: true, reason: "CURRENT" }],
    current: { ...item.current!, latest_review: review, human_review_status: "CURRENT", effective_status: "CONFIRMED",
      accepted_execution_scope: true, human_resolved_machine_review: true } };
}

beforeEach(() => {
  const item = scopeItem();
  queue = [item];
  details = new Map([[item.scope_detail_id, item]]);
  // All HTTP is mocked: no local database, document corpus or model is accessed.
  get = vi.spyOn(axios, "get").mockImplementation(async (url: string) => {
    if (url.endsWith("/scope-review")) return { data: queue };
    const item = details.get(decodeURIComponent(url.split("/").pop() ?? ""));
    if (!item) throw apiFailure(404);
    return { data: item };
  });
  post = vi.spyOn(axios, "post").mockResolvedValue({ data: confirmed(item) });
});

describe("MVP-06.6.3 Human Scope Review", () => {
  it("UI01 renders queue from API in backend order", async () => {
    queue = [scopeItem("z"), scopeItem("a")];
    details = new Map(queue.map((item) => [item.scope_detail_id, item]));
    await open();
    await loaded();
    const buttons = within(screen.getByLabelText("Cola de revisión de alcance")).getAllByRole("button").filter((button) => button.textContent?.includes("Inspeccionar equipo"));
    expect(buttons.map((button) => button.textContent?.slice(0, 21))).toEqual(["Inspeccionar equipo z", "Inspeccionar equipo a"]);
    expect(get).toHaveBeenCalledWith("http://localhost:8000/tenders/tender-1/scope-review");
  });

  it("UI02 selecting an item loads its detail endpoint", async () => {
    queue.push(scopeItem("scope-2"));
    details.set("scope-2", queue[1]);
    const user = await open();
    await loaded();
    await user.click(screen.getByRole("button", { name: /Inspeccionar equipo scope-2/ }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("http://localhost:8000/tenders/tender-1/scope-review/scope-2"));
    expect((await within(detailRegion()).findAllByText("Inspeccionar equipo scope-2"))[0]).toBeVisible();
  });

  it("UI03 shows source document, revision, page, locator and excerpt", async () => {
    await open(); await loaded();
    const region = within(detailRegion());
    expect(region.getByText("Alcance sintético.pdf")).toBeVisible();
    expect(region.getByText("Versión documental")).toBeVisible();
    expect(region.getByText("3")).toBeVisible();
    expect(region.getByText("7")).toBeVisible();
    expect(region.getByText("numeral 4.2")).toBeVisible();
    expect(region.getByText("Se deberá inspeccionar el equipo de control.")).toBeVisible();
    expect(region.getByRole("link", { name: "Abrir documento fuente en página 7" })).toHaveAttribute("href", "http://localhost:8000/tenders/tender-1/documents/document-1/content#page=7");
  });

  it("UI04 displays pending machine review and human-readable reason", async () => {
    await open(); await loaded();
    const region = within(detailRegion());
    expect(region.getByText("Requiere revisión", { selector: "strong" })).toBeVisible();
    expect(region.getByText("Sin revisión humana")).toBeVisible();
    expect(region.getByText("LicitIA originalmente requirió revisión.")).toBeVisible();
    expect(region.getByText("LicitIA marcó este hallazgo para revisión humana.")).toBeVisible();
  });

  it("UI05 confirmation sends exact fingerprint/revision and optional note", async () => {
    const item = scopeItem(); item.projection_fingerprint = "d".repeat(64); item.current_review_revision = 4;
    seed(item);
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(screen.getByText(/Se aceptará como alcance de ejecución/)).toBeVisible();
    await user.type(screen.getByLabelText("Nota de revisión (opcional)"), "Validado");
    await user.click(screen.getByRole("button", { name: "Guardar confirmación" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("http://localhost:8000/tenders/tender-1/scope-review/scope-1/decisions", {
      decision: "CONFIRMED", note: "Validado", expected_projection_fingerprint: "d".repeat(64), expected_current_review_revision: 4,
    }));
  });

  it("UI06 correction edits only description and rejects whitespace", async () => {
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Corregir" }));
    const input = screen.getByLabelText("Descripción corregida");
    expect(input).toHaveValue("Inspeccionar equipo scope-1");
    await user.clear(input); await user.type(input, "  ");
    expect(screen.getByRole("button", { name: "Guardar corrección" })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
    await user.clear(input); await user.type(input, "  Inspeccionar y documentar  ");
    await user.click(screen.getByRole("button", { name: "Guardar corrección" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(expect.any(String), {
      decision: "CORRECTED", correction: { description: "Inspeccionar y documentar" }, note: null,
      expected_projection_fingerprint: "a".repeat(64), expected_current_review_revision: null,
    }));
  });

  it("UI07 rejection requires explicit confirmation and can be cancelled", async () => {
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Rechazar" }));
    expect(screen.getByText(/La evidencia máquina y las decisiones permanecerán/)).toBeVisible();
    expect(post).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("button", { name: "Confirmar rechazo" })).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Rechazar" }));
    await user.click(screen.getByRole("button", { name: "Confirmar rechazo" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(expect.any(String), {
      decision: "REJECTED", note: null, expected_projection_fingerprint: "a".repeat(64), expected_current_review_revision: null,
    }));
  });

  it("UI08 POST detail and queue use recalculated backend response", async () => {
    const result = confirmed(scopeItem());
    result.current!.effective_status = "CORRECTED";
    result.current!.effective_description = "Descripción recalculada por el backend";
    result.history[0].review.decision = "CORRECTED";
    result.history[0].review.correction = { description: "Descripción recalculada por el backend" };
    post.mockResolvedValueOnce({ data: result });
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Corregir" }));
    await user.click(screen.getByRole("button", { name: "Guardar corrección" }));
    expect(await screen.findByText("Decisión guardada. El estado mostrado fue recalculado por LicitIA.")).toBeVisible();
    expect(within(detailRegion()).getByText("Descripción recalculada por el backend")).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspeccionar equipo scope-1.*Corregido/ })).toBeVisible();
    expect(screen.getByText("Aplicable actualmente · Revisión actual")).toBeVisible();
  });

  it.each([
    ["UI09", "SCOPE_REVIEW_TARGET_STALE", "La información de este alcance cambió desde que la abriste."],
    ["UI10", "SCOPE_REVIEW_REVISION_CONFLICT", "Este alcance fue revisado mientras lo tenías abierto."],
  ])("%s handles 409 with refresh, clears the form and never resubmits", async (_, code, message) => {
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Corregir" }));
    await user.type(screen.getByLabelText("Nota de revisión (opcional)"), "Nota antigua");
    const refreshed = confirmed(scopeItem());
    refreshed.current_review_revision = 9;
    refreshed.current!.effective_description = "Información actualizada";
    details.set("scope-1", refreshed); queue = [refreshed];
    post.mockRejectedValueOnce(apiFailure(409, code));
    await user.click(screen.getByRole("button", { name: "Guardar corrección" }));
    expect(await screen.findByText(new RegExp(message))).toBeVisible();
    expect(await screen.findByText("Información actualizada")).toBeVisible();
    expect(get.mock.calls.filter(([url]) => url.endsWith("/scope-review"))).toHaveLength(2);
    expect(get.mock.calls.filter(([url]) => url.endsWith("/scope-1"))).toHaveLength(2);
    expect(post).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("form", { name: "Decisión humana" })).not.toBeInTheDocument();
  });

  it("UI11 a non-reviewable source cannot submit a decision", async () => {
    const item = scopeItem(); item.reviewable = false; item.not_reviewable_reason = "SOURCE_SUPERSEDED";
    item.current!.effective_status = "SOURCE_BLOCKED"; item.current!.source_blocked = true;
    item.current!.source_projection.status = "SUPERSEDED";
    seed(item);
    await open(); await loaded();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Corregir" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rechazar" })).not.toBeInTheDocument();
    expect(within(detailRegion()).getByText("Fuente bloqueada")).toBeVisible();
    expect(post).not.toHaveBeenCalled();
  });

  it("UI12 source ambiguity is explained separately from ordinary fact review", async () => {
    const item = scopeItem(); item.reviewable = false; item.not_reviewable_reason = "SOURCE_REVIEW_REQUIRED";
    item.current!.effective_status = "SOURCE_BLOCKED"; item.current!.source_blocked = true;
    item.current!.source_projection.diagnostics[0].code = "SOURCE_DOCUMENT_REVIEW_REQUIRED";
    seed(item);
    await open(); await loaded();
    expect(within(detailRegion()).getByText(/confirmar el alcance no resuelve esa ambigüedad/)).toBeVisible();
    expect(screen.getByText("La vigencia del documento fuente requiere revisión.")).toBeVisible();
  });

  it("UI13 history shows revisions, date, notes and corrections in backend order", async () => {
    const item = confirmed(scopeItem());
    const earlier = humanReview(item, 1); earlier.decision = "REJECTED";
    const current = humanReview(item, 2); current.decision = "CORRECTED"; current.correction = { description: "Descripción histórica corregida" };
    item.history = [{ review: earlier, applicable: false, reason: "HISTORICAL_REVISION" }, { review: current, applicable: true, reason: "CURRENT" }];
    seed(item);
    await open(); await loaded();
    const history = detailRegion().querySelector(".scope-review-history");
    expect(history).not.toBeNull();
    const rows = within(history as HTMLElement).getAllByRole("listitem");
    expect(within(rows[0]).getByText("Revisión 1 · Rechazado")).toBeVisible();
    expect(within(rows[1]).getByText("Revisión 2 · Corregido")).toBeVisible();
    expect(rows[0].querySelector("time")).toHaveAttribute("datetime", "2026-10-12T13:00:00Z");
    expect(within(rows[1]).getByText("Nota: Revisado con la fuente")).toBeVisible();
    expect(within(rows[1]).getByText("Descripción corregida: Descripción histórica corregida")).toBeVisible();
  });

  it("UI14 historical stale decisions retain their snapshot without carry-forward", async () => {
    const item = scopeItem(); const review = humanReview(item); review.decision = "REJECTED";
    item.current = null; item.reviewable = false; item.projection_fingerprint = null; item.current_review_revision = 1;
    item.not_reviewable_reason = "TARGET_REMOVED";
    item.history = [{ review, applicable: false, reason: "TARGET_REMOVED" }];
    seed(item);
    await open(); await loaded();
    expect(within(detailRegion()).getByText("Registro histórico")).toBeVisible();
    expect(screen.getByText(/Evidencia histórica del registro retirado/)).toBeVisible();
    expect(screen.getByText(/Histórica \/ no aplicable · Histórica: registro regenerado o retirado/)).toBeVisible();
    expect(screen.getByText("Revisión 1 · Rechazado").closest("li")).toHaveClass("scope-review-historical");
    expect(within(detailRegion()).getByText("Alcance sintético.pdf")).toBeVisible();
  });

  it("UI15 distinguishes machine-no-review-required from human-resolved", async () => {
    const item = scopeItem();
    item.current!.machine.review_required = false; item.current!.machine_review_required = false;
    item.current!.effective_status = "NOT_REQUIRED"; item.current!.accepted_execution_scope = true;
    seed(item);
    queue.push(confirmed(scopeItem("human-resolved"))); details.set("human-resolved", queue[1]);
    const user = await open(); await loaded();
    expect(within(detailRegion()).getByText("Sin revisión requerida")).toBeVisible();
    expect(screen.getByText("LicitIA no requirió revisión automática.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Inspeccionar equipo human-resolved/ }));
    expect(await screen.findByText("La decisión humana resolvió la revisión del hallazgo.")).toBeVisible();
    expect(within(detailRegion()).getByText("Confirmado")).toBeVisible();
    expect(screen.getByText("LicitIA originalmente requirió revisión.")).toBeVisible();
  });

  it("UI16 shows loading for queue and detail", async () => {
    const pending = deferred<{ data: ScopeReviewItem[] }>();
    get.mockReturnValueOnce(pending.promise);
    await open();
    expect(screen.getByText("Analizando alcance...")).toBeVisible();
    const pendingDetail = deferred<{ data: ScopeReviewItem }>();
    get.mockReturnValueOnce(pendingDetail.promise);
    await act(async () => pending.resolve({ data: queue }));
    expect(await screen.findByText("Cargando detalle de alcance...")).toBeVisible();
    await act(async () => pendingDetail.resolve({ data: queue[0] }));
    await loaded();
  });

  it("UI17 shows empty queue", async () => {
    queue = [];
    await open();
    expect(await screen.findByText("No hay elementos de alcance disponibles para revisión.")).toBeVisible();
  });

  it("UI18 network/API failure is recoverable without exposing raw exceptions", async () => {
    get.mockRejectedValueOnce(new Error("private stack trace with SQL details"));
    const user = await open();
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo cargar la revisión de alcance");
    expect(screen.queryByText(/private stack/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    await loaded();
  });

  it("UI19 pending POST prevents duplicate submit and selection", async () => {
    const pending = deferred<{ data: ScopeReviewItem }>(); post.mockReturnValueOnce(pending.promise);
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    const form = screen.getByRole("form", { name: "Decisión humana" });
    fireEvent.submit(form); fireEvent.submit(form);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Guardando decisión..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Corregir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Inspeccionar equipo scope-1/ })).toBeDisabled();
    await act(async () => pending.resolve({ data: confirmed(queue[0]) }));
    expect(await screen.findByText(/Decisión guardada/)).toBeVisible();
  });

  it("UI20 normal interface explains states in Spanish; technical codes are secondary", async () => {
    await open(); await loaded();
    expect(screen.getAllByText("Requiere revisión").length).toBeGreaterThan(0);
    expect(screen.queryByText("PENDING")).not.toBeInTheDocument();
    expect(screen.queryByText("NO_REVIEW")).not.toBeInTheDocument();
    const diagnostic = screen.getByText(/FACT_REVIEW_REQUIRED: Synthetic/);
    expect(diagnostic).not.toBeVisible();
    expect(diagnostic.closest("details")?.querySelector("summary")).toHaveTextContent("Diagnóstico técnico");
  });
});

describe("Scope Review lifecycle and recovery", () => {
  it("filters explicit backend states without reordering the queue", async () => {
    const blocked = scopeItem("blocked"); blocked.reviewable = false; blocked.not_reviewable_reason = "SOURCE_REVOKED";
    blocked.current!.effective_status = "SOURCE_BLOCKED";
    queue = [scopeItem("pending-z"), confirmed(scopeItem("reviewed")), blocked, scopeItem("pending-a")];
    details = new Map(queue.map((item) => [item.scope_detail_id, item]));
    const user = await open(); await loaded();
    const region = within(screen.getByLabelText("Cola de revisión de alcance"));
    await user.click(region.getByRole("button", { name: "Pendientes" }));
    expect(region.getByRole("button", { name: /pending-z/ })).toBeVisible();
    expect(region.getByRole("button", { name: /pending-a/ })).toBeVisible();
    expect(region.queryByRole("button", { name: /equipo reviewed/ })).not.toBeInTheDocument();
    const pendingButtons = region.getAllByRole("button").filter((button) => button.textContent?.startsWith("Inspeccionar"));
    expect(pendingButtons[0]).toHaveTextContent("pending-z"); expect(pendingButtons[1]).toHaveTextContent("pending-a");
    await user.click(region.getByRole("button", { name: "Revisados" }));
    expect(region.getByRole("button", { name: /equipo reviewed/ })).toBeVisible();
    expect(region.queryByRole("button", { name: /pending-z/ })).not.toBeInTheDocument();
    await user.click(region.getByRole("button", { name: "Bloqueados" }));
    expect(region.getByRole("button", { name: /equipo blocked/ })).toBeVisible();
    expect(region.queryByRole("button", { name: /equipo reviewed/ })).not.toBeInTheDocument();
  });

  it("ignores a late detail response after another item was selected", async () => {
    queue = [scopeItem(), scopeItem("slow"), scopeItem("newest")];
    details = new Map(queue.map((item) => [item.scope_detail_id, item]));
    const user = await open(); await loaded();
    const pending = deferred<{ data: ScopeReviewItem }>(); get.mockReturnValueOnce(pending.promise);
    await user.click(screen.getByRole("button", { name: /equipo slow/ }));
    expect(screen.getByText("Cargando detalle de alcance...")).toBeVisible();
    await user.click(screen.getByRole("button", { name: /equipo newest/ }));
    await loaded();
    await act(async () => pending.resolve({ data: queue[1] }));
    expect(within(detailRegion()).getAllByText("Inspeccionar equipo newest")[0]).toBeVisible();
    expect(within(detailRegion()).queryByText("Inspeccionar equipo slow")).not.toBeInTheDocument();
  });

  it("detail errors provide a retry and no enabled decisions", async () => {
    const user = await open(); await loaded();
    get.mockImplementationOnce(async () => ({ data: queue })).mockRejectedValueOnce(apiFailure(404));
    await user.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(await screen.findByText(/La licitación o el elemento de alcance ya no está disponible/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar detalle" }));
    await loaded();
  });

  it("a SOURCE_NOT_REVIEWABLE conflict refreshes and removes decision actions", async () => {
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    const blocked = scopeItem(); blocked.reviewable = false; blocked.not_reviewable_reason = "SOURCE_REVOKED";
    blocked.current!.effective_status = "SOURCE_BLOCKED"; blocked.current!.source_blocked = true;
    blocked.current!.source_projection.status = "REVOKED";
    seed(blocked);
    post.mockRejectedValueOnce(apiFailure(409, "SCOPE_SOURCE_NOT_REVIEWABLE"));
    await user.click(screen.getByRole("button", { name: "Guardar confirmación" }));
    expect(await screen.findByText(/La fuente ya no permite revisar este alcance/)).toBeVisible();
    expect(await within(detailRegion()).findByText(/La fuente fue revocada/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("POST failure leaves the displayed state unchanged and never auto-retries", async () => {
    post.mockRejectedValueOnce(new Error("sensitive SQL"));
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    await user.click(screen.getByRole("button", { name: "Guardar confirmación" }));
    expect(await screen.findByText(/No se pudo confirmar el guardado de la decisión/)).toBeVisible();
    await loaded();
    expect(within(detailRegion()).getByText("Sin revisión humana")).toBeVisible();
    expect(screen.queryByText(/sensitive SQL/)).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Decisión humana" })).not.toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("stale review on an existing machine row is distinct from an archived record", async () => {
    const item = scopeItem(); const review = humanReview(item); review.decision = "CORRECTED";
    review.correction = { description: "Corrección anterior" };
    item.current!.human_review_status = "STALE"; item.current!.effective_status = "STALE_REVIEW";
    item.current!.latest_review = review; item.current_review_revision = 1;
    item.history = [{ review, applicable: false, reason: "TARGET_CHANGED" }];
    seed(item);
    await open(); await loaded();
    expect(within(detailRegion()).getByText("Revisión anterior desactualizada")).toBeVisible();
    expect(screen.getByText(/Desactualizada: cambió la evidencia o la fuente/)).toBeVisible();
    expect(screen.queryByText("Registro histórico")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeEnabled();
    expect(screen.getByText("Descripción corregida: Corrección anterior")).toBeVisible();
  });

  it("closing and reopening reads persisted state again", async () => {
    const user = await open(); await loaded();
    await user.click(screen.getByRole("button", { name: "Cerrar revisión de alcance" }));
    expect(screen.queryByRole("heading", { name: "Lo que LicitIA encontró" })).not.toBeInTheDocument();
    seed(confirmed(scopeItem()));
    await user.click(screen.getByRole("button", { name: "Abrir revisión de alcance" }));
    await loaded();
    expect(within(detailRegion()).getByText("Confirmado")).toBeVisible();
    expect(screen.getByText("Revisión 1 · Confirmado")).toBeVisible();
  });

  it("a late POST from the previous tender cannot overwrite the new tender", async () => {
    const user = userEvent.setup();
    const rendered = render(<ScopeReview {...props} />);
    await user.click(screen.getByRole("button", { name: "Abrir revisión de alcance" })); await loaded();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    const pending = deferred<{ data: ScopeReviewItem }>(); post.mockReturnValueOnce(pending.promise);
    await user.click(screen.getByRole("button", { name: "Guardar confirmación" }));
    const next = scopeItem("another-tender"); next.current!.machine.tender_id = "tender-2";
    seed(next);
    rendered.rerender(<ScopeReview {...props} tenderId="tender-2" />);
    await loaded();
    await act(async () => pending.resolve({ data: confirmed(scopeItem()) }));
    expect(within(detailRegion()).getAllByText("Inspeccionar equipo another-tender")[0]).toBeVisible();
    expect(screen.queryByText(/Decisión guardada/)).not.toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("http://localhost:8000/tenders/tender-2/scope-review");
  });
});
