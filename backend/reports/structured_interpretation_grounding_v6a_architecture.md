# MVP-06.V.6a — Structured Interpretation + Grounding: revisión arquitectónica

**Estado: propuesta completa para revisión de implementación; cero implementación.**
HEAD inicial/actual: `a24a5b18fe43ca15a949408b77e19aea1f2950a4`.

## 1. Evidencia aceptada, alcance y conclusión

Attempt4 `06v4_7ed8794a5b9c415dbe9b4c8fc40a70ba`: operacionalPASS / safetyCONDITIONAL PASS / semanticFAIL. First-pass SHA `893ecae1aa6bf9b1fe510eba5b8fefb82fc4e5ff5d6bdb22172bdede6311395b`; adjudicaciónMD `f59c85e2fc0bc062ab5eab8b3c69eef6666b6161c4838a5cd4c9e6ef66a717f5`; JSON `4776b082111b79ae1b0ac47657b0f082d7dd0c7aaf44a456683846a80a51b508`. Hashes verificados. Se usa evidencia aceptada, sin reabrir el corpus para calibración ni reejecutar análisis productivo.

El primer punto genérico de pérdida confirmado está en **formación/interpretación del candidato**, específicamente procurement_rows y el contrato de adapter que lo consume. No se infiere una falla del materializador a partir de persistencia0. El diagnóstico aceptado encontró0filas elegibles en259transcripciones disponibles. El código lo explica: sólo bloques encabezados por una etiqueta explícita de ítem y una acción inmediata. La pérdida de geometría de celdas ocurre todavía antes al persistir texto plano; es un límite de información para reconstrucción, no prueba de que todos los misses necesiten percepción nueva.

Native/OCR ya contienen evidencia útil; la interpretación estrecha y los bindings de grounding no representan bien tablas y prosa distribuida. Children no se forman porque no hay Scope padre. La mejoraV4a debe conservarse: índice/cuestionario permanecen UNKNOWN/review; ampliar cobertura no autoriza owners confiados.

Recomendación: **dos slices**, primero una vertical determinista de bloques/grounding/SAQ y después separar suficiencia perceptual de éxito interpretativo. No introducir un extractorLLM genérico, nuevo proveedor o subida de budgets. No recomendar Attempt5 hasta ambos cierres y regresiones.

## 2. Pipeline actual exacto

