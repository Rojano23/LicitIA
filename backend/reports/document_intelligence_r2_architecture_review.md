# MVP-06.R.2 — revisión arquitectónica de integración transversal

Starting HEAD: `5166ad8 feat(mvp-06.R.2a): persist requirement perception provenance`.
Implementación lista para revisión; 06.R.2 permanece CURRENT hasta aceptación
arquitectónica. 06.R.1 y 06.R.2a CLOSED; 06.R.3 NEXT; 06.V después de 06.R.

## Mapa productivo

| Dominio | Entrada / puente DI | Consumidor productivo |
|---|---|---|
| Requirements | NormalizedContent Native/OCR y resultados Vision persistidos → `load_document_transcriptions` → normalización R.1 / `route_capability` → SourceBlock | `analyze_tender_requirements` → detector/dedup existentes → `_sync_evidence` → `persist_snapshot` → `write_provenance` de R.2a |
| Evidencia solicitada | RequirementCandidateEvidence → lectura tipada R.2a → `candidate_perception` / `candidate_provenance` | `normalize_tender_requirements` y `analyze_tender_requirement_semantics`: propagación de revisión y provenance en fuentes/expectativas |
| Scope / detalle | Artefactos existentes → frontera compartida de elegibilidad → resultados DI de transcripción y estructura separados | `materialize_document_scope_details` → adapters existentes o adaptador semántico neutral explícito → reemplazo existente por artefacto |
| Scope / estructura | Parsers Native/OCR y contrato Vision existentes → `load_page_structure` → routing R.1 | `orchestrate_document_structure_available_only` → `advance_continuity` → resolución y ScopeSegments existentes |

DI percibe; los motores conservan decisiones de dominio. No se introdujo un
candidato universal. CompanyEvidence no recibió OCR/Vision ni cambios de extracción.

## Comportamiento e invariantes

- Corpus vigente completo: no se añadió filtro por clasificación documental.
  La clasificación sigue siendo contexto descriptivo para las reglas existentes.
  El mismo fragmento puede producir Requirement y Scope por contratos independientes.
- Requirements conserva identidad/dedup de candidatos y evidencia lógica. El
  snapshot JSONB usa el contrato/writer de R.2a sin rediseñarlo; retiene múltiples
  artefactos, generaciones, versión, canales, locators, excerpts/hashes, metadata,
  diagnósticos, conflictos y ACTIVE/DESELECTED. NULL legacy continúa válido.
- El refresh completo marca como DESELECTED las observaciones ausentes de la
  página actual y conserva su historia. Los candidatos históricos exponen
  `perception_active` y `perception_review_required`; soporte exclusivamente
  inactivo no alimenta normalization automático. Las decisiones humanas permanecen.
  Mezclar NULL legacy con provenance nueva no oculta una revisión DI.
- La extracción textual exitosa no certifica fidelidad: Native/OCR/Vision
  permanecen REVIEW_REQUIRED en esta frontera. Ningún umbral nuevo de confianza
  convierte texto disponible en confiable. Los desacuerdos entre textos disponibles
  conservan alternativas y requieren revisión. La evidencia solicitada conserva
  expectativas propuestas y marca interpretación REVIEW_REQUIRED; no afirma
  posesión de evidencia por el licitante.
- TRANSCRIPTION y STRUCTURE tienen routing independiente y pueden usar proveedores
  distintos. Estructura válida con detalle fallido conserva continuidad cuando hay
  prueba; el detalle fallido no se materializa. Texto válido con estructura ausente
  sigue disponible para propuestas, sin inventar agrupación/continuidad.
- La cadena Native → Vision → OCR usa estado estructural neutral. Un fallo,
  conflicto o límite sin prueba produce UNKNOWN / REVIEW_REQUIRED, sin selección
  ni arrastre obsoleto. Un inicio nuevo independiente puede recuperar continuidad.
  El materializador también verifica la continuidad actual antes de permitir
  herencia implícita; segmentos/resoluciones persistidos no sustituyen esa prueba.
- Conflictos estructurales impiden selección. Un binding de identificador declarado
  y fundamentado conserva la señal `CRITICAL_IDENTIFIER_CONFLICT` en la resolución
  productiva. Su descubrimiento y hardening quedan para R.3.
