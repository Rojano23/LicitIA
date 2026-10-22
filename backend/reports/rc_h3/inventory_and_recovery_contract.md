# RC-H3 — Inventario y contrato preliminar de recuperación

Estado: inventario operacional; protocolo completado con la continuación recibida. Contrato implementado y sujeto a validación final/revisión arquitectónica.
Baseline RC-H2: `415669f3a42850971ef57bae031ce19a622340b4`.
Commit `feat(rc): connect workspace to canonical tender flow`, 16 archivos, sin push.
Sólo se corrigieron dos líneas vacías finales del helper al verificar el diff staged;
ninguna función o comportamiento cambió respecto a la aceptación RC-H2.

## Inventario verificado en código

| Estado | Ubicación / contrato | Clasificación |
| --- | --- | --- |
| Tender, documentos, SHA/tamaño/revisiones, relaciones | PostgreSQL: `tenders`, `tender_documents`, entidades relacionadas | MUST BACK UP |
| Originales Tender | root/data `tenders/<uuid>/originals/<uuid>/<filename>` | MUST BACK UP, inmutables |
| Biblioteca empresarial y originales | PostgreSQL `companies`, `company_documents`, evidencia; root/data `companies/<uuid>/originals/...` | MUST BACK UP |
| Revisiones/correcciones/notas humanas | PostgreSQL `tender_scope_reviews`, `requirement_reviews`, revisiones/evaluaciones de evidencia, decisiones de cumplimiento y alternativas, overrides de clasificación/referencias | MUST BACK UP |
| Scope→Quantity/Attributes y procedencia | PostgreSQL `tender_scope_details`, `tender_scope_quantities`, `tender_scope_attributes` | REGENERABLE, pero MUST BACK UP en snapshot para conservar identidad y revisión |
| Texto/páginas/normalización/chunks | PostgreSQL `document_pages`, `normalized_content`, `document_chunks` y regiones | REGENERABLE, incluido para conservar generaciones y referencias |
| Resultados/perfil OCR/Vision/estructura | PostgreSQL `page_ocr_results`, `document_vision_analyses`, `document_vision_page_results`, resoluciones de estructura | REGENERABLE mediante adquisición; incluir, no ejecutar proveedor para restaurar |
| Requirements y Requested Evidence | PostgreSQL candidates, requirements, semantics, expectations, enlaces y versiones | REGENERABLE, incluir para conservar revisiones y referencias |
| Manifiestos multispan | root/data `provenance/structured-evidence-v1/<sha>.json` | MUST BACK UP; sus hashes enlazan la evidencia persistida |
| Recibos y límites OCR | root/data `ocr-task-receipts-v1/*.json` | MUST BACK UP para continuidad de fingerprint, adquisiciones e intentos |
| Recibos y límites Vision | root/data `vision-task-receipts-v1/*.json` | MUST BACK UP para continuidad de fingerprint, adquisiciones e intentos |
| Último procesamiento Workspace | root/data `workspace-processing-v1/<hash>.json` | MUST BACK UP; PROCESSING sin lock vivo debe verse interrumpido |
| Locks de archivos | root/data `*.lock` operacionales | EPHEMERAL; no copiar un lock adquirido como garantía de exclusión futura |
| Temporales/render/subprocesos de extracción | temporales controlados del sistema | EPHEMERAL; no requeridos para continuidad de datos persistidos |
| Configuración de destino | runtime.json, DSN/password/puertos/root | Secretos administrativos: conservar fuera del backup de datos; restore debe usar configuración privada del destino |
| Entorno Python/frontend/modelos | venv, frontend/node_modules/dist, pesos Ollama | REGENERABLE mediante instalación aceptada; no incluidos como datos del usuario |
| Logs/PIDs/auditoría de sockets | services.log, postgres.log, network.jsonl, running.json/postmaster.pid | EPHEMERAL para continuidad; no restaurar PIDs ni secretos incidentales |
| Historia de validación ciega | repositorio/reports y roots históricos separados | Fuera de la operación normal de backup/retry; preservar sin inspección/reutilización |

«Regenerable» no autoriza excluir tablas del snapshot: un restore debe conservar
la identidad exacta de los datos y sus decisiones humanas. El formato propuesto
incluye toda la base de aplicación y todo archivo de datos necesario, no sólo Tender.
No se descartan originales por nombre oculto. No se inspeccionó Tender #002.

