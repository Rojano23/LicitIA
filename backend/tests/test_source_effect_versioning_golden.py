from __future__ import annotations

from pathlib import Path

from app.source_effect_versioning_golden import (
    DATASET_KIND_CONTROLLED_SYNTHETIC_VERSIONING,
    DATASET_STATUS_FROZEN_CONTRACT_VALIDATION,
    REQUIRED_CASE_IDS,
    _scenario_for_case,
    compute_versioning_coverage,
    load_source_effect_versioning_golden,
    run_source_effect_versioning_golden,
    validate_source_effect_versioning_golden,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = BACKEND_ROOT / "evals" / "source_effect_versioning_golden_v1.json"
TEST_DB_URL = "postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test"


def test_versioning_golden_dataset_contract_and_coverage() -> None:
    dataset = load_source_effect_versioning_golden(DATASET_PATH)

    assert dataset.dataset_kind == DATASET_KIND_CONTROLLED_SYNTHETIC_VERSIONING
    assert dataset.dataset_status == DATASET_STATUS_FROZEN_CONTRACT_VALIDATION

    errors = validate_source_effect_versioning_golden(dataset)
    assert errors == ()

    case_ids = {case.case_id for case in dataset.cases}
    assert case_ids == REQUIRED_CASE_IDS

    effect_type_coverage, scope_coverage, layer_coverage, conflict_count, projection_count = compute_versioning_coverage(dataset)
    for effect_type in ("SUPERSEDES", "AMENDS", "CORRECTS", "CLARIFIES", "SUPPLEMENTS", "REVOKES"):
        assert effect_type_coverage.get(effect_type, 0) >= 1
    assert scope_coverage.get("DOCUMENT_WIDE", 0) >= 1
    assert scope_coverage.get("PARTIAL", 0) >= 1
    assert scope_coverage.get("UNRESOLVED", 0) >= 1
    assert layer_coverage.get("DOCUMENT", 0) >= 1
    assert layer_coverage.get("PARTIAL", 0) >= 1
    assert layer_coverage.get("PROJECTION", 0) >= 1
    assert conflict_count >= 1
    assert projection_count >= 1


def test_versioning_golden_checks_all_projection_entity_types() -> None:
    dataset = load_source_effect_versioning_golden(DATASET_PATH)
    checked_types = set()
    for case in dataset.cases:
        scenario = _scenario_for_case(case.case_id)
        checked_aliases = {
            check["entity"] for check in scenario.checks
            if check["op"] == "projection_status"
        }
        checked_types.update(
            entity.entity_type for entity in scenario.entities
            if entity.alias in checked_aliases
        )
    assert checked_types == {"REQUIREMENT", "SCOPE_DETAIL", "SCOPE_ATTRIBUTE", "SCOPE_QUANTITY"}


def test_versioning_golden_data_driven_full_passes() -> None:
    dataset = load_source_effect_versioning_golden(DATASET_PATH)
    result = run_source_effect_versioning_golden(
        dataset=dataset,
        python_executable="/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        backend_root=BACKEND_ROOT,
        database_url=TEST_DB_URL,
    )

    assert result.cases_total == len(REQUIRED_CASE_IDS)
    assert result.cases_failed == 0
    assert result.cases_passed == result.cases_total

    for case_result in result.case_results:
        assert case_result.passed
        assert case_result.read_only_verified
        assert case_result.checks_failed == 0


def test_versioning_golden_data_driven_is_idempotent() -> None:
    dataset = load_source_effect_versioning_golden(DATASET_PATH)

    first = run_source_effect_versioning_golden(
        dataset=dataset,
        python_executable="/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        backend_root=BACKEND_ROOT,
        database_url=TEST_DB_URL,
    )
    second = run_source_effect_versioning_golden(
        dataset=dataset,
        python_executable="/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        backend_root=BACKEND_ROOT,
        database_url=TEST_DB_URL,
    )

    assert first.cases_failed == 0
    assert second.cases_failed == 0

    first_by_id = {item.case_id: item for item in first.case_results}
    second_by_id = {item.case_id: item for item in second.case_results}

    assert set(first_by_id.keys()) == set(second_by_id.keys())
    for case_id in first_by_id:
        one = first_by_id[case_id]
        two = second_by_id[case_id]
        assert one.passed == two.passed
        assert one.checks_total == two.checks_total
        assert one.checks_passed == two.checks_passed
        assert one.checks_failed == two.checks_failed
        assert one.read_only_verified == two.read_only_verified
