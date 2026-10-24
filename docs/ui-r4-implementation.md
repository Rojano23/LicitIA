# UI-R4 — Requisitos, Cumplimiento y Partidas

Estado: implementación validada; pendiente de revisión arquitectónica y visual humana.
**UI-R4 sin stage/commit/push.** Baseline visual UI-R3 conservado.
[ADR-0038](adr/0038-requirements-compliance-scope-product-ui.md).

## Reporte final

1. **Aprobación UI-R3:** Product Owner confirmó ARCHITECTURE PASS / FUNCTIONAL PASS / VISUAL PASS.
   Se inspeccionó la contact sheet aceptada antes del commit. Sin UI-R3.1. El contorno azul
   es foco accesible: el E2E verifica outline none tras blur; no se eliminó :focus-visible.
2. **Commit runtime UI-R3:** `935dce1017195f69c1fb74138571b1c8583d037f`,
   `feat(ui): implement tender workspace and documents`;19/19 hashes aceptados coincidieron.
3. **HEAD resultante:** mismo SHA, padre `ed3e1a2ce208f761de4869eae8e252477125afa8`.
   Un único commit runtime UI-R3, sin push. UI-R4 permanece fuera del índice.
4. **19 archivos UI-R3 comprometidos:** docs/roadmap.md, docs/ui-r3-implementation.md,
   frontend/src/App.tsx, frontend/src/ProductApp.tsx, frontend/src/components/WorkspaceFlow.test.tsx,
   frontend/src/components/WorkspaceFlow.tsx, frontend/src/ui/Shell.test.tsx,
   frontend/scripts/ui-r3-browser.mjs, frontend/src/api/tenders.test.ts, frontend/src/api/tenders.ts,
   frontend/src/components/DocumentImports.test.tsx, frontend/src/components/DocumentImports.tsx,
   frontend/src/components/DocumentViewer.test.tsx, frontend/src/components/DocumentViewer.tsx,
   frontend/src/components/TenderDocumentsView.tsx, frontend/src/components/TenderProductViews.test.tsx,
   frontend/src/components/TenderProductViews.tsx, frontend/src/components/TenderRouting.test.tsx,
   frontend/src/components/tenderDocuments.css. Sin reportes, imágenes, DB, env ni archivos ajenos.
5. **Requisitos:** tabla principal y detalle contextual; texto literal de3líneas, no resumen inventado.
6. **Columnas6:** Requisito, Categoría, Fuente, Evidencia solicitada, Revisión y Acción.
   Evidencia solicitada no se presenta como evidencia empresarial encontrada ni cumplimiento.
7. **Filtros:** búsqueda literal case-insensitive del texto, categoría canónica y revisión exacta;
   filtros locales sobre toda la matriz devuelta. Sin filtros de motores ni endpoint nuevo.
8. **Contadores:** total_requirements/pending_review_count/needs_review_count/approved_count del
   summary de GET `/tenders/{id}/requirement-matrix`. Sin porcentaje ni pie chart.
9. **Detalle:** texto completo, fuente, Requested Evidence, interpretación, condición, advertencias,
   revisión humana y nota. UUID/fingerprint bajo diagnóstico. No se inventa historial append-only:
   el contrato Requirement ofrece estado actual/nota/fecha, distinto del historial Scope.
10. **Ver fuente:** misma ruta Documentos con query `document={UUID}&page={N}`; el ID conserva revisión.
    No filename matching ni cambio silencioso a revisión actual. Requested Evidence tiene fuente
    propia si existe. Enlace a Cumplimiento conserva requirement ID; empresa se elige explícitamente.
11. **Etiquetas:** mapas por contexto para categoría, revisión Requirement, interpretación/vigencia,
    evaluación automática, decisión de cumplimiento, evidencia/asociación, Scope, Quantity y frescura.
    Unknown queda “Información por revisar”, nunca raw enum. Categorías del normalizador verificadas.
