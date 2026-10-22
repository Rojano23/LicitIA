# MVP-06.V — Blind Attempt #8: reporte operacional definitivo

**Resultado de cierre: FAILED — PRESERVED FOR RELEASE-GATE REVIEW.**

El harness canónico terminó con exit0, creó first_pass/FROZEN y no creó BLOCKED. El cierre operacional conservador se retiene como FAILED para revisión por una suspensión ambiental durante Vision: no puede certificarse el timeout como límite de tiempo de pared. No se adjudicó semánticamente el corpus ni se declara defecto de código, cierre MVP, UAT ni autorización de desarrollo adicional. No se rerunó el intento.

## Identidad y proveedores

- Run: `06v8_eaca60f950044a40a7e28cdd3e01fa86`.
- HEAD exacto inicial/final: `0b04fc7677e670fb487683ac904d3c3a89daa373`.
- Root: `/Users/ceciliavalencia/LiticIA/backend/.licitia-data-validation-06v8_eaca60f950044a40a7e28cdd3e01fa86`.
- Artefactos: `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v8_eaca60f950044a40a7e28cdd3e01fa86`.
- Bootstrap: `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v8_eaca60f950044a40a7e28cdd3e01fa86_bootstrap`; entorno establecido antes de Settings/database/main en procesos frescos, sin reset de caches ni fallback.
- Perfil DI_BLIND_SELECTIVE_001 / SELECTIVE_PERCEPTION / AUTO; blind-task-contracts-v1; perception-sufficiency-v2; DI_SELECTIVE_FREEZE_003.
- Puente native-table-relationships-v1 y ADR0017 committed/congelados. Se utiliza materialize_canonical → Scope materializer → adaptador Native normal → grounding/reconstruct_native_tables. Sin flags especiales ni configuración Tender-specific.

Phase0 y gate final: GET locales /api/version y /api/tags, sin inferencia: Ollama0.23.3, qwen3-vl:4b-instruct, digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`; manifest local coincide. No inicio/cambio de Ollama. Tesseract5.5.3 en /opt/homebrew/bin/tesseract, tessdata /opt/homebrew/share/tessdata/, spa+eng. Los proveedores reales sólo se ejecutaron después del marcador, dentro del harness.

## Reset, freeze y corpus

Se exportó la base previa mediante pg_dump antes de la secuencia committed dropdb/createdb/alembic, únicamente para licitia_validation_06v. Export previo y SHA preservados en bootstrap. Después se verificó cero tenders/documentos y root nuevo. Alembic current/head `20261013_req_perception_prov_072`; drift59 (55 add_index/4 remove_index), firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`, sin esquema/migración nuevos.

| Archivo bajo el directorio del intento | SHA-256 completo |
|---|---|
| execution_profile.json | a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6 |
| pre_execution.json | 89c46af142874ff9e7ef159a2e61d5f043dac256c361c893e2cfc5b2caccad28 |
| input_binding.json | e9483a1208dfb1f58bc4e3654c11eda347e752f71ba56b4e8c17a3bb0face621 |
| first_pass.json | 9d8861ed64520a832e4dfaac7ce0dbbbcc5a5d0fbc894c98d850777aa4f4eaef |

Los envelopes también contienen hash del payload; no se confunden con hash del archivo. Pre-freeze creado/verificado antes de importar. Original locators complementa el binding sin alterar contratos.

Import por POST /tenders y /documents/import productivos. Corpus completo: **11 originales**, incluida `.DS_Store`, enumerados con rglob+is_file, sin filtrar nombres ocultos. CORPUS COMPLETENESS GATE comparó filename/hash/size/MIME contra Attempt4: coincidencia exacta, cero faltantes/extras, todos bajo root nuevo. Gate preservado antes de input binding. Final gate repitió identidad freeze/binding/runtime/proveedor/corpus y hashes. EXECUTION_STARTED.json exclusivo creado por execute_frozen_run.

## First-pass y mediciones estructurales

FROZEN.json y first_pass.md/JSON preservados antes de toda derivación operacional. Export DB completo `database_first_pass.dump` y su identidad, hashes de todos los archivos del root en runtime_storage_manifest.json, eventos provider/planner y recibos conservados. Estados perceptuales/de interpretación derivados de los eventos congelados en perception_interpretation_states.json. Structured replay se registra por separado y no reescribe first-pass, IR ni DB.

Import11 / PDFs preparados10 / unsupported1 / fallos de preparación observados0. Native253 páginas:251 TEXT_EXTRACTED y2NO_TEXT;251 páginas con texto disponible en8documentos. `.DS_Store` pasa por producto normal; no exclusión manual. Import status11IMPORTED no equivale a preparación exitosa de11.

