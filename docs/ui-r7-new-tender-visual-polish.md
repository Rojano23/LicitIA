# UI-R7 — Nueva licitación: pulido visual final

Estado: implementado y validado, listo para revisión final humana. Sin stage/commit/push.
HEAD conservado: `239c8b5e057f089d28bb0bccc053f8b4a97043e6`.
Continuación visual del [flujo aceptado](ui-r7-new-tender.md); no UI-R8.

## Cambios

- Una sola superficie de expediente, con dos acciones secundarias compactas: Seleccionar
  archivos y Seleccionar carpeta. Los inputs nativos siguen separados, etiquetados y
  accesibles por teclado; su label muestra foco visible. Se elimina el doble recuadro con
  selector nativo visible dentro de otro botón.
- Ayuda inicial breve: “Se agregarán al expediente los archivos compatibles.” Sin aviso
  de ZIP, extracción, navegador o limitaciones de análisis en la pantalla inicial.
- Resumen de selección primero; conteo por extensión y archivos dentro de Revisar archivos,
  plegado por defecto. Ver archivos omitidos sólo aparece cuando hay omisiones reales.
- Quitar todos queda dentro de la revisión expandida, junto a las acciones individuales.
- Se elimina texto repetido antes del botón principal. No se cambia información de conflictos,
  duplicados, revisión, fallo por archivo o resultado parcial después de crear.

## Preservación funcional

Sin cambios en handlers de creación, FileList, lectura recursiva, clasificación, creación de
sesión, importación, duplicados/conflictos/revisiones o recuperación. La envoltura visual de
los inputs conserva sus atributos y handlers. No se agregó un filtro de formatos.

El registro canónico acepta ZIP como original; no se lo convierte en no compatible mediante
este pulido visual. La advertencia proactiva se retiró, manteniendo el contrato funcional
aceptado. Las omisiones reales siguen visibles con su razón; nunca se descartan archivos
silenciosamente. No análisis ni extracción ZIP añadidos.

Comparación hash con `backend/reports/ui_r7_new/source_hashes.json`: sólo difieren los cuatro
archivos de implementación/pruebas/harness listados abajo. Todos los demás archivos del
cierre funcional, incluido importador/API, ProductApp y sesiones, mantienen sus hashes.

## Validación nueva

| Comprobación | Resultado |
|---|---|
| Focused Nueva licitación/documentos/wrapper | 43 passed /5files |
| Frontend completo | 326 passed /38files |
| Browser Nueva licitación | 6 grupos PASS; selector nativo de carpeta y omisiones |
| E2E Product UI | 8 grupos PASS |
| Browser UI-R3 | 12 grupos PASS |
| Browser sidebar | 10 grupos PASS;260/64px y estado conservados |
| Build / typecheck | PASS |
| git diff --check | PASS |
| Backend / migraciones / dependencias | 0 cambios |

Comandos focused y completos iguales al cierre funcional. Nuevos destinos de browser:
`node frontend/scripts/ui-r7-new-browser.mjs backend/reports/ui_r7_new_polish/browser`.
Regresiones existentes ui-r7-browser.mjs,ui-r3-browser.mjs yui-r5-sidebar-browser.mjs, ejecutadas
secuencialmente con datos sintéticos y nuevos directorios bajo `backend/reports/ui_r7_new_polish/`.
No portales ni proveedores reales. No se repite API/Alembic por cambios sólo de copy/CSS/markup:
127 API y Alembic079 pertenecen al cierre funcional previo y se conservan como evidencia heredada.
Las pruebas existentes sólo adaptan el nombre de la revisión y abren el disclosure para usar
sus acciones; ninguna aserción de dominio fue eliminada. Dos pruebas nuevas verifican la
superficie única, ausencia de explicación proactiva y ubicación/visibilidad de acciones.

## Capturas revisadas

`backend/reports/ui_r7_new_polish/browser/`:

1. `01-new-initial.png`: Nueva licitación inicial.
2. `02-from-expediente.png`: modo expediente antes de selección.
3. `04-folder-selected.png`: resumen compacto de carpeta.
4. `05-nested-folder-summary.png`: revisión expandida con Quitar/Quitar todos.
5. `06-omitted-selection.png`: omisión real con motivo, sin rutas absolutas.
6. `09-create-empty.png`: modo crear vacía.

`contact-sheet.png`: seis estados,1800×1320. La inspección técnica confirma una sola superficie
con dos botones secundarios, no dos tarjetas. También se conservan capturas de éxito parcial,
conflictos, sidebar contraída y anchos1440/1920/1024/768/390. Revisión humana final pendiente;
no certificación WCAG ni validación semántica mediante fixtures.

## Alcance incremental exacto

- frontend/src/components/TenderCreation.tsx
- frontend/src/components/tenderDocuments.css
- frontend/src/components/TenderCreation.test.tsx
- frontend/scripts/ui-r7-new-browser.mjs
- docs/ui-r7-new-tender-visual-polish.md

Los cambios anteriores de UI-R7 permanecen sin comprometer. Reportes, imágenes y archivos de
prueba nativa son locales, sin stage. No cambios backend, esquema, paquetes, historial o push.

RX23 TUSCOPE UI-R7 NUEVA LICITACIÓN VISUAL POLISH COMPLETE — READY FOR FINAL REVIEW
