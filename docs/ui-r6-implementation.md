# UI-R6 — Mi empresa, Reportes, Configuración y Diagnóstico

Estado: implementado y validado; pendiente revisión arquitectónica y visual humana.
**UI-R6 sin stage, commit ni push.** MVP-01–10 permanecen cerrados; UI-R7 no implementado.
[Inventario previo y decisión ADR-0040](adr/0040-global-support-product-ui.md).

## Reporte final

1. **UI-R5 commit:** `de29deb3306d261dc40e9e5c15a4617ee5666748`,
   `feat(ui): implement commercial readiness proposal and collapsible sidebar`.
   Se verificaron25/25 hashes aceptados contra evidencia final antes de staging explícito.
2. **HEAD:** mismo SHA; padre `0915e83a4173a14653df089b302d30aa2c7a7a13`. Sin push.
   Ningún commit UI-R6, sin reescribir historia. Los reportes anteriores conservan su estado
   histórico al momento de entrega; roadmap registra la aceptación y commit posteriores.
3. **UI-R5 comprometido:**25 archivos exactos en apéndice. Sólo implementación/pruebas/docs;
   ningún reporte, screenshot, DB, env o artefacto generado.
4. **Mi empresa:** selector, datos generales concisos, registro de documentos en tabla,
   detalle contextual, metadatos/evidencia/manual bajo disclosures. Un solo modelo de storage.
5. **Campos:** nombre, razón social y RFC recibidos de Company; creación explícita con campos
   existentes. Selección local reutiliza `licitia_selected_company_id`. Sin CRM, score o %.
6. **Biblioteca:** cinco columnas: Documento, Categoría registrada, Fecha de vigencia,
   Revisión/estado, Acción. Búsqueda local por nombre/etiqueta e incluir archivados; conteo
   de revisiones registradas, sin inferir familias ni presencia física actual. IDs/SHA sólo
   en detalle; paths nunca se presentan en la biblioteca nueva.
7. **Vigencia:** expiration_date literal comparada con fecha local. Sin fecha de vigencia,
   Fecha registrada vencida o Vigencia registrada hasta; fecha inválida→revisión.
   No se infiere vigencia del filename ni validez legal/aplicabilidad. No Próximo a vencer:
   el contrato no define ese umbral. Current significa revisión actual en registro.
8. **Evidencia/reuso:** lecturas por documento, declaración, fragmento/página/revisión,
   origen Hallazgo del motor local/Captura humana, estado de análisis,
   revisión humana y freshness separados. Análisis sólo por botón explícito;
   revisar/validar/descartar y captura manual reutilizan APIs existentes. Descartar exige
   nota; evidencia validada no confirma asociación ni cumplimiento universal. Sin proyección
   global de usos: enlace a elegir Tender y consultar Cumplimiento, no fanout por licitación.
9. **Carga:** archivos pendientes seleccionados→envío explícito individual. UUID por entrada,
   File retenido; respuesta única/filename validada para cada request de un archivo.
   Conflicto requiere independiente o revisión actual del mismo nombre/empresa, con
   confirmación. B→A probado con File/target distintos. Duplicado y error locales; retry
   conserva acción/archivo/target. Respuesta perdida exige consultar biblioteca antes de
   repetir. Backend conserva original inmutable, ownership y validaciones.
   Metadatos/archivar/restaurar siguen endpoints canónicos; archivar/restaurar confirmado.
10. **Omisiones:** no módulos vacíos de experiencia/personal/certificaciones, catálogo de
    entidades o verificador fiscal/legal. La evidencia tipada existente sí puede representar
    esos tipos. Sin nuevo visor Office, motor de vigencia ni historial global de usos inventado.
11. **Reportes:** catálogo de5 consultas/flujos disponibles: registro local de licitaciones,
    Comercial Excel/CSV, Preparación/bloqueos, versiones/archivos de propuesta, Discovery
    siguiendo. Son accesos a capacidades reales, no cinco nuevos motores de reporte.
12. **Omitidos:** analytics globales, KPIs financieros, tendencias, consolidaciones de requisitos
    o rentabilidad entre Tenders. Inventario AVAILABLE/DERIVABLE/NOT AVAILABLE/DEFERRED en ADR.
