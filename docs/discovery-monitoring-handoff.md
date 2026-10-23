# Discovery M10-C — monitoreo y handoff humano

M10-B ACCEPTED — BOUNDED SCOPE, commit `100caf07ec0ca503145a6b25242591cb6d38f38a`.
M10-C permanece sin stage/commit/push. [ADR-0034](adr/0034-discovery-monitoring-handoff.md),
Alembic `20261023_discovery_079`. Sin dependencias nuevas ni cambios semánticos MVP-01–09.

## Workflow

NEW → REVIEW/FOLLOWING/DISCARDED; REVIEW → NEW/FOLLOWING/DISCARDED;
FOLLOWING → NEW/REVIEW/DISCARDED; DISCARDED → NEW/REVIEW.
IMPORTED es terminal, sólo después de creación explícita de Tender.
Revisión optimista detecta estado desactualizado (409). Cambiar a FOLLOWING activa watching;
otras transiciones lo apagan. Follow/unfollow independiente conserva internal_state, incluso
IMPORTED. Seguir no crea Tender. Estados fuente nunca cambian decisiones humanas.

## Observaciones

Comparación batched de campos normalizados, sin raw_metadata/cosmética HTML. Eventos fuente:
NEW_OPPORTUNITY, METADATA_CHANGED, SOURCE_STATUS_CHANGED, DOCUMENT_ADDED, DOCUMENT_CHANGED,
DOCUMENT_REMOVED, NO_LONGER_OBSERVED, REAPPEARED. Diff de campos conserva valores anteriores/
actuales; textos largos tienen excerpt2000 + hash + truncado. Auditoría humana conserva actor
local, origen y timestamp; actor no constituye identidad autenticada.

Eventos positivos se confirman por batch, incluso si falla otra página. Event key por
scan/Opportunity/categoría/diff impide duplicados; el mismo request devuelve el scan histórico.
Un scan nuevo sin cambios no duplica eventos.

**Sólo SUCCESS global completo** finaliza bajas/cobertura. Ausencia de Opportunity compara
la misma fuente/consulta normalizada/versión adapter; page_size no define alcance, áreas
ordenadas. Primera consulta completa establece baseline, sin bajas retrospectivas pre079.
PARTIAL/FAILED, continuación incompleta, total inconsistente o fallo de persistencia no
producen eventos negativos. Un filtro distinto no demuestra ausencia en el anterior.
DOCUMENT_REMOVED requiere observación completa de la Opportunity; conserva metadata inactive.
Ausencia no afirma cancelación global, no borra datos ni altera workflow. Reaparición conserva
first_seen. Finalizar bajas/cobertura y SUCCESS comparte transacción.

Identidad documental usa ID/referencia estable del adapter, nunca posición. Metadata actual
ID/nombre/URL; tamaño/hash sólo cuando la fuente los represente (no disponibles en los shapes
actuales). Sin descargas binarias durante scans. Contenido cambiado bajo URL/metadata idéntica
requiere refresh explícito para descubrir nuevo SHA.

Historia cronológica paginada (default100, máximo200), acknowledgement valida propiedad y no
muta fuente. Contadores changed incluyen nuevas con eventos fuente sin leer; new_documents
cuenta DOCUMENT_ADDED sin leer. Source changed compara con fingerprint capturado al crear
Tender; no certifica sincronización completa. Receipts muestran importación por documento.

## Handoff explícito

Vista previa readonly sin crear Tender ni adquirir binarios. Incluye identidad, título,
descripción, fecha, entidad/área, URL/estado y documentos activos. Binding incluye revisión,
fingerprint/documentos y vínculo; cambio produce409 y exige consultar nuevamente.

Selección default **ninguno**; elegir todos es explícito. Confirmar crea Tender Core DRAFT
+ vínculo único + IMPORTED en una transacción. Título/referencia se mapean sólo desde fuente
literal o título humano; título máximo255. Contexto del vínculo conserva fecha/URL/área/estado,
pues Tender no tiene esos campos. No se inventa Institution Profile a partir de fuente.
Descartado debe volver a revisión. Repetir create devuelve Tender existente sin importar otra
vez; agregar documentos es acción distinta. Borrado deja tombstone/identidad, create409 sin
recreación. No hay nuevo endpoint de borrado.

