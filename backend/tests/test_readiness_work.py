"""M8B-01–20 current-schema synthetic human workflow; no blind material."""
from uuid import uuid4
import json
import pytest
from sqlalchemy import select, text, event
from sqlalchemy.exc import DBAPIError
from app.models import ReadinessWorkDecision, TenderDocument, TenderScopeDetail, TenderScopeQuantity
from tests.test_workspace_flow import scene, upload, process
from tests.test_commercial_matrix import matrix, bulk
from tests.test_bid_readiness import complete


@pytest.fixture
def work(scene):
    c,t,db=scene;upload(c,t);process(c,t)
    return c,t,db,f'/tenders/{t}/readiness-work'


def read(c,r,query=''):
    response=c.get(r+query);assert response.status_code==200,response.text
    return response.json()


def save(c,r,item,**fields):
    response=c.patch(r+'/'+item['id'],json={'expected_revision':item['revision'],'expected_context_sha256':item['context_sha256'],**fields})
    assert response.status_code==200,response.text
    return response.json()


def test_m8b01_02_10_11_12_13_read_is_derived_and_links(work):
    c,t,db,r=work
    first=read(c,r);assert first==read(c,r)
    assert not list(db.scalars(select(ReadinessWorkDecision)))
    for item in first['items']:
        assert item['revision']==0 and item['lifecycle']=='ACTIVE' and item['workflow_status']=='OPEN'
        assert item['id']==item['issue']['id'] and item['entity_id']==item['issue']['entity_id']
        assert item['action_target'].startswith(f'/tenders/{t}/')
    commercial=next(i for i in first['items'] if i['dimension']=='COMMERCIAL')
    assert commercial['entity_id'] in {s.id for s in db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==t))}


def test_m8b03_04_07_15_16_note_state_owner_audit_and_summary(work):
    c,t,db,r=work;before=read(c,f'/tenders/{t}/bid-readiness')
    item=next(i for i in read(c,r)['items'] if i['issue']['severity']=='REVIEW')
    saved=save(c,r,item,workflow_status='IN_REVIEW',note='Revisión del equipo técnico',owner='Equipo técnico',actor_label='Responsable declarado')
    again=read(c,r+'/'+item['id'])
    assert again==saved and saved['note']=='Revisión del equipo técnico' and saved['revision']==1
    assert read(c,f'/tenders/{t}/bid-readiness')==before
    history=read(c,r+'/'+item['id']+'/history')
    assert history[0]['owner']=='Equipo técnico' and history[0]['actor_label']=='Responsable declarado' and history[0]['timestamp']
    same=save(c,r,saved,workflow_status='IN_REVIEW',note=saved['note'],owner=saved['owner'],actor_label=saved['actor_label'])
    assert same['revision']==1
    assert read(c,r)['work_summary']['review_items_open']>0


def test_m8b05_18_cannot_resolve_away_canonical_blocker(work):
    c,t,db,r=work;item=next(i for i in read(c,r)['items'] if i['code']=='MISSING_OFFERED_PRICE')
    before=read(c,f'/tenders/{t}/bid-readiness')
    saved=save(c,r,item,workflow_status='RESOLVED',note='Actividad cerrada, falta dato fuente')
    assert saved['workflow_status']=='RESOLVED' and saved['canonical_blocker_remains']
    assert read(c,f'/tenders/{t}/bid-readiness')==before and before['status']!='READY'
    summary=read(c,r+'/summary');assert summary['work_summary']['blockers_open']==before['blocker_count']
    for state in ['ACCEPTED_RISK','NOT_APPLICABLE']:
        response=c.patch(r+'/'+item['id'],json={'expected_revision':saved['revision'],'expected_context_sha256':saved['context_sha256'],'workflow_status':state})
        assert response.status_code==422


def test_m8b06_07_warning_risk_keeps_warning_and_history(complete):
    c,t,db,m=complete;r=f'/tenders/{t}/readiness-work'
    bulk(c,m,matrix(c,m)['rows'],changes={'offered_unit_price':'9'},apply=True)
    before=read(c,f'/tenders/{t}/bid-readiness')
    item=next(i for i in read(c,r)['items'] if i['code']=='PRICE_BELOW_COST')
    result=save(c,r,item,workflow_status='ACCEPTED_RISK',note='Estrategia autorizada de entrada')
    assert result['accepted_risk_allowed'] and read(c,r)['work_summary']['accepted_risks']==1
    assert read(c,f'/tenders/{t}/bid-readiness')==before and before['status']=='READY'
    assert read(c,r+'/'+item['id']+'/history')[0]['workflow_status']=='ACCEPTED_RISK'


def test_m8b08_09_resolution_and_stale_notes(work):
    c,t,db,r=work;m=f'/tenders/{t}/commercial-matrix'
    item=next(i for i in read(c,r)['items'] if i['code']=='MISSING_OFFERED_PRICE')
    saved=save(c,r,item,note='Pendiente decisión comercial')
    row=next(row for row in matrix(c,m)['rows'] if row['scope_id']==item['entity_id'])
    bulk(c,m,[row],changes={'offered_unit_price':'12','currency':'MXN'},apply=True)
    current=read(c,r+'/'+item['id'])
    assert current['lifecycle']=='RESOLVED_BY_SOURCE_CHANGE' and current['note']==saved['note']
    assert item['id'] not in {i['id'] for i in read(c,r)['items']}
    assert read(c,r+'?include_inactive=true')['work_summary']['resolved']>=1
    assert c.patch(r+'/'+item['id'],json={'expected_revision':1,'expected_context_sha256':current['context_sha256'],'workflow_status':'OPEN'}).status_code==409
    active=next(i for i in read(c,r)['items'] if i['issue']['severity']=='WARNING')
    accepted=save(c,r,active,workflow_status='ACCEPTED_RISK',note='Nota conservada')
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'notes':'Nuevo contexto comercial'},apply=True)
    refreshed=read(c,r+'/'+active['id'])
    assert refreshed['annotation_stale'] and refreshed['workflow_status']=='OPEN'
    assert refreshed['recorded_workflow_status']=='ACCEPTED_RISK' and refreshed['note']=='Nota conservada'
    assert c.patch(r+'/'+active['id'],json={'expected_revision':1,'expected_context_sha256':accepted['context_sha256'],'note':'viejo'}).status_code==409


