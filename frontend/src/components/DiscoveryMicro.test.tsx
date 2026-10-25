import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import {vi,it,expect,beforeEach} from 'vitest';
import {DiscoveryView} from './DiscoveryView';
import {SettingsView} from './SettingsView';
import {discoveryApi} from '../api/discovery';
vi.mock('../api/discovery',()=>({discoveryApi:{sources:vi.fn(),profiles:vi.fn(),scans:vi.fn(),scan:vi.fn(),list:vi.fn(),configure:vi.fn()},monitoringApi:{}}));
const source={id:'PEMEX',name:'PEMEX',enabled:true,last_scan_state:'SUCCESS',last_error:null,areas:[{key:'support',label:'Soporte'},{key:'logistics',label:'Logística'},{key:'other',label:'Otra área'}],configuration:{areas:['support','logistics']}};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(discoveryApi.sources).mockResolvedValue([source,{...source,id:'COMPRAS_MX',name:'Compras MX',enabled:false,capabilities:{automation_status:'DEFERRED_SOURCE_AUTOMATION_RESTRICTED'}}]);vi.mocked(discoveryApi.profiles).mockResolvedValue([]);vi.mocked(discoveryApi.scans).mockResolvedValue([]);vi.mocked(discoveryApi.list).mockResolvedValue({items:[],total:0,offset:0,limit:50});vi.mocked(discoveryApi.scan).mockResolvedValue({id:'s',source_id:'PEMEX',status:'SUCCESS',started_at:'2026-10-24',metrics:{unique_opportunities:2}});});
it('source blocks have no forced breaks; restriction and actual state stay intact',async()=>{
 render(<DiscoveryView apiUrl=""/>);const strip=await screen.findByLabelText('Estado de fuentes');await waitFor(()=>expect(strip.textContent).toContain('Consulta completada'));expect(strip.querySelector('br')).toBeNull();expect(strip.textContent).toContain('Disponible para consulta');expect(within(strip).getByText('Automatización no disponible actualmente')).toBeInTheDocument();expect(discoveryApi.configure).not.toHaveBeenCalled();
});
it('query area subset works without administrative write; unconfigured areas are not silently enabled',async()=>{
 render(<DiscoveryView apiUrl=""/>);await screen.findByLabelText('Soporte');await waitFor(()=>expect(screen.getByText('Consultar fuente')).not.toBeDisabled());expect(screen.queryByText(/Deshabilitar fuente con áreas/)).not.toBeInTheDocument();expect(screen.getByLabelText('Otra área')).toBeDisabled();fireEvent.click(screen.getByLabelText('Soporte'));fireEvent.click(screen.getByText('Consultar fuente'));await waitFor(()=>expect(discoveryApi.scan).toHaveBeenCalledWith('','PEMEX',expect.any(String),expect.objectContaining({areas:['logistics']})));expect(discoveryApi.configure).not.toHaveBeenCalled();
});
it('disabled source guides to configuration without an enable action or implicit query',async()=>{
 vi.mocked(discoveryApi.sources).mockResolvedValue([{...source,enabled:false}]);render(<DiscoveryView apiUrl=""/>);await screen.findByText(/Esta fuente está deshabilitada/);expect(screen.getByText('Consultar fuente')).toBeDisabled();expect(screen.getByRole('link',{name:'Configurar fuente'})).toHaveAttribute('href','#/configuracion?section=sources');expect(screen.queryByText(/Habilitar fuente con áreas/)).not.toBeInTheDocument();expect(discoveryApi.scan).not.toHaveBeenCalled();
});
it('Configuration retains administrative persistence and focuses the source section',async()=>{
 vi.mocked(discoveryApi.configure).mockResolvedValue(source);render(<SettingsView apiUrl="" focusSources/>);await screen.findByText('Configurar PEMEX');expect(document.activeElement?.id).toBe('source-settings');fireEvent.click(screen.getByText('Configurar PEMEX'));fireEvent.click(screen.getByLabelText('Habilitar consulta manual'));fireEvent.click(screen.getByText('Guardar configuración de fuente'));await waitFor(()=>expect(discoveryApi.configure).toHaveBeenCalledWith('','PEMEX',{enabled:false,areas:['support','logistics']}));expect(discoveryApi.scan).not.toHaveBeenCalled();
});
