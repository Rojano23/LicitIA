from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.document_structure_orchestrator import EXECUTION_POLICY_AUTO, orchestrate_document_structure_available_only
from app.models import DocumentPage, DocumentPageStructureResolution, DocumentVisionAnalysis, DocumentVisionPageResult, PageOcrResult, TenderDocument, TenderScopeSegment

EXPECTED_DATABASE_FRAGMENT = "licitia_dev"
GOLDEN_TENDER_ID = "decd32ae-2c1f-4520-89bc-d845c986a7ba"
GOLDEN_DOCUMENT_ID = "acf31750-1d8d-4a0c-910c-fc3743930c57"
GOLDEN_DOCUMENT_NAME = "ANEXO B-4.pdf"
VISION_SCOPE_PROMPT_VERSION = "vision-structure-scope-2026-09-01-005"
VISION_SCOPE_PROMPT_VERSION_CURRENT = "vision-structure-scope-2026-09-03-006"


def _require_licitia_dev() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if EXPECTED_DATABASE_FRAGMENT not in database_url:
        raise RuntimeError(
            "DATABASE_URL must point to licitia_dev before running the Golden scope runner. "
            f"Current value: {database_url or '<unset>'}"
        )


def _header(execution_policy: str) -> None:
    print(f"DATABASE={os.environ.get('DATABASE_URL', '<unset>')}")
    print(f"TENDER_ID={GOLDEN_TENDER_ID}")
    print(f"DOCUMENT_ID={GOLDEN_DOCUMENT_ID}")
    print(f"DOCUMENT_NAME={GOLDEN_DOCUMENT_NAME}")
    print(f"EXECUTION_POLICY={execution_policy}")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _load_state() -> dict[str, Any]:
    with SessionLocal() as db:
        document = db.get(TenderDocument, GOLDEN_DOCUMENT_ID)
        if document is None:
            raise RuntimeError("Golden B-4 document not found in licitia_dev")

        pages = db.execute(
            select(DocumentPage).where(DocumentPage.document_id == GOLDEN_DOCUMENT_ID).order_by(DocumentPage.page_number.asc())
        ).scalars().all()
        page_ids = [page.id for page in pages]

        resolutions = db.execute(
            select(DocumentPageStructureResolution)
            .where(DocumentPageStructureResolution.source_document_id == GOLDEN_DOCUMENT_ID)
            .order_by(DocumentPageStructureResolution.page_number.asc(), DocumentPageStructureResolution.id.asc())
        ).scalars().all()
        segments = db.execute(
            select(TenderScopeSegment)
            .where(TenderScopeSegment.source_document_id == GOLDEN_DOCUMENT_ID)
            .order_by(TenderScopeSegment.page_number.asc(), TenderScopeSegment.sequence_index.asc(), TenderScopeSegment.id.asc())
        ).scalars().all()
        ocr_rows = db.execute(
            select(PageOcrResult)
            .where(PageOcrResult.document_page_id.in_(page_ids))
            .order_by(PageOcrResult.document_page_id.asc(), PageOcrResult.engine.asc())
        ).scalars().all()
        vision_analyses = db.execute(
            select(DocumentVisionAnalysis)
            .where(DocumentVisionAnalysis.document_id == GOLDEN_DOCUMENT_ID)
            .order_by(DocumentVisionAnalysis.id.asc())
        ).scalars().all()
        vision_pages = db.execute(
            select(DocumentPage.page_number, DocumentVisionPageResult.status, DocumentVisionAnalysis.prompt_version, DocumentVisionPageResult.structured_json)
            .join(DocumentVisionPageResult, DocumentVisionPageResult.document_page_id == DocumentPage.id)
            .join(DocumentVisionAnalysis, DocumentVisionAnalysis.id == DocumentVisionPageResult.analysis_id)
            .where(DocumentPage.document_id == GOLDEN_DOCUMENT_ID)
            .order_by(DocumentPage.page_number.asc(), DocumentVisionAnalysis.id.asc(), DocumentVisionPageResult.id.asc())
        ).all()

        page_state: list[dict[str, Any]] = []
        for page in pages:
            ocr_items = [
                {
                    "engine": row.engine,
                    "status": row.status,
                    "scope": row.scope,
                    "text": row.text[:120],
                }
                for row in ocr_rows
                if row.document_page_id == page.id
            ]
            vision_items = []
            for page_number, status, prompt_version, structured_json in vision_pages:
                if page_number != page.page_number:
                    continue
                continuity_quality = (structured_json or {}).get("_continuity_state_quality")
                item_segments = [
                    {
                        "item_number": segment.get("item_number"),
                        "starts_on_this_page": segment.get("starts_on_this_page"),
                    }
                    for segment in (structured_json or {}).get("item_segments", [])
                ]
                vision_items.append(
                    {
                        "status": status,
                        "prompt_version": prompt_version,
                        "continuity_quality": continuity_quality,
                        "open_item_at_page_end": (structured_json or {}).get("open_item_at_page_end"),
                        "item_segments": item_segments,
                        "compatible_with_current_scope_prompt": prompt_version == VISION_SCOPE_PROMPT_VERSION_CURRENT and status in {"COMPLETED", "PARTIAL"} and continuity_quality == "VALID",
                        "compatible_with_vision_005": prompt_version == VISION_SCOPE_PROMPT_VERSION and status in {"COMPLETED", "PARTIAL"} and continuity_quality == "VALID",
                    }
                )

            page_state.append(
                {
                    "page_number": page.page_number,
                    "document_page_id": page.id,
                    "status": page.status,
                    "ocr_rows": ocr_items,
                    "vision_rows": vision_items,
                }
            )

        return {
            "document": {
                "id": document.id,
                "original_filename": document.original_filename,
                "page_count": document.page_count,
                "tender_id": document.tender_id,
            },
            "pages": page_state,
            "resolutions": [
                {
                    "page_number": row.page_number,
                    "status": row.status,
                    "selected_source_method": row.selected_source_method,
                    "review_required": row.review_required,
                    "reason": row.reason,
                }
                for row in resolutions
            ],
            "segments": [
                {
                    "page_number": row.page_number,
                    "sequence_index": row.sequence_index,
                    "candidate_item_key": row.candidate_item_key,
                    "candidate_item_raw_label": row.candidate_item_raw_label,
                    "tender_item_id": row.tender_item_id,
                    "source_method": row.source_method,
                    "link_reason": row.link_reason,
                    "source_locator": row.source_locator,
                    "review_required": row.review_required,
                }
                for row in segments
            ],
            "counts": {
                "pages": len(pages),
                "resolutions": len(resolutions),
                "segments": len(segments),
                "ocr_rows": len(ocr_rows),
                "vision_analyses": len(vision_analyses),
            },
        }


