"""add deterministic compliance assessment tables

Revision ID: 20260829_cmp_eval_054
Revises: 20260829_ev_match_053
Create Date: 2026-08-29 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260829_cmp_eval_054"
down_revision: Union[str, Sequence[str], None] = "20260829_ev_match_053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_compliance_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("system_status", sa.String(length=32), nullable=False),
        sa.Column("applicability_context", sa.String(length=32), nullable=False),
        sa.Column("assessment_summary", sa.Text(), nullable=False),
        sa.Column("warning_codes_json", sa.Text(), nullable=False),
        sa.Column("evaluator_version", sa.String(length=64), nullable=False),
        sa.Column("assessment_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tender_id",
            "company_id",
            "requirement_id",
            name="uq_requirement_compliance_assessment_scope",
        ),
    )
    op.create_index("ix_req_compliance_assessment_applicability", "requirement_compliance_assessments", ["applicability_context"], unique=False)
    op.create_index("ix_req_compliance_assessment_company_id", "requirement_compliance_assessments", ["company_id"], unique=False)
    op.create_index("ix_req_compliance_assessment_requirement_id", "requirement_compliance_assessments", ["requirement_id"], unique=False)
    op.create_index("ix_req_compliance_assessment_status", "requirement_compliance_assessments", ["system_status"], unique=False)
    op.create_index("ix_req_compliance_assessment_tender_id", "requirement_compliance_assessments", ["tender_id"], unique=False)

    op.create_table(
        "requirement_compliance_checks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("check_type", sa.String(length=64), nullable=False),
        sa.Column("check_status", sa.String(length=32), nullable=False),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("observed_value", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("company_evidence_id", sa.String(length=36), nullable=True),
        sa.Column("match_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["requirement_compliance_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_evidence_id"], ["company_evidence.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["requirement_evidence_candidate_matches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_req_compliance_check_assessment_id", "requirement_compliance_checks", ["assessment_id"], unique=False)
    op.create_index("ix_req_compliance_check_company_evidence_id", "requirement_compliance_checks", ["company_evidence_id"], unique=False)
    op.create_index("ix_req_compliance_check_match_id", "requirement_compliance_checks", ["match_id"], unique=False)
    op.create_index("ix_req_compliance_check_status", "requirement_compliance_checks", ["check_status"], unique=False)
    op.create_index("ix_req_compliance_check_type", "requirement_compliance_checks", ["check_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_req_compliance_check_type", table_name="requirement_compliance_checks")
    op.drop_index("ix_req_compliance_check_status", table_name="requirement_compliance_checks")
    op.drop_index("ix_req_compliance_check_match_id", table_name="requirement_compliance_checks")
    op.drop_index("ix_req_compliance_check_company_evidence_id", table_name="requirement_compliance_checks")
    op.drop_index("ix_req_compliance_check_assessment_id", table_name="requirement_compliance_checks")
    op.drop_table("requirement_compliance_checks")

    op.drop_index("ix_req_compliance_assessment_tender_id", table_name="requirement_compliance_assessments")
    op.drop_index("ix_req_compliance_assessment_status", table_name="requirement_compliance_assessments")
    op.drop_index("ix_req_compliance_assessment_requirement_id", table_name="requirement_compliance_assessments")
    op.drop_index("ix_req_compliance_assessment_company_id", table_name="requirement_compliance_assessments")
    op.drop_index("ix_req_compliance_assessment_applicability", table_name="requirement_compliance_assessments")
    op.drop_table("requirement_compliance_assessments")
