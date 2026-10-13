# ADR-0010 — Document Intelligence Capability Routing

**Estado:** Proposed — pendiente de aceptación humana de arquitectura

**Fecha:** 2026-10-13

## Contexto

La recuperación de información documental combina texto nativo, OCR y Vision.
La fidelidad textual, la fidelidad estructural y la asistencia semántica son
capacidades independientes: una misma página puede tener texto nativo fiable y
requerir otra fuente para estructura. La presencia de texto no demuestra su
calidad, y una transcripción fallida no invalida por sí misma estructura válida.
La selección debe conservar provenance y desacuerdos sin convertir percepción
en autoridad contractual.

## Decisión

Introducir una frontera neutral de Document Intelligence, inicialmente aislada
del runtime productivo, con evidencia validada y routing puro por capacidad.

El vocabulario neutral es `TRANSCRIPTION`, `STRUCTURE` y `SEMANTIC_ASSIST`,
equivalente respectivamente a `VISION_TRANSCRIPTION`, `VISION_STRUCTURE` y
`VISION_SEMANTIC_ASSIST` en la definición del slice. El canal de percepción es
independiente: `NATIVE`, `OCR` o `VISION`. Los nombres históricos `NATIVE_PDF` y
`NATIVE_TEXT` se normalizan al canal `NATIVE`; Ollama/Qwen son metadata del
proveedor/modelo, nunca un canal documental.

Native se prefiere para transcripción confiable. OCR es el siguiente recurso
para recuperación textual. Vision es un especialista controlado para texto
insuficiente, estructura visual o asistencia acotada. La preferencia sólo opera
entre evidencias compatibles: nunca resuelve un desacuerdo confiable por fecha,
orden de carga o canal. Una disponibilidad declarada no ejecuta un proveedor;
si haría falta Vision real, el resultado lo señala y deja la ejecución diferida.

Cada evidencia identifica página, documento, versión cuando existe, artefacto,
generación/analysis, locator/coordenadas, texto exacto, capacidad, diagnósticos y
lineage. La confianza conserva su escala declarada; no se inventan umbrales.
La calidad se declara explícitamente por capacidad y por el adaptador; omitirla
requiere revisión. Un resultado vacío, fallido o DESELECTED no cuenta como
percepción confiable. Los contratos existentes de estructura se reutilizan.

`STRUCTURE_SCOPE` corresponde a estructura; `DETAIL_TRANSCRIPTION` corresponde
a transcripción. Sus resultados se evalúan por separado. Un fallo de Vision u
OCR en una capacidad no elimina evidencia válida de otra.

La continuidad pertenece al estado estructural neutral de LicitIA. Puede enlazar
páginas con canales distintos si hay prueba estructural válida, identidad de
documento/versión consistente y adyacencia. Una estructura desconocida, un
conflicto o una continuación sin prueba invalida ese límite y no transporta la
clave abierta anterior. Un inicio estructural nuevo e independiente puede
restablecer un estado válido; nunca se recupera una continuidad por texto viejo.

Los desacuerdos conservan ambas evidencias y requieren revisión. Los
identificadores críticos se reciben como bindings fundamentados en fragmentos
exactos; DI no descubre ni normaliza identidad contractual. Las diferencias
textuales exactas se tratan conservadoramente como conflicto, sin intentar
resolver equivalencias semánticas en este slice.

Los estados de routing son `RESOLVED`, `REVIEW_REQUIRED` y `UNAVAILABLE`.
`RESOLVED` sólo expresa percepción confiable para la capacidad solicitada.
La asistencia semántica debe ser acotada y fundamentada, y permanece siempre
`REVIEW_REQUIRED`. Ningún resultado otorga autoridad contractual.

Requirements, Evidence, Scope, Source Effects y Alternative Compliance conservan
sus decisiones de dominio y la autoridad humana. Su integración transversal
corresponde a 06.R.2. La política Source Effect Qwen NO-GO permanece vigente.

## Persistencia y consecuencias

No se agregan tablas ni migraciones. Páginas, NormalizedContent, PageOcrResult,
DocumentVisionAnalysis/PageResult y resoluciones estructurales existentes
proveen las identidades y artefactos para adaptadores posteriores. El contrato
neutral es un valor derivado; no requiere una nueva verdad persistida en R.1.
Los contratos de dominio legados no transportan toda la provenance neutral;
los tests de shape conservan el objeto DI junto a ellos y no certifican una
integración productiva sin pérdida. R.2 debe mantener esa información al integrar.

