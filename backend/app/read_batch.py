"""Short-lived batch inputs and memoization for one read-only canonical composition.

No process/global cache. Every entry is discarded even when a reader raises.
"""
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
from inspect import signature
from sqlalchemy import select
from app.models import TenderDocument, DocumentPage, NormalizedContent, TenderScopeDetail, TenderScopeQuantity, TenderScopeReview

KEY = 'licitia_canonical_read_batch'


def current_batch(db):
    return db.info.get(KEY)


def memo_read(function):
    params = signature(function)
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        batch = current_batch(db)
        if batch is None:
            return function(db, *args, **kwargs)
        arguments = params.bind(db, *args, **kwargs).arguments
        key = (function.__module__, function.__name__, repr({k:v for k,v in arguments.items() if k!='db'}))
        if key not in batch['memo']:
            batch['memo'][key] = deepcopy(function(db, *args, **kwargs))
        return deepcopy(batch['memo'][key])
    return wrapped


@contextmanager
def canonical_read_batch(db, tender_id):
    if current_batch(db) is not None:
        raise ValueError('Nested canonical read batch is not supported')
    with db.no_autoflush:
        documents = list(db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tender_id)))
        pages = list(db.scalars(select(DocumentPage).where(DocumentPage.document_id.in_([d.id for d in documents]))))
        normalized = list(db.scalars(select(NormalizedContent).where(NormalizedContent.document_page_id.in_([p.id for p in pages]))))
        scopes = list(db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==tender_id)))
        quantities = list(db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.tender_id==tender_id)))
        reviews = list(db.scalars(select(TenderScopeReview).where(TenderScopeReview.tender_id==tender_id).order_by(TenderScopeReview.revision)))
        history = {}
        for r in reviews:history.setdefault(r.scope_detail_id, []).append(r)
        batch = {'tender_id':tender_id,'scopes':{s.id:s for s in scopes},'history':history,'memo':{},
                 'pinned':(documents,pages,normalized,scopes,quantities,reviews)}
        db.info[KEY] = batch
        try:
            yield batch
        finally:
            db.info.pop(KEY, None)
