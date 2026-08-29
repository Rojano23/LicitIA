from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenderStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CompanyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CompanyDocumentStatus(str, Enum):
    IMPORTED = "IMPORTED"
    DUPLICATE = "DUPLICATE"
    NAME_CONFLICT = "NAME_CONFLICT"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


class CompanyEvidenceType(str, Enum):
    CORPORATE_EXISTENCE = "CORPORATE_EXISTENCE"
    LEGAL_AUTHORITY = "LEGAL_AUTHORITY"
    TAX_REGISTRATION = "TAX_REGISTRATION"
    TAX_COMPLIANCE = "TAX_COMPLIANCE"
    SOCIAL_SECURITY_COMPLIANCE = "SOCIAL_SECURITY_COMPLIANCE"
    REGISTRATION = "REGISTRATION"
    CERTIFICATION = "CERTIFICATION"
    PERSONNEL_QUALIFICATION = "PERSONNEL_QUALIFICATION"
    EXPERIENCE = "EXPERIENCE"
    SAFETY_CREDENTIAL = "SAFETY_CREDENTIAL"
    GUARANTEE = "GUARANTEE"
    COMMERCIAL_DOCUMENT = "COMMERCIAL_DOCUMENT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class CompanyEvidenceSubjectKind(str, Enum):
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    OTHER = "OTHER"


class CompanyEvidenceAnalysisStatus(str, Enum):
    DETERMINED = "DETERMINED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CompanyEvidenceOrigin(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    HUMAN = "HUMAN"


class CompanyEvidenceReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"


class TenderDocumentStatus(str, Enum):
    IMPORTED = "IMPORTED"
    DUPLICATE = "DUPLICATE"
    NAME_CONFLICT = "NAME_CONFLICT"
    FAILED = "FAILED"


class TenderDocumentProcessingStatus(str, Enum):
    PENDING = "PENDING"
    TEXT_EXTRACTION_COMPLETE = "TEXT_EXTRACTION_COMPLETE"
    TEXT_EXTRACTION_PARTIAL = "TEXT_EXTRACTION_PARTIAL"
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    NO_NATIVE_TEXT = "NO_NATIVE_TEXT"