| Etapa / owner | Entrada → salida | Rechazos/limitaciones | Confianza y provenance | Identidad/idempotencia |
|---|---|---|---|---|
| main._extract_pdf_pages / normalización | Original inmutable → DocumentPage.text, IMAGE regions, NormalizedContent | PDF guard/parser/integridad; no persiste texto con bbox por palabra/celda | Native conserva página/revisión/generación; regiónIMAGE no es una tabla tipada | IDs/hash de originales y normalizados |
| document_intelligence_sources._enumerate_persisted_artifacts_for_document | Generaciones Native/OCR y detalleVision → artefactos activos/deselected | OCR fuente vacía/fallida; generación ambigua; contratoVision no detalle; lineage | Conserva proveedor/capacidad; no mezcla ni adquiere | Claves native-page:/ocr-result:/Vision existentes, selección de generación |
| load_document_transcriptions/load_page_structure + guard_structure/advance_continuity | Evidencia activa → RoutingResult y contexto estructural | FAILED/UNAVAILABLE/deselected no resucitan; discrepancias/identidad ambigua →review | Texto disponible no implica RELIABLE; no autoridad contractual por proveedor | Generaciones y resolución estructural versionada |
| NativeScopeDetailAdapter / OcrScopeDetailAdapter | payload.text normalizado → procurement_rows + explicit_fields → ScopeDetailEvidenceCandidate | Etiqueta de ítem+acción; preguntas/TOC excluidas; sin reconstrucción de columnas/tabla | Native/OCR distintos, confidenceNone/reviewTrue; ownership sólo si estructuraRESOLVED y keyrespaldada | locator versionado, generación/hash/span; misma gramática para ambos |
| VisionScopeDetailAdapter | DETAIL_TRANSCRIPTION.parsed_supply_rows → candidatosScope | STRUCTURE_SCOPE no soportado como detalle; sin source_excerpt/domain no candidato; owner debe probarse | analysis/page-result/task/region; review/inheritance bounded | Row index/locator y fingerprintsVision por tarea |
| adapt_and_persist_scope_detail_artifact(persist=False) | Propuestas → lista validada/guardada | excerpt debe existir en fuente activa compatible; comparaciones críticas retiran owner; estructura noRESOLVED retira bindings confiados | review y UNRESOLVED conservan propuesta; no son veto general de persistencia | No persiste todavía; identidad de fuente se conserva |
| scope_logical_identity.reconcile_candidates | Lotes → elegidos + logical_evidence | Distingue ocurrencias; no fuzzymerge; conflictos de owner/valores→review | Devuelve todas las artifact_keys; NO las persiste como relación multievidence | scope-logical-v2:owner/doc/page/domain/type/excerpt/ocurrencia; fingerprint suma campos semánticos |
| scope_details.replace_scope_details_for_artifact | Candidatos → TenderScopeDetail | ITEM requiere owner; UNRESOLVED requiere review; dominio/fuente/pageidentidad válidos | Un source_method/artifact/locator/excerpt canónico | Unique artifact+fingerprint; reuse_unchanged sólo identidad/generación/estado iguales; reemplazo explícito vuelve stale review |
| harness.materialize_canonical | Cada ScopeDetail existente → materializadores de atributos/cantidades | Scope0 implica0iteraciones; no padres por inferencia automática | Padre obligatorio, mantiene decisión humana | Orquestación actual no rescata fragmentos sin padre |
| scope_*_materializer + native/OCR child adapters | Scope versionado + generación validada → candidatos hijos | valid_scope_identity exige ITEM+owner; filas legacy sin identidad no se enriquecen; campos colon explícitos | Heredan review; no copian provenance de otra capacidad | Revalidación de locator/generación/recibo y parentid |
| scope_attribute/quantity adapters + normalizers | Campos raw → valores/unidades/relaciones tipados | Sin adivinar separadores/unidades; quantity yunit deben estar grounded en excerpt; nombres/relaciones vocabularios aceptados | Review propagado; normalización numérica no confirma hecho contractual | Fingerprints de campos +parent/source; reemplazo/reuse según reglas propias |
| replace_scope_attributes/quantities | Candidatos válidos → hijos FKScopeDetail | Parent/source/page/tender mismatch o grounding inválido falla | No huérfanos, no sobrescritura humana silenciosa | Unicidad/fingerprint; regeneración y auditoría vigentes |

Referencias principales: app/scope_detail_materializer.py (preparación→reconciliación→persistencia), app/scope_detail_adapters.py, app/native_scope_evidence.py, app/ocr_scope_evidence.py, app/scope_logical_identity.py, app/scope_attribute_materializer.py, app/scope_quantity_materializer.py, app/scope_details.py, app/scope_attributes.py, app/scope_quantities.py.

## 3. Gramática: qué acepta realmente

native_scope_evidence._ITEM reconoce al comienzo de línea PARTIDA/ITEM/ÍTEM/CONCEPTO/NO, número opcionalmente decimal/letra. El whitespace entre marcador y número es horizontal: “PARTIDA\n7” NO se reconoce como un encabezado. Tras el número, procurement_rows elimina separadores/whitespace, inclusive saltos, y exige que el **cuerpo empiece** con suministro/suministrar/servicio de/prestación de/entrega de/entregar. No basta que aparezca alguna acción más adelante.

El bloque puede ser multi-línea y termina ante el siguiente match de ítem: NO es una gramática exclusivamente de una línea. Sí admite “ITEM7\nSuministro de...\nMarca:...”, pero no el patrón genérico identificador en celda separada +descripción sin verbo rector. Preguntas, signos¿/? y referencias con puntosguía se rechazan de forma conservadora.

explicit_fields exige etiquetas marca/brand/modelo/model/cantidad/quantity/unidad/unit con dospuntos, al inicio o después de pipe/puntoycoma/nueva línea. La cantidad exacta debe tener un número decimal acotado y unidad reconocida. No representa encabezado “Cantidad” más celda vecina, marca compuesta, modelo rotulado con otro rol, rangos o números asociados sólo por cercanía. Las restricciones documentadas en ADR0011 son intencionales; su alcance no satisface el objetivo de cobertura medido. No es un motivo para ensanchar regex alrededor de frases reales del Tender.

Formas legítimas no representadas: tabla con encabezados+celdas, descripción multilínea sin acción lexical inmediata, continuación de fila en página vecina, obligación narrativa de un ítem ya identificado, cantidad/unidad separadas en columnas, fragmentosOCR fuera de orden y encabezados repetidos. Se debe distinguir “no soportado por intérprete” de “documento sin obligación”.

