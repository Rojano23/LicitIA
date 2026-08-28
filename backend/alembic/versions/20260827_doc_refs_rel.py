"""add document references and relationships

Revision ID: 20260827_doc_refs_rel
Revises: 20260827_doc_class_candidates
Create Date: 2026-08-27 23:58:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_doc_refs_rel"
down_revision = "20260827_doc_class_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_reference_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("input_fingerprint_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("extractor_version", sa.String(length=32), nullable=False, server_default="mvp-02.5"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NOT_READY"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_document_reference_analysis_document"),
    )
    op.create_index("ix_document_reference_analyses_document_id", "document_reference_analyses", ["document_id"], unique=False)

    op.create_table(
        "document_references",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=True),
        sa.Column("normalized_content_id", sa.String(length=36), nullable=True),
        sa.Column("document_chunk_id", sa.String(length=36), nullable=True),
        sa.Column("reference_identity_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("raw_reference_text", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("normalized_reference_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("reference_kind", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("relationship_hint", sa.String(length=32), nullable=False, server_default="REFERENCES"),
        sa.Column("resolution_status", sa.String(length=32), nullable=False, server_default="UNRESOLVED"),
        sa.Column("resolved_target_document_id", sa.String(length=36), nullable=True),
        sa.Column("auto_candidate_document_ids", sa.Text(), nullable=True),
        sa.Column("human_target_document_id", sa.String(length=36), nullable=True),
        sa.Column("human_decision", sa.String(length=32), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("source_scope", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_engine", sa.String(length=32), nullable=True),
        sa.Column("source_region_id", sa.String(length=36), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("extractor_version", sa.String(length=32), nullable=False, server_default="mvp-02.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["analysis_id"], ["document_reference_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["normalized_content_id"], ["normalized_content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_target_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["human_target_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_region_id"], ["document_page_regions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_document_id", "reference_identity_key", name="uq_document_reference_identity"),
    )
    op.create_index("ix_document_references_source_document_id", "document_references", ["source_document_id"], unique=False)
    op.create_index("ix_document_references_resolution_status", "document_references", ["resolution_status"], unique=False)
    op.create_index("ix_document_references_normalized_reference_key", "document_references", ["normalized_reference_key"], unique=False)

    op.create_table(
        "document_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("target_document_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False, server_default="REFERENCES"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_document_id", "target_document_id", "relationship_type", name="uq_document_relationship_edge"),
    )
    op.create_index("ix_document_relationships_tender_id", "document_relationships", ["tender_id"], unique=False)
    op.create_index("ix_document_relationships_source_document_id", "document_relationships", ["source_document_id"], unique=False)
    op.create_index("ix_document_relationships_target_document_id", "document_relationships", ["target_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_relationships_target_document_id", table_name="document_relationships")
    op.drop_index("ix_document_relationships_source_document_id", table_name="document_relationships")
    op.drop_index("ix_document_relationships_tender_id", table_name="document_relationships")
    op.drop_table("document_relationships")

    op.drop_index("ix_document_references_normalized_reference_key", table_name="document_references")
    op.drop_index("ix_document_references_resolution_status", table_name="document_references")
    op.drop_index("ix_document_references_source_document_id", table_name="document_references")
    op.drop_table("document_references")

    op.drop_index("ix_document_reference_analyses_document_id", table_name="document_reference_analyses")
    op.drop_table("document_reference_analyses")
