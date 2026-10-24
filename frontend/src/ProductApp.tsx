import type {ImportSession} from './components/expedienteSelection';
import {CompanyView} from './components/CompanyView';
import {ReportsView} from './components/ReportsView';
import {SettingsView} from './components/SettingsView';
import {DiagnosticsView} from './components/DiagnosticsView';
import {CommercialView} from "./components/CommercialView";
import {ReadinessView} from "./components/ReadinessView";
import {ProposalVersions} from "./components/ProposalVersions";
import {RequirementsView} from './components/RequirementsView';
import {ComplianceView} from './components/ComplianceView';
import {ItemsView} from './components/ItemsView';
import { useCallback, useEffect, useRef, useState } from 'react';
import {InicioView} from './components/InicioView';
import {TenderListView,TenderProductWorkspace} from './components/TenderProductViews';
import type {Tender} from './api/tenders';
import type { WorkspaceContext } from './App';
import {DeferredWorkspace} from './ui/DeferredWorkspace';
import { DiscoveryView } from './components/DiscoveryView';
import { AppShell, TenderContextNav } from './ui/AppShell';
import { EmptyState, ErrorState, LoadingState, Notice, PageHeader } from './ui/primitives';
import { readRoute, tenderHref, tenderSections } from './ui/routes';
import './ui/shell.css';
const API_URL = 'http://localhost:8000';
const titles = { inicio: 'Inicio', discovery: 'Discovery', licitaciones: 'Licitaciones', empresa: 'Mi empresa', reportes: 'Reportes', configuracion: 'Configuración', diagnostico: 'Diagnóstico', 'not-found': 'Página no encontrada' };
export default function ProductApp() {
  const [route, setRoute] = useState(() => readRoute(window.location.hash));
  const [availability, setAvailability] = useState<"loading" | "ready" | "error">("loading");
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [visited, setVisited] = useState(() => new Set([route.page]));
  const previous = useRef(route);
  const acceptedHash = useRef(window.location.hash);
  const legacyVisited = useRef(false);
  const [diagnosticToolsOpened,setDiagnosticToolsOpened]=useState(false);
  const listVisited = useRef(false);
  if(route.page==='licitaciones'&&!route.tenderId)listVisited.current=true;
  const [importSession,setImportSession]=useState<ImportSession|undefined>();
  useEffect(()=>{
    if(!importSession)return;
    const guard=(event:Event)=>{
      const next=(event as CustomEvent<{tenderId?:string}>).detail.tenderId;
      if(next===importSession.tenderId||event.defaultPrevented)return;
      if(!window.confirm('La licitación ya está creada, pero sus archivos aún no se han enviado. ¿Salir y descartar esta selección? La licitación se conserva.'))event.preventDefault();
      else setImportSession(undefined);
    };
    const unload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
    window.addEventListener('tuscope:navigate',guard);window.addEventListener('beforeunload',unload);
    return()=>{window.removeEventListener('tuscope:navigate',guard);window.removeEventListener('beforeunload',unload);};
  },[importSession]);
  const [productTender,setProductTender]=useState<WorkspaceContext|null>(null);
  const coreRoute = useRef<{id:string;section:string;documentId?:string;pageNumber?:number}|null>(null);
  const legacyId = useRef<string|undefined>(undefined);
  const isCore = route.page === 'licitaciones' && !!route.tenderId && (['resumen','documentos','requisitos','cumplimiento','partidas','comercial','preparacion','propuesta'].includes(route.section??''));
  const engineeringVisited=useRef<{tenderId:string;sections:Set<string>}>({tenderId:'',sections:new Set()});
  if(isCore&&route.tenderId){if(engineeringVisited.current.tenderId!==route.tenderId)engineeringVisited.current={tenderId:route.tenderId,sections:new Set()};if(['requisitos','cumplimiento','partidas','comercial','preparacion','propuesta'].includes(route.section??''))engineeringVisited.current.sections.add(route.section!);}
  const isLegacy = route.page === 'diagnostico' || route.page === 'licitaciones' && !!route.tenderId && !isCore;
  if(isCore)coreRoute.current={id:route.tenderId!,section:route.section!,documentId:route.documentId,pageNumber:route.pageNumber};
  if(isLegacy&&diagnosticToolsOpened){legacyVisited.current=true;if(route.tenderId)legacyId.current=route.tenderId;else if(coreRoute.current)legacyId.current=coreRoute.current.id;}
  const productContext = useCallback((value:Tender|null)=>{if(value)window.localStorage.setItem('licitia_selected_tender_id',value.id);setProductTender(value?{id:value.id,title:value.title,reference:value.external_reference,status:value.status}:null);},[]);
  const discoveryRoute = useRef(route);
  if(route.page==='discovery')discoveryRoute.current=route;
  const contextChange = useCallback((value: WorkspaceContext | null) => setContext(value), []);
  const openTender = useCallback((id: string) => { window.location.hash = tenderHref(id); }, []);
  useEffect(() => {
    const update = () => {
      const next = readRoute(window.location.hash);
      const navigation=new CustomEvent('tuscope:navigate',{cancelable:true,detail:{tenderId:next.tenderId}});
      if(!window.dispatchEvent(navigation)){window.history.replaceState(null,'',acceptedHash.current||'#/');return;}
      acceptedHash.current=window.location.hash;
      if (next.page !== 'not-found') setVisited(old => new Set([...old, next.page]));
      setRoute(next);
    };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  useEffect(() => {
    document.title = 'RX23 TuScope';
    if (previous.current !== route) document.getElementById('page-title')?.focus();
    previous.current = route;
    if (!route.section || ['resumen','documentos','requisitos','cumplimiento','partidas','comercial','preparacion','propuesta'].includes(route.section)) return;
    // Transitional sections keep the existing workspace mounted: navigation never reruns a pipeline.
    const seek = () => {
      const target = document.getElementById(`workspace-${route.section}`);
      if (!target) return false;
      let parent = target.parentElement;
      while (parent) { if (parent instanceof HTMLDetailsElement) parent.open = true; parent = parent.parentElement; }
      target.scrollIntoView?.({ block: 'start' });
      return true;
    };
    if (seek()) return;
    const observer = new MutationObserver(() => { if (seek()) observer.disconnect(); });
    const content = document.getElementById('legacy-content');
    if (content) observer.observe(content, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [route]);
  const selectedContext = isCore ? productTender : context;
  const tender = route.tenderId && selectedContext?.id === route.tenderId ? selectedContext : null;
  const workspaceVisible = isLegacy&&diagnosticToolsOpened;
  const workspaceVisited = legacyVisited.current;
  return <AppShell route={route}>
    <PageHeader title={tender ? tender.title : titles[route.page]} context={tender ? <>{tender.reference || 'Sin referencia'} · {tender.status === 'DRAFT' ? 'Borrador' : tender.status === 'ACTIVE' ? 'Activa' : tender.status === 'ARCHIVED' ? 'Archivada' : 'Estado por revisar'}</> : undefined} />
    {route.tenderId && <><TenderContextNav id={route.tenderId} section={route.section} /><Notice>Consulta los documentos y resultados del expediente. La revisión y las decisiones finales permanecen bajo tu control.</Notice>{!tender && !isCore && (availability === "error" ? <ErrorState /> : availability === "loading" ? <LoadingState>Consultando la licitación…</LoadingState> : <EmptyState title="La licitación no está disponible" action={<a href="#/licitaciones">Elegir otra licitación</a>}>Verifica que siga disponible en este equipo.</EmptyState>)}</>}
    {listVisited.current && <div hidden={route.page!=='licitaciones'||!!route.tenderId}><TenderListView apiUrl={API_URL} onOpen={openTender} onCreated={(t,session)=>{setImportSession(session);window.location.hash=tenderHref(t.id,session?'documentos':'resumen');}}/></div>}
    {coreRoute.current && <div hidden={!isCore}><TenderProductWorkspace importSession={importSession?.tenderId===coreRoute.current.id?importSession:undefined} onImportAccepted={()=>setImportSession(undefined)} key={coreRoute.current.id} apiUrl={API_URL} tenderId={coreRoute.current.id} section={coreRoute.current.section} documentId={coreRoute.current.documentId} pageNumber={coreRoute.current.pageNumber} active={isCore&&route.section==='documentos'} onContext={productContext}/></div>}
    {engineeringVisited.current.sections.has('requisitos')&&<div className="engineering-route" hidden={!isCore||route.section!=='requisitos'}><RequirementsView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId} initialRequirement={route.requirementId}/></div>}
    {engineeringVisited.current.sections.has('cumplimiento')&&<div className="engineering-route" hidden={!isCore||route.section!=='cumplimiento'}><ComplianceView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId} initialRequirement={route.requirementId}/></div>}
    {engineeringVisited.current.sections.has('partidas')&&<div className="engineering-route" hidden={!isCore||route.section!=='partidas'}><ItemsView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId}/></div>}
    {engineeringVisited.current.sections.has('comercial')&&<div hidden={!isCore||route.section!=='comercial'}><CommercialView initialScope={route.scopeId} key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId}/></div>}
    {engineeringVisited.current.sections.has('preparacion')&&<div hidden={!isCore||route.section!=='preparacion'}><ReadinessView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId}/></div>}
    {engineeringVisited.current.sections.has('propuesta')&&<div className="proposal-product" hidden={!isCore||route.section!=='propuesta'}><ProposalVersions key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId} disabled={false} product/></div>}
    {route.page === 'inicio' && <InicioView apiUrl={API_URL}/>}
    {visited.has('discovery') && <div hidden={route.page !== 'discovery'}><DiscoveryView apiUrl={API_URL} onOpenTender={openTender} view={discoveryRoute.current.view} opportunityId={discoveryRoute.current.opportunityId} scanId={discoveryRoute.current.scanId} scanSource={discoveryRoute.current.scanSource} filterRequest={discoveryRoute.current} /></div>}
    {visited.has('empresa') && <div hidden={route.page !== 'empresa'}><CompanyView embedded apiUrl={API_URL} /></div>}
    {visited.has('reportes')&&<div hidden={route.page!=='reportes'}><ReportsView embedded apiUrl={API_URL}/></div>}
    {visited.has('configuracion')&&<div hidden={route.page!=='configuracion'}><SettingsView embedded apiUrl={API_URL}/></div>}
    {visited.has('diagnostico')&&<div hidden={route.page!=='diagnostico'}><DiagnosticsView embedded apiUrl={API_URL} toolsOpened={diagnosticToolsOpened} onOpenTools={()=>setDiagnosticToolsOpened(v=>!v)}/></div>}
    {route.page === 'not-found' && <EmptyState title="Esta dirección no está disponible" action={<a href="#/">Volver a Inicio</a>}>Usa la navegación para elegir una sección del producto.</EmptyState>}
    {workspaceVisited && <div id="legacy-content" hidden={!workspaceVisible}><DeferredWorkspace embedded processingActive={workspaceVisible} requestedTenderId={legacyId.current ?? context?.id} onTenderOpen={openTender} onContext={contextChange} onAvailability={setAvailability} /></div>}
    {route.page === 'licitaciones' && !route.tenderId && context && <p><a href={tenderHref(context.id)}>Continuar en {context.title}</a></p>}
    {route.tenderId && <p className="ui-secondary">Sección: {tenderSections.find(([key]) => key === route.section)?.[1]} · <a href="#/licitaciones">Cambiar licitación</a> · <a href="#/configuracion/diagnostico">Diagnóstico</a></p>}
  </AppShell>;
}
