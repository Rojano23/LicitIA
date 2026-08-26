# LicitIA — Documento Maestro v0.1

**Estado:** Documento base de producto, dominio y arquitectura  
**Objetivo:** servir como “constitución” del proyecto para diseño, desarrollo y validación del MVP.  
**Perfil inicial soportado:** Concursos Abiertos PEMEX / SNR.  
**Arquitectura de producto:** On-Premise / Local-first, extensible mediante perfiles institucionales y playbooks de dominio.

---

## 1. Visión del producto

**LicitIA** es un software local de inteligencia para procesos licitatorios que ayuda al usuario a **entender, organizar, analizar, validar, costear y controlar** una licitación completa a partir de sus bases, anexos, formatos y actos posteriores.

LicitIA no pretende sustituir al responsable técnico, comercial, legal o administrativo. Su función es reducir el tiempo dedicado a localizar información, cruzar documentos, identificar requisitos, comprobar evidencias, reconstruir el estado vigente del procedimiento, preparar matrices de cumplimiento, estructurar partidas y mantener control e historial del proceso.

### Definición corta

> **LicitIA reconstruye el modelo vigente de una licitación, transforma sus criterios de evaluación en requisitos verificables y ayuda al usuario a preparar, revisar y costear su propuesta sin quitarle el control técnico ni comercial.**

---

## 2. Problema que resuelve

Una licitación no es un solo documento. Puede estar formada por decenas o cientos de archivos con información distribuida entre:

- convocatoria;
- bases;
- anexos técnicos;
- catálogos de conceptos o partidas;
- programas de ejecución;
- formatos comerciales, técnicos y económicos;
- requisitos de debida diligencia;
- criterios de evaluación;
- normas y políticas;
- juntas de aclaraciones;
- modificaciones;
- actas y eventos posteriores;
- documentación del participante;
- cotizaciones de proveedores;
- datasheets, certificados, contratos, CV y evidencias.

El problema principal no es “leer PDFs”; es **reconstruir la lógica completa del procedimiento** y mantener trazabilidad entre lo que se solicita, cómo será evaluado, qué evidencia tiene la empresa, qué falta, qué se propone técnicamente y cuánto se decide ofertar.

---

## 3. Principios no negociables de LicitIA

### 3.1 El humano conserva el control

La IA **propone, interpreta, relaciona, detecta y recomienda**. El usuario decide.

El usuario podrá siempre:

- aprobar o rechazar interpretaciones de IA;
- corregir clasificaciones;
- asociar o desasociar evidencias;
- seleccionar marca, modelo, proveedor o solución técnica;
- aceptar conscientemente un riesgo técnico o documental;
- cambiar costos y precios manualmente;
- cambiar márgenes por partida;
- modificar la estrategia económica general;
- decidir BID / NO BID;
- generar o no la propuesta final.

LicitIA nunca deberá bloquear una estrategia comercial únicamente porque difiera de una recomendación del sistema. Cuando exista un riesgo, debe **advertir, explicar y dejar trazabilidad**, no sustituir la decisión empresarial.

### 3.2 Libertad total de precios

El precio ofertado es una decisión humana y estratégica.

Aunque exista una cotización de respaldo, un costo histórico o una estimación calculada por el sistema, el usuario podrá editar manualmente:

- costo unitario;
- costo total;
- flete;
- seguros;
- importación;
- ingeniería;
- mano de obra;
- subcontratación;
- contingencia;
- costo indirecto;
- utilidad;
- markup;
- margen;
- precio unitario ofertado;
- precio total de la partida.

El sistema debe mostrar el efecto de cada ajuste **en tiempo real** sobre:

- utilidad por partida;
- margen por partida;
- utilidad total;
- margen general;
- costo total;
- precio total ofertado;
- concentración de riesgo económico.

El usuario puede ofertar por encima, por debajo o igual al precio sugerido por el sistema. LicitIA debe registrar la decisión, no impedirla.

### 3.3 No inventar requisitos

Todo requisito extraído debe conservar:

- documento fuente;
- sección o numeral;
- página;
- fragmento fuente;
- versión del documento;
- fecha de extracción;
- nivel de confianza.

Si el sistema no puede determinar algo con suficiente certeza debe indicar **REVISAR / AMBIGUO / SIN EVIDENCIA**, nunca inventarlo.

