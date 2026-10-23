import {describe,it,expect,vi,beforeEach} from 'vitest';
import axios from 'axios';
import {discoveryApi,monitoringApi,type Profile,type Preview} from './discovery';
vi.mock('axios',()=>({default:{get:vi.fn(),post:vi.fn(),patch:vi.fn()}}));
function profile(i:number):Profile{return {id:String(i),name:String(i),revision:1,include_keywords:[],exclude_keywords:[],synonyms:{},source_ids:[],business_areas:[],active:true};}
beforeEach(()=>vi.resetAllMocks());
describe('Discovery local profile pagination',()=>{
 it('recorre todas las páginas locales antes de devolver perfiles',async()=>{
  vi.mocked(axios.get).mockResolvedValueOnce({data:Array.from({length:100},(_,i)=>profile(i))}).mockResolvedValueOnce({data:[profile(100)]});
  const rows=await discoveryApi.profiles('');expect(rows).toHaveLength(101);
  expect(axios.get).toHaveBeenNthCalledWith(2,'/discovery/profiles',{params:{limit:100,offset:100}});
 });
 it('falla explícitamente ante el límite sin truncamiento silencioso',async()=>{
  vi.mocked(axios.get).mockResolvedValue({data:Array.from({length:100},(_,i)=>profile(i))});
  await expect(discoveryApi.profiles('')).rejects.toThrow('DISCOVERY_PROFILE_LIST_LIMIT');
  expect(axios.get).toHaveBeenCalledTimes(20);
 });
});

it('binds the selected local profile to preview and confirmed handoff only',async()=>{
 const captured={id:'private-profile',revision:2,configuration:{...profile(1),name:'Private local interest'},match:{matched:true,include_hits:[],exclude_hits:[],restrictions:[]},sha256:'profile-sha'};
 const preview:Preview={opportunity_id:'o',source_id:'PEMEX',source_fingerprint:'source-sha',binding:'binding',suggested_title:'Public',context:{},documents:[],linked_tender:null,internal_state:'NEW',selection_default:'NONE',analysis_automatic:false,profile_context:captured};
 vi.mocked(axios.get).mockResolvedValue({data:preview});vi.mocked(axios.post).mockResolvedValue({data:{tender_id:'t'}});
 await monitoringApi.preview('http://localhost:8000','o','private-profile');
 expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/discovery/opportunities/o/tender-preview',{params:{profile_id:'private-profile'}});
 await monitoringApi.handoff('http://localhost:8000',preview,'Public',[]);
 expect(axios.post).toHaveBeenCalledWith('http://localhost:8000/discovery/opportunities/o/create-tender',{confirm:true,expected_binding:'binding',profile_id:'private-profile',title:'Public',documents:[]});
});
