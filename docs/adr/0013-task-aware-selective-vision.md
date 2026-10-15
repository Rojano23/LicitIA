# ADR 0013 — Vision selectivo por tarea con ejecución finita

Estado: propuesta implementada para revisión arquitectónica de MVP-06.V.4c2.

## Contexto

V.4c1 separa suficiencia y adquisición OCR. Vision cuenta con clientes, contratos y artefactos canónicos, pero la ruta histórica encadena estructura/detalle, hace probes al reutilizar y no conserva agotamiento entre requests.

## Decisión

Extender el planificador existente con VisionTaskRequest/VisionPlan. Cada tarea mantiene suficiencia y necesidad independientes. Una imagen, texto corto, baja confianza o fallo OCR no acreditan necesidad semántica visual. Se exige binding explícito a región IMAGE persistida y motivo visual tipado; el caller debe aportar esa necesidad. Los contratos soportados son STRUCTURE_SCOPE y DETAIL_TRANSCRIPTION; no interpretación general de diagramas.

Native/OCR suficiente evita invocación. Sin evidencia de déficit visual se conserva revisión. AVAILABLE_ONLY y ALLOW_OCR no adquieren Vision. AUTO habilita únicamente la tarea elegible mediante el servicio explícito execute_planned_vision; no cambia endpoints ni AUTO históricos y no se conecta automáticamente al runner ciego.

Usar OllamaVisionAssistClient existente, sin probes/pull, con endpoint loopback, timeout y tokens acotados. Deshabilitar retry JSON interno en esta ruta: cada llamada reservada equivale a una ejecución del cliente y como máximo un request de inferencia. Estructura y detalle no se encadenan.

El fingerprint independiente por tarea vincula original/documento/revisión/página/región, generaciones Native/OCR evaluadas, crop/render/hash, modelo/revisión local declarada, endpoint/configuración efectiva, prompt/schema y política. El digest de modelo lo aporta el caller desde un freeze autorizado; no se consulta el proveedor al planificar o reutilizar. La configuración exclusiva de detalle no invalida estructura.

Recibos derivados finitos por fingerprint registran intentos y estado con lock y reemplazo atómico. Se reserva RUNNING antes de llamar: una interrupción incierta agota fail-closed y nunca autoriza repetición automática. Un fallo observado permite el siguiente intento hasta el máximo congelado en el primer recibo (1–3); aumentar un presupuesto posterior no borra agotamiento. Cambio material de fingerprint puede adquirir una nueva generación.

Los éxitos crean DocumentVisionAnalysis/DocumentVisionPageResult nuevos bajo el fingerprint canónico. No sobrescriben resultados ni Native/OCR. Un éxito compatible verifica recibo, identidad y hash del payload antes de reutilizar sin probe ni render. Rollback DB que deje recibo huérfano se difiere, sin reparación automática. No hay nuevas tablas/enums/migraciones ni catálogo oculto en warnings.

Presupuesto runtime compartido limita llamadas, tareas y páginas; agotamiento queda explícito. Cada consumidor conserva provenance Vision y revisión; scope-logical-v2 reconcilia sólo grounding comparable. El parsing de filas explícitas reutiliza la gramática canónica sin convertir Vision en Native. Los formatos de cantidades de los adaptadores Vision existentes siguen siendo acotados.

## Consecuencias

La capa es opt-in. Los endpoints y orquestador históricos conservan sus límites previos: la nueva garantía de ejecución finita se aplica al servicio selectivo, no a llamadas directas legacy. No se certifica calidad visual real ni autoridad contractual. No se infieren continuidad entre páginas ni coordenadas de palabras; la región corresponde a crop real.

Retención: recibos son provenance/agotamiento de generaciones referenciadas, no un stream de logs. Conservarlos mientras existan artefactos o pueda reintentarse esa generación; no eliminarlos automáticamente para resetear presupuestos. La eliminación administrativa de derivados requiere un flujo explícito fuera de este slice.
