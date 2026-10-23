import { useEffect, useState, type ReactNode } from 'react';
import { Button } from './primitives';
import { type Route, tenderHref, tenderSections } from './routes';
export const destinations = [
  ['inicio', '#/', 'Inicio'], ['discovery', '#/discovery', 'Discovery'],
  ['licitaciones', '#/licitaciones', 'Licitaciones'], ['empresa', '#/mi-empresa', 'Mi empresa'],
  ['reportes', '#/reportes', 'Reportes'], ['configuracion', '#/configuracion', 'Configuración'],
] as const;
export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { setExpanded(false); }, [route.page, route.tenderId, route.section]);
  const active = route.page === 'diagnostico' ? 'configuracion' : route.page;
  return <div className="app-shell">
    <a className="ui-skip" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus(); }}>Saltar al contenido</a>
    <Button className="shell-menu" aria-expanded={expanded} aria-controls="global-sidebar" onClick={() => setExpanded(v => !v)}>Menú</Button>
    <aside id="global-sidebar" className={`global-sidebar ${expanded ? 'is-expanded' : ''}`} onKeyDown={e => { if (e.key === 'Escape') {setExpanded(false); document.querySelector<HTMLButtonElement>('.shell-menu')?.focus();} }}>
      <a className="product-mark" href="#/" aria-label="RX23 TuScope — Inicio"><span>RX23</span><strong>TuScope</strong></a>
      <nav aria-label="Navegación principal"><ul>{destinations.map(([key, href, label]) => <li key={key}><a href={href} aria-current={active === key ? 'page' : undefined} onClick={() => setExpanded(false)}>{label}</a></li>)}</ul></nav>
      <div className="sidebar-utility"><span>Trabajo local</span><a href="#/configuracion/diagnostico" aria-current={route.page === 'diagnostico' ? 'page' : undefined}>Diagnóstico</a></div>
    </aside>
    <main id="main-content" tabIndex={-1} className="main-workspace">{children}</main>
  </div>;
}
export function TenderContextNav({ id, section }: { id: string; section: Route['section'] }) {
  return <nav className="tender-context-nav" aria-label="Secciones de la licitación">{tenderSections.map(([key, label]) => <a key={key} href={tenderHref(id, key)} aria-current={section === key ? 'page' : undefined}>{label}</a>)}</nav>;
}
