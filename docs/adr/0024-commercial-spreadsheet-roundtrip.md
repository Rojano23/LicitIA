# ADR-0024 — M7-C: round trip comercial local

Estado: aceptado arquitectónicamente — M7-C ACCEPTED. Base M7-B `faa238d`.

## Herramientas

[openpyxl](https://openpyxl.readthedocs.io/en/stable/) MIT/Expat, 3.1.5 ya incluido en
lock/runtime: escritura/lectura XLSX, estilos, filtros y tipos. Se declara dependencia
directa, sin instalación ni cambio de versión/lock. Su documentación advierte sobre XML
hostil: se valida ZIP/XML antes de cargar, con límites, sólo UTF-8, sin DTD/entidades ni
links externos. No se ejecutan fórmulas ni macros. [XlsxWriter](https://xlsxwriter.readthedocs.io/license.html)
BSD-2-Clause revisado, no adoptado: agrega otra dependencia de escritura sin resolver
lectura. [csv](https://docs.python.org/3/library/csv.html), stdlib PSF: lector/writer con
delimitador explícito, strings, sin QUOTE_NONNUMERIC ni sniffing/localización automática.

## Contrato y autoridad

`licitia-commercial-workbook-v1`: Commercial Matrix, Instructions y metadata oculta.
IDs Scope visibles y textos técnicos/referencia grises; campos comerciales azules.
La hoja principal permite ordenar/mover/filtrar filas; no protección que impida sorting
sobre IDs bloqueados. Metadata protegida como ayuda. Estilo/protección no es seguridad.
Todos los importes exportados son textos exactos, sin fórmulas. Backend sigue autoritativo.
CSV UTF-8 (BOM aceptado), coma, quoting estándar; primer registro metadata, segundo headers.
No cambiar esos dos registros al ordenar datos. Campos de texto peligrosos para Excel
llevan prefijo apóstrofe documentado; se quita ese escape al reimportar CSV.

Identidad por export UUID + Tender + Scope UUID, nunca fila/texto/partida/Quantity.
Contexto local exportado conserva campos de referencia, inputs y revisión/fingerprint.
Formato no originado en esta instalación/contexto vigente se rechaza; workbook no es
fuente de Scope. Cambios de descripción/Quantity/unidad/IDs técnicos invalidan esa fila.
Derivados modificados se informan/ignoran; nunca reemplazan cálculos. Fila eliminada no
borra nada; IDs desconocidos/duplicados no se eligen ni mapean por similitud.

Importación: bytes acotados → parse → reconcile → preview/diff inmutable local → aplicar
explícitamente filas elegibles mediante BulkRequest M7-B (chunks ≤100), mismas reglas y
savepoints. Cambios comerciales se comparan con baseline exportado: precio sin editar
no se convierte en override. Precio importado explícito es MANUAL/MANUAL_INPUT y prevalece;
sin cambio de precio explícito, cambios de costo/regla pueden recalcular COST_FIRST,
protegiendo manuales salvo flag confirmado durante preview. Moneda mantiene confirmación
M7-B, sin FX. Preview muestra diferencias efectivas y resultados por fila.

Inputs, revisión/fingerprint y flags del preview quedan congelados. Cambio después del
preview/export produce CONFLICT, sin rebase automático. Si los cambios solicitados ya
son equivalentes al estado actual se informa UNCHANGED sin nueva historia; no descartar
un archivo sólo por hash ni ignorar conflictos mediante ese hash. Segundo apply también
estable/idempotente. Origen XLSX_IMPORT/CSV_IMPORT, SHA-256, nombre descriptivo, export/stage
UUID y fecha quedan en revisión append-only existente, separados de provenance documental.
Rutas bulk públicas no pueden autodeclarar evidencia de importación reservada.

## Números y seguridad

Strings decimales con punto, sin miles/moneda localizada. Porcentajes humanos base 100;
texto 25% o número 25 significa 25%; celda numérica con formato porcentaje usa fracción
(.25 →25). XML numérico lexical se lee como Decimal, sin confiar en float de openpyxl.
Dinero con formato de moneda usa valor numérico exacto más columna currency, sin FX.
Blancos son null (tipos requeridos se validan). Bool/fecha/error/fórmula en editables se
rechazan por fila; fórmulas derivadas se ignoran con warning, jamás se evalúan/cargan caché.

Beta: 5 MiB archivo, 64 MiB ZIP expandido, 1000 filas, 64 entradas ZIP, 32767 caracteres
por celda y 3 hojas conocidas. XML DTD/entidades, macros, cifrado, rutas ZIP peligrosas y
relaciones externas se rechazan antes de openpyxl; sin extractall, VBA, shell ni red.
Nombres de upload nunca se usan como ruta. Errores de formato/estructura fallan claramente.

## Persistencia/privacidad

Sin migración (073). JSON de contexto/stage en commercial-roundtrip-v1 bajo data root,
UUIDs validados, envelopes SHA-256, escritura exclusiva 0600, directorio 0700; no symlinks.
No copias XLSX/CSV retenidas: sólo hash, campos/plan necesarios para preview y auditoría.
Contextos vencen a los 7 días; limpieza de archivos propios vencidos al crear contextos,
capacidad acotada (256 contextos, 16 MiB JSON por contexto). Exportes/stages vencidos
requieren nuevo export/preview. No se limpian reportes/históricos/originales. Snapshots de
auditoría DB retienen evidencia comercial necesaria después de vencer staging.
Export se descarga localmente; usuario/admin deben proteger precios/confidencialidad.
Sin cloud, propuesta, UI final ni implementación MVP-08/09; readiness y Quantity existentes
siguen disponibles para esos contratos futuros.
