# M9-C — Proposal Document Exports

Implementación para revisión arquitectónica; MVP-09 permanece abierto. M9-B aceptado y
comprometido en `ba2e1437d72753292e88990ec61622da7753bc4b`. [ADR-0031](adr/0031-proposal-document-exports.md).

## Contrato y autoridad

`proposal-export-v1` recibe una ProposalVersion explícita: snapshot verificado, composición
materializada, respuestas y configuración preservadas. Los renderers sólo reciben un DTO
externo tipado, sin Session ni consulta a datos comerciales/requisitos actuales. No hay LLM.
Los literales ausentes en históricos legacy fallan cerrados; se necesita una nueva revisión.
Exportar no muta ProposalVersion, snapshot ni dominios MVP-06/07/08.

FROZEN permite export oficial; DRAFT requiere consentimiento explícito y revisiones esperadas,
con etiqueta DRAFT visible en DOCX/XLSX/PDF. Un archivo ya generado conserva su estado original.
Freshness actual se consulta separadamente en Workspace: STALE no cambia el snapshot exportado.
El manifiesto conserva estado al freeze y declara que no reevalúa freshness.

## Formatos y seguridad

DOCX: títulos/tablas editables, orden e inclusión configurados, referencias humanas y metadata.
XLSX: Summary, hojas por sección y _Metadata oculta; no es el round-trip comercial M7-C.
PDF: ReportLab y fuente Vera distribuida localmente; paginación automática y escape de texto.
ZIP: formatos seleccionados más manifest.json; nunca originales del expediente.

Economía externa incluye cantidad/unidad/precio ofrecido/total/moneda preservados, sin recalcular.
Monedas se mantienen separadas. Allowlist excluye costo, margen, markup y notas comerciales o
económicas internas. Respuestas técnicas humanas son contenido intencional de propuesta;
el usuario debe revisarlas antes de compartir. No se implementa clasificación semántica de secretos.

Texto XLSX se escribe como string explícito; prefijos de fórmula quedan neutralizados.
No macros, fórmulas calculadas, links externos DOCX ni recursos remotos PDF. Valores numéricos
Excel que no preservan exactamente su precisión se escriben como texto. No truncamiento silencioso:
32767 caracteres por celda; hasta 10000 filas y 64 MiB de contenido; glifos PDF no soportados fallan.
Layout neutral, sin branding final ni plantillas ejecutables del usuario.

## Storage, historia e integridad

`storage/proposal-exports-v1/<TenderUUID>/<VersionUUID>/<RequestUUID>/` bajo el data root
estricto. Directorios 0700/archivos 0600; UUID y nombres estáticos, symlinks/path escape rechazados.
La descarga usa nombre saneado. Manifest envelope SHA-256 fija DTO semántico, IDs, fecha,
versiones de contrato, composición, snapshot y hashes/tamaños de formatos. Receipt externo fija
hash del ZIP y manifiesto sin autorreferencia. Integridad no equivale a firma digital.

Request UUID + digest de parámetros permite retry idempotente: mismo request devuelve los
mismos archivos verificados; payload distinto se rechaza. Nuevo UUID crea otra entrada histórica.
Lock por versión, temporales privados, fsync y publicación atómica conservan exports previos
ante fallo. No hay eliminación/retención automática; administrador protege y conserva artifacts.
No migración078: metadatos y binarios derivados viven juntos en filesystem, respaldados por
RC-H3 junto con storage. Restore E2E verifica metadata, binarios y literales FROZEN.
La regeneración conserva semántica; no se promete igualdad binaria entre nuevas generaciones.

## API y Workspace

Base: `/tenders/{tender_id}/proposal-versions/{version_id}/exports`.
POST genera; GET lista paginada (20, máximo50). `/{request_id}` obtiene metadata;
`/{request_id}/verify` POST verifica; `/{request_id}/files/{artifact_type}` descarga tras verificar.
Errores explícitos por revisión obsoleta, fuente histórica incompleta, biblioteca ausente,
render inválido, integridad o almacenamiento. Acceso cruzado de Tender se rechaza.

Workspace permite elegir formatos/ZIP, consentir DRAFT, generar, reintentar respuesta perdida,
consultar historia/verificación y descargar. Requiere composición cargada/guardada; no oculta
cambios sin guardar. No auth nueva: sigue el límite de UAT local controlado.

## Validación

Pruebas reales de tres writers, inyección/path safety, ausencia de costos internos, congelamiento,
mutación posterior de Requirement/Evidence, retry/tampering y restore aislado. Medición de
Tender sintético: 7 SELECT pequeños y 7 con 182 Scope/181 Requirements/181 Evidence/182 líneas
económicas; no SQL N+1. Evidencia reproducible en `backend/reports/m9_c/`.
