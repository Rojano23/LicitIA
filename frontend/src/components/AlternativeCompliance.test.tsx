import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";
import { TechnicalAlternatives } from "./TechnicalAlternatives";
import { alternative, assessed, evaluation, judgment } from "../test/alternativeFixtures";
import { alternativeProps, deferred, failure, mockAlternatives } from "../test/alternativeTestHarness";
import type { ComplianceEvaluation, ComplianceStatus } from "../api/alternativeCompliance";

let harness: ReturnType<typeof mockAlternatives>;
beforeEach(() => { harness = mockAlternatives(); });
async function open() {
  const user = userEvent.setup(); render(<TechnicalAlternatives {...alternativeProps} />);
  await user.click(screen.getByRole("button", { name: "Abrir alternativas técnicas" }));
  return user;
}
async function loaded() { await screen.findByLabelText("Detalle de evaluación"); }
function obligation() { return within(screen.getByRole("article", { name: "Inspeccionar equipo scope-1" })); }
async function prepare(user: ReturnType<typeof userEvent.setup>, status = "COMPLIANT") {
  const item = obligation();
  await user.selectOptions(item.getByLabelText("Decisión de cumplimiento"), status);
  await user.type(item.getByLabelText("Justificación técnica"), "Evaluación humana explícita");
  await user.type(item.getByLabelText("Evidencia / referencia (opcional)"), "Documento técnico humano");
}
function seed(row: ComplianceEvaluation) { harness.store.evaluations["alt-a"] = [row]; }

