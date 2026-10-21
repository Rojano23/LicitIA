# RC-H1 — instalación local reproducible para LIMITED UAT

Estado: implementación para revisión arquitectónica; RC-H1 no está comprometido ni existe tag RC. Baseline documental de cierre: `6a5cfdf1666ab8608db350efd31dc6c9aa90b46c`; motor aceptado: `14097f428e2185152aae1b671485244f1656fb07`.

Este procedimiento instala una instancia privada en el equipo del participante. No es un servicio LAN multiusuario ni un reemplazo del hardening de revisión/UI de RC-H2. No usar scripts blind, bases validation o Tender #002 para instalar/probar.

## Plataforma y requisitos

Primera plataforma reproducida: macOS 15.6.1 Apple Silicon arm64, CPython 3.13.15, PostgreSQL 17.10, Node 26.5.0 y npm 11.17.0. El launcher permite Python 3.13 y PostgreSQL 17; otros patches no están certificados por esta reproducción. Windows/Linux no validados; Camelot usa resource/POSIX. Instalar previamente estas herramientas por un canal autorizado; no se instalan silenciosamente.

- RAM: 8 GiB demostrados para la prueba determinista pequeña, sin inferencia. Recomendación inicial 16 GiB si se habilita Vision, no garantía de capacidad de todos los modelos/PDFs. Ajustar con observaciones UAT.
- Disco libre de planificación: al menos 5 GiB para herramientas/instancia pequeña; prever 10 GiB adicionales si se instala el modelo y crece el expediente. No son cuotas ni máximos garantizados. Dejar margen para backups y temporales.
- `python3.13`, `node`, `npm`, `initdb`, `pg_ctl`, `createdb`, `psql` en PATH. No Redis, Docker, workers distribuidos o Tauri requeridos para este recorrido.
- Tesseract 5.5.3 y paquetes `spa`/`eng` instalados. Verificar `tesseract --version` y `tesseract --list-langs`. Configurar `TESSDATA_PREFIX` si no se encuentra el directorio instalado; en el host probado es `/opt/homebrew/share/tessdata/`. Otra ruta se valida, no se adivina ni descarga.
- Ollama es opcional para recuperación visual: no hace falta para Native/Camelot. Si se habilita, runtime 0.23.3 y `qwen3-vl:4b-instruct`, digest `ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b` son la identidad de infraestructura de este ensayo, no una dependencia del dominio.

No se ofrece un instalador completo del SO. La reproducción nueva usa herramientas del host preinstaladas; revisar las limitaciones de evidencia al final.

## Decisión de herramientas y licencias