**Scope0 / Attributes0 / Quantities0.** IR de soporte persistido0, manifests0. Replay productivo sólo lectura del estado final:251fuentes Native +4OCR;2Vision STRUCTURE_ONLY excluidos del replay textual, no del pipeline. Bloques0, table-derived0, identidad positiva0, multilínea0, ambiguos0, relaciones header/row0 y campos provisionales de Attribute/Quantity0. Replay errors0; snapshot errors0. Este replay mide reconstrucción del estado congelado, no el total de instanciaciones históricas.

Históricos transitorios **NOT_DIRECTLY_MEASURABLE**: páginas realmente evaluadas por el puente durante ejecución, total de tablas detectadas/rechazadas/ambiguas, total de filas reconstruidas, candidatos Scope creados/grounding aceptado-rechazado/reconciliados, evidencia provisional histórica y rechazos de hijos por ownership/grounding. El harness no conserva esos contadores por tabla/candidato; cero persistidos no permite inventarlos. No se añadió instrumentación ni se inspeccionó semánticamente el corpus para completar esas métricas.

Manifests: creados/conservados0, verificados0, missing0, fallos hash/integridad0, referencias0, versiones observadas0. Multispan persistido0; no existe prueba positiva de manifests/ownership/geometría del corpus para certificar. La regresión sintética sí prueba esos contratos, con denominador distinto. No se afirma ausencia de tablas reales en el corpus.

## Percepción, OCR y Vision

| Métrica OCR (planes/resultados no son adquisiciones) | Conteo |
|---|---:|
| Planes / páginas evaluadas | 1257 / 253 |
| Native SUFFICIENT / INSUFFICIENT / UNKNOWN | 996 / 10 / 251 |
| Interpretación UNRESOLVED / NOT_ATTEMPTED | 1000 / 257 |
| Needed/eligible por déficit textual | 10 / 10 |
| Adquisiciones ejecutadas / páginas | 4 / 4 |
| Resultados COMPLETED / reusos | 10 / 6 |
| Fallidos / unavailable-deferred / budget exhausted / retry exhausted | 0 / 0 / 0 / 0 |
| Evitados por Native suficiente | 996 |

Native UNKNOWN corresponde a TEXT_TASK_CONTRACT_REQUIRED; no es déficit textual confirmado. Las996 interpretaciones UNRESOLVED con percepción suficiente no escalaron. Sin adquisición desde percepción SUFFICIENT. No se infiere necesidad semántica humana a partir de elegibilidad operacional. Suficiencia intermedia por tarea inmediatamente después de OCR: NOT_DIRECTLY_MEASURABLE; el first-pass no conserva esa serie temporal para cada tarea.

| Vision | Conteo |
|---|---:|
| Needed / eligible (planes espaciales explícitos) | 8 / 8 |
| Llamadas / fingerprints ejecutados / páginas | 4 / 3 / 2 |
| Llamadas STRUCTURE_SCOPE / DETAIL_TRANSCRIPTION | 2 / 2 |
| Completadas / fallidas | 2 / 2 |
| Retry adicional / retry exhausted | 1 / 1 |
| Budget exhausted / reusos | 5 / 0 |
| Avoided según contador canónico | 0 |

Diez resultados Vision: STRUCTURE_SCOPE4/DETAIL_TRANSCRIPTION6; no son10llamadas. Todos los8planes tienen VISUAL_REQUIRED. Avoided0 cubre los planes construidos, no las tareas que construct_tasks dejó de crear por suficiencia previa. No se equipara OCR legible con evidencia espacial.

Budgets congelados: OCR8calls/8pages,1adquisición/fingerprint,30s(timeout),60s techo aceptado, render2x/8Mpx/8MiB; ejecución4calls/4pages. Vision4calls/4tasks/4pages,2intentos/fingerprint,60s, tokens600/1000,JSONretry0; ejecución4calls/3tasks/2pages. Los7recibos (4OCR/3Vision) conservan máximos1/2. No aumentos, cambios de modelo/proveedor ni retry manual.

## Salvedad ambiental de timing y release gate

Evento canónico guard-597: DETAIL_TRANSCRIPTION FAILED, latencia registrada **923,927ms**; recibo final `VISION_PROVIDER_FAILED:['TIMEOUT:timed out']`, attempts2. El primer intento fallido registró57,805ms. Otros eventos Vision30,070/35,973ms, completados.

`pmset -g log` confirma Idle Sleep el2026-10-21 11:37:19-0600 por867s y Wake11:51:46-0600, dentro del intervalo de la llamada larga (evento escrito17:51:52UTC). Evidencia filtrada preservada en power_timing_observation.json. La suspensión explica el desfase de reloj; el tiempo activo efectivo es **NOT_DIRECTLY_MEASURABLE**. No se resta867s del contador canónico ni se afirma que el límite de60s de pared haya sido certificado.

