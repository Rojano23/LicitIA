# MVP-06.V.6b — Structured Evidence Reconstruction + Multispan Grounding

Estado: implementación terminada, sin stage/commit/push; para revisión del arquitecto.

## Estado y alcance

HEAD inicial/actual: `a24a5b18fe43ca15a949408b77e19aea1f2950a4` (sin cambio). Al inicio, tracked tree limpio y
staging vacío. La implementación queda sin commit; los reportes históricos
preexistentes siguen sin rastrear. No se modificaron roadmap, modelos,
migraciones, Requirements, Requested Evidence, planner, proveedores, prompts ni
budgets. No se consultó semánticamente Tender #002 ni se creó Attempt #5.

SI21–SI23 se difieren explícitamente a V.6c por instrucción humana. No se cuentan
como PASS ni como pruebas ejecutadas. La falla interpretativa todavía puede
influir en suficiencia mediante la gramática legacy del planner; esa corrección
permanece pendiente. No preparar una nueva ejecución ciega dentro de este slice.

Reporte arquitectónico V.6a conservado, SHA-256:
`672c9e74952facc7543339e90f59af06ba6b189bc3e1eab1c6c4ba6d845c8046`.

## Pérdida confirmada y cambio de comportamiento

La primera pérdida estaba en formación del candidato Scope, antes de dedup,
persistencia o hijos: procurement_rows no representaba columnas/fragmentos
relacionados. La nueva IR tipada y congelada StructuredEvidenceBlock representa
fuente, documento/revisión/hash original, página/generación, capacidad, ámbito,
fragmentos literales con offsets/orden/roles, relaciones tipadas, field bindings,
ambigüedad y review. El intérprete compartido no adquiere percepción ni depende
de un proveedor. Los contratos legacy y los adapters configurados explícitamente
conservan su camino; la integración canónica aplica el contrato compuesto a las
fuentes soportadas que lo necesitan, incluyendo páginas con filas y tablas mixtas.

Reconstrucción acotada:

- Ítem rotulado con acción de suministro/servicio/entrega, campos explícitos y
  continuación descriptiva indentada. No unir prosa por mera cercanía.
- Tablas con delimitadores explícitos y headers únicos de partida, descripción,
  cantidad y unidad: roles de columnas y referencias de header/celda separados.
  Número/cantidad/unidad reconocidos sostienen identidad local; sin verbo rector,
  dominio OTHER/review conserva incertidumbre sobre el dominio contractual.
- Filas distintas y ocurrencias repetidas mantienen límites separados. Headers
  repetidos aportan contexto; nunca se convierten en ítems. Blank lines, texto
  ajeno y límites de página interrumpen relaciones no demostradas.
- No se crean ítems por índices, preguntas, numeración de secciones, fechas,
  importes o listas de páginas sin relaciones positivas.

Una identidad local positiva permite Scope ITEM revisable; no escribe estructura
TRUSTED ni confianza. Comparaciones críticas y conflictos de continuidad retiran
el owner. Campos duplicados o fuentes en conflicto conservan alternativas en
provenance y Scope UNRESOLVED/review, sin hijos canónicos ni voto por capacidad.
Todos los candidatos del contrato compuesto conservan review_required=true y
confidence=None.

## Grounding, manifiesto y locator

Contrato `STRUCTURED_EVIDENCE_001`, política `structured-evidence-v1`; ADR 0015
creado como propuesta implementada, pendiente de revisión, sin commit.

Manifiestos JSON canónicos por SHA-256 bajo el data root canónico:
`provenance/structured-evidence-v1/<sha256>.json`. El locator compacto conserva
página, revisión, generación y método además de SHA/bloque; documento y página
canónicos siguen en los objetos de negocio. No se guarda ruta absoluta ni /tmp.
source_excerpt es un fragmento literal representativo, nunca un join ficticio.
Description es composición interpretativa; quantity/unit/attributes tienen refs
propias, roles y relaciones al parent/header.

Límites: 500,000 caracteres/fuente, 256 bloques/página, 128 fragmentos/bloque,
64 bloques de soporte/manifiesto y 2 MiB/manifiesto; locator máximo 512 caracteres.

MG01–MG15: versionado, canonicalización determinista, identidad/hash verificados,
publicación atómica de archivo completo fsynced mediante hard link exclusivo,
referencia exacta, missing/corrupt fail-closed, root guard contra escape/symlink,
referencias portables sin temporales, spans separados y exactos, ausencia de
citas concatenadas falsas, identidad genérica, regeneración idempotente,
identidad distinta para evidencia distinta y no sobrescritura histórica.

