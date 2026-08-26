# ADR-0004 — PostgreSQL + pgvector como persistencia inicial

**Estado:** Accepted  
**Fecha:** 2026-08-26

## Contexto

LicitIA necesita almacenar datos transaccionales, relaciones documentales, auditoría, requisitos, costos y búsqueda semántica local.

## Decisión

Usar PostgreSQL como base de datos principal y pgvector para embeddings en el MVP.

Los documentos originales permanecerán en filesystem local y PostgreSQL almacenará metadata, referencias y hashes.

## Consecuencias

- una sola plataforma de datos inicial;
- evita introducir una vector DB separada prematuramente;
- simplifica respaldos y consistencia;
- requiere empaquetar/administrar PostgreSQL en una instalación local.
