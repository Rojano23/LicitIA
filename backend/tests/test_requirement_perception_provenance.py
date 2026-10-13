"""Synthetic RP tests using real PostgreSQL JSONB; no provider execution."""
import hashlib
from copy import deepcopy
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.database import SessionLocal
from app.document_intelligence import Capability, PageIdentity, PerceptionEvidence, Quality, SourceMethod, route_capability
from app.models import CompanyEvidence, DocumentPage, NormalizedContent, RequirementCandidate, RequirementCandidateEvidence, Tender, TenderDocument
from app.requirement_extraction import analyze_tender_requirements
from app.requirement_perception_provenance import provenance_from_routing, read_provenance, serialize_provenance, write_provenance

TEXT = "El licitante debera presentar identificacion oficial vigente."

@pytest.fixture
def logical():
    with SessionLocal() as db:
        tender = Tender(title="RP synthetic", institution_profile="General")
        db.add(tender)
        db.flush()
        doc = TenderDocument(tender_id=tender.id, original_filename="synthetic.pdf", stored_relative_path="not-read.pdf",
            mime_type="application/pdf", file_size_bytes=0, sha256=hashlib.sha256(uuid4().bytes).hexdigest())
        db.add(doc)
        db.flush()
        page = DocumentPage(document_id=doc.id, page_number=1, text=TEXT, char_count=len(TEXT), extraction_method="NATIVE_PDF", status="TEXT_EXTRACTED")
        db.add(page)
        db.flush()
        db.add(NormalizedContent(document_page_id=page.id, source_type="NATIVE_PDF", source_scope="NATIVE_PAGE",
            normalized_text=TEXT, char_count=len(TEXT), content_sha256=hashlib.sha256(TEXT.encode()).hexdigest()))
        db.flush()
        analyze_tender_requirements(db, tender.id)
        candidate = db.scalar(select(RequirementCandidate).where(RequirementCandidate.tender_id == tender.id))
        assert candidate is not None and len(candidate.evidence) == 1
        # This persistence suite exercises an explicitly legacy NULL row. R.2
        # now writes provenance in discovery; production wiring has its own tests.
        candidate.evidence[0].perception_provenance = None
        db.flush()
        identity = PageIdentity(tender_id=tender.id, document_id=doc.id, document_page_id=page.id, page_number=1, document_version="1")
        yield db, candidate.evidence[0], identity
        db.rollback()

def source(page, method="VISION", suffix="A", lineage="ACTIVE", text=TEXT):
    return PerceptionEvidence(page=page, source_method=SourceMethod(method), capability=Capability.TRANSCRIPTION,
        quality=Quality.RELIABLE, source_artifact_key=f"{method}:{suffix}", generation_id=f"generation-{suffix}",
        source_analysis_id=f"analysis-{suffix}", source_page_result_id=f"result-{suffix}", lineage=lineage,
        source_locator="page:1|block:1", source_contract_version="synthetic-v1", text=text,
        confidence=90.0, confidence_scale="percent", provider_metadata=(("model", "QWEN"), ("provider", "OLLAMA")))

def routing(page, *sources):
    return route_capability(page=page, capability=Capability.TRANSCRIPTION, evidence=sources)

def roundtrip(logical, result):
    db, row, _ = logical
    expected = write_provenance(row, result)
    row_id = row.id
    db.flush()
    db.expire_all()
    actual = read_provenance(db.get(RequirementCandidateEvidence, row_id).perception_provenance)
    assert actual == expected
    return actual

def test_RP01_legacy_sql_null(logical):
    db, row, _ = logical
    db.expire(row)
    assert row.perception_provenance is None and read_provenance(row.perception_provenance) is None

@pytest.mark.parametrize("method", [pytest.param("NATIVE", id="RP02"), pytest.param("OCR", id="RP03"), pytest.param("VISION", id="RP04")])
def test_source_jsonb_roundtrip(logical, method):
    page = logical[2]
    assert roundtrip(logical, routing(page, source(page, method))).selected.source_method.value == method

