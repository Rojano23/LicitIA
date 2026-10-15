"""SC01–SC24/DC01–DC06: synthetic contract coverage, never blind fixtures."""
from dataclasses import replace
from decimal import Decimal
import hashlib
import pytest
from sqlalchemy import select
from app.models import TenderScopeDetail, TenderScopeAttribute, TenderScopeQuantity, DocumentVisionAnalysis
from app.scope_detail_materializer import materialize_document_scope_details
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from app.scope_logical_identity import logical_fingerprint, reconcile_candidates
from app.document_intelligence_sources import load_page_structure
from test_document_intelligence_integration import corpus, norm, vision, add_page
from test_document_preparation_recovery import batch
from app.document_intelligence_blind_run import prepare_tender_documents

TEXT = 'ITEM 47: Suministro de sensores | Marca: Acme | Modelo: S-7 | Cantidad: 6 | Unidad: PZA'


def run(corpus):
    db, tender, doc, _ = corpus
    result = materialize_document_scope_details(db, tender_id=tender.id, document_id=doc.id)
    return result, db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id == doc.id).order_by(TenderScopeDetail.source_excerpt)).all()


def children(db, detail):
    return (materialize_scope_attributes_for_scope_detail(db, scope_detail_id=detail.id),
            materialize_scope_quantities_for_scope_detail(db, scope_detail_id=detail.id))


def seeded(corpus, text=TEXT):
    db, _, _, page = corpus
    normalized = norm(db, page, text=text)
    result, rows = run(corpus)
    assert not any(r.errors for r in result.artifact_results), str([r.errors for r in result.artifact_results])
    return normalized, rows


def test_SC01_native_scope(corpus):
    _, rows = seeded(corpus)
    assert len(rows) == 1 and rows[0].domain == 'SUPPLY'


def test_SC02_non_procurement(corpus):
    assert seeded(corpus, 'ITEM 47: Política administrativa y fechas de emisión')[1] == []


def test_SC03_attribute(corpus):
    db = corpus[0]
    _, rows = seeded(corpus)
    attr, _ = children(db, rows[0])
    assert attr.persisted_count == 2
    values = db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == rows[0].id)).all()
    assert {(x.attribute_name, x.value_raw) for x in values} == {('brand','Acme'), ('model','S-7')}


def test_SC04_quantity(corpus):
    db = corpus[0]
    _, rows = seeded(corpus)
    _, qty = children(db, rows[0])
    assert qty.persisted_count == 1
    q = db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == rows[0].id))
    assert q.quantity_value == Decimal('6') and q.unit_raw == 'PZA' and q.relation == 'EXACT'


@pytest.mark.parametrize('child', ['attribute', 'quantity'])
def test_SC05_SC06_no_valid_owner(corpus, child):
    # Supply semantics are explicit, but weak structural identity is not proven.
    _, rows = seeded(corpus, 'CONCEPTO 47: Suministro de sensores\nMarca: Acme\nCantidad: 6\nUnidad: PZA')
    assert rows[0].applicability == 'UNRESOLVED'
    a, q = children(corpus[0], rows[0])
    assert (a if child == 'attribute' else q).persisted_count == 0


def test_SC07_ambiguous_structural_identity(corpus):
    seeded(corpus, 'CONCEPTO 47: Suministro de sensores')
    route = load_page_structure(corpus[0], corpus[2], corpus[3])
    assert route.status != 'RESOLVED' and route.selected is None
    assert all(e.structural_state.outgoing_item_key is None for e in route.candidates)


def test_SC08_generation_provenance(corpus):
    n, rows = seeded(corpus)
    d = rows[0]
    assert d.source_method == 'NATIVE' and n.id in d.source_locator and n.content_sha256 in d.source_locator
    assert d.source_artifact_key == f'native-page:{corpus[3].id}' and 'span:' in d.source_locator


def test_SC09_no_synthetic_vision(corpus):
    _, rows = seeded(corpus)
    assert rows[0].source_analysis_id is None and rows[0].source_page_result_id is None
    assert not corpus[0].scalars(select(DocumentVisionAnalysis).where(DocumentVisionAnalysis.tender_id == corpus[1].id)).all()


def test_SC10_native_vision_dedup_DC01_DC05(corpus):
    db, _, doc, page = corpus
    seeded(corpus)
    before = run(corpus)[1][0]
    identity = before.id
    vision(db, doc, page, TEXT)
    result, rows = run(corpus)
    assert len(rows) == 1 and rows[0].id == identity
    assert len(result.logical_evidence[0][1]) == 2


