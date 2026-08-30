import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import axios from "axios";
import { CompanyEvidenceLibrary } from "./components/CompanyEvidenceLibrary";

type Tender = {
  id: string;
  title: string;
  institution_profile: string | null;
  external_reference: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

type TenderDocument = {
  id: string;
  tender_id: string;
  original_filename: string;
  source_relative_path: string | null;
  stored_relative_path: string;
  mime_type: string | null;
  file_size_bytes: number;
  sha256: string;
  status: string;
  processing_status?: string;
  page_count?: number;
  revision_of_document_id: string | null;
  revision_number: number;
  is_current: boolean;
  imported_at: string;
};

type PageOcrResult = {
  id: string;
  document_page_id: string;
  page_number: number | null;
  engine: string;
  engine_version: string;
  language: string;
  text: string;
  status: string;
  confidence: number | null;
  processing_time_ms: number | null;
  warnings: string | null;
  created_at: string;
  updated_at: string;
};

type DocumentPage = {
  id: string;
  document_id: string;
  page_number: number;
  text: string;
  char_count: number;
  extraction_method: string;
  status: string;
  extracted_at: string;
  ocr_results: PageOcrResult[];
};

type ImportResult = {
  filename: string;
  source_relative_path: string | null;
  status: string;
  message: string | null;
  document_id: string | null;
  stored_relative_path: string | null;
  sha256: string | null;
  revision_of_document_id: string | null;
  revision_number: number | null;
  is_current: boolean | null;
};

type PendingConflict = {
  file: File;
  sourceRelativePath: string | null;
  filename: string;
  candidates: TenderDocument[];
};

type OcrProvider = {
  provider_id: string;
  provider_name: string;
  status: string;
  version: string | null;
  status_reason: string | null;
};

type ClassificationEvidence = {
  document_page_id: string | null;
  normalized_content_id: string | null;
  document_chunk_id: string | null;
  source_kind: string;
  signal: string;
  excerpt: string;
  weight_or_score: number;
};

type ClassificationTag = {
  tag: string;
  score: number;
};

type ClassificationCandidateScore = {
  type: string;
  score: number;
};

type ClassificationResult = {
  document_id: string;
  suggested_type: string;
  suggested_score: number;
  effective_type: string;
  classification_status: string;
  is_composite: boolean;
  human_type: string | null;
  human_note: string | null;
  candidate_scores: ClassificationCandidateScore[];
  functional_tags: ClassificationTag[];
  evidence: ClassificationEvidence[];
  input_fingerprint_sha256: string;
  not_ready: boolean;
};

type ReferenceCandidate = {
  document_id: string;
  original_filename: string;
  processing_status: string | null;
};

type ReferenceItem = {
  id: string;
  source_document_id: string;
  raw_reference_text: string;
  normalized_reference_key: string;
  relationship_hint: string;
  resolution_status: string;
  resolved_target_document_id: string | null;
  resolved_target_filename: string | null;
  page_number: number | null;
  excerpt: string;
  source_type: string | null;
  source_scope: string | null;
  source_engine: string | null;
  ambiguous_candidates: ReferenceCandidate[];
  human_decision: string | null;
};

type RelationshipSupport = {
  reference_id: string;
  raw_reference_text: string;
  normalized_reference_key: string;
  page_number: number | null;
  excerpt: string;
};

type RelationshipItem = {
  id: string;
  source_document_id: string;
  source_document_filename: string | null;
  target_document_id: string;
  target_document_filename: string | null;
  relationship_type: string;
  supporting_references: RelationshipSupport[];
};

type ReferenceAnalysis = {
  document_id: string;
  status: string;
  extractor_version: string;
  input_fingerprint_sha256: string;
  references: ReferenceItem[];
  relationships: RelationshipItem[];
  counts: {
    total_reference_mentions: number;
    resolved_references: number;
    ambiguous_references: number;
    unresolved_references: number;
    human_resolved_references: number;
    ignored_references: number;
    resolved_relationships: number;
  };
};

type AuditFinding = {
  code: string;
  severity: string;
  message: string;
  document_id: string | null;
  document_filename: string | null;
};

type AuditDocumentRow = {
  document_id: string;
  document_short_id: string;
  filename: string;
  is_current: boolean;
  processing_status: string;
  page_count: number;
  text_acquisition_state: string;
  normalized: boolean;
  normalized_source_count: number;
  classification_type: string;
  classification_status: string;
  classification_version: string | null;
  reference_analysis_status: string;
  reference_extractor_version: string | null;
  reference_count: number;
  auto_resolved_reference_count: number;
  human_resolved_reference_count: number;
  ambiguous_reference_count: number;
  unresolved_reference_count: number;
  ignored_reference_count: number;
  integrity_findings: string[];
};

type DocumentIntelligenceAudit = {
  tender_id: string;
  audit_version: string;
  generated_at: string;
  overall_readiness: string;
  summary: {
    documents: {
      total_documents: number;
      current_documents: number;
      non_current_documents: number;
    };
    classification: {
      classified_documents: number;
      unclassified_documents: number;
      status_counts: {
        SUGGESTED: number;
        CONFIRMED: number;
        NEEDS_REVIEW: number;
        OVERRIDDEN: number;
      };
    };
    references: {
      status_counts: {
        AUTO_RESOLVED: number;
        HUMAN_RESOLVED: number;
        AMBIGUOUS: number;
        UNRESOLVED: number;
        IGNORED: number;
      };
    };
  };
  document_rows: AuditDocumentRow[];
  findings: AuditFinding[];
};

type BaselineReferenceStatusCounts = {
  AUTO_RESOLVED: number;
  HUMAN_RESOLVED: number;
  AMBIGUOUS: number;
  UNRESOLVED: number;
  IGNORED: number;
};

type DocumentMapEntry = {
  source_document_id: string;
  source_filename: string | null;
  relationship_type: string;
  target_document_id: string;
  target_filename: string | null;
  supporting_reference_count: number;
  supporting_pages: number[];
  resolution_origin: string;
};

type RelationshipBaseline = {
  tender_id: string;
  baseline_version: string;
  source_audit_version: string;
  generated_at: string;
  counts: {
    relationship_edge_count: number;
    unresolved_reference_groups_count: number;
    ambiguous_reference_groups_count: number;
    duplicate_edge_count: number;
    self_edge_count: number;
  };
  reference_status_counts: BaselineReferenceStatusCounts;
  document_map: DocumentMapEntry[];
};

type TenderEventEvidence = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
};

type TenderEvent = {
  id: string;
  tender_id: string;
  semantic_key: string;
  event_type: string;
  title: string;
  event_date: string | null;
  event_time: string | null;
  date_precision: string;
  timezone: string | null;
  review_status: string;
  detection_origin: string;
  detector_version: string;
  source_document_id: string | null;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string | null;
  raw_date_text: string | null;
  human_event_type: string | null;
  human_title: string | null;
  human_event_date: string | null;
  human_event_time: string | null;
  human_date_precision: string | null;
  human_timezone: string | null;
  human_note: string | null;
  evidence: TenderEventEvidence[];
};

type TenderTimeline = {
  tender_id: string;
  timeline_version: string;
  generated_at: string;
  counts: {
    total_events: number;
    suggested_events: number;
    confirmed_events: number;
    rejected_events: number;
    duplicate_semantic_count: number;
  };
  events: TenderEvent[];
};

type TenderChangeTargetCandidate = {
  document_id: string;
  original_filename: string;
  processing_status: string | null;
};

type TenderChangeEvidence = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
};

type TenderChange = {
  id: string;
  tender_id: string;
  semantic_key: string;
  change_type: string;
  target_reference_key: string | null;
  target_document_id: string | null;
  target_filename: string | null;
  target_candidate_documents: TenderChangeTargetCandidate[];
  target_locator_text: string | null;
  before_text: string | null;
  after_text: string | null;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  source_event_date: string | null;
  review_status: string;
  detection_origin: string;
  detector_version: string;
  human_change_type: string | null;
  human_target_document_id: string | null;
  human_target_locator_text: string | null;
  human_before_text: string | null;
  human_after_text: string | null;
  human_note: string | null;
  evidence: TenderChangeEvidence[];
};

type TenderChanges = {
  tender_id: string;
  changes_version: string;
  generated_at: string;
  counts: {
    total_changes: number;
    suggested_changes: number;
    confirmed_changes: number;
    rejected_changes: number;
    duplicate_semantic_count: number;
  };
  changes: TenderChange[];
};

type EffectiveScopeChange = {
  id: string;
  semantic_key: string;
  review_status: string;
  change_type: string;
  target_document_id: string | null;
  target_filename: string | null;
  target_reference_key: string | null;
  target_locator_text: string | null;
  normalized_locator: string;
  before_text: string | null;
  after_text: string | null;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  source_is_current: boolean;
  temporal_status: string;
  temporal_event_date: string | null;
  temporal_event_time: string | null;
  temporal_date_precision: string | null;
  temporal_event_ids: string[];
  temporal_reason: string;
};

type TenderEffectiveStateScope = {
  scope_key: string;
  scope_kind: string;
  target_document_id: string | null;
  target_filename: string | null;
  target_reference_key: string | null;
  target_locator_text: string | null;
  normalized_locator: string;
  resolution_status: string;
  effective_mutation: EffectiveScopeChange | null;
  confirmed_mutations: EffectiveScopeChange[];
  confirmed_non_replacing_assertions: EffectiveScopeChange[];
  pending_changes: EffectiveScopeChange[];
  rejected_changes: EffectiveScopeChange[];
  non_current_confirmed_changes: EffectiveScopeChange[];
  temporal_reason: string;
  warnings: string[];
};

type TenderEffectiveState = {
  tender_id: string;
  state_version: string;
  generated_at: string;
  summary: {
    total_scopes: number;
    determined: number;
    pending_review: number;
    ambiguous_precedence: number;
    unresolved_target: number;
    no_confirmed_change: number;
  };
  scopes: TenderEffectiveStateScope[];
};

type SnapshotPendingAction = {
  category: string;
  severity: string;
  title: string;
  description: string;
  document_id: string | null;
  source_page: number | null;
  related_entity_id: string | null;
};

type SnapshotDocumentMapEntry = {
  source_document_id: string;
  source_filename: string | null;
  relationship_type: string;
  target_document_id: string;
  target_filename: string | null;
  supporting_reference_count: number;
  supporting_pages: number[];
  resolution_origin: string;
  supporting_change_ids: string[];
};

type TenderStateSnapshot = {
  tender_id: string;
  snapshot_version: string;
  generated_at: string;
  readiness: {
    code: string;
    label: string;
    reason: string;
    understanding_scope_note: string;
  };
  versions: {
    document_intelligence_audit_version: string | null;
    relationship_baseline_version: string | null;
    timeline_version: string | null;
    changes_version: string | null;
    effective_state_version: string | null;
  };
  summary: {
    documents: {
      total_documents: number;
      current_documents: number;
      non_current_documents: number;
      ready_for_analysis: number;
      pending_processing: number;
      with_normalized_content: number;
      without_normalized_content: number;
      classified: number;
      unclassified: number;
      confirmed_classifications: number;
      suggested_classifications: number;
    };
    relationships: {
      total_reference_mentions: number;
      relationship_edge_count: number;
      duplicate_edge_count: number;
      self_edge_count: number;
      unresolved_reference_groups_count: number;
      ambiguous_reference_groups_count: number;
    };
    timeline: {
      total_events: number;
      suggested_events: number;
      confirmed_events: number;
      rejected_events: number;
      duplicate_semantic_count: number;
    };
    changes: {
      total_changes: number;
      suggested_changes: number;
      confirmed_changes: number;
      rejected_changes: number;
      unresolved_target_count: number;
      ambiguous_target_count: number;
      confirmed_mutating_count: number;
      confirmed_non_replacing_count: number;
    };
    effective_state: {
      total_scopes: number;
      determined: number;
      pending_review: number;
      ambiguous_precedence: number;
      unresolved_target: number;
      no_confirmed_change: number;
    };
    pending_actions: {
      total: number;
      blocking: number;
      warning: number;
      info: number;
    };
    integrity: {
      audit_overall_readiness: string;
      total_findings: number;
      cross_layer_issue_count: number;
    };
  };
  documents: {
    matrix: Array<{
      document_id: string;
      filename: string;
      processing_status: string;
      normalized: boolean;
      classification_status: string;
      reference_analysis_status: string;
      event_count: number;
      change_count: number;
      findings_count: number;
    }>;
  };
  relationships: {
    document_map: SnapshotDocumentMapEntry[];
  };
  timeline: {
    events: TenderEvent[];
  };
  changes: {
    items: TenderChange[];
  };
  effective_state: {
    scopes: Array<{
      scope_key: string;
      target_document_id: string | null;
      target_filename: string | null;
      target_reference_key: string | null;
      target_locator_text: string | null;
      resolution_status: string;
      effective_change_id: string | null;
      pending_change_count: number;
    }>;
  };
  pending_actions: SnapshotPendingAction[];
  top_pending_actions: SnapshotPendingAction[];
};

type EvaluationModelEvidence = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  evidence_role: string;
};

type EvaluationModelPayload = {
  suggested_method: string;
  effective_method: string;
  review_status: string;
  summary: string;
  human_method: string | null;
  human_summary: string | null;
  detector_version: string;
  evidence: EvaluationModelEvidence[];
};

type EvaluationCriterionEvidence = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  evidence_role: string;
};

type EvaluationCriterion = {
  id: string;
  criterion_type: string;
  category: string | null;
  title: string;
  criterion_text: string;
  weight_value: number | null;
  weight_unit: string | null;
  threshold_operator: string | null;
  threshold_value: number | null;
  threshold_unit: string | null;
  is_exclusionary: boolean | null;
  review_status: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  human_note: string | null;
  evidence: EvaluationCriterionEvidence[];
};

type TenderEvaluation = {
  tender_id: string;
  evaluation_version: string;
  generated_at: string;
  model: EvaluationModelPayload;
  criteria_summary: {
    total: number;
    suggested: number;
    confirmed: number;
    rejected: number;
    exclusionary: number;
    scoring: number;
    gates: number;
    by_type: Record<string, number>;
    by_category: Record<string, number>;
  };
  criteria: EvaluationCriterion[];
};

type RequirementCandidateEvidence = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  document_page_id: string | null;
  normalized_content_id: string | null;
};

type RequirementCandidate = {
  id: string;
  tender_id: string;
  semantic_key: string;
  requirement_text: string;
  actor_text: string | null;
  modality_text: string | null;
  review_status: string;
  detection_origin: string;
  detector_version: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  document_page_id: string | null;
  normalized_content_id: string | null;
  created_at: string;
  updated_at: string;
  evidence: RequirementCandidateEvidence[];
};

type TenderRequirementCandidates = {
  tender_id: string;
  requirements_version: string;
  generated_at: string;
  summary: {
    total: number;
    suggested: number;
    confirmed: number;
    rejected: number;
    documents_with_candidates: number;
    pages_with_candidates: number;
    explicit_actor_count: number;
    by_modality: Record<string, number>;
  };
  candidates: RequirementCandidate[];
};

type RequirementSourceOccurrence = {
  candidate_id: string;
  source_document_id: string;
  source_filename: string | null;
  source_page: number | null;
  requirement_text: string;
  source_excerpt: string;
  actor_text: string | null;
  modality_text: string | null;
  document_page_id: string | null;
  normalized_content_id: string | null;
  is_primary_source: boolean;
  link_origin: string;
};

type NormalizedRequirement = {
  id: string;
  tender_id: string;
  canonical_key: string;
  canonical_text: string;
  category: string;
  normalization_status: string;
  normalizer_version: string;
  normalization_confidence: number | null;
  normalization_reason: string | null;
  source_occurrence_count: number;
  primary_source: RequirementSourceOccurrence | null;
  candidates: RequirementSourceOccurrence[];
  created_at: string;
  updated_at: string;
};

type TenderRequirements = {
  tender_id: string;
  normalizer_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    candidate_count: number;
    requirement_count: number;
    normalized_count: number;
    review_required_count: number;
    merged_requirement_count: number;
    single_source_requirement_count: number;
    category_counts: Record<string, number>;
    unknown_count: number;
  };
  requirements: NormalizedRequirement[];
};

type RequirementEvidenceExpectation = {
  id: string;
  requirement_semantics_id: string;
  requirement_id: string;
  evidence_type: string;
  evidence_description: string;
  source_candidate_id: string | null;
  source_document_id: string | null;
  source_filename: string | null;
  source_page: number | null;
  source_excerpt: string;
  analyzer_version: string;
  created_at: string;
  updated_at: string;
};

type RequirementSemanticItem = {
  requirement_id: string;
  canonical_text: string;
  category: string;
  normalization_status: string;
  applicability: string;
  condition_text: string | null;
  interpretation_status: string;
  interpretation_reason: string | null;
  evidence_mode: string;
  expected_evidence: RequirementEvidenceExpectation[];
  primary_source: RequirementSourceOccurrence | null;
};

type TenderRequirementSemantics = {
  tender_id: string;
  analyzer_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    requirement_count: number;
    mandatory_count: number;
    conditional_count: number;
    unknown_applicability_count: number;
    determined_count: number;
    review_required_count: number;
    explicit_artifact_count: number;
    direct_verification_count: number;
    unspecified_evidence_count: number;
    evidence_review_required_count: number;
    evidence_expectation_count: number;
    evidence_type_counts: Record<string, number>;
  };
  requirements: RequirementSemanticItem[];
};

type RequirementVersionLink = {
  id: string;
  change_id: string;
  link_kind: string;
  matching_basis: string;
  target_locator_text: string | null;
  before_text: string | null;
  after_text: string | null;
  predecessor_requirement_id: string | null;
  predecessor_canonical_text: string | null;
  successor_requirement_id: string | null;
  successor_canonical_text: string | null;
  analyzer_version: string;
  created_at: string;
  updated_at: string;
};

type RequirementEffectiveItem = {
  requirement_id: string;
  canonical_text: string;
  category: string;
  normalization_status: string;
  effective_status: string;
  effective_source_document_id: string | null;
  effective_source_filename: string | null;
  source_occurrence_count: number;
  primary_source: RequirementSourceOccurrence | null;
  applicability: string;
  interpretation_status: string;
  evidence_mode: string;
  evidence_reasons: string[];
};

type TenderRequirementEffectiveState = {
  tender_id: string;
  analyzer_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    requirement_count: number;
    effective_count: number;
    superseded_count: number;
    ambiguous_count: number;
    unresolved_count: number;
    version_link_count: number;
  };
  requirements: RequirementEffectiveItem[];
  version_links: RequirementVersionLink[];
};

type RequirementMatrixItem = {
  requirement_id: string;
  canonical_text: string;
  category: string;
  normalization_status: string;
  source_occurrence_count: number;
  primary_source: RequirementSourceOccurrence | null;
  applicability: string;
  condition_text: string | null;
  interpretation_status: string;
  interpretation_reason: string | null;
  evidence_mode: string;
  expected_evidence: RequirementEvidenceExpectation[];
  effective_status: string;
  effective_source_document_id: string | null;
  effective_source_filename: string | null;
  effective_reasons: string[];
  system_warnings: string[];
  representation_fingerprint: string;
  review_status: string;
  review_note: string | null;
  reviewed_fingerprint: string | null;
  review_freshness: string;
  reviewed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

type TenderRequirementMatrix = {
  tender_id: string;
  matrix_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    total_requirements: number;
    effective_requirements: number;
    pending_review_count: number;
    approved_count: number;
    needs_review_count: number;
    rejected_count: number;
    current_review_count: number;
    stale_review_count: number;
    not_reviewed_count: number;
  };
  requirements: RequirementMatrixItem[];
};

type CompanyOption = {
  id: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  status: string;
};

type MatchEvidenceSourceDocument = {
  id: string;
  company_id: string;
  original_filename: string;
  document_type: string | null;
  label: string | null;
  status: string;
  archived_at: string | null;
  revision_number: number;
  is_current: boolean;
};

