from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.local_vision import VisionAnalysisRead, VisionPageImage, build_local_vision_provider, normalize_vision_mode, render_document_pages_as_png
from app.models import DocumentClassification, DocumentPage, NormalizedContent, Tender, TenderDocument, TenderItem

TENDER_ITEM_DETECTOR_VERSION = "mvp-06.1"
TENDER_ITEM_STATUS_DETERMINED = "DETERMINED"
TENDER_ITEM_ORIGIN_DETERMINISTIC = "DETERMINISTIC"

HEADING_RE = re.compile(
    r"^(?P<label>(?:PARTIDA|CONCEPTO|I[TÍ]EM|ITEM|NO\.?))\s*:?\s*(?P<number>[A-Z]?[- ]?\d+(?:\.\d+)*)\s*$",
    re.IGNORECASE,
)
HEADING_INLINE_RE = re.compile(
    r"^(?P<label>(?:PARTIDA|CONCEPTO|I[TÍ]EM|ITEM|NO\.?))\s*:?\s*(?P<number>[A-Z]?[- ]?\d+(?:\.\d+)*)\s*[-:]\s*(?P<desc>.+)$",
    re.IGNORECASE,
)
TABLE_PIPE_RE = re.compile(
    r"^(?P<number>[A-Z]?[- ]?\d+(?:\.\d+)*|PARTIDA\s+\d+)\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*(?P<qty>\d+(?:[\.,]\d+)?)\s*\|\s*(?P<unit>[^|]{2,})$",
    re.IGNORECASE,
)
TABLE_SPACED_RE = re.compile(
    r"^(?P<number>[A-Z]?[- ]?\d+(?:\.\d+)*|PARTIDA\s+\d+)\s{2,}(?P<desc>.+?)\s{2,}(?P<qty>\d+(?:[\.,]\d+)?)\s{2,}(?P<unit>[A-ZÁÉÍÓÚÑa-záéíóúñ\./ ]{2,})$",
)
QUANTITY_RE = re.compile(r"^(?:CANTIDAD|CANT\.?|QTY)\s*:?\s*(\d+(?:[\.,]\d+)?)$", re.IGNORECASE)
UNIT_RE = re.compile(r"^(?:UNIDAD|U\.?M\.?|UNIT)\s*:?\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\./ ]{2,40})$", re.IGNORECASE)
BARE_ITEM_NUMBER_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\.?$")
NUMERIC_VALUE_RE = re.compile(r"^\d+(?:[\.,]\d+)?$")
NORMATIVE_CODE_RE = re.compile(r"\b(?:NOM|NMX|ISO|IEC|API|ASME|NFPA)[-\s]?[A-Z0-9\-/\.]*\b", re.IGNORECASE)

VALID_PROCUREMENT_UNIT_ALIASES: dict[str, str] = {
    "PZA": "PZA",
    "PIEZA": "PIEZA",
    "PIEZAS": "PIEZA",
    "SERVICIO": "SERVICIO",
    "SERVICIOS": "SERVICIO",
    "LOTE": "LOTE",
    "LOTES": "LOTE",
    "JUEGO": "JUEGO",
    "JUEGOS": "JUEGO",
    "KIT": "KIT",
    "KITS": "KIT",
    "MES": "MES",
    "MESES": "MES",
    "DIA": "DIA",
    "DIAS": "DIA",
    "DÍA": "DIA",
    "DÍAS": "DIA",
    "HORA": "HORA",
    "HORAS": "HORA",
    "EVENTO": "EVENTO",
    "EVENTOS": "EVENTO",
    "PAQUETE": "PAQUETE",
    "PAQUETES": "PAQUETE",
    "UNIDAD": "UNIDAD",
    "UNIDADES": "UNIDAD",
}

NON_ITEM_CLASSIFICATION_HINTS = {
    "NOTICE",
    "BIDDING_RULES",
    "ADDENDUM_MODIFICATION",
    "ADMINISTRATIVE_LEGAL_REQUIREMENTS",
    "FORM_TEMPLATE",
}

