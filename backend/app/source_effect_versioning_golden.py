from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect

from app.database import SessionLocal
from app.effective_source_projection import (
    ENTITY_TYPE_REQUIREMENT,
    ENTITY_TYPE_SCOPE_ATTRIBUTE,
    ENTITY_TYPE_SCOPE_DETAIL,
    ENTITY_TYPE_SCOPE_QUANTITY,
    project_effective_sources_for_tender,
)
from app.main import app
from app.models import (
    DocumentPage,
    Requirement,
    RequirementCandidate,
    RequirementCandidateLink,
    RequirementReview,
    TenderDocument,
    TenderScopeAttribute,
    TenderScopeDetail,
    TenderScopeQuantity,
    TenderSourceEffect,
)
from app.source_effect_partial_resolution import (
    normalize_partial_locator_identity,
    resolve_partial_source_effects_for_tender,
)
from app.source_effect_resolution import resolve_effective_sources_for_tender
from app.source_effects import SourceEffectCandidate, replace_source_effects_for_artifact

DATASET_KIND_CONTROLLED_SYNTHETIC_VERSIONING = "CONTROLLED_SYNTHETIC_VERSIONING"
DATASET_STATUS_FROZEN_CONTRACT_VALIDATION = "FROZEN_CONTRACT_VALIDATION"

RESOLVER_LAYER_DOCUMENT = "DOCUMENT"
RESOLVER_LAYER_PARTIAL = "PARTIAL"
RESOLVER_LAYER_PROJECTION = "PROJECTION"
RESOLVER_LAYER_DETERMINISM = "DETERMINISM"

ALLOWED_RESOLVER_LAYERS = {
    RESOLVER_LAYER_DOCUMENT,
    RESOLVER_LAYER_PARTIAL,
    RESOLVER_LAYER_PROJECTION,
    RESOLVER_LAYER_DETERMINISM,
}

REQUIRED_CASE_IDS = {
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "D07",
    "D08",
    "D09",
    "D10",
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "G01",
    "G02",
    "X01",
    "X02",
    "X03",
    "X04",
    "X05",
    "X06",
    "X07",
}

client = TestClient(app)


@dataclass(frozen=True, slots=True)
class SourceEffectVersioningGoldenCase:
    case_id: str
    title: str
    resolver_layers: tuple[str, ...]
    effect_types: tuple[str, ...]
    effect_scopes: tuple[str, ...]
    tags: tuple[str, ...]
    fixture_alias: str
    expected_alias: str


@dataclass(frozen=True, slots=True)
class SourceEffectVersioningGoldenDataset:
    golden_version: str
    dataset_kind: str
    dataset_status: str
    certifies: tuple[str, ...]
    does_not_certify: tuple[str, ...]
    cases: tuple[SourceEffectVersioningGoldenCase, ...]


@dataclass(frozen=True, slots=True)
class SourceEffectVersioningCaseResult:
    case_id: str
    passed: bool
    checks_total: int
    checks_passed: int
    checks_failed: int
    read_only_verified: bool
    failure_messages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceEffectVersioningGoldenRunResult:
    dataset_kind: str
    dataset_status: str
    cases_total: int
    cases_passed: int
    cases_failed: int
    case_results: tuple[SourceEffectVersioningCaseResult, ...]
    coverage_effect_type: dict[str, int]
    coverage_effect_scope: dict[str, int]
    coverage_resolver_layer: dict[str, int]
    conflict_case_count: int
    projection_case_count: int


@dataclass(frozen=True, slots=True)
class _EffectSpec:
    alias: str
    acting: str
    effect_type: str
    effect_scope: str
    affected: str | None
    locator: str | None = None
    review_required: bool = False


@dataclass(frozen=True, slots=True)
class _EntitySpec:
    alias: str
    entity_type: str
    source_document: str
    source_locator: str | None
    parent_alias: str | None = None
    review_required: bool = False


@dataclass(frozen=True, slots=True)
class _Scenario:
    docs: tuple[str, ...]
    effects: tuple[_EffectSpec, ...]
    entities: tuple[_EntitySpec, ...]
    checks: tuple[dict[str, Any], ...]


def load_source_effect_versioning_golden(path: str | Path) -> SourceEffectVersioningGoldenDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    cases = []
    for item in payload.get("cases", []):
        cases.append(
            SourceEffectVersioningGoldenCase(
                case_id=str(item["case_id"]),
                title=str(item.get("title", item["case_id"])),
                resolver_layers=tuple(item.get("resolver_layers", [])),
                effect_types=tuple(item.get("effect_types", [])),
                effect_scopes=tuple(item.get("effect_scopes", [])),
                tags=tuple(item.get("tags", [])),
                fixture_alias=str(item.get("fixture_alias", "")),
                expected_alias=str(item.get("expected_alias", "")),
            )
        )

    return SourceEffectVersioningGoldenDataset(
        golden_version=str(payload.get("golden_version", "")),
        dataset_kind=str(payload.get("dataset_kind", "")),
        dataset_status=str(payload.get("dataset_status", "")),
        certifies=tuple(payload.get("certifies", [])),
        does_not_certify=tuple(payload.get("does_not_certify", [])),
        cases=tuple(cases),
    )