- La elegibilidad Vision se centralizó en la frontera DI. Reselección por fingerprint
  explícito conserva la política de ciclo de vida existente para la misma tarea;
  transcripción y estructura tienen lineage independiente. Sin fingerprint, las
  fuentes son aditivas: no se resuelven desacuerdos por fecha, orden de carga,
  modelo, versión de prompt o preferencia de canal. DESELECTED no reentra a discovery.
- Artefactos/provenance de percepción originales permanecen auditables. La limpieza
  de ScopeDetails derivados por artefacto DESELECTED conserva su límite existente;
  no borra resultados/analysis originales ni snapshots de revisión humana.
- Repetir procesamiento mantiene identidad de RequirementCandidate y su evidencia.
  ScopeDetails conserva idempotencia lógica y reemplazo por tender/documento/página/
  artefacto; sus UUID derivados pueden regenerarse, como antes. No se amplió deletion
  ni hubo borrado entre capacidades. Fallo OCR no elimina detalle Native.
- Scope persiste los campos soportados por sus contratos actuales: canal, documento,
  página, artefacto, locator, excerpt, analysis/page-result y revisión. Su contexto
  DI completo es transitorio; no se agregó persistencia paralela.
- Canales neutrales: NATIVE/OCR/VISION. El alias estructural legado NATIVE_TEXT se
  conserva en contratos existentes. QWEN/OLLAMA son metadata, nunca source_method
  ni autoridad contractual. Los adapters no mutan los valores neutrales.

## Dependencias legadas y límites

Los lectores ORM, NormalizedContent/PageOcrResult y schemas Vision de estructura
005/006 y DETAIL_TRANSCRIPTION siguen siendo específicos de los formatos existentes.
El adapter de detalle Vision continúa como predeterminado. El adapter semántico
neutral permite Native/OCR/Vision con proveedores suministrados explícitamente;
no configura ni ejecuta un LLM automáticamente. Interfaces directas legadas de
adapters continúan compatibles; los materializadores/orquestación productivos
inspeccionados sí atraviesan DI. Los mocks prueban contratos y flujo, no calidad
semántica, fidelidad OCR ni percepción visual real.

Esquema cambiado: NO. Migración requerida: NO. Modelo ORM y writer R.2a intactos.
ADR-0010 añadió la decisión de integración productiva, refresh/auditoría, calidad
no certificada y continuidad fail-closed; permanece pendiente de aceptación
arquitectónica para esta integración. Roadmap actualizado mínimamente.

## Archivos exactos

Modificados:

- `backend/app/document_intelligence.py`
- `backend/app/document_structure_orchestrator.py`
- `backend/app/page_structure_resolver.py`
- `backend/app/requirement_extraction.py`
- `backend/app/requirement_normalization.py`
- `backend/app/requirement_semantics.py`
- `backend/app/schemas.py`
- `backend/app/scope_detail_adapters.py`
- `backend/app/scope_detail_materializer.py`
- `backend/app/vision_scope_detail_adapter.py`
- `backend/tests/test_document_structure_orchestrator.py`
- `backend/tests/test_requirement_extraction.py`
- `backend/tests/test_requirement_perception_provenance.py`
- `backend/tests/test_scope_detail_materializer.py`
- `docs/adr/0010-document-intelligence-capability-routing.md`
- `docs/roadmap.md`

Creados:

- `backend/app/document_intelligence_sources.py`
- `backend/app/requirement_di_adapter.py`
- `backend/app/scope_di_adapter.py`
- `backend/tests/test_document_intelligence_integration.py`
- `backend/reports/document_intelligence_r2_architecture_review.md`

Las expectativas existentes sólo cambiaron donde DI añade auditoría, revisión o
prueba de continuidad actual. El fixture de herencia de ownership ahora fundamenta
su identidad en el texto de la página. Las reglas de obligación, normalización
semántica, ownership y contratos de revisión humana no fueron rediseñados.

## Matrices obligatorias

Todas usan fixtures sintéticos y llamadas productivas. SDI11 suministra bindings
R.1 declarados mediante un adapter de prueba y verifica su consumo por el
orquestador real; no certifica descubrimiento de identificadores.

