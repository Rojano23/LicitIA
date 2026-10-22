"""Tender working sheet and bounded human bulk actions over M7-A decisions."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, Context, localcontext, ROUND_HALF_UP
from typing import Literal
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import Tender, TenderScopeDetail, TenderScopeQuantity, CommercialLine, CommercialLineRevision
from app.commercial_calculations import CommercialInputs
from app.commercial import _context, _fingerprint, _inputs, _result, _append

SETTINGS = {'cost_source_type', 'currency', 'calculation_mode', 'calculation_basis', 'markup_percent',
            'target_margin_percent', 'reference_party_name', 'reference_party_reference', 'reference_party_note'}
EDITABLE = SETTINGS | {'cost_value_origin', 'unit_cost', 'offered_unit_price', 'notes'}
DEFAULTS = {'currency', 'calculation_mode', 'calculation_basis', 'markup_percent', 'target_margin_percent'}


class Target(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope_id: str = Field(min_length=1, max_length=36)
    expected_revision: int | None = Field(default=None, ge=1)
    expected_source_fingerprint: str = Field(min_length=64, max_length=64)


class BulkRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: UUID = Field(default_factory=uuid4)
    targets: list[Target] = Field(min_length=1, max_length=100)
    action: Literal['PATCH', 'MARKUP', 'MARGIN', 'RECALCULATE', 'COPY_SETTINGS', 'INITIALIZE'] = 'PATCH'
    changes: dict[str, JsonValue] = Field(default_factory=dict)
    defaults: dict[str, JsonValue] = Field(default_factory=dict)
    row_changes: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    copy_from: Target | None = None
    apply: bool = False
    recalculate: bool = False
    replace_manual_price: bool = False
    confirm_currency_change: bool = False
    input_origin: Literal['UI', 'API', 'XLSX_IMPORT', 'CSV_IMPORT'] = 'API'
    import_evidence: dict[str, JsonValue] | None = None

    @model_validator(mode='after')
    def bounded(self):
        if len({t.scope_id for t in self.targets}) != len(self.targets):
            raise ValueError('Duplicate Scope targets')
        if set(self.row_changes) - {t.scope_id for t in self.targets} or any(set(v) - EDITABLE for v in self.row_changes.values()):
            raise ValueError('Invalid per-row changes')
        if set(self.changes) - EDITABLE or set(self.defaults) - DEFAULTS:
            raise ValueError('Unsupported commercial fields')
        CommercialInputs.model_validate(self.defaults)
        if self.action == 'COPY_SETTINGS' and (self.copy_from is None or self.changes):
            raise ValueError('COPY_SETTINGS requires source and no explicit changes')
        if self.action == 'MARKUP' and set(self.changes) != {'markup_percent'}:
            raise ValueError('MARKUP requires only markup_percent')
        if self.action == 'MARGIN' and set(self.changes) != {'target_margin_percent'}:
            raise ValueError('MARGIN requires only target_margin_percent')
        if self.action in {'RECALCULATE', 'INITIALIZE'} and self.changes:
            raise ValueError('Action does not accept explicit changes')
        if self.action == 'PATCH' and not self.changes and not any(self.row_changes.values()):
            raise ValueError('PATCH requires changes')
        return self


def _scope(db, tender, scope, lock=False):
    query = select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender, TenderScopeDetail.id == scope)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    result = db.scalar(query)
    if result is None:
        raise HTTPException(404, 'SCOPE_UNAVAILABLE')
    return result


def _current(db, tender, scope, lock=False):
    query = select(CommercialLine).where(CommercialLine.tender_id == tender, CommercialLine.scope_id_at_creation == scope)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    line = db.scalar(query)
    prior = db.scalar(select(CommercialLineRevision).where(CommercialLineRevision.line_id == line.id)
                      .order_by(CommercialLineRevision.revision.desc()).limit(1)) if line else None
    return line, prior


def _expect(target, prior, snapshot):
    if target.expected_revision != (prior.revision if prior else None) or target.expected_source_fingerprint != _fingerprint(snapshot):
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_STALE')


def _row(scope, line, revision, snapshot, quantity, warnings):
    values = _inputs(revision) if revision else CommercialInputs()
    if revision and revision.source_fingerprint != _fingerprint(snapshot):
        warnings = warnings + ['SOURCE_CONTEXT_CHANGED']
    summary = _result(values, quantity, warnings)
    if revision and revision.price_method == 'CALCULATED' and values.offered_unit_price != (
            Decimal(summary['recommended_unit_price']) if summary['recommended_unit_price'] is not None else None):
        summary['warnings'].append('PRICE_CALCULATION_STALE')
        if summary['status'] == 'READY':
            summary['status'] = 'REVIEW_REQUIRED'
    return {'scope_id': scope.id, 'item_reference': scope.candidate_item_key,
            'description': snapshot['scope']['description'] if snapshot['scope'] else scope.description,
            'commercial_line_id': line.id if line else None, 'revision': revision.revision if revision else None,
            'source_fingerprint': _fingerprint(snapshot), 'initialized': line is not None,
            'source': snapshot, 'inputs': values.model_dump(mode='json'), 'summary': summary,
            'price_method': revision.price_method if revision else None,
            'price_value_origin': revision.price_value_origin if revision else None,
            'manual_price_protected': bool(revision and revision.price_method == 'MANUAL'),
            'commercial_complete': summary['status'] != 'INCOMPLETE',
            'warning_count': len(summary['warnings']), 'offered_price_status': 'MISSING' if values.offered_unit_price is None else revision.price_method,
            'unresolved_cost': values.unit_cost is None}


def currency_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['inputs']['currency'] or 'UNSPECIFIED'].append(row)
    result = []
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        for currency, items in sorted(groups.items()):
            group = {'currency': None if currency == 'UNSPECIFIED' else currency, 'line_count': len(items),
                     'status_counts': dict(Counter(r['summary']['status'] for r in items))}
            for key in ['total_cost', 'offered_total', 'profit']:
                amounts = [Decimal(r['summary'][key]) for r in items if r['summary'][key] is not None]
                group[key] = str(sum(amounts, Decimal('0.00'))) if amounts else None
                group[key + '_calculable_count'] = len(amounts)
                group[key + '_missing_count'] = len(items) - len(amounts)
            pairs = [r['summary'] for r in items if r['summary']['total_cost'] is not None and r['summary']['offered_total'] is not None]
            cost = sum((Decimal(p['total_cost']) for p in pairs), Decimal(0))
            price = sum((Decimal(p['offered_total']) for p in pairs), Decimal(0))
            group['paired_count'] = len(pairs)
            group['paired_markup_percent'] = str(((price-cost)/cost*100).quantize(Decimal('.00000001'))) if cost else None
            group['paired_margin_percent'] = str(((price-cost)/price*100).quantize(Decimal('.00000001'))) if price else None
            result.append(group)
    return result


def read_matrix(db, tender_id):
    if db.get(Tender, tender_id) is None:
        raise HTTPException(404, 'Tender not found')
    scopes = list(db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender_id)
                            .order_by(TenderScopeDetail.candidate_item_key, TenderScopeDetail.id)))
    children = defaultdict(list)
    for q in db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id == tender_id).order_by(TenderScopeQuantity.id)):
        children[q.scope_detail_id].append(q)
    lines = list(db.scalars(select(CommercialLine).where(CommercialLine.tender_id == tender_id)))
    by_scope = {line.scope_id_at_creation: line for line in lines}
    # PostgreSQL DISTINCT ON reads one current decision, never every audit revision.
    revisions = list(db.scalars(select(CommercialLineRevision).where(CommercialLineRevision.tender_id == tender_id)
                               .distinct(CommercialLineRevision.line_id).order_by(CommercialLineRevision.line_id, CommercialLineRevision.revision.desc())))
    latest = {r.line_id: r for r in revisions}
    rows = []
    for scope in scopes:
        line = by_scope.get(scope.id)
        revision = latest.get(line.id) if line else None
        context = _context(db, tender_id, scope.id, _inputs(revision) if revision else CommercialInputs(),
                           prefetched=(scope, children[scope.id]))
        rows.append(_row(scope, line, revision, *context))
    archived = [{'id': line.id, 'scope_id': line.scope_id_at_creation, 'warning': 'SCOPE_UNAVAILABLE'} for line in lines if line.scope_detail_id is None]
    return {'tender_id': tender_id, 'rows': rows, 'summary_by_currency': currency_summary(rows), 'archived_lines': archived}


def bulk_commercial(db, tender_id, request):
    if db.get(Tender, tender_id) is None:
        raise HTTPException(404, 'Tender not found')
    if request.apply:
        ids = {t.scope_id for t in request.targets}
        if request.copy_from:
            ids.add(request.copy_from.scope_id)
        # Stable lock order includes copy source; scope locks serialize absent-row creation.
        list(db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender_id,
             TenderScopeDetail.id.in_(ids)).order_by(TenderScopeDetail.id).with_for_update()))
        list(db.scalars(select(CommercialLine).where(CommercialLine.tender_id == tender_id,
             CommercialLine.scope_id_at_creation.in_(ids)).order_by(CommercialLine.id).with_for_update()))
    changes = request.changes.copy()
    copy_error = None
    if request.action == 'COPY_SETTINGS':
        try:
            _scope(db, tender_id, request.copy_from.scope_id)
            _, source = _current(db, tender_id, request.copy_from.scope_id)
            if source is None:
                raise HTTPException(409, 'COPY_SOURCE_UNINITIALIZED')
            values = _inputs(source)
            snapshot, _, _ = _context(db, tender_id, request.copy_from.scope_id, values)
            _expect(request.copy_from, source, snapshot)
            changes = {k: v for k, v in values.model_dump(mode='json').items() if k in SETTINGS}
        except HTTPException as exc:
            copy_error = str(exc.detail)
    if request.action in {'MARKUP', 'MARGIN'}:
        changes |= {'calculation_mode': 'COST_FIRST', 'calculation_basis': 'MARKUP' if request.action == 'MARKUP' else 'MARGIN'}
    outcomes = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for target in sorted(request.targets, key=lambda t: t.scope_id):
        outcome = {'scope_id': target.scope_id, 'outcome': 'SKIPPED', 'reasons': [], 'price_outcome': 'NOT_REQUESTED'}
        try:
            with db.begin_nested() if request.apply else db.no_autoflush:
                if copy_error:
                    raise HTTPException(409, 'COPY_SOURCE_' + copy_error)
                scope = _scope(db, tender_id, target.scope_id, lock=request.apply)
                line, prior = _current(db, tender_id, target.scope_id, lock=request.apply)
                old = _inputs(prior) if prior else CommercialInputs()
                old_snapshot, _, _ = _context(db, tender_id, scope.id, old)
                _expect(target, prior, old_snapshot)
                if request.action == 'INITIALIZE' and prior:
                    outcome['reasons'].append('ALREADY_INITIALIZED')
                    outcomes.append(outcome)
                    continue
                if request.action == 'RECALCULATE' and prior is None:
                    outcome['reasons'].append('UNINITIALIZED')
                    outcomes.append(outcome)
                    continue
                row_changes = request.row_changes.get(target.scope_id, {})
                effective_changes = row_changes | changes
                values = CommercialInputs.model_validate(old.model_dump() | (request.defaults if prior is None else {}) | effective_changes | {'input_origin': request.input_origin} | ({'actor_label': None} if request.import_evidence else {}))
                if old.currency != values.currency and (old.unit_cost is not None or old.offered_unit_price is not None) and not request.confirm_currency_change:
                    raise HTTPException(409, 'CURRENCY_CONFIRMATION_REQUIRED')
                snapshot, quantity, warnings = _context(db, tender_id, scope.id, values)
                method, origin = (prior.price_method, prior.price_value_origin) if prior else (None, None)
                if 'offered_unit_price' in effective_changes:
                    method = 'MANUAL' if values.offered_unit_price is not None else None
                    origin = 'MANUAL_INPUT' if method else None
                result = _result(values, quantity, warnings)
                if request.recalculate or request.action in {'MARKUP', 'MARGIN', 'RECALCULATE'}:
                    if method == 'MANUAL' and not request.replace_manual_price:
                        outcome['price_outcome'] = 'PROTECTED'
                        outcome['reasons'].append('MANUAL_PRICE_PROTECTED')
                    elif result['recommended_unit_price'] is None:
                        outcome['price_outcome'] = 'UNRESOLVED'
                        outcome['reasons'].append('CALCULATION_UNRESOLVED')
                    else:
                        values = values.model_copy(update={'offered_unit_price': Decimal(result['recommended_unit_price'])})
                        method, origin = 'CALCULATED', 'SYSTEM_ESTIMATE'
                        outcome['price_outcome'] = 'RECALCULATED'
                differs = values.model_dump(exclude={'input_origin'}) != old.model_dump(exclude={'input_origin'}) or (prior is not None and (method != prior.price_method or _fingerprint(snapshot) != prior.source_fingerprint))
                result = _result(values, quantity, warnings)
                outcome['warnings'] = result['warnings']
                outcome['proposed_inputs'] = values.model_dump(mode='json')
                if not differs:
                    outcome['reasons'].append('UNCHANGED')
                else:
                    outcome['outcome'] = 'UPDATED' if request.apply else 'ELIGIBLE'
                    if request.apply:
                        if line is None:
                            line = CommercialLine(tender_id=tender_id, scope_detail_id=scope.id, scope_id_at_creation=scope.id, scope_snapshot=snapshot)
                            db.add(line); db.flush()
                        fields = [k for k in CommercialInputs.model_fields if getattr(values, k) != getattr(old, k)]
                        audit = {'id': str(request.operation_id), 'origin': request.input_origin if request.import_evidence else 'WORKSPACE_BULK' if request.input_origin == 'UI' else 'API_BULK',
                                 'timestamp': timestamp, 'action': request.action, 'requested_scope_ids': [t.scope_id for t in request.targets],
                                 'changed_fields': fields, 'before': old.model_dump(mode='json'), 'after': values.model_dump(mode='json')}
                        if request.import_evidence is not None:
                            audit['import_evidence'] = request.import_evidence
                        action = request.input_origin if request.import_evidence else 'BULK_WORKSPACE' if request.input_origin == 'UI' else 'BULK_API'
                        revision = _append(db, line, values, prior, action, method, origin, audit_metadata=audit)
                        outcome['revision'] = revision.revision
        except ValidationError as exc:
            outcome.update(outcome='INVALID', reasons=['INVALID_INPUT'], validation_fields=['.'.join(str(k) for k in e['loc']) for e in exc.errors()])
        except HTTPException as exc:
            outcome.update(outcome='STALE' if str(exc.detail) == 'COMMERCIAL_CONTEXT_STALE' else 'SKIPPED', reasons=[str(exc.detail)])
        except IntegrityError:
            outcome.update(outcome='FAILED', reasons=['INTEGRITY_CONFLICT'])
        outcomes.append(outcome)
    return {'operation_id': str(request.operation_id), 'applied': request.apply, 'outcomes': outcomes,
            'counts': dict(Counter(o['outcome'] for o in outcomes))}
