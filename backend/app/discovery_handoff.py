"""Explicit human handoff via canonical Tender and injected canonical ingestion gateway."""
from datetime import datetime,timezone
from uuid import uuid4
from contextlib import contextmanager
from sqlalchemy import select,text
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from app.discovery_contract import fingerprint,PublicDocument
from app.discovery_registry import require_available,adapter_for
from app.discovery_models import DiscoveryOpportunity as Opp,DiscoverySourceDocument as Doc,DiscoveryTenderLink as Link,DiscoveryImportReceipt as Receipt
from app.discovery_monitoring import event,save_events
from app.tender_creation import create_record
from app.models import Tender,TenderDocument

@contextmanager
def handoff_lock(db,oid):
    with db.get_bind().engine.connect() as connection:
        key='discovery-handoff:'+oid
        if not connection.execute(text('SELECT pg_try_advisory_lock(hashtext(:k))'),{'k':key}).scalar():raise HTTPException(409,'DISCOVERY_HANDOFF_IN_PROGRESS')
        try:yield
        finally:connection.execute(text('SELECT pg_advisory_unlock(hashtext(:k))'),{'k':key})

def opportunity(db,oid):
    row=db.get(Opp,oid)
    if row is None:raise HTTPException(404,'DISCOVERY_OPPORTUNITY_NOT_FOUND')
    require_available(row.source_id)
    return row

def receipt_view(row):return {k:getattr(row,k) for k in ['id','source_document_id','tender_identity','tender_document_id','metadata_fingerprint','sha256','source_url','source_name','downloaded_at','result']}

def preview(db,oid):
    row=opportunity(db,oid);docs=list(db.scalars(select(Doc).where(Doc.opportunity_id==oid,Doc.active.is_(True)).order_by(Doc.id)))
    link=db.get(Link,oid);receipts=list(db.scalars(select(Receipt).where(Receipt.opportunity_id==oid).order_by(Receipt.downloaded_at)))
    latest={r.source_document_id:r for r in receipts}
    binding=fingerprint([row.id,row.revision,row.fingerprint,[(d.id,d.fingerprint) for d in docs],link.tender_identity if link else None])
    linked=db.get(Tender,link.tender_id) if link and link.tender_id else None
    context={k:row.representation.get(k) for k in ['external_id','procedure_number','title','description','published_date','business_area','contracting_area','public_url','source_status']}
    return {'opportunity_id':oid,'source_id':row.source_id,'source_fingerprint':row.fingerprint,'binding':binding,
        'internal_state':row.internal_state,'suggested_title':linked.title if linked else row.representation['title'] if len(row.representation['title'])<=255 else None,
        'context':context,'documents':[{'id':d.id,'external_id':d.external_id,'name':d.name,'public_url':d.public_url,'metadata_fingerprint':d.fingerprint,
            'observed_at':d.observed_at,'last_import':receipt_view(latest[d.id]) if d.id in latest else None} for d in docs],
        'linked_tender':{'id':link.tender_identity,'available':link.tender_id is not None} if link else None,
        'selection_default':'NONE','analysis_automatic':False}

def result(db,link,documents=None,already=False):
    return {'tender_id':link.tender_identity,'tender_available':link.tender_id is not None,'opportunity_id':link.opportunity_id,
        'already_created':already,'documents':documents or [],'documents_status':'PARTIAL' if any(d['status'] not in {'IMPORTED','DUPLICATE','REUSED'} for d in (documents or [])) else 'COMPLETE_SELECTION',
        'analysis_started':False}

