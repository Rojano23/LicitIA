"""M8-D immutable versioned proposal-readiness handoff only."""
from alembic import op
import sqlalchemy as sa
revision='20261022_proposal_snapshot_075'
down_revision='20261022_readiness_work_074'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('proposal_readiness_snapshots',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tender_id',sa.String(36),sa.ForeignKey('tenders.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('request_id',sa.String(36),nullable=False),
        sa.Column('request_sha256',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('actor_label',sa.String(200)),
        sa.Column('input_sha256',sa.String(64),nullable=False),
        sa.Column('payload_sha256',sa.String(64),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.UniqueConstraint('tender_id','request_id',name='uq_proposal_snapshot_request'))
    op.create_index('ix_proposal_snapshot_history','proposal_readiness_snapshots',['tender_id','created_at','id'])
    op.execute("""CREATE FUNCTION proposal_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Proposal readiness snapshots are immutable'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER proposal_snapshot_guard BEFORE INSERT OR UPDATE OR DELETE ON proposal_readiness_snapshots FOR EACH ROW EXECUTE FUNCTION proposal_snapshot_guard()')


def downgrade():
    op.drop_table('proposal_readiness_snapshots')
    op.execute('DROP FUNCTION proposal_snapshot_guard()')
