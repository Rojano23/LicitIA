"""M9-D closure: synthetic canonical APIs, historical versions and real local writers."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import json
import re
import pytest
from sqlalchemy import select, event
from app.models import Requirement, RequirementEvidenceExpectation, TenderScopeQuantity
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection, create as create_snapshot
from tests.test_proposal_versions import ready, create
from tests.test_proposal_composition import init, finish, change, route
from tests.test_proposal_exports import (proposal, freeze, generate, artifact, verify_package,
    visible_docx, visible_xlsx, visible_pdf)
from tests.test_commercial_matrix import matrix, bulk
from tests.test_readiness_work import read


def evidence(name, payload):
    root=Path('reports/m9_d');root.mkdir(exist_ok=True)
    (root/name).write_text(json.dumps(payload,indent=2,default=str)+'\n')


def representations(c,t,v,receipt):
    data={kind:artifact(c,t,v,receipt,kind) for kind in ['DOCX','XLSX','PDF','ZIP']}
    manifest=verify_package(data['ZIP'])
    return manifest,[visible_docx(data['DOCX']),visible_xlsx(data['XLSX'])[1],visible_pdf(data['PDF'])]


def test_full_path_historical_revision_traceability_and_external_parity(ready,monkeypatch):
    # ready uses the cheap existing generic PDF fixture, canonical Scope/Quantity and
    # human review APIs, commercial API, readiness and explicit snapshot creation.
    c,t,db,m,seed=ready
    rows=matrix(c,m)['rows']
    bulk(c,m,[rows[0]],changes={'currency':'USD'},apply=True,confirm_currency_change=True)
    bulk(c,m,matrix(c,m)['rows'],changes={'unit_cost':'876543.21','notes':'PRIVATE_PRICING_RATIONALE_M9D'},apply=True)
    from tests.test_readiness_work import save
    work_route=f'/tenders/{t}/readiness-work'
    issues=read(c,work_route)['items']
    assert issues
    save(c,work_route,next(i for i in issues if i['code']=='PRICE_BELOW_COST'),workflow_status='ACCEPTED_RISK',note='PRIVATE_ACCEPTED_RISK_REASON_M9D')
    snapshot,_=create_snapshot(c,t)
    v,_=create(c,t,snapshot);comp=init(c,t,v)
    pending=[r for r in comp['rows'] if r['section']=='REQUIREMENTS']
    assert pending and all(r['response']['status']=='PENDING' for r in pending)
    comp=finish(c,t,v)
    req=next(r for r in comp['rows'] if r['section']=='REQUIREMENTS')
    ev=next(r for r in comp['rows'] if r['section']=='REQUESTED_EVIDENCE')
    scope=next(r for r in comp['rows'] if r['section']=='TECHNICAL_SCOPE')
    comp=change(c,t,v,comp,req['key'],{'status':'COMPLY','text':'HUMAN_REQUIREMENT_ANSWER_M9D','clarification':'HUMAN_CLARIFICATION_M9D'})
    comp=change(c,t,v,comp,ev['key'],{'status':'PROVIDED','text':'HUMAN_EVIDENCE_ANSWER_M9D','external_reference':'HUMAN_ASSOCIATION_M9D'})
    assert comp['summary']['status']=='COMPLETE'
    v=freeze(c,t,v,comp);frozen=deepcopy(read(c,route(t,v)+'/composition'))
    first,_=generate(c,t,v);manifest,texts=representations(c,t,v,first)
    external=manifest['content'];economic=next(s for s in external['sections'] if s['id']=='economic')
    assert {r['group'] for r in economic['rows']}=={'USD','MXN'}
    assert v['snapshot_id']==snapshot['payload']['snapshot_id']==external['snapshot_id']
    assert external['version_id']==v['id'] and external['composition_sha256']==comp['sha256']
    for text in texts:
        normalized=' '.join(text.split())
        for value in ['HUMAN_REQUIREMENT_ANSWER_M9D','HUMAN_EVIDENCE_ANSWER_M9D','HUMAN_ASSOCIATION_M9D','HUMAN_CLARIFICATION_M9D',req['canonical']['display_text'],ev['canonical']['display_text']]:
            assert ' '.join(value.split()) in normalized
        for row in economic['rows']:
            for key in ['item','description','quantity','unit','unit_price','total','currency']:
                if key in {'quantity','unit_price','total'}:
                    assert Decimal(row['values'][key]) in {Decimal(n) for n in re.findall(r'(?<![A-Za-z0-9])[+-]?[0-9]+(?:\.[0-9]+)?',normalized)}
                else:assert ' '.join(row['values'][key].split()) in normalized
        assert 'FROZEN' in text and v['id'] not in text
    exposed=json.dumps(manifest)+'\n'.join(texts)
    for forbidden in ['876543.21','PRIVATE_PRICING_RATIONALE_M9D','unit_cost','markup_percent','target_margin_percent','PRIVATE_ACCEPTED_RISK_REASON_M9D']:
        assert forbidden not in exposed
    source=scope['canonical']['source']
    assert source['document_id'] and source['page']==1 and source['excerpt_sha256']
    exported_scope=next(r for s in external['sections'] for r in s['rows'] if r['key']==scope['key'])
    assert source in exported_scope['source_references']
    # Actual upstream mutations; snapshot B and revision v2 must not rebind v1.
    requirement=db.get(Requirement,req['canonical']['id'])
    expectation=db.get(RequirementEvidenceExpectation,ev['canonical']['id'])
    requirement.canonical_text='NEW_REQUIREMENT_FOR_REVISION_B_M9D'
    expectation.evidence_description='NEW_EVIDENCE_FOR_REVISION_B_M9D';db.flush()
    assert c.patch(f'/tenders/{t}/requirements/{requirement.id}/review',json={'action':'APPROVE'}).status_code==200
    # Synthetic upstream correction only; no Quantity editing capability is added.
    quantity_id=snapshot['payload']['projection']['rows'][0]['quantity_id']
    quantity=db.get(TenderScopeQuantity,quantity_id)
    original_quantity=(quantity.quantity_raw,quantity.quantity_value)
    quantity.quantity_raw='19';quantity.quantity_value=Decimal('19');db.flush()
    invalid=read(c,f'/tenders/{t}/proposal-readiness')
    assert invalid['projection']['eligibility']=='NOT_ELIGIBLE'
    assert any(i['code']=='QUANTITY_INVALID_PARENT_OR_SOURCE' for i in invalid['projection']['blockers'])
    quantity.quantity_raw,quantity.quantity_value=original_quantity;db.flush()
    from tests.test_commercial_readiness import ready_source
    ready_source(c,t,db,m)
    bulk(c,m,matrix(c,m)['rows'],changes={'offered_unit_price':'23','currency':'EUR'},apply=True,confirm_currency_change=True)
    current=read(c,f'/tenders/{t}/proposal-readiness')
    evidence('upstream_readiness.json',current)
    newer,_=create_snapshot(c,t,current)
    second,_=create(c,t,newer,proposal_id=v['proposal_id'],previous_version_id=v['id'])
    updated=init(c,t,second)
    assert second['version']==2 and second['snapshot_id']!=v['snapshot_id']
    for key in [req['key'],ev['key']]:
        copied=next(r for r in updated['rows'] if r['key']==key)
        assert copied['review_required'] and copied['source_match']=='SOURCE_CHANGED'
        assert copied['response']['text'].startswith('HUMAN_')
    assert any(r['canonical'].get('display_text')==requirement.canonical_text for r in updated['rows'])
    assert {r['canonical']['quantity'] for r in updated['rows'] if r['section']=='ECONOMIC'}=={r['values']['quantity'] for r in economic['rows']}
    assert all(r['canonical']['currency']=='EUR' and Decimal(r['canonical']['offered_unit_price'])==23 for r in updated['rows'] if r['section']=='ECONOMIC')
    assert read(c,route(t,v)+'/source-state')['state']=='SOURCE_SNAPSHOT_STALE'
    def denied(*a,**k):raise AssertionError('Historical export queried mutable Requirement state or network')
    with monkeypatch.context() as guard:
        guard.setattr('app.requirement_matrix.get_tender_requirement_matrix',denied)
        guard.setattr('socket.create_connection',denied)
        again,_=generate(c,t,v)
        repeated,repeated_text=representations(c,t,v,again)
    assert repeated['content']==external and again['semantic_sha256']==first['semantic_sha256']
    assert read(c,route(t,v)+'/composition')==frozen
    for text in repeated_text:assert 'NEW_REQUIREMENT_FOR_REVISION_B_M9D' not in text and 'NEW_EVIDENCE_FOR_REVISION_B_M9D' not in text
    assert c.post(route(t,v)+f"/exports/{first['request_id']}/verify").json()['verification_status']=='VERIFIED'
    evidence('e2e.json',{'result':'PASS','snapshot_a':v['snapshot_id'],'snapshot_b':second['snapshot_id'],
        'v1':v['id'],'v2':second['id'],'historical_semantics_identical':True,'requirement_materialized':True,
        'requested_evidence_materialized':True,'economic_representation_preserved':True,'changed_sources_require_review':True,
        'traceability':{'source':source,'scope_key':scope['key'],'snapshot':v['snapshot_id'],'version':v['id'],
            'composition_sha256':comp['sha256'],'request_id':first['request_id'],'artifact_hashes':first['artifacts']},
        'cross_format_parity':True,'external_leakage_gate':'PASS','currencies':['MXN','USD'],'offline_reexport':True})


def test_large_composition_load_freeze_export_queries(proposal,monkeypatch):
    import tests.test_proposal_exports as exports
    c,t,db,m,snapshot,v,comp=proposal
    observations=[]
    def measured_freeze(client,tender,version,composition,**kwargs):
        record={'version_id':version['id']}
        for name,action in [('composition_load',lambda:read(client,route(tender,version)+'/composition')),
                            ('freeze',lambda:freeze(client,tender,version,composition,**kwargs))]:
            statements=[]
            def collect(conn,cursor,statement,parameters,context,executemany):
                if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
            event.listen(db.get_bind().engine,'before_cursor_execute',collect);start=perf_counter()
            try:result=action()
            finally:event.remove(db.get_bind().engine,'before_cursor_execute',collect)
            record[name]={'selects':len(statements),'seconds':round(perf_counter()-start,5)}
            if name=='composition_load':record['rows']=result['total']
        observations.append(record)
        return result
    small,_=create(c,t,snapshot);small_comp=finish(c,t,small);measured_freeze(c,t,small,small_comp)
    monkeypatch.setattr(exports,'freeze',measured_freeze)
    export_times=[]
    original_generate=exports.generate
    def measured_generate(*args,**kwargs):
        started=perf_counter();result=original_generate(*args,**kwargs)
        export_times.append(round(perf_counter()-started,5));return result
    monkeypatch.setattr(exports,'generate',measured_generate)
    start=perf_counter();exports.test_m9c29_many_scope_requirement_evidence_rows_without_n_plus_one(proposal)
    assert len(observations)==2 and observations[1]['rows']>observations[0]['rows']+500
    for phase in ['composition_load','freeze']:
        assert observations[1][phase]['selects']<=observations[0][phase]['selects']+2
    evidence('performance.json',{'measurements':observations,'combined_large_export_test_seconds':round(perf_counter()-start,5),
        'export_seconds_small_large':export_times,'export_sql':json.loads(Path('reports/m9_c/query_scaling.json').read_text()),'result':'PASS'})
