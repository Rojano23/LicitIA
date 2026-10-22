"""Operational retry gates. Original evidence and provider receipts are never reset."""
from __future__ import annotations
import hashlib
import fcntl
import importlib.metadata
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from app.models import Tender, TenderDocument, DocumentPage, TenderScopeDetail, TenderScopeQuantity


class RetryRead(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    eligible: bool
    fingerprint: str
    reasons: tuple[str, ...]
    effect: Literal['REUSE_AVAILABLE_EVIDENCE'] = 'REUSE_AVAILABLE_EVIDENCE'
    previous_results_preserved: bool = True
    provider_acquisition: Literal[False] = False
    provider_degraded: bool = False


class RetryWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_fingerprint: str


def retry_status(db, tender_id, *, owns_lock=False):
    from fastapi import HTTPException
    from app.main import _resolve_document_file_path, _hash_file, get_licitia_data_root
    from app.workspace_flow import _context, _processing, _documents
    from app.structured_evidence_grounding import validate_persisted_candidate
    if db.get(Tender, tender_id) is None: raise HTTPException(404, 'Tender not found')
    documents = _documents(db, tender_id)
    reasons = [] if documents else ['NO_DOCUMENTS']
    source_identity = []
    for document in documents:
        try:
            path = _resolve_document_file_path(document.stored_relative_path)
            with path.open('rb') as stream: sha, size = _hash_file(stream)
            source_identity.append((document.id, sha, size))
            if sha != document.sha256 or size != document.file_size_bytes:
                reasons.append('ORIGINAL_CHANGED')
        except (OSError, HTTPException):
            reasons.append('SOURCE_UNAVAILABLE')
            source_identity.append((document.id, 'UNAVAILABLE'))
        pages = tuple(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)))
        if document.processing_status == 'TEXT_EXTRACTION_FAILED':
            # Parser failed before materializing any page: safe to reset only operational state.
            if pages or document.text_extracted_at is not None or document.page_count not in {None, 0}:
                reasons.append('INCONSISTENT_NATIVE_STATE')
        elif document.processing_status in {'TEXT_EXTRACTION_COMPLETE','TEXT_EXTRACTION_PARTIAL','NO_NATIVE_TEXT'} and (document.text_extracted_at is None or document.page_count != len(pages) or sorted(p.page_number for p in pages) != list(range(1,len(pages)+1))):
            reasons.append('INCONSISTENT_NATIVE_STATE')
        elif document.processing_status not in {'PENDING','TEXT_EXTRACTION_COMPLETE','TEXT_EXTRACTION_PARTIAL','NO_NATIVE_TEXT'}:
            reasons.append('INCONSISTENT_NATIVE_STATE')
        if document.processing_status == 'PENDING' and (pages or document.text_extracted_at is not None or document.page_count not in {None,0}):
            reasons.append('INCONSISTENT_NATIVE_STATE')
    provider_states = []
    from app.models import DocumentVisionPageResult, PageOcrResult
    for model in (DocumentVisionPageResult, PageOcrResult):
        rows = db.execute(select(model.id, model.status).join(DocumentPage, model.document_page_id == DocumentPage.id)
            .where(DocumentPage.document_id.in_([d.id for d in documents])).order_by(model.id)).all()
        provider_states.extend((model.__tablename__, row.id, row.status) for row in rows)
    degraded = any(status in {'FAILED','UNAVAILABLE','INVALID_JSON','PARTIAL','OCR_FAILED','OCR_ERROR','OCR_NO_TEXT'} for _,_,status in provider_states)
    # Existing structured provenance must remain valid; do not delete it to make retry eligible.
    for model, kind in ((TenderScopeDetail,'scope'), (TenderScopeQuantity,'quantity')):
        for record in db.scalars(select(model).where(model.tender_id == tender_id)):
            try: validate_persisted_candidate(db, record, kind)
            except (ValueError, OSError): reasons.append('PROVENANCE_REVIEW_REQUIRED')
    state = _processing(db, tender_id, documents)
    if state.status == 'PROCESSING' and not owns_lock: reasons.append('PROCESSING_ACTIVE')
    root = get_licitia_data_root()
    receipts = []
    for name in ('ocr-task-receipts-v1','vision-task-receipts-v1'):
        directory = root/name
        if directory.is_symlink():
            reasons.append('RECEIPT_STORAGE_INVALID'); continue
        if directory.exists():
            for path in sorted(directory.rglob('*')):
                if path.is_symlink(): reasons.append('RECEIPT_STORAGE_INVALID')
                elif path.is_file() and path.suffix == '.lock':
                    try:
                        with path.open('rb') as lock:
                            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError: reasons.append('RECEIPT_TASK_ACTIVE')
                    except OSError: reasons.append('RECEIPT_STORAGE_UNAVAILABLE')
                elif path.is_file() and path.suffix == '.json':
                    try: receipts.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
                    except OSError: reasons.append('RECEIPT_STORAGE_UNAVAILABLE')
    identity_code = processing_identity()
    identity = {'policy':'workspace-retry-v1-available-only', 'processing_identity':identity_code,
        'context':_context(db, documents), 'sources':source_identity, 'receipts':receipts, 'provider_states':provider_states}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return RetryRead(eligible=not reasons, fingerprint=fingerprint, reasons=tuple(sorted(set(reasons))), provider_degraded=degraded)


def prepare_safe_retry(db, tender_id, expected_fingerprint):
    from fastapi import HTTPException
    status = retry_status(db, tender_id, owns_lock=True)
    if not status.eligible: raise HTTPException(409, {'code':'RETRY_NOT_SAFE','reasons':status.reasons})
    if status.fingerprint != expected_fingerprint: raise HTTPException(409, {'code':'RETRY_CONTEXT_CHANGED'})
    for document in db.scalars(select(TenderDocument).where(TenderDocument.tender_id == tender_id)):
        if document.processing_status == 'TEXT_EXTRACTION_FAILED': document.processing_status = 'PENDING'
    db.commit()


def processing_identity():
    versions = tuple((package, importlib.metadata.version(package)) for package in ('PyMuPDF','camelot-py'))
    from app.local_recovery import application_identity
    return hashlib.sha256(json.dumps({**application_identity(),'versions':versions,'policy':'workspace-retry-v1-available-only'},sort_keys=True).encode()).hexdigest()


def provider_degraded(db, document_ids):
    from app.models import DocumentVisionPageResult, PageOcrResult
    for model in (DocumentVisionPageResult, PageOcrResult):
        if db.scalar(select(model.id).join(DocumentPage,model.document_page_id==DocumentPage.id).where(
            DocumentPage.document_id.in_(document_ids), model.status.in_(['FAILED','UNAVAILABLE','INVALID_JSON','PARTIAL','OCR_FAILED','OCR_ERROR','OCR_NO_TEXT'])).limit(1)):
            return True
    return False
