"""Commercial decisions are an additive human overlay on canonical Scope evidence."""
from datetime import timezone
import hashlib
import json
from decimal import Decimal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import CommercialLine, CommercialLineRevision, TenderScopeDetail, TenderScopeQuantity, TenderDocument
from app.commercial_calculations import CommercialInputs, calculate
from app.scope_review import get_scope_review_item, ScopeReviewSourceBlocked
from app.workspace_flow import _source, quantity_read


class CommercialUpdate(CommercialInputs):
    expected_revision: int = Field(ge=1)
    expected_source_fingerprint: str = Field(min_length=64, max_length=64)


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    expected_source_fingerprint: str = Field(min_length=64, max_length=64)
    apply_calculated_price: bool = False
    replace_manual_price: bool = False


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _inputs(revision):
    return CommercialInputs.model_validate({key: getattr(revision, key) for key in CommercialInputs.model_fields})


def _context(db, tender_id, scope_id, values, *, prefetched=None):
    scope = prefetched[0] if prefetched is not None else db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.id == scope_id, TenderScopeDetail.tender_id == tender_id))
    warnings = []
    quantity = None
    snapshot = {'scope': None, 'quantities': [], 'selected_quantity_id': None, 'quote': None}
    if scope:
        try:
            review = get_scope_review_item(db, tender_id=tender_id, scope_detail_id=scope_id)
            current = review.current
            review_state = current.effective_status if current else 'SOURCE_BLOCKED'
            description = current.effective_description if current else scope.description
            if review_state not in ('CONFIRMED', 'CORRECTED', 'NOT_REQUIRED'):
                warnings.append('SCOPE_REVIEW_REQUIRED')
            review_fp = review.projection_fingerprint
        except (ScopeReviewSourceBlocked, FileNotFoundError):
            review_state, description, review_fp = 'SOURCE_BLOCKED', scope.description, None
            warnings.append('SCOPE_REVIEW_REQUIRED')
        source = _source(db, scope).model_dump(mode='json')
        if not source['available'] or review_state == 'SOURCE_BLOCKED':
            warnings.append('SOURCE_UNAVAILABLE')
        snapshot['scope'] = {'id': scope.id, 'tender_id': scope.tender_id, 'description': description,
                             'source': source, 'review_status': review_state, 'review_fingerprint': review_fp,
                             'semantic_fingerprint': scope.semantic_fingerprint}
        children = prefetched[1] if prefetched is not None else list(db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == scope.id,
                               TenderScopeQuantity.tender_id == tender_id).order_by(TenderScopeQuantity.id)))
        choices = [quantity_read(db, q, scope) for q in children]
        snapshot['quantities'] = [q.model_dump(mode='json') for q in choices]
        selected = None
        if values.quantity_id:
            selected = next((q for q in choices if q.id == values.quantity_id), None)
            if selected is None:
                other = db.get(TenderScopeQuantity, values.quantity_id)
                if other is not None:
                    raise HTTPException(409, 'QUANTITY_PARENT_MISMATCH')
                warnings.append('QUANTITY_SELECTION_STALE')
        elif len(choices) == 1:
            selected = choices[0]
        elif len(choices) > 1:
            warnings.append('QUANTITY_AMBIGUOUS')
        if selected:
            snapshot['selected_quantity_id'] = selected.id
            if selected.status != 'UNRESOLVED' and selected.relation == 'EXACT' and selected.quantity_value is not None and selected.quantity_value >= 0 and source['available'] and review_state != 'SOURCE_BLOCKED':
                quantity = selected.quantity_value
            if selected.status != 'NOT_REQUIRED':
                warnings.append('QUANTITY_REVIEW_REQUIRED')
    else:
        warnings.append('SCOPE_UNAVAILABLE')
    if values.quote_document_id:
        doc = db.get(TenderDocument, values.quote_document_id)
        if doc is None or doc.tender_id != tender_id:
            raise HTTPException(409, 'QUOTE_TENDER_MISMATCH')
        snapshot['quote'] = {'id': doc.id, 'revision': doc.revision_number, 'sha256': doc.sha256, 'filename': doc.original_filename}
    if values.cost_value_origin == 'CONFIRMED_QUOTE' and not (values.quote_document_id or values.quote_reference):
        warnings.append('QUOTE_SUPPORT_UNSPECIFIED')
    return snapshot, quantity, warnings


