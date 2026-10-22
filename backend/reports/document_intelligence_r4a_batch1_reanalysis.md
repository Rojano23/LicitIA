# MVP-06.R.4a Phase 2 — Harness fidelity + offline replay

Starting HEAD: `d399b7a feat(mvp-06.R.3): harden critical identifier conflict propagation`, main.
R.4a CURRENT; R.4b NEXT; 06.V protegido. La fase 2 cierra implementación/validación del harness y replay acotado, no certificación de convergencia.

## Cambios y alcance

Producción modificada: NO. Llamadas reales a proveedores: 0; intentos bloqueados durante replay: 0; entregas del transporte almacenado: 3. No Tesseract, Vision/Ollama/Qwen nuevos, red HTTP ni subprocess de adquisición. Un guard impide HTTP, ejecución del cliente, OCR y subprocess dentro del replay. Los tests prueban también el rechazo de un intento explícito.

Archivos de calibración modificados:
- backend/app/document_intelligence_calibration.py
- backend/scripts/run_document_intelligence_calibration.py
- backend/tests/test_document_intelligence_calibration.py (retira el mock que inyectaba metadata ausente; captura no adjudica estructura)

Archivos nuevos de calibración:
- backend/app/document_intelligence_calibration_fidelity.py
- backend/app/document_intelligence_calibration_replay.py
- backend/tests/test_document_intelligence_calibration_fidelity.py

Documentación: docs/roadmap.md, actualización mínima de fase 2 conservando estados y Tender #002 protegido.
Outputs nuevos, untracked: backend/reports/di_r4a_batch1_reanalysis.json y este reporte. Los tres resultados originales y los reportes de fases previas no se sobrescriben. Sin stage/commit/push.

## Defectos corregidos

1. Ausencia literal ya no equivale automáticamente a omisión material. Se distinguen EXACT_FORMAT_DIFFERENCE, OCR_NOISE, CRITICAL_TOKEN_MISMATCH, NUMERIC_MISMATCH, UNIT_MISMATCH, IDENTIFIER_MISMATCH, MATERIAL_TEXT_OMISSION y REFERENCE_SOURCE_CONFLICT. Los bindings estructurados no se puntúan como prose omission.
2. NFC y colapso de whitespace sólo comparan formato: no alteran ceros, case, sufijos, barras, guiones ni valores canónicos. Ruido `|` se identifica sólo en separador MODELO:/valor; no se elimina dentro de un identificador.
3. Filas de equipo se conservan individualmente con identidad del caso humano, excerpt exacto, modelo, cantidad y unidad. Se alinean por descripción exacta con whitespace o modelo único; no por orden, edit distance ni similitud generativa. La lectura fuente alternativa sólo puede localizar una fila disputada y nunca adjudicar su modelo.
4. FAILED/null structured_json no se vuelve transcripción válida: se separan VALIDATION_FAILED, OUTPUT_TRUNCATED, CANONICAL_RESULT_UNAVAILABLE y PERCEPTION_PARTIAL. Sólo strings raw_visible_text completos se leen como diagnóstico; no se repara el JSON truncado ni se completa su cola.
5. La estructura ya no recibe metadata inventada desde el harness de captura. Captura devuelve observación pendiente de replay. En offline se reutilizan parser/normalizador y `analyze_vision_document_structure_only_isolated` productivos con transporte congelado y todas sus sesiones redirigidas a test. El servicio real construye `_vision_runtime`, `_continuity_state_quality` y contexto; luego DI/R.3 deciden continuidad.
6. Se separan diferencias de percepción, fallo operativo/validación, defecto de calibración, error de dominio y safe review. Safe miss requiere expectativa material aprobada y fallo/rechazo seguro; formato y conflicto de referencia por sí solos no suman.

## Reanálisis del mismo lote

Inputs exactos:
- backend/reports/di_r4a_tesseract_b4_p4_transcription.json
- backend/reports/di_r4a_vision_b4_p4_transcription.json
- backend/reports/di_r4a_vision_b4_p1_p3_structure.json

Hashes originales/Golden verificados contra el reporte de análisis inicial y el manifiesto congelado. Identidad sólo Tender #001 B-4. No etiquetas nuevas.

