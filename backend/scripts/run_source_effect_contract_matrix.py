#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CASE_TO_PYTEST_NODEID = {
    "cm_001_single_document_wide_supersedes": "tests/test_source_effect_resolution.py::test_single_supersedes_marks_target_superseded_with_replacement",
    "cm_002_pure_supersession_chain": "tests/test_source_effect_resolution.py::test_pure_supersedes_chain_resolves_ultimate_replacement",
    "cm_003_single_revokes": "tests/test_source_effect_resolution.py::test_single_revokes_marks_target_revoked_without_replacement",
    "cm_004_branching_supersedes": "tests/test_source_effect_resolution.py::test_branching_supersedes_conflict_sets_review_required",
    "cm_005_supersedes_vs_revokes": "tests/test_source_effect_resolution.py::test_terminal_type_conflict_supersedes_vs_revokes",
    "cm_006_cycle": "tests/test_source_effect_resolution.py::test_supersession_cycle_marks_involved_documents_review_required",
    "cm_007_review_required_dependency": "tests/test_source_effect_resolution.py::test_review_required_effect_with_resolved_target_blocks_document",
    "cm_008_no_revival": "tests/test_source_effect_resolution.py::test_no_revival_when_replacement_is_revoked",
    "cm_009_single_partial_supersedes": "tests/test_source_effect_partial_resolution.py::test_single_partial_supersedes_sets_effective_source_document",
    "cm_010_single_partial_revokes": "tests/test_source_effect_partial_resolution.py::test_single_partial_revokes_sets_locator_revoked",
    "cm_011_partial_branching": "tests/test_source_effect_partial_resolution.py::test_terminal_branching_partial_supersedes_is_review_required",
    "cm_012_partial_terminal_conflict": "tests/test_source_effect_partial_resolution.py::test_partial_supersedes_vs_revokes_conflict_is_review_required",
    "cm_013_superseded_acting_source": "tests/test_source_effect_partial_resolution.py::test_superseded_acting_document_blocks_partial_supersedes",
    "cm_014_parent_child_projection_terminal_conflict": "tests/test_effective_source_projection.py::test_attribute_parent_superseded_child_revoked_conflict_is_review_required",
    "cm_015_unresolved_and_overlay_propagation": "tests/test_effective_source_projection.py::test_parent_unresolved_source_blocks_effective_child",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic source-effect contract matrix")
    parser.add_argument(
        "--matrix",
        default="evals/source_effect_synthetic_contract_matrix_v1.json",
        help="Path to synthetic contract matrix JSON",
    )
    parser.add_argument(
        "--python",
        default="/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        help="Python executable for pytest",
    )
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test",
        help="Database URL for pytest",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend_root = Path(__file__).resolve().parents[1]
    matrix_path = backend_root / args.matrix
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))

    passed = 0
    failed = 0
    missing = 0

    print(f"contract_version={payload.get('contract_version')}")

    for case in payload.get("cases", []):
        case_id = case["case_id"]
        nodeid = CASE_TO_PYTEST_NODEID.get(case_id)
        if not nodeid:
            print(f"CASE {case_id}: MISSING_NODEID")
            missing += 1
            continue

        command = [args.python, "-m", "pytest", "-q", nodeid]
        completed = subprocess.run(
            command,
            cwd=str(backend_root),
            env={**dict(**__import__("os").environ), "DATABASE_URL": args.database_url},
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            print(f"CASE {case_id}: PASS")
            passed += 1
        else:
            print(f"CASE {case_id}: FAIL")
            print(completed.stdout.strip())
            print(completed.stderr.strip())
            failed += 1

    total = len(payload.get("cases", []))
    print(f"contract_cases_total={total}")
    print(f"contract_cases_passed={passed}")
    print(f"contract_cases_failed={failed + missing}")

    return 0 if failed == 0 and missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
