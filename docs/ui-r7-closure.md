# UI-R7 — Cierre de Product UI

Estado autoritativo: **FINAL HUMAN REVIEW PASS — CLOSED**, por decisión final del Product Owner.
**MVP-01–10 CLOSED · UI-R0–R7 CLOSED · RX23 TuScope PRODUCT UI CLOSED.**
Aceptación incluye Nueva licitación desde expediente y su pulido visual final.
Commit local autorizado con `feat(ui): complete rx23 tuscope product experience`; sin push.
Los reportes y notas de ausencia de commit/revisión pendiente siguientes describen la evidencia
previa a esta aceptación; no sustituyen el estado autoritativo de este encabezado.
[Corrección desde expediente](ui-r7-new-tender.md) · [Pulido visual aceptado](ui-r7-new-tender-visual-polish.md).
[ADR-0041](adr/0041-product-ui-closure.md). MVP-01–10 permanecen cerrados.

## Evidencia del cierre anterior a la corrección de Nueva licitación

1. **Commit UI-R6:** 239c8b5e057f089d28bb0bccc053f8b4a97043e6

2. **HEAD resultante:** 239c8b5e057f089d28bb0bccc053f8b4a97043e6; sin push.

3. **Archivos comprometidos UI-R6:** 17 archivos aceptados, enumerados abajo. Hashes17/17 verificados contra evidencia previa; índice vacío antes del staging explícito. Reportes, imágenes, DB y entorno excluidos.

4. **Inventario de lenguaje:** 15 rutas/pantallas;42 archivos de componentes/helpers inventariados,1424 fragmentos JSX estáticos. `source-copy-inventory.json` es inventario, no prueba automática de todas las expresiones o textos fuente. Revisión dirigida adicional de propuestas, comercial y soportes.

5. **Enums:** Etiquetas en filtros/opciones/estado de lote comercial, composición, declaraciones, historial y verificación. Los values/DTO mantienen códigos canónicos. Códigos desconocidos solicitan revisar detalle técnico; códigos de resultado conservados en disclosure técnico.

6. **Términos técnicos:** snapshot → captura de preparación; inputs → información de la versión; freshness/stale → cambios posteriores; matching → búsqueda con reglas del perfil; Scope/Quantity → partidas/cantidades; board canónico → pendientes de licitación.

7. **Errores:** Exportación producto omite detail libre del servidor, ofrece reintentar misma solicitud y conserva archivos anteriores. No se ocultan errores mediante éxito falso. Modo técnico conserva detalle.

8. **Vacíos:** Vacíos existentes distinguen fallo de lectura y ausencia de resultados; acciones hacia importar, Discovery o revisión. No se agregaron ejemplos de producción.

9. **Acciones:** Revisar contenido de la evidencia conserva la operación real de análisis empresarial; no se presenta como matching. Preparar o actualizar contenido, Guardar captura de preparación, Consultar archivos generados.

10. **Excepciones diagnósticas:** Diagnóstico, integridad, identidad de captura, auditoría técnica, fuente canónica JSON y códigos en detalles expresamente técnicos. App heredado se abre por acción humana.

11. **Términos preservados:** Requisito, evidencia, partida, cotización, costo, precio, markup y margen distintos, MXN/USD/EUR y formatos DOCX/XLSX/PDF/ZIP. Texto fuente y notas humanas no se reescriben.

12. **Jerarquía:** h1 del shell conservado; secciones contextuales compactas y niveles existentes. Verificación de un solo h1 visible en capturas; no decoración permanente de foco.

13. **Botones:** Primitivas/tokens aceptados y estilos de módulos sin nuevo sistema visual; generación, guardado y confirmaciones continúan explícitos.

14. **Badges:** Estados textuales y traducciones; sin badges decorativos nuevos ni semántica sólo por color.

15. **Avisos:** Mensajes locales al módulo; no se duplica warning de una condición con nuevos paneles. Sin aviso de falla global por fallo documental aislado.

16. **Detalles:** Trazabilidad a una interacción; diagnóstico más profundo. Tablas y visor conservan proporciones; no se agregaron columnas.

