import { render,screen,waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach,it,expect,vi } from 'vitest';
import axios from 'axios';
import { InicioView } from './InicioView';
import { discoveryApi,monitoringApi } from '../api/discovery';
vi.mock('../api/discovery',()=>({discoveryApi:{list:vi.fn(),scans:vi.fn()},monitoringApi:{summary:vi.fn()}}));
const summary={new_opportunities:37,followed_with_changes:9,changed_opportunities:13,unread_changes:27,new_documents:6};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(monitoringApi.summary).mockResolvedValue(summary);vi.mocked(discoveryApi.list).mockResolvedValue({items:[],total:0,offset:0,limit:5});vi.mocked(discoveryApi.scans).mockResolvedValue([]);vi.spyOn(axios,'get').mockResolvedValue({data:[]});});
it('UIR2-01/03/04: métricas exactas y enlaces con filtros deterministas, sin charts',async()=>{
 render(<InicioView apiUrl="local"/>);expect(await screen.findByText('37')).toBeVisible();expect(screen.getByText('9')).toBeVisible();
 expect(screen.getByRole('link',{name:/Oportunidades nuevas/})).toHaveAttribute('href','#/discovery?view=new');expect(screen.getByRole('link',{name:/Siguiendo con cambios/})).toHaveAttribute('href','#/discovery?view=following-changes');
 expect(discoveryApi.list).toHaveBeenCalledWith('local',{following:true,unread_only:true,offset:0,limit:5});expect(document.querySelector('canvas,svg')).toBeNull();expect(screen.queryByText(/tendencia|porcentaje de cumplimiento/i)).toBeNull();
});
it('UIR2-05: instalación vacía sin tarjetas de cero decorativas',async()=>{
 vi.mocked(monitoringApi.summary).mockResolvedValue({...summary,new_opportunities:0,followed_with_changes:0});render(<InicioView apiUrl=""/>);
 expect(await screen.findByText('Aún no hay licitaciones.')).toBeVisible();expect(screen.getByRole('link',{name:'Crear licitación'})).toBeVisible();expect(screen.getByRole('link',{name:'Ir a Discovery'})).toBeVisible();expect(screen.queryByLabelText('Indicadores de Discovery')).toBeNull();
});
it('UIR2-06: atención sólo a hechos reales, agrupación y vínculos fuente',async()=>{
 vi.mocked(discoveryApi.scans).mockResolvedValue([{id:'scan',source_id:'CFE',status:'PARTIAL',started_at:'2026-10-23',metrics:{}}]);
 vi.mocked(axios.get).mockResolvedValue({data:[{id:'t',title:'Expediente de prueba',external_reference:'REF',institution_profile:null,status:'DRAFT',updated_at:'2026-10-23'}]});
 render(<InicioView apiUrl=""/>);expect(await screen.findByText('CFE · La consulta fue parcial')).toBeVisible();expect(screen.getByRole('link',{name:'Revisar consulta'})).toHaveAttribute('href','#/configuracion/diagnostico');
 expect(screen.getByRole('link',{name:'Abrir licitación'})).toHaveAttribute('href','#/licitaciones/t/resumen');expect(screen.queryByText('Lista para presentar')).toBeNull();
});
it('fallo de resumen no fabrica cero y permite conservar otras secciones/reintentar',async()=>{
 vi.mocked(monitoringApi.summary).mockRejectedValueOnce(new Error('offline'));render(<InicioView apiUrl=""/>);expect(await screen.findByRole('alert')).toHaveTextContent('resumen de oportunidades');expect(screen.queryByLabelText('Indicadores de Discovery')).toBeNull();
 await userEvent.click(screen.getByRole('button',{name:'Volver a consultar'}));await waitFor(()=>expect(screen.getByText('37')).toBeVisible());
});
