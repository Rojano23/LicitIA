from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.company_evidence import list_company_evidence
from app.compliance_evaluation import SYSTEM_NOT_EVALUATED, SYSTEM_REVIEW_REQUIRED, list_tender_company_compliance_assessments
from app.compliance_review import list_tender_company_compliance_review
from app.evidence_matching import list_tender_company_evidence_match_candidates
from app.requirement_matrix import get_tender_requirement_matrix

OPERATIONAL_FINALIZED = "FINALIZED"
OPERATIONAL_ACTION_REQUIRED = "ACTION_REQUIRED"
OPERATIONAL_REVIEW_REQUIRED = "REVIEW_REQUIRED"
OPERATIONAL_DIRECT_VERIFICATION_PENDING = "DIRECT_VERIFICATION_PENDING"
OPERATIONAL_CONDITION_UNRESOLVED = "CONDITION_UNRESOLVED"
OPERATIONAL_NOT_APPLICABLE = "NOT_APPLICABLE"

FINAL_DECISION_STATUSES = {"COMPLIES", "DOES_NOT_COMPLY", "NOT_APPLICABLE"}
PENDING_REVIEW_STATUSES = {"PENDING", "NEEDS_REVIEW"}

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ACTION = "ACTION"


def _normalize_status(value: str | None) -> str:
    return (value or "").strip().upper()


def _finding(code: str, severity: str, message: str, action: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "action": action,
    }


def _findings_catalog() -> dict[str, dict[str, str]]:
    return {
        "NO_COMPANY_EVIDENCE": {
            "severity": SEVERITY_ACTION,
            "message": "No hay evidencia activa de la empresa para este requisito.",
            "action": "Cargar evidencia empresarial o vincular documentos al expediente.",
        },
        "NO_ACTIVE_EVIDENCE": {
            "severity": SEVERITY_ACTION,
            "message": "Existe evidencia histórica, pero no hay evidencia activa vigente.",
            "action": "Revisar la vigencia de la biblioteca de evidencia y actualizar documentos actuales.",
        },
        "NO_CONFIRMED_EVIDENCE_MATCH": {
            "severity": SEVERITY_ACTION,
            "message": "La empresa tiene evidencia activa, pero aún no hay asociación confirmada para este requisito.",
            "action": "Analizar y confirmar una evidencia candidata o crear una asociación manual.",
        },
        "MATCH_REVIEW_PENDING": {
            "severity": SEVERITY_WARNING,
            "message": "Hay asociaciones candidatas de evidencia pendientes de revisión humana.",
            "action": "Confirmar o rechazar las asociaciones candidatas.",
        },
        "MATCH_REVIEW_STALE": {
            "severity": SEVERITY_WARNING,
            "message": "Al menos una asociación candidata quedó desactualizada frente al estado actual del expediente.",
            "action": "Revisar de nuevo la asociación candidata y su justificación.",
        },
        "EVIDENCE_REVIEW_PENDING": {
            "severity": SEVERITY_WARNING,
            "message": "La evidencia asociada todavía no tiene revisión humana vigente.",
            "action": "Validar o marcar la evidencia para revisión humana.",
        },
        "EVIDENCE_REVIEW_STALE": {
            "severity": SEVERITY_WARNING,
            "message": "La evidencia asociada cambió después de la revisión humana.",
            "action": "Revalidar la evidencia asociada.",
        },
        "SYSTEM_ASSESSMENT_MISSING": {
            "severity": SEVERITY_ACTION,
            "message": "Aún no existe evaluación automática para este requisito.",
            "action": "Ejecutar la evaluación automática de cumplimiento.",
        },
        "SYSTEM_ASSESSMENT_REVIEW_REQUIRED": {
            "severity": SEVERITY_WARNING,
            "message": "La evaluación automática requiere revisión antes de cerrar el requisito.",
            "action": "Revisar la evaluación automática y sus advertencias.",
        },
        "DIRECT_VERIFICATION_PENDING": {
            "severity": SEVERITY_ACTION,
            "message": "El requisito se valida por verificación directa y aún no tiene decisión humana final.",
            "action": "Realizar verificación manual y registrar la decisión humana.",
        },
        "CONDITIONAL_APPLICABILITY_UNRESOLVED": {
            "severity": SEVERITY_WARNING,
            "message": "La condición de aplicabilidad del requisito sigue sin resolverse.",
            "action": "Resolver el contexto condicional antes de cerrar el requisito.",
        },
        "HUMAN_DECISION_PENDING": {
            "severity": SEVERITY_ACTION,
            "message": "El requisito todavía no tiene decisión humana final.",
            "action": "Registrar una decisión humana de cumplimiento.",
        },
        "HUMAN_DECISION_STALE": {
            "severity": SEVERITY_WARNING,
            "message": "La decisión humana quedó desactualizada frente al estado actual del requisito.",
            "action": "Revisar la decisión humana y actualizar la justificación.",
        },
        "HUMAN_OVERRIDE_PRESENT": {
            "severity": SEVERITY_INFO,
            "message": "La decisión humana actual no coincide con la referencia automática del sistema.",
            "action": "Conservar la justificación humana y auditar el override.",
        },
        "REQUIREMENT_SUPERSEDED": {
            "severity": SEVERITY_INFO,
            "message": "El requisito fue superado por una versión posterior.",
            "action": "No requiere acción en la matriz activa.",
        },
        "REQUIREMENT_REJECTED": {
            "severity": SEVERITY_INFO,
            "message": "El requisito fue descartado por revisión humana.",
            "action": "No requiere acción en la matriz activa.",
        },
    }


