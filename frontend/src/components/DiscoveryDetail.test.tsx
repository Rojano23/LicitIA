import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {vi,it,expect,beforeEach} from 'vitest';
import {DiscoveryDetail} from './DiscoveryDetail';
import {monitoringApi,type Preview,type Opportunity} from '../api/discovery';
vi.mock('../api/discovery',()=>({monitoringApi:{get:vi.fn(),preview:vi.fn(),history:vi.fn(),follow:vi.fn(),acknowledge:vi.fn(),handoff:vi.fn()}}));
const row:Opportunity={id:'o',source_id:'PEMEX',external_id:'E1',title:'Válvula',description:'Fuente literal',business_area:'Área',published_date:null,event_type:null,supply_type:null,source_status:'Publicado',internal_state:'NEW',revision:1,document_count:1,public_url:'https://www.pemex.com',first_seen:'now',last_seen:'now',match:null,watching:false,unread_changes:1};
const preview:Preview={opportunity_id:'o',source_id:'PEMEX',source_fingerprint:'a',binding:'b',internal_state:'NEW',suggested_title:'Válvula',context:{},documents:[{id:'d',name:'Bases.pdf',public_url:'https://www.pemex.com/doc',metadata_fingerprint:'f',last_import:null}],linked_tender:null,selection_default:'NONE',analysis_automatic:false};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(monitoringApi.get).mockResolvedValue(row);vi.mocked(monitoringApi.preview).mockResolvedValue(preview);vi.mocked(monitoringApi.history).mockResolvedValue({items:[{id:'c',category:'DOCUMENT_ADDED',origin:'SOURCE',detected_at:'now',summary:'New document available',changed_fields:{name:'Bases.pdf'},acknowledged_at:null}],total:1,limit:100,offset:0});});
it('preview no crea ni descarga, selección vacía y confirmación obligatoria',async()=>{
 render(<DiscoveryDetail apiUrl="" id="o" onChanged={async()=>{}}/>);await screen.findByText('Create Tender — vista previa');
 expect(monitoringApi.handoff).not.toHaveBeenCalled();expect(screen.getByLabelText('Bases.pdf')).not.toBeChecked();expect(screen.getByText('Create Tender',{selector:'button'})).toBeDisabled();
 vi.mocked(monitoringApi.handoff).mockResolvedValue({tender_id:'t',tender_available:true,already_created:false,documents_status:'COMPLETE_SELECTION',analysis_started:false,documents:[]});
 fireEvent.click(screen.getByLabelText(/Confirmo crear Tender/));fireEvent.click(screen.getByText('Create Tender',{selector:'button'}));
 await waitFor(()=>expect(monitoringApi.handoff).toHaveBeenCalledWith('',preview,'Válvula',[]));await screen.findByText(/análisis no iniciado/);
});
it('selecciona documentos explícitos y muestra fallos parciales',async()=>{
 render(<DiscoveryDetail apiUrl="" id="o" onChanged={async()=>{}}/>);await screen.findByLabelText('Bases.pdf');
 vi.mocked(monitoringApi.handoff).mockResolvedValue({tender_id:'t',tender_available:true,already_created:false,documents_status:'PARTIAL',analysis_started:false,documents:[{source_document_id:'d',status:'FAILED',error_code:'SOURCE_DOWNLOAD_SIZE_LIMIT'}]});
 fireEvent.click(screen.getByLabelText('Bases.pdf'));fireEvent.click(screen.getByLabelText(/Confirmo crear Tender/));fireEvent.click(screen.getByText('Create Tender',{selector:'button'}));
 await screen.findByText(/SOURCE_DOWNLOAD_SIZE_LIMIT/);expect(monitoringApi.handoff).toHaveBeenCalledWith('',preview,'Válvula',[{document_id:'d',conflict_action:'NONE',revision_of_document_id:null,refresh:false}]);
});
it('follow y acknowledge son acciones separadas de creación',async()=>{
 render(<DiscoveryDetail apiUrl="" id="o" onChanged={async()=>{}}/>);await screen.findByText('Following — seguir');
 fireEvent.click(screen.getByText('Following — seguir'));await waitFor(()=>expect(monitoringApi.follow).toHaveBeenCalledWith('',row));
 await waitFor(()=>expect(screen.getByText('Marcar cambios visibles como leídos')).not.toBeDisabled());fireEvent.click(screen.getByText('Marcar cambios visibles como leídos'));
 await waitFor(()=>expect(monitoringApi.acknowledge).toHaveBeenCalledWith('','o',['c']));expect(monitoringApi.handoff).not.toHaveBeenCalled();
});
it('Open Tender usa vínculo persistido y muestra tombstone sin recreación',async()=>{
 const open=vi.fn();vi.mocked(monitoringApi.preview).mockResolvedValue({...preview,internal_state:'IMPORTED',linked_tender:{id:'t',available:true}});
 const view=render(<DiscoveryDetail apiUrl="" id="o" onOpenTender={open} onChanged={async()=>{}}/>);fireEvent.click(await screen.findByText('Open Tender'));expect(open).toHaveBeenCalledWith('t');view.unmount();
 vi.mocked(monitoringApi.preview).mockResolvedValue({...preview,internal_state:'IMPORTED',linked_tender:{id:'t',available:false}});render(<DiscoveryDetail apiUrl="" id="o" onChanged={async()=>{}}/>);await screen.findByText(/Tender eliminado/);expect(screen.getByText('Agregar documentos seleccionados')).toBeDisabled();
});
it('reintento de red advierte que el Tender puede existir',async()=>{
 vi.mocked(monitoringApi.handoff).mockRejectedValue(new Error('offline'));render(<DiscoveryDetail apiUrl="" id="o" onChanged={async()=>{}}/>);await screen.findByLabelText(/Confirmo crear Tender/);fireEvent.click(screen.getByLabelText(/Confirmo crear Tender/));fireEvent.click(screen.getByText('Create Tender',{selector:'button'}));expect(await screen.findByRole('alert')).toHaveTextContent('el Tender puede haberse creado');
});
