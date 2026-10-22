from pathlib import Path
import json,statistics,hashlib,subprocess
B=Path(__file__).resolve().parent
summary=json.loads((B/'digital_summary.json').read_text());evaluation=json.loads((B/'page_field_evaluation.json').read_text());by={(x['page'],x['tool'],x['configuration']):x for x in evaluation}
lines=['# Matriz completa de configuraciones','', 'Shapes incluyen encabezados. Parámetros exactos y defaults efectivos en digital_configurations.json/effective_defaults.json; matrices/celdas/bboxes en results/.','', '| Página | Tool/config | Shapes de tablas | Ítems con cantidad/unidad correcta | Determinista 2/2 | Segundos (dos ejecuciones) |','|---|---|---|---|---|---|']
for x in summary:
 ev=by[(x['page'],x['tool'],x['configuration'])];fields=[f for t in ev['evaluations'] for f in t['item_fields']]
 linked=sum(f['quantity_and_unit_in_correct_row'] for f in fields)
 lines.append(f"| {x['page']} | {x['tool']}/{x['configuration']} | {x['table_shapes']} | {str(linked)+'/'+str(len(fields)) if fields else 'N/A'} | {x['deterministic']} | {x['repeat_seconds'][0]:.3f} / {x['repeat_seconds'][1]:.3f} |")
