"""Deterministic snapshot composition; human overlays never modify canonical sources."""
from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import Field, model_validator
from app.models import ProposalComposition
from app.proposal_readiness import Contract, digest
from app import proposal_versions as versions

CONTRACT = 'proposal-composition-v1'
SECTIONS = (*versions.SECTION_TYPES[:5], 'CLARIFICATIONS', 'ANNEX_REFERENCES', 'NOTES')
Status = Literal['PENDING', 'COMPLY', 'PARTIAL', 'NOT_APPLICABLE', 'EXCEPTION', 'REVIEW_REQUIRED', 'PROVIDED']


class Response(Contract):
    status: Status = 'PENDING'
    text: str = Field(default='', max_length=8000)
    offered_description: str = Field(default='', max_length=8000)
    comment: str = Field(default='', max_length=4000)
    clarification: str = Field(default='', max_length=4000)
    note: str = Field(default='', max_length=4000)
    document_id: UUID | None = None
    external_reference: str = Field(default='', max_length=1000)
    included: bool = True
    reason: str = Field(default='', max_length=4000)


class StoredResponse(Contract):
    response: Response
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_match: Literal['SAME_SOURCE', 'SOURCE_CHANGED', 'NEW'] = 'NEW'
    review_required: bool = False


class Section(Contract):
    id: str = Field(max_length=64)
    order: int = Field(ge=0, le=999, strict=True)
    included: bool = True
    note: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def known(self):
        if self.id not in {s.lower() for s in SECTIONS}: raise ValueError('UNKNOWN_SECTION')
        return self


class ManualItem(Contract):
    id: UUID
    kind: Literal['CLARIFICATION', 'EXCLUSION', 'ASSUMPTION', 'DEVIATION', 'NOTE', 'ANNEX_REFERENCE']
    text: str = Field(min_length=1, max_length=8000)
    document_id: UUID | None = None
    external_reference: str = Field(default='', max_length=1000)


class MaterializedSource(Contract):
    contract_version: Literal['proposal-composition-v1'] = CONTRACT
    source_type: Literal['REQUIREMENT', 'REQUESTED_EVIDENCE']
    source_id: str
    display_text: str = Field(min_length=1)
    representation_fingerprint: str
    references: list[dict]
    content_sha256: str

    @model_validator(mode='after')
    def verify_content(self):
        payload = self.model_dump(mode='json', exclude={'content_sha256'})
        if digest(payload) != self.content_sha256: raise ValueError('MATERIALIZED_SOURCE_HASH_MISMATCH')
        return self


class Content(Contract):
    sources: dict[str, MaterializedSource] | None = None
    responses: dict[str, StoredResponse] = Field(default_factory=dict)
    sections: list[Section] = Field(default_factory=list, max_length=8)
    items: list[ManualItem] = Field(default_factory=list, max_length=200)
    removed_keys: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique(self):
        if len({s.id for s in self.sections}) != len(self.sections): raise ValueError('DUPLICATE_SECTION')
        if len({s.id for s in self.items}) != len(self.items): raise ValueError('DUPLICATE_MANUAL_ITEM')
        return self


class Initialize(Contract):
    actor_label: str | None = Field(default=None, max_length=200)
    origin: Literal['API', 'WORKSPACE'] = 'API'


class Mutation(Initialize):
    expected_revision: int = Field(ge=1, strict=True)


class ResponseChange(Contract):
    key: str = Field(max_length=100)
    response: Response
    acknowledge_source_change: bool = False


class ChangeResponses(Mutation):
    changes: list[ResponseChange] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def unique(self):
        if len({c.key for c in self.changes}) != len(self.changes): raise ValueError('DUPLICATE_RESPONSE_KEY')
        return self


class ChangeSettings(Mutation):
    sections: list[Section] | None = Field(default=None, max_length=8)
    items: list[ManualItem] | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def unique(self):
        Content(sections=self.sections or [], items=self.items or [])
        return self


