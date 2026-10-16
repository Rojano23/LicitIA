"""Source-bound reconstruction and fail-closed multispan provenance resolution."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import re
from decimal import Decimal

from app.structured_evidence import (EvidenceSource, StructuredEvidenceManifest,
    POLICY_VERSION, reconstruct)
from app.structured_evidence_storage import write_manifest, read_manifest, digest_from_locator


def is_structured(locator: str) -> bool:
    return any(token.startswith('se:') for token in (locator or '').split('|'))


def source_text(db, artifact):
    from app.models import DocumentPage, TenderDocument, NormalizedContent
    from app.document_intelligence_sources import transcription_from_artifact
    from app.document_intelligence import Quality
    page = db.get(DocumentPage, artifact.document_page_id)
    document = db.get(TenderDocument, artifact.source_document_id)
    observation = transcription_from_artifact(db, artifact)
    if observation.quality == Quality.FAILED or (observation.quality == Quality.UNAVAILABLE and artifact.source_method != 'VISION'):
        raise ValueError('STRUCTURED_SOURCE_UNAVAILABLE')
    text = observation.text
    acquisition = ()
    scope,region_id = 'UNKNOWN',None
    if artifact.source_method == 'NATIVE':
        from app.native_scope_evidence import _validate_generation
        n = db.get(NormalizedContent, (artifact.payload or {}).get('normalized_content_id'))
        if n is None:
            raise ValueError('STRUCTURED_GENERATION_MISSING')
        _validate_generation(db,n,document.id,page.id)
        if n.normalized_text.strip() != (artifact.payload or {}).get('text', '').strip():
            raise ValueError('STRUCTURED_NORMALIZED_TEXT_MISMATCH')
        text = n.normalized_text
        generation = n.id
        scope = 'FULL_PAGE'
    elif artifact.source_method == 'OCR':
        from app.ocr_scope_evidence import source_generation, task_fingerprint
        row,n = source_generation(db,artifact.source_artifact_key.removeprefix('ocr-result:'))
        scope = 'FULL_PAGE' if row.scope == 'FULL_PAGE' and not row.region_id else 'REGION' if row.region_id else 'UNKNOWN'
        region_id = row.region_id
        fingerprint = task_fingerprint(db,row)  # Validate any existing execution receipt.
        acquisition = tuple((key,str(value or '')) for key,value in (
            ('engine',row.engine),('engine_version',row.engine_version),('language',row.language),
            ('region_id',row.region_id),('scope',row.scope),('task_fingerprint',fingerprint),
            ('raw_text_sha256',hashlib.sha256(row.text.encode()).hexdigest())))
        text = n.normalized_text  # All offsets explicitly use NORMALIZED_TEXT.
        generation = n.id
    else:
        detail = (artifact.payload or {}).get('detail_transcription')
        if not isinstance(detail,dict) or detail.get('task_type') != 'DETAIL_TRANSCRIPTION':
            raise ValueError('STRUCTURED_VISION_DETAIL_REQUIRED')
        raw_lines = detail.get('raw_lines')
        if isinstance(raw_lines,list) and raw_lines:
            text = '\n'.join(line['raw_visible_text'] for line in raw_lines
                             if isinstance(line,dict) and isinstance(line.get('raw_visible_text'),str))
        if not text.strip():
            raise ValueError('STRUCTURED_SOURCE_UNAVAILABLE')
        region_id = detail.get('task_region_id')
        scope = 'REGION' if region_id else 'UNKNOWN'
        generation = observation.generation_id
        from app.models import DocumentVisionPageResult
        result = db.get(DocumentVisionPageResult,artifact.source_page_result_id)
        acquisition = tuple((str(k),str(v)) for k,v in observation.provider_metadata) + (
            ('image_sha256',result.image_sha256),('analysis_id',result.analysis_id),
            ('task_fingerprint',str(detail.get('task_fingerprint') or '')))
    return EvidenceSource(tender_id=document.tender_id,document_id=document.id,page_id=page.id,
        page_number=page.page_number,revision=document.revision_number,method=artifact.source_method,
        artifact_key=artifact.source_artifact_key,generation_id=generation,text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        offset_space='VISION_RAW_LINES' if artifact.source_method == 'VISION' else 'NORMALIZED_TEXT',
        contract_version=artifact.source_contract_version,original_sha256=document.sha256,
        acquisition_identity=acquisition,source_scope=scope,region_id=region_id), text


def _locator(block, digest):
    s = block.source
    locator = (f'page:{s.page_number}|revision:{s.revision}|generation:{s.generation_id}'
               f'|method:{s.method}|se:1:{digest}|block:0')
    if len(locator) > 512:
        raise ValueError('STRUCTURED_LOCATOR_LIMIT')
    return locator


def extract_candidates(db, artifact):
    from app.item_identity import normalize_item_identity
    from app.scope_detail_adapters import ScopeDetailEvidenceCandidate
    try:
        source,text = source_text(db,artifact)
    except ValueError as exc:
        if str(exc) == 'STRUCTURED_SOURCE_UNAVAILABLE':
            return ()
        raise
    candidates = []
    for block in reconstruct(source,text):
        digest = write_manifest(StructuredEvidenceManifest(blocks=(block,)))
        representative = block.fragment(block.field('description').refs[0]).text
        fields = {f.name:f.value for f in block.fields}
        owner = normalize_item_identity(block.item_raw).normalized_key if block.state == 'SUPPORTED' else None
        candidates.append(ScopeDetailEvidenceCandidate(tender_id=artifact.tender_id,
            source_document_id=artifact.source_document_id,document_page_id=artifact.document_page_id,
            domain=block.domain,detail_type='DETAIL',description=fields['description'],
            applicability='ITEM' if owner else 'UNRESOLVED',candidate_item_key=owner,
            source_method=source.method,source_artifact_key=source.artifact_key,
            source_contract_version=POLICY_VERSION,source_locator=_locator(block,digest),
            source_excerpt=representative,review_required=True,confidence=None,
            source_analysis_id=artifact.source_analysis_id,source_page_result_id=artifact.source_page_result_id,
            quantity_raw=fields.get('quantity'),unit_raw=fields.get('unit'),
            attribute_bindings=tuple((k,fields[k]) for k in ('brand','model') if k in fields),
            structured_block=block))
    return tuple(candidates)


def validate_manifest(db, digest):
    """Re-enumerate active generations, verify each exact fragment and relation.

    Re-running the deterministic interpreter proves role/ownership edges as well
    as literal offsets. A forged, hash-valid arbitrary relationship is rejected.
    """
    from app.models import DocumentPage
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    manifest = read_manifest(digest)
    for block in manifest.blocks:
        s = block.source
        page = db.get(DocumentPage,s.page_id)
        if page is None or page.document_id != s.document_id:
            raise ValueError('STRUCTURED_PAGE_IDENTITY_MISMATCH')
        enumerated = _enumerate_persisted_artifacts_for_document(db,tender_id=s.tender_id,
            document_id=s.document_id,pages=[page])
        artifact = next((a.artifact for a in enumerated.active if a.artifact.source_artifact_key == s.artifact_key),None)
        if artifact is None:
            raise ValueError('STRUCTURED_SOURCE_NOT_ACTIVE')
        current,text = source_text(db,artifact)
        if current != s:
            raise ValueError('STRUCTURED_GENERATION_STALE')
        if any(not 0 <= f.start < f.end <= len(text) or text[f.start:f.end] != f.text for f in block.fragments):
            raise ValueError('STRUCTURED_FRAGMENT_MISMATCH')
        if block not in reconstruct(current,text):
            raise ValueError('STRUCTURED_RELATIONSHIP_MISMATCH')
    primary = manifest.blocks[0]
    if any((b.source.tender_id,b.source.document_id,b.source.page_id,fact_key(b)) !=
           (primary.source.tender_id,primary.source.document_id,primary.source.page_id,fact_key(primary))
           for b in manifest.blocks):
        raise ValueError('STRUCTURED_INCOMPARABLE_SUPPORT')
    return manifest


def resolve_payload(db, detail):
    manifest = validate_manifest(db,digest_from_locator(detail.source_locator))
    block = manifest.blocks[0]
    s = block.source
    if (s.tender_id,s.document_id,s.page_id,s.method,s.artifact_key) != (
            detail.tender_id,detail.source_document_id,detail.document_page_id,detail.source_method,detail.source_artifact_key):
        raise ValueError('STRUCTURED_PRIMARY_SOURCE_MISMATCH')
    expected = _locator(block,digest_from_locator(detail.source_locator))
    if detail.source_locator.split('|occurrence:')[0] != expected:
        raise ValueError('STRUCTURED_LOCATOR_IDENTITY_MISMATCH')
    if detail.source_contract_version != POLICY_VERSION:
        raise ValueError('STRUCTURED_CONTRACT_MISMATCH')
    if detail.source_excerpt != block.fragment(block.field('description').refs[0]).text:
        raise ValueError('STRUCTURED_REPRESENTATIVE_MISMATCH')
    from app.item_identity import normalize_item_identity
    valid = (block.state == 'SUPPORTED' and detail.applicability == 'ITEM'
             and detail.candidate_item_key == normalize_item_identity(block.item_raw).normalized_key)
    return {'source_scope':'STRUCTURED_EVIDENCE_BLOCK','structured_block':block,
            'manifest':manifest,'valid_scope_identity':valid}


def fact_key(block):
    # Exact values and occurrence only; no paraphrase/fuzzy matching. Quantity
    # and attributes are compared separately for conflicts at the same anchor.
    source = block.source
    scope = (source.source_scope, source.region_id if source.source_scope == 'REGION' else
             source.artifact_key if source.source_scope == 'UNKNOWN' else '')
    return (scope,block.item_raw,block.occurrence,block.domain,
            tuple(' '.join(block.fragment(ref).text.split()) for ref in block.field('description').refs))


def merge_proofs(chosen, group):
    blocks = [chosen.structured_block]
    blocks += sorted({c.structured_block.model_dump_json():c.structured_block for c in group
                      if c.structured_block != chosen.structured_block}.values(),key=lambda b:b.model_dump_json())
    digest = write_manifest(StructuredEvidenceManifest(blocks=tuple(blocks)))
    return replace(chosen,source_locator=_locator(chosen.structured_block,digest))


def corroboration_only(db, old_locator, new_locator):
    if not is_structured(old_locator) or not is_structured(new_locator):
        return False
    # Missing/corrupt historical proof blocks reuse. A hash-valid proof whose
    # generation is no longer active authorizes replacement, never authority carry.
    old_digest = digest_from_locator(old_locator)
    read_manifest(old_digest)
    new = validate_manifest(db,digest_from_locator(new_locator))
    try:
        old = validate_manifest(db,old_digest)
    except ValueError as exc:
        if str(exc) in {'STRUCTURED_GENERATION_STALE','STRUCTURED_SOURCE_NOT_ACTIVE'}:
            return False
        raise
    return old.blocks[0] == new.blocks[0] and all(block in new.blocks for block in old.blocks)


class StructuredAttributeAdapter:
    adapter_name = 'StructuredAttributeAdapter'
    adapter_version = POLICY_VERSION

    def supports(self,artifact):
        return (artifact.payload or {}).get('source_scope') == 'STRUCTURED_EVIDENCE_BLOCK'

    def extract_candidates(self,db,artifact):
        from app.scope_attributes import ScopeAttributeCandidate
        if not artifact.payload['valid_scope_identity']:
            return ()
        block = artifact.payload['structured_block']
        return tuple(ScopeAttributeCandidate(**_child_source(artifact,block.fragment(f.refs[0]).text),
            attribute_name=f.name,value_raw=f.value,relation='UNSPECIFIED')
            for f in block.fields if f.name in {'brand','model'} and len(f.refs) == 1)


class StructuredQuantityAdapter:
    adapter_name = 'StructuredQuantityAdapter'
    adapter_version = POLICY_VERSION

    def supports(self,artifact):
        return (artifact.payload or {}).get('source_scope') == 'STRUCTURED_EVIDENCE_BLOCK'

    def extract_candidates(self,db,artifact):
        from app.scope_quantities import ScopeQuantityCandidate
        from app.scope_quantity_adapters import _unit_to_measure_kind
        if not artifact.payload['valid_scope_identity']:
            return ()
        block = artifact.payload['structured_block']
        q,u = block.field('quantity'),block.field('unit')
        if not q or not u or not re.fullmatch(r'\d+(?:\.\d+)?',q.value) or not _unit_to_measure_kind(u.value):
            return ()
        return (ScopeQuantityCandidate(**_child_source(artifact,block.fragment(q.refs[0]).text),
            quantity_raw=q.value,quantity_value=Decimal(q.value),unit_raw=u.value,
            measure_kind=_unit_to_measure_kind(u.value),relation='EXACT'),)


def _child_source(artifact,excerpt):
    return dict(tender_id=artifact.tender_id,scope_detail_id=artifact.scope_detail_id,
        source_document_id=artifact.source_document_id,document_page_id=artifact.document_page_id,
        source_method=artifact.source_method,source_artifact_key=artifact.source_artifact_key,
        source_contract_version=artifact.source_contract_version,source_analysis_id=artifact.source_analysis_id,
        source_page_result_id=artifact.source_page_result_id,source_locator=artifact.source_locator,
        source_excerpt=excerpt,review_required=True,confidence=None)


def validate_quantity_fields(candidate):
    # Public value validator has no DB argument; materializers/persistence verify
    # generations independently. This checks exact role bindings, never substring
    # membership in a fabricated concatenation.
    manifest = read_manifest(digest_from_locator(candidate.source_locator))
    block = manifest.blocks[0]
    q,u = block.field('quantity'),block.field('unit')
    if not q or not u or candidate.quantity_raw != q.value or candidate.unit_raw != u.value:
        raise ValueError('STRUCTURED_QUANTITY_BINDING_MISMATCH')
    if candidate.source_excerpt != block.fragment(q.refs[0]).text:
        raise ValueError('STRUCTURED_QUANTITY_EXCERPT_MISMATCH')


def validate_persisted_candidate(db, candidate, kind):
    """Domain persistence also enforces the new contract, not just adapters."""
    if not is_structured(candidate.source_locator):
        return
    if kind == 'scope':
        payload = resolve_payload(db,candidate)
        block = payload['structured_block']
        from app.item_identity import normalize_item_identity
        if candidate.candidate_item_key and candidate.candidate_item_key != normalize_item_identity(block.item_raw).normalized_key:
            raise ValueError('STRUCTURED_OWNER_MISMATCH')
        if (candidate.description != block.field('description').value or candidate.domain != block.domain
                or candidate.quantity_raw != (block.field('quantity').value if block.field('quantity') else None)
                or candidate.unit_raw != (block.field('unit').value if block.field('unit') else None)):
            raise ValueError('STRUCTURED_SCOPE_FIELD_MISMATCH')
    else:
        from app.models import TenderScopeDetail
        parent = db.get(TenderScopeDetail,candidate.scope_detail_id)
        if parent is None:
            raise ValueError('STRUCTURED_PARENT_MISSING')
        payload = resolve_payload(db,parent)
        manifest = validate_manifest(db,digest_from_locator(candidate.source_locator))
        if (not payload['valid_scope_identity'] or manifest.blocks[0] != payload['structured_block']
                or candidate.source_method != parent.source_method or candidate.source_artifact_key != parent.source_artifact_key):
            raise ValueError('STRUCTURED_CHILD_OWNER_MISMATCH')
        block = payload['structured_block']
        if kind == 'attribute':
            field = block.field(candidate.attribute_name)
            if (field is None or field.name not in {'brand','model'} or candidate.value_raw != field.value
                    or candidate.source_excerpt != block.fragment(field.refs[0]).text):
                raise ValueError('STRUCTURED_ATTRIBUTE_BINDING_MISMATCH')
        else:
            validate_quantity_fields(candidate)
            if candidate.relation != 'EXACT' or candidate.quantity_value != Decimal(candidate.quantity_raw):
                raise ValueError('STRUCTURED_QUANTITY_VALUE_MISMATCH')