## 4. Unidad mínima recomendada

Unidad semántica: **un bloque relacional de evidencia de una ocurrencia**, usualmente una fila o grupo de continuación, con alcance explícito de tabla/región/página. Las líneas/spans son nodos de soporte; la página es contenedor, no un hecho. Multi-page es una relación excepcional con continuidad probada, no unidad por defecto. No tratar el documento entero como un bloque ni heredar owner a todo texto posterior.

Propuesta runtime tipada `StructuredEvidenceBlock` (nombre provisional):

- block_id/policy_version, document/version/page identities y ámbito de tabla/región;
- fragments con source_method/capability/artifact_key/generation/hash, texto exacto, offsets y coordinates opcionales reales;
- edges tipados HEADER_OF, SAME_ROW, CONTINUES, DESCRIBES_ITEM, VALUE_FOR, UNIT_FOR, ATTRIBUTE_OF; cada edge referencia soportes y regla/version que lo justifica;
- item_identity_evidence independiente de confiar en el owner; roles description/item_marker/quantity/unit/attribute conservados;
- estado SUPPORTED/AMBIGUOUS/UNSUPPORTED, razones, alternativas, sin inventar confidence;
- hipótesis de Scope/Attribute/Quantity con field→fragment_refs y posibles owners, no FKs productivas aún.

Reutilizar PageIdentity, Evidence/SourceMethod/Capability, NormalizedItemIdentity, TaskRequest y candidatos de dominio existentes. Ninguno de los objetos actuales proporciona todas las relaciones de fila/celda; extender mediante una IR pequeña, no otro dominio contractual ni un framework de grafos. Dataclass/Pydantic congelado; sin nuevas enumsDB ni servicio externo.

## 5. Reconstrucción determinista y disponibilidad real de geometría

Native actual persiste get_text('text') en DocumentPage/NormalizedContent; DocumentPageRegion describe imágenes, no cajas de palabras ni celdas. OCR actual PageOcrResult conserva text/scope/region_id pero no TSV/hOCR/cajas por token. No se puede afirmar que la geometría ya existe ni fabricar coordenadas para texto normalizado.

Plan acotado futuro:

1. Convertir texto versionado en fragmentos con offsets literales. Preservar orden de fuente; detectar explícitamente etiquetas/campos y bloques de continuación sólo cuando el contrato los sostiene.
2. Para tablasNative cuya relación ya no está en el texto, derivar determinísticamente layout de palabras/celdas desde el original inmutable, en una generación de layout propia con hash original, versiónextractor y sistema de coordenadas. No reemplazar generación de texto ni inventar correspondencia con offsets; validar el mapping o mantenerlo separado. Esta adquisición determinista debe estar aprobada dentro del slice futuro.
3. Encabezados y celdas se vinculan por ámbito/tablarow y geometría/estructura real. Repeticiones son metadata; no nuevaspartidas. Empates o celdas combinadas sin regla suficiente quedan review, no nearest-neighbor arbitrario.
4. OCR sólo usa geometría si un artefacto real ya la aporta. En el flujo actual sólo orden textual/regioncrop puede sostener algunas relaciones; sin prueba de mismo renglón→AMBIGUOUS. Dar soporte a cajasOCR futuras requiere contrato adicional de adquisición; no rerun ni cambio de proveedor como parte de esta revisión.
5. Narrativa se vincula mediante referencia positiva explícita al ítem/conjunto y límites de sección, no “último número visto”. Multi-page exige continuidad explícita más identidad fuente; no simple adyacencia de páginas.

Una IR runtime no vuelve semánticamente fiables todos los fragmentos. Debe admitir hipótesis alternativas y evidencia pendiente sin persistir cantidades como hechos confiados.

## 6. Grounding: conservar exactitud, ampliar representación

Los controles actuales de generación/hash/revisión no son demasiado estrictos; deben conservarse. La limitación es representar sólo un span/locator/excerpt y exigir una relación ya aplanada, no verificar demasiado la fuente.

