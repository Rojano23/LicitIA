# MVP-06.V — Attempt #7: adjudicación semántica final y diagnóstico IR

**Conclusión: NOT READY FOR UAT.** V.6c corrige la separación operacional entre
percepción e interpretación, pero no se demuestra salida material útil de Scope,
Attributes o Quantities. El principal rechazo ocurre antes del candidato, por
contrato de representación/entrada de reconstrucción. No es un fallo demostrado
de DB, dedup, grounding final o child materializer.

## 1. Decisiones separadas

| Eje | Decisión | Alcance |
|---|---|---|
| Operational Integrity | PASS | Freeze/corpus/código/históricos íntegros |
| Safety | CONDITIONAL PASS | V.4a mantiene abstención; propuestas Vision crudas incorrectas y fidelidad parcial no certificadas |
| Perception Selectivity | CONDITIONAL PASS | Frontera V.6c demostrada, muestra respalda evitación; necesidad espacial no probada en todos los planes |
| Structured Interpretation | FAIL | IR0 y Scope/Attributes/Quantities0 pese a contenido material disponible |
| Semantic Quality | FAIL | Omisiones materiales y defectos/contextos en rutas separadas |
| UAT Readiness | NOT READY | Capacidad central anunciada ausente; no reducción implícita de alcance |

Esta es una evaluación de Codex solicitada por el usuario, pendiente de aceptación
arquitectónica/humana; `approved_by_human=false`. El usuario dirige el uso de los
límites inferiores previos. Los archivos previos conservan su autoridad propuesta,
no se transforman en HumanTruth aprobada ni se persisten decisiones de dominio.

## 2. Integridad y método

Run `06v7_eee8df9b4a1f44428531dbae0c236a1d`; HEAD `429bf2ff95043c6d74af379a22d85bdd85843340`.
First-pass SHA-256 `90196c185f2083d3136c8c391048feebbf215d11355c563518ba06713b735fe2`.
Pre-freeze003, binding, FROZEN y summary verificados, corpus11/11 idéntico a Attempt4
por filename/hash/size/MIME, incluido .DS_Store; originales dentro del root aislado.
Se verificaron1660archivos históricos y1351archivos existentes de Attempt7/
bootstrap/root antes de adjudicar; el cierre vuelve a compararlos.

Sólo nuevos artefactos bajo semantic_adjudication/. Se leyeron snapshots/recibos
y fuentes locales. La DB se consultó con SET TRANSACTION READ ONLY. Se evaluaron
funciones productivas puras de reconstrucción/planning y adapters de sólo lectura;
NO se invocaron materializadores, persistencia de manifests, OCR, Vision, clientes
HTTP, pipeline ni nuevos intentos. Los renders PDF son ayudas de lectura, no nuevas
percepciones productivas.

Se revisaron fuentes materiales B-1pp1–4, catálogo y SSPA p1, plantillas de Bases
pp110–111, antiguos falsos trusted, y muestra dirigida de15páginas/60tareas.
No lectura semántica exhaustiva de253páginas, ni muestra probabilística, ni recall
global. Los límites8Scope/10Attributes/4Quantities son casos dirigidos que pueden
solaparse; no se suman como obligaciones independientes.

## 3. Requirements: igualdad real y diferencia de ocurrencia primaria

31Requirements, todos REVIEW_REQUIRED. Comparación con Attempt4 por fuente SHA,
página, canonical_text, categoría, requirement_text y excerpt primario:
**30exactamente iguales;1difiere**. R04 cambia la ocurrencia primaria de la misma
exención DA-5 de Basesp41 a p89 y cambia capitalización. Se revisó p89: sigue siendo
Manifiesto de Confidencialidad y criterio de no desechamiento; no obligación
positiva autónoma. No se heredó ciegamente una cita de p41 como si fuera p89.

Los candidatos de ambas ocurrencias tienen el mismo score antes del último
componente UUID (1,1,1,1,1,88). `_candidate_quality_score` y max(group,...)
permiten variar primary por UUID en el empate. Es una limitación previa de selección
primaria de Requirements, separada de V.6b/V.6c; no evidencia de mejora semántica
ni razón para ampliar el siguiente fix IR a esta ruta.

