# MVP-06.V.5a.2 — Frozen data-root bootstrap / settings safety

HEAD inicial y actual: `75111c047766dc32e480589075df0a029815f394`.
Clasificación arquitectónica: GENERIC BLIND HARNESS BOOTSTRAP / ENVIRONMENT INITIALIZATION DEFECT.

## Causa y ciclo de vida confirmado

`Settings.licitia_data_dir` usa default `.licitia-data`; Pydantic Settings lee LICITIA_DATA_DIR al construir Settings. `get_settings()` está decorado con lru_cache. `app.database` llama get_settings a nivel módulo y crea engine/SessionLocal globales; `app.main` conserva también Settings globales y usa get_settings para resolver almacenamiento. El script operacional anterior importó módulos del harness antes de fijar el entorno; esa cadena importó database/config y fijó el cache. Mutar os.environ después no reconstruye Settings ni engine. La DB se corrigió mediante variable al inicio de otro proceso, pero el root quedó predeterminado en el proceso de importación. El guard del harness encontró la discrepancia antes de EXECUTION_STARTED. No es falla de extracción, schema ni proveedor.

## Corrección

Nuevo `app.blind_environment`, libre de dependencias de Settings/SQLAlchemy/application. `establish_environment` valida DB local validation_06v y root aislado existente/escribible; establece DATABASE_URL, LICITIA_DATA_DIR canónico absoluto, LICITIA_BLIND_DATA_ROOT e IA automática deshabilitada ANTES de importar config/database/main. Si esos módulos ya están cargados rechaza el proceso; no limpia caches ni reconfigura globals. Otro attempt exige proceso fresco, no rebind silencioso.

La CLI selectiva llama esa frontera antes de imports del harness. El mismo helper debe usarse antes de cargar API para una futura importación/reset autorizado. La CLI no añade capacidades ni permisos de import/reset. El directorio se prepara explícitamente antes del bootstrap; missing/unwritable/default dev/test falla cerrado.

El resolver canónico get_licitia_data_root aplica `verify_storage_root` a env+Settings antes de escritura/lectura. Con marcador ciego no crea/fallback a root default. Importación, resolución de originales, preparación y binding usan este resolver. Escritura de originales rechaza symlinks de subdirectorios que escaparían del root antes de mkdir/escritura. Resolución de lectura conserva el control de traversal/escape existente. Operación ordinaria sin marcador conserva default y mkdir habitual.

Freeze nuevo: `DI_SELECTIVE_FREEZE_003`, con `storage = {schema_version: BLIND_STORAGE_ROOT_001, canonical_data_root: ...}`. Observación de storage obligatoria antes de crear freeze y antes de validar binding/ejecución. Se compara env/Settings/root congelado antes del marcador de inicio. Un freeze viejo no se actualiza ni se admite silenciosamente. La identidad del perfil semántico, budgets, proveedores, modelos, task contracts, planners y fingerprints no cambia; sí cambia la serialización/versionado del freeze para futuros intentos.

No se modificaron config.py ni database.py ni se añadieron cache resets productivos, esquema o migraciones.

## Archivos

Modificados:

- backend/app/main.py
- backend/app/blind_selective_freeze.py
- backend/scripts/run_document_intelligence_selective.py
- backend/tests/test_blind_freeze_evidence.py (fixture sintética y versión003)
- backend/tests/test_blind_selective_harness.py (fixture y assertion de storage)
- docs/document-intelligence-06v-protocol.md
- docs/adr/0014-blind-selective-execution.md

Nuevos:

- backend/app/blind_environment.py
- backend/tests/test_blind_data_root_bootstrap.py
- este reporte intencionalmente sin tracking.

## Validación sintética

BR01–BR12 y casos adicionales: **16 passed, 6 warnings**. Incluyen:

- proceso fresco con entorno antes de Settings/app;
- rechazo de proceso con Settings previos y rebind;
- dos procesos/roots independientes;
- importación canónica, identidad/binding y preparación Native del mismo PDF sintético;
- mismatch antes de EXECUTION_STARTED y rechazo de root ausente/default/unwritable;
- planner idéntico al cambiar sólo root;
- freeze histórico no reescrito;
- escape symlink rechazado sin escritura;
- regresión obligatoria en proceso fresco con default sintético existente bajo tmp_path: bootstrap→app→API import→input identity→preparación, y cero archivos nuevos en default.

