# MVP-06.V.4c2 — Task-aware selective Vision

Implementación para revisión arquitectónica. Sin stage, commit ni push.

## 1. HEAD y brecha confirmada

HEAD inicial/actual: `9f61fdcc0b398384c76792ca8754262a78a62afa`.
La ruta Vision histórica encadena estructura/detalle, puede hacer probes al reutilizar y no conserva agotamiento finito entre solicitudes equivalentes. Sus clientes, schemas, artefactos y reconciliación son reutilizables.

## 2. Suficiencia y elegibilidad por tarea

`plan_document_vision_tasks` extiende el planificador V.4c1 y consume sólo evidencia persistida; no renderiza ni prueba proveedores. Mantiene decisiones independientes por tarea. Native/OCR suficiente produce SUFFICIENT_FOR_TASK y cero invocaciones. OCR de página completa puede satisfacer un contrato textual sin scope regional; una tarea con región explícita exige evidencia vinculada a esa región.

OCR fallido/no disponible, texto corto, baja confianza y parser sin filas NO son prueba de necesidad visual. Elegibilidad exige `visual_relationships_required`, motivo explícito permitido y binding a región IMAGE de la página. La señal semántica la aporta el caller autorizado; la presencia de imagen por sí sola no la descubre. Sin prueba hay revisión, no fallback universal. Los contratos visuales siguen acotados a estructura/transcripción; no interpretación general de diagramas.

## 3. Política de ejecución

`execute_planned_vision` es servicio explícito opt-in. AVAILABLE_ONLY y ALLOW_OCR conservan pending/eligibility y no hacen render/probe/invocación. AUTO permite sólo la tarea elegible y valida nuevamente el plan antes de adquirir. Los endpoints, AUTO histórico y runner ciego no se activan ni cambian automáticamente.

Se reutiliza OllamaVisionAssistClient con endpoint loopback y configuración explícita; no probe, instalación, descarga ni chaining de tareas. Retry JSON interno se fija en cero para esta ruta; cada intento reservado ejecuta como máximo una inferencia HTTP. Timeout 1–180 s, tokens por tarea acotados, crop real con renderer existente y límite de imagen/píxeles. Ningún cliente real fue ejecutado en esta tarea.

## 4. Fingerprints y reutilización

Descriptor por tarea: documento/tender/revisión/hash original, página, generaciones Native/OCR, región/coordenadas reales, renderer/zoom/hash imagen, tarea/version, prompt/schema, policy, proveedor/modelo/revisión local declarada, endpoint, temperatura, think, tokens efectivos y timeout. Cambiar tokens de detalle no invalida estructura. El digest/revisión de modelo lo suministra el caller desde configuración congelada; no se verifica mediante probe ni se inventa un digest remoto.

Un éxito equivalente verifica integridad original, recibo, identidad de DB y hash del payload. Reutiliza sin render ni contacto con proveedor. Un cambio material adquiere una generación distinta conservando los resultados previos; corrupción/inconsistencia difiere sin sobrescribir.

## 5. Presupuesto, retry y persistencia

VisionBudget compartido por ejecución limita calls, tareas y páginas (defaults 4/4/4), además de intentos por tarea (default 2, rango 1–3). Budget exhaustion es explícito, no fabrica resultado y deja trabajo pendiente. El caller debe compartir el mismo objeto de presupuesto entre tareas del mismo run.

Recibos locales derivados por fingerprint, lock y reemplazo atómico conservan never attempted, RUNNING, FAILED, COMPLETED y máximo de intentos congelado al primer intento. Se reserva RUNNING antes de invocar. Fallo observado permite un siguiente intento finito; agotamiento sobrevive nuevas llamadas y presupuestos. RUNNING interrumpido se trata como ejecución incierta agotada: no se reemite. Cambiar materialmente fingerprint permite otra generación.