it("UIC01 creates evaluation with exact backend expectations", async () => {
  harness.store.evaluations["alt-a"] = [];
  harness.post.mockImplementationOnce(async () => { const row = evaluation(); seed(row); return { data: row }; });
  const user = await open();
  await screen.findByText("Esta alternativa aún no tiene una evaluación de cumplimiento.");
  await user.click(screen.getByRole("button", { name: "Crear nueva evaluación" }));
  await loaded();
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/alt-a\/compliance$/), {
    expected_alternative_revision: 1, expected_alternative_fingerprint: "a".repeat(64), expected_scope_snapshot_fingerprint: "c".repeat(64),
  });
});
it("UIC02 frozen contractual description is separate from judgment", async () => {
  await open(); await loaded();
  expect(obligation().getByRole("heading", { name: "Lo que exige la licitación" })).toBeVisible();
  expect(obligation().getByRole("heading", { name: "Juicio técnico sobre esta alternativa" })).toBeVisible();
});
it("UIC03 frozen provenance document/version/page/locator/excerpt", async () => {
  await open(); await loaded();
  const region = obligation();
  expect(region.getByText("Alcance sintético.pdf")).toBeVisible();
  expect(region.getByText("3")).toBeVisible(); expect(region.getByText("7")).toBeVisible();
  expect(region.getByText("numeral 4.2")).toBeVisible();
  expect(region.getByText("Se deberá inspeccionar el equipo de control.")).toBeVisible();
  expect(region.getByRole("link", { name: "Abrir documento fuente" })).toHaveAttribute("href", expect.stringMatching(/document-1\/content#page=7$/));
  expect(region.getByText("Sin revisión humana")).toBeVisible();
});
it("UIC04 defaults display without automatically selecting a judgment", async () => {
  await open(); await loaded();
  expect(obligation().getByText("Sin evaluar")).toBeVisible();
  expect(obligation().getByLabelText("Decisión de cumplimiento")).toHaveValue("");
  expect(obligation().queryByRole("option", { name: "Sin evaluar" })).not.toBeInTheDocument();
  expect(harness.post).not.toHaveBeenCalled();
});
it.each([
  ["UIC05", "COMPLIANT", "Cumple"], ["UIC06", "PARTIAL", "Cumplimiento parcial"],
  ["UIC07", "NON_COMPLIANT", "No cumple"], ["UIC08", "REVIEW_REQUIRED", "Requiere revisión"],
] as const)("%s appends %s using human rationale and backend response", async (_id, status, label) => {
  const response = assessed(status); harness.post.mockResolvedValueOnce({ data: response });
  const user = await open(); await loaded(); await prepare(user, status);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  await waitFor(() => expect(obligation().getByText(label, { selector: "strong" })).toBeVisible());
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/eval-1\/items\/scope-1\/decisions$/), {
    status, rationale: "Evaluación humana explícita", evidence_note: "Documento técnico humano", expected_current_decision_revision: null,
  });
  expect(obligation().getByText("Justificación: Justificación histórica 1")).toBeVisible();
});
it("UIC09 requires non-empty rationale", async () => {
  const user = await open(); await loaded();
  await user.selectOptions(obligation().getByLabelText("Decisión de cumplimiento"), "COMPLIANT");
  await user.type(obligation().getByLabelText("Justificación técnica"), "   ");
  expect(obligation().getByRole("button", { name: "Guardar juicio técnico" })).toBeDisabled();
  fireEvent.submit(obligation().getByRole("form"));
  expect(harness.post).not.toHaveBeenCalled();
});
it("UIC10 all previous partial/noncompliant decisions remain visible", async () => {
  const row = assessed("COMPLIANT");
  const last = judgment("COMPLIANT", 3);
  row.items[0] = { ...row.items[0], latest_decision: last, decisions: [judgment("NON_COMPLIANT"), judgment("PARTIAL", 2), last] };
  seed(row); const user = await open(); await loaded();
  await user.click(obligation().getByText("Historial de decisiones técnicas"));
  expect(obligation().getByText("Revisión 1 · No cumple")).toBeVisible();
  expect(obligation().getByText("Revisión 2 · Cumplimiento parcial")).toBeVisible();
  expect(obligation().getByText("Revisión 3 · Cumple")).toBeVisible();
  expect(obligation().getByText("Referencia histórica 2", { exact: false })).toBeVisible();
});
it("UIC11 summary and counts are server values even when fixture items differ", async () => {
  const row = evaluation(); row.overall_status = "PARTIAL"; row.counts.PARTIAL = 9; row.counts.COMPLIANT = 4;
  seed(row); await open(); await loaded();
  expect(screen.getByRole("heading", { name: "Cumplimiento parcial" })).toBeVisible();
  const counts = within(screen.getByLabelText("Conteos de evaluación"));
  expect(counts.getByText("9")).toBeVisible(); expect(counts.getByText("4")).toBeVisible();
  expect(obligation().getByText("Sin evaluar")).toBeVisible();
});
it.each([
  ["UIC12", "STALE_ALTERNATIVE", "La alternativa cambió después de esta evaluación."],
  ["UIC13", "STALE_SCOPE", "El alcance contractual cambió después de esta evaluación."],
  ["UIC14", "STALE_BOTH", "La alternativa y el alcance cambiaron después de esta evaluación."],
] as const)("%s shows %s with historical aggregate clearly qualified", async (_id, applicability, explanation) => {
  seed({ ...assessed("COMPLIANT"), applicability, overall_status: "STALE" });
  await open(); await loaded();
  expect(screen.getByText(explanation)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Evaluación desactualizada" })).toBeVisible();
  expect(screen.getByText("Resultado histórico: Cumple.")).toBeVisible();
});
it("UIC15 stale evaluation disables all new decisions", async () => {
  seed({ ...evaluation(), applicability: "STALE_SCOPE", overall_status: "STALE" });
  await open(); await loaded();
  expect(obligation().getByLabelText("Decisión de cumplimiento")).toBeDisabled();
  expect(obligation().getByRole("button", { name: "Guardar juicio técnico" })).toBeDisabled();
  fireEvent.submit(obligation().getByRole("form")); expect(harness.post).not.toHaveBeenCalled();
});
it("UIC16 new evaluation uses new snapshot and preserves old evaluation", async () => {
  seed({ ...evaluation(), applicability: "STALE_SCOPE", overall_status: "STALE" });
  harness.store.scope.fingerprint = "d".repeat(64);
  const fresh = evaluation("eval-2"); fresh.scope_snapshot.fingerprint = "d".repeat(64);
  harness.post.mockImplementationOnce(async () => { harness.store.evaluations["alt-a"].push(fresh); return { data: fresh }; });
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Crear nueva evaluación" }));
  await waitFor(() => expect(screen.getByRole("heading", { name: "Sin evaluar" })).toBeVisible());
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/alt-a\/compliance$/), expect.objectContaining({ expected_scope_snapshot_fingerprint: "d".repeat(64) }));
  expect(screen.getByRole("button", { name: /Revisión evaluada 1.*Alcance contractual modificado/ })).toBeVisible();
});
it("UIC17 unresolved contractual context remains prominent", async () => {
  const row = evaluation(); row.scope_snapshot.unresolved = true; row.overall_status = "REVIEW_REQUIRED";
  row.items[0].snapshot = { ...row.items[0].snapshot, unresolved: true, accepted_execution_scope: false, effective_status: "SOURCE_BLOCKED" };
  seed(row); await open(); await loaded();
  expect(screen.getByText("Ambigüedad contractual pendiente")).toBeVisible();
  expect(obligation().getByText("Fuente bloqueada")).toBeVisible();
  expect(screen.getByText(/El cumplimiento de una alternativa no resuelve ambigüedades/)).toBeVisible();
  expect(screen.queryByRole("button", { name: /Source Effect/ })).not.toBeInTheDocument();
});
it("UIC18 decision revision conflict reloads history without resubmission", async () => {
  harness.post.mockImplementationOnce(async () => { seed(assessed("PARTIAL")); throw failure(409, "COMPLIANCE_DECISION_REVISION_CONFLICT"); });
  const user = await open(); await loaded(); await prepare(user);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  expect(await screen.findByText(/Esta obligación fue evaluada en otra sesión/)).toBeVisible();
  await screen.findByRole("heading", { name: "Cumplimiento parcial" });
  expect(obligation().getByText("Justificación: Justificación histórica 1")).toBeVisible();
  expect(harness.post).toHaveBeenCalledTimes(1);
});
it("UIC19 scope snapshot conflict refreshes expectations without automatic POST", async () => {
  harness.store.evaluations["alt-a"] = [];
  harness.post.mockImplementationOnce(async () => { harness.store.scope = { ...harness.store.scope, fingerprint: "e".repeat(64) }; throw failure(409, "SCOPE_SNAPSHOT_STALE"); });
  const user = await open(); await screen.findByText("Esta alternativa aún no tiene una evaluación de cumplimiento.");
  await user.click(screen.getByRole("button", { name: "Crear nueva evaluación" }));
  expect(await screen.findByText(/El alcance contractual cambió. Se actualizará/)).toBeVisible();
  await waitFor(() => expect(screen.getByRole("button", { name: "Crear nueva evaluación" })).toBeEnabled());
  expect(harness.post).toHaveBeenCalledTimes(1);
  harness.post.mockImplementationOnce(async () => { const row = evaluation(); seed(row); return { data: row }; });
  await user.click(screen.getByRole("button", { name: "Crear nueva evaluación" }));
  expect(harness.post).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({ expected_scope_snapshot_fingerprint: "e".repeat(64) }));
});
it("UIC20 switching alternatives never copies compliance decisions", async () => {
  harness.store.alternatives.push(alternative("alt-b")); seed(assessed("NON_COMPLIANT"));
  harness.store.evaluations["alt-b"] = [evaluation("eval-b", "alt-b")];
  const user = await open(); await loaded(); expect(obligation().getByText("No cumple", { selector: "strong" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Alternativa B.*Revisión/ })); await loaded();
  expect(obligation().getByText("Sin evaluar")).toBeVisible();
  expect(obligation().queryByText(/Justificación histórica/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Alternativa A.*Revisión/ })); await loaded();
  expect(obligation().getByText("No cumple", { selector: "strong" })).toBeVisible(); expect(harness.post).not.toHaveBeenCalled();
});
it("UIC21 no automatic ranking/recommendation/winner", async () => {
  await open(); await loaded();
  expect(screen.queryByText(/mejor alternativa|ganadora|recomendada|puntaje|porcentaje/i)).not.toBeInTheDocument();
  expect(harness.post).not.toHaveBeenCalled();
});
it("UIC22 explicit loading states", async () => {
  const pending = deferred<{ data: ComplianceEvaluation[] }>();
  const original = harness.get.getMockImplementation()!;
  harness.get.mockImplementation((url: string) => url.endsWith("/compliance") ? pending.promise : original(url));
  await open(); expect(await screen.findByText("Cargando evaluación...")).toBeVisible();
  await act(async () => pending.resolve({ data: [evaluation()] })); await loaded();
});
it("UIC23 recoverable error retries only reads", async () => {
  const original = harness.get.getMockImplementation()!; let failed = false;
  harness.get.mockImplementation(async (url: string) => {
    if (url.endsWith("/compliance") && !failed) { failed = true; throw new Error("SECRET server trace"); }
    return original(url);
  });
  const user = await open(); expect(await screen.findByText("No se pudieron cargar las evaluaciones.")).toBeVisible();
  expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Reintentar evaluaciones" })); await loaded();
  expect(harness.post).not.toHaveBeenCalled();
});
it("UIC24 duplicate submit prevented while controls disabled", async () => {
  const pending = deferred<{ data: ComplianceEvaluation }>(); harness.post.mockReturnValueOnce(pending.promise);
  const user = await open(); await loaded(); await prepare(user);
  const form = obligation().getByRole("form"); fireEvent.submit(form); fireEvent.submit(form);
  expect(harness.post).toHaveBeenCalledTimes(1);
  expect(obligation().getByLabelText("Decisión de cumplimiento")).toBeDisabled();
  await act(async () => pending.resolve({ data: assessed("COMPLIANT") }));
});
it("UIC25 business UI translates backend enums", async () => {
  const row = assessed("REVIEW_REQUIRED"); row.items[0].snapshot.effective_status = "CORRECTED"; row.items[0].snapshot.human_review_status = "CURRENT";
  seed(row); await open(); await loaded();
  expect(screen.queryByText(/COMPLIANT|REVIEW_REQUIRED|NOT_EVALUATED|STALE_SCOPE|CORRECTED|DRAFT/)).not.toBeInTheDocument();
  expect(obligation().getByText("Alcance corregido")).toBeVisible();
  expect(obligation().getByText("Revisión humana vigente")).toBeVisible();
});
it.each([
  ["ALTERNATIVE_FINGERPRINT_STALE", /La alternativa cambió/],
  ["COMPLIANCE_EVALUATION_STALE", /La evaluación ya no está vigente/],
  ["ALTERNATIVE_ARCHIVED", /La alternativa está archivada y no puede/],
] as const)("explicit %s conflict message and no automatic retry", async (code, message) => {
  harness.post.mockRejectedValueOnce(failure(409, code));
  const user = await open(); await loaded(); await prepare(user);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  expect(await screen.findByText(message)).toBeVisible(); expect(harness.post).toHaveBeenCalledTimes(1);
});
it("existing decision revision is sent verbatim from latest backend decision", async () => {
  const row = assessed("PARTIAL"); row.items[0].latest_decision = judgment("PARTIAL", 7); seed(row);
  harness.post.mockResolvedValueOnce({ data: assessed("COMPLIANT") });
  const user = await open(); await loaded(); await prepare(user);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  expect(harness.post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ expected_current_decision_revision: 7 }));
});
it("lost POST response refreshes audit without silently retrying", async () => {
  harness.post.mockImplementationOnce(async () => { seed(assessed("COMPLIANT")); throw new Error("Lost response"); });
  const user = await open(); await loaded(); await prepare(user);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  expect(await screen.findByText(/No se pudo confirmar el guardado/)).toBeVisible();
  await screen.findByRole("heading", { name: "Cumple" });
  expect(harness.post).toHaveBeenCalledTimes(1);
});

