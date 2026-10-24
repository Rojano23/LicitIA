# ADR-0039 — Comercial, Preparación y Propuesta en Product UI

Estado: implementado, pendiente revisión arquitectónica y visual UI-R5.

## Decisión y autoridad

Separar las tres rutas operativas del montaje de App/Diagnóstico, sin cambiar los
contratos MVP-07/08/09. ProductApp monta CommercialView, ReadinessView y
ProposalVersions en modo producto. Se conservan las vistas visitadas del mismo Tender,
y se remontan por identidad al cambiar Tender. Diagnóstico sigue accesible.

CommercialView presenta una tabla de lectura de la matriz canónica y detalle por Scope.
CommercialLine conserva guardar/calcular, expectativas y confirmación de precio manual.
CommercialMatrix/CommercialSpreadsheet conservan edición en lote, borradores, defaults de
sesión, preview, identidad, importación/exportación y confirmaciones. Su editor completo
queda bajo una sección secundaria, evitando duplicar esa lógica en un segundo motor.
La tabla principal se actualiza explícitamente tras operaciones de lote; al guardar una
línea se vuelve a consultar. Los subtotales se reciben del servidor por moneda.

ReadinessView consume el board canónico paginado (50), con prioridad del servidor y
seguimiento humano bajo detalle. El estado fuente nunca se deriva del cierre de trabajo.
ProposalReadiness conserva captura explícita e historial, separados del estado consultado.
ProposalVersions permite elegir capturas reales e inspeccionar versiones; composición,
respuestas humanas, congelado y exports reutilizan comandos existentes.

## Invariantes

- Ningún cálculo de precio, margen, markup, subtotal o elegibilidad se traslada a JS.
- Los importes se formatean desde strings decimales, sin Number, redondeo ni FX.
- No hay vigencia/fecha de cotización en el DTO comercial: no se inventan estados.
- Frozen sigue inmutable; la captura fija no se reemplaza por los datos actuales.
- Freshness se consulta aparte; falta de consulta no significa CURRENT.
- Hashes/IDs/payloads técnicos quedan bajo detalle. Son integridad, no firma.
- Las lecturas de entrada sólo usan GET locales. No generan propuestas, snapshots,
  imports, análisis, OCR, Vision ni solicitudes a proveedores.
- useRead invalida generaciones; editores por Scope/Tender/versión se remontan por key.
  Inspección de versión valida pertenencia e identidad y descarta generaciones anteriores.
- Fallos de export no eliminan el listado previo ni cambian la versión; el retry conserva
  la solicitud canónica. Intercambio comercial y XLSX de propuesta permanecen separados.

## Alcance y límites

Backend, esquema079 y dependencias intactos. Sin renombrado interno, motor comercial,
catálogo de proveedores, edición Quantity ni rediseño de Empresa/Reportes/Configuración.
Drafts de edición viven en memoria. No hay certificación contractual, WCAG ni calidad
semántica demostrada por fixtures. Los contratos de lista de versiones no exponen fechas:
se muestran fechas disponibles de capturas, auditoría y artefactos, sin inventarlas.

## Refinamiento final autorizado del shell —2026-10-24

AppShell posee exclusivamente el estado de presentación desktop expanded/collapsed.
Se persiste `tuscope.sidebar.desktop` en localStorage (`expanded`/`collapsed`), con
fallback expandido para ausencia, valor desconocido o almacenamiento no disponible.
No hay efecto de persistencia/lectura de dominio ni cambio de key de los hijos.

260px→64px en desktop≥1024px; grid y máximo del workspace recuperan196px, también
cuando aplica el máximo de escritorio ancho. En narrow, el drawer existente conserva
etiquetas completas; la preferencia desktop no impone un rail permanente. No animación.
La infraestructura original no incluía icon pack: se usan SVG nativos en línea y el
Button compartido, sin nueva dependencia, fuente, asset remoto o navegación paralela.

Nombres accesibles/title, foco visible y aria-current preservados. Marca RX23 tipográfica
compacta; TenderContextNav y proporción fija del registro documental sin cambios.
La tabla de integridad dice Ver detalle y mantiene SHA dentro; no añade una afirmación
Verificado por archivo ni modifica el estado de verificación recibido.