17. **Ingeniería/duplicados:** Inventario PRODUCT/SECONDARY/DIAGNOSTIC/OBSOLETE DUPLICATE en ADR0041. No segunda ruta primaria. No se borró backend ni componentes todavía usados.

18. **Teclado:** Regresiones de shell/sidebar y browser previos verdes, navegación contextual conservada. Sin nuevo widget de teclado.

19. **Foco:** :focus-visible de shell preservado; return de foco/menú y fuente/visor de UI-R3 conservados. Capturas normales desenfocan controles; no quitan accesibilidad.

20. **Nombres accesibles:** Botones/controles y un h1 visible comprobados en capturas finales; iconos/sidebar cubiertos por tests previos y regresión final.

21. **Formularios:** Labels nativos/aria-label existentes; opciones traducidas con values explícitos. Decimales siguen cadenas y no cambian cálculos.

22. **Diálogos:** Confirmaciones/prompt nativos existentes, sin nuevo modal. Conflictos múltiples conservan correlación/semántica aceptadas y regresión UI-R3.

23. **Estados:** Status/alert textuales; vacío/error/carga separados. No estados basados únicamente en color.

24. **Movimiento:** No se agregan animaciones/transiciones; shell sin movimiento decorativo. No se requiere animación para comprender estados; no certificación WCAG.

25. **1366×768:** Siete áreas densas pasan bounds de página y capturas. Tabla con scroll local; PDF conserva prioridad.

26. **1440×900:** PASS bounds y capturas del recorrido final.

27. **1920×1080:** PASS bounds; máximo de shell conservado.

28. **1024×768:** PASS bounds en siete áreas densas.

29. **768×900:** PASS bounds; menú/tabs/scroll local conservados.

30. **390×844:** PASS sanity de bounds; no se certifica preparación completa de ofertas en móvil.

31. **Sidebar:** Regresión10grupos:260px expandida/64px contraída; visor775→971px con registro250px constante.

32. **Persistencia:** Clave tuscope.sidebar.desktop y fallback expandido intactos; pruebas Sidebar/SidebarState y browser verdes.

33. **Estado/refetch:** E2E conserva nota comercial no guardada tras rutas globales y return; toggle no agrega requests. Montajes visitados conservados.

34. **Bundle antes:** Medición in-memory Vite/Rollup:640318 bytes UTF-8 iniciales; baseline build UI-R6 heredado638.16kB. Son medidas diferentes y no se confunden.

35. **Contribuyentes:** App.tsx294334 bytes renderedLength; react-dom133343; CompanyEvidenceLibrary47753; Discovery33709; axios utils30998; CommercialMatrix27576; ScopeReview26088. renderedLength no es tamaño minificado final.

36. **Decisión de carga:** React.lazy/Suspense sólo para App técnico heredado. Se carga al abrir herramientas, permanece montado tras primera visita. Boundary local ofrece reintento; no reload global.

37. **Bundle después:** Consultar build.log y bundle-final.json: entrada aproximadamente468kB + chunk técnico174kB; reducción inicial aproximada27%. CSS35.04kB. Tamaños exactos finales en evidencia.

38. **Warning:** Build final sin warning >500kB. No se aumentó umbral ni añadieron dependencias.

39. **Riesgo:** Primer acceso a herramientas técnicas requiere descargar chunk local. Fallo de carga recuperable localmente; no cambia dominios/retención de formularios. No fragmentación agresiva.

40. **Recorrido completo:** Un harness determinista, una sesión desde Inicio/Discovery hasta generación de propuesta y retorno;8grupos PASS. API interceptada sólo con fixtures sintéticas. No prueba semántica ni sistema backend completo.

41. **Discovery→Tender:** Follow PATCH y handoff POST explícitos, selección documental y confirmación humana; expected_binding preservado.

42. **Documentos:** PDF sintético de9páginas servido como bytes y visor original; fuente a página7. No documentos reales.

43. **Requisitos:** Detalle y fuente canónica consultados sin análisis automático; decisiones humanas permanecen separadas.

44. **Cumplimiento:** Empresa y evidencia candidata seleccionadas; asociación no presentada como certificación.

