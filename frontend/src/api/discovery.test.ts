import {describe,it,expect,vi,beforeEach} from 'vitest';
import axios from 'axios';
import {discoveryApi,type Profile} from './discovery';
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
