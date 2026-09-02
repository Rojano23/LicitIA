# LicitIA — Architecture v0.1

## 1. Objetivo arquitectónico

Construir una aplicación On-Premise, Local-first, modular y auditable capaz de procesar expedientes licitatorios grandes sin depender de servicios externos y sin acoplar el dominio a nomenclaturas específicas de PEMEX.

## 2. Principios arquitectónicos

1. **Core agnóstico a institución.**
2. **PEMEX como perfil, no como hardcode.**
3. **IA para semántica; reglas para determinismo.**
4. **Human-in-the-loop obligatorio para ambigüedad y decisiones estratégicas.**
5. **Originales inmutables.**
6. **Datos derivados versionables y regenerables.**
7. **Toda conclusión es trazable.**
8. **No microservicios prematuros.**
9. **No Redis/Kafka/Kubernetes sin necesidad medible.**
10. **Instalación final transparente para usuario no técnico.**

## 3. Arquitectura lógica

```text
EXPEDIENTE
   │
   ▼
Tender Ingestion Engine
   │
   ▼
Document Registry
   │
   ▼
Document Intelligence
   │
   ├── text extraction
   ├── page model
   ├── table extraction
   └── OCR fallback
   │
   ▼
Document Role Classifier
   │
   ▼
Procedure & Event Engine
   │
   ▼
Version / Tender State Engine
   │
   ▼
Tender Understanding Engine
   │
   ├── Reference Resolver
   ├── Applicability Engine
   ├── Evaluation Model Engine
   └── Requirement Compiler
   │
   ▼
Tender Model
   │
   ├── Evidence Engine
   ├── Technical Compliance Engine
   ├── Tender Item Engine
   ├── Commercial / Cost Engine
   └── Bid Readiness Engine
   │
   ▼
Human Review / Proposal Builder
```

## 4. Arquitectura de ejecución

```text
┌─────────────────────────────────────────────┐
│              LicitIA Desktop                │
│           Tauri + React + TS                │
└─────────────────────┬───────────────────────┘
                      │ localhost / IPC
┌─────────────────────▼───────────────────────┐
│              FastAPI Local API              │
│      Application + Domain Services          │
└──────────────┬───────────────┬──────────────┘
               │               │
               ▼               ▼
       PostgreSQL + pgvector   Local Filesystem
               │               │
               └───────┬───────┘
                       ▼
              Document / AI Services
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       PyMuPDF       OCR Local     Ollama
```

## 5. Stack inicial

### Desktop / UI

- Tauri 2
- React
- TypeScript estricto
- Vite

### Backend

- Python
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic

### Persistencia

- PostgreSQL
- pgvector
- filesystem local para originales y artefactos derivados

### Document Intelligence

- PyMuPDF para PDF y páginas
- extracción estructurada de texto
- detección/extracción de tablas
- OCR local sólo cuando el texto no sea utilizable
- `python-docx` para DOCX
- `openpyxl` para XLSX

### IA

- Ollama como proveedor local inicial
- interfaz de proveedor desacoplada del dominio
- embeddings locales
- fallback de vision local acotado para documentos ambiguos cuando la extraccion determinista no es suficiente

### Jobs

Inicio:

- job runner local / worker sencillo;
- persistencia de estado del job en PostgreSQL.

No añadir Redis en MVP salvo evidencia de:

- necesidad real de colas distribuidas;
- volumen concurrente que lo justifique;
- bloqueo/latencia que no pueda resolverse con arquitectura simple.

## 6. Límites de módulos

### `core`

Contiene entidades y contratos independientes de institución:

- Tender
- Document
- Requirement
- Evidence
- TenderItem
- EvaluationCriterion
- Cost / Price
- HumanDecision

### `profiles`

Conocimiento institucional:

```text
profiles/
  pemex/
    mappings/
    vocabularies/
    patterns/
    evaluation_rules/
```

No debe contener lógica de UI.

### `playbooks`

Conocimiento técnico por dominio:

```text
playbooks/
  industrial_automation/
    dcs_maintenance/
```

### `engines`

Servicios de análisis:

- ingestion
- document_intelligence
- classification
- reference_resolution
- applicability
- evaluation_model
- requirement_compiler
- evidence
- technical_compliance
- tender_items
- costing
- bid_readiness

### `application`

Orquestación de casos de uso y transacciones.

### `infrastructure`

DB, filesystem, Ollama, OCR, parsers y adaptadores.

## 7. Pipeline documental

