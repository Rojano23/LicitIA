# MVP-06.R.3 — revisión de arquitectura

Starting HEAD: `857bbdc feat(mvp-06.R.3a): add cross-capability critical identifier provenance`, `main`.

Estado: implementación y validación completas para revisión; R.3 permanece CURRENT.
R.3a CLOSED; R.4 NEXT. Sin stage, commit ni push.

## Auditoría de propagación y decisiones

| Superficie | Brecha previa | Comportamiento R.3 |
|---|---|---|
| Identificadores | R.3a comparaba observaciones suministradas, sin puente de bindings productivo | Frontera neutral para bindings declarados y sintaxis explícita, con raw/excerpt antes de confiar en identidad normalizada |
| Requirements | `candidate_perception` ignoraba comparaciones v2 | Revisión local por conflicto material; v2 persiste ambos contextos y observaciones |
| Discovery Requirements | Pruning de prosa podía suprimir una variante de referencia | Identificadores explícitos diferentes impiden ese pruning entre alternativas |
| Evidencia solicitada | Dependía de revisión de Requirements | Bridge existente recibe revisión y provenance v2; no afirma una alternativa como confiable |
| Scope | Se propagaba routing por página; ownership se resolvía sin comparación | Detalle afectado REVIEW_REQUIRED/UNRESOLVED, sin owner FK ni candidate_item_key confiables |
| Continuidad | Firmas estructurales comparaban claves legacy normalizadas | Comparación raw independiente impide cruzar un límite ambiguo; sin selección/fallback ni stale carry |
| Cantidades | Revisión heredada del detalle, sin defensa independiente del owner en el bridge | Owner conflictuado pierde binding confiable; la cantidad auditada hereda revisión; cantidades discrepantes requieren revisión local |
| Atributos | Revisión heredada del detalle | Atributo grounded permanece auditado/revisable, sin attachment contractual confiable a un owner disputado |

`RoutingResult` sigue siendo single-capability y no fue modificado. El contrato y
normalizador de R.3a permanecen intactos. El nuevo módulo no descubre obligaciones:
clasifica cautela a partir de etiquetas Item/Partida, TAG, Model/Modelo, códigos de
referencia documental y cantidades con unidad visible, además de bindings R.1.
No usa números aislados, prosa libre, nombres de modelo/proveedor ni metadata como
identidad contractual; no incorpora valores institucionales al Core.

El vocabulario de R.3a conserva ITEM_NUMBER, PARTIDA, EQUIPMENT_TAG,
MODEL_IDENTIFIER, DOCUMENT_REFERENCE, QUANTITY_BINDING_IDENTIFIER,
STRUCTURAL_GROUP_IDENTIFIER y OTHER_CRITICAL_IDENTIFIER. La normalización sigue
siendo NFC/trim/whitespace, sin eliminar ceros, sufijos, puntuación, case o acentos.

La preferencia de routing no resuelve un conflicto. ACTIVE confiables discrepantes
requieren revisión; DESELECTED se conserva sin generar conflicto activo por sí solo.
FAILED/UNAVAILABLE no aportan valores fabricados; percepciones no certificadas
siguen requiriendo revisión, sin inventar confianza ni umbrales.

La correspondencia no se infiere por orden de filas. El límite de propietario único
puede compararse cuando cada observación contiene un solo owner explícito. Para
múltiples propietarios se usa contexto literal común después de sustituir únicamente
spans reconocidos. Templates repetidos con valores diferentes quedan separados y
marcados como correspondencia no probada; soporte insuficiente entre percepciones
confiables requiere revisión sin fabricar un CONFLICT. Hay prueba específica de
`1`/`01` con múltiples partidas y firmas legacy idénticas.

## Localidad y provenance

La revisión se acota al fragmento o owner afectado. Un fragmento exacto acordado por
todas las transcripciones ACTIVE confiables puede continuar si el desacuerdo está
en otro fragmento. Esto también aplica a conflictos R.1 declarados. No se certifican
fuentes REVIEW_REQUIRED ni se ignora el conflicto del propio fragmento.

El normalizador legacy no cambia. Sólo se usa para localizar el owner persistido
que debe perder confianza cuando sus valores raw están en conflicto; nunca para
declarar AGREEMENT entre esos valores. Un ScopeDetail independiente TENDER_WIDE
continúa, incluyendo sus cantidades/atributos no afectados.

Requirements conserva el snapshot v2 con contextos y comparaciones separados.
El refresh preserva generaciones previas, datos completos de observaciones y
lineage explícita; generaciones ausentes de transcripción/estructura se retienen
DESELECTED. No hay downgrade. NULL/v1 siguen legibles; sin backfill.
La identidad/deduplicación lógica de evidencia no cambia.

