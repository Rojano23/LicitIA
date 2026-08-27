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
    processing_status: str = "PENDING"
    page_count: int = 0
    revision_of_document_id: str | None = None
    conflict_resolution_action: str | None = None
    revision_number: int = 1
    is_current: bool = True
    imported_at: datetime
    text_extracted_at: datetime | None = None


class DocumentPageRegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_page_id: str
    region_index: int
    region_type: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float
    area_ratio: float
    created_at: datetime


class PageOcrResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_page_id: str
    page_number: int | None = None
    engine: str
    engine_version: str
    language: str
    text: str
    status: str
    confidence: float | None = None
    processing_time_ms: int | None = None
    warnings: str | None = None
    scope: str = "FULL_PAGE"
    region_id: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    page_number: int
    text: str
    char_count: int = 0
    extraction_method: str = "NATIVE_PDF"
    status: str
    extracted_at: datetime
    content_profile: str = "TEXT_ONLY"
    regions: list[DocumentPageRegionRead] = Field(default_factory=list)
    ocr_results: list[PageOcrResultRead] = Field(default_factory=list)


class DocumentExtractionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    processing_status: str
    page_count: int
    extracted_at: datetime | None = None


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


class OcrProviderStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: str
    provider_name: str
    status: str
    version: str | None = None
    status_reason: str | None = None


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    normalized_content_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    char_count: int
    content_sha256: str
    created_at: datetime


class NormalizedContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_page_id: str
    page_ocr_result_id: str | None = None
    region_id: str | None = None
    source_type: str
    source_scope: str
    engine: str | None = None
    normalized_text: str
    char_count: int
    content_sha256: str
    created_at: datetime
    updated_at: datetime
    chunks: list[DocumentChunkRead] = Field(default_factory=list)


class NormalizationSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    page_count: int
    normalized_sources: int
    chunks_created: int
    skipped_empty_sources: int
    acquisition_gaps: int
    created: int
    updated: int


class DocumentOcrResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    provider: str
    mode: str
    page_count: int
    results: list[PageOcrResultRead]
