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
- MVP-04.2 (Requirement Extraction): CLOSED
- MVP-04.3 (Requirement Normalization & Taxonomy): CLOSED
- MVP-04.4 (Mandatory, Conditional & Expected Evidence): CLOSED
- MVP-04.5 (Requirement Versioning & Effective Source): CLOSED
- MVP-04.6 (Human Review + Requirement Matrix): CLOSED
- MVP-04.7 (Golden Tender Integrated Acceptance): CLOSED

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

### Estado actual

- MVP-05.1 (Company Evidence Library): CLOSED
- MVP-05.2 (Company Evidence Intelligence): CLOSED
- MVP-05.3 (Requirement ↔ Evidence Candidate Matching): CLOSED
- MVP-05.4 (Deterministic Compliance Evaluation): CLOSED
- MVP-05.5 (Human Compliance Review): CLOSED
- MVP-05.6 (Compliance Matrix & Missing Evidence Audit): CLOSED
- MVP-05.7 (Golden Company + Golden Tender Integrated Acceptance): CLOSED

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

### Estado actual

- MVP-06 (Tender Items & Technical Scope): CURRENT
- MVP-06.1 (Tender Item Detection & Extraction): CLOSED
- MVP-06.2 (Item ↔ Distributed Scope Linking): CLOSED
- MVP-06.3: CLOSED
- MVP-06.4: CLOSED
- MVP-06.5 (Effective Source / Versioning): CLOSED
  - MVP-06.5.1 (Source Effect Contract + Persistence): CLOSED
  - MVP-06.5.2 (Deterministic Cross-Document Effect Discovery): CLOSED
  - MVP-06.5.3 (Semantic Effect Discovery Contract): CLOSED
  - MVP-06.5.4 (Effective Source Resolution Engine): CLOSED
  - MVP-06.5.5 (Golden / Conflict / Versioning Validation): CLOSED
    - MVP-06.5.5a (Human Source Effect Golden): CLOSED
    - MVP-06.5.5b (Real Semantic Calibration): CLOSED
    - MVP-06.5.5c (Conflict / Versioning Golden Validation): CLOSED
- MVP-06.6 (Human Scope Review + Alternatives / Compliance per Alternative): CLOSED
  - MVP-06.6.1 (Human Scope Review Contract + Persistence): CLOSED — commit `426c856`
  - MVP-06.6.2 (Human Scope Review API + Deterministic Recalculation): CLOSED — commit `4899ee6`
  - MVP-06.6.3 (Human Scope Review UI): CLOSED — commit `48707d8`
  - MVP-06.6.4 (Alternatives + Compliance per Alternative): CLOSED — UI aceptada en commit `a56cba4`
