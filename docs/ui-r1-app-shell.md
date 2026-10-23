# UI-R1 — App shell, navegación y sistema visual

Estado: implementado, listo para revisión arquitectónica/visual; **sin stage/commit/push**.
Fecha:2026-10-23. MVP-01–10 CLOSED. UI-R0 ACCEPTED.
[Especificación de producto](RX23_TUSCOPE_PRODUCT_UI_RECONCILIATION_v1.md),
[decisión de integración](adr/0035-product-ui-shell-navigation.md).

## Reporte final

1. **UI-R0 commit:** `8b5121584f0f0c33653d9fcc99f0facd5f1b3091`,
   `docs(ui): define rx23 tuscope product experience`.
2. **HEAD resultante:** mismo SHA; UI-R1 no comprometido. Sin push.
3. **Archivos comprometidos UI-R0:** README.md, docs/roadmap.md,
   docs/PRODUCT_UI_BLUEPRINT_v0.1.md, docs/RX23_TUSCOPE_PRODUCT_UI_RECONCILIATION_v1.md.
4. **Arquitectura encontrada:** React18/TS estricto/Vite, axios, Vitest/jsdom/Testing Library;
   App monolítico con selección local/handlers y componentes funcionales. Sin router ni icon pack.
   Sin browser runner propio; Chromium de pruebas local disponible en cache.
5. **AppShell:** sidebar y main semántico, skip link, header compacto y contenido min-width0;
   ProductApp compone shell y superficies existentes. No tarjetas anidadas para toda la página.
6. **Sidebar:** Inicio, Discovery, Licitaciones, Mi empresa, Reportes, Configuración;
   marca tipográfica y utilidad Trabajo local/Diagnóstico. Reportes responde a instrucción UI-R1:
   explica que los archivos se generan en Comercial/Propuesta, sin nueva función ni KPI.
   Diferencia explícita respecto de omisión sugerida en UI-R0, documentada en ADR0035.
7. **Contexto Tender:** título/referencia/estado de datos reales; ocho enlaces Resumen,
   Documentos, Requisitos, Cumplimiento, Partidas, Comercial, Preparación de oferta y Propuesta.
   No duplicados de features Tender en sidebar global. Enlaces apuntan a secciones existentes,
   no son todavía pantallas rediseñadas separadas. ID preservado en URL y selección local.
8. **Rutas:** `#/`, `#/discovery`, `#/licitaciones`,
   `#/licitaciones/{id}/{resumen|documentos|requisitos|cumplimiento|partidas|comercial|preparacion|propuesta}`,
   `#/mi-empresa`, `#/reportes`, `#/configuracion`, `#/configuracion/diagnostico`.
   Hash soporta refresh sin cambiar servidor; historial/back nativo. Not-found acotado,
   ID codificado validado contra lista real; loading/error/no disponible explícitos.
9. **Branding:** RX23 TuScope en shell, título browser, encabezado legacy y copy frontend;
   lang es-MX. Sin logo complejo/favicon externo, favicon nuevo no requerido.
10. **Strings:** reemplazados títulos/copy visibles en App, ScopeReview, CompanyEvidenceLibrary
    y CommercialSpreadsheet; tests de copy actualizados. Conservados paquetes, DB/migraciones,
    storage keys `licitia_selected_tender_id`/`licitia_selected_company_id`, nombre de archivo
    intercambio `licitia-commercial.*`, metadata y fixtures/documentos históricos. Sin replace global.
11. **Tokens:** `frontend/src/ui/shell.css`: backgrounds, text, border/focus, action y estados;
    sidebar/page max, spacing, radios y escalas tipográficas. Base index.css consume tokens.
    Estilos inline legacy conservados para evitar rediseño de features fuera del slice.
12. **Paleta:** fondo#f7f9fb, navy#091426/slate#1e293b, superficies#fff/#f2f4f6,
    texto#191c1e/#45474c, azul#1d4ed8; estados verde#166534, ámbar#854d0e, rojo#b91c1c
    con fondos suaves. Sin glow, gradient, glass ni efectos animados.
13. **Tipografía:** system-ui/Apple/Segoe UI locales; Inter no se distribuye localmente y no
    se agregó CDN. Página30px, sección20px, cuerpo14px y secundario/caption13px; números tabulares.
14. **Espaciado:**4/8/12/16/24/32px; sidebar260px, página hasta1600px, padding24/16 compacto;
    controles36px, filas40px, celdas8x12px.
15. **Forma:** radios2/4/8px, badge12px; bordes sutiles, controles con borde identificable;
    ninguna sombra nueva. Selección/foco visibles, no sólo cambio de color de texto.
