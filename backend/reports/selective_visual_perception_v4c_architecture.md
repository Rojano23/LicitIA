# MVP-06.V.4c — Selective visual perception: architecture review

HEAD verificado: `f1fccc76111b4d4ab28958fe5412724a264ea7e7`.
Revisión estática de código y contratos, sin aplicación/tests nuevos, DB, instalación,
renderizado, OCR, probes de runtime ni proveedores. Los antecedentes adjudicados sólo
motivan la brecha; no se reabrieron documentos de Tender #002.

## 1. Conclusión

La arquitectura dispone de percepción neutral, adquisición OCR/Vision, artefactos y
políticas, pero NO implementa todavía una escalera completa selectiva por tarea.
El orquestador decide principalmente ESTRUCTURA; no puede usarse como certificado
universal de suficiencia de TRANSCRIPTION o cobertura semántica de una página.

Arquitectura propuesta: **Native suficiente para la tarea → cero llamadas visuales**;
**Native insuficiente → recuperación visual selectiva**, con decisión pura separada
de ejecución explícita. No es una cadena obligatoria Native→OCR→Vision: OCR cubre
texto rasterizado y Vision sólo la capacidad espacial/estructural pendiente. Texto
OCR suficiente no prueba estructura suficiente, ni estructura resuelta prueba texto
completo. Un estado review de dominio tampoco dispara proveedores por sí solo.

Recomiendo dos slices: V.4c1 recuperación OCR selectiva y consumo OCR verificable;
V.4c2 escalamiento Vision independiente por tarea/capacidad. La separación responde
a brechas diferentes existentes, no a crear dos frameworks de percepción.

## 2. Ciclo de vida actual, verificado

| Paso | Código canónico | Comportamiento real |
|---|---|---|
| Ingesta | registro/import canónico de TenderDocument, main.py | Original local inmutable, SHA-256/identidad/revisión; no percepción implícita |
| Preparación | document_intelligence_blind_run.prepare_tender_documents | Predicate PDF canónico; unsupported explícito; reutiliza páginas completadas con IDs |
| Native | main.extract_document_pages / _extract_pdf_pages | PyMuPDF get_text('text'); páginas/texto/status/char_count; parser error TEXT_EXTRACTION_FAILED |
| Perfil | main._page_image_regions_for_page, _page_content_profile; DocumentPage.content_profile | Texto no vacío + imágenes elegibles → MIXED; sólo texto → TEXT_ONLY; sólo imágenes → IMAGE_ONLY |
| Regiones | main._ensure_page_image_regions | Bounding boxes de imágenes y area_ratio en DocumentPageRegion |
| OCR elegible | main._page_ocr_jobs; orchestrator._is_ocr_acquisition_useful / _build_ocr_execution_plan | NO_TEXT/full-page; MIXED/IMAGE_REGION; force puede pedir full-page |
| Plan local | _OcrExecutionPlan / _OcrJobPlan, requests OCR/VisionStructure | Trabajo planificado, no prueba de ejecución ni cola persistente |
| OCR ejecutado | main.run_document_ocr o orchestrator._default_ocr_executor → provider.recognize | Render 2x full-page/clip, un resultado por engine/scope/region |
| OCR persistido | PageOcrResult, _persist_ocr_artifacts | Estado/texto/engine/version/language/confidence/warnings/timing; upsert mutable |
| Normalización | content_normalization.process_document_normalization | Native y OCR separados, hash/NormalizedContent/chunks; no cambia OCR a Native |
| Vision elegible | resolve_page_structure + políticas; route_capability availability | NEEDS_VISION o fallback declarado; disponibilidad no ejecuta modelo |
| Vision ejecutado | OllamaVisionAssistClient; VisionAssistService; wrapper structure_only_isolated | Render bounded, esquema validado, HTTP local configurable; requests explícitos |
| Vision persistido | DocumentVisionAnalysis / DocumentVisionPageResult | Input/task fingerprints, model/prompt, image hash, structured_json, estado, tiempos |
| DI neutral | document_intelligence_sources.load_document_transcriptions / load_page_structure | Capacidad, canal, generación, lineage, calidad y conflictos separados |
| Estructura | document_structure_orchestrator | Resolver/guardas/continuidad → resolución y ScopeSegments; V.4a activo |
| Dominio | Scope/Requirements y sus materializadores/bridges | Decisión de dominio y autoridad humana, sin certificación por éxito del proveedor |

