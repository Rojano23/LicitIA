from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import TenderScopeDetail

SCOPE_DETAIL_DOMAIN_TECHNICAL = "TECHNICAL"
SCOPE_DETAIL_DOMAIN_SERVICE = "SERVICE"
SCOPE_DETAIL_DOMAIN_SUPPLY = "SUPPLY"
SCOPE_DETAIL_DOMAIN_TOOLS_EQUIPMENT = "TOOLS_EQUIPMENT"
SCOPE_DETAIL_DOMAIN_PERSONNEL = "PERSONNEL"
SCOPE_DETAIL_DOMAIN_SSPA = "SSPA"
SCOPE_DETAIL_DOMAIN_DELIVERABLE = "DELIVERABLE"
SCOPE_DETAIL_DOMAIN_LOGISTICS_SITE = "LOGISTICS_SITE"
SCOPE_DETAIL_DOMAIN_OTHER = "OTHER"

SCOPE_DETAIL_ALLOWED_DOMAINS = {
    SCOPE_DETAIL_DOMAIN_TECHNICAL,
    SCOPE_DETAIL_DOMAIN_SERVICE,
    SCOPE_DETAIL_DOMAIN_SUPPLY,
    SCOPE_DETAIL_DOMAIN_TOOLS_EQUIPMENT,
    SCOPE_DETAIL_DOMAIN_PERSONNEL,
    SCOPE_DETAIL_DOMAIN_SSPA,
    SCOPE_DETAIL_DOMAIN_DELIVERABLE,
    SCOPE_DETAIL_DOMAIN_LOGISTICS_SITE,
    SCOPE_DETAIL_DOMAIN_OTHER,
}

SCOPE_DETAIL_APPLICABILITY_ITEM = "ITEM"
SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE = "TENDER_WIDE"
SCOPE_DETAIL_APPLICABILITY_UNRESOLVED = "UNRESOLVED"

SCOPE_DETAIL_ALLOWED_APPLICABILITY = {
    SCOPE_DETAIL_APPLICABILITY_ITEM,
    SCOPE_DETAIL_APPLICABILITY_TENDER_WIDE,
    SCOPE_DETAIL_APPLICABILITY_UNRESOLVED,
}

SOURCE_METHOD_NATIVE = "NATIVE"
SOURCE_METHOD_OCR = "OCR"
SOURCE_METHOD_VISION = "VISION"


@dataclass(frozen=True, slots=True)
class ScopeDetailCandidate:
    tender_id: str
    source_document_id: str
    document_page_id: str
    domain: str
    description: str
    applicability: str
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    review_required: bool
    scope_segment_id: str | None = None
    tender_item_id: str | None = None
    candidate_item_key: str | None = None
    detail_type: str | None = None
    normalized_label: str | None = None
    source_contract_version: str | None = None
    confidence: float | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    quantity_raw: str | None = None
    unit_raw: str | None = None


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


def _fingerprint_for_candidate(candidate: ScopeDetailCandidate) -> str:
    payload = "|".join(
        [
            candidate.tender_id,
            candidate.source_document_id,
            candidate.document_page_id,
            candidate.domain,
            candidate.detail_type or "",
            candidate.description,
            candidate.normalized_label or "",
            candidate.applicability,
            candidate.scope_segment_id or "",
            candidate.tender_item_id or "",
            candidate.candidate_item_key or "",
            candidate.source_method,
            candidate.source_artifact_key,
            candidate.source_locator,
            candidate.source_excerpt,
            candidate.quantity_raw if candidate.quantity_raw is not None else "",
            candidate.unit_raw if candidate.unit_raw is not None else "",
        ]
    )
    return _sha256(payload)


