# MVP-06.R.4b — Document Intelligence Convergence Readiness Gate

Starting HEAD: `530621adee2124959c5677832af37ea615dfff3e` (`530621a`).

**Decisión: CONDITIONAL_GO_FOR_06V.** Sólo significa suficientemente seguro para preparar y realizar una validación ciega controlada cuando se cumplan C01–C05 y exista autorización humana explícita. No certifica producción, comercialización, precisión, proveedores universales ni nuevos tipos de tender. R.4b CURRENT, pendiente aceptación; 06.V NEXT PENDING HUMAN AUTHORIZATION y PROTECTED.

Reporte documental determinista; JSON adjunto conserva matrices, configuración e identidades SHA-256. No evaluator nuevo ni cambios productivos. La evidencia original se preserva; no inferencias nuevas.

## Inventario R.1–R.4a y Golden

R.1 contratos/routing neutrales; R.2a persistence de provenance; R.2 integración Requirements/requested Evidence/Scope; R.3a comparación tipada cross-capability; R.3 propagación local fail-closed; R.4a P1 harness/lote real, P2 fidelidad/replay, P3 Golden humano/rescore, P4 corrección genérica/replay. Las identidades de código se anclan al HEAD, no a conversaciones anteriores.

| Evidencia | Rol | SHA-256 |
|---|---|---|
| `docs/adr/0010-document-intelligence-capability-routing.md` | architecture R.1–R.4a | `1c9a9c2d2761e088ff97740cf0585609427bf6705e8c74f2c8f636a9f4f6afcd` |
| `backend/app/document_intelligence.py` | R.1 neutral contracts/routing/continuity | `d9f8776fbd7fd48211ee3a57641c6e2a1d96224a35a071d3679052ea2c63ef4b` |
| `backend/app/requirement_perception_provenance.py` | R.2a/R.3a typed durable provenance | `518655af05069a1bb9f4b320caf9e5fbd8de44f909ab84525da8b8e2aec15b8c` |
| `backend/app/requirement_di_adapter.py` | R.2 Requirements integration | `d13e596add7d6089b5b1cbd6ddcb5bbc0c39b6b8513617292502eb0984f61bca` |
| `backend/app/document_intelligence_sources.py` | R.2 persisted input adapters | `294d86a6ac3f41812cc813cbdec457df0550ef040b6d675bb3d82f2b0d27c608` |
| `backend/app/requirement_semantics.py` | R.2 requested Evidence | `a4704b28d8398a2fd7de589084bef9b3b32ca11950dcfc1fffcdeec3b8a4ce25` |
| `backend/app/scope_detail_materializer.py` | R.2 Scope integration | `240163aa90f469bc4462489581df320f301495e14e14f80408ddda70bef877eb` |
| `backend/app/critical_identifier_comparison.py` | R.3a cross-capability comparison | `34c1120c41966e4e793a63363515ef2ca18ea4bd862c030cbabe865d2b4ce76e` |
| `backend/app/document_identifier_bindings.py` | R.3 conflict propagation | `e1eacd2b7316db74c86778a3363703edf56ce7e05492e246fe828d0ca3ff24af` |
| `backend/app/document_structure_orchestrator.py` | R.4a Phase 4 production guard | `8300dfb390a4cf41f6251e060f2ee219ca19f48bf2d2bbc632b98fd04bc39f43` |
| `backend/app/scope_detail_adapters.py` | R.4a Phase 4 ownership guard | `654173ea32ea9f2f54c7f627b0d8b68eb8e0b1964b6a6240858451920c27005d` |
| `backend/reports/document_intelligence_r4a_phase1.md` | Phase 1 historical harness | `22d0fa7356a20486bf86295bfbbd0ff4470d58d605e49871c23ff02378f26b9e` |
| `backend/reports/document_intelligence_r4a_first_batch_analysis.json` | Phase 1 historical real batch analysis | `fb5b3761be70a677937b9158069763a64b650b71adcd5ff7c01983d78d40a6c1` |
| `backend/reports/di_r4a_native_transcription.json` | Native current stored diagnostic coverage | `ad9bda3330838a748d349f6cf811419b75fe708d6a1f9a2c87a0e1973bf553e0` |
| `backend/reports/di_r4a_native_structure.json` | Native structure diagnostic coverage | `615f2d367f65ad71f177b66c5099f8dcfeb032ec532a52dba460a61f7268085a` |
| `backend/reports/di_r4a_tesseract_b4_p4_transcription.json` | real Tesseract P4 immutable | `ba099b6dc93e82526c6d5e6bc506cc6ccc239e005ccc2aa735497ae46139f93a` |
| `backend/reports/di_r4a_vision_b4_p4_transcription.json` | real Vision transcription P4 immutable | `9b76c4010617db0e8075f7535775edff5ac9a350081a4a3b840a2e28c9531cef` |
| `backend/reports/di_r4a_vision_b4_p1_p3_structure.json` | real Vision structure P1–P3 immutable | `e37b20c8badc558516e1335beebd5285532c09b08ed339f0711a0abb4abe5aed` |
| `backend/reports/di_r4a_batch1_reanalysis.json` | Phase 2 offline fidelity/replay | `5dac77df45949f4351b4581c6a5c1d1ad78178b208d1c1e6cae8f528942b22c8` |
| `backend/reports/di_r4a_b4_structure_rescore.json` | Phase 3 original adjudication | `c4f8d251a8c004fc76908d384349986aeb0d9f582181ce2a8090ddd89d1ea300` |
| `backend/reports/di_r4a_b4_structure_phase4_rescore.json` | Phase 4 safety adjudication | `5bb02658ecbcce98ce6be8aa46811a8d9a34a547b4da107843c761d8fe57e13b` |
| `backend/reports/document_intelligence_r4a_phase4_structural_trust_hardening.md` | Phase 4 audit/validation | `ffd6b5839775ef31005a2a893b739925acbcf43eac6cf7e958295126e2069698` |
| `backend/evals/document_intelligence_calibration_v1.json` | diagnostic calibration manifest, not all human truth | `7a8d834c4672d93bc882087dd98e374202e3d84fc21d53901e0a86719544fbc8` |
| `backend/evals/document_intelligence_b4_structure_golden_v1.json` | human-approved structural Golden | `60520abdb48862cf99763d40e355cc03f6e3771e4f73f1c438f7c00c069feb71` |
| `backend/evals/semantic_scope_golden_v1.json` | human Tender #001 scope domain Golden | `ad9d44a67022fa1eaec3181799a88b93c4c6dd04572fff46f31c3ac0c244af86` |
| `backend/evals/technical_attribute_golden_v1.json` | human Tender #001 attribute Golden | `ad2e3707f5b7a2e53e44339108c14669d9697ad733af3527a8e40216dd7b991b` |
| `backend/evals/scope_quantity_golden_v1.json` | human Tender #001 quantity Golden | `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7` |

