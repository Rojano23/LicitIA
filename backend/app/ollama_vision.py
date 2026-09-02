from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import pymupdf as fitz
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.local_vision import OllamaVisionProvider
from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionAnalysisStatus,
    DocumentVisionPageResult,
    DocumentVisionPageResultStatus,
    Tender,
    TenderDocument,
)
from app.schemas import (
    VisionAssistAnalysisRead,
    VisionAssistAnalysisSummaryRead,
    VisionAssistAnalyzeRequest,
    VisionAssistLatestAnalysisRead,
    VisionAssistLatestItemCandidateRead,
    VisionAssistLatestPageSummaryRead,
    VisionAssistLatestStructureSummaryRead,
    VisionAssistLatestSummaryRead,
    VisionAssistPageResultRead,
    VisionAssistResultsRead,
    VisionProviderStatusRead,
)

VISION_ASSIST_MODEL_NAME = "qwen3-vl:4b-instruct"
VISION_STRUCTURE_SCOPE_PROMPT_VERSION = "vision-structure-scope-2026-09-01-005"
VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION = "vision-detail-transcription-2026-08-31-001"
VISION_TASK_STRUCTURE_SCOPE = "STRUCTURE_SCOPE"
VISION_TASK_DETAIL_TRANSCRIPTION = "DETAIL_TRANSCRIPTION"
DEFAULT_STRUCTURE_SCOPE_MAX_OUTPUT_TOKENS = 600
DEFAULT_DETAIL_TRANSCRIPTION_MAX_OUTPUT_TOKENS = 1000
VISION_ASSIST_IMAGE_ZOOM = 2.0
VISION_ASSIST_MIN_IMAGE_ZOOM = 1.0
VISION_ASSIST_IMAGE_ZOOM_STEP = 0.25
VISION_ASSIST_MAX_IMAGE_BYTES = 8_388_608
VISION_ASSIST_MAX_IMAGE_DIMENSION_PX = 2800
VISION_ASSIST_MAX_REQUEST_PAGES = 8

WARNING_MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
WARNING_TIMEOUT = "TIMEOUT"
WARNING_HTTP_ERROR = "HTTP_ERROR"
WARNING_EMPTY_CONTENT = "EMPTY_CONTENT"
WARNING_INVALID_JSON = "INVALID_JSON"
WARNING_OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
WARNING_THINKING_IGNORED = "THINKING_CONTENT_IGNORED"
WARNING_CRITICAL_DISAGREEMENT = "CRITICAL_FIELD_DISAGREEMENT_REVIEW_REQUIRED"
WARNING_PREVIOUS_ITEM_FILLED_FROM_CONTEXT = "PREVIOUS_ITEM_FILLED_FROM_CONTEXT"
WARNING_NEW_ITEM_DERIVED_FROM_ITEM_START = "NEW_ITEM_DERIVED_FROM_ITEM_START"
WARNING_OPEN_ITEM_DERIVED_FROM_LAST_NEW_ITEM = "OPEN_ITEM_DERIVED_FROM_LAST_NEW_ITEM"
WARNING_OPEN_ITEM_DERIVED_FROM_PREVIOUS_CONTEXT = "OPEN_ITEM_DERIVED_FROM_PREVIOUS_CONTEXT"
WARNING_OPEN_ITEM_DERIVED_FROM_SINGLE_REGION = "OPEN_ITEM_DERIVED_FROM_SINGLE_REGION"
WARNING_REGION_ITEM_FILLED_FROM_PREVIOUS_CONTEXT = "REGION_ITEM_FILLED_FROM_PREVIOUS_CONTEXT"
WARNING_STRUCTURE_INCONSISTENT = "STRUCTURE_INCONSISTENT"
WARNING_STRUCTURE_CONTINUATION_UNRESOLVED = "STRUCTURE_CONTINUATION_UNRESOLVED"
WARNING_CONTINUITY_CONTEXT_LOST_AFTER_PAGE_FAILURE = "CONTINUITY_CONTEXT_LOST_AFTER_PAGE_FAILURE"
WARNING_SEGMENT_START_SUPPRESSED_BY_CONTINUITY = "SEGMENT_START_SUPPRESSED_BY_CONTINUITY"


class VisionAssistModelItemSegment(BaseModel):
    item_number: str | None = None
    starts_on_this_page: bool = False
    has_service: bool = False
    has_supply: bool = False
    has_deliverable: bool = False
    anchor_raw_text: str | None = None
    review_required: bool = True


class VisionAssistModelNewItem(BaseModel):
    item_number: str
    concept_raw_text: str | None = None
    review_required: bool = True


class VisionAssistModelPageResponse(BaseModel):
    page_number: int
    continues_previous_item: bool = False
    previous_item_number: str | None = None
    item_segments: list[VisionAssistModelItemSegment] = Field(default_factory=list, max_length=4)
    new_items: list[VisionAssistModelNewItem] = Field(default_factory=list)
    open_item_at_page_end: str | None = None
    uncertainties: list[str] = Field(default_factory=list)


class VisionAssistModelDetailRawLine(BaseModel):
    raw_visible_text: str
    uncertain: bool = False
    uncertain_characters: list[str] = Field(default_factory=list)


class VisionAssistModelDetailTranscriptionResponse(BaseModel):
    source_page: int
    raw_lines: list[VisionAssistModelDetailRawLine] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


@dataclass
class RenderedVisionPage:
    page_number: int
    document_page_id: str
    image_bytes: bytes
    image_sha256: str
    width_px: int
    height_px: int
    image_bytes_size: int
    render_time_ms: int
    render_zoom: float
    warnings: list[str]


class OllamaProviderProbeError(RuntimeError):
    pass


class OllamaVisionAssistClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.licitia_ollama_base_url.rstrip("/")
        self.model_name = (self.settings.licitia_ollama_vision_model or VISION_ASSIST_MODEL_NAME).strip() or VISION_ASSIST_MODEL_NAME

    def _tags_url(self) -> str:
        return f"{self.base_url}/api/tags"

    def _chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    def probe(self) -> VisionProviderStatusRead:
        local_provider = OllamaVisionProvider(self.settings)
        runtime = local_provider.runtime_snapshot()
        model_available = self.model_name in runtime.models_available
        selected_model = self.model_name if model_available else None
        provider_status = "AVAILABLE" if runtime.runtime_available and model_available else "UNAVAILABLE"
        status_reason = runtime.provider_status_reason
        if runtime.runtime_available and not model_available:
            status_reason = f"ollama runtime detected but model {self.model_name} is missing"

        return VisionProviderStatusRead(
            provider_id="OLLAMA_VISION",
            provider_name="Ollama Vision Assist",
            provider_status=provider_status,
            provider_status_reason=status_reason,
            runtime_available=runtime.runtime_available,
            configured_model=self.model_name,
            selected_model=selected_model,
            model_available=model_available,
            models_available=runtime.models_available,
            base_url=self.base_url,
        )

    def ensure_available(self) -> VisionProviderStatusRead:
        probe = self.probe()
        if probe.provider_status != "AVAILABLE":
            reason = probe.provider_status_reason or "configured vision model unavailable"
            raise OllamaProviderProbeError(f"{WARNING_MODEL_UNAVAILABLE}: {reason}")
        return probe

    def render_document_pages(self, document: TenderDocument, page_numbers: list[int], *, zoom: float = VISION_ASSIST_IMAGE_ZOOM) -> list[RenderedVisionPage]:
        resolved_path = resolve_document_path(document.stored_relative_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Document file not found: {resolved_path}")

        pdf_document = fitz.open(str(resolved_path))
        try:
            rendered_pages: list[RenderedVisionPage] = []
            for page_number in page_numbers:
                if page_number < 1 or page_number > pdf_document.page_count:
                    raise LookupError(f"Requested page {page_number} is outside the document page range")
                page = pdf_document[page_number - 1]
                render_started_at = time.perf_counter()
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                image_bytes = pixmap.tobytes("png")
                rendered_pages.append(
                    RenderedVisionPage(
                        page_number=page_number,
                        document_page_id="",
                        image_bytes=image_bytes,
                        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
                        width_px=pixmap.width,
                        height_px=pixmap.height,
                        image_bytes_size=len(image_bytes),
                        render_time_ms=int((time.perf_counter() - render_started_at) * 1000),
                        render_zoom=zoom,
                        warnings=[],
                    )
                )
            return rendered_pages
        finally:
            pdf_document.close()

    @staticmethod
    def _build_structure_scope_prompt(page_number: int, mode: str, previous_page_context: dict[str, Any] | None) -> str:
        continuity_context = json.dumps(previous_page_context or {}, ensure_ascii=False, separators=(",", ":"))
        return (
            "You are Vision Assist for a local procurement workflow. "
            "Task type: STRUCTURE_SCOPE. Extract contractual technical scope structure for this page. "
            "Read ONLY visible content from the page image. Preserve contractual wording and do not summarize details away. "
            "Return only short visible anchors where useful; this is not full-page transcription. "
            "Never invent missing information. Use null when uncertain. "
            "Do not infer values from neighboring columns or nearby rows without visual support on this page. "
            "The page may begin as a continuation of a previous partida. "
            "Return item ownership segments, not semantic rows. "
            "An item segment means a contiguous area of the page belonging to one Tender Item or PARTIDA. "
            "An item segment is not an equipment row, one activity, one bullet, or one table row. "
            "If the page starts by continuing the previous item and later shows a new numbered PARTIDA, both item segments must be represented in the same response. "
            "If several consecutive rows belong to the same item area, return one item segment for that contiguous area. "
            "Rows with supply signals such as MARCA, MODELO, PIEZA/PIEZAS, suministro, module or equipment descriptions should set has_supply=true on that item segment, not become separate entries. "
            "anchor_raw_text must contain at most approximately 8 to 15 visible words. Do not transcribe the section body. "
            "Return only valid JSON and no markdown fences. "
            f"Page number: {page_number}. Mode: {mode}. "
            f"Previous continuity context: {continuity_context}. "
            "Required JSON shape: {"
            '"page_number": <int>, '
            '"continues_previous_item": <bool>, '
            '"previous_item_number": <string|null>, '
            '"item_segments": [{"item_number": "...", "starts_on_this_page": <bool>, '
            '"has_service": <bool>, "has_supply": <bool>, "has_deliverable": <bool>, '
            '"anchor_raw_text": "...", "review_required": <bool>}], '
            '"new_items": [{"item_number": "...", "concept_raw_text": "...", "review_required": <bool>}], '
            '"open_item_at_page_end": <string|null>, '
            '"uncertainties": ["..."]'
            " }"
        )

    @staticmethod
    def _build_prompt(page_number: int, mode: str, previous_page_context: dict[str, Any] | None) -> str:
        return OllamaVisionAssistClient._build_structure_scope_prompt(page_number, mode, previous_page_context)

    @staticmethod
    def _build_detail_transcription_prompt(page_number: int, mode: str, region_hint: str | None) -> str:
        return (
            "You are Vision Assist for a local procurement workflow. "
            "Task type: DETAIL_TRANSCRIPTION. Perform faithful transcription only for the bounded relevant region. "
            "Do not redo global page reasoning. "
            "Preserve exact visible wording. Never invent missing characters. "
            "If a character is uncertain, keep raw_visible_text and mark uncertainty. "
            "Do not summarize. Return only valid JSON and no markdown fences. "
            f"Source page: {page_number}. Mode: {mode}. Region hint: {region_hint or 'UNSPECIFIED_RELEVANT_REGION'}. "
            "Required JSON shape: {"
            '"source_page": <int>, '
            '"raw_lines": [{"raw_visible_text": "...", "uncertain": <bool>, "uncertain_characters": ["..."]}], '
            '"uncertainties": ["..."]'
            " }"
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return VisionAssistModelPageResponse.model_json_schema()

    @staticmethod
    def _detail_response_schema() -> dict[str, Any]:
        return VisionAssistModelDetailTranscriptionResponse.model_json_schema()

    @staticmethod
    def _extract_response_metadata(response_payload: dict[str, Any]) -> dict[str, Any]:
        message = response_payload.get("message") if isinstance(response_payload, dict) else {}
        content = None
        thinking = None
        if isinstance(message, dict):
            content = message.get("content")
            thinking = message.get("thinking")
        if content is None:
            content = response_payload.get("response") if isinstance(response_payload, dict) else None
        return {
            "content": content,
            "has_thinking": bool(thinking),
            "done_reason": response_payload.get("done_reason") if isinstance(response_payload, dict) else None,
            "prompt_eval_count": response_payload.get("prompt_eval_count") if isinstance(response_payload, dict) else None,
            "eval_count": response_payload.get("eval_count") if isinstance(response_payload, dict) else None,
        }

    @staticmethod
    def _parse_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _execute_task(
        self,
        *,
        task_type: str,
        prompt_version: str,
        prompt: str,
        schema: dict[str, Any],
        image_bytes: bytes,
        max_output_tokens: int,
    ) -> tuple[str, dict[str, Any] | None, int, int | None, list[str], str | None, str | None, str | None]:
        payload = {
            "model": self.model_name,
            "think": False,
            "stream": False,
            "format": schema,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
            "options": {
                "temperature": 0,
                "num_predict": int(max_output_tokens),
            },
        }
        request = urllib.request.Request(
            self._chat_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        started_at = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.settings.licitia_ollama_timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
                http_status = int(getattr(response, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            processing_time_ms = int((time.perf_counter() - started_at) * 1000)
            code = int(exc.code)
            detail = f"{WARNING_HTTP_ERROR}:{code}"
            return "FAILED", None, processing_time_ms, code, [detail], None, None, None
        except TimeoutError as exc:
            processing_time_ms = int((time.perf_counter() - started_at) * 1000)
            return "FAILED", None, processing_time_ms, None, [f"{WARNING_TIMEOUT}:{exc}"], None, None, None
        except (urllib.error.URLError, ConnectionError) as exc:
            processing_time_ms = int((time.perf_counter() - started_at) * 1000)
            return "FAILED", None, processing_time_ms, None, [f"CONNECTION_ERROR:{exc}"], None, None, None

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        metadata = self._extract_response_metadata(response_payload)
        content = metadata.get("content")
        has_thinking = bool(metadata.get("has_thinking"))
        done_reason = metadata.get("done_reason")
        prompt_eval_count = self._parse_int_or_none(metadata.get("prompt_eval_count"))
        eval_count = self._parse_int_or_none(metadata.get("eval_count"))

        raw_response_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if not isinstance(content, str) or not content.strip():
            warnings = [WARNING_EMPTY_CONTENT]
            if has_thinking:
                warnings.append(WARNING_THINKING_IGNORED)
            if done_reason is not None:
                warnings.append(f"DONE_REASON:{done_reason}")
            return "FAILED", None, processing_time_ms, http_status, warnings, None, None, raw_response_text

        malformed_json_retry_limit = min(max(int(self.settings.licitia_vision_retry_malformed_json or 0), 0), 1)
        retry_count = 0
        retry_warnings: list[str] = []
        while True:
            try:
                parsed_json = self._parse_response_text(raw_response_text)
                if task_type == VISION_TASK_STRUCTURE_SCOPE:
                    structured_json = self._normalize_structured_json(
                        page_number=int(parsed_json.get("page_number") or 0) or 1,
                        parsed_json=parsed_json,
                        previous_page_context=None,
                    )
                else:
                    structured_json = self._normalize_detail_structured_json(parsed_json)

                warnings = list(structured_json.get("uncertainties", []))
                warnings.extend(structured_json.get("_normalization_warnings", []))
                warnings.extend(retry_warnings)
                warnings.append(f"HTTP_STATUS:{http_status}")
                if done_reason is not None:
                    warnings.append(f"DONE_REASON:{done_reason}")
                if has_thinking:
                    warnings.append(WARNING_THINKING_IGNORED)

                structured_json["_provider_response_meta"] = {
                    "task_type": task_type,
                    "prompt_version": prompt_version,
                    "done_reason": done_reason,
                    "prompt_eval_count": prompt_eval_count,
                    "eval_count": eval_count,
                    "max_output_tokens": max_output_tokens,
                }
                return "COMPLETED", structured_json, processing_time_ms, http_status, warnings, None, None, raw_response_text
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                if done_reason == "length":
                    warnings = [WARNING_OUTPUT_TRUNCATED, f"DONE_REASON:{done_reason}"]
                    if has_thinking:
                        warnings.append(WARNING_THINKING_IGNORED)
                    return "FAILED", None, processing_time_ms, http_status, warnings, None, None, raw_response_text

                if retry_count < malformed_json_retry_limit:
                    retry_count += 1
                    retry_warnings.append(f"MALFORMED_JSON_RETRY:{retry_count}/{malformed_json_retry_limit}")
                    try:
                        with urllib.request.urlopen(request, timeout=self.settings.licitia_ollama_timeout_seconds) as retry_response:
                            response_payload = json.loads(retry_response.read().decode("utf-8"))
                            http_status = int(getattr(retry_response, "status", 200) or 200)
                        metadata = self._extract_response_metadata(response_payload)
                        content = metadata.get("content")
                        done_reason = metadata.get("done_reason")
                        has_thinking = bool(metadata.get("has_thinking"))
                        raw_response_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                        continue
                    except urllib.error.HTTPError as retry_http_error:
                        return "FAILED", None, processing_time_ms, int(retry_http_error.code), [f"{WARNING_HTTP_ERROR}:{retry_http_error.code}", *retry_warnings], None, None, raw_response_text
                    except TimeoutError as retry_timeout_error:
                        return "FAILED", None, processing_time_ms, None, [f"{WARNING_TIMEOUT}:{retry_timeout_error}", *retry_warnings], None, None, raw_response_text
                    except (urllib.error.URLError, ConnectionError) as retry_transport_error:
                        return "FAILED", None, processing_time_ms, None, [f"CONNECTION_ERROR:{retry_transport_error}", *retry_warnings], None, None, raw_response_text

                return "INVALID_JSON", None, processing_time_ms, http_status, [WARNING_INVALID_JSON, str(exc), *retry_warnings], None, None, raw_response_text

    def analyze_page(
        self,
        *,
        page_number: int,
        image_bytes: bytes,
        mode: str,
        previous_page_context: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any] | None, int, int | None, list[str], str | None, str | None, str | None]:
        return self.analyze_structure_scope_page(
            page_number=page_number,
            image_bytes=image_bytes,
            mode=mode,
            previous_page_context=previous_page_context,
        )

    def analyze_structure_scope_page(
        self,
        *,
        page_number: int,
        image_bytes: bytes,
        mode: str,
        previous_page_context: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any] | None, int, int | None, list[str], str | None, str | None, str | None]:
        prompt = self._build_structure_scope_prompt(page_number, mode, previous_page_context)
        max_tokens = max(int(self.settings.licitia_vision_structure_scope_max_output_tokens or DEFAULT_STRUCTURE_SCOPE_MAX_OUTPUT_TOKENS), 128)
        status, structured_json, processing_time_ms, http_status, warnings, extracted_markdown, extracted_plain_text, raw_response_text = self._execute_task(
            task_type=VISION_TASK_STRUCTURE_SCOPE,
            prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
            prompt=prompt,
            schema=self._response_schema(),
            image_bytes=image_bytes,
            max_output_tokens=max_tokens,
        )
        if structured_json is not None:
            provider_meta = structured_json.get("_provider_response_meta")
            try:
                structured_json = self._normalize_structured_json(
                    page_number=page_number,
                    parsed_json=structured_json,
                    previous_page_context=previous_page_context,
                )
            except ValidationError as exc:
                warnings.extend([WARNING_INVALID_JSON, f"SCHEMA_VALIDATION_ERROR:{exc}"])
                return "INVALID_JSON", None, processing_time_ms, http_status, warnings, extracted_markdown, extracted_plain_text, raw_response_text
            warnings.extend(str(item) for item in (structured_json.get("_normalization_warnings") or []))
            if isinstance(provider_meta, dict):
                structured_json["_provider_response_meta"] = provider_meta
        return status, structured_json, processing_time_ms, http_status, warnings, extracted_markdown, extracted_plain_text, raw_response_text

    def analyze_detail_transcription_page(
        self,
        *,
        page_number: int,
        image_bytes: bytes,
        mode: str,
        region_hint: str | None,
    ) -> tuple[str, dict[str, Any] | None, int, int | None, list[str], str | None, str | None, str | None]:
        prompt = self._build_detail_transcription_prompt(page_number, mode, region_hint)
        max_tokens = max(int(self.settings.licitia_vision_detail_transcription_max_output_tokens or DEFAULT_DETAIL_TRANSCRIPTION_MAX_OUTPUT_TOKENS), 256)
        return self._execute_task(
            task_type=VISION_TASK_DETAIL_TRANSCRIPTION,
            prompt_version=VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION,
            prompt=prompt,
            schema=self._detail_response_schema(),
            image_bytes=image_bytes,
            max_output_tokens=max_tokens,
        )

    @staticmethod
    def _parse_response_text(raw_response_text: str) -> dict[str, Any]:
        text = (raw_response_text or "").strip()
        if not text:
            raise ValueError("Vision Assist model returned an empty response")
        if text.startswith("```"):
            text = text.strip("`")
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Vision Assist response is not a JSON object")
        return parsed

    @staticmethod
    def _normalize_structured_json(
        *,
        page_number: int,
        parsed_json: dict[str, Any],
        previous_page_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized_json = _build_page_response_from_raw(page_number, parsed_json)
        validated = VisionAssistModelPageResponse.model_validate(normalized_json)
        structured_json = validated.model_dump(mode="json")
        normalization_warnings: list[str] = []
        normalized_previous_page_context = _normalize_previous_page_context(previous_page_context)

        _normalize_structure_item_numbers(structured_json)
        _suppress_continuation_segment_starts(structured_json, normalized_previous_page_context, normalization_warnings)
        _derive_new_items_from_started_segments(structured_json, normalization_warnings)
        _apply_segment_ownership_from_context(structured_json, normalized_previous_page_context, normalization_warnings)
        _apply_structure_consistency_rules(structured_json, normalized_previous_page_context, normalization_warnings)

        for item_segment in structured_json.get("item_segments", []):
            anchor_raw_text = (item_segment.get("anchor_raw_text") or "").strip()
            if anchor_raw_text:
                words = [word for word in anchor_raw_text.split() if word]
                if len(words) > 15:
                    anchor_raw_text = " ".join(words[:15])
                    normalization_warnings.append("ANCHOR_TRUNCATED_TO_MAX_WORDS")
            item_segment["anchor_raw_text"] = anchor_raw_text or None
            if item_segment.get("review_required") is None:
                item_segment["review_required"] = True

        if normalization_warnings:
            structured_json["_normalization_warnings"] = sorted(set(normalization_warnings))

        structured_json["_continuity_context_used"] = normalized_previous_page_context
        return structured_json

    @staticmethod
    def _normalize_detail_structured_json(parsed_json: dict[str, Any]) -> dict[str, Any]:
        validated = VisionAssistModelDetailTranscriptionResponse.model_validate(parsed_json)
        structured_json = validated.model_dump(mode="json")
        normalization_warnings: list[str] = []
        cleaned_lines: list[dict[str, Any]] = []
        for line in structured_json.get("raw_lines", []):
            raw_visible_text = (line.get("raw_visible_text") or "").strip()
            if not raw_visible_text:
                normalization_warnings.append("DETAIL_LINE_WITHOUT_RAW_VISIBLE_TEXT")
                continue
            cleaned_lines.append(
                {
                    "raw_visible_text": raw_visible_text,
                    "uncertain": bool(line.get("uncertain")),
                    "uncertain_characters": [str(item) for item in (line.get("uncertain_characters") or []) if str(item)],
                }
            )
        structured_json["raw_lines"] = cleaned_lines
        if normalization_warnings:
            structured_json["_normalization_warnings"] = sorted(set(normalization_warnings))
        return structured_json


def _extract_previous_page_context(structured_json: dict[str, Any]) -> dict[str, Any] | None:
    item_number = structured_json.get("open_item_at_page_end")
    concept = None

    if not item_number and not concept:
        new_items = structured_json.get("new_items") or []
        if new_items:
            last_item = new_items[-1]
            item_number = item_number or last_item.get("item_number")
            concept = concept or last_item.get("concept_raw_text")

    if not item_number and not concept:
        return None

    return {
        "open_item_number": _normalize_item_number(item_number),
        "open_item_concept": str(concept) if concept is not None else None,
        "open_section": "ALCANCES",
    }


class VisionAssistService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.client = OllamaVisionAssistClient(self.settings)

    def provider_status(self) -> VisionProviderStatusRead:
        return self.client.probe()

    def analyze_document(self, tender_id: str, document_id: str, request: VisionAssistAnalyzeRequest) -> VisionAssistAnalysisRead:
        tender = self.db.get(Tender, tender_id)
        if tender is None:
            raise ValueError("Tender not found")

        document = self.db.get(TenderDocument, document_id)
        if document is None or document.tender_id != tender_id:
            raise LookupError("Tender document not found")

        normalized_page_numbers = normalize_page_numbers(request.page_numbers)
        if len(normalized_page_numbers) > self.settings.licitia_vision_max_pages:
            raise ValueError(f"At most {self.settings.licitia_vision_max_pages} pages can be analyzed in one request")

        rendered_pages = self._render_requested_pages(document, normalized_page_numbers)
        input_fingerprint = _build_input_fingerprint(
            tender_id=tender_id,
            document_id=document_id,
            model_name=self.client.model_name,
            prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
            mode=request.mode,
            rendered_pages=rendered_pages,
            task_type=VISION_TASK_STRUCTURE_SCOPE,
            task_region_id=None,
        )

        existing = self.db.scalar(
            select(DocumentVisionAnalysis).where(
                DocumentVisionAnalysis.document_id == document_id,
                DocumentVisionAnalysis.model_name == self.client.model_name,
                DocumentVisionAnalysis.prompt_version == VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                DocumentVisionAnalysis.input_fingerprint_sha256 == input_fingerprint,
            )
        )
        if existing is not None and existing.status == DocumentVisionAnalysisStatus.COMPLETED.value:
            return self._serialize_analysis(existing, self.client.probe())

        provider = self.client.ensure_available()
        if existing is not None:
            analysis = existing
            analysis.status = DocumentVisionAnalysisStatus.RUNNING.value
            analysis.mode = request.mode
            analysis.model_name = provider.configured_model
            analysis.analyzed_at = datetime.now(timezone.utc)
            self.db.flush()
        else:
            analysis = DocumentVisionAnalysis(
                tender_id=tender_id,
                document_id=document_id,
                status=DocumentVisionAnalysisStatus.RUNNING.value,
                mode=request.mode,
                model_name=provider.configured_model,
                prompt_version=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
                input_fingerprint_sha256=input_fingerprint,
                analyzed_at=datetime.now(timezone.utc),
            )
            self.db.add(analysis)
            self.db.flush()

        completed_count = 0
        failure_count = 0
        previous_page_context: dict[str, Any] | None = None
        continuity_context_quality = "VALID"
        for rendered_page in rendered_pages:
            effective_previous_page_context = previous_page_context if continuity_context_quality == "VALID" else None
            status, structured_json, processing_time_ms, http_status, warnings, extracted_markdown, extracted_plain_text, raw_response_text = self.client.analyze_structure_scope_page(
                page_number=rendered_page.page_number,
                image_bytes=rendered_page.image_bytes,
                mode=request.mode,
                previous_page_context=effective_previous_page_context,
            )

            continuity_context_was_lost = continuity_context_quality != "VALID"

            needs_detail_transcription = False
            if status == DocumentVisionPageResultStatus.COMPLETED.value and structured_json is not None:
                needs_detail_transcription = _should_run_detail_transcription(structured_json)
                if needs_detail_transcription:
                    detail_region_hint = _build_detail_region_hint(structured_json)
                    (
                        detail_status,
                        detail_structured_json,
                        detail_processing_time_ms,
                        detail_http_status,
                        detail_warnings,
                        _,
                        _,
                        _detail_raw_response_text,
                    ) = self.client.analyze_detail_transcription_page(
                        page_number=rendered_page.page_number,
                        image_bytes=rendered_page.image_bytes,
                        mode=request.mode,
                        region_hint=detail_region_hint,
                    )
                    if detail_structured_json is not None:
                        detail_task_fingerprint = _build_task_fingerprint(
                            task_type=VISION_TASK_DETAIL_TRANSCRIPTION,
                            model_name=self.client.model_name,
                            prompt_version=VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION,
                            page_number=rendered_page.page_number,
                            image_sha256=rendered_page.image_sha256,
                            task_region_id=detail_region_hint,
                        )
                        _merge_detail_transcription(
                            structured_json=structured_json,
                            detail_structured_json=detail_structured_json,
                            detail_task_fingerprint=detail_task_fingerprint,
                            detail_region_hint=detail_region_hint,
                        )
                    warnings.extend(f"DETAIL:{warning}" for warning in detail_warnings)
                    if detail_status != DocumentVisionPageResultStatus.COMPLETED.value:
                        status = DocumentVisionPageResultStatus.PARTIAL.value
                    if structured_json is not None:
                        runtime_detail = {
                            "task_type": VISION_TASK_DETAIL_TRANSCRIPTION,
                            "region_hint": detail_region_hint,
                            "ollama_inference_ms": detail_processing_time_ms,
                            "http_status": detail_http_status,
                            "status": detail_status,
                        }
                        structured_json["_detail_runtime"] = runtime_detail

            if status == DocumentVisionPageResultStatus.COMPLETED.value:
                completed_count += 1
            elif status in {
                DocumentVisionPageResultStatus.INVALID_JSON.value,
                DocumentVisionPageResultStatus.FAILED.value,
                DocumentVisionPageResultStatus.PARTIAL.value,
            }:
                failure_count += 1

            page_warnings = list(warnings)
            if continuity_context_was_lost:
                page_warnings.append(WARNING_CONTINUITY_CONTEXT_LOST_AFTER_PAGE_FAILURE)
            page_warnings.append(f"RENDER_DIMENSIONS:{rendered_page.width_px}x{rendered_page.height_px}")
            page_warnings.append(f"RENDER_IMAGE_BYTES:{rendered_page.image_bytes_size}")
            page_warnings.append(f"RENDER_MS:{rendered_page.render_time_ms}")
            page_warnings.append(f"RENDER_ZOOM:{rendered_page.render_zoom}")
            if http_status is not None:
                page_warnings.append(f"HTTP_STATUS:{http_status}")
            page_warnings.extend(rendered_page.warnings)

            if structured_json is not None:
                structured_json["_vision_runtime"] = {
                    "task_type": VISION_TASK_STRUCTURE_SCOPE,
                    "page_number": rendered_page.page_number,
                    "render_ms": rendered_page.render_time_ms,
                    "image_dimensions": {
                        "width": rendered_page.width_px,
                        "height": rendered_page.height_px,
                    },
                    "image_bytes": rendered_page.image_bytes_size,
                    "render_zoom": rendered_page.render_zoom,
                    "ollama_inference_ms": processing_time_ms,
                    "http_status": http_status,
                    "schema_valid": status == DocumentVisionPageResultStatus.COMPLETED.value,
                }
                provider_meta = structured_json.get("_provider_response_meta")
                if isinstance(provider_meta, dict):
                    structured_json["_vision_runtime"]["done_reason"] = provider_meta.get("done_reason")
                    structured_json["_vision_runtime"]["prompt_eval_count"] = provider_meta.get("prompt_eval_count")
                    structured_json["_vision_runtime"]["eval_count"] = provider_meta.get("eval_count")
                    structured_json["_vision_runtime"]["max_output_tokens"] = provider_meta.get("max_output_tokens")
                if continuity_context_was_lost:
                    _mark_item_segments_for_review(structured_json)
                    structured_json["_continuity_state_quality"] = "UNKNOWN"
                else:
                    structured_json["_continuity_state_quality"] = "VALID"
                previous_page_context = _extract_previous_page_context(structured_json)
                continuity_context_quality = "VALID"
            else:
                previous_page_context = None
                continuity_context_quality = "UNKNOWN"

            page_result = self._upsert_page_result(
                analysis_id=analysis.id,
                document_page_id=rendered_page.document_page_id,
                page_number=rendered_page.page_number,
                image_sha256=rendered_page.image_sha256,
                status=status,
                structured_json=structured_json,
                warnings=page_warnings,
                processing_time_ms=processing_time_ms,
                raw_response_text=raw_response_text,
                extracted_markdown=extracted_markdown,
                extracted_plain_text=extracted_plain_text,
            )

        if failure_count == 0:
            analysis.status = DocumentVisionAnalysisStatus.COMPLETED.value
        elif completed_count > 0:
            analysis.status = DocumentVisionAnalysisStatus.PARTIAL.value
        else:
            analysis.status = DocumentVisionAnalysisStatus.FAILED.value
        analysis.analyzed_at = datetime.now(timezone.utc)
        self.db.flush()
        return self._serialize_analysis(analysis, provider)

    def list_document_results(self, tender_id: str, document_id: str) -> VisionAssistResultsRead:
        tender = self.db.get(Tender, tender_id)
        if tender is None:
            raise ValueError("Tender not found")
        document = self.db.get(TenderDocument, document_id)
        if document is None or document.tender_id != tender_id:
            raise LookupError("Tender document not found")

        provider = self.client.probe()
        analyses = self.db.execute(
            select(DocumentVisionAnalysis).where(
                DocumentVisionAnalysis.tender_id == tender_id,
                DocumentVisionAnalysis.document_id == document_id,
            ).order_by(DocumentVisionAnalysis.created_at.asc())
        ).scalars().all()
        serialized = [self._serialize_analysis(analysis, provider) for analysis in analyses]
        summary = VisionAssistAnalysisSummaryRead(
            analysis_count=len(serialized),
            page_count=sum(len(item.page_results) for item in serialized),
            completed_page_count=sum(1 for item in serialized for page in item.page_results if page.status == DocumentVisionPageResultStatus.COMPLETED.value),
            failed_page_count=sum(1 for item in serialized for page in item.page_results if page.status == DocumentVisionPageResultStatus.FAILED.value),
            invalid_json_page_count=sum(1 for item in serialized for page in item.page_results if page.status == DocumentVisionPageResultStatus.INVALID_JSON.value),
            warning_count=sum(len(page.warnings) for item in serialized for page in item.page_results),
        )
        return VisionAssistResultsRead(
            tender_id=tender_id,
            document_id=document_id,
            source_filename=document.original_filename,
            summary=summary,
            analyses=serialized,
        )

    def get_page_result(self, tender_id: str, document_id: str, page_number: int) -> VisionAssistPageResultRead:
        tender = self.db.get(Tender, tender_id)
        if tender is None:
            raise ValueError("Tender not found")
        document = self.db.get(TenderDocument, document_id)
        if document is None or document.tender_id != tender_id:
            raise LookupError("Tender document not found")
        result = self.db.scalar(
            select(DocumentVisionPageResult)
            .join(DocumentVisionAnalysis, DocumentVisionAnalysis.id == DocumentVisionPageResult.analysis_id)
            .where(
                DocumentVisionAnalysis.tender_id == tender_id,
                DocumentVisionAnalysis.document_id == document_id,
                DocumentVisionPageResult.page_number == page_number,
            )
            .order_by(DocumentVisionPageResult.created_at.desc())
        )
        if result is None:
            raise LookupError("Vision page result not found")
        return self._serialize_page_result(result)

    def get_latest_summary(self, tender_id: str, document_id: str) -> VisionAssistLatestSummaryRead:
        tender = self.db.get(Tender, tender_id)
        if tender is None:
            raise ValueError("Tender not found")
        document = self.db.get(TenderDocument, document_id)
        if document is None or document.tender_id != tender_id:
            raise LookupError("Tender document not found")

        latest_analysis = self.db.scalar(
            select(DocumentVisionAnalysis)
            .where(
                DocumentVisionAnalysis.tender_id == tender_id,
                DocumentVisionAnalysis.document_id == document_id,
                DocumentVisionAnalysis.prompt_version == VISION_STRUCTURE_SCOPE_PROMPT_VERSION,
            )
            .order_by(DocumentVisionAnalysis.created_at.desc())
        )

        if latest_analysis is None:
            return VisionAssistLatestSummaryRead(
                tender_id=tender_id,
                document_id=document_id,
                source_filename=document.original_filename,
                latest_analysis=None,
                item_candidates=[],
                page_summaries=[],
            )

        page_results = self.db.execute(
            select(DocumentVisionPageResult)
            .where(DocumentVisionPageResult.analysis_id == latest_analysis.id)
            .order_by(DocumentVisionPageResult.page_number.asc(), DocumentVisionPageResult.created_at.asc())
        ).scalars().all()

        page_summaries = self._build_latest_page_summaries(page_results)
        item_candidates = self._build_latest_item_candidates(page_results)

        detail_partial_pages = [
            page_summary.page_number
            for page_summary in page_summaries
            if page_summary.detail_status is not None and page_summary.detail_status != DocumentVisionPageResultStatus.COMPLETED.value
        ]
        valid_structure_pages = sum(1 for page_summary in page_summaries if page_summary.structure_status == "VALID")
        continuity_values = [
            (result.structured_json or {}).get("_continuity_state_quality")
            for result in page_results
            if isinstance(result.structured_json, dict)
        ]
        structure_continuity_valid = bool(continuity_values) and all(value == "VALID" for value in continuity_values)

        latest_analysis_summary = VisionAssistLatestAnalysisRead(
            analysis_id=latest_analysis.id,
            status=latest_analysis.status,
            model_name=latest_analysis.model_name,
            prompt_version=latest_analysis.prompt_version,
            analyzed_at=latest_analysis.analyzed_at,
            structure_summary=VisionAssistLatestStructureSummaryRead(
                page_count=len(page_results),
                valid_structure_pages=valid_structure_pages,
                structure_continuity_valid=structure_continuity_valid,
                detail_partial_pages=detail_partial_pages,
            ),
        )

        return VisionAssistLatestSummaryRead(
            tender_id=tender_id,
            document_id=document_id,
            source_filename=document.original_filename,
            latest_analysis=latest_analysis_summary,
            item_candidates=item_candidates,
            page_summaries=page_summaries,
        )

    def _render_requested_pages(self, document: TenderDocument, page_numbers: list[int]) -> list[RenderedVisionPage]:
        resolved_path = resolve_document_path(document.stored_relative_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Document file not found: {resolved_path}")

        pdf_document = fitz.open(str(resolved_path))
        try:
            document_pages_by_number = {
                page.page_number: page
                for page in self.db.execute(
                    select(DocumentPage).where(
                        DocumentPage.document_id == document.id,
                        DocumentPage.page_number.in_(page_numbers),
                    )
                ).scalars().all()
            }
            missing_pages = [page_number for page_number in page_numbers if page_number not in document_pages_by_number]
            if missing_pages:
                raise LookupError(f"Missing document pages: {', '.join(str(page) for page in missing_pages)}")

            rendered_pages: list[RenderedVisionPage] = []
            target_zoom = max(float(self.settings.licitia_vision_render_zoom or VISION_ASSIST_IMAGE_ZOOM), 0.5)
            min_zoom = max(float(self.settings.licitia_vision_min_render_zoom or VISION_ASSIST_MIN_IMAGE_ZOOM), 0.5)
            if min_zoom > target_zoom:
                min_zoom = target_zoom
            max_image_bytes = max(int(self.settings.licitia_vision_render_max_image_bytes or VISION_ASSIST_MAX_IMAGE_BYTES), 128_000)
            max_dimension_px = max(int(self.settings.licitia_vision_render_max_dimension_px or VISION_ASSIST_MAX_IMAGE_DIMENSION_PX), 800)

            for page_number in page_numbers:
                page = pdf_document[page_number - 1]
                render_started_at = time.perf_counter()
                render_warnings: list[str] = []
                active_zoom = target_zoom
                pixmap = page.get_pixmap(matrix=fitz.Matrix(active_zoom, active_zoom), alpha=False)
                image_bytes = pixmap.tobytes("png")

                while (
                    (len(image_bytes) > max_image_bytes or pixmap.width > max_dimension_px or pixmap.height > max_dimension_px)
                    and active_zoom > min_zoom
                ):
                    previous_zoom = active_zoom
                    active_zoom = max(min_zoom, round(active_zoom - VISION_ASSIST_IMAGE_ZOOM_STEP, 2))
                    if active_zoom >= previous_zoom:
                        break
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(active_zoom, active_zoom), alpha=False)
                    image_bytes = pixmap.tobytes("png")
                    render_warnings.append(
                        f"IMAGE_RESIZED_FOR_BOUNDARY:{previous_zoom}->{active_zoom}"
                    )

                if len(image_bytes) > max_image_bytes:
                    render_warnings.append(
                        f"IMAGE_SIZE_EXCEEDS_BOUNDARY:{len(image_bytes)}>{max_image_bytes}"
                    )
                if pixmap.width > max_dimension_px or pixmap.height > max_dimension_px:
                    render_warnings.append(
                        f"IMAGE_DIMENSION_EXCEEDS_BOUNDARY:{pixmap.width}x{pixmap.height}>{max_dimension_px}"
                    )

                render_time_ms = int((time.perf_counter() - render_started_at) * 1000)
                rendered_pages.append(
                    RenderedVisionPage(
                        page_number=page_number,
                        document_page_id=document_pages_by_number[page_number].id,
                        image_bytes=image_bytes,
                        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
                        width_px=pixmap.width,
                        height_px=pixmap.height,
                        image_bytes_size=len(image_bytes),
                        render_time_ms=render_time_ms,
                        render_zoom=active_zoom,
                        warnings=render_warnings,
                    )
                )
            return rendered_pages
        finally:
            pdf_document.close()

    def _upsert_page_result(
        self,
        *,
        analysis_id: str,
        document_page_id: str,
        page_number: int,
        image_sha256: str,
        status: str,
        structured_json: dict[str, Any] | None,
        warnings: list[str],
        processing_time_ms: int | None,
        raw_response_text: str | None,
        extracted_markdown: str | None,
        extracted_plain_text: str | None,
    ) -> DocumentVisionPageResult:
        existing = self.db.scalar(
            select(DocumentVisionPageResult).where(
                DocumentVisionPageResult.analysis_id == analysis_id,
                DocumentVisionPageResult.document_page_id == document_page_id,
                DocumentVisionPageResult.image_sha256 == image_sha256,
            )
        )
        if existing is None:
            existing = DocumentVisionPageResult(
                analysis_id=analysis_id,
                document_page_id=document_page_id,
                page_number=page_number,
                image_sha256=image_sha256,
                status=status,
                structured_json=structured_json,
                warnings=warnings,
                processing_time_ms=processing_time_ms,
                raw_response_text=raw_response_text,
                extracted_markdown=extracted_markdown,
                extracted_plain_text=extracted_plain_text,
            )
            self.db.add(existing)
            self.db.flush()
            return existing

        existing.page_number = page_number
        existing.status = status
        existing.structured_json = structured_json
        existing.warnings = warnings
        existing.processing_time_ms = processing_time_ms
        existing.raw_response_text = raw_response_text
        existing.extracted_markdown = extracted_markdown
        existing.extracted_plain_text = extracted_plain_text
        self.db.flush()
        return existing

    def _serialize_analysis(self, analysis: DocumentVisionAnalysis, provider: VisionProviderStatusRead) -> VisionAssistAnalysisRead:
        page_results = self.db.execute(
            select(DocumentVisionPageResult)
            .where(DocumentVisionPageResult.analysis_id == analysis.id)
            .order_by(DocumentVisionPageResult.page_number.asc(), DocumentVisionPageResult.created_at.asc())
        ).scalars().all()
        serialized_page_results = [self._serialize_page_result(result) for result in page_results]
        summary = VisionAssistAnalysisSummaryRead(
            analysis_count=1,
            page_count=len(serialized_page_results),
            completed_page_count=sum(1 for page in serialized_page_results if page.status == DocumentVisionPageResultStatus.COMPLETED.value),
            failed_page_count=sum(1 for page in serialized_page_results if page.status == DocumentVisionPageResultStatus.FAILED.value),
            invalid_json_page_count=sum(1 for page in serialized_page_results if page.status == DocumentVisionPageResultStatus.INVALID_JSON.value),
            warning_count=sum(len(page.warnings) for page in serialized_page_results),
        )
        return VisionAssistAnalysisRead(
            id=analysis.id,
            tender_id=analysis.tender_id,
            document_id=analysis.document_id,
            status=analysis.status,
            mode=analysis.mode,
            model_name=analysis.model_name,
            prompt_version=analysis.prompt_version,
            input_fingerprint_sha256=analysis.input_fingerprint_sha256,
            analyzed_at=analysis.analyzed_at,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            provider=provider,
            summary=summary,
            page_results=serialized_page_results,
        )

    @staticmethod
    def _serialize_page_result(result: DocumentVisionPageResult) -> VisionAssistPageResultRead:
        return VisionAssistPageResultRead(
            id=result.id,
            analysis_id=result.analysis_id,
            document_page_id=result.document_page_id,
            page_number=result.page_number,
            image_sha256=result.image_sha256,
            status=result.status,
            raw_response_text=result.raw_response_text,
            structured_json=result.structured_json,
            extracted_markdown=result.extracted_markdown,
            extracted_plain_text=result.extracted_plain_text,
            warnings=list(result.warnings or []),
            processing_time_ms=result.processing_time_ms,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    @staticmethod
    def _build_latest_page_summaries(page_results: list[DocumentVisionPageResult]) -> list[VisionAssistLatestPageSummaryRead]:
        summaries: list[VisionAssistLatestPageSummaryRead] = []
        for result in page_results:
            structured_json = result.structured_json if isinstance(result.structured_json, dict) else {}
            new_item_numbers: list[str] = []
            seen_item_numbers: set[str] = set()
            for new_item in structured_json.get("new_items") or []:
                if not isinstance(new_item, dict):
                    continue
                item_number = _normalize_item_number(new_item.get("item_number"))
                if item_number is None or item_number in seen_item_numbers:
                    continue
                seen_item_numbers.add(item_number)
                new_item_numbers.append(item_number)

            detail_runtime = structured_json.get("_detail_runtime") if isinstance(structured_json, dict) else None
            detail_status = detail_runtime.get("status") if isinstance(detail_runtime, dict) else None
            structure_status = "VALID" if structured_json else "FAILED"
            summaries.append(
                VisionAssistLatestPageSummaryRead(
                    page_number=result.page_number,
                    structure_status=structure_status,
                    previous_item_number=_normalize_item_number(structured_json.get("previous_item_number")),
                    open_item_at_page_end=_normalize_item_number(structured_json.get("open_item_at_page_end")),
                    new_item_numbers=new_item_numbers,
                    detail_status=detail_status,
                )
            )
        return summaries

    @staticmethod
    def _build_latest_item_candidates(page_results: list[DocumentVisionPageResult]) -> list[VisionAssistLatestItemCandidateRead]:
        by_item_number: dict[str, dict[str, Any]] = {}
        for result in page_results:
            structured_json = result.structured_json if isinstance(result.structured_json, dict) else {}
            if not structured_json:
                continue

            continuity_quality = structured_json.get("_continuity_state_quality")
            can_use_page_ownership = continuity_quality == "VALID"

            page_new_items = structured_json.get("new_items") or []
            for new_item in page_new_items:
                if not isinstance(new_item, dict):
                    continue
                item_number = _normalize_item_number(new_item.get("item_number"))
                if item_number is None:
                    continue
                entry = by_item_number.setdefault(
                    item_number,
                    {
                        "item_number": item_number,
                        "concept_raw_text": None,
                        "first_detected_page": result.page_number,
                        "observed_pages": set(),
                        "review_required": False,
                    },
                )
                entry["first_detected_page"] = min(int(entry["first_detected_page"]), result.page_number)
                if entry["concept_raw_text"] is None and new_item.get("concept_raw_text") is not None:
                    entry["concept_raw_text"] = str(new_item.get("concept_raw_text"))
                entry["review_required"] = bool(entry["review_required"]) or bool(new_item.get("review_required", True))
                entry["observed_pages"].add(result.page_number)

            if can_use_page_ownership:
                for item_segment in structured_json.get("item_segments") or []:
                    if not isinstance(item_segment, dict):
                        continue
                    item_number = _normalize_item_number(item_segment.get("item_number"))
                    if item_number is None or item_number not in by_item_number:
                        continue
                    by_item_number[item_number]["observed_pages"].add(result.page_number)
                    by_item_number[item_number]["review_required"] = bool(by_item_number[item_number]["review_required"]) or bool(
                        item_segment.get("review_required", True)
                    )

        candidates: list[VisionAssistLatestItemCandidateRead] = []
        for item_number in sorted(by_item_number.keys(), key=lambda value: (int(value) if value.isdigit() else float("inf"), value)):
            entry = by_item_number[item_number]
            observed_pages = sorted(int(page_number) for page_number in entry["observed_pages"])
            candidates.append(
                VisionAssistLatestItemCandidateRead(
                    item_number=item_number,
                    concept_raw_text=entry["concept_raw_text"],
                    first_detected_page=int(entry["first_detected_page"]),
                    observed_pages=observed_pages,
                    review_required=bool(entry["review_required"]),
                )
            )
        return candidates


def normalize_page_numbers(page_numbers: list[int]) -> list[int]:
    normalized = sorted({int(page_number) for page_number in page_numbers})
    if not normalized:
        raise ValueError("At least one page number is required")
    if any(page_number < 1 for page_number in normalized):
        raise ValueError("Page numbers must be positive integers")
    return normalized


def resolve_document_path(stored_relative_path: str) -> Path:
    if not stored_relative_path or not stored_relative_path.strip():
        raise ValueError("Document storage path is missing")

    normalized_path = stored_relative_path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)
    if pure_path.is_absolute() or any(part in ("", ".", "..") for part in pure_path.parts):
        raise ValueError("Document storage path is invalid")

    settings = get_settings()
    data_root = Path(settings.licitia_data_dir)
    if not data_root.is_absolute():
        data_root = Path(__file__).resolve().parents[1] / data_root
    data_root = data_root.resolve()
    resolved_path = (data_root / pure_path).resolve()
    if not resolved_path.is_relative_to(data_root):
        raise ValueError("Document storage path escapes the local data directory")
    return resolved_path


def _build_input_fingerprint(
    *,
    tender_id: str,
    document_id: str,
    model_name: str,
    prompt_version: str,
    mode: str,
    rendered_pages: list[RenderedVisionPage],
    task_type: str,
    task_region_id: str | None,
) -> str:
    payload = {
        "tender_id": tender_id,
        "document_id": document_id,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "task_type": task_type,
        "task_region_id": task_region_id,
        "mode": mode,
        "pages": [
            {
                "page_number": page.page_number,
                "document_page_id": page.document_page_id,
                "image_sha256": page.image_sha256,
            }
            for page in rendered_pages
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_task_fingerprint(
    *,
    task_type: str,
    model_name: str,
    prompt_version: str,
    page_number: int,
    image_sha256: str,
    task_region_id: str | None,
) -> str:
    payload = {
        "task_type": task_type,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "page_number": page_number,
        "image_sha256": image_sha256,
        "task_region_id": task_region_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _should_run_detail_transcription(structured_json: dict[str, Any]) -> bool:
    item_segments = structured_json.get("item_segments") or []
    if any(bool(item_segment.get("has_supply")) or bool(item_segment.get("has_deliverable")) for item_segment in item_segments):
        return True

    uncertainties = [str(item).lower() for item in (structured_json.get("uncertainties") or [])]
    if any("ocr" in item or "blur" in item or "uncertain" in item for item in uncertainties):
        return True

    return False


def _build_detail_region_hint(structured_json: dict[str, Any]) -> str:
    for item_segment in structured_json.get("item_segments") or []:
        if bool(item_segment.get("has_supply")) or bool(item_segment.get("has_deliverable")):
            item_number = item_segment.get("item_number")
            anchor = (item_segment.get("anchor_raw_text") or "").strip()
            segment_kind = "SUPPLY" if bool(item_segment.get("has_supply")) else "DELIVERABLE"
            if anchor:
                return f"{segment_kind}:ITEM:{item_number or 'UNKNOWN'}:ANCHOR:{anchor[:80]}"
            return f"{segment_kind}:ITEM:{item_number or 'UNKNOWN'}"
    return "RELEVANT_TECHNICAL_REGION"


def _parse_supply_line(raw_visible_text: str) -> dict[str, Any]:
    text = (raw_visible_text or "").strip()
    if not text:
        return {
            "raw_visible_text": None,
            "description": None,
            "brand": None,
            "model": None,
            "quantity": None,
            "unit": None,
            "review_required": True,
        }

    upper_text = text.upper()
    brand = None
    model = None
    quantity = None
    unit = None

    for marker in ["MARCA:", "BRAND:"]:
        marker_index = upper_text.find(marker)
        if marker_index >= 0:
            after = text[marker_index + len(marker):].strip()
            brand = after.split(",", 1)[0].strip() if after else None
            break

    for marker in ["MODELO:", "MODEL:"]:
        marker_index = upper_text.find(marker)
        if marker_index >= 0:
            after = text[marker_index + len(marker):].strip()
            model = after.split(",", 1)[0].split("(", 1)[0].strip() if after else None
            break

    open_paren = text.rfind("(")
    close_paren = text.rfind(")")
    if open_paren >= 0 and close_paren > open_paren:
        token = text[open_paren + 1:close_paren].strip()
        parts = token.split()
        if len(parts) >= 2:
            quantity = parts[0]
            unit = " ".join(parts[1:]).strip()

    description = text
    for marker in ["MARCA:", "MODELO:", "BRAND:", "MODEL:"]:
        marker_index = description.upper().find(marker)
        if marker_index >= 0:
            description = description[:marker_index].strip(" ,;:-")
            break
    description = description or None

    parsed = {
        "raw_visible_text": text,
        "description": description,
        "brand": brand,
        "model": model,
        "quantity": quantity,
        "unit": unit,
    }
    parsed["review_required"] = not any([brand, model, quantity, unit])
    return parsed


def _merge_detail_transcription(
    *,
    structured_json: dict[str, Any],
    detail_structured_json: dict[str, Any],
    detail_task_fingerprint: str,
    detail_region_hint: str,
) -> None:
    detail_lines = detail_structured_json.get("raw_lines") or []
    parsed_rows: list[dict[str, Any]] = []
    for line in detail_lines:
        raw_visible_text = (line.get("raw_visible_text") or "").strip()
        if not raw_visible_text:
            continue
        parsed_rows.append(_parse_supply_line(raw_visible_text))

    existing_rows = list(((structured_json.get("detail_transcription") or {}).get("parsed_supply_rows") or []))
    if not existing_rows:
        parsed_supply_rows = parsed_rows
    else:
        disagreements: list[str] = []
        for existing, parsed in zip(existing_rows, parsed_rows):
            for field in ("model", "quantity", "unit"):
                existing_value = (existing.get(field) or "").strip()
                parsed_value = (parsed.get(field) or "").strip()
                if existing_value and parsed_value and existing_value != parsed_value:
                    existing["review_required"] = True
                    parsed["review_required"] = True
                    disagreements.append(field)
        parsed_supply_rows = [*existing_rows, *parsed_rows]
        if disagreements:
            uncertainties = list(structured_json.get("uncertainties") or [])
            uncertainties.append(f"{WARNING_CRITICAL_DISAGREEMENT}:{','.join(sorted(set(disagreements)))}")
            structured_json["uncertainties"] = uncertainties

    detail_meta = {
        "task_type": VISION_TASK_DETAIL_TRANSCRIPTION,
        "prompt_version": VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION,
        "task_fingerprint": detail_task_fingerprint,
        "region_hint": detail_region_hint,
        "source_page": detail_structured_json.get("source_page"),
        "raw_lines": detail_lines,
        "parsed_supply_rows": parsed_supply_rows,
    }
    structured_json["detail_transcription"] = detail_meta


def _normalize_item_number(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.lstrip("([{")
    normalized = normalized.rstrip(")]}.;:,")
    return normalized or None


def _normalize_previous_page_context(previous_page_context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(previous_page_context, dict):
        return None
    open_item_number = _normalize_item_number(previous_page_context.get("open_item_number"))
    open_item_concept = previous_page_context.get("open_item_concept")
    if open_item_number is None and open_item_concept is None:
        return None
    return {
        "open_item_number": open_item_number,
        "open_item_concept": str(open_item_concept) if open_item_concept is not None else None,
        "open_section": previous_page_context.get("open_section") or "ALCANCES",
    }


def _normalize_structure_item_numbers(structured_json: dict[str, Any]) -> None:
    structured_json["previous_item_number"] = _normalize_item_number(structured_json.get("previous_item_number"))
    structured_json["open_item_at_page_end"] = _normalize_item_number(structured_json.get("open_item_at_page_end"))

    for new_item in structured_json.get("new_items", []):
        new_item["item_number"] = _normalize_item_number(new_item.get("item_number"))

    deduplicated_new_items: list[dict[str, Any]] = []
    seen_new_item_numbers: set[str] = set()
    for new_item in structured_json.get("new_items", []):
        item_number = new_item.get("item_number")
        if item_number is None or item_number in seen_new_item_numbers:
            continue
        seen_new_item_numbers.add(item_number)
        deduplicated_new_items.append(new_item)
    structured_json["new_items"] = deduplicated_new_items

    for item_segment in structured_json.get("item_segments", []):
        item_segment["item_number"] = _normalize_item_number(item_segment.get("item_number"))


def _derive_new_items_from_started_segments(structured_json: dict[str, Any], normalization_warnings: list[str]) -> None:
    seen_numbers = {
        new_item.get("item_number")
        for new_item in structured_json.get("new_items", [])
        if new_item.get("item_number") is not None
    }
    for item_segment in structured_json.get("item_segments", []):
        if not bool(item_segment.get("starts_on_this_page")):
            continue
        item_number = item_segment.get("item_number")
        if item_number is None or item_number in seen_numbers:
            continue
        structured_json.setdefault("new_items", []).append(
            {
                "item_number": item_number,
                "concept_raw_text": item_segment.get("anchor_raw_text"),
                "review_required": bool(item_segment.get("review_required", True)),
            }
        )
        seen_numbers.add(item_number)
        normalization_warnings.append(WARNING_NEW_ITEM_DERIVED_FROM_ITEM_START)


def _suppress_continuation_segment_starts(
    structured_json: dict[str, Any],
    previous_page_context: dict[str, Any] | None,
    normalization_warnings: list[str],
) -> None:
    if not structured_json.get("continues_previous_item"):
        return

    known_previous_item = structured_json.get("previous_item_number") or (previous_page_context or {}).get("open_item_number")
    if known_previous_item is None:
        return

    for item_segment in structured_json.get("item_segments", []):
        if item_segment.get("item_number") != known_previous_item:
            continue
        if not bool(item_segment.get("starts_on_this_page")):
            continue
        item_segment["starts_on_this_page"] = False
        normalization_warnings.append(WARNING_SEGMENT_START_SUPPRESSED_BY_CONTINUITY)


def _apply_segment_ownership_from_context(
    structured_json: dict[str, Any],
    previous_page_context: dict[str, Any] | None,
    normalization_warnings: list[str],
) -> None:
    previous_item_number = (previous_page_context or {}).get("open_item_number")
    if previous_item_number is None:
        return

    boundary_index: int | None = None
    for index, item_segment in enumerate(structured_json.get("item_segments", [])):
        if bool(item_segment.get("starts_on_this_page")) and item_segment.get("item_number") not in {None, previous_item_number}:
            boundary_index = index
            break

    if boundary_index is None:
        boundary_index = len(structured_json.get("item_segments", []))

    for item_segment in structured_json.get("item_segments", [])[:boundary_index]:
        if item_segment.get("item_number") is not None:
            continue
        item_segment["item_number"] = previous_item_number
        normalization_warnings.append(WARNING_REGION_ITEM_FILLED_FROM_PREVIOUS_CONTEXT)


def _ordered_segment_item_numbers(structured_json: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item_segment in structured_json.get("item_segments", []):
        item_number = item_segment.get("item_number")
        if item_number is None or item_number in seen:
            continue
        seen.add(item_number)
        ordered.append(item_number)
    return ordered


def _mark_item_segments_for_review(structured_json: dict[str, Any], item_numbers: set[str] | None = None) -> None:
    for item_segment in structured_json.get("item_segments", []):
        if item_numbers is None or item_segment.get("item_number") in item_numbers:
            item_segment["review_required"] = True


def _has_segment_content(item_segment: dict[str, Any]) -> bool:
    return any(
        bool(item_segment.get(field))
        for field in ("has_service", "has_supply", "has_deliverable")
    )


def _apply_structure_consistency_rules(
    structured_json: dict[str, Any],
    previous_page_context: dict[str, Any] | None,
    normalization_warnings: list[str],
) -> None:
    previous_item_number = (previous_page_context or {}).get("open_item_number")
    new_item_numbers = [
        new_item.get("item_number")
        for new_item in structured_json.get("new_items", [])
        if new_item.get("item_number") is not None
    ]
    segment_item_numbers = _ordered_segment_item_numbers(structured_json)
    started_segment_numbers = {
        item_segment.get("item_number")
        for item_segment in structured_json.get("item_segments", [])
        if bool(item_segment.get("starts_on_this_page")) and item_segment.get("item_number") is not None
    }

    if structured_json.get("continues_previous_item") and previous_item_number and structured_json.get("previous_item_number") is None:
        structured_json["previous_item_number"] = previous_item_number
        normalization_warnings.append(WARNING_PREVIOUS_ITEM_FILLED_FROM_CONTEXT)

    if structured_json.get("continues_previous_item") and previous_item_number:
        has_previous_owned_segment = any(
            item_segment.get("item_number") == previous_item_number and _has_segment_content(item_segment)
            for item_segment in structured_json.get("item_segments", [])
        )
        if not has_previous_owned_segment:
            normalization_warnings.append(WARNING_STRUCTURE_CONTINUATION_UNRESOLVED)

    if previous_item_number:
        changed_segment_numbers = {
            item_number
            for item_number in segment_item_numbers
            if item_number is not None and item_number != previous_item_number
        }
        declared_boundary_numbers = set(new_item_numbers) | started_segment_numbers
        inconsistent_numbers = {item_number for item_number in changed_segment_numbers if item_number not in declared_boundary_numbers}
        if inconsistent_numbers:
            normalization_warnings.append(WARNING_STRUCTURE_INCONSISTENT)
            _mark_item_segments_for_review(structured_json, inconsistent_numbers)

    if structured_json.get("open_item_at_page_end") is None:
        if new_item_numbers:
            structured_json["open_item_at_page_end"] = new_item_numbers[-1]
            normalization_warnings.append(WARNING_OPEN_ITEM_DERIVED_FROM_LAST_NEW_ITEM)
        elif (
            structured_json.get("continues_previous_item")
            and previous_item_number
            and not any(item_number != previous_item_number for item_number in segment_item_numbers)
        ):
            structured_json["open_item_at_page_end"] = previous_item_number
            normalization_warnings.append(WARNING_OPEN_ITEM_DERIVED_FROM_PREVIOUS_CONTEXT)
        elif len(segment_item_numbers) == 1 and (
            previous_item_number is None or segment_item_numbers[0] == previous_item_number
        ):
            structured_json["open_item_at_page_end"] = segment_item_numbers[0]
            normalization_warnings.append(WARNING_OPEN_ITEM_DERIVED_FROM_SINGLE_REGION)


def _build_item_segments_from_legacy_regions(parsed_json: dict[str, Any]) -> list[dict[str, Any]]:
    region_entries = [region for region in (parsed_json.get("regions") or []) if isinstance(region, dict)]
    if not region_entries:
        region_entries = [
            {
                "type": str(block.get("scope_type") or "OTHER").upper(),
                "item_number": block.get("belongs_to_partida"),
                "anchor_raw_text": block.get("raw_visible_text"),
                "review_required": bool(block.get("review_required", True)),
            }
            for block in (parsed_json.get("scope_blocks") or [])
            if isinstance(block, dict)
        ]

    if not region_entries:
        return []

    started_numbers = {
        str(item.get("item_number"))
        for item in (parsed_json.get("new_items") or [])
        if isinstance(item, dict) and item.get("item_number") is not None
    }
    started_numbers.update(str(item_number) for item_number in (parsed_json.get("new_partidas_started") or []) if item_number is not None)

    item_segments: list[dict[str, Any]] = []
    for region in region_entries:
        item_number = region.get("item_number")
        region_type = str(region.get("type") or "OTHER").upper()
        starts_on_this_page = region_type == "ITEM_START" or (item_number is not None and str(item_number) in started_numbers)
        candidate_segment = {
            "item_number": item_number,
            "starts_on_this_page": starts_on_this_page,
            "has_service": region_type == "SERVICE",
            "has_supply": region_type == "SUPPLY",
            "has_deliverable": region_type == "DELIVERABLE",
            "anchor_raw_text": region.get("anchor_raw_text"),
            "review_required": bool(region.get("review_required", True)),
        }

        if item_segments:
            previous_segment = item_segments[-1]
            if (
                previous_segment.get("item_number") == candidate_segment.get("item_number")
                and bool(previous_segment.get("starts_on_this_page")) == bool(candidate_segment.get("starts_on_this_page"))
            ):
                previous_segment["has_service"] = bool(previous_segment.get("has_service")) or bool(candidate_segment.get("has_service"))
                previous_segment["has_supply"] = bool(previous_segment.get("has_supply")) or bool(candidate_segment.get("has_supply"))
                previous_segment["has_deliverable"] = bool(previous_segment.get("has_deliverable")) or bool(candidate_segment.get("has_deliverable"))
                if not previous_segment.get("anchor_raw_text"):
                    previous_segment["anchor_raw_text"] = candidate_segment.get("anchor_raw_text")
                previous_segment["review_required"] = bool(previous_segment.get("review_required")) or bool(candidate_segment.get("review_required"))
                continue

        item_segments.append(candidate_segment)

    return item_segments


def _build_page_response_from_raw(page_number: int, parsed_json: dict[str, Any]) -> dict[str, Any]:
    if "continues_previous_item" not in parsed_json and "continues_previous_partida" in parsed_json:
        parsed_json = {**parsed_json, "continues_previous_item": bool(parsed_json.get("continues_previous_partida"))}

    if "previous_item_number" not in parsed_json and parsed_json.get("previous_partida_number") is not None:
        parsed_json = {**parsed_json, "previous_item_number": parsed_json.get("previous_partida_number")}

    if "new_items" not in parsed_json and isinstance(parsed_json.get("new_partidas"), list):
        parsed_json = {
            **parsed_json,
            "new_items": [
                {
                    "item_number": str(item.get("item_number")),
                    "concept_raw_text": item.get("concept_raw_text"),
                    "review_required": bool(item.get("review_required")),
                }
                for item in parsed_json.get("new_partidas", [])
                if isinstance(item, dict) and item.get("item_number") is not None
            ],
        }

    if "new_items" not in parsed_json and isinstance(parsed_json.get("new_partidas_started"), list):
        parsed_json = {
            **parsed_json,
            "new_items": [
                {
                    "item_number": str(item_number),
                    "concept_raw_text": None,
                    "review_required": True,
                }
                for item_number in parsed_json.get("new_partidas_started", [])
                if item_number is not None
            ],
        }

    if "item_segments" not in parsed_json and (
        isinstance(parsed_json.get("regions"), list) or isinstance(parsed_json.get("scope_blocks"), list)
    ):
        parsed_json = {**parsed_json, "item_segments": _build_item_segments_from_legacy_regions(parsed_json)}

    if "open_item_at_page_end" not in parsed_json and isinstance(parsed_json.get("open_partida_at_page_end"), dict):
        open_partida = dict(parsed_json["open_partida_at_page_end"])
        parsed_json = {**parsed_json, "open_item_at_page_end": open_partida.get("item_number")}

    if parsed_json.get("page_number") != page_number:
        parsed_json = {**parsed_json, "page_number": page_number}
    return parsed_json


def get_vision_provider_status() -> VisionProviderStatusRead:
    return OllamaVisionAssistClient().probe()


def analyze_vision_document(db: Session, tender_id: str, document_id: str, request: VisionAssistAnalyzeRequest) -> VisionAssistAnalysisRead:
    service = VisionAssistService(db)
    return service.analyze_document(tender_id, document_id, request)


def list_vision_document_results(db: Session, tender_id: str, document_id: str) -> VisionAssistResultsRead:
    service = VisionAssistService(db)
    return service.list_document_results(tender_id, document_id)


def get_vision_document_page_result(db: Session, tender_id: str, document_id: str, page_number: int) -> VisionAssistPageResultRead:
    service = VisionAssistService(db)
    return service.get_page_result(tender_id, document_id, page_number)


def get_vision_document_latest_summary(db: Session, tender_id: str, document_id: str) -> VisionAssistLatestSummaryRead:
    service = VisionAssistService(db)
    return service.get_latest_summary(tender_id, document_id)
