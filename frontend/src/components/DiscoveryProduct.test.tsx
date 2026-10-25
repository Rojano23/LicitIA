import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {beforeEach,it,expect,vi} from 'vitest';
import {DiscoveryView} from './DiscoveryView';
import {discoveryApi,monitoringApi,type Opportunity} from '../api/discovery';
vi.mock('../api/discovery',()=>({discoveryApi:{sources:vi.fn(),profiles:vi.fn(),scans:vi.fn(),scan:vi.fn(),list:vi.fn(),state:vi.fn(),getScan:vi.fn(),configure:vi.fn()},monitoringApi:{follow:vi.fn()}}));
const source={id:'CFE',name:'CFE',enabled:true,last_scan_state:null,last_error:null,areas:[{key:'public',label:'Público'}],configuration:{areas:['public']}};
const row:Opportunity={id:'o',source_id:'CFE',external_id:'1',procedure_number:'1',title:'Controlador de prueba',description:null,business_area:'Área',published_date:null,event_type:null,supply_type:null,source_status:null,internal_state:'NEW',revision:1,document_count:4,public_url:'https://msc.cfe.mx',first_seen:'2026-10-23',last_seen:'2026-10-23',match:null,watching:false};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(discoveryApi.sources).mockResolvedValue([source]);vi.mocked(discoveryApi.profiles).mockResolvedValue([]);vi.mocked(discoveryApi.scans).mockResolvedValue([]);vi.mocked(discoveryApi.list).mockImplementation(async(_base,p)=>({items:[row],total:101,offset:Number(p.offset),limit:50}));});
it('UIR2-04/08/13/18: deep filter NEW y datos normalizados sin códigos en tabla',async()=>{
 render(<DiscoveryView apiUrl="" view="new"/>);await screen.findByText('Controlador de prueba');expect(discoveryApi.list).toHaveBeenCalledWith('',expect.objectContaining({internal_state:'NEW',offset:0}));
 expect(screen.getByText('Nueva',{selector:'.ui-badge'})).toBeVisible();expect(screen.getByText(/4 referencias descubiertas/)).toBeVisible();expect(screen.getByText('Sin perfil seleccionado')).toBeVisible();
});
it('UIR2-09/10/12: filtros/search en servidor y paginación íntegra',async()=>{
 render(<DiscoveryView apiUrl=""/>);await screen.findByText('Controlador de prueba');await waitFor(()=>expect(screen.getByText('Aplicar filtros')).not.toBeDisabled());
 fireEvent.change(screen.getByLabelText('Fuente de oportunidades guardadas'),{target:{value:'CFE'}});fireEvent.change(screen.getByLabelText('Buscar procedimiento, descripción o área'),{target:{value:'PLC'}});fireEvent.click(screen.getByText('Aplicar filtros'));
 await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({source:'CFE',search:'PLC',offset:0})));
 await waitFor(()=>expect(screen.getByText('Página siguiente')).not.toBeDisabled());fireEvent.click(screen.getByText('Página siguiente'));await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({source:'CFE',search:'PLC',offset:50})));
});
it('UIR2-14/19: siguiendo con cambios usa watching, no elimina importadas',async()=>{
 render(<DiscoveryView apiUrl="" view="following-changes"/>);await screen.findByText('Controlador de prueba');expect(discoveryApi.list).toHaveBeenCalledWith('',expect.objectContaining({following:true,unread_only:true,internal_state:undefined}));
});
it('UIR2-25/26: follow y unfollow usan endpoint separado, no crean Tender',async()=>{
 vi.mocked(discoveryApi.list).mockResolvedValue({items:[{...row,watching:true}],total:1,limit:50,offset:0});render(<DiscoveryView apiUrl=""/>);await screen.findByText('Controlador de prueba');await waitFor(()=>expect(screen.getByText('Dejar de seguir')).not.toBeDisabled());fireEvent.click(screen.getByText('Dejar de seguir'));await waitFor(()=>expect(monitoringApi.follow).toHaveBeenCalledWith('',expect.objectContaining({watching:true})));
});
it('UIR2-21: fallo de una consulta no borra resultados locales',async()=>{
 vi.mocked(discoveryApi.scan).mockRejectedValue(new Error('public source unavailable'));render(<DiscoveryView apiUrl=""/>);await screen.findByText('Controlador de prueba');await waitFor(()=>expect(screen.getByText('Aplicar filtros')).not.toBeDisabled());
 fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'CFE'}});await waitFor(()=>expect(screen.getByText('Consultar fuente')).not.toBeDisabled());fireEvent.click(screen.getByText('Consultar fuente'));await screen.findByRole('alert');expect(screen.getByText('Controlador de prueba')).toBeVisible();
});
it('metric navigation clears earlier local filters rather than narrowing a global count',async()=>{
 const v=render(<DiscoveryView apiUrl=""/>);await screen.findByText('Controlador de prueba');await waitFor(()=>expect(screen.getByText('Aplicar filtros')).not.toBeDisabled());
 fireEvent.change(screen.getByLabelText('Fuente de oportunidades guardadas'),{target:{value:'CFE'}});fireEvent.change(screen.getByLabelText('Buscar procedimiento, descripción o área'),{target:{value:'previous'}});fireEvent.click(screen.getByText('Aplicar filtros'));
 await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({search:'previous'})));
 v.rerender(<DiscoveryView apiUrl="" view="new" filterRequest={{}}/>);
 await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({internal_state:'NEW',source:undefined,search:undefined,profile_id:undefined,matched_only:false})));
});
it('pagination uses applied filters, including back to page zero after editing a draft',async()=>{
 render(<DiscoveryView apiUrl=""/>);await screen.findByText('Controlador de prueba');await waitFor(()=>expect(screen.getByText('Página siguiente')).not.toBeDisabled());
 fireEvent.click(screen.getByText('Página siguiente'));await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({offset:50})));
 await waitFor(()=>expect(screen.getByText('Página anterior')).not.toBeDisabled());fireEvent.change(screen.getByLabelText('Buscar procedimiento, descripción o área'),{target:{value:'not applied'}});fireEvent.click(screen.getByText('Página anterior'));
 await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({offset:0,search:undefined})));
});
