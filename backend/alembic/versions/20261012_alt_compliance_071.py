"""Immutable alternative Scope compliance snapshots and human assessments."""
from alembic import op
import sqlalchemy as sa

revision = '20261012_alt_compliance_071'
down_revision = '20261012_technical_alt_070'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('alternative_scope_compliance_evaluations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tender_id', sa.String(36), nullable=False),
        sa.Column('alternative_id', sa.String(36), nullable=False),
        sa.Column('alternative_revision_id', sa.String(36), nullable=False),
        sa.Column('alternative_revision', sa.Integer(), nullable=False),
        sa.Column('alternative_fingerprint', sa.String(64), nullable=False),
        sa.Column('scope_snapshot_fingerprint', sa.String(64), nullable=False),
        sa.Column('scope_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['alternative_id', 'tender_id'], ['technical_alternatives.id', 'technical_alternatives.tender_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['alternative_revision_id'], ['technical_alternative_revisions.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('id', 'tender_id', 'alternative_id', name='uq_alt_compliance_eval_identity'),
        sa.UniqueConstraint('alternative_id', 'alternative_revision', 'alternative_fingerprint', 'scope_snapshot_fingerprint', name='uq_alt_compliance_eval_snapshot'),
        sa.CheckConstraint('alternative_revision > 0', name='ck_alt_compliance_eval_revision'),
        sa.CheckConstraint("alternative_fingerprint ~ '^[0-9a-f]{64}$' AND scope_snapshot_fingerprint ~ '^[0-9a-f]{64}$'", name='ck_alt_compliance_eval_fingerprints'),
    )
    op.create_index('ix_alt_compliance_eval_tender_alt', 'alternative_scope_compliance_evaluations', ['tender_id', 'alternative_id'])
    op.create_table('alternative_scope_compliance_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evaluation_id', sa.String(36), nullable=False),
        sa.Column('tender_id', sa.String(36), nullable=False),
        sa.Column('alternative_id', sa.String(36), nullable=False),
        sa.Column('item_key', sa.String(36), nullable=False),
        sa.Column('scope_detail_id', sa.String(36), nullable=False),
        sa.Column('item_index', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['evaluation_id', 'tender_id', 'alternative_id'], ['alternative_scope_compliance_evaluations.id', 'alternative_scope_compliance_evaluations.tender_id', 'alternative_scope_compliance_evaluations.alternative_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('evaluation_id', 'item_key', name='uq_alt_compliance_item_key'),
        sa.UniqueConstraint('evaluation_id', 'item_index', name='uq_alt_compliance_item_index'),
        sa.UniqueConstraint('id', 'evaluation_id', 'tender_id', 'alternative_id', name='uq_alt_compliance_item_identity'),
        sa.CheckConstraint('item_index >= 0', name='ck_alt_compliance_item_index'),
        sa.CheckConstraint("item_key = scope_detail_id AND (snapshot ->> 'scope_detail_id') IS NOT DISTINCT FROM scope_detail_id AND (snapshot -> 'machine' ->> 'tender_id') IS NOT DISTINCT FROM tender_id", name='ck_alt_compliance_item_snapshot_identity'),
    )
    op.create_table('alternative_scope_compliance_decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('item_id', sa.String(36), nullable=False),
        sa.Column('evaluation_id', sa.String(36), nullable=False),
        sa.Column('tender_id', sa.String(36), nullable=False),
        sa.Column('alternative_id', sa.String(36), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('evidence_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['item_id', 'evaluation_id', 'tender_id', 'alternative_id'], ['alternative_scope_compliance_items.id', 'alternative_scope_compliance_items.evaluation_id', 'alternative_scope_compliance_items.tender_id', 'alternative_scope_compliance_items.alternative_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('item_id', 'revision', name='uq_alt_compliance_decision_revision'),
        sa.CheckConstraint('revision > 0', name='ck_alt_compliance_decision_revision'),
        sa.CheckConstraint("status IN ('COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'REVIEW_REQUIRED', 'NOT_EVALUATED')", name='ck_alt_compliance_decision_status'),
        sa.CheckConstraint('length(trim(rationale)) > 0', name='ck_alt_compliance_decision_rationale'),
    )
    op.execute("""
        CREATE FUNCTION validate_alt_compliance_binding() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM technical_alternative_revisions r
                WHERE r.id = NEW.alternative_revision_id AND r.alternative_id = NEW.alternative_id
                  AND r.tender_id = NEW.tender_id AND r.revision = NEW.alternative_revision
                  AND r.fingerprint = NEW.alternative_fingerprint)
               OR (NEW.scope_snapshot ->> 'tender_id') IS DISTINCT FROM NEW.tender_id
               OR (NEW.scope_snapshot ->> 'fingerprint') IS DISTINCT FROM NEW.scope_snapshot_fingerprint THEN
                RAISE EXCEPTION 'Alternative compliance binding mismatch' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute('CREATE TRIGGER alt_compliance_binding BEFORE INSERT ON alternative_scope_compliance_evaluations FOR EACH ROW EXECUTE FUNCTION validate_alt_compliance_binding()')
    op.execute("""
        CREATE FUNCTION validate_alt_compliance_item() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM (
                    SELECT element, row_number() OVER (ORDER BY ordinality) - 1 AS item_index
                    FROM alternative_scope_compliance_evaluations e,
                         jsonb_array_elements(e.scope_snapshot::jsonb -> 'items') WITH ORDINALITY AS scope(element, ordinality)
                    WHERE e.id = NEW.evaluation_id
                      AND ((element ->> 'accepted_execution_scope')::boolean
                           OR (element ->> 'unresolved')::boolean)
                ) frozen WHERE frozen.element = NEW.snapshot::jsonb AND frozen.item_index = NEW.item_index
            ) THEN
                RAISE EXCEPTION 'Item does not match frozen evaluable Scope' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$
    """)
    op.execute('CREATE TRIGGER alt_compliance_item_binding BEFORE INSERT ON alternative_scope_compliance_items FOR EACH ROW EXECUTE FUNCTION validate_alt_compliance_item()')
    op.execute("""
        CREATE FUNCTION prevent_alt_compliance_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Alternative compliance audit is append-only' USING ERRCODE = '23514';
        END; $$
    """)
    for table in ('alternative_scope_compliance_evaluations', 'alternative_scope_compliance_items', 'alternative_scope_compliance_decisions'):
        op.execute(f'CREATE TRIGGER alt_compliance_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_alt_compliance_mutation()')


def downgrade() -> None:
    op.drop_table('alternative_scope_compliance_decisions')
    op.drop_table('alternative_scope_compliance_items')
    op.drop_table('alternative_scope_compliance_evaluations')
    op.execute('DROP FUNCTION prevent_alt_compliance_mutation()')
    op.execute('DROP FUNCTION validate_alt_compliance_binding()')
    # Also permits removing the earlier local, pre-review 071 test installation.
    op.execute('DROP FUNCTION IF EXISTS validate_alt_compliance_item()')