Native usa normalized UUID/hash +span y valida source_excerpt contra texto normalizado. OCR ocr_locator se construye con offsets usados por la gramática sobre normalized_text, pero resolve_ocr_scope_payload compara el span con PageOcrResult.text raw; existen saltos/normalizaciones potencialmente distintos. **Riesgo de contrato confirmado por código**, no causa demostrada de los0candidatos del pase. La implementación debe declarar qué espacio de offsets usa cada ref y mantener mapping raw↔normalized versionado o verificar contra el espacio correcto. Añadir test específico; no declarar un fallo real no observado.

El guard actual `candidate.source_excerpt in observation.text` no puede validar un excerpt confeccionado concatenando celdas lejanas o capacidades distintas. No se debe relajar a substringaproximado ni unir textos como si fueran una cita literal. Grounding nuevo debe comprobar por campo: fragmentos existentes, rango exacto/hash, rol de columna, edge de pertenencia, ownerpositivo, versión y alcance. Un número presente en algún lugar del excerpt no demuestra cantidad del ítem; se necesita VALUE_FOR +UNIT_FOR.

## 7. Multi-span / multi-capability y persistencia

TenderScopeDetail/Attribute/Quantity tienen source_locator String512, una fuente/artefacto/método, source_excerpt Text; no poseen una colección evidenciaJSON/FKmultisource. RequirementCandidateEvidence sí tiene relaciones/JSONB, pero pertenece a otro dominio; NO reutilizar esas filas ni esconder evidencia en warnings, analysisVision ficticio o description.

`ScopeLogicalEvidence` devuelve varias artifact_keys y conflictos sólo como resultado runtime. Conservar las percepciones por separado no conserva por sí mismo la relación entre todas las fuentes y un hecho persistido. Por tanto una IR exclusivamente efímera no satisface auditoría completa si el hecho combina spans/capacidades.

**Primera implementación sin migración, con contrato nuevo explícito a aprobar:**

- Un único artefacto local derivado `StructuredEvidenceManifest` versionado, acotado e inmutable por contenido, guarda fragments/edges/fieldbindings y todas las capacidades contribuyentes. No guarda originales binarios enDB. Se retiene mientras exista cualquier hecho/revisión que lo referencie; incluido en backup/exports y validación de root/integridad.
- Locator compacto ≤512 refiere manifestSHA+block/field id, no incrusta JSON ni ruta absoluta libre. artifact_key/método canónicos mantienen una representación primaria genuina y compatible, con manifestref en locator/source_contract_version nuevos. No introducir SourceMethod MIXED ni relabel deOCR comoNative.
- source_excerpt permanece una cita literal representativa identificada por ref. Un bounding span contiguo real es válido cuando todos los campos están en una generación/página; un join de spans es display derivado, no una cita original. Fieldbindings del manifest dan el soporte completo de quantity/unit/attribute aunque estén en spans distintos.
- Validadores/resolvers despachan el contrato nuevo ANTES del parserlegacy; para éste verifican todas las refs y relaciones y no sustituyen sin más el excerpt de una capacidad por otro. Las validacioneslegacy siguen idénticas. Cantidad/unit se prueban contra sus propios refs exactos, no sólo contra la cita representativa. Una ref faltante/corrupta/incompatible bloquea materialización/reuso, con diagnóstico explícito; no fallback a current page.text ni promoción de certeza.
- Cambios sólo de corroboración deben conservar identidad lógica si el hecho/owner no cambió, pero actualizar la generación de prueba auditada sin aumentar confianza. Si cambian significado/owner/campos o generation relevante, regenerar conforme al contrato de revisión humana; nunca reasociar una aprobación automáticamente.

No existe todavía este manifest ni su loader: es diseño propuesto, no infraestructura ya disponible. Usar estructuraFilesystem y rootguard existentes, con validadores de hash y versión; no un nuevo servicio/cola. Si la política de persistencia requiere que la relaciónmultifuente sea transaccional y consultable enteramente porSQL, entonces sí se requeriría una tabla evidencia explícita con FK y roles (migración separada). No se recomienda para el primer corte. Si no se aprueba un artefacto derivado durable, limitar el primer corte a candidatos con soporte completo representable en fuenteprimaria y mantener combinacióncross-source pendiente; no fingir que runtime puro ya resuelve auditoría.

## 8. Identidad positiva y protección V4a

Separar candidato plausible, ownerresuelto y estructuraTRUSTED. Un candidato de ítem requiere evidenciaspositivas de rol: ancla en columna/tipo ítem y descripción contractual, o bloque explícito de suministro/servicio/entrega; cantidad/unidad enlazadas pueden reforzar identidad pero un número aislado no lo hace. Si faltan relaciones suficientes: propuesta provisional sin owner/productfact confiado, REVIEW_REQUIRED/UNKNOWN.

