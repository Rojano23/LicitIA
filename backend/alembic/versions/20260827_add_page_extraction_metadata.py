"""add page extraction metadata

Revision ID: 20260827_page_extraction_metadata
Revises: 20260826_pdf_extraction
Create Date: 2026-08-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260827_page_ex_metadata"
down_revision = "20260826_pdf_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_pages",
        sa.Column("char_count", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "document_pages",
        sa.Column("extraction_method", sa.String(length=32), nullable=True, server_default="NATIVE_PDF"),
    )
    op.execute("UPDATE document_pages SET char_count = 0 WHERE char_count IS NULL")
    op.execute("UPDATE document_pages SET extraction_method = 'NATIVE_PDF' WHERE extraction_method IS NULL")
    op.alter_column("document_pages", "char_count", existing_type=sa.Integer(), nullable=False)
    op.alter_column("document_pages", "extraction_method", existing_type=sa.String(length=32), nullable=False)


def downgrade() -> None:
    op.drop_column("document_pages", "extraction_method")
    op.drop_column("document_pages", "char_count")
