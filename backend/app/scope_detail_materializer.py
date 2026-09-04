from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, NormalizedContent, PageOcrResult
from app.scope_details import replace_scope_details_for_artifact
from app.scope_detail_adapters import (
    SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED,
    SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS,
    SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED,
    SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
    ScopeDetailAdapter,
    ScopeDetailAdapterRunResult,
    ScopeDetailEvidenceArtifact,
    adapt_and_persist_scope_detail_artifact,
)

EXECUTION_POLICY_AVAILABLE_ONLY = "AVAILABLE_ONLY"

SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED = "MATERIALIZED"
SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL = "PARTIAL"
SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_DETAILS = "NO_DETAILS"
SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE = "NO_EVIDENCE"
SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED = "DESELECTED"

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"


@dataclass(frozen=True, slots=True)
class ScopeDetailMaterializationArtifactResult:
    source_artifact_key: str
    source_method: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int


@dataclass(frozen=True, slots=True)
class ScopeDetailMaterializationResult:
    tender_id: str
    document_id: str
    execution_policy: str
    pages_seen: int
    artifacts_seen: int
    artifacts_supported: int
    artifacts_materialized: int
    artifacts_no_details: int
    artifacts_unsupported: int
    artifacts_review_required: int
    candidate_count: int
    persisted_count: int
    review_required_count: int
    status: str
    artifact_results: tuple[ScopeDetailMaterializationArtifactResult, ...]


@dataclass(frozen=True, slots=True)
class _EnumeratedArtifact:
    page_number: int
    sort_key: str
    artifact: ScopeDetailEvidenceArtifact
    analysis_created_at: datetime | None = None
    page_result_created_at: datetime | None = None
    page_result_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class _EnumeratedArtifacts:
    active: tuple[_EnumeratedArtifact, ...]
    deselected: tuple[_EnumeratedArtifact, ...]


def materialize_document_scope_details(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    execution_policy: str = EXECUTION_POLICY_AVAILABLE_ONLY,
    adapters: Sequence[ScopeDetailAdapter] | None = None,
) -> ScopeDetailMaterializationResult:
    if execution_policy != EXECUTION_POLICY_AVAILABLE_ONLY:
        raise ValueError(f"Unsupported execution policy: {execution_policy}")

    pages = db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc(), DocumentPage.id.asc())
    ).scalars().all()

    enumerated = _enumerate_persisted_artifacts_for_document(
        db,
        tender_id=tender_id,
        document_id=document_id,
        pages=pages,
    )

    artifact_results: list[ScopeDetailMaterializationArtifactResult] = []
    artifacts_supported = 0
    artifacts_materialized = 0
    artifacts_no_details = 0
    artifacts_unsupported = 0
    artifacts_review_required = 0
    candidate_count = 0
    persisted_count = 0
    review_required_count = 0

    for deselected in enumerated.deselected:
        nested_tx = db.begin_nested()
        try:
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=deselected.artifact.document_page_id,
                source_artifact_key=deselected.artifact.source_artifact_key,
                candidates=(),
            )
            nested_tx.commit()
            artifact_results.append(
                ScopeDetailMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    adapter_name=None,
                    adapter_version=None,
                    status=SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                )
            )
        except Exception:
            nested_tx.rollback()
            artifact_results.append(
                ScopeDetailMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    adapter_name=None,
                    adapter_version=None,
                    status=SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                )
            )

    for enumerated_artifact in enumerated.active:
        nested_tx = db.begin_nested()
        try:
            adapter_result = adapt_and_persist_scope_detail_artifact(
                db,
                enumerated_artifact.artifact,
                adapters=adapters,
            )
            nested_tx.commit()
        except Exception:
            nested_tx.rollback()
            adapter_result = ScopeDetailAdapterRunResult(
                source_artifact_key=enumerated_artifact.artifact.source_artifact_key,
                adapter_name=None,
                adapter_version=None,
                status=SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
                candidate_count=0,
                persisted_count=0,
                review_required_count=0,
            )

        artifact_results.append(
            ScopeDetailMaterializationArtifactResult(
                source_artifact_key=adapter_result.source_artifact_key,
                source_method=enumerated_artifact.artifact.source_method,
                adapter_name=adapter_result.adapter_name,
                adapter_version=adapter_result.adapter_version,
                status=adapter_result.status,
                candidate_count=adapter_result.candidate_count,
                persisted_count=adapter_result.persisted_count,
                review_required_count=adapter_result.review_required_count,
            )
        )

        candidate_count += adapter_result.candidate_count
        persisted_count += adapter_result.persisted_count
        review_required_count += adapter_result.review_required_count

        if adapter_result.status == SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED:
            artifacts_unsupported += 1
            continue

        artifacts_supported += 1
        if adapter_result.status == SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS:
            artifacts_no_details += 1
        if adapter_result.persisted_count > 0:
            artifacts_materialized += 1
        if adapter_result.review_required_count > 0:
            artifacts_review_required += 1

    status = _summarize_materialization_status(
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_details=artifacts_no_details,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        persisted_count=persisted_count,
    )

    return ScopeDetailMaterializationResult(
        tender_id=tender_id,
        document_id=document_id,
        execution_policy=execution_policy,
        pages_seen=len(pages),
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_details=artifacts_no_details,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        candidate_count=candidate_count,
        persisted_count=persisted_count,
        review_required_count=review_required_count,
        status=status,
        artifact_results=tuple(artifact_results),
    )


