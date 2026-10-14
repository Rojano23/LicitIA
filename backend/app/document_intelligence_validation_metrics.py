"""Read-only, Tender-neutral blind validation instrumentation. Never acquires evidence."""
from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

METRICS_VERSION = 'DI_BLIND_METRICS_001'
DOMAINS = ('DOCUMENTS', 'REQUIREMENTS', 'REQUESTED_EVIDENCE', 'SCOPE', 'ATTRIBUTES', 'QUANTITIES', 'VERSIONS', 'EFFECTS', 'STRUCTURE')
SAFETY_FIELDS = ('trusted_correct', 'trusted_incorrect', 'unsafe_trusted_contractual_errors',
    'unsafe_trusted_structural_errors', 'safe_misses', 'unnecessary_review',
    'critical_identifier_conflicts_correctly_surfaced', 'quantity_unsafe_bindings',
    'attribute_unsafe_bindings', 'safe_automatic_selections', 'recall')


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class MetricRecord(Contract):
    id: str = Field(min_length=1)
    domain: Literal['DOCUMENTS', 'REQUIREMENTS', 'REQUESTED_EVIDENCE', 'SCOPE', 'ATTRIBUTES', 'QUANTITIES', 'VERSIONS', 'EFFECTS', 'STRUCTURE']
    state: Literal['TRUSTED', 'REVIEW_REQUIRED', 'UNAVAILABLE', 'REJECTED']
    automatic: bool = False
    reason: str | None = None
    document_id: str | None = None
    page_id: str | None = None
    parent_id: str | None = None
    unresolved_binding: bool = False
    version_state: str | None = None
    provenance: dict[str, object] = Field(default_factory=dict)


class ProviderMetric(Contract):
    id: str
    provider: str
    source_method: Literal['NATIVE', 'OCR', 'VISION']
    model: str | None = None
    capability: Literal['TRANSCRIPTION', 'STRUCTURE', 'SEMANTIC_ASSIST']
    status: str
    calls: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    timeout: bool = False
    truncated: bool = False
    page_id: str | None = None
    configuration: dict[str, object] = Field(default_factory=dict)
    execution_event: bool = False


class ValidationSnapshot(Contract):
    schema_version: Literal['DI_BLIND_METRICS_001'] = METRICS_VERSION
    tender_id: str
    page_ids: tuple[str, ...] = ()
    records: tuple[MetricRecord, ...] = ()
    providers: tuple[ProviderMetric, ...] = ()
    perception: tuple[dict[str, object], ...] = ()
    conflicts: tuple[dict[str, object], ...] = ()
    stale_carry_violations: int | None = Field(default=None, ge=0)
    errors: tuple[str, ...] = ()
    discovery_counts: dict[str, int] = Field(default_factory=dict)
    discovery_records: tuple[dict[str, object], ...] = ()

    @model_validator(mode='after')
    def unique_records(self):
        keys = [(r.domain, r.id) for r in self.records]
        if len(keys) != len(set(keys)) or len({p.id for p in self.providers}) != len(self.providers):
            raise ValueError('Duplicate metric identity')
        return self


