# Source Effect Golden v1 Frozen Review

## Dataset Status

- primary_dataset: evals/source_effect_golden_v1.json
- duplicate_robustness_dataset: evals/source_effect_duplicate_artifact_robustness_v1.json
- label_status: HUMAN_APPROVED
- dataset_status: FROZEN_LIMITED_COVERAGE
- integrity_sha256: 2adae84c2bbbb10633d635ba8e6f95926880e3702ca21a819949fb0d599d0747

## Primary Coverage Snapshot

- cases_total: 15
- positive_cases: 2
- expected_effects_total: 3
- category_counts: {"DESCRIPTIVE_NEGATIVE": 6, "HARD_NEGATIVE": 7, "REVIEW_REQUIRED": 2}
- expected_discovery_status_counts: {"NO_EFFECTS": 13, "REVIEW_REQUIRED": 2}

## Human Curation Decisions

- se_gc_001 promoted to REVIEW_REQUIRED positive with one expected AMENDS/PARTIAL effect at locator 'inciso i'.
- se_gc_011 promoted to REVIEW_REQUIRED positive with two expected PARTIAL effects (AMENDS at 'Apartado 3.1.5', CLARIFIES at 'Disposiciones Transitorias').
- se_gc_012 removed from primary and moved to duplicate robustness.
- se_gc_002 reclassified from HARD_NEGATIVE to DESCRIPTIVE_NEGATIVE.
- Canonical selections: 013 over 014, 015 over 016, 017 over 018.

## Duplicate Artifact Separation

- duplicate_cases_total: 4
- duplicate_case_ids: ["se_gc_012", "se_gc_014", "se_gc_016", "se_gc_018"]
- These cases are excluded from primary aggregate metrics by design.

## Limited Coverage Freeze

- certification: Primary golden is human-reviewed and frozen for curated cases only.
- certification: Source excerpts preserve immutable sha256 traceability from candidate pack.
- certification: Duplicate artifact alternates are intentionally excluded from primary metrics.
- gap: Coverage remains limited to currently persisted Tender #001 source-effect artifacts.
- gap: No claim is made for full recall over all possible source-effect language variants.
- gap: Additional positive MATERIALIZED examples are still missing in this frozen cut.
- gap_effect_types: ["REVOKES", "DEFERS", "SUSPENDS"]
- gap_effect_scopes: ["GLOBAL", "TEMPORAL"]
