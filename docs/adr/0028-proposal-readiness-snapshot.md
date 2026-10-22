# ADR-0028 — M8-D: snapshot de handoff para MVP-09

Estado: implementación autorizada para revisión. Esquema documentado antes de075.
M8-C aceptado, commit `748dda6265feda23d356086fb63218b434c6e501`.

M8-A/B/C y M7-D siguen autoritativos. No existe snapshot de producto previo que preserve
su composición: freezes blind son evidencia experimental, no dominio de propuesta.
ReadinessWorkDecision sólo conserva actividad, CommercialLineRevision sólo comercial;
reutilizarlos para handoff multi-dimensión perdería coherencia/identidad.

## Persistencia acotada075 (sobre074)

Una tabla `proposal_readiness_snapshots`: id UUID, tender_id FK RESTRICT, request_id UUID,
request_sha256 (identidad de solicitud), created_at UTC, actor_label opcional≤200,
input_sha256 (estado relevante), payload_sha256, payload JSON versionado. Unique(Tender,
request_id), índice(Tender,created_at,id). Trigger anti UPDATE/DELETE. Sin ProposalVersion,
no tablas de documentos ni blobs binarios. Payload incluye envelope con identidad/audit
para verificar consistencia con metadata relacional. SHA256 de JSON canónico ordenado,
UTF8, sin NaN; fingerprint de integridad, no firma/autenticación. Se valida typed schema,
identidad Tender/Scope/Quantity/comercial y hash al recuperar. Una referencia no implica
que originales sobrevivan fuera de los backups normales; no se duplican documentos.

## Elegibilidad y snapshot

Blocker M8-A o ausencia de filas propuestas→NOT_ELIGIBLE. REVIEW M8-A o exclusión comercial
por review→REVIEW_REQUIRED; visible separado de blocker, sin snapshot listo hasta resolver
revisión fuente en esta política. Sin blocker/review, warnings→ELIGIBLE_WITH_WARNINGS;
sin warnings→ELIGIBLE. No reglas legales nuevas ni override por actividad RESOLVED.
Cobertura no certificada M8-A permanece Warning, por lo que actualmente los casos completos
usualmente serán ELIGIBLE_WITH_WARNINGS. No se elimina para fabricar ELIGIBLE.

Crear es acción explícita: UUID idempotency request, expected_input_sha256 y confirmación
warnings cuando corresponda. Mismo request con mismo contenido devuelve mismo snapshot
inmutable aun si la fuente cambió después. Reutilizar request con otro contenido→409.
Nuevo request crea versión nueva aun si estado relevante igual. Colisión concurrente→409
retry del mismo request; unique evita duplicados. No reintentos automáticos ni cambios
silenciosos. Snapshot y GET handoff verifican hash y se leen sin reconstruir desde fuente.

API de evaluación/creación/freshness usa sesión PostgreSQL REPEATABLE READ independiente
por request: vista MVCC coherente sin bloqueos de edición. Snapshot es estado visible en
esa transacción, no promesa de que no existan commits posteriores. Base fuente sigue editable.
GET handoff por ID sólo devuelve payload almacenado verificado. CURRENT/STALE se calcula
separado comparando input_sha256 actual; no modifica snapshot. Error al evaluar freshness
se expone, nunca se convierte en CURRENT. Historia usa paginación keyset por fecha/UUID.

Fingerprint incluye sólo proyección de propuesta: identidad Tender, readiness/issues con
referencias estables y estados, filas comerciales elegibles con Quantity/Scope/line IDs,
precios/moneda y fuente, workflow activo/revisión/nota/riesgo, metadata documental hash/
revisión y estado de versiones. Excluye reloj, fingerprints opacos comerciales completos,
costos/margen/markup/contactos y estado de UI. Un costo puede cambiar advertencia o stale
M8-B y entonces sí cambia el handoff. No se rediseña fingerprint conservador M8-B.
Schema/app identity se guarda para lectura reproducible, fuera de fingerprint de estado.

Backup RC-H3 usa pg_dump/restore completo y ya incluye la tabla sin nuevo filesystem.
Nueva prueba E2E en cluster privado sintético comprueba payload/hash tras backup/restore.
075 sólo se migra en licitia_test y clusters efímeros de pruebas, nunca dev/históricos.
Downgrade administrativo elimina nueva historia; no acción UI. Sin auth/roles, UI final,
notificaciones, semántica documental nueva, edición Quantity o generación de propuestas.
