# MVP-06.V.5a — Blind selective-perception execution harness

Implementación propuesta para revisión arquitectónica. Sin stage/commit/push ni ejecución ciega.

## 1. Identidad y brecha resuelta

HEAD inicial y actual: `68ee044a0193778762ea1bcbf5c00bbb0990abfa`.
La infraestructura histórica sólo permitía AVAILABLE_ONLY/calls0 y congelaba snapshots sin ejecutar percepción. Los servicios selectivos estaban opt-in, sin driver, límite OCR agregado ni un pre-freeze/input binding independientes para medir inferencia real autorizada.

Se añaden perfil, harness, tooling de evidencia y CLI separados. BlindConfig, manifest histórico y scripts/run_document_intelligence_06v.py no se modifican ni debilitan.

## 2. Perfiles y tareas

DI_BLIND_SELECTIVE_001 distingue HISTORICAL_SAFE (AVAILABLE_ONLY obligatorio, cero adquisición) y SELECTIVE_PERCEPTION (AVAILABLE_ONLY, ALLOW_OCR o AUTO). Instalación/disponibilidad no dispara inferencia. No hay proveedores semánticos nuevos de Requirements/Scope/Source Effects ni cambio de gramáticas.

construct_tasks usa páginas y regiones canónicas con geometría válida y contratos de tarea congelados. No usa filename, Tender ID como regla, número de página conocido, productos, adjudicación ni cantidades esperadas. TEXT/STRUCTURE/SCOPE/ATTRIBUTES/QUANTITIES usan el planner existente. UNKNOWN sin contrato textual no se convierte automáticamente en OCR; la selección de región se aplica sólo a trabajo ya elegible. Se evalúa suficiencia antes de regiones para evitar trabajo innecesario cuando Native ya cubre la tarea.

spatial_contracts declara preguntas IMAGE_LAYOUT_RELATIONSHIP por tipo STRUCTURE_SCOPE o DETAIL_TRANSCRIPTION, globales y sin IDs/páginas. Lista vacía produce cero necesidades visuales automáticas. La declaración es una decisión de política del futuro freeze, NO una inferencia de que la imagen tenga contenido contractual. Sólo se vincula a regiones IMAGE canónicas y el planner mantiene elegibilidad separada de ejecución. Fallo OCR nunca crea contratos espaciales. Tras OCR se comprueba suficiencia otra vez; si queda satisfecha se evita Vision. No se fuerza OCR para la capacidad de una tarea inherentemente espacial. Vectores sin binding IMAGE siguen pendientes.

## 3. Presupuestos y guard de llamadas

OCR max_calls agregado es obligatorio, finito (0–10000), sin default ni cálculo por Tender. Motor TESSERACT/PADDLEOCR, versión conocida, idioma es+en/es/en y timeout default30/máximo60s. Se conservan renderer2x, 8 millones píxeles y 8MiB. Se reserva antes de llamar; indisponibilidad/fallo consume reserva. Reuse no consume nueva llamada. Al agotarse, no se entra al cliente y el trabajo permanece explícitamente pendiente.

Vision comparte UN VisionBudget por pase: defaults máximos 4 calls/4 tasks/4 pages, 2 intentos por fingerprint, 60s, tokens600/1000 y retryJSON0. El perfil puede reducirlos, no ampliarlos. Se delegan reuse/exhaustion/fingerprints a V.4c2. Hay comprobación final de agotamiento sin una llamada adicional al proveedor. Estructura y detalle permanecen separados.

ProviderCallGuard registra planes y envuelve interfaces canónicas. Sin plan registrado, política permitida o configuración congelada coincidente, rechaza y registra calls0; una violación no puede convertirse en pase válido. Los ejecutores existentes comprueban plan fresco, fingerprint compatible/completado/agotado antes de alcanzar wrappers. El guard es una frontera de aplicación, no sandbox contra Python arbitrario fuera del harness.

Se registran eventos de adquisición y decisiones de reuse/deferred/budget con identidad de plan, fingerprint disponible, motivo, modelo/motor y tiempos. Un ACK incierto OCR mantiene calls=None y reserva acotada; no se inventa cero. Los eventos se escriben exclusivamente y sobreviven a fallos posteriores del pipeline.

## 4. Freeze, input binding y CLI

