"""RT: generated PDFs -> real import/extract/normalize -> IR -> persistence.

No preformatted Native/IR fixtures, blind corpus, OCR or real model calls.
"""
from decimal import Decimal
import hashlib

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import Tender, TenderDocument, DocumentPage, TenderScopeDetail, TenderScopeAttribute, TenderScopeQuantity
from app.scope_detail_materializer import materialize_document_scope_details
from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
from app.structured_evidence_grounding import resolve_payload, validate_manifest
from app.structured_evidence_storage import digest_from_locator, manifest_path, write_manifest

HEADERS = ('ITEM', 'DESCRIPTION', 'QUANTITY', 'UNIT', 'BRAND', 'MODEL')
ROWS = (('31', 'Suministro de sensores', '3', 'PZA', 'Maker A', 'AX-8'),
        ('32', 'Entrega de valvulas', '7', 'PZA', 'Maker B', 'BZ-4'))


def pdf_table(*, rows=ROWS, headers=HEADERS, widths=(48, 200, 72, 45, 75, 65),
              repeat=False, multipage=False, broken=False, ruled=True):
    pdf = pymupdf.open()
    batches = [(row,) for row in rows] if multipage else [rows]
    for batch in batches:
        page = pdf.new_page(width=760, height=600)
        data = [headers, *batch]
        if repeat:
            data = [headers, batch[0], headers, *batch[1:]]
        xs = [36]
        for w in widths[:len(headers)]:
            xs.append(xs[-1] + w)
        ys = [45 + 60 * i for i in range(len(data) + 1)]
        if ruled:
            for x in xs:
                page.draw_line((x, ys[0]), (x, ys[-1]))
            for y in ys:
                page.draw_line((xs[0], y), (xs[-1], y))
        for row_index, values in enumerate(data):
            for col, value in enumerate(values):
                x = xs[col] + 4
                if broken and row_index and col == 1:
                    x = xs[col + 1] - 15  # Actual text crosses a real cell boundary.
                for line_index, line in enumerate(value.split('\n')):
                    page.insert_text((x, ys[row_index] + 18 + line_index * 13), line, fontsize=9)
    data = pdf.tobytes()
    pdf.close()
    return data


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr('app.main.get_licitia_data_root', lambda: tmp_path)
    def denied(*args, **kwargs):
        raise AssertionError('Native bridge cannot acquire perception')
    monkeypatch.setattr('app.ocr.TesseractOCRProvider.recognize', denied)
    monkeypatch.setattr('app.ocr.PaddleOCRProvider.recognize', denied)
    monkeypatch.setattr('app.ollama_vision.OllamaVisionAssistClient', denied)
    client = TestClient(app)
    db = SessionLocal()
    tenders = []
    def prepare(data):
        response = client.post('/tenders', json={'title': 'RT synthetic Native table'})
        assert response.status_code == 201
        tender = response.json()['id']; tenders.append(tender)
        response = client.post(f'/tenders/{tender}/documents/import',
            files=[('files', ('generated.pdf', data, 'application/pdf'))])
        assert response.status_code == 200
        document = response.json()[0]['document_id']
        response = client.post(f'/tenders/{tender}/documents/{document}/extract-pages')
        assert response.status_code == 200
        response = client.post(f'/tenders/{tender}/documents/{document}/normalize')
        assert response.status_code == 200
        result = materialize_document_scope_details(db, tender_id=tender, document_id=document)
        assert not any(r.errors for r in result.artifact_results), result
        details = db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id == document)
            .order_by(TenderScopeDetail.candidate_item_key)).all()
        return result, details, document
    yield db, prepare
    db.rollback()
    for tender in tenders:
        db.execute(delete(Tender).where(Tender.id == tender))
    db.commit(); db.close()


def children(db, details):
    for detail in details:
        a = materialize_scope_attributes_for_scope_detail(db, scope_detail_id=detail.id)
        q = materialize_scope_quantities_for_scope_detail(db, scope_detail_id=detail.id)
        assert not a.errors and not q.errors