def test_RP05_lineage_identities(logical):
    page = logical[2]
    selected = roundtrip(logical, routing(page, source(page))).selected
    assert (selected.source_artifact_key, selected.source_analysis_id, selected.generation_id, selected.source_page_result_id) == ("VISION:A", "analysis-A", "generation-A", "result-A")
    assert selected.page == page and selected.source_locator == "page:1|block:1"

def test_RP06_active(logical):
    page = logical[2]
    assert roundtrip(logical, routing(page, source(page))).selected.lineage == "ACTIVE"

def test_RP07_deselected_history(logical):
    page = logical[2]
    actual = roundtrip(logical, routing(page, source(page, lineage="DESELECTED")))
    assert actual.selected is None and actual.candidates[0].lineage == "DESELECTED"

def test_RP08_distinct_vision_same_fragment(logical):
    _, row, page = logical
    actual = roundtrip(logical, routing(page, source(page), source(page, suffix="B")))
    assert {c.source_artifact_key for c in actual.candidates} == {"VISION:A", "VISION:B"}
    assert {c.generation_id for c in actual.candidates} == {"generation-A", "generation-B"}
    assert len(row.candidate.evidence) == 1

def test_RP09_native_vision_coexist(logical):
    page = logical[2]
    actual = roundtrip(logical, routing(page, source(page, "NATIVE"), source(page), source(page, suffix="B", lineage="DESELECTED")))
    assert actual.selected.source_method == SourceMethod.NATIVE and len(actual.candidates) == 3

def test_RP10_canonical_order(logical):
    page = logical[2]
    a, b = source(page), source(page, suffix="B")
    first = serialize_provenance(provenance_from_routing(routing(page, a, b)))
    reversed_payload = deepcopy(first)
    reversed_payload["candidates"].reverse()
    for c in reversed_payload["candidates"]:
        c["provider_metadata"].reverse()
    reversed_payload["selected"]["provider_metadata"].reverse()
    assert serialize_provenance(read_provenance(reversed_payload)) == first
    assert first == serialize_provenance(provenance_from_routing(routing(page, b, a)))

def test_RP11_review_status(logical):
    page = logical[2]
    review = source(page).model_copy(update={"quality": Quality.REVIEW_REQUIRED})
    actual = roundtrip(logical, routing(page, review))
    assert actual.routing_status == "REVIEW_REQUIRED" and actual.selected is None
    assert actual.diagnostics == ("NO_RELIABLE_CURRENT_EVIDENCE",)

def test_RP12_conflicts(logical):
    page = logical[2]
    actual = roundtrip(logical, routing(page, source(page), source(page, suffix="B", text="Otra lectura contractual.")))
    assert actual.routing_status == "REVIEW_REQUIRED" and actual.selected is None
    assert actual.conflicts[0].kind == "TEXTUAL" and len(actual.conflicts[0].alternatives) == 2
    assert {c.excerpt for c in actual.candidates} == {TEXT, "Otra lectura contractual."}

def test_RP13_metadata_not_channel(logical):
    page = logical[2]
    selected = roundtrip(logical, routing(page, source(page))).selected
    assert selected.source_method == SourceMethod.VISION
    assert dict(selected.provider_metadata) == {"model": "QWEN", "provider": "OLLAMA"}

def test_RP14_unknown_invalid_contract(logical):
    page = logical[2]
    valid = serialize_provenance(provenance_from_routing(routing(page, source(page))))
    for patch in ({"unknown": True}, {"schema_version": "2"}, {"routing_status": "TRUSTED"}):
        with pytest.raises(ValidationError):
            read_provenance({**valid, **patch})
    bad = deepcopy(valid)
    bad["candidates"][0]["source_method"] = "QWEN"
    with pytest.raises(ValidationError):
        read_provenance(bad)

def test_RP15_null_not_empty():
    assert read_provenance(None) is None
    for bad in ({}, [], "null", {"schema_version": "1"}):
        with pytest.raises(ValidationError):
            read_provenance(bad)

