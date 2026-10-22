# MVP-06.V — Blind Attempt #4: revisión operacional

Decisión operacional final: PASS. No certifica calidad semántica.

## Identidad y preflight

Attempt #4 / run `06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba`.
HEAD inicial/final: `a24a5b18fe43ca15a949408b77e19aea1f2950a4`.
Root aislado: `/Users/ceciliavalencia/LiticIA/backend/.licitia-data-validation-06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba`.
Perfil DI_BLIND_SELECTIVE_001 / SELECTIVE_PERCEPTION / AUTO, task policy blind-task-contracts-v1.
Profile SHA-256: `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`.

Bootstrap comprometido establish_environment se invocó ANTES de config/database/main en cada proceso. Root preparado explícitamente, existente/escribible, coincidente con Settings y root congelado; no cache resets. Preflight no inferencial verificó HEAD/índice/working tree, Alembic072 y59 diferencias (55add_index/4remove_index), firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`.

Tesseract5.5.3, ejecutable /opt/homebrew/bin/tesseract, tessdata /opt/homebrew/share/tessdata/, spa+eng. Runtime/version/packs/manifest y blobs registrados. Ollama GET /api/version=0.23.3; /api/tags confirma qwen3-vl:4b-instruct y digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`. Sin inferencia de preflight. Paddle instalado, no seleccionado.

Export previo preservado en `/private/tmp/06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba_pre_reset.dump`, SHA `c233f76868707f567d8ebc5379815eebfa75c854989dc8e3ae9fe91577178153`. Reset autorizado sólo validation_06v, Alembic upgrade head, zero state0/0 y drift exacto verificados antes de pre-freeze. No reparación de índices. Nueva identidad/root independientes de históricos.

## Artefactos inmutables

Todos los nombres siguientes relativos a este directorio:

| Artefacto | SHA-256 de archivo completo |
|---|---|
| pre_execution.json (DI_SELECTIVE_FREEZE_003) | cc61ea98cf31ecbc897e49ef02692db938c2dc99a09f657222d9e344b57e6285 |
| input_binding.json | e37b77425fe2cc8ca12d0ebe8b51bca797d57e9524f0eaa93d1c0b1779a863b9 |
| first_pass.json | 893ecae1aa6bf9b1fe510eba5b8fefb82fc4e5ff5d6bdb22172bdede6311395b |

EXECUTION_STARTED.json: creado exclusivamente por execute_frozen_run después del gate final. FROZEN.json: presente y hashes de JSON/Markdown verificados. BLOCKED.json: ausente. Los envelopes guardan adicionalmente SHA del payload canónico; no confundirlo con SHA del archivo completo.

Originales/importación: Tender `4a0ac86b-a47e-4448-9f15-a6eff3ff43cf`;11 fuentes,11 importadas,11 documentos; duplicados/rechazados/errores0. API canónica POST /tenders y POST /tenders/{id}/documents/import mediante TestClient, sin clientes alternativos. Fuente exacta autorizada `/Users/ceciliavalencia/Documents/LicitIA/Reelevadores Elecricos`.

`source_inventory.json`, `original_locators.json` y `import_integrity.json` registran identidades/hash/tamaños/MIME/locators. El binding canónico conserva nombres exactos y generaciones; locators canónicos complementarios quedan en original_locators.json, ligado por su hash al reporte de importación y al manifest final. No se agregaron campos ad hoc al binding canónico.

Pre-freeze no cambió. Todos los originales existían y permanecen dentro del root congelado, con hash/tamaño válidos; el conjunto y hashes fuente permanecen iguales. No hubo fallback ni movimiento de originales. first_pass_database.dump y su database_export_identity.json preservan filas/outputs/provenance crudos sin inspección semántica. runtime_storage_manifest.json fija originales/recibos persistidos. Los eventos tienen envelopes verificados y coinciden con los del first-pass.

## Métricas de preparación y percepción

Preparados10, unsupported1, fallos0. Páginas Native253 (8 documentos con texto disponible/251 páginas con texto;2 documentos NO_NATIVE_TEXT;1 unsupported PENDING). El estado DOCUMENTS del collector marca8 trusted/3 unavailable; no es un error de preparación ni juicio semántico.

| Métrica | OCR | Vision |
|---|---:|---:|
| Necesarias/elegibles | 80/80 | 78/78 |
| Adquisiciones/llamadas reales | 8 | 4 |
| Páginas distintas ejecutadas | 8 | 2 |
| Tareas/fingerprints ejecutados distintos | 8 adquisiciones | 3 |
| Completados frescos | 8 | 1 |
| Resultados completados incluyendo reuse | 18 | 1 |
| Reused | 10 | 0 |
| Failed | 0 | 3 resultados de llamada |
| Retry exhausted | 0 | 1 |
| Diferidos por presupuesto | 62 | 76 |
| Avoided por suficiencia, métrica canónica | 0 | 0 |
| Presupuesto de llamadas restante | 0/8 | 0/4 |

