from __future__ import annotations

import json

from app import document_structure_orchestrator as orchestrator_module
from app import local_vision as local_vision_module
from app import ocr as ocr_module
from app import ollama_vision as ollama_vision_module
from app.ollama_scope_semantic_provider import (
    ALLOWED_SCOPE_SEMANTIC_DOMAINS,
    OLLAMA_SCOPE_SEMANTIC_PROMPT_VERSION,
    OllamaScopeSemanticDiscoveryProvider,
    run_ollama_scope_semantic_discovery,
)
from app.scope_semantic_discovery import (
    SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS,
    SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED,
    ScopeSemanticSourceFragment,
    discover_scope_semantics,
)


def _fragment(*, source_method: str = "NATIVE", source_text: str) -> ScopeSemanticSourceFragment:
    return ScopeSemanticSourceFragment(
        tender_id="tender-1",
        source_document_id="document-1",
        document_page_id="page-1",
        page_number=1,
        source_method=source_method,
        source_artifact_key="artifact-1",
        source_locator="page:1|block:1",
        source_text=source_text,
        source_contract_version="native-text-v1",
    )


def _ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


def test_valid_multi_domain_response_discovers_three_candidates() -> None:
    source_text = (
        "EL PROVEEDOR DEBE CONTAR CON EL EQUIPO DE COMPUTO Y SOFTWARE NECESARIO PARA LA EJECUCION DE LOS SERVICIOS, "
        "INCLUYENDO LOS MEDIOS DE TRANSPORTE Y COMUNICACION CON RADIOS A PRUEBA DE EXPLOSION."
    )
    evidence = "INCLUYENDO LOS MEDIOS DE TRANSPORTE Y COMUNICACION CON RADIOS A PRUEBA DE EXPLOSION"
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "TOOLS_EQUIPMENT",
                            "description": "Contar con equipo de computo y software para la ejecucion",
                            "evidence_excerpt": source_text,
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.94,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        },
                        {
                            "domain": "TOOLS_EQUIPMENT",
                            "description": "Contar con radios a prueba de explosion para comunicacion",
                            "evidence_excerpt": evidence,
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.95,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        },
                        {
                            "domain": "LOGISTICS_SITE",
                            "description": "Contar con medios de transporte para la ejecucion",
                            "evidence_excerpt": evidence,
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.93,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        },
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(_fragment(source_text=source_text), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 3
    assert [candidate.domain for candidate in result.candidates] == [
        "TOOLS_EQUIPMENT",
        "TOOLS_EQUIPMENT",
        "LOGISTICS_SITE",
    ]


def test_empty_obligations_becomes_no_obligations() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response('{"obligations": []}'),
    )

    result = discover_scope_semantics(_fragment(source_text="INDICE GENERAL"), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS
    assert result.candidate_count == 0


def test_malformed_json_fails_closed() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response("Here is the answer: {\"obligations\": []}"),
    )

    result = discover_scope_semantics(_fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL."), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.candidate_count == 0


def test_markdown_fenced_json_fails_closed() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response("```json\n{\"obligations\": []}\n```"),
    )

    result = discover_scope_semantics(_fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL."), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.candidate_count == 0


def test_hallucinated_evidence_is_rejected_by_neutral_engine() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "SUPPLY",
                            "description": "Suministrar dos bombas",
                            "evidence_excerpt": "DEBERA SUMINISTRAR DOS BOMBAS",
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.98,
                            "quantity_raw": "2",
                            "unit_raw": "BOMBAS",
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(_fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL."), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("evidence_excerpt is not supported by source_text" in error for error in result.errors)


def test_invalid_domain_is_rejected_by_neutral_engine() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "ADMINISTRATIVE",
                            "description": "Presentar documentacion administrativa",
                            "evidence_excerpt": "PRESENTAR DOCUMENTACION ADMINISTRATIVA",
                            "review_required": True,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.66,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(_fragment(source_text="PRESENTAR DOCUMENTACION ADMINISTRATIVA"), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert any("Unsupported semantic domain: ADMINISTRATIVE" in error for error in result.errors)


def test_raw_quantity_and_unit_are_preserved() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "SUPPLY",
                            "description": "Suministrar bateria",
                            "evidence_excerpt": "SUMINISTRAR 4 PIEZAS DE BATERIA",
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.97,
                            "quantity_raw": "4",
                            "unit_raw": "PIEZAS",
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(_fragment(source_text="SUMINISTRAR 4 PIEZAS DE BATERIA"), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidates[0].quantity_raw == "4"
    assert result.candidates[0].unit_raw == "PIEZAS"


def test_review_required_and_confidence_are_preserved() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "TOOLS_EQUIPMENT",
                            "description": "Proveer radios de comunicacion",
                            "evidence_excerpt": "EL PROVEEDOR DEBE PROPORCIONAR RADIOS DE COMUNICACION",
                            "review_required": True,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.61,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(_fragment(source_text="EL PROVEEDOR DEBE PROPORCIONAR RADIOS DE COMUNICACION"), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_REVIEW_REQUIRED
    assert result.candidates[0].review_required is True
    assert result.candidates[0].confidence == 0.61


def test_provider_does_not_invent_ownership_ids() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "DELIVERABLE",
                            "description": "Entregar reporte final",
                            "evidence_excerpt": "EL PROVEEDOR ENTREGARA REPORTE FINAL.",
                            "review_required": True,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.72,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    run = run_ollama_scope_semantic_discovery(_fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL."), provider=provider)

    assert run.result.candidate_count == 1
    candidate = run.result.candidates[0]
    assert candidate.candidate_item_key is None
    assert not hasattr(candidate, "scope_segment_id")
    assert not hasattr(candidate, "tender_item_id")


def test_provider_supports_native_ocr_and_vision_equally() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response('{"obligations": []}'),
    )

    assert provider.supports(_fragment(source_method="NATIVE", source_text="X")) is True
    assert provider.supports(_fragment(source_method="OCR", source_text="X")) is True
    assert provider.supports(_fragment(source_method="VISION", source_text="X")) is True


def test_provider_unavailable_fails_safe_not_no_obligations() -> None:
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    result = discover_scope_semantics(_fragment(source_text="EL PROVEEDOR ENTREGARA REPORTE FINAL."), providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    assert result.status != SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS
    assert any("Ollama semantic transport failed" in error for error in result.errors)


def test_prompt_contract_contains_critical_invariants() -> None:
    captured_payloads: list[dict] = []

    def transport(payload, timeout):
        captured_payloads.append(payload)
        return _ollama_response('{"obligations": []}')

    source_text = "EL PROVEEDOR DEBE CONTAR CON RADIOS Y TRANSPORTE PARA LA EJECUCION"
    provider = OllamaScopeSemanticDiscoveryProvider(model_name="qwen3-vl:4b-instruct", transport=transport)
    run_ollama_scope_semantic_discovery(_fragment(source_text=source_text), provider=provider)

    payload = captured_payloads[0]
    assert payload["model"] == "qwen3-vl:4b-instruct"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0
    assert "images" not in payload["messages"][0]

    prompt = payload["messages"][0]["content"]
    assert source_text in prompt
    assert "SOURCE_TEXT_BEGIN" in prompt
    assert "SOURCE_TEXT_END" in prompt
    assert "Return JSON only" in prompt
    assert "every output obligation object must represent exactly one independently assessable execution obligation" in prompt
    assert "must not mix different execution concepts" in prompt
    assert "single compound sentence may produce multiple" in prompt
    assert "Cross-domain mixing is forbidden when separable" in prompt
    assert "TOOLS_EQUIPMENT plus LOGISTICS_SITE must be split" in prompt
    assert "TOOLS_EQUIPMENT plus DELIVERABLE must be split" in prompt
    assert "Within-domain atomicity also applies" in prompt
    assert "same domain may be separated" in prompt
    assert "words and structures such as y, asi como, incluyendo" in prompt
    assert "Description scope check before output" in prompt
    assert "do not summarize a compound sentence into one broad obligation" in prompt
    assert "most specific domain" in prompt
    assert "TECHNICAL is a fallback only" in prompt
    assert "Use DELIVERABLE only when the obligation itself is an output" in prompt
    assert "computadora para elaborar reportes is TOOLS_EQUIPMENT" in prompt
    assert "shortest sufficient contiguous evidence_excerpt" in prompt
    assert "Evidence scope check before output" in prompt
    assert "do not use the full sentence when a narrower span is available" in prompt
    assert "Each description must express one actionable obligation" in prompt
    assert "review_required is not automatically true" in prompt
    assert "Do not use confidence=0.0 as a placeholder" in prompt
    assert "Do not enforce a minimum candidate count" in prompt
    assert "do not assume at least 3 obligations" in prompt
    assert "Do not invent scope_segment_id or tender_item_id" in prompt
    assert "do not invent unsupported evidence" in prompt.lower()
    assert "multiple obligations" in prompt.lower()
    assert "administrative bid instructions" in prompt.lower()
    assert "Few-shot guidance example 1" in prompt
    assert "COMPUTADORA PORTATIL, RADIO DE COMUNICACION Y VEHICULO PARA TRASLADO AL SITIO" in prompt
    assert "three records" in prompt
    assert "Few-shot negative pattern" in prompt
    assert "BAD output is one TOOLS_EQUIPMENT obligation" in prompt
    assert "Few-shot guidance example 2" in prompt
    assert "Few-shot guidance example 3" in prompt
    assert "Expected pattern: zero execution obligations" in prompt
    assert "always return at least 3" not in prompt.lower()
    for domain in ALLOWED_SCOPE_SEMANTIC_DOMAINS:
        assert domain in prompt


def test_zero_acquisition_guard_holds_with_fake_transport(monkeypatch) -> None:
    fragment = _fragment(
        source_method="VISION",
        source_text=(
            "EL PROVEEDOR DEBE CONTAR CON EL EQUIPO DE COMPUTO Y SOFTWARE NECESARIO PARA LA EJECUCION DE LOS SERVICIOS, "
            "INCLUYENDO LOS MEDIOS DE TRANSPORTE Y COMUNICACION CON RADIOS A PRUEBA DE EXPLOSION."
        ),
    )

    def forbid_provider_acquisition(*args, **kwargs):
        raise AssertionError("acquisition must not run during semantic discovery")

    monkeypatch.setattr(ollama_vision_module, "analyze_vision_document", forbid_provider_acquisition)
    monkeypatch.setattr(ollama_vision_module, "analyze_vision_document_structure_only", forbid_provider_acquisition)
    monkeypatch.setattr(ollama_vision_module, "analyze_vision_document_structure_only_isolated", forbid_provider_acquisition)
    monkeypatch.setattr(local_vision_module.OllamaVisionProvider, "analyze_scope_pages", forbid_provider_acquisition)
    monkeypatch.setattr(orchestrator_module, "_default_vision_executor", forbid_provider_acquisition)
    monkeypatch.setattr(orchestrator_module, "_default_ocr_executor", forbid_provider_acquisition)
    monkeypatch.setattr(ocr_module.TesseractOCRProvider, "recognize", forbid_provider_acquisition)
    monkeypatch.setattr(ocr_module.PaddleOCRProvider, "recognize", forbid_provider_acquisition)

    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(
            json.dumps(
                {
                    "obligations": [
                        {
                            "domain": "TOOLS_EQUIPMENT",
                            "description": "Contar con equipo de computo y software para la ejecucion",
                            "evidence_excerpt": "EL PROVEEDOR DEBE CONTAR CON EL EQUIPO DE COMPUTO Y SOFTWARE NECESARIO PARA LA EJECUCION DE LOS SERVICIOS",
                            "review_required": False,
                            "detail_type": None,
                            "normalized_label": None,
                            "confidence": 0.93,
                            "quantity_raw": None,
                            "unit_raw": None,
                            "candidate_item_key": None,
                            "applicability_hint": None,
                        }
                    ]
                }
            )
        ),
    )

    result = discover_scope_semantics(fragment, providers=(provider,))

    assert result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
    assert result.candidate_count == 1


def test_provider_run_reports_raw_model_json_and_metadata() -> None:
    raw_json = '{"obligations": []}'
    provider = OllamaScopeSemanticDiscoveryProvider(
        model_name="qwen3-vl:4b-instruct",
        transport=lambda payload, timeout: _ollama_response(raw_json),
    )

    run = run_ollama_scope_semantic_discovery(_fragment(source_text="INDICE GENERAL"), provider=provider)

    assert run.provider_name == "Ollama Scope Semantic Discovery"
    assert run.provider_version
    assert run.contract_version == OLLAMA_SCOPE_SEMANTIC_PROMPT_VERSION
    assert run.contract_version == "scope-semantic-discovery-2026-09-04-003"
    assert run.raw_model_json == raw_json
    assert run.elapsed_time_ms >= 0
    assert run.result.status == SCOPE_SEMANTIC_DISCOVERY_STATUS_NO_OBLIGATIONS