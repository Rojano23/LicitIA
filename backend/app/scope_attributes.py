from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
)
from app.scope_details import SOURCE_METHOD_NATIVE, SOURCE_METHOD_OCR, SOURCE_METHOD_VISION

SCOPE_ATTRIBUTE_RELATION_EXACT = "EXACT"
SCOPE_ATTRIBUTE_RELATION_MINIMUM = "MINIMUM"
SCOPE_ATTRIBUTE_RELATION_MAXIMUM = "MAXIMUM"
SCOPE_ATTRIBUTE_RELATION_RANGE = "RANGE"
SCOPE_ATTRIBUTE_RELATION_TOLERANCE = "TOLERANCE"
SCOPE_ATTRIBUTE_RELATION_REFERENCE = "REFERENCE"
SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED = "UNSPECIFIED"

SCOPE_ATTRIBUTE_ALLOWED_RELATIONS = {
    SCOPE_ATTRIBUTE_RELATION_EXACT,
    SCOPE_ATTRIBUTE_RELATION_MINIMUM,
    SCOPE_ATTRIBUTE_RELATION_MAXIMUM,
    SCOPE_ATTRIBUTE_RELATION_RANGE,
    SCOPE_ATTRIBUTE_RELATION_TOLERANCE,
    SCOPE_ATTRIBUTE_RELATION_REFERENCE,
    SCOPE_ATTRIBUTE_RELATION_UNSPECIFIED,
}

SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS = {
    SOURCE_METHOD_NATIVE,
    SOURCE_METHOD_OCR,
    SOURCE_METHOD_VISION,
}


