from __future__ import annotations

import json

from app.ollama_scope_attribute_provider import (
    OLLAMA_SCOPE_ATTRIBUTE_PROMPT_VERSION,
    OllamaScopeAttributeSemanticDiscoveryProvider,
    run_ollama_scope_attribute_discovery,
)
from app.scope_attribute_semantic_discovery import (
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    ScopeAttributeSemanticFragment,
    discover_scope_attributes,
)


def _fragment(*, source_method: str = "VISION", source_text: str) -> ScopeAttributeSemanticFragment:
    return ScopeAttributeSemanticFragment(
        tender_id="tender-1",
        scope_detail_id="scope-detail-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=1,
        source_method=source_method,
        source_artifact_key="scope-detail-1:vision",
        source_locator="page:1|block:2",
        scope_detail_domain="TECHNICAL",
        scope_detail_description="The supplier shall provide a pump set.",
        source_text=source_text,
        source_contract_version="scope-detail-v1",
    )


def _ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


def test_valid_multi_attribute_response_discovers_candidates_and_builds_text_only_prompt() -> None:
    source_text = "MOTOR DE 15 HP, MARCA ACME, MODELO ZX-10, TENSION 24 VDC."
    captured_payloads: list[dict] = []

    def transport(payload, timeout):
        captured_payloads.append(payload)
        return _ollama_response(
            json.dumps(
                {
                    "attributes": [
                        {
                            "attribute_name": "brand",
                            "value_raw": "ACME",
                            "evidence_excerpt": "MARCA ACME",
                            "attribute_label_raw": "MARCA",
                            "unit_raw": None,
                            "relation": "UNSPECIFIED",
                            "confidence": 0.96,
                        },
                        {
                            "attribute_name": "model",
                            "value_raw": "ZX-10",
                            "evidence_excerpt": "MODELO ZX-10",
                            "attribute_label_raw": "MODELO",
                            "unit_raw": None,
                            "relation": "UNSPECIFIED",
                            "confidence": 0.95,
                        },
                        {
                            "attribute_name": "power_supply",
                            "value_raw": "24 VDC",
                            "evidence_excerpt": "TENSION 24 VDC",
                            "attribute_label_raw": "TENSION",
                            "unit_raw": "VDC",
                            "relation": "EXACT",
                            "confidence": 0.91,
                        },
                    ]
                }
            )
        )

    provider = OllamaScopeAttributeSemanticDiscoveryProvider(model_name="qwen3:8b", transport=transport)

    result = discover_scope_attributes(_fragment(source_text=source_text), providers=(provider,))
    run = run_ollama_scope_attribute_discovery(_fragment(source_text=source_text), provider=provider)

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 3
    assert [candidate.attribute_name for candidate in result.candidates] == ["brand", "model", "power_supply"]
    assert result.candidates[0].relation == "UNSPECIFIED"
    assert result.candidates[2].unit_raw == "VDC"
    assert run.contract_version == OLLAMA_SCOPE_ATTRIBUTE_PROMPT_VERSION
    assert run.raw_model_json == json.dumps(
        {
            "attributes": [
                {
                    "attribute_name": "brand",
                    "value_raw": "ACME",
                    "evidence_excerpt": "MARCA ACME",
                    "attribute_label_raw": "MARCA",
                    "unit_raw": None,
                    "relation": "UNSPECIFIED",
                    "confidence": 0.96,
                },
                {
                    "attribute_name": "model",
                    "value_raw": "ZX-10",
                    "evidence_excerpt": "MODELO ZX-10",
                    "attribute_label_raw": "MODELO",
                    "unit_raw": None,
                    "relation": "UNSPECIFIED",
                    "confidence": 0.95,
                },
                {
                    "attribute_name": "power_supply",
                    "value_raw": "24 VDC",
                    "evidence_excerpt": "TENSION 24 VDC",
                    "attribute_label_raw": "TENSION",
                    "unit_raw": "VDC",
                    "relation": "EXACT",
                    "confidence": 0.91,
                },
            ]
        }
    )

    payload = captured_payloads[0]
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0
    assert "images" not in payload["messages"][0]

    prompt = payload["messages"][0]["content"]
    assert "Do not infer attributes from document type" in prompt
    assert "The model cannot control review_required" in prompt
    assert "Do not emit normalized_name" in prompt
    assert "Use only these relation values" in prompt
    assert "SOURCE_TEXT_BEGIN" in prompt
    assert "SOURCE_TEXT_END" in prompt
    assert source_text in prompt


def test_markdown_fenced_json_fails_closed() -> None:
    provider = OllamaScopeAttributeSemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response("```json\n{\"attributes\": []}\n```"),
    )

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.candidate_count == 0


def test_prose_wrapped_json_fails_closed() -> None:
    provider = OllamaScopeAttributeSemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('Here is the JSON: {"attributes": []}'),
    )

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("Ollama attribute response invalid" in error for error in result.errors)


def test_extra_fields_are_rejected_by_the_strict_schema() -> None:
    provider = OllamaScopeAttributeSemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "attributes": [
                        {
                            "attribute_name": "brand",
                            "value_raw": "ACME",
                            "evidence_excerpt": "MARCA ACME",
                            "attribute_label_raw": "MARCA",
                            "unit_raw": None,
                            "relation": "UNSPECIFIED",
                            "confidence": 0.92,
                            "review_required": False,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("extra inputs are not permitted" in error.lower() or "extra field" in error.lower() for error in result.errors)


def test_provider_unavailable_fails_safe_not_no_attributes() -> None:
    provider = OllamaScopeAttributeSemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    result = discover_scope_attributes(_fragment(source_text="MARCA ACME"), providers=(provider,))

    assert result.status == SCOPE_ATTRIBUTE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("Ollama attribute transport failed" in error for error in result.errors)


def test_provider_supports_native_ocr_and_vision_equally() -> None:
    provider = OllamaScopeAttributeSemanticDiscoveryProvider(model_name="qwen3:8b", transport=lambda payload, timeout: _ollama_response('{"attributes": []}'))

    assert provider.supports(_fragment(source_method="NATIVE", source_text="X")) is True
    assert provider.supports(_fragment(source_method="OCR", source_text="X")) is True
    assert provider.supports(_fragment(source_method="VISION", source_text="X")) is True
