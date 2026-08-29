"""add requirement evidence candidate match tables

Revision ID: 20260829_ev_match_053
Revises: 20260829_company_evidence_052
Create Date: 2026-08-29 22:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260829_ev_match_053"
down_revision: Union[str, Sequence[str], None] = "20260829_company_evidence_052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_evidence_candidate_matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("company_evidence_id", sa.String(length=36), nullable=False),
        sa.Column("match_strength", sa.String(length=32), nullable=False),
        sa.Column("match_basis_json", sa.Text(), nullable=False),
        sa.Column("match_rationale", sa.Text(), nullable=False),
        sa.Column("system_warnings_json", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("matcher_version", sa.String(length=64), nullable=False),
        sa.Column("requirement_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("match_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_evidence_id"], ["company_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id",
            "requirement_id",
            "company_id",
            "company_evidence_id",
            "origin",
            name="uq_requirement_evidence_candidate_match_pair_origin",
        ),
    )
    op.create_index("ix_req_ev_match_active", "requirement_evidence_candidate_matches", ["is_active"], unique=False)
    op.create_index("ix_req_ev_match_company_evidence_id", "requirement_evidence_candidate_matches", ["company_evidence_id"], unique=False)
    op.create_index("ix_req_ev_match_company_id", "requirement_evidence_candidate_matches", ["company_id"], unique=False)
    op.create_index("ix_req_ev_match_requirement_id", "requirement_evidence_candidate_matches", ["requirement_id"], unique=False)
    op.create_index("ix_req_ev_match_strength", "requirement_evidence_candidate_matches", ["match_strength"], unique=False)
    op.create_index("ix_req_ev_match_tender_id", "requirement_evidence_candidate_matches", ["tender_id"], unique=False)

    op.create_table(
        "requirement_evidence_candidate_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("match_id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["requirement_evidence_candidate_matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", name="uq_requirement_evidence_candidate_review_match_id"),
    )
    op.create_index("ix_req_ev_match_review_company_id", "requirement_evidence_candidate_reviews", ["company_id"], unique=False)
    op.create_index("ix_req_ev_match_review_status", "requirement_evidence_candidate_reviews", ["review_status"], unique=False)
    op.create_index("ix_req_ev_match_review_tender_id", "requirement_evidence_candidate_reviews", ["tender_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_req_ev_match_review_tender_id", table_name="requirement_evidence_candidate_reviews")
    op.drop_index("ix_req_ev_match_review_status", table_name="requirement_evidence_candidate_reviews")
    op.drop_index("ix_req_ev_match_review_company_id", table_name="requirement_evidence_candidate_reviews")
    op.drop_table("requirement_evidence_candidate_reviews")

    op.drop_index("ix_req_ev_match_tender_id", table_name="requirement_evidence_candidate_matches")
    op.drop_index("ix_req_ev_match_strength", table_name="requirement_evidence_candidate_matches")
    op.drop_index("ix_req_ev_match_requirement_id", table_name="requirement_evidence_candidate_matches")
    op.drop_index("ix_req_ev_match_company_id", table_name="requirement_evidence_candidate_matches")
    op.drop_index("ix_req_ev_match_company_evidence_id", table_name="requirement_evidence_candidate_matches")
    op.drop_index("ix_req_ev_match_active", table_name="requirement_evidence_candidate_matches")
    op.drop_table("requirement_evidence_candidate_matches")