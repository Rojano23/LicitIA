# RC-H1 commit + RC-H2 Workspace Functional Flow

Estado: implementación completa; todos los gates RC-H2 autorizados pasan, con Quantity independiente P1 conforme a la excepción aprobada. Lista para revisión arquitectónica; todavía sin aceptación/commit RC-H2.

## RC-H1

Commit y HEAD de baseline: `65b3465c35877408aafe15757d3e74aaddf10e36`.
Asunto: `chore(rc): add reproducible local uat deployment`. Sin push.
Se comprometieron exclusivamente los 21 archivos aceptados:

```
.env.example
README.md
backend/.env.example
backend/alembic.ini
backend/app/config.py
backend/app/local_deployment.py
backend/pyproject.toml
backend/requirements-rc-macos-arm64.lock
backend/requirements.txt
backend/runtime_guard/sitecustomize.py
backend/scripts/licitia_local.py
backend/tests/test_local_deployment.py
docker-compose.yml
docs/adr/0019-local-uat-deployment.md
docs/local-deployment.md
docs/roadmap.md
docs/uat-admin-quickstart.md
frontend/.node-version
frontend/package-lock.json
frontend/package.json
frontend/vite.config.ts
```

No reportes históricos, originales, credenciales, entornos ni bases locales incluidos.
Se conserva el límite aceptado: no fue una instalación sobre un SO/VM completamente
nuevo; las herramientas del sistema estaban instaladas. La restricción de red de
Python no equivale a un firewall del host.

## RC-H2: arquitectura, gaps y servicios

El Workspace existente conserva selección/creación de Tender, importación documental,
controles de extracción, matriz/revisión de Requirements, Requested Evidence y revisión
Scope mediante APIs reales. No se introdujeron datos simulados en producto.

Gap: preparación y composición completa del camino validado se invocaban desde módulos
de validación; faltaba la composición normal y una presentación Scope→Quantity con
parent explícito, procedencia y estado operacional recuperable.

La nueva composición sigue:

```
Workspace existente
 → POST /tenders/{id}/workspace/process
 → preparación Native canónica + normalización
 → Requirements / normalización / semántica / versiones
 → estructura AVAILABLE_ONLY
 → Scope / Attributes / Quantities
 → Source Effects deterministas
 → GET /tenders/{id}/workspace (DTOs canónicos)
 → fuentes + revisión humana Scope / revisión Requirements existentes
```

`prepare_tender_documents` y `materialize_canonical` se movieron a módulos de aplicación
compartidos. Los módulos de validación conservan exports compatibles; el producto no
importa el harness. Comparación AST contra HEAD: ambas funciones **idénticas**
(`shared_service_equivalence.json`). No segunda interpretación en frontend.

Las rutas nuevas son aditivas. GET conserva contratos completos de matriz y semántica,
DTOs explícitos de Scope y Quantity y estado operacional. POST usa esos mismos servicios
y responde con el mismo contrato. No se cambió el contrato de rutas existentes.

## Scope, Quantity y ownership

El E2E importa un PDF tabular sintético por API, procesa por la ruta normal y consulta
el resultado sin materialización directa del test. Obtiene dos Scope (31/32) con
Quantity 3 PZA y 7 PZA respectivamente. Cada hijo conserva `tender_id`,
`scope_detail_id`, fuente y estado. Los DTOs anidan cantidades por FK y Tender, el
servidor reutiliza el validador canónico de evidencia estructurada y el frontend rechaza
identidades padre/Tender incompatibles.

La prueba con dos padres verifica que una cantidad no se puede presentar como válida
bajo el otro padre, incluso tras forjar su FK en el test: queda UNRESOLVED; nunca se
reconstruye una asociación por posición de fila. Reprocesar conserva Scope y valores,
pertenencia y procedencia de Quantity. El materializador existente puede regenerar
IDs de Quantity; no se prometen IDs estables ni se cambió esa semántica.

## Procedencia y revisión