Scope usa review/applicability/ownership y provenance existentes. Ambos artefactos
NormalizedContent/OCR/Vision permanecen disponibles con sus IDs y fragmentos; las
comparaciones Scope pueden regenerarse desde esas fuentes. No hay almacenamiento
paralelo ni columna nueva. Una prueba del materializador productivo comprueba ambos
page-result IDs Vision, valores `1`/`01` y cantidades `10`/`100` después de repetir
procesamiento y recargar DB; todas las cantidades afectadas siguen en revisión.

La continuidad conserva el estado anterior como histórico, deja el límite actual
UNKNOWN/REVIEW_REQUIRED y no transporta la clave abierta. Un inicio independiente
posterior se recupera. Un conflicto de cantidad sin conflicto de agrupación no
invalida por sí solo la continuidad.

Cantidades y atributos conservan la vinculación al detalle auditado, que no significa
binding a una identidad contractual confiable. No se modificaron sus extractores,
semánticas ni unidades soportadas. Repeated materialization conserva dos filas por
dominio en el caso de prueba, con revisión únicamente de la fila afectada.

No se implementa una nueva resolución humana de conflictos de percepción. Un flujo
explícito de resolución de identidad queda para trabajo posterior. Scope Review no
recibe facultades para resolver Source Effects; las decisiones humanas existentes
no se rediseñan.

## Matrices enfocadas

Todas PASS en `tests/test_critical_identifier_propagation.py`.

| Caso | Verificación |
|---|---|
| CI01 | Native/OCR idénticos: AGREEMENT |
| CI02 | OCR/Vision idénticos: AGREEMENT |
| CI03 | Acuerdo conserva ambas observaciones |
| CI04 | Native/OCR discrepantes: CONFLICT |
| CI05 | OCR/Vision discrepantes: CONFLICT |
| CI06 | Vision A/B independientes discrepantes: CONFLICT |
| CI07 | DESELECTED no genera conflicto activo |
| CI08 | UNAVAILABLE no fabrica valores |
| CI09 | Orden y metadata temporal no resuelven conflicto |
| CI10 | Normalización conservadora |
| CI11 | `1` y `01` distintos |
| CI12 | `TAG-101` y `TAG-10I` distintos |
| CI13 | Sufijo de modelo conservado |
| CI14 | Metadata no se convierte en verdad |
| CI15 | Orden determinista |
| CR01 | Conflicto crítico provoca revisión de Requirement |
| CR02 | Ambas observaciones persisten |
| CR03 | Requirement independiente continúa |
| CE01 | Interpretación de evidencia solicitada REVIEW_REQUIRED |
| CE02 | Ambas alternativas/provenance expuestas |
| CE03 | CompanyEvidence sin cambio de esquema |
| CS01 | Item conflictuado: revisión, sin owner confiable |
| CS02 | Partida conflictuada: revisión |
| CS03 | TAG conflictuado: revisión |
| CS04 | Modelo conflictuado: revisión |
| CS05 | Transcripción/estructura discrepantes: revisión |
| CS06 | ScopeDetail independiente continúa |
| CC01 | Conflicto detiene límite |
| CC02 | Sin stale carry; estado previo histórico |
| CC03 | Grupo independiente recupera continuidad |
| CQ01 | Cantidad del owner disputado: revisión |
| CQ02 | Valor de cantidad discrepante: revisión |
| CQ03 | Cantidad independiente válida |
| CA01 | Atributo del owner disputado: revisión |
| CA02 | Atributo independiente válido |
| XCI01 | Conflicto puede afectar ambos dominios independientemente |
| XCI02 | Revisión Requirement no muta Scope |
| XCI03 | Revisión Scope no muta Requirement |
| XCI04 | Localidad del conflicto |
| XCI05 | Repetición sin duplicar detalles/evidencia |
| XCI06 | Sin fallback oculto después del conflicto |

Otros seis casos: discovery productivo raw `1`/`01` y persistencia idempotente;
orquestador productivo y recuperación posterior; cantidades/atributos repetidos;
múltiples owners con correspondencia no probada; ambas alternativas Vision durables;
localidad con conflicto R.1 de identificador declarado.

## Validación reproducible

Ejecutado desde `/Users/ceciliavalencia/LiticIA/backend`, exclusivamente en `licitia_test`:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_critical_identifier_propagation.py -q
```

La matriz enfocada final contiene 47 casos; todos pasaron también en la corrida final:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_critical_identifier_propagation.py tests/test_document_intelligence.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_integration.py tests/test_requirement_perception_provenance.py tests/test_cross_capability_provenance.py tests/test_requirement_extraction.py tests/test_requirement_normalization.py tests/test_requirement_semantics.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_linking.py tests/test_scope_segments.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_integration.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_integration.py -q
```

