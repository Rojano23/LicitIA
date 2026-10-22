"""Persisted provider artifacts at the DI boundary; never execute providers.

Detail lineage retains the existing fingerprint reselection policy. It is lifecycle
eligibility, not resolution of disagreements between independent active sources.
"""
from __future__ import annotations
from app.read_batch import memo_read

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, NormalizedContent, PageOcrResult, TenderDocument
from app.document_intelligence import Capability, PageIdentity, PerceptionEvidence, Quality, RoutingResult, normalize_perception_evidence, route_capability

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"

@dataclass(frozen=True, slots=True)
class PersistedPerceptionArtifact:
    tender_id: str
    source_document_id: str
    document_page_id: str
    source_method: str
    source_artifact_key: str
    source_contract_version: str | None = None
    source_locator: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    payload: dict | None = None

@dataclass(frozen=True, slots=True)
class _EnumeratedArtifact:
    page_number: int
    sort_key: str
    artifact: PersistedPerceptionArtifact
    analysis_created_at: datetime | None = None
    page_result_created_at: datetime | None = None
    page_result_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class _EnumeratedArtifacts:
    active: tuple[_EnumeratedArtifact, ...]
    deselected: tuple[_EnumeratedArtifact, ...]


@memo_read
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
            artifact=PersistedPerceptionArtifact(
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
        normalized_ocr = db.scalars(select(NormalizedContent).where(
            NormalizedContent.page_ocr_result_id == ocr_row.id,
            NormalizedContent.source_type == 'OCR')).all()
        normalized_ocr_id = normalized_ocr[0].id if len(normalized_ocr) == 1 else None
        active.append(
            _EnumeratedArtifact(
                page_number=page.page_number,
                sort_key=f"ocr:{page.page_number:04d}:{ocr_row.id}",
                artifact=PersistedPerceptionArtifact(
                    tender_id=tender_id,
                    source_document_id=document_id,
                    document_page_id=ocr_row.document_page_id,
                    source_method="OCR",
                    source_artifact_key=f"ocr-result:{ocr_row.id}",
                    source_contract_version=_optional_text(ocr_row.engine_version),
                    source_locator=_ocr_source_locator(page.page_number, ocr_row.scope, ocr_row.region_id),
                    payload={
                        "text": ocr_row.text,
                        "normalized_content_id": normalized_ocr_id,
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
                artifact=PersistedPerceptionArtifact(
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



def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def page_identity(document: TenderDocument, page: DocumentPage) -> PageIdentity:
    return PageIdentity(tender_id=document.tender_id, document_id=document.id,
        document_page_id=page.id, page_number=page.page_number,
        document_version=str(document.revision_number))


def transcription_from_artifact(db: Session, artifact: PersistedPerceptionArtifact,
                                *, lineage: str = "ACTIVE") -> PerceptionEvidence:
    """Explicit acquisition status is not a fidelity certificate.

    Legacy Native/OCR and validated Vision transcriptions remain reviewable.
    Failed detail runtime cannot borrow text from the independent structure task.
    """
    page = db.get(DocumentPage, artifact.document_page_id)
    document = db.get(TenderDocument, artifact.source_document_id)
    if page is None or document is None or page.document_id != document.id or document.tender_id != artifact.tender_id:
        raise ValueError("PERCEPTION_ARTIFACT_PAGE_MISMATCH")
    payload = artifact.payload or {}
    text = _transcription_text(payload.get("text"))
    quality = Quality.REVIEW_REQUIRED
    metadata = ()
    diagnostics = ("PERCEPTION_FIDELITY_NOT_CERTIFIED",)
    generation = artifact.source_artifact_key
    normalized_id = payload.get("normalized_content_id")
    if artifact.source_method == "OCR":
        row = db.get(PageOcrResult, artifact.source_artifact_key.removeprefix("ocr-result:"))
        if row is None or row.document_page_id != page.id:
            raise ValueError("OCR_ARTIFACT_PAGE_MISMATCH")
        generation = row.id
        metadata = (("engine", row.engine),)
        if row.status != "OCR_TEXT_EXTRACTED":
            quality = Quality.FAILED
            diagnostics = ("OCR_TRANSCRIPTION_NOT_COMPLETED",)
    elif artifact.source_method == "VISION":
        row = db.get(DocumentVisionPageResult, artifact.source_page_result_id)
        if row is None or row.document_page_id != page.id or row.analysis_id != artifact.source_analysis_id:
            raise ValueError("VISION_ARTIFACT_PAGE_MISMATCH")
        analysis = row.analysis
        generation = analysis.input_fingerprint_sha256
        metadata = (("model", analysis.model_name), ("prompt_version", analysis.prompt_version))
        detail = payload.get("detail_transcription")
        runtime = payload.get("_detail_runtime")
        failed = (row.status not in {"COMPLETED", "PARTIAL"}
                  or analysis.status not in {"COMPLETED", "PARTIAL"}
                  or isinstance(runtime, dict) and (runtime.get("status") != "COMPLETED" or runtime.get("schema_valid") is False))
        if failed:
            text = ""
            quality = Quality.FAILED
            diagnostics = ("DETAIL_TRANSCRIPTION_FAILED",)
        elif isinstance(detail, dict) and detail.get("task_type") == VISION_DETAIL_TASK_TYPE:
            # Only transcription output, never provider prose/raw_response_text.
            text = _transcription_text(detail.get("raw_text") or detail.get("text") or detail.get("extracted_plain_text"))
            if not text:
                rows = detail.get("parsed_supply_rows")
                if isinstance(rows, list):
                    text = "\n".join(_transcription_text(r.get("raw_visible_text") or r.get("source_excerpt") or r.get("raw_text") or r.get("description")) for r in rows if isinstance(r, dict))
        else:
            text = row.extracted_plain_text or row.extracted_markdown or ""
            vision_runtime = payload.get("_vision_runtime")
            if vision_runtime is not None and not isinstance(vision_runtime, dict):
                raise ValueError("INVALID_VISION_RUNTIME_METADATA")
            task = (vision_runtime or {}).get("task_type")
            if task == "STRUCTURE_SCOPE":
                text = ""
                quality = Quality.UNAVAILABLE
                diagnostics = ("NO_INDEPENDENT_DETAIL_TRANSCRIPTION",)
    elif normalized_id:
        normalized = db.get(NormalizedContent, normalized_id)
        if normalized is None or normalized.document_page_id != page.id:
            raise ValueError("NORMALIZED_ARTIFACT_PAGE_MISMATCH")
        generation = normalized.id + ":" + normalized.content_sha256
    if not text.strip() and quality == Quality.REVIEW_REQUIRED:
        quality = Quality.UNAVAILABLE
    return normalize_perception_evidence(source_method=artifact.source_method, page=page_identity(document, page),
        capability=Capability.TRANSCRIPTION, text=text, quality=quality,
        source_artifact_key=artifact.source_artifact_key, generation_id=generation,
        source_locator=artifact.source_locator, source_contract_version=artifact.source_contract_version,
        source_analysis_id=artifact.source_analysis_id, source_page_result_id=artifact.source_page_result_id,
        normalized_content_id=normalized_id, lineage=lineage, diagnostics=diagnostics, provider_metadata=metadata)


def load_document_transcriptions(db: Session, document: TenderDocument) -> dict[str, RoutingResult]:
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id).order_by(DocumentPage.page_number)).all()
    observations: dict[str, list[PerceptionEvidence]] = {p.id: [] for p in pages}
    artifacts = _enumerate_persisted_artifacts_for_document(db, tender_id=document.tender_id, document_id=document.id, pages=pages)
    # Preserve every normalized observation; Scope's native artifact identity stays unchanged.
    for normalized in db.scalars(select(NormalizedContent).join(DocumentPage).where(DocumentPage.document_id == document.id)):
        if normalized.source_type not in {"NATIVE_PDF", "NATIVE_TEXT", "OCR"}:
            continue
        if normalized.source_type == "OCR" and normalized.page_ocr_result_id:
            row = db.get(PageOcrResult, normalized.page_ocr_result_id)
            if row is None or row.status != "OCR_TEXT_EXTRACTED":
                continue
            key = f"ocr-result:{row.id}"
            method = "OCR"
        elif normalized.source_type == "OCR":
            # Supported legacy normalization without an OCR-result FK: uncalibrated, review-only.
            key = f"normalized-content:{normalized.id}"
            method = "OCR"
        else:
            key = f"native-page:{normalized.document_page_id}"
            method = "NATIVE"
        page = db.get(DocumentPage, normalized.document_page_id)
        observations[page.id].append(normalize_perception_evidence(source_method=method,
            page=page_identity(document, page), capability=Capability.TRANSCRIPTION,
            source_artifact_key=key, generation_id=normalized.id + ":" + normalized.content_sha256,
            normalized_content_id=normalized.id, text=normalized.normalized_text,
            source_locator=f"page:{page.page_number}|scope:{normalized.source_scope}",
            source_contract_version="NORMALIZED_CONTENT_V1", quality=Quality.REVIEW_REQUIRED,
            diagnostics=("PERCEPTION_FIDELITY_NOT_CERTIFIED",)))
    for lineage, collection in (("ACTIVE", artifacts.active), ("DESELECTED", artifacts.deselected)):
        for item in collection:
            if item.artifact.source_method != "VISION":
                continue
            observation = transcription_from_artifact(db, item.artifact, lineage=lineage)
            observations[observation.page.document_page_id].append(observation)
    return {p.id: route_capability(page=page_identity(document, p), capability=Capability.TRANSCRIPTION,
            evidence=observations[p.id]) for p in pages}


def load_page_structure(db: Session, document: TenderDocument, page: DocumentPage) -> RoutingResult:
    """Structure is assessed independently from transcription availability.

    Existing parsers and typed structure validators own structural assessment.
    Vision generations without an explicit same-task fingerprint remain additive:
    timestamp cannot suppress an independent structural disagreement.
    """
    from app.page_structure_resolver import structural_candidate_from_native_text, structural_candidate_from_ocr_evidence, structural_candidate_from_vision_005, OcrStructuralEvidence
    from app.page_structure import PageStructuralProvenance
    from app.ollama_vision import VISION_STRUCTURE_SCOPE_COMPATIBLE_PROMPT_VERSIONS
    identity = page_identity(document, page)
    observations = []
    normalized = db.scalars(select(NormalizedContent).where(NormalizedContent.document_page_id == page.id)).all()
    native = [n for n in normalized if n.source_type in {"NATIVE_PDF", "NATIVE_TEXT"}]
    if not native and page.text:
        native_sources = [(f"native-page:{page.id}", page.text, None, "page-text:" + str(page.id))]
    else:
        native_sources = [(f"native-page:{page.id}", n.normalized_text, n.id, n.id + ":" + n.content_sha256) for n in native]
    for key, text, norm_id, generation in native_sources:
        candidate = structural_candidate_from_native_text(page_number=page.page_number, native_text=text)
        state = candidate.page_state
        observations.append(normalize_perception_evidence(source_method="NATIVE", page=identity,
            capability=Capability.STRUCTURE, source_artifact_key=key, generation_id=generation,
            normalized_content_id=norm_id, text=text, structural_state=state,
            source_contract_version=state.provenance.source_contract_version,
            quality=Quality.RELIABLE if state.state_quality == "VALID" and not state.review_required else Quality.REVIEW_REQUIRED,
            diagnostics=state.warnings, source_locator=f"page:{page.page_number}"))
    # Existing OCR parser needs all scopes per engine; retain that domain-neutral
    # assessment rather than changing duplicate/region ownership semantics.
    ocr_groups = {}
    for n in normalized:
        if n.source_type != "OCR" or not n.page_ocr_result_id:
            continue
        row = db.get(PageOcrResult, n.page_ocr_result_id)
        if row is None or row.status != "OCR_TEXT_EXTRACTED":
            continue
        ocr_groups.setdefault(row.engine, []).append((n, row))
    for engine, rows in sorted(ocr_groups.items()):
        rows.sort(key=lambda pair: (pair[1].scope, pair[0].id))
        candidate = structural_candidate_from_ocr_evidence(page_number=page.page_number,
            ocr_evidence=[OcrStructuralEvidence(text=n.normalized_text, scope=row.scope, page_ocr_result_id=row.id) for n, row in rows])
        state = candidate.page_state
        # OCR result identity is not a Vision page-result identity.
        state = replace(state, provenance=PageStructuralProvenance(source_method="OCR", source_contract_version=state.provenance.source_contract_version))
        observations.append(normalize_perception_evidence(source_method="OCR", page=identity,
            capability=Capability.STRUCTURE, source_artifact_key=f"ocr-result:{rows[0][1].id}",
            generation_id="|".join(n.id + ":" + n.content_sha256 for n, _ in rows),
            text="\n".join(n.normalized_text for n, _ in rows), structural_state=state,
            source_contract_version=state.provenance.source_contract_version, source_locator=f"page:{page.page_number}",
            quality=Quality.RELIABLE if state.state_quality == "VALID" and not state.review_required else Quality.REVIEW_REQUIRED,
            diagnostics=state.warnings, provider_metadata=(("engine", engine),)))
    groups = {}
    additive = []
    for row, analysis in db.execute(select(DocumentVisionPageResult, DocumentVisionAnalysis).join(DocumentVisionAnalysis)
        .where(DocumentVisionPageResult.document_page_id == page.id, DocumentVisionAnalysis.document_id == document.id,
               DocumentVisionAnalysis.tender_id == document.tender_id)):
        payload = row.structured_json
        if not isinstance(payload, dict) or analysis.prompt_version not in VISION_STRUCTURE_SCOPE_COMPATIBLE_PROMPT_VERSIONS:
            continue
        runtime = payload.get("_vision_runtime") or {}
        if not isinstance(runtime, dict):
            raise ValueError("INVALID_VISION_RUNTIME_METADATA")
        if runtime.get("task_type") not in {None, "STRUCTURE_SCOPE"}:
            continue
        candidate = structural_candidate_from_vision_005(structured_json=payload, page_number=page.page_number,
            source_analysis_id=analysis.id, source_page_result_id=row.id)
        state = candidate.page_state
        valid = row.status in {"COMPLETED", "PARTIAL"} and analysis.status in {"COMPLETED", "PARTIAL"}
        if runtime.get("structure_schema_valid") is False:
            valid = False
        if runtime.get("schema_valid") is False and runtime.get("structure_schema_valid") is None:
            detail_runtime = payload.get("_detail_runtime")
            valid = valid and isinstance(detail_runtime, dict) and detail_runtime.get("status") != "COMPLETED"
        quality = Quality.RELIABLE if valid and state.state_quality == "VALID" and not state.review_required else Quality.REVIEW_REQUIRED
        evidence = normalize_perception_evidence(source_method="VISION", page=identity, capability=Capability.STRUCTURE,
            source_artifact_key=f"vision-page-result:{row.id}", generation_id=analysis.input_fingerprint_sha256,
            source_analysis_id=analysis.id, source_page_result_id=row.id,
            source_contract_version=state.provenance.source_contract_version, structural_state=state,
            text="\n".join(s.anchor_raw_text or "" for s in state.segments), quality=quality,
            source_locator=f"page:{page.page_number}", diagnostics=state.warnings,
            provider_metadata=(("model", analysis.model_name),))
        fingerprint = runtime.get("task_fingerprint")
        if fingerprint:
            groups.setdefault(str(fingerprint), []).append((row, analysis, evidence))
        else:
            additive.append(evidence)
    observations.extend(additive)
    for group in groups.values():
        selected = max(group, key=lambda item: (_datetime_or_min(item[1].created_at), _datetime_or_min(item[0].updated_at), _datetime_or_min(item[0].created_at), item[0].id))
        observations.extend(e if row.id == selected[0].id else e.model_copy(update={"lineage": "DESELECTED"}) for row, _, e in group)
    return route_capability(page=identity, capability=Capability.STRUCTURE, evidence=observations)


def _transcription_text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("TRANSCRIPTION_TEXT_MUST_BE_STRING")
    return value
