"""Live-test schema expectation, separate from frozen replay/report identities."""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory


def current_head():
    backend=Path(__file__).resolve().parents[1]
    config=Config(str(backend/'alembic.ini'))
    config.set_main_option('script_location',str(backend/'alembic'))
    heads=ScriptDirectory.from_config(config).get_heads()
    assert len(heads)==1,'Tests require one canonical schema head'
    return heads[0]
