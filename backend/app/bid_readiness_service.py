"""Canonical read adapters and bounded filtered views; never run materialization."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models import TenderDocument
from app.workspace_flow import read_workspace
from app.commercial_projections import tender_readiness
from app.effective_source_projection import project_effective_sources_for_tender
from app.bid_readiness import CanonicalReadinessInput, DocumentState, SourceConflict, build_readiness


def read_bid_readiness(db, tender_id, *, batched=True):
    from app.read_batch import canonical_read_batch
    if batched:
        with canonical_read_batch(db, tender_id):
            return _read_bid_readiness(db, tender_id)
    return _read_bid_readiness(db, tender_id)


def _read_bid_readiness(db, tender_id):
    from app.main import _resolve_document_file_path
    with db.no_autoflush:
        workspace = read_workspace(db, tender_id)
        commercial = tender_readiness(db, tender_id)
        documents = []
        for d in db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tender_id).order_by(TenderDocument.id)):
            try:
                available = _resolve_document_file_path(d.stored_relative_path).is_file()
            except HTTPException:
                available = False
            documents.append(DocumentState(id=d.id,tender_id=tender_id,status=d.status,processing_status=d.processing_status,
                is_current=d.is_current,available=available,revision=d.revision_number,conflict_resolution_action=d.conflict_resolution_action))
        projection = project_effective_sources_for_tender(db,tender_id=tender_id)
        diagnostics = {}
        for diagnostic in projection.diagnostics:
            for identity in diagnostic.effect_ids:
                diagnostics.setdefault(identity, []).append(diagnostic)
        conflicts = []
        for status,code,identities in [('CONFLICT','SOURCE_EFFECT_CONFLICT',projection.conflicts),
                                       ('UNRESOLVED','SOURCE_EFFECT_UNRESOLVED',projection.unresolved_effects)]:
            for identity in identities:
                reasons = diagnostics.get(identity, [])
                source = next((d for d in reasons if d.source_document_id is not None), None)
                conflicts.append(SourceConflict(entity_id=identity,status=status,code=code,
                    reasons=sorted({d.code for d in reasons}),source_document_id=source.source_document_id if source else None,
                    source_locator=source.source_locator if source else None))
        return build_readiness(CanonicalReadinessInput(tender_id=tender_id,workspace=workspace,commercial=commercial,
            documents=documents,source_conflicts=conflicts))
