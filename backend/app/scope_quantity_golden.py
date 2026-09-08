from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from sqlalchemy.orm import Session

from app.models import DocumentPage, TenderScopeDetail
from app.scope_quantities import (
    SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS,
    SCOPE_QUANTITY_ALLOWED_RELATIONS,
    ScopeQuantityCandidate,
)
from app.scope_quantity_semantic_discovery import ScopeQuantitySemanticDiscoveryResult

GOLDEN_LABEL_PENDING = "PENDING"
GOLDEN_LABEL_APPROVED = "APPROVED"
GOLDEN_ALLOWED_LABELS = {GOLDEN_LABEL_PENDING, GOLDEN_LABEL_APPROVED}

GOLDEN_MODE_STRICT = "STRICT"
GOLDEN_MODE_NO_QUANTITIES = "NO_QUANTITIES"
GOLDEN_MODE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
GOLDEN_ALLOWED_MODES = {
    GOLDEN_MODE_STRICT,
    GOLDEN_MODE_NO_QUANTITIES,
    GOLDEN_MODE_REVIEW_REQUIRED,
}

GOLDEN_EVAL_STATUS_PASS = "PASS"
GOLDEN_EVAL_STATUS_FAIL = "FAIL"
GOLDEN_EVAL_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
GOLDEN_EVAL_STATUS_UNLABELED = "UNLABELED"
GOLDEN_EVAL_STATUS_INVALID = "INVALID"

_SAFE_DECIMAL_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


@dataclass(frozen=True, slots=True)
class GoldenExpectedQuantity:
    golden_quantity_id: str
    quantity_raw: str
    evidence_excerpt: str
    measure_kind: str
    relation: str
    quantity_value_raw: Optional[str] = None
    quantity_min_raw: Optional[str] = None
    quantity_max_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    human_note: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ScopeQuantityGoldenCase:
    case_id: str
    golden_version: str
    human_label_status: str
    evaluation_mode: str
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_text: str
    source_text_sha256: str
    expected_quantities: tuple[GoldenExpectedQuantity, ...]
    candidate_reason: str
    forbidden_quantity_literals: tuple[str, ...] = ()
    coverage_tags: tuple[str, ...] = ()
    human_notes: Optional[str] = None
    source_contract_version: Optional[str] = None
    source_analysis_id: Optional[str] = None
    source_page_result_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ScopeQuantityGoldenDataset:
    golden_version: str
    generated_at: str
    notes: Optional[str]
    cases: tuple[ScopeQuantityGoldenCase, ...]


@dataclass(frozen=True, slots=True)
class GoldenQuantityParentSnapshot:
    scope_detail_id: str
    tender_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    source_contract_version: Optional[str]
    source_analysis_id: Optional[str]
    source_page_result_id: Optional[str]


@dataclass(frozen=True, slots=True)
class GoldenValidationResult:
    is_valid: bool
    errors: tuple[str, ...]
    approved_count: int
    pending_count: int
    strict_count: int
    no_quantities_count: int
    review_required_count: int
    expected_quantity_count: int
    measure_kind_counts: tuple[tuple[str, int], ...]
    relation_counts: tuple[tuple[str, int], ...]
    source_method_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class QuantityMatch:
    expected: GoldenExpectedQuantity
    discovered: ScopeQuantityCandidate


