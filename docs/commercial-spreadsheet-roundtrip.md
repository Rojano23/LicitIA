# M7-C — Round trip comercial XLSX/CSV

Aceptado arquitectónicamente — M7-C ACCEPTED; base M7-B `faa238d`, sin migración. [ADR-0024](adr/0024-commercial-spreadsheet-roundtrip.md) documenta herramientas y decisiones.

## Uso en Workspace

Abra Commercial Matrix y descargue XLSX o CSV. Edite campos comerciales, ordene o filtre
filas conservando sus IDs. Seleccione el archivo y solicite preview: cargar no modifica
líneas. Revise diferencias, advertencias y filas inválidas/conflictivas; confirme aplicar
sólo elegibles. Después se consulta otra vez la matriz canónica. Los borradores pendientes
en la matriz deshabilitan intercambio hasta guardarlos/descartarlos.

XLSX contiene Commercial Matrix, Instructions y LicitIA Metadata oculta. Columnas azules
son comerciales; grises son referencia. La hoja principal permite ordenar: estilos y
metadata protegida ayudan, pero la validación backend es la frontera de autoridad.
No se requieren macros ni fórmulas. La descarga contiene precios sensibles: protéjala y
compártala únicamente mediante los canales autorizados de su organización.

## Contrato e identidad

Versión `licitia-commercial-workbook-v1`. Identidad: Tender + export UUID + Scope UUID;
no posición, texto ni similitud. Mantenga los encabezados y metadata. Las columnas pueden
reordenarse. Se requiere el contexto de exportación vigente de esta instalación.

Referencia: scope_id, commercial_line_id, revision, source_fingerprint, item_reference,
description, quantity, unit, source_document, source_page y source_locator. Cambiarlas
invalida esa fila; no modifica evidencia canónica. No se crea Scope por importar.

Editables: cost_source_type, cost_value_origin, reference_party_name,
reference_party_reference, reference_party_note, unit_cost, currency, calculation_mode,
calculation_basis, markup_percent, target_margin_percent, offered_unit_price y notes.
Totales, utilidad, markup/margen resultantes, status y warnings son derivados: cualquier
edición se informa y se ignora; backend recalcula con M7-A/B.

CSV: UTF-8 (BOM aceptado), coma y quoting estándar. Primer registro: versión, Tender,
export UUID y timestamp; segundo: encabezados. Ordene únicamente desde el tercer registro.
Texto con prefijos peligrosos para una hoja de cálculo se exporta con apóstrofe; el lector
revierte ese escape documentado. No hay inferencia de delimitador ni localización.

## Reconciliación y decisiones

Cada fila informa recognized y estado UNCHANGED, CHANGED, INVALID, UNKNOWN_SCOPE,
DUPLICATE_SCOPE o CONFLICT. Se muestran elegibilidad, diferencias actual/importado/propuesto,
y advertencias/errores. MISSING_FROM_IMPORT significa no proporcionado: no borra datos.
Todas las copias de un ID duplicado se rechazan; IDs nuevos no se mapean automáticamente.

El delta se compara contra el export original. Un precio exportado sin editar no se
convierte en override. Precio importado explícitamente es decisión humana y prevalece;
si sólo cambian costo/reglas COST_FIRST, se reutiliza recálculo M7-B protegiendo precios
manuales. Reemplazarlos exige el flag explícito del preview. Cambio de moneda también
requiere confirmación; no hay FX ni suma de monedas diferentes.

Revisión comercial o fingerprint canónico obsoleto produce conflicto cuando existe un
cambio pendiente. Un delta ya equivalente es UNCHANGED y no agrega historial. Apply vuelve
a comprobar expectativas congeladas; no hace rebase silencioso. Repetir apply equivalente
es idempotente. Para resolver conflicto, revise el estado actual y genere nuevo export.

## Números

Decimal con punto, sin separadores de miles ni símbolos monetarios en texto. Blanco es
null, sujeto a validación del contrato comercial. Texto 25%, texto 25 y número 25 son
25% en campos de porcentaje. Número .25 con formato 0%/0.00% representa 25%; formatos de
porcentaje complejos se rechazan. Dinero numérico con formato de moneda usa su valor XML
exacto más currency; no interpreta monedas por símbolo. Fechas, booleanos, errores y
fórmulas en editables son inválidos. Fórmulas derivadas nunca se ejecutan ni se usan como
cálculo canónico. Decimal se obtiene del valor lexical XML para evitar conversión float.

## API y almacenamiento

- GET `/tenders/{id}/commercial-exchange/export/{xlsx|csv}`: descarga local.
- POST `/tenders/{id}/commercial-exchange/stage`: multipart file y flags
  replace_manual_price/confirm_currency_change; retorna preview sin aplicar.
- POST `/tenders/{id}/commercial-exchange/stages/{stage_id}/apply`: JSON confirm=true;
  retorna resultados por fila elegible. Las filas rechazadas permanecen en el preview original.

Apply reutiliza bulk M7-B en grupos de hasta 100, con savepoints por fila. Auditoría
append-only registra XLSX_IMPORT/CSV_IMPORT, timestamp, SHA-256, nombre descriptivo,
export/stage UUID. No atribuye actor anterior cuando no existe actor autenticado.
Hash de spreadsheet y provenance de documentos Tender son ejes separados.

`commercial-roundtrip-v1` bajo data root guarda sólo contexto/plan JSON, no XLSX/CSV
completo; directorio 0700, archivos 0600, UUIDs y envelopes SHA-256. TTL 7 días, limpieza
local de contextos propios vencidos al crear nuevos, máximo 256 contextos y 16 MiB cada
uno. Corruptos fallan cerrados y requieren revisión administrativa; no se reparan solos.
Backup local existente incluye este directorio. Auditoría DB persiste tras vencer staging.

## Límites y seguridad

Máximo 5 MiB de archivo, 1000 filas, 64 entradas ZIP, 64 MiB descomprimidos, 32767 caracteres
por celda, tres hojas conocidas. Upload multipart limitado a 5 MiB + 64 KiB de envoltura;
rechazo temprano por longitud declarada o acumulada, además del límite del archivo leído.
Sólo XLSX/CSV. ZIP/XML se valida antes de openpyxl: UTF-8, sin DTD/entidades, macros,
cifrado, rutas peligrosas, partes binarias ni relaciones externas. No extracción a disco,
ejecución, evaluación de fórmulas ni fetch externo. Nombre upload nunca se usa como ruta.

Sin importación de spreadsheets arbitrarios, remapeo manual de IDs, conversión FX,
contraseñas/encriptación de workbook, almacenamiento cloud ni propuesta final. UI
provisional. Los contratos existentes de estado/warnings/precio y Quantity canónica
siguen disponibles para MVP-08/09, sin implementarlos en este slice.
