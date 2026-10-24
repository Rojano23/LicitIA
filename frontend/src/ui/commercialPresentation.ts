/** Presentation only: no pricing, aggregation, or eligibility calculations. */
const words:Readonly<Record<string,string>>={
 MXN:'MXN',USD:'USD',EUR:'EUR',NOT_REQUIRED:'Sin revisión requerida',
 SUPPLIER_QUOTE:'Cotización de proveedor',INTERNAL_COST:'Costo interno',MANUFACTURER_COST:'Costo de fabricante',HISTORICAL_REFERENCE:'Referencia histórica',ESTIMATE:'Estimación',MANUAL:'Captura manual',NOT_APPLICABLE:'No aplica',
 CONFIRMED_QUOTE:'Cotización confirmada',HISTORICAL_COST:'Costo histórico',SYSTEM_ESTIMATE:'Estimación del sistema',MANUAL_INPUT:'Captura humana',CALCULATED:'Calculado',
 COMPLETE:'Completa',COMPLETE_WITH_REVIEW:'Completa con revisión',VERIFIED_AT_CREATION:'Integridad verificada al generar',READY:'Listo',INCOMPLETE:'Incompleto',REVIEW_REQUIRED:'Requiere revisión',BLOCKED:'Bloqueado',WARNING:'Advertencia',REVIEW:'Revisión',BLOCKER:'Bloqueo',
 DRAFT:'Borrador',FROZEN:'Congelada',CURRENT:'Sin cambios al consultar',STALE:'Hay cambios posteriores',SOURCE_SNAPSHOT_STALE:'Hay cambios posteriores al estado usado para esta versión',
 DOCUMENTS:'Documentos',REQUIREMENTS:'Requisitos',REQUESTED_EVIDENCE:'Evidencia solicitada',SCOPE:'Partidas',QUANTITIES:'Cantidades',COMMERCIAL:'Comercial',HUMAN_REVIEW:'Revisión humana',
 BLOCKERS:'Bloqueos',IN_PROGRESS:'En curso',ATTENTION:'Requiere atención',ACCEPTED_RISKS:'Riesgos aceptados',RESOLVED:'Resuelto',OPEN:'Pendiente',IN_REVIEW:'En revisión',ACCEPTED_RISK:'Riesgo aceptado',
 ELIGIBLE:'Elegible para captura',ELIGIBLE_WITH_WARNINGS:'Elegible con advertencias',NOT_ELIGIBLE:'Aún no elegible',PRICE_FIRST:'Precio primero',COST_FIRST:'Costo primero',MARKUP:'Markup',MARGIN:'Margen',
 ALL:'Todas',MISSING_COST:'Sin costo',MISSING_PRICE:'Sin precio',UNSPECIFIED:'Sin moneda',PATCH:'Actualizar campos',RECALCULATE:'Recalcular',COPY_SETTINGS:'Copiar ajustes',INITIALIZE:'Inicializar',
 IDENTIFICATION:'Identificación',TECHNICAL_SCOPE:'Alcance técnico',ECONOMIC:'Oferta económica',CLARIFICATION:'Aclaración',EXCLUSION:'Exclusión',ASSUMPTION:'Supuesto',DEVIATION:'Desviación',NOTE:'Nota',ANNEX_REFERENCE:'Referencia de anexo',
 PENDING:'Pendiente',COMPLY:'Declaro cumplimiento',PARTIAL:'Parcial',PROVIDED:'Presentada',EXCEPTION:'Excepción',MATCHED:'Fuente coincidente',UNCHANGED:'Sin cambios',CHANGED:'Fuente modificada',VERIFIED:'Verificado',FAILED:'Falló',UI:'Workspace',API:'API',XLSX_IMPORT:'Importado de Excel',CSV_IMPORT:'Importado de CSV',
};
export const commercialLabel=(value:string|null|undefined)=>value?words[value]??'Revisar detalle técnico':'Sin definir';
/** Decimal strings stay strings: format without binary floating point or rounding. */
export function money(value:string|null|undefined,currency:string|null|undefined){
 if(value==null)return 'Sin resolver';
 if(!/^-?\d+(\.\d+)?$/.test(value))return 'Importe por revisar';
 const [integer,fraction='']=value.split('.');
 return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g,',')}.${fraction.padEnd(2,'0')} ${currency??'sin moneda'}`;
}
export const areaSection=(dimension:string)=>({DOCUMENTS:'documentos',REQUIREMENTS:'requisitos',REQUESTED_EVIDENCE:'cumplimiento',SCOPE:'partidas',QUANTITIES:'partidas',COMMERCIAL:'comercial',HUMAN_REVIEW:'partidas'}[dimension]??'resumen');