45. **Partidas:** Registros/cantidades read-only y ownership de fixtures alineado; no extracción ni edición de cantidad.

46. **Comercial:** Separación monedas/costos/decisiones; borrador de nota comercial conservado al salir y regresar.

47. **Preparación:** Estado de respuesta local, bloqueo/faltante distinto de actividad humana; no snapshot automático.

48. **Propuesta:** Captura elegida, borrador creado por acción, composición consultada, autorización de borrador y Generar PDF explícitos; enlaces de cuatro formatos de fixture. No afirmación de render backend por este harness.

49. **Rutas globales:** Inicio,Discovery,Licitaciones,Mi empresa,Reportes,Configuración y Diagnóstico; todas las8rutas Tender verificadas. Sin nuevas rutas.

50. **No autoanálisis:** Exactamente4escrituras en E2E: seguimiento, crearTender, crearborrador, generararchivo. Allowlist impide escrituras extra. Cero OCR/Vision/Ollama/análisis por navegar.

51. **Mocks:** Búsqueda de imports/fixtures/mocks revisada: coincidencias sólo bajo src/test y harnesses. Runtime usa contratos/API existentes; cero datos de ejemplo agregados.

52. **Paths/secretos:** Sin rutas absolutas/env/DB/passwords/token nuevos en UI normal; URLs localhost de conexión internas no se muestran como error. Texto documental/humano conserva literalidad, no se altera por esta auditoría.

53. **Copia de soporte:** Allowlist existente preservada; tests con PRIVATE_SECRET prueban exclusión de campos libres/URL/configuración. No telemetry/copia automática.

54. **Focused:** 108 passed /13files; comando/log bajo reports/ui_r7/focused.log. Incluye contratos comerciales/propuesta, soporte, shell/sidebar y nuevas pruebas de error/carga diferida.

55. **Frontend completo:** 306 passed /37files; frontend.log. Warning conocido de clave duplicada a en fixture DocumentViewer; no se cambia producción para ocultarlo.

56. **Browser:** Final8grupos; R6 10,R5 11,R4 11,R3 12,R2 13,sidebar10 PASS. Ejecución secuencial con targets limpios. Controles responsive/capturas en results.json.

57. **Backend API:** 117 passed,6warnings,229.60s. tests_company_library/company_evidence/proposal_exports/proposal_readiness/proposal_versions/proposal_composition/discovery_handoff/discovery_monitoring; -k not opt_in; PostgreSQL licitia_test. Warnings deprecación multipart/Swig y ccache según api.log.

58. **Build/typecheck:** PASS comandos npm existentes; logs locales. No package/lock modificado.

59. **Compile/diff:** Intérprete backend obligatorio -m compileall -q backend/app backend/scripts backend/tests PASS; git diff --check PASS.

60. **Alembic:** current y heads =20261023_discovery_079, verificación nueva; ninguna migración.

61. **Backend/deps:** 0cambios backend producción/tests,0dominios/APIs nuevos,0dependencias runtime.

62. **Archivos exactos:** Lista completa abajo; reportes/imágenes quedan locales y sin stage.

63. **Límites:** Fixtures no prueban calidad semántica ni disponibilidad pública. PDF nativo depende del navegador. No certificación WCAG, autenticación, instalador o Private Beta. Conservación histórica de5941 heredada, no se repitió barrido ni se leyó Tender002. Refresh completo puede perder borradores en memoria, como antes.

64. **Gates A–S:** A–R: validación técnica con evidencia y límites anteriores. S: revisión técnica de capturas realizada; aprobación visual humana final PENDIENTE. No declarar cierre formal antes de esa aprobación.

65. **Preparación de cierre:** Implementación lista para revisión final humana. UI-R7 sin stage/commit/push. PRODUCT UI CLOSED queda reservado a decisión humana final; no UI-R8.

66. **Siguiente fase exacta:** Tras aceptación final: Product Owner prueba un expediente público real de extremo a extremo, documenta hallazgos y realiza demos controladas; correcciones justificadas, instaladorWindows y PrivateBeta después. No iniciar esa fase aquí.

