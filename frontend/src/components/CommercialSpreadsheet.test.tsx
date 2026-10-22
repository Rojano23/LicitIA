import { render,screen,fireEvent,waitFor } from "@testing-library/react";
import { beforeEach,expect,it,vi } from "vitest";
import { CommercialSpreadsheet } from "./CommercialSpreadsheet";
import { exchangeApi,type ImportPreview } from "../api/commercialExchange";
vi.mock("../api/commercialExchange",()=>({exchangeApi:{export:vi.fn(),stage:vi.fn(),apply:vi.fn()}}));
const preview: ImportPreview={stage_id:"stage",export_id:"export",tender_id:"t",origin:"XLSX_IMPORT",applied:false,counts:{CHANGED:1,INVALID:1},file_evidence:{sha256:"f".repeat(64),file_name:"precios.xlsx",format:"xlsx",export_id:"export",stage_id:"stage"},rows:[
  {scope_id:"s",item_reference:"31",import_row:1,state:"CHANGED",eligible:true,warnings:["MANUAL_PRICE_PROTECTED"],errors:[],diff:[{field:"unit_cost",current:"100",imported:"120",proposed:"120"}]},
  {scope_id:"bad",import_row:2,state:"INVALID",eligible:false,warnings:[],errors:["REFERENCE_FIELDS_MODIFIED"],diff:[],reference_diff:[{field:"quantity",current:"2",imported:"999"}]}]};
const props={apiUrl:"http://local",tenderId:"t",disabled:false,onBusyChange:vi.fn(),onApplied:vi.fn(async()=>{})};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(exchangeApi.stage).mockResolvedValue(preview);vi.mocked(exchangeApi.apply).mockResolvedValue({stage_id:"stage",applied:true,counts:{UPDATED:1},outcomes:[{scope_id:"s",outcome:"UPDATED",reasons:[]}]});});
async function inspect(){render(<CommercialSpreadsheet {...props}/>);fireEvent.change(screen.getByLabelText("Importar archivo comercial"),{target:{files:[new File(["xlsx"],"precios.xlsx")]}});fireEvent.click(screen.getByText("Previsualizar importación"));await screen.findByText(/XLSX_IMPORT:/);}
it("uploads to preview only and shows field diffs and source tamper",async()=>{
  await inspect();expect(exchangeApi.apply).not.toHaveBeenCalled();expect(screen.getByText("unit_cost")).toBeInTheDocument();expect(screen.getByText(/Referencia alterada quantity/)).toHaveTextContent("999");expect(screen.getByText("MANUAL_PRICE_PROTECTED")).toBeInTheDocument();
});
it("requires confirmation then refreshes canonical matrix via callback",async()=>{
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);await inspect();fireEvent.click(screen.getByText("Aplicar cambios comerciales validados"));expect(exchangeApi.apply).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);fireEvent.click(screen.getByText("Aplicar cambios comerciales validados"));await screen.findByText(/Importación aplicada:/);
  expect(exchangeApi.apply).toHaveBeenCalledWith("http://local","t","stage");expect(props.onApplied).toHaveBeenCalledOnce();confirm.mockRestore();
});
it("changing import flags invalidates frozen preview",async()=>{
  await inspect();fireEvent.click(screen.getByLabelText("Confirmar cambio de moneda sin conversión FX"));expect(screen.queryByText("Aplicar cambios comerciales validados")).not.toBeInTheDocument();
});
it("rejects unsupported file without applying",async()=>{
  render(<CommercialSpreadsheet {...props}/>);fireEvent.change(screen.getByLabelText("Importar archivo comercial"),{target:{files:[new File(["macro"],"x.xlsm")]}});fireEvent.click(screen.getByText("Previsualizar importación"));
  expect(await screen.findByRole("alert")).toHaveTextContent("XLSX o CSV");expect(exchangeApi.stage).not.toHaveBeenCalled();
});
it("does not enable apply for invalid-only preview",async()=>{
  vi.mocked(exchangeApi.stage).mockResolvedValue({...preview,rows:[preview.rows[1]]});await inspect();expect(screen.getByText("Aplicar cambios comerciales validados")).toBeDisabled();
});
it("disables exchange while parent has unsaved drafts",()=>{
  render(<CommercialSpreadsheet {...props} disabled/>);expect(screen.getByText("Exportar XLSX")).toBeDisabled();expect(screen.getByText("Exportar CSV")).toBeDisabled();expect(exchangeApi.export).not.toHaveBeenCalled();
});
it("downloads locally using the export API",async()=>{
  vi.mocked(exchangeApi.export).mockResolvedValue(new Blob(["xlsx"]));const create=vi.fn(()=>"blob:local");const revoke=vi.fn();Object.defineProperty(URL,"createObjectURL",{value:create,configurable:true});Object.defineProperty(URL,"revokeObjectURL",{value:revoke,configurable:true});
  const click=vi.spyOn(HTMLAnchorElement.prototype,"click").mockImplementation(()=>{});render(<CommercialSpreadsheet {...props}/>);fireEvent.click(screen.getByText("Exportar XLSX"));
  await waitFor(()=>expect(click).toHaveBeenCalled());expect(exchangeApi.export).toHaveBeenCalledWith("http://local","t","xlsx");expect(revoke).toHaveBeenCalledWith("blob:local");click.mockRestore();
});
