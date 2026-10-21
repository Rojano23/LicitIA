# RELEASE CANDIDATE / LIMITED UAT — revisión de operabilidad

Fecha: **2026-10-21**. Motor HEAD `14097f428e2185152aae1b671485244f1656fb07`.
MVP-06.V: **CLOSED**, decisión arquitectónica aceptada **OPTION B — LIMITED UAT**; [cierre canónico](mvp-06v-closure.md).

**Readiness actual: NO-GO para incorporar hoy al primer participante externo sin hardening.** Esto no reabre el motor ni contradice el cierre. El camino demostrado por harness no certifica entrega UI/API, instalación y recuperación. Un ensayo interno acompañado es distinto de un producto reproducible listo para varios usuarios.

## Método, alcance y límites de esta revisión

Inspección estática del working tree y evidencia congelada; no arranque de aplicación/proveedores, inferencias, DB mutations, instalación limpia, prueba de navegador, penetración, restore ni ejecución de corpus. READY significa función encontrada en código y contratos previos, no un nuevo ensayo de usabilidad end-to-end. No se inventan fallos en vivo ni se declara air-gap certificado. Sólo documentación canónica cambia; los artifacts blind/adjudicación quedan intactos.

Fuentes principales: README.md; docs/architecture.md y roadmap.md; docker-compose.yml; .env.example/backend/.env.example; backend/requirements.txt y pyproject.toml; frontend/package*.json y vite.config.ts; backend/app/main.py,config.py,database.py,ocr.py,local_vision.py,ollama_vision.py,selective_*_executor.py,blind_selective_harness.py,scope_review.py,camelot_table_adapter.py/worker.py; frontend/src/App.tsx y components/ScopeReview.tsx; declaración UAT aceptada bajo Attempt9.

## 1. Recorrido de usuario

| Paso | Estado | Evidencia/límite |
|---|---|---|
| Acceso/login | MISSING | No auth/roles en API; CORS no es control de acceso. Para primer piloto: instancia/OS account por participante y loopback; servicio compartido requiere auth antes de exponerlo. |
| Crear/seleccionar Tender | READY | POST/GET /tenders y selección persistida por UUID en navegador. No equivale a tenant isolation. |
| Subir documentos | READY | Carga múltiple/carpeta, hash, duplicados y conflictos/revisiones; faltan límites globales/validación fuerte antes de documentos no controlados. |
| Procesamiento | PARTIAL | Botones separados Native/OCR/clasificación/requisitos/items. analyze-items no llama al materializador ScopeDetail/Camelot; la composición validada está en blind_selective_harness.materialize_canonical, no un flujo normal expuesto. |
| Visibilidad de progreso | PARTIAL | Loading por acción y estados de documento persistidos; no fase global durable, job/reanudación o progreso verificable después de recargar. |
| Errores/advertencias | PARTIAL | Estados y banners presentes; varios mensajes genéricos, excepciones heterogéneas y diagnósticos técnicos sin paso de recuperación. |
| Revisión Requirements | PARTIAL | Matriz y APPROVE/MARK_NEEDS_REVIEW/REJECT/RESET con nota y navegación; no editor completo de semántica ni garantía de inventario. |
| Revisión Requested Evidence | PARTIAL | Tipos/descripciones visibles y matching con evidencia empresarial; no se encontró editor/revisión independiente de cada solicitud extraída. |
| Revisión Scope | PARTIAL | ScopeReview ofrece confirmar/corregir descripción/rechazar con historia y fuente. Falta camino ordinario desde expediente nuevo a estos ScopeDetails. |
| Revisión Quantity | MISSING | Vista TenderItems contiene quantity legacy; no demuestra UI de TenderScopeQuantity canónica con padre/review/corrección. Scope review explícitamente excluye edición Quantity/Attributes. |
| Fuente/provenance | PARTIAL | Scope: doc/revisión/página/excerpt/enlace PDF; Requirements: source occurrence. No highlight de spans/celdas ni navegación uniforme para Quantity/Evidence. |
| Corrección humana | PARTIAL | Descripción Scope y revisiones/rechazos maduros; Quantity/Attributes y tipado de Requested Evidence sin corrección equivalente. |
| Conflictos/review | PARTIAL | Resolución humana de revisiones de archivos y estados efectivos; discrepancia perceptual no significa contradicción contractual. Consolidación de pendientes incompleta. |
| Guardar/reabrir | READY | PostgreSQL/filesystem y selección localStorage. Persiste información; no prueba recuperación de operación en vuelo. |
| Export/report | MISSING | No export funcional de usuario encontrado para conjunto Requirements/Evidence/Scope/Quantity/review/notas/provenance. GET JSON no equivale a export UX. |
| Completar/archivar proyecto | NOT REQUIRED FOR LIMITED UAT | Sin cierre/archivo de Tender dedicado observado. Operador puede conservar expediente sin borrado; archivo de company document no es archivo de Tender. |

