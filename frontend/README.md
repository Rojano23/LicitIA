# Frontend de LicitIA — revisión humana de alcance

MVP-06.6.3 integra **Revisión de alcance** dentro del tender seleccionado, junto
al bloque **Partidas canónicas** de `src/App.tsx`. La pantalla abre mediante
**Abrir revisión de alcance** y carga datos sólo cuando se abre.

## Arquitectura y límites

Se conserva React + TypeScript estricto + Vite, npm y Axios. No se agregó router
ni un sistema de diseño. `ScopeReview.tsx` muestra cola y detalle con estilos
acotados a `.scope-review`. `src/api/scopeReview.ts` define los contratos tipados
y consume exclusivamente las tres rutas de Scope Review existentes.

Las etiquetas se traducen al español; el frontend no resuelve Source Effects,
no calcula aplicabilidad ni decide el estado efectivo. Las decisiones y la cola
se actualizan con la respuesta recalculada del backend. Los filtros conservan
el orden recibido y usan estados explícitos:

- Todos: todos los registros, incluidos históricos.
- Pendientes: `PENDING` o `STALE_REVIEW`.
- Revisados: `human_review_status=CURRENT`.
- Bloqueados: `reviewable=false`.

`NOT_REQUIRED` se muestra como **Sin revisión requerida**; `PENDING` como
**Requiere revisión**; `CONFIRMED`, `CORRECTED` y `REJECTED` como **Confirmado**,
**Corregido** y **Rechazado**; `STALE_REVIEW` como **Revisión anterior
desactualizada**; `SOURCE_BLOCKED` como **Fuente bloqueada**. Un registro sin
vista actual se presenta como **Registro histórico**, con su snapshot auditado.

La evidencia muestra descripción máquina, revisión solicitada originalmente,
diagnósticos en lenguaje humano, documento, versión, página, locator y fragmento.
El enlace abre el PDF local en su página. Los códigos técnicos están en un
apartado secundario desplegable. El historial conserva el orden recibido,
revisión, fecha local en español, decisión, nota, corrección, aplicabilidad y
snapshot revisado. Las decisiones históricas se distinguen mediante texto y
borde discontinuo, además del color.

Confirmar muestra qué descripción máquina será aceptada. Corregir permite sólo
una descripción no vacía y se prellena con la descripción efectiva del backend.
Rechazar requiere una segunda interacción explícita, permite cancelar y explica
que conserva evidencia e historial. Todas las decisiones aceptan nota opcional.

El POST envía exactamente `projection_fingerprint` y `current_review_revision`
del detalle mostrado como las dos expectativas del contrato. Un 409 muestra el
mensaje específico para target stale, revisión conflictiva o fuente bloqueada;
recarga cola/detalle y descarta el formulario anterior. No se reenvía ninguna
decisión automáticamente. Si falla la confirmación de un guardado por conexión,
se recarga para comprobar el historial antes de decidir de nuevo. Un bloqueo
oculta las acciones y conserva fuente e historial visibles.

Las acciones y selección se deshabilitan durante POST; una guarda síncrona
impide doble submit. Las respuestas tardías de selección y de otro tender no
pueden reemplazar el detalle actual. Cambiar tender remonta la pantalla.

## Dependencias y configuración de pruebas

Se agregaron exclusivamente estas `devDependencies`, con versiones exactas:

| Dependencia | Versión | Uso |
|---|---|---|
| `vitest` | 3.2.7 | Runner compatible con el Vite 5 existente |
| `@testing-library/react` | 16.3.3 | Renderizado de React para pruebas |
| `@testing-library/dom` | 10.4.1 | Peer requerido de Testing Library |
| `jsdom` | 26.1.0 | DOM de pruebas |
| `@testing-library/jest-dom` | 6.9.1 | Matchers DOM con integración Vitest |
| `@testing-library/user-event` | 14.6.1 | Interacciones de usuario |

No se cambiaron versiones existentes del lockfile: React/ReactDOM 18.3.1,
Vite 5.4.21, Axios 1.20.0 y TypeScript 5.9.3 permanecen intactos. No se introdujo
Jest, Cypress, Playwright ni otro runner. `jest-dom` sólo aporta matchers.

`vitest.config.ts` extiende la configuración Vite existente y configura jsdom,
`src/test/setup.ts`, limpieza/restauración de mocks. El setup registra matchers,
cleanup y usa el storage real de jsdom frente al global nativo de Node 26;
no modifica comportamiento productivo. Los fixtures son sintéticos y todas las
llamadas HTTP están mockeadas. Las pruebas no usan documentos reales, base de
datos ni modelos y no certifican resolución semántica o aspecto visual real.

Scripts añadidos:

