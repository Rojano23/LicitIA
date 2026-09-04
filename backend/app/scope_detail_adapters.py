from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from sqlalchemy.orm import Session

from app.models import TenderScopeDetail
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


@dataclass(frozen=True, slots=True)
class ScopeDetailAdapterRunResult:
    source_artifact_key: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int


class ScopeDetailAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def supports(self, artifact: ScopeDetailEvidenceArtifact) -> bool:
        ...

    def extract_candidates(self, db: Session, artifact: ScopeDetailEvidenceArtifact) -> Sequence[ScopeDetailCandidate]:
        ...


def _default_adapters() -> tuple[ScopeDetailAdapter, ...]:
    from app.vision_scope_detail_adapter import VisionScopeDetailAdapter

    return (VisionScopeDetailAdapter(),)


def adapt_and_persist_scope_detail_artifact(
    db: Session,
    artifact: ScopeDetailEvidenceArtifact,
    *,
    adapters: Sequence[ScopeDetailAdapter] | None = None,
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
    if not candidates:
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