Advertencia operacional: extract_document_pages elimina/recrea páginas al extraer;
no usarlo como refresh de percepción completada. El driver V.3a sí evita ese camino
cuando la preparación ya está completa. V.4c no debe reextraer ni borrar Native para
incorporar OCR/Vision.

## 3. Qué significa actualmente «Native suficiente»

Hoy no hay un criterio general de suficiencia. _page_status_for_text sólo exige
strip no vacío. DocumentPage.content_profile también usa texto presente, no fidelidad.
La detección de imágenes filtra rectángulos con MIN_IMAGE_REGION_AREA_RATIO=0.03 y
MIN_IMAGE_REGION_PIXEL_DIMENSION=120. El nombre de esta última constante dice pixel,
pero se aplica a dimensiones de rectángulo PyMuPDF del documento; no es un estudio
de densidad OCR o resolución de píxeles del raster.

No se mide densidad textual útil, cobertura de glifos, legibilidad del raster,
relación de texto con tarea ni suficiencia de celdas/columnas. Char_count no es
calidad. Una página vacía sin imagen detectada se clasifica TEXT_ONLY pero NO_TEXT;
vector graphics, tipografía convertida a curvas e imágenes pequeñas pueden escapar
al perfil de imágenes. Renderability sólo se comprueba cuando se intenta renderizar.
Una cabecera Native y un escaneo del resto puede ser MIXED sin contenido suficiente.
Un logo elegible también puede dar MIXED aunque el texto ya cubra la tarea.

Por ello no recomiendo modificar umbrales por el corpus adjudicado. Recomiendo
suficiencia como prueba acotada a (página/región, capability, tarea): fuente válida,
texto canónico utilizable para el contrato solicitado, anclas/bindings presentes,
sin hueco explícito de adquisición requerido por esa tarea. Mantener tres resultados:
SUFFICIENT_FOR_TASK, INSUFFICIENT_FOR_TASK y UNKNOWN (vocabulario runtime propuesto).
No son nuevos enums DB ni equivalentes a TRUSTED contractual.

Review por fidelidad Native no certificada NO implica automáticamente insuficiencia
para adquisición. Tampoco se declara completa toda una página porque un parser haya
encontrado una fila. Si no hay prueba de necesidad visual, UNKNOWN con razón/revisión,
sin fan-out automático de proveedores. Las regiones visuales no cubiertas permanecen
visibles como gaps; no se inventa que sean decorativas.

## 4. OCR real y sus límites

TesseractOCRProvider ejecuta pytesseract.image_to_string; idioma es→spa, en→eng;
confidence y processing_time pueden ser null. PaddleOCRProvider usa PaddleOCR.predict,
agrega textos y scores; no mantiene por sí mismo relaciones de tabla ni geometría
por palabra. Ambos implementan DefaultOCRProvider, pero sus idiomas/confianzas y
runtimes no son equivalentes. No comparar sus scores como una escala común.

Diferencia importante: ocr.resolve_provider_selection(AUTO) devuelve el primer motor
local disponible, Tesseract antes de Paddle. El endpoint main.run_document_ocr AUTO
selecciona TODOS los disponibles, coherente con la política histórica dual-provider
MVP-02.2. El orquestador estructural elige sólo el preferido. No cambiar silenciosamente
AUTO global. La nueva política selectiva debe elegir un motor explícitamente y dejar
COMPARE/dual como una decisión aparte; tampoco hacer fallback a otro por defecto.

Son adaptadores locales; Tesseract necesita binario, wrapper y language packs.
Paddle requiere runtimes y pesos disponibles localmente: instanciar PaddleOCR puede
necesitar assets si faltan; no afirmar offline garantizado ni permitir descarga
implícita. No se comprobó disponibilidad en esta revisión.

## 5. Vision real y sus límites

Hay dos superficies: local_vision.py (LocalVisionProvider/Disabled/Ollama y renderer)
y ollama_vision.py (VisionAssistService/OllamaVisionAssistClient). Reutilizar la ruta
que persiste artefactos canónicos; no crear un tercer proveedor. Las llamadas/probes
a /api/tags también son contacto con proveedor y no pertenecen al planificador puro.
La configuración es local-first, endpoint configurable; no asumir que una URL remota
es autorizada. No hay fallback cloud ni autorización para instalar/modelos aquí.

