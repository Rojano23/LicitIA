# ADR 0012 — Selective OCR por tarea con consumo trazable

Estado: propuesta implementada para revisión arquitectónica de MVP-06.V.4c1.

## Contexto

El OCR histórico decide por perfil de página y puede reemplazar resultados. Tener texto Native no demuestra suficiencia para cada consumidor; faltaban adaptadores OCR predeterminados para Scope y sus hijos.

## Decisión

Agregar un planificador puro por tarea y un ejecutor explícito, opt-in. La suficiencia usa evidencia y contratos de tarea, no longitud de texto. AVAILABLE_ONLY informa necesidad sin adquirir evidencia. AUTO histórico y los endpoints existentes no cambian. Los casos que requieren relaciones visuales quedan pendientes para V.4c2.

El ejecutor usa las interfaces OCR locales existentes, motor/version explícitos, render acotado y subprocess con timeout. No habilita proveedores ni descargas implícitas. La ejecución se limita a página/región planificada; una página mixta requiere región explícita para recuperar la imagen faltante.

Sin cambios de esquema: un recibo derivado por slot de página/motor/región vincula hash original, render, configuración, fingerprint y resultado. Un resultado compatible se reutiliza; un resultado incompatible, legado sin recibo o inconsistente se difiere sin sobrescribirlo. Una adquisición fallida persistida agota su único intento. El caller conserva control de la transacción; un rollback que deje recibo sin resultado se detecta y difiere, nunca se repara silenciosamente.

Normalizar sólo el nuevo resultado OCR preserva Native y sus chunks. Los adaptadores OCR usan contratos existentes y scope-logical-v2; conservan identidad OCR, generación, locator, spans y contribuyentes. No inventan confianza. El éxito OCR no concede confianza contractual: identidad, estructura y revisión siguen siendo obligatorias.

## Consecuencias

No se crea un sistema general de generaciones ni se permite regeneración incompatible automática. Los endpoints OCR históricos permanecen fuera de estas nuevas garantías. Los errores previos a adquisición no crean una generación ni un ledger de reintentos. La gramática determinista sólo recupera evidencia explícita; no certifica cobertura semántica completa. Vision, sus presupuestos y reintentos quedan fuera de este slice. Las pruebas con motores simulados verifican contratos y flujo, no calidad OCR real.
