# UI-R5 — Comercial, Preparación y Propuesta

Estado: superficies Comercial/Preparación/Propuesta con aprobación visual del Product Owner;
sidebar contraíble implementado y validado, pendiente revisión final UI-R5.
**Sin stage, commit ni push de UI-R5.** MVP-01–10 permanecen cerrados.
[ADR-0039](adr/0039-commercial-readiness-proposal-product-ui.md).

## Reporte final de las superficies UI-R5

Los 59 puntos siguientes registran la entrega previa al refinamiento del shell. El addendum
al final actualiza totales, archivos y gates del conjunto completo; no representa UI-R5.1.

1. **Commit UI-R4:** `0915e83a4173a14653df089b302d30aa2c7a7a13`,
   `feat(ui): implement requirements compliance and items`. Se verificaron los 22 hashes
   aceptados contra la evidencia UI-R4 y se hizo staging explícito, sin reportes ni imágenes.
2. **HEAD resultante:** mismo SHA; padre `935dce1017195f69c1fb74138571b1c8583d037f`.
   Un único commit UI-R4, sin push. UI-R5 permanece sin comprometer.
3. **Archivos comprometidos:** 22, enumerados al final. Sólo implementación, pruebas y docs.
4. **Comercial:** tabla principal de lectura canónica, filtro de estado, detalle contextual
   por partida, subtotales plegables y editor de lote/intercambio secundario.
5. **Columnas (6):** Partida/descripción, Cantidad heredada, Fuente de costo, Costo unitario,
   Precio unitario, Estado/acción. Sin marca/modelo/proveedor inferidos. Quantity sólo se
   muestra para el ID seleccionado canónico; no se supone cantidad 1 ni se suman candidatos.
6. **Formato:** strings decimales agrupados, mínimo dos decimales, signo y moneda explícitos.
   Se conserva precisión adicional sin redondear ni convertir a Number; números a la derecha,
   tabulares y neutrales. Null es Sin resolver. Sin FX ni gran total entre monedas.
7. **Autoridad del valor:** tabla de lectura; campos editables en editor humano; resultados
   identificados como Calculado por el servidor. Origen UI/importación/costo visible en detalle.
8. **Procedencia:** fuente de costo y origen económico traducidos; parte, referencia y documento
   reales, acceso a revisión documental exacta. No se transforma una estimación en cotización.
9. **Proveedor/cotización:** únicamente campos existentes. Sin referencia/documento se informa
   su ausencia. El DTO no expone fecha ni vigencia: no hay etiquetas vigente/vencida, ranking,
   estrellas o score. La ausencia de cotización no bloquea automáticamente una decisión humana.
10. **Markup/margen:** etiquetas separadas; los valores efectivos/recomendados se reciben del
    servidor. No se añadieron fórmulas, cálculos comerciales ni cambios de aritmética en JS.
11. **Detalle:** partida, origen, parte/cotización, costo/oferta/utilidad canónicos, markup/margen,
    editor CommercialLine, override manual, historial y diagnóstico secundario. Guardar/calcular
    conserva expectativas y confirmación explícita para reemplazar un precio manual.
12. **Intercambio:** CommercialMatrix/CommercialSpreadsheet reutilizados: XLSX/CSV, preview,
    apply confirmado, conflictos, manual-price protection y resultados por fila intactos.
    El editor completo sigue bajo disclosure; tras lote se actualiza explícitamente la tabla
    principal. Guardar/aplicar una línea vuelve a consultar la tabla. Sin nuevos formatos.
13. **Preparación:** estado según última consulta local, conteos canónicos, áreas plegables,
    tabla priorizada paginada (50), filtro por grupo y seguimiento humano bajo detalle.
14. **Bloqueos:** orden del board del servidor; se muestran área, resumen y acción. El cierre
    de actividad no modifica la severidad ni satisface faltantes. El detalle lo explica.
15. **Advertencias:** conteo y grupo distintos de bloqueo/revisión. No se convierten en bloqueo
    comercial; riesgos aceptados y seguimiento conservan contratos M8-B.
