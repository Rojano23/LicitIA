# Selective blind first pass 06v7_eee8df9b4a1f44428531dbae0c236a1d

HEAD: 429bf2ff95043c6d74af379a22d85bdd85843340

Semantic correctness remains unadjudicated.

```json
{
  "native": {
    "documents_available": 8,
    "pages_available": 251
  },
  "ocr": {
    "interpretation_states": {
      "NOT_ATTEMPTED": 257,
      "UNRESOLVED": 1000
    },
    "native_sufficient": 996,
    "ocr_avoided": 996,
    "ocr_completed": 10,
    "ocr_eligible": 10,
    "ocr_executed": 4,
    "ocr_execution_unknown": 0,
    "ocr_failed": 0,
    "ocr_unavailable": 0,
    "pages": 253,
    "perception_states": {
      "INSUFFICIENT": 10,
      "SUFFICIENT": 996,
      "UNKNOWN": 251
    },
    "sufficiency_reasons": {
      "CANONICAL_TEXT_READABLE_FOR_TASK_ATTEMPT": 996,
      "REQUESTED_REGION_TEXT_NOT_COVERED": 10,
      "TEXT_TASK_CONTRACT_REQUIRED": 251
    },
    "tasks": 1257,
    "visual_pending": 0
  },
  "ocr_budget_exhausted": 0,
  "ocr_exhausted": 0,
  "ocr_reused": 6,
  "ocr_states": {
    "COMPLETED": 10,
    "SKIPPED": 1247
  },
  "provenance_capabilities": {
    "('NATIVE', 'STRUCTURE')": 253,
    "('NATIVE', 'TRANSCRIPTION')": 253,
    "('OCR', 'STRUCTURE')": 253,
    "('OCR', 'TRANSCRIPTION')": 253,
    "('VISION', 'STRUCTURE')": 253,
    "('VISION', 'TRANSCRIPTION')": 253
  },
  "vision": {
    "avoided": 0,
    "budget_exhausted": 5,
    "eligible": 8,
    "executed": 4,
    "failures": 2,
    "interpretation_states": {
      "AMBIGUOUS": 4,
      "NOT_ATTEMPTED": 4
    },
    "needed": 8,
    "pending": 8,
    "perception_states": {
      "VISUAL_REQUIRED": 8
    },
    "retries": 1,
    "retry_exhausted": 1,
    "reused": 0,
    "sufficiency_reasons": {
      "BOUND_REGION_EVIDENCE_REQUIRED": 8
    },
    "tasks": {
      "DETAIL_TRANSCRIPTION": 6,
      "STRUCTURE_SCOPE": 4
    }
  },
  "vision_completed": 2,
  "vision_states": {
    "BUDGET_EXHAUSTED": 5,
    "COMPLETED": 2,
    "FAILED": 2,
    "RETRY_EXHAUSTED": 1
  }
}
```
