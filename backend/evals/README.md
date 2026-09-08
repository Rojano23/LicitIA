# Semantic Golden Set Evaluation

## Purpose

The Semantic Golden Set provides a **human-owned** deterministic evaluation framework for semantic scope discovery.

This is NOT production model wiring. This is evaluation infrastructure for:
- Validating semantic discovery contract compliance
- Measuring provider recall and precision
- Identifying provider limitations (e.g., mixed-domain atomic decomposition)
- Calibrating human interpretation of edge cases

## Core Principle: Human Owns Truth

- Model inference is provider-neutral (`ScopeSemanticDiscoveryResult`)
- Golden truth is **always human-approved**
- REAL candidate fragments created in the initial MVP slice started as **PENDING**
- No REAL case was labeled APPROVED automatically
- Human review determined final expected obligations
- Synthetic TEST fixtures may contain APPROVED labels for unit testing

## Golden Case States

### PENDING
- REAL cases from tender evidence
- Used to plan future human labeling work
- Not scoreable as PASS/FAIL by evaluator
- Returns `UNLABELED` status

### APPROVED
- Human has validated expected obligations
- Case is scoreable
- Synthetic test cases use this state

## Evaluation Modes

### STRICT
- All expected obligations must be discovered
- No unexpected obligations allowed
- Broad predicted evidence (containing expected) is acceptable
- Narrow predicted evidence (contained by expected) is acceptable
- Mixed-domain predictions trigger `REVIEW_REQUIRED`

### NO_OBLIGATIONS
- Zero obligations must be discovered
- Used for clearly administrative/qualification-only sections
- False positives fail the case
- Exact match

### REVIEW_ONLY
- Always returns `REVIEW_REQUIRED` status
- Reserved for ambiguous contractual language
- Never produces automatic PASS/FAIL

## Evaluation Statuses

| Status | Meaning |
|--------|---------|
| PASS | All expected matched, no unexpected, deterministic confidence |
| FAIL | Expected missing, unexpected predicted, or provider error |
| REVIEW_REQUIRED | Mixed-domain indicator, ambiguous context, or explicit mode |
| UNLABELED | PENDING human_label_status; not yet scoreable |
| INVALID | Malformed Golden case or provider output |

## Provider Neutrality

The evaluator accepts any `ScopeSemanticDiscoveryResult`:
- Ollama (qwen3:8b reference model)
- Alternative LLM providers (future)
- Symbolic/rule-based providers (future)
- Human-override providers (future)

The provider name, version, and contract are preserved but do not affect evaluation logic.

## Evidence Matching

Evidence is matched on:
1. Domain (must match exactly)
2. Grounded containment (no embeddings, no similarity scoring):
   - **Exact match**: predicted excerpt == expected excerpt (after whitespace normalization)
   - **Predicted contains expected**: expected is substring of predicted
   - **Expected contains predicted**: predicted is substring of expected

Match priority:
1. Exact matches first
2. Containment matches second
3. Stable order tie-break

One-to-one matching:
- Each predicted obligation matches **at most one** expected obligation
- Each expected obligation matches **at most one** predicted obligation
- Prevents a broad prediction from falsely claiming multiple expected obligations

## Mixed-Domain Diagnostic

When a single predicted obligation's evidence overlaps/contains evidence from multiple expected obligations of **different domains**, it is flagged as a `mixed_domain_candidate`.

Example:
```
Expected 1: LOGISTICS_SITE → "MEDIOS DE TRANSPORTE"
Expected 2: TOOLS_EQUIPMENT → "RADIOS A PRUEBA DE EXPLOSION"

Predicted: LOGISTICS_SITE → "MEDIOS DE TRANSPORTE Y COMUNICACIÓN CON RADIOS A PRUEBA DE EXPLOSION"
```

This is a known limitation of single-pass atomic decomposition with large context windows. The diagnostic enables human inspection and calibration.

## Approval Workflow

To approve a PENDING case:

