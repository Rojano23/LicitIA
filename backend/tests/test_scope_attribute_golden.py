from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import hashlib

from app.scope_attribute_golden import (
    GOLDEN_EVAL_STATUS_FAIL,
    GOLDEN_EVAL_STATUS_PASS,
    GOLDEN_MODE_NO_ATTRIBUTES,
    GOLDEN_MODE_STRICT,
    GoldenCase,
    GoldenDataset,
    GoldenExpectedAttribute,
    aggregate_evaluations,
    evaluate_case,
    load_technical_attribute_golden,
    validate_technical_attribute_golden,
)
from app.scope_attribute_semantic_discovery import (
    DiscoveredScopeAttribute,
    ScopeAttributeSemanticDiscoveryResult,
)


def _discovery_result(
    *,
    status: str,
    candidates: tuple[DiscoveredScopeAttribute, ...],
    errors: tuple[str, ...] = (),
) -> ScopeAttributeSemanticDiscoveryResult:
    return ScopeAttributeSemanticDiscoveryResult(
        provider_name="stub",
        provider_version="stub-v1",
        contract_version="stub-contract",
        candidate_count=len(candidates),
        review_required_count=len(candidates),
        status=status,
        candidates=candidates,
        errors=errors,
    )


def _expected() -> GoldenExpectedAttribute:
    return GoldenExpectedAttribute(
        golden_attribute_id="ga-1",
        attribute_name="brand",
        value_raw="YOKOGAWA",
        evidence_excerpt="MARCA: YOKOGAWA",
        attribute_label_raw="MARCA",
        relation="UNSPECIFIED",
    )


def _case(*, mode: str = GOLDEN_MODE_STRICT) -> GoldenCase:
    source_text = "MÓDULO X, MARCA: YOKOGAWA, MODELO: ABC-1"
    expected_attributes = (_expected(),) if mode == GOLDEN_MODE_STRICT else ()
    return GoldenCase(
        case_id="case-1",
        golden_version="technical-attribute-golden-2026-09-08-001",
        tender_id="tender-1",
        scope_detail_id="scope-1",
        source_document_id="doc-1",
        document_page_id="page-1",
        page_number=1,
        source_method="VISION",
        source_artifact_key="vision-page-result:1",
        source_locator="page:1|detail_row:1",
        source_text=source_text,
        source_text_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        evaluation_mode=mode,
        human_label_status="APPROVED",
        expected_attributes=expected_attributes,
        candidate_reason="reason",
        source_contract_version="v1",
    )


