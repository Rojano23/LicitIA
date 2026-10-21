"""Runtime perception coverage and interpretation are independent assessments.

Readable canonical text is permission to attempt interpretation, never a claim
of contractual completeness or semantic correctness. Explicit region/spatial
contracts cannot be discharged by unrelated page text.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import re

POLICY_VERSION = 'perception-sufficiency-v2'


@dataclass(frozen=True)
class PerceptionAssessment:
    state: Literal['SUFFICIENT','INSUFFICIENT','VISUAL_REQUIRED','UNAVAILABLE','UNKNOWN']
    reason: str
    source_method: str = 'NATIVE'


@dataclass(frozen=True)
class InterpretationAssessment:
    state: Literal['SUCCESS','UNRESOLVED','AMBIGUOUS','REJECTED','NOT_ATTEMPTED']
    reason: str


def readable_text(text: str) -> bool:
    """Positive lexical integrity/diversity, not a character-count threshold.

    Reject replacement/control corruption and repeated headings/boilerplate with
    little lexical information regardless of total length. Source scope and
    integrity must be checked by the canonical loader, separately from this gate.
    """
    words = re.findall(r'[^\W\d_]+',text,flags=re.UNICODE)
    letters = sum(len(w) for w in words)
    visible = sum(not c.isspace() for c in text)
    return (len({w.casefold() for w in words}) >= 4 and letters >= visible * .45
            and '\ufffd' not in text and not any(ord(c)<32 and c not in '\n\r\t' for c in text))


def assess_perception(text,request,*,supported=True,source_method='NATIVE',region_covered=False,blocks=()):
    def result(state,reason):
        return PerceptionAssessment(state,reason,source_method)
    if not supported:
        return result('UNAVAILABLE','UNSUPPORTED_NATIVE_CAPABILITY')
    if request.visual_relationships_required:
        return result('VISUAL_REQUIRED','EXPLICIT_SPATIAL_RELATIONSHIP_REQUIRED')
    if request.region_id and not region_covered:
        return result('INSUFFICIENT','REQUESTED_REGION_TEXT_NOT_COVERED')
    if request.required_excerpts:
        if all(a.strip() and a in text for a in request.required_excerpts):
            return result('SUFFICIENT','GROUNDED_TASK_EXCERPTS_PRESENT')
        return result('INSUFFICIENT','REQUIRED_TEXT_NOT_AVAILABLE')
    if request.task.value == 'TEXT' and text.strip():
        return result('UNKNOWN','TEXT_TASK_CONTRACT_REQUIRED')
    if not text.strip():
        return result('INSUFFICIENT','TEXT_NOT_AVAILABLE')
    # A verified IR block is additional positive support, never a prerequisite.
    # Unresolved owner does not erase its exact source fragments.
    if blocks:
        return result('SUFFICIENT','GROUNDED_STRUCTURED_FRAGMENTS_AVAILABLE')
    if readable_text(text):
        return result('SUFFICIENT','CANONICAL_TEXT_READABLE_FOR_TASK_ATTEMPT')
    return result('INSUFFICIENT','TEXTUAL_COVERAGE_NOT_ESTABLISHED')


def assess_interpretation(text,request,*,page_number,blocks=()):
    """Observe existing interpreters without changing grammar or materializing."""
    from app.native_scope_evidence import procurement_rows,explicit_fields
    from app.page_structure_resolver import structural_candidate_from_native_text
    if request.task.value == 'TEXT':
        return InterpretationAssessment('NOT_ATTEMPTED','TEXT_RECOVERY_TASK')
    if not text.strip():
        return InterpretationAssessment('NOT_ATTEMPTED','NO_TEXT_EVIDENCE')
    if blocks:
        if any(b.state == 'AMBIGUOUS' for b in blocks):
            return InterpretationAssessment('AMBIGUOUS','STRUCTURED_OWNER_OR_FIELD_REVIEW')
        if request.task.value == 'QUANTITIES':
            from app.scope_quantity_adapters import _unit_to_measure_kind
            pairs = [(b.field('quantity'),b.field('unit')) for b in blocks]
            if not any(q and u and re.fullmatch(r'\d+(?:\.\d+)?',q.value)
                       and _unit_to_measure_kind(u.value) for q,u in pairs):
                return InterpretationAssessment('UNRESOLVED','STRUCTURED_QUANTITY_PAIR_NOT_INTERPRETED')
        required = {'ATTRIBUTES':('brand','model')}.get(request.task.value)
        if required and not any(any(b.field(name) for name in required) for b in blocks):
            return InterpretationAssessment('UNRESOLVED','STRUCTURED_TASK_FIELD_NOT_INTERPRETED')
        return InterpretationAssessment('SUCCESS','STRUCTURED_EVIDENCE_RECONSTRUCTED')
    structure = structural_candidate_from_native_text(page_number=page_number,native_text=text)
    identity = structure.structural_quality == 'VALID' and not structure.page_state.review_required
    if request.task.value == 'STRUCTURE':
        return InterpretationAssessment('SUCCESS' if identity else 'UNRESOLVED',
            'STRUCTURE_INTERPRETED' if identity else 'STRUCTURE_INTERPRETATION_UNRESOLVED')
    rows = procurement_rows(text)
    for row in rows:
        if request.required_excerpts and not all(a.strip() and a in row.text for a in request.required_excerpts):
            continue
        try:
            fields = explicit_fields(row.text)
        except ValueError:
            return InterpretationAssessment('AMBIGUOUS','DUPLICATE_INTERPRETED_FIELD')
        if not identity:
            return InterpretationAssessment('AMBIGUOUS','DOMAIN_IDENTITY_REVIEW_NOT_OCR_GAP')
        if request.task.value == 'SCOPE':
            return InterpretationAssessment('SUCCESS','LEGACY_SCOPE_INTERPRETED')
        if request.task.value == 'ATTRIBUTES' and (fields.get('brand') or fields.get('model')):
            return InterpretationAssessment('SUCCESS','LEGACY_ATTRIBUTE_INTERPRETED')
        if request.task.value == 'QUANTITIES':
            from app.scope_quantity_adapters import _unit_to_measure_kind
            if re.fullmatch(r'\d+(?:\.\d+)?',fields.get('quantity','')) and _unit_to_measure_kind(fields.get('unit','')):
                return InterpretationAssessment('SUCCESS','LEGACY_QUANTITY_INTERPRETED')
    return InterpretationAssessment('UNRESOLVED','INTERPRETATION_UNRESOLVED_OR_UNSUPPORTED')


def reconstruct_for_assessment(source, text):
    """Report known interpretation limits; never recast them as source gaps."""
    from app.structured_evidence import reconstruct
    try:
        return reconstruct(source,text),None
    except ValueError as exc:
        if str(exc) not in {'STRUCTURED_TEXT_LIMIT','STRUCTURED_BLOCK_LIMIT','STRUCTURED_FRAGMENT_LIMIT'}:
            raise
        return (),InterpretationAssessment('REJECTED',str(exc))
