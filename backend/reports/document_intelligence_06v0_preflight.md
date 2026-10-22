# MVP-06.V.0 — Blind Validation Preflight + Freeze

**Recomendación: READY_TO_AUTHORIZE_06V.** Ready para decisión humana sobre preflight, no permiso de inspeccionar Tender #002. V.0 sigue CURRENT; 06.V PROTECTED / NOT AUTHORIZED.

Starting HEAD: `1745c70311e2e29fa1744aef693a35c8d8f16205` (`1745c70`). No stage/commit/push.

## Cinco condiciones R.4b

| Condición | Estado final | Evidencia |
|---|---|---|
| C01 Generic cross-domain collector | PASS | Typed snapshot + ORM read-only adapter + VF01–VF12/VF26–VF30 and positive quantity/attribute integration |
| C02 Bounded provider plan | PASS | Typed manifest AVAILABLE_ONLY, zero OCR/Vision/LLM execution authorization; full-page Vision transcription not normal fallback |
| C03 Debt resolved + code/config identities | PASS_FOR_PREFLIGHT_REVIEW | Four stale tests updated only; broad1709green; 254 frozen code/protocol SHA identities + baseline1745c70; actual run captures future HEAD and refuses dirty code |
| C04 Dedicated validation database | PASS | licitia_validation_06v created via existing Alembic; head072; seven corpus counts=0; dev071 untouched |
| C05 First-pass freeze before analysis | PASS | Exclusive run directory, JSON/MD/FROZEN hashes, tamper verification, independent HumanTruth keyed to first-pass SHA and separate analysis identity |

**Freeze de código:** el manifest fija 254 hashes de archivos/protocolo y el HEAD base. La identidad actual registra protected_dirty=true porque estos cambios están pendientes de revisión y commit, como exige la tarea sin stage/commit/push. El run real queda rechazado; después de aceptación, V.1 debe capturar el HEAD real committed/clean y comprobar hashes iguales antes de importar. El SHA de commit futuro no se inventa ni se introduce una referencia circular en el manifest. Esto es una condición de ejecución futura explícita, no un primer pase autorizado.

## Arquitectura del colector

Instrumentación calibration-only en módulos nuevos, sin imports nuevos en runtime/API productiva. snapshot_tender exige authorized_import antes de acceder al corpus y realiza queries ORM acotadas al tender con no_autoflush; CLI utiliza transacción READ ONLY y rechaza una solicitud no autorizada antes de conectar. Reutiliza DI, candidate_perception/provenance y resolución/proyección de Effective Source. No acquisition, discovery extra, actualización de ownership, flush, commit, create_all o nuevos schemas DB.

Snapshot tipado conserva registros persistidos, valores reales de cantidades/atributos/Requirements, locators/excerpts/source metadata, lineage, generaciones y outputs fallidos/raw. Candidatos y evidencia originales se capturan por separado de canónicos. Queries no abren PDFs ni corpus en filesystem. Interfaces puras admiten IDs arbitrarios; los tests son sintéticos, nunca Tender #002 ni su Golden.

First pass: documentos/páginas y availability por canal/capacidad; Requirements/candidatos; requested Evidence; Scope/ownership; atributos/cantidades/binding; versiones/effects; review por dominio/motivo/página/documento; conflictos/stale carry; telemetría; tasas de automatización no adjudicadas; enlaces trazables perception→dominio y Scope→children.

Post-adjudication inicialmente todos null: trusted_correct/incorrect; unsafe contractual/structural; safe misses; unnecessary review; safe automatic; identifier conflicts correctly surfaced; unsafe quantity/attribute bindings; recall. HumanTruth exige autoridad INDEPENDENT_HUMAN_TRUTH, reviewer/revisión, IDs de verdad humana y SHA del primer pase; MODEL_DERIVED no es autoridad válida. Duplicados/métricas incompatibles rechazados. Recall usa casos humanos únicos y coverage explícita, no total de output como truth.

