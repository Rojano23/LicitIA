"""Pure normalized readiness over canonical domain snapshots; no extraction or pricing."""
from typing import Literal
from uuid import UUID, uuid5
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from app.workspace_flow import WorkspaceRead
from app.commercial_projections import TenderCommercialReadiness

Dimension = Literal['DOCUMENTS', 'REQUIREMENTS', 'REQUESTED_EVIDENCE', 'SCOPE', 'QUANTITIES', 'COMMERCIAL', 'HUMAN_REVIEW']
Status = Literal['READY', 'INCOMPLETE', 'REVIEW_REQUIRED', 'BLOCKED', 'NOT_APPLICABLE']
Severity = Literal['BLOCKER', 'REVIEW', 'WARNING']
DIMENSIONS = ('DOCUMENTS', 'REQUIREMENTS', 'REQUESTED_EVIDENCE', 'SCOPE', 'QUANTITIES', 'COMMERCIAL', 'HUMAN_REVIEW')
NAMESPACE = UUID('52420f58-443f-4f8e-85c1-d669b8cf10e4')
NOTICE = 'Listo sólo según los registros actualmente rastreados por LicitIA; la revisión humana es autoritativa. No certifica cumplimiento contractual ni completitud del checklist.'


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Reference(Contract):
    document_id: str | None = None
    revision: int | None = None
    page: int | None = None
    locator: str | None = None
    excerpt: str | None = None


class DocumentState(Contract):
    id: str
    tender_id: str
    status: str
    processing_status: str
    is_current: bool
    available: bool
    revision: int
    conflict_resolution_action: str | None = None


class SourceConflict(Contract):
    entity_id: str
    status: str
    code: str
    reasons: list[str] = Field(default_factory=list)
    source_document_id: str | None = None
    source_locator: str | None = None


class CanonicalReadinessInput(Contract):
    tender_id: str
    workspace: WorkspaceRead
    commercial: TenderCommercialReadiness
    documents: list[DocumentState]
    source_conflicts: list[SourceConflict] = Field(default_factory=list)


class ReadinessItem(Contract):
    id: str
    tender_id: str
    dimension: Dimension
    entity_type: str
    entity_id: str
    status: Status
    severity: Severity | None
    code: str
    summary: str
    underlying: dict[str, JsonValue]
    reference: Reference | None = None
    review_context: str
    source_module: str


class DimensionReadiness(Contract):
    dimension: Dimension
    status: Status
    item_count: int
    issue_count: int


class TenderBidReadiness(Contract):
    contract_version: Literal['bid-readiness-v1'] = 'bid-readiness-v1'
    tender_id: str
    status: Status
    blocker_count: int
    review_required_count: int
    warning_count: int
    total_issues: int
    ready_dimensions: list[Dimension]
    incomplete_dimensions: list[Dimension]
    dimensions: list[DimensionReadiness]
    items: list[ReadinessItem]
    issues: list[ReadinessItem]
    notice: str = NOTICE


def aggregate_status(statuses):
    for status in ['BLOCKED', 'INCOMPLETE', 'REVIEW_REQUIRED']:
        if status in statuses:
            return status
    return 'READY' if 'READY' in statuses else 'NOT_APPLICABLE'


