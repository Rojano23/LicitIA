from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentPageRegion,
    DocumentPageStatus,
    DocumentPage,
    DocumentPageStructureResolution,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    PageOcrResult,
    TenderDocument,
    TenderItem,
)
from app.content_normalization import process_document_normalization
from app.database import SessionLocal
from app.main import AUTO_OCR_PROVIDER_ORDER, _resolve_document_file_path, get_ocr_providers
from app.ollama_vision import (
    VISION_STRUCTURE_SCOPE_COMPATIBLE_PROMPT_VERSIONS,
    VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
    VISION_TASK_STRUCTURE_SCOPE,
)
from app.ollama_vision import analyze_vision_document_structure_only_isolated
from app.page_structure import (
    PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
    PAGE_STRUCTURE_UNKNOWN,
    PAGE_STRUCTURE_VALID,
    PAGE_STRUCTURE_SOURCE_METHOD_VISION,
    PageStructuralProvenance,
    build_page_structural_state,
)
from app.page_structure_resolver import (
    OcrStructuralEvidence,
    ProviderAcquisitionState,
    StructuralCandidate,
    PageStructureResolution,
    RESOLUTION_REVIEW_REQUIRED,
    resolve_page_structure,
    structural_candidate_from_native_text,
    structural_candidate_from_ocr_evidence,
    structural_candidate_from_vision_005,
)
from app.scope_linking import CanonicalTenderItemReference
from app.scope_linking import CONTINUITY_NOTE_MISMATCH_RESET
from app.scope_segments import (
    TenderScopeSegmentInput,
    replace_tender_scope_segments_for_page_inputs,
    resolve_scope_ownership_decisions_for_page_inputs,
)

EXECUTION_POLICY_AVAILABLE_ONLY = "AVAILABLE_ONLY"
EXECUTION_POLICY_ALLOW_OCR = "ALLOW_OCR"
EXECUTION_POLICY_AUTO = "AUTO"
STRUCTURE_RESOLVER_VERSION = "mvp-06.2.5b1-available-only-v1"
DOCUMENT_CONTINUITY_CONFLICT_REASON = "DOCUMENT_CONTINUITY_CONFLICT"


@dataclass(frozen=True, slots=True)
class OcrAcquisitionRequest:
    tender_id: str
    document_id: str
    document_page_id: str
    page_number: int
    page_status: str
    content_profile: str


@dataclass(frozen=True, slots=True)
class VisionStructureAcquisitionRequest:
    tender_id: str
    document_id: str
    document_page_id: str
    page_number: int
    previous_open_item_key: str | None = None


OcrExecutor = Callable[[OcrAcquisitionRequest], None]
VisionExecutor = Callable[[VisionStructureAcquisitionRequest], None]


@dataclass(frozen=True, slots=True)
class PageStructureOrchestrationResult:
    document_page_id: str
    page_number: int
    status: str
    selected_source_method: str | None
    needs_provider: str | None
    review_required: bool
    reason: str | None
    considered_methods: tuple[str, ...]
    input_fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class DocumentStructureOrchestrationResult:
    tender_id: str
    document_id: str
    execution_policy: str
    page_results: tuple[PageStructureOrchestrationResult, ...]
    scope_segments_persisted: int


@dataclass(frozen=True, slots=True)
class _OcrNormalizedSource:
    page_ocr_result_id: str
    engine: str
    source_scope: str
    region_index: int | None
    text: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class _OcrJobPlan:
    scope: str
    region_id: str | None
    region_index: int | None
    x0: float | None
    y0: float | None
    x1: float | None
    y1: float | None


@dataclass(frozen=True, slots=True)
class _OcrExecutionPlan:
    tender_id: str
    document_id: str
    document_page_id: str
    page_number: int
    provider_id: str
    language: str
    stored_relative_path: str
    jobs: tuple[_OcrJobPlan, ...]


@dataclass(frozen=True, slots=True)
class _PageResolutionSnapshot:
    document_page_id: str
    page_number: int
    resolution: PageStructureResolution
    candidates: tuple[StructuralCandidate, ...]
    native_hash: str
    ocr_fingerprint_parts: tuple[str, ...]
    vision_fingerprint_parts: tuple[str, ...]


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sorted_native_sources(page: DocumentPage) -> list[NormalizedContent]:
    return sorted(
        [
            row
            for row in page.normalized_content
            if row.source_type == "NATIVE_PDF" and row.source_scope == "NATIVE_PAGE" and bool((row.normalized_text or "").strip())
        ],
        key=lambda row: (
            row.updated_at or datetime.min,
            row.created_at or datetime.min,
            row.id,
        ),
    )


