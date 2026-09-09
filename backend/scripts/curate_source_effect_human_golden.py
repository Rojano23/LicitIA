#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = BACKEND_ROOT / "evals/source_effect_golden_candidate_t001_v1.json"
PRIMARY_OUTPUT_PATH = BACKEND_ROOT / "evals/source_effect_golden_v1.json"
DUPLICATE_OUTPUT_PATH = BACKEND_ROOT / "evals/source_effect_duplicate_artifact_robustness_v1.json"
REPORT_OUTPUT_PATH = BACKEND_ROOT / "reports/source_effect_golden_v1_frozen_review.md"

HUMAN_APPROVED = "HUMAN_APPROVED"
FROZEN_LIMITED_COVERAGE = "FROZEN_LIMITED_COVERAGE"
PRIMARY_GOLDEN_VERSION = "source-effect-golden-2026-09-09-001"
DUPLICATE_GOLDEN_VERSION = "source-effect-duplicate-artifact-robustness-2026-09-09-001"

PRIMARY_CASE_IDS = [
    "se_gc_001",
    "se_gc_002",
    "se_gc_003",
    "se_gc_004",
    "se_gc_005",
    "se_gc_006",
    "se_gc_007",
    "se_gc_008",
    "se_gc_009",
    "se_gc_010",
    "se_gc_011",
    "se_gc_013",
    "se_gc_015",
    "se_gc_017",
    "se_gc_019",
]

DUPLICATE_CASE_IDS = ["se_gc_012", "se_gc_014", "se_gc_016", "se_gc_018"]

DUPLICATE_SELECTIONS = [
    {
        "canonical_case_id": "se_gc_013",
        "alternate_case_id": "se_gc_014",
        "reason": "Canonical kept due to cleaner section label and less OCR ambiguity.",
    },
    {
        "canonical_case_id": "se_gc_015",
        "alternate_case_id": "se_gc_016",
        "reason": "Canonical kept due to cleaner section and document wording consistency.",
    },
    {
        "canonical_case_id": "se_gc_017",
        "alternate_case_id": "se_gc_018",
        "reason": "Canonical kept due to cleaner wording and less punctuation noise.",
    },
]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_payload_for_integrity(payload: dict) -> dict:
    canonical_cases: list[dict] = []
    for raw_case in payload.get("cases", []):
        canonical_cases.append(
            {
                "case_id": raw_case.get("case_id"),
                "tender_id": raw_case.get("tender_id"),
                "acting_document_id": raw_case.get("acting_document_id"),
                "document_page_id": raw_case.get("document_page_id"),
                "source_method": raw_case.get("source_method"),
                "source_artifact_key": raw_case.get("source_artifact_key"),
                "source_locator": raw_case.get("source_locator"),
                "source_excerpt": raw_case.get("source_excerpt"),
                "source_excerpt_sha256": raw_case.get("source_excerpt_sha256"),
                "candidate_label_status": raw_case.get("candidate_label_status"),
                "expected_discovery_status": raw_case.get("expected_discovery_status"),
                "expected_effects": [
                    {
                        "expected_effect_type": item.get("expected_effect_type"),
                        "expected_effect_scope": item.get("expected_effect_scope"),
                        "expected_affected_document_ref_raw": item.get("expected_affected_document_ref_raw"),
                        "expected_affected_document_id": item.get("expected_affected_document_id"),
                        "expected_affected_locator_raw": item.get("expected_affected_locator_raw"),
                        "expected_effective_date_raw": item.get("expected_effective_date_raw"),
                        "expected_review_required": bool(item.get("expected_review_required", False)),
                    }
                    for item in raw_case.get("expected_effects", [])
                ],
                "expected_review_required": bool(raw_case.get("expected_review_required", False)),
                "category": raw_case.get("category"),
                "human_note": raw_case.get("human_note"),
                "evidence_note": raw_case.get("evidence_note"),
            }
        )

    return {
        "golden_version": payload.get("golden_version"),
        "tender_id": payload.get("tender_id"),
        "label_status": payload.get("label_status"),
        "dataset_status": payload.get("dataset_status"),
        "coverage_certifications": list(payload.get("coverage_certifications", [])),
        "coverage_gaps": list(payload.get("coverage_gaps", [])),
        "coverage_gap_effect_types": list(payload.get("coverage_gap_effect_types", [])),
        "coverage_gap_effect_scopes": list(payload.get("coverage_gap_effect_scopes", [])),
        "excluded_duplicate_case_ids": list(payload.get("excluded_duplicate_case_ids", [])),
        "duplicate_artifact_robustness_dataset": payload.get("duplicate_artifact_robustness_dataset"),
        "cases": canonical_cases,
    }


