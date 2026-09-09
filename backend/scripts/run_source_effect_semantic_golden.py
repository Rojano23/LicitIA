#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.ollama_source_effect_provider import (
    OLLAMA_SOURCE_EFFECT_PROMPT_VERSION,
    OllamaSourceEffectDiscoveryProvider,
    run_ollama_source_effect_discovery,
)
from app.source_effect_golden import (
    CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
    DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
    DISCOVERY_STATUS_INVALID_OUTPUT,
    DISCOVERY_STATUS_NO_EFFECTS,
    DISCOVERY_STATUS_REVIEW_REQUIRED,
    ExpectedSourceEffect,
    SourceEffectAggregateMetrics,
    SourceEffectCaseEvaluation,
    SourceEffectGoldenCase,
    SourceEffectGoldenDataset,
    aggregate_evaluations,
    evaluate_case,
    load_source_effect_golden,
    validate_source_effect_golden,
)
from app.source_effect_partial_resolution import normalize_partial_locator_identity
from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SourceEffectSemanticDiscoveryResult,
    SourceEffectSemanticFragment,
)

BASELINE_CLASSIFICATION = "BASELINE_ONLY"


@dataclass(frozen=True, slots=True)
class CaseRuntimeResult:
    case_id: str
    category: str
    expected_discovery_status: str
    actual_discovery_status: str
    evaluation_status: str
    expected_effect_count: int
    discovered_effect_count: int
    matched_effect_count: int
    false_positive_effect_count: int
    false_negative_effect_count: int
    review_expected: bool
    review_actual: bool
    review_correctly_surfaced: bool
    review_missed: bool
    grounding_ok: bool
    grounding_failures: tuple[str, ...]
    semantic_mismatch: tuple[str, ...]
    contract_shape_failure: tuple[str, ...]
    target_resolution_mismatch: tuple[str, ...]
    review_policy_mismatch: tuple[str, ...]
    diagnostics: tuple[str, ...]
    errors: tuple[str, ...]
    expected_effects: tuple[dict[str, Any], ...]
    actual_effects: tuple[dict[str, Any], ...]
    matched_effects: tuple[dict[str, int], ...]
    false_positive_effects: tuple[dict[str, Any], ...]
    false_negative_effects: tuple[dict[str, Any], ...]
    provider_name: str | None
    provider_version: str | None
    provider_contract_version: str | None
    provider_model: str
    elapsed_time_ms: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run real source-effect semantic provider against frozen human Golden V1"
    )
    parser.add_argument(
        "--golden",
        default="evals/source_effect_golden_v1.json",
        help="Path to source-effect Golden JSON",
    )
    parser.add_argument(
        "--model",
        default="qwen3:8b",
        help="Ollama model to evaluate (default: qwen3:8b)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output path for machine-readable report JSON",
    )
    parser.add_argument(
        "--allow-non-frozen",
        action="store_true",
        help="Development override: allow non-frozen datasets (never use for certification)",
    )
    return parser.parse_args()


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def _normalized_locator(value: str | None) -> str:
    normalized = normalize_partial_locator_identity(value)
    return normalized or ""


