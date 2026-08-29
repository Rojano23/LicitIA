"""add requirement extraction tables

Revision ID: 20260828_req_extract_042
Revises: 20260828_eval_model_041
Create Date: 2026-08-28 23:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_req_extract_042"
down_revision = "20260828_eval_model_041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("requirement_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("actor_text", sa.String(length=255), nullable=True),
        sa.Column("modality_text", sa.String(length=128), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("document_page_id", sa.String(length=36), nullable=True),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=True),
        sa.Column("detection_origin", sa.String(length=32), nullable=False, server_default="DETERMINISTIC"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="mvp-04.2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "semantic_key", name="uq_requirement_candidates_semantic_key"),
    )
    op.create_index("ix_requirement_candidates_tender_id", "requirement_candidates", ["tender_id"], unique=False)
    op.create_index("ix_requirement_candidates_source_document_id", "requirement_candidates", ["source_document_id"], unique=False)
    op.create_index("ix_requirement_candidates_review_status", "requirement_candidates", ["review_status"], unique=False)

    op.create_table(
        "requirement_candidate_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("document_page_id", sa.String(length=36), nullable=True),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["candidate_id"], ["requirement_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_requirement_candidate_evidence_item",
        ),
    )
    op.create_index(
        "ix_requirement_candidate_evidence_candidate_id",
        "requirement_candidate_evidence",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_requirement_candidate_evidence_source_document_id",
        "requirement_candidate_evidence",
        ["source_document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_requirement_candidate_evidence_source_document_id", table_name="requirement_candidate_evidence")
    op.drop_index("ix_requirement_candidate_evidence_candidate_id", table_name="requirement_candidate_evidence")
    op.drop_table("requirement_candidate_evidence")

    op.drop_index("ix_requirement_candidates_review_status", table_name="requirement_candidates")
    op.drop_index("ix_requirement_candidates_source_document_id", table_name="requirement_candidates")
    op.drop_index("ix_requirement_candidates_tender_id", table_name="requirement_candidates")
    op.drop_table("requirement_candidates")