# ADR-0020 — Composición canónica del Workspace provisional

Estado: ACCEPTED RC-H2, commit `415669f3a42850971ef57bae031ce19a622340b4`.

## Contexto

Los servicios de extracción, materialización, requisitos y revisión están aceptados,
pero su composición completa estaba disponible principalmente desde validación.
El Workspace requiere acceso normal sin depender del harness ni interpretar evidencia
en frontend. No se autoriza ampliar semántica ni crear una migración de revisión.

## Decisión

Agregar GET `/tenders/{id}/workspace` y POST `/tenders/{id}/workspace/process`.
Compartir la preparación Native y la composición canónica mediante módulos de
aplicación. Los módulos históricos conservan exports compatibles. El camino normal
usa `AVAILABLE_ONLY`: consume evidencia existente, sin adquisición automática de
OCR/Vision ni descubrimiento experimental de Source Effects con LLM.

Responder con DTOs Pydantic y contratos TypeScript. Anidar Quantity bajo su FK Scope
y validar la evidencia estructurada con el validador canónico de persistencia.
Una asociación contradictoria se presenta sin resolver y nunca se reasocia.
La revisión y corrección de Scope siguen usando su API autoritativa y su auditoría.

El estado operacional conserva únicamente el último intento por Tender en
`workspace-processing-v1` bajo el root configurado, sin texto documental. Un lock
`flock` por Tender evita procesamiento concurrente entre workers locales que usan
el mismo filesystem. Un reemplazo atómico conserva estado tras reinicio y detecta
interrupción al desaparecer el lock. La identidad de documentos, páginas y versiones
normalizadas detecta resultados desactualizados. No se crean jobs ni tablas.
Retención: un estado y un lock por identidad de Tender, reemplazados en cada ejecución, sin log acumulativo ni vencimiento automático. Su eliminación corresponde al mantenimiento del root; borrar el Tender en DB no elimina estos archivos operacionales.

## Consecuencias y límites

El request de procesamiento es síncrono; otro cliente puede consultar estado. No hay
cola distribuida ni garantía de coordinación entre roots distintos. No es un lock
para las demás operaciones existentes del expediente; los cambios detectados exigen
volver a procesar. Un fallo preserva originales y puede dejar derivados parciales
por los límites transaccionales existentes; se informa FAILED y no se revierte una
preparación aceptada previamente.

Quantity permanece de solo lectura. La revisión de Scope no confirma cantidades.
Agregar decisiones independientes de Quantity requiere un contrato/esquema auditado;
se clasifica P1 para RC-H3. Sus IDs pueden regenerarse por el materializador existente.
Las fuentes ofrecen navegación de página y extracto, sin resaltado geométrico nuevo.
Los resultados de requisitos/evidencia siguen siendo provisionales y visibles para
validación humana; no certifican una lista contractual completa.

Sin cambios de esquema, motor semántico, proveedores, budgets, auth, export o diseño
final. El despliegue continúa restringido a Limited UAT local controlada.
