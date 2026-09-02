# ADR-0006 — Fallback local de vision con Ollama para scope ambiguo

**Estado:** Accepted  
**Fecha:** 2026-08-31

## Contexto

Hay documentos escaneados o con tablas densas en los que la extracción determinista puede quedarse corta para reconstruir partidas o alcance tecnico con suficiente confianza.

LicitIA sigue siendo local-first; no debe enviar documentos a servicios externos.

## Decisión

Agregar un proveedor de vision local desacoplado del dominio, respaldado por Ollama cuando este disponible localmente.

La vision local solo actua como propuesta transitoria y acotada.

No persiste nuevas partidas canonicas ni reemplaza la decision humana.

## Alcance

- modo `OFF`, `AUTO` y `FORCE` para la analitica local;
- validacion estructurada de JSON devuelto por el modelo;
- uso solo en documentos ambiguos o manualmente forzados;
- UI y API muestran la propuesta como apoyo de revision.

## Consecuencias

- mantiene la extraccion determinista como ruta principal;
- conserva trazabilidad y revision humana;
- evita dependencia de nube o de una nueva infraestructura;
- permite desactivar el fallback sin afectar MVP-06.1.