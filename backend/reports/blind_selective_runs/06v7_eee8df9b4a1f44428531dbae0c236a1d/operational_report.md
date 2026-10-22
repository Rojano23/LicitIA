# MVP-06.V — Blind Attempt #7: reporte operacional final

Resultado: OPERATIONAL PASS. First-pass congelado antes de toda derivación de métricas.
No adjudicación semántica, cierre de MVP ni inicio de UAT.

## 1. Preflight, identidad y almacenamiento

- Run: `06v7_eee8df9b4a1f44428531dbae0c236a1d`.
- HEAD inicial/final: `429bf2ff95043c6d74af379a22d85bdd85843340`.
- Root aislado: `/Users/ceciliavalencia/LiticIA/backend/.licitia-data-validation-06v7_eee8df9b4a1f44428531dbae0c236a1d`.
- Bootstrap operacional: `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v7_eee8df9b4a1f44428531dbae0c236a1d_bootstrap`; proceso fresco antes de Settings en cada fase.
- Perfil DI_BLIND_SELECTIVE_001 / SELECTIVE_PERCEPTION / AUTO.
- Task policy blind-task-contracts-v1; perception policy perception-sufficiency-v2.
- Execution-profile SHA-256: `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`.
- Código limpio/committed, staging vacío; hashes de 300 archivos congelados verificados al cierre.

Ollama se consultó no inferencialmente mediante GET /api/version y /api/tags:
versión0.23.3, qwen3-vl:4b-instruct, digest
`ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`.
No se inició, detuvo ni modificó el servicio/modelo. Tesseract5.5.3,
/opt/homebrew/bin/tesseract, /opt/homebrew/share/tessdata/, spa+eng.
Paddle instalado/no seleccionado. Perfiles, prompts, schemas, timeouts, budgets y retries sin cambios.

## 2. Reset, Alembic y freeze

Reset autorizado únicamente de licitia_validation_06v, tras pg_dump preservado
en bootstrap/pre_reset_database.dump y SHA en pre_reset_export_identity.json.
Se verificó cero tenders/documentos antes del freeze. Alembic current/head
`20261013_req_perception_prov_072`, drift59 (55add_index/4remove_index), firma
`3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`.
Verificado antes/después del reset y después del pipeline; cero drift nuevo, sin reparación.

| Artefacto relativo a este directorio | SHA-256 del archivo completo |
|---|---|
| pre_execution.json, DI_SELECTIVE_FREEZE_003 | 51c75177a2cbb6c118caa34ea5478a29f77749a8c09b6c830183c07b6dac0539 |
| input_binding.json | 18bea5507bf9b2eac5b0eeb11af4de1809516cbd2414ec109778f7d4220b115b |
| first_pass.json | 90196c185f2083d3136c8c391048feebbf215d11355c563518ba06713b735fe2 |

Los envelopes conservan además SHA de su payload canónico; son digests diferentes.
EXECUTION_STARTED.json fue creado exclusivamente por execute_frozen_run después del gate final.
FROZEN.json presente/verificado. BLOCKED.json ausente. No rerun ni reparaciones.

## 3. Importación completa y binding

Tender `823d87da-f5b0-40e8-acac-1fcb4e551c67`. API canónica POST /tenders y
POST /tenders/{id}/documents/import mediante TestClient. Se enumeraron todos los
archivos con rglob('*') + is_file, sin descartar ocultos ni usar nombres para semántica.
11 fuentes /11 originales importados /11 documentos; sin faltantes, extras,
duplicados ni rechazos. `.DS_Store` presente como input y PENDING/unsupported
por comportamiento normal del producto; no exclusión manual.

CORPUS COMPLETENESS GATE PASS antes del binding: filename/SHA256/size/MIME
coinciden exactamente con los11 originales del binding histórico de Attempt4,
baseline semántico válido separado de Attempts5/6. Todos los originales se verificaron
por hash/tamaño y permanecen dentro del nuevo root. Gate persistido en
corpus_completeness_gate.json. original_locators.json complementa el binding
con rutas canónicas; no se agregaron campos al contrato ni se mutó el pre-freeze.
El gate final volvió a verificar originales, binding, código, runtime y proveedor.

