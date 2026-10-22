# MVP-06.V.4b — Native Structured Coverage

## Estado y límites

HEAD inicial y actual: `cb27af54292ead1b5562f4d0a3de2637948d8d25`.
Implementación para revisión arquitectónica, sin stage/commit/push. No ejecución
ciega, no nuevo run_id, no acceso al corpus Tender #002 ni tuning contra él.
Reporte de arquitectura previo conservado sin cambios y sin rastrear.

## Causa raíz confirmada

Native ya se enumeraba desde NormalizedContent y llegaba al materializador. El
adaptador Scope por defecto admitía únicamente Vision DETAIL_TRANSCRIPTION.
Attributes y Quantities también tenían adaptadores predeterminados exclusivos de
Vision. Cero padres propagaba cero hijos, pero recuperar padres no bastaba para
cubrir las dos brechas independientes de hijos.

## Scope Native

NativeScopeDetailAdapter consume exclusivamente texto canónico persistido. Gramática
acotada: bloque iniciado por ITEM/PARTIDA/CONCEPTO/NO, cuyo cuerpo comienza con una
acción explícita de suministro/suministrar, servicio/prestación o entrega/entregar.
El próximo encabezado delimita otro bloque. Preguntas y referencias con puntos guía
no se convierten en alcance. No se reconstruyen tablas por posición visual ni se
interpreta prosa administrativa como obligación por contener una palabra de suministro.

Produce candidatos typed del contrato existente, sin percepción sintética. La
identidad ITEM sólo se conserva con estructura actual resuelta y segmentos válidos;
lo demás permanece UNRESOLVED/review. Las guardas comunes de V.4a, identificadores,
continuidad, grounding, lineage y transcripción siguen aplicándose.

## Attributes Native

NativeScopeAttributeAdapter exige padre con identidad ITEM válida y fragmento
verificado. Sólo extrae bindings explícitos Marca/Brand y Modelo/Model con colon y
separadores pipe/punto y coma/salto de línea. Conserva fragmento, valor literal,
provenance y revisión del padre. Sin owner no materializa atributos. No trata prosa
libre como atributo ni amplía el vocabulario por ejemplos del corpus.

## Quantities Native

NativeScopeQuantityAdapter exige el mismo padre y fuente verificable. Lee pares
Cantidad/Quantity y Unidad/Unit explícitos. Usa Decimal, EXACT y el mapeo canónico
de unidad→measure_kind; no duplica ese vocabulario. No adivina unidades ni separadores
locales, no aplana rangos y no interpreta fechas/dinero/números contextuales.
Campos ambiguos o unidad no soportada no producen una cantidad confiada.

## Provenance y confianza

Locator versionado: página, normalized UUID, SHA-256, span de caracteres y revisión
documental. Padre/hijos conservan identidad Tender/documento/página y source_method
NATIVE, native-page:<id> y versión de contrato de fuente/parser. Los hijos validan
la generación exacta, identidad, revisión, hash y excerpt del span. No sustituyen
esa fuente por DocumentPage.text. Generación ausente, hash alterado o página ajena
produce INVALID_EVIDENCE con diagnóstico explícito.

No se crean analysis/page-result ni provenance Vision para Native. No se inventan
bbox, jobs de extracción o confidence. El nuevo camino Native siempre propone en
review, confidence null. Los hijos heredan review. UNKNOWN no gana ownership ni
continuidad por parsear texto. No cambia la autoridad humana ni introduce bloqueos
comerciales. OCR/Vision siguen siendo capacidades separadas.

## Identidad, deduplicación y política

Nueva política explícita `scope-logical-v2`. El materializador primero extrae y
aplica guardas; después reconcilia candidatos antes del reemplazo por artefacto.
La identidad lógica usa documento/página, owner anclado, dominio/tipo, excerpt
exacto con whitespace colapsado y ocurrencia. No incluye método/UUID de percepción.
No normaliza números, unidades o identificadores para afirmar equivalencia.

El fingerprint semántico versionado añade descripción, aplicabilidad, ownership y
campos explícitos; así los cambios materiales invalidan derivaciones. No reutiliza
fingerprints de política anterior. Claims transitorios de atributos permiten revisar
desacuerdos de valores entre capacidades sin agregar campos al modelo persistido.

Para grounding comparable, Native+Vision convergen en un padre. Revisión precede a
la retención de representación previa y al desempate estable por artefacto; ninguna
capacidad gana confianza por votar dos veces. Conflicto de owner/cantidad/unidad o
atributos deja UNRESOLVED/review. Diferencias explícitas entre ítems, cantidades,
atributos, páginas/documentos u obligaciones distintas no se fusionan por parecido.

