from __future__ import annotations

import pytest

from app.source_effect_evidence_selection import (
    MAX_SOURCE_EFFECT_EVIDENCE_SPANS,
    SourceEffectEvidenceSpan,
    SourceEffectSelectionEffect,
    SourceEffectSelectionModelOutput,
    SourceEffectTargetCandidate,
    build_source_effect_evidence_spans,
    enumerate_source_effect_target_candidates,
    reconstruct_evidence_excerpt,
    validate_and_materialize_selection,
)


def test_evidence_spans_are_literal_and_bounded() -> None:
    text = (
        "Se modifica Anexo B, numeral 4.2. "
        "Se corrige la convocatoria para el procedimiento. "
        "Se aclara la condición de participación."
    )

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )

    assert len(spans) <= MAX_SOURCE_EFFECT_EVIDENCE_SPANS
    assert all(isinstance(span, SourceEffectEvidenceSpan) for span in spans)
    assert all(span.text in text for span in spans)
    assert all(span.text == text[span.start_offset : span.end_offset] for span in spans)
    assert [span.span_id for span in spans] == [f"span_{index:03d}" for index in range(1, len(spans) + 1)]
    assert spans[0].source_locator == "page:1"


def test_spans_are_deterministic_and_in_order() -> None:
    text = "Se modifica Anexo B. Se modifica la convocatoria. Se aclara el numeral 4.2."

    first = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )
    second = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )

    assert [span.text for span in first] == [span.text for span in second]
    assert [span.span_id for span in first] == [span.span_id for span in second]


def test_builder_does_not_mutate_source_text() -> None:
    text = "Se modifica Anexo B en su totalidad."
    original = text

    spans = build_source_effect_evidence_spans(
        text,
        source_method="OCR",
        source_artifact_key="ocr-result:abc",
        document_page_id="page-001",
        source_locator="page:1_ocr",
    )

    assert text == original
    assert spans[0].text == original


def test_target_candidates_are_literal_and_selectable() -> None:
    text = "Se modifica Anexo B, numeral 4.2, y la Convocatoria."

    targets = enumerate_source_effect_target_candidates(text)

    assert any(candidate.raw_text == "Anexo B" for candidate in targets)
    assert any(candidate.raw_text == "Convocatoria" for candidate in targets)
    assert all(isinstance(candidate, SourceEffectTargetCandidate) for candidate in targets)
    assert all(candidate.raw_text in text for candidate in targets)


def test_positive_synthetic_span_is_exact_literal() -> None:
    text = "Section 7 is modified to require two inspections."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:synthetic",
        document_page_id="page-09",
        source_locator="page:9",
    )

    assert len(spans) >= 1
    assert spans[0].text == text


def test_negative_synthetic_still_uses_limited_contract_without_asserting_effect() -> None:
    text = "The supplier may request clarification of the bidding rules. Modification means a change in the contract."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:neg",
        document_page_id="page-02",
        source_locator="page:2",
    )

    assert isinstance(spans, tuple)
    assert len(spans) <= MAX_SOURCE_EFFECT_EVIDENCE_SPANS


def test_no_anchor_positive_fragment_still_exposes_literal_span() -> None:
    text = "En adelante, la sección cuarta deberá interpretarse conforme a las condiciones que siguen."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:no-anchor-positive",
        document_page_id="page-11",
        source_locator="page:11",
    )

    assert len(spans) >= 1
    assert spans[0].text in text


def test_no_anchor_negative_fragment_still_exposes_literal_span() -> None:
    text = "El proveedor revisará la documentación y entregará el informe dentro del plazo establecido."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="OCR",
        source_artifact_key="ocr-result:no-anchor-negative",
        document_page_id="page-12",
        source_locator="page:12_ocr",
    )

    assert len(spans) >= 1
    assert spans[0].text in text


def test_anchor_priority_keeps_anchored_span_first() -> None:
    text = "La sede se mantiene operativa. Se modifica la sección cuarta para precisar la obligación. El comité revisará la programación."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:anchor-priority",
        document_page_id="page-13",
        source_locator="page:13",
    )

    assert len(spans) >= 2
    assert "Se modifica la sección cuarta" in spans[0].text
    assert all(spans[i].text in text for i in range(len(spans)))