1. Review the `source_text` carefully
2. Inspect the source provenance (document_id, page, locator, source_method)
3. If adequate obligation is discovered:
   - Add `ExpectedObligation` entries with:
     - `domain` (must be in allowed list)
     - `evidence_excerpt` (must be exact substring of source_text)
     - optional: `review_required`, `quantity_raw`, `unit_raw`, `human_note`
4. Set `human_label_status` to `APPROVED`
5. Set `evaluation_mode` appropriately (STRICT, NO_OBLIGATIONS, REVIEW_ONLY)

If the fragment has no obligations:
- Set `evaluation_mode` to `NO_OBLIGATIONS`
- Leave `expected_obligations` empty
- Set `human_label_status` to `APPROVED`

## Quantities and Units

Quantity and unit fields are **diagnostic** in the Golden Set contract:
- Raw values only (no unit normalization in this MVP)
- Not used for obligation matching
- Preserved for future normalization work (06.4)
- A predicted obligation matches even if `quantity_raw` and `unit_raw` differ

## Current Reference Semantic Model

- **Model**: qwen3:8b
- **Provider contract**: scope-semantic-discovery-2026-09-08-004
- **Provider version**: backend/app/ollama_scope_semantic_provider.py
- **Status**: Calibrated; accepted as bounded candidate-generation assistant, rejected as autonomous contractual authority

The Golden Set itself is **model-independent**. Provider changes, model substitutions, and prompt tuning do not affect Golden case definitions.

## Semantic Golden v1 - Final State (Frozen)

- Golden set version: `semantic-scope-golden-2026-09-06-001`
- Total cases: `12`
- Human label status: `12 APPROVED`, `0 PENDING`
- Evaluation modes: `7 NO_OBLIGATIONS`, `5 STRICT`
- Expected positive obligations: `12`
- Positive domain distribution:
  - `PERSONNEL`: 5
  - `SSPA`: 4
  - `TECHNICAL`: 1
  - `SERVICE`: 1
  - `LOGISTICS_SITE`: 1

Golden v1 is frozen. Do not modify source text, locators, hashes, expected obligations, domains, human labels, or evaluation modes in this slice.

## Semantic Golden v1 - Calibration Decision

### Contract003

- Contract: `scope-semantic-discovery-2026-09-04-003`
- Model: `qwen3:8b`
- Golden: `semantic_scope_golden_v1.json`
- Cases: `12`
- PASS: `4`
- FAIL: `8`
- Expected obligations: `12`
- Discovered obligations: `11`
- Matched obligations: `0`
- Overall recall: `0%`
- Overall precision: `0%`

Observed issues:
- administrative/qualification false positives
- domain confusion
- under-extraction
- over-segmentation
- one INVALID_OUTPUT
- simple timeframe/location scope missed

Decision:
- REJECTED as autonomous semantic authority.

### Contract004

- Contract: `scope-semantic-discovery-2026-09-08-004`
- Model: `qwen3:8b`
- Golden: same frozen `semantic_scope_golden_v1.json`
- Cases: `12`
- PASS: `2`
- FAIL: `10`
- Expected obligations: `12`
- Discovered obligations: `15`
- Matched obligations: `5`
- Overall recall: `41.7%`
- Overall precision: `33.3%`
- Discovery statuses:
  - `DISCOVERED`: 9
  - `INVALID_OUTPUT`: 1
  - `NO_OBLIGATIONS`: 2

Observed improvements:
- positive semantic discovery improved
- three execution personnel obligations matched
- technical maintenance procedure correctly classified TECHNICAL
- physical execution location correctly classified LOGISTICS_SITE
- SSPA training obligation conceptually recognized even though exact Golden evidence-span matching did not count it as a match
- over-segmentation reduced in some cases

Observed remaining failures:
- execution/non-execution gate still unreliable
- administrative/qualification false positives remain
- OTHER still appeared on non-scope administrative text
- DELIVERABLE false positive occurred on procurement documentation
- SSPA/TECHNICAL confusion persists
- PERSONNEL qualification/domain confusion persists
- under-extraction persists
- one INVALID_OUTPUT remains
- timeframe obligation was still missed
- semantic precision and recall remain below MVP autonomous-authority gates

