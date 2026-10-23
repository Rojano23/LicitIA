# ADR-0035 — Shell de producto y navegación incremental

Estado: implementado UI-R1, pendiente de aceptación arquitectónica. Fecha:2026-10-23.
UI-R0 ACCEPTED, commit `8b51215`; MVP-01–10 CLOSED.

## Decisión

React/TS/Vite actual no incorpora router, icon pack ni sistema visual. Se añade ProductApp
como composición sobre AppShell y la UI existente, sin dependencias. Hash routes preservan
refresh/deep links sin requerir reconfiguración FastAPI/servidor. Se valida un conjunto
cerrado de destinos y se provee not-found. `/` sin hash conserva entrada funcional en Inicio.

App existente continúa como workspace; acepta ID solicitado, emite contexto desde datos
reales y conserva selección local con claves internas existentes. Navegación contextual
apunta a anclas del workspace, no desmonta componentes ni ejecuta pipeline. No se promete
separación completa de pantallas hasta los slices correspondientes. Discovery/empresa se
montan al primer acceso y se ocultan al salir para preservar formularios; workspace igual.
Coste aceptado: una vista ya visitada conserva su estado y sus efectos existentes; el polling
de procesamiento activo puede continuar oculto. No nuevos polling/fan-outs. Recarga completa
no conserva drafts no guardados, igual que antes; persistencia sólo por acciones existentes.

Reportes se incluye por instrucción UI-R1 (frente a propuesta UI-R0 de omitirlo), como destino
informativo que dirige a exports existentes de Comercial/Propuesta. No agrega reporting.
Configuración→Diagnóstico conserva workspace técnico, sin borrar observabilidad. Su separación
visual de controles heredados se completa en UI-R3–R6; no se reescriben motores ni contratos.

Tokens CSS semánticos, system fonts locales y marca tipográfica RX23 TuScope. Sin CDN,
framework/icon pack/renaming interno, migración ni backend. Nombre visible en copy frontend
cambia; claves/archivo de intercambio y metadata de exports siguen compatibles.

## Validación

Tests de routing con fixtures aisladas, regresión frontend existente y navegador Chromium
local mediante CDP sin dependencia nueva. Fixtures sólo viven en tests/script de aceptación;
red API interceptada sin DB/portales, capturas marcadas sintéticas. Ver doc UI-R1 para comandos,
resultados, limitaciones y revisión visual. No claim WCAG ni calidad semántica basado en mocks.
