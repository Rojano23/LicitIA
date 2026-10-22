# RC-H2 commit + RC-H3 Operational Recovery and Data Safety

Estado: COMPLETE — gates A–K verificados; listo para revisión arquitectónica. Quantity auditada DEFERRED P1 conforme al alcance autorizado.

## RC-H2

Commit y HEAD: `415669f3a42850971ef57bae031ce19a622340b4`.
Asunto: `feat(rc): connect workspace to canonical tender flow`.
Parent: `65b3465c35877408aafe15757d3e74aaddf10e36` (RC-H1).
16 archivos aceptados, sin reportes/runtime/env/artefactos históricos y sin push:

```
backend/app/blind_selective_harness.py
backend/app/canonical_materialization.py
backend/app/document_intelligence_blind_run.py
backend/app/main.py
backend/app/native_preparation.py
backend/app/workspace_flow.py
backend/tests/test_workspace_flow.py
docs/adr/0020-workspace-canonical-composition.md
docs/roadmap.md
docs/uat-capability-statement.md
docs/workspace-functional-flow.md
frontend/src/App.tsx
frontend/src/api/workspace.ts
frontend/src/components/WorkspaceFlow.test.tsx
frontend/src/components/WorkspaceFlow.tsx
frontend/vite.config.js
```

Al revisar el diff staged apareció whitespace al final del helper nuevo, omitido
por el diff previo de archivos no rastreados. Se retiraron sólo esas líneas vacías
y se ajustó el mismo commit autorizado. Ningún comportamiento cambió.
Git RC-H3: sin stage, commit ni push; HEAD sigue siendo el commit RC-H2 anterior.

## Inventario persistente

Inventario completo: `inventory_and_recovery_contract.md`; contrato definitivo:
`docs/adr/0021-local-backup-restore-safe-retry.md`.

- MUST BACK UP: DB completa con entidades/documentos, relaciones Scope→Quantity,
  revisiones/correcciones/notas, decisiones de evidencia/cumplimiento/alternativas;
  originales de Tender y biblioteca empresarial; manifiestos multispan; recibos
  OCR/Vision y último estado operacional Workspace.
- REGENERABLE pero incluido: páginas/texto/normalizaciones/chunks, propuestas/outputs,
  estructura y resultados OCR/Vision. Restaurar preserva sus IDs/generaciones; no se
  regeneran ni se llama al proveedor para sustituir evidencia revisada.
- EPHEMERAL: posesión de locks, PIDs, temporales/render, logs de servicios. El root
  de datos puede contener archivos lock vacíos que se copian sin restaurar su posesión.
- No se incluye entorno/venv/frontend instalado, pesos LLM, runtime.json/contraseña,
  roles globales PostgreSQL ni logs/configuración fuera del root de datos.

## Consistencia y formato

Backup canónico: toda la DB de aplicación + todo el root de datos + manifiesto.
Sólo instancia local RC-H1 detenida: lifetime operation.lock del launcher, sin
running.json, PID PostgreSQL, listeners configurados o locks de procesamiento activos,
y confirmación administrativa de todos los escritores detenidos. No es backup online
ni una garantía sobre procesos ajenos al despliegue canónico.

Se copian el clúster PostgreSQL apagado y storage. Se inicia únicamente el clon sobre
socket Unix privado sin listener TCP para validar referencias y producir pg_dump
custom. El clúster fuente no se inicia ni altera. Todo permanece local.

Formato **licitia-local-backup-v1**: `database.dump`, `storage/`, `manifest.json`.
Manifest tipado/estricto y serialización JSON determinista: fecha UTC, HEAD/hash de
código, Alembic, PostgreSQL 17, identidad opaca DB/root, categorías/rutas relativas,
SHA-256/tamaño por archivo, conteo de payloads (el manifiesto no se cuenta a sí mismo), estado VALIDATED y conteo de originales huérfanos.
El envelope incluye checksum del payload. La fecha es variable deliberadamente;
la serialización y el orden del inventario son deterministas.

