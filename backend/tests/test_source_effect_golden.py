from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.source_effect_golden import (
    CASE_CATEGORY_DESCRIPTIVE_NEGATIVE,
    CASE_CATEGORY_HARD_NEGATIVE,
    CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
    CANDIDATE_LABEL_STATUS_PROPOSED,
    DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
    DISCOVERY_STATUS_DISCOVERED,
    DISCOVERY_STATUS_NO_EFFECTS,
    DISCOVERY_STATUS_REVIEW_REQUIRED,
    EVAL_STATUS_PASS,
    EVAL_STATUS_UNLABELED,
    ExpectedSourceEffect,
    SourceEffectGoldenCase,
    SourceEffectGoldenDataset,
    aggregate_evaluations,
    compute_source_effect_dataset_integrity_sha256,
    evaluate_case,
    load_source_effect_golden,
    validate_source_effect_golden,
)
from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SourceEffectSemanticDiscoveryResult,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_validate_source_effect_golden_ok(tmp_path: Path) -> None:
    excerpt = "Las aclaraciones de dudas no modifican por si mismas un documento objetivo específico."
    payload = {
        "golden_version": "source-effect-golden-candidate-2026-09-08-001",
        "generated_at": "2026-09-08T00:00:00Z",
        "tender_id": "tender-1",
        "notes": "test",
        "cases": [
            {
                "case_id": "c1",
                "tender_id": "tender-1",
                "acting_document_id": "doc-1",
                "document_page_id": "page-1",
                "source_method": "NATIVE",
                "source_artifact_key": "native-page:page-1",
                "source_locator": "page_1_native|chars_0-80",
                "source_excerpt": excerpt,
                "source_excerpt_sha256": _sha(excerpt),
                "candidate_label_status": "PROPOSED",
                "expected_discovery_status": "NO_EFFECTS",
                "expected_effects": [],
                "expected_review_required": False,
                "category": "HARD_NEGATIVE",
                "human_note": "test",
                "evidence_note": "test",
            }
        ],
    }

    path = tmp_path / "golden.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    dataset = load_source_effect_golden(path)
    errors = validate_source_effect_golden(dataset)
    assert errors == ()


def test_evaluate_case_unlabeled_proposed() -> None:
    excerpt = "Las aclaraciones de dudas no modifican por si mismas un documento objetivo específico."
    case = SourceEffectGoldenCase(
        case_id="c1",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-80",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_PROPOSED,
        expected_discovery_status=DISCOVERY_STATUS_NO_EFFECTS,
        expected_effects=(),
        expected_review_required=False,
        category=CASE_CATEGORY_HARD_NEGATIVE,
    )

    result = SourceEffectSemanticDiscoveryResult(
        provider_name="fake",
        provider_version="v1",
        contract_version="c1",
        status=DISCOVERY_STATUS_NO_EFFECTS,
        candidate_count=0,
        review_required_count=0,
        candidates=(),
        discovered_effects=(),
        diagnostics=(),
        errors=(),
    )

    evaluation = evaluate_case(case, actual=result)
    assert evaluation.evaluation_status == EVAL_STATUS_UNLABELED
    assert evaluation.hard_negative_pass is True


