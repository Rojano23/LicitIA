export type TenderRequirementMatrix = {
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

export type RequirementMatrixItem = {
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

export type RequirementSourceOccurrence = {
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

export type RequirementEvidenceExpectation = {
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

export type ComplianceMatrix = {
  tender_id: string;
  company_id: string;
  matrix_version: string;
  generated_at: string;
  scope_note: string;
  summary: {
    total_requirements: number;
    active_requirements: number;
    excluded_rejected_count: number;
    excluded_superseded_count: number;
    company_evidence_count: number;
    current_company_evidence_count: number;
    matched_evidence_count: number;
    confirmed_match_count: number;
    finalized_count: number;
    action_required_count: number;
    review_required_count: number;
    direct_verification_pending_count: number;
    condition_unresolved_count: number;
    not_applicable_count: number;
    human_review_completion_percent: number;
    finding_counts: Record<string, number>;
  };
  rows: ComplianceMatrixRow[];
};

export type ComplianceMatrixRow = {
  requirement: RequirementMatrixItem;
  system_assessment: ComplianceAssessment | null;
  human_decision: ComplianceDecision | null;
  decision_relation: string | null;
  operational_state: string;
  findings: ComplianceMatrixFinding[];
  matches: RequirementEvidenceMatch[];
};

export type ComplianceAssessment = {
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

export type ComplianceRequirementContext = {
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

export type ComplianceCheck = {
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

export type MatchCompanyEvidence = {
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

export type MatchEvidenceSourceDocument = {
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

export type MatchEvidenceReview = {
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

export type RequirementEvidenceMatch = {
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

export type EvidenceMatchReview = {
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

export type ComplianceDecision = {
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

export type ComplianceMatrixFinding = {
  code: string;
  severity: string;
  message: string;
  action: string;
};

export type TenderRequirementEvidenceMatches = {
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

export type RequirementEvidenceMatchRequirement = {
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

export type CompanyOption = {
  id: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  status: string;
};

export type TenderDocumentScopeSummary = {
  tender_id: string;
  document_id: string;
  source_filename: string | null;
  scope_summary_version: string;
  generated_at: string;
  summary_state: string;
  summary: {
    document_page_count: number;
    structurally_analyzed_count: number;
    resolved_count: number;
    needs_ocr_count: number;
    needs_vision_count: number;
    review_required_count: number;
    not_analyzed_count: number;
    groups_count: number;
    segments_count: number;
  };
  page_resolutions: ScopeSummaryPageResolution[];
  ownership_groups: ScopeSummaryOwnershipGroup[];
};

export type ScopeSummaryPageResolution = {
  document_page_id: string;
  page_number: number;
  has_resolution: boolean;
  status: string | null;
  selected_source_method: string | null;
  review_required: boolean;
  reason: string | null;
  scope_segment_count: number;
};

export type ScopeSummaryOwnershipGroup = {
  group_key: string;
  candidate_item_key: string | null;
  candidate_item_raw_label: string | null;
  review_required: boolean;
  canonical_items: ScopeSummaryCanonicalItem[];
  segments: ScopeSummarySegment[];
};

export type ScopeSummaryCanonicalItem = {
  tender_item_id: string;
  item_number: string | null;
  raw_description: string;
  quantity: string | null;
  unit: string | null;
};

export type ScopeSummarySegment = {
  id: string;
  source_document_id: string;
  source_filename: string | null;
  document_page_id: string;
  page_number: number;
  sequence_index: number;
  tender_item_id: string | null;
  candidate_item_key: string | null;
  candidate_item_raw_label: string | null;
  link_reason: string;
  source_method: string;
  source_locator: string;
  source_excerpt: string;
  review_required: boolean;
};