def canonical_rows(snapshot, content=None):
    """No SQL or mutable Tender data. Ordering never supplies row identity."""
    projection = snapshot.payload.projection.model_dump(mode='json')
    rows = {}
    for source in projection['rows']:
        scope = {k: source[k] for k in ('tender_id', 'scope_id', 'item_reference', 'description', 'quantity_id',
            'quantity_scope_id', 'quantity_tender_id', 'quantity', 'unit', 'source', 'quantity_source')}
        rows['SCOPE:' + source['scope_id']] = {'section': 'TECHNICAL_SCOPE', 'canonical': scope}
        rows['ECONOMIC:' + source['commercial_line_id']] = {'section': 'ECONOMIC', 'canonical': source}
    fingerprints = {r['requirement_id']: r['representation_fingerprint'] for r in projection['requirement_representations']}
    for state in projection['tracked_context']:
        entity = state['entity_type']
        if entity not in {'REQUIREMENT', 'REQUESTED_EVIDENCE'}: continue
        key = entity + ':' + state['entity_id']
        target = rows.setdefault(key, {'section': 'REQUIREMENTS' if entity == 'REQUIREMENT' else 'REQUESTED_EVIDENCE',
            'canonical': {'id': state['entity_id'], 'text_state': 'NOT_FROZEN_IN_SNAPSHOT', 'states': [],
                'representation_fingerprint': fingerprints.get(state['entity_id'] if entity == 'REQUIREMENT' else state['parent_requirement_id'])}})
        target['canonical']['states'].append(state)
    documents = {d['id']: d for d in projection['documents']}
    for key, row in rows.items():
        canonical = row['canonical']
        materialized = content.sources.get(key) if content and content.sources else None
        if materialized:
            canonical.update(display_text=materialized.display_text, text_state='MATERIALIZED',
                             materialized_source=materialized.model_dump(mode='json'))
        if 'states' in canonical: canonical['states'].sort(key=lambda s: s['id'])
        references = ([canonical.get('source'), canonical.get('quantity_source')] if 'states' not in canonical
                      else [s['reference'] for s in canonical['states']])
        referenced = sorted({r['document_id'] for r in references if r and r.get('document_id')})
        row['source_sha256'] = digest({'canonical': canonical, 'documents': [documents.get(i) for i in referenced]})
        row['key'] = key
    return dict(sorted(rows.items()))


def _stored(db, row, required=True):
    stored = db.get(ProposalComposition, row.id)
    if stored is None:
        if required: raise HTTPException(409, 'COMPOSITION_NOT_INITIALIZED')
        return None, None
    try:
        if stored.contract_version != CONTRACT: raise ValueError('CONTRACT')
        content = Content.model_validate(stored.content)
    except (ValueError, TypeError) as exc: raise HTTPException(409, 'COMPOSITION_INTEGRITY_FAILURE') from exc
    return stored, content


def _content_dump(content):
    data = content.model_dump(mode='json')
    if content.sources is None: data.pop('sources')  # Preserve existing frozen byte contract.
    return data