Para la brecha comprobada en Requirements, 06.R.2a permite incluir provenance
neutral en la evidencia de dominio mediante una columna JSONB nullable,
`RequirementCandidateEvidence.perception_provenance`. Su contrato Pydantic es
tipado y versionado; conserva fuentes consideradas, selección segura, conflictos,
diagnósticos y lineage. La identidad lógica de la evidencia permanece separada
de las observaciones de percepción y conserva su deduplicación existente.
Los helpers exigen snapshots completos que retengan observaciones previas con
lineage explícita, sin inferir deselection. NULL identifica provenance legacy
no disponible; no hay backfill especulativo. Datos inválidos fallan explícitamente.
Esta excepción de persistencia no conecta todavía el discovery transversal R.2.

La selección ACTIVE/DESELECTED y la evaluación de calidad son entradas explícitas,
no inferencias del routing. No se reemplazan ahora las selecciones históricas del
runtime. Su convergencia y calibración se revisarán en slices posteriores.

Los tests sintéticos demuestran contratos, routing, lineage y fail-closed;
no certifican extracción visual/OCR ni calidad semántica. No se autorizan modelos
reales en R.1. La calibración real exige una fase controlada posterior y autorización
explícita. Tender #002 permanece ciego hasta MVP-06.V, después de MVP-06.R.

## Integración productiva 06.R.2 — pendiente de aceptación arquitectónica

La frontera ORM `document_intelligence_sources` normaliza artefactos existentes
sin ejecutar proveedores. Centraliza la elegibilidad de detalle Vision conservando
la reselección histórica por fingerprint explícito de tarea. Esa reselección es
lineage de una misma tarea, no precedencia entre fuentes independientes. Sin
fingerprint las observaciones permanecen aditivas; no se elige una estructura
por fecha, versión de prompt o preferencia Vision. La elegibilidad de estructura
se evalúa independientemente de la de detalle, dentro de la misma frontera DI.

La adquisición exitosa de texto Native/OCR/Vision no certifica fidelidad. Estos
adaptadores declaran `REVIEW_REQUIRED`, sin inventar umbrales; el discovery
existente puede producir propuestas fundamentadas, pero normalization e
interpretación de evidencia solicitada deben propagar esa revisión. Diferencias
textuales entre observaciones disponibles, incluso no certificadas, conservan
conflictos. La calidad estructural reutiliza la evaluación de los parsers y el
contrato estructural aceptados. Los anchors Native/OCR conservan ahora el
fragmento literal reconocido por el mismo parser en lugar de un locator sintético.

Requirements persiste snapshots completos mediante el writer de 06.R.2a sin
alterarlo. Al refrescar una página, las generaciones ausentes del snapshot actual
se retienen explícitamente como DESELECTED; no se borran sus observaciones. Los
candidatos históricos quedan auditables y exponen soporte activo/revisión. El
normalizador excluye soporte exclusivamente inactivo de discovery automático;
las decisiones humanas existentes se conservan. NULL legacy sigue siendo válido.
La evidencia solicitada lee ese mismo contrato tipado y conserva el contexto de
revisión en su interpretación y en sus fuentes, sin evaluar posesión del licitante.

Scope recibe transcripción y estructura como resultados neutrales separados.
Los adapters conservan sus reglas de obligación/ownership y los reemplazos
continúan acotados a tender/documento/página/artefacto. Un detalle fallido o
DESELECTED no puede reentrar mediante un bridge. El adaptador semántico neutral
admite proveedores suministrados explícitamente para Native/OCR/Vision; no instala
ni ejecuta un LLM por defecto. El adapter de detalle Vision existente sigue siendo
el predeterminado. Esta integración no certifica calidad semántica de modelos.

El orquestador productivo usa el routing y la continuidad neutral de R.1. Un
límite sin prueba deja continuidad UNKNOWN y resolución REVIEW_REQUIRED, sin
selección ni segmentos heredados. Un nuevo inicio independiente puede recuperar
continuidad válida. Los resultados incompletos se conservan para auditoría sin
impedir los reintentos explícitos permitidos por la política de ejecución existente.
Las señales declaradas de conflicto de identificador se conservan como razón de
revisión; su descubrimiento/hardening pertenece a 06.R.3.