@dataclass(frozen=True, slots=True)
class GoldenCaseEvaluation:
    case_id: str
    evaluation_mode: str
    evaluation_status: str
    discovery_status: str
    elapsed_time_ms: int
    expected_count: int
    discovered_count: int
    matched_count: int
    expected_quantities: tuple[GoldenExpectedQuantity, ...]
    discovered_quantities: tuple[ScopeQuantityCandidate, ...]
    matches: tuple[QuantityMatch, ...]
    missing_expected: tuple[GoldenExpectedQuantity, ...]
    unexpected_discovered: tuple[ScopeQuantityCandidate, ...]
    coverage_tags: tuple[str, ...] = ()
    critical_leakage_count: int = 0
    grounding_error_count: int = 0
    contract_validation_error_count: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GoldenAggregateMetrics:
    cases_total: int
    pass_count: int
    fail_count: int
    review_required_count: int
    unlabeled_count: int
    invalid_count: int
    discovery_status_counts: tuple[tuple[str, int], ...]
    expected_quantity_count: int
    discovered_quantity_count: int
    matched_quantity_count: int
    missing_expected_count: int
    unexpected_discovered_count: int
    precision: float
    recall: float
    hard_negative_pass_count: int
    hard_negative_total_count: int
    mixed_context_pass_count: int
    mixed_context_total_count: int
    critical_technical_leakage_count: int
    grounding_error_count: int
    contract_validation_error_count: int
    invalid_output_count: int
    total_elapsed_time_ms: int
    average_elapsed_time_ms: float
    max_elapsed_time_ms: int


class ParentResolver(Protocol):
    def __call__(self, case: ScopeQuantityGoldenCase) -> Optional[GoldenQuantityParentSnapshot]:
        ...


def load_scope_quantity_golden(path: str | Path) -> ScopeQuantityGoldenDataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[ScopeQuantityGoldenCase] = []
    for case in raw.get("cases", []):
        expected_quantities = tuple(
            GoldenExpectedQuantity(
                golden_quantity_id=item["golden_quantity_id"],
                quantity_raw=item["quantity_raw"],
                evidence_excerpt=item["evidence_excerpt"],
                measure_kind=item["measure_kind"],
                relation=item["relation"],
                quantity_value_raw=item.get("quantity_value_raw"),
                quantity_min_raw=item.get("quantity_min_raw"),
                quantity_max_raw=item.get("quantity_max_raw"),
                unit_raw=item.get("unit_raw"),
                human_note=item.get("human_note"),
            )
            for item in case.get("expected_quantities", [])
        )

        cases.append(
            ScopeQuantityGoldenCase(
                case_id=case["case_id"],
                golden_version=case["golden_version"],
                human_label_status=case["human_label_status"],
                evaluation_mode=case["evaluation_mode"],
                tender_id=case["tender_id"],
                scope_detail_id=case["scope_detail_id"],
                source_document_id=case["source_document_id"],
                document_page_id=case["document_page_id"],
                page_number=int(case["page_number"]),
                source_method=case["source_method"],
                source_artifact_key=case["source_artifact_key"],
                source_locator=case["source_locator"],
                source_text=case["source_text"],
                source_text_sha256=case["source_text_sha256"],
                expected_quantities=expected_quantities,
                candidate_reason=case["candidate_reason"],
                forbidden_quantity_literals=tuple(case.get("forbidden_quantity_literals", [])),
                coverage_tags=tuple(case.get("coverage_tags", [])),
                human_notes=case.get("human_notes"),
                source_contract_version=case.get("source_contract_version"),
                source_analysis_id=case.get("source_analysis_id"),
                source_page_result_id=case.get("source_page_result_id"),
            )
        )

    return ScopeQuantityGoldenDataset(
        golden_version=raw["golden_version"],
        generated_at=raw["generated_at"],
        notes=raw.get("notes"),
        cases=tuple(cases),
    )


