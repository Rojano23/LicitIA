# MVP-06.V — protocolo de primer pase ciego v1

V.0 prepara instrumentación y una base vacía. No autoriza localizar, abrir,
listar, hashear ni importar Tender #002. La autorización humana del corpus es
separada y posterior a la aceptación del preflight. No se construye Golden de
Tender #002 antes del primer reporte congelado.

## Identidades y configuración

Manifest: `backend/evals/document_intelligence_06v_config_v1.json`.
El `code_commit` es el HEAD base del preflight, no una promesa del futuro commit.
Los hashes de archivos de código/protocolo fijan exactamente la superficie
preparada sin introducir una referencia circular al SHA del commit que los
contendrá. El primer pase registra el HEAD real y exige código protegido limpio
más hashes iguales al manifest; exige también identidad pre-import y post-run
iguales. Los reportes runtime pueden quedar untracked. El manifest mismo, código,
pruebas, dependencias, migraciones y protocolo deben estar aceptados/committed
antes de un pase real; V.0 no hace ese commit.

El plan base usa AVAILABLE_ONLY y cero llamadas autorizadas a proveedores:
Native se prefiere cuando sea suficiente/confiable; Tesseract es elegible como
fallback de transcripción y Vision STRUCTURE como especialista bounded, pero
su **ejecución no está autorizada en este plan**. Habilitar un lote futuro exige
una autorización exacta y un manifest nuevo congelado antes de abrir el corpus.
No se usa AUTO ni se encadena acquisition de detalle desde estructura. Vision
full-page TRANSCRIPTION `qwen3-vl:4b-instruct` no es fallback automático bajo la
configuración calibrada (FAILED/OUTPUT_TRUNCATED/DONE_REASON:length). No se cambian
prompts, temperatura ni budgets. SEMANTIC_ASSIST conserva grounding/bounds/review,
sin proveedor instalado o ejecutado por defecto. Source Effect Qwen automático
continúa NO-GO. El plan preserva cobertura limitada como NO_EVIDENCE/UNSUPPORTED.

## Base aislada y procedimiento reproducible

URL futura exacta:
`postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v`.
V.0 sólo crea esta base e inicializa Alembic, verificando cero tenders/documentos.
No migra dev, copia Tender #001 ni configura un nuevo esquema.

Recrear es una acción destructiva futura: sólo con autorización explícita,
tras conservar los reportes/export necesarios, cerrar conexiones de esa DB y
confirmar que su nombre es exclusivamente `licitia_validation_06v`:

```sh
dropdb licitia_validation_06v
createdb licitia_validation_06v
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic upgrade head
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
psql -d licitia_validation_06v -c 'SELECT count(*) FROM tenders; SELECT count(*) FROM tender_documents;'
```

Este documento no ejecuta dropdb ni importa corpus. Filesystem futuro separado:
`backend/.licitia-data-validation-06v`, sin datos de dev/test. Preservar export y
reportes hasta aceptación humana; borrado posterior sólo explícito, sin streams
indefinidos de telemetría.

## Fases futuras — no ejecutadas en V.0

1. **06.V.1 FREEZE + IMPORT.** Aceptar preflight/código, confirmar commit limpio,
   manifest y paquetes/runtime. Antes de abrir corpus, capturar la identidad y
   base vacía mediante el comando siguiente, guardando stdout como
   `pre_import_identity.json` en una carpeta de ejecución local exclusiva:

   ```sh
   /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_06v.py --preflight --database-url postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v
   ```

   `--preflight` permite registrar dirty para revisión; **no es permiso de run**.
   Antes de importar se exige `protected_dirty=false`, revision072 y counts0.
   Sólo después de autorización humana explícita crear/importar mediante la API
   existente, con DATABASE_URL aislada y LICITIA_DATA_DIR separado. Registrar
   UUID/hash/versión durante la importación autorizada; nunca antes. Deshabilitar
   adquisición de modelos mediante `LICITIA_LOCAL_AI_ENABLED=false`; mantener el
   plan AVAILABLE_ONLY y cero OCR/Vision/LLM.
