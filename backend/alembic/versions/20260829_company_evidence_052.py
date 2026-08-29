"""add company evidence intelligence tables

Revision ID: 20260829_company_evidence_052
Revises: 20260829_company_documents_051
Create Date: 2026-08-29 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260829_company_evidence_052"
down_revision: Union[str, Sequence[str], None] = "20260829_company_documents_051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("company_document_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("subject_kind", sa.String(length=32), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("canonical_statement", sa.Text(), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("reference_number", sa.String(length=255), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_locator", sa.String(length=512), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_document_id"], ["company_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_evidence_analysis_status", "company_evidence", ["analysis_status"], unique=False)
    op.create_index("ix_company_evidence_company_document_id", "company_evidence", ["company_document_id"], unique=False)
    op.create_index("ix_company_evidence_company_id", "company_evidence", ["company_id"], unique=False)
    op.create_index("ix_company_evidence_evidence_type", "company_evidence", ["evidence_type"], unique=False)
    op.create_index("ix_company_evidence_subject_kind", "company_evidence", ["subject_kind"], unique=False)

    op.create_table(
        "company_evidence_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("company_evidence_id", sa.String(length=36), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_evidence_id"], ["company_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_evidence_id", name="uq_company_evidence_review_evidence_id"),
    )
    op.create_index("ix_company_evidence_reviews_company_id", "company_evidence_reviews", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_company_evidence_reviews_company_id", table_name="company_evidence_reviews")
    op.drop_table("company_evidence_reviews")

    op.drop_index("ix_company_evidence_subject_kind", table_name="company_evidence")
    op.drop_index("ix_company_evidence_evidence_type", table_name="company_evidence")
    op.drop_index("ix_company_evidence_company_id", table_name="company_evidence")
    op.drop_index("ix_company_evidence_company_document_id", table_name="company_evidence")
    op.drop_index("ix_company_evidence_analysis_status", table_name="company_evidence")
    op.drop_table("company_evidence")