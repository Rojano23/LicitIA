# MVP-06.V.4b — Structured Coverage: revisión de arquitectura

Base verificada: `cb27af54292ead1b5562f4d0a3de2637948d8d25`.
Investigación estática; no implementación, tests, consultas DB, adquisición ni ejecución ciega.
Los conteos de Attempt #2 y los mínimos adjudicados son antecedentes proporcionados,
no objetivos de extracción ni fixtures. No se reabrió el corpus.

## 1. Conclusión y causalidad

La hipótesis es parcialmente correcta y necesita precisión: Native SÍ es una fuente
canónica enumerada y transportada hasta Scope. Está varada en la selección del
adaptador predeterminado, no en la extracción ni en la ausencia de una abstracción.
`document_intelligence_sources.py` enumera NormalizedContent NATIVE_PDF/NATIVE_TEXT
con texto como `native-page:<DocumentPage.id>`, método NATIVE y contrato NATIVE_TEXT_V1.
`scope_detail_materializer.py` les construye contexto neutral de transcripción,
estructura e identificadores. `_default_adapters` en `scope_detail_adapters.py`
instala sólo VisionScopeDetailAdapter; su `supports` exige VISION y
DETAIL_TRANSCRIPTION. Por tanto Native termina UNSUPPORTED con cero candidatos.

Existe NeutralScopeSemanticAdapter compatible con Native/OCR/Vision, pero sólo se
agrega si se pasan semantic_providers explícitamente. No tiene proveedor por defecto.
La ausencia de inferencias no es por sí sola garantía de cobertura semántica.
La ruta AVAILABLE_ONLY predeterminada explica genéricamente cero ScopeDetails para
un expediente sólo Native. Esto no prueba que todo texto Native sea utilizable ni
que todos los casos adjudicados sean recuperables mediante reglas deterministas.

La cascada se confirma en el flujo que itera los ScopeDetails persistidos para
materializar hijos: cero padres implica cero llamadas útiles a Attributes/Quantities.
También hay DOS brechas independientes: los adaptadores predeterminados de ambos
hijos sólo consumen Vision DETAIL_TRANSCRIPTION con detail_row. Producir padres
Native sin ampliar esos adaptadores dejaría ambos hijos UNSUPPORTED.

## 2. Flujo exacto de Scope

Puntos de entrada de dominio: materialize_document_scope_details (AVAILABLE_ONLY);
el protocolo 06v manda estructura → Scope → hijos. El replay canónico existente
(document_intelligence_calibration_replay.py, iteración de materialización) ejemplifica
esta secuencia; no se ejecutó ni se alteró. El runner de freeze no es el extractor.

1. Consulta DocumentPage ordenadas y valida pertenencia Tender/documento.
2. `_enumerate_persisted_artifacts_for_document`: Vision con reselección de lineage
   por tarea/fingerprint, OCR persistido y Native normalizado no vacío (una entrada
   por página; el orden actual conserva la primera normalización elegible).
3. `load_document_transcriptions`: observaciones normalizadas con generación e
   identidad de página/versión; ruteo neutral por capacidad. `load_page_structure`,
   `guard_structure`, comparación de identificadores y advance_continuity producen
   el contexto estructural actual. Continuidad inválida impide confianza estructural.
4. Limpia detalles de artefactos DESELECTED. Para cada activo usa savepoint y
   `_scope_artifact_context`, que incorpora la observación concreta del artefacto.
5. Selecciona el PRIMER adaptador compatible; no compone automáticamente salidas.
   Vision transforma parsed_supply_rows con fragmento, dominio y ownership; permite
   herencia sólo desde un único segmento resuelto y compatible, sin conflicto.
   El adaptador neutral opt-in usa discover_scope_semantics y su contrato validado.
6. Guardas comunes: excerpt debe existir en observación ACTIVE de ese artefacto,
   de calidad RELIABLE/REVIEW_REQUIRED. Riesgos críticos limpian ownership y fuerzan
   UNRESOLVED/review. Transcripción revisable propaga review; estructura no resuelta
   elimina ownership de candidatos que lo estaban afirmando.
7. `replace_scope_details_for_artifact`: valida identidad de reemplazo, campos,
   dominio y aplicabilidad; ITEM exige ownership, UNRESOLVED exige review.
   Borra el lote anterior del artefacto y reinserta TenderScopeDetail.
