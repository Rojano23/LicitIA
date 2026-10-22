"""M7-B synthetic current-schema API contracts, no blind material."""
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models import CommercialLine, CommercialLineRevision
from tests.test_workspace_flow import scene, upload, process


@pytest.fixture
def sheet(scene):
    client,tender,db = scene
    upload(client,tender); process(client,tender)
    route=f'/tenders/{tender}/commercial-matrix'
    return client,tender,db,route


def matrix(c,r):
    response=c.get(r)
    assert response.status_code==200,response.text
    return response.json()


def target(row):
    return {'scope_id':row['scope_id'],'expected_revision':row['revision'],'expected_source_fingerprint':row['source_fingerprint']}


def bulk(c,r,rows,action='PATCH',changes=None,**kwargs):
    payload={'targets':[target(row) for row in rows], 'action':action,'changes':changes or {},**kwargs}
    response=c.post(r+'/bulk',json=payload)
    assert response.status_code==200,response.text
    return response.json()


def test_m7b01_03_16_24_virtual_rows_owner_and_pure_reads(sheet):
    c,t,db,r=sheet
    before=c.get(f'/tenders/{t}/workspace').json()['scopes']
    data=matrix(c,r)
    assert len(data['rows'])==2 and not list(db.scalars(select(CommercialLine)))
    for row in data['rows']:
        assert not row['initialized'] and row['summary']['status']=='INCOMPLETE'
        q=row['source']['quantities'][0]
        assert q['scope_detail_id']==row['scope_id'] and q['tender_id']==t
        assert row['source']['selected_quantity_id']==q['id']
    assert matrix(c,r)==data
    assert c.get(f'/tenders/{t}/workspace').json()['scopes']==before


def test_m7b04_05_13_14_18_20_defaults_and_audit(sheet):
    c,t,db,r=sheet
    rows=matrix(c,r)['rows']
    preview=bulk(c,r,rows,changes={'cost_source_type':'MANUFACTURER_COST'},defaults={'currency':'MXN','calculation_mode':'COST_FIRST','calculation_basis':'MARKUP','markup_percent':'25'},input_origin='UI')
    assert preview['counts']=={'ELIGIBLE':2} and not list(db.scalars(select(CommercialLine)))
    result=bulk(c,r,rows,changes={'cost_source_type':'MANUFACTURER_COST'},defaults={'currency':'MXN','calculation_mode':'COST_FIRST','calculation_basis':'MARKUP','markup_percent':'25'},input_origin='UI',apply=True)
    assert result['counts']=={'UPDATED':2}
    rows=matrix(c,r)['rows']
    bulk(c,r,rows,action='INITIALIZE',defaults={'currency':'USD'},apply=True)
    assert all(row['inputs']['currency']=='MXN' for row in matrix(c,r)['rows'])
    history=list(db.scalars(select(CommercialLineRevision)))
    assert len(history)==2 and all(v.action=='BULK_WORKSPACE' for v in history)
    assert all(v.calculation_snapshot['bulk_operation']['origin']=='WORKSPACE_BULK' for v in history)
    assert history[0].calculation_snapshot['bulk_operation']['before']['unit_cost'] is None


@pytest.mark.parametrize('action,change,expected',[('MARKUP',{'markup_percent':'25'},'125'),('MARGIN',{'target_margin_percent':'20'},'125'),('MARGIN',{'target_margin_percent':'25'},'133.333333')])
def test_m7b06_08_math(sheet,action,change,expected):
    c,_,_,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'unit_cost':'100','currency':'MXN'},apply=True)
    result=bulk(c,r,matrix(c,r)['rows'],action=action,changes=change,apply=True)
    assert all(o['price_outcome']=='RECALCULATED' for o in result['outcomes'])
    assert all(Decimal(row['inputs']['offered_unit_price'])==Decimal(expected) for row in matrix(c,r)['rows'])


def test_m7b09_10_manual_and_explicit_replace(sheet):
    c,_,_,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'unit_cost':'100','offered_unit_price':'150','currency':'MXN'},apply=True)
    result=bulk(c,r,matrix(c,r)['rows'],action='MARKUP',changes={'markup_percent':'25'},apply=True)
    assert all(o['price_outcome']=='PROTECTED' for o in result['outcomes'])
    assert all(Decimal(row['inputs']['offered_unit_price'])==150 for row in matrix(c,r)['rows'])
    bulk(c,r,matrix(c,r)['rows'],action='RECALCULATE',replace_manual_price=True,apply=True)
    assert all(Decimal(row['inputs']['offered_unit_price'])==125 for row in matrix(c,r)['rows'])


def test_m7b11_mixed_failures_stale_missing_and_invalid(sheet):
    c,_,db,r=sheet
    rows=matrix(c,r)['rows']
    bulk(c,r,[rows[0]],changes={'unit_cost':'100'},apply=True)
    outcome=bulk(c,r,rows,changes={'currency':'MXN'},apply=True)
    assert sorted(o['outcome'] for o in outcome['outcomes'])==['STALE','UPDATED']
    result=bulk(c,r,matrix(c,r)['rows'],changes={'unit_cost':0.1},apply=True)
    assert result['counts']=={'INVALID':2}
    result=bulk(c,r,matrix(c,r)['rows'],action='MARGIN',changes={'target_margin_percent':'100'},apply=True)
    assert all('INVALID_MARGIN' in o['warnings'] and o['price_outcome']=='UNRESOLVED' for o in result['outcomes'])


