"""Human technical alternatives with immutable revision history."""
from alembic import op
import sqlalchemy as sa

revision = "20261012_technical_alt_070"
down_revision = "20261012_scope_review_069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "technical_alternatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tender_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("id", "tender_id", name="uq_technical_alt_identity_tender"),
    )
    op.create_index("ix_technical_alt_tender", "technical_alternatives", ["tender_id"])
    op.create_table(
        "technical_alternative_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alternative_id", sa.String(36), nullable=False),
        sa.Column("tender_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("technical_description", sa.Text(), nullable=False),
        sa.Column("assumptions", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alternative_id", "tender_id"],
                                ["technical_alternatives.id", "technical_alternatives.tender_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("alternative_id", "revision", name="uq_technical_alt_revision"),
        sa.CheckConstraint("revision > 0", name="ck_technical_alt_revision"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_technical_alt_name"),
        sa.CheckConstraint("length(trim(technical_description)) > 0", name="ck_technical_alt_description"),
        sa.CheckConstraint("lifecycle_state IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_technical_alt_lifecycle"),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="ck_technical_alt_fingerprint"),
    )
    op.execute("""
        CREATE FUNCTION prevent_technical_alt_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Technical alternative identity and history are immutable'
                USING ERRCODE = '23514';
        END;
        $$
    """)
    for table in ("technical_alternatives", "technical_alternative_revisions"):
        op.execute(f"CREATE TRIGGER technical_alt_append_only BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION prevent_technical_alt_mutation()")


def downgrade() -> None:
    for table in ("technical_alternative_revisions", "technical_alternatives"):
        op.execute(f"DROP TRIGGER technical_alt_append_only ON {table}")
    op.execute("DROP FUNCTION prevent_technical_alt_mutation()")
    op.drop_table("technical_alternative_revisions")
    op.drop_index("ix_technical_alt_tender", table_name="technical_alternatives")
    op.drop_table("technical_alternatives")
