# MVP-06.V.4a — Structural identity / trust safety

HEAD inicial: `c1c6ff4870dc94009b10d62f47020ef6cdf9d580`.

## Auditoría anterior a la implementación

`page_structure_resolver._EXPLICIT_ITEM_START_RE` acepta PARTIDA, ITEM, CONCEPTO y NO con `\s`, incluidos saltos de línea. Native/OCR consideran suficiente una sola identidad numérica normalizada y ausencia de continuidad para construir estado VALID, segmento sin revisión y outgoing owner. No se exige evidencia del rol contractual de la fila. Un rótulo genérico y el primer número de otra línea/columna pueden satisfacer el patrón.

`document_intelligence_sources.load_page_structure` traduce VALID sin review a Quality.RELIABLE; routing y continuidad lo aceptan. El orquestador persiste resolución/segmentos a partir de esa selección. No es problema de la aritmética de confianza ni del almacenamiento: la premisa de identidad del candidato textual es demasiado débil. OCR comparte esa misma premisa; su confidence numérica no debe suplirla. Vision conserva su contrato tipado/grounding, sin cambiar prompts, providers ni ejecutar inferencias.

## Invariante y ubicación del cambio propuesto

La elegibilidad pertenece al productor de estructura textual, antes de convertir un match en VALID. Separar detección (conservar candidato/anchor) de trust: identidad declarada de item sobre la misma línea y descripción, o para etiquetas genéricas, campos explícitos cantidad/unidad asociados a la fila. Preguntas y referencias con líderes de puntos no acreditan una partida. Ausencia de prueba produce UNKNOWN/review, sin outgoing carry confiable. No usar clasificación documental global para bloquear páginas mixtas. Múltiples partidas positivas conservan la abstención previa por ownership ambiguo.

Cambio acotado a parser Native/OCR y tests sintéticos. No cambia schema, contrato de percepción ni políticas de proveedores. No mejora extracción de Scope/Attributes/Quantities ni cobertura OCR. Los intentos y su adjudicación permanecen inmutables.

## Implementación y límites

Se modificó `page_structure_resolver.py`: detección de rótulo conserva candidatos, pero la confianza exige label+identificador en la misma línea y descripción; PARTIDA/ITEM son declaraciones explícitas de rol. Se admite descripción a continuación. CONCEPTO/NO por sí solos no acreditan rol: requieren campos explícitos cantidad/unidad en la fila, directamente o mediante encabezado inmediato alineado por delimitadores. Preguntas y referencias con líderes de puntos no pasan el gate. No hay blacklist de títulos/documentos, score, penalidad ni umbral nuevo.

Ante insuficiencia se conservan identidades/anchors/provenance como candidatos revisables, con UNKNOWN y sin outgoing confiable. En OCR se conserva el ID del artefacto que realmente aporta el anchor elegible, en lugar de tomar arbitrariamente el primer artefacto. Una página mixta conserva una partida positivamente sustentada sin convertir el contexto adyacente en owner.

Se versionó `STRUCTURE_RESOLVER_VERSION` a `mvp-06.V.4a-structural-identity-v2` en `document_structure_orchestrator.py`. El fingerprint ya incluye esta versión: una futura ejecución explícita no debe reutilizar un cache producido bajo la regla antigua. Este slice NO ejecuta ese refresco sobre los intentos históricos.

No cambia generación Vision, contrato/schema, proveedor, política, API, algoritmo de Scope/Attributes/Quantities ni configuración del blind run. Tampoco certifica todos los formatos/documentos ni mejora recall general. La evidencia es sintética; no se afirma haber corregido retroactivamente los resultados de los intentos.

## Ajustes de fixtures y matriz

Dos fixtures existentes de `test_scope_detail_materializer.py` usaban sólo PARTIDA2 para justificar ownership. Se añadió descripción sintética de suministro, conservando todas sus expectativas: prueban herencia/conflicto, no permiso de confiar en una etiqueta aislada. ST13 prueba expresamente la abstención de ITEM sin descripción. No se debilita producción para pasar esos tests.

| Casos | Resultado esperado |
|---|---|
| ST10 | Índice con rótulo/ordinal/referencias: revisión |
| ST11 | Preguntas, incluso con labelITEM: revisión |
| ST12 | Navegación/referencias: revisión |
| ST13 | Tabla/etiqueta ambigua sin identidad suficiente: revisión |
| ST14 | Cantidad/unidad explícitas o header vinculado: positivo |
| ST15 | Partida técnica, descripción inline o siguiente: positivo |
| ST16 | Página mixta: sólo estructura positivamente sustentada |
| ST17 | Provenance original conservada, sin selección confiable falsa |
| ST18 | Identidad/anchor del candidato permanecen auditables |
| ST19 | Repetición determinista/persistencia idempotente; versión cambia fingerprint |
| ST20 | Preparación V.3a y unavailable por capacidad permanecen intactos |

La matriz corre Native y OCR con DTOs sintéticos, sin proveedores reales, más integración ORM/DI/persistencia en licitia_test. No se modifica ni crea un Golden de Tender002.

## Validación final

ST10–ST20: PASS (24 casos parametrizados/integración). Primer pase test-first:14 failed/7 passed; tras gate inicial41/41 con resolver. La regresión final incorpora preservación de descripción a continuación y dos fixtures de Scope corregidos sin cambiar expectativas.

- focused: exit0; 542 passed, 1 deselected, 7 warnings in 31.00s

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence.py tests/test_document_intelligence_06v_preflight.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_structural_trust_safety.py tests/test_document_preparation_recovery.py tests/test_documents.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_critical_identifier_propagation.py tests/test_structural_trust_propagation.py tests/test_scope_detail_materializer.py -m 'not local_ollama' -q
```

- full: exit0; 1753 passed, 1 deselected, 7 warnings in 152.47s (0:02:32)

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -m 'not local_ollama' -q
```

- compileall: exit0; PASS

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
```

Exclusión intencional:1 test opt-in real-Ollama;7 warnings existentes (deprecaciones SWIG/python_multipart y ccache ausente). Cero proveedores reales. Alembic licitia_test current/head:20261013_req_perception_prov_072. Sin schema ni migraciones.

Integridad: 107 archivos históricos SHA-256 idénticos, incluidos Attempt1, freeze/first-pass Attempt2 y adjudicación MD/JSON. No rerun, nuevo blind run_id ni modificación DBvalidation. La decisión arquitectónica histórica OperationalPASS/SemanticFAIL permanece intacta.

Archivos de implementación: backend/app/page_structure_resolver.py; backend/app/document_structure_orchestrator.py (sólo versión). Tests: backend/tests/test_structural_trust_safety.py (nuevo); backend/tests/test_scope_detail_materializer.py (dos fixtures). Este reporte es nuevo; no se editó documentación ni reporte histórico.

git diff --check PASS; sin stage/commit/push. Listo para revisión arquitectónica, sin certificación semántica de un nuevo pase ciego.
