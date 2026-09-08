from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    PageOcrResult,
    TenderScopeDetail,
)
from app.scope_quantities import (
    replace_scope_quantities_for_artifact,
    validate_scope_quantity_candidate,
)
from app.scope_quantity_adapters import (
    SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE,
    SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED,
    SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_ADAPTER_STATUS_REVIEW_REQUIRED,
    SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED,
    ScopeQuantityAdapter,
    ScopeQuantityEvidenceArtifact,
    default_scope_quantity_adapters,
    run_scope_quantity_adapter,
)

SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED = "MATERIALIZED"
SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES = "NO_QUANTITIES"
SCOPE_QUANTITY_MATERIALIZATION_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_QUANTITY_MATERIALIZATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE = "INVALID_EVIDENCE"


@dataclass(frozen=True, slots=True)
class ScopeQuantityMaterializationResult:
    scope_detail_id: str
    source_artifact_key: str | None
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int
    errors: tuple[str, ...] = ()


def materialize_scope_quantities_for_scope_detail(
    db: Session,
    *,
    scope_detail_id: str,
    adapters: Sequence[ScopeQuantityAdapter] | None = None,
) -> ScopeQuantityMaterializationResult:
    scope_detail = db.get(TenderScopeDetail, scope_detail_id)
    if scope_detail is None:
        return ScopeQuantityMaterializationResult(
            scope_detail_id=scope_detail_id,
            source_artifact_key=None,
            adapter_name=None,
            adapter_version=None,
            status=SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            errors=("scope_detail_id does not exist",),
        )

    source_artifact_key = scope_detail.source_artifact_key
    try:
        artifact = _resolve_scope_quantity_evidence_artifact(db, scope_detail=scope_detail)
    except ValueError as exc:
        return ScopeQuantityMaterializationResult(
            scope_detail_id=scope_detail.id,
            source_artifact_key=source_artifact_key,
            adapter_name=None,
            adapter_version=None,
            status=SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            errors=(str(exc),),
        )

    extraction = run_scope_quantity_adapter(
        db,
        artifact,
        adapters=tuple(adapters or default_scope_quantity_adapters()),
    )

    if extraction.status == SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED:
        return ScopeQuantityMaterializationResult(
            scope_detail_id=scope_detail.id,
            source_artifact_key=source_artifact_key,
            adapter_name=extraction.adapter_name,
            adapter_version=extraction.adapter_version,
            status=SCOPE_QUANTITY_MATERIALIZATION_STATUS_UNSUPPORTED,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            errors=extraction.errors,
        )

    if extraction.status == SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE:
        return ScopeQuantityMaterializationResult(
            scope_detail_id=scope_detail.id,
            source_artifact_key=source_artifact_key,
            adapter_name=extraction.adapter_name,
            adapter_version=extraction.adapter_version,
            status=SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            errors=extraction.errors,
        )

    candidates = tuple(extraction.candidates)
    for candidate in candidates:
        validate_scope_quantity_candidate(candidate)

    nested_tx = db.begin_nested()
    try:
        persisted = replace_scope_quantities_for_artifact(
            db,
            tender_id=scope_detail.tender_id,
            scope_detail_id=scope_detail.id,
            source_document_id=scope_detail.source_document_id,
            document_page_id=scope_detail.document_page_id,
            source_artifact_key=scope_detail.source_artifact_key,
            candidates=candidates,
        )
        nested_tx.commit()
    except Exception as exc:
        nested_tx.rollback()
        return ScopeQuantityMaterializationResult(
            scope_detail_id=scope_detail.id,
            source_artifact_key=source_artifact_key,
            adapter_name=extraction.adapter_name,
            adapter_version=extraction.adapter_version,
            status=SCOPE_QUANTITY_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=len(candidates),
            persisted_count=0,
            review_required_count=0,
            errors=(str(exc),),
        )

    review_required_count = sum(1 for row in persisted if row.review_required)

    if extraction.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES:
        status = SCOPE_QUANTITY_MATERIALIZATION_STATUS_NO_QUANTITIES
    elif review_required_count > 0 or extraction.status == SCOPE_QUANTITY_ADAPTER_STATUS_REVIEW_REQUIRED:
        status = SCOPE_QUANTITY_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    else:
        status = SCOPE_QUANTITY_MATERIALIZATION_STATUS_MATERIALIZED

    return ScopeQuantityMaterializationResult(
        scope_detail_id=scope_detail.id,
        source_artifact_key=source_artifact_key,
        adapter_name=extraction.adapter_name,
        adapter_version=extraction.adapter_version,
        status=status,
        candidate_count=len(candidates),
        persisted_count=len(persisted),
        review_required_count=review_required_count,
        errors=extraction.errors,
    )