def test_RT01_real_pdf_end_to_end(scene):
    db, prepare = scene
    result, details, document = prepare(pdf_table())
    assert result.candidate_count == len(details) == 2
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == document)).all()
    assert len(pages) == 1 and '|' not in pages[0].text and '\t' not in pages[0].text
    assert 'ITEM\nDESCRIPTION\nQUANTITY\nUNIT' in pages[0].text
    children(db, details)
    for detail, expected in zip(details, ROWS, strict=True):
        block = resolve_payload(db, detail)['structured_block']
        assert block.native_table_proof and block.source.page_id == pages[0].id
        assert detail.review_required and detail.confidence is None
        assert detail.candidate_item_key == expected[0]
        q = db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == detail.id))
        assert q.quantity_value == Decimal(expected[2]) and q.unit_raw == expected[3]
        attrs = db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id == detail.id)).all()
        assert {(a.attribute_name, a.value_raw) for a in attrs} == {('brand', expected[4]), ('model', expected[5])}


def test_RT02_multiline_description(scene):
    db, prepare = scene
    row = ('31', 'Suministro de sensores\ncon soporte ajustable\ny cable de prueba', '4', 'PZA', 'Maker C', 'CX-9')
    _, details, _ = prepare(pdf_table(rows=(row,)))
    assert len(details) == 1
    block = resolve_payload(db, details[0])['structured_block']
    assert len(block.field('description').refs) == 3
    assert sum(r.kind == 'CONTINUES' for r in block.relations) == 2
    assert details[0].source_excerpt == 'Suministro de sensores'


def test_RT03_repeated_header_is_context(scene):
    _, prepare = scene
    assert len(prepare(pdf_table(repeat=True))[1]) == 2


def test_RT04_adjacent_rows_ownership(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table(rows=(ROWS[0], ('32', ROWS[0][1], '18', 'PZA', 'Other Maker', 'Y-1'))))
    children(db, details)
    assert len(details) == 2
    assert [db.scalar(select(TenderScopeQuantity.quantity_value).where(TenderScopeQuantity.scope_detail_id == d.id))
            for d in details] == [Decimal('3'), Decimal('18')]


def test_RT05_header_value_fragments_and_proof(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table())
    b = resolve_payload(db, details[0])['structured_block']
    q = b.fragment(b.field('quantity').refs[0])
    header = next(f for f in b.fragments if f.role == 'header_quantity')
    assert q.text == '3' and header.text == 'QUANTITY' and q.start != header.start
    assert any(r.kind == 'HEADER_OF' and r.anchor == header.id and r.target == q.id for r in b.relations)
    assert len({p.bbox for p in b.native_table_proof.cells}) == 12


def test_RT06_provisional_attribute_then_owned_children(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table())
    b = resolve_payload(db, details[0])['structured_block']
    assert b.field('brand').value == 'Maker A' and 'scope_detail_id' not in b.model_dump()
    assert not db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.tender_id == details[0].tender_id)).all()
    children(db, details)
    assert len(db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.tender_id == details[0].tender_id)).all()) == 4


def test_RT07_toc(scene):
    _, prepare = scene
    assert not prepare(pdf_table(headers=('ITEM', 'DESCRIPTION', 'PAGE'),
        rows=(('1', 'Suministro de instrumentos ....', '14'),), widths=(48, 300, 70)))[1]


def test_RT08_questionnaire(scene):
    _, prepare = scene
    assert not prepare(pdf_table(rows=(('31', '¿Entrega de sensores?', '3', 'PZA', 'Maker A', 'AX-8'),)))[1]


def test_RT09_section_numbers(scene):
    _, prepare = scene
    assert not prepare(pdf_table(rows=(('2.1', 'Condiciones de entrega', '3', 'PZA', 'Maker A', 'AX-8'),)))[1]


def test_RT10_ambiguous_geometry(scene):
    _, prepare = scene
    assert not prepare(pdf_table(broken=True))[1]


def test_RT11_page_local_repeated_header(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table(multipage=True))
    assert len(details) == 2
    blocks = [resolve_payload(db, d)['structured_block'] for d in details]
    assert {b.source.page_number for b in blocks} == {1, 2}
    assert len({b.source.page_id for b in blocks}) == 2