def build_readiness(snapshot: CanonicalReadinessInput) -> TenderBidReadiness:
    tender = snapshot.tender_id
    w = snapshot.workspace
    if w.tender_id != tender or w.requirements.tender_id != tender or w.semantics.tender_id != tender or snapshot.commercial.tender_id != tender or any(d.tender_id != tender for d in snapshot.documents):
        raise ValueError('READINESS_TENDER_MISMATCH')
    documents = {d.id:d for d in snapshot.documents}
    items = []
    def reference(source):
        if not source:
            return None
        document_id = source.get('document_id') or source.get('source_document_id')
        doc = documents.get(document_id)
        return Reference(document_id=document_id, revision=doc.revision if doc else None,
            page=source.get('page', source.get('source_page')), locator=source.get('locator'),
            excerpt=source.get('excerpt', source.get('source_excerpt')) if doc else None)
    def add(dim, entity, identity, status, code, summary, *, underlying=None, source=None, severity=None, module='workspace_flow'):
        if severity is None and status not in {'READY','NOT_APPLICABLE'}:
            severity = 'REVIEW' if status == 'REVIEW_REQUIRED' else 'BLOCKER'
        stable = str(uuid5(NAMESPACE, '\x1f'.join([tender,dim,entity,identity,code])))
        context = f'/tenders/{tender}/scopes/{identity}/commercial-readiness' if dim=='COMMERCIAL' else f'/tenders/{tender}/scope-review/{identity}' if entity=='SCOPE' else f'/tenders/{tender}/requirement-matrix' if entity in {'REQUIREMENT','REQUESTED_EVIDENCE'} else f'/tenders/{tender}/workspace'
        items.append(ReadinessItem(id=stable,tender_id=tender,dimension=dim,entity_type=entity,entity_id=identity,
            status=status,severity=severity,code=code,summary=summary,underlying=underlying or {},reference=reference(source),review_context=context,source_module=module))
    def review_signal(entity,identity,code,underlying,source=None):
        add('HUMAN_REVIEW',entity,identity,'REVIEW_REQUIRED',code,'Decisión humana pendiente o desactualizada.',underlying=underlying,source=source)

    if not documents:
        add('DOCUMENTS','TENDER',tender,'INCOMPLETE','DOCUMENTS_NOT_OBSERVED','No hay documentos registrados; la cobertura es desconocida.')
    for d in snapshot.documents:
        state = {'status':d.status,'processing_status':d.processing_status,'is_current':d.is_current,'conflict_resolution_action':d.conflict_resolution_action}
        if d.status == 'NAME_CONFLICT' and d.conflict_resolution_action in {None,'NONE'}:
            status,code = 'BLOCKED','DOCUMENT_NAME_CONFLICT'
        elif not d.is_current:
            status,code = 'NOT_APPLICABLE','DOCUMENT_HISTORICAL_REVISION'
        elif not d.available or d.status == 'FAILED' or d.processing_status == 'TEXT_EXTRACTION_FAILED':
            status,code = 'BLOCKED','DOCUMENT_UNAVAILABLE_OR_FAILED'
        elif d.status != 'IMPORTED' or d.processing_status != 'TEXT_EXTRACTION_COMPLETE':
            status,code = 'INCOMPLETE','DOCUMENT_PROCESSING_INCOMPLETE'
        else:
            status,code = 'READY','DOCUMENT_REGISTERED_AND_PREPARED'
        add('DOCUMENTS','DOCUMENT',d.id,status,code,'Estado registrado del documento.',underlying=state,source={'document_id':d.id})
    processing = w.processing.status
    if processing not in {'COMPLETED','COMPLETED_REVIEW_REQUIRED'}:
        add('DOCUMENTS','TENDER',tender,'BLOCKED' if processing in {'FAILED','INTERRUPTED'} else 'INCOMPLETE',
            'WORKSPACE_'+processing,'El procesamiento canónico no está completo/vigente.',underlying={'status':processing})
    if w.processing.provider_degraded:
        add('DOCUMENTS','TENDER',tender,'REVIEW_REQUIRED','PERCEPTION_DEGRADED','La percepción existente está degradada.',underlying={'provider_degraded':True})
    for conflict in snapshot.source_conflicts:
        add('HUMAN_REVIEW','SOURCE_EFFECT',conflict.entity_id,'BLOCKED' if conflict.status=='CONFLICT' else 'REVIEW_REQUIRED',conflict.code,
            'Conflicto o efecto fuente pendiente; no se resuelve automáticamente.',underlying={'status':conflict.status,'reasons':conflict.reasons},source={'document_id':conflict.source_document_id,'locator':conflict.source_locator},module='effective_source_projection')

    requirements = w.requirements.requirements
    if not requirements:
        add('REQUIREMENTS','TENDER',tender,'INCOMPLETE','REQUIREMENTS_NOT_OBSERVED','No hay requisitos rastreados; no confirma ausencia de obligaciones.')
        add('REQUESTED_EVIDENCE','TENDER',tender,'INCOMPLETE','EVIDENCE_COVERAGE_UNKNOWN','Sin requisitos no se puede determinar cobertura de evidencia solicitada.')
    for r in requirements:
        raw = {k:getattr(r,k) for k in ['effective_status','effective_reasons','normalization_status','applicability','interpretation_status','interpretation_reason','evidence_mode','review_status','review_freshness','system_warnings']}
        source = r.primary_source.model_dump(mode='json') if r.primary_source else None
        if r.effective_status == 'SUPERSEDED' or r.review_status == 'REJECTED' and r.review_freshness == 'CURRENT':
            status,code = 'NOT_APPLICABLE','REQUIREMENT_EXCLUDED_BY_CANONICAL_STATE'
        elif r.effective_status not in {'EFFECTIVE'} or r.applicability not in {'MANDATORY','CONDITIONAL'} or r.review_status!='APPROVED' or r.review_freshness!='CURRENT' or not source or source.get('source_document_id') not in documents:
            status,code = 'REVIEW_REQUIRED','REQUIREMENT_REVIEW_REQUIRED'
        else:
            status,code = 'READY','REQUIREMENT_REPRESENTATION_ACCEPTED'
        add('REQUIREMENTS','REQUIREMENT',r.requirement_id,status,code,'Estado actual de la representación del requisito.',underlying=raw,source=source,module='requirement_matrix')
        if status=='REVIEW_REQUIRED':
            review_signal('REQUIREMENT',r.requirement_id,'REQUIREMENT_HUMAN_REVIEW',raw,source)
        if status=='READY' and (r.normalization_status!='NORMALIZED' or r.interpretation_status!='DETERMINED' or r.system_warnings):
            add('REQUIREMENTS','REQUIREMENT',r.requirement_id,'READY','REPRESENTATION_HUMAN_ACCEPTED_WITH_WARNINGS','La revisión humana vigente aceptó la representación; se conservan señales automáticas.',underlying=raw|{'system_warnings':r.system_warnings},source=source,severity='WARNING',module='requirement_matrix')
        if status=='READY' and r.applicability=='CONDITIONAL':
            add('REQUIREMENTS','REQUIREMENT',r.requirement_id,'READY','CONDITIONAL_CONTEXT','El requisito conserva aplicabilidad condicional.',underlying=raw,source=source,severity='WARNING',module='requirement_matrix')
        if status=='NOT_APPLICABLE':
            add('REQUESTED_EVIDENCE','REQUIREMENT',r.requirement_id,'NOT_APPLICABLE','EVIDENCE_PARENT_EXCLUDED','Padre excluido por estado canónico.',underlying=raw,source=source)
            continue
        if not r.expected_evidence:
            direct = r.evidence_mode=='DIRECT_VERIFICATION' and status=='READY'
            add('REQUESTED_EVIDENCE','REQUIREMENT',r.requirement_id,'NOT_APPLICABLE' if direct else 'REVIEW_REQUIRED',
                'DIRECT_VERIFICATION_NO_ARTIFACT' if direct else 'EVIDENCE_DEFINITION_UNRESOLVED','Estado de definición de evidencia solicitada.',underlying=raw,source=source,module='requirement_matrix')
        for e in r.expected_evidence:
            evidence_source = e.model_dump(mode='json')
            valid = e.requirement_id==r.requirement_id and status=='READY' and r.evidence_mode=='EXPLICIT_ARTIFACT' and e.evidence_type not in {'UNKNOWN','OTHER',''} and bool(e.source_excerpt) and e.source_document_id in documents
            add('REQUESTED_EVIDENCE','REQUESTED_EVIDENCE',e.id,'READY' if valid else 'REVIEW_REQUIRED','EVIDENCE_REQUEST_DEFINED' if valid else 'EVIDENCE_REQUEST_REVIEW_REQUIRED',
                'Definición extraída; no demuestra cumplimiento ni entrega.',underlying=raw|{'evidence_type':e.evidence_type,'requirement_id':r.requirement_id},source=evidence_source,module='requirement_matrix')
            if not valid:
                review_signal('REQUESTED_EVIDENCE',e.id,'EVIDENCE_HUMAN_REVIEW',raw|{'evidence_type':e.evidence_type},evidence_source)
    add('REQUESTED_EVIDENCE','TENDER',tender,'READY','TRACKED_REQUESTS_ONLY','La cobertura contractual y el cumplimiento empresarial no se certifican en M8-A.',severity='WARNING',module='bid_readiness')

    if not w.scopes:
        add('SCOPE','TENDER',tender,'INCOMPLETE','SCOPE_NOT_OBSERVED','Sin Scope rastreado; no confirma ausencia de alcance.')
        add('QUANTITIES','TENDER',tender,'INCOMPLETE','QUANTITY_COVERAGE_UNKNOWN','No se determina cobertura de cantidades sin Scope.')
    scope_ids = {s.scope_detail_id for s in w.scopes}
    for s in w.scopes:
        current = s.review.current if s.review else None
        original = current.effective_status if current else 'SOURCE_BLOCKED'
        raw = {'status':original,'item_reference':s.candidate_item_key,'not_reviewable_reason':s.review.not_reviewable_reason if s.review else None,'source_projection_status':current.source_projection.status if current else None,'blocking_effect_ids':list(current.source_projection.blocking_effect_ids) if current else []}
        source = s.source.model_dump(mode='json')
        if not s.source.available or s.source.document_id not in documents or original in {'SOURCE_BLOCKED','REJECTED'}:
            status = 'BLOCKED'
        elif original in {'CONFIRMED','CORRECTED','NOT_REQUIRED'}:
            status = 'READY'
        else:
            status = 'REVIEW_REQUIRED'
        if not s.candidate_item_key:
            status = 'REVIEW_REQUIRED' if status=='READY' else status
        add('SCOPE','SCOPE',s.scope_detail_id,status,'SCOPE_'+original,'Estado canónico del alcance y su identidad.',underlying=raw,source=source,module='scope_review')
        if status not in {'READY','NOT_APPLICABLE'}:
            review_signal('SCOPE',s.scope_detail_id,'SCOPE_HUMAN_REVIEW',raw,source)
        if not s.quantities:
            add('QUANTITIES','SCOPE',s.scope_detail_id,'INCOMPLETE','MISSING_CANONICAL_QUANTITY','El Scope no tiene Quantity canónica.',source=source)
        for q in s.quantities:
            invalid = q.source.document_id not in documents or q.tender_id!=tender or q.scope_detail_id!=s.scope_detail_id or q.status=='UNRESOLVED'
            status = 'BLOCKED' if invalid else 'INCOMPLETE' if q.quantity_value is None or q.relation!='EXACT' else 'REVIEW_REQUIRED' if q.status!='NOT_REQUIRED' else 'READY'
            add('QUANTITIES','QUANTITY',q.id,status,'QUANTITY_'+('INVALID_PARENT_OR_SOURCE' if invalid else q.status),'Estado canónico de Quantity; sólo lectura.',underlying={'status':q.status,'scope_id':s.scope_detail_id,'recorded_parent_id':q.scope_detail_id,'recorded_tender_id':q.tender_id,'relation':q.relation},source=q.source.model_dump(mode='json'))
            if status=='REVIEW_REQUIRED':
                review_signal('QUANTITY',q.id,'QUANTITY_HUMAN_REVIEW',{'status':q.status,'scope_id':s.scope_detail_id},q.source.model_dump(mode='json'))
    scope_by_id = {s.scope_detail_id:s for s in w.scopes}
    for c in snapshot.commercial.items:
        if c.scope_id not in scope_ids:
            raise ValueError('READINESS_SCOPE_CONTEXT_MISMATCH')
        state = c.readiness
        commercial_source = scope_by_id[c.scope_id].source.model_dump(mode='json')
        if not state.reasons:
            add('COMMERCIAL','SCOPE',c.scope_id,state.status,'COMMERCIAL_'+state.status,'Estado comercial canónico.',underlying={'status':state.status},source=commercial_source,module='commercial_projections')
        for reason in state.reasons:
            status = 'READY' if reason.severity=='WARNING' else 'REVIEW_REQUIRED' if reason.severity=='REVIEW' else 'INCOMPLETE'
            add('COMMERCIAL','SCOPE',c.scope_id,status,reason.code,'Razón comercial canónica.',underlying={'status':state.status,'reason':reason.code},severity=reason.severity,source=commercial_source,module='commercial_projections')
    if set(c.scope_id for c in snapshot.commercial.items)!=scope_ids or not scope_ids:
        add('COMMERCIAL','TENDER',tender,'INCOMPLETE','COMMERCIAL_COVERAGE_INCOMPLETE','Cobertura comercial sin determinar.',module='commercial_projections')
    if not any(i.dimension=='HUMAN_REVIEW' for i in items):
        add('HUMAN_REVIEW','TENDER',tender,'NOT_APPLICABLE','NO_TRACKED_PENDING_REVIEW','No hay revisiones pendientes entre los registros consumidos.')
    items.sort(key=lambda i:(DIMENSIONS.index(i.dimension),i.entity_type,i.entity_id,i.code))
    issues = [i for i in items if i.severity is not None]
    dimensions = [DimensionReadiness(dimension=dim,status=aggregate_status([i.status for i in items if i.dimension==dim]),
        item_count=sum(i.dimension==dim for i in items),issue_count=sum(i.dimension==dim for i in issues)) for dim in DIMENSIONS]
    return TenderBidReadiness(tender_id=tender,status=aggregate_status([d.status for d in dimensions]),
        blocker_count=sum(i.severity=='BLOCKER' for i in issues),review_required_count=sum(i.severity=='REVIEW' for i in issues),
        warning_count=sum(i.severity=='WARNING' for i in issues),total_issues=len(issues),
        ready_dimensions=[d.dimension for d in dimensions if d.status in {'READY','NOT_APPLICABLE'}],
        incomplete_dimensions=[d.dimension for d in dimensions if d.status not in {'READY','NOT_APPLICABLE'}],dimensions=dimensions,items=items,issues=issues)
