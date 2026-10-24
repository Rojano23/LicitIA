export const tenderSections = [
  ['resumen', 'Resumen'], ['documentos', 'Documentos'], ['requisitos', 'Requisitos'],
  ['cumplimiento', 'Cumplimiento'], ['partidas', 'Partidas'], ['comercial', 'Comercial'],
  ['preparacion', 'Preparación de oferta'], ['propuesta', 'Propuesta'],
] as const;
export type TenderSection = typeof tenderSections[number][0];
export type Route = { page: 'inicio' | 'discovery' | 'licitaciones' | 'empresa' | 'reportes' | 'configuracion' | 'diagnostico' | 'not-found'; tenderId?: string; section?: TenderSection; view?:string; opportunityId?:string; scanId?:string; scanSource?:string };
export function readRoute(hash: string): Route {
  const [path,query] = (hash.replace(/^#/, '') || '/').split('?');
  if(path==='/discovery'&&query){const q=new URLSearchParams(query);return {page:'discovery',view:q.get('view')??'all',opportunityId:q.get('opportunity')??undefined,scanId:q.get('scan')??undefined,scanSource:q.get('source')??undefined};}
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