- `test`: `vitest run`
- `test:watch`: `vitest`
- `typecheck`: `tsc --noEmit -p tsconfig.json && tsc --noEmit -p tsconfig.node.json`

Se conservaron `dev`, `build` y `preview`. No existe lint configurado.
La configuración separada de Vitest conserva la configuración de build.
`tsconfig.json` incluye además `vitest.config.ts` para verificar sus tipos sin
generar nuevos archivos de configuración compilados.
Documentación del runner: [configuración Vitest](https://v3.vitest.dev/config/).

## Validación automatizada

Desde `/Users/ceciliavalencia/LiticIA/frontend`:

```sh
npm test -- src/components/ScopeReview.test.tsx
npm test -- src/App.test.tsx
npm test
npm run typecheck
npm run build
```

La matriz UI01–UI20 está implementada en `ScopeReview.test.tsx`, con pruebas
adicionales de filtros, respuestas tardías, reintento del detalle, conflicto de
fuente bloqueada, fallo de POST, revisión stale, reapertura y cambio de tender.
`App.test.tsx` cubre integración y preservación del workspace existente. No
había tests frontend antes de este slice. Backend unchanged; su regresión no
se requiere para esta superficie.

## Aceptación humana local

La aceptación humana sigue pendiente después de pruebas automatizadas. El
expediente debe tener ScopeDetails persistidos y la base dev debe contar con
las migraciones vigentes. Esta pantalla no dispara extracción ni modelos.

Terminal 1 — backend local (no se ejecutó como parte de este slice):

```sh
cd /Users/ceciliavalencia/LiticIA/backend
DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev' LICITIA_LOCAL_AI_ENABLED=false /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```sh
cd /Users/ceciliavalencia/LiticIA/frontend
npm run dev -- --host 127.0.0.1
```

Abrir `http://localhost:5173` y verificar:

1. Seleccionar un tender y abrir **Revisión de alcance**, junto a Partidas canónicas.
2. Seleccionar un pendiente; inspeccionar descripción, motivo, fuente, versión,
   página, locator y fragmento; abrir el documento fuente.
3. Confirmar un elemento mediante **Confirmar → Guardar confirmación**.
4. Corregir otro mediante **Corregir → Descripción corregida → Guardar corrección**.
5. Rechazar otro mediante **Rechazar → Confirmar rechazo**; comprobar que
   **Cancelar** evita guardar.
6. Cerrar y reabrir la pantalla; verificar estado e historial de las tres decisiones.
7. Usar Todos/Pendientes/Revisados/Bloqueados. Si hay un elemento bloqueado,
   verificar que no aparecen acciones y que el motivo documental está visible.
8. Inspeccionar registros históricos/stale disponibles; comprobar que sus
   decisiones no se presentan como aplicables al registro nuevo.
9. Abrir el mismo detalle en dos pestañas antes de decidir. Guardar en una;
   guardar desde el formulario ya abierto en la otra. Debe mostrar conflicto de
   revisión, recargar y exigir una nueva interacción para decidir otra vez.
10. Una regeneración/cambio de fuente autorizado mientras el formulario está
    abierto permite verificar el conflicto de fingerprint. No generar efectos
    ni modificar documentos sólo para esta prueba; su UX ya tiene cobertura mock.

Si el expediente no contiene pendientes/bloqueados/históricos, esos escenarios
no quedan aceptados manualmente por el solo hecho de pasar pruebas sintéticas.
No ejecutar botones de extracción/Vision como requisito de esta revisión.

## MVP-06.6.4d — Alternativas técnicas y cumplimiento

La sección **Alternativas técnicas** abre junto a Revisión de alcance dentro del
Tender seleccionado. Sólo carga al abrirse. Lista a la izquierda y detalle a la
derecha; conserva el orden recibido y muestra también alternativas archivadas.
No agrega dependencias, scripts, router ni configuración de pruebas.

`TechnicalAlternatives.tsx` permite crear contenido humano, añadir revisiones con
contenido actual prellenado y archivar con confirmación explícita mediante un
POST de revisión. Cada escritura envía la revisión esperada del backend, conserva
historial y usa la respuesta del servidor. Una alternativa archivada puede
revisarse explícitamente de nuevo; el historial siempre permanece disponible.

`AlternativeCompliance.tsx` consulta snapshot contractual vigente, historial y
detalle de evaluaciones. Crear exige revisión/fingerprint de alternativa y
fingerprint Scope recibidos de API; no calcula hashes. Cada obligación congelada
separa visualmente **Lo que exige la licitación** de **Juicio técnico sobre esta
alternativa**, conservando documento, versión, página, locator, fragmento y
estado de revisión humana. Un enlace abre el PDF local.

El juicio empieza sin selección, exige justificación no vacía y permite referencia
opcional. Las cuatro decisiones sustantivas son humanas. Se envía la revisión de
`latest_decision` o null; no se obtiene de tamaño/orden del historial. La UI muestra
conteos, aggregate, applicability y revisión actual tal como llegan del backend;
no resuelve Scope, Source Effects, vigencia, precedencia ni cobertura técnica.

Historial de revisiones, evaluaciones y decisiones permanece visible, incluyendo
PARTIAL/NON_COMPLIANT anteriores. Una evaluación stale tiene aviso prominente,
resultado histórico identificado y formularios deshabilitados. Un contexto
contractual sin resolver se conserva y explica que el juicio técnico no resuelve
esa ambigüedad. No hay porcentajes, costos, precios, ranking ni ganador.

Los clientes `src/api/technicalAlternatives.ts` y `alternativeCompliance.ts`
separan ambos dominios y encapsulan Axios. Todos los 409 solicitados tienen
mensajes específicos. Conflictos y respuestas de POST perdidas recargan el
servidor, descartan formularios y nunca reenvían una escritura automáticamente.
La guarda síncrona bloquea doble submit y las acciones/selección se deshabilitan
mientras hay POST. Respuestas tardías de otro tender/alternativa/evaluación no
reemplazan la selección vigente. Los errores muestran mensajes recuperables sin
trazas SQL. Se conservan navegación por teclado y estados expresados con texto.

La comparación conjunta está diferida para priorizar el flujo por alternativa,
sin ampliar navegación ni carga de todas las evaluaciones. La lista muestra el
estado de la evaluación consultada cuando está disponible; no declara que sea un
ranking o la evaluación más reciente. Cambiar A/B consulta historiales separados.

Las matrices UIA01–UIA10 y UIC01–UIC25 usan Vitest/RTL existente con fixtures
sintéticos y HTTP mockeado. Incluyen protección adicional ante respuestas tardías,
conflictos, fallos parciales de lectura y respuestas de guardado perdidas. No
certifican apariencia visual ni sustituyen aceptación humana sobre el backend real.

Validación desde `frontend`:

```sh
npm test -- src/components/TechnicalAlternatives.test.tsx
npm test -- src/components/AlternativeCompliance.test.tsx
npm test -- src/components/ScopeReview.test.tsx
npm test -- src/App.test.tsx
npm test
npm run typecheck
npm run build
```

Backend permanece sin cambios; no requiere regresión backend para este slice.
No hay lint configurado. La base local utilizada manualmente debe tener head
`20261012_alt_compliance_071` y ScopeDetails persistidos. No se ejecutaron
migraciones ni fixtures en licitia_dev. Los comandos de backend/frontend de la
sección anterior sirven también para este flujo, con IA local deshabilitada.

Aceptación humana pendiente — abrir `http://localhost:5173`:

1. Seleccionar un Tender y abrir **Alternativas técnicas**.
2. Crear Alternativa A con nombre, descripción técnica, supuestos y notas.
3. Crear Alternativa B; comprobar que ambas permanecen visibles.
4. Seleccionar A, crear una nueva revisión y modificar explícitamente el contenido.
5. Abrir el historial y verificar contenido de ambas revisiones.
6. Crear una evaluación; inspeccionar alcance congelado, fuente y revisión evaluada.
7. En obligaciones distintas, elegir Cumple, Cumplimiento parcial, No cumple y
   Requiere revisión; escribir justificación y guardar. Si no hay suficientes
   obligaciones, verificar distintas decisiones sucesivas conservando historial.
8. Revisar aggregate y conteos recibidos del servidor; sin porcentajes ni ranking.
9. Abrir historial técnico y verificar decisiones, revisiones, fechas y referencias.
10. Modificar A mediante otra revisión; comprobar evaluación anterior desactualizada
    con juicios deshabilitados y resultado histórico identificado.
11. Crear una evaluación nueva; verificar que la anterior sigue consultable y que
    sus decisiones no se copian al snapshot nuevo.
12. Archivar A mediante Archivar alternativa → Confirmar archivo; comprobar
    alternativa, revisiones y evaluaciones conservadas.
13. Verificar que A archivada no ofrece crear una evaluación nueva.
14. Cambiar entre A/B; verificar historiales independientes. En dos pestañas, probar
    revisión/juicio concurrentes y comprobar recarga sin reenvío automático.

No iniciar extracción/Vision/modelos como requisito de aceptación. Los casos
stale Scope o fuente bloqueada requieren datos existentes o cambios contractuales
humanamente autorizados; los mocks no constituyen aceptación real de esos casos.
