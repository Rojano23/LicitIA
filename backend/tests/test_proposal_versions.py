"""M9A-01–22 synthetic proposal versions over explicit canonical snapshots."""
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from app.models import ProposalVersion,ProposalVersionEvent,ProposalReadinessSnapshot
from app.proposal_readiness import get_snapshot
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection,create as create_snapshot,evaluate
from tests.test_commercial_matrix import matrix,bulk
from tests.test_readiness_work import read


def create(c,t,snapshot,**changes):
    payload={'request_id':str(uuid4()),'snapshot_id':snapshot['payload']['snapshot_id'],'acknowledge_warnings':True,**changes}
    response=c.post(f'/tenders/{t}/proposal-versions',json=payload)
    if response.status_code!=200:
        from pathlib import Path
        import json
        Path('reports/m9_b').mkdir(parents=True,exist_ok=True)
        Path('reports/m9_b/fixture_diagnostic.json').write_text(json.dumps({'response':response.text,'snapshot':snapshot,'current':evaluate(c,t)},indent=2))
    assert response.status_code==200,response.text
    return response.json(),payload


@pytest.fixture
def ready(complete):
    c,t,db,m=complete
    current=evaluate(c,t)
    if current['projection']['eligibility'] not in {'ELIGIBLE','ELIGIBLE_WITH_WARNINGS'}:
        from pathlib import Path
        import json
        Path('reports/m9_b').mkdir(parents=True,exist_ok=True)
        Path('reports/m9_b/fixture_ready_diagnostic.json').write_text(json.dumps(current,indent=2))
    assert current['projection']['eligibility'] in {'ELIGIBLE','ELIGIBLE_WITH_WARNINGS'},current
    snapshot,_=create_snapshot(c,t,current)
    return c,t,db,m,snapshot


def test_m9a01_03_04_09_10_11_12_19_20_21_22_input_authority(ready,monkeypatch):
    c,t,db,m,snapshot=ready
    before=matrix(c,m);canonical=read(c,f'/tenders/{t}/bid-readiness');value,request=create(c,t,snapshot)
    assert value['state']=='DRAFT' and value['version']==1 and value['snapshot_id']==snapshot['payload']['snapshot_id']
    assert value['snapshot_sha256']==snapshot['payload_sha256'] and value['snapshot_eligibility']=='ELIGIBLE_WITH_WARNINGS'
    def denied(*a,**k):raise AssertionError('Input read must not reinterpret/query mutable domain')
    monkeypatch.setattr('app.proposal_readiness.evaluate',denied)
    projection=read(c,f"/tenders/{t}/proposal-versions/{value['id']}/inputs")
    assert projection['handoff']==snapshot['payload']['projection'] and projection['contract_version']=='proposal-builder-v1'
    assert all(r['quantity_scope_id']==r['scope_id'] and r['quantity_tender_id']==t for r in projection['handoff']['rows'])
    assert any(i['entity_type']=='REQUIREMENT' for i in projection['handoff']['tracked_context'])
    assert any(i['entity_type']=='REQUESTED_EVIDENCE' for i in projection['handoff']['tracked_context'])
    assert matrix(c,m)==before and read(c,f'/tenders/{t}/bid-readiness')==canonical
    assert read(c,f"/tenders/{t}/proposal-readiness/snapshots/{value['snapshot_id']}")==snapshot


def test_m9a02_invalid_snapshot_precheck_and_warnings(ready,monkeypatch):
    c,t,db,m,snapshot=ready
    response=c.post(f'/tenders/{t}/proposal-versions',json={'request_id':str(uuid4()),'snapshot_id':snapshot['payload']['snapshot_id']})
    assert response.status_code==409 and 'WARNINGS_ACK' in response.text
    stored=get_snapshot(db,t,snapshot['payload']['snapshot_id'])
    invalid=stored.model_copy(update={'payload':stored.payload.model_copy(update={'projection':stored.payload.projection.model_copy(update={'eligibility':'NOT_ELIGIBLE'})})})
    monkeypatch.setattr('app.proposal_versions.get_snapshot',lambda *a:invalid)
    response=c.post(f'/tenders/{t}/proposal-versions',json={'request_id':str(uuid4()),'snapshot_id':snapshot['payload']['snapshot_id'],'acknowledge_warnings':True})
    assert response.status_code==409 and 'NOT_ELIGIBLE' in response.text
    assert not list(db.scalars(select(ProposalVersion)))


def test_m9a05_06_binding_stays_fixed_on_source_change(ready):
    c,t,db,m,snapshot=ready;value,_=create(c,t,snapshot);route=f"/tenders/{t}/proposal-versions/{value['id']}"
    before=read(c,route+'/inputs')
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'offered_unit_price':'15'},apply=True)
    assert read(c,route+'/source-state')['state']=='SOURCE_SNAPSHOT_STALE'
    assert read(c,route+'/inputs')==before and read(c,route)['snapshot_id']==value['snapshot_id']
    response=c.post(f'/tenders/{t}/proposal-versions',json={'request_id':str(uuid4()),'snapshot_id':value['snapshot_id'],'acknowledge_warnings':True})
    assert response.status_code==409 and 'STALE_ACK' in response.text
    historical,_=create(c,t,snapshot,acknowledge_stale=True)
    assert historical['snapshot_id']==value['snapshot_id']


