"""Exact OCR grounding without synthetic Native or Vision identities."""
from __future__ import annotations
import hashlib
from sqlalchemy import select
from app.models import DocumentPage, TenderDocument, PageOcrResult, NormalizedContent
from app.content_normalization import _normalize_text

OCR_SCOPE_VERSION = 'ocr-scope-v1'


def source_generation(db, result_id):
    row = db.get(PageOcrResult, result_id)
    if row is None or row.status != 'OCR_TEXT_EXTRACTED' or not row.text.strip():
        raise ValueError('OCR_SOURCE_UNAVAILABLE')
    sources = db.scalars(select(NormalizedContent).where(NormalizedContent.page_ocr_result_id == row.id,
        NormalizedContent.source_type == 'OCR')).all()
    if len(sources) != 1:
        raise ValueError('OCR_NORMALIZED_GENERATION_AMBIGUOUS_OR_MISSING')
    n = sources[0]
    if (n.document_page_id != row.document_page_id or n.region_id != row.region_id or n.engine != row.engine
            or n.normalized_text != _normalize_text(row.text)
            or hashlib.sha256(n.normalized_text.encode()).hexdigest() != n.content_sha256):
        raise ValueError('OCR_NORMALIZED_GENERATION_MISMATCH')
    return row, n


def ocr_locator(db, artifact, start, end):
    row,n = source_generation(db, artifact.source_artifact_key.removeprefix('ocr-result:'))
    page = db.get(DocumentPage, row.document_page_id)
    document = db.get(TenderDocument, page.document_id)
    if page.id != artifact.document_page_id or document.id != artifact.source_document_id or document.tender_id != artifact.tender_id:
        raise ValueError('OCR_SOURCE_IDENTITY_MISMATCH')
    fingerprint = task_fingerprint(db, row)
    return (f'page:{page.page_number}|ocr_scope:1|normalized:{n.id}|sha256:{n.content_sha256}'
            f'|ocr_sha256:{hashlib.sha256(row.text.encode()).hexdigest()}|span:{start}:{end}|revision:{document.revision_number}'
            + (f'|task:{fingerprint}' if fingerprint else ''))


def resolve_ocr_scope_payload(db, detail):
    tokens = dict(t.split(':',1) for t in detail.source_locator.split('|') if ':' in t)
    if tokens.get('ocr_scope') != '1':
        return {'source_scope': 'LEGACY_OCR_UNVERSIONED'}
    row,n = source_generation(db, detail.source_artifact_key.removeprefix('ocr-result:'))
    page = db.get(DocumentPage, detail.document_page_id)
    document = db.get(TenderDocument, detail.source_document_id)
    if (row.document_page_id != page.id or page.document_id != document.id
            or document.tender_id != detail.tender_id or tokens.get('page') != str(page.page_number)
            or tokens.get('revision') != str(document.revision_number)):
        raise ValueError('OCR_SOURCE_IDENTITY_MISMATCH')
    if tokens.get('normalized') != n.id or tokens.get('sha256') != n.content_sha256 or tokens.get('ocr_sha256') != hashlib.sha256(row.text.encode()).hexdigest():
        raise ValueError('OCR_GENERATION_HASH_MISMATCH')
    if tokens.get('task') and tokens['task'] != task_fingerprint(db, row):
        raise ValueError('OCR_TASK_FINGERPRINT_MISMATCH')
    if detail.source_contract_version != f'{row.engine_version}/{OCR_SCOPE_VERSION}':
        raise ValueError('OCR_ENGINE_VERSION_MISMATCH')
    try:
        start,end = map(int,tokens['span'].split(':'))
    except (KeyError,ValueError) as exc:
        raise ValueError('OCR_SPAN_INVALID') from exc
    if not 0 <= start < end <= len(row.text) or row.text[start:end] != detail.source_excerpt:
        raise ValueError('OCR_SPAN_GROUNDING_MISMATCH')
    return dict(source_scope='OCR_SCOPE_ROW', scope_excerpt=row.text[start:end],
                valid_scope_identity=detail.applicability == 'ITEM' and bool(detail.candidate_item_key or detail.scope_segment_id or detail.tender_item_id))


def task_fingerprint(db, row):
    """Legacy OCR has no receipt: never invent its task/image identity."""
    import json
    from app.selective_ocr_executor import receipt_root, source_slot, _hash, _bytes
    path = receipt_root() / (source_slot(row.document_page_id, row.engine, row.region_id) + '.json')
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_text())
        identity = receipt['identity']
        page = db.get(DocumentPage, row.document_page_id)
        document = db.get(TenderDocument, page.document_id)
        if (receipt['result_id'] != row.id or receipt['text_sha256'] != _hash(row.text.encode())
                or receipt['status'] != row.status or identity['engine_version'] != row.engine_version
                or identity['engine'] != row.engine or identity['language'] != row.language
                or identity['page_id'] != row.document_page_id or identity['region_id'] != row.region_id
                or identity['original_sha256'] != document.sha256 or identity['revision'] != document.revision_number
                or receipt['fingerprint'] != _hash(_bytes({**identity,'image_sha256':receipt['image_sha256']}))):
            raise ValueError('OCR_RECEIPT_GROUNDING_MISMATCH')
        return receipt['fingerprint']
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError('INVALID_OCR_RECEIPT') from exc