Resolvers despachan el contrato nuevo antes de los parsers legacy, reenumeran
fuentes activas y validan identidad/generación/hash, offsets y relaciones mediante
reconstrucción determinista. Una relación inventada con JSON/hash válidos también
se rechaza. No hay fallback a page.text para salvar un manifiesto ausente,
corrupto, incompatible o stale. La persistencia de dominio vuelve a validar;
no basta con pasar un adapter. Valores numéricos distintos de la evidencia
literal también se rechazan.

La prueba se escribe antes de la referencia DB. Rollback puede dejar un archivo
huérfano seguro, nunca una referencia autorizada a un archivo parcial. No hay GC
ni eliminación automática. Retener el subtree completo de provenance junto con
DB/generaciones en backup/export; cualquier limpieza requiere operación explícita
con verificación de referencias. No se promete atomicidad transaccional SQL+FS.

## Fuentes, ownership, hijos e identidad

Native mantiene offsets de NormalizedContent y su hash. OCR verifica generación,
engine/version/language/region/recibo y conserva hash raw; sus spans se aplican
exclusivamente a NORMALIZED_TEXT, evitando el cruce raw/normalized. OCR textual
fragmentado con fila explícita puede reconstruirse; sin relación de fila no se
completan celdas por cercanía. No se inventan cajas ni se reextrae geometría.

Vision consume exclusivamente detalle canónico existente, incluidos raw_lines
cuando están disponibles; conserva imagen SHA, análisis, generación/model/prompt,
task fingerprint y región declarada. STRUCTURE_SCOPE no sustituye detalle.
No se rediseña ni ejecuta Vision. Sin ámbito/celdas demostrables no se presupone
geometría ni equivalencia con una fila Native.

Attribute y Quantity pueden permanecer como FieldBindings provisionales en el
bloque/manifiesto aunque se retire el owner. Persistirlos sigue requiriendo FK
ScopeDetail y valid_scope_identity; no se creó modelo huérfano. Marca/modelo,
cantidad Decimal y unidad se materializan sólo desde bindings revalidados del
parent correcto. El excerpt de cantidad puede ser sólo el número: su unidad se
prueba con su propio fragmento, sin fabricar una cita contigua.

Identidad compuesta `structured-logical-v1`, independiente de capacidad, usa
owner/ocurrencia/ámbito y descripción exacta normalizada sólo en whitespace.
Se comparan hechos con ámbitos demostrablemente equivalentes; FULL_PAGE, REGION
y ámbito desconocido no se fusionan por asumir la misma ocurrencia. No hay
paraphrase/fuzzy merge. Múltiples soportes comparables se guardan en el manifiesto
persistido, conservando todas las capacidades. Conflictos conservan alternativas
y review. `scope-logical-v2` legacy permanece sin cambios.

Replay idéntico conserva IDs/hijos/prueba. Corroboración adicional del mismo hecho
conserva parent y decisión humana sin aumentar confianza: sólo se admite si la
prueba primaria y el resto del snapshot siguen iguales y la proyección Source
Effects coincide. No se reescribe el snapshot histórico de la decisión. Generación
real distinta reemplaza/invalida; la revisión histórica permanece y no se
reasocia al nuevo Scope. Los manifiestos anteriores se retienen.

Freeze registra las constantes reales de política y manifiesto, además de las
versiones legacy. No se cambió la política/fingerprint del planner ni los budgets.

## Matriz SI y MG

39 pruebas sintéticas en test_structured_interpretation; MG01–MG15: 15 PASS.
Cobertura aplicable SI01–SI20 y SI24–SI32; SI21–SI23 PENDIENTES V.6c.

| Casos | Evidencia comprobada |
|---|---|
| SI01–SI05 | Single line, multiline, headers/celdas, filas distintas/mixtas y headers repetidos |
| SI06–SI09 | Abstención en índice, cuestionario, sección, fecha/importe narrativo |
| SI10–SI12 | OCR con orden explícito, abstención sin relación, spans separados |
| SI13–SI15 | Provisionalidad, hijos del owner correcto y rechazo de valor numérico falso |
| SI16–SI17 | Reconciliación comparable, ocurrencias/ámbitos separados y soportes persistidos |
| SI18–SI20 | Owner ambiguo/continuidad conflictiva, prosa sin Scope, replay/generación nueva |
| SI21–SI23 | Diferidos a V.6c por instrucción humana; sin PASS artificial |
| SI24 | ST10–ST20 y positivos/negativos V.4a en regresión completa de safety |
| SI25–SI28 | Raw/normalized OCR, integridad, corroboración humana y conflictos multifuente |
| SI29 | No herencia por adyacencia/header entre páginas; continuidad legacy probada preservada por ST01–ST09 |
| SI30–SI32 | Detalle/imagen Vision, sin geometría ficticia/adquisiciones, cascade/historia/manifiestos retenidos |