Tras comprobar fuente/contexto se mantienen15sustentados,8sustentados con defectos
y8contextuales/no autónomos. Siguen existiendo encabezados como requisitos,
referencias sin antecedente, truncaciones y obligaciones del redactor/convocante
confundidas con requisitos autónomos. Todos conservan review.

| Caso heredado | Fuente SHA abreviado/página actual | Juicio |
|---|---|---|
| R01 | e0958d05fb p1 | Sustentado con defectos |
| R02 | 7ffad7029c p78 | Sustentado |
| R03 | ee9dabcabf p15 | Contextual/no autónomo |
| R04 | 7ffad7029c p89 | Contextual/no autónomo |
| R05 | 7ffad7029c p50 | Sustentado con defectos |
| R06 | 7ffad7029c p18 | Sustentado |
| R07 | 7ffad7029c p9 | Sustentado |
| R08 | 7ffad7029c p97 | Contextual/no autónomo |
| R09 | 7ffad7029c p72 | Sustentado con defectos |
| R10 | 7ffad7029c p9 | Sustentado |
| R11 | 7ffad7029c p18 | Contextual/no autónomo |
| R12 | 7ffad7029c p19 | Sustentado |
| R13 | 7ffad7029c p19 | Sustentado |
| R14 | 7ffad7029c p19 | Sustentado |
| R15 | 7ffad7029c p87 | Sustentado |
| R16 | ee9dabcabf p54 | Contextual/no autónomo |
| R17 | 7ffad7029c p19 | Sustentado con defectos |
| R18 | 4c5c097190 p2 | Contextual/no autónomo |
| R19 | 7ffad7029c p9 | Sustentado |
| R20 | ee9dabcabf p15 | Contextual/no autónomo |
| R21 | 7ffad7029c p21 | Contextual/no autónomo |
| R22 | 7ffad7029c p20 | Sustentado |
| R23 | 7ffad7029c p100 | Sustentado con defectos |
| R24 | 7ffad7029c p93 | Sustentado |
| R25 | 7ffad7029c p82 | Sustentado |
| R26 | 7ffad7029c p96 | Sustentado |
| R27 | 7ffad7029c p9 | Sustentado |
| R28 | 4c5c097190 p3 | Sustentado con defectos |
| R29 | 7ffad7029c p94 | Sustentado con defectos |
| R30 | 7ffad7029c p50 | Sustentado con defectos |
| R31 | 7ffad7029c p19 | Sustentado |

comparison_ledger.json conserva ambos IDs, páginas y textos; semantic_adjudication.json
conserva cada evaluación y fuente exacta. No se presenta15/31 como recall del expediente.

## 4. Los43 candidatos: presencia no equivale a normalización

El multiconjunto de43candidatos coincide exactamente con Attempt4 por fuente SHA,
página, requirement_text y source_excerpt. Se revisaron las43ocurrencias, no sólo
sus conteos.37tienen soporte de excerpt normalizado y vínculos a31Requirements;
6quedan sin vínculo y `candidate_perception.active=false`.

Los6excerpts limpiados eliminan más que whitespace:1.1. del encabezadoB-1,
por el en DT-9p94, guion en consorciop54, viñeta en constanciasp49, su en
propuesta españolp93 y de la en documentaciónp88. El contenido base existe en
la fuente, pero esos excerpts no son citas literales exactas. El guard los excluye
de normalización; NO son6Requirements falsos aceptados. Cinco expresan contenido
sustentado con defecto de fuente y uno es encabezado contextual.

Las37ocurrencias enlazadas heredan15sustentadas/13con defectos/9contextuales
por grupo, incluyendo repeticiones. Estos conteos de ocurrencias no sustituyen
los15/8/8de Requirements únicos. El ledger incluye los6no normalizados y su causa.

## 5. Requested Evidence

