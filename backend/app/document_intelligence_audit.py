from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.document_classification import CLASSIFIER_VERSION
from app.document_references import REFERENCE_EXTRACTOR_VERSION
from app.models import (
    DocumentChunk,
    DocumentClassification,
    DocumentPage,
    DocumentReference,
    DocumentReferenceAnalysis,
    DocumentRelationship,
    NormalizedContent,
    PageOcrResult,
    TenderDocument,
)

AUDIT_VERSION = "mvp-02.6"
READINESS_READY = "READY"
READINESS_PARTIAL = "PARTIALLY_READY"
READINESS_NOT_READY = "NOT_READY"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_BLOCKING = "BLOCKING"


def _data_root() -> Path:
    configured_root = Path(get_settings().licitia_data_dir)
    if not configured_root.is_absolute():
        configured_root = Path(__file__).resolve().parents[1] / configured_root
    return configured_root


def _resolve_storage_path(stored_relative_path: str | None) -> Path | None:
    if not stored_relative_path:
        return None

    normalized_path = stored_relative_path.replace("\\", "/")
    pure_path = PurePosixPath(normalized_path)
    if pure_path.is_absolute() or any(part in ("", ".", "..") for part in pure_path.parts):
        return None

    data_root = _data_root().resolve()
    resolved = (data_root / pure_path).resolve()
    if not resolved.is_relative_to(data_root):
        return None
    return resolved


def _short_id(document_id: str | None) -> str:
    if not document_id:
        return ""
    return document_id[:8]


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    code: str,
    severity: str,
    message: str,
    document_id: str | None = None,
    document_filename: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    findings.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "document_id": document_id,
            "document_filename": document_filename,
            "metadata": metadata or {},
        }
    )


def _effective_classification_type(classification: DocumentClassification | None) -> str:
    if classification is None:
        return "UNCLASSIFIED"
    if classification.human_type:
        return classification.human_type
    return classification.suggested_type


def _candidate_ids(reference: DocumentReference) -> list[str]:
    raw = reference.auto_candidate_document_ids or ""
    return [item for item in (value.strip() for value in raw.split(",")) if item]


