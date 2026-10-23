"""R1–R6 proposal-time literals over real synthetic canonical records."""
from copy import deepcopy
from sqlalchemy import select
from app.models import Requirement,RequirementEvidenceExpectation,ProposalComposition
from tests.test_workspace_flow import scene
from tests.test_bid_readiness import complete
from tests.test_proposal_readiness import proposal_connection,create as create_snapshot
from tests.test_proposal_versions import ready,create
from tests.test_proposal_composition import init,finish,route
from tests.test_readiness_work import read


def test_r1_r2_r3_r4_r5_r6_literal_materialization_and_new_revision(ready,monkeypatch):
    c,t,db,m,snapshot=ready
    requirements=list(db.scalars(select(Requirement).where(Requirement.tender_id==t)))
    evidence=list(db.scalars(select(RequirementEvidenceExpectation).join(Requirement).where(Requirement.tender_id==t)))
    original={r.id:r.canonical_text for r in requirements};original_e={e.id:e.evidence_description for e in evidence}
    v,_=create(c,t,snapshot);comp=finish(c,t,v)
    for row in comp['rows']:
        if row['section']=='REQUIREMENTS':assert row['canonical']['display_text']==original[row['canonical']['id']]
        if row['section']=='REQUESTED_EVIDENCE':assert row['canonical']['display_text']==original_e[row['canonical']['id']]
    assert {r.id:r.canonical_text for r in requirements}==original
    assert {e.id:e.evidence_description for e in evidence}==original_e
    assert c.post(route(t,v)+'/freeze',json={'expected_edit_revision':1,'expected_composition_revision':comp['revision'],'acknowledge_warnings':True}).status_code==200
    frozen=deepcopy(read(c,route(t,v)+'/composition'))
    requirements[0].canonical_text='Nueva representación canónica sintética.'
    for e in evidence:e.evidence_description='Nueva evidencia sintética solicitada.'
    db.flush()
    # Historical composition must not invoke any current Requirement adapter.
    from app.requirement_matrix import get_tender_requirement_matrix
    def denied(*a,**k):raise AssertionError('Frozen composition consulted mutable source')
    with monkeypatch.context() as guard:
        guard.setattr('app.requirement_matrix.get_tender_requirement_matrix',denied)
        assert read(c,route(t,v)+'/composition')==frozen
    for r in requirements:
        response=c.patch(f'/tenders/{t}/requirements/{r.id}/review',json={'action':'APPROVE'})
        assert response.status_code==200,response.text
    newer,_=create_snapshot(c,t)
    second,_=create(c,t,newer,proposal_id=v['proposal_id'],previous_version_id=v['id'])
    updated=init(c,t,second)
    assert any(r['canonical'].get('display_text')=='Nueva representación canónica sintética.' for r in updated['rows'])
    assert any(r['canonical'].get('display_text')=='Nueva evidencia sintética solicitada.' for r in updated['rows'])
    assert any(r['review_required'] and r['source_match']=='SOURCE_CHANGED' for r in updated['rows'])
    assert read(c,route(t,v)+'/composition')==frozen


def test_stale_unmaterialized_snapshot_fails_closed(ready):
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot)
    requirement=db.scalar(select(Requirement).where(Requirement.tender_id==t))
    requirement.canonical_text='Changed after snapshot before proposal capture';db.flush()
    response=c.post(route(t,v)+'/composition/initialize',json={})
    assert response.status_code==409 and 'SOURCE_REPRESENTATION_UNAVAILABLE' in response.text
    assert db.get(ProposalComposition,v['id']) is None


def test_legacy_frozen_composition_keeps_original_hash(ready,monkeypatch):
    from datetime import datetime,timezone
    from app.models import ProposalVersion
    from app.proposal_versions import frozen_envelope
    from app.proposal_readiness import digest
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=finish(c,t,v)
    stored=db.get(ProposalComposition,v['id']);legacy=deepcopy(stored.content);legacy.pop('sources')
    stored.content=legacy;stored.revision+=1;db.flush()
    old_hash=digest({'contract_version':'proposal-composition-v1','version_id':v['id'],'revision':stored.revision,'content':legacy})
    row=db.get(ProposalVersion,v['id']);row.state='FROZEN';row.edit_revision+=1;row.frozen_at=datetime.now(timezone.utc);row.updated_at=row.frozen_at
    row.freeze_acknowledgements={'request_sha256':'a'*64,'composition_contract':'proposal-composition-v1','composition_revision':stored.revision,'composition_sha256':old_hash}
    row.frozen_sha256=digest(frozen_envelope(row));db.flush()
    monkeypatch.setattr('app.requirement_matrix.get_tender_requirement_matrix',lambda *a:(_ for _ in ()).throw(AssertionError('Legacy backfill prohibited')))
    result=read(c,route(t,v)+'/composition');assert result['sha256']==old_hash
    assert any(r['canonical'].get('text_state')=='NOT_FROZEN_IN_SNAPSHOT' for r in result['rows'])
    assert init(c,t,v)['sha256']==old_hash


def test_legacy_draft_capture_preserves_human_content(ready):
    from tests.test_proposal_composition import change
    c,t,db,m,snapshot=ready;v,_=create(c,t,snapshot);comp=init(c,t,v)
    req=next(r for r in comp['rows'] if r['section']=='REQUIREMENTS')
    comp=change(c,t,v,comp,req['key'],{'status':'COMPLY','text':'Prior human content'})
    stored=db.get(ProposalComposition,v['id']);legacy=deepcopy(stored.content);legacy.pop('sources')
    stored.content=legacy;stored.revision+=1;db.flush()
    upgraded=init(c,t,v)
    answer=next(r for r in upgraded['rows'] if r['key']==req['key'])
    assert answer['response']['text']=='Prior human content' and answer['canonical']['text_state']=='MATERIALIZED'
    assert init(c,t,v)['sha256']==upgraded['sha256']