def capture_sources(db, snapshot, prior=None):
    rows = canonical_rows(snapshot)
    expected = {r['requirement_id']: r['representation_fingerprint'] for r in snapshot.payload.projection.requirement_representations}
    sources = {}
    missing = []
    for key, row in rows.items():
        if row['section'] not in {'REQUIREMENTS', 'REQUESTED_EVIDENCE'}: continue
        old = prior.sources.get(key) if prior and prior.sources else None
        fingerprint = row['canonical']['representation_fingerprint']
        refs = [state['reference'] for state in row['canonical']['states'] if state['reference']]
        if old and old.representation_fingerprint == fingerprint and old.references == refs:
            sources[key] = old.model_copy(deep=True)
        else: missing.append((key, row, fingerprint, refs))
    if missing:
        from app.requirement_matrix import get_tender_requirement_matrix
        matrix = get_tender_requirement_matrix(db, snapshot.payload.tender_id)
        requirements = {r['requirement_id']: r for r in matrix['requirements']}
        evidence = {e['id']: (r, e) for r in matrix['requirements'] for e in r['expected_evidence']}
        for key, row, fingerprint, refs in missing:
            kind, identity = key.split(':', 1)
            if kind == 'REQUIREMENT':
                current = requirements.get(identity); text = current['canonical_text'] if current else None
            else:
                parent, item = evidence.get(identity, (None, None)); current = parent
                text = item['evidence_description'] if item else None
            if not current or current['representation_fingerprint'] != fingerprint or expected.get(current['requirement_id']) != fingerprint or not text:
                raise HTTPException(409, 'SOURCE_REPRESENTATION_UNAVAILABLE_FOR_SNAPSHOT')
            payload = {'contract_version': CONTRACT, 'source_type': kind, 'source_id': identity,
                       'display_text': text, 'representation_fingerprint': fingerprint, 'references': refs}
            sources[key] = MaterializedSource(**payload, content_sha256=digest(payload))
    return sources


def composition_hash(stored):
    return digest({'contract_version': CONTRACT, 'version_id': stored.version_id, 'revision': stored.revision,
                   'content': _content_dump(Content.model_validate(stored.content))})


def verify_frozen(db, row):
    receipt = row.freeze_acknowledgements or {}
    if 'composition_sha256' not in receipt: return  # Historical M9-A frozen contract.
    stored, _ = _stored(db, row)
    if receipt.get('composition_contract') != CONTRACT or receipt.get('composition_revision') != stored.revision or receipt['composition_sha256'] != composition_hash(stored):
        raise HTTPException(409, 'FROZEN_COMPOSITION_HASH_MISMATCH')


def _sections(row, content):
    defaults = {s.type: s.model_dump(mode='json') for s in versions.section_projection(versions.ProposalConfig.model_validate(row.configuration))}
    defaults['CLARIFICATIONS'] = {'id': 'clarifications', 'type': 'CLARIFICATIONS', 'order': 45, 'included': True, 'note': ''}
    for section in content.sections:
        defaults[section.id.upper()].update(section.model_dump(mode='json'))
    return sorted(defaults.values(), key=lambda s: (s['order'], s['id']))


def _row_view(key, source, content):
    stored = content.responses.get(key)
    response = stored.response.model_dump(mode='json') if stored else Response().model_dump(mode='json')
    return {**source, 'response': response, 'source_match': stored.source_match if stored else 'NEW',
            'review_required': bool(stored and stored.review_required),
            'declaration_authority': 'USER_DECLARATION_NOT_CERTIFICATION'}


