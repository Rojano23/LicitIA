from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from app.source_effect_partial_resolution import normalize_partial_locator_identity
from app.source_effect_semantic_discovery import DiscoveredSourceEffect, SourceEffectSemanticDiscoveryResult

SOURCE_EFFECT_GOLDEN_CANDIDATE_VERSION = "source-effect-golden-candidate-2026-09-08-001"
SOURCE_EFFECT_GOLDEN_FROZEN_V1_VERSION = "source-effect-golden-2026-09-09-001"
SOURCE_EFFECT_DUPLICATE_ARTIFACT_ROBUSTNESS_V1_VERSION = (
    "source-effect-duplicate-artifact-robustness-2026-09-09-001"
)
ALLOWED_SOURCE_EFFECT_GOLDEN_VERSIONS = {
    SOURCE_EFFECT_GOLDEN_CANDIDATE_VERSION,
    SOURCE_EFFECT_GOLDEN_FROZEN_V1_VERSION,
    SOURCE_EFFECT_DUPLICATE_ARTIFACT_ROBUSTNESS_V1_VERSION,
}

CANDIDATE_LABEL_STATUS_PROPOSED = "PROPOSED"
CANDIDATE_LABEL_STATUS_APPROVED = "APPROVED"
CANDIDATE_LABEL_STATUS_HUMAN_APPROVED = "HUMAN_APPROVED"
ALLOWED_CANDIDATE_LABEL_STATUSES = {
    CANDIDATE_LABEL_STATUS_PROPOSED,
    CANDIDATE_LABEL_STATUS_APPROVED,
    CANDIDATE_LABEL_STATUS_HUMAN_APPROVED,
}

DATASET_STATUS_CANDIDATE = "CANDIDATE"
DATASET_STATUS_FROZEN_LIMITED_COVERAGE = "FROZEN_LIMITED_COVERAGE"
DATASET_STATUS_DUPLICATE_ARTIFACT_ROBUSTNESS = "DUPLICATE_ARTIFACT_ROBUSTNESS"
ALLOWED_DATASET_STATUSES = {
    DATASET_STATUS_CANDIDATE,
    DATASET_STATUS_FROZEN_LIMITED_COVERAGE,
    DATASET_STATUS_DUPLICATE_ARTIFACT_ROBUSTNESS,
}

DISCOVERY_STATUS_DISCOVERED = "DISCOVERED"
DISCOVERY_STATUS_NO_EFFECTS = "NO_EFFECTS"
DISCOVERY_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
DISCOVERY_STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"
DISCOVERY_STATUS_UNSUPPORTED = "UNSUPPORTED"
ALLOWED_DISCOVERY_STATUSES = {
    DISCOVERY_STATUS_DISCOVERED,
    DISCOVERY_STATUS_NO_EFFECTS,
    DISCOVERY_STATUS_REVIEW_REQUIRED,
    DISCOVERY_STATUS_INVALID_OUTPUT,
    DISCOVERY_STATUS_UNSUPPORTED,
}

EVAL_STATUS_PASS = "PASS"
EVAL_STATUS_FAIL = "FAIL"
EVAL_STATUS_UNLABELED = "UNLABELED"
EVAL_STATUS_INVALID = "INVALID"

CASE_CATEGORY_POSITIVE = "POSITIVE"
CASE_CATEGORY_HARD_NEGATIVE = "HARD_NEGATIVE"
CASE_CATEGORY_DESCRIPTIVE_NEGATIVE = "DESCRIPTIVE_NEGATIVE"
CASE_CATEGORY_AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
CASE_CATEGORY_REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class ExpectedSourceEffect:
    expected_effect_type: str | None = None
    expected_effect_scope: str | None = None
    expected_affected_document_ref_raw: str | None = None
    expected_affected_document_id: str | None = None
    expected_affected_locator_raw: str | None = None
    expected_effective_date_raw: str | None = None
    expected_review_required: bool = False


