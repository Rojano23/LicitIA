# MVP-06.V.2 — First blind production run

```json
{
  "execution_status": "COMPLETE",
  "first_pass_path": "backend/reports/blind_attempts/06v_43dee0eb834f48f6a7c77a6e94c37a5a/results/06v_43dee0eb834f48f6a7c77a6e94c37a5a/first_pass.json",
  "first_pass_sha256": "21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0",
  "run_id": "06v_43dee0eb834f48f6a7c77a6e94c37a5a",
  "tender_id": "18a9459d-72e8-408b-89c8-81c8d35937f8",
  "HEAD": "c1c6ff4870dc94009b10d62f47020ef6cdf9d580",
  "config_sha256": "e791486037f6499595c02f36aa74b55fe171600b25ae7866e2026d3e71e884cd",
  "import_manifest_sha256": "4556971cab26448b7fa6d927224a6bfcb83b11b0c71f70c29bfabbea6dac8897",
  "database": {
    "database": "licitia_validation_06v",
    "revision": "20261013_req_perception_prov_072",
    "tender_count": 1,
    "document_count": 11
  },
  "phase_outcomes": [
    {
      "phase": "document_native_preparation",
      "started_at": "2026-10-14T22:03:53.825168+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 3.849872,
      "ended_at": "2026-10-14T22:03:57.675024+00:00"
    },
    {
      "phase": "DI_routing",
      "started_at": "2026-10-14T22:03:57.675308+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 6.881495,
      "ended_at": "2026-10-14T22:04:04.556622+00:00"
    },
    {
      "phase": "Requirements",
      "started_at": "2026-10-14T22:04:04.556962+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 1.915326,
      "ended_at": "2026-10-14T22:04:06.472353+00:00"
    },
    {
      "phase": "requested_Evidence",
      "started_at": "2026-10-14T22:04:06.472655+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 0.254797,
      "ended_at": "2026-10-14T22:04:06.727554+00:00"
    },
    {
      "phase": "Scope",
      "started_at": "2026-10-14T22:04:06.727814+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 1.336085,
      "ended_at": "2026-10-14T22:04:08.063964+00:00"
    },
    {
      "phase": "Attributes",
      "started_at": "2026-10-14T22:04:08.064988+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 0.0022,
      "ended_at": "2026-10-14T22:04:08.067328+00:00"
    },
    {
      "phase": "Quantities",
      "started_at": "2026-10-14T22:04:08.067483+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 0.001374,
      "ended_at": "2026-10-14T22:04:08.069206+00:00"
    },
    {
      "phase": "Versions_Effective_Source",
      "started_at": "2026-10-14T22:04:08.069340+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 0.448326,
      "ended_at": "2026-10-14T22:04:08.517762+00:00"
    },
    {
      "phase": "Review",
      "started_at": "2026-10-14T22:04:08.518080+00:00",
      "status": "COMPLETE",
      "elapsed_seconds": 0.00367,
      "ended_at": "2026-10-14T22:04:08.521894+00:00"
    }
  ],
  "metrics_collection_seconds": 0.972118,
  "provider_calls": {
    "Vision": 0,
    "Ollama": 0,
    "Qwen": 0,
    "Tesseract_OCR": 0
  },
  "blocked_provider_attempts": [],
  "native_extraction_calls": 10,
  "preparation_results": [
    {
      "document_id": "015617b1-91fe-41e4-a7bf-befd1246d971",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 119,
      "reused": false
    },
    {
      "document_id": "02ee7c3d-6d7e-402f-9adf-663eabd27d0b",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 1,
      "reused": false
    },
    {
      "document_id": "5dbe08a3-6525-4995-a248-07901b3ee57c",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 20,
      "reused": false
    },
    {
      "document_id": "a01c1c77-9da4-48af-a1f8-c342981b6c58",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 26,
      "reused": false
    },
    {
      "document_id": "a72a4759-761f-470b-891d-1c7f387803b8",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 55,
      "reused": false
    },
    {
      "document_id": "ade2f09f-4147-4f90-bb76-30f3977fc686",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 3,
      "reused": false
    },
    {
      "document_id": "cffc9137-565f-4a7b-8470-6c8294038da4",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 12,
      "reused": false
    },
    {
      "document_id": "d0e05bd1-c933-4259-a9c7-610aaadd28fe",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "UNAVAILABLE",
      "reason": "UNSUPPORTED_NATIVE_CAPABILITY",
      "page_count": 0,
      "reused": false
    },
    {
      "document_id": "e0c592af-fe32-4ad3-97da-b08a7c91cfd5",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 5,
      "reused": false
    },
    {
      "document_id": "e493d850-421f-4643-aff7-108623c43583",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 11,
      "reused": false
    },
    {
      "document_id": "f9ca92e2-b4b8-473d-81f5-69381d593914",
      "capability": "NATIVE_PDF_TRANSCRIPTION",
      "status": "PREPARED",
      "reason": "NATIVE_PREPARATION_COMPLETE",
      "page_count": 1,
      "reused": false
    }
  ],
  "metrics": {
    "schema_version": "DI_BLIND_METRICS_001",
    "first_pass": {
      "domains": {
        "DOCUMENTS": {
          "total": 11,
          "discovered": 11,
          "trusted": 8,
          "review_required": 0,
          "rejected": 0,
          "unavailable": 3,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": 0.0,
          "unavailable_rate": 0.2727272727272727,
          "trusted_automatic_rate_unadjudicated": 0.0
        },
        "REQUIREMENTS": {
          "total": 31,
          "discovered": 31,
          "trusted": 0,
          "review_required": 31,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": 1.0,
          "unavailable_rate": 0.0,
          "trusted_automatic_rate_unadjudicated": 0.0
        },
        "REQUESTED_EVIDENCE": {
          "total": 8,
          "discovered": 8,
          "trusted": 0,
          "review_required": 8,
          "rejected": 0,
          "unavailable": 0,
          "trusted_automatic_unadjudicated": 0,
          "unresolved_binding": 0,
          "review_required_rate": 1.0,
          "unavailable_rate": 0.0,
          "trusted_automatic_rate_unadjudicated": 0.0
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
          "total": 253,
          "discovered": 253,
          "trusted": 2,
          "review_required": 249,
          "rejected": 0,
          "unavailable": 2,
          "trusted_automatic_unadjudicated": 2,
          "unresolved_binding": 0,
          "review_required_rate": 0.9841897233201581,
          "unavailable_rate": 0.007905138339920948,
          "trusted_automatic_rate_unadjudicated": 0.007905138339920948
        }
      },
      "documents_total": 11,
      "pages_total": 253,
      "discovery_counts": {
        "rejected_requirement_candidates": 0,
        "requirement_candidates": 43
      },
      "versions": {
        "ACTIVE": 11
      },
      "review_queue": {
        "total": 288,
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
        "pages_affected": 249
      },
      "providers": [
        {
          "provider": "PyMuPDF",
          "model": null,
          "capability": "TRANSCRIPTION",
          "source_method": "NATIVE",
          "artifacts": 253,
          "execution_events": 0,
          "calls": null,
          "calls_measurement": "NOT_MEASURED",
          "outcome_basis": "PERSISTED_ARTIFACTS",
          "success": 251,
          "failure": 2,
          "statuses": {
            "COMPLETED": 251,
            "UNAVAILABLE": 2
          },
          "artifact_statuses": {
            "COMPLETED": 251,
            "UNAVAILABLE": 2
          },
          "latencies_ms": [],
          "timeouts": 0,
          "truncations": 0
        }
      ],
      "perception_availability": [
        {
          "channel": "NATIVE",
          "capability": "STRUCTURE",
          "status": "RESOLVED",
          "count": 3
        },
        {
          "channel": "NATIVE",
          "capability": "STRUCTURE",
          "status": "REVIEW_REQUIRED",
          "count": 248
        },
        {
          "channel": "NATIVE",
          "capability": "STRUCTURE",
          "status": "UNAVAILABLE",
          "count": 2
        },
        {
          "channel": "NATIVE",
          "capability": "TRANSCRIPTION",
          "status": "REVIEW_REQUIRED",
          "count": 251
        },
        {
          "channel": "NATIVE",
          "capability": "TRANSCRIPTION",
          "status": "UNAVAILABLE",
          "count": 2
        },
        {
          "channel": "OCR",
          "capability": "STRUCTURE",
          "status": "UNAVAILABLE",
          "count": 253
        },
        {
          "channel": "OCR",
          "capability": "TRANSCRIPTION",
          "status": "UNAVAILABLE",
          "count": 253
        },
        {
          "channel": "VISION",
          "capability": "STRUCTURE",
          "status": "UNAVAILABLE",
          "count": 253
        },
        {
          "channel": "VISION",
          "capability": "TRANSCRIPTION",
          "status": "UNAVAILABLE",
          "count": 253
        }
      ],
      "conflicts_surfaced": 1,
      "stale_carry_violations": 0,
      "domain_impact": {
        "traceable_links": {
          "PERCEPTION->REQUIREMENTS": 31,
          "REQUIREMENTS->REQUESTED_EVIDENCE": 8
        },
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
  "errors": [],
  "correctness_status": "NOT_ADJUDICATED",
  "freeze_verified": true,
  "code_config_changed": false,
  "manual_semantic_inspection": false
}
```
