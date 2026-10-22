# MVP-06.V — Adjudicación semántica propuesta de Blind Attempt #4

**Autoridad:** propuesta de Codex sustentada en fuentes locales; `approved_by_human=false`. Pendiente de revisión arquitectónica/humana independiente. No se escribió HumanTruth, freeze_analysis ni métricas adjudicadas en el first-pass.

**Integridad operacional: PASS. Seguridad: CONDITIONAL PASS. Calidad semántica: FAIL.** El pase mejora la abstención en dos casos conocidos, pero no convierte la recuperación adicional en cobertura estructurada. No se inventa un umbral ni recall global.

## 1. Integridad y método

Run `06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba`; HEAD `a24a5b18fe43ca15a949408b77e19aea1f2950a4`.
Perfil SHA `a4e14ff90be7b66912ab51ac47b060a5a94a90fc38a9f35e37856d03303dfdc6`.
Pre-freeze SHA `cc61ea98cf31ecbc897e49ef02692db938c2dc99a09f657222d9e344b57e6285`.
Binding SHA `e37b77425fe2cc8ca12d0ebe8b51bca797d57e9524f0eaa93d1c0b1779a863b9`.
First-pass SHA `893ecae1aa6bf9b1fe510eba5b8fefb82fc4e5ff5d6bdb22172bdede6311395b`.
FROZEN y manifest operacional verificados:1,369 archivos originales intactos. Históricos107 y24 archivos/originales de Attempt3 intactos.

Se comparó el conjunto completo de11 originales mediante SHA contra source_index de Attempt2, y se verificaron los bytes originales actuales. Los11 hashes coinciden: se puede reutilizar la adjudicación previa sobre la misma fuente, conservando su carácter de propuesta. No se usó como guía de implementación.

Se compararon por fuente SHA+página+contenido31 Requirements,43 candidatos y8 Requested Evidence. Se revisaron las8 adquisiciones OCR,10 decisiones de reuse y3 tareas Vision/4 llamadas. Se comprobaron visualmente los2 antiguos TRUSTED, catálogo, SSPA y B-1, y se inspeccionaron muestras dirigidas de trabajo diferido. source_review.txt conserva extracción Native de28 páginas seleccionadas;10 renders de fuentes se conservan como ayudas de lectura, NO como nuevas percepciones productivas. Incluyen dos páginas adicionales de imagen110/111. No se afirma lectura exhaustiva de253 páginas, precisión global del planner ni recall total.

La única función productiva evaluada en diagnóstico puro fue procurement_rows sobre transcripciones ya congeladas: sin DB, proveedores, adapters persistentes ni materializadores. No se reprodujo el pipeline. La igualdad semántica se limita a los campos enumerados; no afirma igualdad de UUID, timestamps o provenance interna.

## 2. Requirements, candidatos y Requested Evidence

Los31 Requirements mantienen exactamente canonical_text, categoría, fuente SHA/página y excerpt del candidato primario. Los43 candidatos mantienen requirement_text/fuente/página. Los8 Requested Evidence mantienen descripción/tipo/excerpt/fuente/página. Los tres conjuntos emparejan1:1 con Attempt2. Todos los Requirements/Evidence siguen REVIEW_REQUIRED.

Por lo tanto se conservan los juicios previos propuestos: Requirements15 sustentados,8 sustentados con defectos,8 contextuales/no autónomos; Evidence1adecuado,5incompletos/mal tipados,2contextuales. No hay mejora del contenido emitido demostrada por OCR/Vision. Encabezados, obligaciones de la convocante, instrucciones de modelo, cortes de abreviaturas y pérdida de contexto siguen presentes. Las43 ocurrencias no son43 obligaciones independientes; se conservan repeticiones de encabezados CN/excepción DA5.

Los18 misses materiales de Requirements y2componentes incompletos,18 Evidence no individualizadas,8Scope,10Attributes y4Quantities del conjunto dirigido anterior permanecen sin resolver en los outputs comparados. Son límites inferiores de aquella muestra, no un inventario contractual exhaustivo ni dominios sumables entre sí. source_cases del JSON conserva cada juicio y su source SHA/página actual.

En D11p1, OCR recupera Formatos6y7 y5días hábiles, pero no aparecen candidatos sobre esa página. El detector acepta evidencia OCR activa de calidad REVIEW_REQUIRED, de modo que no está excluida por proveedor. Su segmentación/gramática de modalidad y actor no reconstruye la fila de tabla; el fragmento “Si aplica y se debe entregar...” no coincide con la modalidad fuerte “deberá” y queda separado del nombre de los formatos. Esto identifica una pérdida en descubrimiento/interpretación, no un fallo de OCR ni de persistencia de Requirement. No se ejecutó nuevamente el detector para fabricar un ledger temporal que el pase no conservó.

## 3. Scope / Attributes / Quantities: primer punto de pérdida

Native ya contiene modelos, marca y cantidades en B-1p1; cables/software/embalaje enp2; cartas/marcado/avisos enp3; documentación de entrega/2juegos de contrato enp4. OCR agrega catálogo y SSPA, pero Scope=Attributes=Quantities=0.

Diagnóstico de gramática sobre251 observaciones Native no vacías y8OCR disponibles: **0 procurement_rows en259 fuentes**. No es una medición de recall ni un replay productivo. NativeScopeDetailAdapter y OcrScopeDetailAdapter usan esa misma función: línea rotulada PARTIDA/ITEM/CONCEPTO/No +número, seguida inmediatamente por acción admitida (suministro/servicio/entrega). No reconstruyen tablas ni párrafos de obligaciones.

