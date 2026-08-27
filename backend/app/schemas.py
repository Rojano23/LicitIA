from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    institution_profile: str | None = Field(default=None, max_length=255)
    external_reference: str | None = Field(default=None, max_length=255)


class TenderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    institution_profile: str | None = None
    external_reference: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class TenderDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tender_id: str
    original_filename: str
    source_relative_path: str | None = None
    stored_relative_path: str
    mime_type: str | None = None
    file_size_bytes: int
    sha256: str
    status: str
    revision_of_document_id: str | None = None
    conflict_resolution_action: str | None = None
    revision_number: int = 1
    is_current: bool = True
    imported_at: datetime


class DocumentImportResult(BaseModel):
    filename: str
    source_relative_path: str | None = None
    status: str
    message: str | None = None
    document_id: str | None = None
    stored_relative_path: str | None = None
    sha256: str | None = None
    revision_of_document_id: str | None = None
    conflict_resolution_action: str | None = None
    revision_number: int | None = None
    is_current: bool | None = None