16. **Listo:** sólo si el motor devuelve READY. Un conjunto vacío o error no demuestra preparación.
    La fixture lista conserva una advertencia canónica; no se fabrica una preparación perfecta.
17. **Actual/capturado:** board consultado y captura histórica son superficies separadas.
    Evaluación, creación explícita con confirmación, UUID de retry e historial se reutilizan.
    No se crea snapshot al abrir. Datos históricos no reemplazan el board actual.
18. **Navegación:** dimensiones canónicas llevan a Documentos/Requisitos/Cumplimiento/Partidas/
    Comercial. Un issue comercial de entidad SCOPE lleva a su Scope mediante `?scope=…`.
    Contexto API y provenance disponibles en detalle, sin inventar relaciones.
19. **Propuesta:** tabla de versiones, elección explícita de captura preparada, configuración,
    composición/respuestas, congelado y tabla de archivos generados. Hash/IDs en detalle.
20. **Borrador:** editable únicamente latest DRAFT, traducido Borrador. Crear conserva confirmaciones,
    snapshot y solicitud idempotente existente; no implica listo para presentar.
21. **Congelada:** texto de inmutabilidad/historia, configuración/composición deshabilitadas;
    revisión nueva explícita. Backend/FK/expectativas de congelado intactos.
22. **Cambios posteriores:** comprobación explícita separada de fuente; aviso comprensible.
    Sin consulta no se afirma CURRENT. Ninguna lectura modifica binding o contenido histórico.
23. **Binding:** captura fija declarada en la versión, identidad/hash bajo detalle. Selector usa
    historial canónico paginado, nunca UUID inventado ni estado actual como reemplazo silencioso.
24. **Respuestas:** compositor existente con contenido humano identificado y datos fuente de
    sólo lectura plegables. Declaración no equivale a certificación; acciones/inicialización/
    reconciliación permanecen explícitas y protegidas por revisión.
25. **Artefactos:** tabla por generación: formato, descarga, tamaño e integridad secundaria;
    fecha, versión y estado en encabezado. Sólo receipts efectivamente devueltos por la API.
26. **DOCX/XLSX/PDF/ZIP:** comandos/links canónicos existentes; borrador exige autorización,
    congelada preserva snapshot/composición. XLSX de propuesta no reimporta precios comerciales.
    No se exponen costos/margen/markup internos a través de un nuevo renderer.
27. **Generación/error:** acción explícita, estado de solicitud real sin porcentaje ni ETA;
    error local conserva versión y listado anterior. Retry conserva el request pendiente.
28. **Verificación:** comando existente de integridad, resultado local y SHA bajo disclosure.
    No se presenta como firma digital. No se descarga ni genera al montar la página.
29. **Extracción:** ProductApp monta las tres rutas sin App/Diagnóstico; reutiliza servicios y
    componentes canónicos. No se reescribió App.tsx ni se rediseñó Diagnóstico en este slice.
30. **APIs:** cero endpoints nuevos y cero contratos económicos nuevos. Reutilizados matrix,
    commercial-line/exchange, readiness-board/work, proposal-readiness, versions/composition/exports.
    Ruta local comercial admite Scope explícito. Sin nuevo dominio o proveedor.
31. **Async:** useRead invalida generaciones; editores con key Tender/Scope/versión; cambio de
    Tender remonta las vistas. Inspección de versión comprueba ID/Tender y generación.
    Tests de respuesta tardía comercial A→B, evaluación de captura A→B y versión A→B.
    Los comandos existentes bloquean selección mientras hay una acción pendiente.
32. **No automático:** prueba integrada real ProductApp conserva borrador al cambiar tabs y
    no monta legacy ni hace POST/PATCH. Browser registra sólo el POST de export solicitado;
    sin OCR/Vision/LLM, inicialización, snapshot, importación o generación por navegación.
33. **Backend:** cero cambios de producción y cero cambios de tests backend.
34. **Alembic:** current de licitia_test y heads = `20261023_discovery_079`; cero migraciones.
35. **Dependencias:** cero, package/lock intactos. CDP Node/Chromium y Pillow ya disponibles.
36. **Continuidad:** navy/light, tokens del shell, navegación contextual compacta, tablas y
    detalles progresivos. Sin charts, tarjetas decorativas, métricas ficticias o renombrado interno.
