# ADR 0014 — Harness ciego selectivo con freeze en dos etapas

Estado: propuesta implementada para revisión arquitectónica MVP-06.V.5a.

## Contexto

El contrato histórico ciego AVAILABLE_ONLY prohíbe inferencia y no puede debilitarse
para medir los servicios selectivos aceptados en ADRs0012/0013. Un pase futuro
requiere perfil explícito, tareas genéricas, presupuestos y evidencia inmutable.

## Decisión

Mantener BlindConfig, el manifest histórico y el CLI de instrumentación sin cambios.
Introducir DI_BLIND_SELECTIVE_001 en módulos propios de perfil/harness/freeze y
un CLI explícito. HISTORICAL_SAFE sólo admite AVAILABLE_ONLY; SELECTIVE_PERCEPTION
puede permitir ALLOW_OCR/AUTO bajo el mismo significado aceptado de cada política.
El perfil no habilita proveedores por disponibilidad ni por dificultad del parser.

Los contratos por tarea se construyen de páginas/regiones canónicas y política,
no de identidad o contenido conocido del Tender. Las preguntas espaciales requieren
contratos IMAGE_LAYOUT_RELATIONSHIP explícitos congelados y un binding IMAGE válido;
no se deducen de un fallo OCR ni afirman semántica contractual de la imagen. Sin esos
contratos no hay Vision automático. Se comprueba suficiencia antes de seleccionar
regiones y nuevamente tras OCR. Evidencia suficiente evita adquisición. Los vectores
sin región conocida permanecen gap. No se mejora extracción ni gramáticas de dominio.

OCR tiene un límite agregado obligatorio, sin default derivado del corpus. Vision
comparte el presupuesto aceptado de 4 llamadas/tareas/páginas y dos intentos máximos,
60s y tokens600/1000; el perfil puede reducir estos valores, no ampliarlos. Cada motor
se fija explícitamente. Guard de aplicación comprueba planes registrados, política,
configuración y presupuesto; sólo los wrappers permitidos alcanzan clientes canónicos.
No es un sandbox contra código arbitrario externo al harness. Los ejecutores aceptados
siguen controlando fingerprint/reuse/exhaustion; no se reimplementa esa lógica.

Pre-execution freeze exige código limpio/committed y DB vacía072 antes de contacto con
corpus. Incluye hashes de código/protocolo/ADRs, perfil, versiones/prompt/schema,
dependencias/runtime/availability sin inferencia y presupuestos. Tras importación
canónica autorizada se escribe input_binding separado e inmutable con originales,
identidades, hashes y generaciones iniciales. No se modifica el pre-freeze.

EXECUTION_STARTED es exclusivo: ni fallo ni interrupción permiten rerun del pase.
Se conservan eventos exclusivos incluso si falla una fase posterior. El éxito produce
first_pass JSON/Markdown y marcador con hashes; un fallo conserva BLOCKED y evidencia
parcial. Toda corrección posterior a Attempt #3 requiere nuevo commit y Attempt #4.
La ejecución debe verificar nuevamente identidad original/código/config antes del cierre.

Los motores no son importados por el preflight. Paquetes/executable/tessdata/manifest
locales describen presencia, no calidad ni disponibilidad de inferencia. El servicio
no se prueba automáticamente y el digest del modelo es parte del freeze declarado.
La CLI futura fuerza DB local aislada/data-root aparte y deshabilita IA automática
ajena al flujo selectivo. No implementa reset/import ni los autoriza.

## Consecuencias

Sin esquema ni migración nuevos. El collector existente conserva métricas de dominio,
provenance, conflicts y review; el reporte añade estados de planificación/adquisición,
reuso y agotamiento. Un ACK incierto OCR conserva calls=None, no cero ficticio. Los
contadores de reservas limitan intentos aun cuando no se pueda certificar inferencia.
El guard registra rechazos con calls0 y los trata como violación dura de protocolo.

Recibos/eventos congelados se retienen hasta aceptación humana y sólo se eliminan por
acción explícita; no son un stream indefinido. No se convierte éxito operacional o
mocks en calidad semántica real. No hay nuevo run_id/freeze real en este slice.

## Refinamiento V.5a.1 — evidencia del freeze

El contrato selectivo002 exige evidencia de drift aceptado: current/head072,
59 operaciones de índice (55 add/4 remove), algoritmo normalizado versionado y
firma `3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7`.
El observador Alembic usa conexión sólo lectura; revisión igual no sustituye
comparación de firma/conteo. Crear/verificar con baseline distinto o ausente falla
cerrado. No afecta el contrato ni los artefactos del modo ciego histórico.

El binding post-import conserva original_filename exactamente como metadata de
identidad. No lo usa para semántica, planning ni logical procurement identity.
Se mantienen hashes/tamaños/MIME independientes y unicidad documental existente.
Este refinamiento sólo cierra evidencia; no cambia percepción, tareas o budgets.
