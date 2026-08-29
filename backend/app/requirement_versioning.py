from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.effective_tender_state import get_tender_effective_state
from app.models import (
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementEvidenceExpectation,
    RequirementSemantics,
    RequirementVersionLink,
    Tender,
    TenderChange,
)

REQUIREMENT_VERSIONING_VERSION = "mvp-04.5"

STATUS_EFFECTIVE = "EFFECTIVE"
STATUS_SUPERSEDED = "SUPERSEDED"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_UNRESOLVED = "UNRESOLVED"

LINK_SUPERSEDES = "SUPERSEDES"
LINK_INTRODUCES = "INTRODUCES"
LINK_RETIRES = "RETIRES"

MUTATING_TYPES = {"MODIFIES", "REPLACES", "CORRECTS", "ADDS", "REMOVES"}


@dataclass(frozen=True)
class _MatchResult:
    status: str
    requirement_id: str | None
    basis: str
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class _CandidateHit:
    requirement_id: str
    candidate_id: str
    score: int


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    compact = value.replace("\r\n", "\n").replace("\r", "\n")
    compact = compact.lower().strip()
    compact = _strip_accents(compact)
    compact = re.sub(r"\s+", " ", compact)
    return compact.strip()


def _contains_explicit_fragment(text: str, fragment: str) -> bool:
    if not text or not fragment:
        return False
    norm_text = _normalize_text(text)
    norm_fragment = _normalize_text(fragment)
    if len(norm_fragment) < 2:
        return False
    return norm_fragment in norm_text


def _serialize_primary_source(requirement: Requirement) -> dict[str, Any] | None:
    for link in sorted(requirement.candidate_links, key=lambda row: (0 if row.is_primary_source else 1, row.id)):
        candidate = link.candidate
        if candidate is None:
            continue
        source_document = candidate.source_document
        return {
            "candidate_id": candidate.id,
            "source_document_id": candidate.source_document_id,
            "source_filename": source_document.original_filename if source_document else None,
            "source_page": candidate.source_page,
            "requirement_text": candidate.requirement_text,
            "source_excerpt": candidate.source_excerpt,
            "actor_text": candidate.actor_text,
            "modality_text": candidate.modality_text,
            "is_primary_source": link.is_primary_source,
            "link_origin": link.link_origin,
        }
    return None


def _candidate_hits(
    *,
    requirements: list[Requirement],
    document_id: str,
    locator_text: str | None,
    fragment_text: str | None,
) -> list[_CandidateHit]:
    hits: list[_CandidateHit] = []

    for requirement in requirements:
        for link in requirement.candidate_links:
            candidate = link.candidate
            if candidate is None or candidate.source_document_id != document_id:
                continue

            score = 0
            if locator_text and _contains_explicit_fragment(candidate.requirement_text, locator_text):
                score += 2
            if locator_text and _contains_explicit_fragment(candidate.source_excerpt, locator_text):
                score += 2
            if fragment_text and _contains_explicit_fragment(candidate.requirement_text, fragment_text):
                score += 3
            if fragment_text and _contains_explicit_fragment(candidate.source_excerpt, fragment_text):
                score += 3

            if score <= 0:
                continue

            hits.append(_CandidateHit(requirement_id=requirement.id, candidate_id=candidate.id, score=score))

    return hits


def _resolve_unique_requirement(hits: list[_CandidateHit], *, side_label: str) -> _MatchResult:
    if not hits:
        return _MatchResult(status=STATUS_UNRESOLVED, requirement_id=None, basis=f"{side_label}:NO_EXPLICIT_MATCH", candidate_ids=())

    by_requirement: dict[str, int] = {}
    candidate_ids: set[str] = set()
    for hit in hits:
        by_requirement[hit.requirement_id] = max(by_requirement.get(hit.requirement_id, 0), hit.score)
        candidate_ids.add(hit.candidate_id)

    ordered = sorted(by_requirement.items(), key=lambda item: (-item[1], item[0]))
    if len(ordered) == 1:
        req_id, _score = ordered[0]
        return _MatchResult(
            status="RESOLVED",
            requirement_id=req_id,
            basis=f"{side_label}:UNIQUE_EXPLICIT_MATCH",
            candidate_ids=tuple(sorted(candidate_ids)),
        )

    top_score = ordered[0][1]
    second_score = ordered[1][1]
    if top_score > second_score:
        req_id, _score = ordered[0]
        return _MatchResult(
            status="RESOLVED",
            requirement_id=req_id,
            basis=f"{side_label}:UNIQUE_TOP_EXPLICIT_MATCH",
            candidate_ids=tuple(sorted(candidate_ids)),
        )

    ambiguous_req_ids = [req_id for req_id, score in ordered if score == top_score]
    return _MatchResult(
        status=STATUS_AMBIGUOUS,
        requirement_id=None,
        basis=f"{side_label}:AMBIGUOUS_EXPLICIT_MATCH:{','.join(sorted(ambiguous_req_ids))}",
        candidate_ids=tuple(sorted(candidate_ids)),
    )