ADMIN_REQUIREMENT_RE = re.compile(
    r"\b(licitante|participante|oferente|interesado)\b.*\b(deber[aá]|debe|presentar|acreditar|cumplir|entregar)\b",
    re.IGNORECASE,
)
HEADER_ONLY_RE = re.compile(
    r"^(PARTIDA|CONCEPTO|DESCRIPCION|DESCRIPCI[OÓ]N|CANTIDAD|UNIDAD|NO\.?|ITEM|I[TÍ]EM|LICITACI[OÓ]N\s+P[UÚ]BLICA|ANEXO\s+[A-Z0-9\-]+)$",
    re.IGNORECASE,
)


@dataclass
class SourceLine:
    number: int
    text: str


@dataclass
class PageSource:
    page_number: int
    normalized_content_id: str
    text: str


@dataclass
class DetectedTenderItem:
    tender_id: str
    source_document_id: str
    source_page: int
    document_page_id: str | None
    normalized_content_id: str
    item_number: str | None
    parent_item_number: str | None
    raw_description: str
    quantity: Decimal | None
    unit: str | None
    source_excerpt: str
    source_locator: str
    extraction_confidence: float


@dataclass
class DetectionSummary:
    scanned_pages: int = 0
    items_detected: int = 0
    warnings: list[str] | None = None


def _normalize_space(value: str) -> str:
    return " ".join((value or "").replace("\r", "\n").split())


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_key(value: str) -> str:
    return _strip_accents(_normalize_space(value).lower())


def _is_header_only(value: str) -> bool:
    return bool(HEADER_ONLY_RE.match(_normalize_space(value)))


def _is_requirement_like(value: str) -> bool:
    return bool(ADMIN_REQUIREMENT_RE.search(value))


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    compact = value.strip().replace(",", ".")
    if not compact:
        return None
    try:
        return Decimal(compact)
    except InvalidOperation:
        return None


def _normalize_item_number_token(value: str) -> str:
    compact = _normalize_space(value)
    compact = re.sub(r"^(?:PARTIDA|CONCEPTO|I[TÍ]EM|ITEM|NO\.?)\s*:?\s*", "", compact, flags=re.IGNORECASE)
    return _normalize_space(compact)


def _sanitize_description(lines: list[str]) -> str:
    cleaned = [line for line in (_normalize_space(line) for line in lines) if line and not _is_header_only(line)]
    return _normalize_space(" ".join(cleaned))


def _looks_like_catalog_unit(value: str) -> bool:
    return _normalize_procurement_unit(value) is not None


def _normalize_procurement_unit(value: str | None) -> str | None:
    if value is None:
        return None
    compact = _normalize_space(value)
    if not compact or _is_header_only(compact):
        return None
    key = compact.upper().replace(".", "")
    return VALID_PROCUREMENT_UNIT_ALIASES.get(key)


