from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.database import SessionLocal
from app.ollama_scope_attribute_provider import OllamaScopeAttributeSemanticDiscoveryProvider
from app.scope_attribute_golden import (
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_MODE_NO_ATTRIBUTES,
    GoldenCase,
    aggregate_evaluations,
    build_parent_resolver,
    evaluate_case,
    load_technical_attribute_golden,
    validate_technical_attribute_golden,
)
from app.scope_attribute_semantic_discovery import ScopeAttributeSemanticFragment, discover_scope_attributes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run technical attribute Golden evaluation")
    parser.add_argument(
        "--golden",
        default="evals/technical_attribute_golden_v1.json",
        help="Path to technical attribute Golden JSON file",
    )
    parser.add_argument("--model", required=True, help="Ollama model name for semantic attribute discovery")
    return parser.parse_args()


def build_fragment(case: GoldenCase) -> ScopeAttributeSemanticFragment:
    return ScopeAttributeSemanticFragment(
        tender_id=case.tender_id,
        scope_detail_id=case.scope_detail_id,
        source_document_id=case.source_document_id,
        document_page_id=case.document_page_id,
        page_number=case.page_number,
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
        source_locator=case.source_locator,
        scope_detail_domain="TECHNICAL_ATTRIBUTE",
        scope_detail_description=case.candidate_reason,
        source_text=case.source_text,
        source_contract_version=case.source_contract_version,
    )


def run_golden(
    *,
    golden_path: str,
    model_name: str,
    provider_factory=OllamaScopeAttributeSemanticDiscoveryProvider,
) -> int:
    dataset = load_technical_attribute_golden(golden_path)

    with SessionLocal() as db:
        validation = validate_technical_attribute_golden(dataset, parent_resolver=build_parent_resolver(db))

    if not validation.is_valid:
        print("GOLDEN VALIDATION: INVALID")
        for error in validation.errors:
            print(f"  - {error}")
        return 2

    if validation.pending_count > 0:
        print("GOLDEN VALIDATION: PENDING LABELS PRESENT")

    provider = provider_factory(model_name=model_name)

    evaluations = []
    started_all = time.perf_counter()
    for case in dataset.cases:
        fragment = build_fragment(case)
        started = time.perf_counter()
        result = discover_scope_attributes(fragment, providers=(provider,))
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        evaluation = evaluate_case(case, discovery_result=result, elapsed_time_ms=elapsed_ms)
        evaluations.append(evaluation)

        print(f"CASE {evaluation.case_id}")
        print(f"  mode={evaluation.evaluation_mode} status={evaluation.evaluation_status}")
        print(f"  discovery_status={evaluation.discovery_status} elapsed_ms={evaluation.elapsed_time_ms}")
        print(f"  expected={evaluation.expected_count} discovered={evaluation.discovered_count} matched={evaluation.matched_count}")

        print("  expected_attributes:")
        if not evaluation.expected_attributes:
            print("    - (none)")
        for attr in evaluation.expected_attributes:
            print(
                "    - "
                f"{attr.attribute_name} value='{attr.value_raw}' unit='{attr.unit_raw}' relation='{attr.relation}' evidence='{attr.evidence_excerpt}'"
            )

        print("  discovered_attributes:")
        if not evaluation.discovered_attributes:
            print("    - (none)")
        for attr in evaluation.discovered_attributes:
            print(
                "    - "
                f"{attr.attribute_name} value='{attr.value_raw}' unit='{attr.unit_raw}' relation='{attr.relation}' evidence='{attr.evidence_excerpt}'"
            )

        print("  missing_expected:")
        if not evaluation.missing_expected:
            print("    - (none)")
        for attr in evaluation.missing_expected:
            print(f"    - {attr.golden_attribute_id} {attr.attribute_name} value='{attr.value_raw}'")

        print("  unexpected_discovered:")
        if not evaluation.unexpected_discovered:
            print("    - (none)")
        for attr in evaluation.unexpected_discovered:
            print(f"    - {attr.attribute_name} value='{attr.value_raw}'")

        if evaluation.errors:
            print("  errors:")
            for error in evaluation.errors:
                print(f"    - {error}")

    total_elapsed_ms = int((time.perf_counter() - started_all) * 1000)
    aggregate = aggregate_evaluations(evaluations)

    print("\nAGGREGATE")
    print(f"  cases_total={aggregate.total_cases}")
    print(
        "  status_counts="
        f"PASS:{aggregate.pass_count} FAIL:{aggregate.fail_count} REVIEW_REQUIRED:{aggregate.review_required_count} "
        f"UNLABELED:{aggregate.unlabeled_count} INVALID:{aggregate.invalid_count}"
    )
    print("  discovery_status_counts=")
    for key, count in aggregate.discovery_status_counts:
        print(f"    - {key}: {count}")
    print(
        "  attributes="
        f"expected:{aggregate.total_expected_attributes} discovered:{aggregate.total_discovered_attributes} matched:{aggregate.total_matched_attributes}"
    )
    print(f"  precision={aggregate.overall_precision:.4f} recall={aggregate.overall_recall:.4f}")
    print(
        "  hard_negatives="
        f"pass:{aggregate.hard_negative_pass_count} total:{aggregate.hard_negative_total_count}"
    )
    print(
        "  deltas="
        f"missing_expected:{aggregate.missing_expected_count} unexpected_discovered:{aggregate.unexpected_discovered_count}"
    )
    print(
        "  timing_ms="
        f"total:{total_elapsed_ms} avg:{aggregate.average_elapsed_time_ms:.2f} max:{aggregate.max_elapsed_time_ms}"
    )

    if validation.pending_count > 0:
        return 3
    if aggregate.invalid_count > 0:
        return 4
    if aggregate.fail_count > 0:
        return 5

    # PASS includes strict and hard-negative successes only.
    if any(e.evaluation_mode == GOLDEN_MODE_NO_ATTRIBUTES and e.evaluation_status != GOLDEN_EVAL_STATUS_PASS for e in evaluations):
        return 6

    return 0


def main() -> int:
    args = parse_args()
    golden_path = str(Path(args.golden))
    return run_golden(golden_path=golden_path, model_name=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
