# MVP-10 — cierre Discovery M10-D

Estado: MVP-10 CLOSED — gates A–T PASS; M10-D listo para revisión arquitectónica, sin stage/commit/push.
M10-C ACCEPTED, commit `4a4a62938c8651bed9ec8b69e66f398635992dce`.
M10-D es validación/documentación: sin nuevas funciones mayores ni migración080; corrección acotada de auditoría del perfil.

## Capacidad y arquitectura final

Fuente pública → Source Adapter → Discovery Core → Opportunity normalizada → perfil
local determinista → workflow humano → Create Tender explícito → Tender Core canónico.
PEMEX/CFE comparten Opportunity, SourceDocument, ScanRun, Profile, Change, Coverage,
TenderLink, ImportReceipt, servicios y API. Sus contratos de adquisición/paginación se
encapsulan en adapters; no hay workflows/modelos Tender institucionales paralelos.
No flag `created_from_discovery` requerido downstream. La procedencia es un vínculo local.
[ADR-0032](adr/0032-discovery-core-pemex.md), [ADR-0033](adr/0033-discovery-cfe-source-restrictions.md),
[ADR-0034](adr/0034-discovery-monitoring-handoff.md).

| Fuente | Discovery automatizado | Ingestión manual de archivos del usuario |
|---|---|---|
| PEMEX público validado | SUPPORTED | Sí |
| CFE público validado | SUPPORTED | Sí |
| Compras MX | DEFERRED — SOURCE AUTOMATION RESTRICTED | Sí |

**Discovery currently supports automated monitoring of validated public PEMEX and CFE
procurement sources.** No se afirma cobertura nacional exhaustiva ni de todos los
procedimientos gubernamentales. Compras MX automatizado está diferido porque la fuente
pública aplica una restricción que el producto no elude. Su acceso manual no autoriza
adquisición automática. [Investigación y entradas públicas](discovery-m10b-source-inventory.md)
se conservan; no PoW/emulación/bypass/cookies/browser, sustitución por datasets ni requests
nuevos Compras MX. Futuro ComprasMXAdapter puede implementar el mismo contrato/registry
sin rediseñar DB/dominio, sólo ante interfaz oficial automatizable documentada y aprobada.

## Evidencia de cierre

Pruebas sintéticas reproducibles, normales sin red pública:

- Misma configuración de perfil en ambas fuentes: include PLC, exclude cancelado y
  sinónimo controlador lógico programable; explicación idéntica. Cada fuente217 únicos,
 218 filas,3 batches, match sólo en último batch y duplicado suprimido. Source namespace
  separa PEMEX/CFE/Compras MX con idéntico external_id. Scans repetidos sin eventos nuevos.
- Parser PEMEX elimina HTML/script/style y normaliza whitespace. CFE ignora estilos/HTML
  de presentación de detalle, normaliza whitespace JSON y excluye metadata auxiliar del
  fingerprint. JSON CFE con markup literal se preserva como texto; React lo escapa y no
  construye script/img/onerror. No se interpreta como instrucción ni HTML ejecutable.
- FOLLOWING y DISCARDED persisten ante cambios de fuente; no crean Tender. Pruebas previas
  conservan historia/ack, first_seen/last_seen y categorías completas de cambio.
- PARTIAL/FAILED, total incompatible, fila inválida, continuación incompleta, alcance/versión
  distintos y rollback de finalización nunca justifican ausencia. CFE con detalle fallido
  conserva referencias previas. Sólo SUCCESS completo/aplicable permite inferencia negativa.
- La auditoría detectó un hueco de match histórico ante Profile mutable. El fix captura
  ID/revisión/configuración/match/SHA en Link.context existente; evento de creación apunta
  a ese SHA. Preview stale se rechaza; match falso sigue permitiendo la decisión humana.
  Legacy sin captura se muestra como tal, sin inventar historia; sin perfil, contexto null.
- Preview crea cero Tenders; confirmación/binding y selección preceden al handoff canónico.
  Mismo request devuelve enlace existente. Los originales y SHA/receipts mantienen provenance.
  Nombres remotos duplicados reportan NAME_CONFLICT, no sustitución silenciosa. La selección
  intencionalmente omitida no es fallo; subset importado reporta outcomes propios.
- Antes de procesamiento explícito, no hay filas nuevas de dominios downstream en tablas
  con tender_id ni páginas/materializaciones. Guards impiden workspace pipeline, percepción,
  proveedor Vision/Ollama, evaluación Proposal y creación de versiones durante handoff.
  Después de orden explícita, PDFs sintéticos nativos producen2 Scope/2 Quantity y servicios
  Commercial/Bid Readiness/Proposal Readiness aceptan el Tender normal en ambas fuentes.
  Proposal Readiness devuelve NOT_ELIGIBLE por revisión/precios pendientes: no se fabrica
  completitud ni propuesta. No se requiere generar una propuesta completa para este gate.
- Compras MX restringido no bloquea crear Tender manual, subir PDF y procesarlo explícitamente
  por el camino Native normal. Discovery permanece opcional.