13. **Filtros:** Tender para elegir flujo; búsqueda referencia/nombre y estado registrado para
    registro local. Aplican a la respuesta completa de GET /tenders; sin filtros decorativos,
    consulta readiness por cada Tender o fecha contractual inferida.
14. **Fuentes:** GET /tenders; links a rutas canónicas Comercial/Preparación/Propuesta y
    `#/discovery?view=following`. No datos monetarios globales, proyecciones nuevas ni fanout.
15. **Export:** archivos XLSX/CSV en Comercial, DOCX/XLSX/PDF/ZIP en Propuesta. Abrir catálogo
    no descarga ni genera. Sólo el módulo canónico autoriza/genera/verifica el archivo;
    no se muestra como existente un PDF no generado ni se añade exportador nuevo.
16. **Sin datos:** No hay registros para esta consulta; error no se interpreta como vacío.
    No fake charts/placeholders de métricas ni creación automática de Tender.
17. **Configuración:** fuentes Discovery, acceso a perfiles existentes, preferencia de
    presentación y administración local documentada; Diagnóstico es ruta separada.
18. **Valores configurables:** enabled/áreas ya soportados para fuentes permitidas. Guardar
    PATCH canónico, confirmación local y bloqueo de selección durante envío. No inicia scan.
    Perfiles se editan en Discovery; sidebar se ajusta en su propio control existente.
    Sin editor de paths, variables de entorno, credenciales, modelo/provider o budgets.
19. **Local-first:** distingue documentos locales de consultas externas a portales públicos.
    No habilita IA cloud desde esta pantalla ni afirma que toda configuración administrativa
    posible es exclusivamente local. No expone secretos de entorno.
20. **Fuentes:** PEMEX/CFE desde catálogo actual, habilitación local y áreas. No se equipara
    enabled con disponibilidad del portal; no se consultan portales al montar/guardar.
21. **Compras MX:** Automatización no disponible actualmente; sin editar/habilitar/ejecutar
    desde UI-R6. Guard ID + capability; backend mantiene409, probado con fixtures offline.
    Sin parser nuevo, bypass, PoW, cookies/tokens, navegador de portal o sustitución de datasets.
22. **Diagnóstico:** grupos Sistema, lectura/motor visual, Discovery, datos administrativos no
    expuestos y herramientas avanzadas. Refresco explícito a4 GETs, sin polling/telemetría.
23. **Servicios:** /health, /ocr/providers y /vision/providers existentes. Se muestran sólo
    estado API, conteos OCR, disponibilidad runtime/modelo recibida. Desconocido/fallo es
    No disponible, no cero inventado ni uptime certificado. No arranca/modifica Ollama.
24. **DB/schema:** /health devuelve sólo status ok; no se presenta como chequeo DB/schema.
    Versión backend/runtime, schema, paths y espacio libre no tienen contrato de lectura:
    se documenta ausencia y procedimiento administrativo.079 se verificó para este reporte,
    no se hardcodeó como supuesto estado runtime de la instalación del usuario.
25. **Warnings:** consultas independientes por allSettled; indisponibilidad deja los otros
    resultados consultables. Ningún error de proveedor vacía toda la pantalla.
26. **Detalle:** proyección técnica pequeña/allowlist bajo Ver detalle técnico; no payload
    libre gigante. No se exponen status_reason, base_url ni campos desconocidos recibidos.
27. **Copia:** botón explícito al portapapeles; resumen acotado de estados/contadores, sin
    envío ni upload. Error clipboard local con texto seleccionable; no fallback de telemetría.
28. **Confidencialidad:** allowlist antes de presentar/copiar descarta URLs, paths, credenciales,
    nombres de empresa/documento/Tender, contenido, costos/precios y mensajes libres.
    Pruebas inyectan secretos y comprueban que no llegan a proyección/clipboard. Compartir
    el resumen es decisión humana; no existe transmisión automática a RX23.
29. **Extracción:** ProductApp monta CompanyView/ReportsView/SettingsView/DiagnosticsView.
    No fue necesario reescribir App.tsx: la biblioteca ya estaba separada. El componente
    heredado se conserva para App no embebido. Workspace técnico embebido se monta sólo
    al abrir herramientas explícitamente; cerrar/ocultar conserva estado. El polling preexistente de estado se limita al workspace activo, sin nuevo polling global.
    UI-R1–R5 Tender y sidebar conservados, sin rediseñar módulos cerrados.
30. **Wrappers:** company.ts centraliza tipos/lecturas y comandos empresariales; valida
    ownership CompanyDocument/CompanyEvidence, segmentos codificados e identidad del import.
    diagnostics.ts proyecta sólo allowlist de resultados existentes. Reusa discovery.ts y
    tenders.ts sin endpoints nuevos ni cambios de dominio.
31. **Backend:**0 cambios de producción o tests; sólo evidencia local nueva en reports/ui_r6.
32. **Alembic:** current licitia_test y heads nuevos = `20261023_discovery_079`;0 migraciones.
33. **Dependencias:**0; package/lock intactos, sin SaaS/analytics, iconos ni CDN añadidos.
34. **Async:** useRead invalida generaciones y desmontajes, por empresa/documento/consulta.
    Detail key empresa+documento+updated_at; A tardío no reemplaza B. Refresh diagnóstico
    más nuevo invalida anterior. Mutaciones localizadas; selección dentro de biblioteca
    bloqueada durante la acción del detalle. No efecto global que borre estado por sidebar.
35. **Continuidad:** navy/light, tokens, Button/Notice/Loading/Error/TableShell compartidos.
    Header global único en modo embebido, baja ornamentación, sin charts/tarjetas de relleno.
36. **Empresa densidad:** tabla5 columnas y detalle inferior; datos fuente y acciones humanas
    secundarias, formularios plegables. No grafo ni10columnas de evidencia simultáneas.
37. **Reportes densidad:** catálogo corto + registro filtrable; sin dashboard ni galerías.
38. **Configuración densidad:**3 fuentes, editor acotado de enabled/áreas; formularios compactos
    que envuelven controles. No muro de variables técnicas ni opción no contratada.
39. **Diagnóstico densidad:** estados por grupo, detalle seguro plegable y herramientas
    heredadas sólo a demanda; nunca gran volcado por defecto.
40. **Sidebar:** AppShell.tsx/shell.css sin cambios desde UI-R5.260/64px y key persistida
    intactos. Ruta activa y utilidades verificadas, incluyendo globals y narrow.
41. **1366×768:** PASS expandido/contraído; tabla empresarial con scroll contenido y controles
    alcanzables. Header/nav compactos, sin añadir metadata al ganar ancho.
42. **1440×900:** PASS para los cuatro destinos, sin overflow horizontal global.
43. **1920×1080:** PASS, max-width del shell respetado, sin formularios/navegación paralela.
44. **Narrow390×844:** PASS para los cuatro destinos, scroll local en tablas y menú alcanzable;
    no certificación móvil para preparar ofertas ni certificación WCAG.
45. **Capturas:**32 capturas bajo backend/reports/ui_r6/browser, enumeradas al final. Incluyen
    biblioteca/detalle/fechas/vacío, catálogo/resultados/vacío, settings/restricción,
    diagnóstico/detalle/indisponible, sidebars y cuatro vistas en tres desktops+narrow.
46. **Contact sheet:** backend/reports/ui_r6/browser/contact-sheet.png,1800×1040; seis estados,
    incluida restricción Compras. Inspección visual realizada; aprobación humana pendiente.
47. **Focused:**48 passed /5 archivos:18 SupportProduct +5 SupportApi +6 Shell +16 Sidebar
    +3 SidebarState. Cubre capacidades y fallos, rechazo sin nota, carga B→A, source guard,
    privacy, A tardío y refresh nuevo. Contratos mock no prueban semántica documental/modelos.
48. **Frontend completo:**303 passed /36 archivos. Incluye Tender/comercial/propuesta y
    globals. Warning preexistente: key duplicada `a` en fixture DocumentViewer.test; no
    se modificó esa prueba/módulo en UI-R6. Sin excepciones runtime en browser.
49. **Browser UI-R6:**10 grupos PASS,32 capturas; API interceptada con fixtures sintéticas.
    Clipboard sustituido sólo en harness para no escribir el portapapeles del usuario;
    prueba contratos/copia segura, no permisos OS de todos los navegadores.
50. **Backend/API:**37 company_library/evidence PASS (13.84s) +2 fuentes/guard offline PASS
    (3.03s).6warnings en cada corrida: python_multipart/Swig. Sólo licitia_test; no opt-ins
    de modelos, datos dev, portales reales o nueva ejecución ciega. No suite backend completa
    porque la superficie de producción backend no cambió.
