"""M7-A commercial identity and immutable decision revisions.

Only additive tables. Downgrade deliberately removes commercial audit data;
never run it against frozen validation databases.
"""
from alembic import op
import sqlalchemy as sa

revision = '20261021_commercial_073'
down_revision = '20261013_req_perception_prov_072'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('commercial_lines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tender_id', sa.String(36), sa.ForeignKey('tenders.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('scope_detail_id', sa.String(36), sa.ForeignKey('tender_scope_details.id', ondelete='SET NULL')),
        sa.Column('scope_id_at_creation', sa.String(36), nullable=False),
        sa.Column('scope_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('tender_id', 'scope_id_at_creation', name='uq_commercial_scope'),
        sa.UniqueConstraint('id', 'tender_id', name='uq_commercial_line_tender'),
        sa.CheckConstraint('scope_detail_id IS NULL OR scope_detail_id = scope_id_at_creation', name='ck_commercial_scope_identity'))
    columns = [sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('line_id', sa.String(36), nullable=False), sa.Column('tender_id', sa.String(36), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False)]
    for name, size, required in [('cost_source_type',32,True), ('cost_value_origin',32,True),
            ('reference_party_name',300,False), ('reference_party_reference',300,False),
            ('currency',3,False), ('calculation_mode',16,True), ('calculation_basis',16,False),
            ('quantity_id',36,False), ('price_method',16,False), ('price_value_origin',32,False),
            ('input_origin',16,True), ('actor_label',200,False), ('action',32,True),
            ('source_fingerprint',64,True), ('calculation_version',32,True)]:
        columns.append(sa.Column(name, sa.String(size), nullable=not required))
    for name in ['reference_party_note', 'quote_reference', 'notes']:
        columns.append(sa.Column(name, sa.Text()))
    for name in ['unit_cost', 'offered_unit_price']:
        columns.append(sa.Column(name, sa.Numeric(24,6)))
    for name in ['markup_percent', 'target_margin_percent']:
        columns.append(sa.Column(name, sa.Numeric(18,8)))
    for name in ['source_snapshot', 'calculation_snapshot']:
        columns.append(sa.Column(name, sa.JSON(), nullable=False))
    op.create_table('commercial_line_revisions', *columns,
        sa.Column('quote_document_id', sa.String(36), sa.ForeignKey('tender_documents.id', ondelete='RESTRICT')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['line_id','tender_id'], ['commercial_lines.id','commercial_lines.tender_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('line_id','revision', name='uq_commercial_revision'),
        sa.CheckConstraint('revision > 0', name='ck_commercial_revision_positive'))
    # Identity is stable, except canonical source deletion may null the live FK.
    op.execute("""CREATE FUNCTION commercial_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Commercial identity is audited'; END IF;
      IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'scope_detail_id') IS DISTINCT FROM (to_jsonb(OLD) - 'scope_detail_id')
           OR NOT (NEW.scope_detail_id IS NULL AND OLD.scope_detail_id IS NOT NULL) THEN
          RAISE EXCEPTION 'Commercial identity is immutable';
        END IF;
      ELSE
        PERFORM id FROM tender_scope_details WHERE id = NEW.scope_detail_id AND tender_id = NEW.tender_id FOR KEY SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Commercial Scope ownership mismatch'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("CREATE TRIGGER commercial_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON commercial_lines FOR EACH ROW EXECUTE FUNCTION commercial_identity_guard()")
    op.execute("""CREATE FUNCTION commercial_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Commercial revisions are immutable'; END IF;
      IF NEW.quote_document_id IS NOT NULL THEN
        PERFORM id FROM tender_documents WHERE id = NEW.quote_document_id AND tender_id = NEW.tender_id FOR KEY SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Quote Tender ownership mismatch'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("CREATE TRIGGER commercial_revision_guard BEFORE INSERT OR UPDATE OR DELETE ON commercial_line_revisions FOR EACH ROW EXECUTE FUNCTION commercial_revision_guard()")


def downgrade():
    op.drop_table('commercial_line_revisions')
    op.drop_table('commercial_lines')
    op.execute('DROP FUNCTION commercial_revision_guard()')
    op.execute('DROP FUNCTION commercial_identity_guard()')
