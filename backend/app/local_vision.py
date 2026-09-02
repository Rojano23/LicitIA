from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any

import fitz
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import Settings, get_settings
from app.models import TenderDocument

VISION_PROMPT_VERSION = "mvp-06.1-local-vision-001"


class VisionPageImage(BaseModel):
    page_number: int
    png_bytes: bytes
    source_locator: str | None = None
    source_excerpt: str | None = None


class VisionPartidaProposalRead(BaseModel):
    item_number: str | None = None
    description: str
    quantity: Decimal | None = None
    unit: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    evidence_excerpt: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source_pages")
    @classmethod
    def _normalize_source_pages(cls, value: list[int]) -> list[int]:
        normalized = []
        for page in value:
            page_number = int(page)
            if page_number not in normalized:
                normalized.append(page_number)
        return normalized


class VisionRuntimeRead(BaseModel):
    runtime_available: bool
    models_available: list[str] = Field(default_factory=list)
    selected_model: str | None = None
    provider_id: str
    provider_name: str
    provider_status: str
    provider_status_reason: str
    base_url: str


class VisionProposalPayloadRead(BaseModel):
    document_type: str | None = None
    has_procurement_scope: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    review_status: str = "REVIEW_REQUIRED"
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    partidas: list[VisionPartidaProposalRead] = Field(default_factory=list)


class VisionAnalysisRead(VisionProposalPayloadRead):
    tender_id: str
    document_id: str
    source_filename: str | None = None
    vision_mode: str
    status: str
    prompt_version: str
    pages_analyzed: list[int] = Field(default_factory=list)
    runtime: VisionRuntimeRead
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LocalVisionProvider:
    provider_id = "LOCAL_VISION"
    provider_name = "Local Vision"
    provider_status = "UNAVAILABLE"
    provider_status_reason = "provider not initialized"
    runtime_available = False
    models_available: list[str] = []
    selected_model: str | None = None
    base_url = ""

    def runtime_snapshot(self) -> VisionRuntimeRead:
        return VisionRuntimeRead(
            runtime_available=self.runtime_available,
            models_available=list(self.models_available),
            selected_model=self.selected_model,
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            provider_status=self.provider_status,
            provider_status_reason=self.provider_status_reason,
            base_url=self.base_url,
        )

    def analyze_scope_pages(
        self,
        *,
        tender_id: str,
        document_id: str,
        source_filename: str | None,
        document_type: str,
        vision_mode: str,
        pages: list[VisionPageImage],
    ) -> VisionAnalysisRead:
        raise NotImplementedError


class DisabledLocalVisionProvider(LocalVisionProvider):
    def __init__(self, reason: str) -> None:
        self.provider_status = "UNAVAILABLE"
        self.provider_status_reason = reason
        self.runtime_available = False
        self.models_available = []
        self.selected_model = None
        settings = get_settings()
        self.base_url = settings.licitia_ollama_base_url.rstrip("/")

    def analyze_scope_pages(
        self,
        *,
        tender_id: str,
        document_id: str,
        source_filename: str | None,
        document_type: str,
        vision_mode: str,
        pages: list[VisionPageImage],
    ) -> VisionAnalysisRead:
        return VisionAnalysisRead(
            tender_id=tender_id,
            document_id=document_id,
            source_filename=source_filename,
            vision_mode=vision_mode,
            status="UNAVAILABLE",
            prompt_version=VISION_PROMPT_VERSION,
            document_type=document_type,
            has_procurement_scope=False,
            confidence=None,
            pages_analyzed=[page.page_number for page in pages],
            warnings=[self.provider_status_reason],
            partidas=[],
            runtime=self.runtime_snapshot(),
        )