it("scope read failure preserves evaluation history but blocks new snapshot creation", async () => {
  const original = harness.get.getMockImplementation()!;
  harness.get.mockImplementation(async (url: string) => {
    if (url.endsWith("/alternative-scope-snapshot")) throw new Error("Unreachable local service");
    return original(url);
  });
  await open(); await loaded();
  expect(screen.getByText("No se pudo cargar el alcance contractual vigente.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Crear nueva evaluación" })).toBeDisabled();
  expect(screen.getByText("Historial de evaluaciones")).toBeVisible();
});
it("late evaluation from another alternative cannot leak into the selection", async () => {
  harness.store.alternatives.push(alternative("alt-b"));
  harness.store.evaluations["alt-b"] = [evaluation("eval-b", "alt-b")];
  const pending = deferred<{ data: ComplianceEvaluation }>();
  const original = harness.get.getMockImplementation()!;
  harness.get.mockImplementation((url: string) => url.endsWith("/alt-a/compliance/eval-1") ? pending.promise : original(url));
  const user = await open(); await screen.findByText("Cargando detalle de evaluación...");
  await user.click(screen.getByRole("button", { name: /Alternativa B.*Revisión/ })); await loaded();
  await act(async () => pending.resolve({ data: assessed("NON_COMPLIANT") }));
  expect(screen.getByRole("heading", { name: "Sin evaluar" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "No cumple" })).not.toBeInTheDocument();
});
it("changing tender ignores a late mutation response and resets all state", async () => {
  const pending = deferred<{ data: ComplianceEvaluation }>(); harness.post.mockReturnValueOnce(pending.promise);
  const user = userEvent.setup();
  const view = render(<TechnicalAlternatives {...alternativeProps} />);
  await user.click(screen.getByRole("button", { name: "Abrir alternativas técnicas" }));
  await loaded(); await prepare(user);
  await user.click(obligation().getByRole("button", { name: "Guardar juicio técnico" }));
  harness.store.alternatives = [];
  view.rerender(<TechnicalAlternatives {...alternativeProps} tenderId="tender-2" />);
  await screen.findByText("No hay alternativas técnicas todavía.");
  await act(async () => pending.resolve({ data: assessed("COMPLIANT") }));
  expect(screen.queryByLabelText("Detalle de evaluación")).not.toBeInTheDocument();
  expect(screen.queryByText("Guardado confirmado por el servidor local.")).not.toBeInTheDocument();
});

