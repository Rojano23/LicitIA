# ADR-0033 — CFE en Discovery y fuentes con automatización restringida

Estado: M10-B ACCEPTED — BOUNDED SCOPE, commit `100caf07` (2026-10-23).

CFE usa el contrato DiscoveryAdapter y Opportunity genéricos, tablas078 y semántica
ScanRun existente. Un registro de adapters/capacidades sustituye wiring PEMEX exclusivo;
Core no decide paginación ni dominio por nombre de fuente. Sin migración ni dependencia nueva.

El endpoint público CFE getProcBusqueda entrega un array completo (Kendo pagina en cliente).
HTTP/array acotados; batches locales conservan todos los resultados, sin fingir páginas remotas.
No publica total independiente: source_total permanece null. Terminal significa final del array
observado; no certifica ausencia de truncación desconocida del servidor ni snapshot atómico.
Detalle POST público por Id permite empresa/área y referencias HTML; sin binarios ni JavaScript.
Fallo de detalle no inventa campos/documentos y hace parcial el scan. Referencias se limitan
al HTML público verificado; no se promete crawler universal de todas las etapas históricas.

Identidad CFE+Id (no título/posición). procedure_number opcional es un campo neutral de la
representación JSON existente, útil para búsqueda/navegación y fingerprint significativo;
no requiere columna. Cuando ausente se excluye únicamente este campo nuevo del fingerprint,
para conservar exactamente los hashes PEMEX aceptados. Fechas .NET se interpretan como
instantes UTC y fecha civil America/Mexico_City, declarada por el detalle CFE.

Compras MX: DEFERRED — SOURCE AUTOMATION RESTRICTED. No adapter ni parser especulativo.
Entrada/401 históricos documentados; ninguna nueva petición, PoW, reverse engineering,
reutilización de cookies/tokens, browser bypass o sustitución por datasets históricos.
Disponibilidad se expresa en capabilities, sin migración ni estado workflow específico.
La restricción se impone en configuración y factory/API, no sólo UI. Futuro adapter sólo
cuando exista una interfaz oficial automatizable documentada y autorizada.

HTTP CFE sólo HTTPS msc.cfe.mx:443, paths verificados de Concursos; redirects rechazados,
respuestas con MIME/límite de tamaño y retries acotados. Documentos tienen política separada
GetAnexo/DescargarPrecision/DescargarRespuestaPrecision; referencias nunca se recuperan.
Tokens CSRF/cookies sólo en memoria del cliente público CFE; no auditoría/DB/logs.
