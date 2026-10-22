# MVP-08 M8-A — Readiness foundation

Estado: M8-A FUNCTIONALLY ACCEPTED; gate de rendimiento PASS. MVP-07 CLOSED / M7-D ACCEPTED en
`49bc60d2364c17a86347628f945b4fbb227cc593`. [ADR-0026](adr/0026-bid-readiness-foundation.md).

## Inventario canónico consumido

| Dominio | Contrato existente | Uso en M8-A |
| --- | --- | --- |
| Documentos | TenderDocument status/processing_status/is_current, metadata local; Workspace ProcessingRead | Preparación, fallo, cobertura, vigencia y conflicto de nombre persistido |
| Requirements | Workspace.requirements / requirement_matrix, revisión/freshness/effective state | Representación y revisión actuales, sin extracción |
| Requested Evidence | ExpectedEvidence de la matriz, evidence_mode/type, fuente y revisión de su padre | Definición de la solicitud; no cumplimiento ni checklist completo |
| Scope | Workspace.ScopeRead, ScopeReviewItemRead.current, source projection | Aceptación/rechazo/revisión efectiva, identidad y fuente |
| Quantity | Workspace.QuantityRead validado por el lector existente | Parent, fuente, relación EXACT, valor, revisión; sólo lectura |
| Comercial | commercial-readiness-v1 de M7-D | Estado/razones/severidad; sin fórmulas ni acceso a inputs de pricing |
| Human Review | Revisiones de Scope/requisitos/Quantity y estados derivados existentes | Señales pendientes, sin nuevas entidades ni decisiones |
| Source Effects | effective_source_projection | Conflictos/efectos sin resolver, conservando identidad y estado |

El adaptador llama una vez a cada lector Workspace/comercial/Source Effects y carga
metadata documental en lote. No hay un llamado de servicio por issue. Los lectores
conservan validación por Scope pero reciben entradas y proyecciones cargadas en lote,
con reutilización limitada al request. No caché global ni entre consultas. Gate: fixture
2→20 Scope con Quantity, 41→41 SELECTs; salida equivalente y cambios nuevos visibles.
El fixture con Requirements baja de 206 a 64 SELECTs. No se promete O(1) global por
documentos/generaciones diferentes.
No llama a procesar/materializar, providers, OCR, Vision ni interpretación de texto.

## Contrato

`bid-readiness-v1`: Tender ID, status, blocker_count, review_required_count, warning_count,
total_issues, ready_dimensions, incomplete_dimensions, dimensions, items, issues y notice.
Dimensiones: DOCUMENTS, REQUIREMENTS, REQUESTED_EVIDENCE, SCOPE, QUANTITIES, COMMERCIAL,
HUMAN_REVIEW. No dimensión ni regla institucional específica.

Cada ReadinessItem conserva UUID5 estable (Tender/dimensión/tipo/id/código), entidad
original, estado normalizado, severidad opcional, código/resumen, underlying con estado y
razones originales, referencia documento/versión/página/locator/extracto cuando disponible,
review_context y source_module. No copia objetos de dominio completos. Metadata versión
se obtiene del documento del mismo Tender, no de un nombre inferido.

Items contiene también READY/NOT_APPLICABLE; issues sólo señales BLOCKER/REVIEW/WARNING.
Los conteos son señales, no entidades únicas: una revisión puede aparecer en su dimensión
y en HUMAN_REVIEW. IDs y orden son deterministas, sin generated_at volátil ni persistencia
por consulta. Una lectura que falla no retorna una evaluación vacía READY.

## Mapeo y precedencia

- BLOCKED: conflicto/fallo/fuente no disponible, Scope bloqueado/rechazado, Quantity con
  parent/fuente inválidos, conflicto de Source Effects. Severidad BLOCKER.
- INCOMPLETE: preparación no completada/vigente, documentos/Requirements/Scope no observados,
  Quantity faltante/sin valor o relación exacta, razones BLOCKER de comercial. No afirma que
  una obligación exista: informa que la cobertura rastreada no permite concluir readiness.
