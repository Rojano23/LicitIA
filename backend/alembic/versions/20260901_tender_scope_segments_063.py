"""add tender scope segments table

Revision ID: 20260901_scope_segments_063
Revises: 20260830_vision_assist_062
Create Date: 2026-09-01 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260901_scope_segments_063"
down_revision: Union[str, Sequence[str], None] = "20260830_vision_assist_062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_scope_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("tender_item_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_item_key", sa.String(length=64), nullable=True),
        sa.Column("candidate_item_raw_label", sa.String(length=255), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("scope_domain", sa.String(length=32), nullable=True),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("link_reason", sa.String(length=32), nullable=False),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("source_analysis_id", sa.String(length=36), nullable=True),
        sa.Column("source_page_result_id", sa.String(length=36), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_analysis_id"], ["document_vision_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_page_result_id"], ["document_vision_page_results.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_item_id"], ["tender_items.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "tender_item_id IS NOT NULL OR candidate_item_key IS NOT NULL",
            name="ck_tender_scope_segments_has_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id",
            "source_document_id",
            "semantic_fingerprint",
            name="uq_tender_scope_segments_doc_fingerprint",
        ),
    )
    op.create_index("ix_tender_scope_segments_tender_id", "tender_scope_segments", ["tender_id"], unique=False)
    op.create_index("ix_tender_scope_segments_source_document_id", "tender_scope_segments", ["source_document_id"], unique=False)
    op.create_index("ix_tender_scope_segments_document_page_id", "tender_scope_segments", ["document_page_id"], unique=False)
    op.create_index("ix_tender_scope_segments_tender_item_id", "tender_scope_segments", ["tender_item_id"], unique=False)
    op.create_index("ix_tender_scope_segments_candidate_item_key", "tender_scope_segments", ["candidate_item_key"], unique=False)
    op.create_index("ix_tender_scope_segments_review_required", "tender_scope_segments", ["review_required"], unique=False)
    op.create_index("ix_tender_scope_segments_scope_domain", "tender_scope_segments", ["scope_domain"], unique=False)
    op.create_index(
        "ix_tender_scope_segments_page_sequence",
        "tender_scope_segments",
        ["source_document_id", "page_number", "sequence_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tender_scope_segments_page_sequence", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_scope_domain", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_review_required", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_candidate_item_key", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_tender_item_id", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_document_page_id", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_source_document_id", table_name="tender_scope_segments")
    op.drop_index("ix_tender_scope_segments_tender_id", table_name="tender_scope_segments")
    op.drop_table("tender_scope_segments")