El timeout configurado siguió60s y las llamadas/intentos no excedieron presupuesto. No hay defecto de código demostrado. Sin embargo, este pase definitivo tiene una interrupción ambiental y la certificación temporal queda pendiente: se conserva como **FAILED para revisión de release gate**, aunque el harness canónico terminó/FROZEN. No se crea BLOCKED canónico artificial, no se altera FROZEN ni se repara/rerun bajo este run_id. Nueva acción requiere decisión arquitectónica; no se autoriza automáticamente otro intento ni V.6e.

## Outputs, estructura, provenance y seguridad

Requirements31 / candidates43 / RequestedEvidence8; todos los31/8review-required. Estructura0trusted/253review/0unavailable. Review records292; conflictos2; stale carry0. Versiones ACTIVE11; SourceEffects0. Los estados trusted de DOCUMENTS/VERSIONS son metadata operativa, no certeza contractual.

Provenance por canal/capacidad disponible: Native251transcripción/251estructura;OCR4transcripción/4estructura;Vision0transcripción/2estructura. Todos review-required. Los slots totales253 por canal/capacidad incluyen unavailable y no son adquisiciones. Soporte multicapability por hecho: NOT_DIRECTLY_MEASURABLE al no haber Scope/children. Multispan persistido0.

Guard rejections0, llamadas sin plan/déficit0, calls desde percepción suficiente0. Todas las adquisiciones se relacionan con planes y déficits perceptuales (OCR INSUFFICIENT, Vision VISUAL_REQUIRED); INTERPRETATION_UNRESOLVED por sí solo no activó proveedor. Root Settings/env/freeze consistente, originales íntegros y dentro del root; sin fallback/path escape observado. Hijos sin padre0 (sin hijos). No se elevaron estructuras a trusted. Geometría inventada no observada; sin bloques positivos no se certifica cobertura o fidelidad geométrica del corpus. Controles de fuente/manifests se conservan; ninguna intervención semántica humana.

## Comparación operacional primaria

| Métrica | Attempt7 | Attempt8 |
|---|---:|---:|
| Native páginas | 253 | 253 |
| IR replay final | 0 | 0 |
| Scope | 0 | 0 |
| Attributes | 0 | 0 |
| Quantities | 0 | 0 |
| Manifests | 0 | 0 |
| OCR eligible / adquisiciones | 10 / 4 | 10 / 4 |
| Vision eligible / calls | 8 / 4 | 8 / 4 |
| Requirements / candidates / RequestedEvidence | 31 / 43 / 8 | 31 / 43 / 8 |
| Estructura trusted / review | 0 / 253 | 0 / 253 |
| Review records / conflictos | 292 / 2 | 292 / 2 |

Esto describe conteos; no decide corrección, recall, necesidad humana de percepción, suficiencia semántica ni release/UAT. La pregunta sobre outputs defendibles y el resultado semántico final queda a adjudicación separada; no se propone otra gramática.

## Regresión y preservación final

Regresión sobre licitia_test después del first-pass freeze, sin rerun Tender002. Comandos exactos en regression_commands.json; logs/JUnit en regression_*. Sin proveedores reales opt-in (not local_ollama).

Resultados finales: {"focused": {"passed": 538, "failures": 0}, "expanded": {"passed": 1121, "failures": 0}, "full": {"passed": 2077, "failures": 0}}.

Focused538passed/7warnings; expanded1121passed/1deselected/8warnings; full2077passed/1deselected/8warnings. RT22,SI39,MG15,ST44,SC/DC46,PS36,OCR44,Vision46,BR16,FB23,BH37; Scope/human-review/API e integraciones/DI incluidos. Compileall/diffcheck exit0. Conteos por módulo en regression_module_counts.json; comandos exactos y JUnit disponibles. Warnings heredados de SWIG/python_multipart, Alembic path_separator y Paddle ccache; ninguno representa test fallido.

Detalle de verificación final, Git, hashes y preservación: post_run_integrity.json y regression_results.json. Los artefactos operacionales y el reporte se hashean en operational_artifact_manifest.json; raw originales/recibos/manifests en runtime_storage_manifest.json; DB export identity separada.

Históricos Attempts1–7: 3056 archivos hash-verificados, cero alteraciones. Ni se repararon ni se movieron/reusaron freezes/roots/run_id. No cambio de source, stage, commit o push; HEAD permanece exacto y tracked clean. Archivos nuevos sólo bajo root/bootstrap/directorio propios y scripts efímeros de operación fuera de source. No se adjudicó semánticamente Tender002.

MVP-06.V BLIND ATTEMPT #8 FAILED — PRESERVED FOR RELEASE-GATE REVIEW