No se marca BROKEN sin reproducir un fallo concreto. MISSING significa ausencia de la capacidad específica en la superficie revisada, no que todo backend carezca de contratos. Recomendación inicial: un Tender es el proyecto; no añadir una entidad Project ni un sistema nuevo de archivo para el piloto.

### Brecha entre motor y recorrido normal

La búsqueda de llamadas a materialize_document_scope_details en backend/app encuentra la composición productiva en blind_selective_harness.materialize_canonical y un replay de calibración. main.py expone scope-review de lectura/decisión, pero no ese procesamiento para expediente nuevo. /analyze-items llama tender_items.analyze_tender_document_items, motor legacy de TenderItems; no se debe confundir con ScopeDetail/StructuredEvidenceBlock/Quantity canónicas. La lista de revisión no crea hechos al abrirla. El primer hardening funcional debe conectar servicios existentes; NO ejecutar el harness blind ni reutilizar validation DB como API del producto.

## 2. Instalación y despliegue

**PARTIAL; instalación limpia no demostrada.** README refleja todavía la línea base histórica MVP01 y no ofrece receta end-to-end actual. No Tauri/instalador localizado, aunque arquitectura lo contempla; aplicación observada: web React/Vite + API local + PostgreSQL.

| Componente | Hallazgo actual | Requisito de RC |
|---|---|---|
| OS | Worker Camelot importa resource POSIX; rutas Homebrew/macOS y Python local en instrucciones | Primer RC con OS/arquitectura explícitos; no prometer Windows. Linux requeriría validar rutas/binarios. |
| Python | Proyecto >=3.11; entorno validado3.13.15 | Elegir/fijar runtime probado, venv por instalación. |
| Backend deps | requirements con pins directos, pyproject declara sólo3deps; no lock transitivo | Fuente de instalación única y lock completo con hashes/plataforma. No basta pip install -e. |
| Discrepancia real | PyMuPDF declarado1.26.3; entorno instalado validado1.28.2 | Resolver bajo slice autorizado y revalidar; no cambiar versión silenciosamente en esta revisión. |
| Frontend | package-lock presente; React18/Vite5; scripts dev/preview host0.0.0.0 | Fijar Node/npm soportados y build/serve local reproducible; no exponer dev server a usuarios en LAN. |
| PostgreSQL | compose postgres16-alpine, tag mutable, volumen; puerto5432 publicado y passwords ejemplo change_me | DB/usuario UAT independientes, credenciales propias, bindloopback, backup; imagen resuelta por digest para RC. |
| Redis | No requerido ni incluido | No añadir infraestructura. |
| Tesseract | Binario externo y spa/eng no instalados por pip | Receta binario/version/tessdata hashes; fail claro si faltan. |
| Ollama/model | Servicio externo local, modelo adquirido aparte; perfiles blind congelados | Separar opcionalidad y capacidades; instalar/precache explícitamente, registrar runtime/model digest en RC. No hacerlo permanente en dominio. |
| Camelot | camelot-py2.0.0,lattice/combined,PDFium/OpenCV; no Ghostscript para config aceptada | Wheels compatibles/licencias/notices; probar desde entorno limpio. |
| Migraciones | Head072; drift59 aceptado con firma congelada | Alembic autoridad; no copiar esquema ni aplicar drift como reparaciones manuales. |
| Config/root | .env relativo al cwd, LICITIA_DATA_DIR relativo a backend si se usa flujo habitual; defaults de desarrollo | Ruta absoluta por instalación, permisos restringidos, espacio libre y política de backup. No reutilizar roots blind/dev/test. |
| Orden/puertos | PG5432→Alembic→API8000→frontend5173 (preview4173); Ollama11434 si se habilita | Runbook/launcher con cwd/settings/ports y comprobación de conflicto. |
| Salud | /health devuelve sólo statusok | Readiness no inferencial DB/revision/root/espacio/assets; proveedor opcional degradado visible, no bloquear Native. |

