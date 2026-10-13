# ADR-0009 — Alternative Scope Compliance Snapshots

**Estado:** Proposed — pendiente de revisión arquitectónica

**Fecha:** 2026-10-12

## Contexto

Compliance de requisitos/evidencia empresarial no expresa si una estrategia
humana satisface el alcance contractual vigente. Ambos dominios deben mantenerse
separados. Scope derivado puede regenerarse; una evaluación no puede impedirlo
ni reaplicar silenciosamente decisiones a otra revisión de estrategia o alcance.

## Decisión propuesta e implementada

Alternative Scope Compliance conserva snapshots inmutables vinculados a identidad,
revisión y fingerprint exactos de la alternativa. El alcance proviene del servicio
público de Scope Review, conservando máquina, provenance documental, proyección y
revisión humana aplicable. No hay FK a ScopeDetail derivado.

El fingerprint SHA-256 v1 del contexto de alcance usa JSON canónico UTF-8, tender
y items ordenados por identidad ScopeDetail. Incluye identidad máquina, contenido,
provenance, proyección y estado/revisión humana; excluye created_at, updated_at,
reviewed_at y notas humanas. El fingerprint de proyección para este contrato se
recalcula con esos mismos datos sin timestamps, no reutiliza el hash HTTP que
incluye timestamps. Rechazados se conservan sólo en contexto, sin obligación
evaluable. Contexto pendiente, stale o bloqueado impide aggregate COMPLIANT.
Regeneración idéntica con nueva identidad vuelve stale la evaluación.

Los juicios COMPLIANT/PARTIAL/NON_COMPLIANT/REVIEW_REQUIRED/NOT_EVALUATED son
exclusivamente humanos, con justificación no vacía e historial append-only.
No se identifica un actor autenticado inexistente. Current por número de revisión.
La agregación aplica: STALE; contexto unresolved; NON_COMPLIANT; PARTIAL;
REVIEW_REQUIRED; NOT_EVALUATED; todos COMPLIANT. Alcance vacío permanece
NOT_EVALUATED, sin declarar cumplimiento por ausencia de obligaciones.

Cada lectura compara ambas identidades vigentes: CURRENT, STALE_ALTERNATIVE,
STALE_SCOPE o STALE_BOTH. Conserva el aggregate histórico separado. Crear con el
mismo triple revisión/fingerprint alternativo/fingerprint Scope es idempotente.
Expectativas obsoletas o alternativas ARCHIVED no admiten nueva evaluación;
evaluaciones stale no admiten nuevos juicios, pero siguen legibles.

PostgreSQL protege historial contra UPDATE/DELETE y mantiene FKs RESTRICT entre
registros auditados. Para evitar carreras con regeneración, nuevas filas Scope y
Source Effects sin alterar escritores protegidos, las transacciones toman SHARE
en tablas de contexto documental/Scope y bloqueo de identidad alternativa
(SHARE en lectura, UPDATE en escritura). Las escrituras recalculan expectativas
bajo esos bloqueos y usan savepoints; caller controla commit/rollback. No hay
escrituras de persistencia en lecturas. El bloqueo es global por tabla, no por
tender: una limitación deliberada del runtime local actual, a revisar si existe
contención medida. Transacciones deben ser cortas; deadlocks/concurrencia HTTP
se reportan con códigos estables, sin detalles SQL.
Un ítem debe coincidir exactamente con un ítem evaluable del snapshot congelado;
constraints y trigger verifican identidad, contenido e índice. Contexto Scope con
cambios pendientes sin flush falla explícitamente (`SCOPE_CONTEXT_UNFLUSHED`),
sin descartarlos ni hacer flush implícito durante la lectura.

## Consecuencias

Sin autoridad LLM, equivalencia por vocabulario, porcentajes, ranking, selección,
precios ni mutación de Scope/estrategia. La API devuelve contratos tipados y
expone el snapshot vigente para proporcionar expectativas de creación.
Los resolvers y Compliance de requisitos/evidencia permanecen intactos.
Downgrade administrativo elimina únicamente el dominio nuevo.
