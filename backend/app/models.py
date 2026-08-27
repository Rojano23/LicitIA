from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenderStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


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