- B-1p1: tabla extraída como encabezados/filas/celdas separadas, sin bloque “PARTIDA1: Suministro...”. **Pérdida primera: reconocimiento de candidato en adapter.**
- B-1p2: “Para la partida01y02” y obligaciones distribuidas en prosa; no encabezado de fila contractual admitida. Mismo punto de pérdida, pese a OCR adicional.
- B-1p3/p4: numerales2.7/3.4 son secciones, no nuevas partidas; Scope distribuido no encaja en esa gramática. No se debe rescatarlo inventando nuevos owners.
- Catálogo D02p1: OCR recupera modelos/unidad/cantidades, pero pierde números de partida y relación espacial de columnas. Cero candidato; requiere grounding por renglón, no emparejamiento arbitrario.

Attributes y Quantities sólo se materializan iterando ScopeDetail existentes en materialize_canonical: con0 padres no se invocan esos pasos para el Tender. Hay además una restricción secundaria: explicit_fields requiere etiquetas colon “marca/modelo/cantidad/unidad”. Da{} en B-1p1/p2 y catálogo OCR: “FABRICANTE/MARCA”, “NUMERO DE PARTE” y encabezados/celdas separados no crean esos campos. No se atribuye cero a dedup, grounding final o review policy: los candidatos ya son0 antes de esos pasos. El código permite persistir candidatos review-required/unresolved; la revisión no es un veto general de persistencia.

## 4. OCR: valor real y límites

Las8 adquisiciones/8páginas no son18 lecturas nuevas:18completados incluye10reuses del mismo texto, sin nueva adquisición. Ningún resultado recibe confianza automática por existir.

| Fuente | Aporte y fidelidad | Consecuencia |
|---|---|---|
| D09p2 | Texto material de embalaje,2juegos por puerto,USB/Windows10 ya estaba en Native; OCR lo conserva con ruido | Duplicación de percepción; adapter sigue0 |
| D09p3 | Traducción/cartas/48h/marcado10mm ya estaban en Native; ruido en numeración | Misma brecha de interpretación; no nuevo Scope |
| D11p1 | Native vacío; recupera Formatos6/7,aplicabilidad y5días hábiles | Aporte material nuevo; numerales romanos/filas dañados; sin Requirements/Evidence nuevos |
| D06p1 | Native ya contenía convocatoria/cronograma; OCR altera alineación de fechas | No nueva obligación confiable; necesita lectura tabular, no texto redundante |
| D06p2 | Native ya contenía e.firma/firmantes | Redundante para contenido material |
| D06p3 | Firmas/certificados ya en Native; OCR daña cadenas | Sin nuevo Scope ni evidencia del participante |
| D02p1 | Native vacío; recupera modelos GE,PZA1/PZA2 | Aporte material nuevo; pierde binding de filas/partidas;0estructurado |
| D01p51 | Recupera diálogo de certificado mostrado como EJEMPLO | Contexto, no certificado real ni fecha de vigencia del participante |

La lectura visual independiente confirma1PZA modeloF60 y2PZA modeloL90 en catálogo/B-1. No se promueve desde OCR plano a certeza de propiedad/cantidad. Los2juegos por puerto no autorizan inferir cuántos puertos ni multiplicar cables;2juegos de contrato no son2equipos. En SSPA se confirma VI Salud=N/A y Formatos6/7 aplicables5días hábiles después de entrega del requerimiento, no automáticamente después de entregar bienes. No reconstruir cláusulas externas a partir de códigos dañados por OCR.

Los locators/generation IDs/artifact keys existen y se vinculan a fuente/page/version/hash. Para región de imagen, la selección/provenance física es válida; no prueba fidelidad semántica. Las fuentes OCR permanecen disponibles REVIEW_REQUIRED; no fueron descartadas por ser OCR. No hay causa de dedup demostrada para las pérdidas.

## 5. Vision: cuatro llamadas, tres tareas

| Fuente/tarea | Resultado/fallo exacto | Valor y consumo |
|---|---|---|
| B-1p2 STRUCTURE_SCOPE | COMPLETED,45,285ms | Modelo convirtió1.2/1.3/2 (secciones) en nuevas partidas. Incorrecto como identidad de compra; apenas cues de sección |
| B-1p2 DETAIL_TRANSCRIPTION intento1 | TIMEOUT:timed out,60,028ms | Sin resultado validado |
| B-1p2 DETAIL_TRANSCRIPTION intento2 | OUTPUT_TRUNCATED / DONE_REASON:length,59,505ms | Retry exhausted; sin detalle consumible |
| B-1p3 STRUCTURE_SCOPE intento1 | TIMEOUT:timed out,60,029ms | Presupuesto global agotado; sin otro intento |

No se observaron errores de render/schema como causa de estas3llamadas fallidas; no convertir truncación en un mero errorJSON. Los raw responses fallidos no se conservaron completos: la clasificación usa razones de cada evento PLANNER, latencia, estado del cliente y receipt. No se reejecutó nada.

La única estructura completada corresponde a toda la imagen de B-1p2. Source/page/hash/region son correctos; el error es semántico: forma de empaque y entrega aplican a partidas01/02 existentes, no son partidas1.2/1.3 nuevas. anchor_raw_text parafrasea; new_items incluye review_required=false crudo para etiquetas erróneas. El resolver global NO los aceptó: REVIEW_REQUIRED/UNKNOWN y sin owner saliente. No hubo Scope falso confiado.

