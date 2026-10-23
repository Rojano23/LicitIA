"""Local Discovery application services. Never imports Tender Analysis engines."""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4
from contextlib import contextmanager
from sqlalchemy import select,update,text,case,func,or_
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from app.discovery_models import DiscoverySource,DiscoveryProfile,DiscoveryOpportunity,DiscoverySourceDocument,DiscoveryScanRun
from app.discovery_contract import Profile,Opportunity,fingerprint,identity,match_profile
from app.discovery_pemex import PEMEXConcursosAdapter,AREAS

MAX_BATCHES=2000
MAX_UNIQUE=100000

def now():return datetime.now(timezone.utc)
def adapter_for(source):
    if source!='PEMEX':raise HTTPException(422,'UNSUPPORTED_DISCOVERY_SOURCE')
    return PEMEXConcursosAdapter()

def bootstrap(db):
    db.execute(insert(DiscoverySource).values(id='PEMEX',name='PEMEX Concursos Abiertos',base_url='https://www.pemex.com',
        adapter_version=PEMEXConcursosAdapter.version,enabled=True,configuration={'areas':list(AREAS)}).on_conflict_do_nothing())
    db.flush()

def source_view(row):
    return {'id':row.id,'source_type':'PUBLIC_PROCUREMENT','name':row.name,'base_url':row.base_url,'enabled':row.enabled,
        'adapter_version':row.adapter_version,'configuration':row.configuration,'last_scan_state':row.last_scan_state,
        'last_successful_scan':row.last_successful_scan,'last_error':row.last_error,
        'capabilities':PEMEXConcursosAdapter.capabilities() if row.id=='PEMEX' else {},
        'areas':[{'key':k,**v} for k,v in AREAS.items()] if row.id=='PEMEX' else []}

def list_sources(db):
    bootstrap(db);db.commit();return [source_view(s) for s in db.scalars(select(DiscoverySource).order_by(DiscoverySource.id))]

def get_source(db,source):
    bootstrap(db);row=db.get(DiscoverySource,source)
    if row is None:raise HTTPException(404,'DISCOVERY_SOURCE_NOT_FOUND')
    return row

def configure_source(db,source,request):
    row=get_source(db,source)
    if source!='PEMEX' or set(request.areas)-set(AREAS) or len(set(request.areas))!=len(request.areas):raise HTTPException(422,'UNSUPPORTED_SOURCE_AREAS')
    row.enabled=request.enabled;row.configuration={'areas':request.areas};db.commit();return source_view(row)

@contextmanager
def source_lock(db,source):
    # Dedicated connection retains the session-level lock across per-page commits.
    with db.get_bind().engine.connect() as connection:
        acquired=connection.execute(text('SELECT pg_try_advisory_lock(hashtext(:key))'),{'key':'discovery:'+source}).scalar()
        if not acquired:raise HTTPException(409,'DISCOVERY_SCAN_IN_PROGRESS')
        try:yield
        finally:connection.execute(text('SELECT pg_advisory_unlock(hashtext(:key))'),{'key':'discovery:'+source})

def scan_view(run):
    return {'id':run.id,'source_id':run.source_id,'request_id':run.request_id,'query':run.query,'adapter_version':run.adapter_version,
        'status':run.status,'started_at':run.started_at,'finished_at':run.finished_at,'metrics':run.metrics}

def get_scan(db,scan_id):
    row=db.get(DiscoveryScanRun,scan_id)
    if row is None:raise HTTPException(404,'DISCOVERY_SCAN_NOT_FOUND')
    return scan_view(row)

