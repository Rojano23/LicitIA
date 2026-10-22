"""M8-A synthetic canonical contracts; no blind data or provider acquisition."""
from uuid import uuid4
import json
import pytest
from sqlalchemy import event, select
from app.models import TenderDocument, TenderScopeQuantity
from app.bid_readiness import aggregate_status, build_readiness, CanonicalReadinessInput, DocumentState, SourceConflict
from app.workspace_flow import read_workspace
from app.commercial_projections import tender_readiness
from tests.test_workspace_flow import scene, upload, process
from tests.test_commercial_matrix import matrix, bulk
from tests.test_commercial_readiness import ready_source


@pytest.fixture
def complete(scene):
    import pymupdf
    c,t,db=scene;upload(c,t)
    pdf=pymupdf.open();page=pdf.new_page();page.insert_text((40,60),'El licitante debera presentar una carta de garantia firmada.',fontsize=11)
    upload(c,t,pdf.tobytes(),'generic-requirement.pdf');pdf.close();process(c,t)
    r=f'/tenders/{t}/commercial-matrix';ready_source(c,t,db,r)
    reqs=c.get(f'/tenders/{t}/requirement-matrix').json()['requirements'];assert reqs
    for req in reqs:
        response=c.patch(f"/tenders/{t}/requirements/{req['requirement_id']}/review",json={'action':'APPROVE'})
        assert response.status_code==200,response.text
    bulk(c,r,matrix(c,r)['rows'],changes={'offered_unit_price':'12','currency':'MXN','unit_cost':'10'},apply=True,input_origin='UI')
    return c,t,db,r


def read(c,t,suffix=''):
    response=c.get(f'/tenders/{t}/bid-readiness'+suffix);assert response.status_code==200,response.text
    return response.json()


def snapshot(complete):
    _,t,db,_=complete
    docs=[DocumentState(id=d.id,tender_id=t,status=d.status,processing_status=d.processing_status,is_current=d.is_current,available=True,revision=d.revision_number) for d in db.scalars(select(TenderDocument).where(TenderDocument.tender_id==t))]
    return CanonicalReadinessInput(tender_id=t,workspace=read_workspace(db,t),commercial=tender_readiness(db,t),documents=docs)


def test_m8a01_12_13_15_17_20_complete_canonical_tender(complete):
    c,t,db,r=complete
    before=c.get(f'/tenders/{t}/workspace').json();commercial=matrix(c,r)
    first=read(c,t)
    assert first['status']=='READY',json.dumps(first,indent=2)
    assert first['blocker_count']==0 and first['review_required_count']==0 and first['warning_count']>=1
    assert first==read(c,t)
    assert all(d['status'] in {'READY','NOT_APPLICABLE'} for d in first['dimensions'])
    refs=[i['reference'] for i in first['items'] if i['dimension']=='REQUESTED_EVIDENCE' and i['entity_type']=='REQUESTED_EVIDENCE']
    assert refs and all(x['document_id'] and x['revision']==1 and x['page']==1 and x['excerpt'] for x in refs)
    after=c.get(f'/tenders/{t}/workspace').json()
    for key in ['requirements','semantics']:before[key].pop('generated_at');after[key].pop('generated_at')
    assert before==after and matrix(c,r)==commercial


@pytest.mark.parametrize('states,expected',[
    (['READY'],'READY'),(['READY','NOT_APPLICABLE'],'READY'),(['NOT_APPLICABLE'],'NOT_APPLICABLE'),
    (['READY','REVIEW_REQUIRED'],'REVIEW_REQUIRED'),(['REVIEW_REQUIRED','INCOMPLETE'],'INCOMPLETE'),
    (['READY','BLOCKED'],'BLOCKED'),(['INCOMPLETE','BLOCKED','REVIEW_REQUIRED'],'BLOCKED'),([], 'NOT_APPLICABLE'),
])
def test_m8a16_precedence(states,expected):
    assert aggregate_status(states)==aggregate_status(list(reversed(states)))==expected