def collect_metrics(snapshot: ValidationSnapshot) -> dict:
    """Observable confidence is not adjudicated correctness; zero denominators => null rates."""
    result = {}
    reviews = []
    for domain in DOMAINS:
        rows = [r for r in snapshot.records if r.domain == domain]
        counts = Counter(r.state for r in rows)
        total = len(rows)
        result[domain] = {'total': total, 'discovered': total,
            'trusted': counts['TRUSTED'], 'review_required': counts['REVIEW_REQUIRED'],
            'rejected': counts['REJECTED'], 'unavailable': counts['UNAVAILABLE'],
            'trusted_automatic_unadjudicated': sum(r.state == 'TRUSTED' and r.automatic for r in rows),
            'unresolved_binding': sum(r.unresolved_binding for r in rows),
            'review_required_rate': counts['REVIEW_REQUIRED'] / total if total else None,
            'unavailable_rate': counts['UNAVAILABLE'] / total if total else None,
            'trusted_automatic_rate_unadjudicated': sum(r.state == 'TRUSTED' and r.automatic for r in rows) / total if total else None}
        reviews.extend(r for r in rows if r.state == 'REVIEW_REQUIRED')
    review = {'total': len(reviews), 'by_domain': dict(sorted(Counter(r.domain for r in reviews).items())),
        'by_reason': dict(sorted(Counter(r.reason or 'UNSPECIFIED' for r in reviews).items())),
        'documents_affected': len({r.document_id for r in reviews if r.document_id}),
        'pages_affected': len({r.page_id for r in reviews if r.page_id})}
    version = Counter(r.version_state for r in snapshot.records if r.domain == 'VERSIONS')
    provider_groups = []
    keys = sorted({(p.provider, p.model or '', p.capability, p.source_method) for p in snapshot.providers})
    for provider, model, capability, method in keys:
        rows = [p for p in snapshot.providers if (p.provider, p.model or '', p.capability, p.source_method) == (provider, model, capability, method)]
        events = [p for p in rows if p.execution_event]
        call_rows = events or rows
        provider_groups.append({'provider': provider, 'model': model or None, 'capability': capability, 'source_method': method,
            'artifacts': sum(not p.execution_event for p in rows), 'execution_events':len(events),
            'calls': sum(p.calls for p in call_rows) if all(p.calls is not None for p in call_rows) else None,
            'calls_measurement': 'RECORDED' if all(p.calls is not None for p in call_rows) else 'NOT_MEASURED',
            'outcome_basis': 'EXECUTION_EVENTS' if events else 'PERSISTED_ARTIFACTS',
            'success': sum(p.status == 'COMPLETED' for p in call_rows),
            'failure': sum(p.status in {'FAILED', 'INVALID_JSON', 'UNAVAILABLE'} for p in call_rows),
            'statuses': dict(sorted(Counter(p.status for p in call_rows).items())),
            'artifact_statuses': dict(sorted(Counter(p.status for p in rows if not p.execution_event).items())),
            'latencies_ms': sorted(p.latency_ms for p in call_rows if p.latency_ms is not None),
            'timeouts': sum(p.timeout for p in call_rows), 'truncations': sum(p.truncated for p in call_rows)})
    availability = Counter((str(p['channel']), str(p['capability']), str(p['status'])) for p in snapshot.perception)
    links = Counter()
    record_keys = {(r.domain, r.id) for r in snapshot.records}
    for r in snapshot.records:
        if r.parent_id and r.domain in {'ATTRIBUTES', 'QUANTITIES'} and ('SCOPE', r.parent_id) in record_keys:
            links[f'SCOPE->{r.domain}'] += 1
        if r.parent_id and r.domain == 'REQUESTED_EVIDENCE' and ('REQUIREMENTS', r.parent_id) in record_keys:
            links['REQUIREMENTS->REQUESTED_EVIDENCE'] += 1
        if r.provenance.get('source_artifact_key') or r.provenance.get('perception_provenance'):
            links[f'PERCEPTION->{r.domain}'] += 1
    return {'schema_version': METRICS_VERSION, 'first_pass': {'domains': result,
        'documents_total': result['DOCUMENTS']['total'], 'pages_total': len(snapshot.page_ids),
        'discovery_counts': dict(sorted(snapshot.discovery_counts.items())),
        'versions': dict(sorted((k, v) for k, v in version.items() if k)),
        'review_queue': review, 'providers': provider_groups,
        'perception_availability': [{'channel': k[0], 'capability': k[1], 'status': k[2], 'count': v} for k, v in sorted(availability.items())],
        'conflicts_surfaced': len(snapshot.conflicts), 'stale_carry_violations': snapshot.stale_carry_violations,
        'domain_impact': {'traceable_links': dict(sorted(links.items())), 'causal_error_impact': None}},
        'post_adjudication': {name: None for name in SAFETY_FIELDS}}


class HumanJudgment(Contract):
    domain: str
    record_id: str
    disposition: Literal['TRUSTED_CORRECT', 'TRUSTED_INCORRECT', 'SAFE_MISS', 'UNNECESSARY_REVIEW', 'MISSING', 'CONFLICT_SURFACED']
    truth_id: str = Field(min_length=1)
    structural: bool = False
    unsafe_binding: bool = False

    @model_validator(mode='after')
    def frozen_domain(self):
        if self.domain not in DOMAINS:
            raise ValueError('Judgment must use a frozen measurement domain')
        return self


