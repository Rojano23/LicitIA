# Technical Attribute Golden Calibration (MVP-06.3.5d)

## Scope

This calibration evaluates semantic technical-attribute discovery against a human-labeled Golden dataset.

It does not:
- persist TenderScopeAttribute rows;
- invoke scope-attribute materialization;
- change schema or migrations;
- expose API or frontend integration.

## Golden Assets

- Golden file: `evals/technical_attribute_golden_v1.json`
- Golden version: `technical-attribute-golden-2026-09-08-001`
- Known limitation: one parent `TenderScopeDetail` can contain multiple internal subcomponents; since `TenderScopeAttribute` is attached to the parent detail, subcomponent-specific properties with ambiguous ownership should be excluded from Golden truth until ownership is structurally resolvable.

## Validation Rules

The evaluator enforces:
- unique `case_id` values;
- unique `golden_attribute_id` values within each case;
- valid label status (`APPROVED` or `PENDING`);
- `STRICT` mode requires expected attributes;
- `NO_ATTRIBUTES` mode requires zero expected attributes;
- `source_text_sha256` integrity;
- basic locator format;
- expected evidence excerpt must be an exact contiguous span of `source_text`;
- expected value grounding to expected evidence;
- optional expected label/unit grounding;
- relation vocabulary constraints;
- parent `TenderScopeDetail` provenance recovery and alignment.

## Matching Policy

Strict matching is deterministic and interpretable:
- `attribute_name`: exact match;
- `value_raw`: whitespace/case-normalized exact or safe containment semantics;
- `evidence_excerpt`: both expected and discovered evidence must be grounded in source text and refer to the same span by normalized equality/containment;
- `relation`: required only when explicitly expected;
- `unit_raw`: required only when explicitly expected.

No embeddings, no LLM-as-judge, no fuzzy recovery logic.

## Suggested Initial Acceptance Gates

These are calibration targets, not evaluator hardcoding:
- `INVALID_OUTPUT = 0` (mandatory);
- hard negatives pass rate >= 80%;
- overall recall >= 70%;
- overall precision >= 70%;
- deterministic-known brand/model recovery >= 80% where present;
- critical leakage for quantity/duration/location hard negatives = 0.

## Integration Decision Framework

After manual model replay, select one architecture route:
- `A` deterministic-first + semantic fallback;
- `B` deterministic + semantic parallel candidate discovery;
- `C` semantic only for unsupported artifact types;
- `D` semantic disabled by default and manually invoked.

This decision is based on Golden metrics and diagnostics.
Production routing changes are intentionally deferred to a follow-up slice.

## Accepted Manual Calibration Baseline (Approved)

- model: `qwen3:8b`
- prompt/contract: `scope-attribute-semantic-discovery-2026-09-08-001`
- golden cases: `10`
- PASS: `8`
- FAIL: `2`
- INVALID: `0`
- expected attributes: `16`
- discovered: `13`
- matched: `12`
- precision: `0.9231`
- recall: `0.7500`
- hard negatives: `3/3`
- brand/model recovery: `12/14 = 0.8571`
- timing total: `172568 ms`
- timing average: `17253.40 ms`
- timing max: `41971 ms`

Calibration decision:

- `qwen3:8b` is accepted as a bounded semantic technical-attribute candidate generator.
- `qwen3:8b` is not an autonomous technical authority.
- All semantic discoveries remain `review_required=True`.

Known misses (no prompt tuning authorized):

- Case 5: `power_supply` was detected, but relation/unit and evidence granularity diverged from Golden (`RANGE` + `VCA`), and semantic output missed `brand` and `model`.
- Case 6: semantic output missed `protocol = ESB BUS`.

Architecture decision for production integration:

- `DETERMINISTIC-FIRST + SEMANTIC SUPPLEMENTATION`.
- No prompt tuning was performed after this accepted baseline.
- Semantic candidate persistence is deferred to `MVP-06.6 Human Scope Review`.

## Manual Calibration Command (User-run)

```bash
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev' \
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/run_scope_attribute_golden.py \
  --model <ollama-model-name> \
  --golden evals/technical_attribute_golden_v1.json
```

## Optional Candidate Extraction (Read-only)

```bash
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev' \
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/extract_scope_attribute_golden_candidates.py \
  --tender-id decd32ae-2c1f-4520-89bc-d845c986a7ba \
  --output evals/technical_attribute_golden_candidates.json
```

This helper is SELECT-only and does not execute any provider.