def _materialize_native_candidate(page: DocumentPage) -> tuple[StructuralCandidate, str]:
    native_sources = _sorted_native_sources(page)
    if native_sources:
        selected = native_sources[-1]
        native_text = selected.normalized_text
        native_hash = selected.content_sha256 or _sha256(f"{page.id}|native|{native_text}")
    else:
        native_text = page.text or ""
        native_hash = _sha256(f"{page.id}|native-fallback|{native_text}")

    return (
        structural_candidate_from_native_text(
            page_number=page.page_number,
            native_text=native_text,
        ),
        native_hash,
    )


def _materialize_ocr_candidates(page: DocumentPage) -> tuple[list[StructuralCandidate], bool, tuple[str, ...]]:
    ocr_sources: list[_OcrNormalizedSource] = []

    for row in page.normalized_content:
        if row.source_type != "OCR":
            continue
        if not bool((row.normalized_text or "").strip()):
            continue
        if row.page_ocr_result is None:
            continue
        if row.page_ocr_result.status != "OCR_TEXT_EXTRACTED":
            continue

        ocr_sources.append(
            _OcrNormalizedSource(
                page_ocr_result_id=row.page_ocr_result.id,
                engine=row.page_ocr_result.engine,
                source_scope=row.source_scope,
                region_index=row.region.region_index if row.region is not None else None,
                text=row.normalized_text,
                content_sha256=row.content_sha256,
            )
        )

    if not ocr_sources:
        return [], False, ()

    sorted_sources = sorted(
        ocr_sources,
        key=lambda row: (
            row.engine,
            0 if row.source_scope == "FULL_PAGE" else 1,
            row.region_index if row.region_index is not None else -1,
            row.page_ocr_result_id,
        ),
    )

    # When there is a single persisted normalized OCR source, treat it as the effective source.
    if len(sorted_sources) == 1:
        source = sorted_sources[0]
        candidate = structural_candidate_from_ocr_evidence(
            page_number=page.page_number,
            ocr_evidence=(
                OcrStructuralEvidence(
                    text=source.text,
                    scope=source.source_scope,
                    region_index=source.region_index,
                    page_ocr_result_id=source.page_ocr_result_id,
                ),
            ),
        )
        return [candidate], True, (f"OCR:{source.engine}:{source.page_ocr_result_id}:{source.content_sha256}",)

    per_engine: dict[str, list[_OcrNormalizedSource]] = {}
    for source in sorted_sources:
        per_engine.setdefault(source.engine, []).append(source)

    candidates: list[StructuralCandidate] = []
    fingerprint_parts: list[str] = []
    for engine in sorted(per_engine):
        engine_sources = per_engine[engine]
        ocr_evidence = [
            OcrStructuralEvidence(
                text=source.text,
                scope=source.source_scope,
                region_index=source.region_index,
                page_ocr_result_id=source.page_ocr_result_id,
            )
            for source in engine_sources
        ]
        candidates.append(
            structural_candidate_from_ocr_evidence(
                page_number=page.page_number,
                ocr_evidence=ocr_evidence,
            )
        )
        fingerprint_parts.append(
            "|".join(
                f"OCR:{engine}:{source.source_scope}:{source.region_index}:{source.page_ocr_result_id}:{source.content_sha256}"
                for source in engine_sources
            )
        )

    return candidates, True, tuple(fingerprint_parts)


