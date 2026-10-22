# ADR-0027 — M8-B: decisiones de seguimiento de readiness

Estado: aceptado arquitectónicamente, commit M8-B `db3325c`. Esquema documentado ANTES de crear074.
Base M8-A8431338, performance gatePASS.

Inventario: TenderScopeReview tiene decisiones CONFIRMED/CORRECTED/REJECTED con snapshot
Scope y FK a identidad de Scope; RequirementReview valida representación; ComplianceDecision
exige empresa/requisito. Ninguna representa seguimiento de UUID derivado multi-dimensión.
Reutilizar esas tablas confundiría actividad humana con autoridad contractual o comercial.
Se reutilizan sus patrones de revisión append-only, timestamps y expectativas explícitas.

Una sola tabla específica `readiness_work_decisions` (Alembic074 sobre073): UUID PK,
tender_id FK RESTRICT, issue_id estable UUID5, revision>0 única por Tender/issue,
identity descriptor (dimension/entity_type/entity_id/code), context_sha256, workflow_status
OPEN/IN_REVIEW/RESOLVED/ACCEPTED_RISK/NOT_APPLICABLE, note≤4000, owner/actor_label≤200,
created_at UTC. Sin copia de estado canónico, fuente, precios o documentos. Trigger impide
UPDATE/DELETE. Índice Tender/issue/revision. No tabla de issues derivados ni otro review
subsystem genérico. Downgrade administrativo explícito elimina sólo esta historia.

Los ítems siguen derivados, con overlay de última decisión y evento histórico. Fuente
resuelta/entidad retirada se reconcilian al leer, sin inserts automáticos. Fingerprint del
contexto canónico del Tender (readiness + referencias de representación + state reference
comercial) invalida conservadoramente workflow anterior al cambiar hechos. Notas/historia
se conservan; estado efectivo vuelve OPEN si stale. Sin snapshot de propuesta.

ACCEPTED_RISK/NOT_APPLICABLE sólo para WARNING; REVIEW puede anotarse/IN_REVIEW y cerrar
actividad, pero nada modifica canonical readiness. RESOLVED manual no elimina blocker;
blockers_open sigue contando blockers existentes. Owner/actor son declaraciones libres,
no autenticación. Lectura carga overlay/history por lotes. Tender lock y expected_revision/
context protegen escrituras concurrentes. Ninguna acción modifica MVP-06/MVP-07.