def _line(db, tender_id, scope_id, lock=False):
    stmt = select(CommercialLine).where(CommercialLine.tender_id == tender_id, CommercialLine.scope_id_at_creation == scope_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    line = db.scalar(stmt)
    if line is None:
        raise HTTPException(404, 'Commercial line not found')
    return line


def _latest(db, line):
    return db.scalar(select(CommercialLineRevision).where(CommercialLineRevision.line_id == line.id).order_by(CommercialLineRevision.revision.desc()).limit(1))


def _result(values, quantity, warnings, *, initialized=True, manual_price=True):
    result = calculate(values, quantity)
    result['warnings'] = list(dict.fromkeys(result['warnings'] + warnings))
    from app.commercial_readiness import complete_result
    return complete_result(values, result, initialized=initialized, manual_price=manual_price)


def _append(db, line, values, prior, action, method, price_origin, *, audit_metadata=None):
    snapshot, quantity, warnings = _context(db, line.tender_id, line.scope_detail_id, values)
    calculation = _result(values, quantity, warnings, manual_price=method == 'MANUAL')
    if audit_metadata is not None:
        calculation['bulk_operation'] = audit_metadata
    row = CommercialLineRevision(line_id=line.id, tender_id=line.tender_id, revision=prior.revision + 1 if prior else 1,
        **values.model_dump(), action=action, price_method=method, price_value_origin=price_origin,
        source_fingerprint=_fingerprint(snapshot), source_snapshot=snapshot,
        calculation_snapshot=calculation, calculation_version='commercial-v1')
    db.add(row)
    db.flush()
    return row


def read_commercial(db: Session, tender_id: str, scope_id: str):
    line = _line(db, tender_id, scope_id)
    row = _latest(db, line)
    values = _inputs(row)
    snapshot, quantity, warnings = _context(db, tender_id, line.scope_detail_id, values)
    fp = _fingerprint(snapshot)
    if fp != row.source_fingerprint:
        warnings.append('SOURCE_CONTEXT_CHANGED')
    result = _result(values, quantity, warnings, manual_price=row.price_method == 'MANUAL')
    if row.price_method == 'CALCULATED' and values.offered_unit_price != (Decimal(result['recommended_unit_price']) if result['recommended_unit_price'] is not None else None):
        result = _result(values, quantity, warnings + ['PRICE_CALCULATION_STALE'], manual_price=False)
    history = list(db.scalars(select(CommercialLineRevision).where(CommercialLineRevision.line_id == line.id).order_by(CommercialLineRevision.revision)))
    return {'id': line.id, 'tender_id': tender_id, 'scope_detail_id': line.scope_detail_id,
        'scope_id_at_creation': line.scope_id_at_creation, 'revision': row.revision,
        'created_at': line.created_at.astimezone(timezone.utc), 'updated_at': row.created_at.astimezone(timezone.utc), 'inputs': values.model_dump(mode='json'),
        'price_method': row.price_method, 'price_value_origin': row.price_value_origin,
        'source_fingerprint': fp, 'source': snapshot, 'summary': result,
        'history': [{'revision': r.revision, 'action': r.action, 'created_at': r.created_at.astimezone(timezone.utc),
                     'inputs': _inputs(r).model_dump(mode='json'), 'price_method': r.price_method,
                     'price_value_origin': r.price_value_origin, 'source_fingerprint': r.source_fingerprint,
                     'source_snapshot': r.source_snapshot, 'calculation': r.calculation_snapshot} for r in history]}


def create_commercial(db, tender_id, scope_id, values):
    scope = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.id == scope_id, TenderScopeDetail.tender_id == tender_id).with_for_update())
    if scope is None:
        raise HTTPException(404, 'Scope not found')
    if db.scalar(select(CommercialLine).where(CommercialLine.tender_id == tender_id, CommercialLine.scope_id_at_creation == scope_id)):
        raise HTTPException(409, 'COMMERCIAL_LINE_EXISTS')
    snapshot, _, _ = _context(db, tender_id, scope_id, values)
    line = CommercialLine(tender_id=tender_id, scope_detail_id=scope_id, scope_id_at_creation=scope_id, scope_snapshot=snapshot)
    db.add(line)
    db.flush()
    _append(db, line, values, None, 'CREATE', 'MANUAL' if values.offered_unit_price is not None else None,
            'MANUAL_INPUT' if values.offered_unit_price is not None else None)
    return read_commercial(db, tender_id, scope_id)


def _check(db, line, prior, expected_revision, expected_source):
    if line.scope_detail_id is None:
        raise HTTPException(409, 'SCOPE_UNAVAILABLE')
    snapshot, _, _ = _context(db, line.tender_id, line.scope_detail_id, _inputs(prior))
    if expected_revision != prior.revision or expected_source != _fingerprint(snapshot):
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_STALE')


def update_commercial(db, tender_id, scope_id, payload):
    line = _line(db, tender_id, scope_id, lock=True)
    prior = _latest(db, line)
    _check(db, line, prior, payload.expected_revision, payload.expected_source_fingerprint)
    changes = payload.model_dump(exclude_unset=True, exclude={'expected_revision', 'expected_source_fingerprint'})
    values = CommercialInputs.model_validate(_inputs(prior).model_dump() | changes)
    method, origin = prior.price_method, prior.price_value_origin
    if 'offered_unit_price' in changes:
        method = 'MANUAL' if values.offered_unit_price is not None else None
        origin = 'MANUAL_INPUT' if method else None
    snapshot, _, _ = _context(db, tender_id, scope_id, values)
    if values != _inputs(prior) or method != prior.price_method or _fingerprint(snapshot) != prior.source_fingerprint:
        _append(db, line, values, prior, 'UPDATE', method, origin)
    return read_commercial(db, tender_id, scope_id)


def calculate_commercial(db, tender_id, scope_id, payload):
    line = _line(db, tender_id, scope_id, lock=True)
    prior = _latest(db, line)
    _check(db, line, prior, payload.expected_revision, payload.expected_source_fingerprint)
    values = _inputs(prior)
    _, quantity, warnings = _context(db, tender_id, scope_id, values)
    result = _result(values, quantity, warnings, manual_price=prior.price_method == 'MANUAL')
    if not payload.apply_calculated_price:
        return read_commercial(db, tender_id, scope_id)
    if prior.price_method == 'MANUAL' and not payload.replace_manual_price:
        raise HTTPException(409, 'MANUAL_PRICE_PROTECTED')
    recommendation = result['recommended_unit_price']
    if recommendation is None:
        raise HTTPException(409, 'CALCULATION_UNRESOLVED')
    values = values.model_copy(update={'offered_unit_price': Decimal(recommendation)})
    _append(db, line, values, prior, 'APPLY_CALCULATION', 'CALCULATED', 'SYSTEM_ESTIMATE')
    return read_commercial(db, tender_id, scope_id)