@dataclass(frozen=True, slots=True)
class ScopeAttributeCandidate:
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    attribute_name: str
    value_raw: str
    review_required: bool = True
    attribute_label_raw: str | None = None
    normalized_name: str | None = None
    unit_raw: str | None = None
    relation: str | None = None
    confidence: float | None = None
    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_scope_attribute_candidate(candidate: ScopeAttributeCandidate) -> None:
    _required_text("tender_id", candidate.tender_id)
    _required_text("scope_detail_id", candidate.scope_detail_id)
    _required_text("source_document_id", candidate.source_document_id)
    _required_text("document_page_id", candidate.document_page_id)
    _required_text("source_method", candidate.source_method)
    _required_text("source_artifact_key", candidate.source_artifact_key)
    _required_text("source_locator", candidate.source_locator)
    _required_text("source_excerpt", candidate.source_excerpt)
    _required_text("attribute_name", candidate.attribute_name)
    _required_text("value_raw", candidate.value_raw)

    if candidate.source_method not in SCOPE_ATTRIBUTE_ALLOWED_SOURCE_METHODS:
        raise ValueError(f"Unsupported source_method: {candidate.source_method}")

    if candidate.relation is not None and candidate.relation not in SCOPE_ATTRIBUTE_ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {candidate.relation}")

    if candidate.confidence is not None and (candidate.confidence < 0.0 or candidate.confidence > 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")


def compute_scope_attribute_fingerprint(candidate: ScopeAttributeCandidate) -> str:
    """Deterministic fingerprint for semantic identity within scope detail + artifact."""
    payload = "|".join(
        [
            candidate.scope_detail_id,
            candidate.source_artifact_key,
            _required_text("attribute_name", candidate.attribute_name).lower(),
            _required_text("value_raw", candidate.value_raw),
            _optional_text(candidate.unit_raw) or "",
            _optional_text(candidate.relation) or "",
            _optional_text(candidate.normalized_name) or "",
            _optional_text(candidate.attribute_label_raw) or "",
            _required_text("source_locator", candidate.source_locator),
            _required_text("source_excerpt", candidate.source_excerpt),
        ]
    )
    return _sha256(payload)


def _validate_replacement_scope_ownership(
    db: Session,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_analysis_id: str | None,
    source_page_result_id: str | None,
) -> None:
    scope_detail = db.get(TenderScopeDetail, scope_detail_id)
    if scope_detail is None:
        raise ValueError("scope_detail_id does not exist")
    if scope_detail.tender_id != tender_id:
        raise ValueError("scope_detail_id belongs to a different tender")

    source_document = db.get(TenderDocument, source_document_id)
    if source_document is None:
        raise ValueError("source_document_id does not exist")
    if source_document.tender_id != tender_id:
        raise ValueError("source_document_id belongs to a different tender")

    document_page = db.get(DocumentPage, document_page_id)
    if document_page is None:
        raise ValueError("document_page_id does not exist")
    if document_page.document_id != source_document_id:
        raise ValueError("document_page_id does not belong to source_document_id")

    if source_analysis_id is not None:
        analysis = db.get(DocumentVisionAnalysis, source_analysis_id)
        if analysis is None:
            raise ValueError("source_analysis_id does not exist")
        if analysis.tender_id != tender_id:
            raise ValueError("source_analysis_id belongs to a different tender")
        if analysis.document_id != source_document_id:
            raise ValueError("source_analysis_id does not belong to source_document_id")

    if source_page_result_id is not None:
        page_result = db.get(DocumentVisionPageResult, source_page_result_id)
        if page_result is None:
            raise ValueError("source_page_result_id does not exist")
        if page_result.document_page_id != document_page_id:
            raise ValueError("source_page_result_id does not belong to document_page_id")
        if source_analysis_id is not None and page_result.analysis_id != source_analysis_id:
            raise ValueError("source_page_result_id does not belong to source_analysis_id")
        if source_analysis_id is None:
            analysis_id = page_result.analysis_id
            analysis = db.get(DocumentVisionAnalysis, analysis_id)
            if analysis is None or analysis.tender_id != tender_id or analysis.document_id != source_document_id:
                raise ValueError("source_page_result_id lineage is outside replacement tender/document scope")


def replace_scope_attributes_for_artifact(
    db: Session,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
    candidates: Sequence[ScopeAttributeCandidate],
) -> list[TenderScopeAttribute]:
    resolved_tender_id = _required_text("tender_id", tender_id)
    resolved_scope_detail_id = _required_text("scope_detail_id", scope_detail_id)
    resolved_document_id = _required_text("source_document_id", source_document_id)
    resolved_page_id = _required_text("document_page_id", document_page_id)
    resolved_artifact_key = _required_text("source_artifact_key", source_artifact_key)

    _validate_replacement_scope_ownership(
        db,
        tender_id=resolved_tender_id,
        scope_detail_id=resolved_scope_detail_id,
        source_document_id=resolved_document_id,
        document_page_id=resolved_page_id,
        source_analysis_id=None,
        source_page_result_id=None,
    )

    db.execute(
        delete(TenderScopeAttribute).where(
            TenderScopeAttribute.tender_id == resolved_tender_id,
            TenderScopeAttribute.scope_detail_id == resolved_scope_detail_id,
            TenderScopeAttribute.source_document_id == resolved_document_id,
            TenderScopeAttribute.document_page_id == resolved_page_id,
            TenderScopeAttribute.source_artifact_key == resolved_artifact_key,
        )
    )

    persisted: list[TenderScopeAttribute] = []
    seen_fingerprints: set[str] = set()

    for candidate in candidates:
        validate_scope_attribute_candidate(candidate)

        if candidate.tender_id != resolved_tender_id:
            raise ValueError("Candidate tender_id does not match replacement scope")
        if candidate.scope_detail_id != resolved_scope_detail_id:
            raise ValueError("Candidate scope_detail_id does not match replacement scope")
        if candidate.source_document_id != resolved_document_id:
            raise ValueError("Candidate source_document_id does not match replacement scope")
        if candidate.document_page_id != resolved_page_id:
            raise ValueError("Candidate document_page_id does not match replacement scope")

        candidate_artifact_key = _required_text("source_artifact_key", candidate.source_artifact_key)
        if candidate_artifact_key != resolved_artifact_key:
            raise ValueError("Candidate source_artifact_key does not match replacement scope")

        _validate_replacement_scope_ownership(
            db,
            tender_id=resolved_tender_id,
            scope_detail_id=resolved_scope_detail_id,
            source_document_id=resolved_document_id,
            document_page_id=resolved_page_id,
            source_analysis_id=_optional_text(candidate.source_analysis_id),
            source_page_result_id=_optional_text(candidate.source_page_result_id),
        )

        fingerprint = compute_scope_attribute_fingerprint(candidate)
        if fingerprint in seen_fingerprints:
            raise ValueError("Duplicate semantic fingerprint in candidate batch")
        seen_fingerprints.add(fingerprint)

        row = TenderScopeAttribute(
            tender_id=resolved_tender_id,
            scope_detail_id=resolved_scope_detail_id,
            source_document_id=resolved_document_id,
            document_page_id=resolved_page_id,
            attribute_name=_required_text("attribute_name", candidate.attribute_name),
            attribute_label_raw=_optional_text(candidate.attribute_label_raw),
            normalized_name=_optional_text(candidate.normalized_name),
            value_raw=_required_text("value_raw", candidate.value_raw),
            unit_raw=_optional_text(candidate.unit_raw),
            relation=_optional_text(candidate.relation),
            source_method=_required_text("source_method", candidate.source_method),
            source_artifact_key=candidate_artifact_key,
            source_locator=_required_text("source_locator", candidate.source_locator),
            source_excerpt=_required_text("source_excerpt", candidate.source_excerpt),
            review_required=bool(candidate.review_required),
            semantic_fingerprint=fingerprint,
            confidence=candidate.confidence,
            source_contract_version=_optional_text(candidate.source_contract_version),
            source_analysis_id=_optional_text(candidate.source_analysis_id),
            source_page_result_id=_optional_text(candidate.source_page_result_id),
        )
        db.add(row)
        persisted.append(row)

    db.flush()
    return persisted


def list_scope_attributes_for_scope_detail(
    db: Session,
    *,
    scope_detail_id: str,
) -> list[TenderScopeAttribute]:
    resolved_scope_detail_id = _required_text("scope_detail_id", scope_detail_id)
    return list(
        db.execute(
            select(TenderScopeAttribute)
            .where(TenderScopeAttribute.scope_detail_id == resolved_scope_detail_id)
            .order_by(TenderScopeAttribute.created_at.asc(), TenderScopeAttribute.id.asc())
        ).scalars()
    )