Golden B-4: `b4-human-structure-v1`, approval `human-chat-b4-v1-approval-1`, P1–P4; content SHA `885f9c623a07092d3a1880a1736517dd2917888b2435320e9fcaaedcfc082ef5`. File SHA distingue bytes completos del digest de JSON canónico sin su propio campo hash. Loader verifica PDF y PNG aprobados. Los cinco Golden/manifiestos son byte-identical a HEAD y los hashes históricos del lote coinciden. El manifiesto de calibración contiene casos DIAGNOSTIC_ONLY y referencias humanas por dominio: no convierte páginas enteras en verdad canónica. El candidato PENDING no es Golden; la aprobación explícita humana congeló la estructura, nunca el modelo.

## Arquitectura y seguridad

DI separa TRANSCRIPTION/STRUCTURE/SEMANTIC_ASSIST, conserva Native/OCR/Vision, fuentes/versiones/locator/excerpt/generation/lineage y valida antes de persistir. Preferencia de canal sólo entre evidencias compatibles; no adjudica conflictos contractuales. Provenance JSONB v1/v2 durable, unknown/invalid rechazado; NULL legacy permanece ausencia explícita. Fuente FAILED/DESELECTED no se vuelve discovery activo. La continuidad revisa límites abiertos y recuperación grounded; ownership dependiente se retira; cantidades/atributos heredan review. La decisión humana sigue separada.

