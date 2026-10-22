# MVP-07 M7-A — Commercial Traceability & Pricing Assist

Estado: M7-A ACCEPTED; commit autorizado, sin push. La aceptación no certifica decisiones comerciales particulares.
Baseline `6fab7612ed0cbf6659cb1cf985d3becbd60350d8`. [ADR-0022](adr/0022-commercial-line-calculation-traceability.md)
contiene inventario, revisión OSS/licencias y esquema diseñado antes de la migración.

## Contrato de producto

Una CommercialLine por Tender + identidad original de Scope. El Scope, descripción,
Quantity, unidad, documento, página y revisión se consultan del dominio vigente.
Snapshots de auditoría no sustituyen esa evidencia. No es necesario cotizar con un
proveedor: SUPPLIER_QUOTE, INTERNAL_COST, MANUFACTURER_COST, HISTORICAL_REFERENCE,
ESTIMATE, MANUAL y NOT_APPLICABLE son fuentes válidas. NOT_APPLICABLE no implica cero.

Origen económico separado: CONFIRMED_QUOTE, HISTORICAL_COST, SYSTEM_ESTIMATE,
MANUAL_INPUT. El usuario declara el origen del costo; el sistema no certifica una
cotización sólo por seleccionar su tipo. Sin documento ni referencia, un origen
CONFIRMED_QUOTE muestra QUOTE_SUPPORT_UNSPECIFIED. Parte de referencia libre
(nombre/referencia/nota) y documento de cotización opcionales. Un documento existente
puede respaldar varias líneas del mismo Tender; no hay catálogo de proveedores.

La Quantity heredada debe ser un hijo canónico del mismo Tender/Scope con relación
EXACT, valor numérico no negativo y evidencia válida. Un único hijo permite selección
implícita; varios exigen seleccionar un ID canónico. Nunca se asume 1. Rango, ausencia,
fuente inválida o selección eliminada deja totales sin resolver. Seleccionar un hijo
ajeno se rechaza. Confirmar Scope no confirma Quantity; sus estados siguen separados.

## Cálculos

Valores monetarios son strings decimales finitos en API; enteros también se aceptan.
No floats/bool/NaN/Infinity. Numeric(24,6): hasta 18 enteros/6 fracciones; targets
Numeric(18,8). Entradas manuales fuera de representación se rechazan sin redondearlas.
Contexto local Decimal: precisión 50, ROUND_HALF_UP, independiente del contexto ambiental.
Monedas M7-A: MXN, USD, EUR, dos decimales en totales; no hay FX, impuestos ni conversiones.
El precio recomendado se redondea a seis decimales. Ratios son porcentajes base 100 a ocho
fracciones. La unidad/precio no debe confundirse con el total redondeado.

| Modo | Fórmula |
| --- | --- |
| COST_FIRST / MARKUP | recomendación = costo × (1 + markup / 100), markup ≥ −100 |
| COST_FIRST / MARGIN | recomendación = costo / (1 − margen objetivo / 100), margen < 100 |
| PRICE_FIRST | usuario elige precio; ratios efectivos se derivan de costo/precio |
| Costo total | round(costo unitario × Quantity, 2) |
| Total ofertado | round(precio elegido × Quantity, 2) |
| Utilidad | total ofertado redondeado − costo total redondeado |
| Markup efectivo | (precio − costo) / costo × 100 |
| Margen efectivo | (precio − costo) / precio × 100 |

Costo cero deja markup null; precio cero deja margen null. Costo desconocido no se
convierte en cero: precio/total ofertado pueden existir con utilidad/ratios null.
Falta de moneda admite borrador, pero no importes totales ni recomendación sin denominación.
El helper de agregación deja total null ante mezcla de monedas o totales incompletos;
no existe matriz ni agregación global en UI/API M7-A.

## Decisión humana e historial

Guardar costo/regla nunca sustituye el precio elegido cuando el campo de precio no se
envía. Enviar explícitamente offered_unit_price es una decisión MANUAL/MANUAL_INPUT.
Una recomendación sólo se aplica mediante calculate con apply_calculated_price=true;
reemplazar MANUAL requiere además replace_manual_price=true y confirmación en UI.
El nuevo precio aplicado es CALCULATED/SYSTEM_ESTIMATE. Cambiar después una regla
conserva también un precio calculado anterior y marca PRICE_CALCULATION_STALE.
No hay optimización silenciosa ni ocultamiento de pérdidas.