| Métrica | Tesseract validado | Vision validada | Vision raw diagnóstico |
|---|---:|---:|---:|
| Filas esperadas | 7 | 7 | 7 |
| Filas preservadas | 7 | 0 disponibles | 7 |
| Cantidades / unidades coincidentes | 7 / 7 | No evaluables como éxito | 7 / 7, no canónicas |
| Modelos adjudicables coincidentes | 6 | No evaluables | 6, no canónicos |
| Conflictos fuente–Golden | 1 | Sin salida canónica | 1 |
| Omisiones materiales de excerpts aprobados | 0 | **null: fallo de validación** | No certificado como salida exitosa |
| Safe misses | 0 | 1 | No se suma otro miss por el raw |

Tesseract: las tres ausencias por line wrap se clasifican como formato; el `|` antes de AAR145-S50 como OCR_NOISE. El modelo de la primera fila es REFERENCE_SOURCE_CONFLICT. No se identifican cinco obligaciones omitidas. La cobertura de prose contractual completo sigue limitada a referencias existentes; cero omisiones de los excerpts scoreables no certifica transcripción completa.
Vision: raw parcial contiene siete equipos y cantidades, pero el JSON termina a mitad de una cadena de firmas. Estado validado FAILED y texto canónico vacío. Las 14 ausencias anteriores eran consecuencia de indisponibilidad tras validación, no catorce errores independientes de lectura. La cola truncada sigue como diagnóstico material; no se convierte en una etiqueta Golden de fidelidad de prose.

Conflicto explícito, review_required=true:
Golden `AA143-H50/K4400`; Tesseract `AAI143-H50/K4A00`; raw Vision `AA143-H50/K4400`; lectura fuente autorizada/documentada `AAI143-H50/K4A00`. El modelo disputado se excluye de adjudicación automática, tanto si el proveedor coincide con Golden como con la lectura visual. No cambia la verdad humana aprobada ni se declara correcto/incorrecto ese proveedor hasta mantenimiento Golden separado.

## Contexto de estructura y diagnóstico

Estructuras SCORED: **0**. UNSCORED_DIAGNOSTIC: **3**. No hay Golden estructural aprobado verificado para páginas 1–3; labeled_observations de estructura permanece 0.

El transporte entrega el raw existente al parser/normalizador productivo y conserva metadata real de proveedor. El servicio suministra contexto abierto 1 para p2 y 2 para p3; la inferencia original recibió null en todas. Esto es replay determinista de la política con resultados almacenados, no prueba de cómo respondería el modelo si hubiera visto ese contexto. Se conservan ambos hechos. Render/model loading no se ejecutan: los ceros del wrapper para geometría/render son placeholders offline, no mediciones operacionales.

DI de estructura: p1 RESOLVED/VALID/outgoing 1; p2 RESOLVED/VALID/outgoing 2; p3 RESOLVED/VALID/outgoing 3; p4 REVIEW_REQUIRED/UNKNOWN/sin outgoing. Stale carry: **0**.

Persisten diagnósticos iniciales, sin transformarlos en truth labels:
- p1: inicio 1 compatible con diagnóstico visual.
- p2: sólo inicio 2; inspección previa señala falta de continuación/cierre de 1.
- p3: inicio 3; inspección previa sugiere continuación de 2.

**Hallazgo que impide GO:** producción genera segmentos candidatos 1, 2 y 3 con review_required=false en el fixture. No hay etiqueta aprobada para certificar su exactitud; las discrepancias diagnósticas de p2/p3 siguen siendo riesgo importante. Corregir el contexto del harness elimina un UNKNOWN artificial, pero no demuestra fidelidad de identidad. No se cambió producción para ocultarlo ni se contabilizó la interpretación visual como Golden.

## Mapa de replay y resultados de dominio

- Tesseract p4 → PageOcrResult TESSERACT 5.5.3 / spa+eng → NormalizedContent OCR → neutral DI → discovery/normalization de Requirements, requested Evidence y Scope disponibles.
- Vision FAILED p4 → DocumentVisionAnalysis/PageResult FAILED con raw/warnings originales → DI FAILED, texto vacío → ningún dato parcial se transforma en detalle contractual.
- Vision structure p1–3 → servicio/orquestador productivo con transporte offline → artefactos de estructura/metadata productiva → DI/R.3 → scope segments y continuidad.