def _materialize_vision_candidate(db: Session, *, document_id: str, document_page_id: str, page_number: int) -> tuple[StructuralCandidate | None, tuple[str, ...]]:
    def _is_reusable_structural_runtime(structured_json: dict) -> bool:
        runtime = structured_json.get("_vision_runtime")
        if not isinstance(runtime, dict):
            return True

        if str(runtime.get("task_type") or "") != VISION_TASK_STRUCTURE_SCOPE:
            return False

        if runtime.get("structure_schema_valid") is not None:
            return bool(runtime.get("structure_schema_valid"))

        schema_valid = runtime.get("schema_valid")
        if schema_valid is not False:
            return True

        # Historical payloads used `schema_valid` as a page-level flag and can be
        # false when only the detail-transcription task failed. Keep those reusable
        # when detail runtime is explicitly present and non-completed.
        detail_runtime = structured_json.get("_detail_runtime")
        if isinstance(detail_runtime, dict) and str(detail_runtime.get("status") or "") != "COMPLETED":
            return True

        return False

    statement = (
        select(DocumentVisionAnalysis, DocumentVisionPageResult)
        .join(DocumentVisionPageResult, DocumentVisionPageResult.analysis_id == DocumentVisionAnalysis.id)
        .where(
            DocumentVisionAnalysis.document_id == document_id,
            DocumentVisionAnalysis.prompt_version.in_(VISION_STRUCTURE_SCOPE_COMPATIBLE_PROMPT_VERSIONS),
            DocumentVisionAnalysis.status.in_(("COMPLETED", "PARTIAL")),
            DocumentVisionPageResult.document_page_id == document_page_id,
            DocumentVisionPageResult.page_number == page_number,
            DocumentVisionPageResult.status.in_(("COMPLETED", "PARTIAL")),
        )
        .order_by(DocumentVisionAnalysis.created_at.desc(), DocumentVisionPageResult.created_at.desc())
    )

    rows = db.execute(statement).all()
    fallback: tuple[StructuralCandidate, tuple[str, ...]] | None = None
    for analysis, page_result in rows:
        structured_json = page_result.structured_json
        if not isinstance(structured_json, dict):
            continue
        if not _is_reusable_structural_runtime(structured_json):
            continue
        candidate = structural_candidate_from_vision_005(
            structured_json=structured_json,
            page_number=page_number,
            source_analysis_id=analysis.id,
            source_page_result_id=page_result.id,
        )
        if candidate.structural_quality != "VALID":
            continue
        fingerprint = (
            "VISION:" + ":".join(
                [
                    analysis.id,
                    analysis.prompt_version,
                    page_result.id,
                    page_result.image_sha256,
                    _sha256(str(structured_json)),
                ]
            ),
        )
        if analysis.prompt_version == VISION_STRUCTURE_SCOPE_PROMPT_VERSION:
            return candidate, fingerprint
        if fallback is None:
            fallback = (candidate, fingerprint)

    if fallback is not None:
        return fallback

    return None, ()


def _build_input_fingerprint(page: DocumentPage, native_hash: str, ocr_fingerprint_parts: tuple[str, ...], vision_fingerprint_parts: tuple[str, ...]) -> str:
    payload = "|".join(
        [
            STRUCTURE_RESOLVER_VERSION,
            page.id,
            str(page.page_number),
            native_hash,
            *ocr_fingerprint_parts,
            *vision_fingerprint_parts,
        ]
    )
    return _sha256(payload)


def _provider_state(page: DocumentPage, *, ocr_evaluated: bool, vision_evaluated: bool) -> ProviderAcquisitionState:
    ocr_applicable = page.content_profile in {"MIXED_CONTENT", "IMAGE_ONLY"} or page.status == "NO_TEXT"
    return ProviderAcquisitionState(
        native_evaluated=True,
        ocr_evaluated=ocr_evaluated,
        ocr_applicable=ocr_applicable,
        vision_evaluated=vision_evaluated,
    )


def _candidate_preference(method: str) -> int:
    if method == "NATIVE_TEXT":
        return 0
    if method == "OCR":
        return 1
    if method == "VISION":
        return 2
    return 9


def _find_selected_candidate(resolution: PageStructureResolution, candidates: list[StructuralCandidate]) -> StructuralCandidate | None:
    if resolution.resolved_state is None or resolution.resolved_source_method is None:
        return None

    valid_candidates = [
        candidate
        for candidate in candidates
        if candidate.page_state is not None
        and candidate.structural_quality == "VALID"
        and candidate.source_method == resolution.resolved_source_method
        and candidate.page_state.segments == resolution.resolved_state.segments
        and candidate.page_state.outgoing_item_key == resolution.resolved_state.outgoing_item_key
        and candidate.page_state.incoming_item_key == resolution.resolved_state.incoming_item_key
    ]
    if not valid_candidates:
        return None

    return sorted(
        valid_candidates,
        key=lambda candidate: (
            _candidate_preference(candidate.source_method),
            candidate.source_analysis_id or "",
            candidate.source_page_result_id or "",
        ),
    )[0]


def _unknown_page_state(page_number: int, resolution: PageStructureResolution, candidates: list[StructuralCandidate]) -> object:
    ordered_candidates = sorted(
        [candidate for candidate in candidates if candidate.evaluated],
        key=lambda candidate: (_candidate_preference(candidate.source_method), candidate.source_method),
    )
    source_method = resolution.resolved_source_method or (ordered_candidates[0].source_method if ordered_candidates else PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT)
    warnings: tuple[str, ...] = (resolution.reason,) if resolution.reason else ()
    return build_page_structural_state(
        page_number=page_number,
        segments=(),
        state_quality=PAGE_STRUCTURE_UNKNOWN,
        review_required=True,
        provenance=PageStructuralProvenance(source_method=source_method),
        warnings=warnings,
    )


