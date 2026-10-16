from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol, Sequence
import re

from app.structured_evidence import StructuredEvidenceBlock

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
    structured_block: StructuredEvidenceBlock | None = None


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

    from app.ocr_scope_adapters import OcrScopeDetailAdapter

    return (VisionScopeDetailAdapter(), NativeScopeDetailAdapter(), OcrScopeDetailAdapter())


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

    default_interpreter = type(selected_adapter).__module__ in {
        'app.native_scope_detail_adapter','app.ocr_scope_adapters','app.vision_scope_detail_adapter'}
    try:
        candidates = list(selected_adapter.extract_candidates(db, artifact))
    except ValueError as exc:
        if str(exc) != 'AMBIGUOUS_NATIVE_FIELD' or not default_interpreter:
            raise
        candidates = []  # The new block retains duplicate fields as ambiguous evidence.
    # Legacy single-span behavior remains intact. Composite rows use a distinct
    # validated contract, including on pages containing both kinds of evidence.
    payload = artifact.payload or {}
    detail = payload.get('detail_transcription') or {}
    text = payload.get('text') or detail.get('raw_text') or ''
    composite_shape = bool(re.search(r'(?im)^.*(?:partida|item|ítem)[ \t]*[|\t].*(?:cantidad|quantity)',text)
                           or re.search(r'(?m)^ +\S',text))
    if default_interpreter and (not candidates or composite_shape):
        from app.structured_evidence_grounding import extract_candidates
        expanded = list(extract_candidates(db, artifact))
        # Composite pages are interpreted as bounded blocks, including any
        # labelled rows next to a table. Replace only the matching legacy item,
        # never every row that happens to share its description.
        composite = expanded
        for proposal in composite:
            def same_legacy_row(candidate):
                if getattr(candidate, 'structured_block', None) is not None:
                    return False
                marker = re.match(r'(?i)^\s*(?:PARTIDA|ITEM|ÍTEM)\s*:?\s*(\d+(?:\.\d+)*)\b',candidate.source_excerpt)
                return bool(marker and marker.group(1) == proposal.structured_block.item_raw
                            or composite_shape and candidate.source_excerpt.strip() == text.strip())
            candidates = [c for c in candidates if not same_legacy_row(c)]
            candidates.append(proposal)
    if artifact.transcription is not None:
        current = [e for e in artifact.transcription.candidates if e.lineage == "ACTIVE"
            and e.source_artifact_key == artifact.source_artifact_key
            and e.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED}]
        # No bridge can resurrect failed or deselected detail evidence.
        candidates = [candidate for candidate in candidates if any(candidate.source_excerpt in e.text for e in current)
                      or getattr(candidate, 'structured_block', None) is not None]
        from app.structured_evidence_grounding import validate_manifest
        from app.structured_evidence_storage import digest_from_locator
        for candidate in candidates:
            if getattr(candidate, 'structured_block', None) is not None:
                validate_manifest(db, digest_from_locator(candidate.source_locator))
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
        # Local positive row evidence cannot repair a proven continuity conflict.
        boundary_conflict = 'STRUCTURAL_BOUNDARY_CONFLICT' in artifact.structure.diagnostics
        candidates = [replace(candidate, review_required=True, applicability="UNRESOLVED",
            scope_segment_id=None, tender_item_id=None, candidate_item_key=None)
            if (getattr(candidate, "structured_block", None) is None or boundary_conflict) and (candidate.candidate_item_key is not None or candidate.scope_segment_id is not None
                or candidate.tender_item_id is not None) else candidate for candidate in candidates]
    result_adapter_version = selected_adapter.adapter_version
    if any(getattr(c, 'structured_block', None) is not None for c in candidates):
        from app.structured_evidence import POLICY_VERSION
        result_adapter_version += '/' + POLICY_VERSION
    if not persist:
        return ScopeDetailAdapterRunResult(
            source_artifact_key=artifact.source_artifact_key,
            adapter_name=selected_adapter.adapter_name,
            adapter_version=result_adapter_version,
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
            adapter_version=result_adapter_version,
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
        adapter_version=result_adapter_version,
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
