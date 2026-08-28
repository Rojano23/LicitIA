from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DocumentPage, NormalizedContent, Tender, TenderDocument, TenderEvent, TenderEventEvidence

EVENT_DETECTOR_VERSION = "mvp-03.2"

DATE_PRECISION_DAY = "DAY"
DATE_PRECISION_MONTH = "MONTH"
DATE_PRECISION_YEAR = "YEAR"
DATE_PRECISION_UNKNOWN = "UNKNOWN"

REVIEW_SUGGESTED = "SUGGESTED"
REVIEW_CONFIRMED = "CONFIRMED"
REVIEW_REJECTED = "REJECTED"

ORIGIN_DETERMINISTIC = "DETERMINISTIC"

EVENT_ACTION_CONFIRM = "CONFIRM"
EVENT_ACTION_REJECT = "REJECT"
EVENT_ACTION_RESET = "RESET_TO_SUGGESTED"
EVENT_ACTION_OVERRIDE = "OVERRIDE"

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


@dataclass(frozen=True)
class EventPattern:
    event_type: str
    title: str
    anchors: tuple[str, ...]


EVENT_PATTERNS: tuple[EventPattern, ...] = (
    EventPattern(
        event_type="TENDER_PUBLICATION",
        title="Publicacion de convocatoria",
        anchors=("publicacion de la convocatoria", "publicacion convocatoria", "convocatoria publicada"),
    ),
    EventPattern(
        event_type="BIDDING_RULES_PUBLICATION",
        title="Publicacion de bases",
        anchors=("publicacion de bases", "bases publicadas"),
    ),
    EventPattern(
        event_type="SITE_VISIT",
        title="Visita al sitio",
        anchors=("visita al sitio",),
    ),
    EventPattern(
        event_type="CLARIFICATION_MEETING",
        title="Junta de aclaraciones",
        anchors=(
            "junta de aclaraciones",
            "acto de aclaraciones",
            "aclaraciones de dudas",
            "aclaraciones de dudas a las bases de contratacion",
            "recepcion de preguntas",
            "entrega de respuestas",
        ),
    ),
    EventPattern(
        event_type="PROPOSAL_SUBMISSION_DEADLINE",
        title="Presentacion de proposiciones",
        anchors=(
            "presentacion de proposiciones",
            "acto de presentacion",
            "recepcion de proposiciones",
            "fecha limite de proposiciones",
            "fecha limite para presentar proposiciones",
            "presentacion y apertura de propuestas",
            "presentacion y apertura de proposiciones",
            "apertura de propuestas comercial, tecnica y economica",
            "propuestas comercial, tecnica y economica",
        ),
    ),
    EventPattern(
        event_type="TECHNICAL_OPENING",
        title="Apertura tecnica",
        anchors=("apertura tecnica", "evaluacion tecnica"),
    ),
    EventPattern(
        event_type="ECONOMIC_OPENING",
        title="Apertura economica",
        anchors=("apertura economica", "evaluacion economica"),
    ),
    EventPattern(
        event_type="AWARD_ANNOUNCEMENT",
        title="Fallo o adjudicacion",
        anchors=("fallo", "adjudicacion"),
    ),
    EventPattern(
        event_type="CONTRACT_SIGNATURE_DEADLINE",
        title="Firma de contrato",
        anchors=("firma del contrato", "formalizacion del contrato"),
    ),
    EventPattern(
        event_type="ADDENDUM_PUBLICATION",
        title="Publicacion de adenda",
        anchors=("adenda", "addendum", "anexo modificatorio"),
    ),
    EventPattern(
        event_type="CANCELLATION",
        title="Cancelacion",
        anchors=("cancelacion", "cancelada"),
    ),
)


@dataclass
class DetectedEvent:
    semantic_key: str
    event_type: str
    title: str
    event_date: date | None
    event_time: time | None
    date_precision: str
    raw_date_text: str | None
    source_document_id: str
    source_page: int | None
    source_excerpt: str
    evidence_fragments: list[str]


@dataclass(frozen=True)
class TextFragment:
    text: str
    index: int


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_text(value: str) -> str:
    return _strip_accents(value).lower().strip()


def _excerpt(value: str, max_len: int = 500) -> str:
    compact = " ".join(value.split())
    return compact[:max_len]


