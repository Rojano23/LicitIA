# MVP-06.R.4a — análisis del primer lote real

Starting HEAD: `d399b7a`, main. Análisis únicamente; no cambios a producción, prompts, harness, roadmap ni Golden. Reportes de esta revisión separados y untracked.

**Decisión recomendada: D — corregir primero el harness de calibración, sin nuevas inferencias.** Hay diferencias de percepción reales, pero los contadores actuales confunden saltos de línea, identidad discrepante, fallo de validación y omisión. El experimento estructural también está condicionado por una adaptación incompleta del cliente al contrato de continuidad.

## Artefactos analizados

- `backend/reports/di_r4a_tesseract_b4_p4_transcription.json`
- `backend/reports/di_r4a_vision_b4_p4_transcription.json`
- `backend/reports/di_r4a_vision_b4_p1_p3_structure.json`

Hashes exactos de entradas, Golden y original en `document_intelligence_r4a_first_batch_analysis.json`. Ambos experimentos de transcripción usaron la misma imagen SHA-256 `fd5ad8c67cf8161e76b994dd97d21ccc77fa68bcf52c635e476e4cdc04e6f87b`.
Original B-4 autorizado: documento `acf31750-1d8d-4a0c-910c-fc3743930c57`, Tender `decd32ae-2c1f-4520-89bc-d845c986a7ba`; SHA-256 `5b1ecdcf6ab0ec6a1008bf41554367dc3a917fce2a79b197a5289193362ba311`, verificado contra metadata DB.
Se consultaron el original de cuatro páginas, Golden de cantidades/atributos/semántica, inventario previo, runner Golden 06.2.7, commit `913a4d2`, fixtures y contratos productivos. Las consultas DB fueron READ ONLY. No se ejecutó ningún proveedor.

## Autoridad de las referencias

**GOLDEN-LABELED:** `scope_quantity_golden_v1.json` y `technical_attribute_golden_v1.json`, casos APPROVED de página 4. Sus obligaciones y excerpts autorizados siguen intactos. Cantidades aprobadas: cinco filas de 1 PIEZA, una de 2 PIEZAS, una de 4 PIEZAS y UNA COPIA del reporte. Las aprobaciones no certifican todo el OCR original ni una estructura de páginas 1–3.

**KNOWN HUMAN REFERENCE:** el cierre versionado 06.2.7 documenta continuidad fail-closed y conservación de identidad. No se localizó una referencia humana preexistente que apruebe explícitamente la estructura real completa de B-4 páginas 1–3. Los tests de continuidad son fixtures sintéticos; el runner Golden existente imprime estado observado y no contiene expected labels de página 2 con dos segmentos. Un commit aceptado de arquitectura no convierte outputs Vision persistidos en verdad humana.

**DIAGNOSTIC_ONLY:** lectura visual del original realizada en esta revisión y percepciones históricas del inventario. Permiten documentar discrepancias fuente/observación y proponer revisión, pero no crear Golden truth ni declarar accuracy certificada. Las propuestas nuevas del modelo nunca se toman como referencia.

## Página 4 — comparación semántica

