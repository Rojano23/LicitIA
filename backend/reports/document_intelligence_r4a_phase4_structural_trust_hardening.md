# MVP-06.R.4a Phase 4 — Structural Trust Propagation Hardening

Estado: COMPLETE — READY FOR ARCHITECT REVIEW. Starting HEAD: `3f2e29b feat(mvp-06.R.4a): add approved B-4 structural golden and rescore`.

La corrección genérica lleva UNSAFE_TRUSTED_STRUCTURAL_ERRORS de **2 a 0** al reingerir offline el mismo resultado Vision existente. P1 permanece CORRECT; P2 y P3 son REVIEW_REQUIRED_CORRECT. No mejora ni modifica la percepción original. R.4a overall permanece CURRENT; R.4b NEXT; 06.V PROTECTED; readiness no certificado.

## Auditoría del defecto

La auditoría previa a la edición localizó el defecto en `advance_continuity`: sólo comprobaba el límite si el estado actual declaraba incoming_item_key. El resolver local y routing por capacidad podían resolver una sola observación VALID sin detectar inconsistencia entre páginas. El orquestador ya llamaba continuidad y convertía UNKNOWN a revisión, pero la función retornaba VALID en los dos casos. Las comparaciones R.3 de identificadores no suplían esta regla: no existía desacuerdo entre fuentes independientes que por sí solo explicara el límite.

**Caso 1, P2.** El resultado almacenado afirma un inicio de la identidad 2 y omite la entrada/continuación de 1. `adapt_structure_scope_005_page` produce incoming=None; la normalización productiva reconstruye outgoing=2. Producción sabía que P1 tenía outgoing=1. La inconsistencia observable sin Golden era descartar ese grupo abierto al iniciar otro sin dar cuenta del propietario previo. El guard antiguo no entraba en su rama de incoming, por lo que routing local RESOLVED → continuidad VALID → PageStructureResolution RESOLVED → ScopeSegment de 2 con review_required=false. El Golden sólo permitió adjudicar la exactitud y cuantificar el defecto.

**Caso 2, P3.** El resultado almacenado afirma un nuevo inicio 3 con anchor de actividad de servicio sin el identificador 3. En el flujo anterior, P2 dejaba outgoing=2 considerado válido; P3 lo reemplazaba sin entrada/transición sustentada. El mismo guard omitido producía continuidad VALID y ScopeSegment 3 sin revisión. Tras corregir P2, su límite es UNKNOWN, por lo que P3 tampoco puede recuperar confianza mediante una mera afirmación de inicio sin identificador en el anchor. Su diagnóstico pasa a INSUFFICIENT_STRUCTURAL_BOUNDARY_EVIDENCE, sin fabricar una contradicción contra un propietario previo ya no confiable.

Cadena revisada: resultado Vision inmutable → adapter estructural → routing/resolver local → PageStructuralState → continuidad neutral → resolución persistida del orquestador → proyección Scope. La continuidad neutral es dueña del invariante entre páginas; el orquestador persiste el motivo y retira segmentos no confiables; el adapter Scope es dueño de propagar la falta de confianza al ownership dependiente.

## Invariante genérico y límites

Para páginas adyacentes de la misma licitación/documento/versión, una salida abierta válida exige que la primera identidad estructural actual dé cuenta del mismo propietario y no esté en revisión. Incoming incompatible o inicio de otra identidad sin transición sustentada producen STRUCTURAL_BOUNDARY_CONFLICT y UNKNOWN, sin outgoing ni structural_state confiables. La observación original queda disponible como evidencia auditada, sin convertirse en estado abierto.

Repetir un encabezado de la misma identidad es válido; no reemplaza el owner. Continuar A y después iniciar B en la misma página es una transición válida según los segmentos ordenados aceptados. Si el estado previo termina sin outgoing, iniciar B no dispara revisión por cambio de identidad. Ausencia de outgoing sólo prueba ese cierre cuando el contrato/evidencia lo respalda; no se infiere cierre de datos faltantes ni se agregan nuevas facultades de extracción.

Sin estructura utilizable: CURRENT_STRUCTURE_UNTRUSTWORTHY/UNKNOWN. Después de UNKNOWN: un inicio independiente requiere todos sus segmentos como nuevos inicios y el raw_label presente como token en su anchor exacto. Sin ese grounding: INSUFFICIENT_STRUCTURAL_BOUNDARY_EVIDENCE. No se descubre identidad a partir de pies de página, metadata o texto arbitrario. Incoming heredado tras UNKNOWN continúa fallando cerrado.

La revisión afecta el límite/página actual y sus owners dependientes. Las páginas previas conservan confianza; una página posterior con inicio independiente grounded puede recuperarse. No se invalida el tender/documento completo ni se transporta A o se reemplaza silenciosamente por B. No se agrega resolución automática ni UI.

## Scope, cantidades y atributos

