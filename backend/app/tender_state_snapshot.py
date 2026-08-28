from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.document_intelligence_audit import generate_document_intelligence_audit
from app.models import Tender, TenderChange, TenderChangeEvidence, TenderDocument
from app.relationship_baseline import generate_tender_relationship_baseline
from app.tender_changes import list_tender_changes
from app.tender_events import list_tender_events
from app.effective_tender_state import get_tender_effective_state

SNAPSHOT_VERSION = "mvp-03.5"

READINESS_UNDERSTOOD = "UNDERSTOOD"
READINESS_PARTIALLY_UNDERSTOOD = "PARTIALLY_UNDERSTOOD"
READINESS_NOT_READY = "NOT_READY"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_BLOCKING = "BLOCKING"

MUTATING_CHANGE_TYPES = {"MODIFIES", "REPLACES", "CORRECTS", "REMOVES"}
NON_REPLACING_CHANGE_TYPES = {"CLARIFIES", "ADDS", "CONFIRMS"}


def _effective_change_type(change: dict[str, Any]) -> str:
    return change.get("human_change_type") or change.get("change_type") or "UNKNOWN"


def _effective_target_document_id(change: dict[str, Any]) -> str | None:
    return change.get("human_target_document_id") or change.get("target_document_id")


def _effective_target_locator(change: dict[str, Any]) -> str | None:
    return change.get("human_target_locator_text") or change.get("target_locator_text")


def _severity_rank(value: str) -> int:
    if value == SEVERITY_BLOCKING:
        return 3
    if value == SEVERITY_WARNING:
        return 2
    return 1


def _add_pending_action(
    bucket: list[dict[str, Any]],
    dedup: set[tuple[str, str, str | None, int | None, str | None, str]],
    *,
    category: str,
    severity: str,
    title: str,
    description: str,
    document_id: str | None = None,
    source_page: int | None = None,
    related_entity_id: str | None = None,
) -> None:
    key = (category, severity, document_id, source_page, related_entity_id, title)
    if key in dedup:
        return
    dedup.add(key)
    bucket.append(
        {
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "document_id": document_id,
            "source_page": source_page,
            "related_entity_id": related_entity_id,
        }
    )


def _build_document_summary(audit: dict[str, Any]) -> dict[str, Any]:
    summary = audit["summary"]
    status_counts = summary["classification"]["status_counts"]
    return {
        "total_documents": summary["documents"]["total_documents"],
        "current_documents": summary["documents"]["current_documents"],
        "non_current_documents": summary["documents"]["non_current_documents"],
        "ready_for_analysis": summary["references"]["documents_analyzed"],
        "pending_processing": summary["acquisition"]["documents_pending_or_failed"],
        "with_normalized_content": summary["normalization"]["current_documents_with_normalized_content"],
        "without_normalized_content": summary["normalization"]["current_documents_without_normalized_content"],
        "classified": summary["classification"]["classified_documents"],
        "unclassified": summary["classification"]["unclassified_documents"],
        "confirmed_classifications": status_counts.get("CONFIRMED", 0),
        "suggested_classifications": status_counts.get("SUGGESTED", 0),
    }


def _build_relationship_summary(baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_reference_mentions": baseline["counts"]["total_reference_mentions"],
        "reference_status_counts": baseline["reference_status_counts"],
        "relationship_edge_count": baseline["counts"]["relationship_edge_count"],
        "relationship_type_counts": baseline["relationship_type_counts"],
        "duplicate_edge_count": baseline["counts"]["duplicate_edge_count"],
        "self_edge_count": baseline["counts"]["self_edge_count"],
        "unresolved_reference_groups_count": baseline["counts"]["unresolved_reference_groups_count"],
        "ambiguous_reference_groups_count": baseline["counts"]["ambiguous_reference_groups_count"],
    }


def _build_timeline_summary(timeline: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_events": timeline["counts"]["total_events"],
        "suggested_events": timeline["counts"]["suggested_events"],
        "confirmed_events": timeline["counts"]["confirmed_events"],
        "rejected_events": timeline["counts"]["rejected_events"],
        "duplicate_semantic_count": timeline["counts"]["duplicate_semantic_count"],
    }


