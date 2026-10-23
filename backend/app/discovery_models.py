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
    internal_state:Mapped[str]=mapped_column(String(16),default='NEW')
    revision:Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('source_id','external_id',name='uq_discovery_identity'),
        CheckConstraint("internal_state IN ('NEW','REVIEW','FOLLOWING','DISCARDED')",name='ck_discovery_internal_state'),
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
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('opportunity_id','external_id',name='uq_discovery_document'),)