El subprocess de integración usa el entorno blind para bootstrap; sobreescribe sólo la dependencia DB de FastAPI con Session de licitia_test. No conecta a validation_06v. El PDF es sintético, no contiene corpus real y no ejecuta OCR/Vision.

FB23/BH37: verdes dentro de regresiones. Primer intento focal:72 passed/1 error de fixture corpus faltante; corregido en tests. Matriz focal previa:255 passed/7 warnings. BR16 posterior incluye la integración en proceso fresco adicional.

Regresión ampliada FINAL: **1009 passed, 1 deselected, 8 warnings**,47.49s.
Suite completa FINAL: **1965 passed, 1 deselected, 8 warnings**,111.93s.

Logs:

- /private/tmp/br_only.log
- /private/tmp/br_targeted_final.log
- /private/tmp/br_expanded.log
- /private/tmp/br_full.log

Intérprete obligatorio en todos los comandos: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`. Tests únicamente licitia_test; exclusión `-m 'not local_ollama'`. Ninguna inferencia real.

Comandos desde backend:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_data_root_bootstrap.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_data_root_bootstrap.py tests/test_blind_freeze_evidence.py tests/test_blind_selective_harness.py tests/test_selective_vision_recovery.py tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_document_preparation_recovery.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_data_root_bootstrap.py tests/test_blind_freeze_evidence.py tests/test_blind_selective_harness.py tests/test_selective_vision_recovery.py tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_structural_trust_propagation.py tests/test_scope_details.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attributes.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_integration.py tests/test_scope_quantities.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_review.py tests/test_scope_review_api.py tests/test_alternative_compliance.py tests/test_alternative_compliance_api.py tests/test_documents.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'
```

Compileall app/scripts/tests PASS (desde raíz con intérprete obligatorio, `-m compileall -q backend/app backend/scripts backend/tests`). `git diff --check`: PASS.

Warnings existentes python_multipart/SWIG, Alembic path_separator y Paddle ccache; no se modificó configuración para silenciarlos.

Último ajuste sólo de fixtures: el default de la reproducción se simula bajo tmp_path para no depender de runtime real. Cierre BR/FB/BH: **76 passed, 7 warnings**,17.85s, log `/private/tmp/br_closure.log`; no cambió producción después de las regresiones verdes.

## Alembic e históricos

Observador canónico readonly en licitia_test, con PGOPTIONS default_transaction_read_only=on: current/head `20261013_req_perception_prov_072`,59 diferencias,55 add_index/4 remove_index, firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`. Cero diferencial nuevo; no schema/model change/migración/reparación.

Verificación SHA de107 históricos contra `/private/tmp/st_historical_hashes.json`:107 intactos. Baseline al inicio de este slice `/private/tmp/br_attempt3_baseline.json`:24 archivos de Attempt3 y originales intactos. Incluye los11 originales preservados en `backend/.licitia-data/tenders/347c0581-3d2b-4bdb-9fb1-42a50103f2df/originals/`; no se eliminaron/movieron. Attempts1/2/3 no se modificaron.

Cero proveedores/OCR/Vision ejecutados. Sin inspección semántica, reset/import del corpus ni Attempt4/run_id/freeze real. Sin stage/commit/push. No blocker de implementación pendiente si validaciones finales verdes; faltan revisión arquitectónica/commit y autorización separada de futura ejecución.

## Estado Git al cierre

```text
 M backend/app/blind_selective_freeze.py
 M backend/app/main.py
 M backend/scripts/run_document_intelligence_selective.py
 M backend/tests/test_blind_freeze_evidence.py
 M backend/tests/test_blind_selective_harness.py
 M docs/adr/0014-blind-selective-execution.md
 M docs/document-intelligence-06v-protocol.md
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
?? backend/app/blind_environment.py
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
?? backend/tests/test_blind_data_root_bootstrap.py
?? docs/adr/0011-native-structured-coverage.md
```
