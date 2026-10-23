import { useCallback, useEffect, useRef, useState } from 'react';
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
  const contextChange = useCallback((value: WorkspaceContext | null) => setContext(value), []);
  const openTender = useCallback((id: string) => { window.location.hash = tenderHref(id); }, []);
  useEffect(() => {
    const update = () => {
      const next = readRoute(window.location.hash);
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
    if (!route.section) return;
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
  const tender = route.tenderId && context?.id === route.tenderId ? context : null;
  const workspaceVisible = route.page === 'licitaciones' || route.page === 'diagnostico';
  const workspaceVisited = visited.has('licitaciones') || visited.has('diagnostico');
  return <AppShell route={route}>
    <PageHeader title={tender ? tender.title : titles[route.page]} context={tender ? <>{tender.reference || 'Sin referencia'} · {tender.status === 'DRAFT' ? 'Borrador' : tender.status === 'ACTIVE' ? 'Activa' : tender.status === 'ARCHIVED' ? 'Archivada' : 'Estado por revisar'}</> : undefined} />
    {route.tenderId && <><TenderContextNav id={route.tenderId} section={route.section} /><Notice>Consulta los documentos y resultados del expediente. La revisión y las decisiones finales permanecen bajo tu control.</Notice>{!tender && (availability === "error" ? <ErrorState /> : availability === "loading" ? <LoadingState>Consultando la licitación…</LoadingState> : <EmptyState title="La licitación no está disponible" action={<a href="#/licitaciones">Elegir otra licitación</a>}>Verifica que siga disponible en este equipo.</EmptyState>)}</>}
    {route.page === 'inicio' && <EmptyState title="Continúa tu trabajo" action={<a className="ui-button ui-button--primary" href="#/licitaciones">Abrir licitaciones</a>}>Puedes trabajar con tus expedientes o consultar oportunidades públicas en Discovery. Elige una licitación para continuar con sus documentos y pendientes.</EmptyState>}
    {visited.has('discovery') && <div hidden={route.page !== 'discovery'}><DiscoveryView apiUrl={API_URL} onOpenTender={openTender} /></div>}
    {visited.has('empresa') && <div hidden={route.page !== 'empresa'}><CompanyEvidenceLibrary apiUrl={API_URL} /></div>}
    {route.page === 'reportes' && <EmptyState title="Los archivos se generan en cada licitación" action={<a href="#/licitaciones">Elegir licitación</a>}>Usa Comercial para sus archivos de intercambio y Propuesta para DOCX, XLSX, PDF o ZIP. No hay un reporte global habilitado.</EmptyState>}
    {route.page === 'configuracion' && <section className="ui-surface"><h2>Herramientas locales</h2><p>La configuración de fuentes y consultas permanece en Discovery durante esta transición.</p><a href="#/discovery">Abrir Discovery</a><p><a href="#/configuracion/diagnostico">Abrir diagnóstico del expediente</a></p><p>Las copias de seguridad y restauraciones se administran con las herramientas locales documentadas. Esta pantalla no modifica la base de datos.</p></section>}
    {route.page === 'diagnostico' && <Notice>Vista técnica existente del expediente. Selecciona una licitación para consultar fuentes, versiones, lectura y auditorías. Los análisis requieren una acción explícita.</Notice>}
    {route.page === 'not-found' && <EmptyState title="Esta dirección no está disponible" action={<a href="#/">Volver a Inicio</a>}>Usa la navegación para elegir una sección del producto.</EmptyState>}
    {workspaceVisited && <div id="legacy-content" hidden={!workspaceVisible}><Workspace embedded requestedTenderId={route.tenderId ?? context?.id} onTenderOpen={openTender} onContext={contextChange} onAvailability={setAvailability} /></div>}
    {route.page === 'licitaciones' && !route.tenderId && context && <p><a href={tenderHref(context.id)}>Continuar en {context.title}</a></p>}
    {route.tenderId && <p className="ui-secondary">Sección: {tenderSections.find(([key]) => key === route.section)?.[1]} · <a href="#/licitaciones">Cambiar licitación</a> · <a href="#/configuracion/diagnostico">Diagnóstico</a></p>}
  </AppShell>;
}
