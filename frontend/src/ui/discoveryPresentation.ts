import type { Match } from '../api/discovery';
export const workflowLabels: Record<string, string> = {NEW:'Nueva',REVIEW:'En revisión',FOLLOWING:'Siguiendo',DISCARDED:'Descartada',IMPORTED:'Licitación creada'};
export const scanLabels: Record<string, string> = {SUCCESS:'Consulta completada',PARTIAL:'La consulta fue parcial',FAILED:'No se completó la consulta',RUNNING:'Consulta en curso'};
export const changeLabels: Record<string, string> = {NEW_OPPORTUNITY:'Nueva oportunidad detectada',METADATA_CHANGED:'Información actualizada',SOURCE_STATUS_CHANGED:'Cambió el estado publicado',DOCUMENT_ADDED:'Nuevo documento disponible',DOCUMENT_CHANGED:'Cambió un documento',DOCUMENT_REMOVED:'Referencia documental retirada',NO_LONGER_OBSERVED:'Ya no se observa en el mismo filtro',REAPPEARED:'Volvió a aparecer',WORKFLOW_CHANGED:'Decisión de seguimiento',CHANGE_ACKNOWLEDGED:'Cambios marcados como revisados',TENDER_CREATED:'Licitación creada',DOCUMENT_IMPORTED:'Documento importado'};
export function matchLabel(match: Match | null) {
 if(!match) return 'Sin perfil seleccionado';
 if(match.exclude_hits.length) return `Excluida: ${match.exclude_hits.map(h=>h.term).join(', ')}`;
 if(!match.matched) return 'Sin coincidencia';
 const terms=[...new Set(match.include_hits.map(h=>h.term))];
 return terms.length ? `Coincide: ${terms.join(', ')}` : 'Coincide con las condiciones del perfil';
}
export const sourceName = (id:string) => id === 'COMPRAS_MX' ? 'Compras MX' : id;
export function displayDate(value:string|null|undefined) {const date=value?new Date(value.length===10?value+'T12:00:00':value):null;return date&&!Number.isNaN(date.getTime())?new Intl.DateTimeFormat('es-MX',{dateStyle:'medium'}).format(date):'Sin fecha';}

export function changeDocumentName(fields:Record<string,unknown>):string|null{
 const document=fields.document;
 const name=document&&typeof document==='object'&&!Array.isArray(document)?(document as Record<string,unknown>).name:fields.name;
 return typeof name==='string'&&name.length<=1000?name:null;
}
