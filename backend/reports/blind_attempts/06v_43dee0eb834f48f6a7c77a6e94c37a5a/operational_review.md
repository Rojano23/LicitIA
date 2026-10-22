# Blind Attempt #2 — operational execution review

Review JSON SHA-256: `70efa6520884ecd29d7eee33e1670a4cc5ef07967e455d4ea392c3be17726494`

First-pass SHA-256: `21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0`

No semantic adjudication. Original first-pass remains immutable.

```json
{
  "attempt": 2,
  "classification": "PASS",
  "classification_scope": "OPERATIONAL_EXECUTION_ONLY_NOT_SEMANTIC_CORRECTNESS",
  "run_id": "06v_43dee0eb834f48f6a7c77a6e94c37a5a",
  "HEAD": "c1c6ff4870dc94009b10d62f47020ef6cdf9d580",
  "freeze_sha256": "ac217404caf1b316416ee03f111383cead3b6e87af59e5470b6367da8aad7412",
  "config_sha256": "e791486037f6499595c02f36aa74b55fe171600b25ae7866e2026d3e71e884cd",
  "first_pass_sha256": "21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0",
  "import_manifest_sha256": "4556971cab26448b7fa6d927224a6bfcb83b11b0c71f70c29bfabbea6dac8897",
  "tender_id": "18a9459d-72e8-408b-89c8-81c8d35937f8",
  "database": {
    "database": "licitia_validation_06v",
    "document_count": 11,
    "revision": "20261013_req_perception_prov_072",
    "tender_count": 1
  },
  "reset": "CANONICAL_RESET_REIMPORT_COMPLETE_ATTEMPT1_DB_EXPORTED",
  "preparation_counts": {
    "PREPARED": 10,
    "UNAVAILABLE": 1
  },
  "preparation_reason_counts": {
    "NATIVE_PREPARATION_COMPLETE": 10,
    "UNSUPPORTED_NATIVE_CAPABILITY": 1
  },
  "other_document_failures": 0,
  "native_extraction_calls": 10,
  "phase_outcomes": [
    {
      "elapsed_seconds": 3.849872,
      "ended_at": "2026-10-14T22:03:57.675024+00:00",
      "phase": "document_native_preparation",
      "started_at": "2026-10-14T22:03:53.825168+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 6.881495,
      "ended_at": "2026-10-14T22:04:04.556622+00:00",
      "phase": "DI_routing",
      "started_at": "2026-10-14T22:03:57.675308+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 1.915326,
      "ended_at": "2026-10-14T22:04:06.472353+00:00",
      "phase": "Requirements",
      "started_at": "2026-10-14T22:04:04.556962+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 0.254797,
      "ended_at": "2026-10-14T22:04:06.727554+00:00",
      "phase": "requested_Evidence",
      "started_at": "2026-10-14T22:04:06.472655+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 1.336085,
      "ended_at": "2026-10-14T22:04:08.063964+00:00",
      "phase": "Scope",
      "started_at": "2026-10-14T22:04:06.727814+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 0.0022,
      "ended_at": "2026-10-14T22:04:08.067328+00:00",
      "phase": "Attributes",
      "started_at": "2026-10-14T22:04:08.064988+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 0.001374,
      "ended_at": "2026-10-14T22:04:08.069206+00:00",
      "phase": "Quantities",
      "started_at": "2026-10-14T22:04:08.067483+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 0.448326,
      "ended_at": "2026-10-14T22:04:08.517762+00:00",
      "phase": "Versions_Effective_Source",
      "started_at": "2026-10-14T22:04:08.069340+00:00",
      "status": "COMPLETE"
    },
    {
      "elapsed_seconds": 0.00367,
      "ended_at": "2026-10-14T22:04:08.521894+00:00",
      "phase": "Review",
      "started_at": "2026-10-14T22:04:08.518080+00:00",
      "status": "COMPLETE"
    }
  ],
  "metrics_collection_seconds": 0.972118,
  "provider_inference_calls": {
    "Ollama": 0,
    "Qwen": 0,
    "Tesseract_OCR": 0,
    "Vision": 0
  },
  "metrics": {
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
  },
  "integrity": {
    "attempt": 2,
    "attempt1_freeze_verified": true,
    "attempt2_freeze_verified": true,
    "canonical_native_page_provenance": true,
    "correctness": "NOT_ADJUDICATED",
    "document_ids_hashes_originals_preserved": true,
    "first_pass_sha256": "21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0",
    "historical_artifacts_checked": 63,
    "historical_artifacts_unchanged": true,
    "manual_semantic_inspection": false,
    "provider_inference_calls": 0,
    "run_id": "06v_43dee0eb834f48f6a7c77a6e94c37a5a",
    "source_method_observations": {
      "NATIVE": 502
    },
    "supported_documents_continued": true,
    "unsupported_document_count": 1,
    "unsupported_native_pages": 0,
    "unsupported_native_perception_provenance_created": false,
    "unsupported_remains_represented": true,
    "unsupported_trusted_automatic": false
  },
  "regression": [
    {
      "check": "focused",
      "command": [
        "/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        "-m",
        "pytest",
        "tests/test_document_preparation_recovery.py",
        "tests/test_documents.py",
        "tests/test_document_intelligence.py",
        "tests/test_document_structure_orchestrator.py",
        "tests/test_document_intelligence_06v_preflight.py",
        "tests/test_document_intelligence_integration.py",
        "-m",
        "not local_ollama",
        "-q"
      ],
      "exit_code": 0,
      "log_sha256": "9a3cd0e5fea32643938dddc7fd1f4bc0222437b5d2946d2a3f72574b30967d42",
      "summary": "280 passed, 1 deselected, 7 warnings in 15.90s"
    },
    {
      "check": "full",
      "command": [
        "/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        "-m",
        "pytest",
        "-m",
        "not local_ollama",
        "-q"
      ],
      "exit_code": 0,
      "log_sha256": "00cfa0894890a9b821fed6b581de0a04d333fadcc2f839a97cd3e5575c271274",
      "summary": "1729 passed, 1 deselected, 7 warnings in 98.78s (0:01:38)"
    },
    {
      "check": "compileall",
      "command": [
        "/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python",
        "-m",
        "compileall",
        "-q",
        "/Users/ceciliavalencia/LiticIA/backend/app",
        "/Users/ceciliavalencia/LiticIA/backend/scripts",
        "/Users/ceciliavalencia/LiticIA/backend/tests"
      ],
      "exit_code": 0,
      "log_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "summary": null
    }
  ],
  "historical_attempt1_preserved": true,
  "manual_semantic_inspection": false,
  "tracked_code_changes": false,
  "schema_changes": false,
  "new_migrations": false,
  "push_performed": false,
  "first_pass_path": "backend/reports/blind_attempts/06v_43dee0eb834f48f6a7c77a6e94c37a5a/results/06v_43dee0eb834f48f6a7c77a6e94c37a5a/first_pass.json",
  "blockers": []
}
```
