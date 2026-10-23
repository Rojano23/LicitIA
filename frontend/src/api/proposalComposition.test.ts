import {it,expect,vi} from "vitest";
import axios from "axios";
import {compositionApi} from "./proposalComposition";
vi.mock("axios",()=>({default:{patch:vi.fn()}}));
it("sends editable section fields matching the bounded server contract",async()=>{
 vi.mocked(axios.patch).mockResolvedValue({data:{initialized:true}});
 await compositionApi.settings("http://local","t","v",3,{sections:[{id:"notes",type:"NOTES",order:4,included:false,note:null}]});
 expect(axios.patch).toHaveBeenCalledWith("http://local/tenders/t/proposal-versions/v/composition/settings",{
  expected_revision:3,origin:"WORKSPACE",sections:[{id:"notes",order:4,included:false,note:""}]
 });
});
