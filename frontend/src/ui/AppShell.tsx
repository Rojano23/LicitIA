import { useEffect, useState, type ReactNode } from 'react';
import { Button } from './primitives';
import { type Route, tenderHref, tenderSections } from './routes';
export const destinations = [
  ['inicio', '#/', 'Inicio'], ['discovery', '#/discovery', 'Discovery'],
  ['licitaciones', '#/licitaciones', 'Licitaciones'], ['empresa', '#/mi-empresa', 'Mi empresa'],
  ['reportes', '#/reportes', 'Reportes'], ['configuracion', '#/configuracion', 'Configuración'],
] as const;
export const sidebarPreferenceKey = 'tuscope.sidebar.desktop';
function savedCollapsed() {
  try { return window.localStorage.getItem(sidebarPreferenceKey) === 'collapsed'; }
  catch { return false; }
}
/** Native SVG primitives: no font, external asset, or icon dependency. */
function NavigationIcon({name}:{name:string}) {
 const paths:Record<string,string>={
  inicio:'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
  discovery:'M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm6-2 6 6',
  licitaciones:'M3 7h7l2-3h9v17H3ZM3 8h18',
  empresa:'M4 21V5h12v16M8 9h4M8 13h4M8 17h4M16 11h4v10M2 21h20',
  reportes:'M5 2h10l4 4v16H5ZM14 2v5h5M8 17v-4m4 4V9m4 8v-6',
  configuracion:'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6',
  diagnostico:'M3 4h18v16H3ZM6 8l4 4-4 4m6 0h6',
  collapse:'m14 6-6 6 6 6',expand:'m10 6 6 6-6 6',
 };
 return <svg className="navigation-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={paths[name]}/></svg>;
}
export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const [collapsed,setCollapsed] = useState(savedCollapsed);
  useEffect(() => { setExpanded(false); }, [route.page, route.tenderId, route.section]);
  function toggleDesktop() {
    const next=!collapsed;
    setCollapsed(next);
    try { window.localStorage.setItem(sidebarPreferenceKey,next?'collapsed':'expanded'); }
    catch { /* Storage can be unavailable; the current presentation still works. */ }
  }
  const active = route.page === 'diagnostico' ? 'configuracion' : route.page;
  return <div className={`app-shell${collapsed?' is-sidebar-collapsed':''}`}>
    <a className="ui-skip" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus(); }}>Saltar al contenido</a>
    <Button className="shell-menu" aria-expanded={expanded} aria-controls="global-sidebar" onClick={() => setExpanded(v => !v)}>Menú</Button>
    <aside id="global-sidebar" className={`global-sidebar ${expanded ? 'is-expanded' : ''}`} onKeyDown={e => { if (e.key === 'Escape') {setExpanded(false); document.querySelector<HTMLButtonElement>('.shell-menu')?.focus();} }}>
      <a className="product-mark" href="#/" aria-label="RX23 TuScope — Inicio"><span>RX23</span><strong>TuScope</strong></a>
      <Button className="sidebar-toggle" aria-label={collapsed?'Expandir menú':'Contraer menú'} title={collapsed?'Expandir menú':'Contraer menú'} aria-expanded={!collapsed} aria-controls="global-sidebar" onClick={toggleDesktop}><NavigationIcon name={collapsed?'expand':'collapse'}/><span className="sidebar-label">Contraer menú</span></Button>
      <nav aria-label="Navegación principal"><ul>{destinations.map(([key, href, label]) => <li key={key}><a href={href} aria-label={label} title={label} aria-current={active === key ? 'page' : undefined} onClick={() => setExpanded(false)}><NavigationIcon name={key}/><span className="sidebar-label">{label}</span></a></li>)}</ul></nav>
      <div className="sidebar-utility"><span className="sidebar-section-label">Trabajo local</span><a href="#/configuracion/diagnostico" aria-label="Diagnóstico" title="Diagnóstico" aria-current={route.page === 'diagnostico' ? 'page' : undefined}><NavigationIcon name="diagnostico"/><span className="sidebar-label">Diagnóstico</span></a></div>
    </aside>
    <main id="main-content" tabIndex={-1} className="main-workspace">{children}</main>
  </div>;
}
export function TenderContextNav({ id, section }: { id: string; section: Route['section'] }) {
  return <nav className="tender-context-nav" aria-label="Secciones de la licitación">{tenderSections.map(([key, label]) => <a key={key} href={tenderHref(id, key)} aria-current={section === key ? 'page' : undefined}>{label}</a>)}</nav>;
}
