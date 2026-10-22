from pathlib import Path
import json,hashlib,subprocess,collections,shutil
R=Path('/Users/ceciliavalencia/LiticIA');P=R/'backend/reports/blind_selective_runs/06v9_4bb38af849cf4b3683bcc9db455f8349';A=P/'semantic_adjudication'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
items=read(A/'individual_scope_quantity_adjudication.json');ledger=read(A/'comparison_ledger.json');integrity=read(A/'integrity_verification.json');safety=read(A/'structural_safety_review.json')
assert len(items)==2 and all(e['exact_semantic_source_match'] for xs in ledger.values() for e in xs)
capabilities=[
('Document ingestion/integrity','PASS','11/11 originales con hashes/locators; .DS_Store unsupported explícito; ningún original modificado.'),
('Native extraction','CONDITIONAL','251/253 páginas con Native disponible; scans y layouts complejos siguen dependiendo de adquisición/revisión. No certifica recall de todo el expediente.'),
('Physical table structure','CONDITIONAL','PASS en tabla digital B1p1: 1tabla3×4,2filas de bienes. No evaluación exhaustiva de todas las propuestas ni garantía de tablas rotadas/merged/scanned.'),
('Canonical provenance','PASS','2manifests con hashes correctos;37palabras Native únicas,24spans literales y generaciones verificadas; replay puro idéntico.'),
('StructuredEvidenceBlock','CONDITIONAL','2bloques sustentados y positivos; norma/repeated headers no producen Scope. Prosa y referencias cross-page no cubiertas.'),
('Scope extraction','CONDITIONAL','2/2 partidas de referencia B1p1 correctas, descripción/owner distintos, review. No cobertura completa de condiciones de embalaje/entrega/documentación en B1pp2–4.'),
('Quantity extraction','CONDITIONAL','1PZA y2PZA con padre correcto; no prometer extracción de2juegos de cables/puerto ni2juegos de contrato.'),
('Attribute extraction','CONDITIONAL','0campos; descripción completa conserva GE MULTILIN y modelos. No automatizar comparación de Attributes ausentes.'),
('Requirements','CONDITIONAL','31idénticos a#7 en contenido/fuente:15supported,8con defectos,8contextuales. Asistencia sujeta a contraste con originales; no checklist completo.'),
('Requested Evidence','CONDITIONAL','8idénticos a#7:1adecuado,5incompletos/mal tipados,2contextuales; sólo borrador para revisión dirigida.'),
('Human review / abstention','PASS','Scope/Quantity/requisitos/evidencias conservan review;253estructurasreview y continuidadUNKNOWN; UI Scope muestra descripción íntegra y abre página fuente. Sin ensayo nuevo de usabilidad de navegador.'),
('Perception selectivity','CONDITIONAL','996decisionesNative suficiente no disparan OCR por interpretación pendiente;4OCR/4Vision bounded. Necesidad humana espacial de todos los planes no certificada.'),
('Local/offline operation','CONDITIONAL','Ejecución local y proveedores localhost, sin cloud. No certificación air-gap/instalador ni portabilidadWindows; ambiente validado macOS/backend actual.')]
boundary={
 'decision':'OPTION B — LIMITED UAT','audience':'Grupo acotado de usuarios informados y acompañados, sobre documentos autorizados en entorno local controlado.',
 'may_test':['Importar y revisar originales/versiones y procesamiento unsupported.','Revisar Scope de tablas digitales elegibles con navegación a fuente; confirmar/corregir cada partida y cantidad.','Usar Requirements como propuestas revisables, contrastadas contra originales y checklist humano.','Evaluar Requested Evidence como borrador incompleto de documentos/paquetes, nunca como inventario exhaustivo.','Probar provenance, revisión humana y surfacing de conflictos sin asumir que toda discrepancia es contractual.'],
 'must_not_rely_on':['Completitud autónoma del expediente, obligaciones, plazos o entregables.','Scope tabular como sustituto de lectura de prosa/anexos/referencias cruzadas.','Marca/modelo embebidos como Attributes materializados o matching automático certificado.','Requested Evidence como lista definitiva de presentación/cumplimiento.','Anchors Vision/OCR como transcripción literal validada o owner confiable; scans deben contrastarse visualmente.','Conflictos como decisiones contractuales resueltas ni propuestas automáticas como aceptación humana.'],
 'mandatory_user_disclosure':['Extracción asistida e incompleta; ausencia de registro no significa ausencia de obligación.','Todo hallazgo extraído debe contrastarse con su fuente antes de uso contractual.','Las cantidades tabulares validadas son por partida; no sumarlas ni extenderlas a accesorios/contratos por analogía.','OCR/Vision pueden fallar o alterar identificadores; verifique códigos y cantidades en el original.'],
 'entry_conditions':['Entregar esta declaración y explicación de limitaciones a participantes.','Mantener fuente completa accesible y revisión humana como condición del uso contractual.','Entorno local controlado con dependencias y límites del perfil documentados.','Aprobación arquitectónica/humana de esta decisión propuesta; este informe no persiste aceptación de dominio ni publica el producto.']}
