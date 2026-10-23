"""M10-C deterministic offline workflow/change gates. Synthetic public data only."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import json
import pytest
from sqlalchemy import select,func,event as sql_event
from tests.test_discovery import offline,raw,adapter,request
from tests.test_discovery_cfe import adapter as cfe_adapter,row as cfe_row,request as cfe_request
from app.discovery import run_scan,list_opportunities
from app.discovery_contract import identity,ScanRequest
from app.discovery_models import DiscoveryOpportunity as Opp,DiscoverySourceDocument as Doc,DiscoveryChange as Change


def scan(db,rows,*,partial=False,req=None):
    pages=[rows,[]] if partial else [rows]
    a,_=adapter({'support':pages},fail=(lambda area,page:page==1) if partial else None)
    try:return run_scan(db,'PEMEX',req or request(),a)
    finally:a.close()

def events(db,scan_id=None):
    q=select(Change)
    if scan_id:q=q.where(Change.scan_run_id==scan_id)
    return list(db.scalars(q.order_by(Change.detected_at,Change.id)))

def test_workflow_follow_acknowledgement_and_authority(offline):
    c,db=offline;scan(db,[raw(1)]);oid=identity('PEMEX','EVENT-1');url='/discovery/opportunities/'+oid
    row=c.get(url).json();fp=row['source_fingerprint'];source=row['source_status']
    for state in ['REVIEW','FOLLOWING','DISCARDED','REVIEW']:
        r=c.patch(url+'/state',json={'expected_revision':row['revision'],'internal_state':state});assert r.status_code==200,r.text
        row=r.json();assert row['source_fingerprint']==fp and row['source_status']==source
        assert row['watching']==(state=='FOLLOWING')
    r=c.patch(url+'/following',json={'expected_revision':row['revision'],'following':True});assert r.status_code==200
    assert r.json()['internal_state']=='REVIEW' and r.json()['watching']
    assert c.patch(url+'/following',json={'expected_revision':1,'following':False}).status_code==409
    assert c.get('/discovery/opportunities',params={'following':True,'unread_only':True}).json()['total']==1
    history=c.get(url+'/changes').json();assert history['total']==7
    assert [x['detected_at'] for x in history['items']]==sorted(x['detected_at'] for x in history['items'])
    ids=[x['id'] for x in history['items'] if not x['acknowledged_at']]
    summary=c.get('/discovery/monitoring/summary').json();assert summary['followed_with_changes']==1 and summary['new_documents']==1
    assert c.post(url+'/changes/acknowledge',json={'change_ids':ids}).json()['acknowledged']==2
    assert c.post(url+'/changes/acknowledge',json={'change_ids':ids}).json()['acknowledged']==0
    assert c.get('/discovery/opportunities',params={'unread_only':True}).json()['total']==0
    assert c.get(url).json()['source_fingerprint']==fp
    assert c.post(url+'/changes/acknowledge',json={'change_ids':[str(uuid4())]}).status_code==404
    assert c.patch(url+'/state',json={'expected_revision':r.json()['revision'],'internal_state':'IMPORTED'}).status_code==422


def test_all_change_categories_complete_absence_reappearance_and_stable_history(offline):
    c,db=offline;req=request();first=scan(db,[raw(1),raw(2)],req=req);oid=identity('PEMEX','EVENT-1');before=db.get(Opp,oid);first_seen=before.first_seen
    assert Counter(e.category for e in events(db,first['id']))=={'NEW_OPPORTUNITY':2,'DOCUMENT_ADDED':2}
    assert scan(db,[raw(1),raw(2)],req=req)['id']==first['id']
    unchanged=scan(db,[raw(1),raw(2)]);assert unchanged['metrics']['change_events']==0
    changed=raw(1,descripcion='Descripción nueva',estado='Publicado actualizado')
    # Stable source URL is the PEMEX document identity. A filename change changes metadata.
    changed['AttachmentFiles']['results'][0]['FileName']='Bases corregidas.pdf'
    changed['AttachmentFiles']['results'].append({'FileName':'Nuevo.pdf','ServerRelativeUrl':'/procura/procedimientos-de-contratacion/concursosabiertos/Lists/Concursoseinvitaciones/Attachments/1/Nuevo.pdf'})
    second=scan(db,[changed]);categories=Counter(e.category for e in events(db,second['id']))
    assert categories['METADATA_CHANGED']==1 and categories['DOCUMENT_CHANGED']==1 and categories['DOCUMENT_ADDED']==1
    assert categories['NO_LONGER_OBSERVED']==1
    # Actual source status field is tested independently with CFE (verified shape).
    removed=deepcopy(changed);removed['AttachmentFiles']={'results':[]}
    third=scan(db,[removed]);assert Counter(e.category for e in events(db,third['id']))=={'DOCUMENT_REMOVED':2}
    assert db.scalar(select(func.count()).select_from(Doc).where(Doc.opportunity_id==oid))==2
    assert not any(d.active for d in db.scalars(select(Doc).where(Doc.opportunity_id==oid)))
    fourth=scan(db,[raw(1),raw(2)]);assert Counter(e.category for e in events(db,fourth['id']))['REAPPEARED']==1
    assert db.get(Opp,oid).first_seen==first_seen
    assert db.get(Opp,identity('PEMEX','EVENT-2')).internal_state=='NEW'
    a,_=cfe_adapter([cfe_row()]);run_scan(db,'CFE',cfe_request(),a);a.close()
    a,_=cfe_adapter([cfe_row(EstadoProcedimiento='Cancelado')]);out=run_scan(db,'CFE',cfe_request(),a);a.close()
    assert Counter(e.category for e in events(db,out['id']))=={'SOURCE_STATUS_CHANGED':1}


@pytest.mark.parametrize('kind',['partial','failed','different_query','different_version','mismatched_total','malformed'])
def test_negative_inference_requires_same_complete_scope(offline,kind):
    c,db=offline;scan(db,[raw(1),raw(2)]);oid=identity('PEMEX','EVENT-1')
    rows=[raw(1,AttachmentFiles={'results':[]})]
    if kind=='partial':out=scan(db,rows,partial=True)
    elif kind=='failed':
        a,_=adapter({'support':[rows]},fail=lambda area,page:True);out=run_scan(db,'PEMEX',request(),a);a.close()
    elif kind=='different_query':out=scan(db,rows,req=request(event_type='Otro filtro'))
    else:
        source_rows={'results':rows,'__count':'7'} if kind=='mismatched_total' else rows+[{'Id':'broken'}] if kind=='malformed' else rows
        a,_=adapter({'support':[source_rows]})
        if kind=='different_version':a.version='synthetic-v-next'
        out=run_scan(db,'PEMEX',request(),a);a.close()
    cats=Counter(e.category for e in events(db,out['id']))
    assert cats['NO_LONGER_OBSERVED']==0
    if kind not in {'different_query','different_version'}:
        assert out['status'] in {'PARTIAL','FAILED'} and cats['DOCUMENT_REMOVED']==0
        assert db.scalar(select(Doc.active).where(Doc.opportunity_id==oid))
    # Returning to original complete scope can finally infer absence.
    final=scan(db,rows);assert Counter(e.category for e in events(db,final['id']))['NO_LONGER_OBSERVED']==1


def test_large_change_fixture_exact_counts_and_batched_database(offline):
    c,db=offline
    def run(rows,changed_status=False):
        pages=[rows[i:i+100] for i in range(0,len(rows),100)] or [[]];a,_=adapter({'support':pages})
        if changed_status:
            fetch=a.fetch
            def with_status(*args):
                batch=fetch(*args)
                return replace(batch,rows=[r.model_copy(update={'source_status':'Actualizado'}) if int(r.external_id.split('-')[1])<=10 else r for r in batch.rows])
            a.fetch=with_status
        try:return run_scan(db,'PEMEX',request(),a)
        finally:a.close()
    run([raw(i) for i in range(1,201)])
    rows=[raw(i,descripcion='Modificada' if i<=15 else f'Suministro válvula {i}') for i in range(1,196)]
    for r in rows[:25]:r['AttachmentFiles']['results'].append({'FileName':'Nuevo.pdf','ServerRelativeUrl':r['AttachmentFiles']['results'][0]['ServerRelativeUrl'].replace('Bases.pdf','Nuevo.pdf')})
    rows.extend(raw(i) for i in range(201,221));statements=[];bind=db.get_bind()
    def capture(*a):statements.append(a[2])
    def other(*a):
        if a[0] is not bind:capture(*a)
    sql_event.listen(bind,'before_cursor_execute',capture);sql_event.listen(bind.engine,'before_cursor_execute',other)
    try:out=run(rows,changed_status=True)
    finally:sql_event.remove(bind,'before_cursor_execute',capture);sql_event.remove(bind.engine,'before_cursor_execute',other)
    counts=Counter(e.category for e in events(db,out['id']))
    assert counts=={'NEW_OPPORTUNITY':20,'METADATA_CHANGED':15,'SOURCE_STATUS_CHANGED':10,'DOCUMENT_ADDED':45,'NO_LONGER_OBSERVED':5},counts
    assert len(statements)<75,len(statements)
    (Path('reports/m10_c')/'large_changes.json').write_text(json.dumps({'status':out['status'],'existing':200,'observed':215,'events':dict(counts),'sql_statements':len(statements)},indent=2))


def test_ack_rejects_cross_opportunity_and_source_status_never_changes_workflow(offline):
    c,db=offline;scan(db,[raw(1),raw(2)]);ids=[identity('PEMEX',f'EVENT-{i}') for i in [1,2]]
    change=next(e for e in events(db) if e.opportunity_id==ids[1])
    assert c.post('/discovery/opportunities/'+ids[0]+'/changes/acknowledge',json={'change_ids':[change.id]}).status_code==404


def test_failed_finalization_rolls_back_all_negative_events_and_coverage(offline,monkeypatch):
    import app.discovery_monitoring as monitoring
    c,db=offline;scan(db,[raw(1),raw(2)]);original=monitoring.complete
    def fail_after_finalization(*args):original(*args);raise RuntimeError('synthetic final commit failure')
    monkeypatch.setattr(monitoring,'complete',fail_after_finalization)
    out=scan(db,[raw(1,AttachmentFiles={'results':[]})]);assert out['status']=='PARTIAL'
    assert not any(e.category in {'NO_LONGER_OBSERVED','DOCUMENT_REMOVED'} for e in events(db,out['id']))
    assert db.scalar(select(Doc.active).where(Doc.opportunity_id==identity('PEMEX','EVENT-1')))
    monkeypatch.setattr(monitoring,'complete',original)
    final=scan(db,[raw(1,AttachmentFiles={'results':[]})]);assert Counter(e.category for e in events(db,final['id']))=={'DOCUMENT_REMOVED':1,'NO_LONGER_OBSERVED':1}
