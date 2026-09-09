from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TenderDocument
from app.source_effect_adapters import (
    SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE,
    SOURCE_EFFECT_ADAPTER_STATUS_MATERIALIZED,
    SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED,
    SourceEffectEvidenceArtifact,
    build_source_effect_document_aliases,
)
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
    SourceEffectCandidate,
)

SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT = "AMBIGUOUS_TARGET_DOCUMENT"
SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT = "UNRESOLVED_TARGET_DOCUMENT"
SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET = "SAME_DOCUMENT_TARGET"
SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW = "THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW"
SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT = "MISSING_TARGET_CONTEXT"

_ANCHOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (SOURCE_EFFECT_TYPE_SUPERSEDES, re.compile(r"\bse\s+(?:sustituye|reemplaza)\b", re.IGNORECASE)),
    (SOURCE_EFFECT_TYPE_AMENDS, re.compile(r"\bse\s+modific(?:a|an)\b", re.IGNORECASE)),
    (SOURCE_EFFECT_TYPE_CORRECTS, re.compile(r"\bse\s+corrig(?:e|en)\b", re.IGNORECASE)),
    (SOURCE_EFFECT_TYPE_CLARIFIES, re.compile(r"\bse\s+aclar(?:a|an)\b", re.IGNORECASE)),
    (SOURCE_EFFECT_TYPE_SUPPLEMENTS, re.compile(r"\bse\s+(?:complementa|adiciona)\b", re.IGNORECASE)),
    (
        SOURCE_EFFECT_TYPE_REVOKES,
        re.compile(
            r"\b(?:queda|quedan)\s+sin\s+efecto\b|\bse\s+deja(?:n)?\s+sin\s+efecto\b|\bse\s+revoc(?:a|an)\b",
            re.IGNORECASE,
        ),
    ),
)

_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAnexo\s+(?:T[eé]cnico(?:\s+Rev\.?\s*\d+)?|[A-Z0-9]+(?:[-\.][A-Z0-9]+)*)\b", re.IGNORECASE),
    re.compile(r"\bBases(?:\s+de\s+Licitaci[oó]n)?\b", re.IGNORECASE),
    re.compile(r"\bConvocatoria\b", re.IGNORECASE),
    re.compile(r"\bDocumento\s+[A-Z0-9]+(?:[-\.][A-Z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\bFormato\s+[A-Z0-9]+(?:[-\.][A-Z0-9]+)*\b", re.IGNORECASE),
)

_LOCATOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnumeral\s+\d+(?:\.\d+)*[a-z]?\b", re.IGNORECASE),
    re.compile(r"\bapartado\s+[a-z0-9][a-z0-9\.\-]*\b", re.IGNORECASE),
    re.compile(r"\bsecci[oó]n\s+[ivxlcdm0-9]+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bcl[aá]usula\s+\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\binciso\s+[a-z]\)?\b", re.IGNORECASE),
    re.compile(r"\bp[aá]gina\s+\d+\b", re.IGNORECASE),
    re.compile(r"\btabla\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bpartida\s+\d+\b", re.IGNORECASE),
    re.compile(r"\brequisito\s+\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bp[aá]rrafo\s+\d+\b", re.IGNORECASE),
)