OCR1191 decisiones:1111 SKIPPED (860 NO_PROVEN_OCR_SOURCE +251 TEXT_TASK_CONTRACT_REQUIRED),8 adquisiciones,10reuse,62UNAVAILABLE por presupuesto. No confundir SKIPPED con avoided por suficiencia; no confundir18completed con18llamadas. ACK desconocidos0. Ningún fingerprint supera1 adquisición.

Vision78planes únicos:39estructura y39detalle. Hay81resultados de ejecución (40estructura/41detalle) porque incluye retries/exhaustion; no son81planes ni81llamadas. Llamadas reales2estructura/2detalle;1completada/3fallidas;1retry adicional y1retry-exhausted. Consumo shared budget:4calls/3tasks/2pages; capacidad remanente0calls/1task/2pages, por lo que no hay más adquisición posible. Máximo2llamadas por plan/fingerprint verificado. Los3fallos fueron absorbidos por la política bounded comprometida; no impidieron cierre/freeze válido. No se cambió motor/modelo ni timeout/retry/budgets. Causas/calidad semánticas no adjudicadas.

Los1346eventos registran ejecución, decisiones y rechazos por presupuesto; GUARD rechazados0. Todos los proveedores ejecutados tienen plan registrado. Native/OCR-suficientes no alcanzan Vision según gate comprometido y eventos; en este pase avoided canónico=0, sin inferir ganancia semántica.

## Comparación operacional con Attempt #2

| Métrica | Attempt #2 (baseline humano) | Attempt #4 |
|---|---:|---:|
| Tenders/documentos | 1/11 | 1/11 |
| Preparados/unsupported/fallos | 10/1/— | 10/1/0 |
| Páginas Native | 253 | 253 |
| OCR/Vision inferencias | 0/0 | 8/4 |
| Requirements/candidates | 31/43 | 31/43 |
| Requested Evidence | 8 | 8 |
| Scope/Attributes/Quantities | 0/0/0 | 0/0/0 |
| Structure trusted/review/unavailable | 2/249/2 | 0/253/0 |
| Review records | 288 | 292 |
| Conflicts | 1 | 6 |
| Stale carry | 0 | 0 |

Versiones ACTIVE11, Source Effects0. Requirements31 y Requested Evidence8 permanecen review. Attempt #3 se conserva separado como fallo de infraestructura pre-start; no es baseline semántico. Ninguna variación de conteos demuestra mejora/corrección.

## Provenance y seguridad

Disponibilidad por página/capacidad (REVIEW_REQUIRED; no confianza semántica): Native251transcripción/251estructura, OCR8/8, Vision0transcripción/1estructura. Cada canal/capacidad tiene253 observaciones del loader incluyendo UNAVAILABLE: esos253 no son253 adquisiciones ni artefactos disponibles. Persistidos:253páginas Native,8OCR,1resultado Vision.

Guard/root/integridad: PASS mecánico. Cero llamadas no planificadas observadas; OCR8/8 y Vision4/4/4 respetados; máximo de equivalentes OCR1/Vision2 respetado. Estructura y detalle conservan task/version/prompt/fingerprint independientes. El unsupported permanece representado. Native253 y OCR8 siguen presentes después de fallos Vision; no borrado observable. IDs de página/original y SHA de provenance Vision verificados. No se fabricaron páginas/provenance/confianza por el operador; grounding/corrección del contenido quedan para adjudicación humana. No se afirma calidad semántica con mocks ni con éxito operacional.

## Validación posterior

Después del FROZEN, sin repetir pipeline:

- BR/FB/BH + percepción + MVP-06.V/DI ampliada:1009 passed,1deselected,8warnings (72.73s).
- Full suite: 1965 passed, 1 deselected, 8 warnings in 136.13s (0:02:16).
- compileall app/scripts/tests PASS.
- git diff --check PASS.

Intérprete obligatorio: /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python. Suites sólo licitia_test; exclusión explícita -m 'not local_ollama'. Comando full desde backend: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'`.
Logs /private/tmp/attempt4_expanded.log y /private/tmp/attempt4_full.log; serán preservados con hash al cierre. Warnings existentes python_multipart/SWIG, Alembic path_separator y Paddle ccache, sin cambios para silenciarlos.

Sin cambios source/tests/protocolo, stage/commit/push, nueva identidad/replay ni adjudicación semántica. Históricos107 y Attempt3/originales24 se verifican nuevamente al cierre. Sin blocker de integridad/protocolo al terminar el harness; resultados fallidos/deferred permanecen visibles para revisión independiente.

## Cierre de integridad

107 históricos y24 archivos/originales de Attempt3: intactos; cero cambios. Root runtime conservado byte a byte contra manifest; no existe carpeta del nuevo Tender bajo default. first-pass/pre-freeze/binding conservan sus SHA. Git HEAD exacto, tracked clean e índice vacío. Sin stage/commit/push. No adjudicación semántica.