| Elemento / referencia aprobada | Tesseract 5.5.3 | Vision 4B |
|---|---|---|
| Partida / ownership | Página sin etiqueta explícita de partida; no demuestra propietario por sí sola | Texto validado vacío; no demuestra propietario |
| Modelo analógico Golden `AA143-H50/K4400` | `AAI143-H50/K4A00`; discrepancia crítica con Golden, coincide con la lectura ampliada del original | Raw parcial `AA143-H50/K4400`; coincide con Golden, difiere visualmente del original; no validado |
| `ADV159-P00` | Presente, tras salto de línea desde MODELO: | Presente en raw; sin salida validada |
| `ADV551-P60/D5A00` | Presente, tras salto de línea | Presente en raw; sin salida validada |
| `AAR145-S50` | Presente; OCR agrega `|` y líneas vacías entre MODELO: y valor | Presente en raw; sin salida validada |
| `PW481-50` / rango `100-120VCA` | Ambos presentes | Ambos presentes en raw; sin salida validada |
| `EC401-50` / `ESB BUS` | Ambos presentes | Ambos presentes en raw; sin salida validada |
| `S9129FA` / controlador `AFV10D` | Ambos presentes | Ambos presentes en raw; sin salida validada |
| 1 PIEZA × cinco equipos; 2 PIEZAS ESB; 4 PIEZAS baterías | Siete filas y sus cantidades/unidades presentes; necesita revisión de binding antes de confianza | Siete filas/cantidades presentes en raw; no disponibles como datos validados |
| Equipos de cómputo/software, transporte y radios a prueba de explosión | Obligación preservada | Obligación visible en raw, no utilizable como entrada canónica |
| Limpieza y entrega de equipo operando | Preservada; diferencias de acento/puntuación no cambian el sentido observado | Preservada en raw, no validada |
| Reporte profesional, UNA COPIA en medio electrónico | Preservado; UNA y COPIA están separados por newline | Preservado en raw, no validado |
| Sistemas operando a satisfacción de PEMEX; firmas de operativo/coordinador/supervisor | Cláusula completa preservada | Raw termina en `FIRMAS DE RECIBIDO EL`; falta el resto, luego falla todo el JSON |
| Identificadores de documento/referencia | No hay número documental explícito relevante en esta página; B-4 queda identificado por metadata | Igual; no atribuir omisión de un identificador que no aparece aquí |

### Por qué Tesseract contó cinco “material_omissions”

Se reprodujo exactamente la comparación `fragment not in observed.text` sobre los 14 excerpts distintos del esperado almacenado. Ausencias literales:

1. `MODELO: AA143-H50/K4400`: el observado es `AAI143-H50/K4A00`. **IDENTIFIER_ERROR / TRANSCRIPTION_SUBSTITUTION respecto de Golden**, material si se confiara como una equivalencia. La imagen ampliada del original lee `AAI143-H50/K4A00`: hay **discrepancia fuente–Golden pendiente de revisión humana**, no prueba suficiente de error de Tesseract. No se modifica ni rebaja la etiqueta APPROVED.
2. `MODELO: AAR145-S50`: el modelo está presente, pero un `|` espurio separa etiqueta/valor. **TRANSCRIPTION_SUBSTITUTION** del separador / ruido OCR; no es omisión del equipo ni cambio del identificador. Puede afectar un parser de binding y debe conservar revisión.
3. `MODELO: ADV159-P00`: coincide al colapsar whitespace. Artefacto de métrica, sin omisión material observada.
4. `MODELO: ADV551-P60/D5A00`: mismo caso; artefacto de newline.
5. `UNA COPIA`: coincide al colapsar whitespace. No se omitió la obligación ni su cantidad.

Tres diferencias desaparecen usando únicamente comparación de whitespace para diagnóstico, sin modificar texto, identificadores ni Golden. Una es ruido de separador antes de un modelo existente; una es discrepancia crítica fuente/Golden. **Cinco NO significa cinco obligaciones contractuales omitidas.** No se identificó una obligación completa faltante entre estos cinco casos.
Las omisiones del OCR de firmas manuscritas/cargos de aprobación y ruido al final no equivalen a perder la cláusula contractual que exige las firmas del servicio, que sí está íntegra en su texto. No se califica exactitud de nombres personales como métrica de alcance.

### Por qué Vision contó catorce

`runtime_status=FAILED`, `structured_json=null`, `text=""`, warnings `OUTPUT_TRUNCATED`, `DONE_REASON:length`. El JSON termina a mitad de una cadena. El cliente falla de forma cerrada y el runner no promueve raw incompleto a texto canónico. Por ello todos los 14 excerpts resultan ausentes del **texto validado**.

El raw parcial sí contiene las siete filas de equipos, modelos, cantidades y casi todas las obligaciones. Puede leerse para error analysis, pero no persistirse como verdad. Por ejemplo UNA/COPIA está en dos líneas raw; no equivale a ausencia de esa obligación. La cola de la cláusula de firmas sí falta materialmente en el raw recibido.