def test_m8a02_03_11_14_commercial_blocker_and_filters(complete):
    c,t,db,r=complete;bulk(c,r,[matrix(c,r)['rows'][0]],changes={'offered_unit_price':None},apply=True)
    result=read(c,t);assert result['status']=='INCOMPLETE'
    price=next(i for i in result['issues'] if i['dimension']=='COMMERCIAL' and i['code']=='MISSING_OFFERED_PRICE')
    assert price['severity']=='BLOCKER' and price['underlying']['status']=='INCOMPLETE'
    assert price in read(c,t,'/issues?dimension=COMMERCIAL&severity=BLOCKER')
    assert all(i['severity']=='WARNING' for i in read(c,t,'/issues?severity=WARNING'))
    assert 'markup_percent' not in json.dumps([i for i in result['items'] if i['dimension']=='COMMERCIAL'])
    assert c.get(f'/tenders/{t}/bid-readiness/issues?limit=501').status_code==422
    assert c.get(f'/tenders/{t}/bid-readiness/issues?dimension=UNKNOWN').status_code==422
    assert read(c,t,'/dimensions')==result['dimensions']


def test_m8a04_loss_warning_does_not_block(complete):
    c,t,db,r=complete;bulk(c,r,matrix(c,r)['rows'],changes={'offered_unit_price':'9'},apply=True)
    result=read(c,t);assert result['status']=='READY'
    losses=[i for i in result['issues'] if i['code']=='PRICE_BELOW_COST']
    assert len(losses)==2 and all(i['severity']=='WARNING' and i['status']=='READY' for i in losses)


def test_m8a05_06_09_requirement_review_and_evidence(complete):
    c,t,db,r=complete;req=c.get(f'/tenders/{t}/requirement-matrix').json()['requirements'][0]
    c.patch(f"/tenders/{t}/requirements/{req['requirement_id']}/review",json={'action':'MARK_NEEDS_REVIEW'})
    result=read(c,t);assert result['status']=='REVIEW_REQUIRED'
    assert any(i['dimension']=='REQUIREMENTS' and i['entity_id']==req['requirement_id'] for i in result['issues'])
    assert any(i['dimension']=='REQUESTED_EVIDENCE' for i in result['issues'])
    assert any(i['dimension']=='HUMAN_REVIEW' and i['entity_id']==req['requirement_id'] for i in result['issues'])


def test_m8a07_08_quantity_missing_and_source_parent(complete):
    c,t,db,r=complete;row=matrix(c,r)['rows'][0];q=db.get(TenderScopeQuantity,row['source']['selected_quantity_id']);db.delete(q);db.flush()
    result=read(c,t);issue=next(i for i in result['issues'] if i['code']=='MISSING_CANONICAL_QUANTITY')
    assert issue['dimension']=='QUANTITIES' and issue['entity_id']==row['scope_id'] and issue['reference']['page']==1
    assert result['status']=='INCOMPLETE'


def test_m8a10_document_conflict_and_hard_precedence(complete):
    s=snapshot(complete);doc=s.documents[0].model_copy(update={'status':'NAME_CONFLICT'})
    result=build_readiness(s.model_copy(update={'documents':[doc,*s.documents[1:]],'source_conflicts':[SourceConflict(entity_id='effect-id',status='CONFLICT',code='SOURCE_EFFECT_CONFLICT',reasons=['SOURCE_EFFECT_CYCLE'],source_document_id=doc.id)]}))
    assert result.status=='BLOCKED'
    assert any(i.code=='DOCUMENT_NAME_CONFLICT' and i.entity_id==doc.id for i in result.issues)
    assert any(i.code=='SOURCE_EFFECT_CONFLICT' and i.entity_id=='effect-id' and i.underlying['reasons']==['SOURCE_EFFECT_CYCLE'] and i.reference.document_id==doc.id for i in result.issues)


