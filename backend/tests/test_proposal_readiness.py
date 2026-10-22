"""M8D-01–24 synthetic canonical product handoff; no blind/provider runs."""
from copy import deepcopy
from uuid import uuid4
import json
from pathlib import Path
import pytest
from sqlalchemy import select,text,event
from sqlalchemy.exc import DBAPIError
from app.main import app
from app.database import get_db
from app.models import ProposalReadinessSnapshot,TenderScopeQuantity,TenderScopeDetail
from app.proposal_readiness import get_proposal_db,verify_payload,eligibility
from tests.test_workspace_flow import scene,upload,process
from tests.test_bid_readiness import complete
from tests.test_commercial_matrix import matrix,bulk
from tests.test_readiness_work import save,read


@pytest.fixture(autouse=True)
def proposal_connection(scene):
    app.dependency_overrides[get_proposal_db]=app.dependency_overrides[get_db]
    yield
    app.dependency_overrides.pop(get_proposal_db,None)


def evaluate(c,t):return read(c,f'/tenders/{t}/proposal-readiness')


def create(c,t,value=None,**fields):
    current=value or evaluate(c,t)
    request={'request_id':str(uuid4()),'expected_input_sha256':current['input_sha256'],'acknowledge_warnings':True,**fields}
    response=c.post(f'/tenders/{t}/proposal-readiness/snapshots',json=request)
    assert response.status_code==200,response.text
    return response.json(),request


def test_m8d01_03_09_13_23_ready_and_explicit(complete):
    c,t,db,m=complete;before=matrix(c,m);value=evaluate(c,t)
    assert value==evaluate(c,t) and value['projection']['readiness_status']=='READY'
    assert value['projection']['eligibility']=='ELIGIBLE_WITH_WARNINGS'
    assert value['projection']['warnings'] and not value['projection']['blockers']
    assert not list(db.scalars(select(ProposalReadinessSnapshot)))
    result,_=create(c,t,value,actor_label='Responsable declarado');payload=result['payload']
    assert payload['contract_version']=='proposal-readiness-snapshot-v1' and payload['actor_label']=='Responsable declarado'
    assert payload['created_at'] and payload['warnings_acknowledged']
    for row in payload['projection']['rows']:
        source=next(x for x in before['rows'] if x['scope_id']==row['scope_id'])
        assert row['quantity_scope_id']==row['scope_id'] and row['quantity_tender_id']==t
        assert row['quantity_id']==source['source']['selected_quantity_id'] and row['commercial_line_id']==source['commercial_line_id']
        assert row['source']['document_id'] and row['quantity_source']['page']==1
        assert row['price_value_origin']=='MANUAL_INPUT' and row['price_method']=='MANUAL'
    assert matrix(c,m)==before
    assert eligibility([],[],[],[object()],[])=='ELIGIBLE'
    # Internal costs/pricing rules never enter the MVP-09 projection.
    assert all(k not in json.dumps(payload) for k in ['unit_cost','markup_percent','target_margin_percent'])


@pytest.mark.parametrize('field,value,code',[
    ('offered_unit_price',None,'MISSING_OFFERED_PRICE'),('currency',None,'MISSING_CURRENCY')])
def test_m8d02_05_06_22_missing_essentials(complete,field,value,code):
    c,t,db,m=complete
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={field:value},apply=True,confirm_currency_change=True)
    current=evaluate(c,t);assert current['projection']['eligibility']=='NOT_ELIGIBLE'
    issue=next(i for i in current['projection']['blockers'] if i['code']==code)
    work=next(i for i in read(c,f'/tenders/{t}/readiness-work')['items'] if i['id']==issue['id'])
    save(c,f'/tenders/{t}/readiness-work',work,workflow_status='RESOLVED')
    current=evaluate(c,t);assert current['projection']['eligibility']=='NOT_ELIGIBLE'
    response=c.post(f'/tenders/{t}/proposal-readiness/snapshots',json={'request_id':str(uuid4()),'expected_input_sha256':current['input_sha256'],'acknowledge_warnings':True})
    assert response.status_code==409 and not list(db.scalars(select(ProposalReadinessSnapshot)))


def test_m8d04_review_is_distinct_and_prevents_prepared_snapshot(complete):
    c,t,db,m=complete;req=read(c,f'/tenders/{t}/requirement-matrix')['requirements'][0]
    c.patch(f"/tenders/{t}/requirements/{req['requirement_id']}/review",json={'action':'MARK_NEEDS_REVIEW'})
    value=evaluate(c,t);assert value['projection']['eligibility']=='REVIEW_REQUIRED'
    assert value['projection']['reviews'] and not value['projection']['blockers']
    response=c.post(f'/tenders/{t}/proposal-readiness/snapshots',json={'request_id':str(uuid4()),'expected_input_sha256':value['input_sha256'],'acknowledge_warnings':True})
    assert response.status_code==409


def test_m8d07_quantity_missing_exposed(complete):
    c,t,db,m=complete;row=matrix(c,m)['rows'][0]
    db.delete(db.get(TenderScopeQuantity,row['source']['selected_quantity_id']));db.flush()
    value=evaluate(c,t)
    assert value['projection']['eligibility']=='NOT_ELIGIBLE'
    assert any(i['code']=='MISSING_CANONICAL_QUANTITY' for i in value['projection']['blockers'])
    assert row['scope_id'] in value['projection']['excluded_scope_ids']