def _clone_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _unique_evidence_count(matches: list[dict[str, Any]]) -> int:
    return len({str(match["company_evidence"]["id"]) for match in matches if match.get("company_evidence")})


def _current_evidence_count(matches: list[dict[str, Any]]) -> int:
    evidence_ids: set[str] = set()
    for match in matches:
        evidence = match.get("company_evidence") or {}
        if evidence.get("review_freshness") == "CURRENT":
            evidence_ids.add(str(evidence.get("id")))
    return len(evidence_ids)


def _confirmed_match_count(matches: list[dict[str, Any]]) -> int:
    return sum(1 for match in matches if (match.get("review") or {}).get("review_status") == "CONFIRMED")


def _pending_match_count(matches: list[dict[str, Any]]) -> int:
    return sum(1 for match in matches if _normalize_status((match.get("review") or {}).get("review_status")) in {"", "PENDING"})


def _stale_match_count(matches: list[dict[str, Any]]) -> int:
    return sum(
        1
        for match in matches
        if (match.get("review") or {}).get("review_status") in {"CONFIRMED", "NEEDS_REVIEW", "REJECTED"}
        and match.get("review_freshness") == "STALE"
    )


def _evidence_review_status_counts(matches: list[dict[str, Any]]) -> tuple[int, int]:
    pending = 0
    stale = 0
    for match in matches:
        evidence = match.get("company_evidence") or {}
        freshness = evidence.get("review_freshness")
        if freshness == "NOT_REVIEWED":
            pending += 1
        elif freshness == "STALE":
            stale += 1
    return pending, stale


def _deduplicate_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for finding in findings:
        code = finding["code"]
        if code in seen:
            continue
        seen.add(code)
        unique.append(finding)
    return unique