def test_m7b12_copy_rules_without_prices_or_costs(sheet):
    c,_,_,r=sheet
    rows=matrix(c,r)['rows']
    bulk(c,r,[rows[0]],changes={'currency':'MXN','unit_cost':'100','offered_unit_price':'150','calculation_mode':'COST_FIRST','calculation_basis':'MARKUP','markup_percent':'50','reference_party_name':'Fabricante'},apply=True)
    rows=matrix(c,r)['rows']
    result=bulk(c,r,[rows[1]],action='COPY_SETTINGS',copy_from=target(rows[0]),apply=True)
    assert result['counts']=={'UPDATED':1}
    copied=matrix(c,r)['rows'][1]['inputs']
    assert copied['unit_cost'] is None and copied['offered_unit_price'] is None
    assert copied['currency']=='MXN' and copied['reference_party_name']=='Fabricante' and Decimal(copied['markup_percent'])==50


def test_m7b15_currency_confirm_and_partial_summary(sheet):
    c,_,_,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'unit_cost':'10','offered_unit_price':'9','currency':'MXN'},apply=True)
    rows=matrix(c,r)['rows']
    assert bulk(c,r,[rows[1]],changes={'currency':'USD'},apply=True)['outcomes'][0]['reasons']==['CURRENCY_CONFIRMATION_REQUIRED']
    bulk(c,r,[rows[1]],changes={'currency':'USD'},confirm_currency_change=True,apply=True)
    data=matrix(c,r)
    assert {g['currency'] for g in data['summary_by_currency']}=={'MXN','USD'}
    assert all(g['offered_total_calculable_count']==1 for g in data['summary_by_currency'])
    assert all('PRICE_BELOW_COST' in row['summary']['warnings'] for row in data['rows'])
    assert all(Decimal(row['inputs']['offered_unit_price'])==9 for row in data['rows'])


def test_m7b19_repeat_equivalent_no_revision(sheet):
    c,_,db,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'currency':'MXN','unit_cost':'100'},apply=True)
    bulk(c,r,matrix(c,r)['rows'],action='MARKUP',changes={'markup_percent':'25'},apply=True)
    before=len(list(db.scalars(select(CommercialLineRevision))))
    result=bulk(c,r,matrix(c,r)['rows'],action='MARKUP',changes={'markup_percent':'25'},apply=True)
    assert result['counts']=={'SKIPPED':2}
    assert len(list(db.scalars(select(CommercialLineRevision))))==before


def test_invalid_targets_and_copy_context(sheet):
    c,_,_,r=sheet
    rows=matrix(c,r)['rows']
    assert c.post(r+'/bulk',json={'targets':[target(rows[0])]*2,'changes':{'currency':'MXN'}}).status_code==422
    assert c.post(r+'/bulk',json={'targets':[target(rows[0])],'changes':{'quantity_id':'other'}}).status_code==422
    bulk(c,r,[rows[0]],changes={'currency':'MXN'},apply=True)
    result=bulk(c,r,[rows[1]],action='COPY_SETTINGS',copy_from=target(rows[0]),apply=True)
    assert result['outcomes'][0]['outcome']=='SKIPPED'
    assert not matrix(c,r)['rows'][1]['initialized']


def test_distinct_inline_costs_in_one_preview_apply(sheet):
    c,_,db,r=sheet
    rows=matrix(c,r)['rows']
    edits={rows[0]['scope_id']:{'unit_cost':'100'},rows[1]['scope_id']:{'unit_cost':'200'}}
    result=bulk(c,r,rows,action='MARKUP',changes={'markup_percent':'25'},row_changes=edits,defaults={'currency':'MXN'},apply=True)
    assert result['counts']=={'UPDATED':2}
    rows=matrix(c,r)['rows']
    assert [Decimal(row['inputs']['offered_unit_price']) for row in rows]==[125,250]
    assert all(row['source']['selected_quantity_id'] == row['source']['quantities'][0]['id'] for row in rows)


def test_matrix_commercial_queries_are_batched(sheet):
    from sqlalchemy import event
    c,_,db,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'currency':'MXN'},apply=True)
    statements=[]
    def collect(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT') and ('FROM commercial_lines' in statement or 'FROM commercial_line_revisions' in statement):
            statements.append(statement)
    engine=db.get_bind().engine
    event.listen(engine,'before_cursor_execute',collect)
    try:matrix(c,r)
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert len(statements)==2


def test_partial_validation_keeps_valid_row_and_provenance(sheet):
    c,t,db,r=sheet
    rows=matrix(c,r)['rows']
    before=c.get(f'/tenders/{t}/workspace').json()['scopes']
    edits={rows[0]['scope_id']:{'unit_cost':'bad'},rows[1]['scope_id']:{'unit_cost':'100','offered_unit_price':'90'}}
    result=bulk(c,r,rows,changes={'currency':'MXN'},row_changes=edits,apply=True)
    assert result['counts']=={'INVALID':1,'UPDATED':1}
    assert len(list(db.scalars(select(CommercialLine))))==1
    assert c.get(f'/tenders/{t}/workspace').json()['scopes']==before


def test_summary_exposes_incomplete_coverage(sheet):
    c,_,_,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'currency':'MXN'},apply=True)
    bulk(c,r,[matrix(c,r)['rows'][0]],changes={'unit_cost':'10','offered_unit_price':'12'},apply=True)
    group=matrix(c,r)['summary_by_currency'][0]
    assert group['line_count']==2 and group['total_cost_calculable_count']==1 and group['total_cost_missing_count']==1
    assert group['profit_calculable_count']==1 and group['paired_count']==1
    assert group['paired_markup_percent']=='20.00000000'
    assert c.get(r+'/summary').json()['summary_by_currency']==[group]