def test_evaluate_case_matching_and_aggregate_metrics() -> None:
    excerpt = "Se sustituye el Anexo B-4 en su totalidad por el Anexo B-4 Revisado."
    case = SourceEffectGoldenCase(
        case_id="c2",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-70",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_PROPOSED,
        expected_discovery_status=DISCOVERY_STATUS_DISCOVERED,
        expected_effects=(
            ExpectedSourceEffect(
                expected_effect_type="SUPERSEDES",
                expected_effect_scope="DOCUMENT_WIDE",
                expected_affected_document_ref_raw="Anexo B-4",
                expected_affected_locator_raw=None,
                expected_effective_date_raw=None,
                expected_review_required=False,
            ),
        ),
        expected_review_required=False,
        category="POSITIVE",
    )

    result = SourceEffectSemanticDiscoveryResult(
        provider_name="fake",
        provider_version="v1",
        contract_version="c1",
        status=DISCOVERY_STATUS_DISCOVERED,
        candidate_count=1,
        review_required_count=0,
        candidates=(),
        discovered_effects=(
            DiscoveredSourceEffect(
                effect_type="SUPERSEDES",
                effect_scope="DOCUMENT_WIDE",
                affected_document_ref_raw="Anexo B-4",
                affected_locator_raw=None,
                effective_date_raw=None,
                evidence_excerpt="Se sustituye el Anexo B-4 en su totalidad por el Anexo B-4 Revisado.",
                confidence=0.8,
            ),
        ),
        diagnostics=(),
        errors=(),
    )

    evaluation = evaluate_case(case, actual=result)
    aggregate = aggregate_evaluations((evaluation,))

    assert evaluation.matched_positive_count == 1
    assert aggregate.positive_case_count == 1
    assert aggregate.expected_effect_count == 1
    assert aggregate.discovered_effect_count == 1
    assert aggregate.matched_effect_count == 1
    assert aggregate.expected_positive_count == 1
    assert aggregate.discovered_positive_count == 1
    assert aggregate.matched_positive_count == 1
    assert aggregate.precision_defined is True
    assert aggregate.precision == 1.0


def test_evaluate_case_review_required_positive_counts_expected_effects() -> None:
    excerpt = "Se modifica el inciso i para precisar requisitos de entrega."
    case = SourceEffectGoldenCase(
        case_id="c-review-1",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-60",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        expected_discovery_status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        expected_effects=(
            ExpectedSourceEffect(
                expected_effect_type="AMENDS",
                expected_effect_scope="PARTIAL",
                expected_affected_document_ref_raw=None,
                expected_affected_locator_raw="inciso i",
                expected_effective_date_raw=None,
                expected_review_required=True,
            ),
        ),
        expected_review_required=True,
        category="REVIEW_REQUIRED",
    )

    result = SourceEffectSemanticDiscoveryResult(
        provider_name="fake",
        provider_version="v1",
        contract_version="c1",
        status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        candidate_count=1,
        review_required_count=1,
        candidates=(),
        discovered_effects=(
            DiscoveredSourceEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                affected_document_ref_raw=None,
                affected_locator_raw="inciso i",
                effective_date_raw=None,
                evidence_excerpt=excerpt,
                confidence=0.7,
            ),
        ),
        diagnostics=(),
        errors=(),
    )

    evaluation = evaluate_case(case, actual=result)
    aggregate = aggregate_evaluations((evaluation,))

    assert evaluation.evaluation_status == EVAL_STATUS_PASS
    assert evaluation.expected_positive_count == 1
    assert aggregate.expected_positive_count == 1
    assert aggregate.review_expected == 1
    assert aggregate.review_correctly_surfaced == 1


def test_evaluate_case_multiple_expected_effects_match() -> None:
    excerpt = "Se modifica Apartado 3.1.5 y se aclaran Disposiciones Transitorias."
    case = SourceEffectGoldenCase(
        case_id="c-review-2",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-70",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        expected_discovery_status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        expected_effects=(
            ExpectedSourceEffect(
                expected_effect_type="AMENDS",
                expected_effect_scope="PARTIAL",
                expected_affected_document_ref_raw=None,
                expected_affected_locator_raw="Apartado 3.1.5",
                expected_effective_date_raw=None,
                expected_review_required=True,
            ),
            ExpectedSourceEffect(
                expected_effect_type="CLARIFIES",
                expected_effect_scope="PARTIAL",
                expected_affected_document_ref_raw=None,
                expected_affected_locator_raw="Disposiciones Transitorias",
                expected_effective_date_raw=None,
                expected_review_required=True,
            ),
        ),
        expected_review_required=True,
        category="REVIEW_REQUIRED",
    )

    result = SourceEffectSemanticDiscoveryResult(
        provider_name="fake",
        provider_version="v1",
        contract_version="c1",
        status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        candidate_count=2,
        review_required_count=2,
        candidates=(),
        discovered_effects=(
            DiscoveredSourceEffect(
                effect_type="CLARIFIES",
                effect_scope="PARTIAL",
                affected_document_ref_raw=None,
                affected_locator_raw="Disposiciones Transitorias",
                effective_date_raw=None,
                evidence_excerpt=excerpt,
                confidence=0.7,
            ),
            DiscoveredSourceEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                affected_document_ref_raw=None,
                affected_locator_raw="Apartado 3.1.5",
                effective_date_raw=None,
                evidence_excerpt=excerpt,
                confidence=0.7,
            ),
        ),
        diagnostics=(),
        errors=(),
    )

    evaluation = evaluate_case(case, actual=result)
    aggregate = aggregate_evaluations((evaluation,))

    assert evaluation.evaluation_status == EVAL_STATUS_PASS
    assert evaluation.matched_positive_count == 2
    assert aggregate.positive_case_count == 1
    assert aggregate.expected_effect_count == 2
    assert aggregate.expected_positive_count == 2
    assert aggregate.matched_positive_count == 2


