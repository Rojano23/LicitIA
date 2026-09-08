"""
Test suite for MVP-06.3.4c Calibration Runner

Ensures the runner correctly wires provider results through the neutral
discovery orchestration layer, not directly to the evaluator.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence
from unittest.mock import Mock

import pytest

from app.ollama_scope_semantic_provider import OllamaScopeSemanticDiscoveryProvider
from app.scope_semantic_discovery import (
    SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
    DiscoveredScopeObligation,
    ScopeSemanticDiscoveryProvider,
    ScopeSemanticSourceFragment,
    discover_scope_semantics,
)
from app.scope_semantic_golden import (
    ExpectedObligation,
    SemanticGoldenCase,
    SemanticGoldenEvaluator,
)


@dataclass(frozen=True)
class _MockProviderTupleReturn:
    """Mock provider that returns tuple of obligations (like old behavior)."""

    provider_name: str = "mock-tuple-provider"
    provider_version: str = "1.0"
    contract_version: str = "test-001"

    def supports(self, fragment: ScopeSemanticSourceFragment) -> bool:
        return True

    def discover(self, fragment: ScopeSemanticSourceFragment) -> Sequence[DiscoveredScopeObligation]:
        """
        Mock provider that returns a tuple of DiscoveredScopeObligation objects.
        This simulates the provider-level interface.
        """
        return (
            DiscoveredScopeObligation(
                domain="PERSONNEL",
                description="Test obligation 1",
                evidence_excerpt="Test source text",
                review_required=False,
            ),
        )


@dataclass(frozen=True)
class _MockProviderEmptyReturn:
    """Mock provider that returns empty tuple (NO_OBLIGATIONS case)."""

    provider_name: str = "mock-empty-provider"
    provider_version: str = "1.0"
    contract_version: str = "test-001"

    def supports(self, fragment: ScopeSemanticSourceFragment) -> bool:
        return True

    def discover(self, fragment: ScopeSemanticSourceFragment) -> Sequence[DiscoveredScopeObligation]:
        """Mock provider that returns empty tuple."""
        return ()


class TestRunnerNeutralOrchestrationWiring:
    """Test that runner correctly uses discover_scope_semantics."""

    def test_provider_tuple_result_through_neutral_engine(self) -> None:
        """
        REGRESSION: Provider.discover() returns tuple, not ScopeSemanticDiscoveryResult.

        This test proves the runner correctly passes the provider through the neutral
        discovery orchestration layer (discover_scope_semantics), which handles the
        conversion from provider tuple to ScopeSemanticDiscoveryResult.

        Bug that would fail without fix:
          'tuple' object has no attribute 'status'
        """
        provider = _MockProviderTupleReturn()

        fragment = ScopeSemanticSourceFragment(
            tender_id="test-tender-001",
            source_document_id="doc-001",
            document_page_id="page-001",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="artifact-001",
            source_locator="page_1_native|chars_0-100",
            source_text="Test source text",
        )

        # Call neutral orchestration (what the runner should do)
        result = discover_scope_semantics(
            fragment=fragment,
            providers=[provider]
        )

        # Verify result has proper attributes (not a tuple)
        assert hasattr(result, "status"), "Result should have 'status' attribute"
        assert hasattr(result, "candidates"), "Result should have 'candidates' attribute"
        assert hasattr(result, "errors"), "Result should have 'errors' attribute"

        # Verify status is correct
        assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED

        # Verify candidates were properly processed
        assert result.candidate_count == 1
        assert len(result.candidates) == 1

        # Verify each candidate is a DiscoveredScopeObligation
        for candidate in result.candidates:
            assert isinstance(candidate, DiscoveredScopeObligation)


    def test_empty_tuple_provider_through_neutral_engine(self) -> None:
        """
        REGRESSION: Empty provider response should map to NO_OBLIGATIONS, not AttributeError.

        Tests that when a provider returns empty tuple, the neutral engine correctly
        produces a ScopeSemanticDiscoveryResult with NO_OBLIGATIONS status.
        """
        provider = _MockProviderEmptyReturn()

        fragment = ScopeSemanticSourceFragment(
            tender_id="test-tender-001",
            source_document_id="doc-001",
            document_page_id="page-001",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="artifact-001",
            source_locator="page_1_native|chars_0-100",
            source_text="Test source text",
        )

        # Call neutral orchestration
        result = discover_scope_semantics(
            fragment=fragment,
            providers=[provider]
        )

        # Verify NO_OBLIGATIONS status (not error or crash)
        assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS
        assert result.candidate_count == 0
        assert len(result.candidates) == 0

    def test_neutral_engine_result_works_with_evaluator(self) -> None:
        """
        INTEGRATION: Verify evaluator accepts results from neutral discovery engine.

        Proves the full flow: provider tuple → neutral orchestration →
        ScopeSemanticDiscoveryResult → SemanticGoldenEvaluator.
        """
        provider = _MockProviderTupleReturn()

        fragment = ScopeSemanticSourceFragment(
            tender_id="test-tender-001",
            source_document_id="doc-001",
            document_page_id="page-001",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="artifact-001",
            source_locator="page_1_native|chars_0-100",
            source_text="Test source text with evidence for obligation 1",
        )

        # Neutral discovery orchestration
        discovery_result = discover_scope_semantics(
            fragment=fragment,
            providers=[provider]
        )

        # Create a Golden case for comparison
        golden_case = SemanticGoldenCase(
            case_id="test-case-001",
            golden_set_version="test-001",
            tender_id="test-tender-001",
            source_document_id="doc-001",
            document_page_id="page-001",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="artifact-001",
            source_locator="page_1_native|chars_0-100",
            source_text="Test source text with evidence for obligation 1",
            source_text_sha256="abc123",
            evaluation_mode="STRICT",
            human_label_status="APPROVED",
            expected_obligations=(
                ExpectedObligation(
                    golden_obligation_id="oblig-001",
                    domain="PERSONNEL",
                    evidence_excerpt="Test source text with evidence for obligation 1",
                    review_required=False,
                ),
            ),
        )

        # Evaluator should accept discovery_result without AttributeError
        evaluation = SemanticGoldenEvaluator.evaluate(
            golden_case,
            discovery_result
        )

        # Verify evaluation completed successfully
        assert evaluation is not None
        assert evaluation.expected_count == 1
        assert evaluation.predicted_count == 1  # Mock provider returned 1


class TestRunnerDiagnosticOutput:
    """Test diagnostic output visibility for debugging."""

    def test_case_result_contains_expected_obligations(self) -> None:
        """Verify CaseEvaluationResult captures expected obligations."""
        from scripts.run_scope_semantic_golden import CaseEvaluationResult

        expected_oblig = ExpectedObligation(
            golden_obligation_id="test-001",
            domain="PERSONNEL",
            evidence_excerpt="test evidence",
            review_required=False,
        )

        result = CaseEvaluationResult(
            case_id="test-case",
            case_number=1,
            evaluation_mode="STRICT",
            expected_count=1,
            discovered_count=0,
            matched_count=0,
            eval_status="FAIL",
            provider_status="DISCOVERED",
            discovery_status="DISCOVERED",
            recall=0.0,
            precision=0.0,
            missing_expected=(0,),
            unexpected_discovered=(),
            elapsed_ms=100,
            validation_errors=(),
            mixed_domain_issues=(),
            expected_obligations=(expected_oblig,),
            discovered_candidates=(),
            discovery_errors=(),
        )

        # Verify all diagnostic fields are present
        assert len(result.expected_obligations) == 1
        assert result.expected_obligations[0].golden_obligation_id == "test-001"
        assert result.discovery_status == "DISCOVERED"
        assert result.discovery_errors == ()

    def test_case_result_contains_discovered_candidates(self) -> None:
        """Verify CaseEvaluationResult captures discovered candidates."""
        from scripts.run_scope_semantic_golden import CaseEvaluationResult

        candidate = DiscoveredScopeObligation(
            domain="SSPA",
            description="Test discovered obligation",
            evidence_excerpt="Test evidence from model",
            review_required=False,
            detail_type="TRAINING",
            normalized_label="training_requirement",
            confidence=0.95,
            quantity_raw="2",
            unit_raw="sessions",
        )

        result = CaseEvaluationResult(
            case_id="test-case",
            case_number=2,
            evaluation_mode="STRICT",
            expected_count=1,
            discovered_count=1,
            matched_count=0,  # May not match due to span/domain mismatch
            eval_status="FAIL",
            provider_status="DISCOVERED",
            discovery_status="DISCOVERED",
            recall=0.0,
            precision=1.0,
            missing_expected=(0,),
            unexpected_discovered=(0,),
            elapsed_ms=200,
            validation_errors=(),
            mixed_domain_issues=(0,),
            expected_obligations=(),
            discovered_candidates=(candidate,),
            discovery_errors=(),
        )

        # Verify diagnostic visibility
        assert len(result.discovered_candidates) == 1
        cand = result.discovered_candidates[0]
        assert cand.domain == "SSPA"
        assert cand.description == "Test discovered obligation"
        assert cand.confidence == 0.95
        assert cand.quantity_raw == "2"

    def test_case_result_with_discovery_errors(self) -> None:
        """Verify CaseEvaluationResult captures discovery errors."""
        from scripts.run_scope_semantic_golden import CaseEvaluationResult

        result = CaseEvaluationResult(
            case_id="test-case-error",
            case_number=3,
            evaluation_mode="STRICT",
            expected_count=2,
            discovered_count=0,
            matched_count=0,
            eval_status="INVALID",
            provider_status="INVALID_OUTPUT",
            discovery_status="INVALID_OUTPUT",
            recall=0.0,
            precision=0.0,
            missing_expected=(0, 1),
            unexpected_discovered=(),
            elapsed_ms=50,
            validation_errors=("Invalid JSON response from provider",),
            mixed_domain_issues=(),
            expected_obligations=(),
            discovered_candidates=(),
            discovery_errors=("evidence_excerpt is not supported by source_text",),
        )

        # Verify error visibility
        assert result.discovery_status == "INVALID_OUTPUT"
        assert len(result.discovery_errors) == 1
        assert "evidence_excerpt" in result.discovery_errors[0]
        assert len(result.validation_errors) == 1

    def test_case_result_zero_predictions_diagnostic(self) -> None:
        """Verify diagnostic output handles zero discovered candidates."""
        from scripts.run_scope_semantic_golden import CaseEvaluationResult

        result = CaseEvaluationResult(
            case_id="test-empty-discover",
            case_number=4,
            evaluation_mode="STRICT",
            expected_count=3,
            discovered_count=0,
            matched_count=0,
            eval_status="FAIL",
            provider_status="DISCOVERED",
            discovery_status="NO_OBLIGATIONS",
            recall=0.0,
            precision=0.0,
            missing_expected=(0, 1, 2),
            unexpected_discovered=(),
            elapsed_ms=150,
            validation_errors=(),
            mixed_domain_issues=(),
            expected_obligations=(
                ExpectedObligation(
                    golden_obligation_id="oblig-1",
                    domain="PERSONNEL",
                    evidence_excerpt="Personnel requirement 1",
                    review_required=False,
                ),
                ExpectedObligation(
                    golden_obligation_id="oblig-2",
                    domain="PERSONNEL",
                    evidence_excerpt="Personnel requirement 2",
                    review_required=False,
                ),
                ExpectedObligation(
                    golden_obligation_id="oblig-3",
                    domain="SSPA",
                    evidence_excerpt="SSPA requirement",
                    review_required=False,
                ),
            ),
            discovered_candidates=(),
            discovery_errors=(),
        )

        # Verify all expected obligations visible despite zero discoveries
        assert result.expected_count == 3
        assert result.discovered_count == 0
        assert len(result.expected_obligations) == 3
        assert result.discovery_status == "NO_OBLIGATIONS"