Se conserva pip/venv y npm en vez de migrar gestores. Prácticas revisadas: [pip repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/), [pip hash-checking/wheel-only](https://pip.pypa.io/en/stable/topics/secure-installs/), [PostgreSQL initdb](https://www.postgresql.org/docs/17/app-initdb.html), [Uvicorn](https://www.uvicorn.org/). Se usan mecanismos existentes y stdlib, sin nuevos frameworks ni servicios comerciales. El servidor estático stdlib se limita a la UAT controlada en loopback: no es una recomendación para exposición pública.

El lock incluye 49 distribuciones, con dependencias transitivas y pytest según la convención existente de requirements. `requirements-rc-macos-arm64.lock` congela wheels CPython 3.13/macOS arm64 con SHA-256. No es un lock universal. `requirements.txt` sigue siendo la declaración directa; `pyproject.toml` conserva su alcance mínimo y no debe usarse solo para reproducir el backend completo. PyMuPDF se alinea a 1.28.2, versión ya ejecutada en el motor aceptado; Camelot sigue 2.0.0/lattice/combined. No se cambia interpretación o parser.

Frontend usa package-lock.json canónico, engines y `.node-version`; `npm ci`, no `npm install` para reproducir. El instalador trabaja en una copia limpia del frontend dentro del runtime; no sirve el Vite de desarrollo. Mantener avisos/licencias de todos los binarios redistribuidos y revisar obligaciones existentes, incluyendo PyMuPDF/PDFium. Este cambio no agrega una nueva dependencia con licencia comercial obligatoria ni emite una garantía legal del bundle completo.

## Una sola ruta operacional

Desde la raíz de una copia del repositorio, en Terminal:

```sh
LICITIA_REPO="$PWD"
LICITIA_CONFIG="$HOME/Library/Application Support/LicitiaUAT/runtime.json"
python3.13 backend/scripts/licitia_local.py --config "$LICITIA_CONFIG" configure
python3.13 backend/scripts/licitia_local.py --config "$LICITIA_CONFIG" install
python3.13 backend/scripts/licitia_local.py --config "$LICITIA_CONFIG" init
python3.13 backend/scripts/licitia_local.py --config "$LICITIA_CONFIG" start
```

`start` permanece en primer plano. Abra **http://localhost:5173**. Desde otra Terminal, con las mismas variables/ruta al repositorio:

```sh
python3.13 "$LICITIA_REPO/backend/scripts/licitia_local.py" --config "$LICITIA_CONFIG" status
python3.13 "$LICITIA_REPO/backend/scripts/licitia_local.py" --config "$LICITIA_CONFIG" selftest
python3.13 "$LICITIA_REPO/backend/scripts/licitia_local.py" --config "$LICITIA_CONFIG" stop
python3.13 "$LICITIA_REPO/backend/scripts/licitia_local.py" --config "$LICITIA_CONFIG" start
```

También existe `restart`: solicita parada del supervisor identificado y queda al frente del nuevo arranque. Ctrl+C en `start` detiene frontend/API y luego PostgreSQL. No cierra ni modifica Ollama. El supervisor espera al cierre de los procesos, sin SIGKILL automático; si stop excede30s, puede seguir drenando trabajo y debe inspeccionarse antes de reintentar o borrar estado. No matar procesos ajenos para liberar puertos. El launcher comprueba identidad del supervisor antes de señalizar y usa un lock para impedir install/init/start simultáneos.

`configure` crea un secreto aleatorio, archivo0600 y directorios privados. Nunca imprime el secreto ni sobreescribe configuración existente; rechaza un directorio no vacío para no adoptar un clúster/data ajenos. Elegir una ruta absoluta para `--config`, con nombre runtime.json, fuera del repositorio; para otra instalación usar otro directorio y puertos libres. `--pg-port` y `--web-port` sólo se aplican al configurar; API8000 está fijada por la UI actual, y dos instancias por máquina requieren un slice posterior. No asumir que cambiar APIport funciona: el contrato lo rechaza.

`install` crea venv nuevo, instala wheels verificados por hash y ejecuta npm ci/build en una copia limpia. Se necesita Internet para adquirir assets ausentes inicialmente. No instala paquetes OS, no hace upgrade de pip ni repara una instalación existente. Si falla, conservar el log y la configuración; inspeccionar qué quedó a medias antes de eliminar exclusivamente un venv incompleto o elegir runtime nuevo. Nunca borrar data/postgres para intentar arreglar dependencias.

`init` crea exclusivamente el clúster privado con rol `licitia`, DB `licitia_uat`, contraseña generada y SCRAM. PostgreSQL sólo escucha 127.0.0.1:55432; sockets Unix deshabilitados. No usa el servidor de desarrollo5432, no hace dropdb, no resetea datos ni repara drift blind. Alembic upgrade head es la autoridad. `init` puede volver a aplicar migrations pendientes con servicios detenidos; no migrar una base ajena por editar una URL. La URL se deriva del root/config, no se acepta DSN arbitrario.

## Configuración y persistencia

El archivo privado runtime.json es la fuente canónica del launcher. `.env.example` y `backend/.env.example` son plantillas manuales sin secreto; no copiar sus placeholders como credenciales reales.

| Configuración | Valor/contrato |
|---|---|
| root | Absoluto, privado, fuera del repo; sin dependencia de rutas del desarrollador. |
| password | Generada al configurar; no incluir en Git, informes o tickets. |
| pg_port/api_port/web_port | 55432/8000/5173 por defecto, distintos y no privilegiados. |
| provider_enabled/kind | false/OLLAMA; implementación de readiness reemplazable mediante Protocol, no un modelo de dominio. |
| provider_url | HTTP loopback sin auth/query/path/redirect/proxy; externo rechazado. |
| model/digest/provider_version | Identidad de proveedor opcional; sólo metadatos, nunca inferencia durante readiness. |
| TESSDATA_PREFIX/PATH | Herramientas locales preinstaladas. No descarga automática. |

Antes de importar Settings en un proceso de la aplicación, el launcher fija DATABASE_URL, LICITIA_DATA_DIR absoluto, APP_ENV/HOST/PORT, FRONTEND_URL, LICITIA_LOCAL_AI_ENABLED y endpoint/modelo. Elimina variables LICITIA ambientales, incluido cualquier marcador blind. Ejecuta el backend desde el runtime privado, de modo que no cargue el .env del desarrollador. No altera prompts, budgets ni defaults numéricos de los motores.

Dentro del root: `runtime.json` (privado), `venv/`, `frontend/` con build, `postgres/`, `data/` con originales/artefactos, `running.json`, `operation.lock`, `services.log`, `postgres.log`, `network.jsonl` y `selftest.json`. Stop/start conserva DB/data. No trasladar sólo PDFs: para backup/restore coherente seguir el procedimiento conjunto DB+root de [readiness](release-candidate-limited-uat-readiness.md). RC-H1 prueba persistencia, no un backup/restore de RC-H3.

Los logs del piloto son locales0600. `network.jsonl` registra sólo host/puerto/allowed; no textos ni imágenes. `services.log` puede contener mensajes de parsers/errores de usuario: tratarlo como confidencial. Sin colector externo ni retención automática. Política inicial de diagnóstico del piloto: máximo10MiB por log y7días salvo incidente abierto; el operador comprueba/rota con servicios detenidos y suspende nuevas tareas si no puede mantener esos límites. No es un límite automático del logger. Para esta UAT, operador revisa tamaño y rota/retira diagnósticos al terminar sesión según política cliente, preservando errores aún necesarios; no borrar originales o manifests. No es observabilidad ilimitada de producción.

## Salud sin inferencia

`check` verifica storage, DB/migraciones, Tesseract, carga de librerías Camelot/PDFium/OpenCV/PyMuPDF y proveedor opcional. `status` añade API y frontend HTTP. Debe usarse `status`, no sólo /health: el endpoint legado no verifica dependencias. Ambos delegan al venv de esta instalación aunque se invoquen con el Python de bootstrap.

- READY: componentes comprobados disponibles.
- DEGRADED: proveedor opcional deshabilitado/ausente/version o modelo distinto; Native/Camelot siguen disponibles. Código de salida0 permite arrancar sin inferencia.
- FAILED: dependencia requerida o servicio esperado ausente, root inválido o migrations pendientes. Código1; no declarar la instancia lista.

El preflight carga los binarios de PDF/CV y lee metadata; no procesa documentos de clientes. `selftest` crea un PDF genérico y comprueba Camelot físico3×4, APIimport→Native→normalize→descarga/hash. Deja un Tender sintético identificable para comprobar reapertura. No ejecuta OCR ni Vision ni demuestra el wiring UI/Scope/Quantity de RC-H2.

## Proveedor local opcional

El contrato es `ProviderReadiness.probe(config)` y estados, no la API Ollama en los motores. La implementación actual consulta sólo /api/version y /api/tags con timeout3s y límite de metadata; no sigue redirects ni usa proxies. Faltas opcionales se reportan DEGRADED, sin instalar/iniciar servicios ni ejecutar inferencia.

Si el piloto requiere Vision, el administrador instala Ollama y descarga explícitamente el modelo en su Terminal antes de trabajar offline; esa adquisición inicial requiere Internet. Verificar digest y activar provider_enabled sólo con servicios detenidos y autorización del piloto. El launcher no ejecuta `ollama pull/serve`, no modifica el servicio existente y no llama /api/chat en readiness. Recambiar proveedor en el futuro requiere adaptar infraestructura/capacidades y preservar contratos; no hardcodear Qwen como autoridad contractual.

## Red local y prueba offline

| Listener | Bind predeterminado |
|---|---|
| API | 127.0.0.1:8000 |
| Frontend estático | 127.0.0.1:5173 |
| Clúster privado PG | 127.0.0.1:55432 |
| Ollama opcional | Debe configurarse local11434; lo administra el usuario, no este launcher. |

No hay auth multiusuario. No exponer a LAN ni mediante túnel; CORS no sustituye autorización. El compose heredado queda loopback y exige contraseña explícita; no es el camino canónico RC-H1 ni participa en la prueba.

El launcher añade un sitecustomize **sólo a sus procesos Python** que bloquea destinos distintos de loopback en resolución/conexiones/sends de sockets. Proxy/redirect del probe quedan deshabilitados. Esta barrera no es firewall delSO, sandbox para código nativo ni certificación de todas las librerías. No expone un modo cloud por configuración. Para documentos adversarios o políticas corporativas, completar controles de red/OS antes de ampliar el piloto.

Prueba realizada: instalación pip desde wheelhouse con hashes y npm ci --offline desde caché existente, runtime sin llamadas externas observadas, proveedor deshabilitado, dos workflows PDF genéricos, stop/start y hash original idéntico. Registro Python sólo 127.0.0.1 en puertos8000/5173; libpq/PostgreSQL nativo no está en ese registro, su DSN/listener es loopback. Hubo prueba negativa de egress denegado antes de conectar. No se deshabilitó físicamente toda la red del host ni se capturaron todos los paquetes. No hubo documentos de cliente o Tender002, ni inferencia real. No afirmar reproducción completa de OCR/modelos o instalación de SO.

### Preparar un bundle offline

En la plataforma exacta soportada y con acceso autorizado a Internet, descargar antes de trabajar con expedientes:

```sh
python3.13 -m pip download --require-hashes --only-binary=:all: -r backend/requirements-rc-macos-arm64.lock -d /ruta/wheelhouse
```

Instalar el runtime con `install --wheelhouse /ruta/wheelhouse --npm-offline`. npm también necesita su caché poblada previamente con el package-lock exacto. El flag no crea assets faltantes ni descarga modelos. Para distribución offline real, empaquetar explícitamente wheels/caché, Node/Python/PostgreSQL/tessdata y modelo opcional con notices; no se generó aquí un instalador universal.

## Recursos y límites observados

Host8GiBRAM. Venv nuevo404MiB, clúster inicial50MiB, frontend node_modules cercano100MiB, root/data de la prueba unosKiB. Modelo seleccionado3,295,636,231bytes de blobs (~3.30GB), sin inferencia medida; el directorio total de modelos del desarrollador no es requisito de instalación.

Idle observado: API~131MiBRSS, supervisor~17MiB, estático~15MiB y PGpostmaster~10MiB, sin sumar memoria compartida ni todos los hijosPG. Workflow sintético pequeño:1.26s wall,0.79suser/0.20ssystem, máximoRSS reportado216MiB para el comando medido; no es pico total del sistema ni capacidad garantizada bajo carga. Datos exactos en reports/rc_h1; ninguna optimización profunda.

Camelot mantiene CPU30s/deadline35s y límites de input/output aceptados, sin hardOSRAMcap. Primer piloto: operador, un documento a la vez, no archivos arbitrarios no confiables, revisar memoria/disco y evitar nuevas tareas si faltan recursos. Como límite operacional inicial propuesto, PDFs pequeños autorizados (p.ej.≤20MiB/≤100páginas), sin afirmar que exista ese límite global en API ni cambiar budgets OCR/Vision. Cargas amplias/modelos y otros tamaños requieren medición aparte.

## Troubleshooting

Ver [quickstart de administrador](uat-admin-quickstart.md). No resetear DB/data como solución genérica; no borrar running.json sin confirmar procesos; no ejecutar comandos blind. No cambiar motores para hacer pasar readiness. Preservar errores/datos y consultar soporte cuando una dependencia o migración falle.

## Evidencia y estado de entrega

Reproducción sustancial, no clean-machine completa: venv limpio + frontend limpio + clúster inicializado desde cero sobre host macOS con Python/Node/PostgreSQL/Tesseract/Ollama ya instalados. Los wheels se descargaron por red inicialmente; la instalación nueva usó wheelhouse y caché npm offline. No VM/freshOS, no installer Homebrew validado, no inferencia, no Windows/Linux, no UI end-to-end ni RC-H2.

Se mantienen intactas las rutas de extracción/semántica/IR/proof/planner/budgets/prompts y las migraciones existentes. Los cambios de Settings sólo afectan bind/URLdefault de despliegue; Alembic usa ruta portable. El informe RC-H1 contiene comandos/resultados de pruebas y matriz de éxito A–K. Completar RC-H1 no autoriza otro slice ni implica que ya se cumplieron todos losP0de primer usuario externo.
