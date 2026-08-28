from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import PurePosixPath
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

import fitz

ALLOWED_CONFLICT_ACTIONS = {"NONE", "IMPORT_INDEPENDENT", "NEW_REVISION"}

from app.config import get_settings
from app.database import get_db
from app.content_normalization import list_normalized_sources, process_document_normalization
from app.document_classification import apply_human_classification_decision, get_document_classification, process_document_classification
from app.document_references import (
    analyze_document_references,
    analyze_tender_references,
    apply_human_reference_decision,
    list_document_references,
    list_tender_relationships,
)
from app.models import (
    DocumentPage,
    DocumentPageRegion,
    DocumentPageStatus,
    PageOcrResult,
    Tender,
    TenderDocument,
    TenderDocumentProcessingStatus,
    TenderDocumentStatus,
)
from app.ocr import build_default_ocr_provider_registry
from app.schemas import (
    DocumentClassificationRead,
    DocumentReferenceAnalysisRead,
    DocumentReferenceDecisionWrite,
    DocumentExtractionResult,
    DocumentImportResult,
    DocumentOcrResult,
    DocumentPageRead,
    DocumentRelationshipRead,
    NormalizedContentRead,
    NormalizationSummaryRead,
    OcrProviderStatusRead,
    PageOcrResultRead,
    TenderCreate,
    TenderDocumentRead,
    TenderRead,
)

settings = get_settings()

MIN_IMAGE_REGION_AREA_RATIO = 0.03
MIN_IMAGE_REGION_PIXEL_DIMENSION = 120
AUTO_OCR_PROVIDER_ORDER = ["TESSERACT", "PADDLEOCR"]

# MVP-02.2 policy: AUTO acquisition is dual-provider for OCR-dependent pages.
# Native text remains authoritative for TEXT_ONLY pages; image-only and mixed-content pages
# keep both engine results as independent, non-fused provenance records.
app = FastAPI(title="LicitIA", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_licitia_data_root() -> Path:
    configured_root = Path(get_settings().licitia_data_dir)
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[1] / configured_root
    configured_root.mkdir(parents=True, exist_ok=True)
    return configured_root


def _safe_filename(filename: str) -> str:
    candidate = os.path.basename(filename or "document.bin").strip()
    if not candidate:
        candidate = "document.bin"
    return candidate


def _normalize_conflict_action(value: str | None) -> str:
    if value is None:
        return "NONE"
    candidate = value.strip().upper()
    if candidate not in ALLOWED_CONFLICT_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported conflict action: {value}")
    return candidate


def _hash_file(file_handle) -> tuple[str, int]:
    hasher = hashlib.sha256()
    total_size = 0
    file_handle.seek(0)
    while chunk := file_handle.read(65536):
        hasher.update(chunk)
        total_size += len(chunk)
    file_handle.seek(0)
    return hasher.hexdigest(), total_size


def _store_uploaded_file(tender_id: str, upload: UploadFile, source_relative_path: str | None) -> tuple[str, str]:
    data_root = get_licitia_data_root()
    document_id = str(uuid4())
    safe_name = _safe_filename(upload.filename or "document.bin")
    storage_dir = data_root / "tenders" / tender_id / "originals" / document_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / safe_name

    staging_dir = None
    try:
        with tempfile.TemporaryDirectory(prefix=".staging_", dir=storage_dir.parent) as staging_dir_name:
            staging_dir = Path(staging_dir_name)
            staged_path = staging_dir / safe_name
            upload.file.seek(0)
            with open(staged_path, "wb") as temp_handle:
                while chunk := upload.file.read(65536):
                    temp_handle.write(chunk)
            if destination.exists():
                raise HTTPException(status_code=409, detail="Storage path collision detected")
            shutil.move(str(staged_path), str(destination))
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    stored_relative_path = str(Path("tenders") / tender_id / "originals" / document_id / safe_name)
    if source_relative_path:
        source_relative_path = source_relative_path.replace("\\", "/")
    return stored_relative_path, source_relative_path or None


def _resolve_document_file_path(stored_relative_path: str) -> Path:
    if not stored_relative_path or not stored_relative_path.strip():
        raise HTTPException(status_code=400, detail="Document storage path is missing")

    normalized_path = stored_relative_path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)
    if pure_path.is_absolute() or any(part in ("", ".", "..") for part in pure_path.parts):
        raise HTTPException(status_code=400, detail="Document storage path is invalid")

    data_root = get_licitia_data_root().resolve()
    resolved_path = (data_root / pure_path).resolve()
    if not resolved_path.is_relative_to(data_root):
        raise HTTPException(status_code=400, detail="Document storage path escapes the local data directory")

    return resolved_path