@dataclass(frozen=True, slots=True)
class SourceEffectGoldenCase:
    case_id: str
    tender_id: str
    acting_document_id: str
    document_page_id: str | None
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    source_excerpt_sha256: str
    candidate_label_status: str
    expected_discovery_status: str
    expected_effects: tuple[ExpectedSourceEffect, ...] = field(default_factory=tuple)
    expected_review_required: bool = False
    category: str = CASE_CATEGORY_HARD_NEGATIVE
    human_note: str | None = None
    evidence_note: str | None = None

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.case_id.strip():
            errors.append("case_id is required")
        if not self.tender_id.strip():
            errors.append("tender_id is required")
        if not self.acting_document_id.strip():
            errors.append("acting_document_id is required")
        if self.document_page_id is not None and not str(self.document_page_id).strip():
            errors.append("document_page_id must not be empty when provided")
        if not self.source_method.strip():
            errors.append("source_method is required")
        if not self.source_artifact_key.strip():
            errors.append("source_artifact_key is required")
        if not self.source_locator.strip():
            errors.append("source_locator is required")
        if not self.source_excerpt.strip():
            errors.append("source_excerpt is required")

        real_sha = hashlib.sha256(self.source_excerpt.encode("utf-8")).hexdigest()
        if real_sha != self.source_excerpt_sha256:
            errors.append(
                f"source_excerpt_sha256 mismatch expected={self.source_excerpt_sha256} actual={real_sha}"
            )

        if self.candidate_label_status not in ALLOWED_CANDIDATE_LABEL_STATUSES:
            errors.append(f"unsupported candidate_label_status: {self.candidate_label_status}")

        if self.expected_discovery_status not in ALLOWED_DISCOVERY_STATUSES:
            errors.append(f"unsupported expected_discovery_status: {self.expected_discovery_status}")

        if self.expected_discovery_status == DISCOVERY_STATUS_DISCOVERED and len(self.expected_effects) == 0:
            errors.append("DISCOVERED requires at least one expected_effect")

        if self.expected_discovery_status == DISCOVERY_STATUS_NO_EFFECTS and len(self.expected_effects) != 0:
            errors.append("NO_EFFECTS requires zero expected_effects")

        return tuple(errors)


@dataclass(frozen=True, slots=True)
class SourceEffectGoldenDataset:
    golden_version: str
    generated_at: str
    tender_id: str
    notes: str | None
    label_status: str | None
    dataset_status: str | None
    coverage_certifications: tuple[str, ...]
    coverage_gaps: tuple[str, ...]
    coverage_gap_effect_types: tuple[str, ...]
    coverage_gap_effect_scopes: tuple[str, ...]
    excluded_duplicate_case_ids: tuple[str, ...]
    duplicate_artifact_robustness_dataset: str | None
    integrity_sha256: str | None
    cases: tuple[SourceEffectGoldenCase, ...]


@dataclass(frozen=True, slots=True)
class SourceEffectCaseEvaluation:
    case_id: str
    evaluation_status: str
    expected_discovery_status: str
    actual_discovery_status: str
    expected_positive_count: int
    discovered_positive_count: int
    matched_positive_count: int
    false_positive_count: int
    false_negative_count: int
    review_expected: bool
    review_correctly_surfaced: bool
    review_missed: bool
    hard_negative: bool
    hard_negative_pass: bool
    hard_negative_false_positive: bool
    descriptive_negative: bool
    descriptive_negative_pass: bool
    grounding_failures: tuple[str, ...] = ()
    semantic_mismatch: tuple[str, ...] = ()
    contract_shape_failure: tuple[str, ...] = ()
    target_resolution_mismatch: tuple[str, ...] = ()
    review_policy_mismatch: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceEffectAggregateMetrics:
    cases_total: int
    positive_case_count: int
    pass_count: int
    fail_count: int
    unlabeled_count: int
    invalid_count: int
    expected_effect_count: int
    discovered_effect_count: int
    matched_effect_count: int
    false_positive_effect_count: int
    false_negative_effect_count: int
    expected_positive_count: int
    discovered_positive_count: int
    matched_positive_count: int
    false_positive_count: int
    false_negative_count: int
    precision: float | None
    precision_defined: bool
    recall: float
    review_expected: int
    review_correctly_surfaced: int
    review_missed: int
    hard_negative_count: int
    hard_negative_pass: int
    hard_negative_false_positive: int
    descriptive_negative_count: int
    descriptive_negative_pass: int
    grounding_failure_count: int
    semantic_mismatch_count: int
    contract_shape_failure_count: int
    target_resolution_mismatch_count: int
    review_policy_mismatch_count: int


def load_source_effect_golden(path: str | Path) -> SourceEffectGoldenDataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[SourceEffectGoldenCase] = []
    for case in raw.get("cases", []):
        expected_effects = tuple(
            ExpectedSourceEffect(
                expected_effect_type=item.get("expected_effect_type"),
                expected_effect_scope=item.get("expected_effect_scope"),
                expected_affected_document_ref_raw=item.get("expected_affected_document_ref_raw"),
                expected_affected_document_id=item.get("expected_affected_document_id"),
                expected_affected_locator_raw=item.get("expected_affected_locator_raw"),
                expected_effective_date_raw=item.get("expected_effective_date_raw"),
                expected_review_required=bool(item.get("expected_review_required", False)),
            )
            for item in case.get("expected_effects", [])
        )
        cases.append(
            SourceEffectGoldenCase(
                case_id=case["case_id"],
                tender_id=case["tender_id"],
                acting_document_id=case["acting_document_id"],
                document_page_id=case.get("document_page_id"),
                source_method=case["source_method"],
                source_artifact_key=case["source_artifact_key"],
                source_locator=case["source_locator"],
                source_excerpt=case["source_excerpt"],
                source_excerpt_sha256=case["source_excerpt_sha256"],
                candidate_label_status=case.get("candidate_label_status")
                or case.get("label_status")
                or CANDIDATE_LABEL_STATUS_PROPOSED,
                expected_discovery_status=case["expected_discovery_status"],
                expected_effects=expected_effects,
                expected_review_required=bool(case.get("expected_review_required", False)),
                category=str(case.get("category", CASE_CATEGORY_HARD_NEGATIVE)),
                human_note=case.get("human_note"),
                evidence_note=case.get("evidence_note"),
            )
        )

    return SourceEffectGoldenDataset(
        golden_version=raw.get("golden_version", SOURCE_EFFECT_GOLDEN_CANDIDATE_VERSION),
        generated_at=raw["generated_at"],
        tender_id=raw["tender_id"],
        notes=raw.get("notes"),
        label_status=raw.get("label_status"),
        dataset_status=raw.get("dataset_status"),
        coverage_certifications=tuple(raw.get("coverage_certifications", [])),
        coverage_gaps=tuple(raw.get("coverage_gaps", [])),
        coverage_gap_effect_types=tuple(raw.get("coverage_gap_effect_types", [])),
        coverage_gap_effect_scopes=tuple(raw.get("coverage_gap_effect_scopes", [])),
        excluded_duplicate_case_ids=tuple(raw.get("excluded_duplicate_case_ids", [])),
        duplicate_artifact_robustness_dataset=raw.get("duplicate_artifact_robustness_dataset"),
        integrity_sha256=raw.get("integrity_sha256"),
        cases=tuple(cases),
    )


def validate_source_effect_golden(dataset: SourceEffectGoldenDataset) -> tuple[str, ...]:
    errors: list[str] = []
    if dataset.golden_version not in ALLOWED_SOURCE_EFFECT_GOLDEN_VERSIONS:
        errors.append(
            "golden_version no soportada: "
            f"{dataset.golden_version}; soportadas={sorted(ALLOWED_SOURCE_EFFECT_GOLDEN_VERSIONS)}"
        )

    if dataset.dataset_status is not None and dataset.dataset_status not in ALLOWED_DATASET_STATUSES:
        errors.append(f"dataset_status no soportado: {dataset.dataset_status}")

    if dataset.dataset_status == DATASET_STATUS_FROZEN_LIMITED_COVERAGE:
        if dataset.label_status != CANDIDATE_LABEL_STATUS_HUMAN_APPROVED:
            errors.append("FROZEN_LIMITED_COVERAGE requiere label_status=HUMAN_APPROVED")
        if not dataset.coverage_certifications:
            errors.append("FROZEN_LIMITED_COVERAGE requiere coverage_certifications no vacio")
        if not dataset.coverage_gaps:
            errors.append("FROZEN_LIMITED_COVERAGE requiere coverage_gaps no vacio")
        if dataset.integrity_sha256 is None or not dataset.integrity_sha256.strip():
            errors.append("FROZEN_LIMITED_COVERAGE requiere integrity_sha256")
        else:
            computed = compute_source_effect_dataset_integrity_sha256(dataset)
            if computed != dataset.integrity_sha256:
                errors.append(
                    "integrity_sha256 mismatch "
                    f"expected={dataset.integrity_sha256} actual={computed}"
                )

    case_ids: set[str] = set()
    for case in dataset.cases:
        if case.case_id in case_ids:
            errors.append(f"duplicate case_id: {case.case_id}")
        case_ids.add(case.case_id)
        if case.tender_id != dataset.tender_id:
            errors.append(f"case:{case.case_id}:tender_id mismatch")
        errors.extend(f"case:{case.case_id}:{err}" for err in case.validate())

        if dataset.dataset_status == DATASET_STATUS_FROZEN_LIMITED_COVERAGE and case.candidate_label_status != CANDIDATE_LABEL_STATUS_HUMAN_APPROVED:
            errors.append(
                f"case:{case.case_id}:FROZEN_LIMITED_COVERAGE requiere candidate_label_status=HUMAN_APPROVED"
            )

    excluded = set(dataset.excluded_duplicate_case_ids)
    overlap = sorted(excluded.intersection(case_ids))
    if overlap:
        errors.append(f"excluded_duplicate_case_ids no debe incluir casos primarios: {overlap}")

    return tuple(errors)


