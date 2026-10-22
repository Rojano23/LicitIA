"""M8-B append-only readiness human workflow, no canonical issue copies."""
from alembic import op
import sqlalchemy as sa
revision='20261022_readiness_work_074'
down_revision='20261021_commercial_073'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('readiness_work_decisions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tender_id',sa.String(36),sa.ForeignKey('tenders.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('issue_id',sa.String(36),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('dimension',sa.String(32),nullable=False),sa.Column('entity_type',sa.String(64),nullable=False),
        sa.Column('entity_id',sa.String(512),nullable=False),sa.Column('issue_code',sa.String(128),nullable=False),
        sa.Column('context_sha256',sa.String(64),nullable=False),sa.Column('workflow_status',sa.String(32),nullable=False),
        sa.Column('note',sa.Text()),sa.Column('owner',sa.String(200)),sa.Column('actor_label',sa.String(200)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('tender_id','issue_id','revision',name='uq_readiness_work_revision'),
        sa.CheckConstraint('revision > 0',name='ck_readiness_work_revision'),
        sa.CheckConstraint("workflow_status IN ('OPEN','IN_REVIEW','RESOLVED','ACCEPTED_RISK','NOT_APPLICABLE')",name='ck_readiness_work_status'))
    op.create_index('ix_readiness_work_tender_issue','readiness_work_decisions',['tender_id','issue_id'])
    op.execute("""CREATE FUNCTION readiness_work_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Readiness work decisions are append-only'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER readiness_work_guard BEFORE INSERT OR UPDATE OR DELETE ON readiness_work_decisions FOR EACH ROW EXECUTE FUNCTION readiness_work_guard()')


def downgrade():
    op.drop_table('readiness_work_decisions')
    op.execute('DROP FUNCTION readiness_work_guard()')
