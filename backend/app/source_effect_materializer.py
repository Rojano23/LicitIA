from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentPage
from app.source_effect_adapters import (
    EXECUTION_POLICY_AVAILABLE_ONLY,
    SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE,
    SOURCE_EFFECT_ADAPTER_STATUS_MATERIALIZED,
    SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED,
    SourceEffectEvidenceArtifact,
    enumerate_source_effect_evidence_for_document,
    resolve_source_effect_evidence_artifact,
)
from app.source_effect_deterministic import discover_source_effects_from_evidence
from app.source_effects import replace_source_effects_for_artifact

SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED = "MATERIALIZED"
SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS = "NO_EFFECTS"
SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED = "UNSUPPORTED"
SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE = "INVALID_EVIDENCE"
SOURCE_EFFECT_MATERIALIZATION_STATUS_DESELECTED = "DESELECTED"


@dataclass(frozen=True, slots=True)
class SourceEffectMaterializationArtifactResult:
    source_artifact_key: str
    source_method: str
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int
    diagnostics: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceEffectMaterializationResult:
    tender_id: str
    acting_document_id: str
    execution_policy: str
    pages_seen: int
    artifacts_seen: int
    artifacts_supported: int
    artifacts_materialized: int
    artifacts_no_effects: int
    artifacts_unsupported: int
    artifacts_review_required: int
    candidate_count: int
    persisted_count: int
    review_required_count: int
    status: str
    artifact_results: tuple[SourceEffectMaterializationArtifactResult, ...]


@dataclass(frozen=True, slots=True)
class SourceEffectArtifactMaterializationResult:
    tender_id: str
    acting_document_id: str
    document_page_id: str
    source_artifact_key: str
    source_method: str
    status: str
    candidate_count: int
    persisted_count: int
    review_required_count: int
    diagnostics: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def materialize_source_effects_for_artifact(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_method: str,
    source_artifact_key: str,
) -> SourceEffectArtifactMaterializationResult:
    try:
        artifact = resolve_source_effect_evidence_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_document_id,
            document_page_id=document_page_id,
            source_method=source_method,
            source_artifact_key=source_artifact_key,
        )
    except ValueError as exc:
        return SourceEffectArtifactMaterializationResult(
            tender_id=tender_id,
            acting_document_id=acting_document_id,
            document_page_id=document_page_id,
            source_artifact_key=source_artifact_key,
            source_method=source_method,
            status=SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            errors=(str(exc),),
        )

    return _materialize_resolved_source_effect_artifact(db, artifact)


def materialize_document_source_effects(
    db: Session,
    *,
    tender_id: str,
    acting_document_id: str,
    execution_policy: str = EXECUTION_POLICY_AVAILABLE_ONLY,
) -> SourceEffectMaterializationResult:
    if execution_policy != EXECUTION_POLICY_AVAILABLE_ONLY:
        raise ValueError(f"Unsupported execution policy: {execution_policy}")

    pages = db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == acting_document_id)
        .order_by(DocumentPage.page_number.asc(), DocumentPage.id.asc())
    ).scalars().all()

    enumerated = enumerate_source_effect_evidence_for_document(
        db,
        tender_id=tender_id,
        document_id=acting_document_id,
        pages=pages,
    )

    artifact_results: list[SourceEffectMaterializationArtifactResult] = []
    artifacts_supported = 0
    artifacts_materialized = 0
    artifacts_no_effects = 0
    artifacts_unsupported = 0
    artifacts_review_required = 0
    candidate_count = 0
    persisted_count = 0
    review_required_count = 0

    for deselected in enumerated.deselected:
        nested_tx = db.begin_nested()
        try:
            replace_source_effects_for_artifact(
                db,
                tender_id=tender_id,
                acting_document_id=acting_document_id,
                document_page_id=deselected.artifact.document_page_id,
                source_artifact_key=deselected.artifact.source_artifact_key,
                candidates=[],
            )
            nested_tx.commit()
            artifact_results.append(
                SourceEffectMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    status=SOURCE_EFFECT_MATERIALIZATION_STATUS_DESELECTED,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                )
            )
        except Exception as exc:
            nested_tx.rollback()
            artifact_results.append(
                SourceEffectMaterializationArtifactResult(
                    source_artifact_key=deselected.artifact.source_artifact_key,
                    source_method=deselected.artifact.source_method,
                    status=SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
                    candidate_count=0,
                    persisted_count=0,
                    review_required_count=0,
                    errors=(str(exc),),
                )
            )

    for enumerated_artifact in enumerated.active:
        nested_tx = db.begin_nested()
        try:
            artifact_result = _materialize_resolved_source_effect_artifact(db, enumerated_artifact.artifact)
            nested_tx.commit()
        except Exception as exc:
            nested_tx.rollback()
            artifact_result = SourceEffectArtifactMaterializationResult(
                tender_id=tender_id,
                acting_document_id=acting_document_id,
                document_page_id=enumerated_artifact.artifact.document_page_id,
                source_artifact_key=enumerated_artifact.artifact.source_artifact_key,
                source_method=enumerated_artifact.artifact.source_method,
                status=SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
                candidate_count=0,
                persisted_count=0,
                review_required_count=0,
                errors=(str(exc),),
            )

        artifact_results.append(
            SourceEffectMaterializationArtifactResult(
                source_artifact_key=artifact_result.source_artifact_key,
                source_method=artifact_result.source_method,
                status=artifact_result.status,
                candidate_count=artifact_result.candidate_count,
                persisted_count=artifact_result.persisted_count,
                review_required_count=artifact_result.review_required_count,
                diagnostics=artifact_result.diagnostics,
                errors=artifact_result.errors,
            )
        )

        candidate_count += artifact_result.candidate_count
        persisted_count += artifact_result.persisted_count
        review_required_count += artifact_result.review_required_count

        if artifact_result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED:
            artifacts_unsupported += 1
            continue
        if artifact_result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE:
            continue

        artifacts_supported += 1

        if artifact_result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS:
            artifacts_no_effects += 1
        if artifact_result.persisted_count > 0:
            artifacts_materialized += 1
        if artifact_result.review_required_count > 0 or artifact_result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED:
            artifacts_review_required += 1

    status = _summarize_materialization_status(
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_effects=artifacts_no_effects,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        persisted_count=persisted_count,
    )

    return SourceEffectMaterializationResult(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        execution_policy=execution_policy,
        pages_seen=len(pages),
        artifacts_seen=len(enumerated.active) + len(enumerated.deselected),
        artifacts_supported=artifacts_supported,
        artifacts_materialized=artifacts_materialized,
        artifacts_no_effects=artifacts_no_effects,
        artifacts_unsupported=artifacts_unsupported,
        artifacts_review_required=artifacts_review_required,
        candidate_count=candidate_count,
        persisted_count=persisted_count,
        review_required_count=review_required_count,
        status=status,
        artifact_results=tuple(artifact_results),
    )


