from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, PageOcrResult

SOURCE_EFFECT_SUPPORTED_SOURCE_METHODS = ("NATIVE", "OCR", "VISION")
EXECUTION_POLICY_AVAILABLE_ONLY = "AVAILABLE_ONLY"

SOURCE_EFFECT_ADAPTER_STATUS_MATERIALIZED = "MATERIALIZED"
SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS = "NO_EFFECTS"
SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED = "UNSUPPORTED"
SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE = "INVALID_EVIDENCE"


@dataclass(frozen=True, slots=True)
class SourceEffectEvidenceArtifact:
    tender_id: str
    acting_document_id: str
    document_page_id: str
    page_number: int
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_text: str
    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


@dataclass(frozen=True, slots=True)
class SourceEffectEnumeratedArtifact:
    page_number: int
    sort_key: str
    artifact: SourceEffectEvidenceArtifact
    analysis_created_at: datetime | None = None
    page_result_created_at: datetime | None = None
    page_result_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SourceEffectEnumeratedArtifacts:
    active: tuple[SourceEffectEnumeratedArtifact, ...]
    deselected: tuple[SourceEffectEnumeratedArtifact, ...]


def resolve_source_effect_evidence_artifact(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_method: str,
    source_artifact_key: str,
) -> SourceEffectEvidenceArtifact:
    resolved_tender_id = _required_text("tender_id", tender_id)
    resolved_document_id = _required_text("acting_document_id", acting_document_id)
    resolved_page_id = _required_text("document_page_id", document_page_id)
    resolved_source_method = _required_text("source_method", source_method).upper()
    resolved_artifact_key = _required_text("source_artifact_key", source_artifact_key)

    if resolved_source_method not in SOURCE_EFFECT_SUPPORTED_SOURCE_METHODS:
        raise ValueError(f"Unsupported source_method: {source_method}")

    page = db.get(DocumentPage, resolved_page_id)
    if page is None:
        raise ValueError("document_page_id does not exist")
    if page.document_id != resolved_document_id:
        raise ValueError("document_page_id does not belong to acting_document_id")

    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    source_locator: str
    source_text: str | None

    if resolved_source_method == "NATIVE":
        page_id = _parse_prefixed_id(resolved_artifact_key, prefixes=("native-page:", "DocumentPage:"))
        if page_id is None:
            raise ValueError("Unsupported NATIVE source_artifact_key format")
        if page_id != page.id:
            raise ValueError("source artifact page is outside requested document_page_id")

        source_locator = f"page:{page.page_number}"
        source_text = _optional_text(page.text)
        source_contract_version = "NATIVE_TEXT_V1"

    elif resolved_source_method == "OCR":
        ocr_id = _parse_prefixed_id(resolved_artifact_key, prefixes=("ocr-result:", "PageOcrResult:"))
        if ocr_id is None:
            raise ValueError("Unsupported OCR source_artifact_key format")

        ocr_row = db.get(PageOcrResult, ocr_id)
        if ocr_row is None:
            raise ValueError("source artifact OCR result does not exist")
        if ocr_row.document_page_id != page.id:
            raise ValueError("source artifact OCR result is outside requested document_page_id")

        source_locator = _ocr_source_locator(page.page_number, ocr_row.scope, ocr_row.region_id)
        source_text = _optional_text(ocr_row.text)
        source_contract_version = _optional_text(ocr_row.engine_version)

    else:
        page_result_id = _parse_prefixed_id(
            resolved_artifact_key,
            prefixes=("vision-page-result:", "DocumentVisionPageResult:"),
        )
        if page_result_id is None:
            raise ValueError("Unsupported VISION source_artifact_key format")

        page_result = db.get(DocumentVisionPageResult, page_result_id)
        if page_result is None:
            raise ValueError("source artifact page result does not exist")
        if page_result.document_page_id != page.id:
            raise ValueError("source artifact page result is outside requested document_page_id")

        analysis = db.get(DocumentVisionAnalysis, page_result.analysis_id)
        if analysis is None:
            raise ValueError("source analysis for page result does not exist")
        if analysis.tender_id != resolved_tender_id:
            raise ValueError("source analysis belongs to another tender")
        if analysis.document_id != resolved_document_id:
            raise ValueError("source analysis belongs to another document")

        source_locator = f"page:{page_result.page_number}"
        source_text = _optional_text(page_result.extracted_plain_text)
        if source_text is None:
            source_text = _optional_text(page_result.extracted_markdown)
        if source_text is None:
            source_text = _optional_text(page_result.raw_response_text)

        source_contract_version = _optional_text(analysis.prompt_version)
        source_analysis_id = analysis.id
        source_page_result_id = page_result.id

    if source_text is None:
        raise ValueError("source artifact does not contain extractable text")

    return SourceEffectEvidenceArtifact(
        tender_id=resolved_tender_id,
        acting_document_id=resolved_document_id,
        document_page_id=resolved_page_id,
        page_number=page.page_number,
        source_method=resolved_source_method,
        source_artifact_key=resolved_artifact_key,
        source_locator=source_locator,
        source_text=source_text,
        source_contract_version=source_contract_version,
        source_analysis_id=source_analysis_id,
        source_page_result_id=source_page_result_id,
    )


