"""add companies and company documents tables

Revision ID: 20260829_company_documents_051
Revises: 20260829_req_review_046
Create Date: 2026-08-29 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260829_company_documents_051"
down_revision = "20260829_req_review_046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)
    op.create_index("ix_companies_created_at", "companies", ["created_at"], unique=False)

    op.create_table(
        "company_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("source_relative_path", sa.String(length=512), nullable=True),
        sa.Column("stored_relative_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="IMPORTED"),
        sa.Column("document_type", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("metadata_note", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_of_document_id", sa.String(length=36), nullable=True),
        sa.Column("conflict_resolution_action", sa.String(length=32), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_of_document_id"], ["company_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "sha256", name="uq_company_document_sha256"),
    )
    op.create_index("ix_company_documents_company_id", "company_documents", ["company_id"], unique=False)
    op.create_index("ix_company_documents_status", "company_documents", ["status"], unique=False)
    op.create_index("ix_company_documents_imported_at", "company_documents", ["imported_at"], unique=False)
    op.create_index("ix_company_documents_revision_of_document_id", "company_documents", ["revision_of_document_id"], unique=False)
    op.create_index("ix_company_documents_conflict_resolution_action", "company_documents", ["conflict_resolution_action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_company_documents_conflict_resolution_action", table_name="company_documents")
    op.drop_index("ix_company_documents_revision_of_document_id", table_name="company_documents")
    op.drop_index("ix_company_documents_imported_at", table_name="company_documents")
    op.drop_index("ix_company_documents_status", table_name="company_documents")
    op.drop_index("ix_company_documents_company_id", table_name="company_documents")
    op.drop_table("company_documents")

    op.drop_index("ix_companies_created_at", table_name="companies")
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_table("companies")
