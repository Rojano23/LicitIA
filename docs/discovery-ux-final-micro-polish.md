# Discovery UX — micropulido final del mismo hotfix

Implementado y validado; pendiente de aceptación visual final del Product Owner.
No UI-R8. Sin stage/commit/push/amend. Continúa sobre el working tree anterior.

1. **HEAD:** `8712c012c4483c320479814b343e684e6049c6bc`, sin cambios.
2. **Preservación:** todos los 30 archivos del hotfix previo siguen presentes. Sin reset, checkout, revert, descarte o recreación. Su evidencia local no se sobrescribió.
3. **Franja:** override CSS acotado a Discovery; cada bloque pasa de columna a fila con baseline y gap de tokens existentes. Nombre y estado comparten línea; sin cards, iconos nuevos ni reducción de fuente.
4. **Desktop:** 1440 y 1366: comprobación de coordenadas nombre/estado por fuente e inspección de capturas PASS. Los bloques completos pueden pasar a otra fila cuando su suma no cabe, sin forzar una línea global.
5. **Responsive:** flex-wrap y max-width:100%; narrow 390 conserva wrapping natural sin overflow de página. Compras mantiene badge/semántica restringida; los estados proceden del contrato, sin modificación para conseguir el layout.
6. **Control anterior:** invertía `enabled` con `!source.enabled` y persistía las áreas seleccionadas como `configuration.areas`. Luego releía fuentes/perfiles/historial. Era administración, no consulta; no daba confirmación específica de guardado en Discovery.
7. **Endpoint:** `discoveryApi.configure` → PATCH `/discovery/sources/{source_id}`, body `{enabled,areas}`; `configure_source` existente valida fuente/áreas y guarda DB. Capacidad backend y wrapper intactos.
8. **Dependencia real:** POST `/discovery/sources/{source_id}/scans` usa `query.areas` de la selección actual. El backend exige `enabled=true` y que sean subconjunto de `configuration.areas`, o devuelve SOURCE_DISABLED/AREA_NOT_ENABLED. La configuración administrativa puede ser necesaria previamente para habilitar fuente/áreas, pero no hay que guardarla antes de cada consulta. Deshabilitar una fuente no es un paso cotidiano de consulta.
9. **Decisión:** botón de habilitar/deshabilitar retirado de paso 1. No PATCH oculto, autoenable ni migración. Administración sólo en Configuración.
10. **Paso 1:** fuente, estado, áreas de consulta, periodo, evento/suministro y acción explícita Consultar fuente. Sin acción administrativa entre selección y consulta. Conserva presets, UUID/query de reintento y demás comportamiento aceptado.
11. **Áreas:** disponibles como checkboxes; las habilitadas se pueden combinar o reducir y se envían en el siguiente request nuevo. Prueba exacta: desmarcar Soporte envía `areas:['logistics']` sin configure. Áreas del catálogo no habilitadas administrativamente aparecen desactivadas con orientación a Configuración, evitando una solicitud condenada a AREA_NOT_ENABLED. Los reintentos inciertos conservan su query original, como antes.
12. **Deshabilitada:** «Esta fuente está deshabilitada.» + enlace pequeño Configurar fuente a `#/configuracion?section=sources`; Consultar fuente permanece desactivado. Compras conserva su mensaje de restricción, sin ofrecer habilitación operativa ni bypass.
13. **Configuración:** Fuentes Discovery conserva selector/edición, enabled, áreas y guardado explícito mediante PATCH existente. El nuevo enlace enfoca/desplaza su encabezado. No habilita ni guarda al navegar. Discovery conserva su acción existente de actualizar lecturas de fuentes/perfiles si se requiere releer una configuración cambiada.
14. **Backend:** cero cambios de producción/tests. Sin adquisición real PEMEX/CFE/Compras, ni cambios de matching, adapters, paginación, handoff o datos guardados.
15. **Migraciones:** cero cambios; no se ejecutó Alembic. 079 es el estado previamente verificado, no una nueva comprobación de DB aquí.
16. **Dependencias:** cero cambios; package/lock intactos.
17. **Focused:** `npm --prefix frontend test -- src/components/DiscoveryMicro.test.tsx src/components/DiscoveryPolish.test.tsx src/components/DiscoveryView.test.tsx src/components/DiscoveryWorkflow.test.tsx src/components/DiscoveryProduct.test.tsx src/components/DiscoveryDetail.test.tsx src/components/DiscoveryClosure.test.tsx src/components/SupportProduct.test.tsx src/components/InicioView.test.tsx` → **66 passed / 9 files**. Incluye ausencia de administración operativa, selección/request exacto, guard de áreas, orientación/configuración y preservación del flujo anterior.
18. **Frontend:** `npm --prefix frontend test` → **345 passed / 41 files**. Warning conocido de key `a` duplicada en fixture de DocumentViewer ajena al cambio; no falla la suite.
19. **Browser/E2E:** `node frontend/scripts/discovery-ux-micro-browser.mjs backend/reports/discovery_ux_micro/workflow` → **4 grupos PASS**, 7 capturas. Regresión del pulido `discovery-ux-polish-browser.mjs` **10**, UI-R2 **13**, UI-R6 **10**: **37 grupos PASS**. Chromium/Vite locales, fixtures sintéticas interceptadas, sin portales ni DB real. Las fixtures de enabled/disabled son explícitas y no representan cambios de configuración del usuario.
20. **Build:** `npm --prefix frontend run build` PASS; JS principal 485.70 kB, chunk App 173.92 kB, CSS 39.06 kB.
21. **Typecheck:** `npm --prefix frontend run typecheck` PASS.
22. **Diff:** `git diff --check` PASS; backend/migraciones/package/lock sin diff. Archivos nuevos revisados por whitespace.
23. **Capturas:** `backend/reports/discovery_ux_micro/workflow/`: `01-strip-desktop.png`, `02-strip-1366.png`, `03-strip-narrow.png`, `04-step1-pemex.png`, `05-selected-areas.png`, `06-disabled-source.png`, `07-settings-sources.png`, `contact-sheet.png`. Capturas y logs locales sin stage; revisión básica, no certificación WCAG.
24. **Git:** HEAD conservado, índice vacío. 33 archivos acumulados del hotfix sin stage, más reportes históricos/evidencia local sin seguimiento. Lista incremental y acumulada abajo.
25. **Sin stage/commit/push:** confirmado, sin amend ni reescritura. El commit espera aceptación humana final.
26. **Listo para aceptación:** sí, con gates técnicos anteriores PASS. Pendiente PO: confirmar franja compacta en desktop/1366/narrow, limpieza del paso 1, selección de áreas y enlace administrativo. No se rediseñó Discovery ni se abrieron módulos posteriores.
27. **Siguiente flujo real recomendado:** Seleccionar oportunidad real → Revisar → Crear licitación → seleccionar documentos → confirmar creación → abrir Tender → continuar navegación del expediente. No se ejecutó ese flujo real ni una nueva consulta pública en este micropulido.