Verificación independiente: formato/schema, envelope, inventario exacto sin faltantes
ni extras, categoría/ruta segura, tamaños/hashes; rechaza symlinks, hardlinks y special
files. No filtra dotfiles: `.DS_Store` sintético se incluye y sobrevive restore.
Antes de backup/restore se validan originales DB→archivo por hash/tamaño y manifiestos
referenciados por locator/hash/schema. Los huérfanos se conservan/cuentan, no se borran.

## Comandos administrativos y evidencia real

Desde raíz, con el launcher existente y sus dependencias locales:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python backend/scripts/licitia_local.py --config /private/tmp/licitia-rc-h1/runtime.json backup --backup-path /private/tmp/licitia-rc-h3-admin-backup --confirm-quiescent
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python backend/scripts/licitia_local.py --config /private/tmp/licitia-rc-h1/runtime.json verify-backup --backup-path /private/tmp/licitia-rc-h3-admin-backup
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python backend/scripts/licitia_local.py --config /private/tmp/licitia-rc-h1/runtime.json restore --backup-path /private/tmp/licitia-rc-h3-admin-backup --confirm-quiescent --confirm-restore
```

Ejecutados exclusivamente sobre el runtime privado de prueba RC-H1 con originales
sintéticos. Backup VERIFIED, 3 archivos (dump + dos originales), cero originales
huérfanos. Verificación independiente VERIFIED. Restore RESTORED; par anterior
retenido en `/private/tmp/licitia-rc-h1/.restore-648bbe1f3ab349bdb0ca91ca70a353de/prior`.
Los dos archivos restaurados coinciden con hashes del backup; permisos 0700/0600
verificados. Evidencias `admin_backup.json`, `admin_verify.json`, `admin_restore.json`,
`admin_restore_verification.json`. Este caso del launcher no certifica Scope: eso se
prueba en el E2E privado más completo descrito a continuación.

## Restore y preservación

Restore valida antes de modificar DB/storage actuales y construye una copia privada
verificada del backup que debe coincidir con el manifiesto inicial; sólo lee dump y
storage de ese snapshot, evitando mezclar generaciones si el origen externo cambia.
Crea un candidato aislado:
initdb con contraseña del destino, pg_restore single-transaction/exit-on-error, copia
de storage y validación de referencias/schema. No migra ni llama a proveedores.
Sólo tras validar cambia los directorios postgres/data; conserva el par anterior.
Un journal durable controla el swap de dos recursos, que no se presenta como una
transacción atómica única. Error durante swap provoca rollback. Un proceso terminado
entre renames deja journal y el launcher niega start; `recovery-status` y
`recover-restore --confirm-quiescent` revierten el swap incompleto o finalizan COMMITTED.

El E2E real usa un clúster PostgreSQL 17 nuevo y Alembic, PDF tabular genérico y API
normal: Tender/import/process, corrección humana Scope, backup, alteración del working
storage sintético, restore en otro root limpio con distinta contraseña, reinicio de
PostgreSQL/aplicación y consulta de la API.

Verifica dos Scope con dos Quantity y sus padres, originales/manifiestos/fuentes
accesibles, corrección/historial/nota humana y estado operacional. Recibos sintéticos
OCR y Vision conservan bytes/agotamiento exactamente. No son prueba de calidad de
proveedores. Un dump corrupto pero con envelope re-firmado coherentemente falla en
staging, sin destruir datos ya restaurados; una nueva reconexión/API vuelve a leerlos.
Detalle: `e2e_restore_result.json` y XML/log focal.

## Retry y seguridad de generaciones

Rutas aditivas GET `/tenders/{id}/workspace/recovery` y POST
`/tenders/{id}/workspace/retry` con expected_fingerprint. Antes de mutar, el servidor
revalida bajo el lock de Tender hash/tamaño del original, consistencia de páginas,
provenance estructurada, código/HEAD/paquetes, recibos y estados de proveedores.
Tareas de percepción con lock activo difieren el retry. Un fingerprint desactualizado
responde 409; un original alterado/ausente o evidencia inválida no se repara ni borra.

La identidad de código/configuración AVAILABLE_ONLY queda en el estado operacional;
si cambia, el estado pasa a STALE. Generaciones previas siguen sujetas a sus contratos
canónicos y revisión por fingerprint/snapshot. Datos H2 sin identidad se verifican
por fuente/evidencia antes de registrar una identidad actual. No se crea otra provenance.

Un fallo Native regresa a PENDING sólo sin páginas ni extracción previa; si ya hay
páginas o metadatos contradictorios, requiere revisión/soporte. Completado/interrumpido/
fallo parcial con fuente íntegra reutiliza Native y materializadores existentes.
Quantity puede reemplazar IDs según el contrato aceptado, sin multiplicar resultados
ni asignar por posición. Las revisiones humanas no se trasladan a otro ID/generación.

La prueba idempotente usa Scope/Quantity y requisitos/evidencia solicitada no vacíos,
corrección humana y manifests. Dos retry conservan conteos/contenido/ownership, historial
humano y conjunto de manifests. Hay casos de interrupción, parser temporalmente fallido,
fallo simulado tras materialización, original modificado/ausente, request stale,
identidad de código cambiada, lock activo e inconsistencia Native.

## Percepción parcial e interrupción

El retry normal es AVAILABLE_ONLY: no adquiere OCR/Vision, no aumenta budgets, no
borra recibos agotados y no convierte interpretación fallida en más percepción.
Las adquisiciones de proveedor existentes conservan su política y controles propios;
este slice no promete un retry automático adicional de OCR/Vision.

Un registro Vision UNAVAILABLE conserva Native/Camelot válido, se expone como
provider_degraded y mantiene revisión requerida. El fallo simulado de proveedor
muestra FAILED con resultados válidos conservados; retry no los duplica. Esa simulación
prueba control de flujo, no comportamiento/calidad de un modelo real.

Workspace distingue PROCESSING, INTERRUPTED, FAILED, PARTIAL, COMPLETED_REVIEW_REQUIRED,
STALE y completado sin revisión cuando procede. PROCESSING sin lock después de reiniciar
se muestra interrumpido. El test termina un proceso durante swap y recupera ambos
recursos; el E2E también demuestra reconexión DB y nueva instancia API. No se afirma
prueba de falla física de disco ni de reinicio completo del sistema operativo.

## Workspace, Quantity y esquema

Dos controles funcionales: Verificar recuperación y Reintentar de forma segura. No
escritura automática al montar; el usuario ve disponibilidad, diagnóstico, conservación
de resultados y percepción degradada. Si cambió el contexto o falta backend/storage,
se solicita verificar otra vez y no se ofrece retry sin evaluación. No rediseño final.

Quantity audited review: **DEFERRED P1**. La infraestructura persistida de Scope sólo
acepta correction.description y snapshot Scope. Otras revisiones también están ligadas
a sus entidades, no hay primitive genérica Quantity segura sin contrato/migración.
No se implementó subsistema paralelo ni se sobrescribió evidencia extraída. Su
aceptación/corrección independiente no se simula con notas del padre.

Sin migraciones/modelos nuevos. Alembic test: `20261013_req_perception_prov_072 (head)`.
Sin cambios a Camelot/Scope/Quantity/Attribute/Requirements/Evidence, prompts, providers,
budgets o política OCR/Vision. La recuperación es composición/estado operacional.

## Privacidad y offline

Backup y copias anteriores son confidenciales. Operación local 0700/0600, sin cloud,
roles globales/password administrativo/model weights innecesarios. La configuración
del destino se protege por separado. Hashes detectan corrupción, no autentican el
origen de un dump: restaurar sólo backups administrativos confiables. No cifrado
propio; administrador protege medios/copias conforme a su política.

No Internet requerido para backup/verify/restore/retry con dependencias locales ya
instaladas. PostgreSQL temporal usa socket Unix privado, no servicio externo. No
se inició/modificó Ollama ni se ejecutó un modelo real. No equivale a certificación
host-firewall, SO limpio o captura completa de red nativa.

## Validación final

| Validación | Resultado |
| --- | --- |
| RC-H3 RH301–RH312 y casos adicionales | 25 passed |
| Core | 206 passed, 1 skipped |
| Document Intelligence | 1,153 passed, 1 deselected |
| API | 70 passed |
| Full backend final | 2,171 passed, 1 deselected |
| Frontend | 89 passed (5 archivos) |
| Frontend build | PASS |
| compileall | PASS |
| Alembic licitia_test | 072, head; sin migraciones nuevas |
| git diff --check + whitespace de 5 archivos nuevos | PASS |
| Integridad histórica + hashes fuente finales | PASS |

Matriz nominal: `test_matrix.json`; conteos exactos XML: `test_counts.json`.
Comandos core/DI/API: `regression_commands.json`; focal/full finales:
`final_commands.json`; salidas finales: `final_results.json`. XML/logs correspondientes
están en este directorio. Los resultados finales sustituyen las corridas intermedias;
la corrida full interrumpida al corregir snapshot no se contabiliza como validación.

Focal desde backend:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_local_recovery.py tests/test_workspace_recovery.py -q --junitxml=reports/rc_h3/rh3_final.xml`.

