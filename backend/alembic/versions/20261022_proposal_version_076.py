"""M9-A bounded proposal/version/configuration lifecycle, no output artifacts."""
from alembic import op
import sqlalchemy as sa
revision='20261022_proposal_version_076'
down_revision='20261022_proposal_snapshot_075'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('proposals',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tender_id',sa.String(36),sa.ForeignKey('tenders.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('proposal_versions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('proposal_id',sa.String(36),sa.ForeignKey('proposals.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('tender_id',sa.String(36),sa.ForeignKey('tenders.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('snapshot_id',sa.String(36),sa.ForeignKey('proposal_readiness_snapshots.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('snapshot_sha256',sa.String(64),nullable=False),
        sa.Column('previous_version_id',sa.String(36),sa.ForeignKey('proposal_versions.id',ondelete='RESTRICT')),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('edit_revision',sa.Integer(),nullable=False),
        sa.Column('state',sa.String(16),nullable=False),sa.Column('content_contract',sa.String(32),nullable=False),
        sa.Column('configuration',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_origin',sa.String(16),nullable=False),sa.Column('actor_label',sa.String(200)),
        sa.Column('frozen_at',sa.DateTime(timezone=True)),sa.Column('frozen_actor_label',sa.String(200)),
        sa.Column('frozen_sha256',sa.String(64)),sa.Column('freeze_acknowledgements',sa.JSON(none_as_null=True)),
        sa.Column('request_id',sa.String(36),nullable=False),sa.Column('request_sha256',sa.String(64),nullable=False),
        sa.UniqueConstraint('proposal_id','version',name='uq_proposal_version'),
        sa.UniqueConstraint('tender_id','request_id',name='uq_proposal_version_request'),
        sa.CheckConstraint('version > 0 AND edit_revision > 0',name='ck_proposal_version_revision'),
        sa.CheckConstraint("state IN ('DRAFT','FROZEN')",name='ck_proposal_version_state'),
        sa.CheckConstraint("content_contract = 'proposal-builder-v1'",name='ck_proposal_version_contract'),
        sa.CheckConstraint("created_origin IN ('API','WORKSPACE')",name='ck_proposal_version_origin'),
        sa.CheckConstraint("(state = 'DRAFT' AND frozen_at IS NULL AND frozen_sha256 IS NULL AND freeze_acknowledgements IS NULL AND frozen_actor_label IS NULL) OR (state = 'FROZEN' AND frozen_at IS NOT NULL AND frozen_sha256 IS NOT NULL AND freeze_acknowledgements IS NOT NULL)",name='ck_proposal_version_freeze'))
    op.create_index('ix_proposal_version_history','proposal_versions',['tender_id','created_at','id'])
    op.create_table('proposal_version_events',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('version_id',sa.String(36),sa.ForeignKey('proposal_versions.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('action',sa.String(32),nullable=False),
        sa.Column('actor_label',sa.String(200)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('details',sa.JSON(),nullable=False),sa.UniqueConstraint('version_id','sequence',name='uq_proposal_event_sequence'),
        sa.CheckConstraint('sequence > 0',name='ck_proposal_event_sequence'),
        sa.CheckConstraint("action IN ('CREATED','CONFIGURED','FROZEN','SUPERSEDED')",name='ck_proposal_event_action'))
    op.execute("""CREATE FUNCTION proposal_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Proposal identities/events are append-only'; END $$""")
    for table in ['proposals','proposal_version_events']:
        op.execute(f'CREATE TRIGGER proposal_identity_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION proposal_identity_guard()')
    op.execute("""CREATE FUNCTION proposal_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Proposal versions cannot be deleted'; END IF;
      IF NOT EXISTS (SELECT 1 FROM proposals WHERE id=NEW.proposal_id AND tender_id=NEW.tender_id)
         OR NOT EXISTS (SELECT 1 FROM proposal_readiness_snapshots WHERE id=NEW.snapshot_id AND tender_id=NEW.tender_id)
      THEN RAISE EXCEPTION 'Proposal parent mismatch'; END IF;
      IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'DRAFT' OR NEW.edit_revision <> 1 THEN RAISE EXCEPTION 'Proposal starts as draft'; END IF;
        IF (NEW.version = 1 AND NEW.previous_version_id IS NOT NULL) OR
          (NEW.version > 1 AND NOT EXISTS (SELECT 1 FROM proposal_versions WHERE id=NEW.previous_version_id AND proposal_id=NEW.proposal_id AND tender_id=NEW.tender_id AND version=NEW.version-1))
        THEN RAISE EXCEPTION 'Proposal revision chain mismatch'; END IF;
      ELSE
        IF OLD.state = 'FROZEN' THEN RAISE EXCEPTION 'Frozen proposal is immutable'; END IF;
        IF EXISTS (SELECT 1 FROM proposal_versions WHERE proposal_id=OLD.proposal_id AND version>OLD.version)
        THEN RAISE EXCEPTION 'Historical draft is immutable'; END IF;
        IF ROW(NEW.id,NEW.proposal_id,NEW.tender_id,NEW.snapshot_id,NEW.snapshot_sha256,NEW.previous_version_id,NEW.version,NEW.content_contract,NEW.created_at,NEW.created_origin,NEW.actor_label,NEW.request_id,NEW.request_sha256)
           IS DISTINCT FROM ROW(OLD.id,OLD.proposal_id,OLD.tender_id,OLD.snapshot_id,OLD.snapshot_sha256,OLD.previous_version_id,OLD.version,OLD.content_contract,OLD.created_at,OLD.created_origin,OLD.actor_label,OLD.request_id,OLD.request_sha256)
        THEN RAISE EXCEPTION 'Proposal binding is immutable'; END IF;
        IF NEW.edit_revision <> OLD.edit_revision+1 OR NEW.updated_at < OLD.updated_at THEN RAISE EXCEPTION 'Proposal revision invalid'; END IF;
        IF NEW.state = 'FROZEN' AND NEW.configuration::jsonb IS DISTINCT FROM OLD.configuration::jsonb
        THEN RAISE EXCEPTION 'Freeze cannot change configuration'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER proposal_version_guard BEFORE INSERT OR UPDATE OR DELETE ON proposal_versions FOR EACH ROW EXECUTE FUNCTION proposal_version_guard()')


def downgrade():
    op.drop_table('proposal_version_events');op.drop_table('proposal_versions');op.drop_table('proposals')
    op.execute('DROP FUNCTION proposal_version_guard()');op.execute('DROP FUNCTION proposal_identity_guard()')