## Contrato propuesto antes de implementar

Unidad canónica: dump lógico completo de la DB de aplicación + snapshot del root de
datos + manifiesto versionado con checksums SHA-256, tamaños, rutas relativas,
categorías, fecha UTC, HEAD, revisión Alembic y metadatos operacionales sin DSN/password.
Los pesos de modelos, credenciales/roles globales y entorno instalable se excluyen.
El artefacto contiene información confidencial y debe permanecer local, 0700/0600.

Consistencia: respaldo únicamente con aplicación/quienes escriben detenidos,
exclusión del launcher y comprobación de estado de procesos/DB. No basta con copiar
archivos mientras pg_dump toma un snapshot: los escritores filesystem también deben
estar detenidos. El launcher H1 ya mantiene operation.lock durante start y conserva
identidad de procesos. Debe reutilizarse y extenderse; no crear scripts alternos.
No se implementará una operación concurrente de backup sin garantía de quiescencia.

Restore debe verificar formato, inventario completo, checksums, tipos/rutas/links,
compatibilidad de esquema/versión y destino antes de tocar la instancia vigente.
Preparar DB y storage en staging; conservar el estado anterior hasta validar el
candidato. Un error de validación no debe modificar el destino. Si son necesarios
varios renames, definir journal/rollback y recuperación de interrupción para no
presentar un swap de dos recursos como una transacción atómica inexistente.

## Riesgos/retry encontrados en código actual

- Native preparation reutiliza páginas completas sólo con identidad coherente,
  hash y tamaño del original, número de páginas/generación válidos.
- `extract-pages` puede reemplazar páginas al invocarse directamente; no es un
  retry inocuo para evidencia con hijos y revisiones. No usarlo ciegamente.
- Un fallo del parser persiste TEXT_EXTRACTION_FAILED. El driver canónico rechaza
  ese estado sin recuperación explícita; hay que definir recuperación segura
  acotada sin borrar páginas ni decisiones válidas.
- Scope puede conservar su identidad cuando coincide su fingerprint. Quantity
  puede regenerar ID; probar conteo/contenido/ownership, no estabilidad inventada.
- Recibos OCR/Vision ya conservan fingerprint, identidad de generación e intentos.
  Retry normal debe respetarlos; no borrar recibos ni elevar budgets para reintentar.
- Estado Workspace persiste último intento; sin lock, PROCESSING se lee INTERRUPTED.
  Hay camino de consulta, pero debe explicitarse elegibilidad y efecto de retry.
- Configuración/identidad de procesamiento debe distinguirse de la fuente, sin crear
  otro modelo de provenance ni mezclar evidencia vieja con otra generación.
- Fallo opcional de proveedor no autoriza invalidar Native/Camelot ya sustentado.

## Quantity review

ADR-0007 y constraints de `TenderScopeReview` restringen correction a descripción,
snapshot de Scope y no Quantity. Otros reviews están ligados a sus propias entidades;
no se encontró una entidad genérica persistida con soporte Quantity reutilizable sin
nuevo contrato/migración. Conservar P1: no implementar subsistema paralelo, no
sobrescribir extraído, no interpretar nota Scope como corrección Quantity.
No crear migración sin revisión arquitectónica, conforme al prompt recibido.

## Plan aplicado (contrato definitivo en ADR-0021)

1. Contrato de backup, validación de storage y quiescencia integrado al launcher H1.
2. backup / verify-backup / restore y estado de recuperación con staging y rollback.
3. Retry normal condicionado a identidad y estado, con API/Workspace mínimos;
   ninguna modificación a protocolo/historia ciega ni semántica de extracción.
4. E2E genérico sobre instancia de prueba: importar/procesar/revisar → backup →
   alterar estado de prueba → restore/reinicio → comprobar relaciones y revisiones.
5. Casos de corrupción, destino activo, interrupción, proveedor fallido, reconexión,
   idempotencia y generaciones; pruebas frontend donde cambie el flujo.
6. Documentación operacional y ADR, regresión conforme a los comandos finales del prompt.

Superficie prevista: launcher RC-H1, módulo de recuperación/backup de infraestructura,
composición de Workspace/retry y pruebas/guías correspondientes. Sin cambios de
schema, semántica, modelos, budgets, diseño final ni artefactos históricos.