8. Fingerprint semántico incluye documento/página, dominio, descripción, ownership,
   método, artefacto, locator, excerpt y quantity/unit. UniqueConstraint está
   acotada al artefacto. Esto permite contenido reproducible, NO estabilidad de UUID:
   reemplazar reinserta filas y puede afectar hijos por cascada. No hay caché Scope
   que incorpore por sí misma una versión de política de adaptador.

Ceros posibles: ninguna página/normalización elegible; texto vacío; sólo artefactos
fallidos/deseleccionados/no compatibles; tarea Vision distinta; filas sin fuente o
sin dominio admisible; proveedor opt-in ausente o sin obligaciones; grounding que
filtra todo; candidatos inválidos o fallos de persistencia con rollback; limpieza
por reselección. Ambigüedad puede persistir candidatos review y NO implica siempre
cero. El catch-all actual convierte excepciones por artefacto a UNSUPPORTED: es una
limitación diagnóstica real, no evidencia de inexistencia de obligaciones.

## 3. Flujo exacto de Attributes

`materialize_scope_attributes_for_scope_detail` carga el padre; resuelve artefacto
VISION, OCR o NATIVE con verificaciones de documento/página/lineage. Native actualmente
reconstruye payload desde DocumentPage.text, no desde la generación NormalizedContent
que alimentó Scope: requiere corregir/alinear lectura para el nuevo camino.
`default_scope_attribute_adapters` contiene sólo VisionDetailTranscriptionScopeAttributeAdapter.
Exige detail_row en locator, task DETAIL_TRANSCRIPTION, fila válida y overlap con
excerpt del padre. Extrae únicamente brand/model explícitos; valores deben estar
contenidos en el fragmento. Emite relación UNSPECIFIED, confidence None y review
heredado de padre/fila. No es un extractor general de todos los atributos técnicos.
Valida candidatos y reemplaza por padre/artefacto en savepoint; comprueba ownership
documental y provenance. Fingerprint incluye padre, artefacto, atributo, valor,
unidad/relación y fuente; rechaza duplicados dentro del lote.

Ceros: padre inexistente; clave o lineage inválida; adaptador incompatible; fila
inexistente/incorrecta; ningún brand/model; valor sin grounding; excepción de
extracción/validación/persistencia. Diferencia NO_ATTRIBUTES, UNSUPPORTED e
INVALID_EVIDENCE. Integración semántica separada en scope_attribute_integration.py
requiere proveedor explícito y ofrece duplicados/conflictos contra deterministas;
no es una adquisición automática ni reconciliación global de padres.

## 4. Flujo exacto de Quantities

`materialize_scope_quantities_for_scope_detail`: padre → resolver artefacto
VISION/OCR/NATIVE → primer adaptador compatible → validar → reemplazo transaccional.
Native también usa DocumentPage.text; se debe alinear con generación del padre.
El adaptador por defecto VisionDetailTranscriptionScopeQuantityAdapter exige fila
DETAIL_TRANSCRIPTION, locator detail_row y overlap con el padre. Su ruta actual
extrae una cantidad terminal entre paréntesis, decimal con punto y unidad conocida;
usa Decimal y mapa unidad→measure_kind, relación EXACT, confidence None, review
heredado. No cubre arbitrariamente tablas, rangos o numerales en cualquier posición.
La validación de dominio soporta EXACT/MINIMUM/MAXIMUM/RANGE/UNSPECIFIED, exige
grounding raw/unit, coherencia de campos y orden de rango. El fingerprint de cantidad
es de valor/relación/unidad (no incluye capacidad), pero el reemplazo/constraint
sigue acotado por padre/artefacto: no deduplica padres Native/Vision.

Ceros: los mismos fallos de padre/artefacto/adaptador/persistencia; sin cantidad
terminal compatible; unidad desconocida; decimal no válido; excerpt sin grounding.
La integración semántica opcional scope_quantity_integration.py conserva duplicados
y conflictos frente a deterministas bajo un padre; no soluciona duplicidad de Scope.
Restaurar Scope no elimina estas limitaciones de cobertura.

## 5. Matriz de capacidades actuales

