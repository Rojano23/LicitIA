"""add document classification models

Revision ID: 20260827_document_classification
Revises: 20260827_normalized_content
Create Date: 2026-08-27 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_document_classification"
down_revision = "20260827_normalized_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_classifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("suggested_type", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("suggested_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("classification_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("classifier_method", sa.String(length=64), nullable=False, server_default="RULE_BASED_GENERIC"),
        sa.Column("classifier_version", sa.String(length=32), nullable=False, server_default="mvp-02.4"),
        sa.Column("input_fingerprint_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("is_composite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("human_type", sa.String(length=64), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_document_classification_document"),
    )
    op.create_index("ix_document_classification_document_id", "document_classifications", ["document_id"], unique=False)

    op.create_table(
        "document_classification_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("classification_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=True),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=True),
        sa.Column("document_chunk_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="CONTENT"),
        sa.Column("signal", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("weight_or_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["classification_id"], ["document_classifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_classification_evidence_classification_id", "document_classification_evidence", ["classification_id"], unique=False)
    op.create_index("ix_document_classification_evidence_document_page_id", "document_classification_evidence", ["document_page_id"], unique=False)
    op.create_index("ix_document_classification_evidence_normalized_content_id", "document_classification_evidence", ["normalized_content_id"], unique=False)
    op.create_index("ix_document_classification_evidence_document_chunk_id", "document_classification_evidence", ["document_chunk_id"], unique=False)

    op.create_table(
        "document_classification_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("classification_id", sa.String(length=36), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["classification_id"], ["document_classifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classification_id", "tag", name="uq_document_classification_tag"),
    )
    op.create_index("ix_document_classification_tags_classification_id", "document_classification_tags", ["classification_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_classification_tags_classification_id", table_name="document_classification_tags")
    op.drop_table("document_classification_tags")
    op.drop_index("ix_document_classification_evidence_document_chunk_id", table_name="document_classification_evidence")
    op.drop_index("ix_document_classification_evidence_normalized_content_id", table_name="document_classification_evidence")
    op.drop_index("ix_document_classification_evidence_document_page_id", table_name="document_classification_evidence")
    op.drop_index("ix_document_classification_evidence_classification_id", table_name="document_classification_evidence")
    op.drop_table("document_classification_evidence")
    op.drop_index("ix_document_classification_document_id", table_name="document_classifications")
    op.drop_table("document_classifications")