La estructura completada no contiene DETAIL_TRANSCRIPTION/parsed_supply_rows. VisionScopeDetailAdapter soporta ese contrato de detalle, no estructura. Ésa es separación correcta de capacidades; no se debe utilizar la estructura como texto detallado para ocultar el fallo de la tarea de detalle. No se demostró aporte Vision de detalle contractual nuevo útil y propagado.

## 6. Planner y presupuestos

Muestra dirigida, no aleatoria:8adquisiciones completas,4llamadas,2fuentes de imagen material,2antiguos falsos TRUSTED y trabajo diferido de catálogo/Bases/PACMA. No se calcula precisión global de80OCR/78Vision.

Cinco de las8páginas adquiridas (B-1p2/p3 y Convocatoriapp1–3) ya tenían el núcleo textual material en Native. El caso certificado aporta un ejemplo contextual. Dos páginas realmente carecían de texto Native y OCR añadió información material. Esto evidencia problemas de selectividad/priorización, no prueba que cada una de las80necesidades sea incorrecta.

Suficiencia Scope/Attributes/Quantities depende de la misma gramática estrecha y de identidad estructural válida. Incapacidad para interpretar evidencia existente puede terminar etiquetada como necesidad de percepción si existe regiónIMAGE. construct_tasks aplica preguntas de varios dominios a todas las páginas y preguntas espaciales a regiones elegibles cuando Native no supera el contrato. region_id explícito fuerza native_sufficient=false: no hay binding Native regional que cierre el contrato. Por eso avoided0 no equivale a “Native no contiene información útil”.1111SKIPPED tampoco significa1111tareas satisfechas:860NO_PROVEN_OCR_SOURCE y251TEXT_TASK_CONTRACT_REQUIRED.

Vision aplica dos contratos independientes genéricos; B-1p2/p3 son continuación de prosa ya Native. Resolver ownership/contexto es una necesidad semántica, pero no necesariamente un déficit visual que otra adquisición resuelva. El éxito del esquema de llamada no valida esa selección ni el rol de las secciones.

Presupuestos8OCR/4Vision sí limitaron adquisición:62resultados OCR diferidos y76Visionbudget-exhausted, no62/76páginas únicas. D02p1 tiene dos preguntas Vision diferidas pese a que el binding de filas es material y el OCR plano no lo conserva. Basesp110/111 contienen imágenes de modelo de carta de créditoStandby sin textoNative útil; ambas quedaron diferidas. Son información contractual potencialmente material, cuya aplicabilidad requiere contexto, no nuevas obligaciones automáticamente adoptadas. PACMA26páginas y Basesp52/p96 incluyen mucho Native disponible; no todo diferido es una pérdida perceptual. Tres de4llamadas Vision fallaron y la otra propuso roles incorrectos. No hay sustento para concluir que aumentar budgets por sí solo resolvería recuperación estructurada; se separan selección, fallos de proveedor, capacidad de consumo y límites finitos.

## 7. Seguridad y contraste con Attempt2

Los2antiguos TRUSTED incorrectos se verificaron por SHA/página e imagen: índice de reglas D01p13 y cuestionario de integridad D03p12. Ahora ambos REVIEW_REQUIRED, continuidad UNKNOWN, outgoing_item_key=null. Mejora observable:2/2casos inseguros conocidos dejan de confiarse. No es una tasa global de exactitud ni un denominador inventado.

Attempt4 tiene0TRUSTED estructurales y0Scope/Attributes/Quantities. Requirements31/Evidence8 siguen review, no certificación de obligaciones autónomas. Se conserva la abstención frente a estructuras nuevas falsas de Vision. Safety CONDITIONAL PASS: mejora comprobada de fail-closed, pero propuestas crudas, pérdida de fidelidad, owners y cobertura continúan pendientes. No se afirma que toda revisión sea necesaria ni que toda provenance recursiva esté certificada.

Los6conflictos son diferencias de transcripción Native/OCR en B-1p2/p3, Convocatoriapp1–3 y Basesp51. Se comparan coberturas/orden/ruido distintos, incluyendo regiónimagen vs página; no son6contradicciones contractuales verificadas. El antiguo conflicto de continuación del índice no es una obligación real. No se mide globalmente cuánto conflicto contractual permanece oculto. No se identificaron IDs/documentos de fuente inventados en los examinados; sí roles de partida incorrectos y anchors parafraseados en salida Vision, protegidos por review.

## 8. Decisiones y acción arquitectónica

- Operacional: PASS (integridad/freeze/guard confirmados, sin rerun).
- Seguridad: CONDITIONAL PASS, por la mejora concreta de abstención y las limitaciones no certificadas.
- Calidad semántica: FAIL: omisiones materiales persistentes, ceroScope/Attributes/Quantities pese a evidencia disponible y escaso aporte Vision útil. La conclusión no usa un umbral numérico nuevo.
- Frente a Attempt2: mejora perceptual de dos páginas de imagen y seguridad en dos casos; contenido emitido de31/43/8sin mejora semántica demostrada. Conflictos/review mayores no implican mejor comprensión.

Cuello de botella principal en los casos Native/OCR ya disponibles: **interpretación/adapters/grounding estructurado**, no ausencia de percepción. En fuentes de imagen aún diferidas y tareas fallidas hay también límites de percepción/proveedor. No reducir todos los misses a una causa.