def _upsert_page_resolution(
    db: Session,
    *,
    document_id: str,
    page: DocumentPage,
    resolution: PageStructureResolution,
    input_fingerprint_sha256: str,
) -> DocumentPageStructureResolution:
    existing = db.scalar(
        select(DocumentPageStructureResolution).where(DocumentPageStructureResolution.document_page_id == page.id)
    )
    if existing is None:
        existing = DocumentPageStructureResolution(
            source_document_id=document_id,
            document_page_id=page.id,
            page_number=page.page_number,
            status=resolution.status,
            selected_source_method=resolution.resolved_source_method,
            review_required=resolution.review_required,
            reason=resolution.reason,
            resolver_version=STRUCTURE_RESOLVER_VERSION,
            input_fingerprint_sha256=input_fingerprint_sha256,
        )
        db.add(existing)
        return existing

    existing.page_number = page.page_number
    existing.status = resolution.status
    existing.selected_source_method = resolution.resolved_source_method
    existing.review_required = resolution.review_required
    existing.reason = resolution.reason
    existing.resolver_version = STRUCTURE_RESOLVER_VERSION
    existing.input_fingerprint_sha256 = input_fingerprint_sha256
    return existing


def _load_canonical_items(db: Session, tender_id: str) -> list[CanonicalTenderItemReference]:
    rows = db.execute(
        select(TenderItem.id, TenderItem.item_number)
        .where(TenderItem.tender_id == tender_id, TenderItem.item_number.is_not(None))
        .order_by(TenderItem.item_number.asc(), TenderItem.id.asc())
    ).all()
    return [
        CanonicalTenderItemReference(tender_item_id=tender_item_id, item_number=item_number)
        for tender_item_id, item_number in rows
        if item_number is not None
    ]


def _reconcile_continuity_conflicts_on_page_resolutions(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    page_inputs: list[TenderScopeSegmentInput],
    canonical_items: list[CanonicalTenderItemReference],
) -> set[str]:
    db.flush()

    decisions = resolve_scope_ownership_decisions_for_page_inputs(
        tender_id=tender_id,
        page_inputs=page_inputs,
        canonical_items=canonical_items,
    )
    conflicted_page_ids = {
        decision.document_page_id
        for decision in decisions
        if decision.continuity_note == CONTINUITY_NOTE_MISMATCH_RESET
    }

    if not conflicted_page_ids:
        return set()

    rows = db.execute(
        select(DocumentPageStructureResolution).where(
            DocumentPageStructureResolution.source_document_id == document_id,
            DocumentPageStructureResolution.document_page_id.in_(tuple(conflicted_page_ids)),
        )
    ).scalars().all()

    for row in rows:
        row.review_required = True
        if row.status == "RESOLVED" or not row.reason:
            row.reason = DOCUMENT_CONTINUITY_CONFLICT_REASON

    return {row.document_page_id for row in rows}


def _policy_allows_ocr(execution_policy: str) -> bool:
    return execution_policy in {EXECUTION_POLICY_ALLOW_OCR, EXECUTION_POLICY_AUTO}


def _policy_allows_vision(execution_policy: str) -> bool:
    return execution_policy == EXECUTION_POLICY_AUTO


def _is_ocr_acquisition_useful(page: DocumentPage) -> bool:
    if page.status == DocumentPageStatus.NO_TEXT.value:
        return True
    if page.content_profile == "IMAGE_ONLY":
        return True
    if page.content_profile == "MIXED_CONTENT":
        return True
    return False


def _preferred_ocr_provider_id() -> str:
    providers = get_ocr_providers()
    for provider_id in AUTO_OCR_PROVIDER_ORDER:
        for provider in providers:
            if provider.provider_id == provider_id and provider.status == "AVAILABLE":
                return provider.provider_id
    raise RuntimeError("No OCR providers are currently available")


