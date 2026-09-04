from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.item_identity import normalize_item_identity
from app.models import TenderScopeSegment
from app.scope_detail_adapters import ScopeDetailEvidenceArtifact
from app.scope_details import (
    SCOPE_DETAIL_APPLICABILITY_ITEM,
    SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
    SCOPE_DETAIL_DOMAIN_DELIVERABLE,
    SCOPE_DETAIL_DOMAIN_OTHER,
    SCOPE_DETAIL_DOMAIN_SUPPLY,
    ScopeDetailCandidate,
)

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"
VISION_SCOPE_DETAIL_ADAPTER_VERSION = "vision-scope-detail-adapter-001"


@dataclass(frozen=True, slots=True)
class _OwnershipResolution:
    scope_segment_id: str | None
    tender_item_id: str | None
    candidate_item_key: str | None


class VisionScopeDetailAdapter:
    adapter_name = "VisionScopeDetailAdapter"
    adapter_version = VISION_SCOPE_DETAIL_ADAPTER_VERSION

    def supports(self, artifact: ScopeDetailEvidenceArtifact) -> bool:
        if artifact.source_method != "VISION":
            return False
        payload = artifact.payload if isinstance(artifact.payload, dict) else None
        if payload is None:
            return False
        detail = payload.get("detail_transcription")
        return isinstance(detail, dict)

    def extract_candidates(self, db: Session, artifact: ScopeDetailEvidenceArtifact) -> Sequence[ScopeDetailCandidate]:
        payload = artifact.payload if isinstance(artifact.payload, dict) else None
        if payload is None:
            return []

        detail = payload.get("detail_transcription")
        if not isinstance(detail, dict):
            return []

        task_type = str(detail.get("task_type") or "").upper()
        if task_type and task_type != VISION_DETAIL_TASK_TYPE:
            return []

        source_contract_version = artifact.source_contract_version or _optional_text(detail.get("prompt_version"))

        ownership_context = _load_ownership_context(db, artifact)

        rows = detail.get("parsed_supply_rows")
        if not isinstance(rows, list):
            rows = []

        candidates: list[ScopeDetailCandidate] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            source_excerpt = _extract_source_excerpt(row)
            if source_excerpt is None:
                continue

            description = _extract_description(row) or source_excerpt
            domain = _resolve_domain(row, description)
            if domain is None:
                continue

            owner = _resolve_ownership(ownership_context, row)
            applicability = SCOPE_DETAIL_APPLICABILITY_ITEM
            review_required = bool(row.get("review_required"))

            if owner.scope_segment_id is None and owner.tender_item_id is None and owner.candidate_item_key is None:
                applicability = SCOPE_DETAIL_APPLICABILITY_UNRESOLVED
                review_required = True

            source_locator = _resolve_source_locator(
                artifact=artifact,
                detail_meta=detail,
                row=row,
                row_index=row_index,
            )

            candidates.append(
                ScopeDetailCandidate(
                    tender_id=artifact.tender_id,
                    source_document_id=artifact.source_document_id,
                    document_page_id=artifact.document_page_id,
                    domain=domain,
                    detail_type="DETAIL",
                    description=description,
                    normalized_label=None,
                    applicability=applicability,
                    source_method="VISION",
                    source_artifact_key=artifact.source_artifact_key,
                    source_contract_version=source_contract_version,
                    source_locator=source_locator,
                    source_excerpt=source_excerpt,
                    confidence=None,
                    review_required=review_required,
                    scope_segment_id=owner.scope_segment_id,
                    tender_item_id=owner.tender_item_id,
                    candidate_item_key=owner.candidate_item_key,
                    source_analysis_id=artifact.source_analysis_id,
                    source_page_result_id=artifact.source_page_result_id,
                    quantity_raw=_optional_text(row.get("quantity")),
                    unit_raw=_optional_text(row.get("unit")),
                )
            )

        return candidates


@dataclass(frozen=True, slots=True)
class _OwnershipContext:
    by_segment_id: dict[str, TenderScopeSegment]
    by_tender_item_id: dict[str, TenderScopeSegment]
    by_candidate_key: dict[str, TenderScopeSegment]


