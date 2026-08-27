from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import PIL.Image
except Exception:  # pragma: no cover - optional runtime dependency
    PIL = None


@dataclass
class OCRPageResult:
    text: str
    status: str
    engine: str
    engine_version: str
    language: str = "es+en"
    confidence: float | None = None
    processing_time_ms: int | None = None
    warnings: list[str] = field(default_factory=list)


class DefaultOCRProvider:
    provider_id: str = ""
    provider_name: str = ""
    version: str = "unknown"
    status: str = "UNAVAILABLE"
    status_reason: str = "provider not initialized"

    def _base_payload(
        self,
        text: str,
        status: str,
        *,
        confidence: float | None = None,
        processing_time_ms: int | None = None,
        warnings: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        return {
            "text": text,
            "status": status,
            "engine": self.provider_id,
            "engine_version": self.version,
            "language": language or "es+en",
            "confidence": confidence,
            "processing_time_ms": processing_time_ms,
            "warnings": warnings or [],
        }

    def recognize(self, page_image: Any, language: str = "es+en") -> dict[str, Any]:
        raise NotImplementedError


class TesseractOCRProvider(DefaultOCRProvider):
    provider_id = "TESSERACT"
    provider_name = "Tesseract"

    def __init__(self) -> None:
        self.status, self.status_reason = self._probe_runtime()
        self.version = self._detect_version()

    @staticmethod
    def _map_language_profile(language: str) -> str:
        normalized = (language or "es+en").strip()
        if not normalized:
            return "spa+eng"
        normalized = normalized.replace(",", "+")
        parts = [part.strip().lower() for part in normalized.split("+") if part.strip()]
        if not parts:
            return "spa+eng"
        language_map = {
            "es": "spa",
            "spa": "spa",
            "en": "eng",
            "eng": "eng",
        }
        translated = [language_map.get(part, part) for part in parts]
        return "+".join(translated)

    def _probe_runtime(self) -> tuple[str, str]:
        if shutil.which("tesseract") is None:
            return "UNAVAILABLE", "Tesseract binary not found on PATH"
        try:
            import pytesseract  # type: ignore
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            return "UNAVAILABLE", f"pytesseract unavailable: {exc}"
        return "AVAILABLE", "binary detected"

    def _detect_version(self) -> str:
        try:
            import pytesseract  # type: ignore

            version = pytesseract.get_tesseract_version()
            return str(version) if version else "unknown"
        except Exception:  # pragma: no cover - best effort detection only
            return "unknown"

    def recognize(self, page_image: Any, language: str = "es+en") -> dict[str, Any]:
        if self.status != "AVAILABLE":
            raise RuntimeError(self.status_reason)

        try:
            import pytesseract  # type: ignore
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(f"pytesseract unavailable: {exc}") from exc

        effective_language = self._map_language_profile(language)

        try:
            image = self._coerce_image(page_image)
            extracted_text = pytesseract.image_to_string(image, lang=effective_language)
        except Exception as exc:  # pragma: no cover - OCR provider-specific failure
            raise RuntimeError(f"Tesseract OCR failed: {exc}") from exc

        cleaned_text = (extracted_text or "").strip()
        status = "OCR_TEXT_EXTRACTED" if cleaned_text else "NO_TEXT"
        return self._base_payload(
            cleaned_text,
            status,
            confidence=None,
            processing_time_ms=None,
            warnings=[],
            language=effective_language,
        )

    @staticmethod
    def _coerce_image(page_image: Any):
        if PIL is not None and hasattr(page_image, "convert"):
            return page_image
        if hasattr(page_image, "tobytes"):
            return page_image
        if isinstance(page_image, (bytes, bytearray)):
            if PIL is not None:
                return PIL.Image.open(__import__("io").BytesIO(page_image))
        raise TypeError("Unsupported page image payload for Tesseract")


class PaddleOCRProvider(DefaultOCRProvider):
    provider_id = "PADDLEOCR"
    provider_name = "PaddleOCR"

    def __init__(self) -> None:
        self.status, self.status_reason = self._probe_runtime()
        self.version = self._detect_version()

    @staticmethod
    def _map_language_profile(language: str) -> str:
        normalized = (language or "es+en").strip()
        if not normalized:
            return "es"
        parts = [part.strip().lower() for part in normalized.replace(",", "+").split("+") if part.strip()]
        if not parts:
            return "es"
        if "es" in parts or "spa" in parts:
            return "es"
        if "en" in parts or "eng" in parts:
            return "en"
        return parts[0]

    def _probe_runtime(self) -> tuple[str, str]:
        try:
            import paddleocr  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            return "UNAVAILABLE", f"PaddleOCR unavailable: {exc}"
        try:
            import paddle  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            return "UNAVAILABLE", f"paddle runtime unavailable: {exc}"
        return "AVAILABLE", "runtime detected"

    def _detect_version(self) -> str:
        try:
            import paddleocr

            version = getattr(paddleocr, "__version__", "unknown")
            return str(version)
        except Exception:  # pragma: no cover - best effort detection only
            return "unknown"

    @staticmethod
    def _coerce_image(page_image: Any):
        if PIL is not None and hasattr(page_image, "convert"):
            return np.asarray(page_image.convert("RGB"))
        if isinstance(page_image, np.ndarray):
            array = page_image
            if array.ndim == 2:
                return np.stack([array] * 3, axis=-1)
            if array.ndim == 3 and array.shape[-1] == 1:
                return np.repeat(array, 3, axis=-1)
            return array
        if isinstance(page_image, (bytes, bytearray)):
            if PIL is None:
                raise TypeError("Pillow is required to decode PaddleOCR image bytes")
            with io.BytesIO(page_image) as image_buffer:
                image = PIL.Image.open(image_buffer)
                return np.asarray(image.convert("RGB"))
        if hasattr(page_image, "tobytes"):
            return np.asarray(page_image)
        raise TypeError("Unsupported page image payload for PaddleOCR")

    @staticmethod
    def _extract_prediction_text(prediction: Any) -> tuple[str, float | None, int]:
        if isinstance(prediction, dict):
            texts = prediction.get("rec_texts") or []
            scores = prediction.get("rec_scores") or []
            if not texts:
                return "", None, 0
            text_lines = [str(item) for item in texts if item is not None]
            numeric_scores = []
            for score in scores:
                try:
                    numeric_scores.append(float(score))
                except (TypeError, ValueError):
                    continue
            confidence = None
            if numeric_scores:
                confidence = sum(numeric_scores) / len(numeric_scores)
            return "\n".join(text_lines).strip(), confidence, len(text_lines)

        if isinstance(prediction, (list, tuple)):
            aggregated_text: list[str] = []
            scores: list[float] = []
            for item in prediction:
                if isinstance(item, dict):
                    text_fragment, score, _ = PaddleOCRProvider._extract_prediction_text(item)
                    if text_fragment:
                        aggregated_text.append(text_fragment)
                    if score is not None:
                        scores.append(score)
            joined = "\n".join(part for part in aggregated_text if part).strip()
            confidence = None if not scores else sum(scores) / len(scores)
            return joined, confidence, len(aggregated_text)

        return "", None, 0

    def recognize(self, page_image: Any, language: str = "es+en") -> dict[str, Any]:
        if self.status != "AVAILABLE":
            raise RuntimeError(self.status_reason)

        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(f"PaddleOCR unavailable: {exc}") from exc
        try:
            effective_language = self._map_language_profile(language)
            normalized_image = self._coerce_image(page_image)
            ocr_engine = PaddleOCR(lang=effective_language)
            prediction_results = ocr_engine.predict(normalized_image)
            text_parts: list[str] = []
            scores: list[float] = []
            for item in prediction_results or []:
                text_fragment, confidence, _ = self._extract_prediction_text(item)
                if text_fragment:
                    text_parts.append(text_fragment)
                if confidence is not None:
                    scores.append(confidence)
            cleaned_text = "\n".join(part for part in text_parts if part).strip()
            confidence = None if not scores else sum(scores) / len(scores)
        except Exception as exc:  # pragma: no cover - OCR provider-specific failure
            raise RuntimeError(f"PaddleOCR failed: {exc}") from exc

        status = "OCR_TEXT_EXTRACTED" if cleaned_text else "NO_TEXT"
        return self._base_payload(cleaned_text, status, confidence=confidence, processing_time_ms=None, warnings=[], language=effective_language)


def build_default_ocr_provider_registry() -> list[DefaultOCRProvider]:
    return [TesseractOCRProvider(), PaddleOCRProvider()]


def resolve_provider_selection(provider_mode: str, available_providers: list[DefaultOCRProvider], *, force: bool = False) -> list[DefaultOCRProvider]:
    normalized = (provider_mode or "AUTO").upper()
    if normalized == "COMPARE":
        candidates = [provider for provider in available_providers if provider.status == "AVAILABLE"]
        if not candidates:
            raise RuntimeError("No OCR providers are currently available")
        return candidates

    if normalized == "AUTO":
        preferred_order = ["TESSERACT", "PADDLEOCR"]
        for provider_id in preferred_order:
            for provider in available_providers:
                if provider.provider_id == provider_id and provider.status == "AVAILABLE":
                    return [provider]
        raise RuntimeError("No OCR providers are currently available")

    matching = [provider for provider in available_providers if provider.provider_id == normalized]
    if not matching or matching[0].status != "AVAILABLE":
        raise RuntimeError(f"OCR provider {normalized} is unavailable")
    return matching
