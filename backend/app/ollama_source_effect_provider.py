from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.source_effect_evidence_selection import (
    SourceEffectSelectionEffect,
    SourceEffectSelectionModelOutput,
    build_source_effect_evidence_spans,
    enumerate_source_effect_date_candidates,
    enumerate_source_effect_locator_candidates,
    enumerate_source_effect_target_candidates,
    validate_and_materialize_selection,
)
from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    SourceEffectProviderDiscoveryPayload,
    SourceEffectSemanticDiscoveryProvider,
    SourceEffectSemanticDiscoveryResult,
    SourceEffectSemanticFragment,
    discover_source_effect_semantics,
)

OLLAMA_SOURCE_EFFECT_PROVIDER_NAME = "Ollama Source Effect Semantic Discovery"
OLLAMA_SOURCE_EFFECT_PROVIDER_VERSION = "ollama-source-effect-provider-001"
OLLAMA_SOURCE_EFFECT_PROMPT_VERSION = "source-effect-semantic-discovery-2026-09-08-001"

_ALLOWED_STATUSES = {
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_UNSUPPORTED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
}


class _OllamaBoundedSourceEffectModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effect_type: str
    effect_scope: str
    evidence_span_id: str
    affected_locator_id: Optional[str] = None
    affected_target_id: Optional[str] = None
    effective_date_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class _OllamaLegacyDiscoveredSourceEffectModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effect_type: str
    effect_scope: str
    affected_document_ref_raw: Optional[str]
    affected_locator_raw: Optional[str]
    effective_date_raw: Optional[str]
    evidence_excerpt: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class _OllamaSourceEffectResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    effects: list[dict[str, Any]]
    diagnostics: list[str]


@dataclass(frozen=True, slots=True)
class OllamaSourceEffectDiscoveryExecution:
    provider_name: str
    provider_version: str
    contract_version: str
    raw_model_json: Optional[str]
    payload: SourceEffectProviderDiscoveryPayload
    elapsed_time_ms: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OllamaSourceEffectDiscoveryRun:
    provider_name: str
    provider_version: str
    contract_version: str
    raw_model_json: Optional[str]
    elapsed_time_ms: int
    result: SourceEffectSemanticDiscoveryResult


SourceEffectSemanticTransport = Callable[[dict[str, Any], float], dict[str, Any]]


