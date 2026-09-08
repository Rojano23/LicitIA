"""add tender scope quantities table

Revision ID: 20260908_scope_qty_067
Revises: 20260908_scope_attr_066
Create Date: 2026-09-08 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260908_scope_qty_067"
down_revision: Union[str, Sequence[str], None] = "20260908_scope_attr_066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_scope_quantities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("scope_detail_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("quantity_raw", sa.String(length=128), nullable=False),
        sa.Column("quantity_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("quantity_min", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("quantity_max", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("unit_raw", sa.String(length=128), nullable=True),
        sa.Column("measure_kind", sa.String(length=32), nullable=True),
        sa.Column("relation", sa.String(length=32), nullable=True),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("source_artifact_key", sa.String(length=255), nullable=False),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_contract_version", sa.String(length=64), nullable=True),
        sa.Column("source_analysis_id", sa.String(length=36), nullable=True),
        sa.Column("source_page_result_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_tender_scope_quantities_confidence_range",
        ),
        sa.CheckConstraint(
            "relation IS NULL OR relation IN ('EXACT', 'MINIMUM', 'MAXIMUM', 'RANGE', 'APPROXIMATE', 'UNSPECIFIED')",
            name="ck_tender_scope_quantities_relation_allowed",
        ),
        sa.CheckConstraint(
            "measure_kind IS NULL OR measure_kind IN ('COUNT', 'LENGTH', 'AREA', 'VOLUME', 'MASS', 'DURATION', 'PERSONNEL', 'SERVICE', 'LOT', 'OTHER')",
            name="ck_tender_scope_quantities_measure_kind_allowed",
        ),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_detail_id"], ["tender_scope_details.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["tender_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_analysis_id"], ["document_vision_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_page_result_id"], ["document_vision_page_results.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_detail_id",
            "source_artifact_key",
            "semantic_fingerprint",
            name="uq_tender_scope_quantities_artifact_fingerprint",
        ),
    )
    op.create_index("ix_tender_scope_quantities_tender_id", "tender_scope_quantities", ["tender_id"], unique=False)
    op.create_index("ix_tender_scope_quantities_scope_detail_id", "tender_scope_quantities", ["scope_detail_id"], unique=False)
    op.create_index("ix_tender_scope_quantities_source_document_id", "tender_scope_quantities", ["source_document_id"], unique=False)
    op.create_index("ix_tender_scope_quantities_document_page_id", "tender_scope_quantities", ["document_page_id"], unique=False)
    op.create_index("ix_tender_scope_quantities_source_artifact_key", "tender_scope_quantities", ["source_artifact_key"], unique=False)
    op.create_index("ix_tender_scope_quantities_measure_kind", "tender_scope_quantities", ["measure_kind"], unique=False)
    op.create_index("ix_tender_scope_quantities_relation", "tender_scope_quantities", ["relation"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tender_scope_quantities_relation", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_measure_kind", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_source_artifact_key", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_document_page_id", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_source_document_id", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_scope_detail_id", table_name="tender_scope_quantities")
    op.drop_index("ix_tender_scope_quantities_tender_id", table_name="tender_scope_quantities")
    op.drop_table("tender_scope_quantities")
