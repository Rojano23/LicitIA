# ADR-0026 — M8-A: agregación derivada de Bid Readiness

Estado: M8-A FUNCTIONALLY ACCEPTED + performance gate PASS. MVP-07 CLOSED / M7-D ACCEPTED.

Sin migración/dependencias. Adaptador llama una vez a Workspace canónico y una vez a
commercial-readiness-v1; carga metadata de documentos en lote. Motor puro transforma
esos contratos sin leer/interpretar contenido, disparar extracción, percepción o pricing.
Conserva estado/razón originales, UUID de entidad y referencia de documento/versión/página
cuando disponible. No crea issues persistidos ni resoluciones humanas nuevas.

Dimensiones DOCUMENTS, REQUIREMENTS, REQUESTED_EVIDENCE, SCOPE, QUANTITIES, COMMERCIAL,
HUMAN_REVIEW. Un vocabulario READY/INCOMPLETE/REVIEW_REQUIRED/BLOCKED/NOT_APPLICABLE.
Precedencia BLOCKED > INCOMPLETE > REVIEW_REQUIRED > READY; NOT_APPLICABLE sólo según
hechos canónicos explícitos (p.ej. requisito superseded/rechazado con review vigente).
Warnings no cambian READY. Ausencia de requisitos/Scope no confirma inexistencia: se
informa NOT_OBSERVED/INCOMPLETE. Sin porcentajes ni política institucional.

Issue determinista UUID5(Tender,dimensión,tipo,id,código), severidad BLOCKER/REVIEW/WARNING,
estado subyacente, resumen y contexto de revisión. Registros READY/NOT_APPLICABLE se
conservan en dimensions/items; issues contiene sólo acciones/warnings. HUMAN_REVIEW
referencia revisiones pendientes existentes, no duplica entidades persistidas; sus
conteos pueden referir la misma entidad que otra dimensión y se declaran como señales.

Requested Evidence consume definición/tipo/revisión de representación existentes;
no certifica fulfillment/compliance ni checklist completo. Advertencia de cobertura
constante; Ready significa únicamente listo según los registros rastreados. Rechazar
representación no implica afirmar que la obligación contractual no exista. Conflictos
canónicos se preservan (nombre documento, effective/source conflict); no resolverlos.

No M8-B/C/D, tareas/fechas/responsables/overrides, edición Quantity, freeze ni propuesta.
Consultas puras sin timestamps volátiles, orden estable y filtros sobre resultado completo:
filtrar issues no oculta bloqueos en summary. Errores de contrato/servicio se exponen;
no fallback vacío que produzca READY. Scope/Quantity originales permanecen inmutables.

No se duplican consultas por issue: cada lector se invoca una vez. Los lectores existentes
mantienen validación/revisión por Scope; medir composición sintética y reportar ese costo,
sin afirmar O(1) global ni reescribir motores en este slice.

Una revisión Requirement APPROVED/CURRENT es autoritativa sobre advertencias automáticas
de representación: se conservan como WARNING, sin rechazar otra vez lo ya aceptado. No
supera fuente efectiva ambigua/no resuelta, aplicabilidad desconocida ni una definición
de Requested Evidence aún no determinada. Rechazar representación excluye ese registro
rastreado, sin afirmar inexistencia de la obligación contractual.

## Gate de rendimiento M8-A

Aceptación funcional seguida de hardening autorizado. `canonical_read_batch` vive sólo
mientras se compone un Tender: precarga documentos/páginas/normalizados/Scope/Quantity/
historial, conserva referencias ORM y reutiliza resultados puros de proyección, revisión
Scope, enumeración de artefactos y validación de manifests. Los lectores siguen ejecutando
las mismas validaciones; errores no se memoizan. Resultados copiados evitan mutación entre
consumidores. `finally` elimina el estado incluso ante error; no caché global ni entre
requests. Workspace carga todos los Quantity en una consulta agrupada por padre.

Observaciones: fixture con Requirements/2 Scope: 206 SELECTs históricos → 64. Fixture de
escala controlada sin Requirements: 166 → 41 con 2 Scope; 41 con 20 Scope y sus Quantity.
Salida equivalente antes/después, consulta nueva refleja cambios; pruebas toleran un
margen acotado y no fijan un conteo absoluto frágil. No promete SQL constante respecto
al número de documentos/generaciones distintas, sólo elimina las familias por Scope.