TOC/índices, cuestionarios, referencias de página, números de sección, fechas/importes no adquieren identidad porque el nuevo parser reconozca sus columnas. Evitar listas negativas de frases; exigir tipo de tabla/relación positiva sustentada. La nueva IR alimenta los mismos guard_structure/identifier_comparisons/continuity; no escribe directamente una resolución confiable. Índice/cuestionario de V4a se preservan con fixtures sintéticas genéricas independientes del corpus.

## 9. Contrato neutral por capacidad

Neutrales: identidad página/revisión, texto/spans, ámbito/región, roles/edges, estados de ambigüedad, candidatefieldbinding y versionado. Específicos: offsetsNative, mappingnormalización, crop/cajasOCR reales, provider/task/model/imageSHA deVision, generaciones y confianza declarada. Cada fragmento conserva su método/capacidad; coincidencia de valores no fusiona sus locators.

Adaptadores de fuente traducen a la misma IR; UN intérprete determinista opera sobre relaciones verificadas. Los wrappersNative/OCR pueden mantenerse por compatibilidad, delegando el significado común. No mantener tres gramáticas semánticas divergentes. No todas las fuentes ofrecen las mismas relaciones: el adapter debe declarar unavailable/unknown en vez de fabricar equivalencia.

## 10. Scope padre y evidencia provisional de hijos

Conservar FKScopeDetail obligatoria para Attribute/Quantity productivas. Un owner final no se debe resolver por fuerza para salvar valores. Formar bundles runtime con UnresolvedItemHypothesis +Attribute/QuantityEvidence antes de aceptación del owner; no son hijos canónicos ni hechos seguros. Si hay Scope justificado pero ownerdesconocido, el contratoScope ya soporta UNRESOLVED/review; hoy los adapters dehijos exigen valid_scope_identity ITEM y no lo consumen. Ese gate debe permanecer para persistencia de hijos hasta diseño explícito aprobado.

La evidencia provisional se puede reconstruir determinísticamente y, al persistir un Scope revisable que la necesita, conservarse en su manifest; si no hayScope, diagnóstico/bundlederivado versionado puede retenerla sin crear padre contractual ficticio. Cuando el owner se resuelva, validar bindings y generación otra vez antes de crear hijos. Nada de orphanAttribute, childglobal automático o asociación al ítem vecino más cercano. Orden lógico Scope→hijos continúa correcto para persistencia, sin exigir que el parser descarte toda evidenciahija temprana.

## 11. Planner: separar percepción e interpretación

Acoplamiento confirmado: plan_ocr importa procurement_rows/explicit_fields y structural_candidate_from_native_text. La suficienciaScope requiere identity_valid; Attributes además marca/modelo; Quantities número/unidad admitidos. Si falla una gramática y hayIMAGE, termina OCR_NEEDED. region_id explícito fuerzanative_sufficientFalse. construct_tasks aplica todas las tareas a cada página y dos preguntas espaciales cuando Native no supera ese mismo contrato. La misma brecha llega a la reevaluaciónVision. Por ello falla de adapter puede parecer falta de percepción;80/78needs y0avoided no demuestran80/78déficits visuales.

Proponer dos resultados tipados, sin reusar un booleano ambiguo:

- PerceptionAssessment: cobertura de evidencia requerida por tarea/región, espacio de fuente, integridad/legibilidad y razones `SUFFICIENT`, `MISSING_TEXT`, `UNREADABLE`, `VISUAL_RELATIONSHIP_UNAVAILABLE`, `UNKNOWN`. Texto no vacío por sí solo tampoco prueba suficiencia.
- InterpretationAssessment: candidatos/edges resueltos, ambigüedad, `UNSUPPORTED_GRAMMAR`, `OWNER_UNRESOLVED`, `GROUNDING_INCOMPLETE`, `CONFLICT`. Sin éxito interpretativo no se infiere falta perceptual.

Una demandaOCR debe señalar fragmento/ámbito textual ausente o ilegible; una demandaVision, relación espacial necesaria y no disponible, con sourcebinding. Si IR tiene evidencia legible suficiente pero no candidatos, devolver review/unsupported del intérprete y no adquirir por ese único motivo. Si la relación de fila realmente falta trasOCR, Vision sigue permitida bajo contrato/budget, no se suprime indiscriminadamente. Evalúa primero Native, luego OCR existente; no orden ni threshold impuesto por nombrearchivo/conteoesperado. Mantener Guard/recibos/rate/budgetautorizados sin cambios; versionar la nueva política para evitar reuso de planes viejos.

