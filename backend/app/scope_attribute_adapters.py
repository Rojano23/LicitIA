from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from sqlalchemy.orm import Session

from app.scope_attributes import (
    SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
    ScopeAttributeCandidate,
)

SCOPE_ATTRIBUTE_ADAPTER_STATUS_MATERIALIZED = "MATERIALIZED"
SCOPE_ATTRIBUTE_ADAPTER_STATUS_NO_ATTRIBUTES = "NO_ATTRIBUTES"
SCOPE_ATTRIBUTE_ADAPTER_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_ATTRIBUTE_ADAPTER_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_ATTRIBUTE_ADAPTER_STATUS_INVALID_EVIDENCE = "INVALID_EVIDENCE"

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"
VISION_SCOPE_ATTRIBUTE_ADAPTER_VERSION = "vision-scope-attribute-adapter-001"


@dataclass(frozen=True, slots=True)
class ScopeAttributeEvidenceArtifact:
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
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
class ScopeAttributeAdapterExtractResult:
    source_artifact_key: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidates: tuple[ScopeAttributeCandidate, ...]
    errors: tuple[str, ...] = ()


class ScopeAttributeAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def supports(self, artifact: ScopeAttributeEvidenceArtifact) -> bool:
        ...

    def extract_candidates(self, db: Session, artifact: ScopeAttributeEvidenceArtifact) -> Sequence[ScopeAttributeCandidate]:
        ...


class VisionDetailTranscriptionScopeAttributeAdapter:
    adapter_name = "VisionDetailTranscriptionScopeAttributeAdapter"
    adapter_version = VISION_SCOPE_ATTRIBUTE_ADAPTER_VERSION

    def supports(self, artifact: ScopeAttributeEvidenceArtifact) -> bool:
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

    def extract_candidates(self, db: Session, artifact: ScopeAttributeEvidenceArtifact) -> Sequence[ScopeAttributeCandidate]:
        del db
        payload = artifact.payload if isinstance(artifact.payload, dict) else None
        if payload is None:
            raise ValueError("artifact payload is required")

        detail = payload.get("detail_transcription")
        if not isinstance(detail, dict):
            raise ValueError("detail_transcription payload is required")

        task_type = _optional_text(detail.get("task_type"))
        if task_type is None or task_type.upper() != VISION_DETAIL_TASK_TYPE:
            raise ValueError("Unsupported vision task_type for attribute materialization")

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

        source_contract_version = artifact.source_contract_version or _optional_text(detail.get("prompt_version"))
        row_review_required = bool(row.get("review_required"))
        review_required = bool(artifact.scope_detail_review_required or row_review_required)

        candidates: list[ScopeAttributeCandidate] = []
        for payload_key, attribute_name in (("brand", "brand"), ("model", "model")):
            value_raw = _optional_text(row.get(payload_key))
            if value_raw is None:
                continue

            if not _contains_normalized(haystack=row_excerpt, needle=value_raw):
                raise ValueError(f"{attribute_name} value is not grounded in source_excerpt")

            candidates.append(
                ScopeAttributeCandidate(
                    tender_id=artifact.tender_id,
                    scope_detail_id=artifact.scope_detail_id,
                    source_document_id=artifact.source_document_id,
                    document_page_id=artifact.document_page_id,
                    source_method="VISION",
                    source_artifact_key=artifact.source_artifact_key,
                    source_locator=f"{artifact.source_locator}|attr:{attribute_name}",
                    source_excerpt=row_excerpt,
                    attribute_name=attribute_name,
                    value_raw=value_raw,
                    review_required=review_required,
                    attribute_label_raw=None,
                    normalized_name=None,
                    unit_raw=None,
                    relation=SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
                    confidence=None,
                    source_contract_version=source_contract_version,
                    source_analysis_id=artifact.source_analysis_id,
                    source_page_result_id=artifact.source_page_result_id,
                )
            )

        return candidates


def run_scope_attribute_adapter(
    db: Session,
    artifact: ScopeAttributeEvidenceArtifact,
    *,
    adapters: Sequence[ScopeAttributeAdapter],
) -> ScopeAttributeAdapterExtractResult:
    selected: ScopeAttributeAdapter | None = None
    for adapter in adapters:
        if adapter.supports(artifact):
            selected = adapter
            break

    if selected is None:
        return ScopeAttributeAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=None,
            adapter_version=None,
            status=SCOPE_ATTRIBUTE_ADAPTER_STATUS_UNSUPPORTED,
            candidates=(),
        )

    try:
        candidates = tuple(selected.extract_candidates(db, artifact))
    except Exception as exc:
        return ScopeAttributeAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected.adapter_name,
            adapter_version=selected.adapter_version,
            status=SCOPE_ATTRIBUTE_ADAPTER_STATUS_INVALID_EVIDENCE,
            candidates=(),
            errors=(str(exc),),
        )

    if not candidates:
        return ScopeAttributeAdapterExtractResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected.adapter_name,
            adapter_version=selected.adapter_version,
            status=SCOPE_ATTRIBUTE_ADAPTER_STATUS_NO_ATTRIBUTES,
            candidates=(),
        )

    review_required_count = sum(1 for candidate in candidates if candidate.review_required)
    status = (
        SCOPE_ATTRIBUTE_ADAPTER_STATUS_REVIEW_REQUIRED
        if review_required_count > 0
        else SCOPE_ATTRIBUTE_ADAPTER_STATUS_MATERIALIZED
    )

    return ScopeAttributeAdapterExtractResult(
        source_artifact_key=artifact.source_artifact_key,
        adapter_name=selected.adapter_name,
        adapter_version=selected.adapter_version,
        status=status,
        candidates=candidates,
    )


def default_scope_attribute_adapters() -> tuple[ScopeAttributeAdapter, ...]:
    return (VisionDetailTranscriptionScopeAttributeAdapter(),)


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
