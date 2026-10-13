"""Nullable typed perception provenance for logical Requirement evidence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261013_req_perception_prov_072"
down_revision = "20261012_alt_compliance_071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("requirement_candidate_evidence",
                  sa.Column("perception_provenance", JSONB(none_as_null=True), nullable=True))


def downgrade() -> None:
    op.drop_column("requirement_candidate_evidence", "perception_provenance")
