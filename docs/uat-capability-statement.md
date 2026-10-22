# Declaración de capacidades para la primera UAT de LicitIA

Estado arquitectónico aceptado el 2026-10-21: **LIMITED UAT**. Audiencia: participantes informados y acompañados en entorno local controlado. La incorporación de usuarios externos queda condicionada a los gates operacionales de RC; la aceptación del alcance no certifica entrega actual del producto.

LicitIA ofrece asistencia documental trazable; no garantiza extracción completa ni aceptación autónoma de obligaciones. Todo uso contractual requiere contraste humano con originales.

## Qué puede probar el usuario

- Importar y revisar originales/versiones y procesamiento unsupported.
- Revisar Scope de tablas digitales elegibles con navegación a fuente; confirmar/corregir la descripción de Scope mediante revisión humana. Quantity se muestra ligada a su Scope, con fuente y estado automático, de solo lectura; su revisión/edición independiente queda pendiente P1 (RC-H3). Confirmar Scope no confirma Quantity.
- Usar Requirements como propuestas revisables, contrastadas contra originales y checklist humano.
- Evaluar Requested Evidence como borrador incompleto de documentos/paquetes, nunca como inventario exhaustivo.
- Probar provenance, revisión humana y surfacing de conflictos sin asumir que toda discrepancia es contractual.

## Qué requiere contraste y no debe asumirse

- Completitud autónoma del expediente, obligaciones, plazos o entregables.
- Scope tabular como sustituto de lectura de prosa/anexos/referencias cruzadas.
- Marca/modelo embebidos como Attributes materializados o matching automático certificado.
- Requested Evidence como lista definitiva de presentación/cumplimiento.
- Anchors Vision/OCR como transcripción literal validada o owner confiable; scans deben contrastarse visualmente.
- Conflictos como decisiones contractuales resueltas ni propuestas automáticas como aceptación humana.

## Limitaciones que deben comunicarse al participante

- Los fabricantes/modelos embebidos se conservan en la descripción, pero no aparecen necesariamente como Attributes.
- Requirements puede incluir encabezados/contexto, truncaciones y obligaciones de otro actor; requiere decidir aplicabilidad.
- Requested Evidence puede representar paquetes incompletos, tipos demasiado amplios o contexto; no equivale al inventario de entrega.
- Tablas escaneadas/complex layouts y texto visual pueden fallar o alterar identificadores. Los estados de revisión no deben ocultarse.
- Source effects/resolución de conflictos y aceptación de alcance permanecen bajo decisión humana; no hay decisión automática de cumplimiento.
- Que un registro falte no significa que una obligación o accesorio no exista. Leer también prosa, anexos y referencias cruzadas.

Antes del primer piloto, entregar este documento y demostrar navegación a fuente, confirmación/corrección/rechazo y tratamiento de pendientes. Este artifact documenta la frontera; no afirma que ya se haya entregado a usuarios ni modificado la UI.


## Condiciones operacionales de primera UAT

Instancia local aislada y assets preinstalados, originales accesibles, backup/restore probado y soporte identificado. No compartir instancia sin control de acceso. Las solicitudes de corrección de Quantity/Attributes no soportadas por la UI deben capturarse explícitamente con padre/fuente/valor propuesto, sin cambiar silenciosamente el valor máquina. La planilla UAT no sustituye auditoría productiva.

Consultar [readiness RC](release-candidate-limited-uat-readiness.md) para losP0y el recorrido aún pendiente. Que un engine esté validado no implica que ya exista un botón para ejecutar todos los pasos ni un export listo. Usar sólo expedientes con permiso y perfil PEMEX/SNR del MVP.
