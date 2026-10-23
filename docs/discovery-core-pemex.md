# M10-A — Discovery Core y adapter PEMEX

Implementación para revisión arquitectónica. M9-D ACCEPTED, commit
`6467646d6f8738fb8d0a9f6fe5d97de81a4fc348`; MVP-09 CLOSED. M10-A validado y sin stage/commit/push. Backend2422 passed/2opt-ins excluidos;
frontend164 passed/build PASS;32 pruebas focused offline y smoke live PASS.
078 sólo aplicado en licitia_test/clusters efímeros, no en dev/producción.
Futuro nombre público **RX23 TuScope**; repositorio/código conservan LicitIA.
[ADR-0032](adr/0032-discovery-core-pemex.md), esquema078 documentado antes de migración.

## Límites y contrato

Discovery es opcional y opera sin Tender seleccionado. Fuente pública → adapter → Opportunity
normalizada → persistencia local → perfil determinista → revisión humana. No crea Tender ni
invoca DI, OCR, Vision, Ollama, Commercial, Readiness o Proposal Builder. Sin embeddings.
Crear Tender explícitamente corresponde a M10-C. Sin scheduler, notificaciones, CFE/Compras MX,
UI final, branding o renaming en M10-A.

DiscoveryAdapter expone identidad/versión/capabilities/áreas y fetch(query,area,cursor) → Batch.
El adapter construye la petición y continuación propias (page/offset/cursor/URL/token/etc.);
el Core consume batches sin conocer OData ni construir offsets universales. Batch declara
filas normalizadas, raw_count, total cuando existe, next_cursor, terminal explícito y issues.
El Core valida conteos/límites y decide cobertura/auditoría; no convierte ausencia de primera
página en éxito. Un adapter sintético de cursor opaco prueba independencia del Core.
Normalización y documentos metadata pertenecen al adapter. Descarga binaria no soportada
(capability explícita), por lo que no existe fetch genérico de URL suministrada por usuario.

## Fuente pública actual, inspección2026-10-22