## 12. Compatibilidad Vision: sin rediseño de proveedor

STRUCTURE_SCOPE entrega segmentos/new_items/continuidad y anchors; son hipótesis de identidad, no campos detallados ni prueba de que la fila sea contractual. No alimentar automáticamente detalle desde estructura.

DETAIL_TRANSCRIPTION actualmente entrega raw_lines, incertidumbre y source_page. _merge_detail_transcription llama _parse_supply_line **por línea** para parsed_supply_rows; selective_vision_executor._validated_payload añade la misma gramáticaprocurement_rows si puede. Por tanto también hay pérdida potencial en el ensamblado porlínea, aunque en Attempt4 eldetalle no completó. El contrato existente puede alimentar fragmentos de texto e identidadtask/crop; no garantiza cajas por fila/celda ni relaciones semánticas correctas. regioncrop no son boundingboxes de cada palabra.

Primer corte consume raw_lines/parsedrows existentes como evidencia con sus límites; reconstruye sólo relaciones defendibles por orden/etiquetas/contrato verificadas. Si faltan, AMBIGUOUS. No cambiar prompt/modelo/tokens/timeout para dotar geometría imaginaria. Si más tarde se necesita una salida espacial tipada distinta, sería un slice/providercontract independiente; no requisito automático para corregir material Native ya disponible.

## 13. Matriz sintética propuesta (NO ejecutada ni implementada)

Todos los casos inventados genéricos, sin nombres/frases/valores del Tender2. Usar loaders/interpretación/validadores públicos, no fixtures derivadas del corpus. Mocks verifican control de flujo, no calidad realOCR/Vision.

| Caso | Entrada / invariante esperado |
|---|---|
| SI01 | Ítem explícito+acción+cantidad/unidad en una línea →1candidato con refs exactas; review sin confianza inventada |
| SI02 | Marcador, descripción de2líneas y valor posterior vinculados →1bloque/candidato; texto interveniente no se convierte en cita ficticia |
| SI03 | Header+fila con columnas probadas →roles/cantidad/unidad sustentados por refs de header ycell |
| SI04 | Dos filas vecinas con owners distintos →2candidatos y referencias separadas |
| SI05 | Header repetido en segunda página →metadata, no itemnuevo; continuidad requiere soporte |
| SI06 | Tabla de índice con números/páginas →sin itemcontractual/ownerTRUSTED |
| SI07 | Cuestionario con No/Sí/pregunta1 →no partida; ambigüedadreview |
| SI08 | Numeral de sección adyacente a una unidad →no cantidad por posición |
| SI09 | Fecha/moneda/importenarrativo →no cantidad de equipos |
| SI10 | FragmentosOCR con geometría real o relaciónorden explícita defendible →fila única, conserva sourceOCR |
| SI11 | FragmentosOCR sin vínculo de fila →alternativas/review; no completar celdas por cercanía arbitraria |
| SI12 | Descripción/quantity en spans separados →fieldbindings exactos, excerptrepresentativo no fabricado |
| SI13 | Atributo en celdaadyacente al owner probado →hijo correcto; evidencebeforeparent queda provisional |
| SI14 | Quantity/unit en celdasadyacentes al owner probado →Decimal/unidad correctos sin inferir totales |
| SI15 | Dos ownersvecinos →prohibido cruzar atributo/cantidad aunque coincidan valores |
| SI16 | Native/OCR comparables que soportan misma ocurrencia →un hecho lógico; no fuzzymerge de paráfrasis |
| SI17 | Todas las capacidades/fragmentos deSI16 conservadas tras persistir/releer manifest, sin relabel |
| SI18 | Owner o continuidad ambiguos →UNKNOWN/review; no hijocanónico hasta resolver binding |
| SI19 | Prosa genérica sin relacióncontractualpositiva →no inventar item/quantity |
| SI20 | Segunda ejecución idéntica →IDs/hijos/pruebasestables; cambio real de generación invalida correctamente |
| SI21 | UnsupportedGrammar con evidencia legible presente →no PerceptionInsufficient implícito |
| SI22 | Native cubre pregunta textual/región comprobada pero0candidatos →OCRcalls0 |
| SI23 | OCR existente suficiente para pregunta textual yadapterfalla →Visioncalls0; relación espacial realmenteausente sí mantiene demanda legítima |
| SI24 | Suite ST10–ST20 y negativos V4a →misma abstención en índices/cuestionarios, con positivos reales aún viables |
| SI25 | Offsetraw/normalizedOCR distintos por blanklines →resolver correcto/diagnóstico explícito, nunca span falso |
| SI26 | Manifest ausente/hash corrupto/ruta fuera delroot/genstale →failclosed, sin fallbacklegacy |
| SI27 | Corroboración nueva misma identidad →sin duplicarScope ni aumentarconfidence; decisioneshumanas preservadas según contrato |
| SI28 | Conflicto de valores entre fuentes →alternativas+review, no voto/predilección por capacidad |
| SI29 | Continuación multipágina probada vs simple adyacencia →sólo primera admite relación; headersreiniciados no cruzan owners |
| SI30 | Fuente legacysin geometría →unknowngeom y ninguna bbox inventada; detalleVision no sustituye contratoestructura |
| SI31 | Guard y presupuesto:0adquisiciones durante reconstrucción →compatibilidadBR/FB/BH y contratos de freezeversion |
| SI32 | Borrar/reemplazar padre de forma autorizada →revisiónstale/cascade esperado; replayidéntico no elimina hijos ni manifiestos referenciados |

