from __future__ import annotations

from app.database import SessionLocal
from app.scope_attribute_adapters import (
    SCOPE_ATTRIBUTE_ADAPTER_STATUS_INVALID_EVIDENCE,
    SCOPE_ATTRIBUTE_ADAPTER_STATUS_MATERIALIZED,
    SCOPE_ATTRIBUTE_ADAPTER_STATUS_NO_ATTRIBUTES,
    SCOPE_ATTRIBUTE_ADAPTER_STATUS_UNSUPPORTED,
    ScopeAttributeEvidenceArtifact,
    VisionDetailTranscriptionScopeAttributeAdapter,
    run_scope_attribute_adapter,
)


def _artifact(
    *,
    source_method: str = "VISION",
    source_locator: str = "page:1|detail_row:0",
    scope_detail_excerpt: str = "BOMBA YOKOGAWA MODELO YTA1100 CON SELLO SS316",
    row: dict | None = None,
) -> ScopeAttributeEvidenceArtifact:
    resolved_row = row or {
        "raw_visible_text": "BOMBA YOKOGAWA MODELO YTA1100 CON SELLO SS316",
        "description": "BOMBA YOKOGAWA MODELO YTA1100",
        "brand": "YOKOGAWA",
        "model": "YTA1100",
        "review_required": False,
    }
    payload = {
        "detail_transcription": {
            "task_type": "DETAIL_TRANSCRIPTION",
            "prompt_version": "vision-detail-transcription-2026-08-31-001",
            "source_page": 1,
            "parsed_supply_rows": [resolved_row],
        }
    }

    return ScopeAttributeEvidenceArtifact(
        tender_id="tender-1",
        scope_detail_id="scope-1",
        source_document_id="doc-1",
        document_page_id="page-1",
        source_method=source_method,
        source_artifact_key="vision-page-result:pr-1",
        source_locator=source_locator,
        scope_detail_excerpt=scope_detail_excerpt,
        source_contract_version="vision-detail-transcription-2026-08-31-001",
        source_analysis_id="analysis-1",
        source_page_result_id="pr-1",
        payload=payload,
        scope_detail_review_required=False,
    )


def test_supports_only_vision_detail_row_contract() -> None:
    adapter = VisionDetailTranscriptionScopeAttributeAdapter()
    assert adapter.supports(_artifact(source_method="VISION")) is True
    assert adapter.supports(_artifact(source_method="OCR")) is False
    assert adapter.supports(_artifact(source_method="NATIVE")) is False


def test_requires_detail_row_locator_for_deterministic_scope_grounding() -> None:
    adapter = VisionDetailTranscriptionScopeAttributeAdapter()
    assert adapter.supports(_artifact(source_locator="page:1")) is False


def test_extracts_explicit_brand_and_model_from_structured_row() -> None:
    db = SessionLocal()
    try:
        result = run_scope_attribute_adapter(
            db,
            _artifact(),
            adapters=(VisionDetailTranscriptionScopeAttributeAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_ATTRIBUTE_ADAPTER_STATUS_MATERIALIZED
    assert len(result.candidates) == 2
    names = sorted(candidate.attribute_name for candidate in result.candidates)
    assert names == ["brand", "model"]
    assert all(candidate.relation == "UNSPECIFIED" for candidate in result.candidates)


def test_supported_row_without_explicit_attribute_keys_returns_no_attributes() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO DE ENTRADAS",
        "description": "SUMINISTRAR MODULO DE ENTRADAS",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_attribute_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO DE ENTRADAS"),
            adapters=(VisionDetailTranscriptionScopeAttributeAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_ATTRIBUTE_ADAPTER_STATUS_NO_ATTRIBUTES
    assert result.candidates == ()


def test_rejects_when_parent_scope_excerpt_does_not_ground_row() -> None:
    db = SessionLocal()
    try:
        result = run_scope_attribute_adapter(
            db,
            _artifact(scope_detail_excerpt="TEXTO INCOMPATIBLE"),
            adapters=(VisionDetailTranscriptionScopeAttributeAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_ATTRIBUTE_ADAPTER_STATUS_INVALID_EVIDENCE
    assert any("not grounded in parent scope detail excerpt" in error for error in result.errors)


def test_rejects_when_explicit_value_is_not_grounded_in_source_excerpt() -> None:
    row = {
        "raw_visible_text": "TRANSMISOR MARCA YOKOGAWA",
        "description": "TRANSMISOR",
        "brand": "YOKOGAWA",
        "model": "YTA1100",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_attribute_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="TRANSMISOR MARCA YOKOGAWA"),
            adapters=(VisionDetailTranscriptionScopeAttributeAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_ATTRIBUTE_ADAPTER_STATUS_INVALID_EVIDENCE
    assert any("model value is not grounded in source_excerpt" in error for error in result.errors)


def test_unsupported_payload_task_type_is_non_destructive_unsupported() -> None:
    artifact = _artifact()
    payload = {
        "detail_transcription": {
            "task_type": "STRUCTURE_SCOPE",
            "parsed_supply_rows": [],
        }
    }
    artifact = ScopeAttributeEvidenceArtifact(
        tender_id=artifact.tender_id,
        scope_detail_id=artifact.scope_detail_id,
        source_document_id=artifact.source_document_id,
        document_page_id=artifact.document_page_id,
        source_method=artifact.source_method,
        source_artifact_key=artifact.source_artifact_key,
        source_locator=artifact.source_locator,
        scope_detail_excerpt=artifact.scope_detail_excerpt,
        source_contract_version=artifact.source_contract_version,
        source_analysis_id=artifact.source_analysis_id,
        source_page_result_id=artifact.source_page_result_id,
        payload=payload,
        scope_detail_review_required=artifact.scope_detail_review_required,
    )

    db = SessionLocal()
    try:
        result = run_scope_attribute_adapter(
            db,
            artifact,
            adapters=(VisionDetailTranscriptionScopeAttributeAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_ATTRIBUTE_ADAPTER_STATUS_UNSUPPORTED