| Evidencia | Scope predeterminado | Attributes predeterminado | Quantities predeterminado | Provenance/trust | Attempt #2, antecedente |
|---|---|---|---|---|---|
| PDF Native extraído, sin normalizar | No se enumera solo por page.text | Resolver lo lee si ya existe padre Native; sin adaptador | Igual | DocumentPage, NATIVE_PDF; no certificado | 253 páginas Native reportadas |
| Native normalizado | Se enumera y rutea; UNSUPPORTED por adaptador | Resolver Native existe; adaptador no | Igual | native-page + NormalizedContent id/hash/generación en percepción; review | Disponible según flujo/antecedente; no nueva auditoría DB |
| Estructura/ScopeSegments | Contexto de ownership, no obligación por sí misma | Indirecta por padre | Indirecta por padre | Resolución/segmento, continuidad e identificadores; V.4a | Estructura previa a V.4a; no recertificada |
| Vision DETAIL_TRANSCRIPTION | Sí, parsed_supply_rows y guardas | Sí, brand/model en fila | Sí, forma terminal soportada | analysis/page-result/locator; review propagado | Sin inferencias reportadas |
| Vision STRUCTURE_SCOPE | No sustituye transcripción de detalle | No | No | No adquirir detalle implícitamente | Sin inferencias reportadas |
| PageOcrResult persistido | Enumerado, sin adaptador por defecto | Resolver existe, adaptador no | Resolver existe, adaptador no | ocr-result, engine, región; review/no certeza | Sin OCR reportado |
| OCR normalizado legado | Observación neutral; no default de detalle | No default | No default | normalized-content, review | No adquisición reportada |
| Transcripción neutral + semantic_providers opt-in | Contrato existente compatible | Integración semántica separada | Integración semántica separada | grounding y review; proveedor explícito | No proveedor instalado/ejecutado en plan |

## 6. Alternativas y recomendación

| Opción | Evaluación |
|---|---|
| A: ampliar VisionScopeDetailAdapter a Native | Rechazada: mezcla percepción Vision con parsing Native y facilita provenance falsa |
| B: adaptadores Native bajo contratos existentes | Recomendada: módulos pequeños, mismo pipeline y guardas; tests aislados, sin esquema nuevo |
| C: nueva abstracción neutral | Rechazada como nueva capa: ScopeDetailEvidenceArtifact, PerceptionEvidence y RoutingResult ya existen |
| D: activar NeutralScopeSemanticAdapter con LLM | No recomendada para este slice: es opt-in y no proporciona cobertura determinista sin proveedor; ampliar autorizaciones no está permitido |

B debe reutilizar contratos neutrales y validación semántica existente donde aplique.
Proponer parser determinista acotado de obligaciones explícitas (filas o frases con
anclas verificables), no regla de que cualquier PARTIDA o sustantivo sea suministro.
Publicar su gramática y no soportados antes de codificar; nunca prometer recall
universal. Attributes necesita un adaptador Native propio de etiquetas/valores
explícitos; Quantities uno de campos enlazados, Decimal y unidades/relaciones
aceptadas. Compartir sólo resolución de fuente/anchors y helpers pertinentes;
no generar parsed_supply_rows Vision para reutilizar falsamente esos adaptadores.

## 7. Provenance y trust propuestos

Conservar tender/document/page ids, número y revisión documental canónica, método
NATIVE, native-page:<id>, contrato versionado, locator y excerpt literal. Retener
NormalizedContent.id + content_sha256 como generación exacta; extracción disponible
como DocumentPage.extraction_method y hash original/documental existente. No existe
una identidad de job de extracción que deba inventarse. Los modelos Scope no tienen
FK normalized_content_id: locator puede codificar referencia/generación y offsets
con formato versionado y límite 512, comprobados al resolver. Documento y revisión
se obtienen de su identidad existente; no inventar versión inmutable si el contrato
actual no la ofrece. Incluir hash verificable sin duplicar contenido en locator.

Los spans sólo pueden ser offsets de texto canónico cuando se calculen y validen;
no hay autorización para inventar bbox ni coordenadas visuales. Identidad estructural
se conserva por scope_segment_id/candidate_item_key sólo si las guardas V.4a la
sustentan. source_analysis_id/source_page_result_id deben ser null para Native.
El hijo debe resolver esa misma generación, no usar silenciosamente page.text como
si fuera idéntico al texto normalizado. Si falta o difiere, INVALID_EVIDENCE/review.