16. **Compartidos:** AppShell, TenderContextNav, PageHeader, Button primary/secondary/ghost/
    destructive, StatusBadge, SourceBadge, Notice, EmptyState, LoadingState, ErrorState,
    SummarySurface y TableShell. No motor de spreadsheet, MetricCard ni feature drawer nuevo.
    Los componentes base se prueban, no se aplican masivamente a cada feature heredada.
17. **Iconos/dependencias:** ninguna dependencia añadida; nav con texto, sin iconos decorativos
    ni paquete nuevo. Prueba browser por CDP/WebSocket nativo Node26; script fuera de runtime.
18. **Vacíos:** Inicio acotado sin datos ficticios, Reportes informativo con destino real,
    not-found con regreso y Tender no disponible con selección alternativa; base EmptyState.
19. **Carga:** LoadingState role=status, carga de Tender real al entrar por URL; no KPI cero
    ni porcentaje/ETA fabricado. Cargas feature continúan locales.
20. **Error:** ErrorState role=alert con mensaje de producto, sin exponer excepción/payload;
    error de lista/creación traducido. Errores y diagnóstico legacy siguen disponibles.
21. **Restricción:** SourceBadge acepta restricted y texto “Automatización no disponible
    actualmente”; no botón ni red. Discovery conserva su guard Compras MX existente.
22. **Diagnóstico:** utilidad secundaria y ruta Configuración→Diagnóstico, reusa workspace
    técnico completo. No se borró auditoría/percepción. La separación visual de todos los
    controles técnicos dentro de pantallas heredadas se completa en UI-R3–R6.
23. **Accesibilidad:** landmarks/nav labels, un h1 del shell, aria-current, foco visible,
    skip link, controles con texto, Escape devuelve foco al menú y estado no sólo por color.
    Contraste calculado de tres pares shell/nav/acción >=4.5:1. No certificación WCAG:
    matrices/controles legacy y lector de pantalla aún requieren revisión posterior.
24. **Responsive:** desktop sidebar fijo sticky, main flexible; bajo1024 menú expandible
    en flujo (no overlay que tape contenido), Escape/cierre al navegar. Workspace heredado
    tiene scroll horizontal local; picker pasa a columna bajo1100. Tab context tiene scroll propio.
25. **Focused:** `npm --prefix frontend test -- src/ui/Shell.test.tsx src/App.test.tsx`
    →9passed (6nuevos shell +3App) en validación inicial. Suite final vuelve a incluirlos.
    Shell tests prueban rutas/drafts/estados; App tests usan APIs sintéticas con UI real.
26. **Frontend completo final:** `npm --prefix frontend test` →184passed/22files;
    incluye Discovery (API/View/Detail/Closure), Tender, Scope review, comercial y Propuesta.
27. **Browser/rutas:** `node frontend/scripts/ui-r1-browser.mjs backend/reports/ui_r1/browser`
    →13 grupos PASS. Chromium CDP local, intercepta API con fixtures sintéticas aisladas;
    sin escrituras, portales ni DB de producto. Valida destinos, ocho secciones, teclado,
    no refetch entre tabs, overflow, narrow, contraste y ninguna excepción runtime.
28. **Build/types:** `npm --prefix frontend run build` y `npm --prefix frontend run typecheck`
    PASS. Bundle515.52kB antes de documentación, warning>500kB preexistente; sin error.
    No se amplía el slice con división de bundle ni dependencias de visual testing.
29. **Backend acotado:** desde backend,
    `DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_scope_review_api.py tests/test_alternative_compliance_api.py -q`
    →60passed,6warnings deprecación Swig,590.06s. No backend producción modificado;
    no suite2510 repetida por cambio frontend. `compileall -q app scripts tests` PASS.
30. **Alembic:** mismo intérprete + DATABASE_URL test, `-m alembic current` y `heads`
    →`20261023_discovery_079 (head)`. Sólo lectura, sin upgrade/migración nueva.
31. **Históricos:** hash-only sobre manifests protegidos →5941/5941 intactos, cero diferencias;
    `backend/reports/ui_r1/historical_integrity.json`. No inspección semántica de Tender002.
32. **Archivos UI-R1 exactos:**
    - frontend/index.html
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/src/main.tsx
    - frontend/src/index.css
    - frontend/src/ProductApp.tsx (nuevo)
    - frontend/src/components/WorkspaceFlow.tsx
    - frontend/src/components/ScopeReview.tsx
    - frontend/src/components/ScopeReview.test.tsx
    - frontend/src/components/CompanyEvidenceLibrary.tsx
    - frontend/src/components/CommercialSpreadsheet.tsx
    - frontend/src/ui/AppShell.tsx (nuevo)
    - frontend/src/ui/routes.ts (nuevo)
    - frontend/src/ui/primitives.tsx (nuevo)
    - frontend/src/ui/shell.css (nuevo)
    - frontend/src/ui/Shell.test.tsx (nuevo)
    - frontend/scripts/ui-r1-browser.mjs (nuevo)
    - docs/adr/0035-product-ui-shell-navigation.md (nuevo)
    - docs/ui-r1-app-shell.md (nuevo, este reporte)
    - docs/roadmap.md
    Reportes/capturas locales bajo backend/reports/ui_r1 no se incluyen en staging.
