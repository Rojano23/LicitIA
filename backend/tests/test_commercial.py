"""M7A01–20 synthetic commercial contracts; never blind fixtures."""
from decimal import Decimal, localcontext
import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.commercial_calculations import CommercialInputs, calculate, aggregate_currency_totals
from app.models import CommercialLine, TenderScopeDetail, TenderScopeQuantity
from tests.test_workspace_flow import scene, upload, process


def values(**kw):
    return CommercialInputs(currency='MXN', **kw)


@pytest.mark.parametrize('basis,target', [('MARKUP','25'),('MARGIN','20')])
def test_m7a06_09_formulas(basis,target):
    v = values(unit_cost='100', calculation_mode='COST_FIRST', calculation_basis=basis,
               **{'markup_percent' if basis == 'MARKUP' else 'target_margin_percent':target})
    assert calculate(v, Decimal(2))['recommended_unit_price'] == '125.000000'
    assert calculate(v, Decimal(2))['offered_total'] is None
    actual = calculate(values(unit_cost='100',offered_unit_price='125'),Decimal(2))
    assert (actual['actual_markup_percent'],actual['actual_margin_percent'],actual['profit']) == ('25.00000000','20.00000000','50.00')


def test_m7a10_rounding():
    with localcontext() as ctx:
        ctx.prec = 4
        result = calculate(values(unit_cost='0.1',offered_unit_price='0.335'),Decimal(3))
    assert (result['offered_total'],result['total_cost'],result['profit']) == ('1.01','0.30','0.71')


@pytest.mark.parametrize('bad',[0.1,True,'NaN','Infinity','1.0000001','1000000000000000000'])
def test_unsafe_decimal(bad):
    with pytest.raises(ValidationError):
        values(unit_cost=bad)


def test_m7a11_13_zero_missing():
    r = calculate(values(unit_cost='0',offered_unit_price='2'),Decimal(1))
    assert r['actual_markup_percent'] is None and r['actual_margin_percent'] == '100.00000000'
    assert calculate(values(unit_cost='2',offered_unit_price='0'),Decimal(1))['actual_margin_percent'] is None
    r = calculate(values(offered_unit_price='12'),None)
    assert r['actual_margin_percent'] is None and r['total_cost'] is None and r['offered_total'] is None
    assert calculate(values(offered_unit_price='12'),Decimal(2))['offered_total'] == '24.00'


def test_m7a15_17_warnings_currency():
    r = calculate(values(unit_cost='10',offered_unit_price='9'),Decimal(2))
    assert r['profit'] == '-2.00' and 'PRICE_BELOW_COST' in r['warnings']
    missing = calculate(CommercialInputs(offered_unit_price='9'),Decimal(2))
    assert 'MISSING_CURRENCY' in missing['warnings'] and missing['offered_total'] is None
    usd = calculate(CommercialInputs(currency='USD',offered_unit_price='9'),Decimal(2))
    assert aggregate_currency_totals([r,usd])['offered_total'] is None
    assert aggregate_currency_totals([r,r])['offered_total'] == '36.00'


@pytest.mark.parametrize('basis,target,warning',[('MARGIN','100','INVALID_MARGIN'),('MARGIN','120','INVALID_MARGIN'),('MARKUP','-101','INVALID_MARKUP')])
def test_invalid_target_warning(basis,target,warning):
    r = calculate(values(unit_cost='10',calculation_mode='COST_FIRST',calculation_basis=basis,
                  **{'markup_percent' if basis == 'MARKUP' else 'target_margin_percent':target}),Decimal(1))
    assert r['recommended_unit_price'] is None and warning in r['warnings']


@pytest.fixture
def commercial(scene):
    client,tender,db = scene
    document = upload(client,tender)
    scopes = process(client,tender)['scopes']
    route = f"/tenders/{tender}/scopes/{scopes[0]['scope_detail_id']}/commercial-line"
    return client,tender,db,document,scopes,route


def create(c,r,**kw):
    response = c.post(r,json={'currency':'MXN','unit_cost':'100','offered_unit_price':'125',**kw})
    assert response.status_code == 201,response.text
    return response.json()


def guard(row):
    return {'expected_revision':row['revision'],'expected_source_fingerprint':row['source_fingerprint']}