## 4. Preparación y percepción

Preparados10 /unsupported1 /fallos0;253 páginas Native,251 con texto disponible
en8 documentos. Dos documentos NO_NATIVE_TEXT; el unsupported sigue PENDING.

| Percepción OCR, unidad tarea/plan | Conteo |
|---|---:|
| Planes OCR evaluados | 1257 |
| Native suficiente | 996 |
| Native insuficiente | 10 |
| Native UNKNOWN por contrato TEXT ausente | 251 |
| Suficiente + interpretación UNRESOLVED, sin adquisición | 996 |
| OCR needed/eligible según planner | 10/10 |
| OCR evitado por Native suficiente | 996 |
| OCR adquisiciones reales /páginas | 4/4 |
| OCR completado fresco | 4 |
| OCR resultados completed incluyendo reuse | 10 |
| OCR reused | 6 |
| OCR failed /budget-exhausted /ACK desconocido | 0/0/0 |

Interpretación de planes OCR:1000UNRESOLVED/257NOT_ATTEMPTED; no son
1000 déficits perceptuales. Las10 brechas son REQUESTED_REGION_TEXT_NOT_COVERED.
OCR restantes1247 decisiones SKIPPED:996 por interpretación pendiente con percepción
suficiente y251 por TEXT_TASK_CONTRACT_REQUIRED. Los contadores son tareas, no
996 páginas ni996 documentos.

Cuatro fuentes OCR finales cumplen SUFFICIENT para intentar una tarea textual Scope
en evaluación sólo lectura del snapshot congelado. Esta derivación no es el estado
intermedio histórico de todos los planes ni prueba de suficiencia espacial.
El valor para cada tarea textual inmediatamente después de adquisición queda
NOT_DIRECTLY_MEASURABLE.

| Vision | Conteo |
|---|---:|
| Planes needed/eligible con déficit espacial explícito | 8/8 |
| Evitado por suficiencia Native/OCR, contador canónico | 0 |
| Llamadas reales | 4 |
| Tareas/fingerprints /páginas ejecutados | 3/2 |
| Completadas /fallidas | 2/2 |
| Retry adicional /retry-exhausted | 1/1 |
| Resultados budget-exhausted | 5 |
| Reused | 0 |

Los8 planes son VISUAL_REQUIRED. Diez resultados incluyen2COMPLETED,2FAILED,
1RETRY_EXHAUSTED y5BUDGET_EXHAUSTED; no son10planes ni10llamadas.
La métrica avoided0 se refiere a planes Vision construidos; no cuantifica tareas
espaciales que construct_tasks dejó de crear por Native suficiente. No inferir
calidad ni necesidad humana de las adquisiciones a partir de elegibilidad.

## 5. StructuredEvidenceBlock, Scope, children y manifests

Reconstrucción productiva sólo lectura del estado final:251 fuentes Native +4OCR;
2fuentes Vision STRUCTURE_ONLY no proveen detalle textual y se excluyen explícitamente
de esa medición, no del pipeline. Reconstruct devuelve0bloques; positivos item0,
multilínea0, header/row0, OCR-fragment0, ambiguos0 y campos provisionales observados0.
Es un replay determinista sobre evidencia congelada, no un contador histórico de
instanciaciones durante planning/materialización.

Manifests creados/conservados0, verificados0, referencias persistidas0,
missing0, hash/integrity failures0, versiones distintas0. No existe un ejemplo
positivo multispan de este pase que certificar. Zero manifests no equivale a
certificar cobertura o recuperación correcta.

Persistidos: Scope0 /Attributes0 /Quantities0. Candidatos multispan conservados0.
Los siguientes conteos históricos transitorios son NOT_DIRECTLY_MEASURABLE:
Scope candidates formed, grounding accepted/rejected, reconciled logical candidates,
review-required candidates previos a persistencia, evidencia provisional total de
Attributes/Quantities y rechazos por ownership no resuelto. No se inventan valores
a partir de cero persistidos. Los campos provisionales del replay son0 y tienen
un denominador distinto. Sin nueva extracción ni cambios de código para instrumentarlos.

