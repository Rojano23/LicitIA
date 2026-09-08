from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from app.scope_quantity_golden import (
    GOLDEN_EVAL_STATUS_FAIL,
    GOLDEN_EVAL_STATUS_INVALID,
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_LABEL_APPROVED,
    GOLDEN_LABEL_PENDING,
    GOLDEN_MODE_NO_QUANTITIES,
    GOLDEN_MODE_REVIEW_REQUIRED,
    GOLDEN_MODE_STRICT,
    GoldenExpectedQuantity,
    GoldenQuantityParentSnapshot,
    ScopeQuantityGoldenCase,
    ScopeQuantityGoldenDataset,
    aggregate_evaluations,
    evaluate_case,
    load_scope_quantity_golden,
    validate_scope_quantity_golden,
)
from app.scope_quantities import ScopeQuantityCandidate
from app.scope_quantity_semantic_discovery import ScopeQuantitySemanticDiscoveryResult


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _approved_strict_case() -> ScopeQuantityGoldenCase:
    source = "• MÓDULO X, MODELO: PW481-50 (1 PIEZA), ENTRADA 100-120VCA"
    expected = (
        GoldenExpectedQuantity(
            golden_quantity_id="gq-001",
            quantity_raw="1",
            unit_raw="PIEZA",
            measure_kind="COUNT",
            relation="EXACT",
            quantity_value_raw="1",
            quantity_min_raw=None,
            quantity_max_raw=None,
            evidence_excerpt="(1 PIEZA)",
        ),
    )
    return ScopeQuantityGoldenCase(
        case_id="sq_case_001",
        golden_version="scope-quantity-golden-2026-09-08-001",
        human_label_status=GOLDEN_LABEL_APPROVED,
        evaluation_mode=GOLDEN_MODE_STRICT,
        tender_id="tender-1",
        scope_detail_id="scope-1",
        source_document_id="doc-1",
        document_page_id="page-1",
        page_number=4,
        source_method="VISION",
        source_artifact_key="vision-page-result:1",
        source_locator="page:4|detail_row:0",
        source_text=source,
        source_text_sha256=_sha256(source),
        expected_quantities=expected,
        forbidden_quantity_literals=("100-120VCA", "PW481-50"),
        coverage_tags=("COUNT", "MIXED_TECHNICAL_NUMBER"),
        candidate_reason="real row",
        source_contract_version="vision-detail-transcription-2026-08-31-001",
        source_analysis_id="analysis-1",
        source_page_result_id="page-result-1",
    )


def _resolver_for(case: ScopeQuantityGoldenCase):
    def _resolver(_: ScopeQuantityGoldenCase):
        return GoldenQuantityParentSnapshot(
            scope_detail_id=case.scope_detail_id,
            tender_id=case.tender_id,
            source_document_id=case.source_document_id,
            document_page_id=case.document_page_id,
            page_number=case.page_number,
            source_method=case.source_method,
            source_artifact_key=case.source_artifact_key,
            source_locator=case.source_locator,
            source_excerpt=case.source_text,
            source_contract_version=case.source_contract_version,
            source_analysis_id=case.source_analysis_id,
            source_page_result_id=case.source_page_result_id,
        )

    return _resolver


def _discovery(
    *,
    status: str,
    candidates: tuple[ScopeQuantityCandidate, ...],
    errors: tuple[str, ...] = (),
) -> ScopeQuantitySemanticDiscoveryResult:
    return ScopeQuantitySemanticDiscoveryResult(
        provider_name="fake",
        provider_version="fake-v1",
        contract_version="fake-contract",
        status=status,
        candidate_count=len(candidates),
        review_required_count=sum(1 for item in candidates if item.review_required),
        candidates=candidates,
        discovered_quantities=(),
        errors=errors,
    )


def _candidate_from(case: ScopeQuantityGoldenCase, *, quantity_raw: str = "1") -> ScopeQuantityCandidate:
    return ScopeQuantityCandidate(
        tender_id=case.tender_id,
        scope_detail_id=case.scope_detail_id,
        source_document_id=case.source_document_id,
        document_page_id=case.document_page_id,
        quantity_raw=quantity_raw,
        quantity_value=1,
        quantity_min=None,
        quantity_max=None,
        unit_raw="PIEZA",
        measure_kind="COUNT",
        relation="EXACT",
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
        source_locator=case.source_locator,
        source_excerpt="(1 PIEZA)",
        review_required=True,
        confidence=None,
        source_contract_version=case.source_contract_version,
        source_analysis_id=case.source_analysis_id,
        source_page_result_id=case.source_page_result_id,
    )


