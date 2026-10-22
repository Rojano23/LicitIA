# MVP-06.V.6d — Native Table Relationship Bridge

Estado: implementación terminada, pendiente de revisión arquitectónica. Sin stage, commit ni push.
HEAD: `429bf2ff95043c6d74af379a22d85bdd85843340`.

## Representación real observada antes de implementar

Se generó un PDF sintético con líneas de tabla y se llamó al extractor productivo `_extract_pdf_pages`. El texto resultó `ITEM\nDESCRIPTION\nQUANTITY\nUNIT\nBRAND\n31\nSuministro de sensores\n3\nPZA...`: encabezados y valores independientes, sin pipes ni delimitadores inventados. La normalización conserva texto NFC y offsets propios de la generación; no conserva la relación fila/columna.

En SQL sobreviven texto, página, método y generación normalizada; el artefacto Native referencia esa generación. No sobreviven word spans, cajas, fuentes/estilos, filas ni celdas. El original local sí permite recuperar con PyMuPDF 1.28.2 cajas de palabras, IDs de bloque/línea/palabra y celdas delimitadas por líneas reales. No se usan fuentes/estilos ni se supone geometría a partir del texto. El puente agrega un companion local perezoso ligado al original y a la generación, sin cambiar el extractor ni el esquema.

## Contrato implementado

`native-table-relationships-v1` verifica ruta administrada, SHA-256 y tamaño del original, página y coincidencia exacta del texto extraído y normalizado con la generación activa. Usa `find_tables(strategy='lines_strict')`, cajas reales y pertenencia completa de palabras a celdas. Alinea palabras monótonamente con offsets literales del texto canónico. El sondeo de encabezados en líneas sólo decide si consultar geometría; nunca demuestra una relación.

Se requieren columnas distintas item/description/quantity/unit, ID entero positivo, cantidad numérica y unidad reconocida. Marca/modelo son opcionales. Se generan HEADER_OF, DESCRIBES_ITEM, VALUE_FOR, UNIT_FOR, ATTRIBUTE_OF y CONTINUES dentro de la fila/celda demostrada. Reutiliza StructuredEvidenceBlock, candidatos Scope, manifests, grounding y materializadores existentes. No modifica adaptadores de hijos.

No se fabrican celdas, delimitadores ni citas concatenadas. Las líneas permanecen fragmentos literales independientes; sólo los valores interpretados se componen. `native_table_proof` conserva versión del motor, cajas página/tabla/celdas, fila y refs. El Source conserva documento, página, hash original, revisión, generación y hash de texto. Validar exige replay contra el original y motor compatibles; alteración, ausencia o desalineación falla cerrada. Los manifests antiguos omiten la nueva propiedad ausente para conservar sus bytes y hashes.

Límites: 500,000 caracteres, 20,000 palabras, 32 tablas, 4,096 celdas, 256 bloques, 128 fragmentos por bloque y límites de almacenamiento existentes. Sólo tablas regladas rectangulares de 4–6 columnas con roles conocidos. Sin inferencia de encabezado entre páginas, ni reparación de celdas fusionadas, palabras cruzando bordes o layouts ambiguos. TOC, interrogantes y numeración de sección no producen Scope en las pruebas. Todo Scope queda `review_required=True`, sin confianza ni autoridad contractual automática.

## Matriz real PDF

Todas las escenas entran por POST import, extract-pages y normalize productivos; después usan materialización Scope y grounding reales sobre licitia_test. No se insertan evidencias Native ni IR manualmente.

| Caso | Resultado esperado verificado |
|---|---|
| RT01 | 2 bloques/Scope, 2 Quantities, 4 Attributes; ownership y página correctos |
| RT02 | 3 fragmentos de descripción, 2 CONTINUES, un Scope |
| RT03 | encabezado repetido contextual, sin ítem extra |
| RT04 | filas vecinas con igual descripción conservan cantidades 3/18 separadas |
| RT05 | encabezado y cantidad en fragmentos/celdas distintos |
| RT06 | atributo provisional; hijos sólo al materializar bajo Scope |
| RT07 | TOC sin Scope |
| RT08 | cuestionario sin Scope |
| RT09 | sección 2.1 sin Scope |
| RT10 | texto cruzando borde sin relación fabricada |
| RT11 | tabla multipágina, encabezado local, dos páginas/Scope distintos |
| RT12 | dos variantes de anchos, estables |
| RT13 | manifest SHA válido, bytes inmutables, replay determinista; caja falsificada rechazada |
| RT14 | tabla sin líneas sin prueba/Scope |
| RT15 | original ausente bloquea validación |
| RT16 | límite excedido da error explícito |
| RT17 | tabla mínima de cuatro columnas produce dos Scope con Quantity |
| RT18 | original modificado rechazado |
| RT19 | motor incompatible rechazado |
| RT20 | dos variantes KG/M con cantidades decimal/entera y ownership correcto |

El E2E aceptación produce **2 Scope + 2 Quantity + 4 Attribute**, desde PDF real sintético, conservando padres distintos. Multilínea conserva fuente representativa literal y refs independientes. Reejecución determinista no crea Scope extra ni altera el manifest.