El contrato STRUCTURE_SCOPE modela item_segments, inicios, continuidad, anchors y
flags de servicio/supply/deliverable. DETAIL_TRANSCRIPTION modela raw_lines,
incertidumbre y caracteres dudosos; después parsing acotado produce filas.
Esto NO es soporte general de interpretación de diagramas eléctricos, relaciones
arbitrarias de una tabla, celdas con bbox o ingeniería de producto. Esos significados
requieren contratos explícitos/grounding y permanecen review/no soportados.

VisionAssistService.analyze_document arranca con STRUCTURE_SCOPE y puede encadenar
DETAIL_TRANSCRIPTION según flags/uncertainties del resultado. Esa ruta general no es
una escalada selectiva por suficiencia Native/OCR. El wrapper structure_only sí
separa estructura y evita adquisición de detalle. region_hint es una indicación
textual; la invocación pasa image_bytes de página, no demuestra recorte real.
V.4c2 debe separar ejecución de tarea de transcripción/estructura y vincular región
real cuando se declare tal región, sin reutilizar STRUCTURE_SCOPE como transcripción.

## 6. Decisión pura, agenda y ejecución

Reutilizar Capability, PerceptionEvidence, CapabilityAvailability y RoutingResult.
Un PerceptionPlan runtime propuesto identifica documento/versión/página/región,
capacidad/tarea, razón, fuentes/generaciones evaluadas y operación necesaria o diferida.
No agregar un broker/servicio/cola. Un executor pequeño aplica autorización y presupuesto
sobre ese plan, usando interfaces existentes; no vuelve a interpretar requisitos.

Separar cuatro estados observables: elegible (necesidad justificada), planificado
(unidad concreta elegida), ejecutado (evento real de invocación) y completado
(artefacto válido para esa capacidad). Un payload COMPLETED no acredita fidelidad
ni cobertura completa. Instanciar proveedores para descubrir disponibilidad puede
probar runtimes: el dry-run usa disponibilidad declarada/persistida o UNKNOWN.

AVAILABLE_ONLY consume sólo persistido y conserva gap pendiente/UNAVAILABLE o
REVIEW_REQUIRED según evidencia; ninguna adquisición ni probe. RoutingResult ya
puede marcar fallback_requires_real_vision y contractual_authority=false. Las
políticas del orquestador son AVAILABLE_ONLY, ALLOW_OCR y AUTO; AUTO permite OCR y
Vision para estructura, no autorización universal para cualquier tarea/corpus.

| Condición por tarea | Plan mínimo |
|---|---|
| Native suficiente y sin necesidad visual pendiente | Native only, cero OCR/Vision |
| Texto rasterizado recuperable, sin relaciones visuales requeridas | Native+OCR selectivo |
| Relación visual/estructura explícitamente necesaria; texto ya suficiente | Native+Vision STRUCTURE bounded, sin OCR inútil |
| Texto ausente y estructura visual aún pendiente tras OCR | Native+OCR+Vision, sólo tareas/regiones justificadas |
| Perfil desconocido, raster no verificado o fuente no renderizable | UNKNOWN/deferred/unavailable con razón; no fabricación |
| Fallo o ausencia de proveedor bajo AVAILABLE_ONLY | Conservar página/fuentes/gap; no ejecutar |

Granularidad: política por página y capacidad, jobs por región cuando las coordenadas
son confiables. Full-page sólo para escaneo completo o cuando no existe región segura;
límites por documento/lote son presupuesto, no razón para percibir todas sus páginas.
Vectores/diagramas sin imagen raster detectada no son evidencia negativa de contenido.

## 7. Downstream y reconciliación

Requirements consume fuentes NormalizedContent y transcripciones DI; requirement_di_adapter
conserva provenance v2/review, y Requested Evidence la lee desde sus candidatos fuente.
Confirmar en implementación que OCR nuevo se normaliza y que transcripción Vision
independiente efectivamente entra al discovery canónico; no basta crear un PageResult.
No cambiar reglas de Requirements ni Requested Evidence como parte del planificador.

