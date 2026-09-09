"""add tender source effects table

Revision ID: 20260908_src_eff_068
Revises: 20260908_scope_qty_067
Create Date: 2026-09-08 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260908_src_eff_068"
down_revision: Union[str, Sequence[str], None] = "20260908_scope_qty_067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_source_effects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("acting_document_id", sa.String(length=36), nullable=False),
        sa.Column("affected_document_id", sa.String(length=36), nullable=True),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("affected_document_page_id", sa.String(length=36), nullable=True),
        sa.Column("effect_type", sa.String(length=32), nullable=False),
        sa.Column("effect_scope", sa.String(length=32), nullable=False),
        sa.Column("affected_document_ref_raw", sa.String(length=255), nullable=True),
        sa.Column("affected_locator_raw", sa.String(length=255), nullable=True),
        sa.Column("effective_date_raw", sa.String(length=64), nullable=True),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("source_artifact_key", sa.String(length=255), nullable=False),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_contract_version", sa.String(length=64), nullable=True),
        sa.Column("source_analysis_id", sa.String(length=36), nullable=True),
        sa.Column("source_page_result_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_tender_source_effects_confidence_range",
        ),
        sa.CheckConstraint(
            "effect_type IN ('SUPERSEDES', 'AMENDS', 'CORRECTS', 'CLARIFIES', 'SUPPLEMENTS', 'REVOKES', 'UNSPECIFIED')",
            name="ck_tender_source_effects_effect_type_allowed",
        ),
        sa.CheckConstraint(
            "effect_scope IN ('DOCUMENT_WIDE', 'PARTIAL', 'UNRESOLVED')",
            name="ck_tender_source_effects_effect_scope_allowed",
        ),
        sa.CheckConstraint(
            "source_method IN ('NATIVE', 'OCR', 'VISION')",
            name="ck_tender_source_effects_source_method_allowed",
        ),
        sa.CheckConstraint(
            "length(trim(source_artifact_key)) > 0",
            name="ck_tender_source_effects_source_artifact_key_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(source_locator)) > 0",
            name="ck_tender_source_effects_source_locator_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(source_excerpt)) > 0",
            name="ck_tender_source_effects_source_excerpt_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(semantic_fingerprint)) > 0",
            name="ck_tender_source_effects_semantic_fingerprint_not_blank",
        ),
        sa.CheckConstraint(
            "effect_type != 'UNSPECIFIED' OR review_required = TRUE",
            name="ck_tender_source_effects_unspecified_requires_review",
        ),
        sa.CheckConstraint(
            "effect_scope != 'UNRESOLVED' OR review_required = TRUE",
            name="ck_tender_source_effects_unresolved_requires_review",
        ),
        sa.CheckConstraint(
            "effect_scope != 'PARTIAL' OR affected_document_page_id IS NOT NULL OR (affected_locator_raw IS NOT NULL AND length(trim(affected_locator_raw)) > 0)",
            name="ck_tender_source_effects_partial_requires_target_detail",
        ),
        sa.CheckConstraint(
            "acting_document_id != affected_document_id",
            name="ck_tender_source_effects_acting_not_affected",
        ),
        sa.CheckConstraint(
            "affected_document_id IS NOT NULL OR (affected_document_ref_raw IS NOT NULL AND length(trim(affected_document_ref_raw)) > 0) OR review_required = TRUE",
            name="ck_tender_source_effects_target_or_review",
        ),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acting_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["affected_document_id"], ["tender_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["affected_document_page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_analysis_id"], ["document_vision_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_page_result_id"], ["document_vision_page_results.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "acting_document_id",
            "source_artifact_key",
            "semantic_fingerprint",
            name="uq_tender_source_effects_acting_artifact_fingerprint",
        ),
    )
    op.create_index("ix_tender_source_effects_tender_id", "tender_source_effects", ["tender_id"], unique=False)
    op.create_index("ix_tender_source_effects_acting_document_id", "tender_source_effects", ["acting_document_id"], unique=False)
    op.create_index("ix_tender_source_effects_affected_document_id", "tender_source_effects", ["affected_document_id"], unique=False)
    op.create_index("ix_tender_source_effects_document_page_id", "tender_source_effects", ["document_page_id"], unique=False)
    op.create_index("ix_tender_source_effects_affected_document_page_id", "tender_source_effects", ["affected_document_page_id"], unique=False)
    op.create_index("ix_tender_source_effects_effect_type", "tender_source_effects", ["effect_type"], unique=False)
    op.create_index("ix_tender_source_effects_effect_scope", "tender_source_effects", ["effect_scope"], unique=False)
    op.create_index("ix_tender_source_effects_source_artifact_key", "tender_source_effects", ["source_artifact_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_source_effects_source_artifact_key", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_effect_scope", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_effect_type", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_affected_document_page_id", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_document_page_id", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_affected_document_id", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_acting_document_id", table_name="tender_source_effects")
    op.drop_index("ix_tender_source_effects_tender_id", table_name="tender_source_effects")
    op.drop_table("tender_source_effects")