CLI nuevo: scripts/run_document_intelligence_selective.py, acciones preflight/freeze/bind/execute. No genera automáticamente run_id, no resetea DB ni importa corpus. Requiere DATABASE_URL local exacta licitia_validation_06v, Alembic072 y filesystem separado de dev/test. Sólo execute habilita escrituras DB; freeze/bind usan lectura DB y escriben evidencia local exclusiva. La CLI fija LICITIA_LOCAL_AI_ENABLED=false para impedir IA automática ajena al servicio selectivo explícito.

Pre-execution.json exige DB vacía y código limpio/committed, incluyendo ADRs0012/0013/0014. Captura HEAD, hashes de código/protocolo/ADRs, perfil completo, versiones planner/policy/task/fingerprints, prompts/schemas, parámetros motores/modelo/presupuestos/timeouts/retry, dependencias y metadata local sin inferencia. Se crea antes de contacto con corpus.

Input_binding.json se crea separadamente tras importación canónica autorizada: un único Tender, documentos/IDs/hash/tamaño/MIME/revisión y generaciones iniciales vacías. Verifica originales y enlaza SHA del pre-freeze, sin modificarlo. La evidencia tiene hash verificable y creación exclusiva.

EXECUTION_STARTED es exclusivo. Código/perfil/runtime/input se verifican antes de ejecutar; original/código se vuelven a verificar al cierre. El éxito operacional crea first_pass.json/md y FROZEN con hashes. Cualquier excepción conserva BLOCKED y estado parcial; un directorio iniciado no se puede reejecutar ni sobrescribir. No patch/rerun bajo el mismo run_id: una corrección tras Attempt #3 exige commit nuevo y Attempt #4.

Este slice sólo escribe freezes sintéticos bajo tmp_path de pytest. NO se creó freeze real, identidad de Attempt #3 ni directorio de intento ciego.

## 5. Preflight sin inferencia

runtime_preflight consulta metadata de paquetes sin importar motores, presencia/version del ejecutable, tessdata efectivo mediante --version/--list-langs (no reconocimiento), idiomas/packs/hash y manifest/digest/presencia de blobs locales del modelo. No llama Ollama, inicializa Paddle, descarga assets ni genera texto. Si no se puede comprobar tessdata queda NOT_RUNTIME_CONFIRMED; servicio queda NOT_PROBED. Presencia local no certifica que la inferencia funcione. Los probes de ejecutable están simulados en las pruebas de este slice; no se ejecutaron motores reales.

## 6. Orden y consumidores

prepare_tender_documents canónico → cargar escalares persistidos → tareas/suficiencia → OCR selectivo → reevaluar → Vision selectivo → commit de percepción → materialización canónica con adquisición AVAILABLE_ONLY → snapshot/collector.

El driver no llama AUTO legacy ni encadena estructura/detalle. Requirements discovery/normalization/requested Evidence/versioning, estructura/Scope/Attributes/Quantities, Source Effects deterministas y proyecciones usan las funciones públicas existentes. Native/OCR/Vision mantienen sus canales, revisión, conflictos y scope-logical-v2. No se mejoró extracción semántica ni se certificó recall.

## 7. Métricas

Se reutilizan snapshot_tender y collect_metrics para documentos/páginas, dominios, estructura trusted/review/unavailable, conflictos, reviews, capacidades y provenance. El reporte selectivo agrega Native disponible, OCR eligible/executed/completed/failed/reused/exhausted/deferred/avoided y presupuesto, Vision needed/eligible/executed/reused/failures/retries/exhaustion/budget/pending y tipos estructura/detalle. Los resultados y eventos crudos permiten distinguir unidades planificadas, intentos y estados, sin inferir llamadas a partir de filas DB.

## 8. Validación reproducible

Intérprete obligatorio: /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python. DB tests: licitia_test. Sólo fake OCR/Vision y PDFs/filas sintéticos.