def _match_effect_indices(
    *,
    expected: Sequence[ExpectedSourceEffect],
    discovered: Sequence[DiscoveredSourceEffect],
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    matched_pairs: list[tuple[int, int]] = []
    used_discovered: set[int] = set()

    for expected_idx, expected_effect in enumerate(expected):
        selected_discovered: int | None = None
        for discovered_idx, discovered_effect in enumerate(discovered):
            if discovered_idx in used_discovered:
                continue
            if expected_effect.expected_effect_type and expected_effect.expected_effect_type != discovered_effect.effect_type:
                continue
            if expected_effect.expected_effect_scope and expected_effect.expected_effect_scope != discovered_effect.effect_scope:
                continue

            locator_ok = True
            if expected_effect.expected_affected_locator_raw is not None:
                locator_ok = _normalized_locator(expected_effect.expected_affected_locator_raw) == _normalized_locator(
                    discovered_effect.affected_locator_raw
                )

            document_ref_ok = True
            if expected_effect.expected_affected_document_ref_raw is not None:
                document_ref_ok = _normalize_text(expected_effect.expected_affected_document_ref_raw) == _normalize_text(
                    discovered_effect.affected_document_ref_raw
                )

            date_ok = True
            if expected_effect.expected_effective_date_raw is not None:
                date_ok = _normalize_text(expected_effect.expected_effective_date_raw) == _normalize_text(
                    discovered_effect.effective_date_raw
                )

            if locator_ok and document_ref_ok and date_ok:
                selected_discovered = discovered_idx
                break

        if selected_discovered is not None:
            used_discovered.add(selected_discovered)
            matched_pairs.append((expected_idx, selected_discovered))

    unmatched_expected = [idx for idx in range(len(expected)) if idx not in {pair[0] for pair in matched_pairs}]
    unmatched_discovered = [idx for idx in range(len(discovered)) if idx not in used_discovered]
    return matched_pairs, unmatched_expected, unmatched_discovered


def _as_expected_effect_dict(effect: ExpectedSourceEffect) -> dict[str, Any]:
    return {
        "expected_effect_type": effect.expected_effect_type,
        "expected_effect_scope": effect.expected_effect_scope,
        "expected_affected_document_ref_raw": effect.expected_affected_document_ref_raw,
        "expected_affected_document_id": effect.expected_affected_document_id,
        "expected_affected_locator_raw": effect.expected_affected_locator_raw,
        "expected_effective_date_raw": effect.expected_effective_date_raw,
        "expected_review_required": effect.expected_review_required,
    }


def _as_discovered_effect_dict(effect: DiscoveredSourceEffect) -> dict[str, Any]:
    return {
        "effect_type": effect.effect_type,
        "effect_scope": effect.effect_scope,
        "affected_document_ref_raw": effect.affected_document_ref_raw,
        "affected_locator_raw": effect.affected_locator_raw,
        "effective_date_raw": effect.effective_date_raw,
        "evidence_excerpt": effect.evidence_excerpt,
        "confidence": effect.confidence,
    }


def _build_fragment(case: SourceEffectGoldenCase) -> SourceEffectSemanticFragment:
    return SourceEffectSemanticFragment(
        tender_id=case.tender_id,
        acting_document_id=case.acting_document_id,
        document_page_id=str(case.document_page_id or ""),
        page_number=1,
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
        source_locator=case.source_locator,
        source_text=case.source_excerpt,
        source_contract_version=OLLAMA_SOURCE_EFFECT_PROMPT_VERSION,
    )


def _build_invalid_result(
    *,
    provider_name: str,
    provider_version: str,
    contract_version: str,
    error_message: str,
) -> SourceEffectSemanticDiscoveryResult:
    return SourceEffectSemanticDiscoveryResult(
        provider_name=provider_name,
        provider_version=provider_version,
        contract_version=contract_version,
        status=DISCOVERY_STATUS_INVALID_OUTPUT,
        candidate_count=0,
        review_required_count=0,
        candidates=(),
        discovered_effects=(),
        diagnostics=(),
        errors=(error_message,),
    )


def _certification_dataset_errors(dataset: SourceEffectGoldenDataset) -> list[str]:
    errors: list[str] = []
    if dataset.dataset_status != DATASET_STATUS_FROZEN_LIMITED_COVERAGE:
        errors.append("certification_mode requires dataset_status=FROZEN_LIMITED_COVERAGE")
    if dataset.label_status != CANDIDATE_LABEL_STATUS_HUMAN_APPROVED:
        errors.append("certification_mode requires label_status=HUMAN_APPROVED")
    for case in dataset.cases:
        if case.candidate_label_status != CANDIDATE_LABEL_STATUS_HUMAN_APPROVED:
            errors.append(
                f"certification_mode requires HUMAN_APPROVED case labels; found {case.case_id}:{case.candidate_label_status}"
            )
            break
    return errors


def _case_runtime_result(
    *,
    case: SourceEffectGoldenCase,
    evaluation: SourceEffectCaseEvaluation,
    actual: SourceEffectSemanticDiscoveryResult,
    model_name: str,
    elapsed_time_ms: int,
) -> CaseRuntimeResult:
    expected_effects = tuple(_as_expected_effect_dict(item) for item in case.expected_effects)
    discovered_effects = tuple(_as_discovered_effect_dict(item) for item in actual.discovered_effects)

    matched_pairs, unmatched_expected, unmatched_discovered = _match_effect_indices(
        expected=case.expected_effects,
        discovered=actual.discovered_effects,
    )

    return CaseRuntimeResult(
        case_id=case.case_id,
        category=case.category,
        expected_discovery_status=case.expected_discovery_status,
        actual_discovery_status=actual.status,
        evaluation_status=evaluation.evaluation_status,
        expected_effect_count=evaluation.expected_positive_count,
        discovered_effect_count=evaluation.discovered_positive_count,
        matched_effect_count=evaluation.matched_positive_count,
        false_positive_effect_count=evaluation.false_positive_count,
        false_negative_effect_count=evaluation.false_negative_count,
        review_expected=evaluation.review_expected,
        review_actual=actual.status == DISCOVERY_STATUS_REVIEW_REQUIRED,
        review_correctly_surfaced=evaluation.review_correctly_surfaced,
        review_missed=evaluation.review_missed,
        grounding_ok=not evaluation.grounding_failures,
        grounding_failures=evaluation.grounding_failures,
        semantic_mismatch=evaluation.semantic_mismatch,
        contract_shape_failure=evaluation.contract_shape_failure,
        target_resolution_mismatch=evaluation.target_resolution_mismatch,
        review_policy_mismatch=evaluation.review_policy_mismatch,
        diagnostics=actual.diagnostics,
        errors=actual.errors,
        expected_effects=expected_effects,
        actual_effects=discovered_effects,
        matched_effects=tuple(
            {"expected_index": expected_idx, "discovered_index": discovered_idx}
            for expected_idx, discovered_idx in matched_pairs
        ),
        false_positive_effects=tuple(discovered_effects[idx] for idx in unmatched_discovered),
        false_negative_effects=tuple(expected_effects[idx] for idx in unmatched_expected),
        provider_name=actual.provider_name,
        provider_version=actual.provider_version,
        provider_contract_version=actual.contract_version,
        provider_model=model_name,
        elapsed_time_ms=elapsed_time_ms,
    )


def _print_case(case_result: CaseRuntimeResult) -> None:
    print(f"CASE {case_result.case_id}")
    print(
        "  status="
        f"{case_result.evaluation_status} expected={case_result.expected_discovery_status} actual={case_result.actual_discovery_status}"
    )
    print(
        "  effects="
        f"expected:{case_result.expected_effect_count} discovered:{case_result.discovered_effect_count} "
        f"matched:{case_result.matched_effect_count} fp:{case_result.false_positive_effect_count} "
        f"fn:{case_result.false_negative_effect_count}"
    )
    print(
        "  review="
        f"expected:{str(case_result.review_expected).lower()} actual:{str(case_result.review_actual).lower()} "
        f"surfaced:{str(case_result.review_correctly_surfaced).lower()} "
        f"missed:{str(case_result.review_missed).lower()}"
    )
    print(
        "  grounding="
        f"{'PASS' if case_result.grounding_ok else 'FAIL'} contract_failures:{len(case_result.contract_shape_failure)} "
        f"target_mismatch:{len(case_result.target_resolution_mismatch)} elapsed_ms:{case_result.elapsed_time_ms}"
    )
    if case_result.errors:
        print("  errors:")
        for error in case_result.errors:
            print(f"    - {error}")


def _build_report(
    *,
    dataset: SourceEffectGoldenDataset,
    model_name: str,
    runtime_results: Sequence[CaseRuntimeResult],
    aggregate: SourceEffectAggregateMetrics,
    started_at_iso: str,
    elapsed_total_ms: int,
    allow_non_frozen: bool,
) -> dict[str, Any]:
    return {
        "run_type": "SOURCE_EFFECT_SEMANTIC_GOLDEN",
        "classification": BASELINE_CLASSIFICATION,
        "dataset": {
            "golden_version": dataset.golden_version,
            "generated_at": dataset.generated_at,
            "tender_id": dataset.tender_id,
            "label_status": dataset.label_status,
            "dataset_status": dataset.dataset_status,
            "integrity_sha256": dataset.integrity_sha256,
            "duplicate_artifact_robustness_dataset": dataset.duplicate_artifact_robustness_dataset,
            "excluded_duplicate_case_ids": list(dataset.excluded_duplicate_case_ids),
            "cases_total": len(dataset.cases),
        },
        "certification_mode": {
            "enabled": not allow_non_frozen,
            "allow_non_frozen": allow_non_frozen,
            "required_dataset_status": DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
            "required_label_status": CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        },
        "provider": {
            "name": "Ollama Source Effect Semantic Discovery",
            "model": model_name,
            "prompt_contract_version": OLLAMA_SOURCE_EFFECT_PROMPT_VERSION,
        },
        "limited_coverage_declaration": {
            "banner": "FROZEN LIMITED-COVERAGE GOLDEN",
            "baseline_only": True,
            "evaluates": [
                "negative_safety",
                "limited_AMENDS",
                "limited_CLARIFIES",
                "limited_PARTIAL",
                "review_surfacing",
                "grounding_contract_compliance",
            ],
            "does_not_certify": [
                "SUPERSEDES",
                "CORRECTS",
                "SUPPLEMENTS",
                "REVOKES",
                "DOCUMENT_WIDE",
                "general_source_effect_recall",
                "automatic_target_resolution",
                "general_source_precedence_accuracy",
            ],
        },
        "aggregate_metrics": {
            "cases_total": aggregate.cases_total,
            "positive_case_count": aggregate.positive_case_count,
            "pass_count": aggregate.pass_count,
            "fail_count": aggregate.fail_count,
            "unlabeled_count": aggregate.unlabeled_count,
            "invalid_count": aggregate.invalid_count,
            "expected_effect_count": aggregate.expected_effect_count,
            "discovered_effect_count": aggregate.discovered_effect_count,
            "matched_effect_count": aggregate.matched_effect_count,
            "false_positive_effect_count": aggregate.false_positive_effect_count,
            "false_negative_effect_count": aggregate.false_negative_effect_count,
            "expected_positive_count": aggregate.expected_positive_count,
            "discovered_positive_count": aggregate.discovered_positive_count,
            "matched_positive_count": aggregate.matched_positive_count,
            "false_positive_count": aggregate.false_positive_count,
            "false_negative_count": aggregate.false_negative_count,
            "precision": aggregate.precision,
            "precision_defined": aggregate.precision_defined,
            "recall": aggregate.recall,
            "review_expected": aggregate.review_expected,
            "review_correctly_surfaced": aggregate.review_correctly_surfaced,
            "review_missed": aggregate.review_missed,
            "hard_negative_count": aggregate.hard_negative_count,
            "hard_negative_pass": aggregate.hard_negative_pass,
            "hard_negative_false_positive": aggregate.hard_negative_false_positive,
            "descriptive_negative_count": aggregate.descriptive_negative_count,
            "descriptive_negative_pass": aggregate.descriptive_negative_pass,
            "grounding_failure_count": aggregate.grounding_failure_count,
            "semantic_mismatch_count": aggregate.semantic_mismatch_count,
            "contract_shape_failure_count": aggregate.contract_shape_failure_count,
            "target_resolution_mismatch_count": aggregate.target_resolution_mismatch_count,
            "review_policy_mismatch_count": aggregate.review_policy_mismatch_count,
        },
        "run_timing": {
            "started_at_utc": started_at_iso,
            "elapsed_total_ms": elapsed_total_ms,
        },
        "cases": [asdict(item) for item in runtime_results],
    }


def run_semantic_golden(
    *,
    golden_path: str,
    model_name: str,
    output_json_path: str | None = None,
    allow_non_frozen: bool = False,
    provider_factory: Callable[..., OllamaSourceEffectDiscoveryProvider] = OllamaSourceEffectDiscoveryProvider,
    discovery_runner: Callable[..., Any] = run_ollama_source_effect_discovery,
    session_factory: Callable[[], Any] | None = None,
    now_utc: str | None = None,
) -> tuple[int, dict[str, Any] | None]:
    dataset = load_source_effect_golden(golden_path)
    validation_errors = list(validate_source_effect_golden(dataset))
    if validation_errors:
        print("GOLDEN_VALIDATION=INVALID")
        for error in validation_errors:
            print(f"- {error}")
        return 2, None

    if not allow_non_frozen:
        certification_errors = _certification_dataset_errors(dataset)
        if certification_errors:
            print("CERTIFICATION_MODE=REJECTED")
            for error in certification_errors:
                print(f"- {error}")
            return 2, None

    provider = provider_factory(model_name=model_name)

    use_session_factory = session_factory or SessionLocal
    evaluations: list[SourceEffectCaseEvaluation] = []
    runtime_results: list[CaseRuntimeResult] = []

    started_at_iso = now_utc or datetime.now(timezone.utc).isoformat()
    context = use_session_factory() if callable(use_session_factory) else nullcontext(None)
    with context as db:
        for case in dataset.cases:
            fragment = _build_fragment(case)
            started_case = time.perf_counter()
            try:
                run = discovery_runner(db, fragment, provider=provider)
                actual_result = run.result
                elapsed_ms = int(getattr(run, "elapsed_time_ms", 0))
                if elapsed_ms <= 0:
                    elapsed_ms = int((time.perf_counter() - started_case) * 1000)
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started_case) * 1000)
                actual_result = _build_invalid_result(
                    provider_name=getattr(provider, "provider_name", "unknown"),
                    provider_version=getattr(provider, "provider_version", "unknown"),
                    contract_version=getattr(provider, "contract_version", "unknown"),
                    error_message=f"provider_exception: {exc}",
                )

            evaluation = evaluate_case(case, actual=actual_result)
            evaluations.append(evaluation)

            case_result = _case_runtime_result(
                case=case,
                evaluation=evaluation,
                actual=actual_result,
                model_name=model_name,
                elapsed_time_ms=elapsed_ms,
            )
            runtime_results.append(case_result)
            _print_case(case_result)

    aggregate = aggregate_evaluations(tuple(evaluations))
    elapsed_total_ms = sum(item.elapsed_time_ms for item in runtime_results)

    print("\nFROZEN LIMITED-COVERAGE GOLDEN")
    print(f"classification={BASELINE_CLASSIFICATION}")
    print(f"cases_total={aggregate.cases_total}")
    print(f"positive_case_count={aggregate.positive_case_count}")
    print(f"pass_count={aggregate.pass_count}")
    print(f"fail_count={aggregate.fail_count}")
    print(f"expected_effect_count={aggregate.expected_effect_count}")
    print(f"discovered_effect_count={aggregate.discovered_effect_count}")
    print(f"matched_effect_count={aggregate.matched_effect_count}")
    print(f"false_positive_effect_count={aggregate.false_positive_effect_count}")
    print(f"false_negative_effect_count={aggregate.false_negative_effect_count}")
    if aggregate.precision_defined and aggregate.precision is not None:
        print(f"precision={aggregate.precision:.4f}")
    else:
        print("precision=N/A (no positive predictions)")
    print(f"precision_defined={str(aggregate.precision_defined).lower()}")
    print(f"recall={aggregate.recall:.4f}")
    print(f"review_expected={aggregate.review_expected}")
    print(f"review_correctly_surfaced={aggregate.review_correctly_surfaced}")
    print(f"review_missed={aggregate.review_missed}")

    report = _build_report(
        dataset=dataset,
        model_name=model_name,
        runtime_results=runtime_results,
        aggregate=aggregate,
        started_at_iso=started_at_iso,
        elapsed_total_ms=elapsed_total_ms,
        allow_non_frozen=allow_non_frozen,
    )

    if output_json_path:
        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output_json={output_path}")

    # Baseline calibration only; no deployment gate in b1.
    return 0, report


def main() -> int:
    args = parse_args()
    exit_code, _ = run_semantic_golden(
        golden_path=str(BACKEND_ROOT / args.golden),
        model_name=args.model,
        output_json_path=str(BACKEND_ROOT / args.output_json) if args.output_json else None,
        allow_non_frozen=bool(args.allow_non_frozen),
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
