# MVP-08 M8-D — snapshot de readiness y handoff MVP-09

MVP-08 CLOSED — M8-D ACCEPTED; commit `2bcd556b6b785412a5cf24b81d2ccac770e995a4`, sin push. [ADR-0028](adr/0028-proposal-readiness-snapshot.md)
documentó el esquema antes de075. M8-C ACCEPTED, commit748dda6.

## Qué significa preparado

MVP-08 responde qué falta en los registros actuales antes de preparar propuesta. No
certifica legalidad, cumplimiento contractual, completitud documental ni conveniencia
BID/NO BID. La revisión humana sigue autoritativa y los originales inmutables.
M8-A conserva readiness; M8-B conserva actividad; M8-C prioriza; M8-D preserva el handoff.

ProposalReadinessProjection `proposal-readiness-v1` contiene Tender/id/título, status M8-A,
elegibilidad, blockers/reviews/warnings, riesgos aceptados y workflow activo anotado,
filas elegibles M7-D con Scope/Quantity/CommercialLine, precio ofertado/total/moneda,
origen económico y método del precio conservados de MVP-07,
descripción y referencias fuente. Conserva contexto rastreado de las siete dimensiones,
identidad de representación de Requirement, IDs/estado Requested Evidence, metadata/hash/
revisión documental. No costos, cotizaciones completas, margen/markup, documentos binarios
ni texto completo. Referencias incluyen página/locator y hash del fragmento cuando existe.

- NOT_ELIGIBLE: blocker M8-A, o ausencia de filas sin una revisión que explique exclusión.
- REVIEW_REQUIRED: revisión M8-A pendiente o fila comercial excluida por revisión; separado
  de blocker. Política de este handoff exige resolverla antes de crear snapshot preparado.
- ELIGIBLE_WITH_WARNINGS: datos esenciales y revisión fuente preparados, warnings presentes.
- ELIGIBLE: misma condición sin warnings.

M8-A conserva Warning permanente de cobertura no certificada; por ello la fixture completa
actual resulta ELIGIBLE_WITH_WARNINGS. No se oculta para fabricar ELIGIBLE.
Faltante precio/moneda/Quantity, padre roto, Scope ausente o conflicto bloqueante no se
sobrepasan con RESOLVED/ACCEPTED_RISK humanos. Se reutiliza elegibilidad de filas M7-D,
sin inventar reglas de contratación. Quantity permanece sólo lectura: faltante/errónea
requiere corregir fuente o revisión autoritativa fuera de este slice, no bypass snapshot.

## Snapshot explícito e íntegro

`proposal-readiness-snapshot-v1` preserva proyección, UUID snapshot/Tender/request, fechaUTC,
actor declarado opcional, confirmación warnings, input_sha256, request_sha256, schema075 y
application_contract `licitia-mvp08-v1`. No se afirma identidad Git de código sin commit.
Metadata relacional + payload JSON versionado, FK Tender RESTRICT, unique(Tender,request),
índice historial, trigger impide UPDATE/DELETE. No ProposalVersion. Downgrade administrativo
elimina esta historia; no es acción UI. Tabla incluida automáticamente en pg_dump RC-H3.

POST exige expected_input_sha256 de evaluación reciente y UUID request. Warnings/riesgos
requieren acknowledge_warnings=true explícito. NOT_ELIGIBLE/REVIEW_REQUIRED rechazan409
sin crear snapshot preparado. Expected hash antiguo→409. Leer/evaluar no crea snapshots.
Idempotencia: mismo request con mismo body normalizado retorna mismo snapshot incluso si
fuente cambió tras perder respuesta; body diferente409. Nuevo UUID es acción nueva y puede
crear otro snapshot con el mismo input hash. Unique evita duplicados concurrentes; conflicto
23505/40001/40P01 devuelve409 para retry explícito de la misma solicitud. Otros errores de DB
se propagan. UI conserva solicitud pendiente al fallar; volver a evaluar inicia acción nueva.

SHA256 de JSON canónico UTF8 (sort_keys, separadores estables, sin NaN) incluye todo envelope.
Verificación tipada comprueba hash, estado/fingerprint, ownership Scope→Quantity→Tender y
consistencia de metadata relacional. Falla cerrada409 por payload corrupto/incompatible.
Es integridad, no firma ni autenticación. Persona con control total de DB puede recalcular
hashes; proteger backups/DB conforme procedimiento local aceptado.

## Consistencia y CURRENT/STALE