2. **06.V.2 FIRST BLIND PRODUCTION RUN.** Ejecutar extracción Native y las APIs
   productivas existentes, sin instalar adapters nuevos al ver resultados:
   Requirements discovery → normalization → requested Evidence; estructura
   AVAILABLE_ONLY → Scope details → quantities/attributes sobre detalles
   disponibles; versiones/Source Effects sustentados → resolución/proyección
   deterministas; review/matrices. Capturar hora real de inicio y fin, errores en un ledger `DI_BLIND_EXECUTION_LOG_001`,
   owners, provenance, todas las generaciones y resultados FAILED/DESELECTED.
   No convertir UNSUPPORTED o ausencia de candidatos en recall exitoso.
3. **06.V.3 FREEZE FIRST-PASS REPORT.** El script de instrumentación no ejecuta
   pipeline, importación ni proveedores. Sólo lee el resultado del paso anterior
   y emite JSON/Markdown para un run_id exclusivo:

   ```sh
   /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_06v.py --database-url postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v --authorized-import --tender-id <UUID_AUTORIZADO_DESPUES_DE_IMPORTAR> --run-id <RUN_ID_NUEVO> --started-at <ISO8601_INICIO_REAL> --ended-at <ISO8601_FIN_REAL> --start-identity <PRE_IMPORT_IDENTITY_JSON> --execution-log <EXECUTION_LOG_JSON> --output-root reports/blind_runs
   ```

   El flag sólo declara que existió autorización humana; no la sustituye. Código
   dirty o hashes distintos rechazan el freeze. Se verifican identidades contra
   el pre-import, y se registra DB/revisión/runtime/config/proveedores/source
   metadata y hashes prácticos. `FROZEN.json` es el marcador de finalización con
   SHA-256 de JSON y resumen. Un run_id existente, incluso incompleto, nunca se
   sobrescribe. Antes de analizar se verifica marker y hashes. Los UUID
   incidentales pueden diferir en otro run; cada snapshot conserva los suyos.
4. **06.V.4 HUMAN ADJUDICATION / ERROR ANALYSIS.** Sólo tras marker válido se
   admite verdad humana independiente, nunca derivada automáticamente de la
   salida LicitIA. `HumanTruth` exige autoridad/reviewer/revisión y SHA del primer
   pase. `freeze_analysis` emite `analysis_<id>.json` y su hash en ruta nueva;
   nunca reemplaza `first_pass.json` ni reutiliza un analysis_id. Modificación
   externa de reportes se detecta al verificar hashes.
5. **06.V.5 FINAL CROSS-TENDER GO/NO-GO.** Presentar métricas operacionales y
   adjudicadas por dominio, coverage y denominadores. Decisión humana para
   MVP-07 después de 06.V y cierre de MVP-06; no se adelanta aquí.

Desde la primera apertura y hasta freeze válido no se modifican prompts,
routing, thresholds, provider policy, normalization, conflictos ni semántica.
Una reparación operacional se documenta separadamente; invalida/reinicia el
run cuando altera identidades congeladas, nunca reescribe el primer resultado.
Cambios posteriores requieren otro pase/config/version y no alteran el primero.

## Métricas y denominadores congelados

`DI_BLIND_METRICS_001` y `DI_BLIND_FIRST_PASS_001` son contratos de evaluación,
no nuevas entidades contractuales. ORM collector usa queries acotadas al tender,
no hace flush/commit, y reutiliza DI, provenance reader y resolución/proyección
productivas sin acquisition. Desacuerdos/UNKNOWN quedan auditables.

First pass: documentos/páginas, availability por canal/capacidad, requisitos
canónicos y candidatos por separado, evidencia solicitada, Scope details,
attributes/quantities, ownership/binding no resuelto, versiones ACTIVE,
SUPERSEDED/REVOKED/review, effects, review por motivo/dominio/página/documento,
conflictos surfaced, stale carry, telemetría y enlaces de provenance entre
dominios. Toda source/runtime metadata disponible se conserva en snapshot;
no se depende exclusivamente de latest-summary.

Por dominio, total observado es el denominador: trusted proposal automático
no adjudicado / review / unavailable / rejected. Rates con denominador cero son
null. `trusted_automatic_unadjudicated` no significa correcto. Review no es fallo;
NO_EVIDENCE no significa ausencia de obligación real. La cola mide unidades
(domain,id); sus páginas/documentos afectados se deduplican. Los motivos no
provistos son UNSPECIFIED, no inventados. Perception→domain y Scope→children
miden enlaces trazables, no causalidad de error antes de revisión humana.

