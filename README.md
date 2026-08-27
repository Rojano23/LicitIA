# LicitIA

**Estado:** MVP-01 — Tender Workspace completado  
**Versión de definición:** v0.1  
**Perfil institucional inicial:** PEMEX / SNR — Concursos Abiertos  
**Arquitectura de producto:** On-Premise / Local-first

LicitIA es un software local de inteligencia para procesos licitatorios. La primera fase completada del producto centra su valor en administrar de forma local, trazable y segura el expediente de una licitación: tender, documentos, metadatos, conflictos humanos, revisiones y vista local de PDFs. Este primer alcance no sustituye la comprensión documental ni la evaluación técnica/comercial; esas capacidades siguen siendo objetivos de MVP posteriores.

## Principio rector

> LicitIA no gana licitaciones por el usuario. Le da al usuario una comprensión más rápida, completa, trazable y controlable del proceso para que pueda tomar mejores decisiones técnicas, documentales y comerciales.

## Alcance actual

El MVP-01 soporta de forma verificable **Concursos Abiertos PEMEX / SNR** mediante:

- `LicitIA Core`
- `PEMEX Profile v1`
- `Industrial Automation / DCS Maintenance Playbook v1`
- `Golden Tender #001`: `SNR-CAD-265-CA-S-2026`

La arquitectura sigue permitiendo incorporar perfiles de otras instituciones sin reescribir el Core.

## MVP-01 — Tender Workspace completado

La implementación validada de MVP-01 incluye:

- creación de licitaciones y persistencia en PostgreSQL;
- selección explícita de licitación por UUID;
- importación múltiple de documentos reales;
- almacenamiento local inmutable de originales;
- metadatos SHA-256 de integridad;
- detección de duplicados;
- detección de conflicto por mismo nombre y contenido distinto;
- resolución humana explícita del conflicto;
- resolución como documento independiente;
- control de revisiones del documento;
- estado vigente / sustituido por revisión;
- trazabilidad de la decisión humana de conflicto;
- registro persistente de documentos;
- vista local segura de PDF;
- visualización inline sin descarga automática;
- revisión vigente y sustituida permanece visualizable independientemente;
- persistencia al reiniciar la aplicación;
- protección contra path traversal;
- operación local-first sin dependencia en servicios externos.

## Documentación operativa

- [`docs/vision.md`](docs/vision.md) — visión, alcance, usuarios y principios del producto.
- [`docs/architecture.md`](docs/architecture.md) — arquitectura funcional y tecnológica.
- [`docs/domain-model.md`](docs/domain-model.md) — entidades, relaciones, estados e invariantes del dominio.
- [`docs/roadmap.md`](docs/roadmap.md) — plan del proyecto y estado actual de los MVP.
- [`docs/golden-tender-001.md`](docs/golden-tender-001.md) — expediente de referencia y estrategia de validación.
- [`AGENTS.md`](AGENTS.md) — reglas obligatorias para agentes de desarrollo.
- [`docs/adr/`](docs/adr/) — decisiones arquitectónicas registradas.

## Estado del desarrollo

MVP-01 queda cerrado como línea base estable y validada del Tender Workspace.

Las capacidades de comprensión documental, OCR, extracción estructurada, IA, embeddings, análisis de evidencia y evaluación técnica/comercial permanecen fuera del alcance de MVP-01 y corresponden a hitos posteriores del roadmap.

## Stack implementado

**Desktop:** React + TypeScript + Vite  
**Backend local:** Python + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic  
**Datos:** PostgreSQL + filesystem local  
**Documentos:** almacenamiento local inmutable, metadatos y SHA-256  
**Vista local:** PDF inline mediante endpoint local seguro  
**Operación:** local-first sin servicios externos para el flujo base del Tender Workspace.