Se crea un tender/documento propietario con UUID distintos en licitia_test; preserva SHA-256 del documento fuente, revisión, páginas, excerpts, artefactos/generaciones y canal. No se copian ni alteran decisiones humanas de dev. Todas las sesiones internas del orquestador están ligadas al mismo test engine. Fixture eliminado al terminar, probado mediante consulta. No migración nueva ni acceso mutante a dev.

Requirements: **0 candidatos** en el lote; evidencia solicitada: **0**. Se ejecutaron los caminos reales y no se forzó alcance de ejecución a convertirse en obligación documental de oferta. No hay RequirementCandidateEvidence nueva a la que atribuir provenance; las regresiones R.2/R.2a/R.3a verifican ese contrato en fixtures aplicables.

Scope: **0 detalles**, 5 artefactos UNSUPPORTED, NO_EVIDENCE. Los adapters predeterminados no interpretan detalle semántico OCR; estructura sola no es DETAIL_TRANSCRIPTION y la transcripción Vision está fallida. No se agregó un proveedor semántico de evaluación para fabricar resultados productivos. Es una limitación de cobertura real, no prueba de recall exitoso.

Cantidades/atributos: **0 / 0 registros**. El replay no dispone de detalles productivos válidos y no cruza ownership incierto para generarlos. Esa ausencia no certifica extracción positiva. HF22/HF23 también ejercitan bindings **positivos sintéticos** de los materializadores existentes: conflicto de item deja ownership vacío y cantidades/atributos REVIEW_REQUIRED; no son mediciones del modelo real.

Provenance: persisten text/excerpt, OCR result y NormalizedContent IDs, locator, doc/page/revisión, Vision analysis/page-result IDs, fingerprint, raw, warnings y canal; los readers productivos los transportan en evidencia neutral. La ambiguity fuente–Golden permanece en calibración, no se introduce como una segunda observación de proveedor en el dominio. Con una sola transcripción usable no se fabrica CONFLICT; sigue REVIEW_REQUIRED por fidelidad no certificada.

Idempotencia: dos pasadas mantienen filas, owners, review y fingerprints semánticos; no duplicados de candidatos/details/quantity/attribute. Los IDs de scope segments se regeneran por el contrato existente delete/reinsert: se reporta incidental_segment_ids_stable=false, sin prometer estabilidad de UUID que producción no garantiza. Se comparan fingerprints significativos, no texto generativo ni IDs accidentales.

## Confianza y seguridad

Domain trust assessed: **2**, en la frontera productiva de las transcripciones aplicables con equipos esperados aprobados: Tesseract no se eleva a RELIABLE y Vision FAILED se rechaza. Categoría review_required_correct=2. No equivale a dos materializaciones Scope exitosas.
trusted_correct=0; trusted_incorrect=0 adjudicados; review_required_unnecessary=0; unassessed_structural_truth=3. Requirements/requested Evidence quedan no aplicables para este lote; Scope detail no soportado se registra expresamente, sin clasificarlo como inexistencia del requisito real.
Sin referencia material aprobada, el mismo replay no aumenta assessed: HF28 lo verifica.

UNSAFE_TRUSTED_CONTRACTUAL_ERRORS observados en casos adjudicables: **0**. Estructura no adjudicada: **3**, con los tres segmentos candidatos sin revisión y diagnósticos adversos en p2/p3. El cero no demuestra ausencia global de confianza insegura. SAFE_MISS de transcripción: **1** (Vision failed frente a equipos materialmente esperados). Tesseract formato/conflicto no cuenta como ordinary safe miss. Cobertura semántica OCR ausente se reporta aparte y no se convierte en éxito de seguridad/automatización.
Readiness certified=false. R.4a no se cierra.

## Latencia preservada

Tesseract p4 1.549 s; Vision transcription p4 86.592 s; Vision structure p1 35.825 s, p2 35.638 s, p3 36.923 s. Se reutilizan exactamente las mediciones originales; no se estima ni recomputa inferencia. Model-load overhead y total process timing: unavailable/null. No se ejecuta otro lote para obtener tiempos.

## Matriz HF01–HF30

