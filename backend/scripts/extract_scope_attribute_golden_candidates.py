from __future__ import annotations

import argparse
import hashlib
import json

from sqlalchemy import select

from app.database import SessionLocal
from app.models import TenderScopeDetail


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract candidate technical-attribute Golden cases (read-only)")
    parser.add_argument("--tender-id", required=True, help="Tender ID to extract candidates from")
    parser.add_argument(
        "--output",
        default="evals/technical_attribute_golden_candidates.json",
        help="Output JSON path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(TenderScopeDetail)
                .where(TenderScopeDetail.tender_id == args.tender_id)
                .order_by(TenderScopeDetail.created_at.asc(), TenderScopeDetail.id.asc())
            ).scalars()
        )

    payload = {
        "candidate_set_version": "technical-attribute-golden-candidates-2026-09-08-001",
        "tender_id": args.tender_id,
        "case_count": len(rows),
        "cases": [],
    }

    for idx, row in enumerate(rows, start=1):
        source_text = row.source_excerpt or ""
        payload["cases"].append(
            {
                "case_id": f"candidate_{idx:03d}",
                "human_label_status": "PENDING",
                "evaluation_mode": "NO_ATTRIBUTES",
                "candidate_reason": "candidate extracted from TenderScopeDetail; requires human labeling",
                "tender_id": row.tender_id,
                "scope_detail_id": row.id,
                "source_document_id": row.source_document_id,
                "document_page_id": row.document_page_id,
                "page_number": row.page_number,
                "source_method": row.source_method,
                "source_artifact_key": row.source_artifact_key,
                "source_locator": row.source_locator,
                "source_contract_version": row.source_contract_version,
                "source_text": source_text,
                "source_text_sha256": _sha256(source_text),
                "expected_attributes": [],
            }
        )

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(f"Extracted {len(rows)} candidates to {args.output}")
    print("No provider execution, no Vision/OCR execution, and no database mutation performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