def test_bounded_count_stays_under_cap_for_many_segments() -> None:
    text = " ".join(
        [
            "Frase uno del cuadro general.",
            "Frase dos del cuadro general.",
            "Frase tres del cuadro general.",
            "Frase cuatro del cuadro general.",
            "Frase cinco del cuadro general.",
            "Frase seis del cuadro general.",
            "Frase siete del cuadro general.",
            "Frase ocho del cuadro general.",
            "Frase nueve del cuadro general.",
            "Frase diez del cuadro general.",
            "Frase once del cuadro general.",
            "Frase doce del cuadro general.",
        ]
    )

    spans = build_source_effect_evidence_spans(
        text,
        source_method="NATIVE",
        source_artifact_key="native-page:many-segments",
        document_page_id="page-14",
        source_locator="page:14",
    )

    assert len(spans) <= MAX_SOURCE_EFFECT_EVIDENCE_SPANS
    assert len(spans) >= 1
    assert [span.span_id for span in spans] == [f"span_{index:03d}" for index in range(1, len(spans) + 1)]


def test_reconstructs_final_excerpt_from_selected_span() -> None:
    spans = build_source_effect_evidence_spans(
        "Se modifica Anexo B. Se aclara la convocatoria.",
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )

    selected = spans[1]
    model_output = SourceEffectSelectionModelOutput(
        status="DISCOVERED",
        effects=(
            SourceEffectSelectionEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                evidence_span_id=selected.span_id,
                affected_locator_raw="la convocatoria",
                affected_target_id=None,
                effective_date_raw=None,
            ),
        ),
        diagnostics=(),
    )

    result = validate_and_materialize_selection(model_output, spans, target_candidates=())
    assert result.status == "DISCOVERED"
    assert result.effects[0].evidence_excerpt == selected.text
    assert reconstruct_evidence_excerpt(model_output, spans) == (selected.text,)


def test_invalid_span_id_rejected() -> None:
    spans = build_source_effect_evidence_spans(
        "Se modifica Anexo B.",
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )

    model_output = SourceEffectSelectionModelOutput(
        status="DISCOVERED",
        effects=(
            SourceEffectSelectionEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                evidence_span_id="span_999",
                affected_locator_raw="Anexo B",
                affected_target_id=None,
                effective_date_raw=None,
            ),
        ),
        diagnostics=(),
    )

    with pytest.raises(ValueError, match="span_999"):
        validate_and_materialize_selection(model_output, spans, target_candidates=())


def test_invalid_target_id_rejected() -> None:
    spans = build_source_effect_evidence_spans(
        "Se modifica Anexo B.",
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )
    target_candidates = enumerate_source_effect_target_candidates("Se modifica Anexo B.")

    model_output = SourceEffectSelectionModelOutput(
        status="DISCOVERED",
        effects=(
            SourceEffectSelectionEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                evidence_span_id=spans[0].span_id,
                affected_locator_raw="Anexo B",
                affected_target_id="target_missing",
                effective_date_raw=None,
            ),
        ),
        diagnostics=(),
    )

    with pytest.raises(ValueError, match="target_missing"):
        validate_and_materialize_selection(model_output, spans, target_candidates=target_candidates)


def test_null_target_is_valid_for_review_required_case() -> None:
    spans = build_source_effect_evidence_spans(
        "Se modifica la Sección 7 para requerir dos inspecciones.",
        source_method="NATIVE",
        source_artifact_key="native-page:abc",
        document_page_id="page-001",
        source_locator="page:1",
    )

    model_output = SourceEffectSelectionModelOutput(
        status="REVIEW_REQUIRED",
        effects=(
            SourceEffectSelectionEffect(
                effect_type="AMENDS",
                effect_scope="PARTIAL",
                evidence_span_id=spans[0].span_id,
                affected_locator_raw="Sección 7",
                affected_target_id=None,
                effective_date_raw=None,
            ),
        ),
        diagnostics=("target unresolved",),
    )

    result = validate_and_materialize_selection(model_output, spans, target_candidates=())
    assert result.status == "REVIEW_REQUIRED"
    assert result.effects[0].affected_target_id is None
    assert result.effects[0].evidence_excerpt == spans[0].text


def test_ocr_whitespace_stays_grounded_in_literal_span() -> None:
    text = "Se modifica\nla\nSección\t7\npara requerir dos inspecciones."

    spans = build_source_effect_evidence_spans(
        text,
        source_method="OCR",
        source_artifact_key="ocr-result:abc",
        document_page_id="page-001",
        source_locator="page:1_ocr",
    )

    assert len(spans) >= 1
    assert spans[0].text in text
    assert "\n" in spans[0].text or "\t" in spans[0].text