`logical_evidence` devuelve fingerprint, claves de fuentes contribuyentes y conflicto.
Se combina con source_method de artifact_results para conocer capacidades. Todas
las percepciones originales se conservan; no hay tabla nueva multi-evidence. La
relación es regenerable desde las fuentes, no se presenta como persistencia nueva.

Límite deliberado: no certifica equivalencia semántica de paráfrasis ni alineamiento
visual cuando no existe grounding comparable. No usa semejanza de descripción,
orden de carga o número de partida aislado para inferir identidad contractual.

## Idempotencia y revisión humana

El replay del materializador conserva UUID del padre e hijos existentes sólo si
fingerprint, generación/locator, contrato, provenance, segmento y estado de revisión
permanecen iguales. El reemplazo explícito sigue siendo regeneración: crea nueva
identidad persistida y vuelve obsoleta la revisión anterior. No arrastra decisiones
humanas ni evaluaciones de cumplimiento automáticamente. Este contrato se comprobó
con Scope Review y Alternative Compliance, además de SC12/DC04/DC06.

Vision conserva su adaptador, extracción y provenance. Añadir Native no lo reemplaza.
Los semantic_providers explícitos mantienen su ruta opt-in por delante del fallback
Native. Sin proveedor configurado no se ejecuta ninguno. Errores de extracción o
persistencia se exponen como INVALID_EVIDENCE y no como ausencia contractual.

## Matriz de contratos

SC01–SC24 y DC01–DC06 implementados en test_native_structured_coverage.py. Incluye
páginas/ítems múltiples, obligaciones distintas del mismo owner, repetición, hijos,
provenance, normalizado distinto a page.text, generación alterada/ausente/ajena,
Native+Vision, conflictos de cantidad y atributo, FAILED/DESELECTED, errores de
adaptador/persistencia, unidades/decimales/rangos ambiguos y review propagado.
Negativos: contenido/índice, cuestionario, referencias a páginas, lista numérica,
fecha, dinero, sección, versión, narrativa numérica, referencia administrativa al
suministro y negación de la acción. Fixtures sintéticos; no corpus ciego.

## Validación final

- SC01–SC24/DC01–DC06 + ST10–ST20: **70 passed, 6 warnings in 5.49s**. Log: `/private/tmp/v4b_matrix_final.log`.
- Regresión ampliada DI/MVP-06.V/materializadores/Human Review: **719 passed, 6 warnings in 66.06s (0:01:06)**. Log: `/private/tmp/v4b_regression_final.log`.
- Suite completa: **1799 passed, 1 deselected, 7 warnings in 110.27s (0:01:50)**. Log: `/private/tmp/v4b_suite_final.log`.
- Matriz: 46 casos Native/negativos y 24 casos V.4a, todos PASS.
- Exclusión intencional: `local_ollama` (un test opt-in real en suite completa).
- Warnings conocidos: Swig/PyMuPDF, python_multipart y serialización Pydantic; sin fallos finales.
- compileall: PASS; git diff --check: PASS. No se ejecutó validación con modelos reales.

## Comandos reproducibles