class OllamaSourceEffectDiscoveryProvider(SourceEffectSemanticDiscoveryProvider):
    provider_name = OLLAMA_SOURCE_EFFECT_PROVIDER_NAME
    provider_version = OLLAMA_SOURCE_EFFECT_PROVIDER_VERSION
    contract_version = OLLAMA_SOURCE_EFFECT_PROMPT_VERSION

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        model_name: Optional[str] = None,
        transport: Optional[SourceEffectSemanticTransport] = None,
        max_output_tokens: Optional[int] = None,
        strict_bounded_contract: bool = True,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.licitia_ollama_base_url.rstrip("/")
        self.model_name = (model_name or "").strip()
        self.timeout_seconds = float(self.settings.licitia_ollama_timeout_seconds)
        self.transport = transport or self._default_transport
        self.max_output_tokens = max_output_tokens
        self.strict_bounded_contract = strict_bounded_contract

    def supports(self, fragment: SourceEffectSemanticFragment) -> bool:
        return bool(
            str(fragment.tender_id or "").strip()
            and str(fragment.acting_document_id or "").strip()
            and str(fragment.document_page_id or "").strip()
            and int(fragment.page_number) > 0
            and str(fragment.source_method or "").strip()
            and str(fragment.source_artifact_key or "").strip()
            and str(fragment.source_locator or "").strip()
            and str(fragment.source_text or "").strip()
        )

    def discover(self, fragment: SourceEffectSemanticFragment) -> SourceEffectProviderDiscoveryPayload:
        execution = self.execute(fragment)
        if execution.errors:
            raise ValueError("; ".join(execution.errors))
        return execution.payload

    def execute(self, fragment: SourceEffectSemanticFragment) -> OllamaSourceEffectDiscoveryExecution:
        if not self.model_name:
            error_message = "No Ollama model configured for source effect semantic discovery"
            return OllamaSourceEffectDiscoveryExecution(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                contract_version=self.contract_version,
                raw_model_json=None,
                payload=SourceEffectProviderDiscoveryPayload(
                    status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                    effects=(),
                    diagnostics=(),
                    errors=(error_message,),
                ),
                elapsed_time_ms=0,
                errors=(error_message,),
            )

        spans = self._build_evidence_spans(fragment)
        target_candidates = self._build_target_candidates(fragment, spans=spans)
        locator_candidates = self._build_locator_candidates(fragment, spans=spans)
        date_candidates = self._build_date_candidates(fragment, spans=spans)
        request_payload = self._build_chat_payload(
            fragment,
            spans=spans,
            target_candidates=target_candidates,
            locator_candidates=locator_candidates,
            date_candidates=date_candidates,
        )
        started_at = time.perf_counter()
        try:
            response_payload = self.transport(request_payload, self.timeout_seconds)
            elapsed_time_ms = int((time.perf_counter() - started_at) * 1000)
        except Exception as exc:
            message = f"Ollama source effect transport failed: {exc}"
            return OllamaSourceEffectDiscoveryExecution(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                contract_version=self.contract_version,
                raw_model_json=None,
                payload=SourceEffectProviderDiscoveryPayload(
                    status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                    effects=(),
                    diagnostics=(),
                    errors=(message,),
                ),
                elapsed_time_ms=int((time.perf_counter() - started_at) * 1000),
                errors=(message,),
            )

        raw_model_json = self._extract_raw_model_json(response_payload)
        try:
            parsed = self._parse_model_content(raw_model_json)
            validated = _OllamaSourceEffectResponseModel.model_validate(parsed)
            status = str(validated.status or "").strip().upper().replace("-", "_").replace(" ", "_")
            if status not in _ALLOWED_STATUSES:
                raise ValueError(f"Unsupported discovery status: {status}")

            materialized_effects: tuple[DiscoveredSourceEffect, ...] = ()
            if self.strict_bounded_contract:
                allowed_effect_keys = {
                    "effect_type",
                    "effect_scope",
                    "evidence_span_id",
                    "affected_locator_id",
                    "affected_target_id",
                    "effective_date_id",
                    "confidence",
                }
                effect_entries: list[dict[str, Any]] = []
                for item in validated.effects:
                    if not isinstance(item, dict):
                        raise ValueError("Strict bounded mode requires effect objects to be JSON objects")
                    prohibited = {
                        "evidence_excerpt",
                        "affected_document_ref_raw",
                        "target_id",
                        "span_id",
                        "affected_locator_raw",
                        "effective_date_raw",
                    }
                    unexpected = set(item) - allowed_effect_keys
                    if prohibited & set(item) or unexpected:
                        raise ValueError(
                            "Strict bounded mode rejected legacy or free-form fields: "
                            f"{sorted(set(item) - allowed_effect_keys | (prohibited & set(item)))}"
                        )
                    if "effect_type" not in item or "effect_scope" not in item or "evidence_span_id" not in item:
                        raise ValueError("Strict bounded output requires effect_type, effect_scope and evidence_span_id")
                    effect_entries.append(item)
                if status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS and effect_entries:
                    raise ValueError("NO_EFFECTS status cannot include effects")
                model_output = SourceEffectSelectionModelOutput(
                    status=status,
                    effects=tuple(
                        SourceEffectSelectionEffect(
                            effect_type=item["effect_type"],
                            effect_scope=item["effect_scope"],
                            evidence_span_id=item["evidence_span_id"],
                            affected_locator_id=item.get("affected_locator_id"),
                            affected_target_id=item.get("affected_target_id"),
                            effective_date_id=item.get("effective_date_id"),
                        )
                        for item in effect_entries
                    ),
                    diagnostics=tuple(str(item).strip() for item in validated.diagnostics if str(item).strip()),
                )
                selection_result = validate_and_materialize_selection(
                    model_output,
                    spans,
                    target_candidates=target_candidates,
                    locator_candidates=locator_candidates,
                    date_candidates=date_candidates,
                )
                target_map = {candidate.target_id: candidate for candidate in target_candidates}
                materialized_effects = tuple(
                    DiscoveredSourceEffect(
                        effect_type=effect.effect_type,
                        effect_scope=effect.effect_scope,
                        affected_document_ref_raw=(target_map[effect.affected_target_id].raw_text if effect.affected_target_id is not None else None),
                        affected_locator_raw=effect.affected_locator_raw,
                        effective_date_raw=effect.effective_date_raw,
                        evidence_excerpt=effect.evidence_excerpt or "",
                        confidence=None,
                    )
                    for effect in selection_result.effects
                )
            else:
                legacy_items = []
                for item in validated.effects:
                    if "evidence_span_id" in item or "affected_target_id" in item:
                        legacy_items.append(item)
                    else:
                        legacy_items.append(_OllamaLegacyDiscoveredSourceEffectModel.model_validate(item).model_dump())
                for item in legacy_items:
                    if "evidence_span_id" in item or "affected_target_id" in item:
                        continue
                    legacy = _OllamaLegacyDiscoveredSourceEffectModel.model_validate(item)
                    materialized_effects += (
                        DiscoveredSourceEffect(
                            effect_type=legacy.effect_type,
                            effect_scope=legacy.effect_scope,
                            affected_document_ref_raw=legacy.affected_document_ref_raw,
                            affected_locator_raw=legacy.affected_locator_raw,
                            effective_date_raw=legacy.effective_date_raw,
                            evidence_excerpt=legacy.evidence_excerpt,
                            confidence=legacy.confidence,
                        ),
                    )
                if status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS and materialized_effects:
                    raise ValueError("NO_EFFECTS status cannot include effects")
                if status in {SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED, SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED} and not materialized_effects:
                    raise ValueError(f"{status} requires at least one effect")

            if status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS:
                if validated.effects:
                    raise ValueError("NO_EFFECTS status cannot include effects")
                materialized_effects = ()
            elif status in {SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED, SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED}:
                valid_effects = tuple(effect for effect in materialized_effects if effect is not None)
                if not valid_effects:
                    raise ValueError(f"{status} requires at least one effect")
                materialized_effects = valid_effects
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            message = f"Ollama source effect response invalid: {exc}"
            return OllamaSourceEffectDiscoveryExecution(
                provider_name=self.provider_name,
                provider_version=self.provider_version,
                contract_version=self.contract_version,
                raw_model_json=raw_model_json,
                payload=SourceEffectProviderDiscoveryPayload(
                    status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
                    effects=(),
                    diagnostics=(),
                    errors=(message,),
                ),
                elapsed_time_ms=elapsed_time_ms,
                errors=(message,),
            )

        payload = SourceEffectProviderDiscoveryPayload(
            status=status,
            effects=materialized_effects,
            diagnostics=tuple(str(item).strip() for item in validated.diagnostics if str(item).strip()),
            errors=(),
        )

        return OllamaSourceEffectDiscoveryExecution(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            contract_version=self.contract_version,
            raw_model_json=raw_model_json,
            payload=payload,
            elapsed_time_ms=elapsed_time_ms,
        )

    def _build_chat_payload(
        self,
        fragment: SourceEffectSemanticFragment,
        *,
        spans: tuple[Any, ...],
        target_candidates: tuple[Any, ...],
        locator_candidates: tuple[Any, ...],
        date_candidates: tuple[Any, ...],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "think": False,
            "stream": False,
            "format": _OllamaSourceEffectResponseModel.model_json_schema(),
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(
                        fragment,
                        spans=spans,
                        target_candidates=target_candidates,
                        locator_candidates=locator_candidates,
                        date_candidates=date_candidates,
                    ),
                }
            ],
            "options": {
                "temperature": 0,
            },
        }
        if self.max_output_tokens is not None:
            payload["options"]["num_predict"] = int(self.max_output_tokens)
        return payload

    @staticmethod
    def _build_evidence_spans(fragment: SourceEffectSemanticFragment) -> tuple[Any, ...]:
        return build_source_effect_evidence_spans(
            fragment.source_text,
            source_method=fragment.source_method,
            source_artifact_key=fragment.source_artifact_key,
            document_page_id=fragment.document_page_id,
            source_locator=fragment.source_locator,
        )

    @staticmethod
    def _build_target_candidates(fragment: SourceEffectSemanticFragment, *, spans: tuple[Any, ...]) -> tuple[Any, ...]:
        return enumerate_source_effect_target_candidates(fragment.source_text, spans=spans)

    @staticmethod
    def _build_locator_candidates(fragment: SourceEffectSemanticFragment, *, spans: tuple[Any, ...]) -> tuple[Any, ...]:
        return enumerate_source_effect_locator_candidates(fragment.source_text, spans=spans)

    @staticmethod
    def _build_date_candidates(fragment: SourceEffectSemanticFragment, *, spans: tuple[Any, ...]) -> tuple[Any, ...]:
        return enumerate_source_effect_date_candidates(fragment.source_text, spans=spans)

    @staticmethod
    def _build_prompt(
        fragment: SourceEffectSemanticFragment,
        *,
        spans: tuple[Any, ...],
        target_candidates: tuple[Any, ...],
        locator_candidates: tuple[Any, ...],
        date_candidates: tuple[Any, ...],
    ) -> str:
        return (
            "You are a bounded source-effect selection assistant for a local procurement evaluation workflow. "
            "Return strict JSON only with no markdown, no code fences, no prose, no explanations. "
            "Use the provided literal evidence spans and target candidates only. "
            "Do not invent document references, do not invent targets, and do not emit free-form text outside the bounded schema. "
            "Documented source-effect detection is human-controlled and evidence-grounded: the model may abstain when the text does not clearly assert an operative documentary change. "
            "Do not decide legal precedence, governing source, winner document, obsolescence, or effective-source graph. "
            "A source effect exists only when the fragment asserts an operative documentary change over a source, clause, section, page, annex, requirement, or other bounded documentary content. "
            "Return NO_EFFECTS for non-operative mentions such as headings, concept definitions, procedure descriptions, future statements, clarification logistics, list entries, technical equipment changes, operating-parameter changes, personnel changes, commercial/price proposal changes, or bare revision labels without an operative documentary-change assertion. "
            "Use effect_type only from: SUPERSEDES, AMENDS, CORRECTS, CLARIFIES, SUPPLEMENTS, REVOKES, UNSPECIFIED. "
            "Use effect_scope only from: DOCUMENT_WIDE, PARTIAL, UNRESOLVED. "
            "If the source fragment contains a credible source effect but a safe target or scope cannot be determined, use REVIEW_REQUIRED with effects present only when the evidence is still bounded and no free-form fields are emitted. "
            "If no source effect exists, return status NO_EFFECTS with effects=[]. Never return DISCOVERED with empty effects. "
            "If the text is ambiguous, uncertain, or not safely representable, return REVIEW_REQUIRED with effects=[] and diagnostics; do not guess. "
            "The certification path is strict bounded. The only effect keys allowed are: effect_type, effect_scope, evidence_span_id, affected_target_id, affected_locator_id, effective_date_id, confidence. "
            "Do not emit evidence_excerpt. Do not emit affected_document_ref_raw. Do not emit target_id or any other free-form key. "
            "Select evidence_span_id from EVIDENCE_SPANS and then select affected_target_id, affected_locator_id, and effective_date_id only from candidate lists that belong to that same span. Keep each selector null when the bounded candidate is not present. Keep affected_target_id null when the segment does not identify a bounded target. "
            "If evidence is literal and target is unknown, keep the target null and use selector IDs only when the corresponding literal candidate appears inside the selected evidence span. "
            "The model must not generate locator or date text. Deterministic code reconstructs literal values from the selected IDs. "
            "Do not paraphrase, summarize, OCR-correct, spelling-correct, translate, or rewrite the evidence. "
            "Do not fabricate defaults or repair unknown values. No extra keys. Keep null values as null. "
            "Required response shape: {\"status\":\"DISCOVERED\",\"effects\":[{\"effect_type\":\"AMENDS\",\"effect_scope\":\"PARTIAL\",\"evidence_span_id\":\"span_001\",\"affected_target_id\":\"target_001\",\"affected_locator_id\":\"locator_001\",\"effective_date_id\":null,\"confidence\":null}],\"diagnostics\":[]} "
            "Bounded evidence selection contract: use the literal evidence spans and target candidates provided below. Select from the bounded schema only. "
            "EVIDENCE_SPANS:\n"
            f"{json.dumps([{'span_id': span.span_id, 'text': span.text} for span in spans], ensure_ascii=False)}\n"
            "TARGET_CANDIDATES:\n"
            f"{json.dumps([{'target_id': candidate.target_id, 'span_id': candidate.span_id, 'raw_text': candidate.raw_text} for candidate in target_candidates], ensure_ascii=False)}\n"
            "LOCATOR_CANDIDATES:\n"
            f"{json.dumps([{'locator_id': candidate.locator_id, 'span_id': candidate.span_id, 'raw_text': candidate.raw_text} for candidate in locator_candidates], ensure_ascii=False)}\n"
            "DATE_CANDIDATES:\n"
            f"{json.dumps([{'date_id': candidate.date_id, 'span_id': candidate.span_id, 'raw_text': candidate.raw_text} for candidate in date_candidates], ensure_ascii=False)}\n"
            "SOURCE_CONTEXT_BEGIN\n"
            f"SOURCE_METHOD: {fragment.source_method}\n"
            f"PAGE_NUMBER: {fragment.page_number}\n"
            f"SOURCE_LOCATOR: {fragment.source_locator}\n"
            "SOURCE_TEXT_BEGIN\n"
            f"{fragment.source_text}\n"
            "SOURCE_TEXT_END\n"
            "SOURCE_CONTEXT_END"
        )

    def _default_transport(self, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_raw_model_json(response_payload: dict[str, Any]) -> str:
        message = response_payload.get("message") if isinstance(response_payload, dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        response_value = response_payload.get("response") if isinstance(response_payload, dict) else None
        if isinstance(response_value, str):
            return response_value
        raise ValueError("Ollama source effect response does not contain JSON text content")

    @staticmethod
    def _parse_model_content(raw_model_json: str) -> dict[str, Any]:
        text = (raw_model_json or "").strip()
        if not text:
            raise ValueError("Ollama source effect response content is empty")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama source effect response is not a JSON object")
        if "status" not in parsed:
            raise ValueError("Ollama source effect response is missing status")
        if "effects" not in parsed:
            raise ValueError("Ollama source effect response is missing effects")
        if "diagnostics" not in parsed:
            raise ValueError("Ollama source effect response is missing diagnostics")
        return parsed


def run_ollama_source_effect_discovery(
    db: Session,
    fragment: SourceEffectSemanticFragment,
    *,
    provider: Optional[OllamaSourceEffectDiscoveryProvider] = None,
) -> OllamaSourceEffectDiscoveryRun:
    resolved_provider = provider or OllamaSourceEffectDiscoveryProvider()
    execution = resolved_provider.execute(fragment)

    if execution.errors:
        result = SourceEffectSemanticDiscoveryResult(
            provider_name=execution.provider_name,
            provider_version=execution.provider_version,
            contract_version=execution.contract_version,
            status=SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
            candidate_count=0,
            review_required_count=0,
            candidates=(),
            discovered_effects=(),
            diagnostics=execution.payload.diagnostics,
            errors=execution.errors,
        )
    else:
        class _ExecutedProvider:
            provider_name = execution.provider_name
            provider_version = execution.provider_version
            contract_version = execution.contract_version

            def supports(self, fragment: SourceEffectSemanticFragment) -> bool:
                return True

            def discover(self, fragment: SourceEffectSemanticFragment) -> SourceEffectProviderDiscoveryPayload:
                return execution.payload

        result = discover_source_effect_semantics(db, fragment, providers=(_ExecutedProvider(),))

    return OllamaSourceEffectDiscoveryRun(
        provider_name=execution.provider_name,
        provider_version=execution.provider_version,
        contract_version=execution.contract_version,
        raw_model_json=execution.raw_model_json,
        elapsed_time_ms=execution.elapsed_time_ms,
        result=result,
    )
