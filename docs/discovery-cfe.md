# M10-B — CFE y restricción de automatización Compras MX

M10-A ACCEPTED (`d9e9735`), MVP-09 CLOSED. M10-B es un slice acotado:
**CFE ADAPTER COMPLETE** — validado, listo para revisión arquitectónica;
**COMPRAS MX AUTOMATED ADAPTER DEFERRED — SOURCE ACCESS RESTRICTION**.
No se declara completo el plan original de dos adapters.
[ADR-0033](adr/0033-discovery-cfe-source-restrictions.md),
[inventario público observado](discovery-m10b-source-inventory.md).

## Adquisición CFE

Fuente: <https://msc.cfe.mx/Aplicaciones/NCFE/Concursos/>. HTTPX existente; formulario público
con cookie/CSRF propios de CFE, POST getProcBusqueda con fechas ISO del input público.
No login, browser automation, JavaScript remoto, CAPTCHA/PoW ni descargas binarias.
Filtros remotos: rango publicación (ambas fechas o ninguna) y tipo de procedimiento literal
verificado (Concurso abierto/Concurso simplificado/Adjudicación directa). Supply type se
filtra localmente **después de recibir todo el array**, no con códigos inferidos.
Filtros vacíos consultan todos los resultados expuestos; se recomienda rango acotado.

El grid público Kendo pagina un array completo en cliente. Adapter mantiene ese snapshot
acotado y entrega batches locales de 1–200 al mismo Core. Cursor opaco ligado al hash de query,
secuencia estricta; no es URL ni un endpoint remoto configurable. No afirmar 5 páginas HTTP
cuando sólo hubo 1 listado. Terminal se emite sólo al agotar el array filtrado.

El portal no publica un total independiente. `source_total=null` no es cero ni el conteo
inventado de un archivo histórico. Best effort: recorrido completo del array recibido,
sin prometer detección de límites remotos no publicados ni snapshot atómico listado/detalles.
Límites: 16 MiB descomprimidos/respuesta, 100,000 filas/array, límites genéricos Core 2,000 batches/
100,000 oportunidades. El array completo es inherente al endpoint; no se descargan listados
sin límite ni se guardan capturas remotas en DB. Superar límites impide SUCCESS.

## Normalización y trazabilidad

Identidad `CFE + Id` entero opaco. `procedure_number` conserva Numero humano, independiente
para buscar y mostrar. No ID por título, página o posición. Descripcion literal es title/
description; tipos y estado fuente permanecen literales, separados de NEW/REVIEW/FOLLOWING/
DISCARDED. Fecha .NET `/Date(ms)/`→fecha civil America/Mexico_City. Fecha ausente queda null;
fecha no parseable es fila malformada, no una fecha inventada.

Cada fila consulta detalle mediante POST público con Id. Verifica que el número del detalle
coincida con el listado. Empresa→business_area, Área Contratante→contracting_area; ausencia
permanece null (business_area requiere etiqueta genérica de consulta si no hay Empresa).
Entidad Federativa queda en raw metadata, no se confunde con empresa ni se infiere área desde
el número. Opcionales ausentes no se inventan. Contratos de normalización siguen Pydantic.

Detalle accesible por POST; GET Details?id no funcionó. public_url abre el portal real;
raw metadata conserva path/método/Id de navegación, **nunca CSRF ni cookies**. No URL de
detalle ficticia. Workspace muestra número humano e ID; el enlace abre el portal público.

Anexos: metadata referenciada en HTML público (GetAnexo con token opaco, Precision y Respuesta
cuando haya href); nombre, identidad/URL y parent/observed_at mediante SourceDocument existente.
No se ejecutan onclick: sólo se reconoce su formato literal verificado y se valida el URL.
Cobertura declarada `PUBLIC_DETAIL_HTML_REFERENCES_ONLY`; no promete todas las etapas/AJAX
históricas del portal. Referencia descubierta no implica descarga, análisis ni revisión humana.

Fingerprint genérico incluye número humano, campos significativos y documentos. Nuevo campo
opcional JSON 078; si no existe se excluye sólo ese campo del hash para preservar exactamente
fingerprints PEMEX previos. No nueva columna ni migración. Same Id con cambio significativo
actualiza la misma Opportunity; first_seen se preserva y last_seen se renueva por commit.
No borra oportunidades ausentes. Perfiles idénticos y locales, sin puntajes por institución.
Como en M10-A, raw_metadata no participa del fingerprint: cambios sólo de metadata auxiliar
(p. ej. geografía) actualizan la observación, sin evento last_changed/revisión por sí solos.
M10-C deberá evaluar ese alcance al definir seguimiento de cambios significativos.

## Fallos, seguridad y persistencia

