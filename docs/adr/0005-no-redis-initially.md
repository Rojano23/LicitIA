# ADR-0005 — No introducir Redis en el MVP inicial

**Estado:** Accepted  
**Fecha:** 2026-08-26

## Contexto

El procesamiento de documentos puede requerir jobs de larga duración, pero el MVP es una aplicación local y no existe todavía evidencia de necesidad de una cola distribuida.

## Decisión

Comenzar con job runner/worker local y persistir estado de jobs en PostgreSQL.

No introducir Redis hasta demostrar una necesidad operativa medible.

## Señales que justificarían reconsideración

- múltiples workers concurrentes reales;
- bloqueo sistemático del proceso local;
- necesidad de retry/queue semantics que la solución simple no soporte;
- distribución entre procesos/máquinas;
- benchmark que demuestre beneficio.

## Consecuencia

Menor complejidad, menor consumo local y menos riesgo de infraestructura innecesaria.
