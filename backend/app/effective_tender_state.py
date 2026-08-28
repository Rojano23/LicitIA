from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Tender, TenderChange, TenderChangeEvidence, TenderDocument, TenderEvent, TenderEventEvidence

EFFECTIVE_STATE_VERSION = "mvp-03.4"

REVIEW_SUGGESTED = "SUGGESTED"
REVIEW_CONFIRMED = "CONFIRMED"
REVIEW_REJECTED = "REJECTED"

STATUS_DETERMINED = "DETERMINED"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_AMBIGUOUS_PRECEDENCE = "AMBIGUOUS_PRECEDENCE"
STATUS_UNRESOLVED_TARGET = "UNRESOLVED_TARGET"
STATUS_NO_CONFIRMED_CHANGE = "NO_CONFIRMED_CHANGE"

TEMPORAL_RESOLVED = "RESOLVED"
TEMPORAL_UNKNOWN = "UNKNOWN"
TEMPORAL_AMBIGUOUS_SOURCE_DATE = "AMBIGUOUS_SOURCE_DATE"

MUTATING_TYPES = {"MODIFIES", "REPLACES", "CORRECTS", "REMOVES"}
NON_REPLACING_TYPES = {"CLARIFIES", "ADDS", "CONFIRMS"}

ELIGIBLE_PRECEDENCE_EVENT_TYPES = {
    "CLARIFICATION_PUBLICATION",
    "ADDENDUM_PUBLICATION",
    "DOCUMENT_PUBLICATION",
    "CLARIFICATION_MEETING",
    "TENDER_PUBLICATION",
    "BIDDING_RULES_PUBLICATION",
}


@dataclass(frozen=True)
class _SourceTemporal:
    status: str
    event_date: date | None
    event_time: time | None
    date_precision: str | None
    event_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class _TemporalCandidate:
    event_date: date
    event_time: time | None


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_locator(value: str | None) -> str:
    if not value:
        return ""
    compact = value.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.lower().strip()
    compact = _strip_accents(compact)
    compact = re.sub(r"\s+", " ", compact)
    return compact.strip(" ")


def _effective_change_payload(change: TenderChange) -> dict[str, Any]:
    return {
        "change_type": change.human_change_type or change.change_type,
        "target_document_id": change.human_target_document_id or change.target_document_id,
        "target_locator_text": change.human_target_locator_text or change.target_locator_text,
        "before_text": change.human_before_text if change.human_before_text is not None else change.before_text,
        "after_text": change.human_after_text if change.human_after_text is not None else change.after_text,
    }


def _effective_event_payload(event: TenderEvent) -> dict[str, Any]:
    return {
        "event_type": event.human_event_type or event.event_type,
        "event_date": event.human_event_date or event.event_date,
        "event_time": event.human_event_time or event.event_time,
        "date_precision": event.human_date_precision or event.date_precision,
    }


def _build_source_temporal_index(events: list[TenderEvent]) -> dict[str, _SourceTemporal]:
    by_source: dict[str, list[tuple[TenderEvent, dict[str, Any]]]] = {}
    for row in events:
        if row.review_status != REVIEW_CONFIRMED:
            continue
        if not row.source_document_id:
            continue

        effective = _effective_event_payload(row)
        if effective["event_type"] not in ELIGIBLE_PRECEDENCE_EVENT_TYPES:
            continue
        if effective["event_date"] is None:
            continue

        by_source.setdefault(row.source_document_id, []).append((row, effective))

    temporal_index: dict[str, _SourceTemporal] = {}

    for source_document_id, source_events in by_source.items():
        signature_map: dict[tuple[date, time | None, str | None], list[str]] = {}
        for event_row, effective in source_events:
            signature = (
                effective["event_date"],
                effective["event_time"],
                effective["date_precision"],
            )
            signature_map.setdefault(signature, []).append(event_row.id)

        signatures = sorted(
            signature_map.items(),
            key=lambda item: (
                item[0][0],
                item[0][1] is None,
                item[0][1] or time.max,
                item[0][2] or "",
            ),
        )

        if len(signatures) > 1:
            all_event_ids = tuple(sorted(event_id for _, ids in signatures for event_id in ids))
            temporal_index[source_document_id] = _SourceTemporal(
                status=TEMPORAL_AMBIGUOUS_SOURCE_DATE,
                event_date=None,
                event_time=None,
                date_precision=None,
                event_ids=all_event_ids,
                reason="Multiple eligible confirmed publication events disagree for the same source document",
            )
            continue

        signature, ids = signatures[0]
        event_date, event_time, date_precision = signature
        if date_precision != "DAY":
            temporal_index[source_document_id] = _SourceTemporal(
                status=TEMPORAL_UNKNOWN,
                event_date=event_date,
                event_time=event_time,
                date_precision=date_precision,
                event_ids=tuple(sorted(ids)),
                reason="Eligible confirmed publication event exists but date precision is not DAY",
            )
            continue

        temporal_index[source_document_id] = _SourceTemporal(
            status=TEMPORAL_RESOLVED,
            event_date=event_date,
            event_time=event_time,
            date_precision=date_precision,
            event_ids=tuple(sorted(ids)),
            reason="Reliable confirmed publication event",
        )

    return temporal_index