def _default_ocr_executor(request: OcrAcquisitionRequest) -> None:
    plan = _build_ocr_execution_plan(request)
    if not plan.jobs:
        return

    provider = None
    for candidate in get_ocr_providers():
        if candidate.provider_id == plan.provider_id and candidate.status == "AVAILABLE":
            provider = candidate
            break
    if provider is None:
        raise RuntimeError(f"OCR provider {plan.provider_id} is unavailable")

    import fitz

    document_path = _resolve_document_file_path(plan.stored_relative_path)
    artifacts: list[dict[str, object]] = []
    pdf_document = fitz.open(str(document_path))
    try:
        page_index = plan.page_number - 1
        if page_index < 0 or page_index >= pdf_document.page_count:
            raise RuntimeError(f"Page number {plan.page_number} is outside the document page range")
        page = pdf_document[page_index]

        for job in plan.jobs:
            if job.scope == "IMAGE_REGION":
                if None in (job.x0, job.y0, job.x1, job.y1):
                    continue
                region_rect = fitz.Rect(float(job.x0), float(job.y0), float(job.x1), float(job.y1))
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=region_rect)
            else:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            payload_bytes = pix.tobytes("png")
            try:
                provider_result = provider.recognize(payload_bytes, language=plan.language)
            except Exception as exc:
                provider_result = {
                    "text": "",
                    "status": "OCR_FAILED",
                    "engine": provider.provider_id,
                    "engine_version": provider.version,
                    "language": plan.language,
                    "confidence": None,
                    "processing_time_ms": None,
                    "warnings": [str(exc)],
                }

            warnings = provider_result.get("warnings", [])
            normalized_warnings = "; ".join(warnings) if isinstance(warnings, list) else str(warnings or "")
            artifacts.append(
                {
                    "scope": job.scope,
                    "region_id": job.region_id,
                    "engine": str(provider_result.get("engine", provider.provider_id)),
                    "engine_version": str(provider_result.get("engine_version", provider.version)),
                    "language": str(provider_result.get("language", plan.language)),
                    "text": str(provider_result.get("text", "")),
                    "status": str(provider_result.get("status", "OCR_TEXT_EXTRACTED")),
                    "confidence": provider_result.get("confidence"),
                    "processing_time_ms": provider_result.get("processing_time_ms"),
                    "warnings": normalized_warnings,
                }
            )
    finally:
        pdf_document.close()

    _persist_ocr_artifacts(plan, artifacts)


def _default_vision_executor(request: VisionStructureAcquisitionRequest) -> None:
    analyze_vision_document_structure_only_isolated(
        tender_id=request.tender_id,
        document_id=request.document_id,
        page_numbers=[request.page_number],
        mode="ASSISTIVE_EXTRACTION",
        force_retry_on_unusable_structure=True,
        previous_open_item_key=request.previous_open_item_key,
    )


def _previous_open_item_hint_for_page(
    snapshots: list[_PageResolutionSnapshot],
    *,
    current_page_number: int,
) -> str | None:
    previous_page_number = current_page_number - 1
    if previous_page_number < 1:
        return None

    previous_snapshot = next((snapshot for snapshot in snapshots if snapshot.page_number == previous_page_number), None)
    if previous_snapshot is None:
        return None

    previous_resolution = previous_snapshot.resolution
    previous_state = previous_resolution.resolved_state
    if previous_resolution.status != "RESOLVED" or previous_state is None:
        return None
    if previous_state.state_quality != PAGE_STRUCTURE_VALID:
        return None

    return previous_state.outgoing_item_key


def _build_ocr_execution_plan(request: OcrAcquisitionRequest) -> _OcrExecutionPlan:
    provider_id = _preferred_ocr_provider_id()
    if request.content_profile == "IMAGE_ONLY" or request.page_status == DocumentPageStatus.NO_TEXT.value:
        scope = "FULL_PAGE"
    elif request.content_profile == "MIXED_CONTENT":
        scope = "IMAGE_REGION"
    else:
        raise RuntimeError("OCR acquisition is not useful for TEXT_ONLY pages")

    with SessionLocal() as read_db:
        document = read_db.get(TenderDocument, request.document_id)
        if document is None or document.tender_id != request.tender_id:
            raise RuntimeError("Document not found while planning OCR acquisition")
        page = read_db.get(DocumentPage, request.document_page_id)
        if page is None or page.document_id != request.document_id:
            raise RuntimeError("Document page not found while planning OCR acquisition")

        if scope == "FULL_PAGE":
            jobs = (
                _OcrJobPlan(
                    scope="FULL_PAGE",
                    region_id=None,
                    region_index=None,
                    x0=None,
                    y0=None,
                    x1=None,
                    y1=None,
                ),
            )
        else:
            regions = (
                read_db.execute(
                    select(DocumentPageRegion)
                    .where(DocumentPageRegion.document_page_id == request.document_page_id)
                    .order_by(DocumentPageRegion.region_index.asc())
                )
                .scalars()
                .all()
            )
            jobs = tuple(
                _OcrJobPlan(
                    scope="IMAGE_REGION",
                    region_id=region.id,
                    region_index=region.region_index,
                    x0=region.x0,
                    y0=region.y0,
                    x1=region.x1,
                    y1=region.y1,
                )
                for region in regions
                if region.region_type == "IMAGE"
            )

        return _OcrExecutionPlan(
            tender_id=request.tender_id,
            document_id=request.document_id,
            document_page_id=request.document_page_id,
            page_number=request.page_number,
            provider_id=provider_id,
            language="es+en",
            stored_relative_path=document.stored_relative_path,
            jobs=jobs,
        )


