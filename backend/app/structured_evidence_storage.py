"""Immutable content-addressed proofs under the canonical managed data root.

Unreferenced manifests can survive DB rollback. No automatic garbage collection
is performed: backups/exports must retain the complete provenance directory.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from app.structured_evidence import StructuredEvidenceManifest

MAX_BYTES = 2 * 1024 * 1024


def canonical_bytes(manifest: StructuredEvidenceManifest) -> bytes:
    return json.dumps(manifest.model_dump(mode='json'),ensure_ascii=False,sort_keys=True,
                      separators=(',', ':'),allow_nan=False).encode('utf-8')


def manifest_root() -> Path:
    from app.main import get_licitia_data_root
    root = get_licitia_data_root().resolve()
    directory = root / 'provenance' / 'structured-evidence-v1'
    if not directory.resolve().is_relative_to(root):
        raise ValueError('STRUCTURED_MANIFEST_ROOT_ESCAPE')
    return directory


def manifest_path(digest: str) -> Path:
    if not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('STRUCTURED_MANIFEST_REFERENCE_INVALID')
    root = manifest_root()
    path = root / (digest + '.json')
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('STRUCTURED_MANIFEST_ROOT_ESCAPE')
    return path


def write_manifest(manifest: StructuredEvidenceManifest) -> str:
    data = canonical_bytes(manifest)
    if len(data) > MAX_BYTES:
        raise ValueError('STRUCTURED_MANIFEST_SIZE_LIMIT')
    digest = hashlib.sha256(data).hexdigest()
    path = manifest_path(digest)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Publish an fsynced complete file atomically without overwriting an existing
    # historical hash, including races between equivalent writers.
    fd, temporary = tempfile.mkstemp(prefix='.proof-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary,path)
            directory_fd = os.open(path.parent,os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError('STRUCTURED_MANIFEST_HASH_MISMATCH')
    finally:
        Path(temporary).unlink(missing_ok=True)
    return digest


def read_manifest(digest: str) -> StructuredEvidenceManifest:
    path = manifest_path(digest)
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('STRUCTURED_MANIFEST_SIZE_LIMIT')
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError('STRUCTURED_MANIFEST_MISSING') from exc
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('STRUCTURED_MANIFEST_HASH_MISMATCH')
    manifest = StructuredEvidenceManifest.model_validate_json(data)
    if canonical_bytes(manifest) != data:
        raise ValueError('STRUCTURED_MANIFEST_NONCANONICAL')
    return manifest


def digest_from_locator(locator: str) -> str:
    refs = [p.removeprefix('se:1:') for p in locator.split('|') if p.startswith('se:1:')]
    if len(refs) != 1 or not re.fullmatch('[0-9a-f]{64}',refs[0]):
        raise ValueError('STRUCTURED_MANIFEST_REFERENCE_INVALID')
    return refs[0]
