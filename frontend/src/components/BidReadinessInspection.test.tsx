import {render,screen,fireEvent} from "@testing-library/react";
import {beforeEach,it,expect,vi} from "vitest";
import {BidReadinessInspection} from "./BidReadinessInspection";
import {bidReadinessApi,type BidReadiness} from "../api/bidReadiness";
vi.mock("../api/bidReadiness",()=>({bidReadinessApi:{read:vi.fn()}}));
const data:BidReadiness={status:"INCOMPLETE",blocker_count:1,review_required_count:0,warning_count:1,total_issues:2,notice:"Según registros rastreados; la revisión humana es autoritativa.",dimensions:[{dimension:"COMMERCIAL",status:"INCOMPLETE",item_count:1,issue_count:1}],issues:[{id:"i",dimension:"COMMERCIAL",entity_type:"SCOPE",entity_id:"scope-id",status:"INCOMPLETE",severity:"BLOCKER",code:"MISSING_OFFERED_PRICE",summary:"Precio pendiente.",source_module:"commercial_projections",review_context:"/workspace",reference:{document_id:"doc",revision:2,page:4,locator:"fila",excerpt:"Fragmento original"}}]};
const props={apiUrl:"http://local",tenderId:"t",disabled:false};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(bidReadinessApi.read).mockResolvedValue(data);});
it("inspects on demand and shows status, dimensions, identity and provenance",async()=>{
 render(<BidReadinessInspection {...props}/>);expect(bidReadinessApi.read).not.toHaveBeenCalled();fireEvent.click(screen.getByText("Consultar Bid Readiness"));
 expect(await screen.findByRole("status")).toHaveTextContent("INCOMPLETE");expect(screen.getByText(/MISSING_OFFERED_PRICE/)).toHaveTextContent("BLOCKER");expect(screen.getByText(/SCOPE: scope-id/)).toBeInTheDocument();expect(screen.getByText(/Documento doc · versión 2 · p. 4/)).toBeInTheDocument();expect(screen.getByText("Fragmento original")).toBeInTheDocument();
});
it("keeps tracked-state and human-review language visible for READY",async()=>{
 vi.mocked(bidReadinessApi.read).mockResolvedValue({...data,status:"READY",blocker_count:0});render(<BidReadinessInspection {...props}/>);fireEvent.click(screen.getByText("Consultar Bid Readiness"));expect(await screen.findByText(data.notice)).toBeInTheDocument();expect(screen.getByRole("status")).toHaveTextContent("READY");
});
it("failed refresh clears a previous result",async()=>{
 render(<BidReadinessInspection {...props}/>);fireEvent.click(screen.getByText("Consultar Bid Readiness"));await screen.findByRole("status");vi.mocked(bidReadinessApi.read).mockRejectedValue(new Error("offline"));fireEvent.click(screen.getByText("Consultar Bid Readiness"));expect(await screen.findByRole("alert")).toBeInTheDocument();expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
it("respects processing busy state",()=>{render(<BidReadinessInspection {...props} disabled/>);expect(screen.getByText("Consultar Bid Readiness")).toBeDisabled();});
