# M9-B — Composición estructurada de propuesta

Contrato `proposal-composition-v1`; [ADR-0030](adr/0030-proposal-composition.md).

La composición mantiene tres autoridades separadas: snapshot canónico, disposición de
secciones y respuestas humanas. Scope/Quantity/comercial/provenance nunca son campos editables.
Requirements/Evidence materializan su literal/display text al inicializar el DRAFT, validando
identidad y fingerprint contra el snapshot. Después se leen sólo esos inputs propios de versión.
Legacy frozen sin captura conserva `NOT_FROZEN_IN_SNAPSHOT` y su hash original; nunca se rellena
retroactivamente con texto mutable.

Secciones: IDENTIFICATION, TECHNICAL_SCOPE, REQUIREMENTS, REQUESTED_EVIDENCE, ECONOMIC,
CLARIFICATIONS, ANNEX_REFERENCES, NOTES. Identidad estable independiente del orden; empates por
ID. Filtros por sección y offset/limit máximo200, bulk explícito máximo50 filas.

Respuesta humana: estado, texto, descripción ofrecida, comentario, aclaración, nota,
referencia documental/external, inclusión y motivo. No precios editables. COMPLY sólo declara
la intención del participante. PROVIDED exige referencia; N/A/excepción/parcial exige motivo.

Inicialización idempotente conserva ediciones. Revisión nueva copia por tipo+ID; source hash
cambiado genera SOURCE_CHANGED y exige acknowledgment por fila. NEW pendiente, REMOVED no
contamina la revisión nueva. Hash incluye fuente relevante, no posición.

Completitud independiente de readiness: INCOMPLETE para pendientes/referencias faltantes;
REVIEW_REQUIRED para excepciones/exclusiones y cambios sin resolver; COMPLETE en resto.
Freeze bloquea incompletitud/cambio sin resolver; admite revisión intencional con confirmación.
Todas las respuestas y cambios de disposición tienen auditoría append-only anterior/actual,
actor declarado, origen y fecha. No son autenticación.

077 conserva overlay JSON tipado por versión, sin binarios ni nueva autoridad económica.
Backups PostgreSQL existentes incluyen tabla y eventos automáticamente. Frozen M9-A históricos
se verifican con contrato original; todo freeze nuevo vincula también hash de composición.
Sin DOCX/XLSX/PDF/ZIP, rich text, IA, red externa o UI final.

## API y límites

Bajo `/tenders/{tender_id}/proposal-versions/{version_id}/composition`:
GET paginado (`section`, `offset`, `limit`), POST `/initialize`, PATCH `/responses`
(cambios explícitos, atómicos, máximo50), PATCH `/settings` (secciones/contenido humano)
y GET `/summary`. Mutaciones exigen `expected_revision`, rechazan stale y no borran datos
con una repetición de initialize. Reintentar una mutación requiere consultar revisión vigente.
Las listas de razones se acotan a100 globales/25 por sección; conteos y estado son exactos.
Los grupos de moneda publican conteos, sin total entre monedas ni recalcular valores.
Workspace carga25 filas por sección. El snapshot se valida/compone en memoria con ordenación determinista; no se
promete streaming de snapshots arbitrariamente grandes. La prueba de escala usa1000 partidas.

`items` permite hasta200 aclaraciones/exclusiones/supuestos/desviaciones/notas/anexos,
con ID UUID estable y referencias textuales/locales; no se implementa gestión de adjuntos.
Documento asociado debe existir en los IDs congelados del snapshot del mismo Tender.
Cambiar una asociación anterior que ya no pertenece al snapshot exige revisión humana;
las filas copiadas se marcan SOURCE_CHANGED cuando pierden su asociación.

## Compatibilidad y evolución

077 sólo se aplica en validación a `licitia_test` y clusters privados efímeros; no migra
la base de desarrollo/históricos. No modifica076. El nuevo freeze exige
`expected_composition_revision` y, para excepciones aceptables,
`acknowledge_composition_review`. Se conserva el retry/hash original de frozen M9-A.
M9-C recomendado: renderers editables locales sobre composición frozen verificada, con
identidades/provenance y separación de monedas, sin reextraer ni fijar precios.

## Validación funcional inicial

M9-B listo para revisión arquitectónica, sin stage/commit/push. Backend completo:
2371 passed,1 opt-in local_ollama deselected,64 warnings de dependencias/configuración
existente. Frontend150 passed; build118 módulos, compileall y diff check PASS.
Los20 casos de propuesta (11 composición,8 foundation,1 restore) pasan en la suite final.
MVP-07:123; M8-D:12, M8-C:11, M8-B:11, M8-A:22; core207+1 opt-in omitido;
DI1153+1 opt-in excluido; API70; recuperación45. Escala2→1000 partidas:3→3 SELECTs,
página25. Hashes históricos5941/5941 intactos, sin inspección semántica.

Rechazos STALE/NOT_PREPARED/NOT_ELIGIBLE de pasadas iniciales coincidieron con cambios
backend durante pruebas: processing_identity incorpora application_identity (hash de app).
Se separaron etapas y se conservó huella fija en validación final; no se relajó el guard.
Evidencia local no staged: backend/reports/m9_b/.

## Gate de reproducibilidad M9-B

El modelo implementado no es el RequirementVersion conceptual de la visión: Requirement
permite UPDATE de canonical_text (requirement_normalization.py); las expectativas de evidencia
permiten UPDATE de evidence_description (requirement_semantics.py). RequirementVersionLink
expresa relaciones pero no garantiza una copia inmutable del texto original.

Por ello `content.sources` en077 guarda tipo/ID, display_text exacto, referencias congeladas,
fingerprint canónico, hash del contenido y contrato. No duplica documentos ni cambia fuentes.
Una captura no correspondiente al snapshot falla con SOURCE_REPRESENTATION_UNAVAILABLE_FOR_SNAPSHOT.
Una revisión puede reutilizar materialización anterior compatible; cambios producen revisión
SOURCE_CHANGED por hash relevante. Leer y congelar datos ya capturados no reconstruye desde
Requirement/Evidence actuales. Sources y respuestas humanas permanecen separadas.

DRAFT legacy permite captura explícita conservando respuestas y auditoría; frozen legacy no
puede modificarse, ni asumir literal histórico ausente. Hash legacy omite el nuevo campo sólo
cuando nunca estuvo presente. No se necesita078 ni se cambia el contrato M8-D.

Gate de reproducibilidad previo al commit: R1–R6 y compatibilidad legacy PASS; backend2375 passed,1 opt-in excluido; frontend150, build, restore, compileall/diff PASS; históricos5941/5941 intactos. Sin nueva migración.
