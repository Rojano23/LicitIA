"""add evaluation model detection tables

Revision ID: 20260828_eval_model_041
Revises: 20260828_tender_changes
Create Date: 2026-08-28 22:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_eval_model_041"
down_revision = "20260828_tender_changes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_evaluation_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("suggested_method", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("human_method", sa.String(length=64), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("human_summary", sa.Text(), nullable=True),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="mvp-04.1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", name="uq_tender_evaluation_model_tender"),
    )
    op.create_index("ix_tender_evaluation_models_tender_id", "tender_evaluation_models", ["tender_id"], unique=False)
    op.create_index("ix_tender_evaluation_models_review_status", "tender_evaluation_models", ["review_status"], unique=False)

    op.create_table(
        "tender_evaluation_model_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_model_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("evidence_role", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["evaluation_model_id"], ["tender_evaluation_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_model_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_tender_evaluation_model_evidence_item",
        ),
    )
    op.create_index(
        "ix_tender_evaluation_model_evidence_model_id",
        "tender_evaluation_model_evidence",
        ["evaluation_model_id"],
        unique=False,
    )
    op.create_index(
        "ix_tender_evaluation_model_evidence_source_document_id",
        "tender_evaluation_model_evidence",
        ["source_document_id"],
        unique=False,
    )

    op.create_table(
        "evaluation_criteria",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_model_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("criterion_type", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("criterion_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("weight_value", sa.Float(), nullable=True),
        sa.Column("weight_unit", sa.String(length=32), nullable=True),
        sa.Column("threshold_operator", sa.String(length=32), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("threshold_unit", sa.String(length=32), nullable=True),
        sa.Column("is_exclusionary", sa.Boolean(), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("detection_origin", sa.String(length=32), nullable=False, server_default="DETERMINISTIC"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="mvp-04.1"),
        sa.Column("human_criterion_type", sa.String(length=64), nullable=True),
        sa.Column("human_category", sa.String(length=64), nullable=True),
        sa.Column("human_title", sa.String(length=255), nullable=True),
        sa.Column("human_criterion_text", sa.Text(), nullable=True),
        sa.Column("human_weight_value", sa.Float(), nullable=True),
        sa.Column("human_weight_unit", sa.String(length=32), nullable=True),
        sa.Column("human_threshold_operator", sa.String(length=32), nullable=True),
        sa.Column("human_threshold_value", sa.Float(), nullable=True),
        sa.Column("human_threshold_unit", sa.String(length=32), nullable=True),
        sa.Column("human_is_exclusionary", sa.Boolean(), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_model_id"], ["tender_evaluation_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "semantic_key", name="uq_evaluation_criteria_semantic_key"),
    )
    op.create_index("ix_evaluation_criteria_tender_id", "evaluation_criteria", ["tender_id"], unique=False)
    op.create_index("ix_evaluation_criteria_evaluation_model_id", "evaluation_criteria", ["evaluation_model_id"], unique=False)
    op.create_index("ix_evaluation_criteria_review_status", "evaluation_criteria", ["review_status"], unique=False)
    op.create_index("ix_evaluation_criteria_type", "evaluation_criteria", ["criterion_type"], unique=False)

    op.create_table(
        "evaluation_criterion_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("criterion_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("evidence_role", sa.String(length=32), nullable=False, server_default="OTHER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["criterion_id"], ["evaluation_criteria.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "criterion_id",
            "source_document_id",
            "source_page",
            "excerpt_sha256",
            name="uq_evaluation_criterion_evidence_item",
        ),
    )
    op.create_index("ix_evaluation_criterion_evidence_criterion_id", "evaluation_criterion_evidence", ["criterion_id"], unique=False)
    op.create_index("ix_evaluation_criterion_evidence_source_document_id", "evaluation_criterion_evidence", ["source_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluation_criterion_evidence_source_document_id", table_name="evaluation_criterion_evidence")
    op.drop_index("ix_evaluation_criterion_evidence_criterion_id", table_name="evaluation_criterion_evidence")
    op.drop_table("evaluation_criterion_evidence")

    op.drop_index("ix_evaluation_criteria_type", table_name="evaluation_criteria")
    op.drop_index("ix_evaluation_criteria_review_status", table_name="evaluation_criteria")
    op.drop_index("ix_evaluation_criteria_evaluation_model_id", table_name="evaluation_criteria")
    op.drop_index("ix_evaluation_criteria_tender_id", table_name="evaluation_criteria")
    op.drop_table("evaluation_criteria")

    op.drop_index("ix_tender_evaluation_model_evidence_source_document_id", table_name="tender_evaluation_model_evidence")
    op.drop_index("ix_tender_evaluation_model_evidence_model_id", table_name="tender_evaluation_model_evidence")
    op.drop_table("tender_evaluation_model_evidence")

    op.drop_index("ix_tender_evaluation_models_review_status", table_name="tender_evaluation_models")
    op.drop_index("ix_tender_evaluation_models_tender_id", table_name="tender_evaluation_models")
    op.drop_table("tender_evaluation_models")