CWD de pytest/Alembic: /Users/ceciliavalencia/LiticIA/backend.
Conftest fija exclusivamente licitia_test y .licitia-data-test.

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_native_structured_coverage.py tests/test_structural_trust_safety.py tests/test_structural_trust_propagation.py tests/test_scope_details.py tests/test_scope_detail_adapters.py tests/test_scope_detail_materializer.py tests/test_scope_attributes.py tests/test_scope_attribute_adapters.py tests/test_scope_attribute_materializer.py tests/test_scope_attribute_integration.py tests/test_scope_quantities.py tests/test_scope_quantity_adapters.py tests/test_scope_quantity_materializer.py tests/test_scope_quantity_integration.py tests/test_document_intelligence.py tests/test_document_intelligence_integration.py tests/test_document_intelligence_compatibility.py tests/test_document_intelligence_audit.py tests/test_document_intelligence_calibration.py tests/test_document_intelligence_calibration_fidelity.py tests/test_document_intelligence_structural_golden.py tests/test_document_intelligence_structural_rescore.py tests/test_document_intelligence_06v_preflight.py tests/test_document_preparation_recovery.py tests/test_page_structure.py tests/test_page_structure_resolver.py tests/test_document_structure_orchestrator.py tests/test_scope_review.py tests/test_scope_review_api.py tests/test_alternative_compliance.py tests/test_alternative_compliance_api.py -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest -q -m 'not local_ollama'
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m compileall -q /Users/ceciliavalencia/LiticIA/backend/app /Users/ceciliavalencia/LiticIA/backend/scripts /Users/ceciliavalencia/LiticIA/backend/tests
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic current
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic heads
DATABASE_URL=postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m alembic check
git diff --check
git diff --stat
git status --short
```

## Esquema y gate pendiente

Alembic licitia_test current/head: `20261013_req_perception_prov_072`.
Ningún modelo o migración cambió; 40 archivos de models/Alembic comparados byte a
byte con HEAD, sin diferencias. La ruta acotada no requiere esquema, enum persistido
ni migración nuevos; no se creó ni propuso migración para esta implementación.

Sin embargo, `alembic check` devolvió 255 y detectó 59 diferencias de índices entre
ORM y DB; no reportó otro tipo de diferencia. Son preexistentes a este slice: la
metadata/esquema declarados por el código de HEAD son idénticos. Evidencia completa:
`/private/tmp/v4b_alembic_check.log`. No se corrigieron ni limpiaron índices fuera
de alcance. No puede afirmarse el requisito global «no schema drift»; requiere
revisión arquitectónica separada. No es una necesidad de esquema introducida por
Native structured coverage.

## Integridad y restricciones

107 archivos del set histórico verificados por lectura SHA-256: todos intactos.
Attempt #1, Attempt #2 freeze, first-pass y adjudicación conservan sus hashes.
El reporte de arquitectura también conserva su hash original. Sin regeneración
ni reescritura de resultados históricos.

No proveedores reales, OCR/Tesseract, Vision, Ollama o Qwen ejecutados por este
slice. La validación usa mocks/fixtures o replay no ciego existente; no certifica
calidad de modelos reales. Attempt #3 no creado, sin nuevo run_id. Sin cambios en
Requirements/Requested Evidence, modelos, migraciones, configuración productiva ni
intentos históricos. Sin reglas ligadas a nombres, modelos, páginas o cantidades de
Tender #002. No stage, commit ni push.

## Archivos de la entrega

Modificados:
- backend/app/scope_attribute_adapters.py
- backend/app/scope_attribute_materializer.py
- backend/app/scope_detail_adapters.py
- backend/app/scope_detail_materializer.py
- backend/app/scope_details.py
- backend/app/scope_quantity_adapters.py
- backend/app/scope_quantity_materializer.py
- backend/app/vision_scope_detail_adapter.py
- backend/tests/test_document_intelligence_integration.py

Nuevos, sin stage:
- backend/app/native_scope_evidence.py
- backend/app/native_scope_detail_adapter.py
- backend/app/native_scope_attribute_adapter.py
- backend/app/native_scope_quantity_adapter.py
- backend/app/scope_logical_identity.py
- backend/tests/test_native_structured_coverage.py
- docs/adr/0011-native-structured-coverage.md
- backend/reports/native_structured_coverage_v4b.md (runtime, intencionalmente untracked)

El test de integración Native+OCR que antes exigía dos padres para el mismo
fragmento ahora exige uno y comprueba ambos contribuyentes. No se relajó su guarda
contra la eliminación de Native cuando OCR falla. No se modificaron tests de
Human Review para aceptar arrastre de decisiones.

## Git al cierre

Staging vacío; HEAD sin cambios. `git diff --stat` sólo contiene los nueve
archivos rastreados de la entrega; los archivos nuevos se enumeran arriba.

```text
 M backend/app/scope_attribute_adapters.py
 M backend/app/scope_attribute_materializer.py
 M backend/app/scope_detail_adapters.py
 M backend/app/scope_detail_materializer.py
 M backend/app/scope_details.py
 M backend/app/scope_quantity_adapters.py
 M backend/app/scope_quantity_materializer.py
 M backend/app/vision_scope_detail_adapter.py
 M backend/tests/test_document_intelligence_integration.py
