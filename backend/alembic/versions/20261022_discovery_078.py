"""Generic Discovery persistence; schema documented first in ADR0032."""
from alembic import op
import sqlalchemy as sa
revision='20261022_discovery_078'
down_revision='20261022_composition_077'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('discovery_sources',sa.Column('id',sa.String(32),primary_key=True),sa.Column('name',sa.String(160),nullable=False),sa.Column('base_url',sa.String(500),nullable=False),sa.Column('adapter_version',sa.String(40),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('configuration',sa.JSON(),nullable=False),sa.Column('last_scan_state',sa.String(16)),sa.Column('last_successful_scan',sa.DateTime(timezone=True)),sa.Column('last_error',sa.String(500)))
    op.create_table('discovery_profiles',sa.Column('id',sa.String(36),primary_key=True),sa.Column('name',sa.String(160),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('configuration',sa.JSON(),nullable=False),sa.CheckConstraint('revision > 0',name='ck_discovery_profile_revision'))
    op.create_table('discovery_opportunities',sa.Column('id',sa.String(36),primary_key=True),sa.Column('source_id',sa.String(32),sa.ForeignKey('discovery_sources.id',ondelete='RESTRICT'),nullable=False),sa.Column('external_id',sa.String(200),nullable=False),sa.Column('business_area',sa.String(120),nullable=False),sa.Column('published_date',sa.Date()),sa.Column('representation',sa.JSON(),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('previous_fingerprint',sa.String(64)),sa.Column('first_seen',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen',sa.DateTime(timezone=True),nullable=False),sa.Column('last_changed',sa.DateTime(timezone=True)),sa.Column('internal_state',sa.String(16),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.UniqueConstraint('source_id','external_id',name='uq_discovery_identity'),sa.CheckConstraint("internal_state IN ('NEW','REVIEW','FOLLOWING','DISCARDED')",name='ck_discovery_internal_state'))
    op.create_table('discovery_scan_runs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('source_id',sa.String(32),sa.ForeignKey('discovery_sources.id',ondelete='RESTRICT'),nullable=False),sa.Column('request_id',sa.String(36),nullable=False),sa.Column('request_sha256',sa.String(64),nullable=False),sa.Column('query',sa.JSON(),nullable=False),sa.Column('adapter_version',sa.String(40),nullable=False),sa.Column('status',sa.String(16),nullable=False),sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('finished_at',sa.DateTime(timezone=True)),sa.Column('metrics',sa.JSON(),nullable=False),sa.UniqueConstraint('source_id','request_id',name='uq_discovery_scan_request'),sa.CheckConstraint("status IN ('RUNNING','SUCCESS','PARTIAL','FAILED')",name='ck_discovery_scan_state'))
    op.create_table('discovery_source_documents',sa.Column('id',sa.String(36),primary_key=True),sa.Column('opportunity_id',sa.String(36),sa.ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),nullable=False),sa.Column('external_id',sa.String(500),nullable=False),sa.Column('name',sa.String(500),nullable=False),sa.Column('public_url',sa.String(2000),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('opportunity_id','external_id',name='uq_discovery_document'))
    op.create_index('ix_discovery_source_date','discovery_opportunities',['source_id', 'published_date'])
    op.create_index('ix_discovery_workflow','discovery_opportunities',['internal_state'])
    op.create_index('ix_discovery_scan_source_time','discovery_scan_runs',['source_id', 'started_at'])
    op.create_index('ix_discovery_source_documents_opportunity_id','discovery_source_documents',['opportunity_id'])

def downgrade():
    # Explicit destructive downgrade removes Discovery only; previous domains untouched.
    op.drop_table('discovery_source_documents')
    op.drop_table('discovery_scan_runs')
    op.drop_table('discovery_opportunities')
    op.drop_table('discovery_profiles')
    op.drop_table('discovery_sources')
