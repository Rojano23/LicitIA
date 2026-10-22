# MVP-06.V.6b commit + MVP-06.V.6c — Perception Sufficiency Boundary

## A. Commit de V.6b

HEAD inicial de la tarea: `a24a5b18fe43ca15a949408b77e19aea1f2950a4`.
Commit aceptado creado: `02de3a3ac1c59b71a58284e43c0d3ba6af4584bb`.
Subject: `feat(document-intelligence): add multispan structured evidence`.

Se inspeccionó status/diff completo y los archivos nuevos, se verificó diff --check
y se hizo staging explícito sólo de estos 17 archivos:

- `backend/app/blind_selective_freeze.py`
- `backend/app/scope_attribute_adapters.py`
- `backend/app/scope_attribute_materializer.py`
- `backend/app/scope_attributes.py`
- `backend/app/scope_detail_adapters.py`
- `backend/app/scope_details.py`
- `backend/app/scope_logical_identity.py`
- `backend/app/scope_quantities.py`
- `backend/app/scope_quantity_adapters.py`
- `backend/app/scope_quantity_materializer.py`
- `backend/app/scope_review.py`
- `backend/app/structured_evidence.py`
- `backend/app/structured_evidence_grounding.py`
- `backend/app/structured_evidence_storage.py`
- `backend/tests/test_structured_grounding.py`
- `backend/tests/test_structured_interpretation.py`
- `docs/adr/0015-structured-evidence-multispan-grounding.md`

ADR 0015 está incluido en el commit, conservando el contrato revisado. El reporte
`backend/reports/structured_evidence_reconstruction_v6b.md` permanece untracked,
sin reescritura. No se incluyó ningún reporte/artefacto histórico ajeno. Tras el
commit no quedaron modificaciones tracked de V.6b; staging vacío. No hubo push.

## B. V.6c — implementación sin commit

HEAD inicial/actual de V.6c: `02de3a3ac1c59b71a58284e43c0d3ba6af4584bb`.
Estado: implementación y validación terminadas, pendiente de revisión arquitectónica.
No stage, commit ni push de V.6c. ADR 0016 nuevo queda sin commit para revisión.

### Acoplamiento previo confirmado por código

1. plan_ocr calculaba identity_valid con structural_candidate_from_native_text y
   exigía procurement_rows/explicit_fields para Scope/Attributes/Quantities.
   Sin fila/campo reconocido no se establecía suficiencia Native; con IMAGE podía
   aparecer OCR_NEEDED aunque existiera texto útil para intentar interpretación.
2. STRUCTURE exigía identidad válida; UNKNOWN estructural se mezclaba con falta
   de percepción. La excepción legacy DOMAIN_IDENTITY_REVIEW_NOT_OCR_GAP cubría
   sólo algunas filas ambiguas, no gramática no soportada en general.
3. plan_document_vision_tasks volvía a usar plan_ocr sobre OCR normalizado. Una
   limitación de la misma gramática impedía declarar suficiencia OCR. Además,
   conflictos de valores retiraban suficiencia y podían permitir escalamiento
   aunque el texto estuviera disponible.
4. construct_tasks heredaba el booleano para crear tareas por región y preguntas
   espaciales del perfil. El harness quitaba visual_relationships_required para
   una prueba textual antes de reevaluar Vision, debilitando el binding de la
   pregunta original. Ahora conserva la pregunta/región y el planner prueba
   equivalencia de relaciones explícitas cuando realmente están disponibles.
5. No existía una consulta directa a counts de Scope/children materializados.
   El feedback de cero candidatos era indirecto mediante éxito de la gramática.
   materialize_canonical sigue después de percepción, sin alterar ese orden.

### Contratos independientes y positivos

Nuevos valores runtime congelados:

- PerceptionAssessment: SUFFICIENT / INSUFFICIENT / VISUAL_REQUIRED / UNKNOWN /
  UNAVAILABLE, con reason y source_method.
- InterpretationAssessment: SUCCESS / UNRESOLVED / AMBIGUOUS / REJECTED /
  NOT_ATTEMPTED, con reason. Sin texto/capacidad no se inventa un intento;
  límites conocidos de reconstrucción producen REJECTED, no una brecha OCR.