No hay cambio de esquema después de 072 ni nueva persistencia paralela. Scope
conserva la provenance que soportan sus contratos actuales (canal, artefacto,
locator, excerpt, analysis/page-result y revisión); el contexto DI completo es
transitorio. CompanyEvidence y la política Source Effect Qwen NO-GO no cambian.

## Contrato de provenance 06.R.3a — pendiente de aceptación arquitectónica

`RoutingResult` permanece específico por capacidad. Una observación estructural
no se reclasifica como transcripción para transportar un desacuerdo contractual.
La comparación de identificadores críticos es una capa neutral separada, que
consume observaciones clasificadas y bindings suministrados explícitamente por
un contrato upstream; no descubre tipos a partir de texto o metadata del proveedor.

El JSONB existente admite `schema_version: "2"`, sin columna, tabla ni migración.
La v2 contiene página, `routing_contexts` (uno por capacidad, con selección,
candidatos, conflictos, diagnósticos y provenance) e `identifier_comparisons`.
Cada comparación conserva kind, binding, estado, carácter crítico, diagnósticos
y todas las observaciones: valor raw y normalizado, excerpt exacto y fuente con
capacidad original, canal, documento/versión/página, locator/coordenadas,
artefacto/generación/analysis/page-result, calidad/confianza y lineage. La fuente
de cada observación debe estar representada en su contexto de routing.

El vocabulario neutral es `ITEM_NUMBER`, `PARTIDA`, `EQUIPMENT_TAG`,
`MODEL_IDENTIFIER`, `DOCUMENT_REFERENCE`, `QUANTITY_BINDING_IDENTIFIER`,
`STRUCTURAL_GROUP_IDENTIFIER` y `OTHER_CRITICAL_IDENTIFIER`. No implica verdad
contractual ni introduce valores institucionales en el Core.

La normalización de comparación usa NFC, trim y colapso de whitespace; conserva
case, acentos, puntuación, ceros iniciales y sufijos. Nunca modifica el raw ni
`normalize_item_identity`. `1`/`01`, `TAG-101`/`TAG-10I`, `A-1`/`A1`,
`Rev A`/`Rev B`, `10 EA`/`10 SET` y `X100`/`X100A` siguen siendo distintos.

Dos o más observaciones ACTIVE, confiables y de identidades independientes
permiten AGREEMENT o CONFLICT según sus valores normalizados. DESELECTED se
conserva como historia; no participa en el conflicto activo. Observaciones no
certificadas no acreditan acuerdo ni contradicción confiable. FAILED/UNAVAILABLE
pueden conservarse en routing, pero no suministrar valores de identificador.
Sin observaciones el estado es NOT_APPLICABLE; sin dos fuentes confiables activas,
INSUFFICIENT_EVIDENCE. La preferencia de canal del routing nunca resuelve un
conflicto contractual; no existe precedencia por timestamp, archivo o proveedor.

El reader usa una unión discriminada v1/v2. NULL continúa siendo ausencia legacy;
v1 conserva exactamente sus hechos y no fabrica comparaciones. Versiones
futuras, campos desconocidos, observaciones sin grounding, estados incompatibles
y fuentes ajenas al contexto fallan explícitamente. La serialización ordena
colecciones sin alterar hechos; el writer no ejecuta proveedores, recalcula
routing ni hace commit. Rechaza snapshots que pierdan historia y downgrades v2.

La escritura R.3-capable es explícita mediante `provenance_from_routings` y el
writer existente. La ruta anterior de un solo `RoutingResult` conserva v1: esto
evita upgrades/backfill automáticos y activar R.3 antes de su aceptación. El
adapter R.2 admite lecturas v2 y, al refrescar transcripción de una fila v2,
retiene los demás contextos y las observaciones históricas con su lineage; sólo
actualiza el estado derivado de comparación para que sea consistente con esa
lineage. No aplica la comparación a decisiones de dominio en R.3a.

La propagación fail-closed y su alcance local en Requirements, evidencia
solicitada, Scope, continuidad, cantidades y atributos pertenecen a R.3.
No cambia Human Review, CompanyEvidence, Source Effects ni Alternative Compliance.
Las pruebas sintéticas/JSONB no certifican precisión OCR/Vision. R.4 conserva
la calibración real posterior; Tender #002 permanece protegido hasta MVP-06.V.