def _is_structural_label_context(context: str) -> bool:
    normalized = _normalize_text(context)
    compact = " ".join(normalized.split())
    if re.fullmatch(r"apartado\s+[a-z]-\d+", compact):
        return True
    if re.fullmatch(r"anexo\s+[a-z0-9\-]+", compact):
        return True
    return False


def _context_segments(text: str) -> list[str]:
    segments: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for fragment in re.split(r"(?<=[\.;:!?])\s+", line):
            candidate = fragment.strip()
            if candidate:
                segments.append(candidate)
    if not segments:
        compact = text.strip()
        if compact:
            segments.append(compact)
    return segments


def _ordered_fragments(text: str) -> list[TextFragment]:
    fragments = _context_segments(text)
    return [TextFragment(text=fragment, index=index) for index, fragment in enumerate(fragments)]


def _parse_date(context: str) -> tuple[date | None, str, str | None]:
    normalized = _normalize_text(context)

    full_match = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", normalized)
    if full_match:
        day = int(full_match.group(1))
        month = SPANISH_MONTHS.get(full_match.group(2))
        year = int(full_match.group(3))
        if month:
            try:
                return date(year, month, day), DATE_PRECISION_DAY, full_match.group(0)
            except ValueError:
                return None, DATE_PRECISION_UNKNOWN, full_match.group(0)

    month_name_match = re.search(r"\b(\d{1,2})\s*(?:-|/)?\s*([a-z]+)\s*(?:-|/|\s+de\s+|\s+)\s*(\d{4})\b", normalized)
    if month_name_match:
        day = int(month_name_match.group(1))
        month = SPANISH_MONTHS.get(month_name_match.group(2))
        year = int(month_name_match.group(3))
        if month:
            try:
                return date(year, month, day), DATE_PRECISION_DAY, month_name_match.group(0)
            except ValueError:
                return None, DATE_PRECISION_UNKNOWN, month_name_match.group(0)

    slash_match = re.search(r"\b(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})\b", normalized)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = int(slash_match.group(3))
        try:
            return date(year, month, day), DATE_PRECISION_DAY, slash_match.group(0)
        except ValueError:
            return None, DATE_PRECISION_UNKNOWN, slash_match.group(0)

    month_match = re.search(r"\b([a-z]+)(?:\s+de)?\s+(\d{4})\b", normalized)
    if month_match:
        month = SPANISH_MONTHS.get(month_match.group(1))
        year = int(month_match.group(2))
        if month:
            return date(year, month, 1), DATE_PRECISION_MONTH, month_match.group(0)

    year_match = re.search(r"\b(20\d{2})\b", normalized)
    if year_match:
        return date(int(year_match.group(1)), 1, 1), DATE_PRECISION_YEAR, year_match.group(1)

    return None, DATE_PRECISION_UNKNOWN, None


def _parse_time(context: str) -> time | None:
    normalized = _normalize_text(context)
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?:\s*(?:h|hrs|horas))?\b", normalized)
    if not match:
        return None
    return time(hour=int(match.group(1)), minute=int(match.group(2)))


def _anchor_matches(pattern: EventPattern, context: str) -> bool:
    normalized = _normalize_text(context)
    return any(re.search(rf"\b{re.escape(anchor)}\b", normalized) for anchor in pattern.anchors)


def _is_procedural_event_context(pattern: EventPattern, context: str) -> bool:
    normalized = _normalize_text(context)

    # Weak single-token anchors require procedural phrasing nearby.
    if pattern.event_type == "AWARD_ANNOUNCEMENT":
        return bool(
            re.search(r"\b(fallo|adjudicacion)\b", normalized)
            and re.search(r"\b(acto|fecha|hora|horas|celebrara|realizara|emitira|publicara|notificacion)\b", normalized)
        )

    if pattern.event_type in {"TECHNICAL_OPENING", "ECONOMIC_OPENING"}:
        return bool(
            re.search(r"\b(apertura|evaluacion)\b", normalized)
            and re.search(r"\b(tecnica|economica)\b", normalized)
        )

    if pattern.event_type == "CONTRACT_SIGNATURE_DEADLINE":
        # Avoid classifying execution-duration text as signature events.
        if re.search(r"\bplazo de ejecucion\b", normalized):
            return False
        return bool(re.search(r"\b(firma del contrato|formalizacion del contrato)\b", normalized))

    return True


