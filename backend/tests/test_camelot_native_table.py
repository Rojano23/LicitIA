"""CT: real generated PDF -> production import/Native -> Camelot -> Native proof."""
from decimal import Decimal
import hashlib
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import select

from tests.test_native_table_bridge import scene, pdf_table, children, ROWS
from app.models import TenderScopeQuantity, TenderScopeAttribute, TenderScopeDetail
from app.camelot_table_contract import CamelotNativeProof, bottom_to_top, digest
from app.camelot_table_adapter import CamelotTableRelationshipAdapter
from app.structured_evidence_grounding import resolve_payload,validate_manifest
from app.structured_evidence_storage import digest_from_locator,write_manifest,manifest_path
from app.scope_detail_materializer import materialize_document_scope_details


def block(db,detail):
    b=resolve_payload(db,detail)['structured_block']
    assert isinstance(b.native_table_proof,CamelotNativeProof)
    return b


def overflow_pdf(font=12, header_offset=10):
    pdf=pymupdf.open();p=pdf.new_page(width=700,height=450)
    xs=[30,90,350,450,530];ys=[50,110,180,250]
    for x in xs:p.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:p.draw_line((xs[0],y),(xs[-1],y))
    rows=[('ITEM','DESCRIPTION','QUANTITY','UNIT'),('41','Suministro de conexiones','4','PZA'),('42','Entrega de piezas','9','PZA')]
    for r,values in enumerate(rows):
        for col,text in enumerate(values):
            p.insert_text((xs[col]+4,ys[r]+(header_offset if r==0 else 22)),text,fontsize=font if r==0 else 10)
    data=pdf.tobytes();pdf.close();return data


def test_CT01_two_parents(scene):
    db,prepare=scene
    result,details,_=prepare(pdf_table())
    assert result.candidate_count==len(details)==2
    assert all(block(db,d).native_table_proof.proposal.parser=='lattice' for d in details)


def test_CT02_quantity_ownership(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());children(db,details)
    assert [db.scalar(select(TenderScopeQuantity.quantity_value).where(TenderScopeQuantity.scope_detail_id==d.id)) for d in details]==[Decimal('3'),Decimal('7')]


def test_CT03_model_and_attribute_ownership(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());children(db,details)
    for d,r in zip(details,ROWS,strict=True):
        attrs=db.scalars(select(TenderScopeAttribute).where(TenderScopeAttribute.scope_detail_id==d.id)).all()
        assert {(a.attribute_name,a.value_raw) for a in attrs}=={('brand',r[4]),('model',r[5])}
        assert block(db,d).field('description').value==r[1]


def test_CT04_multiline(scene):
    db,prepare=scene;row=('31','Suministro de cables\ncon protección adicional','5','PZA','Generic Brand','G-14')
    _,details,_=prepare(pdf_table(rows=(row,)))
    b=block(db,details[0]);assert len(details)==1 and len(b.field('description').refs)==2
    assert any(r.kind=='CONTINUES' for r in b.relations)


def test_CT05_repeated_header(scene):
    _,prepare=scene;assert len(prepare(pdf_table(repeat=True))[1])==2


def test_CT06_overflow_is_proved_without_containment_patch(scene):
    db,prepare=scene;_,details,_=prepare(overflow_pdf())
    assert len(details)==2
    proof=block(db,details[0]).native_table_proof
    assert any(w.bbox[1]<c.bbox[1] for c in proof.cells if c.header for w in c.words)


@pytest.mark.parametrize(('font','offset'),[(9,7),(13,11),(15,12)])
def test_CT07_varied_font_overflow(scene,font,offset):
    db,prepare=scene;_,details,_=prepare(overflow_pdf(font,offset))
    assert len(details)==2 and all(block(db,d).native_table_proof for d in details)


def test_CT08_adjacent_identical_descriptions_no_cross_children(scene):
    db,prepare=scene
    rows=(ROWS[0],('32',ROWS[0][1],'19','PZA','Different Brand','D-9'))
    _,details,_=prepare(pdf_table(rows=rows));children(db,details)
    for d,r in zip(details,rows,strict=True):
        assert db.scalar(select(TenderScopeQuantity.quantity_value).where(TenderScopeQuantity.scope_detail_id==d.id))==Decimal(r[2])
        assert db.scalar(select(TenderScopeAttribute.value_raw).where(TenderScopeAttribute.scope_detail_id==d.id,TenderScopeAttribute.attribute_name=='brand'))==r[4]


def test_CT09_toc_not_procurement(scene):
    _,prepare=scene
    assert not prepare(pdf_table(headers=('ITEM','DESCRIPTION','PAGE'),rows=(('1','Lista de materiales ....','9'),),widths=(60,260,80)))[1]


