"""M8C-01–22 synthetic contracts; no blind corpus or real providers."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import select, event
from app.models import TenderScopeDetail, TenderScopeQuantity, ReadinessWorkDecision
from tests.test_workspace_flow import scene
from tests.test_readiness_work import work, read, save
from tests.test_bid_readiness import complete
from tests.test_commercial_matrix import matrix, bulk


def board(c,t,query=''):
    return read(c,f'/tenders/{t}/readiness-board'+query)


def test_m8c01_02_03_10_11_12_13_15_21(work):
    c,t,db,r=work;data=board(c,t)
    assert data==board(c,t)
    canonical=read(c,f'/tenders/{t}/bid-readiness')
    assert data['canonical_summary']['status']==canonical['status']
    assert data['canonical_summary']['blocker_count']==canonical['blocker_count']
    assert sum(d['blocker_count'] for d in data['dimensions'])==canonical['blocker_count']
    for row in data['items']:
        i=row['work'];assert i['tender_id']==t
        if i['issue']['severity']=='BLOCKER':assert row['bucket']=='BLOCKERS'
        if i['issue']['severity']=='REVIEW':assert row['bucket']=='REVIEW_REQUIRED'
        if i['entity_type']=='QUANTITY':assert row['action_target']==f"/tenders/{t}/scope-review/{i['issue']['underlying']['scope_id']}"
        if i['dimension']=='COMMERCIAL':assert row['action_target']==f"/tenders/{t}/scopes/{i['entity_id']}/commercial-line"
    item=next(x['work'] for x in data['items'] if x['work']['issue']['severity']=='REVIEW')
    save(c,r,item,workflow_status='IN_REVIEW')
    current=board(c,t);assert current['work_summary']['in_review']==1
    assert next(x for x in current['items'] if x['work']['id']==item['id'])['work']['workflow_status']=='IN_REVIEW'
    assert current['canonical_summary']==data['canonical_summary']
    assert [x['priority'] for x in current['items']]==sorted(x['priority'] for x in current['items'])


@pytest.mark.parametrize('field,value',[('dimension','COMMERCIAL'),('severity','REVIEW'),('workflow_status','OPEN'),('bucket','BLOCKERS')])
def test_m8c07_08_09_filters_and_search(work,field,value):
    c,t,db,r=work;full=board(c,t);filtered=board(c,t,f'?{field}={value}')
    for row in filtered['items']:
        actual=row['bucket'] if field=='bucket' else row['work']['issue']['severity'] if field=='severity' else row['work'][field]
        assert actual==value
    assert filtered['canonical_summary']==full['canonical_summary'] and filtered['dimensions']==full['dimensions']
    assert board(c,t,'?search=missing_offered_price')['items']
    assert not board(c,t,'?search=no-such-synthetic-issue')['items']
    assert c.get(f'/tenders/{t}/readiness-board?dimension=FAKE').status_code==422


def test_m8c04_06_16_risk_visible_and_not_compliance(complete):
    c,t,db,m=complete;r=f'/tenders/{t}/readiness-work'
    bulk(c,m,matrix(c,m)['rows'],changes={'offered_unit_price':'9'},apply=True)
    before=board(c,t);item=next(x['work'] for x in before['items'] if x['work']['code']=='PRICE_BELOW_COST')
    save(c,r,item,workflow_status='ACCEPTED_RISK',note='Riesgo deliberado')
    after=board(c,t);row=next(x for x in after['items'] if x['work']['id']==item['id'])
    assert row['bucket']=='ACCEPTED_RISKS' and row['work']['note']=='Riesgo deliberado'
    assert after['canonical_summary']==before['canonical_summary'] and after['canonical_summary']['warning_count']>0
    assert after['work_summary']['accepted_risks']==1 and 'compliance_percentage' not in after


def test_m8c05_14_17_22_source_resolution_and_stale(work):
    c,t,db,r=work;m=f'/tenders/{t}/commercial-matrix';initial=board(c,t)
    item=next(x['work'] for x in initial['items'] if x['work']['code']=='MISSING_OFFERED_PRICE')
    workspace=read(c,f'/tenders/{t}/workspace');commercial=matrix(c,m)
    save(c,r,item,workflow_status='RESOLVED',note='Seguimiento cerrado')
    row=next(x for x in board(c,t)['items'] if x['work']['id']==item['id'])
    assert row['bucket']=='BLOCKERS' and row['work']['canonical_blocker_remains']
    def stable(value):
        if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k!='generated_at'}
        if isinstance(value,list):return [stable(v) for v in value]
        return value
    assert stable(read(c,f'/tenders/{t}/workspace'))==stable(workspace) and matrix(c,m)==commercial
    assert c.patch(f'/tenders/{t}/readiness-board',json={'offered_unit_price':1}).status_code==405
    price=next(x for x in commercial['rows'] if x['scope_id']==item['entity_id'])
    bulk(c,m,[price],changes={'offered_unit_price':'12','currency':'MXN'},apply=True)
    assert item['id'] not in {x['work']['id'] for x in board(c,t)['items']}
    history=board(c,t,'?include_inactive=true')
    resolved=next(x for x in history['items'] if x['work']['id']==item['id'])
    assert resolved['bucket']=='RESOLVED' and resolved['work']['note']=='Seguimiento cerrado'
    warning=next(x['work'] for x in history['items'] if x['work']['lifecycle']=='ACTIVE' and x['work']['issue']['severity']=='WARNING')
    save(c,r,warning,workflow_status='ACCEPTED_RISK',note='Conservar')
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'notes':'Cambio ajeno'},apply=True)
    stale=next(x for x in board(c,t)['items'] if x['work']['id']==warning['id'])
    assert stale['work']['annotation_stale'] and stale['work']['workflow_status']=='OPEN' and stale['work']['note']=='Conservar'
    assert stale['bucket']!='ACCEPTED_RISKS'


def test_m8c18_bounds_and_tender_isolation(work):
    c,t,db,r=work;other=c.post('/tenders',json={'title':'Other synthetic'}).json()['id']
    ids={x['work']['id'] for x in board(c,t)['items']}
    assert not ids.intersection(x['work']['id'] for x in board(c,other)['items'])
    assert c.get(f'/tenders/{uuid4()}/readiness-board').status_code==404
    for query in ['?limit=201','?offset=-1','?search='+'x'*201]:assert c.get(f'/tenders/{t}/readiness-board'+query).status_code==422
    assert not list(db.scalars(select(ReadinessWorkDecision)))


def test_m8c19_20_large_real_reader_scaling(work):
    c,t,db,r=work;engine=db.get_bind().engine
    def measure(query=''):
        statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
        event.listen(engine,'before_cursor_execute',capture)
        try:data=board(c,t,query)
        finally:event.remove(engine,'before_cursor_execute',capture)
        return data,len(statements)
    small,small_queries=measure()
    original=db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==t))
    quantity=db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id==original.id))
    for _ in range(98):
        values={col.name:getattr(original,col.name) for col in TenderScopeDetail.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        values['semantic_fingerprint']=uuid4().hex*2
        clone=TenderScopeDetail(**values);db.add(clone);db.flush()
        child={col.name:getattr(quantity,col.name) for col in TenderScopeQuantity.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        child.update(scope_detail_id=clone.id,semantic_fingerprint=uuid4().hex*2)
        db.add(TenderScopeQuantity(**child))
    db.flush();large,large_queries=measure('?limit=200')
    assert large['total_filtered']>200 and len(large['items'])==200
    assert large_queries<=small_queries+12,{'small':small_queries,'large':large_queries}
    second=board(c,t,'?offset=200&limit=200')
    assert not {x['work']['id'] for x in large['items']}.intersection(x['work']['id'] for x in second['items'])
    report={'small_scopes':2,'large_scopes':100,'small_selects':small_queries,'large_selects':large_queries,'large_items':large['total_filtered'],'page_size':200}
    Path('reports/m8_c/query_scaling.json').write_text(json.dumps(report,indent=2)+'\n')


def test_m8c10_requirement_evidence_and_source_targets(complete):
    c,t,db,m=complete
    req=read(c,f'/tenders/{t}/requirement-matrix')['requirements'][0]
    response=c.patch(f"/tenders/{t}/requirements/{req['requirement_id']}/review",json={'action':'MARK_NEEDS_REVIEW'})
    assert response.status_code==200
    rows=board(c,t)['items']
    for kind in ['REQUIREMENT','REQUESTED_EVIDENCE']:
        row=next(x for x in rows if x['work']['entity_type']==kind)
        assert row['action_target']==f"/tenders/{t}/requirement-matrix#{row['work']['entity_id']}"
        if kind=='REQUESTED_EVIDENCE':assert row['work']['issue']['underlying']['requirement_id']==req['requirement_id']
        assert row['source_target'] and row['source_target'].startswith(f'/tenders/{t}/documents/')
        assert c.get(row['action_target'].split('#')[0]).status_code==200


def test_in_progress_warning_keeps_canonical_warning(work):
    c,t,db,r=work
    warning=next(x['work'] for x in board(c,t)['items'] if x['work']['issue']['severity']=='WARNING')
    save(c,r,warning,workflow_status='IN_REVIEW')
    row=next(x for x in board(c,t)['items'] if x['work']['id']==warning['id'])
    assert row['bucket']=='IN_PROGRESS' and row['work']['issue']['severity']=='WARNING'
