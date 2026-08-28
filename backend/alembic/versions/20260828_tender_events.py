"""add tender events timeline tables

Revision ID: 20260828_tender_events
Revises: 20260827_doc_refs_rel
Create Date: 2026-08-28 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_tender_events"
down_revision = "20260827_doc_refs_rel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("semantic_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="UNKNOWN"),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("event_time", sa.Time(), nullable=True),
        sa.Column("date_precision", sa.String(length=16), nullable=False, server_default="DAY"),
        sa.Column("timezone", sa.String(length=32), nullable=True),
        sa.Column("raw_date_text", sa.String(length=64), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="SUGGESTED"),
        sa.Column("detection_origin", sa.String(length=32), nullable=False, server_default="DETERMINISTIC"),
        sa.Column("detector_version", sa.String(length=32), nullable=False, server_default="mvp-03.2"),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("human_event_type", sa.String(length=64), nullable=True),
        sa.Column("human_title", sa.String(length=255), nullable=True),
        sa.Column("human_event_date", sa.Date(), nullable=True),
        sa.Column("human_event_time", sa.Time(), nullable=True),
        sa.Column("human_date_precision", sa.String(length=16), nullable=True),
        sa.Column("human_timezone", sa.String(length=32), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "semantic_key", name="uq_tender_event_semantic_key"),
    )
    op.create_index("ix_tender_events_tender_id", "tender_events", ["tender_id"], unique=False)
    op.create_index("ix_tender_events_review_status", "tender_events", ["review_status"], unique=False)
    op.create_index("ix_tender_events_event_date", "tender_events", ["event_date"], unique=False)

    op.create_table(
        "tender_event_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("excerpt_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["event_id"], ["tender_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "source_document_id", "source_page", "excerpt_sha256", name="uq_tender_event_evidence_item"),
    )
    op.create_index("ix_tender_event_evidence_event_id", "tender_event_evidence", ["event_id"], unique=False)
    op.create_index("ix_tender_event_evidence_source_document_id", "tender_event_evidence", ["source_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_event_evidence_source_document_id", table_name="tender_event_evidence")
    op.drop_index("ix_tender_event_evidence_event_id", table_name="tender_event_evidence")
    op.drop_table("tender_event_evidence")

    op.drop_index("ix_tender_events_event_date", table_name="tender_events")
    op.drop_index("ix_tender_events_review_status", table_name="tender_events")
    op.drop_index("ix_tender_events_tender_id", table_name="tender_events")
    op.drop_table("tender_events")
