"""Append-only human ScopeDetail reviews.

Revision ID: 20261012_scope_review_069
Revises: 20260908_src_eff_068
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012_scope_review_069"
down_revision = "20260908_src_eff_068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_scope_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tender_id", sa.String(36), nullable=False),
        sa.Column("scope_detail_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("correction", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("machine_snapshot", sa.JSON(), nullable=False),
        sa.Column("reviewed_source_fingerprint", sa.String(64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("scope_detail_id", "revision", name="uq_scope_review_revision"),
        sa.CheckConstraint("revision > 0", name="ck_scope_review_revision"),
        sa.CheckConstraint("decision IN ('CONFIRMED', 'CORRECTED', 'REJECTED')", name="ck_scope_review_decision"),
        sa.CheckConstraint(
            "(decision = 'CORRECTED' AND correction IS NOT NULL AND "
            "jsonb_typeof(correction::jsonb) = 'object' AND "
            "correction::jsonb ? 'description' AND "
            "jsonb_typeof(correction::jsonb -> 'description') = 'string' AND "
            "length(trim(correction::jsonb ->> 'description')) > 0 AND "
            "(correction::jsonb - 'description') = '{}'::jsonb) OR "
            "(decision != 'CORRECTED' AND correction IS NULL)",
            name="ck_scope_review_correction",
        ),
    )
    op.create_index("ix_scope_review_tender", "tender_scope_reviews", ["tender_id"])
    op.execute("""
        CREATE FUNCTION validate_scope_review_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE source_tender_id text;
        BEGIN
            SELECT tender_id INTO source_tender_id FROM tender_scope_details
                WHERE id = NEW.scope_detail_id FOR KEY SHARE;
            IF source_tender_id IS NULL OR source_tender_id <> NEW.tender_id
                OR (NEW.machine_snapshot ->> 'id') IS DISTINCT FROM NEW.scope_detail_id
                OR (NEW.machine_snapshot ->> 'tender_id') IS DISTINCT FROM NEW.tender_id THEN
                RAISE EXCEPTION 'Scope review identity does not match current machine evidence'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER scope_review_identity BEFORE INSERT ON tender_scope_reviews
        FOR EACH ROW EXECUTE FUNCTION validate_scope_review_identity()
    """)
    op.execute("""
        CREATE FUNCTION prevent_scope_review_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Scope review history is append-only' USING ERRCODE = '23514';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER scope_review_append_only BEFORE UPDATE OR DELETE ON tender_scope_reviews
        FOR EACH ROW EXECUTE FUNCTION prevent_scope_review_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS scope_review_identity ON tender_scope_reviews")
    op.execute("DROP FUNCTION IF EXISTS validate_scope_review_identity()")
    op.execute("DROP TRIGGER scope_review_append_only ON tender_scope_reviews")
    op.execute("DROP FUNCTION prevent_scope_review_mutation()")
    op.drop_index("ix_scope_review_tender", table_name="tender_scope_reviews")
    op.drop_table("tender_scope_reviews")
    # Also cleans up the pre-acceptance RESTRICT implementation if installed.
    op.execute("ALTER TABLE tender_scope_details DROP CONSTRAINT IF EXISTS uq_scope_detail_id_tender")
