export const tenderSections = [
  ['resumen', 'Resumen'], ['documentos', 'Documentos'], ['requisitos', 'Requisitos'],
  ['cumplimiento', 'Cumplimiento'], ['partidas', 'Partidas'], ['comercial', 'Comercial'],
  ['preparacion', 'Preparación de oferta'], ['propuesta', 'Propuesta'],
] as const;
export type TenderSection = typeof tenderSections[number][0];
export type Route = { page: 'inicio' | 'discovery' | 'licitaciones' | 'empresa' | 'reportes' | 'configuracion' | 'diagnostico' | 'not-found'; tenderId?: string; section?: TenderSection };
export function readRoute(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/';
  const pages: Record<string, Route['page']> = { '/': 'inicio', '/discovery': 'discovery', '/licitaciones': 'licitaciones', '/mi-empresa': 'empresa', '/reportes': 'reportes', '/configuracion': 'configuracion', '/configuracion/diagnostico': 'diagnostico' };
  if (pages[path]) return { page: pages[path] };
  const match = /^\/licitaciones\/([^/]+)\/(\w+)$/.exec(path);
  if (match && tenderSections.some(([key]) => key === match[2])) {
    try { return { page: 'licitaciones', tenderId: decodeURIComponent(match[1]), section: match[2] as TenderSection }; }
    catch { return { page: 'not-found' }; }
  }
  return { page: 'not-found' };
}
export const tenderHref = (id: string, section: TenderSection = 'resumen') => `#/licitaciones/${encodeURIComponent(id)}/${section}`;
