# ADR 0018 — Camelot physical proposals proven by canonical Native evidence

Status: accepted by architect; implementation approved for commit.

## Decision and authority

Use camelot-py==2.0.0, lattice/combined, as the single physical table path for
eligible available Native digital PDF interpretation. Camelot proposes table
regions, cells and topology. It is not contractual text, identity or trust.
Native document/page/revision/generation, original hash, normalized text and exact
fragment offsets remain authoritative. No routing by tender, filename, equipment
or known page. No change to perception-sufficiency-v2, OCR/Vision eligibility,
providers/budgets or Requirements/Requested Evidence.

An existing header-shape probe bounds eligible interpretation work; it never
proves cells or items. The adapter verifies original hash/size, Native normalized
text generation and supported page space before parsing. Only unrotated pages
with matching MediaBox/CropBox and zero origin are supported in this contract;
others abstain. Camelot bottom-left boxes transform to Native top-left using
(x0, height-y1, x1, height-y0), without offsets or special tolerances.

Physical parsing runs in a local subprocess (35s parent deadline, 30s CPU budget),
with pdfium and no backend fallback, no OCR or neural extras. Original size128MiB,
proposal2MiB, tables32/cells4096, existing text/word/block/fragment limits apply.
A process-local LRU retains at most16 physical JSON proposals; source bytes/hash
and Native generation are checked on every use. The cache key includes original
path/hash/page/config/dependency versions; no disk cache, telemetry stream or
retention/GC system is added. A new process re-extracts physical proposals.

CamelotNativeProof/CAMELOT_NATIVE_TABLE_001 records a deterministic proposal
identity, source identity digest, engine/parser/config identity, runtime dependency
versions, real Native word boxes/offsets, cell indices/geometry, fragment refs and
proof hash. Full source identity lives in the existing block Source; its digest
binds every proposal. Detector cell text is bounded comparison/debug metadata,
never the source excerpt. Proof and proposal have canonical JSON SHA256s in
addition to the enclosing immutable multispan manifest hash.

Accept only complete nonoverlapping rectangular topology. Match each Native word
center to exactly one proposed cell, then verify literal ordered text modulo
whitespace equals the detector cell text. Font boxes can cross a rule without a
new tolerance; ambiguous ownership, unrepresented Native text, inconsistent
geometry and mismatched text abstain. Native line/block membership defines
independent literal spans; their field composition is not a fabricated quotation.
Do not infer cross-page headers or ownership.

Reuse the existing positive item/quantity/unit grammar and IR relationship builder.
Quantity/unit and brand/model columns remain provisional until an existing Scope
owns them; review_required remainsTrue and confidenceNone. Do not infer model or
arbitrary attributes from prose/part numbers inside a description. A number alone
is insufficient. TOC/questionnaire/section/broken layouts retain abstention.

## Replay, coexistence and compatibility

Extend only the optional runtime proof union; absent proofs serialize exactly as
before. No SQL schema/migration, original blobs or new semantic model. Validation
checks current Source/literals, both hashes, source/config/dependencies, then
regenerates the block and compares it exactly. Missing/stale/corrupt proof fails
closed. Existing manifests/backup lifecycle under provenance/structured-evidence-v1
remain authoritative; originals and referenced generations must accompany them.

Keep V6d implementation intact except factoring its unchanged positive-row builder.
New eligible Native materialization uses Camelot only, not detector consensus;
legacy text-only interpretation remains. Old NATIVE_RULED_TABLE_001 manifests replay
V6d specifically, independent of the new default. This prevents proof hash changes
and duplicate native detector proposals. Unsupported Camelot topology does not
trigger fallback OCR/Vision or an implicit V6d rerun.

Freeze003's existing extensible implementation_versions map gains Camelot proof
policy, full configuration hash and dependency identity. The serialization version
is unchanged. Historical attempts/freezes are never rewritten. No blind run, commit
or production certification is authorized by this ADR.