Cada archivo pasa por estados:

```text
RECEIVED
→ REGISTERED
→ TEXT_EXTRACTED | OCR_REQUIRED
→ STRUCTURED
→ CLASSIFIED
→ REFERENCES_RESOLVED
→ ANALYZED
→ HUMAN_REVIEWED (cuando aplique)
```

Los originales nunca se modifican.

## 8. Modelo de fuente y trazabilidad

Todo objeto derivado que dependa de un documento debe incluir un `SourceLocator`:

```text
SourceLocator
  document_id
  document_version_id
  page
  section
  paragraph_or_block
  source_excerpt
  extraction_method
```

No aceptar un `Requirement`, `EvaluationCriterion` o `EvidenceAssessment` sin fuente, salvo objetos creados manualmente por el usuario, que deberán marcarse explícitamente como `MANUAL`.

## 9. IA y reglas

### IA permitida

- clasificación semántica;
- extracción estructurada;
- identificación de referencias;
- detección de relaciones;
- interpretación de lenguaje natural;
- matching probable;
- explicación de riesgos;
- borradores.

### Regla determinista preferida

- fechas;
- vencimientos;
- cantidades;
- aritmética;
- comparación numérica;
- rangos;
- margen/markup;
- igualdad de unidades normalizadas;
- reglas explícitamente parametrizadas.

### Salidas de IA

Toda inferencia debe incluir:

- valor estructurado;
- confianza;
- fuente(s);
- razonamiento resumido visible, no cadena de pensamiento privada;
- estado de revisión.

## 10. Human Review

Los Engines pueden producir:

- `CONFIRMED`
- `PROBABLE`
- `REVIEW_REQUIRED`
- `INSUFFICIENT`
- `MISSING`

La UI debe permitir:

- aprobar;
- rechazar;
- editar;
- agregar comentario;
- sustituir fuente;
- registrar decisión.

## 11. Arquitectura económica

Separar tres conceptos:

1. **Cost Source** — de dónde proviene el costo.
2. **Cost Model** — costo interno consolidado.
3. **Bid Price** — precio que el usuario decide ofertar.

Nunca inferir que `BidPrice = Cost + margen sugerido` de forma obligatoria.

Debe existir soporte de escenarios:

- BASE
- AGGRESSIVE
- TARGET
- CONSERVATIVE
- CUSTOM

Un escenario no altera otro.

## 12. Seguridad

Mínimos MVP:

- archivos originales locales;
- hash SHA-256 por archivo;
- rutas no expuestas en UI cuando no sea necesario;
- secretos mediante keychain/credential store del SO;
- auditoría de cambios relevantes;
- backups exportables;
- no telemetría documental sin consentimiento.

Futuro:

- cifrado en reposo;
- perfiles de usuario/roles locales;
- política corporativa de backup;
- modo híbrido opcional.

## 13. Observabilidad

La observabilidad debe ser acotada y operativa.

Registrar:

- duración de jobs;
- errores de parser/OCR;
- documentos fallidos;
- uso de modelo;
- tamaño de expediente;
- conteos de requisitos/referencias;
- errores de aplicación.

No almacenar indefinidamente trazas masivas. Definir retención desde MVP-00.

## 14. Pruebas

### Unitarias

Cada Engine.

### Contratos

Schemas Pydantic y persistencia.

### Integración

- DB;
- filesystem;
- parsers;
- Ollama adapter.

### Golden Tender regression

Golden Tender #001 deberá tener expectativas versionadas. No se codificarán excepciones específicas para hacerlo pasar.

## 15. Estructura inicial sugerida del repositorio

```text
licitia/
├── AGENTS.md
├── README.md
├── docs/
│   ├── vision.md
│   ├── architecture.md
│   ├── domain-model.md
│   ├── roadmap.md
│   ├── golden-tender-001.md
│   └── adr/
├── apps/
│   └── desktop/
├── backend/
│   └── licitia/
│       ├── core/
│       ├── application/
│       ├── engines/
│       ├── profiles/
│       ├── playbooks/
│       └── infrastructure/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden_tender/
└── scripts/
```

## 16. Reglas de evolución

Toda decisión que cambie alguno de estos puntos requiere ADR:

- persistencia principal;
- arquitectura local/cloud;
- límites Core/Profile/Playbook;
- proveedor de IA como dependencia obligatoria;
- introducción de nuevas colas/middleware;
- cambio del modelo de trazabilidad;
- cambio de estrategia de originales/documentos derivados.
