"""add page image regions and OCR scope fields

Revision ID: 20260827_mixed_content_ocr_regions
Revises: 20260827_page_ocr_results
Create Date: 2026-08-27 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260827_ocr_regions"
down_revision = "20260827_page_ocr_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_page_regions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_page_id", sa.String(length=36), nullable=False),
        sa.Column("region_index", sa.Integer(), nullable=False),
        sa.Column("region_type", sa.String(length=32), nullable=False, server_default="IMAGE"),
        sa.Column("x0", sa.Float(), nullable=False),
        sa.Column("y0", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("area_ratio", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_page_id", "region_index", name="uq_document_page_regions_document_page_index"),
    )
    op.create_index("ix_document_page_regions_document_page_id", "document_page_regions", ["document_page_id"], unique=False)

    op.add_column("page_ocr_results", sa.Column("scope", sa.String(length=32), nullable=False, server_default="FULL_PAGE"))
    op.add_column("page_ocr_results", sa.Column("region_id", sa.String(length=36), nullable=True))
    op.create_index("ix_page_ocr_results_region_id", "page_ocr_results", ["region_id"], unique=False)
    op.drop_constraint("uq_page_ocr_document_page_engine", "page_ocr_results", type_="unique")
    op.create_foreign_key(
        "fk_page_ocr_results_region_id_document_page_regions",
        "page_ocr_results",
        "document_page_regions",
        ["region_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_page_ocr_document_page_engine_scope_region",
        "page_ocr_results",
        ["document_page_id", "engine", "scope", "region_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_page_ocr_document_page_engine_scope_region", "page_ocr_results", type_="unique")
    op.drop_constraint("fk_page_ocr_results_region_id_document_page_regions", "page_ocr_results", type_="foreignkey")
    op.drop_index("ix_page_ocr_results_region_id", table_name="page_ocr_results")
    op.drop_column("page_ocr_results", "region_id")
    op.drop_column("page_ocr_results", "scope")
    op.drop_index("ix_document_page_regions_document_page_id", table_name="document_page_regions")
    op.drop_table("document_page_regions")
