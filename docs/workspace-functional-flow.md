# RC-H2 — Flujo funcional del Workspace provisional

Estado: implementación para revisión arquitectónica; Limited UAT controlada.
No es la interfaz definitiva ni una certificación de extracción completa.

1. Inicia el despliegue siguiendo [la guía local](local-deployment.md).
2. Selecciona o crea un Tender e importa sus documentos desde el Workspace existente.
3. En **Procesamiento del expediente**, pulsa **Procesar documentos disponibles**.
   La acción usa Native y evidencia existente. No solicita OCR/Vision automáticamente.
   Si hace falta percepción, utiliza los controles específicos existentes; después
   vuelve a procesar la evidencia disponible. No cambies budgets ni proveedores.
4. Consulta el estado. **Parcial** indica documentos no compatibles, texto insuficiente
   o fuentes no disponibles. **Falló** no significa que los originales fueron alterados:
   puede haber derivados parciales. Antes de reintentar, revisa el problema; una
   preparación inconsistente requiere soporte, no reparación manual de la base.
5. En **Alcance y cantidades**, cada partida contiene exclusivamente sus cantidades.
   Consulta descripción, valor/unidad, relación y estado de revisión. Si una asociación
   contradice la evidencia, se muestra **Sin resolver**; no se asigna a otra partida.
6. Abre **Fuente** para consultar documento, revisión, página, método, locator y extracto.
   **Abrir documento fuente** navega a la página cuando el visor PDF lo soporta;
   no hay resaltado geométrico nuevo. Una fuente ausente permanece visible como tal.
7. Usa **Abrir revisión de alcance** para confirmar, corregir o rechazar Scope y consultar
   historial. La API conserva control de concurrencia y vigencia. Después pulsa
   **Actualizar resultados** para reflejar la decisión en el resumen de cantidades.
8. Quantity es de solo lectura: confirmar Scope no confirma Quantity. Contrasta sus
   valores con originales. La revisión/corrección independiente auditada es P1 para
   RC-H3 y requiere contrato arquitectónico; no se guarda una falsa aceptación en notas.
9. Abre **Requisitos y evidencia solicitada**. Los registros conservan incertidumbre,
   revisión, vigencia y fuentes. Los controles completos de matriz/revisión de requisitos
   siguen disponibles en el Workspace existente. La evidencia solicitada requiere
   validación humana y no es una lista contractual certificada.

**Actualizar resultados** consulta estado sin procesar. Recargar el navegador conserva
el último estado operacional; una ejecución interrumpida se distingue de una completada.
Agregar documentos o cambiar generaciones invalida el estado anterior. Durante el
procesamiento evita otras operaciones de extracción sobre el mismo expediente.
No hay cola de background; cerrar/interrumpir un request puede dejar el estado interrumpido.

Contratos aditivos:

- GET `/tenders/{id}/workspace`: DTOs de Scope/Quantity, estado, matriz de requisitos,
  semántica/evidencia solicitada y advertencias de capacidad.
- POST `/tenders/{id}/workspace/process`: preparación canónica y materialización
  `AVAILABLE_ONLY`; responde con el mismo contrato. 409 sin documentos o si hay otra
  ejecución; 422 con código/run_id operativo al fallar. Un Tender inexistente devuelve 404.

Sin migración. [ADR-0020](adr/0020-workspace-canonical-composition.md) documenta composición,
retención acotada del último estado y límites de coordinación/recuperación.


RC-H3 agrega **Verificar recuperación** y **Reintentar de forma segura**. Antes de
retry se verifican fuente, generación, código/paquetes y recibos; un cambio entre
consulta y acción devuelve conflicto, sin borrar evidencia. Sólo un fallo Native
sin páginas previas puede recuperar su estado inicial automáticamente. Los datos
válidos siguen disponibles; percepción fallida requiere revisión y sus acciones
específicas, sin aumentar budgets. [Administración y backups](local-deployment.md#rc-h3--backup-restore-y-retry-local).
