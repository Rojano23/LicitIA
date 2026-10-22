# Administrador — quickstart local de LIMITED UAT

Para macOS Apple Silicon y herramientas exactas de [instalación](local-deployment.md). Sólo loopback, una instancia por participante/host; no servicio público. Motor cerrado no equivale a que RC-H2/UI esté terminado.

1. Obtener la copia aceptada del repositorio y comprobar Python3.13/Node26.5.0/npm11.17.0/PostgreSQL17/Tesseract con spa+eng. No usar bases dev/test/validation ni corpusblind.
2. Desde el repo ejecutar `python3.13 backend/scripts/licitia_local.py configure`, luego `install`, luego `init`. El root predeterminado es `~/Library/Application Support/LicitiaUAT`; todos los comandos aceptan `--config /ruta/absoluta/runtime.json` antes de la acción.
3. Ejecutar `start` y dejar esa Terminal abierta. Abrir http://localhost:5173.
4. En otra Terminal ejecutar `status`. READY o DEGRADED por proveedor opcional deshabilitado permiten probar Native; FAILED requiere corregir causa antes de continuar. /health solo no basta.
5. Ejecutar `selftest` para el PDF sintético; crea un expediente de prueba, no llama modelos. Verificar reapertura tras `stop` y `start`.
6. Stop seguro: Ctrl+C en launcher o acción `stop`. `restart` detiene y vuelve a iniciar los servicios privados; no controla Ollama. Nunca `killall`, dropdb o borrar data para recuperar una sesión.

| Problema | Acción segura |
|---|---|
| DB unavailable | Verificar `init`, herramientasPG17, espacio y puerto55432; no conectar otra DB por conveniencia. Inspeccionar postgres.log local. |
| Ollama unavailable | Si no hace faltaVision, continuar DEGRADED; si hace falta, administrador revisa servicio local manualmente. No descarga automática ni fallbackcloud. |
| Modelo ausente/digest distinto | Preparar explícitamente el modelo acordado antes de offline; no cambiar semántica o aumentar budgets. |
| Tesseract/lenguajes faltantes | Revisar PATH y `tesseract --list-langs`, instalar spa/eng por canal aprobado; repetir check. |
| Storage no escribible | Comprobar root absoluto/propietario/permisos y disco; no redirigir a carpeta de otro usuario o defaultde desarrollo. |
| Puerto ocupado | Identificar el dueño; no detenerlo desde el launcher. Resolver API8000 antes de iniciar; pg/web pueden configurarse en nueva instalación. |
| running.json existe | Puede haber instancia activa o apagado anormal. Verificar identidad de procesos; stop sólo señala al supervisor identificado. No borrar a ciegas. Stop puede reportar timeout mientras drena trabajo; no fuerza SIGKILL ni permite borrar estado. |
| Install incompleto | Conservar logs/config; una instalación existente no se sobreescribe. Operador inspecciona sólo venv/copiafrontend o utiliza otro root, sin tocar DB/data. |
| Migration falla | Conservar dump/errores, comprobar versiónPG/ruta/config; no usar create_all, SQLmanual o driftblind para reparar. |
| Service exited | Revisar services.log privado y status; no prometer recuperación automática de trabajo en vuelo. |

Acceder a runtime.json permite acceso al DB de esa instalación:0600 y no compartirlo. Logs/tickets no deben contener textos, imágenes o credenciales por defecto; compartir únicamente IDs/códigos y metadata saneada bajo autorización. `network.jsonl` no es una captura exhaustiva de paquetes.

Antes de datos reales: entregar [frontera UAT](uat-capability-statement.md), comprobar backup conjunto DB+root y completar gates pendientes de [readiness](release-candidate-limited-uat-readiness.md). RC-H1 demuestra instalación/arranque, no garantiza corrección de outputs ni completitud contractual.

## Recuperación RC-H3

- Antes de cambios importantes: detener launcher/escritores y ejecutar `backup` con
  `--backup-path` nuevo fuera del runtime y `--confirm-quiescent`; después `verify-backup`.
- Para restaurar: destino RC-H1 configurado/instalado y detenido, schema compatible;
  `restore --backup-path ... --confirm-quiescent --confirm-restore`. Conserva el par
  anterior hasta verificar Tender, Scope/Quantity, fuentes y revisiones en Workspace.
- Ante journal pendiente: `recovery-status` y `recover-restore --confirm-quiescent`.
  Nunca borres journal/PIDs/recibos para forzar un arranque o eludir límites.
- Ante procesamiento interrumpido/proveedor caído: consultar resultados conservados,
  **Verificar recuperación**, después **Reintentar de forma segura** si es elegible.
  No repara una fuente alterada ni cambia budgets; OCR/Vision se gestionan aparte.
- Backups y pares previos son confidenciales, locales y de retención manual. Protege
  copias y configuración privada por separado; no hay cloud ni cifrado incorporado.

[Comandos completos, formato, requisitos y troubleshooting](local-deployment.md#rc-h3--backup-restore-y-retry-local).
