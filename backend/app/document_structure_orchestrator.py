from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DocumentPage,
    DocumentPageStructureResolution,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    NormalizedContent,
    TenderDocument,
    TenderItem,
)
from app.ollama_vision import VISION_STRUCTURE_SCOPE_PROMPT_VERSION
from app.page_structure import (
    PAGE_STRUCTURE_SOURCE_METHOD_NATIVE_TEXT,
    PAGE_STRUCTURE_UNKNOWN,
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
from app.scope_segments import TenderScopeSegmentInput, replace_tender_scope_segments_for_page_inputs

EXECUTION_POLICY_AVAILABLE_ONLY = "AVAILABLE_ONLY"
STRUCTURE_RESOLVER_VERSION = "mvp-06.2.5b1-available-only-v1"


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
    statement = (
        select(DocumentVisionAnalysis, DocumentVisionPageResult)
        .join(DocumentVisionPageResult, DocumentVisionPageResult.analysis_id == DocumentVisionAnalysis.id)
        .where(
            DocumentVisionAnalysis.document_id == document_id,
            DocumentVisionAnalysis.prompt_version == VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
            DocumentVisionAnalysis.status.in_(("COMPLETED", "PARTIAL")),
            DocumentVisionPageResult.document_page_id == document_page_id,
            DocumentVisionPageResult.page_number == page_number,
            DocumentVisionPageResult.status.in_(("COMPLETED", "PARTIAL")),
        )
        .order_by(DocumentVisionAnalysis.created_at.desc(), DocumentVisionPageResult.created_at.desc())
    )

    rows = db.execute(statement).all()
    for analysis, page_result in rows:
        structured_json = page_result.structured_json
        if not isinstance(structured_json, dict):
            continue
        candidate = structural_candidate_from_vision_005(
            structured_json=structured_json,
            page_number=page_number,
            source_analysis_id=analysis.id,
            source_page_result_id=page_result.id,
        )
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
        return candidate, fingerprint

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


def orchestrate_document_structure_available_only(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    page_numbers: list[int] | None = None,
) -> DocumentStructureOrchestrationResult:
    db.flush()

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise ValueError("DOCUMENT_NOT_FOUND")
    if document.tender_id != tender_id:
        raise ValueError("DOCUMENT_TENDER_MISMATCH")

    page_statement = (
        select(DocumentPage)
        .options(
            selectinload(DocumentPage.normalized_content).selectinload(NormalizedContent.page_ocr_result),
            selectinload(DocumentPage.normalized_content).selectinload(NormalizedContent.region),
            selectinload(DocumentPage.ocr_results),
        )
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc())
    )
    if page_numbers:
        page_statement = page_statement.where(DocumentPage.page_number.in_(page_numbers))

    pages = db.execute(page_statement).scalars().all()

    page_inputs: list[TenderScopeSegmentInput] = []
    page_results: list[PageStructureOrchestrationResult] = []

    for page in pages:
        native_candidate, native_hash = _materialize_native_candidate(page)
        ocr_candidates, ocr_evaluated, ocr_fingerprint_parts = _materialize_ocr_candidates(page)
        vision_candidate, vision_fingerprint_parts = _materialize_vision_candidate(
            db,
            document_id=document_id,
            document_page_id=page.id,
            page_number=page.page_number,
        )

        candidates: list[StructuralCandidate] = [native_candidate, *ocr_candidates]
        if vision_candidate is not None:
            candidates.append(vision_candidate)

        provider_state = _provider_state(
            page,
            ocr_evaluated=ocr_evaluated,
            vision_evaluated=vision_candidate is not None,
        )

        resolution = resolve_page_structure(
            candidates=candidates,
            acquisition_state=provider_state,
        )
        selected_candidate = _find_selected_candidate(resolution, candidates)
        effective_state = resolution.resolved_state or _unknown_page_state(page.page_number, resolution, candidates)

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
            native_hash,
            ocr_fingerprint_parts,
            vision_fingerprint_parts,
        )
        _upsert_page_resolution(
            db,
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

    canonical_items = _load_canonical_items(db, tender_id)
    persisted_scope_segments = replace_tender_scope_segments_for_page_inputs(
        db,
        tender_id=tender_id,
        page_inputs=page_inputs,
        canonical_items=canonical_items,
    )

    return DocumentStructureOrchestrationResult(
        tender_id=tender_id,
        document_id=document_id,
        execution_policy=EXECUTION_POLICY_AVAILABLE_ONLY,
        page_results=tuple(page_results),
        scope_segments_persisted=len(persisted_scope_segments),
    )
