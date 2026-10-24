import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {describe,it,expect,vi,beforeEach} from 'vitest';
import {ProposalExports} from '../components/ProposalExports';
import {exportsApi} from '../api/proposalExports';
import {versionsApi} from '../api/proposalVersions';
import {proposalVersion} from '../test/commercialProductFixtures';
import {commercialLabel} from './commercialPresentation';
import {WorkspaceLoadBoundary} from './DeferredWorkspace';
vi.mock('../api/proposalExports',()=>({exportsApi:{create:vi.fn(),list:vi.fn(),verify:vi.fn(),file:vi.fn()}}));
vi.mock('../api/proposalVersions',()=>({versionsApi:{source:vi.fn()}}));
beforeEach(()=>vi.clearAllMocks());
describe('UIR7 closure',()=>{
 it('UIR7-01/03/07 translates canonical values without changing their meaning',()=>{
  expect(commercialLabel('FROZEN')).toBe('Versión congelada');
  expect(commercialLabel('MARKUP')).toBe('Markup');expect(commercialLabel('MARGIN')).toBe('Margen');
  expect(commercialLabel('MANUAL_PRICE_PROTECTED')).toBe('Precio manual protegido');
  expect(commercialLabel('UNRECOGNIZED_SECRET_CODE')).toBe('Revisar detalle técnico');
 });
 it('UIR7-04/45–47 suppresses arbitrary backend error text in product and retains retry identity',async()=>{
  vi.mocked(versionsApi.source).mockResolvedValue({state:'SOURCE_SNAPSHOT_STALE'});
  vi.mocked(exportsApi.create).mockRejectedValue({isAxiosError:true,response:{data:{detail:'SQL /Users/private SECRET_TOKEN traceback'}}});
  render(<ProposalExports apiUrl='/api' tenderId='t' version={proposalVersion('v','FROZEN')} compositionRevision={1} disabled={false} product/>);
  expect(exportsApi.create).not.toHaveBeenCalled();fireEvent.click(screen.getByText('Generar PDF'));
  expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron generar o consultar los archivos');
  expect(screen.getByRole('alert')).not.toHaveTextContent('SECRET_TOKEN');
  expect(screen.getByText(/Hay cambios posteriores\. Se generará/)).toBeVisible();
  fireEvent.click(screen.getByText('Reintentar solicitud de exportación'));
  await waitFor(()=>expect(exportsApi.create).toHaveBeenCalledTimes(2));
  expect(vi.mocked(exportsApi.create).mock.calls[0][3]).toEqual(vi.mocked(exportsApi.create).mock.calls[1][3]);
 });
 it('UIR7 local chunk error keeps recovery local and explicitly retryable',async()=>{
  const log=vi.spyOn(console,'error').mockImplementation(()=>{});const retry=vi.fn();
  function Broken():never{throw new Error('chunk unavailable');}
  const view=render(<WorkspaceLoadBoundary retry={retry}><Broken/></WorkspaceLoadBoundary>);
  expect(screen.getByRole('alert')).toHaveTextContent('herramientas de diagnóstico');
  view.rerender(<WorkspaceLoadBoundary retry={retry}><p>Herramientas disponibles</p></WorkspaceLoadBoundary>);
  fireEvent.click(screen.getByText('Volver a consultar'));expect(retry).toHaveBeenCalledOnce();
  expect(screen.getByText('Herramientas disponibles')).toBeVisible();log.mockRestore();
 });
});
