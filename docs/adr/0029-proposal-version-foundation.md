# ADR-0029 — M9-A: versiones de propuesta ligadas a snapshot

Estado: implementación autorizada para revisión. Schema documentado antes de076.
MVP-08 CLOSED / M8-D ACCEPTED (`2bcd556`). Sin M8-E. LicitIA es nombre interno; primera
salida comercial local/on-premise bajo RX23 Digital; sin renaming ni diseño UI final.

## Inventario y reuso

Tender identifica expediente; Scope/Quantity y documentos/provenance permanecen upstream.
M7-D calcula filas, M8-D preserva ProposalReadinessSnapshot tipado/inmutable. Requirement/
Requested Evidence y revisiones están ya referenciados en tracked_context de ese snapshot.
CommercialLineRevision y ReadinessWorkDecision son auditoría de sus dominios, no versiones
de propuesta. Archivos originales/attachments locales se referencian; no se copian ni
se crean artefactos todavía. Reusar get_snapshot/verify/hash y freshness M8-D; no DI/LLM.
[Revisión open source](../proposal-builder-open-source-review.md) informa separación
input/layout y outputs DOCX/XLSX editables futuros, sin dependencias nuevas.

##076 sobre075: tres tablas acotadas

- `proposals`: UUID, Tender FK RESTRICT, created_atUTC. Identidad de agregado inmutable.
- `proposal_versions`: UUID, proposal_id FK, tender_id FK, snapshot_id FK RESTRICT,
  snapshot_sha256 fijado, version>0 unique(proposal,version), previous_version_id self FK,
  state DRAFT/FROZEN, edit_revision>0, configuration JSON tipado, content_contract,
  created/updated UTC, created_origin API/WORKSPACE y actor declarado, freeze_at/actor/hash/
  acknowledgements opcionales; request UUID/hash unique(Tender,request) para retry.
- `proposal_version_events`: UUID, version FK RESTRICT, secuencia positiva única por versión,
  action CREATED/CONFIGURED/FROZEN/SUPERSEDED, actor/timestampUTC, detalles JSON pequeños
  para reconstruir cambios de configuración y lifecycle. Append-only, sin motor de approvals.

Triggers guardan pertenencia Tender/proposal/snapshot y cadena anterior. Prohíben borrar
versiones/header/events, cambiar binding/identidad y cualquier UPDATE de versión FROZEN.
UPDATE DRAFT exige edit_revision+1 y mantiene autoridad de configuración. Freeze fija hash
sobre identidad+snapshot hash+config/contract+metadata/confirmaciones. No copia payload M8-D.
Header inmutable; superseded se informa derivado por revisión posterior y se audita con
nuevo evento sin modificar versión congelada. No status EXPORTED sin archivos existentes.

## Lifecycle y concurrencia

DRAFT admite sólo configuración acotada (título, bidder libre, currency presentation sin FX,
secciones incluidas/orden, notas). No precio, Quantity, textos fuente ni outputs. Secciones
se identifican por tipo genérico estable y orden; sólo overrides explícitos, no boilerplate
vacío persistido. M9-B compone contenido; future responses serán overlays, no fuente.

Primera creación agrega Proposal+version1; crear revisión requiere proposal_id y previous
latest version ID explícitos; snapshot ID siempre explícito, puede ser el mismo o nuevo.
Sólo latest DRAFT editable/congelable. Históricos se leen, no se borran. Header lock serializa
revisiones; expected_edit_revision evita overwrite; idempotency UUID/request hash impide
retries duplicados. Conflictos PostgreSQL únicos/serialización→409, retry explícito.

Toda lectura de inputs consume snapshot almacenado verificado, no matriz actual. Elegible
permite DRAFT; warnings requieren ack explícito y se preservan. REVIEW_REQUIRED/NOT_ELIGIBLE
no se admiten ni se convierten en snapshot listo. Crear/congelar consulta freshness sólo
para advertir CURRENT/STALE; STALE requiere ack explícito, no cambia binding ni inputs.
Frozen no afirma readiness actual/compliance ni existencia de export. Check de freshness
separado permite recuperar históricos aun si fuente no se puede evaluar.

Input contract `proposal-builder-v1`: identidad propuesta/versión/binding/hash + config y
handoff M8-D reutilizado. Hash freeze es integridad, no firma. Todo local/offline sin
Ollama, telemetría sensible, DOCX/XLSX/PDF/ZIP/plantillas/prosa IA. RC-H3 pg_dump incluye
las tres tablas; prueba de restore privado preservará binding/config/hash/auditoría.
076 sólo en licitia_test y clusters efímeros de prueba, no dev/históricos. Downgrade
administrativo elimina nuevo dominio/historial; no acción UI. No stage/commit/push de M9-A.
