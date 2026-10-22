"""Canonical Native preparation shared by application and validation callers."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

class NativePreparationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    """Operational capability outcome; never perception or contractual provenance."""
    document_id: str
    capability: Literal['NATIVE_PDF_TRANSCRIPTION'] = 'NATIVE_PDF_TRANSCRIPTION'
    status: Literal['PREPARED', 'UNAVAILABLE']
    reason: Literal['NATIVE_PREPARATION_COMPLETE', 'UNSUPPORTED_NATIVE_CAPABILITY']
    page_count: int = Field(ge=0)
    reused: bool = False


def prepare_tender_documents(db: Session, *, tender_id: str, document_ids: tuple[str, ...] | None = None) -> tuple[NativePreparationResult, ...]:
    """Deterministic preparation driver using canonical endpoints and their eligibility.

    Unsupported formats yield a per-document outcome. Identity, original integrity,
    persisted-state and parser failures propagate; no catch-all continuation exists.
    Completed Native pages are reused, preserving IDs/provenance on repeated calls.
    Endpoint transaction boundaries remain authoritative. No OCR/Vision acquisition.
    """
    from sqlalchemy import select
    from app.models import Tender, TenderDocument, DocumentPage
    from app.main import _is_pdf_document, _resolve_document_file_path, _hash_file, extract_document_pages, normalize_document_content

    if db.get(Tender, tender_id) is None:
        raise LookupError('Tender not found')
    ids = document_ids if document_ids is not None else tuple(db.scalars(
        select(TenderDocument.id).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.id)))
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate preparation document identity')
    results = []
    for document_id in ids:
        document = db.get(TenderDocument, document_id)
        if document is None or document.tender_id != tender_id:
            raise LookupError('Document identity does not belong to Tender')
        path = _resolve_document_file_path(document.stored_relative_path)
        if not path.is_file():
            raise FileNotFoundError('Stored document original missing')
        with path.open('rb') as original:
            digest, size = _hash_file(original)
        if digest != document.sha256 or size != document.file_size_bytes:
            raise ValueError('Document original integrity mismatch')
        pages = tuple(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)))
        if not _is_pdf_document(document):
            if pages or document.text_extracted_at is not None or document.page_count not in {None, 0} or document.processing_status != 'PENDING':
                raise ValueError('Unsupported document has inconsistent Native preparation state')
            results.append(NativePreparationResult(document_id=document_id, status='UNAVAILABLE',
                reason='UNSUPPORTED_NATIVE_CAPABILITY', page_count=0))
            continue
        completed = document.processing_status in {'TEXT_EXTRACTION_COMPLETE', 'TEXT_EXTRACTION_PARTIAL', 'NO_NATIVE_TEXT'}
        if completed:
            if document.text_extracted_at is None or document.page_count != len(pages) or any(
                    p.page_number != index or p.extraction_method != 'NATIVE_PDF' for index, p in enumerate(pages, 1)):
                raise ValueError('Inconsistent completed Native preparation state')
        elif document.processing_status != 'PENDING' or pages or document.text_extracted_at is not None or document.page_count not in {None, 0}:
            raise ValueError('Native preparation requires consistent pending or completed state')
        else:
            extract_document_pages(tender_id, document_id, db=db)
        normalize_document_content(tender_id, document_id, db=db)
        results.append(NativePreparationResult(document_id=document_id, status='PREPARED',
            reason='NATIVE_PREPARATION_COMPLETE', page_count=document.page_count, reused=completed))
    return tuple(results)