Pasos hoy manuales o no documentados de extremo a extremo: instalación OS/Python/Node/PG; creación rol/DB; venv/deps transitorias y OCR/Paddle opcionales; tessdata; servicio/modelo Ollama; variables de AI ausentes en ejemplos; cwd/root y permisos; migraciones; start order; builds y puertos; corpus upload→normalize→materialización; backup/restore; soporte/retención. Ninguno se automatiza aquí.

## 3. Red, privacidad y offline

| Destino/dependencia | Clasificación | Evaluación |
|---|---|---|
| Browser→API8000 | REQUIRED LOCAL | App.tsx API_URL fijo localhost8000; remoto requiere configurar/revisar CORS y auth, no simple sustitución de URL. |
| API→PostgreSQL | REQUIRED LOCAL | DSN configurable; para piloto exigir instancia del cliente y no credenciales compartidas. |
| API→Ollama11434 | REQUIRED LOCAL sólo si se habilita Vision/semántica | Default loopback; paquetes/documentos enviados al runtime local. Native/Camelot no requieren inferencia. |
| Tesseract/Camelot/FS | REQUIRED LOCAL | Subprocess/archivos, sin servicio cloud propio. Selective OCR worker bloquea sockets. |
| Descarga de Python/npm/modelos/wheels/tessdata | OPTIONAL EXTERNAL durante instalación | Debe ocurrir antes del modo offline, sin documentos de cliente. No es dependencia runtime obligatoria del flujo determinista. |
| PaddleOCR legacy con assets ausentes | UNEXPECTED EXTERNAL potencial en runtime | PaddleOCR(lang=...) sin guard de red en ruta OCR normal puede intentar resolver assets; no se afirma envío de contenido. Excluir/precache y bloquear egress para piloto; selective worker sí deniega red. |
| URL Ollama reconfigurada a externo | OPTIONAL EXTERNAL sólo con autorización, hoy enforcement desigual | VisionConfiguration selectiva exige loopback, pero clientes legacy toman Settings.base_url directamente. Una mala configuración podría sacar imágenes/texto; gateP0 de aislamiento/config. No envío externo observado en Attempt9. |
| Links web dentro de documentos | OPTIONAL EXTERNAL por acción humana | No requeridos por el procesamiento; no usar enlaces/certificadores externos como dependencia implícita ni abrirlos automáticamente. |

No se encontró telemetría/cloud documental obligatorio en los módulos inspeccionados. No equivale a análisis exhaustivo de dependencias binarias. **Offline plausible, no demostrado para el producto completo instalado desde cero.** Piloto: assets presentes, Tesseract seleccionado explícitamente, direcciones locales y egress denegado salvo destinos locales autorizados; verificar sin Internet con PDF sintético. Un flujo externo que envíe documentos sin autorización seríaP0; aquí se identifica riesgo de configuración, no una exfiltración observada.

## 4. Abstracción de proveedor

Hay OCR provider classes y ScopeSemanticDiscoveryProvider Protocol; typed schemas/adapters y validación separan propuestas del dominio. El modelo es configurable y las decisiones humanas no dependen de marca Qwen. Aun así, OllamaVisionAssistService construye cliente concreto; schemas/provenance y tareas legacy conservan semántica de respuesta/manifest Ollama, modelos default en config/constants y varios clientes especializados urllib. Materializadores conocen fuentes/capacidades y payloads versionados, no una API cloud universal.

**PARTIAL, prioridadP1 para desacoplamiento más uniforme**; no justifica reescritura ni bloquea un piloto local restringido. P0 sólo si una ruta permite enviar fuera del entorno o si proveedor ausente impide procesar evidencia determinista. Cambiar proveedor debe conservar contratos de capacidades, source/proof/review, no sólo renombrar modelo. El digest/config del RC identifica infraestructura del ensayo, no una dependencia contractual permanente.

## 5. Errores, progreso y recuperación