## 14. Frontera Requirements/Requested Evidence

requirement_extraction usa SourceBlock, _split_blocks, actores/modalidades y descubrimiento/merge propios; requirement_semantics produce EvidenceExpectation. Comparten loadersDI y fuentes, **no el mismo procurement_rows como primitiva de extracción de requisitos**. Por tanto se difieren. No corregir clasificación, segmentos o evidencia requerida dentro deV6b/V6c. No prometer que laIR arreglará31/43/8. Regressions deben demostrar que esa superficie permanece compatible; no reutilizar su JSONB de evidence para esconder soportesScope.

## 15. Schema y decisión arquitectónica

No new table/column/enum/migration para IRruntime y almacenamiento de un manifest de evidencia local referenciado por campos existentes. Esto requiere contrato persistente versionado, loader y lifecycle/backup explícitos; no es “sin trabajo de persistencia”. No cabe el conjunto arbitrario de spans en locator512; usar referenciahashcompacta, no ampliar silenciosamente la columna ni truncar evidencia.

Si se exige FKmultievidenceSQL/consultas relationales/atomicidad integralDB, presentar propuesta de migración separada y detener implementación hasta aprobación. Actualmente no es necesidad demostrada. Los59driftsAlembic siguen deuda ajena: no justifican alterar modelos ni reparar schema.

Antes de implementar, registrar/aprobar ADR nuevo de interpretación/groundingmultispan (número a elegir según secuencia de ADRs). Extiende ADR0011/0012/0013/0014, no los debilita; no escribir eseADR como aceptado en esta revisión.

## 16. Secuencia mínima recomendada y archivos probables

**Dos slices justificados, no tres por defecto:**

**V6b — vertical bloques/grounding +consumoSAQ.** IncluyeIR tipada, reconstrucción determinista acotada, manifest/refs/resolvers y wrapperadapters compartidos. Cierra verticalmente SI01–SI20 ySI24–SI30/SI32 con Scope/hijos reales sintéticos, sin instalar providers ni modificar adquisición. Así no se entrega unaIR huérfana ni se cambia el planner antes de que exista un contrato de interpretación validado. Delimitar primera cobertura: un documento, misma página/fila con soporte probado, prosa con vínculo explícito; multipágina sólo si ya existe continuidad canónica defendible, de lo contrario deferred.

Archivos nuevos probables (nombrespropuestos, NOcreados): app/structured_evidence.py, app/structured_evidence_grounding.py, app/structured_evidence_storage.py, tests/test_structured_interpretation.py, tests/test_structured_grounding.py. Evitar un archivo por cada conceptopequeño; separar storage del intérprete puro para impedir adquisición/DB en la gramática.