La suficiencia habilita intentar interpretación, no certifica fidelidad,
completitud contractual, Scope confiable ni cumplimiento. Se apoya en fuentes
canónicas/activas, identidad y hashes, ámbito requerido y alguno de estos soportes:
excerpts explícitos exactos; texto con integridad/diversidad léxica y composición
alfabética usable; o fragmentos/relaciones StructuredEvidenceBlock verificados.
La longitud sola no basta: repetir dos palabras cientos de veces no establece
suficiencia. El gate léxico exige al menos cuatro tokens distintos, composición
alfabética >=45% del contenido visible y ausencia de replacement/control corruption;
no es un score de confianza ni una garantía de lectura real. TEXT con texto y sin
contrato de excerpts conserva UNKNOWN. Una región explícita no toma prestado texto
Native global para demostrar cobertura de esa imagen.

SUCCESS describe la interpretación/estructura propuesta por los intérpretes
existentes; no autoridad contractual. Cantidades requieren par numérico/unidad
reconocida para ese diagnóstico; campos parciales quedan UNRESOLVED sin OCR nuevo.
Scope/ownership, Source Effects y revisión humana conservan sus reglas.

La integración IR usa source_text + reconstruct en modo de lectura, con identidades
reales; no crea manifests, geometría, Scope ni children durante planning. Un owner
ambiguo conserva percepción SUFFICIENT y diagnóstico AMBIGUOUS/review. Las gramáticas
V.6b/legacy permanecen sin cambios. Los límites de interpretación no borran evidencia.

### OCR y Vision

OCR sólo se vuelve elegible por una brecha textual independiente de la interpretación
y una fuente IMAGE elegible. Native suficiente, aun con interpretación pendiente o
rechazada, evita OCR; generaciones Native contradictorias o sin normalización quedan
UNKNOWN/review, sin adquisición como reparación. El ejecutor conserva sus recibos,
reuso y agotamiento. No se cambia el fingerprint de adquisición física OCR.

Vision requiere pregunta espacial explícita, motivo soportado y región IMAGE válida.
La lectura OCR suficiente puede satisfacer tareas textuales aunque la gramática
produzca cero candidatos. Un conflicto de valores conserva AMBIGUOUS, sin inventar
por sí mismo necesidad visual. Fallo OCR no es prueba espacial.

El harness mantiene la pregunta original. Texto legible de otra región no la
satisface. Sólo relaciones de header/tabla o fila rotulada con cantidad/unidad
probadas por IR dentro de la misma región pueden responder textualmente una pregunta
de layout de ítem soportada. Prosa OCR legible sin esas relaciones deja Vision
legítimamente elegible. GRAPHICAL_STRUCTURE no se descarga mediante esas reglas de
fila. Requests con bindings de región contradictorios fallan explícitamente.

La ruta legacy OCR sigue siendo legible sin metadata de engine que nunca se registró,
pero metadata contradictoria de página, región o engine falla cerrada; no se usa
como cobertura ni se autorrepara mediante proveedor. Hash/capacidad/estado fallido
siguen sus validaciones existentes. No hay fallback a fuente ajena.

### Observabilidad/versionado

Planes OCR/Vision contienen ambos assessments. perception_metrics/vision_metrics
agregan distribuciones de estados y motivos; conservan contadores de avoided,
needed, executed, reused, failed/exhausted y budgets. Eventos existentes de decisión
PLANNER/GUARD incluyen ambos diagnósticos, sin fragmentos/documentos nuevos en logs.
Mismo ciclo de retención de artefactos de run; no stream o tabla nuevos.

Política `perception-sufficiency-v2` en firmas de plan y de evidencia Vision, y en
implementation_versions del freeze. Planes anteriores no pasan freshness checks.
El task-contract policy `blind-task-contracts-v1`, perfiles, modelos, prompts,
configuración, retries y presupuesto físico OCR/Vision permanecen iguales. No se
creó un freeze/run_id/binding ni se ejecutó un pipeline ciego.

### Matrices y regresiones