def test_m7a01_02_18_20_canonical_audit(commercial):
    c,t,db,doc,scopes,r = commercial
    before = c.get(f'/tenders/{t}/workspace').json()['scopes']
    row = create(c,r,input_origin='UI',actor_label='Operador local')
    q = scopes[0]['quantities'][0]
    assert row['scope_detail_id'] == q['scope_detail_id'] and row['source']['selected_quantity_id'] == q['id']
    assert Decimal(row['summary']['offered_total']) == Decimal(q['quantity_value']) * 125
    assert row['history'][0]['inputs']['input_origin'] == 'UI'
    assert row['price_method'] == 'MANUAL' and row['price_value_origin'] == 'MANUAL_INPUT'
    assert row['created_at'] and row['updated_at']
    assert c.get(f'/tenders/{t}/workspace').json()['scopes'] == before
    assert c.get(r+'/summary').json() == row


def test_m7a03_parent(commercial):
    c,_,_,_,scopes,r = commercial
    assert c.post(r,json={'quantity_id':scopes[1]['quantities'][0]['id']}).status_code == 409


@pytest.mark.parametrize('source',['SUPPLIER_QUOTE','INTERNAL_COST','MANUFACTURER_COST','HISTORICAL_REFERENCE','ESTIMATE','MANUAL','NOT_APPLICABLE'])
def test_m7a04_05_no_mandatory_quote(commercial,source):
    c,_,_,_,_,r = commercial
    assert create(c,r,cost_source_type=source)['inputs']['quote_document_id'] is None


def test_shared_quote_and_foreign_tender(commercial):
    c,_,_,doc,scopes,r = commercial
    row = create(c,r,quote_document_id=doc)
    create(c,r.replace(scopes[0]['scope_detail_id'],scopes[1]['scope_detail_id']),quote_document_id=doc)
    t2 = c.post('/tenders',json={'title':'other'}).json()['id']
    otherdoc = upload(c,t2)
    assert c.patch(r,json={**guard(row),'quote_document_id':otherdoc}).status_code == 409


def test_m7a14_19_override_revision_idempotency(commercial):
    c,_,db,_,_,r = commercial
    row = create(c,r,calculation_mode='COST_FIRST',calculation_basis='MARKUP',markup_percent='25')
    changed = c.patch(r,json={**guard(row),'markup_percent':'40'}).json()
    assert Decimal(changed['inputs']['offered_unit_price']) == 125
    assert changed['summary']['recommended_unit_price'] == '140.000000'
    assert c.patch(r,json={**guard(changed),'markup_percent':'40'}).json()['revision'] == changed['revision']
    assert c.post(r,json={}).status_code == 409
    assert c.patch(r,json={**guard(row),'notes':'stale'}).status_code == 409
    assert c.post(r+'/calculate',json={**guard(changed),'apply_calculated_price':True}).status_code == 409
    assert c.post(r+'/calculate',json=guard(changed)).json()['revision'] == changed['revision']
    applied = c.post(r+'/calculate',json={**guard(changed),'apply_calculated_price':True,'replace_manual_price':True}).json()
    assert applied['price_method'] == 'CALCULATED' and applied['price_value_origin'] == 'SYSTEM_ESTIMATE'
    assert Decimal(applied['inputs']['offered_unit_price']) == 140
    assert len(list(db.scalars(select(CommercialLine)))) == 1 and len(applied['history']) == 3


def test_quantity_deleted_stale_context(commercial):
    c,_,db,_,scopes,r = commercial
    q = db.get(TenderScopeQuantity,scopes[0]['quantities'][0]['id'])
    row = create(c,r,quantity_id=q.id)
    db.delete(q); db.flush()
    read = c.get(r).json()
    assert read['summary']['offered_total'] is None and 'QUANTITY_SELECTION_STALE' in read['summary']['warnings']
    assert 'SOURCE_CONTEXT_CHANGED' in read['summary']['warnings']
    assert c.patch(r,json={**guard(row),'notes':'oldsource'}).status_code == 409


def test_scope_deleted_preserves_history(commercial):
    c,_,db,_,scopes,r = commercial
    row = create(c,r)
    db.delete(db.get(TenderScopeDetail,scopes[0]['scope_detail_id'])); db.flush(); db.expire_all()
    read = c.get(r).json()
    assert read['scope_detail_id'] is None and read['id'] == row['id']
    assert read['summary']['offered_total'] is None and read['history'] == row['history']
    assert c.patch(r,json={**guard(read),'notes':'removed'}).status_code == 409