def validate_source_effect_versioning_golden(
    dataset: SourceEffectVersioningGoldenDataset,
) -> tuple[str, ...]:
    errors: list[str] = []

    if dataset.dataset_kind != DATASET_KIND_CONTROLLED_SYNTHETIC_VERSIONING:
        errors.append(
            "dataset_kind invalido: "
            f"{dataset.dataset_kind} (esperado={DATASET_KIND_CONTROLLED_SYNTHETIC_VERSIONING})"
        )
    if dataset.dataset_status != DATASET_STATUS_FROZEN_CONTRACT_VALIDATION:
        errors.append(
            "dataset_status invalido: "
            f"{dataset.dataset_status} (esperado={DATASET_STATUS_FROZEN_CONTRACT_VALIDATION})"
        )

    case_ids: set[str] = set()
    for case in dataset.cases:
        if case.case_id in case_ids:
            errors.append(f"case_id duplicado: {case.case_id}")
        case_ids.add(case.case_id)

        bad_layers = sorted(set(case.resolver_layers) - ALLOWED_RESOLVER_LAYERS)
        if bad_layers:
            errors.append(f"case:{case.case_id}:resolver_layers invalidos={bad_layers}")

        if not case.fixture_alias:
            errors.append(f"case:{case.case_id}:fixture_alias vacio")
        if not case.expected_alias:
            errors.append(f"case:{case.case_id}:expected_alias vacio")
        if case.fixture_alias != case.case_id:
            errors.append(f"case:{case.case_id}:fixture_alias debe igualar case_id")
        if case.expected_alias != case.case_id:
            errors.append(f"case:{case.case_id}:expected_alias debe igualar case_id")

    missing_required = sorted(REQUIRED_CASE_IDS - case_ids)
    if missing_required:
        errors.append(f"faltan casos requeridos={missing_required}")

    extra_case_ids = sorted(case_ids - REQUIRED_CASE_IDS)
    if extra_case_ids:
        errors.append(f"casos extra no permitidos={extra_case_ids}")

    return tuple(errors)


def compute_versioning_coverage(
    dataset: SourceEffectVersioningGoldenDataset,
) -> tuple[dict[str, int], dict[str, int], dict[str, int], int, int]:
    effect_type: dict[str, int] = {}
    effect_scope: dict[str, int] = {}
    resolver_layer: dict[str, int] = {}
    conflict_case_count = 0
    projection_case_count = 0

    for case in dataset.cases:
        for value in set(case.effect_types):
            effect_type[value] = effect_type.get(value, 0) + 1
        for value in set(case.effect_scopes):
            effect_scope[value] = effect_scope.get(value, 0) + 1
        for value in set(case.resolver_layers):
            resolver_layer[value] = resolver_layer.get(value, 0) + 1

        tags = set(case.tags)
        if "CONFLICT" in tags or "CYCLE" in tags:
            conflict_case_count += 1
        if "PROJECTION" in tags:
            projection_case_count += 1

    return effect_type, effect_scope, resolver_layer, conflict_case_count, projection_case_count


def run_source_effect_versioning_golden(
    *,
    dataset: SourceEffectVersioningGoldenDataset,
    python_executable: str,
    backend_root: Path,
    database_url: str,
) -> SourceEffectVersioningGoldenRunResult:
    del python_executable
    del backend_root

    if "licitia_test" not in database_url:
        raise ValueError("database_url must target licitia_test")
    os.environ["DATABASE_URL"] = database_url

    case_results: list[SourceEffectVersioningCaseResult] = []
    for case in dataset.cases:
        if case.case_id == "G02":
            case_results.append(_run_g02_case(case.case_id))
            continue

        scenario = _scenario_for_case(case.case_id)
        case_results.append(_run_standard_case(case.case_id, scenario))

    cases_total = len(case_results)
    cases_passed = sum(1 for item in case_results if item.passed)
    cases_failed = cases_total - cases_passed

    coverage_effect_type, coverage_effect_scope, coverage_resolver_layer, conflict_case_count, projection_case_count = (
        compute_versioning_coverage(dataset)
    )

    return SourceEffectVersioningGoldenRunResult(
        dataset_kind=dataset.dataset_kind,
        dataset_status=dataset.dataset_status,
        cases_total=cases_total,
        cases_passed=cases_passed,
        cases_failed=cases_failed,
        case_results=tuple(case_results),
        coverage_effect_type=coverage_effect_type,
        coverage_effect_scope=coverage_effect_scope,
        coverage_resolver_layer=coverage_resolver_layer,
        conflict_case_count=conflict_case_count,
        projection_case_count=projection_case_count,
    )


def _run_g02_case(case_id: str) -> SourceEffectVersioningCaseResult:
    scenario = _scenario_for_case(case_id)
    normal = _execute_case_fixture(case_id=case_id, scenario=scenario, reverse_effect_order=False)
    reversed_run = _execute_case_fixture(case_id=case_id, scenario=scenario, reverse_effect_order=True)

    failures: list[str] = []
    if not normal["read_only_verified"]:
        failures.append("read_only verification failed (normal order)")
    if not reversed_run["read_only_verified"]:
        failures.append("read_only verification failed (reversed order)")

    if normal["normalized"] != reversed_run["normalized"]:
        failures.append("normalized outputs differ between insertion orders")

    passed = not failures
    checks_total = 3
    checks_failed = len(failures)
    checks_passed = checks_total - checks_failed

    return SourceEffectVersioningCaseResult(
        case_id=case_id,
        passed=passed,
        checks_total=checks_total,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        read_only_verified=normal["read_only_verified"] and reversed_run["read_only_verified"],
        failure_messages=tuple(failures),
    )