def _load_ownership_context(db: Session, artifact: ScopeDetailEvidenceArtifact) -> _OwnershipContext:
    rows = db.execute(
        select(TenderScopeSegment)
        .where(
            TenderScopeSegment.tender_id == artifact.tender_id,
            TenderScopeSegment.source_document_id == artifact.source_document_id,
            TenderScopeSegment.document_page_id == artifact.document_page_id,
        )
        .order_by(TenderScopeSegment.sequence_index.asc())
    ).scalars().all()

    if artifact.source_page_result_id is not None:
        exact = [row for row in rows if row.source_page_result_id == artifact.source_page_result_id]
        if exact:
            rows = exact

    by_segment_id: dict[str, TenderScopeSegment] = {}
    by_tender_item_id: dict[str, TenderScopeSegment] = {}
    by_candidate_key: dict[str, TenderScopeSegment] = {}
    for row in rows:
        by_segment_id[row.id] = row
        if row.tender_item_id and row.tender_item_id not in by_tender_item_id:
            by_tender_item_id[row.tender_item_id] = row
        normalized = normalize_item_identity((row.candidate_item_key or "").strip())
        if normalized.normalized_key and normalized.normalized_key not in by_candidate_key:
            by_candidate_key[normalized.normalized_key] = row

    return _OwnershipContext(
        by_segment_id=by_segment_id,
        by_tender_item_id=by_tender_item_id,
        by_candidate_key=by_candidate_key,
    )


def _extract_source_excerpt(row: dict[str, Any]) -> str | None:
    for key in ("raw_visible_text", "description"):
        value = _optional_text(row.get(key))
        if value:
            return value
    return None


def _extract_description(row: dict[str, Any]) -> str | None:
    return _optional_text(row.get("description"))


def _resolve_domain(row: dict[str, Any], description: str) -> str | None:
    explicit_domain = _optional_text(row.get("scope_domain") or row.get("detail_domain") or row.get("domain") or row.get("scope_type"))
    if explicit_domain:
        normalized_explicit = explicit_domain.upper().replace("-", "_").replace(" ", "_")
        if normalized_explicit in {SCOPE_DETAIL_DOMAIN_SUPPLY, SCOPE_DETAIL_DOMAIN_DELIVERABLE}:
            return normalized_explicit

    if _has_supply_signals(row):
        return SCOPE_DETAIL_DOMAIN_SUPPLY

    if _has_deliverable_signals(description):
        return SCOPE_DETAIL_DOMAIN_DELIVERABLE

    if bool(row.get("review_required")):
        return SCOPE_DETAIL_DOMAIN_OTHER

    return None


def _has_supply_signals(row: dict[str, Any]) -> bool:
    return any(
        _optional_text(row.get(key))
        for key in ("brand", "model", "quantity", "unit")
    )


def _has_deliverable_signals(text: str) -> bool:
    normalized = text.upper()
    markers = (
        "ENTREGA",
        "ENTREGABLE",
        "ENTREGAR",
        "REPORTE",
        "INFORME",
        "BITACORA",
        "ACTA",
        "DOCUMENTO",
    )
    return any(marker in normalized for marker in markers)


def _resolve_ownership(context: _OwnershipContext, row: dict[str, Any]) -> _OwnershipResolution:
    explicit_segment_id = _optional_text(row.get("scope_segment_id"))
    if explicit_segment_id and explicit_segment_id in context.by_segment_id:
        segment = context.by_segment_id[explicit_segment_id]
        return _OwnershipResolution(
            scope_segment_id=segment.id,
            tender_item_id=segment.tender_item_id,
            candidate_item_key=segment.candidate_item_key,
        )

    explicit_tender_item_id = _optional_text(row.get("tender_item_id"))
    if explicit_tender_item_id and explicit_tender_item_id in context.by_tender_item_id:
        segment = context.by_tender_item_id[explicit_tender_item_id]
        return _OwnershipResolution(
            scope_segment_id=segment.id,
            tender_item_id=segment.tender_item_id,
            candidate_item_key=segment.candidate_item_key,
        )

    raw_candidate_key = _optional_text(
        row.get("candidate_item_key")
        or row.get("item_number")
        or row.get("partida")
        or row.get("partida_numero")
    )
    normalized_candidate_key = None
    if raw_candidate_key:
        normalized = normalize_item_identity(raw_candidate_key)
        normalized_candidate_key = normalized.normalized_key

    if normalized_candidate_key and normalized_candidate_key in context.by_candidate_key:
        segment = context.by_candidate_key[normalized_candidate_key]
        return _OwnershipResolution(
            scope_segment_id=segment.id,
            tender_item_id=segment.tender_item_id,
            candidate_item_key=segment.candidate_item_key,
        )

    return _OwnershipResolution(
        scope_segment_id=None,
        tender_item_id=None,
        candidate_item_key=None,
    )


def _resolve_source_locator(
    *,
    artifact: ScopeDetailEvidenceArtifact,
    detail_meta: dict[str, Any],
    row: dict[str, Any],
    row_index: int,
) -> str:
    explicit = _optional_text(row.get("source_locator"))
    if explicit:
        return explicit

    page_value = _optional_text(row.get("source_page"))
    if page_value is None:
        page_value = _optional_text(detail_meta.get("source_page"))

    if page_value:
        return f"page:{page_value}|detail_row:{row_index}"

    if artifact.source_locator:
        return f"{artifact.source_locator}|detail_row:{row_index}"

    return f"detail_row:{row_index}"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