def _source_temporal_for_change(change: TenderChange, temporal_index: dict[str, _SourceTemporal]) -> _SourceTemporal:
    source_id = change.source_document_id
    if source_id in temporal_index:
        return temporal_index[source_id]
    return _SourceTemporal(
        status=TEMPORAL_UNKNOWN,
        event_date=None,
        event_time=None,
        date_precision=None,
        event_ids=(),
        reason="No eligible confirmed publication event for source document",
    )


def _serialize_change(
    change: TenderChange,
    docs_by_id: dict[str, TenderDocument],
    temporal: _SourceTemporal,
) -> dict[str, Any]:
    effective = _effective_change_payload(change)
    target_doc = docs_by_id.get(effective["target_document_id"]) if effective["target_document_id"] else None
    source_doc = docs_by_id.get(change.source_document_id)

    return {
        "id": change.id,
        "semantic_key": change.semantic_key,
        "review_status": change.review_status,
        "change_type": effective["change_type"],
        "target_document_id": effective["target_document_id"],
        "target_filename": target_doc.original_filename if target_doc else None,
        "target_reference_key": change.target_reference_key,
        "target_locator_text": effective["target_locator_text"],
        "normalized_locator": _normalize_locator(effective["target_locator_text"]),
        "before_text": effective["before_text"],
        "after_text": effective["after_text"],
        "source_document_id": change.source_document_id,
        "source_filename": source_doc.original_filename if source_doc else None,
        "source_page": change.source_page,
        "source_excerpt": change.source_excerpt,
        "source_is_current": bool(source_doc.is_current) if source_doc else False,
        "temporal_status": temporal.status,
        "temporal_event_date": temporal.event_date,
        "temporal_event_time": temporal.event_time,
        "temporal_date_precision": temporal.date_precision,
        "temporal_event_ids": list(temporal.event_ids),
        "temporal_reason": temporal.reason,
        "human_change_type": change.human_change_type,
        "human_target_document_id": change.human_target_document_id,
        "human_target_locator_text": change.human_target_locator_text,
        "human_before_text": change.human_before_text,
        "human_after_text": change.human_after_text,
        "human_note": change.human_note,
    }


def _scope_key_for_change(change: dict[str, Any]) -> tuple[str, str, str]:
    target_document_id = change["target_document_id"]
    locator = change["normalized_locator"]

    if target_document_id:
        return ("RESOLVED", target_document_id, locator)

    unresolved_key = "|".join([
        change["target_reference_key"] or "NO_REFERENCE_KEY",
        locator or "NO_LOCATOR",
    ])
    unresolved_hash = hashlib.sha256(unresolved_key.encode("utf-8")).hexdigest()
    return ("UNRESOLVED", unresolved_hash, locator)


def _stable_change_sort_key(change: dict[str, Any]) -> tuple[str, int, str]:
    return (
        change["source_filename"] or "",
        change["source_page"] or 0,
        change["id"],
    )


def _is_change_authoritative_candidate(change: dict[str, Any]) -> bool:
    return bool(change["review_status"] == REVIEW_CONFIRMED and change["source_is_current"])


def _candidate_temporal(change: dict[str, Any]) -> _TemporalCandidate | None:
    if change["temporal_status"] != TEMPORAL_RESOLVED:
        return None
    event_date = change["temporal_event_date"]
    if event_date is None:
        return None
    return _TemporalCandidate(event_date=event_date, event_time=change["temporal_event_time"])