Native legacy se normaliza hoy como Quality.REVIEW_REQUIRED con
PERCEPTION_FIDELITY_NOT_CERTIFIED. Conservar esa política: una extracción terminada
no autoriza elevar confidence. Candidato grounded puede persistir review; estructura
ambigua pierde ownership y permanece UNRESOLVED. Trusted requiere evidencia fiable,
obligación explícita validada, owner inequívoco cuando aplique, sin conflictos y
política aceptada o decisión humana. V.4b no introduce certificación automática de
Native ni escala de confianza nueva. Sin fuente/soporte: unavailable/unknown o cero
candidatos con razón, nunca obligación inventada. Review no es bloqueo comercial.

## 8. Deduplicación e idempotencia

No existe actualmente identidad lógica cross-capability de Scope. La reselección
Vision por fingerprint sólo resuelve generaciones de la misma tarea; no solapa
Native/OCR. El fingerprint Scope depende de capacidad/artefacto y descripción;
el dedupe del adaptador neutral sólo opera dentro de su extracción.

Invariante mínimo propuesto: antes de persistir, agrupar candidatos de una misma
obligación por documento/versión, página, owner explícito, dominio/tipo y ancla
textual inequívoca. No usar sólo número de partida, descripción parecida o cantidad;
un owner puede tener varias obligaciones legítimas. Coincidencia exacta verificable
selecciona una representación canónica por política estable, conservando las otras
observaciones en los artefactos canónicos originales. No eliminar ni mutar percepción.
Conflicto de identidad/valores impide fusión confiada; emitir review y no contar dos
hechos como confirmados. Si no hay ancla comparable, no afirmar equivalencia: dejar
el grupo sin resolución confiada. No resolver paráfrasis con similitud heurística.

La selección debe operar sobre candidatos del documento, no sólo orden de ejecución
por artefacto, e incluir limpieza de derivados no seleccionados. Conservar Vision
como ruta válida; Native no gana sólo por ser Native. La calidad y el grounding son
anteriores al desempate estable. El consumidor debe distinguir observaciones en
review de un hecho lógico seleccionado. El contrato de esa selección y sus
resultados diagnósticos necesita aceptación arquitectónica antes de implementar.

Para repetición, proponer reconciliación por fingerprint del lote en lugar de
borrado/reinserción incondicional: conservar IDs de candidatos sin cambios y sus
hijos; reemplazar sólo obsoletos. Tests deben distinguir contenido idempotente de
UUID estable y comprobar cascadas. No reutilizar derivaciones de política anterior
sin verificar versión/generación. Esto no reescribe intentos históricos.

## 9. Límite visual

Recuperable: únicamente obligaciones/campos explícitos ya presentes en texto Native
canónico usable y vinculables al owner correcto. No recuperable aquí: imágenes,
texto ausente, tablas cuya asociación se perdió al extraer, diagramas y cualquier
lectura que requiera OCR/Vision/modelos. Deben permanecer unavailable/review;
la fase posterior de percepción de PDFs de imagen sigue siendo necesaria.

## 10. Matriz sintética propuesta (no ejecutada)

