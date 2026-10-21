# MVP-06.V — cierre arquitectónico aceptado

Fecha de cierre: **2026-10-21**. Decisión recibida del arquitecto: **OPTION B — LIMITED UAT**.
Estado formal: **MVP-06.V CLOSED**. Siguiente fase: **RELEASE CANDIDATE / UAT HARDENING**.
No autoriza nuevos slices abiertos de Document Intelligence, otro intento ciego ni cambios de proveedores/semántica.

## Identidad y evidencia

- HEAD del motor aceptado: `14097f428e2185152aae1b671485244f1656fb07`.
- Attempt #9: `06v9_4bb38af849cf4b3683bcc9db455f8349`.
- First-pass SHA-256 verificado: `8972172fd0c9c14ff2e20ba4e13e9c438bfee13d3fc8c5182af723c11972c1b6`.
- Adjudicación aceptada: [reporte](../backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349/semantic_adjudication/semantic_adjudication.md), SHA `56627290f99d61ed14e82fde8b1ebc31a570cca7bb67d94dabe10140dc710273`.
- Su JSON tiene SHA `7eeaa016a787dd683a5cc8c26ba486c1bc89abcdabb6d77d7b08727abb9ed3c7`.

El prompt de cierre transcribe un SHA distinto: `8972172fd0c9c14ff2e20ba4e13e9c438bfee13d3fc8c518ba06713b735fe2`. No coincide con el archivo ni con los sellos previamente aceptados. Este documento conserva el hash realmente verificado; no se modifica, regenera ni recertifica el first-pass para hacer coincidir esa transcripción.

## Capacidad aceptada y límites

La ruta PDF → Camelot physical table → Native proof → StructuredEvidenceBlock → multispan provenance → Scope → Quantity → human review está demostrada en corpus real. B-1 p.1 produjo dos partidas distintas: 1 → 1 PZA/F60…, 2 → 2 PZA/L90…, con descripción, padres y manifests verificados. Camelot propone estructura; Native prueba evidencia. No implica recall global ni autonomía contractual.

- Attributes embebidos: 0 materializados; descripción completa conserva fabricante/modelo para revisión.
- Requirements: 15 sustentados, 8 con defectos, 8 contextuales/no autónomos; revisión obligatoria.
- Requested Evidence: 1 adecuado, 5 incompletos/mal tipados, 2 contextuales; no checklist contractual autoritativo.
- OCR/Vision: recuperación selectiva bounded; scans/layouts complejos pueden quedar incompletos. Proveedores/modelos son infraestructura reemplazable, no autoridad contractual.
- Todos los originales, versiones y decisiones deben permanecer trazables. La decisión humana mantiene autoridad.

Regresión congelada de referencia: CT/RT54, focalizada570, ampliada1153, completa2109 passed; un opt-in real excluido, compileall/diff check PASS. Estos resultados no sustituyen pruebas de instalación, uso real, aislamiento o recuperación.

## Alcance del cierre

Cierra la validación del motor dentro de LIMITED UAT; **no declara que la aplicación esté lista hoy para varios usuarios externos**. Las brechas operacionales, gates RC y alcance de hardening se detallan en [readiness](release-candidate-limited-uat-readiness.md). La frontera para usuarios está en [declaración de capacidades](uat-capability-statement.md).

Tender #002 ya fue expuesto en fases autorizadas: preservar historial, no reutilizarlo como nueva muestra ciega ni para tuning sin autorización. Attempts #1–#9 y sus artifacts permanecen inmutables. Esta aceptación se documenta aquí; no se reescribe la adjudicación histórica que entonces decía pendiente de aceptación humana.

El posicionamiento aceptado es asistencia documental auditable que acelera revisión y conserva evidencia para validación humana, sin prometer certificación completa de cumplimiento.
