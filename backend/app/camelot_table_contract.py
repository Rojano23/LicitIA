"""Physical proposals and source-bound proof; no business domain or authority."""
from __future__ import annotations
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION = 'camelot-native-table-proof-v1'
DETECTOR_VERSION = '2.0.0'
CONFIG = dict(flavor='lattice', engine='combined', backend='pdfium', resolution=300,
              use_fallback=False, parallel=False, suppress_stdout=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


CONFIG_SHA256 = digest(CONFIG)


class PhysicalModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)


class CamelotCell(PhysicalModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    bbox: tuple[float, float, float, float]
    raw_text: str = Field(max_length=500_000)  # Detector/debug only, never a quotation.
    borders: tuple[bool, bool, bool, bool]


class CamelotTableProposal(PhysicalModel):
    detector: Literal['camelot-py'] = 'camelot-py'
    detector_version: Literal['2.0.0'] = DETECTOR_VERSION
    parser: Literal['lattice'] = 'lattice'
    engine: Literal['combined'] = 'combined'
    config_sha256: str
    source_identity_sha256: str
    table_index: int = Field(ge=0)
    page_bbox: tuple[float, float, float, float]
    bbox: tuple[float, float, float, float]
    row_count: int = Field(ge=1, le=4096)
    column_count: int = Field(ge=1, le=4096)
    cells: tuple[CamelotCell, ...] = Field(max_length=4096)
    proposal_sha256: str


class CamelotWordMatch(PhysicalModel):
    fragment_ref: str
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    bbox: tuple[float, float, float, float]


class CamelotCellMatch(PhysicalModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    role: str
    header: bool
    bbox: tuple[float, float, float, float]
    refs: tuple[str, ...]
    words: tuple[CamelotWordMatch, ...] = Field(max_length=20_000)
    status: Literal['NATIVE_PROVEN'] = 'NATIVE_PROVEN'


class CamelotNativeProof(PhysicalModel):
    version: Literal['CAMELOT_NATIVE_TABLE_001'] = 'CAMELOT_NATIVE_TABLE_001'
    policy_version: Literal['camelot-native-table-proof-v1'] = POLICY_VERSION
    engine_version: str  # Native geometry engine, independent of detector version.
    proposal: CamelotTableProposal
    dependencies: tuple[tuple[str, str], ...]
    row_index: int = Field(ge=1)
    cells: tuple[CamelotCellMatch, ...] = Field(max_length=12)
    proof_sha256: str


def bottom_to_top(bbox, height):
    x0, y0, x1, y1 = bbox
    return (x0, height - y1, x1, height - y0)


def check_digest(model, field):
    if getattr(model, field) != digest(model.model_dump(mode='json', exclude={field})):
        raise ValueError('CAMELOT_' + field.upper() + '_MISMATCH')
