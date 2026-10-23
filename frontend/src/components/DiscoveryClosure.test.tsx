import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {vi,it,expect,beforeEach} from 'vitest';
import {DiscoveryView} from './DiscoveryView';
import {DiscoveryDetail} from './DiscoveryDetail';
import {discoveryApi,monitoringApi,type Opportunity,type Preview} from '../api/discovery';
vi.mock('../api/discovery',()=>({discoveryApi:{sources:vi.fn(),profiles:vi.fn(),scans:vi.fn(),scan:vi.fn(),list:vi.fn(),state:vi.fn()},monitoringApi:{summary:vi.fn(),get:vi.fn(),preview:vi.fn(),history:vi.fn(),follow:vi.fn(),acknowledge:vi.fn(),handoff:vi.fn()}}));
let row:Opportunity;
function preview():Preview{return {opportunity_id:row.id,source_id:row.source_id,source_fingerprint:'f',binding:'binding',internal_state:row.internal_state,suggested_title:row.title,context:{},documents:[{id:'document',name:'Bases.pdf',public_url:'https://www.pemex.com/public-document',metadata_fingerprint:'d',last_import:null}],linked_tender:row.linked_tender??null,selection_default:'NONE',analysis_automatic:false};}
beforeEach(()=>{
 vi.clearAllMocks();row={id:'opportunity',source_id:'PEMEX',external_id:'EVENT',title:'Controlador PLC',description:'Objeto público',business_area:'Soporte',published_date:null,event_type:null,supply_type:null,source_status:'Publicado',internal_state:'NEW',revision:1,document_count:1,public_url:'https://www.pemex.com',first_seen:'2026-10-23',last_seen:'2026-10-23',match:{matched:true,include_hits:[{term:'PLC',matched_text:'PLC',field:'title',kind:'EXACT'}],exclude_hits:[],restrictions:[]}};
 vi.mocked(discoveryApi.sources).mockResolvedValue([{id:'PEMEX',name:'PEMEX público',enabled:true,last_scan_state:null,last_error:null,areas:[{key:'support',label:'Soporte'}],configuration:{areas:['support']}}]);
 vi.mocked(discoveryApi.profiles).mockResolvedValue([{id:'profile',name:'Interés local',revision:1,include_keywords:['PLC'],exclude_keywords:['cancelado'],synonyms:{},source_ids:[],business_areas:[],active:true}]);
 vi.mocked(discoveryApi.scans).mockResolvedValue([]);vi.mocked(discoveryApi.scan).mockResolvedValue({id:'scan',status:'SUCCESS',started_at:'now',metrics:{pages_completed:3,unique_opportunities:217}});
 vi.mocked(discoveryApi.list).mockImplementation(async()=>({items:[row],total:1,limit:50,offset:0}));
 vi.mocked(discoveryApi.state).mockImplementation(async(_base,_row,state)=>{row={...row,internal_state:state,watching:state==='FOLLOWING',revision:row.revision+1};return row;});
 vi.mocked(monitoringApi.get).mockImplementation(async()=>row);vi.mocked(monitoringApi.preview).mockImplementation(async()=>preview());
 vi.mocked(monitoringApi.summary).mockResolvedValue({new_opportunities:1,changed_opportunities:1,followed_with_changes:0,unread_changes:1,new_documents:1});
 vi.mocked(monitoringApi.history).mockResolvedValue({items:[{id:'change',category:'DOCUMENT_ADDED',origin:'SOURCE',detected_at:'now',summary:'New document available',changed_fields:{},acknowledged_at:null}],total:1,offset:0,limit:100});
 vi.mocked(monitoringApi.handoff).mockImplementation(async()=>{row={...row,internal_state:'IMPORTED',linked_tender:{id:'canonical-tender',available:true}};return {tender_id:'canonical-tender',tender_available:true,already_created:false,documents_status:'COMPLETE_SELECTION',documents:[{source_document_id:'document',status:'IMPORTED'}],analysis_started:false};});
});
it('recorre scan/perfil/follow/detalle/selección/confirmación/Open Tender sin creación automática',async()=>{
 const open=vi.fn();render(<DiscoveryView apiUrl="" onOpenTender={open}/>);fireEvent.click(screen.getByText('Consultar fuentes Discovery'));await screen.findByText('PEMEX público');
 fireEvent.change(screen.getByLabelText('Perfil'),{target:{value:'profile'}});fireEvent.click(screen.getByLabelText('Sólo coincidencias del perfil'));fireEvent.click(screen.getByText('Ejecutar scan manual'));
 await screen.findByText('EVENT');expect(monitoringApi.handoff).not.toHaveBeenCalled();expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({profile_id:'profile',matched_only:true}));
 await waitFor(()=>expect(screen.getByLabelText('Estado interno EVENT')).not.toBeDisabled());fireEvent.change(screen.getByLabelText('Estado interno EVENT'),{target:{value:'FOLLOWING'}});
 await waitFor(()=>expect(discoveryApi.state).toHaveBeenCalled());await waitFor(()=>expect(screen.getByText('Revisar / Create Tender')).not.toBeDisabled());fireEvent.click(screen.getByText('Revisar / Create Tender'));
 await screen.findByText(/New document available/);expect(screen.getByLabelText('Bases.pdf')).not.toBeChecked();expect(screen.getByText('Create Tender',{selector:'button'})).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Bases.pdf'));fireEvent.click(screen.getByLabelText(/Confirmo crear Tender/));fireEvent.click(screen.getByText('Create Tender',{selector:'button'}));
 await screen.findByText(/análisis no iniciado/);await waitFor(()=>expect(screen.getAllByText('Open Tender').length).toBeGreaterThan(0));fireEvent.click(screen.getAllByText('Open Tender')[0]);expect(open).toHaveBeenCalledWith('canonical-tender');expect(monitoringApi.handoff).toHaveBeenCalledTimes(1);
});
it('muestra metadata HTML/script como texto y no construye elementos ejecutables',async()=>{
 row={...row,title:'<script>malicious()</script>',description:'<img src=x onerror=malicious()>'};render(<DiscoveryDetail apiUrl="" id={row.id} onChanged={async()=>{}}/>);
 await screen.findByText('<script>malicious()</script>');expect(screen.getByText('<img src=x onerror=malicious()>')).toBeInTheDocument();expect(document.querySelector('script')).toBeNull();expect(document.querySelector('[onerror]')).toBeNull();expect(monitoringApi.handoff).not.toHaveBeenCalled();
});
