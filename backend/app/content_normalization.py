from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DocumentChunk, DocumentPage, NormalizedContent, PageOcrResult

TARGET_CHUNK_SIZE = 1400
MAX_CHUNK_SIZE = 1800
CHUNK_OVERLAP = 200


def _normalize_text(raw_text: str | None) -> str:
    if raw_text is None:
        return ""
    text = unicodedata.normalize("NFC", raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch)[0] != "C")
    return text.strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_text(text: str, target_size: int = TARGET_CHUNK_SIZE, max_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict[str, int | str]]:
    if not text:
        return []
    if len(text) <= max_size:
        return [{"start": 0, "end": len(text), "text": text}]

    chunks: list[dict[str, int | str]] = []
    start = 0
    while start < len(text):
        end = min(start + target_size, len(text))
        if end < len(text):
            search_limit = min(len(text), start + max_size)
            boundary_index = search_limit
            for idx in range(search_limit, start, -1):
                if text[idx - 1].isspace():
                    boundary_index = idx
                    break
            if boundary_index > start:
                end = min(boundary_index, len(text))
        chunk_text = text[start:end].rstrip()
        if not chunk_text:
            start = min(len(text), start + max(1, target_size - overlap))
            continue
        chunks.append({"start": start, "end": end, "text": chunk_text})
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _iter_sources_for_page(page: DocumentPage) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if (page.text or "").strip():
        sources.append(
            {
                "document_page_id": page.id,
                "page_ocr_result_id": None,
                "region_id": None,
                "source_type": "NATIVE_PDF",
                "source_scope": "NATIVE_PAGE",
                "engine": None,
                "raw_text": page.text,
            }
        )

    for ocr_result in page.ocr_results:
        if not (ocr_result.text or "").strip():
            continue
        if ocr_result.status == "OCR_FAILED":
            continue
        sources.append(
            {
                "document_page_id": page.id,
                "page_ocr_result_id": ocr_result.id,
                "region_id": ocr_result.region_id,
                "source_type": "OCR",
                "source_scope": "IMAGE_REGION" if ocr_result.region_id else "FULL_PAGE",
                "engine": ocr_result.engine,
                "raw_text": ocr_result.text,
            }
        )
    return sources


def _build_source_identity(source: dict[str, Any]) -> tuple[str, str | None, str | None, str | None, str | None, str | None]:
    return (
        source["document_page_id"],
        source["page_ocr_result_id"],
        source["region_id"],
        source["source_type"],
        source["source_scope"],
        source["engine"],
    )


def _delete_chunks_for_content(db: Session, normalized_content_id: str) -> None:
    for chunk in db.execute(select(DocumentChunk).where(DocumentChunk.normalized_content_id == normalized_content_id)).scalars().all():
        db.delete(chunk)
    db.flush()


def process_document_normalization(db: Session, document: Any) -> dict[str, int]:
    page_records = db.execute(
        select(DocumentPage)
        .options(selectinload(DocumentPage.ocr_results))
        .where(DocumentPage.document_id == document.id)
        .order_by(DocumentPage.page_number.asc())
    ).scalars().all()

    normalized_sources = 0
    chunks_created = 0
    skipped_empty_sources = 0
    acquisition_gaps = 0
    created = 0
    updated = 0

    for page_record in page_records:
        for source in _iter_sources_for_page(page_record):
            source_text = _normalize_text(source["raw_text"])
            if not source_text:
                skipped_empty_sources += 1
                continue

            content_hash = _sha256(source_text)
            source_identity = _build_source_identity(source)
            existing = db.execute(
                select(NormalizedContent).where(
                    NormalizedContent.document_page_id == source["document_page_id"],
                    NormalizedContent.page_ocr_result_id == source["page_ocr_result_id"],
                    NormalizedContent.region_id == source["region_id"],
                    NormalizedContent.source_type == source["source_type"],
                    NormalizedContent.source_scope == source["source_scope"],
                    NormalizedContent.engine == source["engine"],
                )
            ).scalar_one_or_none()

            if existing is None:
                existing = NormalizedContent(
                    document_page_id=source["document_page_id"],
                    page_ocr_result_id=source["page_ocr_result_id"],
                    region_id=source["region_id"],
                    source_type=source["source_type"],
                    source_scope=source["source_scope"],
                    engine=source["engine"],
                    normalized_text=source_text,
                    char_count=len(source_text),
                    content_sha256=content_hash,
                )
                db.add(existing)
                db.flush()
                created += 1
            else:
                _delete_chunks_for_content(db, existing.id)
                if existing.normalized_text != source_text or existing.content_sha256 != content_hash:
                    existing.normalized_text = source_text
                    existing.char_count = len(source_text)
                    existing.content_sha256 = content_hash
                    updated += 1

            normalized_sources += 1
            chunk_layouts = _chunk_text(source_text)
            for chunk_index, chunk_data in enumerate(chunk_layouts):
                chunk_text = str(chunk_data["text"])
                chunk_start = int(chunk_data["start"])
                chunk_end = int(chunk_data["end"])
                chunk_record = DocumentChunk(
                    normalized_content_id=existing.id,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    char_start=chunk_start,
                    char_end=chunk_end,
                    char_count=len(chunk_text),
                    content_sha256=_sha256(chunk_text),
                )
                db.add(chunk_record)
                chunks_created += 1

    # Track unresolved OCR-dependent acquisitions as neutral acquisition gaps.
    for page_record in page_records:
        if page_record.status == "NO_TEXT":
            has_ocr = any(ocr_result.status == "OCR_TEXT_EXTRACTED" for ocr_result in page_record.ocr_results)
            if not has_ocr:
                acquisition_gaps += 1
        if page_record.content_profile == "MIXED_CONTENT":
            if not any(ocr_result.status == "OCR_TEXT_EXTRACTED" for ocr_result in page_record.ocr_results):
                acquisition_gaps += 1

    return {
        "normalized_sources": normalized_sources,
        "chunks_created": chunks_created,
        "skipped_empty_sources": skipped_empty_sources,
        "acquisition_gaps": acquisition_gaps,
        "created": created,
        "updated": updated,
    }


def list_normalized_sources(db: Session, document_id: str) -> list[NormalizedContent]:
    statement = (
        select(NormalizedContent)
        .options(selectinload(NormalizedContent.chunks))
        .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
    )
    return db.execute(statement).scalars().all()