def validate_scope_quantity_golden(
    dataset: ScopeQuantityGoldenDataset,
    *,
    parent_resolver: Optional[ParentResolver] = None,
) -> GoldenValidationResult:
    errors: list[str] = []
    case_ids: set[str] = set()
    quantity_ids: set[str] = set()

    approved_count = 0
    pending_count = 0
    strict_count = 0
    no_quantities_count = 0
    review_required_count = 0
    expected_quantity_count = 0
    measure_kind_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    source_method_counts: dict[str, int] = {}

    for case in dataset.cases:
        _append_required_text(errors, f"case:{case.case_id}:case_id", case.case_id)
        _append_required_text(errors, f"case:{case.case_id}:golden_version", case.golden_version)
        _append_required_text(errors, f"case:{case.case_id}:tender_id", case.tender_id)
        _append_required_text(errors, f"case:{case.case_id}:scope_detail_id", case.scope_detail_id)
        _append_required_text(errors, f"case:{case.case_id}:source_document_id", case.source_document_id)
        _append_required_text(errors, f"case:{case.case_id}:document_page_id", case.document_page_id)
        _append_required_text(errors, f"case:{case.case_id}:source_method", case.source_method)
        _append_required_text(errors, f"case:{case.case_id}:source_artifact_key", case.source_artifact_key)
        _append_required_text(errors, f"case:{case.case_id}:source_locator", case.source_locator)
        _append_required_text(errors, f"case:{case.case_id}:source_text", case.source_text)
        _append_required_text(errors, f"case:{case.case_id}:source_text_sha256", case.source_text_sha256)
        _append_required_text(errors, f"case:{case.case_id}:evaluation_mode", case.evaluation_mode)
        _append_required_text(errors, f"case:{case.case_id}:human_label_status", case.human_label_status)

        if case.case_id in case_ids:
            errors.append(f"duplicate case_id: {case.case_id}")
        case_ids.add(case.case_id)

        if case.page_number <= 0:
            errors.append(f"case:{case.case_id}:page_number must be greater than zero")

        if case.human_label_status not in GOLDEN_ALLOWED_LABELS:
            errors.append(f"case:{case.case_id}:unsupported human_label_status: {case.human_label_status}")
        elif case.human_label_status == GOLDEN_LABEL_APPROVED:
            approved_count += 1
        else:
            pending_count += 1

        if case.evaluation_mode not in GOLDEN_ALLOWED_MODES:
            errors.append(f"case:{case.case_id}:unsupported evaluation_mode: {case.evaluation_mode}")
        elif case.evaluation_mode == GOLDEN_MODE_STRICT:
            strict_count += 1
        elif case.evaluation_mode == GOLDEN_MODE_NO_QUANTITIES:
            no_quantities_count += 1
        else:
            review_required_count += 1

        if case.evaluation_mode == GOLDEN_MODE_STRICT and len(case.expected_quantities) == 0:
            errors.append(f"case:{case.case_id}:STRICT requires expected_quantities")
        if case.evaluation_mode == GOLDEN_MODE_NO_QUANTITIES and len(case.expected_quantities) != 0:
            errors.append(f"case:{case.case_id}:NO_QUANTITIES requires zero expected_quantities")
        if case.evaluation_mode == GOLDEN_MODE_REVIEW_REQUIRED and len(case.expected_quantities) != 0:
            errors.append(f"case:{case.case_id}:REVIEW_REQUIRED requires zero expected_quantities")

        if not _is_sha256(case.source_text_sha256):
            errors.append(f"case:{case.case_id}:invalid source_text_sha256 format")
        else:
            actual = _sha256(case.source_text)
            if actual != case.source_text_sha256:
                errors.append(
                    f"case:{case.case_id}:source_text_sha256 mismatch expected={case.source_text_sha256} actual={actual}"
                )

        if not _is_locator_valid(case.source_locator):
            errors.append(f"case:{case.case_id}:invalid source_locator: {case.source_locator}")

        if parent_resolver is not None:
            _validate_parent_alignment(case, parent_resolver(case), errors)

        source_method_counts[case.source_method] = source_method_counts.get(case.source_method, 0) + 1

        for literal in case.forbidden_quantity_literals:
            if not _grounded(case.source_text, literal):
                errors.append(f"case:{case.case_id}:forbidden literal not grounded in source_text: {literal}")

        for expected in case.expected_quantities:
            expected_quantity_count += 1
            _append_required_text(errors, f"case:{case.case_id}:golden_quantity_id", expected.golden_quantity_id)
            _append_required_text(errors, f"case:{case.case_id}:quantity_raw", expected.quantity_raw)
            _append_required_text(errors, f"case:{case.case_id}:evidence_excerpt", expected.evidence_excerpt)
            _append_required_text(errors, f"case:{case.case_id}:measure_kind", expected.measure_kind)
            _append_required_text(errors, f"case:{case.case_id}:relation", expected.relation)

            if expected.golden_quantity_id in quantity_ids:
                errors.append(f"duplicate golden_quantity_id: {expected.golden_quantity_id}")
            quantity_ids.add(expected.golden_quantity_id)

            if expected.measure_kind not in SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS:
                errors.append(
                    f"case:{case.case_id}:quantity:{expected.golden_quantity_id}:unsupported measure_kind: {expected.measure_kind}"
                )

            if expected.relation not in SCOPE_QUANTITY_ALLOWED_RELATIONS:
                errors.append(
                    f"case:{case.case_id}:quantity:{expected.golden_quantity_id}:unsupported relation: {expected.relation}"
                )

            if not _is_contiguous(case.source_text, expected.evidence_excerpt):
                errors.append(
                    f"case:{case.case_id}:quantity:{expected.golden_quantity_id}:evidence_excerpt is not exact contiguous source span"
                )

            if not _grounded(expected.evidence_excerpt, expected.quantity_raw):
                errors.append(
                    f"case:{case.case_id}:quantity:{expected.golden_quantity_id}:quantity_raw is not grounded in evidence_excerpt"
                )

            if expected.unit_raw is not None and not _grounded(expected.evidence_excerpt, expected.unit_raw):
                errors.append(
                    f"case:{case.case_id}:quantity:{expected.golden_quantity_id}:unit_raw is not grounded in evidence_excerpt"
                )

            _validate_expected_numeric_shape(case, expected, errors)

            measure_kind_counts[expected.measure_kind] = measure_kind_counts.get(expected.measure_kind, 0) + 1
            relation_counts[expected.relation] = relation_counts.get(expected.relation, 0) + 1

    return GoldenValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        approved_count=approved_count,
        pending_count=pending_count,
        strict_count=strict_count,
        no_quantities_count=no_quantities_count,
        review_required_count=review_required_count,
        expected_quantity_count=expected_quantity_count,
        measure_kind_counts=tuple(sorted(measure_kind_counts.items())),
        relation_counts=tuple(sorted(relation_counts.items())),
        source_method_counts=tuple(sorted(source_method_counts.items())),
    )


