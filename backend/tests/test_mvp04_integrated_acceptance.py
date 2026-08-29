from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import RequirementReview
from tests.test_requirement_versioning import _create_tender, _import_pdf, _seed_page_and_normalized, _seed_requirement_candidate

client = TestClient(app)


def _run_pipeline(tender_id: str) -> tuple[dict, dict, dict, dict, dict, dict]:
    eval_payload = client.post(f"/tenders/{tender_id}/analyze-evaluation")
    assert eval_payload.status_code == 200, eval_payload.text

    candidates_payload = client.post(f"/tenders/{tender_id}/analyze-requirements")
    assert candidates_payload.status_code == 200, candidates_payload.text

    requirements_payload = client.post(f"/tenders/{tender_id}/normalize-requirements")
    assert requirements_payload.status_code == 200, requirements_payload.text

    semantics_payload = client.post(f"/tenders/{tender_id}/analyze-requirement-semantics")
    assert semantics_payload.status_code == 200, semantics_payload.text

    versioning_post = client.post(f"/tenders/{tender_id}/analyze-requirement-versions")
    assert versioning_post.status_code == 200, versioning_post.text

    matrix_payload = client.get(f"/tenders/{tender_id}/requirement-matrix")
    assert matrix_payload.status_code == 200, matrix_payload.text

    versioning_get = client.get(f"/tenders/{tender_id}/requirement-effective-state")
    assert versioning_get.status_code == 200, versioning_get.text

    return (
        eval_payload.json(),
        candidates_payload.json(),
        requirements_payload.json(),
        semantics_payload.json(),
        versioning_post.json(),
        versioning_get.json(),
        matrix_payload.json(),
    )


def test_mvp04_pipeline_idempotent_and_review_free_without_human_patch() -> None:
    tender_id = _create_tender("MVP04 integrated idempotency")
    bases_id = _import_pdf(tender_id, "bases-integrated.pdf")

    p1, n1 = _seed_page_and_normalized(
        bases_id,
        1,
        "El participante debera presentar constancia fiscal vigente y firmar su propuesta en idioma espanol.",
    )
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=bases_id,
        page_id=p1,
        normalized_content_id=n1,
        source_page=1,
        text="El participante debera presentar constancia fiscal vigente.",
    )
    p2, n2 = _seed_page_and_normalized(
        bases_id,
        2,
        "Tratandose de propuesta conjunta, cada integrante del consorcio debera presentar su constancia fiscal.",
    )
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=bases_id,
        page_id=p2,
        normalized_content_id=n2,
        source_page=2,
        text="Tratandose de propuesta conjunta, cada integrante del consorcio debera presentar su constancia fiscal.",
    )

    run1 = _run_pipeline(tender_id)
    run2 = _run_pipeline(tender_id)

    versioning_post_1 = run1[4]
    versioning_get_1 = run1[5]
    matrix_1 = run1[6]
    versioning_post_2 = run2[4]
    versioning_get_2 = run2[5]
    matrix_2 = run2[6]

    assert versioning_post_1["summary"] == versioning_post_2["summary"]
    assert versioning_get_1["summary"] == versioning_get_2["summary"]
    assert matrix_1["summary"] == matrix_2["summary"]

    post_status_2 = {row["requirement_id"]: row["effective_status"] for row in versioning_post_2["requirements"]}
    get_status_2 = {row["requirement_id"]: row["effective_status"] for row in versioning_get_2["requirements"]}
    matrix_status_2 = {row["requirement_id"]: row["effective_status"] for row in matrix_2["requirements"]}

    assert post_status_2 == get_status_2
    assert get_status_2 == matrix_status_2

    with SessionLocal() as db:
        review_count = db.query(RequirementReview).filter(RequirementReview.tender_id == tender_id).count()
    assert review_count == 0


def test_mvp04_matrix_composes_requirement_and_semantics_without_compliance_fields() -> None:
    tender_id = _create_tender("MVP04 integrated composition")
    doc_id = _import_pdf(tender_id, "bases-composition.pdf")

    p1, n1 = _seed_page_and_normalized(
        doc_id,
        1,
        "El participante debera presentar formato DA-2 debidamente firmado en PDF y editable.",
    )
    _seed_requirement_candidate(
        tender_id=tender_id,
        document_id=doc_id,
        page_id=p1,
        normalized_content_id=n1,
        source_page=1,
        text="El participante debera presentar formato DA-2 debidamente firmado en PDF y editable.",
    )

    _run_pipeline(tender_id)
    semantics = client.get(f"/tenders/{tender_id}/requirement-semantics")
    matrix = client.get(f"/tenders/{tender_id}/requirement-matrix")

    assert semantics.status_code == 200, semantics.text
    assert matrix.status_code == 200, matrix.text

    sem_rows = {row["requirement_id"]: row for row in semantics.json()["requirements"]}

    for row in matrix.json()["requirements"]:
        sem = sem_rows[row["requirement_id"]]
        assert row["applicability"] == sem["applicability"]
        assert row["condition_text"] == sem["condition_text"]
        assert row["interpretation_status"] == sem["interpretation_status"]
        assert row["evidence_mode"] == sem["evidence_mode"]
        serialized = str(row).lower()
        assert "compliance" not in serialized
        assert "cumple" not in serialized
