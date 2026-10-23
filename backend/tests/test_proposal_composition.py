"""M9B synthetic snapshot/overlay contracts; no blind or provider execution."""
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from app.models import ProposalComposition
from app.proposal_readiness import get_snapshot
from app.proposal_composition import canonical_rows, Content, StoredResponse, Response, completeness, _sections
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection, create as create_snapshot
from tests.test_proposal_versions import ready, create
from tests.test_readiness_work import read
from tests.test_commercial_matrix import matrix, bulk


def route(t, v): return f"/tenders/{t}/proposal-versions/{v['id']}"


def init(c, t, v):
    response = c.post(route(t, v) + '/composition/initialize', json={'origin': 'WORKSPACE'})
    assert response.status_code == 200, response.text
    return response.json()


def change(c, t, v, comp, key, response, **extra):
    result = c.patch(route(t, v) + '/composition/responses', json={'expected_revision': comp['revision'],
        'origin': 'WORKSPACE', 'changes': [{'key': key, 'response': response, **extra}]})
    assert result.status_code == 200, result.text
    return result.json()


def finish(c, t, v):
    comp = init(c, t, v)
    # Explicit synthetic human responses, never a production automatic-compliance action.
    for section, status in [('REQUIREMENTS', 'COMPLY'), ('REQUESTED_EVIDENCE', 'PROVIDED')]:
        rows = read(c, route(t,v) + '/composition?section=' + section)['rows']
        for row in rows:
            comp = change(c,t,v,comp,row['key'],{'status':status,'text':'Synthetic human declaration',
                **({'external_reference':'Local human evidence reference'} if status=='PROVIDED' else {})})
    return comp


def test_m9b01_02_03_04_05_06_07_08_09_10_11_27_28_29_authorities(ready, monkeypatch):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);before=matrix(c,m)
    readiness_before=read(c,f'/tenders/{t}/bid-readiness')
    monkeypatch.setattr('app.proposal_readiness.evaluate',lambda *a:pytest.fail('Mutable Tender read during composition'))
    comp=init(c,t,v);assert comp['snapshot_id']==v['snapshot_id'] and comp['contract_version']=='proposal-composition-v1'
    scope=next(r for r in comp['rows'] if r['section']=='TECHNICAL_SCOPE')
    assert scope['key']=='SCOPE:'+scope['canonical']['scope_id']
    updated=change(c,t,v,comp,scope['key'],{'offered_description':'Human offered wording','comment':'Technical'})
    assert next(r for r in updated['rows'] if r['key']==scope['key'])['canonical']==scope['canonical']
    req=next(r for r in updated['rows'] if r['section']=='REQUIREMENTS')
    updated=change(c,t,v,updated,req['key'],{'status':'COMPLY','text':'Human answer'})
    answer=next(r for r in updated['rows'] if r['key']==req['key'])
    assert answer['canonical']==req['canonical'] and answer['response']['text']=='Human answer'
    assert answer['canonical']['text_state']=='MATERIALIZED' and answer['declaration_authority']=='USER_DECLARATION_NOT_CERTIFICATION'
    evidence=next(r for r in updated['rows'] if r['section']=='REQUESTED_EVIDENCE')
    updated=change(c,t,v,updated,evidence['key'],{'status':'PROVIDED','document_id':snapshot['payload']['projection']['documents'][0]['id']})
    econ=next(r for r in updated['rows'] if r['section']=='ECONOMIC')
    canonical=next(r for r in snapshot['payload']['projection']['rows'] if r['scope_id']==econ['canonical']['scope_id'])
    assert econ['canonical']==canonical
    for response in [{'description':'overwrite'},{'offered_unit_price':'999'},{'status':'COMPLY'}]:
        result=c.patch(route(t,v)+'/composition/responses',json={'expected_revision':updated['revision'],'changes':[{'key':econ['key'],'response':response}]})
        assert result.status_code==422
    assert matrix(c,m)==before and read(c,f'/tenders/{t}/bid-readiness')==readiness_before
    assert read(c,route(t,v)+'/composition')['sha256']==updated['sha256']
    assert init(c,t,v)['sha256']==updated['sha256']