El primer corte no compone automáticamente spans entre páginas: la continuidad
canónica existente sigue intacta, pero una nueva relación multispan multipágina
sin soporte explícito queda fuera de reconstrucción, según el límite de V.6a.
Los tests no certifican recall ni calidad real de OCR/Vision/modelos.

## Validación final reproducible

Intérprete obligatorio; cwd backend. Todos los tests usan licitia_test.

| Grupo (incluido en ampliada) | Resultado |
|---|---|
| SI | 39 PASS |
| MG | 15 PASS |
| V.4a structural trust safety | 24 PASS |
| V.4b SC/DC Native | 46 PASS |
| Selective OCR / Vision | 44 / 46 PASS |
| BR / FB / BH | 16 / 23 / 37 PASS |
| Scope details/attributes/quantities: adapters + materializers + integración | 159 PASS |
| Human review + API | 87 PASS |
| Ampliada DI/MVP-06.V | 1063 PASS, 1 deselected, 8 warnings |
| Suite completa | 2019 PASS, 1 deselected, 8 warnings |
| compileall app/scripts/tests | PASS |
| git diff --check | PASS |

Warnings existentes: SWIG, python_multipart, Alembic path_separator y Paddle
ccache; no nuevos warnings en el cierre. Única exclusión: local_ollama opt-in.
Los fallos de integración detectados durante el desarrollo fueron corregidos;
las cifras anteriores corresponden a la versión final sin fallos.

Comando ampliado exacto (salida redirigida a /private/tmp/v6b_expanded.log):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest \
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
  -q -m 'not local_ollama' --junitxml=/private/tmp/v6b_expanded.xml
```

Suite completa (salida /private/tmp/v6b_full.log):

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama' --junitxml=/private/tmp/v6b_full.xml
```

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
git diff --check
git diff --stat
git status --short
```

Alembic leído mediante observe_schema_drift + verify_accepted_drift en conexión
READ ONLY de licitia_test:

- current/head: `20261013_req_perception_prov_072`;
- drift: 59 = 55 add_index / 4 remove_index;
- firma: `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`;
- nuevos drifts: 0; schema/model/migration change: NO.

## Integridad histórica y Git

Verificación sólo por hashes, sin adjudicación ni inspección semántica:
107/107 históricos, 24/24 del baseline Attempt #3, 1369/1369 artefactos
operativos Attempt #4, 16/16 de adjudicación Attempt #4 y 139/139 archivos de su
storage. Cero mismatches. Attempts #1–#4 y adjudicaciones no se modificaron.
El SHA del reporte V.6a coincide con el aceptado.

Archivos tracked modificados:

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

Archivos nuevos de este slice:

- `backend/app/structured_evidence.py`
- `backend/app/structured_evidence_grounding.py`
- `backend/app/structured_evidence_storage.py`
- `backend/tests/test_structured_interpretation.py`
- `backend/tests/test_structured_grounding.py`
- `docs/adr/0015-structured-evidence-multispan-grounding.md`
- `backend/reports/structured_evidence_reconstruction_v6b.md`

Reporte técnico permanece untracked; ADR pendiente de aceptación. Staging vacío.
Los demás archivos untracked del repositorio son históricos preexistentes y no
se agregaron/eliminaron/reescribieron. No stage, commit ni push.

## Límites y siguiente revisión

No hay blocker de esquema ni de validación automatizada para este corte.
Permanecen explícitamente: V.6c/SI21–SI23, layouts sin delimitadores o prueba de
relación suficiente, composición nueva entre páginas sin continuidad demostrada,
y revisión arquitectónica del contrato durable/backup de provenance. No se
certifica calidad semántica de un Tender real con fixtures sintéticas.

Confirmaciones: evidencia multiline/table válida produce Scope; atributos y
cantidades pueden seguir provisionales; hijos persistidos requieren Scope;
multispan provenance es verificable independientemente; TOC/cuestionarios
mantienen abstención; planner V.6c pendiente; proveedores reales/OCR/Vision
invocados: 0; lógica específica Tender #002: NO; Attempt #5: NO.
