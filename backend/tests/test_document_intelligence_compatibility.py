"""Shape-only compatibility; legacy shapes retain DI lineage alongside them."""
import pytest
from app.company_evidence import SourceSegment
from app.document_intelligence import Capability, PerceptionEvidence, PageIdentity, normalize_perception_evidence
from app.requirement_extraction import SourceBlock
from app.scope_detail_adapters import ScopeDetailEvidenceArtifact
from app.page_structure_resolver import structural_candidate_from_native_text

@pytest.fixture
def neutral():
    return normalize_perception_evidence(source_method="NATIVE_PDF",
        page=PageIdentity(tender_id="synthetic-tender", document_id="document", document_page_id="page", page_number=1,
                          document_version="revision-2"),
        capability=Capability.TRANSCRIPTION, text="PARTIDA 1 servicio contractual",
        source_artifact_key="normalized:content-1", generation_id="hash-1", normalized_content_id="content-1",
        source_locator="page:1|block:1", source_analysis_id="analysis-1", source_page_result_id="result-1")

def test_requirements_adapter_shape(neutral):
    block = SourceBlock(source_document_id=neutral.page.document_id, source_filename="synthetic.pdf",
        source_page=neutral.page.page_number, document_page_id=neutral.page.document_page_id,
        normalized_content_id=neutral.normalized_content_id, classification_type=None,
        source_type="NATIVE_PDF", text=neutral.text, page_text=neutral.text)
    assert (block.source_document_id, block.source_page, block.document_page_id,
            block.normalized_content_id, block.text) == ("document", 1, "page", "content-1", neutral.text)
    assert neutral.page.document_version == "revision-2" and neutral.source_analysis_id == "analysis-1"

def test_evidence_adapter_shape(neutral):
    segment = SourceSegment(source_page=neutral.page.page_number, source_locator=neutral.source_locator, text=neutral.text)
    assert segment.source_locator == "page:1|block:1" and segment.text == neutral.text and segment.source_page == 1
    assert neutral.source_artifact_key == "normalized:content-1" and neutral.page.document_version == "revision-2"

def test_scope_adapter_shape(neutral):
    artifact = ScopeDetailEvidenceArtifact(tender_id=neutral.page.tender_id,
        source_document_id=neutral.page.document_id, document_page_id=neutral.page.document_page_id,
        source_method=neutral.source_method.value, source_artifact_key=neutral.source_artifact_key,
        source_locator=neutral.source_locator, source_analysis_id=neutral.source_analysis_id,
        source_page_result_id=neutral.source_page_result_id, source_contract_version=neutral.source_contract_version,
        payload={"exact_text": neutral.text})
    assert artifact.source_artifact_key == neutral.source_artifact_key
    assert artifact.source_method == "NATIVE" and artifact.payload["exact_text"] == neutral.text
    assert artifact.source_analysis_id == "analysis-1" and artifact.source_page_result_id == "result-1"
    assert neutral.generation_id == "hash-1" and neutral.page.document_version == "revision-2"

def test_existing_structural_contract_reused():
    candidate = structural_candidate_from_native_text(page_number=1, native_text="PARTIDA 1 servicio")
    neutral = normalize_perception_evidence(source_method=candidate.source_method,
        page=PageIdentity(document_id="document", document_page_id="page", page_number=1),
        capability=Capability.STRUCTURE, source_artifact_key="native:page", generation_id="hash",
        text="PARTIDA 1 servicio", structural_state=candidate.page_state,
        source_contract_version=candidate.page_state.provenance.source_contract_version)
    assert neutral.structural_state == candidate.page_state
    assert neutral.structural_state.provenance.source_method == "NATIVE_TEXT"
    assert PerceptionEvidence.model_validate_json(neutral.model_dump_json()) == neutral