def _enumerate_persisted_artifacts_for_document(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    pages: Sequence[DocumentPage],
) -> _EnumeratedArtifacts:
    page_by_id = {page.id: page for page in pages}
    active: list[_EnumeratedArtifact] = []
    deselected: list[_EnumeratedArtifact] = []

    vision_lineage_groups: dict[tuple[str, str, str], list[_EnumeratedArtifact]] = {}
    additive_vision: list[_EnumeratedArtifact] = []

    vision_rows = db.execute(
        select(DocumentVisionPageResult, DocumentVisionAnalysis)
        .join(DocumentVisionAnalysis, DocumentVisionAnalysis.id == DocumentVisionPageResult.analysis_id)
        .where(
            DocumentVisionAnalysis.tender_id == tender_id,
            DocumentVisionAnalysis.document_id == document_id,
        )
        .order_by(DocumentVisionPageResult.page_number.asc(), DocumentVisionPageResult.id.asc())
    ).all()
    for page_result, analysis in vision_rows:
        payload = _build_vision_payload(page_result)
        if payload is None:
            continue
        detail_transcription = payload.get("detail_transcription")
        detail_prompt_version = None
        if isinstance(detail_transcription, dict):
            detail_prompt_version = _optional_text(detail_transcription.get("prompt_version"))
        enumerated_artifact = _EnumeratedArtifact(
            page_number=page_result.page_number,
            sort_key=f"vision:{page_result.page_number:04d}:{page_result.id}",
            artifact=ScopeDetailEvidenceArtifact(
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=page_result.document_page_id,
                source_method="VISION",
                source_artifact_key=f"vision-page-result:{page_result.id}",
                source_contract_version=detail_prompt_version or _optional_text(analysis.prompt_version),
                source_locator=f"page:{page_result.page_number}",
                source_analysis_id=analysis.id,
                source_page_result_id=page_result.id,
                payload=payload,
            ),
            analysis_created_at=analysis.created_at,
            page_result_created_at=page_result.created_at,
            page_result_updated_at=page_result.updated_at,
        )

        lineage_key = _vision_detail_lineage_key(page_result=page_result, payload=payload)
        if lineage_key is None:
            additive_vision.append(enumerated_artifact)
            continue
        vision_lineage_groups.setdefault(lineage_key, []).append(enumerated_artifact)

    active.extend(additive_vision)
    for grouped in vision_lineage_groups.values():
        if len(grouped) == 1:
            active.append(grouped[0])
            continue

        selected = max(grouped, key=_vision_artifact_lifecycle_sort_key)
        active.append(selected)
        for candidate in grouped:
            if candidate is selected:
                continue
            deselected.append(candidate)

    for ocr_row in db.execute(
        select(PageOcrResult)
        .join(DocumentPage, DocumentPage.id == PageOcrResult.document_page_id)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc(), PageOcrResult.created_at.asc(), PageOcrResult.id.asc())
    ).scalars().all():
        page = page_by_id.get(ocr_row.document_page_id)
        if page is None:
            continue
        active.append(
            _EnumeratedArtifact(
                page_number=page.page_number,
                sort_key=f"ocr:{page.page_number:04d}:{ocr_row.id}",
                artifact=ScopeDetailEvidenceArtifact(
                    tender_id=tender_id,
                    source_document_id=document_id,
                    document_page_id=ocr_row.document_page_id,
                    source_method="OCR",
                    source_artifact_key=f"ocr-result:{ocr_row.id}",
                    source_contract_version=_optional_text(ocr_row.engine_version),
                    source_locator=_ocr_source_locator(page.page_number, ocr_row.scope, ocr_row.region_id),
                    payload={
                        "text": ocr_row.text,
                        "engine": ocr_row.engine,
                        "engine_version": ocr_row.engine_version,
                        "scope": ocr_row.scope,
                        "region_id": ocr_row.region_id,
                    },
                ),
            )
        )

    native_rows = db.execute(
        select(NormalizedContent, DocumentPage)
        .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
        .where(
            DocumentPage.document_id == document_id,
            NormalizedContent.source_type.in_(["NATIVE_PDF", "NATIVE_TEXT"]),
        )
        .order_by(DocumentPage.page_number.asc(), NormalizedContent.created_at.asc(), NormalizedContent.id.asc())
    ).all()
    seen_native_page_ids: set[str] = set()
    for normalized_content, page in native_rows:
        if page.id in seen_native_page_ids:
            continue
        text = _optional_text(normalized_content.normalized_text) or _optional_text(page.text)
        if text is None:
            continue
        seen_native_page_ids.add(page.id)
        active.append(
            _EnumeratedArtifact(
                page_number=page.page_number,
                sort_key=f"native:{page.page_number:04d}:{page.id}",
                artifact=ScopeDetailEvidenceArtifact(
                    tender_id=tender_id,
                    source_document_id=document_id,
                    document_page_id=page.id,
                    source_method="NATIVE",
                    source_artifact_key=f"native-page:{page.id}",
                    source_contract_version="NATIVE_TEXT_V1",
                    source_locator=f"page:{page.page_number}",
                    payload={
                        "text": text,
                        "normalized_content_id": normalized_content.id,
                        "source_type": normalized_content.source_type,
                        "source_scope": normalized_content.source_scope,
                    },
                ),
            )
        )

    active.sort(key=lambda item: (item.page_number, item.sort_key))
    deselected.sort(key=lambda item: (item.page_number, item.sort_key))
    return _EnumeratedArtifacts(active=tuple(active), deselected=tuple(deselected))