def _semantic_key(event_type: str, event_date: date | None, event_time: time | None, date_precision: str, title: str) -> str:
    date_token = event_date.isoformat() if event_date else "none"
    time_token = event_time.isoformat() if event_time else "none"
    raw = f"{event_type}|{date_token}|{time_token}|{date_precision}|{_normalize_text(title)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date_without_year_fallback(context: str) -> tuple[date | None, str, str | None]:
    parsed_date, precision, raw_text = _parse_date(context)
    if precision == DATE_PRECISION_YEAR:
        return None, DATE_PRECISION_UNKNOWN, None
    return parsed_date, precision, raw_text


def _parse_day_month_without_year(context: str) -> tuple[int, int, str] | None:
    normalized = _normalize_text(context)
    match = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\b", normalized)
    if not match:
        return None
    day = int(match.group(1))
    month = SPANISH_MONTHS.get(match.group(2))
    if not month:
        return None
    return day, month, match.group(0)


def _explicit_year_in_fragment(context: str) -> int | None:
    normalized = _normalize_text(context)

    full_match = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", normalized)
    if full_match and SPANISH_MONTHS.get(full_match.group(2)):
        return int(full_match.group(3))

    month_name_match = re.search(r"\b(\d{1,2})\s*(?:-|/)?\s*([a-z]+)\s*(?:-|/|\s+de\s+|\s+)\s*(\d{4})\b", normalized)
    if month_name_match and SPANISH_MONTHS.get(month_name_match.group(2)):
        return int(month_name_match.group(3))

    slash_match = re.search(r"\b(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})\b", normalized)
    if slash_match:
        return int(slash_match.group(3))

    return None


def _infer_year_from_neighbor_fragments(fragments: list[TextFragment], index: int) -> int | None:
    best_year: int | None = None
    best_distance = 10**9
    for probe_index, probe in enumerate(fragments):
        year = _explicit_year_in_fragment(probe.text)
        if year is None:
            continue
        distance = abs(probe_index - index)
        if distance > 30:
            continue
        if distance < best_distance:
            best_distance = distance
            best_year = year
    return best_year


def _time_only_fragment(context: str) -> bool:
    normalized = _normalize_text(context)
    return bool(_parse_time(normalized) and not _parse_date_without_year_fallback(normalized)[0])


def _build_detected_event(
    *,
    pattern: EventPattern,
    source_document_id: str,
    source_page: int | None,
    event_date: date,
    date_precision: str,
    raw_date_text: str | None,
    event_time: time | None,
    fragments: list[str],
) -> DetectedEvent:
    merged_excerpt = _excerpt(" | ".join(fragment.strip() for fragment in fragments if fragment.strip()))
    semantic_key = _semantic_key(pattern.event_type, event_date, event_time, date_precision, pattern.title)
    return DetectedEvent(
        semantic_key=semantic_key,
        event_type=pattern.event_type,
        title=pattern.title,
        event_date=event_date,
        event_time=event_time,
        date_precision=date_precision,
        raw_date_text=raw_date_text,
        source_document_id=source_document_id,
        source_page=source_page,
        source_excerpt=merged_excerpt,
        evidence_fragments=[_excerpt(fragment) for fragment in fragments if fragment.strip()],
    )


def _detected_event_from_context(
    pattern: EventPattern,
    source_document_id: str,
    source_page: int | None,
    context: str,
    preferred_excerpt: str,
) -> DetectedEvent | None:
    if _is_structural_label_context(context):
        return None
    if not _is_procedural_event_context(pattern, context):
        return None

    event_date, date_precision, raw_date_text = _parse_date_without_year_fallback(context)
    if event_date is None:
        return None

    event_time = _parse_time(context)
    return _build_detected_event(
        pattern=pattern,
        source_document_id=source_document_id,
        source_page=source_page,
        event_date=event_date,
        date_precision=date_precision,
        raw_date_text=raw_date_text,
        event_time=event_time,
        fragments=[context],
    )


