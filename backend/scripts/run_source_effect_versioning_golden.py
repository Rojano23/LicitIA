#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.source_effect_versioning_golden import (
    load_source_effect_versioning_golden,
    run_result_to_json,
    run_source_effect_versioning_golden,
    validate_source_effect_versioning_golden,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run controlled synthetic source-effect versioning golden"
    )
    parser.add_argument(
        "--golden",
        default="evals/source_effect_versioning_golden_v1.json",
        help="Path to controlled versioning golden dataset",
    )
    parser.add_argument(
        "--python",
        default="/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        help="Compatibility argument (unused by data-driven evaluator)",
    )
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test",
        help="Database URL used by synthetic fixture runs",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output report path",
    )
    return parser.parse_args()


def _print_sorted_map(prefix: str, values: dict[str, int]) -> None:
    for key in sorted(values):
        print(f"{prefix}{key}={values[key]}")


def main() -> int:
    args = parse_args()
    golden_path = BACKEND_ROOT / args.golden
    dataset = load_source_effect_versioning_golden(golden_path)

    validation_errors = validate_source_effect_versioning_golden(dataset)
    if validation_errors:
        print("dataset_validation=FAIL")
        for err in validation_errors:
            print(f"dataset_error={err}")
        return 1

    result = run_source_effect_versioning_golden(
        dataset=dataset,
        python_executable=args.python,
        backend_root=BACKEND_ROOT,
        database_url=args.database_url,
    )

    print(f"dataset_kind={result.dataset_kind}")
    print(f"dataset_status={result.dataset_status}")
    print(f"case_count={result.cases_total}")
    print(f"pass_count={result.cases_passed}")
    print(f"fail_count={result.cases_failed}")

    _print_sorted_map("coverage_effect_type_", result.coverage_effect_type)
    _print_sorted_map("coverage_scope_", result.coverage_effect_scope)
    _print_sorted_map("coverage_layer_", result.coverage_resolver_layer)

    print(f"conflict_cases={result.conflict_case_count}")
    print(f"projection_cases={result.projection_case_count}")

    for case_result in result.case_results:
        status = "PASS" if case_result.passed else "FAIL"
        print(
            f"case:{case_result.case_id}:{status}:"
            f"checks_passed={case_result.checks_passed}:"
            f"checks_failed={case_result.checks_failed}:"
            f"read_only_verified={case_result.read_only_verified}"
        )
        if not case_result.passed:
            for failure in case_result.failure_messages:
                print(f"failure={failure}")

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.write_text(json.dumps(run_result_to_json(result), indent=2), encoding="utf-8")
        print(f"output_json={output_path}")

    return 0 if result.cases_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