Operational observation:
- one contract004 Golden case showed a large latency outlier; do not treat that single run as final performance benchmark.

### Final model decision

qwen3:8b + contract004:
- ACCEPTED as bounded semantic candidate-generation assistant.
- REJECTED as autonomous final execution-scope authority.

No prompt005 will be created in MVP-06.3.4c.

Final operating model:

persisted evidence
  -> deterministic structural engines
  -> semantic discovery provider
  -> provider-neutral validation
  -> candidate semantic obligations
  -> automatic acceptance only where future deterministic confidence policy explicitly allows it OR REVIEW_REQUIRED where semantic ambiguity can affect contractual scope
  -> human confirmation/correction
  -> accepted structured scope truth

The LLM must not silently establish final contractual execution scope when evidence/classification remains ambiguous.

## Golden v1 Coverage Limitations

Golden v1 is an MVP calibration set, not a universal benchmark.

Current positive domains represented:
- `PERSONNEL`
- `SSPA`
- `TECHNICAL`
- `SERVICE`
- `LOGISTICS_SITE`

Not yet positively certified by Golden v1:
- `SUPPLY`
- `TOOLS_EQUIPMENT`
- `DELIVERABLE`
- `OTHER` as a valid execution-positive case

These are future Golden expansion targets.

## Limitations

### Known Qwen 3.1 8B Limitation
- Multi-domain clauses combining transportation/communication/explosion-proof radios are grouped as single LOGISTICS_SITE instead of splitting radios into TOOLS_EQUIPMENT
- Sufficient evidence is preserved; atomicity is the concern
- Acceptable for MVP because contractual content is traceable
- Mitigated by human review before final obligation approval

### Not Implemented
- Embedding-based similarity (determinism priority)
- External semantic services
- Real-time model calibration from Golden Set
- Automatic prompt tuning against Golden data
- Production persistence of Golden evaluation results

## Files

| File | Purpose |
|------|---------|
| `backend/app/scope_semantic_golden.py` | Contracts, validation, evaluation engine |
| `backend/tests/test_scope_semantic_golden.py` | Synthetic deterministic test suite |
| `backend/evals/semantic_scope_golden_v1.json` | REAL candidate corpus (PENDING only) |
| `backend/evals/README.md` | This file |
| `backend/scripts/run_scope_semantic_golden.py` | CLI for human evaluation (optional) |

## Testing

All tests use **synthetic** Golden cases. No real Ollama inference from test suite.

Coverage includes:
- PENDING → UNLABELED
- APPROVED STRICT exact match → PASS
- Missing expected obligations → FAIL
- Unexpected predicted obligations → FAIL
- NO_OBLIGATIONS correct/incorrect
- Evidence grounding validation
- Domain validation
- SHA256 validation
- Containment matching (broad, narrow)
- One-to-one matching constraint
- Mixed-domain diagnostic
- REVIEW_ONLY behavior
- Provider error handling
- Description variation tolerance
- Source method independence
- Quantity/unit diagnostic preservation

Run:
```bash
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test' \
python -m pytest -q tests/test_scope_semantic_golden.py
```

## Candidates

Golden v1 real cases are frozen APPROVED cases:
- Preserved from Golden Tender evidence
- Exact source locator (document, page, source_method, artifact key)
- SHA256-validated source text
- Human-approved expected obligations where evaluation mode is STRICT
- Candidate reason retained for audit context

Do not modify approved real cases in this slice.

## Calibration Execution Policy

Golden evaluation remains human-owned. Calibration can be rerun manually using:
```bash
python scripts/run_scope_semantic_golden.py \
  --golden evals/semantic_scope_golden_v1.json \
  --model qwen3:8b
```

Reruns are for diagnostics and regressions; they do not auto-modify frozen Golden truth.