def _path_b_detect_event_from_fragments(
    *,
    pattern: EventPattern,
    fragments: list[TextFragment],
    source_document_id: str,
    source_page: int | None,
) -> list[DetectedEvent]:
    detected: list[DetectedEvent] = []

    for index, fragment in enumerate(fragments):
        date_value, date_precision, raw_date_text = _parse_date_without_year_fallback(fragment.text)
        if date_value is None:
            partial_date = _parse_day_month_without_year(fragment.text)
            if partial_date is None:
                continue
            inferred_year = _infer_year_from_neighbor_fragments(fragments, index)
            if inferred_year is None:
                continue
            day, month, raw_partial = partial_date
            try:
                date_value = date(inferred_year, month, day)
            except ValueError:
                continue
            date_precision = DATE_PRECISION_DAY
            raw_date_text = raw_partial

        anchor_fragment: TextFragment | None = None
        for offset in range(0, 4):
            probe_index = index - offset
            if probe_index < 0:
                break
            probe = fragments[probe_index]
            if _is_structural_label_context(probe.text):
                continue
            if _anchor_matches(pattern, probe.text):
                anchor_fragment = probe
                break

        if anchor_fragment is None:
            continue

        between_count = index - anchor_fragment.index
        if between_count > 3:
            continue

        candidate_fragments: list[str] = [anchor_fragment.text]
        if anchor_fragment.index != index:
            candidate_fragments.append(fragment.text)

        event_time = _parse_time(fragment.text)
        if event_time is None:
            next_index = index + 1
            if next_index < len(fragments):
                next_fragment = fragments[next_index]
                if next_fragment.index - index == 1 and _time_only_fragment(next_fragment.text):
                    event_time = _parse_time(next_fragment.text)
                    if event_time is not None:
                        candidate_fragments.append(next_fragment.text)

        combined_context = " ".join(candidate_fragments)
        if not _is_procedural_event_context(pattern, combined_context):
            continue

        detected.append(
            _build_detected_event(
                pattern=pattern,
                source_document_id=source_document_id,
                source_page=source_page,
                event_date=date_value,
                date_precision=date_precision,
                raw_date_text=raw_date_text,
                event_time=event_time,
                fragments=candidate_fragments,
            )
        )

    return detected


