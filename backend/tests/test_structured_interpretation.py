"""SI contracts: invented generic data; no blind corpus or provider invocation.

SI21–SI23 are activated in test_perception_sufficiency.py for V.6c.
"""
from decimal import Decimal
import hashlib
from dataclasses import replace
import pytest
from sqlalchemy import select
from app.models import TenderScopeDetail, TenderScopeAttribute, TenderScopeQuantity, PageOcrResult
from app.structured_evidence import EvidenceSource, StructuredEvidenceManifest, reconstruct
from app.structured_evidence_storage import read_manifest, digest_from_locator, manifest_path
from app.structured_evidence_grounding import resolve_payload, validate_manifest
from test_document_intelligence_integration import corpus, norm as base_norm, vision, add_page
from test_native_structured_coverage import run, children

HEADER = 'Partida | Descripción | Cantidad | Unidad | Marca | Modelo'
ROW = '73 | Suministro de actuadores | 12 | PZA | Fabrica Z | AZ-2'
TABLE = HEADER + '\n' + ROW


def norm(db,page,method='NATIVE',text=TABLE):
    n = base_norm(db,page,method,text)
    if method == 'OCR':
        row = db.get(PageOcrResult,n.page_ocr_result_id)
        n.engine = row.engine
        db.flush()
    return n


def change_generation(corpus,text):
    from app.models import NormalizedContent
    db,_,_,page = corpus
    n = db.scalar(select(NormalizedContent).where(NormalizedContent.document_page_id == page.id,
        NormalizedContent.source_type == 'NATIVE_PDF'))
    n.normalized_text = text
    n.content_sha256 = hashlib.sha256(text.encode()).hexdigest()
    n.char_count = len(text)
    page.text = text
    db.flush()
    return n


def source(text, method='NATIVE'):
    return EvidenceSource(tender_id='synthetic-tender',document_id='synthetic-document',page_id='synthetic-page',
        page_number=1,revision=1,method=method,artifact_key='synthetic-source',generation_id='synthetic-generation',
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),offset_space='NORMALIZED_TEXT')


def blocks(text=TABLE, method='NATIVE'):
    return reconstruct(source(text,method),text)


def seeded(corpus,text=TABLE,method='NATIVE'):
    norm(corpus[0],corpus[3],method,text)
    result,rows = run(corpus)
    assert not any(r.errors for r in result.artifact_results),result
    return result,rows


def test_SI01_explicit_refs():
    text = 'ITEM 73: Suministro de actuadores | Cantidad: 12 | Unidad: PZA'
    b, = blocks(text)
    assert b.review_required and b.field('quantity').value == '12'
    assert all(text[f.start:f.end] == f.text for f in b.fragments)


def test_SI02_multiline_composition(corpus):
    text = 'ITEM 73\nSuministro de actuadores\n  con soporte desmontable\nCantidad: 12\nUnidad: PZA'
    _,rows = seeded(corpus,text)
    assert len(rows) == 1
    b = resolve_payload(corpus[0],rows[0])['structured_block']
    assert len(b.field('description').refs) == 2
    assert rows[0].source_excerpt == 'Suministro de actuadores'
    assert rows[0].description == 'Suministro de actuadores con soporte desmontable'


def test_SI03_header_cell_roles(corpus):
    _,rows = seeded(corpus)
    payload = resolve_payload(corpus[0],rows[0]); b = payload['structured_block']
    assert b.field('quantity').value == '12' and b.field('unit').value == 'PZA'
    assert any(e.kind == 'HEADER_OF' and b.fragment(e.anchor).text == 'Cantidad' for e in b.relations)
    assert payload['valid_scope_identity'] and rows[0].review_required and rows[0].confidence is None


def test_SI04_distinct_rows(corpus):
    _,rows = seeded(corpus,TABLE + '\n' + ROW.replace('73','74'))
    assert len(rows) == 2 and len({r.candidate_item_key for r in rows}) == 2