def evaluate_case(
    case: SourceEffectGoldenCase,
    *,
    actual: SourceEffectSemanticDiscoveryResult,
) -> SourceEffectCaseEvaluation:
    contract_failures: list[str] = []
    if actual.status not in ALLOWED_DISCOVERY_STATUSES:
        contract_failures.append(f"unsupported actual status: {actual.status}")

    discovered_effects = tuple(actual.discovered_effects)
    grounding_failures = tuple(_grounding_failures(case.source_excerpt, discovered_effects))

    expected_positive = len(case.expected_effects)
    discovered_positive = len(discovered_effects)

    matches, semantic_mismatch, target_mismatch, review_mismatch = _match_effects(
        expected=case.expected_effects,
        discovered=discovered_effects,
    )

    matched = len(matches)
    false_positive = max(0, discovered_positive - matched)
    false_negative = max(0, expected_positive - matched)

    review_correctly = case.expected_review_required and actual.status == DISCOVERY_STATUS_REVIEW_REQUIRED
    review_missed = case.expected_review_required and actual.status != DISCOVERY_STATUS_REVIEW_REQUIRED

    hard_negative = case.category == CASE_CATEGORY_HARD_NEGATIVE
    descriptive_negative = case.category == CASE_CATEGORY_DESCRIPTIVE_NEGATIVE

    hard_negative_pass = hard_negative and actual.status == DISCOVERY_STATUS_NO_EFFECTS
    hard_negative_false_positive = hard_negative and discovered_positive > 0
    descriptive_negative_pass = descriptive_negative and actual.status == DISCOVERY_STATUS_NO_EFFECTS

    status_ok = case.expected_discovery_status == actual.status
    result_status = EVAL_STATUS_PASS if status_ok and not grounding_failures and not contract_failures and false_positive == 0 and false_negative == 0 else EVAL_STATUS_FAIL
    if case.candidate_label_status == CANDIDATE_LABEL_STATUS_PROPOSED:
        result_status = EVAL_STATUS_UNLABELED
    if contract_failures:
        result_status = EVAL_STATUS_INVALID

    return SourceEffectCaseEvaluation(
        case_id=case.case_id,
        evaluation_status=result_status,
        expected_discovery_status=case.expected_discovery_status,
        actual_discovery_status=actual.status,
        expected_positive_count=expected_positive,
        discovered_positive_count=discovered_positive,
        matched_positive_count=matched,
        false_positive_count=false_positive,
        false_negative_count=false_negative,
        review_expected=case.expected_review_required,
        review_correctly_surfaced=review_correctly,
        review_missed=review_missed,
        hard_negative=hard_negative,
        hard_negative_pass=hard_negative_pass,
        hard_negative_false_positive=hard_negative_false_positive,
        descriptive_negative=descriptive_negative,
        descriptive_negative_pass=descriptive_negative_pass,
        grounding_failures=grounding_failures,
        semantic_mismatch=tuple(semantic_mismatch),
        contract_shape_failure=tuple(contract_failures),
        target_resolution_mismatch=tuple(target_mismatch),
        review_policy_mismatch=tuple(review_mismatch),
    )


def aggregate_evaluations(evaluations: Sequence[SourceEffectCaseEvaluation]) -> SourceEffectAggregateMetrics:
    positive_case_count = sum(1 for item in evaluations if item.expected_positive_count > 0)
    pass_count = sum(1 for item in evaluations if item.evaluation_status == EVAL_STATUS_PASS)
    fail_count = sum(1 for item in evaluations if item.evaluation_status == EVAL_STATUS_FAIL)
    unlabeled_count = sum(1 for item in evaluations if item.evaluation_status == EVAL_STATUS_UNLABELED)
    invalid_count = sum(1 for item in evaluations if item.evaluation_status == EVAL_STATUS_INVALID)

    expected_positive = sum(item.expected_positive_count for item in evaluations)
    discovered_positive = sum(item.discovered_positive_count for item in evaluations)
    matched_positive = sum(item.matched_positive_count for item in evaluations)
    false_positive = sum(item.false_positive_count for item in evaluations)
    false_negative = sum(item.false_negative_count for item in evaluations)

    precision_defined = discovered_positive > 0
    precision = (matched_positive / discovered_positive) if precision_defined else None
    recall = (matched_positive / expected_positive) if expected_positive else 1.0

    review_expected = sum(1 for item in evaluations if item.review_expected)
    review_correctly = sum(1 for item in evaluations if item.review_correctly_surfaced)
    review_missed = sum(1 for item in evaluations if item.review_missed)

    hard_negative_count = sum(1 for item in evaluations if item.hard_negative)
    hard_negative_pass = sum(1 for item in evaluations if item.hard_negative_pass)
    hard_negative_false_positive = sum(1 for item in evaluations if item.hard_negative_false_positive)

    descriptive_negative_count = sum(1 for item in evaluations if item.descriptive_negative)
    descriptive_negative_pass = sum(1 for item in evaluations if item.descriptive_negative_pass)

    return SourceEffectAggregateMetrics(
        cases_total=len(evaluations),
        positive_case_count=positive_case_count,
        pass_count=pass_count,
        fail_count=fail_count,
        unlabeled_count=unlabeled_count,
        invalid_count=invalid_count,
        expected_effect_count=expected_positive,
        discovered_effect_count=discovered_positive,
        matched_effect_count=matched_positive,
        false_positive_effect_count=false_positive,
        false_negative_effect_count=false_negative,
        expected_positive_count=expected_positive,
        discovered_positive_count=discovered_positive,
        matched_positive_count=matched_positive,
        false_positive_count=false_positive,
        false_negative_count=false_negative,
        precision=precision,
        precision_defined=precision_defined,
        recall=recall,
        review_expected=review_expected,
        review_correctly_surfaced=review_correctly,
        review_missed=review_missed,
        hard_negative_count=hard_negative_count,
        hard_negative_pass=hard_negative_pass,
        hard_negative_false_positive=hard_negative_false_positive,
        descriptive_negative_count=descriptive_negative_count,
        descriptive_negative_pass=descriptive_negative_pass,
        grounding_failure_count=sum(len(item.grounding_failures) for item in evaluations),
        semantic_mismatch_count=sum(len(item.semantic_mismatch) for item in evaluations),
        contract_shape_failure_count=sum(len(item.contract_shape_failure) for item in evaluations),
        target_resolution_mismatch_count=sum(len(item.target_resolution_mismatch) for item in evaluations),
        review_policy_mismatch_count=sum(len(item.review_policy_mismatch) for item in evaluations),
    )


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def _normalized_locator(value: str | None) -> str:
    normalized = normalize_partial_locator_identity(value)
    return normalized or ""