PEMEX/CFE comparten servicios. Compras MX continúa DEFERRED_SOURCE_AUTOMATION_RESTRICTED,
guard antes de preview/scan/handoff, sin nuevos requests/bypass. Crear/importar un Tender
manualmente desde archivos obtenidos por usuario permanece disponible.

## Documentos y seguridad

Sólo selección confirmada pasa por adapter/allowlist HTTPS/path, sin redirects. Nombre
validado antes de red: sin traversal/control/ADS/reservados Windows, máximo255 bytes. MIME
allowlist + firma compatible, no HTML/vacío, máximo25MiB descomprimidos por archivo. Timeout30s
por operación de red, ceiling60s comprobado entre chunks (lectura bloqueada puede consumir
su timeout antes de la comprobación). Spooled temporary local1MiB antes de spill; no ejecución
ni descompresión. Máximo1000 selecciones. No antivirus ni validación semántica completa PDF/Office.

Gateway inyectado reutiliza import_documents canónico: SHA, duplicado Tender+hash, conflicto
nombre, revisión/import independiente, staging/publicación atómica y cleanup. No repositorio
Discovery paralelo. Receipt conserva Opportunity/SourceDocument, metadata fingerprint,
SHA-256, URL/nombre, timestamp y documento canónico, incluso al borrar Tender/documento.
Dos referencias al mismo contenido tienen receipts independientes y archivo canónico único.
Sin refresh se reutiliza receipt si existe documento; refresh explícito redescarga.

Fallo parcial conserva Tender y subset exitoso, resultados por archivo
IMPORTED/DUPLICATE/REUSED/NAME_CONFLICT/FAILED; agregado PARTIAL honesto. IMPORTED significa
Tender creado, no todos los documentos importados. Tras fallo de respuesta consultar vínculo;
retry explícito de documentos fallidos. Crash tras commit canónico y antes de receipt se
recupera con hash canónico. Nunca análisis automático: OCR/Vision/LLM/Requirements/Scope/
Readiness siguen bajo decisión humana en Workspace.

Cambios fuente no mutan Tender ni análisis existentes. Sync explícito conserva originales.
Conflicto NONE reporta; IMPORT_INDEPENDENT crea independiente; NEW_REVISION exige target del
mismo Tender previamente importado desde ese SourceDocument. Propiedad se valida antes de red.

## API neutral

- GET /discovery/monitoring/summary
- GET /discovery/opportunities: following, unread_only, internal_state=IMPORTED y filtros previos.
- PATCH /discovery/opportunities/{id}/state: internal_state, expected_revision.
- PATCH /discovery/opportunities/{id}/following: following, expected_revision.
- GET /discovery/opportunities/{id}/changes: limit, offset.
- POST /discovery/opportunities/{id}/changes/acknowledge: change_ids, actor.
- GET /discovery/opportunities/{id}/tender-preview.
- POST /discovery/opportunities/{id}/create-tender.
- POST /discovery/opportunities/{id}/tenders/{tender_id}/documents.

Ambos POST handoff: confirm=true, expected_binding, title opcional, documents=[]. Cada choice:
document_id, conflict_action=NONE, revision_of_document_id=null, refresh=false. Nunca URL
arbitraria suministrada por payload. UI incluye detalle/historia, follow, filtros, indicadores,
preview, selección, confirmación, resultado por archivo y Open Tender por vínculo persistido.

## Operación y alcance

**MANUAL SCAN ONLY FOR PRIVATE BETA**. Sin scheduler/daemon/Redis/Celery/cloud. Locks por fuente
y handoff por Opportunity + row lock inicial. RC-H3 pg_dump/filesystem respalda nuevas tablas,
receipts y originales sin redesign. Downgrade079 elimina estado de monitoreo/receipts/enlaces y
transforma IMPORTED a REVIEW, nunca Tenders/originales; requiere backup y decisión administrativa.
Sin auth nueva, UI final, renaming, notificaciones, ni ampliación de Tender Analysis institucional.

M10-D recomendado: validación cross-source de completitud, cambios/handoff/versión/restore/
reintentos y límites públicos; opt-ins vivos acotados autorizados por separado, cierre gates
MVP-10. Compras MX deferred no bloquea cierre ni autoriza bypass. Scheduler/installer/branding
permanecen fuera de este slice.
