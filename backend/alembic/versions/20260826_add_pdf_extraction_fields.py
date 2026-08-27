"""add pdf extraction fields

Revision ID: 20260826_pdf_extraction
Revises: 20260826_conflict_action
Create Date: 2026-08-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260826_pdf_extraction"
down_revision = "20260826_conflict_action"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tender_documents",
        sa.Column("processing_status", sa.String(length=64), nullable=True, server_default="PENDING"),
    )
    op.add_column(
        "tender_documents",
        sa.Column("page_count", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "tender_documents",
        sa.Column("text_extracted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE tender_documents SET processing_status = 'PENDING' WHERE processing_status IS NULL")
    op.execute("UPDATE tender_documents SET page_count = 0 WHERE page_count IS NULL")
    op.alter_column("tender_documents", "processing_status", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("tender_documents", "page_count", existing_type=sa.Integer(), nullable=False)

    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="EXTRACTED"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_pages_document_id", table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_column("tender_documents", "text_extracted_at")
    op.drop_column("tender_documents", "page_count")
    op.drop_column("tender_documents", "processing_status")
