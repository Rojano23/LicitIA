from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.document_intelligence_audit import AUDIT_VERSION, generate_document_intelligence_audit
from app.document_references import (
    HUMAN_ACTION_RESOLVE,
    RELATIONSHIP_MODIFIES,
    RELATIONSHIP_REFERENCES,
    RESOLUTION_AUTO,
    RESOLUTION_HUMAN,
)
from app.models import DocumentReference, TenderDocument

RELATIONSHIP_BASELINE_VERSION = "mvp-03.1"


def _resolution_origin(auto_count: int, human_count: int) -> str:
    if auto_count > 0 and human_count > 0:
        return "AUTO_HUMAN"
    if human_count > 0:
        return "HUMAN"
    return "AUTO"


def generate_tender_relationship_baseline(db: Session, tender_id: str) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc)
    audit = generate_document_intelligence_audit(db, tender_id)

    current_documents = (
        db.execute(
            select(TenderDocument)
            .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
            .order_by(TenderDocument.imported_at.asc())
        )
        .scalars()
        .all()
    )
    current_ids = {document.id for document in current_documents}

    references = (
        db.execute(
            select(DocumentReference)
            .where(DocumentReference.source_document_id.in_(list(current_ids) or [""]))
            .options(selectinload(DocumentReference.document_page))
            .order_by(DocumentReference.created_at.asc())
        )
        .scalars()
        .all()
    )

    support_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for reference in references:
        target_id = None
        status = reference.resolution_status

        if reference.human_decision == HUMAN_ACTION_RESOLVE and reference.human_target_document_id:
            target_id = reference.human_target_document_id
            status = RESOLUTION_HUMAN
        elif reference.resolution_status in {RESOLUTION_AUTO, RESOLUTION_HUMAN} and reference.resolved_target_document_id:
            target_id = reference.resolved_target_document_id

        if not target_id:
            continue
        if target_id not in current_ids:
            continue

        edge_key = (reference.source_document_id, reference.relationship_hint, target_id)
        record = support_index.setdefault(
            edge_key,
            {
                "pages": set(),
                "auto_count": 0,
                "human_count": 0,
            },
        )
        if reference.document_page is not None and reference.document_page.page_number is not None:
            record["pages"].add(reference.document_page.page_number)
        if status == RESOLUTION_HUMAN:
            record["human_count"] += 1
        else:
            record["auto_count"] += 1

    document_map: list[dict[str, Any]] = []
    for edge in audit["relationship_summary"]["edges"]:
        edge_key = (
            edge["source_document_id"],
            edge["relationship_type"],
            edge["target_document_id"],
        )
        support = support_index.get(edge_key, {"pages": set(), "auto_count": 0, "human_count": 0})
        document_map.append(
            {
                "source_document_id": edge["source_document_id"],
                "source_filename": edge["source_document_filename"],
                "relationship_type": edge["relationship_type"],
                "target_document_id": edge["target_document_id"],
                "target_filename": edge["target_document_filename"],
                "supporting_reference_count": edge["supporting_reference_count"],
                "supporting_pages": sorted(support["pages"]),
                "resolution_origin": _resolution_origin(support["auto_count"], support["human_count"]),
            }
        )

    reference_status_counts = audit["summary"]["references"]["status_counts"]

    return {
        "tender_id": tender_id,
        "baseline_version": RELATIONSHIP_BASELINE_VERSION,
        "source_audit_version": AUDIT_VERSION,
        "generated_at": generated_at,
        "counts": {
            "total_physical_documents": audit["summary"]["documents"]["total_documents"],
            "current_documents": audit["summary"]["documents"]["current_documents"],
            "documents_analyzed_for_references": audit["summary"]["references"]["documents_analyzed"],
            "total_reference_mentions": sum(reference_status_counts.values()),
            "relationship_edge_count": audit["summary"]["relationships"]["total_edges"],
            "unresolved_reference_groups_count": len(audit["unresolved_reference_groups"]),
            "ambiguous_reference_groups_count": len(audit["ambiguous_reference_groups"]),
            "duplicate_edge_count": audit["summary"]["relationships"]["duplicate_edge_count"],
            "self_edge_count": audit["summary"]["relationships"]["self_edge_count"],
        },
        "reference_status_counts": reference_status_counts,
        "relationship_type_counts": {
            RELATIONSHIP_REFERENCES: audit["summary"]["relationships"]["relationship_type_counts"].get(RELATIONSHIP_REFERENCES, 0),
            RELATIONSHIP_MODIFIES: audit["summary"]["relationships"]["relationship_type_counts"].get(RELATIONSHIP_MODIFIES, 0),
        },
        "unresolved_reference_groups": audit["unresolved_reference_groups"],
        "ambiguous_reference_groups": audit["ambiguous_reference_groups"],
        "relationship_edges": audit["relationship_summary"]["edges"],
        "document_map": document_map,
    }
