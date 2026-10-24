# ADR-0040 — UI-R6: superficies globales de apoyo

Estado: propuesto e implementado para revisión UI-R6. Fecha:2026-10-24.

## Inventario previo a implementación

| Capacidad | Clasificación | Contrato/decisión |
|---|---|---|
| Datos empresariales/documentos/revisiones/metadatos | AVAILABLE | /companies, /documents; sin nuevo storage |
| Evidencia, fuente y revisión humana | AVAILABLE | endpoints empresariales existentes |
| Vigencia registrada | DERIVABLE SAFELY | expiration_date literal frente a fecha local; no validez legal ni umbral próximo a vencer |
| Personas/experiencia/certificaciones como módulos separados | NOT AVAILABLE | conceptos de dominio, sin CRUD contratado; evidencia tipada existente solamente |
| Uso global por licitación de evidencia empresarial | NOT AVAILABLE | no fanout por Tender; consultar Cumplimiento por empresa/Tender |
| Registro de licitaciones | AVAILABLE | GET /tenders, filtros locales sobre respuesta completa |
| Comercial XLSX/CSV, preparación, propuesta y archivos | AVAILABLE | acceso al flujo canónico por Tender, sin motor/export nuevo |
| Seguimiento Discovery | AVAILABLE | rutas/vistas UI-R2 existentes |
| Analytics financieros globales y reportes consolidados de requisitos | DEFERRED | sin proyección transversal, no nuevos KPIs ni fanout |
| Fuentes enabled/áreas | AVAILABLE | Discovery source settings; Compras MX restringido |
| Perfiles de búsqueda | AVAILABLE | editor de Discovery existente, enlace, sin segundo editor |
| Sidebar local | AVAILABLE | preferencia UI-R5, sin modificar shell |
| Paths/credenciales/modelos/provider configurables desde producto | NOT AVAILABLE | no formularios de entorno ni setter nuevo |
| Respuesta API, inventario OCR/visión, metadata fuentes | AVAILABLE | health/providers/sources locales, refresco explícito |
| Salud DB/schema/runtime/backend version desde API | NOT AVAILABLE | /health sólo devuelve status ok; no se presenta como chequeo DB |
| Resumen para soporte | DERIVABLE SAFELY | allowlist de estados/cifras públicas; nunca payload libre, documentos, nombres de empresa/Tender, rutas, secretos o precios |

## Composición

CompanyView reemplaza la superficie global, conservando contratos existentes; lecturas por
empresa y documento con ownership y generaciones. Importar por File/identidad local estable
para evitar correlación por orden/nombre en conflictos múltiples. Guardado/archivado/análisis
son explícitos. Originales inmutables, revisiones y evidencia conservados por el servidor.
El componente heredado se conserva sin cambios para App no embebido; Product UI usa
sólo CompanyView. Ambos consumen el mismo modelo de storage. No cambios de interpretación/evaluación automática.

ReportsView presenta catálogo acotado y registro de Tenders; enlaces al módulo canónico
para archivos, sin generación ni modificación por montar la pantalla. SettingsView limita
edición a enabled/áreas ya contratados y enlaza perfiles existentes. No consulta portales.

DiagnosticsView separa grupos disponibles y omisiones explícitas. Copia sólo una proyección
segura; los detalles técnicos también usan allowlist. Promise.allSettled a cuatro GETs,
sin polling; useRead invalida respuestas antiguas. Herramientas heredadas del expediente se
montan sólo al abrirlas explícitamente; se conservan sus controles, no se reescribe App.

Sin backend/migración/dependencias. Sidebar UI-R5 intacto. Fixtures únicamente en tests y
harness local; no documentos reales ni Tender #002. UI-R6 sin stage/commit/push.
