"""Offline local-UAT backup/restore. No engines, providers or application DB globals."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from app.local_deployment import RuntimeConfig, REPOSITORY


class FileEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    path: str
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    category: Literal['DATABASE', 'ORIGINAL', 'MANIFEST', 'RECEIPT', 'PROCESSING', 'OTHER_DATA']


class BackupManifest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    format: Literal['licitia-local-backup-v1'] = 'licitia-local-backup-v1'
    created_at: datetime
    application_head: str
    application_code_sha256: str
    alembic_revisions: tuple[str, ...]
    postgres_major: Literal[17] = 17
    database: Literal['licitia_uat'] = 'licitia_uat'
    storage_identity: str
    database_identity: str
    files: tuple[FileEntry, ...]
    file_count: int = Field(ge=1)
    validation: Literal['VALIDATED'] = 'VALIDATED'
    orphan_original_count: int = Field(ge=0)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path: Path, value):
    temp = path.with_name('.' + path.name + '.' + uuid4().hex)
    try:
        with temp.open('xb') as stream:
            os.chmod(temp, 0o600)
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path); fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if not relative or '\\' in relative or parts.is_absolute() or str(parts) != relative or any(p in {'.', '..'} for p in parts.parts):
        raise ValueError('RECOVERY_PATH_INVALID')
    path = root.joinpath(*parts.parts)
    if not path.resolve().is_relative_to(root.resolve()) or any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('RECOVERY_PATH_ESCAPE')
    return path


def tree_files(root: Path):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('RECOVERY_DIRECTORY_INVALID')
    result = []
    # rglob includes dotfiles. No hidden-original exclusion.
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('RECOVERY_SPECIAL_FILE_REFUSED')
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise ValueError('RECOVERY_HARDLINK_REFUSED')
            result.append(path)
    return tuple(result)


def application_identity():
    paths = sorted((REPOSITORY/'backend/app').glob('*.py')) + [REPOSITORY/'backend/scripts/licitia_local.py']
    code = hashlib.sha256(canonical([(p.relative_to(REPOSITORY).as_posix(), digest(p)) for p in paths])).hexdigest()
    head = _run(['git','-C',REPOSITORY,'rev-parse','HEAD']).strip()
    return {'application_head':head,'application_code_sha256':code}


def schema_heads():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(REPOSITORY / 'backend/alembic.ini'))
    config.set_main_option('script_location', str(REPOSITORY / 'backend/alembic'))
    return tuple(sorted(ScriptDirectory.from_config(config).get_heads()))


def category(relative):
    if relative == 'database.dump': return 'DATABASE'
    if '/originals/' in relative: return 'ORIGINAL'
    if relative.startswith('storage/provenance/'): return 'MANIFEST'
    if relative.startswith(('storage/ocr-task-receipts-v1/', 'storage/vision-task-receipts-v1/')): return 'RECEIPT'
    if relative.startswith('storage/workspace-processing-v1/'): return 'PROCESSING'
    return 'OTHER_DATA'


def verify_backup(directory: Path) -> BackupManifest:
    directory = directory.absolute()
    files = tree_files(directory)
    try:
        envelope = json.loads((directory / 'manifest.json').read_bytes())
        if set(envelope) != {'payload', 'sha256'} or hashlib.sha256(canonical(envelope['payload'])).hexdigest() != envelope['sha256']:
            raise ValueError('BACKUP_MANIFEST_CHECKSUM_MISMATCH')
        manifest = BackupManifest.model_validate(envelope['payload'])
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError('BACKUP_MANIFEST_INVALID') from exc
    if manifest.alembic_revisions != schema_heads():
        raise ValueError('BACKUP_SCHEMA_INCOMPATIBLE')
    names = [f.path for f in manifest.files]
    if names != sorted(set(names)) or manifest.file_count != len(names) or 'database.dump' not in names or not (directory/'storage').is_dir():
        raise ValueError('BACKUP_INVENTORY_INVALID')
    if {p.relative_to(directory).as_posix() for p in files} != set(names) | {'manifest.json'}:
        raise ValueError('BACKUP_INVENTORY_MISMATCH')
    for entry in manifest.files:
        path = safe_path(directory, entry.path)
        if not (entry.path == 'database.dump' or entry.path.startswith('storage/')) or entry.category != category(entry.path):
            raise ValueError('BACKUP_CATEGORY_INVALID')
        if path.stat().st_size != entry.size or digest(path) != entry.sha256:
            raise ValueError('BACKUP_FILE_CHECKSUM_MISMATCH')
    return manifest


def _run(args, env=None):
    # Never expose argv/DSN/password or document content in raised errors.
    result = subprocess.run([str(a) for a in args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError('RECOVERY_TOOL_FAILED_' + Path(str(args[0])).name)
    return result.stdout.decode()


def tools_ready():
    for tool in ('pg_ctl', 'pg_dump', 'pg_restore', 'psql', 'initdb', 'createdb'):
        if not shutil.which(tool) or not re.search(r'\b17\.', _run([tool, '--version'])):
            raise ValueError('POSTGRES_17_TOOLS_REQUIRED')


@contextmanager
def private_postgres(config: RuntimeConfig, cluster: Path):
    if (cluster/'postmaster.pid').exists():
        raise ValueError('POSTGRES_MUST_BE_STOPPED')
    with tempfile.TemporaryDirectory(prefix='lrpg-', dir='/private/tmp') as directory:
        os.chmod(directory, 0o700)
        env = {k:v for k,v in config.environment().items() if not k.startswith('PG')}
        env.update(PGHOST=directory, PGPORT='5432', PGUSER='licitia', PGPASSWORD=config.password, PGDATABASE='licitia_uat')
        options = shlex.join(['-h', '', '-k', directory, '-p', '5432', '-c', 'unix_socket_permissions=0700'])
        _run(['pg_ctl', '-D', cluster, '-w', '-t', '30', '-l', Path(directory)/'postgres.log', '-o', options, 'start'], env)
        try:
            yield env
        finally:
            _run(['pg_ctl', '-D', cluster, '-w', '-t', '30', '-m', 'fast', 'stop'], env)


def sql_json(env, query):
    return json.loads(_run(['psql', '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-c', query], env))


def validate_database_storage(env, storage: Path):
    files = tree_files(storage)
    revisions = tuple(sorted(sql_json(env, "SELECT coalesce(json_agg(version_num),'[]') FROM alembic_version")))
    if revisions != schema_heads():
        raise ValueError('RECOVERY_SCHEMA_INCOMPATIBLE')
    docs = sql_json(env, "SELECT coalesce(json_agg(d),'[]') FROM (SELECT stored_relative_path,sha256,file_size_bytes FROM tender_documents UNION ALL SELECT stored_relative_path,sha256,file_size_bytes FROM company_documents) d")
    referenced = set()
    for doc in docs:
        path = safe_path(storage, doc['stored_relative_path'])
        if not path.is_file() or path.stat().st_size != doc['file_size_bytes'] or digest(path) != doc['sha256']:
            raise ValueError('RECOVERY_ORIGINAL_MISSING_OR_CHANGED')
        referenced.add(path)
    locators = sql_json(env, "SELECT coalesce(json_agg(source_locator),'[]') FROM (SELECT source_locator FROM tender_scope_details UNION SELECT source_locator FROM tender_scope_quantities UNION SELECT source_locator FROM tender_scope_attributes) q")
    for locator in locators:
        if locator and 'se:' in locator:
            from app.structured_evidence_storage import digest_from_locator, canonical_bytes
            from app.structured_evidence import StructuredEvidenceManifest
            sha = digest_from_locator(locator)
            path = safe_path(storage, 'provenance/structured-evidence-v1/' + sha + '.json')
            if not path.is_file() or digest(path) != sha:
                raise ValueError('RECOVERY_MANIFEST_MISSING_OR_CHANGED')
            if canonical_bytes(StructuredEvidenceManifest.model_validate_json(path.read_bytes())) != path.read_bytes():
                raise ValueError('RECOVERY_MANIFEST_INVALID')
    database_identity = hashlib.sha256(canonical(sql_json(env, "SELECT json_build_object('database',current_database(),'cluster',(SELECT system_identifier::text FROM pg_control_system()))"))).hexdigest()
    return {'database_identity':database_identity, 'alembic_revisions': revisions, 'orphan_original_count': sum('/originals/' in p.as_posix() and p not in referenced for p in files)}


def require_stopped(config, *, allow_journal=False):
    root = config.directory
    if root.is_symlink() or not root.is_dir() or (root/'running.json').exists() or (root/'postgres/postmaster.pid').exists():
        raise ValueError('STOP_INSTANCE_BEFORE_RECOVERY')
    if not allow_journal and (root/'restore-journal.json').exists():
        raise ValueError('PENDING_RESTORE_RECOVERY_REQUIRED')
    for name in ('data', 'postgres'):
        if (root/name).is_symlink(): raise ValueError('RECOVERY_DESTINATION_SYMLINK')
    for port in (config.api_port, config.web_port, config.pg_port):
        with socket.socket() as sock:
            try: sock.bind(('127.0.0.1', port))
            except OSError as exc: raise ValueError('STOP_LISTENERS_BEFORE_RECOVERY') from exc
    data = root/'data'
    if data.is_dir():
        for path in tree_files(data):
            if path.suffix == '.lock':
                with path.open('rb') as lock:
                    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError as exc: raise ValueError('PROCESSING_ACTIVE_NO_RECOVERY') from exc


def backup(config: RuntimeConfig, destination: Path):
    require_stopped(config); tools_ready()
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink() or destination.resolve().is_relative_to(config.directory) or config.directory.is_relative_to(destination.resolve()):
        raise ValueError('NEW_BACKUP_OUTSIDE_RUNTIME_REQUIRED')
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError('BACKUP_PARENT_INVALID')
    cluster = config.directory/'postgres'
    if (cluster/'PG_VERSION').read_text().strip() != '17': raise ValueError('POSTGRES_17_REQUIRED')
    tree_files(cluster)
    stage = Path(tempfile.mkdtemp(prefix='.licitia-backup-', dir=destination.parent))
    try:
        # Both source resources are offline under the canonical launcher lock.
        shutil.copytree(config.directory/'data', stage/'storage')
        temporary = Path(tempfile.mkdtemp(prefix='.backup-db-', dir=config.directory))
        clone = temporary/'postgres'
        try:
            shutil.copytree(cluster, clone)
            with private_postgres(config, clone) as env:
                audit = validate_database_storage(env, stage/'storage')
                _run(['pg_dump', '-Fc', '--no-owner', '--no-acl', '-f', stage/'database.dump', 'licitia_uat'], env)
        finally:
            if not (clone/'postmaster.pid').exists(): shutil.rmtree(temporary)
        entries = tuple(FileEntry(path=p.relative_to(stage).as_posix(), size=p.stat().st_size, sha256=digest(p), category=category(p.relative_to(stage).as_posix())) for p in tree_files(stage))
        manifest = BackupManifest(created_at=datetime.now(timezone.utc), **application_identity(),
            storage_identity=hashlib.sha256(str(config.directory/'data').encode()).hexdigest(),
            files=entries, file_count=len(entries), **audit)
        payload = manifest.model_dump(mode='json')
        atomic_json(stage/'manifest.json', {'payload':payload, 'sha256':hashlib.sha256(canonical(payload)).hexdigest()})
        for path in tree_files(stage):
            os.chmod(path, 0o600)
            with path.open('rb') as stream: os.fsync(stream.fileno())
        for path in stage.rglob('*'):
            if path.is_dir(): os.chmod(path, 0o700)
        verify_backup(stage)
        stage.rename(destination); fsync_dir(destination.parent)
        return {'status':'VERIFIED', 'file_count':len(entries), 'backup':str(destination), **audit}
    finally:
        if stage.exists(): shutil.rmtree(stage)


def flush_tree(root: Path):
    for path in tree_files(root):
        with path.open('rb') as stream: os.fsync(stream.fileno())
    for path in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
        fsync_dir(path)
    fsync_dir(root)


def _journal(config):
    path = config.directory/'restore-journal.json'
    if path.is_symlink(): raise ValueError('RECOVERY_JOURNAL_SYMLINK')
    return path


def recovery_status(config):
    path = _journal(config)
    if not path.exists(): return {'status':'NO_PENDING_RESTORE'}
    record = json.loads(path.read_bytes())
    if set(record) != {'stage', 'had', 'phase'} or not re.fullmatch(r'\.restore-[0-9a-f]{32}', record['stage']) or record['phase'] not in {'SWAPPING','COMMITTED'} or set(record['had']) != {'postgres','data'} or any(type(v) is not bool for v in record['had'].values()):
        raise ValueError('RECOVERY_JOURNAL_INVALID')
    return {'status':'PENDING_RESTORE', **record}


def recover_restore(config):
    require_stopped(config, allow_journal=True)
    record = recovery_status(config)
    if record['status'] != 'PENDING_RESTORE': return record
    stage = safe_path(config.directory, record['stage'])
    if not stage.is_dir(): raise ValueError('RECOVERY_STAGE_MISSING')
    tree_files(stage)  # Reject links/special files before recovery renames.
    if record['phase'] == 'COMMITTED':
        if not all((config.directory/name).is_dir() for name in ('postgres','data')):
            raise ValueError('RECOVERY_COMMITTED_PAIR_MISSING')
    else:
        for name in ('data','postgres'):
            current = config.directory/name; prior = stage/'prior'/name; candidate = stage/'candidate'/name
            if prior.exists():
                if current.exists():
                    (stage/'failed').mkdir(exist_ok=True)
                    current.rename(stage/'failed'/name)
                prior.rename(current)
            elif not record['had'][name] and not candidate.exists() and current.exists():
                current.rename(candidate)
        fsync_dir(config.directory)
    _journal(config).unlink(); fsync_dir(config.directory)
    return {'status':'COMMITTED' if record['phase']=='COMMITTED' else 'ROLLED_BACK', 'retained':str(stage)}


def swap_candidate(config, stage):
    record = {'stage':stage.name, 'had':{name:(config.directory/name).exists() for name in ('postgres','data')}, 'phase':'SWAPPING'}
    (stage/'prior').mkdir()
    atomic_json(_journal(config), record)
    try:
        for name in ('postgres','data'):
            if record['had'][name]:
                os.replace(config.directory/name, stage/'prior'/name)
                fsync_dir(stage/'prior'); fsync_dir(config.directory)
            os.replace(stage/'candidate'/name, config.directory/name)
            fsync_dir(config.directory); fsync_dir(stage/'candidate')
        atomic_json(_journal(config), {**record, 'phase':'COMMITTED'})
    except Exception:
        _recover_restore(config)
        raise
    return _recover_restore(config)


def copy_verified_backup(source: Path, destination: Path, expected: BackupManifest):
    shutil.copytree(source, destination)
    snapshot = verify_backup(destination)
    if snapshot != expected:
        raise ValueError('BACKUP_CHANGED_DURING_COPY')
    return destination


def restore(config: RuntimeConfig, source: Path):
    manifest = verify_backup(source)  # Validate completely before destination mutation.
    require_stopped(config); tools_ready()
    if source.resolve().is_relative_to(config.directory) or config.directory.is_relative_to(source.resolve()):
        raise ValueError('BACKUP_OUTSIDE_RUNTIME_REQUIRED')
    stage = config.directory/('.restore-' + uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        frozen_source = copy_verified_backup(source, stage/'backup', manifest)
        candidate = stage/'candidate'; candidate.mkdir(mode=0o700)
        shutil.copytree(frozen_source/'storage', candidate/'data')
        cluster = candidate/'postgres'
        with tempfile.NamedTemporaryFile(mode='w', dir=stage) as secret:
            secret.write(config.password); secret.flush()
            _run(['initdb', '-D', cluster, '-U', 'licitia', '--auth-local=scram-sha-256', '--auth-host=scram-sha-256', '--pwfile', secret.name, '--encoding=UTF8', '--locale=C'])
        with private_postgres(config, cluster) as env:
            _run(['createdb', 'licitia_uat'], env)
            _run(['pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-acl', '-d', 'licitia_uat', frozen_source/'database.dump'], env)
            audit = validate_database_storage(env, candidate/'data')
            if audit['alembic_revisions'] != manifest.alembic_revisions: raise ValueError('RESTORE_SCHEMA_MISMATCH')
        # DB and storage were both built from the same verified private snapshot.
        verify_backup(frozen_source)
        flush_tree(candidate)
        result = swap_candidate(config, stage)
        return {**result, 'status':'RESTORED', 'alembic_revisions':manifest.alembic_revisions}
    except Exception:
        # Never delete retained prior data or a pending interruption journal.
        if not _journal(config).exists() and not (stage/'prior').exists() and not (stage/'candidate/postgres/postmaster.pid').exists(): shutil.rmtree(stage)
        raise


# All mutating administrator entry points share the launcher's lifetime lock.
_recover_restore = recover_restore

def _exclusive(function):
    from functools import wraps
    @wraps(function)
    def guarded(config, *args, **kwargs):
        path = config.directory/'operation.lock'
        if path.is_symlink(): raise ValueError('RECOVERY_LOCK_SYMLINK')
        with path.open('a+b') as lock:
            os.chmod(path, 0o600)
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc: raise ValueError('INSTANCE_OPERATION_ACTIVE') from exc
            return function(config, *args, **kwargs)
    return guarded

backup = _exclusive(backup)
restore = _exclusive(restore)
recover_restore = _exclusive(_recover_restore)