def _is_pdf_document(document: TenderDocument) -> bool:
    mime_type = (document.mime_type or "").lower()
    extension = Path(document.original_filename or "").suffix.lower()
    return "pdf" in mime_type or extension == ".pdf"


def _extract_pdf_pages(file_path: Path) -> list[tuple[int, str]]:
    pdf_document = fitz.open(str(file_path))
    try:
        extracted_pages: list[tuple[int, str]] = []
        for page_number in range(pdf_document.page_count):
            page = pdf_document[page_number]
            text = page.get_text("text")
            extracted_pages.append((page_number + 1, text))
        return extracted_pages
    finally:
        pdf_document.close()


def _page_status_for_text(page_text: str) -> str:
    normalized_text = (page_text or "").strip()
    return DocumentPageStatus.TEXT_EXTRACTED.value if normalized_text else DocumentPageStatus.NO_TEXT.value


def _page_image_regions_for_page(page: fitz.Page) -> list[dict[str, float | int]]:
    page_area = float(page.rect.width * page.rect.height)
    regions: list[dict[str, float | int]] = []
    for image_index, image_data in enumerate(page.get_images(full=True)):
        image_name = image_data[7] if len(image_data) > 7 else None
        if image_name is None:
            continue
        try:
            rects = page.get_image_rects(image_name)
        except Exception:
            continue
        for region_index, rect in enumerate(rects or []):
            if hasattr(rect, "x0"):
                x0, y0, x1, y1 = float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
            else:
                x0, y0, x1, y1 = (float(value) for value in rect[:4])
            width = max(float(x1 - x0), 0.0)
            height = max(float(y1 - y0), 0.0)
            if width < MIN_IMAGE_REGION_PIXEL_DIMENSION or height < MIN_IMAGE_REGION_PIXEL_DIMENSION:
                continue
            area_ratio = (width * height) / max(page_area, 1.0)
            if area_ratio < MIN_IMAGE_REGION_AREA_RATIO:
                continue
            regions.append(
                {
                    "region_index": len(regions) + 1,
                    "region_type": "IMAGE",
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "width": width,
                    "height": height,
                    "area_ratio": area_ratio,
                }
            )
    return regions


def _page_content_profile(page_text: str, image_regions: list[dict[str, float | int]]) -> str:
    has_native_text = bool((page_text or "").strip())
    has_image_region = bool(image_regions)
    if has_native_text and has_image_region:
        return "MIXED_CONTENT"
    if has_native_text:
        return "TEXT_ONLY"
    if has_image_region:
        return "IMAGE_ONLY"
    return "TEXT_ONLY"


def _page_ocr_jobs(page_record: DocumentPage, page: fitz.Page, *, force: bool = False) -> list[dict[str, object]]:
    text_present = bool((page_record.text or "").strip())
    image_regions = _page_image_regions_for_page(page)
    if not text_present:
        return [{"scope": "FULL_PAGE", "region_id": None, "region_index": None}]
    if image_regions and not force:
        return [{"scope": "IMAGE_REGION", "region_id": None, "region_index": region["region_index"]} for region in image_regions]
    if force:
        return [{"scope": "FULL_PAGE", "region_id": None, "region_index": None}]
    return []


def _ensure_page_image_regions(db: Session, page_record: DocumentPage, page: fitz.Page) -> list[DocumentPageRegion]:
    detected_regions = _page_image_regions_for_page(page)
    if not detected_regions:
        return []

    stored_regions: list[DocumentPageRegion] = []
    for region_data in detected_regions:
        region_index = int(region_data["region_index"])
        stored_region = db.execute(
            select(DocumentPageRegion).where(
                DocumentPageRegion.document_page_id == page_record.id,
                DocumentPageRegion.region_index == region_index,
            )
        ).scalar_one_or_none()
        if stored_region is None:
            stored_region = DocumentPageRegion(
                document_page_id=page_record.id,
                region_index=region_index,
                region_type=str(region_data["region_type"]),
                x0=float(region_data["x0"]),
                y0=float(region_data["y0"]),
                x1=float(region_data["x1"]),
                y1=float(region_data["y1"]),
                width=float(region_data["width"]),
                height=float(region_data["height"]),
                area_ratio=float(region_data["area_ratio"]),
            )
            db.add(stored_region)
            db.flush()
        else:
            stored_region.region_type = str(region_data["region_type"])
            stored_region.x0 = float(region_data["x0"])
            stored_region.y0 = float(region_data["y0"])
            stored_region.x1 = float(region_data["x1"])
            stored_region.y1 = float(region_data["y1"])
            stored_region.width = float(region_data["width"])
            stored_region.height = float(region_data["height"])
            stored_region.area_ratio = float(region_data["area_ratio"])
        stored_regions.append(stored_region)
    return stored_regions


