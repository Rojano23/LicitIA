# MVP-06.R.4a Phase 3B — Structural Golden Rescore

Estado: COMPLETE — READY FOR CALIBRATION REVIEW. MVP-06.R.4a sigue CURRENT; readiness no certificado.

El Golden humano confirma dos errores estructurales que el replay del flujo productivo dejó con routing RESOLVED y ScopeSegment.review_required=false. P2 pierde continuidad/cierre de ITEM_1; P3 introduce ITEM_3 en lugar de continuar ITEM_2. No se implementó corrección productiva.

## Golden congelado

Aprobación explícita del usuario sin correcciones, revisión `human-chat-b4-v1-approval-1`. Golden `b4-human-structure-v1`, documento B-4 versión 1, páginas 1–4. Archivo: `backend/evals/document_intelligence_b4_structure_golden_v1.json`.

PDF SHA-256: `5b1ecdcf6ab0ec6a1008bf41554367dc3a917fce2a79b197a5289193362ba311`.

Content SHA-256: `885f9c623a07092d3a1880a1736517dd2917888b2435320e9fcaaedcfc082ef5` (JSON canónico excluyendo su propio campo content_sha256).

File SHA-256: `60520abdb48862cf99763d40e355cc03f6e3771e4f73f1c438f7c00c069feb71` (bytes completos).

El loader tipado valida aprobación, contenido, PDF y hashes de página; freeze rechaza sobrescribir una versión distinta. ITEM_1/ITEM_2 sólo son identidades Golden de comparación. CLOSES representa cierre estructural dentro de B-4, no cumplimiento del servicio ni exclusión de obligaciones de otros documentos. El número del pie no identifica una partida.

| Página | Hash de PNG humano aprobado |
|---|---|
| P1 | `ea80aa4c697d718a0b281d7bf174b90130eaa9c416f29c1c91a4c441845e2bb1` |
| P2 | `a78371c7cae5b34b1c4482c551c98fbd69b6b9edb878b73ddee9ebdf549a0474` |
| P3 | `87fe33b7c9ea727378687c6ccf500b95480e1d5c00cefad11437f53077409ef6` |
| P4 | `ea42337fe661b9185d27d97ddcea9be9de095a7f05452839e126fdb23a34350b` |

Los PNG humanos son renders 1.5×; las imágenes de inferencia originales son 2×. Se verificaron sus hashes por render local del mismo PDF aprobado; esto no ejecutó inferencia ni alteró los resultados Vision.

## Rescore por página y frontera

| Página | Resultado | Hallazgo | Latencia original |
|---|---|---|---|
| P1 | CORRECT | STARTS y CONTINUES_OUT ITEM_1 | 35.825 s |
| P2 | PARTIAL | Inicio/salida ITEM_2 correctos; faltan entrada, continuación y cierre ITEM_1 | 35.638 s |
| P3 | INCORRECT | Falso inicio/salida ITEM_3; falta continuidad ITEM_2 | 36.923 s |
| P4 | Sin observación Vision | Golden aprobado, sin fabricar resultado | No disponible |

| Frontera | Resultado | Evidencia |
|---|---|---|
| P1→P2 | INCORRECT | Salida izquierda correcta; entrada derecha incorrecta |
| P2→P3 | INCORRECT | Salida izquierda correcta; entrada derecha incorrecta |
| P3→P4 | UNASSESSABLE | Sin observación P4; chequeo parcial de salida P3 contra Golden P4 falla |

Dimensiones separadas: incoming, outgoing, starts, continues, closes, group_identity, ordered_events y boundary en JSON. No se infiere cierre a partir de outgoing nulo; sólo se reconoce transición explícita entre segmentos de distintos propietarios. La superficie original del proveedor se conserva separada de la normalización efectiva del replay.

Contadores: 1 falso inicio; 2 continuaciones perdidas; 1 cierre perdido; 2 errores de identidad; 0 conflictos de proveedor; 0 stale carry; 0 escalaciones correctas de revisión; 2 unsafe trusted structural errors. Las tres páginas observadas son evaluables. Confianza adjudicada: 1 trusted_correct, 2 trusted_incorrect, 0 review_required_correct, 0 unassessed.

## Replay aislado

Se reingirió exclusivamente `di_r4a_vision_b4_p1_p3_structure.json` en `licitia_test`, mediante parsers, normalización, routing, persistencia y materializadores existentes. El contexto productivo reconstruido offline no demuestra cómo habría respondido el modelo con ese contexto durante inferencia original.