12. **Acciones Requirement:** APPROVE/MARK_NEEDS_REVIEW/REJECT/RESET mediante PATCH existente y nota.
    Se relee representación antes de guardar; si cambió, no se envía. Confirmación humana explícita.
    El API no recibe expected fingerprint: esta comprobación no crea garantía atómica nueva.
    No editar texto Requirement donde el contrato sólo permite revisión. Aprobar no confirma cumplimiento.
13. **Cumplimiento:** selección de empresa, resumen canónico, filtro operativo y tabla con detalle.
    Empresa/selección/filtros permanecen en memoria al ir a fuente y regresar dentro del mismo Tender.
14. **Estados:** evaluación SUPPORTED/PARTIALLY_SUPPORTED/NOT_SUPPORTED/REVIEW_REQUIRED/NOT_EVALUATED
    se etiqueta automática; COMPLIES/DOES_NOT_COMPLY/NOT_APPLICABLE/PENDING/NEEDS_REVIEW son decisiones
    humanas. Se expone frescura/decisión desactualizada; sin decisión → “Sin decisión humana registrada”.
15. **Candidatos:** “Evidencia candidata”, justificación literal y fuente empresarial. Nunca “Cumple”
    por un match, por confianza ni por encontrar un archivo. Tabla cuenta asociaciones, no éxitos.
16. **Confirmada/rechazada:** la revisión de la asociación y la revisión de evidencia son dos estados
    separados. Confirmar/rechazar asociación usa PATCH match review. “Asociación confirmada — no
    certifica cumplimiento”. Se conserva origen, frescura y diagnóstico de la relación.
17. **Ausencia:** “Sin evidencia asociada” sólo para matches vacíos en esa fila; no sentencia legal.
    Fallo GET evidencia se presenta localizado en detalle, sin vaciar requisito ni tabla de cumplimiento.
18. **Relación manual:** carga biblioteca de la empresa al solicitarla; selector de evidencia real,
    ID canónico y rationale para POST manual existente. Confirmación explícita; se advierte que el
    contrato confirma asociación, no cumplimiento. Sin documentación empresarial ficticia o nuevo workflow.
19. **Contadores Cumplimiento:** active_requirements/finalized_count/review_required_count del
    summary de GET `/tenders/{id}/companies/{company}/compliance-matrix`. Sin porcentajes ni sumar
    candidatos como requisitos cumplidos. Filtro por operational_state existente sobre filas devueltas.
20. **Detalle evidencia/cumplimiento:** requisito/fuente, evaluación y checks, asociaciones/justificación,
    documento/página/extracto empresarial, revisión independiente y decisión humana con nota.
    PDF Company conserva su endpoint y ownership; no se pide un CompanyDocument como TenderDocument.
    Office/otros formatos conducen a Mi empresa, sin visor ficticio. No mini-PDF duplicado.
21. **Partidas:** tabla de alcances, detalle y contexto documental provisional plegable. Alternativas
    técnicas/revisión canónicas existentes siguen accesibles; sin nuevo inventario Vision en paralelo.
22. **Verdad primaria:** GET `/tenders/{id}/workspace`.scopes + sus cantidades por FK ScopeDetail.
    No se usa `/items` legacy ni Vision proposals como lista primaria. Scope persistido no se equipara
    automáticamente a TenderItem contractual completo ni a aceptación humana.
23. **Columnas5:** Alcance, Cantidad/unidad, Revisión, Fuente, Acción. No candidate key ni UUID.
    Varias cantidades se resumen como N cantidades/ver detalle; no agregación numérica inventada.
24. **Candidato/canónico:** Scope sin confirmación se muestra detectado/requiere revisión; las decisiones
    humanas tienen etiqueta propia. En contexto estructural, grupos sin canonical_items se rotulan
    detectados/no partida canónica; no se promueven ni se mezclan como otra tabla de verdad.
25. **Multipágina:** scope-summary muestra segmentos persistidos con sus documentos/páginas/extractos.
    Se vinculan al alcance seleccionado únicamente por IDs de item/segment expuestos en el read model.
    Si no hay relación verificable se dice; no se infiere por número, filename o candidate key.
