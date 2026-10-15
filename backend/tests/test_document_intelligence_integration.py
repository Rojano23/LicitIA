"""R.2 synthetic production integration; no corpus/files/providers executed."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import timedelta
import hashlib
from uuid import uuid4
import pytest
from sqlalchemy import select, delete
from app.database import SessionLocal
from app.document_intelligence import Capability, CriticalIdentifier, Quality, advance_continuity, route_capability
from app.document_intelligence_sources import load_document_transcriptions, load_page_structure
from app.models import Tender, TenderDocument, DocumentPage, NormalizedContent, PageOcrResult, DocumentVisionAnalysis, DocumentVisionPageResult, DocumentClassification, RequirementCandidate, Requirement, TenderScopeDetail
from app.requirement_extraction import analyze_tender_requirements
from app.requirement_normalization import normalize_tender_requirements
from app.requirement_semantics import analyze_tender_requirement_semantics
from app.requirement_perception_provenance import read_provenance
from app.scope_detail_materializer import materialize_document_scope_details
from app.scope_semantic_discovery import DiscoveredScopeObligation
from app.ollama_vision import VISION_STRUCTURE_SCOPE_PROMPT_VERSION
from app import document_structure_orchestrator as orchestrator

TEXT = "El licitante debera presentar certificado de calidad para el suministro de equipos."

@pytest.fixture
def corpus(monkeypatch):
    db = SessionLocal()
    tender = Tender(title="R2 synthetic", institution_profile="General")
    db.add(tender); db.flush()
    doc = TenderDocument(tender_id=tender.id, original_filename="neutral.pdf", stored_relative_path="not-read.pdf",
        mime_type="application/pdf", file_size_bytes=0, sha256=hashlib.sha256(uuid4().bytes).hexdigest())
    db.add(doc); db.flush()
    page = add_page(db, doc)
    # Exercise the production orchestrator's isolated-session call path without
    # publishing fixtures; its commit is cleaned using the same test database.
    monkeypatch.setattr(orchestrator, "SessionLocal", lambda: nullcontext(db))
    yield db, tender, doc, page
    db.rollback()
    db.execute(delete(Tender).where(Tender.id == tender.id)); db.commit(); db.close()


def add_page(db, doc, number=1):
    page = DocumentPage(document_id=doc.id, page_number=number, text="", char_count=0,
        extraction_method="NATIVE_PDF", status="NO_TEXT")
    db.add(page); db.flush()
    return page


def norm(db, page, method="NATIVE", text=TEXT):
    ocr_id = None
    if method == "OCR":
        row = PageOcrResult(document_page_id=page.id, engine="synthetic", engine_version="fixture-1", text=text,
            status="OCR_TEXT_EXTRACTED", scope="FULL_PAGE")
        db.add(row); db.flush(); ocr_id = row.id
    else:
        page.text = text; page.char_count = len(text); page.status = "TEXT_EXTRACTED"
    n = NormalizedContent(document_page_id=page.id, source_type="NATIVE_PDF" if method == "NATIVE" else "OCR",
        source_scope="NATIVE_PAGE" if method == "NATIVE" else "FULL_PAGE", page_ocr_result_id=ocr_id,
        normalized_text=text, char_count=len(text), content_sha256=hashlib.sha256(text.encode()).hexdigest())
    db.add(n); db.flush(); return n


def vision(db, doc, page, text=TEXT, *, fingerprint=None, structure=None, failed=False):
    payload = deepcopy(structure) if structure else {}
    if text is not None:
        payload["detail_transcription"] = {"task_type": "DETAIL_TRANSCRIPTION", "raw_text": text,
            "parsed_supply_rows": [{"raw_visible_text": text, "description": text, "domain": "SUPPLY", "review_required": True}]}
        if fingerprint:
            payload["detail_transcription"]["task_fingerprint"] = fingerprint
        payload["_detail_runtime"] = {"status": "FAILED" if failed else "COMPLETED", "schema_valid": not failed}
    if structure:
        payload["_vision_runtime"] = {"task_type": "STRUCTURE_SCOPE", "structure_schema_valid": True}
    a = DocumentVisionAnalysis(tender_id=doc.tender_id, document_id=doc.id, status="PARTIAL" if failed else "COMPLETED",
        prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION if structure else "synthetic-detail-001",
        model_name="QWEN", input_fingerprint_sha256=hashlib.sha256(uuid4().bytes).hexdigest())
    db.add(a); db.flush()
    row = DocumentVisionPageResult(analysis_id=a.id, document_page_id=page.id, page_number=page.page_number,
        image_sha256=hashlib.sha256(uuid4().bytes).hexdigest(), status="PARTIAL" if failed else "COMPLETED", structured_json=payload)
    db.add(row); db.flush(); return row


def structure(number=1, key="1", incoming=None):
    return {"page_number": number, "continues_previous_item": incoming is not None,
        "previous_item_number": incoming, "open_item_at_page_end": key,
        "new_items": [] if incoming else [{"item_number": key}],
        "item_segments": [{"item_number": key, "starts_on_this_page": incoming is None,
            "anchor_raw_text": f"PARTIDA {key}", "review_required": False}],
        "_continuity_state_quality": "VALID"}


class GroundedProvider:
    provider_name = "synthetic"
    provider_version = "1"
    contract_version = "fixture-1"
    def supports(self, fragment): return True
    def discover(self, fragment):
        return [DiscoveredScopeObligation(domain="SUPPLY", description=fragment.source_text,
            evidence_excerpt=fragment.source_text, review_required=True, applicability_hint="TENDER_WIDE")]


def seed(corpus, method, text=TEXT):
    db, _, doc, page = corpus
    return vision(db, doc, page, text) if method == "VISION" else norm(db, page, method, text)


def requirements(corpus):
    db, tender, _, _ = corpus
    analyze_tender_requirements(db, tender.id)
    return db.scalars(select(RequirementCandidate).where(RequirementCandidate.tender_id == tender.id)).all()


def requested(corpus):
    db, tender, _, _ = corpus
    requirements(corpus); normalize_tender_requirements(db, tender.id)
    return analyze_tender_requirement_semantics(db, tender.id)


def scopes(corpus):
    db, tender, doc, _ = corpus
    result = materialize_document_scope_details(db, tender_id=tender.id, document_id=doc.id,
        semantic_providers=(GroundedProvider(),))
    rows = db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.tender_id == tender.id)).all()
    return result, rows


def routed(corpus):
    db, _, doc, page = corpus
    return load_document_transcriptions(db, doc)[page.id]


def orchestrated(corpus):
    db, tender, doc, _ = corpus
    return orchestrator.orchestrate_document_structure_available_only(db, tender_id=tender.id, document_id=doc.id)


@pytest.mark.parametrize("method", [pytest.param("NATIVE", id="RDI01"), pytest.param("OCR", id="RDI02"), pytest.param("VISION", id="RDI03")])
def test_requirement_channels(corpus, method):
    seed(corpus, method)
    rows = requirements(corpus)
    assert len(rows) == 1
    provenance = read_provenance(rows[0].evidence[0].perception_provenance)
    assert {s.source_method.value for s in provenance.candidates} == {method}
    assert rows[0].review_status == "SUGGESTED"


def test_RDI04_full_provenance(corpus):
    seed(corpus, "NATIVE"); v = seed(corpus, "VISION")
    row = requirements(corpus)[0]
    provenance = read_provenance(row.evidence[0].perception_provenance)
    assert len(provenance.candidates) == 2 and len(row.evidence) == 1
    source = next(s for s in provenance.candidates if s.source_method == "VISION")
    assert source.source_analysis_id == v.analysis_id and source.source_page_result_id == v.id
    assert source.page.document_version == "1" and source.excerpt == TEXT and source.generation_id


def test_RDI05_review_not_trusted(corpus):
    seed(corpus, "VISION"); requested(corpus)
    row = corpus[0].scalar(select(Requirement).where(Requirement.tender_id == corpus[1].id))
    assert row.normalization_status == "REVIEW_REQUIRED"
    assert row.primary_candidate.review_status == "SUGGESTED"


def reselect(corpus):
    db, _, doc, page = corpus
    old = vision(db, doc, page, fingerprint="same-detail")
    old.analysis.created_at -= timedelta(days=1)
    new = vision(db, doc, page, text="texto sin obligaciones", fingerprint="same-detail")
    db.flush(); return old, new


def test_RDI06_deselected_excluded_audited(corpus):
    db, _, doc, page = corpus
    old = vision(db, doc, page, fingerprint="same-detail")
    requirements(corpus)
    old.analysis.created_at -= timedelta(days=1)
    vision(db, doc, page, text="texto sin obligaciones", fingerprint="same-detail"); db.flush()
    rows = requirements(corpus)
    assert len(rows) == 1  # Historical candidate is retained, not active.
    assert any(s.lineage == "DESELECTED" for s in read_provenance(rows[0].evidence[0].perception_provenance).candidates)
    normalize_tender_requirements(db, doc.tender_id)
    assert not db.scalars(select(Requirement).where(Requirement.tender_id == doc.tender_id)).all()


def test_RDI07_same_fragment_scope(corpus):
    seed(corpus, "NATIVE")
    assert requirements(corpus) and scopes(corpus)[1]


def test_RDI08_idempotence(corpus):
    seed(corpus, "NATIVE")
    first = requirements(corpus)[0]; evidence_id = first.evidence[0].id; snapshot = deepcopy(first.evidence[0].perception_provenance)
    second = requirements(corpus)[0]
    assert second.id == first.id and second.evidence[0].id == evidence_id and second.evidence[0].perception_provenance == snapshot


@pytest.mark.parametrize("method", [pytest.param("NATIVE", id="EDI01"), pytest.param("OCR", id="EDI02"), pytest.param("VISION", id="EDI03")])
def test_requested_channels(corpus, method):
    seed(corpus, method); payload = requested(corpus)
    rows = payload["requirements"]
    assert rows and rows[0]["expected_evidence"] and rows[0]["interpretation_status"] == "REVIEW_REQUIRED"
    assert rows[0]["expected_evidence"][0]["perception_provenance"][0].candidates[0].source_method.value == method


def test_EDI04_provenance(corpus):
    v = seed(corpus, "VISION"); row = requested(corpus)["requirements"][0]
    assert row["primary_source"]["perception_provenance"][0].candidates[0].source_page_result_id == v.id
    assert row["expected_evidence"][0]["perception_provenance"][0].page.document_page_id == corpus[3].id


def test_EDI05_conflict_fail_closed(corpus):
    seed(corpus, "NATIVE"); seed(corpus, "OCR", TEXT.replace("certificado de calidad", "certificado de seguridad"))
    payload = requested(corpus)
    assert all(r["interpretation_status"] == "REVIEW_REQUIRED" for r in payload["requirements"])
    assert all(r["primary_source"]["perception_provenance"][0].conflicts for r in payload["requirements"])


def test_EDI06_deselected(corpus):
    reselect(corpus)
    assert requested(corpus)["requirements"] == []


def classify(corpus):
    db, _, doc, _ = corpus
    db.add(DocumentClassification(document_id=doc.id, human_type="TECHNICAL_SPEC", suggested_type="TECHNICAL_SPEC",
        suggested_score=90, classification_status="CONFIRMED")); db.flush()


def test_EDI07_classification(corpus):
    seed(corpus, "NATIVE"); classify(corpus)
    assert requested(corpus)["requirements"][0]["expected_evidence"]


def test_EDI08_idempotence(corpus):
    seed(corpus, "VISION")
    a = requested(corpus)["requirements"][0]; b = requested(corpus)["requirements"][0]
    assert a["requirement_id"] == b["requirement_id"]
    assert [r["id"] for r in a["expected_evidence"]] == [r["id"] for r in b["expected_evidence"]]


@pytest.mark.parametrize("method", [pytest.param("NATIVE", id="SDI01"), pytest.param("OCR", id="SDI02"), pytest.param("VISION", id="SDI03")])
def test_scope_channels(corpus, method):
    seed(corpus, method); _, rows = scopes(corpus)
    assert len(rows) == 1 and rows[0].source_method == method and rows[0].review_required


@pytest.mark.parametrize("method", [pytest.param("NATIVE", id="SDI04"), pytest.param("OCR", id="SDI05")])
def test_scope_independent_providers(corpus, method):
    seed(corpus, method); db, _, doc, page = corpus
    vision(db, doc, page, text=None, structure=structure())
    result = orchestrated(corpus)
    assert result.page_results[0].selected_source_method == "VISION" and result.page_results[0].status == "RESOLVED"
    _, rows = scopes(corpus)
    assert rows and rows[0].source_method == method


def test_SDI06_structure_survives_detail_failure(corpus):
    db, _, doc, page = corpus
    vision(db, doc, page, structure=structure(), failed=True)
    assert orchestrated(corpus).page_results[0].status == "RESOLVED"
    assert not scopes(corpus)[1]


def test_SDI07_text_survives_structure_absence(corpus):
    seed(corpus, "NATIVE")
    assert orchestrated(corpus).page_results[0].status != "RESOLVED"
    assert scopes(corpus)[1] and routed(corpus).candidates[0].text == TEXT


def test_SDI08_transition_continuity(corpus):
    db, _, doc, p1 = corpus
    norm(db, p1, text="PARTIDA 1 suministro")
    p2 = add_page(db, doc, 2); vision(db, doc, p2, text=None, structure=structure(2, incoming="1"))
    p3 = add_page(db, doc, 3); norm(db, p3, "OCR", "PARTIDA 1 suministro")
    result = orchestrated(corpus)
    assert [r.status for r in result.page_results] == ["RESOLVED"] * 3
    assert [r.selected_source_method for r in result.page_results] == ["NATIVE_TEXT", "VISION", "OCR"]


def test_SDI09_failure_no_stale_carry(corpus):
    db, _, doc, p1 = corpus
    norm(db, p1, text="PARTIDA 1 suministro")
    p2 = add_page(db, doc, 2)
    p3 = add_page(db, doc, 3); vision(db, doc, p3, text=None, structure=structure(3, incoming="1"))
    result = orchestrated(corpus)
    assert result.page_results[1].status != "RESOLVED" and result.page_results[2].status == "REVIEW_REQUIRED"
    assert result.page_results[2].reason == "UNPROVEN_CONTINUITY_BOUNDARY"


def test_SDI10_structural_conflict(corpus):
    db, _, doc, page = corpus
    norm(db, page, text="PARTIDA 1 suministro")
    vision(db, doc, page, text=None, structure=structure(key="2"))
    result = orchestrated(corpus)
    assert result.page_results[0].status == "REVIEW_REQUIRED" and result.page_results[0].selected_source_method is None


def test_SDI11_identifier_signal(corpus, monkeypatch):
    seed(corpus, "NATIVE", "PARTIDA 1 suministro"); seed(corpus, "OCR", "PARTIDA 2 suministro")
    original = orchestrator.load_page_structure
    def declared_bindings(db, doc, page):
        result = original(db, doc, page)
        # Adapter-declared grounded bindings are an R.1 input. R.2 preserves
        # their signal in the actual orchestrator; discovery/hardening is R.3.
        observations = [e.model_copy(update={"critical_identifiers": (CriticalIdentifier(binding_key="row:0:item",
            value="1" if e.source_method == "NATIVE" else "2", excerpt=e.text),)}) for e in result.candidates]
        return route_capability(page=result.page, capability=Capability.STRUCTURE, evidence=observations)
    monkeypatch.setattr(orchestrator, "load_page_structure", declared_bindings)
    result = orchestrated(corpus)
    assert result.page_results[0].status == "REVIEW_REQUIRED"
    assert result.page_results[0].reason == "CRITICAL_IDENTIFIER_CONFLICT"


def test_SDI12_deselected_scope(corpus):
    old, new = reselect(corpus)
    _, rows = scopes(corpus)
    assert not any(row.source_page_result_id == old.id for row in rows)


def test_SDI13_detail_provenance(corpus):
    v = seed(corpus, "VISION"); _, rows = scopes(corpus)
    assert rows[0].source_analysis_id == v.analysis_id and rows[0].source_page_result_id == v.id
    assert rows[0].source_excerpt == TEXT and rows[0].document_page_id == corpus[3].id and rows[0].source_locator


def test_SDI14_idempotence(corpus):
    seed(corpus, "NATIVE"); _, a = scopes(corpus)
    snapshot = [(r.source_artifact_key, r.description, r.source_excerpt, r.review_required) for r in a]
    _, b = scopes(corpus)
    assert snapshot == [(r.source_artifact_key, r.description, r.source_excerpt, r.review_required) for r in b] and len(b) == 1


def test_SDI15_multi_domain(corpus):
    seed(corpus, "OCR")
    candidate = requirements(corpus)[0]; _, details = scopes(corpus)
    assert details[0].source_excerpt == candidate.source_excerpt == TEXT


def test_XDI01_independent_domains(corpus):
    seed(corpus, "NATIVE")
    candidate = requirements(corpus)[0]; _, details = scopes(corpus)
    assert candidate.review_status == "SUGGESTED" and details[0].domain == "SUPPLY"
    assert candidate.id != details[0].id


def test_XDI02_capability_independence(corpus):
    seed(corpus, "OCR"); db, _, doc, page = corpus
    vision(db, doc, page, text=None, structure=structure())
    assert {e.source_method.value for e in routed(corpus).candidates if e.text} == {"OCR"}
    assert load_page_structure(db, doc, page).selected.source_method == "VISION"


def test_XDI03_whole_corpus(corpus):
    seed(corpus, "NATIVE"); classify(corpus)
    assert requirements(corpus) and requested(corpus)["requirements"] and scopes(corpus)[1]


def test_XDI04_no_mutation(corpus):
    seed(corpus, "VISION"); before = routed(corpus).model_dump_json()
    requirements(corpus); scopes(corpus)
    assert routed(corpus).model_dump_json() == before


def test_XDI05_metadata_not_truth(corpus):
    seed(corpus, "VISION"); rows = requirements(corpus)
    source = read_provenance(rows[0].evidence[0].perception_provenance).candidates[0]
    assert source.source_method.value == "VISION" and ("model", "QWEN") in source.provider_metadata
    assert not source.contractual_authority and rows[0].review_status == "SUGGESTED"


def test_XDI06_no_hidden_fallback(corpus):
    db, _, doc, page = corpus
    vision(db, doc, page, failed=True)
    assert not requirements(corpus) and not scopes(corpus)[1]
    assert routed(corpus).selected is None


def test_legacy_null_cannot_hide_new_di_review(corpus):
    from app.models import RequirementCandidateEvidence
    from app.requirement_di_adapter import candidate_perception
    seed(corpus, "NATIVE")
    row = requirements(corpus)[0]
    legacy = "legacy context"
    row.evidence.append(RequirementCandidateEvidence(source_document_id=corpus[2].id, source_page=1,
        document_page_id=corpus[3].id, source_excerpt=legacy, excerpt_sha256=hashlib.sha256(legacy.encode()).hexdigest()))
    corpus[0].flush()
    assert candidate_perception(row) == (True, True)
    normalize_tender_requirements(corpus[0], corpus[1].id)
    assert corpus[0].scalar(select(Requirement).where(Requirement.tender_id == corpus[1].id)).normalization_status == "REVIEW_REQUIRED"


def test_no_source_is_explicit(corpus):
    assert not requirements(corpus)
    result, rows = scopes(corpus)
    assert not rows and result.status == "NO_EVIDENCE"
    assert routed(corpus).status == "UNAVAILABLE"


def test_cross_page_artifact_rejected(corpus):
    from app.document_intelligence_sources import PersistedPerceptionArtifact, transcription_from_artifact
    db, _, doc, page = corpus
    other = TenderDocument(tender_id=doc.tender_id, original_filename="other.pdf", stored_relative_path="not-read.pdf",
        mime_type="application/pdf", file_size_bytes=0, sha256=hashlib.sha256(uuid4().bytes).hexdigest())
    db.add(other); db.flush()
    artifact = PersistedPerceptionArtifact(tender_id=doc.tender_id, source_document_id=other.id,
        document_page_id=page.id, source_method="NATIVE", source_artifact_key="native-page:" + page.id, payload={"text": TEXT})
    with pytest.raises(ValueError, match="PERCEPTION_ARTIFACT_PAGE_MISMATCH"):
        transcription_from_artifact(db, artifact)


def test_ocr_failure_does_not_delete_native_details(corpus):
    seed(corpus, "NATIVE"); seed(corpus, "OCR")
    result, rows = scopes(corpus)
    # Same exact grounded obligation has one logical parent and both observations.
    assert len(rows) == 1
    assert len(result.logical_evidence[0][1]) == 2
    db, _, _, page = corpus
    ocr = db.scalar(select(PageOcrResult).where(PageOcrResult.document_page_id == page.id))
    ocr.status = "OCR_FAILED"; db.flush()
    _, rows = scopes(corpus)
    assert len(rows) == 1 and rows[0].source_method == "NATIVE" and rows[0].source_excerpt == TEXT


def test_stale_persisted_structure_cannot_restore_detail_ownership(corpus):
    db, tender, doc, page = corpus
    native = norm(db, page, text="PARTIDA 1 suministro")
    orchestrated(corpus)
    v = vision(db, doc, page)
    materialize_document_scope_details(db, tender_id=tender.id, document_id=doc.id)
    before = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_page_result_id == v.id))
    assert before.applicability == "ITEM" and before.scope_segment_id
    native.normalized_text = page.text = "texto sin estructura"
    native.content_sha256 = hashlib.sha256(native.normalized_text.encode()).hexdigest(); db.flush()
    # The prior persisted segment/resolution still exists. Current DI must veto
    # implicit inheritance without needing the orchestrator to run first.
    materialize_document_scope_details(db, tender_id=tender.id, document_id=doc.id)
    after = db.scalar(select(TenderScopeDetail).where(TenderScopeDetail.source_page_result_id == v.id))
    assert after.applicability == "UNRESOLVED" and after.scope_segment_id is None and after.review_required


def test_untyped_vision_text_cannot_become_requirement(corpus):
    v = seed(corpus, "VISION")
    payload = deepcopy(v.structured_json)
    payload["detail_transcription"]["raw_text"] = {"unvalidated_provider_prose": TEXT}
    v.structured_json = payload; corpus[0].flush()
    with pytest.raises(ValueError, match="TRANSCRIPTION_TEXT_MUST_BE_STRING"):
        requirements(corpus)
    assert not corpus[0].scalars(select(RequirementCandidate).where(RequirementCandidate.tender_id == corpus[1].id)).all()
