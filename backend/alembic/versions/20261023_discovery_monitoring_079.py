"""Generic Discovery monitoring/handoff; schema first in ADR0034."""
from alembic import op
import sqlalchemy as sa
revision='20261023_discovery_079'
down_revision='20261022_discovery_078'
branch_labels=None
depends_on=None

def upgrade():
    op.drop_constraint('ck_discovery_internal_state','discovery_opportunities',type_='check')
    op.create_check_constraint('ck_discovery_internal_state','discovery_opportunities',"internal_state IN ('NEW','REVIEW','FOLLOWING','DISCARDED','IMPORTED')")
    op.add_column('discovery_opportunities',sa.Column('watching',sa.Boolean(),nullable=False,server_default='false'))
    op.execute("UPDATE discovery_opportunities SET watching=true WHERE internal_state='FOLLOWING'")
    op.add_column('discovery_opportunities',sa.Column('last_scan_id',sa.String(36),sa.ForeignKey('discovery_scan_runs.id',ondelete='SET NULL')))
    op.create_index('ix_discovery_opportunities_last_scan_id','discovery_opportunities',['last_scan_id'])
    op.add_column('discovery_source_documents',sa.Column('active',sa.Boolean(),nullable=False,server_default='true'))
    op.add_column('discovery_source_documents',sa.Column('last_scan_id',sa.String(36),sa.ForeignKey('discovery_scan_runs.id',ondelete='SET NULL')))
    op.create_index('ix_discovery_source_documents_last_scan_id','discovery_source_documents',['last_scan_id'])
    op.execute("""UPDATE discovery_source_documents d SET active=EXISTS (
      SELECT 1 FROM discovery_opportunities o, json_array_elements(COALESCE(o.representation->'documents','[]'::json)) j
      WHERE o.id=d.opportunity_id AND j->>'external_id'=d.external_id)""")
    op.create_table('discovery_changes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('event_key',sa.String(64),nullable=False,unique=True),
        sa.Column('opportunity_id',sa.String(36),sa.ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),nullable=False),
        sa.Column('source_id',sa.String(32),sa.ForeignKey('discovery_sources.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('scan_run_id',sa.String(36),sa.ForeignKey('discovery_scan_runs.id',ondelete='SET NULL')),
        sa.Column('category',sa.String(40),nullable=False),sa.Column('origin',sa.String(10),nullable=False),sa.Column('detected_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('previous_fingerprint',sa.String(64)),sa.Column('current_fingerprint',sa.String(64)),sa.Column('changed_fields',sa.JSON(),nullable=False),
        sa.Column('summary',sa.String(2000),nullable=False),sa.Column('actor',sa.String(160)),sa.Column('acknowledged_at',sa.DateTime(timezone=True)))
    op.create_index('ix_discovery_change_parent_time','discovery_changes',['opportunity_id','detected_at'])
    op.create_index('ix_discovery_change_unread','discovery_changes',['opportunity_id','acknowledged_at'])
    op.create_table('discovery_coverage',sa.Column('scope_sha',sa.String(64),primary_key=True),
        sa.Column('opportunity_id',sa.String(36),sa.ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('present',sa.Boolean(),nullable=False),sa.Column('last_scan_id',sa.String(36),sa.ForeignKey('discovery_scan_runs.id',ondelete='RESTRICT'),nullable=False))
    op.create_table('discovery_tender_links',sa.Column('opportunity_id',sa.String(36),sa.ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('tender_id',sa.String(36),sa.ForeignKey('tenders.id',ondelete='SET NULL'),unique=True),sa.Column('tender_identity',sa.String(36),nullable=False,unique=True),
        sa.Column('context',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('discovery_import_receipts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('opportunity_id',sa.String(36),sa.ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),nullable=False),
        sa.Column('source_document_id',sa.String(36),sa.ForeignKey('discovery_source_documents.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('tender_identity',sa.String(36),nullable=False),sa.Column('tender_document_id',sa.String(36),nullable=False),
        sa.Column('metadata_fingerprint',sa.String(64),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('source_url',sa.String(2000),nullable=False),sa.Column('source_name',sa.String(500),nullable=False),sa.Column('downloaded_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('result',sa.String(32),nullable=False),sa.UniqueConstraint('opportunity_id','source_document_id','metadata_fingerprint','sha256',name='uq_discovery_import_receipt'))
    op.create_index('ix_discovery_import_receipts_opportunity_id','discovery_import_receipts',['opportunity_id'])

def downgrade():
    # Explicit destructive rollback of monitoring only; never remove canonical Tenders/files.
    for name in ['discovery_import_receipts','discovery_tender_links','discovery_coverage','discovery_changes']:op.drop_table(name)
    for table in ['discovery_source_documents','discovery_opportunities']:op.drop_column(table,'last_scan_id')
    op.drop_column('discovery_source_documents','active');op.drop_column('discovery_opportunities','watching')
    op.execute("UPDATE discovery_opportunities SET internal_state='REVIEW' WHERE internal_state='IMPORTED'")
    op.drop_constraint('ck_discovery_internal_state','discovery_opportunities',type_='check')
    op.create_check_constraint('ck_discovery_internal_state','discovery_opportunities',"internal_state IN ('NEW','REVIEW','FOLLOWING','DISCARDED')")
