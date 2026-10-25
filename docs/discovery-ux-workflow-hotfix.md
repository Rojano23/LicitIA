# Discovery — hotfix de flujo tras primer uso real

**Reporte de la iteración previa.** La revisión humana posterior sustituye la presentación
descrita aquí con el [pulido final](discovery-ux-final-polish.md); sus resultados anteriores
se conservan como evidencia histórica, no como descripción del flujo vigente.

Implementado y validado; pendiente de revisión del Product Owner. No UI-R8.
MVP-01–10 y UI-R0–R7 permanecen cerrados. Sin stage, commit ni push.
[ADR-0042](adr/0042-discovery-ux-workflow.md).

## Reporte solicitado

1. **HEAD antes:** `8712c012c4483c320479814b343e684e6049c6bc`; se conserva al finalizar.
2. **Archivos:** 20 archivos de frontend, pruebas, scripts y documentación; lista exacta abajo.
3. **Backend de producción:** cero cambios. No se ejecutaron suites backend por este cambio de presentación; no hay nuevas APIs ni cambios de adquisición, adapters, matching o handoff.
4. **Migraciones:** cero cambios. Lectura de `licitia_dev.alembic_version`: `20261023_discovery_079`.
5. **Dependencias:** cero cambios de package/lock/runtime.
6. **Flujo final:** cuatro secciones numeradas, independientes y revisitables: Consultar una fuente → Resultado de la consulta → Filtrar oportunidades guardadas → Revisar oportunidades. Sin wizard obligatorio ni tarjetas decorativas.
7. **Paso 1:** «Nueva consulta» expande, enfoca y desplaza los controles; no consulta. Conserva fuente/áreas/habilitación/filtros compatibles. Sólo «Consultar fuente» ejecuta la acción existente. UUID y query pendientes se conservan para el reintento incierto; no se cambia su contrato.
8. **Paso 2:** muestra el ScanRun seleccionado o el más reciente del historial consultado: fuente, estado, inicio, periodo y cifras presentes. PARTIAL/FAILED conservan sus advertencias; ausencias se muestran como no disponibles. No se confunden cifras de consulta con el total filtrado.
9. **Ver resultados:** acción explícita que aplica `source_id` y `query.published_from/to`, reinicia offset a 0, limpia área/evento/suministro/búsqueda/estado/seguimiento/cambios sin leer y conserva perfil seleccionado + preferencia `matched_only` (efectiva sólo con perfil). Enfoca paso 3. La respuesta corresponde a registros guardados por fuente/periodo, incluidos los de consultas anteriores: no promete pertenencia exclusiva al scan ni inventa un «1 de 111». El total siempre viene del servidor. Si la lectura falla, permanece la tabla anterior y su paginación aplicada.
10. **Paso 3:** fuente, perfil y enlace a administración, búsqueda, periodo, estado y tres flags visibles. Avanzados plegados: sólo Área o entidad, Tipo de evento, Tipo de suministro. Se retiró el selector compuesto de vista redundante; sus estados y combinaciones siguen disponibles mediante los filtros existentes y los enlaces desde Inicio. Aplicar/paginar conserva el contrato de filtros aplicados con éxito.
11. **Paso 4:** tabla de siete columnas, revisión/detalle, seguimiento, estado humano, portal público y Tender vinculado conservados. Preview, selección documental, confirmación, binding y creación explícita no cambian. No análisis ni Tender automáticos.
12. **Perfiles:** editor completo trasladado a Configuración → Perfiles de búsqueda (`SearchProfiles`). Mismas APIs, include ANY, exclusiones prioritarias, sinónimos, restricciones de fuentes/áreas, activo y revisión optimista. Crear/editar permanecen explícitos. Ningún perfil real fue modificado durante la validación.
13. **Administrar perfiles:** enlace junto al selector abre `#/configuracion?section=profiles`, enfoca/desplaza la sección y conserva el shell. Guardar emite un evento interno que refresca lecturas del Discovery montado, sin adquisición pública.
14. **Periodo público:** 7/30/60/90 días, este mes, mes anterior y personalizado; inicial 30 días. Intervalos inclusivos: últimos N = hoy − (N−1) hasta hoy, mes actual = día 1 hasta hoy, anterior = mes completo. Calendario local, sin conversión UTC que desplace un día. El rango resuelto permanece visible; Personalizado revela Desde/Hasta y conserva la validación de fechas existente.
15. **Periodo guardado:** mismos presets más Todos (inicial), traducidos a `published_from/to` del listado existente. Cambiar el borrador no altera páginas aplicadas hasta confirmar filtros.
16. **Ayuda de área:** «Área responsable o entidad que publica o contrata. Usa el nombre que aparece en la oportunidad; no todas las fuentes lo informan de la misma forma». Ayuda desplegable nativa `?`, con nombre accesible, clic/tap/teclado; sin depender de hover.
17. **Eventos reales PEMEX:** lectura autorizada de los 111 registros públicos: Nacional (53), Internacional (13), Internacional bajo TLC (45). No se inspeccionó el corpus ciego ni documentos de Tender.
18. **Eventos CFE:** contrato aceptado del adaptador: Concurso abierto, Concurso simplificado y Adjudicación directa (mapeo a CA/CS/AD). Fixture `cfe-row.json`: Concurso abierto. No hay oportunidades CFE guardadas ni se ejecutó un scan nuevo para obtenerlas.
19. **Ayuda de evento:** PEMEX: «Nacional, Internacional o Internacional bajo TLC». CFE en consulta: «admite Concurso abierto, Concurso simplificado o Adjudicación directa»; sobre registros: «por ejemplo, Concurso abierto». Añade que es opcional y usa el texto informado por la fuente. Sin fuente seleccionada muestra ejemplos identificados por institución.
20. **Control de evento:** selector opcional sólo para la consulta CFE, cuyo adaptador acepta exactamente esas tres etiquetas; texto opcional para PEMEX y filtros guardados, porque una muestra observada no constituye un catálogo exhaustivo. Sin enum de dominio ni endpoint nuevo.
21. **Suministro observado:** PEMEX: Bienes 75, Servicios 27, Obra pública 7, Arrendamientos 1; un registro sin valor. CFE: `Adquisición por Abastecimientos` en fixture/contrato; no se infiere un catálogo ni códigos a partir de etiquetas.
22. **Ayuda de suministro:** «PEMEX: Bienes, Servicios, Obra pública o Arrendamientos» y/o «CFE: por ejemplo, Adquisición por Abastecimientos», según fuente. Campo opcional de texto; usa el valor informado por la fuente. Placeholder coherente con esa fuente.
23. **Estado en la fuente:** filtro retirado de Product UI; capacidad backend intacta. Labels avanzados sin «valor exacto», «valor literal» ni «local». Diagnóstico técnico permanece secundario.
24. **Historial:** «Ver historial» en paso 2 despliega consultas existentes de la fuente seleccionada; permite actualizar lecturas y elegir un registro. No inicia una consulta pública.
25. **Diagnóstico:** disclosure útil con fuente, estado, inicio/fin, intentos/completados, filas y oportunidades; diagnósticos acotados existentes cuando están presentes. No payload, secretos, stack ni métricas inventadas. No se abre un disclosure vacío que sólo promete más información.
26. **Focused:** `npm --prefix frontend test -- src/components/DiscoveryWorkflow.test.tsx src/components/DiscoveryView.test.tsx src/components/DiscoveryProduct.test.tsx src/components/DiscoveryClosure.test.tsx src/components/DiscoveryDetail.test.tsx src/components/SupportProduct.test.tsx` → **52 passed / 6 files**. Incluye periodos y límites de calendario, contexto/perfil off/on, controles/ayudas, traslado y revisión optimista, vacío honesto, CFE/Compras y flujos anteriores. Las pruebas del editor se trasladaron a su componente; no se relajaron invariantes.
27. **Frontend:** `npm --prefix frontend test` → **335 passed / 39 files**. Warning de React por key `a` duplicada en fixture de DocumentViewer; módulo fuera del hotfix y sin cambios. No falla la suite.
28. **Browser/E2E:** script nuevo `node frontend/scripts/discovery-ux-hotfix-browser.mjs backend/reports/discovery_ux_hotfix/workflow` → **9 grupos PASS**. Regresiones `ui-r2-browser.mjs` → **13**, `ui-r7-browser.mjs` → **8**, `ui-r6-browser.mjs` → **10** grupos PASS, salidas separadas bajo el mismo directorio. Ejecución secuencial con targets Chromium aislados, Vite 5181 y API interceptada. Escenario sintético 111 adquiridas/4 lotes → 111 guardadas → 1 coincidencia; no calidad semántica ni disponibilidad real de portales. Reloj del script nuevo fijo al 24/10/2026; navegación y botones no generan scans salvo el POST explícito interceptado. El script nuevo bloquea destinos HTTP externos.
29. **Build:** `npm --prefix frontend run build` PASS. JS principal 483.45 kB + chunk App 173.92 kB; CSS 38.72 kB. Sin dependencia nueva.
30. **TypeScript:** `npm --prefix frontend run typecheck` PASS.
31. **Integridad:** `git diff --check` PASS. Sin cambios en backend, migraciones, package/lock. No nuevo barrido del corpus histórico ni validación semántica/modelos reales.
32. **Capturas:** `backend/reports/discovery_ux_hotfix/workflow/`, 15 capturas listadas abajo y `contact-sheet.png`. Desktop 1440×900, 1366×768 y narrow 390×844 sin overflow global; tabla conserva scroll local. El contorno azul de la captura 02 corresponde al foco solicitado, no decoración permanente; las demás capturas normales se toman sin foco programático. Revisión visual básica, no certificación WCAG.
33. **Git:** HEAD conservado; índice vacío. Cambios del hotfix sin stage y reportes históricos/nuevo directorio de evidencia sin seguimiento. No se borraron ni editaron reportes históricos.
34. **No stage/commit/push:** confirmado. No amend, reset, clean, rebase ni reescritura de historial. No UI-R8.
35. **Revisión humana recomendada:** abrir Discovery → Nueva consulta (sin ejecutarla) → revisar periodo/ayudas → seleccionar consulta existente/Ver resultados → comparar perfil off/on → administrar perfil en Configuración → volver a Discovery → revisar historial/diagnóstico y tamaño 1366. La habilitación real permanece PEMEX=true, CFE=false, Compras MX=false/restringida; una sola consulta real PEMEX y 111 registros permanecen intactos. No se hicieron nuevas consultas públicas durante este hotfix.

