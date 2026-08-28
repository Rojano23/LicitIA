from datetime import date, datetime, time

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
    processing_status: str | None = None


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
    relationship_origin: str | None = None
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


class AuditFindingRead(BaseModel):
    code: str
    severity: str
    message: str
    document_id: str | None = None
    document_filename: str | None = None
    metadata: dict[str, str | int | float | bool | None | list[dict[str, str | int | float | bool | None]]] = Field(default_factory=dict)


class AuditEngineVersionsRead(BaseModel):
    classification_expected_version: str
    reference_expected_version: str


class AuditReadinessRuleRead(BaseModel):
    ready: str
    partially_ready: str
    not_ready: str


class AuditDocumentsSummaryRead(BaseModel):
    total_documents: int
    current_documents: int
    non_current_documents: int


class AuditAcquisitionSummaryRead(BaseModel):
    documents_with_pages: int
    documents_with_native_text: int
    documents_requiring_ocr: int
    documents_with_ocr_results: int
    documents_with_no_usable_text: int
    documents_pending_or_failed: int


class AuditNormalizationSummaryRead(BaseModel):
    current_documents_with_normalized_content: int
    current_documents_without_normalized_content: int
    total_normalized_sources: int
    total_chunks: int
    pages_with_normalized_sources: int
    pages_without_normalized_sources_despite_text: int


class AuditClassificationStatusCountsRead(BaseModel):
    SUGGESTED: int = 0
    CONFIRMED: int = 0
    NEEDS_REVIEW: int = 0
    OVERRIDDEN: int = 0


class AuditClassificationSummaryRead(BaseModel):
    classified_documents: int
    unclassified_documents: int
    status_counts: AuditClassificationStatusCountsRead
    unknown_documents: int
    document_package_count: int
    non_composite_count: int
    stale_classifier_version_documents: int


class AuditReferenceStatusCountsRead(BaseModel):
    AUTO_RESOLVED: int = 0
    AMBIGUOUS: int = 0
    UNRESOLVED: int = 0
    HUMAN_RESOLVED: int = 0
    IGNORED: int = 0


class AuditReferencesSummaryRead(BaseModel):
    documents_analyzed: int
    documents_not_analyzed_not_ready: int
    documents_ready_not_analyzed: int
    status_counts: AuditReferenceStatusCountsRead
    stale_reference_version_documents: int


class AuditRelationshipTypeCountsRead(BaseModel):
    REFERENCES: int = 0
    MODIFIES: int = 0


class AuditRelationshipsSummaryRead(BaseModel):
    total_edges: int
    relationship_type_counts: AuditRelationshipTypeCountsRead
    duplicate_edge_count: int
    self_edge_count: int


class AuditIntegritySummaryRead(BaseModel):
    filename_collision_count: int
    duplicate_current_sha256_count: int
    missing_storage_count: int
    stale_analysis_count: int
    total_findings: int


class AuditSummaryRead(BaseModel):
    documents: AuditDocumentsSummaryRead
    acquisition: AuditAcquisitionSummaryRead
    normalization: AuditNormalizationSummaryRead
    classification: AuditClassificationSummaryRead
    references: AuditReferencesSummaryRead
    relationships: AuditRelationshipsSummaryRead
    integrity: AuditIntegritySummaryRead


class DocumentIntelligenceAuditRowRead(BaseModel):
    document_id: str
    document_short_id: str
    filename: str
    is_current: bool
    processing_status: str
    page_count: int
    text_acquisition_state: str
    storage_exists: bool
    normalized: bool
    normalized_source_count: int
    chunk_count: int
    classification_type: str
    classification_status: str
    classification_version: str | None = None
    reference_analysis_status: str
    reference_extractor_version: str | None = None
    reference_count: int
    auto_resolved_reference_count: int
    human_resolved_reference_count: int
    ambiguous_reference_count: int
    unresolved_reference_count: int
    ignored_reference_count: int
    integrity_findings: list[str] = Field(default_factory=list)


class AuditReferenceSourceDocumentRead(BaseModel):
    document_id: str
    filename: str


class UnresolvedReferenceGroupRead(BaseModel):
    normalized_reference_key: str
    mention_count: int
    source_documents: list[AuditReferenceSourceDocumentRead] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    sample_excerpt: str
    candidate_count: int


class AmbiguousCandidateRead(BaseModel):
    document_id: str
    filename: str
    document_short_id: str
    processing_status: str | None = None


class AmbiguousReferenceGroupRead(BaseModel):
    source_document_id: str
    source_document_filename: str
    normalized_reference_key: str
    candidate_documents: list[AmbiguousCandidateRead] = Field(default_factory=list)
    mention_count: int
    ambiguous_mention_count: int
    human_resolved_mention_count: int
    pages: list[int] = Field(default_factory=list)


class RelationshipEdgeSummaryRead(BaseModel):
    source_document_id: str
    source_document_filename: str | None = None
    relationship_type: str
    target_document_id: str
    target_document_filename: str | None = None
    supporting_reference_count: int


class RelationshipSummaryRead(BaseModel):
    total_edges: int
    relationship_type_counts: AuditRelationshipTypeCountsRead
    duplicate_edge_count: int
    self_edge_count: int
    edges: list[RelationshipEdgeSummaryRead] = Field(default_factory=list)


class RegistryFilenameCollisionItemRead(BaseModel):
    document_id: str
    sha256: str
    processing_status: str


class RegistryFilenameCollisionRead(BaseModel):
    filename: str
    documents: list[RegistryFilenameCollisionItemRead] = Field(default_factory=list)


