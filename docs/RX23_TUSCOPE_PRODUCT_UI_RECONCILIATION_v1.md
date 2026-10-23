# RX23 TuScope — Product UI Reconciliation v1

Fecha: 2026-10-23. UI-R0: especificación propuesta, lista para revisión arquitectónica.
**MVP-01 through MVP-10 CLOSED** por decisión arquitectónica. No M10-E ni MVP-11.
M10-D aceptado y comprometido en `8668fb2` (HEAD completo en §19).
Esta especificación es la referencia única propuesta para implementación UI-R1–R7;
el [Blueprint v0.1](PRODUCT_UI_BLUEPRINT_v0.1.md) conserva contexto histórico.
No implementa pantallas, tokens, renaming, APIs, migraciones, fuentes ni nuevos motores.

## 1. Autoridad y evidencia inspeccionada

Orden de autoridad: decisión arquitectónica actual → capacidades verificadas en código →
Stitch para lenguaje visual → Blueprint para intención del producto. Una imagen no acredita
una función, dato, porcentaje ni soporte institucional. Se preservan originales y contratos.

Directorio original localizado, sólo leído:
`/Users/ceciliavalencia/Downloads/stitch_licitia_gesti_n_de_licitaciones_pro/`.

Inspección visual efectiva: `Dashbrd.png`, `NuevaLicita.png`, `VisorDoctos.png`,
`MatrizRequisitos.png`, `Cat_part.png`, `DetalleCost.png`, `Proveedores.png`.
Los nombres reales NuevaLicita/MatrizRequisitos carecen del sufijo `(1)` del Blueprint.
Se leyeron `licitia_professional_system/DESIGN.md` y los 12 `code.html` del directorio:
dashboard, plataforma industrial, nueva licitación, visor, catálogo, dos matrices,
dos costeos, proveedores, evaluación BID/NO BID y untitled prototype.
`EvalBnB.png` y el screen de evaluación no pudieron decodificarse con el visor disponible;
la evaluación se auditó por HTML, sin afirmar revisión visual de esos dos archivos.
Los otros screen.png son variantes incluidas en inventario, no se declara inspección visual individual.

Inventario reproducible de todos los assets (ruta, tamaño, SHA), sin copiarlos al producto:
`backend/reports/ui_r0/asset_inventory.json` (artefacto local, no staging).
No se ejecutaron HTML/scripts/CDN de Stitch ni se hicieron solicitudes a portales.
Los ejemplos CFE/IMSS/SCT/CONAGUA de Stitch no certifican soporte de análisis de esas fuentes.

Código inspeccionado: `frontend/src/App.tsx`, `index.css`, `index.html`, componentes y contratos
`frontend/src/api/`; rutas en `backend/app/main.py`, modelos y `discovery_monitoring.py`.
Documentación base: README, visión, arquitectura, dominio, roadmap, Golden001, ADR0032–34,
Blueprint y cierre Discovery. No se abrió contenido del corpus ciego Tender002.

## 2. Lenguaje visual y reglas de producto

Conservar sidebar navy/slate, lienzo claro, superficies blancas, bordes sutiles, jerarquía
compacta, tablas profesionales y azul restringido. La calidad procede de alineación,
legibilidad y estados claros. No gradientes, glass, glow, héroes grandes, gráficos decorativos,
rotaciones de iconos o animaciones del costeo animado. No fuentes remotas obligatorias.

Cada campo, badge, columna, tarjeta y acción debe tener una pregunta/acción y fuente real.
No mostrar porcentajes de cumplimiento arbitrarios ni transformar presencia documental en
cumplimiento. Extracción, asociación de evidencia, evaluación automática y decisión humana
son hechos distintos. Advertencias comerciales no bloquean decisiones por sí mismas.
No presentación automática, fijación de precios, creación de Tender ni análisis por navegar.

## 3. Navegación y jerarquía de pantallas

Global: **Inicio · Discovery · Licitaciones · Mi empresa · Configuración**.
**Reportes no aparece como menú global en v1**: no hay servicio de reporting transversal
verificado; los exports reales pertenecen a Comercial/Propuesta. No menú vacío ni dashboard ficticio.
Sin navegación IA, proveedores autónomos, motor, OCR o Vision. Diagnóstico bajo Configuración.

Licitaciones → lista → licitación seleccionada, con título/referencia y cambio de licitación
persistente → **Resumen · Documentos · Requisitos · Cumplimiento · Partidas · Comercial ·
Preparación de oferta · Propuesta**. “Preparación de oferta” es etiqueta propuesta para Bid
Readiness: no implica cumplimiento certificado ni presentación. “Anexo C” sólo como nombre
literal de un documento. No duplicar navegación global con tabs Dashboard/Bidding/Compliance.
Conservar destino, filtros y retorno al abrir fuente; URL navegable propuesta, no router implementado.

Discovery usa el mismo shell: **Oportunidades** (Todas/Nuevas/Siguiendo/Con cambios/Licitación
creada), **Perfiles**, **Consultas e historial**, con estado de fuentes en contexto/enlace a
Configuración. Cambios son eventos de fuente pendientes de lectura, no una nueva evaluación
contractual. Perfil determinista es filtro local, no decisión BID/NO BID. Una oportunidad puede
seguirse aunque esté importada. Nueva = estado NEW, no “publicada hoy”.

