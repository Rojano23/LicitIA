from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app import source_effect_materializer as materializer_module
from app.models import DocumentPage, DocumentVisionAnalysis, DocumentVisionPageResult, TenderDocument, TenderSourceEffect
from app.source_effect_materializer import (
    SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE,
    SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED,
    SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS,
    SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED,
    materialize_document_source_effects,
    materialize_source_effects_for_artifact,
)
from app.source_effect_deterministic import (
    SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT,
    SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET,
    SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW,
)
from app.source_effect_adapters import SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED, SourceEffectEvidenceArtifact
from app.source_effect_deterministic import SourceEffectDeterministicResult
from app.source_effects import SourceEffectCandidate, replace_source_effects_for_artifact

client = TestClient(app)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-MAT-{uuid4()}",
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


def _seed_page(db, document_id: str, page_number: int, text: str) -> DocumentPage:
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
    return page


def _seed_stale_effect(
    db,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
) -> None:
    replace_source_effects_for_artifact(
        db,
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        document_page_id=document_page_id,
        source_artifact_key=source_artifact_key,
        candidates=[
            SourceEffectCandidate(
                tender_id=tender_id,
                acting_document_id=acting_document_id,
                affected_document_id=None,
                document_page_id=document_page_id,
                affected_document_page_id=None,
                effect_type="AMENDS",
                effect_scope="UNRESOLVED",
                affected_document_ref_raw="Anexo B",
                affected_locator_raw=None,
                effective_date_raw=None,
                source_method="NATIVE",
                source_artifact_key=source_artifact_key,
                source_locator="page:1|effect:0",
                source_excerpt="Se modifica Anexo B.",
                review_required=True,
                confidence=None,
                source_contract_version="NATIVE_TEXT_V1",
            )
        ],
    )


def _count_effects(db, *, tender_id: str) -> int:
    value = db.scalar(select(func.count(TenderSourceEffect.id)).where(TenderSourceEffect.tender_id == tender_id))
    return int(value or 0)


def _count_boundary_effects(
    db,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    source_artifact_key: str,
) -> int:
    value = db.scalar(
        select(func.count(TenderSourceEffect.id)).where(
            TenderSourceEffect.tender_id == tender_id,
            TenderSourceEffect.acting_document_id == acting_document_id,
            TenderSourceEffect.document_page_id == document_page_id,
            TenderSourceEffect.source_artifact_key == source_artifact_key,
        )
    )
    return int(value or 0)


def _seed_vision_analysis(
    db,
    *,
    tender_id: str,
    document_id: str,
    input_fingerprint: str,
) -> DocumentVisionAnalysis:
    analysis = DocumentVisionAnalysis(
        tender_id=tender_id,
        document_id=document_id,
        status="COMPLETED",
        mode="ASSISTIVE_EXTRACTION",
        model_name="qwen3-vl:4b-instruct",
        prompt_version="vision-source-effects-001",
        input_fingerprint_sha256=input_fingerprint,
    )
    db.add(analysis)
    db.flush()
    return analysis


def _seed_vision_page_result(
    db,
    *,
    analysis_id: str,
    page: DocumentPage,
    plain_text: str,
) -> DocumentVisionPageResult:
    page_result = DocumentVisionPageResult(
        analysis_id=analysis_id,
        document_page_id=page.id,
        page_number=page.page_number,
        image_sha256=hashlib.sha256(f"image|{page.id}|{uuid4()}".encode("utf-8")).hexdigest(),
        status="COMPLETED",
        raw_response_text=None,
        structured_json=None,
        extracted_markdown=None,
        extracted_plain_text=plain_text,
        warnings=[],
        processing_time_ms=8,
    )
    db.add(page_result)
    db.flush()
    return page_result


def test_supported_no_effects_clears_boundary_rows() -> None:
    tender_id = _create_tender("source effect materializer clear boundary")
    acting_doc_id = _import_pdf(tender_id, "junta-clear.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Sin menciones de cambios documentales.")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=artifact_key,
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS
        assert result.persisted_count == 0
        assert _count_effects(db, tender_id=tender_id) == 0
    finally:
        db.close()


def test_invalid_evidence_is_non_destructive() -> None:
    tender_id = _create_tender("source effect materializer invalid non destructive")
    acting_doc_id = _import_pdf(tender_id, "junta-invalid.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B.")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key="native-page:missing",
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_INVALID_EVIDENCE
        assert _count_effects(db, tender_id=tender_id) == 1
    finally:
        db.close()