(B/'configuration_matrix.md').write_text('\n'.join(lines)+'\n')
report='''# LicitIA — Benchmark open-source de extracción física de tablas

**Decisión: candidato de integración identificado — Camelot 2.0.0, spike acotado Camelot→IR.** No integración ni desarrollo V.6e realizados. HEAD `0b04fc7677e670fb487683ac904d3c3a89daa373` intacto. Attempt8 permanece fallo de release gate; no se rerunó ni se creó Attempt9. Este benchmark conocido no es una nueva validación ciega.

## Método, alcance y referencia

Cinco páginas dirigidas, no muestra estadística: B-1 p.1 (dos tablas: materiales y normas), B-1 p.2 (control de prosa), Bases p.41 (otro formulario Native digital), Cuestionarios p.12 (formulario superior débilmente delimitado y cuestionario inferior) y Anexo C p.1 (tabla material escaneada, Native vacío). Proceden del source_index/adjudicación aceptada de Attempt7 y conservan hashes/original/page identity en page_manifest.json. No corpus-wide tuning ni envío de PDFs a servicios externos.

Referencia en `reference_proposed.json`: transcripción visual manual del asistente, basada en la adjudicación aceptada; **no se presenta como una nueva referencia humana independiente aprobada**. Se solicitó confirmación humana de las dos partidas en chat; mientras no se reciba, permanece propuesta pendiente. Bboxes aproximadas por lectura de render, coordenadas PDF origen superior izquierdo, sólo para evaluar solapamiento; nunca se pasaron al extractor ni se eligieron zonas/columnas hardcodeadas. No se estima precisión/recall global ni se oculta el resultado detrás de un score único.

| Página / tabla | Referencia lógica propuesta | Identidad, cantidades y atributos |
|---|---|---|
| B1 p1 / materiales | 3 filas con header × 4 columnas; bbox≈[49,292,568,415] | Partida1→1PZA; partida2→2PZA; marca GE MULTILIN en cada descripción; números de parte distintos F60…/L90… |
| B1 p1 / normas | 11×2; bbox≈[54,448,558,696] | Diez normas/descripciones; no diez partidas ni cantidades |
| B1 p2 | sin tabla de datos en cuerpo | Prosa/listas de obligaciones; panel de encabezado decorativo no procurement |
| Bases p41 | 2×2; bbox≈[42,396,547,427] | Documento / Tipo de Información, placeholders XXXXXXXX/XXXXXXXXX; no ítems |
| Cuestionarios p12 / superior | 4×3; bbox≈[56,124,560,230] | Tres renglones de formulario, valor5.00 en porcentaje, no cantidad comercial |
| Cuestionarios p12 / inferior | 12×3; bbox≈[92,272,525,709] | Once preguntas, Sí/No; los bullets pertenecen a pregunta5, no filas nuevas |
| AnexoC p1 | 3×4; bbox≈[39,213,560,337] | Dos partidas 1/2PZA y marca/números de parte como B1; fuente escaneada |

Números de parte literales: `F60-U03-HKH-F8L-H6L-M6B-P6B-W7K` y `L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K`. El source rotula NUMERO DE PARTE/No.PARTE; esto no autoriza convertirlos silenciosamente a `model` canónico. Los renders y PDFs mon página derivados están en pages/; originales intactos.

## Versiones, licencias y aislamiento

pdfplumber0.11.10 y Camelot2.0.0 eran releases estables consultadas en PyPI; versiones fijadas y dependencias en versions.json/benchmark_environment_freeze.txt. Venv separado `/private/tmp/licitia-table-benchmark-venv`. No cambios a requirements, Docker, imports app, adaptadores, planner, IR/grounding, DB/esquema o migraciones.

- [pdfplumber v0.11.10, LICENSE MIT](https://github.com/jsvine/pdfplumber/blob/v0.11.10/LICENSE.txt).
- [Camelot v2.0.0, LICENSE MIT](https://github.com/camelot-dev/camelot/blob/v2.0.0/LICENSE); [release estable](https://github.com/camelot-dev/camelot/releases/tag/v2.0.0).
- [PaddleOCR v3.7.0, Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/LICENSE). Se usó runtime ya instalado PaddleOCR3.7.0 / PaddlePaddle3.3.0 / PaddleX3.7.2; sin instalación o actualización en backend. Caché y pesos nuevos sólo dentro del benchmark. No se afirma haber usado PaddlePaddle3.3.1 más reciente.
- Pesos oficiales declarados Apache-2.0: [PP-DocLayout-S](https://huggingface.co/PaddlePaddle/PP-DocLayout-S), [SLANet_plus](https://huggingface.co/PaddlePaddle/SLANet_plus), [PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det), [latin_PP-OCRv5_mobile_rec](https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec). Model cards archivadas; revisiones, SHA y tamaños en model_manifest.json, contrastados con los blobs publicados cuando disponibles.
- docTR: [código Apache-2.0](https://github.com/mindee/doctr/blob/main/LICENSE), no instalado/ejecutado ni pesos descargados. Su [ruta OCR documentada](https://github.com/mindee/doctr#quick-tour) detecta y reconoce palabras; aquí otro OCR no resuelve por sí solo el rowspan erróneo con texto ya correcto. No añade comparación estructural decisiva a este set pequeño.

Licencias verificadas antes de instalar/descargar. Copias en licenses/. Metadata transitive en installed_dependency_licenses.json: playa-pdf/pdfminer MIT, OpenCV Apache-2.0, pypdfium2 BSD/Apache con licencias transitivas. No Ghostscript ni Camelot[ml]/[ocr] instalados; no candidato AGPL/comercial recomendado. Despliegue requeriría conservar notices/licencias de paquetes y del binario PDFium, fijar wheels/model revisions y revisar su distribución concreta; MIT de Camelot no sustituye las licencias transitivas ni la de pesos. No se infiere calidad española por una licencia Apache o por confianza alta del modelo.

## Baseline V.6d — replay sólo lectura

v6d_baseline.json usa exactamente el código committed y artefactos Native activos de la página seleccionada, Session SQL read-only, root de Attempt8 establecido antes de Settings. Sin materializar ni guardar manifests. En las cinco páginas: **IR0, filas IR0, columnas IR0, Quantity/Attribute links0**. El escaneo no tiene artefacto Native textual. Geometría original existe en las cuatro páginas digitales; no se inventa en el escaneo.

La prueba geométrica bruta `PyMuPDF.find_tables(lines_strict)` **sí detecta B1 materiales3×4 y normas11×2**, y Bases formulario2×2. En B1 el header shape gate es True, pero el puente produce0bloques sin excepción; no se atribuye el fallo exclusivamente a detección física. En Cuestionarios el detector bruto segmenta17×7. Este resultado distingue detector geométrico de relación/celda→IR productiva. Sustituir sólo una llamada find_tables no es una solución demostrada. No se implementó otro parche de gramática ni se alteró el puente.

## Matriz digital

70 combinaciones (5páginas × [6pdfplumber +8Camelot]), **dos ejecuciones por combinación**, 140extracciones, cero errores; las70producen estructura idéntica en repetición. Parámetros genéricos fijados, sin bboxes ni columnas específicos del Tender. `configuration_matrix.md` registra cada combinación/shapes/tiempos; JSON completos en results/ contienen texto de celdas, coordenadas, matrices y métricas de parser. `page_field_evaluation.json` separa página/tabla/campo, y `effective_defaults.json` conserva defaults efectivos/siganturas de las versiones fijadas.

pdfplumber: lines(default), lines_strict/lines_strict, text/text, text/text con snap/join/intersection tolerance5, lines/text y text/lines; otros defaults sin cambio. Camelot: lattice engines combined/vector/raster; stream default y split_text=True; network; hybrid; auto. `auto`2.0 es heurístico raster/network, no ML. La configuración de cada corrida está serializada junto a los resultados.

| Página | pdfplumber | Camelot | Evaluación de campo / falsos positivos |
|---|---|---|---|
| B1 p1 materiales | lines3×4 correcto; strict0; text87×6, tolerance5→55×6; combinaciones fragmentan | lattice combined/vector/raster, hybrid y auto3×4 correctos; stream14×5 y network0 | En los correctos: IDs1/2, cantidades1/2, PZA y marca/número de parte conservados en su fila. 2/2Quantity links y2/2desc→spec links físicamente defendibles |
| B1 p1 normas | lines15×9 incorrecto (líneas/rectángulos generan splits); texto no resuelve | lattice tres engines, hybrid/auto11×2 correctos; stream20×2 incorrecto | Texto multilínea de normas debe permanecer en una celda; no se promueven códigos IEC a item/quantity |
| Bases p41 | lines2×6, strict0; estrategias text mezclan prosa | combined/vector2×2 correcto; raster0; hybrid2×2 más tabla espuria18×1; auto/network18×1 espurio | La contribución vectorial importa; combined evita perder una tabla tenue/coloreada que raster solo pierde |
| Cuestionarios p12 inferior | lines17×7; text67×8/tolerance547×8; splits por checkbox | lattice/auto17×3; hybrid12×3 correcto; stream28×4; network26×1 | Hybrid conserva bullets dentro de pregunta5. No es procurement, aunque sea tabla correcta |
| Cuestionarios p12 superior débil | Ninguna configuración recupera estructura4×3 defendible | Ningún parser probado recupera estructura4×3 defendible | Permanece gap; 5.00 no se convierte en cantidad/item por estar en una pseudo-tabla |
| B1 p2 control prosa | lines detecta panel1×2; text61×7/tolerance540×7 falsos como cuerpo | lattice combined/vector panel1×2; raster0; stream25×4+8×1, network21×2, hybrid21×3 falsos | Detectar un rectángulo de encabezado no es detectar una tabla de materiales; no usar table_count como recall |
| AnexoC p1 escaneo | Sin tablas/texto | Todos los parsers sin tablas por ausencia de texto Native | Resultado esperado de extractores digitales; requiere percepción estructural selectiva |

No se eligió el parser por marca/modelo/Tender. Las diferencias prueban límites de capacidad (vectores, líneas, alineación y forma física), no una regla comercial nueva.

## PaddleOCR local — escaneo material

Se evaluaron **componentes modulares oficiales de PaddleOCR usados en la familia PP-Structure**, no se presenta esto como ejecución del pipeline completo PP-StructureV3 ni TableRecognitionV2. [La documentación permite inferir módulos independientemente](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md).

Layout PP-DocLayout-S sobre página completa render2×; detecta una tabla en píxeles [78.10,423.58,1116.42,668.66], score0.6893. El crop lo decide ese detector, no la referencia humana. SLANet_plus sobre crop devuelve tres filas y cuatro columnas efectivas, **11celdas en lugar de12**: primer item `rowspan=2`. Structure score0.9754 no convierte esa relación incorrecta en evidencia confiable.

OCR con PP-OCRv5_mobile_det + latin_PP-OCRv5_mobile_rec reconoce ambos IDs, cantidades1/2, PZA y marca/números de parte exactos respecto a transcripción visual propuesta; rec_scores≈0.9876–0.99998. Sin embargo, la primera celda item abarca dos filas y la segunda partida carece de celda propia: **ownership completo no defendible con esa estructura**. Los textos OCR, polígonos, scores, estructura HTML y bboxes están separados en paddle_components_repeat*.json. Transformación de geometría documentada: (coordenada crop + origen crop)/2 hacia PDF; considerar redondeo de crop <1px y error del detector, no geometría Native exacta.

Dos ejecuciones equivalentes excluyendo paths/timing. CPU4threads, sin GPU; orientación/unwarping/textline orientation deshabilitados genéricamente, no se corrigieron celdas o texto manualmente. Modelos26,244,630bytes; startup1.35s, inferencia4.54/4.29s, RSS pico≈641.4MiB. Red bloqueada en inferencia; sólo descargas previas de pesos públicos. Warnings ccache/sysctl sandbox visibles; inferencia terminó exit0.

No se generaliza este fallo a toda PP-StructureV3: faltan sus detectores de celdas/recognition pipeline completo. Esa comparación sería otro experimento selectivo si se acepta investigarlo; este resultado no permite recomendar todavía ese fallback para producir ownership automático. docTR no ejecutado por falta de beneficio estructural esperado en este caso ya legible, no por licencia.

## Literalidad, geometría e integración

En tablas Native correctas, pdfplumber/Camelot recuperan todos los campos críticos de las dos filas sin valores nuevos observados. Comparación exacta modulo whitespace para IDs/quantity/unit/brand/partnumber; no se afirma CER global de cada carácter de las cinco páginas. Cambian espacios y saltos de línea: **un string de celda compuesto no es una nueva cita literal**. pdfplumber permite auditoría a caracteres con bbox (capturados por celda); Camelot conserva bbox tabla/celda y matriz, con origen inferior original y conversión superior explícita. Los gráficos de checkbox, bordes de sombreado y paneles producen falsos splits/tablas según estrategia.

El adapter debe volver al texto Native canónico y preservar fragmentos/offsets independientes. No persistir DataFrame/HTML como verdad contractual. Los números de parte y la marca dentro de Descripción tienen dueño físico; su tipificación semántica no viene resuelta por Camelot. El extractor no emite Scope ni registra Quantity/Attribute; este benchmark no prueba materialización productiva positiva.

Compatibilidad: la IR actual ya representa Source, fragments, fields y HEADER_OF/DESCRIBES_ITEM/VALUE_FOR/UNIT_FOR/ATTRIBUTE_OF/CONTINUES. El grounding actual de native_table_proof está fijado a motor PyMuPDF y NATIVE_RULED_TABLE_001. **Camelot no es drop-in con ese proof**: necesita variante de prueba versionada/mapeo y replay verificable, sin reemplazar el modelo semántico, manifests, identidad lógica ni materializadores. La atribución de modelos/partnumbers no debe ampliarse silenciosamente; conservar label/value literal y review o abstención si el contrato actual no lo soporta.

## Rendimiento y despliegue

MacOS15.6.1 arm64, Python3.13.15,8CPU lógicas. Medianas de 10runs por configuración (incluyen página escaneada sin texto): pdfplumber lines0.078s, Camelot lattice_combined0.284s (máximo1.344s con inicio frío), vector0.024s, hybrid0.265s, auto0.463s. El proceso digital combinado llegó≈508MiB; ese ru_maxrss es high-water mark del proceso compartido, **no memoria incremental de cada parser**. No extrapolar throughput de un set5páginas.

Camelot añade OpenCV, PDFium, playa-pdf, pandas/openpyxl/numpy; no se instaló Ghostscript ni ML. pdfplumber usa pdfminer/PDFium/Pillow. Paddle necesita runtime/modelosCPU y cachingoffline; scores y entrenamiento English/Chinese de algunos modelos no certifican idioma/especificaciones del corpus. Hay diferencias reales de tiempo/dependencias además de precisión física. Rutas de entorno y freeze de paquetes conservados para reproducción; ninguna dependencia entró a producción.

## Decisión y spike mínimo recomendado

**Caso B con cobertura parcial complementaria entre parsers de Camelot. Candidato principal: Camelot2.0.0 `lattice`, engine=`combined`.** Recupera materiales/Quantity y specs de fila donde V6d da0IR, mantiene normas11×2 y formulario Native2×2. `vector` demuestra alternativa rápida para PDFs con líneas vectoriales; `hybrid` resuelve el cuestionario, pero produce falsos positivos en prosa. No elegir auto como default ni desplegar un router con más herramientas a partir de cinco páginas.

**V6d: augmentar**, conservando comportamiento legado y sus límites. No reemplazar ciegamente el detector bruto (que ya ve B1) ni reconstruir otro detector propio. El contrato de ingreso tabla/celdas→IR es parte del gap. No se justifica sumar simultáneamente pdfplumber como segundo detector de producción: es alternativa MIT viable para materiales, y herramienta útil de auditoría de caracteres; no resolvió normas/formulario tan bien. Percepción estructural de escaneos es una necesidad separada; Paddle probado aún no certifica ownership. Ningún score alto autoriza un fallback global.

Spike propuesto, **sólo recomendación para aprobación posterior**:

1. Un adapter de extracción física Camelot lattice_combined, sin ML, sobre originales Native verificados; parámetros genéricos congelados y límites tiempo/memoria/páginas. Output tipado de tablas/celdas/rowspan/geometry, conservando versión y parámetros; no copiar detector ni configurar por Tender.
2. Mapping a StructuredEvidenceBlock existente, con Source original/page/hash/generation/text hash y fragmentos canónicos independientes; campos item/description/unit/quantity sólo cuando positivos y una única fila/celda lo demuestra. Marca explícita label/value bajo review si hay contrato de alias aprobado; no convertir automáticamente número de parte a model ni desarrollar extracción arbitraria. Si la tipificación de atributos exige trabajo sustancial separado, detener y reportar.
3. Variante nueva de proof/replay Camelot aprobada en ADR, en vez de mentir NATIVE_RULED_TABLE_001/PyMuPDF. Conservar manifests inmutables, fail-closed, ownership y revisar grounding por fragmentos. Sin cambiar planner/budgets ni Requirements/Evidence; sin migración prevista.
4. Gate de spike: PDF original→Native→tabla→IR→Scope/Quantity y Attribute soportado con source exacto, dos filas sin cruce, casos negativos formularios/prosa/cuestionarios, múltiples documentos genéricos nuevos, manifests/replay/idempotencia/mutación/revisión humana. Las páginas de este benchmark son conjunto expuesto, no Golden congelado ni prueba out-of-sample; no adulterar históricos.

Sólo tras ese E2E, regresión y aceptación arquitectónica se justificaría solicitar Attempt9. No basta instalar Camelot ni obtener un DataFrame3×4. No se crea ni preautoriza Attempt9, ni se convierte Attempt8 en semanticPASS. Una futura validación debe declarar exposición del set y separar evidencia out-of-sample. Si ese spike no logra source/ownership defensible, corresponde reevaluación arquitectónica/producto, no otra expansión artesanal de gramática.

## Preservación y entrega

Git/HEAD, inventario hashes e integridad final en integrity_verification.json. Reportes/scripts/resultados/modelos sólo en `backend/reports/table_tooling_benchmark/` untracked y venv temporal. No cambios productivos, stage, commit, push, DBwrites ni mutaciones de Attempts1–8. No rerun Attempt8; no Attempt9. No suite productiva innecesaria: se verifican140extracciones, repetibilidad, 2inferencias Paddle, sintaxis de scripts, Gitdiffcheck y hashes históricos; el código productivo no cambió.

Archivos centrales: page_manifest.json, reference_proposed.json, v6d_baseline.json, configuration_matrix.md, results/*.json, page_field_evaluation.json, performance_summary.json, paddle_*json, licenses/, model_manifest.json, versiones/freeze, run_digital_benchmark.py, run_paddle_components.py, evaluate_digital.py. Referencia humana independiente pendiente si no hay respuesta en chat; esa limitación no se oculta detrás de cifras de accuracy.

LICITIA OPEN-SOURCE TABLE TOOLING BENCHMARK COMPLETE — INTEGRATION CANDIDATE IDENTIFIED
'''
(B/'benchmark_report.md').write_text(report)
print('Report and configuration matrix written')