37. **Densidad comercial:** seis columnas, números neutros, scroll contenido y header sticky;
    todos los campos/reglas no se muestran simultáneamente en la tabla principal.
38. **Densidad preparación:** bloqueos primero, detalles de trabajo sólo al seleccionar; sin
    score, gauge, porcentaje arbitrario ni cientos de checks exitosos expandidos.
39. **Densidad propuesta:** tabla compacta, estado textual y detalle de composición/integridad;
    campos largos/diagnóstico secundarios. Artefactos separados de contenido y configuración.
40. **1366×768:** PASS en las tres rutas. Columnas financieras con scroll local; acciones y
    navegación alcanzables. Leer detalles largos requiere scroll vertical, no compresión extrema.
41. **1440×900:** PASS, captura de las tres superficies, sin overflow horizontal global.
42. **1920×1080:** PASS, shell acotado y tabla legible, sin nueva navegación paralela.
43. **Narrow:** 768×900 y 390×844 PASS sin overflow de página; tablas desplazan localmente.
    No certificación móvil para preparar ofertas ni certificación WCAG.
44. **Capturas:** 32 capturas nuevas bajo `backend/reports/ui_r5/browser/`, enumeradas abajo.
    Incluyen cotización ausente, error de importación, draft/frozen/stale, archivos y retry.
    Fixtures sintéticas aisladas; no datos del usuario ni consultas a portales/proveedores.
45. **Hoja de contacto:** `backend/reports/ui_r5/browser/contact-sheet.png`, 1800×1040,
    seis estados. Inspeccionada visualmente; pendiente aprobación humana, no versionada.
46. **Focused:** 77 passed /12 archivos. Catorce pruebas nuevas (13 producto +1 routing)
    amplían las regresiones comerciales/readiness/propuesta existentes. Comando exacto abajo.
47. **Frontend completo:** `npm --prefix frontend test` → 261 passed /32 archivos.
    Warning preexistente: key duplicada `a` en fixture de DocumentViewer.test, sin cambios
    a esa prueba en UI-R5. No excepciones de runtime en browser.
48. **Browser UI-R5:** 11 grupos PASS, 32 capturas; tres desktops y dos narrow para cada ruta.
    Datos API interceptados, control de flujo/visual verificados; no calidad semántica ni
    generación binaria real mediante mocks. La API real se valida por separado.
49. **Backend/API:** 101 passed,6 warnings,437.24s; seis archivos canónicos comerciales,
    snapshots, versiones y exports. Warnings python_multipart y Swig. Sólo licitia_test.
    No opt-ins de proveedores reales ni suite completa ajena al cambio de frontend.
50. **UI-R4 browser:** script original sin modificar → 11 grupos PASS.
51. **UI-R3 browser:** script original sin modificar → 12 grupos PASS.
52. **UI-R2 browser:** script original sin modificar → 13 grupos PASS.
    Las tres regresiones se ejecutaron secuencialmente, con páginas limpias del perfil aislado,
    evidencia nueva bajo ui_r5; no sobrescribieron capturas/reportes históricos.
53. **Build/typecheck:** ambos PASS; JS607.32kB, CSS32.33kB. Persiste warning bundle >500kB;
    no se añadió dependencia ni se amplió alcance para code splitting.
54. **Compile/diff:** intérprete backend obligatorio `-m compileall -q backend/app backend/scripts backend/tests`
    PASS; `git diff --check` PASS; índice vacío. Lista de archivos nueva/modificada abajo.
55. **Archivos exactos:** 20 de UI-R5, incluidos este reporte y ADR-0039; lista abajo.
    Ningún backend/env/DB/binario/reporte local forma parte de los cambios versionables.
56. **Límites:** editor de lote conserva su UI funcional extensa en sección secundaria;
    tabla principal requiere actualización después de lote. Drafts/File/UUID pendiente viven
    en memoria; refresh completo puede perderlos. Historial/composición están paginados;
    matriz conserva lectura completa del contrato actual, sin promesa de escala ilimitada.
    No fecha/vigencia de quote ni fechas de versión ausentes en DTO. Browser usa fixtures;
    no prueba calidad semántica o certificación contractual. No se inspeccionó Tender #002
    ni se repitió el barrido histórico5941: su evidencia anterior no es una ejecución nueva.