def _build_requirement_index(requirements: list[Requirement]) -> dict[str, Requirement]:
    return {row.id: row for row in requirements}


def _candidate_owner_index(requirements: list[Requirement]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for requirement in requirements:
        for link in requirement.candidate_links:
            candidate = link.candidate
            if candidate is None:
                continue
            owners[candidate.id] = requirement.id
    return owners


def _serialize_version_link(link: RequirementVersionLink, requirement_index: dict[str, Requirement]) -> dict[str, Any]:
    predecessor = requirement_index.get(link.predecessor_requirement_id) if link.predecessor_requirement_id else None
    successor = requirement_index.get(link.successor_requirement_id) if link.successor_requirement_id else None
    return {
        "id": link.id,
        "change_id": link.change_id,
        "link_kind": link.link_kind,
        "matching_basis": link.matching_basis,
        "target_locator_text": link.target_locator_text,
        "before_text": link.before_text,
        "after_text": link.after_text,
        "predecessor_requirement_id": link.predecessor_requirement_id,
        "predecessor_canonical_text": predecessor.canonical_text if predecessor else None,
        "successor_requirement_id": link.successor_requirement_id,
        "successor_canonical_text": successor.canonical_text if successor else None,
        "analyzer_version": link.analyzer_version,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def _serialize_requirement_effective(
    requirement: Requirement,
    effective_status: str,
    effective_source_document_id: str | None,
    effective_source_filename: str | None,
    evidence_reasons: list[str],
) -> dict[str, Any]:
    semantics = requirement.semantics
    return {
        "requirement_id": requirement.id,
        "canonical_text": requirement.canonical_text,
        "category": requirement.category,
        "normalization_status": requirement.normalization_status,
        "effective_status": effective_status,
        "effective_source_document_id": effective_source_document_id,
        "effective_source_filename": effective_source_filename,
        "source_occurrence_count": len(requirement.candidate_links),
        "primary_source": _serialize_primary_source(requirement),
        "applicability": semantics.applicability if semantics is not None else "UNKNOWN",
        "interpretation_status": semantics.interpretation_status if semantics is not None else "REVIEW_REQUIRED",
        "evidence_mode": semantics.evidence_mode if semantics is not None else "REVIEW_REQUIRED",
        "evidence_reasons": evidence_reasons,
    }


def analyze_tender_requirement_versions(db: Session, tender_id: str) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics)
            .selectinload(RequirementSemantics.expected_evidence)
            .selectinload(RequirementEvidenceExpectation.source_document),
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    changes_by_id = {
        row.id: row
        for row in db.execute(
            select(TenderChange).where(TenderChange.tender_id == tender_id)
        ).scalars().all()
    }

    existing_links = db.execute(
        select(RequirementVersionLink)
        .where(RequirementVersionLink.tender_id == tender_id)
        .order_by(RequirementVersionLink.created_at.asc(), RequirementVersionLink.id.asc())
    ).scalars().all()

    effective_state = get_tender_effective_state(db, tender_id)
    candidate_owner = _candidate_owner_index(requirements)

    desired_links: list[dict[str, Any]] = []
    non_deterministic_reasons: dict[str, set[str]] = {req.id: set() for req in requirements}

    for scope in effective_state["scopes"]:
        effective_mutation = scope.get("effective_mutation")
        if not effective_mutation:
            continue

        change_id = effective_mutation.get("id")
        if not change_id or change_id not in changes_by_id:
            continue

        change_row = changes_by_id[change_id]
        if change_row.review_status != "CONFIRMED":
            continue

        change_type = effective_mutation.get("change_type")
        if change_type not in MUTATING_TYPES:
            continue

        target_document_id = effective_mutation.get("target_document_id")
        source_document_id = effective_mutation.get("source_document_id")
        locator_text = effective_mutation.get("target_locator_text")
        before_text = effective_mutation.get("before_text")
        after_text = effective_mutation.get("after_text")

        predecessor_match = _MatchResult(status=STATUS_UNRESOLVED, requirement_id=None, basis="PRE:NOT_EVALUATED", candidate_ids=())
        successor_match = _MatchResult(status=STATUS_UNRESOLVED, requirement_id=None, basis="POST:NOT_EVALUATED", candidate_ids=())

        if change_type != "ADDS" and target_document_id:
            predecessor_hits = _candidate_hits(
                requirements=requirements,
                document_id=target_document_id,
                locator_text=locator_text,
                fragment_text=before_text,
            )
            predecessor_match = _resolve_unique_requirement(predecessor_hits, side_label="PRE")

        if change_type != "REMOVES" and source_document_id:
            successor_hits = _candidate_hits(
                requirements=requirements,
                document_id=source_document_id,
                locator_text=locator_text,
                fragment_text=after_text,
            )
            successor_match = _resolve_unique_requirement(successor_hits, side_label="POST")

        if change_type in {"MODIFIES", "REPLACES", "CORRECTS"}:
            if predecessor_match.status == "RESOLVED" and successor_match.status == "RESOLVED":
                if predecessor_match.requirement_id == successor_match.requirement_id:
                    req_id = predecessor_match.requirement_id
                    if req_id:
                        non_deterministic_reasons[req_id].add(STATUS_AMBIGUOUS)
                else:
                    desired_links.append(
                        {
                            "change_id": change_id,
                            "predecessor_requirement_id": predecessor_match.requirement_id,
                            "successor_requirement_id": successor_match.requirement_id,
                            "link_kind": LINK_SUPERSEDES,
                            "matching_basis": f"{predecessor_match.basis}+{successor_match.basis}",
                            "target_locator_text": locator_text,
                            "before_text": before_text,
                            "after_text": after_text,
                        }
                    )
            else:
                reason_code = STATUS_AMBIGUOUS if STATUS_AMBIGUOUS in {predecessor_match.status, successor_match.status} else STATUS_UNRESOLVED
                for candidate_id in predecessor_match.candidate_ids + successor_match.candidate_ids:
                    req_id = candidate_owner.get(candidate_id)
                    if req_id:
                        non_deterministic_reasons[req_id].add(reason_code)
        elif change_type == "REMOVES":
            if predecessor_match.status == "RESOLVED":
                desired_links.append(
                    {
                        "change_id": change_id,
                        "predecessor_requirement_id": predecessor_match.requirement_id,
                        "successor_requirement_id": None,
                        "link_kind": LINK_RETIRES,
                        "matching_basis": predecessor_match.basis,
                        "target_locator_text": locator_text,
                        "before_text": before_text,
                        "after_text": after_text,
                    }
                )
            else:
                reason_code = STATUS_AMBIGUOUS if predecessor_match.status == STATUS_AMBIGUOUS else STATUS_UNRESOLVED
                for candidate_id in predecessor_match.candidate_ids:
                    req_id = candidate_owner.get(candidate_id)
                    if req_id:
                        non_deterministic_reasons[req_id].add(reason_code)
        elif change_type == "ADDS":
            if successor_match.status == "RESOLVED":
                desired_links.append(
                    {
                        "change_id": change_id,
                        "predecessor_requirement_id": None,
                        "successor_requirement_id": successor_match.requirement_id,
                        "link_kind": LINK_INTRODUCES,
                        "matching_basis": successor_match.basis,
                        "target_locator_text": locator_text,
                        "before_text": before_text,
                        "after_text": after_text,
                    }
                )
            else:
                reason_code = STATUS_AMBIGUOUS if successor_match.status == STATUS_AMBIGUOUS else STATUS_UNRESOLVED
                for candidate_id in successor_match.candidate_ids:
                    req_id = candidate_owner.get(candidate_id)
                    if req_id:
                        non_deterministic_reasons[req_id].add(reason_code)

    desired_signature = {
        (
            item["change_id"],
            item["predecessor_requirement_id"],
            item["successor_requirement_id"],
            item["link_kind"],
        ): item
        for item in desired_links
    }

    existing_signature = {
        (row.change_id, row.predecessor_requirement_id, row.successor_requirement_id, row.link_kind): row
        for row in existing_links
    }

    for signature, row in existing_signature.items():
        if signature in desired_signature:
            desired = desired_signature[signature]
            row.matching_basis = desired["matching_basis"]
            row.target_locator_text = desired["target_locator_text"]
            row.before_text = desired["before_text"]
            row.after_text = desired["after_text"]
            row.analyzer_version = REQUIREMENT_VERSIONING_VERSION
            continue
        db.delete(row)

    for signature, payload in desired_signature.items():
        if signature in existing_signature:
            continue
        db.add(
            RequirementVersionLink(
                tender_id=tender_id,
                change_id=payload["change_id"],
                predecessor_requirement_id=payload["predecessor_requirement_id"],
                successor_requirement_id=payload["successor_requirement_id"],
                link_kind=payload["link_kind"],
                matching_basis=payload["matching_basis"],
                target_locator_text=payload["target_locator_text"],
                before_text=payload["before_text"],
                after_text=payload["after_text"],
                analyzer_version=REQUIREMENT_VERSIONING_VERSION,
            )
        )

    db.flush()
    db.expire_all()
    return get_tender_requirement_effective_state(db, tender_id, non_deterministic_reasons=non_deterministic_reasons)


def get_tender_requirement_effective_state(
    db: Session,
    tender_id: str,
    *,
    non_deterministic_reasons: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise ValueError("Tender not found")

    requirements = db.execute(
        select(Requirement)
        .options(
            selectinload(Requirement.candidate_links)
            .selectinload(RequirementCandidateLink.candidate)
            .selectinload(RequirementCandidate.source_document),
            selectinload(Requirement.semantics),
        )
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.created_at.asc(), Requirement.id.asc())
    ).scalars().all()

    requirement_index = _build_requirement_index(requirements)

    links = db.execute(
        select(RequirementVersionLink)
        .where(RequirementVersionLink.tender_id == tender_id)
        .order_by(RequirementVersionLink.created_at.asc(), RequirementVersionLink.id.asc())
    ).scalars().all()

    superseded_ids: set[str] = set()
    introduced_ids: set[str] = set()
    retired_ids: set[str] = set()
    successor_source_by_req: dict[str, tuple[str, str | None]] = {}

    change_by_id = {
        row.id: row
        for row in db.execute(select(TenderChange).where(TenderChange.tender_id == tender_id)).scalars().all()
    }

    for link in links:
        if link.link_kind == LINK_SUPERSEDES:
            if link.predecessor_requirement_id:
                superseded_ids.add(link.predecessor_requirement_id)
            if link.successor_requirement_id:
                introduced_ids.add(link.successor_requirement_id)
        elif link.link_kind == LINK_RETIRES and link.predecessor_requirement_id:
            retired_ids.add(link.predecessor_requirement_id)
        elif link.link_kind == LINK_INTRODUCES and link.successor_requirement_id:
            introduced_ids.add(link.successor_requirement_id)

        if link.successor_requirement_id and link.change_id in change_by_id:
            change = change_by_id[link.change_id]
            doc_name = change.source_document.original_filename if change.source_document else None
            successor_source_by_req[link.successor_requirement_id] = (change.source_document_id, doc_name)

    if non_deterministic_reasons is None:
        non_deterministic_reasons = {req.id: set() for req in requirements}

    effective_requirements: list[dict[str, Any]] = []

    for requirement in requirements:
        reasons: list[str] = []
        status_flags = non_deterministic_reasons.get(requirement.id, set())

        if STATUS_AMBIGUOUS in status_flags:
            status = STATUS_AMBIGUOUS
            reasons.append("EXPLICIT_CHANGE_MAPPING_AMBIGUOUS")
            source_doc_id = None
            source_filename = None
        elif STATUS_UNRESOLVED in status_flags:
            status = STATUS_UNRESOLVED
            reasons.append("EXPLICIT_CHANGE_MAPPING_UNRESOLVED")
            source_doc_id = None
            source_filename = None
        elif requirement.id in superseded_ids or requirement.id in retired_ids:
            status = STATUS_SUPERSEDED
            reasons.append("REPLACED_BY_CONFIRMED_EXPLICIT_CHANGE")
            source_doc_id = None
            source_filename = None
        elif requirement.id in introduced_ids:
            status = STATUS_EFFECTIVE
            reasons.append("SUPPORTED_BY_CONFIRMED_EXPLICIT_CHANGE")
            source_doc_id, source_filename = successor_source_by_req.get(requirement.id, (None, None))
        else:
            status = STATUS_EFFECTIVE
            reasons.append("NO_CONFIRMED_EXPLICIT_SUPERSESSION")
            primary_source = _serialize_primary_source(requirement)
            source_doc_id = primary_source["source_document_id"] if primary_source else None
            source_filename = primary_source["source_filename"] if primary_source else None

        effective_requirements.append(
            _serialize_requirement_effective(
                requirement,
                effective_status=status,
                effective_source_document_id=source_doc_id,
                effective_source_filename=source_filename,
                evidence_reasons=reasons,
            )
        )

    summary = {
        "requirement_count": len(requirements),
        "effective_count": sum(1 for row in effective_requirements if row["effective_status"] == STATUS_EFFECTIVE),
        "superseded_count": sum(1 for row in effective_requirements if row["effective_status"] == STATUS_SUPERSEDED),
        "ambiguous_count": sum(1 for row in effective_requirements if row["effective_status"] == STATUS_AMBIGUOUS),
        "unresolved_count": sum(1 for row in effective_requirements if row["effective_status"] == STATUS_UNRESOLVED),
        "version_link_count": len(links),
    }

    return {
        "tender_id": tender_id,
        "analyzer_version": REQUIREMENT_VERSIONING_VERSION,
        "generated_at": datetime.now(timezone.utc),
        "scope_note": "Versionado derivado exclusivamente de cambios confirmados con evidencia explícita (locator/before/after); no usa similitud textual.",
        "summary": summary,
        "requirements": effective_requirements,
        "version_links": [_serialize_version_link(link, requirement_index) for link in links],
    }