26. **Página compartida:** distintos grupos conservan segmentos propios aunque compartan página.
    No se reasignan por orden ni se deduplica la página eliminando ownership de otra partida.
27. **Incompleto:** estado operacional y cobertura de scope-summary (not_analyzed/review_required)
    permanecen visibles. Cero resultados/cobertura parcial jamás implica alcance completo.
28. **Fuentes/revisión Scope:** documento/revisión/página/extracto y método traducido. Cantidades de
    sólo lectura, con ownership validado y fuente propia. Confirmación/corrección de descripción/rechazo
    conserva expected_projection_fingerprint y expected_current_review_revision;409 exige nueva revisión.
    Historia por Scope ID disponible; registros retirados siguen accesibles en Diagnóstico, no se borran.
29. **App.tsx:** extracción de24 DTO aliases reutilizables hacia `api/engineeringTypes.ts`; sin alterar
    lógica backend ni cálculos. Vistas operativas UI-R4 nuevas sustituyen anclas para esos tres destinos;
    App técnico permanece en Diagnóstico y UI-R5. No rediseño global ni eliminación de herramientas.
30. **Wrappers:** `api/engineering.ts` refleja GET/mutaciones existentes, valida Tender/Company y
    codifica IDs. Reutiliza workspaceApi/scopeReviewApi. No proyección ni DTO servidor nuevo.
31. **Ownership async:** `useRead` liga estado a key de contexto y generation/liveness; detalles con
    key Requirement/Company/Scope. Cada formulario tiene estado y liveness propios; empresa distinta
    desmonta el contexto anterior. Vistas visitadas conservadas por Tender para retorno de fuente.
32. **Stale:** resultados de contexto anterior no se consumen por otro key; A tardío no sustituye B.
    Fuente documental mantiene protecciones R3 y agrega página inicial explícita. Tests de Requirement,
    Evidence y Scope atrasados, además del test PDF de revisión histórica/página7.
33. **No análisis automático:** abrir lista/detalle/fuente sólo lee registros; CDP registra cero writes
    en recorrido R4. Tests comprueban cero OCR/Vision/LLM/matching/extracción por navegación. Acciones
    de análisis ya existentes permanecen explícitas en Diagnóstico; no se cambian budgets/políticas.
34. **Backend:**0 cambios producción/tests. Los GET y mutaciones existentes permanecen autoritativos.
35. **Alembic:** current test y heads verificados = `20261023_discovery_079`;0 migraciones.
36. **Dependencias:**0; sin package/lock changes. React/TS/axios y herramientas de validación existentes.
37. **Stitch/baseline:** navy compacto, lienzo claro, tabs Tender sin aumento de altura, azul sobrio,
    table-first y metadatos técnicos secundarios. CSS del shell y proporciones Documentos sin modificar.
38. **Densidad:** seis columnas Requirement y cinco Cumplimiento/Partidas; detalle360px cuando cabe,
    scroll local, texto recortado con literal completo al abrir. Sin cards de relleno ni métricas fake.
39. **1366×768:** PASS para las tres vistas. Tabla y panel contextual utilizables; detalle desplaza
    internamente y la tabla puede tener scroll local. Errores no invalidan visualmente todo el Tender.
40. **1440×900:** PASS para las tres vistas, capturas específicas. Mismo shell/nav, sin segundo sistema UI.
41. **1920×1080:** PASS, contenido limitado por ancho del shell y más espacio para matriz/lectura.
42. **Narrow768×900/390×844:** PASS sin overflow horizontal global; tabla desplaza localmente,
    panel debajo de tabla y navegación accesible. No certificación de operación móvil de ofertas.
