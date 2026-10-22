# MVP-06.R.4a — fase 1 de calibración

Starting HEAD: `d399b7a feat(mvp-06.R.3): harden critical identifier conflict propagation`, main.
R.1/R.2a/R.2/R.3a/R.3 CLOSED; R.4a CURRENT; R.4b NEXT; 06.V después de R.4b.
No se cierra R.4a hasta revisar resultados reales. Este reporte es diagnóstico y permanece untracked.

## Inventario read-only de Tender #001

Identidad: `decd32ae-2c1f-4520-89bc-d845c986a7ba`, `SNR-CAD-265-CA-S-2026`.
24 registros documentales, 415 páginas persistidas: 161 TEXT_ONLY, 136 IMAGE_ONLY, 118 MIXED_CONTENT.
Incluye revisiones documentales y un registro sin páginas; no se presenta como 24 documentos vigentes independientes.
279 páginas con texto nativo disponible. 274 artefactos OCR: 137 TESSERACT + 137 PADDLEOCR, conservados por separado.
30 resultados Vision históricos: 25 qwen3-vl:4b-instruct + 5 qwen3-vl:4b. No todos son elegibles para ambas capacidades.
La lineage es específica por capacidad: en transcripción Vision hay 24 ACTIVE (16 UNAVAILABLE, 7 FAILED, 1 REVIEW_REQUIRED) y 1 DESELECTED REVIEW_REQUIRED. Estructura Vision: 7 ACTIVE (4 RELIABLE, 3 REVIEW_REQUIRED).
Native: 279 transcripciones ACTIVE REVIEW_REQUIRED; estructura 1 RELIABLE y 278 REVIEW_REQUIRED.
OCR: 274 transcripciones ACTIVE REVIEW_REQUIRED; estructura 9 RELIABLE y 265 REVIEW_REQUIRED.
El inventario contiene IDs, versiones, hashes documentales, perfiles, fuentes completas, estados, conflictos, modelos, prompts y latencias históricas cuando existen.
13 páginas alimentan Requirements; 7 requested Evidence; una página alimenta Scope (11 detalles B-4 página 4); no hay cantidades/atributos persistidos actuales en dev.
Estos son vínculos existentes de dominio; no son un replay nuevo ni medición de recall.

B-4: páginas 1–4 IMAGE_ONLY, con ambos OCR presentes. Las estructuras Vision históricas observan 1→1 en páginas 1–2 y 2→2 en páginas 3–4. La frontera 2→3 carece de prueba compatible: continuidad UNKNOWN, sin carry viejo; página 4 no recupera identidad mediante una continuación heredada.

## Golden congelado

Las referencias originales no se escriben. Los hashes se toman antes de leer percepción y se verifican al concluir.
El runner también rechaza drift respecto del manifiesto congelado antes de adquirir o interpretar nuevos resultados.
El manifiesto sólo fija selección de casos, no agrega verdad humana.
- `backend/evals/semantic_scope_golden_v1.json`: `ad9d44a67022fa1eaec3181799a88b93c4c6dd04572fff46f31c3ac0c244af86`
- `backend/evals/technical_attribute_golden_v1.json`: `ad2e3707f5b7a2e53e44339108c14669d9697ad733af3527a8e40216dd7b991b`
- `backend/evals/scope_quantity_golden_v1.json`: `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7`

La aprobación de un Golden de dominio no certifica toda la transcripción de la página. Se puntúan exclusivamente excerpts aprobados de cantidad/atributo; no se convierten source_text, outputs previos, estructuras o ejemplos documentales en nuevas etiquetas.
El negativo aprobado de índice NO_OBLIGATIONS conserva su alcance de dominio y no se transforma en una etiqueta de estructura vacía.
No existe referencia humana aprobada completa de fidelidad textual/estructura para este conjunto: precisión crítica, recall numérico/unidades y exactitud estructural permanecen no medidos/null donde falta referencia suficiente. No hay aprobación implícita.

## Matriz T01–T15

| Caso | Documento / página | Cobertura / alcance |
|---|---|---|
| T01 | 06 Mecanismos de ingeniería GNR-ABS.pdf / 2 (`9601b788-4824-43b8-b97e-44f1a3682eaa`) | Good Native availability; fidelity diagnostic; No human-approved page fidelity label |
| T02 | 04. PAPFS.pdf / 1 (`05729651-df52-405b-864b-fc7ad6e591ad`) | Image-only OCR candidate; OCR-friendly is hypothesis; No human-approved page fidelity label |
| T03 | ANEXO B-4.pdf / 4 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Difficult scanned supply text; partial human-approved quantity/attribute excerpts |
| T04 | ANEXO B-4.pdf / 1 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Visible structure start candidate; No human-approved page fidelity label |
| T05 | ANEXO B-4.pdf / 2 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Continuation candidate; No human-approved page fidelity label |
| T06 | ANEXO B-4.pdf / 4 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Model critical identifier; approved attribute fragment; partial human-approved quantity/attribute excerpts |
| T07 | ANEXO B-4.pdf / 4 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Quantity binding; approved quantity fragment; partial human-approved quantity/attribute excerpts |
| T08 | 2.1. ANEXOS - CAD-265-2026.pdf / 59 (`ca4ada03-8740-4f29-a99e-d5e874669555`) | Native structure reliable vs transcription uncertified; No human-approved page fidelity label |
| T09 | ANEXO B-4.pdf / 4 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | OCR/Vision disagreement diagnostic; partial human-approved quantity/attribute excerpts |
| T10 | ANEXO B-4.pdf / 2 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Known B-4 difficult structure; No human-approved page fidelity label |
| T11 | ANEXO B-4.pdf / 3 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | B-4 page 2→3 ownership transition, unproven boundary; No human-approved page fidelity label |
| T12 | 2.1. ANEXOS - CAD-265-2026.pdf / 24 (`ca4ada03-8740-4f29-a99e-d5e874669555`) | Persisted Requirements input; No human-approved page fidelity label |
| T13 | 2.1. ANEXOS - CAD-265-2026.pdf / 19 (`ca4ada03-8740-4f29-a99e-d5e874669555`) | Persisted requested Evidence input; No human-approved page fidelity label |
| T14 | ANEXO B-4.pdf / 4 (`acf31750-1d8d-4a0c-910c-fc3743930c57`) | Persisted Scope input; partial human-approved quantity/attribute excerpts |
| T15 | 2.1. ANEXOS - CAD-265-2026.pdf / 2 (`ca4ada03-8740-4f29-a99e-d5e874669555`) | Approved domain negative: annex index, NO_OBLIGATIONS; no structure truth implied; domain NO_OBLIGATIONS only |

## Runner y métricas

`app/document_intelligence_calibration.py` contiene contratos Pydantic estrictos, inventario, evaluación y agregado deterministas.
`scripts/run_document_intelligence_calibration.py` expone --provider, --capability, --document-id, --pages, --database-url, --output-json, --inventory-json, --no-real-model y --ingest-json.
Default: adquisición desactivada. --execute-provider es obligatorio para adquirir; exige documento explícito, páginas positivas y máximo cuatro páginas. --no-real-model y --execute-provider son incompatibles.
La identidad Tender #001 se verifica antes de acceder a documentos. Un UUID ajeno se rechaza, sin buscar otro corpus.
Todas las sesiones del runner ejecutan SET TRANSACTION READ ONLY. No commits, migrations, materializers destructivos ni actualizaciones de decisiones humanas. Outputs sólo bajo backend/reports, nunca sobre Golden.
La adquisición externa usa los clientes existentes, schemas/normalización y límites de imágenes actuales; no modifica prompts ni routing productivo. Estructura usa routing/guard/advance_continuity productivos; contexto sólo se conserva tras frontera VALID y se elimina ante fallo. Observaciones externas quedan REVIEW_REQUIRED y no se persisten en dev.
La ingestión filtra provider/capability/document/page y valida la identidad por Pydantic. Conserva texto, estructura y provenance; no ejecuta proveedor ni eleva calidad. No es un importador de verdad canónica.