def enumerate_source_effect_evidence_for_document(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    pages: Sequence[DocumentPage],
) -> SourceEffectEnumeratedArtifacts:
    page_by_id = {page.id: page for page in pages}
    active: list[SourceEffectEnumeratedArtifact] = []
    deselected: list[SourceEffectEnumeratedArtifact] = []

    vision_lineage_groups: dict[tuple[str, str], list[SourceEffectEnumeratedArtifact]] = {}

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
        source_text = _optional_text(page_result.extracted_plain_text)
        if source_text is None:
            source_text = _optional_text(page_result.extracted_markdown)
        if source_text is None:
            source_text = _optional_text(page_result.raw_response_text)
        if source_text is None:
            continue

        page = page_by_id.get(page_result.document_page_id)
        if page is None:
            continue

        artifact = SourceEffectEvidenceArtifact(
            tender_id=tender_id,
            acting_document_id=document_id,
            document_page_id=page_result.document_page_id,
            page_number=page_result.page_number,
            source_method="VISION",
            source_artifact_key=f"vision-page-result:{page_result.id}",
            source_locator=f"page:{page_result.page_number}",
            source_text=source_text,
            source_contract_version=_optional_text(analysis.prompt_version),
            source_analysis_id=analysis.id,
            source_page_result_id=page_result.id,
        )

        enumerated = SourceEffectEnumeratedArtifact(
            page_number=page_result.page_number,
            sort_key=f"vision:{page_result.page_number:04d}:{page_result.id}",
            artifact=artifact,
            analysis_created_at=analysis.created_at,
            page_result_created_at=page_result.created_at,
            page_result_updated_at=page_result.updated_at,
        )
        lineage_key = (page_result.document_page_id, analysis.input_fingerprint_sha256)
        vision_lineage_groups.setdefault(lineage_key, []).append(enumerated)

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

        text = _optional_text(ocr_row.text)
        if text is None:
            continue

        active.append(
            SourceEffectEnumeratedArtifact(
                page_number=page.page_number,
                sort_key=f"ocr:{page.page_number:04d}:{ocr_row.id}",
                artifact=SourceEffectEvidenceArtifact(
                    tender_id=tender_id,
                    acting_document_id=document_id,
                    document_page_id=page.id,
                    page_number=page.page_number,
                    source_method="OCR",
                    source_artifact_key=f"ocr-result:{ocr_row.id}",
                    source_locator=_ocr_source_locator(page.page_number, ocr_row.scope, ocr_row.region_id),
                    source_text=text,
                    source_contract_version=_optional_text(ocr_row.engine_version),
                ),
            )
        )

    for page in pages:
        text = _optional_text(page.text)
        if text is None:
            continue

        active.append(
            SourceEffectEnumeratedArtifact(
                page_number=page.page_number,
                sort_key=f"native:{page.page_number:04d}:{page.id}",
                artifact=SourceEffectEvidenceArtifact(
                    tender_id=tender_id,
                    acting_document_id=document_id,
                    document_page_id=page.id,
                    page_number=page.page_number,
                    source_method="NATIVE",
                    source_artifact_key=f"native-page:{page.id}",
                    source_locator=f"page:{page.page_number}",
                    source_text=text,
                    source_contract_version="NATIVE_TEXT_V1",
                ),
            )
        )

    active.sort(key=lambda item: (item.page_number, item.sort_key))
    deselected.sort(key=lambda item: (item.page_number, item.sort_key))
    return SourceEffectEnumeratedArtifacts(active=tuple(active), deselected=tuple(deselected))


def _parse_prefixed_id(value: str, *, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if value.startswith(prefix):
            suffix = value[len(prefix) :].strip()
            return suffix or None
    return None


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _datetime_or_min(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value


def _vision_artifact_lifecycle_sort_key(enumerated: SourceEffectEnumeratedArtifact) -> tuple:
    return (
        _datetime_or_min(enumerated.analysis_created_at),
        _datetime_or_min(enumerated.page_result_updated_at),
        _datetime_or_min(enumerated.page_result_created_at),
        enumerated.artifact.source_artifact_key,
    )


def _ocr_source_locator(page_number: int, scope: str, region_id: str | None) -> str:
    resolved_scope = _optional_text(scope) or "FULL_PAGE"
    locator = f"page:{page_number}|ocr_scope:{resolved_scope}"
    if region_id is not None:
        locator = f"{locator}|region:{region_id}"
    return locator


def build_source_effect_document_aliases(*, original_filename: str, source_relative_path: str | None) -> set[str]:
    aliases: set[str] = set()

    full_filename = _normalize_text(original_filename)
    stem = _normalize_text(Path(original_filename).stem)
    if full_filename:
        aliases.add(full_filename)
    if stem:
        aliases.add(stem)

    relative_path = _optional_text(source_relative_path)
    if relative_path is not None:
        rel_full = _normalize_text(relative_path)
        rel_stem = _normalize_text(Path(relative_path).stem)
        if rel_full:
            aliases.add(rel_full)
        if rel_stem:
            aliases.add(rel_stem)

    if any("BASES DE LICITACION" in alias for alias in aliases):
        aliases.add("BASES")
    if any("CONVOCATORIA" in alias for alias in aliases):
        aliases.add("CONVOCATORIA")

    for alias in tuple(aliases):
        annex = _extract_annex_alias(alias)
        if annex is not None:
            aliases.add(annex)

    return aliases


def _extract_annex_alias(value: str) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    if "ANEXO TECNICO" in normalized:
        return "ANEXO TECNICO"

    match = re.search(r"\bANEXO[\s\-_\.]*([A-Z0-9]+)\b", normalized)
    if match is None:
        return None

    marker = match.group(1).strip()
    if not marker:
        return None
    cleaned = "".join(ch for ch in marker if ch.isalnum() or ch in {"-", "."})
    if not cleaned:
        return None
    return f"ANEXO {cleaned}"


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).upper()