Full desde backend:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m "not local_ollama" --junitxml=reports/rc_h3/full_final.xml`.

Frontend desde frontend: `npm test -- --reporter=dot`; `npm run build`.
Compilación desde raíz:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests backend/runtime_guard`.

Alembic desde backend:
`DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current`.

DB de regresión: licitia_test. E2E de instalación/restauración: clústeres privados
temporales con DB licitia_uat según el contrato del launcher, nunca licitia_dev.
Sin modelos reales; mocks/control de errores no certifican calidad semántica.
Warnings de la full final (42): deprecación python_multipart/SWIG, configuración
legacy de Alembic y ausencia de ccache en Paddle; sin fallos. No se modificaron
motores para silenciarlos. `semantic_freeze_check.json` confirma modelos, preparación,
materialización, planners, ejecutores/policies y protocolo blind protegidos sin cambios.

## Archivos RC-H3 exactos

19 archivos, inventariados en `implementation_files.json`:

```
README.md
backend/app/local_recovery.py
backend/app/main.py
backend/app/workspace_flow.py
backend/app/workspace_recovery.py
backend/scripts/licitia_local.py
backend/tests/test_local_recovery.py
backend/tests/test_workspace_recovery.py
docs/adr/0019-local-uat-deployment.md
docs/adr/0020-workspace-canonical-composition.md
docs/adr/0021-local-backup-restore-safe-retry.md
docs/local-deployment.md
docs/roadmap.md
docs/uat-admin-quickstart.md
docs/uat-capability-statement.md
docs/workspace-functional-flow.md
frontend/src/api/workspace.ts
frontend/src/components/WorkspaceFlow.test.tsx
frontend/src/components/WorkspaceFlow.tsx
```

