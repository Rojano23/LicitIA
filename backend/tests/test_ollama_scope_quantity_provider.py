from __future__ import annotations

import json

from app.ollama_scope_quantity_provider import (
    OLLAMA_SCOPE_QUANTITY_PROMPT_VERSION,
    _OllamaScopeQuantityResponseModel,
    OllamaScopeQuantitySemanticDiscoveryProvider,
    run_ollama_scope_quantity_discovery,
)
from app.scope_quantity_semantic_discovery import (
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    ScopeQuantitySemanticFragment,
    discover_scope_quantities,
)


def _fragment(*, source_method: str = "VISION", source_text: str) -> ScopeQuantitySemanticFragment:
    return ScopeQuantitySemanticFragment(
        tender_id="tender-1",
        scope_detail_id="scope-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=1,
        source_method=source_method,
        source_artifact_key="vision-page-result:pr-1",
        source_locator="page:1|detail_row:0",
        scope_detail_domain="SUPPLY",
        scope_detail_description="Suministrar material para ejecución.",
        source_text=source_text,
        source_contract_version="vision-detail-transcription-2026-08-31-001",
        source_analysis_id="analysis-1",
        source_page_result_id="pr-1",
    )


def _ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


def test_valid_discovered_json_maps_to_review_required_candidates() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.92,
                        }
                    ],
                }
            )
        ),
    )

    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))

    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1
    assert result.candidates[0].review_required is True