def persist_batch(db,source,rows,seen):
    stamp=now();values=[];documents=[];counts={'new':0,'updated':0,'unchanged':0,'duplicates':0,'conflicting_duplicates':0}
    accepted=[]
    for row in rows:
        key=row.external_id;fp=row.source_fingerprint
        if key in seen:
            counts['duplicates']+=1
            if seen[key]!=fp:counts['conflicting_duplicates']+=1
            continue
        seen[key]=fp;accepted.append(row)
    if not accepted:return counts
    existing={r.external_id:r.fingerprint for r in db.scalars(select(DiscoveryOpportunity).where(
        DiscoveryOpportunity.source_id==source,DiscoveryOpportunity.external_id.in_([r.external_id for r in accepted])))}
    for row in accepted:
        fp=row.source_fingerprint;key=row.external_id;oid=identity(source,key)
        counts['new' if key not in existing else 'unchanged' if existing[key]==fp else 'updated']+=1
        values.append(dict(id=oid,source_id=source,external_id=key,business_area=row.business_area,published_date=row.published_date,
            representation=row.model_dump(mode='json'),fingerprint=fp,first_seen=stamp,last_seen=stamp,internal_state='NEW',revision=1))
        for doc in row.documents:
            documents.append(dict(id=identity(source,key+'\0document:'+doc.external_id),opportunity_id=oid,
                external_id=doc.external_id,name=doc.name,public_url=doc.public_url,fingerprint=fingerprint(doc.model_dump()),observed_at=stamp))
    table=DiscoveryOpportunity;statement=insert(table).values(values);incoming=statement.excluded
    changed=table.fingerprint!=incoming.fingerprint
    db.execute(statement.on_conflict_do_update(index_elements=['source_id','external_id'],set_={
        'representation':incoming.representation,'business_area':incoming.business_area,'published_date':incoming.published_date,
        'fingerprint':incoming.fingerprint,'last_seen':incoming.last_seen,
        'previous_fingerprint':case((changed,table.fingerprint),else_=table.previous_fingerprint),
        'last_changed':case((changed,stamp),else_=table.last_changed),'revision':table.revision+case((changed,1),else_=0)}))
    # Bounded chunks avoid PostgreSQL parameter limits when a page has many attachments.
    for start in range(0,len(documents),500):
        statement=insert(DiscoverySourceDocument).values(documents[start:start+500]);incoming=statement.excluded
        db.execute(statement.on_conflict_do_update(index_elements=['opportunity_id','external_id'],set_={
            'name':incoming.name,'public_url':incoming.public_url,'fingerprint':incoming.fingerprint,'observed_at':incoming.observed_at}))
    return counts


