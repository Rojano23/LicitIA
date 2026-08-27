"""create tender documents

Revision ID: 20260826_create_tender_documents
Revises: 20260826_create_tenders
Create Date: 2026-08-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260826_create_tender_documents"
down_revision = "20260826_create_tenders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("source_relative_path", sa.String(length=512), nullable=True),
        sa.Column("stored_relative_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "sha256", name="uq_tender_document_sha256"),
    )
    op.create_index("ix_tender_documents_tender_id", "tender_documents", ["tender_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_documents_tender_id", table_name="tender_documents")
    op.drop_table("tender_documents")
