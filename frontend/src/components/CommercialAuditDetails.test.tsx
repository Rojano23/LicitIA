import {render,screen,fireEvent} from "@testing-library/react";
import {beforeEach,it,expect,vi} from "vitest";
import {CommercialAuditDetails} from "./CommercialAuditDetails";
import {auditApi,type CommercialAudit} from "../api/commercialReadiness";
vi.mock("../api/commercialReadiness",()=>({auditApi:{read:vi.fn()}}));
const history: CommercialAudit={current_revision:2,current_manual_price:true,scope_available:true,next_before_revision:2,events:[{
  revision:2,timestamp:"2026-10-22T00:00:00Z",origin:"XLSX",action:"XLSX_IMPORT",actor_label:null,manual_price:true,note:"Estrategia autorizada",
  offered_unit_price:"90",recommended_unit_price:"125",differs_from_recommendation:true,changes:[{field:"offered_unit_price",previous:"80",current:"90"}],import_evidence:{sha256:"f".repeat(64)}}]};
const props={apiUrl:"http://local",tenderId:"t",scopeId:"s",disabled:false};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(auditApi.read).mockResolvedValue(history);});
it("loads history on demand and shows manual decision, origin, note and previous value",async()=>{
  render(<CommercialAuditDetails {...props}/>);expect(auditApi.read).not.toHaveBeenCalled();fireEvent.click(screen.getByText("Consultar historial comercial s"));
  expect(await screen.findByText(/Estrategia autorizada/)).toHaveTextContent("90");expect(screen.getByText(/Revisión 2 · XLSX/)).toBeInTheDocument();expect(screen.getByText(/offered_unit_price: 80 → 90/)).toBeInTheDocument();expect(screen.getByText(/Import SHA-256:/)).toBeInTheDocument();
});
it("loads older revisions without losing visible recent history",async()=>{
  render(<CommercialAuditDetails {...props}/>);fireEvent.click(screen.getByText("Consultar historial comercial s"));await screen.findByText(/Revisión 2 · XLSX/);
  vi.mocked(auditApi.read).mockResolvedValue({...history,next_before_revision:null,events:[{...history.events[0],revision:1,origin:"UI"}]});
  fireEvent.click(screen.getByText("Ver revisiones anteriores"));expect(await screen.findByText(/Revisión 1 · UI/)).toBeInTheDocument();expect(screen.getByText(/Revisión 2 · XLSX/)).toBeInTheDocument();expect(auditApi.read).toHaveBeenLastCalledWith("http://local","t","s",2);
});
it("reports unavailable audit explicitly",async()=>{
  vi.mocked(auditApi.read).mockRejectedValue(new Error("offline"));render(<CommercialAuditDetails {...props}/>);fireEvent.click(screen.getByText("Consultar historial comercial s"));expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo consultar");
});
it("respects parent busy state",()=>{render(<CommercialAuditDetails {...props} disabled/>);expect(screen.getByText("Consultar historial comercial s")).toBeDisabled();});
