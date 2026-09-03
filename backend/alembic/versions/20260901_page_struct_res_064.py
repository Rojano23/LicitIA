"""add persisted document page structure resolution status

Revision ID: 20260901_page_struct_res_064
Revises: 20260901_scope_segments_063
Create Date: 2026-09-01 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260901_page_struct_res_064"
down_revision: Union[str, Sequence[str], None] = "20260901_scope_segments_063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_page_structure_resolutions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("selected_source_method", sa.String(length=32), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolver_version", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_page_id", name="uq_doc_page_structure_resolution_page"),
    )
    op.create_index(
        "ix_doc_page_structure_resolution_document_id",
        "document_page_structure_resolutions",
        ["source_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_doc_page_structure_resolution_status",
        "document_page_structure_resolutions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_doc_page_structure_resolution_review_required",
        "document_page_structure_resolutions",
        ["review_required"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_doc_page_structure_resolution_review_required", table_name="document_page_structure_resolutions")
    op.drop_index("ix_doc_page_structure_resolution_status", table_name="document_page_structure_resolutions")
    op.drop_index("ix_doc_page_structure_resolution_document_id", table_name="document_page_structure_resolutions")
    op.drop_table("document_page_structure_resolutions")