def _dataset_integrity_sha256(payload: dict) -> str:
    canonical_payload = _canonical_payload_for_integrity(payload)
    canonical_json = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(canonical_json)


def _configure_positive_cases(case_by_id: dict[str, dict]) -> None:
    case_001 = case_by_id["se_gc_001"]
    case_001["expected_discovery_status"] = "REVIEW_REQUIRED"
    case_001["expected_review_required"] = True
    case_001["category"] = "REVIEW_REQUIRED"
    case_001["expected_effects"] = [
        {
            "expected_effect_type": "AMENDS",
            "expected_effect_scope": "PARTIAL",
            "expected_affected_document_ref_raw": None,
            "expected_affected_document_id": None,
            "expected_affected_locator_raw": "inciso i",
            "expected_effective_date_raw": None,
            "expected_review_required": True,
        }
    ]
    case_001["human_note"] = "Human curated: REVIEW_REQUIRED positive with partial amendment anchored at inciso i."

    case_011 = case_by_id["se_gc_011"]
    case_011["expected_discovery_status"] = "REVIEW_REQUIRED"
    case_011["expected_review_required"] = True
    case_011["category"] = "REVIEW_REQUIRED"
    case_011["expected_effects"] = [
        {
            "expected_effect_type": "AMENDS",
            "expected_effect_scope": "PARTIAL",
            "expected_affected_document_ref_raw": None,
            "expected_affected_document_id": None,
            "expected_affected_locator_raw": "Apartado 3.1.5",
            "expected_effective_date_raw": None,
            "expected_review_required": True,
        },
        {
            "expected_effect_type": "CLARIFIES",
            "expected_effect_scope": "PARTIAL",
            "expected_affected_document_ref_raw": None,
            "expected_affected_document_id": None,
            "expected_affected_locator_raw": "Disposiciones Transitorias",
            "expected_effective_date_raw": None,
            "expected_review_required": True,
        },
    ]
    case_011["human_note"] = (
        "Human curated: REVIEW_REQUIRED positive with two partial effects "
        "(Apartado 3.1.5 and Disposiciones Transitorias)."
    )


def _apply_human_labels(cases: list[dict]) -> None:
    for case in cases:
        case["candidate_label_status"] = HUMAN_APPROVED


def _build_summary(cases: list[dict], *, duplicates_excluded: list[str]) -> dict:
    category_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    positive_cases = 0
    expected_effects = 0

    for case in cases:
        category = str(case.get("category", "HARD_NEGATIVE"))
        category_counts[category] = category_counts.get(category, 0) + 1

        status = str(case.get("expected_discovery_status", "NO_EFFECTS"))
        status_counts[status] = status_counts.get(status, 0) + 1

        effects = list(case.get("expected_effects", []))
        expected_effects += len(effects)
        if effects:
            positive_cases += 1

    return {
        "cases_total": len(cases),
        "positive_cases": positive_cases,
        "expected_effects_total": expected_effects,
        "category_counts": dict(sorted(category_counts.items())),
        "expected_discovery_status_counts": dict(sorted(status_counts.items())),
        "excluded_duplicate_case_ids": duplicates_excluded,
    }