def test_m8b09_removed_entity_obsolete_preserves_note(work):
    c,t,db,r=work
    item=next(i for i in read(c,r)['items'] if i['entity_type']=='QUANTITY')
    save(c,r,item,note='Nota histórica')
    quantity=db.get(TenderScopeQuantity,item['entity_id']);db.delete(quantity);db.flush()
    result=read(c,r+'/'+item['id'])
    assert result['lifecycle']=='OBSOLETE' and result['note']=='Nota histórica'


def test_m8b14_unknown_and_foreign_tender_cannot_write(work):
    c,t,db,r=work;item=read(c,r)['items'][0]
    save(c,r,item,note='Local')
    other=c.post('/tenders',json={'title':'Other'}).json()['id'];route=f'/tenders/{other}/readiness-work'
    assert c.get(route+'/'+item['id']).status_code==404
    assert c.patch(route+'/'+item['id'],json={'expected_revision':0,'expected_context_sha256':item['context_sha256'],'note':'Intrusión'}).status_code==404
    assert read(c,route+'/'+item['id']+'/history')==[]
    assert c.get(f'/tenders/{uuid4()}/readiness-work').status_code==404
    assert c.get(r+'/'+str(uuid4())).status_code==404


def test_context_and_revision_concurrency_and_history_bounds(work):
    c,t,db,r=work;item=read(c,r)['items'][0]
    first=save(c,r,item,note='Primera nota')
    assert c.patch(r+'/'+item['id'],json={'expected_revision':0,'expected_context_sha256':item['context_sha256'],'note':'desactualizada'}).status_code==409
    second=save(c,r,first,note='Segunda nota')
    assert second['revision']==2
    assert [i['revision'] for i in read(c,r+'/'+item['id']+'/history?limit=1')]==[2]
    assert [i['revision'] for i in read(c,r+'/'+item['id']+'/history?before_revision=2')]==[1]
    assert c.get(r+'?limit=201').status_code==422
    assert c.get(r+'?workflow_status=UNKNOWN').status_code==422
    assert c.patch(r+'/'+item['id'],json={'expected_revision':2,'expected_context_sha256':second['context_sha256'],'note':'x'*4001}).status_code==422


def test_m8b17_20_domain_sources_unchanged_and_append_only(work):
    c,t,db,r=work
    before=c.get(f'/tenders/{t}/workspace').json()['scopes'];m=matrix(c,f'/tenders/{t}/commercial-matrix')
    item=read(c,r)['items'][0];save(c,r,item,note='Sólo seguimiento')
    assert c.get(f'/tenders/{t}/workspace').json()['scopes']==before
    assert matrix(c,f'/tenders/{t}/commercial-matrix')==m
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('UPDATE readiness_work_decisions SET note=:note WHERE tender_id=:t'),{'note':'alterado','t':t})
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('DELETE FROM readiness_work_decisions WHERE tender_id=:t'),{'t':t})


def test_m8b19_work_queries_bounded_after_overlay(work):
    c,t,db,r=work
    for item in read(c,r)['items'][:5]:save(c,r,item,note='Seguimiento')
    statements=[]
    def collect(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    engine=db.get_bind().engine;event.listen(engine,'before_cursor_execute',collect)
    try:result=read(c,r)
    finally:event.remove(engine,'before_cursor_execute',collect)
    overlay=[s for s in statements if 'FROM readiness_work_decisions' in s]
    assert len(overlay)==1 and len(statements)<100
    from pathlib import Path
    Path('reports/m8_b/query_composition.json').write_text(json.dumps({'selects':len(statements),'overlay_selects':len(overlay),'items':result['total_filtered']},indent=2)+'\n')


def test_m8b10_13_requirement_and_requested_evidence_targets(complete):
    c,t,db,m=complete;r=f'/tenders/{t}/readiness-work'
    req=c.get(f'/tenders/{t}/requirement-matrix').json()['requirements'][0]
    c.patch(f"/tenders/{t}/requirements/{req['requirement_id']}/review",json={'action':'MARK_NEEDS_REVIEW'})
    data=read(c,r)
    requirement=next(i for i in data['items'] if i['dimension']=='REQUIREMENTS' and i['entity_type']=='REQUIREMENT')
    evidence=next(i for i in data['items'] if i['dimension']=='REQUESTED_EVIDENCE' and i['entity_type']=='REQUESTED_EVIDENCE')
    assert requirement['entity_id']==req['requirement_id'] and '/requirement-matrix' in requirement['action_target']
    assert evidence['entity_id'] in {e['id'] for e in req['expected_evidence']}
    assert evidence['issue']['underlying']['requirement_id']==req['requirement_id']
    assert save(c,r,evidence,workflow_status='IN_REVIEW',note='Revisar documento fuente')['note']=='Revisar documento fuente'
