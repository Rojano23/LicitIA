from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DocumentPage, Tender, TenderDocument, TenderSourceEffect
from app.scope_details import SOURCE_METHOD_NATIVE, SOURCE_METHOD_OCR, SOURCE_METHOD_VISION

SOURCE_EFFECT_TYPE_SUPERSEDES = "SUPERSEDES"
SOURCE_EFFECT_TYPE_AMENDS = "AMENDS"
SOURCE_EFFECT_TYPE_CORRECTS = "CORRECTS"
SOURCE_EFFECT_TYPE_CLARIFIES = "CLARIFIES"
SOURCE_EFFECT_TYPE_SUPPLEMENTS = "SUPPLEMENTS"
SOURCE_EFFECT_TYPE_REVOKES = "REVOKES"
SOURCE_EFFECT_TYPE_UNSPECIFIED = "UNSPECIFIED"

SOURCE_EFFECT_ALLOWED_TYPES = {
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_UNSPECIFIED,
}

SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE = "DOCUMENT_WIDE"
SOURCE_EFFECT_SCOPE_PARTIAL = "PARTIAL"
SOURCE_EFFECT_SCOPE_UNRESOLVED = "UNRESOLVED"

SOURCE_EFFECT_ALLOWED_SCOPES = {
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
}

SOURCE_EFFECT_ALLOWED_SOURCE_METHODS = {
    SOURCE_METHOD_NATIVE,
    SOURCE_METHOD_OCR,
    SOURCE_METHOD_VISION,
}


@dataclass(frozen=True, slots=True)
class SourceEffectCandidate:
    tender_id: str
    acting_document_id: str
    document_page_id: str
    source_method: str
    source_artifact_key: str
    source_locator: str
    source_excerpt: str
    effect_type: str
    effect_scope: str
    affected_document_id: str | None = None
    affected_document_page_id: str | None = None
    affected_document_ref_raw: str | None = None
    affected_locator_raw: str | None = None
    effective_date_raw: str | None = None
    review_required: bool = True
    confidence: float | None = None
    source_contract_version: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None


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


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).upper()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _target_identity_for_fingerprint(candidate: SourceEffectCandidate) -> str:
    affected_document_ref_raw = _optional_text(candidate.affected_document_ref_raw)
    if affected_document_ref_raw is not None:
        return _normalize_text(affected_document_ref_raw)

    affected_document_id = _optional_text(candidate.affected_document_id)
    if affected_document_id is not None:
        return f"AFFECTED_DOCUMENT_ID:{_normalize_text(affected_document_id)}"

    return "UNRESOLVED_TARGET"


