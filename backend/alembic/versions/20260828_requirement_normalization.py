"""add requirement normalization tables

Revision ID: 20260828_req_norm_043
Revises: 20260828_req_extract_042
Create Date: 2026-08-28 23:58:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_req_norm_043"
down_revision = "20260828_req_extract_042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("canonical_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("normalization_status", sa.String(length=32), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("normalizer_version", sa.String(length=32), nullable=False, server_default="mvp-04.3"),
        sa.Column("normalization_confidence", sa.Float(), nullable=True),
        sa.Column("normalization_reason", sa.Text(), nullable=True),
        sa.Column("primary_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["primary_candidate_id"], ["requirement_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "canonical_key", name="uq_requirements_canonical_key"),
    )
    op.create_index("ix_requirements_tender_id", "requirements", ["tender_id"], unique=False)
    op.create_index("ix_requirements_category", "requirements", ["category"], unique=False)
    op.create_index("ix_requirements_status", "requirements", ["normalization_status"], unique=False)

    op.create_table(
        "requirement_candidate_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("is_primary_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("link_origin", sa.String(length=32), nullable=False, server_default="DETERMINISTIC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["requirement_candidate_id"], ["requirement_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", "requirement_candidate_id", name="uq_requirement_candidate_link"),
    )
    op.create_index(
        "ix_requirement_candidate_links_requirement_id",
        "requirement_candidate_links",
        ["requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_candidate_links_candidate_id",
        "requirement_candidate_links",
        ["requirement_candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_requirement_candidate_links_candidate_id", table_name="requirement_candidate_links")
    op.drop_index("ix_requirement_candidate_links_requirement_id", table_name="requirement_candidate_links")
    op.drop_table("requirement_candidate_links")

    op.drop_index("ix_requirements_status", table_name="requirements")
    op.drop_index("ix_requirements_category", table_name="requirements")
    op.drop_index("ix_requirements_tender_id", table_name="requirements")
    op.drop_table("requirements")
