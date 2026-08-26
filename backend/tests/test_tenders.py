from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_tender() -> None:
    payload = {
        "title": "Tender Alpha",
        "institution_profile": "PEMEX",
        "external_reference": "REF-001",
    }
    created = client.post("/tenders", json=payload)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["title"] == "Tender Alpha"
    assert data["institution_profile"] == "PEMEX"
    assert data["external_reference"] == "REF-001"

    fetched = client.get(f"/tenders/{data['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Tender Alpha"


def test_list_tenders() -> None:
    created = client.post("/tenders", json={"title": "Tender Beta"})
    assert created.status_code == 201, created.text

    response = client.get("/tenders")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["title"] == "Tender Beta" for item in payload)