Core neutral sin ramas de paginación institucionales. Registry contiene factories/áreas/
capabilities; no CFEOpportunity, nueva tabla, motor ni API específica por fuente.
Bootstrap idempotente registra PEMEX/CFE y Compras MX diferido con enabled false.

Scans manuales genéricos: POST `/discovery/sources/CFE/scans`, query.areas=[public]. Misma
request_id+payload retorna auditoría previa; nuevo request después de fallo converge mediante
upsert. Mismos locks y commits por batch: fallo tardío conserva filas previas. Detalle fallido
no persiste una fila incompleta ni descarta sus documentos anteriores: diagnostica y produce
PARTIAL/FAILED. Malformed, URL inseguro o identidad de detalle ambigua impiden SUCCESS.

Sólo HTTPS msc.cfe.mx puerto443, rutas exactas de Concursos permitidas; sin credenciales,
fragmentos, escapes de path ni redirects. Política de URLs documentales separada; no son targets
de fetch. HTTP 30 s / connect 10 s, pacing 1 s y hasta 3 intentos sólo para errores transitorios (429/
500/502/503/504, timeout/network), backoff 1/2 s. MIME HTML/JSON y límite por stream. Error no
registra cuerpos/token/cookie. Todo filesystem/DB privado permanece local; HTTP sólo metadata
pública de CFE. No Tender automático, DI/OCR/Vision/LLM, scheduler, notificación o branding.

DB sigue batching/upsert, sin consulta por campo/documento. HTTP sí necesita un detalle por
procedimiento porque el listado carece de Empresa/Área/anexos; se contabiliza y pacea. No se
confunde esa necesidad de adquisición con un N+1 de persistencia. Parcialidad no certifica
la cobertura de matches sobre el conjunto remoto.

## Compras MX: restricción autoritativa

`DEFERRED — SOURCE AUTOMATION RESTRICTED`, en capabilities de la fuente COMPRAS_MX.
No adapter/factory/parser. API rechaza habilitar o escanear incluso si enabled de DB fuese true;
Workspace muestra restricción y deshabilita adquisición. La accesibilidad manual del sitio
**no autoriza retrieval automatizado**. No nuevas solicitudes a Compras MX en esta continuación.
No solve/emulación/reverse engineering de PoW, reutilización de tokens/cookies de navegador,
anti-bot bypass ni browser diseñado para vencer el control. No sustituir procedimientos
actuales por CompraNet 3/5, contratos ni PAAASOP. Esas fuentes siguen fuera del slice.

Interfaz futura oficial/documentada y autorizada podrá registrarse detrás de DiscoveryAdapter,
con el mismo dominio/perfil/ScanRun. No se infiere el contrato actual desde nombres del bundle
ni se fabrican fixtures Compras MX. No se requiere migración para representar esta restricción.

## Workspace/API y validación

Selectores independientes: fuente para scan manual y fuente de tabla local (All sources/PEMEX/
CFE/Compras MX). Tabla neutral, número humano/ID, empresa/área, fecha/tipos/estados, explicación
de perfil y conteo de referencias. Buscar número/ID, descripción, empresa/área; filtros literales
y paginación local. Áreas de perfil explícitas, independientes de áreas de adquisición:
la opción CFE public no se confunde con Empresa. Selección explícita de una o varias fuentes de perfil (ninguna=todas), independiente de
la fuente de adquisición; conserva las restricciones de perfiles previamente guardados. Estado humano usa la misma revisión optimista. Sin cambio de navegación final.

Tests offline: formas públicas sanitizadas y registros sintéticos explícitos, tres batches,
217 únicos/218 filas, match sólo en último batch, dedup, retry/partial, cambios, sparsity,
seguridad y DB bounded. No calidad semántica o cobertura histórica certificada por mocks.
Live opt-in CFE sólo metadata: `LICITIA_DISCOVERY_CFE_LIVE=1` con intérprete backend obligatorio,
`python -m pytest tests/test_discovery_cfe_live.py`; fechas opcionales LICITIA_CFE_FROM/TO ISO.
Regresión normal excluye `local_ollama` y `live_discovery`. Detalles/resultado exacto/comandos
actuales: `backend/reports/m10_b/cfe_completion_report.md`, reportes locales no destinados a Git.

Resultados finales: backend 2452 passed / 3 opt-ins excluidos; frontend 168 passed / build PASS.
Focused CFE+PEMEX 62 passed. Live CFE 46 únicos / 5 batches / 364 referencias, sin binarios ni DB.
Fixture CFE 217 únicos / 218 filas / 3 batches / 39 SQL incluyendo lock; sin DB N+1.
Compileall/diff PASS; Alembic078; no stage/commit/push M10-B.
