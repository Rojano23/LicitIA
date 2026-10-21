# ADR 0016 — Separate perception sufficiency from interpretation outcome

Status: accepted (MVP-06.V.6c).

## Context

The prior planner used procurement_rows, explicit_fields and structural identity
as necessary conditions for Native sufficiency. A readable source rejected by
that grammar could become OCR_NEEDED. The Vision planner reused that test over
OCR; harness spatial construction and its textual re-evaluation inherited the
coupling. There is no direct query of persisted candidate/materialization counts;
the feedback was through interpretation-dependent sufficiency booleans.

## Decision

Use independent frozen runtime PerceptionAssessment and InterpretationAssessment.
Perception distinguishes SUFFICIENT, INSUFFICIENT, VISUAL_REQUIRED, UNKNOWN and
UNAVAILABLE. Interpretation distinguishes SUCCESS, UNRESOLVED, AMBIGUOUS,
REJECTED and NOT_ATTEMPTED. These are diagnostics, never contractual authority.

Positive textual coverage requires a validated canonical source in the requested
scope plus explicit grounded task excerpts or readable lexical evidence (diverse
alphabetic tokens, usable character composition, absence of replacement/control
corruption). Repetition/length alone does not qualify. Existing StructuredEvidenceBlock
fragments are an additional positive proof, never a mandatory grammar-success
condition. A missing/ambiguous owner does not erase its readable evidence.
Generic TEXT tasks without an excerpt contract retain UNKNOWN when text exists.
Explicit region requests cannot borrow Native page text as region coverage.

OCR eligibility follows a textual evidence gap and an eligible IMAGE source.
Interpretation outcome cannot establish that gap. Source integrity/normalization
failures fail closed; conflicting Native generations require review without OCR.
Existing receipt reuse/exhaustion and acquisition fingerprints remain intact:
the physical OCR acquisition is equivalent despite a new planning policy.

Vision requires an explicit spatial question, valid IMAGE binding and declared
visual reason. Readable OCR without parser success can satisfy a textual task;
its failure or conflicting values cannot invent visual need. Explicit spatial
questions retain their region binding through harness re-evaluation. Only proven
same-region table/header or explicitly labelled quantity/unit row edges can
discharge a supported item-layout question using OCR. Page text or unrelated region prose cannot substitute for those edges.
No new geometry, grammar or acquisition is introduced.

Expose both assessments and reason distributions through existing plan/decision
records and aggregate runtime metrics. Retain them with the run artifact lifecycle;
no new log stream, schema or persisted metrics model. The next first-pass report
can distinguish perception gaps from unresolved interpretation and avoidance.

Version the boundary as perception-sufficiency-v2 in plan signatures, Vision
source signatures and freeze implementation versions. Old plans fail freshness
checks. The frozen task-contract policy, engines/models/prompts, timeout/render
limits, OCR8 and Vision4/4/4 budgets, retries and execution policies are unchanged.
AVAILABLE_ONLY and HISTORICAL_SAFE still acquire nothing.

## Consequences

Readable evidence permits an interpretation attempt; it does not certify complete
coverage of every hidden visual obligation or real OCR quality. Explicit region
and spatial contracts remain necessary for those questions. No source names,
Tender-specific content, expected outputs or candidate counts determine planning.
No materialization or provider is invoked by assessments. V.6b grammar, ownership,
grounding and review remain authoritative and unchanged. SI21–SI23 are activated
with PS coverage; this ADR does not authorize a blind run.
