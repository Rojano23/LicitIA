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
    """Verify contract004 includes all five rules and critical instructions."""
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

    # RULE 1: Execution Scope Gate
    assert "RULE 1: EXECUTION SCOPE GATE" in prompt
    assert "Does this source fragment establish an obligation" in prompt
    assert "Execution scope means what the contractor must DO" in prompt

    # RULE 2: Domain Discrimination
    assert "RULE 2: DOMAIN DECISION RULES" in prompt
    assert "EXACTLY one of these nine domains" in prompt
    assert "TECHNICAL" in prompt
    assert "SERVICE" in prompt
    assert "SUPPLY" in prompt

    # RULE 3: OTHER is not a fallback
    assert "RULE 3: OTHER MUST NEVER HIDE NON-SCOPE" in prompt
    assert "OTHER IS NOT A FALLBACK CATEGORY" in prompt

    # RULE 4: Contractual Atomicity
    assert "RULE 4: CONTRACTUAL ATOMICITY" in prompt
    assert "Every output obligation must represent exactly one independently meaningful contractual commitment" in prompt
    assert "Split when the same source fragment contains multiple INDEPENDENT obligations" in prompt
    assert "OVER-GROUPING" in prompt
    assert "OVER-SEGMENTATION" in prompt

    # RULE 5: Evidence Must Be Verbatim
    assert "RULE 5: EVIDENCE MUST BE VERBATIM" in prompt
    assert "copied VERBATIM from SOURCE_TEXT" in prompt
    assert "contiguous" in prompt
    assert "Do not invent unsupported evidence" in prompt

    # Verify all nine domains are present
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
    assert run.contract_version == "scope-semantic-discovery-2026-09-08-004"
    assert run.raw_model_json == raw_json
    assert run.elapsed_time_ms >= 0


# ========================================================================================================
# DETERMINISTIC TESTS FOR SEMANTIC PROMPT CONTRACT 004
# These tests verify the five architect-defined classification rules are encoded in the prompt
# without invoking Ollama.
# ========================================================================================================


def test_prompt_contract_004_contains_execution_scope_gate_rule() -> None:
    """RULE 1: Execution Gate must be the first semantic decision."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify execution gate concepts are explicitly documented
    assert "RULE 1: EXECUTION SCOPE GATE" in prompt
    assert "Does this source fragment establish an obligation" in prompt
    assert "If NO, return no obligation" in prompt
    assert "Execution scope means what the contractor must DO" in prompt

    # Verify bidder qualification is excluded from execution scope
    assert "Bidder qualification" in prompt
    assert "Proof of experience" in prompt
    assert "Proposal submission requirements" in prompt
    assert "Procurement forms" in prompt

    # Verify classification is NOT based on document type
    assert "Do NOT use document type as a filter" in prompt
    assert "Classify the OBLIGATION itself, not the document type" in prompt


def test_prompt_contract_004_contains_nine_domain_definitions() -> None:
    """RULE 2: Domain definitions must be explicit for all nine domains."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify all nine domains are documented with semantic definitions
    assert "RULE 2: DOMAIN DECISION RULES" in prompt
    assert "EXACTLY one of these nine domains" in prompt

    # Verify each domain is explicitly defined
    domains = [
        "TECHNICAL",
        "SERVICE",
        "SUPPLY",
        "TOOLS_EQUIPMENT",
        "PERSONNEL",
        "SSPA",
        "DELIVERABLE",
        "LOGISTICS_SITE",
        "OTHER",
    ]
    for domain in domains:
        assert domain in prompt

    # Verify domain definitions distinguish concepts
    assert "technical execution methods" in prompt
    assert "service/action to be performed" in prompt
    assert "materials, consumables, spare parts" in prompt
    assert "equipment, tools, machinery" in prompt
    assert "execution personnel requirements" in prompt
    assert "operational safety" in prompt
    assert "output that must be produced/delivered" in prompt
    assert "physical execution location" in prompt