Siguiente acción recomendada: revisión arquitectónica de la brecha entre contratos de suficiencia y consumo estructurado, usando casos sintéticos genéricos independientes para tablas, prosa distribuida y grounding de filas/owners; revisar selectividad antes de justificar otra ejecución o presupuesto. No autoriza tuning con Tender2, fixes, cambios de modelo/budget ni Attempt5. No certificar cierreMVP06 ni saltoMVP07 con estos outputs.

## 9. Clasificación de deficiencias

- **no defect**: Storage/freeze/input integrity; preservation of sources and abstention on the two prior unsafe trusted structures.
- **expected MVP limitation**: Bounded row grammar intentionally excludes prose/table reconstruction; technically conforms to narrow contract but insufficient for measured semantic objective. Unsupported Finder metadata safely represented.
- **adapter defect**: Material Native/OCR content has zero eligible Scope rows; child attribute/quantity adapters depend on nonexistent Scope and colon-labelled fields. Requirements/Evidence segmentation/classification defects persist.
- **planner/selectivity defect**: Task-contract/identity grammar insufficiency is escalated as perception deficit on images; five of eight acquired pages already carried core text in Native. Spatial contracts overbroad on B1 prose; no global precision estimate.
- **OCR quality limitation**: Useful image text recovered, but item-row bindings and Roman numerals/layout are not faithfully retained.
- **Vision provider/model limitation**: Two timeouts and one truncated output; completed structure falsely labels section headings as procurement items.
- **Vision task-contract defect**: STRUCTURE_SCOPE/DETAIL_TRANSCRIPTION generic spatial questions on a prose continuation consume scarce calls without proving a distinct visual need; contracts remain separate technically.
- **grounding defect**: Raw Vision anchor paraphrases and OCR flattened table cannot be promoted to exact row ownership. Source page/image identities themselves are valid.
- **materializer defect**: No independent persistence defect demonstrated; first loss precedes materialization. Persisting review-required candidates is supported by code.
- **logical identity/dedup defect**: Not demonstrated:0 Scope proposals reach reconciliation; reuse10 is not10 additional acquisitions. No evidence zero Scope was caused by dedup.
- **trust-policy defect**: Prior defect improved for two known cases; current review abstention works. Broad all-page review may be conservative, but no global unnecessary-review count established.
- **budget-policy limitation**: Finite budget deferred legitimate AnexoC layout question and unperceived image template pages110/111. Overbroad selection and3failed Vision calls confound budget adequacy; no recommendation to simply increase limits.
- **provenance defect**: No invented source IDs/hashes found in examined records; citation/context defects from Attempt2 persist. Raw semantic anchors and image-region/page differences require review, not fabricated certainty.

## 10. Ledger de Requirements (propuestas heredadas tras equivalencia exacta)