Denominadores congelados: por dominio total de registros observados; review/unavailable/trusted automatic unadjudicated rates. Denominador0 → null. Review no es fallo ni trusted automatic prueba de éxito. Cola total son unidades (domain,id), con páginas/documentos únicos afectados. Ausencia de datos/model outputs no es recall exitoso. Domain impact mide enlaces de provenance; causal error impact queda null antes de humano.

Telemetría distingue eventos explícitos de artefactos persistidos. Un result no inventa call count/retries; missing es null/NOT_MEASURED. ExecutionLog obligatorio captura run_id/start/end, ProviderMetric execution_event/calls/status/model/capability/source_method/config/latencia y errores, incluidos intentos sin artefacto. Si hay eventos, outcomes/latencias se miden sobre ellos y no se duplican con artifacts. Native persistido no ofrece latencia y se reporta así.

## Plan proveedor/capacidad congelado

| Capacidad | Política | Ejecución base |
|---|---|---|
| Native | Preferido cuando suficiente/confiable | Adquisición determinista existente; sin certificar fidelidad por presencia |
| OCR/Tesseract transcription | Elegible fallback | NO autorizado en V.0 ni en plan base AVAILABLE_ONLY |
| Vision STRUCTURE qwen3-vl:4b-instruct | Elegible bounded con grounding, continuidad fail-closed y review | NO autorizado sin plan nuevo aprobado/congelado antes de abrir corpus |
| Vision full-page TRANSCRIPTION qwen3-vl:4b-instruct | No normal automatic fallback: FAILED/OUTPUT_TRUNCATED/DONE_REASON:length calibrado | Excluido; sin tuning budget/prompt |
| SEMANTIC_ASSIST | Sólo bounded/grounded/review con proveedor explícito | Sin nuevo proveedor/default acquisition |
| Source Effect Qwen | NO-GO automático intacto | No ejecución ni cambio semántico |

Config registra timeout180 s, estructura600 tokens, detalle1000 tokens sólo como configuración heredada no autorizada, temperatura0, prompts006/detail001, maxpages4/task y retry malformed0. No latency target o acceptable review threshold inventado. Una llamada OCR/Vision fuera del plan en el ledger produce INVALID_PROTOCOL en el reporte congelado, conservando evidencia y error, sin reinterpretarla como run válido.

## Disposición exacta de deuda heredada

006 es autoritativo: constante/prompt productivo ya existente y test de contrato006 sobre segmentos físicos compartidos, aceptado antes de starting HEAD. No se modifica el proveedor para mejorar un score ni para acomodar tests005.

| Test | Expectativa005 | Comportamiento006 | Cambio equivalente / final |
|---|---|---|---|
| test_structure_scope_prompt_version_bumped_for_normalization_semantics | Constante requerida005 | Constante006 existente desde el HEAD aceptado | Misma aserción exacta, actualizada a vision-structure-scope-2026-09-03-006; PASS; producción NO |
| test_completed_old_structure_scope_analysis_is_not_reused_after_version_bump | Set de análisis004/005 | Set004/006: reusa lógica de fingerprint y crea nueva revisión actual | Se mantiene len=2, no reuso antiguo, IDs/status/versiones; sólo literal esperado actualizado; PASS; producción NO |
| test_vision_latest_summary_prefers_current_005_over_legacy → test_vision_latest_summary_prefers_current_006_over_legacy | Fixture005 considerado current; IDs005 frente a004 | Latest-summary selecciona únicamente current006 | Fixture/nombre/variable/aserciones versionadas a006; mismo ID/status/metadata; PASS; producción NO |
| test_vision_latest_summary_derives_candidates_and_status_without_heavy_payload | Fixture005 que latest-summary006 no seleccionaba | Fixture006 y mismo contrato de resumen liviano | Se conservan status/candidates/ausencia heavy payload y restantes aserciones; PASS; producción NO |

No tests eliminados; se cambia un nombre005→006 y ocho líneas semánticas de fixtures/aserciones, manteniendo selección/reuso/IDs/status/metadata/payload assertions.