Cada observación incluye Tender, documento/página, provider/model/capability, artefacto, esperado con hash cuando hay etiqueta, observado, status, categorías, criticality, review surfaced, dominio potencial, latency y notas. Los resultados completos llevan provenance y lineage.
Se mantienen métricas por provider/capability; no se fusionan Tesseract/Paddle antes de medirlos. Entradas UNAVAILABLE sin proveedor observado se contabilizan como ausencia, no como salida de un OCR concreto.
Los identificadores conservan raw, ceros iniciales y bindings acotados de R.3; no se inventan identificadores ni etiquetas para prosa arbitraria.
Los tokens se comparan mediante multiset; referencias parciales no permiten declarar precisión sobre una página completa. Coincidencia de tokens no demuestra binding contractual.
Errores de dominio se registran separadamente mediante domain_errors. Vínculos existentes a Requirements/requested Evidence/Scope/Quantity/Attribute son impacto potencial, no conteos certificados de errores de dominio.
`UNSAFE TRUSTED CONTRACTUAL ERRORS` exige domain_input_trusted=True medido; una selección DI RESOLVED errónea se cuenta separadamente como UNSAFE_AUTO_SELECTION. Sin replay, domain_trust_unassessed queda visible y cero errores observados no certifica seguridad.
SAFE MISSES y CORRECT_REVIEW_ESCALATION se separan del trust inseguro; conflictos no etiquetados son diagnósticos, sin inferir cuál proveedor está equivocado.
DESELECTED conserva historia y no suma resultados confiables activos. Serialization/orden estable e idempotencia de análisis verificados.

Taxonomía: TRANSCRIPTION_OMISSION, TRANSCRIPTION_SUBSTITUTION, NUMERIC_ERROR, UNIT_ERROR, IDENTIFIER_ERROR, STRUCTURE_BOUNDARY_ERROR, CONTINUITY_ERROR, QUANTITY_BINDING_ERROR, ATTRIBUTE_BINDING_ERROR, PROVIDER_CONFLICT, UNSAFE_AUTO_SELECTION, UNNECESSARY_REVIEW, CORRECT_REVIEW_ESCALATION, UNAVAILABLE_EXPECTED, OTHER.
No se usa FAIL genérico como sustituto de las categorías. No se fija un umbral arbitrario de readiness.

## Baselines

| Superficie | RESOLVED | REVIEW_REQUIRED | UNAVAILABLE |
|---|---:|---:|---:|
| Native transcripción | 0 | 279 | 136 |
| Native estructura | 1 | 278 | 136 |
| OCR transcripción (observaciones) | 0 | 274 | 278 páginas sin salida |
| OCR estructura (observaciones) | 9 | 265 | 278 páginas sin salida |

Los denominadores OCR mezclan observaciones por proveedor y ausencias por página: NO son tasas de accuracy. Cada proveedor aporta 137 transcripciones reales existentes.
Native B-4 página 4 no tiene texto: 14 excerpts aprobados distintos ausentes. Los dos OCR tienen 10 omisiones exactas de esos excerpts en total; esto no demuestra diez omisiones materiales visuales, pues puntuación/espacios pueden explicar una diferencia literal. Se requiere inspección humana antes de certificar materialidad o sustitución.
El reporte conserva estas diferencias como candidatas TRANSCRIPTION_OMISSION, sin tolerancias semánticas inventadas ni cambios al Golden. La precisión crítica y calidad real de OCR/Vision no quedan certificadas.
Stale-carry violations observados = 0; unsafe trusted contractual errors observados = 0; domain trust assessed = 0. Readiness certified = false.
No se ejecutó OCR nuevo; el baseline OCR procede de artefactos reales existentes. La adquisición siguiente usa Tesseract local instalado con spa+eng. Paddle conserva sus resultados independientes; no se inicia su runtime ni se descargan modelos.
No se ejecutó Vision/Ollama/Qwen. Se analizaron sólo artefactos previos y contratos deterministas. Render local B-4 1–4 verificado sin inferencia: 1190×1684 px, 577,218–795,853 bytes por imagen, dentro de límites existentes; SHA-256 del PDF original coincide con DB.

