# Blind first pass 06v_43dee0eb834f48f6a7c77a6e94c37a5a

Code: c1c6ff4870dc94009b10d62f47020ef6cdf9d580

First-pass SHA-256: 21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0

Tender: 18a9459d-72e8-408b-89c8-81c8d35937f8

Correctness/recall remain unadjudicated. Analysis must use a new report.

```json
{
  "first_pass": {
    "conflicts_surfaced": 1,
    "discovery_counts": {
      "rejected_requirement_candidates": 0,
      "requirement_candidates": 43
    },
    "documents_total": 11,
    "domain_impact": {
      "causal_error_impact": null,
      "traceable_links": {
        "PERCEPTION->REQUIREMENTS": 31,
        "REQUIREMENTS->REQUESTED_EVIDENCE": 8
      }
    },
    "domains": {
      "ATTRIBUTES": {
        "discovered": 0,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": null,
        "total": 0,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": null,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": null,
        "unresolved_binding": 0
      },
      "DOCUMENTS": {
        "discovered": 11,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": 0.0,
        "total": 11,
        "trusted": 8,
        "trusted_automatic_rate_unadjudicated": 0.0,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 3,
        "unavailable_rate": 0.2727272727272727,
        "unresolved_binding": 0
      },
      "EFFECTS": {
        "discovered": 0,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": null,
        "total": 0,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": null,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": null,
        "unresolved_binding": 0
      },
      "QUANTITIES": {
        "discovered": 0,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": null,
        "total": 0,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": null,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": null,
        "unresolved_binding": 0
      },
      "REQUESTED_EVIDENCE": {
        "discovered": 8,
        "rejected": 0,
        "review_required": 8,
        "review_required_rate": 1.0,
        "total": 8,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": 0.0,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": 0.0,
        "unresolved_binding": 0
      },
      "REQUIREMENTS": {
        "discovered": 31,
        "rejected": 0,
        "review_required": 31,
        "review_required_rate": 1.0,
        "total": 31,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": 0.0,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": 0.0,
        "unresolved_binding": 0
      },
      "SCOPE": {
        "discovered": 0,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": null,
        "total": 0,
        "trusted": 0,
        "trusted_automatic_rate_unadjudicated": null,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": null,
        "unresolved_binding": 0
      },
      "STRUCTURE": {
        "discovered": 253,
        "rejected": 0,
        "review_required": 249,
        "review_required_rate": 0.9841897233201581,
        "total": 253,
        "trusted": 2,
        "trusted_automatic_rate_unadjudicated": 0.007905138339920948,
        "trusted_automatic_unadjudicated": 2,
        "unavailable": 2,
        "unavailable_rate": 0.007905138339920948,
        "unresolved_binding": 0
      },
      "VERSIONS": {
        "discovered": 11,
        "rejected": 0,
        "review_required": 0,
        "review_required_rate": 0.0,
        "total": 11,
        "trusted": 11,
        "trusted_automatic_rate_unadjudicated": 0.0,
        "trusted_automatic_unadjudicated": 0,
        "unavailable": 0,
        "unavailable_rate": 0.0,
        "unresolved_binding": 0
      }
    },
    "pages_total": 253,
    "perception_availability": [
      {
        "capability": "STRUCTURE",
        "channel": "NATIVE",
        "count": 3,
        "status": "RESOLVED"
      },
      {
        "capability": "STRUCTURE",
        "channel": "NATIVE",
        "count": 248,
        "status": "REVIEW_REQUIRED"
      },
      {
        "capability": "STRUCTURE",
        "channel": "NATIVE",
        "count": 2,
        "status": "UNAVAILABLE"
      },
      {
        "capability": "TRANSCRIPTION",
        "channel": "NATIVE",
        "count": 251,
        "status": "REVIEW_REQUIRED"
      },
      {
        "capability": "TRANSCRIPTION",
        "channel": "NATIVE",
        "count": 2,
        "status": "UNAVAILABLE"
      },
      {
        "capability": "STRUCTURE",
        "channel": "OCR",
        "count": 253,
        "status": "UNAVAILABLE"
      },
      {
        "capability": "TRANSCRIPTION",
        "channel": "OCR",
        "count": 253,
        "status": "UNAVAILABLE"
      },
      {
        "capability": "STRUCTURE",
        "channel": "VISION",
        "count": 253,
        "status": "UNAVAILABLE"
      },
      {
        "capability": "TRANSCRIPTION",
        "channel": "VISION",
        "count": 253,
        "status": "UNAVAILABLE"
      }
    ],
    "providers": [
      {
        "artifact_statuses": {
          "COMPLETED": 251,
          "UNAVAILABLE": 2
        },
        "artifacts": 253,
        "calls": null,
        "calls_measurement": "NOT_MEASURED",
        "capability": "TRANSCRIPTION",
        "execution_events": 0,
        "failure": 2,
        "latencies_ms": [],
        "model": null,
        "outcome_basis": "PERSISTED_ARTIFACTS",
        "provider": "PyMuPDF",
        "source_method": "NATIVE",
        "statuses": {
          "COMPLETED": 251,
          "UNAVAILABLE": 2
        },
        "success": 251,
        "timeouts": 0,
        "truncations": 0
      }
    ],
    "review_queue": {
      "by_domain": {
        "REQUESTED_EVIDENCE": 8,
        "REQUIREMENTS": 31,
        "STRUCTURE": 249
      },
      "by_reason": {
        "CURRENT_STRUCTURE_UNTRUSTWORTHY": 248,
        "DOMAIN_REVIEW_REQUIRED": 8,
        "FACT_REVIEW_REQUIRED": 31,
        "STRUCTURAL_BOUNDARY_CONFLICT": 1
      },
      "documents_affected": 8,
      "pages_affected": 249,
      "total": 288
    },
    "stale_carry_violations": 0,
    "versions": {
      "ACTIVE": 11
    }
  },
  "post_adjudication": {
    "attribute_unsafe_bindings": null,
    "critical_identifier_conflicts_correctly_surfaced": null,
    "quantity_unsafe_bindings": null,
    "recall": null,
    "safe_automatic_selections": null,
    "safe_misses": null,
    "trusted_correct": null,
    "trusted_incorrect": null,
    "unnecessary_review": null,
    "unsafe_trusted_contractual_errors": null,
    "unsafe_trusted_structural_errors": null
  },
  "schema_version": "DI_BLIND_METRICS_001"
}
```
