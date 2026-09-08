#!/usr/bin/env python3
"""
MVP-06.3.4c — Scope Semantic Golden Set Calibration Runner

Deterministic evaluation of semantic scope discovery provider against
architect-approved Golden cases.

Usage:
  python scripts/run_scope_semantic_golden.py --model qwen3:8b
  python scripts/run_scope_semantic_golden.py --model qwen3:8b --golden evals/semantic_scope_golden_v1.json

The runner:
1. Loads Golden JSON with 12 APPROVED cases
2. Constructs OllamaScopeSemanticDiscoveryProvider with specified model
3. For each case: extract fragment, invoke provider.discover(), evaluate against expected
4. Aggregates per-case results: PASS/FAIL/REVIEW_REQUIRED/INVALID
5. Reports recall, precision, missing/unexpected obligations
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ollama_scope_semantic_provider import OllamaScopeSemanticDiscoveryProvider
from app.scope_semantic_discovery import (
    SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    ScopeSemanticSourceFragment,
    discover_scope_semantics,
)
from app.scope_semantic_golden import (
    GOLDEN_EVAL_STATUS_FAIL,
    GOLDEN_EVAL_STATUS_INVALID,
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_EVAL_STATUS_REVIEW_REQUIRED,
    ExpectedObligation,
    SemanticGoldenCase,
    SemanticGoldenEvaluator,
)


@dataclass(frozen=True)
class CaseEvaluationResult:
    """Result of evaluating a single Golden case."""

    case_id: str
    case_number: int
    evaluation_mode: str
    expected_count: int
    discovered_count: int
    matched_count: int
    eval_status: str
    provider_status: str
    discovery_status: str
    recall: float
    precision: float
    missing_expected: tuple[int, ...]
    unexpected_discovered: tuple[int, ...]
    elapsed_ms: int
    validation_errors: tuple[str, ...]
    mixed_domain_issues: tuple[int, ...]
    expected_obligations: tuple[Any, ...]
    discovered_candidates: tuple[Any, ...]
    discovery_errors: tuple[str, ...]


def _load_golden(golden_path: str) -> dict[str, Any]:
    """Load and parse Golden JSON."""
    with open(golden_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _golden_dict_to_case(case_dict: dict[str, Any]) -> SemanticGoldenCase:
    """Convert Golden JSON case object to SemanticGoldenCase dataclass."""
    expected_oblig_dicts = case_dict.get("expected_obligations", [])
    expected_obligations = tuple(
        ExpectedObligation(
            golden_obligation_id=o["golden_obligation_id"],
            domain=o["domain"],
            evidence_excerpt=o["evidence_excerpt"],
            review_required=o.get("review_required"),
            quantity_raw=o.get("quantity_raw"),
            unit_raw=o.get("unit_raw"),
            human_note=o.get("human_note"),
        )
        for o in expected_oblig_dicts
    )

    return SemanticGoldenCase(
        case_id=case_dict["case_id"],
        golden_set_version=case_dict["golden_set_version"],
        tender_id=case_dict["tender_id"],
        source_document_id=case_dict["source_document_id"],
        document_page_id=case_dict["document_page_id"],
        page_number=case_dict["page_number"],
        source_method=case_dict["source_method"],
        source_artifact_key=case_dict["source_artifact_key"],
        source_locator=case_dict["source_locator"],
        source_text=case_dict["source_text"],
        source_text_sha256=case_dict["source_text_sha256"],
        evaluation_mode=case_dict["evaluation_mode"],
        human_label_status=case_dict["human_label_status"],
        expected_obligations=expected_obligations,
        candidate_reason=case_dict.get("candidate_reason"),
        source_contract_version=case_dict.get("source_contract_version"),
    )


def _evaluate_case(
    golden_case: SemanticGoldenCase,
    provider: OllamaScopeSemanticDiscoveryProvider,
    case_number: int,
) -> CaseEvaluationResult:
    """Evaluate a single Golden case against provider predictions."""
    started = time.time()

    # Construct source fragment
    fragment = ScopeSemanticSourceFragment(
        tender_id=golden_case.tender_id,
        source_document_id=golden_case.source_document_id,
        document_page_id=golden_case.document_page_id,
        page_number=golden_case.page_number,
        source_method=golden_case.source_method,
        source_artifact_key=golden_case.source_artifact_key,
        source_locator=golden_case.source_locator,
        source_text=golden_case.source_text,
        source_contract_version=golden_case.source_contract_version,
    )

    # Invoke provider through neutral discovery orchestration
    try:
        provider_result = discover_scope_semantics(
            fragment=fragment,
            providers=[provider]
        )
    except Exception as exc:
        from app.scope_semantic_discovery import ScopeSemanticDiscoveryResult

        provider_result = ScopeSemanticDiscoveryResult(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            candidate_count=0,
            review_required_count=0,
            status=SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidates=(),
            errors=(str(exc),),
        )

    # Evaluate
    evaluation = SemanticGoldenEvaluator.evaluate(golden_case, provider_result)

    elapsed_ms = int((time.time() - started) * 1000)

    return CaseEvaluationResult(
        case_id=golden_case.case_id,
        case_number=case_number,
        evaluation_mode=golden_case.evaluation_mode,
        expected_count=evaluation.expected_count,
        discovered_count=evaluation.predicted_count,
        matched_count=evaluation.matched_count,
        eval_status=evaluation.evaluation_status,
        provider_status=evaluation.provider_result_status,
        discovery_status=provider_result.status,
        recall=evaluation.recall or 0.0,
        precision=evaluation.precision or 0.0,
        missing_expected=evaluation.unmatched_expected_obligation_indices,
        unexpected_discovered=evaluation.unexpected_prediction_indices,
        elapsed_ms=elapsed_ms,
        validation_errors=evaluation.validation_errors,
        mixed_domain_issues=evaluation.mixed_domain_candidate_indices,
        expected_obligations=golden_case.expected_obligations,
        discovered_candidates=provider_result.candidates,
        discovery_errors=provider_result.errors,
    )


def _print_case_result(result: CaseEvaluationResult) -> None:
    """Print detailed diagnostic result for a single case."""
    print(f"\n{'=' * 120}")
    print(f"Case {result.case_number}/12: {result.case_id}")
    print(f"{'=' * 120}")
    print(f"Evaluation Mode: {result.evaluation_mode}")
    print(f"Status: {result.eval_status} | Discovery Status: {result.discovery_status}")
    print(f"Counts: Expected={result.expected_count}, Discovered={result.discovered_count}, Matched={result.matched_count}")
    print(f"Metrics: Recall={result.recall:.1%}, Precision={result.precision:.1%}")
    print(f"Elapsed: {result.elapsed_ms}ms")

    # Expected obligations
    print(f"\nEXPECTED OBLIGATIONS ({result.expected_count}):")
    if result.expected_count == 0:
        print("  NONE")
    else:
        for idx, oblig in enumerate(result.expected_obligations):
            print(f"  [{idx}] {oblig.golden_obligation_id}")
            print(f"      Domain: {oblig.domain}")
            print(f"      Evidence: {oblig.evidence_excerpt[:100]}..." if len(oblig.evidence_excerpt) > 100 else f"      Evidence: {oblig.evidence_excerpt}")
            if oblig.quantity_raw:
                print(f"      Quantity: {oblig.quantity_raw}")
            if oblig.unit_raw:
                print(f"      Unit: {oblig.unit_raw}")
            if oblig.review_required:
                print(f"      Review Required: {oblig.review_required}")

    # Discovered candidates
    print(f"\nDISCOVERED CANDIDATES ({result.discovered_count}):")
    if result.discovered_count == 0:
        print("  NONE")
    else:
        for idx, candidate in enumerate(result.discovered_candidates):
            print(f"  [{idx}]")
            print(f"      Domain: {candidate.domain}")
            print(f"      Description: {candidate.description}")
            print(f"      Evidence: {candidate.evidence_excerpt}")
            if candidate.detail_type:
                print(f"      Detail Type: {candidate.detail_type}")
            if candidate.normalized_label:
                print(f"      Normalized Label: {candidate.normalized_label}")
            if candidate.confidence is not None:
                print(f"      Confidence: {candidate.confidence:.2f}")
            if candidate.quantity_raw:
                print(f"      Quantity: {candidate.quantity_raw}")
            if candidate.unit_raw:
                print(f"      Unit: {candidate.unit_raw}")
            if candidate.review_required:
                print(f"      Review Required: {candidate.review_required}")
            if candidate.candidate_item_key:
                print(f"      Candidate Item Key: {candidate.candidate_item_key}")
            if candidate.applicability_hint:
                print(f"      Applicability Hint: {candidate.applicability_hint}")

    # Discovery status and errors
    print(f"\nDISCOVERY STATUS: {result.discovery_status}")
    if result.discovery_errors:
        print(f"DISCOVERY ERRORS:")
        for error in result.discovery_errors:
            print(f"  • {error}")

    # Match diagnostics
    print(f"\nMATCH DIAGNOSTICS:")
    print(f"  Expected: {result.expected_count}")
    print(f"  Discovered: {result.discovered_count}")
    print(f"  Matched: {result.matched_count}")
    if result.missing_expected:
        print(f"  Missing Expected Indices: {result.missing_expected}")
    if result.unexpected_discovered:
        print(f"  Unexpected Discovered Indices: {result.unexpected_discovered}")
    if result.mixed_domain_issues:
        print(f"  Mixed-Domain Issues: {result.mixed_domain_issues}")

    # Validation errors
    if result.validation_errors:
        print(f"\nVALIDATION ERRORS:")
        for error in result.validation_errors:
            print(f"  • {error}")


def _print_summary(results: Sequence[CaseEvaluationResult]) -> None:
    """Print aggregate summary with discovery status visibility."""
    print("\n" + "=" * 120)
    print("GOLDEN CALIBRATION SUMMARY")
    print("=" * 120)

    # Evaluation status counts
    eval_status_counts = {}
    for result in results:
        status = result.eval_status
        eval_status_counts[status] = eval_status_counts.get(status, 0) + 1

    print(f"\nEVALUATION RESULTS ({len(results)} cases):")
    print(f"  PASS:             {eval_status_counts.get(GOLDEN_EVAL_STATUS_PASS, 0)}")
    print(f"  FAIL:             {eval_status_counts.get(GOLDEN_EVAL_STATUS_FAIL, 0)}")
    print(f"  REVIEW_REQUIRED:  {eval_status_counts.get(GOLDEN_EVAL_STATUS_REVIEW_REQUIRED, 0)}")
    print(f"  INVALID:          {eval_status_counts.get(GOLDEN_EVAL_STATUS_INVALID, 0)}")

    # Discovery status counts (separate from evaluation)
    discovery_status_counts = {}
    for result in results:
        status = result.discovery_status
        discovery_status_counts[status] = discovery_status_counts.get(status, 0) + 1

    print(f"\nDISCOVERY STATUS COUNTS:")
    for status in sorted(discovery_status_counts.keys()):
        print(f"  {status}: {discovery_status_counts[status]}")

    # Obligation aggregates
    total_expected = sum(r.expected_count for r in results)
    total_discovered = sum(r.discovered_count for r in results)
    total_matched = sum(r.matched_count for r in results)

    print(f"\nOBLIGATION AGGREGATES:")
    print(f"  Total expected:        {total_expected}")
    print(f"  Total discovered:      {total_discovered}")
    print(f"  Total matched:         {total_matched}")

    if total_expected > 0:
        overall_recall = total_matched / total_expected
        print(f"  Overall recall:        {overall_recall:.1%}")
    if total_discovered > 0:
        overall_precision = total_matched / total_discovered
        print(f"  Overall precision:     {overall_precision:.1%}")

    # Defect counts
    total_missing = sum(len(r.missing_expected) for r in results)
    total_unexpected = sum(len(r.unexpected_discovered) for r in results)
    total_mixed_domain = sum(len(r.mixed_domain_issues) for r in results)

    print(f"\nDEFECT COUNTS:")
    print(f"  Missing expected:      {total_missing}")
    print(f"  Unexpected discovered: {total_unexpected}")
    print(f"  Mixed-domain issues:   {total_mixed_domain}")

    # Timing details
    total_elapsed = sum(r.elapsed_ms for r in results)
    avg_elapsed = total_elapsed / len(results) if results else 0
    max_elapsed = max((r.elapsed_ms for r in results), default=0)
    max_case = next((r.case_id for r in results if r.elapsed_ms == max_elapsed), "N/A")

    print(f"\nTIMING:")
    print(f"  Total elapsed:         {total_elapsed}ms ({total_elapsed / 1000:.2f}s)")
    print(f"  Average per case:      {avg_elapsed:.1f}ms")
    print(f"  Maximum elapsed:       {max_elapsed}ms ({max_case})")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scope Semantic Golden Set Calibration Runner"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen3:8b",
        help="Ollama model name (default: qwen3:8b)",
    )
    parser.add_argument(
        "--golden",
        type=str,
        default="evals/semantic_scope_golden_v1.json",
        help="Path to Golden JSON (default: evals/semantic_scope_golden_v1.json)",
    )

    args = parser.parse_args()

    golden_path = args.golden
    model_name = args.model

    print("=" * 120)
    print("SCOPE SEMANTIC GOLDEN CALIBRATION RUNNER")
    print("=" * 120)
    print(f"Model: {model_name}")
    print(f"Golden: {golden_path}")
    print("")

    # Load Golden
    try:
        golden_dict = _load_golden(golden_path)
        cases_data = golden_dict["cases"]
        case_count = golden_dict["case_count"]
        print(f"Loaded Golden Set: {case_count} cases")
    except Exception as exc:
        print(f"ERROR: Failed to load Golden: {exc}")
        return 1

    # Initialize provider with specified model
    print(f"Initializing OllamaScopeSemanticDiscoveryProvider with model '{model_name}'...")
    try:
        provider = OllamaScopeSemanticDiscoveryProvider(model_name=model_name)
    except Exception as exc:
        print(f"ERROR: Failed to initialize provider: {exc}")
        return 1

    print("")
    print("=" * 120)
    print("EVALUATING CASES")
    print("=" * 120)

    # Evaluate all cases
    results: list[CaseEvaluationResult] = []
    for case_number, case_dict in enumerate(cases_data, 1):
        try:
            golden_case = _golden_dict_to_case(case_dict)
            result = _evaluate_case(golden_case, provider, case_number)
            results.append(result)
            _print_case_result(result)
        except Exception as exc:
            print(f"\nCase {case_number}: EXCEPTION")
            print(f"  Error: {exc}")
            return 1

    # Print summary
    _print_summary(results)

    print("")
    print("=" * 120)

    return 0


if __name__ == "__main__":
    sys.exit(main())