| ID | Contrato a probar |
|---|---|
| SC01 | Scope textual explícito Native produce detalle con cero Vision/proveedores |
| SC02 | Prosa no contractual/no procurement no fabrica detalle |
| SC03 | Atributo explícito de ítem Native conserva etiqueta/valor y parent correcto |
| SC04 | Cantidad+unidad enlazadas producen Decimal y measure_kind correctos |
| SC05 | Sin identidad válida, atributo no se asigna a otro owner; review/no trusted |
| SC06 | Misma guarda para cantidades |
| SC07 | Ambigüedad V.4a conserva evidencia, UNKNOWN/review y sin outgoing confiado |
| SC08 | Provenance Native referencia página y generación normalizada verificable |
| SC09 | No se crean analysis/page-result ni método Vision sintéticos |
| SC10 | Native+Vision equivalentes producen un único alcance lógico seleccionado |
| SC11 | Varios ítems y varias obligaciones de un ítem permanecen distintos |
| SC12 | Repetir conserva contenido, IDs acordados e hijos; sin duplicados |
| SC13 | Unsupported native no aborta Tender ni fabrica páginas |
| SC14 | Imagen sin texto no produce detalles inferidos |
| SC15 | Ruta Vision válida conserva comportamiento y provenance |
| SC16 | Native/Vision en conflicto no fusionan silenciosamente identidad/valores |
| SC17 | Generación faltante/alterada o documento/página ajenos fallan explícitamente |
| SC18 | Normalizado distinto a page.text: hijos leen fuente exacta del padre |
| SC19 | FAILED/DESELECTED no resucitan; nueva selección limpia sólo derivados |
| SC20 | Unidades desconocidas, decimales ambiguos, rangos inválidos → review/no guess |
| SC21 | Mismo número en distinta página/documento y obligaciones similares no se colapsan |
| SC22 | Error de adaptador/persistencia no se reporta como ausencia de obligaciones |
| SC23 | Orden Native/Vision invertido no cambia selección ni incrementa confidence |
| SC24 | Review del padre/percepción se propaga a hijos; sin promoción por parser exitoso |

## 11. Esquema, archivos y slice propuesto

No se requiere esquema/migración/enum nuevo para candidatos Native: los métodos y
campos ya existen, los hijos admiten NATIVE y los contratos son neutrales. Puede
resolverse la referencia de generación mediante locator versionado verificable.
No hay soporte relacional actual para múltiples evidencias de una única fila Scope;
la propuesta mínima conserva fuentes alternativas en percepción y selección
reproducible, sin afirmar que las almacena como relaciones multi-evidence. Si se
exige auditoría persistida de esas relaciones o spans como columnas consultables,
es una ampliación de dominio con ADR/esquema separado, no migración implícita.

Archivos probables para implementación posterior (ninguno modificado en esta tarea):

- Nuevos backend/app/native_scope_detail_adapter.py,
  native_scope_attribute_adapter.py y native_scope_quantity_adapter.py.
- backend/app/scope_detail_adapters.py: registro y guardas, selección compartida.
- backend/app/scope_detail_materializer.py: reconciliación previa al persistido.
- backend/app/scope_details.py: actualización idempotente y limpieza controlada.
- backend/app/scope_attribute_adapters.py y scope_quantity_adapters.py: registro Native.
- backend/app/scope_attribute_materializer.py y scope_quantity_materializer.py:
  lectura de generación Native exacta del padre.
- backend/app/document_intelligence_sources.py: sólo si se necesita helper compartido
  de resolución de generación; no cambiar política global de calidad por comodidad.
- Nuevo backend/tests/test_native_structured_coverage.py y regresiones existentes
  test_scope_detail_materializer.py, test_structural_trust_safety.py;
  familias de materialización Attributes/Quantities e integración DI afectadas.
- ADR específico para selección lógica multicapa/idempotencia y documento de contrato
  del parser Native. No cambiar Requirements ni Requested Evidence.

Recomendar un slice de implementación revisable: (1) aceptar contrato de gramática,
anchors, revisión y reconciliación; (2) adaptadores Native de Scope e hijos sobre
los mismos artefactos, sin proveedores; (3) selección cross-capability e idempotencia;
(4) SC01–SC24 y regresiones pertinentes en licitia_test. Sólo después evaluar nueva
validación ciega bajo autorización separada. No fijar resultados al conteo adjudicado.

Riesgos: falsos positivos en prose/encabezados; pérdida de asociación de columnas;
herencia del owner equivocado; confianza promovida; duplicados o pérdida de campos
al seleccionar capacidad; pérdida de hijos al reinsertar padres; cambio de generación
sin invalidación; excepciones ocultas como UNSUPPORTED. Requieren pruebas de contrato,
no corpus ciego como fixtures. La revisión está completa para decisión de arquitectura;
no certifica calidad real ni garantiza cobertura de todos los atributos posibles.

## 12. Alcance de esta entrega

Sólo se creó este reporte técnico sin rastrear. Código, tests, configuración, DB,
schema, migraciones y reportes históricos no se modificaron. No se ejecutaron tests
ni compileall por tratarse de inspección estática. Cero proveedores; sin Attempt #3,
run_id, stage, commit ni push. HEAD base conservado. Verificación final de Git y
hashes históricos se reporta en la entrega.
