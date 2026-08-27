"""add normalized content and chunk tables

Revision ID: 20260827_normalized_content
Revises: 20260827_ocr_regions
Create Date: 2026-08-27 12:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260827_normalized_content"
down_revision = "20260827_ocr_regions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_content",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("page_ocr_result_id", sa.String(length=36), nullable=True),
        sa.Column("region_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="NATIVE_PDF"),
        sa.Column("source_scope", sa.String(length=32), nullable=False, server_default="NATIVE_PAGE"),
        sa.Column("engine", sa.String(length=32), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_ocr_result_id"], ["page_ocr_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_id"], ["document_page_regions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_page_id",
            "page_ocr_result_id",
            "region_id",
            "source_type",
            "source_scope",
            "engine",
            name="uq_normalized_content_source",
        ),
    )
    op.create_index("ix_normalized_content_document_page_id", "normalized_content", ["document_page_id"], unique=False)
    op.create_index("ix_normalized_content_page_ocr_result_id", "normalized_content", ["page_ocr_result_id"], unique=False)
    op.create_index("ix_normalized_content_region_id", "normalized_content", ["region_id"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("char_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_content_id", "chunk_index", name="uq_document_chunks_normalized_content_chunk"),
    )
    op.create_index("ix_document_chunks_normalized_content_id", "document_chunks", ["normalized_content_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_chunks_normalized_content_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_normalized_content_region_id", table_name="normalized_content")
    op.drop_index("ix_normalized_content_page_ocr_result_id", table_name="normalized_content")
    op.drop_index("ix_normalized_content_document_page_id", table_name="normalized_content")
    op.drop_table("normalized_content")