## 4. Mapa de pantallas y contratos reales

Prefijos: T=`/tenders/{tender_id}`, C=`/companies/{company_id}`, O=`/discovery/opportunities/{opportunity_id}`.
GET salvo verbo indicado. Rutas relativas al backend local configurado. Las acciones existentes
se preservan con sus DTO, precondiciones, ownership y revisión optimista; no sustituir servicios.

| Pantalla / propósito y pregunta | Acciones y datos principales | Métrica / fuente backend | Stitch / cambio requerido |
|---|---|---|---|
| Inicio: ¿dónde continúo? | Abrir licitación, Discovery y pendientes disponibles; sin traer todos los expedientes | Nuevas y seguidas con cambios, §6; `/discovery/monitoring/summary` | Dashbrd: ADAPT, eliminar KPIs sin definición |
| Licitaciones: ¿qué expediente trabajo? | Listar/buscar localmente título, referencia y estado; abrir/crear | `/tenders`; sin sumar sólo una página si cambia el contrato | Centro: KEEP concepto, ADAPT navegación y columnas |
| Nueva licitación: ¿cómo incorporo originales? | POST `/tenders`, import explícito T`/documents/import`; resultados por archivo y resolución de conflictos | T`/documents`, T`/workspace`; no progreso inventado | NuevaLicita: ADAPT, separar subir y procesar |
| Resumen: ¿qué requiere atención aquí? | Estado, acceso a documentos, preparación y cambios; proceso/retry explícito | T`/workspace`, `/workspace/recovery`, `/bid-readiness`, `/events`, `/effective-state` | Dashboard de expediente: ADAPT/NEW integración |
| Documentos: ¿dónde dice eso? | Lista de revisiones, visor PDF, página, fuente y decisiones; importar, elegir revisión, procesar | T`/documents`, `/documents/{document_id}/pages`, `/documents/{document_id}/content`; conteos del conjunto consultado | VisorDoctos: KEEP patrón, ADAPT capacidades reales |
| Requisitos: ¿qué piden y qué evidencia solicitan? | Matriz, filtros, detalle, fuente y Requested Evidence; revisión disponible | T`/requirements`, `/requirement-matrix`, `/requirement-effective-state`, `/requirement-semantics`, `/workspace` | MatrizRequisitos y dos variantes: MERGE, no tabla de todos los campos |
| Cumplimiento: ¿qué soporta mi evidencia y qué decidí? | Seleccionar empresa, relacionar/revisar evidencia, evaluación y decisión separadas | T`/companies/{company_id}/compliance-matrix`, `/compliance-review`, `/evidence-match-candidates`; C`/evidence` | Cumplimiento técnico: ADAPT nombre/dominio, sin certificación |
| Partidas: ¿qué alcance/cantidad tiene cada partida? | Scope/cantidad/unidad/fuente, revisión Scope, alternativas y riesgo | T`/workspace`, `/scope-review`, `/technical-alternatives`, `/alternative-scope-snapshot`; no mezclar legacy `/items` con Scope canónico | Cat_part: ADAPT; cantidad canónica read-only, edición auditada diferida |
| Comercial: ¿cuánto cuesta y qué precio decido? | Matriz, selección, bulk con preview, costo/origen, markup/margen, override, round-trip y auditoría | T`/commercial-matrix`, `/commercial-matrix/summary`, POST `/commercial-matrix/bulk`, `/commercial-exchange/export/{kind}`, `/scopes/{scope_id}/commercial-audit` | Catálogo+Costeo: MERGE; conservar decisiones y separar monedas |
| Preparación de oferta: ¿qué falta y cuál es mi siguiente acción? | Issues, filtros, tablero, notas/riesgo permitido e historia; snapshot explícito | T`/bid-readiness`, `/readiness-board`, `/readiness-work`, `/proposal-readiness`, POST `/proposal-readiness/snapshots` | Evaluación BID/NO BID: ADAPT/NEW; quitar recomendación automática BID y score inventado |
| Propuesta: ¿qué versión estoy preparando/emitiendo? | Crear/revisar versión, composición/respuestas, congelar con confirmación, exportar/verificar/reintentar | T`/proposal-versions`, `/{version_id}/composition`, `/source-state`, `/history`, `/exports`; rutas completas bajo proposal-versions | Propuesta económica: MERGE en propuesta completa; NEW versiones/snapshot/freeze |
| Discovery lista/detalle: ¿me interesa y qué cambió? | Filtros, perfil/match, seguir, historia/ack, referencias, preview y Crear/Abrir licitación | `/discovery/opportunities`, O, O`/changes`, O`/following`, O`/tender-preview`, POST O`/create-tender` | NEW; no miniaplicación separada |
| Discovery perfiles/consultas | Configurar intereses; consulta manual, rango/áreas, historial y parcialidad | `/discovery/profiles`, `/discovery/sources`, POST `/discovery/sources/{source_id}/scans`, `/discovery/scans` | NEW; distinguir consultar fuente de filtrar DB local |
| Mi empresa: ¿qué documentación/evidencia puedo usar? | Crear/editar empresa, biblioteca, revisiones, extracción/revisión explícita | `/companies`, C, C`/documents`, C`/evidence`; `CompanyEvidenceLibrary` | Base documental: ADAPT, no inventar subsistemas RH/certificaciones |
| Configuración/Diagnóstico | Fuentes/capacidades y explicaciones; salud local, proveedores sólo soporte; backup según CLI existente | `/discovery/sources`, `/health`, `/ocr/providers`, `/vision/providers`; backup RC-H3 CLI, no API UI inventada | Configuración: ADAPT; Reportes: REMOVE menú; diagnóstico NEW organización |