33. **Dependencias añadidas:**0, lockfiles/package sin cambios.
34. **Límites:** navegación contextual es fundamento por anclas al workspace completo;
    no rediseño ni partición de features. Mantener vistas visitadas preserva formularios,
    pero efectos/polling existentes de procesamiento pueden seguir ocultos; no nuevos timers.
    Refresh completo pierde borradores no guardados igual que antes. App conserva múltiples
    lecturas al seleccionar Tender; tabs no disparan lecturas adicionales. Capas técnicas
    heredadas siguen en workspace hasta sus slices. Reportes no genera reportes globales.
    Screenshots no prueban calidad DI ni comportamiento de portales/proveedores reales.
35. **Capturas:**11 PNG de estado local determinista de prueba, en
    `backend/reports/ui_r1/browser/`: Inicio1366, Discovery1366, Tender1366, tres desktop,
    Configuración, Diagnóstico, menú768, Tender768, Inicio390; results.json conserva evidencia.
    Se inspeccionaron visualmente Inicio, Discovery, Tender, desktop1440/1920 y menú estrecho.
36. **1366×768:** PASS shell/sidebar/header; controles legacy pueden requerir scroll local.
37. **1440×900:** PASS shell/header, sin overflow de página en caso inspeccionado.
38. **1920×1080:** PASS límite de contenido, sidebar estable y sin superposición.
39. **Narrow:**768×900 menú expand/collapse y Tender accesibles;390×844 Inicio cabe,
    sin overflow global observado. No certificación mobile de todas las tablas feature.
40. **Gates A–O:** PASS para alcance UI-R1. Matriz de evidencia abajo; limitaciones34 no
    representan rediseño final terminado. No datos/métricas ficticios ni lógica de dominio nueva.
41. **Listo para commit:** sí, sujeto a aceptación arquitectónica/visual. UI-R1 sigue unstaged,
    uncommitted/unpushed. Sólo UI-R0 se comprometió por autorización explícita.
42. **UI-R2 recomendado:** Inicio con contadores deterministas autorizados y Discovery integrado
    (lista/perfiles/consultas/detalle/historia/preview/handoff), conservar paginación total,
    parcialidad y restricción Compras; sin nuevas fuentes/backend/scheduler/AI. No UI-R3–R7 ahora.

## Gates y evidencia

| Gate | Resultado | Evidencia |
|---|---|---|
| A marca/shell | PASS | título/lang y captura Inicio |
| B Stitch | PASS | tokens navy/light, sidebar260, comparación visual |
| C navegación global | PASS |6 destinos y rutas tipadas; Reportes acotado |
| D contexto Tender | PASS |8 enlaces sin features root |
| E no mock runtime | PASS | fixtures sólo test/script, runtime axios real |
| F no KPIs fake | PASS | Inicio vacío accionable, sin números de ejemplo |
| G dominio intacto | PASS | diff sin backend, wrappers/anclas no extraen ni calculan |
| H esquema | PASS | Alembic079, sin migraciones |
| I accesibilidad funcional | PASS | workspace/empresa/Discovery/propuestas preservados |
| J diagnóstico secundario | PASS | utilidad/ruta Configuración, sin eliminar observabilidad |
| K tokens | PASS | shell.css + base consumidora |
| L desktop | PASS | screenshots y bounds browser3resoluciones |
| M narrow | PASS |768 menú+Tender,390 Inicio |
| N a11y básica | PASS | foco/skip/labels/current/Escape/contraste básico |
| O regresión | PASS | frontend184,API60,build/types/compileall/diff |

## Reproducción del ensayo visual

1. Desde frontend: `npm run dev -- --port 5181`.
2. Abrir Chromium local con `--headless --remote-debugging-port=9331` y user-data-dir
   temporal aislado. No reutilizar perfiles/cookies del usuario.
3. Desde raíz: comando browser del punto27. No necesita servidor8000: todo HTTP API8000
   se intercepta dentro de la página de pruebas; no lleva fixtures a runtime.
4. Revisar results.json y PNG. El script no descarga binarios ni consulta Compras/PEMEX/CFE.

Artefactos locales adicionales: logs de focused/frontend/build/typecheck/backend,
validation.json, brand audit y archivo de commit UI-R0. Se conservan fuera del commit.
