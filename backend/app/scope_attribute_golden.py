from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from sqlalchemy.orm import Session

from app.models import TenderScopeDetail
from app.scope_attribute_semantic_discovery import (
    DiscoveredScopeAttribute,
    ScopeAttributeSemanticDiscoveryResult,
)
from app.scope_attributes import SCOPE_ATTRIBUTE_ALLOWED_RELATIONS

GOLDEN_LABEL_APPROVED = "APPROVED"
GOLDEN_LABEL_PENDING = "PENDING"
GOLDEN_ALLOWED_LABELS = {GOLDEN_LABEL_APPROVED, GOLDEN_LABEL_PENDING}

GOLDEN_MODE_STRICT = "STRICT"
GOLDEN_MODE_NO_ATTRIBUTES = "NO_ATTRIBUTES"
GOLDEN_MODE_REVIEW_ONLY = "REVIEW_ONLY"
GOLDEN_ALLOWED_MODES = {
    GOLDEN_MODE_STRICT,
    GOLDEN_MODE_NO_ATTRIBUTES,
    GOLDEN_MODE_REVIEW_ONLY,
}

GOLDEN_EVAL_STATUS_PASS = "PASS"
GOLDEN_EVAL_STATUS_FAIL = "FAIL"
GOLDEN_EVAL_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
GOLDEN_EVAL_STATUS_UNLABELED = "UNLABELED"
GOLDEN_EVAL_STATUS_INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class GoldenExpectedAttribute:
    golden_attribute_id: str
    attribute_name: str
    value_raw: str
    evidence_excerpt: str
    attribute_label_raw: Optional[str] = None
    unit_raw: Optional[str] = None
    relation: Optional[str] = None


@dataclass(frozen=True, slots=True)
class GoldenCase:
    case_id: str
    golden_version: str
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
    evaluation_mode: str
    human_label_status: str
    expected_attributes: tuple[GoldenExpectedAttribute, ...]
    candidate_reason: str
    source_contract_version: Optional[str] = None


@dataclass(frozen=True, slots=True)
class GoldenDataset:
    golden_version: str
    generated_at: str
    notes: Optional[str]
    cases: tuple[GoldenCase, ...]


@dataclass(frozen=True, slots=True)
class GoldenParentSnapshot:
    scope_detail_id: str
    tender_id: str
    source_document_id: str
    document_page_id: str
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    source_contract_version: Optional[str]