### Original → vigente (incluye decisiones de retiro)

Centro KEEP tabla/jerarquía, ADAPT métricas; nueva/upload ADAPT progreso real y privacidad;
visor KEEP disposición; requisitos MERGE variantes detalle/matriz; cumplimiento ADAPT;
Partidas ADAPT y mover precios a Comercial; costeo MERGE en detalle comercial; propuesta
económica MERGE en Propuesta, conservar proyección comercial como sección; proveedores/cotizaciones
MERGE sólo referencia de contraparte, documento y costo en Comercial. **REMOVE** catálogo maestro,
estrellas, 98%, 48h y extracción universal de cotizaciones: no hay API/entidad maestra de proveedor
verificada. No construir SRM para parecerse al mockup. REMOVE impuestos/desglose de ingeniería/flete
cuando no estén en contrato; no introducir cálculos sugeridos por la imagen (el “margen” visual no
es autoridad aritmética). Evaluación BID/NO BID ADAPT a preparación sin decisión automática.
Dashboard/plataforma/untitled duplicados MERGE. Reportes genéricos REMOVE; configuración ADAPT.
Discovery, cambios, handoff, snapshot, versiones, freeze y export seguro NEW integraciones.

## 5. Experiencias de trabajo, densidad y disclosure

Nivel 1: pregunta, estado legible, resultado y siguiente acción. Nivel 2: drawer/página con
fuente/revisión/página/fragmento, evidencia, decisión humana e historia. Nivel 3: diagnóstico
opt-in con UUID, SHA, parser/provider, versiones, payload/códigos; nunca sustituye “Ver fuente”.
Un STALE que afecta decisión o propuesta sí aparece en nivel1 como cambios posteriores; el
código y fingerprints permanecen en nivel3. No ocultar riesgo material bajo diagnóstico.

Documentos: lista lateral 220–280px + visor flexible + panel contextual plegable 300–360px.
En 1366px no forzar tres paneles abiertos: revisión en drawer, visor conserva espacio principal.
Enlace fuente lleva documento **y revisión** y página real; si no hay página, abrir fragmento
con “Página no disponible”. Nunca saltar silenciosamente a revisión vigente en una fuente histórica.
PDF inline existente se reutiliza; no prometer resaltado geométrico exacto ni visor DOCX/XLSX
si no está implementado. Texto/metadata y descarga segura son alternativas explícitas.

Requisitos: texto, categoría cuando disponible, evidencia solicitada, revisión, fuente y acción.
Cumplimiento y fuente de evidencia se abren en contexto, sin duplicar todas las matrices.
Partidas: referencia, descripción, cantidad/unidad, revisión, fuente; atributos en detalle.
Comercial: costo y precio con moneda/origen, warnings y acciones reales; mantener porcentajes
margen/markup distintos, pérdidas visibles y override protegido. Totales por moneda con
cantidad de filas calculables/incompletas; no FX ni sumar MXN+USD.
Propuesta: versión/borrador/congelada e inputs/snapshot; cambios actuales no reescriben historia.
Export muestra outcomes, verificación, advertencia de revisión humana; no “cumplimiento certificado”.

Tablas: header sticky dentro de scroll acotado, filtros/sort con alcance anunciado, descripción
flexible, cifras alineadas y tabulares; truncado con acceso por teclado a texto completo. Columna
acción estable. 5–8 columnas principales según tarea; detalle para resto, no límite contractual.
Bulk sólo donde existe (Comercial); selección con alcance claro. Paginación Discovery es servidor,
no reemplazar por primeras50 ni contar lo visible como total. Sin cards por cada fila en desktop.

## 6. Inventario de métricas: definición, fuente y destino

No valores de ejemplo en runtime. No mostrar cero durante carga/error; usar “No disponible”.
La fecha de consulta/alcance debe ser visible; no llamar “tiempo real” a observación persistida.

