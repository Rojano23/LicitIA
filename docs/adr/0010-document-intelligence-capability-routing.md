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

La selección ACTIVE/DESELECTED y la evaluación de calidad son entradas explícitas,
no inferencias del routing. No se reemplazan ahora las selecciones históricas del
runtime. Su convergencia y calibración se revisarán en slices posteriores.

Los tests sintéticos demuestran contratos, routing, lineage y fail-closed;
no certifican extracción visual/OCR ni calidad semántica. No se autorizan modelos
reales en R.1. La calibración real exige una fase controlada posterior y autorización
explícita. Tender #002 permanece ciego hasta MVP-06.V, después de MVP-06.R.