### 3.4 No inventar precios

Todo costo o precio usado como referencia debe indicar su procedencia:

- **CONFIRMADO:** cotización vigente del proveedor;
- **HISTÓRICO:** costo registrado en un proceso anterior;
- **ESTIMADO:** cálculo derivado de históricos/reglas;
- **MANUAL:** valor capturado directamente por el usuario.

Una estimación nunca debe presentarse como una cotización confirmada.

### 3.5 Evidencia antes que opinión

“Cumple” no debe ser una afirmación aislada de IA.

Debe ser una conclusión trazable:

**Requisito → Evidencia → Fuente → Evaluación → Decisión humana.**

### 3.6 Local-first y confidencialidad

Por defecto:

- documentos locales;
- base de datos local;
- OCR local;
- embeddings locales;
- LLM local;
- sin envío automático de documentos a servicios externos.

El soporte futuro para IA Cloud será opcional, explícito y configurable por el cliente.

### 3.7 Arquitectura flexible, no rígida

No programar el producto alrededor de nombres particulares como “DT-4” o “Anexo C”.

El núcleo debe trabajar con conceptos semánticos como:

- `TechnicalEvaluationCriteria`
- `ExperienceRequirement`
- `TenderItemCatalog`
- `EconomicProposal`
- `Evidence`

El **PEMEX Profile** será quien conozca nomenclaturas como DC, DT, DD, DE, D-1, D-3, etc.

---

## 4. Alcance del MVP

### Incluido

- Concursos Abiertos PEMEX / SNR.
- Ingesta masiva de documentos PDF y archivos Office seleccionados.
- OCR cuando el documento no tenga texto extraíble.
- Clasificación documental.
- Reconstrucción del procedimiento y sus etapas.
- Identificación de documentos vigentes y eventos posteriores.
- Extracción de requisitos.
- Extracción de criterios de evaluación.
- Relación entre requisitos y fuentes.
- Detección de referencias cruzadas.
- Matriz comercial/legal.
- Matriz técnica.
- Matriz económica.
- Extracción de partidas / conceptos.
- Relación de partidas con alcances, materiales y equipos.
- Carga de documentación del participante.
- Asociación requisito ↔ evidencia.
- Carga y extracción básica de cotizaciones de proveedores.
- Costeo por partida.
- Margen y utilidad por partida y general.
- Edición manual completa de costos y precios.
- Historial de decisiones y revisiones.
- Dashboard de preparación de propuesta.

### Fuera del MVP

- Presentación automática de propuestas en SISCEP.
- Firma electrónica automática.
- Envío automático a la convocante.
- Decisión autónoma de BID/NO BID.
- Precio final decidido por IA.
- Selección técnica irreversible decidida por IA.
- Soporte formal a CFE u otras dependencias.
- Entrenamiento de un LLM propio desde cero.
- Automatización 100% sin revisión humana.

---

## 5. Modelo conceptual de cuatro capas

```text
LICITIA CORE
    │
    ├── Institution Profile
    │       └── PEMEX Profile v1
    │
    ├── Domain Playbook
    │       └── Industrial Automation / DCS Maintenance (primer caso)
    │
    └── Tender Instance
            └── SNR-CAD-265-CA-S-2026 (Golden Tender #001)
```

### 5.1 LicitIA Core

Conocimiento genérico del proceso:

- documentos;
- requisitos;
- evidencias;
- partidas;
- eventos;
- versiones;
- evaluación;
- propuestas;
- costos;
- decisiones;
- auditoría.

### 5.2 Institution Profile

Conocimiento particular de la institución.

**PEMEX Profile v1** puede incluir:

- Concurso Abierto;
- SISCEP;
- HIIP;
- e-Firma;
- familias DC / DT / DD / DE / D;
- SSPA;
- contenido nacional;
- Debida Diligencia;
- nomenclaturas habituales;
- patrones de referencias;
- reglas de evaluación conocidas.

### 5.3 Domain Playbook

Conocimiento técnico por especialidad.

Ejemplos futuros:

- Instrumentación;
- Automatización;
- DCS/SIS;
- Válvulas;
- Eléctrico;
- Construcción;
- TI;
- Servicios profesionales.

Un perfil institucional explica **cómo licita una institución**. Un playbook de dominio explica **cómo analizar técnicamente el objeto licitado**.