def evaluate_case(
    case: ScopeQuantityGoldenCase,
    *,
    discovery_result: ScopeQuantitySemanticDiscoveryResult,
    elapsed_time_ms: int,
) -> GoldenCaseEvaluation:
    discovered = tuple(discovery_result.candidates)

    if case.human_label_status == GOLDEN_LABEL_PENDING:
        return GoldenCaseEvaluation(
            case_id=case.case_id,
            evaluation_mode=case.evaluation_mode,
            evaluation_status=GOLDEN_EVAL_STATUS_UNLABELED,
            discovery_status=discovery_result.status,
            elapsed_time_ms=elapsed_time_ms,
            expected_count=len(case.expected_quantities),
            discovered_count=len(discovered),
            matched_count=0,
            expected_quantities=case.expected_quantities,
            discovered_quantities=discovered,
            matches=(),
            missing_expected=case.expected_quantities,
            unexpected_discovered=discovered,
            coverage_tags=case.coverage_tags,
            errors=discovery_result.errors,
        )

    discovery_grounding_errors, discovery_contract_errors = _classify_discovery_errors(discovery_result.errors)
    grounding_errors = list(discovery_grounding_errors)
    for item in discovered:
        if not _is_discovered_grounded(case.source_text, item):
            grounding_errors.append(
                f"case:{case.case_id}:discovered quantity is not grounded: quantity_raw={item.quantity_raw}"
            )

    if discovery_result.status == "INVALID_OUTPUT" or grounding_errors or discovery_contract_errors:
        return GoldenCaseEvaluation(
            case_id=case.case_id,
            evaluation_mode=case.evaluation_mode,
            evaluation_status=GOLDEN_EVAL_STATUS_INVALID,
            discovery_status=discovery_result.status,
            elapsed_time_ms=elapsed_time_ms,
            expected_count=len(case.expected_quantities),
            discovered_count=len(discovered),
            matched_count=0,
            expected_quantities=case.expected_quantities,
            discovered_quantities=discovered,
            matches=(),
            missing_expected=case.expected_quantities,
            unexpected_discovered=discovered,
            coverage_tags=case.coverage_tags,
            grounding_error_count=len(grounding_errors),
            contract_validation_error_count=len(discovery_contract_errors),
            critical_leakage_count=_count_critical_leakage(case, discovered),
            errors=tuple(discovery_contract_errors) + tuple(grounding_errors),
        )

    matches, missing_expected, unexpected_discovered = _match_expected_to_discovered(
        expected=case.expected_quantities,
        discovered=discovered,
    )

    if case.evaluation_mode == GOLDEN_MODE_NO_QUANTITIES:
        passed = discovery_result.status == GOLDEN_MODE_NO_QUANTITIES and len(discovered) == 0
    elif case.evaluation_mode == GOLDEN_MODE_REVIEW_REQUIRED:
        passed = discovery_result.status == GOLDEN_MODE_REVIEW_REQUIRED and len(discovered) == 0
    else:
        passed = len(missing_expected) == 0 and len(unexpected_discovered) == 0

    return GoldenCaseEvaluation(
        case_id=case.case_id,
        evaluation_mode=case.evaluation_mode,
        evaluation_status=GOLDEN_EVAL_STATUS_PASS if passed else GOLDEN_EVAL_STATUS_FAIL,
        discovery_status=discovery_result.status,
        elapsed_time_ms=elapsed_time_ms,
        expected_count=len(case.expected_quantities),
        discovered_count=len(discovered),
        matched_count=len(matches),
        expected_quantities=case.expected_quantities,
        discovered_quantities=discovered,
        matches=tuple(matches),
        missing_expected=tuple(missing_expected),
        unexpected_discovered=tuple(unexpected_discovered),
        coverage_tags=case.coverage_tags,
        critical_leakage_count=_count_critical_leakage(case, discovered),
        contract_validation_error_count=len(discovery_contract_errors),
        errors=discovery_result.errors,
    )


