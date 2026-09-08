from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

from app.database import SessionLocal
from app.ollama_scope_quantity_provider import OllamaScopeQuantitySemanticDiscoveryProvider, run_ollama_scope_quantity_discovery
from app.scope_quantity_golden import (
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_MODE_NO_QUANTITIES,
    GOLDEN_MODE_REVIEW_REQUIRED,
    GoldenCaseEvaluation,
    ScopeQuantityGoldenCase,
    aggregate_evaluations,
    build_parent_resolver,
    evaluate_case,
    load_scope_quantity_golden,
    validate_scope_quantity_golden,
)
from app.scope_quantity_semantic_discovery import ScopeQuantitySemanticFragment, discover_scope_quantities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic scope quantity Golden evaluation")
    parser.add_argument(
        "--golden",
        default="evals/scope_quantity_golden_v1.json",
        help="Path to scope quantity Golden JSON",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model name for semantic quantity discovery (required only when all labels are APPROVED)",
    )
    return parser.parse_args()


def build_fragment(case: ScopeQuantityGoldenCase) -> ScopeQuantitySemanticFragment:
    return ScopeQuantitySemanticFragment(
        tender_id=case.tender_id,
        scope_detail_id=case.scope_detail_id,
        source_document_id=case.source_document_id,
        document_page_id=case.document_page_id,
        page_number=case.page_number,
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
        source_locator=case.source_locator,
        scope_detail_domain="QUANTITY_GOLDEN",
        scope_detail_description=case.candidate_reason,
        source_text=case.source_text,
        source_contract_version=case.source_contract_version,
        source_analysis_id=case.source_analysis_id,
        source_page_result_id=case.source_page_result_id,
    )


def run_golden(
    *,
    golden_path: str,
    model_name: Optional[str],
    provider_factory=OllamaScopeQuantitySemanticDiscoveryProvider,
) -> int:
    dataset = load_scope_quantity_golden(golden_path)

    with SessionLocal() as db:
        validation = validate_scope_quantity_golden(dataset, parent_resolver=build_parent_resolver(db))

    if not validation.is_valid:
        print("GOLDEN VALIDATION: INVALID")
        for error in validation.errors:
            print(f"  - {error}")
        return 2

    if validation.pending_count > 0:
        print("GOLDEN VALIDATION: PENDING LABELS PRESENT")
        print("Calibration is blocked until all cases are human-approved.")
        print(f"pending_cases={validation.pending_count} approved_cases={validation.approved_count}")
        return 3

    if not str(model_name or "").strip():
        print("GOLDEN VALIDATION: MODEL REQUIRED WHEN ALL LABELS ARE APPROVED")
        return 2

    provider = provider_factory(model_name=str(model_name))

    evaluations: list[GoldenCaseEvaluation] = []
    started_all = time.perf_counter()
    for case in dataset.cases:
        fragment = build_fragment(case)
        started_case = time.perf_counter()
        raw_model_json: Optional[str] = None
        if callable(getattr(provider, "execute", None)):
            executed = run_ollama_scope_quantity_discovery(fragment, provider=provider)
            discovery_result = executed.result
            raw_model_json = executed.raw_model_json
        else:
            discovery_result = discover_scope_quantities(fragment, providers=(provider,))
        elapsed_ms = int((time.perf_counter() - started_case) * 1000)

        evaluation = evaluate_case(case, discovery_result=discovery_result, elapsed_time_ms=elapsed_ms)
        evaluations.append(evaluation)

        print(f"CASE {evaluation.case_id}")
        print(f"  mode={evaluation.evaluation_mode} eval_status={evaluation.evaluation_status}")
        print(f"  discovery_status={evaluation.discovery_status} elapsed_ms={evaluation.elapsed_time_ms}")
        print(
            "  quantities="
            f"expected:{evaluation.expected_count} discovered:{evaluation.discovered_count} matched:{evaluation.matched_count}"
        )
        print(f"  missing_expected={len(evaluation.missing_expected)} unexpected_discovered={len(evaluation.unexpected_discovered)}")
        print(
            "  critical_leakage="
            f"{evaluation.critical_leakage_count} grounding_errors:{evaluation.grounding_error_count} "
            f"contract_validation_errors:{evaluation.contract_validation_error_count}"
        )

        if evaluation.discovery_status == "INVALID_OUTPUT":
            print("  RAW_MODEL_JSON:")
            print(raw_model_json if raw_model_json is not None else "<unavailable>")

        if evaluation.errors:
            print("  errors:")
            for error in evaluation.errors:
                print(f"    - {error}")

    total_elapsed_ms = int((time.perf_counter() - started_all) * 1000)
    aggregate = aggregate_evaluations(evaluations)

    print("\nAGGREGATE")
    print(f"  cases_total={aggregate.cases_total}")
    print(
        "  status_counts="
        f"PASS:{aggregate.pass_count} FAIL:{aggregate.fail_count} REVIEW_REQUIRED:{aggregate.review_required_count} "
        f"UNLABELED:{aggregate.unlabeled_count} INVALID:{aggregate.invalid_count}"
    )
    print("  discovery_status_distribution=")
    for key, value in aggregate.discovery_status_counts:
        print(f"    - {key}: {value}")
    print(
        "  quantities="
        f"expected:{aggregate.expected_quantity_count} discovered:{aggregate.discovered_quantity_count} matched:{aggregate.matched_quantity_count}"
    )
    print(
        "  deltas="
        f"missing_expected:{aggregate.missing_expected_count} unexpected_discovered:{aggregate.unexpected_discovered_count}"
    )
    print(f"  precision={aggregate.precision:.4f} recall={aggregate.recall:.4f}")
    print(
        "  hard_negative="
        f"pass:{aggregate.hard_negative_pass_count} total:{aggregate.hard_negative_total_count}"
    )
    print(
        "  mixed_context="
        f"pass:{aggregate.mixed_context_pass_count} total:{aggregate.mixed_context_total_count}"
    )
    print(
        "  critical="
        f"technical_leakage:{aggregate.critical_technical_leakage_count} grounding_errors:{aggregate.grounding_error_count} "
        f"contract_validation_errors:{aggregate.contract_validation_error_count} invalid_output:{aggregate.invalid_output_count}"
    )
    print(
        "  timing_ms="
        f"total:{total_elapsed_ms} avg:{aggregate.average_elapsed_time_ms:.2f} max:{aggregate.max_elapsed_time_ms}"
    )

    if aggregate.invalid_count > 0:
        return 4
    if aggregate.fail_count > 0:
        return 5

    if any(
        eval_case.evaluation_mode == GOLDEN_MODE_NO_QUANTITIES and eval_case.evaluation_status != GOLDEN_EVAL_STATUS_PASS
        for eval_case in evaluations
    ):
        return 6

    if any(
        eval_case.evaluation_mode == GOLDEN_MODE_REVIEW_REQUIRED and eval_case.evaluation_status != GOLDEN_EVAL_STATUS_PASS
        for eval_case in evaluations
    ):
        return 7

    return 0


def main() -> int:
    args = parse_args()
    golden_path = str(Path(args.golden))
    return run_golden(golden_path=golden_path, model_name=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