def test_prompt_contract_004_other_is_not_fallback() -> None:
    """RULE 3: OTHER must never hide non-scope; NOT a fallback category."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify OTHER is explicitly NOT a fallback
    assert "RULE 3: OTHER MUST NEVER HIDE NON-SCOPE" in prompt
    assert "OTHER IS NOT A FALLBACK CATEGORY" in prompt

    # Verify the decision sequence is clear
    assert "STEP 1: Is this actual execution scope?" in prompt
    assert "STEP 2: Which specific execution domain applies?" in prompt
    assert "STEP 3: Only if none fits, but it IS definitely execution scope" in prompt

    # Verify anti-patterns are explicit
    assert "Do NOT perform: uncertain → OTHER" in prompt
    assert "Do NOT perform: mandatory administrative language → OTHER" in prompt
    assert "Do NOT perform: documentation mentioned → DELIVERABLE" in prompt


def test_prompt_contract_004_contains_contractual_atomicity_rule() -> None:
    """RULE 4: Contractual atomicity governs splitting and grouping decisions."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify atomicity rule is explicit
    assert "RULE 4: CONTRACTUAL ATOMICITY" in prompt
    assert "Every output obligation must represent exactly one independently meaningful contractual commitment" in prompt

    # Verify splitting guidance
    assert "Split when the same source fragment contains multiple INDEPENDENT obligations" in prompt

    # Verify over-segmentation danger is documented
    assert "OVER-SEGMENTATION" in prompt
    assert "one obligation exploded into every descriptive phrase" in prompt

    # Verify over-grouping danger is documented
    assert "OVER-GROUPING" in prompt
    assert "multiple independent obligations collapsed into one" in prompt

    # Verify the guiding question is present
    assert "Could this candidate reasonably be reviewed as a separate contractual commitment?" in prompt


def test_prompt_contract_004_evidence_must_be_verbatim() -> None:
    """RULE 5: Evidence must be verbatim, contiguous, and exact source copy."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify verbatim evidence rule is explicit
    assert "RULE 5: EVIDENCE MUST BE VERBATIM" in prompt
    assert "evidence_excerpt MUST be:" in prompt

    # Verify all verbatim requirements are listed
    assert "copied VERBATIM from SOURCE_TEXT" in prompt
    assert "contiguous" in prompt
    assert "not paraphrased" in prompt
    assert "not corrected" in prompt
    assert "not translated" in prompt
    assert "not normalized by the model" in prompt
    assert "not combined from non-contiguous spans" in prompt

    # Verify description vs evidence distinction is clear
    assert "The description may normalize wording semantically" in prompt
    assert "but evidence_excerpt must remain verbatim grounded" in prompt

    # Verify "no invent" is explicit
    assert "Do not invent unsupported evidence" in prompt


def test_prompt_contract_004_json_strict_requirement() -> None:
    """Contract 004 must preserve strict JSON-only output requirement."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify strict JSON requirement is maintained
    assert "Return JSON only" in prompt
    assert "no markdown" in prompt
    assert "no prose" in prompt
    assert "no explanation" in prompt
    assert "no reasoning trace" in prompt
    assert "no code fences" in prompt


def test_prompt_contract_004_no_golden_examples_encoded() -> None:
    """Contract 004 must NOT encode specific Golden case IDs or examples."""
    fragment = _fragment(source_text="dummy")
    provider = OllamaScopeSemanticDiscoveryProvider()
    prompt = provider._build_prompt(fragment)

    # Verify no Golden-specific content
    # (Checking for patterns that would indicate overfitting to the frozen Golden)
    assert "HIIP" not in prompt, "Golden-specific registry name should not be in prompt"
    assert "PLDD" not in prompt, "Golden-specific acronym should not be in prompt"
    assert "NOM-251" not in prompt, "Golden-specific standard should not be in prompt"
    assert "MTBE" not in prompt, "Golden-specific facility should not be in prompt"
    assert "Yokogawa" not in prompt, "Golden-specific equipment brand should not be in prompt"
    assert "Cadereyta" not in prompt, "Golden-specific location should not be in prompt"

    # Verify no semantic contamination from frozen worked-example combinations
    assert "obtain a work permit" not in prompt
    assert "use a specialized crew" not in prompt
    assert "follow a technical maintenance procedure" not in prompt
    assert "temperature control, storage rotation" not in prompt
    assert "service within 35 days" not in prompt

    # Verify replacement examples are generic and unrelated to frozen Golden cases
    assert "package components for transport" in prompt
    assert "maintain an inventory record" in prompt
    assert "restore the work area after completion" in prompt
    assert "inspection checklist" in prompt

    # Verify general rule encoding instead
    assert "Classify the OBLIGATION itself" in prompt, "General reasoning should replace specific examples"


def test_prompt_contract_004_version_metadata_correct() -> None:
    """Verify contract version metadata is updated to 004."""
    provider = OllamaScopeSemanticDiscoveryProvider()

    # Verify provider reports correct version
    assert provider.contract_version == "scope-semantic-discovery-2026-09-08-004"
    assert OLLAMA_SCOPE_SEMANTIC_PROMPT_VERSION == "scope-semantic-discovery-2026-09-08-004"
