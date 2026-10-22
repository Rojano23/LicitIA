# RC-H1 — reporte final para revisión arquitectónica

## Parte A: commit de cierre

Commit y HEAD: `6a5cfdf1666ab8608db350efd31dc6c9aa90b46c`.
Asunto: `docs: close mvp-06v and define limited uat readiness`.

Contiene exclusivamente los seis documentos canónicos aceptados. No incluye reportes, benchmarks, entornos generados o implementación. No hubo push. Este HEAD es la base formal de RC / UAT HARDENING; Part B permanece sin stage ni commit.

## Parte B: resultado

**RC-H1 COMPLETE — READY FOR ARCHITECT REVIEW**, con las limitaciones de reproducción que se detallan aquí. No se creó RC/tag. Esto no declara lista toda la aplicación para el primer participante: RC-H2, recuperación y disclosure siguen pendientes.

### Plataforma e inventario

Plataforma reproducida: macOS 15.6.1 arm64, CPython 3.13.15, PostgreSQL 17.10, Node 26.5.0 y npm 11.17.0. No Windows/Linux validados. Se documenta 8 GiB para el caso determinista pequeño; 16 GiB como recomendación inicial con Vision, sin garantía de rendimiento de modelos. Prever 5 GiB libres para instalación pequeña y margen adicional para modelo, expedientes y backups; no son cuotas automáticas.

Se conservan FastAPI 0.115.0, Uvicorn 0.30.6, SQLAlchemy 2.0.34, Alembic 1.19.1, psycopg 3.3.4 y Pydantic 2.11.7. Camelot sigue 2.0.0 / lattice / combined, PDFium y OpenCV. La declaración PyMuPDF se alinea a **1.28.2, ya instalada y validada antes del slice**: no se cambió el motor efectivo para obtener resultados nuevos. Tesseract 5.5.3 / spa+eng es prerrequisito local; Paddle no se añadió al lock RC. Ollama es opcional. No Redis, Docker obligatorio ni workers distribuidos.

### Locks y prácticas revisadas

Backend: pip/venv existentes, lock de 49 distribuciones transitivas y wheels CPython 3.13/macOS arm64 con SHA-256. Instalación `--require-hashes --only-binary=:all:`. `requirements.txt` declara dependencias directas; el lock es el contrato RC. `pyproject.toml` conserva el alcance mínimo previo y no instala todo por sí solo.

Frontend: package-lock canónico, `npm ci`, Node/npm explícitos. El cambio del lock agrega engines sin actualizar dependencias resueltas. Build en copia limpia dentro del runtime, sin servir Vite de desarrollo.

Se revisaron prácticas oficiales de pip, PostgreSQL y Uvicorn, enlazadas en docs/local-deployment.md. Se usan stdlib y herramientas existentes, sin gestores o servicios nuevos. El servidor estático stdlib sólo corresponde a esta UAT en loopback, no a hosting público. La revisión del bundle redistribuido y sus notices incluye obligaciones existentes de PyMuPDF/PDFium; no se emite garantía legal ni se introduce una nueva dependencia comercial obligatoria.

### Configuración y lifecycle

El launcher ofrece `configure/install/init/start/check/status/stop/restart/selftest`. Genera secreto aleatorio0600 y runtime privado fuera del repo. Rechaza root relativo, configuración sobreescrita, directorio no vacío, endpoint externo o puertos incompatibles. No adopta un clúster ajeno ni acepta DSN arbitrario.

Fija entorno antes de Settings/application y ejecuta desde el runtime privado: no carga el .env del desarrollador ni hereda un marcador blind. Los templates no contienen secretos reales. Los defaults de red y compose pasan a loopback; compose exige contraseña explícita y no es la ruta canónica de RC-H1.

| Servicio | Bind local |
|---|---|
| API | 127.0.0.1:8000 |
| Frontend estático | 127.0.0.1:5173 |
| PostgreSQL privado | 127.0.0.1:55432 |
| Ollama opcional | Endpoint loopback 11434, administrado por el usuario |

La UI actual fija API8000; el contrato rechaza remapping silencioso. Es una instancia por host confiable, sin auth multiusuario ni exposición LAN. Los procesos tienen lock y el stop comprueba identidad del supervisor. El supervisor drena procesos sin SIGKILL automático y detiene sólo su PostgreSQL; no controla Ollama. No hay reparación destructiva de instalaciones incompletas.

`init` crea clúster privado SCRAM, rol licitia y DB licitia_uat; migra desde cero hasta072. No drop/reset de bases existentes, create_all, migración nueva o reparación del drift blind. Alembic.ini usa %(here)s para resolver rutas. Stop/start conserva DB y data; el procedimiento de backup/restore sigue siendo un gate separado.

### Readiness y proveedor

`status` comprueba backend/frontend HTTP, DB/migraciones, storage, Tesseract y dependencias Camelot, más el proveedor opcional. `check` cubre dependencias antes de iniciar API. Required missing → FAILED; proveedor opcional ausente/deshabilitado → DEGRADED sin ocultar fallos esenciales. /health legado no sustituye status.

ProviderReadiness es un Protocol de despliegue; su implementación Ollama sólo consulta metadatos, sin redirects/proxies ni inferencia. La comprobación real de metadatos pasó con Ollama0.23.3, qwen3-vl:4b-instruct y digest esperado. La instancia permanece con inferencia deshabilitada por defecto. No se instalaron modelos ni se cambió el servicio. Los clientes legacy concretos no se rediseñaron: no se afirma una abstracción universal terminada, sólo que no se convirtió proveedor/modelo en dependencia del dominio.

### Instalación nueva y offline