Scope recibe transcripción/estructura neutrales. Vision DETAIL sí tiene adaptador
predeterminado, Native V.4b también. OCR NO tiene todavía adaptadores predeterminados
de Scope/Attributes/Quantities: los resolvers aceptan su artefacto pero los adapters
lo dejan UNSUPPORTED. NeutralScopeSemanticAdapter requiere proveedor opt-in; no debe
instalarse un LLM para tapar esa brecha.

V.4c1 debe añadir un adaptador OCR de texto fundamentado bajo los mismos contratos,
reutilizando las funciones puras procurement_rows/explicit_fields ya existentes,
sin usar native_locator ni convertir método a NATIVE. Hijos necesitan resolver su
generación OCR exacta y owner válido. No rediseñar ni ampliar la gramática Native.
No afirmar que V.4b ya da cobertura OCR sólo por tener DI neutral.

Reutilizar scope-logical-v2 para grounding comparable y artefactos contribuyentes.
Conservar Native/OCR/Vision separados con sus calidades, lineage e identidades.
Conflictos → review/ownership no resuelto; Vision no gana por sofisticación, mayoría,
fecha ni canal. Paráfrasis o correspondencias espaciales no probadas no se fusionan
por parecido. V.4a y la invalidación de revisión humana por regeneración siguen activas.

## 8. Provenance disponible y faltante

| Dato | OCR actual | Vision actual | Requisito de diseño |
|---|---|---|---|
| Documento/revisión/hash original | Join DocumentPage→TenderDocument | Analysis→document/page | Validar antes/después; nunca mutar original |
| Página/número | PageOcrResult→DocumentPage | PageResult ids/page_number | Identidad de la página ya existente |
| Región/coords | region_id→DocumentPageRegion cuando existe | hint textual; DI admite coords opcionales | Guardar coords reales o declarar ausentes |
| Imagen renderizada/hash | No campo hash render en PageOcrResult | image_sha256 persistido | OCR necesita descriptor runtime/hash verificable |
| Engine/modelo/config | engine/version/language; score opcional | model/prompt + runtime JSON | Capturar parámetros reales, no inventar versión |
| Generación | OCR result id; normalizado id+hash | analysis id/input hash/page result/task fingerprint | No reutilizar ID como si prueba contenido inmutable |
| Texto/spans | texto OCR y normalización; sin word boxes contractuales | raw_lines/extracted fields; no bbox universal | Span calculado sobre texto exacto, no coordenadas inventadas |
| Capacidad/lineage/quality | PerceptionEvidence | PerceptionEvidence | Mantener canal OCR/Vision y revisión |

Un descriptor de adquisición runtime/artefacto local derivado puede conservar hash de
imagen, parámetros de render, job/task y contador de intentos sin esquema nuevo.
No esconder un catálogo de generaciones en warnings ni representar texto OCR como
Native para aprovechar un adapter. Los modelos de dominio conservan sólo provenance
soportada; no prometer una relación persistida multi-evidence que no existe.

## 9. Retry, fallos e idempotencia

Actual: el orquestador usa attempted_ocr/attempted_vision para limitar un intento
por canal por página en una invocación; AVAILABLE_ONLY no los ejecuta. Puede pasar
de OCR fallido a Vision bajo AUTO; ALLOW_OCR no. Excepciones OCR pueden quedar
absorbidas en esa frontera: el executor nuevo debe conservar diagnóstico/evento.
La política de NEEDS/review puede detener escalada antes; no todo review requiere Vision.

Ollama _execute_task tiene timeout configurado (default 180 s), sin retry genérico
automático para timeout/transporte. JSON malformado admite retry configurable 0–1,
default 0. Vacío, truncado, schema inválido y errores HTTP no son texto canónico.
Repetir requests externos/force puede reejecutar indefinidamente: no existe un
presupuesto global duradero que certifique agotamiento entre requests.
OCR no tiene retry/sandbox temporal general; tiempo de ejecución del motor necesita
límite explícito antes de certificar terminación. No inventar latencias legacy null.

