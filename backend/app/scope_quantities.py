from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    DocumentPage,
    DocumentVisionAnalysis,
    DocumentVisionPageResult,
    TenderDocument,
    TenderScopeDetail,
    TenderScopeQuantity,
)
from app.scope_details import SOURCE_METHOD_NATIVE, SOURCE_METHOD_OCR, SOURCE_METHOD_VISION

SCOPE_QUANTITY_RELATION_EXACT = "EXACT"
SCOPE_QUANTITY_RELATION_MINIMUM = "MINIMUM"
SCOPE_QUANTITY_RELATION_MAXIMUM = "MAXIMUM"
SCOPE_QUANTITY_RELATION_RANGE = "RANGE"
SCOPE_QUANTITY_RELATION_APPROXIMATE = "APPROXIMATE"
SCOPE_QUANTITY_RELATION_UNSPECIFIED = "UNSPECIFIED"

SCOPE_QUANTITY_ALLOWED_RELATIONS = {
    SCOPE_QUANTITY_RELATION_EXACT,
    SCOPE_QUANTITY_RELATION_MINIMUM,
    SCOPE_QUANTITY_RELATION_MAXIMUM,
    SCOPE_QUANTITY_RELATION_RANGE,
    SCOPE_QUANTITY_RELATION_APPROXIMATE,
    SCOPE_QUANTITY_RELATION_UNSPECIFIED,
}

SCOPE_QUANTITY_MEASURE_KIND_COUNT = "COUNT"
SCOPE_QUANTITY_MEASURE_KIND_LENGTH = "LENGTH"
SCOPE_QUANTITY_MEASURE_KIND_AREA = "AREA"
SCOPE_QUANTITY_MEASURE_KIND_VOLUME = "VOLUME"
SCOPE_QUANTITY_MEASURE_KIND_MASS = "MASS"
SCOPE_QUANTITY_MEASURE_KIND_DURATION = "DURATION"
SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL = "PERSONNEL"
SCOPE_QUANTITY_MEASURE_KIND_SERVICE = "SERVICE"
SCOPE_QUANTITY_MEASURE_KIND_LOT = "LOT"
SCOPE_QUANTITY_MEASURE_KIND_OTHER = "OTHER"

SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS = {
    SCOPE_QUANTITY_MEASURE_KIND_COUNT,
    SCOPE_QUANTITY_MEASURE_KIND_LENGTH,
    SCOPE_QUANTITY_MEASURE_KIND_AREA,
    SCOPE_QUANTITY_MEASURE_KIND_VOLUME,
    SCOPE_QUANTITY_MEASURE_KIND_MASS,
    SCOPE_QUANTITY_MEASURE_KIND_DURATION,
    SCOPE_QUANTITY_MEASURE_KIND_PERSONNEL,
    SCOPE_QUANTITY_MEASURE_KIND_SERVICE,
    SCOPE_QUANTITY_MEASURE_KIND_LOT,
    SCOPE_QUANTITY_MEASURE_KIND_OTHER,
}

SCOPE_QUANTITY_ALLOWED_SOURCE_METHODS = {
    SOURCE_METHOD_NATIVE,
    SOURCE_METHOD_OCR,
    SOURCE_METHOD_VISION,
}


@dataclass(frozen=True, slots=True)
class ScopeQuantityCandidate:
    tender_id: str
    scope_detail_id: str
    source_document_id: str
    document_page_id: str
    quantity_raw: str
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    review_required: bool = True
    quantity_value: Decimal | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    unit_raw: str | None = None
    measure_kind: str | None = None
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


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()


