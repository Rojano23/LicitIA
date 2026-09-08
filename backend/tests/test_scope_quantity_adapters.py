from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.scope_quantity_adapters import (
    SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE,
    SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED,
    SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES,
    SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED,
    ScopeQuantityEvidenceArtifact,
    VisionDetailTranscriptionScopeQuantityAdapter,
    run_scope_quantity_adapter,
)


def _artifact(
    *,
    source_method: str = "VISION",
    source_locator: str = "page:1|detail_row:0",
    scope_detail_excerpt: str = "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS (2 PIEZAS)",
    row: dict | None = None,
) -> ScopeQuantityEvidenceArtifact:
    resolved_row = row or {
        "raw_visible_text": "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS (2 PIEZAS)",
        "description": "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS",
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

    return ScopeQuantityEvidenceArtifact(
        tender_id="tender-1",
        scope_detail_id="scope-1",
        source_document_id="doc-1",
        document_page_id="page-1",
        page_number=1,
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
    adapter = VisionDetailTranscriptionScopeQuantityAdapter()
    assert adapter.supports(_artifact(source_method="VISION")) is True
    assert adapter.supports(_artifact(source_method="OCR")) is False
    assert adapter.supports(_artifact(source_method="NATIVE")) is False


def test_requires_detail_row_locator_for_deterministic_scope_grounding() -> None:
    adapter = VisionDetailTranscriptionScopeQuantityAdapter()
    assert adapter.supports(_artifact(source_locator="page:1")) is False


def test_extracts_terminal_parenthetical_quantity_exact_relation() -> None:
    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert str(candidate.quantity_value) == "2"
    assert candidate.quantity_raw == "2"
    assert candidate.unit_raw == "PIEZAS"
    assert candidate.relation == "EXACT"
    assert candidate.measure_kind == "COUNT"


def test_non_terminal_parenthetical_number_is_ignored() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO (2 PIEZAS) PARA AREA CRITICA",
        "description": "SUMINISTRAR MODULO",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO (2 PIEZAS) PARA AREA CRITICA"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES
    assert result.candidates == ()


def test_non_numeric_parenthetical_is_ignored() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO (DOS PIEZAS)",
        "description": "SUMINISTRAR MODULO",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO (DOS PIEZAS)"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES


def test_unsupported_unit_is_ignored_review_safe() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO (4 FOOUNITS)",
        "description": "SUMINISTRAR MODULO",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO (4 FOOUNITS)"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES


def test_rejects_when_parent_scope_excerpt_does_not_ground_row() -> None:
    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(scope_detail_excerpt="TEXTO INCOMPATIBLE"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE
    assert any("not grounded in parent scope detail excerpt" in error for error in result.errors)


def test_supported_row_without_terminal_quantity_returns_no_quantities() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS",
        "description": "SUMINISTRAR MODULO",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO DE ENTRADAS ANALOGICAS"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES


def test_unsupported_payload_task_type_is_non_destructive_unsupported() -> None:
    artifact = _artifact()
    payload = {
        "detail_transcription": {
            "task_type": "STRUCTURE_SCOPE",
            "parsed_supply_rows": [],
        }
    }
    artifact = ScopeQuantityEvidenceArtifact(
        tender_id=artifact.tender_id,
        scope_detail_id=artifact.scope_detail_id,
        source_document_id=artifact.source_document_id,
        document_page_id=artifact.document_page_id,
        page_number=artifact.page_number,
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
        result = run_scope_quantity_adapter(
            db,
            artifact,
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_UNSUPPORTED


def test_provenance_fields_are_preserved_exactly() -> None:
    locator = "page:7|detail_row:0|bbox:10,20,30,40"
    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(source_locator=locator, scope_detail_excerpt="SUMINISTRAR CABLE (12 METROS)", row={
                "raw_visible_text": "SUMINISTRAR CABLE (12 METROS)",
                "description": "SUMINISTRAR CABLE",
                "review_required": False,
            }),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED
    candidate = result.candidates[0]
    assert candidate.source_locator == locator
    assert candidate.source_analysis_id == "analysis-1"
    assert candidate.source_page_result_id == "pr-1"
    assert candidate.source_artifact_key == "vision-page-result:pr-1"
    assert candidate.source_method == "VISION"


@pytest.mark.parametrize(
    "token",
    [
        "24 VDC",
        "100-120 VCA",
        "4-20 mA",
        "±0.075 %",
        "Class 300",
        "ANSI 150",
        "IP66",
        "model 3051",
        "AA143-H50/K4400",
        "EC401-50",
        "2026",
        "3/4 inch",
    ],
)
def test_false_positive_tokens_do_not_materialize(token: str) -> None:
    row = {
        "raw_visible_text": f"ESPECIFICACION TECNICA ({token})",
        "description": "ESPECIFICACION TECNICA",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt=f"ESPECIFICACION TECNICA ({token})"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_NO_QUANTITIES
    assert result.candidates == ()


def test_extracts_one_piece_exact() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR EQUIPO DE RESPALDO (1 PIEZA)",
        "description": "SUMINISTRAR EQUIPO DE RESPALDO",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR EQUIPO DE RESPALDO (1 PIEZA)"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED
    candidate = result.candidates[0]
    assert candidate.quantity_raw == "1"
    assert candidate.unit_raw == "PIEZA"
    assert candidate.relation == "EXACT"
    assert candidate.review_required is False


def test_extracts_four_pieces_with_terminal_period() -> None:
    row = {
        "raw_visible_text": "SUMINISTRAR MODULO REDUNDANTE (4 PIEZAS).",
        "description": "SUMINISTRAR MODULO REDUNDANTE",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO REDUNDANTE (4 PIEZAS)."),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_MATERIALIZED
    candidate = result.candidates[0]
    assert candidate.quantity_raw == "4"
    assert candidate.quantity_value == 4
    assert candidate.unit_raw == "PIEZAS"


def test_empty_row_excerpt_is_invalid_evidence() -> None:
    row = {
        "raw_visible_text": "   ",
        "description": "",
        "review_required": False,
    }

    db = SessionLocal()
    try:
        result = run_scope_quantity_adapter(
            db,
            _artifact(row=row, scope_detail_excerpt="SUMINISTRAR MODULO"),
            adapters=(VisionDetailTranscriptionScopeQuantityAdapter(),),
        )
    finally:
        db.close()

    assert result.status == SCOPE_QUANTITY_ADAPTER_STATUS_INVALID_EVIDENCE
