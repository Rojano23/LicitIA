"""Discovery persistence, deliberately without Tender foreign keys."""
from datetime import datetime,date
from sqlalchemy import String,Boolean,Integer,JSON,DateTime,Date,ForeignKey,UniqueConstraint,CheckConstraint,Index
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base

class DiscoverySource(Base):
    __tablename__='discovery_sources'
    id:Mapped[str]=mapped_column(String(32),primary_key=True)
    name:Mapped[str]=mapped_column(String(160))
    base_url:Mapped[str]=mapped_column(String(500))
    adapter_version:Mapped[str]=mapped_column(String(40))
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)
    configuration:Mapped[dict]=mapped_column(JSON,default=dict)
    last_scan_state:Mapped[str|None]=mapped_column(String(16))
    last_successful_scan:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    last_error:Mapped[str|None]=mapped_column(String(500))

class DiscoveryProfile(Base):
    __tablename__='discovery_profiles'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    name:Mapped[str]=mapped_column(String(160))
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    revision:Mapped[int]=mapped_column(Integer,default=1)
    configuration:Mapped[dict]=mapped_column(JSON)
    __table_args__=(CheckConstraint('revision > 0',name='ck_discovery_profile_revision'),)

class DiscoveryOpportunity(Base):
    __tablename__='discovery_opportunities'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    source_id:Mapped[str]=mapped_column(ForeignKey('discovery_sources.id',ondelete='RESTRICT'))
    external_id:Mapped[str]=mapped_column(String(200))
    business_area:Mapped[str]=mapped_column(String(120))
    published_date:Mapped[date|None]=mapped_column(Date)
    representation:Mapped[dict]=mapped_column(JSON)
    fingerprint:Mapped[str]=mapped_column(String(64))
    previous_fingerprint:Mapped[str|None]=mapped_column(String(64))
    first_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    last_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    last_changed:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    watching:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    last_scan_id:Mapped[str|None]=mapped_column(ForeignKey('discovery_scan_runs.id',ondelete='SET NULL'),index=True)
    internal_state:Mapped[str]=mapped_column(String(16),default='NEW')
    revision:Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('source_id','external_id',name='uq_discovery_identity'),
        CheckConstraint("internal_state IN ('NEW','REVIEW','FOLLOWING','DISCARDED','IMPORTED')",name='ck_discovery_internal_state'),
        Index('ix_discovery_source_date','source_id','published_date'),Index('ix_discovery_workflow','internal_state'))

class DiscoveryScanRun(Base):
    __tablename__='discovery_scan_runs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    source_id:Mapped[str]=mapped_column(ForeignKey('discovery_sources.id',ondelete='RESTRICT'))
    request_id:Mapped[str]=mapped_column(String(36))
    request_sha256:Mapped[str]=mapped_column(String(64))
    query:Mapped[dict]=mapped_column(JSON)
    adapter_version:Mapped[str]=mapped_column(String(40))
    status:Mapped[str]=mapped_column(String(16))
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    metrics:Mapped[dict]=mapped_column(JSON,default=dict)
    __table_args__=(UniqueConstraint('source_id','request_id',name='uq_discovery_scan_request'),
        CheckConstraint("status IN ('RUNNING','SUCCESS','PARTIAL','FAILED')",name='ck_discovery_scan_state'),
        Index('ix_discovery_scan_source_time','source_id','started_at'))

class DiscoverySourceDocument(Base):
    __tablename__='discovery_source_documents'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    opportunity_id:Mapped[str]=mapped_column(ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),index=True)
    external_id:Mapped[str]=mapped_column(String(500))
    name:Mapped[str]=mapped_column(String(500))
    public_url:Mapped[str]=mapped_column(String(2000))
    fingerprint:Mapped[str]=mapped_column(String(64))
    active:Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
    last_scan_id:Mapped[str|None]=mapped_column(ForeignKey('discovery_scan_runs.id',ondelete='SET NULL'),index=True)
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('opportunity_id','external_id',name='uq_discovery_document'),)

class DiscoveryChange(Base):
    __tablename__='discovery_changes'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    event_key:Mapped[str]=mapped_column(String(64),unique=True)
    opportunity_id:Mapped[str]=mapped_column(ForeignKey('discovery_opportunities.id',ondelete='CASCADE'))
    source_id:Mapped[str]=mapped_column(ForeignKey('discovery_sources.id',ondelete='RESTRICT'))
    scan_run_id:Mapped[str|None]=mapped_column(ForeignKey('discovery_scan_runs.id',ondelete='SET NULL'))
    category:Mapped[str]=mapped_column(String(40))
    origin:Mapped[str]=mapped_column(String(10))
    detected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    previous_fingerprint:Mapped[str|None]=mapped_column(String(64))
    current_fingerprint:Mapped[str|None]=mapped_column(String(64))
    changed_fields:Mapped[dict]=mapped_column(JSON)
    summary:Mapped[str]=mapped_column(String(2000))
    actor:Mapped[str|None]=mapped_column(String(160))
    acknowledged_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(Index('ix_discovery_change_parent_time','opportunity_id','detected_at'),Index('ix_discovery_change_unread','opportunity_id','acknowledged_at'))

class DiscoveryCoverage(Base):
    __tablename__='discovery_coverage'
    scope_sha:Mapped[str]=mapped_column(String(64),primary_key=True)
    opportunity_id:Mapped[str]=mapped_column(ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),primary_key=True)
    present:Mapped[bool]=mapped_column(Boolean)
    last_scan_id:Mapped[str]=mapped_column(ForeignKey('discovery_scan_runs.id',ondelete='RESTRICT'))

class DiscoveryTenderLink(Base):
    __tablename__='discovery_tender_links'
    opportunity_id:Mapped[str]=mapped_column(ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),primary_key=True)
    tender_id:Mapped[str|None]=mapped_column(ForeignKey('tenders.id',ondelete='SET NULL'),unique=True)
    tender_identity:Mapped[str]=mapped_column(String(36),unique=True)
    context:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class DiscoveryImportReceipt(Base):
    __tablename__='discovery_import_receipts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    opportunity_id:Mapped[str]=mapped_column(ForeignKey('discovery_opportunities.id',ondelete='CASCADE'),index=True)
    source_document_id:Mapped[str]=mapped_column(ForeignKey('discovery_source_documents.id',ondelete='RESTRICT'))
    tender_identity:Mapped[str]=mapped_column(String(36))
    tender_document_id:Mapped[str]=mapped_column(String(36))
    metadata_fingerprint:Mapped[str]=mapped_column(String(64))
    sha256:Mapped[str]=mapped_column(String(64))
    source_url:Mapped[str]=mapped_column(String(2000))
    source_name:Mapped[str]=mapped_column(String(500))
    downloaded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    result:Mapped[str]=mapped_column(String(32))
    __table_args__=(UniqueConstraint('opportunity_id','source_document_id','metadata_fingerprint','sha256',name='uq_discovery_import_receipt'),)
