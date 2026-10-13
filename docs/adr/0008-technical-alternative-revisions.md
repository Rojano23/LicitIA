# ADR-0008 — Identidad y revisiones de alternativas técnicas humanas

**Estado:** Proposed — pendiente de revisión arquitectónica

**Fecha:** 2026-10-12

**Slice:** MVP-06.6.4a

## Contexto

El concepto futuro `TechnicalProposal` de domain-model v0.1 no está implementado.
Sus campos por partida, selección primaria y cumplimiento no constituyen el
contrato de este slice. La alternativa representa cómo propone cumplir el humano,
no qué exige el Scope. Compliance existente evalúa requisitos contra evidencia
empresarial; no se reutiliza como cumplimiento de una alternativa.

## Decisión propuesta e implementada

- TechnicalAlternative contiene sólo UUID estable, tender_id y fecha UTC.
  TechnicalAlternativeRevision conserva contenido humano completo por revisión.
  No copia Scope ni añade vínculos a requisitos, scores, selección o cumplimiento.
- Nombre obligatorio de hasta 255 caracteres, descripción obligatoria,
  assumptions y notes textuales opcionales. Pydantic estricto para textos elimina
  sólo espacios exteriores; conserva espacios interiores, caso y puntuación.
  Estados DRAFT, ACTIVE y ARCHIVED; archivar añade revisión preservando contenido.
  Puede haber varias alternativas ACTIVE; ninguna se elige automáticamente.
- Revisión positiva única por identidad. Historial ascendente y current por máximo
  número explícito; listado por UUID ascendente, sin ranking estratégico.
- Fingerprint SHA-256 de JSON canónico UTF-8 con contrato v1, nombre, descripción
  y assumptions normalizados. Assumptions vacío equivale a ausencia. Excluye UUID,
  tender, revisión, fechas, notes y lifecycle: éstos no cambian el contenido técnico.
  Una revisión sólo administrativa puede conservar fingerprint. No sustituye al
  número de revisión ni certifica cumplimiento.
- El servicio bloquea la identidad con FOR UPDATE, resuelve current en servidor y
  exige expected_current_revision entero positivo. Expectativa obsoleta falla sin
  append; el bloqueo dura hasta terminar la transacción del caller. UNIQUE protege
  también frente a escritores que omitan el servicio. No se asigna HTTP 409 aquí.
- FK compuesta (alternative_id, tender_id) exige aislamiento incluso en SQL directo.
  RESTRICT conserva historia frente a borrados de identidad/tender. Triggers
  PostgreSQL prohíben UPDATE/DELETE de identidad y revisiones, siguiendo ADR-0007.
- Servicio sin commit: creación de identidad/revisión inicial y cada append usan
  savepoints para atomicidad. begin_nested puede hacer flush de trabajo previo
  del caller según SQLAlchemy; lecturas nunca hacen flush ni escrituras.
  No hay operación de borrado. Downgrade administrativo elimina las tablas nuevas.

## Consecuencias y límites

Scope regeneration, Source Effects y Human Scope Review no modifican alternativas.
Evaluaciones futuras deberán identificar revisión y fingerprint, y evaluar Scope
aceptado vigente independientemente. ARCHIVED significa preservada, no propuesta
actualmente. Restaurar estrategia requiere otra revisión explícita humana.
Sin API, frontend, motor de Compliance, modelos IA ni costos/precios.