def test_SI05_repeated_headers():
    b = blocks(TABLE + '\n' + TABLE.replace('73','74'))
    assert len(b) == 2 and {x.item_raw for x in b} == {'73','74'}
    assert not blocks(HEADER)


@pytest.mark.parametrize('case,text',[
 ('SI06','No | Sección | Página\n1 | Suministro de equipos | 8'),
 ('SI06b','ITEM 73: Suministro de equipos .... 14'),
 ('SI07','No | Pregunta | Sí\n1 | ¿Entrega de equipos? | Sí'),
 ('SI08','3.2 Instalación del edificio\n12 PZA'),
 ('SI09','Fecha: 2026-09-01\nImporte: $1200\n12 PZA'),
 ('SI19','Se revisarán las políticas generales. 73 equipos.'),
])
def test_negative_positive_identity(case,text):
    assert blocks(text) == (),case


def test_SI10_ocr_explicit_order(corpus):
    _,rows = seeded(corpus,TABLE,'OCR')
    assert len(rows) == 1 and rows[0].source_method == 'OCR'
    b = resolve_payload(corpus[0],rows[0])['structured_block']
    assert b.source.offset_space == 'NORMALIZED_TEXT'
    assert b.field('quantity').value == '12'


def test_SI11_ocr_unproven_fragments():
    assert not blocks('73\nSuministro de actuadores\n12\nPZA','OCR')


def test_SI12_separate_field_grounding(corpus):
    _,rows = seeded(corpus)
    b = resolve_payload(corpus[0],rows[0])['structured_block']
    desc,q,u = [b.fragment(b.field(role).refs[0]) for role in ('description','quantity','unit')]
    assert desc.end < q.start < u.start and q.text not in rows[0].source_excerpt
    assert rows[0].source_excerpt == desc.text


def test_SI13_provisional_attribute():
    b, = blocks(TABLE)
    assert b.field('brand').value == 'Fabrica Z'
    assert b.field('brand').refs and b.relations
    # Runtime evidence has no invented persisted ScopeDetail FK.
    assert 'scope_detail_id' not in b.model_dump()


def test_SI14_quantity_children(corpus):
    _,rows = seeded(corpus)
    a,q = children(corpus[0],rows[0])
    assert (a.persisted_count,q.persisted_count) == (2,1),(a,q)
    child = corpus[0].scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == rows[0].id))
    assert child.quantity_value == Decimal('12') and child.unit_raw == 'PZA'
    assert child.source_excerpt == '12' and child.unit_raw not in child.source_excerpt


def test_SI15_no_neighbor_crossing(corpus):
    _,rows = seeded(corpus,TABLE + '\n' + ROW.replace('73','74').replace('12','19').replace('Fabrica Z','Fabrica Y'))
    for row in rows:
        a,q = children(corpus[0],row)
        assert (a.persisted_count,q.persisted_count) == (2,1)
        attr = corpus[0].scalar(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == row.id,TenderScopeAttribute.attribute_name == 'brand'))
        qty = corpus[0].scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == row.id))
        assert (attr.value_raw,qty.quantity_value) == (('Fabrica Z',Decimal(12)) if '73' in row.candidate_item_key else ('Fabrica Y',Decimal(19)))


def test_SI16_SI17_comparable_capabilities(corpus):
    db,_,_,page = corpus
    seeded(corpus)
    norm(db,page,'OCR',TABLE)
    result,rows = run(corpus)
    assert len(rows) == 1 and len(result.logical_evidence[0].source_artifact_keys) == 2
    manifest = validate_manifest(db,digest_from_locator(rows[0].source_locator))
    assert {b.source.method for b in manifest.blocks} == {'NATIVE','OCR'}


def test_SI18_ambiguous_owner_no_children(corpus):
    text = 'ITEM 73\nSuministro de actuadores\n  con soporte\nCantidad: 12\nCantidad: 19\nUnidad: PZA'
    _,rows = seeded(corpus,text)
    assert rows[0].applicability == 'UNRESOLVED'
    assert resolve_payload(corpus[0],rows[0])['structured_block'].field('quantity')
    assert all(r.persisted_count == 0 for r in children(corpus[0],rows[0]))