### 5.4 Tender Instance

Representa un procedimiento real con:

- expediente;
- documentos;
- versiones;
- cronograma;
- requisitos;
- partidas;
- evidencias;
- decisiones;
- costos;
- propuesta.

---

## 6. Arquitectura funcional

```text
DOCUMENTOS / EXPEDIENTE
        │
        ▼
Tender Ingestion Engine
        │
        ▼
Document Registry
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
   ┌────┼────────────────────────────┐
   ▼    ▼                            ▼
Reference Resolver            Applicability Engine
   │                                  │
   └──────────────┬───────────────────┘
                  ▼
          Evaluation Model Engine
                  │
                  ▼
          Requirement Compiler
                  │
                  ▼
             Tender Model
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
 Evidence      Technical    Commercial/
 Engine        Compliance   Economic Engine
     │            │            │
     └────────────┼────────────┘
                  ▼
             Bid Readiness
                  │
                  ▼
             Human Review
```

---

## 7. Engines principales

### 7.1 Tender Ingestion Engine

Responsabilidad:

- recibir múltiples archivos;
- registrar archivo original;
- calcular hash;
- determinar tipo MIME;
- contar páginas;
- detectar si requiere OCR;
- generar registro inmutable del original.

### 7.2 Document Registry

Cada documento debe tener:

- ID interno;
- nombre original;
- hash;
- tipo;
- fecha;
- versión;
- fuente;
- páginas;
- estado de procesamiento;
- rol documental;
- relaciones.

### 7.3 Document Role Classifier

Clasificación semántica, independiente del nombre de archivo.

Valores iniciales:

- `GOVERNING`
- `PROCEDURAL`
- `EVALUATION_CRITERIA`
- `TECHNICAL_SCOPE`
- `COMMERCIAL_SCOPE`
- `ECONOMIC_SCOPE`
- `SUBMISSION_FORM`
- `EVIDENCE_TEMPLATE`
- `CONTRACTUAL`
- `POLICY_REFERENCE`
- `PROCEDURAL_GUIDE`
- `INFORMATIVE`
- `UNKNOWN`

### 7.4 Procedure & Event Engine

Construye el ciclo del procedimiento:

- publicación;
- interés en participar;
- visita;
- preguntas;
- aclaraciones;
- modificaciones;
- presentación;
- apertura;
- evaluación;
- fallo;
- formalización.

### 7.5 Version / Tender State Engine

Debe responder:

> ¿Cuál es el estado vigente de la licitación en este momento?

Debe conservar historial de:

- requisito original;
- aclaración;
- modificación;
- versión vigente.

### 7.6 Tender Understanding Engine

Componente central.

Su función no es resumir PDFs, sino construir una representación estructurada de la licitación:

- qué documentos existen;
- qué rol tienen;
- cómo se relacionan;
- qué reglas contienen;
- qué alcance definen;
- qué requisitos generan;
- qué partidas afectan;
- qué información falta;
- qué información es ambigua.

### 7.7 Reference Resolver

Resuelve referencias como:

- “Anexo B-4”;
- “DT-4”;
- “Sección VIII.1”;
- “Numeral 4.2”;
- “Formato 4”;
- “Anexo C”.

Debe detectar documentos referenciados pero no cargados.

### 7.8 Applicability Engine

Determina si una obligación es aplicable al procedimiento concreto.

No debe tratar cada página de una norma como un requisito particular si el documento contiene mecanismos para determinar aplicabilidad.

Resultados:

- `APPLIES`
- `DOES_NOT_APPLY`
- `CONDITIONAL`
- `UNKNOWN`

### 7.9 Evaluation Model Engine

Debe identificar **cómo será evaluada la propuesta** antes de compilar los requisitos.

Métodos soportados inicialmente:

- `BINARY`
- `PASS_FAIL`
- `PRICE_BASED`
- `CUSTOM`

Preparado para futuro:

- puntos;
- ponderación;
- costo-beneficio;
- híbrido.

### 7.10 Requirement Compiler

Transforma lenguaje documental en requisitos estructurados.

Ejemplo:

```text
Requirement
  category = TECHNICAL_EXPERIENCE
  mandatory = true
  required_contracts = 2
  max_age_years = 5
  technology = [Centum VP, Prosafe RS]
  evidence = [Contract, DeliveryAct, Closeout]
  evaluation = PASS_FAIL
```

