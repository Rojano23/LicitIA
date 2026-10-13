import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";
import { TechnicalAlternatives } from "./TechnicalAlternatives";
import { alternative, evaluation } from "../test/alternativeFixtures";
import { alternativeProps, deferred, failure, mockAlternatives } from "../test/alternativeTestHarness";

let harness: ReturnType<typeof mockAlternatives>;
beforeEach(() => { harness = mockAlternatives(); });
async function open() {
  const user = userEvent.setup(); render(<TechnicalAlternatives {...alternativeProps} />);
  await user.click(screen.getByRole("button", { name: "Abrir alternativas técnicas" }));
  return user;
}
async function loaded() { await screen.findByRole("heading", { name: "Alternativa A" }); }

it("UIA01 empty alternatives", async () => {
  harness.store.alternatives = []; await open();
  expect(await screen.findByText("No hay alternativas técnicas todavía.")).toBeVisible();
});
it("UIA02 creates a human alternative with typed fields", async () => {
  const row = alternative("alt-b");
  harness.post.mockImplementationOnce(async () => { harness.store.alternatives.push(row); return { data: row }; });
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Crear alternativa" }));
  await user.type(screen.getByLabelText("Nombre de alternativa"), "Alternativa B");
  await user.type(screen.getByLabelText("Descripción técnica"), "Propuesta humana B");
  await user.selectOptions(screen.getByLabelText("Estado de alternativa"), "ACTIVE");
  await user.click(screen.getByRole("button", { name: "Guardar alternativa" }));
  expect(await screen.findByRole("heading", { name: "Alternativa B" })).toBeVisible();
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/technical-alternatives$/), {
    name: "Alternativa B", technical_description: "Propuesta humana B", assumptions: null, notes: null, lifecycle_state: "ACTIVE",
  });
});
it("UIA03 list preserves backend order and archived rows", async () => {
  const row = alternative("alt-b"); row.current_revision.lifecycle_state = "ARCHIVED";
  harness.store.alternatives = [row, alternative()];
  await open();
  const list = within(screen.getByLabelText("Lista de alternativas técnicas"));
  await waitFor(() => expect(list.getAllByRole("button")).toHaveLength(2));
  expect(list.getAllByRole("button")[0]).toHaveTextContent("Alternativa B");
  expect(list.getByText(/Archivada/)).toBeVisible();
});
it("UIA04 selects another alternative", async () => {
  harness.store.alternatives.push(alternative("alt-b"));
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: /Alternativa B.*Revisión/ }));
  expect(await screen.findByRole("heading", { name: "Alternativa B" })).toBeVisible();
  expect(harness.get).toHaveBeenCalledWith(expect.stringMatching(/technical-alternatives\/alt-b$/));
});
it("UIA05 history shows every revision", async () => {
  const older = alternative(); const current = alternative("alt-a", 2);
  current.revisions = [older.current_revision, current.current_revision]; harness.store.alternatives = [current];
  const user = await open(); await loaded();
  await user.click(screen.getByText("Historial de revisiones de alternativa"));
  expect(screen.getByText(/Revisión 1 · Alternativa A/)).toBeVisible();
  expect(screen.getByText(/Revisión 2 · Alternativa A/)).toBeVisible();
});
it("UIA06 prefilled edit appends with server revision expectation", async () => {
  const row = alternative("alt-a", 2); row.revisions.unshift(alternative().current_revision);
  harness.post.mockResolvedValueOnce({ data: row });
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Crear nueva revisión" }));
  expect(screen.getByLabelText("Nombre de alternativa")).toHaveValue("Alternativa A");
  await user.clear(screen.getByLabelText("Descripción técnica"));
  await user.type(screen.getByLabelText("Descripción técnica"), "Estrategia revisada");
  await user.click(screen.getByRole("button", { name: "Guardar nueva revisión" }));
  await screen.findByText(/Revisión actual 2/);
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/alt-a\/revisions$/), expect.objectContaining({ expected_current_revision: 1, technical_description: "Estrategia revisada" }));
});
it("UIA07 revision conflict reloads and never resubmits", async () => {
  harness.post.mockImplementationOnce(async () => { harness.store.alternatives = [alternative("alt-a", 2)]; throw failure(409, "ALTERNATIVE_REVISION_CONFLICT"); });
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Crear nueva revisión" }));
  await user.click(screen.getByRole("button", { name: "Guardar nueva revisión" }));
  expect(await screen.findByText(/Ya existe otra revisión/)).toBeVisible();
  expect(await screen.findByText(/Revisión actual 2/)).toBeVisible();
  expect(harness.post).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: "Guardar nueva revisión" })).not.toBeInTheDocument();
});
it("UIA08 archive needs explicit confirmation and appends content", async () => {
  const row = alternative("alt-a", 2); row.current_revision.lifecycle_state = "ARCHIVED"; row.revisions.unshift(alternative().current_revision);
  harness.post.mockResolvedValueOnce({ data: row });
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Archivar alternativa" }));
  expect(harness.post).not.toHaveBeenCalled();
  expect(screen.getByText(/Archivar conserva la alternativa/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Confirmar archivo" }));
  expect(await screen.findByText(/Revisión actual 2 · Archivada/)).toBeVisible();
  expect(harness.post).toHaveBeenCalledWith(expect.stringMatching(/revisions$/), expect.objectContaining({ lifecycle_state: "ARCHIVED", expected_current_revision: 1, technical_description: "Estrategia técnica alt-a" }));
});
it("UIA09 archived alternative and evaluation history remain", async () => {
  harness.store.alternatives[0].current_revision.lifecycle_state = "ARCHIVED";
  harness.store.evaluations["alt-a"] = [{ ...evaluation(), applicability: "STALE_ALTERNATIVE", overall_status: "STALE" }];
  await open(); await loaded();
  expect(await screen.findByText("Evaluación histórica desactualizada")).toBeVisible();
  expect(within(screen.getByLabelText("Lista de alternativas técnicas")).getByText(/Archivada/)).toBeVisible();
});
it("UIA10 archived alternative cannot start an evaluation", async () => {
  harness.store.alternatives[0].current_revision.lifecycle_state = "ARCHIVED";
  await open(); await loaded();
  expect(await screen.findByText(/La alternativa está archivada/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Crear nueva evaluación" })).not.toBeInTheDocument();
  expect(harness.post).not.toHaveBeenCalled();
});
it("cancel archive performs no write", async () => {
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Archivar alternativa" }));
  await user.click(screen.getByRole("button", { name: "Cancelar archivo" }));
  expect(harness.post).not.toHaveBeenCalled();
});
it("late detail from an old selection cannot replace new selection", async () => {
  const pending = deferred<{ data: ReturnType<typeof alternative> }>();
  harness.store.alternatives.push(alternative("alt-b"));
  const original = harness.get.getMockImplementation()!;
  harness.get.mockImplementation((url: string) => url.endsWith("/alt-a") ? pending.promise : original(url));
  const user = await open();
  await user.click(await screen.findByRole("button", { name: /Alternativa B.*Revisión/ }));
  await screen.findByRole("heading", { name: "Alternativa B" });
  await act(async () => pending.resolve({ data: alternative() }));
  expect(screen.queryByRole("heading", { name: "Alternativa A" })).not.toBeInTheDocument();
});
it("creation prevents duplicate submit and disables selection", async () => {
  const pending = deferred<{ data: ReturnType<typeof alternative> }>(); harness.post.mockReturnValueOnce(pending.promise);
  const user = await open(); await loaded();
  await user.click(screen.getByRole("button", { name: "Crear alternativa" }));
  await user.type(screen.getByLabelText("Nombre de alternativa"), "Nueva");
  await user.type(screen.getByLabelText("Descripción técnica"), "Plan humano");
  const form = screen.getByRole("form", { name: "Crear alternativa técnica" });
  fireEvent.submit(form); fireEvent.submit(form);
  expect(harness.post).toHaveBeenCalledTimes(1);
  expect(within(screen.getByLabelText("Lista de alternativas técnicas")).getByRole("button")).toBeDisabled();
  await act(async () => pending.resolve({ data: alternative("alt-b") }));
});