def _grounding_failures(source_excerpt: str, discovered_effects: tuple[DiscoveredSourceEffect, ...]) -> list[str]:
    failures: list[str] = []
    source_norm = _normalize_text(source_excerpt)
    for index, effect in enumerate(discovered_effects):
        evidence = _normalize_text(effect.evidence_excerpt)
        if not evidence:
            failures.append(f"effect[{index}] evidence_excerpt vacío")
            continue
        if evidence not in source_norm:
            failures.append(f"effect[{index}] evidence_excerpt no grounded")
    return failures


def _match_effects(
    *,
    expected: tuple[ExpectedSourceEffect, ...],
    discovered: tuple[DiscoveredSourceEffect, ...],
) -> tuple[set[int], list[str], list[str], list[str]]:
    matched_discovered: set[int] = set()
    semantic_mismatch: list[str] = []
    target_mismatch: list[str] = []
    review_mismatch: list[str] = []

    for expected_index, expected_effect in enumerate(expected):
        candidate_idx: int | None = None
        for discovered_index, discovered_effect in enumerate(discovered):
            if discovered_index in matched_discovered:
                continue

            if expected_effect.expected_effect_type and expected_effect.expected_effect_type != discovered_effect.effect_type:
                continue
            if expected_effect.expected_effect_scope and expected_effect.expected_effect_scope != discovered_effect.effect_scope:
                continue

            doc_ref_ok = True
            if expected_effect.expected_affected_document_ref_raw is not None:
                doc_ref_ok = _normalize_text(expected_effect.expected_affected_document_ref_raw) == _normalize_text(
                    discovered_effect.affected_document_ref_raw
                )

            locator_ok = True
            if expected_effect.expected_affected_locator_raw is not None:
                locator_ok = _normalized_locator(expected_effect.expected_affected_locator_raw) == _normalized_locator(
                    discovered_effect.affected_locator_raw
                )

            date_ok = True
            if expected_effect.expected_effective_date_raw is not None:
                date_ok = _normalize_text(expected_effect.expected_effective_date_raw) == _normalize_text(
                    discovered_effect.effective_date_raw
                )

            if doc_ref_ok and locator_ok and date_ok:
                candidate_idx = discovered_index
                break

        if candidate_idx is None:
            semantic_mismatch.append(f"expected[{expected_index}] sin match")
            continue

        matched_discovered.add(candidate_idx)

        if expected_effect.expected_affected_document_ref_raw is not None:
            discovered_ref = discovered[candidate_idx].affected_document_ref_raw
            if _normalize_text(expected_effect.expected_affected_document_ref_raw) != _normalize_text(discovered_ref):
                target_mismatch.append(f"expected[{expected_index}] mismatch affected_document_ref_raw")

        expected_review = expected_effect.expected_review_required
        discovered_review = bool(
            discovered[candidate_idx].effect_scope == "UNRESOLVED" or not discovered[candidate_idx].affected_document_ref_raw
        )
        if expected_review != discovered_review:
            review_mismatch.append(f"expected[{expected_index}] mismatch review policy")

    return matched_discovered, semantic_mismatch, target_mismatch, review_mismatch