it("revision change clears old current compliance until backend applicability reloads", async () => {
  const old = assessed("COMPLIANT"); seed(old);
  const pending = deferred<{ data: ComplianceEvaluation[] }>();
  const original = harness.get.getMockImplementation()!; let reads = 0;
  harness.get.mockImplementation((url: string) => {
    if (url.endsWith("/alt-a/compliance") && ++reads > 1) return pending.promise;
    return original(url);
  });
  const revised = alternative("alt-a", 2); revised.revisions.unshift(alternative().current_revision);
  const stale: ComplianceEvaluation = { ...old, applicability: "STALE_ALTERNATIVE", overall_status: "STALE" };
  harness.post.mockImplementationOnce(async () => {
    harness.store.alternatives = [revised]; seed(stale); return { data: revised };
  });
  const user = await open(); await loaded();
  expect(screen.getByRole("heading", { name: "Cumple" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Crear nueva revisión" }));
  await user.click(screen.getByRole("button", { name: "Guardar nueva revisión" }));
  await screen.findByText("Cargando evaluación...");
  expect(screen.queryByRole("heading", { name: "Cumple" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Guardar juicio técnico" })).not.toBeInTheDocument();
  await act(async () => pending.resolve({ data: [stale] }));
  expect(await screen.findByRole("heading", { name: "Evaluación desactualizada" })).toBeVisible();
  expect(obligation().getByLabelText("Decisión de cumplimiento")).toBeDisabled();
});