def _build_primary_dataset(candidate: dict) -> dict:
    case_by_id = {item["case_id"]: copy.deepcopy(item) for item in candidate["cases"]}
    _configure_positive_cases(case_by_id)

    case_by_id["se_gc_002"]["category"] = "DESCRIPTIVE_NEGATIVE"
    case_by_id["se_gc_002"]["human_note"] = "Human curated: descriptive negative (announcement context, no actionable source effect)."

    primary_cases = [case_by_id[case_id] for case_id in PRIMARY_CASE_IDS]
    _apply_human_labels(primary_cases)

    generated_at = datetime.now(timezone.utc).isoformat()
    primary = {
        "golden_version": PRIMARY_GOLDEN_VERSION,
        "generated_at": generated_at,
        "tender_id": candidate["tender_id"],
        "notes": "Frozen human-curated primary golden for Tender #001 with limited coverage.",
        "label_status": HUMAN_APPROVED,
        "dataset_status": FROZEN_LIMITED_COVERAGE,
        "coverage_certifications": [
            "Primary golden is human-reviewed and frozen for curated cases only.",
            "Source excerpts preserve immutable sha256 traceability from candidate pack.",
            "Duplicate artifact alternates are intentionally excluded from primary metrics.",
        ],
        "coverage_gaps": [
            "Coverage remains limited to currently persisted Tender #001 source-effect artifacts.",
            "No claim is made for full recall over all possible source-effect language variants.",
            "Additional positive MATERIALIZED examples are still missing in this frozen cut.",
        ],
        "coverage_gap_effect_types": ["REVOKES", "DEFERS", "SUSPENDS"],
        "coverage_gap_effect_scopes": ["GLOBAL", "TEMPORAL"],
        "excluded_duplicate_case_ids": DUPLICATE_CASE_IDS,
        "duplicate_artifact_robustness_dataset": str(DUPLICATE_OUTPUT_PATH.relative_to(BACKEND_ROOT)),
        "duplicate_selection_policy": DUPLICATE_SELECTIONS,
        "cases": primary_cases,
    }
    primary["summary"] = _build_summary(primary_cases, duplicates_excluded=DUPLICATE_CASE_IDS)
    primary["integrity_sha256"] = _dataset_integrity_sha256(primary)
    return primary


def _build_duplicate_dataset(candidate: dict) -> dict:
    case_by_id = {item["case_id"]: copy.deepcopy(item) for item in candidate["cases"]}
    duplicate_cases = [case_by_id[case_id] for case_id in DUPLICATE_CASE_IDS]
    _apply_human_labels(duplicate_cases)

    generated_at = datetime.now(timezone.utc).isoformat()
    duplicate_dataset = {
        "golden_version": DUPLICATE_GOLDEN_VERSION,
        "generated_at": generated_at,
        "tender_id": candidate["tender_id"],
        "notes": "Duplicate artifact robustness set; excluded from primary baseline metrics.",
        "label_status": HUMAN_APPROVED,
        "dataset_status": "DUPLICATE_ARTIFACT_ROBUSTNESS",
        "paired_with_primary_dataset": str(PRIMARY_OUTPUT_PATH.relative_to(BACKEND_ROOT)),
        "duplicate_selection_policy": DUPLICATE_SELECTIONS,
        "cases": duplicate_cases,
    }
    duplicate_dataset["summary"] = {
        "cases_total": len(duplicate_cases),
        "excluded_from_primary_metrics": True,
        "alternate_case_ids": DUPLICATE_CASE_IDS,
    }
    duplicate_dataset["integrity_sha256"] = _dataset_integrity_sha256(duplicate_dataset)
    return duplicate_dataset