| Safety | Estado | Evidencia y alcance |
|---|---|---|
| S01 — Known adjudicated unsafe contractual errors = 0 | PASS | Phase 2 transcription safety + Phase 4 structural adjudication; current focused tests; Sólo los casos adjudicados conocidos; no certificación global de todas las páginas/dominios. |
| S02 — Unsafe structural errors = 0 | PASS | Phase 4 aggregate + GS15; P2/P3 en revisión; P1 segura. |
| S03 — Stale carry = 0 | PASS | Phase 4 aggregate, HF21, ST06/ST07; UNKNOWN no transporta salida confiable. |
| S04 — FAILED/truncated cannot become canonical | PASS | HF10/HF11, failed Vision artifact; Raw parcial se conserva sólo como diagnóstico. |
| S05 — Critical conflicts fail closed | PASS | test_critical_identifier_propagation.py; Review local y retiro de owner. |
| S06 — Provider preference does not resolve identity | PASS | R.1/R.3a tests; Canal/fecha no adjudican identidad contractual. |
| S07 — Unresolved structure removes ownership | PASS | ST10 + Scope production guard; Detail afectado: UNRESOLVED, sin IDs de owner confiables. |
| S08 — Quantity ownership protected | PASS | ST11 + HF22 + R.3 CQ tests; Derivado conserva review del detalle. |
| S09 — Attribute ownership protected | PASS | ST12 + HF23 + R.3 CA tests; Derivado conserva review del detalle. |
| S10 — Reference/source conflict is not adjudicated | PASS | HF08/HF09/HF27 + Phase 2 fidelity; Modelo disputado excluido de correcto/incorrecto. |
| S11 — DESELECTED cannot reenter discovery | PASS | DI16 + R.2 deselection tests; Historia conservada; discovery activo excluye lineage inactiva. |
| S12 — Invalid provenance fails closed | PASS | R.2a/R.3a validation tests; Versiones/shape/fuentes incompatibles rechazados; NULL legacy es ausencia explícita. |

Errores contractuales adjudicados conocidos actuales=0; estructurales=0 (antes=2); stale carry=0. Esto combina la seguridad de dos transcripciones adjudicables y tres observaciones estructurales, no demuestra tasa global de errores del corpus. Phase4: P1 CORRECT, P2/P3 REVIEW_REQUIRED_CORRECT, P3→P4 UNASSESSABLE. Dos escalaciones correctas/dos safe misses estructurales y un safe miss de transcription Vision FAILED; categorías se reportan por capacidad, no se suman como accuracy única. Percepción estructural sigue con un falso inicio, dos continuaciones perdidas y un cierre perdido.

## Percepción, operaciones y dominios

| Canal/capacidad | Hechos existentes | Viabilidad | Política |
|---|---|---|
| Native transcription | 415 observaciones: 279 REVIEW_REQUIRED, 136 UNAVAILABLE; sin latency/accuracy contractual completa. Las omisiones literales del reporte inicial no prueban error material completo. | INSUFFICIENT_DATA para certificación operacional completa | Primera adquisición en páginas con texto utilizable; revisión de fidelidad, nunca confianza por mera presencia. |
| Tesseract transcription P4 | 7/7 filas, cantidades/unidades; 6 modelos adjudicables; 1 REFERENCE_SOURCE_CONFLICT; 0 omisiones materiales scoreables; 1.549 s. | OPERATIONALLY_VIABLE sólo en caso probado | Fallback local sujeto a revisión; no certifica todo el tender ni Paddle. |
| Vision transcription P4 qwen3-vl:4b-instruct | FAILED, OUTPUT_TRUNCATED/DONE_REASON:length; JSON/texto canónico no disponible; raw parcial sólo diagnóstico; 86.592 s. | NOT_CURRENTLY_VIABLE | No fallback normal bajo configuración probada; excluir en plan 06.V (C02), no ajustar budget aquí. |
| Vision structure qwen3-vl:4b-instruct | P1 35.825 s, P2 35.638 s, P3 36.923 s; origen CORRECT/PARTIAL/INCORRECT, ahora protegido por review. | VIABLE_AS_BOUNDED_FALLBACK | Sólo tarea bounded preautorizada con revisión; no percepción automática certificada. |

