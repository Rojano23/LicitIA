# MVP-07 M7-B — Matriz comercial y edición masiva

M7-B ACCEPTED. Commit autorizado, sin push.
M7-A aceptado y comprometido en `6d30509d9859dabf44fd85341759ff8054707668`.
[ADR-0023](adr/0023-commercial-matrix-bulk.md), [fundación M7-A](commercial-foundation.md).

## Uso

En Workspace, abrir **Matriz comercial**. Cada Scope actual aparece con descripción,
Quantity/unidad, provenance/revisión, datos comerciales y warnings. Las filas sin línea
son virtuales INCOMPLETE: consultar/filtrar/seleccionar no crea registros. Scope/Quantity
siguen canónicos, de sólo lectura; cantidades ausentes/ambiguas no se suponen iguales a 1.
Las líneas de Scope retirado aparecen separadamente y enlazan a su auditoría existente,
sin mezclarlas con los subtotales de Scope actual.

Editar costos/precios/notas/reglas por fila. Tab usa navegación nativa; Enter solicita
preview de la fila, no guarda automáticamente. Se pueden capturar distintos costos en
varias filas y previsualizar juntas las ediciones visibles o incluirlas en una regla
compartida. Los borradores de filas no seleccionadas/fallidas se conservan; refrescar
para descartarlos requiere confirmación. No se crea un objeto comercial antes de aplicar
información efectiva. Un preview sin cambios o recalcular una fila vacía no crea registros.

Filtrar por estado, falta de costo/precio, fuente o moneda. Selección por UUID es estado
local, no dato del dominio. **Seleccionar visibles** marca el conjunto filtrado actual;
las acciones afectan sólo seleccionadas visibles, nunca seleccionadas ocultas. Máximo
100 filas por lote; para conjuntos mayores usar selección/filtros y varios lotes.

Defaults de moneda/modo/markup o margen son de sesión React para el Tender actual.
No hay settings comerciales persistidos reutilizables en el modelo existente: no se
crea una tabla para esta preferencia. Defaults sólo inicializan filas nuevas al aplicar,
no se reaplican a las existentes. Cambiar Tender/remontar Workspace pierde esos defaults.
No hay motor de reglas ni valores económicos inferidos.

## Precedencia y acciones

- PATCH aplica campos explícitos comunes; row_changes contiene ediciones explícitas
  por Scope. En el mismo campo prevalece la acción común elegida para ese lote.
- MARKUP/MARGIN establecen COST_FIRST con su basis y target. Precio se calcula sólo
  con costo/moneda/regla válidos. Quantity se consulta de su padre y no se modifica.
- RECALCULATE utiliza la regla guardada, sin cambiar PRICE_FIRST a COST_FIRST a escondidas.
- Modo cambia sin borrar costo/precio. Cálculo posterior es una acción explícita.
- Precio MANUAL se protege salvo replace_manual_price=true. La UI confirma antes de
  aplicar el reemplazo. Precio ingresado explícitamente conserva MANUAL/MANUAL_INPUT;
  precio aplicado por fórmula es CALCULATED/SYSTEM_ESTIMATE.
- Copiar ajustes usa fuente/moneda/modo/basis/targets/parte de una fila con expectativas
  vigentes. No copia costo, precio, Quantity, notas, origen de costo ni documento quote.
  Un borrador monetario enviado explícitamente como row_changes es una edición humana,
  no una copia implícita. La fuente de copia también se verifica/serializa con locks.
- Cambio de moneda en una fila que ya tiene costo o precio requiere
  confirm_currency_change=true, incluso para retirar la moneda. No convierte ni altera
  los números por FX. El preview informa CURRENCY_CONFIRMATION_REQUIRED si falta permiso.
- INITIALIZE sólo aplica defaults a líneas nuevas; existentes quedan ALREADY_INITIALIZED.

