"""RC local deployment contracts. No engines, Settings, database globals or inference."""
from __future__ import annotations
from dataclasses import dataclass
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol
from urllib.parse import urlsplit
import urllib.request

REPOSITORY = Path(__file__).resolve().parents[2]


def local_url(value: str) -> str:
    url = urlsplit(value)
    if (url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1'}
            or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment):
        raise ValueError('LOCAL_PROVIDER_ENDPOINT_REQUIRED')
    return value.rstrip('/')


@dataclass(frozen=True)
class RuntimeConfig:
    root: str
    password: str
    pg_port: int = 55432
    api_port: int = 8000
    web_port: int = 5173
    provider_enabled: bool = False
    provider_kind: str = 'OLLAMA'
    provider_url: str = 'http://127.0.0.1:11434'
    model: str = 'qwen3-vl:4b-instruct'
    model_digest: str = 'ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b'
    provider_version: str = '0.23.3'

    def __post_init__(self):
        root = Path(self.root)
        if (not root.is_absolute() or root.resolve() != root or root == Path('/')
                or REPOSITORY.is_relative_to(root) or root.is_relative_to(REPOSITORY)):
            raise ValueError('ABSOLUTE_ISOLATED_RUNTIME_ROOT_REQUIRED')
        if (not isinstance(self.password, str) or len(self.password) < 32
                or not all(c in '0123456789abcdef' for c in self.password)):
            raise ValueError('GENERATED_SECRET_REQUIRED')
        if not isinstance(self.provider_enabled, bool):
            raise ValueError('BOOLEAN_PROVIDER_ENABLED_REQUIRED')
        if self.provider_kind != 'OLLAMA':
            raise ValueError('PROVIDER_IMPLEMENTATION_NOT_AVAILABLE')
        local_url(self.provider_url)
        ports = (self.pg_port, self.api_port, self.web_port)
        if any(type(p) is not int or not 1024 <= p <= 65535 for p in ports) or len(set(ports)) != 3:
            raise ValueError('DISTINCT_UNPRIVILEGED_PORTS_REQUIRED')
        # Frontend currently uses this explicit API endpoint. No silent port remapping.
        if self.api_port != 8000:
            raise ValueError('FRONTEND_REQUIRES_API_PORT_8000')

    @property
    def directory(self):
        return Path(self.root)

    @property
    def python(self):
        return self.directory / 'venv/bin/python'

    @property
    def database_url(self):
        return f'postgresql+psycopg://licitia:{self.password}@127.0.0.1:{self.pg_port}/licitia_uat'

    def environment(self):
        env = dict(os.environ)
        # No ambient developer/blind settings may redirect storage/database/provider.
        for name in list(env):
            if name.startswith('LICITIA_'):
                env.pop(name)
        env.update(DATABASE_URL=self.database_url, LICITIA_DATA_DIR=str(self.directory / 'data'),
                   APP_ENV='limited-uat', APP_HOST='127.0.0.1', APP_PORT=str(self.api_port),
                   FRONTEND_URL=f'http://localhost:{self.web_port}',
                   LICITIA_LOCAL_AI_ENABLED=str(self.provider_enabled).lower(),
                   LICITIA_OLLAMA_BASE_URL=local_url(self.provider_url),
                   LICITIA_OLLAMA_VISION_MODEL=self.model,
                   PYTHONPATH=os.pathsep.join([str(REPOSITORY/'backend/runtime_guard'),str(REPOSITORY/'backend')]),
                   LICITIA_RUNTIME_LOCAL_ONLY='1',
                   LICITIA_NETWORK_AUDIT=str(self.directory/'network.jsonl'),
                   PGPASSWORD=self.password, PGHOST='127.0.0.1', PGPORT=str(self.pg_port), PGUSER='licitia')
        return env


def load_config(path: Path) -> RuntimeConfig:
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError('PRIVATE_CONFIG_0600_REQUIRED')
    try:
        config = RuntimeConfig(**json.loads(path.read_bytes()))
    except TypeError as exc:
        raise ValueError('INVALID_RUNTIME_CONFIG_FIELDS') from exc
    if path.resolve().parent != config.directory:
        raise ValueError('CONFIG_MUST_BELONG_TO_RUNTIME_ROOT')
    return config