def test_SC11_multiple_items_DC02_DC03(corpus):
    _, rows = seeded(corpus, TEXT + '\n' + TEXT.replace('47', '48').replace('6 |', '9 |'))
    assert len(rows) == 2 and len({r.semantic_fingerprint for r in rows}) == 2


def test_SC12_repeat_DC04(corpus):
    _, rows = seeded(corpus)
    db = corpus[0]
    children(db, rows[0])
    ids = (rows[0].id, rows[0].semantic_fingerprint)
    assert (run(corpus)[1][0].id, run(corpus)[1][0].semantic_fingerprint) == ids
    assert db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == ids[0])).all()


def test_SC13_unsupported_unchanged(batch):
    db, tender, docs, _, calls = batch
    results = prepare_tender_documents(db, tender_id=tender.id, document_ids=tuple(d.id for d in docs))
    assert results[1].status == 'UNAVAILABLE' and results[1].page_count == 0 and not calls


def test_SC14_image_only(corpus):
    assert run(corpus)[1] == []


def test_SC15_existing_vision(corpus):
    db, _, doc, page = corpus
    row = vision(db, doc, page, TEXT)
    _, details = run(corpus)
    assert len(details) == 1 and details[0].source_method == 'VISION'
    assert details[0].source_page_result_id == row.id


def test_SC16_conflicting_fields(corpus):
    db, _, doc, page = corpus
    seeded(corpus)
    v = vision(db, doc, page, TEXT)
    v.structured_json = {'detail_transcription': {'task_type': 'DETAIL_TRANSCRIPTION', 'raw_text': TEXT,
        'parsed_supply_rows': [{'raw_visible_text': TEXT, 'description': TEXT, 'domain': 'SUPPLY', 'quantity': '99'}]}}
    db.flush()
    result, rows = run(corpus)
    assert len(rows) == 1 and rows[0].review_required and rows[0].applicability == 'UNRESOLVED'
    assert result.logical_evidence[0][2]


@pytest.mark.parametrize('fault', ['hash', 'missing', 'page'])
def test_SC17_invalid_generation(corpus, fault):
    db = corpus[0]
    n, rows = seeded(corpus)
    if fault == 'hash':
        n.normalized_text = 'modified without matching generation hash'
    elif fault == 'missing':
        rows[0].source_locator = rows[0].source_locator.replace(n.id, '00000000-0000-0000-0000-000000000000')
    else:
        other = add_page(db, corpus[2], 2)
        n.document_page_id = other.id
    db.flush()
    a, q = children(db, rows[0])
    assert a.status == q.status == 'INVALID_EVIDENCE' and a.errors and q.errors


def test_SC18_exact_normalized_source(corpus):
    _, rows = seeded(corpus)
    corpus[3].text = 'different current page text with no fields'
    a, q = children(corpus[0], rows[0])
    assert a.persisted_count == 2 and q.persisted_count == 1


def test_SC19_failed_no_resurrection(corpus):
    db, _, doc, page = corpus
    v = vision(db, doc, page, TEXT, failed=True)
    assert run(corpus)[1] == []
    assert v.structured_json['_detail_runtime']['status'] == 'FAILED'


@pytest.mark.parametrize('quantity,unit', [('1,5', 'PZA'), ('2-4','PZA'), ('3','UNKNOWN'), ('$100','PZA')])
def test_SC20_ambiguous_numbers(corpus, quantity, unit):
    _, rows = seeded(corpus, TEXT.replace('Cantidad: 6', f'Cantidad: {quantity}').replace('Unidad: PZA', f'Unidad: {unit}'))
    assert children(corpus[0], rows[0])[1].persisted_count == 0


def test_SC21_same_item_different_page(corpus):
    seeded(corpus)
    page = add_page(corpus[0], corpus[2], 2)
    norm(corpus[0], page, text=TEXT)
    assert len(run(corpus)[1]) == 2


def test_SC22_errors_explicit(corpus, monkeypatch):
    from app.native_scope_detail_adapter import NativeScopeDetailAdapter
    norm(corpus[0], corpus[3], text=TEXT)
    def fail(*args):
        raise ValueError('synthetic adapter failure')
    monkeypatch.setattr(NativeScopeDetailAdapter, 'extract_candidates', fail)
    result, rows = run(corpus)
    assert not rows and result.artifact_results[0].status == 'INVALID_EVIDENCE'
    assert result.artifact_results[0].errors == ('synthetic adapter failure',)


