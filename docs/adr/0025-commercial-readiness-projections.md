# ADR-0025 — M7-D: completitud comercial y contratos de lectura

Estado: aceptado arquitectónicamente — M7-D ACCEPTED. Base M7-C `d22cf3e`.

Un resultado comercial canónico READY/INCOMPLETE/REVIEW_REQUIRED con razones tipadas
BLOCKER/REVIEW/WARNING sustituye la promoción indiscriminada de warnings a revisión.
Falta de línea/precio/moneda/Quantity es incompletitud. Fuente/Quantity pendiente,
contexto cambiado, precio calculado obsoleto y valores negativos requieren revisión.
Pérdida, costo desconocido con precio manual, cero y referencia de cotización ausente
son advertencias; no se exige cotización a fuentes internas/fabricante/manuales.
COST_FIRST sin decisión manual requiere costo/regla válidos. Precio manual explícito
puede ser usable sin costo; no se fabrican ratios. La falta de cálculo recomendado
con precio manual se expone como warning. No se añade aceptación/edición de Quantity.

El mismo evaluador puro se usa en cálculo, composición comercial y matriz; no camino
separado para XLSX/CSV/bulk. Lecturas de readiness y propuesta consumen esa composición.
MVP-08 recibe identidad, estado, razones, warnings y presencia de precio/fuente; no inputs
ni algoritmos de pricing. MVP-09 sólo filas READY con Quantity canónica y precio/moneda,
notas/estado/warnings, sin costos internos ni auditoría. Resumen mantiene monedas separadas.
No filas se consideran listas por el mero hecho de existir un precio.

Readiness no incorpora previews spreadsheet no aplicados: sus conflictos son resultados
de esa operación, no hechos comerciales persistidos. Apply rechazado no deteriora una
decisión canónica vigente. Contexto/precio obsoleto persistido sí exige revisión.

Auditoría GET paginada (1–100, before_revision) sobre revisiones append-only existentes:
inputs actuales, eventos con diffs antes/después, origen, actor declarado opcional,
notas, precio manual/recomendación histórica y evidencia hash del import cuando exista.
No reinterpretar cálculo histórico con reglas nuevas. Scope retirado conserva historial;
no se reatacha por texto. Sin nuevas tablas, migración, dependencias ni proveedores.

Se difiere bid freeze/locking a MVP-08/09. Referencia SHA-256 determinista del estado leído
(revisiones/fingerprints/inputs y resultado comercial) permite detectar cambios; no garantiza
snapshot transaccional de todo Tender ni sustituye un futuro freeze. Consultas son puras.
UI provisional muestra razones/resumen e historial bajo demanda, sin dashboard final.