@dataclass(frozen=True, slots=True)
class GoldenValidationResult:
    is_valid: bool
    errors: tuple[str, ...]
    approved_count: int
    pending_count: int
    strict_count: int
    no_attributes_count: int
    review_only_count: int
    expected_attribute_count: int
    attribute_name_counts: tuple[tuple[str, int], ...]
    source_method_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class AttributeMatch:
    expected: GoldenExpectedAttribute
    discovered: DiscoveredScopeAttribute


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
    expected_attributes: tuple[GoldenExpectedAttribute, ...]
    discovered_attributes: tuple[DiscoveredScopeAttribute, ...]
    matches: tuple[AttributeMatch, ...]
    missing_expected: tuple[GoldenExpectedAttribute, ...]
    unexpected_discovered: tuple[DiscoveredScopeAttribute, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GoldenAggregateMetrics:
    total_cases: int
    pass_count: int
    fail_count: int
    review_required_count: int
    unlabeled_count: int
    invalid_count: int
    discovery_status_counts: tuple[tuple[str, int], ...]
    total_expected_attributes: int
    total_discovered_attributes: int
    total_matched_attributes: int
    overall_precision: float
    overall_recall: float
    hard_negative_pass_count: int
    hard_negative_total_count: int
    missing_expected_count: int
    unexpected_discovered_count: int
    total_elapsed_time_ms: int
    average_elapsed_time_ms: float
    max_elapsed_time_ms: int


class ParentResolver(Protocol):
    def __call__(self, case: GoldenCase) -> Optional[GoldenParentSnapshot]:
        ...


def load_technical_attribute_golden(path: str | Path) -> GoldenDataset:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[GoldenCase] = []
    for case in raw.get("cases", []):
        expected = tuple(
            GoldenExpectedAttribute(
                golden_attribute_id=item["golden_attribute_id"],
                attribute_name=item["attribute_name"],
                value_raw=item["value_raw"],
                evidence_excerpt=item["evidence_excerpt"],
                attribute_label_raw=item.get("attribute_label_raw"),
                unit_raw=item.get("unit_raw"),
                relation=item.get("relation"),
            )
            for item in case.get("expected_attributes", [])
        )
        cases.append(
            GoldenCase(
                case_id=case["case_id"],
                golden_version=case["golden_version"],
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
                evaluation_mode=case["evaluation_mode"],
                human_label_status=case["human_label_status"],
                expected_attributes=expected,
                candidate_reason=case["candidate_reason"],
                source_contract_version=case.get("source_contract_version"),
            )
        )

    return GoldenDataset(
        golden_version=raw["golden_version"],
        generated_at=raw["generated_at"],
        notes=raw.get("notes"),
        cases=tuple(cases),
    )


def validate_technical_attribute_golden(
    dataset: GoldenDataset,
    *,
    parent_resolver: Optional[ParentResolver] = None,
) -> GoldenValidationResult:
    errors: list[str] = []
    case_ids: set[str] = set()
    attribute_ids: set[str] = set()

    approved_count = 0
    pending_count = 0
    strict_count = 0
    no_attributes_count = 0
    review_only_count = 0
    expected_attribute_count = 0

    attribute_name_counts: dict[str, int] = {}
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
        elif case.evaluation_mode == GOLDEN_MODE_NO_ATTRIBUTES:
            no_attributes_count += 1
        else:
            review_only_count += 1

        if case.evaluation_mode == GOLDEN_MODE_STRICT and len(case.expected_attributes) == 0:
            errors.append(f"case:{case.case_id}:STRICT requires expected_attributes")
        if case.evaluation_mode == GOLDEN_MODE_NO_ATTRIBUTES and len(case.expected_attributes) != 0:
            errors.append(f"case:{case.case_id}:NO_ATTRIBUTES requires zero expected_attributes")

        if not _is_sha256(case.source_text_sha256):
            errors.append(f"case:{case.case_id}:invalid source_text_sha256 format")
        else:
            real_sha = _sha256(case.source_text)
            if real_sha != case.source_text_sha256:
                errors.append(
                    f"case:{case.case_id}:source_text_sha256 mismatch expected={case.source_text_sha256} actual={real_sha}"
                )

        if not _is_locator_valid(case.source_locator):
            errors.append(f"case:{case.case_id}:invalid source_locator: {case.source_locator}")

        if parent_resolver is not None:
            _validate_parent_alignment(case, parent_resolver(case), errors)

        source_method_counts[case.source_method] = source_method_counts.get(case.source_method, 0) + 1

        for expected in case.expected_attributes:
            expected_attribute_count += 1
            _append_required_text(errors, f"case:{case.case_id}:attribute_id", expected.golden_attribute_id)
            _append_required_text(errors, f"case:{case.case_id}:attribute_name", expected.attribute_name)
            _append_required_text(errors, f"case:{case.case_id}:value_raw", expected.value_raw)
            _append_required_text(errors, f"case:{case.case_id}:evidence_excerpt", expected.evidence_excerpt)

            attr_key = f"{case.case_id}:{expected.golden_attribute_id}"
            if attr_key in attribute_ids:
                errors.append(f"duplicate golden_attribute_id in case: {attr_key}")
            attribute_ids.add(attr_key)

            if not _is_contiguous(case.source_text, expected.evidence_excerpt):
                errors.append(
                    f"case:{case.case_id}:attribute:{expected.golden_attribute_id}:evidence_excerpt is not exact contiguous source span"
                )

            if not _grounded(expected.evidence_excerpt, expected.value_raw):
                errors.append(
                    f"case:{case.case_id}:attribute:{expected.golden_attribute_id}:value_raw is not grounded in evidence_excerpt"
                )

            if expected.attribute_label_raw is not None and not _grounded(expected.evidence_excerpt, expected.attribute_label_raw):
                errors.append(
                    f"case:{case.case_id}:attribute:{expected.golden_attribute_id}:attribute_label_raw is not grounded in evidence_excerpt"
                )

            if expected.unit_raw is not None and not (
                _grounded(expected.evidence_excerpt, expected.unit_raw)
                or _grounded(expected.value_raw, expected.unit_raw)
            ):
                errors.append(
                    f"case:{case.case_id}:attribute:{expected.golden_attribute_id}:unit_raw is not grounded"
                )

            if expected.relation is not None and expected.relation not in SCOPE_ATTRIBUTE_ALLOWED_RELATIONS:
                errors.append(
                    f"case:{case.case_id}:attribute:{expected.golden_attribute_id}:unsupported relation: {expected.relation}"
                )

            attribute_name_counts[expected.attribute_name] = attribute_name_counts.get(expected.attribute_name, 0) + 1

    return GoldenValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        approved_count=approved_count,
        pending_count=pending_count,
        strict_count=strict_count,
        no_attributes_count=no_attributes_count,
        review_only_count=review_only_count,
        expected_attribute_count=expected_attribute_count,
        attribute_name_counts=tuple(sorted(attribute_name_counts.items())),
        source_method_counts=tuple(sorted(source_method_counts.items())),
    )