### 7.11 Evidence Engine

Relaciona documentación empresarial con requisitos.

Estados:

- `CONFIRMED`
- `PROBABLE`
- `INSUFFICIENT`
- `MISSING`
- `REJECTED_BY_USER`

Toda evidencia conserva fuente y ubicación.

### 7.12 Technical Compliance Engine

Compara:

- requisitos técnicos;
- alcance;
- propuesta técnica;
- marca/modelo;
- datasheets;
- certificados;
- experiencia;
- personal;
- herramientas;
- servicios.

Cuando exista una comparación determinista, usar regla en lugar de LLM.

Ejemplo:

```text
required_accuracy <= 0.5%
proposed_accuracy = 0.3%
=> PASS
```

Cuando exista ambigüedad:

```text
=> REVIEW_REQUIRED
```

### 7.13 Tender Item Engine

No crear un “Anexo C Engine”.

Debe descubrir el documento que cumple la función de catálogo de partidas/conceptos.

Entidad:

```text
TenderItem
  item_number
  description
  quantity
  unit
  source
  scope_components[]
  technical_requirements[]
  cost_components[]
```

Una partida puede estar definida en varias fuentes.

### 7.14 Commercial / Cost Engine

Debe separar:

**Costo interno** de **precio ofertado**.

#### Capas de costo sugeridas

```text
Compra / suministro
+ Mano de obra
+ Ingeniería
+ Herramientas / maquinaria
+ Logística
+ Fletes
+ Seguros
+ Importación
+ Subcontratos
+ Viáticos
+ SSPA
+ Documentación
+ Contingencia
+ Otros
= COSTO BASE
```

Posteriormente:

```text
Costo base
+ estrategia comercial
= Precio ofertado
```

La estrategia comercial no será rígida.

### 7.15 Bid Readiness Engine

No decide automáticamente BID/NO BID.

Presenta al usuario:

- requisitos críticos faltantes;
- cumplimiento documental;
- cumplimiento técnico;
- cobertura de partidas;
- partidas sin cotización;
- exposición económica;
- margen estimado;
- documentos vencidos;
- referencias sin resolver;
- ambigüedades.

El usuario decide.

---

## 8. Modelo de datos mínimo

Entidades iniciales:

- `Tender`
- `TenderDocument`
- `DocumentVersion`
- `DocumentSection`
- `DocumentReference`
- `TenderEvent`
- `Requirement`
- `RequirementVersion`
- `EvaluationCriterion`
- `Evidence`
- `EvidenceAssessment`
- `HumanDecision`
- `TenderItem`
- `TenderItemScope`
- `TechnicalProposal`
- `Product`
- `Supplier`
- `SupplierQuote`
- `SupplierQuoteLine`
- `CostComponent`
- `PriceScenario`
- `BidPrice`
- `CompanyDocument`
- `CompanyPerson`
- `CompanyExperience`
- `CompanyCertification`
- `AuditEvent`

---

## 9. Modelo de estados de cumplimiento

Estados principales:

- 🟢 `COMPLIES`
- 🟡 `REVIEW`
- 🔴 `DOES_NOT_COMPLY`
- ⚪ `NO_EVIDENCE`
- 🔵 `ESTIMATED`

Separar siempre:

- decisión IA;
- decisión determinista;
- decisión humana.

Ejemplo:

```text
AI Assessment: PROBABLE_COMPLIANCE
Rule Assessment: NOT_APPLICABLE
Human Decision: APPROVED
```

---

## 10. Modelo económico y libertad de estrategia

### 10.1 Fuentes de costo

Cada valor económico tendrá:

- importe;
- moneda;
- fecha;
- origen;
- proveedor;
- documento de respaldo si existe;
- vigencia;
- confianza;
- comentario.

### 10.2 Tipo de fuente

```text
CONFIRMED_QUOTE
HISTORICAL_COST
SYSTEM_ESTIMATE
MANUAL_INPUT
```

### 10.3 Precio final siempre editable

Para cada partida, el usuario podrá capturar manualmente:

- precio unitario final;
- importe final;
- margen objetivo;
- markup objetivo;
- descuento;
- contingencia;
- ajuste estratégico.

El software recalcula sin impedir la decisión.