def test_load_golden_json_round_trip(tmp_path: Path) -> None:
    payload = {
        "golden_version": "technical-attribute-golden-2026-09-08-001",
        "generated_at": "2026-09-08T00:00:00Z",
        "notes": "x",
        "cases": [
            {
                "case_id": "case-1",
                "golden_version": "technical-attribute-golden-2026-09-08-001",
                "tender_id": "tender-1",
                "scope_detail_id": "scope-1",
                "source_document_id": "doc-1",
                "document_page_id": "page-1",
                "page_number": 1,
                "source_method": "VISION",
                "source_artifact_key": "vision-page-result:1",
                "source_locator": "page:1|detail_row:1",
                "source_text": "MÓDULO X, MARCA: YOKOGAWA",
                "source_text_sha256": "95e4e4386f347889655c9c45f42ee63ecf09ca915f3d4fe4d8f0c211a9a44704",
                "evaluation_mode": "STRICT",
                "human_label_status": "APPROVED",
                "candidate_reason": "reason",
                "expected_attributes": [
                    {
                        "golden_attribute_id": "ga-1",
                        "attribute_name": "brand",
                        "value_raw": "YOKOGAWA",
                        "evidence_excerpt": "MARCA: YOKOGAWA",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    dataset = load_technical_attribute_golden(path)

    assert dataset.golden_version == payload["golden_version"]
    assert len(dataset.cases) == 1
    assert dataset.cases[0].expected_attributes[0].attribute_name == "brand"


def test_validate_real_golden_file_schema_integrity() -> None:
    dataset = load_technical_attribute_golden("evals/technical_attribute_golden_v1.json")
    validation = validate_technical_attribute_golden(dataset)

    assert validation.is_valid is True
    assert validation.pending_count == 0
    assert validation.approved_count == 10
    assert validation.strict_count > 0
    assert validation.no_attributes_count > 0


def test_parent_recovery_alignment_with_stub_resolver() -> None:
    case = _case()
    dataset = GoldenDataset(
        golden_version="technical-attribute-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(case,),
    )

    from app.scope_attribute_golden import GoldenParentSnapshot

    def resolver(_: GoldenCase):
        return GoldenParentSnapshot(
            scope_detail_id=case.scope_detail_id,
            tender_id=case.tender_id,
            source_document_id=case.source_document_id,
            document_page_id=case.document_page_id,
            source_method=case.source_method,
            source_artifact_key=case.source_artifact_key,
            source_locator=case.source_locator,
            source_excerpt=case.source_text,
            source_contract_version=case.source_contract_version,
        )

    validation = validate_technical_attribute_golden(dataset, parent_resolver=resolver)

    assert validation.is_valid is True


def test_validate_rejects_sha_mismatch() -> None:
    case = _case()
    dataset = GoldenDataset(
        golden_version="technical-attribute-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(
            replace(case, source_text_sha256="0" * 64),
        ),
    )

    validation = validate_technical_attribute_golden(dataset)

    assert validation.is_valid is False
    assert any("source_text_sha256 mismatch" in error for error in validation.errors)


def test_validate_rejects_non_contiguous_evidence() -> None:
    bad_expected = GoldenExpectedAttribute(
        golden_attribute_id="ga-2",
        attribute_name="brand",
        value_raw="YOKOGAWA",
        evidence_excerpt="MARCA X YOKOGAWA",
        relation="UNSPECIFIED",
    )
    case = _case()
    dataset = GoldenDataset(
        golden_version="technical-attribute-golden-2026-09-08-001",
        generated_at="2026-09-08T00:00:00Z",
        notes=None,
        cases=(replace(case, expected_attributes=(bad_expected,)),),
    )

    validation = validate_technical_attribute_golden(dataset)

    assert validation.is_valid is False
    assert any("not exact contiguous source span" in error for error in validation.errors)


def test_strict_evaluation_passes_with_exact_match() -> None:
    case = _case(mode=GOLDEN_MODE_STRICT)
    discovered = DiscoveredScopeAttribute(
        attribute_name="brand",
        value_raw="YOKOGAWA",
        evidence_excerpt="MARCA: YOKOGAWA",
        attribute_label_raw="MARCA",
        relation="UNSPECIFIED",
    )

    evaluation = evaluate_case(
        case,
        discovery_result=_discovery_result(status="DISCOVERED", candidates=(discovered,)),
        elapsed_time_ms=11,
    )

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS
    assert evaluation.matched_count == 1
    assert len(evaluation.missing_expected) == 0
    assert len(evaluation.unexpected_discovered) == 0


def test_strict_evaluation_fails_with_unexpected_discovered() -> None:
    case = _case(mode=GOLDEN_MODE_STRICT)
    discovered = DiscoveredScopeAttribute(
        attribute_name="model",
        value_raw="ABC-1",
        evidence_excerpt="MODELO: ABC-1",
        relation="UNSPECIFIED",
    )

    evaluation = evaluate_case(
        case,
        discovery_result=_discovery_result(status="DISCOVERED", candidates=(discovered,)),
        elapsed_time_ms=11,
    )

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL
    assert len(evaluation.missing_expected) == 1
    assert len(evaluation.unexpected_discovered) == 1


def test_no_attributes_hard_negative_passes_when_empty() -> None:
    case = _case(mode=GOLDEN_MODE_NO_ATTRIBUTES)

    evaluation = evaluate_case(
        case,
        discovery_result=_discovery_result(status="NO_ATTRIBUTES", candidates=()),
        elapsed_time_ms=5,
    )

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS


def test_no_attributes_hard_negative_fails_on_false_positive() -> None:
    case = _case(mode=GOLDEN_MODE_NO_ATTRIBUTES)
    discovered = DiscoveredScopeAttribute(
        attribute_name="brand",
        value_raw="YOKOGAWA",
        evidence_excerpt="MARCA: YOKOGAWA",
        relation="UNSPECIFIED",
    )

    evaluation = evaluate_case(
        case,
        discovery_result=_discovery_result(status="DISCOVERED", candidates=(discovered,)),
        elapsed_time_ms=5,
    )

    assert evaluation.evaluation_status == GOLDEN_EVAL_STATUS_FAIL


def test_aggregate_metrics_compute_precision_and_recall() -> None:
    strict_case = _case(mode=GOLDEN_MODE_STRICT)
    no_case = _case(mode=GOLDEN_MODE_NO_ATTRIBUTES)
    discovered = DiscoveredScopeAttribute(
        attribute_name="brand",
        value_raw="YOKOGAWA",
        evidence_excerpt="MARCA: YOKOGAWA",
        relation="UNSPECIFIED",
    )

    strict_eval = evaluate_case(
        strict_case,
        discovery_result=_discovery_result(status="DISCOVERED", candidates=(discovered,)),
        elapsed_time_ms=10,
    )
    no_eval = evaluate_case(
        no_case,
        discovery_result=_discovery_result(status="NO_ATTRIBUTES", candidates=()),
        elapsed_time_ms=20,
    )

    metrics = aggregate_evaluations((strict_eval, no_eval))

    assert metrics.total_cases == 2
    assert metrics.pass_count == 2
    assert metrics.fail_count == 0
    assert metrics.hard_negative_total_count == 1
    assert metrics.hard_negative_pass_count == 1
    assert metrics.total_expected_attributes == 1
    assert metrics.total_discovered_attributes == 1
    assert metrics.total_matched_attributes == 1
    assert metrics.overall_precision == 1.0
    assert metrics.overall_recall == 1.0
