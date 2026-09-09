#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.effective_source_projection import project_effective_sources_for_tender
from app.models import DocumentPage, TenderDocument
from app.source_effect_adapters import enumerate_source_effect_evidence_for_document
from app.source_effect_deterministic import discover_source_effects_from_evidence
from app.source_effect_golden import (
    CASE_CATEGORY_DESCRIPTIVE_NEGATIVE,
    CASE_CATEGORY_HARD_NEGATIVE,
    CASE_CATEGORY_POSITIVE,
    CASE_CATEGORY_REVIEW_REQUIRED,
    CANDIDATE_LABEL_STATUS_PROPOSED,
    DISCOVERY_STATUS_DISCOVERED,
    DISCOVERY_STATUS_NO_EFFECTS,
    DISCOVERY_STATUS_REVIEW_REQUIRED,
    SOURCE_EFFECT_GOLDEN_VERSION,
    is_descriptive_negative_text,
)
from app.source_effect_partial_resolution import resolve_partial_source_effects_for_tender
from app.source_effect_resolution import resolve_effective_sources_for_tender
from app.source_effects import (
    SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
    SOURCE_EFFECT_SCOPE_PARTIAL,
    SOURCE_EFFECT_SCOPE_UNRESOLVED,
    SOURCE_EFFECT_TYPE_AMENDS,
    SOURCE_EFFECT_TYPE_CLARIFIES,
    SOURCE_EFFECT_TYPE_CORRECTS,
    SOURCE_EFFECT_TYPE_REVOKES,
    SOURCE_EFFECT_TYPE_SUPERSEDES,
    SOURCE_EFFECT_TYPE_SUPPLEMENTS,
)

KEYWORD_PATTERN = re.compile(
    r"sustituye|reemplaza|modifica|corrige|aclara|complementa|adiciona|queda\s+sin\s+efecto|deja\s+sin\s+efecto|revoca|adenda|aclaraci[oó]n",
    re.IGNORECASE,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _excerpt_around_keyword(text: str) -> tuple[str, int, int] | None:
    match = KEYWORD_PATTERN.search(text)
    if not match:
        return None
    start = max(0, match.start() - 180)
    end = min(len(text), match.end() + 220)
    excerpt = text[start:end].strip()
    return excerpt, start, end


def _discovery_status_from_deterministic(status: str) -> str:
    mapping = {
        "MATERIALIZED": DISCOVERY_STATUS_DISCOVERED,
        "NO_EFFECTS": DISCOVERY_STATUS_NO_EFFECTS,
        "REVIEW_REQUIRED": DISCOVERY_STATUS_REVIEW_REQUIRED,
        "UNSUPPORTED": "UNSUPPORTED",
        "INVALID_EVIDENCE": "INVALID_OUTPUT",
    }
    return mapping.get(status, "INVALID_OUTPUT")


def _build_source_locator(base_locator: str, source_method: str, start: int, end: int, page_number: int) -> str:
    if source_method == "NATIVE":
        return f"page_{page_number}_native|chars_{start}-{end}"
    if source_method == "OCR":
        return f"page_{page_number}_ocr|chars_{start}-{end}"
    return f"page_{page_number}_vision|chars_{start}-{end}"


def _expected_effect_payload(candidate) -> dict[str, object]:
    return {
        "expected_effect_type": candidate.effect_type,
        "expected_effect_scope": candidate.effect_scope,
        "expected_affected_document_ref_raw": candidate.affected_document_ref_raw,
        "expected_affected_document_id": candidate.affected_document_id,
        "expected_affected_locator_raw": candidate.affected_locator_raw,
        "expected_effective_date_raw": candidate.effective_date_raw,
        "expected_review_required": bool(candidate.review_required),
    }


def _iter_active_artifacts(db, tender_id: str) -> Iterable[tuple[TenderDocument, object]]:
    docs = db.execute(
        select(TenderDocument)
        .where(TenderDocument.tender_id == tender_id, TenderDocument.is_current.is_(True))
        .order_by(TenderDocument.original_filename.asc())
    ).scalars().all()

    for doc in docs:
        pages = db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.page_number.asc())
        ).scalars().all()
        enumerated = enumerate_source_effect_evidence_for_document(
            db,
            tender_id=tender_id,
            document_id=doc.id,
            pages=pages,
        )
        for item in enumerated.active:
            yield doc, item