def test_CT10_questionnaire_not_procurement(scene):
    _,prepare=scene
    assert not prepare(pdf_table(rows=(('31','¿Suministro de equipos?','3','PZA','Generic','X'),)))[1]


def test_CT11_broken_table(scene):
    _,prepare=scene;assert not prepare(pdf_table(broken=True))[1]


def alter_proposals(monkeypatch,alter):
    original=CamelotTableRelationshipAdapter.propose
    def changed(self,*args,**kwargs):
        result=original(self,*args,**kwargs)
        changed = tuple(alter(t) for t in result)
        return tuple(t.model_copy(update={'proposal_sha256':digest(t.model_dump(mode='json',exclude={'proposal_sha256'}))}) for t in changed)
    monkeypatch.setattr(CamelotTableRelationshipAdapter,'propose',changed)


def test_CT12_camelot_only_text_rejected(scene,monkeypatch):
    _,prepare=scene
    def alter(t):
        cells=list(t.cells);cells[-1]=cells[-1].model_copy(update={'raw_text':'UNSUPPORTED DETECTOR VALUE'})
        return t.model_copy(update={'cells':tuple(cells)})
    alter_proposals(monkeypatch,alter)
    assert not prepare(pdf_table())[1]


def test_CT13_ambiguous_fragment_membership(scene,monkeypatch):
    _,prepare=scene
    def alter(t):
        cells=list(t.cells);cells[1]=cells[1].model_copy(update={'bbox':cells[0].bbox})
        return t.model_copy(update={'cells':tuple(cells)})
    alter_proposals(monkeypatch,alter)
    assert not prepare(pdf_table())[1]


def test_CT14_wrong_source_generation_fails(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table())
    m=validate_manifest(db,digest_from_locator(details[0].source_locator));b=m.blocks[0]
    forged=b.model_copy(update={'source':b.source.model_copy(update={'generation_id':'wrong-generation'})})
    bad=write_manifest(m.model_copy(update={'blocks':(forged,)}))
    with pytest.raises(ValueError,match='GENERATION_STALE'):validate_manifest(db,bad)


@pytest.mark.parametrize('height,box',[(800,(10,20,200,90)),(450,(0,0,100,100)),(300,(5,0,10,300))])
def test_CT15_coordinate_transform(height,box):
    top=bottom_to_top(box,height)
    assert bottom_to_top(top,height)==box and top[0]==box[0] and top[2]==box[2]


def test_CT16_proof_replay_identity(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table())
    first=block(db,details[0]);second=block(db,details[0])
    assert first==second and first.native_table_proof.proof_sha256==second.native_table_proof.proof_sha256
    p=first.native_table_proof
    assert p.proof_sha256==digest(p.model_dump(mode='json',exclude={'proof_sha256'}))


def test_CT17_tampered_proof(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table())
    m=validate_manifest(db,digest_from_locator(details[0].source_locator));b=m.blocks[0]
    proof=b.native_table_proof.model_copy(update={'row_index':99})
    bad=write_manifest(m.model_copy(update={'blocks':(b.model_copy(update={'native_table_proof':proof}),)}))
    with pytest.raises(ValueError,match='MISMATCH'):validate_manifest(db,bad)


def test_CT18_manifest_and_literals(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table())
    digest_=digest_from_locator(details[0].source_locator);m=validate_manifest(db,digest_)
    assert hashlib.sha256(manifest_path(digest_).read_bytes()).hexdigest()==digest_
    b=m.blocks[0];assert all(f.text for f in b.fragments)
    assert {c.role for c in b.native_table_proof.cells if c.header}>={'item','description','quantity','unit'}


def test_CT19_idempotence(scene):
    db,prepare=scene;_,details,document=prepare(pdf_table());ids={d.id for d in details};locators={d.source_locator for d in details}
    materialize_document_scope_details(db,tender_id=details[0].tender_id,document_id=document)
    rows=db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==document)).all()
    assert {d.id for d in rows}==ids and {d.source_locator for d in rows}==locators


def test_CT20_generic_vocabulary(scene):
    db,prepare=scene
    row=('87','Delivery of custom widgets','12','KG','Example Manufacturer','ZETA-11')
    _,details,_=prepare(pdf_table(rows=(row,)));children(db,details)
    assert block(db,details[0]).item_raw=='87'


def test_CT21_missing_manifest(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());dg=digest_from_locator(details[0].source_locator)
    manifest_path(dg).unlink()
    with pytest.raises(ValueError,match='STRUCTURED_MANIFEST_MISSING'):validate_manifest(db,dg)


