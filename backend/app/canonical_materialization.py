"""Accepted available-evidence composition; no provider acquisition or benchmark policy."""
from sqlalchemy import select
from app.models import TenderScopeDetail

def materialize_canonical(db,tender_id,documents):
    from app.document_structure_orchestrator import orchestrate_document_structure_available_only
    from app.scope_detail_materializer import materialize_document_scope_details
    from app.scope_attribute_materializer import materialize_scope_attributes_for_scope_detail
    from app.scope_quantity_materializer import materialize_scope_quantities_for_scope_detail
    from app.requirement_extraction import analyze_tender_requirements
    from app.requirement_normalization import normalize_tender_requirements
    from app.requirement_semantics import analyze_tender_requirement_semantics
    from app.source_effect_materializer import materialize_document_source_effects
    analyze_tender_requirements(db,tender_id)
    normalize_tender_requirements(db,tender_id)
    analyze_tender_requirement_semantics(db,tender_id)
    from app.requirement_versioning import analyze_tender_requirement_versions
    analyze_tender_requirement_versions(db,tender_id)
    for document in documents:
        orchestrate_document_structure_available_only(db,tender_id=tender_id,document_id=document.id,
            execution_policy='AVAILABLE_ONLY')
        materialize_document_scope_details(db,tender_id=tender_id,document_id=document.id)
        for detail in db.scalars(select(TenderScopeDetail).where(TenderScopeDetail.source_document_id==document.id)):
            materialize_scope_attributes_for_scope_detail(db,scope_detail_id=detail.id)
            materialize_scope_quantities_for_scope_detail(db,scope_detail_id=detail.id)
        materialize_document_source_effects(db,tender_id=tender_id,acting_document_id=document.id)
