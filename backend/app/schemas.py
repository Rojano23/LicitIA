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


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=64)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    legal_name: str | None = None
    tax_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CompanyDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    original_filename: str
    source_relative_path: str | None = None
    stored_relative_path: str
    mime_type: str | None = None
    file_size_bytes: int
    sha256: str
    status: str
    document_type: str | None = None
    label: str | None = None
    issuer: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    metadata_note: str | None = None
    archived_at: datetime | None = None
    revision_of_document_id: str | None = None
    conflict_resolution_action: str | None = None
    revision_number: int = 1
    is_current: bool = True
    imported_at: datetime
    updated_at: datetime


class CompanyDocumentImportResult(BaseModel):
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


class CompanyDocumentUpdate(BaseModel):
    document_type: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    issuer: str | None = Field(default=None, max_length=255)
    issue_date: date | None = None
    expiration_date: date | None = None
    metadata_note: str | None = Field(default=None, max_length=2000)


class CompanyDocumentArchiveWrite(BaseModel):
    archived: bool = True


class CompanyEvidenceSourceDocumentRead(BaseModel):
    id: str
    company_id: str
    original_filename: str
    document_type: str | None = None
    label: str | None = None
    status: str
    archived_at: datetime | None = None
    revision_number: int
    is_current: bool


class CompanyEvidenceReviewRead(BaseModel):
    id: str
    company_id: str
    company_evidence_id: str
    review_status: str
    review_note: str | None = None
    reviewed_fingerprint: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CompanyEvidenceRead(BaseModel):
    id: str
    company_id: str
    company_document_id: str
    evidence_type: str
    subject_kind: str
    subject_name: str | None = None
    canonical_statement: str
    issuer: str | None = None
    reference_number: str | None = None
    issued_on: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    analysis_status: str
    origin: str
    extractor_version: str
    source_page: int | None = None
    source_locator: str | None = None
    source_excerpt: str
    semantic_fingerprint: str
    system_warnings: list[str] = Field(default_factory=list)
    review_freshness: str
    created_at: datetime
    updated_at: datetime
    source_document: CompanyEvidenceSourceDocumentRead
    review: CompanyEvidenceReviewRead | None = None


class CompanyEvidenceSummaryRead(BaseModel):
    evidence_count: int
    determined_count: int
    review_required_count: int
    validated_count: int
    pending_review_count: int
    rejected_count: int
    historical_source_count: int
    current_review_count: int
    stale_review_count: int
    not_reviewed_count: int


class CompanyEvidenceCollectionRead(BaseModel):
    summary: CompanyEvidenceSummaryRead
    evidence: list[CompanyEvidenceRead] = Field(default_factory=list)


class CompanyDocumentEvidenceAnalysisSummaryRead(CompanyEvidenceSummaryRead):
    document_id: str
    company_id: str
    text_extraction_status: str
    extractor_version: str
    warnings: list[str] = Field(default_factory=list)


class CompanyDocumentEvidenceAnalysisRead(BaseModel):
    summary: CompanyDocumentEvidenceAnalysisSummaryRead
    evidence: list[CompanyEvidenceRead] = Field(default_factory=list)


class CompanyEvidenceReviewWrite(BaseModel):
    review_status: str = Field(..., min_length=1, max_length=32)
    review_note: str | None = Field(default=None, max_length=2000)


class CompanyEvidenceManualWrite(BaseModel):
    evidence_type: str = Field(..., min_length=1, max_length=64)
    subject_kind: str = Field(..., min_length=1, max_length=32)
    subject_name: str | None = Field(default=None, max_length=255)
    canonical_statement: str = Field(..., min_length=1, max_length=2000)
    issuer: str | None = Field(default=None, max_length=255)
    reference_number: str | None = Field(default=None, max_length=255)
    issued_on: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_locator: str | None = Field(default=None, max_length=512)
    source_excerpt: str = Field(..., min_length=1, max_length=4000)
    review_note: str | None = Field(default=None, max_length=2000)


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


