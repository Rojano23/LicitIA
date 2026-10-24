# UI-R7 — Nueva licitación desde expediente

Estado: implementado y validado para revisión humana final. Corrección del hallazgo Product
Owner, dentro de UI-R7; no UI-R8. **Sin stage, commit ni push.**
HEAD conservado: `239c8b5e057f089d28bb0bccc053f8b4a97043e6`.
[ADR-0041 actualizado](adr/0041-product-ui-closure.md).

## Flujo y contratos

Nueva licitación presenta **Crear desde expediente** y **Crear vacía**. El campo
“Referencia o nombre de la licitación” usa `TenderCreate.title`; referencia/perfil opcionales
siguen los campos existentes. No se infiere institución ni procedencia PEMEX/CFE.

Crear desde expediente: seleccionar/revisar → confirmar “Crear licitación y agregar
 documentos” → POST `/tenders` → ID retornado → Documentos del mismo Tender →
DocumentImports existente envía cada File al POST `/tenders/{id}/documents/import`.
Sólo esa sesión explícitamente confirmada inicia sus envíos; abrir Documentos normalmente
no importa archivos. Al terminar quedan resultados reales y **Revisar documentos**.
Crear vacía usa el mismo POST y abre Resumen con el enlace existente Ir a Documentos.

No se agregan acciones de análisis. No OCR, Vision, Ollama, extracción de requisitos,
alcance/evidencia/comercial, preparación ni propuesta por crear/importar/navegar.
Discovery conserva su preview, selección, confirmación, binding y provenance originales.

## Formatos reales y archivos omitidos

Inspección de `backend/app/main.py`, `import_documents`, `_store_uploaded_file`:
el registro **no restringe extensiones ni MIME**. Soporta registrar originales arbitrarios;
esto no equivale a poder visualizarlos/analizarlos. La UI lo explica en lugar de inventar
una allowlist PDF/DOCX/Excel. ZIP se guarda como original, sin extracción ni inspección.

Todos los archivos descubiertos se clasifican para registro; sólo se omiten selecciones
con ubicación relativa insegura (absoluta, drive, componentes vacíos, `.`/`..`, controles).
Se informa cantidad, nombre base y motivo en **Ver archivos omitidos**. No se muestran rutas
absolutas y no se bloquean los archivos válidos. No existe un caso canónico de extensión
no compatible para fabricar una captura: el estado omitido probado corresponde a ruta insegura.

No se descartan ocultos. El selector nativo Chromium incluyó `.DS_Store` entre seis originales,
con PDF, XLSX y ZIP anidado; todos pasaron por el mismo contrato.

## Selección, rutas y escala

Selector múltiple, selector `webkitdirectory`, drop de archivos y enumeración recursiva de
entradas de carpeta. Los handles se capturan durante drop; `readEntries` se repite hasta
vacío, sin perder páginas del lector. Fallback visible: usar Seleccionar carpeta cuando
el navegador no permite drop de directorios. Una lectura incompleta no agrega silenciosamente
parte de la nueva carpeta; muestra error y conserva las selecciones anteriores.

FileList se copia inmediatamente, antes de vaciar el input nativo. Cada original tiene
clientImportId estable; las ubicaciones relativas sirven para distinguir homónimos.
Se reutiliza `source_relative_paths` existente. En multipart se fija **filename = File.name**:
Chromium usaba la ubicación relativa como filename al enviar File de carpeta nativo. La prueba
nativa reprodujo ese comportamiento y verifica el envío corregido; los bytes no cambian.

Resumen por cantidad/extensión declarada, tipo MIME/tamaño disponibles, lista ligera plegable
y scroll local; Quitar por archivo y Quitar todos. Probados 5,30,125 archivos; sin dependencia
de virtualización, lectura del contenido para selección ni componente pesado por original.

## Identidad, seguridad y recuperación