ScopeDetail dependiente de estructura no resuelta conserva su evidencia pero pasa a review_required=true y applicability=UNRESOLVED; scope_segment_id/tender_item_id/candidate_item_key confiables se retiran. El guard no depende de que exista una transcripción. Los detalles independientes sin ownership de grupo conservan sus condiciones de confianza.

Los materializadores existentes de cantidades y atributos heredan la revisión del detalle. ST11 y ST12 crean registros derivados reales sobre fixtures sintéticos compatibles y comprueban review_required; no basta con mocks ni ausencia de registros. ST13 conserva un detalle independiente confiable. No se rediseña extracción, unidades, atributos ni decisiones humanas.

Native/OCR/Vision ejecutan la misma regla; ST14–ST17 prueban transiciones válidas e inválidas para los tres canales. No hay ramas basadas en provider, nombres B-4, páginas 2/3 ni ITEM_1/ITEM_2 en el guard productivo. ST20 bloquea lectura de rutas Golden/evals durante decisiones productivas y comprueba los módulos modificados. El runtime nunca carga el Golden; sólo el evaluador posterior lo usa.

## Superficie

Producción modificada:

- `backend/app/document_intelligence.py`: guard neutral de continuidad y recuperación grounded.
- `backend/app/document_structure_orchestrator.py`: persistencia del diagnóstico específico.
- `backend/app/scope_detail_adapters.py`: fail-closed del ownership dependiente.

Evaluación/pruebas/documentación:

- `backend/app/document_intelligence_structural_rescore.py`: contador explícito de safe misses estructurales, sólo evaluación.
- `backend/app/document_intelligence_calibration_replay.py`: reporte del routing efectivo cuando continuidad falla; sin modificar observaciones originales.
- `backend/scripts/run_b4_structural_rescore.py`: `--phase4` escribe exclusivamente un reporte separado.
- `backend/tests/test_structural_trust_propagation.py`: ST01–ST20.
- `backend/tests/test_document_intelligence_structural_rescore.py`: GS15 exige ahora cero errores confiados y dos escalaciones.
- `backend/tests/test_document_structure_orchestrator.py`: expectativas antiguas que descartaban un owner abierto pasan a exigir revisión; diagnósticos específicos.
- `docs/adr/0010-document-intelligence-capability-routing.md`: aclaración arquitectónica propuesta.
- `docs/roadmap.md`: Phase 3 CLOSED; Phase 4 CURRENT/ready for review.
- `backend/reports/di_r4a_b4_structure_phase4_rescore.json` y este reporte.

Schema changed: NO. Migration required: NO. Frontend y Source Effects sin cambios. Sin cambios a prompt, modelo, presupuesto, temperatura, proveedor, raw result o Golden.

## ST01–ST20

| Caso | Invariante | Resultado |
|---|---|---|
| ST01 | A→A válido | PASS |
| ST02 | Continuación A/cierre estructural/inicio B; previo cerrado→B | PASS |
| ST03 | Inicio B sin dar cuenta de A | PASS |
| ST04 | Incoming incompatible | PASS |
| ST05 | Evidencia ausente sin fabricar conflicto | PASS |
| ST06 | Sin stale carry A | PASS |
| ST07 | Sin reemplazo silencioso por B | PASS |
| ST08 | Recuperación con inicio independiente grounded | PASS |
| ST09 | Localidad por límite/página | PASS |
| ST10 | Scope ownership en revisión | PASS |
| ST11 | Cantidad hereda revisión | PASS |
| ST12 | Atributo hereda revisión | PASS |
| ST13 | Detalle independiente conserva confianza | PASS |
| ST14 | Native neutral | PASS |
| ST15 | OCR neutral | PASS |
| ST16 | Vision neutral | PASS |
| ST17 | Canal por sí solo no provoca revisión | PASS |
| ST18 | Idempotencia | PASS |
| ST19 | Sin diagnósticos duplicados | PASS |
| ST20 | Producción sin dependencia Golden | PASS |

## Validación reproducible

