"""add document conflict resolution action

Revision ID: 20260826_conflict_action
Revises: 20260826_doc_revisions
Create Date: 2026-08-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260826_conflict_action"
down_revision = "20260826_doc_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tender_documents",
        sa.Column("conflict_resolution_action", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_tender_documents_conflict_resolution_action",
        "tender_documents",
        ["conflict_resolution_action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tender_documents_conflict_resolution_action", table_name="tender_documents")
    op.drop_column("tender_documents", "conflict_resolution_action")