## Auditoría de modelos local

Config y cliente aceptan `qwen3-vl:4b-instruct`, primer experimento. Manifiestos locales existentes:
- qwen3-vl:4b-instruct: 3,295,635,680 bytes de capas (~3.07 GiB); 25 resultados históricos.
- qwen3-vl:4b: 3,295,635,584 bytes de capas (~3.07 GiB); 5 resultados históricos.
Ambos tags existen en manifests; disponibilidad efectiva en Ollama se comprobará en Terminal por el cliente. No se inicia el servicio para la auditoría ni se descarga un modelo.
Pesos en disco no equivalen a RAM: memoria adicional de runtime/KV/contexto/imagen y viabilidad todavía no medidas. Los dos modelos requieren al menos cargar pesos más overhead; no se promete una cifra de RAM.
qwen3:8b y qwen3:14b están en manifests locales, pero no son el proveedor Vision elegido. Política Source Effect Qwen NO-GO intacta; no se usa el modelo grande.

## Validación

29 pruebas de harness: CAL01–CAL20 más nueve casos adicionales (etiquetas parciales, DESELECTED, captures Native/OCR del contrato productivo, separación de fidelidad por capacidad, trust no evaluado, errores de dominio y continuidad del cliente).
La prueba del cliente externo es mock de control de flujo, no evidencia de calidad visual.

| Familia | Pass | Fail |
|---|---:|---:|
| Harness CAL | 29 | 0 |
| R.1 DI + compatibilidad | 35 | 0 |
| R.2 integración | 43 | 0 |
| R.3 propagación crítica | 47 | 0 |
| Orquestación estructural productiva | 29 | 0 |
| R.2a provenance | 23 | 0 |
| R.3a cross-capability provenance | 33 | 0 |
| Requested Evidence / requirement semantics | 33 | 0 |
| Quantity integration | 11 | 0 |
| Attribute integration | 11 | 0 |
| **Total** | **294** | **0** |

Comando final desde backend:
```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence_calibration.py tests/test_document_intelligence.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_integration.py tests/test_critical_identifier_propagation.py tests/test_document_structure_orchestrator.py tests/test_requirement_perception_provenance.py tests/test_cross_capability_provenance.py tests/test_requirement_semantics.py tests/test_scope_quantity_integration.py tests/test_scope_attribute_integration.py -q
```
294 passed, 6 warnings, 12.69s. Warnings existentes SWIG/PyMuPDF y python_multipart; no warnings nuevos de schemas.
Alembic test current/head: `20261013_req_perception_prov_072`. Dev current: `20261012_alt_compliance_071`. No migración nueva; no upgrade en dev.
Compileall app/scripts/tests PASS con Python absoluto obligatorio.
Análisis repetido de cada baseline produce exactamente la misma serialización.
Git diff --check PASS; whitespace de los cuatro archivos nuevos y este reporte PASS. Sólo docs/roadmap.md aparece modificado entre los tracked; cuatro archivos nuevos de implementación/manifiesto y ocho diagnósticos nuevos permanecen untracked. Los 18 untracked históricos iniciales se conservan. No stage/commit/push.

## Archivos