def test_m8a18_other_tender_and_unknown(complete):
    c,t,db,r=complete;other=c.post('/tenders',json={'title':'Other'}).json()['id'];data=read(c,other)
    assert data['status']=='INCOMPLETE' and not any(i['entity_type']=='SCOPE' for i in data['items'])
    assert c.get(f'/tenders/{uuid4()}/bid-readiness').status_code==404
    with pytest.raises(ValueError,match='TENDER_MISMATCH'):build_readiness(snapshot(complete).model_copy(update={'tender_id':other}))
    s=snapshot(complete)
    foreign=s.workspace.requirements.model_copy(update={'tender_id':other})
    with pytest.raises(ValueError,match='TENDER_MISMATCH'):
        build_readiness(s.model_copy(update={'workspace':s.workspace.model_copy(update={'requirements':foreign})}))


def test_invalid_parent_and_quantity_review_fail_closed(complete):
    s=snapshot(complete);w=s.workspace;scope=w.scopes[0];q=scope.quantities[0]
    invalid=q.model_copy(update={'scope_detail_id':str(uuid4())})
    result=build_readiness(s.model_copy(update={'workspace':w.model_copy(update={'scopes':(scope.model_copy(update={'quantities':(invalid,)}),*w.scopes[1:])})}))
    assert result.status=='BLOCKED' and any(i.code=='QUANTITY_INVALID_PARENT_OR_SOURCE' for i in result.issues)
    pending=q.model_copy(update={'status':'REVIEW_REQUIRED','review_required':True})
    result=build_readiness(s.model_copy(update={'workspace':w.model_copy(update={'scopes':(scope.model_copy(update={'quantities':(pending,)}),*w.scopes[1:])})}))
    assert result.status=='REVIEW_REQUIRED' and any(i.dimension=='HUMAN_REVIEW' and i.entity_id==q.id for i in result.issues)


def test_m8a19_no_institutional_identifiers_in_engine():
    from pathlib import Path
    text=Path('app/bid_readiness.py').read_text().lower();assert all(name not in text for name in ['pemex','cfe','compras mx','anexo c'])


def test_adapter_errors_are_not_empty_ready_fallbacks(complete,monkeypatch):
    from app import bid_readiness_service as service
    _,t,db,_=complete
    def failed(*args,**kwargs):raise ValueError('CANONICAL_UNAVAILABLE')
    monkeypatch.setattr(service,'tender_readiness',failed)
    with pytest.raises(ValueError,match='CANONICAL_UNAVAILABLE'):service.read_bid_readiness(db,t)


