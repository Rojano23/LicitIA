# ADR 0017 — Source-bound Native ruled table relationships

Status: accepted and implemented (MVP-06.V.6d).

## Context

Production Native extraction persists page text and normalized generations, not
word/cell geometry. Delimited or labelled V.6b fixtures already supply stronger
relationships than this output. Text alone cannot prove a flattened table's rows.
The originals remain immutable and available locally. ADR 0015 requires a distinct
contract before actual geometry can support composite evidence.

## Decision

Add the bounded `native-table-relationships-v1` companion to canonical Native
evidence at Scope interpretation time. It reads the verified original PDF/page;
hash, size and production-normalized text must agree with the active generation.
PyMuPDF Native word boxes/block-line identities and `lines_strict` table cells
provide structural evidence without OCR, rendering, LLM or a database migration.
No font or semantic guess creates a cell. Unruled/merged/overlapping, straddling,
unaligned, absent or unsupported cells produce no relationship or explicit error.

Require distinct item, description, quantity and unit columns, numeric positive
integer item IDs, explicit numeric quantities, recognized units and non-question
descriptions. Optional brand/model columns reuse existing child contracts. A
numbered first column alone is insufficient. No cross-page header/owner inference;
each page must supply its own complete header and rows. Bounded limits apply to
text, words, tables, cells, blocks and fragments. A row remains review-required,
without confidence or contractual authority; it does not promote page structure.

Map extracted words monotonically to literal offsets in canonical normalized
text. A cell may contain several independent line fragments; field composition
and continuation are relationships, never a newly fabricated literal quotation.
Preserve original extraction order in fragment offsets and proven local cell
reading order in field refs. Use the existing StructuredEvidenceBlock, Scope
candidate, child ownership and immutable multispan manifest lifecycle.

The optional `native_table_proof` on a block records `NATIVE_RULED_TABLE_001`,
PyMuPDF version, page/table bounds, row index and actual header/value cell bounds
with fragment refs. Source identity already binds original hash, document/page,
revision, generation and text hash. Validation reopens the hash-verified original,
checks the engine version and regenerates the same relationships. A forged,
stale, missing or incompatible proof fails closed. No stored geometry is trusted
without replay. Originals and referenced generations remain required for backup.

Existing blocks omit the absent optional proof during serialization, preserving
their exact canonical bytes and content-addressed hashes. Existing v1 manifests
continue replaying the old text contract. New geometry-backed blocks replay the
Native companion. The compatible freeze003 versions map includes the bridge
policy; do not rewrite historical freezes or bump SQL/schema versions.

## Consequences and limits

No parallel semantic model, provider call or planner feedback is added. Native
geometry is retrieved lazily from the original, not persisted in SQL. Missing or
changed originals/engine prevent proof verification rather than silently falling
back. Extra deterministic PDF reads have bounded inputs; no new logging stream,
cache, retention policy or infrastructure is introduced.

The text-only grammar and `perception-sufficiency-v2` remain unchanged, including
OCR/Vision eligibility, profiles and budgets. Requirements/Requested Evidence,
general prose/reference/global-scope extraction and arbitrary specifications are
outside this slice. The bridge deliberately supports ruled rectangular tables
with known roles, not every PDF table. Unknown structure remains reviewable or
unrepresented. Real blind quality is not certified by synthetic tests.

Acceptance exercises generated PDFs through production import/extract/normalize,
IR, grounding, persistence and children, including repeated headers, multiline
cells, varying widths, negative TOC/questionnaire cases and forged proofs. This
ADR does not authorize a new blind attempt, commit or provider execution.
