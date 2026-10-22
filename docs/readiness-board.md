# MVP-08 M8-C — Board operacional provisional

M8-B aceptado y comprometido en `db3325c3e201123ef8f54045e484f2a6328969fa`.
M8-C implementado para revisión; sin stage/commit/push. Sin nueva migración: head074.

## Contrato y autoridades

GET `/tenders/{id}/readiness-board` compone M8-A y M8-B una vez por request.
`canonical_summary` mantiene exactamente status/conteos M8-A; `work_summary` reutiliza
M8-B y agrega in_review. `dimensions` contiene estado canónico y conteos de bloqueos,
revisión, advertencias y trabajo abierto. Filtros no alteran estos totales del Tender.
`bucket_counts` cuenta todo el conjunto rastreado, incluida historia anotada; la lista
por defecto sólo presenta activos. Resueltos sin anotación no se inventan ni persisten.
No porcentaje contractual ni nuevo estado global del Workspace.

Cada fila lleva WorkItem M8-B (identidad, entidad, estado/severidad canónicos, referencia
fuente, workflow, nota, stale), bucket, prioridad y targets de contexto/fuente.
No copia objetos completos de dominio ni crea filas al leer. Reutiliza el único overlay
agrupado y batch request-local, sin caché global ni query por ítem.

## Prioridad y secciones

Orden determinista: BLOCKED/BLOCKER (0), REVIEW (1), INCOMPLETE/BLOCKER (2), WARNING (3),
aceptados/resueltos (4); después dimensión canónica, tipo/id entidad, código/UUID.
Secciones: BLOCKERS, REVIEW_REQUIRED, IN_PROGRESS, ATTENTION, ACCEPTED_RISKS, RESOLVED.
IN_REVIEW en WARNING aparece IN_PROGRESS; en blocker/review conserva su sección fuente
más urgente y muestra actividad IN_REVIEW. Cierre manual de blocker/review mantiene la
sección canónica. Riesgo/no aplicable sólo WARNING conforme M8-B, visible en ACCEPTED_RISKS.
RESOLVED manual de WARNING cierra actividad; no borra la advertencia canónica.
RESOLVED_BY_SOURCE_CHANGE/OBSOLETE pasan a RESOLVED e historial sólo lectura.

## Consulta acotada

Filtros tipados: dimension (las siete M8-A), severity BLOCKER/REVIEW/WARNING,
workflow_status (los cinco M8-B), bucket, include_inactive=false. search≤200 busca resumen,
código, dimensión, entidad/reference local; sin indexado documental/full-text.
offset≥0, limit1–200/default50. Pagina después de composición para preservar agregados,
no renderiza todo el Tender. Computación/memoria sigue proporcional al conjunto canónico;
no certifica miles de documentos/generaciones. Prueba sintética100 Scope con Quantity
propia valida cientos de señales, paginación sin solapamientos y crecimiento SQL acotado.

## Targets y cambios

Scope/Human Review Scope → scope-review existente. Quantity → Scope padre explícito en
underlying.scope_id, nunca al UUID Quantity como si fuera Scope. Comercial → commercial-line
por Scope. Requirement/Evidence → requirement-matrix con fragmento UUID y entidad visible;
es contexto API, no pantalla nueva ni deep-link con resaltado automático. Documento fuente
→ content local, página cuando existe. Otros → contexto canónico M8-A. No inventa source
cuando falta ni adquiere percepción. Workspace abre contexto/fuente locales en nueva pestaña.

Board no tiene endpoint de mutación. WorkRow reutiliza PATCH/history M8-B, expectativas
revision/hash y política de riesgo. Las ediciones fuente se hacen en su módulo canónico.
No modifica precios, Requirements, Scope, Quantity, documentos ni provenance.
Reconciliación/fingerprint M8-B intactos: cambio en otra partida puede reabrir actividad;
nota/historia permanecen, stale visible, riesgo anterior no se transporta silenciosamente.

## Workspace y alcance

Vista a demanda con status/conteos fuente, actividad separada, tabla de dimensiones,
filtros, lista priorizada y paginación50. Reutiliza controles humanos existentes.
Guardar borradores antes de consultar/cambiar filtros; no hay guardado automático.
Riesgos visibles, historial accesible, estado stale explícito. Sin porcentaje de cumplimiento:
se muestran conteos de trabajo resuelto por fuente/aceptado, no certificación.
MVP-09 debe consumir M8-A + M7-D, nunca actividades cerradas como datos de propuesta.
No freeze, propuesta, auth/roles, notificaciones, scheduling, prioridad manual/IA,
UI final, rediseño global ni nuevas semánticas documentales/comerciales.

M8-D recomendado: cierre de contratos y revisión de handoff read-only M8-A/M7-D para MVP-09,
validación de invariantes/gates, evidencia y límites operacionales; cualquier snapshot/freeze
persistente requiere diseño y aceptación explícitos antes de implementación.
