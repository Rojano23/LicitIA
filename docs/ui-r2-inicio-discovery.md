# UI-R2 — Inicio + Discovery Product UI

Estado: implementado y validado, listo para revisión arquitectónica/visual.
**Sin stage/commit/push de UI-R2**. MVP-01–10 CLOSED.
[Contrato visual canónico](RX23_TUSCOPE_PRODUCT_UI_RECONCILIATION_v1.md),
[ADR-0036](adr/0036-inicio-discovery-product-ui.md).

## Reporte final

1. **Commit UI-R1:** `d0398f17f4b46c4a74046513aaced1451ad52951`,
   `feat(ui): establish rx23 tuscope app shell`. Creado al recibir aceptación UI-R1; sin push.
2. **HEAD resultante:** mismo SHA. No segundo commit UI-R1 ni commit UI-R2.
3. **Archivos UI-R1 comprometidos (20):** docs/adr/0035-product-ui-shell-navigation.md,
   docs/roadmap.md, docs/ui-r1-app-shell.md, frontend/index.html,
   frontend/scripts/ui-r1-browser.mjs, frontend/src/App.test.tsx, frontend/src/App.tsx,
   frontend/src/ProductApp.tsx, frontend/src/components/CommercialSpreadsheet.tsx,
   frontend/src/components/CompanyEvidenceLibrary.tsx, frontend/src/components/ScopeReview.test.tsx,
   frontend/src/components/ScopeReview.tsx, frontend/src/components/WorkspaceFlow.tsx,
   frontend/src/index.css, frontend/src/main.tsx, frontend/src/ui/AppShell.tsx,
   frontend/src/ui/Shell.test.tsx, frontend/src/ui/primitives.tsx, frontend/src/ui/routes.ts,
   frontend/src/ui/shell.css. Se verificaron20 hashes aceptados antes del staging explícito;
   imágenes/reportes/env/DB excluidos.
4. **Inicio final:** header compacto del shell, actualización manual de lecturas locales,
   dos indicadores accionables, atención agrupada y tabla de5 licitaciones recientes.
   Sin hero, charts, trending ni métricas financieras/globales sin contrato.
5. **Métricas mostradas:** Oportunidades nuevas; Siguiendo con cambios. Dos tarjetas compactas,
   no relleno de una grilla4–6. No se muestra valor0 por una petición fallida.
6. **Fuentes/definición exactas:** GET `/discovery/monitoring/summary` →
   `new_opportunities` = COUNT Opportunity.internal_state NEW;
   `followed_with_changes` = COUNT Opportunity.watching=true con >=1 Change.origin SOURCE
   y acknowledged_at NULL. Watching puede incluir IMPORTED: no se sustituye por estado
   FOLLOWING. Destinos `#/discovery?view=new` y `?view=following-changes` → filtros del backend
   NEW, o following=true+unread_only=true respectivamente. Limpian filtros locales anteriores.
7. **Métricas omitidas:** atención/readiness global, requisitos por revisar globales,
   propuestas en preparación globales, fechas límite, tendencias y totales económicos:
   no proyección transversal verificable/acotada; no fanout ni nuevas APIs. Activas queda
   fuera de Inicio como en UI-R0 para no confundir ACTIVE con DRAFT que sigue en trabajo.
8. **Atención:** hasta5 oportunidades seguidas con cambios sin leer, GET `/discovery/opportunities`
   following=true,unread_only=true,limit5,offset0 (orden canónico publicación/first_seen/ID);
   vínculos a detalle e historia. Otro grupo con hasta3 PARTIAL/FAILED entre20 scans recientes
   GET `/discovery/scans` orden started_at DESC/ID. No ranking inventado entre categorías.
   Es historia de consultas, no declaración del estado actual de una fuente. Errores de lectura
   independientes mediante allSettled; se conserva utilidad de las otras secciones.
9. **Tenders:** GET `/tenders` completo existente, orden frontend updated_at DESC/ID,
   primeros5; referencia/título, perfil institucional, estado legible, actualización de registro
   y Abrir licitación. Sin consultas readiness por Tender ni fecha contractual inferida.
10. **Vacío:** sin Tenders ni señales de atención de los conjuntos consultados, “Aún no hay
    licitaciones”, Crear licitación/Ir a Discovery. No afirma que no existan procedimientos
    públicos ni certifica que no haya registros descartados/seguidos sin cambios.