Vision timeout registrado=180 s; el fallo observado es truncación por length, no timeout. Prompts almacenados: transcription `vision-detail-transcription-2026-08-31-001`, structure `vision-structure-scope-2026-09-03-006`; Tesseract 5.5.3, spa+eng. Overhead/render/model-load/output-budget completo histórico no medido; valores null no se reemplazan por estimaciones. Ejecución local documentada, no prueba benchmark general. Paddle real no calibrado en este lote.

Requirements: integración/provenance/conflictos/idempotencia probados sintéticamente; replay real de lote produce 0 candidatos. Requested Evidence: ruta Tender-side/review/provenance probada, 0 resultados reales positivos; CompanyEvidence fuera de esta calibración. Scope: adapters neutrales/independencia y ownership seguros; lote produce 0 detalles, cantidades y atributos, artefactos structure-only/OCR sin adapter semántico predeterminado=UNSUPPORTED/NO_EVIDENCE. Esa ausencia no prueba recall. ST/HF/R.3 prueban positivos sintéticos de quantities/attributes. Un fragmento puede alimentar dominios independientes, cada uno con evidencia propia, sin clasificación excluyente.

Carga total de revisión, revisión innecesaria y automatización adjudicada de todo un tender: NOT_MEASURED. P1 muestra una selección segura; P2/P3 y transcription fallida muestran safe misses; no declarar aceptable la carga global. Son objetivos de 06.V, no safety FAIL por exigir revisión.

## Matriz G01–G25

