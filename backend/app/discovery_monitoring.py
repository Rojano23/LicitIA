"""Deterministic, batched Discovery observations and human audit. No Tender mutation."""
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select,update,func,exists,or_,case
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from app.discovery_contract import Opportunity,fingerprint,identity
from app.discovery_models import DiscoveryOpportunity as Opp,DiscoverySourceDocument as Doc,DiscoveryChange as Change,DiscoveryCoverage as Coverage,DiscoveryTenderLink as Link

SOURCE_CATEGORIES={'NEW_OPPORTUNITY','METADATA_CHANGED','SOURCE_STATUS_CHANGED','DOCUMENT_ADDED','DOCUMENT_CHANGED','DOCUMENT_REMOVED','NO_LONGER_OBSERVED','REAPPEARED'}
TRANSITIONS={'NEW':{'REVIEW','FOLLOWING','DISCARDED'},'REVIEW':{'NEW','FOLLOWING','DISCARDED'},'FOLLOWING':{'NEW','REVIEW','DISCARDED'},'DISCARDED':{'NEW','REVIEW'},'IMPORTED':set()}
def now():return datetime.now(timezone.utc)
def diff_value(v):
    if isinstance(v,str) and len(v)>2000:return {'excerpt':v[:2000],'sha256':fingerprint(v),'truncated':True}
    return v

def event(source,opportunity_id,category,previous,current,fields,summary,scan_id=None,actor=None):
    origin='SOURCE' if category in SOURCE_CATEGORIES else 'HUMAN'
    key=fingerprint([scan_id or str(uuid4()),opportunity_id,category,previous,current,fields]);stamp=now()
    return dict(id=identity('DISCOVERY_CHANGE',key),event_key=key,opportunity_id=opportunity_id,source_id=source,
        scan_run_id=scan_id,category=category,origin=origin,detected_at=stamp,previous_fingerprint=previous,
        current_fingerprint=current,changed_fields=fields,summary=summary,actor=actor,
        acknowledged_at=None if origin=='SOURCE' else stamp)

def save_events(db,events):
    count=0
    for start in range(0,len(events),500):
        count+=len(db.execute(insert(Change).values(events[start:start+500]).on_conflict_do_nothing(index_elements=['event_key']).returning(Change.id)).all())
    return count

def observed(db,source,scan_id,rows,old):
    ids=[identity(source,r.external_id) for r in rows]
    docs={(d.opportunity_id,d.external_id):d for d in db.scalars(select(Doc).where(Doc.opportunity_id.in_(ids)))} if ids else {}
    events=[]
    for row in rows:
        oid=identity(source,row.external_id);previous=old.get(row.external_id);before_fp=previous.fingerprint if previous else None;fp=row.source_fingerprint
        if previous is None:
            events.append(event(source,oid,'NEW_OPPORTUNITY',None,fp,{},'Nueva oportunidad observada',scan_id))
        else:
            before=Opportunity.model_validate(previous.representation).model_dump(mode='json',exclude={'raw_metadata','documents'})
            after=row.model_dump(mode='json',exclude={'raw_metadata','documents'});changed={k:{'previous':diff_value(before[k]),'current':diff_value(v)} for k,v in after.items() if before.get(k)!=v}
            status=changed.pop('source_status',None)
            if changed:events.append(event(source,oid,'METADATA_CHANGED',before_fp,fp,changed,'Cambió metadata: '+', '.join(changed),scan_id))
            if status:events.append(event(source,oid,'SOURCE_STATUS_CHANGED',before_fp,fp,{'source_status':status},'Cambió el estado publicado por la fuente',scan_id))
        for doc in row.documents:
            prior=docs.get((oid,doc.external_id));docfp=fingerprint(doc.model_dump())
            if prior is None or not prior.active:
                events.append(event(source,oid,'DOCUMENT_ADDED',prior.fingerprint if prior else None,docfp,{'document_id':identity(source,row.external_id+'\0document:'+doc.external_id),'document':doc.model_dump()},'Nueva referencia documental disponible',scan_id))
            elif prior.fingerprint!=docfp:
                fields={k:{'previous':getattr(prior,k),'current':v} for k,v in doc.model_dump().items() if getattr(prior,k)!=v}
                events.append(event(source,oid,'DOCUMENT_CHANGED',prior.fingerprint,docfp,{'document_id':prior.id,'fields':fields},'Cambió una referencia documental',scan_id))
    return events

def complete(db,source,scan_id,query,version):
    """Caller invokes only for global SUCCESS, in same transaction as final SUCCESS."""
    events=[];scope_query=query.model_dump(mode='json',exclude={'page_size'});scope_query['areas']=sorted(scope_query['areas'])
    scope=fingerprint([source,version,scope_query])
    current={r.id:r.fingerprint for r in db.scalars(select(Opp).where(Opp.source_id==source,Opp.last_scan_id==scan_id))}
    prior={r.opportunity_id:r for r in db.scalars(select(Coverage).where(Coverage.scope_sha==scope))}
    for oid,fp in current.items():
        if oid in prior and not prior[oid].present:
            events.append(event(source,oid,'REAPPEARED',None,fp,{'coverage_scope':scope,'query':scope_query},'Reapareció en el mismo filtro completo',scan_id))
    missing=[oid for oid,r in prior.items() if r.present and oid not in current]
    for oid in missing:events.append(event(source,oid,'NO_LONGER_OBSERVED',None,None,{'coverage_scope':scope,'query':scope_query},'Ya no se observa en el mismo filtro completo; no implica cancelación global',scan_id))
    values=[dict(scope_sha=scope,opportunity_id=oid,present=True,last_scan_id=scan_id) for oid in current]
    for start in range(0,len(values),500):
        stmt=insert(Coverage).values(values[start:start+500]);db.execute(stmt.on_conflict_do_update(index_elements=['scope_sha','opportunity_id'],set_={'present':True,'last_scan_id':scan_id}))
    for start in range(0,len(missing),500):db.execute(update(Coverage).where(Coverage.scope_sha==scope,Coverage.opportunity_id.in_(missing[start:start+500])).values(present=False,last_scan_id=scan_id))
    removed=list(db.scalars(select(Doc).join(Opp,Opp.id==Doc.opportunity_id).where(Opp.source_id==source,Opp.last_scan_id==scan_id,Doc.active.is_(True),or_(Doc.last_scan_id!=scan_id,Doc.last_scan_id.is_(None)))))
    for doc in removed:
        events.append(event(source,doc.opportunity_id,'DOCUMENT_REMOVED',doc.fingerprint,None,{'document_id':doc.id,'name':doc.name,'public_url':doc.public_url},'Referencia documental ausente de una observación completa; metadata histórica conservada',scan_id))
    for start in range(0,len(removed),500):db.execute(update(Doc).where(Doc.id.in_([d.id for d in removed[start:start+500]])).values(active=False))
    return save_events(db,events)