def test_SC23_capability_order_independent(corpus):
    from app.scope_details import ScopeDetailCandidate
    d = ScopeDetailCandidate(tender_id='t', source_document_id='d', document_page_id='p', domain='SUPPLY',
        detail_type='DETAIL', description=TEXT, applicability='UNRESOLVED', source_method='NATIVE',
        source_artifact_key='native-page:p', source_locator='page:1', source_excerpt=TEXT, review_required=True)
    v = replace(d, source_method='VISION', source_artifact_key='vision-page-result:v')
    assert reconcile_candidates([d,v]) == reconcile_candidates([v,d])
    assert logical_fingerprint(d) == logical_fingerprint(v)


def test_SC24_review_propagation(corpus):
    _, rows = seeded(corpus)
    a,q = children(corpus[0], rows[0])
    assert rows[0].review_required and rows[0].confidence is None
    assert a.review_required_count == 2 and q.review_required_count == 1


def test_DC06_policy_invalidation(corpus, monkeypatch):
    import app.scope_logical_identity as policy
    _, rows = seeded(corpus)
    old = rows[0].semantic_fingerprint
    monkeypatch.setattr(policy, 'SCOPE_IDENTITY_POLICY', 'prior-policy')
    assert run(corpus)[1][0].semantic_fingerprint != old


@pytest.mark.parametrize('text', [
    'Contenido\nConcepto\n8\nSuministro ........ 16',
    'ITEM 7: ¿Dispone de suministro de sensores?',
    'NO. 7: Suministro de sensores ........ 32',
    '1. Suministro de sensores', 'Fecha 2026-10-14', 'Total $1000',
    'Sección 2.3', 'Versión 4.2', 'En 2020 se compraron 300 piezas',
    'ITEM 47: Comprobante administrativo para suministro de sensores',
    'ITEM 47: No se requiere suministro de sensores',
])
def test_negative_safety(corpus, text):
    assert seeded(corpus, text)[1] == []


def test_SC11_separate_obligations_same_owner(corpus):
    _, rows = seeded(corpus, TEXT + '\nITEM 47: Entrega de informe | Modelo: R-2')
    assert len(rows) == 2 and {r.domain for r in rows} == {'SUPPLY', 'DELIVERABLE'}


def test_SC16_conflicting_attribute_claims(corpus):
    db, _, doc, page = corpus
    seeded(corpus)
    v = vision(db, doc, page, TEXT)
    payload = v.structured_json.copy()
    detail = payload['detail_transcription'].copy()
    detail['parsed_supply_rows'] = [{'raw_visible_text': TEXT, 'description': TEXT,
        'domain': 'SUPPLY', 'brand': 'Different'}]
    payload['detail_transcription'] = detail
    v.structured_json = payload
    db.flush()
    result, rows = run(corpus)
    assert len(rows) == 1 and result.logical_evidence[0][2]
    assert rows[0].applicability == 'UNRESOLVED' and rows[0].review_required


def test_SC19_deselected_cleanup_preserves_perception(corpus):
    from datetime import timedelta
    db, _, doc, page = corpus
    first = vision(db, doc, page, TEXT, fingerprint='same-task')
    assert len(run(corpus)[1]) == 1
    second = vision(db, doc, page, TEXT.replace('sensores', 'actuadores'), fingerprint='same-task')
    second.analysis.created_at = first.analysis.created_at + timedelta(seconds=1)
    second.created_at = first.created_at + timedelta(seconds=1)
    db.flush()
    _, rows = run(corpus)
    assert len(rows) == 1 and rows[0].source_page_result_id == second.id
    assert db.get(type(first), first.id).structured_json['detail_transcription']['raw_text'] == TEXT


def test_SC12_repeated_children_do_not_duplicate(corpus):
    db = corpus[0]
    _, rows = seeded(corpus)
    for _ in range(2):
        children(db, rows[0])
    assert len(db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == rows[0].id)).all()) == 2
    assert len(db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == rows[0].id)).all()) == 1


def test_SC22_persistence_error_not_no_evidence(corpus, monkeypatch):
    import app.scope_detail_materializer as materializer
    norm(corpus[0], corpus[3], text=TEXT)
    def fail(*args, **kwargs):
        raise ValueError('synthetic persistence failure')
    monkeypatch.setattr(materializer, 'replace_scope_details_for_artifact', fail)
    result, rows = run(corpus)
    assert not rows and result.status == 'INVALID_EVIDENCE'
    assert result.artifact_results[0].errors == ('synthetic persistence failure',)