def _document_processing_status_for_pages(page_statuses: list[str]) -> str:
    if not page_statuses:
        return TenderDocumentProcessingStatus.NO_NATIVE_TEXT.value
    if all(status == DocumentPageStatus.NO_TEXT.value for status in page_statuses):
        return TenderDocumentProcessingStatus.NO_NATIVE_TEXT.value
    if all(status == DocumentPageStatus.TEXT_EXTRACTED.value for status in page_statuses):
        return TenderDocumentProcessingStatus.TEXT_EXTRACTION_COMPLETE.value
    return TenderDocumentProcessingStatus.TEXT_EXTRACTION_PARTIAL.value


def get_ocr_providers() -> list[object]:
    return build_default_ocr_provider_registry()


def _render_pdf_page_image(file_path: Path, page_number: int):
    pdf_document = fitz.open(str(file_path))
    try:
        page = pdf_document[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        return pix
    finally:
        pdf_document.close()


def _page_ocr_payload_for_result(result: dict[str, object]) -> dict[str, object]:
    return {
        "text": str(result.get("text", "")),
        "status": str(result.get("status", "OCR_TEXT_EXTRACTED")),
        "engine": str(result.get("engine", "UNKNOWN")),
        "engine_version": str(result.get("engine_version", "unknown")),
        "language": str(result.get("language", "es+en")),
        "confidence": result.get("confidence"),
        "processing_time_ms": result.get("processing_time_ms"),
        "warnings": "; ".join(result.get("warnings", []) or []) if isinstance(result.get("warnings", []), list) else str(result.get("warnings") or ""),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tenders", response_model=TenderRead, status_code=status.HTTP_201_CREATED)
def create_tender(payload: TenderCreate, db: Session = Depends(get_db)) -> Tender:
    cleaned_title = payload.title.strip()
    if not cleaned_title:
        raise HTTPException(status_code=400, detail="Tender title is required")

    tender = Tender(
        title=cleaned_title,
        institution_profile=(payload.institution_profile.strip() if payload.institution_profile else None),
        external_reference=(payload.external_reference.strip() if payload.external_reference else None),
        status="DRAFT",
    )

    db.add(tender)
    db.commit()
    db.refresh(tender)
    return tender


@app.get("/tenders", response_model=list[TenderRead])
def list_tenders(db: Session = Depends(get_db)) -> list[Tender]:
    statement = select(Tender).order_by(Tender.created_at.desc())
    return db.execute(statement).scalars().all()


@app.get("/tenders/{tender_id}", response_model=TenderRead)
def get_tender(tender_id: str, db: Session = Depends(get_db)) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


@app.post("/tenders/{tender_id}/documents/import", response_model=list[DocumentImportResult])
async def import_documents(
    tender_id: str,
    files: list[UploadFile] = File(...),
    source_relative_paths: list[str] | None = Form(default=None),
    conflict_action: str | None = Form(default=None),
    revision_of_document_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> list[DocumentImportResult]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided")

    input_relative_paths = source_relative_paths or [None for _ in files]
    if len(input_relative_paths) != len(files):
        input_relative_paths = [None for _ in files]

    normalized_conflict_action = _normalize_conflict_action(conflict_action)
    results: list[DocumentImportResult] = []

    for index, upload in enumerate(files):
        filename = upload.filename or "document.bin"
        source_relative_path = input_relative_paths[index] if index < len(input_relative_paths) else None

        if not filename.strip():
            results.append(
                DocumentImportResult(
                    filename="document.bin",
                    source_relative_path=source_relative_path,
                    status=TenderDocumentStatus.FAILED.value,
                    message="Empty filename was provided.",
                )
            )
            continue

        try:
            upload.file.seek(0)
            sha256_value, file_size = _hash_file(upload.file)
            mime_type = upload.content_type or mimetypes.guess_type(filename)[0]

            is_duplicate = db.execute(
                select(TenderDocument).where(
                    TenderDocument.tender_id == tender_id,
                    TenderDocument.sha256 == sha256_value,
                )
            ).scalar_one_or_none()
            if is_duplicate is not None:
                results.append(
                    DocumentImportResult(
                        filename=filename,
                        source_relative_path=source_relative_path,
                        status=TenderDocumentStatus.DUPLICATE.value,
                        message="Document content already exists in this Tender.",
                        document_id=is_duplicate.id,
                        sha256=sha256_value,
                    )
                )
                continue

            existing_name = db.execute(
                select(TenderDocument)
                .where(
                    TenderDocument.tender_id == tender_id,
                    TenderDocument.original_filename == filename,
                    TenderDocument.sha256 != sha256_value,
                )
                .order_by(TenderDocument.is_current.desc(), TenderDocument.revision_number.desc(), TenderDocument.imported_at.desc())
            ).first()
            if existing_name is not None:
                if normalized_conflict_action == "NONE":
                    results.append(
                        DocumentImportResult(
                            filename=filename,
                            source_relative_path=source_relative_path,
                            status=TenderDocumentStatus.NAME_CONFLICT.value,
                            message="Same filename already exists with different content; human review required.",
                            document_id=existing_name[0].id,
                            sha256=sha256_value,
                            revision_number=existing_name[0].revision_number,
                            is_current=existing_name[0].is_current,
                        )
                    )
                    continue

                if normalized_conflict_action == "IMPORT_INDEPENDENT":
                    stored_relative_path, source_relative_path = _store_uploaded_file(tender_id, upload, source_relative_path)
                    document = TenderDocument(
                        tender_id=tender_id,
                        original_filename=filename,
                        source_relative_path=source_relative_path,
                        stored_relative_path=stored_relative_path,
                        mime_type=mime_type,
                        file_size_bytes=file_size,
                        sha256=sha256_value,
                        status=TenderDocumentStatus.IMPORTED.value,
                        revision_of_document_id=None,
                        revision_number=1,
                        is_current=True,
                        conflict_resolution_action="IMPORT_INDEPENDENT",
                    )
                    try:
                        db.add(document)
                        db.commit()
                        db.refresh(document)
                    except Exception:
                        db.rollback()
                        file_path = get_licitia_data_root() / stored_relative_path
                        if file_path.exists():
                            file_path.unlink(missing_ok=True)
                            parent = file_path.parent
                            while parent != get_licitia_data_root() and not any(parent.iterdir()):
                                parent.rmdir()
                                parent = parent.parent
                        raise

                    results.append(
                        DocumentImportResult(
                            filename=filename,
                            source_relative_path=source_relative_path,
                            status=document.status,
                            message="Imported successfully.",
                            document_id=document.id,
                            stored_relative_path=document.stored_relative_path,
                            sha256=document.sha256,
                            revision_of_document_id=document.revision_of_document_id,
                            conflict_resolution_action=document.conflict_resolution_action,
                            revision_number=document.revision_number,
                            is_current=document.is_current,
                        )
                    )
                    continue
                elif normalized_conflict_action == "NEW_REVISION":
                    if not revision_of_document_id:
                        raise HTTPException(status_code=400, detail="revision_of_document_id is required for NEW_REVISION")
                    target_document = db.get(TenderDocument, revision_of_document_id)
                    if target_document is None:
                        raise HTTPException(status_code=404, detail="Revision target document not found")
                    if target_document.tender_id != tender_id:
                        raise HTTPException(status_code=400, detail="Revision target must belong to the same Tender")
                    if target_document.original_filename != filename:
                        raise HTTPException(status_code=400, detail="Revision target filename must match the incoming filename")
                    if not target_document.is_current:
                        raise HTTPException(status_code=400, detail="Only the current revision can receive a new revision")
                    if target_document.sha256 == sha256_value:
                        raise HTTPException(status_code=400, detail="Target document content already matches the incoming file")

                    stored_relative_path, source_relative_path = _store_uploaded_file(tender_id, upload, source_relative_path)
                    target_document.is_current = False

                    document = TenderDocument(
                        tender_id=tender_id,
                        original_filename=filename,
                        source_relative_path=source_relative_path,
                        stored_relative_path=stored_relative_path,
                        mime_type=mime_type,
                        file_size_bytes=file_size,
                        sha256=sha256_value,
                        status=TenderDocumentStatus.IMPORTED.value,
                        revision_of_document_id=target_document.id,
                        revision_number=target_document.revision_number + 1,
                        is_current=True,
                        conflict_resolution_action="NEW_REVISION",
                    )
                    try:
                        db.add(document)
                        db.commit()
                        db.refresh(document)
                    except Exception:
                        db.rollback()
                        file_path = get_licitia_data_root() / stored_relative_path
                        if file_path.exists():
                            file_path.unlink(missing_ok=True)
                            parent = file_path.parent
                            while parent != get_licitia_data_root() and not any(parent.iterdir()):
                                parent.rmdir()
                                parent = parent.parent
                        raise

                    results.append(
                        DocumentImportResult(
                            filename=filename,
                            source_relative_path=source_relative_path,
                            status=document.status,
                            message="Imported successfully.",
                            document_id=document.id,
                            stored_relative_path=document.stored_relative_path,
                            sha256=document.sha256,
                            revision_of_document_id=document.revision_of_document_id,
                            conflict_resolution_action=document.conflict_resolution_action,
                            revision_number=document.revision_number,
                            is_current=document.is_current,
                        )
                    )
                    continue
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported conflict action: {normalized_conflict_action}")

            stored_relative_path, source_relative_path = _store_uploaded_file(tender_id, upload, source_relative_path)

            document = TenderDocument(
                tender_id=tender_id,
                original_filename=filename,
                source_relative_path=source_relative_path,
                stored_relative_path=stored_relative_path,
                mime_type=mime_type,
                file_size_bytes=file_size,
                sha256=sha256_value,
                status=TenderDocumentStatus.IMPORTED.value,
                revision_number=1,
                is_current=True,
                revision_of_document_id=None,
                conflict_resolution_action=None,
            )
            try:
                db.add(document)
                db.commit()
                db.refresh(document)
            except Exception:
                db.rollback()
                file_path = get_licitia_data_root() / stored_relative_path
                if file_path.exists():
                    file_path.unlink(missing_ok=True)
                    parent = file_path.parent
                    while parent != get_licitia_data_root() and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                raise

            results.append(
                DocumentImportResult(
                    filename=filename,
                    source_relative_path=source_relative_path,
                    status=document.status,
                    message="Imported successfully.",
                    document_id=document.id,
                    stored_relative_path=document.stored_relative_path,
                    sha256=document.sha256,
                    revision_of_document_id=document.revision_of_document_id,
                    conflict_resolution_action=document.conflict_resolution_action,
                    revision_number=document.revision_number,
                    is_current=document.is_current,
                )
            )
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            results.append(
                DocumentImportResult(
                    filename=filename,
                    source_relative_path=source_relative_path,
                    status=TenderDocumentStatus.FAILED.value,
                    message=f"Import failed: {exc}",
                    sha256=None,
                )
            )

    return results


@app.get("/tenders/{tender_id}/documents", response_model=list[TenderDocumentRead])
def list_tender_documents(tender_id: str, db: Session = Depends(get_db)) -> list[TenderDocument]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    statement = select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.imported_at.desc())
    return db.execute(statement).scalars().all()


@app.get("/documents/{document_id}", response_model=TenderDocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> TenderDocument:
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.post("/tenders/{tender_id}/documents/{document_id}/extract-pages", response_model=DocumentExtractionResult)
def extract_document_pages(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")
    if not _is_pdf_document(document):
        raise HTTPException(status_code=400, detail="Only PDF documents can be extracted.")

    file_path = _resolve_document_file_path(document.stored_relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")

    try:
        extracted_pages = _extract_pdf_pages(file_path)
    except Exception as exc:  # pragma: no cover - defensive coverage for parser failure
        document.processing_status = TenderDocumentProcessingStatus.TEXT_EXTRACTION_FAILED.value
        document.page_count = 0
        document.text_extracted_at = None
        db.commit()
        raise HTTPException(status_code=500, detail=f"PDF text extraction failed: {exc}") from exc

    for page_record in list(document.pages):
        db.delete(page_record)

    page_records: list[DocumentPage] = []
    page_statuses: list[str] = []
    pdf_document = fitz.open(str(file_path))
    try:
        for page_number, text in extracted_pages:
            normalized_text = text or ""
            page_status = _page_status_for_text(normalized_text)
            page_statuses.append(page_status)
            page_records.append(
                DocumentPage(
                    document_id=document.id,
                    page_number=page_number,
                    text=normalized_text,
                    char_count=len(normalized_text.strip()),
                    extraction_method="NATIVE_PDF",
                    status=page_status,
                )
            )
        document.pages.extend(page_records)
        db.flush()
        for page_record in page_records:
            page = pdf_document[page_record.page_number - 1]
            _ensure_page_image_regions(db, page_record, page)
        document.processing_status = _document_processing_status_for_pages(page_statuses)
        document.page_count = len(extracted_pages)
        document.text_extracted_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        pdf_document.close()
    db.refresh(document)

    return {
        "document_id": document.id,
        "processing_status": document.processing_status,
        "page_count": document.page_count,
        "extracted_at": document.text_extracted_at,
    }


@app.post("/documents/{document_id}/extract-pages", response_model=DocumentExtractionResult)
def extract_document_pages_legacy(document_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return extract_document_pages(document.tender_id, document_id, db=db)


@app.post("/tenders/{tender_id}/documents/{document_id}/normalize", response_model=NormalizationSummaryRead)
def normalize_document_content(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    summary = process_document_normalization(db, document)
    db.commit()
    return {
        "document_id": document.id,
        "page_count": document.page_count,
        "normalized_sources": summary["normalized_sources"],
        "chunks_created": summary["chunks_created"],
        "skipped_empty_sources": summary["skipped_empty_sources"],
        "acquisition_gaps": summary["acquisition_gaps"],
        "created": summary["created"],
        "updated": summary["updated"],
    }


@app.get("/tenders/{tender_id}/documents/{document_id}/normalized", response_model=list[NormalizedContentRead])
def list_document_normalized_content(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> list[object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    return list_normalized_sources(db, document_id)


@app.post("/tenders/{tender_id}/documents/{document_id}/classify", response_model=DocumentClassificationRead)
def classify_document(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    classification = process_document_classification(db, document)
    db.commit()
    return classification


@app.get("/tenders/{tender_id}/documents/{document_id}/classification", response_model=DocumentClassificationRead)
def get_document_classification_endpoint(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    classification = get_document_classification(db, document_id)
    return classification


@app.patch("/tenders/{tender_id}/documents/{document_id}/classification", response_model=DocumentClassificationRead)
def update_document_classification(
    tender_id: str,
    document_id: str,
    payload: dict[str, str | None],
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    action = str(payload.get("action") or "").upper()
    human_type = payload.get("human_type")
    human_note = payload.get("human_note")
    if not action:
        raise HTTPException(status_code=400, detail="Action is required")

    classification = apply_human_classification_decision(db, document, action, human_type, human_note)
    db.commit()
    return classification


@app.post("/tenders/{tender_id}/classify-documents", response_model=list[DocumentClassificationRead])
def classify_tender_documents(
    tender_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    results: list[dict[str, object]] = []
    documents = db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.imported_at.desc())).scalars().all()
    for document in documents:
        try:
            results.append(process_document_classification(db, document))
        except Exception:
            results.append({
                "document_id": document.id,
                "suggested_type": "UNKNOWN",
                "suggested_score": 0,
                "effective_type": "UNKNOWN",
                "classification_status": "NOT_READY",
                "is_composite": False,
                "human_type": None,
                "human_note": None,
                "candidate_scores": [],
                "functional_tags": [],
                "evidence": [],
                "input_fingerprint_sha256": "",
                "not_ready": True,
            })
    db.commit()
    return results


@app.post("/tenders/{tender_id}/documents/{document_id}/analyze-references", response_model=DocumentReferenceAnalysisRead)
def analyze_document_references_endpoint(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    payload = analyze_document_references(db, tender_id, document)
    db.commit()
    return payload


@app.post("/tenders/{tender_id}/analyze-references", response_model=list[DocumentReferenceAnalysisRead])
def analyze_tender_references_endpoint(
    tender_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    payload = analyze_tender_references(db, tender_id)
    db.commit()
    return payload


@app.get("/tenders/{tender_id}/documents/{document_id}/references", response_model=DocumentReferenceAnalysisRead)
def get_document_references_endpoint(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    return list_document_references(db, tender_id, document_id)


@app.get("/tenders/{tender_id}/relationships", response_model=list[DocumentRelationshipRead])
def get_tender_relationships_endpoint(
    tender_id: str,
    source_document_id: str | None = None,
    target_document_id: str | None = None,
    relationship_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    return list_tender_relationships(
        db,
        tender_id,
        source_document_id=source_document_id,
        target_document_id=target_document_id,
        relationship_type=relationship_type,
    )


@app.patch("/tenders/{tender_id}/references/{reference_id}", response_model=DocumentReferenceAnalysisRead)
def update_reference_resolution_endpoint(
    tender_id: str,
    reference_id: str,
    payload: DocumentReferenceDecisionWrite,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    try:
        result = apply_human_reference_decision(
            db,
            tender_id=tender_id,
            reference_id=reference_id,
            action=payload.action,
            human_target_document_id=payload.human_target_document_id,
            human_note=payload.human_note,
        )
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tenders/{tender_id}/documents/{document_id}/pages", response_model=list[DocumentPageRead])
def list_document_pages(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> list[DocumentPage]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    statement = (
        select(DocumentPage)
        .options(selectinload(DocumentPage.regions), selectinload(DocumentPage.ocr_results))
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc())
    )
    return db.execute(statement).scalars().all()


@app.get("/documents/{document_id}/pages", response_model=list[DocumentPageRead])
def list_document_pages_legacy(document_id: str, db: Session = Depends(get_db)) -> list[DocumentPage]:
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return list_document_pages(document.tender_id, document_id, db=db)


@app.get("/tenders/{tender_id}/documents/{document_id}/content")
def get_document_content(tender_id: str, document_id: str, db: Session = Depends(get_db)) -> FileResponse:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")

    file_path = _resolve_document_file_path(document.stored_relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")

    upper_mime = (document.mime_type or "").lower()
    file_extension = file_path.suffix.lower()
    if "pdf" not in upper_mime and file_extension != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files can be displayed in the local viewer")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=document.original_filename,
        content_disposition_type="inline",
    )


@app.get("/ocr/providers", response_model=list[OcrProviderStatusRead])
def list_ocr_providers() -> list[dict[str, object]]:
    providers = get_ocr_providers()
    payload: list[dict[str, object]] = []
    for provider in providers:
        payload.append(
            {
                "provider_id": provider.provider_id,
                "provider_name": provider.provider_name,
                "status": provider.status,
                "version": provider.version,
                "status_reason": provider.status_reason,
            }
        )
    return payload


@app.post("/tenders/{tender_id}/documents/{document_id}/ocr", response_model=DocumentOcrResult)
def run_document_ocr(
    tender_id: str,
    document_id: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload is None:
        payload = {}

    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.tender_id != tender_id:
        raise HTTPException(status_code=404, detail="Document not found for the selected Tender")
    if not _is_pdf_document(document):
        raise HTTPException(status_code=400, detail="Only PDF documents can be OCR-processed.")

    provider_mode = str(payload.get("provider", "AUTO")).upper()
    requested_pages = payload.get("page_numbers")
    force = bool(payload.get("force", False))
    scope = str(payload.get("scope", "AUTO")).upper()
    region_index = payload.get("region_index")
    language = str(payload.get("language", "es+en")) or "es+en"

    available_providers = get_ocr_providers()
    try:
        selected_providers = [
            provider for provider in available_providers if provider.provider_id == provider_mode
        ] if provider_mode in {"TESSERACT", "PADDLEOCR"} else [
            provider for provider in available_providers if provider.status == "AVAILABLE"
        ]
        if provider_mode == "AUTO":
            preferred_order = AUTO_OCR_PROVIDER_ORDER
            selected_providers = []
            for provider_id in preferred_order:
                for provider in available_providers:
                    if provider.provider_id == provider_id and provider.status == "AVAILABLE":
                        selected_providers.append(provider)
                        break
            if not selected_providers:
                raise RuntimeError("No OCR providers are currently available")
        elif provider_mode == "COMPARE":
            selected_providers = [provider for provider in available_providers if provider.status == "AVAILABLE"]
            if not selected_providers:
                raise RuntimeError("No OCR providers are currently available")
        elif provider_mode in {"TESSERACT", "PADDLEOCR"}:
            if not selected_providers or selected_providers[0].status != "AVAILABLE":
                raise RuntimeError(f"OCR provider {provider_mode} is unavailable")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported OCR provider mode: {provider_mode}")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    file_path = _resolve_document_file_path(document.stored_relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")

    pdf_document = fitz.open(str(file_path))
    try:
        page_records = db.execute(
            select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number.asc())
        ).scalars().all()
        if not page_records:
            for page_number in range(pdf_document.page_count):
                page = pdf_document[page_number]
                text = page.get_text("text") or ""
                page_record = DocumentPage(
                    document_id=document.id,
                    page_number=page_number + 1,
                    text=text,
                    char_count=len(text.strip()),
                    extraction_method="NATIVE_PDF",
                    status=_page_status_for_text(text),
                )
                db.add(page_record)
                page_records.append(page_record)
            document.page_count = pdf_document.page_count
            document.processing_status = _document_processing_status_for_pages([page.status for page in page_records])
            db.flush()

        if requested_pages is None:
            requested_page_numbers = [page_record.page_number for page_record in page_records]
        else:
            requested_page_numbers = []
            for item in requested_pages:
                try:
                    requested_page_numbers.append(int(item))
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail=f"Invalid page number: {item}") from None

        eligible_pages: list[DocumentPage] = []
        for page_record in page_records:
            if page_record.page_number not in requested_page_numbers:
                continue
            page_index = page_record.page_number - 1
            if page_index < 0 or page_index >= pdf_document.page_count:
                continue
            page = pdf_document[page_index]
            image_regions = _ensure_page_image_regions(db, page_record, page)
            page_record_content_profile = _page_content_profile(page_record.text or "", [
                {"region_index": region.region_index, "region_type": region.region_type, "x0": region.x0, "y0": region.y0, "x1": region.x1, "y1": region.y1, "width": region.width, "height": region.height, "area_ratio": region.area_ratio}
                for region in image_regions
            ])
            if scope == "FULL_PAGE":
                eligible_pages.append(page_record)
                continue
            if scope == "IMAGE_REGION":
                if image_regions:
                    eligible_pages.append(page_record)
                continue
            if not force and page_record.status == DocumentPageStatus.TEXT_EXTRACTED.value and (page_record.text or "").strip() and page_record_content_profile == "TEXT_ONLY":
                continue
            if not force and page_record.status == DocumentPageStatus.TEXT_EXTRACTED.value and page_record_content_profile == "MIXED_CONTENT":
                eligible_pages.append(page_record)
                continue
            eligible_pages.append(page_record)

        results: list[dict[str, object]] = []
        for page_record in eligible_pages:
            page_index = page_record.page_number - 1
            if page_index < 0 or page_index >= pdf_document.page_count:
                continue
            page = pdf_document[page_index]
            page_regions = _ensure_page_image_regions(db, page_record, page)
            ocr_jobs: list[dict[str, object]] = []
            if scope in {"FULL_PAGE", "IMAGE_REGION"}:
                requested_region_index = region_index if region_index is not None else None
                if scope == "IMAGE_REGION":
                    if requested_region_index is None:
                        filtered_regions = page_regions
                    else:
                        filtered_regions = [region for region in page_regions if region.region_index == int(requested_region_index)]
                    ocr_jobs = [{"scope": "IMAGE_REGION", "region_id": region.id, "region_index": region.region_index} for region in filtered_regions]
                else:
                    ocr_jobs = [{"scope": "FULL_PAGE", "region_id": None, "region_index": None}]
            elif force:
                ocr_jobs = [{"scope": "FULL_PAGE", "region_id": None, "region_index": None}]
            elif page_record.status == DocumentPageStatus.NO_TEXT.value:
                ocr_jobs = [{"scope": "FULL_PAGE", "region_id": None, "region_index": None}]
            elif page_regions:
                ocr_jobs = [{"scope": "IMAGE_REGION", "region_id": region.id, "region_index": region.region_index} for region in page_regions]
            if not ocr_jobs:
                continue
            for provider in selected_providers:
                for job in ocr_jobs:
                    region_id = job["region_id"]
                    scope_name = str(job["scope"])
                    region_index_value = job["region_index"]
                    if scope_name == "IMAGE_REGION":
                        region_record = db.get(DocumentPageRegion, str(region_id))
                        if region_record is None:
                            continue
                        region_rect = fitz.Rect(region_record.x0, region_record.y0, region_record.x1, region_record.y1)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=region_rect)
                        payload_bytes = pix.tobytes("png")
                    else:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        payload_bytes = pix.tobytes("png")
                    try:
                        provider_result = provider.recognize(payload_bytes, language=language)
                    except Exception as exc:  # pragma: no cover - provider runtime issue
                        provider_result = {
                            "text": "",
                            "status": "OCR_FAILED",
                            "engine": provider.provider_id,
                            "engine_version": provider.version,
                            "language": language,
                            "confidence": None,
                            "processing_time_ms": None,
                            "warnings": [str(exc)],
                        }
                    saved_payload = _page_ocr_payload_for_result(provider_result)
                    stored_result = db.execute(
                        select(PageOcrResult).where(
                            PageOcrResult.document_page_id == page_record.id,
                            PageOcrResult.engine == provider.provider_id,
                            PageOcrResult.scope == scope_name,
                            or_(PageOcrResult.region_id == region_id, and_(PageOcrResult.region_id.is_(None), region_id is None)),
                        )
                    ).scalar_one_or_none()
                    if stored_result is None:
                        stored_result = PageOcrResult(
                            document_page_id=page_record.id,
                            engine=str(saved_payload["engine"]),
                            engine_version=str(saved_payload["engine_version"]),
                            language=str(saved_payload["language"]),
                            text=str(saved_payload["text"]),
                            status=str(saved_payload["status"]),
                            confidence=saved_payload["confidence"],
                            processing_time_ms=saved_payload["processing_time_ms"],
                            warnings=str(saved_payload["warnings"]),
                            scope=scope_name,
                            region_id=str(region_id) if region_id is not None else None,
                        )
                        db.add(stored_result)
                    else:
                        stored_result.engine_version = str(saved_payload["engine_version"])
                        stored_result.language = str(saved_payload["language"])
                        stored_result.text = str(saved_payload["text"])
                        stored_result.status = str(saved_payload["status"])
                        stored_result.confidence = saved_payload["confidence"]
                        stored_result.processing_time_ms = saved_payload["processing_time_ms"]
                        stored_result.warnings = str(saved_payload["warnings"])
                        stored_result.scope = scope_name
                        stored_result.region_id = str(region_id) if region_id is not None else None
                    db.flush()
                    results.append(
                        {
                            "id": stored_result.id,
                            "document_page_id": page_record.id,
                            "page_number": page_record.page_number,
                            "engine": stored_result.engine,
                            "engine_version": stored_result.engine_version,
                            "language": stored_result.language,
                            "text": stored_result.text,
                            "status": stored_result.status,
                            "confidence": stored_result.confidence,
                            "processing_time_ms": stored_result.processing_time_ms,
                            "warnings": stored_result.warnings,
                            "scope": stored_result.scope,
                            "region_id": stored_result.region_id,
                            "created_at": stored_result.created_at,
                            "updated_at": stored_result.updated_at,
                        }
                    )
        db.commit()
    finally:
        pdf_document.close()

    response_results = [PageOcrResultRead.model_validate(item) for item in results]
    return {
        "document_id": document.id,
        "provider": provider_mode,
        "mode": provider_mode,
        "page_count": len(response_results),
        "results": [result.model_dump() for result in response_results],
    }