- MVP-06.R (Document Intelligence Convergence): CLOSED — gate condicional aceptado para preparar preflight, sin certificar producción ni autorizar Tender #002.
  - MVP-06.R.1 (Document Intelligence Convergence Contract + Routing): CLOSED — commit `fcc6564`.
  - MVP-06.R.2 (Transversal Document Intelligence Integration): CLOSED — commit `6d97859`; integración productiva Native/OCR/Vision aceptada.
    - MVP-06.R.2a (Requirement Perception Provenance Persistence): CLOSED — commit `5166ad8`; contrato tipado/versionado y migración 072 aceptados.
  - MVP-06.R.3 (Critical Identifier + Conflict / Review Hardening): CLOSED — commit `d399b7a`; propagación fail-closed aceptada.
    - MVP-06.R.3a (Cross-Capability Critical Identifier Provenance Contract): CLOSED — commit `857bbdc`; contrato v2 aceptado, compatible con v1 en el JSONB existente.
  - MVP-06.R.4a (Tender #001 Real Document Intelligence Convergence Calibration): CLOSED — Phase 4 aceptada en commit `530621a`; Golden estructural B-4 aprobado humanamente y replay offline con errores estructurales confiados sin revisión de 2 a 0. No certifica readiness productivo ni cobertura real completa. Detalle OCR no soportado por adapters predeterminados; Vision/Ollama/Qwen requieren autorización separada.
    - Phase 1 (Calibration Harness): CLOSED — commit `dc8f825`.
    - Phase 2 (Harness Fidelity + Offline Replay): CLOSED — commit `dc8f825`.
    - Phase 3A (B-4 Human Structural Golden Candidate): CLOSED — páginas 1–4, PDF y hashes de página aprobados humanamente sin correcciones; ITEM_1/ITEM_2 sólo como identidades Golden de comparación.
    - Phase 3B (Structural Golden Freeze + Offline Rescore): CLOSED — commit `3f2e29b`; Golden v1 congelado; P1 CORRECT, P2 PARTIAL, P3 INCORRECT; sin observación Vision P4. Rescore/replay sin proveedores ni cambios productivos.
    - Phase 4 (Structural Trust Propagation Hardening): CLOSED — commit `530621a`; P1 CORRECT, P2/P3 REVIEW_REQUIRED_CORRECT; cero unsafe trusted structural errors y cero proveedores en replay offline. Sin migración; Golden sólo para evaluación.
  - MVP-06.R.4b (Convergence Readiness Gate): CLOSED — commit documental `1745c70`; CONDITIONAL_GO_FOR_06V aceptado para V.0. S01–S12 PASS; no certifica producción ni autoriza acceso ciego.
- MVP-06.V (Cross-Tender Integration Validation): **CLOSED — 2026-10-21**, aceptación arquitectónica de Attempt #9, **OPTION B — LIMITED UAT**. Motor HEAD `14097f428e2185152aae1b671485244f1656fb07`; [cierre e identidad canónicos](mvp-06v-closure.md).
  - MVP-06.V.0 (Blind Validation Preflight + Freeze): CLOSED — commit `3c989fa`; plan AVAILABLE_ONLY sin inferencias autorizadas.
  - MVP-06.V.1 (Freeze + Blind Import): CLOSED — importación canónica en DB aislada 072; originales y manifest congelados.
  - MVP-06.V.2 ATTEMPT_1: FROZEN / EXECUTION_BLOCKED — `BLIND_RUN_EXECUTION_BLOCKER`; run `06v_6f6c60e697534a04abc3f922e698fef1`, SHA-256 `af9eeb1c94b79417033d6e533f4ca837ea94984a6085254392d39ff041fe5ead`. Evidencia histórica permanente; no representa ejecución exitosa de Effective Source.
  - MVP-06.V.3 (Freeze Verification + First-Pass Operational Review): CLOSED — integridad/blindness preservadas; defecto genérico en driver de preparación, guard PDF correcto.
  - MVP-06.V.3a (Capability-Aware Document Preparation Recovery): registro histórico anterior a la validación final; su estado CURRENT quedó superado por el cierre de V. No representa trabajo actual autorizado.
  - Attempts #1–#8: historia preservada; no reparar/reutilizar identidades. Los gates intermedios históricos no son una autorización vigente para otro intento.
  - Adjudicación final de Attempt #9 `06v9_4bb38af849cf4b3683bcc9db455f8349`: ACCEPTED. Dos partidas B-1 con Scope/Quantity/manifests correctos; límites Requirements/Evidence/Attributes/scans explícitos. No certificación autónoma ni productiva general.
- **Fase actual: RELEASE CANDIDATE / UAT HARDENING** — [readiness y gates P0](release-candidate-limited-uat-readiness.md), [capacidades UAT](uat-capability-statement.md). Primer usuario externo pendiente de hardening operacional; no reabrir Document Intelligence ni crear Attempt #10. No RC/tag creado.
  - RC-H1 (Local Reproducible Deployment): ACCEPTED, commit `65b3465c35877408aafe15757d3e74aaddf10e36`; [instalación](local-deployment.md). Sin push. No reabre semántica de Document Intelligence.
  - RC-H2 (Functional Workspace Integration): ACCEPTED, commit `415669f3a42850971ef57bae031ce19a622340b4`; composición normal Native/evidencia disponible, Scope con Quantity por padre, requisitos/evidencia y revisión Scope existentes. [Decisión y límites](adr/0020-workspace-canonical-composition.md), [flujo UAT](workspace-functional-flow.md). Sin migración ni rediseño final. Quantity independiente queda de solo lectura; revisión/edición auditada permanece DEFERRED P1 tras evaluación RC-H3, requiere contrato/migración y aprobación arquitectónica.
  - RC-H3 (Operational Recovery and Data Safety): implementado para revisión arquitectónica; backup DB+filesystem offline, verify/restore con staging y rollback, recuperación tras interrupción y retry normal con identidad vigente. [Contrato y límites](adr/0021-local-backup-restore-safe-retry.md), [operación](local-deployment.md#rc-h3--backup-restore-y-retry-local). Sin migración ni cambios semánticos; sin stage/commit/push RC-H3.

Tender #002 fue expuesto sólo en las fases de validación/adjudicación autorizadas y ahora es referencia histórica; no es una muestra ciega nueva. No usar para tuning, fixtures, Golden o nuevas ejecuciones sin autorización explícita; preservar todos los artefactos.

Nota de política MVP-06.5.5b:
La calibración semántica de Source Effects queda cerrada como NO-GO para uso automático en MVP. El camino autoritativo permanece determinista con revisión humana: efectos ambiguos deben escalar a `REVIEW_REQUIRED`, la validación estricta permanece fail-closed y ningún candidato semántico puede pasar a confiable automáticamente. El proveedor bounded se conserva sólo como infraestructura experimental y reutilizable. Motivos: `qwen3:8b` mantuvo `0/3` positivos correctamente emparejados tras iteraciones calibradas y fully bounded; `qwen3:14b` resultó operacionalmente inviable en el hardware local objetivo.

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

### Secuencia

Permanece después del cierre de MVP-06, incluyendo MVP-06.R y MVP-06.V.

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