def _vision_detail_lineage_key(
    *,
    page_result: DocumentVisionPageResult,
    payload: dict,
) -> tuple[str, str, str] | None:
    detail = payload.get("detail_transcription")
    if not isinstance(detail, dict):
        return None

    task_type = str(detail.get("task_type") or "").strip().upper()
    if task_type != VISION_DETAIL_TASK_TYPE:
        return None

    task_fingerprint = _optional_text(detail.get("task_fingerprint"))
    if task_fingerprint is None:
        return None

    return (page_result.document_page_id, task_type, task_fingerprint)


def _vision_artifact_lifecycle_sort_key(enumerated: _EnumeratedArtifact) -> tuple:
    return (
        _datetime_or_min(enumerated.analysis_created_at),
        _datetime_or_min(enumerated.page_result_updated_at),
        _datetime_or_min(enumerated.page_result_created_at),
        enumerated.artifact.source_artifact_key,
    )


def _datetime_or_min(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value


def _build_vision_payload(page_result: DocumentVisionPageResult) -> dict | None:
    if isinstance(page_result.structured_json, dict):
        return page_result.structured_json
    if page_result.raw_response_text or page_result.extracted_markdown or page_result.extracted_plain_text:
        return {
            "raw_response_text": page_result.raw_response_text,
            "extracted_markdown": page_result.extracted_markdown,
            "extracted_plain_text": page_result.extracted_plain_text,
            "source_page": page_result.page_number,
        }
    return None


def _ocr_source_locator(page_number: int, scope: str, region_id: str | None) -> str:
    locator = f"page:{page_number}|ocr_scope:{scope}"
    if region_id is not None:
        locator = f"{locator}|region:{region_id}"
    return locator


def _summarize_materialization_status(
    *,
    artifacts_seen: int,
    artifacts_supported: int,
    artifacts_materialized: int,
    artifacts_no_details: int,
    artifacts_unsupported: int,
    artifacts_review_required: int,
    persisted_count: int,
) -> str:
    if artifacts_seen == 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_supported == 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_materialized == 0:
        if artifacts_no_details > 0:
            return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_DETAILS
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_review_required > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    if artifacts_unsupported > 0 or artifacts_no_details > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL
    if persisted_count > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED
    return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE


def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
