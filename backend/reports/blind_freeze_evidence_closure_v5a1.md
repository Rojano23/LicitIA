# MVP-06.V.5a.1 — Freeze evidence closure

HEAD inicial y actual: `ff64b9ca534ba52fe85aa6d7d67fc352a25b82d3`.

## Corrección acotada

`input_identity()` incluye `original_filename` exacto, sin normalización, junto a identidad documental, hash, tamaño, MIME y revisión existentes; conserva Tender y generaciones. Renombrar cambia el binding, pero no el planner ni los fingerprints semánticos. No se modificaron adaptadores ni lógica de percepción. La restricción canónica `(tender_id, sha256)` permanece: no se crean duplicados artificiales dentro de un Tender. Identidades canónicas distintas conservan sus respectivos nombres aun compartiendo bytes.

El pre-freeze avanza a `DI_SELECTIVE_FREEZE_002` y contiene `schema_drift`: revisión actual/head, versión de normalización, conteo, firma y operaciones. Un observador independiente consulta Alembic/metadatos en una transacción PostgreSQL explícitamente READ ONLY, sin flush del Session caller ni migraciones. La normalización reproduce la certificación anterior y rechaza operaciones distintas de add_index/remove_index.

Baseline confirmado en `licitia_test`:

- current/head: `20261013_req_perception_prov_072`.
- diferencias: 59; add_index: 55; remove_index: 4.
- SHA-256: `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`.

La creación del pre-freeze verifica el baseline antes de crear el directorio. El binding y la ejecución verifican evidencia observada, baseline aceptado y evidencia congelada. Cambiar revisión, firma, conteo u operaciones bloquea; también bloquea la ausencia del contrato nuevo. Se vuelve a verificar al terminar la ejecución. No se reescriben freezes históricos. El binding es un artefacto exclusivo separado y no altera el pre-freeze.

El perfil candidato conserva su SHA normalizado `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`. No cambiaron presupuestos, proveedores, modelos ni task contracts. El perfil histórico AVAILABLE_ONLY permanece intacto.

## Archivos del slice

Modificados:

- `backend/app/blind_selective_freeze.py`
- `backend/tests/test_blind_selective_harness.py` (observador sintético en fixture)
- `docs/adr/0014-blind-selective-execution.md`
- `docs/document-intelligence-06v-protocol.md`

Nuevos:

- `backend/app/blind_schema_drift.py`
- `backend/tests/test_blind_freeze_evidence.py`
- este reporte, intencionalmente sin tracking.

## Validación

Intérprete usado: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`.
Tests exclusivamente en `licitia_test`; no se accedió a validation_06v.

FB01–FB12 y casos adicionales: 23 casos. BH: 37 casos; ambos incluidos en validaciones verdes. Se comprueba identidad exacta, independencia del planner, baseline, rechazo de evidencia alterada, inmutabilidad, perfil histórico, configuración candidata y observador real con SQL limitado a SELECT/SET/SHOW.

Validación focal final (desde raíz):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest backend/tests/test_blind_freeze_evidence.py backend/tests/test_blind_selective_harness.py backend/tests/test_document_intelligence_06v_preflight.py backend/tests/test_selective_ocr_recovery.py backend/tests/test_selective_vision_recovery.py -q -m 'not local_ollama'
```

Resultado: **183 passed, 7 warnings**. Log: `/private/tmp/fb-targeted.log`.

Regresión ampliada: **993 passed, 1 deselected, 8 warnings**. Incluye FB/BH, OCR/Vision sintéticos, Native structured coverage, structural trust, Scope details/attributes/quantities/review, Document Intelligence y preflight, preparación, estructura, alternativas y documentos. Log: `/private/tmp/fb-expanded.log`.

Suite completa (desde backend):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'
```

Resultado: **1949 passed, 1 deselected, 8 warnings en 115.65 s**. Log: `/private/tmp/fb-full.log`.

`compileall` PASS con:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests
```

`git diff --check`: PASS. `alembic current` / `alembic heads`: revisión 072 (head). Observador canónico ejecutado contra licitia_test con `PGOPTIONS=-c default_transaction_read_only=on`: baseline exacto confirmado. No cambio de esquema, reparación ni migración.

Warnings: deprecaciones existentes de python_multipart/SWIG y aviso Paddle de ccache. El uso de ScriptDirectory expone además el aviso existente de Alembic por falta de `path_separator`; no se modificó configuración para suprimirlo.

## Integridad y límites

Verificación final de los 107 archivos históricos contra `/private/tmp/st_historical_hashes.json`: **107 intactos, 0 modificados**. Attempt #1, Attempt #2, freezes, first-pass y adjudicación conservados. No se regeneraron sus resultados ni se reescribieron sus hashes.

Providers ejecutados: **0**. OCR/Vision reales: **NO**. Tender #002 inspeccionado/importado/reiniciado: **NO**. Attempt #3, run_id y freeze reales creados: **NO**. Los tests sólo generan evidencia sintética temporal.

Sin stage, commit ni push. Índice vacío. Working tree: cuatro archivos rastreados modificados y dos archivos nuevos de código/tests, más este reporte; los reportes y artefactos no rastreados previos permanecen ajenos al slice. La salida exacta de `git status --short` se registra en la verificación final de la sesión.

Los dos gaps quedan resueltos sin blocker de implementación. Esto no autoriza ejecutar Attempt #3: faltan revisión arquitectónica, commit aceptado y preparación/autorización de un nuevo freeze ligado al HEAD definitivo.

## Git status final

```text
 M backend/app/blind_selective_freeze.py
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
?? backend/app/blind_schema_drift.py
?? backend/reports/b4_structural_golden_candidate_v1.json
?? backend/reports/b4_structural_golden_review_packet.md
?? backend/reports/b4_structural_golden_review_pages/
?? backend/reports/blind_attempts/
?? backend/reports/blind_first_passes/
?? backend/reports/blind_freeze_evidence_closure_v5a1.md
?? backend/reports/blind_runs/
?? backend/reports/blind_selective_execution_harness_v5a.md
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
?? backend/tests/test_blind_freeze_evidence.py
?? docs/adr/0011-native-structured-coverage.md
```