def _run_standard_case(case_id: str, scenario: _Scenario) -> SourceEffectVersioningCaseResult:
    execution = _execute_case_fixture(case_id=case_id, scenario=scenario, reverse_effect_order=False)
    normalized = execution["normalized"]
    failures = list(_evaluate_checks(normalized, scenario.checks))
    if not execution["read_only_verified"]:
        failures.append("read_only verification failed")

    checks_total = len(scenario.checks) + 1
    checks_failed = len(failures)
    checks_passed = checks_total - checks_failed

    return SourceEffectVersioningCaseResult(
        case_id=case_id,
        passed=(checks_failed == 0),
        checks_total=checks_total,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        read_only_verified=bool(execution["read_only_verified"]),
        failure_messages=tuple(failures),
    )


def _execute_case_fixture(*, case_id: str, scenario: _Scenario, reverse_effect_order: bool) -> dict[str, Any]:
    tender_id = _create_tender(f"versioning-golden-{case_id}")

    db = SessionLocal()
    try:
        doc_ids, pages = _prepare_docs(db, tender_id, scenario.docs)
        effect_id_by_alias: dict[str, str] = {}

        effects = list(scenario.effects)
        if reverse_effect_order:
            effects = list(reversed(effects))

        for index, effect in enumerate(effects, start=1):
            effect_id = _persist_effect(
                db,
                tender_id=tender_id,
                acting_document_id=doc_ids[effect.acting],
                document_page_id=pages[effect.acting].id,
                effect_type=effect.effect_type,
                effect_scope=effect.effect_scope,
                affected_document_id=(doc_ids[effect.affected] if effect.affected is not None else None),
                effect_index=index,
                review_required=effect.review_required,
                affected_locator_raw=effect.locator,
            )
            effect_id_by_alias[effect.alias] = effect_id

        entity_id_by_alias = _create_entities_for_scenario(
            db,
            tender_id=tender_id,
            pages=pages,
            doc_ids=doc_ids,
            entities=scenario.entities,
        )
        db.commit()

        snapshot_before = _snapshot_state(db, tender_id=tender_id)

        document_resolution = resolve_effective_sources_for_tender(db, tender_id=tender_id)
        partial_resolution = resolve_partial_source_effects_for_tender(
            db,
            tender_id=tender_id,
            document_resolution=document_resolution,
        )
        projection = project_effective_sources_for_tender(
            db,
            tender_id=tender_id,
            document_resolution=document_resolution,
            partial_resolution=partial_resolution,
        )

        snapshot_after = _snapshot_state(db, tender_id=tender_id)
        read_only_verified = snapshot_before == snapshot_after

        return {
            "read_only_verified": read_only_verified,
            "normalized": _normalize_outputs(
                document_resolution=document_resolution,
                partial_resolution=partial_resolution,
                projection=projection,
                doc_ids=doc_ids,
                effect_id_by_alias=effect_id_by_alias,
                entity_id_by_alias=entity_id_by_alias,
            ),
        }
    finally:
        db.close()


def _normalize_outputs(
    *,
    document_resolution: Any,
    partial_resolution: Any,
    projection: Any,
    doc_ids: dict[str, str],
    effect_id_by_alias: dict[str, str],
    entity_id_by_alias: dict[str, str],
) -> dict[str, Any]:
    doc_name_by_id = {value: key for key, value in doc_ids.items()}
    effect_alias_by_id = {value: key for key, value in effect_id_by_alias.items()}

    document_items: dict[str, dict[str, Any]] = {}
    for item in document_resolution.documents:
        alias = doc_name_by_id[item.document_id]
        document_items[alias] = {
            "status": item.status,
            "replacement": (doc_name_by_id.get(item.effective_replacement_document_id) if item.effective_replacement_document_id else None),
            "blocking_effect_aliases": sorted(
                effect_alias_by_id[row]
                for row in item.blocking_effect_ids
                if row in effect_alias_by_id
            ),
            "diagnostic_codes": sorted({diag.code for diag in item.diagnostics}),
        }

    partial_items: dict[str, dict[str, Any]] = {}
    for item in partial_resolution.locators:
        doc_alias = doc_name_by_id[item.affected_document_id]
        key = f"{doc_alias}|{item.locator_identity}"
        partial_items[key] = {
            "status": item.status,
            "effective_source": doc_name_by_id.get(item.effective_source_document_id) if item.effective_source_document_id else None,
            "blocking_effect_aliases": sorted(
                effect_alias_by_id[row]
                for row in item.blocking_effect_ids
                if row in effect_alias_by_id
            ),
            "diagnostic_codes": sorted({diag.code for diag in item.diagnostics}),
        }

    entity_alias_by_id = {value: key for key, value in entity_id_by_alias.items()}

    projection_items: dict[str, dict[str, Any]] = {}
    all_entities = list(projection.requirements) + list(projection.scope_details) + list(projection.scope_attributes) + list(projection.scope_quantities)
    for item in all_entities:
        alias = entity_alias_by_id.get(item.entity_id)
        if alias is None:
            continue
        projection_items[alias] = {
            "status": item.status,
            "supporting_effect_aliases": sorted(
                effect_alias_by_id[row]
                for row in item.supporting_effect_ids
                if row in effect_alias_by_id
            ),
            "blocking_effect_aliases": sorted(
                effect_alias_by_id[row]
                for row in item.blocking_effect_ids
                if row in effect_alias_by_id
            ),
            "diagnostic_codes": sorted({diag.code for diag in item.diagnostics}),
        }

    return {
        "document_tender_status": document_resolution.status,
        "document_diagnostic_codes": sorted({diag.code for diag in document_resolution.diagnostics}),
        "documents": document_items,
        "partial_tender_status": partial_resolution.status,
        "partial_diagnostic_codes": sorted({diag.code for diag in partial_resolution.diagnostics}),
        "partial_locators": partial_items,
        "projection_tender_status": projection.status,
        "projection_diagnostic_codes": sorted({diag.code for diag in projection.diagnostics}),
        "projection_entities": projection_items,
    }