51. **UI-R5 browser:** script original11 grupos PASS.
52. **UI-R4 browser:** script original11 grupos PASS.
53. **UI-R3 browser:** script original12 grupos PASS.
54. **UI-R2 browser:** script original13 grupos PASS. Sidebar UI-R5 original10 grupos PASS.
    Scripts secuenciales con páginas nuevas; evidencias en ui_r6 sin sobrescribir históricos.
55. **Build/typecheck:** PASS. JS638.16kB,CSS35.04kB, persiste warning >500kB. No dependencia
    nueva; optimización/code splitting no implementados en este slice.
56. **Compile/diff:** intérprete backend obligatorio `-m compileall -q backend/app backend/scripts backend/tests`
    PASS, `git diff --check` PASS. Índice vacío; cambios/newfiles enumerados abajo.
57. **Archivos exactos:** apéndice siguiente. Reportes, capturas, DBs/env/binarios excluidos
    del conjunto versionable. Sólo UI-R5 comprometido, sin stage de UI-R6.
58. **Límites:** lista de compañías/documentos/Tenders sigue contratos completos existentes,
    sin promesa de escala ilimitada. Refresh explícito puede reconstruir el detalle; drafts,
    File y solicitudes pendientes viven en memoria, reload puede perderlos. No existe
    idempotencia empresarial exactly-once del servidor: reintento ambiguo exige verificar.
    Metadatos/source settings conservan concurrencia del API actual, sin inventar revisiones.
    Módulos globales de personas/usos/reportes agregados no disponibles. Diagnóstico no
    certifica salud DB/semántica ni valida ejecución real de OCR/LLM. Herramientas legacy
    conservan su UI extensa bajo acceso explícito; no rediseñadas. Sin inspeccionar Tender
    #002 ni repetir el barrido5941; evidencia previa no se presenta como nueva ejecución.
59. **Gates A–Q:** PASS técnico para alcance disponible, con límites descritos abajo.
    Aprobación arquitectónica y visual humana UI-R6 pendiente.
60. **Listo para commit:** sí para revisión; no se autoriza/ejecuta stage/commit/push UI-R6.
    HEAD sigue UI-R5 y los reportes locales históricos permanecen sin seguimiento.
61. **UI-R7 recomendado exacto:** revisión transversal de copy/spacing/densidad, estados
    vacíos/error/loading, teclado/foco/labels, deep links y navegación coherente; validación
    completa visual expandido/contraído y responsive. Preservar semántica, fuentes y autoridad
    humana. Evaluar code splitting únicamente por el warning medido, con plan acotado antes
    de tocar composición. Sin nuevos dominios, dashboards, providers, auth, telemetría o
    rediseño de foundations. UI-R7 no implementado.

## Gates A–Q

| Gate | Evidencia / resultado |
|---|---|
| A información empresarial real | PASS contratos Company/Document/Evidence |
| B documento no implica cumplimiento | PASS aviso, decisiones separadas, tests |
| C reportes útiles reales | PASS inventario previo y catálogo de contratos |
| D sin KPIs ficticios | PASS0charts/scores, estados basados en respuestas |
| E settings de producto | PASS enabled/áreas, sin editor de entorno |
| F fuentes veraces | PASS metadata local, sin afirmar uptime |
| G Compras restringido | PASS UI sin acción y guard409 offline |
| H diagnóstico secundario | PASS route/disclosure y advanced a demanda |
| I no secretos en resumen | PASS allowlist y payloads secretos inyectados |
| J no telemetría | PASS requests locales y copia explícita |
| K sidebar estable | PASS hashes de fuentes intactos y10grupos regresión |
| L sin expansión backend | PASS0producción/tests backend |
| M sin migración | PASS079 current/heads |
| N sin fixtures runtime | PASS imports sólo tests/script |
| O1366 utilizable | PASS desktop expandido/contraído |
| P continuidad visual | PASS tokens/shell/tablas, review humana pendiente |
| Q regresión | PASS48focused/303frontend/39API/10R6+regresiones |

## Validación reproducible

Desde raíz:

```sh
npm --prefix frontend test -- src/components/SupportProduct.test.tsx src/api/SupportApi.test.ts src/ui/Shell.test.tsx src/ui/Sidebar.test.tsx src/components/SidebarState.test.tsx
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run typecheck
node frontend/scripts/ui-r6-browser.mjs backend/reports/ui_r6/browser
node frontend/scripts/ui-r5-browser.mjs backend/reports/ui_r6/r5_regression
node frontend/scripts/ui-r4-browser.mjs backend/reports/ui_r6/r4_regression
node frontend/scripts/ui-r3-browser.mjs backend/reports/ui_r6/r3_regression
node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r6/r2_regression
node frontend/scripts/ui-r5-sidebar-browser.mjs backend/reports/ui_r6/r5-sidebar_regression
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests
git diff --check
```

Desde backend:

```sh
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test LICITIA_DISCOVERY_REPORT_ROOT=reports/ui_r6 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_company_library.py tests/test_company_evidence.py -q -k 'not opt_in'
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test LICITIA_DISCOVERY_REPORT_ROOT=reports/ui_r6 /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_discovery.py::test_m10a01_02_05_23_24_28_29_normalization_and_source tests/test_discovery_cfe.py::test_registry_api_deferred_guard_and_generic_cfe_scan -q
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
```

Vite localhost5181, Chromium CDP9331/perfil aislado. Sin cookies/perfiles del usuario.
Evidencia local nueva en backend/reports/ui_r6, sin editar artefactos históricos.

## Archivos del commit UI-R5 (25)

- `docs/adr/0039-commercial-readiness-proposal-product-ui.md`
- `docs/roadmap.md`
- `docs/ui-r5-implementation.md`
- `frontend/scripts/ui-r5-browser.mjs`
- `frontend/scripts/ui-r5-sidebar-browser.mjs`
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
- `frontend/src/components/SidebarState.test.tsx`
- `frontend/src/components/commercialProduct.css`
- `frontend/src/test/commercialProductFixtures.ts`
- `frontend/src/ui/AppShell.tsx`
- `frontend/src/ui/Shell.test.tsx`
- `frontend/src/ui/Sidebar.test.tsx`
- `frontend/src/ui/commercialPresentation.ts`
- `frontend/src/ui/routes.ts`
- `frontend/src/ui/shell.css`

## Archivos exactos UI-R6 (17, sin stage)

- `docs/adr/0040-global-support-product-ui.md`
- `docs/roadmap.md`
- `docs/ui-r6-implementation.md`
- `frontend/scripts/ui-r6-browser.mjs`
- `frontend/src/ProductApp.tsx`
- `frontend/src/api/SupportApi.test.ts`
- `frontend/src/api/company.ts`
- `frontend/src/api/diagnostics.ts`
- `frontend/src/components/CompanyView.tsx`
- `frontend/src/components/DiagnosticsView.tsx`
- `frontend/src/components/ReportsView.tsx`
- `frontend/src/components/SettingsView.tsx`
- `frontend/src/components/SupportProduct.test.tsx`
- `frontend/src/components/supportProduct.css`
- `frontend/src/test/supportFixtures.ts`
- `frontend/src/ui/Shell.test.tsx`
- `frontend/src/ui/companyPresentation.ts`

## Capturas exactas UI-R6

- `01-company-library.png`
- `02-company-detail.png`
- `03-company-validity.png`
- `04-company-empty.png`
- `05-reports-catalogue.png`
- `06-report-result.png`
- `07-report-no-data.png`
- `08-settings.png`
- `09-source-settings.png`
- `10-compras-restricted.png`
- `11-diagnostics.png`
- `12-technical-detail.png`
- `13-service-warning.png`
- `14-company-collapsed.png`
- `15-settings-collapsed.png`
- `16-configuracion-1366.png`
- `16-configuracion-1440.png`
- `16-configuracion-1920.png`
- `16-configuracion-diagnostico-1366.png`
- `16-configuracion-diagnostico-1440.png`
- `16-configuracion-diagnostico-1920.png`
- `16-mi-empresa-1366.png`
- `16-mi-empresa-1440.png`
- `16-mi-empresa-1920.png`
- `16-reportes-1366.png`
- `16-reportes-1440.png`
- `16-reportes-1920.png`
- `17-configuracion-390.png`
- `17-configuracion-diagnostico-390.png`
- `17-mi-empresa-390.png`
- `17-reportes-390.png`
- `18-narrow-navigation.png`
- `contact-sheet.png`
