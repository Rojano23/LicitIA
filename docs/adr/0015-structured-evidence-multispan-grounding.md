# ADR 0015 — Structured evidence and immutable multispan grounding

Status: implemented proposal for architect review (MVP-06.V.6b).

## Context

A single literal row cannot express separately grounded item, header, description,
quantity, unit and specification fragments. Legacy Native/OCR row parsing also
feeds the perception planner; changing it would combine V.6b with V.6c.

## Decision

Use a frozen runtime StructuredEvidenceBlock, one bounded acquisition-free
interpreter, and STRUCTURED_EVIDENCE_001 manifests. Keep legacy grammar and
planner behavior unchanged. Deterministic interpretation handles explicitly
labelled procurement blocks, indented description continuations and delimited
tables with unique item/description/quantity/unit headers. It requires a positive
procurement action for labelled blocks. Tables require an explicit item column,
nonempty description and linked numeric quantity/recognized unit; descriptions
without a procurement verb remain domain OTHER/review. Numbers/proximity alone
never establish a row. Blank lines,
unlabelled prose and page boundaries end the relationship; unsupported layout
is left unresolved. No word geometry is synthesized and no extraction is run.

Every field references exact fragments in a declared offset space. OCR offsets
refer to its validated NormalizedContent, not raw OCR text. Existing Vision detail
raw lines may supply ordered text; structure-only output cannot supply detail.
Native, OCR and Vision retain their genuine artifact/generation identities.

An ITEM proposal with a proven local row anchor remains REVIEW_REQUIRED without
confidence; this is a reviewable local binding, never a TRUSTED page structure or
continuity resolution. Critical identifier disagreements still remove its owner.
Legacy guards are unchanged. Ambiguous fields stay provisional in the block;
canonical children still require a ScopeDetail with a valid owner.

Store canonical JSON in the canonical data root under
provenance/structured-evidence-v1/<sha256>.json. Bound each manifest to 2 MiB,
64 source blocks, 128 fragments/block, 256 blocks/page and 500,000 text characters/source.
Publish an fsynced complete temporary file with an atomic exclusive hard link;
never overwrite an existing hash. Locators contain page, revision, generation,
method and the manifest SHA (under the existing 512-character limit), rather
than arbitrary filesystem paths. Representative excerpts are literal fragments,
not concatenated field displays. Resolvers re-enumerate active sources, check
hashes/generations and replay deterministic relationship validation. Missing,
stale or corrupt proof fails closed with no legacy fallback.

Exact item/occurrence/description grounding identifies comparable composite
facts independently of capability when their source scopes are comparable. Full-page
and region observations do not share an occurrence by assumption; unknown-scope
observations remain separate. Disagreeing values preserve proofs and remove
ownership for review. Added corroboration can update the proof reference without
replacing the same primary generation, increasing confidence or overwriting human
authority. Real primary generation/meaning changes use existing replacement and
review invalidation. Legacy scope-logical-v2 remains unchanged; the new contract
uses structured-logical-v1. Freeze versions include the interpreter/manifest.

## Lifecycle and limitations

Manifests are durable derived provenance: back up/export the entire provenance
subtree together with DB and source generations. No automatic GC, reset, deletion
or overwrite is introduced. Orphans after DB rollback are safe and retained;
removal needs an explicit audited reference-aware administrative operation.
No SQL multi-source joins or cross-store transactional guarantee is claimed.
The file must exist before a DB reference is persisted. Source generations and
referenced manifests must remain available for independent verification.

Cross-page adjacency is deliberately unsupported without an explicit canonical
continuity proof; do not carry headers or owners across pages. Actual word/cell
geometry requires a separate source-generation contract. Unsupported prose or
layout is not a reason to invent a fact. Planner sufficiency (SI21–SI23) belongs
to V.6c, explicitly deferred by the user. Providers, prompts, budgets, schemas,
Requirements and Requested Evidence are outside this decision.
