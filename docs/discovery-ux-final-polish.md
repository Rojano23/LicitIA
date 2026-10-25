# Discovery UX — pulido final del mismo hotfix

Seguimiento acotado posterior: [micropulido final de fuentes](discovery-ux-final-micro-polish.md).
Los conteos y archivos de este reporte corresponden a esta iteración previa.

Implementado y validado; pendiente de revisión final del Product Owner. No UI-R8.
Se conserva el working tree anterior; sin stage, commit, push ni amend.
[ADR-0042](adr/0042-discovery-ux-workflow.md), [iteración previa](discovery-ux-workflow-hotfix.md).

## Reporte solicitado

1. **HEAD:** `8712c012c4483c320479814b343e684e6049c6bc`, conservado.
2. **Hotfix preservado:** continúan presentes sus 20 archivos previos. Se trabajó sobre ellos; no reset/checkout/revert/recreación ni descarte. Presets, perfiles en Configuración, ayudas, filtros, matching y handoff permanecen.
3. **Total acumulado:** 30 archivos de implementación/pruebas/documentación frente a HEAD; lista exacta abajo. Reportes y capturas quedan fuera de ese conjunto.
4. **Adicionales de este pulido:** lista incremental abajo, comparada con los hashes de la evidencia previa, sin modificar ese manifiesto histórico.
5. **Backend producción:** cero cambios. No nuevos endpoints, adquisición, reglas, matching, scheduler o análisis.
6. **Migraciones:** cero cambios; no se ejecutó Alembic. 079 es el estado verificado en la iteración previa, no una nueva migración o validación de DB en este pulido.
7. **Dependencias:** cero cambios de package/lock/runtime.
8. **Estructura final:** franja de fuentes → 1 Consultar → 2 Resultado actual → 3 Filtrar → 4 Revisar. Modo de detalle separado dentro de la misma vista, sin dominio/ruta nuevos.
9. **Nueva consulta:** retirada, incluida la alternativa del vacío. No hay botón superior sustituto ni entrada redundante.
10. **Paso 1:** visible permanentemente. Fuente, áreas, periodo y filtros opcionales conservados; sólo Consultar fuente ejecuta consulta explícita. Mantiene UUID/query pendientes para reintento incierto. Busy/error de consulta aparecen junto al control; abrir/navegar no consulta portales.
11. **Paso 2:** un solo resultado actual/más reciente de la fuente, con estado, fuente, fecha/periodo legibles, oportunidades y lotes. Advertencias PARTIAL/FAILED intactas y cifras ausentes no se inventan. Ver resultados aplica fuente/periodo, preserva perfil/preferencia de coincidencias y enfoca filtros; no fuerza matching.
12. **Última consulta:** no acumula botones históricos. Fixture de 100 consultas mantiene un solo resultado operativo. Cambiar fuente obtiene su resultado más reciente. Una consulta explícita recién completada se conserva frente a un listado histórico anterior. Enlaces antiguos a un scan redirigen a Diagnóstico.
13. **Consultas anteriores:** Diagnóstico → Consultas Discovery → Historial de consultas Discovery. Tabla acotada a 20 registros, lectura/actualización existente, sin consulta pública ni nuevo almacenamiento. Inicio dirige Revisar consulta a Diagnóstico.
14. **Revisar:** carga el detalle y oculta el flujo sin desmontarlo. Foco al encabezado accesible; desplazamiento al inicio del contenedor conserva visible Volver a oportunidades. No hay que buscar el resultado debajo de la tabla.
15. **Volver a oportunidades:** conserva filtros y página; enfoca/desplaza al botón de la fila seleccionada, con fallback al encabezado de resultados. No vuelve a pedir la lista. Tests incluyen página 50 y filtro aplicado.
16. **Seguir/Dejar de seguir:** respuesta canónica actualiza el detalle y la tabla; botón inverso y confirmación inline («Siguiendo esta oportunidad» / «Dejaste de seguir esta oportunidad»). La fila también muestra confirmación propia. Sin toasts ni actualización automática del portal.
17. **Estado:** tras actualización/relectura exitosa, «Estado actualizado» junto a la fila. Fallos permanecen junto a esa acción; los errores del detalle se localizan en contexto, historial o creación según corresponda.
18. **Ver cambios:** abre el mismo modo de detalle y enfoca/desplaza directamente al encabezado del historial. Probado en navegador y tests.
19. **Encabezado:** Historial de cambios. Explica que las observaciones pueden preceder a Seguir y que seguir no crea el historial. No se confunden con documentos de una licitación.
20. **Acción:** «Marcar estos cambios como revisados». Acknowledgment canónico de los cambios visibles pendientes; confirmación «Cambios marcados como revisados», sin borrar historia ni tocar la fuente.
21. **Lista:** un `ol`/`li` cronológico, fecha legible, estado revisado/por revisar, etiqueta humana y nombre documental cuando existe en campos soportados. Orden antiguo → reciente y paginación de 100 del contrato existente. Scroll del contenedor hasta 32rem; no una tarjeta/botón por evento.
22. **Volumen:** fixture con 50 eventos → 50 filas de una lista y sólo tres botones de historial (revisar/anterior/siguiente). Fixture con 100 consultas → un resultado operativo y hasta 20 filas en Diagnóstico. Sin dependencia de virtualización.
23. **Traducciones:** Nueva oportunidad detectada, Nuevo documento disponible, Información actualizada, Cambió el estado publicado, Referencia documental retirada y otras categorías canónicas existentes. No se muestra el summary libre del servidor. El contrato también incluye acciones auditadas no SOURCE: se conservan identificadas como «Acción registrada en TuScope»; no se presentan como cambios públicos.
24. **Códigos:** NEW_OPPORTUNITY, DOCUMENT_ADDED y códigos internos retirados del detalle normal. No se añade expansión si sólo aportaría datos técnicos.
25. **UUID/JSON/external_id:** retirados de texto y etiquetas de detalle; no `pre`/JSON ni payload. La tabla y su selector usan el número de procedimiento público cuando existe; sin él muestran una ausencia comprensible/título, no el identificador técnico. IDs siguen internamente en keys/requests para conservar ownership y correlación. Fechas de importación se formatean y se retiran SHA y errores crudos de la presentación normal.
26. **Información técnica:** historial operativo en Diagnóstico con fecha/hora, fuente, periodo, estado, conteos y número de incidencias. Sin payload, secretos, paths ni mensajes libres. Los detalles crudos por evento se retiraron, no se duplicaron ni se creó un visor técnico nuevo.
27. **Crear licitación:** conserva preview, selección vacía, confirmación, binding, conflictos/revisión, reintento y advertencia de resultado incierto. No descargas por defecto ni análisis automático. Se conservan pruebas que verifican payload y outcomes; sólo se adapta la expectativa de copy técnico retirado.
28. **Accesibilidad:** foco inmediato en Revisar/Ver cambios, regreso por botón, lista semántica y mensajes locales `role=status/alert`. Shell/foco visible conservados. Verificación básica, no certificación WCAG.
29. **Focused:** `npm --prefix frontend test -- src/components/DiscoveryPolish.test.tsx src/components/DiscoveryDetail.test.tsx src/components/DiscoveryWorkflow.test.tsx src/components/DiscoveryView.test.tsx src/components/DiscoveryClosure.test.tsx src/components/DiscoveryProduct.test.tsx src/components/SupportProduct.test.tsx src/components/InicioView.test.tsx` → **62 passed / 8 files**.
30. **Frontend completo:** `npm --prefix frontend test` → **341 passed / 40 files**. Warning conocido de React por key `a` duplicada en fixture de DocumentViewer; ese módulo no cambió. Sin suite backend ajena: contratos frontend/API incluidos en la suite.
31. **Browser:** nuevo `node frontend/scripts/discovery-ux-polish-browser.mjs backend/reports/discovery_ux_polish/workflow` → **10 grupos PASS**. Regresiones `ui-r2-browser.mjs` **13**, `ui-r7-browser.mjs` **8**, `ui-r6-browser.mjs` **10**; total **41 grupos PASS**. Chromium aislado/Vite 5181, API interceptada, fixtures sintéticas; ningún scan real PEMEX/CFE/Compras ni tráfico a portales. No demuestra relevancia/cobertura semántica real.
32. **Build:** `npm --prefix frontend run build` PASS.
33. **TypeScript:** `npm --prefix frontend run typecheck` PASS.
34. **Git diff:** `git diff --check` PASS; revisión adicional de whitespace en archivos nuevos. Backend, migraciones y package/lock sin diff.
35. **Capturas:** `backend/reports/discovery_ux_polish/workflow/`, 15 PNG y `contact-sheet.png`; lista abajo. 1440×900, 1366×768 y 390×844 sin overflow de página. Sin expansión adicional de evento: no hay información humana extra que justifique una. Capturas de fixtures, nunca de documentos/cookies del usuario.
36. **Git:** índice vacío; 30 archivos del hotfix modificados/nuevos, más directorios históricos de reportes y nueva evidencia local sin seguimiento. HEAD intacto; reportes históricos preservados.
37. **Sin stage/commit/push:** confirmado. Sin amend, reset, clean ni reescritura de historia. No UI-R8.
38. **Pendiente PO:** aprobar visualmente único punto de consulta, limpieza de resultado con mucho historial, navegación/foco/regreso, feedback de seguir/estado/revisión, lista legible sin códigos, ubicación de consultas anteriores y preview explícito. No blockers técnicos detectados en los gates ejecutados; revisión humana pendiente.