Preview por defecto, luego **Aplicar vista previa**. Las expectativas de cada Scope
incluyen revisión comercial (null si no existe) y fingerprint de contexto fuente. Si
alguien actualiza/crea una línea o cambia la evidencia, esa fila queda stale. No sustituir
las expectativas viejas automáticamente por las actuales al repetir un request.

Resultado por fila: ELIGIBLE en preview, UPDATED al aplicar, SKIPPED/INVALID/STALE/FAILED
cuando corresponda, con reasons/warnings y price_outcome separado:
NOT_REQUESTED, PROTECTED, UNRESOLVED o RECALCULATED. Actualizar una regla con precio
protegido puede ser UPDATED + PROTECTED; no implica que se cambió ese precio. Target
inválido puede guardarse con warning, sin recomendación inventada. Pérdida/negativos no
bloquean guardar. Errores de representación/propiedad sí protegen integridad.

Savepoint por fila para fallos esperados, commit exterior de filas válidas. Error
inesperado revierte el request completo y retorna error. Si falla la actualización de
UI después de aplicar, consultar estado antes de repetir. Repetir cambios equivalentes
con expectativas vigentes no crea revisiones; expectativas anteriores fallan cerradas.
No es una API de exactly-once por operation_id: UUID agrupa auditoría, no elimina checks.

## Auditoría y resumen

Revisiones append-only M7-A: action BULK_WORKSPACE/BULK_API, UI/API y metadata en
calculation_snapshot.bulk_operation (UUID, timestamp UTC, acción, IDs solicitados,
campos modificados, valores antes/después). Los registros no modificados/omitidos se
informan en el resultado; no se crea una tabla enterprise de eventos ni se escriben
revisiones sólo por consultar/previsualizar. Historial de línea sigue disponible en API M7-A.

Resumen por moneda: número de filas y estado, costo/oferta/utilidad calculables,
conteos calculables/faltantes por campo. Si faltan filas son **subtotales calculables**,
no totales certificados. Sin datos calculables el importe es null, no cero inventado.
Markup/margen agregados usan exclusivamente pares costo/oferta completos de la misma
moneda y exponen paired_count. No gran total MXN+USD+EUR ni FX. Moneda ausente tiene grupo
sin moneda y totales sin resolver. Los warnings no convierten esta vista en bloqueo BID.

## API

- GET `/tenders/{id}/commercial-matrix`: rows, summary_by_currency, archived_lines.
- GET `/tenders/{id}/commercial-matrix/summary`: el mismo resumen agrupado.
- POST `/tenders/{id}/commercial-matrix/bulk`: targets (1–100, únicos), action, changes,
  row_changes por ID, defaults, copy_from, flags recalculate/replace_manual_price/
  confirm_currency_change, input_origin UI/API y apply=false por defecto.
- Actualización individual reutiliza bulk de un Scope o endpoints M7-A existentes.

DTO MVP-08: commercial_complete, warning_count/types, offered_price_status, unresolved_cost
más summary.status. Es completitud comercial derivada, no confianza contractual ni Bid
Readiness. No sumar estados de revisión como aprobación humana ni resolver Quantity
confirmando Scope.

Prefetch de Scope/Quantity, CommercialLine y última revisión (DISTINCT ON PostgreSQL).
Dos SELECT comerciales para la matriz, sin historia por fila. Lectores canónicos de
revisión/grounding aún realizan consultas por Scope: no se altera MVP-06 para ocultarlo.
No nueva migración/dependencia; Alembic permanece 073. Sin XLSX/CSV, reconciliación,
UI final, branding, navegación nueva, optimización ni cambio de provider/prompt/política.

M7-C recomendado: exportar DTOs con identidad/revisión/fingerprint, moneda y decimales
exactos; importar a staging/preview, reconciliar por IDs, informar conflictos/stale,
validar ownership y mantener overrides/auditoría. No matching por texto como identidad,
no importación silenciosa sobre una decisión más nueva, sin alterar originales.
