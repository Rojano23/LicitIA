from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import DocumentPage, TenderDocument
from app.ollama_source_effect_provider import (
    OLLAMA_SOURCE_EFFECT_PROMPT_VERSION,
    OllamaSourceEffectDiscoveryProvider,
    run_ollama_source_effect_discovery,
)
from app.source_effect_semantic_discovery import (
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT,
    SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS,
    SourceEffectSemanticFragment,
    discover_source_effect_semantics,
)

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-OLLAMA-{uuid4()}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page(db, document_id: str, page_number: int, text: str) -> DocumentPage:
    page = DocumentPage(
        document_id=document_id,
        page_number=page_number,
        text=text,
        char_count=len(text),
        extraction_method="NATIVE_PDF",
        status="TEXT_EXTRACTED",
    )
    db.add(page)
    db.flush()

    document = db.get(TenderDocument, document_id)
    assert document is not None
    document.page_count = max(document.page_count, page_number)
    document.processing_status = "TEXT_EXTRACTION_COMPLETE"
    return page


def _fragment(*, tender_id: str, acting_document_id: str, document_page_id: str, source_text: str, source_method: str = "NATIVE") -> SourceEffectSemanticFragment:
    return SourceEffectSemanticFragment(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        document_page_id=document_page_id,
        page_number=1,
        source_method=source_method,
        source_artifact_key=f"native-page:{document_page_id}",
        source_locator="page:1",
        source_text=source_text,
        source_contract_version=OLLAMA_SOURCE_EFFECT_PROMPT_VERSION,
    )


def _ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


def test_valid_discovered_json_maps_to_semantic_candidate() -> None:
    tender_id = _create_tender("ollama source effect discovered")
    acting_doc_id = _import_pdf(tender_id, "junta.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige Anexo B, numeral 4.2.")
        _seed_page(db, affected_doc_id, 1, "contenido")
        db.commit()

        provider = OllamaSourceEffectDiscoveryProvider(
            model_name="qwen3:8b",
            transport=lambda payload, timeout: _ollama_response(
                json.dumps(
                    {
                        "status": "DISCOVERED",
                        "effects": [
                            {
                                "effect_type": "CORRECTS",
                                "effect_scope": "PARTIAL",
                                "affected_document_ref_raw": "Anexo B",
                                "affected_locator_raw": "numeral 4.2",
                                "effective_date_raw": None,
                                "evidence_excerpt": "Se corrige Anexo B, numeral 4.2.",
                                "confidence": 0.93,
                            }
                        ],
                        "diagnostics": [],
                    }
                )
            ),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=acting_page.id,
                source_text="Se corrige Anexo B, numeral 4.2.",
            ),
            providers=(provider,),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_DISCOVERED
        assert result.candidate_count == 1
        assert result.candidates[0].affected_document_id == affected_doc_id
        assert result.candidates[0].review_required is True
    finally:
        db.close()


def test_valid_no_effects_json() -> None:
    tender_id = _create_tender("ollama source effect no effects")
    acting_doc_id = _import_pdf(tender_id, "nota.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Documento actualizado Rev. 2")
        db.commit()

        provider = OllamaSourceEffectDiscoveryProvider(
            model_name="qwen3:8b",
            transport=lambda payload, timeout: _ollama_response('{"status":"NO_EFFECTS","effects":[],"diagnostics":[]}'),
        )

        result = discover_source_effect_semantics(
            db,
            _fragment(
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=page.id,
                source_text="Documento actualizado Rev. 2",
            ),
            providers=(provider,),
        )

        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS
        assert result.candidate_count == 0
    finally:
        db.close()


def test_malformed_json_is_invalid_output() -> None:
    provider = OllamaSourceEffectDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_EFFECTS"'),
    )

    db = SessionLocal()
    try:
        result = discover_source_effect_semantics(
            db,
            SourceEffectSemanticFragment(
                tender_id="t-1",
                acting_document_id="d-1",
                document_page_id="p-1",
                page_number=1,
                source_method="NATIVE",
                source_artifact_key="native-page:p-1",
                source_locator="page:1",
                source_text="x",
            ),
            providers=(provider,),
        )
        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    finally:
        db.close()


def test_markdown_and_prose_json_are_invalid_output() -> None:
    provider_markdown = OllamaSourceEffectDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response("```json\n{\"status\":\"NO_EFFECTS\",\"effects\":[],\"diagnostics\":[]}\n```"),
    )
    provider_prose = OllamaSourceEffectDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('Here is the output: {"status":"NO_EFFECTS","effects":[],"diagnostics":[]}'),
    )

    db = SessionLocal()
    try:
        fragment = SourceEffectSemanticFragment(
            tender_id="t-1",
            acting_document_id="d-1",
            document_page_id="p-1",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="native-page:p-1",
            source_locator="page:1",
            source_text="x",
        )

        result_markdown = discover_source_effect_semantics(db, fragment, providers=(provider_markdown,))
        result_prose = discover_source_effect_semantics(db, fragment, providers=(provider_prose,))

        assert result_markdown.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert result_prose.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    finally:
        db.close()


