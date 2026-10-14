"""Read-only Tender #001 calibration. Measurements never certify production input."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.document_intelligence import Capability, PerceptionEvidence, RoutingResult, advance_continuity, route_capability
from app.document_intelligence_sources import load_document_transcriptions, load_page_structure, page_identity
from app.document_identifier_bindings import guard_structure, page_identifier_comparisons
from app.models import (Tender, TenderDocument, DocumentPage, PageOcrResult, DocumentVisionAnalysis,
                        DocumentVisionPageResult, RequirementCandidateEvidence, TenderScopeDetail,
                        TenderScopeQuantity, TenderScopeAttribute, RequirementEvidenceExpectation)

TENDER_ID = 'decd32ae-2c1f-4520-89bc-d845c986a7ba'
TENDER_REFERENCE = 'SNR-CAD-265-CA-S-2026'

class ErrorCategory(str, Enum):
    TRANSCRIPTION_OMISSION = 'TRANSCRIPTION_OMISSION'
    TRANSCRIPTION_SUBSTITUTION = 'TRANSCRIPTION_SUBSTITUTION'
    NUMERIC_ERROR = 'NUMERIC_ERROR'
    UNIT_ERROR = 'UNIT_ERROR'
    IDENTIFIER_ERROR = 'IDENTIFIER_ERROR'
    STRUCTURE_BOUNDARY_ERROR = 'STRUCTURE_BOUNDARY_ERROR'
    CONTINUITY_ERROR = 'CONTINUITY_ERROR'
    QUANTITY_BINDING_ERROR = 'QUANTITY_BINDING_ERROR'
    ATTRIBUTE_BINDING_ERROR = 'ATTRIBUTE_BINDING_ERROR'
    PROVIDER_CONFLICT = 'PROVIDER_CONFLICT'
    UNSAFE_AUTO_SELECTION = 'UNSAFE_AUTO_SELECTION'
    UNNECESSARY_REVIEW = 'UNNECESSARY_REVIEW'
    CORRECT_REVIEW_ESCALATION = 'CORRECT_REVIEW_ESCALATION'
    UNAVAILABLE_EXPECTED = 'UNAVAILABLE_EXPECTED'
    OTHER = 'OTHER'

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

class EquipmentReference(Contract):
    identity: str
    source_excerpt: str
    model: str
    quantity: str
    unit: str

class SourceReferenceConflict(Contract):
    golden_value: str
    source_reading: str
    authority: str
    resolved: Literal[False] = False

class Reference(Contract):
    identity: str
    file_sha256: str
    human_label_status: Literal['APPROVED', 'PENDING'] = 'PENDING'
    # Partial references: fields omitted here are never treated as complete truth.
    critical_tokens: tuple[str, ...] = ()
    numeric_tokens: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    material_fragments: tuple[str, ...] = ()
    identifiers: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    exhaustive_identifiers: bool = False
    structure: dict[str, object] = Field(default_factory=dict)
    expected_routing: str | None = None
    quantity_bindings: tuple[str, ...] = ()
    attribute_bindings: tuple[str, ...] = ()
    equipment_rows: tuple[EquipmentReference, ...] = ()
    source_conflicts: tuple[SourceReferenceConflict, ...] = ()
    fragment_dimensions: dict[str, Literal['MATERIAL_TEXT_OMISSION','IDENTIFIER_MISMATCH','CRITICAL_TOKEN_MISMATCH','NUMERIC_MISMATCH','UNIT_MISMATCH']] = Field(default_factory=dict)

class Observation(Contract):
    tender_id: str = TENDER_ID
    external_reference: str = TENDER_REFERENCE
    provider: str
    model: str | None = None
    capability: Capability
    document_id: str
    page_number: int = Field(gt=0)
    artifact_id: str
    text: str = ''
    identifiers: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    critical_tokens: tuple[str, ...] = ()
    structure: dict[str, object] = Field(default_factory=dict)
    routing_status: Literal['RESOLVED', 'REVIEW_REQUIRED', 'UNAVAILABLE']
    lineage: Literal['ACTIVE', 'DESELECTED'] = 'ACTIVE'
    conflicts: tuple[str, ...] = ()
    continuity_status: str | None = None
    outgoing_item_key: str | None = None
    quantity_bindings: tuple[str, ...] = ()
    attribute_bindings: tuple[str, ...] = ()
    domain_impact: tuple[str, ...] = ()
    domain_input_trusted: bool | None = None
    domain_errors: tuple[ErrorCategory, ...] = ()
    latency_ms: int | None = Field(default=None, ge=0)
    provenance: dict = Field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @model_validator(mode='after')
    def only_development_tender(self):
        if self.tender_id != TENDER_ID or self.external_reference != TENDER_REFERENCE:
            raise ValueError('Only authorized Tender #001 is selectable')
        if self.provider=='VISION' and self.provenance.get('runtime_status')=='FAILED' and self.text.strip():
            raise ValueError('FAILED Vision cannot supply canonical transcription')
        return self


def serialize(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def freeze_references(paths: list[Path]) -> list[dict]:
    return [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)]


def evaluate(observed: Observation, reference: Reference | None = None) -> dict:
    labeled = reference is not None and reference.human_label_status == 'APPROVED'
    if observed.capability == Capability.STRUCTURE and reference is not None and not reference.structure:
        labeled = False
    active = observed.lineage == 'ACTIVE'
    errors: set[str] = set()
    measurements: dict = {}
    failed = observed.provider=='VISION' and observed.capability==Capability.TRANSCRIPTION and observed.provenance.get('runtime_status')=='FAILED'
    if labeled:
        for name, expected, actual, category in (
            ('critical_tokens', reference.critical_tokens, observed.critical_tokens, ErrorCategory.IDENTIFIER_ERROR),
            ('numeric_tokens', reference.numeric_tokens, tuple(re.findall(r'(?<!\w)\d+(?:[.,]\d+)?(?!\w)', observed.text)), ErrorCategory.NUMERIC_ERROR),
            ('units', reference.units, tuple(re.findall(r'\b(?:PIEZAS?|PZAS?|UNIDADES?|EA|SET)\b', observed.text)), ErrorCategory.UNIT_ERROR),
        ):
            if name=='critical_tokens':
                expected=tuple(v for v in expected if not any(c.golden_value==v for c in reference.source_conflicts))
            if expected:
                # Multisets retain repeated obligations/tokens; reference may be partial.
                exp, act = Counter(expected), Counter(actual)
                correct = sum((exp & act).values())
                measurements[name] = {'correct': correct, 'expected': sum(exp.values()),
                                      'observed': sum(act.values()), 'missing': sum((exp-act).values()),
                                      'extra': sum((act-exp).values())}
                if exp-act:
                    errors.add(category.value)
        from app.document_intelligence_calibration_fidelity import compare_fragments,compare_equipment
        findings = [] if failed else compare_fragments(observed.text,reference)
        omissions = None if failed else sum(f['kind']=='MATERIAL_TEXT_OMISSION' for f in findings)
        measurements['material_omissions'] = omissions
        for finding in findings:
            category={'IDENTIFIER_MISMATCH':'IDENTIFIER_ERROR','CRITICAL_TOKEN_MISMATCH':'IDENTIFIER_ERROR',
                      'NUMERIC_MISMATCH':'NUMERIC_ERROR','UNIT_MISMATCH':'UNIT_ERROR'}.get(finding['kind'])
            if category:
                errors.add(category)
        if reference.equipment_rows and not failed:
            equipment=compare_equipment(observed.text,reference)
            measurements['equipment_rows_preserved']=equipment['preserved_rows']
            measurements['equipment_rows_expected']=equipment['expected_rows']
            measurements['equipment_quantity_matches']=equipment['quantity_matches']
            measurements['equipment_unit_matches']=equipment['unit_matches']
            measurements['equipment_model_matches']=equipment['model_matches']
            for row in equipment['rows']:
                for finding in row['findings']:
                    category={'NUMERIC_MISMATCH':'NUMERIC_ERROR','UNIT_MISMATCH':'UNIT_ERROR','IDENTIFIER_MISMATCH':'IDENTIFIER_ERROR'}.get(finding['kind'])
                    if category:
                        errors.add(category)
        if failed:
            errors.add(ErrorCategory.OTHER.value)
        if omissions:
            errors.add(ErrorCategory.TRANSCRIPTION_OMISSION.value)
        for kind, expected in sorted(reference.identifiers.items()):
            expected=tuple(v for v in expected if not any(c.golden_value==v for c in reference.source_conflicts))
            if not expected:
                continue
            exp, act = Counter(expected), Counter(observed.identifiers.get(kind, ()))
            measurements['identifier:' + kind] = {'correct': sum((exp & act).values()),
                'missing': sum((exp-act).values()), 'false': sum((act-exp).values()) if reference.exhaustive_identifiers else None}
            if exp-act or reference.exhaustive_identifiers and act-exp:
                errors.add(ErrorCategory.IDENTIFIER_ERROR.value)
        for field, expected in sorted(reference.structure.items()):
            equal = field in observed.structure and observed.structure[field] == expected
            measurements['structure:' + field] = equal
            if not equal:
                errors.add(ErrorCategory.CONTINUITY_ERROR.value if 'continu' in field or 'outgoing' in field else ErrorCategory.STRUCTURE_BOUNDARY_ERROR.value)
        for field, category in [('quantity_bindings', ErrorCategory.QUANTITY_BINDING_ERROR), ('attribute_bindings', ErrorCategory.ATTRIBUTE_BINDING_ERROR)]:
            expected = getattr(reference, field)
            if expected:
                equal = Counter(expected) == Counter(getattr(observed, field))
                measurements[field] = equal
                if not equal:
                    errors.add(category.value)
        if reference.expected_routing is not None:
            measurements['routing_correct'] = reference.expected_routing == observed.routing_status
            if reference.expected_routing == 'RESOLVED' and observed.routing_status == 'REVIEW_REQUIRED' and not errors:
                errors.add(ErrorCategory.UNNECESSARY_REVIEW.value)
    if observed.conflicts:
        errors.add(ErrorCategory.PROVIDER_CONFLICT.value)
    stale = observed.continuity_status == 'UNKNOWN' and observed.outgoing_item_key is not None
    if stale:
        errors.add(ErrorCategory.CONTINUITY_ERROR.value)
    wrong = bool(errors - {ErrorCategory.UNNECESSARY_REVIEW.value})
    unsafe_selection = active and observed.routing_status == 'RESOLVED' and wrong
    # Routing certainty alone is not evidence that a domain engine trusted the input.
    unsafe = active and observed.domain_input_trusted is True and wrong
    reviewed = active and observed.routing_status == 'REVIEW_REQUIRED'
    # Only a demonstrably expected material fact qualifies; conflicts/formatting alone do not.
    material_error = bool(errors & {'TRANSCRIPTION_OMISSION','IDENTIFIER_ERROR','NUMERIC_ERROR','UNIT_ERROR',
                                   'QUANTITY_BINDING_ERROR','ATTRIBUTE_BINDING_ERROR','STRUCTURE_BOUNDARY_ERROR','CONTINUITY_ERROR'})
    safe_miss = reviewed and labeled and (material_error or failed and bool(reference.material_fragments or reference.equipment_rows))
    if unsafe_selection:
        errors.add(ErrorCategory.UNSAFE_AUTO_SELECTION.value)
    if safe_miss:
        errors.add(ErrorCategory.CORRECT_REVIEW_ESCALATION.value)
    if labeled and reference.expected_routing == 'UNAVAILABLE' and observed.routing_status == 'UNAVAILABLE':
        errors.add(ErrorCategory.UNAVAILABLE_EXPECTED.value)
    return {'observed': observed.model_dump(mode='json'), 'expected': reference.model_dump(mode='json') if reference else None,
        'status': 'DIAGNOSTIC_ONLY' if not labeled else ('ERROR' if wrong else 'MATCH'),
        'criticality': 'CONTRACTUAL' if wrong else 'DIAGNOSTIC', 'error_category': sorted(errors),
        'review_surfaced': reviewed, 'unsafe_trusted_contractual_errors': int(unsafe),
        'safe_misses': int(safe_miss), 'stale_carry_violations': int(stale),
        'measurements': measurements,
        'domain_impact': list(observed.domain_impact) if wrong else [],
        'domain_errors': sorted(e.value for e in observed.domain_errors),
        'fidelity_findings': findings if labeled else [],
        'error_origin': 'DOMAIN_ENGINE' if observed.domain_errors else 'VALIDATION_FAILED' if failed else (('PERCEPTION' if labeled else 'UNDETERMINED') if wrong else None)}


def aggregate(results: list[dict]) -> dict:
    active = [r for r in results if r['observed']['lineage'] == 'ACTIVE']
    categories = Counter(c for r in active for c in r['error_category'])
    domains = Counter(d for r in active for d in r['domain_impact'])
    totals = Counter()
    for row in active:
        for field, measure in row['measurements'].items():
            if isinstance(measure, dict):
                for key, value in measure.items():
                    if value is not None:
                        totals[field + ':' + key] += value
            elif isinstance(measure, bool):
                totals[field + ':correct'] += int(measure)
                totals[field + ':labeled'] += 1
            elif isinstance(measure, int):
                totals[field] += measure
    precision_recall = {}
    for field in ('critical_tokens', 'numeric_tokens', 'units'):
        correct, expected, count = (totals[field+':'+k] for k in ('correct','expected','observed'))
        precision_recall[field] = {'recall': correct / expected if expected else None,
            # Partial golden reference cannot prove precision over an entire page.
            'precision': None, 'matched_observed_fraction': correct / count if count else None}
    return {'active_observations': len(active), 'deselected_observations': len(results)-len(active),
        'labeled_observations': sum(r['status'] != 'DIAGNOSTIC_ONLY' for r in active),
        'unsafe_trusted_contractual_errors': sum(r['unsafe_trusted_contractual_errors'] for r in active),
        'domain_trust_assessed': sum(r['observed']['domain_input_trusted'] is not None for r in active),
        'domain_trust_unassessed': sum(r['observed']['domain_input_trusted'] is None for r in active),
        'domain_engine_error_count': sum(len(r['domain_errors']) for r in active),
        'safe_misses': sum(r['safe_misses'] for r in active),
        'stale_carry_violations': sum(r['stale_carry_violations'] for r in active),
        'unsafe_auto_selections': categories['UNSAFE_AUTO_SELECTION'],
        'correct_review_required': categories['CORRECT_REVIEW_ESCALATION'],
        'unnecessary_review': categories['UNNECESSARY_REVIEW'],
        'safe_automatic_selections': sum(r['status']=='MATCH' and r['observed']['routing_status']=='RESOLVED' for r in active),
        'error_categories': dict(sorted(categories.items())), 'domain_impact': dict(sorted(domains.items())),
        'measurements': dict(sorted(totals.items())), 'transcription': precision_recall,
        'readiness_certified': False}


def analyze(observations: list[Observation], references: dict[tuple[str, int], Reference]) -> dict:
    results = [evaluate(o, references.get((o.document_id,o.page_number))) for o in sorted(observations,
        key=lambda o:(o.document_id,o.page_number,o.capability.value,o.provider,o.artifact_id))]
    groups = sorted({(o.provider, o.capability.value) for o in observations})
    return {'schema_version': '1', 'tender_id': TENDER_ID, 'external_reference': TENDER_REFERENCE,
            'results': results, 'aggregate': aggregate(results),
            'by_provider_capability': {provider+':'+cap: aggregate([r for r in results
                if r['observed']['provider']==provider and r['observed']['capability']==cap]) for provider,cap in groups}}


def inventory(db: Session) -> dict:
    tender = db.get(Tender, TENDER_ID)
    if tender is None or tender.external_reference != TENDER_REFERENCE:
        raise ValueError('Authorized Tender #001 absent or identity mismatch')
    documents = db.scalars(select(TenderDocument).where(TenderDocument.tender_id == TENDER_ID).order_by(TenderDocument.id)).all()
    records = []
    for doc in documents:
        trans = load_document_transcriptions(db, doc)
        for page in db.scalars(select(DocumentPage).where(DocumentPage.document_id==doc.id).order_by(DocumentPage.page_number)):
            ocr = db.scalars(select(PageOcrResult).where(PageOcrResult.document_page_id==page.id).order_by(PageOcrResult.id)).all()
            vision = db.execute(select(DocumentVisionPageResult,DocumentVisionAnalysis).join(DocumentVisionAnalysis).where(
                DocumentVisionPageResult.document_page_id==page.id,DocumentVisionAnalysis.tender_id==TENDER_ID).order_by(DocumentVisionPageResult.id)).all()
            impacts = {}
            for name, model in [('Requirements',RequirementCandidateEvidence),('Scope',TenderScopeDetail),
                                ('Quantity',TenderScopeQuantity),('Attribute',TenderScopeAttribute)]:
                impacts[name] = len(db.scalars(select(model.id).where(model.source_document_id==doc.id,model.document_page_id==page.id)).all())
            # Requested evidence is measured through the requirement interpretation bridge, not assumed from filename.
            impacts['requested_Evidence'] = len(db.scalars(select(RequirementEvidenceExpectation).where(
                RequirementEvidenceExpectation.source_document_id==doc.id,
                RequirementEvidenceExpectation.source_page==page.page_number)).all())
            struct = load_page_structure(db,doc,page)
            records.append({'document_id':doc.id,'filename':doc.original_filename,'revision':doc.revision_number,
                'current':doc.is_current,'document_sha256':doc.sha256,'page_number':page.page_number,'page_id':page.id,
                'profile':page.content_profile,'native_chars':len(page.text),'domain_inputs':impacts,
                'ocr':[{'id':o.id,'provider':o.engine,'version':o.engine_version,'status':o.status,'scope':o.scope,'latency_ms':o.processing_time_ms} for o in ocr],
                'vision':[{'id':v.id,'analysis_id':a.id,'model':a.model_name,'prompt':a.prompt_version,'status':v.status,'latency_ms':v.processing_time_ms} for v,a in vision],
                'transcription':trans[page.id].model_dump(mode='json'), 'structure':struct.model_dump(mode='json')})
    return {'tender_id':TENDER_ID,'external_reference':TENDER_REFERENCE,
        'documents':[{'id':d.id,'filename':d.original_filename,'pages_declared':d.page_count,'revision':d.revision_number,'current':d.is_current} for d in documents],
        'total_documents':len(documents),'total_pages':len(records),'profiles':dict(sorted(Counter(r['profile'] for r in records).items())), 'pages':records}


def observations_from_inventory(data: dict, provider: str, capability: Capability, document_id: str | None = None,
                                pages: tuple[int,...] = ()) -> list[Observation]:
    out = []
    previous = None
    previous_doc = None
    for row in sorted(data['pages'],key=lambda r:(r['document_id'],r['page_number'])):
        if document_id and row['document_id'] != document_id or pages and row['page_number'] not in pages:
            continue
        trans = RoutingResult.model_validate(row['transcription'])
        struct = RoutingResult.model_validate(row['structure'])
        source_result = trans if capability == Capability.TRANSCRIPTION else struct
        def source_provider(source):
            metadata = dict(source.provider_metadata)
            if source.source_method.value == 'OCR':
                artifact = next((o for o in row.get('ocr',()) if 'ocr-result:'+o['id']==source.source_artifact_key),None)
                return metadata.get('engine') or (artifact['provider'] if artifact else 'OCR_UNSPECIFIED')
            return source.source_method.value
        sources = tuple(s for s in source_result.candidates if provider=='ALL' or s.source_method.value==provider or source_provider(s)==provider)
        routing = route_capability(page=source_result.page,capability=capability,evidence=sources)
        if capability == Capability.STRUCTURE:
            routing = guard_structure(routing,page_identifier_comparisons(trans,routing))
            if previous_doc != row['document_id']:
                previous = None
            previous = advance_continuity(routing,previous)
            previous_doc = row['document_id']
        observed_sources = sources or (None,)
        for source in observed_sources:
            # Individual fidelity is kept separate from page routing; a different source's selection never trusts this one.
            trusted = source is not None and routing.selected == source and routing.status=='RESOLVED'
            if capability == Capability.STRUCTURE and previous.status == 'UNKNOWN':
                trusted = False
            identifiers: dict[str,tuple[str,...]] = {}
            if source:
                for comparison in page_identifier_comparisons(route_capability(page=source.page,capability=capability,evidence=(source,))):
                    identifiers[comparison.kind.value] = tuple(sorted(set((*identifiers.get(comparison.kind.value,()),*(o.raw_value for o in comparison.observations)))))
            out.append(Observation(provider=source_provider(source) if source else provider,
                model=dict(source.provider_metadata).get('model') if source else None,capability=capability,
                document_id=row['document_id'],page_number=row['page_number'],artifact_id=source.generation_id if source else 'unavailable',
                text=source.text if source else '',identifiers=identifiers,
                critical_tokens=tuple(value for values in identifiers.values() for value in values),
                routing_status='RESOLVED' if trusted else ('REVIEW_REQUIRED' if source and source.quality.value not in {'FAILED','UNAVAILABLE'} else 'UNAVAILABLE'),
                lineage=source.lineage if source else 'ACTIVE', conflicts=tuple(c.kind for c in routing.conflicts),
                structure=asdict(source.structural_state) if source and source.structural_state else {},
                continuity_status=previous.status if capability==Capability.STRUCTURE else None,
                outgoing_item_key=previous.outgoing_item_key if capability==Capability.STRUCTURE else None,
                domain_impact=tuple(k for k,v in row['domain_inputs'].items() if v),
                provenance=source.model_dump(mode='json') if source else {},notes=(f'PAGE_ROUTING:{routing.status}',)))
    return out