Una sola creación a la vez, con ref síncrono contra doble click/Enter y bloqueo durante
lectura/envío. No se atribuye idempotencia al POST Tender existente: si su respuesta se pierde,
se conserva el borrador/selección y se exige verificar la lista antes de reenviar.

DocumentImports conserva clientImportId/File/ruta para resultado, retry y decisión. Duplicado
no ofrece revisión. NAME_CONFLICT mantiene independiente/nueva revisión/cancelar, confirmación
y target actual del mismo Tender/nombre. Prueba de dos Same.pdf en carpetas distintas, resueltos
B→A con File/path/target exactos. El retry conserva decisión intentada, sin resolverla por posición.

Éxito de creación y éxito documental se muestran por separado. Un fallo parcial no hace rollback,
no borra Tender ni anuncia expediente completo. Resultados: agregados, duplicados, requieren
decisión, fallidos, pendientes, cancelados y omitidos. Se conserva acceso a Documentos y retry.

Sidebar y rerender conservan identificación/selección; toggle no reenvía ni crea. Antes de crear,
Cancelar pide descarte si hay borrador. Después, cancelar un conflicto no elimina Tender. Si
Documentos aún no pudo abrirse, salir de la sesión pendiente requiere confirmar que la licitación
se conserva y la selección se descarta. Los guards del importador siguen protegiendo cambios
de Tender con pendientes. beforeunload advierte selección no persistida.

## Accesibilidad y visual

Inputs nativos etiquetados para archivos/carpeta; alternativa de teclado a drop. Radios,
Quitar con ubicación en su nombre accesible, resumen textual y errores por archivo. Sin
modal personalizado, dependencia, animación, nueva navegación o rediseño del shell.

Formulario compacto hasta900px; lista plegable con260px máximos; resultados de esta creación
con scroll de50vh. Sidebar260/64 y visor/registro existentes conservados. Bounds de creación
verificados en1366,1440,1920,1024,768 y390; no certificación WCAG o preparación móvil.

## Validación ejecutada

| Validación | Resultado |
|---|---|
| Nueva licitación/documentos/wrapper focused | 41 passed /5files |
| UI-R7 focused anterior, ejecución nueva | 108 passed /13files |
| Frontend completo | 324 passed /38files |
| Browser Nueva licitación | 6 grupos PASS, selector Chromium de carpeta nativo |
| Final Product UI E2E | 8 grupos PASS |
| Regresión browser UI-R3 | 12 grupos PASS |
| Regresión browser UI-R2 | 13 grupos PASS |
| Regresión sidebar | 10 grupos PASS |
| Tender/document API | 127 passed,1deselected,7warnings,13.50s |
| Build / typecheck | PASS; sin dependencia nueva |
| compileall / git diff --check | PASS |
| Alembic current / heads | `20261023_discovery_079` ambos |
| Backend producción/tests / migraciones | 0 /0 |

Focused:
`npm --prefix frontend test -- src/components/TenderCreation.test.tsx src/components/TenderProductViews.test.tsx src/components/TenderRouting.test.tsx src/components/DocumentImports.test.tsx src/api/tenders.test.ts`.
Comandos npm completos existentes para test/build/typecheck. Browser:
`node frontend/scripts/ui-r7-new-browser.mjs backend/reports/ui_r7_new/browser`.
Regresiones existentes con destino nuevo bajo `backend/reports/ui_r7_new/`.
Desde backend, DB `licitia_test` e intérprete obligatorio:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_tenders.py tests/test_documents.py -q -k 'not opt_in'`.
Compilación desde raíz:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests`.

Warnings API: python_multipart/Swig deprecados y ccache ausente; live Ollama opt-in excluido.
Warning frontend conocido de clave duplicada en fixture DocumentViewer, sin cambio de producción
para ocultarlo. Mocks prueban contrato/control/UI, no calidad documental ni fuentes públicas.

## Cobertura de aceptación

