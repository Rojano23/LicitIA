# ADR-0021 — Recuperación local coherente y retry del producto

Estado: implementado para revisión arquitectónica RC-H3. RC-H2 ACCEPTED.

## Contexto y decisión

La unidad de backup es toda la DB de aplicación más su root de datos, incluidos
originales, manifiestos, resultados, revisiones y recibos de presupuesto/generación.
Los derivados son regenerables pero se incluyen: regenerar no equivale a restaurar
la identidad exacta de la evidencia revisada. No se añade otra provenance ni schema.

Se reutilizan las herramientas nativas [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html)
y [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
El snapshot inicial de PostgreSQL se copia sólo detenido, conforme al contrato de
[backup filesystem](https://www.postgresql.org/docs/17/backup-file.html). La exclusión
del launcher, listeners apagados, PID/locks y confirmación administrativa de todos
los escritores detenidos son requisitos. Esto cubre la instalación canónica local;
no certifica escritores ajenos al launcher ni un filesystem montado compartido.

Un clon offline del clúster produce el dump mediante socket Unix privado sin listener
TCP. El clúster original no se inicia/modifica. El directorio portable contiene dump
custom, storage y manifest JSON versionado con SHA-256/tamaño de cada archivo,
fecha UTC, HEAD y hash de código, schema, identidad opaca de DB/root y conteo de
huérfanos detectados. No excluye archivos por ser ocultos. No borra huérfanos.
Incluye locks vacíos como archivos; su posesión por procesos es efímera y no se restaura.
Excluye runtime.json/contraseña, roles globales, entorno y pesos de modelos.
Permisos 0700/0600; no transferencia cloud. Checksums detectan corrupción, no autentican
un backup manipulado: restore es administrativo, de artefactos locales confiables.

Restore exige el schema exacto instalado y valida todo antes de modificar DB/storage.
Copia el backup a un snapshot privado, verifica su inventario y exige identidad exacta
con el manifiesto inicial. Cambios posteriores en el backup externo no pueden mezclar
generaciones de DB/storage. Construye un clúster nuevo con las credenciales del destino, importa el dump, verifica
originales y manifiestos referenciados y sólo entonces intercambia postgres/data.
Retiene el par anterior. Un journal durable de renames permite rollback si hay
interrupción entre ambos; el arranque se niega con journal pendiente. Si el journal
ya indica COMMITTED, recuperación finaliza el par nuevo. No se presume una operación
atómica única entre DB y filesystem. Un error previo al swap sólo elimina staging
inactivo, nunca datos actuales. No se elimina staging con PostgreSQL todavía activo.

## Retry normal

GET recovery produce elegibilidad y fingerprint operativo; POST retry exige ese
fingerprint y vuelve a comprobarlo bajo el lock de Tender. Verifica hash/tamaño del
original, consistencia de páginas, evidencia estructurada, código/paquetes actuales
y recibos/estados de proveedores. La identidad de procesamiento se conserva en el
estado operacional; un cambio indica STALE, sin aplicar revisiones a otro objeto.
Los estados H2 anteriores sin identidad se comprueban por fuente/evidencia al primer
retry; no se inventa retrospectivamente su configuración.

Un parser fallido puede regresar a PENDING sólo sin páginas ni extracción materializada
previa. Fuentes cambiadas/ausentes o evidencia inconsistente requieren soporte/revisión,
no borrado automático. Completados/interrumpidos/errores parciales reutilizan Native
coherente y los materializadores existentes. Quantity puede regenerar ID; no aumenta
el conteo equivalente ni se reasigna por orden. Revisiones Scope existentes siguen
su contrato de snapshot/fingerprint; ninguna se traslada a otro ID/generación.

El retry de Workspace es AVAILABLE_ONLY: no reintenta una adquisición de proveedor,
no modifica budgets, fingerprints ni recibos agotados. Los controles de adquisición
existentes conservan su política. Fallos OCR/Vision se exponen como percepción degradada
con revisión humana sin invalidar Native/Camelot válido. No dispara percepción por
un fallo de interpretación. El protocolo/historia blind permanece inmutable y separado.

## Límites y retención

Sólo clúster privado RC-H1 PostgreSQL 17, sin tablespaces/links externos, y root local
canónico. No auth, cloud, export comercial, scheduler ni GC. Backups/pares anteriores
contienen datos confidenciales: retención manual del administrador y al menos un
backup verificado antes de eliminar copias previas; sin eliminación automática.
Un fallo de parada de un PostgreSQL temporal conserva su staging; requiere soporte
para detener ese proceso específico antes de retirar el directorio. No hay claim de
consistencia con escritores fuera del contrato, de backup online, de recuperación
ante fallo físico del disco o de certificación de SO nuevo.

Quantity auditada: DEFERRED P1. Los reviews persistidos están especializados; el de
Scope sólo permite description y snapshot de Scope. Quantity requiere contrato/migración
adicional y aprobación arquitectónica previa. No se añade subsistema paralelo ni se
sobrescribe evidencia extraída.