def _is_grounded(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(haystack)


def _decimal_or_none(value: Decimal | int | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def validate_scope_quantity_candidate(candidate: ScopeQuantityCandidate) -> None:
    _required_text("tender_id", candidate.tender_id)
    _required_text("scope_detail_id", candidate.scope_detail_id)
    _required_text("source_document_id", candidate.source_document_id)
    _required_text("document_page_id", candidate.document_page_id)
    _required_text("quantity_raw", candidate.quantity_raw)
    _required_text("source_method", candidate.source_method)
    _required_text("source_artifact_key", candidate.source_artifact_key)
    _required_text("source_locator", candidate.source_locator)
    _required_text("source_excerpt", candidate.source_excerpt)

    if candidate.source_method not in SCOPE_QUANTITY_ALLOWED_SOURCE_METHODS:
        raise ValueError(f"Unsupported source_method: {candidate.source_method}")

    relation = _optional_text(candidate.relation) or SCOPE_QUANTITY_RELATION_UNSPECIFIED
    if relation not in SCOPE_QUANTITY_ALLOWED_RELATIONS:
        raise ValueError(f"Unsupported relation: {relation}")

    measure_kind = _optional_text(candidate.measure_kind)
    if measure_kind is not None and measure_kind not in SCOPE_QUANTITY_ALLOWED_MEASURE_KINDS:
        raise ValueError(f"Unsupported measure_kind: {measure_kind}")

    if candidate.confidence is not None and (candidate.confidence < 0.0 or candidate.confidence > 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")

    if not _is_grounded(candidate.source_excerpt, candidate.quantity_raw):
        raise ValueError("quantity_raw is not grounded in source_excerpt")

    unit_raw = _optional_text(candidate.unit_raw)
    if unit_raw is not None and not _is_grounded(candidate.source_excerpt, unit_raw):
        raise ValueError("unit_raw is not grounded in source_excerpt")

    quantity_value = _decimal_or_none(candidate.quantity_value)
    quantity_min = _decimal_or_none(candidate.quantity_min)
    quantity_max = _decimal_or_none(candidate.quantity_max)

    if relation == SCOPE_QUANTITY_RELATION_EXACT:
        if quantity_value is None:
            raise ValueError("quantity_value is required for EXACT relation")
        if quantity_min is not None or quantity_max is not None:
            raise ValueError("quantity_min/quantity_max must be null for EXACT relation")
    elif relation == SCOPE_QUANTITY_RELATION_MINIMUM:
        if quantity_min is None:
            raise ValueError("quantity_min is required for MINIMUM relation")
    elif relation == SCOPE_QUANTITY_RELATION_MAXIMUM:
        if quantity_max is None:
            raise ValueError("quantity_max is required for MAXIMUM relation")
    elif relation == SCOPE_QUANTITY_RELATION_RANGE:
        if quantity_min is None or quantity_max is None:
            raise ValueError("quantity_min and quantity_max are required for RANGE relation")
        if quantity_min > quantity_max:
            raise ValueError("quantity_min cannot be greater than quantity_max")


def compute_scope_quantity_fingerprint(candidate: ScopeQuantityCandidate) -> str:
    relation = _normalize_text(_optional_text(candidate.relation) or SCOPE_QUANTITY_RELATION_UNSPECIFIED)
    quantity_raw = _normalize_text(_required_text("quantity_raw", candidate.quantity_raw))
    unit_raw = _normalize_text(_optional_text(candidate.unit_raw) or "")
    measure_kind = _normalize_text(_optional_text(candidate.measure_kind) or "")
    payload = "|".join(
        [
            quantity_raw,
            str(_decimal_or_none(candidate.quantity_value) if candidate.quantity_value is not None else ""),
            str(_decimal_or_none(candidate.quantity_min) if candidate.quantity_min is not None else ""),
            str(_decimal_or_none(candidate.quantity_max) if candidate.quantity_max is not None else ""),
            unit_raw,
            measure_kind,
            relation,
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
            analysis = db.get(DocumentVisionAnalysis, page_result.analysis_id)
            if analysis is None or analysis.tender_id != tender_id or analysis.document_id != source_document_id:
                raise ValueError("source_page_result_id lineage is outside replacement tender/document scope")


def replace_scope_quantities_for_artifact(
    db: Session,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
    candidates: Sequence[ScopeQuantityCandidate],
) -> list[TenderScopeQuantity]:
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
        delete(TenderScopeQuantity).where(
            TenderScopeQuantity.tender_id == resolved_tender_id,
            TenderScopeQuantity.scope_detail_id == resolved_scope_detail_id,
            TenderScopeQuantity.source_document_id == resolved_document_id,
            TenderScopeQuantity.document_page_id == resolved_page_id,
            TenderScopeQuantity.source_artifact_key == resolved_artifact_key,
        )
    )

    persisted: list[TenderScopeQuantity] = []
    seen_fingerprints: set[str] = set()

    for candidate in candidates:
        validate_scope_quantity_candidate(candidate)

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

        fingerprint = compute_scope_quantity_fingerprint(candidate)
        if fingerprint in seen_fingerprints:
            raise ValueError("Duplicate semantic fingerprint in candidate batch")
        seen_fingerprints.add(fingerprint)

        row = TenderScopeQuantity(
            tender_id=resolved_tender_id,
            scope_detail_id=resolved_scope_detail_id,
            source_document_id=resolved_document_id,
            document_page_id=resolved_page_id,
            quantity_raw=_required_text("quantity_raw", candidate.quantity_raw),
            quantity_value=_decimal_or_none(candidate.quantity_value),
            quantity_min=_decimal_or_none(candidate.quantity_min),
            quantity_max=_decimal_or_none(candidate.quantity_max),
            unit_raw=_optional_text(candidate.unit_raw),
            measure_kind=_optional_text(candidate.measure_kind),
            relation=_optional_text(candidate.relation) or SCOPE_QUANTITY_RELATION_UNSPECIFIED,
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


def list_scope_quantities_for_scope_detail(
    db: Session,
    *,
    scope_detail_id: str,
) -> list[TenderScopeQuantity]:
    resolved_scope_detail_id = _required_text("scope_detail_id", scope_detail_id)
    return list(
        db.execute(
            select(TenderScopeQuantity)
            .where(TenderScopeQuantity.scope_detail_id == resolved_scope_detail_id)
            .order_by(TenderScopeQuantity.created_at.asc(), TenderScopeQuantity.id.asc())
        ).scalars()
    )