def _persist_ocr_artifacts(plan: _OcrExecutionPlan, artifacts: list[dict[str, object]]) -> None:
    with SessionLocal() as write_db:
        for artifact in artifacts:
            scope = str(artifact["scope"])
            region_id = artifact.get("region_id")
            existing = write_db.execute(
                select(PageOcrResult).where(
                    PageOcrResult.document_page_id == plan.document_page_id,
                    PageOcrResult.engine == str(artifact["engine"]),
                    PageOcrResult.scope == scope,
                    or_(
                        PageOcrResult.region_id == (str(region_id) if region_id is not None else None),
                        and_(PageOcrResult.region_id.is_(None), region_id is None),
                    ),
                )
            ).scalar_one_or_none()

            if existing is None:
                existing = PageOcrResult(
                    document_page_id=plan.document_page_id,
                    engine=str(artifact["engine"]),
                    engine_version=str(artifact["engine_version"]),
                    language=str(artifact["language"]),
                    text=str(artifact["text"]),
                    status=str(artifact["status"]),
                    confidence=artifact.get("confidence"),
                    processing_time_ms=artifact.get("processing_time_ms"),
                    warnings=str(artifact.get("warnings") or ""),
                    scope=scope,
                    region_id=str(region_id) if region_id is not None else None,
                )
                write_db.add(existing)
            else:
                existing.engine_version = str(artifact["engine_version"])
                existing.language = str(artifact["language"])
                existing.text = str(artifact["text"])
                existing.status = str(artifact["status"])
                existing.confidence = artifact.get("confidence")
                existing.processing_time_ms = artifact.get("processing_time_ms")
                existing.warnings = str(artifact.get("warnings") or "")
                existing.scope = scope
                existing.region_id = str(region_id) if region_id is not None else None
            write_db.flush()

        document = write_db.get(TenderDocument, plan.document_id)
        if document is None:
            raise RuntimeError("Document not found while normalizing OCR output")
        process_document_normalization(write_db, document)
        write_db.commit()


def _load_page_with_sources(db: Session, page_id: str) -> DocumentPage:
    page = db.execute(
        select(DocumentPage)
        .options(
            selectinload(DocumentPage.normalized_content).selectinload(NormalizedContent.page_ocr_result),
            selectinload(DocumentPage.normalized_content).selectinload(NormalizedContent.region),
            selectinload(DocumentPage.ocr_results),
        )
        .where(DocumentPage.id == page_id)
    ).scalar_one_or_none()
    if page is None:
        raise LookupError("Document page not found")
    return page


def _collect_candidates_for_page(
    db: Session,
    *,
    document_id: str,
    page: DocumentPage,
) -> tuple[StructuralCandidate, list[StructuralCandidate], StructuralCandidate | None, str, tuple[str, ...], tuple[str, ...]]:
    native_candidate, native_hash = _materialize_native_candidate(page)
    ocr_candidates, _, ocr_fingerprint_parts = _materialize_ocr_candidates(page)
    vision_candidate, vision_fingerprint_parts = _materialize_vision_candidate(
        db,
        document_id=document_id,
        document_page_id=page.id,
        page_number=page.page_number,
    )
    return (
        native_candidate,
        ocr_candidates,
        vision_candidate,
        native_hash,
        ocr_fingerprint_parts,
        vision_fingerprint_parts,
    )