def validate_storage(root: Path):
    if root.is_symlink() or not root.is_dir() or not root.stat().st_mode & 0o200:
        raise ValueError('STORAGE_NOT_WRITABLE')
    with tempfile.TemporaryFile(dir=root) as stream:
        stream.write(b'licitia-readiness'); stream.flush()


class ProviderReadiness(Protocol):
    def probe(self, config: RuntimeConfig) -> tuple[str, str]: ...


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('PROVIDER_REDIRECT_REJECTED')


class OllamaReadiness:
    """Read metadata only. Does not install, start or infer."""
    def probe(self, config):
        if not config.provider_enabled:
            return 'DEGRADED', 'LOCAL_PROVIDER_DISABLED'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        def get(path):
            with opener.open(local_url(config.provider_url) + path, timeout=3) as response:
                payload = response.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise ValueError('PROVIDER_METADATA_LIMIT')
            return json.loads(payload)
        try:
            version = get('/api/version')['version']
            models = get('/api/tags')['models']
            match = next((m for m in models if m['name'] == config.model), None)
            if version != config.provider_version:
                return 'DEGRADED', 'PROVIDER_VERSION_MISMATCH'
            if not match or match['digest'] != config.model_digest:
                return 'DEGRADED', 'MODEL_MISSING_OR_DIGEST_MISMATCH'
            return 'READY', 'LOCAL_PROVIDER_METADATA_VERIFIED'
        except (OSError, ValueError, KeyError, TypeError):
            return 'DEGRADED', 'LOCAL_PROVIDER_UNAVAILABLE'


def aggregate(components):
    if any(c['required'] and c['state'] == 'FAILED' for c in components.values()):
        return 'FAILED'
    if any(c['state'] != 'READY' for c in components.values()):
        return 'DEGRADED'
    return 'READY'


def readiness(config: RuntimeConfig, *, runtime=False, provider: ProviderReadiness | None = None):
    components = {}
    def check(name, required, action):
        try:
            detail = action()
            components[name] = dict(state='READY', required=required, detail=detail)
        except Exception as exc:
            # Never serialize connection strings, file content or raw provider responses.
            components[name] = dict(state='FAILED' if required else 'DEGRADED', required=required,
                                    detail=type(exc).__name__)
    check('storage', True, lambda: (validate_storage(config.directory / 'data'), 'WRITABLE')[1])
    def packages():
        expected = {'camelot-py':'2.0.0','PyMuPDF':'1.28.2'}
        for name, version in expected.items():
            if importlib.metadata.version(name) != version:
                raise ValueError('DEPENDENCY_VERSION_MISMATCH')
        for name in ('playa-pdf','pypdfium2','opencv-python-headless','numpy','pandas'):
            importlib.metadata.version(name)
        # Load native libraries as well as inspecting dist metadata.
        import cv2, pypdfium2, pymupdf  # noqa: F401
        return 'CAMELOT_2_LATTICE_COMBINED_DEPENDENCIES'
    check('camelot', True, packages)
    def tesseract():
        result = subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=5,check=True)
        langs = set(result.stdout.splitlines()[1:])
        if not {'spa','eng'} <= langs:
            raise ValueError('TESSDATA_SPA_ENG_REQUIRED')
        return 'spa+eng'
    check('tesseract', True, tesseract)
    def database():
        from sqlalchemy import create_engine, text
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        engine = create_engine(config.database_url,connect_args={'connect_timeout':3})
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                version = connection.execute(text('select version_num from alembic_version')).scalars().all()
                alembic = Config(str(REPOSITORY/'backend/alembic.ini'))
                alembic.set_main_option('script_location',str(REPOSITORY/'backend/alembic'))
                if set(version) != set(ScriptDirectory.from_config(alembic).get_heads()):
                    raise ValueError('MIGRATIONS_REQUIRED')
            return 'ALEMBIC_HEAD'
        finally:
            engine.dispose()
    check('database_migrations', True, database)
    state, detail = (provider or OllamaReadiness()).probe(config)
    components['local_provider'] = dict(state=state,required=False,detail=detail)
    if runtime:
        def http(port,path):
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with opener.open(f'http://127.0.0.1:{port}{path}',timeout=3) as response:
                if response.status != 200:raise ValueError('HTTP_NOT_READY')
            return 'HTTP_READY'
        check('backend', True, lambda: http(config.api_port,'/health'))
        check('frontend', True, lambda: http(config.web_port,'/'))
    return dict(state=aggregate(components),components=components)