?? MVP-06.3.4c-FINAL-SAFETY-REPORT.md
?? MVP-06.3.4c-HUMAN-LABELS-FINAL-REPORT.md
?? MVP-06.3.4c-PENDING-IDENTITY-FIX-REPORT.md
?? backend/GOLDEN_FINAL_REVIEW.txt
?? backend/MVP-06.3.4c-DIAGNOSTIC-OUTPUT-REPORT.txt
?? backend/MVP-06.3.4c-PHASE-4-FINAL-REPORT.txt
?? backend/MVP-06.3.4c-RUNNER-HOTFIX-REPORT.txt
?? backend/MVP-06.3.4c-TECHNICAL-CLOSURE-FINAL.txt
?? backend/MVP-06.4.4b-QWEN8B-BASELINE-002.txt
?? backend/MVP-06.4.4b-QWEN8B-BASELINE-003.txt
?? backend/PARENT_RECOVERY_AUDIT.txt
?? backend/SCOPE-SEMANTIC-CONTRACT-004-IMPLEMENTATION.txt
?? backend/app/native_scope_attribute_adapter.py
?? backend/app/native_scope_detail_adapter.py
?? backend/app/native_scope_evidence.py
?? backend/app/native_scope_quantity_adapter.py
?? backend/app/scope_logical_identity.py
?? backend/reports/b4_structural_golden_candidate_v1.json
?? backend/reports/b4_structural_golden_review_packet.md
?? backend/reports/b4_structural_golden_review_pages/
?? backend/reports/blind_attempts/
?? backend/reports/blind_first_passes/
?? backend/reports/blind_runs/
?? backend/reports/di_r4a_available_structure.json
?? backend/reports/di_r4a_b4_structure_phase4_rescore.json
?? backend/reports/di_r4a_b4_structure_rescore.json
?? backend/reports/di_r4a_batch1_reanalysis.json
?? backend/reports/di_r4a_existing_vision_transcription.json
?? backend/reports/di_r4a_inventory.json
?? backend/reports/di_r4a_native_structure.json
?? backend/reports/di_r4a_native_transcription.json
?? backend/reports/di_r4a_ocr_structure.json
?? backend/reports/di_r4a_ocr_transcription.json
?? backend/reports/di_r4a_tesseract_b4_p4_transcription.json
?? backend/reports/di_r4a_vision_b4_p1_p3_structure.json
?? backend/reports/di_r4a_vision_b4_p4_transcription.json
?? backend/reports/document_intelligence_06v0_preflight.json
?? backend/reports/document_intelligence_06v0_preflight.md
?? backend/reports/document_intelligence_06v_execution_log.json
?? backend/reports/document_intelligence_06v_execution_phases.json
?? backend/reports/document_intelligence_06v_first_pass.md
?? backend/reports/document_intelligence_06v_import_blocker.json
?? backend/reports/document_intelligence_06v_import_blocker.md
?? backend/reports/document_intelligence_06v_import_manifest.json
?? backend/reports/document_intelligence_06v_import_manifest.md
?? backend/reports/document_intelligence_06v_import_manifest.sha256
?? backend/reports/document_intelligence_06v_run_identity.json
?? backend/reports/document_intelligence_06v_run_identity.sha256
?? backend/reports/document_intelligence_r2_architecture_review.md
?? backend/reports/document_intelligence_r3_review.md
?? backend/reports/document_intelligence_r4a_b4_structure_rescore.md
?? backend/reports/document_intelligence_r4a_batch1_reanalysis.md
?? backend/reports/document_intelligence_r4a_first_batch_analysis.json
?? backend/reports/document_intelligence_r4a_first_batch_analysis.md
?? backend/reports/document_intelligence_r4a_phase1.md
?? backend/reports/document_intelligence_r4a_phase4_structural_trust_hardening.md
?? backend/reports/document_intelligence_r4b_readiness_gate.json
?? backend/reports/document_intelligence_r4b_readiness_gate.md
?? backend/reports/native_structured_coverage_v4b.md
?? backend/reports/source_effect_qwen8b_baseline_v1.json
?? backend/reports/source_effect_qwen8b_bounded_v3.json
?? backend/reports/source_effect_qwen8b_calibrated_v2.json
?? backend/reports/source_effect_qwen8b_fully_bounded_v4.json
?? backend/reports/structural_trust_safety_v4a.md
?? backend/reports/structured_coverage_v4b_architecture.md
?? backend/tests/test_native_structured_coverage.py
?? docs/adr/0011-native-structured-coverage.md
```

## Resultado

Native puede producir Scope, Attributes y Quantities dentro de la gramática declarada.
La duplicación Native+Vision por capacidad se evita para el grounding comparable
soportado. La percepción sólo visual sigue fuera del slice y sin inferencias.
La implementación queda lista para revisión funcional; el gate global de ausencia
de schema drift queda bloqueado por las diferencias de índices preexistentes.

MVP-06.V.4b NATIVE STRUCTURED COVERAGE BLOCKED — READY FOR ARCHITECT REVIEW
