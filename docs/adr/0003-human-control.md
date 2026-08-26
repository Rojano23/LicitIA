# ADR-0003 — Human-in-the-loop para decisiones técnicas y comerciales

**Estado:** Accepted  
**Fecha:** 2026-08-26

## Contexto

Cada empresa puede adoptar estrategias técnicas y comerciales diferentes. Una misma licitación puede admitir decisiones de riesgo, alternativas técnicas y estructuras de precio distintas.

## Decisión

La IA y las reglas no tendrán autoridad final sobre:

- estrategia técnica;
- proveedor;
- marca/modelo;
- aceptación de evidencia ambigua;
- costo asumido;
- margen;
- markup;
- precio ofertado;
- decisión BID/NO BID.

El usuario podrá realizar overrides y dichos cambios serán auditados.

## Consecuencias

La UI debe distinguir:

- evaluación AI;
- evaluación RULE;
- decisión HUMAN.

Una advertencia puede coexistir con una decisión humana distinta.
