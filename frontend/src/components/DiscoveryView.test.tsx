import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {vi,describe,it,expect,beforeEach} from 'vitest';
import {SearchProfiles} from './SearchProfiles';
import {DiscoveryView} from './DiscoveryView';
import {discoveryApi} from '../api/discovery';
vi.mock('../api/discovery',()=>({monitoringApi:{summary:vi.fn().mockResolvedValue({new_opportunities:1,changed_opportunities:0,followed_with_changes:0,unread_changes:0,new_documents:0})},discoveryApi:{sources:vi.fn(),profiles:vi.fn(),scans:vi.fn(),scan:vi.fn(),list:vi.fn(),state:vi.fn(),saveProfile:vi.fn(),configure:vi.fn()}}));
const source={id:'PEMEX',name:'PEMEX Concursos Abiertos',enabled:true,last_scan_state:null,last_error:null,areas:[{key:'support',label:'Soporte'}],configuration:{areas:['support']}};
const row={id:'o1',source_id:'PEMEX',external_id:'EVENT-1',procedure_number:'EVENT-1',title:'Válvula',description:'Válvula',business_area:'Soporte',published_date:'2026-10-01',event_type:'Nacional',supply_type:'Bienes',source_status:null,internal_state:'NEW',revision:1,document_count:2,public_url:'https://www.pemex.com/public',first_seen:'2026-10-22',last_seen:'2026-10-22',match:{matched:true,include_hits:[{term:'válvula',matched_text:'Válvula',field:'title',kind:'EXACT'}],exclude_hits:[],restrictions:[]}};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(discoveryApi.sources).mockResolvedValue([source]);vi.mocked(discoveryApi.profiles).mockResolvedValue([]);vi.mocked(discoveryApi.scans).mockResolvedValue([]);vi.mocked(discoveryApi.list).mockResolvedValue({items:[row],total:1,limit:50,offset:0});});
async function open(){render(<DiscoveryView apiUrl=""/>);fireEvent.click(screen.getByText('Actualizar fuentes y perfiles locales'));await screen.findByText('PEMEX Concursos Abiertos');}
describe('Discovery independiente',()=>{
 it('sólo consulta datos locales al montar, sin adquisición pública ni Tender',async()=>{render(<DiscoveryView apiUrl=""/>);await screen.findByText('EVENT-1');expect(discoveryApi.sources).toHaveBeenCalled();expect(discoveryApi.scan).not.toHaveBeenCalled();});
 it('renderiza oportunidades, metadata y explicación local',async()=>{await open();fireEvent.click(screen.getByText('Aplicar filtros'));await screen.findByText('EVENT-1');expect(screen.getByText(/2 referencias descubiertas/)).toBeInTheDocument();expect(screen.getByText(/Coincide: válvula/)).toBeInTheDocument();});
 it('expone PARTIAL y fallo de página sin declararlo completo',async()=>{vi.mocked(discoveryApi.scan).mockResolvedValue({id:'s1',status:'PARTIAL',started_at:'now',metrics:{pages_attempted:3,pages_completed:2,unique_opportunities:100,diagnostics:[{area:'support',code:'ACQUISITION_FAILED',page:3}]}});await open();fireEvent.click(screen.getByText('Consultar fuente'));await screen.findByText(/La consulta fue parcial/,{selector:'strong'});expect(screen.getByText(/La cobertura es incompleta/)).toBeInTheDocument();expect(screen.queryByText(/ACQUISITION_FAILED/)).not.toBeInTheDocument();expect(discoveryApi.scan).toHaveBeenCalledWith('','PEMEX',expect.any(String),expect.objectContaining({areas:['support']}));});
 it('cambia estado interno explícitamente',async()=>{await open();fireEvent.click(screen.getByText('Aplicar filtros'));await screen.findByText('EVENT-1');fireEvent.change(screen.getByLabelText('Estado interno EVENT-1'),{target:{value:'FOLLOWING'}});await waitFor(()=>expect(discoveryApi.state).toHaveBeenCalledWith('',expect.objectContaining({id:'o1'}),'FOLLOWING'));});
 it('muestra fallo y conserva request para retry seguro',async()=>{vi.mocked(discoveryApi.scan).mockRejectedValue(new Error('offline'));await open();fireEvent.click(screen.getByText('Consultar fuente'));await screen.findByRole('alert');const first=vi.mocked(discoveryApi.scan).mock.calls[0][2];fireEvent.click(screen.getByText('Consultar fuente'));await waitFor(()=>expect(discoveryApi.scan).toHaveBeenCalledTimes(2));expect(vi.mocked(discoveryApi.scan).mock.calls[1][2]).toBe(first);});
});