async def handoff(db,oid,request,importer,*,tender_id=None,adapter=None):
    row=opportunity(db,oid)
    with handoff_lock(db,oid):
        # Refresh after waiting/locking; never recreate a deleted linked Tender.
        db.refresh(row,with_for_update=True);link=db.get(Link,oid)
        if link and (not link.tender_id or not db.get(Tender,link.tender_id)):raise HTTPException(409,'LINKED_TENDER_DELETED_NO_AUTOMATIC_RECREATION')
        if tender_id is None and link:return result(db,link,already=True)
        if tender_id is not None and (not link or link.tender_id!=tender_id):raise HTTPException(409,'DISCOVERY_TENDER_LINK_MISMATCH')
        current=preview(db,oid)
        if request.expected_binding!=current['binding']:raise HTTPException(409,'DISCOVERY_PREVIEW_STALE')
        if not link and row.internal_state=='DISCARDED':raise HTTPException(409,'REVIEW_DISCARDED_OPPORTUNITY_FIRST')
        available={d['id']:d for d in current['documents']}
        for choice in request.documents:
            if str(choice.document_id) not in available:raise HTTPException(404,'SOURCE_DOCUMENT_NOT_OWNED_OR_ACTIVE')
            if choice.revision_of_document_id:
                target=db.get(TenderDocument,str(choice.revision_of_document_id))
                owned_receipt=db.scalar(select(Receipt.id).where(Receipt.opportunity_id==oid,Receipt.source_document_id==str(choice.document_id),Receipt.tender_document_id==str(choice.revision_of_document_id)))
                if not link or target is None or target.tender_id!=link.tender_id or not owned_receipt:raise HTTPException(409,'REVISION_TARGET_NOT_OWNED')
        if link is None:
            title=request.title or current['suggested_title']
            if not title:raise HTTPException(422,'TENDER_TITLE_REQUIRED_255_MAX')
            tender=create_record(db,title,external_reference=row.representation.get('procedure_number') or row.external_id,commit=False)
            link=Link(opportunity_id=oid,tender_id=tender.id,tender_identity=tender.id,
                context={**current['context'],'source_id':row.source_id,'source_fingerprint':row.fingerprint},created_at=datetime.now(timezone.utc))
            db.add(link);previous=row.internal_state;row.internal_state='IMPORTED';row.revision+=1
            save_events(db,[event(row.source_id,oid,'TENDER_CREATED',row.fingerprint,row.fingerprint,{'tender_id':tender.id,'previous_state':previous,'state':'IMPORTED','selected_document_ids':[str(d.document_id) for d in request.documents]},'Tender creado por decisión humana explícita',actor=request.actor)])
            db.commit()
        owned=adapter is None
        if not request.documents:return result(db,link)
        try:client=adapter or adapter_for(row.source_id)
        except Exception as exc:
            outcomes=[{'source_document_id':str(d.document_id),'status':'FAILED','error_type':type(exc).__name__,'error_code':'SOURCE_CLIENT_UNAVAILABLE'} for d in request.documents]
            save_events(db,[event(row.source_id,oid,'DOCUMENT_IMPORT_FAILED',None,None,{'documents':outcomes},'Tender conservado; cliente de descarga no disponible',actor=request.actor)])
            db.commit();return result(db,link,outcomes)
        if client.source_id!=row.source_id:
            if owned:client.close()
            raise HTTPException(422,'ADAPTER_SOURCE_MISMATCH')
        outcomes=[]
        try:
            for choice in request.documents:
                selected=available[str(choice.document_id)];downloaded=None
                prior=db.scalar(select(Receipt).where(Receipt.opportunity_id==oid,Receipt.source_document_id==selected['id'],Receipt.metadata_fingerprint==selected['metadata_fingerprint']).order_by(Receipt.downloaded_at.desc()))
                if prior and not choice.refresh and db.get(TenderDocument,prior.tender_document_id):
                    outcomes.append({'source_document_id':selected['id'],'status':'REUSED','document_id':prior.tender_document_id,'sha256':prior.sha256});continue
                try:
                    downloaded=client.download(PublicDocument(external_id=selected['external_id'],name=selected['name'],public_url=selected['public_url']))
                    imported=await importer(link.tender_id,downloaded,choice.conflict_action,str(choice.revision_of_document_id) if choice.revision_of_document_id else None)
                    state=imported['status'];document_id=imported.get('document_id')
                    outcome={'source_document_id':selected['id'],'status':state,'document_id':document_id,'sha256':imported.get('sha256')}
                    if state in {'IMPORTED','DUPLICATE'}:
                        document=db.get(TenderDocument,document_id)
                        if document is None or document.tender_id!=link.tender_id or document.sha256!=downloaded.sha256:raise ValueError('CANONICAL_INGESTION_RECEIPT_MISMATCH')
                        values=dict(id=str(uuid4()),opportunity_id=oid,source_document_id=selected['id'],tender_identity=link.tender_identity,tender_document_id=document_id,
                            metadata_fingerprint=selected['metadata_fingerprint'],sha256=downloaded.sha256,source_url=selected['public_url'],source_name=selected['name'],downloaded_at=downloaded.downloaded_at,result=state)
                        db.execute(insert(Receipt).values(values).on_conflict_do_nothing(constraint='uq_discovery_import_receipt'))
                        category='DOCUMENT_IMPORTED'
                    else:category='DOCUMENT_IMPORT_FAILED'
                    save_events(db,[event(row.source_id,oid,category,row.fingerprint,row.fingerprint,outcome,'Resultado de importación documental explícita',actor=request.actor)])
                    db.commit();outcomes.append(outcome)
                except Exception as exc:
                    db.rollback();outcome={'source_document_id':selected['id'],'status':'FAILED','error_type':type(exc).__name__}
                    # Whitelisted exception codes only, never remote body/URLs/cookies.
                    if isinstance(exc,ValueError) and str(exc).isupper() and len(str(exc))<=100:outcome['error_code']=str(exc)
                    save_events(db,[event(row.source_id,oid,'DOCUMENT_IMPORT_FAILED',None,None,outcome,'Falló importación explícita; Tender y originales anteriores conservados',actor=request.actor)])
                    db.commit();outcomes.append(outcome)
                finally:
                    if downloaded:downloaded.close()
        finally:
            if owned:client.close()
        return result(db,link,outcomes)
