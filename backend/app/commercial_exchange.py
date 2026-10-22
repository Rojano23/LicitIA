"""Staged spreadsheet reconciliation delegates every commercial write to M7-B."""
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePath
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi import HTTPException
from app.commercial_calculations import CommercialInputs
from app.commercial_matrix import BulkRequest, bulk_commercial, read_matrix
from app import commercial_workbook as workbook
from app.commercial_exchange_store import save, load


class ApplyExchange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: bool


def _target(row):
    return {'scope_id': row['scope_id'], 'expected_revision': row['revision'], 'expected_source_fingerprint': row['source_fingerprint']}


def export_commercial(db, tender_id, kind):
    matrix = read_matrix(db, tender_id)
    identity = str(uuid4())
    metadata = {'format_version': workbook.VERSION, 'tender_id': tender_id, 'export_id': identity,
                'export_timestamp': datetime.now(timezone.utc).isoformat(), 'application_identity': 'licitia-backend-0.1.0'}
    rows = [workbook.export_row(row) for row in matrix['rows']]
    data = workbook.write_workbook(rows, metadata, kind)
    baseline = {row['scope_id']: {'reference': workbook.reference_row(row), 'inputs': row['inputs'],
                                'target': _target(row), 'derived': {key: value for key, value in exported.items() if key in workbook.DERIVED}}
                for row, exported in zip(matrix['rows'], rows)}
    save('export', identity, {'tender_id': tender_id, 'metadata': metadata, 'rows': baseline})
    return identity, data


def _same_values(current, changes):
    validated = CommercialInputs.model_validate(current)
    changed = CommercialInputs.model_validate(current | changes)
    return all(getattr(validated, key) == getattr(changed, key) for key in changes)


def _batches(db, tender_id, plans, *, origin, evidence, stage_id, apply, replace, currency):
    results = {}
    for recalculate in [False, True]:
        group = [p for p in plans if p['recalculate'] == recalculate]
        for offset in range(0, len(group), 100):
            batch = group[offset:offset + 100]
            request = BulkRequest(operation_id=stage_id, targets=[p['target'] for p in batch],
                row_changes={p['target']['scope_id']: p['changes'] for p in batch}, input_origin=origin,
                import_evidence=evidence, apply=apply, recalculate=recalculate,
                replace_manual_price=replace, confirm_currency_change=currency)
            response = bulk_commercial(db, tender_id, request)
            results.update({out['scope_id']: out for out in response['outcomes']})
    return results


