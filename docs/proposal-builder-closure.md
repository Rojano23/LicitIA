# MVP-09 — cierre de Proposal Builder

M9-C ACCEPTED, commit `49c36ab39c3a697fcc993e64be98960045bb400b`, sin push.
**MVP-09 CLOSED — gates A–P PASS. M9-D ACCEPTED; cierre formal autorizado.** Backend2390 passed/1 opt-in excluido; frontend157 passed, build PASS.
No declara release público.

## Flujo y autoridad

Tender → Scope/Quantity canónicos → oferta comercial humana → Bid Readiness → snapshot
explícito → ProposalVersion → composición → respuestas humanas → completitud → freeze →
DOCX/XLSX/PDF/ZIP con manifiesto. Se valida con PDFs genéricos sintéticos existentes;
no se usa Tender #002 ni se adquiere OCR/Vision para este cierre.

El snapshot ID/hash vinculado no se sustituye por el último snapshot o estado actual.
Requirement/Requested Evidence usan literales materializados al inicializar la composición,
con referencias, fingerprint y hash propios; nunca un fallback mutable para FROZEN.
Los cambios upstream requieren nuevo snapshot/revisión. Las respuestas copiadas con fuente
cambiada quedan SOURCE_CHANGED/review hasta revisión explícita. La versión anterior permanece
inmutable y exportable aunque su snapshot sea STALE; freshness se muestra separadamente.

Quantity sigue de sólo lectura en Proposal Builder. Si requiere corrección: corregir upstream,
crear nuevo readiness snapshot y nueva revisión de propuesta. La prueba conserva Quantity X y demuestra que una mutación sintética sin evidencia compatible
es rechazada por Readiness; no incorpora un editor de Quantity ni una corrección sin fuente.

## Trazabilidad y control humano

SourceRef conserva documento, revisión, página/locator y SHA del fragmento, unidos al ID de
Scope/Requirement. Snapshot → ProposalVersion → clave de fila de composición → DTO de export
→ manifiesto → SHA del artefacto permite seguir la cadena interna. Los identificadores
internos permanecen en metadata/manifiesto, sin exigir mostrarlos como contenido externo.

Canonical y respuesta humana están separados. PENDING es el estado inicial; COMPLY sólo se
registra por acción humana y significa declaración del participante, no certificación.
Completitud determinista no equivale a validación jurídica ni cumplimiento garantizado.
Precio final, alternativa técnica, excepción, aclaración y evidencia siguen bajo control humano.

## Confidencialidad e integridad

Todo el flujo opera sobre DB/filesystem local/on-premise. No transmite contenido a LLM,
renderer cloud, analytics ni servicio documental externo. La allowlist externa omite costos,
markup/margen y notas comerciales/económicas internas. Sentinelas comprueban también que una
explicación privada de riesgo aceptado no aparece en DOCX/XLSX/PDF/manifiesto. Texto humano
intencional de propuesta se revisa antes de compartir; no se promete clasificación semántica
universal de secretos.

DRAFT requiere consentimiento y etiqueta visible; FROZEN conserva estado/hashes. Hashes y
verificación de ZIP detectan alteración, sin afirmar firma digital. Error de renderer es
fallo del export, no de la propuesta: no invalida FROZEN ni elimina outputs anteriores.
Retry UUID+digest es idempotente, temporales incompletos no aparecen como outputs válidos.

Filesystem bajo root estricto, nombres saneados, ownership Tender/version, symlink/path escape
rechazados. XLSX sin fórmulas/macros/hyperlinks ejecutables; DOCX sin macros/relaciones remotas;
PDF usa fuente local y se prueba con red denegada. [Contrato M9-C](proposal-document-exports.md).

RC-H3 respalda DB y storage completo: propuesta, composición, respuestas, freeze, metadatos,
historia y binarios exportados. Restore aislado comprueba igualdad de proyección y hashes.
Regeneración conserva semántica; no se promete igualdad binaria entre generaciones nuevas.

## Alcance incluido y exclusiones

Incluye dominio/revisiones, snapshot binding, composición, respuestas, completitud, freeze,
reconciliación, DOCX/XLSX/PDF/ZIP, manifiesto, hashes, exports locales y trazabilidad.

No incluye UI final, branding RX23 final, nombre permanente del producto, escritura IA,
certificación legal, firmas electrónicas, approvals, auth nueva, colaboración cloud, SaaS,
CRM/project management, marketplace de plantillas ni presentación automática.

## Evidencia y límites

`backend/tests/test_proposal_closure.py` demuestra el flujo A→B con cambios reales en
Requirement/Evidence y precios/monedas, manteniendo Quantity X y verificando rechazo de una cantidad sin soporte; re-export A conserva exactamente su DTO
semántico. Los tres formatos se comparan por contenido y valores, no por layout.
La prueba de escala mide composición, freeze y export en snapshot sintético expandido.
No certifica recall semántico, estética institucional ni performance de modelos reales.

Gates A–P y comandos/conteos finales: `backend/reports/m9_d/final_report.md`.
No nueva migración; Alembic077. M9-D aceptado y commit autorizado; sin push.

MVP-10 Discovery recomendado: acordar usuarios y escenarios de revisión/paquete de entrega,
criterios de aceptación y límites de confidencialidad, reutilizando versiones/export existentes.
No abre automáticamente UI final, cloud, firma, AI writing ni soporte institucional adicional.