@pytest.mark.parametrize('widths', [(55, 220, 76, 50, 78, 65), (45, 190, 80, 55, 90, 70)])
def test_RT12_varied_spacing(scene, widths):
    _, prepare = scene
    assert len(prepare(pdf_table(widths=widths))[1]) == 2


def test_RT13_manifest_replay_immutability_and_forgery(scene):
    db, prepare = scene
    _, details, document = prepare(pdf_table())
    digest = digest_from_locator(details[0].source_locator)
    path = manifest_path(digest); before = path.read_bytes()
    manifest = validate_manifest(db, digest)
    assert hashlib.sha256(before).hexdigest() == digest
    assert write_manifest(manifest) == digest and path.read_bytes() == before
    block = manifest.blocks[0]
    assert all(block.source.text_sha256 for _ in block.fragments)
    proof = block.native_table_proof
    cell = proof.cells[0].model_copy(update={'bbox': (0.0, 0.0, 1.0, 1.0)})
    forged = block.model_copy(update={'native_table_proof': proof.model_copy(update={'cells': (cell,) + proof.cells[1:]})})
    bad = write_manifest(manifest.model_copy(update={'blocks': (forged,)}))
    with pytest.raises(ValueError, match='RELATIONSHIP_MISMATCH'):
        validate_manifest(db, bad)
    result = materialize_document_scope_details(db, tender_id=details[0].tender_id, document_id=document)
    assert result.persisted_count == 2 and path.read_bytes() == before
    assert set(db.scalars(select(TenderScopeDetail.id).where(TenderScopeDetail.source_document_id == document)).all()) == {d.id for d in details}


def test_RT14_unruled_unproven_cells(scene):
    _, prepare = scene
    assert not prepare(pdf_table(ruled=False))[1]


def test_RT15_missing_original_fails_closed(scene):
    db, prepare = scene
    _, details, document = prepare(pdf_table())
    from app.main import _resolve_document_file_path
    row = db.get(TenderDocument, document)
    path = _resolve_document_file_path(row.stored_relative_path)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        validate_manifest(db, digest_from_locator(details[0].source_locator))


def test_RT16_layout_limit_is_explicit(scene, monkeypatch):
    db, prepare = scene
    monkeypatch.setattr('app.native_table_relationships.MAX_WORDS', 0)
    with pytest.raises(AssertionError, match='NATIVE_TABLE_WORD_LIMIT'):
        prepare(pdf_table())


def test_RT17_minimal_four_columns(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table(headers=HEADERS[:4], rows=tuple(r[:4] for r in ROWS)))
    assert len(details) == 2
    children(db, details)
    for detail in details:
        assert len(db.scalars(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == detail.id)).all()) == 1


def test_RT18_modified_original_rejected(scene):
    db, prepare = scene
    _, details, document = prepare(pdf_table())
    from app.main import _resolve_document_file_path
    path = _resolve_document_file_path(db.get(TenderDocument, document).stored_relative_path)
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='ORIGINAL_INTEGRITY_MISMATCH'):
        validate_manifest(db, digest_from_locator(details[0].source_locator))


def test_RT19_engine_version_rejected(scene):
    db, prepare = scene
    _, details, _ = prepare(pdf_table())
    manifest = validate_manifest(db, digest_from_locator(details[0].source_locator))
    block = manifest.blocks[0]
    forged = block.model_copy(update={'native_table_proof': block.native_table_proof.model_copy(update={'engine_version': 'different'})})
    digest = write_manifest(manifest.model_copy(update={'blocks': (forged,)}))
    with pytest.raises(ValueError, match='ENGINE_MISMATCH'):
        validate_manifest(db, digest)


@pytest.mark.parametrize(('unit', 'quantity'), [('KG', '12.5'), ('M', '24')])
def test_RT20_varied_units_and_values(scene, unit, quantity):
    db, prepare = scene
    row = ('43', 'Suministro de material de montaje', quantity, unit, 'Generic Maker', 'GM-2')
    _, details, _ = prepare(pdf_table(rows=(row,)))
    assert len(details) == 1
    children(db, details)
    q = db.scalar(select(TenderScopeQuantity).where(TenderScopeQuantity.scope_detail_id == details[0].id))
    assert q.quantity_value == Decimal(quantity) and q.unit_raw == unit
