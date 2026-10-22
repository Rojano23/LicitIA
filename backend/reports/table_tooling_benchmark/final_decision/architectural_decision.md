# Decisión arquitectónica final — benchmark de tablas

**Opción B — CAMELOT INTEGRATION SPIKE.** Candidato: Camelot2.0.0, parser `lattice`, engine `combined`, parámetros genéricos fijados. Augmentar el ingreso físico tabla/celdas→IR; conservar StructuredEvidenceBlock, grounding, identidad, Scope/children, review/provenance y validación ciega. No implementar en esta tarea.

HEAD preservado: `0b04fc7677e670fb487683ac904d3c3a89daa373`. Cero nuevas extracciones/inferencias/dependencias; decisión basada en los artefactos corregidos existentes. Benchmark anterior147archivos y4,407archivos históricos verificados íntegros; Git rastreado limpio, staging vacío, diffcheckPASS. Evidencia en integrity.json e input_evidence_hashes.json. El directorio final_decision es nuevo/untracked; no modifica el benchmark consumido ni Attempts1–8.

## Referencia humana y alcance

Única referencia humana de partidas aquí: **Anexo B-1 p.1**: partida1→1PZA→GE MULTILIN→modelo empiezaF60…; partida2→2PZA→GE MULTILIN→modelo empiezaL90…. No se hereda **ninguna** de estas partidas a AnexoC p.1. Allí los outputs son observaciones independientes de modelos y no existe confirmación humana de item/quantity/model association. Bboxes visuales de evaluación y sufijos literales completos no son una nueva aprobación humana.

Se mantienen separados literal_fragments.json, geometry_fragments.json y fragment_provenance.json bajo reference_revision_002/, unidos por fragment_id. La auditoría nueva b1_fragment_cell_audit.json usa sólo esos fragmentos y las celdas ya extraídas:37fragmentos Native/37con una única celda/37textos presentes en esa celda en pdfplumber lines y Camelot lattice combined/vector/raster/hybrid/auto. No es grounding productivo ni una puntuación de recall de página completa; no se compara contra prosa reconstruida.

## B-1: diez criterios por extractor ejecutado

Evaluación de la tabla relevante de materiales, no de cualquier tabla en la página. PASS se refiere a referencia humana y fragmentos guardados; PARTIAL señala límites concretos. Lattice incluye combined/vector/raster: resultados iguales3×4 en este caso. Hybrid y auto se muestran porque fueron ejecutados, no como defaults recomendados.

| Criterio | V6d productivo | pdfplumber lines | Camelot lattice | Camelot stream / split | Camelot network | Camelot hybrid / auto | Paddle en B1 |
|---|---|---|---|---|---|---|---|
| 1 Detecta tabla relevante | PASS, geometría3×4 | PASS | PASS | PARTIAL, región detectada pero14×5 | FAIL, sin tabla | PASS | NOT TESTED |
| 2 Exactamente dos filas lógicas item | FAIL,0IR | PASS | PASS | FAIL | FAIL | PASS | NOT TESTED |
| 3 Distingue fila1/fila2 utilizable | FAIL en IR | PASS | PASS | FAIL | FAIL | PASS | NOT TESTED |
| 4 Conserva descripción/model-prefix bajo fila | FAIL en IR | PASS | PASS | FAIL como relación | FAIL | PASS | NOT TESTED |
| 5 Item1→1PZA | FAIL | PASS | PASS | FAIL | FAIL | PASS | NOT TESTED |
| 6 Item2→2PZA | FAIL | PASS | PASS | FAIL | FAIL | PASS | NOT TESTED |
| 7 Literalidad fuente | PASS Native; no bloque compuesto | PASS,37fragmentos | PASS,37fragmentos | PARTIAL, texto repartido/fragmentado; no certificado campo por campo | NOT TESTED, sin output | PASS,37fragmentos | NOT TESTED |
| 8 Bbox para provenance | PARTIAL, geometría existe pero sin proof IR | PASS, tabla/celda/caracteres | PASS, tabla/celda | PARTIAL, coordenadas de partición incorrecta | FAIL, sin tabla | PASS | NOT TESTED |
| 9 Sin filas/celdas falsas en tabla relevante | PASS por abstención; geometría3×4 | PASS | PASS | FAIL,14×5 | PARTIAL, abstiene sin output | PASS | NOT TESTED |
| 10 Mapping a IR sin rediseñar dominios | PARTIAL, camino existente falla | PARTIAL, adapter/proof pendientes | PARTIAL, adapter/proof pendientes | FAIL con esta salida | FAIL con esta salida | PARTIAL, adapter/proof pendientes | NOT TESTED |