11. **Discovery final:** franja fuentes, vista/fuente/perfil/search, Más filtros, tabla,
    paginación, detalle contextual y secciones plegables de consultas/historial y perfiles.
    “Buscar actualizaciones” abre controles de consulta; no ejecuta adquisición por sí solo.
12. **Fuentes:** nombre, enabled y última consulta traducida. “Disponible para consulta”
    expresa capacidad/habilitación local, no uptime probado del portal. Compras neutral.
13. **Filtros:** Todas/Nuevas/Siguiendo/Con cambios/Siguiendo con cambios/Licitaciones creadas/
    Descartadas; fuente, perfil y búsqueda normalizada. Avanzados: área exacta, publicación,
    tipos de evento/suministro y estado fuente; estado interno y flags combinables conservados.
    Aplicar reinicia offset; páginas anterior/siguiente usan filtros aplicados con éxito,
    incluso al volver a0 después de editar un borrador. Total viene del servidor, no de filas.
14. **Perfiles:** selector de búsqueda y editor existente plegable: include ANY/exclude,
    sinónimos, fuentes, áreas, activo, create/edit y revisión optimista. Matching del servidor,
    local y determinista. Perfiles no se envían al portal; no motor/rediseño de reglas.
15. **Columnas (7):** Fuente/Procedimiento, Descripción, Publicación/Área, Coincidencia,
    Documentos/Cambios, Estado y Acciones. Otros campos en detalle. Descripción3 líneas con
    texto completo accesible al abrir y title. Sin external ID técnico extra si existe número humano.
16. **Traducciones:** NEW Nueva, REVIEW En revisión, FOLLOWING Siguiendo, DISCARDED Descartada,
    IMPORTED Licitación creada; scan SUCCESS Consulta completada, PARTIAL La consulta fue parcial,
    FAILED No se completó la consulta, RUNNING Consulta en curso. Categorías de cambios a español.
17. **Acciones:** Revisar o Abrir licitación según vínculo; Más acciones para detalle/cambios,
    Seguir/Dejar de seguir, estado humano explícito y portal público. IMPORTED no editable como
    un estado arbitrario. Tombstone explica vínculo conservado sin recreación automática.
18. **Detalle:** metadata pública, descripción literal, fecha, área, enlace fuente,
    first_seen/last_seen y evento/suministro en disclosure; match entendible, historia y
    preview. React escapa HTML remoto; no dangerouslySetInnerHTML ni payload como verdad.
19. **Historia:** mismo orden canónico ascendente por detected_at/ID,100 por página,
    paginación y ack explícito de visibles. “Del más antiguo al más reciente”; no sort sólo
    dentro de una página que simule cronología total. Ausencia en filtro no significa cancelación.
    Summary original/códigos/diffs disponibles en detalle diagnóstico, no crudos por defecto.
20. **Documentos:** conteo de referencias descubiertas; lista pública en preview con nombre
    y enlace. Selección no implica importación, referencia no implica archivo disponible local.
    Importación previa separada y SHA sólo al abrir integridad. Resultados por documento conservados.
21. **Crear:** preview readonly por Opportunity/perfil → título → selección vacía → confirmación
    humana → handoff con expected_binding/profile_id/choices. Refresh invalida confirmación.
    No descarga por montar pantalla, no Tender automático ni DI/OCR/Vision/LLM.
22. **Importada:** Abrir usa linked_tender canónico; preview posterior propone agregar documentos,
    no otra creación. Fallo de red advierte que la licitación puede existir y exige verificar
    vínculo antes de reintento. Tombstone no se recrea ni se oculta su historia.
23. **Consulta:** UUID idempotente y query preservados para retry incierto; nueva solicitud
    independiente es explícita. Estado/cifras reales del modelo ScanRun, sin porcentajes ni ETA.
    Controles de adquisición (rango/áreas/tipos) independientes de lista local. GET scan por ID
    reutiliza endpoint existente para vínculos de atención; no API nueva.
24. **Parcial/error:** mensaje específico del resultado, métricas disponibles (ausente se
    presenta No disponible, no cero inventado), cobertura incompleta y diagnóstico bajo demanda.
    Fallo de petición conserva tabla/resultados previos y recovery local; una fuente no vacía otras.
    El historial permite inspeccionar consultas, no fuerza nuevo scan automáticamente.
25. **Compras:** visible “Automatización no disponible actualmente”, sin botón de ejecutar
    consulta y habilitación desactivada. Guard por capability reutilizado, no parser/bypass/
    token/cookie/browser para portal. Sólo metadata e historial de API local; ninguna consulta
    pública a Compras ni sustitución por CompraNet/PAAASOP.