SI21, SI22, SI23: PASS, activos en test_perception_sufficiency. El marcador temporal
del módulo de tests V.6b se actualizó para señalar estos casos activos. Los documentos
históricos aceptados no se reescribieron. Sin skips de V.6c.

| PS | Invariante verificado |
|---|---|
| 01 | Native suficiente + interpretación positiva evita OCR/Vision |
| 02 | Native suficiente + UNRESOLVED evita OCR |
| 03 | Ausencia real de texto conserva elegibilidad OCR |
| 04 | OCR suficiente + interpretación pendiente evita Vision textual |
| 05 | OCR textual insuficiente no inventa demanda visual |
| 06 | Contrato espacial explícito conserva Vision |
| 07 | Sin contrato espacial no hay Vision |
| 08 | Tareas/regiones conservan decisiones independientes |
| 09 | IR con ownership ambiguo: suficiencia + revisión, sin OCR |
| 10 | Falta de percepción e interpretación pendiente se observan separadas |
| 11 | AVAILABLE_ONLY no adquiere |
| 12 | HISTORICAL_SAFE no adquiere |
| 13 | Selective sigue ejecutando necesidad OCR legítima con cliente doble |
| 14 | Selective sigue ejecutando Vision legítimo con cliente doble |
| 15 | Budgets cero/caps conservados, sin llamadas |
| 16 | Planning determinista/idempotente |
| 17 | Repetición/longitud no demuestran suficiencia |
| 18 | Excerpt requerido ausente produce brecha textual |
| 19 | Generación con hash corrupto falla cerrada |
| 20 | OCR fallido no acredita suficiencia |
| 21 | OCR de otra región no cubre el target |
| 22 | Tabla IR aporta prueba perceptual sin autoridad contractual |
| 23 | Freeze registra la versión real de suficiencia |
| 24 | Prosa OCR legible no sustituye una relación espacial faltante |
| 25 | Relaciones OCR probadas de la misma región evitan Vision |
| 26 | Bindings de región incompatibles se rechazan |
| 27 | Capacidad unavailable no inventa interpretación |
| 28 | Límite del intérprete se observa REJECTED sin crear brecha perceptual |
| 29 | Tres casos: OCR con página/región/engine mal vinculados falla cerrado |
| 30 | Cuatro casos: par cantidad/unidad válido o parcial conserva percepción y distingue interpretación |

36 pruebas nuevas PASS (SI21–SI23 + PS01–PS30, con parametrizaciones).
Pruebas con dobles verifican contratos, no fidelidad semántica/visual de motores reales.

| Grupo final | Resultado |
|---|---|
| Nuevas SI/PS | 36 PASS |
| V.6b SI/MG | 54 PASS |
| V.4a structural trust safety | 24 PASS |
| V.4b SC/DC Native | 46 PASS |
| OCR / Vision selectivos | 44 / 46 PASS |
| BR / FB / BH | 16 / 23 / 37 PASS |
| Scope adapters/materializers/details/attributes/quantities | 159 PASS |
| Scope Human Review + API | 87 PASS |
| Ampliada DI/MVP-06.V | 1099 PASS, 1 deselected, 8 warnings |
| Suite completa | 2055 PASS, 1 deselected, 8 warnings |
| compileall app/scripts/tests | PASS |
| git diff --check | PASS |

Warnings existentes: SWIG, python_multipart, Alembic path_separator y Paddle ccache.
Única exclusión explícita: test real local_ollama. Los fallos de integración durante
el desarrollo se corrigieron; las cifras de cierre son de la versión final.

### Comandos reproducibles