43. **26 capturas nuevas:** directorio absoluto
    `/Users/ceciliavalencia/LiticIA/backend/reports/ui_r4/browser/`.
    `01-requirements.png`, `02-requires-review.png`, `03-requirement-detail.png`, `04-source-page.png`,
    `05-requirements-empty.png`, `06-compliance.png`, `07-evidence-candidate.png`,
    `08-confirmed-association.png`, `09-missing-evidence.png`, `10-compliance-review.png`,
    `11-scopes.png`, `12-scope-review.png`, `13-multipage-scope.png`, `14-shared-page.png`,
    `15-partial-coverage.png`, `16-{requisitos|cumplimiento|partidas}-{1366|1440|1920}.png`,
    `17-narrow-768.png`, `18-narrow-390.png`. Fixtures aisladas, no datos del usuario.
44. **Contact sheet:** mismo directorio `contact-sheet.png`,1800×1000,6estados (requisitos/detalle,
    cumplimiento/evidencia/partidas/trazabilidad). No incorporada a Git.
45. **Focused nuevo:** `npm --prefix frontend test -- src/components/Engineering.test.tsx src/components/DocumentViewer.test.tsx src/components/TenderRouting.test.tsx src/components/ScopeReview.test.tsx src/components/TechnicalAlternatives.test.tsx src/components/AlternativeCompliance.test.tsx`
    → **107 passed/6files**. Engineering incluye21casos nuevos de contratos, revisión, manual match,
    async y StrictMode; PDF agrega navegación inicial histórica. Mocks no prueban calidad semántica.
46. **Frontend completo nuevo:** `npm --prefix frontend test` → **247 passed/30files**.
    Shell test transitorio ahora inicia en Comercial (workspace legacy), preservando su assert de no
    remount/draft; las rutas nuevas y fuentes tienen pruebas reales de componentes separadas.
47. **E2E nuevo:** `node frontend/scripts/ui-r4-browser.mjs backend/reports/ui_r4/browser`
    → **11grupos PASS**,26capturas, sin excepciones ni writes de análisis. Matrices/filtros, fuente
    documento/página7, empty, evidencia candidata/confirmada, decisión humana, multipágina/shared-page,
    parcialidad, tres desktops+narrow, UI-R5/Diagnóstico. PDF sintético9páginas; sin API de producto.
48. **Backend API nuevo:** desde backend,
    `DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_requirement_matrix.py tests/test_evidence_matching.py tests/test_compliance_review.py tests/test_compliance_matrix.py tests/test_scope_review_api.py -q`
    → **93 passed,6warnings,34.80s**. Warnings Swig; sin proveedores reales ni suite semántica ajena.
49. **Regresión UI-R3 nueva:** `node frontend/scripts/ui-r3-browser.mjs backend/reports/ui_r4/ui_r3_regression`
    → **12grupos PASS**. No se sobrescribieron sus capturas históricas.
50. **Regresión UI-R2 nueva:** `node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r4/ui_r2_regression`
    → **13grupos PASS**. Runners secuenciales en Chromium aislado; sin perfiles/cookies del usuario.
51. **Build/typecheck nuevos:** `npm --prefix frontend run build`, `npm --prefix frontend run typecheck`
    PASS; JS589.26kB,CSS28.52kB. Persiste warning>500kB conocido, sin code splitting dentro del slice.
52. **Compile/diff:** intérprete backend obligatorio `-m compileall -q backend/app backend/scripts backend/tests`
    desde raíz PASS; `git diff --check` PASS. Índice vacío. Sin stage/commit/push UI-R4.
53. **Archivos exactos:** lista abajo. Sólo UI-R3 se comprometió; reportes/PNG/JSON locales excluidos.
54. **Limitaciones:** no relación Requirement→Partida inventada donde no hay read model canónico;
    fuente Company no entra al visor Tender; Office sigue sin preview. Sin edición de texto Requirement,
    historial Requirement append-only o nueva garantía de concurrencia en endpoints que no la ofrecen.
    La comprobación previa de representación reduce riesgo sin sustituir un CAS servidor inexistente.
    Los filtros/empresa/detalles se conservan durante navegación del mismo Tender, no después de refresh;
    borradores no guardados pueden perderse al cambiar contexto. No certificar alcance completo,
    cumplimiento contractual, calidad semántica o WCAG con fixtures. Sin barrido5941 nuevo: su resultado
    anterior es heredado; evidencia histórica anterior se conserva y no se inspeccionó Tender002.
