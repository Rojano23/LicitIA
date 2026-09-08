from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, Sequence

from sqlalchemy.orm import Session

from app.scope_quantities import (
    SCOPE_QUANTITY_MEASURE_KIND_AREA,
    SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    SCOPE_QUANTITY_MEASURE_KIND_LOT,
    SCOPE_QUANTITY_MEASURE_KIND_MASS,
    SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    SCOPE_QUANTITY_MEASURE_KIND_VOLUME,
    SCOPE_QUANTITY_RELATION_EXACT,
    ScopeQuantityCandidate,
)

SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED = "MATERIALIZED"
SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES = "NO_QUANTITIES"
SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_QUANTITY_ADAPTER_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE = "INVALID_EVIDENCE"

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"
VISION_SCOPE_QUANTITY_ADAPTER_VERSION = "vision-scope-quantity-adapter-001"

_TERMINAL_QUANTITY_PATTERN = re.compile(
    r"\((\d+(?:\.\d+)?)\s+([^()]+?)\)\.?\s*$",
    re.IGNORECASE,
)

_UNIT_TO_MEASURE_KIND = {
    "PIEZA": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PIEZAS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PZA": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "PZAS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "UNIDAD": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "UNIDADES": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "EQUIPO": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "EQUIPOS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "JUEGO": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "JUEGOS": SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    "SERVICIO": SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    "SERVICIOS": SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    "LOTE": SCOPE_QUANTITY_MEASURE_KIND_LOT,
    "LOTES": SCOPE_QUANTITY_MEASURE_KIND_LOT,
    "PERSONA": SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    "PERSONAS": SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    "TECNICO": SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    "TECNICOS": SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    "DIA": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "DIAS": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "HORA": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "HORAS": SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    "METRO": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    "METROS": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    "M": SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    "M2": SCOPE_QUANTITY_MEASURE_KIND_AREA,
    "M3": SCOPE_QUANTITY_MEASURE_KIND_VOLUME,
    "KG": SCOPE_QUANTITY_MEASURE_KIND_MASS,
    "TON": SCOPE_QUANTITY_MEASURE_KIND_MASS,
}


@dataclass(frozen=True, slots=True)
class ScopeQuantityEvidenceArtifact:
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    scope_detail_excerpt: str
    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    payload: dict | None = None
    scope_detail_review_required: bool = True


@dataclass(frozen=True, slots=True)
class ScopeQuantityAdapterExtractResult:
    source_artifact_key: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidates: tuple[ScopeQuantityCandidate, ...]
    errors: tuple[str, ...] = ()


class ScopeQuantityAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def supports(self, artifact: ScopeQuantityEvidenceArtifact) -> bool:
        ...

    def extract_candidates(self, db: Session, artifact: ScopeQuantityEvidenceArtifact) -> Sequence[ScopeQuantityCandidate]:
        ...


class VisionDetailTranscriptionScopeQuantityAdapter:
    adapter_name = "VisionDetailTranscriptionScopeQuantityAdapter"
    adapter_version = VISION_SCOPE_QUANTITY_ADAPTER_VERSION

    def supports(self, artifact: ScopeQuantityEvidenceArtifact) -> bool:
        if artifact.source_method != "VISION":
            return False
        if _extract_detail_row_index(artifact.source_locator) is None:
            return False

        payload = artifact.payload if isinstance(artifact.payload, dict) else None
        if payload is None:
            return False

        detail = payload.get("detail_transcription")
        if not isinstance(detail, dict):
            return False

        task_type = _optional_text(detail.get("task_type"))
        if task_type is None:
            return False

        return task_type.upper() == VISION_DETAIL_TASK_TYPE

    def extract_candidates(self, db: Session, artifact: ScopeQuantityEvidenceArtifact) -> Sequence[ScopeQuantityCandidate]:
        del db
        payload = artifact.payload if isinstance(artifact.payload, dict) else None
        if payload is None:
            raise ValueError("artifact payload is required")

        detail = payload.get("detail_transcription")
        if not isinstance(detail, dict):
            raise ValueError("detail_transcription payload is required")

        task_type = _optional_text(detail.get("task_type"))
        if task_type is None or task_type.upper() != VISION_DETAIL_TASK_TYPE:
            raise ValueError("Unsupported vision task_type for quantity materialization")

        row_index = _extract_detail_row_index(artifact.source_locator)
        if row_index is None:
            raise ValueError("detail_row index is required in source_locator")

        rows = detail.get("parsed_supply_rows")
        if not isinstance(rows, list):
            raise ValueError("parsed_supply_rows must be a list")
        if row_index < 0 or row_index >= len(rows):
            raise ValueError("detail_row index is outside parsed_supply_rows bounds")

        row = rows[row_index]
        if not isinstance(row, dict):
            raise ValueError("detail_row payload must be an object")

        row_excerpt = _optional_text(row.get("raw_visible_text") or row.get("description"))
        if row_excerpt is None:
            raise ValueError("detail_row must include raw_visible_text or description")

        if not _evidence_overlaps_parent_scope(
            parent_excerpt=artifact.scope_detail_excerpt,
            child_excerpt=row_excerpt,
        ):
            raise ValueError("detail_row evidence is not grounded in parent scope detail excerpt")

        terminal = _extract_terminal_quantity(row_excerpt)
        if terminal is None:
            return ()

        quantity_token, unit_token = terminal

        quantity_value: Decimal
        try:
            quantity_value = Decimal(quantity_token)
        except InvalidOperation:
            return ()

        unit_raw = unit_token.strip()
        measure_kind = _unit_to_measure_kind(unit_raw)
        if measure_kind is None:
            return ()

        if not _contains_normalized(haystack=row_excerpt, needle=quantity_token):
            raise ValueError("quantity value is not grounded in source_excerpt")
        if not _contains_normalized(haystack=row_excerpt, needle=unit_raw):
            raise ValueError("unit value is not grounded in source_excerpt")

        source_contract_version = artifact.source_contract_version or _optional_text(detail.get("prompt_version"))
        review_required = bool(artifact.scope_detail_review_required or bool(row.get("review_required")))

        return (
            ScopeQuantityCandidate(
                tender_id=artifact.tender_id,
                scope_detail_id=artifact.scope_detail_id,
                source_document_id=artifact.source_document_id,
                document_page_id=artifact.document_page_id,
                quantity_raw=quantity_token,
                quantity_value=quantity_value,
                quantity_min=None,
                quantity_max=None,
                unit_raw=unit_raw,
                measure_kind=measure_kind,
                relation=SCOPE_QUANTITY_RELATION_EXACT,
                source_method=artifact.source_method,
                source_artifact_key=artifact.source_artifact_key,
                source_locator=artifact.source_locator,
                source_excerpt=row_excerpt,
                review_required=review_required,
                confidence=None,
                source_contract_version=source_contract_version,
                source_analysis_id=artifact.source_analysis_id,
                source_page_result_id=artifact.source_page_result_id,
            ),
        )


