# AGENTS.md — LicitIA Development Constitution

Este archivo contiene instrucciones obligatorias para cualquier agente de IA que analice, planifique o modifique el repositorio de LicitIA.

## 1. Antes de escribir código

Antes de comenzar un NUEVO slice sustancial de implementación, lee, en este orden:

1. `README.md`
2. `docs/vision.md`
3. `docs/architecture.md`
4. `docs/domain-model.md`
5. `docs/roadmap.md`
6. `docs/golden-tender-001.md`
7. ADRs aplicables en `docs/adr/`

Durante el seguimiento del MISMO slice/contexto, no releas mecánicamente todos los documentos; relee los relevantes cuando cambien supuestos o alcance. Para validaciones o seguimientos pequeños y acotados, inspecciona sólo documentos y código necesarios, salvo otra obligación explícita de esta constitución.

Consulta `docs/architecture.md` para límites de servicios, runtime, proveedores, persistencia o despliegue; `docs/domain-model.md` para entidades, contratos o persistencia; `docs/roadmap.md` para estado MVP, límites de slices o política aceptada; y `docs/golden-tender-001.md` cuando se necesite contexto Golden de Tender #001.

El working tree y código actuales son la fuente de verdad de implementación; no asumas que un reporte o conversación anterior describe el código vigente.

Si una tarea contradice estos documentos, detente y señala la contradicción antes de implementar.

## 2. Principios no negociables

1. LicitIA es **On-Premise / Local-first**.
2. No envíes documentos, embeddings ni información sensible a servicios externos por defecto.
3. No inventes requisitos.
4. No inventes precios.
5. Toda conclusión automática debe conservar trazabilidad a su fuente.
6. La IA propone; el usuario decide.
7. El usuario puede sobrescribir evaluaciones de IA y reglas cuando el flujo lo permita.
8. El usuario puede modificar costos y precios en todo momento antes de cerrar su propuesta.
9. El precio final es una decisión humana.
10. La estrategia técnica es una decisión humana.
11. Una advertencia no debe convertirse automáticamente en bloqueo comercial.
12. Toda ambigüedad debe poder terminar en `REVIEW_REQUIRED`.
13. No hardcodees el Core alrededor de nombres PEMEX como `DT-4`, `D-3` o `Anexo C`.
14. Separa `Core`, `Institution Profile`, `Domain Playbook` y `Tender Instance`.
15. Usa reglas deterministas para aritmética, fechas y comparaciones explícitas.
16. Usa IA sólo cuando exista necesidad semántica.
17. No introduzcas Redis, Kafka, Kubernetes ni microservicios sin un problema medido que lo justifique.
18. Los originales del expediente son inmutables.
19. Los datos derivados deben ser regenerables/versionables.
20. Toda decisión arquitectónica significativa requiere ADR.

La visión de LicitIA abarca inteligencia de licitaciones industriales y contratación pública/privada mexicana; esto no amplía el alcance del MVP vigente.

La confidencialidad incluye documentos licitatorios, embeddings, información confidencial y datos sensibles de clientes. Cualquier procesamiento externo/cloud requiere aprobación explícita arquitectónica y del usuario cuando corresponda; nunca se habilita por defecto.

LicitIA automatiza sólo con evidencia suficiente. Si una ambigüedad estructural o semántica afecta alcance contractual, cumplimiento, versionado, cantidades, precios o entregables, expón la revisión humana en lugar de inferir hechos sin soporte. La revisión humana es autoritativa para decisiones contractuales.

Nunca inventes requisitos, obligaciones contractuales, Source Effects, cantidades, precios, targets documentales, evidencia ni conclusiones de cumplimiento. Falla de forma cerrada (fail-closed): prefiere `REVIEW_REQUIRED` a una inferencia sin soporte.

La clasificación describe el documento; no debe impedir que otros motores semánticos descubran requisitos u obligaciones de alcance de ejecución válidos dentro de él. Un fragmento puede producir registros en varios dominios semánticos cuando cada registro esté sustentado independientemente por evidencia y provenance.

## 3. Reglas comerciales

### Prohibido

- fijar automáticamente el precio de venta;
- impedir un override manual por existir una cotización;
- confundir markup con margen;
- presentar estimaciones como costos confirmados;
- ocultar partidas con pérdida;
- corregir silenciosamente un precio introducido por el usuario.

### Obligatorio

Cada valor económico debe identificar su origen:

- `CONFIRMED_QUOTE`
- `HISTORICAL_COST`
- `SYSTEM_ESTIMATE`
- `MANUAL_INPUT`

Si el usuario reemplaza un valor, conserva auditoría y origen anterior.

Las vistas económicas deben soportar:

- utilidad por partida;
- margen por partida;
- markup por partida;
- utilidad global;
- margen global;
- costo total;
- venta total;
- escenarios.

No optimices silenciosamente un resultado comercialmente indeseable; los escenarios con pérdida y sus consecuencias deben seguir visibles para decisión humana. La estrategia comercial y de precios permanece bajo control humano.

## 4. Reglas técnicas

El sistema puede identificar una posible desviación técnica, pero debe permitir:

- mantener alternativa;
- registrar riesgo;
- añadir justificación;
- cambiar marca/modelo/proveedor;
- aprobar/rechazar la evaluación.

Nunca borres automáticamente una alternativa técnica porque un Engine la considere no conforme.

Conserva las alternativas y sus consecuencias para decisión humana. Sólo un contrato de dominio aceptado que lo exija explícitamente puede convertir una advertencia en bloqueo comercial.

## 5. Trazabilidad

Todo objeto extraído automáticamente que represente una obligación, criterio o evidencia debe conservar `SourceLocator` con al menos:

- documento;
- versión documental;
- página;
- sección/bloque cuando sea posible;
- fragmento fuente.

Si no existe fuente confiable, el estado debe ser de revisión, no de certeza.

No pierdas provenance de versión documental. Toda conclusión significativa extraída o resuelta debe conservar documento, página/locator, fragmento y confianza/estado de revisión cuando el contrato de dominio lo soporte.

## 6. Calidad de IA

No uses una respuesta libre del LLM como dato canónico.

Preferir:

```text
Document → Structured Extraction → Typed Schema → Validation → Persist
```

No:

```text
Document → LLM prose → Persist prose as truth
```

Toda salida del modelo debe validarse con Pydantic/schema equivalente.

## 7. Base de datos

- SQLAlchemy 2 style.
- Pydantic v2.
- Alembic para migraciones.
- No cambios manuales de esquema sin migración.
- No almacenar PDFs completos como blobs en tablas salvo decisión ADR explícita.
- Originals en filesystem; DB almacena metadata/rutas/identificadores/hash.

Almacenar originales PDF u otros documentos como blobs en base de datos requiere un ADR explícito. La capacidad técnica del backend o una indicación arquitectónica sin ese ADR no debilita este requisito.

## 8. Frontend

- React + TypeScript estricto.
- No `any` salvo justificación puntual.
- UI Desktop-first.
- IA contextual; no chatbot como navegación principal.
- Estados claros: cumple / revisar / no cumple / sin evidencia / estimado.
- Diferenciar evaluación automática de decisión humana.
- Toda acción destructiva o irreversible requiere confirmación de usuario.

## 9. Backend

- FastAPI.
- servicios de dominio desacoplados de FastAPI.
- Engines sin dependencia directa de UI.
- adaptadores externos detrás de interfaces.
- proveedor LLM intercambiable.
- errores explícitos; no swallow exceptions.

No acoples lógica de dominio/negocio al comportamiento de presentación.

## 10. Tests

Toda nueva funcionalidad debe incluir la prueba adecuada.

### Obligatorio por Engine

- unit tests;
- casos de éxito;
- caso ambiguo;
- caso de ausencia de fuente;
- error handling.

### Golden Tender

Las pruebas relacionadas con `Golden Tender #001` deben comprobar estructura y trazabilidad, no texto generativo exacto.

No añadas una excepción específica sólo para hacer pasar el Golden Tender.

Toda implementación debe cerrar con validación reproducible apropiada a la superficie cambiada:

```text
focused tests → relevant regression → broader regression sólo cuando la superficie de producción cambiada lo requiera
```

No ejecutes suites costosas ajenas por hábito. Si la tarea proporciona comandos exactos, úsalos exactamente.

Los mocks sólo prueban contratos y control de flujo; no prueban calidad semántica, visual, OCR ni comportamiento de modelos reales.

Reporta evidencia exacta: comandos ejecutados, conteos pass/fail, warnings relevantes, migraciones/estado, compilación cuando corresponda, estado/diff de Git y blockers.

## 11. Observabilidad

Mantener observabilidad acotada.

No crear streams/logs sin política de retención.

Registrar sólo lo necesario para:

- diagnosticar fallos;
- medir jobs;
- validar procesamiento;
- auditar decisiones importantes.