Resultado: **464 PASS / 0 FAIL**, 20.57 s; seis warnings de dependencias SWIG/PyMuPDF
y `python_multipart`, más aviso SWIG al cerrar el intérprete. No errores de aplicación.
La primera regresión amplia tuvo una expectativa obsoleta del diagnóstico estructural;
se actualizó al diagnóstico más preciso CRITICAL_IDENTIFIER_CONFLICT y se repitió.
Los fixtures de cantidades se ajustaron a sintaxis terminal parentizada y unidades
existentes; no se cambió producción para permitir esos fixtures.

| Familia | Archivo(s) | PASS |
|---|---|---:|
| R.3 enfocadas | test_critical_identifier_propagation.py | 47 |
| R.1 | test_document_intelligence.py / test_document_intelligence_compatibility.py | 31 + 4 = 35 |
| R.2 | test_document_intelligence_integration.py | 43 |
| R.2a | test_requirement_perception_provenance.py | 23 |
| R.3a | test_cross_capability_provenance.py | 33 |
| Requirements | test_requirement_extraction.py / test_requirement_normalization.py | 31 + 29 = 60 |
| Evidencia solicitada | test_requirement_semantics.py | 33 |
| Scope adapters/materialization | test_scope_detail_adapters.py / test_scope_detail_materializer.py | 10 + 21 = 31 |
| Estructura/continuidad/linking | test_page_structure.py / test_page_structure_resolver.py / test_document_structure_orchestrator.py / test_scope_linking.py / test_scope_segments.py | 12 + 17 + 29 + 14 + 13 = 85 |
| Cantidades | test_scope_quantity_materializer.py / test_scope_quantity_adapters.py / test_scope_quantity_integration.py | 9 + 25 + 11 = 45 |
| Atributos | test_scope_attribute_materializer.py / test_scope_attribute_adapters.py / test_scope_attribute_integration.py | 11 + 7 + 11 = 29 |

Scope total: **116**. Conteos verificados con colección explícita, sin globs.

CompanyEvidence regression required: **NO**. Sus imports/implementación/modelos no
cambian; no depende de los bridges modificados. Source Effect regression required:
**NO**. Resolver/proyección y sus dependencias de producción permanecen intactos;
no cambia discovery, precedencia, resolución ni Goldens Source Effect.

Schema changed: **NO**. Migration required: **NO**.

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
```

Ambos: `20261013_req_perception_prov_072 (head)`.

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
git diff --check
git diff --stat
git status --short
```

Compileall y diff check: PASS. Los archivos nuevos se verificaron adicionalmente
con `git diff --no-index --check /dev/null <archivo>`.

## Archivos y límites

Creados:

- backend/app/document_identifier_bindings.py
- backend/tests/test_critical_identifier_propagation.py
- backend/reports/document_intelligence_r3_review.md

Modificados:

- backend/app/document_structure_orchestrator.py
- backend/app/requirement_di_adapter.py
- backend/app/requirement_extraction.py
- backend/app/scope_detail_adapters.py
- backend/app/scope_detail_materializer.py
- backend/app/scope_di_adapter.py
- backend/tests/test_cross_capability_provenance.py
- backend/tests/test_document_structure_orchestrator.py
- docs/adr/0010-document-intelligence-capability-routing.md
- docs/roadmap.md

ADR-0010 documenta trust/localidad, correspondencia no probada, continuidad y
seguridad de bindings; R.3a queda identificado como aceptado. Roadmap conserva
R.3 CURRENT/R.4 NEXT, con R.3a CLOSED y Tender #002 blind hasta 06.V/readiness gate.

Git: 10 archivos rastreados modificados y 3 nuevos de este slice. Los 17 archivos
no rastreados preexistentes permanecen intactos. No stage/commit/push.

Semánticas protegidas sin redefinición. Source Effect protected modules, frontend,
pricing, Golden/versioning labels y Tender #001 Golden: sin cambios.
Tender #002: no inspeccionado ni usado. Modelos reales ejecutados: **NO**.
Fixtures/mocks prueban contratos y flujo; no certifican percepción visual/OCR.

Blockers técnicos: ninguno. Pendiente aceptación humana de arquitectura; no cerrar
R.3 ni ejecutar calibración real automáticamente.

Siguiente slice recomendado: **MVP-06.R.4 — Tender #001 Real Document Intelligence
Convergence Calibration**, después de aceptar R.3.
