from __future__ import annotations

import re
from dataclasses import dataclass, replace

MAX_SOURCE_EFFECT_EVIDENCE_SPANS = 5

_SELECTION_STATUSES = {"NO_EFFECTS", "DISCOVERED", "REVIEW_REQUIRED", "INVALID_OUTPUT"}
_EFFECT_ANCHOR_PATTERN = re.compile(
    r"\b(?:se\s+)?(?:modific(?:a|an|ó|arse)|modified|revis(?:a|an|ó)|sustituy(?:e|en|ó)|reemplaz(?:a|an|ó)|corrig(?:e|en|ió)|aclar(?:a|an|ó)|adicion(?:a|an|ó)|complement(?:a|an|ó)|revoc(?:a|an|ó)|qued(?:a|an)\s+sin\s+efecto|deja(?:n)?\s+sin\s+efecto|modificaci[oó]n|amend(?:ed|s)|supersed(?:es|ed)|clarif(?:y|ies|ied)|correct(?:ed|s)|supplement(?:s|ed)|revok(?:e|es)|amend)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SourceEffectEvidenceSpan:
    span_id: str
    source_method: str
    source_artifact_key: str
    document_page_id: str | None
    source_locator: str
    text: str
    start_offset: int
    end_offset: int

    def validate(self) -> None:
        if self.start_offset < 0 or self.end_offset < self.start_offset:
            raise ValueError(f"Invalid offsets for span_id={self.span_id}")
        if self.end_offset - self.start_offset != len(self.text):
            raise ValueError(f"Span text length does not match offsets for span_id={self.span_id}")


@dataclass(frozen=True, slots=True)
class SourceEffectTargetCandidate:
    target_id: str
    raw_text: str


@dataclass(frozen=True, slots=True)
class SourceEffectSelectionEffect:
    effect_type: str
    effect_scope: str
    evidence_span_id: str
    affected_locator_raw: str | None = None
    affected_target_id: str | None = None
    effective_date_raw: str | None = None
    evidence_excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class SourceEffectSelectionModelOutput:
    status: str
    effects: tuple[SourceEffectSelectionEffect, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceEffectSelectionResult:
    status: str
    effects: tuple[SourceEffectSelectionEffect, ...]
    diagnostics: tuple[str, ...] = ()


def build_source_effect_evidence_spans(
    source_text: str,
    *,
    source_method: str,
    source_artifact_key: str,
    document_page_id: str | None,
    source_locator: str,
    max_spans: int = MAX_SOURCE_EFFECT_EVIDENCE_SPANS,
) -> tuple[SourceEffectEvidenceSpan, ...]:
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if max_spans <= 0:
        return ()

    if not source_text.strip():
        return ()

    segments = _candidate_literal_segments(source_text)
    if not segments:
        return ()

    anchor_segments: list[tuple[int, int, str]] = []
    fallback_segments: list[tuple[int, int, str]] = []
    for start, end, chunk in segments:
        if _EFFECT_ANCHOR_PATTERN.search(chunk):
            anchor_segments.append((start, end, chunk))
        else:
            fallback_segments.append((start, end, chunk))

    ordered_segments = anchor_segments + fallback_segments
    bounded_segments = ordered_segments[:max_spans]

    selected: list[SourceEffectEvidenceSpan] = []
    for index, (start, end, text) in enumerate(bounded_segments, start=1):
        selected.append(
            SourceEffectEvidenceSpan(
                span_id=f"span_{index:03d}",
                source_method=str(source_method).upper(),
                source_artifact_key=str(source_artifact_key),
                document_page_id=document_page_id,
                source_locator=str(source_locator),
                text=text,
                start_offset=start,
                end_offset=end,
            )
        )

    return tuple(selected)


def _candidate_literal_segments(source_text: str) -> list[tuple[int, int, str]]:
    text = source_text or ""
    if not text.strip():
        return []

    segments: list[tuple[int, int, str]] = []
    buffer: list[str] = []
    start_index = 0

    for idx, char in enumerate(text):
        if char in ".!?":
            prev_char = text[idx - 1] if idx > 0 else ""
            next_char = text[idx + 1] if idx + 1 < len(text) else ""
            if prev_char.isdigit() and next_char.isdigit():
                buffer.append(char)
                continue

            if buffer:
                buffer.append(char)
            else:
                buffer = [char]
                start_index = idx

            chunk = "".join(buffer)
            if chunk.strip():
                segments.append((start_index, idx + 1, chunk))
            buffer = []
            start_index = idx + 1
        else:
            if not buffer:
                start_index = idx
            buffer.append(char)

    if buffer:
        chunk = "".join(buffer)
        if chunk.strip():
            segments.append((start_index, len(text), chunk))

    if segments:
        return segments

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunk_size = max(1, min(len(normalized), 240))
    start = 0
    for index in range(0, len(normalized), chunk_size):
        chunk = normalized[index : index + chunk_size]
        if not chunk.strip():
            continue
        literal_start = text.find(chunk, start)
        if literal_start < 0:
            literal_start = start
        literal_end = literal_start + len(chunk)
        segments.append((literal_start, literal_end, text[literal_start:literal_end]))
        start = literal_end

    return segments


def enumerate_source_effect_target_candidates(source_text: str) -> tuple[SourceEffectTargetCandidate, ...]:
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")

    patterns: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bAnexo\s+[A-Za-z0-9]+(?:[-\.]?[A-Za-z0-9]+)*\b", re.IGNORECASE),
        re.compile(r"\bBases(?:\s+de\s+Licitaci[oó]n)?\b", re.IGNORECASE),
        re.compile(r"\bConvocatoria\b", re.IGNORECASE),
        re.compile(r"\b(?:Secci[oó]n|Apartado|Numeral|Cl[aá]usula|Inciso|P[aá]rrafo)\s+[A-Za-z0-9IVXLCDM\.\-]+\b", re.IGNORECASE),
    )

    seen: set[str] = set()
    results: list[SourceEffectTargetCandidate] = []
    for pattern in patterns:
        for match in pattern.finditer(source_text):
            raw_text = match.group(0)
            key = " ".join(raw_text.split()).upper()
            if key in seen:
                continue
            seen.add(key)
            results.append(SourceEffectTargetCandidate(target_id=f"target_{len(results) + 1:03d}", raw_text=raw_text))
    return tuple(results)


def validate_and_materialize_selection(
    model_output: SourceEffectSelectionModelOutput,
    spans: tuple[SourceEffectEvidenceSpan, ...],
    *,
    target_candidates: tuple[SourceEffectTargetCandidate, ...] = (),
) -> SourceEffectSelectionResult:
    status = str(model_output.status or "").strip().upper().replace("-", "_").replace(" ", "_")
    if status not in _SELECTION_STATUSES:
        raise ValueError(f"Unsupported selection status: {model_output.status!r}")

    if status == "NO_EFFECTS":
        if model_output.effects:
            raise ValueError("NO_EFFECTS status cannot include effects")
        return SourceEffectSelectionResult(status=status, effects=(), diagnostics=model_output.diagnostics)

    if status in {"DISCOVERED", "REVIEW_REQUIRED"} and not model_output.effects:
        raise ValueError(f"{status} requires at least one effect")

    span_map = {span.span_id: span for span in spans}
    target_map = {candidate.target_id: candidate for candidate in target_candidates}

    materialized: list[SourceEffectSelectionEffect] = []
    for effect in model_output.effects:
        if effect.evidence_span_id not in span_map:
            raise ValueError(f"Unknown evidence_span_id: {effect.evidence_span_id}")
        span = span_map[effect.evidence_span_id]

        if effect.affected_locator_raw is not None and effect.affected_locator_raw not in span.text:
            raise ValueError(f"affected_locator_raw is not grounded in span {effect.evidence_span_id}")
        if effect.effective_date_raw is not None and effect.effective_date_raw not in span.text:
            raise ValueError(f"effective_date_raw is not grounded in span {effect.evidence_span_id}")
        if effect.affected_target_id is not None and effect.affected_target_id not in target_map:
            raise ValueError(f"Unknown affected_target_id: {effect.affected_target_id}")

        materialized.append(
            SourceEffectSelectionEffect(
                effect_type=effect.effect_type,
                effect_scope=effect.effect_scope,
                evidence_span_id=effect.evidence_span_id,
                affected_locator_raw=effect.affected_locator_raw,
                affected_target_id=effect.affected_target_id,
                effective_date_raw=effect.effective_date_raw,
                evidence_excerpt=span.text,
            )
        )

    return SourceEffectSelectionResult(status=status, effects=tuple(materialized), diagnostics=model_output.diagnostics)


def reconstruct_evidence_excerpt(
    model_output: SourceEffectSelectionModelOutput,
    spans: tuple[SourceEffectEvidenceSpan, ...],
    *,
    target_candidates: tuple[SourceEffectTargetCandidate, ...] = (),
) -> tuple[str, ...]:
    result = validate_and_materialize_selection(model_output, spans, target_candidates=target_candidates)
    return tuple(effect.evidence_excerpt for effect in result.effects)