def test_SI20_idempotence_generation(corpus):
    db = corpus[0]
    _,rows = seeded(corpus)
    children(db,rows[0]); identity = rows[0].id; locator = rows[0].source_locator
    assert run(corpus)[1][0].id == identity
    assert run(corpus)[1][0].source_locator == locator
    assert db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == identity))
    n = change_generation(corpus,TABLE.replace('12','19'))
    with pytest.raises(ValueError,match='STALE|ACTIVE'):
        resolve_payload(db,rows[0])
    assert n.content_sha256 != read_manifest(digest_from_locator(locator)).blocks[0].source.text_sha256


def test_SI25_normalized_ocr_offsets(corpus):
    db,_,_,page = corpus
    normalized = norm(db,page,'OCR',TABLE)
    raw = db.get(PageOcrResult,normalized.page_ocr_result_id)
    raw.text = '\n\n' + TABLE.replace('\n','\r\n') + '\n'
    # Real normalizer removes surrounding/blank whitespace; offsets remain in
    # NORMALIZED_TEXT, never applied to this different raw offset space.
    from app.content_normalization import _normalize_text
    normalized.normalized_text = _normalize_text(raw.text)
    normalized.content_sha256 = hashlib.sha256(normalized.normalized_text.encode()).hexdigest()
    db.flush()
    result,rows = run(corpus)
    assert rows and not any(r.errors for r in result.artifact_results)
    assert resolve_payload(db,rows[0])['structured_block'].field('quantity').value == '12'
    assert children(db,rows[0])[1].persisted_count == 1


@pytest.mark.parametrize('defect',['missing','corrupt','stale'])
def test_SI26_fail_closed(corpus,defect):
    _,rows = seeded(corpus)
    row = rows[0]
    path = manifest_path(digest_from_locator(row.source_locator))
    original = path.read_bytes()
    try:
        if defect == 'missing': path.unlink()
        elif defect == 'corrupt': path.write_bytes(b'{}')
        else:
            change_generation(corpus,TABLE.replace('12','19'))
        assert children(corpus[0],row)[1].status == 'INVALID_EVIDENCE'
    finally:
        if defect != 'stale': path.write_bytes(original)


def test_SI27_corroboration_identity(corpus):
    db,_,_,page = corpus
    _,rows = seeded(corpus); identity = rows[0].id
    from app.scope_review import append_scope_review, ScopeReviewDecisionInput, get_effective_scope_review
    review = append_scope_review(db,tender_id=rows[0].tender_id,scope_detail_id=identity,
        decision=ScopeReviewDecisionInput(decision='CONFIRMED',note='Synthetic acceptance'))
    snapshot = review.machine_snapshot
    norm(db,page,'OCR',TABLE)
    _,rows = run(corpus)
    assert rows[0].id == identity and rows[0].confidence is None and rows[0].review_required
    view = get_effective_scope_review(db,tender_id=rows[0].tender_id,scope_detail_id=identity)
    assert view.effective_status == 'CONFIRMED' and view.human_review_status == 'CURRENT'
    assert view.latest_review.machine_snapshot == snapshot


def test_SI28_conflicting_values(corpus):
    db,_,_,page = corpus
    seeded(corpus)
    norm(db,page,'OCR',TABLE.replace('12','19'))
    result,rows = run(corpus)
    assert len(rows) == 1 and rows[0].applicability == 'UNRESOLVED'
    assert result.logical_evidence[0].conflict
    m = read_manifest(digest_from_locator(rows[0].source_locator))
    assert {b.field('quantity').value for b in m.blocks} == {'12','19'}
    assert all(r.persisted_count == 0 for r in children(db,rows[0]))


def test_SI29_no_cross_page_header(corpus):
    db,_,doc,_ = corpus
    seeded(corpus)
    page2 = add_page(db,doc,2)
    norm(db,page2,text=ROW.replace('73','74'))
    _,rows = run(corpus)
    assert len(rows) == 1
    assert not blocks('Continuación de la página anterior\n12 | PZA')