8outputs:1adecuado,5incompletos/mal tipados,2contextuales. Todos los8coinciden
exactamente con Attempt4 en fuente SHA/página/tipo/descripción/excerpt y siguen
REVIEW_REQUIRED. Sobres/paquetes no individualizan documentos; el certificado
queda cortado en A.C.; una instrucción de contrato modelo no completado no prueba
adopción contractual.

| Caso | Fuente | Juicio | Evaluación |
|---|---|---|---|
| E01 | p19 | Contextual | Mecánica de sobres, no documento autónomo. Solapa paquetes E02/E04/E06/E08; no contar como cinco documentos distintos. |
| E02 | p19 | Incompleto/mal tipado | Propuesta económica real. Descripción cortada antes de referencia completa; falta DE-1 y sus campos. FORM sólo cubre el componente de formato, no todo el paquete. |
| E03 | p15 | Contextual | Mención/instrucción de modelo con Anexo en blanco. La obligación real de DT-1 condicional se sustenta en D01 pp16/93, no en haber completado ese espacio de D05. |
| E04 | p20 | Incompleto/mal tipado | Documentación DD real, pero FORM es demasiado estrecho para paquete de documentos. Omite inventario DD-1…DD-14 y condiciones. |
| E05 | p87 | Adecuado | Documento DA-3 realmente requerido; página y fragmento correctos. Registro genérico DOCUMENT válido; anexos específicos no se materializan por nombrar el formato. |
| E06 | p19 | Incompleto/mal tipado | Paquete comercial real; FORM es demasiado estrecho. Corte pierde D-1 y no enumera documentos exigidos. |
| E07 | p50 | Incompleto/mal tipado | CERTIFICATE sí corresponde al certificado e.firma, pero “EMITIDO POR EL A” está truncado y no identifica SAT/A.C. ni certificado completo. |
| E08 | p19 | Incompleto/mal tipado | Propuesta técnica real; texto cortado y sin lista DT-9, DT-11, catálogos/cartas. No considerar una evidencia satisfecha por existencia de este registro. |

V.6b/V.6c no corrigen esta ruta independiente. Se mantienen los misses dirigidos
previos sobre fuentes idénticas; no se inventa recall exhaustivo. El caso de
Formatos6/7 sigue sin representación útil pese a OCR disponible. No se atribuye
a budgets sin evidencia específica ni se incluye en el fix de tablas Scope.

## 6. Scope, Attributes y Quantities

Persistidos0/0/0. Los8casosScope,10Attributes y4Quantities dirigidos continúan
materialmente ausentes. material_case_ledger.json añade22casos con fragmentos
literales y offsets sobre la transcripción congelada actual; la asociación
semántica es de adjudicación humana/asistida, no un IR productivo inventado.

B-1p1 y catálogo confirman1PZA F60 y2PZA L90 con marcaGE MULTILIN. B-1p2
contiene2juegos de cables por puerto, softwareUSB/Windows10 y protección de
embalaje; p3aviso48h y marcado mínimo10mm; p4contrato impreso2juegos. No
inferir número de puertos, multiplicar cables ni convertir2juegos de contrato
en equipos. Basespp15–16 conservan60días desde formalización, precios fijos y
monedas permitidas.

## 7. V.4a: seguridad estructural

Basesp13 es índice de reglas y Cuestionariop12 es formulario de integridad.
Ambos antiguos falsos TRUSTED siguen REVIEW_REQUIRED, continuidadUNKNOWN y
outgoing_item_key=null, comprobados por fuenteSHA/página e imagen.
Attempt7 tiene0estructuras trusted en253páginas, por lo que no introduce nuevos
TRUSTED estructurales sin soporte. Scope0 tampoco contiene owners confiados falsos.

Sin embargo, las propuestas Vision crudas sí contienen errores:107478de iniciativa
como partida en SSPA; L90 con LLH en lugar de HLH en catálogo. La segunda anchor
no es fiel al modelo visible. Source IDs, documento/página/región y hashes son
válidos: provenance física correcta no valida una interpretación ni una cita cruda.
new_items incluye review_required=false derivado, mientras segmentos/routing
conservan revisión. No se promovieron esos owners.

