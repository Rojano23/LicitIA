# MVP-09 M9-A — dominio de propuesta y versiones

MVP-08 CLOSED / M8-D ACCEPTED, commit `2bcd556b6b785412a5cf24b81d2ccac770e995a4`.
M9-A implementado para revisión, sin stage/commit/push. LicitIA sigue como nombre interno;
producto público futuro por definir, distribución inicial RX23 Digital local/on-premise.
No renaming ni UI final. [ADR-0029](adr/0029-proposal-version-foundation.md) documentó076
antes de implementación; [revisión open source](proposal-builder-open-source-review.md).

## Autoridades e inventario

Tender identifica expediente. Snapshot M8-D fija readiness/Scope/Quantity/comercial, estados
Requirement/Requested Evidence y referencias documento/versión/página/locator/hash. M7-D
calcula precios; MVP-06 extrae Quantity; M9 no recalcula ni reinterpreta. Company/biblioteca
y attachments ya existen, pero no se crea master data ni se copian documentos aquí.
Originals siguen filesystem local, metadata/hash en DB. No nuevas rutas de archivos/output.
Reutiliza snapshot verificado/hash/freshness M8-D y patrones de audit/concurrencia locales.

`ProposalInput` (`proposal-builder-v1`) contiene identidad Proposal/Version/revisión,
binding snapshot ID/hash, configuración/secciones y handoff M8-D íntegro sin cambiarlo.
Input se deriva del snapshot almacenado, no de dominios mutables. Puede consultarse aunque
la fuente actual cambió: los precios/Quantity y refs siguen iguales. Freshness es endpoint
separado; errores se exponen, no se convierten en CURRENT. Fuente no se congela ni bloquea.
MVP-08 snapshot conserva contrato de formato/schema075; DB global pasa a076 por M9-A.

## Persistencia076

Tres tablas acotadas: Proposal (identidad/Tender/fecha), ProposalVersion (binding, versión,
estado/config/revisión/metadata, hash frozen y request idempotente), ProposalVersionEvent
(auditoría append-only). No duplicar handoff JSON en versiones; FK snapshot RESTRICT.
Trigger comprueba Tender de Proposal/snapshot/cadena anterior; binding/identidad no cambian.
No output tables, ProposalDocument, PDF blobs, paquetes ni plantillas. Eventos conservan
CREATED/CONFIGURED/FROZEN/SUPERSEDED, actor declarado, timestampUTC y configuración antes/
después donde corresponde. No identidad autenticada ni aprobación empresarial.

## Lifecycle mínimo

DRAFT: sólo latest de cada Proposal admite cambiar configuración. FROZEN: todo registro
inmutable, incluso vía SQL; sus input/config requieren otra revisión para cambios.
No READY/EXPORTED ficticio ni archivos generados. Versiones antiguas no se borran.
Superseded es condición derivada por revisión posterior + evento nuevo en auditoría;
no UPDATE del frozen para marcarlo. Fecha updated sólo cambia por edición/freeze propio.

Primera solicitud crea Proposal + v1. Revisión nueva exige proposal_id y previous_version_id
más reciente explícitos y snapshot_id elegido (puede ser igual o distinto). Clona config
anterior si no se suministra otra; no copia datos fuente. Históricos DRAFT quedan consulta
solamente, no pueden editarse/congelarse después de crear sucesor. Otra Proposal separada
para el mismo Tender se crea omitiendo grupo/previous; no se confunde con revisión.

Unique(proposal,version) y lock de header serializan; expected_edit_revision evita overwrites.
request_id UUID + SHA del body normalizado es idempotencia: retry crea una sola identidad;
body distinto con mismo UUID409. Respuesta de retry retorna estado actual de esa identidad
(si se configuró/congeló después), nunca otra Proposal/Version. Repetir config igual con
revisión vigente no agrega evento. Revisión vieja409. Freeze repetido con mismo request
normalizado devuelve versión frozen; confirmación diferente no la modifica.

## Prechecks y stale

Snapshot ID obligatorio del mismo Tender, hash/payload verificados por M8-D. ELIGIBLE
permite DRAFT; ELIGIBLE_WITH_WARNINGS exige confirmación explícita. Warning permanente de
cobertura no certificada se conserva. REVIEW_REQUIRED/NOT_ELIGIBLE no se convierten en
snapshot válido ni propuesta preparada. Aunque se encontrara un snapshot no elegible, el
precheck también falla cerrado. No se usa actividad RESOLVED como sustituto de datos.

Crear y congelar consultan freshness: STALE exige acknowledge_stale explícito. Se permite
trabajar con snapshot histórico elegible confirmado; el contenido mantiene ese estado
almacenado y se informa SOURCE_SNAPSHOT_STALE para fuente actual. No se afirma readiness
actual por estar FROZEN. Error evaluando fuente impide estas acciones, pero GET de inputs/
versión sigue independiente. Transacción REPEATABLE READ reutilizada de M8-D, sin locks
permanentes de edición upstream. Conflicto PostgreSQL23505/40001/40P01→409/retry explícito.