def preview() -> None:
    _require_licitia_dev()
    _header("AUTO")
    state = _load_state()
    print("PREVIEW_STATE")
    print(_json(state))


def run_auto() -> None:
    _require_licitia_dev()
    _header(EXECUTION_POLICY_AUTO)
    preview_state = _load_state()
    print("PREVIEW_STATE")
    print(_json(preview_state))
    print("RUNNING_AUTO")

    with SessionLocal() as db:
        result = orchestrate_document_structure_available_only(
            db,
            tender_id=GOLDEN_TENDER_ID,
            document_id=GOLDEN_DOCUMENT_ID,
            execution_policy=EXECUTION_POLICY_AUTO,
        )
        db.commit()

        print("RUN_RESULT")
        print(
            _json(
                {
                    "summary": {
                        "scope_segments_persisted": result.scope_segments_persisted,
                        "page_results": [
                            {
                                "page_number": row.page_number,
                                "status": row.status,
                                "selected_source_method": row.selected_source_method,
                                "reason": row.reason,
                                "review_required": row.review_required,
                                "needs_provider": row.needs_provider,
                            }
                            for row in result.page_results
                        ],
                    }
                }
            )
        )


def verify() -> None:
    _require_licitia_dev()
    _header("READ_ONLY_VERIFY")
    state = _load_state()
    print("VERIFY_STATE")
    print(_json(state))


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden B-4 scope acceptance runner for licitia_dev.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("preview", help="Show current persisted Golden state without mutating the database.")
    subparsers.add_parser("run", help="Run AUTO orchestration against the Golden B-4 document.")
    subparsers.add_parser("verify", help="Print read-only post-run state for acceptance checks.")
    args = parser.parse_args()

    command = args.command or "preview"
    if command == "preview":
        preview()
    elif command == "run":
        run_auto()
    elif command == "verify":
        verify()
    else:
        raise RuntimeError(f"Unsupported command: {command}")


if __name__ == "__main__":
    main()
