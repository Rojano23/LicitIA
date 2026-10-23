# ADR-0034 — Monitoring y handoff humano Discovery→Tender

Estado: M10-C ACCEPTED, commit `4a4a62938c8651bed9ec8b69e66f398635992dce`. Fecha:2026-10-23.
M10-B ACCEPTED BOUNDED SCOPE (`100caf0`); Compras MX restringido no bloquea MVP-10.

## Esquema079 propuesto antes de migrar

Tablas neutrales:
- discovery_changes: UUID, event_key SHA UNIQUE, Opportunity/source/ScanRun FK, category,
  origin SOURCE/HUMAN, detected_at, previous/current fingerprint, structured changed_fields,
  deterministic summary, actor y acknowledged_at. Índice parent/fecha y parent/unread.
  Incluye auditoría humana workflow/ack/create/import, sin objetos Opportunity duplicados.
- discovery_coverage: PK(scope_sha,opportunity_id), present y last_scan_id. Scope incluye
  fuente, versión adapter, áreas ordenadas y filtros; excluye tamaño de página. Permite
  ausencia/reaparición sólo al completar SUCCESS el mismo filtro, sin equiparar ausencia
  de filtro con cancelación global. Primer scan de cada filtro establece baseline.
- discovery_tender_links: Opportunity PK, tender_id FK nullable SET NULL, tender_identity
  UUID inmutable UNIQUE, contexto mínimo de fuente, created_at. El tombstone evita crear
  otro Tender tras borrado; Discovery/history sobreviven. Sin DiscoveryTender paralelo.
- discovery_import_receipts: UUID, Opportunity/SourceDocument FK, identidad Tender/Document,
  metadata fingerprint, SHA256, source URL/name/downloaded_at y resultado. UNIQUE por parent,
  source document, metadata fingerprint y contenido. Recibos no eliminan originales previos.

Opportunity agrega watching bool (FOLLOWING existente→true) y last_scan_id nullable.
SourceDocument agrega active bool y last_scan_id nullable; se inicializa active desde las
referencias actuales de Opportunity JSON, conservando metadata histórica. Check de workflow
admite IMPORTED, sólo asignado por handoff exitoso. No se permite setear IMPORTED por PATCH.
Sin nuevas dependencias;079 sólo licitia_test/clusters temporales, no dev/producción.

## Observación y cambios

Eventos positivos y upserts se confirman en el mismo batch. Sólo un scan global SUCCESS,
terminal y sin problemas permite inferencias negativas; finalización y estado SUCCESS se
confirman juntos. PARTIAL/FAILED/interrupción nunca produce DOCUMENT_REMOVED ni ausencia.
Referencias antiguas se retienen; active cambia sólo con observación suficientemente completa.
Evento único por run/objeto/categoría/diff. Retry sin cambios no duplica. Descripción/estado/
fecha/tipos/áreas/procedure_number y docs se comparan tipados; raw_metadata auxiliar no se
promueve como cambio significativo. Diffs largos preservan hash/extracto y marca de truncado.

FOLLOWING no crea Tender. watching también admite seguimiento de IMPORTED sin cambiar su
estado. Cambios de fuente no alteran workflow ni Tender. Ack es auditable/local, no fuente.
No scheduler: MANUAL SCAN ONLY FOR PRIVATE BETA. Sin servicios OS/colas/infra adicional.

## Handoff explícito y seguridad

Preview readonly, sin red/Tender; binding incluye revisión/fingerprint y referencias activas.
Confirmación humana requerida; selección vacía por defecto. Título largo requiere entrada
humana <=255; institución/URL/publicación se preservan en contexto del vínculo, sin inventar
un Institution Profile CFE. Tender normal DRAFT mediante infraestructura existente.

Lock por Opportunity y vínculo único aseguran create idempotente. Primero se confirma
Tender+vínculo+IMPORTED atómicamente; descargas seleccionadas son resultados independientes,
con errores explícitos. Retry Create retorna vínculo existente, no reimporta implícitamente.
Sync separado valida ownership y binding. Descarga por adapter/política de fuente, nunca fetch
URL libre. HTTPS/host/ruta permitidos, sin redirects, timeout/techo/25MiB, MIME/magic,
nombre seguro, SHA256, staging temporal local; no ejecución ni extracción de archives.

El servicio de handoff depende de un callback de ingestión; la API adapta streams al import
canónico existente. No duplica reglas hash/conflicto/revisión/storage ni invoca análisis.
Recibo conserva provenance aunque el documento canónico fuera duplicado. Name conflict se
expone; NEW_REVISION requiere elección explícita y target del mismo Tender/fuente. Estado
previo y originales permanecen. Fallo parcial no se representa como importación completa.

Compras MX scan/preview/create/import automatizados rechazados antes de red. Manual Tender
creation/import siguen disponibles e independientes. No PoW, token/browser bypass ni datasets
sustitutos. No DI/OCR/Vision/LLM/Requirements/Scope/Bid Readiness automáticos.


## Corrección de cierre M10-D — contexto histórico de perfil

La auditoría Phase30 detectó que reevaluar un Profile mutable no reconstruye el match al
crear Tender. Se captura opcionalmente su ID/revisión/configuración tipada y match determinista
con SHA en Link.context existente, junto con los campos fuente usados para matching. El evento
TENDER_CREATED conserva ID/revisión/SHA de ese contexto; no duplica la configuración completa.
Preview/binding incorpora el contexto; modificación del perfil requiere nueva confirmación.
Request sólo acepta profile_id, nunca una explicación/decisión de relevancia del cliente como
verdad canónica. El servidor evalúa el mismo matcher. Sin perfil seleccionado se registra null;
vínculos legacy se muestran LEGACY_NOT_CAPTURED, sin reconstrucción retroactiva inventada.
Un match falso no bloquea la decisión humana. Perfil/keywords quedan locales, nunca se envían
al portal. El contexto capturado sobrevive edición/borrado del perfil y backup/restore.
Sin migración080, fuente nueva, análisis automático ni cambio a las reglas del matcher.