26. **Consistencia:** AppShell/sidebar navy y lienzo claro de UI-R1, Button/StatusBadge/SourceBadge/
    Notice/TableShell/states existentes. CSS nuevo usa tokens; sin nueva paleta ni sistema visual.
27. **Densidad:** tabla compacta con scroll contenido/max-height56vh,7 columnas y descripción
    legible, acción final sticky a la derecha. En1366 no se pierde acción; otras columnas
    pueden desplazarse horizontalmente. No tarjetas por oportunidad.
28. **Cards:** sólo2 indicadores de Inicio; atención/listas y datos tabulares para el trabajo.
29. **1366×768:** PASS inspección visual y bounds; contenido operativo visible sin hero.
    Tabla con scroll local y acción visible. Captura05-discovery-1366.
30. **1440×900:** PASS; Inicio y Discovery capturados, sin overflow global.
31. **1920×1080:** PASS; ancho máximo del shell y tabla legibles, sin nueva navegación paralela.
32. **Narrow:**768×900 y390×844 sin overflow de página; menú sigue alcanzable,
    filtros se envuelven y tabla desplaza localmente. No certifica móvil para preparar ofertas.
33. **Capturas exactas:** todas bajo
    `/Users/ceciliavalencia/LiticIA/backend/reports/ui_r2/browser/`:
    `01-inicio-1366.png`, `02-inicio-1440.png`, `03-inicio-1920.png`, `04-inicio-empty.png`,
    `05-discovery-1366.png`, `05-discovery-1440.png`, `05-discovery-1920.png`,
    `06-following-changes.png`, `07-opportunity-detail.png`, `08-create-preview.png`,
    `09-compras-restricted.png`, `10-partial-source.png`, `11-discovery-narrow-768.png`,
    `12-discovery-narrow-390.png`. Estado sintético exclusivamente de prueba aislada.
34. **Hoja de contacto:** mismo directorio `contact-sheet.png` (6 estados,1800×940).
    Artefacto local para compartir/revisar, no versionado; no datos del usuario.
35. **Backend:**0 cambios producción/tests backend. Wrappers TypeScript sólo para endpoints
    existentes; listado local al montar, sin adquisición pública. Sin nuevo dominio/proyección.
36. **Migraciones:**0; Alembic current test y heads = `20261023_discovery_079`.
37. **Dependencias:**0; sin cambios package/lock; browser CDP nativo Node26 y Chromium local.
    Hoja de contacto compuesta con Pillow ya disponible; no paquete runtime añadido.
38. **Archivos exactos UI-R2:** docs/adr/0036-inicio-discovery-product-ui.md,
    docs/ui-r2-inicio-discovery.md, docs/roadmap.md, frontend/scripts/ui-r2-browser.mjs,
    frontend/src/ProductApp.tsx, frontend/src/api/discovery.ts,
    frontend/src/components/InicioView.tsx, frontend/src/components/InicioView.test.tsx,
    frontend/src/components/DiscoveryProduct.test.tsx, frontend/src/components/discovery.css,
    frontend/src/components/DiscoveryView.tsx, frontend/src/components/DiscoveryView.test.tsx,
    frontend/src/components/DiscoveryDetail.tsx, frontend/src/components/DiscoveryDetail.test.tsx,
    frontend/src/components/DiscoveryClosure.test.tsx, frontend/src/ui/Shell.test.tsx,
    frontend/src/ui/routes.ts, frontend/src/ui/discoveryPresentation.ts.
    Reportes/logs/imágenes sólo bajo backend/reports/ui_r2, sin stage.
39. **Focused:** `npm --prefix frontend test -- src/components/InicioView.test.tsx src/components/DiscoveryProduct.test.tsx src/components/DiscoveryView.test.tsx src/components/DiscoveryDetail.test.tsx src/components/DiscoveryClosure.test.tsx src/ui/Shell.test.tsx`
    →35passed/6files. Incluye filtros, perfil, persistencia de idempotencykey, source restriction,
    partial/fail, override de filtros desde métricas, página0 y contratos de confirmación.
40. **Frontend completo:** `npm --prefix frontend test` →195passed/24files. Regresión UI-R1,
    Tender, revisión Scope, Comercial, preparación y Propuesta incluidas. Tests antiguos sólo
    adaptados a labels/carga local nueva; invariantes de dominio no relajadas.
