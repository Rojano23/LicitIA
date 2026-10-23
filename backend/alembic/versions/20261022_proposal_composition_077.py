"""Proposal-owned composition overlay; see ADR0030 documented before migration."""
from alembic import op
import sqlalchemy as sa
revision = '20261022_composition_077'
down_revision = '20261022_proposal_version_076'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proposal_compositions',
        sa.Column('version_id', sa.String(36), sa.ForeignKey('proposal_versions.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('contract_version', sa.String(32), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('revision > 0', name='ck_composition_revision'),
        sa.CheckConstraint("contract_version = 'proposal-composition-v1'", name='ck_composition_contract'))
    op.drop_constraint('ck_proposal_event_action', 'proposal_version_events', type_='check')
    op.create_check_constraint('ck_proposal_event_action', 'proposal_version_events',
        "action IN ('CREATED','CONFIGURED','FROZEN','SUPERSEDED','COMPOSITION_INITIALIZED','COMPOSITION_UPDATED')")
    op.execute("""CREATE FUNCTION proposal_composition_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent proposal_versions%ROWTYPE;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Composition cannot be deleted'; END IF;
      SELECT * INTO parent FROM proposal_versions WHERE id=NEW.version_id;
      PERFORM 1 FROM proposals WHERE id=parent.proposal_id FOR UPDATE;
      SELECT * INTO parent FROM proposal_versions WHERE id=NEW.version_id FOR UPDATE;
      IF parent.id IS NULL OR parent.state <> 'DRAFT' OR EXISTS
         (SELECT 1 FROM proposal_versions WHERE proposal_id=parent.proposal_id AND version>parent.version)
      THEN RAISE EXCEPTION 'Composition requires latest draft'; END IF;
      IF TG_OP = 'INSERT' THEN
        IF NEW.revision <> 1 THEN RAISE EXCEPTION 'Composition starts at revision 1'; END IF;
      ELSE
        IF ROW(NEW.version_id,NEW.contract_version,NEW.created_at) IS DISTINCT FROM
           ROW(OLD.version_id,OLD.contract_version,OLD.created_at) OR
           NEW.revision <> OLD.revision+1 OR NEW.updated_at < OLD.updated_at
        THEN RAISE EXCEPTION 'Composition revision invalid'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER proposal_composition_guard BEFORE INSERT OR UPDATE OR DELETE ON proposal_compositions FOR EACH ROW EXECUTE FUNCTION proposal_composition_guard()')


def downgrade():
    op.drop_table('proposal_compositions')
    op.execute('DROP FUNCTION proposal_composition_guard()')
    # Retain append-only composition events; refuse destructive downgrade if any exist.
    op.drop_constraint('ck_proposal_event_action', 'proposal_version_events', type_='check')
    op.create_check_constraint('ck_proposal_event_action', 'proposal_version_events',
        "action IN ('CREATED','CONFIGURED','FROZEN','SUPERSEDED')")
