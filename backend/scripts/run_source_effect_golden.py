#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.source_effect_adapters import resolve_source_effect_evidence_artifact
from app.source_effect_deterministic import discover_source_effects_from_evidence
from app.source_effect_golden import (
    DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
    aggregate_evaluations,
    evaluate_case,
    load_source_effect_golden,
    validate_source_effect_golden,
)
from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SourceEffectSemanticDiscoveryResult,
)


def _map_status(status: str) -> str:
    mapping = {
        "MATERIALIZED": "DISCOVERED",
        "NO_EFFECTS": "NO_EFFECTS",
        "REVIEW_REQUIRED": "REVIEW_REQUIRED",
        "UNSUPPORTED": "UNSUPPORTED",
        "INVALID_EVIDENCE": "INVALID_OUTPUT",
    }
    return mapping.get(status, "INVALID_OUTPUT")


def _deterministic_actual(db: Session, case) -> SourceEffectSemanticDiscoveryResult:
    artifact = resolve_source_effect_evidence_artifact(
        db,
        tender_id=case.tender_id,
        acting_document_id=case.acting_document_id,
        document_page_id=case.document_page_id,
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
    )
    result = discover_source_effects_from_evidence(db, artifact)
    discovered = tuple(
        DiscoveredSourceEffect(
            effect_type=item.effect_type,
            effect_scope=item.effect_scope,
            affected_document_ref_raw=item.affected_document_ref_raw,
            affected_locator_raw=item.affected_locator_raw,
            effective_date_raw=item.effective_date_raw,
            evidence_excerpt=item.source_excerpt,
            confidence=item.confidence,
        )
        for item in result.candidates
    )

    return SourceEffectSemanticDiscoveryResult(
        provider_name="deterministic",
        provider_version="source-effect-deterministic",
        contract_version="source-effect-semantic-discovery-2026-09-08-001",
        status=_map_status(result.status),
        candidate_count=len(discovered),
        review_required_count=sum(1 for item in result.candidates if item.review_required),
        candidates=(),
        discovered_effects=discovered,
        diagnostics=result.diagnostics,
        errors=result.errors,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run source-effect golden candidate evaluation")
    parser.add_argument(
        "--golden",
        default="evals/source_effect_golden_v1.json",
        help="Path to source-effect golden JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_source_effect_golden(BACKEND_ROOT / args.golden)
    errors = validate_source_effect_golden(dataset)
    if errors:
        print("GOLDEN_VALIDATION=INVALID")
        for error in errors:
            print(f"- {error}")
        return 2

    evaluations = []
    with SessionLocal() as db:
        for case in dataset.cases:
            actual = _deterministic_actual(db, case)
            evaluation = evaluate_case(case, actual=actual)
            evaluations.append(evaluation)
            print(f"CASE {case.case_id} expected={evaluation.expected_discovery_status} actual={evaluation.actual_discovery_status} eval={evaluation.evaluation_status}")

    aggregate = aggregate_evaluations(tuple(evaluations))
    if dataset.dataset_status == DATASET_STATUS_FROZEN_LIMITED_COVERAGE:
        print("DETERMINISTIC BASELINE METRICS (FROZEN_LIMITED_COVERAGE)")
    else:
        print("DETERMINISTIC BASELINE METRICS")
    print(f"cases_total={aggregate.cases_total}")
    print(f"positive_case_count={aggregate.positive_case_count}")
    print(f"pass_count={aggregate.pass_count}")
    print(f"fail_count={aggregate.fail_count}")
    print(f"unlabeled_count={aggregate.unlabeled_count}")
    print(f"invalid_count={aggregate.invalid_count}")

    print("# effect-level metrics")
    print(f"expected_effect_count={aggregate.expected_effect_count}")
    print(f"discovered_effect_count={aggregate.discovered_effect_count}")
    print(f"matched_effect_count={aggregate.matched_effect_count}")
    print(f"false_positive_effect_count={aggregate.false_positive_effect_count}")
    print(f"false_negative_effect_count={aggregate.false_negative_effect_count}")

    print("# legacy compatibility fields (effect-level semantics)")
    print(f"expected_positive_count={aggregate.expected_positive_count}")
    print(f"discovered_positive_count={aggregate.discovered_positive_count}")
    print(f"matched_positive_count={aggregate.matched_positive_count}")
    print(f"false_positive_count={aggregate.false_positive_count}")
    print(f"false_negative_count={aggregate.false_negative_count}")

    if aggregate.precision_defined and aggregate.precision is not None:
        print(f"precision={aggregate.precision:.4f}")
    else:
        print("precision=N/A (no positive predictions)")
    print(f"precision_defined={str(aggregate.precision_defined).lower()}")
    print(f"recall={aggregate.recall:.4f}")
    print(f"review_expected={aggregate.review_expected}")
    print(f"review_correctly_surfaced={aggregate.review_correctly_surfaced}")
    print(f"review_missed={aggregate.review_missed}")
    print(f"hard_negative_count={aggregate.hard_negative_count}")
    print(f"hard_negative_pass={aggregate.hard_negative_pass}")
    print(f"hard_negative_false_positive={aggregate.hard_negative_false_positive}")
    print(f"descriptive_negative_count={aggregate.descriptive_negative_count}")
    print(f"descriptive_negative_pass={aggregate.descriptive_negative_pass}")
    print(f"grounding_failure_count={aggregate.grounding_failure_count}")
    print(f"semantic_mismatch_count={aggregate.semantic_mismatch_count}")
    print(f"contract_shape_failure_count={aggregate.contract_shape_failure_count}")
    print(f"target_resolution_mismatch_count={aggregate.target_resolution_mismatch_count}")
    print(f"review_policy_mismatch_count={aggregate.review_policy_mismatch_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
