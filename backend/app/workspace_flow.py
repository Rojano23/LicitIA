"""Normal Workspace composition over canonical services; no perception acquisition."""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tender, TenderDocument, TenderScopeDetail, TenderScopeQuantity, DocumentPage, NormalizedContent
from app.schemas import TenderRequirementMatrixRead, TenderRequirementSemanticsRead
from app.scope_review import ScopeReviewItemRead, ScopeReviewSourceBlocked, get_scope_review_item

logger = logging.getLogger(__name__)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProcessingRead(Contract):
    status: Literal['NOT_PROCESSED', 'PROCESSING', 'COMPLETED', 'COMPLETED_REVIEW_REQUIRED', 'PARTIAL', 'FAILED', 'INTERRUPTED', 'STALE'] = 'NOT_PROCESSED'
    run_id: str | None = None
    error_code: str | None = None
    context_sha256: str | None = None


class SourceRead(Contract):
    document_id: str
    filename: str | None
    revision: int | None
    page: int | None
    excerpt: str
    locator: str
    method: str
    available: bool


class QuantityRead(Contract):
    id: str
    tender_id: str
    scope_detail_id: str
    quantity_raw: str
    quantity_value: Decimal | None
    quantity_min: Decimal | None
    quantity_max: Decimal | None
    unit_raw: str | None
    relation: str | None
    review_required: bool
    status: Literal['REVIEW_REQUIRED', 'NOT_REQUIRED', 'UNRESOLVED']
    source: SourceRead


class ScopeRead(Contract):
    scope_detail_id: str
    candidate_item_key: str | None
    description: str
    source: SourceRead
    review: ScopeReviewItemRead | None
    quantities: tuple[QuantityRead, ...]


class WorkspaceRead(Contract):
    tender_id: str
    processing: ProcessingRead
    scopes: tuple[ScopeRead, ...]
    requirements: TenderRequirementMatrixRead
    semantics: TenderRequirementSemanticsRead
    warnings: tuple[str, ...] = ('HUMAN_VALIDATION_REQUIRED', 'QUANTITY_REVIEW_READ_ONLY', 'AVAILABLE_EVIDENCE_ONLY')


def _documents(db, tender_id):
    if db.get(Tender, tender_id) is None:
        raise HTTPException(404, 'Tender not found')
    return tuple(db.scalars(select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.id)))


def _paths(tender_id: str) -> tuple[Path, Path]:
    from app.main import get_licitia_data_root
    # Hash identifiers: never incorporate a route parameter into a filesystem path.
    root = get_licitia_data_root().resolve()
    directory = root / 'workspace-processing-v1'
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise HTTPException(409, 'Workspace status storage is invalid')
    identity = hashlib.sha256(tender_id.encode()).hexdigest()
    paths = directory / f'{identity}.json', directory / f'{identity}.lock'
    if any(p.is_symlink() for p in paths):
        raise HTTPException(409, 'Workspace status storage is invalid')
    return paths


def _context(db, documents) -> str:
    ids = [d.id for d in documents]
    pages = tuple(db.execute(select(DocumentPage.id, DocumentPage.document_id, DocumentPage.page_number, DocumentPage.status)
        .where(DocumentPage.document_id.in_(ids)).order_by(DocumentPage.id)))
    normalized = tuple(db.execute(select(NormalizedContent.id, NormalizedContent.document_page_id, NormalizedContent.content_sha256)
        .where(NormalizedContent.document_page_id.in_([p.id for p in pages])).order_by(NormalizedContent.id)))
    data = [[(d.id, d.sha256, d.revision_number, d.processing_status) for d in documents], [tuple(p) for p in pages], [tuple(n) for n in normalized]]
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def _save(path: Path, state: ProcessingRead):
    temp = path.with_suffix(f'.{uuid4().hex}.tmp')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            os.chmod(temp, 0o600)
            stream.write(state.model_dump_json())
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _processing(db, tender_id, documents):
    path, lock_path = _paths(tender_id)
    try:
        state = ProcessingRead.model_validate_json(path.read_text())
    except FileNotFoundError:
        return ProcessingRead()
    except ValueError:
        return ProcessingRead(status='FAILED', error_code='STATUS_UNAVAILABLE')
    if lock_path.exists():
        with lock_path.open('rb') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return state.model_copy(update={'status': 'PROCESSING'})
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    if state.status == 'PROCESSING':
        return state.model_copy(update={'status': 'INTERRUPTED', 'error_code': 'PROCESS_INTERRUPTED'})
    if state.context_sha256 != _context(db, documents):
        return state.model_copy(update={'status': 'STALE'})
    return state


def _source(db, record) -> SourceRead:
    from app.main import _resolve_document_file_path
    document = db.get(TenderDocument, record.source_document_id)
    page = db.get(DocumentPage, record.document_page_id)
    available = bool(document and page and document.tender_id == record.tender_id and page.document_id == document.id)
    if available:
        try:
            available = _resolve_document_file_path(document.stored_relative_path).is_file()
        except HTTPException:
            available = False
    return SourceRead(document_id=record.source_document_id, filename=document.original_filename if document else None,
        revision=document.revision_number if document else None, page=page.page_number if page else None,
        excerpt=record.source_excerpt, locator=record.source_locator, method=record.source_method, available=available)