def _gather_detected_events(db: Session, tender_id: str) -> list[DetectedEvent]:
    statement = (
        select(NormalizedContent, DocumentPage, TenderDocument)
        .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
        .join(TenderDocument, TenderDocument.id == DocumentPage.document_id)
        .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
        .order_by(TenderDocument.original_filename.asc(), DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
    )

    detected: list[DetectedEvent] = []
    for normalized_content, page, document in db.execute(statement).all():
        text = (normalized_content.normalized_text or "").strip()
        if not text:
            continue

        segments = _context_segments(text)
        for segment in segments:
            for pattern in EVENT_PATTERNS:
                if not _anchor_matches(pattern, segment):
                    continue
                event = _detected_event_from_context(
                    pattern=pattern,
                    source_document_id=document.id,
                    source_page=page.page_number,
                    context=segment,
                    preferred_excerpt=segment,
                )
                if event is not None:
                    detected.append(event)

        fragments = _ordered_fragments(text)
        for pattern in EVENT_PATTERNS:
            detected.extend(
                _path_b_detect_event_from_fragments(
                    pattern=pattern,
                    fragments=fragments,
                    source_document_id=document.id,
                    source_page=page.page_number,
                )
            )

    return detected


def _effective_event_payload(event: TenderEvent) -> dict[str, Any]:
    return {
        "event_type": event.human_event_type or event.event_type,
        "title": event.human_title or event.title,
        "event_date": event.human_event_date or event.event_date,
        "event_time": event.human_event_time or event.event_time,
        "date_precision": event.human_date_precision or event.date_precision,
        "timezone": event.human_timezone or event.timezone,
    }


def _serialize_tender_event(event: TenderEvent) -> dict[str, Any]:
    effective = _effective_event_payload(event)
    evidence_payload = [
        {
            "id": item.id,
            "source_document_id": item.source_document_id,
            "source_filename": item.source_document.original_filename if item.source_document else None,
            "source_page": item.source_page,
            "source_excerpt": item.source_excerpt,
        }
        for item in sorted(event.evidence, key=lambda row: (row.source_document_id, row.source_page or 0, row.id))
    ]

    return {
        "id": event.id,
        "tender_id": event.tender_id,
        "semantic_key": event.semantic_key,
        "event_type": effective["event_type"],
        "title": effective["title"],
        "event_date": effective["event_date"],
        "event_time": effective["event_time"],
        "date_precision": effective["date_precision"],
        "timezone": effective["timezone"],
        "review_status": event.review_status,
        "detection_origin": event.detection_origin,
        "detector_version": event.detector_version,
        "source_document_id": event.source_document_id,
        "source_page": event.source_page,
        "source_excerpt": event.source_excerpt,
        "source_filename": event.source_document.original_filename if event.source_document else None,
        "raw_date_text": event.raw_date_text,
        "human_event_type": event.human_event_type,
        "human_title": event.human_title,
        "human_event_date": event.human_event_date,
        "human_event_time": event.human_event_time,
        "human_date_precision": event.human_date_precision,
        "human_timezone": event.human_timezone,
        "human_note": event.human_note,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "evidence": evidence_payload,
    }


def _timeline_sort_key(event: TenderEvent) -> tuple[int, date, int, time, str, str]:
    effective = _effective_event_payload(event)
    event_date = effective["event_date"]
    event_time = effective["event_time"]

    has_date = event_date is None
    has_time = event_time is None
    return (
        1 if has_date else 0,
        event_date or date.max,
        1 if has_time else 0,
        event_time or time.max,
        effective["event_type"],
        event.id,
    )


def list_tender_events(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    events = (
        db.execute(
            select(TenderEvent)
            .where(TenderEvent.tender_id == tender_id)
            .options(selectinload(TenderEvent.source_document), selectinload(TenderEvent.evidence).selectinload(TenderEventEvidence.source_document))
        )
        .scalars()
        .all()
    )
    events.sort(key=_timeline_sort_key)

    duplicate_semantic_count = 0
    semantic_counts: dict[str, int] = {}
    for event in events:
        semantic_counts[event.semantic_key] = semantic_counts.get(event.semantic_key, 0) + 1
    for count in semantic_counts.values():
        if count > 1:
            duplicate_semantic_count += count - 1

    status_counts = {
        REVIEW_SUGGESTED: 0,
        REVIEW_CONFIRMED: 0,
        REVIEW_REJECTED: 0,
    }
    for event in events:
        status_counts[event.review_status] = status_counts.get(event.review_status, 0) + 1

    return {
        "tender_id": tender_id,
        "timeline_version": EVENT_DETECTOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "counts": {
            "total_events": len(events),
            "suggested_events": status_counts.get(REVIEW_SUGGESTED, 0),
            "confirmed_events": status_counts.get(REVIEW_CONFIRMED, 0),
            "rejected_events": status_counts.get(REVIEW_REJECTED, 0),
            "duplicate_semantic_count": duplicate_semantic_count,
        },
        "events": [_serialize_tender_event(event) for event in events],
    }


def analyze_tender_events(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    detected = _gather_detected_events(db, tender_id)
    grouped: dict[str, list[DetectedEvent]] = {}
    for item in detected:
        grouped.setdefault(item.semantic_key, []).append(item)

    existing_events = (
        db.execute(select(TenderEvent).where(TenderEvent.tender_id == tender_id))
        .scalars()
        .all()
    )
    existing_index = {item.semantic_key: item for item in existing_events}

    detected_semantic_keys = set(grouped.keys())

    for event in existing_events:
        if (
            event.detection_origin == ORIGIN_DETERMINISTIC
            and event.review_status == REVIEW_SUGGESTED
            and event.semantic_key not in detected_semantic_keys
        ):
            db.delete(event)

    if not grouped:
        db.flush()
        return list_tender_events(db, tender_id)

    for semantic_key in sorted(grouped.keys()):
        samples = sorted(grouped[semantic_key], key=lambda item: (item.source_document_id, item.source_page or 0, item.source_excerpt))
        primary = samples[0]
        event = existing_index.get(semantic_key)
        if event is None:
            event = TenderEvent(
                tender_id=tender_id,
                semantic_key=semantic_key,
                event_type=primary.event_type,
                title=primary.title,
                event_date=primary.event_date,
                event_time=primary.event_time,
                date_precision=primary.date_precision,
                timezone="America/Mexico_City",
                raw_date_text=primary.raw_date_text,
                review_status=REVIEW_SUGGESTED,
                detection_origin=ORIGIN_DETERMINISTIC,
                detector_version=EVENT_DETECTOR_VERSION,
                source_document_id=primary.source_document_id,
                source_page=primary.source_page,
                source_excerpt=primary.source_excerpt,
            )
            db.add(event)
            db.flush()
            existing_index[semantic_key] = event
        else:
            has_human_override = any(
                [
                    event.human_event_type,
                    event.human_title,
                    event.human_event_date,
                    event.human_event_time,
                    event.human_date_precision,
                    event.human_timezone,
                    event.human_note,
                ]
            )
            if event.review_status == REVIEW_SUGGESTED and not has_human_override:
                event.event_type = primary.event_type
                event.title = primary.title
                event.event_date = primary.event_date
                event.event_time = primary.event_time
                event.date_precision = primary.date_precision
                event.raw_date_text = primary.raw_date_text
                event.source_document_id = primary.source_document_id
                event.source_page = primary.source_page
                event.source_excerpt = primary.source_excerpt
                event.detector_version = EVENT_DETECTOR_VERSION
                event.detection_origin = ORIGIN_DETERMINISTIC

        existing_evidence = {
            (row.source_document_id, row.source_page, row.excerpt_sha256): row
            for row in event.evidence
        }
        expected_evidence_keys = set()
        for sample in samples:
            for fragment_text in sample.evidence_fragments or [sample.source_excerpt]:
                excerpt_sha = hashlib.sha256(fragment_text.encode("utf-8")).hexdigest()
                evidence_key = (sample.source_document_id, sample.source_page, excerpt_sha)
                expected_evidence_keys.add(evidence_key)
                if evidence_key in existing_evidence:
                    continue
                new_evidence = TenderEventEvidence(
                    event=event,
                    source_document_id=sample.source_document_id,
                    source_page=sample.source_page,
                    source_excerpt=fragment_text,
                    excerpt_sha256=excerpt_sha,
                )
                db.add(new_evidence)
                existing_evidence[evidence_key] = new_evidence

        has_human_override = any(
            [
                event.human_event_type,
                event.human_title,
                event.human_event_date,
                event.human_event_time,
                event.human_date_precision,
                event.human_timezone,
                event.human_note,
            ]
        )
        if event.review_status == REVIEW_SUGGESTED and not has_human_override:
            for evidence_key, evidence_row in existing_evidence.items():
                if evidence_key not in expected_evidence_keys:
                    db.delete(evidence_row)

    db.flush()
    return list_tender_events(db, tender_id)


def update_tender_event_human_decision(
    db: Session,
    tender_id: str,
    event_id: str,
    action: str,
    *,
    event_type: str | None = None,
    title: str | None = None,
    event_date: date | None = None,
    event_time: time | None = None,
    date_precision: str | None = None,
    timezone_name: str | None = None,
    human_note: str | None = None,
) -> dict[str, Any]:
    event = db.get(TenderEvent, event_id)
    if event is None or event.tender_id != tender_id:
        raise ValueError("Event not found")

    normalized_action = action.strip().upper()
    if normalized_action == EVENT_ACTION_CONFIRM:
        event.review_status = REVIEW_CONFIRMED
    elif normalized_action == EVENT_ACTION_REJECT:
        event.review_status = REVIEW_REJECTED
    elif normalized_action == EVENT_ACTION_RESET:
        event.review_status = REVIEW_SUGGESTED
        event.human_event_type = None
        event.human_title = None
        event.human_event_date = None
        event.human_event_time = None
        event.human_date_precision = None
        event.human_timezone = None
        event.human_note = None
    elif normalized_action == EVENT_ACTION_OVERRIDE:
        event.review_status = REVIEW_CONFIRMED
        if event_type is not None:
            event.human_event_type = event_type.strip() or None
        if title is not None:
            event.human_title = title.strip() or None
        if event_date is not None:
            event.human_event_date = event_date
        if event_time is not None:
            event.human_event_time = event_time
        if date_precision is not None:
            event.human_date_precision = date_precision
        if timezone_name is not None:
            event.human_timezone = timezone_name
        if human_note is not None:
            event.human_note = human_note
    else:
        raise ValueError(f"Unsupported action: {action}")

    db.flush()
    return list_tender_events(db, tender_id)