| Caso | Prueba | Resultado |
|---|---|---|
| HF01 | Line wrap no es omisión material | PASS |
| HF02 | Whitespace no es omisión material | PASS |
| HF03 | Ruido de separador OCR separado | PASS |
| HF04 | Sufijo de identificador sigue siendo material | PASS |
| HF05 | Cantidad incorrecta material | PASS |
| HF06 | Unidad incorrecta material | PASS |
| HF07 | Omisión real de prose material | PASS |
| HF08 | Conflicto fuente–Golden separado | PASS |
| HF09 | Conflicto sin adjudicación automática | PASS |
| HF10 | Raw truncado sólo diagnóstico | PASS |
| HF11 | FAILED no puede dar transcripción canónica | PASS |
| HF12 | Cero llamadas durante replay | PASS |
| HF13 | Metadata generada por servicio productivo | PASS |
| HF14 | Cliente raw sin metadata; no se inventa en test | PASS |
| HF15 | Estructura sin label diagnóstico | PASS |
| HF16 | Diagnóstico no crea etiquetas | PASS |
| HF17 | 7/7 equipos medibles | PASS |
| HF18 | Test exclusivo, dev rechazado y fixture limpiado | PASS |
| HF19 | Provenance neutral conservada | PASS |
| HF20 | REVIEW_REQUIRED conserva transcripciones inseguras | PASS |
| HF21 | Stale carry cero | PASS |
| HF22 | Cantidad real no generada; positivo sintético sin owner confiable | PASS |
| HF23 | Atributo real no generado; positivo sintético con revisión | PASS |
| HF24 | Idempotencia semántica | PASS |
| HF25 | Contador unsafe detecta confianza incorrecta | PASS |
| HF26 | Safe miss excluye formato | PASS |
| HF27 | Safe miss excluye conflicto de referencia | PASS |
| HF28 | Assessed sólo con expectativa material aprobada | PASS |
| HF29 | Tender ajeno rechazado | PASS |
| HF30 | Modo offline rechaza adquisición y bloquea HTTP | PASS |

## Validación reproducible

Comando exacto final desde backend:
```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_integration.py tests/test_critical_identifier_propagation.py tests/test_document_structure_orchestrator.py tests/test_requirement_perception_provenance.py tests/test_cross_capability_provenance.py tests/test_requirement_semantics.py tests/test_scope_detail_materializer.py tests/test_scope_quantity_integration.py tests/test_scope_attribute_integration.py -q
```
**345 passed, 0 failed, 6 warnings, 14.74s.** Conteos: HF 30; CAL 29; R.1 DI/compat 35; R.2 integration 43; R.3 critical propagation 47; structure orchestration 29; provenance R.2a 23; cross-capability R.3a 33; requested Evidence/semantics 33; scope materializer 21; quantity integration 11; attribute integration 11.
Warnings existentes SWIG/PyMuPDF y python_multipart; ningún warning nuevo de schema.
Alembic licitia_test current/head: `20261013_req_perception_prov_072`. No schema change ni migration nueva. Compileall app/scripts/tests PASS con intérprete absoluto obligatorio. Git diff --check y whitespace de archivos nuevos PASS al entregar.

Comando offline utilizado, sin inferencia:
```sh
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_calibration.py --offline-replay --no-real-model --batch-artifacts reports/di_r4a_tesseract_b4_p4_transcription.json reports/di_r4a_vision_b4_p4_transcription.json reports/di_r4a_vision_b4_p1_p3_structure.json --output-json reports/di_r4a_batch1_reanalysis.json
```

## Decisión siguiente

**B — creación humana acotada de etiquetas estructurales de B-4 páginas 1–3.** Debe ser un trabajo separado explícitamente autorizado: este slice no las crea. La adjudicación debe aclarar dos segmentos en p2 y continuidad/identidad en p3, contrastando el original y conservando su versión/hash. Hace falta también mantenimiento humano separado para el modelo fuente–Golden disputado; no se altera ahora.
No se propone otro lote real, tuning de prompts, aumento de presupuesto de salida ni nuevo proveedor en esta entrega. La cobertura semántica OCR y los candidatos estructurales sin revisión quedan visibles para la decisión posterior de arquitectura; no se proclama readiness mientras no haya verdad/coverage suficiente.

Golden aprobado y tres resultados originales sin cambios; hashes verificados. Tender #002 no inspeccionado ni usado. Source Effect Qwen NO-GO intacto. Modelos reales/Tesseract nuevos ejecutados=NO. Los cambios previos del working tree se conservaron; sólo calibración/test/documentación del slice y dos outputs nuevos. Sin stage/commit/push.

MVP-06.R.4a PHASE 2 HARNESS FIDELITY + OFFLINE REPLAY COMPLETE — READY FOR CALIBRATION REVIEW