No se observaron fuentes/documentos inventados en los registros examinados ni
confianza de fidelidad automáticamente certificada. Los6candidatos con excerpts
limpiados están excluidos de la normalización. Safety CONDITIONAL PASS por
abstención comprobada con límites de fidelity/semántica; no certificación universal
de toda propuesta o toda página.

## 8. V.6c: muestra real de los996planes suficientes

Se seleccionaron estratos de forma/documento: tabla, prosa técnica, reglas globales,
índice, cuestionario, formato, modelo y convocatoria.15páginas de6documentos,
4tareas por página=60decisiones. Se recomputó sólo el plan, en lectura, y sus60
identidades coinciden con eventos congelados originales SUFFICIENT+UNRESOLVED,
sin OCR. No se reconstruyó el pipeline ni se adquirió nada.

| Clasificación primaria | Casos dirigidos |
|---|---:|
| Correct avoidance | 46 |
| Interpretation limitation | 13 |
| Perception actually insufficient | 0 identificados en esta muestra |
| Ambiguous | 1 |

Los13casos tienen contenido disponible que la interpretación acotada no convierte.
El ambiguo es STRUCTURE en B-1p1: celdas legibles, pero relaciones por fila no
representadas en la entrada. No se equipara suficiencia textual con certificación
espacial. No se publica46/60como precisión global ni se afirma que los996casos
son todos correctos. planner_sample.json conserva selección, evento, plan, task,
estado y nota de cada caso.

Los10planesOCR corresponden a4páginas con brecha textual real:SSPA/catálogo
Native vacío y Bases110/111sólo con membrete. No son una repetición de adquirir
B-1p2/p3por grammar failure. En los8planesVision hay4preguntas sobre grids/
catálogo y4sobre plantillas de prosa:estas últimas tienen brecha textual real,
pero no queda demostrado un requisito espacial independiente por su contenido.
Además STRUCTURE_SCOPE de compra no es una tarea bien ajustada al gridSSPA.
La autorización espacial explícita del perfil explica elegibilidad operacional;
no demuestra por sí misma necesidad semántica.

La invariancia crítica sí se verifica: interpretación UNRESOLVED por sí sola no
produjo llamadas desde planes SUFFICIENT. Selectivity CONDITIONAL PASS: mejora
real, sin precisión global inventada ni certificación de todas las preguntasVision.

## 9. Cuatro OCR: contribución y fidelidad

| Fuente | Valor nuevo | Límite | Consumo estructurado |
|---|---|---|---|
| SSPA p1 | Formatos6/7 y5días hábiles tras entrega del requerimiento | Códigos romanos dañados; comentario separado de su fila | OCR activo visto por adapter; IR0; Req/Evidence sin cambio |
| Catálogo p1 | Modelos/marca/PZA y1/2 | Pierde números de partida y binding por fila | OCR activo visto; IR0 antes de candidato |
| Bases p110 | Cuerpo de modelo carta créditoStandby ausente en Native | Fragmentos materiales de compromiso/monto/condiciones omitidos o corruptos | Texto útil para revisión; no nueva partida por ser plantilla |
| Bases p111 | Prórroga por cierre de banco y cierre de plantilla | Omite jurisdicción y parte de referenciaISP98 | No afirmar fidelidad completa ni aplicabilidad automática |

Son4adquisiciones físicas,10completedincluyendo6reuses. Las2últimas aportan
texto nuevo respecto de Attempt4; no certifican una garantía emitida ni crean
automáticamente documentos exigibles al participante. Los4OCR tienen canonical
source/generation/offsets válidos y se les ofrece a la ruta de reconstrucción.
Percepción tuvo éxito parcial; interpretación no convirtió tablas ni resolvió
las obligaciones. Texto lexicalmente suficiente no garantiza completitud OCR.

## 10. Cuatro llamadas Vision

| Evento /fuente | Tarea | Resultado | Evaluación |
|---|---|---|---|
| guard-4 SSPA p1 | STRUCTURE_SCOPE | COMPLETED,44,270ms ledger | Confunde No.de iniciativa107478con partida; no semánticamente útil como catálogo |
| guard-6 SSPA p1 | DETAIL_TRANSCRIPTION | TIMEOUT,60,035ms | Sin detalle validado |
| guard-8 SSPA p1 | DETAIL_TRANSCRIPTION retry | TIMEOUT,60,026ms | Sin detalle validado; fingerprint agotado |
| guard-145 Catálogo p1 | STRUCTURE_SCOPE | COMPLETED,45,418ms ledger | Filas1/2útiles como cues; modeloL90HLH se altera aLLH; requiere revisión |

Tiempos ledger incluyen wrapper; payloads conservan processing_time ligeramente
distinto. No se confunden ambas mediciones. Los fallos nuevos son TIMEOUT; no se
hereda la truncación observada en Attempt4. No hay raw responses completos de los
fallos para evaluar contenido; no se inventan causas JSON o texto parcial.

Las2salidas completadas son STRUCTURE, no DETAIL_TRANSCRIPTION. El adapter de
Scope exige el contrato de detalle y no soporta esas fuentes como detalle: es
separación correcta de capacidades, no ausencia accidental de una invocación.
No convertir anchors o roles de estructura en citas/rows de detalle. El budget
se consumió antes de detalle de catálogo/plantillas; no recomendar aumentarlo
sin separar ajuste de tarea y fallos de proveedor.

## 11. Por qué IR permanece en0: cadena y predicado exactos

Ruta revisada: _extract_pdf_pages(get_text(text)) → DocumentPage.text →
_normalize_text → NormalizedContent → PersistedPerceptionArtifact(text, id,
source_type, source_scope) → source_text → reconstruct → candidato → manifest →
reconciliación → persistencia. El payload Native/OCR no conserva words/cells/
header relations ni geometría por palabra; regionesIMAGE no equivalen a celdas.

255fuentes textuales activas (251Native+4OCR) dan0legacy procurement_rows y0IR
en funciones productivas puras. Se comprobó el contexto real/adapters de9fuentes
B-1/OCR:soportados,0legacy candidates. El código de adapt_and_persist...111–126
activa el puente estructurado cuando no hay candidatos legacy. No se llamó ese
wrapper porque puede escribir manifests; el diagnóstico usa source_text/reconstruct
y adapters de sólo lectura, con sus entradas exactas preservadas. El original
no guarda ledger por invocación; esto es evidencia de código/replay acotado, no
un contador histórico fabricado.

**Primer rechazo mecánico en la tabla Native:**

- structured_evidence.py:148no encuentra pipe/tab en la línea19 Partida.
- L149–154:cells=[],roles=[]; no header con item/description/quantity/unit.
- Líneas20–23contienen Descripción /Unidad de /Medida /Cantidad, cada una aparte.
- Línea24contiene1; línea25descripción; líneas29/30PZA/1. No son una row delimitada.
- L173–176:el fallback _ITEM rechaza Partida sin número en la misma línea y luego
  1/2sin prefijo; continúa sin crear bloque. **Cantidad/unit validation, manifest
  grounding y materializers nunca reciben este caso.**

B-1p1 tiene63líneas no vacías tanto en raw como normalized,0pipes y0tabs desde
raw. _normalize_text no borró una tabla delimitada ni fusionó aquí todas las líneas
en un párrafo:la representación relacional no se suministró desde extracción.
Fuente exacta de entrada SHA2a94f5cbedba2bae0f327c511dae8f97ef3c1f138aac642d8beeee0e910d1e95
en reconstruction_inputs/D09_p1_NATIVE.txt.

Incluso tras construir filas fieles, los headers partidos Unidad de Medida y
labels FABRICANTE/MARCA /NUMERO DE PARTE no son las etiquetas simples inyectadas
en losfixtures. Son propiedades genéricas de representación/header mapping, no
reglas por palabras de este Tender. La rama table admite noun descriptions como
OTHER/review; el action predicate no es el primer fallo en esa tabla. No corregir
esto relajando identidad hasta aceptar todo número de sección.