- Restore real PostgreSQL+filesystem conserva Source/Profile/Opportunity/Scan/Change/ack/
  workflow/Link/Receipt/documentos. Retry del mismo scan devuelve auditoría; un scan nuevo
  sin cambios no duplica; Create repetido retorna el mismo Tender. Un Tender+archivo existente
  en077 sobreviven078→079. Clean install a079 y reversibilidad079→078→079 en clúster efímero.
- Escala con20 vs215 observaciones: SELECT15→21, sentencias totales31→53; crecimiento por
  batches, no por Opportunity. Dataset grande:20 nuevas,15 metadata,45 documentos añadidos,
 5 documentos retirados,5 ausencias; conserva FOLLOWING e IMPORTED sin mutar el Tender.

La matriz de pruebas completa y resultados por comando se entrega en reportes locales
`backend/reports/m10_d/`; esos reportes no forman parte del commit. Los60 casos M10D y gates
A–T se vinculan a pruebas/código/evidencia. Mocks prueban contratos, no recall real ni calidad
semántica de modelos. No corpus ciego ni providers reales de IA.

## Comprobación pública acotada — 2026-10-23

Rango2026-10-22 a2026-10-23,20 filas/batch, máximo12 batches por área. Sólo metadata, sin
escrituras producto, binarios ni Compras MX. PEMEX cuatro áreas alcanzaron terminal:2 únicos,
9 referencias (otras tres áreas vacías en ese filtro). CFE51 únicos,3 batches locales,
402 referencias,1 listado+51 detalles+form=53 requests. Opt-ins separados de regresión;
fallo temporal de fuente se informa, no redefine el resultado determinista de arquitectura.
La prueba live PEMEX acotada no demuestra multipágina real ese día; las fixtures de3 páginas
sí prueban el contrato. CFE total independiente no publicado: terminal es fin del array
observado, sin garantía de ausencia de truncación desconocida del servidor.

## Seguridad, autoridad y privacidad

Se reutilizan allowlists de host/path/HTTPS del adapter, no redirects; nombres seguros antes
de red, límites25MiB/archivo, MIME+firma, timeout30s y ceiling60s comprobado entre chunks.
No RCE/descompresión/ejecución ni scanner antivirus. Estado/URLs del payload no habilitan fetch
arbitrario. Ownership Opportunity/SourceDocument/Tender/target de revisión y ack se comprueba.
Originales/versiones/receipts previos permanecen. Cambios públicos nunca reescriben análisis
ni decisiones del Tender: nuevas referencias/cambio de contenido requieren import/sync humano.
[Contrato operativo y límites](discovery-monitoring-handoff.md).

No telemetría RX23 ni uploads de keyword profiles, Following, Tenders privados, documentos,
precios o decisiones. Sólo requests públicos soportados salen del equipo; keywords/perfiles
se evalúan localmente. Tokens públicos CFE son efímeros/en memoria, no reportados ni persistidos.
Al crear Tender, trabajo/documentos/decisiones del cliente quedan privados en DB/filesystem
locales. Backups locales confidenciales bajo reglas RC-H3. Auth no agregado: boundary LIMITED
UAT controlada permanece. Actor local es auditoría, no identidad autenticada.

## Límites canónicos

- Compras MX automatizado diferido; portales estatales/municipales y otras fuentes no incluidos.
- MANUAL SCAN ONLY FOR PRIVATE BETA; scheduler no es gate ni se añade daemon/infraestructura.
- Discovery requiere Internet para fuentes públicas; disponibilidad/HTML/API pueden cambiar
  independientemente del producto. Tender Analysis sigue local-first.
- Completitud es del conjunto aplicable observado, no snapshot remoto atómico ni cobertura
  total nacional. No total externo inventado; datos/eventos ambiguos quedan explícitos.
- Mismo URL/metadata con binario diferente exige refresh humano para calcular nuevo SHA.
  Source changed compara con creación, no una lista perfecta de tareas pendientes de sync.
- No evidencia semántica real de nuevos formatos/portales: pruebas locales y live metadata
  no certifican cumplimiento ni relevancia contractual. Límites históricos de Quantity/
  Requirements/DI siguen vigentes. No certificación de CFE Tender Analysis por este slice.
- Ceiling de descarga se revisa entre chunks; una lectura puede consumir su timeout antes
  de comprobarlo. MIME/magic no valida íntegramente semántica interna de PDF/Office.
- Tombstone no crea otro Tender automáticamente. Downgrade pierde monitoreo, no originales.
- Warning de bundle506.07kB en build permanece; no es rediseño final ni optimización UI.

## Después del cierre

A–T PASS; roadmap `MVP-10 CLOSED`, sin M10-E. Orden posterior, sólo documentado aquí:
1. Plan acotado de identidad pública RX23 TuScope/rename.
2. UI/UX final de producto.
3. Pruebas reales E2E por product owner.
4. Demos controladas con contactos de confianza.
5. Corregir hallazgos.
6. Instalador Windows.
7. Private Beta externa instalada.

Nada de estas fases se implementa en M10-D. Futuras fuentes estatales/federales o Compras MX
requieren aprobación e interfaces documentadas; no se construyen anticipadamente.