| Métrica / ubicación | Definición determinista | Fuente exacta | Acción/destino |
|---|---|---|---|
| Nuevas oportunidades / Inicio, Discovery | COUNT oportunidades internal_state=NEW, de todas las fuentes locales; no publicación reciente ni perfil actual | GET `/discovery/monitoring/summary`.new_opportunities; `app.discovery_monitoring.summary` | Discovery filtro internal_state=NEW |
| Seguidas con cambios / Inicio, Discovery | COUNT oportunidades watching=true con >=1 Change origin=SOURCE y acknowledged_at IS NULL | mismo GET, followed_with_changes | Discovery following=true&unread_only=true |
| Oportunidades con cambios / Discovery | COUNT DISTINCT opportunity_id en Change SOURCE sin ack | mismo GET, changed_opportunities | Discovery unread_only=true |
| Cambios sin leer / Discovery detalle/resumen | COUNT eventos SOURCE sin ack; no número de oportunidades | mismo GET, unread_changes; detalle O`/changes` | Historia de la oportunidad / filtro de lista |
| Referencias documentales nuevas / Discovery | COUNT eventos DOCUMENT_ADDED SOURCE sin ack; no número de archivos descargados ni únicos actuales | mismo GET, new_documents | Lista con cambios → historia; no inventar filtro docs inexistente |
| Licitaciones activas / sólo lista si se desea | COUNT status=ACTIVE en respuesta completa GET `/tenders`; DRAFT no es ACTIVE | GET `/tenders`, TenderStatus ACTIVE | Lista status ACTIVE (filtro local mientras endpoint completo) |
| Bloqueos / Resumen y preparación de UNA licitación | blocker_count del resultado canónico, independiente de notas humanas de seguimiento | GET T`/bid-readiness`.blocker_count | Preparación, severity BLOCKER |
| Revisiones / misma licitación | review_required_count canónico, no “todos los requisitos pendientes” | mismo GET, review_required_count | Preparación, severity REVIEW |
| Partidas / Partidas | workspace.scopes.length, Scope canónico; no suma de candidatos/items/Quantity | GET T`/workspace` | Partidas |
| Requisitos / Requisitos | workspace.requirements.requirements.length del conjunto efectivo devuelto | GET T`/workspace` | Requisitos; mostrar scope_note/limitaciones |
| Costo/venta/contribución por moneda / Comercial | Valores total_cost/offered_total/profit por currency; conservar null y *_calculable_count y *_missing_count | GET T`/commercial-matrix/summary` (servicio comercial) o summary_by_currency de matriz | Matriz filtrada por moneda |
| Borradores/congeladas / Propuesta de UNA licitación | COUNT versiones por campo state=DRAFT/FROZEN sólo tras recorrer cursor before_id hasta terminal; si no, etiquetar conteo de página y omitir total | GET T`/proposal-versions` (limit20, máximo50, cursor before_id) | Historial filtrado localmente por estado; no filtro servidor inventado |

Inicio v1 muestra sólo las dos primeras métricas y acceso a licitaciones; resto en contexto,
no 12 cards. La métrica “activas” se reserva a la lista para no confundir borradores en trabajo.
Omitir globalmente: Tenders que requieren atención, bloqueos globales, requisitos pendientes
globales, propuestas listas globales, documentos por revisar globales y vencimientos agregados:
no hay proyección transversal acotada verificada. No hacer fan-out a todos los Tenders al abrir Inicio.
No KPIs de ahorro/éxito/porcentaje de cumplimiento, cotizaciones pendientes, ranking o capacidad
industrial sin definición y fuente. Fechas próximas: eventos y valid_until existen, pero una fecha
extraída/revisión pendiente no define cierre autoritativo; omitir card global hasta contrato revisado.
Si se aprueba después, una proyección read-only acotada puede reutilizar servicios existentes;
UI-R0 no la implementa ni convierte esta conveniencia en nuevo dominio.

## 7. Discovery integrado y restricciones

Columnas base: fuente, procedimiento/evento, título, área, fecha publicada si existe, estado
interno y cambios; match/perfil y número de referencias según espacio. Descripción larga,
first_seen/last_seen, identidad y documentos en detalle. No confundir fecha publicada con observada.
Sin perfil seleccionado, no mostrar “sin coincidencia”; mostrar “Sin perfil seleccionado”.
Perfil histórico al crear Tender se distingue del perfil actual editable; legacy no capturado
se explica, nunca se reconstruye como hecho. Orden/filtros persisten al volver del detalle.

Crear licitación siempre usa preview readonly → título y selección vacía por defecto →
confirmación → outcomes por documento. No análisis automático. Fallo parcial conserva Tender;
abrir vínculo existente y reintentar sólo acción pendiente, sin duplicar creación. Tombstone
explica eliminado y conserva historia sin botón recrear. Cambios de fuente no reescriben Tender;
“Hay cambios desde la creación” no es cola exacta de sincronización. Ack sólo marca leído.

PEMEX/CFE muestran última consulta, rango/área y estado SUCCESS/PARTIAL/FAILED, sin certificar
cobertura nacional/instantánea atómica. CFE terminal es fin del array observado, no total externo.
Consultas manuales únicamente, sin notificaciones push/scheduler ficticios.
Compras MX: **Automatización no disponible actualmente**, detalle “Restricción de acceso de la
fuente; soporte automatizado diferido”. Sin Scan habilitado ni solicitud de red; sin PoW,
cookies/tokens o browser bypass. La carga manual de un Tender sigue disponible por separado.

## 8. Lenguaje de estados