def _build_change_summary(changes_payload: dict[str, Any]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    unresolved_target = 0
    ambiguous_target = 0
    confirmed_mutating = 0
    confirmed_non_replacing = 0

    for row in changes_payload["changes"]:
        effective_type = _effective_change_type(row)
        by_type[effective_type] = by_type.get(effective_type, 0) + 1

        target_document_id = _effective_target_document_id(row)
        if not target_document_id and row.get("target_reference_key"):
            unresolved_target += 1
        if len(row.get("target_candidate_documents") or []) > 1:
            ambiguous_target += 1

        if row["review_status"] == "CONFIRMED":
            if effective_type in MUTATING_CHANGE_TYPES:
                confirmed_mutating += 1
            if effective_type in NON_REPLACING_CHANGE_TYPES:
                confirmed_non_replacing += 1

    return {
        "total_changes": changes_payload["counts"]["total_changes"],
        "suggested_changes": changes_payload["counts"]["suggested_changes"],
        "confirmed_changes": changes_payload["counts"]["confirmed_changes"],
        "rejected_changes": changes_payload["counts"]["rejected_changes"],
        "duplicate_semantic_count": changes_payload["counts"]["duplicate_semantic_count"],
        "counts_by_change_type": dict(sorted(by_type.items())),
        "unresolved_target_count": unresolved_target,
        "ambiguous_target_count": ambiguous_target,
        "confirmed_mutating_count": confirmed_mutating,
        "confirmed_non_replacing_count": confirmed_non_replacing,
    }


def _build_effective_summary(effective_state: dict[str, Any]) -> dict[str, Any]:
    summary = effective_state["summary"]
    return {
        "total_scopes": summary["total_scopes"],
        "determined": summary["determined"],
        "pending_review": summary["pending_review"],
        "ambiguous_precedence": summary["ambiguous_precedence"],
        "unresolved_target": summary["unresolved_target"],
        "no_confirmed_change": summary.get("no_confirmed_change", 0),
    }


def _build_document_matrix(
    *,
    audit: dict[str, Any],
    timeline: dict[str, Any],
    changes_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    event_count_by_doc: dict[str, int] = {}
    change_count_by_doc: dict[str, int] = {}

    for row in timeline["events"]:
        source_document_id = row.get("source_document_id")
        if not source_document_id:
            continue
        event_count_by_doc[source_document_id] = event_count_by_doc.get(source_document_id, 0) + 1

    for row in changes_payload["changes"]:
        source_document_id = row.get("source_document_id")
        if not source_document_id:
            continue
        change_count_by_doc[source_document_id] = change_count_by_doc.get(source_document_id, 0) + 1

    matrix: list[dict[str, Any]] = []
    for row in audit["document_rows"]:
        if not row["is_current"]:
            continue
        matrix.append(
            {
                "document_id": row["document_id"],
                "filename": row["filename"],
                "processing_status": row["processing_status"],
                "normalized": row["normalized"],
                "classification_status": row["classification_status"],
                "reference_analysis_status": row["reference_analysis_status"],
                "event_count": event_count_by_doc.get(row["document_id"], 0),
                "change_count": change_count_by_doc.get(row["document_id"], 0),
                "findings_count": len(row["integrity_findings"]),
            }
        )

    matrix.sort(key=lambda item: item["filename"].lower())
    return matrix


def _build_document_map_with_change_support(
    baseline: dict[str, Any],
    changes_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    confirmed_change_ids: dict[tuple[str, str], list[str]] = {}
    for row in changes_payload["changes"]:
        if row["review_status"] != "CONFIRMED":
            continue
        effective_type = _effective_change_type(row)
        if effective_type not in MUTATING_CHANGE_TYPES:
            continue
        source_document_id = row["source_document_id"]
        target_document_id = _effective_target_document_id(row)
        if not target_document_id:
            continue
        confirmed_change_ids.setdefault((source_document_id, target_document_id), []).append(row["id"])

    mapped: list[dict[str, Any]] = []
    for row in baseline["document_map"]:
        item = dict(row)
        if item["relationship_type"] == "MODIFIES":
            item["supporting_change_ids"] = sorted(confirmed_change_ids.get((item["source_document_id"], item["target_document_id"]), []))
        else:
            item["supporting_change_ids"] = []
        mapped.append(item)
    return mapped


def _build_cross_layer_checks(
    *,
    baseline: dict[str, Any],
    timeline: dict[str, Any],
    changes_payload: dict[str, Any],
    effective_state: dict[str, Any],
    documents: list[TenderDocument],
    tender_changes: list[TenderChange],
) -> list[dict[str, Any]]:
    docs_by_id = {item.id: item for item in documents}
    issues: list[dict[str, Any]] = []

    def add_issue(code: str, severity: str, message: str, related_entity_id: str | None = None, document_id: str | None = None) -> None:
        issues.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "related_entity_id": related_entity_id,
                "document_id": document_id,
            }
        )

    confirmed_mutating_pairs: set[tuple[str, str]] = set()
    for row in changes_payload["changes"]:
        if row["review_status"] != "CONFIRMED":
            continue
        effective_type = _effective_change_type(row)
        if effective_type not in MUTATING_CHANGE_TYPES:
            continue
        target_document_id = _effective_target_document_id(row)
        if not target_document_id:
            continue
        confirmed_mutating_pairs.add((row["source_document_id"], target_document_id))

    modifies_edge_pairs: set[tuple[str, str]] = set()
    for edge in baseline["document_map"]:
        source_id = edge["source_document_id"]
        target_id = edge["target_document_id"]

        if edge["source_filename"] is None or edge["target_filename"] is None:
            add_issue(
                "RELATIONSHIP_EDGE_MISSING_DOCUMENT",
                SEVERITY_BLOCKING,
                "Existe una relacion que apunta a documento inexistente en el inventario del expediente.",
                related_entity_id=f"{source_id}|{edge['relationship_type']}|{target_id}",
            )

        if edge["relationship_type"] != "MODIFIES":
            continue

        modifies_edge_pairs.add((source_id, target_id))
        if (source_id, target_id) not in confirmed_mutating_pairs:
            add_issue(
                "MODIFIES_WITHOUT_CONFIRMED_CHANGE",
                SEVERITY_WARNING,
                "Existe arista MODIFIES sin soporte de cambio confirmado vigente.",
                related_entity_id=f"{source_id}|{target_id}",
            )

    for source_id, target_id in sorted(confirmed_mutating_pairs):
        if (source_id, target_id) not in modifies_edge_pairs:
            add_issue(
                "CONFIRMED_MUTATION_MISSING_MODIFIES_EDGE",
                SEVERITY_WARNING,
                "Existe cambio mutante confirmado con destino resuelto, pero no aparece arista MODIFIES en el mapa documental.",
                related_entity_id=f"{source_id}|{target_id}",
                document_id=source_id,
            )

    for event in timeline["events"]:
        source_document_id = event.get("source_document_id")
        if source_document_id and source_document_id not in docs_by_id:
            add_issue(
                "EVENT_SOURCE_DOCUMENT_MISSING",
                SEVERITY_BLOCKING,
                "Existe evento con documento fuente inexistente.",
                related_entity_id=event["id"],
                document_id=source_document_id,
            )

    for change in tender_changes:
        for evidence in change.evidence:
            if evidence.source_document_id not in docs_by_id:
                add_issue(
                    "CHANGE_EVIDENCE_SOURCE_MISSING",
                    SEVERITY_BLOCKING,
                    "Existe evidencia de cambio con documento fuente inexistente.",
                    related_entity_id=evidence.id,
                    document_id=evidence.source_document_id,
                )

    for scope in effective_state["scopes"]:
        target_document_id = scope.get("target_document_id")
        if not target_document_id:
            continue
        target = docs_by_id.get(target_document_id)
        if target is None:
            add_issue(
                "EFFECTIVE_SCOPE_TARGET_MISSING",
                SEVERITY_WARNING,
                "El estado efectivo referencia un documento destino inexistente en inventario.",
                related_entity_id=scope["scope_key"],
                document_id=target_document_id,
            )
            continue
        if not target.is_current:
            add_issue(
                "EFFECTIVE_SCOPE_TARGET_NON_CURRENT",
                SEVERITY_WARNING,
                "El estado efectivo referencia un destino no vigente; revisar consistencia del alcance vigente.",
                related_entity_id=scope["scope_key"],
                document_id=target_document_id,
            )

    issues.sort(key=lambda item: (-_severity_rank(item["severity"]), item["code"], item.get("related_entity_id") or ""))
    return issues


def _build_pending_actions(
    *,
    audit: dict[str, Any],
    baseline: dict[str, Any],
    timeline: dict[str, Any],
    changes_payload: dict[str, Any],
    effective_state: dict[str, Any],
    cross_layer_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    dedup: set[tuple[str, str, str | None, int | None, str | None, str]] = set()

    for row in audit["document_rows"]:
        if not row["is_current"]:
            continue
        if row["processing_status"] not in {
            "TEXT_EXTRACTION_COMPLETE",
            "OCR_COMPLETE",
            "OCR_COMPLETE_WITH_WARNINGS",
        }:
            _add_pending_action(
                actions,
                dedup,
                category="PROCESS_DOCUMENT",
                severity=SEVERITY_WARNING,
                title="Documento vigente pendiente de procesamiento",
                description=f"El documento {row['filename']} requiere procesamiento para completar comprension del expediente.",
                document_id=row["document_id"],
            )
        if row["classification_status"] in {"UNCLASSIFIED", "NEEDS_REVIEW", "SUGGESTED"}:
            _add_pending_action(
                actions,
                dedup,
                category="REVIEW_CLASSIFICATION",
                severity=SEVERITY_WARNING,
                title="Clasificacion documental por revisar",
                description=f"El documento {row['filename']} tiene clasificacion {row['classification_status']}.",
                document_id=row["document_id"],
            )

    for finding in audit["findings"]:
        code = finding["code"]
        severity = finding["severity"]
        category = "PROCESS_DOCUMENT"
        title = "Hallazgo de integridad"

        if code in {"CURRENT_FILENAME_COLLISION", "DUPLICATE_CURRENT_SHA256"}:
            category = "REVIEW_DOCUMENT_COLLISION"
            title = "Colision de documentos vigentes"
        elif code == "STALE_ANALYSIS_VERSION":
            category = "REPROCESS_STALE_ANALYSIS"
            title = "Analisis desactualizado"
        elif code == "MISSING_CLASSIFICATION":
            category = "REVIEW_CLASSIFICATION"
            title = "Clasificacion faltante"
        elif code == "MISSING_REFERENCE_ANALYSIS":
            category = "RESOLVE_REFERENCE"
            title = "Analisis de referencias faltante"

        _add_pending_action(
            actions,
            dedup,
            category=category,
            severity=severity,
            title=title,
            description=finding["message"],
            document_id=finding.get("document_id"),
            related_entity_id=code,
        )

    for group in baseline["ambiguous_reference_groups"]:
        _add_pending_action(
            actions,
            dedup,
            category="RESOLVE_REFERENCE",
            severity=SEVERITY_WARNING,
            title="Referencia ambigua",
            description=f"Resolver referencia ambigua {group['normalized_reference_key']}.",
            related_entity_id=group["normalized_reference_key"],
        )

    for group in baseline["unresolved_reference_groups"]:
        _add_pending_action(
            actions,
            dedup,
            category="RESOLVE_REFERENCE",
            severity=SEVERITY_WARNING,
            title="Referencia sin documento objetivo",
            description=f"Resolver referencia no localizada {group['normalized_reference_key']}.",
            related_entity_id=group["normalized_reference_key"],
        )

    for event in timeline["events"]:
        if event["review_status"] != "SUGGESTED":
            continue
        _add_pending_action(
            actions,
            dedup,
            category="REVIEW_EVENT",
            severity=SEVERITY_WARNING,
            title="Evento sugerido pendiente de decision",
            description=f"Revisar evento {event['title']} ({event['event_type']}).",
            document_id=event.get("source_document_id"),
            source_page=event.get("source_page"),
            related_entity_id=event["id"],
        )

    for change in changes_payload["changes"]:
        effective_type = _effective_change_type(change)
        if change["review_status"] == "SUGGESTED":
            _add_pending_action(
                actions,
                dedup,
                category="REVIEW_CHANGE",
                severity=SEVERITY_WARNING,
                title="Cambio sugerido pendiente de decision",
                description=f"Revisar cambio sugerido de tipo {effective_type}.",
                document_id=change.get("source_document_id"),
                source_page=change.get("source_page"),
                related_entity_id=change["id"],
            )
        if not _effective_target_document_id(change) and change.get("target_reference_key"):
            _add_pending_action(
                actions,
                dedup,
                category="RESOLVE_CHANGE_TARGET",
                severity=SEVERITY_WARNING,
                title="Cambio con destino no resuelto",
                description=f"Resolver documento destino para cambio {change['id']} ({change.get('target_reference_key')}).",
                document_id=change.get("source_document_id"),
                source_page=change.get("source_page"),
                related_entity_id=change["id"],
            )

    for scope in effective_state["scopes"]:
        status = scope["resolution_status"]
        if status == "AMBIGUOUS_PRECEDENCE":
            _add_pending_action(
                actions,
                dedup,
                category="RESOLVE_PRECEDENCE",
                severity=SEVERITY_WARNING,
                title="Orden de cambios por revisar",
                description="Existen mutaciones confirmadas que no pueden ordenarse de forma defendible.",
                related_entity_id=scope["scope_key"],
                document_id=scope.get("target_document_id"),
            )
        elif status == "UNRESOLVED_TARGET":
            _add_pending_action(
                actions,
                dedup,
                category="RESOLVE_CHANGE_TARGET",
                severity=SEVERITY_WARNING,
                title="Documento afectado no resuelto",
                description="El estado efectivo incluye un alcance con destino no resuelto.",
                related_entity_id=scope["scope_key"],
            )
        elif status == "PENDING_REVIEW":
            _add_pending_action(
                actions,
                dedup,
                category="REVIEW_CHANGE",
                severity=SEVERITY_WARNING,
                title="Estado efectivo pendiente de revision",
                description="Existe mutacion efectiva pero con cambios sugeridos pendientes.",
                related_entity_id=scope["scope_key"],
                document_id=scope.get("target_document_id"),
            )

    for issue in cross_layer_issues:
        category = "PROCESS_DOCUMENT"
        if issue["code"] in {
            "MODIFIES_WITHOUT_CONFIRMED_CHANGE",
            "CONFIRMED_MUTATION_MISSING_MODIFIES_EDGE",
        }:
            category = "REVIEW_CHANGE"
        elif issue["code"] == "CHANGE_EVIDENCE_SOURCE_MISSING":
            category = "PROCESS_DOCUMENT"

        _add_pending_action(
            actions,
            dedup,
            category=category,
            severity=issue["severity"],
            title="Consistencia estructural por revisar",
            description=issue["message"],
            document_id=issue.get("document_id"),
            related_entity_id=issue.get("related_entity_id") or issue["code"],
        )

    actions.sort(
        key=lambda item: (
            -_severity_rank(item["severity"]),
            item["category"],
            item["title"],
            item.get("document_id") or "",
            item.get("related_entity_id") or "",
        )
    )
    return actions


def _derive_readiness(
    *,
    audit: dict[str, Any],
    baseline: dict[str, Any],
    timeline: dict[str, Any],
    changes_payload: dict[str, Any],
    effective_state: dict[str, Any],
    pending_actions: list[dict[str, Any]],
    cross_layer_issues: list[dict[str, Any]],
) -> tuple[str, str]:
    has_blocking = any(item["severity"] == SEVERITY_BLOCKING for item in pending_actions) or any(
        item["severity"] == SEVERITY_BLOCKING for item in cross_layer_issues
    )
    if has_blocking:
        return READINESS_NOT_READY, "Se detectaron bloqueos estructurales de integridad o trazabilidad."

    has_partial_signals = any(
        [
            audit["summary"]["acquisition"]["documents_pending_or_failed"] > 0,
            audit["summary"]["normalization"]["current_documents_without_normalized_content"] > 0,
            baseline["counts"]["unresolved_reference_groups_count"] > 0,
            baseline["counts"]["ambiguous_reference_groups_count"] > 0,
            timeline["counts"]["suggested_events"] > 0,
            changes_payload["counts"]["suggested_changes"] > 0,
            effective_state["summary"]["ambiguous_precedence"] > 0,
            effective_state["summary"]["pending_review"] > 0,
            effective_state["summary"]["unresolved_target"] > 0,
            audit["summary"]["references"]["documents_ready_not_analyzed"] > 0,
            audit["summary"]["integrity"]["stale_analysis_count"] > 0,
            audit["summary"]["integrity"]["filename_collision_count"] > 0,
            any(item["severity"] == SEVERITY_WARNING for item in pending_actions),
        ]
    )
    if has_partial_signals:
        return READINESS_PARTIALLY_UNDERSTOOD, "Existe comprension util, pero quedan pendientes o ambiguedades estructurales."

    # UNDERSTOOD here means structural coherence of Tender Understanding only.
    # It does not mean bid/compliance/commercial readiness.
    return READINESS_UNDERSTOOD, "Las capas de Tender Understanding estan estructuralmente coherentes para el corpus vigente."


def generate_tender_state_snapshot(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    audit = generate_document_intelligence_audit(db, tender_id)
    baseline = generate_tender_relationship_baseline(db, tender_id)
    timeline = list_tender_events(db, tender_id)
    changes_payload = list_tender_changes(db, tender_id)
    effective_state = get_tender_effective_state(db, tender_id)

    documents = (
        db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.imported_at.asc()))
        .scalars()
        .all()
    )

    tender_changes = (
        db.execute(
            select(TenderChange)
            .where(TenderChange.tender_id == tender_id)
            .options(selectinload(TenderChange.evidence).selectinload(TenderChangeEvidence.source_document))
        )
        .scalars()
        .all()
    )

    document_summary = _build_document_summary(audit)
    relationship_summary = _build_relationship_summary(baseline)
    timeline_summary = _build_timeline_summary(timeline)
    change_summary = _build_change_summary(changes_payload)
    effective_summary = _build_effective_summary(effective_state)

    cross_layer_issues = _build_cross_layer_checks(
        baseline=baseline,
        timeline=timeline,
        changes_payload=changes_payload,
        effective_state=effective_state,
        documents=documents,
        tender_changes=tender_changes,
    )

    pending_actions = _build_pending_actions(
        audit=audit,
        baseline=baseline,
        timeline=timeline,
        changes_payload=changes_payload,
        effective_state=effective_state,
        cross_layer_issues=cross_layer_issues,
    )

    readiness_code, readiness_reason = _derive_readiness(
        audit=audit,
        baseline=baseline,
        timeline=timeline,
        changes_payload=changes_payload,
        effective_state=effective_state,
        pending_actions=pending_actions,
        cross_layer_issues=cross_layer_issues,
    )

    severity_counts = {
        SEVERITY_BLOCKING: sum(1 for item in pending_actions if item["severity"] == SEVERITY_BLOCKING),
        SEVERITY_WARNING: sum(1 for item in pending_actions if item["severity"] == SEVERITY_WARNING),
        SEVERITY_INFO: sum(1 for item in pending_actions if item["severity"] == SEVERITY_INFO),
    }

    return {
        "tender_id": tender_id,
        "snapshot_version": SNAPSHOT_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "readiness": {
            "code": readiness_code,
            "label": {
                READINESS_UNDERSTOOD: "Comprension estructural consolidada",
                READINESS_PARTIALLY_UNDERSTOOD: "Comprension parcial",
                READINESS_NOT_READY: "No listo estructuralmente",
            }[readiness_code],
            "reason": readiness_reason,
            "understanding_scope_note": "No implica cumplimiento, decision de oferta ni completitud comercial.",
        },
        "versions": {
            "document_intelligence_audit_version": audit.get("audit_version"),
            "relationship_baseline_version": baseline.get("baseline_version"),
            "timeline_version": timeline.get("timeline_version"),
            "changes_version": changes_payload.get("changes_version"),
            "effective_state_version": effective_state.get("state_version"),
        },
        "summary": {
            "documents": document_summary,
            "relationships": relationship_summary,
            "timeline": timeline_summary,
            "changes": change_summary,
            "effective_state": effective_summary,
            "pending_actions": {
                "total": len(pending_actions),
                "blocking": severity_counts[SEVERITY_BLOCKING],
                "warning": severity_counts[SEVERITY_WARNING],
                "info": severity_counts[SEVERITY_INFO],
            },
            "integrity": {
                "audit_overall_readiness": audit["overall_readiness"],
                "total_findings": len(audit["findings"]),
                "cross_layer_issue_count": len(cross_layer_issues),
            },
        },
        "documents": {
            "summary": document_summary,
            "matrix": _build_document_matrix(audit=audit, timeline=timeline, changes_payload=changes_payload),
        },
        "relationships": {
            "summary": relationship_summary,
            "unresolved_reference_groups": baseline["unresolved_reference_groups"],
            "ambiguous_reference_groups": baseline["ambiguous_reference_groups"],
            "document_map": _build_document_map_with_change_support(baseline, changes_payload),
        },
        "timeline": {
            "summary": timeline_summary,
            "events": timeline["events"],
        },
        "changes": {
            "summary": change_summary,
            "items": changes_payload["changes"],
        },
        "effective_state": {
            "summary": effective_summary,
            "scopes": [
                {
                    "scope_key": scope["scope_key"],
                    "target_document_id": scope.get("target_document_id"),
                    "target_filename": scope.get("target_filename"),
                    "target_reference_key": scope.get("target_reference_key"),
                    "target_locator_text": scope.get("target_locator_text"),
                    "resolution_status": scope["resolution_status"],
                    "effective_change_id": scope["effective_mutation"]["id"] if scope.get("effective_mutation") else None,
                    "pending_change_count": len(scope.get("pending_changes") or []),
                }
                for scope in effective_state["scopes"]
            ],
        },
        "integrity": {
            "document_intelligence_audit": {
                "overall_readiness": audit["overall_readiness"],
                "findings": audit["findings"],
            },
            "cross_layer_issues": cross_layer_issues,
        },
        "pending_actions": pending_actions,
        "top_pending_actions": pending_actions[:10],
    }
