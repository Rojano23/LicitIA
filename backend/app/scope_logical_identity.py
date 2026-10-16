"""Capability-independent exact-grounding identity, not semantic similarity."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
import hashlib
import json
import re
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app.scope_details import ScopeDetailCandidate


class ScopeLogicalEvidence(NamedTuple):
    fingerprint: str
    source_artifact_keys: tuple[str, ...]
    conflict: bool

SCOPE_IDENTITY_POLICY = 'scope-logical-v2'


def logical_key(candidate: ScopeDetailCandidate) -> tuple:
    block = getattr(candidate, 'structured_block', None)
    if block is not None:
        from app.structured_evidence_grounding import fact_key
        return ('structured-logical-v1', candidate.tender_id, candidate.source_document_id,
                candidate.document_page_id, fact_key(block))
    # Whitespace only; preserve case, numeric spelling, units and all identifiers.
    excerpt = ' '.join(candidate.source_excerpt.split())
    occurrence = next((t for t in candidate.source_locator.split('|') if t.startswith('occurrence:')), 'occurrence:0')
    explicit = re.search(r'(?im)^[ \t]*(?:PARTIDA|ITEM|I[TÍ]EM|CONCEPTO|NO\.?)[ \t]*:?[ \t]*([A-Z]?[- ]?\d+(?:\.\d+)*)\b', candidate.source_excerpt)
    owner = explicit.group(1) if explicit else candidate.candidate_item_key or candidate.tender_item_id or candidate.scope_segment_id or ''
    return (SCOPE_IDENTITY_POLICY, owner, candidate.tender_id, candidate.source_document_id,
            candidate.document_page_id, candidate.domain, candidate.detail_type or '', excerpt, occurrence)


def logical_fingerprint(candidate: ScopeDetailCandidate) -> str:
    payload = (logical_key(candidate), candidate.description, candidate.normalized_label,
               candidate.applicability, candidate.candidate_item_key, candidate.tender_item_id,
               candidate.quantity_raw, candidate.unit_raw, tuple(sorted(getattr(candidate, 'attribute_bindings', ()))))
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def reconcile_candidates(candidates, existing=()):
    """One selected representation per exact source-backed occurrence.

    All contributing artifact keys are returned for audit. Perceptions remain
    immutable. Disagreement never promotes review or replaces a human decision.
    """
    groups = defaultdict(list)
    occurrences = defaultdict(int)
    for candidate in candidates:
        if getattr(candidate, 'structured_block', None) is not None:
            groups[logical_key(candidate)].append(candidate)
            continue
        base = (candidate.source_artifact_key, logical_key(candidate)[:-1])
        index = occurrences[base]
        occurrences[base] += 1
        locator = re.sub(r'\|occurrence:\d+', '', candidate.source_locator) + f'|occurrence:{index}'
        candidate = replace(candidate, source_locator=locator)
        groups[logical_key(candidate)].append(candidate)
    old_sources = {r.semantic_fingerprint: r.source_artifact_key for r in existing}
    selected, evidence = [], []
    for _, group in sorted(groups.items()):
        # Review/quality precede stable representation retention. No confidence boost.
        group.sort(key=lambda c: (c.review_required, old_sources.get(logical_fingerprint(c)) != c.source_artifact_key,
                                  c.source_artifact_key))
        chosen = group[0]
        owners = {(c.candidate_item_key, c.tender_item_id) for c in group if c.candidate_item_key or c.tender_item_id}
        quantities = {c.quantity_raw for c in group if c.quantity_raw is not None}
        units = {c.unit_raw for c in group if c.unit_raw is not None}
        attributes = defaultdict(set)
        for candidate in group:
            for name, value in getattr(candidate, 'attribute_bindings', ()):
                attributes[name].add(value)
        conflict = (len(owners) > 1 or len(quantities) > 1 or len(units) > 1
                    or any(len(values) > 1 for values in attributes.values()))
        if conflict:
            chosen = replace(chosen, review_required=True, applicability='UNRESOLVED',
                             candidate_item_key=None, scope_segment_id=None, tender_item_id=None)
        if getattr(chosen, 'structured_block', None) is not None:
            from app.structured_evidence_grounding import merge_proofs
            chosen = merge_proofs(chosen, group)
        selected.append(chosen)
        evidence.append(ScopeLogicalEvidence(logical_fingerprint(chosen), tuple(sorted({c.source_artifact_key for c in group})), conflict))
    return tuple(selected), tuple(evidence)
