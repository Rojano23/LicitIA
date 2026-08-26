# AGENTS.md — LicitIA Development Constitution

Este archivo contiene instrucciones obligatorias para cualquier agente de IA que analice, planifique o modifique el repositorio de LicitIA.

## 1. Antes de escribir código

Lee, en este orden:

1. `README.md`
2. `docs/vision.md`
3. `docs/architecture.md`
4. `docs/domain-model.md`
5. `docs/roadmap.md`
6. `docs/golden-tender-001.md`
7. ADRs aplicables en `docs/adr/`

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

## 4. Reglas técnicas

El sistema puede identificar una posible desviación técnica, pero debe permitir:

- mantener alternativa;
- registrar riesgo;
- añadir justificación;
- cambiar marca/modelo/proveedor;
- aprobar/rechazar la evaluación.

Nunca borres automáticamente una alternativa técnica porque un Engine la considere no conforme.

## 5. Trazabilidad

Todo objeto extraído automáticamente que represente una obligación, criterio o evidencia debe conservar `SourceLocator` con al menos:

- documento;
- versión;
- página;
- sección/bloque cuando sea posible;
- fragmento fuente.

Si no existe fuente confiable, el estado debe ser de revisión, no de certeza.

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

## 13. Definition of Done

Una tarea no está terminada si:

- los tests relevantes no pasan;
- introdujo acoplamiento institucional al Core;
- perdió trazabilidad;
- convirtió una decisión humana en automática;
- no documentó una decisión arquitectónica relevante;
- dejó migraciones inconsistentes;
- agregó infraestructura innecesaria.

## 14. Protección del alcance

MVP v1 soporta **PEMEX / SNR Concursos Abiertos**.

No implementar soporte CFE, estatal, municipal o privado salvo issue/milestone explícito.

Diseñar interfaces extensibles, pero no construir funcionalidad futura “por si acaso”.

## 15. Regla final

> Optimiza LicitIA para reducir trabajo repetitivo y aumentar trazabilidad; nunca para quitar al usuario el control técnico o comercial.