### 10.4 Margen y markup

LicitIA deberá distinguir explícitamente ambos conceptos para evitar errores.

```text
Utilidad = Precio de Venta - Costo

Margen % = Utilidad / Precio de Venta × 100

Markup % = Utilidad / Costo × 100
```

El usuario podrá trabajar con margen, markup o precio directo.

### 10.5 Vista por partida

Cada partida debe mostrar:

- costo confirmado;
- costo histórico;
- estimación;
- costo manual actual;
- precio ofertado;
- utilidad;
- margen;
- markup;
- fuente;
- riesgo;
- estado técnico.

### 10.6 Vista general

Mostrar:

- costo total;
- venta total;
- utilidad total;
- margen global;
- markup global;
- partidas con pérdida;
- partidas con margen inferior al objetivo;
- partidas sin precio;
- partidas sin costo confirmado;
- concentración de utilidad por partida.

### 10.7 Escenarios

El sistema debe permitir escenarios sin modificar la propuesta base:

```text
BASE
AGGRESSIVE
TARGET
CONSERVATIVE
CUSTOM
```

Cada escenario puede tener precios y márgenes diferentes.

El usuario decide cuál convertir en propuesta.

---

## 11. Flexibilidad técnica

De manera equivalente a los precios, la estrategia técnica pertenece al usuario.

El sistema debe permitir:

- múltiples alternativas por partida;
- marca/modelo A, B, C;
- opción principal y alterna;
- proveedor diferente;
- observación de desviación;
- aprobación explícita de excepción;
- sustitución posterior;
- historial de cambios.

Si una alternativa parece incumplir:

> LicitIA debe advertir y mostrar evidencia, no borrar automáticamente la alternativa.

---

## 12. Trazabilidad y auditoría

Cada acción relevante debe guardar:

- usuario;
- fecha/hora;
- entidad afectada;
- valor anterior;
- valor nuevo;
- fuente;
- motivo opcional;
- origen de decisión: AI / RULE / HUMAN.

Esto permite reconstruir cómo se preparó una propuesta.

---

## 13. Golden Tender #001

El procedimiento **SNR-CAD-265-CA-S-2026** será el primer expediente de referencia.

Debe utilizarse como conjunto de validación para probar:

- clasificación documental;
- reconstrucción de la estructura;
- referencias cruzadas;
- requisitos comerciales;
- requisitos técnicos;
- requisitos económicos;
- Debida Diligencia;
- partidas;
- alcances;
- materiales;
- maquinaria;
- condiciones SSPA;
- propuesta económica;
- reglas de evaluación.

No se codificarán excepciones especiales únicamente para hacerlo pasar.

El objetivo es que las reglas creadas sean reutilizables.

---

## 14. Ejemplos confirmados por Golden Tender #001

### 14.1 Estructura del procedimiento

El expediente separa comercial, técnico, económico, Debida Diligencia, criterios de evaluación, documentación complementaria y modelo de contrato.

### 14.2 Evaluación comercial

Existen requisitos que son evaluados de manera binaria y contienen criterios explícitos de revisión.

### 14.3 Evaluación técnica

Existen requisitos técnicos con método CUMPLE / NO CUMPLE.

### 14.4 Evaluación económica

La propuesta económica debe conservar correspondencia con catálogo de conceptos, unidad, cantidad, precio unitario e importe.

### 14.5 Partida no equivale a alcance

Una partida puede depender de información distribuida en especificaciones particulares, catálogo de alcances, materiales, maquinaria, seguridad y otros anexos.

Por eso `TenderItem` debe mantener múltiples `scope_components`.

---

## 15. Arquitectura tecnológica propuesta

### Desktop

- Tauri 2
- React
- TypeScript
- Vite

### Backend local

- Python
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic

### Datos

- PostgreSQL
- pgvector
- filesystem local para originales

### Document Intelligence

- PyMuPDF
- parser por página
- extracción de tablas
- OCR local cuando sea requerido
- parser DOCX/XLSX cuando aplique

### IA local

- Ollama como proveedor inicial
- capa de abstracción de modelo
- embeddings locales

### Jobs

Comenzar con jobs locales / worker sencillo.

No introducir Redis hasta demostrar una necesidad concreta.

### Empaquetado

Desarrollo inicial:

- Docker Compose puede utilizarse internamente.

