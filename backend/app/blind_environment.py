"""Settings-free bootstrap and fail-closed storage identity for blind processes."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[1]
ROOT_VARIABLE = 'LICITIA_BLIND_DATA_ROOT'


def canonical_root(value: str | Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else BACKEND / path).resolve()


def require_root(value: str | Path, *, writable: bool = False) -> Path:
    root = canonical_root(value)
    if root in {canonical_root('.licitia-data'), canonical_root('.licitia-data-test')}:
        raise ValueError('ISOLATED_BLIND_DATA_ROOT_REQUIRED')
    if not root.is_dir():
        raise ValueError('BLIND_DATA_ROOT_MUST_EXIST')
    if writable and (not os.access(root, os.W_OK | os.X_OK) or
                     not root.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)):
        raise ValueError('BLIND_DATA_ROOT_NOT_WRITABLE')
    return root


def establish_environment(*, database_url: str, data_dir: str | Path) -> Path:
    """Call before app imports; a new attempt requires a fresh process, not cache resets."""
    if any(name in sys.modules for name in ('app.config', 'app.database', 'app.main')):
        raise RuntimeError('FRESH_BLIND_BOOTSTRAP_PROCESS_REQUIRED')
    url = urlsplit(database_url)
    if url.hostname not in {'localhost', '127.0.0.1'} or url.path != '/licitia_validation_06v':
        raise ValueError('DEDICATED_LOCAL_VALIDATION_DATABASE_REQUIRED')
    root = require_root(data_dir, writable=True)
    previous = os.environ.get(ROOT_VARIABLE)
    if previous and canonical_root(previous) != root:
        raise ValueError('BLIND_PROCESS_ROOT_ALREADY_BOUND')
    os.environ.update(DATABASE_URL=database_url, LICITIA_DATA_DIR=str(root),
                      LICITIA_BLIND_DATA_ROOT=str(root), LICITIA_LOCAL_AI_ENABLED='false')
    return root


def verify_storage_root(settings_root: str | Path, *, expected: str | None = None,
                        required: bool = False, writable: bool = False) -> Path:
    marker = os.environ.get(ROOT_VARIABLE)
    if not marker:
        if required or expected is not None:
            raise ValueError('BLIND_BOOTSTRAP_REQUIRED')
        return canonical_root(settings_root)
    root = require_root(marker, writable=writable)
    environment = os.environ.get('LICITIA_DATA_DIR')
    if not environment or canonical_root(environment) != root or canonical_root(settings_root) != root:
        raise ValueError('BLIND_RUNTIME_DATA_ROOT_MISMATCH')
    if expected is not None and canonical_root(expected) != root:
        raise ValueError('FROZEN_DATA_ROOT_MISMATCH')
    return root


def storage_identity(*, expected: str | None = None) -> dict:
    from app.config import get_settings
    root = verify_storage_root(get_settings().licitia_data_dir, expected=expected,
                               required=True, writable=True)
    return {'schema_version': 'BLIND_STORAGE_ROOT_001', 'canonical_data_root': str(root)}