def stage_commercial(db, tender_id, filename, data, *, replace=False, currency=False):
    suffix = PurePath(filename or '').suffix.lower()
    if suffix not in {'.xlsx', '.csv'}:
        raise HTTPException(422, 'UNSUPPORTED_SPREADSHEET_FORMAT')
    kind = suffix[1:]
    metadata, imported = workbook.read_workbook(data, kind)
    if metadata.get('format_version') != workbook.VERSION or metadata.get('tender_id') != tender_id:
        raise HTTPException(422, 'SPREADSHEET_VERSION_OR_TENDER_MISMATCH')
    baseline = load('export', metadata.get('export_id'), tender_id)
    if any(metadata.get(key) != value for key, value in baseline['metadata'].items() if kind == 'xlsx' or key != 'application_identity'):
        raise HTTPException(422, 'SPREADSHEET_METADATA_MISMATCH')
    stage_id = str(uuid4())
    evidence = {'sha256': hashlib.sha256(data).hexdigest(), 'file_name': (filename or '').replace('\\', '/').rsplit('/', 1)[-1][:200],
                'format': kind, 'export_id': metadata['export_id'], 'stage_id': stage_id}
    origin = 'XLSX_IMPORT' if kind == 'xlsx' else 'CSV_IMPORT'
    current = {row['scope_id']: row for row in read_matrix(db, tender_id)['rows']}
    identities = [row['scope_id']['value'] for row in imported]
    duplicates = {key for key, count in Counter(identities).items() if count > 1}
    details = []; plans = []
    for position, raw in enumerate(imported, 1):
        identity = raw['scope_id']['value']
        detail = {'scope_id': identity, 'import_row': position, 'state': 'INVALID', 'recognized': identity in baseline['rows'], 'warnings': [], 'errors': [], 'diff': [], 'eligible': False, 'item_reference': baseline['rows'].get(identity, {}).get('reference', {}).get('item_reference', '')}
        details.append(detail)
        if identity in duplicates:
            detail.update(state='DUPLICATE_SCOPE', errors=['DUPLICATE_SCOPE'])
            continue
        try:
            UUID(identity)
        except (ValueError, TypeError):
            detail['errors'] = ['MALFORMED_SCOPE_ID']
            continue
        if identity not in baseline['rows'] or identity not in current:
            detail.update(state='UNKNOWN_SCOPE', errors=['UNKNOWN_OR_REMOVED_SCOPE'])
            continue
        before = baseline['rows'][identity]; live = current[identity]
        altered = [k for k, value in before['reference'].items() if raw[k]['value'] != value or raw[k]['type'] not in {'s', 'n', 'inlineStr'}]
        if altered:
            detail['reference_diff'] = [{'field': k, 'current': before['reference'][k], 'imported': raw[k]['value']} for k in altered]
            detail['errors'] = ['REFERENCE_FIELDS_MODIFIED']
            continue
        if any(raw[k]['value'] != before['derived'][k] or raw[k]['type'] == 'f' for k in workbook.DERIVED):
            detail['warnings'].append('DERIVED_VALUES_IGNORED')
        try:
            fields = {key: ('' if raw[key]['value'] == '' and before['inputs'][key] == '' else workbook.editable_value(key, raw[key])) for key in workbook.EDITABLE}
            values = CommercialInputs.model_validate(before['inputs'] | fields)
            base_values = CommercialInputs.model_validate(before['inputs'])
            changes = {key: values.model_dump(mode='json')[key] for key in workbook.EDITABLE if getattr(values, key) != getattr(base_values, key)}
        except (ValidationError, ValueError) as exc:
            detail['errors'] = ['INVALID_COMMERCIAL_INPUT']
            if isinstance(exc, ValidationError):
                detail['invalid_fields'] = ['.'.join(str(k) for k in e['loc']) for e in exc.errors()]
            continue
        if live['source_fingerprint'] != before['target']['expected_source_fingerprint']:
            detail.update(state='CONFLICT', errors=['SOURCE_CONTEXT_CHANGED'])
            continue
        if not changes or _same_values(live['inputs'], changes):
            detail.update(state='UNCHANGED')
            if live['revision'] != before['target']['expected_revision']:
                detail['warnings'].append('NEWER_REVISION_NO_WRITE')
            continue
        if live['revision'] != before['target']['expected_revision']:
            detail.update(state='CONFLICT', errors=['NEWER_COMMERCIAL_REVISION'])
            continue
        plan = {'target': _target(live), 'changes': changes,
                'recalculate': 'offered_unit_price' not in changes and values.calculation_mode == 'COST_FIRST'}
        plans.append(plan)
        detail.update(state='CHANGED')
    preview = _batches(db, tender_id, plans, origin=origin, evidence=evidence, stage_id=stage_id, apply=False, replace=replace, currency=currency)
    valid_plans = []
    for detail in details:
        outcome = preview.get(detail['scope_id'])
        if detail['state'] != 'CHANGED' or outcome is None:
            continue
        detail['warnings'].extend(outcome.get('warnings', []) + outcome.get('reasons', []))
        detail['price_outcome'] = outcome['price_outcome']
        if outcome['outcome'] == 'ELIGIBLE':
            detail['eligible'] = True
            proposed = outcome['proposed_inputs']
            live = current[detail['scope_id']]
            detail['diff'] = [{'field': k, 'current': live['inputs'][k], 'imported': raw_value,
                               'proposed': proposed[k]} for k in workbook.EDITABLE
                              if (raw_value := next(p['changes'] for p in plans if p['target']['scope_id'] == detail['scope_id']).get(k, live['inputs'][k])) != live['inputs'][k] or not _same_values(live['inputs'], {k: proposed[k]})]
            plan = next(p for p in plans if p['target']['scope_id'] == detail['scope_id'])
            valid_plans.append(plan | {'proposed': proposed})
        else:
            detail.update(state='CONFLICT', errors=outcome['reasons'])
    missing = sorted(set(baseline['rows']) - set(identities))
    details.extend({'scope_id': identity, 'import_row': None, 'state': 'MISSING_FROM_IMPORT', 'recognized': True,
                    'warnings': ['NOT_PROVIDED_NO_DELETE'], 'errors': [], 'diff': [], 'eligible': False} for identity in missing)
    response = {'stage_id': stage_id, 'export_id': metadata['export_id'], 'tender_id': tender_id, 'file_evidence': evidence,
                'origin': origin, 'applied': False, 'rows': details, 'counts': dict(Counter(r['state'] for r in details))}
    save('stage', stage_id, {'tender_id': tender_id, 'preview': response, 'plans': valid_plans,
                            'replace': replace, 'currency': currency})
    return response


def apply_commercial(db, tender_id, stage_id, confirm):
    if not confirm:
        raise HTTPException(422, 'IMPORT_CONFIRMATION_REQUIRED')
    stage = load('stage', stage_id, tender_id)
    preview = stage['preview']
    current = {row['scope_id']: row for row in read_matrix(db, tender_id)['rows']}
    plans = []; results = []
    for plan in stage['plans']:
        identity = plan['target']['scope_id']
        row = current.get(identity)
        if row is None:
            results.append({'scope_id': identity, 'outcome': 'CONFLICT', 'reasons': ['SCOPE_UNAVAILABLE']})
        elif _same_values(row['inputs'], {k: plan['proposed'][k] for k in plan['changes'] | ({'offered_unit_price': None} if plan['recalculate'] else {})}) and row['source_fingerprint'] == plan['target']['expected_source_fingerprint']:
            results.append({'scope_id': identity, 'outcome': 'UNCHANGED', 'reasons': ['ALREADY_EQUIVALENT']})
        else:
            plans.append(plan)
    outcomes = _batches(db, tender_id, plans, origin=preview['origin'], evidence=preview['file_evidence'], stage_id=stage_id,
                        apply=True, replace=stage['replace'], currency=stage['currency'])
    for value in outcomes.values():
        if value['outcome'] == 'STALE':
            value['outcome'] = 'CONFLICT'
        results.append(value)
    return {'stage_id': stage_id, 'applied': True, 'outcomes': results, 'counts': dict(Counter(r['outcome'] for r in results))}