Entrada: [Concursos Abiertos PEMEX](https://www.pemex.com/procura/procedimientos-de-contratacion/concursosabiertos/Paginas/default.aspx).
Cuatro configuraciones de un solo adapter:

| Key | Etiqueta actual | Lista pública |
|---|---|---|
| support | Servicios y Bienes de Soporte | Concursoseinvitaciones |
| exploration | Exploración y Extracción | ConcursosAbiertosPEP |
| industrial | Procesos Industriales y Transformación Energética | ConcursosAbiertosPTI |
| logistics | Logística | ConcursosAbiertosPL |

Páginas bajo `/procura/procedimientos-de-contratacion/concursosabiertos/Paginas/`:
Pemex.aspx, Pemex-Exploración-y-Producción.aspx, Pemex-Transformación-Industrial.aspx,
Pemex-Logística.aspx. El HTML tiene tabla `mitabla`,20 filas y postback SharePoint DataView
`dvt_firstrow/dvt_startposition` con indicador Siguiente. Los botones documentales publican
`data-listname/data-itemid`. No se ejecutan sus scripts/analytics.

Se eligió interfaz pública JSON SharePoint sobre HTML: sitio `/_api/web/GetList('<list-path>')/items`,
Accept application/json;odata=verbose. No se encontró API documentada específica de contratación;
se trata como interfaz pública estructurada, no contrato oficial estable de integración.
No browser automation, Selenium/Playwright, login ni bypass de CAPTCHA/antibot.

HTTPX0.27.2 BSD-3-Clause existente, Pydantic2/SQLAlchemy2 existentes, lxml6.1.3 BSD-3-Clause
con notices existentes para convertir texto HTML en texto literal. Sin dependencias nuevas.
No framework scraping adicional. Licencias/notices instalados y docs/licenses existentes.

## Consultas y exhaustividad

SourceQuery permite áreas habilitadas, published_from/to, tipo de evento y suministro;
page_size1–200 (default100). Filtros de fuente explícitos no incluyen perfiles privados.
OData escapa comillas y codifica parámetros; fecha límite final23:59:59. Fuente devuelve
`d.results`, `d.__next` con `$skiptoken` y filtros, o término sin __next. El adapter comprueba
host/path y conservación de query en cada continuación. No se asume total por tamaño de batch.
`__count` se captura si aparece; las consultas live actuales no lo publicaron. Si existe total,
únicos observados deben coincidir; mismatch impide SUCCESS.

Todo el query se recorre hasta terminal. Límites de seguridad2000 batches/área y100000 identidades
por scan evitan consumo ilimitado; alcanzar límite con resultados pendientes es PARTIAL/FAILED,
nunca truncamiento exitoso. Respuesta HTTP descomprimida máxima16MiB; timeout30s/connect10s,
hasta3 intentos en errores transitorios, pacing1s y backoff acotado. Redirects no se siguen.
Sin snapshot remoto atómico: best-effort ante movimiento del listado. Identidades evitan
duplicados; total cambiante, discrepancias o representaciones incompatibles se diagnostican.
No se garantiza detectar un desplazamiento silencioso del portal si no publica total/snapshot.

## Identidad, observación y documentos

Opportunity ID determinista UUIDv5(source+external event ID), UNIQUE(source_id,external_id).
ID de evento es Title/No. Evento literal con whitespace normalizado, no descripción ni índice.
Faltante/malformado: fila aislada, diagnóstico y scan incompleto. Campos no disponibles quedan
NULL; no se inventa deadline, status ni área contratante. `areacontratante` es Choice público y
se conserva cuando viene; literal source_status actualmente no expuesto por esta interfaz.

Fingerprint incluye identidad, descripción, publicación/tipos/área, status y metadata documental
ordenada; ignora metadata de parser/presentación. Primera observación fija first_seen; cada
observación válida actualiza last_seen. published_date es fecha de fuente independiente.
Repetición no duplica; cambio conserva previous_fingerprint y last_changed. No se borran
registros que dejan de aparecer. NEW/REVIEW/FOLLOWING/DISCARDED son estados internos humanos
separados del source_status; no existe transición a IMPORTED en este slice.

AttachmentFiles expandido trae FileName/ServerRelativeUrl; ID documental por URL dentro del
parent Opportunity, fingerprint metadata, observed_at y UNIQUE(parent,external_id). Conteo
representa referencias descubiertas, nunca descargas. Histórico de referencias persistidas no
se borra al desaparecer; representación actual distingue su inventario presente. No se descargan
PDFs ni se afirma hash de contenido binario. Raw metadata allowlist: item ID, area key, lista;
máximo8KiB, sin HTML/respuesta completa ni datos de contacto innecesarios.

## Transacciones, estados y retry

Lock PostgreSQL por fuente sobre conexión dedicada a través de commits por página. Upsert
batch de oportunidades/documentos y actualización de scan se confirman juntos. Contadores e
identidades se publican sólo tras commit durable; un fallo no cuenta filas pendientes como
persistidas y finaliza las áreas abiertas como PARTIAL/FAILED según observaciones confirmadas. Fallo posterior
conserva observaciones previas. Scan RUNNING guarda started/finished, versión/query/request,
contadores de páginas/filas/únicos/new/updated/unchanged/duplicados y diagnóstico por área.
SUCCESS sólo con todas las áreas terminales sin issues; PARTIAL si hubo observaciones útiles
pero cobertura no comprobada; FAILED cuando no hubo cobertura válida. Un error no dispara IA.

Mismo request UUID+payload devuelve resultado preservado; otro payload409. Nuevo UUID reintenta
scan y converge por upsert, sin borrar resultados. Scan concurrente409. Próximo scan con nuevo
request recupera un RUNNING huérfano como PARTIAL/FAILED con diagnóstico de interrupción.
Máximo100 diagnósticos detallados más contador de truncados; no logs/streams sin retención.
Auditoría de scans permanece como datos locales del producto para administración; sin historial
binario de respuestas remotas ni cron de limpieza. M10-C ampliará monitoreo/timeline/retención.

## Perfiles y filtros locales

Perfil con nombre/active/revisión, include/exclude, grupos de sinónimos, restricción opcional
por fuente y business area. Normaliza case, acentos y whitespace; frases por límites de palabra.
ANY include; lista vacía incluye cualquier registro dentro de restricciones. Exclude siempre
gana, también con sinónimos explícitos; sin expansión IA. Explicación enumera término, texto,
field y EXACT/SYNONYM, exclusiones/restricciones. Score diferido, sin probabilidad de ganar.

Matching derivado se aplica al flujo local filtrado completo antes de paginar resultados UI;
no se limita a página1 del portal. Un scan PARTIAL no certifica cobertura del query. Puede
consultarse offline sobre DB local. Orden: published_date desc NULLS LAST, first_seen desc, ID.
Filtros: fuente, área, fechas, evento/suministro/status de fuente, estado interno, perfil/match;
búsqueda literal local case-insensitive de evento/título/descripción. `%/_` no actúan como wildcard.
Lectura con perfil transmite filas por chunks200 sin SQL por término/field. Lista50/default,
200máximo; offset y total explícitos. Historial scans20/default/100máximo.

## API y vista provisional

- GET `/discovery/sources`, GET/PATCH `/discovery/sources/{id}`: configuración soportada/estado.
- POST `/discovery/sources/{id}/scans`: manual, request UUID/query tipado. No acepta URL arbitraria.
- GET `/discovery/scans`, GET `/discovery/scans/{id}`: auditoría/progreso persistido/resultado.
- GET/POST `/discovery/profiles`, PATCH `/discovery/profiles/{id}`: optimistic revision.
  GET paginado100/default,200máximo; UI recorre páginas locales hasta2000 perfiles y falla
  explícitamente al alcanzar el límite, sin truncamiento silencioso.
- GET `/discovery/opportunities`, GET `/{id}`, PATCH `/{id}/state`: límites/filtros y revisión humana.

Sección independiente opcional en App, sin cambiar navegación global. No hace HTTP al montar:
usuario consulta fuentes, elige áreas/filtros y ejecuta scan. Estado busy durante request síncrono;
resultado/historial expone cobertura y errores (sin scheduler/job framework). Perfiles locales
editables con sinónimos `PLC=controlador lógico programable|otro`; tabla muestra NEW, datos de
fuente, estado humano, coincidencias y referencias sin descargar. Retry conserva request/query.
No botón Create Tender. No claims de recomendación IA, guaranteed fit o probabilidad de ganar.

## Seguridad y datos

Sólo HTTPS www.pemex.com/pemex.com, puerto443, paths procura configurados, sin credenciales,
fragmentos, path traversal ni esquemas arbitrarios. Continuaciones sólo al endpoint/lista original;
no reenvío de query a otro host. URLs documentales se validan sin fetch. React muestra texto
escapado; lxml descarta script/style y no ejecuta JS. Contenido privado/intereses permanecen en DB
local, sin telemetry RX23. Sólo adquisición pública explícita requiere Internet; lista/matching
locales funcionan offline. UAT local controlado permanece, sin auth nueva.

078 agrega cinco tablas genéricas e índices acotados (source+external único, source+published,
workflow, scan source+started, documentos parent). Sin FK Tender ni cambios a001–077. RC-H3
respalda DB completa; no motor nuevo. Downgrade destruye sólo datos/tablas Discovery, explícito;
upgrade/downgrade verificados sólo en licitia_test. No migración automática de dev/producción.

## Evidencia

Fixtures sanitizadas derivadas de forma pública actual: pemex-row.json y factories en
`test_discovery.py`. Single/3pages/217únicos, duplicados, orden, malformed, cambio, filtros,
metadata, fallo intermedio, retry, mismatches, ciclos, límites y adapter opaco. No red en fixtures.
Live sólo `LICITIA_DISCOVERY_LIVE=1 ... pytest tests/test_discovery_live.py`; marker live_discovery,
no bloquea regresión normal si portal cae. La prueba explícita inlinecount=allpages tampoco devolvió
__count; no se presume un total filtrado independiente. Reportes en backend/reports/m10_a, sin stage.

Consulta live desde2026-10-01/page_size20: Soporte7/1batch/19refs; Exploración8/1/28;
Industrial44/3/385; Logística1/1/13. Total60 únicos,6batches,445 referencias,0duplicados/0malformed,
4áreas SUCCESS, todas terminales. Total de fuente NULL; no inventar conteo remoto independiente.
La fixture217únicos/218filas/3pages usa37sentencias SQL, no query por campo/término/entidad.
No certifica exhaustividad de otros filtros ni estabilidad futura del portal.