def test_m9b12_13_14_20_settings_and_currency(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=init(c,t,v)
    sections=[{'id':'economic','order':1,'included':False,'note':'Presentation decision'}, {'id':'technical_scope','order':1}]
    item={'id':str(uuid4()),'kind':'ASSUMPTION','text':'Human assumption'}
    result=c.patch(route(t,v)+'/composition/settings',json={'expected_revision':1,'sections':sections,'items':[item]})
    assert result.status_code==200,result.text
    comp=result.json();assert comp['sections'][:2][0]['id']=='identification' # default order 0
    tied=[s['id'] for s in comp['sections'] if s['order']==1];assert tied==['economic','technical_scope']
    assert not next(s for s in comp['sections'] if s['id']=='economic')['included']
    assert read(c,route(t,v)+'/composition')['items'][0]['text']=='Human assumption'
    stored=get_snapshot(db,t,v['snapshot_id']).model_copy(deep=True)
    stored.payload.projection.rows[0].currency='USD';stored.payload.projection.rows[1].currency='MXN'
    rows=canonical_rows(stored);assert {r['canonical']['currency'] for r in rows.values() if r['section']=='ECONOMIC'}=={'USD','MXN'}
    for row in rows.values():
        if row['section']=='ECONOMIC':
            original=next(r for r in snapshot['payload']['projection']['rows'] if r['commercial_line_id']==row['canonical']['commercial_line_id'])
            assert row['canonical']['offered_total']==original['offered_total']


def test_m9b15_16_17_18_stable_revision_reconciliation(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=finish(c,t,v)
    scope=next(r for r in comp['rows'] if r['section']=='TECHNICAL_SCOPE')
    comp=change(c,t,v,comp,scope['key'],{'offered_description':'Preserved human response'})
    econ=next(r for r in comp['rows'] if r['section']=='ECONOMIC')
    comp=change(c,t,v,comp,econ['key'],{'note':'Price acknowledged'})
    original=read(c,route(t,v)+'/composition')
    bulk(c,m,[next(r for r in matrix(c,m)['rows'] if r['commercial_line_id']==econ['canonical']['commercial_line_id'])],changes={'offered_unit_price':'15'},apply=True)
    newer,_=create_snapshot(c,t);second,_=create(c,t,newer,proposal_id=v['proposal_id'],previous_version_id=v['id'])
    cloned=init(c,t,second)
    copied=next(r for r in cloned['rows'] if r['key']==scope['key']);assert copied['response']['offered_description']=='Preserved human response' and copied['source_match']=='SAME_SOURCE'
    # Commercial price changes do not invalidate Scope wording; do invalidate a copied economic note.
    changed=[r for r in cloned['rows'] if r['review_required']];assert len(changed)==1 and changed[0]['section']=='ECONOMIC'
    assert read(c,route(t,v)+'/composition')['sha256']==original['sha256']
    cloned=change(c,t,second,cloned,changed[0]['key'],changed[0]['response'],acknowledge_source_change=True)
    assert not any(r['review_required'] for r in cloned['rows'])
    # Pure ID-keyed policy: new IDs never inherit text, removed IDs never appear in canonical rows.
    stored=get_snapshot(db,t,second['snapshot_id']).model_copy(deep=True)
    old=stored.payload.projection.rows[0].scope_id;new=str(uuid4())
    stored.payload.projection.rows[0].scope_id=new;stored.payload.projection.rows[0].quantity_scope_id=new
    rows=canonical_rows(stored);assert 'SCOPE:'+old not in rows and 'SCOPE:'+new in rows


def test_m9b19_cross_tender_and_unknown_source(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=init(c,t,v)
    other=c.post('/tenders',json={'title':'Other'}).json()['id']
    assert c.get(route(other,v)+'/composition').status_code==404
    for payload in [{'key':'SCOPE:'+str(uuid4()),'response':{}}, {'key':comp['rows'][0]['key'],'response':{'document_id':str(uuid4())}}]:
        assert c.patch(route(t,v)+'/composition/responses',json={'expected_revision':1,'changes':[payload]}).status_code==422
    assert c.patch(route(t,v)+'/composition/settings',json={'expected_revision':1,'items':[{'id':str(uuid4()),'kind':'ANNEX_REFERENCE','text':'Invalid','document_id':str(uuid4())}]}).status_code==422


def test_m9b21_22_23_24_25_26_freeze_and_reviews(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot)
    payload={'expected_edit_revision':1,'acknowledge_warnings':True}
    assert c.post(route(t,v)+'/freeze',json=payload).status_code==409
    comp=init(c,t,v);payload['expected_composition_revision']=comp['revision']
    assert comp['summary']['status']=='INCOMPLETE' and any(s['pending_count'] for s in comp['summary']['sections'])
    assert c.post(route(t,v)+'/freeze',json=payload).status_code==409
    comp=finish(c,t,v);assert comp['summary']['status']=='COMPLETE'
    req=next(r for r in comp['rows'] if r['section']=='REQUIREMENTS')
    comp=change(c,t,v,comp,req['key'],{'status':'EXCEPTION','reason':'Human decision'})
    payload['expected_composition_revision']=comp['revision']
    assert c.post(route(t,v)+'/freeze',json=payload).status_code==409
    frozen=c.post(route(t,v)+'/freeze',json={**payload,'acknowledge_composition_review':True})
    assert frozen.status_code==200,frozen.text
    assert c.patch(route(t,v)+'/composition/responses',json={'expected_revision':comp['revision'],'changes':[{'key':req['key'],'response':{}}]}).status_code==409
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('UPDATE proposal_compositions SET revision=revision+1 WHERE version_id=:id'),{'id':v['id']})
    second,_=create(c,t,snapshot,proposal_id=v['proposal_id'],previous_version_id=v['id']);init(c,t,second)
    assert read(c,route(t,v)+'/composition')['sha256']==comp['sha256']
    assert read(c,route(t,v))['frozen_sha256']==frozen.json()['frozen_sha256']


def test_atomic_bounded_bulk_audit_and_stale(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=init(c,t,v)
    keys=[r['key'] for r in comp['rows'] if r['section']=='REQUIREMENTS']
    payload={'expected_revision':1,'origin':'WORKSPACE','changes':[{'key':k,'response':{'status':'COMPLY'}} for k in keys]}
    result=c.patch(route(t,v)+'/composition/responses',json=payload);assert result.status_code==200
    assert c.patch(route(t,v)+'/composition/responses',json=payload).status_code==409
    payload['expected_revision']=result.json()['revision'];payload['changes'].append({'key':'SCOPE:'+str(uuid4()),'response':{}})
    assert c.patch(route(t,v)+'/composition/responses',json=payload).status_code==422
    assert read(c,route(t,v)+'/composition')['sha256']==result.json()['sha256']
    audit=read(c,route(t,v)+'/history');assert audit[0]['action']=='COMPOSITION_UPDATED' and audit[0]['details']['origin']=='WORKSPACE'
    assert audit[0]['details']['previous']!=audit[0]['details']['current']
    payload['changes']=[{'key':str(i),'response':{}} for i in range(51)]
    assert c.patch(route(t,v)+'/composition/responses',json=payload).status_code==422
    assert c.get(route(t,v)+'/composition?limit=201').status_code==422


def test_m9b30_bounded_queries_and_large_pure_contract(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);init(c,t,v)
    statements=[]
    def collect(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    engine=db.get_bind().engine;event.listen(engine,'before_cursor_execute',collect)
    try:value=read(c,route(t,v)+'/composition?section=ECONOMIC&limit=1')
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert len(value['rows'])==1 and value['next_offset']==1
    assert len(statements)<=5 and not any('FROM tender_scope' in s or 'FROM requirements' in s for s in statements)
    stored=get_snapshot(db,t,v['snapshot_id']).model_copy(deep=True)
    source=stored.payload.projection.rows[0]
    for _ in range(998):
        row=source.model_copy(deep=True);row.scope_id=str(uuid4());row.quantity_scope_id=row.scope_id;row.commercial_line_id=str(uuid4());stored.payload.projection.rows.append(row)
    assert len([r for r in canonical_rows(stored).values() if r['section']=='TECHNICAL_SCOPE'])==1000
    small_selects=len(statements)
    def expand(p):p['rows']=[r.model_dump(mode='json') for r in stored.payload.projection.rows]
    large_snapshot=synthetic_snapshot(db,snapshot,expand)
    large_version,_=create(c,t,large_snapshot,acknowledge_stale=True)
    init(c,t,large_version);statements.clear()
    event.listen(engine,'before_cursor_execute',collect)
    try:large=read(c,route(t,large_version)+'/composition?section=TECHNICAL_SCOPE&offset=975&limit=25')
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert large['total']==1000 and len(large['rows'])==25 and large['next_offset'] is None
    assert len(statements)<=small_selects+1
    import json
    from pathlib import Path
    Path('reports/m9_b').mkdir(parents=True,exist_ok=True)
    Path('reports/m9_b/query_scaling.json').write_text(json.dumps({'small_scopes':2,'large_scopes':1000,
        'small_selects':small_selects,'large_selects':len(statements),'page_rows':len(large['rows'])},indent=2)+'\n')


def synthetic_snapshot(db, snapshot, mutate):
    """New synthetic immutable snapshot, never UPDATE a snapshot or inspect a corpus."""
    from app.models import ProposalReadinessSnapshot
    from app.proposal_readiness import SnapshotPayload, state_fingerprint, digest
    from datetime import datetime, timezone
    payload=deepcopy(snapshot['payload']);mutate(payload['projection'])
    payload.update(snapshot_id=str(uuid4()),request_id=str(uuid4()),created_at=datetime.now(timezone.utc).isoformat())
    from app.proposal_readiness import ProposalReadinessProjection
    payload['input_sha256']=state_fingerprint(ProposalReadinessProjection.model_validate(payload['projection']))
    typed=SnapshotPayload.model_validate(payload);payload=typed.model_dump(mode='json')
    stored=ProposalReadinessSnapshot(id=payload['snapshot_id'],tender_id=payload['tender_id'],request_id=payload['request_id'],
        request_sha256=payload['request_sha256'],created_at=typed.created_at,actor_label=typed.actor_label,
        input_sha256=payload['input_sha256'],payload_sha256=digest(payload),payload=payload)
    db.add(stored);db.flush()
    return {'payload':payload,'payload_sha256':stored.payload_sha256}


def test_actual_revision_changed_requirement_new_removed_rows(ready,monkeypatch):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=finish(c,t,v)
    scope=next(r for r in comp['rows'] if r['section']=='TECHNICAL_SCOPE')
    comp=change(c,t,v,comp,scope['key'],{'offered_description':'Must not migrate by index'})
    req=next(r for r in comp['rows'] if r['section']=='REQUIREMENTS')
    removed_id=scope['canonical']['scope_id'];new_id=str(uuid4());req_id=req['canonical']['id']
    def mutate(p):
        old=next(r for r in p['rows'] if r['scope_id']==removed_id)
        old['scope_id']=new_id;old['quantity_scope_id']=new_id;old['commercial_line_id']=str(uuid4());old['description']='Synthetic new scope'
        next(r for r in p['requirement_representations'] if r['requirement_id']==req_id)['representation_fingerprint']='f'*64
        original=next(r for r in p['tracked_context'] if r['entity_type']=='REQUIREMENT')
        new=deepcopy(original);new['id']=str(uuid4());new['entity_id']=str(uuid4());p['tracked_context'].append(new)
        p['requirement_representations'].append({'requirement_id':new['entity_id'],'representation_fingerprint':'f'*64})
    newer=synthetic_snapshot(db,snapshot,mutate)
    # Synthetic matching source adapter for this deliberately synthetic snapshot.
    from app.requirement_matrix import get_tender_requirement_matrix
    live=get_tender_requirement_matrix(db,t)
    target=next(r for r in live['requirements'] if r['requirement_id']==req_id)
    target['representation_fingerprint']='f'*64
    extra=deepcopy(target);extra['expected_evidence']=[]
    added=next(r for r in newer['payload']['projection']['tracked_context'] if r['entity_type']=='REQUIREMENT' and r['entity_id'] not in {x['requirement_id'] for x in live['requirements']})
    extra['requirement_id']=added['entity_id'];extra['representation_fingerprint']=target['representation_fingerprint']
    # Snapshot helper is immutable: append the new representation during mutation instead below.
    live['requirements'].append(extra)
    monkeypatch.setattr('app.requirement_matrix.get_tender_requirement_matrix',lambda *a:live)
    second,_=create(c,t,newer,proposal_id=v['proposal_id'],previous_version_id=v['id'],acknowledge_stale=True)
    result=init(c,t,second)
    assert scope['key'] in result['removed_keys'] and scope['key'] not in {r['key'] for r in result['rows']}
    new=next(r for r in result['rows'] if r['key']=='SCOPE:'+new_id)
    assert new['response']['offered_description']=='' and new['source_match']=='NEW'
    changed=next(r for r in result['rows'] if r['key']==req['key'])
    assert changed['response']['text']=='Synthetic human declaration' and changed['source_match']=='SOURCE_CHANGED' and changed['review_required']
    assert any(r['section']=='REQUIREMENTS' and r['source_match']=='NEW' and r['response']['status']=='PENDING' for r in result['rows'])
    assert result['summary']['blocking_review'] and result['summary']['hard_incomplete']
    completed=finish(c,t,second)
    freeze=c.post(route(t,second)+'/freeze',json={'expected_edit_revision':1,'expected_composition_revision':completed['revision'],
        'acknowledge_warnings':True,'acknowledge_stale':True,'acknowledge_composition_review':True})
    assert freeze.status_code==409 and 'COMPOSITION_REVIEW_UNRESOLVED' in freeze.text


def test_evidence_pending_reference_and_section_cannot_hide(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=finish(c,t,v)
    evidence=next(r for r in comp['rows'] if r['section']=='REQUESTED_EVIDENCE')
    comp=change(c,t,v,comp,evidence['key'],{'status':'PROVIDED'})
    assert any(r['code']=='EVIDENCE_REFERENCE_REQUIRED' for r in comp['summary']['hard_incomplete'])
    result=c.patch(route(t,v)+'/composition/settings',json={'expected_revision':comp['revision'],
        'sections':[{'id':'requested_evidence','order':10,'included':False,'note':'Human presentation choice'}]})
    assert result.status_code==200
    comp=result.json();assert comp['summary']['hard_incomplete']
    payload={'expected_edit_revision':1,'expected_composition_revision':comp['revision'],'acknowledge_warnings':True,'acknowledge_composition_review':True}
    assert c.post(route(t,v)+'/freeze',json=payload).status_code==409
    comp=change(c,t,v,comp,evidence['key'],{'status':'NOT_APPLICABLE','reason':'Human explanation'})
    payload['expected_composition_revision']=comp['revision']
    assert c.post(route(t,v)+'/freeze',json=payload).status_code==200


def test_frozen_composition_hash_and_database_identity_guard(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=finish(c,t,v)
    assert c.post(route(t,v)+'/freeze',json={'expected_edit_revision':1,'expected_composition_revision':comp['revision'],'acknowledge_warnings':True}).status_code==200
    stored=db.get(ProposalComposition,v['id']);content=deepcopy(stored.content)
    first=next(iter(content['responses']));content['responses'][first]['response']['text']='Tampered'
    stored.content=content
    assert c.get(route(t,v)+'/composition').status_code==409
    db.expire(stored)
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.execute(text('DELETE FROM proposal_compositions WHERE version_id=:id'),{'id':v['id']})


def test_legacy_frozen_envelope_remains_valid_without_composition(ready):
    from datetime import datetime,timezone
    from app.models import ProposalVersion
    from app.proposal_versions import frozen_envelope
    from app.proposal_readiness import digest
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot)
    row=db.get(ProposalVersion,v['id']);row.state='FROZEN';row.edit_revision+=1
    row.frozen_at=datetime.now(timezone.utc);row.updated_at=row.frozen_at
    legacy_request={'expected_edit_revision':1,'acknowledge_warnings':True,'acknowledge_stale':False,'actor_label':None}
    row.freeze_acknowledgements={'request_sha256':digest(legacy_request),'warnings':True,'stale':False,'source_state':'CURRENT'}
    row.frozen_sha256=digest(frozen_envelope(row));db.flush()
    assert read(c,route(t,v))['frozen_sha256']==row.frozen_sha256
    assert c.post(route(t,v)+'/freeze',json=legacy_request).status_code==200
    assert c.post(route(t,v)+'/freeze',json={**legacy_request,'actor_label':'Different'}).status_code==409
    assert not read(c,route(t,v)+'/composition')['initialized']
    assert c.post(route(t,v)+'/composition/initialize',json={}).status_code==409