57. **Gates A–S:** PASS técnico para este alcance, con límites descritos y tabla abajo.
    La aprobación arquitectónica/visual humana de UI-R5 permanece pendiente.
58. **Listo para commit:** sí para revisión; sin stage/commit/push de UI-R5. Permanecen
    modificaciones/nuevos archivos del slice y los directorios de reportes locales históricos.
59. **UI-R6 recomendado:** integrar presentación existente de Mi empresa/biblioteca de evidencia,
    Reportes y Configuración, con acciones locales y navegación coherentes; preservar aislamiento
    por empresa/Tender, provenance, confidencialidad y autoridad humana. Sin auth, proveedores,
    DI, nuevos scores ni dashboard económico global. Pulido transversal final en UI-R7.

## Gates

| Gate | Resultado y evidencia |
|---|---|
| A | PASS matriz/API canónicas, pruebas de lectura y routing |
| B | PASS markup/margen distintos; strings, sin fórmula JS |
| C | PASS fuente/origen/captura/cotización visibles |
| D | PASS sólo campos reales; sin score ni vigencia inferida |
| E | PASS prioridad canónica y detalle de seguimiento |
| F | PASS sin porcentaje de preparación |
| G | PASS estado consultado y captura histórica separados |
| H | PASS draft/frozen/cambios posteriores y binding fijo |
| I | PASS controles frozen deshabilitados y texto de inmutabilidad |
| J | PASS receipts reales de API, cuatro formatos;101 API |
| K | PASS generación explícita/retry conserva solicitud |
| L | PASS routing sin writes/análisis; browser registra acción explícita |
| M | PASS tres casos tardíos y guard de ownership/generación |
| N | PASS cero expansión backend/dominio |
| O | PASS079 sin migración |
| P | PASS fixtures sólo en tests/harness, cero imports runtime |
| Q | PASS1366 y scroll contenido |
| R | PASS tokens/shell/nav/proporciones; revisión humana pendiente |
| S | PASS77focused/261frontend/101API/11R5+11R4+12R3+13R2 browser |

## Comandos de validación

Desde raíz:

```sh
npm --prefix frontend test -- src/components/CommercialProduct.test.tsx src/components/FinancialRouting.test.tsx src/components/CommercialLine.test.tsx src/components/CommercialMatrix.test.tsx src/components/CommercialSpreadsheet.test.tsx src/components/CommercialAuditDetails.test.tsx src/components/ReadinessBoard.test.tsx src/components/ReadinessWork.test.tsx src/components/ProposalReadiness.test.tsx src/components/ProposalVersions.test.tsx src/components/ProposalComposition.test.tsx src/components/ProposalExports.test.tsx
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run typecheck
node frontend/scripts/ui-r5-browser.mjs backend/reports/ui_r5/browser
node frontend/scripts/ui-r4-browser.mjs backend/reports/ui_r5/r4_regression
node frontend/scripts/ui-r3-browser.mjs backend/reports/ui_r5/r3_regression
node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r5/r2_regression
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests
git diff --check
```