def _select_latest_defensible_mutation(mutations: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str, str, list[str]]:
    if not mutations:
        return None, STATUS_NO_CONFIRMED_CHANGE, "No confirmed mutating changes for this scope", []

    if len(mutations) == 1:
        only = mutations[0]
        if only["temporal_status"] == TEMPORAL_RESOLVED:
            reason = "Single confirmed mutating change with reliable publication chronology"
        else:
            reason = "Single confirmed mutating change; chronology not required because there is no competing confirmed mutation"
        return only, STATUS_DETERMINED, reason, []

    warnings: list[str] = []
    candidates: list[tuple[dict[str, Any], _TemporalCandidate]] = []

    for row in mutations:
        temporal = _candidate_temporal(row)
        if temporal is None:
            if row["temporal_status"] == TEMPORAL_AMBIGUOUS_SOURCE_DATE:
                warnings.append(f"Change {row['id']} has ambiguous confirmed source publication chronology")
            else:
                warnings.append(f"Change {row['id']} has no reliable confirmed publication chronology")
            return None, STATUS_AMBIGUOUS_PRECEDENCE, "Competing confirmed mutating changes cannot be ordered safely", warnings
        candidates.append((row, temporal))

    if not candidates:
        return None, STATUS_AMBIGUOUS_PRECEDENCE, "Competing confirmed mutating changes cannot be ordered safely", warnings

    date_groups: dict[date, list[tuple[dict[str, Any], _TemporalCandidate]]] = {}
    for row, temporal in candidates:
        date_groups.setdefault(temporal.event_date, []).append((row, temporal))

    latest_date = max(date_groups.keys())
    latest_day_rows = date_groups[latest_date]

    if len(latest_day_rows) == 1:
        winner, _ = latest_day_rows[0]
        return winner, STATUS_DETERMINED, "Latest confirmed mutating change selected by publication date", warnings

    # Same day competition requires explicit times for all competitors to avoid invented ordering.
    if any(item[1].event_time is None for item in latest_day_rows):
        warnings.append("At least one competing same-day change has no confirmed event time")
        return None, STATUS_AMBIGUOUS_PRECEDENCE, "Competing confirmed mutations share publication day without fully reliable time ordering", warnings

    max_time = max(item[1].event_time for item in latest_day_rows if item[1].event_time is not None)
    winners = [item[0] for item in latest_day_rows if item[1].event_time == max_time]

    if len(winners) != 1:
        warnings.append("Competing same-day changes have identical confirmed publication time")
        return None, STATUS_AMBIGUOUS_PRECEDENCE, "Competing confirmed mutations are tied in reliable chronology", warnings

    return winners[0], STATUS_DETERMINED, "Latest confirmed mutating change selected by publication date and time", warnings


