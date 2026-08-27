"""add OCR provider results

Revision ID: 20260827_page_ocr_results
Revises: 20260827_page_ex_metadata
Create Date: 2026-08-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260827_page_ocr_results"
down_revision = "20260827_page_ex_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_ocr_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("language", sa.String(length=64), nullable=False, server_default="es+en"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OCR_TEXT_EXTRACTED"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_page_id", "engine", name="uq_page_ocr_document_page_engine"),
    )
    op.create_index("ix_page_ocr_results_document_page_id", "page_ocr_results", ["document_page_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_page_ocr_results_document_page_id", table_name="page_ocr_results")
    op.drop_table("page_ocr_results")