| Contexto/código | Etiqueta propuesta | Precaución |
|---|---|---|
| REVIEW_REQUIRED / NEEDS_REVIEW | Requiere revisión | Motivo y siguiente acción |
| Discovery NEW / REVIEW / FOLLOWING | Nueva / En revisión / Siguiendo | Seguir no crea licitación |
| Discovery IMPORTED / DISCARDED | Licitación creada / Descartada | No confundir con importación completa de documentos |
| watching=true | Siguiendo | Independiente de IMPORTED |
| scan SUCCESS / PARTIAL / FAILED / RUNNING | Consulta completada / Consulta parcial / No se completó / Consultando | Exponer rango y fecha |
| workspace NOT_PROCESSED / PROCESSING | Sin procesar / Procesando | Acciones explícitas |
| COMPLETED / COMPLETED_REVIEW_REQUIRED | Procesado / Procesado con revisiones pendientes | No “cumple” |
| INTERRUPTED / FAILED / PARTIAL | Procesamiento interrumpido / No se completó / Resultado parcial | Consultar recuperación antes de retry |
| STALE / source changed | Hay cambios posteriores | Mantener versión histórica; renovar sólo explícitamente |
| NO_EVIDENCE | Sin evidencia | No sentencia contractual automática |
| decisión humana positiva/negativa | Cumple / No cumple (decisión humana) | Evaluación automática se etiqueta aparte |
| proposal DRAFT / FROZEN | Borrador / Versión congelada | Congelada no significa presentada ni certificada |
| commercial INCOMPLETE / READY | Datos incompletos / Datos comerciales completos | No “licitación lista” |
| CONFIRMED_QUOTE / HISTORICAL_COST | Cotización confirmada / Costo histórico | Origen económico, no cumplimiento |
| SYSTEM_ESTIMATE / MANUAL_INPUT | Estimación / Captura manual | No presentar estimado como confirmado |

Los nombres de contrato reales pueden variar por dominio: usar mapas tipados por contexto,
no un traductor universal que colapse PENDING, READY o CONFIRMED entre dominios. Términos
preferidos: Detectado, Extraído, Sugerido, Fuente, Evidencia. No IA en menú principal.

## 9. Tokens y layout propuestos (documentación, sin migración)

| Token | Valor inicial | Uso |
|---|---|---|
| bg / surface / surface-subtle | #f7f9fb / #ffffff / #f2f4f6 | lienzo, tabla, header |
| nav / nav-active / nav-text | #091426 / #1e293b / #eff1f3 | navegación oscura y selección |
| text / text-secondary | #191c1e / #45474c | lectura principal/secundaria |
| border / input-border | #e2e8f0 / #75777d | separación sutil / control identificable |
| action / focus | #1d4ed8 / #1d4ed8 | azul restringido, enlace y focus visible |
| success / bg-success | #166534 / #dcfce7 | estado sustentado |
| warning / bg-warning | #854d0e / #fef9c3 | revisión/advertencia |
| danger / bg-danger | #b91c1c / #fee2e2 | error/no cumple contextual |
| muted / bg-muted | #475569 / #f1f5f9 | no disponible/sin evaluar |

Stitch usa #3b82f6 como acento; propuesta #1d4ed8 para texto/controles pequeños con contraste
más sólido. Mantener #3b82f6 sólo donde se pruebe contraste. No cambiar palette arbitrariamente.
Sin claim WCAG hasta pruebas de combinaciones, focus y estados.
Spacing 4/8/12/16/24/32px; radius2/4/6/8px (badge12); sin sombras permanentes,
overlays máximo sombra tenue. Inter local si disponible, fallback system-ui/Segoe UI, sin CDN.
Tipos: título30/38 peso700, sección20/28 peso600, subsección16/24, body14/20,
meta13/18; evitar cuerpo11px; cifras13/18 tabular-nums. Sidebar260, header56–64,
padding24 (16 compacto), gap16. Filas40–44px, celda12x8, editor al menos36px.
Tablas pueden ocupar ancho disponible; texto de lectura con máximo~80 caracteres por línea.
No fondo navy en grandes resúmenes financieros si reduce legibilidad o parece hero.

## 10. Inventario de implementación y gaps

| Superficie actual | Clasificación | Reutilizar / trabajo posterior |
|---|---|---|
| App.tsx (~6500 líneas), selección Tender y llamadas axios | Técnicamente acoplada; requiere rediseño | Conservar contratos/handlers, extraer vistas por etapas; no reescritura global |
| index.css, estilos inline y style local | Requiere reconciliación | Inter existente; sustituir tokens/estilos gradualmente, sin dependencia UI nueva automática |
| WorkspaceFlow | Existe reutilizable | Lectura/proceso/recovery y Scope/Quantity; rediseñar ubicación/estado |
| ScopeReview, TechnicalAlternatives, AlternativeCompliance | Existe reutilizable | Conservar auditoría, fuentes y autoridad; adaptar drawer/tabla |
| CommercialLine, CommercialMatrix, CommercialAuditDetails, CommercialSpreadsheet | Existe reutilizable; duplicación de controles | Conservar preview, límites, overrides, origen, roundtrip; editor detallado desde matriz |
| BidReadinessInspection, ReadinessWork, ReadinessBoard, ProposalReadiness | Existe reutilizable; presentación duplicada | Una preparación de oferta con tabs resumen/pendientes/historia/snapshot; separar canónico y seguimiento |
| ProposalVersions, ProposalComposition, ProposalExports | Existe reutilizable | Integrar versión seleccionada y navegación, preservar historial/exports seguros |
| CompanyEvidenceLibrary | Existe reutilizable, monolítica | Ruta propia, biblioteca y evidencia; sin submódulos empresariales ficticios |
| DiscoveryView, DiscoveryDetail | Existe y backend listo | Mover fuera de details; separar perfiles/scan/lista/detalle, traducir labels |
| Documentos/visor en App | Existe, requiere rediseño | Recuperar tamaño útil y contexto fuente; no confundir dos bloques Documentos condicionales con dos dominios |
| Requisitos/cumplimiento/eventos/estado efectivo en App | Existe, requiere rediseño | Separar matrices y detalle, mover raw/engine a diagnóstico |
| AppShell/sidebar/context-nav/routing/Inicio | Faltante de integración frontend | APIs base disponibles; Inicio acotado §6 |
| Reportes/SRM/highlight geométrico universal | No capacidad verificada | Retirar promesa, no ampliar backend |

