# LicitIA — Vision v0.1

## 1. Propósito

LicitIA es una aplicación de escritorio On-Premise y Local-first para apoyar a empresas y profesionales que participan en procesos licitatorios complejos. El sistema debe reducir el tiempo dedicado a localizar información, cruzar anexos, interpretar criterios de evaluación, detectar omisiones, asociar evidencias, preparar matrices de cumplimiento y estructurar costos.

LicitIA **no sustituye** al responsable técnico, comercial, legal o administrativo. La IA y los Engines deben asistir; las decisiones relevantes permanecen en manos del usuario.

## 2. Problema central

Una licitación no es un PDF aislado. Es un expediente con múltiples documentos, referencias cruzadas, versiones, eventos, anexos, formatos, criterios de evaluación, partidas, condiciones técnicas y obligaciones documentales.

El problema que LicitIA resuelve es:

> convertir un expediente fragmentado en un modelo vigente, trazable y accionable del procedimiento.

## 3. Preguntas que la aplicación debe responder

LicitIA debe permitir que el usuario responda con rapidez y evidencia a cinco preguntas:

1. **¿Qué me están solicitando?**
2. **¿Qué documentos necesito?**
3. **¿Cumplo técnica y documentalmente?**
4. **¿Cuánto me cuesta y cuánto quiero ofertar?**
5. **¿Qué me falta antes de presentar?**

## 4. Usuario objetivo inicial

Profesionales o empresas que participan en Concursos Abiertos PEMEX / SNR y que necesitan coordinar información:

- técnica;
- comercial/legal;
- económica;
- debida diligencia;
- seguridad/SSPA;
- proveedores y cotizaciones;
- evidencia corporativa.

## 5. Propuesta de valor

LicitIA deberá reducir:

- tiempo de lectura y clasificación documental;
- tiempo para localizar requisitos y criterios;
- omisiones documentales;
- errores de trazabilidad;
- tiempo para generar matrices de cumplimiento;
- tiempo para relacionar anexos con partidas;
- tiempo para consolidar costos y cotizaciones;
- retrabajo entre licitaciones;
- pérdida de conocimiento histórico.

## 6. Principios de producto

### 6.1 Humano en control

El usuario puede en todo momento:

- corregir clasificaciones;
- aprobar/rechazar interpretaciones;
- aceptar o rechazar evidencia;
- seleccionar alternativas técnicas;
- registrar desviaciones;
- elegir proveedor;
- modificar costos;
- modificar precios;
- cambiar margen o markup;
- aceptar conscientemente riesgos;
- decidir BID / NO BID;
- decidir qué propuesta emitir.

### 6.2 Flexibilidad comercial

La estrategia de precio pertenece al usuario. La herramienta calcula, compara, alerta y conserva historia, pero no bloquea una decisión comercial.

Fuentes económicas soportadas:

- `CONFIRMED_QUOTE`
- `HISTORICAL_COST`
- `SYSTEM_ESTIMATE`
- `MANUAL_INPUT`

El usuario puede reemplazar cualquier referencia por un valor manual.

### 6.3 Flexibilidad técnica

La herramienta puede recomendar o advertir, pero debe permitir mantener alternativas técnicas aunque presenten riesgo, siempre que el estado quede visible y trazable.

### 6.4 Evidencia antes que opinión

Toda conclusión debe poder responder:

- ¿qué requisito?
- ¿qué fuente lo define?
- ¿qué evidencia lo soporta?
- ¿qué Engine produjo la evaluación?
- ¿qué decidió el usuario?

### 6.5 No inventar

Nunca inventar:

- requisitos;
- referencias;
- evidencia;
- costos;
- precios;
- documentos faltantes que no estén efectivamente referenciados.

Cuando exista incertidumbre usar estados explícitos como `REVIEW_REQUIRED`, `UNKNOWN`, `NO_EVIDENCE` o `AMBIGUOUS`.

### 6.6 Local-first

Por defecto, documentos, base de datos, OCR, embeddings y modelo de IA permanecen en el equipo o infraestructura local del cliente.

## 7. Alcance MVP

### Incluye

- crear un workspace de licitación;
- ingesta masiva de documentos;
- registro/hash/versiones;
- visor documental;
- extracción de texto/tablas;
- OCR local cuando aplique;
- clasificación semántica;
- referencias cruzadas;
- eventos y versiones;
- identificación del modelo de evaluación;
- compilación de requisitos;
- matrices comercial, técnica y económica;
- biblioteca empresarial;
- evidencia y revisión humana;
- extracción de catálogo de partidas/conceptos;
- relación partida ↔ alcance;
- cotizaciones y costos;
- edición manual completa de precios;
- margen/markup/utilidad por partida y general;
- escenarios de precio;
- dashboard de Bid Readiness;
- exportaciones para revisión humana.

### No incluye

- envío automático a SISCEP;
- firma electrónica automática;
- presentación autónoma de propuesta;
- decisión autónoma BID/NO BID;
- precio final decidido por IA;
- selección técnica irreversible por IA;
- soporte formal de CFE u otras instituciones en v1;
- entrenamiento de un LLM propio.

## 8. Arquitectura de producto

LicitIA se organiza en cuatro capas:

1. **LicitIA Core** — conceptos universales del dominio.
2. **Institution Profile** — reglas y nomenclaturas de una institución.
3. **Domain Playbook** — conocimiento técnico de una especialidad.
4. **Tender Instance** — un procedimiento real y su expediente.

Para v1:

- `PEMEX Profile v1`
- `Industrial Automation / DCS Maintenance Playbook v1`
- `Golden Tender #001: SNR-CAD-265-CA-S-2026`

## 9. Métricas de éxito

El producto debe medirse por reducción de trabajo y riesgo, no por cantidad de documentos procesados.

Indicadores candidatos:

- tiempo desde importación hasta mapa documental;
- porcentaje de referencias resueltas;
- porcentaje de requisitos con trazabilidad completa;
- tiempo para producir matriz de cumplimiento;
- tiempo para identificar pendientes;
- tiempo para consolidar costeo;
- número de omisiones detectadas antes de propuesta;
- porcentaje de decisiones humanas con evidencia visible;
- reutilización de documentos empresariales entre procesos.

## 10. Criterio de producto terminado para MVP

El MVP será útil cuando pueda procesar el Golden Tender #001 de extremo a extremo, manteniendo trazabilidad y permitiendo que un usuario prepare su estrategia técnica y económica sin depender de lectura manual exhaustiva de todo el expediente.