| Gate | Estado | Blocking | Evidencia | Razón |
|---|---|---|---|---|
| G01 architecture convergence | PASS | NO | R.1/R.2/R.3/current tests | Capacidades separadas y runtime neutral; no autoridad contractual automática. |
| G02 Requirements integration | PASS | NO | R.2, R.2a, R.3 tests | Consumo DI, provenance durable, review e idempotencia sintéticos; cobertura real positiva no certificada. |
| G03 requested Evidence integration | PASS | NO | R.2 integration, R.3 CE tests | Ruta Tender-side independiente de CompanyEvidence; no demuestra cobertura real positiva. |
| G04 Scope integration | PASS | NO | R.2 + ST10–ST13 + Phase 4 replay | Estructura/transcripción independientes; ownership fail-closed. |
| G05 provenance durability | PASS | NO | R.2a 072 / R.3a tests | JSONB tipado, historia, página/documento/versión/locator y lineage; no backfill especulativo. |
| G06 critical identifier safety | PASS | NO | R.3/R.3a tests | Conflictos conservados sin precedencia de proveedor. |
| G07 structural continuity safety | PASS | NO | ST01–ST09 + Phase 4 | 0 unsafe/0 stale; transición sustentada y recuperación independiente válidas. |
| G08 quantity binding safety | PASS | NO | ST11/HF22/R.3 | Binding inseguro no se promueve a owner confiable. |
| G09 attribute binding safety | PASS | NO | ST12/HF23/R.3 | Review del detalle heredada por atributo. |
| G10 FAILED provider result safety | PASS | NO | HF10/HF11 + Vision FAILED | Truncación no produce transcripción canónica. |
| G11 reference/source conflict safety | PASS | NO | Phase 2/HF08/HF09 | REFERENCE_SOURCE_CONFLICT excluido; mantenimiento humano separado. |
| G12 DESELECTED lineage safety | PASS | NO | DI16/R.2 | No reingreso activo ni ocultamiento de historia. |
| G13 Golden integrity | PASS | NO | Bytes HEAD + hashes históricos + approved loader | Aprobación humana identificada; candidato no canónico; modelos no generan verdad. |
| G14 production/calibration separation | PASS | NO | ST20 + búsqueda módulos runtime | Sin imports/rutas Golden/reports/UUIDs B-4/ITEM_1/ITEM_2 en producción inspeccionada. |
| G15 Native operational viability | WARN | NO | 415 observaciones almacenadas; 279 REVIEW_REQUIRED / 136 UNAVAILABLE | Primera adquisición para páginas con texto utilizable; fidelidad/latencia real completas no medidas. No bloquea medirlas en 06.V. |
| G16 OCR operational viability | WARN | NO | Tesseract P4 1.549 s / 7 filas | Viable en el caso probado, sujeto a revisión; no generalizar a expediente ni Paddle. No bloquea 06.V controlado. |
| G17 Vision transcription viability | WARN | YES | P4 FAILED, truncación, 86.592 s | NOT_CURRENTLY_VIABLE en configuración probada; excluir fallback normal antes de primer pase. Condición C02. |
| G18 Vision structure viability | WARN | NO | 35.825/35.638/36.923 s; 1 correcta/2 protegidas | VIABLE_AS_BOUNDED_FALLBACK con revisión; no calidad automática certificada. Sin tuning y sólo plan autorizado. |
| G19 runtime observability | WARN | NO | Artifacts include provider/model/prompt/timeout/latency/hash | Latencia de inferencia medida; overhead/load/budget histórico incompletos. Captura completa futura C03; no bloquea evaluar límite actual. |
| G20 real-domain calibration coverage | NOT_MEASURED | NO | Replay: Requirements/Evidence/ScopeDetail/quantities/attributes=0 | Sin evidencia positiva real end-to-end; contratos sintéticos no equivalen a recall. Objetivo de 06.V. |
| G21 review-load knowledge | NOT_MEASURED | NO | Sin medición adjudicada de todo el tender | No afirmar carga aceptable; medir denominadores/revisión innecesaria en 06.V. |
| G22 idempotence | PASS | NO | HF24/GS22/ST18/current tests | Fingerprints/estados estables; IDs incidentales de segmentos regenerados. |
| G23 isolated DB readiness | PASS | NO | test current/head 072; dev 071 sólo lectura | Alembic reproducible; preparar DB nueva de validación, no importar datos de dev. |
| G24 blind-run metrics readiness | WARN | YES | Production snapshots + bounded calibration harness | Harness actual fija Tender #001/B-4; falta colector transversal/adjudicación con denominadores. C01 antes de abrir corpus, sin reglas específicas. |
| G25 Tender #002 blindness intact | PASS | NO | Sólo whitelist de evidencia T001/code/tests; sin corpus ciego | No preview, documentos, hashes, expected outputs ni fixtures T002. |

Blocking YES en G17/G24 identifica condiciones previas a abrir el corpus, no fallo de S01–S12. Todos los safety mandatory PASS; los gaps concernen eficiencia, cobertura y medición, y pueden resolverse sin inspección ciega. No se propone GO incondicional: el harness bounded actual no sirve directamente como colector universal de 06.V.

## Condiciones previas a 06.V