Sobrecarga actual: Discovery entero dentro de details; Mi empresa y creación/lista en pantalla
principal; estado expediente, evaluación, requisitos detectados/normalizados, partidas y Vision
conviven en App; aclaraciones, estado efectivo, mapa y timeline extensos antes de documentos.
UUID/códigos/provenance de provider y respuesta cruda compiten con trabajo diario. Visor min-height760
más encabezados produce mucho scroll a768px. Grilla370px+1fr y maxWidth1200 no conforman shell.
Inspección estática; UI-R0 no ejecutó ensayo visual del runtime ni mediciones de usabilidad.

## 11. Componentes finales y estrategia de reutilización

| Componente propuesto | Base actual | Decisión |
|---|---|---|
| AppShell, GlobalSidebar, TenderContextNav | App sin shell/router dedicado | NEW, migración incremental UI-R1 |
| PageHeader | títulos h2/h3 locales | Extraer presentación, contexto/acción real |
| MetricCard | contadores locales Discovery/readiness | NEW liviano con loading/error y destino, §6 |
| StatusBadge, SourceBadge | labels locales/alternativeLabels | Unificar aspecto, mapas tipados por dominio |
| FilterBar, DataTable | tablas Discovery/Commercial/Work | Reusar lógica, componentes simples antes de motor spreadsheet |
| EmptyState, LoadingState, ErrorState | strings/busy/error locales | Extraer presentación y mantener outcomes/errores explícitos |
| ProvenanceLink, ReviewDrawer | fuentes ScopeReview/WorkspaceFlow/App | Integrar navegación documento-revisión-página; no perder excerpt |
| DocumentViewer | iframe PDF seguro en App | Reutilizar backend/iframe, separar layout |
| ChangeTimeline | DiscoveryDetail y timeline App | Compartir presentación, contratos/historias siguen separados |
| ActionMenu | botones locales | Agrupar secundarias, primaria visible |
| ConfirmationDialog | window.confirm y confirm checkbox | Unificar UI accesible sin debilitar confirmaciones/previews |

No reemplazar componentes correctos por uniformidad estética. Retener DTO/tests existentes;
primero composición y estilos, luego extraer estado donde haya beneficio medible.

## 12. API/UI audit y límites reales

No falta un dominio para pantallas esenciales §4; falta composición frontend/navegación,
traducción y carga bajo demanda. Hay wrappers tipados para comercial, workspace, Scope review,
alternativas, preparación, propuestas y Discovery. Company/requisitos/visor permanecen en App
con axios; mover a wrappers conserva contrato, no exige nueva API.
No endpoint transversal acotado de Inicio con atención/propuestas/fechas verificado. Propuesta
read-only futura sujeta a revisión, no gate para Inicio mínimo. No nuevo endpoint de reportes.
No API SRM ni extracción universal de cotizaciones, visor Office universal, edición Quantity
auditada o resaltado geométrico garantizado: omitir acciones y conservar limitación canónica.
Configuración backup puede ofrecer instrucciones del administrador; sin fingir endpoint restore.
No exponer DB/secretos en interfaz diaria. Contratos de seguridad no se debilitan por diseño.

## 13. Estados vacíos, carga, error y recuperación

| Estado | Mensaje/acción útil |
|---|---|
| Sin oportunidades | “Aún no hay oportunidades guardadas”; configurar fuente soportada y consultar explícitamente |
| Fuente no disponible | Mostrar último éxito/fecha, consultar datos locales, reintentar manual; no borrar resultados |
| Sin Tender seleccionado | Elegir licitación o crear una; no paneles de engines vacíos |
| Sin documentos | Agregar originales; explicar límites y procesamiento local |
| Procesando | Etapa/estado real disponible, conservar navegación; no porcentaje/ETA fabricado |
| Análisis no disponible | Motivo/estado, ver documentos y recuperación elegible; no afirmar cero requisitos |
| Scan parcial | Mostrar resultados conservados y advertencia de cobertura, revisar auditoría y nueva consulta explícita |
| Compras restringido | Automatización no disponible actualmente; explicación, sin scan/red; creación manual independiente |
| Sin coincidencias | Revisar perfil/filtros y alcance persistido/scan parcial; no “no existen oportunidades” |
| Export fallido/parcial | Mostrar versión/outcomes, verificar y retry seguro; no congelar/copiar datos de nuevo |
| Fuente histórica no disponible | Indicar revisión/locator faltante, conservar excerpt; no sustituir fuente silenciosamente |