class EffectiveScopeChangeRead(BaseModel):
    id: str
    semantic_key: str
    review_status: str
    change_type: str
    target_document_id: str | None = None
    target_filename: str | None = None
    target_reference_key: str | None = None
    target_locator_text: str | None = None
    normalized_locator: str
    before_text: str | None = None
    after_text: str | None = None
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    source_is_current: bool
    temporal_status: str
    temporal_event_date: date | None = None
    temporal_event_time: time | None = None
    temporal_date_precision: str | None = None
    temporal_event_ids: list[str] = Field(default_factory=list)
    temporal_reason: str
    human_change_type: str | None = None
    human_target_document_id: str | None = None
    human_target_locator_text: str | None = None
    human_before_text: str | None = None
    human_after_text: str | None = None
    human_note: str | None = None


class TenderEffectiveStateScopeRead(BaseModel):
    scope_key: str
    scope_kind: str
    target_document_id: str | None = None
    target_filename: str | None = None
    target_reference_key: str | None = None
    target_locator_text: str | None = None
    normalized_locator: str
    resolution_status: str
    effective_mutation: EffectiveScopeChangeRead | None = None
    confirmed_mutations: list[EffectiveScopeChangeRead] = Field(default_factory=list)
    confirmed_non_replacing_assertions: list[EffectiveScopeChangeRead] = Field(default_factory=list)
    pending_changes: list[EffectiveScopeChangeRead] = Field(default_factory=list)
    rejected_changes: list[EffectiveScopeChangeRead] = Field(default_factory=list)
    non_current_confirmed_changes: list[EffectiveScopeChangeRead] = Field(default_factory=list)
    temporal_reason: str
    warnings: list[str] = Field(default_factory=list)


class TenderEffectiveStateSummaryRead(BaseModel):
    total_scopes: int
    determined: int
    pending_review: int
    ambiguous_precedence: int
    unresolved_target: int
    no_confirmed_change: int


class TenderEffectiveStateRead(BaseModel):
    tender_id: str
    state_version: str
    generated_at: datetime
    summary: TenderEffectiveStateSummaryRead
    scopes: list[TenderEffectiveStateScopeRead] = Field(default_factory=list)


class SnapshotReadinessRead(BaseModel):
    code: str
    label: str
    reason: str
    understanding_scope_note: str


class SnapshotVersionsRead(BaseModel):
    document_intelligence_audit_version: str | None = None
    relationship_baseline_version: str | None = None
    timeline_version: str | None = None
    changes_version: str | None = None
    effective_state_version: str | None = None


class SnapshotDocumentsSummaryRead(BaseModel):
    total_documents: int
    current_documents: int
    non_current_documents: int
    ready_for_analysis: int
    pending_processing: int
    with_normalized_content: int
    without_normalized_content: int
    classified: int
    unclassified: int
    confirmed_classifications: int
    suggested_classifications: int


class SnapshotRelationshipsSummaryRead(BaseModel):
    total_reference_mentions: int
    reference_status_counts: AuditReferenceStatusCountsRead
    relationship_edge_count: int
    relationship_type_counts: AuditRelationshipTypeCountsRead
    duplicate_edge_count: int
    self_edge_count: int
    unresolved_reference_groups_count: int
    ambiguous_reference_groups_count: int


class SnapshotTimelineSummaryRead(BaseModel):
    total_events: int
    suggested_events: int
    confirmed_events: int
    rejected_events: int
    duplicate_semantic_count: int


class SnapshotChangesSummaryRead(BaseModel):
    total_changes: int
    suggested_changes: int
    confirmed_changes: int
    rejected_changes: int
    duplicate_semantic_count: int
    counts_by_change_type: dict[str, int] = Field(default_factory=dict)
    unresolved_target_count: int
    ambiguous_target_count: int
    confirmed_mutating_count: int
    confirmed_non_replacing_count: int


class SnapshotEffectiveStateSummaryRead(BaseModel):
    total_scopes: int
    determined: int
    pending_review: int
    ambiguous_precedence: int
    unresolved_target: int
    no_confirmed_change: int


class SnapshotPendingActionsSummaryRead(BaseModel):
    total: int
    blocking: int
    warning: int
    info: int


class SnapshotIntegritySummaryRead(BaseModel):
    audit_overall_readiness: str
    total_findings: int
    cross_layer_issue_count: int


class SnapshotSummaryRead(BaseModel):
    documents: SnapshotDocumentsSummaryRead
    relationships: SnapshotRelationshipsSummaryRead
    timeline: SnapshotTimelineSummaryRead
    changes: SnapshotChangesSummaryRead
    effective_state: SnapshotEffectiveStateSummaryRead
    pending_actions: SnapshotPendingActionsSummaryRead
    integrity: SnapshotIntegritySummaryRead


