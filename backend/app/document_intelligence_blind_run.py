"""Blind-run freeze protocol and deterministic capability-aware preparation driver."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Literal

from sqlalchemy.orm import Session

from pydantic import Field, model_validator
from app.document_intelligence_validation_metrics import Contract, METRICS_VERSION, ValidationSnapshot, HumanTruth, ProviderMetric, adjudicate, collect_metrics

REPORT_VERSION = 'DI_BLIND_FIRST_PASS_001'
REVISION = '20261013_req_perception_prov_072'
PROTECTED = ('backend/app/', 'backend/scripts/', 'backend/tests/', 'backend/evals/', 'backend/alembic/', 'backend/pyproject.toml', 'backend/requirements.txt', 'backend/alembic.ini',
    'docs/document-intelligence-06v-protocol.md', 'docs/adr/0010-document-intelligence-capability-routing.md')


def canonical_bytes(value: object) -> bytes:
    if isinstance(value, Contract): value = value.model_dump(mode='json')
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BlindConfig(Contract):
    schema_version: Literal['DI_06V_CONFIG_001'] = 'DI_06V_CONFIG_001'
    code_commit: str = Field(pattern=r'^[0-9a-f]{40}$')
    code_commit_role: Literal['PREFLIGHT_BASELINE'] = 'PREFLIGHT_BASELINE'
    code_file_sha256: dict[str, str]
    alembic_revision: Literal['20261013_req_perception_prov_072'] = REVISION
    metrics_schema: Literal['DI_BLIND_METRICS_001'] = METRICS_VERSION
    report_schema: Literal['DI_BLIND_FIRST_PASS_001'] = REPORT_VERSION
    database_name: Literal['licitia_validation_06v'] = 'licitia_validation_06v'
    runtime: dict[str, object]
    provider_policy: dict[str, object]
    deterministic_configuration: dict[str, object]
    routing_policy_reference: str
    no_tuning_until_first_pass_frozen: Literal[True] = True
    independent_human_truth_after_freeze: Literal[True] = True
    measurement_scope: tuple[str, ...]

    @model_validator(mode='after')
    def safe_policy(self):
        policy = self.provider_policy
        if policy.get('vision_full_page_transcription_automatic') is not False:
            raise ValueError('Vision full-page transcription cannot be a normal fallback')
        if policy.get('source_effect_llm_automatic') is not False:
            raise ValueError('Source Effect LLM automatic discovery is not authorized')
        if (policy.get('execution_policy') != 'AVAILABLE_ONLY' or policy.get('provider_calls_authorized') != 0
                or policy.get('vision_structure_requires_grounding_review_and_explicit_authorization') is not True):
            raise ValueError('Blind baseline requires bounded fail-closed AVAILABLE_ONLY policy')
        if not self.code_file_sha256 or any(not re.fullmatch(r'[0-9a-f]{64}', v) for v in self.code_file_sha256.values()):
            raise ValueError('Frozen code hashes required')
        if any(Path(p).is_absolute() or '..' in Path(p).parts or not p.startswith(PROTECTED) for p in self.code_file_sha256):
            raise ValueError('Code freeze paths must remain within repository code surface')
        return self


def load_config(path: Path) -> BlindConfig:
    return BlindConfig.model_validate_json(path.read_bytes())


def capture_code_identity(root: Path, config_path: Path, *, require_clean: bool = True) -> dict:
    config = load_config(config_path)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=root, text=True).splitlines()
    # Runtime reports may remain untracked; code, tests, manifests and dependencies may not.
    dirty = [line for line in status if line[3:].strip('"').startswith(PROTECTED)]
    mismatches = [p for p, expected in config.code_file_sha256.items()
        if not (root / p).is_file() or sha256((root / p).read_bytes()) != expected]
    tracked_files = subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
    missing = [p for p in tracked_files if p.startswith(PROTECTED) and p != str(config_path.relative_to(root)) and p not in config.code_file_sha256]
    if mismatches or missing:
        raise ValueError(f'Frozen code/config changed: {mismatches + missing}')
    if require_clean and dirty:
        raise ValueError('Dirty protected code state; first blind pass must wait for approved freeze commit')
    return {'commit': commit, 'preflight_baseline_commit': config.code_commit,
        'protected_dirty': bool(dirty), 'protected_status': dirty, 'working_tree_status': status,
        'config_sha256': sha256(config_path.read_bytes()), 'code_manifest_sha256': sha256(canonical_bytes(config.code_file_sha256)),
        'python_executable': sys.executable, 'python_version': platform.python_version(), 'platform': platform.platform(),
        'alembic_revision': config.alembic_revision}


class ExecutionLog(Contract):
    schema_version: Literal['DI_BLIND_EXECUTION_LOG_001'] = 'DI_BLIND_EXECUTION_LOG_001'
    run_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    started_at: datetime
    ended_at: datetime
    providers: tuple[ProviderMetric, ...] = ()
    errors: tuple[str, ...] = ()

    @model_validator(mode='after')
    def events_only(self):
        if any(not p.execution_event or p.calls is None for p in self.providers):
            raise ValueError('Execution ledger requires explicit event call counts')
        return self


class FirstPass(Contract):
    schema_version: Literal['DI_BLIND_FIRST_PASS_001'] = REPORT_VERSION
    run_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    started_at: datetime
    ended_at: datetime
    code_identity: dict[str, object]
    database_identity: dict[str, object]
    snapshot: ValidationSnapshot
    metrics: dict[str, object]
    errors: tuple[str, ...] = ()
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    execution_plan_violations: tuple[str, ...] = ()

    @model_validator(mode='after')
    def validate_run(self):
        if not self.started_at.tzinfo or not self.ended_at.tzinfo or self.ended_at < self.started_at:
            raise ValueError('Ordered timezone-aware execution timestamps required')
        if self.code_identity.get('protected_dirty') is not False:
            raise ValueError('Cannot freeze dirty protected code as blind first pass')
        if self.database_identity.get('revision') != REVISION:
            raise ValueError('Validation DB must be at frozen revision')
        if self.database_identity.get('database') != 'licitia_validation_06v':
            raise ValueError('Dedicated validation database required')
        if self.metrics != collect_metrics(self.snapshot):
            raise ValueError('First-pass metrics must be derived from the preserved snapshot')
        return self


def freeze_first_pass(report: FirstPass, output_root: Path) -> dict:
    """Exclusive run directory + complete marker; never overwrites even after interrupted writes."""
    output_root.mkdir(parents=True, exist_ok=True)
    directory = output_root / report.run_id
    directory.mkdir(exist_ok=False)
    data = canonical_bytes(report)
    digest = sha256(data)
    summary = (f'# Blind first pass {report.run_id}\n\nCode: {report.code_identity["commit"]}\n\n'
        f'First-pass SHA-256: {digest}\n\n'
        f'Tender: {report.snapshot.tender_id}\n\n'
        'Correctness/recall remain unadjudicated. Analysis must use a new report.\n\n'
        '```json\n' + json.dumps(report.metrics, ensure_ascii=False, sort_keys=True, indent=2) + '\n```\n')
    (directory / 'first_pass.json').write_bytes(data)
    (directory / 'first_pass.md').write_text(summary)
    manifest = {'schema_version': REPORT_VERSION, 'run_id': report.run_id, 'first_pass_sha256': digest,
        'summary_sha256': sha256(summary.encode()), 'complete': True,
        'run_status': 'INVALID_PROTOCOL' if report.execution_plan_violations else 'FROZEN'}
    (directory / 'FROZEN.json').write_bytes(canonical_bytes(manifest))
    return manifest


def verify_frozen(directory: Path) -> FirstPass:
    marker = json.loads((directory / 'FROZEN.json').read_bytes())
    raw = (directory / 'first_pass.json').read_bytes()
    if marker.get('complete') is not True or sha256(raw) != marker['first_pass_sha256']:
        raise ValueError('First-pass freeze incomplete or tampered')
    if sha256((directory / 'first_pass.md').read_bytes()) != marker['summary_sha256']:
        raise ValueError('First-pass summary changed')
    return FirstPass.model_validate_json(raw)


def freeze_analysis(directory: Path, truth: HumanTruth, analysis_id: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', analysis_id):
        raise ValueError('Safe independent analysis identity required')
    report = verify_frozen(directory)
    original_hash = sha256((directory / 'first_pass.json').read_bytes())
    result = adjudicate(report.snapshot, truth, original_hash)
    path = directory / f'analysis_{analysis_id}.json'
    data = canonical_bytes({'first_pass_sha256': original_hash, 'analysis_id': analysis_id, **result})
    with path.open('xb') as handle: handle.write(data)
    with (directory / f'analysis_{analysis_id}.sha256').open('x') as handle: handle.write(sha256(data) + '\n')
    return path


def assert_tuning_allowed(directory: Path) -> None:
    verify_frozen(directory)


from app.native_preparation import NativePreparationResult, prepare_tender_documents  # compatibility exports