def completeness(rows, sections, content):
    summaries = {s['type']: {'section': s['type'], 'pending_count': 0, 'review_count': 0, 'row_count': 0, 'reasons': []} for s in sections}
    hard, blocking, reviews = [], [], []
    for key, source in rows.items():
        row = _row_view(key, source, content); response = row['response']; kind = source['section']
        target = summaries[kind]; target['row_count'] += 1
        pending, review, blocked = [], [], []
        if kind in {'REQUIREMENTS', 'REQUESTED_EVIDENCE'} and response['status'] == 'PENDING': pending.append('RESPONSE_PENDING')
        if kind == 'REQUESTED_EVIDENCE' and response['status'] == 'PROVIDED' and not (response['document_id'] or response['external_reference'].strip()): pending.append('EVIDENCE_REFERENCE_REQUIRED')
        if row['review_required']: blocked.append('SOURCE_CHANGED_UNRESOLVED')
        if response['status'] == 'REVIEW_REQUIRED': blocked.append('RESPONSE_REVIEW_UNRESOLVED')
        if response['status'] in {'PARTIAL', 'EXCEPTION', 'NOT_APPLICABLE'} or not response['included']:
            if not response['reason'].strip(): pending.append('RESPONSE_REASON_REQUIRED')
            review.append('HUMAN_EXCEPTION_OR_EXCLUSION')
        if kind == 'ECONOMIC':
            c = source['canonical']
            if any(c.get(k) is None or c.get(k) == '' for k in ('quantity', 'unit', 'currency', 'offered_unit_price', 'offered_total')): pending.append('CANONICAL_ECONOMIC_INCOMPLETE')
        hard.extend({'key': key, 'code': r} for r in pending)
        blocking.extend({'key': key, 'code': r} for r in blocked)
        reviews.extend({'key': key, 'code': r} for r in review)
        target['pending_count'] += bool(pending); target['review_count'] += bool(review or blocked)
        target['reasons'].extend({'key': key, 'code': r} for r in pending + blocked + review)
    for section in sections:
        if not section['included']:
            reviews.append({'key': section['id'], 'code': 'SECTION_EXCLUDED'})
            summaries[section['type']]['review_count'] += 1
            if not (section.get('note') or '').strip():
                reason = {'key': section['id'], 'code': 'SECTION_EXCLUSION_REASON_REQUIRED'}
                hard.append(reason)
                summaries[section['type']]['pending_count'] += 1
                summaries[section['type']]['reasons'].append(reason)
    for target in summaries.values():
        target['status'] = 'INCOMPLETE' if target['pending_count'] else 'REVIEW_REQUIRED' if target['review_count'] else 'COMPLETE'
    return {'status': 'INCOMPLETE' if hard else 'REVIEW_REQUIRED' if blocking or reviews else 'COMPLETE',
            'hard_incomplete': hard, 'blocking_review': blocking, 'acknowledgeable_review': reviews, 'sections': list(summaries.values())}


def bounded_summary(summary):
    # Counts remain exact; diagnostic lists and Workspace rendering stay bounded.
    for field in ('hard_incomplete', 'blocking_review', 'acknowledgeable_review'):
        summary[field + '_count'] = len(summary[field])
        summary[field] = summary[field][:100]
    for section in summary['sections']:
        section['reason_count'] = len(section['reasons'])
        section['reasons'] = section['reasons'][:25]
    return summary


def projection(db, tender_id, version_id, *, section=None, offset=0, limit=50):
    if section is not None and section not in SECTIONS: raise HTTPException(422, 'UNKNOWN_SECTION')
    if offset < 0 or not 1 <= limit <= 200: raise HTTPException(422, 'INVALID_COMPOSITION_PAGE')
    row = versions._row(db, tender_id, version_id); snapshot = versions._verified(db, row)
    stored, content = _stored(db, row, required=False)
    if stored is None: return {'contract_version': CONTRACT, 'initialized': False, 'version_id': row.id}
    rows = canonical_rows(snapshot, content); sections = _sections(row, content)
    if set(content.responses) - set(rows): raise HTTPException(409, 'COMPOSITION_ORPHAN_RESPONSE')
    visible = [value for value in rows.values() if section is None or value['section'] == section]
    config = versions.ProposalConfig.model_validate(row.configuration)
    return {'contract_version': CONTRACT, 'initialized': True, 'version_id': row.id, 'snapshot_id': row.snapshot_id,
        'snapshot_sha256': row.snapshot_sha256, 'revision': stored.revision, 'sha256': composition_hash(stored),
        'identification': {'tender_id': tender_id, 'tender_title': snapshot.payload.projection.tender_title,
            'proposal_id': row.proposal_id, 'version': row.version, 'snapshot_date': snapshot.payload.created_at,
            'title': config.title, 'bidder_name': config.bidder_name, 'bidder_reference': config.bidder_reference, 'notes': config.notes},
        'sections': sections, 'summary': bounded_summary(completeness(rows, sections, content)),
        'rows': [_row_view(value['key'], value, content) for value in visible[offset:offset + limit]],
        'total': len(visible), 'next_offset': offset + limit if offset + limit < len(visible) else None,
        'currency_groups': [{'currency': currency, 'line_count': sum(r['section'] == 'ECONOMIC' and r['canonical']['currency'] == currency for r in rows.values())}
                            for currency in sorted({r['canonical']['currency'] or '' for r in rows.values() if r['section'] == 'ECONOMIC'})],
        'items': [item.model_dump(mode='json') for item in content.items], 'removed_keys': content.removed_keys}


