# Scope Quantity Calibration (MVP-06.4.4a)

## Estado

HUMAN GOLDEN APPROVED AND FROZEN
REAL MODEL CALIBRATION BASELINE 003 EXECUTED
CALIBRATION DECISION: ACCEPT BOUNDED

## Propósito

Este slice define infraestructura determinista de Golden para cantidades semánticas.
No evalúa ni aprueba modelos todavía.

## Activos Golden

- Golden file: `evals/scope_quantity_golden_v1.json`
- Golden version: `scope-quantity-golden-2026-09-08-001`
- Data source authority: `Tender.external_reference = SNR-CAD-265-CA-S-2026`
- Golden file SHA-256: `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7`
- Fuente: `TenderScopeDetail` persistido en `licitia_dev`

## Contrato semántico de producción

- `scope-quantity-semantic-discovery-2026-09-08-003`
- Actualizado en este slice como Contract 003.

## Modelo calibrado

- Baseline calibrado en 06.4.4b: `qwen3:8b`
- Resultado formal de calibración en Golden v1: `ACCEPT BOUNDED`

## Gate humano obligatorio

- Etiquetas válidas: `PENDING`, `APPROVED`
- Dataset draft inicial: todos `PENDING`
- El runner falla en modo cerrado si existe cualquier `PENDING`

## Política de matching (determinista)

Comparación semántica por cantidad:

- `quantity_raw` normalizado
- `unit_raw` normalizado
- `measure_kind`
- `relation`
- valores numéricos comparados como Decimal:
  - `quantity_value`
  - `quantity_min`
  - `quantity_max`

Sin embeddings, sin LLM judge, sin similitud semántica difusa.

## Política de evidence grounding

Para cada cantidad descubierta:

- `source_excerpt` debe estar grounded en `source_text`
- `quantity_raw` debe estar grounded en `source_excerpt`
- `unit_raw` (si existe) debe estar grounded en `source_excerpt`

La igualdad exacta de span entre evidencia Golden y evidencia descubierta no es obligatoria para identidad semántica.
Grounding sí es obligatorio.

## Definiciones de métrica

- Precision = matched / discovered
- Recall = matched / expected
- Hard-negative pass = casos `NO_QUANTITIES` en PASS
- Critical leakage = cantidad descubierta grounded en literal de `forbidden_quantity_literals`

## Gates pre-registrados (para 06.4.4b)

- `INVALID_OUTPUT`: 0 (mandatorio)
- `critical_technical_leakage`: 0 (mandatorio)
- `precision >= 0.85`
- `recall >= 0.70`
- `hard_negative_pass >= 0.80`
- `mixed_context_pass >= 0.80` cuando existan casos reales de mixed context

Estos gates no se degradan por resultados de corrida sin decisión explícita de arquitecto.

## Historial real de baseline

### Baseline 001

- Fecha: 2026-09-08
- Modelo: qwen3:8b
- Contrato: `scope-quantity-semantic-discovery-2026-09-08-001`
- Golden: `scope-quantity-golden-2026-09-08-001`
- SHA Golden: `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7`
- Resultados: `PASS=3`, `FAIL=0`, `REVIEW_REQUIRED=0`, `INVALID=8`
- Discovery: `INVALID_OUTPUT=8`, `NO_QUANTITIES=3`
- Cantidades: `expected=8`, `discovered=0`, `matched=0`, `missing=8`, `unexpected=0`
- Precision / recall: `0.0000 / 0.0000`
- Hard-negative: `3/3`
- Mixed-context: `0/7`
- Critical technical leakage: `0`
- Reported grounding_errors: `8`
- Timing: `total_ms=112680`, `avg_ms=10242.18`, `max_ms=35668`
- Decisión: `DO NOT INTEGRATE`
- Falla primaria: `EXACT relation requires quantity_value_raw`
- Nota histórica: la auditoría posterior confirmó que los `grounding_errors=8` reportados en esta baseline eran errores estructurales de contrato clasificados incorrectamente como grounding.

### Baseline 002

- Fecha: 2026-09-08
- Modelo: qwen3:8b
- Contrato: `scope-quantity-semantic-discovery-2026-09-08-002`
- Golden: `scope-quantity-golden-2026-09-08-001`
- SHA Golden: `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7`
- Resultados: `PASS=3`, `FAIL=2`, `REVIEW_REQUIRED=0`, `UNLABELED=0`, `INVALID=6`
- Discovery: `DISCOVERED=1`, `INVALID_OUTPUT=6`, `NO_QUANTITIES=3`, `REVIEW_REQUIRED=1`
- Cantidades: `expected=8`, `discovered=1`, `matched=0`, `missing=8`, `unexpected=1`
- Precision / recall: `0.0000 / 0.0000`
- Hard-negative: `3/3`
- Mixed-context: `0/7`
- Critical technical leakage: `0`
- Grounding errors: `0`
- Contract validation errors: `6`
- Timing: `total_ms=80248`, `avg_ms=7293.55`, `max_ms=24256`
- Decisión: `DO NOT INTEGRATE`
- Falla primaria: objetos `DISCOVERED` parciales, especialmente ausencia de `measure_kind`.
- Limitación diagnóstica: no se imprimió raw response para `sq_golden_case_007` con `REVIEW_REQUIRED` ni para `sq_golden_case_011` con `DISCOVERED/FAIL`, por lo que su salida exacta de modelo no pudo recuperarse de la corrida histórica.