Producto final:

- instalación transparente al usuario;
- Docker no debe ser requisito visible para el cliente.

---

## 16. Seguridad

### Principios

- No enviar archivos a Internet por defecto.
- Separar documentos originales de datos derivados.
- Hash de archivos originales.
- Cifrado local donde sea viable.
- Credenciales protegidas mediante mecanismos del sistema operativo.
- Registro de auditoría.
- Backups configurables.
- Exportación explícita.

### Modo futuro opcional

```text
LOCAL_ONLY
LOCAL_WITH_OPTIONAL_CLOUD_AI
```

La segunda opción deberá requerir consentimiento explícito.

---

## 17. UI / UX principal

La aplicación debe responder rápidamente cinco preguntas:

1. ¿Qué me están solicitando?
2. ¿Qué documentos necesito?
3. ¿Cumplo técnicamente?
4. ¿Cuánto me cuesta y cuánto quiero ofertar?
5. ¿Qué me falta antes de presentar?

Pantallas núcleo:

- Centro de Licitaciones;
- Detalle de licitación;
- Documentos / visor;
- Matriz de requisitos;
- Cumplimiento técnico;
- Partidas;
- Detalle de partida;
- Cotizaciones;
- Costeo;
- Propuesta económica;
- Base documental de la empresa;
- Bid Readiness.

La IA debe mostrarse de manera contextual, no como chatbot central.

---

## 18. Indicador de comprensión del expediente

Antes de mostrar un porcentaje de cumplimiento, LicitIA debe mostrar qué tan completa es su comprensión del procedimiento.

Ejemplo:

```text
Documentos procesados        22/22
Referencias resueltas        94/97
Documentos faltantes         3
Requisitos extraídos         138
Requisitos ambiguos          4
Partidas detectadas          2
Partidas con alcance ligado  2

Integridad del análisis: 93%
```

No debe generar falsa certeza cuando faltan documentos o existen referencias sin resolver.

---

## 19. Flujo operativo ideal

```text
1. Crear licitación
2. Importar expediente completo
3. Clasificar documentos
4. Construir mapa documental
5. Detectar eventos/versiones
6. Identificar modelo de evaluación
7. Compilar requisitos
8. Extraer partidas
9. Relacionar alcances
10. Revisar interpretación humana
11. Cargar biblioteca empresarial
12. Asociar evidencias
13. Evaluar cumplimiento
14. Seleccionar estrategia técnica
15. Cargar cotizaciones / costos
16. Ajustar precios manualmente
17. Revisar margen por partida
18. Revisar margen general
19. Resolver pendientes
20. Generar propuesta / expediente
```

---

## 20. Filosofía de IA

### IA debe utilizarse para

- clasificación semántica;
- extracción estructurada;
- resolución de referencias;
- detección de relaciones;
- identificación de requisitos;
- detección de ambigüedad;
- asociación probable de evidencia;
- interpretación técnica no determinista;
- matching de cotizaciones con partidas;
- generación de borradores y explicaciones.

### Software determinista debe utilizarse para

- cálculos;
- fechas;
- vencimientos;
- cantidades;
- comparación de rangos;
- validación numérica;
- cálculo de costos;
- margen;
- markup;
- totales;
- reglas explícitas.

### Humano debe decidir

- interpretación dudosa;
- aceptación de evidencia;
- estrategia técnica;
- proveedor;
- marca/modelo;
- costo asumido;
- margen;
- precio ofertado;
- riesgo aceptable;
- BID / NO BID;
- propuesta final.

---

## 21. Estrategia de expansión futura

### Fase 1

`LicitIA Core + PEMEX Profile v1`

### Fase 2

Probar una licitación real de CFE sin adaptación.

Medir:

- qué entendió el Core;
- qué falló;
- qué conceptos fueron específicos de CFE.

Crear:

`CFE Profile v1`

### Fase 3

Perfiles adicionales:

- Gobierno Federal;
- gobiernos estatales;
- municipios;
- procesos privados.

La incorporación de una nueva institución no debe exigir reescribir el Core.

---

## 22. Roadmap sugerido

### MVP-00 — Constitución del proyecto

- Documento Maestro.
- Domain Model.
- Architecture Decision Records.
- AGENTS.md.
- Golden Tender #001.
- repositorio y pruebas base.