Scope y Quantity muestran documento, revisión, página, extracto, locator y método,
con enlace al original y navegación a página cuando el visor lo soporta. Sin visor
avanzado ni resaltado geométrico nuevo. Una fuente/manifiesto ausente no oculta todos
los registros: muestra fuente no disponible o asociación sin resolver y estado parcial.

Scope reutiliza confirmación/corrección/rechazo, control optimista de concurrencia,
vigencia e historial append-only existentes. El test corrige por API, consulta la
descripción humana y verifica su conservación tras reprocesar. Quantity conserva
REVIEW_REQUIRED y no hereda la aceptación/corrección del padre.

Quantity independiente: **P1, solo lectura**. `TenderScopeReview` admite corrección de
descripción de Scope y su snapshot no identifica/versiona decisiones sobre cada hijo
Quantity. Reutilizar notas o interpretar aceptación Scope como aceptación Quantity
perdería auditoría. No se creó migración ni otro workflow. Es la excepción autorizada
en la fase 7, no una capacidad completada de edición Quantity.

## Requirements / Requested Evidence

La vista consume la matriz canónica y semántica existentes: conserva revisión,
normalización, vigencia, incertidumbre, warnings, extracto y fuente. No se ocultan
registros contextuales/revisables. El test de PDF genérico con una solicitud de carta
comprueba requisitos y evidencia solicitada no vacíos, procedencia y equivalencia con
los lectores canónicos. Los controles completos existentes de revisión de requisitos
siguen disponibles; no se agregó un segundo mecanismo de decisión.

Requested Evidence identifica su requisito, estado de interpretación, tipo y fuente.
El banner y la sección dicen que requiere validación humana y que no es una lista
contractual certificada. Los originales siguen siendo autoritativos; los resultados
pueden estar incompletos.

## Estados y errores

Sin procesar; procesando; completado; completado con revisión requerida; parcial;
fallido; interrumpido; desactualizado. Los estados no exponen terminología de validación
ciega. GET/refresh no procesan automáticamente. POST exige una acción humana y evita
concurrencia entre workers locales mediante lock por Tender/root compartido.

Se conserva únicamente el último estado por Tender en el root local, con reemplazo
atómico, permisos restringidos y sin texto documental. El archivo sobrevive al proceso;
una pérdida del lock con estado PROCESSING se informa interrumpida. La identidad de
documentos, páginas y generaciones invalida el estado cuando cambia el expediente.
Sin tablas nuevas ni sistema de jobs. No hay vencimiento automático de estos archivos;
el mantenimiento del root conserva la responsabilidad de su eliminación.

409 sin documentos o por otra ejecución; 404 si no existe Tender; 422 con código y
run_id operativo al fallar. El frontend explica backend no disponible, parcial,
fuente ausente, falta de resultados y errores, sin convertir ausencia en cumplimiento.
El procesamiento es síncrono; puede dejar derivados parciales por las fronteras de
commit existentes. No repara automáticamente estados inconsistentes.

OCR/Vision: este paso usa evidencia disponible sin adquirir percepción ni cambiar
providers/budgets. Los controles explícitos existentes permanecen separados. PDFs
escaneados/insuficientes pueden quedar parciales. Los tests prohíben invocaciones reales
a Tesseract/Paddle/Ollama para este flujo; no son prueba de calidad de modelos reales.

## Camino aceptado e integridad

Comprobación de representación de solo lectura sobre first-pass congelado de Attempt #9:
2 Scope, 2 Quantity, 2 padres distintos y coincidencia de documento/página con su padre.
El contrato tipado admite exactamente estas relaciones. No se reejecutó el corpus ni
se usó para tuning, fixtures o nuevos Goldens. No adjudicación semántica nueva.

SHA first-pass: `8972172fd0c9c14ff2e20ba4e13e9c438bfee13d3fc8c5182af723c11972c1b6`.
Ver `accepted_path_representation.json`. Integridad: 4,560 archivos históricos y 1,381
de Attempt #9/bootstrap sin cambios ni faltantes (`historical_integrity.json`).

## Validación reproducible

