/** Presentation only: no pricing, aggregation, or eligibility calculations. */
const words:Readonly<Record<string,string>>={
 cost_source_type:'Fuente de costo',currency:'Moneda',calculation_mode:'Modo de cálculo',reference_party_name:'Parte de referencia',UPDATED:'Actualizada',PROTECTED:'Protegido',NOT_REQUESTED:'Sin cambio solicitado',MANUAL_PRICE_PROTECTED:'Precio manual protegido',COMMERCIAL_CONTEXT_STALE:'La información comercial cambió; vuelve a consultar',PRICE_BELOW_COST:'Precio por debajo del costo',MISSING_OFFERED_PRICE:'Falta el precio ofrecido',MISSING_UNIT_COST:'Falta el costo unitario',MISSING_CURRENCY:'Falta la moneda',CONFIRMED:'Confirmado',CREATE:'Creación',UPDATE:'Actualización',BULK:'Edición en lote',CREATED:'Creada',CONFIG_UPDATED:'Configuración actualizada',FROZEN_VERSION:'Versión congelada',
 unit_cost:'Costo unitario',offered_unit_price:'Precio unitario ofrecido',markup_percent:'Markup objetivo',target_margin_percent:'Margen objetivo',notes:'Notas',calculation_basis:'Regla de cálculo',quantity_id:'Cantidad seleccionada',cost_value_origin:'Origen del costo',quote_reference:'Referencia de cotización',quote_document_id:'Documento de cotización',XLSX:'Excel',CSV:'CSV',ELIGIBLE_WITH_REVIEW:'Elegible con revisión',INVALID:'No válido',SKIPPED:'Omitido',NOT_APPLIED:'Sin aplicar',APPLIED:'Aplicado',NO_CHANGE:'Sin cambios',
 quantity:'Cantidad',REFERENCE_FIELDS_MODIFIED:'Se modificaron referencias del expediente; no se aplicarán',
 MXN:'MXN',USD:'USD',EUR:'EUR',NOT_REQUIRED:'Sin revisión requerida',
 SUPPLIER_QUOTE:'Cotización de proveedor',INTERNAL_COST:'Costo interno',MANUFACTURER_COST:'Costo de fabricante',HISTORICAL_REFERENCE:'Referencia histórica',ESTIMATE:'Estimación',MANUAL:'Captura manual',NOT_APPLICABLE:'No aplica',
 CONFIRMED_QUOTE:'Cotización confirmada',HISTORICAL_COST:'Costo histórico',SYSTEM_ESTIMATE:'Estimación del sistema',MANUAL_INPUT:'Captura humana',CALCULATED:'Calculado',
 COMPLETE:'Completa',COMPLETE_WITH_REVIEW:'Completa con revisión',VERIFIED_AT_CREATION:'Integridad verificada al generar',READY:'Listo',INCOMPLETE:'Incompleto',REVIEW_REQUIRED:'Requiere revisión',BLOCKED:'Bloqueado',WARNING:'Advertencia',REVIEW:'Revisión',BLOCKER:'Bloqueo',
 DRAFT:'Borrador',FROZEN:'Versión congelada',CURRENT:'Sin cambios al consultar',STALE:'Hay cambios posteriores',SOURCE_SNAPSHOT_STALE:'Hay cambios posteriores al estado usado para esta versión',
 DOCUMENTS:'Documentos',REQUIREMENTS:'Requisitos',REQUESTED_EVIDENCE:'Evidencia solicitada',SCOPE:'Partidas',QUANTITIES:'Cantidades',COMMERCIAL:'Comercial',HUMAN_REVIEW:'Revisión humana',
 BLOCKERS:'Bloqueos',IN_PROGRESS:'En curso',ATTENTION:'Requiere atención',ACCEPTED_RISKS:'Riesgos aceptados',RESOLVED:'Resuelto',OPEN:'Pendiente',IN_REVIEW:'En revisión',ACCEPTED_RISK:'Riesgo aceptado',
 ELIGIBLE:'Elegible para captura',ELIGIBLE_WITH_WARNINGS:'Elegible con advertencias',NOT_ELIGIBLE:'Aún no elegible',PRICE_FIRST:'Precio primero',COST_FIRST:'Costo primero',MARKUP:'Markup',MARGIN:'Margen',
 ALL:'Todas',MISSING_COST:'Sin costo',MISSING_PRICE:'Sin precio',UNSPECIFIED:'Sin moneda',PATCH:'Actualizar campos',RECALCULATE:'Recalcular',COPY_SETTINGS:'Copiar ajustes',INITIALIZE:'Inicializar',
 IDENTIFICATION:'Identificación',TECHNICAL_SCOPE:'Alcance técnico',ECONOMIC:'Oferta económica',CLARIFICATION:'Aclaración',EXCLUSION:'Exclusión',ASSUMPTION:'Supuesto',DEVIATION:'Desviación',NOTE:'Nota',ANNEX_REFERENCE:'Referencia de anexo',
 PENDING:'Pendiente',COMPLY:'Declaro cumplimiento',PARTIAL:'Parcial',PROVIDED:'Presentada',EXCEPTION:'Excepción',MATCHED:'Fuente coincidente',UNCHANGED:'Sin cambios',CHANGED:'Fuente modificada',VERIFIED:'Verificado',FAILED:'Falló',UI:'Edición en pantalla',API:'API',XLSX_IMPORT:'Importado de Excel',CSV_IMPORT:'Importado de CSV',
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