Vision usa input fingerprint de documento/modelo/prompt/modo/tarea/región y páginas
con hash de imagen, y task fingerprint de modelo/prompt/tarea/página/imagen/región.
COMPLETED puede reutilizarse; aun en cache algunos caminos llaman client.probe:
cache no equivale hoy a cero contactos con proveedor. Structure_only valida estructura
usable antes del reuse y admite force_retry_on_unusable_structure. General PARTIAL
puede reejecutar páginas ya completadas de su lote; fingerprint por lote no proporciona
idempotencia óptima por tarea/página. Evitar duplicar trabajo con planes de una tarea
por página/región y reuse validado antes de render/probe cuando sea posible.

OCR actual hace upsert por page/engine/scope/region y sobrescribe texto/version/status.
No usa fingerprint de render/config ni skip previo de completados. NormalizedContent
también se actualiza por identidad de fuente. No asumir generaciones inmutables.

Invariantes propuestos: no borrar Native; no sobrescribir percepción completada válida
con un fallo; completar páginas independientemente; registrar cada intento real;
JSON inválido sin transcript; retry budget finito por job/tarea/generación, sin reset
silencioso por nuevo request; determinista no soportado no reintenta. Cambios de
modelo/provider/config invalidan sólo la capacidad afectada, no Native ni otras tareas.
Si no puede persistirse la nueva generación sin perder historia, dejar STALE/deferred
runtime y requerir decisión explícita de versionado, no reutilizar ni sobrescribir.

## 10. Control de ejecución, métricas y local-first

Cap por lote/páginas/regiones/tareas/requests, límite de render/bytes/tokens y retry
budget antes de ejecutar. La configuración Vision ya limita páginas (default 4),
zoom/tamaño/dimensión y tokens por tarea. No cambiar budgets ni prompts por Tender.
Coste arquitectónico: OCR sólo por jobs pendientes y motor elegido; Vision sólo por
tareas pendientes con necesidad visual. No inferir coste económico de ese conteo.

ProviderMetric/ValidationSnapshot en document_intelligence_validation_metrics ya
separan artefactos de execution_event, calls/latency opcionales, timeout/truncation y
configuration. Reutilizar collector. Total páginas viene de page_ids; estados por
capacidad de perception. Agregar al REPORTE del plan los conteos sufficiency,
OCR/Vision eligible/planned/deferred/skipped y retry ordinal/reason en eventos.
No se pueden inferir llamadas ejecutadas/reintentos sólo contando filas DB ni asumir
cero para NOT_MEASURED. «Avoided calls» sólo sobre unidades planificables rechazadas
por razón explícita, no total páginas menos inferencias (hay múltiples regiones/tareas).
No requiere nuevo stream, tabla ni servicio; mantener retención acotada de reportes.

Native y render son locales/deterministas para input/runtime fijados. OCR es local,
pero versión/pesos/config afectan reproducibilidad; Paddle no garantiza descarga cero
si assets faltan. Ollama requiere runtime/modelo local disponibles; disabled/unavailable
es estado explícito, sin fabricar texto y sin fallback cloud. Aprobación de proveedor
y corpus es independiente de elegibilidad; un futuro run real necesita autorización
exacta. No se ejecutó ni siquiera probe en esta revisión.

## 11. Matriz sintética propuesta — sin ejecución

