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

### Estado actual

- MVP-02.1 (PDF extraction): CLOSED
- MVP-02.2 (OCR acquisition): CLOSED
- MVP-02.3 (NormalizedContent + chunking): CLOSED
- MVP-02.4 (Document Classification): CLOSED
- MVP-02.5 (References + Relationships): CLOSED
- MVP-02.6 (Golden Tender Integrated Acceptance): CLOSED

### Objetivo

Convertir archivos en contenido estructurado por página/sección.

### Funciones

- extracción de texto PDF;
- OCR fallback;
- page model;
- detección básica de tablas;
- DOCX/XLSX seleccionados;
- clasificación documental inicial;
- estado/calidad de extracción;
- adquisición dual-provider para páginas OCR-dependientes.

### Política MVP-02.2

La adquisición automática de OCR no fusiona ni prioriza resultados por defecto. Para páginas `TEXT_ONLY` sin regiones visuales elegibles, se usa la extracción nativa y no se dispara OCR automático. Para páginas `IMAGE_ONLY` o `MIXED_CONTENT`, `AUTO` ejecuta Tesseract y PaddleOCR por separado sobre cada región elegible o sobre la página completa cuando corresponde, conservando cada resultado con su provenance original.

Esto no significa que los textos OCR queden automáticamente “confiables” ni que deban combinarse. La reconciliación de resultados entre proveedores pertenece a una fase posterior de normalización y evidencia, no a MVP-02.2.

### Métricas

- páginas procesadas;
- páginas OCR;
- páginas fallidas;
- cobertura de texto utilizable.

### Criterio de salida

El sistema puede explicar qué tipo de documento es cada archivo del Golden Tender y mostrar la fuente de esa clasificación.

---

## MVP-02.4 — Evidence-Based Document Classification

### Objetivo

Clasificar documentos físicos del expediente con un flujo determinista, explicable y revisable, sin depender de LLM ni de reglas PEMEX.

### Funciones

- taxonomía Core genérica para documento físico;
- reglas deterministas sobre nombre y contenido normalizado;
- persistencia de sugerencia, evidencia y funcional tags;
- clasificación compuesta para paquetes documentales;
- deduplicación de señales por origen físico (página / región / OCR provider);
- override y confirmación humana;
- status UNKNOWN / NEEDS_REVIEW / CONFIRMED / OVERRIDDEN.

### Fuera de alcance

- extracción de requisitos;
- evaluación de cumplimiento;
- referencias entre documentos;
- secciones lógicas dentro de un PDF;
- embeddings, pgvector, semántica LLM;
- OCR fusion ni reconcilación de proveedores.

### Criterio de salida

El usuario puede clasificar un documento a partir de evidencia de archivo y contenido normalizado, ver la evidencia, confirmar o revisar la decisión y dejar constancia de un override humano sin que el motor lo reescriba silenciosamente.

---

## MVP-03 — Tender Understanding

### Estado actual

- MVP-03.1 (Relationship Baseline Consolidation): CLOSED
- MVP-03.2 (Tender Events & Timeline): CLOSED
- MVP-03.3 (Clarifications & Modifications): CLOSED
- MVP-03.4 (Effective Tender State): CLOSED
- MVP-03.5 (Document Map + Tender State Snapshot): CLOSED
- MVP-03.6 (Golden Tender Integrated Acceptance): CLOSED
- MVP-03 (Tender Understanding): CLOSED

Nota de cierre MVP-03:
MVP-03 closed with Golden Tender in PARTIALLY_UNDERSTOOD state because Tender Understanding is structurally coherent while the real corpus still contains intentionally visible processing gaps, unresolved/ambiguous references and human-review pending items. This does not block MVP-03 closure because incomplete evidence is explicitly represented rather than silently treated as understood.

Requirement extraction begins in MVP-04.

Nota de consolidación MVP-03.1:
Document references, physical document relationships and corpus integrity were implemented ahead of schedule in MVP-02.5/MVP-02.6 because Golden Tender acceptance required them. MVP-03 reuses and consolidates these capabilities rather than duplicating them.

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

### Estado actual

- MVP-03 (Tender Understanding): CLOSED
- MVP-04.1 (Evaluation Model Detection): CLOSED
- MVP-04.2 (Requirement Extraction): IN IMPLEMENTATION

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