def _resolve_scope_quantity_evidence_artifact(
    db: Session,
    *,
    scope_detail: TenderScopeDetail,
) -> ScopeQuantityEvidenceArtifact:
    source_method = str(scope_detail.source_method or "").strip().upper()
    artifact_key = str(scope_detail.source_artifact_key or "").strip()
    if not source_method:
        raise ValueError("scope_detail.source_method is required")
    if not artifact_key:
        raise ValueError("scope_detail.source_artifact_key is required")

    page = db.get(DocumentPage, scope_detail.document_page_id)
    if page is None:
        raise ValueError("scope_detail document_page_id does not exist")
    if page.document_id != scope_detail.source_document_id:
        raise ValueError("scope_detail page does not belong to source_document_id")

    payload: dict | None
    source_analysis_id = scope_detail.source_analysis_id
    source_page_result_id = scope_detail.source_page_result_id

    if source_method == "VISION":
        page_result_id = _parse_prefixed_id(artifact_key, prefixes=("vision-page-result:", "DocumentVisionPageResult:"))
        if page_result_id is None:
            raise ValueError("Unsupported VISION source_artifact_key format")

        page_result = db.get(DocumentVisionPageResult, page_result_id)
        if page_result is None:
            raise ValueError("source artifact page result does not exist")
        if page_result.document_page_id != scope_detail.document_page_id:
            raise ValueError("source artifact page result is outside scope detail page")

        analysis = db.get(DocumentVisionAnalysis, page_result.analysis_id)
        if analysis is None:
            raise ValueError("source analysis for page result does not exist")
        if analysis.tender_id != scope_detail.tender_id:
            raise ValueError("source analysis belongs to another tender")
        if analysis.document_id != scope_detail.source_document_id:
            raise ValueError("source analysis belongs to another document")

        if source_page_result_id is not None and source_page_result_id != page_result.id:
            raise ValueError("scope detail source_page_result_id does not match source_artifact_key")
        if source_analysis_id is not None and source_analysis_id != analysis.id:
            raise ValueError("scope detail source_analysis_id does not match source artifact lineage")

        source_analysis_id = analysis.id
        source_page_result_id = page_result.id
        payload = page_result.structured_json if isinstance(page_result.structured_json, dict) else None

    elif source_method == "OCR":
        ocr_id = _parse_prefixed_id(artifact_key, prefixes=("ocr-result:", "PageOcrResult:"))
        if ocr_id is None:
            raise ValueError("Unsupported OCR source_artifact_key format")

        ocr_row = db.get(PageOcrResult, ocr_id)
        if ocr_row is None:
            raise ValueError("source artifact OCR result does not exist")
        if ocr_row.document_page_id != scope_detail.document_page_id:
            raise ValueError("source artifact OCR result is outside scope detail page")

        payload = {
            "text": ocr_row.text,
            "engine": ocr_row.engine,
            "engine_version": ocr_row.engine_version,
            "scope": ocr_row.scope,
            "region_id": ocr_row.region_id,
        }
        source_analysis_id = None
        source_page_result_id = None

    elif source_method == "NATIVE":
        page_id = _parse_prefixed_id(artifact_key, prefixes=("native-page:", "DocumentPage:"))
        if page_id is None:
            raise ValueError("Unsupported NATIVE source_artifact_key format")
        if page_id != page.id:
            raise ValueError("source artifact page is outside scope detail page")

        payload = {
            "text": page.text,
            "source_type": page.extraction_method,
            "source_scope": "NATIVE_PAGE",
        }
        source_analysis_id = None
        source_page_result_id = None

    else:
        raise ValueError(f"Unsupported source_method: {scope_detail.source_method}")

    return ScopeQuantityEvidenceArtifact(
        tender_id=scope_detail.tender_id,
        scope_detail_id=scope_detail.id,
        source_document_id=scope_detail.source_document_id,
        document_page_id=scope_detail.document_page_id,
        page_number=page.page_number,
        source_method=source_method,
        source_artifact_key=artifact_key,
        source_locator=scope_detail.source_locator,
        scope_detail_excerpt=scope_detail.source_excerpt,
        source_contract_version=scope_detail.source_contract_version,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
        payload=payload,
        scope_detail_review_required=bool(scope_detail.review_required),
    )


def _parse_prefixed_id(value: str, *, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if value.startswith(prefix):
            candidate = value[len(prefix):].strip()
            return candidate or None
    return None