metrics=[
 dict(name='Aceptación sin corrección',definition='Hallazgos aceptados sin cambio / hallazgos revisados, separado por Scope,Quantity,Requirement,Evidence.'),
 dict(name='Aceptación con corrección menor',definition='Hallazgos útiles después de corrección menor / revisados; definir previamente menor frente a material.'),
 dict(name='Falsos positivos',definition='Hallazgos descartados por falta de soporte/aplicabilidad / revisados; separar encabezados, paquetes, owners.'),
 dict(name='Omisiones materiales',definition='Casos esenciales del inventario humano independiente que no tienen hallazgo útil / casos materiales de ese inventario. Documentar solapes, sin extrapolar este corpus.'),
 dict(name='Exactitud de Quantity',definition='Valor+unidad+Scope parent correctos / cantidades revisadas; informar cada error material y correcciones.'),
 dict(name='Utilidad Requirements',definition='Propuestas que ayudan a identificar una obligación aplicable / revisadas, con contextualización y tiempo de corrección.'),
 dict(name='Utilidad Requested Evidence',definition='Registros útiles para identificar documento/paquete/condición / revisados; medir tipos y omisiones por separado.'),
 dict(name='Ahorro de tiempo',definition='Tiempo de revisión manual comparable menos tiempo asistido incluyendo validación/corrección; diseño pareado o contrabalanceado, mismo alcance.'),
 dict(name='Carga de revisión',definition='Minutos por expediente y por hallazgo, registros revisados, rechazos/correcciones y pendientes.'),
 dict(name='Utilidad de provenance',definition='Porcentaje de intentos que llegan a la página/fragmento correcto; tiempo de verificación y valor reportado por usuario.'),
 dict(name='Confianza calibrada',definition='Valoración del usuario antes/después de verificar evidencia, junto con errores aceptados y dependencia indebida de automatización.')]
backlog={
 'P0 — antes de uso externo más amplio':['Hacer obligatoria la comunicación de límites y revisión; validar UX completa para Requirements/Evidence/Quantity y rechazo/override, no sólo contratos backend.','Resolver o delimitar de forma visible contextualización de Requirements y tipado/incompletitud Evidence antes de anunciarlos como checklist contractual.','No exponer anchors Vision erróneos como identificadores fiables; comprobar visibilidad uniforme de estados de revisión.','Hardening de recurso/RAM y operación con PDFs no confiables antes de ampliar volumen/usuarios; el spike sólo limita CPU/tiempo/input/output.','Verificar paquete de instalación/despliegue, avisos/licencias de todas las dependencias existentes, persistencia/backup/acceso y operación offline antes de distribución. Son gates pendientes, no defectos nuevos demostrados por este intento.'],
 'P1 — mejoras posteriores a UAT':['Attributes embebidos con grounding y ownership, sin reglas GE/F60/L90.','Contextualización de Requirements y completitud/typing de Requested Evidence guiadas por hallazgos UAT.','Prosa técnica/cross-page/globales y cantidades subordinadas sin fabricar nuevas partidas.','Fallback de tablas escaneadas con prueba literal/espacial; aislar fallos bounded sin depender de un modelo concreto.','Hardening de abstracción de proveedor y pruebas de capacidades, respetando local-first.','Observabilidad mínima de evaluaciones/rechazos para futuros gates, con política de retención.'],
 'P2 — enhancements':['Más layouts/rotación/crop/merged cuando UAT demuestre necesidad.','Mejoras de navegación a spans/celdas y presentación de provenance multispan.','Métricas de usabilidad/tiempo por tarea y simplificación de distribución en plataformas adicionales.']}
