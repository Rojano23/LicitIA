import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { CommercialMatrix } from "./CommercialMatrix";
import { matrixApi, type MatrixRead, type MatrixRow, type BulkRead } from "../api/commercialMatrix";
vi.mock("../api/commercialMatrix", async original => ({...await original<typeof import("../api/commercialMatrix")>(), matrixApi:{read:vi.fn(),bulk:vi.fn()}}));
function row(id: string, currency: "MXN" | "USD"): MatrixRow {
  return {scope_id:id,item_reference:id,description:`Equipo ${id}`,commercial_line_id:`line${id}`,revision:1,source_fingerprint:"f".repeat(64),initialized:true,
    inputs:{cost_source_type:"INTERNAL_COST",cost_value_origin:"MANUAL_INPUT",currency,unit_cost:"100",offered_unit_price:"90",calculation_mode:"COST_FIRST",calculation_basis:"MARKUP",markup_percent:"25",target_margin_percent:null,reference_party_name:null,reference_party_reference:null,reference_party_note:null,quote_document_id:null,quote_reference:null,quantity_id:null,notes:null,input_origin:"UI",actor_label:null},
    source:{scope:null,quantities:[],selected_quantity_id:null},summary:{recommended_unit_price:"125",total_cost:"200",offered_total:"180",profit:"-20",actual_markup_percent:"-10",actual_margin_percent:"-11.11111111",currency,status:"REVIEW_REQUIRED",warnings:["PRICE_BELOW_COST"]},
    price_method:"MANUAL",price_value_origin:"MANUAL_INPUT",manual_price_protected:true,commercial_complete:true,warning_count:1,offered_price_status:"MANUAL",unresolved_cost:false};
}
const data: MatrixRead = {tender_id:"t",rows:[row("31","MXN"),row("32","USD")],summary_by_currency:[],archived_lines:[]};
const props={apiUrl:"http://local",tenderId:"t"};
beforeEach(() => {
  vi.clearAllMocks(); vi.mocked(matrixApi.read).mockResolvedValue(data);
  vi.mocked(matrixApi.bulk).mockImplementation(async (_base,_tender,payload):Promise<BulkRead> => ({operation_id:"operation",applied:payload.apply,counts:{[payload.apply ? "UPDATED":"ELIGIBLE"]:payload.targets.length},outcomes:payload.targets.map(t => ({scope_id:t.scope_id,outcome:payload.apply ? "UPDATED":"ELIGIBLE",reasons:[],price_outcome:"PROTECTED",warnings:["MANUAL_PRICE_PROTECTED"]}))}));
});
async function open() {render(<CommercialMatrix {...props}/>);fireEvent.click(screen.getByText("Abrir matriz comercial"));await screen.findByText("Equipo 31");}
it("M7B21 renders all rows lazily without writes",async () => {
  render(<CommercialMatrix {...props}/>);expect(matrixApi.read).not.toHaveBeenCalled();fireEvent.click(screen.getByText("Abrir matriz comercial"));
  expect(await screen.findByText("Equipo 31")).toBeInTheDocument();expect(screen.getByText("Equipo 32")).toBeInTheDocument();
  expect(screen.getAllByText("PRICE_BELOW_COST")).toHaveLength(2);expect(matrixApi.bulk).not.toHaveBeenCalled();
});
it("M7B22 selection includes only visible filtered rows",async () => {
  await open();fireEvent.click(screen.getByText("Seleccionar visibles"));
  fireEvent.change(screen.getByLabelText("Filtrar moneda"),{target:{value:"USD"}});
  fireEvent.click(screen.getByText("Previsualizar lote"));await screen.findByText(/Vista previa:/);
  const payload=vi.mocked(matrixApi.bulk).mock.calls[0][2];expect(payload.targets.map(t => t.scope_id)).toEqual(["32"]);expect(payload.apply).toBe(false);
  expect(screen.queryByText("Equipo 31")).not.toBeInTheDocument();
});
it("distinct inline drafts travel together as decimal strings",async () => {
  await open();fireEvent.change(screen.getByLabelText("Costo 31"),{target:{value:"0.10"}});fireEvent.change(screen.getByLabelText("Costo 32"),{target:{value:"200.25"}});
  fireEvent.click(screen.getByText("Seleccionar visibles"));fireEvent.change(screen.getByLabelText("Acción"),{target:{value:"MARKUP"}});fireEvent.change(screen.getByLabelText("Porcentaje del lote"),{target:{value:"25"}});
  fireEvent.click(screen.getByText("Previsualizar lote"));await screen.findByText(/Vista previa:/);
  const payload=vi.mocked(matrixApi.bulk).mock.calls[0][2];expect(payload.row_changes).toEqual({"31":{unit_cost:"0.10"},"32":{unit_cost:"200.25"}});expect(payload.changes).toEqual({markup_percent:"25"});
});
it("M7B23 reports protected prices and per-row failures",async () => {
  vi.mocked(matrixApi.bulk).mockResolvedValue({operation_id:"operation",applied:false,counts:{ELIGIBLE:1,STALE:1},outcomes:[{scope_id:"31",outcome:"ELIGIBLE",reasons:["MANUAL_PRICE_PROTECTED"],price_outcome:"PROTECTED"},{scope_id:"32",outcome:"STALE",reasons:["COMMERCIAL_CONTEXT_STALE"],price_outcome:"NOT_REQUESTED"}]});
  await open();fireEvent.click(screen.getByText("Seleccionar visibles"));fireEvent.click(screen.getByText("Previsualizar lote"));
  expect(await screen.findByText(/COMMERCIAL_CONTEXT_STALE/)).toBeInTheDocument();expect(screen.getByText(/31: ELIGIBLE/)).toHaveTextContent("MANUAL_PRICE_PROTECTED");
});
it("requires explicit apply and confirmation for manual replacement",async () => {
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);
  await open();fireEvent.click(screen.getByText("Seleccionar visibles"));fireEvent.click(screen.getByLabelText("Reemplazar también precios manuales"));
  fireEvent.click(screen.getByText("Previsualizar lote"));fireEvent.click(await screen.findByText("Aplicar vista previa"));
  expect(confirm).toHaveBeenCalled();expect(matrixApi.bulk).toHaveBeenCalledTimes(1);
  confirm.mockReturnValue(true);fireEvent.click(screen.getByText("Aplicar vista previa"));await screen.findByText(/Lote aplicado:/);
  expect(vi.mocked(matrixApi.bulk).mock.calls[1][2]).toMatchObject({apply:true,replace_manual_price:true,operation_id:"operation"});confirm.mockRestore();
});
it("defaults and copy settings do not send monetary decisions",async () => {
  await open();fireEvent.change(screen.getByLabelText("Moneda inicial"),{target:{value:"EUR"}});fireEvent.click(screen.getByLabelText("Seleccionar 32"));
  fireEvent.change(screen.getByLabelText("Acción"),{target:{value:"COPY_SETTINGS"}});fireEvent.change(screen.getByLabelText("Copiar ajustes desde"),{target:{value:"31"}});fireEvent.click(screen.getByText("Previsualizar lote"));await screen.findByText(/Vista previa:/);
  const payload=vi.mocked(matrixApi.bulk).mock.calls[0][2];expect(payload.defaults.currency).toBe("EUR");expect(payload.changes).toEqual({});expect(payload.copy_from?.scope_id).toBe("31");expect(payload.row_changes).toEqual({});
});
it("Enter previews a single edited row without applying it",async () => {
  await open();const input=screen.getByLabelText("Costo 31");fireEvent.change(input,{target:{value:"125.01"}});fireEvent.keyDown(input,{key:"Enter"});
  await waitFor(() => expect(matrixApi.bulk).toHaveBeenCalled());const payload=vi.mocked(matrixApi.bulk).mock.calls[0][2];expect(payload.targets.map(t => t.scope_id)).toEqual(["31"]);expect(payload.apply).toBe(false);
});
it("changing a preview setting invalidates the previous apply action",async () => {
  await open();fireEvent.click(screen.getByText("Seleccionar visibles"));fireEvent.click(screen.getByText("Previsualizar lote"));await screen.findByText("Aplicar vista previa");
  fireEvent.change(screen.getByLabelText("Moneda inicial"),{target:{value:"USD"}});expect(screen.queryByText("Aplicar vista previa")).not.toBeInTheDocument();
});
it("applying a selected row preserves unselected monetary drafts",async () => {
  await open();fireEvent.change(screen.getByLabelText("Costo 31"),{target:{value:"0.10"}});fireEvent.change(screen.getByLabelText("Costo 32"),{target:{value:"200.25"}});
  fireEvent.click(screen.getByLabelText("Seleccionar 32"));fireEvent.click(screen.getByText("Previsualizar lote"));
  fireEvent.click(await screen.findByText("Aplicar vista previa"));await screen.findByText(/Lote aplicado:/);
  expect(screen.getByLabelText("Costo 31")).toHaveValue("0.10");
  expect(vi.mocked(matrixApi.bulk).mock.calls[1][2].row_changes).toEqual({"32":{unit_cost:"200.25"}});
});
it("M7D shows canonical completeness and separates blockers from warnings",async()=>{
  const ready=row("31","MXN");ready.summary.status="READY";ready.summary.readiness={status:"READY",proposal_eligible:true,reasons:[{code:"PRICE_BELOW_COST",severity:"WARNING"}],warnings:["PRICE_BELOW_COST"]};
  const missing=row("32","USD");missing.summary.status="INCOMPLETE";missing.summary.readiness={status:"INCOMPLETE",proposal_eligible:false,reasons:[{code:"MISSING_OFFERED_PRICE",severity:"BLOCKER"}],warnings:[]};
  vi.mocked(matrixApi.read).mockResolvedValue({...data,rows:[ready,missing],commercial_readiness:{status:"INCOMPLETE",total_scope_items:2,ready_count:1,incomplete_count:1,review_required_count:0,warning_count:1,missing_commercial_treatment_count:0}});
  await open();expect(screen.getByLabelText("Completitud comercial")).toHaveTextContent("1 READY · 1 INCOMPLETE · 0 REVIEW_REQUIRED");expect(screen.getByText("WARNING: PRICE_BELOW_COST")).toBeInTheDocument();expect(screen.getByText("BLOCKER: MISSING_OFFERED_PRICE")).toBeInTheDocument();
});
