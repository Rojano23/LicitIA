# ADR-0042 — Separar consulta pública y filtros de Discovery

Estado: implementado; pendiente de revisión del Product Owner. Fecha: 2026-10-24.
Hotfix posterior al cierre Product UI; no abre UI-R8 ni modifica MVP-01–10.

## Decisión

Discovery presenta cuatro secciones numeradas y revisitables: consultar fuente, resultado,
filtrar oportunidades guardadas y revisar oportunidades. Abrir una sección sólo cambia la
presentación. Consultar requiere la acción humana y conserva el UUID/query de reintento.
No se cambia el dominio, matching, adquisición, paginación ni handoff.

Los periodos son intervalos de fechas inclusivos, calculados con el calendario local:
últimos N días = hoy menos N−1 hasta hoy; mes actual = día 1 hasta hoy; mes anterior completo.
Consulta inicial: 30 días. Lista inicial: sin límite. Personalizado conserva fechas editables.

«Ver resultados» es una acción explícita: aplica fuente y publicación del ScanRun, reinicia
página, área/evento/suministro/búsqueda/estado/seguimiento/cambios sin leer y conserva perfil
seleccionado + preferencia de sólo coincidencias. Es un contexto sobre datos guardados, no
un conjunto de pertenencia a un scan. Puede incluir consultas anteriores. El total mostrado
siempre es el del servidor para esos filtros; no se inventa un denominador contra lo adquirido.
Las páginas siguientes usan los últimos filtros aplicados con éxito, como antes.

El editor existente se extrae a Configuración → Perfiles de búsqueda, con las mismas APIs,
ANY/exclusiones/sinónimos/restricciones/activo y revisión optimista. El hash
`#/configuracion?section=profiles` dirige foco a la sección sin remontar el shell. Un evento
interno después de guardar refresca lecturas de Discovery montado; nunca ejecuta un scan.

Los ejemplos proceden de valores públicos persistidos PEMEX y contratos/fixtures CFE.
No se convierte una muestra en catálogo exhaustivo. Sólo el evento de consulta CFE ofrece
un selector acotado porque su adaptador acepta exactamente tres etiquetas; los filtros
sobre registros guardados mantienen texto opcional. No hay nuevos endpoints ni enums de dominio.
Compras MX conserva su restricción y las habilitaciones locales no se cambian al navegar.

## Validación y límites

Fixtures de navegador aisladas, fechas de prueba fijas, ninguna consulta pública ni escritura
sobre datos reales. Lectura autorizada de valores públicos existentes, sin corpus ciego.
Backend, esquema 079, dependencias y semántica permanecen intactos. La validación UI prueba
contratos y presentación; no certifica relevancia, disponibilidad ni cobertura de portales.
[Reporte del hotfix](../discovery-ux-workflow-hotfix.md).

## Pulido final solicitado por Product Owner — 2026-10-24

La revisión humana sustituye la presentación inicial: paso 1 siempre visible, sin «Nueva
consulta»; paso 2 contiene sólo el resultado actual/más reciente. Historial de consultas en
Diagnóstico, tabla de hasta 20 registros usando la lectura existente. Los enlaces de atención
de Inicio y los enlaces antiguos a scan dirigen a esa superficie, sin adquisición pública.

Revisar abre un modo de detalle dentro de la misma vista: flujo montado pero oculto, foco
inmediato y regreso al botón de la fila sin nueva petición. Ver cambios enfoca su encabezado.
Confirmaciones y errores se muestran en la fila/sección de la acción. El historial conserva
orden/paginación canónicos, una lista con scroll y tres acciones independientes de su volumen.
No muestra JSON, códigos, UUID, identificadores internos, hashes ni timestamps crudos. Usa
número de procedimiento público cuando existe; sin él no expone external_id como sustituto.

El contrato histórico incluye observaciones SOURCE y acciones HUMAN/SYSTEM auditadas. No se
filtran ni reinterpretan como cambios de la fuente: las acciones se identifican por separado.
No se borra auditoría ni se cambia el alcance de acknowledgment. Los detalles técnicos de
cada evento se retiran, sin crear otra API/sistema de logs. Diagnóstico conserva sólo campos
acotados de ScanRun y conteos de incidencias, sin mensajes libres ni payloads.

[Reporte final y evidencia](../discovery-ux-final-polish.md). Continúa sin stage/commit/push.

## Micropulido final — fuentes, operación y administración

La franja de fuentes utiliza una línea nombre/estado por bloque cuando cabe, con wrapping
natural en anchos menores y sin cambiar estados. Se elimina el PATCH administrativo de
Discovery; habilitación y áreas permitidas permanecen en Configuración → Fuentes Discovery.
El enlace `#/configuracion?section=sources` enfoca esa sección.

Auditoría del contrato existente: PATCH guarda enabled y configuration.areas; POST scan
usa query.areas pero exige fuente habilitada y subconjunto de las áreas configuradas.
Por ello los checkboxes operativos permiten escoger ese subconjunto; áreas no habilitadas
quedan desactivadas con enlace administrativo. No se autoamplía la configuración ni se
escribe antes de consultar. Fuente deshabilitada ofrece orientación/enlace, no otro botón.
[Reporte de micropulido](../discovery-ux-final-micro-polish.md). Sin backend/migración nueva.