No se contabiliza al cuestionario o a la tabla de normas como Scope. No se marca mapping PASS porque ningún extractor externo fue integrado productivamente. Preservar fuentes no convierte automáticamente un número de parte literal en el campo `model` canónico.

### pdfplumber0.11.10

Trabaja `vertical_strategy=lines`, `horizontal_strategy=lines` con defaults fijados. B1 materiales3×4, dos items y relaciones Quantity/Unit/description correctas según referencia. Todas las seis configuraciones son deterministas2/2; sólo lines satisface ese caso completo. lines_strict no detecta; text/text devuelve87×6, tolerancias snap/join/intersection5→55×6, lines/text fragmenta20×2, text/lines19×6. No se usaron coordenadas explícitas ni frases comerciales para extracción.

La biblioteca expone bbox y caracteres; se archivaron texto/cajas por celda. Su `Table.extract` decide pertenencia por centros horizontal/vertical del carácter, no contención de la caja entera de una palabra. Literalidad crítica comprobada con fragments. Fuera de esa tabla introduce splits de celdas y falsas tablas de prosa. Integración viable, pero cobertura digital secundaria inferior a Camelot; no copiar su algoritmo al Core.

### Camelot2.0.0

`lattice` combined/vector/raster, hybrid y auto recuperan3×4: ambas filas, cantidades/unidades, marca y cadenas F60…/L90… en sus descripciones. `stream`, incluso split_text=True, devuelve14×5; network no detecta la tabla material. Los strings de celda tienen variaciones de whitespace; las37palabras Native fuente siguen vinculadas a la celda correcta. Bboxes originales PDF-bottom-left y conversión top-left están guardados por tabla y celda.

`lattice_combined` es el candidato inicial: combina líneas raster y vectoriales. `vector` obtiene el mismo resultado más rápido en este set; `hybrid` aporta al cuestionario, pero crea tablas de prosa en otros casos. `auto` es heurístico no neural en esta versión, pero falla en Bases41; no recomendarlo como default. Accuracy/confidence del parser no son confianza contractual.

## Por qué V6d falla aquí

No faltan líneas: el baseline guardado detecta B1 materiales3×4 y normas11×2, header-shape gateTrue, pero genera0bloques sin excepción. La explicación demostrable está en `v6d_failure_evidence.json`, deducida de geometría existente y código committed, sin nueva extracción:

- Tabla material: y superior292.3219787597656pt.
- Fragmento literal «Unidad»: bbox [459.0700073,291.8689880,491.3889465,304.1269836].
- Su caja de palabra sobresale **0.4529907pt** por encima del borde. Cualquier celda contenida en esa tabla resulta incapaz de contener esa caja por completo.
- `_cell_spans` devuelveNone si una palabra se solapa con la celda pero no está completamente dentro. `header_spans` incompleto hace que reconstruct_native_tables omita la tabla antes de construir filas/IR.
- Los sintéticos colocan texto dentro de celdas amplias: no ejercitaron esta protrusión de métricas de fuente en un encabezado real multilínea.

pdfplumber admite la pertenencia mediante centros de caracteres. Camelot `get_table_index` usa banda por punto medio vertical de línea y solapamiento horizontal/error de asignación; no exige contención completa de cada bbox PyMuPDF. Esa robustez de asociación texto-celda explica el éxito material, no una capacidad borderless que hiciera falta en B1 ni un aumento de percepción. Otras diferencias (líneas vectoriales débiles y hybrid para bullets) importan en casos secundarios.

No se propone relajar esa condición con un epsilon hecho para este Tender. No se modifica V6d ni se copia otro detector. Tampoco se afirma que reemplazar sólo find_tables resolvería el pipeline: el detector bruto ya encontraba B1. El spike debe evaluar el contrato físico completo de texto/celdas→IR.

## Páginas secundarias, sin verdad heredada

