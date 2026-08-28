"""add document classification candidates table

Revision ID: 20260827_doc_class_candidates
Revises: 20260827_document_classification
Create Date: 2026-08-27 23:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_doc_class_candidates"
down_revision = "20260827_document_classification"
branch_labels = None
depends_on = None


CONTROLLED_FUNCTIONAL_TAGS = {
    "TECHNICAL",
    "COMMERCIAL",
    "ECONOMIC",
    "ADMINISTRATIVE",
    "LEGAL",
    "CONTRACTUAL",
    "SCHEDULE",
    "EXPERIENCE",
    "PERSONNEL",
    "SAFETY",
    "GUARANTEE",
    "REGISTRATION",
    "INSTRUCTIONS",
}


def _cleanup_legacy_candidate_tags(bind) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO document_classification_candidates (id, classification_id, candidate_type, score, created_at)
            SELECT md5(t.classification_id || '|' || t.tag), t.classification_id, t.tag, t.score, COALESCE(t.created_at, CURRENT_TIMESTAMP)
            FROM document_classification_tags t
            WHERE t.tag NOT IN :controlled_tags
            ON CONFLICT (classification_id, candidate_type) DO UPDATE
            SET score = GREATEST(document_classification_candidates.score, EXCLUDED.score)
            """
        ).bindparams(sa.bindparam("controlled_tags", expanding=True)),
        {"controlled_tags": sorted(CONTROLLED_FUNCTIONAL_TAGS)},
    )
    bind.execute(
        sa.text(
            "DELETE FROM document_classification_tags WHERE tag NOT IN :controlled_tags"
        ).bindparams(sa.bindparam("controlled_tags", expanding=True)),
        {"controlled_tags": sorted(CONTROLLED_FUNCTIONAL_TAGS)},
    )


def upgrade() -> None:
    op.create_table(
        "document_classification_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("classification_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_type", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["classification_id"], ["document_classifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classification_id", "candidate_type", name="uq_document_classification_candidate"),
    )
    op.create_index(
        "ix_document_classification_candidates_classification_id",
        "document_classification_candidates",
        ["classification_id"],
        unique=False,
    )
    _cleanup_legacy_candidate_tags(op.get_bind())


def downgrade() -> None:
    op.drop_index(
        "ix_document_classification_candidates_classification_id",
        table_name="document_classification_candidates",
    )
    op.drop_table("document_classification_candidates")