_DOCUMENT_WIDE_PATTERN = re.compile(
    r"\ben\s+su\s+totalidad\b|\bdocumento\s+completo\b|\bla\s+totalidad\s+del\b|\bla\s+totalidad\s+de\s+la\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SourceEffectDeterministicResult:
    source_artifact_key: str
    status: str
    candidates: tuple[SourceEffectCandidate, ...]
    diagnostics: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def discover_source_effects_from_evidence(
    db: Session,
    artifact: SourceEffectEvidenceArtifact,
) -> SourceEffectDeterministicResult:
    if artifact.source_method not in {"NATIVE", "OCR", "VISION"}:
        return SourceEffectDeterministicResult(
            source_artifact_key=artifact.source_artifact_key,
            status=SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED,
            candidates=(),
            errors=(f"Unsupported source_method: {artifact.source_method}",),
        )

    source_text = _optional_text(artifact.source_text)
    if source_text is None:
        return SourceEffectDeterministicResult(
            source_artifact_key=artifact.source_artifact_key,
            status=SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE,
            candidates=(),
            errors=("source_text is required",),
        )

    candidates: list[SourceEffectCandidate] = []
    diagnostics: list[str] = []
    effect_index = 0

    for excerpt in _context_segments(source_text):
        anchor = _extract_anchor(excerpt)
        if anchor is None:
            continue

        affected_document_ref_raw = _extract_reference(excerpt)
        affected_locator_raw = _extract_locator(excerpt)

        if affected_document_ref_raw is None and affected_locator_raw is None:
            diagnostics.append(SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT)
            continue

        effect_type = anchor
        effect_scope = _resolve_effect_scope(excerpt, affected_locator_raw)
        review_required = effect_scope == SOURCE_EFFECT_SCOPE_UNRESOLVED

        affected_document_id: str | None = None
        if affected_document_ref_raw is not None:
            resolved_target = _resolve_affected_document_id(
                db,
                tender_id=artifact.tender_id,
                acting_document_id=artifact.acting_document_id,
                affected_document_ref_raw=affected_document_ref_raw,
            )
            affected_document_id = resolved_target.affected_document_id
            if resolved_target.diagnostic is not None:
                diagnostics.append(resolved_target.diagnostic)
                review_required = True

        third_ref = _extract_reference_after_por(excerpt)
        if (
            third_ref is not None
            and affected_document_ref_raw is not None
            and _normalize_text(third_ref) != _normalize_text(affected_document_ref_raw)
        ):
            diagnostics.append(SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW)
            review_required = True

        locator_value = f"{artifact.source_locator}|effect:{effect_index}"
        effect_index += 1

        candidate = SourceEffectCandidate(
            tender_id=artifact.tender_id,
            acting_document_id=artifact.acting_document_id,
            affected_document_id=affected_document_id,
            document_page_id=artifact.document_page_id,
            affected_document_page_id=None,
            effect_type=effect_type,
            effect_scope=effect_scope,
            affected_document_ref_raw=affected_document_ref_raw,
            affected_locator_raw=affected_locator_raw,
            effective_date_raw=None,
            source_method=artifact.source_method,
            source_artifact_key=artifact.source_artifact_key,
            source_locator=locator_value,
            source_excerpt=excerpt,
            review_required=review_required,
            confidence=None,
            source_contract_version=artifact.source_contract_version,
            source_analysis_id=artifact.source_analysis_id,
            source_page_result_id=artifact.source_page_result_id,
        )

        if affected_document_ref_raw is not None and not _contains_normalized(excerpt, affected_document_ref_raw):
            return SourceEffectDeterministicResult(
                source_artifact_key=artifact.source_artifact_key,
                status=SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE,
                candidates=(),
                errors=("affected_document_ref_raw is not grounded in source_excerpt",),
            )
        if affected_locator_raw is not None and not _contains_normalized(excerpt, affected_locator_raw):
            return SourceEffectDeterministicResult(
                source_artifact_key=artifact.source_artifact_key,
                status=SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE,
                candidates=(),
                errors=("affected_locator_raw is not grounded in source_excerpt",),
            )

        candidates.append(candidate)

    if not candidates:
        if diagnostics:
            return SourceEffectDeterministicResult(
                source_artifact_key=artifact.source_artifact_key,
                status=SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED,
                candidates=(),
                diagnostics=tuple(diagnostics),
            )
        return SourceEffectDeterministicResult(
            source_artifact_key=artifact.source_artifact_key,
            status=SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS,
            candidates=(),
        )

    review_required_count = sum(1 for candidate in candidates if candidate.review_required)
    status = SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED if review_required_count > 0 else SOURCE_EFFECT_ADAPTER_STATUS_MATERIALIZED

    return SourceEffectDeterministicResult(
        source_artifact_key=artifact.source_artifact_key,
        status=status,
        candidates=tuple(candidates),
        diagnostics=tuple(diagnostics),
    )


@dataclass(frozen=True, slots=True)
class _TargetResolutionResult:
    affected_document_id: str | None
    diagnostic: str | None = None


def _resolve_affected_document_id(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    affected_document_ref_raw: str,
) -> _TargetResolutionResult:
    reference_key = _normalize_text(affected_document_ref_raw)
    if not reference_key:
        return _TargetResolutionResult(affected_document_id=None)

    matches: list[str] = []
    for doc in db.execute(
        select(TenderDocument).where(TenderDocument.tender_id == tender_id)
    ).scalars().all():
        aliases = build_source_effect_document_aliases(
            original_filename=doc.original_filename,
            source_relative_path=doc.source_relative_path,
        )
        if reference_key not in aliases:
            continue
        matches.append(doc.id)

    unique_matches = sorted(set(matches))
    if len(unique_matches) == 0:
        return _TargetResolutionResult(
            affected_document_id=None,
            diagnostic=SOURCE_EFFECT_DIAGNOSTIC_UNRESOLVED_TARGET_DOCUMENT,
        )
    if len(unique_matches) > 1:
        return _TargetResolutionResult(
            affected_document_id=None,
            diagnostic=SOURCE_EFFECT_DIAGNOSTIC_AMBIGUOUS_TARGET_DOCUMENT,
        )
    if unique_matches[0] == acting_document_id:
        return _TargetResolutionResult(
            affected_document_id=None,
            diagnostic=SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET,
        )

    return _TargetResolutionResult(affected_document_id=unique_matches[0])


def _extract_anchor(excerpt: str) -> str | None:
    for effect_type, pattern in _ANCHOR_PATTERNS:
        if pattern.search(excerpt) is not None:
            return effect_type
    return None


def _extract_reference(excerpt: str) -> str | None:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(excerpt)
        if match is None:
            continue
        value = _optional_text(match.group(0))
        if value is not None:
            return value
    return None


def _extract_reference_after_por(excerpt: str) -> str | None:
    lowered = excerpt.lower()
    marker = " por "
    index = lowered.find(marker)
    if index < 0:
        return None
    tail = excerpt[index + len(marker) :]
    return _extract_reference(tail)


def _extract_locator(excerpt: str) -> str | None:
    for pattern in _LOCATOR_PATTERNS:
        match = pattern.search(excerpt)
        if match is None:
            continue
        value = _optional_text(match.group(0))
        if value is not None:
            return value
    return None


def _resolve_effect_scope(excerpt: str, affected_locator_raw: str | None) -> str:
    if affected_locator_raw is not None:
        return SOURCE_EFFECT_SCOPE_PARTIAL
    if _DOCUMENT_WIDE_PATTERN.search(excerpt) is not None:
        return SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE
    return SOURCE_EFFECT_SCOPE_UNRESOLVED


def _contains_normalized(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    normalized_haystack = " ".join(haystack.split()).upper()
    normalized_needle = " ".join(needle.split()).upper()
    return normalized_needle in normalized_haystack


def _context_segments(text: str) -> tuple[str, ...]:
    collapsed = "\n".join(line.strip() for line in str(text).splitlines() if line.strip())
    if not collapsed:
        return ()

    segments: list[str] = []
    for block in collapsed.split("\n"):
        candidates = re.split(r"(?<=[\.;:])\s+", block)
        for candidate in candidates:
            normalized = " ".join(candidate.split())
            if not normalized:
                continue
            segments.append(normalized)
    return tuple(segments)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).upper()