def _build_findings(
    *,
    requirement_row: dict[str, Any],
    assessment_row: dict[str, Any] | None,
    review_row: dict[str, Any] | None,
    matches: list[dict[str, Any]],
    company_evidence_count: int,
    current_company_evidence_count: int,
) -> list[dict[str, str]]:
    catalog = _findings_catalog()
    findings: list[dict[str, str]] = []

    effective_status = _normalize_status(str(requirement_row.get("effective_status") or None))
    review_status = _normalize_status(str(requirement_row.get("review_status") or None))
    evidence_mode = _normalize_status(str(requirement_row.get("evidence_mode") or None))

    if effective_status == "SUPERSEDED":
        findings.append(_finding("REQUIREMENT_SUPERSEDED", **catalog["REQUIREMENT_SUPERSEDED"]))
    elif review_status == "REJECTED":
        findings.append(_finding("REQUIREMENT_REJECTED", **catalog["REQUIREMENT_REJECTED"]))

    if evidence_mode != "DIRECT_VERIFICATION":
        if company_evidence_count == 0:
            findings.append(_finding("NO_COMPANY_EVIDENCE", **catalog["NO_COMPANY_EVIDENCE"]))
        elif current_company_evidence_count == 0:
            findings.append(_finding("NO_ACTIVE_EVIDENCE", **catalog["NO_ACTIVE_EVIDENCE"]))

    if matches:
        confirmed_count = _confirmed_match_count(matches)
        pending_count = _pending_match_count(matches)
        stale_match_count = _stale_match_count(matches)
        evidence_pending_count, evidence_stale_count = _evidence_review_status_counts(matches)

        if confirmed_count == 0:
            findings.append(_finding("NO_CONFIRMED_EVIDENCE_MATCH", **catalog["NO_CONFIRMED_EVIDENCE_MATCH"]))
        if pending_count > 0:
            findings.append(_finding("MATCH_REVIEW_PENDING", **catalog["MATCH_REVIEW_PENDING"]))
        if stale_match_count > 0:
            findings.append(_finding("MATCH_REVIEW_STALE", **catalog["MATCH_REVIEW_STALE"]))
        if evidence_pending_count > 0:
            findings.append(_finding("EVIDENCE_REVIEW_PENDING", **catalog["EVIDENCE_REVIEW_PENDING"]))
        if evidence_stale_count > 0:
            findings.append(_finding("EVIDENCE_REVIEW_STALE", **catalog["EVIDENCE_REVIEW_STALE"]))

    if assessment_row is None and evidence_mode != "DIRECT_VERIFICATION":
        findings.append(_finding("SYSTEM_ASSESSMENT_MISSING", **catalog["SYSTEM_ASSESSMENT_MISSING"]))
    elif assessment_row is not None:
        system_status = _normalize_status(str(assessment_row.get("system_status") or None))
        if system_status == SYSTEM_REVIEW_REQUIRED:
            findings.append(_finding("SYSTEM_ASSESSMENT_REVIEW_REQUIRED", **catalog["SYSTEM_ASSESSMENT_REVIEW_REQUIRED"]))

    if assessment_row is not None and assessment_row.get("applicability_context") == "CONDITION_UNRESOLVED":
        findings.append(_finding("CONDITIONAL_APPLICABILITY_UNRESOLVED", **catalog["CONDITIONAL_APPLICABILITY_UNRESOLVED"]))

    if review_row is None:
        if evidence_mode == "DIRECT_VERIFICATION":
            findings.append(_finding("DIRECT_VERIFICATION_PENDING", **catalog["DIRECT_VERIFICATION_PENDING"]))
        elif assessment_row is None or company_evidence_count == 0 or current_company_evidence_count == 0 or not matches:
            findings.append(_finding("HUMAN_DECISION_PENDING", **catalog["HUMAN_DECISION_PENDING"]))
    else:
        decision = review_row.get("human_decision") or {}
        decision_status = _normalize_status(str(decision.get("decision_status") or None))
        decision_freshness = _normalize_status(str(decision.get("freshness") or None))
        decision_relation = _normalize_status(str(review_row.get("decision_relation") or None))

        if decision_status in PENDING_REVIEW_STATUSES:
            if evidence_mode == "DIRECT_VERIFICATION":
                findings.append(_finding("DIRECT_VERIFICATION_PENDING", **catalog["DIRECT_VERIFICATION_PENDING"]))
            else:
                findings.append(_finding("HUMAN_DECISION_PENDING", **catalog["HUMAN_DECISION_PENDING"]))
        elif decision_freshness == "STALE":
            findings.append(_finding("HUMAN_DECISION_STALE", **catalog["HUMAN_DECISION_STALE"]))
        elif decision_status in FINAL_DECISION_STATUSES and decision_relation == "HUMAN_OVERRIDE":
            findings.append(_finding("HUMAN_OVERRIDE_PRESENT", **catalog["HUMAN_OVERRIDE_PRESENT"]))

    return _deduplicate_findings(findings)


def _operational_state(
    *,
    requirement_row: dict[str, Any],
    assessment_row: dict[str, Any] | None,
    review_row: dict[str, Any] | None,
    findings: list[dict[str, str]],
) -> str:
    effective_status = _normalize_status(str(requirement_row.get("effective_status") or None))
    review_status = _normalize_status(str(requirement_row.get("review_status") or None))
    evidence_mode = _normalize_status(str(requirement_row.get("evidence_mode") or None))

    if effective_status == "SUPERSEDED" or review_status == "REJECTED":
        return OPERATIONAL_NOT_APPLICABLE

    if review_row is not None:
        decision = review_row.get("human_decision") or {}
        decision_status = _normalize_status(str(decision.get("decision_status") or None))
        freshness = _normalize_status(str(decision.get("freshness") or None))
        if decision_status in FINAL_DECISION_STATUSES and freshness == "CURRENT":
            if decision_status == "NOT_APPLICABLE":
                return OPERATIONAL_NOT_APPLICABLE
            return OPERATIONAL_FINALIZED

    if evidence_mode == "DIRECT_VERIFICATION" and any(finding["code"] == "DIRECT_VERIFICATION_PENDING" for finding in findings):
        return OPERATIONAL_DIRECT_VERIFICATION_PENDING

    if assessment_row is not None and assessment_row.get("applicability_context") == "CONDITION_UNRESOLVED":
        return OPERATIONAL_CONDITION_UNRESOLVED

    if any(finding["code"] in {"HUMAN_DECISION_STALE", "SYSTEM_ASSESSMENT_REVIEW_REQUIRED", "MATCH_REVIEW_STALE", "EVIDENCE_REVIEW_STALE"} for finding in findings):
        return OPERATIONAL_REVIEW_REQUIRED

    if any(finding["code"] in {"HUMAN_DECISION_PENDING", "SYSTEM_ASSESSMENT_MISSING", "NO_COMPANY_EVIDENCE", "NO_ACTIVE_EVIDENCE", "NO_CONFIRMED_EVIDENCE_MATCH", "MATCH_REVIEW_PENDING", "EVIDENCE_REVIEW_PENDING"} for finding in findings):
        return OPERATIONAL_ACTION_REQUIRED

    if assessment_row is not None and _normalize_status(str(assessment_row.get("system_status") or None)) in {SYSTEM_NOT_EVALUATED, SYSTEM_REVIEW_REQUIRED}:
        return OPERATIONAL_REVIEW_REQUIRED

    return OPERATIONAL_FINALIZED