| Caso | Prueba de integración | Resultado |
|---|---|---|
| RDI01 | `test_requirement_channels[RDI01]` | PASS |
| RDI02 | `test_requirement_channels[RDI02]` | PASS |
| RDI03 | `test_requirement_channels[RDI03]` | PASS |
| RDI04 | `test_RDI04_full_provenance` | PASS |
| RDI05 | `test_RDI05_review_not_trusted` | PASS |
| RDI06 | `test_RDI06_deselected_excluded_audited` | PASS |
| RDI07 | `test_RDI07_same_fragment_scope` | PASS |
| RDI08 | `test_RDI08_idempotence` | PASS |
| EDI01 | `test_requested_channels[EDI01]` | PASS |
| EDI02 | `test_requested_channels[EDI02]` | PASS |
| EDI03 | `test_requested_channels[EDI03]` | PASS |
| EDI04 | `test_EDI04_provenance` | PASS |
| EDI05 | `test_EDI05_conflict_fail_closed` | PASS |
| EDI06 | `test_EDI06_deselected` | PASS |
| EDI07 | `test_EDI07_classification` | PASS |
| EDI08 | `test_EDI08_idempotence` | PASS |
| SDI01 | `test_scope_channels[SDI01]` | PASS |
| SDI02 | `test_scope_channels[SDI02]` | PASS |
| SDI03 | `test_scope_channels[SDI03]` | PASS |
| SDI04 | `test_scope_independent_providers[SDI04]` | PASS |
| SDI05 | `test_scope_independent_providers[SDI05]` | PASS |
| SDI06 | `test_SDI06_structure_survives_detail_failure` | PASS |
| SDI07 | `test_SDI07_text_survives_structure_absence` | PASS |
| SDI08 | `test_SDI08_transition_continuity` | PASS |
| SDI09 | `test_SDI09_failure_no_stale_carry` | PASS |
| SDI10 | `test_SDI10_structural_conflict` | PASS |
| SDI11 | `test_SDI11_identifier_signal` | PASS |
| SDI12 | `test_SDI12_deselected_scope` | PASS |
| SDI13 | `test_SDI13_detail_provenance` | PASS |
| SDI14 | `test_SDI14_idempotence` | PASS |
| SDI15 | `test_SDI15_multi_domain` | PASS |
| XDI01 | `test_XDI01_independent_domains` | PASS |
| XDI02 | `test_XDI02_capability_independence` | PASS |
| XDI03 | `test_XDI03_whole_corpus` | PASS |
| XDI04 | `test_XDI04_no_mutation` | PASS |
| XDI05 | `test_XDI05_metadata_not_truth` | PASS |
| XDI06 | `test_XDI06_no_hidden_fallback` | PASS |

Además: mezcla NULL legacy/DI, ausencia de fuente, error de página cruzada,
fallo OCR sin borrar detalle Native, rechazo de ownership estructural obsoleto
y rechazo de texto Vision no tipado. Total nuevo: 43 pruebas.

## Validación reproducible

482 casos distintos PASS, 0 FAIL, 0 SKIP. Las ejecuciones se superponen:
384 PASS en regresión transversal (42 tests nuevos entonces presentes),
53 PASS en cierre focal/proveedores (43 nuevos + 10 proveedores) y
87 PASS de revisión humana. El último test agregado sólo añadió cobertura;
no hubo cambio productivo después de la regresión transversal.

| Familia | PASS |
|---|---:|
| Integración R.2 | 43 |
| R.1 DI + compatibilidad | 35 (31 + 4) |
| R.2a provenance | 23 |
| Requirements extraction / normalization | 60 (31 + 29) |
| Evidencia solicitada / semantics | 33 |
| Scope adapters / materialización | 31 (10 + 21) |
| Page structure / resolver / orquestador | 58 (12 + 17 + 29) |
| Scope linking / segments / semantic discovery | 41 (14 + 13 + 14) |
| Integración atributos / cantidades | 22 (11 + 11) |
| Revisión humana / API | 87 |
| Proveedores Native/OCR/Vision | 10 |
| CompanyEvidence | 22 |
| Source Effects API/persistencia | 17 |

