"""Read-only Alembic comparison using the previously certified index normalization.

No revision generation, migration execution, repair, or corpus queries.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Literal
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import Field
from sqlalchemy import Index
from app.document_intelligence_validation_metrics import Contract

REVISION='20261013_req_perception_prov_072'


class DriftEvidence(Contract):
    normalization_version: Literal['ALEMBIC_INDEX_DRIFT_001'] = 'ALEMBIC_INDEX_DRIFT_001'
    current_revision: tuple[str,...]
    head_revision: tuple[str,...]
    difference_count: int = Field(ge=0)
    signature_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    operations: dict[str,int]


ACCEPTED_DRIFT=DriftEvidence(current_revision=(REVISION,),head_revision=(REVISION,),difference_count=59,
    signature_sha256='3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7',
    operations={'add_index':55,'remove_index':4})


def _canonical(value):
    # Exact encoding used by the accepted V.4b baseline certification.
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def _safe(value):
    if value is None or isinstance(value,(str,int,float,bool)):return value
    if isinstance(value,(list,tuple)):return [_safe(v) for v in value]
    if isinstance(value,dict):return {str(k):_safe(v) for k,v in value.items()}
    return str(value)


def normalize_differences(differences):
    normalized=[]
    for operation in differences:
        kind,*objects=operation
        if kind not in {'add_index','remove_index'} or len(objects)!=1 or not isinstance(objects[0],Index):
            raise ValueError('UNACCEPTED_SCHEMA_DRIFT_OPERATION')
        index=objects[0]
        normalized.append(dict(operation=kind,name=index.name,table=index.table.name,schema=index.table.schema,
            unique=bool(index.unique),columns=[dict(name=c.name,type=str(c.type),nullable=c.nullable) for c in index.columns],
            expressions=[str(e) for e in index.expressions],options=_safe(dict(index.dialect_kwargs))))
    return sorted(normalized,key=_canonical)


def observe_schema_drift(db):
    if db is None:raise ValueError('DRIFT_VERIFICATION_REQUIRES_DATABASE')
    from app.database import Base
    # Same canonical model registration as alembic/env.py.
    from app.models import Tender  # noqa: F401
    backend=Path(__file__).resolve().parents[1]
    config=Config(str(backend/'alembic.ini'))
    config.set_main_option('script_location',str(backend/'alembic'))
    heads=tuple(sorted(ScriptDirectory.from_config(config).get_heads()))
    # Independent connection cannot flush caller ORM state or change its transaction.
    with db.get_bind().engine.connect() as connection:
        if connection.dialect.name!='postgresql':raise ValueError('POSTGRESQL_DRIFT_VERIFICATION_REQUIRED')
        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
        if connection.exec_driver_sql('SHOW transaction_read_only').scalar_one()!='on':
            raise ValueError('DRIFT_VERIFICATION_MUST_BE_READ_ONLY')
        context=MigrationContext.configure(connection,opts={'compare_type':True})
        current=tuple(sorted(context.get_current_heads()))
        differences=normalize_differences(compare_metadata(context,Base.metadata))
    return DriftEvidence(current_revision=current,head_revision=heads,difference_count=len(differences),
        signature_sha256=hashlib.sha256(_canonical(differences).encode()).hexdigest(),
        operations=dict(Counter(d['operation'] for d in differences)))


def verify_accepted_drift(observed,*,frozen=None):
    observed=DriftEvidence.model_validate(observed)
    if observed!=ACCEPTED_DRIFT:
        raise ValueError('OBSERVED_SCHEMA_DRIFT_MISMATCH')
    if frozen is not None and DriftEvidence.model_validate(frozen)!=observed:
        raise ValueError('FROZEN_SCHEMA_DRIFT_MISMATCH')
    return observed.model_dump(mode='json')