def quantity_read(db, quantity, parent) -> QuantityRead:
    from app.structured_evidence_grounding import validate_persisted_candidate
    valid = (quantity.scope_detail_id == parent.id and quantity.tender_id == parent.tender_id
             and quantity.source_document_id == parent.source_document_id and quantity.document_page_id == parent.document_page_id)
    if valid:
        try:
            validate_persisted_candidate(db, quantity, 'quantity')
        except (ValueError, FileNotFoundError):
            valid = False
    source = _source(db, quantity)
    valid = valid and source.available
    return QuantityRead(id=quantity.id, tender_id=quantity.tender_id, scope_detail_id=quantity.scope_detail_id,
        quantity_raw=quantity.quantity_raw, quantity_value=quantity.quantity_value,
        quantity_min=quantity.quantity_min, quantity_max=quantity.quantity_max, unit_raw=quantity.unit_raw,
        relation=quantity.relation, review_required=quantity.review_required,
        status='UNRESOLVED' if not valid else 'REVIEW_REQUIRED' if quantity.review_required else 'NOT_REQUIRED', source=source)


def read_workspace(db: Session, tender_id: str) -> WorkspaceRead:
    from app.requirement_matrix import get_tender_requirement_matrix
    from app.requirement_semantics import get_tender_requirement_semantics
    documents = _documents(db, tender_id)
    scopes = []
    for detail in db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender_id).order_by(TenderScopeDetail.candidate_item_key, TenderScopeDetail.id)):
        try:
            review = get_scope_review_item(db, tender_id=tender_id, scope_detail_id=detail.id)
        except (ScopeReviewSourceBlocked, FileNotFoundError):
            review = None
        quantities = tuple(quantity_read(db, q, detail) for q in db.scalars(select(TenderScopeQuantity).where(
            TenderScopeQuantity.tender_id == tender_id, TenderScopeQuantity.scope_detail_id == detail.id).order_by(TenderScopeQuantity.id)))
        scopes.append(ScopeRead(scope_detail_id=detail.id, candidate_item_key=detail.candidate_item_key,
            description=review.current.effective_description if review and review.current else detail.description,
            source=_source(db, detail), review=review, quantities=quantities))
    processing = _processing(db, tender_id, documents)
    if processing.status in {'COMPLETED', 'COMPLETED_REVIEW_REQUIRED'} and any(
            not s.source.available or s.review is None or any(q.status == 'UNRESOLVED' for q in s.quantities) for s in scopes):
        processing = processing.model_copy(update={'status': 'PARTIAL'})
    return WorkspaceRead(tender_id=tender_id, processing=processing, scopes=tuple(scopes),
        requirements=TenderRequirementMatrixRead.model_validate(get_tender_requirement_matrix(db, tender_id)),
        semantics=TenderRequirementSemanticsRead.model_validate(get_tender_requirement_semantics(db, tender_id)))


def process_workspace(db: Session, tender_id: str) -> WorkspaceRead:
    from app.native_preparation import prepare_tender_documents
    from app.canonical_materialization import materialize_canonical
    documents = _documents(db, tender_id)
    if not documents:
        raise HTTPException(409, 'Import documents before processing')
    path, lock_path = _paths(tender_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HTTPException(409, 'Tender processing already active')
        run_id = str(uuid4())
        try:
            _save(path, ProcessingRead(status='PROCESSING', run_id=run_id, context_sha256=_context(db, documents)))
            input_ids = tuple(d.id for d in documents)
            prepared = prepare_tender_documents(db, tender_id=tender_id, document_ids=input_ids)
            materialize_canonical(db, tender_id, documents)
            db.commit()
            db.expire_all()
            documents = _documents(db, tender_id)
            result = read_workspace(db, tender_id)
            partial = any(p.status == 'UNAVAILABLE' for p in prepared) or any(d.processing_status in {'NO_NATIVE_TEXT', 'TEXT_EXTRACTION_PARTIAL'} for d in documents)
            needs_review = bool(result.requirements.summary.pending_review_count or result.scopes or result.semantics.requirements)
            state = ('STALE' if tuple(d.id for d in documents) != input_ids else
                     'PARTIAL' if partial else 'COMPLETED_REVIEW_REQUIRED' if needs_review else 'COMPLETED')
            _save(path, ProcessingRead(status=state, run_id=run_id, context_sha256=_context(db, documents)))
        except Exception:
            db.rollback()
            logger.exception('Workspace processing failed: run_id=%s', run_id)
            _save(path, ProcessingRead(status='FAILED', run_id=run_id, error_code='PROCESSING_FAILED',
                context_sha256=_context(db, _documents(db, tender_id))))
            raise HTTPException(422, {'code': 'PROCESSING_FAILED', 'run_id': run_id})
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return read_workspace(db, tender_id)
