"""Native procurement proposals; perception availability never certifies semantics."""
from app.item_identity import normalize_item_identity
from app.native_scope_evidence import NATIVE_SCOPE_VERSION, native_locator, procurement_rows, explicit_fields
from app.scope_detail_adapters import ScopeDetailEvidenceCandidate


class NativeScopeDetailAdapter:
    adapter_name = 'NativeScopeDetailAdapter'
    adapter_version = NATIVE_SCOPE_VERSION

    def supports(self, artifact):
        return artifact.source_method == 'NATIVE' and bool((artifact.payload or {}).get('normalized_content_id'))

    def extract_candidates(self, db, artifact):
        text = (artifact.payload or {}).get('text', '')
        structure = artifact.structure
        trusted_keys = set()
        if structure is not None and structure.status == 'RESOLVED' and structure.selected is not None:
            trusted_keys = {s.item_identity.normalized_key for s in structure.selected.structural_state.segments if not s.review_required}
        candidates = []
        for row in procurement_rows(text):
            locator = native_locator(db, artifact, row.start, row.end)
            key = normalize_item_identity(row.item_raw).normalized_key
            owner = key if key in trusted_keys else None
            fields = explicit_fields(row.text)
            candidates.append(ScopeDetailEvidenceCandidate(
                tender_id=artifact.tender_id, source_document_id=artifact.source_document_id,
                document_page_id=artifact.document_page_id, domain=row.domain, detail_type='DETAIL',
                description=row.text, applicability='ITEM' if owner else 'UNRESOLVED',
                candidate_item_key=owner, source_method='NATIVE', source_artifact_key=artifact.source_artifact_key,
                source_contract_version=f'{artifact.source_contract_version}/{NATIVE_SCOPE_VERSION}', source_locator=locator, source_excerpt=row.text,
                review_required=True, confidence=None, quantity_raw=fields.get('quantity'), unit_raw=fields.get('unit'),
                attribute_bindings=tuple((name, fields[name]) for name in ('brand', 'model') if name in fields)))
        return candidates