Cwd backend, intérprete obligatorio, tests exclusivamente licitia_test:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_perception_sufficiency.py -q --junitxml=/private/tmp/v6c_ps.xml
```

Ampliada (salida /private/tmp/v6c_expanded.log):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest \
  tests/test_perception_sufficiency.py \
  tests/test_structured_interpretation.py \
  tests/test_structured_grounding.py \
  tests/test_blind_data_root_bootstrap.py \
  tests/test_blind_freeze_evidence.py \
  tests/test_blind_selective_harness.py \
  tests/test_selective_vision_recovery.py \
  tests/test_selective_ocr_recovery.py \
  tests/test_native_structured_coverage.py \
  tests/test_structural_trust_safety.py \
  tests/test_structural_trust_propagation.py \
  tests/test_scope_details.py \
  tests/test_scope_detail_adapters.py \
  tests/test_scope_detail_materializer.py \
  tests/test_scope_attributes.py \
  tests/test_scope_attribute_adapters.py \
  tests/test_scope_attribute_materializer.py \
  tests/test_scope_attribute_integration.py \
  tests/test_scope_quantities.py \
  tests/test_scope_quantity_adapters.py \
  tests/test_scope_quantity_materializer.py \
  tests/test_scope_quantity_integration.py \
  tests/test_document_intelligence.py \
  tests/test_document_intelligence_integration.py \
  tests/test_document_intelligence_compatibility.py \
  tests/test_document_intelligence_audit.py \
  tests/test_document_intelligence_calibration.py \
  tests/test_document_intelligence_calibration_fidelity.py \
  tests/test_document_intelligence_structural_golden.py \
  tests/test_document_intelligence_structural_rescore.py \
  tests/test_document_intelligence_06v_preflight.py \
  tests/test_document_preparation_recovery.py \
  tests/test_page_structure.py \
  tests/test_page_structure_resolver.py \
  tests/test_document_structure_orchestrator.py \
  tests/test_scope_review.py \
  tests/test_scope_review_api.py \
  tests/test_alternative_compliance.py \
  tests/test_alternative_compliance_api.py \
  tests/test_documents.py \
  -q -m 'not local_ollama' --junitxml=/private/tmp/v6c_expanded.xml
```

Completa (salida /private/tmp/v6c_full.log):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama' --junitxml=/private/tmp/v6c_full.xml
```

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
git diff --check
git diff --stat
git status --short
```

Alembic mediante observe_schema_drift / verify_accepted_drift, conexión independiente
READ ONLY a licitia_test: current/head `20261013_req_perception_prov_072`.
Drift 59: 55 add_index / 4 remove_index; firma sin cambio
`3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`.
Cero drifts nuevos. No modelos, schema o migraciones modificados.

### Integridad, archivos y Git

Sólo verificación de hashes: 107/107 históricos, 24/24 del baseline Attempt #3,
1369/1369 operativos de Attempt #4, 16/16 de adjudicación y 139/139 de storage
Attempt #4. Sin mismatches; Attempts #1–#4 y adjudicaciones permanecen intactos.
El reporte arquitectónico V.6a conserva su SHA aceptado. No se inspeccionó Tender
#002 semánticamente ni se usó como tuning/fixture/Golden.

Archivos tracked modificados únicamente por V.6c:

- `backend/app/blind_selective_freeze.py`
- `backend/app/blind_selective_harness.py`
- `backend/app/document_perception_planner.py`
- `backend/app/selective_vision_executor.py`
- `backend/tests/test_structured_interpretation.py`

Archivos nuevos de V.6c:

- `backend/app/perception_sufficiency.py`
- `backend/tests/test_perception_sufficiency.py`
- `docs/adr/0016-perception-interpretation-sufficiency.md`
- `backend/reports/perception_sufficiency_boundary_v6c.md`

Staging vacío. El reporte V.6b y los históricos untracked no se agregaron.
No stage/commit de V.6c ni push. HEAD permanece en el commit aceptado de V.6b.

### Límites y confirmaciones

La suficiencia positiva permite intentar interpretación; no certifica que una
fuente textual cubra toda obligación visual oculta o calidad real de OCR. El gate
léxico es acotado y puede conservar gaps; las preguntas/regiones explícitas siguen
siendo necesarias. No se amplió gramática ni se agregó una recuperación visual
universal. Las decisiones de dominio y humano siguen pendientes cuando corresponda.

No quedan blockers de tests/schema para este slice. Requiere aceptación del
arquitecto antes de commit y autorización separada para un run futuro.

V.6b committed cleanly: YES. Interpretación fallida por sí sola provoca OCR: NO.
Interpretación fallida por sí sola provoca Vision: NO. Déficits genuinos conservan
escalamiento: YES (con prueba de región/capacidad/política). Budgets/providers
cambiados: NO. Proveedores reales invocados: ZERO. Attempt #5 creado: NO.
