from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select
import pytest

from app.config import Settings
from app.database import SessionLocal
from app.main import app
import app.local_vision as local_vision_module
from app.local_vision import OllamaVisionProvider, VisionAnalysisRead, VisionPageImage, VisionPartidaProposalRead, VisionRuntimeRead
from app.models import DocumentPage, NormalizedContent, TenderDocument, TenderItem
import app.tender_items as tender_items_module

client = TestClient(app)


def _create_tender(title: str, external_reference: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": external_reference,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\n1 0 obj\n<< /Title ({filename}) >>\nendobj\n%%EOF\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    assert response.status_code == 200, response.text
    return response.json()[0]["document_id"]


def _seed_page_and_normalized(document_id: str, page_number: int, text: str, *, source_type: str = "NATIVE_PDF") -> tuple[str, str]:
    db = SessionLocal()
    try:
        page = DocumentPage(
            document_id=document_id,
            page_number=page_number,
            text=text,
            char_count=len(text),
            extraction_method="NATIVE_PDF",
            status="TEXT_EXTRACTED",
        )
        db.add(page)
        db.flush()

        document = db.get(TenderDocument, document_id)
        assert document is not None
        document.page_count = max(document.page_count, page_number)
        document.processing_status = "TEXT_EXTRACTION_COMPLETE"

        normalized = NormalizedContent(
            document_page_id=page.id,
            source_type=source_type,
            source_scope="NATIVE_PAGE" if source_type == "NATIVE_PDF" else "OCR_PAGE",
            normalized_text=text,
            char_count=len(text),
            content_sha256=hashlib.sha256(f"{document_id}|{page_number}|{source_type}|{text}".encode("utf-8")).hexdigest(),
        )
        db.add(normalized)
        db.commit()
        return page.id, normalized.id
    finally:
        db.close()


def _update_normalized_text(document_id: str, new_text: str) -> None:
    db = SessionLocal()
    try:
        page_ids = [row[0] for row in db.execute(select(DocumentPage.id).where(DocumentPage.document_id == document_id)).all()]
        for normalized in db.execute(select(NormalizedContent).where(NormalizedContent.document_page_id.in_(page_ids))).scalars().all():
            normalized.normalized_text = new_text
            normalized.char_count = len(new_text)
            normalized.content_sha256 = hashlib.sha256(f"updated|{normalized.id}|{new_text}".encode("utf-8")).hexdigest()
        db.commit()
    finally:
        db.close()


def _analyze_document_items(tender_id: str, document_id: str) -> dict:
    response = client.post(f"/tenders/{tender_id}/documents/{document_id}/analyze-items")
    assert response.status_code == 200, response.text
    return response.json()


def _list_items(tender_id: str, document_id: str | None = None) -> dict:
    query = f"?document_id={document_id}" if document_id else ""
    response = client.get(f"/tenders/{tender_id}/items{query}")
    assert response.status_code == 200, response.text
    return response.json()


def _db_item_count(*, tender_id: str, document_id: str | None = None) -> int:
    db = SessionLocal()
    try:
        statement = select(func.count(TenderItem.id)).where(TenderItem.tender_id == tender_id)
        if document_id:
            statement = statement.where(TenderItem.source_document_id == document_id)
        return int(db.execute(statement).scalar_one())
    finally:
        db.close()


def test_extracts_numbered_multiline_item_with_quantity_and_unit() -> None:
    tender_id = _create_tender("items multiline", "ITEM-001")
    document_id = _import_pdf(tender_id, "scope-a.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 4\n\nServicio de mantenimiento preventivo\ny correctivo al sistema de control\ndistribuido instalado en planta.\n\nCantidad: 1\nUnidad: SERVICIO",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    assert payload["summary"]["items_created"] == 1
    assert payload["summary"]["items_with_number"] == 1
    item = payload["items"][0]
    assert item["item_number"] == "4"
    assert item["quantity"] == "1.0000"
    assert item["unit"] == "SERVICIO"
    assert "preventivo y correctivo" in item["raw_description"].lower()
    assert item["source_page"] == 1
    assert item["source_locator"]
    assert item["source_excerpt"]


def test_extracts_table_like_rows_and_ignores_header() -> None:
    tender_id = _create_tender("items table", "ITEM-002")
    document_id = _import_pdf(tender_id, "scope-table.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA | DESCRIPCION | CANTIDAD | UNIDAD\n1 | Servicio de calibracion | 2 | SERVICIO\n2 | Modulo de comunicacion | 4 | PIEZA",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 2
    assert payload["summary"]["total_items"] == 2
    descriptions = [item["raw_description"] for item in payload["items"]]
    assert all("descripcion" not in desc.lower() for desc in descriptions)


def test_extracts_bare_number_multiline_rows_from_ocr_style_catalog() -> None:
    tender_id = _create_tender("items ocr multiline", "ITEM-002B")
    document_id = _import_pdf(tender_id, "scope-ocr-catalog.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA\nCONCEPTO\nUNIDAD DE MEDIDA\nCANTIDAD\n"
        "1.\nSERVICIO DE MANTENIMIENTO PREVENTIVO PARA SISTEMA DE CONTROL DISTRIBUIDO MTBE 1\nSERVICIO\n1\n"
        "2.\nSERVICIO DE MANTENIMIENTO PREVENTIVO PARA SISTEMA DE CONTROL DISTRIBUIDO ASFALTOS\nSERVICIO\n1",
        source_type="PADDLEOCR",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 2
    assert payload["summary"]["items_with_quantity"] == 2
    assert payload["summary"]["items_with_unit"] == 2
    assert payload["items"][0]["item_number"] == "1"
    assert payload["items"][0]["quantity"] == "1.0000"
    assert payload["items"][0]["unit"] == "SERVICIO"
    assert "mantenimiento preventivo" in payload["items"][0]["raw_description"].lower()


def test_bare_normative_identifier_with_standard_title_is_not_item() -> None:
    tender_id = _create_tender("items normative negative", "ITEM-002C")
    document_id = _import_pdf(tender_id, "normative-list.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "No. M-002 - NOM-002-STPS-2010 Condiciones de Seguridad y Proteccion contra incendios",
        source_type="PADDLEOCR",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 0
    assert payload["summary"]["total_items"] == 0


def test_procurement_item_can_keep_iso_in_description() -> None:
    tender_id = _create_tender("items iso in description", "ITEM-002D")
    document_id = _import_pdf(tender_id, "scope-iso-item.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 14\nServicio de mantenimiento preventivo conforme a ISO 9001:2015 para sistema DCS.\nCantidad: 1\nUnidad: SERVICIO",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    assert payload["items"][0]["item_number"] == "14"
    assert payload["items"][0]["quantity"] == "1.0000"
    assert payload["items"][0]["unit"] == "SERVICIO"


def test_arbitrary_multiline_text_after_quantity_is_not_taken_as_unit() -> None:
    tender_id = _create_tender("items unit drift control", "ITEM-002E")
    document_id = _import_pdf(tender_id, "scope-unit-drift.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA\nCONCEPTO\nUNIDAD\nCANTIDAD\n"
        "1.\nServicio de mantenimiento preventivo de gabinete de control\n1\nCONTINUAS DE SWITCHES",
        source_type="PADDLEOCR",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    assert payload["items"][0]["quantity"] == "1.0000"
    assert payload["items"][0]["unit"] is None


def test_flattened_row_with_valid_unit_extracts_unit() -> None:
    tender_id = _create_tender("items flattened row", "ITEM-002F")
    document_id = _import_pdf(tender_id, "scope-flat-row.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA | DESCRIPCION | CANTIDAD | UNIDAD\n1 | Servicio de inspeccion de campo | 3 | SERVICIO",
        source_type="PADDLEOCR",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    assert payload["items"][0]["quantity"] == "3.0000"
    assert payload["items"][0]["unit"] == "SERVICIO"


def test_procedural_duration_is_not_item_quantity_binding() -> None:
    tender_id = _create_tender("items procedural duration", "ITEM-002G")
    document_id = _import_pdf(tender_id, "procedural-duration.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "RESPONSABILIDADES\n5. Elaborar y suscribir dictamen de evaluacion tecnica\nPlazo 21 Meses\n6. Informar resultados a la convocante",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 0


def test_technical_numbers_do_not_become_quantity() -> None:
    tender_id = _create_tender("items quantity safety", "ITEM-003")
    document_id = _import_pdf(tender_id, "scope-technical.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 7\nRelevador de proteccion para transformador,\nalimentacion 125 a 250 VCD,\ncorriente nominal 5 A.\nCantidad: 2\nUnidad: PIEZA",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    item = payload["items"][0]
    assert item["item_number"] == "7"
    assert item["quantity"] == "2.0000"
    assert item["unit"] == "PIEZA"


def test_admin_requirement_text_does_not_create_items() -> None:
    tender_id = _create_tender("items admin control", "ITEM-004")
    document_id = _import_pdf(tender_id, "admin.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "El participante debera estar registrado en la HIIP y presentar constancia vigente.",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 0
    assert payload["items"] == []


def test_header_only_text_does_not_create_items() -> None:
    tender_id = _create_tender("items header control", "ITEM-005")
    document_id = _import_pdf(tender_id, "header.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "ANEXO B-4\nPARTIDA\nDESCRIPCION\nCANTIDAD\nUNIDAD\nLicitacion Publica",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 0


def test_quantity_and_unit_are_nullable_when_not_explicit() -> None:
    tender_id = _create_tender("items nullable qty unit", "ITEM-006")
    document_id = _import_pdf(tender_id, "scope-no-qty.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 12\nServicio de inspeccion integral de instrumentacion en campo.",
    )

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    item = payload["items"][0]
    assert item["quantity"] is None
    assert item["unit"] is None


def test_rerun_is_deterministic_without_duplicate_growth() -> None:
    tender_id = _create_tender("items rerun", "ITEM-007")
    document_id = _import_pdf(tender_id, "scope-rerun.pdf")
    _seed_page_and_normalized(document_id, 1, "PARTIDA 1\nServicio de mantenimiento.\nCantidad: 1\nUnidad: SERVICIO")

    first = _analyze_document_items(tender_id, document_id)
    second = _analyze_document_items(tender_id, document_id)

    assert first["summary"]["items_created"] == 1
    assert second["summary"]["items_created"] == 0
    assert second["summary"]["items_unchanged"] == 1
    assert _db_item_count(tender_id=tender_id, document_id=document_id) == 1


def test_reanalysis_updates_document_scope_without_cross_document_mutation() -> None:
    tender_id = _create_tender("items doc isolation", "ITEM-008")
    doc_a = _import_pdf(tender_id, "scope-a.pdf")
    doc_b = _import_pdf(tender_id, "scope-b.pdf")

    _seed_page_and_normalized(doc_a, 1, "PARTIDA 1\nServicio de calibracion.\nCantidad: 2\nUnidad: SERVICIO")
    _seed_page_and_normalized(doc_b, 1, "PARTIDA 9\nTarjeta de entrada analogica.\nCantidad: 4\nUnidad: PIEZA")

    _analyze_document_items(tender_id, doc_a)
    _analyze_document_items(tender_id, doc_b)

    before_a = _db_item_count(tender_id=tender_id, document_id=doc_a)
    before_b = _db_item_count(tender_id=tender_id, document_id=doc_b)

    _update_normalized_text(doc_a, "PARTIDA 1\nServicio de calibracion avanzada.\nCantidad: 3\nUnidad: SERVICIO")
    rerun_a = _analyze_document_items(tender_id, doc_a)

    assert rerun_a["summary"]["items_detected"] == 1
    assert _db_item_count(tender_id=tender_id, document_id=doc_a) == 1
    assert _db_item_count(tender_id=tender_id, document_id=doc_b) == before_b == 1
    assert before_a == 1


def test_cross_tender_isolation_and_document_endpoints() -> None:
    tender_a = _create_tender("items tender A", "ITEM-009A")
    tender_b = _create_tender("items tender B", "ITEM-009B")
    doc_a = _import_pdf(tender_a, "scope-a.pdf")
    doc_b = _import_pdf(tender_b, "scope-b.pdf")

    _seed_page_and_normalized(doc_a, 1, "PARTIDA 3\nServicio A\nCantidad: 1\nUnidad: SERVICIO")
    _seed_page_and_normalized(doc_b, 1, "PARTIDA 3\nServicio B\nCantidad: 1\nUnidad: SERVICIO")

    _analyze_document_items(tender_a, doc_a)
    _analyze_document_items(tender_b, doc_b)

    list_a = _list_items(tender_a)
    list_b = _list_items(tender_b)
    assert list_a["summary"]["total_items"] == 1
    assert list_b["summary"]["total_items"] == 1

    document_items = client.get(f"/tenders/{tender_a}/documents/{doc_a}/items")
    assert document_items.status_code == 200
    detail_id = document_items.json()["items"][0]["id"]

    detail = client.get(f"/tenders/{tender_a}/items/{detail_id}")
    assert detail.status_code == 200
    assert detail.json()["source_document_id"] == doc_a

    wrong_tender_detail = client.get(f"/tenders/{tender_b}/items/{detail_id}")
    assert wrong_tender_detail.status_code == 404


def test_list_items_supports_document_filter() -> None:
    tender_id = _create_tender("items filter", "ITEM-010")
    doc_a = _import_pdf(tender_id, "scope-a.pdf")
    doc_b = _import_pdf(tender_id, "scope-b.pdf")

    _seed_page_and_normalized(doc_a, 1, "PARTIDA 1\nServicio principal\nCantidad: 1\nUnidad: SERVICIO")
    _seed_page_and_normalized(doc_b, 1, "PARTIDA 2\nMaterial de conexion\nCantidad: 4\nUnidad: PIEZA")

    _analyze_document_items(tender_id, doc_a)
    _analyze_document_items(tender_id, doc_b)

    all_items = _list_items(tender_id)
    filtered = _list_items(tender_id, document_id=doc_b)

    assert all_items["summary"]["total_items"] == 2
    assert filtered["summary"]["total_items"] == 1
    assert filtered["items"][0]["source_document_id"] == doc_b


class _FakeUrlopenResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeUrlopenResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_ollama_provider_parses_local_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return _FakeUrlopenResponse({"models": [{"name": "llava:latest"}, {"name": "qwen2.5vl:latest"}]})
        if request.full_url.endswith("/api/chat"):
            return _FakeUrlopenResponse(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "document_type": "TECHNICAL_SPECIFICATION",
                                "has_procurement_scope": True,
                                "confidence": 0.91,
                                "review_status": "REVIEW_REQUIRED",
                                "summary": "Local vision found one procurement scope proposal.",
                                "warnings": ["Needs human validation"],
                                "partidas": [
                                    {
                                        "item_number": "1",
                                        "description": "Servicio de mantenimiento predictivo para sistema de control distribuido",
                                        "quantity": "2",
                                        "unit": "SERVICIO",
                                        "source_pages": [1, 2],
                                        "evidence_excerpt": "Servicio de mantenimiento predictivo",
                                        "confidence": 0.88,
                                        "warnings": [],
                                    }
                                ],
                            }
                        )
                    }
                }
            )
        raise AssertionError(f"Unexpected URL: {request.full_url}")

    monkeypatch.setattr(local_vision_module.urllib.request, "urlopen", fake_urlopen)
    provider = OllamaVisionProvider(
        Settings(
            licitia_local_ai_enabled=True,
            licitia_ollama_base_url="http://127.0.0.1:11434",
            licitia_ollama_vision_model="llava:latest",
            licitia_ollama_timeout_seconds=1.0,
        )
    )

    assert provider.provider_status == "AVAILABLE"
    analysis = provider.analyze_scope_pages(
        tender_id="tender-1",
        document_id="document-1",
        source_filename="scope.pdf",
        document_type="TECHNICAL_SPECIFICATION",
        vision_mode="AUTO",
        pages=[VisionPageImage(page_number=1, png_bytes=b"page-1"), VisionPageImage(page_number=2, png_bytes=b"page-2")],
    )

    assert analysis.status == "PROPOSED"
    assert analysis.has_procurement_scope is True
    assert analysis.runtime.runtime_available is True
    assert analysis.runtime.selected_model == "llava:latest"
    assert analysis.partidas[0].description.startswith("Servicio de mantenimiento predictivo")
    assert analysis.partidas[0].source_pages == [1, 2]


def test_analyze_items_skips_vision_when_deterministic_items_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    tender_id = _create_tender("items deterministic first", "ITEM-011")
    document_id = _import_pdf(tender_id, "scope-deterministic.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 1\nServicio de calibracion de sensores.\nCantidad: 2\nUnidad: SERVICIO",
    )

    called = {"value": False}

    def fake_builder():
        called["value"] = True
        raise AssertionError("Vision provider should not be built when deterministic extraction succeeds")

    monkeypatch.setattr(tender_items_module, "build_local_vision_provider", fake_builder)

    payload = _analyze_document_items(tender_id, document_id)

    assert payload["summary"]["items_detected"] == 1
    assert payload["vision_analysis"] is None
    assert called["value"] is False


def test_analyze_items_forced_vision_returns_transient_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    tender_id = _create_tender("items forced vision", "ITEM-012")
    document_id = _import_pdf(tender_id, "scope-forced-vision.pdf")
    _seed_page_and_normalized(
        document_id,
        1,
        "PARTIDA 1\nServicio de mantenimiento integral\nCantidad: 2\nUnidad: SERVICIO",
        source_type="PADDLEOCR",
    )

    class FakeVisionProvider:
        provider_status = "AVAILABLE"

        def analyze_scope_pages(self, *, tender_id, document_id, source_filename, document_type, vision_mode, pages):
            assert vision_mode == "FORCE"
            assert pages
            return VisionAnalysisRead(
                tender_id=tender_id,
                document_id=document_id,
                source_filename=source_filename,
                vision_mode=vision_mode,
                status="PROPOSED",
                prompt_version="mvp-06.1-local-vision-001",
                document_type=document_type,
                has_procurement_scope=True,
                confidence=0.84,
                summary="Forced local vision proposal for review.",
                warnings=["Human validation required"],
                partidas=[
                    VisionPartidaProposalRead(
                        item_number="1",
                        description="Servicio de mantenimiento integral",
                        quantity=None,
                        unit="SERVICIO",
                        source_pages=[1],
                        evidence_excerpt="Servicio de mantenimiento integral",
                        confidence=0.84,
                        warnings=[],
                    )
                ],
                runtime=VisionRuntimeRead(
                    runtime_available=True,
                    models_available=["llava:latest"],
                    selected_model="llava:latest",
                    provider_id="LOCAL_VISION",
                    provider_name="Local Vision",
                    provider_status="AVAILABLE",
                    provider_status_reason="ok",
                    base_url="http://127.0.0.1:11434",
                ),
            )

    monkeypatch.setattr(tender_items_module, "build_local_vision_provider", lambda: FakeVisionProvider())
    monkeypatch.setattr(
        tender_items_module,
        "render_document_pages_as_png",
        lambda document, page_numbers: [VisionPageImage(page_number=page_number, png_bytes=b"page-bytes") for page_number in page_numbers],
    )

    response = client.post(
        f"/tenders/{tender_id}/documents/{document_id}/analyze-items",
        params={"vision_mode": "FORCE"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["items_detected"] == 1
    assert payload["vision_analysis"]["status"] == "PROPOSED"
    assert payload["vision_analysis"]["partidas"][0]["description"] == "Servicio de mantenimiento integral"
    assert _db_item_count(tender_id=tender_id, document_id=document_id) == 1
