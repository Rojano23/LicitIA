from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol, Sequence

from sqlalchemy.orm import Session

from app.models import TenderScopeDetail
from app.document_intelligence import RoutingResult, Quality
from app.critical_identifier_comparison import IdentifierComparison
from app.document_identifier_bindings import affected_comparisons, page_identifier_comparisons, review_comparisons, transcription_requires_review
from app.scope_details import ScopeDetailCandidate, replace_scope_details_for_artifact

SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED = "ADAPTED"
SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS = "NO_DETAILS"
SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED = "UNSUPPORTED"
SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class ScopeDetailEvidenceArtifact:
    tender_id: str
    source_document_id: str
    document_page_id: str
    source_method: str
    source_artifact_key: str
    source_contract_version: str | None = None
    source_locator: str | None = None
    source_analysis_id: str | None = None
    source_page_result_id: str | None = None
    payload: dict | None = None
    transcription: RoutingResult | None = None
    structure: RoutingResult | None = None
    identifier_comparisons: tuple[IdentifierComparison, ...] = ()


@dataclass(frozen=True, slots=True)
class ScopeDetailEvidenceCandidate(ScopeDetailCandidate):
    # Transient claims used for cross-capability disagreement checks. Canonical
    # persistence and explicit regeneration retain the existing candidate shape.
    attribute_bindings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ScopeDetailAdapterRunResult:
    source_artifact_key: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int
    candidates: tuple[ScopeDetailCandidate, ...] = ()
    errors: tuple[str, ...] = ()


class ScopeDetailAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def supports(self, artifact: ScopeDetailEvidenceArtifact) -> bool:
        ...

    def extract_candidates(self, db: Session, artifact: ScopeDetailEvidenceArtifact) -> Sequence[ScopeDetailCandidate]:
        ...


def _default_adapters() -> tuple[ScopeDetailAdapter, ...]:
    from app.vision_scope_detail_adapter import VisionScopeDetailAdapter

    from app.native_scope_detail_adapter import NativeScopeDetailAdapter

    return (VisionScopeDetailAdapter(), NativeScopeDetailAdapter())


def adapt_and_persist_scope_detail_artifact(
    db: Session,
    artifact: ScopeDetailEvidenceArtifact,
    *,
    adapters: Sequence[ScopeDetailAdapter] | None = None,
    persist: bool = True,
) -> ScopeDetailAdapterRunResult:
    available_adapters = tuple(adapters or _default_adapters())

    selected_adapter: ScopeDetailAdapter | None = None
    for adapter in available_adapters:
        if adapter.supports(artifact):
            selected_adapter = adapter
            break

    if selected_adapter is None:
        return ScopeDetailAdapterRunResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=None,
            adapter_version=None,
            status=SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
        )

    candidates = list(selected_adapter.extract_candidates(db, artifact))
    if artifact.transcription is not None:
        current = [e for e in artifact.transcription.candidates if e.lineage == "ACTIVE"
            and e.source_artifact_key == artifact.source_artifact_key
            and e.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED}]
        # No bridge can resurrect failed or deselected detail evidence.
        candidates = [candidate for candidate in candidates if any(candidate.source_excerpt in e.text for e in current)]
        comparisons = artifact.identifier_comparisons or page_identifier_comparisons(artifact.transcription,
            *((artifact.structure,) if artifact.structure is not None else ()))
        guarded = []
        for candidate in candidates:
            critical = affected_comparisons(comparisons,candidate.source_excerpt)
            if not critical and candidate.candidate_item_key is not None:
                from app.critical_identifier_comparison import IdentifierKind
                from app.item_identity import normalize_item_identity
                # Map risk to a pre-existing owner key; never use this legacy
                # normalization to assert agreement between perception values.
                critical = tuple(c for c in review_comparisons(comparisons) if c.kind in {IdentifierKind.ITEM_NUMBER,IdentifierKind.PARTIDA,IdentifierKind.STRUCTURAL_GROUP_IDENTIFIER}
                    and any(normalize_item_identity(o.raw_value).normalized_key == candidate.candidate_item_key
                        for o in c.observations if o.source.lineage == "ACTIVE"))
            if critical:
                candidate = replace(candidate,review_required=True, applicability="UNRESOLVED",
                    scope_segment_id=None,tender_item_id=None,candidate_item_key=None)
            elif transcription_requires_review(artifact.transcription,candidate.source_excerpt):
                candidate = replace(candidate,review_required=True)
            guarded.append(candidate)
        candidates = guarded
    if artifact.structure is not None and artifact.structure.status != "RESOLVED":
        candidates = [replace(candidate, review_required=True, applicability="UNRESOLVED",
            scope_segment_id=None, tender_item_id=None, candidate_item_key=None)
            if (candidate.candidate_item_key is not None or candidate.scope_segment_id is not None
                or candidate.tender_item_id is not None) else candidate for candidate in candidates]
    if not persist:
        return ScopeDetailAdapterRunResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected_adapter.adapter_name,
            adapter_version=selected_adapter.adapter_version,
            status=(SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED if any(c.review_required for c in candidates)
                    else SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED if candidates else SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS),
            candidate_count=len(candidates), persisted_count=0,
            review_required_count=sum(c.review_required for c in candidates), candidates=tuple(candidates))
    if not candidates:
        replace_scope_details_for_artifact(
            db,
            tender_id=artifact.tender_id,
            source_document_id=artifact.source_document_id,
            document_page_id=artifact.document_page_id,
            source_artifact_key=artifact.source_artifact_key,
            candidates=(),
        )
        return ScopeDetailAdapterRunResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected_adapter.adapter_name,
            adapter_version=selected_adapter.adapter_version,
            status=SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
        )

    persisted = replace_scope_details_for_artifact(
        db,
        tender_id=artifact.tender_id,
        source_document_id=artifact.source_document_id,
        document_page_id=artifact.document_page_id,
        source_artifact_key=artifact.source_artifact_key,
        candidates=candidates,
    )

    review_required_count = sum(1 for row in persisted if row.review_required)
    status = (
        SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED
        if review_required_count > 0
        else SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED
    )

    return ScopeDetailAdapterRunResult(
        source_artifact_key=artifact.source_artifact_key,
        adapter_name=selected_adapter.adapter_name,
        adapter_version=selected_adapter.adapter_version,
        status=status,
        candidate_count=len(candidates),
        persisted_count=len(persisted),
        review_required_count=review_required_count,
    )


def count_persisted_scope_details_for_artifact(
    db: Session,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
) -> int:
    return len(
        db.query(TenderScopeDetail)
        .filter(
            TenderScopeDetail.tender_id == tender_id,
            TenderScopeDetail.source_document_id == source_document_id,
            TenderScopeDetail.document_page_id == document_page_id,
            TenderScopeDetail.source_artifact_key == source_artifact_key,
        )
        .all()
    )
