# UI-R3 — Licitaciones, Resumen y Documentos

Estado: implementado y validado, listo para revisión arquitectónica y visual.
**Runtime sin stage/commit/push.** MVP-01–10 permanecen cerrados.
[Diseño aprobado](ui-r3-architecture-design.md), [ADR-0037](adr/0037-tender-documents-product-ui.md).
Los documentos de diseño conservan su texto propuesto como artefactos de la revisión aceptada;
esta entrega registra su implementación y las correcciones expresamente autorizadas.

## Reporte final

1. **Commit documental:** `ed3e1a2ce208f761de4869eae8e252477125afa8`,
   `docs(ui): define tender documents product experience`. Creado antes del runtime, sin push.
2. **HEAD resultante:** mismo SHA; padre `1d73dcd1738162ed5e0edbf2993a9415d247f170`, UI-R2/UI-R2.1 aceptado.
3. **Archivos comprometidos:** sólo `docs/ui-r3-architecture-design.md` y
   `docs/adr/0037-tender-documents-product-ui.md`. Ningún reporte/imagen/dato local incluido.
4. **Licitaciones:** header compacto, Nueva licitación, filtros y tabla. Sin galería, hero ni KPIs.
5. **Columnas (5):** Procedimiento/Licitación, Perfil institucional, Estado, Registro actualizado,
   Acción. No origen inferido, UUID, readiness o monto. Perfil es texto literal, no catálogo institucional.
6. **Búsqueda/filtro:** referencia/nombre case-insensitive y estado registrado exacto sobre toda
   la respuesta GET `/tenders`. Orden updated_at DESC/ID; conteo N de M locales. Sin filtros/API nuevos.
7. **Creación:** sólo título obligatorio; referencia y perfil opcionales bajo disclosure;
   POST `/tenders` canónico. ID del201 abre Resumen; busy evita doble submit normal. Fallo incierto
   conserva borrador y exige verificar lista, sin retry automático ni garantía de idempotencia inexistente.
8. **Vacío:** “Aún no hay licitaciones.” con Nueva licitación/Discovery. Error API no equivale a vacío.
9. **Resumen:** datos del registro + expediente documental + Ir a Documentos. Ocho tabs existentes,
   sin navegación paralela ni duplicación de Inicio.
10. **Fuentes exactas:** GET `/tenders/{id}` → referencia, perfil, estado, created_at/updated_at;
    GET `/tenders/{id}/documents` → documents.length, is_current true/false. Son revisiones registradas,
    no archivos físicamente verificados ni familias contractuales. Entrada directa hace sólo esos dos GET.
11. **Omisiones deliberadas:** no readiness global, cumplimiento, progreso, fechas contractuales,
    URL/origen Discovery reconstruidos, costos, charts ni consultas por módulo para decorar Resumen.
12. **Atención:** cantidad de revisiones con TEXT_EXTRACTION_FAILED/TEXT_EXTRACTION_PARTIAL/NO_NATIVE_TEXT,
    aviso explícito y acceso a Documentos. No se transforma en obligación ausente ni en checklist certificado.
13. **Documentos:** registro a ancho completo; al seleccionar, lista240–250px + visor flexible.
    Contexto e integridad plegables; sin tres paneles fijos. Importación se abre explícitamente.
14. **Registro (4 columnas):** Archivo, Revisión, Texto/páginas registradas, Acción. Selección cambia
    a lista compacta usando los mismos UUID. Filtros por nombre y revisiones Todas/Actuales/Anteriores.
15. **Revisiones:** Actual/Versión anterior + número y lineage técnico disponible. Revisiones
    anteriores permanecen visibles y abribles; is_current no certifica vigencia contractual.
16. **Importación:** selección local vacía → archivos pendientes → Importar archivos seleccionados.
    Uno o varios archivos, sin ejecutar análisis. Cada archivo viaja en su propia solicitud multipart
    al endpoint canónico existente, conservando File y webkitRelativePath; no nueva API.
17. **Duplicados:** DUPLICATE muestra “Contenido idéntico ya registrado”; no ofrece revisión inapropiada.
    El backend conserva UNIQUE Tender+SHA y almacenamiento inmutable.