Requests de preparación usan sesión PostgreSQL REPEATABLE READ propia, con vista MVCC
consistente y sin bloquear edición de fuentes. Fuente puede cambiar después del snapshot;
CURRENT significa equivalente a la vista actual evaluada, no bloqueo o promesa futura.
GET handoff sólo verifica/devuelve snapshot almacenado: nunca consulta fuentes para cambiar
su contenido. Freshness se consulta aparte y compara fingerprint relevante; no actualiza
snapshot ni devuelve CURRENT si no se pudo evaluar fuente.

Input hash cubre proyección relevante: estado/issues/ref/identidades, Scope/Quantity/precios/
moneda, fuentes/hash/revisión documental, representación de requisitos, workflow/nota/riesgo.
Excluye hora, estado UI, fingerprints opacos de costo y revisión comercial puramente técnica.
Se conserva commercial_revision en payload para auditoría, pero no en fingerprint relevante:
un cambio sólo de costo/contacto que deja iguales las señales/valores de propuesta no vuelve
STALE. Un costo sí puede cambiar warning o freshness conservador M8-B; entonces el contexto
visible cambia y se vuelve STALE. No se rediseña fingerprint M8-B. Actor de creación no altera
estado fuente; una decisión humana nueva sí cambia workflow incluido.

## API

- GET `/tenders/{id}/proposal-readiness`: Evaluation con input hash + proyección completa.
- POST `.../proposal-readiness/snapshots`: CreateSnapshot, respuesta envelope/hash verificado.
- GET `.../snapshots`: historial20(default), max50, cursor before_id keyset fecha/id descendente;
  fecha/estado/elegibilidad/CURRENT-STALE/hash, next_before_id. Evalúa estado actual una vez.
- GET `.../snapshots/{snapshot_id}`: payload/hash almacenados verificados.
- GET `.../snapshots/{snapshot_id}/freshness`: CURRENT/STALE y hash estado actual.
- GET `.../snapshots/{snapshot_id}/handoff`: proyección almacenada verificada para MVP-09.

Todo acceso de snapshot restringido al Tender indicado; IDs ajenos404. Sin endpoint de
mutación/borrado ni generación de propuesta. Historial usa límite por página; proyección
completa es necesariamente proporcional al Tender, usa contexto canónico por request y
consultas agrupadas. Prueba sintética2→100 Scope conserva54 SELECTs (1,004 señales).
No se certifica O(1) respecto a documentos/generaciones ni miles de snapshots grandes.

## Workspace y consumo futuro

Control provisional dentro de Readiness Board: evaluar elegibilidad/historia, ver bloqueos/
revisiones/advertencias/riesgos, declarar actor, confirmar warnings y crear explícitamente.
Muestra CURRENT/STALE e historial20 con cursor y enlace a handoff. Contexto visible acotado
50 señales/50 riesgos; board paginado/API conserva conjunto completo. No porcentaje de
cumplimiento. Actor/owner no autenticados; instalación local UAT controlada continúa.
No se crea automáticamente al abrir board. Error de creación mantiene UUID/body para retry;
volver a evaluar permite otra acción explícita. No persistencia del UUID UI tras recargar.

MVP-09 deberá elegir un snapshot ID y relacionar ProposalVersion→ReadinessSnapshot. Consumir
GET handoff por ID para reproducir la versión, no recomponer con datos actuales. Detectar
STALE por endpoint separado y exigir decisión humana de usar versión anterior o crear otra,
sin reemplazo silencioso. Snapshot no genera propuesta, no firma, no envía ni bloquea edición.

## Límites y cierre

Incluye agregación, dimensiones, blockers/warnings/review, workflow/notas/riesgo, board,
prioridad, navegación, resumen y snapshot/handoff. Excluye certificación legal, aprobación
autónoma, project management, notificaciones, auth/roles, UI final, edición Quantity y
generación documental. Cierre MVP-08 requiere gates A–L y regresión green; revisión de cierre
arquitectónica separada del commit. M8-D aceptado y comprometido en `2bcd556`, sin push.

## Gate de cierre verificado

A agregación estable; B actividad subordinada; C board operacional; D elegibilidad determinista;
E blocker/warning/review separados; F snapshot íntegro/inmutable/reproducible; G stale correcto;
H contrato por snapshot para MVP-09; I sin certificación; J sin project management;
K semántica MVP-06/07 conservada; L regresión green. Todos PASS. Backend2351 y frontend134;
build/compileall/diff PASS. La revisión de cierre M8-D fue aceptada; commit `2bcd556`. MVP-08 CLOSED formalmente.