## 12. Synthetic-vs-real y trazas

SI/MG positivos inyectan mediante norm() un texto ya serializado:
`Partida | Descripción | Cantidad | Unidad | Marca | Modelo` y una fila por línea,
o ITEMrotulado +acción inmediata +continuaciones indentadas. Validan interpretación,
spans, manifests y propiedad bajo esa forma; no acreditan conversión de un PDF
real a esa forma. La integración de test usa servicios reales después de una
fuente sintética preformateada, sin demostrar extracción geométrica previa.

En real, get_text(text) devuelve encabezados/celdas por separado y su orden de
objetoPDF; en p4incluso3.3/3.4aparecen después de metadata de firma pese a estar
arriba visualmente. OCR suministra plain text, no TSV/word geometry.
EvidenceSource tiene identidad/provenance válida pero no geometría que permita
recrear relaciones por proximidad con certeza. **SI11 ya rechaza a propósito
fragmentos aplanados sin relaciones demostradas. Esa seguridad debe conservarse.**

La integración sí alcanza la entrada textual. La brecha es de contrato
real-source→relacionesIR y cobertura de reconstrucción, no engine que nunca
se llama ni field type corrupto/normalización de offsets incorrecta.

### T1 — D09 B-1 p1, tabla de equipos

**Fuente → evidencia normalizada:** Modelos F60/L90, GE MULTILIN, PZA y cantidades1/2 visibles. Native conserva texto pero no cells/words/bboxes en payload. 63 líneas no vacías antes/después; cero pipes/tabs antes y después. No pérdida de saltos causada por normalización.

**Reconstrucción, primera pérdida:** structured_evidence.py:148–154: delimiter=None -> cells=[] -> header no establecido. p1 líneas19–23 son encabezados separados. L173–176 rechaza Partida sin número y luego1/2 sin prefijo; no se llega al validador de cantidades.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. Unidad de Medida es header partido y distinto de alias simple unidad; FABRICANTE/MARCA y NUMERO DE PARTE no son los field labels de fixtures. La rama table acepta noun description como OTHER/review; el verbo de acción no es el primer bloqueo aquí.

### T2 — D09 B-1 p2, accesorios/embalaje

**Fuente → evidencia normalizada:** Referencia Para la partida01y02; 2 juegos por puerto, softwareUSB Windows10, ESD/humedad. Prosa y numerales de sección preservados, sin indentación relacional ni anchor ITEM nuevo.

**Reconstrucción, primera pérdida:** No header delimitado; _ITEM.match no acepta Para la partida... ni Cada relevador.../Deberá entregarse... como boundary de nuevo item. El requerimiento depende de referencia a owners existentes, no de fabricar un ítem1.2.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. Sin block no hay fields provisionales; cantidades por puerto no permiten inferir número de puertos ni total de cables.

### T3 — D09 B-1 p3, marcado/aviso

**Fuente → evidencia normalizada:** 48h de aviso y marcado de centro/contrato con10mm aparecen literalmente. 2.7 y viñetas conservados como texto; son secciones, no identidad de partida.

**Reconstrucción, primera pérdida:** Header no reconocido y _ITEM anclado no acepta sección/viñeta con referencia a bienes existentes. No se ejecuta binding de atributo10mm.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. 

### T4 — D09 B-1 p4, documentación/2juegos

**Fuente → evidencia normalizada:** 3.4 Contrato impreso (2juegos), documentación y fichas visibles. get_text(text) entrega3.3/3.4 después de firma/metadata aunque visualmente están arriba; normalizer conserva ese orden.

**Reconstrucción, primera pérdida:** No fila ni ITEM rotulado; 3.4 es sección. Se pierde en segmentación/entrada antes de fields cantidad/unidad, no en persistir el hijo.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. 

### T5 — D02 catálogo p1, imagen/OCR