Tres entregas almacenadas y tres ScopeSegments, claves 1/2/3, todos sin revisión. Requirements=0; Requested Evidence=0; ScopeDetail=0; cantidades=0; atributos=0. Los tres artefactos structure-only son UNSUPPORTED para detalle; Scope materialization=NO_EVIDENCE. No se forzaron adapters, cantidades ni atributos. El riesgo de asociación futura incorrecta es estructural: este replay no demuestra daño económico o cantidades materializadas incorrectas.

Dos pasadas conservan fingerprints semánticos: idempotent=true. Los UUID incidentales de segmentos se regeneran (incidental_segment_ids_stable=false). Provenance conserva documento/version/página, analysis ID, page-result ID, contrato y locator del fixture aislado; el reporte conserva la identidad/hash original. Fixture eliminado mediante cleanup; no se modificó licitia_dev.

La evaluación genérica anterior a Golden se conserva como pre_golden_domain_trust; domain_trust y unsafe_trusted_contractual_errors contienen la adjudicación humana estructural. Latencias sólo copiadas del lote existente; no se midió overhead nuevo ni se ejecutó render durante la entrega del replay.

## Validación reproducible

Desde backend, Python obligatorio `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`:

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_b4_structural_rescore.py
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py -q
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q app/document_intelligence_structural_golden.py app/document_intelligence_structural_rescore.py scripts/run_b4_structural_rescore.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
```

99 passed, 0 failed, 6 warnings en 5.06 s: GS=25, HG=15, CAL=29, HF=30. Warnings existentes de SWIG/PyMuPDF y python_multipart; runner también informa deprecación de fitz. Compileall exit 0. Alembic `20261013_req_perception_prov_072 (head)`; sin migraciones nuevas.

| Caso | Comprobación | Estado |
|---|---|---|
| GS01 | Carga aprobada | PASS |
| GS02 | Hashes de página | PASS |
| GS03 | Fuente alterada rechazada | PASS |
| GS04 | Inmutabilidad | PASS |
| GS05 | Candidato rechazado | PASS |
| GS06 | Ingestión P1–P3 | PASS |
| GS07 | Cero proveedores | PASS |
| GS08 | Boundary | PASS |
| GS09 | Continuación | PASS |
| GS10 | Identidad | PASS |
| GS11 | Falso inicio | PASS |
| GS12 | Continuaciones perdidas | PASS |
| GS13 | Cierre perdido y transición correcta | PASS |
| GS14 | Escalamiento de revisión | PASS |
| GS15 | Errores confiados inseguros | PASS |
| GS16 | Stale carry | PASS |
| GS17 | Boundary P1→P2 | PASS |
| GS18 | Boundary P2→P3 | PASS |
| GS19 | P4 ausente | PASS |
| GS20 | Determinismo | PASS |
| GS21 | Aislamiento test | PASS |
| GS22 | Idempotencia semántica | PASS |
| GS23 | Provenance | PASS |
| GS24 | Restricción Tender #001 sin leer otro corpus | PASS |
| GS25 | Modelo no constituye verdad | PASS |

## Integridad, Git y siguiente paso

Hash del resultado Vision original: `e37b20c8badc558516e1335beebd5285532c09b08ed339f0711a0abb4abe5aed`. Los tres artefactos del primer lote conservan sus hashes históricos; PDF y PNG aprobados verificados. Candidato y resultados Vision existentes sin cambios. Provider calls=0; blocked attempts=0; ningún modelo real, OCR nuevo ni proveedor ejecutado. Tender #002 no inspeccionado ni utilizado.

Sólo se añadieron herramientas/contratos de evaluación, pruebas, Golden aprobado y reporte de rescore, más sincronización mínima de roadmap. No cambios de runtime productivo, adapters, prompts, migraciones o política Source Effects. HEAD permanece `dc8f825`; no stage/commit/push. Reportes históricos y archivos ajenos preservados. `git diff --check` y checks de whitespace de nuevos archivos sin errores; estado/diff inspeccionados. Los archivos nuevos aún son untracked y no aparecen en git diff --stat.

Recomendación única: **D — Production Architecture Correction**, en un slice separado y autorizado: investigar y corregir la propagación de revisión ante continuidad/identidad estructural ambigua o inconsistente. No aumentar inferencias ni certificar readiness antes de resolver los dos errores confiados observados. Esta fase se detiene después del reporte.

MVP-06.R.4a PHASE 3B STRUCTURAL GOLDEN RESCORE COMPLETE — READY FOR CALIBRATION REVIEW