def _summary_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    finding_counts: dict[str, int] = {}
    operational_state_counts: dict[str, int] = {}
    for row in rows:
        operational_state = str(row["operational_state"])
        operational_state_counts[operational_state] = operational_state_counts.get(operational_state, 0) + 1
        for finding in row["findings"]:
            code = finding["code"]
            finding_counts[code] = finding_counts.get(code, 0) + 1

    active_count = len(rows)
    finalized_count = operational_state_counts.get(OPERATIONAL_FINALIZED, 0)
    not_applicable_count = operational_state_counts.get(OPERATIONAL_NOT_APPLICABLE, 0)
    review_required_count = operational_state_counts.get(OPERATIONAL_REVIEW_REQUIRED, 0)
    action_required_count = operational_state_counts.get(OPERATIONAL_ACTION_REQUIRED, 0)
    direct_verification_pending_count = operational_state_counts.get(OPERATIONAL_DIRECT_VERIFICATION_PENDING, 0)
    condition_unresolved_count = operational_state_counts.get(OPERATIONAL_CONDITION_UNRESOLVED, 0)

    current_decisions = 0
    for row in rows:
        human_decision = row.get("human_decision")
        if not human_decision:
            continue
        decision_status = _normalize_status(str(human_decision.get("decision_status") or None))
        freshness = _normalize_status(str(human_decision.get("freshness") or None))
        if decision_status in FINAL_DECISION_STATUSES and freshness == "CURRENT":
            current_decisions += 1

    return {
        "total_requirements": active_count,
        "active_requirements": active_count,
        "excluded_rejected_count": 0,
        "excluded_superseded_count": 0,
        "company_evidence_count": 0,
        "current_company_evidence_count": 0,
        "matched_evidence_count": 0,
        "confirmed_match_count": 0,
        "finalized_count": finalized_count,
        "action_required_count": action_required_count,
        "review_required_count": review_required_count,
        "direct_verification_pending_count": direct_verification_pending_count,
        "condition_unresolved_count": condition_unresolved_count,
        "not_applicable_count": not_applicable_count,
        "human_review_completion_percent": 0.0 if active_count == 0 else round((current_decisions / active_count) * 100, 2),
        "finding_counts": finding_counts,
        "operational_state_counts": operational_state_counts,
    }


