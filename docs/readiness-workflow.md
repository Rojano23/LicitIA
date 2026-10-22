# MVP-08 M8-B — trabajo de readiness y decisiones humanas

Aceptado arquitectónicamente; commit `db3325c3e201123ef8f54045e484f2a6328969fa`, sin push. Base M8-A
`8431338f7004911c625a713bd9429be92ee7d03f`, con gate de rendimiento PASS.
[ADR-0027](adr/0027-readiness-workflow.md) documenta esquema e inventario antes de074.

## Fuente y actividad son ejes separados

M8-A responde qué está/no está listo. M8-B muestra qué está haciendo una persona al
respecto. Leer no crea work items persistidos: cada issue M8-A aparece con su mismo UUID,
dimensión, entidad y contexto. Se persiste sólo una decisión humana cuando alguien actúa.
Ni notas ni workflow recalculan precios, modifican documentos o aceptan evidencia fuente.
MVP-09 debe consumir readiness canónico y las proyecciones M7-D; no inferir elegibilidad
porque todas las actividades se hayan marcado RESOLVED.

OPEN, IN_REVIEW, RESOLVED, ACCEPTED_RISK y NOT_APPLICABLE describen actividad. Dos últimas
sólo se admiten para WARNING; REVIEW admite anotación/revisión/cierre de actividad, no una
exención de su incertidumbre. BLOCKER no puede aceptarse como riesgo/no aplicable. Puede
registrarse RESOLVED como declaración de actividad, pero canonical_blocker_remains y
blockers_open siguen reflejando el problema fuente; no se hace READY por ese clic.

ACCEPTED_RISK no borra advertencia, ni certifica/legaliza cumplimiento. Ejemplo: precio
bajo costo sigue en M8-A; M8-B conserva decisión, nota opcional y fecha. Notas≤4000,
owner/actor≤200, texto libre declarado sin autenticación ni gestión de identidades.
No fechas, scheduling, prioridades manuales o suite de colaboración.

## Persistencia y auditoría

Alembic074 agrega sólo readiness_work_decisions sobre073. Eventos append-only, UUID,
Tender, issue UUID, revisión positiva única por Tender/issue, descriptor mínimo de
identidad, hash de contexto y campos humanos. Trigger impide UPDATE/DELETE. No copia
Scope, Requirement, Quantity, precios, documentos ni estado fuente. No nueva tabla
genérica de revisiones: los subsistemas previos conservan sus decisiones autoritativas.
FK Tender RESTRICT conserva auditoría. Downgrade administrativo elimina esta tabla/historia;
no ejecutarlo en bases históricas. Se probó074 en licitia_test; desarrollo no se migró.
Backups PostgreSQL existentes incluyen esta tabla sin nuevo filesystem.

Actualización bloquea identidad Tender y verifica expected_revision/expected_context_sha256.
Conflicto devuelve409; no sobrescribe una decisión nueva. Operación equivalente con revisión
vigente no agrega evento. El actor no se hereda silenciosamente si no fue declarado en
la nueva acción. Historial consulta25 eventos (máximo100) descendentes, before_revision.

## Reconciliación derivada

ACTIVE: issue sigue presente. RESOLVED_BY_SOURCE_CHANGE: desaparece y la entidad todavía
está rastreada; p.ej. se agrega precio en M7 y desaparece MISSING_OFFERED_PRICE.
OBSOLETE: ya no existe la entidad rastreada. No se insertan cierres automáticos al leer;
historia y notas se conservan. Ítems inactivos son sólo consulta y no aceptan escritura.

Fingerprint del contexto canónico completo del Tender (M8-A + representaciones de requisitos
+ state reference comercial) invalida conservadoramente decisiones ante cambios de fuente.
Si un issue aún existe y el hash cambió, annotation_stale=true, workflow efectivo OPEN;
recorded_workflow_status y notas permanecen. Una modificación en otra partida también
puede volver stale la actividad: límite conservador explícito de este slice, no rebase
ni transporte silencioso de ACCEPTED_RISK. Notas de M8-B no cambian ese contexto.
No es snapshot transaccional/freeze de propuesta.

## API

- GET `/tenders/{id}/readiness-work`: canonical_summary separado de work_summary, items y
  total_filtered; dimension/severity/workflow_status/include_inactive, offset≥0,
  limit1–200(default50). Blocker→Review→Warning, después identidad estable.
- GET `/tenders/{id}/readiness-work/summary`: ambos resúmenes sin lista.
- GET `/tenders/{id}/readiness-work/{issue_id}`: activo o histórico anotado.
- PATCH en misma ruta: expectativas, workflow_status opcional, note/owner/actor_label.
- GET `.../{issue_id}/history`: limit1–100/default25 y before_revision.

No endpoints de completar Scope/Quantity/Requirement desde work items. Items desconocidos,
fuera del Tender o de contexto anterior fallan cerrados. Historial de otro Tender no
se devuelve. Filtros no recalculan ni ocultan el summary canónico.

Work summary: total_active, total_open, blockers_open, review_items_open, accepted_risks,
resolved, obsolete, manually_closed_activity, stale_annotations. Total_open incluye todo
blocker activo incluso si actividad humana está RESOLVED. Resolved se reserva para fuente
resuelta; manually_closed_activity es un conteo distinto. Señales pueden referirse a la
misma entidad en diferentes dimensiones, como M8-A; no son un score contractual.

## Rendimiento e interfaz

Reutiliza un contexto de carga por lote M8-A por request; Workspace/comercial/proyecciones
no se cargan por fila. Overlay actual se lee en una consulta agrupada (DISTINCT ON issue).
Sin caché global, jobs o inserciones de sincronización al consultar.
Workspace provisional muestra fuente vs actividad, severidad, entidad, nota, actor/owner,
acción relacionada, historial y paginación. Mostrar/guardar requiere acción explícita;
volver a consultar tras cambios. Sin dashboard final ni rediseño.

M8-C recomendado: board interno con filtros por dimensión/severidad/lifecycle/actividad,
prioridad derivada de severidad, navegación contextual y presentación clara de stale;
sin nuevo motor de prioridades, project management, edición Quantity o freeze/propuesta.