18. **NAME_CONFLICT:** decisión explícita por archivo, independiente o nueva revisión; esta última
    exige target vigente del mismo Tender y mismo nombre. Etiqueta humana con nombre/revisión/fecha;
    confirmación nativa antes del POST, Cancelar no resuelve otros archivos.
19. **Correlación múltiple:** crypto.randomUUID por entrada, `clientImportId` local como key/lock,
    File inmutable retenido en esa entrada. Cada respuesta se cierra sobre esa identidad; el request
    contiene un solo archivo y se valida resultado único/nombre. Nunca posición/orden de respuesta
    ni filename como identidad del lote. Retry conserva ID y File; B→A probado con targets/bytes distintos.
20. **Visor:** GET canónico `/tenders/{id}/documents/{document_id}/content`, responseType blob,
    validación de firma PDF, URL temporal local revocada al cambiar/reintentar/desmontar. iframe nativo
    muestra bytes del original, no un render derivado. Sin SDK/dependencia nueva ni `file://`.
21. **Página:** selector de páginas reales devueltas por GET `/pages`, texto separado y petición
    `#page=N` al PDF. No se afirma sincronización con la posición/zoom interna del plugin. Zoom,
    imprimir/guardar son controles nativos; abrir original usa URL servida por el backend y revisión exacta.
22. **No-PDF:** “Vista previa no disponible” + metadata/texto derivado disponible. Sin visor Office,
    descarga genérica o conversión inventados: el contrato content actual sólo sirve PDF.
23. **Error/retry:** páginas y PDF independientes con mensajes claros y Volver a consultar.
    Reabrir visor sólo vuelve a leer el original. Registro y selección se conservan. No reload global,
    no extracción como retry de lectura. Firma/respuesta de páginas malformadas fallan de forma cerrada.
24. **Procedencia:** nombre literal, MIME/tamaño, importado, revisión/actual-anterior; UUID/parent/SHA
    bajo Detalles técnicos. No paths visibles. Registro local no demuestra presencia física actual.
    TenderRead/documentos no exponen origen manual/Discovery: no se fabrica; receipts/contexto público
    permanecen consultables en Discovery. Referencias públicas nunca se mezclan como archivos locales.
25. **Refactor App:** se retiran tipos/estado/handlers de importación inseguros y su formulario;
    se reutiliza DocumentImports también en Diagnóstico. Se añade guard de páginas legacy. ProductApp
    monta vistas nuevas sin cargar el App completo en lista/Resumen/Documentos. Se conservan App,
    anclas y funciones posteriores, sin rediseñarlas. WorkspaceFlow agrega modo processingOnly y active.
26. **Ownership de requests:** lista posee sus lecturas/creación; TenderProductWorkspace posee registro
    y documentos; visor por key Tender+Document posee páginas/PDF. Core y contexto legacy separados.
    La selección validada conserva `licitia_selected_tender_id`; Diagnóstico recibe el Tender correcto.
27. **Respuestas tardías:** generation/liveness por request; limpiar loading/error/página/texto al
    cambiar documento; desmontar key anterior y revocar blob. El test A retrasado/B actual resuelve
    A al final y verifica que no aparece su texto ni iframe. Guard equivalente en páginas legacy.
28. **Cross-Tender:** wrappers verifican TenderRead.id, document.tender_id y pages.document_id;
    visor rechaza contexto ajeno antes de pedir páginas/contenido. IDs codificados como segmentos,
    sin URL arbitraria. Ownership/path safety backend intactos y cubiertos por regresión real de API.
29. **No auto-analysis:** sólo GET al abrir/listar/ver, comprobado en tests y captura de requests CDP.
    Process/retry siguen acciones humanas AVAILABLE_ONLY; OCR/Vision/LLM no se activan. Herramientas
    explícitas anteriores quedan en Diagnóstico. processingOnly evita montar Requisitos/Comercial/
   Propuesta/revisión Scope para representar estado; polling sólo en superficie activa y PROCESSING.
30. **Backend:** cero cambios de producción o tests backend. Sin dominio/API nuevo ni corrección servidor.
31. **Migraciones:** cero. Alembic current test y heads nuevos = `20261023_discovery_079`.
32. **Dependencias:** cero; package y lock intactos. PDF nativo, CDP Node y Pillow ya disponibles.
33. **Continuidad visual:** shell navy/light y tokens/components UI-R1; densidad compacta/table-first,
    acciones primarias azules, fuentes técnicas secundarias. Stitch NuevaLicita/VisorDoctos consultados
    como referencia; no se copian pipeline automático, KPIs ni highlights ficticios.
34. **1366×768:** PASS, visor775px de ancho en fixture, lista utilizable y controles alcanzables;
    scroll vertical necesario para leer el documento completo. No overflow horizontal global.
35. **1440×900:** PASS, mayor espacio de lectura, separación registro/visor y foco visibles.
36. **1920×1080:** PASS, main acotado por shell, visor ampliado sin tercer panel fijo.
37. **768×900 y390×844:** PASS sin overflow global; registro acotado antes del visor, menú y tabs
    alcanzables, scroll interno/vertical explícito. No certificación de uso móvil para preparar ofertas.
38. **Capturas exactas** bajo `/Users/ceciliavalencia/LiticIA/backend/reports/ui_r3/browser/`:
    `01-licitaciones.png`, `02-empty.png`, `03-create.png`, `04-resumen.png`,
    `05-resumen-attention.png`, `06-documents-viewer.png`, `07-current-revision.png`,
    `08-previous-revision.png`, `09-conflict.png`, `10-multiple-conflicts.png`,
    `11-viewer-loading.png`, `12-viewer-error.png`, `13-non-pdf.png`,
    `14-documents-1366.png`, `14-documents-1440.png`, `14-documents-1920.png`,
    `14-documents-768.png`, `14-documents-390.png`. Fixtures exclusivamente de prueba aislada.
39. **Contact sheet:** mismo directorio, `contact-sheet.png` (1800×1000), seis estados; no versionado.
40. **Focused nuevo:** `npm --prefix frontend test -- src/api/tenders.test.ts src/components/TenderRouting.test.tsx src/components/DocumentImports.test.tsx src/components/DocumentViewer.test.tsx src/components/TenderProductViews.test.tsx src/components/WorkspaceFlow.test.tsx src/ui/Shell.test.tsx`
    → **47 passed /7files**. Cubre correlación/reverse order/cancel/retry, stale response, guard ownership,
    URL/malformed, creación, lecturas mínimas, drafts, polling activo y regresión del shell/Workspace.
41. **Frontend completo nuevo:** `npm --prefix frontend test` → **225 passed /29files**.
    Incluye Inicio/Discovery y todos los módulos posteriores. La prueba shell transitoria pasa a
    comenzar en Partidas (legacy) para conservar su comprobación de no remount de ese workspace;
    las rutas core reales se prueban aparte con ProductApp, sin mocks de las vistas nuevas.
42. **Browser/E2E nuevo:** `node frontend/scripts/ui-r3-browser.mjs backend/reports/ui_r3/browser`
    → **12 grupos PASS**,18capturas. Creación manual201→Resumen, PDF binario sintético real servido
    por fixture, dos conflictos, carga/error/retry, revisiones, cinco tamaños, teclado/foco/labels,
    downstream/Diagnóstico, cero excepciones/cero análisis. Regresión original UI-R2:
    `node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r3/ui_r2_regression` → **13 grupos PASS**.
    Scripts ejecutados secuencialmente; nunca DB producto/portales ni perfiles del usuario.
43. **Backend documental nuevo:** desde backend, `DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test LICITIA_DISCOVERY_REPORT_ROOT=reports/ui_r3 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_tenders.py tests/test_documents.py -q -k 'not opt_in'`
    → **127 passed,1deselected,7warnings,38.55s**. Excluido live Ollama; mocks de proveedores no
    prueban calidad real. Warnings python_multipart, Swig y ccache. Primer intento sandbox sin
    conexión a PostgreSQL dio errores de setup; al habilitar acceso local pasó el comando idéntico.
44. **Build/typecheck nuevos:** comandos npm existentes PASS; JS550.26kB,CSS25.96kB. Warning>500kB
    conocido, sin optimización ajena ni dependencia nueva.
45. **Compile/diff:** intérprete backend obligatorio `-m compileall -q backend/app backend/scripts backend/tests`
    desde raíz PASS; `git diff --check` PASS. Índice runtime vacío.