def test_precision_is_undefined_when_no_discovered_effects() -> None:
    excerpt = "Se modifica Apartado 3.1.5 y se aclaran Disposiciones Transitorias."
    case = SourceEffectGoldenCase(
        case_id="c-no-discovery",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-70",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        expected_discovery_status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        expected_effects=(
            ExpectedSourceEffect(
                expected_effect_type="AMENDS",
                expected_effect_scope="PARTIAL",
                expected_affected_document_ref_raw=None,
                expected_affected_locator_raw="Apartado 3.1.5",
                expected_effective_date_raw=None,
                expected_review_required=True,
            ),
        ),
        expected_review_required=True,
        category="REVIEW_REQUIRED",
    )
    result = SourceEffectSemanticDiscoveryResult(
        provider_name="fake",
        provider_version="v1",
        contract_version="c1",
        status=DISCOVERY_STATUS_REVIEW_REQUIRED,
        candidate_count=0,
        review_required_count=0,
        candidates=(),
        discovered_effects=(),
        diagnostics=(),
        errors=(),
    )

    aggregate = aggregate_evaluations((evaluate_case(case, actual=result),))

    assert aggregate.discovered_effect_count == 0
    assert aggregate.precision is None
    assert aggregate.precision_defined is False
    assert aggregate.recall == 0.0


def test_validate_frozen_limited_coverage_requires_metadata() -> None:
    excerpt = "Texto descriptivo sin efectos materiales."
    case = SourceEffectGoldenCase(
        case_id="c-frozen-metadata",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-40",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        expected_discovery_status=DISCOVERY_STATUS_NO_EFFECTS,
        expected_effects=(),
        expected_review_required=False,
        category=CASE_CATEGORY_DESCRIPTIVE_NEGATIVE,
    )
    dataset = SourceEffectGoldenDataset(
        golden_version="source-effect-golden-2026-09-09-001",
        generated_at="2026-09-09T00:00:00Z",
        tender_id="t1",
        notes="test",
        label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        dataset_status=DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
        coverage_certifications=(),
        coverage_gaps=(),
        coverage_gap_effect_types=(),
        coverage_gap_effect_scopes=(),
        excluded_duplicate_case_ids=(),
        duplicate_artifact_robustness_dataset=None,
        integrity_sha256=None,
        cases=(case,),
    )

    errors = validate_source_effect_golden(dataset)
    assert any("coverage_certifications" in error for error in errors)
    assert any("coverage_gaps" in error for error in errors)
    assert any("integrity_sha256" in error for error in errors)


def test_validate_frozen_integrity_sha256_mismatch_detected() -> None:
    excerpt = "Texto descriptivo sin efectos materiales."
    case = SourceEffectGoldenCase(
        case_id="c-frozen-integrity",
        tender_id="t1",
        acting_document_id="d1",
        document_page_id="p1",
        source_method="NATIVE",
        source_artifact_key="native-page:p1",
        source_locator="page_1_native|chars_0-40",
        source_excerpt=excerpt,
        source_excerpt_sha256=_sha(excerpt),
        candidate_label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        expected_discovery_status=DISCOVERY_STATUS_NO_EFFECTS,
        expected_effects=(),
        expected_review_required=False,
        category=CASE_CATEGORY_DESCRIPTIVE_NEGATIVE,
    )

    dataset = SourceEffectGoldenDataset(
        golden_version="source-effect-golden-2026-09-09-001",
        generated_at="2026-09-09T00:00:00Z",
        tender_id="t1",
        notes="test",
        label_status=CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
        dataset_status=DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
        coverage_certifications=("curated",),
        coverage_gaps=("limited",),
        coverage_gap_effect_types=("REVOKES",),
        coverage_gap_effect_scopes=("GLOBAL",),
        excluded_duplicate_case_ids=("dup-1",),
        duplicate_artifact_robustness_dataset="evals/dup.json",
        integrity_sha256="bad-digest",
        cases=(case,),
    )
    expected_real = compute_source_effect_dataset_integrity_sha256(dataset)
    assert expected_real != "bad-digest"

    errors = validate_source_effect_golden(dataset)
    assert any("integrity_sha256 mismatch" in error for error in errors)