Desde backend, siempre con `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python` y DATABASE_URL de licitia_test:

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_structural_trust_propagation.py -q
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_critical_identifier_propagation.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_structure_orchestrator.py tests/test_page_structure_resolver.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_linking.py tests/test_scope_quantity_materializer.py tests/test_scope_attribute_materializer.py -q --tb=short
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_structural_trust_propagation.py tests/test_page_structure.py tests/test_scope_details.py tests/test_scope_quantities.py tests/test_scope_attributes.py tests/test_scope_quantity_integration.py tests/test_scope_attribute_integration.py -q --tb=short
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_structural_trust_propagation.py tests/test_document_intelligence_structural_rescore.py -q --tb=short
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_b4_structural_rescore.py --phase4
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
```

Focused: 20 passed, 0 failed (1.62 s antes del ajuste final de fixture; también pasan en el comando suplementario final). Regresión requerida: 331 passed, 0 failed en 13.23 s. Suplementaria: 108 passed, 0 failed en 3.68 s, incluidos ST20 y 88 regresiones adicionales. Total único: 20 focused + 419 regresiones = 439 pruebas. Después de añadir el contador safe_misses al evaluador, revalidación final ST+GS: 45 passed, 0 failed en 3.82 s, con los mismos seis warnings; sin nuevos cambios productivos. Seis warnings existentes SWIG/PyMuPDF/python_multipart por ejecución; fitz advierte deprecación en el runner. CompanyEvidence y Source Effects no comparten dependencias modificadas, por lo que no se ejecutaron suites ajenas.

Durante la iteración: un intento sin acceso local a PostgreSQL produjo 31 errores de setup (ningún caso ejecutado); otro comando desde cwd raíz no encontró el archivo de tests. ST11/ST12 fallaron inicialmente por fixture sin artefacto compatible y se corrigió el fixture. La primera regresión encontró cuatro expectativas: una repetición válida de la misma identidad motivó preservar ese comportamiento; tres expectativas aceptaban descarte de owner abierto o diagnóstico genérico. Se ajustaron sólo esas expectativas de seguridad, sin debilitar el invariante. Un segundo pase señaló otra aserción del mismo diagnóstico que también se actualizó. Las ejecuciones finales arriba pasan.

Alembic current/head: `20261013_req_perception_prov_072`. Compileall exit 0. Sin migración aplicada nueva.

## Replay B-4 final

| Página | Resultado | Confianza efectiva |
|---|---|---|
| P1 | CORRECT | RESOLVED; único ScopeSegment conservado, sin revisión |
| P2 | REVIEW_REQUIRED_CORRECT | UNKNOWN; sin ScopeSegment confiable |
| P3 | REVIEW_REQUIRED_CORRECT | UNKNOWN; sin ScopeSegment confiable |
| P3→P4 | UNASSESSABLE | No existe observación Vision P4 |

UNSAFE_TRUSTED_STRUCTURAL_ERRORS BEFORE=2; AFTER=0. Correct review escalations=2. Safe misses=2: las dos percepciones estructurales incorrectas se retienen en revisión, siguiendo la distinción del harness entre error material confiado y error material fail-closed. Coinciden con las dos escalaciones correctas; no son casos adicionales. P4 no observada se informa como UNASSESSABLE y se excluye, no se computa como acierto o miss. No existe métrica de recall estructural certificada por esta fase.

Los errores de percepción siguen intactos: 1 falso inicio, 2 continuaciones perdidas, 1 cierre perdido, 2 errores de identidad. Fronteras P1→P2 y P2→P3 siguen INCORRECT en exactitud del artefacto, ahora protegidas por revisión; P3→P4 permanece UNASSESSABLE con salida izquierda incorrecta en el chequeo parcial contra Golden P4.

Stale carry violations=0; provider calls=0; blocked provider attempts=0; real models executed=NO. Replay semánticamente idempotente; UUID incidental de segmento regenerado. Requirements=0; Requested Evidence=0; ScopeDetail=0; cantidades=0; atributos=0 en este lote structure-only. La prueba de propagación a derivados viene de ST10–ST13 y regresiones sintéticas, no de inventar detalle B-4. Fixtures del replay se eliminan al terminar; licitia_dev no se usa.

Latencias originales conservadas: P1 35.825 s, P2 35.638 s, P3 36.923 s. No nuevas mediciones de inferencia ni overhead. Reconstruir contexto offline no altera el contexto recibido por el modelo en su ejecución original.

## Integridad y Git

Golden file SHA-256: `60520abdb48862cf99763d40e355cc03f6e3771e4f73f1c438f7c00c069feb71`.

Golden content SHA-256: `885f9c623a07092d3a1880a1736517dd2917888b2435320e9fcaaedcfc082ef5`.

Vision original SHA-256: `e37b20c8badc558516e1335beebd5285532c09b08ed339f0711a0abb4abe5aed`.

PDF aprobado: `5b1ecdcf6ab0ec6a1008bf41554367dc3a917fce2a79b197a5289193362ba311`. Golden/hash de páginas y original validados por loader; los tres artefactos históricos del lote conservan sus hashes. Reportes Phase 3 preservados; resultado Phase 4 escrito en ruta nueva.

`git diff --check` y checks de whitespace para archivos nuevos sin errores; `git diff --stat` y `git status --short` inspeccionados. HEAD permanece `3f2e29b`; cambios rastreados más los nuevos archivos de test/reportes permanecen sin stage. Reportes históricos untracked preservados. No stage/commit/push. Tender #002 no buscado, inspeccionado ni utilizado.

Blockers: ninguno para revisar esta corrección. Pendientes: aceptación arquitectónica del invariante y aclaración ADR, calidad de percepción todavía imperfecta, readiness no certificado. Siguiente acción recomendada: revisión arquitectónica y humana de Phase 4; no avanzar automáticamente a R.4b ni ejecutar nuevos modelos.

MVP-06.R.4a PHASE 4 STRUCTURAL TRUST PROPAGATION HARDENING COMPLETE — READY FOR ARCHITECT REVIEW
