# Camelot Native — commit aceptado y readiness

Commit/HEAD: `14097f428e2185152aae1b671485244f1656fb07`. Parent: `0b04fc7677e670fb487683ac904d3c3a89daa373`.
Asunto: `feat(document-intelligence): integrate camelot native table proof`.

## Archivos exactos del commit

- `backend/app/blind_selective_freeze.py`
- `backend/app/camelot_table_adapter.py`
- `backend/app/camelot_table_contract.py`
- `backend/app/camelot_table_worker.py`
- `backend/app/native_table_relationships.py`
- `backend/app/structured_evidence.py`
- `backend/app/structured_evidence_grounding.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/tests/test_camelot_native_table.py`
- `docs/adr/0018-camelot-native-table-relationship-proof.md`
- `docs/camelot-table-dependency.md`

## Contratos verificados

`camelot-py==2.0.0`, parser lattice, engine combined. MIT y dependencias relevantes permisivas documentadas en docs/camelot-table-dependency.md; conservar notices transitivos al redistribuir. No otro extractor añadido; PyMuPDF es dependencia existente. Pip check: no broken requirements.

Camino normal: structured_evidence_grounding._reconstruct_for_materialization → reconstruct_camelot_tables → CamelotTableRelationshipAdapter → propuesta física → prueba Native → StructuredEvidenceBlock → manifests/Scope/Quantity/Attribute existentes. Sin activación por Tender, filename, página conocida o benchmark.

Camelot sólo propone estructura y usa raw_text como comparación/debug. Native aporta literales/offsets/identidad canónica; pertenencia única, topología y acuerdo literal son obligatorios. Ambigüedad abstiene; generación/hash/página/config/prueba corrupta rechazan. Replay y manifests verifican hashes. V4a y padres de hijos se conservan, sin elevar trust automáticamente.

Proof policy `camelot-native-table-proof-v1`, formato `CAMELOT_NATIVE_TABLE_001`. DI_SELECTIVE_FREEZE_003 mantiene su esquema y añade configuración/hash, parser/engine, dependencies y proof policy en implementation_versions. Ningún freeze creado.

ADR0018 actualizado a accepted. B1 conserva 0Attributes: fabricante/modelo embebidos en descripción no se interpretan como atributos. No expansión semántica, model regex ni tuning.

## Regresión post-commit

- 570 passed, 7 warnings in 92.46s (0:01:32)
- 1153 passed, 1 deselected, 8 warnings in 125.89s (0:02:05)
- 2109 passed, 1 deselected, 8 warnings in 194.23s (0:03:14)

CT32/RT22 incluidos en las tres suites. SI/MG, ST, SC/DC, V6c PS, Scope adapters/materializers, human review/API, bootstrap/freeze/harness y OCR/Vision incluidos en focused. Compileall y git diff --check PASS. Opt-in real local_ollama excluido; warnings heredados conservados en logs. No inferencia OCR/Vision/LLM real ejecutada.

Alembic current/head `20261013_req_perception_prov_072`, drift59, firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`. Verificado sólo lectura en licitia_test. Sin migración ni reset validation DB.

Árbol rastreado limpio; staging vacío; reportes/runtime/benchmark históricos siguen untracked. Sin push. Integridad:4560 archivos históricos intactos y9 archivos de producción coinciden con sello previo a B1. Provider/perfiles/budgets, V6c, Requirements/Evidence sin cambios respecto al parent. Cambios limitados a los12 archivos arriba.

## Readiness

HEAD comprometido y limpio elegible para DI_BLIND_SELECTIVE_001 / DI_SELECTIVE_FREEZE_003 / blind-task-contracts-v1 / perception-sufficiency-v2 con Camelot2.0.0 lattice/combined y proof canónico. Readiness técnica; no certificación semántica ni verificación de disponibilidad operacional actual de proveedores. Attempt9 requiere su preflight al ejecutarse por instrucción posterior.

No Attempt9, run_id, freeze, reset de validation DB, inspección/tuning adicional de Tender002 ni nuevo slice. No rerun B1. Ningún desarrollo posterior preautorizado. Limitaciones heredadas del spike: digital Native, topología rectangular no ambigua, abstención rotation/crop especial, sin hard cap OS RAM; atributos embebidos pendientes de evaluación posterior.

LICITIA CAMELOT NATIVE TABLE INTEGRATION COMMITTED — BLIND ATTEMPT #9 READY