- **C01**: Preparar y validar con fixtures sintéticos un colector genérico para Documents, Requirements, requested Evidence, Scope, attributes, quantities, Versions/Effective Source y review queue; separar observaciones, hechos de dominio y adjudicación humana. Congelar esquema/denominadores y capture de todas las generaciones antes de abrir T002. No reutilizar el harness B-4 fijo como evaluador universal.
- **C02**: Congelar plan bounded: Vision full-page TRANSCRIPTION excluida como fallback normal bajo configuración probada; Source Effect Qwen automático deshabilitado. Plan base AVAILABLE_ONLY sin adquisición OCR/Vision; cualquier lote real futuro exige autorización humana exacta y límites/configuración congelados antes de importar el corpus.
- **C03**: Congelar commit limpio/revisado, SHA de configs/provider versions/prompts/temperature/output budgets/timeout/retry/page limits, procedimiento y colector. No inventar targets de latencia; usuario acepta presupuesto operativo antes de ver T002. Reparar/aceptar explícitamente deuda de tests 005 sin alterar prompts o semántica para hacerlos pasar.
- **C04**: Crear DB aislada de validación al head072 y filesystem separado vacío; no migrar dev ni copiar T001. Autorizar T002 explícitamente después de aceptar el gate y verificar condiciones.
- **C05**: Congelar la primera salida y sus hashes antes de analizar errores; preservar raw FAILED/lineage/versiones. Medir seguridad por adjudicación humana posterior separada, sin tuning retroactivo ni asumir que ausencia de candidatos demuestra recall.

## Protocolo exacto de primer pase — preparado, NO ejecutado

1. Antes de abrir corpus: aceptar explícitamente el gate y C01–C05; validar colector con fixtures sintéticos y congelar código/configuración/plan de ejecución. Registrar HEAD completo, diff vacío, hashes y versiones. No usar Git commit automático en este gate.
2. Crear, sólo en la fase autorizada: createdb licitia_06v; DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_06v /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic upgrade head. Verificar current/head072 y filesystem nuevo separado. No ejecutar estos comandos ahora.
3. Emitir autorización humana explícita para importación del corpus ciego. Iniciar API local con DATABASE_URL de la DB aislada y LICITIA_DATA_DIR nuevo; importar exclusivamente mediante POST /tenders y POST /tenders/{tender_id}/documents/import. Registrar UUIDs/hash/versiones al importar, nunca antes.
4. Ejecutar extracción nativa existente; usar orchestrate_document_structure_available_only(..., execution_policy="AVAILABLE_ONLY"). No activar OCR/Vision automático ni providers semánticos no configurados. Si otro plan de proveedores fue aprobado antes de abrir, ejecutar sólo sus tareas/límites congelados y registrar fallos/timeouts sin reparar raw.
5. Por tender/documento: analyze_tender_requirements → normalize_tender_requirements → analyze_tender_requirement_semantics; por documento: estructura → materialize_document_scope_details; por detail: materialize_scope_quantities_for_scope_detail y materialize_scope_attributes_for_scope_detail. Registrar unsupported/no evidence/failed como tales; no introducir adapters o labels al ver resultados.
6. Capturar Versions/Effective Source mediante resoluciones/proyecciones deterministas y Source Effects sustentados disponibles; conservar revisión humana separada, sin discovery Qwen. Recoger matrices/snapshots y scope-review sin aprobar decisiones automáticamente.
7. Colector C01: guardar IDs, generaciones/lineage, hashes, locator/excerpt, routing/review, owners, cantidades/atributos, provider/configuration, runtime y errores por dominio; registrar numeradores/denominadores y unavailable/unsupported. Exportar datos suficientes para adjudicación, no sólo latest-summary.
8. Producir y congelar primer reporte de resultados observables y hashes de outputs/DB export. Antes de analizar errores no cambiar código/prompts/routing/thresholds, repetir para mejorar, ni fabricar Golden de T002.
9. Después del reporte congelado: revisión humana adjudica unsafe trusted errors, safe misses, unnecessary review, automation rate y domain impact por denominadores explícitos. Lo no adjudicado permanece NOT_MEASURED; adjudicación es un artefacto separado que referencia el primer reporte inmutable.
10. Cualquier corrección posterior es un pase separado/versionado; nunca reemplaza métricas del primer pase. GO/NO-GO de MVP-07 se decide humanamente después de 06.V.

Las métricas de precisión/unsafe/review innecesario requieren adjudicación humana posterior: el primer reporte congela hechos observados y denominadores antes de analizar fallos. No presentar métricas no adjudicadas como PASS. Las semánticas Source Effects permanecen deterministas con revisión humana; Qwen NO-GO intacto.

## Validación del HEAD actual

