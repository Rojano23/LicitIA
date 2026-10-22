# ADR 0019 — instancia local reproducible para UAT controlada

Estado: ACCEPTED RC-H1, commit `65b3465c35877408aafe15757d3e74aaddf10e36`. Fecha2026-10-21.

Se mantiene PostgreSQL+filesystem y el proveedor local opcional; no nuevo servicio distribuido, schema o dominio. La primera plataforma es macOS arm64/Python3.13/PostgreSQL17. Se conserva pip/venv con lock de wheels/hashes específico de plataforma y npmci con package-lock. Se revisaron prácticas oficiales pip/PostgreSQL/Uvicorn enlazadas en docs/local-deployment.md antes de implementar el wrapper mínimo.

Un launcher separado de FastAPI y de los harnesses blind genera configuración privada, clústerPG privadoSCRAM/loopback, inicia APIUvicorn y un servidor estático stdlib de build local, comprueba dependencias, y detiene exclusivamente procesos propios. No reutiliza defaults ni roots del desarrollador; no instala servicios/modelos silenciosamente. El servidor estático sólo se admite en este entorno loopback controlado, no hostingLAN/público.

Readiness neutral clasifica READY/DEGRADED/FAILED y distingue infraestructura requerida de proveedor opcional. La implementación Ollama consulta metadata sin inferencia y se puede sustituir detrás de Protocol sin cambiar semántica de negocio. Se aplica una restricción de sockets loopback a los procesosPython del launcher; no se presenta como sandboxOS ni protección universal de binarios nativos. Instancias compartidas requieren hardening de acceso posterior; no habilitadas aquí.

Consecuencias: instalación con prerequisitos explícitos y menos pasos internos; wheels no universales, herramientasOS a cargo del administrador, y sin reparación destructiva implícita. Settings/alembic resuelven bind/DSN/rutas de despliegue; no cambian extracción, budgets, prompts, migraciones ni authorityNative. PyMuPDF declarado se alinea al runtime ya validado1.28.2. Ollama/Qwen siguen siendo infraestructura del ensayo, no requisito contractual permanente. Backup/restore/operabilidadUI permanecen gates separados.
