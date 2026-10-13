"""Human-authored technical strategy. Caller owns commit/rollback; no Scope writes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TechnicalAlternative, TechnicalAlternativeRevision, Tender

TextContent = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
LifecycleState = Literal["DRAFT", "ACTIVE", "ARCHIVED"]
RevisionNumber = Annotated[int, Field(strict=True, ge=1)]


class TechnicalAlternativeNotFound(LookupError):
    """Identity does not belong to the requested tender."""


class TechnicalAlternativeConflict(ValueError):
    """Current revision differs from the human's expectation."""


class TechnicalAlternativeContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: Annotated[TextContent, Field(max_length=255)]
    technical_description: TextContent
    assumptions: Annotated[str, StringConstraints(strict=True, strip_whitespace=True)] | None = None
    notes: Annotated[str, StringConstraints(strict=True, strip_whitespace=True)] | None = None
    lifecycle_state: LifecycleState = "DRAFT"


class TechnicalAlternativeAppend(TechnicalAlternativeContent):
    expected_current_revision: RevisionNumber


class TechnicalAlternativeRevisionRead(TechnicalAlternativeContent):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)
    id: str
    alternative_id: str
    tender_id: str
    revision: int
    fingerprint: str
    created_at: datetime


class TechnicalAlternativeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    tender_id: str
    created_at: datetime
    revisions: tuple[TechnicalAlternativeRevisionRead, ...]

    @property
    def current_revision(self) -> TechnicalAlternativeRevisionRead:
        return max(self.revisions, key=lambda row: row.revision)


def technical_content_fingerprint(content: TechnicalAlternativeContent) -> str:
    """v1: trimmed title/description/assumptions; excludes notes and lifecycle.

    Preserve internal whitespace, order, punctuation and case: no semantic inference.
    Empty optional assumptions and absence have the same technical meaning.
    """
    payload = {"contract": "technical-alternative-v1", "name": content.name,
               "technical_description": content.technical_description,
               "assumptions": content.assumptions or None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _identity(db: Session, tender_id: str, alternative_id: str, *, lock: bool = False) -> TechnicalAlternative:
    query = select(TechnicalAlternative).where(TechnicalAlternative.id == alternative_id,
                                               TechnicalAlternative.tender_id == tender_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise TechnicalAlternativeNotFound("Technical alternative not found in requested tender")
    return row


def get_technical_alternative(db: Session, *, tender_id: str, alternative_id: str) -> TechnicalAlternativeRead:
    with db.no_autoflush:
        identity = _identity(db, tender_id, alternative_id)
        rows = db.scalars(select(TechnicalAlternativeRevision).where(
            TechnicalAlternativeRevision.alternative_id == alternative_id,
            TechnicalAlternativeRevision.tender_id == tender_id,
        ).order_by(TechnicalAlternativeRevision.revision.asc())).all()
        if not rows:
            raise TechnicalAlternativeConflict("Alternative has no persisted revision")
        return TechnicalAlternativeRead(id=identity.id, tender_id=identity.tender_id,
                                        created_at=identity.created_at,
                                        revisions=tuple(TechnicalAlternativeRevisionRead.model_validate(row) for row in rows))


def list_technical_alternatives(db: Session, *, tender_id: str) -> tuple[TechnicalAlternativeRead, ...]:
    with db.no_autoflush:
        if db.get(Tender, tender_id) is None:
            raise TechnicalAlternativeNotFound("Tender not found")
        ids = db.scalars(select(TechnicalAlternative.id).where(
            TechnicalAlternative.tender_id == tender_id).order_by(TechnicalAlternative.id.asc())).all()
        return tuple(get_technical_alternative(db, tender_id=tender_id, alternative_id=value) for value in ids)


def _insert_revision(db: Session, identity: TechnicalAlternative, content: TechnicalAlternativeContent,
                     revision: int) -> None:
    db.add(TechnicalAlternativeRevision(alternative_id=identity.id, tender_id=identity.tender_id,
                                       revision=revision, **content.model_dump(),
                                       fingerprint=technical_content_fingerprint(content)))
    db.flush()


def create_technical_alternative(db: Session, *, tender_id: str,
                                 content: TechnicalAlternativeContent) -> TechnicalAlternativeRead:
    content = TechnicalAlternativeContent.model_validate(content.model_dump())
    with db.no_autoflush:
        if db.get(Tender, tender_id) is None:
            raise TechnicalAlternativeNotFound("Tender not found")
        # Savepoint makes identity + initial revision atomic without committing caller work.
        with db.begin_nested():
            identity = TechnicalAlternative(tender_id=tender_id)
            db.add(identity)
            db.flush()
            _insert_revision(db, identity, content, 1)
        return get_technical_alternative(db, tender_id=tender_id, alternative_id=identity.id)


def append_technical_alternative_revision(db: Session, *, tender_id: str, alternative_id: str,
                                          content: TechnicalAlternativeAppend) -> TechnicalAlternativeRead:
    content = TechnicalAlternativeAppend.model_validate(content.model_dump())
    with db.no_autoflush:
        identity = _identity(db, tender_id, alternative_id, lock=True)
        current = get_technical_alternative(db, tender_id=tender_id, alternative_id=alternative_id).current_revision
        if current.revision != content.expected_current_revision:
            raise TechnicalAlternativeConflict("Technical alternative revision conflict")
        values = TechnicalAlternativeContent.model_validate(content.model_dump(exclude={"expected_current_revision"}))
        with db.begin_nested():
            _insert_revision(db, identity, values, current.revision + 1)
        return get_technical_alternative(db, tender_id=tender_id, alternative_id=alternative_id)


def archive_technical_alternative(db: Session, *, tender_id: str, alternative_id: str,
                                 expected_current_revision: int) -> TechnicalAlternativeRead:
    # Strict validation before acquiring locks or writing. No invented technical change.
    expectation = TypeAdapter(RevisionNumber).validate_python(expected_current_revision)
    with db.no_autoflush:
        current = get_technical_alternative(db, tender_id=tender_id, alternative_id=alternative_id).current_revision
        values = current.model_dump(include=set(TechnicalAlternativeContent.model_fields))
        values["lifecycle_state"] = "ARCHIVED"
        return append_technical_alternative_revision(
            db, tender_id=tender_id, alternative_id=alternative_id,
            content=TechnicalAlternativeAppend(**values, expected_current_revision=expectation))
