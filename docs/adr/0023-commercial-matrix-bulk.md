# ADR-0023 — M7-B: matriz comercial y acciones por lote

Estado: aceptado arquitectónicamente — M7-B ACCEPTED. Base M7-A `6d30509`.

## Decisión

Sin migración, nuevas dependencias ni cambios semánticos MVP-06. La matriz incluye todos
los Scope actuales del Tender, con fila virtual INCOMPLETE si no hay CommercialLine.
Consulta no crea líneas. Las líneas archivadas se listan separadamente, sin totales.
Prelectura conjunta de Scope/Quantity, identidades y última revisión; no cargar historia
comercial por fila. Validación de revisión/provenance reutiliza lectores canónicos y
mantiene sus consultas internas por Scope (limitación explícita, no promesa de O(1)).

Bulk máximo 100 IDs únicos: preview puro por defecto; aplicación explícita, revisión y
fingerprint esperados por fila, incluso para filas virtuales. Savepoint por fila para
errores esperados; commit exterior de resultados válidos. Error inesperado revierte el
request completo. Locks en orden de Scope para serializar creación concurrente. No jobs,
colas ni persistencia de selección. Repetir ajustes equivalentes con expectativas vigentes
no agrega revisiones; reenviar expectativas viejas devuelve stale sin sobrescribir.

Acciones PATCH, MARKUP, MARGIN, RECALCULATE, COPY_SETTINGS e INITIALIZE. Markup/margen
establecen COST_FIRST y su basis; sólo aplican precio cuando hay recomendación y no está
protegido, o replace_manual_price explícito. Precio manual prevalece; modo/reglas cambian
sin borrar precio. Outcome distingue ajustes y resultado de precio (protegido/sin resolver/
recalculado), sin ocultar filas omitidas. Moneda cambia denominación sin FX/número nuevo;
si hay importes requiere confirm_currency_change. Copia sólo reglas/fuente/parte/moneda,
no costo/precio/notas/Quantity/quote. Fuente de copia también exige expectativas vigentes.

Defaults de sesión React por Tender, no almacenamiento persistente ni pricing engine.
Sólo moneda/modo/basis/markup/margen; se validan con M7-A. No sobrescriben líneas existentes.
Edición por fila usa row_changes explícito (costo/precio/notas incluidos). Los borradores
pueden aplicarse juntos con una regla compartida; los cambios comunes prevalecen en los
mismos campos. No es una copia implícita de decisiones monetarias. Los borradores de filas
no seleccionadas o fallidas se conservan en UI; refrescar descartándolos pide confirmación.

Auditoría usa revisiones existentes: action BULK_WORKSPACE/BULK_API, input UI/API, metadatos
de operación en calculation_snapshot (UUID, acción, fecha, IDs solicitados, campos,
antes/después). No editar revisiones insertadas. Los cambios de precio calculado retienen
CALCULATED/SYSTEM_ESTIMATE; precio editado explícitamente es MANUAL/MANUAL_INPUT.

Resumen por moneda, sin gran total mixto: sumas parciales y conteos calculables/faltantes
para costo/oferta/utilidad; subtotal nunca se etiqueta como total completo si faltan filas.
Markup/margen globales sólo sobre pares costo/oferta completos, con cobertura explícita.
Estado/cantidad de warnings y precio/costo resueltos forman DTO consumible por MVP-08,
sin implementar Bid Readiness. UI HTML/React provisional con selección visible/filtrada,
Tab nativo y Enter para previsualizar fila; no motor de spreadsheet ni export/import.

## Referencias OSS

[TanStack Table v8 row selection](https://raw.githubusercontent.com/TanStack/table/v8/docs/guide/row-selection.md)
([MIT](https://raw.githubusercontent.com/TanStack/table/main/LICENSE)): referencia para
selección local por UUID y selección de filas filtradas, sin adoptar dependencia/código.
[SQLAlchemy SAVEPOINT](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint):
patrón de aislamiento por fila sobre la dependencia existente. Precisión/money/audit
siguen ADR-0022, sin nuevos formatos monetarios ni proveedores.