**Fuente → evidencia normalizada:** Native vacío; OCR recupera descripciones y paresPZA1/PZA2 pero pierde ids de fila y asociación espacial. OCR activo/normalizado, offsets NORMALIZED_TEXT e identidad de generación validados; no word/cell geometry.

**Reconstrucción, primera pérdida:** Header Partida Descripción Medida separado/incompleto, sin delimitador; _ITEM no puede ligar números ausentes. Vision reconoce1/2 en STRUCTURE pero ese contrato no aporta literal detail ni valida row-to-value relationships.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. No unir automáticamente anchors Vision a cantidades OCR por proximidad. La lectura visual humana confirma1PZA F60/2PZA L90, con provenance separada.

### T6 — D11 SSPA p1, grid de aplicabilidad

**Fuente → evidencia normalizada:** Formatos6/7 y cinco días hábiles después de entrega del requerimiento, no necesariamente de bienes. OCR pone comentario de plazo antes de Formatos6y7; columnas sin relación tipada.

**Reconstrucción, primera pérdida:** Tabla no procurement item/description/quantity/unit; los roles de la fila no satisfacen el esquema. Vision107478 confunde iniciativa con partida. STRUCTURE no se convierte en detalle.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. Obligación pertenece a Requirements/Requested Evidence. IR Scope0 en esta forma no demuestra por sí mismo defecto de Scope ni autoriza ampliar ese engine.

### T7 — D01 Bases pp15–16, condiciones globales

**Fuente → evidencia normalizada:** 60días desde formalización, precios fijos y moneda permitida existen en Native. Texto suficiente y fiel para revisión; fuente literal/provenance disponible.

**Reconstrucción, primera pérdida:** Reconstrucción sólo entra mediante item local; numerales2.1/3.1/3.2 no constituyen ítems. El Core sí permite TENDER_WIDE; no existe puente de estas condiciones al bloque actual.

**Candidate → grounding → materialization:** 0 → NOT_REACHED → 0. Persistir un Scope padre de equipos no descubre por sí solo atributos de plazo/precio/moneda; vocabulario child por defecto también acotado.

## 13. Efecto padre e hijos

El harness151–171recorre children sólo sobre ScopeDetails persistidos; con0Scope
no entra a esos materializadores para el Tender. Pero **no es la única causa**:
IR0significa que ni siquiera existen fields provisionales de marca/modelo/
cantidad/unidad en bloques. No hubo evidencia de hijos perdida dentro de su
persistencia ni rechazo independiente de ownership que explicar.

Además, StructuredAttributeAdapter206–220sólo extrae brand/model y
StructuredQuantityAdapter223–243requiere pareja explícita quantity/unit y
valid_scope_identity. Windows10/ESD/norma10mm/plazo/precio/moneda no aparecen por
el simple hecho de que nazca un padre. Cantidades2juegos en prosa no se vuelven
campos rotulados por sí solas. Hay límites adicionales de reconstrucción/vocabulario/
aplicabilidad; no culpar al child materializer sin que la evidencia lo alcance.
El Core admite TENDER_WIDE; el reconstructor actual inicia sólo desde un item local.

## 14. Conflictos6→2

Los6conflictos anteriores eran diferencias Native/OCR en B-1pp2/3,
Convocatoriapp1–3 y Basesp51. Esas6páginas dejaron de adquirirse. Se conserva
su contenido Native y los casos revisados no demuestran pérdida del núcleo
material; p51es ejemplo de certificado, no certificado del participante.

Los2nuevos son Bases110/111:membrete Native vs cuerpo OCR de regiónimagen.
Son coberturas complementarias, no2contradicciones contractuales confirmadas.
Por tanto reducción de conteo se explica por conjunto de adquisiciones distinto
y eliminación de algunas comparaciones redundantes; no demuestra mejor resolución
de conflictos ni que menos conflictos sea intrínsecamente mejor. La evidencia
adicional recuperada tiene valor pero sigue parcialmente infiel.

## 15. Clasificación y siguiente acción mínima

