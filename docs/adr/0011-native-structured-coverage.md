# ADR-0011 — Native structured coverage and logical Scope identity

Estado: implementación propuesta para revisión arquitectónica de MVP-06.V.4b,
basada en arquitectura aceptada por el usuario. Sin esquema ni migración.

## Decisión

Registrar adaptadores Native separados de Vision bajo los contratos existentes.
Native consume exclusivamente NormalizedContent NATIVE_PDF/NATIVE_TEXT persistido;
no adquiere percepción. Scope propone bloques que empiezan con etiqueta explícita
ITEM/PARTIDA/CONCEPTO/NO y cuyo cuerpo inicia con una acción explícita de suministro, servicio o entrega.
Un bloque termina ante el siguiente ítem; no se reconstruyen tablas visuales.
Preguntas y referencias con puntos guía no son obligaciones. No se descubren hechos
por números, títulos de documentos o nombres de anexos. Se limita a propuestas
revisables, sin certificar exhaustividad ni interpretación de prosa arbitraria.

Atributos Native consumen bindings Marca/Brand/Modelo/Model separados por pipe,
punto y coma o salto de línea. Cantidades consumen Cantidad/Quantity y Unidad/Unit
explícitas, Decimal no ambiguo y unidades del vocabulario canónico existente.
No se adivinan separadores decimales, rangos, unidades ni valores monetarios.
Los hijos exigen identidad ITEM válida y fuente exacta; no asignan hijos a un
owner ambiguo. Las limitaciones de gramática no se presentan como ausencia contractual.

## Provenance y confianza

El locator versionado conserva página, NormalizedContent UUID/hash, span en texto
canónico y revisión documental. La resolución valida identidad, hash, span y revisión;
no sustituye la generación por DocumentPage.text. Native no crea analysis/page-result
Vision ni bbox. La fidelidad Native sigue REVIEW_REQUIRED; confidence permanece null.
La estructura y continuidad se evalúan mediante V.4a y sus guardas comunes; una
propuesta semántica no convierte UNKNOWN en estructura confiable.

## Identidad e idempotencia

Política explícita `scope-logical-v2`: documento/página, owner anclado, dominio/tipo,
excerpt exacto con whitespace colapsado y ocurrencia dentro del artefacto. No se
normalizan identificadores, unidades ni números para afirmar equivalencia. La
capacidad y UUID de percepción no forman identidad lógica. El fingerprint
semántico versionado añade descripción, aplicabilidad, ownership y campos explícitos
para invalidar derivaciones ante cambios de contenido, sin incluir la capacidad. Descripciones similares
sin mismo grounding no se fusionan por similitud. Repeticiones legítimas conservan
ocurrencia; otras páginas/documentos/ítems o valores explícitos distintos no colapsan.

El materializador reúne candidatos ya validados antes de seleccionar. Coincidencias
exactas eligen una representación: revisión primero, fuente previamente elegida si
sigue elegible y después desempate estable por clave de artefacto. No hay voto de
confianza ni precedencia contractual por capacidad. Conflictos de owner o campos
explícitos retiran ownership y fuerzan review. Todas las percepciones originales se
conservan. `logical_evidence` retorna fingerprint, claves de artefactos contribuyentes
y conflicto; esa relación es regenerable, no una nueva tabla multi-evidence.

Los fingerprints de política anterior se reemplazan explícitamente al materializar,
sin backfill ni reutilización silenciosa. El replay del materializador conserva UUIDs únicamente para fingerprints, generación
y estado de revisión sin cambios dentro de su artefacto, sin destruir hijos por
repetición. El reemplazo explícito sigue siendo regeneración y vuelve obsoletas
las revisiones humanas; nunca las reasocia automáticamente.
Cambios de generación actualizan la provenance y se validan antes de generar hijos.
Una capacidad adicional no crea un segundo padre por sí misma. Este slice no resuelve
equivalencia semántica de paráfrasis, no crea autoridad humana y no certifica el corpus.

Vision permanece como adaptador válido; semantic_providers explícitos conservan
su ruta opt-in anterior a Native. OCR no recibe nuevo extractor ni se ejecuta.
Una tarea sólo STRUCTURE_SCOPE no se reutiliza como transcripción de detalle.

## Validación y límites

SC01–SC24/DC01–DC06 y negativos sintéticos, regresión V.4a, materializadores, DI,
MVP-06.V y suite sin real-Ollama. No modificar intentos históricos, Requirements,
Requested Evidence ni Source Effects; no acceder al corpus ciego para tuning.
PDFs de imagen y asociaciones perdidas al extraer siguen requiriendo una fase
posterior de percepción. Las coincidencias que no puedan probarse conservan review.
