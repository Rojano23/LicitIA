"""Read-only consumer projections over the canonical commercial matrix and audit."""
from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy import select
from app.commercial import _fingerprint, _line, _latest, _inputs
from app.commercial_matrix import read_matrix
from app.commercial_readiness import CommercialReadiness
from app.models import CommercialLineRevision


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ScopeCommercialReadiness(Contract):
    scope_id: str
    readiness: CommercialReadiness
    offered_price_present: bool
    currency: str | None
    cost_source_present: bool
    cost_source_type: str | None
    unresolved_cost: bool
    review_required: bool


class TenderCommercialReadiness(Contract):
    contract_version: Literal['commercial-readiness-v1'] = 'commercial-readiness-v1'
    tender_id: str
    status: Literal['READY', 'INCOMPLETE', 'REVIEW_REQUIRED']
    total_scope_items: int
    ready_count: int
    incomplete_count: int
    review_required_count: int
    warning_count: int
    missing_commercial_treatment_count: int
    items: list[ScopeCommercialReadiness]
    summary_by_currency: list[dict[str, JsonValue]]
    state_reference: str


class ProposalCommercialRow(Contract):
    scope_id: str
    item_reference: str | None
    description: str
    quantity: str
    unit: str | None
    offered_unit_price: str
    offered_total: str
    currency: str
    notes: str | None
    status: Literal['READY'] = 'READY'
    warnings: list[str]


class ProposalCommercialProjection(Contract):
    contract_version: Literal['commercial-proposal-v1'] = 'commercial-proposal-v1'
    tender_id: str
    state_reference: str
    rows: list[ProposalCommercialRow]
    excluded: list[ScopeCommercialReadiness]


def _item(row):
    state = row['summary']['readiness']
    return ScopeCommercialReadiness(scope_id=row['scope_id'], readiness=state,
        offered_price_present=row['inputs']['offered_unit_price'] is not None,
        currency=row['inputs']['currency'], cost_source_present=row['initialized'],
        cost_source_type=row['inputs']['cost_source_type'] if row['initialized'] else None,
        unresolved_cost=row['unresolved_cost'], review_required=any(r['severity'] == 'REVIEW' for r in state['reasons']))


def _state(matrix):
    return _fingerprint([{'scope_id': r['scope_id'], 'revision': r['revision'],
        'source_fingerprint': r['source_fingerprint'], 'inputs': r['inputs'],
        'summary': r['summary']} for r in matrix['rows']])


def tender_readiness(db, tender_id):
    matrix = read_matrix(db, tender_id)
    items = [_item(r) for r in matrix['rows']]
    return TenderCommercialReadiness(tender_id=tender_id, **matrix['commercial_readiness'],
        items=items, summary_by_currency=matrix['summary_by_currency'], state_reference=_state(matrix))


def scope_readiness(db, tender_id, scope_id):
    matrix = read_matrix(db, tender_id)
    row = next((r for r in matrix['rows'] if r['scope_id'] == scope_id), None)
    if row is None:
        raise HTTPException(404, 'Scope not found')
    return _item(row)


def proposal_projection(db, tender_id):
    matrix = read_matrix(db, tender_id)
    rows = []; excluded = []
    for row in matrix['rows']:
        item = _item(row)
        if not item.readiness.proposal_eligible:
            excluded.append(item)
            continue
        # Completeness uses the same canonical selected Quantity/context as calculations.
        quantity = next(q for q in row['source']['quantities'] if q['id'] == row['source']['selected_quantity_id'])
        rows.append(ProposalCommercialRow(scope_id=row['scope_id'], item_reference=row['item_reference'],
            description=row['description'], quantity=quantity['quantity_value'], unit=quantity['unit_raw'],
            offered_unit_price=row['inputs']['offered_unit_price'], offered_total=row['summary']['offered_total'],
            currency=row['inputs']['currency'], notes=row['inputs']['notes'], warnings=item.readiness.warnings))
    return ProposalCommercialProjection(tender_id=tender_id, state_reference=_state(matrix), rows=rows, excluded=excluded)


class AuditChange(Contract):
    field: str
    previous: JsonValue
    current: JsonValue


class CommercialAuditEvent(Contract):
    revision: int
    timestamp: datetime
    origin: Literal['UI', 'API', 'BULK', 'XLSX', 'CSV']
    action: str
    actor_label: str | None
    manual_price: bool
    offered_unit_price: str | None
    recommended_unit_price: str | None
    differs_from_recommendation: bool | None
    note: str | None
    changes: list[AuditChange]
    import_evidence: dict[str, JsonValue] | None


class CommercialAudit(Contract):
    contract_version: Literal['commercial-audit-v1'] = 'commercial-audit-v1'
    tender_id: str
    scope_id: str
    scope_available: bool
    current_revision: int
    current_inputs: dict[str, JsonValue]
    current_manual_price: bool
    events: list[CommercialAuditEvent]
    next_before_revision: int | None


def commercial_audit(db, tender_id, scope_id, *, limit=25, before_revision=None):
    if not 1 <= limit <= 100 or before_revision is not None and before_revision < 1:
        raise HTTPException(422, 'INVALID_AUDIT_PAGE')
    line = _line(db, tender_id, scope_id)
    current = _latest(db, line)
    query = select(CommercialLineRevision).where(CommercialLineRevision.line_id == line.id, CommercialLineRevision.tender_id == tender_id)
    if before_revision is not None:
        query = query.where(CommercialLineRevision.revision < before_revision)
    revisions = list(db.scalars(query.order_by(CommercialLineRevision.revision.desc()).limit(limit + 1)))
    events = []
    for index, revision in enumerate(revisions[:limit]):
        values = _inputs(revision).model_dump(mode='json')
        previous = _inputs(revisions[index + 1]).model_dump(mode='json') if index + 1 < len(revisions) else {}
        recommendation = revision.calculation_snapshot.get('recommended_unit_price')
        price = values['offered_unit_price']
        bulk = revision.calculation_snapshot.get('bulk_operation', {})
        # Applying a calculation retains the input origin historically; its action is API.
        origin = 'API' if revision.action == 'APPLY_CALCULATION' else 'XLSX' if revision.action == 'XLSX_IMPORT' else 'CSV' if revision.action == 'CSV_IMPORT' else 'BULK' if revision.action.startswith('BULK_') else revision.input_origin
        if origin not in {'UI', 'API', 'BULK', 'XLSX', 'CSV'}:
            origin = 'API'  # Scalar edits to an imported line are API actions, not another import.
        from decimal import Decimal
        events.append(CommercialAuditEvent(revision=revision.revision, timestamp=revision.created_at.astimezone(timezone.utc),
            origin=origin, action=revision.action, actor_label=revision.actor_label, manual_price=revision.price_method == 'MANUAL',
            offered_unit_price=price, recommended_unit_price=recommendation,
            differs_from_recommendation=Decimal(price) != Decimal(recommendation) if price is not None and recommendation is not None else None,
            note=revision.notes, changes=[AuditChange(field=k, previous=previous.get(k), current=v) for k,v in values.items() if previous.get(k) != v],
            import_evidence=bulk.get('import_evidence')))
    return CommercialAudit(tender_id=tender_id, scope_id=scope_id, scope_available=line.scope_detail_id is not None,
        current_revision=current.revision, current_inputs=_inputs(current).model_dump(mode='json'),
        current_manual_price=current.price_method == 'MANUAL', events=events,
        next_before_revision=events[-1].revision if len(revisions) > limit else None)