Telemetría: proveedor/modelo/capacidad/source_method, statuses, latencia disponible,
timeout y truncación. `calls` sólo suma conteos explícitamente registrados; un
artefacto persistido no demuestra cuántas llamadas/retries hubo. Si falta ese dato
es null/NOT_MEASURED. Native persistido no incluye runtime, así que tampoco se
inventa. `ProviderMetric` permite registrar call counts/latencia real cuando
existan; el plan base excluye inferencias. Los intentos/errores del pipeline se reciben en un ledger obligatorio
`ExecutionLog` con run_id/start/end coincidentes y ProviderMetric execution_event=true,
calls explícitos, modelo/capacidad/source/configuration/latencia. No se deducen de
artefactos. Ledger y pre-import se hashean en el reporte. Los intentos fallidos sin
artefacto también se conservan. Una ejecución OCR/Vision no autorizada por el plan
base deja marker `INVALID_PROTOCOL`, preservando resultados para auditoría; no se
presenta como ejecución válida ni se reescribe para ocultar la desviación.

Post-adjudication inicialmente TODO null: trusted_correct/incorrect, unsafe
contractual/structural, safe misses, unnecessary review, safe automatic selections,
critical conflicts correctamente surfaced, unsafe quantity/attribute bindings y
recall. La verdad aprobada etiqueta IDs de observación y casos humanos únicos:

- TRUSTED_INCORRECT: output confiado e incorrecto; structural flag cuenta subset
  estructural; unsafe_binding cuenta subset de Quantity/Attribute. No doble suma
  de esos subsets como errores contractuales independientes.
- SAFE_MISS: expectativa material no satisfecha que quedó review/unavailable/
  rejected, sin confianza insegura. No se etiqueta output trusted como safe miss.
- UNNECESSARY_REVIEW: output correcto que quedó review sin necesidad adjudicada.
- TRUSTED_CORRECT: output confiado confirmado correcto; sólo si automatic=true
  cuenta safe_automatic_selection.
- CONFLICT_SURFACED: conflicto de identificador observado y review, confirmado
  por humano; no basta con afirmar conflicto sin diagnóstico observado.
- MISSING: caso humano esperado sin registro observado. No se fuerza a encajar
  en output existente. Recall usa casos (dominio,truth_id) únicos adjudicados;
  numerator sólo casos correctos encontrados. Coverage parcial permanece explícita,
  no representa recall de todo el tender sin verdad exhaustiva independiente.

Stale carry es observable si UNKNOWN transportara outgoing confiable, reutilizando
el guard productivo; sin medición es null. Se reportan structural errors y errores
contractuales juntos con sus denominadores y solapamientos, no accuracy única.
No se fija una carga aceptable de revisión ni una latencia objetivo arbitraria.

## Recuperación 06.V.3a — pendiente de aceptación

ATTEMPT_1 permanece `BLIND_RUN_EXECUTION_BLOCKER`: run
`06v_6f6c60e697534a04abc3f922e698fef1`, primer pase SHA-256
`af9eeb1c94b79417033d6e533f4ca837ea94984a6085254392d39ff041fe5ead`.
No se sobrescribe ni se reclasifica como éxito. Los 11 ACTIVE del collector
representan estado observado; no acreditan descubrimiento de Source Effects,
que no se ejecutó. El contenido semántico de Tender #002 continúa protegido.

El driver genérico `prepare_tender_documents(db, tender_id=...)` de
`app.document_intelligence_blind_run` reemplaza el loop incondicional de
extracción del driver temporal V.2. Reutiliza la elegibilidad MIME/extensión del
endpoint PDF y los endpoints canónicos de extracción/normalización. El guard
PDF permanece intacto. Un original válido sin esa capacidad produce resultado
operacional tipado `UNAVAILABLE / UNSUPPORTED_NATIVE_CAPABILITY`, conserva
PENDING y no crea páginas, percepción ni provenance de extracción. El collector
existente refleja ese documento como unavailable; no cambia denominadores.

La ausencia de capacidad de un documento no aborta otros documentos soportados.
Identidad ajena/inexistente, original ausente, hash/tamaño inconsistente, estado
persistido inconsistente y error de parser se propagan explícitamente; no existe
catch-all que los convierta en unsupported. Las páginas Native completadas se
reutilizan y la normalización conserva su idempotencia. El driver no adquiere
OCR/Vision ni clasifica el soporte por contenido o nombre institucional.