def run_scan(db,source,request,adapter=None):
    configured=get_source(db,source)
    if not configured.enabled:raise HTTPException(409,'DISCOVERY_SOURCE_DISABLED')
    if set(request.query.areas)-set(configured.configuration['areas']):raise HTTPException(422,'AREA_NOT_ENABLED')
    request_hash=fingerprint(request.model_dump(mode='json'))
    with source_lock(db,source):
        previous=db.scalar(select(DiscoveryScanRun).where(DiscoveryScanRun.source_id==source,DiscoveryScanRun.request_id==str(request.request_id)))
        if previous:
            if previous.request_sha256!=request_hash:raise HTTPException(409,'SCAN_REQUEST_REUSED')
            return scan_view(previous)
        # Holding source lock proves earlier RUNNING process no longer owns acquisition.
        for stale in db.scalars(select(DiscoveryScanRun).where(DiscoveryScanRun.source_id==source,DiscoveryScanRun.status=='RUNNING')):
            stale.status='PARTIAL' if stale.metrics.get('unique_opportunities',0) else 'FAILED';stale.finished_at=now()
            stale.metrics={**stale.metrics,'interruption':'PREVIOUS_SCAN_INTERRUPTED_RETRY_WITH_NEW_REQUEST'}
        owned=adapter is None;adapter=adapter or adapter_for(source)
        if adapter.source_id!=source:raise HTTPException(422,'ADAPTER_SOURCE_MISMATCH')
        run=DiscoveryScanRun(id=str(uuid4()),source_id=source,request_id=str(request.request_id),request_sha256=request_hash,
            query=request.query.model_dump(mode='json'),adapter_version=adapter.version,status='RUNNING',started_at=now(),metrics={})
        db.add(run);db.flush();run_id=run.id;db.commit()
        metrics={'pages_attempted':0,'pages_completed':0,'rows_retrieved':0,'unique_opportunities':0,
            'new':0,'updated':0,'unchanged':0,'duplicates':0,'malformed_rows':0,'document_references':0,
            'areas':{},'diagnostics':[],'diagnostics_truncated':0,'consistency':'BEST_EFFORT_NO_REMOTE_SNAPSHOT'}
        seen={};issue_count=0
        def issue(area,code,**context):
            nonlocal issue_count
            issue_count+=1
            if len(metrics['diagnostics'])<100:metrics['diagnostics'].append({'area':area,'code':code,**context})
            else:metrics['diagnostics_truncated']+=1
        try:
            for area in request.query.areas:
                detail={'pages_attempted':0,'pages_completed':0,'rows_retrieved':0,'unique_records':0,
                    'source_reported_total':None,'terminal_observed':False,'status':'RUNNING'}
                metrics['areas'][area]=detail;cursor=None;visited=set();area_seen=set();start_issues=issue_count
                for page_number in range(1,MAX_BATCHES+1):
                    detail['pages_attempted']+=1;metrics['pages_attempted']+=1
                    try:
                        batch=adapter.fetch(request.query,area,cursor)
                        if not isinstance(batch.raw_count,int) or batch.raw_count<len(batch.rows) or batch.raw_count>request.query.page_size:
                            raise ValueError('INVALID_ADAPTER_BATCH_COUNT')
                        if batch.source_total is not None and (not isinstance(batch.source_total,int) or batch.source_total<0):
                            raise ValueError('INVALID_ADAPTER_SOURCE_TOTAL')
                    except Exception as exc:
                        # External parser/transport failure is recorded without remote body/URLs/secrets.
                        issue(area,'ACQUISITION_FAILED',page=page_number,cursor_sha256=fingerprint(cursor),error_type=type(exc).__name__)
                        break
                    detail['pages_completed']+=1;metrics['pages_completed']+=1
                    detail['rows_retrieved']+=batch.raw_count;metrics['rows_retrieved']+=batch.raw_count
                    if batch.source_total is not None:
                        if detail['source_reported_total'] is not None and detail['source_reported_total']!=batch.source_total:issue(area,'SOURCE_TOTAL_CHANGED')
                        detail['source_reported_total']=batch.source_total
                    for problem in batch.issues:
                        issue(area,str(problem.get('code','PARSER_ISSUE')),page=page_number)
                        if problem.get('code')=='MALFORMED_ROW':metrics['malformed_rows']+=1
                    if len(seen)+len(batch.rows)>MAX_UNIQUE:issue(area,'UNIQUE_RECORD_LIMIT');break
                    added_keys={row.external_id for row in batch.rows if row.external_id not in seen}
                    try:
                        counts=persist_batch(db,source,batch.rows,seen)
                        if counts['conflicting_duplicates']:issue(area,'CONFLICTING_DUPLICATE_REPRESENTATION',count=counts['conflicting_duplicates'])
                        pending_metrics=deepcopy(metrics)
                        for field in ['new','updated','unchanged','duplicates']:pending_metrics[field]+=counts[field]
                        pending_metrics['unique_opportunities']=len(seen)
                        pending_metrics['document_references']+=sum(len(row.documents) for row in batch.rows)
                        pending_metrics['areas'][area]['unique_records']=len(area_seen|{row.external_id for row in batch.rows})
                        run=db.get(DiscoveryScanRun,run_id);run.metrics=pending_metrics;db.commit()
                        # Publish counters/identities only after the page transaction commits.
                        metrics.update(pending_metrics);detail=metrics['areas'][area]
                        area_seen.update(row.external_id for row in batch.rows)
                    except Exception:
                        db.rollback()
                        for key in added_keys:seen.pop(key,None)
                        raise
                    if batch.terminal:
                        if batch.next_cursor:issue(area,'TERMINAL_WITH_CONTINUATION')
                        else:detail['terminal_observed']=True
                        break
                    if not batch.next_cursor:issue(area,'MISSING_TERMINAL_OR_CONTINUATION');break
                    if batch.next_cursor in visited:issue(area,'CONTINUATION_CYCLE');break
                    visited.add(batch.next_cursor);cursor=batch.next_cursor
                else:issue(area,'BATCH_LIMIT_WITH_REMAINING_RESULTS')
                if not detail['terminal_observed'] and issue_count==start_issues:issue(area,'RESULT_SET_NOT_COMPLETE')
                if detail['source_reported_total'] is not None and len(area_seen)!=detail['source_reported_total']:
                    issue(area,'SOURCE_TOTAL_MISMATCH',expected=detail['source_reported_total'],retrieved=len(area_seen))
                detail['status']='SUCCESS' if issue_count==start_issues and detail['terminal_observed'] else 'PARTIAL' if area_seen else 'FAILED'
            status='SUCCESS' if all(a['status']=='SUCCESS' for a in metrics['areas'].values()) else 'PARTIAL' if seen else 'FAILED'
        except Exception as exc:
            db.rollback();issue('CORE','PERSISTENCE_OR_CORE_FAILURE',error_type=type(exc).__name__)
            status='PARTIAL' if metrics['unique_opportunities'] else 'FAILED'
            for detail in metrics['areas'].values():
                if detail['status']=='RUNNING':detail['status']='PARTIAL' if detail['unique_records'] else 'FAILED'
        finally:
            if owned:adapter.close()
        run=db.get(DiscoveryScanRun,run_id);run.metrics=metrics;run.status=status;run.finished_at=now()
        configured=db.get(DiscoverySource,source);configured.last_scan_state=status
        configured.last_error=None if status=='SUCCESS' else 'DISCOVERY_INCOMPLETE_SEE_SCAN_DIAGNOSTICS'
        if status=='SUCCESS':configured.last_successful_scan=run.finished_at
        db.commit();return scan_view(run)