| Validación | Resultado |
| --- | --- |
| Backend/API RC-H2 | 10 passed |
| Core | 206 passed, 1 skipped |
| Document Intelligence | 1,153 passed, 1 deselected |
| Full backend | 2,146 passed, 1 deselected |
| Frontend | 86 passed (5 archivos) |
| Frontend build | PASS |
| compileall | PASS |
| Alembic licitia_test | 072, head; sin migración nueva |
| git diff --check | PASS |

Comandos exactos core/DI/full: `regression_commands.json`; resultados de salida:
`regression_results.json`; conteos XML: `test_counts.json`.

Pruebas focales desde backend:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_workspace_flow.py -q --junitxml=reports/rc_h2/focused.xml`.

Frontend desde frontend: `npm test -- --reporter=dot` y `npm run build`.
Compilación desde raíz:
`/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests backend/runtime_guard`.

Consulta de esquema desde backend:
`DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current`.

Las pruebas usan licitia_test; ningún modelo real ni ejecución nueva de corpus ciego.
El fixture API usa PostgreSQL real y savepoints para rollback; la factoría del
orquestador también abre sesiones reales en esa conexión, sin mock de extracción o
materialización. Frontend usa contratos HTTP simulados; no certifica calidad semántica.
Los XML/logs conservan evidencia exacta. Warnings sin fallos: deprecaciones de
python_multipart/SWIG, configuración legacy de Alembic y ausencia de ccache en Paddle. No se modificaron motores para
eliminarlos.

## Archivos RC-H2

Los 16 archivos exactos de implementación/documentación/pruebas están también en
`implementation_files.json`:

```
backend/app/blind_selective_harness.py
backend/app/document_intelligence_blind_run.py
backend/app/main.py
backend/app/canonical_materialization.py
backend/app/native_preparation.py
backend/app/workspace_flow.py
backend/tests/test_workspace_flow.py
frontend/src/App.tsx
frontend/src/api/workspace.ts
frontend/src/components/WorkspaceFlow.tsx
frontend/src/components/WorkspaceFlow.test.tsx
frontend/vite.config.js
docs/roadmap.md
docs/uat-capability-statement.md
docs/adr/0020-workspace-canonical-composition.md
docs/workspace-functional-flow.md
```

`frontend/vite.config.js` es la sincronización generada por TypeScript del host loopback
ya aceptado en H1 en `vite.config.ts`; no cambia navegación ni diseño.
La evidencia nueva de esta ejecución permanece en `backend/reports/rc_h2/`, sin stage.
Los reportes históricos/no rastreados anteriores se preservaron.

## Límites y siguiente slice

Sin migración: Alembic `20261013_req_perception_prov_072 (head)` en licitia_test.
Sin cambio de extracción semántica, proveedores/budgets, diseño final, auth o export.
ADR-0020 documenta la composición y sus límites para revisión arquitectónica.

La revisión independiente Quantity queda como P1 explícito; navegación de fuente es
por página/extracto; resultados de Requirements/Evidence siguen incompletos y requieren
contraste humano. El lock no coordina otras operaciones de extracción existentes ni
roots diferentes. Evitar modificaciones concurrentes del expediente mientras procesa.
No se afirma readiness productivo general ni extracción autónoma completa.

Recomendación RC-H3: aceptar primero el contrato de revisión Quantity con identidad,
snapshot, concurrencia, auditoría y regeneración; sólo entonces autorizar su esquema.
Agregar recuperación operacional guiada para procesamiento inconsistente si la UAT
lo demuestra. Mantener UI provisional y el resto de gates del roadmap separados.

RC-H2 se entrega sin stage, commit ni push. La aceptación arquitectónica precede a
cualquier commit de RC-H2.


Git final: HEAD RC-H1 sin cambios; índice vacío, RC-H2 sin stage/commit/push.
Los cambios exactos son los 16 archivos enumerados; no hay blocker obligatorio pendiente.
Técnicamente listo para proponer commit RC-H2 después de aceptación arquitectónica, sin ejecutarlo ahora.

LICITIA RC-H2 WORKSPACE FUNCTIONAL FLOW COMPLETE — READY FOR ARCHITECT REVIEW