def test_RP16_input_not_mutated(logical):
    page = logical[2]
    result = routing(page, source(page))
    before = result.model_dump_json()
    roundtrip(logical, result)
    assert result.model_dump_json() == before

def test_RP17_dedup_unchanged(logical):
    db, row, page = logical
    key = (row.source_document_id, row.source_page, row.excerpt_sha256)
    roundtrip(logical, routing(page, source(page), source(page, suffix="B")))
    analyze_tender_requirements(db, page.tender_id)
    rows = db.scalars(select(RequirementCandidateEvidence).where(RequirementCandidateEvidence.candidate_id == row.candidate_id)).all()
    assert len(rows) == 1 and rows[0].id == row.id
    assert (rows[0].source_document_id, rows[0].source_page, rows[0].excerpt_sha256) == key
    sources = read_provenance(rows[0].perception_provenance).candidates
    assert len(sources) == 3  # Two explicit history observations plus current discovery.
    assert sum(source.lineage == "DESELECTED" for source in sources) == 2

def test_RP18_idempotence(logical):
    db, row, page = logical
    result = routing(page, source(page))
    first, second = roundtrip(logical, result), roundtrip(logical, result)
    analyze_tender_requirements(db, page.tender_id)
    assert first == second
    refreshed = read_provenance(row.perception_provenance)
    analyze_tender_requirements(db, page.tender_id)
    assert read_provenance(row.perception_provenance) == refreshed
    assert any(source.source_artifact_key == "VISION:A" and source.lineage == "DESELECTED" for source in refreshed.candidates)
    assert len(row.candidate.evidence) == 1

def test_RP19_no_domain_decision(logical):
    _, row, page = logical
    row.candidate.review_status = "CONFIRMED"
    before = (row.candidate.semantic_key, row.candidate.requirement_text, row.candidate.review_status, row.source_excerpt, row.excerpt_sha256, row.normalized_content_id)
    roundtrip(logical, routing(page, source(page), source(page, suffix="B", text="Conflicto.")))
    assert before == (row.candidate.semantic_key, row.candidate.requirement_text, row.candidate.review_status, row.source_excerpt, row.excerpt_sha256, row.normalized_content_id)

def test_RP20_company_schema_unchanged():
    assert "perception_provenance" not in CompanyEvidence.__table__.columns
    assert "source_method" not in CompanyEvidence.__table__.columns

def test_hash_tampering_cross_page_rejected(logical):
    _, row, page = logical
    payload = serialize_provenance(provenance_from_routing(routing(page, source(page))))
    payload["candidates"][0]["excerpt_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        read_provenance(payload)
    other = page.model_copy(update={"document_page_id": "another-page"})
    with pytest.raises(ValueError):
        write_provenance(row, routing(other, source(other)))
    assert row.perception_provenance is None

def test_reselection_retains_prior_observations_without_inferred_lineage(logical):
    _, row, page = logical
    roundtrip(logical, routing(page, source(page)))
    with pytest.raises(ValueError, match="retain prior"):
        write_provenance(row, routing(page, source(page, suffix="B")))
    actual = roundtrip(logical, routing(page, source(page, lineage="DESELECTED"), source(page, suffix="B")))
    assert actual.selected.source_artifact_key == "VISION:B"
    assert {c.source_artifact_key: c.lineage for c in actual.candidates} == {"VISION:A": "DESELECTED", "VISION:B": "ACTIVE"}
    with pytest.raises(ValueError, match="retain prior"):
        write_provenance(row, routing(page, source(page, suffix="B")))

def test_malformed_jsonb_read_and_write_fail_closed(logical):
    db, row, page = logical
    row.perception_provenance = {"schema_version": "bad"}
    db.flush()
    db.expire(row)
    with pytest.raises(ValidationError):
        read_provenance(row.perception_provenance)
    with pytest.raises(ValidationError):
        write_provenance(row, routing(page, source(page)))
    assert row.perception_provenance == {"schema_version": "bad"}