V.3a sólo prueba fixtures sintéticos en licitia_test, sin reset/reimport/rerun
ni cambios a evidencia de ATTEMPT_1. ATTEMPT_2 exige aceptación humana,
commit/push, HEAD nuevo, manifest nuevo que congele los hashes de código/protocolo
actualizados (sin editar el manifest histórico), reset/reimport autorizado de la
DB de validación conforme al protocolo y run_id nuevo. Se identifica como
`BLIND ATTEMPT #2 AFTER DISCLOSED OPERATIONAL FIX`, nunca continuación del anterior.

## V.5a — perfil selectivo explícito (propuesto para aceptación)

El protocolo histórico `DI_06V_CONFIG_001`, `BlindConfig`, su CLI y AVAILABLE_ONLY
conservan cero adquisición. No se altera el manifest histórico ni se reclasifican
sus llamadas. El perfil nuevo `DI_BLIND_SELECTIVE_001` vive separado en
`blind_selective_profile.py`; su CLI es `scripts/run_document_intelligence_selective.py`.
Esto prepara un pase futuro; NO autoriza ni crea Attempt #3.

Perfiles:

- HISTORICAL_SAFE exige AVAILABLE_ONLY: Native/persistido, cero OCR/Vision.
- SELECTIVE_PERCEPTION permite AVAILABLE_ONLY (sólo gaps), ALLOW_OCR (OCR
  planificado) o AUTO (OCR y Vision planificados/budgeted). No usar AUTO legacy.
- No se permiten proveedores semánticos de Requirements/Scope/Source Effects
  instalados implícitamente; Source Effect LLM automático continúa deshabilitado.

### Contratos de tarea genéricos

Después de preparación Native canónica, el harness construye TEXT, STRUCTURE,
SCOPE, ATTRIBUTES y QUANTITIES por página. El planner exige evidencia suficiente;
texto no vacío no demuestra TEXT completo. UNKNOWN/review sin tarea OCR elegible
no se transforma en OCR por existir un logo. Regiones IMAGE canónicas con geometría
válida acotan adquisición de tareas pendientes; nunca se elige por archivo,
producto, página conocida, respuesta adjudicada ni conteo esperado.

`spatial_contracts` es una lista explícita congelada, sin IDs/páginas, de preguntas
STRUCTURE_SCOPE o DETAIL_TRANSCRIPTION que requieren IMAGE_LAYOUT_RELATIONSHIP.
Lista vacía significa ninguna necesidad visual declarada. Una imagen no crea ese
contrato: el responsable del futuro freeze debe aprobarlo como necesidad de tarea,
no como afirmación de que la imagen contiene una partida/tabla contractual.
Native suficiente evita el trabajo visual. Tras OCR se reevalúa el mismo contrato
textual; si ya es suficiente, no se ejecuta Vision. De lo contrario, sólo un
contrato espacial aprobado + binding de región canónica habilita el planner Vision.
Un fallo OCR por sí solo no construye contratos. No hay descubrimiento nuevo de
semántica visual ni tuning. Vectores sin binding IMAGE siguen pendientes.

Las tareas espaciales independientes no requieren OCR previo para su capacidad;
OCR de otras tareas textuales no constituye requisito de esa tarea Vision. Estructura
y detalle tienen planes, presupuestos y provenance independientes.

### Presupuestos y guard

OCR requiere `max_calls` agregado explícito, finito (0–10000), sin default derivado
del Tender; motor/version conocidos, idioma es+en/es/en, timeout default30/máximo60s,
2x, 8 millones de píxeles y 8 MiB. La elección del límite real se aprueba antes del
freeze; los fixtures sintéticos pueden usar límites pequeños. Se reserva antes de
invocar; indisponibilidad/fallo consume la reserva, sin fan-out a otro motor.

Vision comparte UN VisionBudget por pase: defaults 4 calls / 4 tasks / 4 pages,
2 intentos por fingerprint, 60s, 600 tokens estructura / 1000 detalle y retry JSON
interno0. El perfil permite reducirlos, no aumentarlos. Agotamiento permanece
pending explícito y no borra evidencia. El executor conserva agotamiento equivalente
entre ejecuciones. El pase completo no se reintenta bajo su misma identidad.

