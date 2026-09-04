"""add tender scope details table

Revision ID: 20260903_scope_det_065
Revises: 20260901_page_struct_res_064
Create Date: 2026-09-04 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260903_scope_det_065"
down_revision: Union[str, Sequence[str], None] = "20260901_page_struct_res_064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_scope_details",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("scope_segment_id", sa.String(length=36), nullable=True),
        sa.Column("tender_item_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_item_key", sa.String(length=64), nullable=True),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("detail_type", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=True),
        sa.Column("applicability", sa.String(length=32), nullable=False),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("source_artifact_key", sa.String(length=255), nullable=False),
        sa.Column("source_contract_version", sa.String(length=64), nullable=True),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("source_analysis_id", sa.String(length=36), nullable=True),
        sa.Column("source_page_result_id", sa.String(length=36), nullable=True),
        sa.Column("quantity_raw", sa.String(length=128), nullable=True),
        sa.Column("unit_raw", sa.String(length=128), nullable=True),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_segment_id"], ["tender_scope_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_analysis_id"], ["document_vision_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_page_result_id"], ["document_vision_page_results.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_item_id"], ["tender_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "source_artifact_key",
            "semantic_fingerprint",
            name="uq_tender_scope_details_artifact_fingerprint",
        ),
    )
    op.create_index("ix_tender_scope_details_tender_id", "tender_scope_details", ["tender_id"], unique=False)
    op.create_index("ix_tender_scope_details_tender_item_id", "tender_scope_details", ["tender_item_id"], unique=False)
    op.create_index("ix_tender_scope_details_source_document_id", "tender_scope_details", ["source_document_id"], unique=False)
    op.create_index("ix_tender_scope_details_document_page_id", "tender_scope_details", ["document_page_id"], unique=False)
    op.create_index("ix_tender_scope_details_scope_segment_id", "tender_scope_details", ["scope_segment_id"], unique=False)
    op.create_index("ix_tender_scope_details_candidate_item_key", "tender_scope_details", ["candidate_item_key"], unique=False)
    op.create_index("ix_tender_scope_details_domain", "tender_scope_details", ["domain"], unique=False)
    op.create_index("ix_tender_scope_details_source_artifact_key", "tender_scope_details", ["source_artifact_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_scope_details_source_artifact_key", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_domain", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_candidate_item_key", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_scope_segment_id", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_document_page_id", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_source_document_id", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_tender_item_id", table_name="tender_scope_details")
    op.drop_index("ix_tender_scope_details_tender_id", table_name="tender_scope_details")
    op.drop_table("tender_scope_details")