def get_tender_company_compliance_matrix(
    db: Any,
    tender_id: str,
    company_id: str,
    *,
    category: str | None = None,
    system_status: str | None = None,
    decision_status: str | None = None,
    operational_state: str | None = None,
    action_code: str | None = None,
    include_historical: bool = False,
) -> dict[str, Any]:
    matrix = get_tender_requirement_matrix(db, tender_id)
    assessments_payload = list_tender_company_compliance_assessments(
        db,
        tender_id,
        company_id,
        category=category,
        system_status=system_status,
    )
    review_payload = list_tender_company_compliance_review(
        db,
        tender_id,
        company_id,
        category=category,
        system_status=system_status,
        decision_status=decision_status,
    )
    match_payload = list_tender_company_evidence_match_candidates(
        db,
        tender_id,
        company_id,
        include_historical=include_historical,
    )
    company_evidence = list_company_evidence(db, company_id)
    current_company_evidence = list_company_evidence(db, company_id, current_source_only=True)

    requirement_rows = matrix["requirements"]
    if not include_historical:
        requirement_rows = [
            row
            for row in requirement_rows
            if _normalize_status(str(row.get("effective_status") or None)) != "SUPERSEDED"
            and _normalize_status(str(row.get("review_status") or None)) != "REJECTED"
        ]

    assessment_by_requirement = {row["requirement_id"]: row for row in assessments_payload["assessments"]}
    review_by_requirement = {row["requirement_id"]: row for row in review_payload["rows"]}
    match_by_requirement = {row["requirement_id"]: row for row in match_payload["requirements"]}

    rows: list[dict[str, Any]] = []
    company_evidence_count = int(company_evidence["summary"]["evidence_count"])
    current_company_evidence_count = int(current_company_evidence["summary"]["evidence_count"])

    for requirement_row in requirement_rows:
        requirement_id = str(requirement_row["requirement_id"])
        assessment_row = _clone_row(assessment_by_requirement.get(requirement_id))
        review_row = _clone_row(review_by_requirement.get(requirement_id))
        match_row = _clone_row(match_by_requirement.get(requirement_id))
        matches = list(match_row.get("matches", [])) if match_row else []

        findings = _build_findings(
            requirement_row=requirement_row,
            assessment_row=assessment_row,
            review_row=review_row,
            matches=matches,
            company_evidence_count=company_evidence_count,
            current_company_evidence_count=current_company_evidence_count,
        )
        state = _operational_state(
            requirement_row=requirement_row,
            assessment_row=assessment_row,
            review_row=review_row,
            findings=findings,
        )

        row = {
            "requirement": requirement_row,
            "system_assessment": assessment_row,
            "human_decision": review_row["human_decision"] if review_row is not None else None,
            "decision_relation": review_row["decision_relation"] if review_row is not None else None,
            "operational_state": state,
            "findings": findings,
            "matches": matches,
        }

        if category and _normalize_status(str(requirement_row.get("category") or None)) != _normalize_status(category):
            continue
        if system_status:
            if assessment_row is None or _normalize_status(str(assessment_row.get("system_status") or None)) != _normalize_status(system_status):
                continue
        if decision_status:
            if review_row is None or _normalize_status(str(review_row["human_decision"]["decision_status"])) != _normalize_status(decision_status):
                continue
        if operational_state and _normalize_status(state) != _normalize_status(operational_state):
            continue
        if action_code and action_code.upper() not in {finding["code"] for finding in findings}:
            continue

        rows.append(row)

    rows.sort(
        key=lambda row: (
            0
            if row["operational_state"]
            in {OPERATIONAL_ACTION_REQUIRED, OPERATIONAL_REVIEW_REQUIRED, OPERATIONAL_DIRECT_VERIFICATION_PENDING, OPERATIONAL_CONDITION_UNRESOLVED}
            else 1,
            str(row["requirement"]["canonical_text"]).lower(),
            row["requirement"]["requirement_id"],
        )
    )

    summary = _summary_counts(rows)
    summary["company_evidence_count"] = company_evidence_count
    summary["current_company_evidence_count"] = current_company_evidence_count
    summary["matched_evidence_count"] = sum(_unique_evidence_count(row["matches"]) for row in rows)
    summary["confirmed_match_count"] = sum(_confirmed_match_count(row["matches"]) for row in rows)
    summary["excluded_rejected_count"] = 0 if include_historical else sum(
        1 for requirement_row in matrix["requirements"] if _normalize_status(str(requirement_row.get("review_status") or None)) == "REJECTED"
    )
    summary["excluded_superseded_count"] = 0 if include_historical else sum(
        1 for requirement_row in matrix["requirements"] if _normalize_status(str(requirement_row.get("effective_status") or None)) == "SUPERSEDED"
    )
    summary["total_requirements"] = len(rows)
    summary["active_requirements"] = len(rows)

    return {
        "tender_id": tender_id,
        "company_id": company_id,
        "matrix_version": "mvp-05.6",
        "generated_at": datetime.now(timezone.utc),
        "scope_note": (
            "La matriz de cumplimiento compone verdad aceptada de requisitos, evidencia, asociaciones, evaluación automática y decisión humana. "
            "No crea nueva autoridad de decisión; sólo expone huecos operativos y trazabilidad."
        ),
        "summary": summary,
        "rows": rows,
    }


def get_tender_company_missing_evidence_audit(db: Any, tender_id: str, company_id: str, **kwargs: Any) -> dict[str, Any]:
    return get_tender_company_compliance_matrix(db, tender_id, company_id, **kwargs)