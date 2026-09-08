"""
Synthetic deterministic tests for Semantic Golden Set evaluation.

These tests use SYNTHETIC Golden cases and predictions. No real model inference.
No network access. All behavior is deterministic and traceable.

All real Golden cases with real tender data must start with:
- human_label_status = PENDING
- expected_obligations = []

Real labeling happens in a later manual step after human review.
"""

import hashlib
import pytest

from app.scope_semantic_discovery import (
    SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
    DiscoveredScopeObligation,
    ScopeSemanticDiscoveryResult,
)
from app.scope_semantic_golden import (
    GOLDEN_EVAL_STATUS_FAIL,
    GOLDEN_EVAL_STATUS_INVALID,
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_EVAL_STATUS_REVIEW_REQUIRED,
    GOLDEN_EVAL_STATUS_UNLABELED,
    GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS,
    GOLDEN_EVALUATION_MODE_REVIEW_ONLY,
    GOLDEN_EVALUATION_MODE_STRICT,
    GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
    GOLDEN_HUMAN_LABEL_STATUS_PENDING,
    SEMANTIC_GOLDEN_VERSION,
    ExpectedObligation,
    SemanticGoldenCase,
    SemanticGoldenEvaluator,
    SemanticGoldenValidator,
)


def test_valid_pending_case_evaluates_to_unlabeled():
    """Test 1: Valid PENDING case → UNLABELED."""
    source_text = "The contractor shall provide supervision of all installation work."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    case = SemanticGoldenCase(
        case_id="test_case_001",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_PENDING,
    )

    # Validate
    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Create dummy provider result
    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=0,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
        candidates=(),
    )

    # Evaluate
    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.case_id == "test_case_001"
    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_UNLABELED


def test_approved_strict_exact_match_passes():
    """Test 2: APPROVED STRICT exact match → PASS."""
    source_text = "The contractor must provide three (3) portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="three (3) portable generators",
    )

    case = SemanticGoldenCase(
        case_id="test_case_002",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of portable generators",
        evidence_excerpt="three (3) portable generators",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1
    assert evaluation.recall == 1.0
    assert evaluation.precision == 1.0
    assert len(evaluation.unmatched_expected_obligation_indices) == 0
    assert len(evaluation.unexpected_prediction_indices) == 0


def test_expected_obligation_missing_fails():
    """Test 3: Expected obligation missing → FAIL."""
    source_text = "The contractor must provide three (3) portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="three (3) portable generators",
    )

    case = SemanticGoldenCase(
        case_id="test_case_003",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Provider returns nothing
    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=0,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
        candidates=(),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL
    assert evaluation.matched_count == 0
    assert evaluation.recall == 0.0
    assert 0 in evaluation.unmatched_expected_obligation_indices


def test_unexpected_model_obligation_fails():
    """Test 4: Unexpected model obligation → FAIL."""
    source_text = "The contractor must provide three (3) portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    case = SemanticGoldenCase(
        case_id="test_case_004",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Provider returns something unexpected
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of portable generators",
        evidence_excerpt="three (3) portable generators",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL
    assert evaluation.expected_count == 0
    assert evaluation.predicted_count == 1
    assert 0 in evaluation.unexpected_prediction_indices


def test_no_obligations_correct_passes():
    """Test 5: NO_OBLIGATIONS correct → PASS."""
    source_text = "Administrative and qualification criteria for bidders."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    case = SemanticGoldenCase(
        case_id="test_case_005",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=0,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
        candidates=(),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 0


def test_no_obligations_false_positive_fails():
    """Test 6: NO_OBLIGATIONS false positive → FAIL."""
    source_text = "Administrative and qualification criteria. Must provide generator."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    case = SemanticGoldenCase(
        case_id="test_case_006",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of generator",
        evidence_excerpt="Must provide generator",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_invalid_golden_evidence_not_grounded_fails():
    """Test 7: Invalid Golden evidence not grounded → validation failure."""
    source_text = "The contractor must provide equipment."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="three (3) portable generators",  # NOT IN source_text
    )

    case = SemanticGoldenCase(
        case_id="test_case_007",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) > 0
    assert any("not grounded in source text" in e for e in errors)


def test_invalid_domain_rejected():
    """Test 8: Invalid domain rejected."""
    source_text = "The contractor must provide equipment."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="INVALID_DOMAIN",  # Not in SCOPE_DETAIL_ALLOWED_DOMAINS
        evidence_excerpt="equipment",
    )

    case = SemanticGoldenCase(
        case_id="test_case_008",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) > 0
    assert any("domain" in e.lower() and "not in allowed" in e.lower() for e in errors)


def test_sha256_mismatch_rejected():
    """Test 9: SHA256 mismatch rejected."""
    source_text = "The contractor must provide equipment."
    wrong_sha256 = "0" * 64  # Obviously wrong

    case = SemanticGoldenCase(
        case_id="test_case_009",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=wrong_sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_PENDING,
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) > 0
    assert any("SHA256 mismatch" in e for e in errors)


def test_broader_predicted_excerpt_matches_narrower_expected():
    """Test 10: Broader predicted excerpt can match narrower Golden evidence."""
    source_text = "The contractor must provide supervision and portable generators for the site."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="portable generators",
    )

    case = SemanticGoldenCase(
        case_id="test_case_010",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Predicted is broader
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of supervision and equipment",
        evidence_excerpt="supervision and portable generators for the site",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1


def test_narrower_predicted_excerpt_matches_broader_expected():
    """Test 11: Narrower predicted excerpt can match broader Golden evidence."""
    source_text = "The contractor must provide supervision and portable generators for the site."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="supervision and portable generators for the site",
    )

    case = SemanticGoldenCase(
        case_id="test_case_011",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Predicted is narrower
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of portable generators",
        evidence_excerpt="portable generators",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1


def test_one_predicted_cannot_satisfy_two_expected():
    """Test 12: One predicted candidate cannot satisfy two Golden obligations."""
    source_text = "The contractor must provide supervision and portable generators and fuel for the site."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl_1 = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="portable generators",
    )

    expected_obl_2 = ExpectedObligation(
        golden_obligation_id="obl_002",
        domain="SUPPLY",
        evidence_excerpt="fuel",
    )

    case = SemanticGoldenCase(
        case_id="test_case_012",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl_1, expected_obl_2),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # One broad predicted that contains both obligations
    # But different domains, so should NOT match both
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",  # Only matches domain of first expected
        description="Provision of equipment and supplies",
        evidence_excerpt="portable generators and fuel",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    # Should have 1 matched, 1 unmatched expected (the SUPPLY one)
    assert evaluation.matched_count == 1
    assert 1 in evaluation.unmatched_expected_obligation_indices