class HumanTruth(Contract):
    approved_by_human: Literal[True]
    authority: Literal['INDEPENDENT_HUMAN_TRUTH']
    reviewer: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    frozen_first_pass_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    judgments: tuple[HumanJudgment, ...]


def adjudicate(snapshot: ValidationSnapshot, truth: HumanTruth, first_pass_sha256: str) -> dict:
    if truth.frozen_first_pass_sha256 != first_pass_sha256:
        raise ValueError('Truth belongs to another first pass')
    rows = {(r.domain, r.id): r for r in snapshot.records}
    seen = set()
    counts = {name: 0 for name in SAFETY_FIELDS if name != 'recall'}
    found, expected = set(), set()
    for judgment in truth.judgments:
        key = (judgment.domain, judgment.record_id)
        if key in seen:
            raise ValueError('Duplicate human judgment')
        seen.add(key)
        row = rows.get(key)
        if judgment.disposition != 'MISSING' and row is None:
            raise ValueError('Judgment has no observed record')
        if judgment.disposition == 'MISSING' and row is not None:
            raise ValueError('Missing truth cannot label an existing record')
        disposition = judgment.disposition
        if disposition.startswith('TRUSTED_') and row.state != 'TRUSTED':
            raise ValueError('Trusted judgment requires trusted observation')
        if disposition == 'UNNECESSARY_REVIEW' and row.state != 'REVIEW_REQUIRED':
            raise ValueError('Unnecessary review requires reviewed observation')
        if disposition == 'SAFE_MISS' and row.state not in {'REVIEW_REQUIRED', 'UNAVAILABLE', 'REJECTED'}:
            raise ValueError('Safe miss cannot label trusted observation')
        if disposition == 'TRUSTED_CORRECT':
            counts['trusted_correct'] += 1
            counts['safe_automatic_selections'] += int(row.automatic)
        if disposition == 'TRUSTED_INCORRECT':
            counts['trusted_incorrect'] += 1
            counts['unsafe_trusted_contractual_errors'] += 1
            counts['unsafe_trusted_structural_errors'] += int(judgment.structural)
            counts['quantity_unsafe_bindings'] += int(judgment.unsafe_binding and judgment.domain == 'QUANTITIES')
            counts['attribute_unsafe_bindings'] += int(judgment.unsafe_binding and judgment.domain == 'ATTRIBUTES')
        if disposition == 'SAFE_MISS': counts['safe_misses'] += 1
        if disposition == 'UNNECESSARY_REVIEW': counts['unnecessary_review'] += 1
        if disposition == 'CONFLICT_SURFACED':
            surfaced = any(c.get('page_id') == row.page_id and
                ('identifier_comparison' in c or (c.get('conflict') or {}).get('kind') == 'IDENTIFIER')
                for c in snapshot.conflicts)
            if row.state != 'REVIEW_REQUIRED' or not surfaced:
                raise ValueError('Conflict adjudication requires a surfaced identifier conflict')
            counts['critical_identifier_conflicts_correctly_surfaced'] += 1
        if disposition != 'CONFLICT_SURFACED':
            expected.add((judgment.domain, judgment.truth_id))
            if disposition in {'TRUSTED_CORRECT', 'UNNECESSARY_REVIEW'}:
                found.add((judgment.domain, judgment.truth_id))
    return {'post_adjudication': counts | {'recall': len(found) / len(expected) if expected else None},
        'coverage': {'judged': len(seen), 'observed_unjudged': len(set(rows) - seen),
            'recall_denominator': len(expected), 'scope': 'ADJUDICATED_TRUTH_ONLY'},
        'human_truth': truth.model_dump(mode='json')}


def database_identity(db: Session) -> dict:
    return {'database': db.execute(text('SELECT current_database()')).scalar_one(),
        'revision': db.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),
        'tender_count': db.execute(text('SELECT count(*) FROM tenders')).scalar_one(),
        'document_count': db.execute(text('SELECT count(*) FROM tender_documents')).scalar_one()}


def snapshot_tender(db: Session, tender_id: str, *, authorized_import: bool = False) -> ValidationSnapshot:
    """Only after explicit future import authorization; all queries bounded to one Tender."""
    if not authorized_import:
        raise PermissionError('Explicit authorized import required before corpus access')
    with db.no_autoflush:
        return _snapshot_tender(db, tender_id)