def orchestrate_document_structure_available_only(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    page_numbers: list[int] | None = None,
    execution_policy: str = EXECUTION_POLICY_AVAILABLE_ONLY,
    ocr_executor: OcrExecutor | None = None,
    vision_executor: VisionExecutor | None = None,
) -> DocumentStructureOrchestrationResult:
    _ = db
    if execution_policy not in {EXECUTION_POLICY_AVAILABLE_ONLY, EXECUTION_POLICY_ALLOW_OCR, EXECUTION_POLICY_AUTO}:
        raise ValueError(f"Unsupported execution policy: {execution_policy}")

    effective_ocr_executor = ocr_executor or _default_ocr_executor
    effective_vision_executor = vision_executor or _default_vision_executor

    with SessionLocal() as read_db:
        document = read_db.get(TenderDocument, document_id)
        if document is None:
            raise ValueError("DOCUMENT_NOT_FOUND")
        if document.tender_id != tender_id:
            raise ValueError("DOCUMENT_TENDER_MISMATCH")

        page_statement = select(DocumentPage.id).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number.asc())
        if page_numbers:
            page_statement = page_statement.where(DocumentPage.page_number.in_(page_numbers))
        page_ids = list(read_db.execute(page_statement).scalars().all())

    final_snapshots: list[_PageResolutionSnapshot] = []

    for page_id in page_ids:
        attempted_ocr = False
        attempted_vision = False
        final_resolution: PageStructureResolution | None = None
        final_candidates: list[StructuralCandidate] = []
        final_page_number: int | None = None
        native_hash = ""
        ocr_fingerprint_parts: tuple[str, ...] = ()
        vision_fingerprint_parts: tuple[str, ...] = ()
        final_page_status = ""
        final_content_profile = ""

        while True:
            with SessionLocal() as read_db:
                page = _load_page_with_sources(read_db, page_id)
                final_page_number = page.page_number
                final_page_status = page.status
                final_content_profile = page.content_profile
                (
                    native_candidate,
                    ocr_candidates,
                    vision_candidate,
                    native_hash,
                    ocr_fingerprint_parts,
                    vision_fingerprint_parts,
                ) = _collect_candidates_for_page(read_db, document_id=document_id, page=page)

                final_candidates = [native_candidate, *ocr_candidates]
                if vision_candidate is not None:
                    final_candidates.append(vision_candidate)

                ocr_useful = _is_ocr_acquisition_useful(page)
                if _policy_allows_ocr(execution_policy):
                    ocr_evaluated = bool(ocr_candidates) or attempted_ocr or not ocr_useful
                else:
                    ocr_evaluated = bool(ocr_candidates)

                # Persisted compatible VISION results are only considered evaluated when structurally valid.
                vision_evaluated = any(
                    candidate.source_method == PAGE_STRUCTURE_SOURCE_METHOD_VISION and candidate.structural_quality == "VALID"
                    for candidate in final_candidates
                ) or attempted_vision
                provider_state = ProviderAcquisitionState(
                    native_evaluated=True,
                    ocr_evaluated=ocr_evaluated,
                    ocr_applicable=ocr_useful,
                    vision_evaluated=vision_evaluated,
                )

                resolution = resolve_page_structure(
                    candidates=final_candidates,
                    acquisition_state=provider_state,
                )
                final_resolution = resolution

            if resolution.status in {"RESOLVED", RESOLUTION_REVIEW_REQUIRED}:
                break

            if resolution.status == "NEEDS_OCR":
                if not _policy_allows_ocr(execution_policy) or attempted_ocr:
                    break
                attempted_ocr = True
                if not ocr_useful:
                    continue
                try:
                    effective_ocr_executor(
                        OcrAcquisitionRequest(
                            tender_id=tender_id,
                            document_id=document_id,
                            document_page_id=page_id,
                            page_number=final_page_number or 0,
                            page_status=final_page_status,
                            content_profile=final_content_profile,
                        )
                    )
                except Exception:
                    # Under AUTO we can still escalate to VISION; ALLOW_OCR remains unresolved.
                    pass
                continue

            if resolution.status == "NEEDS_VISION":
                if not _policy_allows_vision(execution_policy) or attempted_vision:
                    break
                attempted_vision = True
                previous_open_item_key = _previous_open_item_hint_for_page(
                    final_snapshots,
                    current_page_number=final_page_number or 0,
                )
                try:
                    effective_vision_executor(
                        VisionStructureAcquisitionRequest(
                            tender_id=tender_id,
                            document_id=document_id,
                            document_page_id=page_id,
                            page_number=final_page_number or 0,
                            previous_open_item_key=previous_open_item_key,
                        )
                    )
                except Exception as exc:
                    final_resolution = PageStructureResolution(
                        status=RESOLUTION_REVIEW_REQUIRED,
                        resolved_state=None,
                        resolved_source_method=None,
                        needs_provider=None,
                        reason=f"VISION_ACQUISITION_FAILED:{exc}",
                        review_required=True,
                        considered_methods=resolution.considered_methods,
                    )
                    break
                continue

            break

        if final_page_number is None or final_resolution is None:
            raise RuntimeError("Page resolution state was not computed")

        final_snapshots.append(
            _PageResolutionSnapshot(
                document_page_id=page_id,
                page_number=final_page_number,
                resolution=final_resolution,
                candidates=tuple(final_candidates),
                native_hash=native_hash,
                ocr_fingerprint_parts=ocr_fingerprint_parts,
                vision_fingerprint_parts=vision_fingerprint_parts,
            )
        )

    page_inputs: list[TenderScopeSegmentInput] = []
    page_results: list[PageStructureOrchestrationResult] = []

    with SessionLocal() as write_db:
        canonical_items = _load_canonical_items(write_db, tender_id)
        for snapshot in final_snapshots:
            page = write_db.get(DocumentPage, snapshot.document_page_id)
            if page is None:
                raise LookupError("Document page not found while persisting orchestration result")

            resolution = snapshot.resolution
            selected_candidate = _find_selected_candidate(resolution, list(snapshot.candidates))
            effective_state = resolution.resolved_state or _unknown_page_state(snapshot.page_number, resolution, list(snapshot.candidates))

            if effective_state.provenance.source_method != PAGE_STRUCTURE_SOURCE_METHOD_VISION:
                effective_state = build_page_structural_state(
                    page_number=effective_state.page_number,
                    segments=effective_state.segments,
                    state_quality=effective_state.state_quality,
                    review_required=effective_state.review_required,
                    provenance=PageStructuralProvenance(
                        source_method=effective_state.provenance.source_method,
                        source_contract_version=effective_state.provenance.source_contract_version,
                    ),
                    incoming_item_key=effective_state.incoming_item_key,
                    outgoing_item_key=effective_state.outgoing_item_key,
                    warnings=effective_state.warnings,
                )

            input_fingerprint_sha256 = _build_input_fingerprint(
                page,
                snapshot.native_hash,
                snapshot.ocr_fingerprint_parts,
                snapshot.vision_fingerprint_parts,
            )
            _upsert_page_resolution(
                write_db,
                document_id=document_id,
                page=page,
                resolution=resolution,
                input_fingerprint_sha256=input_fingerprint_sha256,
            )

            source_analysis_id = None
            source_page_result_id = None
            if selected_candidate is not None and selected_candidate.source_method == "VISION":
                source_analysis_id = selected_candidate.source_analysis_id
                source_page_result_id = selected_candidate.source_page_result_id
            page_inputs.append(
                TenderScopeSegmentInput(
                    page_state=effective_state,
                    source_document_id=document_id,
                    document_page_id=page.id,
                    source_analysis_id=source_analysis_id,
                    source_page_result_id=source_page_result_id,
                )
            )

            page_results.append(
                PageStructureOrchestrationResult(
                    document_page_id=page.id,
                    page_number=page.page_number,
                    status=resolution.status,
                    selected_source_method=resolution.resolved_source_method,
                    needs_provider=resolution.needs_provider,
                    review_required=resolution.review_required,
                    reason=resolution.reason,
                    considered_methods=resolution.considered_methods,
                    input_fingerprint_sha256=input_fingerprint_sha256,
                )
            )

        persisted_scope_segments = replace_tender_scope_segments_for_page_inputs(
            write_db,
            tender_id=tender_id,
            page_inputs=page_inputs,
            canonical_items=canonical_items,
        )

        reconciled_page_ids = _reconcile_continuity_conflicts_on_page_resolutions(
            write_db,
            tender_id=tender_id,
            document_id=document_id,
            page_inputs=page_inputs,
            canonical_items=canonical_items,
        )

        if reconciled_page_ids:
            updated_page_results: list[PageStructureOrchestrationResult] = []
            for row in page_results:
                if row.document_page_id not in reconciled_page_ids:
                    updated_page_results.append(row)
                    continue

                updated_page_results.append(
                    PageStructureOrchestrationResult(
                        document_page_id=row.document_page_id,
                        page_number=row.page_number,
                        status=row.status,
                        selected_source_method=row.selected_source_method,
                        needs_provider=row.needs_provider,
                        review_required=True,
                        reason=DOCUMENT_CONTINUITY_CONFLICT_REASON if row.status == "RESOLVED" or not row.reason else row.reason,
                        considered_methods=row.considered_methods,
                        input_fingerprint_sha256=row.input_fingerprint_sha256,
                    )
                )
            page_results = updated_page_results

        write_db.commit()

    return DocumentStructureOrchestrationResult(
        tender_id=tender_id,
        document_id=document_id,
        execution_policy=execution_policy,
        page_results=tuple(page_results),
        scope_segments_persisted=len(persisted_scope_segments),
    )
