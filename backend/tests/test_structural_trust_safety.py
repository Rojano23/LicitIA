"""Synthetic structural classes; no blind corpus strings or execution."""
from dataclasses import asdict
import pytest
from app.page_structure_resolver import structural_candidate_from_native_text, structural_candidate_from_ocr_evidence, OcrStructuralEvidence
from test_document_preparation_recovery import batch
from app.document_intelligence_blind_run import prepare_tender_documents

@pytest.fixture(params=['NATIVE','OCR'])
def build(request):
    def candidate(text):
        if request.param=='NATIVE':
            return structural_candidate_from_native_text(page_number=7,native_text=text,source_analysis_id='synthetic-analysis',source_page_result_id='synthetic-page')
        return structural_candidate_from_ocr_evidence(page_number=7,ocr_evidence=[OcrStructuralEvidence(text=text,page_ocr_result_id='synthetic-ocr',confidence=.999)],source_analysis_id='synthetic-analysis')
    return candidate

def abstains(c):
    assert c.structural_quality=='UNKNOWN' and c.page_state.review_required
    assert c.page_state.outgoing_item_key is None
    assert all(s.review_required for s in c.page_state.segments)

def test_ST10_contents(build):abstains(build('Contenido\nConcepto\n8\nAdministración ................ 16'))
def test_ST11_questionnaire(build):
    abstains(build('Respuestas\nSí\nNo\n6\n¿Dispone de procedimientos?'))
    abstains(build('ITEM 6: ¿Cómo describe su operación?'))
def test_ST12_references(build):abstains(build('No. 23: Documentación relacionada ........ 45'))
def test_ST13_ambiguous(build):
    abstains(build('CONCEPTO 15: Registro general'))
    abstains(build('ITEM 15'))
def test_ST14_quantity(build):
    c=build('CONCEPTO 24 | Componente industrial | Cantidad: 6 | Unidad: PZA')
    assert c.structural_quality=='VALID' and not c.page_state.review_required
    assert c.page_state.outgoing_item_key=='24'
    assert build('No | Descripción | Cantidad | Unidad\nNO. 24 | Componente industrial | 6 | PZA').structural_quality=='VALID'
def test_ST15_technical(build):
    c=build('PARTIDA 9: Servicio de calibración de instrumentos')
    assert c.structural_quality=='VALID' and c.page_state.segments[0].item_identity.normalized_key=='9'
    assert build('PARTIDA 9\nServicio de calibración').structural_quality=='VALID'
def test_ST16_mixed(build):
    c=build('Índice\nConcepto\n3\nAdministración ........ 8\n\nITEM 19: Suministro de sensores')
    assert c.structural_quality=='VALID' and c.page_state.outgoing_item_key=='19'
def test_ST17_provenance(build):
    c=build('No. 25: Elemento genérico')
    abstains(c)
    assert c.page_state.provenance.source_analysis_id=='synthetic-analysis'
    assert c.page_state.provenance.source_method==c.source_method
    assert c.page_state.provenance.source_page_result_id in {'synthetic-page','synthetic-ocr'}
def test_ST18_candidate_identity(build):
    c=build('CONCEPTO 25: Elemento genérico')
    abstains(c)
    assert c.page_state.segments[0].item_identity.normalized_key=='25'
    assert c.page_state.segments[0].anchor_raw_text=='CONCEPTO 25'
def test_ST19_idempotence(build):
    for text in ['Concepto\n31\nRegistro general','PARTIDA 12: Suministro de maquinaria']:
        assert asdict(build(text))==asdict(build(text))
def test_ST20_native_capability_unchanged(batch):
    db,tender,docs,_,calls=batch
    result=prepare_tender_documents(db,tender_id=tender.id,document_ids=tuple(d.id for d in docs))
    assert [x.status for x in result]==['PREPARED','UNAVAILABLE','PREPARED']
    assert result[1].reason=='UNSUPPORTED_NATIVE_CAPABILITY' and result[1].page_count==0 and not calls

from test_document_intelligence_integration import corpus, norm, orchestrated
from app.document_intelligence_sources import load_page_structure
from app.models import DocumentPageStructureResolution, TenderScopeSegment
from sqlalchemy import select

@pytest.mark.parametrize('method', ['NATIVE','OCR'])
def test_ST17_ST19_DI_persistence(corpus, method):
    db,tender,doc,page=corpus
    norm(db,page,method,text='CONCEPTO 36: Sección informativa')
    route=load_page_structure(db,doc,page)
    assert route.status!='RESOLVED' and route.selected is None
    candidate=next(x for x in route.candidates if x.source_method.value==method)
    assert candidate.page.document_page_id==page.id
    assert candidate.structural_state.segments[0].item_identity.normalized_key=='36'
    assert candidate.structural_state.outgoing_item_key is None
    for _ in range(2):
        orchestrated(corpus)
        resolution=db.scalar(select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id==page.id))
        assert resolution.status!='RESOLVED' and resolution.selected_source_method is None
        assert not db.scalars(select(TenderScopeSegment).where(TenderScopeSegment.source_document_id==doc.id)).all()


def test_ST19_changed_policy_invalidates_cached_fingerprint(corpus, monkeypatch):
    import app.document_structure_orchestrator as engine
    page=corpus[3]
    current=engine._build_input_fingerprint(page,'same-native',(),())
    monkeypatch.setattr(engine,'STRUCTURE_RESOLVER_VERSION','previous-synthetic-policy')
    assert current!=engine._build_input_fingerprint(page,'same-native',(),())