| Gates | Evidencia |
|---|---|
| A–B crear vacía/múltiples | focused, browser rutas Resumen/Documentos y contratos reales |
| C–D carpeta/anidados | selector nativo Chromium6originales + lector recursivo multibatch/drop |
| E–F formatos/omisiones | contrato permisivo real, ZIP/ocultos, ruta insegura visible y excluida |
| G–H importación/seguridad | único DocumentImports, regresión conflictos UI-R3, Same.pdf B→A y duplicado |
| I escala | 5/30/125 selecciones, lista plegable/scroll sin componente pesado |
| J parcial | 2conflictos+1fallo en browser, Tender conservado, retry explícito |
| K sin autoanálisis | E2E allowlist sólo POST Tender/import; sin llamadas a motores |
| L sin expansión | diff backend vacío,079,package/lock intactos |
| M lenguaje | etiquetas humanas; técnicos no requeridos para crear/importar |
| N Discovery | E2E Product UI y regresión UI-R2 intactos |
| O regresión | focused/full/API/browser/build/types/compile/diff verdes |

UIR7-NEW01–39 se cubren con casos combinados de focused y browser. NEW11–14 respetan la
realidad del contrato: no se inventa rechazo de formatos inexistente; se verifica omisión
operacional segura, reporte visible y continuación con archivos válidos.

## Capturas y artefactos

`backend/reports/ui_r7_new/browser/`:
01-new-initial.png,02-from-expediente.png,03-multiple-selected.png,04-folder-selected.png,
05-nested-folder-summary.png,06-omitted-selection.png,07-successful-import.png,
08-partial-conflicts.png,09-create-empty.png,10-collapsed-1366.png y11-creation-{1440,1920,1024,768,390}.png.
`contact-sheet.png` reúne diez estados. `inputs/Expediente` contiene sólo archivos sintéticos
creados para el selector nativo; nunca documentos de clientes o Tender002.
Logs/hashes/results/validation quedan locales, sin stage. Reportes UI-R0–R7 previos preservados.

## Archivos incrementales de esta corrección

Modificados:
- docs/roadmap.md
- docs/ui-r7-closure.md
- docs/adr/0041-product-ui-closure.md
- frontend/src/ProductApp.tsx
- frontend/src/api/tenders.ts
- frontend/src/api/tenders.test.ts
- frontend/src/components/DocumentImports.tsx
- frontend/src/components/TenderDocumentsView.tsx
- frontend/src/components/TenderProductViews.tsx
- frontend/src/components/TenderProductViews.test.tsx
- frontend/src/components/TenderRouting.test.tsx
- frontend/src/components/tenderDocuments.css
- frontend/scripts/ui-r3-browser.mjs

Nuevos:
- docs/ui-r7-new-tender.md
- frontend/src/components/TenderCreation.tsx
- frontend/src/components/expedienteSelection.ts
- frontend/src/components/TenderCreation.test.tsx
- frontend/scripts/ui-r7-new-browser.mjs

La lista es incremental respecto de UI-R7 anterior, no reemplaza su diff acumulado contra HEAD.

## Límites y cierre

Las selecciones/File viven en memoria: refresh/cierre puede perderlas tras advertencia.
No se añaden jobs, persistencia de cola o garantía transaccional conjunta. Carpetas dependen
del navegador; el selector nativo se probó en Chromium, no se certifican otros runtimes.
No extracción ZIP, directorios backend, nuevos formatos de análisis ni autorización automática
contractual. Las ubicaciones relativas existentes son metadata, nunca destinos de escritura.

Listo para revisión final humana; sin autorización de commit UI-R7 ni cierre visual automático.
No UI-R8, instalador, demo ni prueba real nueva iniciados.

RX23 TUSCOPE UI-R7 NUEVA LICITACIÓN FROM EXPEDIENTE COMPLETE — READY FOR FINAL HUMAN REVIEW