| Situación | Comportamiento localizado | Readiness |
|---|---|---|
| Unsupported | 400 al extraer no-PDF; import puede quedar PENDING | PARTIAL: explicar unsupported y conservar original; no prometer parser de ZIP/DOCX. |
| PDF corrupto | TEXT_EXTRACTION_FAILED y HTTP500 con detalle del parser | PARTIAL: original permanece; mensaje de usuario y protección contra loops faltan. |
| Original ausente | 404 o integridad/path failure | PARTIAL: restaurar original exacto, no reemplazar bytes bajo misma identidad. |
| OCR no disponible/fallo | 503 al seleccionar engine ausente; resultados por página/worker bounded | PARTIAL: la UI legacy no hereda todas las garantías de selective executor. |
| Vision timeout/Ollama offline | Probes/status y resultadosFAILED/UNAVAILABLE/INVALID_JSON; UI error genérico | PARTIAL: mostrar causa útil y conservar el último resultado válido identificado como tal. |
| Tesseract ausente | ProviderUNAVAILABLE/503 | PARTIAL: readiness/check de instalación, no descarga silenciosa. |
| Camelot fallo | Subprocess35s/CPU30s, excepción explícita o abstención | PARTIAL: fail-closed de evidencia; aún falta recuperación y mensaje en recorrido de usuario normal. |
| DB caída | Conexión/excepción; /health sólo responde statusok | PARTIAL: /health no demuestra DB/root/provider listos; no hay readiness compuesto. |
| Interrupción de procesamiento | Requests síncronos/commits por fases; no job durable global | PARTIAL: no garantizar cancelación por cerrar pestaña ni reanudación automática. |
| Disco insuficiente | Staging/cleanup intentan proteger original; sin quota/preflight global | PARTIAL: coherencia DB/FS y huérfanos deben verificarse; evitar retry ciego. |
| Respuesta de modelo malformada | Schema/Pydantic e INVALID_JSON/failure | PARTIAL: no prosa cruda canónica; error no debe aparecer como evidencia validada. |
| Resultado parcial/review | Estados REVIEW_REQUIRED/UNKNOWN y algunos banners/scope_notes | PARTIAL: estados legibles por dominio pero sin resumen único de completitud del expediente. |

La extracción Native no borra páginas hasta terminar lectura inicial; después reemplaza document.pages, cambia IDs/generaciones y puede dejar refs históricas stale por cascadas. No es suficiente afirmar retry inocuo. El contrato debe invalidar/auditar derivados/revisiones afectados y preservar la evidencia que soportó decisiones. No se ha demostrado restore/retry seguro en esta revisión.

Estados mínimos de producto recomendados: pendiente→en proceso/fase→completado/completado parcial/fallido; review es un eje separado de éxito técnico. Identidad durable de operación, hora/último avance y causa/paso siguiente; al recargar recuperar estado real, sin prometer cancelación. Implementación local pequeña con estado persistente y exclusión por expediente basta; no Redis/Kafka/Kubernetes. Un estado conservador de resultado parcial es preferible a progreso porcentual inventado.

**Blind benchmarks:** identidad/start-marker/first-pass inmutables; nunca retry whole-run. **Producto:** un usuario sí debe poder reintentar una operación fallida cuando sea seguro, con identidad nueva por ejecución y generaciones/revisión auditadas, sin sobrescribir originales ni decisiones. No heredar prohibiciones de benchmark a UI normal ni usar sus scripts para usuarios.

## 6. Review UX, fuentes y export

ScopeReview.tsx tiene estado efectivo/máquina/humano separados, descripción completa, confirmar/corregir/rechazar, nota e historia; source document/revisión/página/excerpt y enlace /content#page=N. La tarjeta trunca pero detalle no. Requirements tiene review/nota/source occurrences; Requested Evidence sólo asistencia y matching parcial. Faltan revisión numérica canónica y editor específico Evidence. No llamar confianza calibrada a scores/prosa de modelos.

Source navigation es útil pero no uniforme: navegadorPDF debe respetar fragment#page, y no existe highlight multispan/celda. El manifest estructural permanece disponible en backend; no se afirma que el usuario entienda su locator técnico. Validar click→página correcta y comparación cómoda en piloto, sin exponer rutas absolutas internas.

Export: no hay botón/servicio tabular de usuario localizado. Para primer UAT de tareas dentro de app puede aceptarse una planilla administrada de medición **sin prometer export de resultados**. Si usuarios deben llevar resultados al trabajo diario, mínimo antes de esa actividad: archivo local simple CSV/JSON con tipo/ID,descripción,cantidad/unidad,parent,estado/nota humana,documento/revisión/página/excerpt y advertencia de completitud; neutralizar fórmulasCSV y limitar datos exportados. Excel/PDF de presentación esP2, no se implementa.