type MatchEvidenceReview = {
  id: string;
  company_id: string;
  company_evidence_id: string;
  review_status: string;
  review_note: string | null;
  reviewed_fingerprint: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

type MatchCompanyEvidence = {
  id: string;
  company_id: string;
  company_document_id: string;
  evidence_type: string;
  subject_kind: string;
  subject_name: string | null;
  canonical_statement: string;
  issuer: string | null;
  reference_number: string | null;
  issued_on: string | null;
  valid_from: string | null;
  valid_until: string | null;
  period_start: string | null;
  period_end: string | null;
  analysis_status: string;
  origin: string;
  extractor_version: string;
  source_page: number | null;
  source_locator: string | null;
  source_excerpt: string;
  semantic_fingerprint: string;
  system_warnings: string[];
  review_freshness: string;
  created_at: string;
  updated_at: string;
  source_document: MatchEvidenceSourceDocument;
  review: MatchEvidenceReview | null;
};

type EvidenceMatchReview = {
  id: string;
  match_id: string;
  tender_id: string;
  company_id: string;
  review_status: string;
  review_note: string | null;
  reviewed_fingerprint: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

type RequirementEvidenceMatch = {
  id: string;
  tender_id: string;
  requirement_id: string;
  company_id: string;
  company_evidence_id: string;
  match_strength: string;
  match_basis: string[];
  match_rationale: string;
  system_warnings: string[];
  origin: string;
  matcher_version: string;
  requirement_fingerprint: string;
  evidence_fingerprint: string;
  match_fingerprint: string;
  is_active: boolean;
  review_freshness: string;
  created_at: string;
  updated_at: string;
  company_evidence: MatchCompanyEvidence;
  review: EvidenceMatchReview | null;
};

type RequirementEvidenceMatchRequirement = {
  requirement_id: string;
  canonical_text: string;
  category: string;
  normalization_status: string;
  source_occurrence_count: number;
  primary_source: RequirementSourceOccurrence | null;
  applicability: string;
  condition_text: string | null;
  interpretation_status: string;
  interpretation_reason: string | null;
  evidence_mode: string;
  expected_evidence: RequirementEvidenceExpectation[];
  effective_status: string;
  effective_source_document_id: string | null;
  effective_source_filename: string | null;
  effective_reasons: string[];
  requirement_system_warnings: string[];
  requirement_review_status: string;
  requirement_review_note: string | null;
  requirement_review_freshness: string;
  representation_fingerprint: string;
  matching_warnings: string[];
  candidate_count: number;
  matches: RequirementEvidenceMatch[];
};

type TenderRequirementEvidenceMatches = {
  tender_id: string;
  company_id: string;
  matcher_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    requirements_evaluated: number;
    requirements_with_candidate_evidence: number;
    candidate_associations: number;
    strong_candidates: number;
    possible_candidates: number;
    review_required_candidates: number;
    human_confirmed_associations: number;
    rejected_associations: number;
  };
  requirements: RequirementEvidenceMatchRequirement[];
};

type ComplianceCheck = {
  id: string;
  assessment_id: string;
  check_type: string;
  check_status: string;
  expected_value: string | null;
  observed_value: string | null;
  rationale: string;
  company_evidence_id: string | null;
  match_id: string | null;
  created_at: string;
  company_evidence: MatchCompanyEvidence | null;
  match: RequirementEvidenceMatch | null;
};

type ComplianceRequirementContext = {
  requirement_id: string;
  canonical_text: string;
  category: string;
  applicability: string;
  condition_text: string | null;
  effective_status: string;
  interpretation_status: string;
  evidence_mode: string;
  expected_evidence: RequirementEvidenceExpectation[];
  review_status: string;
  review_freshness: string;
  primary_source: RequirementSourceOccurrence | null;
  representation_fingerprint: string;
};

type ComplianceAssessment = {
  id: string;
  tender_id: string;
  company_id: string;
  requirement_id: string;
  system_status: string;
  applicability_context: string;
  assessment_summary: string;
  warning_codes: string[];
  evaluator_version: string;
  assessment_fingerprint: string;
  evaluated_at: string;
  created_at: string;
  updated_at: string;
  requirement: ComplianceRequirementContext;
  company: { id: string; name: string };
  checks: ComplianceCheck[];
};

type TenderComplianceAssessments = {
  tender_id: string;
  company_id: string;
  evaluator_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    requirements_considered: number;
    supported_count: number;
    partially_supported_count: number;
    not_supported_count: number;
    review_required_count: number;
    not_evaluated_count: number;
    condition_unresolved_count: number;
  };
  assessments: ComplianceAssessment[];
};

type ComplianceDecision = {
  id: string | null;
  tender_id: string;
  company_id: string;
  requirement_id: string;
  decision_status: string;
  decision_note: string | null;
  reviewed_assessment_fingerprint: string | null;
  decided_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  freshness: string;
};

type ComplianceReviewRow = {
  requirement_id: string;
  requirement: ComplianceRequirementContext;
  system_assessment: ComplianceAssessment;
  human_decision: ComplianceDecision;
  decision_relation: string;
};

type TenderComplianceReview = {
  tender_id: string;
  company_id: string;
  generated_at: string;
  scope_note: string;
  summary: {
    requirements_reviewable: number;
    pending_count: number;
    complies_count: number;
    does_not_comply_count: number;
    needs_review_count: number;
    not_applicable_count: number;
    aligned_count: number;
    human_override_count: number;
    system_undecided_count: number;
    stale_count: number;
    current_count: number;
    not_reviewed_count: number;
  };
  rows: ComplianceReviewRow[];
};

const API_URL = "http://localhost:8000";
const SELECTED_TENDER_STORAGE_KEY = "licitia_selected_tender_id";