## Archivos exactos

Modificados:

- docs/roadmap.md
- frontend/scripts/ui-r2-browser.mjs
- frontend/src/ProductApp.tsx
- frontend/src/api/discovery.ts
- frontend/src/components/DiscoveryClosure.test.tsx
- frontend/src/components/DiscoveryProduct.test.tsx
- frontend/src/components/DiscoveryView.test.tsx
- frontend/src/components/DiscoveryView.tsx
- frontend/src/components/SettingsView.tsx
- frontend/src/components/SupportProduct.test.tsx
- frontend/src/components/discovery.css
- frontend/src/components/supportProduct.css
- frontend/src/ui/routes.ts

Nuevos:

- docs/adr/0042-discovery-ux-workflow.md
- docs/discovery-ux-workflow-hotfix.md
- frontend/scripts/discovery-ux-hotfix-browser.mjs
- frontend/src/components/DiscoveryWorkflow.test.tsx
- frontend/src/components/SearchProfiles.tsx
- frontend/src/components/discoveryHelp.tsx
- frontend/src/components/discoveryPeriods.tsx

## Capturas y límites

`01-initial.png`, `02-query-expanded.png`, `03-query-preset.png`, `04-query-custom.png`,
`05-success-summary.png`, `06-results-context.png`, `07-profile-off.png`, `08-profile-on.png`,
`09-advanced-collapsed.png`, `10-advanced-help.png`, `11-settings-profiles.png`,
`12-history-diagnostic.png`, `13-filters-1366.png`, `13-filters-390.png`,
`14-compras-restricted.png`, `contact-sheet.png`.

Logs, `validation.json`, hashes y comprobación SQL sólo lectura bajo
`backend/reports/discovery_ux_hotfix/`, fuera del conjunto de código para revisión.
No nuevos endpoints para catálogos o pertenencia exacta a scan; ejemplos CFE no son evidencia
live ni certificación de cobertura. El historial es acotado por el contrato existente.