La evidencia nueva está en `backend/reports/rc_h3/`, sin stage. Los artefactos previos
no se alteran. Integridad: 4,560 archivos históricos y 1,381 de Attempt #9/bootstrap
sin cambios ni faltantes. No hubo otra ejecución/adjudicación ciega ni tuning.

## Límites y siguiente gate

Sólo instalación canónica local PostgreSQL 17 y schema exacto. Requiere todos los
escritores detenidos, espacio para clon/dump/candidato/par anterior y dependencias
instaladas; no backup online, writers ajenos, tablespaces/links, cloud o GC. Retención
manual de backups/pares previos; no eliminar hasta aceptar restore y conservar copia
verificada. Si no se puede detener un PostgreSQL temporal se retiene staging para
soporte; no se elimina automáticamente un clúster vivo. Proveedores se recuperan por
sus rutas/políticas existentes, sin reset de budget. Quantity independiente sigue P1.

Recomendación RC-H4 conforme al backlog RC: instrucciones y protocolo de primera
UAT acompañada, disclosure de capacidades/límites, captura local de resultados y
medición operacional acotada, checklist del administrador y decisiones P0 pendientes.
Mantener UI provisional; Quantity review requiere aprobación arquitectónica separada
antes de cualquier migración. No ampliar semántica ni reabrir MVP-06.V.

RC-H3 técnicamente listo para commit después de aceptación arquitectónica; no queda
ningún gate obligatorio pendiente. Sin stage, commit ni push de RC-H3. La excepción
Quantity independiente sigue DEFERRED P1 y no se presenta como capacidad implementada.


LICITIA RC-H3 RECOVERY AND DATA SAFETY COMPLETE — READY FOR ARCHITECT REVIEW