## Configuración/secciones

Título≤300, bidder_name≤300 y referencia≤200 libres, notes≤4000, presentación BY_CURRENCY u
ORIGINAL (sin FX o cambio de moneda), overrides de sección (máximo7). Nada permite editar
precios/Quantity/requisitos fuente. Sección: id estable igual a tipo lower-case, tipo,
order0–999, included y nota≤4000. IDs/órdenes explícitos duplicados inválidos. Orden final
estable por order/id. Sin overrides se deriva catálogo, no se guardan cuerpos vacíos.

Tipos genéricos: IDENTIFICATION, TECHNICAL_SCOPE, REQUIREMENTS, REQUESTED_EVIDENCE,
ECONOMIC, NOTES, ANNEX_REFERENCES. No nombres PEMEX ni layout final. Catálogo y orden default pertenecen al contrato v1; cambios requieren otra versión y
conservar el lector v1 para frozen históricos. M9-B compondrá matrices/
contenido y futuros overlays de respuesta humana, manteniendo fuente sin cambios.
Configuración es reemplazo tipado completo con expected_edit_revision; extra fields422.

Freeze conserva SHA256 de envelope canónico con identidad/versión/previous, snapshot ID/hash,
config/content contract, metadata de creación y freeze/confirmaciones. Hash se verifica con
snapshot en cada GET de versión/input; inconsistencia409. Es integridad, no firma. Auditoría
SUPERSEDED posterior no forma parte del input frozen ni lo reescribe. Listado devuelve
metadata paginada; abrir versión verifica integridad. Roles/admin DB siguen bajo política
local aceptada. FK RESTRICT retiene historia; downgrade administrativo la elimina.

## API y Workspace

Base `/tenders/{id}/proposal-versions`:

- POST CreateProposal: request UUID, snapshot UUID, optional Proposal/previous UUIDs, config,
  warnings/stale ack, actor libre, origin API/WORKSPACE.
- GET list: proposal_id opcional, limit1–50/default20, before_id keyset fecha/id descendente;
  metadata, is_latest, next_before_id. Consulta agrupada MAX(version), sin query por fila.
- GET `/{version_id}`: metadata/config/secciones/eligibilidad snapshot/hash.
- PATCH mismo: configuración DRAFT vigente + expected_edit_revision/actor.
- POST `/{version_id}/freeze`: expected_edit_revision, ackwarnings/stale/actor.
- GET `/{version_id}/inputs`: contrato MVP-09 desde snapshot inmutable.
- GET `/{version_id}/source-state`: CURRENT/SOURCE_SNAPSHOT_STALE, sin cambiar binding.
- GET `/{version_id}/history`: limit1–100/default25, before_sequence.

UUID ajeno/versión fuera del Tender404; source/binding/config inválidos fallan cerrados.
UI provisional: lista20, snapshot ID explícito, crear Proposal o revisión desde seleccionada,
ver state/binding/eligibilidad, check freshness, título/bidder/notas/presentación de monedas,
guardar y congelar con checkbox irreversible, historial25 y enlace input JSON. Inclusión/
orden de secciones por API; no editor de matrices todavía. Retry creación conserva body/UUID
mientras componente montado; iniciar otra solicitud es acción explícita. Sin persistencia
del UUID frontend tras recarga. UI impide freeze mientras haya configuración sin guardar. Freeze después de respuesta perdida requiere refetch para
ver versión; API permite repetir request original, no crea exports.

## Backup/offline/límites

RC-H3 pg_dump incluye tablas sin cambios de motor. Prueba privada snapshot-island preserva
Proposal/Version frozen/config/hash/eventos al restore; no pretende copiar originales del
expediente a esa isla. RC-H3 completo cubre originales/provenance en regresión separada.
076 sólo en licitia_test/clusters efímeros. No dev ni históricos migrados. Todo flujo local,
sin LLM/Ollama ni servicios externos/telemetría sensible. Investigación pública sólo docs.

Aún sin contenido compuesto, DOCX/XLSX/PDF/ZIP, logos/branding, plantillas, firma/envío,
UI final, renderer/editor rico o generación de prosa. Outputs futuros deben ser editables
(DOCX/XLSX, PDF derivado si procede), separados de cálculos. Control humano final intacto.
M9-B recomendado: composición determinista de secciones/matrices con source IDs y overlays
humanos, ligada a versión DRAFT/freeze; diseñar contrato tipado sin producir archivos aún.
M9-C añadirá export editable y manifiesto de outputs tras selección de dependencias/licencias.