def generate_document_intelligence_audit(db: Session, tender_id: str) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc)

    documents = (
        db.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id).order_by(TenderDocument.imported_at.asc()))
        .scalars()
        .all()
    )
    docs_by_id = {document.id: document for document in documents}
    current_documents = [document for document in documents if document.is_current]
    current_ids = [document.id for document in current_documents]

    findings: list[dict[str, Any]] = []

    pages = (
        db.execute(select(DocumentPage).where(DocumentPage.document_id.in_(current_ids or [""])).order_by(DocumentPage.page_number.asc()))
        .scalars()
        .all()
    )
    pages_by_doc: dict[str, list[DocumentPage]] = {}
    for page in pages:
        pages_by_doc.setdefault(page.document_id, []).append(page)

    ocr_rows = (
        db.execute(
            select(PageOcrResult)
            .join(DocumentPage, DocumentPage.id == PageOcrResult.document_page_id)
            .where(DocumentPage.document_id.in_(current_ids or [""]))
        )
        .scalars()
        .all()
    )
    ocr_by_page: dict[str, list[PageOcrResult]] = {}
    for row in ocr_rows:
        ocr_by_page.setdefault(row.document_page_id, []).append(row)

    normalized_sources = (
        db.execute(
            select(NormalizedContent)
            .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
            .where(DocumentPage.document_id.in_(current_ids or [""]))
        )
        .scalars()
        .all()
    )
    normalized_by_page: dict[str, list[NormalizedContent]] = {}
    normalized_by_doc: dict[str, list[NormalizedContent]] = {}
    normalized_by_id: dict[str, NormalizedContent] = {}
    for source in normalized_sources:
        normalized_by_page.setdefault(source.document_page_id, []).append(source)
        page = next((item for item in pages if item.id == source.document_page_id), None)
        if page is not None:
            normalized_by_doc.setdefault(page.document_id, []).append(source)
        normalized_by_id[source.id] = source

    chunks = (
        db.execute(
            select(DocumentChunk)
            .join(NormalizedContent, NormalizedContent.id == DocumentChunk.normalized_content_id)
            .join(DocumentPage, DocumentPage.id == NormalizedContent.document_page_id)
            .where(DocumentPage.document_id.in_(current_ids or [""]))
        )
        .scalars()
        .all()
    )
    chunk_count_by_doc: dict[str, int] = {}
    for chunk in chunks:
        source = normalized_by_id.get(chunk.normalized_content_id)
        if source is None:
            continue
        page = next((item for item in pages if item.id == source.document_page_id), None)
        if page is None:
            continue
        chunk_count_by_doc[page.document_id] = chunk_count_by_doc.get(page.document_id, 0) + 1

    classifications = (
        db.execute(select(DocumentClassification).where(DocumentClassification.document_id.in_(current_ids or [""])))
        .scalars()
        .all()
    )
    classification_by_doc = {item.document_id: item for item in classifications}

    reference_analyses = (
        db.execute(select(DocumentReferenceAnalysis).where(DocumentReferenceAnalysis.document_id.in_(current_ids or [""])))
        .scalars()
        .all()
    )
    analysis_by_doc = {item.document_id: item for item in reference_analyses}

    references = (
        db.execute(
            select(DocumentReference)
            .where(DocumentReference.source_document_id.in_(current_ids or [""]))
            .options(selectinload(DocumentReference.document_page))
            .order_by(DocumentReference.created_at.asc())
        )
        .scalars()
        .all()
    )
    refs_by_doc: dict[str, list[DocumentReference]] = {}
    for reference in references:
        refs_by_doc.setdefault(reference.source_document_id, []).append(reference)

    relationships = db.execute(select(DocumentRelationship).where(DocumentRelationship.tender_id == tender_id)).scalars().all()

    for reference in references:
        if reference.source_document_id not in docs_by_id:
            _add_finding(
                findings,
                code="REFERENCE_SOURCE_MISSING",
                severity=SEVERITY_BLOCKING,
                message="Existe una referencia cuyo documento fuente no existe.",
                document_id=reference.source_document_id,
                metadata={"reference_id": reference.id},
            )

    relationship_keys: dict[tuple[str, str, str], int] = {}
    for edge in relationships:
        relationship_keys[(edge.source_document_id, edge.target_document_id, edge.relationship_type)] = (
            relationship_keys.get((edge.source_document_id, edge.target_document_id, edge.relationship_type), 0) + 1
        )

    for (source_id, target_id, relationship_type), count in relationship_keys.items():
        if count > 1:
            _add_finding(
                findings,
                code="DUPLICATE_RELATIONSHIP_EDGE",
                severity=SEVERITY_WARNING,
                message="Existen aristas duplicadas en el grafo documental.",
                metadata={
                    "source_document_id": source_id,
                    "target_document_id": target_id,
                    "relationship_type": relationship_type,
                    "count": count,
                },
            )

    for edge in relationships:
        if edge.source_document_id == edge.target_document_id:
            source = docs_by_id.get(edge.source_document_id)
            _add_finding(
                findings,
                code="SELF_RELATIONSHIP_EDGE",
                severity=SEVERITY_BLOCKING,
                message="Existe una auto-relación persistida en el grafo documental.",
                document_id=edge.source_document_id,
                document_filename=source.original_filename if source else None,
                metadata={"relationship_id": edge.id},
            )
        if edge.source_document_id not in docs_by_id or edge.target_document_id not in docs_by_id:
            _add_finding(
                findings,
                code="RELATIONSHIP_REFERENTIAL_INTEGRITY",
                severity=SEVERITY_BLOCKING,
                message="Existe una relación con documentos inexistentes.",
                metadata={
                    "relationship_id": edge.id,
                    "source_document_id": edge.source_document_id,
                    "target_document_id": edge.target_document_id,
                },
            )

    duplicate_current_sha_groups: list[dict[str, Any]] = []
    current_by_sha: dict[str, list[TenderDocument]] = {}
    for document in current_documents:
        current_by_sha.setdefault(document.sha256, []).append(document)
    for sha256_value, group in current_by_sha.items():
        if len(group) > 1:
            payload = {
                "sha256": sha256_value,
                "documents": [
                    {"document_id": item.id, "original_filename": item.original_filename, "processing_status": item.processing_status}
                    for item in group
                ],
            }
            duplicate_current_sha_groups.append(payload)
            _add_finding(
                findings,
                code="DUPLICATE_CURRENT_SHA256",
                severity=SEVERITY_WARNING,
                message="Hay documentos vigentes con el mismo SHA-256.",
                metadata=payload,
            )

    filename_collision_groups: list[dict[str, Any]] = []
    current_by_filename: dict[str, list[TenderDocument]] = {}
    for document in current_documents:
        current_by_filename.setdefault(document.original_filename, []).append(document)
    for filename, group in current_by_filename.items():
        distinct_hashes = sorted({item.sha256 for item in group})
        if len(group) > 1 and len(distinct_hashes) > 1:
            payload = {
                "filename": filename,
                "documents": [
                    {
                        "document_id": item.id,
                        "sha256": item.sha256,
                        "processing_status": item.processing_status,
                    }
                    for item in group
                ],
            }
            filename_collision_groups.append(payload)
            _add_finding(
                findings,
                code="CURRENT_FILENAME_COLLISION",
                severity=SEVERITY_WARNING,
                message="Hay documentos vigentes con mismo nombre y distinto SHA-256.",
                metadata=payload,
            )

    per_document_rows: list[dict[str, Any]] = []

    acquisition_with_pages = 0
    acquisition_with_native_text = 0
    acquisition_requires_ocr = 0
    acquisition_with_ocr_results = 0
    acquisition_no_usable_text = 0
    acquisition_pending = 0

    normalization_with_sources = 0
    normalization_without_sources = 0
    pages_with_normalized_sources = 0
    pages_without_normalized_sources_despite_text = 0

    classification_classified = 0
    classification_unclassified = 0
    classification_status_counts = {
        "SUGGESTED": 0,
        "CONFIRMED": 0,
        "NEEDS_REVIEW": 0,
        "OVERRIDDEN": 0,
    }
    classification_unknown = 0
    classification_document_package = 0
    classification_non_composite = 0
    classification_stale_versions = 0

    references_analyzed = 0
    references_not_ready = 0
    references_ready_not_analyzed = 0
    reference_status_counts = {
        "AUTO_RESOLVED": 0,
        "AMBIGUOUS": 0,
        "UNRESOLVED": 0,
        "HUMAN_RESOLVED": 0,
        "IGNORED": 0,
    }
    references_stale_versions = 0

    for document in current_documents:
        row_findings: list[str] = []
        pages_for_doc = pages_by_doc.get(document.id, [])
        refs_for_doc = refs_by_doc.get(document.id, [])
        normalized_for_doc = normalized_by_doc.get(document.id, [])
        classification = classification_by_doc.get(document.id)
        analysis = analysis_by_doc.get(document.id)

        storage_path = _resolve_storage_path(document.stored_relative_path)
        storage_exists = bool(storage_path and storage_path.exists() and storage_path.is_file())
        if not storage_exists:
            row_findings.append("MISSING_STORAGE")
            _add_finding(
                findings,
                code="MISSING_STORAGE",
                severity=SEVERITY_BLOCKING,
                message="Documento vigente sin archivo físico local accesible.",
                document_id=document.id,
                document_filename=document.original_filename,
                metadata={"stored_relative_path": document.stored_relative_path},
            )

        has_pages = len(pages_for_doc) > 0
        has_native_text = any(bool((page.text or "").strip()) for page in pages_for_doc)
        doc_ocr_rows = [ocr for page in pages_for_doc for ocr in ocr_by_page.get(page.id, [])]
        has_ocr_results = len(doc_ocr_rows) > 0
        has_usable_ocr_text = any(bool((ocr.text or "").strip()) for ocr in doc_ocr_rows)
        has_usable_text = has_native_text or has_usable_ocr_text

        if has_pages:
            acquisition_with_pages += 1
        if has_native_text:
            acquisition_with_native_text += 1
        if document.processing_status == "NO_NATIVE_TEXT":
            acquisition_requires_ocr += 1
        if has_ocr_results:
            acquisition_with_ocr_results += 1
        if not has_usable_text:
            acquisition_no_usable_text += 1
        if document.processing_status in {"PENDING", "TEXT_EXTRACTION_FAILED"}:
            acquisition_pending += 1

        if not has_pages and document.processing_status == "PENDING":
            text_state = "PENDING"
        elif has_usable_text:
            text_state = "READY"
        elif has_ocr_results and not has_usable_ocr_text:
            text_state = "OCR_FAILED"
        elif document.processing_status == "NO_NATIVE_TEXT":
            text_state = "OCR_REQUIRED"
        else:
            text_state = "INCOMPLETE"

        if not has_usable_text:
            if document.processing_status in {"PENDING", "NO_NATIVE_TEXT", "TEXT_EXTRACTION_FAILED"}:
                row_findings.append("TEXT_PIPELINE_INCOMPLETE")
                _add_finding(
                    findings,
                    code="TEXT_PIPELINE_INCOMPLETE",
                    severity=SEVERITY_WARNING,
                    message="Documento vigente sin texto utilizable; flujo de adquisición pendiente o incompleto.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                    metadata={"processing_status": document.processing_status, "text_state": text_state},
                )
            else:
                row_findings.append("NO_USABLE_TEXT")
                _add_finding(
                    findings,
                    code="NO_USABLE_TEXT",
                    severity=SEVERITY_BLOCKING,
                    message="Documento vigente sin texto utilizable en un estado inconsistente.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                    metadata={"processing_status": document.processing_status},
                )
        elif text_state in {"PENDING", "OCR_REQUIRED", "OCR_FAILED", "INCOMPLETE"}:
            row_findings.append("TEXT_PIPELINE_INCOMPLETE")
            _add_finding(
                findings,
                code="TEXT_PIPELINE_INCOMPLETE",
                severity=SEVERITY_WARNING,
                message="Documento vigente con adquisición de texto incompleta.",
                document_id=document.id,
                document_filename=document.original_filename,
                metadata={"processing_status": document.processing_status, "text_state": text_state},
            )

        normalized_count = len(normalized_for_doc)
        chunk_count = chunk_count_by_doc.get(document.id, 0)

        if normalized_count > 0:
            normalization_with_sources += 1
        else:
            normalization_without_sources += 1

        page_has_text_or_ocr = {
            page.id: bool((page.text or "").strip()) or any(bool((ocr.text or "").strip()) for ocr in ocr_by_page.get(page.id, []))
            for page in pages_for_doc
        }
        for page in pages_for_doc:
            if normalized_by_page.get(page.id):
                pages_with_normalized_sources += 1
            elif page_has_text_or_ocr.get(page.id):
                pages_without_normalized_sources_despite_text += 1

        if normalized_count == 0 and has_usable_text:
            row_findings.append("MISSING_NORMALIZED_CONTENT")
            _add_finding(
                findings,
                code="MISSING_NORMALIZED_CONTENT",
                severity=SEVERITY_WARNING,
                message="Documento con texto utilizable pero sin contenido normalizado.",
                document_id=document.id,
                document_filename=document.original_filename,
            )

        if classification is None:
            classification_unclassified += 1
            classification_type = "UNCLASSIFIED"
            classification_status = "UNCLASSIFIED"
            classifier_version = None
            if normalized_count > 0:
                row_findings.append("MISSING_CLASSIFICATION")
                _add_finding(
                    findings,
                    code="MISSING_CLASSIFICATION",
                    severity=SEVERITY_WARNING,
                    message="Documento con contenido normalizado sin clasificación persistida.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                )
        else:
            classification_classified += 1
            classification_type = _effective_classification_type(classification)
            classification_status = classification.classification_status
            classifier_version = classification.classifier_version
            classification_status_counts[classification.classification_status] = (
                classification_status_counts.get(classification.classification_status, 0) + 1
            )
            if classification_type == "UNKNOWN":
                classification_unknown += 1
            if classification_type == "DOCUMENT_PACKAGE":
                classification_document_package += 1
            if not classification.is_composite:
                classification_non_composite += 1
            if classification.classifier_version != CLASSIFIER_VERSION:
                classification_stale_versions += 1
                row_findings.append("STALE_CLASSIFIER_VERSION")
                _add_finding(
                    findings,
                    code="STALE_ANALYSIS_VERSION",
                    severity=SEVERITY_WARNING,
                    message="Clasificación generada con versión anterior del clasificador.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                    metadata={
                        "engine": "classification",
                        "expected_version": CLASSIFIER_VERSION,
                        "observed_version": classification.classifier_version,
                    },
                )

        if analysis is None:
            reference_status = "NOT_ANALYZED"
            reference_version = None
            if normalized_count > 0:
                references_ready_not_analyzed += 1
                row_findings.append("MISSING_REFERENCE_ANALYSIS")
                _add_finding(
                    findings,
                    code="MISSING_REFERENCE_ANALYSIS",
                    severity=SEVERITY_WARNING,
                    message="Documento listo para referencias pero aún no analizado.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                )
        else:
            reference_status = analysis.status
            reference_version = analysis.extractor_version
            if analysis.status == "COMPLETED":
                references_analyzed += 1
            elif analysis.status == "NOT_READY":
                references_not_ready += 1
            if analysis.extractor_version != REFERENCE_EXTRACTOR_VERSION:
                references_stale_versions += 1
                row_findings.append("STALE_REFERENCE_VERSION")
                _add_finding(
                    findings,
                    code="STALE_ANALYSIS_VERSION",
                    severity=SEVERITY_WARNING,
                    message="Análisis de referencias generado con versión anterior del resolver.",
                    document_id=document.id,
                    document_filename=document.original_filename,
                    metadata={
                        "engine": "references",
                        "expected_version": REFERENCE_EXTRACTOR_VERSION,
                        "observed_version": analysis.extractor_version,
                    },
                )

        status_counters = {
            "AUTO_RESOLVED": 0,
            "AMBIGUOUS": 0,
            "UNRESOLVED": 0,
            "HUMAN_RESOLVED": 0,
            "IGNORED": 0,
        }
        for reference in refs_for_doc:
            if reference.resolution_status in status_counters:
                status_counters[reference.resolution_status] += 1
                reference_status_counts[reference.resolution_status] += 1

        if status_counters["AMBIGUOUS"] > 0:
            row_findings.append("AMBIGUOUS_REFERENCES")
        if status_counters["UNRESOLVED"] > 0:
            row_findings.append("UNRESOLVED_REFERENCES")

        per_document_rows.append(
            {
                "document_id": document.id,
                "document_short_id": _short_id(document.id),
                "filename": document.original_filename,
                "is_current": document.is_current,
                "processing_status": document.processing_status,
                "page_count": document.page_count,
                "text_acquisition_state": text_state,
                "storage_exists": storage_exists,
                "normalized": normalized_count > 0,
                "normalized_source_count": normalized_count,
                "chunk_count": chunk_count,
                "classification_type": classification_type,
                "classification_status": classification_status,
                "classification_version": classifier_version,
                "reference_analysis_status": reference_status,
                "reference_extractor_version": reference_version,
                "reference_count": len(refs_for_doc),
                "auto_resolved_reference_count": status_counters["AUTO_RESOLVED"],
                "human_resolved_reference_count": status_counters["HUMAN_RESOLVED"],
                "ambiguous_reference_count": status_counters["AMBIGUOUS"],
                "unresolved_reference_count": status_counters["UNRESOLVED"],
                "ignored_reference_count": status_counters["IGNORED"],
                "integrity_findings": sorted(set(row_findings)),
            }
        )

    unresolved_groups_map: dict[str, dict[str, Any]] = {}
    ambiguous_groups_map: dict[tuple[str, str, str], dict[str, Any]] = {}

    for reference in references:
        source_document = docs_by_id.get(reference.source_document_id)
        source_filename = source_document.original_filename if source_document else "(desconocido)"
        page_number = reference.document_page.page_number if reference.document_page is not None else None
        candidates = _candidate_ids(reference)

        if reference.resolution_status == "UNRESOLVED":
            group = unresolved_groups_map.setdefault(
                reference.normalized_reference_key,
                {
                    "normalized_reference_key": reference.normalized_reference_key,
                    "mention_count": 0,
                    "source_documents": {},
                    "pages": set(),
                    "sample_excerpt": "",
                    "candidate_count": 0,
                },
            )
            group["mention_count"] += 1
            group["source_documents"][reference.source_document_id] = {
                "document_id": reference.source_document_id,
                "filename": source_filename,
            }
            if page_number is not None:
                group["pages"].add(page_number)
            if not group["sample_excerpt"] and reference.excerpt:
                group["sample_excerpt"] = reference.excerpt
            group["candidate_count"] = max(group["candidate_count"], len(candidates))

        if reference.resolution_status in {"AMBIGUOUS", "HUMAN_RESOLVED"}:
            candidate_set_key = ",".join(candidates)
            key = (reference.source_document_id, reference.normalized_reference_key, candidate_set_key)
            group = ambiguous_groups_map.setdefault(
                key,
                {
                    "source_document_id": reference.source_document_id,
                    "source_document_filename": source_filename,
                    "normalized_reference_key": reference.normalized_reference_key,
                    "candidate_documents": [
                        {
                            "document_id": candidate_id,
                            "filename": docs_by_id[candidate_id].original_filename if candidate_id in docs_by_id else "(desconocido)",
                            "document_short_id": _short_id(candidate_id),
                            "processing_status": docs_by_id[candidate_id].processing_status if candidate_id in docs_by_id else None,
                        }
                        for candidate_id in candidates
                    ],
                    "mention_count": 0,
                    "ambiguous_mention_count": 0,
                    "human_resolved_mention_count": 0,
                    "pages": set(),
                },
            )
            group["mention_count"] += 1
            if reference.resolution_status == "AMBIGUOUS":
                group["ambiguous_mention_count"] += 1
            if reference.resolution_status == "HUMAN_RESOLVED":
                group["human_resolved_mention_count"] += 1
            if page_number is not None:
                group["pages"].add(page_number)

    unresolved_groups = []
    for group in unresolved_groups_map.values():
        unresolved_groups.append(
            {
                "normalized_reference_key": group["normalized_reference_key"],
                "mention_count": group["mention_count"],
                "source_documents": sorted(group["source_documents"].values(), key=lambda item: item["filename"]),
                "pages": sorted(group["pages"]),
                "sample_excerpt": group["sample_excerpt"],
                "candidate_count": group["candidate_count"],
            }
        )
    unresolved_groups.sort(key=lambda item: (-item["mention_count"], item["normalized_reference_key"]))

    ambiguous_groups = []
    for group in ambiguous_groups_map.values():
        ambiguous_groups.append(
            {
                "source_document_id": group["source_document_id"],
                "source_document_filename": group["source_document_filename"],
                "normalized_reference_key": group["normalized_reference_key"],
                "candidate_documents": group["candidate_documents"],
                "mention_count": group["mention_count"],
                "ambiguous_mention_count": group["ambiguous_mention_count"],
                "human_resolved_mention_count": group["human_resolved_mention_count"],
                "pages": sorted(group["pages"]),
            }
        )
    ambiguous_groups.sort(
        key=lambda item: (
            item["source_document_filename"],
            item["normalized_reference_key"],
            -item["mention_count"],
        )
    )

    relationship_type_counts = {
        "REFERENCES": 0,
        "MODIFIES": 0,
    }
    edge_rows = []
    for edge in relationships:
        relationship_type_counts[edge.relationship_type] = relationship_type_counts.get(edge.relationship_type, 0) + 1
        support_count = 0
        for reference in references:
            if reference.source_document_id != edge.source_document_id:
                continue
            if reference.relationship_hint != edge.relationship_type:
                continue
            if reference.resolved_target_document_id != edge.target_document_id:
                continue
            if reference.resolution_status not in {"AUTO_RESOLVED", "HUMAN_RESOLVED"}:
                continue
            support_count += 1

        edge_rows.append(
            {
                "source_document_id": edge.source_document_id,
                "source_document_filename": docs_by_id[edge.source_document_id].original_filename if edge.source_document_id in docs_by_id else None,
                "relationship_type": edge.relationship_type,
                "target_document_id": edge.target_document_id,
                "target_document_filename": docs_by_id[edge.target_document_id].original_filename if edge.target_document_id in docs_by_id else None,
                "supporting_reference_count": support_count,
            }
        )

    duplicate_edge_count = sum(1 for value in relationship_keys.values() if value > 1)
    self_edge_count = sum(1 for edge in relationships if edge.source_document_id == edge.target_document_id)

    summary = {
        "documents": {
            "total_documents": len(documents),
            "current_documents": len(current_documents),
            "non_current_documents": len(documents) - len(current_documents),
        },
        "acquisition": {
            "documents_with_pages": acquisition_with_pages,
            "documents_with_native_text": acquisition_with_native_text,
            "documents_requiring_ocr": acquisition_requires_ocr,
            "documents_with_ocr_results": acquisition_with_ocr_results,
            "documents_with_no_usable_text": acquisition_no_usable_text,
            "documents_pending_or_failed": acquisition_pending,
        },
        "normalization": {
            "current_documents_with_normalized_content": normalization_with_sources,
            "current_documents_without_normalized_content": normalization_without_sources,
            "total_normalized_sources": len(normalized_sources),
            "total_chunks": len(chunks),
            "pages_with_normalized_sources": pages_with_normalized_sources,
            "pages_without_normalized_sources_despite_text": pages_without_normalized_sources_despite_text,
        },
        "classification": {
            "classified_documents": classification_classified,
            "unclassified_documents": classification_unclassified,
            "status_counts": classification_status_counts,
            "unknown_documents": classification_unknown,
            "document_package_count": classification_document_package,
            "non_composite_count": classification_non_composite,
            "stale_classifier_version_documents": classification_stale_versions,
        },
        "references": {
            "documents_analyzed": references_analyzed,
            "documents_not_analyzed_not_ready": references_not_ready,
            "documents_ready_not_analyzed": references_ready_not_analyzed,
            "status_counts": reference_status_counts,
            "stale_reference_version_documents": references_stale_versions,
        },
        "relationships": {
            "total_edges": len(relationships),
            "relationship_type_counts": relationship_type_counts,
            "duplicate_edge_count": duplicate_edge_count,
            "self_edge_count": self_edge_count,
        },
        "integrity": {
            "filename_collision_count": len(filename_collision_groups),
            "duplicate_current_sha256_count": len(duplicate_current_sha_groups),
            "missing_storage_count": sum(1 for item in findings if item["code"] == "MISSING_STORAGE"),
            "stale_analysis_count": sum(1 for item in findings if item["code"] == "STALE_ANALYSIS_VERSION"),
            "total_findings": len(findings),
        },
    }

    has_blocking = any(item["severity"] == SEVERITY_BLOCKING for item in findings)
    if has_blocking:
        overall_readiness = READINESS_NOT_READY
    else:
        has_partial_signals = any(
            [
                summary["acquisition"]["documents_pending_or_failed"] > 0,
                summary["acquisition"]["documents_with_no_usable_text"] > 0,
                summary["normalization"]["current_documents_without_normalized_content"] > 0,
                summary["classification"]["unclassified_documents"] > 0,
                summary["references"]["documents_ready_not_analyzed"] > 0,
                summary["references"]["status_counts"]["AMBIGUOUS"] > 0,
                summary["references"]["status_counts"]["UNRESOLVED"] > 0,
                summary["classification"]["status_counts"].get("NEEDS_REVIEW", 0) > 0,
                any(item["severity"] == SEVERITY_WARNING for item in findings),
            ]
        )
        overall_readiness = READINESS_PARTIAL if has_partial_signals else READINESS_READY

    return {
        "tender_id": tender_id,
        "audit_version": AUDIT_VERSION,
        "generated_at": generated_at,
        "overall_readiness": overall_readiness,
        "readiness_rule": {
            "ready": "Sin hallazgos BLOCKING y sin brechas críticas de pipeline en documentos vigentes.",
            "partially_ready": "Sin corrupción estructural, pero con pendientes o ambiguedades visibles.",
            "not_ready": "Existe al menos un hallazgo BLOCKING de integridad o adquisición.",
        },
        "engine_versions": {
            "classification_expected_version": CLASSIFIER_VERSION,
            "reference_expected_version": REFERENCE_EXTRACTOR_VERSION,
        },
        "summary": summary,
        "document_rows": sorted(per_document_rows, key=lambda row: row["filename"].lower()),
        "findings": findings,
        "unresolved_reference_groups": unresolved_groups,
        "ambiguous_reference_groups": ambiguous_groups,
        "relationship_summary": {
            **summary["relationships"],
            "edges": sorted(
                edge_rows,
                key=lambda item: (
                    item["source_document_filename"] or "",
                    item["relationship_type"],
                    item["target_document_filename"] or "",
                ),
            ),
        },
        "registry_anomalies": {
            "filename_collisions": filename_collision_groups,
            "duplicate_current_sha256": duplicate_current_sha_groups,
        },
    }
