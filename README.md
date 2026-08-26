# LicitIA

**Estado:** Pre-MVP / MVP-00  
**Versión de definición:** v0.1  
**Perfil institucional inicial:** PEMEX / SNR — Concursos Abiertos  
**Arquitectura de producto:** On-Premise / Local-first

LicitIA es un software local de inteligencia para procesos licitatorios. Su propósito es reconstruir el modelo vigente de una licitación a partir de sus bases, anexos, formatos y actos posteriores; transformar criterios de evaluación en requisitos verificables; relacionarlos con evidencia; estructurar partidas y alcance; apoyar el costeo; y mantener al usuario en control de la estrategia técnica y comercial.

## Principio rector

> LicitIA no gana licitaciones por el usuario. Le da al usuario una comprensión más rápida, completa, trazable y controlable del proceso para que pueda tomar mejores decisiones técnicas, documentales y comerciales.

## Alcance actual

El MVP soportará inicialmente **Concursos Abiertos PEMEX / SNR** mediante:

- `LicitIA Core`
- `PEMEX Profile v1`
- `Industrial Automation / DCS Maintenance Playbook v1`
- `Golden Tender #001`: `SNR-CAD-265-CA-S-2026`

La arquitectura deberá permitir incorporar perfiles de otras instituciones sin reescribir el Core.

## Documentación operativa

- [`docs/vision.md`](docs/vision.md) — visión, alcance, usuarios y principios del producto.
- [`docs/architecture.md`](docs/architecture.md) — arquitectura funcional y tecnológica.
- [`docs/domain-model.md`](docs/domain-model.md) — entidades, relaciones, estados e invariantes del dominio.
- [`docs/roadmap.md`](docs/roadmap.md) — plan MVP-00 a MVP-09 con criterios de salida.
- [`docs/golden-tender-001.md`](docs/golden-tender-001.md) — expediente de referencia y estrategia de validación.
- [`AGENTS.md`](AGENTS.md) — reglas obligatorias para agentes de desarrollo.
- [`docs/adr/`](docs/adr/) — decisiones arquitectónicas registradas.

## Estado del desarrollo

No iniciar implementación funcional antes de completar MVP-00:

1. validar modelo de dominio;
2. validar arquitectura;
3. congelar contratos de entidades principales;
4. establecer pruebas base del Golden Tender;
5. configurar repositorio, calidad y CI local.

## Stack propuesto

**Desktop:** Tauri 2 + React + TypeScript + Vite  
**Backend local:** Python + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic  
**Datos:** PostgreSQL + pgvector + filesystem local  
**Document Intelligence:** PyMuPDF + extracción estructurada + OCR local cuando aplique  
**IA local:** Ollama mediante una capa de abstracción  
**Jobs:** ejecución local/worker sencillo; no introducir Redis sin necesidad demostrada.
