import {RequirementsView} from './components/RequirementsView';
import {ComplianceView} from './components/ComplianceView';
import {ItemsView} from './components/ItemsView';
import { useCallback, useEffect, useRef, useState } from 'react';
import {InicioView} from './components/InicioView';
import {TenderListView,TenderProductWorkspace} from './components/TenderProductViews';
import type {Tender} from './api/tenders';
import Workspace, { type WorkspaceContext } from './App';
import { CompanyEvidenceLibrary } from './components/CompanyEvidenceLibrary';
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
  const listVisited = useRef(false);
  if(route.page==='licitaciones'&&!route.tenderId)listVisited.current=true;
  const [productTender,setProductTender]=useState<WorkspaceContext|null>(null);
  const coreRoute = useRef<{id:string;section:string;documentId?:string;pageNumber?:number}|null>(null);
  const legacyId = useRef<string|undefined>(undefined);
  const isCore = route.page === 'licitaciones' && !!route.tenderId && (['resumen','documentos','requisitos','cumplimiento','partidas'].includes(route.section??''));
  const engineeringVisited=useRef<{tenderId:string;sections:Set<string>}>({tenderId:'',sections:new Set()});
  if(isCore&&route.tenderId){if(engineeringVisited.current.tenderId!==route.tenderId)engineeringVisited.current={tenderId:route.tenderId,sections:new Set()};if(['requisitos','cumplimiento','partidas'].includes(route.section??''))engineeringVisited.current.sections.add(route.section!);}
  const isLegacy = route.page === 'diagnostico' || route.page === 'licitaciones' && !!route.tenderId && !isCore;
  if(isCore)coreRoute.current={id:route.tenderId!,section:route.section!,documentId:route.documentId,pageNumber:route.pageNumber};
  if(isLegacy){legacyVisited.current=true;if(route.tenderId)legacyId.current=route.tenderId;else if(coreRoute.current)legacyId.current=coreRoute.current.id;}
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
    if (!route.section || ['resumen','documentos','requisitos','cumplimiento','partidas'].includes(route.section)) return;
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
  const workspaceVisible = isLegacy;
  const workspaceVisited = legacyVisited.current;
  return <AppShell route={route}>
    <PageHeader title={tender ? tender.title : titles[route.page]} context={tender ? <>{tender.reference || 'Sin referencia'} · {tender.status === 'DRAFT' ? 'Borrador' : tender.status === 'ACTIVE' ? 'Activa' : tender.status === 'ARCHIVED' ? 'Archivada' : 'Estado por revisar'}</> : undefined} />
    {route.tenderId && <><TenderContextNav id={route.tenderId} section={route.section} /><Notice>Consulta los documentos y resultados del expediente. La revisión y las decisiones finales permanecen bajo tu control.</Notice>{!tender && !isCore && (availability === "error" ? <ErrorState /> : availability === "loading" ? <LoadingState>Consultando la licitación…</LoadingState> : <EmptyState title="La licitación no está disponible" action={<a href="#/licitaciones">Elegir otra licitación</a>}>Verifica que siga disponible en este equipo.</EmptyState>)}</>}
    {listVisited.current && <div hidden={route.page!=='licitaciones'||!!route.tenderId}><TenderListView apiUrl={API_URL} onOpen={openTender}/></div>}
    {coreRoute.current && <div hidden={!isCore}><TenderProductWorkspace key={coreRoute.current.id} apiUrl={API_URL} tenderId={coreRoute.current.id} section={coreRoute.current.section} documentId={coreRoute.current.documentId} pageNumber={coreRoute.current.pageNumber} active={isCore&&route.section==='documentos'} onContext={productContext}/></div>}
    {engineeringVisited.current.sections.has('requisitos')&&<div className="engineering-route" hidden={!isCore||route.section!=='requisitos'}><RequirementsView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId} initialRequirement={route.requirementId}/></div>}
    {engineeringVisited.current.sections.has('cumplimiento')&&<div className="engineering-route" hidden={!isCore||route.section!=='cumplimiento'}><ComplianceView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId} initialRequirement={route.requirementId}/></div>}
    {engineeringVisited.current.sections.has('partidas')&&<div className="engineering-route" hidden={!isCore||route.section!=='partidas'}><ItemsView key={engineeringVisited.current.tenderId} apiUrl={API_URL} tenderId={engineeringVisited.current.tenderId}/></div>}
    {route.page === 'inicio' && <InicioView apiUrl={API_URL}/>}
    {visited.has('discovery') && <div hidden={route.page !== 'discovery'}><DiscoveryView apiUrl={API_URL} onOpenTender={openTender} view={discoveryRoute.current.view} opportunityId={discoveryRoute.current.opportunityId} scanId={discoveryRoute.current.scanId} scanSource={discoveryRoute.current.scanSource} filterRequest={discoveryRoute.current} /></div>}
    {visited.has('empresa') && <div hidden={route.page !== 'empresa'}><CompanyEvidenceLibrary apiUrl={API_URL} /></div>}
    {route.page === 'reportes' && <EmptyState title="Los archivos se generan en cada licitación" action={<a href="#/licitaciones">Elegir licitación</a>}>Usa Comercial para sus archivos de intercambio y Propuesta para DOCX, XLSX, PDF o ZIP. No hay un reporte global habilitado.</EmptyState>}
    {route.page === 'configuracion' && <section className="ui-surface"><h2>Herramientas locales</h2><p>La configuración de fuentes y consultas permanece en Discovery durante esta transición.</p><a href="#/discovery">Abrir Discovery</a><p><a href="#/configuracion/diagnostico">Abrir diagnóstico del expediente</a></p><p>Las copias de seguridad y restauraciones se administran con las herramientas locales documentadas. Esta pantalla no modifica la base de datos.</p></section>}
    {route.page === 'diagnostico' && <Notice>Vista técnica existente del expediente. Selecciona una licitación para consultar fuentes, versiones, lectura y auditorías. Los análisis requieren una acción explícita.</Notice>}
    {route.page === 'not-found' && <EmptyState title="Esta dirección no está disponible" action={<a href="#/">Volver a Inicio</a>}>Usa la navegación para elegir una sección del producto.</EmptyState>}
    {workspaceVisited && <div id="legacy-content" hidden={!workspaceVisible}><Workspace embedded processingActive={workspaceVisible} requestedTenderId={legacyId.current ?? context?.id} onTenderOpen={openTender} onContext={contextChange} onAvailability={setAvailability} /></div>}
    {route.page === 'licitaciones' && !route.tenderId && context && <p><a href={tenderHref(context.id)}>Continuar en {context.title}</a></p>}
    {route.tenderId && <p className="ui-secondary">Sección: {tenderSections.find(([key]) => key === route.section)?.[1]} · <a href="#/licitaciones">Cambiar licitación</a> · <a href="#/configuracion/diagnostico">Diagnóstico</a></p>}
  </AppShell>;
}
