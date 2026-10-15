from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, NormalizedContent, PageOcrResult
from app.document_intelligence_sources import PersistedPerceptionArtifact, _enumerate_persisted_artifacts_for_document, load_document_transcriptions, load_page_structure, transcription_from_artifact
from app.document_intelligence import Capability, RoutingResult, advance_continuity, route_capability
from app.document_identifier_bindings import guard_structure, page_identifier_comparisons
from app.scope_semantic_discovery import ScopeSemanticDiscoveryProvider
from app.models import TenderDocument, TenderScopeDetail
from app.scope_details import replace_scope_details_for_artifact
from app.scope_logical_identity import ScopeLogicalEvidence
from app.scope_detail_adapters import (
    SCOPE_DETAIL_ADAPTER_STATUS_ADAPTED,
    SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS,
    SCOPE_DETAIL_ADAPTER_STATUS_REVIEW_REQUIRED,
    SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
    ScopeDetailAdapter,
    ScopeDetailAdapterRunResult,
    ScopeDetailEvidenceArtifact,
    adapt_and_persist_scope_detail_artifact,
)

EXECUTION_POLICY_AVAILABLE_ONLY = "AVAILABLE_ONLY"

SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED = "MATERIALIZED"
SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL = "PARTIAL"
SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_DETAILS = "NO_DETAILS"
SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE = "NO_EVIDENCE"
SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED = "DESELECTED"

VISION_DETAIL_TASK_TYPE = "DETAIL_TRANSCRIPTION"


@dataclass(frozen=True, slots=True)
class ScopeDetailMaterializationArtifactResult:
    source_artifact_key: str
    source_method: str
    adapter_name: str | None
    adapter_version: str | None
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScopeDetailMaterializationResult:
    tender_id: str
    document_id: str
    execution_policy: str
    pages_seen: int
    artifacts_seen: int
    artifacts_supported: int
    artifacts_materialized: int
    artifacts_no_details: int
    artifacts_unsupported: int
    artifacts_review_required: int
    candidate_count: int
    persisted_count: int
    review_required_count: int
    status: str
    artifact_results: tuple[ScopeDetailMaterializationArtifactResult, ...]
    logical_evidence: tuple[ScopeLogicalEvidence, ...] = ()