Clasificación: **OTHER** para fallo/truncamiento de contrato JSON; **TRANSCRIPTION_OMISSION** para la cola material de firmas no recibida; **IDENTIFIER_ERROR / TRANSCRIPTION_SUBSTITUTION** diagnósticos para el primer modelo respecto de la lectura del original. Los otros “14 faltantes” son una consecuencia de indisponibilidad tras validación, no catorce fallos de lectura independientes. No se rescata ni completa silenciosamente JSON inválido.

**Resultado comparativo:** Tesseract supera a Vision 4B en **salida utilizable validada y cobertura de cierre contractual** en este experimento: tiene texto completo y tarda menos. No demuestra superioridad universal ni más fidelidad en cada carácter; el primer identificador tiene una disputa fuente/Golden, y el raw parcial de Vision conserva muchos tokens aprobados sin convertirse en entrada válida.

## Estructura Vision — páginas 1, 2 y 3

| Página | Propuesta raw / normalizada | Original: diagnóstico visual, no Golden nuevo | Evaluación |
|---|---|---|---|
| 1 | Inicio 1, no continuación; raw `1.` normalizado a `1`; open 1 | Inicio visible de partida 1, servicio MTBE 1 | Inicio e identidad local compatibles con fuente. No se certifican todos los flags has_supply/has_deliverable por falta de label. Resultado final REVIEW_REQUIRED |
| 2 | Sólo inicio 2; no incoming ni continuación; raw open null, normalizador propone open 2 | Arriba continúa alcance de partida 1, incluye suministro y entregables; al final comienza partida 2 para Asfaltos | Omite segmento heredado 1 y su cierre/cambio hacia 2. **STRUCTURE_BOUNDARY_ERROR + CONTINUITY_ERROR** diagnósticos; peligro de atribuir suministro de 1 a 2. La detección local del inicio 2 no resuelve toda la página |
| 3 | Inicio 3, sin incoming; raw open null, normalizador propone open 3 | Continúa partida 2; no se observa inicio de partida 3. El número 3 está en el pie de página | **IDENTIFIER_ERROR + STRUCTURE_BOUNDARY_ERROR + CONTINUITY_ERROR** diagnósticos. Posible confusión con número de página, sin afirmar causalidad del modelo |

En la lectura del original, fronteras candidatas: p1 incoming null/outgoing 1; p2 incoming 1/outgoing 2; p3 incoming 2/outgoing 2. Se registran exclusivamente como DIAGNOSTIC_ONLY para revisión humana, sin etiquetas APPROVED nuevas. No se infiere cierre contractual completo porque el raw del proveedor diga open null; el normalizador también deriva claves abiertas y nuevos items, hechos que deben diferenciarse de percepción literal.

El inventario histórico observaba p2 sólo continuación 1 y p3 continuación 2: también carecía del segmento que prueba transición a 2 en p2. Su estado RESOLVED no lo convierte en Golden. El manifiesto de fase 1 llamó a T05 “Continuation candidate” y dejó todo sin etiqueta estructural aprobada; esta revisión demuestra que esa descripción no cubría la página entera.

### Brecha específica del harness estructural

`execute()` llama directamente `OllamaVisionAssistClient.analyze_structure_scope_page()` y después `adapt_structure_scope_005_page()`. El payload del cliente no incluye `_continuity_state_quality`. El adaptador requiere explícitamente VALID; si falta, lo marca UNKNOWN, review=true y elimina outgoing.
La capa de servicio existente añade esa metadata bajo su política de continuidad; el runner se la salta. Por tanto las tres páginas resultan UNKNOWN y no se transporta contexto: `previous_page_context=null` en las tres solicitudes. Esto **no prueba que la percepción del modelo haya provocado por sí sola los tres UNKNOWN**.
La prueba mock del runner suministró manualmente `_continuity_state_quality=VALID`, que el cliente directo real no emite. Cubrió una condición distinta de la interfaz real. Es una brecha de integración del harness, no motivo para cambiar dominio/routing productivo ni asignar VALID a ciegas.