def change_view(r):
    return {k:getattr(r,k) for k in ['id','opportunity_id','source_id','scan_run_id','category','origin','detected_at','previous_fingerprint','current_fingerprint','changed_fields','summary','actor','acknowledged_at']}

def changes(db,oid,limit=100,offset=0):
    if not db.get(Opp,oid):raise HTTPException(404,'DISCOVERY_OPPORTUNITY_NOT_FOUND')
    query=select(Change).where(Change.opportunity_id==oid)
    return {'items':[change_view(r) for r in db.scalars(query.order_by(Change.detected_at,Change.id).offset(offset).limit(limit))],
        'total':db.scalar(select(func.count()).select_from(Change).where(Change.opportunity_id==oid)),'limit':limit,'offset':offset}

def acknowledge(db,oid,ids,actor):
    if len(set(ids))!=len(ids):raise HTTPException(422,'DUPLICATE_CHANGE_ID')
    rows=list(db.scalars(select(Change).where(Change.id.in_(ids))))
    if len(rows)!=len(ids) or any(r.opportunity_id!=oid for r in rows):raise HTTPException(404,'DISCOVERY_CHANGE_NOT_OWNED')
    updated=db.execute(update(Change).where(Change.id.in_(ids),Change.acknowledged_at.is_(None)).values(acknowledged_at=now()).returning(Change.id)).scalars().all()
    if updated:
        row=db.get(Opp,oid);save_events(db,[event(row.source_id,oid,'CHANGE_ACKNOWLEDGED',row.fingerprint,row.fingerprint,{'change_ids':list(updated)},'Cambios marcados como leídos',actor=actor)])
    db.commit();return {'acknowledged':len(updated)}

def workflow(db,row,state,expected,actor='LOCAL_USER',watch=None):
    if state!=row.internal_state and state not in TRANSITIONS[row.internal_state]:raise HTTPException(409,'INVALID_DISCOVERY_TRANSITION')
    watching=(state=='FOLLOWING') if watch is None else watch
    if state==row.internal_state and watching==row.watching:
        if row.revision!=expected:raise HTTPException(409,'DISCOVERY_OPPORTUNITY_STALE')
        return
    before={'internal_state':row.internal_state,'watching':row.watching}
    result=db.execute(update(Opp).where(Opp.id==row.id,Opp.revision==expected).values(internal_state=state,watching=watching,revision=Opp.revision+1))
    if result.rowcount!=1:raise HTTPException(409,'DISCOVERY_OPPORTUNITY_STALE')
    save_events(db,[event(row.source_id,row.id,'WORKFLOW_CHANGED',row.fingerprint,row.fingerprint,{'previous':before,'current':{'internal_state':state,'watching':watching}},'Decisión humana de seguimiento/estado',actor=actor)])

def unread_exists():return exists(select(Change.id).where(Change.opportunity_id==Opp.id,Change.origin=='SOURCE',Change.acknowledged_at.is_(None)))

def enrich(db,items):
    ids=[i['id'] for i in items]
    if not ids:return items
    counts={oid:(count,documents) for oid,count,documents in db.execute(select(Change.opportunity_id,func.count(),func.sum(case((Change.category.in_(['DOCUMENT_ADDED','DOCUMENT_CHANGED','DOCUMENT_REMOVED']),1),else_=0))).where(Change.opportunity_id.in_(ids),Change.origin=='SOURCE',Change.acknowledged_at.is_(None)).group_by(Change.opportunity_id)).all()}
    links={l.opportunity_id:l for l in db.scalars(select(Link).where(Link.opportunity_id.in_(ids)))}
    for i in items:
        link=links.get(i['id']);i['unread_changes'],i['unread_document_changes']=counts.get(i['id'],(0,0))
        i['linked_tender']={'id':link.tender_identity,'available':link.tender_id is not None} if link else None
        i['source_changes_available']=bool(link and link.context['source_fingerprint']!=i['source_fingerprint'])
    return items

def summary(db):
    unread=select(Change).where(Change.origin=='SOURCE',Change.acknowledged_at.is_(None)).subquery()
    return {'new_opportunities':db.scalar(select(func.count()).select_from(Opp).where(Opp.internal_state=='NEW')),
        'changed_opportunities':db.scalar(select(func.count(func.distinct(unread.c.opportunity_id)))),
        'followed_with_changes':db.scalar(select(func.count()).select_from(Opp).where(Opp.watching.is_(True),unread_exists())),
        'unread_changes':db.scalar(select(func.count()).select_from(unread)),
        'new_documents':db.scalar(select(func.count()).select_from(unread).where(unread.c.category=='DOCUMENT_ADDED'))}