def evaluate_case(
    case: GoldenCase,
    *,
    discovery_result: ScopeAttributeSemanticDiscoveryResult,
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
            expected_count=len(case.expected_attributes),
            discovered_count=len(discovered),
            matched_count=0,
            expected_attributes=case.expected_attributes,
            discovered_attributes=discovered,
            matches=(),
            missing_expected=case.expected_attributes,
            unexpected_discovered=discovered,
            errors=discovery_result.errors,
        )

    if discovery_result.status == "INVALID_OUTPUT":
        return GoldenCaseEvaluation(
            case_id=case.case_id,
            evaluation_mode=case.evaluation_mode,
            evaluation_status=GOLDEN_EVAL_STATUS_INVALID,
            discovery_status=discovery_result.status,
            elapsed_time_ms=elapsed_time_ms,
            expected_count=len(case.expected_attributes),
            discovered_count=len(discovered),
            matched_count=0,
            expected_attributes=case.expected_attributes,
            discovered_attributes=discovered,
            matches=(),
            missing_expected=case.expected_attributes,
            unexpected_discovered=discovered,
            errors=discovery_result.errors,
        )

    matches, missing_expected, unexpected_discovered = _match_expected_to_discovered(
        expected=case.expected_attributes,
        discovered=discovered,
        source_text=case.source_text,
    )

    if case.evaluation_mode == GOLDEN_MODE_NO_ATTRIBUTES:
        passed = len(discovered) == 0
    elif case.evaluation_mode == GOLDEN_MODE_STRICT:
        passed = len(missing_expected) == 0 and len(unexpected_discovered) == 0
    else:
        passed = len(missing_expected) == 0

    status = GOLDEN_EVAL_STATUS_PASS if passed else GOLDEN_EVAL_STATUS_FAIL

    return GoldenCaseEvaluation(
        case_id=case.case_id,
        evaluation_mode=case.evaluation_mode,
        evaluation_status=status,
        discovery_status=discovery_result.status,
        elapsed_time_ms=elapsed_time_ms,
        expected_count=len(case.expected_attributes),
        discovered_count=len(discovered),
        matched_count=len(matches),
        expected_attributes=case.expected_attributes,
        discovered_attributes=discovered,
        matches=tuple(matches),
        missing_expected=tuple(missing_expected),
        unexpected_discovered=tuple(unexpected_discovered),
        errors=discovery_result.errors,
    )