46. **Históricos:** no se repitió aquí el barrido5941;5941/5941 es evidencia heredada UI-R2.1, no
    nueva. Se preservaron los reportes anteriores y no se inspeccionó contenido ciego. Pruebas de
    navegador exclusivamente sintéticas; no nuevo Attempt ni tuning. Hashes UI-R2 históricos se
    verifican en el cierre de evidencia acotada, sin sobrescribir manifiestos.
47. **Archivos runtime/documentación exactos:** lista abajo. Ningún artefacto local/backend/env/DB
    forma parte del conjunto para revisión de código.
48. **Limitaciones:** archivo PDF se carga como blob completo (memoria proporcional a su tamaño),
    plugin nativo dependiente del navegador; error interno del plugin no siempre detectable.
    Sin Office/download genérico, edición Tender, catálogo institucional, lineage gráfico o reverse-link
    Discovery inventado. Drafts/File pendientes viven en memoria; refresh requiere confirmación y puede
    perderlos. Cambiar Tender con pendientes requiere confirmación; en busy se rechaza. Legacy mantiene
    sus lecturas amplias al visitarlo. No certificación WCAG ni semántica mediante fixtures. No blockers
    funcionales detectados en gates ejecutados; pendiente aceptación humana visual/arquitectónica.
49. **Gates A–Q:** PASS con evidencia y límites en matriz siguiente.
50. **Listo para commit:** sí, sujeto a revisión/aceptación; runtime sin stage/commit/push.
51. **UI-R4 recomendado exacto:** integrar visualmente Requisitos/Requested Evidence, Cumplimiento,
    Partidas/alternativas/revisión Scope y Ver fuente al contexto documental. Preservar autoridad
    humana, provenance/versiones/conflictos y Quantity read-only; sin cambiar semántica DI, revisar
    precios o rediseñar Comercial/Preparación/Propuesta. No implementado en esta entrega.

## Archivos exactos de implementación

Modificados:

- docs/roadmap.md
- frontend/src/App.tsx
- frontend/src/ProductApp.tsx
- frontend/src/components/WorkspaceFlow.tsx
- frontend/src/components/WorkspaceFlow.test.tsx
- frontend/src/ui/Shell.test.tsx

Nuevos:

- docs/ui-r3-implementation.md
- frontend/src/api/tenders.ts
- frontend/src/api/tenders.test.ts
- frontend/src/components/TenderProductViews.tsx
- frontend/src/components/TenderProductViews.test.tsx
- frontend/src/components/TenderRouting.test.tsx
- frontend/src/components/TenderDocumentsView.tsx
- frontend/src/components/DocumentViewer.tsx
- frontend/src/components/DocumentViewer.test.tsx
- frontend/src/components/DocumentImports.tsx
- frontend/src/components/DocumentImports.test.tsx
- frontend/src/components/tenderDocuments.css
- frontend/scripts/ui-r3-browser.mjs

## Gates A–Q

| Gate | Resultado / evidencia |
|---|---|
| A lista | PASS tabla5columnas, búsqueda/estado, browser |
| B creación | PASS POST canónico y201ID; focused+browser |
| C Resumen | PASS sólo registro/documentos, atención determinista |
| D workspace | PASS registro/lista+visor/contexto agrupado |
| E visor | PASS PDF binario original en iframe nativo |
| F revisiones | PASS UUID/actual/anterior, backend revision tests |
| G decisión humana | PASS confirmación/cancel, targets canónicos |
| H correlación | PASS clientImportId/File, dos conflictos B→A |
| I async | PASS A tardío no sustituye B, guard por contexto |
| J lectura | PASS cero análisis por navegación, explicit process/retry |
| K backend | PASS cero cambios;127API |
| L esquema | PASS079 sin migración |
| M datos | PASS fixtures sólo tests/script, runtime API real |
| N downstream | PASS rutas/anclas legacy, regresión frontend y browser |
| O visual | PASS tokens/shared shell/Stitch, inspección de capturas |
| P1366 | PASS775px de visor, scroll contenido |
| Q regresión | PASS225frontend,127backend,12R3+13R2browser,build/types/compile/diff |

## Evidencia local

`backend/reports/ui_r3/`: logs, hashes de archivos, validación, capturas/resultados R3 y
regresión R2. Imágenes, datos sintéticos y reportes no stageados ni comprometidos.
Sólo el commit de diseño está autorizado y creado; no push. Detener antes de UI-R4.