def test_load_scope_quantity_golden_json_round_trip(tmp_path: Path) -> None:
    payload = {
        "golden_version": "scope-quantity-golden-2026-09-08-001",
        "generated_at": "2026-09-08T00:00:00Z",
        "notes": "x",
        "cases": [
            {
                "case_id": "sq_case_001",
                "golden_version": "scope-quantity-golden-2026-09-08-001",
                "human_label_status": "PENDING",
                "evaluation_mode": "NO_QUANTITIES",
                "tender_id": "tender-1",
                "scope_detail_id": "scope-1",
                "source_document_id": "doc-1",
                "document_page_id": "page-1",
                "page_number": 4,
                "source_method": "VISION",
                "source_artifact_key": "vision-page-result:1",
                "source_locator": "page:4|detail_row:0",
                "source_text": "SIN CANTIDAD",
                "source_text_sha256": "fba5e9965af3530456bfda1f295f1f13004db645e7f670d39f688b1339f2fbd2",
                "expected_quantities": [],
                "candidate_reason": "test",
            }
        ],
    }
    path = tmp_path / "scope_quantity_golden.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    dataset = load_scope_quantity_golden(path)

    assert dataset.golden_version == payload["golden_version"]
    assert len(dataset.cases) == 1
    assert dataset.cases[0].human_label_status == GOLDEN_LABEL_PENDING


def test_validate_pending_dataset_is_structurally_valid() -> None:
    case = replace(_approved_strict_case(), human_label_status=GOLDEN_LABEL_PENDING)
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset, parent_resolver=_resolver_for(case))

    assert result.is_valid is True
    assert result.pending_count == 1
    assert result.approved_count == 0


def test_validate_approved_dataset_is_structurally_valid() -> None:
    case = _approved_strict_case()
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset, parent_resolver=_resolver_for(case))

    assert result.is_valid is True
    assert result.approved_count == 1
    assert result.pending_count == 0


def test_validate_rejects_duplicate_case_id() -> None:
    case = _approved_strict_case()
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case, replace(case, golden_version="scope-quantity-golden-2026-09-08-001")),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("duplicate case_id" in error for error in result.errors)


def test_validate_rejects_duplicate_golden_quantity_id() -> None:
    case_1 = _approved_strict_case()
    case_2 = replace(
        _approved_strict_case(),
        case_id="sq_case_002",
        scope_detail_id="scope-2",
        source_locator="page:4|detail_row:1",
    )
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case_1, case_2),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("duplicate golden_quantity_id" in error for error in result.errors)


def test_validate_rejects_invalid_mode_and_human_status() -> None:
    case = replace(_approved_strict_case(), evaluation_mode="BAD_MODE", human_label_status="AUTO")
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("unsupported evaluation_mode" in error for error in result.errors)
    assert any("unsupported human_label_status" in error for error in result.errors)


def test_validate_rejects_empty_source_and_bad_sha() -> None:
    case = replace(_approved_strict_case(), source_text="", source_text_sha256="abc")
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("source_text is required" in error for error in result.errors)
    assert any("invalid source_text_sha256" in error for error in result.errors)


def test_validate_rejects_bad_quantity_and_unit_grounding() -> None:
    bad = GoldenExpectedQuantity(
        golden_quantity_id="gq-010",
        quantity_raw="2",
        unit_raw="PIEZA",
        measure_kind="COUNT",
        relation="EXACT",
        quantity_value_raw="2",
        evidence_excerpt="(1 PIEZA)",
    )
    case = replace(_approved_strict_case(), expected_quantities=(bad,))
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("quantity_raw is not grounded" in error for error in result.errors)


def test_validate_rejects_unknown_measure_kind_and_relation() -> None:
    bad = replace(_approved_strict_case().expected_quantities[0], measure_kind="UNKNOWN", relation="SIDEWAYS")
    case = replace(_approved_strict_case(), expected_quantities=(bad,))
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("unsupported measure_kind" in error for error in result.errors)
    assert any("unsupported relation" in error for error in result.errors)


def test_validate_rejects_invalid_numeric_strings_and_range_shape() -> None:
    bad = replace(
        _approved_strict_case().expected_quantities[0],
        relation="RANGE",
        quantity_value_raw="1,2",
        quantity_min_raw="2",
        quantity_max_raw="1",
    )
    case = replace(_approved_strict_case(), expected_quantities=(bad,))
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("invalid numeric string" in error for error in result.errors)
    assert any("RANGE forbids quantity_value_raw" in error for error in result.errors)
    assert any("RANGE requires min<=max" in error for error in result.errors)