## 7. Datos, auth y backup

Hay aislamiento lógico por tender_id/company_id, checks documento→Tender y UUID/rutas controladas. **No es autorización:** endpoints generales /documents/{id},GET /tenders y lecturas de originales son accesibles para cualquier cliente con acceso a la API. No login/roles/tenant membership encontrado. CORS no protege frente a clientes directos. No varias empresas con documentación privada en una instancia compartida sin control adicional.

Modelo mínimo:3–5participantes, cada uno con instancia/root/DB o cuenta/host aislado, API/UI/PG sólo loopback, acceso por sesiónSO autorizada, disco protegido y soporte sin acceso documental automático. Sesiones acompañadas en una estación dedicada también son posibles si datasets autorizan visibilidad y se reinicializa operacionalmente entre organizaciones. Si se exige servidorLAN o concurrencia multiusuario, auth+autorización de Tender y TLS son prerrequisitosP0; IAM empresarial/RBAC complejo no lo son para instancias personales.

Originales se guardan con SHA/staging/rutaUUID y contención al resolver. FS y PostgreSQL no son una sola transacción: un fallo después de escribir archivo y antes de commit puede dejar huérfanos. Sin lifecycle/GC/quota para históricos/failed artifacts; no borrar reportes o manifests por edad sin comprobar referencias. Archivo company document existe; no se encontró DELETE/Tender archive global en las rutas revisadas. No inventar borrado seguro por ausencia de botón.

### Backup mínimo propuesto antes de recibir datos externos

1. Elegir DB/root UAT dedicados y registrar HEAD/lock/Alembic/model-config. Acceso sólo al operador autorizado; no usar bases validation/dev por conveniencia.
2. Detener nuevas escrituras y esperar operaciones; la simple copia del filesystem durante escritura no da snapshot coherente. Registrar hora y último estado confirmado.
3. Export PostgreSQL mediante pg_dump formato custom; copiar **todo** LICITIA_DATA_DIR, incluidos originales, manifests, derivados y evidencias de revisión. Conservar settings necesarios saneados y secretos por canal protegido separado.
4. ManifestSHA para dump/root y metadatos de versión. Backup local protegido/cifrado según política cliente y segunda copia autorizada; nunca subirlo a cloud por defecto. Definir retención/cuota y responsables, sin guardar indefinidamente cada payload/debug.
5. Restaurar primero en DB/root NUEVOS aislados; revisar Alembic/hash/tamaño/provenance y una decisión humana persistida. No tocar benchmarks. Abrir fuente y reabrir el expediente; documentar resultado y tiempo de restauración.
6. Proponer backup previo a actualización/import importante y al cierre de cada jornada UAT; acordar RPO/RTO/retención con responsable. No se inventan objetivos aprobados ni se ejecuta el procedimiento en esta tarea.

pg_dump no respalda originales; copiar sólo PDFs no respalda decisions/DB; un volumen Docker no es backup probado.

## 8. Observabilidad y recursos

Hay IDs de Tender/document/page/generation, status por página, registros de proveedor con duración/errores/respuesta, manifiestos y metadata de visión/OCR. Attempt9 tuvo recibos detallados; **no se presume la misma trazabilidad de run en UI normal**. Logs de servidor/excepciones no tienen un contrato central de correlación/redacción/retención. Raw responses, excerpts y stderr pueden contener datos sensibles; evitar enviarlos a tickets/logs generales.

MínimoRC: identificador de operación/doc, fase, duración, código de error, estado parcial y ubicación local de diagnóstico con permisos; sin texto completo en logs por defecto. Una captura de usuario puede contener información confidencial. Métrica de memoria/Ollama y disco es operativa, no nuevo stream sin retención.

Camelot:128MiBoriginal/2MiBproposal/32tables/4096cells,35sdeadline/30sCPU,cache16; **no hard OS RAM limit** y renderer puede asignar memoria antes del timeout. OCRselectivo2x/8Mpx/8MiB/30s con ceiling60s; límites de endpointOCRlegacy no son necesariamente los mismos. Ollama comparteRAM con OS y renderers. No admisión global de concurrencia/cuota/cancelación localizada.

