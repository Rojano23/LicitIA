from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import PurePosixPath
from sqlalchemy import select
from sqlalchemy.orm import Session

ALLOWED_CONFLICT_ACTIONS = {"NONE", "IMPORT_INDEPENDENT", "NEW_REVISION"}

from app.config import get_settings
from app.database import get_db
from app.models import Tender, TenderDocument, TenderDocumentStatus
from app.schemas import DocumentImportResult, TenderCreate, TenderDocumentRead, TenderRead

settings = get_settings()

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