- BH: 37 casos parametrizados, todos incluidos en la regresión final. BH01–BH20 cubiertos: compatibilidad safe; Native suficiente; OCR/Vision autorizado; rechazo no planificado; AVAILABLE_ONLY; presupuestos compartidos y OCR agregado; reuse/exhaustion; configuración; pending; preservación Native; freeze y binding; tareas genéricas; métricas y separación de tareas.
- Focal BH/VP/OCR/SC/DC/ST/preflight: 229 passed, 6 warnings (antes del último caso de metadata no-inferencia).
- Focal final BH + materializador atributos: 48 passed, 6 warnings.
- Regresión ampliada final DI/MVP-06.V/VP/OCR/SC/DC/ST: **970 passed, 1 deselected, 7 warnings**.
- Suite completa final: **1926 passed, 1 deselected, 7 warnings en 111.82s**. Advertencias existentes: python_multipart, SWIG/PyMuPDF y ccache/Paddle; sin fallos pendientes.
- compileall app/scripts/tests: PASS.
- git diff --check: PASS.

Un fallo inicial de regresión reveló una comparación de dos queries SQL sin ORDER BY en test_replay_is_semantically_idempotent. Los mismos valores/fingerprints aparecieron en orden distinto. Se corrigió exclusivamente el assert para comparar sorted(first_state)/sorted(second_state), manteniendo el invariante de contenido y sin modificar producción. La regresión final pasa. No se ocultó ni relajó un defecto de extracción.

## 9. Esquema e integridad

Alembic current/head licitia_test: 20261013_req_perception_prov_072. Sin modelos nuevos ni migración. Probe read-only conserva exactamente 59 diferencias preexistentes aceptadas (55 add_index, 4 remove_index), cero drift adicional. Signature SHA-256: 3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7. Metadata54tablas/hash 97651292fc4c46655c8727943ba813d40366229d8318d5b67739f7b751e97270. Hash esquema antes/después idéntico. No se arregló drift histórico.

107 artefactos históricos verificados intactos, incluidos Attempts #1/#2, freezes, first-pass y adjudicación. Sin reset/reimport, replay, proveedores reales ni inspección/tuning de Tender #002.

## 10. Archivos y prerrequisitos restantes

Nuevos: backend/app/blind_selective_profile.py, backend/app/blind_selective_harness.py, backend/app/blind_selective_freeze.py, backend/scripts/run_document_intelligence_selective.py, backend/tests/test_blind_selective_harness.py, docs/adr/0014-blind-selective-execution.md y este reporte runtime sin rastrear.

Modificados: docs/document-intelligence-06v-protocol.md (sección nueva, sin cambiar protocolo histórico) y backend/tests/test_scope_attribute_materializer.py (comparación independiente del orden SQL).

Antes de Attempt #3: aceptación/commit del harness/ADR/protocolo; elegir perfil real y OCR max_calls finito; aprobar explícitamente los contratos espaciales deseados sin IDs/páginas; confirmar motor/version/idiomas/tessdata/pesos y modelo local/digest/servicio; aprobar reset/reimport y ejecución exacta; filesystem aislado, DB072 vacía, HEAD nuevo limpio y hashes actuales; recién entonces nuevo run_id y pre-freeze. La calidad real sigue sin certificar. Los contratos espaciales son decisiones de política, no hallazgos automáticos del contenido. No existe autorización implícita para ejecutar el intento por completar este código.

## Comandos ejecutados y Git final

Cwd backend:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_selective_harness.py tests/test_selective_vision_recovery.py tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_structural_trust_propagation.py tests/test_scope_details.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attributes.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_integration.py tests/test_scope_quantities.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_review.py tests/test_scope_review_api.py tests/test_alternative_compliance.py tests/test_alternative_compliance_api.py tests/test_documents.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q app scripts tests
git diff --check
```

Focal final: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_selective_harness.py tests/test_scope_attribute_materializer.py -q -m 'not local_ollama'`.

Staging vacío; HEAD sin cambio; sin stage/commit/push.

```text
 M backend/tests/test_scope_attribute_materializer.py
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
?? backend/app/blind_selective_freeze.py
?? backend/app/blind_selective_harness.py
?? backend/app/blind_selective_profile.py
?? backend/reports/b4_structural_golden_candidate_v1.json
?? backend/reports/b4_structural_golden_review_packet.md
?? backend/reports/b4_structural_golden_review_pages/
?? backend/reports/blind_attempts/
?? backend/reports/blind_first_passes/
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
?? backend/scripts/run_document_intelligence_selective.py
?? backend/tests/test_blind_selective_harness.py
?? docs/adr/0011-native-structured-coverage.md
?? docs/adr/0014-blind-selective-execution.md
```
