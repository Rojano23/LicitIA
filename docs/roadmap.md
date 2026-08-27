# LicitIA — Roadmap v0.1

## Filosofía del roadmap

Cada MVP debe cerrar una capacidad verificable. No avanzar por “porcentaje de código” sino por resultados observables sobre expedientes reales.

Golden Tender #001 será prueba de regresión funcional desde MVP-02.

---

## MVP-00 — Constitución del proyecto

### Objetivo

Crear la base documental, técnica y de calidad antes de implementar funcionalidades.

### Entregables

- Documento Maestro v0.1
- `README.md`
- `docs/vision.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/roadmap.md`
- `docs/golden-tender-001.md`
- `AGENTS.md`
- ADR iniciales
- estructura de repositorio
- linters/formatters/tests base

### Criterio de salida

Un agente nuevo puede leer el repositorio y explicar correctamente:

- qué es LicitIA;
- qué no debe hacer;
- cómo se separan Core/Profile/Playbook;
- quién decide precio y estrategia técnica;
- qué es Golden Tender #001.

---

## MVP-01 — Tender Workspace

### Estado

Completado y validado humanamente.

### Objetivo

Crear y administrar un expediente local sin IA, con trazabilidad completa del ciclo de tender y documentos.

### Funciones implementadas

- crear licitación;
- persistencia en PostgreSQL;
- selección explícita de licitación por UUID;
- importación múltiple de documentos reales;
- almacenamiento local inmutable de originales;
- hash SHA-256 para integridad;
- metadatos persistentes del documento;
- detección de duplicados;
- detección de conflicto por nombre con contenido distinto;
- resolución humana explícita del conflicto;
- importación independiente del mismo nombre;
- manejo de revisiones con número de versión;
- estado vigente y sustituido por revisión;
- conservación del origen de la decisión humana de conflicto;
- registro persistente del expediente y sus documentos;
- visor PDF local seguro;
- visualización inline sin descarga automática;
- revisiones actuales y sustituidas visualizables de forma independiente;
- persistencia al reiniciar;
- protección contra path traversal;
- operación local-first sin dependencia de servicios externos.

### Criterio de salida

Golden Tender #001 puede cargarse, navegarse, verificarse y revisarse sin alterar originales ni perder trazabilidad del expediente.

---

## MVP-02 — Document Intelligence

### Objetivo

Convertir archivos en contenido estructurado por página/sección.

### Funciones

- extracción de texto PDF;
- OCR fallback;
- page model;
- detección básica de tablas;
- DOCX/XLSX seleccionados;
- clasificación documental inicial;
- estado/calidad de extracción.

### Métricas

- páginas procesadas;
- páginas OCR;
- páginas fallidas;
- cobertura de texto utilizable.

### Criterio de salida

El sistema puede explicar qué tipo de documento es cada archivo del Golden Tender y mostrar la fuente de esa clasificación.

---

## MVP-03 — Tender Understanding

### Objetivo

Reconstruir relaciones y estado del expediente.

### Funciones

- referencias entre documentos;
- detección de documentos mencionados no cargados;
- eventos;
- versiones;
- aclaraciones/modificaciones;
- mapa documental;
- Tender State Snapshot;
- indicador de integridad.

### Criterio de salida

El usuario puede ver qué documentos definen, complementan o modifican otros y qué pendientes impiden declarar completa la comprensión.

---

## MVP-04 — Evaluation & Requirements

### Objetivo

Transformar criterios del procedimiento en requisitos verificables.

### Funciones

- detectar modelo de evaluación;
- extraer EvaluationCriteria;
- compilar Requirements;
- SourceLocator obligatorio;
- mandatory/conditional;
- versiones de requisito;
- revisión humana;
- matriz comercial/técnica/económica.

### Criterio de salida

Los requisitos principales del Golden Tender pueden rastrearse a documento, página y fragmento, sin depender de nombres de archivo hardcodeados.

---

## MVP-05 — Evidence & Compliance

### Objetivo

Comparar requisitos contra evidencia empresarial.

### Funciones

- biblioteca empresarial;
- documentos legales;
- certificados;
- personal;
- experiencia;
- evidencia candidata;
- asociación automática probable;
- reglas deterministas;
- revisión humana;
- estados de cumplimiento.

### Criterio de salida

Para un conjunto de evidencias de prueba, LicitIA distingue correctamente entre cumple, probable, insuficiente, faltante y revisión requerida.

---

## MVP-06 — Tender Items & Technical Scope

### Objetivo

Entender qué se está cotizando realmente.

### Funciones

- detectar catálogo de partidas/conceptos;
- extraer item/description/unit/quantity;
- vincular alcance distribuido en anexos;
- materiales/equipos/herramientas/SSPA;
- alternativas técnicas;
- cumplimiento por alternativa.

### Criterio de salida

Cada partida del Golden Tender muestra su alcance consolidado y sus fuentes documentales.

---

## MVP-07 — Costing & Pricing

### Objetivo

Dar control comercial completo sin rigidizar la estrategia del usuario.

### Funciones

- proveedores;
- carga de cotizaciones;
- extracción de líneas;
- matching cotización ↔ partida;
- costos confirmados/históricos/estimados/manuales;
- componentes de costo;
- escenarios;
- edición manual total;
- margen y markup;
- utilidad por partida;
- utilidad global;
- alertas de pérdida y falta de respaldo.

### Regla crítica

Ningún precio de venta es inmutable ni obligatorio.

### Criterio de salida

El usuario puede cambiar cualquier costo o precio y observar de inmediato el efecto por partida y general sin perder origen ni auditoría.

---

## MVP-08 — Bid Readiness

### Objetivo

Consolidar estado de preparación para decisión humana.

### Funciones

- integridad del análisis;
- requisitos críticos;
- cumplimiento comercial;
- cumplimiento técnico;
- cobertura de partidas;
- documentos faltantes;
- cotizaciones faltantes;
- costos no confirmados;
- margen actual;
- ambigüedades;
- riesgos.

### Criterio de salida

El dashboard permite decidir dónde invertir tiempo antes del cierre sin emitir una decisión autónoma BID/NO BID.

---

## MVP-09 — Proposal Builder

### Objetivo

Preparar artefactos de salida para revisión y presentación humana.

### Funciones

- matrices exportables;
- propuesta económica;
- lista de documentos;
- expediente organizado;
- reportes de cumplimiento;
- exportaciones XLSX/PDF donde aplique;
- validaciones finales.

### Fuera de alcance

- envío automático;
- firma automática;
- presentación automática en plataforma institucional.

### Criterio de salida

El usuario puede generar un paquete de revisión final que conserva correspondencia con la información aprobada dentro de LicitIA.

---

## Gates transversales

No cerrar un MVP si falla alguno:

### Seguridad

- originales intactos;
- no envío externo involuntario;
- auditoría de overrides críticos.

### Calidad

- pruebas unitarias para Engines nuevos;
- migraciones reproducibles;
- errores controlados;
- no datos silenciosamente descartados.

### Dominio

- no hardcode institucional dentro de Core;
- no decisiones técnicas/comerciales irreversibles por IA;
- trazabilidad de requisitos.

### Performance

Registrar métricas de tiempo y memoria sobre Golden Tender. Optimizar sólo con evidencia.