def test_m8d08_risk_confirm_and_hash(complete):
    c,t,db,m=complete;bulk(c,m,matrix(c,m)['rows'],changes={'offered_unit_price':'9'},apply=True)
    route=f'/tenders/{t}/readiness-work'
    warning=next(i for i in read(c,route)['items'] if i['code']=='PRICE_BELOW_COST')
    save(c,route,warning,workflow_status='ACCEPTED_RISK',note='Estrategia consciente',actor_label='Comercial')
    value=evaluate(c,t);assert value['projection']['accepted_risks'][0]['note']=='Estrategia consciente'
    response=c.post(f'/tenders/{t}/proposal-readiness/snapshots',json={'request_id':str(uuid4()),'expected_input_sha256':value['input_sha256']})
    assert response.status_code==409 and 'CONFIRMATION' in response.text
    result,_=create(c,t,value)
    verified=verify_payload(result['payload'],result['payload_sha256'])
    assert verified.projection.accepted_risks[0].note=='Estrategia consciente'
    assert any(i.code=='PRICE_BELOW_COST' for i in verified.projection.warnings)


def test_m8d10_11_12_15_16_17_18_19_immutable_stale_and_retry(complete,monkeypatch):
    c,t,db,m=complete;result,request=create(c,t);identity=result['payload']['snapshot_id'];route=f'/tenders/{t}/proposal-readiness/snapshots'
    assert read(c,f'{route}/{identity}/freshness')['state']=='CURRENT'
    assert c.post(route,json=request).json()==result
    tampered=deepcopy(result['payload']);tampered['projection']['rows'][0]['quantity']='999'
    with pytest.raises(ValueError,match='HASH'):verify_payload(tampered,result['payload_sha256'])
    for sql in ['UPDATE proposal_readiness_snapshots SET actor_label=\'changed\' WHERE id=:id','DELETE FROM proposal_readiness_snapshots WHERE id=:id']:
        with pytest.raises(DBAPIError):
            with db.begin_nested():db.execute(text(sql),{'id':identity})
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'offered_unit_price':'13'},apply=True)
    assert read(c,f'{route}/{identity}/freshness')['state']=='STALE'
    assert read(c,f'{route}/{identity}')==result
    assert c.post(route,json=request).json()==result  # Lost response retry returns original even after source changed.
    assert c.post(route,json={**request,'actor_label':'Different'}).status_code==409
    later,_=create(c,t);second=later['payload']['snapshot_id'];assert second!=identity
    same_state,_=create(c,t);assert same_state['payload']['input_sha256']==later['payload']['input_sha256']
    page=read(c,route+'?limit=1');assert page['items'][0]['snapshot_id']==same_state['payload']['snapshot_id']
    assert read(c,route+'?limit=1&before_id='+page['next_before_id'])['items'][0]['snapshot_id']==second
    def denied(*a,**k):raise AssertionError('Handoff must not recompute source state')
    monkeypatch.setattr('app.proposal_readiness.evaluate',denied)
    assert read(c,f'{route}/{identity}/handoff')==result['payload']['projection']
    assert len(list(db.scalars(select(ProposalReadinessSnapshot))))==3


def test_m8d14_tender_boundary_and_unknown(complete):
    c,t,db,m=complete;result,_=create(c,t);identity=result['payload']['snapshot_id']
    other=c.post('/tenders',json={'title':'Different'}).json()['id']
    for suffix in ['', '/handoff','/freshness']:
        assert c.get(f'/tenders/{other}/proposal-readiness/snapshots/{identity}'+suffix).status_code==404
    assert c.get(f'/tenders/{uuid4()}/proposal-readiness').status_code==404
    tampered=deepcopy(result['payload']);tampered['projection']['rows'][0]['quantity_scope_id']=str(uuid4())
    from app.proposal_readiness import digest
    with pytest.raises(ValueError,match='PARENT'):verify_payload(tampered,digest(tampered))


def test_precheck_stale_and_irrelevant_cost_only_edit(complete):
    c,t,db,m=complete;initial=evaluate(c,t)
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'unit_cost':'11'},apply=True)
    assert evaluate(c,t)['input_sha256']==initial['input_sha256']
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'offered_unit_price':'14'},apply=True)
    response=c.post(f'/tenders/{t}/proposal-readiness/snapshots',json={'request_id':str(uuid4()),'expected_input_sha256':initial['input_sha256'],'acknowledge_warnings':True})
    assert response.status_code==409 and 'STALE' in response.text


def test_m8d21_bounded_scale(scene):
    c,t,db=scene;upload(c,t);process(c,t);engine=db.get_bind().engine
    def measure():
        statements=[]
        def collect(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
        event.listen(engine,'before_cursor_execute',collect)
        try:value=evaluate(c,t)
        finally:event.remove(engine,'before_cursor_execute',collect)
        return value,len(statements)
    _,small=measure();scope=db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==t));quantity=db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id==scope.id))
    for _ in range(98):
        values={col.name:getattr(scope,col.name) for col in TenderScopeDetail.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        values['semantic_fingerprint']=uuid4().hex*2;clone=TenderScopeDetail(**values);db.add(clone);db.flush()
        child={col.name:getattr(quantity,col.name) for col in TenderScopeQuantity.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        child.update(scope_detail_id=clone.id,semantic_fingerprint=uuid4().hex*2);db.add(TenderScopeQuantity(**child))
    db.flush();value,large=measure();assert large<=small+12,{'small':small,'large':large}
    Path('reports/m8_d/query_scaling.json').write_text(json.dumps({'small_scopes':2,'large_scopes':100,'small_selects':small,'large_selects':large,'signals':len(value['projection']['tracked_context'])},indent=2)+'\n')


def test_repeatable_read_dependency():
    # Verify production transaction contract independently of the API fixture override.
    generator=get_proposal_db();db=next(generator)
    try:assert db.connection().get_isolation_level()=='REPEATABLE READ'
    finally:generator.close()