Cada éxito crea DocumentVisionAnalysis/PageResult canónicos nuevos. Native/OCR no se modifican; no se actualizan éxitos anteriores. Un rollback DB posterior que deje recibo completado huérfano se difiere, sin reparación silenciosa. No nuevas tablas/enums ni migración. Recibos son provenance/agotamiento vinculados a generaciones, no un stream de logs; no deben borrarse para reiniciar retries.

## 6. Provenance, tareas y consumidores

STRUCTURE_SCOPE y DETAIL_TRANSCRIPTION tienen ejecución, fingerprints, reutilización y agotamiento independientes. Structure no proporciona transcripción; detail no ejecuta estructura. El payload tipado conserva `_selective_vision` con identidad, original/revisión/página/región/crop, modelo/configuración, imagen, fingerprint e intento; Analysis/PageResult conservan IDs canónicos.

Provenance permanece VISION. La transcripción entra al loader DI y a Requirements/Requested Evidence por rutas existentes. Scope e hijos usan adaptadores Vision canónicos; cantidades siguen su gramática acotada existente (por ejemplo, cantidad/unidad terminal explícita), sin expansión semántica. Filas con sintaxis explícita reutilizan procurement_rows/explicit_fields para grounding comparable, sin Native IDs.

`scope-logical-v2` no cambia. Pruebas verifican Native+Vision, OCR+Vision y tres canales en un Scope lógico con todos los contribuyentes. Partidas distintas y paráfrasis no probadas permanecen distintas. Conflictos preservan evidencia y requieren revisión; Vision no recibe prioridad contractual. Todos los nuevos candidatos visuales conservan review; éxito de percepción no significa TRUSTED. V.4a y V.4b permanecen vigentes.

## 7. Fallos y observabilidad

Unavailable, timeout, malformed JSON, schema inválido, vacío, parcial, truncado, render fallido, presupuesto y retry exhaustion no generan percepción completada ni borran fuentes. Un resultado incompatible/corrupto no se reutiliza. No se fabrican páginas/transcript/bbox/confianza.

`vision_metrics` separa necesidad, elegibilidad, llamadas de ejecución, reutilización, evitado, fallos, retries, agotamiento/pending y tarea. `vision_provider_metrics` adapta eventos al ProviderMetric del collector existente. Los conteos de tests representan invocaciones simuladas; proveedores reales en esta tarea: cero.

## 8. Validación