def test_cross_domain_mixed_candidate_diagnostic():
    """Test 13: Cross-domain mixed candidate diagnostic."""
    source_text = "Transportation and communication with explosion-proof radios, and portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl_1 = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="LOGISTICS_SITE",
        evidence_excerpt="Transportation and communication",
    )

    expected_obl_2 = ExpectedObligation(
        golden_obligation_id="obl_002",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="explosion-proof radios",
    )

    case = SemanticGoldenCase(
        case_id="test_case_013",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl_1, expected_obl_2),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Predicted combines both into one (known 8B limitation)
    predicted_obl = DiscoveredScopeObligation(
        domain="LOGISTICS_SITE",
        description="Site logistics and communication",
        evidence_excerpt="Transportation and communication with explosion-proof radios",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    # Should flag mixed domain
    assert len(evaluation.mixed_domain_candidate_indices) > 0
    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_REVIEW_REQUIRED


def test_review_only_always_requires_review():
    """Test 14: REVIEW_ONLY → REVIEW_REQUIRED."""
    source_text = "The contractor must provide equipment."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    case = SemanticGoldenCase(
        case_id="test_case_014",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_REVIEW_ONLY,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=0,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
        candidates=(),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_REVIEW_REQUIRED


def test_provider_invalid_output_fails():
    """Test 15: Provider INVALID_OUTPUT → Golden FAIL."""
    source_text = "The contractor must provide equipment."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="equipment",
    )

    case = SemanticGoldenCase(
        case_id="test_case_015",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=0,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
        candidates=(),
        errors=("Model returned malformed JSON",),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_descriptions_not_exact_match_scoring():
    """Test 16: Descriptions are not exact-match scoring keys."""
    source_text = "The contractor must provide portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="portable generators",
    )

    case = SemanticGoldenCase(
        case_id="test_case_016",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Different description, same evidence and domain
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Supply of backup power generation equipment",  # Different wording
        evidence_excerpt="portable generators",
        review_required=False,
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    # Should still match because description is not a scoring key
    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1


def test_source_method_independence():
    """Test 17: Source method independence (NATIVE, OCR, VISION all valid)."""
    source_text = "The contractor must provide equipment."

    for source_method in ["NATIVE", "OCR", "VISION"]:
        sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

        case = SemanticGoldenCase(
            case_id=f"test_case_017_{source_method}",
            golden_set_version=SEMANTIC_GOLDEN_VERSION,
            tender_id="tender_001",
            source_document_id="doc_001",
            document_page_id="page_001",
            page_number=1,
            source_method=source_method,
            source_artifact_key="artifact_001",
            source_locator="page_1_para_1",
            source_text=source_text,
            source_text_sha256=sha256,
            evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
            human_label_status=GOLDEN_HUMAN_LABEL_STATUS_PENDING,
        )

        errors = SemanticGoldenValidator.validate(case)
        assert len(errors) == 0


def test_quantity_unit_remain_diagnostic_raw():
    """Test 18: Quantity/unit remain diagnostic raw values only."""
    source_text = "Provide 3 portable generators."
    sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    expected_obl = ExpectedObligation(
        golden_obligation_id="obl_001",
        domain="TOOLS_EQUIPMENT",
        evidence_excerpt="3 portable generators",
        quantity_raw="3",
        unit_raw="units",
    )

    case = SemanticGoldenCase(
        case_id="test_case_018",
        golden_set_version=SEMANTIC_GOLDEN_VERSION,
        tender_id="tender_001",
        source_document_id="doc_001",
        document_page_id="page_001",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="artifact_001",
        source_locator="page_1_para_1",
        source_text=source_text,
        source_text_sha256=sha256,
        evaluation_mode=GOLDEN_EVALUATION_MODE_STRICT,
        human_label_status=GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
        expected_obligations=(expected_obl,),
    )

    errors = SemanticGoldenValidator.validate(case)
    assert len(errors) == 0

    # Predicted with different quantity_raw (unit normalization is not scoring)
    predicted_obl = DiscoveredScopeObligation(
        domain="TOOLS_EQUIPMENT",
        description="Provision of generators",
        evidence_excerpt="3 portable generators",
        review_required=False,
        quantity_raw="tres",  # Different form
        unit_raw="pieces",  # Different unit
    )

    provider_result = ScopeSemanticDiscoveryResult(
        provider_name="test_provider",
        provider_version="1.0",
        contract_version="test",
        candidate_count=1,
        review_required_count=0,
        status=SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
        candidates=(predicted_obl,),
    )

    evaluation = SemanticGoldenEvaluator.evaluate(case, provider_result)

    # Should still match (quantity/unit are not scoring keys in this MVP)
    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1