| Página / tabla | pdfplumber | Camelot | Texto, geometría, relaciones y falsos positivos |
|---|---|---|---|
| B1p1 normas | lines15×9, splits incorrectos | lattice tres engines/hybrid/auto11×2; stream20×2 | Camelot conserva diez normas y descripción bajo cada fila, bbox disponible. No son items/cantidades; estos conteos de layout permanecen referencia visual propuesta |
| Basesp41 Native, formulario | lines2×6, strict0; text incorpora prosa | combined/vector2×2; raster0; hybrid agrega18×1 espurio; auto/network18×1 | Columnas Documento/Tipo información recuperadas por combined/vector, placeholders preservados. Prueba de aporte vectorial frente a raster solo; no procurement |
| Cuestionariosp12 inferior | lines17×7 por checkboxes; text67×8 | lattice17×3, hybrid12×3; stream28×4/network26×1 | Hybrid conserva bullets en pregunta5 y11preguntas. Bbox disponible, texto fuente observable. Checkbox no es columna/item nuevo; no relaciones Quantity comerciales |
| Cuestionariosp12 superior débil | Ninguna configuración recupera4×3 defendible | Ningún parser probado recupera4×3 defendible | Gap real de borderless/alineación; el5.00 observado es porcentaje, no quantity. No recomendar router que no lo resuelve |
| B1p2 prosa | lines detecta panel1×2; text61×7 falso | lattice combined/vector panel1×2; stream/network/hybrid fragmentan prosa; raster0 | Panel decorativo no es tabla de bienes. Table count/confidence alto no sustituye identidad positiva |
| AnexoCp1 escaneo | Sin texto/tablas | Sin texto/tablas | Ausencia Native; no son pruebas de que falten items reales. Ninguna partida B1 se atribuye aquí |

V6d productivo tiene0IR en todas estas páginas; su geometría bruta de Bases2×2 y Cuestionarios17×7 no equivale a relaciones semánticas aceptadas. Las cifras secundarias comparan el layout visual propuesto; la confirmación humana de B1 no se extiende a ellas.

## PaddleOCR / PP-Structure y docTR

Ejecutado únicamente en AnexoCp1: componentes independientes PaddleOCR3.7.0, PaddlePaddle3.3.0 y PaddleX3.7.2, no PP-StructureV3 end-to-end ni TableRecognitionV2 completo. PP-DocLayout-S detectó una región table(score0.6893); SLANet_plus produjo11polígonos y un rowspan=2(score0.9754); OCR mobile det/latin rec emitió strings y polígonos. Dos repeticiones equivalentes excluyendo paths/timing. Aporta **detección/OCR/estructura predicha en imagen donde los parsers digitales no tienen texto**. No se probó en B1 Native ni layouts digitales difíciles, y no se ejecutó corrección de OCR previo.

Partidas/cantidades/asociaciones de AnexoC quedan **sin verificación humana independiente**. No se heredan ni1ni2desdeB1; no se puntúa literalidad contra B1. El rowspan y las cadenas se conservan como observación, no se certifica que una segunda partida tenga o no tenga celda correcta. Su confianza alta no certifica ownership; no hay evidencia suficiente para elegir OpciónD. El pipeline completo PP-StructureV3 permanece NOT TESTED; no extrapolar el resultado modular a él.

docTR no se ejecutó: NOT TESTED, sin resultado de geometría/celdas/rows/texto a inferir. No se recomienda como solución estructural a partir de su capacidad OCR documentada.

## Geometría, literalidad e integración

Los datos ganadores son relaciones físicas auditables de fila/celda, con fuentes y coordenadas. El audit B1 de37fragmentos usa los literales nativos y cajas fuente separados, y comprueba pertenencia única/texto coincidente para las seis configuraciones ganadoras. No produce una nueva cita concatenando la DataFrame ni demuestra un IR productivo generado por Camelot. Los fragmentos deben volver a los offsets de la generación Native canónica con hash/revisión/página; si no hay alineación unívoca, REVIEW_REQUIRED/abstención.

El proof existente `NATIVE_RULED_TABLE_001` y su validator fijan PyMuPDF y replay del puente actual. No puede etiquetarse una caja Camelot como si fuera esa prueba. Hace falta una variante de evidencia/replay versionada, acotada y aprobada en ADR, manteniendo la IR y manifests existentes. Los hijos siguen resolviendo el padre por identidad lógica. Marca explícita puede proponerse bajo contrato aprobado; etiqueta NUMERO DE PARTE no se convierte silenciosamente a model, ni se amplía extracción de especificaciones arbitrarias.

## Gate de licencia y coste

Verificadas las copias de licencias de releases y model cards archivadas con hashes del benchmark, no se instaló nada nuevo:

- [pdfplumber0.11.10: MIT](https://github.com/jsvine/pdfplumber/blob/v0.11.10/LICENSE.txt).
- [Camelot2.0.0: MIT](https://github.com/camelot-dev/camelot/blob/v2.0.0/LICENSE). Parser recomendado no usa pesos ML. Metadata fijada: playa-pdf/pdfminer MIT, OpenCV Apache-2.0, PDFium/pypdfium2 BSD/Apache y licencias transitivas. No Ghostscript, ML backend ni OCR extras instalados.
- [PaddleOCR3.7.0: Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/LICENSE). Model cards oficiales PP-DocLayout-S, SLANet_plus, PP-OCRv5_mobile_det y latin_PP-OCRv5_mobile_rec declaran Apache-2.0; archivos/revisiones/hashes en model_manifest.json. No se generaliza esa declaración a pesos no probados de PP-StructureV3.

Candidato digital compatible con integración comercial bajo estas licencias permisivas sin licencia comercial obligatoria identificada. Mantener atribuciones/notices y revisar el bundle concreto y licencias transitivas PDFium antes de distribuir; la licencia superior no reemplaza esa revisión. No recomendar candidato AGPL. Modelos y código ML tienen gates separados; su licencia no certifica dominio/idioma ni calidad.

MacOSarm64/Python3.13.15; mediana por configuración sobre5páginas (incluido escaneo sin texto): pdfplumber lines0.078s, Camelot combined0.284s, vector0.024s, hybrid0.265s. RSS pico proceso digital compartido508MiB: no es RAM incremental de cada parser. Paddle CPU4threads: startup1.35s y4.54/4.29s inferencia, pico641MiB,26.24MBpesos; red bloqueada durante inferencia. Son mediciones aproximadas del set, no SLA de producto. Camelot añade OpenCV/PDFium/playa/pandas; no coste ML para el candidato inicial.

## Recomendación única y spike mínimo

**Elegir OpciónB. No OpciónC:** el caso humano principal lo resuelve una sola biblioteca; la complementariedad relevante es entre parsers de Camelot. pdfplumber es alternativa viable pero inferior en normas/formulario. No hay justificación para un router digital con múltiples bibliotecas a partir de este set. OpciónA no es la más fuerte, D carece de ownership validado y E no procede mientras exista un candidato digital con relaciones defendibles.

Spike propuesto para autorización posterior:

1. Un adapter físico Camelot2.0.0 lattice_combined, parámetros genéricos congelados, original/page verificados, límites explícitos de tiempo/memoria; preservar tabla/celda/bbox y versión/configuración. Sin parser por Tender ni detección propia copiada.
2. Traducir celdas a fragmentos Native canónicos independientes y relaciones existentes; exigir identidad positiva V4a y cantidad/unidad explícitas con un único dueño. Campos de marca/atributo sólo bajo contrato de label/value soportado; desconocidos quedan en descripción/review. Nada de semántica contractual inferida del DataFrame.
3. Variante de proof tipada/versionada y replay verificable para ese adapter, dentro de IR/grounding existentes; ADR acotado. Sin SQL/migración esperados, sin reemplazar manifests, Scope/children, review o provenance. Si exige un rediseño sustancial de hijos/esquema, STOP y revisión arquitectónica.
4. Mantener planner, eligibility, proveedores, budgets y Requirements/Evidence sin cambios. Conservar bridgeV6d para compatibilidad y medir el camino nuevo; no reemplazar todo el stack antes de demostrar E2E.

### Gate mínimo antes de solicitar Attempt9

- PDFs genéricos reales por import/extract/normalize: dos filas con IDs distintos, 1/2cantidades variadas, unidades/atributos explícitos, fuente literal y bbox. Probar encabezado multilínea con métricas de palabra sobrepasando el borde, varias fuentes/tamaños/anchos, sin epsilon ligado a B1.
- Negativos de prosa/paneles/índices/normas/cuestionarios/checkboxes y layout ambiguo: no convertir números/porcentajes en items; celdas sin propietario inequívoco abstienen.
- Encabezados repetidos, varias tablas y varias páginas: no duplicar Scope ni heredar dueño sin evidencia; hijos vecinos no se cruzan.
- E2E PDF→IR→Scope→Quantity y Attribute soportado, no sólo DataFrame; no model canónico inferido de partnumber. Persistencia/replay idempotentes, fuente fragmentada conservada, review humano vigente.
- Manifests/hash/version/config/source tampering, generación stale, original ausente o alterado: fail-closed. No citas compuestas falsas ni geometría inventada.
- Tiempo/memoria bounded, ejecución local/offline, licencias transitivas fijadas; regresión SI/MG/ST/SC-DC/PS/Scope/human-review/API y ampliación apropiada por cambios. Demostrar cero cambio del planner/budgets, Alembic/drift esperados y Git limpio en commit aceptado.

**Attempt9 actualmente NO está justificado ni autorizado por esta decisión.** Sólo solicitarlo tras spike E2E, regresión y aceptación arquitectónica en un HEAD limpio congelable. Las páginas ya examinadas son conjunto expuesto, no nueva evidencia out-of-sample; declarar exposición y separar el control de generalización. No ejecutar Attempt9, no rerun de8, no reetiquetar8como semanticPASS y no autorizar otra gramática incremental por defecto.

LICITIA TABLE BENCHMARK DECISION COMPLETE — BOUNDED INTEGRATION SPIKE RECOMMENDED
