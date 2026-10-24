# UI-R2.1 — Visual Polish

Estado: implementado y validado; listo para revisión final. Sin stage, commit ni push.
HEAD conservado: `d0398f17f4b46c4a74046513aaced1451ad52951`.

Se pulió exclusivamente la presentación de Inicio y Discovery: jerarquía, espaciado,
alineación, señales de atención y distinción entre acciones informativas y persistentes.
Se conservaron los dos indicadores, la tabla de siete columnas, su scroll local y la
confirmación humana. No se añadieron funcionalidades, métricas ni dependencias.

## Alcance exacto

Archivos incrementales respecto del baseline UI-R2:

- `frontend/src/components/InicioView.tsx`
- `frontend/src/components/DiscoveryView.tsx`
- `frontend/src/components/DiscoveryDetail.tsx`
- `frontend/src/components/discovery.css`
- `docs/ui-r2-1-visual-polish.md`

Las modificaciones anteriores de UI-R2 permanecen sin comprometer. El diff acumulado
contra HEAD incluye esas modificaciones; no debe confundirse con esta lista incremental.
No se modificaron pruebas, AppShell, componentes compartidos, rutas, wrappers API,
backend, migraciones, contratos, matching ni módulos posteriores durante UI-R2.1.

## Baseline y comparación visual

Antes de editar se verificaron los 18 hashes de archivos UI-R2 contra su evidencia
local. Sus resultados previos (195 frontend, 38 API y 13 grupos browser) son evidencia
heredada, no ejecuciones nuevas. Se revisaron el contrato visual canónico, ADR-0036,
componentes UI-R1/UI-R2, capturas anteriores y referencias originales Stitch.

| Pantalla | Antes | Después |
|---|---|---|
| Inicio | Secciones con menor separación | Indicadores compactos, divisores y filas de atención con acción visible |
| Discovery | Controles y acciones con jerarquía similar | Filtros alineados en superficie delimitada, acción principal reconocible y secundarios subordinados |
| Siguiendo con cambios | Conteos integrados al texto de fila | Celda de cambios pendientes destacada con token de advertencia; estado de seguimiento separado |
| Detalle | Secciones consecutivas poco diferenciadas | Información pública, coincidencia/contexto, historial y handoff separados por encabezados y divisores |
| Vista previa | Selección y confirmación visualmente continuas | Selección explícita y confirmación humana agrupadas; acción persistente primaria |
| Compras MX | Restricción neutral existente | Restricción conservada y legible; sin controles para consultar el portal |

Se revisaron capturas en 1366×768, 1440×900, 1920×1080, 768×900 y 390×844.
No se observó overflow horizontal de página. La tabla conserva desplazamiento local,
altura máxima y columna de acciones sticky. En anchos reducidos hay columnas que
requieren ese desplazamiento, conforme al contrato anterior.

## Preservación funcional

La comparación mediante parser TypeScript confirma, para los tres componentes,
identidad de todas las instrucciones previas al return y de atributos JSX de handlers,
valor, checked y disabled. Evidencia: `functional_preservation.json`.
Los otros 14 archivos del baseline UI-R2 y todos sus reportes previos conservan sus hashes.

Se mantuvieron filtros, estados, historial/ack, claves idempotentes, preview, binding,
selección y confirmación de creación. La verificación browser original se ejecutó sin
modificar su script ni sus fixtures. No hay adquisición pública al montar pantallas,
Tender automático, descarga automática, DI, OCR, Vision ni LLM añadidos.

## Validación ejecutada

| Comando / comprobación | Resultado nuevo |
|---|---|
| `npm --prefix frontend test` | 195 passed / 24 files |
| `npm --prefix frontend run build` | PASS; JS 531.01 kB, CSS 22.13 kB |
| `npm --prefix frontend run typecheck` | PASS |
| `node frontend/scripts/ui-r2-browser.mjs backend/reports/ui_r2_1/browser` | 13 grupos PASS; 14 capturas |
| `node backend/reports/ui_r2_1/accessibility-check.mjs` | 4 verificaciones PASS |
| `git diff --check` | PASS |
| Integridad histórica, sólo hashes | 5941 / 5941 intactos |

La comprobación adicional de accesibilidad cubre menú por teclado y retorno de foco,
foco visible de filtros, labels de campos y contraste de muestras afectadas ≥4.5:1.
No constituye certificación WCAG. Las fixtures de navegador son aisladas y prueban
presentación y contratos, no calidad semántica ni disponibilidad de portales reales.

Backend sin cambios: no se repitieron pruebas API. Los 38 PASS API, compileall PASS y
Alembic `20261023_discovery_079` pertenecen a la validación anterior de UI-R2; no se
presentan como nuevas ejecuciones. No hay nuevas migraciones ni cambios de esquema.

## Evidencias

Directorio local: `backend/reports/ui_r2_1/`. Contiene baseline, hashes, comparación
funcional, integridad histórica, accesibilidad, logs y `validation.json`.
Capturas bajo `backend/reports/ui_r2_1/browser/`:

- `01-inicio-1366.png`, `02-inicio-1440.png`, `03-inicio-1920.png`, `04-inicio-empty.png`
- `05-discovery-1366.png`, `05-discovery-1440.png`, `05-discovery-1920.png`
- `06-following-changes.png`, `07-opportunity-detail.png`, `08-create-preview.png`
- `09-compras-restricted.png`, `10-partial-source.png`
- `11-discovery-narrow-768.png`, `12-discovery-narrow-390.png`
- `contact-sheet.png`: Inicio, Discovery, Siguiendo con cambios, Detalle, Vista previa y Compras
- `before-after.png`: comparación de los seis estados contra UI-R2

Imágenes y reportes locales sin stage; las evidencias históricas no fueron editadas.
No se inspeccionó contenido semántico del corpus ciego.

## Observaciones y cierre

Persiste el warning conocido de bundle JS superior a 500 kB. No se realizó optimización
de dependencias ni code splitting. El alcance mantiene las limitaciones funcionales de
UI-R2 y la restricción de automatización de Compras MX. No se detectaron blockers
funcionales o arquitectónicos nuevos en las comprobaciones realizadas.

Recomendación: cerrar la iteración de implementación y someterla a revisión visual final.
Índice vacío; sin stage, commit, push ni reescritura de historia. La aprobación visual
humana permanece pendiente.
