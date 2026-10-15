"""Explicit OCR jobs using canonical local providers and write-once job receipts.

No Vision, no historical AUTO changes, no overwrite of completed/legacy results.
One attempt per source slot: incompatible work is deferred, never silently reused.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import fcntl
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from app.models import DocumentPage, PageOcrResult, TenderDocument
from app.document_perception_planner import PerceptionPlan


class OcrOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str
    status: Literal['OCR_TEXT_EXTRACTED', 'NO_TEXT', 'OCR_FAILED']
    engine: Literal['TESSERACT', 'PADDLEOCR']
    engine_version: str = Field(min_length=1, max_length=64)
    language: str = Field(min_length=1, max_length=64)
    confidence: float | None = Field(default=None, allow_inf_nan=False)
    processing_time_ms: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)

    @field_validator('text', 'engine_version', 'language')
    @classmethod
    def reject_null_characters(cls, value):
        if '\x00' in value:
            raise ValueError('INVALID_OCR_NULL_CHARACTER')
        return value


@dataclass(frozen=True)
class OcrInvocation:
    status: str
    invoked: bool | None
    payload: dict | None = None
    error: str | None = None


@dataclass(frozen=True)
class OcrExecutionResult:
    page_id: str
    status: str
    reason: str
    executed: bool | None = False
    fingerprint: str | None = None
    result_id: str | None = None
    receipt_path: str | None = None


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def receipt_root() -> Path:
    from app.main import get_licitia_data_root
    return get_licitia_data_root() / 'ocr-task-receipts-v1'


def source_slot(page_id: str, engine: str, region_id: str | None) -> str:
    return _hash(_bytes([page_id, engine, region_id]))


def bounded_local_ocr(engine: str, image: bytes, language: str, timeout_seconds: float) -> OcrInvocation:
    """Kill the owned process group on timeout; no abandoned OCR grandchildren."""
    import base64
    command = [sys.executable, '-m', 'app.selective_ocr_executor', '--worker']
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PYTHONDONTWRITEBYTECODE': '1'}
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True, env=env) as process:
        try:
            stdout, stderr = process.communicate(_bytes(dict(engine=engine, image=base64.b64encode(image).decode(), language=language)), timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            return OcrInvocation('FAILED', None, error='OCR_TIMEOUT_EXECUTION_NOT_CONFIRMED')
    if process.returncode:
        return OcrInvocation('FAILED', None, error='OCR_WORKER_FAILED')
    try:
        envelope = json.loads(stdout)
        if (type(envelope.get('invoked')) is not bool or envelope.get('status') not in {'COMPLETED', 'FAILED', 'UNAVAILABLE'}
                or not isinstance(envelope.get('error', ''), str)
                or envelope.get('payload') is not None and not isinstance(envelope['payload'], dict)):
            raise ValueError('MISSING_EXECUTION_ACK')
        return OcrInvocation(envelope['status'], envelope['invoked'], envelope.get('payload'), envelope.get('error'))
    except (ValueError, KeyError, TypeError):
        return OcrInvocation('INVALID_OUTPUT', None, error='INVALID_OCR_WORKER_OUTPUT')


def _verified_path(document):
    from app.main import _resolve_document_file_path, _hash_file
    path = _resolve_document_file_path(document.stored_relative_path)
    with path.open('rb') as original:
        actual_sha256, _ = _hash_file(original)
    if actual_sha256 != document.sha256:
        raise ValueError('ORIGINAL_INTEGRITY_MISMATCH')
    return path


def render_ocr_input(document, page, region):
    import fitz
    path = _verified_path(document)
    with fitz.open(path) as pdf:
        if not 1 <= page.page_number <= pdf.page_count:
            raise ValueError('PAGE_OUTSIDE_PDF')
        clip = fitz.Rect(region.x0, region.y0, region.x1, region.y1) if region else None
        rectangle = (clip & pdf[page.page_number - 1].rect) if clip else pdf[page.page_number - 1].rect
        if rectangle.is_empty or rectangle.width * rectangle.height * 4 > 8_000_000:
            raise ValueError('OCR_RENDER_PIXEL_BUDGET_EXCEEDED')
        image = pdf[page.page_number - 1].get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip).tobytes('png')
    _verified_path(document)
    return image


def execute_planned_ocr(db, plan: PerceptionPlan, *, engine: str, engine_version: str,
                        language: str = 'es+en', timeout_seconds: float = 30,
                        invoke=bounded_local_ocr, render=render_ocr_input) -> OcrExecutionResult:
    def outcome(status, reason, **kwargs):
        return OcrExecutionResult(plan.page_id, status, reason, **kwargs)
    if not plan.ocr_eligible:
        return outcome('SKIPPED', plan.reason)
    if plan.execution_policy == 'AVAILABLE_ONLY':
        return outcome('DEFERRED', 'AVAILABLE_ONLY_NO_ACQUISITION')
    if plan.execution_policy not in {'ALLOW_OCR', 'AUTO'}:
        raise ValueError('UNSUPPORTED_EXECUTION_POLICY')
    if engine not in {'TESSERACT', 'PADDLEOCR'} or engine_version.strip().lower() in {'', 'unknown', 'unavailable'} or len(engine_version) > 64 or not 0 < timeout_seconds <= 60:
        raise ValueError('INVALID_EXPLICIT_OCR_CONFIGURATION')
    page = db.get(DocumentPage, plan.page_id)
    if page is None:
        raise ValueError('PAGE_MISSING')
    document = db.get(TenderDocument, page.document_id)
    from app.main import _is_pdf_document
    if not _is_pdf_document(document):
        return outcome('UNAVAILABLE', 'UNSUPPORTED_NATIVE_CAPABILITY')
    from app.document_perception_planner import plan_document_ocr_tasks
    fresh = plan_document_ocr_tasks(db, tender_id=document.tender_id, document_id=document.id,
        requests={page.id: (plan.request,)}, execution_policy=plan.execution_policy)[0]
    if plan != fresh:
        return outcome('DEFERRED', 'STALE_OR_UNBOUND_PERCEPTION_PLAN')
    region = next((r for r in page.regions if r.id == plan.request.region_id), None)
    if page.text.strip() and region is None and any(r.region_type == 'IMAGE' for r in page.regions):
        return outcome('DEFERRED', 'REGION_SELECTION_REQUIRED_FOR_MIXED_PAGE')
    if plan.request.region_id and (region is None or region.region_type != 'IMAGE'):
        raise ValueError('REGION_OUTSIDE_PAGE')
    from app.ocr import TesseractOCRProvider, PaddleOCRProvider
    provider_class = TesseractOCRProvider if engine == 'TESSERACT' else PaddleOCRProvider
    language = provider_class._map_language_profile(language)
    if not language or len(language) > 64:
        raise ValueError('INVALID_OCR_LANGUAGE')
    scope = 'IMAGE_REGION' if region else 'FULL_PAGE'
    import fitz
    identity = dict(renderer_version=fitz.VersionBind, version='selective-ocr-v1', task='OCR_TRANSCRIPTION', document_id=document.id,
        revision=document.revision_number, original_sha256=document.sha256, page_id=page.id,
        page_number=page.page_number, engine=engine, engine_version=engine_version, language=language,
        scope=scope, region_id=region.id if region else None,
        coordinates=[region.x0, region.y0, region.x1, region.y1] if region else None, zoom=2)
    # File locking avoids concurrent duplicate acquisition, before any provider call.
    directory = receipt_root(); directory.mkdir(parents=True, exist_ok=True)
    slot = source_slot(page.id, engine, identity['region_id'])
    path = directory / (slot + '.json')
    with (directory / (slot + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = db.scalars(select(PageOcrResult).where(PageOcrResult.document_page_id == page.id,
            PageOcrResult.engine == engine, PageOcrResult.scope == scope,
            PageOcrResult.region_id == identity['region_id'])).all()
        if path.exists():
            try:
                receipt = json.loads(path.read_text())
                if receipt['fingerprint'] != _hash(_bytes({**receipt['identity'], 'image_sha256': receipt['image_sha256']})):
                    raise ValueError('INVALID_RECEIPT_FINGERPRINT')
            except (ValueError, KeyError, TypeError):
                return outcome('DEFERRED', 'INVALID_OCR_RECEIPT')
            if receipt['identity'] != identity:
                return outcome('DEFERRED', 'INCOMPATIBLE_GENERATION_REQUIRES_REVIEW')
            row = db.get(PageOcrResult, receipt['result_id'])
            if (row is None or len(rows) != 1 or row not in rows or _hash(row.text.encode()) != receipt['text_sha256']
                    or row.status != receipt['status'] or row.engine_version != engine_version or row.language != language):
                return outcome('DEFERRED', 'RECEIPT_RESULT_MISMATCH')
            # Verification of the original does not require rendering or a probe.
            _verified_path(document)
            return outcome('COMPLETED' if row.status == 'OCR_TEXT_EXTRACTED' else 'FAILED',
                'REUSED_EQUIVALENT_COMPLETED' if row.status == 'OCR_TEXT_EXTRACTED' else 'RETRY_EXHAUSTED',
                fingerprint=receipt['fingerprint'], result_id=row.id, receipt_path=str(path))
        if rows:
            return outcome('DEFERRED', 'EXISTING_UNVERIFIED_GENERATION_NO_OVERWRITE')
        try:
            image = render(document, page, region)
            if not isinstance(image, bytes) or not image or len(image) > 8_388_608:
                raise ValueError('EMPTY_RENDER')
        except Exception as exc:
            return outcome('RENDER_FAILED', str(exc))
        fingerprint = _hash(_bytes({**identity, 'image_sha256': _hash(image)}))
        try:
            invocation = invoke(engine, image, language, timeout_seconds)
        except Exception as exc:
            invocation = OcrInvocation('FAILED', None, error=f'OCR_EXECUTION_ERROR:{exc}')
        output = None
        error = invocation.error
        status = invocation.status
        if status == 'UNAVAILABLE':
            return outcome('UNAVAILABLE', error or 'OCR_ENGINE_UNAVAILABLE', executed=invocation.invoked)
        try:
            if status == 'COMPLETED':
                output = OcrOutput.model_validate(invocation.payload)
                if output.engine != engine or output.engine_version != engine_version or output.language != language:
                    raise ValueError('OCR_OUTPUT_CONFIGURATION_MISMATCH')
                if output.status != 'OCR_TEXT_EXTRACTED' or not output.text.strip():
                    status, error = 'FAILED', 'OCR_NO_USABLE_TEXT'
            else:
                status = 'FAILED'
        except ValueError as exc:
            status, error = 'INVALID_OUTPUT', str(exc)
        _verified_path(document)
        row = PageOcrResult(document_page_id=page.id, engine=engine, engine_version=engine_version,
            language=language, scope=scope, region_id=identity['region_id'],
            text=output.text if status == 'COMPLETED' else '',
            status='OCR_TEXT_EXTRACTED' if status == 'COMPLETED' else 'OCR_FAILED',
            confidence=output.confidence if output and status == 'COMPLETED' else None,
            processing_time_ms=output.processing_time_ms if output else None,
            warnings='; '.join(output.warnings) if output and status == 'COMPLETED' else error or 'OCR_FAILED')
        db.add(row); db.flush()
        from app.content_normalization import process_document_normalization
        db.expire(page, ['ocr_results'])
        process_document_normalization(db, document, ocr_result_ids=frozenset({row.id}))
        receipt = dict(identity=identity, fingerprint=fingerprint, image_sha256=_hash(image),
            result_id=row.id, text_sha256=_hash(row.text.encode()), status=row.status, attempts=1)
        # Write once; a rolled-back DB transaction causes a mismatch, never false reuse.
        with path.open('x') as file:
            json.dump(receipt, file, sort_keys=True)
        return outcome(status, error or 'OCR_ACQUIRED_REVIEW_REQUIRED', executed=invocation.invoked,
                       fingerprint=fingerprint, result_id=row.id, receipt_path=str(path))


def _worker():
    import base64
    import socket
    # OCR is local-only. Missing assets must fail, never download implicitly.
    def deny_network(*args, **kwargs):
        raise RuntimeError('OCR_WORKER_NETWORK_DISABLED')
    socket.create_connection = deny_network
    socket.getaddrinfo = deny_network
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    from app.ocr import TesseractOCRProvider, PaddleOCRProvider
    request = json.loads(sys.stdin.buffer.read())
    cls = {'TESSERACT': TesseractOCRProvider, 'PADDLEOCR': PaddleOCRProvider}[request['engine']]
    provider = cls()
    if provider.status != 'AVAILABLE':
        print(json.dumps(dict(status='UNAVAILABLE', invoked=False, error=provider.status_reason)))
        return
    try:
        result = provider.recognize(base64.b64decode(request['image']), language=request['language'])
        print(json.dumps(dict(status='COMPLETED', invoked=True, payload=result)))
    except Exception as exc:
        print(json.dumps(dict(status='FAILED', invoked=True, error=str(exc))))


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    _worker()