55. **Gates A–S:** PASS para los contratos y límites implementados, matriz abajo; no equivale a aprobación
    visual humana final de UI-R4 ni certificación de cumplimiento.
56. **Listo para commit:** sí, sujeto a revisión/aceptación humana. Sin stage/commit/push UI-R4.
57. **UI-R5 recomendado exacto:** composición visual de Comercial, Preparación y Propuesta sobre APIs
    actuales; conservar monedas, markup≠margen, overrides/audit, snapshots, versiones, freeze/stale y
    export seguro. Integrar fuentes sin rediseñar motores, presupuestos, auth o Mi empresa. No implementado.

## Archivos exactos UI-R4

Modificados:

- docs/roadmap.md
- frontend/src/App.tsx
- frontend/src/ProductApp.tsx
- frontend/src/components/DocumentViewer.test.tsx
- frontend/src/components/DocumentViewer.tsx
- frontend/src/components/TenderDocumentsView.tsx
- frontend/src/components/TenderProductViews.tsx
- frontend/src/ui/Shell.test.tsx
- frontend/src/ui/routes.ts

Nuevos:

- docs/adr/0038-requirements-compliance-scope-product-ui.md
- docs/ui-r4-implementation.md
- frontend/scripts/ui-r4-browser.mjs
- frontend/src/api/engineering.ts
- frontend/src/api/engineeringTypes.ts
- frontend/src/components/ComplianceView.tsx
- frontend/src/components/Engineering.test.tsx
- frontend/src/components/ItemsView.tsx
- frontend/src/components/RequirementsView.tsx
- frontend/src/components/engineering.css
- frontend/src/components/useRead.ts
- frontend/src/test/engineeringFixtures.ts
- frontend/src/ui/engineeringPresentation.ts

## Gates A–S

| Gate | Resultado / evidencia |
|---|---|
| A requisitos | PASS tabla6columnas, filtros, literal truncado sin resumen inventado |
| B fuente | PASS documento/revisión/página7 y extracto |
| C evidencia | PASS candidato/asociación/evaluación/decisión separados |
| D autoridad | PASS acciones explícitas, notas y confirmación; Scope CAS conservado |
| E cumplimiento | PASS assessment y decisión humana canónicos; summary sin porcentaje |
| F partidas | PASS workspace.scopes/Quantity persistidos |
| G candidatos | PASS grupos provisionales aparte; nunca Vision como inventario primario |
| H estructura | PASS segmentos por ID, multipágina y página compartida |
| I parcialidad | PASS cobertura y not_analyzed, sin certeza de completitud |
| J disclosure | PASS tres niveles; IDs/métodos crudos en diagnóstico |
| K visor | PASS UI-R3 reutilizado, sin mini-PDF duplicado |
| L async | PASS generation/context keys, A tardío no sustituye B |
| M lectura | PASS navegación sin escrituras/análisis en tests y CDP |
| N backend | PASS0 cambios backend/modelos/API |
| O esquema | PASS079,0migrations |
| P datos | PASS fixtures sólo en test/script; runtime lee API |
| Q1366 | PASS tres matrices y detalle con scroll local |
| R visual | PASS continuidad con baseline aprobado; revisión humana UI-R4 pendiente |
| S regresión | PASS107focused/247frontend/93backend/11R4+12R3+13R2browser/build/types/compile/diff |

## Evidencia y cierre

Artefactos locales bajo `backend/reports/ui_r4/`: logs, validation.json, hashes de fuentes,
results.json, capturas y regresiones. Sin reportes/imágenes en staging; sin bases de datos/env.
No providers reales, portales públicos, cloud upload ni análisis ciego. Originales/historia sin
modificaciones. Esta entrega se detiene para revisión arquitectónica y visual; no inicia UI-R5.