| Etiqueta / ID actual | Fuente | Clasificación | Evaluación |
|---|---|---|---|
| R01 / `f3585204-74fe-4409-8bf3-e0991416d974` | D10 p1 | SUPPORTED_WITH_DEFECT | La obligación de declarar CN sí existe, sin porcentaje mínimo. El encabezado no conserva Formato 3, plazo ni acuses (§5.1); no equivale al manifiesto de origen de bienes. |
| R02 / `04b2bdd3-0834-444e-8ac1-7a1e8dd61d40` | D01 p78 | SUPPORTED_REQUIREMENT | Condicional a consorcio: cada integrante entrega Anexo 3/DD-8. No convertirlo en requisito de toda participación individual. |
| R03 / `99010e10-4ebc-49e0-ae96-2bf3980ea302` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | D05 es modelo sin completar: instrucción al redactor y Anexo en blanco; no acredita una obligación adoptada ni su aplicabilidad. |
| R04 / `9cda38b4-1f47-487a-9fb3-822d54803c6b` | D01 p41 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Excepción válida de no desechamiento del DA-5; NO es obligación positiva de presentar un documento. Conservar como criterio/exención, no como obligación autónoma. |
| R05 / `d4935c82-be4e-48b7-9fbf-feed2f567661` | D01 p50 | SUPPORTED_WITH_DEFECT | Obligación real pero “presente documento” queda sin identidad autónoma: DA-13, aceptación de e.firma. Falta el objeto documental en canonical_text. |
| R06 / `592bf8b4-139f-4084-917d-dd9787332aef` | D01 p18 | SUPPORTED_REQUIREMENT | Considerar bases finales/modificaciones aplicables es regla real; no demuestra que existan modificaciones ni un Source Effect específico. |
| R07 / `39926a03-9b13-4dff-b02d-7eef91bfb6c2` | D01 p9 | SUPPORTED_REQUIREMENT | Alta inicial SISCEP tras comunicación: condición y cuenta/contraseña conservadas. |
| R08 / `b0f37a9f-f07d-49de-9f76-d68995b6ff30` | D01 p97 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Regla de la CONVOCANTE sobre PMR, no obligación autónoma del licitante. Además corta “Negociación de la” y pierde continuación p98. |
| R09 / `40c9ee9d-2657-4a75-95bf-0b19630eb51f` | D01 p72 | SUPPORTED_WITH_DEFECT | Condicional real, pero “presente documento” en p72 es continuación de DD-2 (p71). No unificarla semánticamente con el manifiesto de origen p53–54 sólo por texto igual. |
| R10 / `48d2b5e6-5051-47ea-ac57-3d719d300ea3` | D01 p9 | SUPPORTED_REQUIREMENT | Aceptación del Acuerdo de Participante en SISCEP es real, aunque el inicio del fragmento arrastra una referencia de sección. |
| R11 / `e02489e4-47a6-4241-b256-363543dd4398` | D01 p18 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Instrucción de soporte condicionada a dudas; no acredita documentación de elegibilidad ni obligación técnica/comercial autónoma. |
| R12 / `f879f159-a795-4032-9d8f-fdbb841c50b9` | D01 p19 | SUPPORTED_REQUIREMENT | Firma de última hoja por facultado, donde se solicite; no significa que cualquier persona o firma por ausencia sea válida. |
| R13 / `74a27370-60df-4318-8ac1-82f7d2080593` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre1 comercial PDF/ZIP hasta100MB y documentos D-1: regla de presentación real; no lista todas sus evidencias. |
| R14 / `f8ce8c76-311f-4cd8-97fc-1c87b161a6e2` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre1 técnico PDF/ZIP hasta100MB y D-3: regla real; no sustituye catálogo de obligaciones de B-1. |
| R15 / `611ccf21-ae70-4405-bbca-3875315b20aa` | D01 p87 | SUPPORTED_REQUIREMENT | DA-3 membretado y firmado real. Su mera mención no extrae por separado identificación, actas y poderes exigidos en la tabla. |
| R16 / `3640d72c-4514-4820-9252-17c9c1ab684e` | D05 p54 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Nota de modelo para cláusula de financiamiento >500 millones; D01 p14 dice Fuentes de Financiamiento No Aplica. Texto localizado real, aplicabilidad como obligación del Tender no sustentada. |
| R17 / `0c55f8a9-1b44-468e-8527-0e4a13ded794` | D01 p19 | SUPPORTED_WITH_DEFECT | Presentación electrónica real, pero corta antes de enumerar los sobres y elimina 9. del ordinal 9.2; no es evidencia documental específica. |
| R18 / `a6d67971-03fa-4cf1-b7b1-6e3cacd4c74d` | D09 p2 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Encabezado “Otros requisitos...” sin los numerales 2.1–2.8. No expresa una obligación verificable por sí solo. |
| R19 / `ff7d7fd2-e68c-4c1d-9ade-172a560b60d6` | D01 p9 | SUPPORTED_REQUIREMENT | Corregir/re-enviar DA-1 si discrepa del SISCEP: requisito condicional real; el resto del párrafo fija consecuencia/plazo no conservados aquí. |
| R20 / `4ee70ac5-fb29-4480-b3db-0875375bdcf9` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Instrucción para redactar acuerdos referenciales/preparatorios, no el contrato puntual de D01 p15. Categoría EXPERIENCE tampoco está sustentada. |
| R21 / `b414fd66-55df-4f18-b5e4-9e30a88590ae` | D01 p21 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Obligación del servidor público de levantar acta. Actor no es el participante; corte inicial “1,2 y3” pierde el contexto de sobres. |
| R22 / `36025725-621d-4e24-8c46-cc10c8b0a16a` | D01 p20 | SUPPORTED_REQUIREMENT | Sobre3 DD PDF/ZIP hasta100MB y anexo DD: obligación real; no implica extracción de sus documentos individuales. |
| R23 / `9ff6d936-351c-4fe0-9ff6-c856020f946d` | D01 p100 | SUPPORTED_WITH_DEFECT | Regla real de desempate; omite del texto autónomo el supuesto de empate previo. No aplicar siempre a todos los participantes. |
| R24 / `c06df2aa-9b69-4081-b9e7-104d2603def3` | D01 p93 | SUPPORTED_REQUIREMENT | Firma autógrafa por facultado DA-3 en propuesta técnica, al menos última hoja. Solapa parcialmente R12, con alcance técnico más específico. |
| R25 / `5a6c8b0c-fa51-4b82-b67a-351547eadf60` | D01 p82 | SUPPORTED_REQUIREMENT | Fotografías actualizadas DD-12 realmente solicitadas. No aparecen como Requested Evidence individual en los ocho emitidos. |
| R26 / `764e613a-a5bb-4b59-bf04-63c2e26a3f62` | D01 p96 | SUPPORTED_REQUIREMENT | Aritmética correcta y corrección sin cambiar unitarios: criterio económico real, no permiso para fijar precio automáticamente. |
| R27 / `a5e8a317-f5ee-4afe-9ba3-63fa4b7dd1e5` | D01 p9 | SUPPORTED_REQUIREMENT | Reutilizar cuenta existente en los supuestos de RI/RC: condición alternativa a R07, no duplicado exacto. |
| R28 / `099640eb-9d5a-41d2-812e-69773c065f61` | D09 p3 | SUPPORTED_WITH_DEFECT | Corta en “estén en otro”, omite la traducción simple y la conformidad completa; categoría PERSONNEL no corresponde a documentación técnica/idioma. |
| R29 / `bddbceb8-6ee9-46ba-a1a2-b3d344de24d9` | D01 p94 | SUPPORTED_WITH_DEFECT | Congruencia de propuesta y soportes real; PERSONNEL es clasificación incorrecta. El defecto es categorización, no falta de respaldo textual. |
| R30 / `3d3be949-16c6-4567-bf65-b44ec29796e2` | D01 p50 | SUPPORTED_WITH_DEFECT | Certificado e.firma/SAT por integrante de consorcio; corte A.C. pierde la identificación completa del emisor y la relación e.firma. |
| R31 / `e1524376-6244-431b-9e85-6fd26fec2c16` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre2 económico PDF/ZIP hasta100MB y D-4: regla real; D-4 es criterio de evaluación, no el nombre de un único formato a entregar. |