## 6. Outputs, estructura, revisión y provenance

Requirements31 /requirement candidates43 /Requested Evidence8; Requirements y
Requested Evidence conservan review. Scope/Attributes/Quantities0/0/0.
Estructura0trusted/253review/0unavailable. Review records292, conflictos2, stale carry0.
Versiones ACTIVE11, Source Effects0. No decisión humana o contractual automática.

Provenance disponible por página/capacidad: Native251transcripción/251estructura,
OCR4transcripción/4estructura, Vision0transcripción/2estructura, todos review.
Native253páginas, OCR4filas y Vision2resultados persistidos. Los253slots por
canal/capacidad incluyen UNAVAILABLE y no representan adquisiciones. No hay
Scope multicapability persistido que medir; distribución de soporte multicapability
por hecho queda NOT_DIRECTLY_MEASURABLE al no existir esos hechos.

## 7. Presupuestos, recibos y seguridad

OCR4/8calls y4/8páginas;4calls restantes; ningún fingerprint supera1adquisición.
Vision4/4calls,3/4tasks,2/4pages;0calls restantes; máximo2intentos por fingerprint.
60s Vision,30s OCR, tokens600/1000, retry JSON0, render2x/8Mpx/8MiB sin cambio.
Dos fallos Vision quedaron dentro de la política bounded y permanecen visibles;
no son excepción de protocolo ni autorización para reparar/repetir el pase.

Todas las8llamadas reales se vinculan a decisiones/planes: OCR con INSUFFICIENT
y Vision con VISUAL_REQUIRED;0llamadas desde percepción SUFFICIENT.
Guard rejections0; no llamada no planificada observada.996 interpretaciones
UNRESOLVED con percepción suficiente no generaron adquisición. Necesidades
perceptuales genuinas según el contrato del planner conservaron elegibilidad
y ejecución. Esto verifica controles de flujo, no necesidad semántica adjudicada.

Identidades/hash de recibos, originals, páginas, OCR y payload Vision verificados
sólo lectura. Sin fallback/path escape observado; root congelado coherente.
Native/OCR permanecen presentes después de Vision. No se modificó provenance
por el operador. No se certifica la fidelidad semántica de citas/modelo sin adjudicación.
Manifests missing/failures0, sin ejemplo positivo; controles positivos cubiertos
por regresión sintética SI/MG. Estructura trusted0 y stale carry0 permanecen seguros
bajo invariantes operacionales, no se declara corrección de toda estructura.

## 8. Comparación operacional

| Métrica | Attempt2 | Attempt4 | Attempt7 |
|---|---:|---:|---:|
| Documentos | 11 | 11 | 11 |
| Preparados/unsupported | 10/1 | 10/1 | 10/1 |
| Páginas Native | 253 | 253 | 253 |
| OCR needed/eligible | — | 80/80 | 10/10 |
| OCR adquisiciones | 0 | 8 | 4 |
| OCR budget-deferred | — | 62 | 0 |
| OCR avoided por suficiencia | — | 0 | 996 |
| Vision needed/eligible | — | 78/78 | 8/8 |
| Vision calls | 0 | 4 | 4 |
| Vision completed/failed | — | 1/3 | 2/2 |
| Scope/Attributes/Quantities | 0/0/0 | 0/0/0 | 0/0/0 |
| Requirements/candidates | 31/43 | 31/43 | 31/43 |
| Requested Evidence | 8 | 8 | 8 |
| Structure trusted/review/unavailable | 2/249/2 | 0/253/0 | 0/253/0 |
| Review/conflicts | 288/1 | 292/6 | 292/2 |