def test_materializes_resolved_cross_document_effect() -> None:
    tender_id = _create_tender("source effect materializer resolved")
    acting_doc_id = _import_pdf(tender_id, "junta-resolved.pdf")
    target_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        acting_page = _seed_page(db, acting_doc_id, 1, "Se corrige Anexo B, numeral 4.2.")
        _seed_page(db, target_doc_id, 2, "contenido")
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=acting_page.id,
            source_method="NATIVE",
            source_artifact_key=f"native-page:{acting_page.id}",
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_MATERIALIZED
        assert result.persisted_count == 1
        row = db.scalar(select(TenderSourceEffect).where(TenderSourceEffect.tender_id == tender_id))
        assert row is not None
        assert row.affected_document_id == target_doc_id
        assert row.effect_type == "CORRECTS"
        assert row.effect_scope == "PARTIAL"
    finally:
        db.close()


def test_review_required_without_candidates_clears_exact_boundary_and_keeps_isolation() -> None:
    tender_id = _create_tender("source effect materializer review no candidates")
    acting_doc_id = _import_pdf(tender_id, "junta-review-no-candidates.pdf")
    other_doc_id = _import_pdf(tender_id, "anexo-c.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se corrige el voltaje del transmisor.")
        other_page = _seed_page(db, acting_doc_id, 2, "Texto sin efecto")
        other_doc_page = _seed_page(db, other_doc_id, 1, "Texto sin efecto")

        artifact_key = f"native-page:{page.id}"
        other_artifact_key = f"native-page:{other_page.id}"
        other_doc_artifact_key = f"native-page:{other_doc_page.id}"

        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=other_page.id,
            source_artifact_key=other_artifact_key,
        )
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=other_doc_id,
            document_page_id=other_doc_page.id,
            source_artifact_key=other_doc_artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=artifact_key,
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        assert result.persisted_count == 0
        assert SOURCE_EFFECT_DIAGNOSTIC_MISSING_TARGET_CONTEXT in result.diagnostics

        assert (
            _count_boundary_effects(
                db,
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=page.id,
                source_artifact_key=artifact_key,
            )
            == 0
        )
        assert (
            _count_boundary_effects(
                db,
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=other_page.id,
                source_artifact_key=other_artifact_key,
            )
            == 1
        )
        assert (
            _count_boundary_effects(
                db,
                tender_id=tender_id,
                acting_document_id=other_doc_id,
                document_page_id=other_doc_page.id,
                source_artifact_key=other_doc_artifact_key,
            )
            == 1
        )
        assert _count_effects(db, tender_id=tender_id) == 2
    finally:
        db.close()


def test_unsupported_result_stays_non_destructive() -> None:
    tender_id = _create_tender("source effect materializer unsupported")
    acting_doc_id = _import_pdf(tender_id, "junta-unsupported.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B.")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        original_discover = materializer_module.discover_source_effects_from_evidence

        def _unsupported_discover(_db, artifact: SourceEffectEvidenceArtifact) -> SourceEffectDeterministicResult:
            return SourceEffectDeterministicResult(
                source_artifact_key=artifact.source_artifact_key,
                status=SOURCE_EFFECT_ADAPTER_STATUS_UNSUPPORTED,
                candidates=(),
                diagnostics=("forced-unsupported",),
            )

        materializer_module.discover_source_effects_from_evidence = _unsupported_discover
        try:
            result = materialize_source_effects_for_artifact(
                db,
                tender_id=tender_id,
                acting_document_id=acting_doc_id,
                document_page_id=page.id,
                source_method="NATIVE",
                source_artifact_key=artifact_key,
            )
        finally:
            materializer_module.discover_source_effects_from_evidence = original_discover

        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_UNSUPPORTED
        assert _count_effects(db, tender_id=tender_id) == 1
    finally:
        db.close()


def test_review_required_with_safe_candidate_replaces_stale_boundary() -> None:
    tender_id = _create_tender("source effect materializer review with candidate")
    acting_doc_id = _import_pdf(tender_id, "junta-review-candidate.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo Técnico en su totalidad.")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=artifact_key,
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        assert result.persisted_count == 1

        row = db.scalar(
            select(TenderSourceEffect).where(
                TenderSourceEffect.tender_id == tender_id,
                TenderSourceEffect.acting_document_id == acting_doc_id,
                TenderSourceEffect.document_page_id == page.id,
                TenderSourceEffect.source_artifact_key == artifact_key,
            )
        )
        assert row is not None
        assert row.review_required is True
        assert row.affected_document_id is None
        assert row.affected_document_ref_raw == "Anexo Técnico"
    finally:
        db.close()


def test_self_target_replaces_stale_with_review_candidate_and_preserves_diagnostic() -> None:
    tender_id = _create_tender("source effect materializer self target")
    acting_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se modifica Anexo B en su totalidad.")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=artifact_key,
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        assert SOURCE_EFFECT_DIAGNOSTIC_SAME_DOCUMENT_TARGET in result.diagnostics

        row = db.scalar(
            select(TenderSourceEffect).where(
                TenderSourceEffect.tender_id == tender_id,
                TenderSourceEffect.acting_document_id == acting_doc_id,
                TenderSourceEffect.document_page_id == page.id,
                TenderSourceEffect.source_artifact_key == artifact_key,
            )
        )
        assert row is not None
        assert row.review_required is True
        assert row.affected_document_id is None
        assert row.affected_document_ref_raw == "Anexo B"
    finally:
        db.close()