def test_SI30_vision_detail_and_no_fake_geometry(corpus):
    db,_,doc,page = corpus
    row = vision(db,doc,page,TABLE)
    # Explicit source detail is used; existing parsed rows already propose a
    # different legacy shape, so exercise the public neutral interpretation.
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    from app.structured_evidence_grounding import extract_candidates
    artifacts = _enumerate_persisted_artifacts_for_document(db,tender_id=doc.tender_id,document_id=doc.id,pages=[page])
    artifact = next(x.artifact for x in artifacts.active if x.artifact.source_method == 'VISION')
    c, = extract_candidates(db,artifact)
    assert c.structured_block.source.method == 'VISION'
    assert not any('coordinates' in f.model_dump() for f in c.structured_block.fragments)
    row.structured_json = {'_vision_runtime':{'task_type':'STRUCTURE_SCOPE'}}
    db.flush()
    with pytest.raises(ValueError): resolve_payload(db,c)


def test_SI31_acquisition_free(corpus,monkeypatch):
    def denied(*args,**kwargs):
        raise AssertionError('Reconstruction must not acquire perception')
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize',denied)
    monkeypatch.setattr('app.ocr.PaddleOCRProvider.recognize',denied)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient',denied)
    monkeypatch.setattr('app.selective_ocr_executor.execute_planned_ocr',denied)
    monkeypatch.setattr('app.selective_vision_executor.execute_planned_vision',denied)
    _,rows = seeded(corpus)
    assert len(rows) == 1 and children(corpus[0],rows[0])[1].persisted_count == 1


def test_SI32_parent_replacement_cascade(corpus):
    db,_,_,page = corpus
    _,rows = seeded(corpus); parent = rows[0]; children(db,parent)
    manifest = manifest_path(digest_from_locator(parent.source_locator)); identity = parent.id
    change_generation(corpus,TABLE.replace('12','19'))
    _,new = run(corpus)
    assert new[0].id != identity
    assert not db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == identity)).all()
    assert manifest.exists()


def test_SI03_noun_table_preserves_unknown_domain(corpus):
    _,rows = seeded(corpus,TABLE.replace('Suministro de actuadores','Actuadores de control'))
    assert rows[0].domain == 'OTHER' and rows[0].review_required
    assert children(corpus[0],rows[0])[1].persisted_count == 1


def test_SI04_mixed_labelled_and_table_same_description(corpus):
    text = 'ITEM 72: Suministro de actuadores | Cantidad: 8 | Unidad: PZA\n' + TABLE
    _,rows = seeded(corpus,text)
    assert len(rows) == 2
    assert {r.quantity_raw for r in rows} == {'8','12'}


def test_SI16_distinct_occurrences_not_collapsed(corpus):
    _,rows = seeded(corpus,TABLE + '\n' + ROW)
    assert len(rows) == 2
    assert {resolve_payload(corpus[0],r)['structured_block'].occurrence for r in rows} == {0,1}


def test_SI26_hash_valid_forged_relationship_fails(corpus):
    _,rows = seeded(corpus)
    from app.structured_evidence_storage import write_manifest
    row = rows[0]
    manifest = read_manifest(digest_from_locator(row.source_locator))
    block = manifest.blocks[0]
    relation = block.relations[0].model_copy(update={'rule':'invented-relationship'})
    forged = block.model_copy(update={'relations':(relation,)+block.relations[1:]})
    digest = write_manifest(StructuredEvidenceManifest(blocks=(forged,)))
    with pytest.raises(ValueError,match='RELATIONSHIP_MISMATCH'):
        validate_manifest(corpus[0],digest)