Cargar al entrar a vista apropiada; lectura no dispara jobs, import, percepción o AI. Error
conserva ediciones/resultado previo claramente fechado. Abort/ignorar respuesta de Tender
anterior al cambiar selección; proteger datos comerciales no guardados.

## 14. Auditoría de marca y de datos ficticios

Cambios visibles futuros, no efectuados aquí:
- `frontend/index.html`: title LicitIA → RX23 TuScope; lang en → es-MX.
- `frontend/src/App.tsx`: h1 y textos “LicitIA propone” / “reglas determinísticas de LicitIA”.
- `ScopeReview.tsx`: motivos/copy FACT_REVIEW_REQUIRED, SCOPE_REVIEW_TARGET_STALE,
  feedback de guardado, “LicitIA solicitó/no solicitó revisión”, “Lo que LicitIA encontró” y
  explicación histórica. Usar producto o lenguaje neutral conservando autoridad humana.
- `CompanyEvidenceLibrary.tsx`: explicación de validación de evidencia.
- `CommercialSpreadsheet.tsx`: mensajes de archivo/export LicitIA; download name
  `licitia-commercial.${kind}` se evalúa como nombre visible, **sin cambiar metadata interna**
  ni contrato de reimportación. Revisar marca de exports por separado para no romper historia.

Mantener storage keys licitia_selected_tender_id/company_id, paquetes, DB, migraciones,
identificadores de intercambio y fixtures históricos. Strings servidor de errores/exports
necesitan auditoría de copy en UI-R5/R6; no renaming masivo por búsqueda/reemplazo.

Búsqueda estática de mock/dummy/Math.random/faker/sample/demo y porcentajes decorativos en
frontend/src: referencias de mocks en tests y `src/test`, no tabla fake/KPI runtime identificados.
App obtiene Tender/documentos por axios y componentes usan APIs reales. Valores iniciales de
formularios (moneda, fuente, porcentaje), mensajes vacíos y ejemplos de input no son resultados.
No garantía dinámica de ausencia de toda simulación: UI-R7 probará sin DB y con API error.
No importar HTML/datos de Stitch al runtime. Tests/fixtures aislados sí pueden usar datos
sintéticos deterministas; ninguna entidad sintética se mezcla con almacenamiento del usuario.

## 15. Responsive y accesibilidad: criterios comprobables

Primario1366x768: sidebar260 plegable, contenido min-width0, una acción primaria y visor útil;
1440x900: tabla y drawer sin desplazar navegación;1920x1080: ampliar tabla/visor, limitar ancho
lectura. Bajo1024: sidebar plegable con etiquetas accesibles, panel detalle alternable; bajo768:
una columna/drawer, scroll horizontal **dentro** de tabla. No scroll lateral de toda la app,
no ocultar acciones críticas por viewport. Probar zoom200% y textos largos reales.

Objetivos: contraste texto normal>=4.5:1, grande>=3:1, controles/focus>=3:1; focus visible,
orden DOM y tab coherente, skip-to-content, landmarks y heading único, botones con nombre,
inputs con label/error asociado, estados texto+icono, tablas con caption/th scope y selección
anunciada. Targets mínimo24px (preferencia36–44), no hover-only. Dialog con foco atrapado,
Escape seguro y retorno al origen; estados asíncronos con live region moderada. No afirmar
cumplimiento WCAG certificado: todavía no auditado con teclado/lector/contrastes dinámicos.

## 16. Plan acotado de implementación y gates

| Slice | Alcance exacto | Gate verificable |
|---|---|---|
| UI-R1 | Shell/sidebar/context-nav, URLs/retorno, tokens y componentes básicos, title/lang/marca visibles del shell | Selección Tender/empresa preservada, navegación teclado, cero writes al navegar, tests existentes verdes |
| UI-R2 | Inicio mínimo §6 + Discovery integrado, lista/perfiles/consulta/detalle/historia/handoff | Paginación total, fuente parcial/restringida, estados/match histórico, create explícito idempotente; sin Compras red |
| UI-R3 | Lista/creación/Resumen/documentos/visor/recovery | Import conflictos/revisiones y path safety sin cambios; enlaces fuente a revisión/página; retry explícito |
| UI-R4 | Requisitos/Requested Evidence/Cumplimiento/Partidas/alternativas/revisión | Autoridad humana y fuentes; Quantity read-only, no mezcla Scope/parent ni cumplimiento por mera asociación |
| UI-R5 | Matriz comercial/preparación/propuestas versiones/composición/exports | Margen≠markup, monedas separadas, overrides/audit, snapshot/freeze/stale, no fuga de costos/datos internos |
| UI-R6 | Mi empresa/configuración/diagnóstico; decidir Reportes con evidencia, no construir analytics | Biblioteca/provenance preservadas, secretos fuera de UI, sin menús ficticios/SRM/backend nuevo |
| UI-R7 | Consistencia de copy/estados, viewport/a11y/performance/E2E completo | Tres resoluciones+zoom/teclado, vacío/error/parcial, test owner sintético completo; no mocks runtime |