describe('Fuentes M10-B',()=>{
 const cfe={...source,id:'CFE',name:'CFE',areas:[{key:'public',label:'CFE procedimientos públicos'}],configuration:{areas:['public']},capabilities:{automation_status:'AVAILABLE'}};
 const restricted={...cfe,id:'COMPRAS_MX',name:'Compras MX',enabled:false,capabilities:{automation_status:'DEFERRED_SOURCE_AUTOMATION_RESTRICTED',message:'Automatización no disponible actualmente. La fuente restringe el acceso automatizado.'}};
 it('filtra tabla unificada y muestra número humano/área CFE',async()=>{
  vi.mocked(discoveryApi.sources).mockResolvedValue([source,cfe,restricted]);
  vi.mocked(discoveryApi.list).mockResolvedValue({items:[row,{...row,id:'cfe1',source_id:'CFE',external_id:'123',procedure_number:'CFE-HUMAN-123',contracting_area:'Área contratante visible'}],total:2,limit:50,offset:0});
  await open();fireEvent.click(screen.getByText('Aplicar filtros'));
  await screen.findByText('CFE-HUMAN-123');expect(screen.getByText(/Área contratante visible/)).toBeInTheDocument();
  expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({source:undefined}));
  fireEvent.change(screen.getByLabelText('Fuente de oportunidades guardadas'),{target:{value:'CFE'}});
  fireEvent.click(screen.getByText('Aplicar filtros'));
  await waitFor(()=>expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({source:'CFE'})));
 });
 it('scanea CFE y deshabilita la adquisición de Compras MX',async()=>{
  vi.mocked(discoveryApi.sources).mockResolvedValue([source,cfe,restricted]);
  vi.mocked(discoveryApi.scan).mockResolvedValue({id:'cfe',status:'SUCCESS',started_at:'now',metrics:{pages_completed:3}});
  await open();fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'CFE'}});
  await waitFor(()=>expect(screen.getByText('Consultar fuente')).not.toBeDisabled());
  fireEvent.click(screen.getByText('Consultar fuente'));
  await waitFor(()=>expect(discoveryApi.scan).toHaveBeenCalledWith('','CFE',expect.any(String),expect.objectContaining({areas:['public']})));
  await waitFor(()=>expect(screen.getByLabelText('Fuente para consultar')).not.toBeDisabled());
  fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'COMPRAS_MX'}});
  expect(screen.getByText('Automatización no disponible actualmente. La fuente restringe el acceso automatizado.')).toBeInTheDocument();
  expect(screen.queryByText('Consultar fuente')).not.toBeInTheDocument();
  expect(screen.queryByText(/Habilitar fuente/)).not.toBeInTheDocument();
  expect(discoveryApi.scan).toHaveBeenCalledTimes(1);
 });
});

it('no confunde área de adquisición CFE con empresa del perfil',async()=>{
 const cfe={...source,id:'CFE',name:'CFE',areas:[{key:'public',label:'CFE procedimientos públicos'}],configuration:{areas:['public']}};
 vi.mocked(discoveryApi.sources).mockResolvedValue([source,cfe]);
 vi.mocked(discoveryApi.saveProfile).mockResolvedValue({id:'p',name:'Industrial',revision:1,include_keywords:[],exclude_keywords:[],synonyms:{},source_ids:['CFE'],business_areas:[],active:true});
 await open();render(<SearchProfiles apiUrl=""/>);await screen.findByLabelText('Restringir perfil a CFE');fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'CFE'}});
 fireEvent.change(screen.getByLabelText('Nombre del perfil'),{target:{value:'Industrial'}});
 fireEvent.click(screen.getByLabelText('Restringir perfil a CFE'));
 fireEvent.click(screen.getByText('Guardar perfil'));
 await waitFor(()=>expect(discoveryApi.saveProfile).toHaveBeenCalledWith('',expect.objectContaining({source_ids:['CFE'],business_areas:[]}),undefined,undefined));
});

