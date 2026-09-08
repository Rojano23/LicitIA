# Scope Quantity Calibration (MVP-06.4.4a)

## Estado

HUMAN GOLDEN APPROVED AND FROZEN
REAL MODEL CALIBRATION NOT YET EXECUTED

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

- `scope-quantity-semantic-discovery-2026-09-08-001`
- No modificado en este slice.

## Modelo objetivo para calibración futura

- Baseline previsto para 06.4.4b: `qwen3:8b`
- En 06.4.4a no se ejecuta modelo real.

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

- COUNT: covered by Golden v1
- PERSONNEL: NOT CERTIFIED BY GOLDEN v1
- DURATION: NOT CERTIFIED BY GOLDEN v1
- LENGTH: NOT CERTIFIED BY GOLDEN v1
- SERVICE: NOT CERTIFIED BY GOLDEN v1
- LOT: NOT CERTIFIED BY GOLDEN v1
- AREA: NOT CERTIFIED BY GOLDEN v1
- VOLUME: NOT CERTIFIED BY GOLDEN v1
- MASS: NOT CERTIFIED BY GOLDEN v1
