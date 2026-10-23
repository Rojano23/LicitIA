# ADR-0032 — Discovery independiente y adapter público PEMEX

Estado: M10-A autorizado para implementación y revisión. Fecha:2026-10-22.

## Decisión y límites

Discovery es opcional e independiente de Tender Analysis. Core normaliza/persiste observaciones,
perfiles deterministas y auditoría; un adapter controla adquisición y paginación propias.
No crea Tender, no importa binarios ni invoca DI/OCR/Vision/LLM. No scheduler/notificaciones.
MVP-09 CLOSED; nombre interno LicitIA permanece. Futuro producto RX23 TuScope; renaming/UI
final posteriores a cierre MVP-10, antes de pruebas reales/demos/Windows/Private Beta.

## Fuente y dependencias

Inspección pública actual: cuatro áreas de PEMEX con listas SharePoint. HTML usa20 filas y
postback DataView; interfaz pública JSON SharePoint permite $top, filtros OData y __next/
$skiptoken, con AttachmentFiles expandido. Se elige JSON estructurado antes de HTML/browser.
No se encontró documentación API específica de contratación; no se presenta como API formal
estable. Sólo HTTPS www.pemex.com/pemex.com y paths procura configurados, sin redirects,
credenciales, scripts, CAPTCHA bypass ni envío de intereses privados. Usa httpx existente
(BSD-3-Clause), Pydantic/SQLAlchemy existentes; lxml existente (BSD-3-Clause/notices conservados)
sólo para texto HTML literal. Sin nuevas dependencias ni framework scraping/browser.

## Esquema078 propuesto ANTES de migración

Cinco tablas genéricas, sin FK ni escritura a Tender:
- discovery_sources: ID estable, nombre/base URL/tipo/adapter versión, enabled y config JSON
  tipada; último scan/éxito/error y fecha. PEMEX es una fuente, áreas configuradas.
- discovery_profiles: UUID, nombre, active, revisión optimista y contrato JSON acotado de
  términos include/exclude/sinónimos/restricciones. Matching local, no se transmite al portal.
- discovery_opportunities: UUID estable, UNIQUE(source_id,external_id), representación
  normalizada JSON, first_seen/last_seen separados de published_date, fingerprint actual/
  anterior/last_changed, estado interno NEW/REVIEW/FOLLOWING/DISCARDED y revisión humana.
- discovery_scan_runs: UUID/request identidad idempotente por source/request, query JSON,
  started/finished, adapter versión, RUNNING/SUCCESS/PARTIAL/FAILED y métricas/diagnósticos JSON.
- discovery_source_documents: ID estable, opportunity FK, UNIQUE(opportunity_id,external_id),
  nombre/URL/fingerprint y observed_at. Referencia descubierta, nunca implica descarga.

Índices de source/fecha publicación/estado interno, scans source/started y documentos parent;
sin proliferación por campos JSON. JSON normalizado tipado sigue contrato público genérico.
078 sólo se aplica a licitia_test/clusters temporales; downgrade elimina sólo tablas Discovery
(en orden FK), destructivo explícito; no se alteran migraciones001–077.

## Exhaustividad y transacciones

Adapter devuelve batches con contexto/next/terminal/total cuando disponible. Core no fabrica
un algoritmo universal de paginación; detecta ciclos, límites, conteo único incompatible,
filas inválidas, final no explícito, errores de área/página. Todo ello impide SUCCESS.
Cada batch se valida y upsertea en bloque y se confirma junto con auditoría; fallo tardío
conserva páginas previas y queda PARTIAL/FAILED. Retry con nuevo request converge por identidad;
repetir mismo request devuelve auditoría original, no ejecuta otra vez. Lock por fuente evita
scans concurrentes. Interrupción deja RUNNING explícito y siguiente scan lo finaliza como
PARTIAL/FAILED con diagnóstico, sin declarar éxito. No se eliminan oportunidades ausentes.

Identidad source + número de evento literal normalizado en whitespace (sin matching por título
/descripción). ID ausente/inválido: fila aislada y scan parcial. Duplicado idéntico se cuenta una
vez; representaciones incompatibles en mismo scan generan diagnóstico PARTIAL. Fingerprint
considera representación y documentos, no HTML ni timestamps de observación. Mantiene anterior.
Sin snapshot/cursor estable del portal se declara best-effort frente a movimiento de resultados;
no se promete snapshot remoto atómico. Matching se consulta localmente sobre todos los registros
persistidos; un scan parcial nunca certifica completitud de matches del query.

## Seguridad y retención

Respuestas acotadas, pacing y retry limitado para fallos temporales; no fetch genérico URL.
HTML remoto se trata como texto y no se ejecuta. Metadata documentos validada por host/path;
URLs inseguras se diagnostican, nunca se recuperan. Descarga de binarios diferida a M10-C.
Datos sólo local DB y backup RC-H3 existente; no logs de contenido ni raw HTML permanente.
Raw metadata permitida acotada y por allowlist para depuración; auditoría resumida con límite
explícito de diagnósticos, sin crecimiento de logs/streams. Historial de scans producto se
conserva para administración local; no borrado automático ni retención infinita de respuestas.