## 11. Requested Evidence

| Etiqueta / ID actual | Fuente | Clasificación | Evaluación |
|---|---|---|---|
| E01 / `56994d60-7437-4008-b938-7adb44d2aaed` | D01 p19 | CONTEXT_NOT_DOCUMENT | Mecánica de sobres, no documento autónomo. Solapa paquetes E02/E04/E06/E08; no contar como cinco documentos distintos. |
| E02 / `d5982028-be4f-4926-b375-5b1172730683` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Propuesta económica real. Descripción cortada antes de referencia completa; falta DE-1 y sus campos. FORM sólo cubre el componente de formato, no todo el paquete. |
| E03 / `f6aba220-3601-407f-8789-b333476339d5` | D05 p15 | CONTEXT_NOT_DOCUMENT | Mención/instrucción de modelo con Anexo en blanco. La obligación real de DT-1 condicional se sustenta en D01 pp16/93, no en haber completado ese espacio de D05. |
| E04 / `fa84e005-57cd-4f02-a1e2-c5c867d96fd7` | D01 p20 | SUPPORTED_BUT_INCOMPLETE | Documentación DD real, pero FORM es demasiado estrecho para paquete de documentos. Omite inventario DD-1…DD-14 y condiciones. |
| E05 / `c885c2ee-fbd5-4d9f-9f1e-a6de7178624a` | D01 p87 | SUPPORTED_DOCUMENT | Documento DA-3 realmente requerido; página y fragmento correctos. Registro genérico DOCUMENT válido; anexos específicos no se materializan por nombrar el formato. |
| E06 / `51bb2713-c2f9-4aff-9071-9837f0754fd6` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Paquete comercial real; FORM es demasiado estrecho. Corte pierde D-1 y no enumera documentos exigidos. |
| E07 / `699dee62-14e8-47e9-801a-fe1d8ea73270` | D01 p50 | SUPPORTED_BUT_INCOMPLETE | CERTIFICATE sí corresponde al certificado e.firma, pero “EMITIDO POR EL A” está truncado y no identifica SAT/A.C. ni certificado completo. |
| E08 / `6c4f2251-cb85-4ff5-93dc-effe84fccb6b` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Propuesta técnica real; texto cortado y sin lista DT-9, DT-11, catálogos/cartas. No considerar una evidencia satisfecha por existencia de este registro. |

## 12. Candidatos:43 equivalencias