### Baseline 003

- Fecha: 2026-09-08
- Modelo: qwen3:8b
- Contrato: `scope-quantity-semantic-discovery-2026-09-08-003`
- Golden: `scope-quantity-golden-2026-09-08-001`
- SHA Golden: `de2327ca868f8b72bf6dd80f50a568807b567f92c4106d65f913b7ce263339e7`
- Casos: `cases_total=11`
- Resultados: `PASS=11`, `FAIL=0`, `REVIEW_REQUIRED=0`, `UNLABELED=0`, `INVALID=0`
- Discovery: `DISCOVERED=8`, `NO_QUANTITIES=3`
- Cantidades: `expected=8`, `discovered=8`, `matched=8`, `missing=0`, `unexpected=0`
- Precision / recall: `1.0000 / 1.0000`
- Hard-negative: `3/3`
- Mixed-context: `7/7`
- Critical technical leakage: `0`
- Grounding errors: `0`
- Contract validation errors: `0`
- Invalid output: `0`
- Timing: `total_ms=179410`, `avg_ms=16303.82`, `max_ms=73075`
- Decisión: `ACCEPT BOUNDED`
- Interpretación: éxito de calibración sobre Golden v1, no generalización ciega out-of-sample.

## Cobertura y certificación

Aprobación de métrica de modelo no equivale a certificación de cobertura de categoría.
Si una categoría no aparece en Golden real aprobado, debe reportarse como `NOT CERTIFIED BY GOLDEN v1`.

## Procedimiento futuro de corrida real (placeholder)

1. Validar Golden (estructura + parent recovery + SHA + grounding).
2. Confirmar `PENDING=0`.
3. Ejecutar runner con modelo local explícito.
4. Revisar métricas y leakage.
5. Decisión arquitectónica humana.

En 06.4.4a no se ejecuta este procedimiento.

## Estado de cobertura de categoría

- COUNT: CERTIFIED BY GOLDEN v1
- PERSONNEL: NOT CERTIFIED BY GOLDEN v1
- DURATION: NOT CERTIFIED BY GOLDEN v1
- LENGTH: NOT CERTIFIED BY GOLDEN v1
- SERVICE: NOT CERTIFIED BY GOLDEN v1
- LOT: NOT CERTIFIED BY GOLDEN v1
- AREA: NOT CERTIFIED BY GOLDEN v1
- VOLUME: NOT CERTIFIED BY GOLDEN v1
- MASS: NOT CERTIFIED BY GOLDEN v1

## Contrato 003

`scope-quantity-semantic-discovery-2026-09-08-003` es una corrección pre-baseline-003 de prompt y JSON Schema estructurado.

Su propósito es reforzar la completitud de campos en `DISCOVERED` tanto por instrucción del prompt como por required keys en el schema.

No cambia el Golden, no cambia las gates, no introduce fallback determinista, no relaja validación y no cambia comportamiento de persistencia.

## Política de iteración final

Contract 003 es la última iteración planificada de corrección schema/prompt antes de una decisión arquitectónica sobre qwen3:8b.

Después de Baseline 003, no deben alterarse Golden ni gates ni continuar ajuste iterativo de prompt sin decisión explícita de arquitecto.

## Decisión arquitectónica vigente

qwen3:8b bajo Contract 003 se acepta como generador semántico acotado de candidatos de cantidad para ScopeDetail.

No es autoridad contractual ni autoridad autónoma de persistencia.

La arquitectura permanece: evidencia determinista persistida primero, suplementación semántica opcional y revisión humana para candidatos semánticos.

## Límite de calibración y certificación

Baseline 003 no demuestra exactitud general de producción.

Razones explícitas:

1. Golden v1 sólo certifica COUNT en datos reales aprobados.
2. Contract 003 se endureció usando fallas observadas en Baseline 001/002 sobre el mismo Golden.
3. Baseline 003 es éxito de calibración sobre ese Golden, no validación ciega out-of-sample.
4. La validación ciega queda diferida a MVP-06.V con Tender #002.
5. Los candidatos semánticos permanecen `review_required=True` y no se persisten automáticamente.

## Límite de throughput

La calibración funcional no certifica throughput de producción.

Con Baseline 003: `total_ms=179410`, `avg_ms=16303.82`, `max_ms=73075`.

La orquestación de invocación semántica debe seguir explícita e inyectada para evitar fan-out no controlado.

## Freeze

- Golden v1: FROZEN
- Contract 003: FROZEN
- Calibration gates: FROZEN

No se planifica Contract 004 antes de la validación ciega MVP-06.V y decisión explícita de arquitectura.
