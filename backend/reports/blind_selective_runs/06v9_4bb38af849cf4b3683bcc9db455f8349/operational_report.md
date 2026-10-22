# Blind Attempt #9 — reporte operacional final

**OPERATIONAL PASS — sin adjudicación semántica.** El pipeline committed produjo al menos un StructuredEvidenceBlock Camelot-proven del corpus real, Scope, Quantity y manifest persistidos. Estos hechos no certifican corrección contractual ni cierran el release gate.

## Identidad, gates y corpus

Run_id `06v9_4bb38af849cf4b3683bcc9db455f8349`. HEAD inicial/final `14097f428e2185152aae1b671485244f1656fb07`. Root aislado `/Users/ceciliavalencia/LiticIA/backend/.licitia-data-validation-06v9_4bb38af849cf4b3683bcc9db455f8349`. Entorno establecido con establish_environment ANTES de Settings/database/main en cada proceso fresco; sin fallback ni cache clearing. Perfil DI_BLIND_SELECTIVE_001 / SELECTIVE_PERCEPTION / AUTO, blind-task-contracts-v1, perception-sufficiency-v2, DI_SELECTIVE_FREEZE_003.

Ollama GET /api/version y /api/tags:0.23.3, qwen3-vl:4b-instruct, digest ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b. Sin inferencia durante readiness, sin iniciar/modificar servicio. Tesseract5.5.3 /opt/homebrew/bin/tesseract, /opt/homebrew/share/tessdata/, spa+eng. Camelot-py2.0.0 lattice/combined, camelot-native-table-proof-v1. Identidades/config/dependencies completas en pre-freeze.

Prevención de reposo `caffeinate -ims`, PID52678, activa antes de generar identidad y durante todo el pipeline. sleep_assertions_start.txt y sleep_log_start.txt bajo bootstrap; sleep_log_end.txt y host_awake_verification.json aquí. No eventos Sleep/Wake/DarkWake en TODO el intervalo de ejecución: ninguna llamada estuvo atravesada por suspensión. Logs de assertions con la palabra Sleep no son eventos de suspensión. No se infieren timestamps individuales no registrados; las duraciones wall-clock sí son canónicas.

Reset exclusivo de licitia_validation_06v mediante pg_dump→dropdb→createdb→Alembic; dump previo y SHA preservados bajo bootstrap. Cero tenders/documentos antes del pre-freeze. Alembic current/head20261013_req_perception_prov_072, drift59 (55add/4remove), firma3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7; verificado antes/después del reset y al cierre. Sin nuevas migraciones ni reparación de esquema.

Importación API productiva de11originales, `.DS_Store` incluido, sin excluir ocultos. Completeness gate ANTES del binding:11/11 filename/hash/size/MIME idénticos al binding histórico Attempt4, cero faltantes/extras, root aislado para todos. Gate PASS; no reparación. Locators canónicos complementan input_binding en original_locators.json; generations vacías al bind según contrato. El gate final revalidó identidad código/root/freeze/binding/runtime/provider y fuentes antes del marcador exclusivo.