Con el harness actual no hay carry viejo (todas las fronteras UNKNOWN/outgoing null). En un replay que promoviera ingenuamente las propuestas habría identidad/ownership erróneos de p2/p3; esto no es evidencia de que R.2/R.3 productivo los confiaría, pues el replay no ocurrió. No confundir identidad errónea nueva con carry de estado viejo.

### Motivo de labeled_observations=0

**A, para las referencias inspeccionadas:** no hay Golden de estructura real aprobado y conectado al evaluator. El lector actual sólo reúne excerpts aprobados de cantidades/atributos de p4; no hay referencia de estructura para p1–p3. No se localizó label humano estructural preexistente que permita afirmar B.
También existe una brecha de capacidad del harness para incorporar futuras referencias humanas estructurales, pero no es correcto activarla a partir de esta salida Vision ni del diagnóstico visual de esta revisión. El defecto de metadata descrito arriba es independiente de la ausencia de etiquetas.

## Seguridad y calidad

- Percepción: Tesseract conserva texto utilizable y las obligaciones inspeccionadas; Vision transcription falla validación; estructura p2/p3 contiene discrepancias visuales importantes.
- Seguridad de adquisición: ambos textos y las tres estructuras quedan REVIEW_REQUIRED; raw inválido no se vuelve entrada canónica. Dos safe misses / correct_review_required según métricas originales. La marca review del runner es incondicional, por lo que no prueba que haya detectado las causas específicas.
- Unsafe trusted contractual errors observados: **0**; domain_trust_assessed: **0**, unassessed: **5**. No hubo materialización de dominio ni evaluación de confianza posterior: el cero no certifica producción.
- Stale carry observado: **0**, con las tres fronteras UNKNOWN y sin clave saliente. Parte de ese resultado se debe al defecto de adaptación; no certifica continuidad percibida correcta.
- Active observations=3 describe presencia de artefactos, no aciertos estructurales. Precisión/recall siguen sin certificación.

## Viabilidad operacional medida

| Solicitud | Latencia registrada |
|---|---:|
| Tesseract p4 | 1,549 ms / 1.549 s |
| Vision transcripción p4 | 86,592 ms / 86.592 s |
| Vision estructura p1 | 35,825 ms / 35.825 s |
| Vision estructura p2 | 35,638 ms / 35.638 s |
| Vision estructura p3 | 36,923 ms / 36.923 s |

Estructura: suma de latencias 108.386 s; no es wall time total de proceso. Vision tiene timeout configurado 180 s; no hay timeout reportado. Transcripción terminó por límite de salida, no por timeout. Estructura: done_reason=stop, HTTP 200, eval_count=156/157/147, prompt_eval_count=2626 por página, max_output_tokens=600.
Transcripción truncada no conserva counts de tokens/meta completos; el default de código 1000 tokens no debe presentarse como medición del número realmente generado.
No se observan marcadores de retry; el camino DONE_REASON:length retorna FAILED antes de reintentar. Sin contador general ni logs de cada intento no se certifica un registro exhaustivo de retries. No se registró load_duration, separación de carga de modelo, render time ni elapsed completo del CLI. No se estiman.

## Replay: posible con adaptación controlada, todavía no listo para ejecutar

Los archivos permiten replay **sin llamar nuevamente al proveedor**, pero no son artefactos ORM productivos listos para importar. Dev sigue en `20261012_alt_compliance_071`; producción R.2/R.3 de Requirements requiere 072. No se aplicó migración ni se escribió estado dev.
Plan acotado condicionado a la corrección del harness:

