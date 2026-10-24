# ADR-0038 — Requisitos, evidencia, cumplimiento y Scope en Product UI

Estado: diseño UI-R4 autorizado; implementación pendiente de aceptación arquitectónica/visual.
Fecha: 2026-10-23. Baseline UI-R3 aceptado: `935dce1017195f69c1fb74138571b1c8583d037f`.

## Decisión

Componer tres vistas enfocadas sobre contratos existentes: requirement-matrix,
compliance-matrix por empresa y workspace.scopes/Quantity por FK. Las lecturas no ejecutan
análisis. Reutilizar acciones humanas canónicas, sin nuevos DTO backend o persistencia.
Extraer sólo los tipos reutilizados desde App hacia un módulo API frontend.

Conservar las tablas de decisión pequeñas y el detalle contextual. Separar hecho detectado,
evidencia solicitada, asociación candidata/confirmada, evaluación automática y decisión humana.
Mapas de presentación por contexto, no un estado universal que convierta asociación en cumplimiento.
Quantity permanece sólo lectura. Confirmar Scope no confirma cantidades.

Las vistas visitadas se conservan en memoria por Tender para volver de una fuente con
selección/filtros/empresa intactos. Requests están ligados a su contexto y generación;
los detalles seleccionados tienen identidad propia y sus escrituras no actualizan otro detalle.
No store/router nuevo. Documentos recibe parámetros opcionales document/page en su ruta existente;
se conserva revisión exacta, no se resuelve por filename. El plugin PDF sigue siendo nativo.

Los documentos empresariales conservan su contrato y ownership Company. No se insertan como
TenderDocument ni se usa un ID empresarial en el visor Tender. PDF empresarial abre el endpoint
Company existente; otros formatos conducen a la biblioteca, sin visor Office ficticio.

Estructura multipágina/página compartida procede exclusivamente de scope-summary. Vincular
segmentos a alcance sólo mediante IDs canónicos item/segment; no por candidate key o página.
Sin vínculo verificable se indica la limitación y se mantiene el contexto documental provisional
separado del inventario Scope. No hay completitud contractual inferida de cobertura parcial.

## Límites

Backend, esquema079, motores, OCR/Vision, proveedores/budgets y módulos UI-R5 sin cambios.
El endpoint de revisión Requirement y decisiones de asociación/cumplimiento no incorpora un
expected fingerprint del cliente: se conserva su contrato; no se promete nueva concurrencia
atómica. Scope sí conserva fingerprint/revisión esperados. Corrección literal de Requirement e
historial append-only no se inventan donde el contrato no los ofrece.

La fuente Requirement→Partida sólo se enlazará si existe relación canónica expuesta; en este
slice no se crea asociación por similitud. Los candidatos Vision quedan en Diagnóstico.
No renaming, gráficas, métricas falsas, certificación automática ni cambios al shell aprobado.