class OllamaVisionProvider(LocalVisionProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.licitia_ollama_base_url.rstrip("/")
        self.selected_model = (self.settings.licitia_ollama_vision_model or "").strip() or None
        self.models_available = []
        self.runtime_available = False
        self.provider_status = "UNAVAILABLE"
        self.provider_status_reason = "provider not probed"

        if not self.settings.licitia_local_ai_enabled:
            self.provider_status_reason = "local AI is disabled"
            return

        if self.selected_model is None:
            self.provider_status_reason = "no vision model configured"
            return

        runtime_available, models_available, reason = self._probe_runtime()
        self.runtime_available = runtime_available
        self.models_available = models_available
        if not runtime_available:
            self.provider_status_reason = reason
            return

        if self.selected_model not in models_available:
            self.provider_status_reason = f"vision model {self.selected_model} is not installed locally"
            return

        self.provider_status = "AVAILABLE"
        self.provider_status_reason = reason

    def _probe_runtime(self) -> tuple[bool, list[str], str]:
        request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.settings.licitia_ollama_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return False, [], f"Ollama server unavailable at {self.base_url}: {exc}"

        models: list[str] = []
        for model in payload.get("models", []):
            name = model.get("name") if isinstance(model, dict) else None
            if name:
                models.append(str(name))
        return True, models, "ollama runtime detected"

    @staticmethod
    def _build_prompt(document_type: str, pages: list[VisionPageImage]) -> str:
        page_numbers = ", ".join(str(page.page_number) for page in pages)
        return (
            "You are extracting procurement scope from local tender document pages. "
            "Return only valid JSON, no markdown, no commentary. "
            "If the page set is ambiguous, keep review_status as REVIEW_REQUIRED. "
            "Do not invent quantities or units unless they are explicit in the page images. "
            f"Document type hint: {document_type}. Pages: {page_numbers}. "
            "Schema: {"
            '"document_type": string or null, '
            '"has_procurement_scope": boolean, '
            '"confidence": number between 0 and 1 or null, '
            '"review_status": string, '
            '"summary": string or null, '
            '"warnings": array of strings, '
            '"partidas": [ {"item_number": string or null, "description": string, '
            '"quantity": string or number or null, "unit": string or null, '
            '"source_pages": array of integers, "evidence_excerpt": string, '
            '"confidence": number between 0 and 1 or null, "warnings": array of strings } ]'
            " }"
        )

    def _chat_completion(self, prompt: str, pages: list[VisionPageImage]) -> dict[str, Any]:
        assert self.selected_model is not None
        payload = {
            "model": self.selected_model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(page.png_bytes).decode("ascii") for page in pages],
                }
            ],
            "options": {"temperature": 0},
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.settings.licitia_ollama_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _coerce_payload(raw_content: Any) -> dict[str, Any]:
        if isinstance(raw_content, dict):
            return raw_content
        if not isinstance(raw_content, str):
            raise ValueError("Vision response content is not JSON text")

        text = raw_content.strip()
        if not text:
            raise ValueError("Vision response content is empty")

        if text.startswith("```"):
            text = text.strip("`")
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        return json.loads(text)

    def analyze_scope_pages(
        self,
        *,
        tender_id: str,
        document_id: str,
        source_filename: str | None,
        document_type: str,
        vision_mode: str,
        pages: list[VisionPageImage],
    ) -> VisionAnalysisRead:
        runtime_snapshot = self.runtime_snapshot()
        if self.provider_status != "AVAILABLE" or self.selected_model is None:
            return VisionAnalysisRead(
                tender_id=tender_id,
                document_id=document_id,
                source_filename=source_filename,
                vision_mode=vision_mode,
                status="UNAVAILABLE",
                prompt_version=VISION_PROMPT_VERSION,
                document_type=document_type,
                has_procurement_scope=False,
                confidence=None,
                pages_analyzed=[page.page_number for page in pages],
                warnings=[self.provider_status_reason],
                partidas=[],
                runtime=runtime_snapshot,
            )

        prompt = self._build_prompt(document_type, pages)
        started_at = datetime.now(timezone.utc)
        warnings: list[str] = []
        try:
            raw_response = self._chat_completion(prompt, pages)
            message = raw_response.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else raw_response.get("response")
            payload = self._coerce_payload(content)
            validated = VisionProposalPayloadRead.model_validate(payload)
            status = "PROPOSED" if validated.partidas else "SKIPPED"
            warnings.extend(validated.warnings)
            return VisionAnalysisRead(
                tender_id=tender_id,
                document_id=document_id,
                source_filename=source_filename,
                vision_mode=vision_mode,
                status=status,
                prompt_version=VISION_PROMPT_VERSION,
                document_type=validated.document_type or document_type,
                has_procurement_scope=validated.has_procurement_scope,
                confidence=validated.confidence,
                summary=validated.summary,
                warnings=warnings,
                partidas=validated.partidas,
                review_status=validated.review_status,
                pages_analyzed=[page.page_number for page in pages],
                runtime=runtime_snapshot,
                generated_at=started_at,
            )
        except (urllib.error.URLError, TimeoutError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            warnings.append(str(exc))
            return VisionAnalysisRead(
                tender_id=tender_id,
                document_id=document_id,
                source_filename=source_filename,
                vision_mode=vision_mode,
                status="ERROR",
                prompt_version=VISION_PROMPT_VERSION,
                document_type=document_type,
                has_procurement_scope=False,
                confidence=None,
                pages_analyzed=[page.page_number for page in pages],
                warnings=warnings,
                partidas=[],
                runtime=runtime_snapshot,
                generated_at=started_at,
            )


def build_local_vision_provider(settings: Settings | None = None) -> LocalVisionProvider:
    active_settings = settings or get_settings()
    if not active_settings.licitia_local_ai_enabled:
        return DisabledLocalVisionProvider("local AI is disabled")
    return OllamaVisionProvider(active_settings)


def normalize_vision_mode(value: str | None) -> str:
    normalized = (value or "AUTO").strip().upper()
    if normalized not in {"OFF", "AUTO", "FORCE"}:
        raise ValueError(f"Unsupported vision mode: {value}")
    return normalized


def resolve_document_file_path(stored_relative_path: str) -> Path:
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


def render_document_pages_as_png(document: TenderDocument, page_numbers: list[int], *, zoom: float = 2.0) -> list[VisionPageImage]:
    resolved_path = resolve_document_file_path(document.stored_relative_path)
    if not resolved_path.exists():
        raise ValueError(f"Document file not found: {resolved_path}")

    pdf_document = fitz.open(str(resolved_path))
    try:
        rendered_pages: list[VisionPageImage] = []
        for page_number in page_numbers:
            if page_number < 1 or page_number > pdf_document.page_count:
                continue
            page = pdf_document[page_number - 1]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            rendered_pages.append(
                VisionPageImage(
                    page_number=page_number,
                    png_bytes=pixmap.tobytes("png"),
                    source_locator=f"page:{page_number}",
                )
            )
        return rendered_pages
    finally:
        pdf_document.close()


def compact_text_excerpt(text: str, limit: int = 1000) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