| Etiqueta | ID actual | Fuente | Clasificación previa conservada |
|---|---|---|---|
| C01 | `79cd958f-916e-4f55-854b-194156b7f9ee` | D01 p19 | SUPPORTED_REQUIREMENT |
| C02 | `9050d539-e234-40d7-b9a3-6355ed0aa289` | D01 p9 | SUPPORTED_REQUIREMENT |
| C03 | `1da57502-b55f-4ce3-a957-4c3207ad0ab6` | D01 p82 | SUPPORTED_REQUIREMENT |
| C04 | `83e2d395-a35e-49f6-aa34-7a6eb28fdff4` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C05 | `1d9dfcfb-f479-44ca-ba34-1cc761533bf4` | D10 p10 | REPEATED_HEADER_OCCURRENCE |
| C06 | `52b9b171-d653-4a41-8200-5248ec7e7aa3` | D05 p54 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C07 | `434b22ac-200e-487f-b1c0-aa0086c8e275` | D01 p19 | SUPPORTED_WITH_DEFECT |
| C08 | `6cbe3a10-46a1-4dc9-923f-713567d38f9a` | D01 p72 | SUPPORTED_WITH_DEFECT |
| C09 | `18c002f1-106d-4c7c-ba7d-3206994ba1d5` | D01 p9 | SUPPORTED_REQUIREMENT |
| C10 | `967dfdb0-9fd6-4fea-b1ae-097730e6b2a5` | D01 p19 | SUPPORTED_REQUIREMENT |
| C11 | `b82d5554-f99e-449d-ac2e-7be652437e37` | D09 p2 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C12 | `4e391ccd-395d-4fb5-8667-65bf557b25e0` | D10 p8 | REPEATED_HEADER_OCCURRENCE |
| C13 | `aad0965c-ac97-4bfb-90b0-2e121fde2e41` | D10 p9 | REPEATED_HEADER_OCCURRENCE |
| C14 | `0b73306e-0f8e-4b32-934e-a18f29164730` | D01 p89 | DUPLICATE_CONTEXT_OCCURRENCE |
| C15 | `0ac7c46f-695d-4c34-815c-44664ba19637` | D01 p21 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C16 | `7b0872a1-0bbe-4b4e-b51b-d932a972b7d1` | D01 p93 | SUPPORTED_WITH_DEFECT |
| C17 | `2044d51b-c791-4b84-8a0c-57891c14302e` | D01 p50 | SUPPORTED_WITH_DEFECT |
| C18 | `e114557f-4ce2-4a5d-9c96-ebb64039e090` | D10 p6 | REPEATED_HEADER_OCCURRENCE |
| C19 | `6a160265-9b87-4147-af05-3b1cb57a6ba0` | D09 p1 | SUPPORTED_WITH_DEFECT |
| C20 | `b8775193-572b-476a-82f0-4ad35fe1a9d9` | D01 p9 | SUPPORTED_REQUIREMENT |
| C21 | `5be5822e-3fce-41cc-9217-5e06705675e7` | D01 p100 | SUPPORTED_WITH_DEFECT |
| C22 | `d5460650-c416-4e62-9b00-8b87166ed41c` | D01 p94 | SUPPORTED_REQUIREMENT |
| C23 | `d88b560e-0d2b-45aa-9df1-7a18361156f7` | D01 p19 | SUPPORTED_REQUIREMENT |
| C24 | `7c81862f-3f63-4f7c-b06e-61058d6e2e4d` | D01 p19 | SUPPORTED_REQUIREMENT |
| C25 | `015a120e-5368-495e-8396-0e1d3fc3213a` | D01 p20 | SUPPORTED_REQUIREMENT |
| C26 | `337db4e6-0d0e-4eb3-9b5f-5b2d233ff4f8` | D01 p18 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C27 | `b4523734-e1e9-4ed8-bc80-9a7796899654` | D10 p11 | REPEATED_HEADER_OCCURRENCE |
| C28 | `e66da09a-0a2f-4729-a160-67c3fef22733` | D01 p78 | SUPPORTED_REQUIREMENT |
| C29 | `132f8423-8c51-46d9-829d-1de19f3f429b` | D01 p18 | SUPPORTED_REQUIREMENT |
| C30 | `8d89793e-5eb4-4be4-b591-1ca210e6a0df` | D01 p97 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C31 | `a328d6ed-320a-4b69-9461-59583aa2042e` | D01 p87 | SUPPORTED_REQUIREMENT |
| C32 | `39cca73f-5ace-4e0a-b968-1396e1340837` | D01 p88 | SUPPORTED_WITH_DEFECT |
| C33 | `87125eab-bbb3-4ed2-bc79-fb53cb3f6db2` | D01 p54 | SUPPORTED_WITH_DEFECT |
| C34 | `747eddaa-2c1f-48ed-8e35-12f51e15b9a9` | D10 p1 | SUPPORTED_WITH_DEFECT |
| C35 | `3d6c39bc-bdec-47f8-a26e-55c7e0e7b810` | D01 p41 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |
| C36 | `2154d8ce-8e79-4999-b4b9-7a89eccbf607` | D01 p49 | SUPPORTED_WITH_DEFECT |
| C37 | `52ab22e6-4b64-45a9-9223-dc69ca38b6ab` | D01 p50 | SUPPORTED_WITH_DEFECT |
| C38 | `0c8b62e2-d718-407e-b1ff-04b88ed3aa61` | D01 p93 | SUPPORTED_REQUIREMENT |
| C39 | `f5c91463-3288-4780-a7ba-4ed644fc324d` | D01 p96 | SUPPORTED_REQUIREMENT |
| C40 | `905121b6-04d2-4e25-bc70-d5f7109c1318` | D01 p9 | SUPPORTED_REQUIREMENT |
| C41 | `81ac9958-e1a7-46a4-a719-043cce520a7d` | D09 p3 | SUPPORTED_WITH_DEFECT |
| C42 | `b1bc9ae6-7e6a-4da9-b77d-ad638fe3b492` | D01 p94 | SUPPORTED_WITH_DEFECT |
| C43 | `bb9fc9ab-6abd-44ac-a3f5-b55889d54610` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT |

## 13. Casos materiales dirigidos (sin sumar dominios como hechos únicos)