Scope: 152 pruebas base + 87 de revisión humana = 239 PASS.
CompanyEvidence regression requerida: SÍ, por el módulo compartido de schemas/API;
su extracción/contrato permanece intacto. Source Effect regression requerida:
SÍ, por esa misma superficie API compartida; no cambió ningún resolver/proyección
ni se ejecutaron Goldens de Source Effects.

Comandos ejecutados desde backend:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_compatibility.py tests/test_requirement_perception_provenance.py tests/test_requirement_extraction.py tests/test_requirement_normalization.py tests/test_requirement_semantics.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_linking.py tests/test_scope_segments.py tests/test_scope_semantic_discovery.py tests/test_scope_attribute_integration.py tests/test_scope_quantity_integration.py tests/test_company_evidence.py tests/test_source_effects.py -q --tb=short --junitxml=/private/tmp/r2-validation.xml > /private/tmp/r2-validation.txt 2>&1

/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_integration.py tests/test_documents.py::test_pdf_extraction_tracks_native_text_metadata_and_tender_scope tests/test_documents.py::test_normalize_document_content_preserves_separate_native_and_ocr_sources tests/test_documents.py::test_ocr_auto_skips_native_text_and_runs_on_no_text_pages tests/test_documents.py::test_detail_transcription_is_conditional_and_task_typed tests/test_documents.py::test_detail_failure_after_successful_structure_keeps_next_page_context tests/test_documents.py::test_detail_parser_extracts_fields_and_preserves_raw_text tests/test_documents.py::test_detail_parser_failure_preserves_raw_text_and_marks_review tests/test_documents.py::test_task_fingerprint_differs_by_task_type_and_region tests/test_documents.py::test_vision_assist_failed_page_does_not_fabricate_structured_result tests/test_documents.py::test_structure_scope_aggregated_supply_block_fixture_is_accepted_and_triggers_detail -q --tb=short --junitxml=/private/tmp/r2-provider-validation.xml > /private/tmp/r2-provider-validation.txt 2>&1

/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_scope_review.py tests/test_scope_review_api.py -q --tb=short --junitxml=/private/tmp/r2-human-review-validation.xml > /private/tmp/r2-human-review-validation.txt 2>&1

DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test' /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test' /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
```

Alembic current = heads = `20261013_req_perception_prov_072 (head)`.
Sin roundtrip de migración ni operación contra licitia_dev.

Compileall PASS:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
```

Warnings: seis advertencias conocidas por ejecución (SWIG/PyMuPDF y deprecación
`python_multipart`); no fallos de tests ni certificación de modelos reales.

Git: `git diff --check` PASS; nuevos archivos también revisados con
`git diff --no-index --check /dev/null <archivo>`. `git diff --stat` y
`git status --short` inspeccionados. No hay staging: diff cached vacío;
HEAD sigue en 5166ad8. Los 16 reportes históricos no rastreados permanecen
intactos. Cambios de este slice: 16 archivos modificados y cinco creados,
incluido este reporte. No stage/commit/push.

## Superficies protegidas y cierre

- Contratos/semánticas protegidas de Requirements, RequirementReview,
  CompanyEvidence, ScopeDetail, ScopeAttribute, ScopeQuantity, Human Scope Review,
  Source Effects, Technical Alternatives y Alternative Compliance sin rediseño.
- `source_effect_resolution.py`, `source_effect_partial_resolution.py` y
  `effective_source_projection.py`: sin cambios.
- Frontend y pricing: sin cambios.
- Tender #001 Golden labels, Source Effect Goldens y versioning Golden: sin cambios.
- Tender #002: no inspeccionado/buscado/parseado/usado; permanece blind
  out-of-sample hasta 06.V, después de todos los slices 06.R.
- Ejecución real Vision/Ollama/Qwen = NO. Source Effect Qwen NO-GO permanece.
- Blockers técnicos: ninguno. Aceptación arquitectónica pendiente; no se cierra R.2.
- Siguiente slice recomendado: MVP-06.R.3 — Critical Identifier + Conflict / Review Hardening.

MVP-06.R.2 TRANSVERSAL DOCUMENT INTELLIGENCE INTEGRATION COMPLETE — READY FOR ARCHITECT REVIEW
