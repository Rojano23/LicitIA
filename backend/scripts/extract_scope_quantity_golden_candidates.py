from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.database import SessionLocal
from app.models import DocumentPage, Tender, TenderScopeDetail
from app.scope_quantities import (
    SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    SCOPE_QUANTITY_MEASURE_KIND_LOT,
    SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    SCOPE_QUANTITY_RELATION_EXACT,
)
from app.scope_quantity_golden import GOLDEN_LABEL_PENDING, GOLDEN_MODE_NO_QUANTITIES, GOLDEN_MODE_REVIEW_REQUIRED, GOLDEN_MODE_STRICT

DEFAULT_EXTERNAL_REFERENCE = "SNR-CAD-265-CA-S-2026"
DEFAULT_GOLDEN_VERSION = "scope-quantity-golden-2026-09-08-001"
DEFAULT_OUTPUT = "evals/scope_quantity_golden_v1.json"

_TERMINAL_QUANTITY_PATTERN = re.compile(r"\((\d+(?:\.\d+)?)\s+([^()]+?)\)\.?\s*$", re.IGNORECASE)

_WORD_QUANTITY_HINTS = (
    " UNA ",
    " UN ",
    " DOS ",
    " TRES ",
    " CUATRO ",
    " COPIA",
    " COPIAS",
    " PIEZA",
    " PIEZAS",
    " SERVICIO",
    " SERVICIOS",
    " DIAS",
    " DÍAS",
)

_FORBIDDEN_LITERAL_PATTERNS = (
    r"\b\d+\s*-\s*\d+\s*VCA\b",
    r"\b\d+\s*-\s*\d+\s*VDC\b",
    r"\b[A-Z]{2,}\d+(?:[-/][A-Z0-9]+)+\b",
    r"\b[A-Z]{2,}\d+[A-Z0-9]*\b",
)

_UNIT_TO_MEASURE_KIND = {
    "PIEZA": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PIEZAS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PZA": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PZAS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "UNIDAD": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "UNIDADES": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "SERVICIO": SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    "SERVICIOS": SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    "LOTE": SCOPE_QUANTITY_MEASURE_KIND_LOT,
    "LOTES": SCOPE_QUANTITY_MEASURE_KIND_LOT,
    "DIA": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "DIAS": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "DÍA": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "DÍAS": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "METRO": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    "METROS": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    "M": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
}


@dataclass(frozen=True)
class _QuantityProposal:
    quantity_raw: str
    unit_raw: str
    measure_kind: str
    relation: str
    quantity_value_raw: str
    evidence_excerpt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract HUMAN-PENDING scope quantity Golden candidates from real TenderScopeDetail evidence"
    )
    parser.add_argument("--external-reference", default=DEFAULT_EXTERNAL_REFERENCE, help="Tender external_reference")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output golden JSON path")
    parser.add_argument("--golden-version", default=DEFAULT_GOLDEN_VERSION, help="Golden version label")
    return parser.parse_args()


def _normalize(value: str) -> str:
    return " ".join(str(value or "").split()).upper()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _find_terminal_quantity(text: str) -> Optional[_QuantityProposal]:
    match = _TERMINAL_QUANTITY_PATTERN.search(text or "")
    if match is None:
        return None

    qty = match.group(1).strip()
    unit = match.group(2).strip().rstrip(".")
    unit_key = _normalize(unit)
    measure_kind = _UNIT_TO_MEASURE_KIND.get(unit_key)
    if measure_kind is None:
        return None

    Decimal(qty)
    return _QuantityProposal(
        quantity_raw=qty,
        unit_raw=unit,
        measure_kind=measure_kind,
        relation=SCOPE_QUANTITY_RELATION_EXACT,
        quantity_value_raw=qty,
        evidence_excerpt=match.group(0).strip(),
    )


def _contains_quantity_like_language(text: str) -> bool:
    normalized = f" {_normalize(text)} "
    has_digits = bool(re.search(r"\d", normalized))
    has_word_hints = any(token in normalized for token in _WORD_QUANTITY_HINTS)
    return has_digits or has_word_hints


def _extract_forbidden_literals(text: str, quantity: Optional[_QuantityProposal]) -> list[str]:
    found: list[str] = []
    for pattern in _FORBIDDEN_LITERAL_PATTERNS:
        for match in re.finditer(pattern, text or ""):
            literal = match.group(0).strip()
            if not literal:
                continue
            if quantity is not None and _normalize(literal) == _normalize(quantity.quantity_raw):
                continue
            found.append(literal)

    deduped = []
    seen = set()
    for literal in found:
        key = _normalize(literal)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(literal)
    return deduped


