from __future__ import annotations

import argparse
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Company

GOLDEN_COMPANY_NAME = "GOLDEN INDUSTRIAL SERVICES"
GOLDEN_COMPANY_LEGAL_NAME = "GOLDEN INDUSTRIAL SERVICES, S.A. DE C.V."
GOLDEN_COMPANY_TAX_ID = "GIS260101AB1"


def _fixture_dir() -> Path:
    return BACKEND_ROOT / "tests" / "fixtures" / "golden_company_001"


def _find_existing_company_id() -> str | None:
    with SessionLocal() as db:
        row = db.execute(
            select(Company).where(
                Company.tax_id == GOLDEN_COMPANY_TAX_ID,
            )
        ).scalar_one_or_none()
        return row.id if row is not None else None


def _create_company(client: TestClient) -> str:
    response = client.post(
        "/companies",
        json={
            "name": GOLDEN_COMPANY_NAME,
            "legal_name": GOLDEN_COMPANY_LEGAL_NAME,
            "tax_id": GOLDEN_COMPANY_TAX_ID,
        },
    )
    if response.status_code != 201:
        raise RuntimeError(f"Unable to create Golden Company: {response.status_code} {response.text}")
    return response.json()["id"]


def _seed_documents(client: TestClient, company_id: str, fixture_dir: Path) -> tuple[int, int, int]:
    imported_count = 0
    duplicate_count = 0
    conflict_count = 0

    fixtures = sorted(fixture_dir.glob("GC001_*_BASE.txt"))
    if not fixtures:
        raise RuntimeError("No GC001 fixture files were found.")

    for fixture in fixtures:
        payload = fixture.read_bytes()
        response = client.post(
            f"/companies/{company_id}/documents/import",
            files=[("files", (fixture.name, payload, "text/plain"))],
            data={"source_relative_paths": f"fixtures/golden_company_001/{fixture.name}"},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Import failed for {fixture.name}: {response.status_code} {response.text}")

        status = response.json()[0]["status"]
        if status == "IMPORTED":
            imported_count += 1
        elif status == "DUPLICATE":
            duplicate_count += 1
        elif status == "NAME_CONFLICT":
            conflict_count += 1
        else:
            raise RuntimeError(f"Unexpected import status for {fixture.name}: {status}")

    return imported_count, duplicate_count, conflict_count


def _analyze_documents(client: TestClient, company_id: str) -> int:
    listed = client.get(f"/companies/{company_id}/documents")
    if listed.status_code != 200:
        raise RuntimeError(f"Unable to list company documents: {listed.status_code} {listed.text}")
    documents = listed.json()
    analyzed = 0
    for row in documents:
        response = client.post(f"/companies/{company_id}/documents/{row['id']}/analyze-evidence")
        if response.status_code != 200:
            raise RuntimeError(f"Evidence analysis failed for {row['id']}: {response.status_code} {response.text}")
        analyzed += 1
    return analyzed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed/reuse Golden Company 001 acceptance data in the current DATABASE_URL.",
    )
    parser.add_argument(
        "--analyze-evidence",
        action="store_true",
        help="Analyze imported documents into evidence (does not approve evidence, confirm matches, or set compliance decisions).",
    )
    args = parser.parse_args()

    fixture_dir = _fixture_dir()
    if not fixture_dir.exists():
        raise RuntimeError(f"Fixture directory not found: {fixture_dir}")

    client = TestClient(app)
    company_id = _find_existing_company_id()
    created = False
    if company_id is None:
        company_id = _create_company(client)
        created = True

    imported_count, duplicate_count, conflict_count = _seed_documents(client, company_id, fixture_dir)
    analyzed_count = _analyze_documents(client, company_id) if args.analyze_evidence else 0

    print(f"company_id={company_id}")
    print(f"created={created}")
    print(f"imported={imported_count}")
    print(f"duplicates={duplicate_count}")
    print(f"name_conflicts={conflict_count}")
    print(f"analyzed_documents={analyzed_count}")
    print("human_actions=manual_only")


if __name__ == "__main__":
    main()