1. Usar fixture propietario en licitia_test migrada a 072, con copia mínima del original/metadatos de B-4 y páginas 1–4, sin copiar ni tocar decisiones humanas aceptadas de dev. No resets destructivos ni segunda base improvisada.
2. Mapear Tesseract a PageOcrResult/NormalizedContent por contrato productivo, conservando proveedor/versión/idioma/texto/locator. Mapear Vision structure a artefactos válidos de tareas existentes mediante la política de wrapper/continuidad aceptada; retener raw original y distinguir campos derivados. No declarar fidelidad RELIABLE sólo por COMPLETED.
3. Vision transcription fallida permanece FAILED: conservar raw/warnings para auditoría y texto no utilizable. No parsear rescate para fabricar detalle válido.
4. Derivar neutral DI y comparaciones R.3 con evidencia disponible actual. El inventario existente tiene OCR/Vision históricos: conservar fuentes independientes y lineage, sin usar timestamps o el artefacto más nuevo como ganador contractual. Usar identidades explícitas de run/task/proveedor: `external:imageSHA` coincide entre proveedores y no identifica una generación independiente por sí solo.
5. Ejecutar discovery/normalization de Requirements y requested Evidence sólo donde el motor detecte obligación del licitante; esta página contiene alcance de ejecución y no debe forzarse a producir requisitos de oferta. Ejecutar materializadores Scope/continuidad/quantity/attribute con adapters existentes. Si OCR detail no tiene adapter semántico productivo predeterminado, registrar la capacidad ausente y no inventar uno ni sustituirlo por raw LLM canónico.
6. Verificar provenance, review local, conflictos, ausencia de ownership confiable en fronteras inciertas, cantidades/atributos sin cruce de identidad. Repetir y comparar IDs/semantic keys/review/provenance. Aislar también las sesiones que el orquestador abra internamente; rollback de una sola sesión no basta. Sin llamadas de adquisición/Ollama y sin commits a dev.

No se ejecutó este plan. Antes del replay hay que corregir la adaptación/medición para interpretar correctamente las mismas salidas almacenadas.

## Brechas de métricas y decisión siguiente

1. Ausencia de substring exacto se llama material_omissions: mezcla newlines, ruido OCR, sustitución de identifier y texto verdaderamente ausente. Etiquetas de binding/identificador/quantities no se cargan a sus dimensiones respectivas; los 14 excerpts deduplicados pierden multiplicidad de filas.
2. FAILED/null structured_json se mide como catorce omisiones de percepción; debe distinguir indisponibilidad contractual de salida y diagnóstico raw no canónico.
3. Metadatos estructurales de wrapper no incluidos en la ruta del cliente directo: UNKNOWN artificial, contexto perdido; el test mock ocultó la brecha.
4. Identifiers/critical_tokens/domain impact externos vacíos: sus ceros no prueban fidelidad. No existe confianza de dominio evaluada.
5. Referencia fuente–Golden del primer modelo requiere decisión humana; no resolverla cambiando Golden ni normalizando caracteres críticos.
6. Raw original, payload normalizado y claves derivadas deben evaluarse separadamente; el normalizador agregó new_items/open y recortó anchors.
7. Falta telemetry de carga/render/tiempo completo y una identidad independiente del run. No atribuir overhead sin dato.

**Única siguiente acción: D — corregir harness primero y reanalizar este lote sin nuevas inferencias**, con pruebas que reproduzcan payloads reales (sin la metadata que el cliente no entrega), separando error de validación, diferencia de whitespace, discrepancia de identificador y diferencia material. Conservar Golden y runtime productivo. El desacuerdo fuente–Golden debe seguir visible para revisión humana, sin etiquetas nuevas.

Cambios productivos recomendados ahora: **NO**. Prompt tuning: **NO**. Nueva corrida real: **NO**. Wiring de estructura aprobado: no efectuar todavía; no existe etiqueta preexistente verificada para hacerlo en este análisis. No se modifica el harness en esta tarea.

## Integridad y Git

Golden de semántica/cantidades/atributos coincide con hashes congelados del manifiesto; original PDF coincide con hash DB. Tender #002 no se inspeccionó, buscó ni seleccionó. No se ejecutaron modelos adicionales ni replay mutante. No tests de implementación ni migraciones, pues esta tarea sólo analiza y escribe los dos reportes nuevos. Todos los cambios previos se conservaron. Sin stage/commit/push. Se verifica git diff --check, diff --stat y status --short al entregar.

MVP-06.R.4a FIRST REAL-MODEL BATCH ANALYZED — READY FOR CALIBRATION DECISION
