# ADR-0030 — Composición y respuestas humanas M9-B

Estado: aceptado funcionalmente; gate de reproducibilidad PASS. Documentado antes de Alembic077.

## Decisión

`proposal-composition-v1` deriva referencias canónicas exclusivamente del snapshot fijado
por ProposalVersion. Lecturas posteriores usan sólo snapshot + materialización persistida.
El gate de reproducibilidad descrito abajo autoriza la captura inicial del literal con
fingerprint verificado; nunca rellena frozen históricos. Legacy sin literal conserva ID,
referencia/provenance y `NOT_FROZEN_IN_SNAPSHOT`. COMPLY es declaración humana.

076 sólo permite configuración de siete secciones; no representa respuestas por fuente.
077 añade `proposal_compositions`: PK/FK `version_id` RESTRICT, contrato, revisión positiva,
estado JSON tipado (respuestas indexadas por tipo + ID canónico, configuración de secciones,
notas/aclaraciones/referencias), fechas. Una composición por versión; sin duplicar valores
comerciales ni binarios. No DELETE. INSERT/UPDATE sólo en último DRAFT, revisión incremental.
La versión y su snapshot siguen siendo autoridad de pertenencia Tender. El trigger bloquea
la cabecera Proposal durante escrituras para serializar freeze/revisión/respuestas.
Se amplía el CHECK de acciones de ProposalVersionEvent para auditoría de composición;
no se modifica ninguna migración histórica.

Inicialización explícita idempotente, respuestas persistidas separadas. Revisión copia sólo
por ID estable; fingerprint diferente exige revisión humana explícita; retirados no se copian.
No matching por posición/texto. Lectura paginada por sección sin consultas SQL por fila.

Freeze nuevo exige composición inicializada/revisión vigente: PENDING en Requirement/Evidence,
PROVIDED sin referencia y SOURCE_CHANGED sin resolver bloquean. Excepciones/PARTIAL/N/A o
exclusiones requieren motivo y acknowledgment de revisión; no equivalen a certificación.
Scope admite respuesta opcional. Secciones excluidas no ocultan respuestas pendientes: siguen
computándose; exclusión es sólo presentación. Aclaraciones/notas son opcionales.
Freeze preserva hash de composición/revisión/contrato dentro del recibo existente. Frozen
históricos sin recibo de composición conservan exactamente su algoritmo original.

## Límites

Datos locales/confidenciales, sin red, LLM, dependencias nuevas, cálculo económico ni generación.
Referencias documentales sólo contra IDs congelados en snapshot o referencia externa textual
acotada sin fetch. No DMS ni evidencia inventada. No cambia readiness MVP-08.

## Gate de reproducibilidad previo al commit M9-B

Requirement.canonical_text y RequirementEvidenceExpectation.evidence_description no son
históricos inmutables; sus tablas permiten UPDATE y regeneración. VersionLink no congela
el texto de cada representación. Se materializa en content JSON de077, sin nueva migración:
`sources` por tipo+ID, literal exacto visible, referencia/provenance del snapshot,
fingerprint de representación y hash de contenido, contrato proposal-composition-v1.
Captura al inicializar DRAFT con fingerprint canónico igual al snapshot; reutiliza una
representación anterior sólo si mantiene identidad/fingerprint. Incompatibilidad o fuente
faltante falla cerrada. Nunca se rellena un frozen histórico desde estado mutable.
Leer/componer/exportar después de captura no consulta Requirements actuales. Captura es
input de propuesta, no otra autoridad canónica. Las respuestas permanecen separadas.
Legacy sin sources conserva exactamente hash anterior; un DRAFT puede capturar explícitamente,
FROZEN legacy sin literal queda sólo con referencias y no puede exportar texto ausente.
