# ADR-0022 — M7-A, línea comercial y decisión humana

Estado: aceptado arquitectónicamente — M7-A ACCEPTED. Baseline `6fab7612ed0cbf6659cb1cf985d3becbd60350d8`.

## Inventario y revisión previa

Persisten TenderScopeDetail, TenderScopeQuantity, documentos/versiones/manifests,
Scope Review, alternativas/revisiones y decisiones de cumplimiento. No existen modelos
comerciales ni Supplier/Quote/CostComponent persistidos; aparecen sólo como visión futura.
Se reutilizan lectores/validadores canónicos de Scope/Quantity y el patrón identidad +
revisiones append-only de ADR-0008. No se convierte Scope Review en revisión de cantidades.

Referencias examinadas (sin copiar código ni instalar dependencias):

| Proyecto | Licencia verificada | Patrón usado como referencia |
| --- | --- | --- |
| [py-moneyed](https://github.com/py-moneyed/py-moneyed), [licencia](https://github.com/py-moneyed/py-moneyed/blob/master/LICENSE), [uso](https://github.com/py-moneyed/py-moneyed/blob/master/docs/usage.rst) | BSD-3-Clause | Decimal desde strings; importe con denominación; no sumar monedas diferentes |
| [Dinero.js](https://github.com/dinerojs/dinero.js), [licencia](https://github.com/dinerojs/dinero.js/blob/main/LICENSE) | MIT | Operaciones puras, precisión explícita, importes inmutables; frontend sin aritmética monetaria autoritativa |
| [django-simple-history](https://github.com/django-commons/django-simple-history), [licencia](https://github.com/django-commons/django-simple-history/blob/master/LICENSE.txt), [documentación](https://github.com/django-commons/django-simple-history/blob/master/docs/quick_start.rst) | BSD-3-Clause | Historial de estados y metadatos de cambio separado del registro actual |

Decimal stdlib, SQLAlchemy y Pydantic existentes bastan para este contrato acotado.
No se adopta Django/ERP, no dependencias ni nuevas obligaciones transitivas.

## Esquema propuesto ANTES de crear la migración

Dos tablas nuevas, sin cambiar tablas/semántica MVP-06:

- `commercial_lines`: UUID estable, tender_id FK RESTRICT, scope_detail_id FK nullable
  SET NULL, scope_id_at_creation histórico inmutable, snapshot inicial para auditoría,
  created_at UTC. UNIQUE(tender_id, scope_id_at_creation) garantiza una decisión actual
  por identidad Scope; UNIQUE(id,tender_id) soporta FK compuesta de revisiones.
- `commercial_line_revisions`: UUID, line_id/tender_id FK compuesta RESTRICT,
  revision positiva única por línea, cost_source_type, cost_value_origin, referencia
  de parte (nombre/referencia/nota), quote_document_id FK opcional RESTRICT al documento
  del mismo Tender, quote_reference opcional, currency nullable, unit_cost y
  offered_unit_price Numeric(24,6), calculation_mode, calculation_basis, markup_percent y
  target_margin_percent Numeric(18,8), quantity_id opcional como selección histórica
  (no FK viva: los hijos Quantity pueden regenerarse), notes, price_method/value_origin,
  input_origin, actor_label opcional no autenticado, action, source_fingerprint,
  source_snapshot/calculation_snapshot JSON de auditoría, calculation_version y fecha UTC.

La descripción y Quantity no se duplican como verdad comercial. Snapshots son sólo
historia de qué evidencia/inputs vio cada decisión. Trigger verifica Tender/Scope y
quote pertenecientes al mismo Tender. Historial no admite UPDATE/DELETE; identidad
no se borra ni reparenta. La anulación de FK viva por borrado de Scope está permitida:
no bloquea regeneración de MVP-06 ni destruye decisiones comerciales. La identidad
histórica sigue consultable y requiere revisión; no se reatacha por texto/posición.

No nuevo catálogo de proveedores, tabla Quote ni binarios. Un documento existente puede
referenciar múltiples líneas; una cotización no es obligatoria. Nuevas tablas tienen
migración Alembic reversible 073, sin ejecutar contra DBs/roots históricos congelados.
El downgrade administrativo elimina la nueva historia comercial; no es acción de usuario.

## Cantidad y contexto

La selección implícita usa únicamente el único Quantity hijo canónico EXACT, numérico
no negativo, con evidencia válida. Ambigüedad, ausencia, rango o fuente inválida deja
cantidad/totales sin resolver. Nunca se asume 1. Si hay varios hijos, selección explícita
de un ID existente del MISMO padre; no entrada de cantidad comercial ni override Quantity.
Una selección cuyo ID se regeneró queda stale, no se sustituye silenciosamente.
Los flags de revisión y bloqueo de fuente permanecen visibles, sin impedir guardar
una estrategia comercial. Scope rechazado/fuente bloqueada no se vuelve aceptado por
el precio. Cambio de contexto fuente se informa y exige acción consciente al actualizar.

## Dinero, cálculo y precedencia

- Entradas monetarias finitas Decimal desde strings/enteros/Decimal; float/bool/NaN/Inf
  rechazados. Hasta 18 enteros y 6 fracciones, sin redondear silenciosamente input manual.
- Porcentajes son unidades humanas base 100 (25 significa 25%), hasta 8 decimales.
- Contexto local precisión 50, ROUND_HALF_UP. Precio recomendado se cuantiza a 6
  decimales; totales MXN/USD/EUR a 2. Profit = total ofertado redondeado − costo total
  redondeado; ratios efectivos usan unidades y se devuelven como porcentajes a 8 decimales.
- Monedas M7-A: MXN, USD, EUR; sin FX ni agregación mixta. Moneda ausente admite borrador
  con warning; no produce totales monetarios sin denominación.
- COST_FIRST/MARKUP: p = c × (1 + markup_percent/100), markup >= −100.
- COST_FIRST/MARGIN: p = c / (1 − target_margin_percent/100), margin < 100.
  Targets negativos no se corrigen ni optimizan. Inputs inválidos se guardan como
  borrador revisable; no producen una recomendación inventada.
- PRICE_FIRST: p manual; markup = (p−c)/c, margin = (p−c)/p, ambos ×100 en DTO.
  Denominador cero deja ratio null con warning, nunca división por cero.
- Falta de costo no equivale a cero; puede haber precio/total ofertado sin profit/ratios.
  NOT_APPLICABLE es tipo de fuente, no un costo cero implícito. Negativos se conservan
  con revisión/warnings; pérdida no bloquea guardado ni se oculta.
- Guardar inputs no cambia el precio elegido cuando ese campo no se envía. Se distinguen
  recomendación, precio vigente, método MANUAL/CALCULATED y origen MANUAL_INPUT/
  SYSTEM_ESTIMATE. Aplicar cálculo exige acción explícita y expectativa de revisión/contexto;
  reemplazar un precio manual exige además replace_manual_price=true. La decisión anterior
  permanece auditada. Cambiar una regla nunca sobrescribe un precio manual.

Fuentes comerciales: SUPPLIER_QUOTE, INTERNAL_COST, MANUFACTURER_COST,
HISTORICAL_REFERENCE, ESTIMATE, MANUAL, NOT_APPLICABLE. Son distintas del origen económico
obligatorio CONFIRMED_QUOTE/HISTORICAL_COST/SYSTEM_ESTIMATE/MANUAL_INPUT. El tipo de parte
no certifica un costo: el origen es declarado y trazable, con revisión si no hay soporte.
Input origin UI/API ahora; XLSX/CSV quedan sólo como vocabulario futuro, sin endpoints.
No se inventa actor autenticado: actor_label, cuando se aporta, es una declaración.

## API y límites

API aditiva por Tender/Scope: crear/consultar, PATCH con revisión/contexto esperados,
calcular/consultar resumen; lecturas puras, commits en capa API y bloqueo de identidad
para concurrencia. Readiness READY/INCOMPLETE/REVIEW_REQUIRED es derivada; warnings no
bloquean decisiones comerciales válidas. Sin endpoint de matriz/bulk, XLSX/CSV, defaults,
FX, optimización, parsing de quotes, ERP, propuesta o Bid Readiness. UI provisional
mínima dentro del Scope existente, sin reingresar datos canónicos.
