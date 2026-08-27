"""add document revision fields

Revision ID: 20260826_add_document_revision_fields
Revises: 20260826_create_tender_documents
Create Date: 2026-08-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260826_doc_revisions"
down_revision = "20260826_create_tender_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tender_documents", sa.Column("revision_of_document_id", sa.String(length=36), nullable=True))
    op.add_column("tender_documents", sa.Column("revision_number", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("tender_documents", sa.Column("is_current", sa.Boolean(), nullable=True, server_default=sa.true()))

    op.create_foreign_key(
        "fk_tender_documents_revision_of_document_id",
        "tender_documents",
        "tender_documents",
        ["revision_of_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tender_documents_revision_of_document_id",
        "tender_documents",
        ["revision_of_document_id"],
        unique=False,
    )

    op.execute(
        "UPDATE tender_documents SET revision_number = 1 WHERE revision_number IS NULL"
    )
    op.execute(
        "UPDATE tender_documents SET is_current = true WHERE is_current IS NULL"
    )

    op.alter_column("tender_documents", "revision_number", existing_type=sa.Integer(), nullable=False)
    op.alter_column("tender_documents", "is_current", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_tender_documents_revision_of_document_id", "tender_documents", type_="foreignkey")
    op.drop_index("ix_tender_documents_revision_of_document_id", table_name="tender_documents")
    op.drop_column("tender_documents", "is_current")
    op.drop_column("tender_documents", "revision_number")
    op.drop_column("tender_documents", "revision_of_document_id")