def aggregate_evaluations(evaluations: Sequence[GoldenCaseEvaluation]) -> GoldenAggregateMetrics:
    status_counts: dict[str, int] = {}
    discovery_counts: dict[str, int] = {}

    total_expected = 0
    total_discovered = 0
    total_matched = 0
    missing_expected_count = 0
    unexpected_discovered_count = 0

    hard_negative_total = 0
    hard_negative_pass = 0

    total_elapsed = 0
    max_elapsed = 0

    for evaluation in evaluations:
        status_counts[evaluation.evaluation_status] = status_counts.get(evaluation.evaluation_status, 0) + 1
        discovery_counts[evaluation.discovery_status] = discovery_counts.get(evaluation.discovery_status, 0) + 1

        total_expected += evaluation.expected_count
        total_discovered += evaluation.discovered_count
        total_matched += evaluation.matched_count
        missing_expected_count += len(evaluation.missing_expected)
        unexpected_discovered_count += len(evaluation.unexpected_discovered)

        if evaluation.evaluation_mode == GOLDEN_MODE_NO_ATTRIBUTES:
            hard_negative_total += 1
            if evaluation.evaluation_status == GOLDEN_EVAL_STATUS_PASS:
                hard_negative_pass += 1

        total_elapsed += evaluation.elapsed_time_ms
        if evaluation.elapsed_time_ms > max_elapsed:
            max_elapsed = evaluation.elapsed_time_ms

    precision = (total_matched / total_discovered) if total_discovered > 0 else 0.0
    recall = (total_matched / total_expected) if total_expected > 0 else 0.0

    total_cases = len(evaluations)
    average_elapsed = (total_elapsed / total_cases) if total_cases > 0 else 0.0

    return GoldenAggregateMetrics(
        total_cases=total_cases,
        pass_count=status_counts.get(GOLDEN_EVAL_STATUS_PASS, 0),
        fail_count=status_counts.get(GOLDEN_EVAL_STATUS_FAIL, 0),
        review_required_count=status_counts.get(GOLDEN_EVAL_STATUS_REVIEW_REQUIRED, 0),
        unlabeled_count=status_counts.get(GOLDEN_EVAL_STATUS_UNLABELED, 0),
        invalid_count=status_counts.get(GOLDEN_EVAL_STATUS_INVALID, 0),
        discovery_status_counts=tuple(sorted(discovery_counts.items())),
        total_expected_attributes=total_expected,
        total_discovered_attributes=total_discovered,
        total_matched_attributes=total_matched,
        overall_precision=precision,
        overall_recall=recall,
        hard_negative_pass_count=hard_negative_pass,
        hard_negative_total_count=hard_negative_total,
        missing_expected_count=missing_expected_count,
        unexpected_discovered_count=unexpected_discovered_count,
        total_elapsed_time_ms=total_elapsed,
        average_elapsed_time_ms=average_elapsed,
        max_elapsed_time_ms=max_elapsed,
    )


def build_parent_resolver(db: Session) -> ParentResolver:
    def _resolver(case: GoldenCase) -> Optional[GoldenParentSnapshot]:
        row = db.get(TenderScopeDetail, case.scope_detail_id)
        if row is None:
            return None
        return GoldenParentSnapshot(
            scope_detail_id=row.id,
            tender_id=row.tender_id,
            source_document_id=row.source_document_id,
            document_page_id=row.document_page_id,
            source_method=row.source_method,
            source_artifact_key=row.source_artifact_key,
            source_locator=row.source_locator,
            source_excerpt=row.source_excerpt,
            source_contract_version=row.source_contract_version,
        )

    return _resolver


