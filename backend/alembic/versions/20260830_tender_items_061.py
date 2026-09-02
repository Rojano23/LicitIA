"""add tender items table

Revision ID: 20260830_tender_items_061
Revises: 20260829_cmp_review_055
Create Date: 2026-08-30 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260830_tender_items_061"
down_revision: Union[str, Sequence[str], None] = "20260829_cmp_review_055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("document_page_id", sa.String(length=36), nullable=True),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=True),
        sa.Column("item_number", sa.String(length=64), nullable=True),
        sa.Column("parent_item_number", sa.String(length=64), nullable=True),
        sa.Column("raw_description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("detection_origin", sa.String(length=32), nullable=False),
        sa.Column("detector_version", sa.String(length=32), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id",
            "source_document_id",
            "semantic_fingerprint",
            name="uq_tender_items_doc_fingerprint",
        ),
    )
    op.create_index("ix_tender_items_tender_id", "tender_items", ["tender_id"], unique=False)
    op.create_index("ix_tender_items_source_document_id", "tender_items", ["source_document_id"], unique=False)
    op.create_index("ix_tender_items_item_number", "tender_items", ["item_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_items_item_number", table_name="tender_items")
    op.drop_index("ix_tender_items_source_document_id", table_name="tender_items")
    op.drop_index("ix_tender_items_tender_id", table_name="tender_items")
    op.drop_table("tender_items")