def initialize(db, tender_id, version_id, request):
    row = versions._row(db, tender_id, version_id, lock=True); snapshot = versions._verified(db, row)
    stored, _ = _stored(db, row, required=False)
    if stored:
        _, existing = _stored(db, row)
        if existing.sources is None and row.state == 'DRAFT':
            versions._editable(db, row, row.edit_revision)
            existing.sources = capture_sources(db, snapshot)
            for key, source in canonical_rows(snapshot, existing).items():
                if key in existing.responses: existing.responses[key].source_sha256 = source['source_sha256']
            return _save(db, row, stored, existing, request)
        return projection(db, tender_id, version_id)
    versions._editable(db, row, row.edit_revision)
    content = Content()
    prior = None
    if row.previous_version_id:
        previous = versions._row(db, tender_id, row.previous_version_id); versions._verified(db, previous)
        _, prior = _stored(db, previous, required=False)
    content.sources = capture_sources(db, snapshot, prior)
    rows = canonical_rows(snapshot, content)
    if row.previous_version_id:
        previous = versions._row(db, tender_id, row.previous_version_id); previous_snapshot = versions._verified(db, previous)
        _, prior = _stored(db, previous, required=False)
        if prior:
            content.sections = deepcopy(prior.sections); content.items = deepcopy(prior.items)
            documents = {d['id'] for d in snapshot.payload.projection.documents}
            # Invalid copied manual associations are not silently rebound to another document.
            for item in content.items:
                if item.document_id and str(item.document_id) not in documents:
                    item.external_reference = f'Previous document: {item.document_id}; {item.external_reference}'[:1000]
                    item.document_id = None
            content.removed_keys = sorted(set(canonical_rows(previous_snapshot, prior)) - set(rows))
            for key in sorted(set(prior.responses) & set(rows)):
                old = prior.responses[key]; same = old.source_sha256 == rows[key]['source_sha256']
                response = old.response.model_copy(deep=True)
                if response.document_id and str(response.document_id) not in documents:
                    response.document_id = None; same = False
                content.responses[key] = StoredResponse(response=response, source_sha256=rows[key]['source_sha256'],
                    source_match='SAME_SOURCE' if same else 'SOURCE_CHANGED', review_required=old.review_required or not same)
    now = datetime.now(timezone.utc)
    stored = ProposalComposition(version_id=row.id, contract_version=CONTRACT, revision=1,
        content=_content_dump(content), created_at=now, updated_at=now)
    db.add(stored); db.flush()
    versions._event(db, row, 'COMPOSITION_INITIALIZED', request.actor_label, {'origin': request.origin,
        'contract_version': CONTRACT, 'removed_keys': content.removed_keys, 'copied_keys': sorted(content.responses)})
    return projection(db, tender_id, version_id)


def _mutation(db, tender_id, version_id, request):
    row = versions._row(db, tender_id, version_id, lock=True); snapshot = versions._verified(db, row)
    versions._editable(db, row, row.edit_revision)
    stored, content = _stored(db, row)
    if stored.revision != request.expected_revision: raise HTTPException(409, 'COMPOSITION_REVISION_STALE')
    return row, snapshot, stored, content