| Artefacto | SHA256 archivo completo |
|---|---|
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349_bootstrap/execution_profile.json` | `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6` |
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/pre_execution.json` | `a969ae9550c3693526ffcda3188f3b65ab0f4de9e6e151f8ec24920f0f964433` |
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/input_binding.json` | `a9607abe42d6096524c7ef432020787377f4a1c581741940ec6f0df85d5a543f` |
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/EXECUTION_STARTED.json` | `e340774c20f3170fe17e63acebec316f8a596ed15addb5f62902c0887d1ee740` |
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/first_pass.json` | `8972172fd0c9c14ff2e20ba4e13e9c438bfee13d3fc8c5182af723c11972c1b6` |
| `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/FROZEN.json` | `d0bf745d7bfce01c1caa00ad47309a34b280f5cd70d558cd7983e21367e66df7` |

Los envelopes pre_execution/input_binding/first_pass tienen además hash de payload; FROZEN es marcador plano. EXECUTION_STARTED presente; FROZEN verificado; BLOCKED ausente. Ningún rerun del intento. First-pass congelado ANTES de métricas/replay/post-run; se sellaron 32 archivos derivados/originales del root en first_pass_artifact_manifest.json. No cambios posteriores a esos archivos.

## Import y Native

1Tender,11documentos,10preparados/1unsupported/0fallos de preparación; Native253páginas,251con texto disponible en8documentos. Estados documentales8TEXT_EXTRACTION_COMPLETE/2NO_NATIVE_TEXT/1PENDING. `.DS_Store` siguió comportamiento normal unsupported/PENDING, sin exclusión manual.

## Camelot / Native proof / IR

2StructuredEvidenceBlocks,2table-derived,2positive item identities;1tabla aceptada representada en proofs con12celdas;2proofs CAMELOT_NATIVE_TABLE_001,2manifests verificados,0missing/0hash failures/0proof replay failures.37palabras Native únicas probadas;24fragmentos literales entre ambos bloques, incluyendo encabezados compartidos. No confundir palabras con fragments IR.

2bloques multiline; relaciones:16HEADER_OF,8DESCRIBES_ITEM,2UNIT_FOR,2VALUE_FOR,6CONTINUES. Ownership estructural registrado en proofs; su corrección contractual permanece sin adjudicar. Los dos bloques conservan revisión requerida y no adquieren trust automático.

Eligible PDF pages, Camelot pages evaluated, tables proposed/rejected/ambiguous, total cells proposed, ambiguous fragment ownership/rejected relationships y bloques descartados: **NOT_DIRECTLY_MEASURABLE**. Sólo se preservan propuestas aceptadas en manifests; no hay trazas completas de todas las evaluaciones y no se reejecuta el detector sobre el corpus para inventar totales.1tabla/12celdas son el subconjunto aceptado, no el total propuesto.

## Scope / Quantities / Attributes

ScopeDetails persistidos2, review-required2; Quantities persistidas2, review-required2; Attributes0. Scope/Quantity conservan padres/Native provenance y revisión, no conclusión humana. Conteos intermedios de candidates creados, grounding aceptado/rechazado, reconciliación, provisional/parent-resolved/rechazado/ambiguo: **NOT_DIRECTLY_MEASURABLE**, no se sustituyen por conteos persistidos. No se agregaron métricas/código. Attributes0 no es fallo operacional por sí solo; la limitación conocida de semántica embebida continúa sin tuning.

## Percepción y proveedores

OCR:1257planes;996Native suficiente,10insuficiente,251UNKNOWN sin contrato textual.1000UNRESOLVED/257NOT_ATTEMPTED;996Native suficiente + interpretación no resuelta sin adquisición. OCR needed/eligible10/10;4adquisiciones/4páginas;10resultados completados incluyendo6reuse;0failed/0retryexhausted/0budgetexhausted;1247SKIPPED,996evitados por suficienciaNative y251por contrato ausente. Son tareas, no996páginas. No inferir que1000interpretaciones pendientes son déficit perceptual.

Vision:8needed/8eligible/VISUAL_REQUIRED;4calls en2páginas y3fingerprints de tarea;2completed/2failed;1retry adicional,1retryexhausted,5budgetexhausted;0reuse/0avoided canónico. Diez resultados del executor no significan diez llamadas. Avoided0 sólo cubre planes construidos, no todos los contratos espaciales potenciales.

Wall durations Vision (receipts por guard id):

- guard-524: 45217ms, COMPLETED
- guard-526: 60018ms, FAILED
- guard-528: 59355ms, FAILED
- guard-1164: 24877ms, COMPLETED

Dos fallos de DETAIL_TRANSCRIPTION conservados como fallos bounded. No se reclasifican como éxito ni se ajustan timeouts: uno registra60018ms, ligera sobrecarga wall del límite60s, sin suspensión. Flags timeout/truncated del guard permanecen tal como fueron registrados; no se inventan causas que el artifact no distingue.

OCR wall durations:

- guard-520: 1549ms, COMPLETED
- guard-1117: 2478ms, COMPLETED
- guard-1121: 1413ms, COMPLETED
- guard-1169: 2838ms, COMPLETED

Budgets intactos:OCR8acquisitions/8pages,1attempt/fingerprint,30s ceiling60s,2x,8Mpx/8MiB,spa+eng; Vision4calls/4tasks/4pages/2attempts,60s,600/1000tokens,JSONretry0, mismo modelo/digest. Guard sin violaciones. Las adquisiciones están ligadas a déficits textuales/espaciales explícitos; interpretación no resuelta sola no elevó percepción.

## Salidas / provenance

Requirements31, candidates43, rejected requirement candidates0, RequestedEvidence8. Structure0trusted/253review/0unavailable. Review296 (253structure+31requirements+8evidence+2scope+2quantity); conflicts2; stale carry0. No juicio semántico.

Native/OCR/Vision por capacidad y estados están en first_pass.json, metrics.first_pass.perception_availability y selective_metrics.provenance_capabilities; estos últimos son slots por capacidad, no adquisiciones. Native251available/2unavailable por capacidad; OCR4available/249unavailable; VisionSTRUCTURE2available/251unavailable y TRANSCRIPTION0available/253unavailable. Scope2Native/Quantity2Native; STRUCTURE253NATIVE_PDF. Multi-capability/multispan no tiene contador global canónico: los2manifests verificados son multispan; no se inventa un agregado de todas las combinaciones de provenance. Datos completos de provenance conservados en snapshot y root sellado.

## Comparación operacional con #7

| Métrica | #7 | #9 |
|---|---:|---:|
| IR | 0 | 2 |
| Scope | 0 | 2 |
| Attributes | 0 | 0 |
| Quantities | 0 | 2 |
| manifests | 0 | 2 |
| OCR eligible | 10 | 10 |
| OCR acquisitions | 4 | 4 |
| Vision eligible | 8 | 8 |
| Vision calls | 4 | 4 |
| conflicts | 2 | 2 |
| review records | 292 | 296 |
| Requirements | 31 | 31 |
| Requirement candidates | 43 | 43 |
| Requested Evidence | 8 | 8 |

#8 permanece histórico operacionalmente inválido por suspensión; no baseline temporal. Ningún aumento es calificado como correcto o mejora semántica.

## Seguridad y regresión

Código sin cambios, mismoHEAD committed limpio, staging vacío; perfiles/providers/budgets sin modificaciones. Sin configuración Tender/filename/página específica, sin texto Camelot promovido como cita, Native proof obligatorio, ownership ambiguo no admitido por contrato, V4a/V6c intactos. Hash/replay de cada manifest pasó; guard sin adquisiciones fuera de plan/budget. Sin cambios de schema.

Post-run (sólo licitia_test; NO rerun del Tender):

- focused: 570 passed, 7 warnings in 149.03s (0:02:29)
- expanded: 1153 passed, 1 deselected, 8 warnings in 138.27s (0:02:18)
- full: 2109 passed, 1 deselected, 8 warnings in 184.70s (0:03:04)
- compileall: PASS
- diff_check: PASS

Focused incluye CT/RT,SI/MG,ST,SC/DC,PS,Scope adapters/materializers,HumanReview/API,BR/FB/BH,OCR/Vision. CT32+RT22 incluidos; opt-in local_ollama excluido. Logs/JUnit/commands efectivos bajo regression/. Warnings heredados conservados, sin nuevos errores. Estas pruebas de contratos no adjudican calidad semántica real.

Históricos:4560archivos verificados intactos, Attempts1–8 y benchmark sin cambios. No source/stage/commit/push. Reportes nuevos untracked. Estado Git completo en git_status.txt. No nuevo slice ni rerun autorizado. Scripts operacionales de orquestación/reporte conservados por separado; no instrumentación de producción. El verificador auxiliar inicialmente intentó leer FROZEN como envelope, se corrigió a marcador plano antes de completar verificación; no cambió ningún artifact ni se repitió pipeline.

Bloqueadores operacionales:ninguno. Limitaciones: métricas internas no registradas se declaran NOT_DIRECTLY_MEASURABLE;2fallos Vision bounded; Attributes0; pendiente adjudicación semántica final. No se revisaron descripciones ni valores del corpus para decidir corrección.

LICITIA BLIND ATTEMPT #9 OPERATIONAL PASS — READY FOR FINAL MVP RELEASE-GATE ADJUDICATION