def _validate_candidate(candidate: ScopeDetailCandidate) -> None:
    _required_text("tender_id", candidate.tender_id)
    _required_text("source_document_id", candidate.source_document_id)
    _required_text("document_page_id", candidate.document_page_id)
    _required_text("description", candidate.description)
    _required_text("source_method", candidate.source_method)
    _required_text("source_artifact_key", candidate.source_artifact_key)
    _required_text("source_locator", candidate.source_locator)
    _required_text("source_excerpt", candidate.source_excerpt)

    if candidate.domain not in SCOPE_DETAIL_ALLOWED_DOMAINS:
        raise ValueError(f"Unsupported scope detail domain: {candidate.domain}")

    if candidate.applicability not in SCOPE_DETAIL_ALLOWED_APPLICABILITY:
        raise ValueError(f"Unsupported applicability: {candidate.applicability}")

    has_item_ownership = bool(
        _optional_text(candidate.scope_segment_id)
        or _optional_text(candidate.tender_item_id)
        or _optional_text(candidate.candidate_item_key)
    )

    if candidate.applicability == SCOPE_DETAIL_APPLICABILITY_ITEM and not has_item_ownership:
        raise ValueError("ITEM applicability requires ownership evidence")

    if candidate.applicability == SCOPE_DETAIL_APPLICABILITY_UNRESOLVED and not candidate.review_required:
        raise ValueError("UNRESOLVED applicability requires review_required=true")


def replace_scope_details_for_artifact(
    db: Session,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
    candidates: Sequence[ScopeDetailCandidate],
) -> list[TenderScopeDetail]:
    resolved_artifact_key = _required_text("source_artifact_key", source_artifact_key)

    db.execute(
        delete(TenderScopeDetail).where(
            TenderScopeDetail.tender_id == tender_id,
            TenderScopeDetail.source_document_id == source_document_id,
            TenderScopeDetail.document_page_id == document_page_id,
            TenderScopeDetail.source_artifact_key == resolved_artifact_key,
        )
    )

    persisted: list[TenderScopeDetail] = []
    for candidate in candidates:
        _validate_candidate(candidate)

        if candidate.tender_id != tender_id:
            raise ValueError("Candidate tender_id does not match replacement scope")
        if candidate.source_document_id != source_document_id:
            raise ValueError("Candidate source_document_id does not match replacement scope")
        if candidate.document_page_id != document_page_id:
            raise ValueError("Candidate document_page_id does not match replacement scope")

        candidate_artifact_key = _required_text("source_artifact_key", candidate.source_artifact_key)
        if candidate_artifact_key != resolved_artifact_key:
            raise ValueError("Candidate source_artifact_key does not match replacement scope")

        row = TenderScopeDetail(
            tender_id=tender_id,
            source_document_id=source_document_id,
            document_page_id=document_page_id,
            scope_segment_id=_optional_text(candidate.scope_segment_id),
            tender_item_id=_optional_text(candidate.tender_item_id),
            candidate_item_key=_optional_text(candidate.candidate_item_key),
            domain=candidate.domain,
            detail_type=_optional_text(candidate.detail_type),
            description=_required_text("description", candidate.description),
            normalized_label=_optional_text(candidate.normalized_label),
            applicability=candidate.applicability,
            source_method=_required_text("source_method", candidate.source_method),
            source_artifact_key=candidate_artifact_key,
            source_contract_version=_optional_text(candidate.source_contract_version),
            source_locator=_required_text("source_locator", candidate.source_locator),
            source_excerpt=_required_text("source_excerpt", candidate.source_excerpt),
            confidence=candidate.confidence,
            review_required=bool(candidate.review_required),
            source_analysis_id=_optional_text(candidate.source_analysis_id),
            source_page_result_id=_optional_text(candidate.source_page_result_id),
            quantity_raw=None if candidate.quantity_raw is None else str(candidate.quantity_raw),
            unit_raw=None if candidate.unit_raw is None else str(candidate.unit_raw),
            semantic_fingerprint=_fingerprint_for_candidate(candidate),
        )
        db.add(row)
        persisted.append(row)

    db.flush()
    return persisted
