"""add requirement reviews table

Revision ID: 20260829_req_review_046
Revises: 20260829_req_ver_045
Create Date: 2026-08-29 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260829_req_review_046"
down_revision = "20260829_req_ver_045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", name="uq_requirement_reviews_requirement_id"),
    )
    op.create_index("ix_requirement_reviews_tender_id", "requirement_reviews", ["tender_id"], unique=False)
    op.create_index("ix_requirement_reviews_requirement_id", "requirement_reviews", ["requirement_id"], unique=False)
    op.create_index("ix_requirement_reviews_review_status", "requirement_reviews", ["review_status"], unique=False)
    op.create_index("ix_requirement_reviews_reviewed_at", "requirement_reviews", ["reviewed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_requirement_reviews_reviewed_at", table_name="requirement_reviews")
    op.drop_index("ix_requirement_reviews_review_status", table_name="requirement_reviews")
    op.drop_index("ix_requirement_reviews_requirement_id", table_name="requirement_reviews")
    op.drop_index("ix_requirement_reviews_tender_id", table_name="requirement_reviews")
    op.drop_table("requirement_reviews")
