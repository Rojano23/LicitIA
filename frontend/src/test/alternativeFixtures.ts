import type { AlternativeRevision, TechnicalAlternative } from "../api/technicalAlternatives";
import type { ComplianceDecision, ComplianceEvaluation, ComplianceItem, ComplianceStatus, FrozenScopeItem } from "../api/alternativeCompliance";
import { scopeItem } from "./scopeReviewFixtures";

export function alternative(id = "alt-a", revision = 1): TechnicalAlternative {
  const current: AlternativeRevision = {
    id: `${id}-r${revision}`, alternative_id: id, tender_id: "tender-1", revision,
    name: id === "alt-a" ? "Alternativa A" : "Alternativa B", technical_description: `Estrategia técnica ${id}`,
    assumptions: "Acceso autorizado", notes: "Nota humana", lifecycle_state: "DRAFT",
    fingerprint: "a".repeat(64), created_at: "2026-10-12T12:00:00Z",
  };
  return { id, tender_id: "tender-1", created_at: current.created_at,
    revisions: [current], current_revision: current };
}
export function frozenScope(id = "scope-1"): FrozenScopeItem {
  const machine = scopeItem().current!.machine;
  const { created_at: _created, updated_at: _updated, ...content } = machine;
  return { scope_detail_id: id, effective_description: `Inspeccionar equipo ${id}`,
    accepted_execution_scope: true, unresolved: false, effective_status: "NOT_REQUIRED",
    human_review_status: "NO_REVIEW", current_review_revision: null,
    machine: { ...content, id, review_required: false },
    source_projection: { ...scopeItem().current!.source_projection, status: "EFFECTIVE", diagnostics: [] },
    applicable_review: null, projection_fingerprint: "b".repeat(64) };
}
export function complianceItem(id = "scope-1"): ComplianceItem {
  return { item_key: id, item_index: 0, snapshot: frozenScope(id), status: "NOT_EVALUATED", latest_decision: null, decisions: [] };
}
export function evaluation(id = "eval-1", alternativeId = "alt-a"): ComplianceEvaluation {
  const item = complianceItem();
  return { id, tender_id: "tender-1", alternative_id: alternativeId,
    alternative_revision: alternative(alternativeId).current_revision,
    scope_snapshot: { tender_id: "tender-1", items: [item.snapshot], fingerprint: "c".repeat(64), unresolved: false },
    created_at: "2026-10-12T13:00:00Z", applicability: "CURRENT", overall_status: "NOT_EVALUATED",
    historical_aggregate: "NOT_EVALUATED", counts: { COMPLIANT: 0, PARTIAL: 0, NON_COMPLIANT: 0, REVIEW_REQUIRED: 0, NOT_EVALUATED: 1 }, items: [item] };
}
export function judgment(status: ComplianceStatus, revision = 1): ComplianceDecision {
  return { id: `decision-${revision}`, revision, status, rationale: `Justificación histórica ${revision}`,
    evidence_note: `Referencia histórica ${revision}`, created_at: "2026-10-12T14:00:00Z" };
}
export function assessed(status: ComplianceStatus): ComplianceEvaluation {
  const row = evaluation(); const decision = judgment(status);
  return { ...row, overall_status: status, historical_aggregate: status,
    counts: { COMPLIANT: 0, PARTIAL: 0, NON_COMPLIANT: 0, REVIEW_REQUIRED: 0, NOT_EVALUATED: 0, [status]: 1 },
    items: [{ ...row.items[0], status, latest_decision: decision, decisions: [decision] }] };
}