Se creó un **venv nuevo**, una **copia limpia de frontend** y un **clúster PostgreSQL nuevo**. Wheels descargados inicialmente por Internet; la instalación nueva usó wheelhouse con hashes y npm ci --offline desde caché existente. Build y pip check pasaron. Migraciones desde cero, arranque, salud, apagado, reinicio y reapertura del original sintético con hash idéntico pasaron.

No fue VM, SO nuevo o fresh user: Python, Node, PostgreSQL, Tesseract, Ollama y caché npm ya existían en el host. No se reprodujo la adquisición del modelo ni tessdata, ni se validó Windows/Linux. No inferencia, corpus ciego o UI end-to-end. Esta es reproducción sustancial en componentes aislados, no certificación universal clean-machine.

Dos workflows de PDF genérico comprobaron Camelot físico3×4, API import→Native→normalize→content/hash. Ningún OCR/Vision real o procesamiento Tender002. La barrera de sockets Python del launcher bloqueó la prueba negativa externa antes de conectar; el workflow registró sólo loopback8000/5173. Sin transmisiones externas observadas. No firewallOS/packet capture: libpq y binarios nativos no están instrumentados; PostgreSQL usa DSN/listener loopback. La limitación está documentada y no se presenta como air-gap corporativo.

### Recursos y riesgos

Host8GiB. Venv404MiB, clúster inicial50MiB, frontend dependencies~100MiB; data sintética unosKiB. Modelo seleccionado:3,295,636,231 bytes de blobs; RAM de inferencia no medida. Idle aproximado: API131MiB RSS, supervisor17MiB, estático15MiB, postmaster10MiB; no sumar memoria compartida ni inferir pico total. Selftest:1.26s wall,0.79user/0.20system y maxRSS226,607,104 bytes (~216MiB) del comando medido.

Camelot sigue sin hard RAM cap. Primer piloto con operador, un PDF a la vez y control de tamaño/memoria/disco; no se cambian budgets OCR/Vision. Diagnóstico local con política manual7días/10MiB por log, salvo incidentes abiertos; no retención automatizada ni colector externo. Directorio no vacío rechazado; no reparación implícita o borrado de data. Precondiciones OS manuales, auth LAN, cargas hostiles, memoria de modelos y restore completo siguen fuera de esta prueba.

### Documentación y próxima fase

Instalación canónica: docs/local-deployment.md. Administrador: docs/uat-admin-quickstart.md. Decisión: ADR0019, implementado y pendiente de revisión. README/roadmap enlazan RC-H1; no se autoriza RC-H2 automáticamente.

**RC-H2 recomendado:** recorrido normal UI/API → servicios canónicos ya aceptados → Scope/Quantity con padre/fuente → review → reopen, con progreso y errores legibles. No usar harnesses blind/reset ni ampliar semántica, modelos o budgets. Backup/recovery y disclosure continúan como gates antes de participantes externos.


## Archivos exactos y validación

Documentación comprometida:

- `README.md`
- `docs/architecture.md`
- `docs/mvp-06v-closure.md`
- `docs/release-candidate-limited-uat-readiness.md`
- `docs/roadmap.md`
- `docs/uat-capability-statement.md`

RC-H1 modificados (sin stage):

- `.env.example`
- `README.md`
- `backend/.env.example`
- `backend/alembic.ini`
- `backend/app/config.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `docker-compose.yml`
- `docs/roadmap.md`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/vite.config.ts`

RC-H1 nuevos (sin stage):

- `backend/app/local_deployment.py`
- `backend/requirements-rc-macos-arm64.lock`
- `backend/runtime_guard/sitecustomize.py`
- `backend/scripts/licitia_local.py`
- `backend/tests/test_local_deployment.py`
- `docs/adr/0019-local-uat-deployment.md`
- `docs/local-deployment.md`
- `docs/uat-admin-quickstart.md`
- `frontend/.node-version`

Resultados finales:

- new: 27 passed, 8 warnings in 1.95s
- core: 205 passed, 1 skipped, 10 warnings in 14.99s
- di: 1153 passed, 1 deselected, 8 warnings in 118.43s (0:01:58)
- full: 2136 passed, 1 deselected, 11 warnings in 205.25s (0:03:25)
- frontend: 78 passed (4 test files)
- frontend_build: PASS, clean copied frontend after npm ci --offline
- compileall: PASS app/scripts/tests + runtime_guard
- diff_check: PASS

Gates A–K: PASS dentro de la plataforma y límites documentados. Nuevas pruebas:27, incluidos parsing/ambiente, storage, clasificación de salud, provider metadata, dependencias ausentes, egress y protección de configuración/clúster ajeno. La primera full tuvo2135pass; se repitió al añadir el caso final de seguridad. Core1skipped es opt-in Ollama real. Una invocación focused sin permiso de DB falló en setup y fue repetida con acceso autorizado; no fue fallo funcional. Los logs/JUnit conservan resultados y warnings exactos.

Sin schema/migration nueva ni cambios en Scope, Quantity, Requirements/Evidence, planner, prompts, config Camelot o budgets. Las únicas superficies existentes de aplicación modificadas son configuración de bind/DSN y rutas/declaraciones de despliegue.

Históricos: 4560 archivos y 1381 artifacts relacionados con Attempt9 verificados intactos. Servicios privados detenidos; datos sintéticos conservados. Se comprobó que el secreto privado no aparece en candidatos de commit ni reportes. Staging vacío, sin push/tag. RC-H1 listo para revisión y commit posterior si el arquitecto acepta la evidencia y límites.

LICITIA RC-H1 REPRODUCIBLE LOCAL DEPLOYMENT COMPLETE — READY FOR ARCHITECT REVIEW