| ID | Contrato y evidencia de prueba |
|---|---|
| VP10 | Texto Native suficiente para tarea → plan vacío y spies de providers/probes en cero |
| VP11 | Página escaneada sin Native, render válido → OCR elegible, no ejecutado al planificar |
| VP12 | Fixture OCR con texto conocido → persistir/normalizar/consumir; prueba real OCR separada opt-in |
| VP13 | OCR conserva engine/version/idioma/resultado/región/generación y fuente exacta |
| VP14 | Ningún resultado OCR toma método NATIVE ni native-page como identidad |
| VP15 | Texto suficiente + imagen decorativa sustentada → cero Vision/OCR innecesarios |
| VP16 | Necesidad visual declarada con evidencia de región → Vision elegible; no afirmar interpretación general de diagramas |
| VP17 | AVAILABLE_ONLY mantiene eligibility/gap y cero adquisición/probes |
| VP18 | Proveedor ausente → unavailable/deferred con página conservada; sin transcript |
| VP19 | Timeout/fallo visual no borra ni cambia Native/normalizado/derivados independientes |
| VP20 | OCR fallido → sólo escalada permitida por task/policy/budget; ALLOW_OCR no ejecuta Vision |
| VP21 | Tarea equivalente completada → reuse sin HTTP, recognize ni render innecesario |
| VP22 | Modelo/engine/config cambia → invalidar sólo esa tarea; nueva generación o deferred seguro, nunca overwrite silencioso |
| VP23 | Native+OCR+Vision con grounding comparable → un Scope lógico y tres fuentes auditables |
| VP24 | Valores/owners contradictorios → review, sin preferencia Vision ni votos de certeza |
| VP25 | Provenance OCR/Vision exacta llega a Scope/hijos y bridges Requirements/Requested Evidence |
| VP26 | Sin imagen/texto válido no fabricar página, transcript, bbox, provenance ni confidence |
| VP27 | Retry agotado o fallo determinista → terminar con evento/razón; nueva llamada no borra agotamiento |
| VP28 | ST10–ST20/V.4a conservan UNKNOWN/continuidad/ownership seguro |
| VP29 | SC01–SC24/DC/V.4b Native mantienen comportamiento y revisión humana |
| VP30 | Unsupported native V.3a sigue representado; no extracción ni proveedores |
| VP31 | AUTO OCR histórico no cambia inadvertidamente; plan selectivo elige motor explícito |
| VP32 | Blanco real, texto-cabecera+escaneo, vectores y perfil desconocido se distinguen; sin confiar en char_count |
| VP33 | Región decorativa no se decide por filename ni sólo area_ratio |
| VP34 | Éxito OCR previo + fallo posterior no pierde evidencia ni su generación |
| VP35 | Completar página 1, fallar página 2 → reintento sólo de pendiente con contexto seguro |
| VP36 | STRUCTURE_SCOPE no llena transcripción faltante; detail task no dispara estructura ya suficiente |
| VP37 | Imagen/render/config/hash diferente no reutiliza percepción incompatible |
| VP38 | Modelo/pesos ausentes no descargan ni llaman cloud; estado explícito local |

Mocks prueban control/contratos y no calidad OCR/Vision. Calidad real exige protocolo
separado y autorización exacta; nunca Tender #002 como tuning/fixture/Golden.

## 12. Secuencia de implementación recomendada

1. Aceptar contrato de suficiencia por tarea, política explícita (sin alterar AUTO
   histórico), no-overwrite y budgets. Documentar ADR; usar tipos runtime neutrales.
2. V.4c1: planificador puro + executor OCR selectivo con capacidades existentes,
   reuse/timeout/eventos, fuentes/normalización y adapters OCR de dominio. Cerrar
   VP10–VP15/17–VP22/25–VP30 y negativos; sin ejecutar modelos reales por defecto.
3. V.4c2: tareas Vision independientes, crop/hash reales cuando corresponda, cache
   sin probes, retry finito y eventos; no chaining automático de estructura→detalle.
   Cerrar VP16/23–VP24/31–VP38 y regresión completa V.4a/V.4b.
4. Sólo después, calibración real autorizada de OCR/Vision y nueva evaluación ciega
   bajo otro freeze/permiso. Esta revisión no los autoriza ni crea run_id.

## 13. Esquema y riesgos de generación

Planificación, estados de ejecución, métricas y primera adquisición/reuse acotados
pueden usar modelos/provenance existentes y reportes runtime: **sin migración ni
nuevo enum persistido**. No declarar equivalencia de esos estados a confianza.

Límite explícito: PageOcrResult tiene unique page/engine/scope/region sin generación,
y los writers actuales sobrescriben. Su ID no garantiza historial inmutable ni
cambio de engine_version. No explotar NULLs de unique para insertar generaciones
ambiguas. La versión inicial sin esquema debe prohibir overwrite de completados;
si versión/config cambia, invalidar/revisar y diferir la nueva adquisición cuando
no se pueda conservar lineage. Esto satisface el fallo cerrado, no certifica un
catálogo de generaciones durable.

Si se exige refresco automático con varias generaciones OCR históricas referenciables,
se necesita una decisión de persistencia explícita: generación/fingerprint en la
identidad OCR y ajuste mínimo del unique/lineage, o un contrato aceptado de artefactos
inmutables referenciados. No esconder ese cambio en warnings ni prometer que ya existe.
Sería revisión ADR/esquema separada antes de implementarlo; aquí no se crea migración.
Vision tiene soporte de fingerprints/artefactos mejor, pero tampoco se debe sobreescribir
éxitos con reintentos. Las 59 diferencias de índices históricas no pertenecen a V.4c.

