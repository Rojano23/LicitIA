"""
Provider-neutral Semantic Golden Set contracts and evaluation engine.

Golden truth is HUMAN-OWNED. Model-generated labels must never be imported into
APPROVED REAL cases. All real Golden candidates start with human_label_status=PENDING.

This module provides:
- SemanticGoldenCase: immutable contract for a single Golden evaluation case
- ExpectedObligation: human-approved expected obligation (for APPROVED cases only)
- SemanticGoldenEvaluation: deterministic evaluation result
- SemanticGoldenValidator: validation of Golden data integrity
- SemanticGoldenEvaluator: deterministic matching and scoring
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from app.scope_details import SCOPE_DETAIL_ALLOWED_DOMAINS
from app.scope_semantic_discovery import DiscoveredScopeObligation, ScopeSemanticDiscoveryResult


SEMANTIC_GOLDEN_VERSION = "semantic-scope-golden-2026-09-06-001"

# Allowed human label states
GOLDEN_HUMAN_LABEL_STATUS_PENDING = "PENDING"
GOLDEN_HUMAN_LABEL_STATUS_APPROVED = "APPROVED"

ALLOWED_GOLDEN_HUMAN_LABEL_STATUSES = {
    GOLDEN_HUMAN_LABEL_STATUS_PENDING,
    GOLDEN_HUMAN_LABEL_STATUS_APPROVED,
}

# Evaluation modes
GOLDEN_EVALUATION_MODE_STRICT = "STRICT"
GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS = "NO_OBLIGATIONS"
GOLDEN_EVALUATION_MODE_REVIEW_ONLY = "REVIEW_ONLY"

ALLOWED_GOLDEN_EVALUATION_MODES = {
    GOLDEN_EVALUATION_MODE_STRICT,
    GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS,
    GOLDEN_EVALUATION_MODE_REVIEW_ONLY,
}

# Evaluation statuses
GOLDEN_EVAL_STATUS_PASS = "PASS"
GOLDEN_EVAL_STATUS_FAIL = "FAIL"
GOLDEN_EVAL_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
GOLDEN_EVAL_STATUS_UNLABELED = "UNLABELED"
GOLDEN_EVAL_STATUS_INVALID = "INVALID"

ALLOWED_GOLDEN_EVAL_STATUSES = {
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_EVAL_STATUS_FAIL,
    GOLDEN_EVAL_STATUS_REVIEW_REQUIRED,
    GOLDEN_EVAL_STATUS_UNLABELED,
    GOLDEN_EVAL_STATUS_INVALID,
}

# Source methods
GOLDEN_SOURCE_METHOD_NATIVE = "NATIVE"
GOLDEN_SOURCE_METHOD_OCR = "OCR"
GOLDEN_SOURCE_METHOD_VISION = "VISION"

ALLOWED_GOLDEN_SOURCE_METHODS = {
    GOLDEN_SOURCE_METHOD_NATIVE,
    GOLDEN_SOURCE_METHOD_OCR,
    GOLDEN_SOURCE_METHOD_VISION,
}


@dataclass(frozen=True, slots=True)
class ExpectedObligation:
    """
    Human-approved expected obligation for an APPROVED Golden case.

    These fields exist ONLY in APPROVED cases. PENDING cases have empty
    expected_obligations tuple.
    """

    golden_obligation_id: str
    domain: str
    evidence_excerpt: str
    review_required: bool | None = None
    quantity_raw: str | None = None
    unit_raw: str | None = None
    human_note: str | None = None

    def validate(self) -> tuple[str, ...]:
        """Validate expected obligation. Return tuple of error messages."""
        errors = []

        if not self.golden_obligation_id or not self.golden_obligation_id.strip():
            errors.append("ExpectedObligation: golden_obligation_id is empty")

        if self.domain not in SCOPE_DETAIL_ALLOWED_DOMAINS:
            errors.append(
                f"ExpectedObligation: domain '{self.domain}' not in allowed domains"
            )

        if not self.evidence_excerpt or not self.evidence_excerpt.strip():
            errors.append("ExpectedObligation: evidence_excerpt is empty")

        return tuple(errors)


@dataclass(frozen=True, slots=True)
class SemanticGoldenCase:
    """
    Provider-neutral immutable Golden case contract.

    For REAL cases from the Golden Tender:
    - human_label_status must be PENDING only (in this slice)
    - expected_obligations must be empty
    - The actual human-approved labels will be added in a later manual step.

    For SYNTHETIC TEST cases:
    - human_label_status may be APPROVED
    - expected_obligations contains the expected ground truth
    """

    case_id: str
    golden_set_version: str
    tender_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_text: str
    source_text_sha256: str
    evaluation_mode: str
    human_label_status: str
    expected_obligations: tuple[ExpectedObligation, ...] = field(default_factory=tuple)
    candidate_reason: str | None = None
    source_contract_version: str | None = None

    def validate(self) -> tuple[str, ...]:
        """Deterministically validate Golden case. Return tuple of error messages."""
        errors = []

        if not self.case_id or not self.case_id.strip():
            errors.append("SemanticGoldenCase: case_id is empty")

        if self.golden_set_version != SEMANTIC_GOLDEN_VERSION:
            errors.append(
                f"SemanticGoldenCase: golden_set_version mismatch. "
                f"Expected {SEMANTIC_GOLDEN_VERSION}, got {self.golden_set_version}"
            )

        if not self.tender_id or not self.tender_id.strip():
            errors.append("SemanticGoldenCase: tender_id is empty")

        if not self.source_document_id or not self.source_document_id.strip():
            errors.append("SemanticGoldenCase: source_document_id is empty")

        if not self.document_page_id or not self.document_page_id.strip():
            errors.append("SemanticGoldenCase: document_page_id is empty")

        if self.page_number < 0:
            errors.append(f"SemanticGoldenCase: page_number is negative ({self.page_number})")

        if self.source_method not in ALLOWED_GOLDEN_SOURCE_METHODS:
            errors.append(
                f"SemanticGoldenCase: source_method '{self.source_method}' not in allowed methods"
            )

        if not self.source_artifact_key or not self.source_artifact_key.strip():
            errors.append("SemanticGoldenCase: source_artifact_key is empty")

        if not self.source_locator or not self.source_locator.strip():
            errors.append("SemanticGoldenCase: source_locator is empty")
        else:
            # Validate character offset format and values
            if "|chars_" in self.source_locator:
                try:
                    chars_part = self.source_locator.split("|chars_")[1]
                    start_str, end_str = chars_part.split("-")
                    char_start = int(start_str)
                    char_end = int(end_str)

                    if char_start < 0:
                        errors.append(
                            f"SemanticGoldenCase: character offset start is negative ({char_start}). "
                            f"Locator: {self.source_locator}"
                        )
                    if char_end <= char_start:
                        errors.append(
                            f"SemanticGoldenCase: character offset end ({char_end}) must be > start ({char_start}). "
                            f"Locator: {self.source_locator}"
                        )
                except (ValueError, IndexError):
                    errors.append(
                        f"SemanticGoldenCase: source_locator has invalid |chars_START-END format. "
                        f"Locator: {self.source_locator}"
                    )

        if not self.source_text or not self.source_text.strip():
            errors.append("SemanticGoldenCase: source_text is empty")

        # Validate SHA256
        computed_sha256 = hashlib.sha256(self.source_text.encode("utf-8")).hexdigest()
        if computed_sha256 != self.source_text_sha256:
            errors.append(
                f"SemanticGoldenCase: SHA256 mismatch. "
                f"Expected {self.source_text_sha256}, computed {computed_sha256}"
            )

        if self.evaluation_mode not in ALLOWED_GOLDEN_EVALUATION_MODES:
            errors.append(
                f"SemanticGoldenCase: evaluation_mode '{self.evaluation_mode}' not in allowed modes"
            )

        if self.human_label_status not in ALLOWED_GOLDEN_HUMAN_LABEL_STATUSES:
            errors.append(
                f"SemanticGoldenCase: human_label_status '{self.human_label_status}' not in allowed statuses"
            )

        # Validate expected obligations
        for expected_obligation in self.expected_obligations:
            obligation_errors = expected_obligation.validate()
            errors.extend(obligation_errors)

        # Evidence grounding check: each expected obligation evidence must be in source text
        for expected_obligation in self.expected_obligations:
            if expected_obligation.evidence_excerpt not in self.source_text:
                errors.append(
                    f"SemanticGoldenCase: expected obligation evidence not grounded in source text. "
                    f"Evidence: {expected_obligation.evidence_excerpt[:50]}..."
                )

        # STRICT + APPROVED requires at least one expected obligation
        if (
            self.evaluation_mode == GOLDEN_EVALUATION_MODE_STRICT
            and self.human_label_status == GOLDEN_HUMAN_LABEL_STATUS_APPROVED
            and len(self.expected_obligations) == 0
        ):
            errors.append(
                "SemanticGoldenCase: STRICT mode with APPROVED status requires at least one expected obligation"
            )

        # NO_OBLIGATIONS + APPROVED requires zero expected obligations
        if (
            self.evaluation_mode == GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS
            and self.human_label_status == GOLDEN_HUMAN_LABEL_STATUS_APPROVED
            and len(self.expected_obligations) > 0
        ):
            errors.append(
                "SemanticGoldenCase: NO_OBLIGATIONS mode must have zero expected obligations"
            )

        return tuple(errors)


@dataclass(frozen=True, slots=True)
class SemanticGoldenEvaluationMatch:
    """Represents a match between a predicted obligation and an expected obligation."""

    expected_obligation_index: int
    predicted_obligation_index: int
    match_type: str  # "exact" | "expected_contains_predicted" | "predicted_contains_expected"


@dataclass(frozen=True, slots=True)
class SemanticGoldenEvaluation:
    """
    Deterministic evaluation result comparing predicted to expected obligations.

    PENDING cases always evaluate to UNLABELED status (never PASS/FAIL).
    APPROVED cases evaluate based on mode and matching logic.
    """

    case_id: str
    evaluation_status: str
    provider_result_status: str
    expected_count: int
    predicted_count: int
    matched_count: int
    recall: float | None = None  # matched / expected
    precision: float | None = None  # matched / predicted
    unmatched_expected_obligation_indices: tuple[int, ...] = field(default_factory=tuple)
    unexpected_prediction_indices: tuple[int, ...] = field(default_factory=tuple)
    review_required_prediction_count: int = 0
    validation_errors: tuple[str, ...] = field(default_factory=tuple)
    mixed_domain_candidate_indices: tuple[int, ...] = field(default_factory=tuple)


class SemanticGoldenValidator:
    """Deterministically validate Golden case data integrity."""

    @staticmethod
    def validate(case: SemanticGoldenCase) -> tuple[str, ...]:
        """Return tuple of validation error messages."""
        return case.validate()


class SemanticGoldenEvaluator:
    """
    Deterministic provider-neutral evaluator.

    Matches are based on:
    1. Exact domain match
    2. Grounded evidence containment (not similarity)
    3. One-to-one matching (each predicted/expected matched at most once)
    4. Priority: exact match > containment > order
    """

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace for comparison."""
        return " ".join(text.split())

    @staticmethod
    def _evidence_matches(expected: str, predicted: str) -> tuple[bool, str]:
        """
        Check if predicted evidence matches expected evidence.

        Returns: (match: bool, match_type: str)

        Match types:
        - "exact": exact match
        - "predicted_contains_expected": predicted is broader
        - "expected_contains_predicted": expected is broader
        """
        expected_norm = SemanticGoldenEvaluator._normalize_whitespace(expected)
        predicted_norm = SemanticGoldenEvaluator._normalize_whitespace(predicted)

        if expected_norm == predicted_norm:
            return True, "exact"

        if expected_norm in predicted_norm:
            return True, "predicted_contains_expected"

        if predicted_norm in expected_norm:
            return True, "expected_contains_predicted"

        return False, ""

    @staticmethod
    def _find_matches(
        expected_obligations: tuple[ExpectedObligation, ...],
        predicted_obligations: tuple[DiscoveredScopeObligation, ...],
    ) -> tuple[SemanticGoldenEvaluationMatch, ...]:
        """
        Find one-to-one matches between expected and predicted obligations.

        Matching priority:
        1. exact evidence match
        2. containment match (prefer expected_contains_predicted)
        3. stable order tie-break
        """
        matches: list[SemanticGoldenEvaluationMatch] = []
        matched_expected: set[int] = set()
        matched_predicted: set[int] = set()

        # First pass: exact matches
        for exp_idx, expected_obl in enumerate(expected_obligations):
            if exp_idx in matched_expected:
                continue
            for pred_idx, predicted_obl in enumerate(predicted_obligations):
                if pred_idx in matched_predicted:
                    continue

                if expected_obl.domain != predicted_obl.domain:
                    continue

                matches_evidence, match_type = SemanticGoldenEvaluator._evidence_matches(
                    expected_obl.evidence_excerpt, predicted_obl.evidence_excerpt
                )
                if matches_evidence and match_type == "exact":
                    matches.append(
                        SemanticGoldenEvaluationMatch(
                            expected_obligation_index=exp_idx,
                            predicted_obligation_index=pred_idx,
                            match_type=match_type,
                        )
                    )
                    matched_expected.add(exp_idx)
                    matched_predicted.add(pred_idx)
                    break

        # Second pass: containment matches (prefer narrower/broader)
        for exp_idx, expected_obl in enumerate(expected_obligations):
            if exp_idx in matched_expected:
                continue
            for pred_idx, predicted_obl in enumerate(predicted_obligations):
                if pred_idx in matched_predicted:
                    continue

                if expected_obl.domain != predicted_obl.domain:
                    continue

                matches_evidence, match_type = SemanticGoldenEvaluator._evidence_matches(
                    expected_obl.evidence_excerpt, predicted_obl.evidence_excerpt
                )
                if matches_evidence:
                    matches.append(
                        SemanticGoldenEvaluationMatch(
                            expected_obligation_index=exp_idx,
                            predicted_obligation_index=pred_idx,
                            match_type=match_type,
                        )
                    )
                    matched_expected.add(exp_idx)
                    matched_predicted.add(pred_idx)
                    break

        return tuple(matches)

    @staticmethod
    def _find_mixed_domain_candidates(
        expected_obligations: tuple[ExpectedObligation, ...],
        predicted_obligations: tuple[DiscoveredScopeObligation, ...],
    ) -> tuple[int, ...]:
        """
        Diagnostic: find predicted obligations that contain evidence from multiple
        expected obligations of DIFFERENT domains.

        This flags potential atomicity issues (e.g., Ollama combining unrelated clauses).
        """
        mixed_domain_predicted_indices: set[int] = set()

        for pred_idx, predicted_obl in enumerate(predicted_obligations):
            domains_found: set[str] = set()

            for expected_obl in expected_obligations:
                if expected_obl.domain not in domains_found:
                    expected_norm = SemanticGoldenEvaluator._normalize_whitespace(
                        expected_obl.evidence_excerpt
                    )
                    predicted_norm = SemanticGoldenEvaluator._normalize_whitespace(
                        predicted_obl.evidence_excerpt
                    )

                    if expected_norm in predicted_norm:
                        domains_found.add(expected_obl.domain)

            if len(domains_found) > 1:
                mixed_domain_predicted_indices.add(pred_idx)

        return tuple(sorted(mixed_domain_predicted_indices))

    @staticmethod
    def evaluate(
        golden_case: SemanticGoldenCase,
        provider_result: ScopeSemanticDiscoveryResult,
    ) -> SemanticGoldenEvaluation:
        """
        Deterministically evaluate provider result against Golden case.
        """
        validation_errors = SemanticGoldenValidator.validate(golden_case)

        if validation_errors:
            return SemanticGoldenEvaluation(
                case_id=golden_case.case_id,
                evaluation_status=GOLDEN_EVAL_STATUS_INVALID,
                provider_result_status=provider_result.status,
                expected_count=len(golden_case.expected_obligations),
                predicted_count=provider_result.candidate_count,
                matched_count=0,
                validation_errors=validation_errors,
            )

        # PENDING cases are UNLABELED
        if golden_case.human_label_status == GOLDEN_HUMAN_LABEL_STATUS_PENDING:
            return SemanticGoldenEvaluation(
                case_id=golden_case.case_id,
                evaluation_status=GOLDEN_EVAL_STATUS_UNLABELED,
                provider_result_status=provider_result.status,
                expected_count=len(golden_case.expected_obligations),
                predicted_count=provider_result.candidate_count,
                matched_count=0,
            )

        # REVIEW_ONLY always requires review
        if golden_case.evaluation_mode == GOLDEN_EVALUATION_MODE_REVIEW_ONLY:
            return SemanticGoldenEvaluation(
                case_id=golden_case.case_id,
                evaluation_status=GOLDEN_EVAL_STATUS_REVIEW_REQUIRED,
                provider_result_status=provider_result.status,
                expected_count=len(golden_case.expected_obligations),
                predicted_count=provider_result.candidate_count,
                matched_count=0,
            )

        # Provider error handling
        from app.scope_semantic_discovery import SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT

        if provider_result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT:
            return SemanticGoldenEvaluation(
                case_id=golden_case.case_id,
                evaluation_status=GOLDEN_EVAL_STATUS_FAIL,
                provider_result_status=provider_result.status,
                expected_count=len(golden_case.expected_obligations),
                predicted_count=0,
                matched_count=0,
                validation_errors=provider_result.errors,
            )

        # Find one-to-one matches
        matches = SemanticGoldenEvaluator._find_matches(
            golden_case.expected_obligations,
            provider_result.candidates,
        )

        matched_expected_indices: set[int] = {m.expected_obligation_index for m in matches}
        matched_predicted_indices: set[int] = {m.predicted_obligation_index for m in matches}

        unmatched_expected = tuple(
            i for i in range(len(golden_case.expected_obligations)) if i not in matched_expected_indices
        )
        unexpected_predicted = tuple(
            i for i in range(len(provider_result.candidates)) if i not in matched_predicted_indices
        )

        # Mixed domain diagnostic
        mixed_domain_indices = SemanticGoldenEvaluator._find_mixed_domain_candidates(
            golden_case.expected_obligations,
            provider_result.candidates,
        )

        # Review required count
        review_required_count = sum(
            1 for pred in provider_result.candidates if pred.review_required
        )

        # Calculate recall and precision
        expected_count = len(golden_case.expected_obligations)
        predicted_count = len(provider_result.candidates)
        matched_count = len(matches)

        recall = matched_count / expected_count if expected_count > 0 else 0.0
        precision = matched_count / predicted_count if predicted_count > 0 else 0.0

        # Determine evaluation status
        eval_status = GOLDEN_EVAL_STATUS_FAIL

        if golden_case.evaluation_mode == GOLDEN_EVALUATION_MODE_STRICT:
            # STRICT: all expected matched, no unexpected
            if (
                len(unmatched_expected) == 0
                and len(unexpected_predicted) == 0
                and len(mixed_domain_indices) == 0
            ):
                eval_status = GOLDEN_EVAL_STATUS_PASS
            elif len(mixed_domain_indices) > 0 or review_required_count > 0:
                eval_status = GOLDEN_EVAL_STATUS_REVIEW_REQUIRED
            else:
                eval_status = GOLDEN_EVAL_STATUS_FAIL

        elif golden_case.evaluation_mode == GOLDEN_EVALUATION_MODE_NO_OBLIGATIONS:
            # NO_OBLIGATIONS: zero predicted obligations
            if predicted_count == 0 and len(provider_result.errors) == 0:
                eval_status = GOLDEN_EVAL_STATUS_PASS
            elif review_required_count > 0:
                eval_status = GOLDEN_EVAL_STATUS_REVIEW_REQUIRED
            else:
                eval_status = GOLDEN_EVAL_STATUS_FAIL

        return SemanticGoldenEvaluation(
            case_id=golden_case.case_id,
            evaluation_status=eval_status,
            provider_result_status=provider_result.status,
            expected_count=expected_count,
            predicted_count=predicted_count,
            matched_count=matched_count,
            recall=recall,
            precision=precision,
            unmatched_expected_obligation_indices=unmatched_expected,
            unexpected_prediction_indices=unexpected_predicted,
            review_required_prediction_count=review_required_count,
            mixed_domain_candidate_indices=mixed_domain_indices,
        )