def materialize_document_scope_details(
    db: Session,
    *,
    tender_id: str,
    document_id: str,
    execution_policy: str = EXECUTION_POLICY_AVAILABLE_ONLY,
    adapters: Sequence[ScopeDetailAdapter] | None = None,
    semantic_providers: Sequence[ScopeSemanticDiscoveryProvider] | None = None,
) -> ScopeDetailMaterializationResult:
    if execution_policy != EXECUTION_POLICY_AVAILABLE_ONLY:
        raise ValueError(f"Unsupported execution policy: {execution_policy}")

    pages = db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc(), DocumentPage.id.asc())
    ).scalars().all()

    enumerated = _enumerate_persisted_artifacts_for_document(
        db,
        tender_id=tender_id,
        document_id=document_id,
        pages=pages,
    )

    document = db.get(TenderDocument, document_id)
    if document is None or document.tender_id != tender_id:
        raise ValueError("DOCUMENT_TENDER_MISMATCH")
    transcriptions = load_document_transcriptions(db, document)
    structures: dict[str, RoutingResult] = {}
    previous_continuity = None
    for page in pages:
        structure = load_page_structure(db, document, page)
        structure = guard_structure(structure,page_identifier_comparisons(transcriptions[page.id],structure))
        continuity = advance_continuity(structure, previous_continuity)
        previous_continuity = continuity
        if structure.status == "RESOLVED" and continuity.status != "VALID":
            structure = RoutingResult(page=structure.page, capability=Capability.STRUCTURE,
                status="REVIEW_REQUIRED", candidates=structure.candidates,
                diagnostics=continuity.diagnostics)
        structures[page.id] = structure
    if semantic_providers is not None:
        from app.scope_di_adapter import NeutralScopeSemanticAdapter
        from app.scope_detail_adapters import _default_adapters
        from app.native_scope_detail_adapter import NativeScopeDetailAdapter
        configured = tuple(adapters or _default_adapters())
        adapters = (tuple(a for a in configured if not isinstance(a, NativeScopeDetailAdapter))
                    + (NeutralScopeSemanticAdapter(tuple(semantic_providers)),)
                    + tuple(a for a in configured if isinstance(a, NativeScopeDetailAdapter)))

    artifact_results: list[ScopeDetailMaterializationArtifactResult] = []
    artifacts_supported = 0
    artifacts_materialized = 0
    artifacts_no_details = 0
    artifacts_unsupported = 0
    artifacts_review_required = 0
    candidate_count = 0
    persisted_count = 0
    review_required_count = 0

    for deselected in enumerated.deselected:
        nested_tx = db.begin_nested()
        try:
            replace_scope_details_for_artifact(
                db,
                tender_id=tender_id,
                source_document_id=document_id,
                document_page_id=deselected.artifact.document_page_id,
                source_artifact_key=deselected.artifact.source_artifact_key,
                candidates=(),
            )
            nested_tx.commit()
            artifact_results.append(
                ScopeDetailMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    adapter_name=None,
                    adapter_version=None,
                    status=SCOPE_DETAIL_MATERIALIZATION_ARTIFACT_STATUS_DESELECTED,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                )
            )
        except Exception:
            nested_tx.rollback()
            artifact_results.append(
                ScopeDetailMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    adapter_name=None,
                    adapter_version=None,
                    status=SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                )
            )

    prepared = []
    for enumerated_artifact in enumerated.active:
        nested_tx = db.begin_nested()
        try:
            adapter_result = adapt_and_persist_scope_detail_artifact(
                db,
                _scope_artifact_context(db, enumerated_artifact.artifact, transcriptions, structures),
                adapters=adapters, persist=False,
            )
            nested_tx.commit()
        except Exception as exc:
            nested_tx.rollback()
            adapter_result = ScopeDetailAdapterRunResult(
                source_artifact_key=enumerated_artifact.artifact.source_artifact_key,
                adapter_name=None,
                adapter_version=None,
                status="INVALID_EVIDENCE",
                candidate_count=0,
                persisted_count=0,
                review_required_count=0, errors=(str(exc),),
            )
        prepared.append((enumerated_artifact, adapter_result))

    from app.scope_logical_identity import reconcile_candidates
    existing = db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id == document_id)).all()
    chosen, logical_evidence = reconcile_candidates(
        [c for _, run in prepared for c in run.candidates], existing)
    for enumerated_artifact, adapter_result in prepared:
        if adapter_result.status not in {"INVALID_EVIDENCE", SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED}:
            batch = tuple(c for c in chosen if c.source_artifact_key == adapter_result.source_artifact_key)
            nested_tx = db.begin_nested()
            try:
                rows = replace_scope_details_for_artifact(db, tender_id=tender_id, source_document_id=document_id,
                    document_page_id=enumerated_artifact.artifact.document_page_id,
                    source_artifact_key=adapter_result.source_artifact_key, candidates=batch, reuse_unchanged=True)
                nested_tx.commit()
                adapter_result = replace(adapter_result, persisted_count=len(rows),
                    review_required_count=sum(r.review_required for r in rows))
            except Exception as exc:
                nested_tx.rollback()
                adapter_result = replace(adapter_result, status="INVALID_EVIDENCE", errors=(str(exc),))

        artifact_results.append(
            ScopeDetailMaterializationArtifactResult(
                source_artifact_key=adapter_result.source_artifact_key,
                source_method=enumerated_artifact.artifact.source_method,
                adapter_name=adapter_result.adapter_name,
                adapter_version=adapter_result.adapter_version,
                status=adapter_result.status,
                candidate_count=adapter_result.candidate_count,
                persisted_count=adapter_result.persisted_count,
                review_required_count=adapter_result.review_required_count, errors=adapter_result.errors,
            )
        )

        candidate_count += adapter_result.candidate_count
        persisted_count += adapter_result.persisted_count
        review_required_count += adapter_result.review_required_count

        if adapter_result.status in {SCOPE_DETAIL_ADAPTER_STATUS_UNSUPPORTED, "INVALID_EVIDENCE"}:
            artifacts_unsupported += 1
            continue

        artifacts_supported += 1
        if adapter_result.status == SCOPE_DETAIL_ADAPTER_STATUS_NO_DETAILS:
            artifacts_no_details += 1
        if adapter_result.persisted_count > 0:
            artifacts_materialized += 1
        if adapter_result.review_required_count > 0:
            artifacts_review_required += 1

    status = _summarize_materialization_status(
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_details=artifacts_no_details,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        persisted_count=persisted_count,
    )

    if any(r.errors for r in artifact_results):
        status = "INVALID_EVIDENCE"

    return ScopeDetailMaterializationResult(
        tender_id=tender_id,
        document_id=document_id,
        execution_policy=execution_policy,
        pages_seen=len(pages),
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_details=artifacts_no_details,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        candidate_count=candidate_count,
        persisted_count=persisted_count,
        review_required_count=review_required_count,
        status=status,
        artifact_results=tuple(artifact_results), logical_evidence=logical_evidence,
    )


def _summarize_materialization_status(
    *,
    artifacts_seen: int,
    artifacts_supported: int,
    artifacts_materialized: int,
    artifacts_no_details: int,
    artifacts_unsupported: int,
    artifacts_review_required: int,
    persisted_count: int,
) -> str:
    if artifacts_seen == 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_supported == 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_materialized == 0:
        if artifacts_no_details > 0:
            return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_DETAILS
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE
    if artifacts_review_required > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    if artifacts_unsupported > 0 or artifacts_no_details > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_PARTIAL
    if persisted_count > 0:
        return SCOPE_DETAIL_MATERIALIZATION_STATUS_MATERIALIZED
    return SCOPE_DETAIL_MATERIALIZATION_STATUS_NO_EVIDENCE


def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _scope_artifact_context(db: Session, artifact: PersistedPerceptionArtifact,
                            transcriptions: dict[str, RoutingResult],
                            structures: dict[str, RoutingResult]) -> ScopeDetailEvidenceArtifact:
    result = transcriptions[artifact.document_page_id]
    observation = transcription_from_artifact(db, artifact)
    if not any(e.source_artifact_key == observation.source_artifact_key
               and e.generation_id == observation.generation_id
               and e.source_method == observation.source_method
               and e.capability == observation.capability for e in result.candidates):
        result = route_capability(page=result.page, capability=Capability.TRANSCRIPTION,
            evidence=(*result.candidates, observation))
    return ScopeDetailEvidenceArtifact(**asdict(artifact), transcription=result,
        structure=structures[artifact.document_page_id],
        identifier_comparisons=page_identifier_comparisons(result,structures[artifact.document_page_id]))