41. **Browser/E2E:** `node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r2/browser`
    →13grupos PASS. Incluye métricas/destinos, empty, filtros NEW/watching+changes, detalle,
    preview sin writes, confirmación/selección/binding, crear y abrir Tender, partial/restricted,
    tres desktops/narrow y accesibilidad de rutas legacy/Propuesta/Diagnóstico. API interceptada
    con fixtures; no DB producto/portales reales ni prueba de calidad semántica.
42. **API backend:** desde backend,
    `LICITIA_DISCOVERY_REPORT_ROOT=reports/ui_r2 DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_discovery_handoff.py tests/test_discovery_monitoring.py -q`
    →38passed,6warnings deprecación Swig,4.37s. No suite completa2510 requerida/repetida
    por cambio frontend sin backend. No live opt-ins ni consultas públicas.
43. **Build/tipos:** `npm --prefix frontend run build` y `npm --prefix frontend run typecheck`
    PASS. Warning bundle>500kB persiste (~530kB JS); no error ni dependencia nueva.
44. **Compilación/integridad:** intérprete backend obligatorio `-m compileall -q app scripts tests`
    PASS; `git diff --check` PASS. Hash-only histórico5941/5941 intacto, cero diferencias.
    No lectura semántica del corpus ciego. Índice vacío, sólo UI-R1 comprometido por autorización.
45. **Límites:** no métricas globales readiness/propuestas, total nacional ni uptime de portales;
    scan parcial no completa cobertura. Inicio lee listaTender completa porque es el contrato
    existente; no proyección nueva ni fanout. Algunas funciones heredadas siguen plegables;
    sin drawer modal nuevo. E2E mock valida UI/contrato, no fuente real ni semántica.
    Mantener vistas visitadas conserva formularios en memoria; refresh completo no conserva
    cambios sin guardar. A11y básica/foco/labels/semantic table, no certificación WCAG.
46. **Gates A–P:** PASS para alcance UI-R2, matriz abajo. Pendiente aceptación humana de diseño.
47. **Listo para commit:** sí, sujeto a revisión arquitectónica/visual; UI-R2 sin stage/commit/push.
48. **UI-R3 exacto recomendado:** lista/creación/Resumen Tender y Documentos/visor/recovery;
    integrar navegación y fuentes por revisión/página, conservar conflictos/versiones/originales
    y retry explícito. Sin rediseñar aún Requisitos/Cumplimiento/Comercial/Propuesta, sin backend
    nuevo ni cambios DI. UI-R3 no implementado en esta entrega.

## Gates A–P

| Gate | Resultado | Evidencia |
|---|---|---|
| A atención | PASS | dos grupos acotados de hechos locales + acciones |
| B métricas reales | PASS | summary existente y tests de igualdad/destino |
| C sin decoración fake | PASS |0charts,0trends, fixtures sólo test |
| D Opportunity normalizada | PASS | contrato list/get existente |
| E table-first | PASS |7 columnas y scroll contenido |
| F workflows | PASS |35focused + E2E+regresión Discovery |
| G matching transparente | PASS | términos/exclusión/condiciones legibles, sin score |
| H cambios auditables | PASS | historia/ack/detalle de origen preservados |
| I handoff explícito | PASS | preview, selección, confirmación, binding |
| J Compras restringido | PASS |sin consulta ejecutable ni requests al portal |
| K PEMEX/CFE | PASS |handlers/guards/queries existentes, mocks no certifican uptime |
| L backend sin expansión | PASS |diff backend vacío |
| M esquema | PASS |Alembic079,0migrations |
| N visual | PASS |tokens/shared components/capturas comparadas |
| O1366 útil | PASS |tabla legible y acción sticky, sin overflow de página |
| P regresión | PASS |195frontend,38API,13browser,build/types/compile/diff |

## Artefactos y reproducibilidad

`backend/reports/ui_r2/validation.json` registra archivos/HEAD/checks; logs de comandos,
`browser/results.json`, hashes de archivos UI-R2 y conservación histórica permanecen locales.
Para browser: Vite localhost5181, Chromium aislado con CDP9331, script anterior. Cada ejecución
empieza en página limpia; fixtures nunca se cargan en aplicación de producción. No reutiliza
cookies/perfiles del usuario. La aprobación automática inicial falló por límite de uso, sin
emitir juicio de seguridad; al continuar se aprobó el mismo mecanismo y E2E se completó.