## Archivos exactos

- `backend/app/document_intelligence_validation_metrics.py` (nuevo)
- `backend/app/document_intelligence_blind_run.py` (nuevo)
- `backend/scripts/run_document_intelligence_06v.py` (nuevo)
- `backend/evals/document_intelligence_06v_config_v1.json` (nuevo)
- `backend/tests/test_document_intelligence_06v_preflight.py` (nuevo)
- `backend/tests/test_documents.py` (modificado)
- `docs/document-intelligence-06v-protocol.md` (nuevo)
- `docs/roadmap.md` (modificado)
- `backend/reports/document_intelligence_06v0_preflight.json` y este reporte (runtime nuevos, untracked).

Producción changed: NO en comportamiento/routing/semántica; YES sólo nuevas herramientas de evaluación en app/scripts aisladas. Frontend/pricing, Source Effect semantics, modelos, prompts, thresholds y DB models/Alembic code intactos. Ninguna nueva migración; las existentes inicializaron exclusivamente la DB nueva.

## VF01–VF30

| Caso | Comprobación | Resultado |
|---|---|---|
| VF01 | Colector sin supuestos Tender | PASS |
| VF02 | Separación first-pass/adjudicación | PASS |
| VF03 | Requirements deterministas | PASS |
| VF04 | Requested Evidence determinista | PASS |
| VF05 | Scope determinista | PASS |
| VF06 | Attributes deterministas | PASS |
| VF07 | Quantities deterministas | PASS |
| VF08 | Versiones/Source deterministas | PASS |
| VF09 | Review/motivos/páginas deterministas | PASS |
| VF10 | Telemetría explícita vs artifacts | PASS |
| VF11 | Automatización no adjudicada | PASS |
| VF12 | Unsafe trust null antes de verdad | PASS |
| VF13 | Manifest tipado válido | PASS |
| VF14 | Transcription Vision no automática | PASS |
| VF15 | Structure Vision eligible/exec blocked/grounding-review | PASS |
| VF16 | SHA de HEAD capturado | PASS |
| VF17 | SHA de config capturado | PASS |
| VF18 | Dirty code capturado y run rechazado | PASS |
| VF19 | Serialización canónica determinista | PASS |
| VF20 | Directorio de freeze exclusivo, no overwrite | PASS |
| VF21 | SHA first-pass emitido | PASS |
| VF22 | Análisis separado/no overwrite | PASS |
| VF23 | Revisión DB registrada | PASS |
| VF24 | Validation DB real vacía detectable | PASS |
| VF25 | Autorización requerida antes de corpus/DB | PASS |
| VF26 | Cero providers en collector real sobre fixture | PASS |
| VF27 | IDs arbitrarios no cambian métricas | PASS |
| VF28 | No tuning antes de marcador/hash válido | PASS |
| VF29 | Métricas operacionales sin verdad humana | PASS |
| VF30 | Adjudicación humana independiente posterior | PASS |

Adicionales: tamper/path controls; ORM integration de Requirements/Evidence/Scope/versions; Quantity/Attribute positivos con enlaces Scope→children y lectura repetible. No usan mocks como calidad real del modelo; son pruebas de contratos/safety/instrumentación.

## Validación

**Focused final: 37 passed, 0 failed, 6 warnings, 5.67 s** (30 VF + 3 adicionales + 4 deuda). **Broad: 1709 passed, 0 failed, 1 deselected, 7 warnings, 110.45 s**. Unexpected failures=0. Una ejecución completa anterior también pasó1709 en109.23 s. El guard final del CLI fue revalidado después mediante focused37; no cambió ningún servicio productivo.

Exclusión intencional: tests/test_documents.py::test_local_ollama_live_structure_scope_opt_in, marker local_ollama y RUN_LOCAL_OLLAMA_TESTS=0. No se ejecutó real provider. Warnings existentes SWIG/PyMuPDF y python_multipart; broad añade Paddle No ccache por importación de dependencia, no reconocimiento.

