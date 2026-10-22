"""M7D synthetic contracts: no blind data, providers or Quantity editing endpoints."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.commercial_calculations import CommercialInputs, calculate
from app.commercial_readiness import complete_result
from app.models import TenderScopeQuantity, CommercialLineRevision
from tests.test_workspace_flow import scene
from tests.test_commercial_matrix import sheet, matrix, bulk


@pytest.mark.parametrize('changes,quantity,status,code,severity',[
    ({},'2','READY',None,None),
    ({'offered_unit_price':None},'2','INCOMPLETE','MISSING_OFFERED_PRICE','BLOCKER'),
    ({'currency':None},'2','INCOMPLETE','MISSING_CURRENCY','BLOCKER'),
    ({},None,'INCOMPLETE','MISSING_CANONICAL_QUANTITY','BLOCKER'),
    ({'unit_cost':'100','offered_unit_price':'90'},'2','READY','PRICE_BELOW_COST','WARNING'),
    ({'unit_cost':None},'2','READY','COST_UNRESOLVED','WARNING'),
    ({'cost_source_type':'INTERNAL_COST'},'2','READY',None,None),
    ({'cost_source_type':'MANUFACTURER_COST'},'2','READY',None,None),
    ({'cost_source_type':'MANUAL'},'2','READY',None,None),
    ({'cost_source_type':'SUPPLIER_QUOTE'},'2','READY','COST_SOURCE_REFERENCE_MISSING','WARNING'),
    ({'cost_source_type':'SUPPLIER_QUOTE','reference_party_reference':'Q-1'},'2','READY',None,None),
    ({'unit_cost':'0'},'2','READY','ZERO_COST','WARNING'),
    ({'offered_unit_price':'0'},'2','READY','ZERO_PRICE','WARNING'),
    ({'offered_unit_price':'-1'},'2','REVIEW_REQUIRED','NEGATIVE_VALUE','REVIEW'),
    ({'calculation_mode':'COST_FIRST','calculation_basis':'MARGIN','target_margin_percent':'100'},'2','READY','INVALID_MARGIN','WARNING'),
])
def test_m7d02_08_policy(changes,quantity,status,code,severity):
    values=CommercialInputs.model_validate({'currency':'MXN','unit_cost':'10','offered_unit_price':'12'}|changes)
    result=calculate(values,Decimal(quantity) if quantity else None)
    assert result['status']==result['readiness']['status']==status
    assert result['readiness']['proposal_eligible']==(status=='READY')
    if code:assert {'code':code,'severity':severity} in result['readiness']['reasons']
    if values.unit_cost is None:
        assert result['actual_margin_percent'] is None and result['actual_markup_percent'] is None and result['profit'] is None


@pytest.mark.parametrize('warning',['SOURCE_UNAVAILABLE','SCOPE_REVIEW_REQUIRED','QUANTITY_REVIEW_REQUIRED','SOURCE_CONTEXT_CHANGED','PRICE_CALCULATION_STALE','UNKNOWN_CONTEXT_WARNING'])
def test_review_cannot_be_removed_by_a_price(warning):
    values=CommercialInputs(currency='MXN',offered_unit_price='12')
    result=complete_result(values,calculate(values,Decimal(2))|{'warnings':[warning]})
    assert result['status']=='REVIEW_REQUIRED' and not result['readiness']['proposal_eligible']


def test_m7d01_missing_line_and_cost_first_without_manual_decision():
    values=CommercialInputs(currency='MXN',offered_unit_price='12',calculation_mode='COST_FIRST')
    result=complete_result(values,calculate(values,Decimal(2)),initialized=False,manual_price=False)
    assert result['status']=='INCOMPLETE'
    assert {'code':'MISSING_COMMERCIAL_LINE','severity':'BLOCKER'} in result['readiness']['reasons']
    assert {'code':'COST_UNRESOLVED','severity':'BLOCKER'} in result['readiness']['reasons']


def ready_source(c,t,db,r):
    """Controlled current-schema fixture, NOT a product Quantity correction mechanism."""
    for row in matrix(c,r)['rows']:
        path=f"/tenders/{t}/scope-review/{row['scope_id']}"
        view=c.get(path).json()
        response=c.post(path+'/decisions',json={'decision':'CONFIRMED','expected_projection_fingerprint':view['projection_fingerprint'],'expected_current_review_revision':view['current_review_revision']})
        assert response.status_code==200,response.text
    for q in db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==t)):
        q.review_required=False
    db.flush()


def get(c,path):
    response=c.get(path);assert response.status_code==200,response.text
    return response.json()


def test_m7d01_10_11_18_readiness_pure_and_empty(sheet):
    c,t,db,r=sheet
    path=f'/tenders/{t}/commercial-readiness'
    before=c.get(f'/tenders/{t}/workspace').json()['scopes']
    first=get(c,path)
    assert first==get(c,path) and first['missing_commercial_treatment_count']==2 and first['incomplete_count']==2
    assert all(i['readiness']['status']=='INCOMPLETE' for i in first['items'])
    assert all('inputs' not in i and 'unit_cost' not in i for i in first['items'])
    assert not list(db.scalars(select(CommercialLineRevision)))
    assert c.get(f'/tenders/{t}/workspace').json()['scopes']==before
    empty=c.post('/tenders',json={'title':'Empty'}).json()['id']
    assert get(c,f'/tenders/{empty}/commercial-readiness')['status']=='INCOMPLETE'
    assert c.get(f'/tenders/{uuid4()}/commercial-readiness').status_code==404
    assert c.get(f'/tenders/{t}/scopes/{uuid4()}/commercial-readiness').status_code==404


def test_m7d05_09_12_19_20_proposal_loss_and_currencies(sheet):
    c,t,db,r=sheet;ready_source(c,t,db,r)
    before=c.get(f'/tenders/{t}/workspace').json()['scopes']
    rows=matrix(c,r)['rows']
    for index,currency in enumerate(['MXN','USD']):
        bulk(c,r,[rows[index]],changes={'unit_cost':'100','offered_unit_price':'90','currency':currency,'notes':'Estrategia de entrada'},apply=True,input_origin='UI')
    data=get(c,f'/tenders/{t}/commercial-readiness')
    assert data['status']=='READY' and data['ready_count']==2 and data['warning_count']==2
    assert {g['currency'] for g in data['summary_by_currency']}=={'MXN','USD'}
    assert 'offered_total' not in data
    projection=get(c,f'/tenders/{t}/commercial-proposal')
    assert projection['state_reference']==data['state_reference'] and not projection['excluded']
    for row,source in zip(projection['rows'],matrix(c,r)['rows']):
        assert row['scope_id']==source['scope_id'] and Decimal(row['quantity'])==Decimal(source['source']['quantities'][0]['quantity_value'])
        assert Decimal(row['offered_total'])==Decimal(row['quantity'])*90
        assert row['warnings']==['PRICE_BELOW_COST'] and 'unit_cost' not in row and 'source_fingerprint' not in row
    assert c.get(f'/tenders/{t}/workspace').json()['scopes']==before
    assert get(c,f"/tenders/{t}/scopes/{rows[0]['scope_id']}/commercial-readiness")==data['items'][0]


def test_m7d07_08_17_manual_known_price_without_cost_and_audit(sheet):
    c,t,db,r=sheet;ready_source(c,t,db,r)
    bulk(c,r,matrix(c,r)['rows'],changes={'offered_unit_price':'120','currency':'MXN','calculation_mode':'COST_FIRST','calculation_basis':'MARKUP','markup_percent':'25'},apply=True,input_origin='UI')
    assert get(c,f'/tenders/{t}/commercial-readiness')['ready_count']==2
    rows=matrix(c,r)['rows'];row=rows[0]
    bulk(c,r,[row],changes={'unit_cost':'100','notes':'Precio autorizado por dirección'},apply=True,input_origin='UI')
    audit=get(c,f"/tenders/{t}/scopes/{row['scope_id']}/commercial-audit?limit=1")
    event=audit['events'][0]
    assert event['origin']=='BULK' and event['manual_price'] and event['differs_from_recommendation']
    assert event['note']=='Precio autorizado por dirección' and Decimal(event['recommended_unit_price'])==125
    assert audit['next_before_revision']==2
    older=get(c,f"/tenders/{t}/scopes/{row['scope_id']}/commercial-audit?before_revision=2")
    assert older['events'][0]['revision']==1 and older['current_revision']==2 and older['next_before_revision'] is None
    assert any(change['field']=='unit_cost' and change['previous'] is None for change in event['changes'])
    assert c.get(f"/tenders/{t}/scopes/{row['scope_id']}/commercial-audit?limit=101").status_code==422


def test_quantity_pending_and_missing_prevent_proposal(sheet):
    c,t,db,r=sheet
    bulk(c,r,matrix(c,r)['rows'],changes={'offered_unit_price':'12','currency':'MXN'},apply=True)
    data=get(c,f'/tenders/{t}/commercial-readiness')
    assert data['review_required_count']==2
    assert not get(c,f'/tenders/{t}/commercial-proposal')['rows']
    ready_source(c,t,db,r)
    row=matrix(c,r)['rows'][0]
    quantity=db.get(TenderScopeQuantity,row['source']['selected_quantity_id']);db.delete(quantity);db.flush()
    current=get(c,f"/tenders/{t}/scopes/{row['scope_id']}/commercial-readiness")
    assert current['readiness']['status']=='INCOMPLETE'
    assert any(reason['code']=='MISSING_CANONICAL_QUANTITY' for reason in current['readiness']['reasons'])


@pytest.mark.parametrize('kind',['xlsx','csv'])
def test_m7d14_16_imports_use_canonical_readiness_and_audit(sheet,kind):
    from tests.test_commercial_exchange import export, edit, stage
    c,t,db,r=sheet;ready_source(c,t,db,r)
    before=get(c,f'/tenders/{t}/commercial-readiness')['state_reference']
    data=export(c,r,kind)
    changes={'offered_unit_price':'90','currency':'MXN','unit_cost':'100'}
    if kind=='xlsx':
        data=edit(data,{(2,key):value for key,value in changes.items()})
    else:
        import csv,io
        records=list(csv.reader(io.StringIO(data.decode('utf-8'))))
        for key,value in changes.items():records[2][records[1].index(key)]=value
        out=io.StringIO(newline='');csv.writer(out).writerows(records);data=out.getvalue().encode('utf-8')
    preview=stage(c,r,data,kind)
    path=r.replace('/commercial-matrix','/commercial-exchange')
    response=c.post(path+f"/stages/{preview['stage_id']}/apply",json={'confirm':True})
    assert response.status_code==200,response.text
    state=get(c,f'/tenders/{t}/commercial-readiness')
    row=matrix(c,r)['rows'][0]
    assert state['state_reference']!=before and state['items'][0]['readiness']==row['summary']['readiness']
    audit=get(c,f"/tenders/{t}/scopes/{row['scope_id']}/commercial-audit")
    assert audit['events'][0]['origin']==kind.upper() and audit['events'][0]['import_evidence']['sha256']==preview['file_evidence']['sha256']


def test_m7d13_cross_tender_and_unknown_audit(sheet):
    c,t,db,r=sheet
    row=matrix(c,r)['rows'][0]
    bulk(c,r,[row],changes={'currency':'MXN'},apply=True)
    other=c.post('/tenders',json={'title':'Other'}).json()['id']
    for suffix in ['commercial-readiness','commercial-audit']:
        assert c.get(f"/tenders/{other}/scopes/{row['scope_id']}/{suffix}").status_code==404
    assert c.get(f'/tenders/{t}/scopes/{uuid4()}/commercial-audit').status_code==404