def profile_view(row):return {'id':row.id,'revision':row.revision,**row.configuration}
def save_profile(db,request,profile_id=None):
    row=db.get(DiscoveryProfile,profile_id) if profile_id else None
    if profile_id and row is None:raise HTTPException(404,'DISCOVERY_PROFILE_NOT_FOUND')
    data=request.model_dump(mode='json',exclude={'expected_revision'})
    if row:
        result=db.execute(update(DiscoveryProfile).where(DiscoveryProfile.id==profile_id,DiscoveryProfile.revision==request.expected_revision)
            .values(name=request.name,active=request.active,configuration=data,revision=DiscoveryProfile.revision+1))
        if result.rowcount!=1:raise HTTPException(409,'DISCOVERY_PROFILE_STALE')
    else:
        row=DiscoveryProfile(id=str(uuid4()),name=request.name,active=request.active,revision=1,configuration=data);db.add(row)
    db.commit();db.refresh(row);return profile_view(row)

def opportunity_view(row,profile=None):
    value=Opportunity.model_validate(row.representation)
    return {'id':row.id,'source_id':row.source_id,**value.model_dump(mode='json'),'internal_state':row.internal_state,
        'first_seen':row.first_seen,'last_seen':row.last_seen,'source_fingerprint':row.fingerprint,
        'previous_fingerprint':row.previous_fingerprint,'last_changed':row.last_changed,'revision':row.revision,
        'document_count':len(value.documents),'documents_state':'REFERENCES_DISCOVERED_NOT_DOWNLOADED',
        'match':match_profile(profile,row.source_id,value) if profile else None}

def list_opportunities(db,*,source=None,area=None,published_from=None,published_to=None,event_type=None,supply_type=None,
        source_status=None,internal_state=None,search=None,profile_id=None,matched_only=False,limit=50,offset=0):
    if not 1<=limit<=200 or offset<0:raise HTTPException(422,'INVALID_DISCOVERY_PAGE')
    query=select(DiscoveryOpportunity)
    if source:query=query.where(DiscoveryOpportunity.source_id==source)
    if area:query=query.where(DiscoveryOpportunity.business_area==area)
    if published_from:query=query.where(DiscoveryOpportunity.published_date>=published_from)
    if published_to:query=query.where(DiscoveryOpportunity.published_date<=published_to)
    if internal_state:query=query.where(DiscoveryOpportunity.internal_state==internal_state)
    for field,value in [('event_type',event_type),('supply_type',supply_type),('source_status',source_status)]:
        if value:query=query.where(DiscoveryOpportunity.representation[field].as_string()==value)
    if search:
        escaped=search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(or_(DiscoveryOpportunity.external_id.ilike('%'+escaped+'%',escape='\\'),
            DiscoveryOpportunity.representation['title'].as_string().ilike('%'+escaped+'%',escape='\\'),
            DiscoveryOpportunity.representation['description'].as_string().ilike('%'+escaped+'%',escape='\\')))
    profile=None
    if profile_id:
        row=db.get(DiscoveryProfile,profile_id)
        if not row:raise HTTPException(404,'DISCOVERY_PROFILE_NOT_FOUND')
        profile=Profile.model_validate(row.configuration)
    if matched_only and not profile:raise HTTPException(422,'PROFILE_REQUIRED')
    query=query.order_by(DiscoveryOpportunity.published_date.desc().nullslast(),DiscoveryOpportunity.first_seen.desc(),DiscoveryOpportunity.id)
    # Matching over the entire local result stream, never just the first UI/source page.
    if profile:
        total=0;items=[]
        for row in db.scalars(query.execution_options(yield_per=200)):
            value=opportunity_view(row,profile)
            if matched_only and not value['match']['matched']:continue
            if offset<=total<offset+limit:items.append(value)
            total+=1
        return {'items':items,'total':total,'limit':limit,'offset':offset,'match_scope':'ALL_LOCAL_FILTERED_RESULTS_SCAN_COMPLETENESS_REPORTED_SEPARATELY'}
    total=db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {'items':[opportunity_view(r) for r in db.scalars(query.offset(offset).limit(limit))],'total':total,'limit':limit,'offset':offset}

def get_opportunity(db,opportunity_id):
    row=db.get(DiscoveryOpportunity,opportunity_id)
    if row is None:raise HTTPException(404,'DISCOVERY_OPPORTUNITY_NOT_FOUND')
    return opportunity_view(row)

def change_workflow(db,opportunity_id,request):
    row=db.get(DiscoveryOpportunity,opportunity_id)
    if not row:raise HTTPException(404,'DISCOVERY_OPPORTUNITY_NOT_FOUND')
    result=db.execute(update(DiscoveryOpportunity).where(DiscoveryOpportunity.id==opportunity_id,DiscoveryOpportunity.revision==request.expected_revision)
        .values(internal_state=request.internal_state,revision=DiscoveryOpportunity.revision+1))
    if result.rowcount!=1:raise HTTPException(409,'DISCOVERY_OPPORTUNITY_STALE')
    db.commit();db.refresh(row);return opportunity_view(row)