def summarize_dataset(dataset: SourceEffectGoldenDataset) -> dict[str, object]:
    category_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for case in dataset.cases:
        category_counts[case.category] = category_counts.get(case.category, 0) + 1
        status_counts[case.expected_discovery_status] = status_counts.get(case.expected_discovery_status, 0) + 1

    return {
        "golden_version": dataset.golden_version,
        "cases_total": len(dataset.cases),
        "label_status": dataset.label_status,
        "dataset_status": dataset.dataset_status,
        "category_counts": dict(sorted(category_counts.items())),
        "expected_discovery_status_counts": dict(sorted(status_counts.items())),
        "excluded_duplicate_case_ids_count": len(dataset.excluded_duplicate_case_ids),
    }


def compute_source_effect_dataset_integrity_sha256(dataset: SourceEffectGoldenDataset) -> str:
    canonical_cases = []
    for case in dataset.cases:
        canonical_cases.append(
            {
                "case_id": case.case_id,
                "tender_id": case.tender_id,
                "acting_document_id": case.acting_document_id,
                "document_page_id": case.document_page_id,
                "source_method": case.source_method,
                "source_artifact_key": case.source_artifact_key,
                "source_locator": case.source_locator,
                "source_excerpt": case.source_excerpt,
                "source_excerpt_sha256": case.source_excerpt_sha256,
                "candidate_label_status": case.candidate_label_status,
                "expected_discovery_status": case.expected_discovery_status,
                "expected_effects": [
                    {
                        "expected_effect_type": effect.expected_effect_type,
                        "expected_effect_scope": effect.expected_effect_scope,
                        "expected_affected_document_ref_raw": effect.expected_affected_document_ref_raw,
                        "expected_affected_document_id": effect.expected_affected_document_id,
                        "expected_affected_locator_raw": effect.expected_affected_locator_raw,
                        "expected_effective_date_raw": effect.expected_effective_date_raw,
                        "expected_review_required": effect.expected_review_required,
                    }
                    for effect in case.expected_effects
                ],
                "expected_review_required": case.expected_review_required,
                "category": case.category,
                "human_note": case.human_note,
                "evidence_note": case.evidence_note,
            }
        )

    canonical_payload = {
        "golden_version": dataset.golden_version,
        "tender_id": dataset.tender_id,
        "label_status": dataset.label_status,
        "dataset_status": dataset.dataset_status,
        "coverage_certifications": list(dataset.coverage_certifications),
        "coverage_gaps": list(dataset.coverage_gaps),
        "coverage_gap_effect_types": list(dataset.coverage_gap_effect_types),
        "coverage_gap_effect_scopes": list(dataset.coverage_gap_effect_scopes),
        "excluded_duplicate_case_ids": list(dataset.excluded_duplicate_case_ids),
        "duplicate_artifact_robustness_dataset": dataset.duplicate_artifact_robustness_dataset,
        "cases": canonical_cases,
    }
    canonical_json = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def is_descriptive_negative_text(text: str) -> bool:
    return bool(
        re.search(
            r"\badenda\b|\baclaraciones?\b|\bmodificaciones?\s+a\s+las\s+bases\b|\bversi[oó]n\s+final\b",
            text,
            re.IGNORECASE,
        )
    )