def _serialize_scope(
    *,
    scope_key: tuple[str, str, str],
    scope_changes: list[dict[str, Any]],
    docs_by_id: dict[str, TenderDocument],
) -> dict[str, Any]:
    scope_kind, scope_target, locator = scope_key

    confirmed = [row for row in scope_changes if row["review_status"] == REVIEW_CONFIRMED]
    suggested = [row for row in scope_changes if row["review_status"] == REVIEW_SUGGESTED]
    rejected = [row for row in scope_changes if row["review_status"] == REVIEW_REJECTED]

    confirmed_current = [row for row in confirmed if row["source_is_current"]]
    non_current_confirmed = [row for row in confirmed if not row["source_is_current"]]

    confirmed_mutations = [
        row
        for row in confirmed_current
        if row["change_type"] in MUTATING_TYPES
    ]
    confirmed_non_replacing = [
        row
        for row in confirmed_current
        if row["change_type"] in NON_REPLACING_TYPES
    ]

    for bucket in (confirmed_mutations, confirmed_non_replacing, suggested, rejected, non_current_confirmed):
        bucket.sort(key=_stable_change_sort_key)

    warnings: list[str] = []
    if non_current_confirmed:
        warnings.append("Confirmed change(s) from non-current source document excluded from authoritative automatic precedence")

    if scope_kind == "UNRESOLVED":
        resolution_status = STATUS_UNRESOLVED_TARGET
        effective_mutation = None
        temporal_reason = "Physical target is unresolved; authoritative effective state cannot be computed"
        warnings.append("Target document unresolved; preserving reference key/locator without inventing target")
    else:
        effective_mutation, resolution_status, temporal_reason, precedence_warnings = _select_latest_defensible_mutation(confirmed_mutations)
        warnings.extend(precedence_warnings)

        if resolution_status == STATUS_DETERMINED and suggested:
            resolution_status = STATUS_PENDING_REVIEW
            temporal_reason = "A confirmed effective mutation exists, but suggested changes are pending human review"
        elif resolution_status == STATUS_NO_CONFIRMED_CHANGE and suggested:
            resolution_status = STATUS_PENDING_REVIEW
            temporal_reason = "No authoritative confirmed mutation; suggested changes require human review"

    target_doc = docs_by_id.get(scope_target) if scope_kind == "RESOLVED" else None

    scope_identifier = f"{scope_kind}|{scope_target}|{locator}"
    stable_scope_key = hashlib.sha256(scope_identifier.encode("utf-8")).hexdigest()

    return {
        "scope_key": stable_scope_key,
        "scope_kind": scope_kind,
        "target_document_id": target_doc.id if target_doc else None,
        "target_filename": target_doc.original_filename if target_doc else None,
        "target_reference_key": scope_changes[0]["target_reference_key"] if scope_changes else None,
        "target_locator_text": scope_changes[0]["target_locator_text"] if scope_changes else None,
        "normalized_locator": locator,
        "resolution_status": resolution_status,
        "effective_mutation": effective_mutation,
        "confirmed_mutations": confirmed_mutations,
        "confirmed_non_replacing_assertions": confirmed_non_replacing,
        "pending_changes": suggested,
        "rejected_changes": rejected,
        "non_current_confirmed_changes": non_current_confirmed,
        "temporal_reason": temporal_reason,
        "warnings": warnings,
    }


def get_tender_effective_state(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    documents = (
        db.execute(
            select(TenderDocument)
            .where(TenderDocument.tender_id == tender_id)
            .order_by(TenderDocument.original_filename.asc(), TenderDocument.id.asc())
        )
        .scalars()
        .all()
    )
    docs_by_id = {row.id: row for row in documents}

    changes = (
        db.execute(
            select(TenderChange)
            .where(TenderChange.tender_id == tender_id)
            .options(selectinload(TenderChange.evidence).selectinload(TenderChangeEvidence.source_document))
            .order_by(TenderChange.created_at.asc(), TenderChange.id.asc())
        )
        .scalars()
        .all()
    )

    events = (
        db.execute(
            select(TenderEvent)
            .where(TenderEvent.tender_id == tender_id)
            .options(selectinload(TenderEvent.evidence).selectinload(TenderEventEvidence.source_document))
            .order_by(TenderEvent.created_at.asc(), TenderEvent.id.asc())
        )
        .scalars()
        .all()
    )

    temporal_index = _build_source_temporal_index(events)

    serialized_changes: list[dict[str, Any]] = []
    for row in changes:
        temporal = _source_temporal_for_change(row, temporal_index)
        serialized_changes.append(_serialize_change(row, docs_by_id, temporal))

    grouped_scopes: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in serialized_changes:
        grouped_scopes.setdefault(_scope_key_for_change(row), []).append(row)

    scopes = [
        _serialize_scope(scope_key=scope_key, scope_changes=rows, docs_by_id=docs_by_id)
        for scope_key, rows in grouped_scopes.items()
    ]

    scopes.sort(
        key=lambda scope: (
            scope["target_filename"] or "~~~~",
            scope["normalized_locator"] or "~~~~",
            scope["scope_key"],
        )
    )

    summary = {
        "total_scopes": len(scopes),
        "determined": sum(1 for scope in scopes if scope["resolution_status"] == STATUS_DETERMINED),
        "pending_review": sum(1 for scope in scopes if scope["resolution_status"] == STATUS_PENDING_REVIEW),
        "ambiguous_precedence": sum(1 for scope in scopes if scope["resolution_status"] == STATUS_AMBIGUOUS_PRECEDENCE),
        "unresolved_target": sum(1 for scope in scopes if scope["resolution_status"] == STATUS_UNRESOLVED_TARGET),
        "no_confirmed_change": sum(1 for scope in scopes if scope["resolution_status"] == STATUS_NO_CONFIRMED_CHANGE),
    }

    return {
        "tender_id": tender_id,
        "state_version": EFFECTIVE_STATE_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "summary": summary,
        "scopes": scopes,
    }