## Archivos UI-R6 comprometidos

- `docs/adr/0040-global-support-product-ui.md`
- `docs/roadmap.md`
- `docs/ui-r6-implementation.md`
- `frontend/scripts/ui-r6-browser.mjs`
- `frontend/src/ProductApp.tsx`
- `frontend/src/api/SupportApi.test.ts`
- `frontend/src/api/company.ts`
- `frontend/src/api/diagnostics.ts`
- `frontend/src/components/CompanyView.tsx`
- `frontend/src/components/DiagnosticsView.tsx`
- `frontend/src/components/ReportsView.tsx`
- `frontend/src/components/SettingsView.tsx`
- `frontend/src/components/SupportProduct.test.tsx`
- `frontend/src/components/supportProduct.css`
- `frontend/src/test/supportFixtures.ts`
- `frontend/src/ui/Shell.test.tsx`
- `frontend/src/ui/companyPresentation.ts`

## Archivos UI-R7 modificados/nuevos

- `docs/roadmap.md`
- `frontend/scripts/ui-r5-browser.mjs`
- `frontend/src/ProductApp.tsx`
- `frontend/src/components/CommercialAuditDetails.tsx`
- `frontend/src/components/CommercialLine.tsx`
- `frontend/src/components/CommercialMatrix.test.tsx`
- `frontend/src/components/CommercialMatrix.tsx`
- `frontend/src/components/CommercialProduct.test.tsx`
- `frontend/src/components/CommercialSpreadsheet.test.tsx`
- `frontend/src/components/CommercialSpreadsheet.tsx`
- `frontend/src/components/CompanyView.tsx`
- `frontend/src/components/ProposalComposition.test.tsx`
- `frontend/src/components/ProposalComposition.tsx`
- `frontend/src/components/ProposalExports.test.tsx`
- `frontend/src/components/ProposalExports.tsx`
- `frontend/src/components/ProposalReadiness.test.tsx`
- `frontend/src/components/ProposalReadiness.tsx`
- `frontend/src/components/ProposalVersions.test.tsx`
- `frontend/src/components/ProposalVersions.tsx`
- `frontend/src/components/ReadinessView.tsx`
- `frontend/src/components/ReadinessWork.test.tsx`
- `frontend/src/components/ReadinessWork.tsx`
- `frontend/src/components/ReportsView.tsx`
- `frontend/src/components/SettingsView.tsx`
- `frontend/src/components/SupportProduct.test.tsx`
- `frontend/src/ui/commercialPresentation.ts`
- `docs/adr/0041-product-ui-closure.md`
- `docs/ui-r7-closure.md`
- `frontend/scripts/ui-r7-browser.mjs`
- `frontend/scripts/ui-r7-audit.mjs`
- `frontend/src/ui/Closure.test.tsx`
- `frontend/src/ui/DeferredWorkspace.tsx`

## Reproducibilidad y evidencia

`backend/reports/ui_r7/`: focused.log, frontend.log, api.log, build.log, typecheck.log,
alembic.log, bundle-before.json, bundle-final.json, source-copy-inventory.json, hashes y
validation.json. Capturas finales en `browser/`, hoja `browser/contact-sheet.png` de15pantallas.
Screenshots:01-inicio,02-discovery,03-licitaciones,04-resumen,05-documentos,06-requisitos,
07-cumplimiento,08-partidas,09-comercial,10-preparacion,11-propuesta,12-mi-empresa,
13-reportes,14-configuracion,15-diagnostico;16-commercial-collapsed;42responsive adicionales.
Comandos: `npm --prefix frontend test`, `npm --prefix frontend run build`,
`npm --prefix frontend run typecheck`, `node frontend/scripts/ui-r7-browser.mjs backend/reports/ui_r7/browser`,
`node frontend/scripts/ui-r7-audit.mjs backend/reports/ui_r7`. Regresiones existentes con directorios
nuevos ui_r7/rN_regression, nunca sobrescribiendo reportes aceptados.

RX23 TUSCOPE UI-R7 PRODUCT UI CLOSURE COMPLETE — READY FOR FINAL HUMAN REVIEW
