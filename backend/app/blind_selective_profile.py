"""Separate, explicit blind execution profile. Historical BlindConfig is unchanged."""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from app.document_intelligence_validation_metrics import Contract
from app.selective_vision_executor import VisionConfiguration

PROFILE_VERSION = 'DI_BLIND_SELECTIVE_001'
TASK_POLICY_VERSION = 'blind-task-contracts-v1'


class OcrPolicy(Contract):
    engine: Literal['TESSERACT','PADDLEOCR']
    engine_version: str = Field(min_length=1,max_length=64)
    language: Literal['es+en','es','en'] = 'es+en'
    max_calls: int = Field(ge=0,le=10000)  # Required, never inferred from the corpus.
    timeout_seconds: int = Field(default=30,ge=1,le=60)
    zoom: Literal[2] = 2
    max_pixels: Literal[8000000] = 8000000
    max_image_bytes: Literal[8388608] = 8388608

    @model_validator(mode='after')
    def known_engine(self):
        if self.engine_version.strip().lower() in {'','unknown','unavailable'}:
            raise ValueError('Frozen known OCR engine version required')
        return self


class VisionPolicy(Contract):
    provider: Literal['OLLAMA'] = 'OLLAMA'
    model: str = Field(min_length=1,max_length=64)
    model_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    model_manifest: str
    base_url: str = 'http://127.0.0.1:11434'
    max_calls: int = Field(default=4,ge=0,le=4)
    max_tasks: int = Field(default=4,ge=0,le=4)
    max_pages: int = Field(default=4,ge=0,le=4)
    max_attempts: int = Field(default=2,ge=1,le=2)
    timeout_seconds: int = Field(default=60,ge=1,le=60)
    structure_tokens: int = Field(default=600,ge=128,le=600)
    detail_tokens: int = Field(default=1000,ge=256,le=1000)
    internal_json_retry: Literal[0] = 0
    zoom: Literal[2] = 2
    max_pixels: Literal[8000000] = 8000000
    max_image_bytes: Literal[8388608] = 8388608

    def configuration(self):
        return VisionConfiguration(model=self.model,model_revision=self.model_revision,base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,structure_tokens=self.structure_tokens,detail_tokens=self.detail_tokens)

    @model_validator(mode='after')
    def local_endpoint(self):
        self.configuration()
        return self


class SpatialContract(Contract):
    """Frozen task requirement, not a finding inferred from OCR failure."""
    task: Literal['STRUCTURE_SCOPE','DETAIL_TRANSCRIPTION']
    requirement: Literal['IMAGE_LAYOUT_RELATIONSHIP']


class SelectiveProfile(Contract):
    schema_version: Literal['DI_BLIND_SELECTIVE_001'] = PROFILE_VERSION
    profile: Literal['HISTORICAL_SAFE','SELECTIVE_PERCEPTION']
    execution_policy: Literal['AVAILABLE_ONLY','ALLOW_OCR','AUTO'] = 'AVAILABLE_ONLY'
    database_name: Literal['licitia_validation_06v'] = 'licitia_validation_06v'
    alembic_revision: Literal['20261013_req_perception_prov_072'] = '20261013_req_perception_prov_072'
    task_policy_version: Literal['blind-task-contracts-v1'] = TASK_POLICY_VERSION
    ocr: OcrPolicy
    vision: VisionPolicy
    spatial_contracts: tuple[SpatialContract,...] = ()
    source_effect_llm_automatic: Literal[False] = False

    @model_validator(mode='after')
    def policies(self):
        if self.profile=='HISTORICAL_SAFE' and self.execution_policy!='AVAILABLE_ONLY':
            raise ValueError('Historical safe profile permits AVAILABLE_ONLY only')
        if len({c.task for c in self.spatial_contracts})!=len(self.spatial_contracts):
            raise ValueError('Duplicate spatial task contract')
        return self