- REVIEW_REQUIRED: revisión pendiente/stale, requisitos con fuente efectiva ambigua/no
  resuelta o aplicabilidad desconocida, Requested Evidence sin definición/tipo resolubles,
  cantidades pendientes y efectos sin resolver. Severidad REVIEW.
- READY: estado aceptado/satisfecho según contratos consumidos. Warnings se conservan sin
  convertirlo en bloqueo, incluido precio bajo costo.
- NOT_APPLICABLE: revisión documental histórica; requisito superseded o representación
  rechazada con revisión vigente; DIRECT_VERIFICATION sin artefacto; sin revisión pendiente
  entre registros rastreados. No certifica ausencia de obligaciones contractuales.

Precedencia determinista: BLOCKED > INCOMPLETE > REVIEW_REQUIRED > READY.
NOT_APPLICABLE no deteriora dimensiones con registros READY. No porcentajes.
blocker_count incluye faltantes INCOMPLETE y bloqueos BLOCKED; el estado BLOCKED se reserva
para los bloqueos duros descritos. Una lista filtrada no redefine el summary del Tender.

Una aprobación Requirement APPROVED/CURRENT es autoritativa para aceptar representación
con advertencias automáticas: permanecen visibles como WARNING, con estados originales.
No resuelve por sí sola fuente efectiva desconocida/ambigua ni definición/tipo de evidencia
no determinados. Aplicabilidad CONDITIONAL aceptada permanece como warning contextual.

## Requested Evidence y límites de cobertura

Definición extraída no equivale a evidencia entregada, asociación correcta o cumplimiento
empresarial. Siempre se expone TRACKED_REQUESTS_ONLY y notice de responsabilidad humana.
M8-A no selecciona empresa ni evalúa sus evidencias/cumplimiento; no afirma agregar todas
las revisiones de cumplimiento por empresa/alternativa fuera de los contratos consumidos.
No descubre obligaciones faltantes en texto o IR no materializada: ausencia de Scope o
Requirements se expone como cobertura desconocida. Conflictos no persistidos de un upload
sólo existen en su respuesta original; no se inventa un registro histórico para ellos.

READY significa: «Listo sólo según los registros actualmente rastreados por LicitIA».
No es certificación contractual ni garantía de presentación. La revisión humana permanece
autoritativa. Quantity audited editing continúa diferido; confirmar Scope no la confirma.

## API y Workspace

- GET `/tenders/{id}/bid-readiness`: proyección completa y summary canónico.
- GET `/tenders/{id}/bid-readiness/issues`: filtros dimension y severity
  (BLOCKER/REVIEW/WARNING), offset≥0, limit 1–500 (default100), orden estable.
- GET `/tenders/{id}/bid-readiness/dimensions`: estado/conteos por dimensión.

Los tres usan el mismo servicio puro de composición; no cambian fuentes. Tender ajeno
no aporta registros; identidad incompatible falla cerrada. No hay POST/PATCH de readiness.
Workspace añade inspección bajo demanda con overall/conteos/dimensiones/issues y fuentes.
No consulta continua, UI final ni board de prioridades. Se debe volver a consultar después
de cambios. Cambios documentales/refresco de revisión reinician el inspector.

## Límites de MVP-08

M8-A no crea checklist, responsables, fechas, tareas ni overrides de completitud. M8-B
podrá definir seguimiento y decisiones humanas auditadas que no borren el estado canónico.
M8-C: board/filtros/prioridades. M8-D: snapshot/handoff y cierre. Sin ejecución automática
de esos slices ni nueva migración en M8-A (Alembic073), dependencia, cloud o provider.

MVP-09 podrá consultar readiness y la proyección comercial M7-D para identificar filas
actualmente utilizables. M8-A conserva identidad/razones/documentos rastreados; no autoriza
generación, envío, freeze ni propuesta contractual. Snapshot final se difiere a M8-D/MVP-09.