def test_m9a07_13_14_15_16_17_revision_and_freeze(ready):
    c,t,db,m,snapshot=ready;first,_=create(c,t,snapshot);route=f"/tenders/{t}/proposal-versions/{first['id']}"
    config={**first['configuration'],'title':'Propuesta humana','bidder_name':'Participante local','sections':[{'id':'economic','type':'ECONOMIC','order':1,'included':True,'note':'Revisar presentación'}]}
    update=c.patch(route,json={'expected_edit_revision':1,'configuration':config,'actor_label':'Responsable'})
    assert update.status_code==200,update.text
    draft=update.json();assert draft['edit_revision']==2 and draft['configuration']['title']=='Propuesta humana'
    assert c.patch(route,json={'expected_edit_revision':1,'configuration':config}).status_code==409
    from tests.test_proposal_composition import finish
    composition=finish(c,t,draft)
    payload={'expected_edit_revision':2,'expected_composition_revision':composition['revision'],'acknowledge_warnings':True,'actor_label':'Responsable'}
    frozen=c.post(route+'/freeze',json=payload);assert frozen.status_code==200,frozen.text
    frozen=frozen.json();assert frozen['state']=='FROZEN' and frozen['frozen_sha256']
    assert c.post(route+'/freeze',json=payload).json()==frozen
    assert c.patch(route,json={'expected_edit_revision':3,'configuration':{**config,'title':'Silencioso'}}).status_code==409
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('UPDATE proposal_versions SET configuration=:config WHERE id=:id'),{'config':'{}','id':first['id']})
    bulk(c,m,[matrix(c,m)['rows'][0]],changes={'offered_unit_price':'16'},apply=True)
    newer,_=create_snapshot(c,t)
    second,_=create(c,t,newer,proposal_id=first['proposal_id'],previous_version_id=first['id'])
    assert second['version']==2 and second['previous_version_id']==first['id'] and second['configuration']==config
    old=read(c,route);assert old['frozen_sha256']==frozen['frozen_sha256'] and old['configuration']==config and not old['is_latest']
    audit=read(c,route+'/history');assert [e['action'] for e in audit if not e['action'].startswith('COMPOSITION_')]==['SUPERSEDED','FROZEN','CONFIGURED','CREATED']
    page=read(c,f'/tenders/{t}/proposal-versions?limit=1');assert page['items'][0]['id']==second['id']
    assert read(c,f"/tenders/{t}/proposal-versions?limit=1&before_id={page['next_before_id']}")['items'][0]['id']==first['id']


def test_m9a08_cross_tender_and_database_binding_guard(ready):
    c,t,db,m,snapshot=ready;first,_=create(c,t,snapshot)
    other=c.post('/tenders',json={'title':'Other'}).json()['id']
    assert c.post(f'/tenders/{other}/proposal-versions',json={'request_id':str(uuid4()),'snapshot_id':first['snapshot_id'],'acknowledge_warnings':True}).status_code==404
    for suffix in ['', '/inputs','/history','/source-state']:
        assert c.get(f"/tenders/{other}/proposal-versions/{first['id']}"+suffix).status_code==404
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('UPDATE proposal_versions SET snapshot_id=:id,edit_revision=2 WHERE id=:version'),{'id':str(uuid4()),'version':first['id']})
    assert c.get(f'/tenders/{uuid4()}/proposal-versions').status_code==404


def test_request_retry_and_historical_draft_guard(ready):
    c,t,db,m,snapshot=ready;first,payload=create(c,t,snapshot);route=f'/tenders/{t}/proposal-versions'
    assert c.post(route,json=payload).json()==first
    assert c.post(route,json={**payload,'actor_label':'Changed'}).status_code==409
    second,_=create(c,t,snapshot,proposal_id=first['proposal_id'],previous_version_id=first['id'])
    assert second['version']==2 and len(list(db.scalars(select(ProposalVersion))))==2
    assert c.patch(route+'/'+first['id'],json={'expected_edit_revision':1,'configuration':first['configuration']}).status_code==409
    assert c.post(route,json={**payload,'request_id':str(uuid4()),'proposal_id':first['proposal_id'],'previous_version_id':first['id']}).status_code==409
    assert c.get(route+'?limit=51').status_code==422
    assert c.get(route+'/'+first['id']+'/history?limit=101').status_code==422
    assert c.patch(route+'/'+second['id'],json={'expected_edit_revision':1,'configuration':{'offered_unit_price':'999'}}).status_code==422


def test_section_validation_and_append_only_events(ready):
    c,t,db,m,snapshot=ready;value,_=create(c,t,snapshot);route=f"/tenders/{t}/proposal-versions/{value['id']}"
    invalid={'sections':[{'id':'wrong','type':'ECONOMIC','order':1}]}
    assert c.patch(route,json={'expected_edit_revision':1,'configuration':invalid}).status_code==422
    for table in ['proposals','proposal_versions','proposal_version_events']:
        with pytest.raises(DBAPIError):
            with db.begin_nested():db.execute(text('DELETE FROM '+table))
    assert len(list(db.scalars(select(ProposalVersionEvent))))==1


def test_frozen_hash_detects_in_memory_tamper(ready):
    c,t,db,m,snapshot=ready;value,_=create(c,t,snapshot);route=f"/tenders/{t}/proposal-versions/{value['id']}"
    from tests.test_proposal_composition import finish
    composition=finish(c,t,value)
    assert c.post(route+'/freeze',json={'expected_edit_revision':1,'expected_composition_revision':composition['revision'],'acknowledge_warnings':True}).status_code==200
    row=db.get(ProposalVersion,value['id']);row.configuration={**row.configuration,'title':'Tampered'}
    assert c.get(route+'/inputs').status_code==409
    db.expire(row)
