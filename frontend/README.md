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