class DocumentPageStatus(str, Enum):
    TEXT_EXTRACTED = "TEXT_EXTRACTED"
    NO_TEXT = "NO_TEXT"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CompanyStatus.ACTIVE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    documents: Mapped[list["CompanyDocument"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    evidence: Mapped[list["CompanyEvidence"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    evidence_reviews: Mapped[list["CompanyEvidenceReview"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class CompanyDocument(Base):
    __tablename__ = "company_documents"

    __table_args__ = (
        UniqueConstraint("company_id", "sha256", name="uq_company_document_sha256"),
        Index("ix_company_documents_company_id", "company_id"),
        Index("ix_company_documents_revision_of_document_id", "revision_of_document_id"),
        Index("ix_company_documents_status", "status"),
        Index("ix_company_documents_conflict_resolution_action", "conflict_resolution_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_relative_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stored_relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=CompanyDocumentStatus.IMPORTED.value, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision_of_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    conflict_resolution_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="documents")
    evidence: Mapped[list["CompanyEvidence"]] = relationship(back_populates="source_document", cascade="all, delete-orphan")


class CompanyEvidence(Base):
    __tablename__ = "company_evidence"

    __table_args__ = (
        Index("ix_company_evidence_company_id", "company_id"),
        Index("ix_company_evidence_company_document_id", "company_document_id"),
        Index("ix_company_evidence_evidence_type", "evidence_type"),
        Index("ix_company_evidence_subject_kind", "subject_kind"),
        Index("ix_company_evidence_analysis_status", "analysis_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("company_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_statement: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_locator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="evidence")
    source_document: Mapped[CompanyDocument] = relationship(back_populates="evidence")
    review: Mapped["CompanyEvidenceReview | None"] = relationship(
        back_populates="company_evidence",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CompanyEvidenceReview(Base):
    __tablename__ = "company_evidence_reviews"

    __table_args__ = (
        UniqueConstraint("company_evidence_id", name="uq_company_evidence_review_evidence_id"),
        Index("ix_company_evidence_reviews_company_id", "company_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_evidence_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("company_evidence.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default=CompanyEvidenceReviewStatus.PENDING.value)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="evidence_reviews")
    company_evidence: Mapped[CompanyEvidence] = relationship(back_populates="review")


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=TenderStatus.DRAFT.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    documents: Mapped[list["TenderDocument"]] = relationship(back_populates="tender")
    events: Mapped[list["TenderEvent"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    changes: Mapped[list["TenderChange"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    requirement_candidates: Mapped[list["RequirementCandidate"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    requirement_version_links: Mapped[list["RequirementVersionLink"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    requirement_reviews: Mapped[list["RequirementReview"]] = relationship(back_populates="tender", cascade="all, delete-orphan")


class TenderDocument(Base):
    __tablename__ = "tender_documents"

    __table_args__ = (
        UniqueConstraint("tender_id", "sha256", name="uq_tender_document_sha256"),
        Index("ix_tender_documents_tender_id", "tender_id"),
        Index("ix_tender_documents_revision_of_document_id", "revision_of_document_id"),
        Index("ix_tender_documents_conflict_resolution_action", "conflict_resolution_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_relative_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stored_relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=TenderDocumentStatus.IMPORTED.value, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(64),
        default=TenderDocumentProcessingStatus.PENDING.value,
        nullable=False,
    )
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision_of_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    conflict_resolution_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    text_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tender: Mapped[Tender] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    classifications: Mapped[list["DocumentClassification"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    reference_analysis: Mapped["DocumentReferenceAnalysis | None"] = relationship(back_populates="document", cascade="all, delete-orphan")
    outbound_references: Mapped[list["DocumentReference"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentReference.source_document_id",
    )
    resolved_references: Mapped[list["DocumentReference"]] = relationship(
        back_populates="resolved_target_document",
        foreign_keys="DocumentReference.resolved_target_document_id",
    )
    human_resolved_references: Mapped[list["DocumentReference"]] = relationship(
        back_populates="human_target_document",
        foreign_keys="DocumentReference.human_target_document_id",
    )
    outbound_relationships: Mapped[list["DocumentRelationship"]] = relationship(
        back_populates="source_document",
        foreign_keys="DocumentRelationship.source_document_id",
        cascade="all, delete-orphan",
    )
    inbound_relationships: Mapped[list["DocumentRelationship"]] = relationship(
        back_populates="target_document",
        foreign_keys="DocumentRelationship.target_document_id",
    )
    sourced_events: Mapped[list["TenderEvent"]] = relationship(
        back_populates="source_document",
        foreign_keys="TenderEvent.source_document_id",
    )
    event_evidence: Mapped[list["TenderEventEvidence"]] = relationship(
        back_populates="source_document",
        foreign_keys="TenderEventEvidence.source_document_id",
    )
    sourced_changes: Mapped[list["TenderChange"]] = relationship(
        back_populates="source_document",
        foreign_keys="TenderChange.source_document_id",
    )
    targeted_changes: Mapped[list["TenderChange"]] = relationship(
        back_populates="target_document",
        foreign_keys="TenderChange.target_document_id",
    )
    change_evidence: Mapped[list["TenderChangeEvidence"]] = relationship(
        back_populates="source_document",
        foreign_keys="TenderChangeEvidence.source_document_id",
    )
    requirement_candidates: Mapped[list["RequirementCandidate"]] = relationship(
        back_populates="source_document",
        foreign_keys="RequirementCandidate.source_document_id",
        cascade="all, delete-orphan",
    )
    requirement_candidate_evidence: Mapped[list["RequirementCandidateEvidence"]] = relationship(
        back_populates="source_document",
        foreign_keys="RequirementCandidateEvidence.source_document_id",
        cascade="all, delete-orphan",
    )


class DocumentPageRegion(Base):
    __tablename__ = "document_page_regions"

    __table_args__ = (
        Index("ix_document_page_regions_document_page_id", "document_page_id"),
        UniqueConstraint("document_page_id", "region_index", name="uq_document_page_regions_document_page_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_page_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    region_index: Mapped[int] = mapped_column(Integer, nullable=False)
    region_type: Mapped[str] = mapped_column(String(32), nullable=False, default="IMAGE")
    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    area_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document_page: Mapped["DocumentPage"] = relationship(back_populates="regions")
    ocr_results: Mapped[list["PageOcrResult"]] = relationship(back_populates="region", cascade="all, delete-orphan")
    normalized_content: Mapped[list[NormalizedContent]] = relationship(back_populates="region", cascade="all, delete-orphan")


class NormalizedContent(Base):
    __tablename__ = "normalized_content"

    __table_args__ = (
        Index("ix_normalized_content_document_page_id", "document_page_id"),
        Index("ix_normalized_content_page_ocr_result_id", "page_ocr_result_id"),
        Index("ix_normalized_content_region_id", "region_id"),
        UniqueConstraint(
            "document_page_id",
            "page_ocr_result_id",
            "region_id",
            "source_type",
            "source_scope",
            "engine",
            name="uq_normalized_content_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_page_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_ocr_result_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("page_ocr_results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    region_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_page_regions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="NATIVE_PDF")
    source_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="NATIVE_PAGE")
    engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document_page: Mapped["DocumentPage"] = relationship(back_populates="normalized_content")
    page_ocr_result: Mapped["PageOcrResult | None"] = relationship(back_populates="normalized_content")
    region: Mapped[DocumentPageRegion | None] = relationship(back_populates="normalized_content")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="normalized_content", cascade="all, delete-orphan")
    classification_evidence: Mapped[list["DocumentClassificationEvidence"]] = relationship(back_populates="normalized_content", cascade="all, delete-orphan")
    requirement_candidates: Mapped[list["RequirementCandidate"]] = relationship(back_populates="normalized_content")
    requirement_candidate_evidence: Mapped[list["RequirementCandidateEvidence"]] = relationship(back_populates="normalized_content")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    __table_args__ = (
        Index("ix_document_pages_document_id", "document_id"),
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False, default="NATIVE_PDF")
    status: Mapped[str] = mapped_column(String(32), default=DocumentPageStatus.TEXT_EXTRACTED.value, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped[TenderDocument] = relationship(back_populates="pages")
    regions: Mapped[list[DocumentPageRegion]] = relationship(back_populates="document_page", cascade="all, delete-orphan")
    ocr_results: Mapped[list["PageOcrResult"]] = relationship(back_populates="document_page", cascade="all, delete-orphan")
    normalized_content: Mapped[list[NormalizedContent]] = relationship(back_populates="document_page", cascade="all, delete-orphan")
    classification_evidence: Mapped[list["DocumentClassificationEvidence"]] = relationship(back_populates="document_page", cascade="all, delete-orphan")
    requirement_candidates: Mapped[list["RequirementCandidate"]] = relationship(back_populates="document_page")
    requirement_candidate_evidence: Mapped[list["RequirementCandidateEvidence"]] = relationship(back_populates="document_page")

    @property
    def content_profile(self) -> str:
        has_native_text = bool((self.text or "").strip())
        has_eligible_image = any(region.region_type == "IMAGE" and region.area_ratio >= 0.03 for region in self.regions)
        if has_native_text and has_eligible_image:
            return "MIXED_CONTENT"
        if has_native_text:
            return "TEXT_ONLY"
        if has_eligible_image:
            return "IMAGE_ONLY"
        return "TEXT_ONLY"


class PageOcrResult(Base):
    __tablename__ = "page_ocr_results"

    __table_args__ = (
        Index("ix_page_ocr_results_document_page_id", "document_page_id"),
        Index("ix_page_ocr_results_region_id", "region_id"),
        UniqueConstraint("document_page_id", "engine", "scope", "region_id", name="uq_page_ocr_document_page_engine_scope_region"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_page_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    language: Mapped[str] = mapped_column(String(64), nullable=False, default="es+en")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OCR_TEXT_EXTRACTED")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="FULL_PAGE")
    region_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_page_regions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document_page: Mapped[DocumentPage] = relationship(back_populates="ocr_results")
    region: Mapped[DocumentPageRegion | None] = relationship(back_populates="ocr_results")
    normalized_content: Mapped[list[NormalizedContent]] = relationship(back_populates="page_ocr_result", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        Index("ix_document_chunks_normalized_content_id", "normalized_content_id"),
        UniqueConstraint("normalized_content_id", "chunk_index", name="uq_document_chunks_normalized_content_chunk"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    normalized_content_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("normalized_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    normalized_content: Mapped[NormalizedContent] = relationship(back_populates="chunks")
    classification_evidence: Mapped[list["DocumentClassificationEvidence"]] = relationship(back_populates="document_chunk", cascade="all, delete-orphan")


class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_classification_document"),
        Index("ix_document_classification_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    suggested_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    classifier_method: Mapped[str] = mapped_column(String(64), nullable=False, default="RULE_BASED_GENERIC")
    classifier_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-02.4")
    input_fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_composite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped[TenderDocument] = relationship(back_populates="classifications")
    evidence: Mapped[list["DocumentClassificationEvidence"]] = relationship(back_populates="classification", cascade="all, delete-orphan")
    candidates: Mapped[list["DocumentClassificationCandidate"]] = relationship(back_populates="classification", cascade="all, delete-orphan")
    tags: Mapped[list["DocumentClassificationTag"]] = relationship(back_populates="classification", cascade="all, delete-orphan")


class DocumentClassificationEvidence(Base):
    __tablename__ = "document_classification_evidence"

    __table_args__ = (
        Index("ix_document_classification_evidence_classification_id", "classification_id"),
        Index("ix_document_classification_evidence_document_page_id", "document_page_id"),
        Index("ix_document_classification_evidence_normalized_content_id", "normalized_content_id"),
        Index("ix_document_classification_evidence_document_chunk_id", "document_chunk_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    classification_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_classifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_page_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    normalized_content_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("normalized_content.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_chunk_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="CONTENT")
    signal: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight_or_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classification: Mapped[DocumentClassification] = relationship(back_populates="evidence")
    document_page: Mapped[DocumentPage | None] = relationship(back_populates="classification_evidence")
    normalized_content: Mapped[NormalizedContent | None] = relationship(back_populates="classification_evidence")
    document_chunk: Mapped[DocumentChunk | None] = relationship(back_populates="classification_evidence")


class DocumentClassificationTag(Base):
    __tablename__ = "document_classification_tags"

    __table_args__ = (
        UniqueConstraint("classification_id", "tag", name="uq_document_classification_tag"),
        Index("ix_document_classification_tags_classification_id", "classification_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    classification_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_classifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classification: Mapped[DocumentClassification] = relationship(back_populates="tags")


class DocumentClassificationCandidate(Base):
    __tablename__ = "document_classification_candidates"

    __table_args__ = (
        UniqueConstraint("classification_id", "candidate_type", name="uq_document_classification_candidate"),
        Index("ix_document_classification_candidates_classification_id", "classification_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    classification_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_classifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    classification: Mapped[DocumentClassification] = relationship(back_populates="candidates")


class DocumentReferenceAnalysis(Base):
    __tablename__ = "document_reference_analyses"

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_reference_analysis_document"),
        Index("ix_document_reference_analyses_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-02.5.1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_READY")
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped[TenderDocument] = relationship(back_populates="reference_analysis")
    references: Mapped[list["DocumentReference"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class DocumentReference(Base):
    __tablename__ = "document_references"

    __table_args__ = (
        UniqueConstraint("source_document_id", "reference_identity_key", name="uq_document_reference_identity"),
        Index("ix_document_references_source_document_id", "source_document_id"),
        Index("ix_document_references_resolution_status", "resolution_status"),
        Index("ix_document_references_normalized_reference_key", "normalized_reference_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    analysis_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_reference_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_page_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    normalized_content_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("normalized_content.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_chunk_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reference_identity_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    raw_reference_text: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    normalized_reference_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    reference_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    relationship_hint: Mapped[str] = mapped_column(String(32), nullable=False, default="REFERENCES")
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNRESOLVED")
    resolved_target_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    auto_candidate_document_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_target_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    human_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_region_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_page_regions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-02.5")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    analysis: Mapped[DocumentReferenceAnalysis | None] = relationship(back_populates="references")
    source_document: Mapped[TenderDocument] = relationship(back_populates="outbound_references", foreign_keys=[source_document_id])
    resolved_target_document: Mapped[TenderDocument | None] = relationship(back_populates="resolved_references", foreign_keys=[resolved_target_document_id])
    human_target_document: Mapped[TenderDocument | None] = relationship(back_populates="human_resolved_references", foreign_keys=[human_target_document_id])
    document_page: Mapped[DocumentPage | None] = relationship(foreign_keys=[document_page_id])
    normalized_content: Mapped[NormalizedContent | None] = relationship(foreign_keys=[normalized_content_id])
    document_chunk: Mapped[DocumentChunk | None] = relationship(foreign_keys=[document_chunk_id])


class DocumentRelationship(Base):
    __tablename__ = "document_relationships"

    __table_args__ = (
        UniqueConstraint("source_document_id", "target_document_id", "relationship_type", name="uq_document_relationship_edge"),
        Index("ix_document_relationships_tender_id", "tender_id"),
        Index("ix_document_relationships_source_document_id", "source_document_id"),
        Index("ix_document_relationships_target_document_id", "target_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, default="REFERENCES")
    relationship_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="REFERENCE_ENGINE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    source_document: Mapped[TenderDocument] = relationship(back_populates="outbound_relationships", foreign_keys=[source_document_id])
    target_document: Mapped[TenderDocument] = relationship(back_populates="inbound_relationships", foreign_keys=[target_document_id])


class TenderEvent(Base):
    __tablename__ = "tender_events"

    __table_args__ = (
        UniqueConstraint("tender_id", "semantic_key", name="uq_tender_event_semantic_key"),
        Index("ix_tender_events_tender_id", "tender_id"),
        Index("ix_tender_events_review_status", "review_status"),
        Index("ix_tender_events_event_date", "event_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    date_precision: Mapped[str] = mapped_column(String(16), nullable=False, default="DAY")
    timezone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_date_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    detection_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-03.2")
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    human_event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    human_event_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    human_date_precision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    human_timezone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="events")
    source_document: Mapped[TenderDocument | None] = relationship(back_populates="sourced_events", foreign_keys=[source_document_id])
    evidence: Mapped[list["TenderEventEvidence"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class TenderEventEvidence(Base):
    __tablename__ = "tender_event_evidence"

    __table_args__ = (
        UniqueConstraint("event_id", "source_document_id", "source_page", "excerpt_sha256", name="uq_tender_event_evidence_item"),
        Index("ix_tender_event_evidence_event_id", "event_id"),
        Index("ix_tender_event_evidence_source_document_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    event: Mapped[TenderEvent] = relationship(back_populates="evidence")
    source_document: Mapped[TenderDocument] = relationship(back_populates="event_evidence", foreign_keys=[source_document_id])


class TenderChange(Base):
    __tablename__ = "tender_changes"

    __table_args__ = (
        UniqueConstraint("tender_id", "semantic_key", name="uq_tender_change_semantic_key"),
        Index("ix_tender_changes_tender_id", "tender_id"),
        Index("ix_tender_changes_review_status", "review_status"),
        Index("ix_tender_changes_change_type", "change_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    target_reference_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_candidate_document_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_locator_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    detection_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-03.3")
    human_change_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_target_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    human_target_locator_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    human_before_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_after_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="changes")
    source_document: Mapped[TenderDocument] = relationship(back_populates="sourced_changes", foreign_keys=[source_document_id])
    target_document: Mapped[TenderDocument | None] = relationship(back_populates="targeted_changes", foreign_keys=[target_document_id])
    human_target_document: Mapped[TenderDocument | None] = relationship(foreign_keys=[human_target_document_id])
    evidence: Mapped[list["TenderChangeEvidence"]] = relationship(back_populates="change", cascade="all, delete-orphan")
    requirement_version_links: Mapped[list["RequirementVersionLink"]] = relationship(back_populates="change")


class TenderChangeEvidence(Base):
    __tablename__ = "tender_change_evidence"

    __table_args__ = (
        UniqueConstraint("change_id", "source_document_id", "source_page", "excerpt_sha256", name="uq_tender_change_evidence_item"),
        Index("ix_tender_change_evidence_change_id", "change_id"),
        Index("ix_tender_change_evidence_source_document_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    change: Mapped[TenderChange] = relationship(back_populates="evidence")
    source_document: Mapped[TenderDocument] = relationship(back_populates="change_evidence", foreign_keys=[source_document_id])


class TenderEvaluationModel(Base):
    __tablename__ = "tender_evaluation_models"

    __table_args__ = (
        UniqueConstraint("tender_id", name="uq_tender_evaluation_model_tender"),
        Index("ix_tender_evaluation_models_tender_id", "tender_id"),
        Index("ix_tender_evaluation_models_review_status", "review_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_method: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    human_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    human_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship()
    evidence: Mapped[list["TenderEvaluationModelEvidence"]] = relationship(back_populates="evaluation_model", cascade="all, delete-orphan")
    criteria: Mapped[list["EvaluationCriterion"]] = relationship(back_populates="evaluation_model", cascade="all, delete-orphan")


class TenderEvaluationModelEvidence(Base):
    __tablename__ = "tender_evaluation_model_evidence"

    __table_args__ = (
        UniqueConstraint(
            "evaluation_model_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_tender_evaluation_model_evidence_item",
        ),
        Index("ix_tender_evaluation_model_evidence_model_id", "evaluation_model_id"),
        Index("ix_tender_evaluation_model_evidence_source_document_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evaluation_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_evaluation_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    evidence_role: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    evaluation_model: Mapped[TenderEvaluationModel] = relationship(back_populates="evidence")
    source_document: Mapped[TenderDocument] = relationship(foreign_keys=[source_document_id])


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    __table_args__ = (
        UniqueConstraint("tender_id", "semantic_key", name="uq_evaluation_criteria_semantic_key"),
        Index("ix_evaluation_criteria_tender_id", "tender_id"),
        Index("ix_evaluation_criteria_evaluation_model_id", "evaluation_model_id"),
        Index("ix_evaluation_criteria_review_status", "review_status"),
        Index("ix_evaluation_criteria_type", "criterion_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_evaluation_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    criterion_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    threshold_operator: Mapped[str | None] = mapped_column(String(32), nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_exclusionary: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    detection_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.1")
    human_criterion_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    human_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    human_criterion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_weight_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_weight_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_threshold_operator: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_threshold_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    human_is_exclusionary: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    human_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    evaluation_model: Mapped[TenderEvaluationModel] = relationship(back_populates="criteria")
    source_document: Mapped[TenderDocument] = relationship(foreign_keys=[source_document_id])
    evidence: Mapped[list["EvaluationCriterionEvidence"]] = relationship(back_populates="criterion", cascade="all, delete-orphan")


class EvaluationCriterionEvidence(Base):
    __tablename__ = "evaluation_criterion_evidence"

    __table_args__ = (
        UniqueConstraint(
            "criterion_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_evaluation_criterion_evidence_item",
        ),
        Index("ix_evaluation_criterion_evidence_criterion_id", "criterion_id"),
        Index("ix_evaluation_criterion_evidence_source_document_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    criterion_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    evidence_role: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    criterion: Mapped[EvaluationCriterion] = relationship(back_populates="evidence")
    source_document: Mapped[TenderDocument] = relationship(foreign_keys=[source_document_id])


class RequirementCandidate(Base):
    __tablename__ = "requirement_candidates"

    __table_args__ = (
        UniqueConstraint("tender_id", "semantic_key", name="uq_requirement_candidates_semantic_key"),
        Index("ix_requirement_candidates_tender_id", "tender_id"),
        Index("ix_requirement_candidates_source_document_id", "source_document_id"),
        Index("ix_requirement_candidates_review_status", "review_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modality_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    document_page_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    normalized_content_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("normalized_content.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detection_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")
    detector_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.2")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="requirement_candidates")
    source_document: Mapped[TenderDocument] = relationship(back_populates="requirement_candidates", foreign_keys=[source_document_id])
    document_page: Mapped[DocumentPage | None] = relationship(back_populates="requirement_candidates", foreign_keys=[document_page_id])
    normalized_content: Mapped[NormalizedContent | None] = relationship(back_populates="requirement_candidates", foreign_keys=[normalized_content_id])
    evidence: Mapped[list["RequirementCandidateEvidence"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    requirement_links: Mapped[list["RequirementCandidateLink"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Requirement(Base):
    __tablename__ = "requirements"

    __table_args__ = (
        UniqueConstraint("tender_id", "canonical_key", name="uq_requirements_canonical_key"),
        Index("ix_requirements_tender_id", "tender_id"),
        Index("ix_requirements_category", "category"),
        Index("ix_requirements_status", "normalization_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    normalization_status: Mapped[str] = mapped_column(String(32), nullable=False, default="REVIEW_REQUIRED")
    normalizer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.3")
    normalization_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalization_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("requirement_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="requirements")
    primary_candidate: Mapped[RequirementCandidate | None] = relationship(foreign_keys=[primary_candidate_id])
    candidate_links: Mapped[list["RequirementCandidateLink"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")
    semantics: Mapped["RequirementSemantics | None"] = relationship(back_populates="requirement", cascade="all, delete-orphan", uselist=False)
    predecessor_links: Mapped[list["RequirementVersionLink"]] = relationship(
        back_populates="predecessor_requirement",
        foreign_keys="RequirementVersionLink.predecessor_requirement_id",
    )
    successor_links: Mapped[list["RequirementVersionLink"]] = relationship(
        back_populates="successor_requirement",
        foreign_keys="RequirementVersionLink.successor_requirement_id",
    )
    review: Mapped["RequirementReview | None"] = relationship(back_populates="requirement", uselist=False, cascade="all, delete-orphan")


class RequirementReview(Base):
    __tablename__ = "requirement_reviews"

    __table_args__ = (
        UniqueConstraint("requirement_id", name="uq_requirement_reviews_requirement_id"),
        Index("ix_requirement_reviews_tender_id", "tender_id"),
        Index("ix_requirement_reviews_requirement_id", "requirement_id"),
        Index("ix_requirement_reviews_review_status", "review_status"),
        Index("ix_requirement_reviews_reviewed_at", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="requirement_reviews")
    requirement: Mapped[Requirement] = relationship(back_populates="review")


class RequirementVersionLink(Base):
    __tablename__ = "requirement_version_links"

    __table_args__ = (
        UniqueConstraint(
            "tender_id",
            "change_id",
            "predecessor_requirement_id",
            "successor_requirement_id",
            "link_kind",
            name="uq_requirement_version_link_item",
        ),
        Index("ix_requirement_version_links_tender_id", "tender_id"),
        Index("ix_requirement_version_links_change_id", "change_id"),
        Index("ix_requirement_version_links_predecessor_id", "predecessor_requirement_id"),
        Index("ix_requirement_version_links_successor_id", "successor_requirement_id"),
        Index("ix_requirement_version_links_link_kind", "link_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predecessor_requirement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    successor_requirement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    link_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="SUPERSEDES")
    matching_basis: Mapped[str] = mapped_column(String(64), nullable=False, default="EXPLICIT_CHANGE_EVIDENCE")
    target_locator_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.5")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="requirement_version_links")
    change: Mapped[TenderChange] = relationship(back_populates="requirement_version_links")
    predecessor_requirement: Mapped[Requirement | None] = relationship(
        back_populates="predecessor_links",
        foreign_keys=[predecessor_requirement_id],
    )
    successor_requirement: Mapped[Requirement | None] = relationship(
        back_populates="successor_links",
        foreign_keys=[successor_requirement_id],
    )


class RequirementCandidateLink(Base):
    __tablename__ = "requirement_candidate_links"

    __table_args__ = (
        UniqueConstraint("requirement_id", "requirement_candidate_id", name="uq_requirement_candidate_link"),
        Index("ix_requirement_candidate_links_requirement_id", "requirement_id"),
        Index("ix_requirement_candidate_links_candidate_id", "requirement_candidate_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_primary_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    link_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    requirement: Mapped[Requirement] = relationship(back_populates="candidate_links")
    candidate: Mapped[RequirementCandidate] = relationship(back_populates="requirement_links")


class RequirementCandidateEvidence(Base):
    __tablename__ = "requirement_candidate_evidence"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_requirement_candidate_evidence_item",
        ),
        Index("ix_requirement_candidate_evidence_candidate_id", "candidate_id"),
        Index("ix_requirement_candidate_evidence_source_document_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    document_page_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    normalized_content_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("normalized_content.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    candidate: Mapped[RequirementCandidate] = relationship(back_populates="evidence")
    source_document: Mapped[TenderDocument] = relationship(back_populates="requirement_candidate_evidence", foreign_keys=[source_document_id])
    document_page: Mapped[DocumentPage | None] = relationship(back_populates="requirement_candidate_evidence", foreign_keys=[document_page_id])
    normalized_content: Mapped[NormalizedContent | None] = relationship(back_populates="requirement_candidate_evidence", foreign_keys=[normalized_content_id])


class RequirementSemantics(Base):
    __tablename__ = "requirement_semantics"

    __table_args__ = (
        UniqueConstraint("requirement_id", name="uq_requirement_semantics_requirement"),
        Index("ix_requirement_semantics_requirement_id", "requirement_id"),
        Index("ix_requirement_semantics_applicability", "applicability"),
        Index("ix_requirement_semantics_interpretation_status", "interpretation_status"),
        Index("ix_requirement_semantics_evidence_mode", "evidence_mode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    applicability: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    condition_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="REVIEW_REQUIRED")
    evidence_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="REVIEW_REQUIRED")
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.4")
    interpretation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    requirement: Mapped[Requirement] = relationship(back_populates="semantics")
    expected_evidence: Mapped[list["RequirementEvidenceExpectation"]] = relationship(
        back_populates="requirement_semantics",
        cascade="all, delete-orphan",
    )


class RequirementEvidenceExpectation(Base):
    __tablename__ = "requirement_evidence_expectations"

    __table_args__ = (
        UniqueConstraint(
            "requirement_semantics_id",
            "source_candidate_id",
            "evidence_type",
            "excerpt_sha256",
            name="uq_requirement_evidence_expectation_item",
        ),
        Index("ix_requirement_evidence_expectations_semantics_id", "requirement_semantics_id"),
        Index("ix_requirement_evidence_expectations_requirement_id", "requirement_id"),
        Index("ix_requirement_evidence_expectations_candidate_id", "source_candidate_id"),
        Index("ix_requirement_evidence_expectations_type", "evidence_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requirement_semantics_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_semantics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    evidence_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("requirement_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tender_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="mvp-04.4")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    requirement_semantics: Mapped[RequirementSemantics] = relationship(back_populates="expected_evidence")
    requirement: Mapped[Requirement] = relationship()
    source_candidate: Mapped[RequirementCandidate | None] = relationship(foreign_keys=[source_candidate_id])
    source_document: Mapped[TenderDocument | None] = relationship(foreign_keys=[source_document_id])