result=dict(schema_version='DI_ATTEMPT9_FINAL_RELEASE_GATE_ADJUDICATION_001',run_id='06v9_4bb38af849cf4b3683bcc9db455f8349',head='14097f428e2185152aae1b671485244f1656fb07',first_pass_sha256=integrity['first_pass_sha256'],authority='Evaluación de Codex solicitada por el usuario; decisión arquitectónica/humana final pendiente. Referencia B1 aceptada por usuario; juicios anteriores reutilizados sólo después de igualdad exacta de contenido/fuente.',approved_by_human=False,integrity='PASS',core_table_path='PASS_ON_VALIDATED_B1_TABLE',scope_adjudication=items,quantity_adjudication=[dict(item=x['item'],quantity_id=x['quantity_id'],scope_parent=x['parent_id'],value=x['quantity'],unit=x['unit'],verdict='PASS') for x in items],attribute_limitation=dict(classification='ACCEPTABLE MVP LIMITATION',followup='POST-UAT IMPROVEMENT',reason='No fields brand/model en los bloques; texto completo sí visible en descripción y fuente. Adapter reconoce fields tipados, no labels embebidos en descripción.'),manifest_adjudication='PASS_BOTH',false_positives=dict(materialized_scope=0,materialized_quantity=0,review_scope='Todos los2bloques/2Scope/2Quantity del corpus inspeccionados; sólo B1p1, no normas/índice/cuestionario/formulario/header.',physical_detector_false_tables='NOT_DIRECTLY_MEASURABLE; no log de propuestas descartadas',global_recall='NOT_MEASURED'),requirements=dict(exact_unchanged=31,supported=15,supported_with_defects=8,contextual=8,classification='CONDITIONAL — assisted limited UAT only'),requested_evidence=dict(exact_unchanged=8,adequate=1,incomplete_mistyped=5,contextual=2,classification='LIMITED UAT; not adequate for autonomous checklist'),structural_safety=dict(trusted=0,review=253,historical_false_trusted_cases='Both REVIEW_REQUIRED / UNKNOWN / outgoing_item_key=null',raw_vision_issues=['AnexoC L90-U03-LLH differs from independently viewed HLH.','Bases110 model heading proposed as item1; remains UNKNOWN/review, not materialized.']),perception_selectivity=dict(classification='CONDITIONAL PASS',native_sufficient_without_ocr=996,ocr_calls=4,vision_calls=4,no_measured_call_reduction_vs_attempt7=True,deterministic_table_independent_of_vision=True),provider_failure_impact=dict(classification='ACCEPTABLE BOUNDED PROVIDER LIMITATION; not a blocker of validated deterministic B1 path',failed_tasks='Two DETAIL_TRANSCRIPTION attempts on AnexoC p1',independent_source_review='AnexoC page1 visually inspected independently; no B1 truth inherited. Same two high-level goods/quantity values visible, but source/version/signatures remain distinct.',limits='Does not certify full scan fidelity or completeness in documents without equivalent digital evidence.'),capability_matrix=[dict(capability=k,status=v,evidence=e) for k,v,e in capabilities],uat_boundary=boundary,uat_metrics=metrics,thresholds='No thresholds invented or approved; define with human owner before UAT and assess by domain/criticality.',backlog=backlog,mvp06v_assessment='MVP-06.V CLOSED — within explicitly LIMITED UAT boundary',next_formal_phase='RELEASE CANDIDATE / UAT HARDENING',decision_scope='Propuesta de cierre para aceptación arquitectónica; no roadmap edit, no deployment, no persisted human acceptance, no general production certification.',no_code_change=True,no_frozen_artifact_change=True,no_provider_rerun=True,no_new_attempt=True)
(A/'semantic_adjudication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
capdoc='''# Declaración de capacidades para la primera UAT de LicitIA

Estado propuesto: LIMITED UAT. Audiencia: participantes informados y acompañados en entorno local controlado. Pendiente aceptación arquitectónica/humana de este alcance.

LicitIA ofrece asistencia documental trazable; no garantiza extracción completa ni aceptación autónoma de obligaciones. Todo uso contractual requiere contraste humano con originales.

## Qué puede probar el usuario

'''+ '\n'.join('- '+x for x in boundary['may_test'])+'''

## Qué requiere contraste y no debe asumirse

'''+ '\n'.join('- '+x for x in boundary['must_not_rely_on'])+'''

## Limitaciones que deben comunicarse al participante

- Los fabricantes/modelos embebidos se conservan en la descripción, pero no aparecen necesariamente como Attributes.
- Requirements puede incluir encabezados/contexto, truncaciones y obligaciones de otro actor; requiere decidir aplicabilidad.
- Requested Evidence puede representar paquetes incompletos, tipos demasiado amplios o contexto; no equivale al inventario de entrega.
- Tablas escaneadas/complex layouts y texto visual pueden fallar o alterar identificadores. Los estados de revisión no deben ocultarse.
- Source effects/resolución de conflictos y aceptación de alcance permanecen bajo decisión humana; no hay decisión automática de cumplimiento.
- Que un registro falte no significa que una obligación o accesorio no exista. Leer también prosa, anexos y referencias cruzadas.

Antes del primer piloto, entregar este documento y demostrar navegación a fuente, confirmación/corrección/rechazo y tratamiento de pendientes. Este artifact documenta la frontera; no afirma que ya se haya entregado a usuarios ni modificado la UI.
'''
(A/'uat_capability_statement.md').write_text(capdoc)
itemrows='\n'.join(f"| {x['item']} | `{x['scope_id']}` | {x['quantity']} {x['unit']} | {'F60…' if x['item']=='1' else 'L90…'} | PASS |" for x in items)
report=f'''# Attempt #9 — adjudicación semántica final MVP-06.V

**Decisión propuesta: OPTION B — LIMITED UAT.** La ruta central Native/Camelot→IR→Scope→Quantity→manifest queda demostrada sobre las dos partidas humanas de B1p1. Recomendación de evaluación: **MVP-06.V CLOSED**, bajo la frontera limitada documentada; siguiente fase **RELEASE CANDIDATE / UAT HARDENING**. La aceptación arquitectónica/humana final sigue pendiente: no se publica, cambia roadmap ni persiste aceptación de dominio en esta tarea.

No se exige autonomía total para una herramienta asistida. Sí se exige revisar originales, mantener incertidumbre visible y no presentar Requirements/Evidence como inventario completo. Por esos defectos no se recomienda UAT normal sin restricciones; tampoco se justifica bloquear todo piloto cuando las partidas/cantidades útiles están sustentadas y las salidas permanecen revisables.

## Integridad y método

Run `{result['run_id']}`, HEAD `{result['head']}`; first-pass `{result['first_pass_sha256']}`. Se verificaron pre-freeze/input-binding envelopes, FROZEN, manifiesto operacional1314archivos,32archivos del root y4560históricos; preservación inicial de1347archivos externos a esta adjudicación. Todos coinciden. Se revalida al cierre.

Sólo lectura de snapshots/originales y código relevante. Render local PDF para inspección humana/asistida; no nueva adquisición productiva. Replay **puro** sobre proposal guardado + Native words/offsets reales: match_cells/_prove_row; no rerun Camelot parser, DBwrites, materializadores, OCR, Vision o pipeline. Sin nuevas métricas productivas ni cambios fuente. Evidencia visual B1 y AnexoC conservada por separado. No se presenta esta evaluación de Codex como HumanTruth aprobada.

## Pruebas Camelot→Native, Scope y Quantities

Inspección visual B1p1 (originalSHA4c5c09719046f8e8a84b929cfc8a930eb9d700938a5e6c88d0f21ae457d00208): tabla explícita Partida/Descripción/Unidad de Medida/Cantidad, filas1/2. La tabla de normas inferior es distinta y no creó Scope. Cada bloque tiene fuente documental/página/revisión/generación Native y literalidad exactas, pertenencia única, headers y fila consistentes.

| Partida | ScopeDetail | Quantity | Modelo dentro de descripción | Juicio |
|---|---|---|---|---|
{itemrows}

Partida1:1PZA y descripción F60-U03-HKH-F8L-H6L-M6B-P6B-W7K, GE MULTILIN. Partida2:2PZA y descripción L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K, GE MULTILIN. La identidad no se deduce sólo de números: cada fila tiene columnaPartida, descripción de bien y pareja cantidad/unidad explícita. Se revisaron los textos completos, no sólo count2 o prefijos de modelos. No intercambio de descripciones/Quantity entre padres.

AmbosScope y ambasQuantity:review_required=True/confidence=None; effective_projection REVIEW_REQUIRED. LosScope conservan candidate_item_key y no afirman tender_item_id/scope_segment_id confiables. Es vinculación entre ScopeDetail e hijo, no promoción de owner contractual autónomo.

Camelot conserva raw_text sólo como metadata de comparación y propone geometría. Cada fragmento coincide con substring Native normalizado; source textSHA, originalSHA y generación coinciden con snapshot.37palabras únicas soportan24spans entre bloques. No texto exclusivo Camelot convertido en cita contractual.

2manifests válidos:0d5e4442ac675b1a473128551920816ab1509953164199de05842b4bf0b20f28 y659cc2dcb365ebebde555141cdf7bccaeafaf8c144035fdcb2d49140914f9070. Proof hashes, proposal hashes y source_identity hashes correctos. Replay puro produce el bloque idéntico, incluidos fragmentrefs y relaciones. Cada header y valor tiene span propio; el FieldBinding.description concatena múltiples fragmentos explícitamente, no una cita única fabricada. Source_excerpt persistido es un fragmento literal, y el usuario puede revisar el resto vía manifest/descripcion/fuente.

El ledger individual conserva IDs completos, source/page/generation, cada fragmento/celda/ref, descripción, Quantity y hashes. No se atribuye prueba o juicio de B1 a AnexoC.

## Attributes

**ACCEPTABLE MVP LIMITATION; POST-UAT IMPROVEMENT.** La causa sigue siendo exactamente la prevista: los bloques contienen sólo description/unit/quantity; FABRICANTE/MARCA y NUMERO/No.PARTE son líneas dentro de descripción, no fields brand/model. StructuredAttributeAdapter sólo recoge fields tipadosbrand/model sustentados. No fallo demostrado de persistencia del hijo.

La UI ScopeReview muestra machine.description completa (no sólo la tarjeta truncada), revisión efectiva, documento/revisión/página, excerpt y enlace a la página original. GE MULTILIN/F60/L90 siguen legibles allí. Por ello no bloquea un piloto de lectura/revisión; sí impide anunciar extracción/comparación automática de todos los atributos. No se añadieron reglas.

## Falsos positivos y cobertura

Se revisó exhaustivamente el conjunto **producido** por Camelot:2bloques/2Scope/2Quantity, todos B1p1 y sustentados.0falsos Scope/Quantity/ownership entre esos outputs;0Scope extra por normas/TOC/cuestionario/formularios/repeated headers. No existe log completo para adjudicar cada propuesta física descartada: falsos tablesproposed totales NOT_DIRECTLY_MEASURABLE, no se declara0universal.

No es prueba de recall global. B1pp2–4 todavía contienen embalaje,2juegos de cables por puerto,USB/Windows10,48h,marcado10mm y2juegos de contrato que no aparecen como estos2Scope/Quantity. No sumarlos a equipos ni inferir número de puertos. El piloto debe leer esa prosa y completar su checklist humano. La extracción tabular útil no equivale al alcance completo de suministro.

## Requirements y Requested Evidence

Comparación por hash original/página y campos de contenido/fuente, excluyendo IDs/timestamps regenerados: **31/31 Requirements exactos** respecto a#7 en canonical_text/category/requirement_text/excerpt primario; **8/8 Requested Evidence exactos** en hash/página/type/description/excerpt. comparison_ledger.json conserva ambosIDs y juicio previo. No se heredó juicio por conteo o UUID; tampoco se afirma identidad de metadatos de generaciones nuevas.

Se reutilizan15Requirements sustentados,8sustentados con defectos,8contextuales/no autónomos. TodosREVIEW_REQUIRED. Persisten encabezados, truncaciones, aplicabilidad/actor inciertos. Calidad **CONDITIONAL para asistencia limitada**, no barrera a todo UAT si originales/revisión son obligatorios; inadecuada para checklist autónomo o prueba de cumplimiento.

Evidence:1adecuado,5incompletos/mal tipados,2contextuales. Sobres/paquetes no equivalen a documentos autónomos; tiposFORM pueden ocultar inventario, certificado truncado no identifica documento completo y plantilla no implica obligación aplicable. **LIMITED UAT**, no adecuada para UATnormal de inventario contractual. Camelot no cambió esta ruta separada. No se ocultan misses anteriores ni se inventa recall de253páginas.

## V4a, V6c y fallos de proveedor

253estructurasreview/0trusted. Basesp13 índice y Cuestionariop12 mantienenREVIEW_REQUIRED,continuityUNKNOWN,outgoing_item_key=null. No nueva promoción numérica confiable; los2Scope tabulares se distinguen de esos falsos owners.

Propuestas Vision crudas conservan problemas:AnexoC1 L90-U03-LLH frente a HLH visible en imagen; Bases110 trata encabezado de modelo de carta como item1. Ambas quedan UNKNOWN/review y no producen Scope/Quantity. SafetyPASS para contención en esta ejecución; no certificación de fidelidad de toda propuesta de percepción.

V6c:996Native-sufficient no adquieren OCR por interpretación no resuelta;10deficits textuales/8planesVisualRequired;4OCR/4Vision dentro del perfil. Sin evidencia de escalation por interpretación sola. Comparado con#7, las llamadasVision siguen4: **no reducción medida**. El nuevo valor es que B1 digital materializa sin depender de una salidaVision, no un ahorro demostrado de llamadas.

Los2fallos son DETAIL_TRANSCRIPTION de AnexoCp1, duraciones60018/59355ms;2STRUCTURE completadas45217/24877ms. No suspensión. Inspección **independiente** del renderAnexoC confirma visualmente bienes/cantidades de su propia tabla; B1permanece fuente de los outputs adjudicados y no se le transfiere autoridad/versiones/signaturas. Losfallos no eliminan la evidencia esencial de las2partidas que B1permite recuperar determinísticamente. Son **acceptable bounded provider limitation**, irrelevantes al éxito de esa ruta digital; siguen siendo límite material para scans sin respaldo digital. No se recomienda condicionar release a este modeloOllama ni ocultar losfallos.

## Matriz de capacidad

| Capacidad | Estado | Evidencia/límite |
|---|---|---|
'''+ '\n'.join(f'| {k} | {v} | {e} |' for k,v,e in capabilities)+'''

## Decisión UAT y documentación para usuarios

Se elige exactamente **OPTION B — LIMITED UAT**. La declaración producto para participantes está en **uat_capability_statement.md**: ingesta, revisión de Scope/cantidades tabulares, provenance/navegación, propuestasRequirements/Evidence, conflictos y flujos humanos. Excluye reliance en extracción exhaustiva, Attributes embebidos, checklistEvidence definitivo, fidelidadScan y decisión contractual automática.

Este documento debe entregarse y aceptarse al iniciar el piloto; no se afirma que ya se haya entregado o que la interfaz haya cambiado. UAT debe incluir corrección/rechazo y consulta de originales. Sin estas condiciones la recomendaciónBno se extiende a uso externo normal.

## Métricas UAT propuestas, sin umbrales inventados

'''+ '\n'.join('- **'+m['name']+'**: '+m['definition'] for m in metrics)+'''

Registrar por dominio, documento, usuario y criticidad, con duración de validación y corrección. El inventario humano de comparación debe definirse independientemente; el número de outputs no es recall. Acordar metas con arquitecto/responsable deUAT antes de medir; no hay límites de aprobación fabricados en este informe.

## Backlog clasificado; nada implementado

'''+ '\n\n'.join('### '+k+'\n\n'+'\n'.join('- '+x for x in v) for k,v in backlog.items())+'''

## Cierre y siguiente fase

**MVP-06.V CLOSED para la frontera LIMITED UAT descrita**, como conclusión de esta adjudicación para decisión humana final. **RELEASE CANDIDATE / UAT HARDENING** es la siguiente fase formal propuesta; no V6e, Attempt10 ni desarrollo abierto de DocumentIntelligence. No equivale a certificación productiva, deployment o aceptación humana de cada hecho. Roadmap permanece sin editar, al estar esta tarea limitada a artifacts.

No hay release blocker observado en la literalidad, ownership o manifest de la tabla adjudicada. Las limitaciones mencionadas bloquean promesas autónomas/uso externo amplio y requieren losP0de hardening o una frontera explícita, no necesariamente impedir un piloto asistido controlado. No se sustituye toda la evaluación del expediente por2partidas exitosas.

## Verificación final

Sin source/config/schema, DBwrites,providers,rerunAttempt9/Attempt10,stage/commit/push. Artefactos operacionales y root congelados intactos; sólo nuevos artifacts bajo semantic_adjudication. No se reran suites: no cambia producción y las regresiones previas570/1153/2109 siguen evidencia operacional, no calidad semántica. git diff --check PASS, tracked limpio; integridad/poststatus y hashes adjuntos.

LICITIA BLIND ATTEMPT #9 FINAL RELEASE-GATE ADJUDICATION COMPLETE — READY FOR MVP CLOSURE DECISION
'''
(A/'semantic_adjudication.md').write_text(report)
for file in ['adjudicate9_integrity.py','adj9_compare.py','adj9_proof.py','adj9_finalize.py']:shutil.copyfile(Path('/private/tmp')/file,A/file)
preservation=read(A/'preservation_manifest.json');bad=[p for p,h in preservation.items() if not Path(p).is_file() or sha(p)!=h];assert not bad
hist=read(R/'backend/reports/camelot_native_table_spike/historical_baseline.json');assert all(sha(k)==v for k,v in hist.items())
for name,args in [('post_git_status.txt',['status','--short']),('post_git_diff_stat.txt',['diff','--stat']),('post_git_diff_check.txt',['diff','--check'])]:
 x=subprocess.run(['git',*args],cwd=R,capture_output=True,text=True);assert x.returncode==0;(A/name).write_text(x.stdout+x.stderr)
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).strip()
(A/'post_adjudication_integrity.json').write_text(json.dumps(dict(preserved_files_verified=len(preservation),historical_files_verified=len(hist),mismatches=bad,tracked_clean=True,staging_empty=True,code_changes=False,providers_rerun=False,pipeline_rerun=False,new_attempt=False),indent=2)+'\n')
hashes={str(x.relative_to(A)):sha(x) for x in A.rglob('*') if x.is_file() and x.name!='adjudication_artifacts.sha256.json'}
(A/'adjudication_artifacts.sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
for x in ['semantic_adjudication.md','semantic_adjudication.json','uat_capability_statement.md','adjudication_artifacts.sha256.json']:print(x,sha(A/x))
