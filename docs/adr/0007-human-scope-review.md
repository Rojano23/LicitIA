# ADR-0007 — Revisión humana de ScopeDetail separada de evidencia máquina

**Estado:** Proposed — pendiente de revisión arquitectónica

**Fecha:** 2026-10-12

**Slice:** MVP-06.6.1

## Contexto

ScopeDetail conserva descubrimiento, ownership, provenance y `review_required`.
No existe revisión humana persistida de ScopeDetail. Las revisiones de
Requirements/Compliance usan registros actualizables, sin historial append-only
reutilizable. El materializador de ScopeDetail reemplaza filas por artefacto.
La proyección de fuentes combina incertidumbre del hecho y de la fuente; una
confirmación del hecho no puede resolver precedencia documental ni revivir fuentes.

## Decisión propuesta e implementada

- `TenderScopeReview` almacena CONFIRMED, CORRECTED o REJECTED, nota opcional,
  fecha UTC, revisión incremental, snapshot máquina tipado y fingerprint de la
  proyección revisada. No existe identidad de usuario autenticado en este slice;
  no se inventa un sistema de auth ni un identificador de reviewer.
- CORRECTED contiene exclusivamente una descripción no vacía, validada por
  Pydantic y constraints PostgreSQL. No cambia ownership, atributos, cantidades,
  clasificación ni provenance. Es un override separado, no un nuevo hecho máquina.
- La evidencia auditada incluye todos los campos de ScopeDetail, número de página
  y revisión documental. No incluye binarios. El snapshot preserva el estado exacto
  que vio el revisor; la corrección almacena sólo el campo cambiado.
- El historial es append-only en servicio y en PostgreSQL (trigger UPDATE/DELETE).
  La última decisión es la de mayor `revision`, única por ScopeDetail. La escritura
  bloquea la fila ScopeDetail hasta completar la transacción para serializar revisiones.
  El caller controla commit/rollback; las lecturas no hacen flush.
- `scope_detail_id` es identidad histórica sin FK al derivado. Una FK al tender
  con RESTRICT protege el historial; ningún cascade puede borrar revisiones.
  El servicio y un trigger INSERT verifican que el detalle exista, pertenezca al
  tender y coincida con la identidad del snapshot. El trigger toma KEY SHARE sobre
  el detalle durante la inserción. UPDATE/DELETE del historial siguen prohibidos.
  La regeneración puede eliminar/reemplazar filas máquina sin modificar revisiones.
  El historial se consulta por tender e ID histórico, aun sin la fila original.
- La lectura conserva la proyección original completa. Una decisión vigente puede
  satisfacer únicamente `FACT_REVIEW_REQUIRED`. Estados documentales o de locator
  terminales/inciertos, blocking effects u otros diagnósticos mantienen SOURCE_BLOCKED.
  Cambios de evidencia o proyección vuelven STALE la decisión; no se recurre a una
  decisión anterior ni se aplica una corrección vieja a evidencia nueva.
- La aplicabilidad requiere la misma identidad máquina, snapshot completo y
  fingerprint de proyección. Regenerar produce un ID nuevo: la vista nueva indica
  NO_REVIEW (PENDING si máquina exige revisión), y la revisión anterior queda
  exclusivamente como historial no aplicable bajo el ID anterior. Incluso con
  semantic_fingerprint idéntico, el ID nuevo cambia el fingerprint de proyección;
  no hay reattachment ni carry-forward de CONFIRMED/CORRECTED/REJECTED. Una revisión
  explícita sobre la fila nueva inicia su propio historial. El historial no puede
  congelar derivados ni revivir fuentes terminales o bloqueadas.
- REJECTED conserva máquina e historial y excluye el detalle del alcance aceptado
  en esta vista. Sin revisión, `review_required` produce PENDING; en su ausencia,
  NOT_REQUIRED. CONFIRMED/CORRECTED no alteran el flag máquina ni sus diagnósticos.

## Consecuencias y límites

Sin endpoints, frontend, cambios de resolvers, edición de hijos ni recálculo de
contratos existentes. Esta vista de dominio es la base de MVP-06.6.2 Review API +
Deterministic Recalculation. Los consumidores existentes conservan su estado
máquina hasta adoptar explícitamente la nueva vista.
Downgrade elimina únicamente el contrato añadido (y limpia la constraint obsoleta
de la implementación 069 anterior a aceptación, si todavía existe);
es una operación administrativa destructiva del historial, no una acción de usuario.