def _evaluate_checks(normalized: dict[str, Any], checks: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    failures: list[str] = []

    for check in checks:
        op = check["op"]

        if op == "document_tender_status":
            if normalized["document_tender_status"] != check["value"]:
                failures.append(f"document_tender_status expected={check['value']} got={normalized['document_tender_status']}")
            continue

        if op == "doc_status":
            alias = check["doc"]
            actual = normalized["documents"].get(alias, {}).get("status")
            if actual != check["value"]:
                failures.append(f"doc_status {alias} expected={check['value']} got={actual}")
            continue

        if op == "doc_replacement":
            alias = check["doc"]
            actual = normalized["documents"].get(alias, {}).get("replacement")
            if actual != check.get("value"):
                failures.append(f"doc_replacement {alias} expected={check.get('value')} got={actual}")
            continue

        if op == "doc_block_count":
            alias = check["doc"]
            actual = len(normalized["documents"].get(alias, {}).get("blocking_effect_aliases", []))
            if actual != check["value"]:
                failures.append(f"doc_block_count {alias} expected={check['value']} got={actual}")
            continue

        if op == "doc_has_diag":
            alias = check["doc"]
            codes = normalized["documents"].get(alias, {}).get("diagnostic_codes", [])
            if check["value"] not in codes:
                failures.append(f"doc_has_diag {alias} missing={check['value']} got={codes}")
            continue

        if op == "partial_tender_status":
            if normalized["partial_tender_status"] != check["value"]:
                failures.append(f"partial_tender_status expected={check['value']} got={normalized['partial_tender_status']}")
            continue

        if op == "partial_status":
            key = f"{check['doc']}|{normalize_partial_locator_identity(check['locator'])}"
            actual = normalized["partial_locators"].get(key, {}).get("status")
            if actual != check["value"]:
                failures.append(f"partial_status {key} expected={check['value']} got={actual}")
            continue

        if op == "partial_effective_source":
            key = f"{check['doc']}|{normalize_partial_locator_identity(check['locator'])}"
            actual = normalized["partial_locators"].get(key, {}).get("effective_source")
            if actual != check.get("value"):
                failures.append(f"partial_effective_source {key} expected={check.get('value')} got={actual}")
            continue

        if op == "partial_has_diag":
            key = f"{check['doc']}|{normalize_partial_locator_identity(check['locator'])}"
            codes = normalized["partial_locators"].get(key, {}).get("diagnostic_codes", [])
            if check["value"] not in codes:
                failures.append(f"partial_has_diag {key} missing={check['value']} got={codes}")
            continue

        if op == "projection_tender_status":
            if normalized["projection_tender_status"] != check["value"]:
                failures.append(f"projection_tender_status expected={check['value']} got={normalized['projection_tender_status']}")
            continue

        if op == "projection_status":
            alias = check["entity"]
            actual = normalized["projection_entities"].get(alias, {}).get("status")
            if actual != check["value"]:
                failures.append(f"projection_status {alias} expected={check['value']} got={actual}")
            continue

        if op == "projection_supports":
            alias = check["entity"]
            values = normalized["projection_entities"].get(alias, {}).get("supporting_effect_aliases", [])
            if check["value"] not in values:
                failures.append(f"projection_supports {alias} missing={check['value']} got={values}")
            continue

        if op == "projection_blocks":
            alias = check["entity"]
            values = normalized["projection_entities"].get(alias, {}).get("blocking_effect_aliases", [])
            if check["value"] not in values:
                failures.append(f"projection_blocks {alias} missing={check['value']} got={values}")
            continue

        if op == "projection_has_diag":
            alias = check["entity"]
            codes = normalized["projection_entities"].get(alias, {}).get("diagnostic_codes", [])
            if check["value"] not in codes:
                failures.append(f"projection_has_diag {alias} missing={check['value']} got={codes}")
            continue

        failures.append(f"unsupported_check_op={op}")

    return tuple(failures)


def _create_tender(title: str) -> str:
    response = client.post(
        "/tenders",
        json={
            "title": title,
            "institution_profile": "General",
            "external_reference": f"SRC-EFF-VERSIONING-{uuid4()}",
        },
    )
    if response.status_code != 201:
        raise RuntimeError(f"unable to create tender: status={response.status_code} body={response.text}")
    return response.json()["id"]


def _import_pdf(tender_id: str, filename: str) -> str:
    payload = f"%PDF-1.4\\n1 0 obj\\n<< /Title ({filename}) >>\\nendobj\\n%%EOF\\n".encode("utf-8")
    response = client.post(
        f"/tenders/{tender_id}/documents/import",
        files=[("files", (filename, payload, "application/pdf"))],
        data={"source_relative_paths": f"fixture/{filename}"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"unable to import document: status={response.status_code} body={response.text}")
    return response.json()[0]["document_id"]


def _seed_page(db: Any, document_id: str, page_number: int, text: str) -> DocumentPage:
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
    if document is None:
        raise RuntimeError("unable to fetch seeded document")
    document.page_count = max(document.page_count, page_number)
    document.processing_status = "TEXT_EXTRACTION_COMPLETE"
    return page


def _prepare_docs(db: Any, tender_id: str, names: tuple[str, ...]) -> tuple[dict[str, str], dict[str, DocumentPage]]:
    doc_ids: dict[str, str] = {}
    pages: dict[str, DocumentPage] = {}
    for name in names:
        doc_id = _import_pdf(tender_id, f"{name}.pdf")
        doc_ids[name] = doc_id
        pages[name] = _seed_page(db, doc_id, 1, f"Texto de {name}")
    db.commit()
    return doc_ids, pages


def _persist_effect(
    db: Any,
    *,
    tender_id: str,
    acting_document_id: str,
    document_page_id: str,
    effect_type: str,
    effect_scope: str,
    affected_document_id: str | None,
    effect_index: int,
    review_required: bool,
    affected_locator_raw: str | None,
) -> str:
    artifact_key = f"native-page:{document_page_id}:effect:{effect_index}"
    candidate = SourceEffectCandidate(
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        affected_document_id=affected_document_id,
        document_page_id=document_page_id,
        affected_document_page_id=None,
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=None,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=None,
        source_method="NATIVE",
        source_artifact_key=artifact_key,
        source_locator=f"page:1|effect:{effect_index}",
        source_excerpt=f"Efecto {effect_index}: {effect_type}",
        review_required=review_required,
        confidence=0.9,
        source_contract_version="source-effect-versioning-golden-001",
        source_analysis_id=None,
        source_page_result_id=None,
    )

    rows = replace_source_effects_for_artifact(
        db,
        tender_id=tender_id,
        acting_document_id=acting_document_id,
        document_page_id=document_page_id,
        source_artifact_key=artifact_key,
        candidates=[candidate],
    )
    if len(rows) != 1:
        raise RuntimeError("unexpected replace_source_effects_for_artifact cardinality")
    return rows[0].id


def _create_entities_for_scenario(
    db: Any,
    *,
    tender_id: str,
    pages: dict[str, DocumentPage],
    doc_ids: dict[str, str],
    entities: tuple[_EntitySpec, ...],
) -> dict[str, str]:
    entity_id_by_alias: dict[str, str] = {}

    for entity in entities:
        source_document_id = doc_ids.get(entity.source_document)
        source_page_id = pages.get(entity.source_document).id if entity.source_document in pages else None

        if entity.entity_type == ENTITY_TYPE_REQUIREMENT:
            entity_id_by_alias[entity.alias] = _create_requirement(
                db,
                tender_id=tender_id,
                source_document_id=source_document_id,
                document_page_id=source_page_id,
                source_locator=entity.source_locator,
                review_required=entity.review_required,
            )
            continue

        if source_document_id is None:
            raise RuntimeError(
                f"entity type {entity.entity_type} requires mapped source document alias: {entity.source_document}"
            )

        if entity.entity_type == ENTITY_TYPE_SCOPE_DETAIL:
            entity_id_by_alias[entity.alias] = _create_scope_detail(
                db,
                tender_id=tender_id,
                source_document_id=source_document_id,
                document_page_id=(source_page_id or next(iter(pages.values())).id),
                source_locator=(entity.source_locator or "loc"),
                review_required=entity.review_required,
            )
            continue

        if entity.entity_type == ENTITY_TYPE_SCOPE_ATTRIBUTE:
            parent = entity.parent_alias
            if parent is None or parent not in entity_id_by_alias:
                raise RuntimeError(f"scope attribute requires existing parent scope detail alias: {entity.alias}")
            entity_id_by_alias[entity.alias] = _create_scope_attribute(
                db,
                tender_id=tender_id,
                scope_detail_id=entity_id_by_alias[parent],
                source_document_id=source_document_id,
                document_page_id=(source_page_id or next(iter(pages.values())).id),
                source_locator=(entity.source_locator or "loc"),
                review_required=entity.review_required,
            )
            continue

        if entity.entity_type == ENTITY_TYPE_SCOPE_QUANTITY:
            parent = entity.parent_alias
            if parent is None or parent not in entity_id_by_alias:
                raise RuntimeError(f"scope quantity requires existing parent scope detail alias: {entity.alias}")
            entity_id_by_alias[entity.alias] = _create_scope_quantity(
                db,
                tender_id=tender_id,
                scope_detail_id=entity_id_by_alias[parent],
                source_document_id=source_document_id,
                document_page_id=(source_page_id or next(iter(pages.values())).id),
                source_locator=(entity.source_locator or "loc"),
                review_required=entity.review_required,
            )
            continue

        raise RuntimeError(f"unsupported entity type: {entity.entity_type}")

    db.flush()
    return entity_id_by_alias


def _create_requirement(
    db: Any,
    *,
    tender_id: str,
    source_document_id: str | None,
    document_page_id: str | None,
    source_locator: str | None,
    review_required: bool,
) -> str:
    requirement = Requirement(
        id=str(uuid4()),
        tender_id=tender_id,
        canonical_key=f"req-{uuid4()}",
        canonical_text="texto",
        category="TECHNICAL",
        normalization_status=("REVIEW_REQUIRED" if review_required else "NORMALIZED"),
        normalizer_version="golden",
        primary_candidate_id=None,
    )
    db.add(requirement)
    db.flush()

    if source_document_id is not None:
        candidate = RequirementCandidate(
            id=str(uuid4()),
            tender_id=tender_id,
            semantic_key=f"cand-{uuid4()}",
            requirement_text=source_locator or "req",
            source_document_id=source_document_id,
            source_page=1,
            source_excerpt=source_locator or "",
            document_page_id=document_page_id,
            review_status="CONFIRMED",
            detector_version="golden",
        )
        requirement.primary_candidate_id = candidate.id

        link = RequirementCandidateLink(
            requirement_id=requirement.id,
            requirement_candidate_id=candidate.id,
            is_primary_source=True,
            link_origin="DETERMINISTIC",
        )

        db.add(candidate)
        db.flush()
        db.add(link)

    if review_required:
        db.add(
            RequirementReview(
                tender_id=tender_id,
                requirement_id=requirement.id,
                review_status="NEEDS_REVIEW",
            )
        )

    db.flush()
    return requirement.id


def _create_scope_detail(
    db: Any,
    *,
    tender_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool,
) -> str:
    row = TenderScopeDetail(
        id=str(uuid4()),
        tender_id=tender_id,
        tender_item_id=None,
        scope_segment_id=None,
        candidate_item_key=None,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        domain="TECHNICAL",
        detail_type="ACTIVITY",
        description="detalle",
        normalized_label=None,
        applicability="APPLIES",
        source_method="NATIVE",
        source_artifact_key=f"detail:{uuid4()}",
        source_contract_version="golden",
        source_locator=source_locator,
        source_excerpt=source_locator,
        confidence=0.9,
        review_required=review_required,
        quantity_raw=None,
        unit_raw=None,
        semantic_fingerprint=f"fp-{uuid4()}",
    )
    db.add(row)
    db.flush()
    return row.id


def _create_scope_attribute(
    db: Any,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool,
) -> str:
    row = TenderScopeAttribute(
        id=str(uuid4()),
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        attribute_name="presion",
        attribute_label_raw="Presion",
        normalized_name="presion",
        value_raw="10",
        unit_raw="bar",
        relation="EXACT",
        source_method="NATIVE",
        source_artifact_key=f"attr:{uuid4()}",
        source_locator=source_locator,
        source_excerpt=source_locator,
        review_required=review_required,
        semantic_fingerprint=f"fp-{uuid4()}",
        confidence=0.9,
        source_contract_version="golden",
        source_analysis_id=None,
        source_page_result_id=None,
    )
    db.add(row)
    db.flush()
    return row.id


def _create_scope_quantity(
    db: Any,
    *,
    tender_id: str,
    scope_detail_id: str,
    source_document_id: str,
    document_page_id: str,
    source_locator: str,
    review_required: bool,
) -> str:
    row = TenderScopeQuantity(
        id=str(uuid4()),
        tender_id=tender_id,
        scope_detail_id=scope_detail_id,
        source_document_id=source_document_id,
        document_page_id=document_page_id,
        quantity_raw="5",
        quantity_value=Decimal("5.0000"),
        quantity_min=None,
        quantity_max=None,
        unit_raw="pieza",
        measure_kind="COUNT",
        relation="EXACT",
        source_method="NATIVE",
        source_artifact_key=f"qty:{uuid4()}",
        source_locator=source_locator,
        source_excerpt=source_locator,
        review_required=review_required,
        semantic_fingerprint=f"fp-{uuid4()}",
        confidence=0.9,
        source_contract_version="golden",
        source_analysis_id=None,
        source_page_result_id=None,
    )
    db.add(row)
    db.flush()
    return row.id


def _snapshot_rows(db: Any, model: Any, *, tender_id: str) -> tuple[tuple[Any, ...], ...]:
    rows = list(db.execute(select(model).where(model.tender_id == tender_id)).scalars())
    column_names = [column.name for column in sa_inspect(model).columns]

    normalized: list[tuple[Any, ...]] = []
    for row in rows:
        normalized.append(tuple(getattr(row, col) for col in column_names))

    return tuple(sorted(normalized))


def _snapshot_state(db: Any, *, tender_id: str) -> tuple[tuple[Any, ...], ...]:
    return (
        _snapshot_rows(db, TenderSourceEffect, tender_id=tender_id),
        _snapshot_rows(db, Requirement, tender_id=tender_id),
        _snapshot_rows(db, RequirementCandidate, tender_id=tender_id),
        _snapshot_rows(db, RequirementReview, tender_id=tender_id),
        _snapshot_rows(db, TenderScopeDetail, tender_id=tender_id),
        _snapshot_rows(db, TenderScopeAttribute, tender_id=tender_id),
        _snapshot_rows(db, TenderScopeQuantity, tender_id=tender_id),
    )


def _scenario_for_case(case_id: str) -> _Scenario:
    if case_id == "D01":
        return _Scenario(
            docs=("A", "B"),
            effects=(_EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "RESOLVED"},
                {"op": "doc_status", "doc": "B", "value": "SUPERSEDED"},
                {"op": "doc_replacement", "doc": "B", "value": "A"},
            ),
        )

    if case_id == "D02":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "C", "SUPERSEDES", "DOCUMENT_WIDE", "A"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "RESOLVED"},
                {"op": "doc_status", "doc": "A", "value": "SUPERSEDED"},
                {"op": "doc_status", "doc": "B", "value": "SUPERSEDED"},
                {"op": "doc_replacement", "doc": "B", "value": "C"},
            ),
        )

    if case_id == "D03":
        return _Scenario(
            docs=("A", "B"),
            effects=(_EffectSpec("e1", "A", "REVOKES", "DOCUMENT_WIDE", "B"),),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "RESOLVED"},
                {"op": "doc_status", "doc": "B", "value": "REVOKED"},
            ),
        )

    if case_id == "D04":
        return _Scenario(
            docs=("A", "B", "C", "D", "E"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "A", "CORRECTS", "DOCUMENT_WIDE", "C"),
                _EffectSpec("e3", "A", "CLARIFIES", "DOCUMENT_WIDE", "D"),
                _EffectSpec("e4", "A", "SUPPLEMENTS", "DOCUMENT_WIDE", "E"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "RESOLVED"},
                {"op": "doc_status", "doc": "B", "value": "ACTIVE_WITH_EFFECTS"},
                {"op": "doc_status", "doc": "C", "value": "ACTIVE_WITH_EFFECTS"},
                {"op": "doc_status", "doc": "D", "value": "ACTIVE_WITH_EFFECTS"},
                {"op": "doc_status", "doc": "E", "value": "ACTIVE_WITH_EFFECTS"},
            ),
        )

    if case_id == "D05":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "C"),
                _EffectSpec("e2", "B", "SUPERSEDES", "DOCUMENT_WIDE", "C"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "C", "value": "REVIEW_REQUIRED"},
                {"op": "doc_has_diag", "doc": "C", "value": "MULTIPLE_SUPERSEDING_SOURCES"},
            ),
        )

    if case_id == "D06":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "C"),
                _EffectSpec("e2", "B", "REVOKES", "DOCUMENT_WIDE", "C"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "C", "value": "REVIEW_REQUIRED"},
                {"op": "doc_has_diag", "doc": "C", "value": "CONFLICTING_TERMINAL_EFFECTS"},
            ),
        )

    if case_id == "D07":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "B", "SUPERSEDES", "DOCUMENT_WIDE", "A"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "A", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "B", "value": "REVIEW_REQUIRED"},
                {"op": "doc_has_diag", "doc": "A", "value": "SUPERSESSION_CYCLE"},
            ),
        )

    if case_id == "D08":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "B", "AMENDS", "DOCUMENT_WIDE", "C"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "C", "value": "REVIEW_REQUIRED"},
                {
                    "op": "doc_has_diag",
                    "doc": "C",
                    "value": "ACTING_SOURCE_SUPERSEDED_MIXED_EFFECT_REQUIRES_REVIEW",
                },
            ),
        )

    if case_id == "D09":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "C", "REVOKES", "DOCUMENT_WIDE", "A"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "B", "value": "REVIEW_REQUIRED"},
                {"op": "doc_has_diag", "doc": "B", "value": "NO_REVIVAL_REQUIRES_REVIEW"},
            ),
        )

    if case_id == "D10":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "DOCUMENT_WIDE", "B", review_required=True),
                _EffectSpec("e2", "A", "AMENDS", "UNRESOLVED", None, review_required=True),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "doc_status", "doc": "B", "value": "REVIEW_REQUIRED"},
                {
                    "op": "doc_has_diag",
                    "doc": "B",
                    "value": "REVIEW_REQUIRED_EFFECT_TARGET_BLOCKS_AUTOMATION",
                },
            ),
        )

    if case_id == "P01":
        return _Scenario(
            docs=("A", "B", "C", "D", "E"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "PARTIAL", "B", locator="numeral 1"),
                _EffectSpec("e2", "A", "CORRECTS", "PARTIAL", "C", locator="numeral 2"),
                _EffectSpec("e3", "A", "CLARIFIES", "PARTIAL", "D", locator="numeral 3"),
                _EffectSpec("e4", "A", "SUPPLEMENTS", "PARTIAL", "E", locator="numeral 4"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "RESOLVED"},
                {"op": "partial_status", "doc": "B", "locator": "numeral 1", "value": "MODIFIED"},
                {"op": "partial_status", "doc": "C", "locator": "numeral 2", "value": "CORRECTED"},
                {"op": "partial_status", "doc": "D", "locator": "numeral 3", "value": "CLARIFIED"},
                {"op": "partial_status", "doc": "E", "locator": "numeral 4", "value": "SUPPLEMENTED"},
            ),
        )

    if case_id == "P02":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "PARTIAL", "B", locator="numeral 4.2"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "RESOLVED"},
                {"op": "partial_status", "doc": "B", "locator": "numeral 4.2", "value": "SUPERSEDED"},
                {"op": "partial_effective_source", "doc": "B", "locator": "numeral 4.2", "value": "A"},
            ),
        )

    if case_id == "P03":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "REVOKES", "PARTIAL", "B", locator="numeral 4.2"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "RESOLVED"},
                {"op": "partial_status", "doc": "B", "locator": "numeral 4.2", "value": "REVOKED"},
            ),
        )

    if case_id == "P04":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "PARTIAL", "C", locator="numeral 4.2"),
                _EffectSpec("e2", "B", "SUPERSEDES", "PARTIAL", "C", locator="numeral 4.2"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "partial_status", "doc": "C", "locator": "numeral 4.2", "value": "REVIEW_REQUIRED"},
                {
                    "op": "partial_has_diag",
                    "doc": "C",
                    "locator": "numeral 4.2",
                    "value": "MULTIPLE_PARTIAL_SUPERSEDING_SOURCES",
                },
            ),
        )

    if case_id == "P05":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "PARTIAL", "C", locator="numeral 4.2"),
                _EffectSpec("e2", "B", "REVOKES", "PARTIAL", "C", locator="numeral 4.2"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "partial_status", "doc": "C", "locator": "numeral 4.2", "value": "REVIEW_REQUIRED"},
                {
                    "op": "partial_has_diag",
                    "doc": "C",
                    "locator": "numeral 4.2",
                    "value": "CONFLICTING_PARTIAL_TERMINAL_EFFECTS",
                },
            ),
        )

    if case_id == "P06":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "B", "AMENDS", "PARTIAL", "C", locator="numeral 4.2"),
            ),
            entities=(),
            checks=(
                {"op": "partial_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "partial_status", "doc": "C", "locator": "numeral 4.2", "value": "REVIEW_REQUIRED"},
                {
                    "op": "partial_has_diag",
                    "doc": "C",
                    "locator": "numeral 4.2",
                    "value": "PARTIAL_EFFECT_ACTING_SOURCE_SUPERSEDED_REQUIRES_REVIEW",
                },
            ),
        )

    if case_id == "G01":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
            ),
            entities=(),
            checks=(
                {"op": "document_tender_status", "value": "RESOLVED"},
                {"op": "doc_status", "doc": "B", "value": "SUPERSEDED"},
                {"op": "doc_block_count", "doc": "B", "value": 2},
            ),
        )

    if case_id == "G02":
        return _Scenario(
            docs=("A", "B", "C"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),
                _EffectSpec("e2", "C", "AMENDS", "PARTIAL", "B", locator="numeral 9"),
            ),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "numeral 9"),
            ),
            checks=(),
        )

    if case_id == "X01":
        return _Scenario(
            docs=("A", "B"),
            effects=(_EffectSpec("e1", "A", "SUPERSEDES", "DOCUMENT_WIDE", "B"),),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "num 1"),
            ),
            checks=(
                {"op": "projection_status", "entity": "r1", "value": "SUPERSEDED"},
            ),
        )

    if case_id == "X02":
        return _Scenario(
            docs=("A", "B"),
            effects=(_EffectSpec("e1", "A", "REVOKES", "DOCUMENT_WIDE", "B"),),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "num 1"),
            ),
            checks=(
                {"op": "projection_status", "entity": "r1", "value": "REVOKED"},
            ),
        )

    if case_id == "X03":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "PARTIAL", "B", locator="num 1"),
            ),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "num 1"),
            ),
            checks=(
                {"op": "projection_status", "entity": "r1", "value": "EFFECTIVE_WITH_OVERLAY"},
                {"op": "projection_supports", "entity": "r1", "value": "e1"},
            ),
        )

    if case_id == "X04":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "SUPERSEDES", "PARTIAL", "B", locator="loc-s"),
                _EffectSpec("e2", "A", "REVOKES", "PARTIAL", "B", locator="loc-r"),
            ),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "loc-s"),
                _EntitySpec("r2", ENTITY_TYPE_REQUIREMENT, "B", "loc-r"),
            ),
            checks=(
                {"op": "projection_status", "entity": "r1", "value": "SUPERSEDED"},
                {"op": "projection_status", "entity": "r2", "value": "REVOKED"},
            ),
        )

    if case_id == "X05":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "PARTIAL", "B", locator="padre"),
            ),
            entities=(
                _EntitySpec("sd1", ENTITY_TYPE_SCOPE_DETAIL, "B", "padre", review_required=True),
                _EntitySpec("sa1", ENTITY_TYPE_SCOPE_ATTRIBUTE, "B", "hijo", parent_alias="sd1"),
                _EntitySpec("sq1", ENTITY_TYPE_SCOPE_QUANTITY, "B", "cantidad", parent_alias="sd1"),
            ),
            checks=(
                {"op": "projection_status", "entity": "sd1", "value": "REVIEW_REQUIRED"},
                {"op": "projection_status", "entity": "sa1", "value": "REVIEW_REQUIRED"},
                {"op": "projection_status", "entity": "sq1", "value": "REVIEW_REQUIRED"},
                {
                    "op": "projection_has_diag",
                    "entity": "sq1",
                    "value": "PARENT_SCOPE_REVIEW_REQUIRED",
                },
                {
                    "op": "projection_has_diag",
                    "entity": "sa1",
                    "value": "PARENT_SCOPE_REVIEW_REQUIRED",
                },
            ),
        )

    if case_id == "X06":
        return _Scenario(
            docs=("A", "B"),
            effects=(
                _EffectSpec("e1", "A", "AMENDS", "UNRESOLVED", None, review_required=True),
            ),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "B", "num 1"),
            ),
            checks=(
                {"op": "projection_tender_status", "value": "REVIEW_REQUIRED"},
                {"op": "projection_status", "entity": "r1", "value": "EFFECTIVE"},
            ),
        )

    if case_id == "X07":
        return _Scenario(
            docs=("A",),
            effects=(),
            entities=(
                _EntitySpec("r1", ENTITY_TYPE_REQUIREMENT, "MISSING", "num 1"),
            ),
            checks=(
                {"op": "projection_status", "entity": "r1", "value": "UNRESOLVED_SOURCE"},
            ),
        )

    raise ValueError(f"unsupported case_id: {case_id}")


def run_result_to_json(result: SourceEffectVersioningGoldenRunResult) -> dict[str, Any]:
    return asdict(result)
