"""One pure commercial completeness policy, independent of transport and persistence."""
from typing import Literal
from pydantic import BaseModel, ConfigDict

CommercialStatus = Literal['READY', 'INCOMPLETE', 'REVIEW_REQUIRED']


class ReadinessReason(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str
    severity: Literal['BLOCKER', 'REVIEW', 'WARNING']


class CommercialReadiness(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: CommercialStatus
    reasons: list[ReadinessReason]
    warnings: list[str]
    proposal_eligible: bool


BLOCKERS = {'MISSING_COMMERCIAL_LINE', 'MISSING_OFFERED_PRICE', 'MISSING_CURRENCY', 'MISSING_CANONICAL_QUANTITY'}
CALCULATION = {'INVALID_MARKUP', 'INVALID_MARGIN', 'MISSING_CALCULATION_BASIS', 'CALCULATION_OUT_OF_RANGE'}
ADVISORIES = {'PRICE_BELOW_COST', 'COST_UNRESOLVED', 'ZERO_PRICE', 'ZERO_COST', 'QUOTE_SUPPORT_UNSPECIFIED', 'COST_SOURCE_REFERENCE_MISSING'}


def complete_result(values, result, *, initialized=True, manual_price=True):
    """Enrich an existing calculation, never change monetary values or evidence."""
    codes = list(result['warnings'])
    if not initialized:
        codes.append('MISSING_COMMERCIAL_LINE')
    if values.cost_source_type == 'SUPPLIER_QUOTE' and not any([
        values.quote_document_id, values.quote_reference, values.reference_party_reference,
    ]):
        codes.append('COST_SOURCE_REFERENCE_MISSING')
    codes = list(dict.fromkeys(codes))
    reasons = []
    for code in codes:
        if code in BLOCKERS:
            severity = 'BLOCKER'
        elif code == 'COST_UNRESOLVED' and values.calculation_mode == 'COST_FIRST' and not manual_price:
            severity = 'BLOCKER'
        elif code in CALCULATION:
            severity = 'WARNING' if manual_price and values.offered_unit_price is not None else 'BLOCKER'
        elif code in ADVISORIES:
            severity = 'WARNING'
        else:
            # Unknown context warnings fail closed rather than become silent eligibility.
            severity = 'REVIEW'
        reasons.append(ReadinessReason(code=code, severity=severity))
    status = 'INCOMPLETE' if any(r.severity == 'BLOCKER' for r in reasons) else 'REVIEW_REQUIRED' if any(r.severity == 'REVIEW' for r in reasons) else 'READY'
    readiness = CommercialReadiness(status=status, reasons=reasons,
        warnings=[r.code for r in reasons if r.severity == 'WARNING'], proposal_eligible=status == 'READY')
    return result | {'status': status, 'warnings': codes, 'readiness': readiness.model_dump(mode='json')}


def readiness_counts(rows):
    states = [r['summary']['readiness'] for r in rows]
    counts = {status: sum(s['status'] == status for s in states) for status in ['READY', 'INCOMPLETE', 'REVIEW_REQUIRED']}
    return {'status': 'INCOMPLETE' if not rows or counts['INCOMPLETE'] else 'REVIEW_REQUIRED' if counts['REVIEW_REQUIRED'] else 'READY',
        'total_scope_items': len(rows), 'ready_count': counts['READY'], 'incomplete_count': counts['INCOMPLETE'],
        'review_required_count': counts['REVIEW_REQUIRED'], 'warning_count': sum(len(s['warnings']) for s in states),
        'missing_commercial_treatment_count': sum(not r['initialized'] for r in rows)}