Ausencia de hardRAM **no bloquea por sí sola** UAT acotada: operador, un expediente/documento a la vez, archivos controlados y tamaño/páginas aprobados en runbook, monitor local de memoria/disco y suspensión de nuevos trabajos al llegar al límite operativo. No afirmar que inputlimit protege todoPDFpatológico. Antes de carga no confiable/muchos usuarios, límites y aislamiento mayores sonP1; si no puede imponerse el control operacional mínimo, se vuelveP0.

## 9. Seguridad y privacidad práctica

- Positivo: nombres de archivo saneados para almacenamiento, UUIDdir, resolve y checkis_relative_to, parentesco documento/Tender, originales sin ejecución shell, respuestasLLM tipadas/Pydantic antes de dominio, revisión/abstención.
- Déficits: upload acepta MIME/extensión declarados y _is_pdf_document usa OR entre MIME/extensión; no sniffing fuerte, límite global de upload/páginas o cuota encontrados. /content sirve application/pdf si extensión/MIME declaraPDF. No resultado de exploit: registrar como riesgo con archivos no confiables.
- Ejecutables/ZIP: pueden almacenarse comounsupported; no descompresión automática ni ejecución subida localizada en flujo normal, por tanto no afirmar archivebomb explotable. Mantener no ejecución/no unpack, mostrar unsupported y aplicar límites; parserPDF sigue siendo superficie de riesgo.
- Prompt injection: tratar contenido como datos; el modelo no ejecuta herramientas en rutas inspeccionadas. Schema no prueba verdad ni evita toda instrucción adversaria; no actuar sobre URLs/instrucciones de documentos como comandos.
- Red: defaults locales no bastan si legacybase_url permite externo; gateconfig/egress antes de datos reales. Ninguna exfiltración observada; no auditoría de toda librería.
- Secretos: ejemploschange_me/no auth, .env del cwd; no leer ni imprimir secretos reales. Credenciales por instalación y permisosSO; keychain definido en arquitectura no equivale a implementación demostrada.
- Temporales: Camelot usa TemporaryDirectory/cleanup; render/payload/DBrawresponses y backups requieren permisos/retención; cleanup normal no garantiza eliminación tras kill/powerloss.
- Bind0.0.0.0 de dev y puertosDocker, sumados a faltaauth, constituyen riesgoP0 de exposición antes de primer usuario. Puede resolverse inicialmente por despliegue aislado verificable, sin IAMnuevo.

## 10. Dataset, participantes y medición

Primera ola recomendada: **3–5 usuarios** de licitaciones/compras y propuestas técnicas/comerciales, con perfiles mixtos de autor/revisor, acompañados por operador. No cifra de éxito, sino tamaño inicial administrable. Evitar mezclar clientes en una base compartida.

Seleccionar **varios expedientes reales autorizados** distintos de Tender002, idealmente3–5conjuntos distribuidos entre participantes si permisos lo permiten: digital simple, tabla con bordes, borderless, escaneado, mixto y uno con estructura/prosa compleja. Mantener perfil PEMEX/SNR del MVP; diversidad no autoriza CFE/estatal/privado. Hash/origen/permiso por expediente; separar desarrollo de evaluación y no tunear sobre el conjunto reservado sin una decisión nueva. Tender002 es referencia expuesta, no prueba ciega nueva.

| Medida | Captura/denominador |
|---|---|
| Aceptado sin cambio / con corrección menor | Por dominio y hallazgos revisados; definir menor/material antes de comenzar. |
| Falsos positivos | Hallazgos rechazados por falta de soporte/aplicabilidad / revisados; razón/criticidad. |
| Omisiones materiales | Inventario independiente de experto frente a resultados; registrar fuente y límites, no usar total extraído como recall. |
| Quantity correcta | Valor+unidad+Scope parent correctos / cantidades revisadas; errores críticos aparte. |
| Utilidad Requirements/Evidence | Sirve para acción real, aplicabilidad/tipo/completitud y minutos de corrección; evaluar por separado. |
| Tiempo | Inicio/fin revisión, correcciones incluidas, baseline manual comparable o estimación explícitamente etiquetada; evitar comparar tareas distintas. |
| Confianza/usabilidad | Breve valoración antes/después de consultar fuente, tareas completadas/ayuda requerida, problemas de comprensión de estado. |
| Fallos de procesamiento | Fase/doc/tipo/tiempo/recuperación/impacto en evidencia, sin contenido documental en tracker general. |
| Review/provenance | Minutos por hallazgo, pendientes, click a página correcta y utilidad del excerpt. |