def test_SI18_continuity_conflict_removes_local_owner(corpus,monkeypatch):
    from app.scope_detail_materializer import _scope_artifact_context
    from app.scope_detail_adapters import adapt_and_persist_scope_detail_artifact
    from app.document_intelligence_sources import (_enumerate_persisted_artifacts_for_document,
        load_document_transcriptions,load_page_structure)
    db,_,doc,page = corpus
    norm(db,page,text=TABLE)
    context = _scope_artifact_context(db,
        _enumerate_persisted_artifacts_for_document(db,tender_id=doc.tender_id,document_id=doc.id,pages=[page]).active[0].artifact,
        load_document_transcriptions(db,doc),{page.id:load_page_structure(db,doc,page)})
    route = context.structure.model_copy(update={'status':'REVIEW_REQUIRED','diagnostics':('STRUCTURAL_BOUNDARY_CONFLICT',)})
    result = adapt_and_persist_scope_detail_artifact(db,replace(context,structure=route),persist=False)
    assert len(result.candidates) == 1
    assert result.candidates[0].applicability == 'UNRESOLVED' and result.candidates[0].candidate_item_key is None


def test_SI20_same_fact_changed_generation_invalidates_human_review(corpus):
    from app.scope_review import append_scope_review, ScopeReviewDecisionInput, get_effective_scope_review, list_scope_review_history
    db = corpus[0]
    _,rows = seeded(corpus)
    old = rows[0]
    review = append_scope_review(db,tender_id=old.tender_id,scope_detail_id=old.id,
        decision=ScopeReviewDecisionInput(decision='CONFIRMED'))
    change_generation(corpus,TABLE + '\n' + HEADER)
    result,rows = run(corpus)
    assert not any(r.errors for r in result.artifact_results),result
    assert rows[0].id != old.id
    assert get_effective_scope_review(db,tender_id=rows[0].tender_id,scope_detail_id=rows[0].id).human_review_status == 'NO_REVIEW'
    assert list_scope_review_history(db,tender_id=old.tender_id,scope_detail_id=old.id) == (review,)


def test_SI14_persistence_rejects_forged_numeric_value(corpus):
    from dataclasses import fields
    from app.scope_quantities import ScopeQuantityCandidate, replace_scope_quantities_for_artifact
    db = corpus[0]
    _,rows = seeded(corpus); children(db,rows[0])
    child = db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == rows[0].id))
    candidate = ScopeQuantityCandidate(**{f.name:getattr(child,f.name) for f in fields(ScopeQuantityCandidate)})
    with pytest.raises(ValueError,match='STRUCTURED_QUANTITY_VALUE_MISMATCH'), db.begin_nested():
        replace_scope_quantities_for_artifact(db,tender_id=child.tender_id,scope_detail_id=child.scope_detail_id,
            source_document_id=child.source_document_id,document_page_id=child.document_page_id,
            source_artifact_key=child.source_artifact_key,candidates=[replace(candidate,quantity_value=Decimal('999'))])


def test_SI30_vision_image_identity_is_frozen(corpus):
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    from app.structured_evidence_grounding import extract_candidates
    db,_,doc,page = corpus
    row = vision(db,doc,page,TABLE)
    artifact = _enumerate_persisted_artifacts_for_document(db,tender_id=doc.tender_id,document_id=doc.id,pages=[page]).active[0].artifact
    candidate, = extract_candidates(db,artifact)
    assert dict(candidate.structured_block.source.acquisition_identity)['image_sha256'] == row.image_sha256
    row.image_sha256 = '0' * 64
    db.flush()
    with pytest.raises(ValueError,match='GENERATION_STALE'):
        validate_manifest(db,digest_from_locator(candidate.source_locator))


def test_SI16_cropped_occurrence_requires_comparable_scope():
    from app.structured_evidence_grounding import fact_key
    block, = blocks()
    whole = block.model_copy(update={'source':block.source.model_copy(update={'source_scope':'FULL_PAGE'})})
    crop = block.model_copy(update={'source':block.source.model_copy(update={'method':'OCR','source_scope':'REGION','region_id':'synthetic-region'})})
    unknown = block.model_copy(update={'source':block.source.model_copy(update={'method':'VISION','artifact_key':'other-source'})})
    assert len({fact_key(whole),fact_key(crop),fact_key(unknown)}) == 3