Baselines operacionales históricos autorizados; no se abrieron adjudicaciones
semánticas para esta comparación. Attempts5 y6 no son baseline semántico.
Reducción de elegibilidad no demuestra por sí misma corrección/necesidad humana.
Este pase no demuestra materialización nueva de Scope/hijos y no ofrece un
ejemplo positivo multispan. Las preguntas de correctness/recall/unsafe outcomes
quedan pendientes de adjudicación humana separada.

## 9. Regresión posterior al FROZEN

- SI/MG54PASS; SI21–23/PS36PASS; ST24PASS; SC/DC46PASS.
- OCR44PASS /Vision46PASS; BR16 /FB23 /BH37PASS.
- Adapters/materializers estructurados83PASS dentro de la focalizada.
- Focalizada: 409 passed, 7 warnings in 47.92s.
- Ampliada DI/MVP-06.V: 1099 passed, 1 deselected, 8 warnings in 92.39s (0:01:32).
- Suite completa: 2055 passed, 1 deselected, 8 warnings in 142.94s (0:02:22).
- compileall app/scripts/tests PASS; git diff --check PASS.

Pruebas sólo licitia_test. Única exclusión explícita local_ollama.
Warnings conocidos:SWIG/python_multipart/Alembic path_separator/Paddle ccache.
No se silenciaron warnings; mocks no acreditan calidad semántica/visual real.
Logs y JUnit XML preservados aquí. Comandos exactos, cwd backend:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_structured_interpretation.py tests/test_structured_grounding.py tests/test_perception_sufficiency.py tests/test_structural_trust_safety.py tests/test_native_structured_coverage.py tests/test_selective_ocr_recovery.py tests/test_selective_vision_recovery.py tests/test_blind_data_root_bootstrap.py tests/test_blind_freeze_evidence.py tests/test_blind_selective_harness.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py -q -m 'not local_ollama' --junitxml=/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v7_eee8df9b4a1f44428531dbae0c236a1d/regression_focused.xml
```

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_perception_sufficiency.py tests/test_structured_interpretation.py tests/test_structured_grounding.py tests/test_blind_data_root_bootstrap.py tests/test_blind_freeze_evidence.py tests/test_blind_selective_harness.py tests/test_selective_vision_recovery.py tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_structural_trust_propagation.py tests/test_scope_details.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attributes.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_integration.py tests/test_scope_quantities.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_review.py tests/test_scope_review_api.py tests/test_alternative_compliance.py tests/test_alternative_compliance_api.py tests/test_documents.py -q -m 'not local_ollama' --junitxml=/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v7_eee8df9b4a1f44428531dbae0c236a1d/regression_expanded.xml
```

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama' --junitxml=/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v7_eee8df9b4a1f44428531dbae0c236a1d/regression_full.xml
```

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
git diff --check
git diff --stat
git status --short
```

## 10. Integridad, Git y límites

Históricos y roots de Attempts1–6: 1660/1660 archivos verificados
por SHA256, cero diferencias. Incluye Attempt5 environment failure y Attempt6
incomplete-corpus pre-execution failure, conservados sin reparación/reuso.
Los 30 archivos runtime del root7 permanecen idénticos al manifest.
Código/protocolo/ADRs/config, pre-freeze/binding/first-pass y summary sin cambios.
Export DB first_pass_database.dump y SHA en database_export_identity.json.
Originales, recibos/locks, snapshot, ledger y budgets preservados para revisión.

HEAD exacto; tracked worktree limpio, staging vacío, diff stat vacío,
diff check PASS. post_run_git_status.txt conserva el status completo con
reportes/históricos untracked. Sólo artefactos runtime nuevos de Attempt7
en este directorio, bootstrap y su root; sin source edits, stage, commit o push.
Sin nuevo run, rerun, cambio provider/model/budget/policy ni reparación.

Sin blocker operacional de regresión/protocolo al cierre. Pendientes: adjudicación
semántica, límites de métricas transitorias y ausencia de evidencia positiva de
IR/Scope/hijos/multispan. No se declara MVP cerrado ni se inicia UAT.

MVP-06.V BLIND ATTEMPT #7 OPERATIONAL PASS — READY FOR FINAL SEMANTIC ADJUDICATION