| Caso | Fuente | Verdad propuesta | Estado actual | Primera pérdida |
|---|---|---|---|---|
| REQUIREMENTS-01 | D01 p15 | Entrega en 60 días naturales desde formalización | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-02 | D01 p15 | DDP nacionales / DAP extranjeros, destino final | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-03 | D01 p15 | Precios fijos, dos decimales y sin IVA al cotizar | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-04 | D01 p16 | Subcontratación no aplica | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-05 | D09 p1 | Suministro conforme a los dos modelos GE y cantidades de la tabla | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-06 | D09 p2 | Contenedor con espuma, ESD y protección contra humedad | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-07 | D09 p2 | Dos juegos de cables de comunicación de cada puerto del relevador | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-08 | D09 p2 | Software libre licencia en USB para Windows10 | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-09 | D09 p2 | Anexar catálogos/fichas/dibujos/boletines del fabricante identificando partidas, marca y modelo | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-10 | D09 p3 | Carta de componentes nuevos, compatibles y ensamble correcto | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-11 | D09 p3 | Compromiso de avisar entrega con48h de anticipación | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-12 | D09 p3 | Marcar bienes con centro de trabajo y contrato, letra>=10mm | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-13 | D09 p3 | Comprometer carta original fabricante y certificados de calidad en entrega | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-14 | D01 p49 | Opiniones positivas SAT/IMSS/INFONAVIT posteriores al fallo con plazo de3 días hábiles | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-15 | D01 p94 | Cotizar total de partidas y conformidad de cada una | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-16 | D01 p32 | Adoptar/mantener programa Pemex CUMPLE o compromiso de implementar propio | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-17 | D09 p3 | Carta compromiso de cumplimiento Formato4 SSPA si resulta ganador | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-18 | D10 p2 | Formato3 de CN, plazo anual y acuse: detalles no conservados por R01 | INCOMPLETE_COMPONENT | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUIREMENTS-19 | D09 p3 | Traducción simple de adjuntos en otro idioma: perdida al cortar R28 | INCOMPLETE_COMPONENT | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-01 | D09 p2 | Catálogos/fichas/dibujos/boletines emitidos por fabricante para oferta | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-02 | D09 p3 | Carta compromiso SSPA de adjudicado | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-03 | D09 p3 | Carta de componentes nuevos/compatibles/ensamble | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-04 | D09 p3 | Manifiesto de compromiso aviso de entrega y marcado | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-05 | D09 p3 | Carta original fabricante con certificados de calidad para entrega | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-06 | D09 p4 | Copia de nota de remisión con descripción/especificaciones | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-07 | D09 p4 | Contrato impreso en2 juegos para entrega | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-08 | D01 p49 | Opinión positiva SAT, etapa posterior al fallo | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-09 | D01 p49 | Opinión positiva IMSS, etapa posterior al fallo | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-10 | D01 p49 | Opinión positiva INFONAVIT, etapa posterior al fallo | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-11 | D01 p82 | Fotografías actualizadas fachada/áreas; R25 sí detecta requisito, no Requested Evidence | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-12 | D10 p2 | Formato3 declaración CN de bienes, no porcentaje mínimo exigido | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-13 | D01 p78 | Cuestionario Anexo3 completo, firmado y escaneado; R02 sólo cubre condición de consorcio | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-14 | D01 p8 | DA-1 manifiesto de interés por plazo del cronograma | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-15 | D01 p87 | Identificación oficial vigente con fotografía y ambos lados | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-16 | D01 p87 | Primera acta constitutiva y última reforma para persona moral | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-17 | D01 p87 | Poder de representante para firmar contrato, cuando aplique | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| REQUESTED_EVIDENCE-18 | D01 p87 | Constancia situación fiscal, distinta de opinión positiva SAT | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |
| SCOPE-01 | D09 p1 | Suministrar relevador F60-U03-HKH-F8L-H6L-M6B-P6B-W7K | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-02 | D09 p1 | Suministrar relevador L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-03 | D09 p2 | Entregar cables de comunicación por puerto | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-04 | D09 p2 | Entregar software de configuración/comunicación enUSB | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-05 | D09 p2 | Embalaje con espuma, protecciónESD y humedad | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-06 | D09 p3 | Marcado con centro de trabajo/número de contrato | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-07 | D09 p3 | Coordinación de recepción mediante aviso anticipado | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| SCOPE-08 | D09 p3 | Documentación acompañante de entrega: carta, nota, fichas, contrato | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-01 | D09 p1 | Marca/fabricante GE MULTILIN | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-02 | D09 p1 | Modelo F60-U03-HKH-F8L-H6L-M6B-P6B-W7K | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-03 | D09 p1 | Modelo L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-04 | D09 p2 | Compatibilidad del software con Windows10 | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-05 | D09 p1 | Norma IEC60255-1:2022, cláusula8 | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-06 | D09 p2 | Protección antiestáticaESD | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-07 | D09 p3 | Dimensión mínima de marcado10mm | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-08 | D01 p15 | Plazo de entrega60 días naturales desde formalización | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-09 | D01 p15 | Precios fijos | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| ATTRIBUTES-10 | D01 p16 | Moneda permitida MXN o USD | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| QUANTITIES-01 | D09 p1 | 1 PZA de modelo F60; confirmación visual independiente D02p1 | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| QUANTITIES-02 | D09 p1 | 2 PZA de modelo L90; confirmación visual independiente D02p1 | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| QUANTITIES-03 | D09 p2 | 2 juegos de cables de comunicación de cada puerto; no inferir número de puertos ni total de cables | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| QUANTITIES-04 | D09 p4 | 2 juegos de contrato impreso; son documentación, no dos relevadores adicionales | MISSING | Native/OCR Scope row recognition:0 candidates; children never called without Scope parent. |
| REQUIREMENTS-20 | D11 p1 | Formatos6y7 sí aplican y deben entregarse5 días hábiles posteriores a la entrega del requerimiento | MISSING | Requirement discovery/segmentation/actor-context or Requested Evidence interpretation remains semantically unchanged; per-record classification inherited after source hash and exact output equivalence. Not attributed to budget without specific evidence. |

## 14. Límite de evidencia y conservación

comparison_ledger.json conserva IDs/fuentes SHA de ambos intentos y campos comparados. grammar_diagnostic.json conserva fuente/generación/row_count. semantic_adjudication.json contiene OCR/llamadas/clasificación/casos. LosPNG y source_review.txt son ayudas nuevas de adjudicación separadas del resultado productivo.

No hay un ledger congelado por cada adapter intermedio: las inferencias de primera pérdida se sustentan en transcripción congelada, evaluación pura de la gramática y código de la cadena de consumo; no en un replay de materialización. No se certifica ausencia universal de errores, contradicciones ocultas o recall.

No se modificaron código, DB, schema, migraciones, configuración, presupuesto, proveedor, pre-freeze, binding, first-pass ni reporte operacional. No hubo OCR/Vision/proveedores, rerun, nueva identidad/Attempt5, stage/commit/push. Adjudicación nueva pendiente de aprobación humana, sin alterar históricos. Los hashes de cierre se registran en adjudication_artifacts.sha256.json y su SHA separado.