Intérprete obligatorio: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`. Tests en `licitia_test`; nunca licitia_dev ni DB de validación ciega.

- Nuevos casos V.4c2: **46**, todos incluidos en regresión final focal.
- Focal final V.4c2 + V.4c1 + V.4b SC/DC + V.4a ST: **160 passed, 6 warnings**.
- Ampliada DI/MVP-06.V, Vision/OCR y materializadores: **933 passed, 1 deselected, 7 warnings**.
- Suite completa inicial: **1889 passed, 1 deselected, 7 warnings**. Después se reforzó aserción de suficiencia OCR, se ajustó filtro regional para esa tarea textual y se explicitó UNAVAILABLE. Regresión focal final verde. Suite completa sobre el estado final: **1889 passed, 1 deselected, 7 warnings en 108.68 s**. Advertencias existentes: python_multipart, SWIG/PyMuPDF y ccache/Paddle. Sin fallos inesperados.
- compileall app/scripts/tests: PASS.
- git diff --check: PASS.

VI01–VI06: suficiencia Native/OCR, tarea independiente, ausencia de prueba, pending y AVAILABLE_ONLY. VE01–VE05: modos, no trabajo sin plan, no probes y reuse. VB01–VB05: caps calls/tasks/pages, estado pendiente y no fabricación. VR01–VR05: fallos repetidos, máximo persistente, nuevo fingerprint, payload inválido y estado RUNNING incierto. VT01–VT05: tareas independientes y structure sin transcripción. VC01–VC05: reconciliación comparable, tres fuentes auditables, items distintos y paráfrasis no colapsadas.

VP15–19,21–30 y superficie Vision VP31–38 cubiertos por pruebas nuevas más regresiones: imagen/relación explícita, cero calls sin necesidad, metadata unsupported, cache sin render, cambios config, fallo preserva Native/OCR, children/bridges, conflicto, presupuesto, agotamiento y página completada independiente de fallo adyacente. VP31/34 mantienen OCR histórico/V.4c1 por regresión; VP32/33 conservan UNKNOWN/revisión sin deducir necesidad por char_count/filename/área; VP36 valida separación estructura/detalle. VP38 limita endpoint local y no incorpora pull/cloud; no certifica runtime/modelo real. Los tests no certifican calidad semántica visual real.

## 9. Alembic e integridad histórica

Current/head de licitia_test: `20261013_req_perception_prov_072`. Probe read-only conserva exactamente las 59 diferencias aceptadas (55 add_index, 4 remove_index), cero drift nuevo. Signature `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`; metadata 54 tablas/hash `97651292fc4c46655c8727943ba813d40366229d8318d5b67739f7b751e97270`; esquema antes/después idéntico. No se corrigió drift ni se crearon migraciones/modelos.

107 archivos históricos verificados sin cambio, incluidos Attempt #1 y freeze/first-pass/adjudicación de Attempt #2. Arquitectura V.4c intacta SHA-256 `83fe42ccf9e2ec2e602c28d4ff8eee1df93407b2d6f63e568884a30a748d27fa`. Sin replay, blind run_id nuevo ni Attempt #3. Sin inspección/tuning de Tender #002, lógica por nombre/documento/producto/página/cantidad ni proveedores reales.

## 10. Archivos y riesgos

Modificado: `backend/app/document_perception_planner.py`.
Nuevos: `backend/app/selective_vision_executor.py`, `backend/tests/test_selective_vision_recovery.py`, `docs/adr/0013-task-aware-selective-vision.md` y este reporte intencionalmente no rastreado.

Sin blockers de esquema. Límites: integración explícita opt-in; las rutas legacy conservan sus garantías anteriores. Motivo visual y revisión/digest del modelo son entradas autoritativas del caller, no descubrimiento/certificación automática. Vectores sin región raster comprobada permanecen sin adquisición automática. Continuidad multi-página no se infiere. Recibos huérfanos/interrumpidos fallan cerrado y requieren decisión administrativa fuera del slice. La calidad real requiere ejecución posterior autorizada, no realizada aquí.

## Comandos exactos

Cwd backend para regresión ampliada y completa:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_selective_vision_recovery.py tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_structural_trust_propagation.py tests/test_scope_details.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attributes.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_integration.py tests/test_scope_quantities.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_review.py tests/test_scope_review_api.py tests/test_alternative_compliance.py tests/test_alternative_compliance_api.py tests/test_documents.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q app scripts tests
git diff --check
```

Focal final ejecutada desde raíz:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest backend/tests/test_selective_vision_recovery.py backend/tests/test_selective_ocr_recovery.py backend/tests/test_native_structured_coverage.py backend/tests/test_structural_trust_safety.py -q -m 'not local_ollama'
```

## Estado final de Git

HEAD sin cambio; staging vacío; no stage/commit/push. `git diff --stat`: un archivo rastreado, 80 líneas añadidas; los cuatro archivos nuevos de este slice siguen sin rastrear.

```text
 M backend/app/document_perception_planner.py
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
?? backend/app/selective_vision_executor.py
?? backend/reports/b4_structural_golden_candidate_v1.json
?? backend/reports/b4_structural_golden_review_packet.md
?? backend/reports/b4_structural_golden_review_pages/
?? backend/reports/blind_attempts/
?? backend/reports/blind_first_passes/
?? backend/reports/blind_runs/
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
?? backend/tests/test_selective_vision_recovery.py
?? docs/adr/0011-native-structured-coverage.md
?? docs/adr/0013-task-aware-selective-vision.md
```