## Archivos

Incremental respecto de la entrega anterior (11):

- docs/adr/0042-discovery-ux-workflow.md
- docs/discovery-ux-final-micro-polish.md
- docs/discovery-ux-final-polish.md
- docs/roadmap.md
- frontend/scripts/discovery-ux-micro-browser.mjs
- frontend/src/ProductApp.tsx
- frontend/src/components/DiscoveryMicro.test.tsx
- frontend/src/components/DiscoveryView.test.tsx
- frontend/src/components/DiscoveryView.tsx
- frontend/src/components/SettingsView.tsx
- frontend/src/components/discovery.css

Acumulado del hotfix (33):

- docs/adr/0042-discovery-ux-workflow.md
- docs/discovery-ux-final-micro-polish.md
- docs/discovery-ux-final-polish.md
- docs/discovery-ux-workflow-hotfix.md
- docs/roadmap.md
- frontend/scripts/discovery-ux-hotfix-browser.mjs
- frontend/scripts/discovery-ux-micro-browser.mjs
- frontend/scripts/discovery-ux-polish-browser.mjs
- frontend/scripts/ui-r2-browser.mjs
- frontend/src/ProductApp.tsx
- frontend/src/api/discovery.ts
- frontend/src/components/DiagnosticsView.tsx
- frontend/src/components/DiscoveryClosure.test.tsx
- frontend/src/components/DiscoveryDetail.test.tsx
- frontend/src/components/DiscoveryDetail.tsx
- frontend/src/components/DiscoveryMicro.test.tsx
- frontend/src/components/DiscoveryPolish.test.tsx
- frontend/src/components/DiscoveryProduct.test.tsx
- frontend/src/components/DiscoveryQueryHistory.tsx
- frontend/src/components/DiscoveryView.test.tsx
- frontend/src/components/DiscoveryView.tsx
- frontend/src/components/DiscoveryWorkflow.test.tsx
- frontend/src/components/InicioView.test.tsx
- frontend/src/components/InicioView.tsx
- frontend/src/components/SearchProfiles.tsx
- frontend/src/components/SettingsView.tsx
- frontend/src/components/SupportProduct.test.tsx
- frontend/src/components/discovery.css
- frontend/src/components/discoveryHelp.tsx
- frontend/src/components/discoveryPeriods.tsx
- frontend/src/components/supportProduct.css
- frontend/src/ui/discoveryPresentation.ts
- frontend/src/ui/routes.ts

Evidencia reproducible: `backend/reports/discovery_ux_micro/validation.json`, hashes, logs y
estado Git. Los reportes previos de hotfix/polish permanecen sin sobrescribir. No nuevo
barrido de corpus histórico ni modelos reales; las pruebas sintéticas no certifican fuentes.
