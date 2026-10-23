"""External-safe export DTOs. Renderers receive no database/session objects."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field,model_validator
from app.proposal_readiness import Contract,digest

EXPORT_CONTRACT='proposal-export-v1'
ArtifactType=Literal['DOCX','XLSX','PDF']


class ExportRequest(Contract):
    request_id: UUID
    formats: list[ArtifactType]=Field(default_factory=lambda:['DOCX','XLSX','PDF'],min_length=1,max_length=3)
    include_package: bool=True
    allow_draft: bool=False
    expected_composition_revision: int | None=Field(default=None,ge=1,strict=True)
    expected_edit_revision: int | None=Field(default=None,ge=1,strict=True)
    actor_label: str | None=Field(default=None,max_length=200)

    @model_validator(mode='after')
    def unique(self):
        if len(set(self.formats))!=len(self.formats):raise ValueError('DUPLICATE_EXPORT_FORMAT')
        self.formats=[f for f in ['DOCX','XLSX','PDF'] if f in self.formats]
        return self


class ExportColumn(Contract):
    key: str
    label: str
    numeric: bool=False


class ExportRow(Contract):
    key: str
    values: dict[str,str]
    group: str | None=None
    document_id: str | None=None
    source_references: list[dict]=Field(default_factory=list)


class ExportSection(Contract):
    id: str
    title: str
    columns: list[ExportColumn]
    rows: list[ExportRow]


class ExportContent(Contract):
    contract_version: Literal['proposal-export-v1']=EXPORT_CONTRACT
    composition_contract: str
    tender_id: str
    proposal_id: str
    version_id: str
    proposal_version: int
    proposal_state: Literal['DRAFT','FROZEN']
    snapshot_id: str
    snapshot_sha256: str
    composition_sha256: str
    composition_revision: int
    frozen_sha256: str | None
    proposal_title: str
    bidder_name: str | None
    warnings_acknowledged: bool
    source_state_at_freeze: str | None
    sections: list[ExportSection]
    notice: str='COMPLY expresa una declaración del participante; no una certificación automática.'

    @property
    def semantic_sha256(self):return digest(self.model_dump(mode='json'))


def artifact_identity(content,created_at,kind):
    return {'export_contract':EXPORT_CONTRACT,'artifact_type':kind,'version_id':content.version_id,
        'snapshot_id':content.snapshot_id,'snapshot_sha256':content.snapshot_sha256,
        'composition_contract':content.composition_contract,'composition_sha256':content.composition_sha256,
        'semantic_sha256':content.semantic_sha256,'created_at':created_at.isoformat(),'proposal_state':content.proposal_state}
