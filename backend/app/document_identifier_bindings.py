"""Explicit identifier bindings at the perception boundary, before legacy identity.

No provider execution. Only declared R.1 bindings and explicit labelled syntax
are compared; unlabeled numbers and provider metadata never become identities.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from app.critical_identifier_comparison import IdentifierKind as K, IdentifierComparison, compare_identifiers, identifier_observation, normalize_identifier
from app.document_intelligence import Capability, Quality, RoutingResult

# Labelled syntax is deliberately narrow. It is caution, not contractual truth.
_PATTERNS = (
    (K.ITEM_NUMBER, re.compile(r'\b(?i:item|partida)\s*[:#]?\s*(\d+(?:\.\d+)*)(?!\w)')),
    (K.PARTIDA, re.compile(r'\b(?i:partida)\s*[:#]?\s*(\d+(?:\.\d+)*)(?!\w)')),
    (K.EQUIPMENT_TAG, re.compile(r'\b(?i:tag)\s*[:#]?\s*([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+)')),
    (K.MODEL_IDENTIFIER, re.compile(r'\b(?i:modelo|model)\s*[:#]?\s*([A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*)')),
    (K.DOCUMENT_REFERENCE, re.compile(r'\b(?i:anexo|formato|documento|document)\s*[:#]?\s*([A-Z0-9]+(?:[-_.][A-Z0-9]+)*)(?!\w)')),
    (K.QUANTITY_BINDING_IDENTIFIER, re.compile(r'\b(\d+(?:[.,]\d+)?\s+(?:EA|SET|units|unidades|piezas))\b')),
)


def page_identifier_comparisons(*results: RoutingResult) -> tuple[IdentifierComparison, ...]:
    grouped = defaultdict(list)
    # A page with one explicit owner per observation admits a single-owner
    # boundary comparison. Multi-owner pages require the same labelled context;
    # row order alone is never treated as correspondence.
    sources = tuple(source for result in results for source in result.candidates)
    single_owner = all(len(set(m.group(1) for m in _PATTERNS[0][1].finditer(s.text))) <= 1
                       for s in sources if s.lineage == 'ACTIVE' and s.quality not in {Quality.FAILED,Quality.UNAVAILABLE})
    for source in sources:
        if source.quality in {Quality.FAILED,Quality.UNAVAILABLE}:
            continue
        used = set()
        automatic = defaultdict(list)
        for declared in source.critical_identifiers:
            prefix = declared.binding_key.split(':',1)[0]
            kind = K(prefix) if prefix in K._value2member_map_ else K.OTHER_CRITICAL_IDENTIFIER
            key = (kind, declared.binding_key)
            grouped[key].append(identifier_observation(kind=kind,binding_key=declared.binding_key,
                raw_value=declared.value,excerpt=declared.excerpt,source=source))
            used.add(key)
        for line in source.text.splitlines():
            matches = [(kind, match) for kind,pattern in _PATTERNS for match in pattern.finditer(line)]
            # Grounded context after replacing only recognised identifier spans.
            context = line
            for start,end in sorted({m.span(1) for _,m in matches}, reverse=True):
                context = context[:start] + '<identifier>' + context[end:]
            context_key = hashlib.sha256(normalize_identifier(context).encode()).hexdigest()
            for kind,match in matches:
                binding = f'{kind.value}:' + ('single-owner' if single_owner and kind in {K.ITEM_NUMBER,K.PARTIDA} else context_key)
                key = (kind,binding)
                if key not in used:
                    automatic[key].append((match.group(1),line))
        for (kind,binding),entries in automatic.items():
            values = {value for value,_ in entries}
            for value in sorted(values):
                # An ambiguous repeated template cannot align by row order.
                # Each literal stays auditable without selecting the first row.
                key_binding = binding if len(values) == 1 else binding + ":unproven:" + hashlib.sha256(value.encode()).hexdigest()
                excerpt = next(line for raw,line in entries if raw == value)
                grouped[(kind,key_binding)].append(identifier_observation(kind=kind,binding_key=key_binding,
                    raw_value=value,excerpt=excerpt,source=source))
    return tuple(compare_identifiers(kind=kind,binding_key=binding,observations=tuple(observations))
        for (kind,binding),observations in sorted(grouped.items(),key=lambda pair:(pair[0][0].value,pair[0][1])))


def review_comparisons(comparisons: tuple[IdentifierComparison,...]) -> tuple[IdentifierComparison,...]:
    reliable = {(o.source.source_artifact_key,o.source.generation_id,o.source.capability)
        for c in comparisons for o in c.observations
        if o.source.lineage == 'ACTIVE' and o.source.quality == Quality.RELIABLE}
    return tuple(c for c in comparisons if c.status == 'CONFLICT' or (
        c.status == 'INSUFFICIENT_EVIDENCE' and ':unproven:' in c.binding_key and len(reliable) > 1
        and any(o.source.lineage == 'ACTIVE' and o.source.quality == Quality.RELIABLE for o in c.observations)))


def affected_comparisons(comparisons: tuple[IdentifierComparison,...], excerpt: str) -> tuple[IdentifierComparison,...]:
    text = normalize_identifier(excerpt)
    return tuple(c for c in review_comparisons(comparisons) if any(
        normalize_identifier(o.excerpt) in text or text in normalize_identifier(o.excerpt)
        for o in c.observations if o.source.lineage == 'ACTIVE'))


def transcription_requires_review(result: RoutingResult, excerpt: str) -> bool:
    if result.status == 'RESOLVED':
        return False
    active = tuple(s for s in result.candidates if s.lineage == 'ACTIVE'
                   and s.quality not in {Quality.FAILED,Quality.UNAVAILABLE})
    text = normalize_identifier(excerpt)
    # Only an independently agreed exact fragment can escape a page-wide
    # wording conflict. Uncertified perceptions remain review-required.
    return not (active and result.conflicts and all(c.kind in {'TEXTUAL','IDENTIFIER'} for c in result.conflicts)
        and all(s.quality == Quality.RELIABLE and text in normalize_identifier(s.text) for s in active))


def guard_structure(result: RoutingResult, comparisons: tuple[IdentifierComparison,...]) -> RoutingResult:
    owner_kinds = {K.ITEM_NUMBER,K.PARTIDA,K.STRUCTURAL_GROUP_IDENTIFIER}
    if any(c.kind in owner_kinds for c in review_comparisons(comparisons)):
        return RoutingResult(page=result.page,capability=Capability.STRUCTURE,status='REVIEW_REQUIRED',
            candidates=result.candidates,conflicts=result.conflicts,
            diagnostics=tuple(sorted(set(result.diagnostics + ('CRITICAL_IDENTIFIER_CONFLICT',)))))
    return result


def explicit_identifier_values(text: str) -> frozenset[tuple[str,str]]:
    """Protect grounded candidate alternatives from prose similarity pruning."""
    return frozenset((kind.value,normalize_identifier(match.group(1)))
        for kind,pattern in _PATTERNS for match in pattern.finditer(text))