def _looks_like_meaningful_description(value: str) -> bool:
    return bool(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", value))


def _is_normative_reference_like(item_number: str | None, description: str) -> bool:
    normalized_description = _normalize_key(description)
    has_normative_word = any(
        token in normalized_description
        for token in ("norma", "normativo", "referencia", "estandar", "standard", "especificacion normativa")
    )
    has_normative_code = bool(NORMATIVE_CODE_RE.search(description))
    code_like_number = bool(item_number and re.match(r"^[A-Z]-\d{2,4}$", item_number))
    return (has_normative_word or has_normative_code) and code_like_number


def _header_context_score(lines: list[SourceLine], index: int) -> int:
    start = max(0, index - 14)
    context = "\n".join(lines[pos].text for pos in range(start, index))
    normalized = _normalize_key(context)
    score = 0
    for token in ("partida", "concepto", "cantidad", "unidad"):
        if token in normalized:
            score += 1
    return score


def _is_credible_item_candidate(
    *,
    item_number: str | None,
    description: str,
    quantity: Decimal | None,
    unit: str | None,
    parser_kind: str,
    header_context: int,
    role_penalty: bool,
    consumed_lines: int,
) -> bool:
    if not description or _is_requirement_like(description):
        return False

    if _is_normative_reference_like(item_number, description) and quantity is None and unit is None:
        return False

    if parser_kind == "table" and quantity is None and unit is None:
        return False

    if parser_kind == "bare" and consumed_lines > 8:
        return False

    if parser_kind == "bare" and header_context < 2:
        return False

    if role_penalty and parser_kind == "bare" and (quantity is None or unit is None):
        return False

    return True


def _is_probable_column_drift_tail(value: str) -> bool:
    compact = _normalize_space(value)
    if not compact:
        return False
    if _normalize_procurement_unit(compact) is not None:
        return False
    if NUMERIC_VALUE_RE.match(compact):
        return False
    words = compact.split()
    if len(words) > 3:
        return False
    return compact.upper() == compact


def _page_has_catalog_structure(text: str) -> bool:
    normalized = _normalize_key(text)
    signals = 0
    for token in ("partida", "concepto", "cantidad", "unidad"):
        if token in normalized:
            signals += 1
    return signals >= 2


def _item_signal_score(text: str) -> int:
    compact = text or ""
    score = 0
    score += len(re.findall(r"(?m)^\s*\d+\.\s*$", compact)) * 6
    score += len(re.findall(r"\|", compact))
    if _page_has_catalog_structure(compact):
        score += 4
    return score


def _is_bare_item_heading(text: str) -> bool:
    compact = _normalize_space(text)
    if not BARE_ITEM_NUMBER_RE.match(compact):
        return False
    return compact.endswith(".") or "." in compact


def _build_source_locator(page: int, start_line: int, end_line: int, local_index: int) -> str:
    return f"page:{page}|lines:{start_line}-{end_line}|item:{local_index}"


def _build_semantic_fingerprint(item: DetectedTenderItem) -> str:
    payload = "|".join(
        [
            item.tender_id,
            item.source_document_id,
            str(item.source_page),
            item.item_number or "",
            item.raw_description,
            str(item.quantity) if item.quantity is not None else "",
            item.unit or "",
            item.source_locator,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _excerpt_from_lines(lines: list[SourceLine], start: int, end: int) -> str:
    selected = [lines[idx].text for idx in range(start, end + 1) if 0 <= idx < len(lines)]
    text = _normalize_space(" ".join(selected))
    if len(text) <= 1400:
        return text
    return text[:1397].rstrip() + "..."


def _line_is_blank(text: str) -> bool:
    return not _normalize_space(text)


def _parse_table_row(line: str) -> tuple[str, str, Decimal | None, str | None] | None:
    compact = _normalize_space(line)
    for pattern in (TABLE_PIPE_RE, TABLE_SPACED_RE):
        match = pattern.match(compact)
        if not match:
            continue
        number = _normalize_item_number_token(match.group("number"))
        description = _normalize_space(match.group("desc"))
        quantity = _to_decimal(match.group("qty"))
        unit = _normalize_procurement_unit(match.group("unit"))

        if _is_header_only(number) or _is_header_only(description):
            return None
        if _is_requirement_like(description):
            return None
        return number, description, quantity, unit
    return None


def _extract_page_items(
    *,
    tender_id: str,
    source_document_id: str,
    page: PageSource,
    document_page_id: str | None,
    role_penalty: bool,
) -> tuple[list[DetectedTenderItem], list[str]]:
    lines = [SourceLine(number=index + 1, text=_normalize_space(raw)) for index, raw in enumerate(page.text.replace("\r", "\n").split("\n"))]
    catalog_like_page = _page_has_catalog_structure(page.text)

    items: list[DetectedTenderItem] = []
    warnings: list[str] = []
    i = 0
    local_index = 0

    while i < len(lines):
        line = lines[i].text
        if _line_is_blank(line):
            i += 1
            continue

        table_row = _parse_table_row(line)
        if table_row is not None:
            number, description, quantity, unit = table_row
            header_score = _header_context_score(lines, i)
            if not _is_credible_item_candidate(
                item_number=number,
                description=description,
                quantity=quantity,
                unit=unit,
                parser_kind="table",
                header_context=header_score,
                role_penalty=role_penalty,
                consumed_lines=1,
            ):
                i += 1
                continue
            local_index += 1
            locator = _build_source_locator(page.page_number, lines[i].number, lines[i].number, local_index)
            item = DetectedTenderItem(
                tender_id=tender_id,
                source_document_id=source_document_id,
                source_page=page.page_number,
                document_page_id=document_page_id,
                normalized_content_id=page.normalized_content_id,
                item_number=number,
                parent_item_number=None,
                raw_description=description,
                quantity=quantity,
                unit=unit,
                source_excerpt=_excerpt_from_lines(lines, i, i),
                source_locator=locator,
                extraction_confidence=0.95,
            )
            items.append(item)
            i += 1
            continue

        inline_heading = HEADING_INLINE_RE.match(line)
        if inline_heading:
            number = _normalize_item_number_token(inline_heading.group("number"))
            description = _normalize_space(inline_heading.group("desc"))
            header_score = _header_context_score(lines, i)
            if (
                description
                and not _is_header_only(description)
                and _is_credible_item_candidate(
                    item_number=number,
                    description=description,
                    quantity=None,
                    unit=None,
                    parser_kind="inline",
                    header_context=header_score,
                    role_penalty=role_penalty,
                    consumed_lines=1,
                )
            ):
                local_index += 1
                locator = _build_source_locator(page.page_number, lines[i].number, lines[i].number, local_index)
                items.append(
                    DetectedTenderItem(
                        tender_id=tender_id,
                        source_document_id=source_document_id,
                        source_page=page.page_number,
                        document_page_id=document_page_id,
                        normalized_content_id=page.normalized_content_id,
                        item_number=number,
                        parent_item_number=None,
                        raw_description=description,
                        quantity=None,
                        unit=None,
                        source_excerpt=_excerpt_from_lines(lines, i, i),
                        source_locator=locator,
                        extraction_confidence=0.9,
                    )
                )
            i += 1
            continue

        bare_number_match = BARE_ITEM_NUMBER_RE.match(line)
        if catalog_like_page and bare_number_match and _is_bare_item_heading(line):
            item_number = _normalize_space(bare_number_match.group("number"))
            block_lines: list[str] = []
            start_idx = i
            end_idx = i
            j = i + 1
            while j < len(lines):
                next_line = lines[j].text
                if _line_is_blank(next_line):
                    end_idx = j
                    j += 1
                    continue
                if _is_bare_item_heading(next_line):
                    break
                if HEADING_RE.match(next_line) or HEADING_INLINE_RE.match(next_line) or _parse_table_row(next_line) is not None:
                    break
                block_lines.append(next_line)
                end_idx = j
                j += 1

            quantity: Decimal | None = None
            unit: str | None = None
            pruned_lines = [line_value for line_value in block_lines if line_value and not _is_header_only(line_value)]

            if pruned_lines and NUMERIC_VALUE_RE.match(pruned_lines[-1]):
                quantity = _to_decimal(pruned_lines.pop())
            elif len(pruned_lines) >= 2 and NUMERIC_VALUE_RE.match(pruned_lines[-2]) and _normalize_procurement_unit(pruned_lines[-1]) is None:
                quantity = _to_decimal(pruned_lines.pop(-2))

            if pruned_lines and _looks_like_catalog_unit(pruned_lines[-1]):
                unit = _normalize_procurement_unit(pruned_lines.pop())
            elif pruned_lines and _is_probable_column_drift_tail(pruned_lines[-1]):
                pruned_lines.pop()

            description = _sanitize_description(pruned_lines)
            header_score = _header_context_score(lines, i)
            consumed_lines = max(1, end_idx - start_idx + 1)
            if description and _looks_like_meaningful_description(description) and _is_credible_item_candidate(
                item_number=item_number,
                description=description,
                quantity=quantity,
                unit=unit,
                parser_kind="bare",
                header_context=header_score,
                role_penalty=role_penalty,
                consumed_lines=consumed_lines,
            ):
                local_index += 1
                locator = _build_source_locator(page.page_number, lines[start_idx].number, lines[end_idx].number, local_index)
                items.append(
                    DetectedTenderItem(
                        tender_id=tender_id,
                        source_document_id=source_document_id,
                        source_page=page.page_number,
                        document_page_id=document_page_id,
                        normalized_content_id=page.normalized_content_id,
                        item_number=item_number,
                        parent_item_number=None,
                        raw_description=description,
                        quantity=quantity,
                        unit=unit,
                        source_excerpt=_excerpt_from_lines(lines, start_idx, end_idx),
                        source_locator=locator,
                        extraction_confidence=0.88,
                    )
                )
            i = j
            continue

        heading_match = HEADING_RE.match(line)
        if not heading_match:
            i += 1
            continue

        item_number = _normalize_item_number_token(heading_match.group("number"))
        desc_lines: list[str] = []
        quantity: Decimal | None = None
        unit: str | None = None
        start_idx = i
        end_idx = i

        j = i + 1
        while j < len(lines):
            next_line = lines[j].text
            if _line_is_blank(next_line):
                end_idx = j
                j += 1
                continue

            if HEADING_RE.match(next_line) or HEADING_INLINE_RE.match(next_line) or _parse_table_row(next_line) is not None:
                break

            quantity_match = QUANTITY_RE.match(next_line)
            if quantity_match and quantity is None:
                quantity = _to_decimal(quantity_match.group(1))
                end_idx = j
                j += 1
                continue

            unit_match = UNIT_RE.match(next_line)
            if unit_match and unit is None:
                unit = _normalize_procurement_unit(unit_match.group(1))
                end_idx = j
                j += 1
                continue

            if not _is_header_only(next_line):
                desc_lines.append(next_line)
                end_idx = j
            j += 1

        description = _sanitize_description(desc_lines)
        header_score = _header_context_score(lines, i)
        consumed_lines = max(1, end_idx - start_idx + 1)
        if description and _is_credible_item_candidate(
            item_number=item_number,
            description=description,
            quantity=quantity,
            unit=unit,
            parser_kind="heading",
            header_context=header_score,
            role_penalty=role_penalty,
            consumed_lines=consumed_lines,
        ):
            local_index += 1
            locator = _build_source_locator(page.page_number, lines[start_idx].number, lines[end_idx].number, local_index)
            items.append(
                DetectedTenderItem(
                    tender_id=tender_id,
                    source_document_id=source_document_id,
                    source_page=page.page_number,
                    document_page_id=document_page_id,
                    normalized_content_id=page.normalized_content_id,
                    item_number=item_number,
                    parent_item_number=None,
                    raw_description=description,
                    quantity=quantity,
                    unit=unit,
                    source_excerpt=_excerpt_from_lines(lines, start_idx, end_idx),
                    source_locator=locator,
                    extraction_confidence=0.9,
                )
            )
        else:
            warnings.append(f"Skipped heading without reliable description at page {page.page_number} line {lines[start_idx].number}")

        i = j

    return items, warnings


def _select_best_page_sources(db: Session, tender_id: str, document_id: str) -> list[tuple[PageSource, str | None]]:
    rows = db.execute(
        select(
            DocumentPage.id,
            DocumentPage.page_number,
            NormalizedContent.id,
            NormalizedContent.normalized_text,
            NormalizedContent.source_type,
            NormalizedContent.char_count,
            NormalizedContent.created_at,
        )
        .join(NormalizedContent, NormalizedContent.document_page_id == DocumentPage.id)
        .join(TenderDocument, TenderDocument.id == DocumentPage.document_id)
        .where(TenderDocument.id == document_id, TenderDocument.tender_id == tender_id)
        .order_by(DocumentPage.page_number.asc(), NormalizedContent.created_at.asc())
    ).all()

    by_page: dict[str, tuple[PageSource, str | None, int, int, int, datetime]] = {}
    for document_page_id, page_number, normalized_content_id, normalized_text, source_type, char_count, created_at in rows:
        text = (normalized_text or "").strip()
        if not text:
            continue
        rank = 0 if source_type == "NATIVE_PDF" else 1
        signal_score = _item_signal_score(text)
        entry = (
            PageSource(
                page_number=page_number,
                normalized_content_id=normalized_content_id,
                text=text,
            ),
            document_page_id,
            rank,
            signal_score,
            int(char_count or 0),
            created_at,
        )
        existing = by_page.get(document_page_id)
        if existing is None:
            by_page[document_page_id] = entry
            continue
        _, _, existing_rank, existing_signal_score, existing_chars, existing_created = existing
        if (-signal_score, rank, -int(char_count or 0), created_at) < (-existing_signal_score, existing_rank, -existing_chars, existing_created):
            by_page[document_page_id] = entry

    selected = [(value[0], value[1]) for value in by_page.values()]
    selected.sort(key=lambda value: value[0].page_number)
    return selected


def _document_type_hint(classification: DocumentClassification | None) -> str:
    if classification is None:
        return "UNKNOWN"
    return (classification.human_type or classification.suggested_type or "UNKNOWN").strip() or "UNKNOWN"


def _page_has_vision_scope_signal(text: str) -> bool:
    normalized = _normalize_key(text)
    if not normalized:
        return False
    if _page_has_catalog_structure(text):
        return True
    signal_keywords = (
        "alcance",
        "partida",
        "concepto",
        "servicio",
        "equipo",
        "material",
        "unidad",
        "cantidad",
        "catalogo",
        "catalogo de conceptos",
    )
    return any(keyword in normalized for keyword in signal_keywords)


def _select_vision_page_sources(selected_sources: list[tuple[PageSource, str | None]], vision_mode: str) -> list[PageSource]:
    settings = get_settings()
    max_pages = max(1, int(settings.licitia_vision_max_pages or 4))
    normalized_mode = normalize_vision_mode(vision_mode)

    if normalized_mode == "OFF":
        return []

    scored_sources = [
        (page_source, _item_signal_score(page_source.text))
        for page_source, _ in selected_sources
        if _page_has_vision_scope_signal(page_source.text)
    ]

    if normalized_mode == "FORCE" and not scored_sources:
        return [page_source for page_source, _ in selected_sources[:max_pages]]

    scored_sources.sort(key=lambda value: (-value[1], value[0].page_number))
    return [page_source for page_source, _ in scored_sources[:max_pages]]


def _should_attempt_vision_analysis(
    *,
    classification: DocumentClassification | None,
    detected_items: list[DetectedTenderItem],
    selected_sources: list[tuple[PageSource, str | None]],
    vision_mode: str,
) -> bool:
    normalized_mode = normalize_vision_mode(vision_mode)
    if normalized_mode == "OFF":
        return False
    if normalized_mode == "FORCE":
        return True
    if detected_items:
        return False
    if classification and classification.suggested_type in NON_ITEM_CLASSIFICATION_HINTS:
        return False
    return any(_page_has_vision_scope_signal(page_source.text) for page_source, _ in selected_sources)


def _build_vision_analysis(
    *,
    document: TenderDocument,
    classification: DocumentClassification | None,
    selected_sources: list[tuple[PageSource, str | None]],
    detected_items: list[DetectedTenderItem],
    vision_mode: str,
) -> VisionAnalysisRead | None:
    if not _should_attempt_vision_analysis(
        classification=classification,
        detected_items=detected_items,
        selected_sources=selected_sources,
        vision_mode=vision_mode,
    ):
        return None

    page_sources = _select_vision_page_sources(selected_sources, vision_mode)
    if not page_sources:
        return None

    placeholder_pages = [VisionPageImage(page_number=page_source.page_number, png_bytes=b"", source_locator=f"page:{page_source.page_number}") for page_source in page_sources]

    provider = build_local_vision_provider()
    if provider.provider_status != "AVAILABLE":
        return provider.analyze_scope_pages(
            tender_id=document.tender_id,
            document_id=document.id,
            source_filename=document.original_filename,
            document_type=_document_type_hint(classification),
            vision_mode=normalize_vision_mode(vision_mode),
            pages=placeholder_pages,
        )

    selected_pages = render_document_pages_as_png(document, [page_source.page_number for page_source in page_sources])
    if not selected_pages:
        return provider.analyze_scope_pages(
            tender_id=document.tender_id,
            document_id=document.id,
            source_filename=document.original_filename,
            document_type=_document_type_hint(classification),
            vision_mode=normalize_vision_mode(vision_mode),
            pages=placeholder_pages,
        )

    for image in selected_pages:
        for page_source in page_sources:
            if page_source.page_number == image.page_number:
                image.source_excerpt = _excerpt_from_lines([
                    SourceLine(number=1, text=page_source.text)
                ], 0, 0)
                break

    return provider.analyze_scope_pages(
        tender_id=document.tender_id,
        document_id=document.id,
        source_filename=document.original_filename,
        document_type=_document_type_hint(classification),
        vision_mode=normalize_vision_mode(vision_mode),
        pages=selected_pages,
    )


def _serialize_item(item: TenderItem) -> dict[str, Any]:
    source_document = item.source_document
    return {
        "id": item.id,
        "tender_id": item.tender_id,
        "source_document_id": item.source_document_id,
        "source_filename": source_document.original_filename if source_document else None,
        "source_page": item.source_page,
        "item_number": item.item_number,
        "parent_item_number": item.parent_item_number,
        "raw_description": item.raw_description,
        "quantity": item.quantity,
        "unit": item.unit,
        "source_excerpt": item.source_excerpt,
        "source_locator": item.source_locator,
        "extraction_confidence": item.extraction_confidence,
        "extraction_status": item.extraction_status,
        "detection_origin": item.detection_origin,
        "detector_version": item.detector_version,
        "semantic_fingerprint": item.semantic_fingerprint,
        "document_page_id": item.document_page_id,
        "normalized_content_id": item.normalized_content_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_tender_items(db: Session, tender_id: str, *, document_id: str | None = None) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    statement = select(TenderItem).where(TenderItem.tender_id == tender_id)
    if document_id:
        statement = statement.where(TenderItem.source_document_id == document_id)

    rows = db.execute(statement.order_by(TenderItem.source_document_id.asc(), TenderItem.source_page.asc(), TenderItem.created_at.asc())).scalars().all()

    items_with_number = sum(1 for row in rows if row.item_number)
    items_with_quantity = sum(1 for row in rows if row.quantity is not None)
    items_with_unit = sum(1 for row in rows if row.unit)
    without_locator = sum(1 for row in rows if not row.source_locator)

    documents_with_items = sorted({row.source_document_id for row in rows})

    return {
        "tender_id": tender_id,
        "items_version": TENDER_ITEM_DETECTOR_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "summary": {
            "total_items": len(rows),
            "documents_with_items": len(documents_with_items),
            "items_with_number": items_with_number,
            "items_with_quantity": items_with_quantity,
            "items_with_unit": items_with_unit,
            "items_without_locator": without_locator,
        },
        "items": [_serialize_item(row) for row in rows],
    }


def get_tender_item(db: Session, tender_id: str, item_id: str) -> dict[str, Any]:
    row = db.get(TenderItem, item_id)
    if row is None or row.tender_id != tender_id:
        raise LookupError("Tender item not found")
    return _serialize_item(row)


def analyze_tender_document_items(db: Session, tender_id: str, document_id: str, *, vision_mode: str = "AUTO") -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    document = db.get(TenderDocument, document_id)
    if document is None or document.tender_id != tender_id:
        raise LookupError("Tender document not found")

    classification = db.scalar(select(DocumentClassification).where(DocumentClassification.document_id == document_id))
    role_penalty = bool(classification and classification.suggested_type in NON_ITEM_CLASSIFICATION_HINTS)

    selected_sources = _select_best_page_sources(db, tender_id, document_id)
    detected: list[DetectedTenderItem] = []
    warnings: list[str] = []

    for page_source, document_page_id in selected_sources:
        page_items, page_warnings = _extract_page_items(
            tender_id=tender_id,
            source_document_id=document_id,
            page=page_source,
            document_page_id=document_page_id,
            role_penalty=role_penalty,
        )
        detected.extend(page_items)
        warnings.extend(page_warnings)

    vision_analysis = _build_vision_analysis(
        document=document,
        classification=classification,
        selected_sources=selected_sources,
        detected_items=detected,
        vision_mode=vision_mode,
    )

    existing_rows = db.execute(
        select(TenderItem).where(TenderItem.tender_id == tender_id, TenderItem.source_document_id == document_id)
    ).scalars().all()
    existing_by_fingerprint = {row.semantic_fingerprint: row for row in existing_rows}

    detected_fingerprints: set[str] = set()
    created = 0
    updated = 0
    unchanged = 0

    for item in detected:
        fingerprint = _build_semantic_fingerprint(item)
        detected_fingerprints.add(fingerprint)

        existing = existing_by_fingerprint.get(fingerprint)
        if existing is None:
            created += 1
            db.add(
                TenderItem(
                    tender_id=tender_id,
                    source_document_id=document_id,
                    source_page=item.source_page,
                    document_page_id=item.document_page_id,
                    normalized_content_id=item.normalized_content_id,
                    item_number=item.item_number,
                    parent_item_number=item.parent_item_number,
                    raw_description=item.raw_description,
                    quantity=item.quantity,
                    unit=item.unit,
                    source_excerpt=item.source_excerpt,
                    source_locator=item.source_locator,
                    extraction_confidence=item.extraction_confidence,
                    extraction_status=TENDER_ITEM_STATUS_DETERMINED,
                    detection_origin=TENDER_ITEM_ORIGIN_DETERMINISTIC,
                    detector_version=TENDER_ITEM_DETECTOR_VERSION,
                    semantic_fingerprint=fingerprint,
                )
            )
            continue

        changed = False
        for field, value in (
            ("source_page", item.source_page),
            ("document_page_id", item.document_page_id),
            ("normalized_content_id", item.normalized_content_id),
            ("item_number", item.item_number),
            ("parent_item_number", item.parent_item_number),
            ("raw_description", item.raw_description),
            ("quantity", item.quantity),
            ("unit", item.unit),
            ("source_excerpt", item.source_excerpt),
            ("source_locator", item.source_locator),
            ("extraction_confidence", item.extraction_confidence),
            ("extraction_status", TENDER_ITEM_STATUS_DETERMINED),
            ("detection_origin", TENDER_ITEM_ORIGIN_DETERMINISTIC),
            ("detector_version", TENDER_ITEM_DETECTOR_VERSION),
        ):
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True

        if changed:
            updated += 1
        else:
            unchanged += 1

    deleted = 0
    for row in existing_rows:
        if row.semantic_fingerprint not in detected_fingerprints:
            db.delete(row)
            deleted += 1

    db.flush()

    payload = list_tender_items(db, tender_id, document_id=document_id)
    payload["document_id"] = document_id
    payload["source_filename"] = document.original_filename
    payload["summary"] = {
        **payload["summary"],
        "scanned_pages": len(selected_sources),
        "items_detected": len(detected),
        "items_created": created,
        "items_updated": updated,
        "items_unchanged": unchanged,
        "items_deleted": deleted,
        "warnings_count": len(warnings),
    }
    payload["warnings"] = warnings
    payload["vision_analysis"] = vision_analysis.model_dump(mode="json") if vision_analysis is not None else None
    return payload
