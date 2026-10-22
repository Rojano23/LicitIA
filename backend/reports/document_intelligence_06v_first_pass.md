# MVP-06.V.2 — First blind production run

```json
{
  "execution_status": "BLIND_RUN_EXECUTION_BLOCKER",
  "first_pass_path": "backend/reports/blind_first_passes/06v_6f6c60e697534a04abc3f922e698fef1/first_pass.json",
  "first_pass_sha256": "af9eeb1c94b79417033d6e533f4ca837ea94984a6085254392d39ff041fe5ead",
  "run_id": "06v_6f6c60e697534a04abc3f922e698fef1",
  "tender_id": "421da160-2a27-410b-b159-8f10eb99938d",
  "HEAD": "3c989fae39975ed89d185fe52af0f94ab4012497",
  "config_sha256": "73d56599fc016a7b11bf43b4e5a9a58bbd008ae28410224c6b78e01c8743f9f2",
  "import_manifest_sha256": "89a0df37929d4a4f69df0a7b16d643fef472f9d6557fe3f92b56083053a2bd4d",
  "database": {
    "database": "licitia_validation_06v",
    "revision": "20261013_req_perception_prov_072",
    "tender_count": 1,
    "document_count": 11
  },
  "phase_outcomes": [
    {
      "phase": "document_native_preparation",
      "started_at": "2026-10-14T06:53:16.519054+00:00",
      "status": "BLOCKED",
      "exception_type": "HTTPException",
      "exception": "400: Only PDF documents can be extracted.",
      "elapsed_seconds": 0.005322,
      "ended_at": "2026-10-14T06:53:16.524565+00:00"
    }
  ],
  "metrics_collection_seconds": 0.142638,
  "provider_calls": {
    "Vision": 0,
    "Ollama": 0,
    "Qwen": 0,
    "Tesseract_OCR": 0
  },
  "blocked_provider_attempts": [],
  "native_extraction_calls": 0,
  "metrics": {
    "schema_version": "DI_BLIND_METRICS_001",
    "first_pass": {
      "domains": {
        "DOCUMENTS": {
          "total": 11,
          "discovered": 11,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 11,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": 0.0,
          "unavailable_rate": 1.0,
          "trusted_automatic_rate_unadjudicated": 0.0
        },
        "REQUIREMENTS": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "REQUESTED_EVIDENCE": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "SCOPE": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "ATTRIBUTES": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "QUANTITIES": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "VERSIONS": {
          "total": 11,
          "discovered": 11,
          "trusted": 11,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": 0.0,
          "unavailable_rate": 0.0,
          "trusted_automatic_rate_unadjudicated": 0.0
        },
        "EFFECTS": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        },
        "STRUCTURE": {
          "total": 0,
          "discovered": 0,
          "trusted": 0,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": null,
          "unavailable_rate": null,
          "trusted_automatic_rate_unadjudicated": null
        }
      },
      "documents_total": 11,
      "pages_total": 0,
      "discovery_counts": {
        "rejected_requirement_candidates": 0,
        "requirement_candidates": 0
      },
      "versions": {
        "ACTIVE": 11
      },
      "review_queue": {
        "total": 0,
        "by_domain": {},
        "by_reason": {},
        "documents_affected": 0,
        "pages_affected": 0
      },
      "providers": [],
      "perception_availability": [],
      "conflicts_surfaced": 0,
      "stale_carry_violations": 0,
      "domain_impact": {
        "traceable_links": {},
        "causal_error_impact": null
      }
    },
    "post_adjudication": {
      "trusted_correct": null,
      "trusted_incorrect": null,
      "unsafe_trusted_contractual_errors": null,
      "unsafe_trusted_structural_errors": null,
      "safe_misses": null,
      "unnecessary_review": null,
      "critical_identifier_conflicts_correctly_surfaced": null,
      "quantity_unsafe_bindings": null,
      "attribute_unsafe_bindings": null,
      "safe_automatic_selections": null,
      "recall": null
    }
  },
  "errors": [
    "document_native_preparation:HTTPException:400: Only PDF documents can be extracted."
  ],
  "correctness_status": "NOT_ADJUDICATED",
  "freeze_verified": true,
  "code_config_changed": false,
  "manual_semantic_inspection": false
}
```