## 12. Workflow esperado para tareas

Para tareas medianas/grandes:

1. leer documentación relevante;
2. explicar impacto;
3. proponer plan;
4. identificar archivos a modificar;
5. implementar por etapas;
6. ejecutar tests;
7. reportar resultados y riesgos pendientes.

No implementar “todo LicitIA” en una sola tarea.

Antes de editar, entiende la superficie mínima relevante. Prefiere el cambio seguro más pequeño. No hagas refactors amplios en un slice acotado sin necesidad explícita ni amplíes silenciosamente su alcance.

Si implementar requiere tocar un módulo prohibido o fuera de alcance, DETENTE y reporta el blocker antes de editarlo.

No alteres producción sólo para hacer pasar un Golden o test; determina primero si está mal la expectativa o el comportamiento. Para cambios complejos, multi-módulo, migraciones o arquitectura, prepara un plan breve antes de editar; en tareas pequeñas procede tras inspeccionar lo relevante.

## 13. Definition of Done

Una tarea no está terminada si:

- los tests relevantes no pasan;
- introdujo acoplamiento institucional al Core;
- perdió trazabilidad;
- convirtió una decisión humana en automática;
- no documentó una decisión arquitectónica relevante;
- dejó migraciones inconsistentes;
- agregó infraestructura innecesaria.

No basta con escribir código: demuestra los invariantes relevantes, conserva intactas las superficies prohibidas y no introduzcas fallbacks ocultos ni inferencias sin soporte. No declares COMPLETE con condiciones obligatorias pendientes; reporta blockers y verifica que `git diff --check` no tenga errores.

## 14. Protección del alcance

MVP v1 soporta **PEMEX / SNR Concursos Abiertos**.

No implementar soporte CFE, estatal, municipal o privado salvo issue/milestone explícito.

Diseñar interfaces extensibles, pero no construir funcionalidad futura “por si acaso”.

La visión puede ser más amplia, pero el MVP ACTUAL permanece en PEMEX / SNR Concursos Abiertos. No amplíes ese alcance sin aprobación explícita del roadmap, además del issue/milestone correspondiente.

### Política MVP de Source Effects

El descubrimiento automático de Source Effects con Qwen/Ollama NO está certificado para el MVP. El camino autoritativo es:

```text
deterministic discovery
→ strict validation
→ REVIEW_REQUIRED when ambiguous
→ human validation
→ persisted Source Effect
→ deterministic resolution/projection
```

Conserva la infraestructura LLM bounded como experimental y reutilizable, salvo cambio explícito de política. No conectes Qwen automáticamente al runtime MVP de Source Effects sin aprobación arquitectónica explícita.

### Protección de Tender #002

Tender #002 es material ciego out-of-sample reservado para MVP-06.V. No inspecciones, busques, abras, parses, extraigas, resumas ni uses ese corpus sin autorización explícita para la fase de validación ciega. No lo uses para tuning de prompts, calibración, creación de fixtures, construcción Golden ni ejemplos de desarrollo.

### Seguridad de Git

- Nunca uses `git add .`.
- Usa staging explícito por archivo; no incluyas archivos ajenos.
- No hagas stage, commit ni push sin instrucción explícita del usuario.
- La aceptación humana normalmente precede al commit.
- No borres, renombres ni hagas stage de reportes históricos/no rastreados salvo solicitud explícita.
- Antes de entregar, inspecciona `git status --short`, `git diff --stat` y `git diff --check`.

### Prioridad e instrucciones de backend

El `AGENTS.md` raíz define la política global de producto, arquitectura y seguridad. Los `AGENTS.md` anidados pueden añadir instrucciones específicas de implementación; no pueden debilitar seguridad, confidencialidad, provenance, autoridad humana ni alcance MVP. Ante conflicto con estos principios, DETENTE y repórtalo.

`backend/AGENTS.md` detalla el intérprete Python obligatorio, bases dev/test, autoridad de Alembic, restricciones de modelos reales, disciplina Golden y convenciones de tests/compilación. Estos detalles operativos complementan los principios autoritativos de la raíz.

### Idioma

La narración, avances y reportes finales al usuario deben estar en español (México), salvo solicitud explícita de otro idioma. Identificadores, schemas, constantes y terminología técnica existente pueden permanecer en inglés.

## 15. Regla final

> Optimiza LicitIA para reducir trabajo repetitivo y aumentar trazabilidad; nunca para quitar al usuario el control técnico o comercial.