def aggregate_evaluations(evaluations: Sequence[GoldenCaseEvaluation]) -> GoldenAggregateMetrics:
    status_counts: dict[str, int] = {}
    discovery_counts: dict[str, int] = {}

    expected_count = 0
    discovered_count = 0
    matched_count = 0
    missing_expected_count = 0
    unexpected_discovered_count = 0

    hard_negative_total = 0
    hard_negative_pass = 0
    mixed_context_total = 0
    mixed_context_pass = 0

    critical_leakage_count = 0
    grounding_error_count = 0
    contract_validation_error_count = 0
    invalid_output_count = 0

    total_elapsed = 0
    max_elapsed = 0

    for evaluation in evaluations:
        status_counts[evaluation.evaluation_status] = status_counts.get(evaluation.evaluation_status, 0) + 1
        discovery_counts[evaluation.discovery_status] = discovery_counts.get(evaluation.discovery_status, 0) + 1

        expected_count += evaluation.expected_count
        discovered_count += evaluation.discovered_count
        matched_count += evaluation.matched_count
        missing_expected_count += len(evaluation.missing_expected)
        unexpected_discovered_count += len(evaluation.unexpected_discovered)
        critical_leakage_count += evaluation.critical_leakage_count
        grounding_error_count += evaluation.grounding_error_count
        contract_validation_error_count += evaluation.contract_validation_error_count

        if evaluation.discovery_status == "INVALID_OUTPUT":
            invalid_output_count += 1

        if evaluation.evaluation_mode == GOLDEN_MODE_NO_QUANTITIES:
            hard_negative_total += 1
            if evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS:
                hard_negative_pass += 1

        if any(tag == "MIXED_TECHNICAL_NUMBER" for tag in evaluation.coverage_tags):
            mixed_context_total += 1
            if evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS:
                mixed_context_pass += 1

        total_elapsed += evaluation.elapsed_time_ms
        if evaluation.elapsed_time_ms > max_elapsed:
            max_elapsed = evaluation.elapsed_time_ms

    total_cases = len(evaluations)
    precision = (matched_count / discovered_count) if discovered_count > 0 else 0.0
    recall = (matched_count / expected_count) if expected_count > 0 else 0.0
    average_elapsed = (total_elapsed / total_cases) if total_cases > 0 else 0.0

    return GoldenAggregateMetrics(
        cases_total=total_cases,
        pass_count=status_counts.get(GOLDEN_EVAL_STATUS_PASS, 0),
        fail_count=status_counts.get(GOLDEN_EVAL_STATUS_FAIL, 0),
        review_required_count=status_counts.get(GOLDEN_EVAL_STATUS_REVIEW_REQUIRED, 0),
        unlabeled_count=status_counts.get(GOLDEN_EVAL_STATUS_UNLABELED, 0),
        invalid_count=status_counts.get(GOLDEN_EVAL_STATUS_INVALID, 0),
        discovery_status_counts=tuple(sorted(discovery_counts.items())),
        expected_quantity_count=expected_count,
        discovered_quantity_count=discovered_count,
        matched_quantity_count=matched_count,
        missing_expected_count=missing_expected_count,
        unexpected_discovered_count=unexpected_discovered_count,
        precision=precision,
        recall=recall,
        hard_negative_pass_count=hard_negative_pass,
        hard_negative_total_count=hard_negative_total,
        mixed_context_pass_count=mixed_context_pass,
        mixed_context_total_count=mixed_context_total,
        critical_technical_leakage_count=critical_leakage_count,
        grounding_error_count=grounding_error_count,
        contract_validation_error_count=contract_validation_error_count,
        invalid_output_count=invalid_output_count,
        total_elapsed_time_ms=total_elapsed,
        average_elapsed_time_ms=average_elapsed,
        max_elapsed_time_ms=max_elapsed,
    )


