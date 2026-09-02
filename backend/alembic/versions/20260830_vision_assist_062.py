"""add document vision assist tables

Revision ID: 20260830_vision_assist_062
Revises: 20260830_tender_items_061
Create Date: 2026-08-30 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260830_vision_assist_062"
down_revision: Union[str, Sequence[str], None] = "20260830_tender_items_061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_vision_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "model_name",
            "prompt_version",
            "input_fingerprint_sha256",
            name="uq_document_vision_analyses_input_fingerprint",
        ),
    )
    op.create_index("ix_document_vision_analyses_tender_id", "document_vision_analyses", ["tender_id"], unique=False)
    op.create_index("ix_document_vision_analyses_document_id", "document_vision_analyses", ["document_id"], unique=False)
    op.create_index(
        "ix_document_vision_analyses_input_fingerprint_sha256",
        "document_vision_analyses",
        ["input_fingerprint_sha256"],
        unique=False,
    )

    op.create_table(
        "document_vision_page_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_response_text", sa.Text(), nullable=True),
        sa.Column("structured_json", sa.JSON(), nullable=True),
        sa.Column("extracted_markdown", sa.Text(), nullable=True),
        sa.Column("extracted_plain_text", sa.Text(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["document_vision_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "document_page_id",
            "image_sha256",
            name="uq_document_vision_page_result_analysis_page_image",
        ),
    )
    op.create_index("ix_document_vision_page_results_analysis_id", "document_vision_page_results", ["analysis_id"], unique=False)
    op.create_index(
        "ix_document_vision_page_results_document_page_id",
        "document_vision_page_results",
        ["document_page_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_vision_page_results_document_page_id", table_name="document_vision_page_results")
    op.drop_index("ix_document_vision_page_results_analysis_id", table_name="document_vision_page_results")
    op.drop_table("document_vision_page_results")

    op.drop_index("ix_document_vision_analyses_input_fingerprint_sha256", table_name="document_vision_analyses")
    op.drop_index("ix_document_vision_analyses_document_id", table_name="document_vision_analyses")
    op.drop_index("ix_document_vision_analyses_tender_id", table_name="document_vision_analyses")
    op.drop_table("document_vision_analyses")
