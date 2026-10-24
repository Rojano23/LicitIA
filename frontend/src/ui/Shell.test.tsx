import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEffect, useState } from 'react';
import { AppShell, TenderContextNav } from './AppShell';
import { Button, EmptyState, ErrorState, LoadingState, SourceBadge, StatusBadge, TableShell } from './primitives';
import { readRoute } from './routes';
const reads = vi.hoisted(() => ({ workspace: vi.fn(), discovery: vi.fn() }));
vi.mock('../App', () => ({ default: ({ onContext, requestedTenderId }: { onContext: (value: {id:string;title:string;reference:null;status:string}) => void; requestedTenderId?:string }) => {
 const [value, setValue] = useState('');
 useEffect(() => { reads.workspace(); onContext({id:requestedTenderId ?? 'synthetic',title:'Expediente de prueba',reference:null,status:'DRAFT'}); }, [onContext, requestedTenderId]);
 return <section aria-label="Workspace de prueba"><input aria-label="Decisión local de prueba" value={value} onChange={e=>setValue(e.target.value)}/><div id="workspace-propuesta">Versiones existentes</div></section>;
} }));
vi.mock('../components/DiscoveryView', () => ({ DiscoveryView: () => {useEffect(()=>{reads.discovery();},[]);return <p>Discovery existente</p>;} }));
vi.mock('../components/CompanyView', () => ({ CompanyView: () => <p>Biblioteca existente</p> }));
vi.mock('../components/ReportsView',()=>({ReportsView:()=> <p>Catálogo de reportes existente</p>}));
vi.mock('../components/SettingsView',()=>({SettingsView:()=> <a href="#/configuracion/diagnostico">Abrir Diagnóstico</a>}));
vi.mock('../components/DiagnosticsView',()=>({DiagnosticsView:({onOpenTools}:{onOpenTools:()=>void})=><button onClick={onOpenTools}>Abrir herramientas del expediente</button>}));
vi.mock('../components/InicioView',()=>({InicioView:()=> <p>Inicio sin adquisición de prueba</p>}));
vi.mock('../components/TenderProductViews',()=>({TenderListView:()=>null,TenderProductWorkspace:()=>null}));
import ProductApp from '../ProductApp';
function route(path:string) { window.history.replaceState(null,'',`/#${path}`); fireEvent(window,new HashChangeEvent('hashchange')); }
beforeEach(()=>{route('/'); reads.workspace.mockClear();reads.discovery.mockClear();});
describe('UI-R1 shell / routing',()=>{
 it('UIR1-01/03/04/05/08/09/10/21/32/34: marca, destinos y fallback sin cifras ficticias',async()=>{
  render(<ProductApp/>);expect(document.title).toBe('RX23 TuScope');expect(screen.getByRole('link',{name:'RX23 TuScope — Inicio'})).toBeVisible();
  expect(screen.getByRole('heading',{level:1,name:'Inicio'})).toBeVisible();expect(reads.workspace).not.toHaveBeenCalled();expect(reads.discovery).not.toHaveBeenCalled();
  route('/mi-empresa');expect(await screen.findByText('Biblioteca existente')).toBeVisible();
  route('/reportes');expect(await screen.findByText('Catálogo de reportes existente',{exact:false})).toBeVisible();
  route('/configuracion');expect(await screen.findByRole('link',{name:'Abrir Diagnóstico'})).toBeVisible();
  route('/configuracion/diagnostico');await userEvent.click(await screen.findByText('Abrir herramientas del expediente'));expect(await screen.findByLabelText('Workspace de prueba')).toBeVisible();
  route('/missing');expect(await screen.findByRole('heading',{name:'Esta dirección no está disponible'})).toBeVisible();
 });
 it('UIR1-06/07/11/13–16/29–31: contexto conserva identidad y borrador; no remonta por tab',async()=>{
  const user=userEvent.setup();render(<ProductApp/>);route('/discovery');expect(await screen.findByText('Discovery existente')).toBeVisible();route('/configuracion/diagnostico');
  expect(await screen.findByRole('heading',{level:1,name:'Diagnóstico'})).toBeVisible();
  // Core routes are tested with the real product views in CommercialProduct/TenderRouting.

  expect(screen.getByRole('navigation',{name:'Navegación principal'})).not.toHaveTextContent('Partidas');
  await user.click(screen.getByText('Abrir herramientas del expediente'));
  await user.type(screen.getByLabelText('Decisión local de prueba'),'precio pendiente');const count=reads.workspace.mock.calls.length;
  route('/configuracion');expect(await screen.findByRole('heading',{level:1,name:'Configuración'})).toBeVisible();
  expect(screen.getByLabelText('Decisión local de prueba')).toHaveValue('precio pendiente');expect(reads.workspace).toHaveBeenCalledTimes(count);
  route('/');route('/configuracion/diagnostico');await waitFor(()=>expect(screen.getByLabelText('Decisión local de prueba')).toBeVisible());
  expect(screen.getByLabelText('Decisión local de prueba')).toHaveValue('precio pendiente');expect(reads.workspace).toHaveBeenCalledTimes(count);
 });
 it('UIR1-12/28: menú accesible y Escape',async()=>{
  const user=userEvent.setup();render(<AppShell route={{page:'discovery'}}><p>Contenido real</p></AppShell>);
  const menu=screen.getByRole('button',{name:'Menú'});await user.click(menu);expect(menu).toHaveAttribute('aria-expanded','true');
  expect(screen.getByRole('link',{name:'Discovery'})).toHaveAttribute('aria-current','page');
  fireEvent.keyDown(screen.getByRole('complementary'),{key:'Escape'});expect(menu).toHaveAttribute('aria-expanded','false');expect(menu).toHaveFocus();
 });
 it('rutas inválidas y codificadas',()=>{
  expect(readRoute('#/licitaciones/a%20b/documentos')).toEqual({page:'licitaciones',tenderId:'a b',section:'documentos'});
  for(const path of ['#/licitaciones/%GG/resumen','#/licitaciones/id/raw','#/unknown'])expect(readRoute(path).page).toBe('not-found');
 });
 it('UIR1-19/20/22–24: estados con texto y fuente restringida sin scan',()=>{
  render(<><StatusBadge tone="warning">Requiere revisión</StatusBadge><SourceBadge name="Compras MX" restricted/><Button variant="primary">Guardar</Button><Button variant="destructive">Eliminar</Button><LoadingState/><ErrorState/><EmptyState title="Sin documentos">Agrega originales para continuar.</EmptyState><TableShell label="Lista" empty><table/></TableShell></>);
  expect(screen.getByText('Requiere revisión')).toBeVisible();expect(screen.getByText('Automatización no disponible actualmente')).toBeVisible();expect(screen.queryByRole('button',{name:/scan|consultar fuente/i})).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Guardar'})).toHaveClass('ui-button--primary');expect(screen.getByRole('button',{name:'Eliminar'})).toHaveClass('ui-button--destructive');expect(screen.getByRole('status')).toHaveTextContent('Consultando');expect(screen.getByRole('alert')).not.toHaveTextContent('Traceback');
 });
 it('UIR1-14: contextual no agrega destinos globales',()=>{
  render(<TenderContextNav id="id" section="preparacion"/>);expect(screen.getByRole('link',{name:'Preparación de oferta'})).toHaveAttribute('aria-current','page');expect(screen.queryByText('Discovery')).not.toBeInTheDocument();
 });
});