def _classify_discovery_errors(errors: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    grounding_errors: list[str] = []
    contract_errors: list[str] = []

    for error in errors:
        normalized_error = _normalize(error)
        if _is_grounding_error_message(normalized_error):
            grounding_errors.append(error)
        else:
            contract_errors.append(error)

    return tuple(grounding_errors), tuple(contract_errors)


def _is_grounding_error_message(normalized_error: str) -> bool:
    return any(
        marker in normalized_error
        for marker in (
            "evidence_excerpt is not supported by source_text",
            "quantity_raw is not grounded in evidence_excerpt",
            "unit_raw is not grounded in evidence_excerpt",
            "discovered quantity is not grounded",
        )
    )


def build_parent_resolver(db: Session) -> ParentResolver:
    def _resolver(case: ScopeQuantityGoldenCase) -> Optional[GoldenQuantityParentSnapshot]:
        row = db.get(TenderScopeDetail, case.scope_detail_id)
        if row is None:
            return None

        page = db.get(DocumentPage, row.document_page_id)
        page_number = int(page.page_number) if page is not None else 0

        return GoldenQuantityParentSnapshot(
            scope_detail_id=row.id,
            tender_id=row.tender_id,
            source_document_id=row.source_document_id,
            document_page_id=row.document_page_id,
            page_number=page_number,
            source_method=row.source_method,
            source_artifact_key=row.source_artifact_key,
            source_locator=row.source_locator,
            source_excerpt=row.source_excerpt,
            source_contract_version=row.source_contract_version,
            source_analysis_id=row.source_analysis_id,
            source_page_result_id=row.source_page_result_id,
        )

    return _resolver


def evaluate_golden_dataset(
    dataset: ScopeQuantityGoldenDataset,
    *,
    discover_case: Callable[[ScopeQuantityGoldenCase], tuple[ScopeQuantitySemanticDiscoveryResult, int]],
) -> tuple[GoldenAggregateMetrics, tuple[GoldenCaseEvaluation, ...]]:
    evaluations: list[GoldenCaseEvaluation] = []
    for case in dataset.cases:
        result, elapsed_ms = discover_case(case)
        evaluations.append(evaluate_case(case, discovery_result=result, elapsed_time_ms=elapsed_ms))

    aggregate = aggregate_evaluations(evaluations)
    return aggregate, tuple(evaluations)


def _validate_parent_alignment(
    case: ScopeQuantityGoldenCase,
    parent: Optional[GoldenQuantityParentSnapshot],
    errors: list[str],
) -> None:
    if parent is None:
        errors.append(f"case:{case.case_id}:scope_detail not found")
        return

    if parent.scope_detail_id != case.scope_detail_id:
        errors.append(f"case:{case.case_id}:scope_detail_id mismatch")
    if parent.tender_id != case.tender_id:
        errors.append(f"case:{case.case_id}:tender_id mismatch")
    if parent.source_document_id != case.source_document_id:
        errors.append(f"case:{case.case_id}:source_document_id mismatch")
    if parent.document_page_id != case.document_page_id:
        errors.append(f"case:{case.case_id}:document_page_id mismatch")
    if parent.page_number != case.page_number:
        errors.append(f"case:{case.case_id}:page_number mismatch")
    if parent.source_method != case.source_method:
        errors.append(f"case:{case.case_id}:source_method mismatch")
    if parent.source_artifact_key != case.source_artifact_key:
        errors.append(f"case:{case.case_id}:source_artifact_key mismatch")
    if parent.source_locator != case.source_locator:
        errors.append(f"case:{case.case_id}:source_locator mismatch")

    if _normalize(parent.source_excerpt) != _normalize(case.source_text):
        errors.append(f"case:{case.case_id}:source_text does not match parent source_excerpt")

    if case.source_contract_version is not None and parent.source_contract_version != case.source_contract_version:
        errors.append(f"case:{case.case_id}:source_contract_version mismatch")

    if case.source_analysis_id is not None and parent.source_analysis_id != case.source_analysis_id:
        errors.append(f"case:{case.case_id}:source_analysis_id mismatch")

    if case.source_page_result_id is not None and parent.source_page_result_id != case.source_page_result_id:
        errors.append(f"case:{case.case_id}:source_page_result_id mismatch")


def _match_expected_to_discovered(
    *,
    expected: Sequence[GoldenExpectedQuantity],
    discovered: Sequence[ScopeQuantityCandidate],
) -> tuple[list[QuantityMatch], list[GoldenExpectedQuantity], list[ScopeQuantityCandidate]]:
    matches: list[QuantityMatch] = []
    missing_expected: list[GoldenExpectedQuantity] = []
    remaining_discovered = list(discovered)

    for expected_item in expected:
        hit_index = -1
        for idx, discovered_item in enumerate(remaining_discovered):
            if _semantically_matches(expected_item, discovered_item):
                hit_index = idx
                break

        if hit_index == -1:
            missing_expected.append(expected_item)
            continue

        matched = remaining_discovered.pop(hit_index)
        matches.append(QuantityMatch(expected=expected_item, discovered=matched))

    return matches, missing_expected, remaining_discovered


def _semantically_matches(expected: GoldenExpectedQuantity, discovered: ScopeQuantityCandidate) -> bool:
    if _normalize(expected.quantity_raw) != _normalize(discovered.quantity_raw):
        return False

    expected_unit = _normalize(expected.unit_raw or "")
    discovered_unit = _normalize(discovered.unit_raw or "")
    if expected_unit != discovered_unit:
        return False

    if expected.measure_kind != (discovered.measure_kind or ""):
        return False

    discovered_relation = discovered.relation or "UNSPECIFIED"
    if expected.relation != discovered_relation:
        return False

    expected_value = _decimal_or_none(expected.quantity_value_raw)
    expected_min = _decimal_or_none(expected.quantity_min_raw)
    expected_max = _decimal_or_none(expected.quantity_max_raw)

    discovered_value = _decimal_or_none(discovered.quantity_value)
    discovered_min = _decimal_or_none(discovered.quantity_min)
    discovered_max = _decimal_or_none(discovered.quantity_max)

    return expected_value == discovered_value and expected_min == discovered_min and expected_max == discovered_max


def _is_discovered_grounded(source_text: str, discovered: ScopeQuantityCandidate) -> bool:
    if not _grounded(source_text, discovered.source_excerpt):
        return False
    if not _grounded(discovered.source_excerpt, discovered.quantity_raw):
        return False
    if discovered.unit_raw is not None and not _grounded(discovered.source_excerpt, discovered.unit_raw):
        return False
    return True


def _count_critical_leakage(case: ScopeQuantityGoldenCase, discovered: Sequence[ScopeQuantityCandidate]) -> int:
    if not case.forbidden_quantity_literals:
        return 0

    count = 0
    forbidden_norm = tuple(_normalize(item) for item in case.forbidden_quantity_literals if _normalize(item))
    for item in discovered:
        excerpt_norm = _normalize(item.source_excerpt)
        if any(token in excerpt_norm for token in forbidden_norm):
            count += 1
    return count


def _validate_expected_numeric_shape(
    case: ScopeQuantityGoldenCase,
    expected: GoldenExpectedQuantity,
    errors: list[str],
) -> None:
    qid = expected.golden_quantity_id

    for field_name, value in (
        ("quantity_value_raw", expected.quantity_value_raw),
        ("quantity_min_raw", expected.quantity_min_raw),
        ("quantity_max_raw", expected.quantity_max_raw),
    ):
        if value is not None and not _is_safe_decimal(value):
            errors.append(f"case:{case.case_id}:quantity:{qid}:{field_name} invalid numeric string: {value}")

    relation = expected.relation
    value = expected.quantity_value_raw
    min_value = expected.quantity_min_raw
    max_value = expected.quantity_max_raw

    if relation == "EXACT":
        if value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:EXACT requires quantity_value_raw")
        if min_value is not None or max_value is not None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:EXACT forbids quantity_min_raw/quantity_max_raw")
    elif relation == "MINIMUM":
        if min_value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:MINIMUM requires quantity_min_raw")
    elif relation == "MAXIMUM":
        if max_value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:MAXIMUM requires quantity_max_raw")
    elif relation == "RANGE":
        if min_value is None or max_value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:RANGE requires quantity_min_raw and quantity_max_raw")
        if value is not None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:RANGE forbids quantity_value_raw")
        if min_value is not None and max_value is not None:
            min_dec = _decimal_or_none(min_value)
            max_dec = _decimal_or_none(max_value)
            if min_dec is not None and max_dec is not None and min_dec > max_dec:
                errors.append(f"case:{case.case_id}:quantity:{qid}:RANGE requires min<=max")
    elif relation == "APPROXIMATE":
        if value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:APPROXIMATE requires quantity_value_raw")
    elif relation == "UNSPECIFIED":
        if value is None and min_value is None and max_value is None:
            errors.append(f"case:{case.case_id}:quantity:{qid}:UNSPECIFIED requires at least one numeric field")


def _append_required_text(errors: list[str], label: str, value: str) -> None:
    if not str(value or "").strip():
        errors.append(f"{label} is required")


def _is_safe_decimal(value: str) -> bool:
    return bool(_SAFE_DECIMAL_RE.fullmatch(str(value).strip()))


def _decimal_or_none(value: Decimal | str | None) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _is_sha256(value: str) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text.lower())


def _is_locator_valid(value: str) -> bool:
    text = str(value or "").strip()
    if not text or "|" not in text:
        return False
    left, right = text.split("|", 1)
    return bool(left.strip()) and bool(right.strip())


def _is_contiguous(haystack: str, needle: str) -> bool:
    return str(needle or "") in str(haystack or "")


def _grounded(haystack: str, needle: str) -> bool:
    return _normalize(needle) in _normalize(haystack)


def _normalize(value: Optional[str]) -> str:
    return " ".join(str(value or "").split()).upper()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