## Esquema y superficies protegidas

Verificación de sólo lectura: revisión y head `20261013_req_perception_prov_072`; drift 59 (55 add_index/4 remove_index), firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`. Sin migración, tablas ni blobs nuevos. Evidencia: `native_table_bridge_v6d_schema.json`.

V.6c, eligibility OCR/Vision, budgets, task contracts, Requirements y Requested Evidence sin cambios. Sólo se registra la versión del puente en implementation_versions del freeze para futuros artefactos; freezes históricos no se reescriben. Proveedores reales ejecutados: **ninguno**. Tests de proveedores usan fakes/mocks; opt-in `local_ollama` excluido. No se consultó Ollama ni se ejecutó reconocimiento Tesseract/Vision para validar el puente. La prueba heredada de traducción de idioma construye Tesseract con `image_to_string` simulado; su constructor puede consultar la versión local del binario, sin procesar documentos con OCR.

Integridad histórica: 3,056 archivos comparados byte por byte mediante SHA-256, cero alteraciones; evidencia en `native_table_bridge_v6d_history_verification.json`. No se ejecutó Tender #002, no se inspeccionó semánticamente para tuning ni se inició un nuevo intento.

## Archivos del slice

Modificados: `backend/app/structured_evidence.py`, `backend/app/structured_evidence_grounding.py`, `backend/app/blind_selective_freeze.py`.

Nuevos: `backend/app/native_table_relationships.py`, `backend/tests/test_native_table_bridge.py`, `docs/adr/0017-native-ruled-table-relationship-proof.md` y artefactos `backend/reports/native_table_bridge_v6d*` (reporte, comandos, JUnit, esquema, baseline y verificación de historia). Reportes históricos/no rastreados ajenos se preservan. Sin stage/commit/push.

## Decisión de continuidad

**Does production Native extraction now provide sufficient structural evidence for the current IR architecture? YES**, para tablas regladas soportadas al recuperar geometría del original local y verificarla contra la evidencia Native activa. El texto plano persistido por sí solo sigue siendo insuficiente. La prueba demuestra continuidad genérica del pipeline para esa representación; no certifica recall de documentos reales ni calidad semántica de Tender #002.

Recomendación: **FINAL BLIND VALIDATION**, después de revisión y aceptación arquitectónica de V.6d/ADR 0017. No se ejecuta aquí. Tablas sin líneas, roles desconocidos, celdas fusionadas, atributos arbitrarios, marca/modelo con múltiples fragmentos (adaptador existente limitado), y encabezados heredados entre páginas permanecen fuera de cobertura. Requirements/Evidence mantienen sus limitaciones independientes; esto no declara UAT READY.

## Regresión reproducible

Comandos exactos: `native_table_bridge_v6d_commands.txt` y `native_table_bridge_v6d_expanded_command.txt`. Intérprete absoluto obligatorio, PostgreSQL `licitia_test`; sin base dev. La corrida RT inicial dio 17 passed (6 warnings); se añadieron tres checks de integridad/contrato, resultando 20 RT dentro de la ampliada. La enfocada inicial dio 367 passed (6 warnings).

| Grupo de la ampliada | Passed |
|---|---:|
| RT | 20 |
| SI | 39 |
| MG | 15 |
| ST_safety_and_propagation | 44 |
| SC_DC | 46 |
| V6c_PS | 36 |
| Scope_all | 159 |
| human_review_API | 87 |
| DI | 228 |
| expanded | 1119 |

Ampliada: **1,119 passed, 1 deselected, 8 warnings** (65.85 s), cero fallos. JUnit y conteos por módulo adjuntos en reports. SI incluye SI21–23. Scope incluye adaptadores, materializadores e integraciones de Scope/Attributes/Quantities; ST incluye propagación.

Warnings heredados: tipos SWIG sin __module__, python_multipart, configuración Alembic sin path_separator y Paddle sin ccache. Sin avisos de fallo funcional. `compileall` (app/scripts/tests) y `git diff --check`: exit 0.


Suite completa: **2,075 passed, 1 deselected, 8 warnings** (130.99 s), cero fallos. Incluyó las 20 RT de la ampliada. Después sólo se añadieron dos parametrizaciones de unidades y una aserción explícita de IDs idempotentes; sin cambios de producción. Verificación RT final: **22 passed, 6 warnings** (7.57 s). No se repitió la suite completa por esas ampliaciones exclusivas de test. `native_table_bridge_v6d_full.xml` y `native_table_bridge_v6d_rt_final.xml` conservan el detalle.

Comando RT final:

```sh
/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest tests/test_native_table_bridge.py -q --junitxml=reports/native_table_bridge_v6d_rt_final.xml
```

`compileall` y `git diff --check` repetidos después del ajuste de tests: PASS. Staging vacío. Diff rastreado: tres archivos, 45 inserciones/4 eliminaciones; más módulo Native, tests, ADR y evidencia nuevos no rastreados. Sin cambios de esquema ni blockers de implementación; aceptación arquitectónica y validación ciega pendientes.

MVP-06.V.6d NATIVE TABLE BRIDGE COMPLETE — READY FOR ARCHITECT REVIEW