function App() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<TenderDocument[]>([]);
  const [title, setTitle] = useState("");
  const [institutionProfile, setInstitutionProfile] = useState("");
  const [externalReference, setExternalReference] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResults, setImportResults] = useState<ImportResult[]>([]);
  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);
  const [selectedRevisionTargetId, setSelectedRevisionTargetId] = useState<string>("");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [documentPages, setDocumentPages] = useState<DocumentPage[]>([]);
  const [documentPagesLoading, setDocumentPagesLoading] = useState(false);
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(null);
  const [ocrProviders, setOcrProviders] = useState<OcrProvider[]>([]);
  const [ocrMode, setOcrMode] = useState("AUTO");
  const [ocrRunning, setOcrRunning] = useState(false);
  const [classificationResult, setClassificationResult] = useState<ClassificationResult | null>(null);
  const [classificationLoading, setClassificationLoading] = useState(false);
  const [referenceAnalysis, setReferenceAnalysis] = useState<ReferenceAnalysis | null>(null);
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceTargetSelections, setReferenceTargetSelections] = useState<Record<string, string>>({});
  const [audit, setAudit] = useState<DocumentIntelligenceAudit | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [relationshipBaseline, setRelationshipBaseline] = useState<RelationshipBaseline | null>(null);
  const [relationshipBaselineLoading, setRelationshipBaselineLoading] = useState(false);
  const [timeline, setTimeline] = useState<TenderTimeline | null>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [changes, setChanges] = useState<TenderChanges | null>(null);
  const [changesLoading, setChangesLoading] = useState(false);
  const [effectiveState, setEffectiveState] = useState<TenderEffectiveState | null>(null);
  const [effectiveStateLoading, setEffectiveStateLoading] = useState(false);
  const [stateSnapshot, setStateSnapshot] = useState<TenderStateSnapshot | null>(null);
  const [stateSnapshotLoading, setStateSnapshotLoading] = useState(false);
  const [evaluation, setEvaluation] = useState<TenderEvaluation | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [requirementCandidates, setRequirementCandidates] = useState<TenderRequirementCandidates | null>(null);
  const [requirementCandidatesLoading, setRequirementCandidatesLoading] = useState(false);
  const [requirements, setRequirements] = useState<TenderRequirements | null>(null);
  const [requirementsLoading, setRequirementsLoading] = useState(false);
  const [requirementSemantics, setRequirementSemantics] = useState<TenderRequirementSemantics | null>(null);
  const [requirementSemanticsLoading, setRequirementSemanticsLoading] = useState(false);
  const [requirementEffectiveState, setRequirementEffectiveState] = useState<TenderRequirementEffectiveState | null>(null);
  const [requirementEffectiveStateLoading, setRequirementEffectiveStateLoading] = useState(false);
  const [requirementMatrix, setRequirementMatrix] = useState<TenderRequirementMatrix | null>(null);
  const [requirementMatrixLoading, setRequirementMatrixLoading] = useState(false);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [selectedMatchCompanyId, setSelectedMatchCompanyId] = useState<string>("");
  const [companyEvidenceOptions, setCompanyEvidenceOptions] = useState<MatchCompanyEvidence[]>([]);
  const [companyEvidenceOptionsLoading, setCompanyEvidenceOptionsLoading] = useState(false);
  const [requirementEvidenceMatches, setRequirementEvidenceMatches] = useState<TenderRequirementEvidenceMatches | null>(null);
  const [requirementEvidenceMatchesLoading, setRequirementEvidenceMatchesLoading] = useState(false);
  const [complianceAssessments, setComplianceAssessments] = useState<TenderComplianceAssessments | null>(null);
  const [complianceAssessmentsLoading, setComplianceAssessmentsLoading] = useState(false);
  const [complianceReview, setComplianceReview] = useState<TenderComplianceReview | null>(null);
  const [complianceReviewLoading, setComplianceReviewLoading] = useState(false);
  const [decisionSavingRequirementId, setDecisionSavingRequirementId] = useState<string | null>(null);
  const [decisionNotesByRequirement, setDecisionNotesByRequirement] = useState<Record<string, string>>({});
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [editEventType, setEditEventType] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editTime, setEditTime] = useState("");
  const [editNote, setEditNote] = useState("");
  const [editingChangeId, setEditingChangeId] = useState<string | null>(null);
  const [editChangeType, setEditChangeType] = useState("");
  const [editChangeTargetDocumentId, setEditChangeTargetDocumentId] = useState("");
  const [editChangeLocator, setEditChangeLocator] = useState("");
  const [editChangeBeforeText, setEditChangeBeforeText] = useState("");
  const [editChangeAfterText, setEditChangeAfterText] = useState("");
  const [editChangeNote, setEditChangeNote] = useState("");
  const documentRequestRef = useRef(0);

  const EVENT_TYPE_OPTIONS = [
    "TENDER_PUBLICATION",
    "BIDDING_RULES_PUBLICATION",
    "SITE_VISIT",
    "CLARIFICATION_MEETING",
    "PROPOSAL_SUBMISSION_DEADLINE",
    "TECHNICAL_OPENING",
    "ECONOMIC_OPENING",
    "AWARD_ANNOUNCEMENT",
    "CONTRACT_SIGNATURE_DEADLINE",
    "ADDENDUM_PUBLICATION",
    "CANCELLATION",
  ];

  const CHANGE_TYPE_OPTIONS = [
    "CLARIFIES",
    "MODIFIES",
    "REPLACES",
    "ADDS",
    "REMOVES",
    "CORRECTS",
    "CONFIRMS",
    "OTHER",
    "UNKNOWN",
  ];

  const EVALUATION_METHOD_OPTIONS = [
    "BINARY_COMPLIANCE",
    "POINTS_PERCENTAGES",
    "COST_BENEFIT",
    "LOWEST_EVALUATED_PRICE",
    "TECHNICAL_ECONOMIC_COMBINED",
    "MULTI_STAGE",
    "MIXED",
    "OTHER",
    "UNKNOWN",
  ];

  const loadTenders = async () => {
    try {
      const response = await axios.get<Tender[]>(`${API_URL}/tenders`);
      setTenders(response.data);

      const storedTenderId = window.localStorage.getItem(SELECTED_TENDER_STORAGE_KEY);
      const isStoredTenderValid = storedTenderId && response.data.some((tender) => tender.id === storedTenderId);

      if (storedTenderId && isStoredTenderValid) {
        setSelectedTenderId(storedTenderId);
        return;
      }

      window.localStorage.removeItem(SELECTED_TENDER_STORAGE_KEY);
      setSelectedTenderId(null);
    } catch (err) {
      setError("Unable to load tenders from the backend.");
    }
  };

  const handleSelectTender = (tenderId: string) => {
    setSelectedTenderId(tenderId);
    window.localStorage.setItem(SELECTED_TENDER_STORAGE_KEY, tenderId);
  };

  const loadDocuments = async (tenderId: string) => {
    const requestId = ++documentRequestRef.current;
    setDocumentsLoading(true);
    setDocumentsError(null);

    try {
      const response = await axios.get<TenderDocument[]>(`${API_URL}/tenders/${tenderId}/documents`);

      if (requestId !== documentRequestRef.current) {
        return;
      }

      setDocuments(response.data);
    } catch (err) {
      if (requestId !== documentRequestRef.current) {
        return;
      }

      setDocuments([]);
      setDocumentsError("No fue posible cargar los documentos.");
    } finally {
      if (requestId === documentRequestRef.current) {
        setDocumentsLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadTenders();
    void loadCompanies();
  }, []);

  useEffect(() => {
    if (!selectedTenderId) {
      setDocuments([]);
      setDocumentsError(null);
      setDocumentsLoading(false);
      setSelectedDocumentId(null);
      setReferenceAnalysis(null);
      setAudit(null);
      setRelationshipBaseline(null);
      setTimeline(null);
      setChanges(null);
      setEffectiveState(null);
      setStateSnapshot(null);
      setEvaluation(null);
      setRequirementCandidates(null);
      setRequirements(null);
      setRequirementSemantics(null);
      setRequirementEffectiveState(null);
      setRequirementMatrix(null);
      setRequirementEvidenceMatches(null);
      setComplianceAssessments(null);
      setComplianceReview(null);
      setDecisionNotesByRequirement({});
      return;
    }

    setSelectedDocumentId(null);
    void loadDocuments(selectedTenderId);
    void loadOcrProviders();
    void loadDocumentIntelligenceAudit(selectedTenderId);
    void loadRelationshipBaseline(selectedTenderId);
    void loadTenderTimeline(selectedTenderId);
    void loadTenderChanges(selectedTenderId);
    void loadEffectiveState(selectedTenderId);
    void loadTenderStateSnapshot(selectedTenderId);
    void loadTenderEvaluation(selectedTenderId);
    void loadTenderRequirementCandidates(selectedTenderId);
    void loadTenderRequirements(selectedTenderId);
    void loadTenderRequirementSemantics(selectedTenderId);
    void loadTenderRequirementEffectiveState(selectedTenderId);
    void loadTenderRequirementMatrix(selectedTenderId);
  }, [selectedTenderId]);

  useEffect(() => {
    if (!selectedMatchCompanyId) {
      setCompanyEvidenceOptions([]);
      setRequirementEvidenceMatches(null);
      setComplianceAssessments(null);
      setComplianceReview(null);
      setDecisionNotesByRequirement({});
      return;
    }

    void loadCompanyEvidenceOptions(selectedMatchCompanyId);

    if (selectedTenderId) {
      void loadRequirementEvidenceMatches(selectedTenderId, selectedMatchCompanyId);
      void loadComplianceAssessments(selectedTenderId, selectedMatchCompanyId);
      void loadComplianceReview(selectedTenderId, selectedMatchCompanyId);
    }
  }, [selectedTenderId, selectedMatchCompanyId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");

    if (!title.trim()) {
      setError("Tender title is required.");
      return;
    }

    setLoading(true);

    try {
      await axios.post(`${API_URL}/tenders`, {
        title: title.trim(),
        institution_profile: institutionProfile.trim() || null,
        external_reference: externalReference.trim() || null,
      });

      setTitle("");
      setInstitutionProfile("");
      setExternalReference("");
      await loadTenders();
    } catch (err) {
      setError("Unable to create the Tender.");
    } finally {
      setLoading(false);
    }
  };

  const resolveConflict = async (action: "IMPORT_INDEPENDENT" | "NEW_REVISION") => {
    if (!selectedTenderId || !pendingConflict) {
      return;
    }

    setImporting(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("files", pendingConflict.file);
      if (pendingConflict.sourceRelativePath) {
        formData.append("source_relative_paths", pendingConflict.sourceRelativePath);
      }
      formData.append("conflict_action", action);

      if (action === "NEW_REVISION") {
        if (!selectedRevisionTargetId) {
          setError("Debe seleccionar un documento actual para crear una revisión.");
          return;
        }
        formData.append("revision_of_document_id", selectedRevisionTargetId);
      }

      const response = await axios.post<ImportResult[]>(`${API_URL}/tenders/${selectedTenderId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setImportResults(response.data);
      setPendingConflict(null);
      setSelectedRevisionTargetId("");
      await loadDocuments(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo resolver el conflicto del documento.");
    } finally {
      setImporting(false);
    }
  };

  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!selectedTenderId) {
      setError("Select a Tender before importing documents.");
      return;
    }

    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }

    setImporting(true);
    setError("");

    try {
      const formData = new FormData();
      const relativePaths: string[] = [];

      selectedFiles.forEach((file) => {
        const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || "";
        formData.append("files", file);
        relativePaths.push(relativePath);
      });

      relativePaths.forEach((item) => formData.append("source_relative_paths", item));

      const response = await axios.post<ImportResult[]>(`${API_URL}/tenders/${selectedTenderId}/documents/import`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const conflicts = response.data.filter((result) => result.status === "NAME_CONFLICT");
      if (conflicts.length > 0 && selectedFiles.length > 0) {
        const conflictFile = selectedFiles[0];
        const candidates = documents.filter((document) => document.original_filename === conflicts[0].filename);
        setPendingConflict({
          file: conflictFile,
          sourceRelativePath: relativePaths[0] || null,
          filename: conflicts[0].filename,
          candidates,
        });
        if (candidates[0]) {
          setSelectedRevisionTargetId(candidates[0].id);
        }
      }

      setImportResults(response.data);
      await loadDocuments(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("Unable to import the selected documents.");
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? null;
  const selectedDocumentUrl =
    selectedTenderId && selectedDocumentId ? `${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/content` : null;
  const selectedPage = documentPages.find((page) => page.page_number === selectedPageNumber) ?? null;

  const loadDocumentPages = async (tenderId: string, documentId: string) => {
    setDocumentPagesLoading(true);
    try {
      const response = await axios.get<DocumentPage[]>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/pages`);
      setDocumentPages(response.data);
      setSelectedPageNumber(response.data[0]?.page_number ?? null);
    } catch (err) {
      setDocumentPages([]);
      setSelectedPageNumber(null);
    } finally {
      setDocumentPagesLoading(false);
    }
  };

  const handleExtractPdfText = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setDocumentPagesLoading(true);
    try {
      await axios.post(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/extract-pages`);
      await loadDocuments(selectedTenderId);
      await loadDocumentPages(selectedTenderId, selectedDocumentId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo extraer el texto del PDF.");
    } finally {
      setDocumentPagesLoading(false);
    }
  };

  const loadOcrProviders = async () => {
    try {
      const response = await axios.get<OcrProvider[]>(`${API_URL}/ocr/providers`);
      setOcrProviders(response.data);
    } catch (err) {
      setOcrProviders([]);
    }
  };

  const handleRunOcr = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setOcrRunning(true);
    try {
      const pageSelection = selectedPageNumber ? [selectedPageNumber] : undefined;
      await axios.post(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/ocr`, {
        provider: ocrMode,
        page_numbers: pageSelection,
        force: false,
      });
      await loadDocumentPages(selectedTenderId, selectedDocumentId);
      await loadOcrProviders();
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo ejecutar el OCR del documento.");
    } finally {
      setOcrRunning(false);
    }
  };

  const loadDocumentClassification = async (tenderId: string, documentId: string) => {
    setClassificationLoading(true);
    try {
      const response = await axios.get<ClassificationResult>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/classification`);
      setClassificationResult(response.data);
    } catch (err) {
      setClassificationResult(null);
    } finally {
      setClassificationLoading(false);
    }
  };

  const loadDocumentReferences = async (tenderId: string, documentId: string) => {
    setReferenceLoading(true);
    try {
      const response = await axios.get<ReferenceAnalysis>(`${API_URL}/tenders/${tenderId}/documents/${documentId}/references`);
      setReferenceAnalysis(response.data);
    } catch (err) {
      setReferenceAnalysis(null);
    } finally {
      setReferenceLoading(false);
    }
  };

  const handleAnalyzeReferences = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setReferenceLoading(true);
    try {
      const response = await axios.post<ReferenceAnalysis>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/analyze-references`);
      setReferenceAnalysis(response.data);
      await loadRelationshipBaseline(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudieron analizar las referencias del documento.");
    } finally {
      setReferenceLoading(false);
    }
  };

  const handleReferenceDecision = async (referenceId: string, action: string) => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const payload: Record<string, string> = {
        action,
      };
      if (action === "RESOLVE_TO_DOCUMENT") {
        const selectedTarget = referenceTargetSelections[referenceId];
        if (!selectedTarget) {
          setError("Seleccione un documento destino para resolver la referencia.");
          return;
        }
        payload.human_target_document_id = selectedTarget;
      }
      const response = await axios.patch<ReferenceAnalysis>(`${API_URL}/tenders/${selectedTenderId}/references/${referenceId}`, payload);
      setReferenceAnalysis(response.data);
      await loadRelationshipBaseline(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo guardar la decisión de referencia.");
    }
  };

  const loadDocumentIntelligenceAudit = async (tenderId: string) => {
    setAuditLoading(true);
    try {
      const response = await axios.get<DocumentIntelligenceAudit>(`${API_URL}/tenders/${tenderId}/document-intelligence-audit`);
      setAudit(response.data);
    } catch (err) {
      setAudit(null);
    } finally {
      setAuditLoading(false);
    }
  };

  const handleRunDocumentIntelligenceAudit = async () => {
    if (!selectedTenderId) {
      return;
    }

    setAuditLoading(true);
    try {
      const response = await axios.post<DocumentIntelligenceAudit>(`${API_URL}/tenders/${selectedTenderId}/audit-document-intelligence`);
      setAudit(response.data);
      await loadRelationshipBaseline(selectedTenderId);
      await loadTenderChanges(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo auditar el estado documental del expediente.");
    } finally {
      setAuditLoading(false);
    }
  };

  const loadRelationshipBaseline = async (tenderId: string) => {
    setRelationshipBaselineLoading(true);
    try {
      const response = await axios.get<RelationshipBaseline>(`${API_URL}/tenders/${tenderId}/relationship-baseline`);
      setRelationshipBaseline(response.data);
    } catch (err) {
      setRelationshipBaseline(null);
    } finally {
      setRelationshipBaselineLoading(false);
    }
  };

  const loadTenderTimeline = async (tenderId: string) => {
    setTimelineLoading(true);
    try {
      const response = await axios.get<TenderTimeline>(`${API_URL}/tenders/${tenderId}/events`);
      setTimeline(response.data);
    } catch (err) {
      setTimeline(null);
    } finally {
      setTimelineLoading(false);
    }
  };

  const loadTenderChanges = async (tenderId: string) => {
    setChangesLoading(true);
    try {
      const response = await axios.get<TenderChanges>(`${API_URL}/tenders/${tenderId}/changes`);
      setChanges(response.data);
    } catch (err) {
      setChanges(null);
    } finally {
      setChangesLoading(false);
    }
  };

  const loadEffectiveState = async (tenderId: string) => {
    setEffectiveStateLoading(true);
    try {
      const response = await axios.get<TenderEffectiveState>(`${API_URL}/tenders/${tenderId}/effective-state`);
      setEffectiveState(response.data);
    } catch (err) {
      setEffectiveState(null);
    } finally {
      setEffectiveStateLoading(false);
    }
  };

  const loadTenderStateSnapshot = async (tenderId: string) => {
    setStateSnapshotLoading(true);
    try {
      const response = await axios.get<TenderStateSnapshot>(`${API_URL}/tenders/${tenderId}/state-snapshot`);
      setStateSnapshot(response.data);
    } catch (err) {
      setStateSnapshot(null);
    } finally {
      setStateSnapshotLoading(false);
    }
  };

  const loadTenderEvaluation = async (tenderId: string) => {
    setEvaluationLoading(true);
    try {
      const response = await axios.get<TenderEvaluation>(`${API_URL}/tenders/${tenderId}/evaluation`);
      setEvaluation(response.data);
    } catch (err) {
      setEvaluation(null);
    } finally {
      setEvaluationLoading(false);
    }
  };

  const loadTenderRequirementCandidates = async (tenderId: string) => {
    setRequirementCandidatesLoading(true);
    try {
      const response = await axios.get<TenderRequirementCandidates>(`${API_URL}/tenders/${tenderId}/requirement-candidates`);
      setRequirementCandidates(response.data);
    } catch (err) {
      setRequirementCandidates(null);
    } finally {
      setRequirementCandidatesLoading(false);
    }
  };

  const loadTenderRequirements = async (tenderId: string) => {
    setRequirementsLoading(true);
    try {
      const response = await axios.get<TenderRequirements>(`${API_URL}/tenders/${tenderId}/requirements`);
      setRequirements(response.data);
    } catch (err) {
      setRequirements(null);
    } finally {
      setRequirementsLoading(false);
    }
  };

  const loadTenderRequirementSemantics = async (tenderId: string) => {
    setRequirementSemanticsLoading(true);
    try {
      const response = await axios.get<TenderRequirementSemantics>(`${API_URL}/tenders/${tenderId}/requirement-semantics`);
      setRequirementSemantics(response.data);
    } catch (err) {
      setRequirementSemantics(null);
    } finally {
      setRequirementSemanticsLoading(false);
    }
  };

  const loadTenderRequirementEffectiveState = async (tenderId: string) => {
    setRequirementEffectiveStateLoading(true);
    try {
      const response = await axios.get<TenderRequirementEffectiveState>(`${API_URL}/tenders/${tenderId}/requirement-effective-state`);
      setRequirementEffectiveState(response.data);
    } catch (err) {
      setRequirementEffectiveState(null);
    } finally {
      setRequirementEffectiveStateLoading(false);
    }
  };

  const loadTenderRequirementMatrix = async (tenderId: string) => {
    setRequirementMatrixLoading(true);
    try {
      const response = await axios.get<TenderRequirementMatrix>(`${API_URL}/tenders/${tenderId}/requirement-matrix`);
      setRequirementMatrix(response.data);
    } catch (err) {
      setRequirementMatrix(null);
    } finally {
      setRequirementMatrixLoading(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const response = await axios.get<CompanyOption[]>(`${API_URL}/companies`);
      setCompanies(response.data);
      if (response.data.length === 0) {
        setSelectedMatchCompanyId("");
        return;
      }
      if (!response.data.some((company) => company.id === selectedMatchCompanyId)) {
        setSelectedMatchCompanyId(response.data[0].id);
      }
    } catch (err) {
      setError("No se pudieron cargar las empresas para el matching de evidencia.");
    }
  };

  const loadCompanyEvidenceOptions = async (companyId: string) => {
    setCompanyEvidenceOptionsLoading(true);
    try {
      const response = await axios.get<{ evidence: MatchCompanyEvidence[] }>(`${API_URL}/companies/${companyId}/evidence?current_source_only=true`);
      setCompanyEvidenceOptions(response.data.evidence);
    } catch (err) {
      setCompanyEvidenceOptions([]);
    } finally {
      setCompanyEvidenceOptionsLoading(false);
    }
  };

  const loadRequirementEvidenceMatches = async (tenderId: string, companyId: string) => {
    setRequirementEvidenceMatchesLoading(true);
    try {
      const response = await axios.get<TenderRequirementEvidenceMatches>(`${API_URL}/tenders/${tenderId}/companies/${companyId}/evidence-match-candidates`);
      setRequirementEvidenceMatches(response.data);
    } catch (err) {
      setRequirementEvidenceMatches(null);
    } finally {
      setRequirementEvidenceMatchesLoading(false);
    }
  };

  const loadComplianceAssessments = async (tenderId: string, companyId: string) => {
    setComplianceAssessmentsLoading(true);
    try {
      const response = await axios.get<TenderComplianceAssessments>(
        `${API_URL}/tenders/${tenderId}/companies/${companyId}/compliance-assessments`,
      );
      setComplianceAssessments(response.data);
    } catch (err) {
      setComplianceAssessments(null);
    } finally {
      setComplianceAssessmentsLoading(false);
    }
  };

  const loadComplianceReview = async (tenderId: string, companyId: string) => {
    setComplianceReviewLoading(true);
    try {
      const response = await axios.get<TenderComplianceReview>(
        `${API_URL}/tenders/${tenderId}/companies/${companyId}/compliance-review`,
      );
      setComplianceReview(response.data);
    } catch (err) {
      setComplianceReview(null);
    } finally {
      setComplianceReviewLoading(false);
    }
  };

  const handleAnalyzeCompliance = async () => {
    if (!selectedTenderId || !selectedMatchCompanyId) {
      return;
    }

    setComplianceAssessmentsLoading(true);
    try {
      const response = await axios.post<TenderComplianceAssessments>(
        `${API_URL}/tenders/${selectedTenderId}/companies/${selectedMatchCompanyId}/analyze-compliance`,
      );
      setComplianceAssessments(response.data);
      await loadComplianceReview(selectedTenderId, selectedMatchCompanyId);
    } catch (err) {
      setError("No se pudo ejecutar la evaluación automática de soporte documental.");
    } finally {
      setComplianceAssessmentsLoading(false);
    }
  };

  const complianceDecisionStatusLabel = (value: string) => {
    if (value === "PENDING") {
      return "Pendiente";
    }
    if (value === "COMPLIES") {
      return "Cumple";
    }
    if (value === "DOES_NOT_COMPLY") {
      return "No cumple";
    }
    if (value === "NEEDS_REVIEW") {
      return "Revisar";
    }
    if (value === "NOT_APPLICABLE") {
      return "No aplica";
    }
    return value;
  };

  const complianceDecisionFreshnessLabel = (value: string) => {
    if (value === "CURRENT") {
      return "Actual";
    }
    if (value === "STALE") {
      return "Desactualizada";
    }
    if (value === "NOT_REVIEWED") {
      return "No revisada";
    }
    return value;
  };

  const complianceDecisionRelationLabel = (value: string) => {
    if (value === "ALIGNED") {
      return "Alineada al sistema";
    }
    if (value === "HUMAN_OVERRIDE") {
      return "Override humano";
    }
    if (value === "SYSTEM_UNDECIDED") {
      return "Sistema no concluyente";
    }
    if (value === "PENDING") {
      return "Pendiente";
    }
    return value;
  };

  const isDecisionNoteRequired = (row: ComplianceReviewRow, targetStatus: string) => {
    const systemStatus = row.system_assessment.system_status;
    const effectiveStatus = row.requirement.effective_status;
    const applicabilityContext = row.system_assessment.applicability_context;

    if (targetStatus === "DOES_NOT_COMPLY" || targetStatus === "NOT_APPLICABLE") {
      return true;
    }

    if (targetStatus !== "COMPLIES" && targetStatus !== "DOES_NOT_COMPLY") {
      return false;
    }

    if (["PARTIALLY_SUPPORTED", "REVIEW_REQUIRED", "NOT_EVALUATED"].includes(systemStatus)) {
      return true;
    }

    if (["AMBIGUOUS", "UNRESOLVED"].includes(effectiveStatus)) {
      return true;
    }

    if (applicabilityContext === "CONDITION_UNRESOLVED") {
      return true;
    }

    if (targetStatus === "COMPLIES" && systemStatus === "NOT_SUPPORTED") {
      return true;
    }

    if (targetStatus === "DOES_NOT_COMPLY" && systemStatus === "SUPPORTED") {
      return true;
    }

    return false;
  };

  const handleComplianceDecisionAction = async (row: ComplianceReviewRow, decisionStatus: string) => {
    if (!selectedTenderId || !selectedMatchCompanyId) {
      return;
    }

    const noteDraft = (decisionNotesByRequirement[row.requirement_id] ?? row.human_decision.decision_note ?? "").trim();
    if (isDecisionNoteRequired(row, decisionStatus) && !noteDraft) {
      setError("La justificación es obligatoria para esta decisión humana en el contexto actual.");
      return;
    }

    setDecisionSavingRequirementId(row.requirement_id);
    try {
      const response = await axios.patch<ComplianceReviewRow>(
        `${API_URL}/tenders/${selectedTenderId}/companies/${selectedMatchCompanyId}/requirements/${row.requirement_id}/compliance-decision`,
        {
          decision_status: decisionStatus,
          decision_note: noteDraft || null,
        },
      );

      setComplianceReview((current) => {
        if (!current) {
          return current;
        }
        const updatedRows = current.rows.map((item) => (item.requirement_id === row.requirement_id ? response.data : item));
        const pendingCount = updatedRows.filter((item) => item.human_decision.decision_status === "PENDING").length;
        const compliesCount = updatedRows.filter((item) => item.human_decision.decision_status === "COMPLIES").length;
        const doesNotComplyCount = updatedRows.filter((item) => item.human_decision.decision_status === "DOES_NOT_COMPLY").length;
        const needsReviewCount = updatedRows.filter((item) => item.human_decision.decision_status === "NEEDS_REVIEW").length;
        const notApplicableCount = updatedRows.filter((item) => item.human_decision.decision_status === "NOT_APPLICABLE").length;
        const alignedCount = updatedRows.filter((item) => item.decision_relation === "ALIGNED").length;
        const humanOverrideCount = updatedRows.filter((item) => item.decision_relation === "HUMAN_OVERRIDE").length;
        const systemUndecidedCount = updatedRows.filter((item) => item.decision_relation === "SYSTEM_UNDECIDED").length;
        const staleCount = updatedRows.filter((item) => item.human_decision.freshness === "STALE").length;
        const currentCount = updatedRows.filter((item) => item.human_decision.freshness === "CURRENT").length;
        const notReviewedCount = updatedRows.filter((item) => item.human_decision.freshness === "NOT_REVIEWED").length;

        return {
          ...current,
          rows: updatedRows,
          summary: {
            requirements_reviewable: updatedRows.length,
            pending_count: pendingCount,
            complies_count: compliesCount,
            does_not_comply_count: doesNotComplyCount,
            needs_review_count: needsReviewCount,
            not_applicable_count: notApplicableCount,
            aligned_count: alignedCount,
            human_override_count: humanOverrideCount,
            system_undecided_count: systemUndecidedCount,
            stale_count: staleCount,
            current_count: currentCount,
            not_reviewed_count: notReviewedCount,
          },
        };
      });
      await loadComplianceAssessments(selectedTenderId, selectedMatchCompanyId);
      setError("");
    } catch (err) {
      setError("No se pudo registrar la decisión humana de cumplimiento.");
    } finally {
      setDecisionSavingRequirementId(null);
    }
  };

  const handleAnalyzeRequirementEvidenceMatches = async () => {
    if (!selectedTenderId || !selectedMatchCompanyId) {
      return;
    }

    setRequirementEvidenceMatchesLoading(true);
    try {
      const response = await axios.post<TenderRequirementEvidenceMatches>(
        `${API_URL}/tenders/${selectedTenderId}/companies/${selectedMatchCompanyId}/analyze-evidence-matches`,
      );
      setRequirementEvidenceMatches(response.data);
      await loadCompanyEvidenceOptions(selectedMatchCompanyId);
    } catch (err) {
      setError("No se pudieron calcular las evidencias candidatas para la empresa seleccionada.");
    } finally {
      setRequirementEvidenceMatchesLoading(false);
    }
  };

  const handleAnalyzeEvaluation = async () => {
    if (!selectedTenderId) {
      return;
    }

    setEvaluationLoading(true);
    try {
      const response = await axios.post<TenderEvaluation>(`${API_URL}/tenders/${selectedTenderId}/analyze-evaluation`);
      setEvaluation(response.data);
    } catch (err) {
      setError("No se pudo analizar el modelo de evaluacion.");
    } finally {
      setEvaluationLoading(false);
    }
  };

  const handleAnalyzeRequirements = async () => {
    if (!selectedTenderId) {
      return;
    }

    setRequirementCandidatesLoading(true);
    try {
      const response = await axios.post<TenderRequirementCandidates>(`${API_URL}/tenders/${selectedTenderId}/analyze-requirements`);
      setRequirementCandidates(response.data);
    } catch (err) {
      setError("No se pudieron extraer los requisitos detectados.");
    } finally {
      setRequirementCandidatesLoading(false);
    }
  };

  const handleNormalizeRequirements = async () => {
    if (!selectedTenderId) {
      return;
    }

    setRequirementsLoading(true);
    try {
      const response = await axios.post<TenderRequirements>(`${API_URL}/tenders/${selectedTenderId}/normalize-requirements`);
      setRequirements(response.data);
      await loadTenderRequirementMatrix(selectedTenderId);
    } catch (err) {
      setError("No se pudieron normalizar los requisitos detectados.");
    } finally {
      setRequirementsLoading(false);
    }
  };

  const handleAnalyzeRequirementSemantics = async () => {
    if (!selectedTenderId) {
      return;
    }

    setRequirementSemanticsLoading(true);
    try {
      const response = await axios.post<TenderRequirementSemantics>(`${API_URL}/tenders/${selectedTenderId}/analyze-requirement-semantics`);
      setRequirementSemantics(response.data);
      await loadTenderRequirementMatrix(selectedTenderId);
    } catch (err) {
      setError("No se pudo interpretar aplicabilidad y evidencia esperada de los requisitos.");
    } finally {
      setRequirementSemanticsLoading(false);
    }
  };

  const handleAnalyzeRequirementVersions = async () => {
    if (!selectedTenderId) {
      return;
    }

    setRequirementEffectiveStateLoading(true);
    try {
      const response = await axios.post<TenderRequirementEffectiveState>(`${API_URL}/tenders/${selectedTenderId}/analyze-requirement-versions`);
      setRequirementEffectiveState(response.data);
      await loadTenderRequirementMatrix(selectedTenderId);
    } catch (err) {
      setError("No se pudo analizar el versionado de requisitos.");
    } finally {
      setRequirementEffectiveStateLoading(false);
    }
  };

  const requirementReviewStatusLabel = (value: string) => {
    if (value === "PENDING") {
      return "Pendiente";
    }
    if (value === "APPROVED") {
      return "Validado";
    }
    if (value === "NEEDS_REVIEW") {
      return "Revisar";
    }
    if (value === "REJECTED") {
      return "Descartado como requisito";
    }
    return value;
  };

  const requirementReviewFreshnessLabel = (value: string) => {
    if (value === "CURRENT") {
      return "Vigente";
    }
    if (value === "STALE") {
      return "Desactualizada";
    }
    if (value === "NOT_REVIEWED") {
      return "Sin revisión";
    }
    return value;
  };

  const updateRequirementReview = async (requirementId: string, action: string, reviewNote: string | null = null) => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const payload: Record<string, string> = { action };
      if (reviewNote !== null) {
        payload.review_note = reviewNote;
      }
      const response = await axios.patch<TenderRequirementMatrix>(
        `${API_URL}/tenders/${selectedTenderId}/requirements/${requirementId}/review`,
        payload,
      );
      setRequirementMatrix(response.data);
    } catch (err) {
      setError("No se pudo guardar la revisión del requisito.");
    }
  };

  const handleRequirementReviewAction = async (item: RequirementMatrixItem, action: "APPROVE" | "MARK_NEEDS_REVIEW" | "REJECT" | "RESET") => {
    if (action === "REJECT") {
      const note = window.prompt("Justificación para descartar como requisito", item.review_note ?? "");
      if (note === null) {
        return;
      }
      if (!note.trim()) {
        setError("La nota es obligatoria para descartar un requisito.");
        return;
      }
      await updateRequirementReview(item.requirement_id, action, note.trim());
      return;
    }

    if (action === "MARK_NEEDS_REVIEW") {
      const note = window.prompt("Nota de revisión (opcional)", item.review_note ?? "");
      if (note === null) {
        return;
      }
      await updateRequirementReview(item.requirement_id, action, note.trim() || null);
      return;
    }

    await updateRequirementReview(item.requirement_id, action, null);
  };

  const openRequirementSource = async (source: RequirementSourceOccurrence | null) => {
    if (!selectedTenderId || !source?.source_document_id) {
      return;
    }
    setSelectedDocumentId(source.source_document_id);
    await loadDocumentPages(selectedTenderId, source.source_document_id);
    await loadDocumentClassification(selectedTenderId, source.source_document_id);
    await loadDocumentReferences(selectedTenderId, source.source_document_id);
    if (source.source_page !== null) {
      setSelectedPageNumber(source.source_page);
    }
  };

  const handleRequirementEvidenceMatchReviewAction = async (
    matchId: string,
    nextStatus: "CONFIRMED" | "NEEDS_REVIEW" | "REJECTED",
    currentNote: string | null,
  ) => {
    if (!selectedTenderId || !selectedMatchCompanyId) {
      return;
    }

    let reviewNote: string | null = null;
    if (nextStatus === "REJECTED") {
      const note = window.prompt("Justificación para descartar la asociación", currentNote ?? "");
      if (note === null) {
        return;
      }
      if (!note.trim()) {
        setError("La nota es obligatoria para descartar una asociación.");
        return;
      }
      reviewNote = note.trim();
    } else if (nextStatus === "NEEDS_REVIEW") {
      const note = window.prompt("Nota de revisión (opcional)", currentNote ?? "");
      if (note === null) {
        return;
      }
      reviewNote = note.trim() || null;
    }

    try {
      const response = await axios.patch<TenderRequirementEvidenceMatches>(
        `${API_URL}/tenders/${selectedTenderId}/companies/${selectedMatchCompanyId}/evidence-match-candidates/${matchId}/review`,
        {
          review_status: nextStatus,
          review_note: reviewNote,
        },
      );
      setRequirementEvidenceMatches(response.data);
    } catch (err) {
      setError("No se pudo guardar la revisión de la asociación requisito-evidencia.");
    }
  };

  const handleCreateManualRequirementEvidenceMatch = async (requirementId: string) => {
    if (!selectedTenderId || !selectedMatchCompanyId) {
      return;
    }

    const evidenceId = window.prompt(
      "Ingresa el ID completo de la evidencia a asociar manualmente.",
      companyEvidenceOptions[0]?.id ?? "",
    );
    if (evidenceId === null) {
      return;
    }
    if (!evidenceId.trim()) {
      setError("Debes indicar un ID de evidencia para crear una asociación manual.");
      return;
    }

    const rationale = window.prompt(
      "Justificación de la asociación manual",
      "Asociación manual confirmada por revisión humana.",
    );
    if (rationale === null) {
      return;
    }
    if (!rationale.trim()) {
      setError("La justificación es obligatoria para una asociación manual.");
      return;
    }

    try {
      const response = await axios.post<TenderRequirementEvidenceMatches>(
        `${API_URL}/tenders/${selectedTenderId}/companies/${selectedMatchCompanyId}/requirements/${requirementId}/evidence-match-candidates/manual`,
        {
          company_evidence_id: evidenceId.trim(),
          rationale: rationale.trim(),
        },
      );
      setRequirementEvidenceMatches(response.data);
    } catch (err) {
      setError("No se pudo crear la asociación manual entre requisito y evidencia.");
    }
  };

  const openRequirementEvidenceSource = (match: RequirementEvidenceMatch) => {
    const source = [
      `Documento: ${match.company_evidence.source_document.original_filename}`,
      `Tipo: ${match.company_evidence.evidence_type}`,
      `Página: ${match.company_evidence.source_page ?? "n/d"}`,
      `Locator: ${match.company_evidence.source_locator ?? "n/d"}`,
      "",
      match.company_evidence.source_excerpt,
    ].join("\n");

    window.alert(source);
  };

  const matchStrengthLabel = (value: string) => {
    if (value === "STRONG") {
      return "Fuerte";
    }
    if (value === "POSSIBLE") {
      return "Posible";
    }
    if (value === "REVIEW_REQUIRED") {
      return "Revisión requerida";
    }
    return value;
  };

  const matchReviewStatusLabel = (value: string | null) => {
    if (value === "PENDING") {
      return "Pendiente";
    }
    if (value === "CONFIRMED") {
      return "Confirmada";
    }
    if (value === "NEEDS_REVIEW") {
      return "Revisión requerida";
    }
    if (value === "REJECTED") {
      return "Descartada";
    }
    return "Sin revisión";
  };

  const matchReviewFreshnessLabel = (value: string) => {
    if (value === "FRESH") {
      return "Vigente";
    }
    if (value === "STALE") {
      return "Desactualizada";
    }
    if (value === "NOT_REVIEWED") {
      return "No revisada";
    }
    return value;
  };

  const complianceStatusLabel = (value: string) => {
    if (value === "SUPPORTED") {
      return "Evidencia suficiente";
    }
    if (value === "PARTIALLY_SUPPORTED") {
      return "Evidencia parcial";
    }
    if (value === "NOT_SUPPORTED") {
      return "Evidencia insuficiente";
    }
    if (value === "REVIEW_REQUIRED") {
      return "Requiere revisión";
    }
    if (value === "NOT_EVALUATED") {
      return "No evaluado";
    }
    return value;
  };

  const complianceApplicabilityContextLabel = (value: string) => {
    if (value === "APPLIES") {
      return "Aplica";
    }
    if (value === "CONDITION_UNRESOLVED") {
      return "Condición aún no resuelta";
    }
    if (value === "UNKNOWN") {
      return "Aplicabilidad por determinar";
    }
    return value;
  };

  const complianceCheckStatusLabel = (value: string) => {
    if (value === "PASS") {
      return "PASS";
    }
    if (value === "FAIL") {
      return "FAIL";
    }
    if (value === "UNKNOWN") {
      return "UNKNOWN";
    }
    if (value === "NOT_APPLICABLE") {
      return "N/A";
    }
    return value;
  };

  const applicabilityLabel = (value: string) => {
    if (value === "MANDATORY") {
      return "Obligatorio";
    }
    if (value === "CONDITIONAL") {
      return "Condicional";
    }
    if (value === "UNKNOWN") {
      return "Por determinar";
    }
    return value;
  };

  const interpretationStatusLabel = (value: string) => {
    if (value === "DETERMINED") {
      return "Determinado";
    }
    if (value === "REVIEW_REQUIRED") {
      return "Revisión requerida";
    }
    return value;
  };

  const evidenceModeLabel = (value: string) => {
    if (value === "EXPLICIT_ARTIFACT") {
      return "Evidencia documental";
    }
    if (value === "DIRECT_VERIFICATION") {
      return "Verificación directa";
    }
    if (value === "UNSPECIFIED") {
      return "Evidencia no especificada";
    }
    if (value === "REVIEW_REQUIRED") {
      return "Revisar fuente";
    }
    return value;
  };

  const requirementEffectiveStatusLabel = (value: string) => {
    if (value === "EFFECTIVE") {
      return "Vigente";
    }
    if (value === "SUPERSEDED") {
      return "Sustituido";
    }
    if (value === "AMBIGUOUS") {
      return "Ambiguo";
    }
    if (value === "UNRESOLVED") {
      return "No resuelto";
    }
    return value;
  };

  const handleEvaluationModelDecision = async (action: "CONFIRM" | "REJECT" | "RESET_TO_SUGGESTED") => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const response = await axios.patch<TenderEvaluation>(`${API_URL}/tenders/${selectedTenderId}/evaluation`, { action });
      setEvaluation(response.data);
    } catch (err) {
      setError("No se pudo guardar la decision del modelo de evaluacion.");
    }
  };

  const handleEvaluationModelOverride = async () => {
    if (!selectedTenderId || !evaluation) {
      return;
    }

    const method = window.prompt("Metodo de evaluacion (codigo)", evaluation.model.effective_method);
    if (method === null) {
      return;
    }
    const summary = window.prompt("Resumen de la decision", evaluation.model.summary);
    if (summary === null) {
      return;
    }

    const normalizedMethod = method.trim().toUpperCase();
    if (!EVALUATION_METHOD_OPTIONS.includes(normalizedMethod)) {
      setError("Metodo de evaluacion invalido para MVP-04.1.");
      return;
    }

    try {
      const response = await axios.patch<TenderEvaluation>(`${API_URL}/tenders/${selectedTenderId}/evaluation`, {
        action: "OVERRIDE",
        method: normalizedMethod,
        summary,
      });
      setEvaluation(response.data);
    } catch (err) {
      setError("No se pudo modificar el modelo de evaluacion.");
    }
  };

  const handleCriterionDecision = async (criterionId: string, action: "CONFIRM" | "REJECT" | "RESET_TO_SUGGESTED") => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const response = await axios.patch<TenderEvaluation>(`${API_URL}/tenders/${selectedTenderId}/evaluation-criteria/${criterionId}`, { action });
      setEvaluation(response.data);
    } catch (err) {
      setError("No se pudo guardar la decision del criterio de evaluacion.");
    }
  };

  const handleCriterionOverride = async (criterion: EvaluationCriterion) => {
    if (!selectedTenderId) {
      return;
    }

    const criterionType = window.prompt("Tipo de criterio", criterion.criterion_type);
    if (criterionType === null) {
      return;
    }
    const category = window.prompt("Categoria (opcional)", criterion.category ?? "");
    if (category === null) {
      return;
    }
    const title = window.prompt("Titulo", criterion.title);
    if (title === null) {
      return;
    }
    const criterionText = window.prompt("Texto del criterio", criterion.criterion_text);
    if (criterionText === null) {
      return;
    }
    const exclusionaryRaw = window.prompt("Es excluyente? (true/false, opcional)", criterion.is_exclusionary === null ? "" : String(criterion.is_exclusionary));
    if (exclusionaryRaw === null) {
      return;
    }

    const exclusionary = exclusionaryRaw.trim() === "" ? null : exclusionaryRaw.trim().toLowerCase() === "true";

    try {
      const response = await axios.patch<TenderEvaluation>(`${API_URL}/tenders/${selectedTenderId}/evaluation-criteria/${criterion.id}`, {
        action: "OVERRIDE",
        criterion_type: criterionType.trim().toUpperCase(),
        category: category.trim() ? category.trim().toUpperCase() : null,
        title: title.trim(),
        criterion_text: criterionText.trim(),
        is_exclusionary: exclusionary,
      });
      setEvaluation(response.data);
    } catch (err) {
      setError("No se pudo modificar el criterio de evaluacion.");
    }
  };

  const handleAnalyzeEvents = async () => {
    if (!selectedTenderId) {
      return;
    }

    setTimelineLoading(true);
    try {
      const response = await axios.post<TenderTimeline>(`${API_URL}/tenders/${selectedTenderId}/analyze-events`);
      setTimeline(response.data);
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo analizar la línea de tiempo del procedimiento.");
    } finally {
      setTimelineLoading(false);
    }
  };

  const handleAnalyzeChanges = async () => {
    if (!selectedTenderId) {
      return;
    }

    setChangesLoading(true);
    try {
      const response = await axios.post<TenderChanges>(`${API_URL}/tenders/${selectedTenderId}/analyze-changes`);
      setChanges(response.data);
      await loadRelationshipBaseline(selectedTenderId);
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudieron analizar aclaraciones y modificaciones.");
    } finally {
      setChangesLoading(false);
    }
  };

  const handleChangeDecision = async (changeId: string, action: "CONFIRM" | "REJECT" | "RESET_TO_SUGGESTED") => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const response = await axios.patch<TenderChanges>(`${API_URL}/tenders/${selectedTenderId}/changes/${changeId}`, { action });
      setChanges(response.data);
      await loadRelationshipBaseline(selectedTenderId);
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo guardar la decisión del cambio.");
    }
  };

  const handleEventDecision = async (eventId: string, action: "CONFIRM" | "REJECT" | "RESET_TO_SUGGESTED") => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const response = await axios.patch<TenderTimeline>(`${API_URL}/tenders/${selectedTenderId}/events/${eventId}`, { action });
      setTimeline(response.data);
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo guardar la decisión del evento.");
    }
  };

  const openEditEvent = (eventItem: TenderEvent) => {
    setEditingEventId(eventItem.id);
    setEditEventType(eventItem.human_event_type ?? eventItem.event_type);
    setEditTitle(eventItem.human_title ?? eventItem.title);
    setEditDate(eventItem.human_event_date ?? eventItem.event_date ?? "");
    setEditTime(eventItem.human_event_time ? eventItem.human_event_time.slice(0, 5) : eventItem.event_time ? eventItem.event_time.slice(0, 5) : "");
    setEditNote(eventItem.human_note ?? "");
  };

  const cancelEditEvent = () => {
    setEditingEventId(null);
    setEditEventType("");
    setEditTitle("");
    setEditDate("");
    setEditTime("");
    setEditNote("");
  };

  const saveEventOverride = async (eventId: string) => {
    if (!selectedTenderId) {
      return;
    }
    if (!editDate.trim()) {
      setError("La fecha del evento es obligatoria para modificar un evento.");
      return;
    }

    try {
      const payload: Record<string, string> = {
        action: "OVERRIDE",
        event_type: editEventType,
        title: editTitle,
        event_date: editDate,
        date_precision: "DAY",
        human_note: editNote,
      };
      if (editTime.trim()) {
        payload.event_time = `${editTime}:00`;
      }
      const response = await axios.patch<TenderTimeline>(`${API_URL}/tenders/${selectedTenderId}/events/${eventId}`, payload);
      setTimeline(response.data);
      cancelEditEvent();
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo modificar el evento.");
    }
  };

  const openEditChange = (changeItem: TenderChange) => {
    setEditingChangeId(changeItem.id);
    setEditChangeType(changeItem.human_change_type ?? changeItem.change_type);
    setEditChangeTargetDocumentId(changeItem.human_target_document_id ?? changeItem.target_document_id ?? "");
    setEditChangeLocator(changeItem.human_target_locator_text ?? changeItem.target_locator_text ?? "");
    setEditChangeBeforeText(changeItem.human_before_text ?? changeItem.before_text ?? "");
    setEditChangeAfterText(changeItem.human_after_text ?? changeItem.after_text ?? "");
    setEditChangeNote(changeItem.human_note ?? "");
  };

  const cancelEditChange = () => {
    setEditingChangeId(null);
    setEditChangeType("");
    setEditChangeTargetDocumentId("");
    setEditChangeLocator("");
    setEditChangeBeforeText("");
    setEditChangeAfterText("");
    setEditChangeNote("");
  };

  const saveChangeOverride = async (changeId: string) => {
    if (!selectedTenderId) {
      return;
    }

    try {
      const payload: Record<string, string> = {
        action: "OVERRIDE",
        change_type: editChangeType,
        target_locator_text: editChangeLocator,
        before_text: editChangeBeforeText,
        after_text: editChangeAfterText,
        human_note: editChangeNote,
      };
      payload.target_document_id = editChangeTargetDocumentId;

      const response = await axios.patch<TenderChanges>(`${API_URL}/tenders/${selectedTenderId}/changes/${changeId}`, payload);
      setChanges(response.data);
      cancelEditChange();
      await loadRelationshipBaseline(selectedTenderId);
      await loadEffectiveState(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo modificar el cambio detectado.");
    }
  };

  const openEventSource = async (eventItem: TenderEvent) => {
    if (!selectedTenderId || !eventItem.source_document_id) {
      return;
    }

    setSelectedDocumentId(eventItem.source_document_id);
    await loadDocumentPages(selectedTenderId, eventItem.source_document_id);
    await loadDocumentClassification(selectedTenderId, eventItem.source_document_id);
    await loadDocumentReferences(selectedTenderId, eventItem.source_document_id);
    if (eventItem.source_page !== null) {
      setSelectedPageNumber(eventItem.source_page);
    }
  };

  const openChangeSource = async (changeItem: TenderChange) => {
    if (!selectedTenderId) {
      return;
    }

    setSelectedDocumentId(changeItem.source_document_id);
    await loadDocumentPages(selectedTenderId, changeItem.source_document_id);
    await loadDocumentClassification(selectedTenderId, changeItem.source_document_id);
    await loadDocumentReferences(selectedTenderId, changeItem.source_document_id);
    if (changeItem.source_page !== null) {
      setSelectedPageNumber(changeItem.source_page);
    }
  };

  const eventStatusLabel = (status: string) => {
    if (status === "CONFIRMED") {
      return "Confirmado";
    }
    if (status === "REJECTED") {
      return "Rechazado";
    }
    if (status === "SUGGESTED") {
      return "Sugerido";
    }
    return status;
  };

  const hasHumanOverride = (eventItem: TenderEvent) => {
    return Boolean(
      eventItem.human_event_type ||
      eventItem.human_title ||
      eventItem.human_event_date ||
      eventItem.human_event_time ||
      eventItem.human_note,
    );
  };

  const changeStatusLabel = (status: string) => {
    if (status === "CONFIRMED") {
      return "Confirmado";
    }
    if (status === "REJECTED") {
      return "Rechazado";
    }
    if (status === "SUGGESTED") {
      return "Sugerido";
    }
    return status;
  };

  const hasChangeHumanOverride = (changeItem: TenderChange) => {
    return Boolean(
      changeItem.human_change_type ||
      changeItem.human_target_document_id ||
      changeItem.human_target_locator_text ||
      changeItem.human_before_text !== null ||
      changeItem.human_after_text !== null ||
      changeItem.human_note,
    );
  };

  const effectiveStatusLabel = (status: string) => {
    if (status === "DETERMINED") {
      return "Determinado";
    }
    if (status === "PENDING_REVIEW") {
      return "Pendiente de revisión";
    }
    if (status === "AMBIGUOUS_PRECEDENCE") {
      return "Orden ambiguo";
    }
    if (status === "UNRESOLVED_TARGET") {
      return "Destino no resuelto";
    }
    if (status === "NO_CONFIRMED_CHANGE") {
      return "Sin cambio confirmado";
    }
    return status;
  };

  const readinessLabel = (value: string) => {
    if (value === "UNDERSTOOD") {
      return "Comprension estructural consolidada";
    }
    if (value === "PARTIALLY_UNDERSTOOD") {
      return "Comprension parcial";
    }
    if (value === "NOT_READY") {
      return "No listo estructuralmente";
    }
    return value;
  };

  const pendingSeverityLabel = (value: string) => {
    if (value === "BLOCKING") {
      return "Bloqueante";
    }
    if (value === "WARNING") {
      return "Advertencia";
    }
    if (value === "INFO") {
      return "Informativo";
    }
    return value;
  };

  const pendingCategoryLabel = (value: string) => {
    if (value === "PROCESS_DOCUMENT") {
      return "Procesar documento";
    }
    if (value === "REVIEW_CLASSIFICATION") {
      return "Revisar clasificacion";
    }
    if (value === "RESOLVE_REFERENCE") {
      return "Resolver referencia";
    }
    if (value === "REVIEW_EVENT") {
      return "Revisar evento";
    }
    if (value === "REVIEW_CHANGE") {
      return "Revisar cambio";
    }
    if (value === "RESOLVE_CHANGE_TARGET") {
      return "Resolver destino de cambio";
    }
    if (value === "RESOLVE_PRECEDENCE") {
      return "Resolver precedencia";
    }
    if (value === "REVIEW_DOCUMENT_COLLISION") {
      return "Revisar colision de documentos";
    }
    if (value === "REPROCESS_STALE_ANALYSIS") {
      return "Reprocesar analisis desactualizado";
    }
    return value;
  };

  const evaluationReviewLabel = (value: string) => {
    if (value === "SUGGESTED") {
      return "Sugerido";
    }
    if (value === "CONFIRMED") {
      return "Confirmado";
    }
    if (value === "REJECTED") {
      return "Rechazado";
    }
    return value;
  };

  const evaluationMethodLabel = (value: string) => {
    if (value === "BINARY_COMPLIANCE") {
      return "Evaluacion binaria";
    }
    if (value === "POINTS_PERCENTAGES") {
      return "Puntos y porcentajes";
    }
    if (value === "COST_BENEFIT") {
      return "Costo-beneficio";
    }
    if (value === "LOWEST_EVALUATED_PRICE") {
      return "Menor precio evaluado";
    }
    if (value === "TECHNICAL_ECONOMIC_COMBINED") {
      return "Tecnica y economica combinada";
    }
    if (value === "MULTI_STAGE") {
      return "Multietapa";
    }
    if (value === "MIXED") {
      return "Mixto";
    }
    if (value === "OTHER") {
      return "Otro";
    }
    if (value === "UNKNOWN") {
      return "Sin evidencia suficiente";
    }
    return value;
  };

  const criterionTypeLabel = (value: string) => {
    if (value === "PASS_FAIL_RULE") {
      return "Regla cumple/no cumple";
    }
    if (value === "SCORING_COMPONENT") {
      return "Componente de puntuacion";
    }
    if (value === "MINIMUM_SCORE") {
      return "Puntaje minimo";
    }
    if (value === "WEIGHTING_RULE") {
      return "Regla de ponderacion";
    }
    if (value === "QUALIFICATION_GATE") {
      return "Condicion de paso";
    }
    if (value === "REJECTION_CAUSE") {
      return "Causa de desechamiento";
    }
    if (value === "AWARD_RULE") {
      return "Regla de adjudicacion";
    }
    if (value === "PRICE_EVALUATION_RULE") {
      return "Regla de evaluacion economica";
    }
    if (value === "TECHNICAL_EVALUATION_RULE") {
      return "Regla de evaluacion tecnica";
    }
    if (value === "ADMINISTRATIVE_EVALUATION_RULE") {
      return "Regla de evaluacion administrativa";
    }
    if (value === "LEGAL_EVALUATION_RULE") {
      return "Regla de evaluacion legal";
    }
    if (value === "EXPERIENCE_EVALUATION_RULE") {
      return "Regla de evaluacion de experiencia";
    }
    return value;
  };

  const referenceStatusLabel = (status: string) => {
    if (status === "AUTO_RESOLVED") {
      return "Resuelta";
    }
    if (status === "AMBIGUOUS") {
      return "Ambigua";
    }
    if (status === "UNRESOLVED") {
      return "No encontrada";
    }
    if (status === "HUMAN_RESOLVED") {
      return "Resuelta por usuario";
    }
    if (status === "IGNORED") {
      return "Ignorada";
    }
    return status;
  };

  const shortId = (value: string | null) => (value ? value.slice(0, 8) : "");

  const candidateLabel = (candidate: ReferenceCandidate) => {
    return `${candidate.original_filename} · ${shortId(candidate.document_id)} · ${candidate.processing_status ?? "PENDING"}`;
  };

  const groupedReferences = (() => {
    if (!referenceAnalysis) {
      return [] as Array<{
        groupKey: string;
        normalized_reference_key: string;
        resolution_status: string;
        relationship_hint: string;
        mentions: ReferenceItem[];
        page_numbers: number[];
        candidate_label: string;
        target_label: string;
      }>;
    }

    const groups = new Map<string, {
      groupKey: string;
      normalized_reference_key: string;
      resolution_status: string;
      relationship_hint: string;
      mentions: ReferenceItem[];
      page_numbers: Set<number>;
      candidate_label: string;
      target_label: string;
    }>();

    for (const mention of referenceAnalysis.references) {
      const candidateSignature = mention.ambiguous_candidates.map((item) => item.document_id).sort().join(",");
      const key = `${mention.normalized_reference_key}|${mention.resolution_status}|${candidateSignature}`;
      const candidateText = mention.ambiguous_candidates
        .map((candidate) => `${candidate.original_filename} · ${shortId(candidate.document_id)} · ${candidate.processing_status ?? "PENDING"}`)
        .join(" | ");
      const targetText = mention.resolved_target_filename
        ? `${mention.resolved_target_filename} · ${shortId(mention.resolved_target_document_id)}`
        : "-";

      const existing = groups.get(key);
      if (existing) {
        existing.mentions.push(mention);
        if (mention.page_number !== null) {
          existing.page_numbers.add(mention.page_number);
        }
        continue;
      }

      groups.set(key, {
        groupKey: key,
        normalized_reference_key: mention.normalized_reference_key,
        resolution_status: mention.resolution_status,
        relationship_hint: mention.relationship_hint,
        mentions: [mention],
        page_numbers: mention.page_number !== null ? new Set([mention.page_number]) : new Set(),
        candidate_label: candidateText,
        target_label: targetText,
      });
    }

    return Array.from(groups.values())
      .map((item) => ({ ...item, page_numbers: Array.from(item.page_numbers).sort((a, b) => a - b) }))
      .sort((a, b) => b.mentions.length - a.mentions.length);
  })();

  const handleClassifyDocument = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    setClassificationLoading(true);
    try {
      const response = await axios.post<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classify`);
      setClassificationResult(response.data);
      await loadDocumentIntelligenceAudit(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setClassificationResult(null);
      setError("No se pudo clasificar el documento.");
    } finally {
      setClassificationLoading(false);
    }
  };

  const handleConfirmClassification = async () => {
    if (!selectedTenderId || !selectedDocumentId || !classificationResult) {
      return;
    }

    try {
      const response = await axios.patch<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classification`, {
        action: "CONFIRM",
        human_type: classificationResult.effective_type,
        human_note: "Confirmado por usuario",
      });
      setClassificationResult(response.data);
      await loadDocumentIntelligenceAudit(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo confirmar la clasificación.");
    }
  };

  const handleReviewClassification = async () => {
    if (!selectedTenderId || !selectedDocumentId) {
      return;
    }

    try {
      const response = await axios.patch<ClassificationResult>(`${API_URL}/tenders/${selectedTenderId}/documents/${selectedDocumentId}/classification`, {
        action: "MARK_FOR_REVIEW",
        human_note: "Revisión humana requerida",
      });
      setClassificationResult(response.data);
      await loadDocumentIntelligenceAudit(selectedTenderId);
      await loadTenderStateSnapshot(selectedTenderId);
    } catch (err) {
      setError("No se pudo marcar la clasificación para revisión.");
    }
  };

  const isPdfDocument = (document: TenderDocument | null) => {
    if (!document) {
      return false;
    }
    const mimeType = document.mime_type?.toLowerCase() ?? "";
    const filename = document.original_filename.toLowerCase();
    return mimeType.includes("pdf") || filename.endsWith(".pdf");
  };

  return (
    <div style={{ maxWidth: 1200, margin: "40px auto", padding: "0 20px", fontFamily: "sans-serif" }}>
      <style>{`
        .pdf-viewer {
          width: 100%;
          min-height: 760px;
          border: 1px solid #d9e1ec;
          border-radius: 12px;
          background: #f8fafc;
        }
        .viewer-placeholder {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 240px;
          border: 1px dashed #d9e1ec;
          border-radius: 12px;
          background: #f8fafc;
          color: #52607a;
          padding: 20px;
          text-align: center;
        }
      `}</style>
      <h1>LicitIA — Tender Workspace</h1>

      <CompanyEvidenceLibrary apiUrl={API_URL} />

      <div style={{ display: "grid", gridTemplateColumns: "370px 1fr", gap: 24 }}>
        <section style={{ border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Create Tender</h2>
          <form onSubmit={handleSubmit}>
            <div style={{ display: "grid", gap: 12 }}>
              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Title</div>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>Institution / Profile</div>
                <input
                  value={institutionProfile}
                  onChange={(event) => setInstitutionProfile(event.target.value)}
                  placeholder="optional"
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              <label>
                <div style={{ marginBottom: 6, fontWeight: 600 }}>External Reference</div>
                <input
                  value={externalReference}
                  onChange={(event) => setExternalReference(event.target.value)}
                  placeholder="optional"
                  style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                />
              </label>

              {error && <div style={{ color: "crimson", fontSize: 14 }}>{error}</div>}

              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: "11px 16px",
                  borderRadius: 8,
                  border: "none",
                  background: "#1b5bd8",
                  color: "#fff",
                  fontWeight: 700,
                  cursor: loading ? "not-allowed" : "pointer",
                }}
              >
                {loading ? "Creating..." : "Create Tender"}
              </button>
            </div>
          </form>
        </section>

        <section style={{ border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Existing Tenders</h2>

          {tenders.length === 0 ? (
            <p>No tenders created yet.</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {tenders.map((tender) => {
                const active = tender.id === selectedTenderId;
                return (
                  <button
                    key={tender.id}
                    type="button"
                    onClick={() => handleSelectTender(tender.id)}
                    style={{
                      textAlign: "left",
                      border: active ? "2px solid #1b5bd8" : "1px solid #e8edf2",
                      borderRadius: 10,
                      padding: 14,
                      background: active ? "#edf4ff" : "#f8fafc",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{tender.title}</div>
                      {active && (
                        <span style={{ fontSize: 12, background: "#dfeeff", color: "#1b5bd8", borderRadius: 999, padding: "4px 8px", fontWeight: 700 }}>
                          Seleccionado
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 14, color: "#52607a", marginTop: 8 }}>
                      {tender.institution_profile || "No institution profile"} • {tender.external_reference || "No external reference"}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 8 }}>
                      Status: {tender.status} • ID: {tender.id}
                    </div>
                    <div style={{ fontSize: 12, color: "#5d6d88", marginTop: 4 }}>
                      Created: {new Date(tender.created_at).toLocaleString()}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 12, fontWeight: 700, color: active ? "#1b5bd8" : "#52607a" }}>
                      {active ? "Seleccionado" : "Abrir"}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Estado del expediente</h2>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" onClick={() => selectedTenderId && void loadTenderStateSnapshot(selectedTenderId)} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                {stateSnapshotLoading ? "Actualizando snapshot..." : "Actualizar snapshot"}
              </button>
              <button type="button" onClick={() => void handleRunDocumentIntelligenceAudit()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                {auditLoading ? "Auditando..." : "Auditar expediente"}
              </button>
            </div>
          </div>

          {stateSnapshotLoading && <div style={{ color: "#52607a", fontSize: 13, marginTop: 10 }}>Consolidando snapshot del expediente...</div>}
          {!stateSnapshotLoading && !stateSnapshot && <div style={{ color: "#52607a", fontSize: 13, marginTop: 10 }}>No se pudo cargar el snapshot del expediente.</div>}

          {stateSnapshot && (
            <>
              <div style={{ marginTop: 12, fontSize: 13, color: "#52607a" }}>
                Snapshot {stateSnapshot.snapshot_version} • Readiness: <strong>{readinessLabel(stateSnapshot.readiness.code)}</strong> ({stateSnapshot.readiness.code}) • {new Date(stateSnapshot.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>{stateSnapshot.readiness.reason}</div>

              <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Documentos</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.documents.current_documents} actuales / {stateSnapshot.summary.documents.total_documents} totales</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Pendientes proc.: {stateSnapshot.summary.documents.pending_processing}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Relaciones</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.relationships.relationship_edge_count} aristas</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Ambiguas {stateSnapshot.summary.relationships.ambiguous_reference_groups_count} • Sin resolver {stateSnapshot.summary.relationships.unresolved_reference_groups_count}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Eventos</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.timeline.total_events}</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Sugeridos {stateSnapshot.summary.timeline.suggested_events} • Confirmados {stateSnapshot.summary.timeline.confirmed_events}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Cambios</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.changes.total_changes}</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Sugeridos {stateSnapshot.summary.changes.suggested_changes} • Confirmados {stateSnapshot.summary.changes.confirmed_changes}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Estado efectivo</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.effective_state.total_scopes} ambitos</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Determinados {stateSnapshot.summary.effective_state.determined} • Orden por revisar {stateSnapshot.summary.effective_state.ambiguous_precedence}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Pendientes</div>
                  <div style={{ fontWeight: 700 }}>{stateSnapshot.summary.pending_actions.total}</div>
                  <div style={{ fontSize: 12, color: "#52607a" }}>B {stateSnapshot.summary.pending_actions.blocking} • W {stateSnapshot.summary.pending_actions.warning} • I {stateSnapshot.summary.pending_actions.info}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, border: "1px solid #e8edf2", borderRadius: 10, padding: 10, background: "#f8fafc" }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Pendientes principales</div>
                {stateSnapshot.top_pending_actions.length === 0 ? (
                  <div style={{ color: "#52607a", fontSize: 12 }}>Sin pendientes estructurales.</div>
                ) : (
                  <div style={{ display: "grid", gap: 6 }}>
                    {stateSnapshot.top_pending_actions.map((item) => (
                      <div key={`${item.category}-${item.related_entity_id ?? ""}-${item.document_id ?? ""}`} style={{ fontSize: 12 }}>
                        <strong>{pendingSeverityLabel(item.severity)}</strong> • {pendingCategoryLabel(item.category)} • {item.title}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Mapa documental consolidado</div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Origen</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Relación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Destino</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Soporte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stateSnapshot.relationships.document_map.slice(0, 20).map((entry) => (
                      <tr key={`${entry.source_document_id}-${entry.relationship_type}-${entry.target_document_id}`}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.source_filename ?? entry.source_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.relationship_type}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.target_filename ?? entry.target_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {entry.supporting_reference_count} refs • págs {entry.supporting_pages.length > 0 ? entry.supporting_pages.join(", ") : "-"} • origen {entry.resolution_origin}
                          {entry.supporting_change_ids.length > 0 && <div style={{ color: "#52607a" }}>Cambios: {entry.supporting_change_ids.join(", ")}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Matriz por documento vigente</div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Procesamiento</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Normalizado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Clasificación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Referencias</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Eventos/Cambios</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Findings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stateSnapshot.documents.matrix.map((row) => (
                      <tr key={row.document_id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.filename}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.processing_status}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.normalized ? "Sí" : "No"}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.classification_status}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.reference_analysis_status}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.event_count} / {row.change_count}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.findings_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <div style={{ marginTop: 16, border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>Modelo de evaluacion</h3>
              <button type="button" onClick={() => void handleAnalyzeEvaluation()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                {evaluationLoading ? "Analizando..." : "Analizar evaluacion"}
              </button>
            </div>

            {evaluationLoading && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Analizando modelo y criterios de evaluacion...</div>}
            {!evaluationLoading && !evaluation && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Sin analisis de evaluacion disponible.</div>}

            {evaluation && (
              <>
                <div style={{ marginTop: 8, fontSize: 13, color: "#334155" }}>
                  Metodo detectado: <strong>{evaluationMethodLabel(evaluation.model.effective_method)}</strong> ({evaluation.model.effective_method})
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                  Estado: <strong>{evaluationReviewLabel(evaluation.model.review_status)}</strong> • Motor: {evaluation.model.detector_version}
                </div>
                <div style={{ marginTop: 6, fontSize: 12, color: "#334155" }}>{evaluation.model.summary}</div>

                <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" onClick={() => void handleEvaluationModelDecision("CONFIRM")} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>
                    Confirmar
                  </button>
                  <button type="button" onClick={() => void handleEvaluationModelOverride()} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                    Modificar
                  </button>
                  <button type="button" onClick={() => void handleEvaluationModelDecision("REJECT")} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#b91c1c", color: "#fff", fontWeight: 700 }}>
                    Rechazar
                  </button>
                  <button type="button" onClick={() => void handleEvaluationModelDecision("RESET_TO_SUGGESTED")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                    Reset
                  </button>
                </div>

                <div style={{ marginTop: 10, fontSize: 12, color: "#52607a" }}>
                  Evidencia del modelo: {evaluation.model.evidence.length}
                </div>
                <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                  {evaluation.model.evidence.slice(0, 6).map((evidence) => (
                    <div key={evidence.id} style={{ fontSize: 12, color: "#334155" }}>
                      <strong>{evidence.evidence_role}</strong> • {evidence.source_filename ?? evidence.source_document_id} p{evidence.source_page ?? "-"} • {evidence.source_excerpt}
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: 12, fontSize: 13, color: "#334155" }}>
                  Criterios de evaluacion: <strong>{evaluation.criteria_summary.total}</strong> • Sugeridos {evaluation.criteria_summary.suggested} • Confirmados {evaluation.criteria_summary.confirmed} • Rechazados {evaluation.criteria_summary.rejected}
                </div>

                <div style={{ marginTop: 10, overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "#eef2f7" }}>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Tipo</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Categoria</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Criterio</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Peso/Umbral</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Excluyente</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Fuente</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Estado</th>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evaluation.criteria.map((criterion) => (
                        <tr key={criterion.id}>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{criterionTypeLabel(criterion.criterion_type)}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{criterion.category ?? "-"}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{criterion.criterion_text}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            {criterion.weight_value !== null ? `${criterion.weight_value} ${criterion.weight_unit ?? ""}` : "-"}
                            {criterion.threshold_value !== null && (
                              <div>{criterion.threshold_operator ?? ""} {criterion.threshold_value} {criterion.threshold_unit ?? ""}</div>
                            )}
                          </td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{criterion.is_exclusionary === null ? "-" : criterion.is_exclusionary ? "Si" : "No"}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            {criterion.source_filename ?? criterion.source_document_id} p{criterion.source_page ?? "-"}
                          </td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{evaluationReviewLabel(criterion.review_status)}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              <button type="button" onClick={() => void handleCriterionDecision(criterion.id, "CONFIRM")} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>Confirmar</button>
                              <button type="button" onClick={() => void handleCriterionOverride(criterion)} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>Modificar</button>
                              <button type="button" onClick={() => void handleCriterionDecision(criterion.id, "REJECT")} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#b91c1c", color: "#fff", fontWeight: 700 }}>Rechazar</button>
                              <button type="button" onClick={() => void handleCriterionDecision(criterion.id, "RESET_TO_SUGGESTED")} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>Reset</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          <div style={{ marginTop: 16, border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>Requisitos detectados</h3>
              <button type="button" onClick={() => void handleAnalyzeRequirements()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                {requirementCandidatesLoading ? "Analizando..." : "Extraer requisitos"}
              </button>
            </div>

            {requirementCandidatesLoading && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Extrayendo candidatos verificables desde contenido normalizado...</div>}
            {!requirementCandidatesLoading && !requirementCandidates && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Sin analisis de requisitos disponible.</div>}

            {requirementCandidates && (
              <>
                <div style={{ marginTop: 8, fontSize: 13, color: "#334155" }}>
                  Candidatos: <strong>{requirementCandidates.summary.total}</strong> • Documentos {requirementCandidates.summary.documents_with_candidates} • Páginas {requirementCandidates.summary.pages_with_candidates} • Actor explícito {requirementCandidates.summary.explicit_actor_count}
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                  Sugeridos {requirementCandidates.summary.suggested} • Confirmados {requirementCandidates.summary.confirmed} • Rechazados {requirementCandidates.summary.rejected} • Motor {requirementCandidates.requirements_version}
                </div>

                {Object.keys(requirementCandidates.summary.by_modality).length > 0 && (
                  <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                    Modalidades: {Object.entries(requirementCandidates.summary.by_modality)
                      .map(([modality, count]) => `${modality} (${count})`)
                      .join(" • ")}
                  </div>
                )}

                <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
                  {requirementCandidates.candidates.map((candidate) => (
                    <div key={candidate.id} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 10, background: "#fff" }}>
                      <div style={{ fontSize: 12, color: "#52607a" }}>
                        {candidate.source_filename ?? candidate.source_document_id} p{candidate.source_page ?? "-"} • {candidate.review_status} • {candidate.detection_origin}
                      </div>
                      <div style={{ marginTop: 6, fontSize: 14, color: "#0f172a" }}>{candidate.requirement_text}</div>
                      <div style={{ marginTop: 6, fontSize: 12, color: "#334155" }}>
                        Actor: <strong>{candidate.actor_text ?? "-"}</strong> • Modalidad: <strong>{candidate.modality_text ?? "-"}</strong>
                      </div>
                      <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>
                        Evidencia: {candidate.evidence.length}
                      </div>
                      <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                        {candidate.evidence.slice(0, 3).map((evidence) => (
                          <div key={evidence.id} style={{ fontSize: 12, color: "#334155" }}>
                            {evidence.source_filename ?? evidence.source_document_id} p{evidence.source_page ?? "-"} • {evidence.source_excerpt}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div style={{ marginTop: 16, border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>Requisitos normalizados</h3>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" onClick={() => void handleNormalizeRequirements()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                  {requirementsLoading ? "Normalizando..." : "Normalizar requisitos"}
                </button>
                <button type="button" onClick={() => void handleAnalyzeRequirementSemantics()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                  {requirementSemanticsLoading ? "Interpretando..." : "Interpretar aplicabilidad y evidencia"}
                </button>
                <button type="button" onClick={() => void handleAnalyzeRequirementVersions()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                  {requirementEffectiveStateLoading ? "Versionando..." : "Analizar vigencia por cambios"}
                </button>
              </div>
            </div>

            {requirementsLoading && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Consolidando ocurrencias detectadas en requisitos canónicos...</div>}
            {!requirementsLoading && !requirements && <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>Sin normalización de requisitos disponible.</div>}

            {requirements && (
              <>
                <div style={{ marginTop: 8, fontSize: 13, color: "#334155" }}>
                  Requisitos detectados: <strong>{requirements.summary.candidate_count}</strong> • Requisitos normalizados: <strong>{requirements.summary.requirement_count}</strong> • Merges {requirements.summary.merged_requirement_count}
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                  NORMALIZED {requirements.summary.normalized_count} • REVIEW_REQUIRED {requirements.summary.review_required_count} • Fuentes únicas {requirements.summary.single_source_requirement_count} • Motor {requirements.normalizer_version}
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>{requirements.scope_note}</div>
                {requirementSemantics && (
                  <>
                    <div style={{ marginTop: 6, fontSize: 12, color: "#52607a" }}>{requirementSemantics.scope_note}</div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                      Aplicabilidad: MANDATORY {requirementSemantics.summary.mandatory_count} • CONDITIONAL {requirementSemantics.summary.conditional_count} • UNKNOWN {requirementSemantics.summary.unknown_applicability_count}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                      Interpretación: DETERMINED {requirementSemantics.summary.determined_count} • REVIEW_REQUIRED {requirementSemantics.summary.review_required_count}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                      Evidencia: EXPLICIT_ARTIFACT {requirementSemantics.summary.explicit_artifact_count} • DIRECT_VERIFICATION {requirementSemantics.summary.direct_verification_count} • UNSPECIFIED {requirementSemantics.summary.unspecified_evidence_count} • REVIEW_REQUIRED {requirementSemantics.summary.evidence_review_required_count}
                    </div>
                  </>
                )}

                {requirementEffectiveState && (
                  <>
                    <div style={{ marginTop: 6, fontSize: 12, color: "#52607a" }}>{requirementEffectiveState.scope_note}</div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                      Vigencia: EFFECTIVE {requirementEffectiveState.summary.effective_count} • SUPERSEDED {requirementEffectiveState.summary.superseded_count} • AMBIGUOUS {requirementEffectiveState.summary.ambiguous_count} • UNRESOLVED {requirementEffectiveState.summary.unresolved_count}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                      Enlaces de versión: {requirementEffectiveState.summary.version_link_count} • Motor {requirementEffectiveState.analyzer_version}
                    </div>
                  </>
                )}

                {Object.keys(requirements.summary.category_counts).length > 0 && (
                  <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                    Categorías: {Object.entries(requirements.summary.category_counts)
                      .map(([category, count]) => `${category} (${count})`)
                      .join(" • ")}
                  </div>
                )}

                <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
                  {requirements.requirements.map((requirement) => {
                    const semantics = requirementSemantics?.requirements.find((item) => item.requirement_id === requirement.id) ?? null;
                    const requirementEffective = requirementEffectiveState?.requirements.find((item) => item.requirement_id === requirement.id) ?? null;
                    return (
                    <details key={requirement.id} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 10, background: "#fff" }}>
                      <summary style={{ cursor: "pointer" }}>
                        <strong>{requirement.canonical_text}</strong>
                        <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                          {requirement.category} • Fuentes {requirement.source_occurrence_count} • {requirement.normalization_status}
                        </div>
                        {semantics && (
                          <div style={{ fontSize: 12, color: "#334155", marginTop: 4 }}>
                            {applicabilityLabel(semantics.applicability)} • {evidenceModeLabel(semantics.evidence_mode)} • {interpretationStatusLabel(semantics.interpretation_status)}
                          </div>
                        )}
                        {requirementEffective && (
                          <div style={{ fontSize: 12, color: "#334155", marginTop: 4 }}>
                            {requirementEffectiveStatusLabel(requirementEffective.effective_status)} • Fuente vigente {requirementEffective.effective_source_filename ?? requirementEffective.effective_source_document_id ?? "-"}
                          </div>
                        )}
                      </summary>

                      <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                        Confianza: {requirement.normalization_confidence ?? "-"} • Razón: {requirement.normalization_reason ?? "-"}
                      </div>

                      {semantics && (
                        <>
                          <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                            Aplicabilidad: <strong>{applicabilityLabel(semantics.applicability)}</strong>
                            {semantics.condition_text && <span> • Condición: {semantics.condition_text}</span>}
                          </div>
                          <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                            Evidencia esperada: <strong>{evidenceModeLabel(semantics.evidence_mode)}</strong> • Estado: <strong>{interpretationStatusLabel(semantics.interpretation_status)}</strong>
                          </div>
                          {semantics.interpretation_reason && (
                            <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                              Razón de interpretación: {semantics.interpretation_reason}
                            </div>
                          )}

                          {semantics.evidence_mode === "DIRECT_VERIFICATION" && (
                            <div style={{ marginTop: 6, fontSize: 12, color: "#334155" }}>
                              Se verifica directamente en la propuesta.
                            </div>
                          )}
                          {semantics.evidence_mode === "UNSPECIFIED" && (
                            <div style={{ marginTop: 6, fontSize: 12, color: "#334155" }}>
                              La fuente establece el requisito pero no especifica cómo acreditarlo.
                            </div>
                          )}
                          {semantics.evidence_mode === "REVIEW_REQUIRED" && (
                            <div style={{ marginTop: 6, fontSize: 12, color: "#334155" }}>
                              Revisar fuente.
                            </div>
                          )}

                          {semantics.expected_evidence.length > 0 && (
                            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                              {semantics.expected_evidence.map((item) => (
                                <div key={item.id} style={{ fontSize: 12, color: "#334155", borderTop: "1px solid #f1f5f9", paddingTop: 6 }}>
                                  <div>
                                    <strong>{item.evidence_type}</strong> • {item.evidence_description}
                                  </div>
                                  <div style={{ color: "#52607a", marginTop: 3 }}>
                                    {item.source_filename ?? item.source_document_id} p{item.source_page ?? "-"}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}

                      {requirementEffective && (
                        <>
                          <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                            Vigencia: <strong>{requirementEffectiveStatusLabel(requirementEffective.effective_status)}</strong>
                          </div>
                          <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                            Fuente vigente: <strong>{requirementEffective.effective_source_filename ?? requirementEffective.effective_source_document_id ?? "-"}</strong>
                          </div>
                          {requirementEffective.evidence_reasons.length > 0 && (
                            <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                              Base: {requirementEffective.evidence_reasons.join(" • ")}
                            </div>
                          )}
                        </>
                      )}

                      {requirement.primary_source && (
                        <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                          Fuente primaria: {requirement.primary_source.source_filename ?? requirement.primary_source.source_document_id} p{requirement.primary_source.source_page ?? "-"}
                        </div>
                      )}

                      <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                        {requirement.candidates.map((candidate) => (
                          <div key={candidate.candidate_id} style={{ fontSize: 12, color: "#334155", borderTop: "1px solid #f1f5f9", paddingTop: 6 }}>
                            <div>
                              {candidate.source_filename ?? candidate.source_document_id} p{candidate.source_page ?? "-"} • {candidate.is_primary_source ? "PRIMARY" : "SECONDARY"}
                            </div>
                            <div style={{ marginTop: 3 }}>{candidate.requirement_text}</div>
                            <div style={{ marginTop: 3, color: "#52607a" }}>
                              Actor {candidate.actor_text ?? "-"} • Modalidad {candidate.modality_text ?? "-"}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                    );
                  })}
                </div>

                {requirementEffectiveState && requirementEffectiveState.version_links.length > 0 && (
                  <div style={{ marginTop: 12, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
                    <div style={{ fontSize: 12, color: "#334155", fontWeight: 700 }}>Enlaces de versión trazables</div>
                    <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
                      {requirementEffectiveState.version_links.slice(0, 20).map((link) => (
                        <div key={link.id} style={{ fontSize: 12, color: "#334155", border: "1px solid #e2e8f0", borderRadius: 8, padding: 8, background: "#fff" }}>
                          <div>
                            <strong>{link.link_kind}</strong> • cambio {link.change_id}
                          </div>
                          <div style={{ marginTop: 3 }}>
                            Antes: {link.predecessor_canonical_text ?? "-"}
                          </div>
                          <div style={{ marginTop: 3 }}>
                            Después: {link.successor_canonical_text ?? "-"}
                          </div>
                          <div style={{ marginTop: 3, color: "#52607a" }}>
                            Base {link.matching_basis} • Localizador {link.target_locator_text ?? "-"}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 14, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>Matriz de requisitos</div>
                    <button
                      type="button"
                      onClick={() => selectedTenderId && void loadTenderRequirementMatrix(selectedTenderId)}
                      style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}
                    >
                      {requirementMatrixLoading ? "Actualizando..." : "Actualizar matriz"}
                    </button>
                  </div>

                  {requirementMatrixLoading && <div style={{ marginTop: 6, fontSize: 12, color: "#52607a" }}>Consolidando revisión humana de requisitos...</div>}
                  {!requirementMatrixLoading && !requirementMatrix && <div style={{ marginTop: 6, fontSize: 12, color: "#52607a" }}>Sin matriz de requisitos disponible.</div>}

                  {requirementMatrix && (
                    <>
                      <div style={{ marginTop: 6, fontSize: 12, color: "#52607a" }}>{requirementMatrix.scope_note}</div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                        Total {requirementMatrix.summary.total_requirements} • Efectivos {requirementMatrix.summary.effective_requirements} • Pendientes {requirementMatrix.summary.pending_review_count} • Validados {requirementMatrix.summary.approved_count} • Revisar {requirementMatrix.summary.needs_review_count} • Descartados {requirementMatrix.summary.rejected_count}
                      </div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                        Revisión vigente {requirementMatrix.summary.current_review_count} • Desactualizada {requirementMatrix.summary.stale_review_count} • Sin revisión {requirementMatrix.summary.not_reviewed_count}
                      </div>

                      <div style={{ marginTop: 8, overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                          <thead>
                            <tr style={{ background: "#eef2f7" }}>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Requisito</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Representación automática</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Revisión humana</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Acciones</th>
                            </tr>
                          </thead>
                          <tbody>
                            {requirementMatrix.requirements.map((item) => (
                              <tr key={item.requirement_id}>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  <div style={{ fontWeight: 700 }}>{item.canonical_text}</div>
                                  <div style={{ marginTop: 3, color: "#52607a" }}>{item.category} • Fuentes {item.source_occurrence_count} • {requirementEffectiveStatusLabel(item.effective_status)}</div>
                                  {item.primary_source && (
                                    <div style={{ marginTop: 3, color: "#52607a" }}>
                                      Fuente {item.primary_source.source_filename ?? item.primary_source.source_document_id} p{item.primary_source.source_page ?? "-"}
                                    </div>
                                  )}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  <div>{applicabilityLabel(item.applicability)} • {evidenceModeLabel(item.evidence_mode)} • {interpretationStatusLabel(item.interpretation_status)}</div>
                                  {item.effective_source_filename && (
                                    <div style={{ marginTop: 3, color: "#52607a" }}>Fuente vigente: {item.effective_source_filename}</div>
                                  )}
                                  {item.system_warnings.length > 0 && (
                                    <div style={{ marginTop: 3, color: "#7a4b00" }}>Advertencias: {item.system_warnings.join(" • ")}</div>
                                  )}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  <div><strong>{requirementReviewStatusLabel(item.review_status)}</strong></div>
                                  <div style={{ marginTop: 3, color: "#52607a" }}>Estado revisión: {requirementReviewFreshnessLabel(item.review_freshness)}</div>
                                  {item.review_note && <div style={{ marginTop: 3, color: "#52607a" }}>{item.review_note}</div>}
                                  {item.reviewed_at && <div style={{ marginTop: 3, color: "#52607a" }}>Revisado: {new Date(item.reviewed_at).toLocaleString()}</div>}
                                </td>
                                <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                    <button type="button" onClick={() => void handleRequirementReviewAction(item, "APPROVE")} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>
                                      Validar
                                    </button>
                                    <button type="button" onClick={() => void handleRequirementReviewAction(item, "MARK_NEEDS_REVIEW")} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                                      Revisar
                                    </button>
                                    <button type="button" onClick={() => void handleRequirementReviewAction(item, "REJECT")} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#b91c1c", color: "#fff", fontWeight: 700 }}>
                                      Descartar como requisito
                                    </button>
                                    <button type="button" onClick={() => void handleRequirementReviewAction(item, "RESET")} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                      Restablecer pendiente
                                    </button>
                                    <button type="button" onClick={() => void openRequirementSource(item.primary_source)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                      Ver fuente
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>

                <div style={{ marginTop: 14, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>Evidencia candidata por requisito</div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                        LicitIA propone evidencias que podrían ser relevantes para cada requisito. Una asociación confirmada indica que la evidencia es pertinente para evaluar el requisito; no significa que el requisito esté cumplido.
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <select
                        value={selectedMatchCompanyId}
                        onChange={(event) => setSelectedMatchCompanyId(event.target.value)}
                        style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cfd8e3", minWidth: 220 }}
                      >
                        <option value="">Selecciona una empresa</option>
                        {companies.map((company) => (
                          <option key={company.id} value={company.id}>
                            {company.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void loadCompanies()}
                        style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}
                      >
                        Actualizar empresas
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleAnalyzeRequirementEvidenceMatches()}
                        disabled={!selectedMatchCompanyId || requirementEvidenceMatchesLoading}
                        style={{ padding: "8px 10px", borderRadius: 8, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700, opacity: !selectedMatchCompanyId || requirementEvidenceMatchesLoading ? 0.6 : 1 }}
                      >
                        {requirementEvidenceMatchesLoading ? "Buscando..." : "Buscar evidencias candidatas"}
                      </button>
                    </div>
                  </div>

                  {selectedMatchCompanyId && (
                    <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                      <div style={{ fontSize: 12, color: "#334155" }}>
                        Evidencias disponibles de la empresa: {companyEvidenceOptionsLoading ? "cargando..." : companyEvidenceOptions.length}
                      </div>
                      {!companyEvidenceOptionsLoading && companyEvidenceOptions.length > 0 && (
                        <div style={{ display: "grid", gap: 6, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
                          {companyEvidenceOptions.slice(0, 8).map((evidence) => (
                            <div key={evidence.id} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 8, background: "#fff", fontSize: 12 }}>
                              <div style={{ fontWeight: 700 }}>{evidence.evidence_type} • {evidence.id.slice(0, 8)}</div>
                              <div style={{ marginTop: 3, color: "#52607a" }}>{evidence.source_document.original_filename}</div>
                              <div style={{ marginTop: 3, color: "#334155" }}>{evidence.canonical_statement}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {selectedMatchCompanyId && !requirementEvidenceMatchesLoading && !requirementEvidenceMatches && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>
                      Ejecuta el análisis para cargar asociaciones requisito ↔ evidencia para la empresa seleccionada.
                    </div>
                  )}

                  {requirementEvidenceMatches && (
                    <>
                      <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>{requirementEvidenceMatches.scope_note}</div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                        Requisitos evaluados {requirementEvidenceMatches.summary.requirements_evaluated} • Con evidencia candidata {requirementEvidenceMatches.summary.requirements_with_candidate_evidence} • Asociaciones {requirementEvidenceMatches.summary.candidate_associations}
                      </div>
                      <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                        Fuertes {requirementEvidenceMatches.summary.strong_candidates} • Posibles {requirementEvidenceMatches.summary.possible_candidates} • Revisión requerida {requirementEvidenceMatches.summary.review_required_candidates} • Confirmadas por humano {requirementEvidenceMatches.summary.human_confirmed_associations}
                      </div>

                      <div style={{ marginTop: 8, overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                          <thead>
                            <tr style={{ background: "#eef2f7" }}>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Requisito</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Aplicabilidad</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Evidencia candidata</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Fuerza</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Revisión</th>
                              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Acciones</th>
                            </tr>
                          </thead>
                          <tbody>
                            {requirementEvidenceMatches.requirements.flatMap((item) => {
                              const renderRows = item.matches.length > 0 ? item.matches : [null];
                              return renderRows.map((match, index) => (
                                <tr key={match ? match.id : `${item.requirement_id}-empty`}>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    <div style={{ fontWeight: 700 }}>{item.canonical_text}</div>
                                    <div style={{ marginTop: 3, color: "#52607a" }}>{item.category} • {item.evidence_mode} • Estado {item.effective_status}</div>
                                    {item.condition_text && <div style={{ marginTop: 3, color: "#7a4b00" }}>Condición: {item.condition_text}</div>}
                                    {item.matching_warnings.length > 0 && <div style={{ marginTop: 3, color: "#7a4b00" }}>Advertencias: {item.matching_warnings.join(" • ")}</div>}
                                    {item.primary_source && <div style={{ marginTop: 3, color: "#52607a" }}>Fuente {item.primary_source.source_filename ?? item.primary_source.source_document_id} p{item.primary_source.source_page ?? "-"}</div>}
                                  </td>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    <div>{applicabilityLabel(item.applicability)}</div>
                                    <div style={{ marginTop: 3, color: "#52607a" }}>{interpretationStatusLabel(item.interpretation_status)}</div>
                                    <div style={{ marginTop: 3, color: "#52607a" }}>Revisión requisito: {requirementReviewStatusLabel(item.requirement_review_status)}</div>
                                  </td>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    {match ? (
                                      <>
                                        <div style={{ fontWeight: 700 }}>{match.company_evidence.evidence_type} • {match.company_evidence.id.slice(0, 8)}</div>
                                        <div style={{ marginTop: 3, color: "#334155" }}>{match.company_evidence.canonical_statement}</div>
                                        <div style={{ marginTop: 3, color: "#52607a" }}>{match.company_evidence.source_document.original_filename}</div>
                                        {match.system_warnings.length > 0 && <div style={{ marginTop: 3, color: "#7a4b00" }}>Advertencias: {match.system_warnings.join(" • ")}</div>}
                                      </>
                                    ) : (
                                      <div style={{ color: "#52607a" }}>Sin evidencia candidata activa.</div>
                                    )}
                                  </td>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    {match ? (
                                      <>
                                        <div><strong>{matchStrengthLabel(match.match_strength)}</strong></div>
                                        <div style={{ marginTop: 3, color: "#52607a" }}>{match.match_basis.join(" • ")}</div>
                                        <div style={{ marginTop: 3, color: "#52607a" }}>{match.match_rationale}</div>
                                      </>
                                    ) : (
                                      <div style={{ color: "#52607a" }}>Sin asociación.</div>
                                    )}
                                  </td>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    {match ? (
                                      <>
                                        <div><strong>{matchReviewStatusLabel(match.review?.review_status ?? null)}</strong></div>
                                        <div style={{ marginTop: 3, color: "#52607a" }}>Vigencia: {matchReviewFreshnessLabel(match.review_freshness)}</div>
                                        {match.review?.review_note && <div style={{ marginTop: 3, color: "#52607a" }}>{match.review.review_note}</div>}
                                      </>
                                    ) : (
                                      <div style={{ color: "#52607a" }}>Sin revisión.</div>
                                    )}
                                  </td>
                                  <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9", verticalAlign: "top" }}>
                                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                      {match && (
                                        <>
                                          <button type="button" onClick={() => void handleRequirementEvidenceMatchReviewAction(match.id, "CONFIRMED", match.review?.review_note ?? null)} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>
                                            Confirmar asociación
                                          </button>
                                          <button type="button" onClick={() => void handleRequirementEvidenceMatchReviewAction(match.id, "NEEDS_REVIEW", match.review?.review_note ?? null)} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                                            Marcar revisión
                                          </button>
                                          <button type="button" onClick={() => void handleRequirementEvidenceMatchReviewAction(match.id, "REJECTED", match.review?.review_note ?? null)} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#b91c1c", color: "#fff", fontWeight: 700 }}>
                                            Descartar asociación
                                          </button>
                                          <button type="button" onClick={() => openRequirementEvidenceSource(match)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                            Ver evidencia / fuente
                                          </button>
                                        </>
                                      )}
                                      {index === 0 && (
                                        <>
                                          <button type="button" onClick={() => void handleCreateManualRequirementEvidenceMatch(item.requirement_id)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                            Asociar evidencia manualmente
                                          </button>
                                          <button type="button" onClick={() => void openRequirementSource(item.primary_source)} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                            Ver requisito / fuente
                                          </button>
                                        </>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              ));
                            })}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}

                  <div style={{ marginTop: 14, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <div>
                        <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>Evaluación automática de soporte documental</div>
                        <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                          La evaluación automática indica qué tan bien la evidencia disponible soporta cada requisito según reglas determinísticas de LicitIA. No constituye la decisión final de cumplimiento. La decisión final corresponde al operador.
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleAnalyzeCompliance()}
                        disabled={!selectedMatchCompanyId || complianceAssessmentsLoading}
                        style={{ padding: "8px 10px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700, opacity: !selectedMatchCompanyId || complianceAssessmentsLoading ? 0.6 : 1 }}
                      >
                        {complianceAssessmentsLoading ? "Evaluando..." : "Evaluar soporte documental"}
                      </button>
                    </div>

                    {selectedMatchCompanyId && !complianceAssessmentsLoading && !complianceAssessments && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>
                        Ejecuta la evaluación para obtener el estado de soporte documental por requisito.
                      </div>
                    )}

                    {complianceAssessments && (
                      <>
                        <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>{complianceAssessments.scope_note}</div>
                        <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                          Requisitos {complianceAssessments.summary.requirements_considered} • Evidencia suficiente {complianceAssessments.summary.supported_count} • Evidencia parcial {complianceAssessments.summary.partially_supported_count}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                          Evidencia insuficiente {complianceAssessments.summary.not_supported_count} • Requiere revisión {complianceAssessments.summary.review_required_count} • No evaluado {complianceAssessments.summary.not_evaluated_count} • Condición no resuelta {complianceAssessments.summary.condition_unresolved_count}
                        </div>

                        <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                          {complianceAssessments.assessments.map((assessment) => (
                            <details key={assessment.id} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 10, background: "#fff" }}>
                              <summary style={{ cursor: "pointer" }}>
                                <div style={{ fontWeight: 700 }}>{assessment.requirement.canonical_text}</div>
                                <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                                  Estado: <strong>{complianceStatusLabel(assessment.system_status)}</strong> ({assessment.system_status})
                                </div>
                                <div style={{ marginTop: 3, fontSize: 12, color: "#52607a" }}>
                                  Aplicabilidad: {applicabilityLabel(assessment.requirement.applicability)} • Contexto: {complianceApplicabilityContextLabel(assessment.applicability_context)}
                                </div>
                                {assessment.requirement.condition_text && (
                                  <div style={{ marginTop: 3, fontSize: 12, color: "#7a4b00" }}>
                                    Condición: {assessment.requirement.condition_text}
                                  </div>
                                )}
                              </summary>

                              <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>{assessment.assessment_summary}</div>
                              {assessment.warning_codes.length > 0 && (
                                <div style={{ marginTop: 6, fontSize: 12, color: "#7a4b00" }}>
                                  Advertencias: {assessment.warning_codes.join(" • ")}
                                </div>
                              )}

                              <div style={{ marginTop: 8, overflowX: "auto" }}>
                                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                                  <thead>
                                    <tr style={{ background: "#eef2f7" }}>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Qué se verificó</th>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Esperado</th>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Observado</th>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Resultado</th>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Motivo</th>
                                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #d9e1ec" }}>Evidencia / fuente</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {assessment.checks.map((check) => (
                                      <tr key={check.id}>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{check.check_type}</td>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{check.expected_value ?? "-"}</td>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{check.observed_value ?? "-"}</td>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}><strong>{complianceCheckStatusLabel(check.check_status)}</strong></td>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{check.rationale}</td>
                                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                                          {check.company_evidence ? (
                                            <>
                                              <div style={{ fontWeight: 700 }}>{check.company_evidence.evidence_type} • {check.company_evidence.id.slice(0, 8)}</div>
                                              <div style={{ color: "#52607a", marginTop: 3 }}>{check.company_evidence.source_document.original_filename}</div>
                                              <div style={{ color: "#334155", marginTop: 3 }}>{check.company_evidence.canonical_statement}</div>
                                            </>
                                          ) : (
                                            <span style={{ color: "#52607a" }}>Sin evidencia vinculada</span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </details>
                          ))}
                        </div>
                      </>
                    )}

                    <div style={{ marginTop: 14, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <div>
                          <div style={{ fontSize: 14, color: "#0f172a", fontWeight: 700 }}>Decisión humana de cumplimiento</div>
                          <div style={{ marginTop: 4, fontSize: 12, color: "#52607a" }}>
                            La IA propone; el usuario decide.
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => selectedTenderId && selectedMatchCompanyId && void loadComplianceReview(selectedTenderId, selectedMatchCompanyId)}
                          disabled={!selectedMatchCompanyId || complianceReviewLoading}
                          style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700, opacity: !selectedMatchCompanyId || complianceReviewLoading ? 0.6 : 1 }}
                        >
                          {complianceReviewLoading ? "Cargando..." : "Actualizar revisión humana"}
                        </button>
                      </div>

                      {selectedMatchCompanyId && !complianceReviewLoading && !complianceReview && (
                        <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>
                          Ejecuta primero la evaluación automática para habilitar la revisión humana por requisito.
                        </div>
                      )}

                      {complianceReview && (
                        <>
                          <div style={{ marginTop: 8, fontSize: 12, color: "#52607a" }}>{complianceReview.scope_note}</div>
                          <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                            Requisitos {complianceReview.summary.requirements_reviewable} • Pendientes {complianceReview.summary.pending_count} • Cumple {complianceReview.summary.complies_count} • No cumple {complianceReview.summary.does_not_comply_count}
                          </div>
                          <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                            Revisar {complianceReview.summary.needs_review_count} • No aplica {complianceReview.summary.not_applicable_count} • Override humano {complianceReview.summary.human_override_count} • Decisiones desactualizadas {complianceReview.summary.stale_count}
                          </div>

                          <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                            {complianceReview.rows.map((row) => {
                              const noteRequired = isDecisionNoteRequired(row, row.human_decision.decision_status);
                              return (
                                <details key={`review-${row.requirement_id}`} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 10, background: "#fff" }}>
                                  <summary style={{ cursor: "pointer" }}>
                                    <div style={{ fontWeight: 700 }}>{row.requirement.canonical_text}</div>
                                    <div style={{ marginTop: 4, fontSize: 12, color: "#334155" }}>
                                      Sistema: <strong>{complianceStatusLabel(row.system_assessment.system_status)}</strong> • Humano: <strong>{complianceDecisionStatusLabel(row.human_decision.decision_status)}</strong>
                                    </div>
                                    <div style={{ marginTop: 3, fontSize: 12, color: "#52607a" }}>
                                      Relación: {complianceDecisionRelationLabel(row.decision_relation)} • Vigencia: {complianceDecisionFreshnessLabel(row.human_decision.freshness)}
                                    </div>
                                    {row.human_decision.freshness === "STALE" && (
                                      <div style={{ marginTop: 3, fontSize: 12, color: "#7a4b00" }}>
                                        La decisión humana quedó desactualizada tras cambios en la evaluación automática. Requiere confirmación del operador.
                                      </div>
                                    )}
                                  </summary>

                                  <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>
                                    Estado automático: {row.system_assessment.system_status} • Contexto: {row.system_assessment.applicability_context} • Requisito: {row.requirement.effective_status}
                                  </div>

                                  <div style={{ marginTop: 8 }}>
                                    <label style={{ fontSize: 12, color: "#52607a", fontWeight: 700 }} htmlFor={`decision-note-${row.requirement_id}`}>
                                      Justificación de decisión humana {noteRequired ? "(obligatoria en el estado actual)" : "(opcional)"}
                                    </label>
                                    <textarea
                                      id={`decision-note-${row.requirement_id}`}
                                      value={decisionNotesByRequirement[row.requirement_id] ?? row.human_decision.decision_note ?? ""}
                                      onChange={(event) =>
                                        setDecisionNotesByRequirement((current) => ({
                                          ...current,
                                          [row.requirement_id]: event.target.value,
                                        }))
                                      }
                                      rows={3}
                                      style={{ width: "100%", marginTop: 6, borderRadius: 8, border: "1px solid #cfd8e3", padding: 8, fontSize: 12 }}
                                      placeholder="Documenta la razón de la decisión humana cuando aplique"
                                    />
                                  </div>

                                  <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                                    <button type="button" onClick={() => void handleComplianceDecisionAction(row, "COMPLIES")} disabled={decisionSavingRequirementId === row.requirement_id} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700 }}>
                                      Marcar Cumple
                                    </button>
                                    <button type="button" onClick={() => void handleComplianceDecisionAction(row, "DOES_NOT_COMPLY")} disabled={decisionSavingRequirementId === row.requirement_id} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#b91c1c", color: "#fff", fontWeight: 700 }}>
                                      Marcar No cumple
                                    </button>
                                    <button type="button" onClick={() => void handleComplianceDecisionAction(row, "NEEDS_REVIEW")} disabled={decisionSavingRequirementId === row.requirement_id} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                                      Revisar
                                    </button>
                                    <button type="button" onClick={() => void handleComplianceDecisionAction(row, "NOT_APPLICABLE")} disabled={decisionSavingRequirementId === row.requirement_id} style={{ padding: "4px 8px", borderRadius: 6, border: "none", background: "#92400e", color: "#fff", fontWeight: 700 }}>
                                      Marcar No aplica
                                    </button>
                                    <button type="button" onClick={() => void handleComplianceDecisionAction(row, "PENDING")} disabled={decisionSavingRequirementId === row.requirement_id} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                      Volver a Pendiente
                                    </button>
                                  </div>
                                </details>
                              );
                            })}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          {!audit && <p style={{ color: "#52607a" }}>Sin auditoría cargada para esta licitación.</p>}

          {audit && (
            <>
              <div style={{ marginTop: 12, fontSize: 13, color: "#52607a" }}>
                Estado general: <strong>{audit.overall_readiness}</strong> • Versión auditoría: {audit.audit_version} • Actualizado: {new Date(audit.generated_at).toLocaleString()}
              </div>

              <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Documentos</div>
                  <div style={{ fontWeight: 700 }}>{audit.summary.documents.current_documents} actuales / {audit.summary.documents.total_documents} totales</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Clasificación</div>
                  <div style={{ fontWeight: 700 }}>{audit.summary.classification.classified_documents} clasificados / {audit.summary.classification.unclassified_documents} pendientes</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencias</div>
                  <div style={{ fontWeight: 700 }}>
                    Auto {audit.summary.references.status_counts.AUTO_RESOLVED} • Usuario {audit.summary.references.status_counts.HUMAN_RESOLVED} • Ambiguas {audit.summary.references.status_counts.AMBIGUOUS}
                  </div>
                  <div style={{ fontWeight: 700 }}>
                    Sin resolver {audit.summary.references.status_counts.UNRESOLVED} • Ignoradas {audit.summary.references.status_counts.IGNORED}
                  </div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Hallazgos</div>
                  <div style={{ fontWeight: 700 }}>{audit.findings.length} hallazgos</div>
                </div>
              </div>

              {audit.findings.length > 0 && (
                <div style={{ marginTop: 12, border: "1px solid #e8edf2", borderRadius: 10, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontWeight: 700, marginBottom: 8 }}>Hallazgos de integridad</div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {audit.findings.slice(0, 10).map((finding, index) => (
                      <div key={`${finding.code}-${index}`} style={{ fontSize: 12 }}>
                        <strong>{finding.severity}</strong> • {finding.code} • {finding.message}
                        {finding.document_filename ? ` (${finding.document_filename})` : ""}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Texto</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Normalizado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Clasificación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Referencias</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.document_rows.map((row) => (
                      <tr key={row.document_id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ fontWeight: 700 }}>{row.filename}</div>
                          <div style={{ color: "#52607a" }}>{row.document_short_id} • {row.processing_status}</div>
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.text_acquisition_state}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.normalized ? `Sí (${row.normalized_source_count})` : "No"}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {row.classification_type} • {row.classification_status}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {row.reference_analysis_status} • A:{row.auto_resolved_reference_count} H:{row.human_resolved_reference_count} Am:{row.ambiguous_reference_count} U:{row.unresolved_reference_count}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{row.integrity_findings.join(", ") || "OK"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Aclaraciones y modificaciones</h2>
            <button type="button" onClick={() => void handleAnalyzeChanges()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
              {changesLoading ? "Analizando..." : "Analizar cambios"}
            </button>
          </div>

          {changesLoading && <div style={{ color: "#52607a", fontSize: 13 }}>Cargando cambios detectados...</div>}
          {!changesLoading && !changes && <div style={{ color: "#52607a", fontSize: 13 }}>Sin análisis de aclaraciones/modificaciones todavía.</div>}

          {changes && (
            <>
              <div style={{ marginTop: 10, fontSize: 13, color: "#52607a" }}>
                Versión {changes.changes_version} • Actualizado: {new Date(changes.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Total cambios</div>
                  <div style={{ fontWeight: 700 }}>{changes.counts.total_changes}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Sugeridos / Confirmados</div>
                  <div style={{ fontWeight: 700 }}>{changes.counts.suggested_changes} / {changes.counts.confirmed_changes}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Rechazados</div>
                  <div style={{ fontWeight: 700 }}>{changes.counts.rejected_changes}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Duplicados semánticos</div>
                  <div style={{ fontWeight: 700 }}>{changes.counts.duplicate_semantic_count}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Tipo</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Cambio detectado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Origen</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento afectado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Ubicación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changes.changes.map((changeItem) => (
                      <tr key={changeItem.id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ fontWeight: 700 }}>{changeItem.human_change_type ?? changeItem.change_type}</div>
                          {hasChangeHumanOverride(changeItem) && <div style={{ color: "#0f766e" }}>Modificado por usuario</div>}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div>{changeItem.source_excerpt}</div>
                          <div style={{ color: "#52607a" }}>Antes: {changeItem.human_before_text ?? changeItem.before_text ?? "-"}</div>
                          <div style={{ color: "#52607a" }}>Después: {changeItem.human_after_text ?? changeItem.after_text ?? "-"}</div>
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {changeItem.source_filename ?? changeItem.source_document_id}
                          <div style={{ color: "#52607a" }}>Pág. {changeItem.source_page ?? "-"}</div>
                          {changeItem.source_event_date && <div style={{ color: "#52607a" }}>Evento: {changeItem.source_event_date}</div>}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {(changeItem.human_target_document_id ? documents.find((item) => item.id === changeItem.human_target_document_id)?.original_filename : null) ?? changeItem.target_filename ?? changeItem.target_reference_key ?? "Sin resolver"}
                          {changeItem.target_candidate_documents.length > 1 && (
                            <div style={{ color: "#52607a" }}>Ambigua: {changeItem.target_candidate_documents.map((item) => item.original_filename).join(" | ")}</div>
                          )}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {changeItem.human_target_locator_text ?? changeItem.target_locator_text ?? "-"}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {changeStatusLabel(changeItem.review_status)}
                          {changeItem.human_note && <div style={{ color: "#52607a" }}>{changeItem.human_note}</div>}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {changeItem.review_status === "SUGGESTED" && (
                              <button type="button" onClick={() => void handleChangeDecision(changeItem.id, "CONFIRM")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Confirmar
                              </button>
                            )}
                            <button type="button" onClick={() => openEditChange(changeItem)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                              Modificar
                            </button>
                            {changeItem.review_status !== "REJECTED" ? (
                              <button type="button" onClick={() => void handleChangeDecision(changeItem.id, "REJECT")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Rechazar
                              </button>
                            ) : (
                              <button type="button" onClick={() => void handleChangeDecision(changeItem.id, "RESET_TO_SUGGESTED")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Restablecer
                              </button>
                            )}
                            <button type="button" onClick={() => void openChangeSource(changeItem)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                              Ver fuente
                            </button>
                          </div>

                          {changeItem.evidence.length > 0 && (
                            <details style={{ marginTop: 6 }}>
                              <summary style={{ cursor: "pointer", color: "#1b5bd8", fontWeight: 700 }}>Evidencias</summary>
                              <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
                                {changeItem.evidence.map((evidence) => (
                                  <div key={evidence.id} style={{ fontSize: 12, color: "#52607a" }}>
                                    "{evidence.source_excerpt}" ({evidence.source_filename ?? evidence.source_document_id} · pág. {evidence.source_page ?? "-"})
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}

                          {editingChangeId === changeItem.id && (
                            <div style={{ marginTop: 10, border: "1px solid #d9e1ec", borderRadius: 8, padding: 10, background: "#f8fafc", display: "grid", gap: 8 }}>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Tipo de cambio
                                <select value={editChangeType} onChange={(event) => setEditChangeType(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }}>
                                  {CHANGE_TYPE_OPTIONS.map((item) => (
                                    <option key={item} value={item}>{item}</option>
                                  ))}
                                </select>
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Documento destino
                                <select value={editChangeTargetDocumentId} onChange={(event) => setEditChangeTargetDocumentId(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }}>
                                  <option value="">Sin resolver</option>
                                  {documents
                                    .filter((item) => item.id !== changeItem.source_document_id && item.is_current)
                                    .map((item) => (
                                      <option key={item.id} value={item.id}>{item.original_filename}</option>
                                    ))}
                                </select>
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Ubicación / numeral
                                <input value={editChangeLocator} onChange={(event) => setEditChangeLocator(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Texto anterior
                                <textarea value={editChangeBeforeText} onChange={(event) => setEditChangeBeforeText(event.target.value)} style={{ width: "100%", minHeight: 56, padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Texto nuevo
                                <textarea value={editChangeAfterText} onChange={(event) => setEditChangeAfterText(event.target.value)} style={{ width: "100%", minHeight: 56, padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Nota
                                <textarea value={editChangeNote} onChange={(event) => setEditChangeNote(event.target.value)} style={{ width: "100%", minHeight: 56, padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                <button type="button" onClick={() => void saveChangeOverride(changeItem.id)} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                                  Guardar
                                </button>
                                <button type="button" onClick={cancelEditChange} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Estado efectivo</h2>
            <button type="button" onClick={() => selectedTenderId && void loadEffectiveState(selectedTenderId)} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
              {effectiveStateLoading ? "Actualizando..." : "Actualizar estado efectivo"}
            </button>
          </div>

          {effectiveStateLoading && <div style={{ color: "#52607a", fontSize: 13 }}>Calculando estado efectivo...</div>}
          {!effectiveStateLoading && !effectiveState && <div style={{ color: "#52607a", fontSize: 13 }}>No se pudo cargar el estado efectivo.</div>}

          {effectiveState && (
            <>
              <div style={{ marginTop: 10, fontSize: 13, color: "#52607a" }}>
                Versión {effectiveState.state_version} • Actualizado: {new Date(effectiveState.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Ámbitos analizados</div>
                  <div style={{ fontWeight: 700 }}>{effectiveState.summary.total_scopes}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Determinados</div>
                  <div style={{ fontWeight: 700 }}>{effectiveState.summary.determined}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Pendientes de revisión</div>
                  <div style={{ fontWeight: 700 }}>{effectiveState.summary.pending_review}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Orden ambiguo</div>
                  <div style={{ fontWeight: 700 }}>{effectiveState.summary.ambiguous_precedence}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Destino no resuelto</div>
                  <div style={{ fontWeight: 700 }}>{effectiveState.summary.unresolved_target}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento afectado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Ubicación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Último cambio confirmado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Fecha de cambio</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Pendientes</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Fuente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {effectiveState.scopes.map((scope) => {
                      const effective = scope.effective_mutation;
                      const latestDate = effective?.temporal_event_date ?? "-";
                      const latestTime = effective?.temporal_event_time ? ` ${effective.temporal_event_time.slice(0, 5)}` : "";
                      const latestChangeText = effective
                        ? `${effective.change_type}: ${effective.before_text ?? "-"} -> ${effective.after_text ?? "-"}`
                        : "-";
                      const sourceText = effective
                        ? `${effective.source_filename ?? effective.source_document_id} · pág. ${effective.source_page ?? "-"}`
                        : "-";

                      return (
                        <tr key={scope.scope_key}>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            {scope.target_filename ?? scope.target_reference_key ?? "Sin destino"}
                          </td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{scope.target_locator_text ?? "-"}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            <div>{latestChangeText}</div>
                            {scope.resolution_status === "AMBIGUOUS_PRECEDENCE" && (
                              <div style={{ marginTop: 6, color: "#7a4b00" }}>
                                No hay evidencia temporal suficiente para determinar qué cambio es posterior.
                              </div>
                            )}
                          </td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{`${latestDate}${latestTime}`}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            {effectiveStatusLabel(scope.resolution_status)}
                            <div style={{ color: "#52607a", marginTop: 4 }}>{scope.temporal_reason}</div>
                          </td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{scope.pending_changes.length}</td>
                          <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                            <div>{sourceText}</div>
                            {scope.warnings.length > 0 && (
                              <details style={{ marginTop: 6 }}>
                                <summary style={{ cursor: "pointer", color: "#1b5bd8", fontWeight: 700 }}>Advertencias</summary>
                                <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
                                  {scope.warnings.map((warning) => (
                                    <div key={`${scope.scope_key}-${warning}`} style={{ color: "#52607a" }}>{warning}</div>
                                  ))}
                                </div>
                              </details>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2 style={{ marginTop: 0 }}>Mapa documental</h2>
          {relationshipBaselineLoading && <div style={{ color: "#52607a", fontSize: 13 }}>Cargando baseline relacional...</div>}
          {!relationshipBaselineLoading && !relationshipBaseline && (
            <div style={{ color: "#52607a", fontSize: 13 }}>No se pudo cargar el baseline relacional.</div>
          )}
          {relationshipBaseline && (
            <>
              <div style={{ fontSize: 13, color: "#52607a" }}>
                Baseline {relationshipBaseline.baseline_version} (fuente audit {relationshipBaseline.source_audit_version}) • {new Date(relationshipBaseline.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Relaciones</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.counts.relationship_edge_count}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencias ambiguas</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.reference_status_counts.AMBIGUOUS}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Referencia sin documento físico resuelto</div>
                  <div style={{ fontWeight: 700 }}>{relationshipBaseline.reference_status_counts.UNRESOLVED}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Integridad del grafo</div>
                  <div style={{ fontWeight: 700 }}>Dup {relationshipBaseline.counts.duplicate_edge_count} • Self {relationshipBaseline.counts.self_edge_count}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento origen</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Relación</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Documento destino</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Evidencias</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relationshipBaseline.document_map.map((entry) => (
                      <tr key={`${entry.source_document_id}-${entry.relationship_type}-${entry.target_document_id}`}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.source_filename ?? entry.source_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.relationship_type}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>{entry.target_filename ?? entry.target_document_id}</td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {entry.supporting_reference_count} refs • págs {entry.supporting_pages.length > 0 ? entry.supporting_pages.join(", ") : "-"} • origen {entry.resolution_origin}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Timeline del procedimiento</h2>
            <button type="button" onClick={() => void handleAnalyzeEvents()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
              {timelineLoading ? "Analizando..." : "Analizar eventos"}
            </button>
          </div>

          {timelineLoading && <div style={{ color: "#52607a", fontSize: 13 }}>Cargando timeline...</div>}
          {!timelineLoading && !timeline && <div style={{ color: "#52607a", fontSize: 13 }}>Sin timeline todavía para esta licitación.</div>}

          {timeline && (
            <>
              <div style={{ marginTop: 10, fontSize: 13, color: "#52607a" }}>
                Versión {timeline.timeline_version} • Actualizado: {new Date(timeline.generated_at).toLocaleString()}
              </div>
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Total eventos</div>
                  <div style={{ fontWeight: 700 }}>{timeline.counts.total_events}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Sugeridos / Confirmados</div>
                  <div style={{ fontWeight: 700 }}>{timeline.counts.suggested_events} / {timeline.counts.confirmed_events}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Rechazados</div>
                  <div style={{ fontWeight: 700 }}>{timeline.counts.rejected_events}</div>
                </div>
                <div style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                  <div style={{ fontSize: 12, color: "#52607a" }}>Duplicados semánticos</div>
                  <div style={{ fontWeight: 700 }}>{timeline.counts.duplicate_semantic_count}</div>
                </div>
              </div>

              <div style={{ marginTop: 12, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc" }}>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Evento</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Fecha / Hora</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Estado</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Fuente</th>
                      <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e8edf2" }}>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.events.map((eventItem) => (
                      <tr key={eventItem.id}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ fontWeight: 700 }}>{eventItem.human_title ?? eventItem.title}</div>
                          <div style={{ color: "#52607a" }}>{eventItem.human_event_type ?? eventItem.event_type}</div>
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {eventItem.human_event_date ?? eventItem.event_date ?? "-"} {eventItem.human_event_time ?? eventItem.event_time ?? ""}
                          <div style={{ color: "#52607a" }}>Precisión: {eventItem.date_precision}</div>
                          {hasHumanOverride(eventItem) && (
                            <div style={{ color: "#0f766e", marginTop: 4 }}>Modificado por usuario</div>
                          )}
                          {hasHumanOverride(eventItem) && (
                            <div style={{ color: "#52607a", marginTop: 4 }}>
                              Detectado: {eventItem.event_date ?? "-"} {eventItem.event_time ?? ""}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {eventStatusLabel(eventItem.review_status)}
                          {eventItem.human_note && <div style={{ color: "#52607a", marginTop: 4 }}>{eventItem.human_note}</div>}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          {eventItem.source_filename ?? eventItem.source_document_id ?? "-"}
                          <div style={{ color: "#52607a" }}>Pág. {eventItem.source_page ?? "-"}</div>
                          {eventItem.evidence.length > 0 && (
                            <details style={{ marginTop: 6 }}>
                              <summary style={{ cursor: "pointer", color: "#1b5bd8", fontWeight: 700 }}>Evidencia</summary>
                              <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
                                {eventItem.evidence.map((evidence) => (
                                  <div key={evidence.id} style={{ fontSize: 12, color: "#52607a" }}>
                                    "{evidence.source_excerpt}" ({evidence.source_filename ?? evidence.source_document_id} · pág. {evidence.source_page ?? "-"})
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}
                        </td>
                        <td style={{ padding: 8, borderBottom: "1px solid #f1f5f9" }}>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {eventItem.review_status === "SUGGESTED" && (
                              <button type="button" onClick={() => void handleEventDecision(eventItem.id, "CONFIRM")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Confirmar
                              </button>
                            )}
                            <button type="button" onClick={() => openEditEvent(eventItem)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                              Modificar
                            </button>
                            {eventItem.review_status !== "REJECTED" ? (
                              <button type="button" onClick={() => void handleEventDecision(eventItem.id, "REJECT")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Rechazar
                              </button>
                            ) : (
                              <button type="button" onClick={() => void handleEventDecision(eventItem.id, "RESET_TO_SUGGESTED")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Restablecer
                              </button>
                            )}
                            {eventItem.source_document_id && (
                              <button type="button" onClick={() => void openEventSource(eventItem)} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                Ver fuente
                              </button>
                            )}
                          </div>
                          {editingEventId === eventItem.id && (
                            <div style={{ marginTop: 10, border: "1px solid #d9e1ec", borderRadius: 8, padding: 10, background: "#f8fafc", display: "grid", gap: 8 }}>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Evento
                                <select value={editEventType} onChange={(event) => setEditEventType(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }}>
                                  {EVENT_TYPE_OPTIONS.map((item) => (
                                    <option key={item} value={item}>{item}</option>
                                  ))}
                                </select>
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Título
                                <input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Fecha
                                <input type="date" value={editDate} onChange={(event) => setEditDate(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Hora (opcional)
                                <input type="time" value={editTime} onChange={(event) => setEditTime(event.target.value)} style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <label style={{ fontSize: 12, color: "#52607a" }}>
                                Nota (opcional)
                                <textarea value={editNote} onChange={(event) => setEditNote(event.target.value)} style={{ width: "100%", minHeight: 68, padding: 8, borderRadius: 6, border: "1px solid #cfd8e3", marginTop: 4 }} />
                              </label>
                              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                <button type="button" onClick={() => void saveEventOverride(eventItem.id)} style={{ padding: "6px 10px", borderRadius: 6, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                                  Guardar
                                </button>
                                <button type="button" onClick={cancelEditEvent} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {selectedTenderId && (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Import Documents</h2>
          <p style={{ color: "#52607a", marginTop: -4 }}>
            Select a Tender and import multiple files or an entire folder. Duplicates are detected by SHA-256.
          </p>
          <label style={{ display: "inline-block", marginTop: 12 }}>
            <input type="file" multiple onChange={handleImport} style={{ display: "block" }} />
          </label>
          <div style={{ marginTop: 12, color: "#52607a" }}>{importing ? "Importing..." : "Ready to import."}</div>

          {pendingConflict && (
            <div style={{ marginTop: 16, border: "1px solid #d9e1ec", borderRadius: 12, background: "#fff8e7", padding: 16 }}>
              <h3 style={{ marginTop: 0 }}>Conflicto de documento</h3>
              <p style={{ margin: "8px 0" }}>
                Ya existe un documento con el mismo nombre, pero el contenido es diferente. Archivo: <strong>{pendingConflict.filename}</strong>
              </p>

              {pendingConflict.candidates.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>Selecciona la revisión actual para registrar la nueva revisión</label>
                  <select
                    value={selectedRevisionTargetId}
                    onChange={(event) => setSelectedRevisionTargetId(event.target.value)}
                    style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #cfd8e3" }}
                  >
                    {pendingConflict.candidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.original_filename} • Rev {candidate.revision_number} • {candidate.is_current ? "Vigente" : "Sustituido"}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
                <button type="button" onClick={() => void resolveConflict("IMPORT_INDEPENDENT")} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                  Importar como documento independiente
                </button>
                <button type="button" onClick={() => void resolveConflict("NEW_REVISION")} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                  Registrar como nueva revisión
                </button>
                <button type="button" onClick={() => setPendingConflict(null)} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {importResults.length > 0 && (
            <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
              {importResults.map((result, index) => (
                <div key={`${result.filename}-${index}`} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 12, background: "#f8fafc" }}>
                  <div style={{ fontWeight: 700 }}>{result.filename}</div>
                  <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                    {result.status} • {result.message || "No message"}
                  </div>
                  {result.sha256 && <div style={{ fontSize: 12, color: "#52607a" }}>SHA-256: {result.sha256}</div>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {selectedTenderId ? (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Documentos</h2>

          {documentsLoading && <p>Cargando documentos...</p>}

          {!documentsLoading && documentsError && <p>{documentsError}</p>}

          {!documentsLoading && !documentsError && documents.length === 0 && (
            <p>Esta licitación todavía no tiene documentos importados.</p>
          )}

          {!documentsLoading && !documentsError && documents.length > 0 && (
            <div style={{ display: "grid", gap: 12 }}>
              {documents.map((document) => (
                <div key={document.id} style={{ border: "1px solid #e8edf2", borderRadius: 10, padding: 14, background: selectedDocumentId === document.id ? "#edf4ff" : "#f8fafc" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{document.original_filename}</div>
                      <div style={{ fontSize: 12, color: "#52607a", marginTop: 6 }}>
                        Revisión {document.revision_number} • {document.is_current ? "Vigente" : "Sustituido"}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDocumentId(document.id);
                        void loadDocumentPages(selectedTenderId ?? "", document.id);
                        void loadDocumentClassification(selectedTenderId ?? "", document.id);
                        void loadDocumentReferences(selectedTenderId ?? "", document.id);
                      }}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: "1px solid #cfd8e3",
                        background: selectedDocumentId === document.id ? "#1b5bd8" : "#fff",
                        color: selectedDocumentId === document.id ? "#fff" : "#1a1a1a",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {selectedDocumentId === document.id ? "Vista previa" : "Ver"}
                    </button>
                  </div>
                  {document.sha256 && (
                    <div style={{ fontSize: 11, color: "#52607a", marginTop: 6, wordBreak: "break-all" }}>
                      SHA-256: {document.sha256.slice(0, 12)}...
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {selectedDocument && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ marginBottom: 12 }}>{selectedDocument.original_filename}</h3>

              {isPdfDocument(selectedDocument) && (
                <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
                  <button type="button" onClick={() => void handleExtractPdfText()} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>
                    Extraer texto PDF
                  </button>
                  <button type="button" onClick={() => void handleClassifyDocument()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                    {classificationLoading ? "Clasificando..." : "Clasificar documento"}
                  </button>
                  <button type="button" onClick={() => void handleAnalyzeReferences()} style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>
                    {referenceLoading ? "Analizando referencias..." : "Analizar referencias"}
                  </button>
                  <span style={{ fontSize: 12, color: "#52607a" }}>
                    Estado: {selectedDocument.processing_status ?? "PENDING"}
                  </span>
                </div>
              )}

              {referenceAnalysis && (
                <div style={{ marginBottom: 20, border: "1px solid #d9e1ec", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>Referencias detectadas</h4>
                  <div style={{ fontSize: 12, color: "#52607a", marginBottom: 10 }}>
                    Estado análisis: {referenceAnalysis.status} • Total: {referenceAnalysis.counts.total_reference_mentions} • Auto-resueltas: {referenceAnalysis.counts.resolved_references} • Resueltas por usuario: {referenceAnalysis.counts.human_resolved_references} • Ambiguas: {referenceAnalysis.counts.ambiguous_references} • Sin documento resuelto: {referenceAnalysis.counts.unresolved_references} • Ignoradas: {referenceAnalysis.counts.ignored_references}
                  </div>

                  {referenceAnalysis.references.length === 0 ? (
                    <div style={{ fontSize: 12, color: "#52607a" }}>No se detectaron referencias documentales.</div>
                  ) : (
                    <div style={{ display: "grid", gap: 8 }}>
                      {groupedReferences.map((group) => (
                        <div key={group.groupKey} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#fff" }}>
                          <div style={{ fontWeight: 700, marginBottom: 6 }}>{group.normalized_reference_key}</div>
                          <div style={{ fontSize: 12, color: "#52607a" }}>
                            {group.mentions.length} menciones • Estado: {referenceStatusLabel(group.resolution_status)} • Relación: {group.relationship_hint} • Páginas: {group.page_numbers.length > 0 ? group.page_numbers.join(", ") : "-"}
                          </div>
                          <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                            Destino: {group.target_label}
                          </div>
                          {group.candidate_label && (
                            <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                              Candidatos: {group.candidate_label}
                            </div>
                          )}

                          <details style={{ marginTop: 8 }}>
                            <summary style={{ cursor: "pointer", fontSize: 12, color: "#1b5bd8", fontWeight: 700 }}>Ver evidencias y acciones</summary>
                            <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
                              {group.mentions.map((reference) => (
                                <div key={reference.id} style={{ border: "1px solid #edf2f7", borderRadius: 8, padding: 8, background: "#f8fafc" }}>
                                  <div style={{ fontSize: 12, color: "#52607a" }}>
                                    Página: {reference.page_number ?? "-"} • Texto: {reference.raw_reference_text}
                                  </div>
                                  <div style={{ fontSize: 12, marginTop: 4 }}>{reference.excerpt}</div>
                                  {(reference.resolution_status === "AMBIGUOUS" || reference.resolution_status === "UNRESOLVED") && (
                                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                                      <select
                                        value={referenceTargetSelections[reference.id] ?? ""}
                                        onChange={(event) =>
                                          setReferenceTargetSelections((prev) => ({
                                            ...prev,
                                            [reference.id]: event.target.value,
                                          }))
                                        }
                                        style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #cfd8e3" }}
                                      >
                                        <option value="">Seleccionar documento destino</option>
                                        {reference.ambiguous_candidates.map((candidate) => (
                                          <option key={candidate.document_id} value={candidate.document_id}>
                                            {candidateLabel(candidate)}
                                          </option>
                                        ))}
                                      </select>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "RESOLVE_TO_DOCUMENT")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Resolver
                                      </button>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "MARK_UNRESOLVED")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Marcar no encontrada
                                      </button>
                                      <button type="button" onClick={() => void handleReferenceDecision(reference.id, "IGNORE_REFERENCE")} style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #cfd8e3", background: "#fff", fontWeight: 700 }}>
                                        Ignorar
                                      </button>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {classificationResult && (
                <div style={{ marginBottom: 20, border: "1px solid #d9e1ec", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{classificationResult.effective_type}</div>
                      <div style={{ fontSize: 12, color: "#52607a", marginTop: 4 }}>
                        Tipo sugerido: {classificationResult.suggested_type} • Puntuación: {classificationResult.suggested_score}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button type="button" onClick={() => void handleConfirmClassification()} style={{ padding: "8px 12px", borderRadius: 8, border: "none", background: "#1b5bd8", color: "#fff", fontWeight: 700 }}>Confirmar</button>
                      <button type="button" onClick={() => void handleReviewClassification()} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cfd8e3", background: "#fff", color: "#1a1a1a", fontWeight: 700 }}>Revisar</button>
                    </div>
                  </div>

                  {classificationResult.candidate_scores.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>Tipos candidatos</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {classificationResult.candidate_scores.map((candidate) => (
                          <span key={candidate.type} style={{ fontSize: 12, borderRadius: 999, background: "#ede9fe", color: "#312e81", padding: "4px 8px", fontWeight: 700 }}>
                            {candidate.type} ({candidate.score})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {classificationResult.functional_tags.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>Funciones detectadas</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {classificationResult.functional_tags.map((tag) => (
                          <span key={tag.tag} style={{ fontSize: 12, borderRadius: 999, background: "#e0f2fe", color: "#0f172a", padding: "4px 8px", fontWeight: 700 }}>
                            {tag.tag} ({tag.score})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {classificationResult.evidence.length > 0 && (
                    <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                      {classificationResult.evidence.slice(0, 3).map((item, index) => (
                        <div key={`${item.signal}-${index}`} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#fff" }}>
                          <div style={{ fontSize: 12, color: "#52607a", marginBottom: 6 }}>
                            {item.source_kind} • {item.signal} • peso {item.weight_or_score}
                          </div>
                          <div style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>{item.excerpt}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {isPdfDocument(selectedDocument) && (
                <div style={{ marginBottom: 16, border: "1px solid #e8edf2", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>OCR providers</h4>
                  <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <select value={ocrMode} onChange={(event) => setOcrMode(event.target.value)} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #cfd8e3" }}>
                      <option value="AUTO">AUTO</option>
                      <option value="TESSERACT">TESSERACT</option>
                      <option value="PADDLEOCR">PADDLEOCR</option>
                      <option value="COMPARE">COMPARE</option>
                    </select>
                    <button type="button" onClick={() => void handleRunOcr()} disabled={ocrRunning} style={{ padding: "10px 14px", borderRadius: 8, border: "none", background: "#0f766e", color: "#fff", fontWeight: 700, cursor: ocrRunning ? "not-allowed" : "pointer" }}>
                      {ocrRunning ? "Procesando OCR..." : "Ejecutar OCR"}
                    </button>
                  </div>

                  <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                    {ocrProviders.length === 0 ? (
                      <div style={{ color: "#52607a", fontSize: 12 }}>Catalogando providers OCR…</div>
                    ) : (
                      ocrProviders.map((provider) => (
                        <div key={provider.provider_id} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", border: "1px solid #d9e1ec", borderRadius: 8, padding: "8px 10px", background: "#fff" }}>
                          <div>
                            <strong>{provider.provider_name}</strong>
                            <div style={{ fontSize: 12, color: "#52607a" }}>{provider.version ?? "versión desconocida"}</div>
                          </div>
                          <span style={{ fontSize: 12, borderRadius: 999, padding: "4px 8px", background: provider.status === "AVAILABLE" ? "#dcfce7" : "#fee2e2", color: provider.status === "AVAILABLE" ? "#166534" : "#991b1b", fontWeight: 700 }}>
                            {provider.status}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {isPdfDocument(selectedDocument) && selectedDocumentUrl ? (
                <iframe src={selectedDocumentUrl} className="pdf-viewer" title={selectedDocument.original_filename} />
              ) : (
                <div className="viewer-placeholder">Este documento no puede mostrarse en el visor local PDF.</div>
              )}

              {documentPages.length > 0 && (
                <div style={{ marginTop: 20, border: "1px solid #e8edf2", borderRadius: 12, padding: 16, background: "#f8fafc" }}>
                  <h4 style={{ marginTop: 0, marginBottom: 12 }}>Texto extraído por página</h4>

                  {documentPagesLoading ? (
                    <p>Cargando páginas…</p>
                  ) : (
                    <>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                        {documentPages.map((page) => (
                          <button
                            key={page.id}
                            type="button"
                            onClick={() => setSelectedPageNumber(page.page_number)}
                            style={{
                              borderRadius: 999,
                              border: selectedPageNumber === page.page_number ? "1px solid #1b5bd8" : "1px solid #d9e1ec",
                              background: selectedPageNumber === page.page_number ? "#edf4ff" : "#fff",
                              color: selectedPageNumber === page.page_number ? "#1b5bd8" : "#1a1a1a",
                              padding: "6px 10px",
                              cursor: "pointer",
                              fontWeight: 700,
                            }}
                          >
                            Pág. {page.page_number}
                          </button>
                        ))}
                      </div>

                      {selectedPage && (
                        <div style={{ display: "grid", gap: 16 }}>
                          <div style={{ border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#fff" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
                              <strong>Texto nativo</strong>
                              <span style={{ color: "#52607a", fontSize: 12 }}>
                                {selectedPage.status} • {selectedPage.char_count} caracteres • {selectedPage.extraction_method}
                              </span>
                            </div>
                            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, lineHeight: 1.5 }}>
                              {selectedPage.text || "(Sin texto nativo detectado en esta página)"}
                            </pre>
                          </div>

                          {selectedPage.ocr_results && selectedPage.ocr_results.length > 0 && (
                            <div style={{ border: "1px solid #d9e1ec", borderRadius: 10, padding: 12, background: "#fff" }}>
                              <div style={{ marginBottom: 12, fontWeight: 700 }}>OCR alternativas</div>
                              <div style={{ display: "grid", gap: 12 }}>
                                {selectedPage.ocr_results.map((ocrResult) => (
                                  <div key={ocrResult.id} style={{ border: "1px solid #e8edf2", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
                                      <strong>OCR — {ocrResult.engine}</strong>
                                      <span style={{ color: "#52607a", fontSize: 12 }}>
                                        {ocrResult.status} • {ocrResult.text.length} caracteres • {ocrResult.engine_version}
                                      </span>
                                    </div>
                                    <div style={{ color: "#52607a", fontSize: 12, marginBottom: 8 }}>
                                      {ocrResult.language || "idioma no especificado"}
                                    </div>
                                    {ocrResult.status === "OCR_FAILED" ? (
                                      <div style={{ color: "#991b1b", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 6, padding: 8 }}>
                                        OCR falló: {ocrResult.warnings || "No se pudo completar la lectura por OCR."}
                                      </div>
                                    ) : (
                                      <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12, lineHeight: 1.5 }}>
                                        {ocrResult.text || "No se detectó texto OCR en esta página."}
                                      </pre>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      ) : (
        <section style={{ marginTop: 24, border: "1px solid #d9e1ec", borderRadius: 12, padding: 20, background: "#fff" }}>
          <h2>Documentos</h2>
          <p style={{ color: "#52607a" }}>Selecciona una licitación para ver sus documentos</p>
        </section>
      )}
    </div>
  );
}

export default App;