def _materialize_resolved_source_effect_artifact(
    db: Session,
    artifact: SourceEffectEvidenceArtifact,
) -> SourceEffectArtifactMaterializationResult:
    discovery = discover_source_effects_from_evidence(db, artifact)

    if discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED:
        return SourceEffectArtifactMaterializationResult(
            tender_id=artifact.tender_id,
            acting_document_id=artifact.acting_document_id,
            document_page_id=artifact.document_page_id,
            source_artifact_key=artifact.source_artifact_key,
            source_method=artifact.source_method,
            status=SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            diagnostics=discovery.diagnostics,
            errors=discovery.errors,
        )

    if discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_INVALID_EVIDENCE:
        return SourceEffectArtifactMaterializationResult(
            tender_id=artifact.tender_id,
            acting_document_id=artifact.acting_document_id,
            document_page_id=artifact.document_page_id,
            source_artifact_key=artifact.source_artifact_key,
            source_method=artifact.source_method,
            status=SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
            candidate_count=0,
            persisted_count=0,
            review_required_count=0,
            diagnostics=discovery.diagnostics,
            errors=discovery.errors,
        )

    persisted_count = 0
    review_required_count = 0
    should_replace = False

    if discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS:
        should_replace = True
    elif discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_MATERIALIZED:
        should_replace = True
    elif discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED:
        # Fail-closed: once supported evidence is successfully analyzed, stale
        # boundary rows must be replaced even if ambiguity yields zero candidates.
        should_replace = True

    if should_replace:
        persisted = replace_source_effects_for_artifact(
            db,
            tender_id=artifact.tender_id,
            acting_document_id=artifact.acting_document_id,
            document_page_id=artifact.document_page_id,
            source_artifact_key=artifact.source_artifact_key,
            candidates=list(discovery.candidates),
        )
        persisted_count = len(persisted)
        review_required_count = sum(1 for row in persisted if row.review_required)

    if discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_NO_EFFECTS:
        status = SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS
    elif review_required_count > 0 or discovery.status == SOURCE_EFFECT_ADAPTER_STATUS_REVIEW_REQUIRED:
        status = SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    else:
        status = SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED

    return SourceEffectArtifactMaterializationResult(
        tender_id=artifact.tender_id,
        acting_document_id=artifact.acting_document_id,
        document_page_id=artifact.document_page_id,
        source_artifact_key=artifact.source_artifact_key,
        source_method=artifact.source_method,
        status=status,
        candidate_count=len(discovery.candidates),
        persisted_count=persisted_count,
        review_required_count=review_required_count,
        diagnostics=discovery.diagnostics,
        errors=discovery.errors,
    )


def _summarize_materialization_status(
    *,
    artifacts_seen: int,
    artifacts_supported: int,
    artifacts_materialized: int,
    artifacts_no_effects: int,
    artifacts_unsupported: int,
    artifacts_review_required: int,
    persisted_count: int,
) -> str:
    if artifacts_seen == 0:
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS
    if artifacts_supported == 0:
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED
    if artifacts_materialized == 0:
        if artifacts_review_required > 0:
            return SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS
    if artifacts_review_required > 0:
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
    if artifacts_unsupported > 0 or artifacts_no_effects > 0:
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED
    if persisted_count > 0:
        return SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED
    return SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS
