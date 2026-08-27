import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DB_NAME = "licitia_test"
TEST_DB_URL = "postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test"


def _ensure_test_database() -> None:
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["LICITIA_DATA_DIR"] = str(BACKEND_ROOT / ".licitia-data-test")

    database_check = subprocess.run(
        ["psql", "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{TEST_DB_NAME}'"],
        capture_output=True,
        text=True,
        check=False,
    )
    if database_check.returncode == 0 and "1" not in database_check.stdout.strip():
        subprocess.run(["createdb", TEST_DB_NAME], check=True, capture_output=True, text=True)


_ensure_test_database()


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT)},
        check=True,
        capture_output=True,
        text=True,
    )
    yield