it('conserva perfil con varias fuentes al cambiar fuente de adquisición',async()=>{
 const cfe={...source,id:'CFE',name:'CFE',areas:[{key:'public',label:'CFE procedimientos públicos'}],configuration:{areas:['public']}};
 const profile={id:'multi',name:'Compartido',revision:2,include_keywords:['válvula'],exclude_keywords:[],synonyms:{},source_ids:['PEMEX','CFE'],business_areas:['CFE Empresa Sintética'],active:true};
 vi.mocked(discoveryApi.sources).mockResolvedValue([source,cfe]);vi.mocked(discoveryApi.profiles).mockResolvedValue([profile]);vi.mocked(discoveryApi.saveProfile).mockResolvedValue({...profile,revision:3});
 await open();render(<SearchProfiles apiUrl=""/>);await screen.findByLabelText('Restringir perfil a CFE');fireEvent.change(screen.getByLabelText('Editar perfil'),{target:{value:'multi'}});
 expect(screen.getByLabelText('Restringir perfil a PEMEX')).toBeChecked();expect(screen.getByLabelText('Restringir perfil a CFE')).toBeChecked();
 fireEvent.change(screen.getByLabelText('Fuente para consultar'),{target:{value:'CFE'}});fireEvent.click(screen.getByText('Guardar perfil'));
 await waitFor(()=>expect(discoveryApi.saveProfile).toHaveBeenCalledWith('',expect.objectContaining({source_ids:['PEMEX','CFE'],business_areas:['CFE Empresa Sintética']}),'multi',2));
});

it('restringe handoff según capability de cualquier fuente, sin depender del nombre institucional',async()=>{
 const deferred={...source,id:'SYNTHETIC_RESTRICTED',name:'Fuente restringida sintética',capabilities:{automation_status:'DEFERRED_SOURCE_AUTOMATION_RESTRICTED'}};
 vi.mocked(discoveryApi.sources).mockResolvedValue([source,deferred]);vi.mocked(discoveryApi.list).mockResolvedValue({items:[{...row,source_id:deferred.id}],total:1,limit:50,offset:0});
 await open();fireEvent.click(screen.getByText('Aplicar filtros'));await screen.findByText('EVENT-1');expect(screen.getByText('Revisar')).toBeDisabled();
});

it('combina Following con cambios e Imported y abre únicamente el Tender vinculado',async()=>{
 const onOpen=vi.fn();vi.mocked(discoveryApi.list).mockResolvedValue({items:[{...row,internal_state:'IMPORTED',watching:true,unread_document_changes:1,linked_tender:{id:'canonical-t',available:true}}],total:1,limit:50,offset:0});
 render(<DiscoveryView apiUrl="" onOpenTender={onOpen}/>);fireEvent.click(screen.getByText('Actualizar fuentes y perfiles locales'));await screen.findByText('PEMEX Concursos Abiertos');
 fireEvent.click(screen.getByLabelText('Siguiendo'));fireEvent.click(screen.getByLabelText('Cambios sin leer'));fireEvent.change(screen.getByLabelText('Estado interno'),{target:{value:'IMPORTED'}});
 fireEvent.click(screen.getByText('Aplicar filtros'));await screen.findByText('EVENT-1');expect(discoveryApi.list).toHaveBeenLastCalledWith('',expect.objectContaining({following:true,unread_only:true,internal_state:'IMPORTED'}));
 expect(screen.getByLabelText('Estado interno EVENT-1')).toBeDisabled();fireEvent.click(screen.getByText('Abrir licitación'));expect(onOpen).toHaveBeenCalledWith('canonical-t');expect(screen.getByText(/1 documentales/)).toBeInTheDocument();
});