def test_CT22_proof_config_hash_forgery_rejected(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());m=validate_manifest(db,digest_from_locator(details[0].source_locator));b=m.blocks[0]
    p=b.native_table_proof;q=p.proposal.model_copy(update={'config_sha256':'0'*64});q=q.model_copy(update={'proposal_sha256':digest(q.model_dump(mode='json',exclude={'proposal_sha256'}))})
    p=p.model_copy(update={'proposal':q});p=p.model_copy(update={'proof_sha256':digest(p.model_dump(mode='json',exclude={'proof_sha256'}))})
    bad=write_manifest(m.model_copy(update={'blocks':(b.model_copy(update={'native_table_proof':p}),)}))
    with pytest.raises(ValueError,match='ENGINE_OR_CONFIG_MISMATCH'):validate_manifest(db,bad)



def test_CT23_legacy_v6d_manifest_still_replays(scene):
    from app.document_intelligence_sources import _enumerate_persisted_artifacts_for_document
    from app.models import DocumentPage
    from app.structured_evidence_grounding import source_text
    from app.native_table_relationships import reconstruct_native_tables
    from app.structured_evidence import StructuredEvidenceManifest, NativeTableProof
    db,prepare=scene;_,details,document=prepare(pdf_table())
    pages=db.scalars(select(DocumentPage).where(DocumentPage.document_id==document)).all()
    enum=_enumerate_persisted_artifacts_for_document(db,tender_id=details[0].tender_id,document_id=document,pages=pages)
    artifact=next(x.artifact for x in enum.active if x.artifact.source_method=='NATIVE')
    source,text=source_text(db,artifact)
    legacy=reconstruct_native_tables(db,artifact,source,text)
    assert len(legacy)==2 and isinstance(legacy[0].native_table_proof,NativeTableProof)
    dg=write_manifest(StructuredEvidenceManifest(blocks=(legacy[0],)))
    assert validate_manifest(db,dg).blocks[0]==legacy[0]


def test_CT24_detector_whitespace_does_not_replace_native_quote(scene,monkeypatch):
    db,prepare=scene
    def alter(t):
        return t.model_copy(update={'cells':tuple(c.model_copy(update={'raw_text': '  '+c.raw_text.replace(' ','   ')+'  '}) for c in t.cells)})
    alter_proposals(monkeypatch,alter)
    _,details,_=prepare(pdf_table())
    b=block(db,details[0])
    assert details[0].source_excerpt==ROWS[0][1]
    assert b.field('description').value==ROWS[0][1]
    assert all(f.text==f.text.strip() for f in b.fragments)


def test_CT25_wrong_original_hash_fails(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());m=validate_manifest(db,digest_from_locator(details[0].source_locator));b=m.blocks[0]
    bad=write_manifest(m.model_copy(update={'blocks':(b.model_copy(update={'source':b.source.model_copy(update={'original_sha256':'0'*64})}),)}))
    with pytest.raises(ValueError,match='GENERATION_STALE'):validate_manifest(db,bad)


def test_CT26_wrong_page_fails(scene):
    db,prepare=scene;_,details,_=prepare(pdf_table());m=validate_manifest(db,digest_from_locator(details[0].source_locator));b=m.blocks[0]
    bad=write_manifest(m.model_copy(update={'blocks':(b.model_copy(update={'source':b.source.model_copy(update={'page_id':'missing-page'})}),)}))
    with pytest.raises(ValueError,match='PAGE_IDENTITY_MISMATCH'):validate_manifest(db,bad)


def test_CT27_merged_cell_abstains(scene):
    _,prepare=scene
    pdf=pymupdf.open();page=pdf.new_page(width=700,height=400)
    xs=[30,90,350,450,530];ys=[50,110,180,250]
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    for i,x in enumerate(xs):
        if i==2:
            page.draw_line((x,ys[0]),(x,ys[1]));page.draw_line((x,ys[2]),(x,ys[-1]))
        else:page.draw_line((x,ys[0]),(x,ys[-1]))
    rows=[('ITEM','DESCRIPTION','QUANTITY','UNIT'),('1','Suministro de tubos','3','PZA'),('2','Entrega de soportes','5','PZA')]
    for r,row in enumerate(rows):
        for col,t in enumerate(row):page.insert_text((xs[col]+4,ys[r]+20),t,fontsize=10)
    data=pdf.tobytes();pdf.close()
    assert not prepare(data)[1]


def test_CT28_rotated_page_abstains(scene):
    _,prepare=scene
    pdf=pymupdf.open(stream=pdf_table(),filetype='pdf');pdf[0].set_rotation(90)
    data=pdf.tobytes();pdf.close()
    assert not prepare(data)[1]