## 14. Archivos probables de implementación futura

No modificados en esta revisión:
- Nuevo backend/app/document_perception_planner.py: decisión pura y PerceptionPlan.
- Nuevo backend/app/document_perception_executor.py: política/budgets/eventos/reuse,
  sobre providers existentes, sin nueva infraestructura.
- backend/app/main.py: reutilizar helpers/guardas; mantener endpoints históricos.
- backend/app/document_structure_orchestrator.py: integración por capacidad sin
  convertir resolución estructural en señal universal de suficiencia.
- backend/app/ocr.py: timeout/selección explícita/offline, sin instalar motores.
- backend/app/content_normalization.py: preservar fuentes; no refresh destructivo.
- backend/app/document_intelligence_sources.py: binding/generación/coords OCR/Vision.
- backend/app/ollama_vision.py y local_vision.py: ejecución por tarea/crop/reuse/probes;
  no prometer transcripción independiente mientras siga acoplada a estructura.
- Nuevo backend/app/ocr_scope_adapters.py y ocr_scope_evidence.py: tres contratos de
  dominio y resolución exacta OCR, reutilizando gramática pura V.4b sin relabel Native.
- backend/app/scope_detail_adapters.py, scope_attribute_adapters.py,
  scope_quantity_adapters.py y sus materializadores: registro/resolución OCR,
  conservando ScopeLogicalEvidence/scope-logical-v2.
- backend/app/document_intelligence_validation_metrics.py sólo si se requiere extensión
  runtime compatible; preferir reportar conteos del plan y eventos con contrato actual.
- Nuevos backend/tests/test_selective_perception.py y test_ocr_structured_coverage.py;
  regresiones document_structure_orchestrator/document_intelligence/materializadores,
  SC/ST, V.3a y mocks de proveedores. No nuevas reglas Requirements/Requested Evidence.
- Nuevo ADR del contrato selectivo. Modelos/Alembic fuera de la ruta acotada; su
  eventual cambio requiere decisión separada por el problema de generaciones.

Riesgos a revisar antes de codificar: significado de suficiencia vs review; cobertura
visual no medible por logos/char_count; AUTO OCR divergente; reproducción de render;
cache que hace probes; OCR mutable y presupuesto no duradero; transcripción Vision
acoplada a estructura; OCR sin adapters predeterminados; parsers de dominio acotados.
No son razones para incorporar percepción universal ni certificar calidad sin pruebas.
La revisión de arquitectura está completa para aceptar/rechazar este límite acotado.

## 15. Integridad y entrega

Se creó únicamente este reporte sin rastrear. Sin cambios de aplicación/tests,
configuración, modelos, esquema, migraciones o documentos previos; sin DB ni proveedores.
No se ejecutaron tests/compileall por ser revisión estática. Sin stage/commit/push,
Attempt #3, nuevo run_id o relectura semántica del corpus. Verificación final de hashes
y Git documentada en la entrega.

Verificación final: 437 archivos previos conservan sus hashes;
107 artefactos históricos intactos, incluidos Attempts #1/#2 y adjudicación.
HEAD sin cambios; diff rastreado y staging vacíos; git diff --check PASS.

```text
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
?? backend/reports/selective_visual_perception_v4c_architecture.md
?? backend/reports/source_effect_qwen8b_baseline_v1.json
?? backend/reports/source_effect_qwen8b_bounded_v3.json
?? backend/reports/source_effect_qwen8b_calibrated_v2.json
?? backend/reports/source_effect_qwen8b_fully_bounded_v4.json
?? backend/reports/structural_trust_safety_v4a.md
?? backend/reports/structured_coverage_v4b_architecture.md
?? backend/reports/v4b_drift_baseline_certification.json
?? backend/reports/v4b_drift_baseline_certification.md
?? docs/adr/0011-native-structured-coverage.md
```

MVP-06.V.4c SELECTIVE VISUAL PERCEPTION ARCHITECTURE COMPLETE — READY FOR IMPLEMENTATION REVIEW
