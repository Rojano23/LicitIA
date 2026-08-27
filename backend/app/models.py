from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
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

    tender: Mapped[Tender] = relationship(back_populates="documents")
