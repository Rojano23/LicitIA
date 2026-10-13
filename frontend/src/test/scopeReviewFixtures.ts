/** Synthetic wire-contract fixtures. These do not certify backend domain resolution. */
import type { ScopeHumanReview, ScopeReviewItem } from "../api/scopeReview";

export function scopeItem(id = "scope-1"): ScopeReviewItem {
  return {
    scope_detail_id: id,
    projection_fingerprint: "a".repeat(64),
    current_review_revision: null,
    latest_applicable_review: null,
    reviewable: true,
    not_reviewable_reason: null,
    history: [],
    current: {
      machine: {
        id, tender_id: "tender-1", tender_item_id: null, scope_segment_id: null,
        candidate_item_key: null, source_document_id: "document-1", document_page_id: "page-7",
        source_analysis_id: null, source_page_result_id: null, domain: "SERVICE", detail_type: null,
        description: `Inspeccionar equipo ${id}`, normalized_label: null, applicability: "TENDER_WIDE",
        source_method: "NATIVE", source_artifact_key: "synthetic-native:page-7", source_contract_version: "synthetic-contract",
        source_locator: "numeral 4.2", source_excerpt: "Se deberá inspeccionar el equipo de control.",
        confidence: 0.8, review_required: true, quantity_raw: null, unit_raw: null,
        semantic_fingerprint: "b".repeat(64), created_at: "2026-10-12T12:00:00Z", updated_at: "2026-10-12T12:00:00Z",
        document_revision: 3, source_page: 7,
      },
      latest_review: null, human_review_status: "NO_REVIEW", effective_status: "PENDING",
      effective_description: `Inspeccionar equipo ${id}`, accepted_execution_scope: false,
      machine_review_required: true, human_resolved_machine_review: false, source_blocked: false,
      source_projection: {
        entity_type: "SCOPE_DETAIL", entity_id: id, source_document_id: "document-1", document_page_id: "page-7",
        source_locator: "numeral 4.2", status: "REVIEW_REQUIRED", document_effective_status: "ACTIVE",
        partial_locator_status: null, supporting_effect_ids: [], blocking_effect_ids: [],
        diagnostics: [{ code: "FACT_REVIEW_REQUIRED", message: "Synthetic fact requires review", effect_ids: [],
          entity_type: "SCOPE_DETAIL", entity_id: id, source_document_id: "document-1", source_locator: "numeral 4.2", parent_entity_id: null }],
      },
    },
  };
}

export function humanReview(item: ScopeReviewItem, revision = 1): ScopeHumanReview {
  if (!item.current) throw new Error("Fixture needs a machine snapshot");
  return {
    id: `review-${revision}`, tender_id: "tender-1", scope_detail_id: item.scope_detail_id,
    revision, decision: "CONFIRMED", correction: null, note: "Revisado con la fuente",
    machine_snapshot: item.current.machine, reviewed_source_fingerprint: "c".repeat(64), reviewed_at: "2026-10-12T13:00:00Z",
  };
}
