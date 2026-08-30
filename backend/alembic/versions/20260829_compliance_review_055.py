"""add human compliance decision table

Revision ID: 20260829_cmp_review_055
Revises: 20260829_cmp_eval_054
Create Date: 2026-08-29 23:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260829_cmp_review_055"
down_revision: Union[str, Sequence[str], None] = "20260829_cmp_eval_054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requirement_compliance_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tender_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("decision_status", sa.String(length=32), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("reviewed_assessment_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
            name="uq_requirement_compliance_decision_scope",
        ),
    )
    op.create_index("ix_req_compliance_decision_company_id", "requirement_compliance_decisions", ["company_id"], unique=False)
    op.create_index("ix_req_compliance_decision_requirement_id", "requirement_compliance_decisions", ["requirement_id"], unique=False)
    op.create_index("ix_req_compliance_decision_status", "requirement_compliance_decisions", ["decision_status"], unique=False)
    op.create_index("ix_req_compliance_decision_tender_id", "requirement_compliance_decisions", ["tender_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_req_compliance_decision_tender_id", table_name="requirement_compliance_decisions")
    op.drop_index("ix_req_compliance_decision_status", table_name="requirement_compliance_decisions")
    op.drop_index("ix_req_compliance_decision_requirement_id", table_name="requirement_compliance_decisions")
    op.drop_index("ix_req_compliance_decision_company_id", table_name="requirement_compliance_decisions")
    op.drop_table("requirement_compliance_decisions")