Comandos exactos, cwd backend:

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_06v_preflight.py tests/test_documents.py::test_structure_scope_prompt_version_bumped_for_normalization_semantics tests/test_documents.py::test_completed_old_structure_scope_analysis_is_not_reused_after_version_bump tests/test_documents.py::test_vision_latest_summary_prefers_current_006_over_legacy tests/test_documents.py::test_vision_latest_summary_derives_candidates_and_status_without_heavy_payload -q --tb=short
RUN_LOCAL_OLLAMA_TESTS=0 DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests -m 'not local_ollama' -q --tb=short
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_06v.py --preflight --database-url postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
```

DB exacta `licitia_validation_06v`, URL `postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_validation_06v`; no existía al inicio, creada mediante createdb y alembic upgrade head. Current/head `20261013_req_perception_prov_072`; Tender count=0; documentos/páginas/Requirements/ScopeDetails/Quantities/Attributes=0 (siete counts SQL). licitia_test current/head072; licitia_dev current071 sólo leído y no migrado. No copy/create/import de corpus. Reset futuro destructivo exacto, con aprobación explícita y backup, está en protocolo; NO ejecutado aquí.

Compileall PASS exit0; git diff --check PASS; whitespace de nuevos archivos y Git status/diff inspeccionados. Sin stage/commit/push; archivos/reportes históricos untracked preservados.

## Identidades y freeze

Manifest: `backend/evals/document_intelligence_06v_config_v1.json`.

SHA-256: `73d56599fc016a7b11bf43b4e5a9a58bbd008ae28410224c6b78e01c8743f9f2`.

Code manifest SHA-256: `6ad0e80d613009511f58e036088213c23711b0adbcdf8d33fbc9412a5cff1bfd`.

Baseline HEAD completo en manifest y runtime identity; actual run compara HEAD/config/code hash/DB revision de pre-import y final. Guarda Python/executable/platform y provider/model/task configuration disponible. No secrets ni Tender #002 identity/content en config.

FirstPass incluye run_id/start/end, code/config/DB identities, Tender ID sólo después de importación autorizada, snapshot/metrics/provider ledger, errores/review y hashes de documento/provider/pre-import/ledger. run_id safe, timestamps aware/ordered y DB072 requeridos. Directorio exclusivo evita overwrite; FROZEN.json define immutable SHA de JSON/resumen; verifier detecta modificación/incompleto. Análisis posterior genera analysis_<id>.json y sha separado. No primer pase real emitido: sólo mecanismos y casos sintéticos en directorios temporales.

Protocolo fijo: [docs/document-intelligence-06v-protocol.md](../../docs/document-intelligence-06v-protocol.md). V.1 freeze limpio+import autorizado → V.2 pipeline productivo congelado → V.3 report/hash antes de analizar → V.4 verdad humana independiente/reporte separado → V.5 decisión cross-tender y sólo después MVP-07. Tras abrir corpus no tuning ni cambios semánticos hasta freeze; reparación operacional se declara y puede invalidar/reiniciar, jamás reescribir.

## Cierre

Tender #002 inspected=NO. Provider calls=0. Real models=NO. Existing Golden/runtime model results intactos. Stage/commit/push=NO.

Blockers para revisión de preflight: ninguno. La ejecución real sigue bloqueada por código protegido dirty hasta aceptación/commit/freeze limpio y requiere autorización humana explícita del corpus; no se evade esa condición. Plan base sin inferencias autorizadas preserva cobertura limitada; la instrumentación la medirá honestamente, no promete automatización o recall.

**Siguiente acción:** aceptar V.0 y autorizar separadamente el commit/freeze de código preparado; después, sólo mediante autorización nueva explícita, abrir/importar Tender #002 y ejecutar V.1–V.3 conforme al plan. No activar 06.V en este slice.

MVP-06.V.0 BLIND VALIDATION PREFLIGHT COMPLETE — READY FOR HUMAN AUTHORIZATION DECISION