class SnapshotDocumentMatrixRowRead(BaseModel):
    document_id: str
    filename: str
    processing_status: str
    normalized: bool
    classification_status: str
    reference_analysis_status: str
    event_count: int
    change_count: int
    findings_count: int


class SnapshotDocumentMapEntryRead(BaseModel):
    source_document_id: str
    source_filename: str | None = None
    relationship_type: str
    target_document_id: str
    target_filename: str | None = None
    supporting_reference_count: int
    supporting_pages: list[int] = Field(default_factory=list)
    resolution_origin: str
    supporting_change_ids: list[str] = Field(default_factory=list)


class SnapshotEffectiveScopeRead(BaseModel):
    scope_key: str
    target_document_id: str | None = None
    target_filename: str | None = None
    target_reference_key: str | None = None
    target_locator_text: str | None = None
    resolution_status: str
    effective_change_id: str | None = None
    pending_change_count: int


class SnapshotCrossLayerIssueRead(BaseModel):
    code: str
    severity: str
    message: str
    related_entity_id: str | None = None
    document_id: str | None = None


class SnapshotIntegrityRead(BaseModel):
    document_intelligence_audit: dict[str, object]
    cross_layer_issues: list[SnapshotCrossLayerIssueRead] = Field(default_factory=list)


class SnapshotPendingActionRead(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    document_id: str | None = None
    source_page: int | None = None
    related_entity_id: str | None = None


class SnapshotDocumentsRead(BaseModel):
    summary: SnapshotDocumentsSummaryRead
    matrix: list[SnapshotDocumentMatrixRowRead] = Field(default_factory=list)


class SnapshotRelationshipsRead(BaseModel):
    summary: SnapshotRelationshipsSummaryRead
    unresolved_reference_groups: list[UnresolvedReferenceGroupRead] = Field(default_factory=list)
    ambiguous_reference_groups: list[AmbiguousReferenceGroupRead] = Field(default_factory=list)
    document_map: list[SnapshotDocumentMapEntryRead] = Field(default_factory=list)


class SnapshotTimelineRead(BaseModel):
    summary: SnapshotTimelineSummaryRead
    events: list[TenderEventRead] = Field(default_factory=list)


class SnapshotChangesRead(BaseModel):
    summary: SnapshotChangesSummaryRead
    items: list[TenderChangeRead] = Field(default_factory=list)


class SnapshotEffectiveStateRead(BaseModel):
    summary: SnapshotEffectiveStateSummaryRead
    scopes: list[SnapshotEffectiveScopeRead] = Field(default_factory=list)


class TenderStateSnapshotRead(BaseModel):
    tender_id: str
    snapshot_version: str
    generated_at: datetime
    readiness: SnapshotReadinessRead
    versions: SnapshotVersionsRead
    summary: SnapshotSummaryRead
    documents: SnapshotDocumentsRead
    relationships: SnapshotRelationshipsRead
    timeline: SnapshotTimelineRead
    changes: SnapshotChangesRead
    effective_state: SnapshotEffectiveStateRead
    integrity: SnapshotIntegrityRead
    pending_actions: list[SnapshotPendingActionRead] = Field(default_factory=list)
    top_pending_actions: list[SnapshotPendingActionRead] = Field(default_factory=list)


class RequirementCandidateEvidenceRead(BaseModel):
    id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    document_page_id: str | None = None
    normalized_content_id: str | None = None


class RequirementCandidateRead(BaseModel):
    id: str
    tender_id: str
    semantic_key: str
    requirement_text: str
    actor_text: str | None = None
    modality_text: str | None = None
    review_status: str
    detection_origin: str
    detector_version: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    document_page_id: str | None = None
    normalized_content_id: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence: list[RequirementCandidateEvidenceRead] = Field(default_factory=list)


class RequirementCandidatesSummaryRead(BaseModel):
    total: int
    suggested: int
    confirmed: int
    rejected: int
    documents_with_candidates: int
    pages_with_candidates: int
    explicit_actor_count: int
    by_modality: dict[str, int] = Field(default_factory=dict)


class TenderRequirementCandidatesRead(BaseModel):
    tender_id: str
    requirements_version: str
    generated_at: datetime
    summary: RequirementCandidatesSummaryRead
    candidates: list[RequirementCandidateRead] = Field(default_factory=list)


class RequirementSourceOccurrenceRead(BaseModel):
    candidate_id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    requirement_text: str
    source_excerpt: str
    actor_text: str | None = None
    modality_text: str | None = None
    document_page_id: str | None = None
    normalized_content_id: str | None = None
    is_primary_source: bool = False
    link_origin: str


class RequirementRead(BaseModel):
    id: str
    tender_id: str
    canonical_key: str
    canonical_text: str
    category: str
    normalization_status: str
    normalizer_version: str
    normalization_confidence: float | None = None
    normalization_reason: str | None = None
    source_occurrence_count: int
    primary_source: RequirementSourceOccurrenceRead | None = None
    candidates: list[RequirementSourceOccurrenceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RequirementsSummaryRead(BaseModel):
    candidate_count: int
    requirement_count: int
    normalized_count: int
    review_required_count: int
    merged_requirement_count: int
    single_source_requirement_count: int
    category_counts: dict[str, int] = Field(default_factory=dict)
    unknown_count: int


class TenderRequirementsRead(BaseModel):
    tender_id: str
    normalizer_version: str
    generated_at: datetime
    scope_note: str
    summary: RequirementsSummaryRead
    requirements: list[RequirementRead] = Field(default_factory=list)


class RequirementEvidenceExpectationRead(BaseModel):
    id: str
    requirement_semantics_id: str
    requirement_id: str
    evidence_type: str
    evidence_description: str
    source_candidate_id: str | None = None
    source_document_id: str | None = None
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    analyzer_version: str
    created_at: datetime
    updated_at: datetime


class RequirementSemanticsRead(BaseModel):
    requirement_id: str
    canonical_text: str
    category: str
    normalization_status: str
    applicability: str
    condition_text: str | None = None
    interpretation_status: str
    interpretation_reason: str | None = None
    evidence_mode: str
    expected_evidence: list[RequirementEvidenceExpectationRead] = Field(default_factory=list)
    primary_source: RequirementSourceOccurrenceRead | None = None


class RequirementSemanticsSummaryRead(BaseModel):
    requirement_count: int
    mandatory_count: int
    conditional_count: int
    unknown_applicability_count: int
    determined_count: int
    review_required_count: int
    explicit_artifact_count: int
    direct_verification_count: int
    unspecified_evidence_count: int
    evidence_review_required_count: int
    evidence_expectation_count: int
    evidence_type_counts: dict[str, int] = Field(default_factory=dict)


class TenderRequirementSemanticsRead(BaseModel):
    tender_id: str
    analyzer_version: str
    generated_at: datetime
    scope_note: str
    summary: RequirementSemanticsSummaryRead
    requirements: list[RequirementSemanticsRead] = Field(default_factory=list)


class RequirementVersionLinkRead(BaseModel):
    id: str
    change_id: str
    link_kind: str
    matching_basis: str
    target_locator_text: str | None = None
    before_text: str | None = None
    after_text: str | None = None
    predecessor_requirement_id: str | None = None
    predecessor_canonical_text: str | None = None
    successor_requirement_id: str | None = None
    successor_canonical_text: str | None = None
    analyzer_version: str
    created_at: datetime
    updated_at: datetime


class RequirementEffectiveItemRead(BaseModel):
    requirement_id: str
    canonical_text: str
    category: str
    normalization_status: str
    effective_status: str
    effective_source_document_id: str | None = None
    effective_source_filename: str | None = None
    source_occurrence_count: int
    primary_source: RequirementSourceOccurrenceRead | None = None
    applicability: str
    interpretation_status: str
    evidence_mode: str
    evidence_reasons: list[str] = Field(default_factory=list)


class RequirementEffectiveSummaryRead(BaseModel):
    requirement_count: int
    effective_count: int
    superseded_count: int
    ambiguous_count: int
    unresolved_count: int
    version_link_count: int


class TenderRequirementEffectiveStateRead(BaseModel):
    tender_id: str
    analyzer_version: str
    generated_at: datetime
    scope_note: str
    summary: RequirementEffectiveSummaryRead
    requirements: list[RequirementEffectiveItemRead] = Field(default_factory=list)
    version_links: list[RequirementVersionLinkRead] = Field(default_factory=list)


class RequirementMatrixItemRead(BaseModel):
    requirement_id: str
    canonical_text: str
    category: str
    normalization_status: str
    source_occurrence_count: int
    primary_source: RequirementSourceOccurrenceRead | None = None
    applicability: str
    condition_text: str | None = None
    interpretation_status: str
    interpretation_reason: str | None = None
    evidence_mode: str
    expected_evidence: list[RequirementEvidenceExpectationRead] = Field(default_factory=list)
    effective_status: str
    effective_source_document_id: str | None = None
    effective_source_filename: str | None = None
    effective_reasons: list[str] = Field(default_factory=list)
    system_warnings: list[str] = Field(default_factory=list)
    representation_fingerprint: str
    review_status: str
    review_note: str | None = None
    reviewed_fingerprint: str | None = None
    review_freshness: str
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RequirementMatrixSummaryRead(BaseModel):
    total_requirements: int
    effective_requirements: int
    pending_review_count: int
    approved_count: int
    needs_review_count: int
    rejected_count: int
    current_review_count: int
    stale_review_count: int
    not_reviewed_count: int


class TenderRequirementMatrixRead(BaseModel):
    tender_id: str
    matrix_version: str
    generated_at: datetime
    scope_note: str
    summary: RequirementMatrixSummaryRead
    requirements: list[RequirementMatrixItemRead] = Field(default_factory=list)


class RequirementReviewWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    review_note: str | None = Field(default=None, max_length=2000)


class EvaluationModelEvidenceRead(BaseModel):
    id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    evidence_role: str


class TenderEvaluationModelRead(BaseModel):
    suggested_method: str
    effective_method: str
    review_status: str
    summary: str
    human_method: str | None = None
    human_summary: str | None = None
    detector_version: str
    created_at: datetime
    updated_at: datetime
    evidence: list[EvaluationModelEvidenceRead] = Field(default_factory=list)


class EvaluationCriterionEvidenceRead(BaseModel):
    id: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    evidence_role: str


class EvaluationCriterionRead(BaseModel):
    id: str
    tender_id: str
    evaluation_model_id: str
    semantic_key: str
    criterion_type: str
    category: str | None = None
    title: str
    criterion_text: str
    weight_value: float | None = None
    weight_unit: str | None = None
    threshold_operator: str | None = None
    threshold_value: float | None = None
    threshold_unit: str | None = None
    is_exclusionary: bool | None = None
    review_status: str
    detection_origin: str
    detector_version: str
    source_document_id: str
    source_filename: str | None = None
    source_page: int | None = None
    source_excerpt: str
    human_criterion_type: str | None = None
    human_category: str | None = None
    human_title: str | None = None
    human_criterion_text: str | None = None
    human_weight_value: float | None = None
    human_weight_unit: str | None = None
    human_threshold_operator: str | None = None
    human_threshold_value: float | None = None
    human_threshold_unit: str | None = None
    human_is_exclusionary: bool | None = None
    human_note: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence: list[EvaluationCriterionEvidenceRead] = Field(default_factory=list)


class EvaluationCriteriaSummaryRead(BaseModel):
    total: int
    suggested: int
    confirmed: int
    rejected: int
    exclusionary: int
    scoring: int
    gates: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)


class TenderEvaluationRead(BaseModel):
    tender_id: str
    evaluation_version: str
    generated_at: datetime
    model: TenderEvaluationModelRead
    criteria_summary: EvaluationCriteriaSummaryRead
    criteria: list[EvaluationCriterionRead] = Field(default_factory=list)


class TenderEvaluationModelDecisionWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    method: str | None = Field(default=None, max_length=64)
    summary: str | None = Field(default=None, max_length=4000)


class EvaluationCriterionDecisionWrite(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    criterion_type: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    criterion_text: str | None = Field(default=None, max_length=4000)
    weight_value: float | None = None
    weight_unit: str | None = Field(default=None, max_length=32)
    threshold_operator: str | None = Field(default=None, max_length=32)
    threshold_value: float | None = None
    threshold_unit: str | None = Field(default=None, max_length=32)
    is_exclusionary: bool | None = None
    human_note: str | None = Field(default=None, max_length=2000)
