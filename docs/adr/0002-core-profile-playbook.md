# ADR-0002 — Separar Core, Institution Profile y Domain Playbook

**Estado:** Accepted  
**Fecha:** 2026-08-26

## Contexto

El MVP se construirá con expedientes PEMEX, pero el objetivo futuro es poder soportar otras instituciones sin reescribir el núcleo.

Las nomenclaturas institucionales (`DT-4`, `D-3`, `Anexo C`) no son conceptos universales.

## Decisión

Separar:

- `LicitIA Core`: dominio genérico;
- `Institution Profile`: vocabulario, patrones y reglas institucionales;
- `Domain Playbook`: conocimiento técnico por especialidad;
- `Tender Instance`: procedimiento real.

## Consecuencias

El Core modelará conceptos como `ExperienceRequirement`, `TenderItemCatalog` o `EvaluationCriterion`, no nombres específicos de PEMEX.

## Criterio de validación

Añadir en el futuro un perfil CFE no debe requerir modificar las entidades centrales salvo una necesidad de dominio verdaderamente general.