def validate_source_effect_candidate(db: Session, candidate: SourceEffectCandidate) -> None:
    tender_id = _required_text("tender_id", candidate.tender_id)
    acting_document_id = _required_text("acting_document_id", candidate.acting_document_id)
    document_page_id = _required_text("document_page_id", candidate.document_page_id)
    source_method = _required_text("source_method", candidate.source_method)
    _required_text("source_artifact_key", candidate.source_artifact_key)
    _required_text("source_locator", candidate.source_locator)
    _required_text("source_excerpt", candidate.source_excerpt)

    effect_type = _required_text("effect_type", candidate.effect_type).upper()
    effect_scope = _required_text("effect_scope", candidate.effect_scope).upper()

    if effect_type not in SOURCE_EFFECT_ALLOWED_TYPES:
        raise ValueError(f"Unsupported effect_type: {effect_type}")
    if effect_scope not in SOURCE_EFFECT_ALLOWED_SCOPES:
        raise ValueError(f"Unsupported effect_scope: {effect_scope}")
    if source_method not in SOURCE_EFFECT_ALLOWED_SOURCE_METHODS:
        raise ValueError(f"Unsupported source_method: {source_method}")

    if candidate.confidence is not None and (candidate.confidence < 0.0 or candidate.confidence > 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")

    if effect_type == SOURCE_EFFECT_TYPE_UNSPECIFIED and not candidate.review_required:
        raise ValueError("UNSPECIFIED effect_type requires review_required=True")
    if effect_scope == SOURCE_EFFECT_SCOPE_UNRESOLVED and not candidate.review_required:
        raise ValueError("UNRESOLVED effect_scope requires review_required=True")

    if effect_scope == SOURCE_EFFECT_SCOPE_PARTIAL:
        if _optional_text(candidate.affected_locator_raw) is None and _optional_text(candidate.affected_document_page_id) is None:
            raise ValueError("PARTIAL effect_scope requires affected_locator_raw or affected_document_page_id")

    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("tender_id does not exist")

    acting_document = db.get(TenderDocument, acting_document_id)
    if acting_document is None:
        raise ValueError("acting_document_id does not exist")
    if acting_document.tender_id != tender_id:
        raise ValueError("acting_document_id belongs to a different tender")

    acting_page = db.get(DocumentPage, document_page_id)
    if acting_page is None:
        raise ValueError("document_page_id does not exist")
    if acting_page.document_id != acting_document_id:
        raise ValueError("document_page_id does not belong to acting_document_id")

    affected_document_id = _optional_text(candidate.affected_document_id)
    affected_ref_raw = _optional_text(candidate.affected_document_ref_raw)
    if affected_document_id is None and affected_ref_raw is None and not candidate.review_required:
        raise ValueError("Unresolved target requires review_required=True")

    if affected_document_id is not None:
        affected_document = db.get(TenderDocument, affected_document_id)
        if affected_document is None:
            raise ValueError("affected_document_id does not exist")
        if affected_document.tender_id != tender_id:
            raise ValueError("affected_document_id belongs to a different tender")
        if affected_document_id == acting_document_id:
            raise ValueError("acting_document_id cannot equal affected_document_id")

    affected_document_page_id = _optional_text(candidate.affected_document_page_id)
    if affected_document_page_id is not None:
        if affected_document_id is None:
            raise ValueError("affected_document_page_id requires affected_document_id")
        affected_page = db.get(DocumentPage, affected_document_page_id)
        if affected_page is None:
            raise ValueError("affected_document_page_id does not exist")
        if affected_page.document_id != affected_document_id:
            raise ValueError("affected_document_page_id does not belong to affected_document_id")


def compute_source_effect_fingerprint(candidate: SourceEffectCandidate) -> str:
    payload = "|".join(
        [
            _normalize_text(candidate.effect_type),
            _normalize_text(candidate.effect_scope),
            _target_identity_for_fingerprint(candidate),
            _normalize_text(candidate.affected_locator_raw),
            _normalize_text(candidate.effective_date_raw),
        ]
    )
    return _sha256(payload)


def replace_source_effects_for_artifact(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
    candidates: list[SourceEffectCandidate],
) -> list[TenderSourceEffect]:
    resolved_tender_id = _required_text("tender_id", tender_id)
    resolved_acting_document_id = _required_text("acting_document_id", acting_document_id)
    resolved_document_page_id = _required_text("document_page_id", document_page_id)
    resolved_source_artifact_key = _required_text("source_artifact_key", source_artifact_key)

    acting_document = db.get(TenderDocument, resolved_acting_document_id)
    if acting_document is None:
        raise ValueError("acting_document_id does not exist")
    if acting_document.tender_id != resolved_tender_id:
        raise ValueError("acting_document_id belongs to a different tender")

    acting_page = db.get(DocumentPage, resolved_document_page_id)
    if acting_page is None:
        raise ValueError("document_page_id does not exist")
    if acting_page.document_id != resolved_acting_document_id:
        raise ValueError("document_page_id does not belong to acting_document_id")

    db.execute(
        delete(TenderSourceEffect).where(
            TenderSourceEffect.tender_id == resolved_tender_id,
            TenderSourceEffect.acting_document_id == resolved_acting_document_id,
            TenderSourceEffect.document_page_id == resolved_document_page_id,
            TenderSourceEffect.source_artifact_key == resolved_source_artifact_key,
        )
    )

    persisted: list[TenderSourceEffect] = []
    seen_fingerprints: set[str] = set()

    for candidate in candidates:
        validate_source_effect_candidate(db, candidate)

        if candidate.tender_id != resolved_tender_id:
            raise ValueError("Candidate tender_id does not match replacement scope")
        if candidate.acting_document_id != resolved_acting_document_id:
            raise ValueError("Candidate acting_document_id does not match replacement scope")
        if candidate.document_page_id != resolved_document_page_id:
            raise ValueError("Candidate document_page_id does not match replacement scope")
        if candidate.source_artifact_key != resolved_source_artifact_key:
            raise ValueError("Candidate source_artifact_key does not match replacement scope")

        fingerprint = compute_source_effect_fingerprint(candidate)
        if fingerprint in seen_fingerprints:
            raise ValueError("Duplicate semantic fingerprint in candidate batch")
        seen_fingerprints.add(fingerprint)

        row = TenderSourceEffect(
            tender_id=resolved_tender_id,
            acting_document_id=resolved_acting_document_id,
            affected_document_id=_optional_text(candidate.affected_document_id),
            document_page_id=resolved_document_page_id,
            affected_document_page_id=_optional_text(candidate.affected_document_page_id),
            effect_type=_normalize_text(candidate.effect_type),
            effect_scope=_normalize_text(candidate.effect_scope),
            affected_document_ref_raw=_optional_text(candidate.affected_document_ref_raw),
            affected_locator_raw=_optional_text(candidate.affected_locator_raw),
            effective_date_raw=_optional_text(candidate.effective_date_raw),
            source_method=_required_text("source_method", candidate.source_method),
            source_artifact_key=resolved_source_artifact_key,
            source_locator=_required_text("source_locator", candidate.source_locator),
            source_excerpt=_required_text("source_excerpt", candidate.source_excerpt),
            review_required=bool(candidate.review_required),
            confidence=candidate.confidence,
            semantic_fingerprint=fingerprint,
            source_contract_version=_optional_text(candidate.source_contract_version),
            source_analysis_id=_optional_text(candidate.source_analysis_id),
            source_page_result_id=_optional_text(candidate.source_page_result_id),
        )
        db.add(row)
        persisted.append(row)

    db.flush()
    return persisted


def list_source_effects_for_tender(db: Session, *, tender_id: str) -> list[TenderSourceEffect]:
    resolved_tender_id = _required_text("tender_id", tender_id)
    return list(
        db.execute(
            select(TenderSourceEffect)
            .where(TenderSourceEffect.tender_id == resolved_tender_id)
            .order_by(
                TenderSourceEffect.created_at.asc(),
                TenderSourceEffect.id.asc(),
            )
        ).scalars()
    )


def list_source_effects_for_boundary(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
) -> list[TenderSourceEffect]:
    return list(
        db.execute(
            select(TenderSourceEffect)
            .where(
                TenderSourceEffect.tender_id == _required_text("tender_id", tender_id),
                TenderSourceEffect.acting_document_id == _required_text("acting_document_id", acting_document_id),
                TenderSourceEffect.document_page_id == _required_text("document_page_id", document_page_id),
                TenderSourceEffect.source_artifact_key == _required_text("source_artifact_key", source_artifact_key),
            )
            .order_by(TenderSourceEffect.created_at.asc(), TenderSourceEffect.id.asc())
        ).scalars()
    )