| Problema | Clasificación |
|---|---|
| CeldasNative sin relaciones que el parser presupone | source representation/normalization boundary +reconstruction |
| Fallback IR no invocado | No demostrado; ruta conectada |
| Prosa/referencia existente/globales fuera de entrada local | reconstruction/identity gate/limitación esperada del contrato actual |
| OCR sin fila/wordbindings y con texto incompleto | perception +representación de fuente |
| Vision107478/HLH→LLH y timeouts | provider/fidelidad/identity role; protegido por review |
| Prosa de plantillas con preguntaVision genérica | perception planner/task-fit; no parser-only escalation demostrado |
| Children0 | ausencia upstream deIR/padre y vocabulario/ownership; no fallo de persistencia probado |
| Requirements/Evidence y empateprimaryUUID | limitación separada de extracción/normalización |
| Grounding/dedup/DB/materializer | No defecto independiente demostrado; caso se pierde antes |

**Próximo slice más pequeño sustentado:** puente canónico Native-table→IR,
acotado a relaciones de fila/header que puedan probarse desde fuente real
versionada. Usar geometría/orden genuinos si se necesitan, con spans literales y
provenance, sin inventar pipes como citas, ni IDs/owners por proximidad. Headers
multilínea requieren relaciones demostradas; incertidumbre termina enreview.
Validarlo con PDFs sintéticos genéricos que recorran extracción real→normalización→
adapter→IR→grounding, no sólo norm(TABLE). Mantener SI11, índices/cuestionarios,
separaciónV6c, providers/budgets y autoridad humana. Cualquier cambio significativo
del contrato de fuente/proof requeriría revisiónADR, no se implementa aquí.

Un único slice acotado es razonable para atacar el **primer bloqueo de tablas**
y demostrar si produce Scope/hijos fieles. **No está demostrado que él solo cierre
todo MVP-06.V.** Permanecen prosa/referencias/globales y defectos separados de
Requirements/Evidence. No prometer cierre ni ampliar ese fix para resolver todo
a la vez. No hay evidencia para proponer mayor budget, otro LLM o reescritura
general de gramática. La aceptación del siguiente trabajo/validación es humana.

NOT READY FOR UAT bajo el alcance actual:Workspace/ingesta maduros no sustituyen
Scope anunciado. LIMITED UAT requeriría un alcance restringido explícitamente
aprobado que no prometa las capacidades ausentes; no se declara ese recorte aquí.

## 16. Verificación y conservación

Se preservan pre-freeze, input binding, first-pass, FROZEN, reporte operacional,
exports, eventos, originales y recibos; históricos1–6inalterados. No code/test/
config/schema/migration edits, DBwrites, providers, pipeline replay, Attempt8,
stage, commit o push. Sin nueva HumanTruth ni overrides de dominio.

Validaciones reproducidas:envelopes/SHA/corpus, funciones puras sobre255fuentes,
60identidades de plan congeladas,9contextosadapter,43candidatos y37/6guards,
2antiguos casos de seguridad y revisión visual dirigida. No se reran tests ni
compileall:sin cambios source y los mocks no prueban calidad semántica. La
regresión previa congelada sigue409focalizada/1099ampliada/2055completaPASS,
pero no se presenta como nueva medición de este análisis. git diff --check PASS
y tracked limpio. Las comprobaciones de cierre están en post_adjudication_integrity.json.

Artefactos principales:semantic_adjudication.json/md, comparison_ledger.json,
material_case_ledger.json, loss_traces.json, reconstruction_diagnostic.json,
adapter_context_diagnostic.json, planner_sample.json, perception_contribution.json,
requirement_candidate_adjudication.json, candidate_source_checks.json y ayudas
original_source_review/selected_source_review/source_renders. Hashes completos
en adjudication_artifacts.sha256.json con digest separado.

MVP-06.V BLIND ATTEMPT #7 FINAL SEMANTIC ADJUDICATION COMPLETE — READY FOR RELEASE-GATE ARCHITECT REVIEW