def test_parent_recovery_missing_and_mismatches_rejected() -> None:
    case = _approved_strict_case()
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    missing = validate_scope_quantity_golden(dataset, parent_resolver=lambda _: None)
    assert missing.is_valid is False
    assert any("scope_detail not found" in error for error in missing.errors)

    bad_parent = GoldenQuantityParentSnapshot(
        scope_detail_id=case.scope_detail_id,
        tender_id="other-tender",
        source_document_id=case.source_document_id,
        document_page_id="other-page",
        page_number=99,
        source_method=case.source_method,
        source_artifact_key="other-artifact",
        source_locator="page:4|detail_row:777",
        source_excerpt="other",
        source_contract_version=case.source_contract_version,
        source_analysis_id="wrong-analysis",
        source_page_result_id="wrong-page-result",
    )

    mismatch = validate_scope_quantity_golden(dataset, parent_resolver=lambda _: bad_parent)
    assert mismatch.is_valid is False
    assert any("tender_id mismatch" in error for error in mismatch.errors)
    assert any("document_page_id mismatch" in error for error in mismatch.errors)
    assert any("source_analysis_id mismatch" in error for error in mismatch.errors)


def test_forbidden_literal_must_be_grounded() -> None:
    case = replace(_approved_strict_case(), forbidden_quantity_literals=("NOT_IN_SOURCE",))
    dataset = ScopeQuantityGoldenDataset(
        golden_version="scope-quantity-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    result = validate_scope_quantity_golden(dataset)

    assert result.is_valid is False
    assert any("forbidden literal not grounded" in error for error in result.errors)


def test_strict_perfect_pass() -> None:
    case = _approved_strict_case()
    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(_candidate_from(case),)),
        elapsed_time_ms=5,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert result.matched_count == 1
    assert len(result.missing_expected) == 0
    assert len(result.unexpected_discovered) == 0


def test_missing_expected_and_unexpected_fail() -> None:
    case = _approved_strict_case()
    wrong = replace(_candidate_from(case), quantity_value=9)
    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(wrong,)),
        elapsed_time_ms=5,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_FAIL
    assert len(result.missing_expected) == 1
    assert len(result.unexpected_discovered) == 1


def test_no_quantities_pass_and_fail() -> None:
    case = replace(
        _approved_strict_case(),
        case_id="sq_case_noq",
        evaluation_mode=GOLDEN_MODE_NO_QUANTITIES,
        expected_quantities=(),
        forbidden_quantity_literals=(),
        coverage_tags=("HARD_NEGATIVE",),
    )

    passed = evaluate_case(case, discovery_result=_discovery(status="NO_QUANTITIES", candidates=()), elapsed_time_ms=1)
    failed = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(_candidate_from(_approved_strict_case()),)),
        elapsed_time_ms=1,
    )

    assert passed.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert failed.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_review_required_mode_deterministic_behavior() -> None:
    case = replace(
        _approved_strict_case(),
        case_id="sq_case_review",
        evaluation_mode=GOLDEN_MODE_REVIEW_REQUIRED,
        expected_quantities=(),
        coverage_tags=("DELIVERABLE",),
    )

    passed = evaluate_case(case, discovery_result=_discovery(status="REVIEW_REQUIRED", candidates=()), elapsed_time_ms=1)
    failed = evaluate_case(case, discovery_result=_discovery(status="NO_QUANTITIES", candidates=()), elapsed_time_ms=1)

    assert passed.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert failed.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_duplicate_discovered_cannot_double_match() -> None:
    case = _approved_strict_case()
    c1 = _candidate_from(case)
    c2 = _candidate_from(case)

    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(c1, c2)),
        elapsed_time_ms=1,
    )

    assert result.matched_count == 1
    assert len(result.unexpected_discovered) == 1
    assert result.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_evidence_span_can_differ_but_grounded_semantics_match() -> None:
    case = _approved_strict_case()
    discovered = ScopeQuantityCandidate(
        tender_id=case.tender_id,
        scope_detail_id=case.scope_detail_id,
        source_document_id=case.source_document_id,
        document_page_id=case.document_page_id,
        quantity_raw="1",
        quantity_value=1,
        quantity_min=None,
        quantity_max=None,
        unit_raw="PIEZA",
        measure_kind="COUNT",
        relation="EXACT",
        source_method=case.source_method,
        source_artifact_key=case.source_artifact_key,
        source_locator=case.source_locator,
        source_excerpt="MODELO: PW481-50 (1 PIEZA)",
        review_required=True,
    )

    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(discovered,)),
        elapsed_time_ms=1,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_PASS


