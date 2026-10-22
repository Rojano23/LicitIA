# MVP-07 — Commercial Traceability & Pricing Assist

**MVP-07 CLOSED — aceptación arquitectónica formal. M7-A/B/C/D ACCEPTED.** Base M7-C `d22cf3ed24d9529093513829d3a784dc63cadd62`.

## Propósito y capacidades

Decisiones de costo/precio ligadas al Scope, con Quantity heredada, trazabilidad de costo,
cálculo determinista, override humano, matriz/bulk y round trip XLSX/CSV seguro. Un usuario
puede trabajar en Workspace o exportar → editar → cargar → preview → confirmar; ambos
caminos usan los mismos servicios. No reingresa Scope/Quantity/fuente ni se pierde historia.

[Fundación y fórmulas](commercial-foundation.md), [matriz/bulk](commercial-matrix.md),
[round trip](commercial-spreadsheet-roundtrip.md), [decisión M7-D](adr/0025-commercial-readiness-projections.md).

Markup = (precio−costo)/costo×100; margen = (precio−costo)/precio×100.
COST_FIRST/MARKUP recomienda costo×(1+markup/100); COST_FIRST/MARGIN recomienda
costo/(1−margen/100). PRICE_FIRST conserva el precio humano. Decimal, precisión y
redondeos siguen commercial-v1; falta de costo deja utilidad/ratios sin resolver,
no cero. Guardar una regla no obliga a aceptar la recomendación. Precio manual protegido;
reemplazarlo requiere acción explícita. Sin FX, totales sólo por moneda/cobertura.

## Un contrato canónico de readiness

`commercial-readiness-v1` por Scope: READY, INCOMPLETE o REVIEW_REQUIRED, razones
estructuradas (code, severity), warnings y proposal_eligible. El mismo evaluador puro
alimenta cálculo, línea, matriz, UI, bulk e imports; no readiness especial para Excel.

| Condición | Severidad | Consecuencia |
| --- | --- | --- |
| Falta línea, precio, moneda o Quantity canónica resoluble | BLOCKER | INCOMPLETE |
| COST_FIRST sin decisión manual y sin costo/regla válidos | BLOCKER | INCOMPLETE |
| Scope/Quantity pendientes, fuente no disponible/contexto cambiado, cálculo aplicado obsoleto, valor negativo o warning desconocido | REVIEW | REVIEW_REQUIRED si no hay blocker |
| Precio bajo costo, costo desconocido con precio manual, cero, soporte/referencia quote ausente | WARNING | No impide READY por sí sola |
| Regla de recomendación incompleta/inválida con precio manual explícito | WARNING | Se conserva precio; la recomendación puede seguir sin resolver |

Si coinciden faltantes y revisión, estado INCOMPLETE y se conservan todas las razones.
La revisión no desaparece por introducir un precio. No se exige una cotización a fuentes
INTERNAL_COST/MANUFACTURER_COST/MANUAL. SUPPLIER_QUOTE sin referencia documental,
quote_reference o reference_party_reference muestra COST_SOURCE_REFERENCE_MISSING,
sin inventar un requisito contractual. CONFIRMED_QUOTE sin soporte conserva su warning.
Actor/origen/manual quedan trazables; no se exige justificación extensa para cada edición.
Pérdida explícita queda visible como warning, sin requerir un nuevo flujo de aprobación.

Readiness no convierte en evidencia canónica un preview no aplicado. Un conflicto de
spreadsheet se resuelve en ese flujo; no invalida por sí solo la decisión vigente que
logró proteger. SOURCE_CONTEXT_CHANGED/PRICE_CALCULATION_STALE persistidos sí exigen revisión.

## API y consumidores

GET `/tenders/{id}/commercial-readiness`: estado Tender, total_scope_items, ready_count,
incomplete_count, review_required_count, warning_count (sólo WARNING),
missing_commercial_treatment_count, items, summary_by_currency y state_reference.
Tender sin Scope es INCOMPLETE. No existe gran total entre monedas.
GET `/tenders/{id}/scopes/{scope_id}/commercial-readiness`: mismo contrato por Scope.

MVP-08 consume Scope ID, readiness/reasons/warnings, offered_price_present, currency,
cost_source_present/type, unresolved_cost y review_required. No necesita entender
cálculo, markup/margen, historial o estrategias de pricing. No Bid Readiness global aquí.

GET `/tenders/{id}/commercial-proposal`: `commercial-proposal-v1`, filas elegibles
READY con Scope ID, item_reference, descripción efectiva, Quantity/unit canónicas,
precio/total ofertado, moneda, nota, estado y warnings. Excluded informa readiness
por Scope de las demás filas. No costos internos ni auditoría innecesaria. Precio manual
sin costo puede ser elegible si contexto/Quantity están resueltos. Sin editar Quantity ni
generar archivos de propuesta. Una fila no recibe Quantity de otro padre.

`state_reference` es SHA-256 determinista del estado leído (revisiones, fingerprint,
inputs, resultado); cambia al cambiar decisiones/evidencia. No es un bid freeze ni una
garantía transaccional del Tender completo. Lock/snapshot final se difiere a MVP-08/09.

## Auditoría

GET `/tenders/{id}/scopes/{scope_id}/commercial-audit?limit=25&before_revision=…`:
`commercial-audit-v1`, inputs actuales, revisión actual y manual flag, eventos descendentes,
next_before_revision. Limit 1–100. Cada evento contiene timestamp UTC, origen UI/API/BULK/
XLSX/CSV, acción exacta, actor declarado cuando existe, precio/recomendación histórica,
diff antes/después, nota y metadata hash de import si aplica. No reinterpreta cálculos
históricos. APPLY_CALCULATION es acción API aunque inputs conserven origen anterior.
No actor autenticado: no atribuir autenticidad a actor_label.

UI provisional en matriz: resumen/readiness/razones e historial por fila a solicitud,
con paginación. Refrescar una fila/revisión remonta su historial; sin streams/logs nuevos.
Historial de Scope retirado sigue consultable por API, sin reparentar decisiones.

## Límites de cierre

Sin migración (Alembic 073), dependencia nueva, proveedores ni cambios semánticos MVP-06.
Quantity audited review continúa diferido; una Quantity pendiente impide elegibilidad
hasta resolverla mediante un contrato futuro autorizado, no se ignora su revisión.
Defaults de sesión, máximo 100 por bulk; XLSX/CSV conservan límites/TTL M7-C.

Sin ERP, estimating engine, inventario, purchasing, accounting, sourcing/interpretación
automática de quotes, FX, optimización, escenarios nuevos, propuesta o UI final.
Próximo paso: revisión arquitectónica del cierre y posterior definición de MVP-08.
