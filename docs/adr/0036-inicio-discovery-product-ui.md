# ADR-0036 — Inicio y Discovery sobre contratos existentes

Estado: UI-R2 implementado, pendiente de revisión arquitectónica/visual. Fecha:2026-10-23.
UI-R1 ACCEPTED y comprometido en `d0398f17f4b46c4a74046513aaced1451ad52951`.

## Decisión

Inicio compone cuatro lecturas locales existentes: summary Discovery, hasta5 oportunidades
watching con cambios SOURCE sin leer,20 scans recientes y lista Tender. Sólo dos métricas
canónicas (NEW y watching+unread); atención por grupos, sin score transversal ni fanout por
Tender. Se muestran hasta3 consultas fallidas/parciales del conjunto20 y5 Tenders ordenados
por updated_at/ID; esa fecha se etiqueta actualización de registro, no fecha contractual.
Fallos independientes no fabrican cero ni borran las otras secciones. No nuevos endpoints,
modelos, migraciones, persistencia, dependencias o AI.

Discovery conserva handlers y DTO existentes, reorganizados como tabla principal + filtros
locales + controles secundarios de consulta pública/perfiles. Filtros de adquisición separados
de filtros locales; páginas usan los últimos filtros aplicados con éxito, no borradores.
Navegación desde métricas limpia filtros anteriores para corresponder al agregado global.
Hash query parameters view/opportunity/scan/source sólo direccionan vistas existentes.
La vista visitada se conserva en el shell; otras rutas no alteran sus filtros ni provocan
consultas adicionales. Entradas explícitas desde Inicio reaplican el destino solicitado.

Source capability restringida se expresa neutralmente, sin Scan ni adquisición; las lecturas
de metadata/historial locales no contactan Compras MX. Todos los guards de backend permanecen.
Handoff sigue preview readonly, binding, selección vacía y confirmación explícita; refresh
invalida confirmación, importaciones parciales conservan outcomes. No se altera dominio.
Historia mantiene orden backend ascendente y paginación; raw codes/hashes sólo bajo detalle.

## Validación y límites

Tests locales deterministas prueban contratos, no relevancia contractual ni disponibilidad
real de portales. Browser CDP intercepta API exclusivamente con fixtures de test; no datos
sintéticos en runtime. Datos locales persistidos no equivalen a cobertura nacional ni a
snapshot remoto atómico. Inicio no agrega readiness/propuestas globales inexistentes.
No scheduler, procesamiento documental, fuentes adicionales, FX ni analítica nueva.