def test_primary_frozen_dataset_excludes_duplicate_cases_from_metrics() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    primary_dataset = load_source_effect_golden(backend_root / "evals/source_effect_golden_v1.json")
    duplicate_dataset = load_source_effect_golden(
        backend_root / "evals/source_effect_duplicate_artifact_robustness_v1.json"
    )

    primary_case_ids = {item.case_id for item in primary_dataset.cases}
    duplicate_case_ids = {item.case_id for item in duplicate_dataset.cases}

    assert primary_dataset.integrity_sha256 == (
        "2adae84c2bbbb10633d635ba8e6f95926880e3702ca21a819949fb0d599d0747"
    )
    assert len(primary_dataset.cases) == 15
    assert len(duplicate_dataset.cases) == 4
    assert sum(1 for item in primary_dataset.cases if item.expected_effects) == 2
    assert sum(len(item.expected_effects) for item in primary_dataset.cases) == 3
    assert sum(
        1
        for item in primary_dataset.cases
        for effect in item.expected_effects
        if effect.expected_effect_type == "AMENDS"
    ) == 2
    assert sum(
        1
        for item in primary_dataset.cases
        for effect in item.expected_effects
        if effect.expected_effect_type == "CLARIFIES"
    ) == 1
    assert sum(1 for item in primary_dataset.cases if item.category == "HARD_NEGATIVE") == 7
    assert sum(1 for item in primary_dataset.cases if item.category == "DESCRIPTIVE_NEGATIVE") == 6

    se_gc_011 = next(item for item in primary_dataset.cases if item.case_id == "se_gc_011")
    assert len(se_gc_011.expected_effects) == 2

    assert set(primary_dataset.excluded_duplicate_case_ids) == {
        "se_gc_012",
        "se_gc_014",
        "se_gc_016",
        "se_gc_018",
    }
    assert primary_case_ids.isdisjoint(duplicate_case_ids)
    assert primary_case_ids.isdisjoint(set(primary_dataset.excluded_duplicate_case_ids))


def test_primary_aggregate_semantics_case_vs_effect_levels() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    primary_dataset = load_source_effect_golden(backend_root / "evals/source_effect_golden_v1.json")

    evaluations = []
    for case in primary_dataset.cases:
        status = DISCOVERY_STATUS_REVIEW_REQUIRED if case.expected_review_required else DISCOVERY_STATUS_NO_EFFECTS
        result = SourceEffectSemanticDiscoveryResult(
            provider_name="fake",
            provider_version="v1",
            contract_version="c1",
            status=status,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=(),
            errors=(),
        )
        evaluations.append(evaluate_case(case, actual=result))

    aggregate = aggregate_evaluations(tuple(evaluations))

    assert aggregate.cases_total == 15
    assert aggregate.positive_case_count == 2
    assert aggregate.expected_effect_count == 3
    assert aggregate.expected_positive_count == 3
    assert aggregate.discovered_effect_count == 0
    assert aggregate.matched_effect_count == 0
    assert aggregate.false_negative_effect_count == 3
    assert aggregate.review_expected == 2
    assert aggregate.review_correctly_surfaced == 2
    assert aggregate.review_missed == 0
    assert aggregate.precision is None
    assert aggregate.precision_defined is False


def test_candidate_pack_remains_proposed() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    candidate_dataset = load_source_effect_golden(
        backend_root / "evals/source_effect_golden_candidate_t001_v1.json"
    )

    assert len(candidate_dataset.cases) == 19
    assert all(item.candidate_label_status == CANDIDATE_LABEL_STATUS_PROPOSED for item in candidate_dataset.cases)
