"""OCR consumers reuse only the bounded textual grammar, never Native provenance."""
from decimal import Decimal
import re
from app.native_scope_evidence import procurement_rows, explicit_fields
from app.ocr_scope_evidence import OCR_SCOPE_VERSION, ocr_locator
from app.item_identity import normalize_item_identity
from app.scope_detail_adapters import ScopeDetailEvidenceCandidate
from app.scope_attributes import ScopeAttributeCandidate
from app.scope_quantities import ScopeQuantityCandidate
from app.scope_quantity_adapters import _unit_to_measure_kind


class OcrScopeDetailAdapter:
    adapter_name = 'OcrScopeDetailAdapter'
    adapter_version = OCR_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'OCR' and bool((artifact.payload or {}).get('normalized_content_id'))

    def extract_candidates(self, db, artifact):
        structure = artifact.structure
        keys = set()
        if structure and structure.status == 'RESOLVED' and structure.selected:
            keys = {s.item_identity.normalized_key for s in structure.selected.structural_state.segments if not s.review_required}
        candidates = []
        for row in procurement_rows(artifact.payload['text']):
            locator = ocr_locator(db, artifact, row.start, row.end)
            key = normalize_item_identity(row.item_raw).normalized_key
            owner = key if key in keys else None
            fields = explicit_fields(row.text)
            candidates.append(ScopeDetailEvidenceCandidate(
                tender_id=artifact.tender_id, source_document_id=artifact.source_document_id,
                document_page_id=artifact.document_page_id, domain=row.domain, detail_type='DETAIL', description=row.text,
                applicability='ITEM' if owner else 'UNRESOLVED', candidate_item_key=owner,
                source_method='OCR', source_artifact_key=artifact.source_artifact_key,
                source_contract_version=f'{artifact.source_contract_version}/{OCR_SCOPE_VERSION}',
                source_locator=locator, source_excerpt=row.text, review_required=True, confidence=None,
                quantity_raw=fields.get('quantity'), unit_raw=fields.get('unit'),
                attribute_bindings=tuple((name, fields[name]) for name in ('brand','model') if name in fields)))
        return candidates


def _fields(artifact):
    if not artifact.payload.get('valid_scope_identity'):
        return {}
    return explicit_fields(artifact.payload['scope_excerpt'])


def _source(artifact):
    return dict(tender_id=artifact.tender_id, scope_detail_id=artifact.scope_detail_id,
        source_document_id=artifact.source_document_id, document_page_id=artifact.document_page_id,
        source_method='OCR', source_artifact_key=artifact.source_artifact_key,
        source_locator=artifact.source_locator, source_excerpt=artifact.payload['scope_excerpt'],
        source_contract_version=artifact.source_contract_version, review_required=True, confidence=None)


class OcrScopeAttributeAdapter:
    adapter_name = 'OcrScopeAttributeAdapter'
    adapter_version = OCR_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'OCR' and (artifact.payload or {}).get('source_scope') == 'OCR_SCOPE_ROW'

    def extract_candidates(self, db, artifact):
        fields = _fields(artifact)
        return tuple(ScopeAttributeCandidate(**{**_source(artifact), 'source_locator': artifact.source_locator + '|attr:' + name},
            attribute_name=name, value_raw=fields[name], relation='UNSPECIFIED') for name in ('brand','model') if name in fields)


class OcrScopeQuantityAdapter:
    adapter_name = 'OcrScopeQuantityAdapter'
    adapter_version = OCR_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'OCR' and (artifact.payload or {}).get('source_scope') == 'OCR_SCOPE_ROW'

    def extract_candidates(self, db, artifact):
        fields = _fields(artifact)
        raw,unit = fields.get('quantity',''),fields.get('unit','')
        kind = _unit_to_measure_kind(unit)
        if not re.fullmatch(r'\d+(?:\.\d+)?',raw) or not kind:
            return ()
        return (ScopeQuantityCandidate(**_source(artifact), quantity_raw=raw, quantity_value=Decimal(raw),
                unit_raw=unit, measure_kind=kind, relation='EXACT'),)
