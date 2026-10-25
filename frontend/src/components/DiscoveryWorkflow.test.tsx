import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {vi,it,expect,beforeEach,afterEach} from 'vitest';
import {DiscoveryView} from './DiscoveryView';
import {SettingsView} from './SettingsView';
import {discoveryApi,type Scan} from '../api/discovery';
import {resolvePeriod} from './discoveryPeriods';
import {readRoute} from '../ui/routes';
vi.mock('../api/discovery',()=>({discoveryApi:{sources:vi.fn(),profiles:vi.fn(),scans:vi.fn(),scan:vi.fn(),list:vi.fn(),saveProfile:vi.fn()},monitoringApi:{}}));
const source={id:'PEMEX',name:'PEMEX',enabled:true,last_scan_state:'SUCCESS',last_error:null,areas:[{key:'support',label:'Soporte'}],configuration:{areas:['support']}};
const profile={id:'p',name:'Instrumentación',revision:4,include_keywords:['PLC'],exclude_keywords:['cancelado'],synonyms:{PLC:['controlador']},source_ids:['PEMEX'],business_areas:['Área'],active:true};
const scan:Scan={id:'s',source_id:'PEMEX',status:'SUCCESS',started_at:'2026-10-24T12:00:00Z',finished_at:'2026-10-24T12:03:00Z',query:{areas:['support'],published_from:'2026-09-25',published_to:'2026-10-24',event_type:null,supply_type:null,page_size:100},metrics:{unique_opportunities:111,pages_attempted:4,pages_completed:4,rows_retrieved:111}};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(discoveryApi.sources).mockResolvedValue([source]);vi.mocked(discoveryApi.profiles).mockResolvedValue([profile]);vi.mocked(discoveryApi.scans).mockResolvedValue([scan]);vi.mocked(discoveryApi.list).mockResolvedValue({items:[],total:0,limit:50,offset:0});vi.mocked(discoveryApi.scan).mockResolvedValue(scan);});
afterEach(()=>vi.useRealTimers());
async function open(){render(<DiscoveryView apiUrl=""/>);await screen.findByText(/111 oportunidades · 4 lotes/);await waitFor(()=>expect(screen.getByText('Aplicar filtros')).not.toBeDisabled());}
it('presets are inclusive calendar dates across month/year/leap boundaries',()=>{
 const today=new Date(2026,9,24,23,59);expect(resolvePeriod('30',today)).toEqual({from:'2026-09-25',to:'2026-10-24'});
 expect(resolvePeriod('7',today)).toEqual({from:'2026-10-18',to:'2026-10-24'});expect(resolvePeriod('60',today).from).toBe('2026-08-26');expect(resolvePeriod('90',today).from).toBe('2026-07-27');
 expect(resolvePeriod('month',today).from).toBe('2026-10-01');expect(resolvePeriod('previous',new Date(2024,2,15))).toEqual({from:'2024-02-01',to:'2024-02-29'});expect(resolvePeriod('previous',new Date(2026,0,5))).toEqual({from:'2025-12-01',to:'2025-12-31'});expect(resolvePeriod('all',today)).toEqual({from:'',to:''});
});
it('four steps, Nueva consulta focuses without acquisition; custom dates only when requested',async()=>{
 await open();for(const label of ['1. Consultar una fuente','2. Resultado de la consulta','3. Filtrar oportunidades guardadas','4. Revisar oportunidades'])expect(screen.getByText(label)).toBeInTheDocument();
 expect(screen.getByLabelText('Periodo de publicación')).toHaveValue('30');expect(screen.getByLabelText('Periodo de oportunidades')).toHaveValue('all');
 expect(screen.queryByText('Nueva consulta')).not.toBeInTheDocument();expect(screen.getByText('Consultar fuente')).toBeVisible();expect(discoveryApi.scan).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Periodo de publicación'),{target:{value:'custom'}});fireEvent.change(screen.getByLabelText('Periodo de publicación: Desde'),{target:{value:'2026-01-01'}});fireEvent.change(screen.getByLabelText('Periodo de publicación: Hasta'),{target:{value:'2026-01-31'}});
 fireEvent.click(screen.getByText('Consultar fuente'));await waitFor(()=>expect(discoveryApi.scan).toHaveBeenCalledWith('','PEMEX',expect.any(String),expect.objectContaining({published_from:'2026-01-01',published_to:'2026-01-31'})));
});
it.each([false,true])('Ver resultados applies source/publication, clears unrelated filters, preserves profile-only=%s',async matched=>{
 await open();fireEvent.change(screen.getByLabelText('Perfil de búsqueda'),{target:{value:'p'}});if(matched)fireEvent.click(screen.getByLabelText('Sólo coincidencias del perfil'));
 fireEvent.change(screen.getByLabelText('Buscar procedimiento, descripción o área'),{target:{value:'old'}});fireEvent.click(screen.getByLabelText('Siguiendo'));fireEvent.click(screen.getByText('Ver resultados'));
 await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({source:'PEMEX',published_from:'2026-09-25',published_to:'2026-10-24',profile_id:'p',matched_only:matched,search:undefined,following:false,offset:0})));
 expect(screen.getByLabelText('Sólo coincidencias del perfil')).toHaveProperty('checked',matched);expect(screen.getByLabelText('Periodo de oportunidades')).toHaveValue('custom');expect(document.activeElement?.id).toBe('stored-filters');expect(screen.queryByText(/0 de 111/)).not.toBeInTheDocument();
});
it('advanced filters have accessible toggle help with verified source examples; no source-status filter/editor',async()=>{
 await open();expect(screen.queryByLabelText(/Estado fuente/)).not.toBeInTheDocument();expect(screen.queryByLabelText('Nombre del perfil')).not.toBeInTheDocument();expect(screen.getByRole('link',{name:'Administrar perfiles'})).toHaveAttribute('href','#/configuracion?section=profiles');
 fireEvent.click(screen.getByText('Más filtros'));const help=screen.getByLabelText('Ayuda: Tipo de evento');fireEvent.click(help);expect(help.parentElement).toHaveAttribute('open');expect(help.parentElement?.querySelector('p')).toHaveTextContent('Internacional bajo TLC');expect(help.parentElement?.querySelector('p')).toBeVisible();expect(screen.getByLabelText('Ayuda: Área o entidad')).toBeVisible();
});
it('latest consultation stays compact with no history or technical disclosure',async()=>{await open();expect(screen.queryByText('Ver historial')).not.toBeInTheDocument();expect(screen.queryByText('Diagnóstico de la consulta')).not.toBeInTheDocument();expect(discoveryApi.scan).not.toHaveBeenCalled();});
it('Settings owns complete editor and preserves optimistic revision and configuration semantics',async()=>{
 render(<SettingsView apiUrl="" focusProfiles/>);await screen.findByRole('option',{name:'Instrumentación'});fireEvent.change(screen.getByLabelText('Editar perfil'),{target:{value:'p'}});
 expect(screen.getByLabelText('Restringir perfil a PEMEX')).toBeChecked();expect(screen.getByLabelText('Excluir (precedencia sobre incluir)')).toHaveValue('cancelado');
 vi.mocked(discoveryApi.saveProfile).mockResolvedValue({...profile,revision:5});fireEvent.click(screen.getByText('Guardar perfil'));await waitFor(()=>expect(discoveryApi.saveProfile).toHaveBeenCalledWith('',expect.objectContaining({synonyms:{PLC:['controlador']},source_ids:['PEMEX'],business_areas:['Área'],active:true}),'p',4));
 expect(readRoute('#/configuracion?section=profiles')).toEqual({page:'configuracion',settingsSection:'profiles'});expect(discoveryApi.scan).not.toHaveBeenCalled();
});
it('CFE acquisition uses only accepted event labels; supply stays optional and no source configuration is written',async()=>{
 vi.mocked(discoveryApi.sources).mockResolvedValue([source,{...source,id:'CFE',name:'CFE',areas:[{key:'public',label:'Público'}],configuration:{areas:['public']}}]);await open();fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'CFE'}});
 const query=document.getElementById('source-consultation')!;const event=Array.from(query.querySelectorAll('label')).find(e=>e.firstChild?.textContent==='Tipo de evento')!.querySelector('select')!;
 expect(Array.from(event.options).map(o=>o.value)).toEqual(['','Concurso abierto','Concurso simplificado','Adjudicación directa']);expect(discoveryApi.scan).not.toHaveBeenCalled();
});
it('empty installation offers a first query but a filtered zero never claims no public procedures',async()=>{
 vi.mocked(discoveryApi.sources).mockResolvedValue([{...source,last_scan_state:null}]);vi.mocked(discoveryApi.scans).mockResolvedValue([]);render(<DiscoveryView apiUrl=""/>);await screen.findByText(/Aún no hay oportunidades consultadas/);
 fireEvent.change(screen.getByLabelText('Buscar procedimiento, descripción o área'),{target:{value:'sin coincidencias'}});fireEvent.click(screen.getByText('Aplicar filtros'));await waitFor(()=>expect(screen.queryByText(/Aún no hay oportunidades consultadas/)).not.toBeInTheDocument());expect(screen.getByText(/esto no confirma ausencia/)).toBeInTheDocument();expect(discoveryApi.scan).not.toHaveBeenCalled();
});