def build_scope_quantity_golden_payload(*, external_reference: str, golden_version: str) -> dict:
    with SessionLocal() as db:
        tender = db.execute(select(Tender).where(Tender.external_reference == external_reference)).scalar_one_or_none()
        if tender is None:
            raise ValueError(f"Tender with external_reference '{external_reference}' was not found")

        rows = list(
            db.execute(
                select(TenderScopeDetail, DocumentPage)
                .join(DocumentPage, DocumentPage.id == TenderScopeDetail.document_page_id)
                .where(TenderScopeDetail.tender_id == tender.id)
                .order_by(DocumentPage.page_number.asc(), TenderScopeDetail.source_locator.asc(), TenderScopeDetail.id.asc())
            ).all()
        )

    cases = []
    strict_count = 0
    no_quantities_count = 0
    review_required_count = 0

    for index, (detail, page) in enumerate(rows, start=1):
        source_text = detail.source_excerpt or ""
        proposal = _find_terminal_quantity(source_text)
        has_quantity_like = _contains_quantity_like_language(source_text)

        if proposal is not None:
            evaluation_mode = GOLDEN_MODE_STRICT
            strict_count += 1
            expected_quantities = [
                {
                    "golden_quantity_id": f"gq-{index:03d}-001",
                    "quantity_raw": proposal.quantity_raw,
                    "unit_raw": proposal.unit_raw,
                    "measure_kind": proposal.measure_kind,
                    "relation": proposal.relation,
                    "quantity_value_raw": proposal.quantity_value_raw,
                    "quantity_min_raw": None,
                    "quantity_max_raw": None,
                    "evidence_excerpt": proposal.evidence_excerpt,
                }
            ]
            candidate_reason = "Propuesta determinista: patrón terminal '(N UNIDAD)' detectado en evidencia real. Requiere aprobación humana."
        elif has_quantity_like:
            evaluation_mode = GOLDEN_MODE_REVIEW_REQUIRED
            review_required_count += 1
            expected_quantities = []
            candidate_reason = (
                "Sin patrón determinista exacto, pero hay lenguaje cantidad-like en evidencia; se propone revisión humana explícita."
            )
        else:
            evaluation_mode = GOLDEN_MODE_NO_QUANTITIES
            no_quantities_count += 1
            expected_quantities = []
            candidate_reason = "Sin patrón determinista de cantidad ejecutable en evidencia real; propuesta NO_QUANTITIES pendiente de revisión humana."

        forbidden_literals = _extract_forbidden_literals(source_text, proposal)

        coverage_tags: list[str] = []
        if proposal is not None:
            coverage_tags.append(proposal.measure_kind)
        if forbidden_literals:
            coverage_tags.append("MIXED_TECHNICAL_NUMBER")
            coverage_tags.append("IDENTIFIER_NEGATIVE")
        if detail.domain == "DELIVERABLE":
            coverage_tags.append("DELIVERABLE")
            coverage_tags.append("HARD_NEGATIVE")

        cases.append(
            {
                "case_id": f"sq_golden_case_{index:03d}",
                "golden_version": golden_version,
                "human_label_status": GOLDEN_LABEL_PENDING,
                "evaluation_mode": evaluation_mode,
                "tender_id": detail.tender_id,
                "scope_detail_id": detail.id,
                "source_document_id": detail.source_document_id,
                "document_page_id": detail.document_page_id,
                "page_number": int(page.page_number),
                "source_method": detail.source_method,
                "source_artifact_key": detail.source_artifact_key,
                "source_locator": detail.source_locator,
                "source_text": source_text,
                "source_text_sha256": _sha256(source_text),
                "source_contract_version": detail.source_contract_version,
                "source_analysis_id": detail.source_analysis_id,
                "source_page_result_id": detail.source_page_result_id,
                "expected_quantities": expected_quantities,
                "forbidden_quantity_literals": forbidden_literals,
                "coverage_tags": list(dict.fromkeys(coverage_tags)),
                "candidate_reason": candidate_reason,
            }
        )

    return {
        "golden_version": golden_version,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "notes": (
            "DRAFT HUMAN GOLDEN. All labels are PENDING by design. "
            "Cases are real persisted TenderScopeDetail evidence from licitia_dev and require human domain approval."
        ),
        "external_reference": external_reference,
        "tender_id": rows[0][0].tender_id if rows else None,
        "summary": {
            "cases_total": len(cases),
            "pending": len(cases),
            "approved": 0,
            "strict_proposals": strict_count,
            "no_quantities_proposals": no_quantities_count,
            "review_required_proposals": review_required_count,
        },
        "cases": cases,
    }


def main() -> int:
    args = parse_args()

    payload = build_scope_quantity_golden_payload(
        external_reference=args.external_reference,
        golden_version=args.golden_version,
    )

    if any(case["human_label_status"] != GOLDEN_LABEL_PENDING for case in payload["cases"]):
        raise RuntimeError("Invariant violated: generator produced a non-PENDING human_label_status")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_mode = Counter(case["evaluation_mode"] for case in payload["cases"])
    print(f"Golden quantity draft generated at: {output_path}")
    print(f"tender_id={payload['tender_id']} external_reference={payload['external_reference']}")
    print(f"cases_total={len(payload['cases'])} pending={len(payload['cases'])} approved=0")
    print(f"mode_distribution={dict(sorted(by_mode.items()))}")
    print("No provider execution performed. No DB mutation performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