class RegistryDuplicateShaItemRead(BaseModel):
    document_id: str
    original_filename: str
    processing_status: str


class RegistryDuplicateShaRead(BaseModel):
    sha256: str
    documents: list[RegistryDuplicateShaItemRead] = Field(default_factory=list)


class RegistryAnomaliesRead(BaseModel):
    filename_collisions: list[RegistryFilenameCollisionRead] = Field(default_factory=list)
    duplicate_current_sha256: list[RegistryDuplicateShaRead] = Field(default_factory=list)


class DocumentIntelligenceAuditRead(BaseModel):
    tender_id: str
    audit_version: str
    generated_at: datetime
    overall_readiness: str
    readiness_rule: AuditReadinessRuleRead
    engine_versions: AuditEngineVersionsRead
    summary: AuditSummaryRead
    document_rows: list[DocumentIntelligenceAuditRowRead] = Field(default_factory=list)
    findings: list[AuditFindingRead] = Field(default_factory=list)
    unresolved_reference_groups: list[UnresolvedReferenceGroupRead] = Field(default_factory=list)
    ambiguous_reference_groups: list[AmbiguousReferenceGroupRead] = Field(default_factory=list)
    relationship_summary: RelationshipSummaryRead
    registry_anomalies: RegistryAnomaliesRead


class RelationshipBaselineCountsRead(BaseModel):
    total_physical_documents: int
    current_documents: int
    documents_analyzed_for_references: int
    total_reference_mentions: int
    relationship_edge_count: int
    unresolved_reference_groups_count: int
    ambiguous_reference_groups_count: int
    duplicate_edge_count: int
    self_edge_count: int


class DocumentMapEntryRead(BaseModel):
    source_document_id: str
    source_filename: str | None = None
    relationship_type: str
    target_document_id: str
    target_filename: str | None = None
    supporting_reference_count: int
    supporting_pages: list[int] = Field(default_factory=list)
    resolution_origin: str


class TenderRelationshipBaselineRead(BaseModel):
    tender_id: str
    baseline_version: str
    source_audit_version: str
    generated_at: datetime
    counts: RelationshipBaselineCountsRead
    reference_status_counts: AuditReferenceStatusCountsRead
    relationship_type_counts: AuditRelationshipTypeCountsRead
    unresolved_reference_groups: list[UnresolvedReferenceGroupRead] = Field(default_factory=list)
    ambiguous_reference_groups: list[AmbiguousReferenceGroupRead] = Field(default_factory=list)
    relationship_edges: list[RelationshipEdgeSummaryRead] = Field(default_factory=list)
    document_map: list[DocumentMapEntryRead] = Field(default_factory=list)


class TenderEventEvidenceRead(BaseModel):
    id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str


class TenderEventRead(BaseModel):
    id: str
    tender_id: str
    semantic_key: str
    event_type: str
    title: str
    event_date: date | None = None
    event_time: time | None = None
    date_precision: str
    timezone: str | None = None
    review_status: str
    detection_origin: str
    detector_version: str
    source_document_id: str | None = None
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str | None = None
    raw_date_text: str | None = None
    human_event_type: str | None = None
    human_title: str | None = None
    human_event_date: date | None = None
    human_event_time: time | None = None
    human_date_precision: str | None = None
    human_timezone: str | None = None
    human_note: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence: list[TenderEventEvidenceRead] = Field(default_factory=list)


class TenderTimelineCountsRead(BaseModel):
    total_events: int
    suggested_events: int
    confirmed_events: int
    rejected_events: int
    duplicate_semantic_count: int


class TenderTimelineRead(BaseModel):
    tender_id: str
    timeline_version: str
    generated_at: datetime
    counts: TenderTimelineCountsRead
    events: list[TenderEventRead] = Field(default_factory=list)


class TenderEventDecisionWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    event_type: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    event_date: date | None = None
    event_time: time | None = None
    date_precision: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=32)
    human_note: str | None = Field(default=None, max_length=2000)


class TenderChangeTargetCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    original_filename: str
    processing_status: str | None = None


class TenderChangeEvidenceRead(BaseModel):
    id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str


class TenderChangeRead(BaseModel):
    id: str
    tender_id: str
    semantic_key: str
    change_type: str
    target_reference_key: str | None = None
    target_document_id: str | None = None
    target_filename: str | None = None
    target_candidate_documents: list[TenderChangeTargetCandidateRead] = Field(default_factory=list)
    target_locator_text: str | None = None
    before_text: str | None = None
    after_text: str | None = None
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    source_event_date: date | None = None
    review_status: str
    detection_origin: str
    detector_version: str
    human_change_type: str | None = None
    human_target_document_id: str | None = None
    human_target_locator_text: str | None = None
    human_before_text: str | None = None
    human_after_text: str | None = None
    human_note: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence: list[TenderChangeEvidenceRead] = Field(default_factory=list)


class TenderChangesCountsRead(BaseModel):
    total_changes: int
    suggested_changes: int
    confirmed_changes: int
    rejected_changes: int
    duplicate_semantic_count: int


class TenderChangesRead(BaseModel):
    tender_id: str
    changes_version: str
    generated_at: datetime
    counts: TenderChangesCountsRead
    changes: list[TenderChangeRead] = Field(default_factory=list)


class TenderChangeDecisionWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    change_type: str | None = Field(default=None, max_length=32)
    target_document_id: str | None = None
    target_locator_text: str | None = Field(default=None, max_length=255)
    before_text: str | None = Field(default=None, max_length=4000)
    after_text: str | None = Field(default=None, max_length=4000)
    human_note: str | None = Field(default=None, max_length=2000)
