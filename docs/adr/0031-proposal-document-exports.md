# ADR-0031 — Exports locales sobre composición preservada

Estado: implementación autorizada para revisión M9-C, después del gate/commit M9-B.

## Autoridad

proposal-export-v1 usa exclusivamente snapshot + materialización + respuestas de una
ProposalVersion explícita. El renderer recibe un DTO externo seguro, nunca una Session.
FROZEN oficial; DRAFT sólo con autorización explícita, etiqueta visible en cada formato.
Legacy sin literal no se rellena: export que requiera esos textos falla cerrada.
Freshness se observa por endpoint existente separado; no cambia inputs ni impide exportar
un frozen histórico. Manifest diferencia estado de fuente al freeze y freshness no reevaluada.

## Renderers y confidencialidad

python-docx1.2.0 MIT, openpyxl3.1.5 MIT ya fijado, ReportLab5.1.0 BSD-3-Clause.
Transitivas nuevas lxml6.1.3 BSD-3-Clause (componentes incluidos con sus notices),
charset-normalizer3.5.1 MIT (se reutiliza la versión existente); Pillow ya fijado. Fuente Vera local distribuida por ReportLab,
licencia Bitstream Vera que permite distribución en software; conservar notices.
No ReportLab PLUS/pyRXP, office automation, SaaS, URLs/font assets externos ni LLM.
Se fijan hashes de wheels en lock RC según convención existente.

DTO por allowlist excluye costos/margen/markup/commercial notes y notas económicas humanas.
Aviso genérico de warnings reconocidos, sin detalles internos de pérdidas/pricing.
Los comentarios técnicos/respuestas/aclaraciones son contenido humano intencional de propuesta.
Secciones e inclusión usan composición. No recalcular precios ni totales; monedas separadas.
No importación XLSX de propuesta a MVP-07. Metadata/IDs internos en manifiesto/propiedades,
no celdas visibles salvo referencias humanas útiles. Fórmulas del usuario como texto explícito.

## Storage e historia

Metadata mínima en filesystem controlado, sin078: storage/proposal-exports-v1/TenderUUID/
VersionUUID/RequestUUID con archivos generados, manifest.json y receipt.json verificados.
La convención RC-H3 ya respalda storage completo; SQL no necesita tabla para estos derivados.
No binarios en PostgreSQL. Snapshot/propuesta no se mutan al exportar.

Manifest interno al ZIP identifica contrato, versión/snapshot/comp hash, semántica externa,
fecha, warnings reconocidos y hashes/tamaños/tipos de outputs. Receipt externo al ZIP fija
hash del manifest y del ZIP (evita hash autorreferencial). Integridad no equivale a firma.
Request UUID + digest permite retry idempotente. Nuevo request genera nueva historia.
Temporales privados y publicación atómica; fallo conserva artefactos previos y permite retry.
No originales incluidos en paquete. ZIP nombres estáticos y safe-name para descarga.

## Límites

Lista paginada de historia. Identidades UUID, nombres de artefacto por enum, root estricto,
symlink/path escape rechazados. Sin macros/hyperlinks externos. PDF escapa texto y utiliza
fuentes locales; glifos no soportados fallan explícitamente. Límites de tamaño/filas para
fallos útiles, no truncamiento silencioso de celdas. Regeneración garantiza identidad
semántica; hash binario se verifica por generación y no se confunde con semántica.