def _build_real_candidate_cases(db, tender_id: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    positives: list[dict[str, object]] = []
    hard_negatives: list[dict[str, object]] = []
    descriptive_negatives: list[dict[str, object]] = []
    review_cases: list[dict[str, object]] = []

    dedupe_keys: set[str] = set()

    for doc, item in _iter_active_artifacts(db, tender_id):
        artifact = item.artifact
        result = discover_source_effects_from_evidence(db, artifact)
        discovery_status = _discovery_status_from_deterministic(result.status)

        if result.candidates:
            excerpt = result.candidates[0].source_excerpt.strip()
            if not excerpt:
                continue
            key = f"{artifact.source_artifact_key}|positive|{excerpt[:120]}"
            if key in dedupe_keys:
                continue
            dedupe_keys.add(key)
            positives.append(
                {
                    "acting_document_filename": doc.original_filename,
                    "acting_document_id": artifact.acting_document_id,
                    "document_page_id": artifact.document_page_id,
                    "source_method": artifact.source_method,
                    "source_artifact_key": artifact.source_artifact_key,
                    "source_locator": artifact.source_locator,
                    "source_excerpt": excerpt,
                    "source_excerpt_sha256": _sha256(excerpt),
                    "candidate_label_status": CANDIDATE_LABEL_STATUS_PROPOSED,
                    "expected_discovery_status": discovery_status,
                    "expected_effects": [_expected_effect_payload(candidate) for candidate in result.candidates],
                    "expected_review_required": any(bool(candidate.review_required) for candidate in result.candidates),
                    "category": CASE_CATEGORY_POSITIVE,
                    "human_note": "Propuesta automática basada en evidencia persistida. Requiere aprobación humana.",
                    "evidence_note": "; ".join(result.diagnostics) if result.diagnostics else "",
                    "page_number": artifact.page_number,
                }
            )
            continue

        keyword_match = _excerpt_around_keyword(artifact.source_text)

        if discovery_status == DISCOVERY_STATUS_REVIEW_REQUIRED:
            excerpt = (keyword_match[0] if keyword_match else artifact.source_text[:420]).strip()
            start = keyword_match[1] if keyword_match else 0
            end = keyword_match[2] if keyword_match else min(len(artifact.source_text), 420)
            key = f"{artifact.source_artifact_key}|review|{start}|{end}"
            if key in dedupe_keys:
                continue
            dedupe_keys.add(key)
            review_cases.append(
                {
                    "acting_document_filename": doc.original_filename,
                    "acting_document_id": artifact.acting_document_id,
                    "document_page_id": artifact.document_page_id,
                    "source_method": artifact.source_method,
                    "source_artifact_key": artifact.source_artifact_key,
                    "source_locator": _build_source_locator(artifact.source_locator, artifact.source_method, start, end, artifact.page_number),
                    "source_excerpt": excerpt,
                    "source_excerpt_sha256": _sha256(excerpt),
                    "candidate_label_status": CANDIDATE_LABEL_STATUS_PROPOSED,
                    "expected_discovery_status": DISCOVERY_STATUS_REVIEW_REQUIRED,
                    "expected_effects": [],
                    "expected_review_required": True,
                    "category": CASE_CATEGORY_REVIEW_REQUIRED,
                    "human_note": "Evidencia con lenguaje potencial de versionado sin contexto mínimo de objetivo. Mantener en revisión.",
                    "evidence_note": "; ".join(result.diagnostics) if result.diagnostics else "",
                    "page_number": artifact.page_number,
                }
            )
            continue

        if keyword_match and discovery_status == DISCOVERY_STATUS_NO_EFFECTS:
            excerpt, start, end = keyword_match
            category = CASE_CATEGORY_DESCRIPTIVE_NEGATIVE if is_descriptive_negative_text(excerpt) else CASE_CATEGORY_HARD_NEGATIVE
            key = f"{artifact.source_artifact_key}|{category}|{start}|{end}"
            if key in dedupe_keys:
                continue
            dedupe_keys.add(key)
            payload = {
                "acting_document_filename": doc.original_filename,
                "acting_document_id": artifact.acting_document_id,
                "document_page_id": artifact.document_page_id,
                "source_method": artifact.source_method,
                "source_artifact_key": artifact.source_artifact_key,
                "source_locator": _build_source_locator(artifact.source_locator, artifact.source_method, start, end, artifact.page_number),
                "source_excerpt": excerpt,
                "source_excerpt_sha256": _sha256(excerpt),
                "candidate_label_status": CANDIDATE_LABEL_STATUS_PROPOSED,
                "expected_discovery_status": DISCOVERY_STATUS_NO_EFFECTS,
                "expected_effects": [],
                "expected_review_required": False,
                "category": category,
                "human_note": "Texto real del expediente con palabras potencialmente confusas pero sin efecto operativo de versionado.",
                "evidence_note": "Negativo de seguridad para evitar falsos positivos.",
                "page_number": artifact.page_number,
            }
            if category == CASE_CATEGORY_DESCRIPTIVE_NEGATIVE:
                descriptive_negatives.append(payload)
            else:
                hard_negatives.append(payload)

    selected = []
    selected.extend(positives[:8])
    selected.extend(review_cases[:6])
    selected.extend(hard_negatives[:8])
    selected.extend(descriptive_negatives[:8])

    selected.sort(key=lambda item: (item["acting_document_filename"], int(item["page_number"]), item["source_method"], item["source_locator"]))

    cases: list[dict[str, object]] = []
    for index, item in enumerate(selected, start=1):
        case = {
            "case_id": f"se_gc_{index:03d}",
            "tender_id": tender_id,
            "acting_document_id": item["acting_document_id"],
            "document_page_id": item["document_page_id"],
            "source_method": item["source_method"],
            "source_artifact_key": item["source_artifact_key"],
            "source_locator": item["source_locator"],
            "source_excerpt": item["source_excerpt"],
            "source_excerpt_sha256": item["source_excerpt_sha256"],
            "candidate_label_status": item["candidate_label_status"],
            "expected_discovery_status": item["expected_discovery_status"],
            "expected_effects": item["expected_effects"],
            "expected_review_required": item["expected_review_required"],
            "category": item["category"],
            "human_note": item["human_note"],
            "evidence_note": item["evidence_note"],
            "acting_document_filename": item["acting_document_filename"],
        }
        cases.append(case)

    expected_effect_types = {
        SOURCE_EFFECT_TYPE_SUPERSEDES,
        SOURCE_EFFECT_TYPE_REVOKES,
        SOURCE_EFFECT_TYPE_AMENDS,
        SOURCE_EFFECT_TYPE_CORRECTS,
        SOURCE_EFFECT_TYPE_CLARIFIES,
        SOURCE_EFFECT_TYPE_SUPPLEMENTS,
    }
    expected_effect_scopes = {
        SOURCE_EFFECT_SCOPE_DOCUMENT_WIDE,
        SOURCE_EFFECT_SCOPE_PARTIAL,
        SOURCE_EFFECT_SCOPE_UNRESOLVED,
    }

    observed_types: set[str] = set()
    observed_scopes: set[str] = set()
    for case in cases:
        for effect in case.get("expected_effects", []):
            effect_type = effect.get("expected_effect_type")
            effect_scope = effect.get("expected_effect_scope")
            if effect_type:
                observed_types.add(str(effect_type))
            if effect_scope:
                observed_scopes.add(str(effect_scope))

    summary = {
        "cases_total": len(cases),
        "proposed_positives": len([c for c in cases if c["category"] == CASE_CATEGORY_POSITIVE]),
        "hard_negatives": len([c for c in cases if c["category"] == CASE_CATEGORY_HARD_NEGATIVE]),
        "descriptive_negatives": len([c for c in cases if c["category"] == CASE_CATEGORY_DESCRIPTIVE_NEGATIVE]),
        "review_required_cases": len([c for c in cases if c["expected_review_required"]]),
        "expected_discovery_status_counts": dict(Counter(c["expected_discovery_status"] for c in cases)),
        "coverage_gap_effect_types": sorted(expected_effect_types - observed_types),
        "coverage_gap_effect_scopes": sorted(expected_effect_scopes - observed_scopes),
        "coverage_notes": "Dataset candidato basado solo en evidencia persistida; sin ejecución de modelo semántico.",
    }

    return cases, summary


def _snapshot_versioning_state(db, tender_id: str) -> dict[str, object]:
    document_resolution = resolve_effective_sources_for_tender(db, tender_id=tender_id)
    partial_resolution = resolve_partial_source_effects_for_tender(db, tender_id=tender_id)
    projection = project_effective_sources_for_tender(db, tender_id=tender_id)

    snapshot = {
        "tender_id": tender_id,
        "document_resolution": {
            "status": document_resolution.status,
            "document_status_counts": dict(Counter(item.status for item in document_resolution.documents)),
            "unresolved_effects_count": len(document_resolution.unresolved_effects),
            "conflicts_count": len(document_resolution.conflicts),
            "review_required_documents": sum(1 for item in document_resolution.documents if item.status == "REVIEW_REQUIRED"),
        },
        "partial_resolution": {
            "status": partial_resolution.status,
            "locator_status_counts": dict(Counter(item.status for item in partial_resolution.locators)),
            "unresolved_effects_count": len(partial_resolution.unresolved_effects),
            "conflicts_count": len(partial_resolution.conflicts),
            "review_required_locators": sum(1 for item in partial_resolution.locators if item.status == "REVIEW_REQUIRED"),
        },
        "effective_projection": {
            "status": projection.status,
            "requirement_status_counts": dict(Counter(item.status for item in projection.requirements)),
            "scope_detail_status_counts": dict(Counter(item.status for item in projection.scope_details)),
            "attribute_status_counts": dict(Counter(item.status for item in projection.scope_attributes)),
            "quantity_status_counts": dict(Counter(item.status for item in projection.scope_quantities)),
            "diagnostic_count": len(projection.diagnostics),
            "review_required_entities": (
                sum(1 for item in projection.requirements if item.status == "REVIEW_REQUIRED")
                + sum(1 for item in projection.scope_details if item.status == "REVIEW_REQUIRED")
                + sum(1 for item in projection.scope_attributes if item.status == "REVIEW_REQUIRED")
                + sum(1 for item in projection.scope_quantities if item.status == "REVIEW_REQUIRED")
            ),
        },
    }
    return snapshot


def _render_review_pack(cases: list[dict[str, object]], tender_id: str) -> str:
    lines: list[str] = []
    lines.append("# SOURCE EFFECT GOLDEN CANDIDATE REVIEW PACK")
    lines.append("")
    lines.append("Este documento contiene etiquetas PROPUESTAS para revisión humana.")
    lines.append("No hay etiquetas aprobadas, congeladas ni finales en este paquete.")
    lines.append("")
    lines.append(f"Tender: {tender_id}")
    lines.append(f"Fecha de generación: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    for case in cases:
        lines.append(f"## {case['case_id']}")
        lines.append("")
        lines.append(f"- Documento origen: {case['acting_document_filename']} ({case['acting_document_id']})")
        lines.append(f"- Página/Locator: {case['source_locator']}")
        lines.append(f"- Método fuente: {case['source_method']}")
        lines.append(f"- Artifact key: {case['source_artifact_key']}")
        lines.append(f"- Categoría: {case['category']}")
        lines.append(f"- candidate_label_status: {case['candidate_label_status']}")
        lines.append(f"- expected_discovery_status: {case['expected_discovery_status']}")
        lines.append(f"- expected_review_required: {case['expected_review_required']}")
        lines.append(f"- Motivo: {case['human_note'] or ''}")
        lines.append(f"- Nota de evidencia: {case['evidence_note'] or ''}")
        lines.append("")
        lines.append("### Extracto literal")
        lines.append("")
        lines.append(case["source_excerpt"])
        lines.append("")

        if case["expected_effects"]:
            lines.append("### Efectos esperados propuestos")
            lines.append("")
            for effect in case["expected_effects"]:
                lines.append(f"- effect_type: {effect.get('expected_effect_type')}")
                lines.append(f"- effect_scope: {effect.get('expected_effect_scope')}")
                lines.append(f"- affected_document_ref_raw: {effect.get('expected_affected_document_ref_raw')}")
                lines.append(f"- affected_document_id: {effect.get('expected_affected_document_id')}")
                lines.append(f"- affected_locator_raw: {effect.get('expected_affected_locator_raw')}")
                lines.append(f"- effective_date_raw: {effect.get('expected_effective_date_raw')}")
                lines.append(f"- expected_review_required: {effect.get('expected_review_required')}")
            lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Source Effect Golden candidate pack and snapshots")
    parser.add_argument("--tender-id", required=True)
    parser.add_argument("--output-json", default="evals/source_effect_golden_candidate_t001_v1.json")
    parser.add_argument("--output-review", default="reports/source_effect_golden_candidate_review_pack_t001.md")
    parser.add_argument("--output-snapshot", default="reports/source_effect_versioning_snapshot_t001.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    backend_root = BACKEND_ROOT
    output_json = backend_root / args.output_json
    output_review = backend_root / args.output_review
    output_snapshot = backend_root / args.output_snapshot

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_review.parent.mkdir(parents=True, exist_ok=True)
    output_snapshot.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        cases, summary = _build_real_candidate_cases(db, args.tender_id)
        snapshot = _snapshot_versioning_state(db, args.tender_id)

    payload = {
        "golden_version": SOURCE_EFFECT_GOLDEN_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tender_id": args.tender_id,
        "notes": "UNAPPROVED GOLDEN CANDIDATE METRIC dataset. Todas las etiquetas son PROPOSED.",
        "candidate_schema": {
            "case_id": "str",
            "tender_id": "str",
            "acting_document_id": "str",
            "document_page_id": "str|null",
            "source_method": "str",
            "source_artifact_key": "str",
            "source_locator": "str",
            "source_excerpt": "str",
            "source_excerpt_sha256": "str",
            "candidate_label_status": "PROPOSED|APPROVED",
            "expected_discovery_status": "DISCOVERED|NO_EFFECTS|REVIEW_REQUIRED|INVALID_OUTPUT|UNSUPPORTED",
            "expected_effects": "list[expected effect payload]",
            "expected_review_required": "bool",
            "human_note": "str|null",
            "evidence_note": "str|null",
        },
        "summary": summary,
        "cases": cases,
    }

    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    output_review.write_text(_render_review_pack(cases, args.tender_id), encoding="utf-8")

    print(f"written_json={output_json}")
    print(f"written_review={output_review}")
    print(f"written_snapshot={output_snapshot}")
    print(f"cases_total={summary['cases_total']}")
    print(f"proposed_positives={summary['proposed_positives']}")
    print(f"hard_negatives={summary['hard_negatives']}")
    print(f"descriptive_negatives={summary['descriptive_negatives']}")
    print(f"review_required_cases={summary['review_required_cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
