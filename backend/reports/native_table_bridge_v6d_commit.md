# V.6d — cierre de commit aceptado

Commit/HEAD: `0b04fc7677e670fb487683ac904d3c3a89daa373`.
Subject: `feat(document-intelligence): bridge native ruled tables to structured evidence`.
ADR 0017 aceptado y committed. Reporte runtime `native_table_bridge_v6d.md` permanece untracked.

Archivos exactos:

```
backend/app/blind_selective_freeze.py
backend/app/native_table_relationships.py
backend/app/structured_evidence.py
backend/app/structured_evidence_grounding.py
backend/tests/test_native_table_bridge.py
docs/adr/0017-native-ruled-table-relationship-proof.md
```

Diff revisado completo: sólo puente, IR/grounding, registro de versión, pruebas reales PDF y ADR. Sin cambios al planner, perfiles, proveedores/modelos, budgets, Requirements/Evidence ni esquema/migraciones. Los seis módulos de perfil/harness/planner/OCR/Vision/Ollama se compararon byte a byte contra el HEAD previo y son idénticos.

RT precommit: 22 passed, 6 warnings, 6.39 s. Reconfirmados JUnit aceptados: SI39/MG15/ST44/SC-DC46/PS36, Scope159, human review/API87, DI228; ampliada1119 y completa2075 passed/1 deselected/8 warnings. La completa tenía20RT; RT final22 se comprobó después. Compileall y diffcheck PASS. No se repitieron suites amplias: producción idéntica a la evidencia aceptada. Sin llamadas a proveedores reales en este cierre.

Alembic current/head072 (`20261013_req_perception_prov_072`), drift59 (55add_index/4remove_index), firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`, reconfirmados antes y después del commit en licitia_test, read-only.

RT01_real_pdf_end_to_end comienza con `pdf_table()`, invoca import/extract-pages/normalize productivos, materializa Scope y valida IR por resolve_payload; persiste 2Scope+2Quantities+4Attributes con padres correctos. RT02/04/05/11/12/13 prueban continuidad, ownership, geometría real, páginas, variaciones, literalidad y manifests inmutables. Tablas regladas soportadas únicamente; sin geometría fabricada, texto plano insuficiente, ambigüedad abstiene/error/review y ninguna autoridad contractual automática.

Git: tracked clean, staging vacío, reportes históricos untracked preservados. 3056 archivos históricos con SHA idéntico. Sin push.

Readiness read-only: code_identity exige y confirma HEAD committed limpio; compatible con DI_BLIND_SELECTIVE_001, DI_SELECTIVE_FREEZE_003, blind-task-contracts-v1 y perception-sufficiency-v2. El harness llama materialize_canonical → materialize_document_scope_details → adaptador Native normal → structured_evidence_grounding → reconstruct_native_tables. Sin flag/configuración/activación especial; conserva condiciones y abstenciones productivas normales. Se conserva el proveedor/modelo/budget previo, sin comprobar disponibilidad operacional de servicios ni ejecutar preflight de proveedor.

No se creó Attempt8, run_id, freeze, binding ni root; no reset/import ni inspección de Tender002. Sin nuevo slice V6e. Listo para autorización separada del Attempt8 desde este HEAD; no certifica calidad semántica/UAT.

MVP-06.V.6d NATIVE TABLE BRIDGE COMMITTED — BLIND ATTEMPT #8 READY