def test_valid_no_quantities_json() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_QUANTITIES","quantities":[]}'),
    )
    result = discover_scope_quantities(_fragment(source_text="24 VDC"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_NO_QUANTITIES


def test_valid_review_required_json() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"REVIEW_REQUIRED","quantities":[]}'),
    )
    result = discover_scope_quantities(_fragment(source_text="entregar a más tardar en 10 días"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED


def test_malformed_json_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response("{\"status\":\"DISCOVERED\""),
    )
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_markdown_fenced_json_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response("```json\n{\"status\":\"NO_QUANTITIES\",\"quantities\":[]}\n```"),
    )
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_prose_prefixed_json_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response("Here is the result: {\"status\":\"NO_QUANTITIES\",\"quantities\":[]}"),
    )
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_prose_suffixed_json_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_QUANTITIES","quantities":[]} trailing text'),
    )
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unknown_status_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"SOMETHING_ELSE","quantities":[]}'),
    )
    result = discover_scope_quantities(_fragment(source_text="x"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unknown_measure_kind_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "HEADCOUNT",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.7,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unknown_relation_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "ABOUT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.7,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_invalid_numeric_string_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "dos",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "2,5",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "dos técnicos",
                            "confidence": 0.7,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="dos técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_bad_confidence_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 1.5,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_grounding_failure_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "5",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "5",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "5 técnicos",
                            "confidence": 0.5,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_multiple_quantities_from_single_fragment_are_supported() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.9,
                        },
                        {
                            "quantity_raw": "5",
                            "unit_raw": "días",
                            "measure_kind": "DURATION",
                            "relation": "EXACT",
                            "quantity_value_raw": "5",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "5 días",
                            "confidence": 0.9,
                        },
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos durante 5 días"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 2


def test_provider_rejects_extra_forbidden_fields() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.9,
                            "scope_detail_id": "evil",
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_prompt_contains_barriers_and_text_only_invariants() -> None:
    captured_payloads: list[dict] = []

    def transport(payload, timeout):
        captured_payloads.append(payload)
        return _ollama_response('{"status":"NO_QUANTITIES","quantities":[]}')

    source = "Se suministrarán 2 válvulas de 4 pulgadas, clase 300."
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(model_name="qwen3:8b", transport=transport)
    run = run_ollama_scope_quantity_discovery(_fragment(source_text=source), provider=provider)

    assert run.contract_version == OLLAMA_SCOPE_QUANTITY_PROMPT_VERSION
    payload = captured_payloads[0]
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0
    assert "images" not in payload["messages"][0]

    prompt = payload["messages"][0]["content"]
    assert "Return strict JSON only" in prompt
    assert "Do not omit keys" in prompt
    assert "Do not classify as execution quantities" in prompt
    assert "For every DISCOVERED quantity always include quantity_raw, unit_raw, measure_kind, relation" in prompt
    assert "EXACT requires quantity_value_raw" in prompt
    assert "MINIMUM requires quantity_value_raw to be null" in prompt
    assert "MAXIMUM requires quantity_value_raw to be null" in prompt
    assert "RANGE requires quantity_value_raw to be null" in prompt
    assert "APPROXIMATE requires quantity_value_raw as a normalized numeric string" in prompt
    assert "quantity_raw must be the literal quantity expression from source evidence" in prompt
    assert "quantity_value_raw\":\"3\"" in prompt
    assert "24 VDC" in prompt
    assert "3/4 inch" in prompt
    assert "$25,000" in prompt
    assert "16% IVA" in prompt
    assert "2 válvulas de 4 pulgadas" in prompt
    assert "500 m de cable de 5 mm" in prompt
    assert "SOURCE_TEXT_BEGIN" in prompt
    assert source in prompt
    assert "PIEZA" not in prompt
    assert "UNA COPIA" not in prompt
    assert "PW481" not in prompt
    assert "Yokogawa" not in prompt
    assert "sq_golden_case" not in prompt
    assert "AFV10D" not in prompt
    assert "S9129" not in prompt
    assert "PIEZAS" not in prompt


def _is_nullable_property(prop: dict) -> bool:
    if prop.get("type") == ["string", "null"]:
        return True
    return any(item.get("type") == "null" for item in prop.get("anyOf", []) if isinstance(item, dict))


def test_contract_003_schema_requires_complete_quantity_keys_and_nullable_behavior() -> None:
    schema = _OllamaScopeQuantityResponseModel.model_json_schema()
    defs = schema.get("$defs", {})

    quantity_schema = None
    for entry in defs.values():
        if isinstance(entry, dict) and "properties" in entry and "quantity_raw" in entry["properties"]:
            quantity_schema = entry
            break

    assert quantity_schema is not None
    required = set(quantity_schema["required"])
    assert required == {
        "quantity_raw",
        "unit_raw",
        "measure_kind",
        "relation",
        "quantity_value_raw",
        "quantity_min_raw",
        "quantity_max_raw",
        "evidence_excerpt",
    }

    props = quantity_schema["properties"]
    assert _is_nullable_property(props["unit_raw"]) is True
    assert _is_nullable_property(props["quantity_value_raw"]) is True
    assert _is_nullable_property(props["quantity_min_raw"]) is True
    assert _is_nullable_property(props["quantity_max_raw"]) is True
    assert props["measure_kind"]["enum"] == ["COUNT", "LENGTH", "AREA", "VOLUME", "MASS", "DURATION", "PERSONNEL", "SERVICE", "LOT", "OTHER"]
    assert props["relation"]["enum"] == ["EXACT", "MINIMUM", "MAXIMUM", "RANGE", "APPROXIMATE", "UNSPECIFIED"]


def test_valid_complete_word_number_exact_object_is_accepted() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "tres",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "tres técnicos",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )

    result = discover_scope_quantities(_fragment(source_text="se requieren tres técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED


def test_missing_measure_kind_key_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_missing_relation_key_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_missing_unit_raw_key_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "measure_kind": "COUNT",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_unit_raw_null_is_structurally_allowed() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": None,
                            "measure_kind": "COUNT",
                            "relation": "EXACT",
                            "quantity_value_raw": "3",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_DISCOVERED


def test_missing_quantity_value_raw_key_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_quantity_value_raw_null_under_exact_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_value_raw": None,
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.95,
                        }
                    ],
                }
            )
        ),
    )
    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_missing_exact_quantity_value_raw_is_invalid_output() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "quantities": [
                        {
                            "quantity_raw": "3",
                            "unit_raw": "técnicos",
                            "measure_kind": "PERSONNEL",
                            "relation": "EXACT",
                            "quantity_min_raw": None,
                            "quantity_max_raw": None,
                            "evidence_excerpt": "3 técnicos",
                            "confidence": 0.92,
                        }
                    ],
                }
            )
        ),
    )

    result = discover_scope_quantities(_fragment(source_text="se requieren 3 técnicos"), providers=(provider,))

    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT


def test_missing_model_configuration_fails_closed() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(model_name="", transport=lambda payload, timeout: _ollama_response("{}"))
    result = discover_scope_quantities(_fragment(source_text="3 técnicos"), providers=(provider,))
    assert result.status == SCOPE_QUANTITY_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("No Ollama model configured" in error for error in result.errors)


def test_provider_supports_native_ocr_and_vision() -> None:
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_QUANTITIES","quantities":[]}'),
    )
    assert provider.supports(_fragment(source_method="NATIVE", source_text="x")) is True
    assert provider.supports(_fragment(source_method="OCR", source_text="x")) is True
    assert provider.supports(_fragment(source_method="VISION", source_text="x")) is True


def test_provider_run_metadata_and_raw_json() -> None:
    raw_json = '{"status":"NO_QUANTITIES","quantities":[]}'
    provider = OllamaScopeQuantitySemanticDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response(raw_json),
    )

    run = run_ollama_scope_quantity_discovery(_fragment(source_text="sin cantidades"), provider=provider)

    assert run.provider_name == "Ollama Scope Quantity Semantic Discovery"
    assert run.provider_version == "ollama-scope-quantity-provider-001"
    assert run.contract_version == OLLAMA_SCOPE_QUANTITY_PROMPT_VERSION
    assert run.raw_model_json == raw_json
    assert run.elapsed_time_ms >= 0
