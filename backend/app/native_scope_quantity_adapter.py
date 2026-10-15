import re
from decimal import Decimal
from app.native_scope_evidence import NATIVE_SCOPE_VERSION, explicit_fields
from app.scope_quantities import ScopeQuantityCandidate
from app.scope_quantity_adapters import _unit_to_measure_kind


class NativeScopeQuantityAdapter:
    adapter_name = 'NativeScopeQuantityAdapter'
    adapter_version = NATIVE_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'NATIVE' and (artifact.payload or {}).get('source_scope') == 'NATIVE_SCOPE_ROW'

    def extract_candidates(self, db, artifact):
        del db
        if not (artifact.payload or {}).get('valid_scope_identity'):
            return ()
        text = artifact.payload['scope_excerpt']
        fields = explicit_fields(text)
        raw, unit = fields.get('quantity', ''), fields.get('unit', '')
        # No locale guessing, monetary parsing, implicit units or range flattening.
        if not re.fullmatch(r'\d+(?:\.\d+)?', raw) or not unit:
            return ()
        kind = _unit_to_measure_kind(unit)
        if kind is None:
            return ()
        return (ScopeQuantityCandidate(
            tender_id=artifact.tender_id, scope_detail_id=artifact.scope_detail_id,
            source_document_id=artifact.source_document_id, document_page_id=artifact.document_page_id,
            quantity_raw=raw, quantity_value=Decimal(raw), unit_raw=unit, measure_kind=kind,
            relation='EXACT', source_method='NATIVE', source_artifact_key=artifact.source_artifact_key,
            source_locator=artifact.source_locator, source_excerpt=text, source_contract_version=artifact.source_contract_version,
            review_required=artifact.scope_detail_review_required, confidence=None),)
