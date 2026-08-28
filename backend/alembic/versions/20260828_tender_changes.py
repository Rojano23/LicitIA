"""add tender changes and evidence tables

Revision ID: 20260828_tender_changes
Revises: 20260828_tender_events
Create Date: 2026-08-28 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_tender_changes"
down_revision = "20260828_tender_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_relationships",
        sa.Column("relationship_origin", sa.String(length=32), nullable=False, server_default="REFERENCE_ENGINE"),
    )
    op.create_index("ix_document_relationships_relationship_origin", "document_relationships", ["relationship_origin"], unique=False)

    op.create_table(
        "tender_changes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("change_type", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("target_reference_key", sa.String(length=128), nullable=True),
        sa.Column("target_document_id", sa.String(length=36), nullable=True),
        sa.Column("target_candidate_document_ids", sa.Text(), nullable=True),
        sa.Column("target_locator_text", sa.String(length=255), nullable=True),
        sa.Column("before_text", sa.Text(), nullable=True),
        sa.Column("after_text", sa.Text(), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("detection_origin", sa.String(length=32), nullable=False, server_default="DETERMINISTIC"),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="mvp-03.3"),
        sa.Column("human_change_type", sa.String(length=32), nullable=True),
        sa.Column("human_target_document_id", sa.String(length=36), nullable=True),
        sa.Column("human_target_locator_text", sa.String(length=255), nullable=True),
        sa.Column("human_before_text", sa.Text(), nullable=True),
        sa.Column("human_after_text", sa.Text(), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_target_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "semantic_key", name="uq_tender_change_semantic_key"),
    )
    op.create_index("ix_tender_changes_tender_id", "tender_changes", ["tender_id"], unique=False)
    op.create_index("ix_tender_changes_review_status", "tender_changes", ["review_status"], unique=False)
    op.create_index("ix_tender_changes_change_type", "tender_changes", ["change_type"], unique=False)

    op.create_table(
        "tender_change_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["change_id"], ["tender_changes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("change_id", "source_document_id", "source_page", "excerpt_sha256", name="uq_tender_change_evidence_item"),
    )
    op.create_index("ix_tender_change_evidence_change_id", "tender_change_evidence", ["change_id"], unique=False)
    op.create_index("ix_tender_change_evidence_source_document_id", "tender_change_evidence", ["source_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_change_evidence_source_document_id", table_name="tender_change_evidence")
    op.drop_index("ix_tender_change_evidence_change_id", table_name="tender_change_evidence")
    op.drop_table("tender_change_evidence")

    op.drop_index("ix_tender_changes_change_type", table_name="tender_changes")
    op.drop_index("ix_tender_changes_review_status", table_name="tender_changes")
    op.drop_index("ix_tender_changes_tender_id", table_name="tender_changes")
    op.drop_table("tender_changes")

    op.drop_index("ix_document_relationships_relationship_origin", table_name="document_relationships")
    op.drop_column("document_relationships", "relationship_origin")