def test_query_composition_measured_no_service_call_per_issue(complete,monkeypatch):
    from app import bid_readiness_service as service
    c,t,db,r=complete;counts={};statements=[]
    for name in ['read_workspace','tender_readiness','project_effective_sources_for_tender']:
        original=getattr(service,name)
        def counted(*args,_name=name,_call=original,**kwargs):counts[_name]=counts.get(_name,0)+1;return _call(*args,**kwargs)
        monkeypatch.setattr(service,name,counted)
    def collect(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    engine=db.get_bind().engine;event.listen(engine,'before_cursor_execute',collect)
    try:result=service.read_bid_readiness(db,t)
    finally:event.remove(engine,'before_cursor_execute',collect)
    assert counts=={'read_workspace':1,'tender_readiness':1,'project_effective_sources_for_tender':1}
    from pathlib import Path
    Path('reports/m8_a_hardening/query_composition.json').write_text(json.dumps({'scope_count':2,'item_count':len(result.items),'selects':len(statements),'service_calls':counts,'inherited_scope_validation_queries':True},indent=2)+'\n')


def test_unresolved_evidence_and_scope_keep_original_reasons(complete):
    s=snapshot(complete);w=s.workspace;r=w.requirements.requirements[0]
    expectation=r.expected_evidence[0].model_copy(update={'evidence_type':'UNKNOWN'})
    changed=r.model_copy(update={'expected_evidence':[expectation]})
    result=build_readiness(s.model_copy(update={'workspace':w.model_copy(update={'requirements':w.requirements.model_copy(update={'requirements':[changed]})})}))
    issue=next(i for i in result.issues if i.entity_id==expectation.id and i.dimension=='REQUESTED_EVIDENCE')
    assert issue.status=='REVIEW_REQUIRED' and issue.underlying['evidence_type']=='UNKNOWN'
    assert any(i.dimension=='HUMAN_REVIEW' and i.entity_id==expectation.id for i in result.issues)
    scope=w.scopes[0];current=scope.review.current.model_copy(update={'effective_status':'STALE_REVIEW'})
    updated=scope.model_copy(update={'review':scope.review.model_copy(update={'current':current})})
    result=build_readiness(s.model_copy(update={'workspace':w.model_copy(update={'scopes':(updated,*w.scopes[1:])})}))
    issue=next(i for i in result.issues if i.dimension=='SCOPE' and i.entity_id==scope.scope_detail_id)
    assert issue.underlying['status']=='STALE_REVIEW' and issue.reference.document_id==scope.source.document_id
    assert '/scope-review/' in issue.review_context


def test_unknown_and_contextual_requirements_are_explicit(complete):
    s=snapshot(complete);w=s.workspace;r=w.requirements.requirements[0]
    for change,expected in [({'effective_status':'UNRESOLVED'},'REVIEW_REQUIRED'),({'applicability':'UNKNOWN'},'REVIEW_REQUIRED'),({'applicability':'CONDITIONAL'},'READY'),({'review_status':'REJECTED'},'NOT_APPLICABLE')]:
        updated=r.model_copy(update=change)
        result=build_readiness(s.model_copy(update={'workspace':w.model_copy(update={'requirements':w.requirements.model_copy(update={'requirements':[updated]})})}))
        record=next(i for i in result.items if i.dimension=='REQUIREMENTS' and i.code!='REPRESENTATION_HUMAN_ACCEPTED_WITH_WARNINGS' and i.code!='CONDITIONAL_CONTEXT')
        assert record.status==expected


def test_request_batch_equivalence_freshness_and_scaling(scene):
    from app.bid_readiness_service import read_bid_readiness
    from app.read_batch import KEY
    from app.models import TenderScopeDetail
    from pathlib import Path
    c,t,db=scene;upload(c,t);process(c,t)
    engine=db.get_bind().engine
    def measure(batched):
        queries=[]
        def capture(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):queries.append(statement)
        event.listen(engine,'before_cursor_execute',capture)
        try:result=read_bid_readiness(db,t,batched=batched)
        finally:event.remove(engine,'before_cursor_execute',capture)
        assert KEY not in db.info
        return result,len(queries)
    baseline,before=measure(False);optimized,small=measure(True)
    assert baseline==optimized
    scopes=list(db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id==t)))
    # Controlled synthetic copies retain valid source/manifest identity but unique Scope IDs.
    # Each copied Scope has its own Quantity child for equal domain composition.
    original=scopes[0]
    for _ in range(18):
        values={col.name:getattr(original,col.name) for col in TenderScopeDetail.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        values['semantic_fingerprint']=str(uuid4()).replace('-','')*2
        clone=TenderScopeDetail(**values);db.add(clone);db.flush()
        quantity=db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id==original.id))
        child={col.name:getattr(quantity,col.name) for col in TenderScopeQuantity.__table__.columns if col.name not in {'id','created_at','updated_at'}}
        child['scope_detail_id']=clone.id
        child['semantic_fingerprint']=str(uuid4()).replace('-','')*2
        db.add(TenderScopeQuantity(**child))
    db.flush()
    larger,large=measure(True)
    assert len([i for i in larger.items if i.dimension=='SCOPE'])==20
    assert large<=small+12,{'small':small,'large':large}
    assert small<before/2,{'before':before,'after':small}
    doc=db.scalar(select(TenderDocument).where(TenderDocument.tender_id==t))
    doc.processing_status='TEXT_EXTRACTION_FAILED';db.flush()
    changed,_=measure(True)
    assert changed!=larger and changed.status=='BLOCKED'
    Path('reports/m8_a_hardening/query_scaling.json').write_text(json.dumps({'before_2_scope':before,'after_2_scope':small,'after_20_scope':large,'equivalence':True,'freshness':True},indent=2)+'\n')