```text
?? MVP-06.3.4c-FINAL-SAFETY-REPORT.md
?? MVP-06.3.4c-HUMAN-LABELS-FINAL-REPORT.md
?? MVP-06.3.4c-PENDING-IDENTITY-FIX-REPORT.md
?? backend/GOLDEN_FINAL_REVIEW.txt
?? backend/MVP-06.3.4c-DIAGNOSTIC-OUTPUT-REPORT.txt
?? backend/MVP-06.3.4c-PHASE-4-FINAL-REPORT.txt
?? backend/MVP-06.3.4c-RUNNER-HOTFIX-REPORT.txt
?? backend/MVP-06.3.4c-TECHNICAL-CLOSURE-FINAL.txt
?? backend/MVP-06.4.4b-QWEN8B-BASELINE-002.txt
?? backend/MVP-06.4.4b-QWEN8B-BASELINE-003.txt
?? backend/PARENT_RECOVERY_AUDIT.txt
?? backend/SCOPE-SEMANTIC-CONTRACT-004-IMPLEMENTATION.txt
?? backend/reports/b4_structural_golden_candidate_v1.json
?? backend/reports/b4_structural_golden_review_packet.md
?? backend/reports/b4_structural_golden_review_pages/
?? backend/reports/blind_attempts/
?? backend/reports/blind_data_root_bootstrap_v5a2.md
?? backend/reports/blind_first_passes/
?? backend/reports/blind_freeze_evidence_closure_v5a1.md
?? backend/reports/blind_runs/
?? backend/reports/blind_selective_execution_harness_v5a.md
?? backend/reports/blind_selective_runs/
?? backend/reports/di_r4a_available_structure.json
?? backend/reports/di_r4a_b4_structure_phase4_rescore.json
?? backend/reports/di_r4a_b4_structure_rescore.json
?? backend/reports/di_r4a_batch1_reanalysis.json
?? backend/reports/di_r4a_existing_vision_transcription.json
?? backend/reports/di_r4a_inventory.json
?? backend/reports/di_r4a_native_structure.json
?? backend/reports/di_r4a_native_transcription.json
?? backend/reports/di_r4a_ocr_structure.json
?? backend/reports/di_r4a_ocr_transcription.json
?? backend/reports/di_r4a_tesseract_b4_p4_transcription.json
?? backend/reports/di_r4a_vision_b4_p1_p3_structure.json
?? backend/reports/di_r4a_vision_b4_p4_transcription.json
?? backend/reports/document_intelligence_06v0_preflight.json
?? backend/reports/document_intelligence_06v0_preflight.md
?? backend/reports/document_intelligence_06v_execution_log.json
?? backend/reports/document_intelligence_06v_execution_phases.json
?? backend/reports/document_intelligence_06v_first_pass.md
?? backend/reports/document_intelligence_06v_import_blocker.json
?? backend/reports/document_intelligence_06v_import_blocker.md
?? backend/reports/document_intelligence_06v_import_manifest.json
?? backend/reports/document_intelligence_06v_import_manifest.md
?? backend/reports/document_intelligence_06v_import_manifest.sha256
?? backend/reports/document_intelligence_06v_run_identity.json
?? backend/reports/document_intelligence_06v_run_identity.sha256
?? backend/reports/document_intelligence_r2_architecture_review.md
?? backend/reports/document_intelligence_r3_review.md
?? backend/reports/document_intelligence_r4a_b4_structure_rescore.md
?? backend/reports/document_intelligence_r4a_batch1_reanalysis.md
?? backend/reports/document_intelligence_r4a_first_batch_analysis.json
?? backend/reports/document_intelligence_r4a_first_batch_analysis.md
?? backend/reports/document_intelligence_r4a_phase1.md
?? backend/reports/document_intelligence_r4a_phase4_structural_trust_hardening.md
?? backend/reports/document_intelligence_r4b_readiness_gate.json
?? backend/reports/document_intelligence_r4b_readiness_gate.md
?? backend/reports/native_structured_coverage_v4b.md
?? backend/reports/selective_ocr_recovery_v4c1.md
?? backend/reports/selective_vision_recovery_v4c2.md
?? backend/reports/selective_visual_perception_v4c_architecture.md
?? backend/reports/source_effect_qwen8b_baseline_v1.json
?? backend/reports/source_effect_qwen8b_bounded_v3.json
?? backend/reports/source_effect_qwen8b_calibrated_v2.json
?? backend/reports/source_effect_qwen8b_fully_bounded_v4.json
?? backend/reports/structural_trust_safety_v4a.md
?? backend/reports/structured_coverage_v4b_architecture.md
?? backend/reports/v4b_drift_baseline_certification.json
?? backend/reports/v4b_drift_baseline_certification.md
?? docs/adr/0011-native-structured-coverage.md
```
