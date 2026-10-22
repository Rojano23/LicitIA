"""Local expiring export/preview contexts, no workbook retention or Tender originals."""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from fastapi import HTTPException

MAX_CONTEXT_BYTES = 16 * 1024 * 1024
MAX_CONTEXTS = 256
TTL = timedelta(days=7)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def directory():
    from app.main import get_licitia_data_root
    root = get_licitia_data_root().resolve()
    path = root / 'commercial-roundtrip-v1'
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_STORAGE_UNSAFE')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def _path(kind, identity):
    if kind not in {'export', 'stage'}:
        raise ValueError('Unsupported context kind')
    try:
        normalized = str(UUID(str(identity)))
    except ValueError as exc:
        raise HTTPException(422, 'INVALID_CONTEXT_ID') from exc
    return directory() / f'{kind}_{normalized}.json'


def _read(path):
    if path.is_symlink():
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_STORAGE_UNSAFE')
    try:
        with path.open('rb') as handle:
            raw = handle.read(MAX_CONTEXT_BYTES + 1)
        if len(raw) > MAX_CONTEXT_BYTES:
            raise ValueError('oversized context')
        envelope = json.loads(raw)
        payload = envelope['payload']
        if hashlib.sha256(canonical(payload)).hexdigest() != envelope['sha256']:
            raise ValueError('context hash')
        expires = datetime.fromisoformat(payload['expires_at'])
        if expires.tzinfo is None:
            raise ValueError('timezone required')
    except FileNotFoundError as exc:
        raise HTTPException(404, 'COMMERCIAL_CONTEXT_NOT_FOUND') from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_CORRUPT') from exc
    return payload, expires


def save(kind, identity, payload):
    path = _path(kind, identity)
    now = datetime.now(timezone.utc)
    paths = list(directory().glob('*.json'))
    for owned in paths[:MAX_CONTEXTS + 1]:
        if owned.is_symlink():
            raise HTTPException(409, 'COMMERCIAL_CONTEXT_STORAGE_UNSAFE')
        if owned.name.startswith(('stage_', 'export_')):
            try:
                _, expires = _read(owned)
                if expires < now:
                    owned.unlink()
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
    if sum(1 for _ in directory().glob('*.json')) >= MAX_CONTEXTS:
        raise HTTPException(413, 'COMMERCIAL_CONTEXT_CAPACITY_REACHED')
    payload = payload | {'created_at': now.isoformat(), 'expires_at': (now + TTL).isoformat()}
    raw = canonical({'payload': payload, 'sha256': hashlib.sha256(canonical(payload)).hexdigest()})
    if len(raw) > MAX_CONTEXT_BYTES:
        raise HTTPException(413, 'COMMERCIAL_CONTEXT_TOO_LARGE')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
    except FileExistsError as exc:
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_EXISTS') from exc
    return payload


def load(kind, identity, tender_id):
    payload, expires = _read(_path(kind, identity))
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(410, 'COMMERCIAL_CONTEXT_EXPIRED')
    if payload['tender_id'] != tender_id:
        raise HTTPException(409, 'COMMERCIAL_CONTEXT_TENDER_MISMATCH')
    return payload
