from app.native_scope_evidence import NATIVE_SCOPE_VERSION, explicit_fields
from app.scope_attributes import ScopeAttributeCandidate


class NativeScopeAttributeAdapter:
    adapter_name = 'NativeScopeAttributeAdapter'
    adapter_version = NATIVE_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'NATIVE' and (artifact.payload or {}).get('source_scope') == 'NATIVE_SCOPE_ROW'

    def extract_candidates(self, db, artifact):
        del db
        if not (artifact.payload or {}).get('valid_scope_identity'):
            return ()
        text = artifact.payload['scope_excerpt']
        fields = explicit_fields(text)
        return tuple(ScopeAttributeCandidate(
            tender_id=artifact.tender_id, scope_detail_id=artifact.scope_detail_id,
            source_document_id=artifact.source_document_id, document_page_id=artifact.document_page_id,
            attribute_name=name, value_raw=fields[name], relation='UNSPECIFIED',
            source_method='NATIVE', source_artifact_key=artifact.source_artifact_key,
            source_locator=artifact.source_locator + '|attr:' + name, source_excerpt=text,
            source_contract_version=artifact.source_contract_version, review_required=artifact.scope_detail_review_required,
            confidence=None) for name in ('brand', 'model') if name in fields)