def evaluate_golden_dataset(
    dataset: GoldenDataset,
    *,
    discover_case: Callable[[GoldenCase], tuple[ScopeAttributeSemanticDiscoveryResult, int]],
) -> tuple[GoldenAggregateMetrics, tuple[GoldenCaseEvaluation, ...]]:
    evaluations: list[GoldenCaseEvaluation] = []
    for case in dataset.cases:
        discovery_result, elapsed_ms = discover_case(case)
        evaluations.append(evaluate_case(case, discovery_result=discovery_result, elapsed_time_ms=elapsed_ms))

    aggregate = aggregate_evaluations(evaluations)
    return aggregate, tuple(evaluations)


def _validate_parent_alignment(
    case: GoldenCase,
    parent: Optional[GoldenParentSnapshot],
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
    if parent.source_method != case.source_method:
        errors.append(f"case:{case.case_id}:source_method mismatch")
    if parent.source_artifact_key != case.source_artifact_key:
        errors.append(f"case:{case.case_id}:source_artifact_key mismatch")
    if parent.source_locator != case.source_locator:
        errors.append(f"case:{case.case_id}:source_locator mismatch")

    if _normalize(parent.source_excerpt) != _normalize(case.source_text):
        errors.append(f"case:{case.case_id}:source_text does not match parent source_excerpt")


def _match_expected_to_discovered(
    *,
    expected: Sequence[GoldenExpectedAttribute],
    discovered: Sequence[DiscoveredScopeAttribute],
    source_text: str,
) -> tuple[list[AttributeMatch], list[GoldenExpectedAttribute], list[DiscoveredScopeAttribute]]:
    matches: list[AttributeMatch] = []
    missing_expected: list[GoldenExpectedAttribute] = []
    remaining_discovered = list(discovered)

    for expected_attr in expected:
        hit_index = -1
        for idx, discovered_attr in enumerate(remaining_discovered):
            if _attributes_match(expected_attr, discovered_attr, source_text=source_text):
                hit_index = idx
                break
        if hit_index == -1:
            missing_expected.append(expected_attr)
            continue

        matched = remaining_discovered.pop(hit_index)
        matches.append(AttributeMatch(expected=expected_attr, discovered=matched))

    return matches, missing_expected, remaining_discovered


def _attributes_match(
    expected: GoldenExpectedAttribute,
    discovered: DiscoveredScopeAttribute,
    *,
    source_text: str,
) -> bool:
    if expected.attribute_name != discovered.attribute_name:
        return False

    if not _safe_value_match(expected.value_raw, discovered.value_raw):
        return False

    expected_evidence = _normalize(expected.evidence_excerpt)
    discovered_evidence = _normalize(discovered.evidence_excerpt)
    source = _normalize(source_text)
    if expected_evidence not in source or discovered_evidence not in source:
        return False
    if expected_evidence != discovered_evidence and expected_evidence not in discovered_evidence and discovered_evidence not in expected_evidence:
        return False

    if expected.relation is not None:
        if (discovered.relation or "UNSPECIFIED") != expected.relation:
            return False

    if expected.unit_raw is not None:
        if not _safe_value_match(expected.unit_raw, discovered.unit_raw or ""):
            return False

    return True


def _safe_value_match(expected: str, discovered: str) -> bool:
    e = _normalize(expected)
    d = _normalize(discovered)
    if not e or not d:
        return False
    return e == d or e in d or d in e


def _append_required_text(errors: list[str], label: str, value: str) -> None:
    if not str(value or "").strip():
        errors.append(f"{label} is required")


def _is_locator_valid(locator: str) -> bool:
    text = str(locator or "").strip()
    if not text:
        return False
    if "|" not in text:
        return False
    left, right = text.split("|", 1)
    return bool(left.strip()) and bool(right.strip()) and ":" in right


def _grounded(haystack: str, needle: str) -> bool:
    return _normalize(needle) in _normalize(haystack)


def _is_contiguous(haystack: str, needle: str) -> bool:
    return str(needle or "") in str(haystack or "")


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).upper()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    text = str(value or "")
    if len(text) != 64:
        return False
    allowed = set("0123456789abcdef")
    return set(text.lower()).issubset(allowed)