## Archivos acumulados e incrementales

Acumulado (30):

- docs/adr/0042-discovery-ux-workflow.md
- docs/discovery-ux-final-polish.md
- docs/discovery-ux-workflow-hotfix.md
- docs/roadmap.md
- frontend/scripts/discovery-ux-hotfix-browser.mjs
- frontend/scripts/discovery-ux-polish-browser.mjs
- frontend/scripts/ui-r2-browser.mjs
- frontend/src/ProductApp.tsx
- frontend/src/api/discovery.ts
- frontend/src/components/DiagnosticsView.tsx
- frontend/src/components/DiscoveryClosure.test.tsx
- frontend/src/components/DiscoveryDetail.test.tsx
- frontend/src/components/DiscoveryDetail.tsx
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

Incremental respecto de los hashes de la entrega previa (21):

- docs/adr/0042-discovery-ux-workflow.md
- docs/discovery-ux-final-polish.md
- docs/discovery-ux-workflow-hotfix.md
- docs/roadmap.md
- frontend/scripts/discovery-ux-polish-browser.mjs
- frontend/scripts/ui-r2-browser.mjs
- frontend/src/components/DiagnosticsView.tsx
- frontend/src/components/DiscoveryClosure.test.tsx
- frontend/src/components/DiscoveryDetail.test.tsx
- frontend/src/components/DiscoveryDetail.tsx
- frontend/src/components/DiscoveryPolish.test.tsx
- frontend/src/components/DiscoveryProduct.test.tsx
- frontend/src/components/DiscoveryQueryHistory.tsx
- frontend/src/components/DiscoveryView.test.tsx
- frontend/src/components/DiscoveryView.tsx
- frontend/src/components/DiscoveryWorkflow.test.tsx
- frontend/src/components/InicioView.test.tsx
- frontend/src/components/InicioView.tsx
- frontend/src/components/SupportProduct.test.tsx
- frontend/src/components/discovery.css
- frontend/src/ui/discoveryPresentation.ts

## Capturas

`01-main-workflow.png`, `02-latest-only.png`, `03-filtered-table.png`,
`04-review-immediate.png`, `05-detail-top.png`, `06-compact-history.png`,
`07-reviewed.png`, `08-following.png`, `09-create-preview.png`, `10-return-context.png`,
`11-state-feedback.png`, `12-diagnostic-history.png`, `13-discovery-1366.png`,
`13-discovery-390.png`, `14-change-history-focus.png`, `contact-sheet.png`.

Logs, hashes, resultados y estado Git: `backend/reports/discovery_ux_polish/validation.json`
y archivos adyacentes. Reportes previos bajo `discovery_ux_hotfix` no se sobrescribieron.

Límites: historial de consultas limitado por el endpoint existente a sus registros recientes;
sin nueva API de paginación. Historial de oportunidad mantiene su paginación canónica. Filtros,
archivos seleccionados y formularios en memoria no se hacen persistentes por este pulido.