def _snapshot_tender(db: Session, tender_id: str) -> ValidationSnapshot:
    from app import models as m
    from app.document_intelligence_sources import load_document_transcriptions, load_page_structure
    from app.document_intelligence import advance_continuity, Capability, SourceMethod, route_capability
    from app.document_identifier_bindings import guard_structure, page_identifier_comparisons
    from app.requirement_di_adapter import candidate_perception, candidate_provenance
    from app.source_effect_resolution import resolve_effective_sources_for_tender
    from app.effective_source_projection import project_effective_sources_for_tender
    from dataclasses import asdict
    from datetime import datetime, date
    from decimal import Decimal
    from enum import Enum
    def value(item):
        if isinstance(item, (datetime,date)): return item.isoformat()
        if isinstance(item, Decimal): return str(item)
        if isinstance(item, Enum): return item.value
        if isinstance(item, dict): return {k:value(v) for k,v in item.items()}
        if isinstance(item, (tuple,list)): return [value(v) for v in item]
        if item is None or isinstance(item,(str,int,float,bool)): return item
        raise ValueError('Unsupported persisted audit value')
    def columns(row):
        return {c.key:value(getattr(row,c.key)) for c in row.__table__.columns}
    if db.get(m.Tender, tender_id) is None:
        raise LookupError('Tender not found')
    records, providers, perceptions, conflicts = [], [], [], []
    pages_all = []
    stale = 0
    resolution = resolve_effective_sources_for_tender(db, tender_id=tender_id)
    projection = project_effective_sources_for_tender(db, tender_id=tender_id, document_resolution=resolution)
    projected = {p.entity_id: p for family in (projection.requirements, projection.scope_details, projection.scope_attributes, projection.scope_quantities) for p in family}
    def add(domain, row, state, **fields):
        projected_row = projected.get(row.id)
        reasons = []
        if projected_row and projected_row.status in {'REVIEW_REQUIRED', 'UNRESOLVED_SOURCE'}:
            state = 'REVIEW_REQUIRED'; reasons = [d.code for d in projected_row.diagnostics]
        if projected_row and projected_row.status in {'SUPERSEDED', 'REVOKED'}:
            state = 'REJECTED'
        metadata = fields.pop('provenance', {})
        metadata['persisted_record'] = columns(row)
        if projected_row: metadata['effective_projection'] = asdict(projected_row)
        records.append(MetricRecord(id=row.id, domain=domain, state=state,
            reason=fields.pop('reason', None) or ';'.join(sorted(set(reasons))) or ('DOMAIN_REVIEW_REQUIRED' if state == 'REVIEW_REQUIRED' else None),
            provenance=metadata, **fields))
    docs = db.scalars(select(m.TenderDocument).where(m.TenderDocument.tender_id == tender_id).order_by(m.TenderDocument.id)).all()
    for doc in docs:
        add('DOCUMENTS', doc, 'UNAVAILABLE' if doc.processing_status in {'PENDING', 'TEXT_EXTRACTION_FAILED', 'NO_NATIVE_TEXT'} else 'REVIEW_REQUIRED' if doc.status == 'NAME_CONFLICT' else 'TRUSTED',
            document_id=doc.id, provenance={'sha256': doc.sha256, 'revision_number': doc.revision_number, 'processing_status': doc.processing_status})
        pages = db.scalars(select(m.DocumentPage).where(m.DocumentPage.document_id == doc.id).order_by(m.DocumentPage.page_number)).all()
        pages_all.extend(p.id for p in pages)
        transcriptions = load_document_transcriptions(db, doc)
        previous = None
        for page in pages:
            providers.append(ProviderMetric(id=f'native:{page.id}', provider='PyMuPDF', source_method='NATIVE',
                capability='TRANSCRIPTION', status='COMPLETED' if page.text.strip() else 'UNAVAILABLE',
                page_id=page.id, configuration={'extraction_method': page.extraction_method,
                    'runtime_measurement': 'NOT_MEASURED'}))
            transcription = transcriptions[page.id]
            structure = load_page_structure(db, doc, page)
            comparisons = page_identifier_comparisons(transcription, structure)
            structure = guard_structure(structure, comparisons)
            previous = advance_continuity(structure, previous)
            if 'STRUCTURAL_BOUNDARY_CONFLICT' in previous.diagnostics:
                conflicts.append({'page_id': page.id, 'kind': 'STRUCTURAL_BOUNDARY',
                    'diagnostics': list(previous.diagnostics)})
            stale += int(previous.status == 'UNKNOWN' and previous.outgoing_item_key is not None)
            state = 'TRUSTED' if structure.status == 'RESOLVED' and previous.status == 'VALID' else 'UNAVAILABLE' if structure.status == 'UNAVAILABLE' else 'REVIEW_REQUIRED'
            add('STRUCTURE', page, state, automatic=True, document_id=doc.id, page_id=page.id,
                reason=';'.join(previous.diagnostics) or None, provenance={'routing': structure.model_dump(mode='json'), 'continuity': previous.model_dump(mode='json')})
            for routing in (transcription, structure):
                for method in SourceMethod:
                    channel_sources = [e for e in routing.candidates if e.source_method == method]
                    routed = route_capability(page=routing.page, capability=routing.capability, evidence=channel_sources)
                    perceptions.append({'page_id': page.id, 'channel': method.value, 'capability': routing.capability.value,
                        'status': routed.status, 'sources': [e.model_dump(mode='json') for e in channel_sources]})
                conflicts.extend({'page_id': page.id, 'capability': routing.capability.value, 'conflict': c.model_dump(mode='json')} for c in routing.conflicts)
            conflicts.extend({'page_id': page.id, 'identifier_comparison': c.model_dump(mode='json')} for c in comparisons if c.status == 'CONFLICT')
            for ocr in db.scalars(select(m.PageOcrResult).where(m.PageOcrResult.document_page_id == page.id)).all():
                warnings = ocr.warnings or ''
                providers.append(ProviderMetric(id=ocr.id, provider=ocr.engine, source_method='OCR', capability='TRANSCRIPTION',
                    status='COMPLETED' if ocr.status == 'OCR_TEXT_EXTRACTED' else ocr.status, latency_ms=ocr.processing_time_ms,
                    timeout='TIMEOUT' in str(warnings).upper(), page_id=page.id,
                    configuration={'version': ocr.engine_version, 'language': ocr.language, 'warnings': warnings}))
        for result, analysis in db.execute(select(m.DocumentVisionPageResult, m.DocumentVisionAnalysis).join(m.DocumentVisionAnalysis)
                .where(m.DocumentVisionAnalysis.document_id == doc.id)).all():
            payload = result.structured_json or {}
            detail = payload.get('detail_transcription')
            # Structure and detail artifacts retain independent runtime/quality, even on a mixed result.
            tasks = [('STRUCTURE', payload.get('_vision_runtime'))] if payload.get('item_segments') is not None else []
            if detail is not None: tasks.append(('TRANSCRIPTION', payload.get('_detail_runtime')))
            if not tasks: tasks = [('TRANSCRIPTION' if 'detail-transcription' in analysis.prompt_version else 'STRUCTURE', None)]
            for capability, runtime in tasks:
                warnings = result.warnings or []
                providers.append(ProviderMetric(id=f'{result.id}:{capability}', provider='VISION', source_method='VISION', model=analysis.model_name,
                    capability=capability, status=(runtime or {}).get('status', result.status), latency_ms=result.processing_time_ms,
                    timeout=any('TIMEOUT' in str(w).upper() for w in warnings), truncated=any('OUTPUT_TRUNCATED' in str(w) or 'DONE_REASON:length' in str(w) for w in warnings),
                    page_id=result.document_page_id, configuration={'prompt_version': analysis.prompt_version, 'input_fingerprint': analysis.input_fingerprint_sha256,
                        'analysis_id': analysis.id, 'warnings': warnings, 'structured_json': payload, 'raw_response_text': result.raw_response_text}))
    candidates = db.scalars(select(m.RequirementCandidate).where(m.RequirementCandidate.tender_id == tender_id)).all()
    candidate_map = {c.id: c for c in candidates}
    for row in db.scalars(select(m.Requirement).where(m.Requirement.tender_id == tender_id)).all():
        candidate = candidate_map.get(row.primary_candidate_id)
        active, reviewed = candidate_perception(candidate) if candidate else (False, True)
        rejected = bool(row.review and row.review.review_status == 'REJECTED')
        state = 'REJECTED' if rejected else 'UNAVAILABLE' if not active else 'REVIEW_REQUIRED' if reviewed or row.normalization_status != 'NORMALIZED' else 'TRUSTED'
        add('REQUIREMENTS', row, state, automatic=not bool(row.review and row.review.review_status != 'PENDING'), document_id=candidate.source_document_id if candidate else None,
            page_id=candidate.document_page_id if candidate else None,
            provenance={'perception_provenance': [p.model_dump(mode='json') for p in candidate_provenance(candidate)] if candidate else [], 'primary_candidate_id': row.primary_candidate_id})
    for row in db.scalars(select(m.RequirementEvidenceExpectation).join(m.Requirement).where(m.Requirement.tender_id == tender_id)).all():
        semantics = row.requirement_semantics
        parent = next(r for r in records if r.domain == 'REQUIREMENTS' and r.id == row.requirement_id)
        state = 'TRUSTED' if semantics.interpretation_status == 'DETERMINED' and parent.state == 'TRUSTED' else 'REVIEW_REQUIRED'
        add('REQUESTED_EVIDENCE', row, state, automatic=True, document_id=row.source_document_id, parent_id=row.requirement_id,
            provenance={'source_excerpt': row.source_excerpt, 'source_page': row.source_page, 'evidence_type': row.evidence_type})
    for model, domain in [(m.TenderScopeDetail, 'SCOPE'), (m.TenderScopeAttribute, 'ATTRIBUTES'), (m.TenderScopeQuantity, 'QUANTITIES')]:
        for row in db.scalars(select(model).where(model.tender_id == tender_id)).all():
            parent = None if domain == 'SCOPE' else next(r for r in records if r.domain == 'SCOPE' and r.id == row.scope_detail_id)
            unresolved = (row.applicability == 'UNRESOLVED' or (row.applicability == 'ITEM' and not (row.scope_segment_id or row.tender_item_id or row.candidate_item_key))) if domain == 'SCOPE' else parent.unresolved_binding
            reviewed = row.review_required or unresolved or bool(parent and parent.state != 'TRUSTED')
            add(domain, row, 'REVIEW_REQUIRED' if reviewed else 'TRUSTED', automatic=True, unresolved_binding=unresolved,
                document_id=row.source_document_id, page_id=row.document_page_id, parent_id=parent.id if parent else None,
                provenance={'source_artifact_key': row.source_artifact_key, 'source_locator': row.source_locator,
                    'source_excerpt': row.source_excerpt, 'scope_detail_id': parent.id if parent else row.id})
    for version in resolution.documents:
        records.append(MetricRecord(id=version.document_id, domain='VERSIONS', document_id=version.document_id,
            state='REVIEW_REQUIRED' if version.status == 'REVIEW_REQUIRED' else 'REJECTED' if version.status in {'SUPERSEDED','REVOKED'} else 'TRUSTED', version_state=version.status,
            reason=';'.join(d.code for d in version.diagnostics) or None, provenance=asdict(version)))
    for row in db.scalars(select(m.TenderSourceEffect).where(m.TenderSourceEffect.tender_id == tender_id)).all():
        add('EFFECTS', row, 'REVIEW_REQUIRED' if row.review_required else 'TRUSTED', document_id=row.acting_document_id,
            page_id=row.document_page_id, unresolved_binding=row.effect_scope == 'UNRESOLVED' or row.affected_document_id is None,
            provenance={'source_artifact_key': row.source_artifact_key, 'effect_type': row.effect_type, 'effect_scope': row.effect_scope})
    errors = tuple(f'{d.code}:{d.document_id or ""}' for d in resolution.diagnostics)
    return ValidationSnapshot(tender_id=tender_id, page_ids=tuple(sorted(pages_all)),
        records=tuple(sorted(records, key=lambda r: (r.domain, r.id))), providers=tuple(sorted(providers, key=lambda p: p.id)),
        perception=tuple(perceptions), conflicts=tuple(conflicts), stale_carry_violations=stale, errors=errors,
        discovery_counts={'requirement_candidates':len(candidates),
            'rejected_requirement_candidates':sum(c.review_status == 'REJECTED' for c in candidates)},
        discovery_records=tuple({'candidate':columns(c), 'evidence':[columns(e) for e in sorted(c.evidence,key=lambda e:e.id)]}
            for c in sorted(candidates,key=lambda c:c.id)))
