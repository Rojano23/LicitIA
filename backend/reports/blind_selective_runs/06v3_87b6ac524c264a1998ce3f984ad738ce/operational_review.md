# Blind Attempt #3 — FAILED / preservado

Run: `06v3_87b6ac524c264a1998ce3f984ad738ce`. HEAD: `75111c047766dc32e480589075df0a029815f394`.

## Preflight y freeze

HEAD exacto; tracked worktree limpio; índice vacío. Los 107 históricos verificaron intactos antes del reset y tras el bloqueo. Alembic current/head072; drift59 (55 add_index, 4 remove_index), firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`, confirmado antes y después del reset.

Tesseract `/opt/homebrew/bin/tesseract` 5.5.3, effective tessdata `/opt/homebrew/share/tessdata/`, packs spa/eng disponibles. Ollama GET /api/version=0.23.3 y GET /api/tags confirma qwen3-vl:4b-instruct / digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`; blobs presentes. Sólo probes no inferenciales.

El usuario autorizó mover el reset antes del pre-freeze, porque el harness exige DB vacía. Se preservó export previo en `/private/tmp/06v3_87b6ac524c264a1998ce3f984ad738ce_attempt2_database.dump`, SHA `5760deb5049d0a58bdae1d8f67dabaa5889e6254ccb292dfb75d66ccb61f90e1`. Reset únicamente de licitia_validation_06v; Alembic upgrade head, baseline sin reparar. Pre-freeze creado/verificado antes de corpus; DB0/0.

Perfil SHA: `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`.
Pre-freeze `pre_execution.json`: `89b02a39d958d9b3b8bc5619db8a2f1386f6479f5a5ed569baec3439a763a024`.
Input binding `input_binding.json`: `25c3afe412584d450b38d87039bb6c9a052fd301cad11289bc8d6bd4ff77f2c4`.
Estos hashes son de archivos completos; los envelopes conservan adicionalmente SHA del payload canónico.

## Importación e incidente operacional

Fuente exacta autorizada: `/Users/ceciliavalencia/Documents/LicitIA/Reelevadores Elecricos`. API canónica POST /tenders y POST /tenders/{id}/documents/import vía TestClient. Tender `347c0581-3d2b-4bdb-9fb1-42a50103f2df`. Source11, IMPORTED11, documentos11, duplicados/rechazos/errores de importación0. Inventario fuente pre/post idéntico; binding contiene nombres exactos, MIME, tamaño, SHA y generaciones iniciales vacías. Pre-freeze no cambió.

Error de orquestación del operador: el script temporal importó módulos que inicializaron settings antes de establecer LICITIA_DATA_DIR. La primera invocación abortó por guard de DB antes de corpus; al lanzar después con DATABASE_URL explícita, la DB fue correctamente validation_06v, pero el filesystem de importación resultó `backend/.licitia-data`, con11 originales nuevos del Tender. El binding se verificó en ese mismo proceso. El proceso de ejecución recibió el filesystem aislado congelado y el guard `_verified_path` falló con FileNotFoundError, ANTES de EXECUTION_STARTED y ANTES de Native/proveedores.

Clasificación: OPERATOR_PROCESS_ENVIRONMENT_MISMATCH / FAILED_BEFORE_EXECUTION_STARTED. No es evidencia de defecto del código del harness ni de calidad semántica del modelo. Se preservan los archivos nuevos sin mover/eliminar; no se cambió código/configuración congelada ni se repitió ejecución. No hay first_pass.json, first-pass SHA, EXECUTION_STARTED ni FROZEN. `operational_failure.json`, `execution_failure.log`, `post_stop_identity.json` conservan el bloqueo.

## Métricas operacionales y comparación

| Métrica | Attempt #2 (baseline humano) | Attempt #3 |
|---|---:|---:|
| Tenders/documentos | 1/11 | 1/11 |
| Preparados/unsupported | 10/1 | NO EJECUTADO |
| Páginas Native | 253 | 0 registros; preparación no ejecutada |
| OCR/Vision inferencias | 0/0 | 0/0 |
| Requirements/candidates | 31/43 | NO MEDIDO |
| Requested Evidence | 8 | NO MEDIDO |
| Scope/Attributes/Quantities | 0/0/0 | NO MEDIDO |
| Structure trusted/review/unavailable | 2/249/2 | NO MEDIDO |
| Review/conflicts/stale carry | 288/1/0 | NO MEDIDO |

No comparar ausencia de resultados con calidad semántica. No hubo planning, OCR-needed/eligible, Vision-needed/eligible, materialización ni métricas de dominio/provenance. Executed/reused/completed/failed tasks=0 para ambos motores; exhausted/deferred/avoided y distribución de capacidades NO MEDIDOS. Adquisiciones OCR0/8, páginas OCR0/8; llamadas/tareas/páginas Vision0/4. Sin retries ni consumo de budgets. No hubo llamadas no planificadas. Las comprobaciones de no borrado de evidencia inferior, suficiencia, separación structure/detail y unsupported no son evaluables por este intento no ejecutado; no se presentan como validación real. Sin páginas/provenance/confianza generadas.

## Validación posterior

Regresión sintética focal+DI: **209 passed, 7 warnings**, log `/private/tmp/attempt3_focused.log`.

Comando desde backend, intérprete `/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python`:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_blind_freeze_evidence.py tests/test_blind_selective_harness.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py -q -m 'not local_ollama'
```

Suite completa: 1949 passed, 1 deselected, 8 warnings in 117.86s (0:01:57). Comando `python obligatorio -m pytest -q -m 'not local_ollama'` desde backend; log `/private/tmp/attempt3_full.log`. Sólo licitia_test; no rerun del corpus.

Compileall app/scripts/tests PASS. Git diff --check PASS. Tracked source/protocolo/tests sin cambios; índice vacío. No stage/commit/push. Los107 históricos siguen intactos; Attempt1/2 sin modificaciones. No adjudicación semántica realizada.

Siguiente acción: revisión arquitectónica del incidente y autorización de recuperación. No ejecutar nuevamente esta identidad ni limpiar datos automáticamente.
