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


class DocumentClassificationEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_page_id: str | None = None
    normalized_content_id: str | None = None
    document_chunk_id: str | None = None
    source_kind: str
    signal: str
    excerpt: str
    weight_or_score: int


class DocumentClassificationTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tag: str
    score: int


class DocumentClassificationCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    score: int


class DocumentClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    suggested_type: str
    suggested_score: int
    effective_type: str
    classification_status: str
    is_composite: bool
    human_type: str | None = None
    human_note: str | None = None
    candidate_scores: list[DocumentClassificationCandidateRead] = Field(default_factory=list)
    functional_tags: list[DocumentClassificationTagRead] = Field(default_factory=list)
    evidence: list[DocumentClassificationEvidenceRead] = Field(default_factory=list)
    input_fingerprint_sha256: str
    not_ready: bool = False


class DocumentOcrResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    provider: str
    mode: str
    page_count: int
    results: list[PageOcrResultRead]


class DocumentReferenceCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    original_filename: str


class DocumentReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_document_id: str
    document_page_id: str | None = None
    normalized_content_id: str | None = None
    document_chunk_id: str | None = None
    source_scope: str | None = None
    source_type: str | None = None
    source_engine: str | None = None
    source_region_id: str | None = None
    raw_reference_text: str
    normalized_reference_key: str
    reference_kind: str
    relationship_hint: str
    resolution_status: str
    resolved_target_document_id: str | None = None
    resolved_target_filename: str | None = None
    ambiguous_candidates: list[DocumentReferenceCandidateRead] = Field(default_factory=list)
    human_target_document_id: str | None = None
    human_note: str | None = None
    human_decision: str | None = None
    excerpt: str
    extractor_version: str
    created_at: datetime
    updated_at: datetime
    page_number: int | None = None


class DocumentRelationshipSupportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference_id: str
    raw_reference_text: str
    normalized_reference_key: str
    page_number: int | None = None
    excerpt: str


class DocumentRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tender_id: str
    source_document_id: str
    source_document_filename: str | None = None
    target_document_id: str
    target_document_filename: str | None = None
    relationship_type: str
    supporting_references: list[DocumentRelationshipSupportRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentReferenceCountsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_reference_mentions: int
    resolved_references: int
    ambiguous_references: int
    unresolved_references: int
    human_resolved_references: int
    ignored_references: int
    resolved_relationships: int


class DocumentReferenceAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    status: str
    extractor_version: str
    input_fingerprint_sha256: str
    references: list[DocumentReferenceRead] = Field(default_factory=list)
    relationships: list[DocumentRelationshipRead] = Field(default_factory=list)
    counts: DocumentReferenceCountsRead


class DocumentReferenceDecisionWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    human_target_document_id: str | None = None
    human_note: str | None = Field(default=None, max_length=2000)
