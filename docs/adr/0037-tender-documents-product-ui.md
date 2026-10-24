# ADR-0037 — Pantallas Tender y Documentos sobre contratos existentes

Estado: **PROPUESTO — NO IMPLEMENTADO / pendiente de aprobación**. Fecha: 2026-10-23.
Baseline UI-R2/UI-R2.1 aceptado: `1d73dcd1738162ed5e0edbf2993a9415d247f170`.

## Contexto

ADR-0035 dejó navegación transitoria por anclas sobre App, manteniendo vistas visitadas
montadas. El workspace mezcla selección documental y lecturas de múltiples dominios.
Ocultar paneles no limita sus efectos. UI-R3 debe presentar lista/creación, Resumen y
Documentos sin reescribir Core ni usar un dashboard de agregados ajenos.

## Decisión propuesta

Reutilizar las rutas hash actuales. Resumen consume únicamente GET Tender y documentos;
lista filtra colección completa localmente. No agregar endpoints ni métricas readiness.
Documentos integra visor PDF local por UUID/revisión, texto derivado separado, importación
humana y bloque operacional AVAILABLE_ONLY con recovery/fingerprint existente.

Extraer únicamente presentación y ciclo de lecturas de esta superficie desde App y el
bloque operacional de WorkspaceFlow. Una única instancia controla polling por ejecución;
los otros módulos permanecen detrás del adapter legacy, con inputs/estado preservados.
No router/store/dependencias nuevas ni refactor transversal. Cancelación/generación identifica
Tender y documento; estado de drafts/filtros/selección se conserva en memoria por contexto.
No cambiar autoridades de persistencia o contratos de procesamiento.

No crear ruta específica de visor: selección interna y retorno a lista; los enlaces fuente
existentes a content#page siguen funcionando sin migrar ahora los módulos posteriores.
No reconstruir origen Discovery a partir de nombres ni consultar todas las Opportunities.
No visor Office, descarga genérica o sincronización geométrica simulados.

## Alternativas consideradas

- Sólo esconder secciones de App: insuficiente para reducir lecturas y aislar identidad.
- Rehacer todo Workspace o añadir store/router: amplitud innecesaria para el slice.
- Nuevo backend de resumen/availability: no requerido por la experiencia mínima.

## Consecuencias y condiciones

Habrá superficies frontend enfocadas y un puente legacy temporal. Sus límites deben quedar
cubiertos por pruebas de no remount/drafts/cero writes, ownership y fuentes históricas.
GET Workspace sigue siendo DTO completo; usarlo sólo para procesamiento/documentos cuando
se necesita, sin montar Comercial/Propuesta para representar su estado.

La revisión de código identifica correlación incorrecta del primer conflicto de lote con
el primer File seleccionado en App. Este ADR no autoriza repararla: se requiere decisión
explícita sobre corrección acotada o restricción segura antes del gate de importación.
No cambiar backend/versiones/OCR/Vision por solucionar composición visual.

Detalles, wireframes, riesgos y gates: [diseño UI-R3](../ui-r3-architecture-design.md).
Esta decisión sólo se adoptará tras aceptación humana; esta entrega no implementa código.