def _changes(value, other):
    changed = {}
    for key in value:
        if value[key] == other.get(key): continue
        if key == 'responses':
            changed[key] = {k: value[key].get(k) for k in sorted(set(value[key]) | set(other.get(key, {})))
                            if value[key].get(k) != other.get(key, {}).get(k)}
        else: changed[key] = value[key]
    return changed


def _save(db, row, stored, content, request):
    current = _content_dump(content)
    if current != stored.content:
        previous = stored.content
        stored.content = current; stored.revision += 1; stored.updated_at = datetime.now(timezone.utc); db.flush()
        versions._event(db, row, 'COMPOSITION_UPDATED', request.actor_label,
            {'origin': request.origin, 'revision': stored.revision,
             'previous': _changes(previous, current), 'current': _changes(current, previous)})
    return projection(db, row.tender_id, row.id)


def _document(snapshot, document_id):
    if document_id and str(document_id) not in {d['id'] for d in snapshot.payload.projection.documents}:
        raise HTTPException(422, 'DOCUMENT_NOT_IN_BOUND_SNAPSHOT')


def change_responses(db, tender_id, version_id, request):
    row, snapshot, stored, content = _mutation(db, tender_id, version_id, request); rows = canonical_rows(snapshot, content)
    for change in request.changes:
        if change.key not in rows: raise HTTPException(422, 'SOURCE_NOT_IN_BOUND_SNAPSHOT')
        kind = rows[change.key]['section']; response = change.response
        if kind == 'ECONOMIC' and response.model_dump(exclude={'note'}) != Response().model_dump(exclude={'note'}):
            raise HTTPException(422, 'ECONOMIC_CANONICAL_READ_ONLY')
        if response.status == 'PROVIDED' and kind != 'REQUESTED_EVIDENCE': raise HTTPException(422, 'STATUS_NOT_ALLOWED_FOR_ROW')
        if kind == 'REQUESTED_EVIDENCE' and response.status not in {'PENDING', 'PROVIDED', 'NOT_APPLICABLE', 'REVIEW_REQUIRED'}: raise HTTPException(422, 'STATUS_NOT_ALLOWED_FOR_ROW')
        _document(snapshot, response.document_id)
        previous = content.responses.get(change.key)
        content.responses[change.key] = StoredResponse(response=response, source_sha256=rows[change.key]['source_sha256'],
            source_match=previous.source_match if previous else 'NEW',
            review_required=bool(previous and previous.review_required and not change.acknowledge_source_change))
    return _save(db, row, stored, content, request)


def change_settings(db, tender_id, version_id, request):
    row, snapshot, stored, content = _mutation(db, tender_id, version_id, request)
    if request.sections is not None: content.sections = request.sections
    if request.items is not None:
        for item in request.items: _document(snapshot, item.document_id)
        content.items = request.items
    content = Content.model_validate(content.model_dump(mode='json'))
    return _save(db, row, stored, content, request)


def freeze_precheck(db, row, snapshot, request):
    stored, content = _stored(db, row)
    if request.expected_composition_revision != stored.revision: raise HTTPException(409, 'COMPOSITION_REVISION_STALE')
    if content.sources is None: raise HTTPException(409, 'SOURCE_MATERIALIZATION_REQUIRED')
    summary = completeness(canonical_rows(snapshot, content), _sections(row, content), content)
    if summary['hard_incomplete']: raise HTTPException(409, {'code': 'COMPOSITION_INCOMPLETE', 'reasons': summary['hard_incomplete']})
    if summary['blocking_review']: raise HTTPException(409, {'code': 'COMPOSITION_REVIEW_UNRESOLVED', 'reasons': summary['blocking_review']})
    if summary['acknowledgeable_review'] and not request.acknowledge_composition_review: raise HTTPException(409, 'COMPOSITION_REVIEW_ACK_REQUIRED')
    return {'composition_contract': CONTRACT, 'composition_revision': stored.revision,
            'composition_sha256': composition_hash(stored), 'composition_review_acknowledged': request.acknowledge_composition_review}