Desde backend:

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test LICITIA_DISCOVERY_REPORT_ROOT=reports/ui_r5 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_commercial_matrix.py tests/test_commercial_exchange.py tests/test_readiness_board.py tests/test_proposal_readiness.py tests/test_proposal_versions.py tests/test_proposal_exports.py -q -k 'not opt_in'
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
```

Vite localhost5181 y Chromium CDP9331 con perfil aislado. El harness sólo intercepta API
local con contratos sintéticos; no reutiliza cookies/perfiles del usuario. Las repeticiones
del harness durante desarrollo corrigieron selectores y comprobaron el refresco del editor;
no fueron ejecuciones ciegas ni alteraron datos/históricos de producto.

## Archivos del commit UI-R4 (22)

- `docs/adr/0038-requirements-compliance-scope-product-ui.md`
- `docs/roadmap.md`
- `docs/ui-r4-implementation.md`
- `frontend/scripts/ui-r4-browser.mjs`
- `frontend/src/App.tsx`
- `frontend/src/ProductApp.tsx`
- `frontend/src/api/engineering.ts`
- `frontend/src/api/engineeringTypes.ts`
- `frontend/src/components/ComplianceView.tsx`
- `frontend/src/components/DocumentViewer.test.tsx`
- `frontend/src/components/DocumentViewer.tsx`
- `frontend/src/components/Engineering.test.tsx`
- `frontend/src/components/ItemsView.tsx`
- `frontend/src/components/RequirementsView.tsx`
- `frontend/src/components/TenderDocumentsView.tsx`
- `frontend/src/components/TenderProductViews.tsx`
- `frontend/src/components/engineering.css`
- `frontend/src/components/useRead.ts`
- `frontend/src/test/engineeringFixtures.ts`
- `frontend/src/ui/Shell.test.tsx`
- `frontend/src/ui/engineeringPresentation.ts`
- `frontend/src/ui/routes.ts`

## Archivos UI-R5 (20, sin stage)

- `docs/adr/0039-commercial-readiness-proposal-product-ui.md`
- `docs/roadmap.md`
- `docs/ui-r5-implementation.md`
- `frontend/scripts/ui-r5-browser.mjs`
- `frontend/src/ProductApp.tsx`
- `frontend/src/components/CommercialLine.tsx`
- `frontend/src/components/CommercialProduct.test.tsx`
- `frontend/src/components/CommercialView.tsx`
- `frontend/src/components/FinancialRouting.test.tsx`
- `frontend/src/components/ProposalComposition.tsx`
- `frontend/src/components/ProposalExports.tsx`
- `frontend/src/components/ProposalReadiness.tsx`
- `frontend/src/components/ProposalVersions.tsx`
- `frontend/src/components/ReadinessView.tsx`
- `frontend/src/components/ReadinessWork.tsx`
- `frontend/src/components/commercialProduct.css`
- `frontend/src/test/commercialProductFixtures.ts`
- `frontend/src/ui/Shell.test.tsx`
- `frontend/src/ui/commercialPresentation.ts`
- `frontend/src/ui/routes.ts`

## Capturas exactas

- `01-commercial-matrix.png`
- `02-commercial-detail.png`
- `03-quote-provenance.png`
- `04-missing-quote.png`
- `04-quote-edit.png`
- `05-import-export.png`
- `05b-import-local-error.png`
- `07-readiness-blockers.png`
- `08-readiness-warnings.png`
- `09-readiness-ready.png`
- `10-readiness-detail.png`
- `11-proposal-draft.png`
- `11b-human-composition.png`
- `12-proposal-frozen.png`
- `13-proposal-stale.png`
- `14-proposal-artifacts.png`
- `15-export-error-retry.png`
- `16-comercial-1366.png`
- `16-comercial-1440.png`
- `16-comercial-1920.png`
- `16-comercial-390.png`
- `16-comercial-768.png`
- `16-preparacion-1366.png`
- `16-preparacion-1440.png`
- `16-preparacion-1920.png`
- `16-preparacion-390.png`
- `16-preparacion-768.png`
- `16-propuesta-1366.png`
- `16-propuesta-1440.png`
- `16-propuesta-1920.png`
- `16-propuesta-390.png`
- `16-propuesta-768.png`
- `contact-sheet.png`

## Evidencia local

`backend/reports/ui_r5/`: logs de comandos, Alembic, resultados de navegador,
hashes de fuentes y validation.json. Sin stage ni commit de esos artefactos.
No se modificaron reportes históricos ni originales. Detener antes de UI-R6.

## Addendum final — sidebar global contraíble (2026-10-24)

Refinamiento final del mismo UI-R5, sin UI-R5.1. Comercial, Preparación y Propuesta
conservan aprobación visual del Product Owner; el conjunto permanece **sin stage,
commit ni push**, pendiente revisión final. HEAD `0915e83a4173a14653df089b302d30aa2c7a7a13`.

1. **Ancho expandido:**260px, navegación e identidad RX23 TuScope completas.
2. **Ancho contraído:**64px en desktop≥1024px, iconos y expandir alcanzables.
3. **Persistencia:** localStorage, clave `tuscope.sidebar.desktop`; valores `expanded` y
   `collapsed`. Sobrevive rutas, cambios de Tender y reload; no DB/backend.
4. **Default/fallback:** expandido si no hay preferencia válida. Storage inaccesible no
   impide alternar en la sesión; si el navegador deniega almacenamiento no se promete
   persistencia entre recargas. Corrupto/desconocido no activa un estado estrecho inesperado.
5. **Marca:** RX23 TuScope expandido; RX23 tipográfico contraído. Sin nuevo logo/imagen.
6. **Accesibilidad:** Button nativo compartido, nombres exactos Contraer menú/Expandir menú,
   title y aria-expanded. Cada destino tiene aria-label y title; SVG decorativo aria-hidden.
   No existía icon pack: SVG en línea sin dependencia. Enter y foco visible comprobados.
7. **Ruta activa:** aria-current, fondo/navy y borde claro existentes; íconos y utilidades
   conservados. Un solo nav global; ocho enlaces Tender horizontales idénticos antes/después.
8. **Ganancia1366:** workspace1106→1302px, tabla comercial1058→1254px: **+196px**.
   En1920, el máximo útil1600→1796px recupera los mismos196 sin modificar el modo expandido.
9. **Comercial antes/después:** mismas seis columnas, mismos datos/estado/selección. La
   comparación usa estado idéntico; no se añadieron columnas ni metadata. Costo sin guardar
   y filtro conservados; test de identidad del input, no sólo igualdad visual del texto.
10. **Documentos:** PDF775→971px; registro250→250px. Se conserva el iframe/blob, documento y
    selector/petición de página7. El plugin PDF mantiene sus límites de sincronización UI-R3;
    la prueba no afirma sincronización interna con la página física del plugin.
11. **Requisitos:** tabla/filtros conservados; captura contraída. Cumplimiento y Partidas
    también capturados, sin cambios de jerarquía, fuente, columnas o información visible.
12. **Propuesta:** versión, campo humano sin guardar y acciones permanecen. Preparación
    conserva orden y layout. Sólo copy autorizado en integridad: Ver detalle, SHA adentro.
    Verificación al generar recibida del servidor sigue distinta de verificación actual;
    no se inventa un Verificado por archivo.
13. **Conservación:** tests reales ProductApp para Tender/comercial, versión/propuesta y
    PDF/página. Tests del shell cubren navegación, Tender diferente, reload, valor inválido,
    teclado, storage denegado y no remount. No cambios de keys/handlers de dominio.
14. **Solicitudes:** cero lecturas adicionales al alternar, verificadas por conteo API en
    pruebas de producto y CDP. Cero writes en el harness de sidebar; sin análisis/generación.
15. **Narrow:**≤1023 conserva botón Menú y panel responsive existente. Contraer desktop
    no modifica ese flujo: etiquetas completas, Escape/foco y cierre al navegar; captura390.
    Sin transición/animación, por lo que no hay movimiento que desactivar en reduced-motion.
16. **Focused shell:**25 passed /3 archivos (16 Sidebar,6 Shell,3 SidebarState).
    **Focused UI-R5:**77 passed /12 archivos, comando original del reporte anterior.
17. **Frontend completo nuevo:**280 passed /34 archivos. El warning preexistente de key `a`
    en fixture de DocumentViewer sigue registrado; no se modificó esa prueba ni ese módulo.
18. **Browser nuevo:** sidebar10 grupos PASS,9 capturas y comparación. UI-R5 original11,
    UI-R4 original11, UI-R3 original12, UI-R2 original13 grupos PASS; scripts secuenciales,
    páginas nuevas en perfil aislado. La comprobación1920 adicional sólo afecta modo contraído;
    regresiones originales usan el modo expandido. Todas las evidencias nuevas van al root
    `backend/reports/ui_r5_sidebar/`; originales ui_r2/r3/r4/r5 intactos.
19. **Build/typecheck/diff:** PASS. JS608.86kB,CSS33.38kB; persiste warning >500kB, sin
    optimización/dependencia fuera de alcance. `git diff --check` PASS; índice vacío.
20. **Archivos adicionales exactos (9 respecto del baseline UI-R5 previo):**
    `frontend/src/ui/AppShell.tsx`, `frontend/src/ui/shell.css`,
    `frontend/src/ui/Sidebar.test.tsx`, `frontend/src/components/SidebarState.test.tsx`,
    `frontend/scripts/ui-r5-sidebar-browser.mjs`,
    `frontend/src/components/ProposalExports.tsx` (copy secundario),
    `docs/adr/0039-commercial-readiness-proposal-product-ui.md`,
    `docs/roadmap.md`, `docs/ui-r5-implementation.md`.
    Total acumulado UI-R5:25 archivos versionables, todos sin stage.
21. **Dependencias añadidas:**0; package/lock intactos. Sin icon/tooltip package, CDN o fuente.
22. **Backend:**0 cambios de producción/tests. No se repitieron101 API ni compileall por este
    refinamiento de presentación; son evidencia previa, no ejecuciones nuevas de este addendum.
23. **Alembic:** comprobación de sólo lectura de licitia_test nueva = `20261023_discovery_079`.
    Cero migraciones, cambios manuales o fallback de esquema.
24. **Listo para commit:** sí para revisión final del conjunto; **no autorizado todavía**.
    Gates A–L abajo. Sin stage/commit/push; no se inició UI-R6.

### Gates finales A–L

| Gate | Resultado / evidencia |
|---|---|
| A alternar | PASS controles nativos + teclado +CDP |
| B persistencia | PASS rutas/Tender/reload/invalid/storage tests |
| C ancho real | PASS+196 tabla/workspace/PDF y escritorio ancho |
| D navegación | PASS iconos+nombres/title, utilidades conservadas |
| E activo | PASS aria-current y borde/fondo existentes |
| F Tender | PASS identidad y contexto reales conservados |
| G estado | PASS inputs, filtro, selección/iframe y versión no remontan |
| H refetch | PASS cero solicitudes por alternar; cero writes en harness |
| I narrow | PASS drawer original, etiquetas y navegación390 |
| J superficies | PASS sin rediseño; aprobación visual previa preservada; revisión final pendiente |
| K regresión | PASS25shell/77focused/280frontend/10sidebar+11R5+11R4+12R3+13R2browser |
| L alcance | PASS backend0/schema079/dependencias0 |

### Reproducción y capturas adicionales

```sh
npm --prefix frontend test -- src/ui/Sidebar.test.tsx src/ui/Shell.test.tsx src/components/SidebarState.test.tsx
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run typecheck
node frontend/scripts/ui-r5-sidebar-browser.mjs backend/reports/ui_r5_sidebar/browser
node frontend/scripts/ui-r5-browser.mjs backend/reports/ui_r5_sidebar/r5_regression
node frontend/scripts/ui-r4-browser.mjs backend/reports/ui_r5_sidebar/r4_regression
node frontend/scripts/ui-r3-browser.mjs backend/reports/ui_r5_sidebar/r3_regression
node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r5_sidebar/r2_regression
git diff --check
```

Root de capturas: `backend/reports/ui_r5_sidebar/browser/`:

- `01-commercial-expanded-1366.png`
- `02-commercial-collapsed-1366.png`
- `03-documents-collapsed-1366.png`
- `04-requirements-collapsed-1366.png`
- `04b-compliance-collapsed-1366.png`
- `04c-items-collapsed-1366.png`
- `04d-readiness-collapsed-1366.png`
- `05-proposal-collapsed-1366.png`
- `06-narrow-drawer-390.png`
- `expanded-vs-collapsed.png`:1800×560, comparación del mismo estado comercial.

Capturas revisadas visualmente. Datos exclusivamente sintéticos, respuestas API interceptadas
localmente y PDF sintético heredado del harness UI-R3; sin documentos del usuario ni portales.
No es certificación WCAG/semántica. Los20 hashes del baseline UI-R5 fueron verificados antes
de editar; el barrido histórico5941 no se repitió. Logs, mediciones, requests, hashes actuales
y validation.json permanecen locales, fuera del conjunto versionable.