Focused: **300 passed, 0 failed, 6 warnings, 10.34 s**. Broad: **1672 passed, 4 failed, 1 deselected, 7 warnings, 178.65 s**. Test real local_ollama excluido explícitamente. Reproducción dirigida: **4 failed, 6 warnings, 2.29 s** sobre el mismo starting HEAD; app/tests/scripts sin diff.

Fallos preexistentes reproducidos:

- `tests/test_documents.py::test_structure_scope_prompt_version_bumped_for_normalization_semantics`
- `tests/test_documents.py::test_completed_old_structure_scope_analysis_is_not_reused_after_version_bump`
- `tests/test_documents.py::test_vision_latest_summary_prefers_current_005_over_legacy`
- `tests/test_documents.py::test_vision_latest_summary_derives_candidates_and_status_without_heavy_payload`

Clasificación: las dos primeras expectativas requieren prompt005 pese a constante006 vigente; las dos últimas sólo siembran análisis005/004 y los llaman current, pero latest-summary filtra006. No son evidencia de promoción de output fallido/conflictivo a confianza; son deuda de fixtures/versionado, no blockers de S01–S12. No se corrigieron tests ni producción. Captura futura debe conservar todas las generaciones/IDs y no depender sólo de latest-summary; C03 exige mantenimiento o aceptación explícita de la deuda antes del freeze. No se ocultan como suite verde.

Warnings existentes: SWIG/PyMuPDF, python_multipart; broad añade Paddle No ccache. Importar dependencia Paddle en test no es ejecutar reconocimiento OCR. Sin inference real; pruebas de proveedores usan fakes/mocks y guard offline.

Comandos (cwd backend salvo Git/compileall):

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_integration.py tests/test_requirement_perception_provenance.py tests/test_cross_capability_provenance.py tests/test_critical_identifier_propagation.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_structural_trust_propagation.py -q --tb=short
RUN_LOCAL_OLLAMA_TESTS=0 DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests -m 'not local_ollama' -q --tb=short
RUN_LOCAL_OLLAMA_TESTS=0 DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_documents.py::test_structure_scope_prompt_version_bumped_for_normalization_semantics tests/test_documents.py::test_completed_old_structure_scope_analysis_is_not_reused_after_version_bump tests/test_documents.py::test_vision_latest_summary_prefers_current_005_over_legacy tests/test_documents.py::test_vision_latest_summary_derives_candidates_and_status_without_heavy_payload -q --tb=short
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
git diff --check
git diff --stat
git status --short
```

Alembic test current/head072; dev current071 por lectura, sin upgrade. DB propuesta licitia_06v aún no creada/importada. Compileall exit0; Git whitespace/check sin errores. Sólo docs/roadmap.md modificado y dos nuevos reportes untracked; app/tests/scripts, schema, frontend/pricing y Source Effects intactos. No stage/commit/push.

Producción/calibración separadas: ST20 y búsqueda de módulos runtime sin rutas backend/reports, calibration Golden, UUIDs Tender001/B-4 ni ITEM_1/ITEM_2. Golden/model outputs intactos y approval humana identificada. Provider calls=0; real models executed=NO. Tender #002 no abierto/listado/buscado/parseado/OCR/hasheado/resumido ni usado para fixtures/tuning.

## Limitaciones y siguiente acción

Cobertura real positiva de dominios no demostrada; Vision transcription truncada no viable en configuración actual; estructura depende de revisión; Native/OCR no cuentan con certificación global; review load, overhead y precision/recall de tender completo no medidos; falta colector transversal genérico y deuda de cuatro tests005. La seguridad conocida PASS no elimina esas limitaciones.

**Siguiente acción:** decisión humana sobre el gate condicional y C01–C05; cumplirlas y congelarlas antes de una autorización explícita nueva para Tender #002. R.4b no CLOSED aún; 06.V no ACTIVE; MVP-07 después de 06.V y cierre MVP-06.

MVP-06.R.4b CONVERGENCE READINESS GATE COMPLETE — READY FOR HUMAN GO/NO-GO DECISION
