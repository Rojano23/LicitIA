# MVP-06.V.4c1 — Selective OCR recovery

Implementación lista para revisión arquitectónica, sin stage/commit/push.

## Estado e impacto

HEAD inicial y actual: `f1fccc76111b4d4ab28958fe5412724a264ea7e7`.
Causa confirmada: la suficiencia previa por página no representaba necesidades por tarea; el OCR podía reemplazar resultados y no existían adaptadores OCR predeterminados para Scope/Attributes/Quantities.

El nuevo servicio opt-in usa `plan_document_ocr_tasks` y `execute_planned_ocr`. No activa OCR automáticamente en el runtime ciego ni altera AUTO/endpoints históricos. Native suficiente evita OCR y Vision. Native insuficiente puede producir OCR_NEEDED cuando hay imagen demostrable; AVAILABLE_ONLY difiere sin render/proveedor. Texto no normalizado, falta de contrato o evidencia insuficiente permanece UNKNOWN/revisión. Necesidad visual explícita permanece VISUAL_CAPABILITY_PENDING.

TEXT usa fragmentos exigidos por el caller; STRUCTURE usa el parser canónico; Scope/Attributes/Quantities usan gramática explícita existente, identidad y unidades canónicas. No se declara toda una página resuelta porque una tarea tenga evidencia. Una identidad ambigua no se convierte artificialmente en brecha OCR. Requirements/Requested Evidence consumen OCR mediante sus contratos existentes sin modificar sus extractores.

## Persistencia, provenance y seguridad

Motor/version explícitos; render de página/región acotado; subprocess local con timeout y bloqueo de red en worker. Los recibos derivados vinculan original/hash, documento/revisión, página/región, motor/configuración/render, fingerprint y PageOcrResult. Hay lock por slot y un intento adquirido. Repetición equivalente reutiliza; incompatibilidad o corrupción difiere. Los resultados completos y legados no se sobrescriben. Native y sus chunks se preservan normalizando sólo el nuevo OCR.

Los adaptadores mantienen OCR como OCR: resultado, normalized content/hash, raw hash, locator/span, revisión, motor y fingerprint cuando existe recibo válido. No fabrican fingerprints para OCR legado. Scope/Attributes/Quantities conservan revisión; V.4a sigue autoritativo. `scope-logical-v2` permanece sin cambio: grounding comparable deduplica Native+OCR y conserva contribuyentes; identidades distintas y paráfrasis no probadas no se fusionan. Contradicciones terminan en revisión.

Errores, timeout, ausencia de texto, salida inválida y motor no disponible son explícitos. No fabrican transcript ni confianza. Fallos persistidos agotan el intento; fallos de render/pre-adquisición no crean una generación. Métricas distinguen elegibilidad, ejecución, ejecución desconocida, completado, fallo, indisponible, evitado y pendiente visual. Completado describe percepción, no cumplimiento ni cobertura semántica.

## Validación reproducible

Intérprete obligatorio: `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`; cwd `backend`; pytest contra `licitia_test`.

- Nuevos tests: 44 casos parametrizados de `tests/test_selective_ocr_recovery.py`, incluidos en las regresiones siguientes.
- Targeted: `python -m pytest tests/test_selective_ocr_recovery.py tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_document_intelligence_integration.py tests/test_scope_attribute_materializer.py tests/test_scope_quantity_materializer.py -q -m 'not local_ollama'`: 177 passed, 6 warnings.
- OCR histórico: `python -m pytest tests/test_documents.py -q -k 'ocr or normalization' -m 'not local_ollama'`: 10 passed, 115 deselected, 7 warnings.
- Regresión ampliada DI/MVP-06.V/materializers/SC/DC/ST: 763 passed, 6 warnings. Incluye Native structured coverage, structural trust safety/propagation, familias scope details/attributes/quantities, DI integration/compatibility/audit/calibration/fidelity/golden/rescore/preflight, preparation recovery, page/document structure, scope review y alternative compliance.
- Suite completa: `python -m pytest -q -m 'not local_ollama'`: **1843 passed, 1 deselected, 7 warnings**. Advertencias existentes: python_multipart, SWIG/PyMuPDF y ccache/Paddle.
- `python -m compileall -q app scripts tests`: PASS.
- `git diff --check`: PASS.

OC01–OC06, OP01–OP03/OP05 y OI01–OI05 cubiertos por pruebas nuevas; invalidación de revisión OP04 conserva las regresiones canónicas, sin una ruta nueva de regeneración incompatible. VP10–15,17–30 cubiertos en su superficie OCR y regresiones V.4a/V.4b. VP31 conserva AUTO; VP32 distingue ausencia de imagen demostrable sin confiar en char_count; VP33 evita OCR decorativo mediante suficiencia por tarea; VP34 conserva resultado previo; VP35 ejecuta sólo región/página elegida con idempotencia independiente; VP37 rechaza configuración/hash incompatible. VP38 bloquea red en el worker y reporta indisponibilidad; no se certificó un motor real. VP16 y la semántica Vision de VP36 quedan diferidos a V.4c2. No se atribuye calidad OCR real a motores simulados: VP12 prueba recuperación/consumo con transcripción inyectada y PDF sintético.

## Esquema e integridad

Alembic current/head en licitia_test: `20261013_req_perception_prov_072`. Sin modelos, esquema ni migración nuevos. Probe read-only: las **59 diferencias preexistentes** coinciden exactamente con baseline aceptado (55 add_index, 4 remove_index); cero drift adicional. Signature SHA-256: `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`. Hash de esquema antes/después idéntico.

107 archivos históricos verificados sin cambios: Attempt #1, freeze/first-pass/adjudicación de Attempt #2 incluidos. Reporte arquitectónico V.4c intacto: SHA-256 `83fe42ccf9e2ec2e602c28d4ff8eee1df93407b2d6f63e568884a30a748d27fa`. Sin replay, nuevo blind run_id ni Attempt #3. No se inspeccionó Tender #002 ni se incorporó lógica por documento/producto/página/cantidad.

## Archivos de este slice

Modificados: content_normalization.py, document_intelligence_sources.py, scope_detail_adapters.py, scope_detail_materializer.py, scope_attribute_adapters.py, scope_attribute_materializer.py, scope_quantity_adapters.py y scope_quantity_materializer.py (todos bajo backend/app).

Nuevos: backend/app/document_perception_planner.py, backend/app/selective_ocr_executor.py, backend/app/ocr_scope_evidence.py, backend/app/ocr_scope_adapters.py, backend/tests/test_selective_ocr_recovery.py, docs/adr/0012-task-aware-selective-ocr.md y este reporte.

El working tree contiene estos cambios sin staging y los reportes históricos no rastreados preexistentes, que no se agregaron ni alteraron. `git status --short` y `git diff --stat` inspeccionados al cierre. HEAD permanece congelado; no stage/commit/push.

## Límites y diferidos

Sin blockers de implementación. La integración es explícita/opt-in. Los endpoints OCR históricos mantienen sus garantías previas; no hay sistema general de generaciones. Cambiar configuración o regenerar evidencia incompatible requiere una decisión posterior y permanece DEFERRED. Un rollback DB con recibo ya escrito falla cerrado por inconsistencia. Gramática estrecha no equivale a recall semántico certificado.

Vision por tarea, presupuestos, retry y parsing visual pertenecen a V.4c2. No se ejecutaron OCR real, Vision, Ollama/Qwen ni proveedores reales. No hubo tuning de Tender #002 ni Attempt #3.