def test_ungrounded_discovered_is_invalid() -> None:
    case = _approved_strict_case()
    bad = replace(_candidate_from(case), source_excerpt="TEXT NOT IN SOURCE")

    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(bad,)),
        elapsed_time_ms=1,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_INVALID
    assert result.grounding_error_count > 0


def test_structural_exact_missing_quantity_value_is_invalid_but_not_grounding() -> None:
    case = _approved_strict_case()
    result = evaluate_case(
        case,
        discovery_result=_discovery(
            status="INVALID_OUTPUT",
            candidates=(),
            errors=("EXACT relation requires quantity_value_raw",),
        ),
        elapsed_time_ms=1,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_INVALID
    assert result.discovery_status == "INVALID_OUTPUT"
    assert result.grounding_error_count == 0
    assert result.contract_validation_error_count == 1


def test_quantity_raw_grounding_failure_counts_as_grounding() -> None:
    case = _approved_strict_case()
    bad = replace(_candidate_from(case), source_excerpt="3 técnicos", quantity_raw="5")

    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(bad,)),
        elapsed_time_ms=1,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_INVALID
    assert result.grounding_error_count > 0
    assert result.contract_validation_error_count == 0


def test_unit_raw_grounding_failure_counts_as_grounding() -> None:
    case = _approved_strict_case()
    bad = replace(_candidate_from(case), unit_raw="metros", source_excerpt="3 técnicos")

    result = evaluate_case(
        case,
        discovery_result=_discovery(status="DISCOVERED", candidates=(bad,)),
        elapsed_time_ms=1,
    )

    assert result.evaluation_status == GOLDEN_EVAL_STATUS_INVALID
    assert result.grounding_error_count > 0
    assert result.contract_validation_error_count == 0


def test_aggregate_metrics_precision_recall_hard_negative_mixed_critical_invalid_and_timing() -> None:
    strict = _approved_strict_case()
    no_q = replace(
        _approved_strict_case(),
        case_id="sq_case_noq",
        evaluation_mode=GOLDEN_MODE_NO_QUANTITIES,
        expected_quantities=(),
        coverage_tags=("HARD_NEGATIVE",),
    )

    leakage_candidate = ScopeQuantityCandidate(
        tender_id=no_q.tender_id,
        scope_detail_id=no_q.scope_detail_id,
        source_document_id=no_q.source_document_id,
        document_page_id=no_q.document_page_id,
        quantity_raw="100",
        quantity_value=100,
        quantity_min=None,
        quantity_max=None,
        unit_raw=None,
        measure_kind="COUNT",
        relation="EXACT",
        source_method=no_q.source_method,
        source_artifact_key=no_q.source_artifact_key,
        source_locator=no_q.source_locator,
        source_excerpt="100-120VCA",
        review_required=True,
    )

    pass_eval = evaluate_case(
        strict,
        discovery_result=_discovery(status="DISCOVERED", candidates=(_candidate_from(strict),)),
        elapsed_time_ms=10,
    )
    fail_eval = evaluate_case(
        no_q,
        discovery_result=_discovery(status="DISCOVERED", candidates=(leakage_candidate,)),
        elapsed_time_ms=20,
    )
    invalid_eval = evaluate_case(
        strict,
        discovery_result=_discovery(status="INVALID_OUTPUT", candidates=(), errors=("boom",)),
        elapsed_time_ms=30,
    )

    metrics = aggregate_evaluations((pass_eval, fail_eval, invalid_eval))

    assert metrics.cases_total == 3
    assert metrics.pass_count == 1
    assert metrics.fail_count == 1
    assert metrics.invalid_count == 1
    assert metrics.expected_quantity_count == 2
    assert metrics.discovered_quantity_count == 2
    assert metrics.matched_quantity_count == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.hard_negative_total_count == 1
    assert metrics.hard_negative_pass_count == 0
    assert metrics.critical_technical_leakage_count >= 1
    assert metrics.invalid_output_count == 1
    assert metrics.contract_validation_error_count == 1
    assert metrics.grounding_error_count == 0
    assert metrics.total_elapsed_time_ms == 60
    assert metrics.max_elapsed_time_ms == 30
