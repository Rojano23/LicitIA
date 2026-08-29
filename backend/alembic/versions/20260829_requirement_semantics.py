"""add requirement semantics and expected evidence tables

Revision ID: 20260829_req_sem_044
Revises: 20260828_req_norm_043
Create Date: 2026-08-29 00:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260829_req_sem_044"
down_revision = "20260828_req_norm_043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_semantics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("applicability", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("condition_text", sa.Text(), nullable=True),
        sa.Column("interpretation_status", sa.String(length=32), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("evidence_mode", sa.String(length=32), nullable=False, server_default="REVIEW_REQUIRED"),
        sa.Column("analyzer_version", sa.String(length=32), nullable=False, server_default="mvp-04.4"),
        sa.Column("interpretation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", name="uq_requirement_semantics_requirement"),
    )
    op.create_index("ix_requirement_semantics_requirement_id", "requirement_semantics", ["requirement_id"], unique=False)
    op.create_index("ix_requirement_semantics_applicability", "requirement_semantics", ["applicability"], unique=False)
    op.create_index(
        "ix_requirement_semantics_interpretation_status",
        "requirement_semantics",
        ["interpretation_status"],
        unique=False,
    )
    op.create_index("ix_requirement_semantics_evidence_mode", "requirement_semantics", ["evidence_mode"], unique=False)

    op.create_table(
        "requirement_evidence_expectations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requirement_semantics_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("analyzer_version", sa.String(length=32), nullable=False, server_default="mvp-04.4"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["requirement_semantics_id"], ["requirement_semantics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["requirement_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_semantics_id",
            "source_candidate_id",
            "evidence_type",
            "excerpt_sha256",
            name="uq_requirement_evidence_expectation_item",
        ),
    )
    op.create_index(
        "ix_requirement_evidence_expectations_semantics_id",
        "requirement_evidence_expectations",
        ["requirement_semantics_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_evidence_expectations_requirement_id",
        "requirement_evidence_expectations",
        ["requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_evidence_expectations_candidate_id",
        "requirement_evidence_expectations",
        ["source_candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_evidence_expectations_type",
        "requirement_evidence_expectations",
        ["evidence_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_requirement_evidence_expectations_type", table_name="requirement_evidence_expectations")
    op.drop_index("ix_requirement_evidence_expectations_candidate_id", table_name="requirement_evidence_expectations")
    op.drop_index("ix_requirement_evidence_expectations_requirement_id", table_name="requirement_evidence_expectations")
    op.drop_index("ix_requirement_evidence_expectations_semantics_id", table_name="requirement_evidence_expectations")
    op.drop_table("requirement_evidence_expectations")

    op.drop_index("ix_requirement_semantics_evidence_mode", table_name="requirement_semantics")
    op.drop_index("ix_requirement_semantics_interpretation_status", table_name="requirement_semantics")
    op.drop_index("ix_requirement_semantics_applicability", table_name="requirement_semantics")
    op.drop_index("ix_requirement_semantics_requirement_id", table_name="requirement_semantics")
    op.drop_table("requirement_semantics")
