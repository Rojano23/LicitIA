# ADR-0001 — Local-first / On-Premise

**Estado:** Accepted  
**Fecha:** 2026-08-26

## Contexto

LicitIA procesa documentos potencialmente confidenciales: propuestas, cotizaciones, contratos, información legal, estados financieros, certificados y estrategia de precios.

## Decisión

El producto será On-Premise y Local-first por defecto.

Documentos, base de datos, OCR, embeddings y LLM se ejecutarán localmente en la configuración estándar.

## Consecuencias

### Positivas

- menor barrera de confianza;
- control de datos por el cliente;
- posibilidad de uso sin conexión;
- diferenciación comercial.

### Negativas

- instalación más compleja;
- restricciones de hardware;
- soporte de modelos locales;
- actualizaciones requieren estrategia de distribución.

## No decisión

Se permitirá estudiar en el futuro un modo híbrido opcional con consentimiento explícito.