ProviderCallGuard registra planes y envuelve sólo las interfaces canónicas. Rechaza
llamadas no planificadas, política incompatible o configuración distinta del freeze;
no puede convertirse el rechazo en un resultado válido. Se registran eventos de
llamadas reales/simuladas y rechazos, con calls0 para rechazo, None cuando el ACK OCR
no demuestra si llegó a reconocer y diagnóstico aparte de reserva de presupuesto.
La selección/reuse/exhaustion de fingerprint permanece en los ejecutores aceptados.
El guard es control de flujo de esta aplicación, no sandbox contra código Python
arbitrario que invoque proveedores fuera del harness.

### Preflight sin inferencia y evidencia inmutable

CLI futuro (NO ejecutado aquí):

```text
python scripts/run_document_intelligence_selective.py <preflight|freeze|bind|execute>
  --profile <JSON_APROBADO> --database-url <URL_VALIDACION>
  --data-dir <FILESYSTEM_VALIDACION_AISLADO> --run-id <IDENTIDAD_NUEVA>
```

Usar exclusivamente `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`.
La URL debe ser local y apuntar a licitia_validation_06v; revisión072. La CLI no
resetea ni importa documentos. Reset/reimport requieren autorización aparte y el
procedimiento/API canónicos documentados arriba. No reutilizar el filesystem de
percepción de intentos anteriores ni eliminar recibos para reiniciar retries.

1. `preflight`: lectura de identidad DB y metadata local, sin inferencia ni corpus.
   Captura ejecutable/paquetes/versiones instaladas, candidatos tessdata/packs/hash,
   manifest/digest y presencia de blobs del modelo. No inicializa Paddle ni descarga
   pesos. Los probes Tesseract --version/--list-langs no reconocen imágenes. Si el effective
   tessdata no puede comprobarse, queda NOT_RUNTIME_CONFIRMED;
   servicio Ollama queda NOT_PROBED. La disponibilidad operacional debe confirmarse
   y autorizarse antes del pase real; presencia de paquetes NO certifica inferencia.
2. `freeze --authorized-freeze`: exige DB vacía, HEAD/código limpio y ADRs relevantes
   committed. Crea directorio exclusivo y `pre_execution.json` con perfil completo,
   presupuestos, runtime/availability, código/protocolo/ADRs, prompts/schemas,
   planner/policy/fingerprints y DB/revisión. No abre corpus. El run_id lo aporta
   la autorización humana; no se genera automáticamente.
3. Importar ciegamente mediante create_tender/import_documents con URL y data-dir
   aislados. `bind --authorized-import --tender-id <UUID>` crea input_binding.json
   separado, ligado por SHA al pre-freeze, antes de extracción/percepción. Incluye
   Tender/document IDs, originales/hash/tamaño/MIME/revisión y generaciones iniciales.
   No modifica pre_execution.json. Exige un único Tender y ninguna generación previa.
4. `execute --authorized-execution`: verifica código/perfil/runtime/input y escribe
   marcador exclusivo EXECUTION_STARTED. Ejecuta Native → tareas/suficiencia → OCR
   selectivo → reevaluación → Vision selectivo → materialización canónica → métricas.
   El materializador estructural consume AVAILABLE_ONLY; no tiene un segundo canal
   de adquisición legacy. Requirements/normalization/requested Evidence, Scope/hijos,
   Source Effects deterministas y proyecciones/collector conservan sus reglas.
5. Los eventos se conservan en archivos exclusivos bajo events/, incluso si el pase
   falla. first_pass.json/md y FROZEN.json cierran un éxito operacional; no certifican
   corrección semántica. Presupuestos, reuse, pending, fallos y fuentes quedan visibles.

Cualquier excepción/violación produce BLOCKED y preserva resultados parciales;
EXECUTION_STARTED impide repetir aun tras interrupción. No patch ni rerun bajo el
mismo run_id. Una corrección posterior a Attempt #3 requiere commit nuevo y Attempt #4.
Los errores esperados de proveedor se consumen sólo dentro del retry congelado;
no autorizan reparar código, cambiar motor, prompts ni presupuesto a mitad del pase.
Retener evidencia hasta aceptación humana; eliminación sólo explícita. Attempts #1/#2,
sus freezes/first-pass/adjudicación permanecen inmutables.