def run_scope_quantity_adapter(
    db: Session,
    artifact: ScopeQuantityEvidenceArtifact,
    *,
    adapters: Sequence[ScopeQuantityAdapter],
) -> ScopeQuantityAdapterExtractResult:
    selected: ScopeQuantityAdapter | None = None
    for adapter in adapters:
        if adapter.supports(artifact):
            selected = adapter
            break

    if selected is None:
        return ScopeQuantityAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=None,
            adapter_version=None,
            status=SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED,
            candidates=(),
        )

    try:
        candidates = tuple(selected.extract_candidates(db, artifact))
    except Exception as exc:
        return ScopeQuantityAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected.adapter_name,
            adapter_version=selected.adapter_version,
            status=SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE,
            candidates=(),
            errors=(str(exc),),
        )

    if not candidates:
        return ScopeQuantityAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected.adapter_name,
            adapter_version=selected.adapter_version,
            status=SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES,
            candidates=(),
        )

    review_required_count = sum(1 for candidate in candidates if candidate.review_required)
    status = (
        SCOPE_QUANTITY_ADAPTER_STATUS_REVIEW_REQUIRED
        if review_required_count > 0
        else SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED
    )

    return ScopeQuantityAdapterExtractResult(
        source_artifact_key=artifact.source_artifact_key,
        adapter_name=selected.adapter_name,
        adapter_version=selected.adapter_version,
        status=status,
        candidates=candidates,
    )


def default_scope_quantity_adapters() -> tuple[ScopeQuantityAdapter, ...]:
    return (VisionDetailTranscriptionScopeQuantityAdapter(),)


def _extract_detail_row_index(source_locator: str | None) -> int | None:
    locator = _optional_text(source_locator)
    if locator is None:
        return None
    for token in locator.split("|"):
        candidate = token.strip()
        if not candidate.startswith("detail_row:"):
            continue
        raw_value = candidate.split(":", 1)[1].strip()
        if raw_value.isdigit():
            return int(raw_value)
        return None
    return None


def _extract_terminal_quantity(text: str) -> tuple[str, str] | None:
    normalized = " ".join(text.split())
    match = _TERMINAL_QUANTITY_PATTERN.search(normalized)
    if match is None:
        return None

    quantity_token = match.group(1).strip()
    unit_token = match.group(2).strip()

    if not quantity_token or not unit_token:
        return None

    return quantity_token, unit_token


def _unit_to_measure_kind(unit_raw: str) -> str | None:
    normalized = _normalize_unit(unit_raw)
    if not normalized:
        return None
    return _UNIT_TO_MEASURE_KIND.get(normalized)


def _normalize_unit(value: str) -> str:
    return _normalize_text(value).replace(".", "")


def _evidence_overlaps_parent_scope(*, parent_excerpt: str, child_excerpt: str) -> bool:
    normalized_parent = _normalize_text(parent_excerpt)
    normalized_child = _normalize_text(child_excerpt)
    return normalized_child in normalized_parent or normalized_parent in normalized_child


def _contains_normalized(*, haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