Creado: backend/app/document_intelligence_calibration.py; backend/scripts/run_document_intelligence_calibration.py; backend/tests/test_document_intelligence_calibration.py; backend/evals/document_intelligence_calibration_v1.json.
Modificado: docs/roadmap.md (R.3 CLOSED, R.4a CURRENT, R.4b NEXT, secuencia 06.V).
Diagnósticos untracked: este reporte y reports/di_r4a_inventory.json, di_r4a_native_transcription.json, di_r4a_native_structure.json, di_r4a_ocr_transcription.json, di_r4a_ocr_structure.json, di_r4a_available_structure.json, di_r4a_existing_vision_transcription.json.
18 archivos históricos untracked iniciales conservados. No producción existente, frontend, pricing, schema, migrations ni Golden labels modificados.

## Limitaciones / blockers de cierre R.4a

Resultados reales nuevos pendientes de ejecución externa y revisión. Etiquetas humanas de página/estructura/identidad completas no disponibles: T01–T15 son selección diagnóstica, con referencias parciales donde corresponden.
Replay real de dominio no ejecutado: dev aún está en 071; esta fase no autoriza modificar su esquema ni sus decisiones. Las regresiones ejercitan APIs productivas en licitia_test con fixtures aislados; no son replay de percepción real de Tender #001.
No se emite GO de convergencia ni se abre Tender #002. Los conteos cero tienen cobertura limitada y no certifican readiness.
Tender #001 auditado en read-only; Golden intacto. Tender #002 no inspeccionado ni seleccionado. Modelos reales ejecutados = NO.

## Próximos comandos exactos — ejecutar en macOS Terminal normal

Cada comando consulta sólo Tender #001 y escribe un artefacto separado; la base permanece READ ONLY incluso durante adquisición. No modifica decisiones humanas. Primer lote: una transcripción B-4 página 4 y estructura páginas 1–3; máximo tres páginas por invocación, timeout 180 segundos por solicitud Vision. Sin tuning ni descargas.

```sh
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev LICITIA_OLLAMA_BASE_URL=http://127.0.0.1:11434 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_calibration.py --provider VISION --model qwen3-vl:4b-instruct --capability TRANSCRIPTION --document-id acf31750-1d8d-4a0c-910c-fc3743930c57 --pages 4 --timeout 180 --execute-provider --output-json /Users/ceciliavalencia/LiticIA/backend/reports/di_r4a_vision_b4_p4_transcription.json
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev LICITIA_OLLAMA_BASE_URL=http://127.0.0.1:11434 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_calibration.py --provider VISION --model qwen3-vl:4b-instruct --capability STRUCTURE --document-id acf31750-1d8d-4a0c-910c-fc3743930c57 --pages 1 2 3 --timeout 180 --execute-provider --output-json /Users/ceciliavalencia/LiticIA/backend/reports/di_r4a_vision_b4_p1_p3_structure.json
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_calibration.py --provider TESSERACT --capability TRANSCRIPTION --document-id acf31750-1d8d-4a0c-910c-fc3743930c57 --pages 4 --execute-provider --output-json /Users/ceciliavalencia/LiticIA/backend/reports/di_r4a_tesseract_b4_p4_transcription.json
```

Tesseract usa el provider local existente, perfil spa+eng. El provider legado no ofrece timeout duro; el flag timeout controla Vision, no Tesseract. No se ejecuta desde Codex en esta fase.
Reanálisis externo, sin ejecución de modelo:
```sh
cd /Users/ceciliavalencia/LiticIA/backend
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_document_intelligence_calibration.py --provider VISION --capability TRANSCRIPTION --document-id acf31750-1d8d-4a0c-910c-fc3743930c57 --pages 4 --no-real-model --ingest-json /Users/ceciliavalencia/LiticIA/backend/reports/di_r4a_vision_b4_p4_transcription.json --output-json /Users/ceciliavalencia/LiticIA/backend/reports/di_r4a_vision_b4_p4_analysis.json
```

MVP-06.R.4a PHASE 1 CALIBRATION HARNESS READY — AWAITING REAL-MODEL RUN