Revisiones inmutables guardan inputs, método/origen, fecha UTC, UI/API, etiqueta de actor
opcional declarada (no autenticada), acción, fingerprint/snapshot de evidencia y resultado
con versión commercial-v1. Una actualización idéntica no crea revisión duplicada.
La API exige revisión vigente y fingerprint actual; conflictos devuelven 409.
Cambios de fuente producen SOURCE_CONTEXT_CHANGED y requieren refrescar/confirmar
contexto al guardar. Un Scope eliminado anula sólo el vínculo vivo; identidad e historia
permanecen consultables por el Scope original, sin totales ni reatachado automático.

READY/INCOMPLETE/REVIEW_REQUIRED es preparación comercial, nunca certificación contractual.
Warnings de moneda/precio/costo/cantidad ausentes, pérdida, negativos, targets inválidos,
ambigüedad, fuente/revisión pendiente y contexto stale permanecen visibles. No impiden
guardar un borrador estructuralmente válido. Rechazar tipos no representables o asociaciones
ajenas protege integridad; no es un bloqueo por estrategia comercial.

## API aditiva

Base: `/tenders/{tender_id}/scopes/{scope_id}/commercial-line`.

- POST crea, 201; si ya existe, 409. No hay escritura automática por consultar Workspace.
- GET consulta decisión, inputs, evidencia, resumen e historia. GET `/summary` devuelve
  el mismo contrato completo con resumen derivado.
- PATCH parcial: expected_revision y expected_source_fingerprint obligatorios; no enviar
  campos sin editar. Cantidad comercial libre/override no existe.
- POST `/calculate`: mismas expectativas, preview sin escribir por defecto. Aplicación
  explícita y protección de manual descritas arriba. Si no hay recomendación, 409.

Workspace agrega un panel lazy por Scope: fuente/origen, referencia, costo/moneda,
modo/regla/targets, precio y notas; muestra recomendación, totales, utilidad/ratios,
readiness, warnings e historia. Quantity ambigua se selecciona de los hijos existentes.
No aritmética monetaria autoritativa en JavaScript. Errores conservan entradas y piden
revisar/refrescar; una lectura fallida no habilita crear a ciegas.

## Migración y operación

Alembic `20261021_commercial_073` → padre `20261013_req_perception_prov_072` agrega
commercial_lines/commercial_line_revisions. FK de Tender/documento y revisiones RESTRICT;
Scope vivo SET NULL. Triggers preservan identidad, propiedad Tender y auditoría.
Sin cambios a tablas, servicios o políticas semánticas MVP-06. Un downgrade elimina
historia comercial: sólo operación administrativa deliberada, nunca mecanismo de retry.
Las pruebas ejecutan upgrade en licitia_test y downgrade/upgrade DDL dentro de una
transacción revertida. No migrar/resetear roots o DBs congelados de validación.
Para una instalación de desarrollo nueva/vigente, usar el comando Alembic documentado
con su DATABASE_URL explícito; M7-A no migra licitia_dev automáticamente.

## Límites y continuación

Sólo una estrategia actual por Scope, con revisiones; sin escenarios alternativos,
componentes, impuestos, FX, vendor DB, parsing automático, ERP ni precios inferidos.
Decimales/montos están acotados; otras monedas requieren política de fracciones explícita.
Actor no autenticado y acceso Controlled Limited UAT siguen vigentes. No se implementan
XLSX/CSV, bulk/defaults, matriz final, propuesta ni Bid Readiness.

M7-B debe reutilizar estos servicios para matriz/bulk/defaults con cambios explícitos,
previsualización, concurrencia y respeto de overrides. M7-C añade round trip XLSX/CSV
con reconciliación, y M7-D completitud/auditoría/contratos MVP-08/MVP-09.

Los fixtures de replay offline de Tender #001 declaran temporalmente 073 como contrato
para la regresión sobre la base viva; no se cambia el código del replay histórico ni
el perfil blind 072. La comparación de drift comprueba los mismos índices certificados
con head 073 y además exige que verify_accepted_drift siga rechazándolo frente al
contrato congelado 072. Esto no autoriza ni certifica un nuevo Blind Attempt.

Una identidad cuyo Scope fue eliminado se consulta mediante el API y su Scope ID
histórico; el Workspace actual no agrega una lista de líneas archivadas. Esa visibilidad
y lectura eficiente de varias líneas son consideraciones para la matriz M7-B.
