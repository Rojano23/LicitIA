"""add requirement version links table

Revision ID: 20260829_req_ver_045
Revises: 20260829_req_sem_044
Create Date: 2026-08-29 02:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260829_req_ver_045"
down_revision = "20260829_req_sem_044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_version_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("change_id", sa.String(length=36), nullable=False),
        sa.Column("predecessor_requirement_id", sa.String(length=36), nullable=True),
        sa.Column("successor_requirement_id", sa.String(length=36), nullable=True),
        sa.Column("link_kind", sa.String(length=32), nullable=False, server_default="SUPERSEDES"),
        sa.Column("matching_basis", sa.String(length=64), nullable=False, server_default="EXPLICIT_CHANGE_EVIDENCE"),
        sa.Column("target_locator_text", sa.String(length=255), nullable=True),
        sa.Column("before_text", sa.Text(), nullable=True),
        sa.Column("after_text", sa.Text(), nullable=True),
        sa.Column("analyzer_version", sa.String(length=32), nullable=False, server_default="mvp-04.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["change_id"], ["tender_changes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["predecessor_requirement_id"], ["requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["successor_requirement_id"], ["requirements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id",
            "change_id",
            "predecessor_requirement_id",
            "successor_requirement_id",
            "link_kind",
            name="uq_requirement_version_link_item",
        ),
    )
    op.create_index("ix_requirement_version_links_tender_id", "requirement_version_links", ["tender_id"], unique=False)
    op.create_index("ix_requirement_version_links_change_id", "requirement_version_links", ["change_id"], unique=False)
    op.create_index(
        "ix_requirement_version_links_predecessor_id",
        "requirement_version_links",
        ["predecessor_requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_version_links_successor_id",
        "requirement_version_links",
        ["successor_requirement_id"],
        unique=False,
    )
    op.create_index("ix_requirement_version_links_link_kind", "requirement_version_links", ["link_kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_requirement_version_links_link_kind", table_name="requirement_version_links")
    op.drop_index("ix_requirement_version_links_successor_id", table_name="requirement_version_links")
    op.drop_index("ix_requirement_version_links_predecessor_id", table_name="requirement_version_links")
    op.drop_index("ix_requirement_version_links_change_id", table_name="requirement_version_links")
    op.drop_index("ix_requirement_version_links_tender_id", table_name="requirement_version_links")
    op.drop_table("requirement_version_links")