No se fijan porcentajes de éxito sin baseline. Go/no-go inicial recomendado por seguridad/operación: no pérdida de datos o envío externo no autorizado, restauración demostrada, participante llega a evidencia y entiende límites; criterios de extracción/tiempo se acuerdan con arquitecto después de baseline. Un incidente de privacidad/integridad pausa incorporación y preserva evidencia para revisión humana.

## 11. Disclosure

La [declaración canónica](uat-capability-statement.md) deriva de la aceptada en Attempt9. Debe mostrarse: (a) onboarding inicial con alcance local y consentimiento dataset; (b) encabezado de módulosRequirements/Evidence/scan/Attributes con límites accionables; (c) instruccionesUAT con original obligatorio y protocolo de corrección/soporte. La UI actual tiene review y scope_notes pero no esta disclosure transversal. Esta tarea documenta; no afirma que se haya implementado en producto.

## 12. Backlog de hardening

P0 se limita a los cuatro gates de entrega siguientes; no incluye perfección semántica ni cambio de proveedor:

| ID | Gate | Mínimo | Evidencia de salida |
|---|---|---|---|
| P0-1 | Instancia local reproducible y aislada | Lock/backend y receta validada en instalación limpia; runtime/modelo/assets offline y settings explícitos; loopback+cuenta SO/instancia por participante, puertos PostgreSQL no expuestos, credenciales propias y egress restringido. Sin IAM empresarial si no hay servicio compartido. Verificar licencias/notices del paquete real antes de redistribuir. | Instalar desde cero, iniciar/reabrir sin Internet; documentar qué se bloquea y qué queda opcional; confirmar bindings/ausencia de acceso cruzado. |
| P0-2 | Recorrido normal del producto hacia resultados revisables | Exponer/orquestar los servicios ya aceptados para expediente nuevo sin invocar un script blind/reset/freeze. Estado durable mínimo y prevención de doble ejecución; leer Quantity canónica con padre y fuente. Para corrección numérica, declarar límite y capturar solicitud revisable sin sobrescribir silenciosamente; editor tipado completo puede seguir después. | Un usuario asistido importa PDF sintético nuevo, procesa sin CLI/harness, ve Scope/Quantity reales y sus fuentes, decide sobre Scope y reabre; fallos conservan incertidumbre. No tocar gramática/semántica. |
| P0-3 | Seguridad de datos y recuperación mínima | Backup coherente DB+root+manifests y ensayo restore aislado; documentar retry normal por fase con generaciones/revisiones y sin destruir decisiones/historial. Límite operacional de archivos/concurrencia y control de disco. | Restaurar en ubicación/DB de prueba independiente, validar hashes/navegación/decisión humana; simular una interrupción y ausencia de original sin modificar benchmarks. |
| P0-4 | Paquete de primer piloto y disclosure | Onboarding visible y guía que distingue hallazgo/revisión/ausencia; límites Requirements/Evidence/scan/Attributes explícitos, planillas de medición y soporte local sin textos sensibles en tickets por defecto. | Participante demuestra abrir fuente y rechazar/corregir; consiente dataset local y entiende que no hay checklist exhaustivo. Operador puede localizar documento/fase/error sin copiar contenido privado. |

**P1 — durante/después de primera UAT y antes de ampliar piloto:** edición tipada Quantity/Attributes con auditoría cuando se requiera; RequestedEvidence contextualización/tipado y Requirements; export útil si la tarea ya lo exige; jobs/retry más cómodos; validaciónMIME/resourceRAM/concurrencia más robusta para archivos no controlados; abstracción proveedor uniforme; logs saneados/retención; installer/restores automatizados; permisos por usuario si se decide compartir servidor. Sólo promovidos aP0si el modelo concreto de piloto los requiere.

**P2:** Excel/PDF pulido, highlighting de cada celda/span, cierre/archivo de proyecto integrado, otrosOS, dashboards y layouts nuevos guiados por resultados. No otro sliceDI automáticamente autorizado.

## 13. Definición propuesta RC-0.1

No crear tag/RC ahora. RC-0.1 debe identificar:

- HEAD/product artifact exacto **después** de hardening aceptado;14097f4es base del motor, no fingir que contiene las mejoras pendientes.
- Lock backend transitivo/plataforma/Python y package-lock/frontend/Node; licencias/notices del bundle existente revisados (incluyendo dependencias previas comoPyMuPDF), sin garantía legal emitida aquí.
- Alembic head072 y baseline drift59/firma aceptada, o decisión nueva explícita si hardening exigiera otra migración. Nunca copiar el drift a mano.
- OS/CPU/RAM/disco/puertos/data-root, PostgreSQL y procedimiento instalación/start/stop/health/backup/restore probados desde limpio.
- Proveedores opcionales/capacidades; siVisionhabilitado, versiónruntime/modeldigest/config/budgets y assets presentes; se congela el proveedor del RC, no el dominio aOllama.
- Matriz de capacidades soportadas, límites, tratamientounsupported/parcial/review/retry, declaraciónUAT y protección de datos.
- Prueba UI→API→servicios→fuente→decisión→reopen, offline local y recuperación, sobre sintético nuevo y datos autorizados; no rerun de benchmarks inmutables.

GateRC no es repetir2109tests para cada documento; focused→regresión relevante según superficie y luego suites delRC cuando correspondan. La evidencia pasada no certifica build/instalador nuevo.

## 14. Archivos que probablemente requieren cambios en slices posteriores

Estos son candidatos concretos, **no cambios realizados ni autorización de implementación**:

| Slice | Superficie | Tamaño |
|---|---|---|
| RC-H1: instalación local aislada | backend/requirements.txt,backend/pyproject.toml + futuro lock; docker-compose.yml;.env.example;backend/.env.example;frontend/package.json,vite.config.ts;README y futuro runbook/launcher local | SMALL/MEDIUM: acotado, sin engine; validar discrepanciaPyMuPDF y plataforma puede aumentar alcance. |
| RC-H2: camino de usuario y estado | backend/app/main.py,schemas.py + servicio de aplicación sobre scope_detail_materializer/quantity_materializer existentes; frontend/src/App.tsx,components/ScopeReview.tsx,api/scopeReview.ts; tests API/UI | MEDIUM: no cambiar gramática/proofs; modelo durable nuevo, si precisa DB, exige plan/migración/aceptación. No presuponer que blindharness es reusable como UI backend. |
| RC-H3: recuperación/backup | runbook/scripts nuevos; revisión main.extract_document_pages y almacenamiento/provenance; pruebas sintéticas de restore/retry; modelo de generación si el diseño lo requiere | MEDIUM: no borrar evidencia ni introducir cleanup sin política. |
| RC-H4: instrucciones/disclosure/medición | docs/uat-capability-statement.md, frontendApp/módulos, futuras instrucciones/plantilla local de resultados | SMALL. |
| Escalamiento multiusuario/export/edición tipada | auth boundaries/API/schema/UI y auditoría según decisión de piloto | MEDIUM/LARGE, no prerrequisito de estaciones individuales aisladas salvo que ese modelo cambie. |

**Esfuerzo total del hardening mínimo: MEDIUM, en slices revisables**, no una reescritura LARGE ni implementación silenciosa de todoLicitIA. No se dan días sin estimación con equipo/entorno objetivo.

**Primer slice recomendado: RC-H1 — receta local aislada reproducible y lock del RC.** Fijar el entorno de piloto, reconciliar versión instalada/declarada, configurar loopback/egress/assets y demostrar install/start/offline con sintético y health de dependencias sin inferencia. No hace falta modificar el motor. Luego RC-H2 es el primer slice funcional indispensable: expediente nuevo→servicios canónicos→review. No declarar usuarios listos sólo por completarRC-H1. Cada slice requiere autorización separada; no ejecutados en esta tarea.

## 15. Verificación y decisión

MVP-06.V permanece formalmente cerrado. **Limited UAT está aceptada como siguiente alcance; primera incorporación externa todavía condicionada aP0.** README/roadmap apuntan al cierre y no autorizan Attempt10 ni DIabierto. Sin cambio productivo, proveedores, DB, fuentesoriginales, historial congelado, stage/commit/push. Sólo documentación. No tests/suites/proveedores rerun: revisión estática, hashes y diffcheck; instalación/UI/recovery quedan por demostrar, no se reportan como PASS.