### MVP-01 — Tender Workspace

- crear licitación;
- cargar archivos;
- registro documental;
- hash;
- visor PDF;
- metadata.

### MVP-02 — Document Intelligence

- extracción;
- OCR;
- secciones;
- tablas;
- clasificación documental.

### MVP-03 — Tender Understanding

- referencias;
- relaciones;
- eventos;
- versiones;
- estado vigente.

### MVP-04 — Evaluation & Requirements

- identificar modelo de evaluación;
- compilar requisitos;
- trazabilidad.

### MVP-05 — Evidence & Compliance

- biblioteca empresarial;
- evidencia;
- cumplimiento;
- revisión humana.

### MVP-06 — Tender Items & Technical Scope

- catálogo de partidas;
- alcances;
- materiales;
- equipos;
- estrategia técnica.

### MVP-07 — Costing & Pricing

- cotizaciones;
- históricos;
- costos;
- edición manual;
- escenarios;
- márgenes;
- precio ofertado.

### MVP-08 — Bid Readiness

- dashboard integral;
- pendientes;
- riesgos;
- estado de preparación.

### MVP-09 — Proposal Builder

- matrices;
- exportaciones;
- propuesta económica;
- expediente de salida.

---

## 23. Criterios de aceptación del MVP

El MVP se considerará útil cuando pueda procesar el Golden Tender #001 y permitir al usuario:

1. visualizar todos los documentos del expediente;
2. entender la función de cada documento;
3. identificar referencias entre documentos;
4. detectar documentos faltantes;
5. identificar criterios de evaluación;
6. generar una matriz de requisitos trazable;
7. relacionar requisitos con evidencias;
8. detectar requisitos pendientes o ambiguos;
9. extraer las partidas del catálogo;
10. relacionar cada partida con su alcance técnico real;
11. cargar cotizaciones de proveedores;
12. asociar costos a partidas;
13. editar cualquier costo o precio manualmente;
14. mostrar margen y utilidad por partida;
15. mostrar margen y utilidad global;
16. conservar histórico de decisiones;
17. mostrar qué falta antes de presentar;
18. exportar matrices y propuesta económica para revisión humana.

---

## 24. Reglas para los agentes de desarrollo

1. LicitIA es On-Premise y local-first.
2. No enviar documentos a servicios externos por defecto.
3. No inventar requisitos.
4. No inventar precios.
5. Toda conclusión debe conservar trazabilidad.
6. El usuario puede sobrescribir decisiones de IA.
7. El usuario puede editar costos y precios en todo momento.
8. Los precios sugeridos nunca son obligatorios.
9. La estrategia técnica pertenece al usuario.
10. No programar reglas rígidas basadas únicamente en nombres PEMEX.
11. Separar Core, Institution Profile, Domain Playbook y Tender Instance.
12. Preferir reglas deterministas para cálculos y validaciones explícitas.
13. Usar IA cuando exista comprensión semántica real.
14. Toda ambigüedad debe poder terminar en `REVIEW_REQUIRED`.
15. No introducir microservicios, Redis, Kafka o Kubernetes sin necesidad demostrada.
16. Mantener el producto instalable por usuarios no técnicos.
17. Cada Engine debe tener pruebas unitarias.
18. Golden Tender #001 debe utilizarse como prueba funcional/regresión.
19. Ningún Engine debe depender de una única licitación para funcionar.
20. Toda modificación arquitectónica significativa debe documentarse.

---

## 25. Métrica de éxito del producto

LicitIA no será evaluado por “cuántos PDFs lee”, sino por cuánto reduce:

- tiempo para entender un expediente;
- tiempo para localizar requisitos;
- omisiones documentales;
- errores de cumplimiento;
- tiempo para preparar matrices;
- tiempo para cruzar anexos;
- tiempo para costear partidas;
- pérdida de trazabilidad;
- reutilización manual de información de licitaciones anteriores.

La meta final es que el usuario tenga **más tiempo para decidir la estrategia técnica y comercial**, porque LicitIA absorbe el trabajo repetitivo de organización, extracción, relación, validación e historización.

---

## 26. Principio rector final

> **LicitIA no gana licitaciones por el usuario. Le da al usuario una comprensión más rápida, completa, trazable y controlable del proceso para que pueda tomar mejores decisiones técnicas, documentales y comerciales.**