Por slice: pruebas frontend focused → regresión pertinente → build y diff check; backend sólo
si contratos/superficie lo justifican. UI-R7 E2E con datos sintéticos y autoridad humana explícita;
no reutilizar Tender002 para tuning. No añadir framework UI/router/dependencia sin evaluar
mínimo necesario. No backend convenience project dentro de R1–R7 sin aprobación separada.
Luego UI final → pruebas Tender reales del owner → demos controladas → correcciones →
instalador Windows → Private Beta externa. Ni instalador ni fuentes/AI nuevos ahora.

## 17. Decisiones para revisión y limitaciones

Aprobar “Preparación de oferta”; menú global sin Reportes/SRM; Inicio mínimo sin proyección
transversal; azul accesible derivado de Stitch; navegación y extracción incremental de App;
tratar Supplier Quote como referencia comercial y no catálogo; no prometer Quantity editing,
Office viewer o highlights exactos. Son decisiones propuestas revisables, no implementadas.

Assets fuera del repositorio: conservar su respaldo original; inventario SHA permite detectar
cambios pero no distribuye las imágenes a otros equipos. Dos imágenes evaluación ilegibles en
visor; HTML sí inspeccionado. No nueva evaluación de calidad semántica ni soporte DI institucional.
Single-user/local-first y UAT controlada sin auth permanecen; UI no afirma seguridad multiusuario.
Bundle warning aceptado previo no se arregla en doc-only; medir en R7 antes de optimizar.

## 18. Validación UI-R0 y evidencia heredada

M10-D:22 hashes aceptados coincidieron, HEAD anterior verificado, índice vacío antes de stage,
commit limitado a22 archivos, sin reportes y sin push. Regresión aceptada **heredada**, no repetida:
Discovery120, backend2510passed/5deselected, frontend178, build/compileall PASS, Alembic079,
live metadata2, históricos5941/5941. No se presenta como ejecución nueva de UI-R0.
UI-R0 sólo modifica documentación: links locales, rutas de lectura §4, presencia de secciones,
git diff --check e índice vacío se validan al cerrar. Sin tests runtime nuevos por doc-only.
No cambios en código/DB/env, ni ejecución de providers o acceso a fuentes públicas.

## 19. Reporte final de 28 puntos

1. M10-D commit: `8668fb2` (`fix(discovery): preserve handoff provenance and close mvp-10`).
2. HEAD completo: 8668fb240db70564bab26d420609e42819a4f3ab; sin push.
3. MVP-01–10 CLOSED; README/roadmap distinguen cierre funcional y UI pendiente.
4. Stitch: siete imágenes vistas, DESIGN.md y12 HTML leídos; dos imágenes evaluación no decodificables (§1).
5. Inventario frontend real: App, CSS, APIs y componentes (§10–11).
6. Global: Inicio, Discovery, Licitaciones, Mi empresa, Configuración (§3).
7. Tender: Resumen, Documentos, Requisitos, Cumplimiento, Partidas, Comercial, Preparación de oferta, Propuesta.
8. Discovery: Oportunidades, Perfiles, Consultas/historial; fuentes integradas (§3,7).
9. KEEP/ADAPT/MERGE/REMOVE/NEW por pantalla y variante (§4).
10. Inicio mínimo nuevas y seguidas con cambios; métricas contextuales enumeradas (§6).
11. Cada métrica tiene fuente/campo/definición/destino; agregados no confiables omitidos (§6).
12. Sobrecarga: App, Discovery details, duplicación de matrices, Vision/raw/UUID, visor alto (§10).
13. Tres niveles: operación → fuente/decisión → diagnóstico (§5).
14. Tokens navy/light/blue y estados, spacing/radius (§9).
15. Inter/system, jerarquía30/20/16/14/13, filas compactas y layout desktop (§9).
16. Componentes shell/nav/header/card/badge/filter/table/states/source/provenance/review/viewer/timeline/menu/dialog (§11).
17. Reutilizar lógica/domain UI de componentes comerciales, review, readiness, propuesta, empresa y Discovery (§10–11).
18. Rediseñar composición de App, estilos inline, navegación y documentos; evitar reescritura (§10).
19. Integraciones faltantes: shell/rutas/retorno, Inicio real, fuentes cross-screen y vistas enfocadas (§10–12).
20. API gap: resumen transversal no verificado; no necesario para Inicio mínimo. Sin nuevo dominio/API implementado (§12).
21. Scope rename visible exacto por archivo; claves/contratos/historia permanecen (§14).
22. Auditoría estática sin mocks runtime detectados; no equivale a test dinámico (§14).
23. Tres tamaños desktop, sidebar/panel plegables y overflow local (§15).
24. Criterios a11y medibles, sin claim de certificación (§15).
25. UI-R1–R7 y sus gates delimitados (§16).
26. UI-R0: README.md, docs/roadmap.md, docs/PRODUCT_UI_BLUEPRINT_v0.1.md y este archivo.
    Artefactos locales no versionados: backend/reports/ui_r0/asset_inventory.json,
    m10d_commit.json y validation.json. Lista exacta22 del commit en m10d_commit.json / git show.
27. Decisiones y límites pendientes de aprobación (§17); no blocker para revisar esta especificación.
28. UI-R0 listo para revisión arquitectónica; documentación sin stage/commit/push. R1–R7 no implementados.