def test_third_source_replacement_replaces_stale_and_preserves_diagnostic() -> None:
    tender_id = _create_tender("source effect materializer third source")
    acting_doc_id = _import_pdf(tender_id, "junta-third-source.pdf")
    affected_doc_id = _import_pdf(tender_id, "anexo-b.pdf")
    _ = _import_pdf(tender_id, "anexo-c.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "Se sustituye Anexo B por Anexo C.")
        _seed_page(db, affected_doc_id, 1, "contenido")
        artifact_key = f"native-page:{page.id}"
        _seed_stale_effect(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=artifact_key,
        )
        db.commit()

        result = materialize_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_method="NATIVE",
            source_artifact_key=artifact_key,
        )
        db.commit()

        assert result.status == SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED
        assert result.persisted_count == 1
        assert SOURCE_EFFECT_DIAGNOSTIC_THIRD_SOURCE_REFERENCE_REQUIRES_REVIEW in result.diagnostics

        row = db.scalar(
            select(TenderSourceEffect).where(
                TenderSourceEffect.tender_id == tender_id,
                TenderSourceEffect.acting_document_id == acting_doc_id,
                TenderSourceEffect.document_page_id == page.id,
                TenderSourceEffect.source_artifact_key == artifact_key,
            )
        )
        assert row is not None
        assert row.review_required is True
        assert row.affected_document_id == affected_doc_id
        assert row.affected_document_ref_raw == "Anexo B"
    finally:
        db.close()


def test_document_materializer_clears_deselected_vision_boundary() -> None:
    tender_id = _create_tender("source effect materializer vision deselected")
    acting_doc_id = _import_pdf(tender_id, "vision-deselected.pdf")
    target_doc_id = _import_pdf(tender_id, "anexo-b.pdf")

    db = SessionLocal()
    try:
        page = _seed_page(db, acting_doc_id, 1, "texto base")
        _seed_page(db, target_doc_id, 1, "contenido")
        lineage_key = hashlib.sha256(f"lineage|{acting_doc_id}|{page.id}".encode("utf-8")).hexdigest()
        analysis = _seed_vision_analysis(
            db,
            tender_id=tender_id,
            document_id=acting_doc_id,
            input_fingerprint=lineage_key,
        )

        older = _seed_vision_page_result(
            db,
            analysis_id=analysis.id,
            page=page,
            plain_text="Se modifica Anexo B en su totalidad.",
        )
        newer = _seed_vision_page_result(
            db,
            analysis_id=analysis.id,
            page=page,
            plain_text="Texto sin efectos cross-document.",
        )

        replace_source_effects_for_artifact(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
            document_page_id=page.id,
            source_artifact_key=f"vision-page-result:{older.id}",
            candidates=[
                SourceEffectCandidate(
                    tender_id=tender_id,
                    acting_document_id=acting_doc_id,
                    affected_document_id=target_doc_id,
                    document_page_id=page.id,
                    affected_document_page_id=None,
                    effect_type="AMENDS",
                    effect_scope="DOCUMENT_WIDE",
                    affected_document_ref_raw="Anexo B",
                    affected_locator_raw=None,
                    effective_date_raw=None,
                    source_method="VISION",
                    source_artifact_key=f"vision-page-result:{older.id}",
                    source_locator="page:1|effect:0",
                    source_excerpt="Se modifica Anexo B en su totalidad.",
                    review_required=False,
                    confidence=None,
                    source_contract_version="vision-source-effects-001",
                    source_analysis_id=older.analysis_id,
                    source_page_result_id=older.id,
                )
            ],
        )
        db.commit()

        result = materialize_document_source_effects(
            db,
            tender_id=tender_id,
            acting_document_id=acting_doc_id,
        )
        db.commit()

        assert result.status in {
            SOURCE_EFFECT_MATERIALIZATION_STATUS_NO_EFFECTS,
            SOURCE_EFFECT_MATERIALIZATION_STATUS_REVIEW_REQUIRED,
        }
        stale_count = db.scalar(
            select(func.count(TenderSourceEffect.id)).where(
                TenderSourceEffect.source_artifact_key == f"vision-page-result:{older.id}",
            )
        )
        assert int(stale_count or 0) == 0

        current_count = db.scalar(
            select(func.count(TenderSourceEffect.id)).where(
                TenderSourceEffect.source_artifact_key == f"vision-page-result:{newer.id}",
            )
        )
        assert int(current_count or 0) == 0
    finally:
        db.close()