Reusar/extender: document_intelligence_sources.py (conversiones aIR), native_scope_evidence.py/ocr_scope_evidence.py (lectura de contratoslegacy), native_scope_detail_adapter.py, ocr_scope_adapters.py, vision_scope_detail_adapter.py, scope_detail_adapters.py, scope_detail_materializer.py; scope_attribute_materializer.py/scope_quantity_materializer.py y sus adapters para nuevo locator, scope_details.py/scope_attributes.py/scope_quantities.py para despacho de grounding/version. scope_logical_identity.py necesita revisar ocurrencia/identidad y generación de prueba. main.py sólo si la exposición canónica de layoutNative requiere un helper mínimo; preferir nuevo módulo de lectura determinista, sin cambiar endpoint/import.

**V6c — frontera de suficiencia del planner.** Añade PerceptionAssessment/InterpretationAssessment e integra evidenceavailable/deficit explícito en document_perception_planner.py (incluye plan_document_vision_tasks), y construct_tasks en blind_selective_harness.py. Verificar SI21–SI23/SI31 y negativos/positivos de elegibilidad manteniendo presupuestos y Guard. selectivexecutors sólo para integrar resultados versionados, sin cambio de cliente/config. Requiere V6b aceptado para distinguir un déficit real de noSoportado, pero puede validarse independientemente con clientesdobles.

Archivos de configuración/freeze a revisar si cambian versiones: blind_selective_freeze.implementation_versions y codehashmanifest canónicos; no reusar resoluciones/planes viejos bajo nuevas reglas. PruebasBR/FB/BH, OC/VP/ST/SC/DC y materializadores, relevantDI y fullsuite sólo conforme al alcance acordado de implementación. Documentar en protocolo/ADR. No cambiar modelos/alembic/requirements/provider configs en ninguno de los dos slices sin blocker explícito.

No se recomienda unV6d separado ahora: dividir sólo los wrappers de consumo deV6b dejaría un contrato sin caso vertical y duplicaría integración. Tampoco un solo slice conplanner: mezclar adquisición/costpolicy con nueva interpretación haría difícil atribuir regresiones. Esta secuencia debe aprobarse, no es autorización de implementación.

## 17. Riesgos principales y gates de cierre

- Confundir headings/cuestionarios con ítems: positivos estrictos +STnegativos; sin listasTenderespecíficas.
- Unir celdas/filas equivocadas, perder ocurrencias o attrs de vecino: edgesauditables/ambigüedad ySI04/15/29.
- Offsetraw/normalized incorrecto y join como cita literal: contratos de espacio ySI12/25.
- Sourcebundle falso o rollbackDB que deje archivohuérfano: escritura inmutable anterior a ref, contenido por hash, failclosed a refmissing; limpieza explícita sólo de no referenciados, sin borrar recibos/históricos para resetear.
- Borrar hijos/decisiones por cambio de artefactoprimario o fingerprint: tests de identidad/reuse/autoridad humana; separar identidad de hecho y generación de soporte.
- Mezcla de capacidades que fabriqueconcordancia/confianza: fuentes independientes, conflictos visibles, no mayoría.
- Planner que ahorre llamadas pero oculte un déficit genuino: positivos de image-only/relacionesvisuales todavíaadquiribles y negativos parserfalla sinadquisición.
- Explosión de memoria/layout/manifest: límites por página/bloque/spans/tamaño definidos por contrato antes de ejecución; no stream ni infraestructura nueva.
- Geometría inexistente o reextracción con versiondistinta: no inventarla; generaciónlayout separada y explícita; missingrelationreview.
- Alterar Requirements/SourceEffects por reutilización de loaders: regresión de compatibilidad sin ampliar semántica.

Attempt5 sólo se justifica después de aceptación+commits deV6b/V6c, matriz sintética positiva/negativa, regressions apropiadas, revisión de seguridad e idempotencia y nuevo preflight/freeze/autorización humana. Los casosTender2 siguen evidencia de validación, no fuente de prompts/fixtures/regexcalibrados. No autoriza modelo/budgets nuevos ni permite reusar Attempts1–4.

## 18. Acciones realizadas en esta revisión

Sólo lectura de código/contratos/evidenciaaceptada y creación de este reporte técnico bajo reports. No implementaciones, proveedores, DBaccess/mutación, schema, migraciones, nuevosrun_id/freeze, replay, cambios a fuentes/outputs/semadjudication, stage/commit/push. Tests no ejecutados: no hay cambio de código; SI01–SI32 son diseño propuesto. Git diff --check y estado se verifican al cierre. Hashes de Attempts1–4/adjudicación/históricos se verifican sin reescribirlos.