def _render_report(primary: dict, duplicate_dataset: dict) -> str:
    lines: list[str] = []
    lines.append("# Source Effect Golden v1 Frozen Review")
    lines.append("")
    lines.append("## Dataset Status")
    lines.append("")
    lines.append(f"- primary_dataset: {PRIMARY_OUTPUT_PATH.relative_to(BACKEND_ROOT)}")
    lines.append(f"- duplicate_robustness_dataset: {DUPLICATE_OUTPUT_PATH.relative_to(BACKEND_ROOT)}")
    lines.append(f"- label_status: {primary['label_status']}")
    lines.append(f"- dataset_status: {primary['dataset_status']}")
    lines.append(f"- integrity_sha256: {primary['integrity_sha256']}")
    lines.append("")
    lines.append("## Primary Coverage Snapshot")
    lines.append("")
    lines.append(f"- cases_total: {primary['summary']['cases_total']}")
    lines.append(f"- positive_cases: {primary['summary']['positive_cases']}")
    lines.append(f"- expected_effects_total: {primary['summary']['expected_effects_total']}")
    lines.append(f"- category_counts: {json.dumps(primary['summary']['category_counts'], ensure_ascii=False)}")
    lines.append(
        "- expected_discovery_status_counts: "
        f"{json.dumps(primary['summary']['expected_discovery_status_counts'], ensure_ascii=False)}"
    )
    lines.append("")
    lines.append("## Human Curation Decisions")
    lines.append("")
    lines.append("- se_gc_001 promoted to REVIEW_REQUIRED positive with one expected AMENDS/PARTIAL effect at locator 'inciso i'.")
    lines.append(
        "- se_gc_011 promoted to REVIEW_REQUIRED positive with two expected PARTIAL effects "
        "(AMENDS at 'Apartado 3.1.5', CLARIFIES at 'Disposiciones Transitorias')."
    )
    lines.append("- se_gc_012 removed from primary and moved to duplicate robustness.")
    lines.append("- se_gc_002 reclassified from HARD_NEGATIVE to DESCRIPTIVE_NEGATIVE.")
    lines.append("- Canonical selections: 013 over 014, 015 over 016, 017 over 018.")
    lines.append("")
    lines.append("## Duplicate Artifact Separation")
    lines.append("")
    lines.append(f"- duplicate_cases_total: {duplicate_dataset['summary']['cases_total']}")
    lines.append(f"- duplicate_case_ids: {json.dumps(DUPLICATE_CASE_IDS)}")
    lines.append("- These cases are excluded from primary aggregate metrics by design.")
    lines.append("")
    lines.append("## Limited Coverage Freeze")
    lines.append("")
    for item in primary["coverage_certifications"]:
        lines.append(f"- certification: {item}")
    for item in primary["coverage_gaps"]:
        lines.append(f"- gap: {item}")
    lines.append(f"- gap_effect_types: {json.dumps(primary['coverage_gap_effect_types'])}")
    lines.append(f"- gap_effect_scopes: {json.dumps(primary['coverage_gap_effect_scopes'])}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))

    primary = _build_primary_dataset(candidate)
    duplicate_dataset = _build_duplicate_dataset(candidate)
    report_markdown = _render_report(primary, duplicate_dataset)

    PRIMARY_OUTPUT_PATH.write_text(
        json.dumps(primary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    DUPLICATE_OUTPUT_PATH.write_text(
        json.dumps(duplicate_dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_OUTPUT_PATH.write_text(report_markdown, encoding="utf-8")

    print(f"WROTE {PRIMARY_OUTPUT_PATH.relative_to(BACKEND_ROOT)}")
    print(f"WROTE {DUPLICATE_OUTPUT_PATH.relative_to(BACKEND_ROOT)}")
    print(f"WROTE {REPORT_OUTPUT_PATH.relative_to(BACKEND_ROOT)}")
    print(f"PRIMARY_INTEGRITY_SHA256={primary['integrity_sha256']}")
    print(f"DUPLICATE_INTEGRITY_SHA256={duplicate_dataset['integrity_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
