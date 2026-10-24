# ADR-0041 — UI-R7: cierre de presentación y carga técnica diferida

Estado: **ACEPTADO — FINAL HUMAN REVIEW PASS; PRODUCT UI CLOSED**. Fecha: 2026-10-24.

UI-R6 aceptado y comprometido localmente en `239c8b5e057f089d28bb0bccc053f8b4a97043e6`.
UI-R7 no amplía dominio, contratos, fuentes, esquema ni dependencias.

## Decisión

Conservar shell, navegación contextual, tablas, proporciones documentales y ownership de
peticiones aceptados. Revisar lenguaje de preparación/propuesta, edición comercial en lote,
intercambio de archivos, evidencia empresarial y configuración. Traducir etiquetas sin
cambiar valores de opciones, DTO, cálculos, elegibilidad, confirmaciones o idempotencia.
Errores de exportación en modo producto no presentan `detail` arbitrario del servidor;
el modo técnico conserva su información diagnóstica. Identificadores/códigos de auditoría
siguen disponibles en detalles técnicos. Textos fuente y decisiones humanas no se reescriben.

Medición Rollup previa: App.tsx es el mayor módulo propio (294334 bytes renderedLength;
esta medida por módulo no equivale al tamaño minificado del archivo). Bundle inicial
640318 bytes UTF-8. Diferir únicamente App con React.lazy/Suspense: se monta sólo al abrir
herramientas avanzadas de Diagnóstico y continúa montado después de visitarlo. Una frontera
local ofrece reintento ante fallo de carga; no recarga la aplicación ni descarta otros módulos.
No fragmentar las superficies de trabajo pequeñas ni alterar la retención de formularios.

## Inventario de superficies

| Clasificación | Superficies | Decisión |
|---|---|---|
| PRODUCT | Inicio, Discovery, lista/Resumen/Documentos, Requisitos, Cumplimiento, Partidas, Comercial, Preparación, Propuesta, Mi empresa, Reportes, Configuración | rutas y modelos canónicos existentes |
| SECONDARY | detalle de requisito/evidencia/partida; edición comercial en lote; composición, historial y archivos de propuesta | apertura contextual explícita, no segunda ruta primaria |
| DIAGNOSTIC | estado local, copia para soporte, integridad/identificadores/códigos; App heredado con controles explícitos | sólo Diagnóstico o detalle técnico identificado |
| OBSOLETE DUPLICATE | acceso global anterior a CompanyEvidenceLibrary y antiguas superficies primarias de App | ya retirados de navegación primaria en slices aceptados; no borrar contratos backend |

No se eliminan componentes por conjetura. CompanyEvidenceLibrary y los paneles de ingeniería
siguen usados por las herramientas heredadas. No hay una segunda representación primaria
independiente del estado de requisitos, evidencia, partidas, comercial o propuesta.

## Límites

Pruebas sintéticas prueban UI y contratos, no exactitud semántica ni portales reales. La copia
para soporte sigue una allowlist de estados, sin payload libre. No se introducen telemetría,
peticiones externas, fuentes remotas, animaciones ni nuevos diálogos personalizados.
La revisión visual humana final es autoridad de cierre; no se sustituye por screenshots o tests.

## Hallazgo humano final: crear desde expediente local

La revisión final exige corregir Nueva licitación dentro de UI-R7, sin UI-R8. Dos entradas:
crear desde expediente (predeterminada) y crear vacía. Ambas usan TenderCreate.title,
external_reference e institution_profile existentes. TenderCreation selecciona/enlista File,
pero no sube bytes: después del POST canónico transfiere una sesión efímera aprobada por
el usuario a Documentos, donde la única implementación DocumentImports realiza las
solicitudes existentes por archivo. No endpoint, tabla, dominio o procesador nuevo.

El registro canónico (`main.py:import_documents`) no tiene allowlist de extensiones/MIME:
almacena originales, calcula hash y resuelve duplicados/conflictos. No confundir con soporte
de extracción/visor. Todos los formatos seleccionados con nombre/ruta segura son elegibles
para registro; ZIP se registra sin abrirlo. No inventar una lista de formatos rechazados.
Las omisiones visibles son rutas inseguras, no extensiones presumidas como no soportadas.
No se filtran archivos ocultos: .DS_Store se incluyó en la prueba de carpeta nativa.

El selector webkitdirectory y las entradas de drop usan capacidades nativas. El lector de
carpetas consume todas sus páginas hasta lista vacía. No APIs de rutas arbitrarias ni
traversal ajeno a los handles entregados por la selección. Guardar sólo rutas relativas
seguras; reutilizar source_relative_paths. FormData fija filename=file.name explícitamente:
Chromium, con archivos de carpeta nativos, enviaba la ruta dentro del filename multipart.
Separar nombre base y ruta conserva identidad documental/conflictos y bytes originales.

Cada archivo conserva clientImportId y File; la sesión se consume una sola vez. Su montaje
no equivale a análisis: es la continuación de Crear licitación y agregar documentos, ya
confirmada por el usuario. El montaje normal de Documentos sin esa sesión no importa nada.
El resultado muestra agregados/duplicados/conflictos/fallos/pendientes/cancelados/omitidos.
Un fallo documental no borra la licitación. Guardar File/ID/ruta y decisión para retry; no
resolver conflictos por nombre o posición. Las revisiones siguen requiriendo target vigente
del mismo Tender y nombre. La creación tiene lock síncrono; no se inventa idempotencia de
servidor. Respuesta de creación perdida exige verificar la lista antes de repetir.