def test_db_audit_guard(commercial):
    c,_,db,_,_,r = commercial
    create(c,r)
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.execute(text("UPDATE commercial_line_revisions SET notes = 'tampered'"))


def test_migration_downgrade_upgrade_transactional():
    """DDL round trip rolls back; never downgrades a frozen/customer database."""
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.database import engine
    spec = importlib.util.spec_from_file_location('commercial_migration', Path(__file__).parents[1] / 'alembic/versions/20261021_commercial_073.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text('SELECT count(*) FROM commercial_lines')) == 0
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert connection.scalar(text("SELECT to_regclass('commercial_lines')")) is None
                migration.upgrade()
                assert connection.scalar(text("SELECT to_regclass('commercial_lines')")) is not None
        finally:
            transaction.rollback()


def test_negative_missing_currency_draft_saveable(commercial):
    c,_,_,_,_,r = commercial
    row = create(c,r,currency=None,unit_cost='-10',offered_unit_price='-12')
    assert row['summary']['status'] == 'INCOMPLETE' and Decimal(row['inputs']['unit_cost']) == -10
    assert {'MISSING_CURRENCY','NEGATIVE_VALUE'} <= set(row['summary']['warnings'])
    assert c.patch(r,json={**guard(row),'unit_cost':0.1}).status_code == 422
    assert c.patch(r,json={**guard(row),'unit_cost':'nonsense'}).status_code == 422


def test_calculated_rule_change_keeps_chosen_price(commercial):
    c,_,_,_,_,r = commercial
    row = create(c,r,offered_unit_price=None,calculation_mode='COST_FIRST',calculation_basis='MARKUP',markup_percent='25')
    row = c.post(r+'/calculate',json={**guard(row),'apply_calculated_price':True}).json()
    changed = c.patch(r,json={**guard(row),'markup_percent':'60'}).json()
    assert Decimal(changed['inputs']['offered_unit_price']) == 125
    assert changed['summary']['recommended_unit_price'] == '160.000000'
    assert 'PRICE_CALCULATION_STALE' in changed['summary']['warnings']


def test_ambiguous_quantity_requires_selection(commercial):
    from uuid import uuid4
    c,_,db,_,scopes,r = commercial
    first = db.get(TenderScopeQuantity,scopes[0]['quantities'][0]['id'])
    data = {col.name:getattr(first,col.name) for col in TenderScopeQuantity.__table__.columns if col.name not in ('id','semantic_fingerprint')}
    db.add(TenderScopeQuantity(id=str(uuid4()),semantic_fingerprint='f'*64,**data)); db.flush()
    row = create(c,r)
    assert row['summary']['offered_total'] is None and 'QUANTITY_AMBIGUOUS' in row['summary']['warnings']
    chosen = c.patch(r,json={**guard(row),'quantity_id':first.id}).json()
    assert chosen['summary']['offered_total'] is not None


def test_nonexact_quantity_never_total(commercial):
    c,_,db,_,scopes,r = commercial
    q = db.get(TenderScopeQuantity,scopes[0]['quantities'][0]['id'])
    q.relation = 'MINIMUM'; db.flush()
    row = create(c,r)
    assert row['summary']['offered_total'] is None


def test_quote_database_guard(commercial):
    from app.models import CommercialLineRevision
    c,_,db,_,_,r = commercial
    create(c,r)
    t = c.post('/tenders',json={'title':'other'}).json()['id']
    doc = upload(c,t)
    original = db.scalar(select(CommercialLineRevision))
    data = {col.name:getattr(original,col.name) for col in CommercialLineRevision.__table__.columns if col.name != 'id'}
    data.update(revision=2,quote_document_id=doc)
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.add(CommercialLineRevision(**data)); db.flush()


def test_calculation_ignores_ambient_inexact_trap():
    from decimal import Inexact
    v = values(unit_cost='100',calculation_mode='COST_FIRST',calculation_basis='MARGIN',target_margin_percent='23')
    with localcontext() as ctx:
        ctx.traps[Inexact] = True
        assert calculate(v,Decimal(3))['recommended_unit_price'] == '129.870130'