def test_missing_required_keys_and_unknown_status_fail_closed() -> None:
    provider_missing = OllamaSourceEffectDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_EFFECTS","effects":[]}'),
    )
    provider_unknown = OllamaSourceEffectDiscoveryProvider(
        model_name="qwen3:8b",
        transport=lambda payload, timeout: _ollama_response('{"status":"SOMETHING","effects":[],"diagnostics":[]}'),
    )

    db = SessionLocal()
    try:
        fragment = SourceEffectSemanticFragment(
            tender_id="t-1",
            acting_document_id="d-1",
            document_page_id="p-1",
            page_number=1,
            source_method="NATIVE",
            source_artifact_key="native-page:p-1",
            source_locator="page:1",
            source_text="x",
        )

        result_missing = discover_source_effect_semantics(db, fragment, providers=(provider_missing,))
        result_unknown = discover_source_effect_semantics(db, fragment, providers=(provider_unknown,))

        assert result_missing.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert result_unknown.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
    finally:
        db.close()


def test_hard_negative_contract_examples_do_not_create_candidates() -> None:
    examples = (
        "se modifica la presión de operación",
        "se sustituye la válvula",
        "se reemplaza el transmisor",
        "se adicionan dos técnicos",
        "se corrige el rango de señal",
        "Anexo modificado",
        "Versión revisada",
        "Documento actualizado",
        "Rev. 2",
        "Adenda No. 3",
        "Aclaración de dudas",
    )

    db = SessionLocal()
    try:
        for idx, text in enumerate(examples, start=1):
            fragment = SourceEffectSemanticFragment(
                tender_id=f"t-{idx}",
                acting_document_id=f"d-{idx}",
                document_page_id=f"p-{idx}",
                page_number=1,
                source_method="NATIVE",
                source_artifact_key=f"native-page:p-{idx}",
                source_locator="page:1",
                source_text=text,
            )
            provider = OllamaSourceEffectDiscoveryProvider(
                model_name="qwen3:8b",
                transport=lambda payload, timeout: _ollama_response('{"status":"NO_EFFECTS","effects":[],"diagnostics":[]}'),
            )
            result = discover_source_effect_semantics(db, fragment, providers=(provider,))
            assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_NO_EFFECTS
            assert result.candidate_count == 0
    finally:
        db.close()


def test_prompt_has_human_control_and_negative_safety_instructions() -> None:
    captured_payloads: list[dict] = []

    def transport(payload, timeout):
        captured_payloads.append(payload)
        return _ollama_response('{"status":"NO_EFFECTS","effects":[],"diagnostics":[]}')

    provider = OllamaSourceEffectDiscoveryProvider(model_name="qwen3:8b", transport=transport)

    db = SessionLocal()
    try:
        fragment = SourceEffectSemanticFragment(
            tender_id="t-1",
            acting_document_id="d-1",
            document_page_id="p-1",
            page_number=1,
            source_method="VISION",
            source_artifact_key="vision-page-result:1",
            source_locator="page:1",
            source_text="Se sustituye Anexo B por Anexo C.",
        )

        run = run_ollama_source_effect_discovery(db, fragment, provider=provider)
        assert run.contract_version == OLLAMA_SOURCE_EFFECT_PROMPT_VERSION

        payload = captured_payloads[0]
        assert payload["model"] == "qwen3:8b"
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["options"]["temperature"] == 0

        prompt = payload["messages"][0]["content"]
        assert "Do not decide legal precedence" in prompt
        assert "Technical or execution changes alone are not source effects" in prompt
        assert "Descriptive labels alone are not source effects" in prompt
        assert "SOURCE_TEXT_BEGIN" in prompt
        assert "SOURCE_TEXT_END" in prompt
    finally:
        db.close()


def test_provider_supports_native_ocr_vision_and_no_model_fails_safe() -> None:
    provider = OllamaSourceEffectDiscoveryProvider(
        model_name="",
        transport=lambda payload, timeout: _ollama_response('{"status":"NO_EFFECTS","effects":[],"diagnostics":[]}'),
    )

    fragment_native = SourceEffectSemanticFragment(
        tender_id="t-1",
        acting_document_id="d-1",
        document_page_id="p-1",
        page_number=1,
        source_method="NATIVE",
        source_artifact_key="native-page:p-1",
        source_locator="page:1",
        source_text="x",
    )
    fragment_ocr = SourceEffectSemanticFragment(
        tender_id="t-1",
        acting_document_id="d-1",
        document_page_id="p-1",
        page_number=1,
        source_method="OCR",
        source_artifact_key="ocr-result:o-1",
        source_locator="page:1|ocr_scope:FULL_PAGE",
        source_text="x",
    )
    fragment_vision = SourceEffectSemanticFragment(
        tender_id="t-1",
        acting_document_id="d-1",
        document_page_id="p-1",
        page_number=1,
        source_method="VISION",
        source_artifact_key="vision-page-result:v-1",
        source_locator="page:1",
        source_text="x",
    )

    assert provider.supports(fragment_native) is True
    assert provider.supports(fragment_ocr) is True
    assert provider.supports(fragment_vision) is True

    db = SessionLocal()
    try:
        result = discover_source_effect_semantics(db, fragment_native, providers=(provider,))
        assert result.status == SOURCE_EFFECT_SEMANTIC_DISCOVERY_STATUS_INVALID_OUTPUT
        assert any("No Ollama model configured" in err for err in result.errors)
    finally:
        db.close()
