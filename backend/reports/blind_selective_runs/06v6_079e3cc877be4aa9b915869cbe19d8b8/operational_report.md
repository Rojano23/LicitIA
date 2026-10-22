# MVP-06.V — Blind Attempt #6: detenido antes de ejecución

## Resultado

FAILED / OPERATOR_IMPORT_INVENTORY_OMISSION, fase FINAL_PRE_START_GATE.
El operador excluyó archivos ocultos al enumerar fuentes; omitió `.DS_Store`,
original del baseline (6148 bytes). No es un defecto ni resultado semántico de LicitIA.
El input binding ya estaba creado: no se modifica, repara ni reutiliza.
No se creó EXECUTION_STARTED y no hubo adquisición/inferencia.

## Identidades

- Run: `06v6_079e3cc877be4aa9b915869cbe19d8b8`.
- HEAD inicial/final: `429bf2ff95043c6d74af379a22d85bdd85843340`.
- Root aislado: `/Users/ceciliavalencia/LiticIA/backend/.licitia-data-validation-06v6_079e3cc877be4aa9b915869cbe19d8b8`.
- Perfil SHA-256: `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`.
- Pre-freeze: `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v6_079e3cc877be4aa9b915869cbe19d8b8/pre_execution.json`.
- Pre-freeze SHA-256: `a827ef282726ab28f0d33370b78c171ea7ee466b548205205ce000b9cfcfcb30`.
- Input binding: `/Users/ceciliavalencia/LiticIA/backend/reports/blind_selective_runs/06v6_079e3cc877be4aa9b915869cbe19d8b8/input_binding.json`.
- Input-binding SHA-256: `2fb79c7d24595089e28245a0faf4ef3f909702cca9e55ab1bc0b708e28e9e0e8`.
- Tender: `f2ccf71a-9fb1-42a7-94fa-391afe75cb57`.
- EXECUTION_STARTED / first_pass / FROZEN: NO CREADOS.

## Preflight y reset

Preflight PASS: HEAD exacto, tracked limpio, staging vacío, code identity aceptada.
Ollama consultado sólo con GET /api/version y /api/tags: versión0.23.3,
qwen3-vl:4b-instruct y digest ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b.
No se inició ni modificó Ollama. Tesseract5.5.3, tessdata esperado y spa+eng.
Perfil/budgets/modelos sin cambios. Bootstrap fresco antes de Settings en cada proceso.
Reset autorizado sólo licitia_validation_06v después de export. Export anterior preservado
en bootstrap/pre_reset_database.dump; SHA9a87a58273602ecb82defc7081170020a2f49018f3a57bcb47ddeaa6840f3d38.
Post-reset cero tenders/documentos verificado. Alembic current/head072, drift59
(55add_index/4remove_index), firma3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7.
Pre-freeze003 creado y verificado sin mutarlo. Perception policy perception-sufficiency-v2.

## Importación y métricas

API canónica: 1 Tender, 10 fuentes enumeradas/importadas, 10 documentos.
Originales importados verificados por hash/tamaño y físicamente dentro del root.
Comparación de inventario de identidad con Attempt4:11 originales; omitido `.DS_Store`.
Prepared/unsupported/failures/Native pages: NOT_MEASURED (preparación no ejecutada).
Perception sufficiency, interpretación unresolved, OCR/Vision needed/avoided/deferred:
NOT_MEASURED (planning no ejecutado). OCR acquisitions0/8; Vision calls0/4, tasks0/4,
pages0/4. No retry consumido.
IR blocks/candidates/grounding, Attributes/Quantities provisionales/persistidas,
multispan manifests/verificación, Requirements/candidates/Requested Evidence,
structure/review/conflicts/stale/effects/provenance: NOT_MEASURED, no pipeline ejecutado.
No derivar ceros de calidad ni comparación semántica de un pase inexistente.
Comparación operacional #4/#2: ambos11documentos; Attempt6 importó10 y se detuvo.
No primer pase válido comparable.

## Seguridad y cierre

No ejecución de proveedores, no pipeline, no semántica manual ni adjudicación.
No reparación de binding, cambio de configuración, rerun ni nuevo intento.
No source edits, stage, commit ni push. Tracked limpio; staging vacío;
git diff --stat vacío; git diff --check PASS.
Históricos Attempts1–5 y sus roots: 1627/1627 archivos SHA256 sin diferencias.
No acceso semántico al corpus; sólo copia/importación y metadata/hash autorizados.
Regresión post-run y compileall: NOT_RUN, no existe first-pass congelado; sin cambios source.
Pre-freeze, binding, originales y export/artefactos parciales quedan preservados.

MVP-06.V BLIND ATTEMPT #6 FAILED — PRESERVED FOR ARCHITECT REVIEW
